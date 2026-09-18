"""Reviewer client wire/projection regressions; fake backend is not native proof."""
import copy
from pathlib import Path
from types import SimpleNamespace
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.reviewer.client import ReplayClient
from studio.reviewer.model import UiAction, Phase, UiCode, EventKind
from studio.host.replay.trace import default_trace
from studio.host.core.transport import epoch_ms
from studio.protocol.core import Response, Status


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.binding = {'run_id': 'run.client', 'command_id': 'run.client.play',
            'runtime_instance_id': 'runtime.client', 'generation': 1,
            'source_closure_sha256': '1' * 64, 'runtime_snapshot_sha256': '2' * 64,
            'trace_sha256': default_trace(17).raw_sha256, 'glb_sha256': '3' * 64}
        self.client = ReplayClient(port=12340, control_port=12341, stop_port=12342,
            credential=SimpleNamespace(bearer='private-test-value'), project_id='fixture.client', binding=self.binding)
        self.calls = []
        self.patch = patch.object(self.client, '_call', side_effect=self.wire)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def receipt(self, status='ACCEPTED_PENDING'):
        facts = {'public_ack': False}
        if status == 'COMMITTED':
            facts.update(binding=self.binding, native_capture_sha256='5' * 64, process={'pid': 123, 'process_start': 'windows:123456'},
                artifact={'kind': 'observation', 'sha256': '4' * 64, 'size_bytes': 100})
        return Response(Status(status), 'REPLAY_NATIVE_COMPLETED' if status == 'COMMITTED' else 'REPLAY_ADMITTED',
                        self.client._command, postconditions=facts).as_dict()

    def wire(self, route, body):
        self.calls.append((route, copy.deepcopy(body)))
        if route == '/v1/lease':
            return {'binding': self.binding, 'lease_id': 'lease.test', 'fencing_epoch': 1,
                'expected_revision': 'sha256:' + self.binding['runtime_snapshot_sha256'], 'expires_ms': epoch_ms() + 30_000}
        if route in ('/v1/commands', '/v1/lookup'):
            return self.receipt()
        if route == '/v1/stop':
            return {'stopped': True, 'draining': False, 'runtime_instance_id': self.binding['runtime_instance_id']}
        raise AssertionError(route)

    def test_play_attempt_only_once_repeated_click_is_same_id_lookup(self):
        self.assertEqual(self.client.perform(UiAction.PLAY).phase, Phase.RUNNING)
        self.assertEqual(self.client.perform(UiAction.PLAY).phase, Phase.RUNNING)
        self.assertEqual([r for r, _ in self.calls], ['/v1/lease', '/v1/commands', '/v1/lookup'])
        self.assertEqual(self.calls[1][1]['command_id'], self.calls[2][1]['command_id'])

    def test_reconnect_before_play_is_local_no_effect(self):
        event = self.client.perform(UiAction.LOOKUP)
        self.assertEqual((event.phase, event.code), (Phase.READY, UiCode.NO_COMMAND))
        self.assertEqual(self.calls, [])

    def test_early_lookup_waits_for_initial_post_instead_of_false_missing_command(self):
        entered, release = threading.Event(), threading.Event()
        original = self.wire
        def slow_lease(route, body):
            if route == '/v1/lease':
                entered.set()
                self.assertTrue(release.wait(2))
            return original(route, body)
        self.client._call.side_effect = slow_lease
        worker = threading.Thread(target=self.client.perform, args=(UiAction.PLAY,))
        worker.start()
        try:
            self.assertTrue(entered.wait(1))
            event = self.client.perform(UiAction.LOOKUP)
            self.assertEqual(event.phase, Phase.QUEUED)
            self.assertFalse(any(route == '/v1/lookup' for route, _ in self.calls))
        finally:
            release.set()
            worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(self.client.perform(UiAction.LOOKUP).phase, Phase.RUNNING)

    def test_response_loss_never_resubmits_play(self):
        original = self.wire
        def loss(route, body):
            result = original(route, body)
            if route == '/v1/commands':
                raise TimeoutError('private-test-value')
            return result
        self.client._call.side_effect = loss
        event = self.client.perform(UiAction.PLAY)
        self.assertEqual(event.kind, EventKind.DISCONNECTED)
        self.assertNotIn('private-test-value', repr(event))
        self.client.perform(UiAction.PLAY)
        self.assertEqual(sum(r == '/v1/commands' for r, _ in self.calls), 1)

    def test_stop_latches_before_io_and_never_claims_owner_closed(self):
        def stop(route, body):
            self.assertTrue(self.client._stopped.is_set())
            return self.wire(route, body)
        self.client._call.side_effect = stop
        result = self.client.perform(UiAction.STOP)
        self.assertEqual(result.phase, Phase.DRAINING)
        self.assertFalse(result.stop_confirmed)
        self.client.perform(UiAction.PLAY)
        self.assertFalse(any(route == '/v1/commands' for route, _ in self.calls))

    def test_stop_not_blocked_by_work_lock(self):
        self.client._work.acquire()
        try:
            self.assertEqual(self.client.perform(UiAction.STOP).phase, Phase.DRAINING)
        finally:
            self.client._work.release()

    def test_stale_binding_terminal_is_unknown_and_not_retained(self):
        self.client._attempted = True
        value = self.receipt('COMMITTED')
        value['postconditions']['binding'] = {**self.binding, 'generation': 2}
        self.client._call.side_effect = lambda *_: value
        result = self.client.perform(UiAction.LOOKUP)
        self.assertEqual((result.phase, result.code), (Phase.UNKNOWN, UiCode.INVALID_RESPONSE))
        self.assertIsNone(self.client._terminal)

    def test_foreign_command_receipt_rejected(self):
        self.client._attempted = True
        value = self.receipt('COMMITTED');value['command_id'] = 'other.command'
        self.client._call.side_effect = lambda *_: value
        self.assertEqual(self.client.perform(UiAction.LOOKUP).phase, Phase.UNKNOWN)

    def test_raw_exception_is_never_projected_to_ui(self):
        self.client._attempted = True
        self.client._call.side_effect = RuntimeError('private-test-value C:/secret/file')
        event = self.client.perform(UiAction.LOOKUP)
        self.assertEqual(event.code, UiCode.INVALID_RESPONSE)
        self.assertNotIn('private-test-value', repr(event))
        self.assertNotIn('secret/file', repr(event))

    def test_terminal_committed_projects_only_bound_metadata(self):
        self.client._attempted = True
        self.client._call.side_effect = lambda *_: self.receipt('COMMITTED')
        event = self.client.perform(UiAction.LOOKUP)
        self.assertEqual(event.phase, Phase.COMMITTED)
        self.assertEqual(event.historical.pid, 123)
        self.assertEqual(event.historical.source_sha256, self.binding['source_closure_sha256'])
        self.assertEqual(event.historical.rows, ())

    def test_canceled_receipt_requires_owner_cleanup(self):
        self.client._attempted = True
        self.client._call.side_effect = lambda *_: self.receipt('CANCELED')
        event = self.client.perform(UiAction.LOOKUP)
        self.assertEqual(event.phase, Phase.DRAINING)
        self.assertFalse(event.stop_confirmed)
        self.assertTrue(self.client._stopped.is_set())


if __name__ == '__main__':
    unittest.main()

"""Service lifecycle with a local fake backend and real sessions/journal.

Fake artifact bytes are deliberately not valid native evidence. These tests
exercise the coordinator's trust boundary and never claim engine validation.
"""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.host.core.limits import SafetyViolation
from studio.host.core.journal import JournalError
from studio.host.core.transport import epoch_ms
from studio.host.replay import contract, service
from studio.host.replay.trace import default_trace
from studio.protocol.core import Request, canonical_bytes
from studio.tests.replay import run_service_probe


class FakePreparedPlay:
    def __init__(self, root):
        self.root = root
        self.project = root / 'project'
        (self.project / 'out').mkdir(parents=True)
        self.trace = default_trace(17)
        self.binding = {'run_id': 'run.service', 'command_id': 'run.service.play',
            'runtime_instance_id': 'runtime.service', 'generation': 1,
            'source_closure_sha256': '1' * 64, 'runtime_snapshot_sha256': '2' * 64,
            'trace_sha256': self.trace.raw_sha256, 'glb_sha256': '3' * 64}
        self._done = threading.Event()
        self._result = None
        self.phase = 'PREPARED'
        self.starts = self.stops = self.closes = 0

    def status(self):
        return {'phase': self.phase, 'process': {'pid': 123, 'process_start': 'windows:123456'},
                'draining': self.phase == 'RUNNING', 'public_ack': False}

    def start(self):
        if self.phase != 'PREPARED':
            raise service.BackendError('FAKE_ALREADY_STARTED_OR_STOPPED')
        self.starts += 1
        self.phase = 'RUNNING'

    def complete(self, *, report_present=True):
        # Not native proof: only the backend's already-validated result boundary
        # is simulated here. Real observation verifier tests are separate.
        raw = b'{"test_fake_backend":true}\n'
        self._result = {'report_sha256': hashlib.sha256(raw).hexdigest()}
        (self.root / 'capture.json').write_bytes(canonical_bytes(self._result))
        if report_present:
            (self.project / 'out/report.json').write_bytes(raw)
        self.phase = 'COMPLETED'
        self._done.set()

    def stop(self):
        self.stops += 1
        self.phase = 'STOPPED_AFTER_COMPLETION' if self.phase == 'COMPLETED' else 'STOPPED'
        self._done.set()
        return self.status()

    def close(self):
        self.closes += 1
        self.stop()


class ReplayServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hh-replay-service-')
        self.addCleanup(self.temp.cleanup)
        self.type_patch = patch.object(service, 'PreparedPlay', FakePreparedPlay)
        self.type_patch.start()
        self.addCleanup(self.type_patch.stop)
        self.backend = FakePreparedPlay(Path(self.temp.name))
        self.owner = service.ReplayService(self.backend)
        self.addCleanup(self.owner.close)
        self.credential = self.owner.sessions.issue()
        self.lease = self.owner.lease({'project_id': self.owner.project_id, 'ttl_ms': 30_000}, **self.auth())

    def auth(self, credential=None):
        return {'authorization': 'Bearer ' + (credential or self.credential).bearer,
                'catalog_digest': contract.CATALOG_DIGEST}

    def request(self, command_id='command.start', operation='play.start', **changes):
        payload = {'expected_generation': 1,
            'expected_snapshot_sha256': self.backend.binding['runtime_snapshot_sha256'],
            'expected_source_sha256': self.backend.binding['source_closure_sha256'],
            'trace_sha256': self.backend.binding['trace_sha256']}
        fields = dict(command_id=command_id, project_id=self.owner.project_id, operation=operation,
            lease_id=self.lease['lease_id'], fencing_epoch=self.lease['fencing_epoch'],
            expected_revision=self.lease['expected_revision'], target={'stable_id': 'runtime.service'},
            payload=payload, payload_hash='sha256:' + hashlib.sha256(canonical_bytes(payload)).hexdigest(),
            deadline_ms=epoch_ms() + 15_000)
        fields.update(changes)
        return Request(**fields).as_dict()

    def lookup(self, command_id='command.start', credential=None):
        return self.owner.lookup({'project_id': self.owner.project_id, 'command_id': command_id},
                                 **self.auth(credential))

    def stop(self, command_id='command.stop'):
        return self.owner.stop({'project_id': self.owner.project_id, 'command_id': command_id}, **self.auth())

    def finish_thread(self):
        thread = self.owner._launch_thread
        self.assertIsNotNone(thread)
        thread.join(2)
        self.assertFalse(thread.is_alive(), 'completion worker did not finish')

    def rejects(self, code, call, *args, **kwargs):
        with self.assertRaises(SafetyViolation) as caught:
            call(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_start_is_pending_then_commits_only_after_bound_result_and_dedupes_once(self):
        request = self.request()
        pending = self.owner.submit(request, **self.auth())
        self.assertEqual(pending['status'], 'ACCEPTED_PENDING')
        self.assertFalse(pending['postconditions']['public_ack'])
        self.assertEqual(self.owner.submit(request, **self.auth()), pending)
        self.assertEqual(self.backend.starts, 1)
        self.backend.complete()
        self.finish_thread()
        committed = self.lookup()
        self.assertEqual(committed['status'], 'COMMITTED')
        self.assertEqual(committed['postconditions']['artifact']['sha256'], self.backend._result['report_sha256'])
        self.assertEqual(self.owner.submit(request, **self.auth()), committed)
        self.assertEqual(self.backend.starts, 1)

    def test_changed_payload_same_pending_id_cannot_poison_original_receipt(self):
        request = self.request()
        pending = self.owner.submit(request, **self.auth())
        altered = dict(request['payload'])
        altered['trace_sha256'] = '9' * 64
        collision = self.request(payload=altered,
            payload_hash='sha256:' + hashlib.sha256(canonical_bytes(altered)).hexdigest())
        self.rejects('REPLAY_COMMAND_ID_COLLISION', self.owner.submit, collision, **self.auth())
        self.assertEqual(self.lookup()['status'], pending['status'])
        self.backend.complete()
        self.finish_thread()
        self.assertEqual(self.lookup()['status'], 'COMMITTED')
        self.assertEqual(self.backend.starts, 1)

    def test_rotated_old_bearer_foreign_lease_and_revocation_cannot_launch(self):
        request = self.request()
        rotated = self.owner.sessions.rotate(self.credential)
        self.rejects('AUTH_REQUIRED', self.owner.submit, request, **self.auth())
        outsider = self.owner.sessions.issue()
        self.rejects('REPLAY_LEASE_REQUIRED', self.owner.submit, request, **self.auth(outsider))
        self.owner.sessions.revoke(rotated)
        self.rejects('AUTH_REQUIRED', self.owner.submit, request, **self.auth(rotated))
        self.assertEqual(self.backend.starts, 0)

    def test_rotated_grant_requires_fresh_lease_and_foreign_grant_cannot_borrow_it(self):
        rotated = self.owner.sessions.rotate(self.credential)
        self.rejects('REPLAY_LEASE_REQUIRED', self.owner.submit, self.request(), **self.auth(rotated))
        renewed = self.owner.lease({'project_id': self.owner.project_id, 'ttl_ms': 30_000}, **self.auth(rotated))
        self.assertGreater(renewed['fencing_epoch'], self.lease['fencing_epoch'])
        request = self.request(lease_id=renewed['lease_id'], fencing_epoch=renewed['fencing_epoch'])
        outsider = self.owner.sessions.issue()
        self.rejects('REPLAY_LEASE_REQUIRED', self.owner.submit, request, **self.auth(outsider))
        self.assertEqual(self.backend.starts, 0)
        self.assertEqual(self.owner.submit(request, **self.auth(rotated))['status'], 'ACCEPTED_PENDING')
        self.backend.complete()
        self.finish_thread()
        self.assertEqual(self.lookup(credential=rotated)['status'], 'COMMITTED')
        self.assertEqual(self.backend.starts, 1)

    def test_stop_before_start_latches_and_new_connections_cannot_resume(self):
        stopped = self.stop()
        self.assertTrue(stopped['stopped'])
        self.assertFalse(stopped['public_ack'])
        self.rejects('REPLAY_STOPPED', self.owner.submit, self.request(), **self.auth())
        self.rejects('REPLAY_STOPPED', self.owner.sessions.issue)
        self.assertEqual(self.backend.starts, 0)
        self.assertEqual(self.lookup('missing.command')['status'], 'UNKNOWN')

    def test_stop_during_pending_runtime_records_canceled_without_relaunch(self):
        request = self.request()
        self.owner.submit(request, **self.auth())
        self.stop()
        self.finish_thread()
        result = self.lookup()
        self.assertEqual(result['status'], 'CANCELED')
        self.assertIn('do_not_replay', result['postconditions']['next_action'])
        self.rejects('REPLAY_STOPPED', self.owner.submit, request, **self.auth())
        self.assertEqual(self.backend.starts, 1)

    def test_controls_still_work_when_work_slot_is_saturated(self):
        self.assertTrue(self.owner._work.acquire(blocking=False))
        try:
            self.rejects('REPLAY_WORK_BUSY', self.owner.submit, self.request(), **self.auth())
            self.assertEqual(self.lookup('missing.command')['status'], 'UNKNOWN')
            self.assertTrue(self.stop()['stopped'])
        finally:
            self.owner._work.release()
        self.assertEqual(self.backend.starts, 0)

    def test_read_only_grant_cannot_use_start_even_with_registered_lease(self):
        reader = self.owner.sessions.issue(operations=frozenset({'play.inspect', 'control.lookup'}))
        discovery = self.owner.discover({'project_id': self.owner.project_id}, **self.auth(reader))
        self.assertEqual([item['operation'] for item in discovery['capabilities']], ['play.inspect'])
        self.rejects('REPLAY_OPERATION_FORBIDDEN', self.owner.submit, self.request(), **self.auth(reader))
        self.rejects('REPLAY_OPERATION_FORBIDDEN', self.owner.stop,
            {'project_id': self.owner.project_id, 'command_id': 'read.stop'}, **self.auth(reader))
        self.assertEqual(self.backend.starts, 0)

    def test_missing_completion_postcondition_never_commits_and_closes_admission(self):
        self.owner.submit(self.request(), **self.auth())
        self.backend.complete(report_present=False)
        self.finish_thread()
        self.assertTrue(self.owner.sessions.status()['stopped'])
        result = self.lookup()
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertIn('do_not_replay', result['postconditions']['next_action'])
        self.assertEqual(self.backend.starts, 1)

    def test_late_completion_cannot_turn_expired_command_into_commit(self):
        request = self.request()
        self.owner.submit(request, **self.auth())
        with patch('studio.host.replay.session.epoch_ms', return_value=request['deadline_ms']):
            self.backend.complete()
            self.finish_thread()
        self.assertEqual(self.lookup()['status'], 'UNKNOWN')
        self.assertEqual(self.backend.starts, 1)

    def test_completion_persistence_failure_lookup_is_unknown_without_durable_success(self):
        self.owner.submit(self.request(), **self.auth())
        with patch.object(self.owner._journal, 'finish_command', side_effect=JournalError('JOURNAL_WRITE_FAILED')):
            self.backend.complete()
            self.finish_thread()
        result = self.lookup()
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertFalse(result['postconditions']['public_ack'])
        self.assertIn('do_not_replay', result['postconditions']['next_action'])
        self.assertTrue(self.owner.sessions.status()['stopped'])
        # Failed terminal persistence must not silently mutate the disk intent.
        disk = self.owner._journal.lookup(project_id=self.owner.project_id,
            command_id='command.start', now_ms=epoch_ms())
        self.assertEqual(disk['status'], 'ACCEPTED_PENDING')

    def test_durable_terminal_wins_if_finish_raises_after_commit(self):
        self.owner.submit(self.request(), **self.auth())
        original = self.owner._journal.finish_command

        def persist_then_raise(**fields):
            result = original(**fields)
            if fields['status'] == 'COMMITTED':
                raise JournalError('JOURNAL_DURABILITY_UNCONFIRMED')
            return result

        with patch.object(self.owner._journal, 'finish_command', side_effect=persist_then_raise):
            self.backend.complete()
            self.finish_thread()
        self.assertIn('command.start', self.owner._uncertain)
        self.assertTrue(self.owner.sessions.status()['stopped'])
        # The fallback cannot replace a successfully persisted terminal fact.
        result = self.lookup()
        self.assertEqual(result['status'], 'COMMITTED')
        self.assertEqual(result['code'], 'REPLAY_NATIVE_COMPLETED')
        disk = self.owner._journal.lookup(project_id=self.owner.project_id,
            command_id='command.start', now_ms=epoch_ms())
        self.assertEqual(result, disk['receipt'])

    def test_stop_persistence_failure_still_latches_runtime_and_work_admission(self):
        with patch.object(self.owner._journal, 'append_command', side_effect=JournalError('JOURNAL_WRITE_FAILED')):
            result = self.stop()
            self.owner._stop_thread.join(2)
            self.assertFalse(self.owner._stop_thread.is_alive())
        self.assertTrue(result['stopped'])
        self.assertFalse(result['public_ack'])
        self.assertEqual(self.owner._stop_persistence, 'UNKNOWN')
        self.rejects('REPLAY_STOPPED', self.owner.submit, self.request(), **self.auth())
        self.assertEqual(self.backend.starts, 0)

    def test_revoked_launch_grant_cannot_deliver_success_to_new_control_session(self):
        controller = self.owner.sessions.issue(operations=frozenset({'control.lookup', 'control.stop'}))
        self.owner.submit(self.request(), **self.auth())
        self.owner.sessions.revoke(self.credential)
        self.backend.complete()
        self.finish_thread()
        result = self.lookup(credential=controller)
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertIn('do_not_replay', result['postconditions']['next_action'])
        self.assertFalse(result['postconditions']['public_ack'])

    def test_close_drains_workers_and_rejects_further_routes(self):
        self.owner.submit(self.request(), **self.auth())
        self.owner.close()
        self.assertGreaterEqual(self.backend.closes, 1)
        self.assertFalse(self.owner._watchdog.is_alive())
        self.assertFalse(self.owner._launch_thread.is_alive())
        self.rejects('REPLAY_SERVICE_CLOSED', self.owner.lookup,
            {'project_id': self.owner.project_id, 'command_id': 'command.start'}, **self.auth())

    def test_probe_preserves_and_closes_cleanup_owner_when_prepare_raises(self):
        cleanup = FakePreparedPlay(self.backend.root / 'held-prepare')
        failure = service.BackendError('REPLAY_BACKEND_PREPARE_HELD', cleanup_owner=cleanup)
        with patch.object(run_service_probe.PreparedPlay, 'prepare', side_effect=failure) as prepare, \
             patch.object(run_service_probe, 'ReplayService') as owner, \
             patch.object(run_service_probe, 'ReplayTransport') as transport:
            with self.assertRaises(service.BackendError) as caught:
                run_service_probe.run('gt06-test-only-prepare', 'complete')
        self.assertIs(caught.exception, failure)
        self.assertIs(caught.exception.cleanup_owner, cleanup)
        self.assertEqual(cleanup.closes, 1)
        prepare.assert_called_once_with('gt06-test-only-prepare')
        owner.assert_not_called()
        transport.assert_not_called()


if __name__ == '__main__':
    unittest.main()

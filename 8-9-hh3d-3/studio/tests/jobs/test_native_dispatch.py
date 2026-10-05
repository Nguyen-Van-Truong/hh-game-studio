"""Real queue custody and real owner/session/ledger logic, inert Blender.

The reused writer-owner fixture models native effects and uses MemoryJournal.
These tests are not evidence of native Blender execution or full crash recovery.
"""
from dataclasses import replace
import hashlib
import importlib
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
sys.path.insert(0, str(STUDIO / 'tests/blender'))
fixture = importlib.import_module('test_client_writer_owner')
from studio.host.core.custody_registry import BASE_PATH
from studio.host.core.limits import SafetyViolation
from studio.host.core.transport import epoch_ms
from studio.host.blender.client_writer_transport import BlenderWriterClientTransport
from studio.host.jobs.native_dispatch import (BlenderOwnerBinding, NativeDispatchError,
                                             NativeOwnerDispatcher)
from studio.host.jobs.queue_owner import QueueOwner
from studio.protocol.core import Status


@unittest.skipUnless(os.name == 'nt', 'Windows native custody required')
class NativeDispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gt07-native-dispatch-')
        self.addCleanup(self.temp.cleanup)
        self.case = fixture.WriterOwnerTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.owner = self.case.owner
        self.case.host._close_lock = threading.RLock()
        root = Path(self.temp.name) / 'queue'
        root.mkdir()
        self.queue = QueueOwner.create(root)
        self.storage_id = self.queue.storage_id
        self.addCleanup(self.cleanup_queue)
        self.dispatch = NativeOwnerDispatcher(self.queue)

    def cleanup_queue(self):
        self.dispatch.close()
        self.queue.close()
        import winreg
        path = BASE_PATH + '\\' + self.storage_id
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0,
                            winreg.KEY_QUERY_VALUE | winreg.KEY_WOW64_64KEY) as key:
            self.assertEqual(winreg.QueryValueEx(key, 'Format'),
                (b'hh-registry-custody-1\0' + self.storage_id.encode(), winreg.REG_BINARY))
        winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, path, winreg.KEY_WOW64_64KEY, 0)

    def binding(self, body=None):
        return BlenderOwnerBinding.create(self.owner, body=body or self.case.body(),
                                           **self.case.kw)

    def admit(self, body=None):
        binding = self.binding(body)
        self.dispatch.register(binding)
        row = self.dispatch.enqueue(binding)
        return binding, row, self.dispatch.reserve()

    def test_exact_native_binding_rejects_fake_owner_constructor_and_mutation(self):
        with self.assertRaisesRegex(NativeDispatchError, 'NATIVE_BLENDER_OWNER_REQUIRED'):
            BlenderOwnerBinding.create(object(), body={}, **self.case.kw)
        with self.assertRaises(TypeError):
            BlenderOwnerBinding()
        binding = self.binding()
        self.assertNotIn(self.case.credential.bearer, repr(binding))
        object.__setattr__(binding, 'session_id', 'session.' + 'f' * 32)
        with self.assertRaisesRegex(NativeDispatchError, 'NATIVE_BINDING_CHANGED'):
            self.dispatch.register(binding)

    def test_request_is_detached_and_full_envelope_hash_includes_deadline(self):
        body = self.case.body()
        binding = self.binding(body)
        changed = dict(body, deadline_ms=body['deadline_ms'] - 1)
        other = self.binding(changed)
        self.assertEqual(body['digest'], changed['digest'])
        self.assertNotEqual(binding.command_sha256, other.command_sha256)
        self.assertEqual(binding.command_sha256, hashlib.sha256(binding.body).hexdigest())
        body['payload']['arguments']['size'][0] = 900
        self.dispatch.register(binding)
        self.dispatch.enqueue(binding)
        response = self.dispatch.advance(self.dispatch.reserve())
        self.assertIs(response.status, Status.COMMITTED)
        self.assertEqual(self.case.host.execute.call_args.args[0]['payload']['size'], [1, 2, 3])
        with self.assertRaisesRegex(NativeDispatchError, 'ALREADY_REGISTERED'):
            self.dispatch.register(other)

    def test_success_needs_owner_receipt_and_fresh_readback_ticket_once(self):
        binding, row, ticket = self.admit()
        forged = replace(ticket)
        with self.assertRaisesRegex(NativeDispatchError, 'RESERVATION_REQUIRED'):
            self.dispatch.advance(forged)
        response = self.dispatch.advance(ticket)
        self.assertIs(response.status, Status.COMMITTED)
        self.assertEqual(binding.lookup().as_dict(), response.as_dict())
        self.assertEqual(self.queue.broker.lookup(row.job.job_id).state, 'COMMITTED')
        read = self.case.host.submit.call_args.args[0]
        fixture.module.queue.c.identifier(read['command_id'])
        self.assertEqual(read['operation'], 'scene.inspect')
        with self.assertRaisesRegex(NativeDispatchError, 'RESERVATION_REQUIRED'):
            self.dispatch.advance(ticket)
        self.assertEqual(self.case.host.execute.call_count, 1)

    def test_stop_after_reserve_blocks_effect_and_is_durable(self):
        _, _, ticket = self.admit()
        stopped = self.dispatch.stop()
        self.assertTrue(stopped.stopped)
        self.assertTrue(self.owner.sessions._stopped.is_set())
        self.assertIn('native-stop', self.case.events)
        with self.assertRaisesRegex(NativeDispatchError, 'STOPPED'):
            self.dispatch.advance(ticket)
        self.case.host.execute.assert_not_called()
        self.assertEqual(len(self.queue.broker.snapshot().reservations), 1)

    def test_close_blocks_new_effect_and_gui_close_until_detached(self):
        _, _, ticket = self.admit()
        with self.assertRaisesRegex(Exception, 'BLENDER_QUEUE_DRAIN_REQUIRED'):
            self.case.host.close()
        with self.assertRaisesRegex(Exception, 'QUEUE_DISPATCHER_ACTIVE'):
            self.queue.close()
        self.dispatch.close()
        with self.assertRaisesRegex(NativeDispatchError, 'STOPPED'):
            self.dispatch.advance(ticket)
        self.assertIsNone(self.case.host._queue_dispatcher)
        self.case.host.execute.assert_not_called()

    def test_transport_and_second_queue_cannot_attach_same_owner(self):
        self.dispatch.register(self.binding())
        with self.assertRaisesRegex(SafetyViolation, 'ALREADY_ATTACHED'):
            BlenderWriterClientTransport(self.owner)
        self.dispatch.close()
        transport = BlenderWriterClientTransport(self.owner)
        try:
            with self.assertRaisesRegex(SafetyViolation, 'ALREADY_ATTACHED'):
                BlenderWriterClientTransport(self.owner)
            self.dispatch = NativeOwnerDispatcher(self.queue)
            with self.assertRaisesRegex(NativeDispatchError, 'ALREADY_BOUND'):
                self.dispatch.register(self.binding())
        finally:
            transport.close()
        self.dispatch.register(self.binding())

    def test_oversized_operation_deadline_rejected_before_queue_or_native(self):
        binding = self.binding(self.case.body(deadline_ms=epoch_ms() + 15000))
        self.dispatch.register(binding)
        with self.assertRaisesRegex(SafetyViolation, 'DEADLINE_EXPIRED'):
            self.dispatch.enqueue(binding)
        self.assertEqual(self.queue.broker.snapshot().pending, ())
        self.case.host.execute.assert_not_called()

    def test_revocation_after_reserve_never_calls_native_or_reissues_ticket(self):
        _, _, ticket = self.admit()
        self.owner.sessions.revoke(self.case.credential)
        with self.assertRaises(SafetyViolation):
            self.dispatch.advance(ticket)
        with self.assertRaisesRegex(NativeDispatchError, 'RESERVATION_REQUIRED'):
            self.dispatch.advance(ticket)
        self.case.host.execute.assert_not_called()
        self.assertEqual(len(self.queue.broker.snapshot().reservations), 1)

    def test_uncertain_native_response_keeps_reservation_and_blocks_retry(self):
        _, _, ticket = self.admit()
        self.case.host.execute.side_effect = OSError('injected native response loss')
        with self.assertRaises(NativeDispatchError):
            self.dispatch.advance(ticket)
        with self.assertRaisesRegex(NativeDispatchError, 'RESERVATION_REQUIRED'):
            self.dispatch.advance(ticket)
        self.assertEqual(self.case.host.execute.call_count, 1)
        self.assertEqual(len(self.queue.broker.snapshot().reservations), 1)

    def test_known_pre_intent_refusal_retires_without_inventing_ledger(self):
        _, row, ticket = self.admit()
        # A host-side newer revision rejects before any INTENT/effect.
        self.owner._read_owner._baseline = fixture.canonical_bytes(dict(
            self.case.scene, revision='sha256:' + 'b' * 64))
        response = self.dispatch.advance(ticket)
        self.assertIs(response.status, Status.REJECTED)
        self.assertEqual(response.code, 'BLENDER_STALE_REVISION')
        self.assertEqual(self.queue.broker.lookup(row.job.job_id).state, 'REJECTED')
        self.case.host.execute.assert_not_called()
        self.assertEqual(len(self.case.journal._records), 1)

    def test_lost_queue_receipt_reopens_and_reconciles_without_effect_replay(self):
        binding, _, ticket = self.admit()
        with patch.object(self.queue.broker, 'record_owner_result', side_effect=OSError('lost collection')):
            with self.assertRaises(OSError):
                self.dispatch.advance(ticket)
        self.dispatch.close()
        self.queue.close()
        self.queue = QueueOwner.reopen(self.storage_id)
        self.dispatch = NativeOwnerDispatcher(self.queue)
        self.dispatch.register(binding)
        recovered, = self.queue.broker.snapshot().reservations
        with self.assertRaisesRegex(NativeDispatchError, 'RESERVATION_REQUIRED'):
            self.dispatch.advance(recovered)
        result = self.dispatch.reconcile(recovered, binding)
        self.assertEqual(result.state, 'COMMITTED')
        self.assertEqual(self.case.host.execute.call_count, 1)
        keys = [call.args[0]['command_id'] for call in self.case.host.submit.call_args_list]
        self.assertEqual(len(keys), 2)
        self.assertNotEqual(keys[0], keys[1], 'recovery must not reuse cached inspection')

    def test_newer_manual_edit_prevents_reconciliation_and_is_preserved(self):
        binding, _, ticket = self.admit()
        with patch.object(self.queue.broker, 'record_owner_result', side_effect=OSError('lost collection')):
            with self.assertRaises(OSError):
                self.dispatch.advance(ticket)
        self.case.scene['snapshot']['objects'][0]['location'] = [7, 8, 9]
        self.case._revision()
        with self.assertRaisesRegex(NativeDispatchError, 'READBACK_CHANGED'):
            self.dispatch.reconcile(ticket, binding)
        self.assertEqual(self.case.host.execute.call_count, 1)
        self.assertEqual(self.case.scene['snapshot']['objects'][0]['location'], [7, 8, 9])
        self.assertEqual(len(self.queue.broker.snapshot().reservations), 1)

    def test_stop_during_native_effect_does_not_wait_for_queue_phase(self):
        _, _, ticket = self.admit()
        entered, release = threading.Event(), threading.Event()
        results, errors = [], []
        def blocked(command, **kwargs):
            entered.set()
            if not release.wait(2):
                raise AssertionError('inert native not released')
            return self.case._row(command, None, 'CANCELLED')
        self.case.host.execute.side_effect = blocked
        def worker():
            try:
                results.append(self.dispatch.advance(ticket))
            except BaseException as exc:
                errors.append(exc)
        thread = threading.Thread(target=worker)
        thread.start()
        try:
            self.assertTrue(entered.wait(1))
            self.dispatch.stop()
            self.assertTrue(self.owner.sessions._stopped.is_set())
        finally:
            release.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertIs(results[0].status, Status.CANCELED)

    def test_fresh_owner_command_cannot_replace_scene_during_collection(self):
        binding, _, ticket = self.admit()
        original = self.dispatch._collect
        outputs, failures = [], []
        def collect(*args):
            def caller():
                try:
                    outputs.append(self.owner.submit(self.case.body(command_id='other'), **self.case.kw))
                except BaseException as exc:
                    failures.append(exc)
            thread = threading.Thread(target=caller)
            thread.start()
            thread.join(1)
            self.assertFalse(thread.is_alive())
            return original(*args)
        with patch.object(self.dispatch, '_collect', side_effect=collect):
            self.dispatch.advance(ticket)
        self.assertEqual(failures, [])
        self.assertEqual(outputs[0].code, 'BLENDER_CLIENT_BUSY')
        self.assertEqual(self.case.host.execute.call_count, 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)

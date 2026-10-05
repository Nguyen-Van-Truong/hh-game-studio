"""O10 M6 host lifecycle: real queue custody, registered owner, inert Blender.

QueueOwner/DurableBroker use native Windows filesystem and Registry barriers.
The reused owner fixture supplies real session/ledger logic but MemoryJournal
and modeled Blender responses. Production BlenderUIHost.execute supplies its
polling deadline. These tests prove neither native Blender effects nor kill,
fsync of owner receipts, or a Stop latency percentile. Dispatcher.drain_stop
currently skips Blender; the deadline test proves its existing operation bound,
not a supervisor API that waits for an active Blender phase.
"""
from __future__ import annotations

import copy
import importlib
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
sys.path.insert(0, str(STUDIO / 'tests/blender'))
fixture = importlib.import_module('test_client_writer_owner')

from studio.host.core.custody_registry import BASE_PATH
from studio.host.core.limits import SafetyViolation
from studio.host.core.transport import epoch_ms
from studio.host.jobs.dispatch_policy import QueueLimits
from studio.host.jobs.durable_broker import BrokerError, DurableBroker
from studio.host.jobs.native_dispatch import (BlenderOwnerBinding, NativeDispatchError,
                                             NativeOwnerDispatcher)
from studio.host.jobs.queue_owner import QueueOwner
from studio.protocol.core import Status, canonical_bytes


@unittest.skipUnless(os.name == 'nt', 'Windows native queue custody required')
class GT07StopLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gt07-stop-lifecycle-')
        self.addCleanup(self.temp.cleanup)
        self.case = fixture.WriterOwnerTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.owner = self.case.owner
        self.case.host._close_lock = threading.RLock()
        self.limits = QueueLimits(pending=2, project_pending=2, session_pending=2,
                                  active=1, project_active=1, session_active=1)
        root = Path(self.temp.name) / 'queue'
        root.mkdir()
        self.queue = QueueOwner.create(root, limits=self.limits)
        self.storage_id = self.queue.storage_id
        self.assertIs(type(self.queue.broker), DurableBroker)
        self.dispatch = NativeOwnerDispatcher(self.queue)
        self.workers = []
        self.releases = []
        self.addCleanup(self.cleanup_queue)

    def cleanup_queue(self):
        for release in self.releases:
            release.set()
        for worker in self.workers:
            worker.join(3)
            self.assertFalse(worker.is_alive(), 'inert job outlived its test bound')
        self.dispatch.close()
        self.queue.close()
        import winreg
        path = BASE_PATH + '\\' + self.storage_id
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0,
                            winreg.KEY_QUERY_VALUE | winreg.KEY_WOW64_64KEY) as key:
            self.assertEqual(winreg.QueryValueEx(key, 'Format'),
                (b'hh-registry-custody-1\0' + self.storage_id.encode(), winreg.REG_BINARY))
        winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, path, winreg.KEY_WOW64_64KEY, 0)

    def binding(self, key, *, body=None, authorization=None):
        return BlenderOwnerBinding.create(self.owner,
            body=self.case.body(command_id=key) if body is None else body,
            authorization=self.case.auth if authorization is None else authorization,
            catalog_digest=self.case.kw['catalog_digest'])

    def enqueue(self, key, *, body=None):
        binding = self.binding(key, body=body)
        self.dispatch.register(binding)
        return binding, self.dispatch.enqueue(binding)

    def start(self, ticket):
        results, errors = [], []
        def advance():
            try:
                results.append(self.dispatch.advance(ticket))
            except BaseException as error:
                errors.append(error)
        worker = threading.Thread(target=advance, daemon=True)
        self.workers.append(worker)
        worker.start()
        return worker, results, errors

    def polling_native(self, *, cancel_on_stop):
        """Keep the production UI polling loop; model only its IPC responses."""
        entered = threading.Event()
        commands = {}
        def submit(command, **_):
            commands[command['command_id']] = copy.deepcopy(command)
            entered.set()
            return self.case._row(command, None, 'PENDING')
        def result(key):
            canceled = cancel_on_stop and self.case.host._stopped \
                and self.queue.broker.snapshot().stopped
            state = 'CANCELLED' if canceled else 'PENDING'
            return self.case._row(commands[key], None, state)
        self.case.host.submit.side_effect = submit
        self.case.host.result = Mock(side_effect=result)
        self.case.host.execute.side_effect = fixture.BlenderUIHost.execute.__get__(
            self.case.host, fixture.BlenderUIHost)
        return entered

    def test_stop_at_full_pending_cap_cancels_waiters_and_collects_running_cancel(self):
        _, active = self.enqueue('m6.active')
        ticket = self.dispatch.reserve()
        self.assertIsNotNone(ticket)
        waiting = [self.enqueue(key)[1] for key in ('m6.waiting.1', 'm6.waiting.2')]
        overflow = self.binding('m6.overflow')
        self.dispatch.register(overflow)
        with self.assertRaisesRegex(BrokerError, 'DISPATCH_CAPACITY'):
            self.dispatch.enqueue(overflow)
        self.assertEqual(len(self.queue.broker.snapshot().pending), self.limits.pending)

        entered = self.polling_native(cancel_on_stop=True)
        worker, results, errors = self.start(ticket)
        self.assertTrue(entered.wait(1), 'registered owner never reached inert IPC')
        started = time.monotonic()
        stopped = self.dispatch.stop()
        worker.join(2)
        self.assertFalse(worker.is_alive(), 'running cancellation did not drain')
        self.assertLess(time.monotonic() - started, 2)
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 1)
        self.assertIs(results[0].status, Status.CANCELED)
        self.assertTrue(stopped.stopped)
        self.assertEqual(stopped.pending, ())
        # Stop itself preserves active ownership; only the verified owner
        # terminal is allowed to release that reservation afterward.
        self.assertEqual(stopped.reservations[0].fence, ticket.fence)
        self.assertEqual({row.job.job_id for row in stopped.receipts},
                         {row.job.job_id for row in waiting})
        self.assertTrue(all(row.state == 'CANCELED' for row in stopped.receipts))
        final = self.queue.broker.snapshot()
        self.assertEqual(final.reservations, ())
        self.assertEqual(self.queue.broker.lookup(active.job.job_id).state, 'CANCELED')
        self.assertEqual(self.case.host.execute.call_count, 1)
        self.assertEqual(self.case.host.submit.call_count, 1)
        self.assertEqual(len(self.case.journal._records), 3, 'waiters must have no owner INTENT')
        with self.assertRaisesRegex(NativeDispatchError, 'STOPPED'):
            self.dispatch.advance(ticket)

    def test_noncooperating_running_poll_is_bounded_and_never_gets_false_terminal(self):
        body = self.case.body(command_id='m6.timeout', deadline_ms=epoch_ms() + 800)
        binding, row = self.enqueue('m6.timeout', body=body)
        ticket = self.dispatch.reserve()
        entered = self.polling_native(cancel_on_stop=False)
        started = time.monotonic()
        worker, results, errors = self.start(ticket)
        self.assertTrue(entered.wait(1))
        stopped = self.dispatch.stop()
        self.assertTrue(stopped.stopped)
        # The modeled IPC keeps returning PENDING after Stop; the existing
        # operation timeout, not a test-controlled release, ends the call.
        worker.join(2)
        self.assertFalse(worker.is_alive(), 'production polling exceeded its operation bound')
        self.assertLess(time.monotonic() - started, 2)
        self.assertEqual(results, [])
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], NativeDispatchError)
        self.assertEqual(errors[0].code, 'NATIVE_BLENDER_UNKNOWN_MISMATCH')
        timeout = self.case.host.execute.call_args.kwargs
        self.assertEqual(timeout['deadline_ms'], body['deadline_ms'])
        self.assertGreater(timeout['timeout'], 0)
        self.assertLessEqual(timeout['timeout'], .8)
        self.assertTrue(self.owner._held)
        retained = binding.lookup()
        self.assertIs(retained.status, Status.UNKNOWN)
        self.assertEqual(self.queue.broker.lookup(row.job.job_id).state, 'RESERVED')
        reservation, = self.queue.broker.snapshot().reservations
        self.assertEqual(reservation.fence, ticket.fence)
        self.assertEqual(self.queue.broker.snapshot().receipts, ())
        self.assertEqual(self.case.host.execute.call_count, 1)

    def test_reopen_after_stop_preserves_cancel_receipt_and_never_resumes_owner(self):
        _, row = self.enqueue('m6.reconnect.waiter')
        stopped = self.dispatch.stop()
        canceled = self.queue.broker.lookup(row.job.job_id)
        self.assertEqual(canceled.state, 'CANCELED')
        native_calls = self.case.host.execute.call_count
        for _ in range(2):
            self.dispatch.close()
            self.queue.close()
            self.queue = QueueOwner.reopen(self.storage_id, limits=self.limits)
            self.dispatch = NativeOwnerDispatcher(self.queue)
            self.assertEqual(self.queue.broker.snapshot(), stopped)
            self.assertIsNone(self.dispatch.reserve())
            self.assertEqual(self.queue.broker.lookup(row.job.job_id), canceled)
            with self.assertRaisesRegex(BrokerError, 'BROKER_STOPPED'):
                self.queue.broker.enqueue(fixture_job(), now_ms=epoch_ms())
            with self.assertRaisesRegex(SafetyViolation, 'STOPPED'):
                self.binding('m6.reconnect.new')
            self.assertEqual(self.case.host.execute.call_count, native_calls)
            self.assertEqual(len(self.case.journal._records), 1, 'reconnect created an owner INTENT')

    def test_rotation_mid_effect_denies_old_token_and_reconciles_with_current_observer(self):
        body = self.case.body(command_id='m6.rotate')
        old, row = self.enqueue('m6.rotate', body=body)
        ticket = self.dispatch.reserve()
        entered, release = threading.Event(), threading.Event()
        self.releases.append(release)
        def effect(command, **_):
            entered.set()
            if not release.wait(2):
                raise AssertionError('rotation test did not release the modeled effect')
            return self.case.execute(command)
        self.case.host.execute.side_effect = effect
        worker, results, errors = self.start(ticket)
        try:
            self.assertTrue(entered.wait(1))
            self.assertEqual(self.owner.sessions._activity()['write_phase'], 'DISPATCHING')
            rotated = self.owner.sessions.rotate(self.case.credential)
            current_auth = 'Bearer ' + rotated.bearer
            self.assertEqual(rotated.session_id, old.session_id)
            with self.assertRaisesRegex(SafetyViolation, 'AUTH_REQUIRED'):
                old.lookup()
        finally:
            release.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(results, [])
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], SafetyViolation)
        self.assertEqual(errors[0].code, 'AUTH_REQUIRED')
        with self.assertRaisesRegex(SafetyViolation, 'AUTH_REQUIRED'):
            old.lookup()
        observer_kw = dict(self.case.kw, authorization=current_auth)
        terminal = self.case.lookup(key=body['command_id'], **observer_kw)
        self.assertIs(terminal.status, Status.COMMITTED)
        self.assertEqual(self.queue.broker.lookup(row.job.job_id).state, 'RESERVED')
        self.assertEqual(self.case.host.execute.call_count, 1)
        self.assertEqual(len(self.case.scene['snapshot']['objects']), 1)
        self.assertEqual(self.owner.submit(body, **observer_kw), terminal)

        # An exact refreshed binding can reattach through the existing
        # lookup-only recovery route. It cannot enqueue or advance an effect.
        self.dispatch.close()
        self.queue.close()
        self.queue = QueueOwner.reopen(self.storage_id, limits=self.limits)
        self.dispatch = NativeOwnerDispatcher(self.queue)
        current = self.binding('m6.rotate', body=body, authorization=current_auth)
        self.assertEqual(current.command_sha256, old.command_sha256)
        self.dispatch.register_recovery(current)
        recovered, = self.queue.broker.snapshot().reservations
        self.assertTrue(recovered.recovered)
        with self.assertRaisesRegex(NativeDispatchError, 'RECOVERY_LOOKUP_ONLY'):
            self.dispatch.enqueue(current)
        with self.assertRaisesRegex(NativeDispatchError, 'RECOVERY_LOOKUP_ONLY'):
            self.dispatch.advance(recovered)
        reconciled = self.dispatch.reconcile(recovered, current)
        self.assertEqual(reconciled.state, 'COMMITTED')
        import hashlib
        self.assertEqual(reconciled.receipt_sha256,
                         hashlib.sha256(canonical_bytes(terminal.as_dict())).hexdigest())
        self.assertEqual(self.queue.broker.snapshot().reservations, ())
        self.assertEqual(self.case.host.execute.call_count, 1)
        self.assertEqual(len(self.case.scene['snapshot']['objects']), 1)
        self.assertEqual(len(self.case.journal._records), 3)


def fixture_job():
    from studio.host.jobs.durable_broker import JobRequest
    return JobRequest('m6.no.resume', 'blender.test', 'session.reconnect',
                      epoch_ms() + 1000, ('resource.reconnect',), (), '1' * 64)


if __name__ == '__main__':
    unittest.main()

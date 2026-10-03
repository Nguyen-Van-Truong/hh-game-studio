"""Actual Windows storage/reopen/crash tests; command-owner facts are synthetic.

No engine, payload execution or gameplay ACK is exercised. Failure injection is
named explicitly. The small-cap test is not a full 512-record capacity claim.
"""
from __future__ import annotations

from dataclasses import replace
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock
import uuid

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))

from studio.host.core.custody import WitnessCustody
from studio.host.core.custody_registry import BASE_PATH, RegistryCustody
from studio.host.core.private_events import EventLogError, PrivateEventLog
from studio.host.core.private_store import PrivateBlobStore
from studio.host.core.safe_replace import ProtectedFileRoot
from studio.host.jobs import durable_broker as module
from studio.host.jobs.dispatch_policy import QueueLimits
from studio.host.jobs.durable_broker import (BrokerError, DurableBroker, Fence,
                                            JobRequest, OwnerResult)


def request(key, *, project='project-a', session='session-a', resources=None,
            dependencies=(), deadline=100_000):
    return JobRequest(key, project, session, deadline,
                      (key + '.resource',) if resources is None else resources,
                      dependencies, hashlib.sha256(key.encode()).hexdigest())


def owner_result(reservation, outcome='COMMITTED'):
    # This deliberately simulates the integration's verified owner receipt.
    # It is not proof that a native application executed any command.
    return OwnerResult(outcome, reservation.command_sha256,
                       hashlib.sha256((reservation.job.job_id + outcome).encode()).hexdigest())


class _Fixture:
    def __init__(self, base, limits=QueueLimits()):
        self.base, self.limits, self.local_id = base, limits, uuid.uuid4().hex
        self.files = self.blobs = self.events = self.registry = self.broker = None
        self.created = False
        parent = base / ('files-' + self.local_id)
        parent.mkdir()
        self.files = ProtectedFileRoot.create(parent)
        self.blobs = PrivateBlobStore.create(base)
        self.events = PrivateEventLog.create(base)
        self.registry = RegistryCustody.create(self.local_id)
        self.created = True
        self.custody = WitnessCustody(self.registry, storage_id=self.local_id,
                                     project_id='queue-test', create=True)
        self.custody.activate(file_root=self.files.root, file_identity=self.files.root_identity,
                             blob_root=self.blobs.root, blob_identity=self.blobs.root_identity,
                             event_root=self.events.root, event_binding=self.events.binding())
        self.events.bind_custody(self.custody)
        self.broker = DurableBroker(self.events, limits=limits)

    def close(self):
        for name in ('broker', 'events', 'registry', 'blobs', 'files'):
            value = getattr(self, name)
            if value is not None:
                value.close()
                setattr(self, name, None)

    def reopen(self):
        self.close()
        self.registry = RegistryCustody.reopen(self.local_id)
        self.custody = WitnessCustody(self.registry, storage_id=self.local_id, project_id='queue-test')
        self.events = PrivateEventLog.reopen(self.custody.record['events']['path'], self.custody.binding)
        self.events.bind_custody(self.custody)
        self.broker = DurableBroker(self.events, limits=self.limits)
        return self.broker

    def cleanup(self):
        self.close()
        if not self.created:
            return
        import winreg
        leaf = BASE_PATH + '\\' + self.local_id
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, leaf, 0,
                            winreg.KEY_QUERY_VALUE | winreg.KEY_WOW64_64KEY) as key:
            marker, kind = winreg.QueryValueEx(key, 'Format')
        if (marker, kind) != (b'hh-registry-custody-1\0' + self.local_id.encode(), winreg.REG_BINARY):
            raise AssertionError('Refusing cleanup of an unowned registry leaf')
        winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, leaf, winreg.KEY_WOW64_64KEY, 0)
        self.created = False


@unittest.skipUnless(os.name == 'nt', 'Windows retained handles and registry required')
class DurableBrokerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        RegistryCustody.provision_base()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gt07-queue-', dir=os.getenv('GT07_TEST_ROOT'))
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.fixture = self.make_fixture()
        self.broker = self.fixture.broker

    def make_fixture(self, limits=QueueLimits()):
        fixture = _Fixture(self.base, limits)
        self.addCleanup(fixture.cleanup)
        return fixture

    def admit(self, key, **kwargs):
        return self.broker.enqueue(request(key, **kwargs), now_ms=1_000)

    def reserve(self):
        return self.broker.reserve_next(now_ms=1_000)

    def test_pending_flood_caps_leave_admission_for_another_project(self):
        # Real default profile; active quotas alone cannot enforce admission.
        for index in range(8):
            self.admit(f'session-fill-{index}')
        head = self.broker.snapshot().head
        with self.assertRaisesRegex(BrokerError, 'DISPATCH_PENDING_OVER_QUOTA'):
            self.admit('session-overflow')
        self.assertEqual(self.broker.snapshot().head, head)
        for session in range(1, 4):
            for index in range(8):
                self.admit(f'project-fill-{session}-{index}', session=f'session-{session}')
        head = self.broker.snapshot().head
        with self.assertRaisesRegex(BrokerError, 'DISPATCH_PENDING_OVER_QUOTA'):
            self.admit('project-overflow', session='fresh-session')
        self.assertEqual(self.broker.snapshot().head, head)
        other = self.admit('other-project', project='project-b')
        self.assertEqual(other.state, 'QUEUED')
        self.assertEqual(len(self.broker.snapshot().pending), 33)
        self.assertTrue(self.broker.stop().stopped)

    def test_default_native_stream_capacity_keeps_receipts_and_stop_headroom(self):
        # Actual default storage limits and native writes; owner results remain
        # synthetic. This measures record exhaustion, not disk-full/compaction.
        completed = []
        for index in range(module.MAX_RECORDS):
            key = f'capacity-{index}'
            before = self.broker.snapshot()
            try:
                self.admit(key)
            except BrokerError as exc:
                self.assertEqual(exc.code, 'BROKER_JOURNAL_FULL')
                self.assertFalse(exc.outcome_unknown)
                self.assertIn('drain/reconcile', exc.next_action)
                self.assertEqual(self.broker.snapshot(), before)
                self.assertIsNone(self.broker.lookup(key))
                break
            reserved = self.reserve()
            self.assertEqual(reserved.job.job_id, key)
            completed.append(self.broker.record_owner_result(reserved, owner_result(reserved)))
        else:
            self.fail('default stream did not refuse before its record bound')
        self.assertGreater(len(completed), self.broker.limits.pending)
        self.assertFalse(before.pending or before.reservations)
        self.assertLessEqual(before.head.sequence, module.MAX_RECORDS)
        self.assertLessEqual(before.head.size, module.MAX_LOG_BYTES)
        self.broker = self.fixture.reopen()
        self.assertEqual(self.broker.snapshot().receipts, tuple(completed))
        stopped = self.broker.stop()
        self.assertTrue(stopped.stopped)
        self.assertEqual(stopped.receipts, tuple(completed))
        self.assertEqual(stopped.head.sequence, before.head.sequence + 1)
        self.broker = self.fixture.reopen()
        self.assertTrue(self.broker.snapshot().stopped)
        self.assertIsNone(self.broker.reserve_next(now_ms=1_000))
        print(f'GT07_CAPACITY jobs={len(completed)} records={stopped.head.sequence} '
              f'bytes={stopped.head.size} max_records={module.MAX_RECORDS} '
              f'max_bytes={module.MAX_LOG_BYTES}', flush=True)

    def test_native_reservation_cursor_restart_and_no_duplicate_dispatch(self):
        self.admit('a1')
        self.admit('a2', session='session-b')
        self.admit('b1', project='project-b')
        first = self.reserve()
        self.assertEqual(first.job.job_id, 'a1')
        before = self.broker.snapshot()
        self.broker = self.fixture.reopen()
        restored = self.broker.snapshot()
        self.assertEqual(restored.cursor, before.cursor)
        self.assertEqual(restored.reservations[0].fence, first.fence)
        self.assertTrue(restored.reservations[0].recovered)
        second = self.reserve()
        self.assertEqual(second.job.job_id, 'b1')
        self.assertGreater(second.fence.generation, first.fence.generation)
        self.assertEqual(second.fence.stream_id, first.fence.stream_id)
        self.assertEqual(self.reserve().job.job_id, 'a2')
        self.assertIsNone(self.reserve())
        self.assertEqual(len(self.broker.snapshot().reservations), 3)

    def test_unknown_and_expired_active_reservation_keep_resource_and_dependency(self):
        self.admit('first', resources=('shared.tscn',), deadline=1_001)
        first = self.reserve()
        self.admit('blocked', project='project-b', resources=('shared.tscn',), dependencies=('first',))
        self.broker.record_owner_result(first, owner_result(first, 'UNKNOWN'))
        self.broker = self.fixture.reopen()
        self.assertEqual(self.broker.lookup('first').state, 'UNKNOWN')
        self.assertIsNone(self.broker.reserve_next(now_ms=2_000))
        active = self.broker.snapshot().reservations[0]
        self.broker.record_owner_result(active, owner_result(active))
        self.assertEqual(self.broker.reserve_next(now_ms=2_000).job.job_id, 'blocked')

    def test_terminal_owner_receipt_reopen_unlocks_dependency_without_storage_ack(self):
        self.admit('source')
        self.admit('dependent', dependencies=('source',))
        self.assertEqual(self.broker.lookup('source').state, 'QUEUED')
        active = self.reserve()
        self.assertEqual(self.broker.lookup('source').state, 'RESERVED')
        self.assertEqual(self.broker.snapshot().receipts, ())
        self.broker.record_owner_result(active, owner_result(active))
        self.broker = self.fixture.reopen()
        result = self.broker.lookup('source')
        self.assertEqual(result.state, 'COMMITTED')
        self.assertEqual(result.receipt_sha256, owner_result(active).receipt_sha256)
        self.assertEqual(self.reserve().job.job_id, 'dependent')

    def test_bad_fence_or_untrusted_receipt_cannot_release_reservation(self):
        self.admit('source')
        active = self.reserve()
        head = self.broker.snapshot().head
        for reservation, result in (
                (active, {'outcome': 'COMMITTED'}),
                (replace(active, fence=Fence(active.fence.stream_id, active.fence.generation + 1)), owner_result(active)),
                (replace(active, fence=Fence('other-stream', active.fence.generation)), owner_result(active)),
                (active, replace(owner_result(active), command_sha256='0' * 64)),
                (active, replace(owner_result(active), receipt_sha256='not-a-digest'))):
            with self.subTest(reservation=reservation, result=result), self.assertRaises(BrokerError):
                self.broker.record_owner_result(reservation, result)
        self.assertEqual(self.broker.snapshot().head, head)
        self.assertEqual(self.broker.lookup('source').state, 'RESERVED')

    def test_repeat_id_self_cycle_forward_cycle_and_duplicate_dependencies_fail_closed(self):
        for key, dependencies in (('self', ('self',)), ('cycle-a', ('cycle-b',)), ('cycle-b', ('cycle-a',))):
            with self.assertRaisesRegex(BrokerError, 'BROKER_DEPENDENCY_INVALID'):
                self.admit(key, dependencies=dependencies)
        self.admit('once')
        with self.assertRaisesRegex(BrokerError, 'BROKER_ID_CONFLICT'):
            self.admit('once')
        with self.assertRaisesRegex(BrokerError, 'DISPATCH_JOB_INVALID'):
            self.admit('duplicate-dependency', dependencies=('once', 'once'))
        active = self.reserve()
        self.broker.record_owner_result(active, owner_result(active, 'REJECTED'))
        self.broker = self.fixture.reopen()
        with self.assertRaisesRegex(BrokerError, 'BROKER_ID_CONFLICT'):
            self.admit('once')

    def test_pending_cap_cannot_block_stop_or_resume_after_reopen(self):
        fixture = self.make_fixture(QueueLimits(pending=2))
        self.broker = fixture.broker
        self.admit('active')
        active = self.reserve()
        self.admit('queued-1')
        self.admit('queued-2')
        with self.assertRaisesRegex(BrokerError, 'DISPATCH_CAPACITY'):
            self.admit('overflow')
        stopped = self.broker.stop()
        self.assertTrue(stopped.stopped)
        self.assertEqual(stopped.pending, ())
        self.assertEqual({row.state for row in stopped.receipts}, {'CANCELED'})
        self.assertEqual(stopped.reservations[0].fence, active.fence)
        self.broker = fixture.reopen()
        self.assertIsNone(self.reserve())
        with self.assertRaisesRegex(BrokerError, 'BROKER_STOPPED'):
            self.admit('reconnect')
        self.broker.record_owner_result(self.broker.snapshot().reservations[0], owner_result(active, 'CANCELED'))
        self.assertTrue(self.broker.stop().stopped)
        self.assertIsNone(self.reserve())

    def test_project_session_and_global_caps_preserve_other_project_progress(self):
        self.admit('a1')
        self.admit('a-same')
        self.admit('a2', session='session-b')
        self.admit('a-over', session='session-c')
        self.admit('b1', project='project-b')
        self.admit('b2', project='project-b', session='session-b')
        self.admit('c1', project='project-c')
        selected = [self.reserve().job.job_id for _ in range(4)]
        self.assertEqual(selected, ['a1', 'b1', 'c1', 'a2'])
        self.assertIsNone(self.reserve())
        self.assertEqual({job.job_id for job in self.broker.snapshot().pending}, {'a-same', 'a-over', 'b2'})

    def test_shared_resource_fifo_and_two_concurrent_callers_get_one_reservation(self):
        self.admit('old', resources=('shared.blend',))
        self.admit('young', project='project-b', resources=('shared.blend',))
        barrier = threading.Barrier(3)
        results, errors = [], []
        def worker():
            try:
                barrier.wait(timeout=5)
                results.append(self.reserve())
            except BaseException as exc:
                errors.append(exc)
        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait(timeout=5)
        for thread in threads:
            thread.join(10)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertEqual(sum(result is None for result in results), 1)
        self.assertEqual(next(result for result in results if result is not None).job.job_id, 'old')

    def test_exact_storage_custody_and_single_writer_are_mandatory(self):
        with self.assertRaisesRegex(BrokerError, 'BROKER_TRUSTED_LOG_REQUIRED'):
            DurableBroker(str(self.base))
        with PrivateEventLog.create(self.base) as unbound:
            with self.assertRaisesRegex(BrokerError, 'BROKER_CUSTODY_REQUIRED'):
                DurableBroker(unbound)
        with self.assertRaisesRegex(BrokerError, 'BROKER_ALREADY_OWNED'):
            DurableBroker(self.fixture.events)
        with self.assertRaises(EventLogError):
            PrivateEventLog.reopen(self.fixture.events.root, self.fixture.custody.binding)

    def test_expired_pending_gets_rejected_tombstone_but_active_never_expires(self):
        self.admit('active', deadline=1_001)
        self.reserve()
        self.admit('expires', project='project-b', deadline=1_001)
        self.assertIsNone(self.broker.reserve_next(now_ms=1_001))
        self.assertEqual(self.broker.lookup('expires').state, 'REJECTED')
        self.assertEqual(self.broker.lookup('active').state, 'RESERVED')
        self.assertIsNone(self.broker.lookup('expires').receipt_sha256)
        with self.assertRaisesRegex(BrokerError, 'BROKER_CLOCK_INVALID'):
            self.reserve()

    def test_expiration_removes_dead_project_cursor_before_atomic_selection(self):
        self.admit('old-a')
        active = self.reserve()
        self.broker.record_owner_result(active, owner_result(active))
        self.admit('expired-a', deadline=1_001)
        self.admit('live-b', project='project-b')
        selected = self.broker.reserve_next(now_ms=1_001)
        self.assertEqual(selected.job.job_id, 'live-b')
        expected = (('project-b', 'session-a'),)
        self.assertEqual(self.broker.snapshot().cursor.sessions, expected)
        self.assertEqual(self.broker.lookup('expired-a').state, 'REJECTED')
        self.broker = self.fixture.reopen()
        self.assertEqual(self.broker.snapshot().cursor.sessions, expected)

    def test_injected_small_capacity_preserves_terminal_and_stop_headroom(self):
        # Deliberately reduced cap, actual native append/readback, no compaction.
        with mock.patch.object(module, 'MAX_RECORDS', 12), \
                mock.patch('studio.host.core.private_events.MAX_RECORDS', 12):
            for index in range(3):
                self.admit(f'job-{index}')
                active = self.reserve()
                self.broker.record_owner_result(active, owner_result(active))
            with self.assertRaisesRegex(BrokerError, 'BROKER_JOURNAL_FULL') as caught:
                self.admit('full')
            self.assertIn('rotation is not implemented', caught.exception.next_action)
            self.assertEqual(self.broker.snapshot().head.sequence, 11)
            self.assertTrue(self.broker.stop().stopped)
            self.assertEqual(self.broker.snapshot().head.sequence, 12)

    def test_injected_failure_after_durable_reserve_poison_no_retry_reopen_holds(self):
        self.admit('work')
        append = self.fixture.events.append
        def lose_reply(*args, **kwargs):
            append(*args, **kwargs)
            raise RuntimeError('injected broker receipt loss after durable barrier')
        with mock.patch.object(self.fixture.events, 'append', side_effect=lose_reply):
            with self.assertRaisesRegex(BrokerError, 'BROKER_PERSIST_UNCERTAIN') as caught:
                self.reserve()
        self.assertTrue(caught.exception.outcome_unknown)
        with self.assertRaisesRegex(BrokerError, 'BROKER_RECOVERY_REQUIRED'):
            self.reserve()
        self.broker = self.fixture.reopen()
        self.assertIsNone(self.reserve())
        self.assertTrue(self.broker.snapshot().reservations[0].recovered)

    def test_injected_custody_failure_preserves_ahead_stream_without_auto_rebind(self):
        self.admit('work')
        saved = self.fixture.custody.binding
        with mock.patch.object(self.fixture.custody, 'persist_binding', side_effect=RuntimeError('injected custody outage')):
            with self.assertRaisesRegex(BrokerError, 'BROKER_PERSIST_UNCERTAIN'):
                self.reserve()
        root = self.fixture.events.root
        self.fixture.close()
        with PrivateEventLog.reopen(root, saved) as ahead:
            self.assertGreater(ahead.binding().witnessed.sequence, saved.witnessed.sequence)
            with self.assertRaisesRegex(BrokerError, 'BROKER_CUSTODY_REQUIRED'):
                DurableBroker(ahead)
            with RegistryCustody.reopen(self.fixture.local_id) as registry:
                custody = WitnessCustody(registry, storage_id=self.fixture.local_id, project_id='queue-test')
                with self.assertRaisesRegex(EventLogError, 'EVENT_CUSTODY_BINDING_MISMATCH'):
                    ahead.bind_custody(custody)

    def test_injected_stop_during_reservation_barrier_never_returns_launch_ticket(self):
        self.admit('work')
        append = self.fixture.events.append
        entered, release = threading.Event(), threading.Event()
        results, errors = [], []
        def delayed(*args, **kwargs):
            head = append(*args, **kwargs)
            if args[0]['kind'] == 'RESERVE':
                entered.set()
                if not release.wait(5):
                    raise RuntimeError('test synchronization timeout')
            return head
        def reserve_worker():
            try:
                results.append(self.reserve())
            except BaseException as exc:
                errors.append(exc)
        def stop_worker():
            try:
                results.append(self.broker.stop())
            except BaseException as exc:
                errors.append(exc)
        reserving, stopping = threading.Thread(target=reserve_worker), threading.Thread(target=stop_worker)
        with mock.patch.object(self.fixture.events, 'append', side_effect=delayed):
            reserving.start()
            self.assertTrue(entered.wait(5))
            stopping.start()
            # Instrument the latch, not a guessed sleep or the Stop result.
            for _ in range(1000):
                if self.broker._stop_requested:
                    break
                threading.Event().wait(.001)
            self.assertTrue(self.broker._stop_requested)
            release.set()
            reserving.join(5)
            stopping.join(5)
        self.assertEqual(errors, [])
        self.assertIn(None, results)
        self.assertTrue(self.broker.snapshot().stopped)
        self.assertEqual(len(self.broker.snapshot().reservations), 1)

    def test_actual_child_exit_after_reservation_before_dispatch_cannot_reissue(self):
        self.admit('crash-job')
        self.fixture.close()
        script = r'''
import os, sys
sys.path.insert(0, sys.argv[1])
from studio.host.core.custody_registry import RegistryCustody
from studio.host.core.custody import WitnessCustody
from studio.host.core.private_events import PrivateEventLog
from studio.host.jobs.durable_broker import DurableBroker
registry = RegistryCustody.reopen(sys.argv[2])
custody = WitnessCustody(registry, storage_id=sys.argv[2], project_id='queue-test')
events = PrivateEventLog.reopen(custody.record['events']['path'], custody.binding)
events.bind_custody(custody)
broker = DurableBroker(events)
reservation = broker.reserve_next(now_ms=1000)
assert reservation.job.job_id == 'crash-job'
print('DURABLE_RESERVATION_BEFORE_DISPATCH', flush=True)
os._exit(73)
'''
        child = subprocess.run([sys.executable, '-B', '-c', script, str(STUDIO.parent), self.fixture.local_id],
                               capture_output=True, text=True, timeout=30)
        self.assertEqual(child.returncode, 73, child.stdout + child.stderr)
        self.assertEqual(child.stdout.strip(), 'DURABLE_RESERVATION_BEFORE_DISPATCH')
        self.assertEqual(child.stderr, '')
        self.broker = self.fixture.reopen()
        self.assertIsNone(self.reserve())
        self.assertEqual(self.broker.snapshot().reservations[0].job.job_id, 'crash-job')
        self.assertTrue(self.broker.snapshot().reservations[0].recovered)


if __name__ == '__main__':
    unittest.main()

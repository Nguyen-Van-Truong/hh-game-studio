"""Native custody-backed segmented queue journal tests (no engine/ACK claim)."""
from contextlib import ExitStack
import hashlib
import os
from pathlib import Path
import tempfile
import time
import unittest
import uuid

STUDIO = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(STUDIO.parent))

from studio.host.core.custody import WitnessCustody, binding_from
from studio.host.core.custody_registry import BASE_PATH, RegistryCustody
from studio.host.core.private_events import PrivateEventLog
from studio.host.core.private_store import PrivateBlobStore
from studio.host.core.safe_replace import ProtectedFileRoot
from studio.host.jobs.segmented_journal import QueueJournalManager, descriptor_from
from studio.host.jobs.queue_owner import QueueOwner
from studio.host.jobs.durable_broker import BrokerError, JobRequest, OwnerResult


@unittest.skipUnless(os.name == 'nt', 'Windows native custody required')
class SegmentedJournalTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix='gt07-segments-'))).resolve()
        RegistryCustody.provision_base()
        self.storage_id = uuid.uuid4().hex
        self.registry = RegistryCustody.create(self.storage_id)
        self.stack.callback(self._remove_registry)
        self.stack.callback(self.registry.close)
        file_parent = self.root / 'files'
        file_parent.mkdir()
        self.files = self.stack.enter_context(ProtectedFileRoot.create(file_parent))
        self.blobs = self.stack.enter_context(PrivateBlobStore.create(self.root))
        self.old = self.stack.enter_context(PrivateEventLog.create(self.root))
        self.custody = WitnessCustody(self.registry, storage_id=self.storage_id,
                                      project_id='studio.scheduler', create=True)
        self.custody.activate(file_root=self.files.root, file_identity=self.files.root_identity,
                              blob_root=self.blobs.root, blob_identity=self.blobs.root_identity,
                              event_root=self.old.root, event_binding=self.old.binding())
        self.old.bind_custody(self.custody)
        self._append({'schema': 'hh-durable-dispatch-1', 'kind': 'ENQUEUE',
                      'job': {'job_id': 'old-job', 'project_id': 'p', 'session_id': 's',
                              'sequence': 1, 'deadline_ms': 100000,
                              'resources': ['r'], 'dependencies': []},
                      'command_sha256': hashlib.sha256(b'old').hexdigest(), 'now_ms': 1})
        self._append({'schema': 'hh-durable-dispatch-1', 'kind': 'OWNER_RESULT',
                      'job_id': 'old-job', 'fence': {'stream_id': 'logical', 'generation': 1},
                      'outcome': 'COMMITTED',
                      'command_sha256': hashlib.sha256(b'old').hexdigest(),
                      'receipt_sha256': hashlib.sha256(b'receipt').hexdigest(),
                      'terminal_ms': 10, 'expires_ms': 20})

    def tearDown(self):
        for manager in getattr(self, '_managers', ()):
            try:
                manager.current.close()
            except Exception:
                pass
        self.stack.close()

    def _append(self, event):
        return self.old.append(event, self.old.binding().witnessed)

    def _remove_registry(self):
        import winreg
        leaf = BASE_PATH + '\\' + self.storage_id
        try:
            winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, leaf, winreg.KEY_WOW64_64KEY, 0)
        except FileNotFoundError:
            pass

    def test_rotation_reopen_and_expired_lookup_keeps_old_bytes(self):
        manager = QueueJournalManager(self.old, self.custody,
                                      logical_stream_id='queue-' + self.storage_id,
                                      parent=self.root, retry_horizon_ms=60_000)
        self._managers = [manager]
        old_head = self.old.binding().witnessed
        row = {'job_id': 'active', 'state': 'UNKNOWN', 'fence_generation': 2,
               'logical_stream_id': manager.logical_stream_id}
        descriptor = manager.rotate([row], row_count=1, now_ms=1000,
                                    cursor={'last_project': None, 'sessions': []},
                                    stopped=False, logical_generation=2)
        self.assertEqual(manager.current.binding().witnessed.sequence, 4)
        self.assertEqual(self.custody.binding.witnessed, manager.current.binding().witnessed)
        previous = descriptor_from(manager.checkpoint.begin['previous'])
        with PrivateEventLog.reopen(previous['path'], binding_from(previous['binding'])) as old_readback:
            self.assertEqual(old_readback.binding().witnessed, old_head)
        found, terminal_ms = manager.lookup_archived('old-job')
        self.assertIsNotNone(found)
        self.assertEqual(found['state'], 'COMMITTED')
        self.assertEqual(terminal_ms, 10)
        reopened = QueueJournalManager(manager.current, self.custody,
                                       logical_stream_id=manager.logical_stream_id,
                                       parent=self.root)
        found, terminal_ms = reopened.lookup_archived('old-job')
        self.assertIsNotNone(found)
        self.assertEqual(terminal_ms, 10)
        self.assertEqual(descriptor.generation, 1)

    def test_two_rotations_follow_descriptor_chain_without_ram_catalog(self):
        manager = QueueJournalManager(self.old, self.custody,
                                      logical_stream_id='queue-' + self.storage_id,
                                      parent=self.root)
        self._managers = [manager]
        first = manager.rotate([{'job_id': 'one'}], row_count=1, now_ms=100,
                               cursor={}, stopped=False, logical_generation=1)
        second = manager.rotate([{'job_id': 'two'}], row_count=1, now_ms=200,
                                cursor={}, stopped=False, logical_generation=2)
        reopened = QueueJournalManager(manager.current, self.custody,
                                       logical_stream_id=manager.logical_stream_id,
                                       parent=self.root)
        self.assertEqual(first.generation, 1)
        self.assertEqual(second.generation, 2)
        self.assertIsNone(reopened.lookup_archived('missing'))
        self.assertEqual(reopened.checkpoint.generation, 2)

    def test_expired_terminal_is_archived_and_same_id_never_executes_again(self):
        owner_root = self.root / 'retention-owner'
        owner_root.mkdir()
        owner = QueueOwner.create(owner_root)
        command = hashlib.sha256(b'retention-command').hexdigest()
        receipt = hashlib.sha256(b'retention-receipt').hexdigest()
        request = JobRequest('expired', 'project', 'session', 100_000,
                             ('resource',), (), command)
        try:
            owner.broker.enqueue(request, now_ms=1)
            reservation = owner.broker.reserve_next(now_ms=2)
            self.assertIsNotNone(reservation)
            owner.broker.record_owner_result(
                reservation, OwnerResult('COMMITTED', command, receipt, completed_at_ms=3))
            owner.rotate_journal(now_ms=60_004, retry_horizon_ms=60_000)
            self.assertEqual(owner.broker.snapshot().receipts, ())
            archived, terminal_ms = owner.journal.lookup_archived('expired')
            self.assertEqual(archived['state'], 'COMMITTED')
            self.assertEqual(terminal_ms, 3)
            replay = owner.broker.enqueue(request, now_ms=60_005)
            self.assertEqual(replay.state, 'COMMITTED')
            changed = JobRequest('expired', 'project', 'session', 100_000,
                                 ('resource',), (), hashlib.sha256(b'changed').hexdigest())
            with self.assertRaises(BrokerError) as error:
                owner.broker.enqueue(changed, now_ms=60_006)
            self.assertEqual(str(error.exception), 'BROKER_ID_CONFLICT')
        finally:
            owner.close()

    @unittest.skipUnless(os.environ.get('GT07_REAL_CLOCK_SOAK') == '1',
                         'set GT07_REAL_CLOCK_SOAK=1 for the bounded real-clock evidence run')
    def test_real_clock_expiry_compacts_terminal_but_keeps_archive_tombstone(self):
        owner_root = self.root / 'real-clock-owner'
        owner_root.mkdir()
        owner = QueueOwner.create(owner_root)
        command = hashlib.sha256(b'real-clock-command').hexdigest()
        receipt = hashlib.sha256(b'real-clock-receipt').hexdigest()
        started = int(time.time_ns() // 1_000_000)
        request = JobRequest('real-clock-expired', 'project', 'session', started + 120_000,
                             ('resource',), (), command)
        try:
            owner.broker.enqueue(request, now_ms=started)
            reservation = owner.broker.reserve_next(now_ms=started + 1)
            owner.broker.record_owner_result(
                reservation, OwnerResult('COMMITTED', command, receipt,
                                         completed_at_ms=started + 2))
            # The manager's minimum test horizon is one minute.  Use host wall
            # clock, not a mocked timestamp, and wait beyond that boundary.
            time.sleep(60.25)
            now = int(time.time_ns() // 1_000_000)
            owner.rotate_journal(now_ms=now, retry_horizon_ms=60_000)
            self.assertEqual(owner.broker.snapshot().receipts, ())
            archived, terminal_ms = owner.journal.lookup_archived('real-clock-expired')
            self.assertEqual(archived['state'], 'COMMITTED')
            self.assertEqual(terminal_ms, started + 2)
        finally:
            owner.close()

    def test_queue_owner_rotates_checkpoint_and_reopens_without_losing_pending_job(self):
        owner_root = self.root / 'owner'
        owner_root.mkdir()
        owner = QueueOwner.create(owner_root)
        storage_id = owner.storage_id
        request = JobRequest('pending', 'project', 'session', 100_000,
                             ('resource',), (), hashlib.sha256(b'pending').hexdigest())
        owner.broker.enqueue(request, now_ms=1)
        try:
            descriptor = owner.rotate_journal(now_ms=2)
            self.assertEqual(descriptor.logical_stream_id, 'queue:' + storage_id)
            self.assertEqual(owner.broker.snapshot().pending[0].job_id, 'pending')
        finally:
            owner.close()
        reopened = QueueOwner.reopen(storage_id)
        try:
            self.assertEqual(reopened.broker.snapshot().pending[0].job_id, 'pending')
            reservation = reopened.broker.reserve_next(now_ms=3)
            self.assertIsNotNone(reservation)
            self.assertEqual(reservation.fence.stream_id, 'queue:' + storage_id)
        finally:
            reopened.close()


if __name__ == '__main__':
    unittest.main()

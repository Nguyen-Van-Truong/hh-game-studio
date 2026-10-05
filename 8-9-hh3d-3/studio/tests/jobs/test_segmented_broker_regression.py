"""Focused GT-07 M7 broker regressions.

These tests exercise the Windows custody path used by QueueOwner.  Clocks in
these cases are short synthetic epoch values; the real-clock measurement gate
belongs to the native scenario caller and is intentionally not used here.
"""
from contextlib import ExitStack
from dataclasses import asdict
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
import uuid
import sys

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))

from studio.host.core.custody import WitnessCustody
from studio.host.core.custody_registry import BASE_PATH, RegistryCustody
from studio.host.core.private_events import PrivateEventLog
from studio.host.core.private_store import PrivateBlobStore
from studio.host.core.safe_replace import ProtectedFileRoot
from studio.host.jobs.dispatch_policy import QueueLimits
from studio.host.jobs.durable_broker import (
    BrokerError,
    DurableBroker,
    JobRecord,
    JobRequest,
    OwnerResult,
)
from studio.host.jobs.queue_owner import QueueOwner, QueueOwnerError


_HORIZON = 60_000
_SCHEMA = "hh-durable-dispatch-1"


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


@unittest.skipUnless(os.name == "nt", "Windows custody fixture required")
class SegmentedBrokerRegressionTests(unittest.TestCase):
    """M7 queue invariants against the real Windows custody fixture."""

    def setUp(self):
        self.stack = ExitStack()
        self.root = Path(
            self.stack.enter_context(tempfile.TemporaryDirectory(prefix="m7-broker-"))
        ).resolve()
        RegistryCustody.provision_base()
        self._owners = []
        self._storage_ids = set()

    def tearDown(self):
        # QueueOwner owns the active writer handles.  Remove the registry leaf
        # only after those handles have been closed.
        for owner in reversed(self._owners):
            try:
                owner.close()
            except Exception:
                pass
        for storage_id in self._storage_ids:
            self._remove_registry_leaf(storage_id)
        self.stack.close()

    @staticmethod
    def _remove_registry_leaf(storage_id):
        import winreg

        leaf = BASE_PATH + "\\" + storage_id
        try:
            winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, leaf, winreg.KEY_WOW64_64KEY, 0)
        except FileNotFoundError:
            pass

    def _owner(self, *, retry_horizon_ms=_HORIZON):
        owner_root = self.root / ("owner-" + uuid.uuid4().hex)
        owner_root.mkdir()
        owner = QueueOwner.create(owner_root, retry_horizon_ms=retry_horizon_ms)
        self._owners.append(owner)
        self._storage_ids.add(owner.storage_id)
        return owner

    @staticmethod
    def _request(job_id, command, *, deadline_ms=1_000_000, now_ms=1,
                 project_id="project", session_id="session", resource="resource"):
        return JobRequest(
            job_id,
            project_id,
            session_id,
            deadline_ms,
            (resource,),
            (),
            _digest(command),
        )

    def _expire_and_rotate(self, owner, request, *, deadline_ms=10):
        owner.broker.enqueue(request, now_ms=1)
        self.assertIsNone(owner.broker.reserve_next(now_ms=deadline_ms))
        self.assertEqual(owner.broker.lookup(request.job_id).state, "REJECTED")
        owner.rotate_journal(now_ms=deadline_ms + _HORIZON + 1)

    def test_horizon_is_bound_at_create_and_rotation_cannot_override_it(self):
        owner = self._owner(retry_horizon_ms=_HORIZON)
        storage_id = owner.storage_id
        self.assertEqual(owner.broker.retry_horizon_ms, _HORIZON)

        owner.close()
        reopened = QueueOwner.reopen(storage_id, retry_horizon_ms=_HORIZON)
        self._owners.append(reopened)
        self.assertEqual(reopened.broker.retry_horizon_ms, _HORIZON)

        # Rotation uses the owner’s create-time profile.  A caller-supplied
        # different horizon must be rejected (or the removed keyword must fail)
        # before custody advances.
        with self.assertRaises((TypeError, QueueOwnerError, BrokerError)):
            reopened.rotate_journal(now_ms=1, retry_horizon_ms=_HORIZON + 1)
        before = reopened.custody.record["events"]["path"]
        reopened.rotate_journal(now_ms=1)
        self.assertNotEqual(reopened.custody.record["events"]["path"], before)

    def test_three_rotations_find_oldest_exact_receipt(self):
        owner = self._owner()
        command = _digest("oldest-command")
        receipt = _digest("oldest-receipt")
        request = JobRequest("oldest", "project", "oldest-session", 1_000_000,
                             ("oldest-resource",), (), command)
        owner.broker.enqueue(request, now_ms=1)
        reservation = owner.broker.reserve_next(now_ms=2)
        self.assertIsNotNone(reservation)
        owner.broker.record_owner_result(
            reservation, OwnerResult("COMMITTED", command, receipt, completed_at_ms=3)
        )

        # The first checkpoint expires the receipt.  Two later checkpoints
        # leave live rows behind so lookup must walk the full descriptor chain.
        owner.rotate_journal(now_ms=_HORIZON + 4)
        middle = self._request("middle", "middle-command", now_ms=_HORIZON + 5,
                               project_id="middle-project", session_id="middle-session",
                               resource="middle-resource")
        owner.broker.enqueue(middle, now_ms=_HORIZON + 5)
        owner.rotate_journal(now_ms=_HORIZON + 6)
        newest = self._request("newest", "newest-command", now_ms=_HORIZON + 7,
                               project_id="newest-project", session_id="newest-session",
                               resource="newest-resource")
        owner.broker.enqueue(newest, now_ms=_HORIZON + 7)
        owner.rotate_journal(now_ms=_HORIZON + 8)

        archived, terminal_ms = owner.journal.lookup_archived("oldest")
        self.assertEqual(archived["state"], "COMMITTED")
        self.assertEqual(archived["receipt_sha256"], receipt)
        self.assertEqual(terminal_ms, 3)
        record = owner.broker.lookup("oldest")
        self.assertIsInstance(record, JobRecord)
        self.assertEqual(record.state, "COMMITTED")
        self.assertEqual(record.receipt_sha256, receipt)

    def test_compaction_preserves_global_enqueue_sequence_when_latest_rows_expire(self):
        owner = self._owner()
        first = self._request("first", "first-command", now_ms=1,
                              project_id="p1", session_id="s1", resource="r1")
        first_record = owner.broker.enqueue(first, now_ms=1)
        first_reservation = owner.broker.reserve_next(now_ms=2)
        owner.broker.record_owner_result(
            first_reservation,
            OwnerResult("COMMITTED", first.command_sha256, _digest("first-receipt"),
                        completed_at_ms=60_000),
        )

        second = self._request("second", "second-command", now_ms=3,
                               project_id="p2", session_id="s2", resource="r2")
        owner.broker.enqueue(second, now_ms=3)
        second_reservation = owner.broker.reserve_next(now_ms=4)
        owner.broker.record_owner_result(
            second_reservation,
            OwnerResult("COMMITTED", second.command_sha256, _digest("second-receipt"),
                        completed_at_ms=2),
        )

        # Sequence 2 is compacted while sequence 1 remains inside the
        # retention horizon.  New admission must continue at sequence 3.
        owner.rotate_journal(now_ms=60_003)
        self.assertEqual([row.job.job_id for row in owner.broker.snapshot().receipts], ["first"])
        third = self._request("third", "third-command", now_ms=60_004,
                              project_id="p3", session_id="s3", resource="r3")
        third_record = owner.broker.enqueue(third, now_ms=60_004)
        self.assertEqual(first_record.job.sequence, 1)
        self.assertEqual(third_record.job.sequence, 3)

    def test_unknown_checkpoint_then_terminal_suffix_archives_newest_terminal(self):
        owner = self._owner()
        command = _digest("unknown-command")
        unknown_receipt = _digest("unknown-receipt")
        terminal_receipt = _digest("terminal-receipt")
        request = JobRequest("uncertain", "project", "uncertain-session", 1_000_000,
                             ("uncertain-resource",), (), command)
        owner.broker.enqueue(request, now_ms=1)
        reservation = owner.broker.reserve_next(now_ms=2)
        owner.broker.record_owner_result(
            reservation, OwnerResult("UNKNOWN", command, unknown_receipt, completed_at_ms=2)
        )
        owner.rotate_journal(now_ms=3)

        # The terminal result is a suffix on the segment whose checkpoint says
        # UNKNOWN.  Archive lookup must reconcile the suffix over that row.
        owner.broker.record_owner_result(
            reservation, OwnerResult("COMMITTED", command, terminal_receipt, completed_at_ms=4)
        )
        owner.rotate_journal(now_ms=_HORIZON + 5)
        archived, terminal_ms = owner.journal.lookup_archived("uncertain")
        self.assertEqual(archived["state"], "COMMITTED")
        self.assertEqual(archived["receipt_sha256"], terminal_receipt)
        self.assertEqual(terminal_ms, 4)
        record = owner.broker.lookup("uncertain")
        self.assertIsInstance(record, JobRecord)
        self.assertEqual(record.state, "COMMITTED")
        self.assertEqual(record.receipt_sha256, terminal_receipt)

    def test_stop_cancellation_gets_terminal_timestamp_and_archives(self):
        owner = self._owner()
        request = self._request("stopped", "stopped-command", project_id="p-stop",
                                session_id="s-stop", resource="r-stop")
        owner.broker.enqueue(request, now_ms=1)
        owner.broker.stop(now_ms=2)
        record = owner.broker.lookup("stopped")
        self.assertIsInstance(record, JobRecord)
        self.assertEqual(record.state, "CANCELED")

        owner.rotate_journal(now_ms=_HORIZON + 3)
        archived, terminal_ms = owner.journal.lookup_archived("stopped")
        self.assertEqual(archived["state"], "CANCELED")
        self.assertEqual(terminal_ms, 2)
        self.assertEqual(owner.broker.lookup("stopped").state, "CANCELED")

    def test_rejected_pending_gets_terminal_timestamp_and_archives(self):
        owner = self._owner()
        request = self._request("expired", "expired-command", deadline_ms=10,
                                project_id="p-expired", session_id="s-expired",
                                resource="r-expired")
        self._expire_and_rotate(owner, request, deadline_ms=10)
        archived, terminal_ms = owner.journal.lookup_archived("expired")
        self.assertEqual(archived["state"], "REJECTED")
        self.assertEqual(terminal_ms, 10)
        record = owner.broker.lookup("expired")
        self.assertIsInstance(record, JobRecord)
        self.assertEqual(record.state, "REJECTED")

    def test_expired_id_retry_is_rejected_but_changed_command_is_conflict(self):
        owner = self._owner()
        request = self._request("retry-expired", "retry-command", deadline_ms=10,
                                project_id="p-retry", session_id="s-retry",
                                resource="r-retry")
        self._expire_and_rotate(owner, request, deadline_ms=10)

        with self.assertRaises(BrokerError) as same_id:
            owner.broker.enqueue(request, now_ms=_HORIZON + 12)
        self.assertEqual(str(same_id.exception), "BROKER_RETRY_EXPIRED")

        changed = JobRequest(request.job_id, request.project_id, request.session_id,
                             request.deadline_ms, request.resources, request.dependencies,
                             _digest("retry-command-changed"))
        with self.assertRaises(BrokerError) as changed_id:
            owner.broker.enqueue(changed, now_ms=_HORIZON + 13)
        self.assertEqual(str(changed_id.exception), "BROKER_ID_CONFLICT")
        record = owner.broker.lookup(request.job_id)
        self.assertIsInstance(record, JobRecord)
        self.assertEqual(record.state, "REJECTED")

    def test_legacy_config_and_physical_fence_reopen_unchanged(self):
        """A pre-feature CONFIG remains readable without a synthetic rewrite."""
        storage_id = uuid.uuid4().hex
        registry = RegistryCustody.create(storage_id)
        self.stack.callback(self._remove_registry_leaf, storage_id)
        self.stack.callback(registry.close)
        file_parent = self.root / "legacy-files"
        file_parent.mkdir()
        files = self.stack.enter_context(ProtectedFileRoot.create(file_parent))
        blobs = self.stack.enter_context(PrivateBlobStore.create(self.root))
        events = self.stack.enter_context(PrivateEventLog.create(self.root))
        custody = WitnessCustody(registry, storage_id=storage_id,
                                 project_id="studio.scheduler", create=True)
        custody.activate(file_root=files.root, file_identity=files.root_identity,
                         blob_root=blobs.root, blob_identity=blobs.root_identity,
                         event_root=events.root, event_binding=events.binding())
        events.bind_custody(custody)
        limits = QueueLimits()
        events.append({"schema": _SCHEMA, "kind": "CONFIG", "limits": asdict(limits)},
                      events.binding().witnessed)
        physical_stream = f"{events.binding().stream.volume}:{events.binding().stream.file_id}"
        before = events._read_at(0, events.binding().witnessed.size)

        broker = DurableBroker(events, limits=limits)
        self.assertEqual(events._read_at(0, events.binding().witnessed.size), before)
        request = JobRequest("legacy", "legacy-project", "legacy-session", 1_000_000,
                             ("legacy-resource",), (), _digest("legacy-command"))
        broker.enqueue(request, now_ms=1)
        reservation = broker.reserve_next(now_ms=2)
        self.assertIsNotNone(reservation)
        self.assertEqual(reservation.fence.stream_id, physical_stream)
        broker.record_owner_result(
            reservation,
            OwnerResult("COMMITTED", request.command_sha256, _digest("legacy-receipt"),
                        completed_at_ms=3),
        )
        final_binding = events.binding()
        broker.close()
        events.close()

        reopened_log = PrivateEventLog.reopen(events.root, final_binding)
        self.stack.callback(reopened_log.close)
        reopened_log.bind_custody(custody)
        reopened = DurableBroker(reopened_log, limits=limits)
        try:
            record = reopened.lookup("legacy")
            self.assertIsInstance(record, JobRecord)
            self.assertEqual(record.state, "COMMITTED")
            self.assertEqual(record.fence.stream_id, physical_stream)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()

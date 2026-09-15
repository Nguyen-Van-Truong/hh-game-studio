"""Persistent archive and admission capacity regressions found in S26 review."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from host.core.journal import Journal, JournalError, JournalLimits
from host.core.limits import LimitsProfile


class JournalRetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gt02-retention-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "journal.jsonl"

    def append(self, journal, name="c", *, pending=False, receipt=None):
        return journal.append_command(project_id="p", command_id=name,
            digest="sha256:" + "a" * 64, now_ms=0, pending=pending,
            receipt={"result": "original"} if receipt is None else receipt)

    def test_archive_retains_original_receipt_across_repeated_compact_and_reopen(self):
        limits = JournalLimits(retry_horizon_ms=10)
        journal = Journal(self.path, limits=limits)
        self.append(journal)
        expected = journal.lookup_archive(project_id="p", command_id="c", now_ms=11)
        self.assertEqual(expected["receipt"], {"result": "original"})
        self.assertEqual(expected["status"], "COMMITTED")
        self.assertFalse(expected["execution_permitted"])
        for timestamp in (11, 20, 0):
            journal.compact(now_ms=timestamp)
            journal = Journal(self.path, limits=limits)
            before = self.path.read_bytes()
            self.assertEqual(journal.lookup_archive(project_id="p", command_id="c", now_ms=timestamp), expected)
            with self.assertRaisesRegex(JournalError, "RETRY_HORIZON_EXPIRED"):
                self.append(journal)
            self.assertEqual(self.path.read_bytes(), before)

    def test_archive_does_not_upgrade_expired_pending_to_committed(self):
        journal = Journal(self.path, limits=JournalLimits(retry_horizon_ms=10))
        self.append(journal, pending=True, receipt={"state": "intent"})
        journal.compact(now_ms=11)
        result = Journal(self.path).lookup_archive(project_id="p", command_id="c", now_ms=11)
        self.assertEqual(result["status"], "ACCEPTED_PENDING")
        self.assertEqual(result["receipt"], {"state": "intent"})
        self.assertFalse(result["execution_permitted"])

    def test_archive_has_explicit_missing_and_not_yet_expired_results(self):
        journal = Journal(self.path, limits=JournalLimits(retry_horizon_ms=10))
        with self.assertRaisesRegex(JournalError, "COMMAND_NOT_FOUND"):
            journal.lookup_archive(project_id="p", command_id="c", now_ms=11)
        self.append(journal)
        with self.assertRaisesRegex(JournalError, "ARCHIVE_NOT_EXPIRED"):
            journal.lookup_archive(project_id="p", command_id="c", now_ms=10)

    def test_legacy_discarded_receipt_is_explicitly_unavailable(self):
        journal = Journal(self.path)
        record = {"kind": "command", "project_id": "p", "command_id": "c",
                  "digest": "sha256:" + "a" * 64, "status": "EXPIRED_TOMBSTONE",
                  "receipt": {}, "created_ms": 0, "expires_ms": 10}
        self.path.write_bytes(journal._encoded_record(record))
        with self.assertRaisesRegex(JournalError, "ARCHIVE_RESULT_UNAVAILABLE"):
            Journal(self.path).lookup_archive(project_id="p", command_id="c", now_ms=11)

    def test_pending_admission_reserves_terminal_record_before_any_write(self):
        journal = Journal(self.path, limits=JournalLimits(max_records=2))
        journal.acquire_lease(project_id="p", target="t", owner="o", now_ms=0, ttl_ms=100)
        before = self.path.read_bytes()
        with self.assertRaisesRegex(JournalError, "JOURNAL_RECORD_LIMIT"):
            self.append(journal, pending=True)
        self.assertEqual(self.path.read_bytes(), before)

    def test_other_writers_cannot_spend_reserved_record(self):
        limits = JournalLimits(max_records=2)
        journal = Journal(self.path, limits=limits)
        self.append(journal, pending=True)
        reopened = Journal(self.path, limits=limits)
        with self.assertRaisesRegex(JournalError, "JOURNAL_RECORD_LIMIT"):
            self.append(reopened, "unrelated")
        result = reopened.finish_command(project_id="p", command_id="c", status="COMMITTED",
                                         receipt={"result": "finished"}, now_ms=1)
        self.assertEqual(result["status"], "COMMITTED")

    def test_byte_reservation_survives_compaction_and_reopen(self):
        profile = LimitsProfile(max_envelope_bytes=2048)
        journal = Journal(self.path, profile=profile, limits=JournalLimits(max_bytes=3000))
        self.append(journal, pending=True)
        journal.compact(now_ms=1)
        reopened = Journal(self.path, profile=profile, limits=journal.limits)
        before = self.path.read_bytes()
        with self.assertRaisesRegex(JournalError, "JOURNAL_FULL"):
            self.append(reopened, "unrelated", receipt={"large": "x" * 700})
        self.assertEqual(self.path.read_bytes(), before)
        finished = reopened.finish_command(project_id="p", command_id="c", status="COMMITTED",
                                          receipt={"large": "x" * 1000}, now_ms=2)
        self.assertEqual(finished["status"], "COMMITTED")

    def test_terminal_fsync_failure_blocks_reopen_until_a_later_barrier(self):
        """A readable terminal line is not an ACK until durability is reproved."""
        import host.core.journal as journal_module

        journal = Journal(self.path)
        self.append(journal, pending=True)
        pending_size = self.path.stat().st_size
        real_fsync = journal_module.os.fsync

        def fail_only_after_terminal_bytes(fd):
            if self.path.stat().st_size > pending_size:
                raise OSError("injected terminal fsync failure")
            return real_fsync(fd)

        with mock.patch.object(journal_module.os, "fsync", side_effect=fail_only_after_terminal_bytes):
            with self.assertRaisesRegex(JournalError, "JOURNAL_WRITE_FAILED"):
                journal.finish_command(project_id="p", command_id="c", status="COMMITTED",
                                       receipt={"result": "readback"}, now_ms=1)
            with self.assertRaisesRegex(JournalError, "JOURNAL_DURABILITY_UNCONFIRMED"):
                Journal(self.path)

        recovered = Journal(self.path)
        result = recovered.lookup(project_id="p", command_id="c", now_ms=2)
        self.assertEqual(result["status"], "COMMITTED")
        self.assertEqual(result["receipt"], {"result": "readback"})


if __name__ == "__main__":
    unittest.main()

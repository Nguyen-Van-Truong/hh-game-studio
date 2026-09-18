from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from host.core.journal import Journal, JournalError, JournalLimits  # noqa: E402


class JournalTests(unittest.TestCase):
    def make(self, **kwargs):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        return Path(temp.name) / "journal.log", kwargs

    def test_response_loss_retry_returns_original_receipt_after_reopen(self):
        path, _ = self.make()
        j = Journal(path)
        first = j.append_command(project_id="p", command_id="c", digest="sha256:" + "a" * 64,
                                  receipt={"revision": "r1"}, now_ms=100, pending=False)
        self.assertFalse(first["replayed"])
        reopened = Journal(path)
        retry = reopened.append_command(project_id="p", command_id="c", digest="sha256:" + "a" * 64,
                                        receipt={"revision": "ignored"}, now_ms=200)
        self.assertTrue(retry["replayed"])
        self.assertEqual(retry["receipt"], {"revision": "r1"})

    def test_same_id_different_payload_rejects(self):
        path, _ = self.make()
        j = Journal(path)
        j.append_command(project_id="p", command_id="c", digest="sha256:" + "a" * 64, receipt={}, now_ms=0)
        with self.assertRaisesRegex(JournalError, "COMMAND_ID_PAYLOAD_CONFLICT"):
            j.append_command(project_id="p", command_id="c", digest="sha256:" + "b" * 64, receipt={}, now_ms=1)

    def test_pending_limit_and_terminal_transition(self):
        path, _ = self.make()
        j = Journal(path, limits=JournalLimits(max_pending_commands=1))
        j.append_command(project_id="p", command_id="c", digest="sha256:" + "a" * 64, receipt={"state": "started"}, now_ms=0, pending=True)
        with self.assertRaisesRegex(JournalError, "PENDING_LIMIT"):
            j.append_command(project_id="p", command_id="c2", digest="sha256:" + "b" * 64, receipt={}, now_ms=1, pending=True)
        done = j.finish_command(project_id="p", command_id="c", status="COMMITTED", receipt={"state": "done"}, now_ms=2)
        self.assertEqual(done["status"], "COMMITTED")
        self.assertEqual(j.lookup(project_id="p", command_id="c", now_ms=3)["receipt"], {"state": "done"})

    def test_retry_horizon_expiry_does_not_reexecute(self):
        path, _ = self.make()
        j = Journal(path, limits=JournalLimits(retry_horizon_ms=10))
        j.append_command(project_id="p", command_id="c", digest="sha256:" + "a" * 64, receipt={"ok": 1}, now_ms=0)
        with self.assertRaisesRegex(JournalError, "RETRY_HORIZON_EXPIRED"):
            j.lookup(project_id="p", command_id="c", now_ms=11)
        with self.assertRaisesRegex(JournalError, "RETRY_HORIZON_EXPIRED"):
            j.append_command(project_id="p", command_id="c", digest="sha256:" + "a" * 64, receipt={}, now_ms=11)

    def test_digest_and_terminal_status_are_strict(self):
        path, _ = self.make()
        j = Journal(path)
        with self.assertRaisesRegex(JournalError, "INVALID_DIGEST"):
            j.append_command(project_id="p", command_id="c", digest="a" * 64, receipt={}, now_ms=0)
        j.append_command(project_id="p", command_id="c", digest="sha256:" + "a" * 64, receipt={}, now_ms=0, pending=True)
        with self.assertRaisesRegex(JournalError, "INVALID_STATUS"):
            j.finish_command(project_id="p", command_id="c", status="DONE", receipt={}, now_ms=1)

    def test_compaction_keeps_expired_id_tombstone(self):
        path, _ = self.make()
        j = Journal(path, limits=JournalLimits(retry_horizon_ms=10))
        j.append_command(project_id="p", command_id="c", digest="sha256:" + "a" * 64, receipt={"ok": 1}, now_ms=0)
        j.compact(now_ms=11)
        reopened = Journal(path, limits=JournalLimits(retry_horizon_ms=10))
        with self.assertRaisesRegex(JournalError, "RETRY_HORIZON_EXPIRED"):
            reopened.append_command(project_id="p", command_id="c", digest="sha256:" + "a" * 64, receipt={}, now_ms=11)

    def test_full_journal_and_truncated_or_tampered_record_fail_closed(self):
        path, _ = self.make()
        j = Journal(path, limits=JournalLimits(max_bytes=180))
        with self.assertRaisesRegex(JournalError, "JOURNAL_FULL"):
            j.append_command(project_id="p", command_id="c", digest="sha256:" + "a" * 64, receipt={"x": "y" * 100}, now_ms=0)
        path.write_bytes(b'{"record":{"kind":"command"}')
        with self.assertRaisesRegex(JournalError, "JOURNAL_TRUNCATED"):
            Journal(path)
        path.write_bytes(b'{"record":{"kind":"command","project_id":"p","command_id":"c"},"checksum":"' + b"0" * 64 + b'"}\n')
        with self.assertRaisesRegex(JournalError, "JOURNAL_CHECKSUM_MISMATCH"):
            Journal(path)

    def test_lease_fencing_expiry_and_revision(self):
        path, _ = self.make()
        j = Journal(path)
        first = j.acquire_lease(project_id="p", target="scene", owner="a", now_ms=0, ttl_ms=100)
        with self.assertRaisesRegex(JournalError, "LEASE_BUSY"):
            j.acquire_lease(project_id="p", target="scene", owner="b", now_ms=1, ttl_ms=100)
        j.check_lease(first, now_ms=50)
        second = j.acquire_lease(project_id="p", target="scene", owner="b", now_ms=101, ttl_ms=100)
        self.assertEqual(second.fencing_epoch, first.fencing_epoch + 1)
        with self.assertRaisesRegex(JournalError, "STALE_LEASE"):
            j.check_lease(first, now_ms=50)
        with self.assertRaisesRegex(JournalError, "REVISION_MISMATCH"):
            j.check_revision(expected_revision="r1", current_revision="r2")


if __name__ == "__main__":
    unittest.main()

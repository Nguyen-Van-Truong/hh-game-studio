"""OS liveness probes must observe processes without sending signals."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import time
import tracemalloc
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from host.core.journal import Journal, JournalError, JournalLimits
from host.core.limits import LimitsProfile


class JournalPlatformTests(unittest.TestCase):
    def test_liveness_probe_returns_without_terminating_caller(self):
        # Isolate the legacy bug: on Windows os.kill(pid, 0) terminates this
        # disposable child with exit 0, so a host exit alone is insufficient.
        code = (
            "import os,sys; sys.path.insert(0,sys.argv[1]); "
            "from host.core.journal import Journal; "
            "assert Journal._pid_alive(os.getpid()); "
            "print('LIVENESS_RETURNED',flush=True)"
        )
        result = subprocess.run([sys.executable, "-c", code, str(ROOT)],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "LIVENESS_RETURNED")

    def test_aged_live_lock_is_never_stolen(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "journal"
            lock = Path(str(path) + ".lock")
            raw = json.dumps({"pid": str(os.getpid()), "created_ns": "1"}).encode()
            lock.write_bytes(raw)
            os.utime(lock, (time.time() - 120, time.time() - 120))
            with self.assertRaisesRegex(JournalError, "JOURNAL_LOCKED"):
                Journal(path, limits=JournalLimits(lock_timeout_ms=30, lock_stale_ms=1))
            self.assertEqual(lock.read_bytes(), raw)
            self.assertFalse(path.exists())

    def test_existing_reader_observes_later_receipt_and_fence(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "journal"
            reader, writer = Journal(path), Journal(path)
            writer.append_command(project_id="p", command_id="c", digest="sha256:" + "a" * 64,
                                  receipt={"ok": True}, now_ms=0)
            self.assertEqual(reader.lookup(project_id="p", command_id="c", now_ms=1)["receipt"], {"ok": True})
            old = reader.acquire_lease(project_id="p", target="t", owner="a", now_ms=0, ttl_ms=1)
            writer.acquire_lease(project_id="p", target="t", owner="b", now_ms=2, ttl_ms=10)
            with self.assertRaisesRegex(JournalError, "STALE_LEASE"):
                reader.check_lease(old, now_ms=0)

    def test_compaction_never_resets_fencing_epoch(self):
        with tempfile.TemporaryDirectory() as td:
            journal = Journal(Path(td) / "journal")
            old = journal.acquire_lease(project_id="p", target="t", owner="a", now_ms=0, ttl_ms=1)
            journal.compact(now_ms=2)
            new = Journal(journal.path).acquire_lease(project_id="p", target="t", owner="b", now_ms=3, ttl_ms=1)
            self.assertGreater(new.fencing_epoch, old.fencing_epoch)

    def test_invalid_timestamps_never_poison_durable_journal(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "journal"
            journal = Journal(path)
            for bad in (True, -1, 0.5, 1 << 60):
                with self.subTest(value=bad):
                    with self.assertRaisesRegex(JournalError, "INVALID_CLOCK"):
                        journal.append_command(project_id="p", command_id="c", digest="sha256:" + "a" * 64,
                                               receipt={}, now_ms=bad)
                    with self.assertRaisesRegex(JournalError, "INVALID_CLOCK"):
                        journal.acquire_lease(project_id="p", target="t", owner="a", now_ms=bad, ttl_ms=1)
                    self.assertFalse(path.exists())
                    self.assertEqual(len(Journal(path)._records), 0)

    def test_reordered_terminal_history_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "journal"
            journal = Journal(path)
            journal.append_command(project_id="p", command_id="c", digest="sha256:" + "a" * 64,
                                   receipt={}, now_ms=0, pending=True)
            journal.finish_command(project_id="p", command_id="c", status="COMMITTED", receipt={"done": True}, now_ms=1)
            path.write_bytes(b"".join(reversed(path.read_bytes().splitlines(keepends=True))))
            with self.assertRaisesRegex(JournalError, "JOURNAL_HISTORY_INVALID"):
                Journal(path)

    def test_custom_load_limits_apply_before_durable_write(self):
        with tempfile.TemporaryDirectory() as td:
            for index, profile in enumerate((LimitsProfile(max_envelope_bytes=256),
                                             LimitsProfile(max_string_chars=10),
                                             LimitsProfile(max_depth=2))):
                path = Path(td) / f"journal-{index}"
                with self.subTest(profile=profile):
                    with self.assertRaisesRegex(JournalError, "JOURNAL_RECORD_INVALID"):
                        Journal(path, profile=profile).append_command(
                            project_id="p", command_id="c", digest="sha256:" + "a" * 64,
                            receipt={"nested": {"value": "abc"}}, now_ms=0)
                    self.assertFalse(path.exists())
                    self.assertEqual(len(Journal(path, profile=profile)._records), 0)

    def test_hardlink_alias_cannot_split_journal_lock_domain(self):
        with tempfile.TemporaryDirectory() as td:
            first, alias = Path(td) / "first", Path(td) / "alias"
            first.write_bytes(b"")
            os.link(first, alias)
            for path in (first, alias):
                with self.assertRaisesRegex(JournalError, "JOURNAL_PATH_UNSAFE"):
                    Journal(path)
            self.assertEqual(first.read_bytes(), b"")

    def test_clock_rollback_cannot_revive_expired_tombstone(self):
        with tempfile.TemporaryDirectory() as td:
            journal = Journal(Path(td) / "journal", limits=JournalLimits(retry_horizon_ms=10))
            journal.append_command(project_id="p", command_id="c", digest="sha256:" + "a" * 64,
                                   receipt={"done": True}, now_ms=100)
            journal.compact(now_ms=111)
            with self.assertRaisesRegex(JournalError, "RETRY_HORIZON_EXPIRED"):
                journal.lookup(project_id="p", command_id="c", now_ms=105)
            with self.assertRaisesRegex(JournalError, "RETRY_HORIZON_EXPIRED"):
                journal.append_command(project_id="p", command_id="c", digest="sha256:" + "a" * 64,
                                       receipt={}, now_ms=105)

    def test_reopen_and_compaction_stream_receipts_with_bounded_memory(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "journal"
            journal = Journal(path)
            # Materialize a valid large fixture without O(n^2) admission work.
            with path.open("wb") as stream:
                for index in range(128):
                    record = {"kind": "command", "project_id": "p", "command_id": f"c{index}",
                              "digest": "sha256:" + "a" * 64, "status": "COMMITTED",
                              "receipt": {"blob": "x" * 8192}, "created_ms": 0, "expires_ms": 86400000}
                    envelope = {"record": record, "checksum": journal._checksum(record)}
                    stream.write((json.dumps(envelope, separators=(",", ":")) + "\n").encode())
            tracemalloc.start()
            try:
                reopened = Journal(path)
                reopened.compact(now_ms=1)
                self.assertEqual(len(reopened.lookup(project_id="p", command_id="c127", now_ms=1)["receipt"]["blob"]), 8192)
                reopened.compact(now_ms=86400001)
                archived = reopened.lookup_archive(project_id="p", command_id="c127", now_ms=86400001)
                self.assertEqual(len(archived["receipt"]["blob"]), 8192)
                self.assertFalse(archived["execution_permitted"])
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
            self.assertLess(peak, path.stat().st_size // 2, "receipt corpus was retained in memory")

    def test_kernel_lock_released_after_owned_writer_crash(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "journal"
            ready = Path(td) / "ready"
            code = "\n".join([
                "import sys,time", "from pathlib import Path", "sys.path.insert(0,sys.argv[1])",
                "from host.core.journal import Journal", "j=Journal(sys.argv[2])",
                "with j._writer_lock():", "    Path(sys.argv[3]).write_text('LOCK_HELD')", "    time.sleep(20)",
            ])
            child = subprocess.Popen([sys.executable, "-c", code, str(ROOT), str(path), str(ready)],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                deadline = time.monotonic() + 3
                while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(ready.exists(), "worker never acquired its lock")
                with self.assertRaisesRegex(JournalError, "JOURNAL_LOCKED"):
                    Journal(path, limits=JournalLimits(lock_timeout_ms=30))
            finally:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=3)
            journal = Journal(path)
            journal.append_command(project_id="p", command_id="c", digest="sha256:" + "a" * 64,
                                   receipt={"recovered": True}, now_ms=0)
            self.assertEqual(journal.lookup(project_id="p", command_id="c", now_ms=0)["status"], "COMMITTED")


if __name__ == "__main__":
    unittest.main()

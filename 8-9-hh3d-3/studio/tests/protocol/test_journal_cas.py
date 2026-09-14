"""GT-02 journal single-writer/CAS regression tests.

These tests intentionally exercise the real file lock through independent
Python processes.  They are local durability evidence, not a distributed
database claim.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from host.core.journal import Journal, JournalError, JournalLimits  # noqa: E402


class JournalCasTests(unittest.TestCase):
    def test_dead_lock_is_recovered_and_lock_is_removed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "journal.log"
            lock = Path(str(path) + ".lock")
            lock.write_text(json.dumps({"pid": "99999999", "created_ns": "1"}), encoding="utf-8")
            old = time.time() - 120
            os.utime(lock, (old, old))
            Journal(path, limits=JournalLimits(lock_timeout_ms=250, lock_stale_ms=10)).append_command(
                project_id="p", command_id="c", digest="sha256:" + "a" * 64, receipt={"ok": 1}, now_ms=0
            )
            self.assertFalse(lock.exists())
            self.assertEqual(Journal(path).lookup(project_id="p", command_id="c", now_ms=1)["receipt"], {"ok": 1})

    def test_live_lock_fails_closed_and_invalid_call_releases_lock(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "journal.log"
            lock = Path(str(path) + ".lock")
            lock.write_text(json.dumps({"pid": str(os.getpid()), "created_ns": str(time.time_ns())}), encoding="utf-8")
            with self.assertRaisesRegex(JournalError, "JOURNAL_LOCKED"):
                Journal(path, limits=JournalLimits(lock_timeout_ms=30)).append_command(
                    project_id="p", command_id="c", digest="invalid", receipt={}, now_ms=0
                )
            lock.unlink()
            journal = Journal(path, limits=JournalLimits(lock_timeout_ms=100))
            with self.assertRaisesRegex(JournalError, "INVALID_DIGEST"):
                journal.append_command(project_id="p", command_id="c", digest="invalid", receipt={}, now_ms=0)
            self.assertFalse(lock.exists())

    def test_independent_processes_do_not_lose_or_duplicate_appends(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "journal.log"
            code = (
                "import sys; sys.path.insert(0, sys.argv[2]); "
                "from host.core.journal import Journal; "
                "j=Journal(sys.argv[1]); "
                "j.append_command(project_id='p', command_id=sys.argv[3], "
                "digest='sha256:'+sys.argv[3].ljust(64,'x')[:64], receipt={'id':sys.argv[3]}, now_ms=0)"
            )
            procs = [subprocess.Popen([sys.executable, "-c", code, str(path), str(ROOT), f"c{i}"])
                     for i in range(8)]
            exits = [proc.wait(timeout=10) for proc in procs]
            self.assertEqual(exits, [0] * 8)
            reopened = Journal(path)
            self.assertEqual(len(reopened._records), 8)
            self.assertEqual({record["command_id"] for record in reopened._records}, {f"c{i}" for i in range(8)})
            self.assertFalse(Path(str(path) + ".lock").exists())

    def test_compaction_reopen_has_tombstone_and_no_temp_lock_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "journal.log"
            limits = JournalLimits(retry_horizon_ms=10)
            journal = Journal(path, limits=limits)
            journal.append_command(project_id="p", command_id="expired", digest="sha256:" + "a" * 64,
                                   receipt={"ok": 1}, now_ms=0)
            journal.compact(now_ms=11)
            reopened = Journal(path, limits=limits)
            with self.assertRaisesRegex(JournalError, "RETRY_HORIZON_EXPIRED"):
                reopened.append_command(project_id="p", command_id="expired", digest="sha256:" + "a" * 64,
                                         receipt={}, now_ms=11)
            self.assertEqual(list(Path(td).glob(".*.lock")), [])
            self.assertEqual(list(Path(td).glob(".journal.log.*")), [])


if __name__ == "__main__":
    unittest.main()

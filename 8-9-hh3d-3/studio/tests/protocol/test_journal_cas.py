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
    _CAS_WORKER_COUNT = 8
    # This is a total test budget, rather than one wait budget per worker.  A
    # wedged worker must therefore never hold the test process indefinitely.
    _CAS_DEADLINE_S = 10.0

    @staticmethod
    def _cleanup_workers(procs: list[subprocess.Popen[str]]) -> None:
        """These fixed workers spawn no descendants; terminate owned handles.

        Windows Popen retains a handle, avoiding taskkill's numeric PID reuse
        race. Cleanup has one separate three-second budget for all children.
        """
        for proc in procs:
            if proc.poll() is None:
                proc.kill()
        deadline = time.monotonic() + 3.0
        try:
            for proc in procs:
                proc.wait(timeout=max(0.001, deadline - time.monotonic()))
        finally:
            for proc in procs:
                for stream in (proc.stdin, proc.stdout, proc.stderr):
                    if stream is not None:
                        stream.close()
        if any(proc.poll() is None for proc in procs):
            raise AssertionError("CAS cleanup failed: owned worker still running")

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
        self._run_concurrent_workers([f"c{i}" for i in range(self._CAS_WORKER_COUNT)])

    def test_same_command_concurrent_retries_have_one_durable_result(self):
        self._run_concurrent_workers(["same-command"] * self._CAS_WORKER_COUNT)

    def _run_concurrent_workers(self, command_ids):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "journal.log"
            code = (
                "import sys,json; sys.path.insert(0, sys.argv[2]); "
                "from host.core.journal import Journal; "
                "assert sys.stdin.readline() == 'GO\\n'; "
                "j=Journal(sys.argv[1]); "
                "result=j.append_command(project_id='p', command_id=sys.argv[3], "
                "digest='sha256:'+('abcdef0123456789'*4)[:64], receipt={'id':sys.argv[3]}, now_ms=0); "
                "assert j.lookup(project_id='p',command_id=sys.argv[3],now_ms=1)['receipt']=={'id':sys.argv[3]}; "
                "print(json.dumps({'completed':sys.argv[3],'replayed':result['replayed']}),flush=True)"
            )
            procs: list[subprocess.Popen[str]] = []
            exits: list[int | None] = [None] * self._CAS_WORKER_COUNT
            started = time.monotonic()
            try:
                for i in range(self._CAS_WORKER_COUNT):
                    try:
                        procs.append(subprocess.Popen(
                            [sys.executable, "-c", code, str(path), str(ROOT), command_ids[i]],
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                        ))
                    except OSError as exc:
                        self.skipTest(f"SKIP_ENVIRONMENT: unable to spawn CAS worker, errno={exc.errno}")

                for proc in procs:
                    proc.stdin.write("GO\n")
                    proc.stdin.flush()
                    proc.stdin.close()
                    proc.stdin = None

                pending = set(range(len(procs)))
                deadline = started + self._CAS_DEADLINE_S
                while pending and time.monotonic() < deadline:
                    for index in tuple(pending):
                        result = procs[index].poll()
                        if result is not None:
                            exits[index] = result
                            pending.remove(index)
                    if pending:
                        time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))

                if pending:
                    self.fail(
                        "CAS workers exceeded total deadline of %.1fs: pending=%s"
                        % (self._CAS_DEADLINE_S, sorted(pending))
                    )

                failures = []
                completed = []
                for index, proc in enumerate(procs):
                    stdout, stderr = proc.communicate(timeout=1)
                    if exits[index] != 0 or stderr:
                        failures.append(f"worker {index} exit={exits[index]} stderr={stderr!r} stdout={stdout!r}")
                    else:
                        self.assertTrue(stdout.strip(), f"worker {index}: exit 0 without completion proof")
                        marker = json.loads(stdout)
                        self.assertEqual(marker["completed"], command_ids[index])
                        completed.append(marker)
                if failures:
                    self.fail("CAS worker failure: " + "; ".join(failures))
                self.assertEqual(sum(not item["replayed"] for item in completed), len(set(command_ids)))
            finally:
                # Also handles assertion/skip paths after some workers started.
                self._cleanup_workers(procs)
            reopened = Journal(path)
            self.assertEqual(len(reopened._records), len(set(command_ids)))
            self.assertEqual({record["command_id"] for record in reopened._records}, set(command_ids))
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

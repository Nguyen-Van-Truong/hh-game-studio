#!/usr/bin/env python3
"""Static and process-supervision tests for :mod:`tools.run_guarded`.

The Windows process-tree test is intentionally opt-in to the normal test run:
it starts a real descendant and should only be used on an idle workstation.
No test creates, removes, or alters the machine-wide measurement lock.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from tools import run_guarded


class GuardUnitTests(unittest.TestCase):
    def test_lock_path_is_read_only_and_measure_lock_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "local"
            lock = local / "HHGodotAgent" / "measure-window.lock"
            lock.parent.mkdir(parents=True)
            lock.write_text("measurement-owned\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(local)}, clear=False), mock.patch.object(
                run_guarded, "scheduled_hhstudio_running", return_value=(False, None)
            ):
                blocked, reason, unknown = run_guarded.measurement_guard_status()
            self.assertTrue(blocked)
            self.assertIn("measure-lock", reason or "")
            self.assertFalse(unknown)
            self.assertTrue(lock.exists(), "guard must never remove the machine lock")

    def test_non_gt06_hhstudio_task_is_recognized(self) -> None:
        completed = subprocess.CompletedProcess(
            ["powershell.exe"], 0, stdout="HHStudio.SA02.Measure\r\n", stderr=""
        )
        with mock.patch.object(run_guarded.os, "name", "nt"), mock.patch.object(
            run_guarded.subprocess, "run", return_value=completed
        ) as run:
            running, detail = run_guarded.scheduled_hhstudio_running(timeout=0.01)
        self.assertTrue(running)
        self.assertEqual(detail, "HHStudio.SA02.Measure")
        self.assertIn("HHStudio.*", run.call_args.args[0][-1])

    def test_scheduler_query_failure_is_fail_closed(self) -> None:
        with mock.patch.object(run_guarded.os, "name", "nt"), mock.patch.object(
            run_guarded.subprocess, "run", side_effect=subprocess.TimeoutExpired("powershell", 1.5)
        ):
            running, detail = run_guarded.scheduled_hhstudio_running(timeout=0.01)
        self.assertFalse(running)
        self.assertTrue((detail or "").startswith("scheduled-task-query-unavailable"))

    def test_scheduler_query_unavailable_blocks_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "local"
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(local)}, clear=False), mock.patch.object(
                run_guarded, "scheduled_hhstudio_running",
                return_value=(False, "scheduled-task-query-unavailable:TimeoutExpired"),
            ):
                blocked, reason, unknown = run_guarded.measurement_guard_status()
        self.assertTrue(blocked)
        self.assertEqual(reason, "scheduled-task-query-unavailable:TimeoutExpired")
        self.assertTrue(unknown)

    def test_redaction_covers_command_and_stream_lines(self) -> None:
        self.assertEqual(
            run_guarded.redact_command(["python", "-m", "demo", "--token", "secret-value", "--mode", "arena"]),
            ["python", "-m", "demo", "--token", "[REDACTED]", "--mode", "arena"],
        )
        self.assertEqual(run_guarded._redact_text("Authorization: Bearer abc\nready\n"), "[REDACTED_SENSITIVE_LINE]\nready\n")

    def test_source_hash_rejects_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"; root.mkdir()
            outside = Path(tmp) / "outside.txt"; outside.write_text("outside", encoding="utf-8")
            link = root / "link.txt"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable")
            with self.assertRaises(ValueError):
                run_guarded._hash_sources([link], root, [sys.executable, "-c", "pass"])

    def test_source_hash_ignores_generated_caches_and_requires_existing_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"; root.mkdir()
            (root / "source.py").write_text("value = 1\n", encoding="utf-8")
            (root / "cache.pyc").write_bytes(b"first")
            (root / "asset.png.import").write_text("first", encoding="utf-8")
            (root / "__pycache__").mkdir(); (root / "__pycache__" / "source.cpython.pyc").write_bytes(b"first")
            (root / ".local").mkdir(); (root / ".local" / "generated.txt").write_text("first", encoding="utf-8")
            first = run_guarded._hash_sources([], root)
            (root / "cache.pyc").write_bytes(b"second")
            (root / "asset.png.import").write_text("second", encoding="utf-8")
            (root / "__pycache__" / "source.cpython.pyc").write_bytes(b"second")
            (root / ".local" / "generated.txt").write_text("second", encoding="utf-8")
            self.assertEqual(first, run_guarded._hash_sources([], root))
            with self.assertRaises(ValueError):
                run_guarded._hash_sources([root / "missing.py"], root)

    def test_shell_and_external_executables_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                run_guarded._safe_command(["cmd.exe", "/c", "echo", "unsafe"], root)
            with self.assertRaises(ValueError):
                run_guarded._safe_command(["definitely-not-a-project-executable"], root)

    def test_prelaunch_guard_writes_unique_manifest_without_starting_child(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"; project.mkdir()
            (project / "fixture.txt").write_text("fixture\n", encoding="utf-8")
            local = Path(tmp) / "local"; guard = local / "HHGodotAgent" / "measure-window.lock"
            guard.parent.mkdir(parents=True); guard.write_text("held\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(local)}, clear=False), mock.patch.object(
                run_guarded, "scheduled_hhstudio_running", return_value=(False, None)
            ):
                code, result = run_guarded.run(["--timeout", "1", "--project-root", str(project), "--", sys.executable, "-c", "raise SystemExit(7)"])
            self.assertEqual(code, run_guarded.EXIT_GUARD)
            self.assertEqual(result["status"], "MEASURE_GUARD_BLOCKED")
            run_dir = project / ".local" / "runs" / result["run_id"]
            self.assertTrue((run_dir / "manifest.json").exists())
            self.assertTrue(guard.exists())

    def test_directory_evidence_is_rejected_before_lease_or_child(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "fixture.txt").write_text("fixture\n", encoding="utf-8")
            evidence = project / ".local" / "runs"; evidence.mkdir(parents=True)
            with mock.patch.object(run_guarded.ProjectLock, "acquire") as acquire, mock.patch.object(
                run_guarded.subprocess, "Popen"
            ) as popen, mock.patch.object(run_guarded, "_write_json") as write_json:
                with self.assertRaisesRegex(ValueError, "--evidence must name a file"):
                    run_guarded.run([
                        "--timeout", "1", "--project-root", str(project), "--evidence", str(evidence),
                        "--", sys.executable, "-c", "pass"
                    ])
            acquire.assert_not_called()
            popen.assert_not_called()
            write_json.assert_not_called()
            self.assertEqual(list(evidence.iterdir()), [])
            self.assertFalse((project / ".local" / "run_guarded.lock").exists())

    def test_final_evidence_write_failure_releases_owned_project_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "fixture.txt").write_text("fixture\n", encoding="utf-8")
            evidence = project / ".local" / "summary.json"
            write_json = run_guarded._write_json

            def fail_optional_evidence(path: Path, result: dict) -> None:
                if path == evidence:
                    raise OSError("optional evidence write failed")
                write_json(path, result)

            # An early guard return still enters finalization, without starting
            # an engine or changing the real machine measurement lock.
            with mock.patch.object(run_guarded, "measurement_guard_status", return_value=(True, "test-guard", False)), mock.patch.object(
                run_guarded, "_write_json", side_effect=fail_optional_evidence
            ), mock.patch.object(run_guarded.subprocess, "Popen") as popen:
                with self.assertRaisesRegex(OSError, "optional evidence write failed"):
                    run_guarded.run([
                        "--timeout", "1", "--project-root", str(project), "--evidence", str(evidence),
                        "--", sys.executable, "-c", "pass"
                    ])
            popen.assert_not_called()
            self.assertFalse((project / ".local" / "run_guarded.lock").exists())
            manifests = list((project / ".local" / "runs").glob("*/manifest.json"))
            self.assertEqual(len(manifests), 1)
            result = json.loads(manifests[0].read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "MEASURE_GUARD_BLOCKED")
            self.assertIn("finished_utc", result)
            self.assertFalse(evidence.exists())


@unittest.skipUnless(os.name == "nt", "requires Windows Job Object and an idle measurement host")
class WindowsDescendantTimeoutTests(unittest.TestCase):
    def test_live_legacy_owner_is_not_signalled_or_reclaimed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lease.lock"
            with subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"]) as owner:
                original = json.dumps({"run_id": "legacy", "pid": owner.pid})
                path.write_text(original, encoding="utf-8")
                contender = run_guarded.ProjectLock(path, {"run_id": "new", "pid": os.getpid()})
                try:
                    with self.assertRaisesRegex(RuntimeError, "project writer lock exists"):
                        contender.acquire()
                    self.assertIsNone(owner.poll(), "probing a live owner must never terminate it")
                    self.assertEqual(path.read_text(encoding="utf-8"), original)
                finally:
                    owner.terminate()
                    owner.wait(timeout=3)

    def test_dead_legacy_owner_can_be_recovered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lease.lock"
            with subprocess.Popen([sys.executable, "-c", "pass"]) as owner:
                owner.wait(timeout=3)
                path.write_text(json.dumps({"run_id": "old", "pid": owner.pid}), encoding="utf-8")
                lease = run_guarded.ProjectLock(path, {"run_id": "new", "pid": os.getpid()})
                lease.acquire()
                try:
                    self.assertEqual(json.loads(path.read_text())["run_id"], "new")
                    contender = run_guarded.ProjectLock(path, {"run_id": "racing", "pid": os.getpid()})
                    with self.assertRaises(RuntimeError):
                        contender.acquire()
                finally:
                    lease.release()
                self.assertFalse(path.exists())

    def test_crashed_owner_releases_os_gate_and_new_owner_is_exclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lease.lock"
            ready = Path(tmp) / "ready"
            script = (
                "import os,sys,time; from pathlib import Path; from tools.run_guarded import ProjectLock; "
                "lease=ProjectLock(Path(sys.argv[1]), {'run_id':'crash','pid':os.getpid()}); "
                "lease.acquire(); Path(sys.argv[2]).write_text('ready'); time.sleep(60)"
            )
            with subprocess.Popen([sys.executable, "-c", script, str(path), str(ready)], cwd=Path(__file__).resolve().parents[1]) as owner:
                try:
                    deadline = time.monotonic() + 3
                    while not ready.exists() and owner.poll() is None and time.monotonic() < deadline:
                        time.sleep(0.02)
                    self.assertTrue(ready.exists(), "child must hold the lease before crash")
                finally:
                    owner.terminate()
                    owner.wait(timeout=3)
            lease = run_guarded.ProjectLock(path, {"run_id": "recovered", "pid": os.getpid()})
            lease.acquire()
            try:
                with self.assertRaises(RuntimeError):
                    run_guarded.ProjectLock(path, {"run_id": "second", "pid": os.getpid()}).acquire()
                self.assertEqual(json.loads(path.read_text())["run_id"], "recovered")
            finally:
                lease.release()

    def test_simultaneous_recovery_has_one_writer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path = folder / "lease.lock"
            with subprocess.Popen([sys.executable, "-c", "pass"]) as old:
                old.wait(timeout=3)
                path.write_text(json.dumps({"run_id": "old", "pid": old.pid}), encoding="utf-8")
            script = '''import os,sys,time
from pathlib import Path
from tools.run_guarded import ProjectLock
folder=Path(sys.argv[1]); identity=sys.argv[2]
while not (folder/'start').exists(): time.sleep(0.01)
lease=ProjectLock(folder/'lease.lock', {'run_id':identity,'pid':os.getpid()})
try:
    lease.acquire()
except RuntimeError:
    (folder/identity).write_text('blocked')
else:
    (folder/identity).write_text('acquired')
    while not (folder/'finish').exists(): time.sleep(0.01)
    lease.release()
'''
            workers = [subprocess.Popen([sys.executable, "-c", script, str(folder), name], cwd=Path(__file__).resolve().parents[1]) for name in ("a", "b")]
            try:
                (folder / "start").touch()
                deadline = time.monotonic() + 4
                while not all((folder / name).exists() for name in ("a", "b")) and time.monotonic() < deadline:
                    time.sleep(0.02)
                outcomes = [(folder / name).read_text() for name in ("a", "b")]
                self.assertEqual(sorted(outcomes), ["acquired", "blocked"])
            finally:
                (folder / "finish").touch()
                for worker in workers:
                    try:
                        worker.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        worker.terminate(); worker.wait(timeout=3)
            self.assertFalse(path.exists())

    def test_timeout_kills_owned_descendant_tree(self) -> None:
        script = (
            "import subprocess,sys,time; "
            "subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
            "time.sleep(60)"
        )
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "fixture.txt").write_text("fixture\n", encoding="utf-8")
            local = project / "localappdata"
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(local)}, clear=False), mock.patch.object(
                run_guarded, "scheduled_hhstudio_running", return_value=(False, None)
            ):
                code, result = run_guarded.run([
                    "--timeout", "0.8", "--project-root", str(project), "--", sys.executable, "-c", script
                ])
            self.assertEqual(code, run_guarded.EXIT_TIMEOUT)
            self.assertTrue(result["timed_out"])
            self.assertEqual(result["status"], "TIMEOUT")
            self.assertIsInstance(result["host_exit_code"], int)
            self.assertEqual(result["active_processes_after_cleanup"], 0)
            manifest = project / ".local" / "runs" / result["run_id"] / "manifest.json"
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["status"], "TIMEOUT")

    def test_actual_nonzero_exit_is_recorded_from_host(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "fixture.txt").write_text("fixture\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(project / "localappdata")}, clear=False), mock.patch.object(
                run_guarded, "scheduled_hhstudio_running", return_value=(False, None)
            ):
                code, result = run_guarded.run([
                    "--timeout", "2", "--project-root", str(project), "--", sys.executable, "-c", "raise SystemExit(7)"
                ])
            self.assertEqual(code, 7)
            self.assertEqual(result["status"], "EXITED")
            self.assertEqual(result["host_exit_code"], 7)
            self.assertEqual(result["active_processes_after_cleanup"], 0)

    def test_measure_lock_started_midrun_stops_child(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "fixture.txt").write_text("fixture\n", encoding="utf-8")
            local = project / "localappdata"
            measure_lock = local / "HHGodotAgent" / "measure-window.lock"
            def start_measurement() -> None:
                time.sleep(0.35)
                measure_lock.parent.mkdir(parents=True, exist_ok=True)
                measure_lock.write_text("measurement-owned\n", encoding="utf-8")
            starter = threading.Thread(target=start_measurement, daemon=True)
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(local)}, clear=False), mock.patch.object(
                run_guarded, "scheduled_hhstudio_running", return_value=(False, None)
            ):
                starter.start()
                code, result = run_guarded.run([
                    "--timeout", "5", "--project-root", str(project), "--", sys.executable, "-c", "import time; time.sleep(60)"
                ])
            starter.join(timeout=2)
            self.assertEqual(code, run_guarded.EXIT_GUARD)
            self.assertEqual(result["status"], "MEASURE_WINDOW_STARTED")
            self.assertEqual(result["active_processes_after_cleanup"], 0)
            self.assertTrue(measure_lock.exists())

    def test_runtime_exception_is_not_left_as_starting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "fixture.txt").write_text("fixture\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(project / "localappdata")}, clear=False), mock.patch.object(
                run_guarded, "scheduled_hhstudio_running", return_value=(False, None)
            ), mock.patch.object(run_guarded, "_ProcessContainer", side_effect=RuntimeError("containment unavailable")), mock.patch("builtins.print"):
                code, result = run_guarded.run([
                    "--timeout", "2", "--project-root", str(project), "--", sys.executable, "-c", "pass"
                ])
            self.assertEqual(code, run_guarded.EXIT_CONTAINMENT)
            self.assertEqual(result["status"], "FAILED")
            manifest = project / ".local" / "runs" / result["run_id"] / "manifest.json"
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()

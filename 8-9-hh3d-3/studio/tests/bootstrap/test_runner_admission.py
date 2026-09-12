"""Integration-style admission tests for the GT-01 fixture runner.

The tests use real temporary files and the production ``main`` entry point,
while replacing only Godot process execution.  They therefore exercise lock,
snapshot, stream and post-run admission without launching an arbitrary binary.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


STUDIO = Path(__file__).resolve().parents[2]
MODULE = STUDIO / "build" / "bootstrap" / "run_fixture.py"
spec = importlib.util.spec_from_file_location("runner_admission", MODULE)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

OBSERVED_VERSION = "4.7.2.stable.official.ed1daf0bf"
TRACE = 'GT01_TRACE {"result":"PASS","phase":"QUITTING"}\n'


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class RunnerAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="hh3d-admission-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "root space-đ"
        self.studio = self.root / "studio"
        self.fixture = self.studio / "fixtures" / "sample-game"
        (self.fixture / "scripts").mkdir(parents=True)
        (self.fixture / "project.godot").write_text("[application]\n", encoding="utf-8")
        (self.fixture / "main.tscn").write_text("[gd_scene format=3]\n", encoding="utf-8")
        (self.fixture / "scripts" / "main.gd").write_text("extends Node\n", encoding="utf-8")
        (self.fixture / "scripts" / "trace.gd").write_text("extends SceneTree\n", encoding="utf-8")
        (self.studio / "source-marker.txt").write_text("stable\n", encoding="utf-8")

        self.tooling = self.root / "tooling"
        self.tooling.mkdir(parents=True)
        real_lock = json.loads((STUDIO / "toolchain.lock.json").read_text(encoding="utf-8"))
        self.lock = copy.deepcopy(real_lock)
        self.lock["schema"] = "HH-STUDIO-TOOLCHAIN-LOCK-2"
        self.lock["status"] = "CANDIDATE"
        pin = self.lock["godot"]
        pin["version"] = "4.7.2-stable"
        pin["source_tag"] = "4.7.2-stable"
        pin["source_commit"] = "ed1daf0bf001b61586d9930840f2f1394092c079"
        pin["observed_version"] = OBSERVED_VERSION
        pin["console_executable"] = "Godot_v4.7.2-stable_win64_console.exe"
        pin["gui_executable"] = "Godot_v4.7.2-stable_win64.exe"
        self.console = self.tooling / pin["console_executable"]
        self.gui = self.tooling / pin["gui_executable"]
        self.console.write_bytes(b"synthetic-console")
        self.gui.write_bytes(b"synthetic-gui")
        pin["console_sha256"] = sha256(self.console.read_bytes())
        pin["gui_sha256"] = sha256(self.gui.read_bytes())
        (self.studio / "toolchain.lock.json").write_text(
            json.dumps(self.lock, indent=2) + "\n", encoding="utf-8")

    def arguments(self, output_name: str = "evidence", **overrides) -> list[str]:
        pin = self.lock["godot"]
        values = {
            "studio-root": str(self.studio),
            "godot-exe": str(self.console),
            "expected-version": pin["version"],
            "console-sha256": pin["console_sha256"],
            "gui-sha256": pin["gui_sha256"],
            "run-id": "GT01-ADMISSION-TEST",
            "command-id": "cmd.gt01.admission.test",
            "output": str(self.root / output_name),
            "timeout-seconds": "10",
        }
        values.update(overrides)
        result: list[str] = []
        for key, value in values.items():
            result.extend((f"--{key}", str(value)))
        return result

    def process_double(self, *, trace: str = TRACE, warning_label: str | None = None,
                       wrapper_failure_label: str | None = None, mutation=None):
        calls: list[str] = []

        def run_process(argv, *, cwd, output, timeout, label):
            calls.append(label)
            stdout = trace if label == "run-3" else ""
            if label == warning_label:
                stdout += "WARNING: synthetic admission warning\n"
            (output / f"{label}-stdout.txt").write_text(stdout, encoding="utf-8")
            (output / f"{label}-stderr.txt").write_bytes(b"")
            if mutation is not None:
                mutation(label, cwd)
            portable_argv = [Path(argv[0]).name]
            for arg in argv[1:]:
                if isinstance(arg, str) and os.path.isabs(arg):
                    try:
                        portable_argv.append("$SNAPSHOT/" + Path(arg).relative_to(cwd).as_posix())
                    except ValueError:
                        portable_argv.append(Path(arg).name)
                else:
                    portable_argv.append(arg)
            return {
                "wrapper_pid": 100 + len(calls),
                "target_pid": 200 + len(calls),
                "started_at": "2026-09-12T00:00:00+00:00",
                "argv": portable_argv,
                "exit_code": 0,
                "wrapper_exit_code": 9 if label == wrapper_failure_label else 0,
                "timed_out": False,
                "tree_verified": True,
                "ownership": "test-double",
                "stdout": f"{label}-stdout.txt",
                "stderr": f"{label}-stderr.txt",
            }

        return run_process, calls

    def invoke(self, output_name: str = "evidence", *, process=None, overrides=None):
        process = process or self.process_double()[0]
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(runner, "_observed_version",
                          return_value=(OBSERVED_VERSION, OBSERVED_VERSION)) as version_mock:
            with patch.object(runner, "run_process", side_effect=process) as process_mock:
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    code = runner.main(self.arguments(output_name, **(overrides or {})))
        return code, version_mock, process_mock, stdout.getvalue(), stderr.getvalue()

    def evidence(self, output_name: str) -> dict:
        return json.loads((self.root / output_name / "evidence.json").read_text(encoding="utf-8"))

    def test_valid_full_three_phase_baseline(self):
        process, calls = self.process_double()
        code, version_mock, process_mock, stdout, stderr = self.invoke(process=process)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(calls, ["run-1", "run-2", "run-3"])
        version_mock.assert_called_once_with(self.console.resolve(), 10)
        self.assertEqual(process_mock.call_count, 3)
        proof = self.evidence("evidence")
        self.assertEqual(proof["status"], "CANDIDATE")
        self.assertTrue(all(proof["checks"].values()))
        self.assertNotIn(str(self.root), json.dumps(proof["runs"], ensure_ascii=False))
        self.assertIn('"status": "CANDIDATE"', stdout)

    def test_caller_hash_and_version_mismatch_reject_before_spawn(self):
        cases = [
            {"expected-version": "4.7.1-stable"},
            {"console-sha256": "1" * 64},
            {"gui-sha256": "2" * 64},
        ]
        for number, overrides in enumerate(cases):
            with self.subTest(overrides=overrides):
                code, version_mock, process_mock, _, error = self.invoke(
                    f"mismatch-{number}", overrides=overrides)
                self.assertEqual(code, 2, error)
                version_mock.assert_not_called()
                process_mock.assert_not_called()
                self.assertFalse((self.root / f"mismatch-{number}").exists())

    def test_existing_output_rejects_with_otherwise_valid_inputs(self):
        output = self.root / "duplicate-output"
        output.mkdir()
        (output / "unrelated.txt").write_text("preserve", encoding="utf-8")
        code, version_mock, process_mock, _, error = self.invoke("duplicate-output")
        self.assertEqual(code, 2, error)
        version_mock.assert_not_called()
        process_mock.assert_not_called()
        self.assertEqual((output / "unrelated.txt").read_text(encoding="utf-8"), "preserve")

    def test_source_change_during_runtime_rejects(self):
        def mutate(label, _cwd):
            if label == "run-3":
                (self.studio / "source-marker.txt").write_text("changed\n", encoding="utf-8")

        code, *_ = self.invoke("source-change", process=self.process_double(mutation=mutate)[0])
        self.assertEqual(code, 2)
        proof = self.evidence("source-change")
        self.assertFalse(proof["checks"]["source_stable"])
        self.assertTrue(proof["checks"]["snapshot_stable"])

    def test_snapshot_change_during_runtime_rejects(self):
        def mutate(label, cwd):
            if label == "run-3":
                (cwd / "main.tscn").write_text("changed snapshot\n", encoding="utf-8")

        code, *_ = self.invoke("snapshot-change", process=self.process_double(mutation=mutate)[0])
        self.assertEqual(code, 2)
        proof = self.evidence("snapshot-change")
        self.assertFalse(proof["checks"]["snapshot_stable"])
        self.assertTrue(proof["checks"]["source_stable"])

    def test_binary_change_during_runtime_rejects(self):
        def mutate(label, _cwd):
            if label == "run-3":
                self.console.write_bytes(b"changed-console")

        code, *_ = self.invoke("binary-change", process=self.process_double(mutation=mutate)[0])
        self.assertEqual(code, 2)
        self.assertFalse(self.evidence("binary-change")["checks"]["binaries_stable"])

    def test_stdout_warning_rejects(self):
        process, _ = self.process_double(warning_label="run-2")
        code, *_ = self.invoke("stdout-warning", process=process)
        self.assertEqual(code, 2)
        proof = self.evidence("stdout-warning")
        self.assertFalse(proof["checks"]["streams_clean"])
        self.assertTrue(proof["checks"]["stderr_clean"])

    def test_duplicate_or_missing_trace_rejects(self):
        for name, trace in (("missing-trace", ""), ("duplicate-trace", TRACE + TRACE)):
            with self.subTest(name=name):
                code, *_ = self.invoke(name, process=self.process_double(trace=trace)[0])
                self.assertEqual(code, 2)
                self.assertFalse(self.evidence(name)["checks"]["trace_exactly_one_pass"])

    def test_wrong_wrapper_exit_rejects(self):
        process, calls = self.process_double(wrapper_failure_label="run-2")
        code, *_ = self.invoke("wrapper-exit", process=process)
        self.assertEqual(code, 2)
        self.assertEqual(calls, ["run-1", "run-2", "run-3"])
        self.assertEqual(self.evidence("wrapper-exit")["status"], "DIAGNOSTIC")


if __name__ == "__main__":
    unittest.main()

"""GT-01 runtime admission probes that do not launch Godot.

These tests deliberately use a synthetic lock and a patched process runner.  They
check the fail-closed admission boundary while an official runtime remint is
still pending; no engine binary is started by this module.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


HERE = Path(__file__).resolve()
STUDIO_SOURCE = HERE.parents[3]
RUNNER_PATH = STUDIO_SOURCE / "studio" / "build" / "bootstrap" / "run_fixture.py"
spec = importlib.util.spec_from_file_location("gt01_runtime_runner", RUNNER_PATH)
runner = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(runner)

OBSERVED = "4.7.2.stable.official.ed1daf0bf"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class RuntimeReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="gt01-runtime-r13-unicode-đ-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "fixture root with spaces-đ"
        self.studio = self.root / "studio"
        fixture = self.studio / "fixtures" / "sample-game" / "scripts"
        fixture.mkdir(parents=True)
        (fixture.parent / "project.godot").write_text("[application]\n", encoding="utf-8")
        (fixture.parent / "main.tscn").write_text("[gd_scene format=3]\n", encoding="utf-8")
        (fixture / "trace.gd").write_text("extends SceneTree\n", encoding="utf-8")
        (self.studio / "source-marker.txt").write_text("stable\n", encoding="utf-8")
        self.tooling = self.root / "tooling"
        self.tooling.mkdir()
        self.console = self.tooling / "Godot_v4.7.2-stable_win64_console.exe"
        self.gui = self.tooling / "Godot_v4.7.2-stable_win64.exe"
        self.console.write_bytes(b"synthetic-console-r13")
        self.gui.write_bytes(b"synthetic-gui-r13")
        lock = json.loads((STUDIO_SOURCE / "studio" / "toolchain.lock.json").read_text(encoding="utf-8"))
        lock = copy.deepcopy(lock)
        lock["status"] = "CANDIDATE"
        godot = lock["godot"]
        godot["console_executable"] = self.console.name
        godot["gui_executable"] = self.gui.name
        godot["console_sha256"] = digest(self.console.read_bytes())
        godot["gui_sha256"] = digest(self.gui.read_bytes())
        godot["observed_version"] = OBSERVED
        (self.studio / "toolchain.lock.json").write_text(json.dumps(lock), encoding="utf-8")
        self.lock = lock

    def args(self, output: str = "evidence", **overrides: str) -> list[str]:
        pin = self.lock["godot"]
        values = {
            "studio-root": str(self.studio), "godot-exe": str(self.console),
            "expected-version": pin["version"], "console-sha256": pin["console_sha256"],
            "gui-sha256": pin["gui_sha256"], "run-id": "GT01-R13-READINESS",
            "command-id": "cmd.gt01.r13.readiness", "output": str(self.root / output),
            "timeout-seconds": "5",
        }
        values.update(overrides)
        result: list[str] = []
        for key, value in values.items():
            result.extend((f"--{key}", str(value)))
        return result

    def test_missing_executable_fails_before_lock_or_spawn(self) -> None:
        missing = self.tooling / "missing-console.exe"
        output = io.StringIO()
        with contextlib.redirect_stderr(output), patch.object(runner, "_observed_version") as probe:
            code = runner.main(self.args(**{"godot-exe": str(missing), "output": str(self.root / "missing-out")}))
        self.assertEqual(code, 2)
        probe.assert_not_called()
        self.assertIn("executable is missing", output.getvalue())

    def test_wrong_hash_and_caller_version_fail_before_probe(self) -> None:
        for suffix, overrides in (("hash", {"console-sha256": "0" * 64}),
                                  ("version", {"expected-version": "4.7.1-stable"})):
            with self.subTest(suffix=suffix):
                with patch.object(runner, "_observed_version") as probe:
                    code = runner.main(self.args(suffix, **overrides))
                self.assertEqual(code, 2)
                probe.assert_not_called()
                self.assertFalse((self.root / suffix).exists())

    def _fake_process(self, *, tree: bool, exit_code: int):
        def run(argv, *, cwd, output, timeout, label):
            (output / f"{label}-stdout.txt").write_text("", encoding="utf-8")
            (output / f"{label}-stderr.txt").write_text("", encoding="utf-8")
            return {"wrapper_pid": 101, "target_pid": 202, "started_at": "2026-09-13T00:00:00+00:00",
                    "argv": [Path(argv[0]).name, "--headless"], "exit_code": exit_code,
                    "wrapper_exit_code": exit_code, "timed_out": False, "tree_verified": tree,
                    "ownership": "test-double", "stdout": f"{label}-stdout.txt", "stderr": f"{label}-stderr.txt"}
        return run

    def test_nonzero_exit_or_unverified_tree_is_diagnostic(self) -> None:
        for suffix, fake in (("exit", self._fake_process(tree=True, exit_code=7)),
                             ("tree", self._fake_process(tree=False, exit_code=0))):
            with self.subTest(suffix=suffix):
                with patch.object(runner, "_observed_version", return_value=(OBSERVED, OBSERVED)), \
                        patch.object(runner, "run_process", side_effect=fake):
                    code = runner.main(self.args(suffix))
                self.assertEqual(code, 2)
                evidence = json.loads((self.root / suffix / "evidence.json").read_text(encoding="utf-8"))
                self.assertEqual(evidence["status"], "DIAGNOSTIC")
                self.assertFalse(evidence["checks"]["process_tree_verified"] if suffix == "tree" else evidence["checks"]["trace_exactly_one_pass"])

    def test_evidence_redacts_host_root_and_keeps_portable_argv(self) -> None:
        fake = self._fake_process(tree=True, exit_code=0)
        with patch.object(runner, "_observed_version", return_value=(OBSERVED, OBSERVED)), \
                patch.object(runner, "run_process", side_effect=fake):
            runner.main(self.args("redaction"))
        raw = (self.root / "redaction" / "evidence.json").read_text(encoding="utf-8")
        self.assertNotIn(str(self.root), raw)
        evidence = json.loads(raw)
        self.assertTrue(all(not any(str(self.root) in str(value) for value in run.values()) for run in evidence["runs"]))


if __name__ == "__main__":
    unittest.main()

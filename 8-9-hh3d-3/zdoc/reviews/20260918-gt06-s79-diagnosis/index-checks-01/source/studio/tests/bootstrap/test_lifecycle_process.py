"""Real-process GT-01 lifecycle checks.

These tests invoke the probe CLI, which in turn launches only short-lived
children of its own.  No network, engine binary, PID signalling, or mocked
installer API is involved.
"""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "build" / "bootstrap" / "lifecycle_probe.py"


class LifecycleProcessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="gt01-lifecycle-")
        cls.work = Path(cls.temp.name)
        cls.report_path = cls.work / "candidate.json"
        command = [sys.executable, str(PROBE), "run", "--work-root", str(cls.work / "run"),
                   "--run-id", "GT01-LIFECYCLE-REAL-20260913", "--output", str(cls.report_path)]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=45, check=False)
        if completed.returncode != 0:
            raise AssertionError("lifecycle probe failed to run")
        cls.report = json.loads(cls.report_path.read_text(encoding="utf-8"))
        cls.evidence_root = cls.work / "run"
        cls.module = importlib.util.spec_from_file_location("lifecycle_probe", PROBE)
        module = importlib.util.module_from_spec(cls.module)
        cls.module.loader.exec_module(module)
        cls.probe_module = module

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_real_probe_is_candidate_with_exact_cases(self):
        self.probe_module.validate_report(self.report, evidence_root=self.evidence_root)
        self.assertEqual(self.report["case_ids"], list(self.probe_module.CASE_IDS))
        self.assertEqual(len(self.report["cases"]), 5)
        self.assertTrue(all(case["status"] == "PASS" for case in self.report["cases"]))

    def test_live_owner_and_crash_observations_are_real(self):
        cases = {case["case_id"]: case for case in self.report["cases"]}
        live = cases["live_owner_guard_refusal"]["observed"]
        self.assertGreater(live["child_pid"], 0)
        self.assertRegex(live["process_start"], r"^(windows:[0-9]+|linux:[0-9a-f-]+:[0-9]+)$")
        self.assertEqual(live["child_exit"], 0)
        crash = cases["crashed_owner_identity_cas_recovery"]["observed"]
        self.assertEqual(crash["child_exit"], 23)
        self.assertEqual(crash["recovery_status"], "STALE_LOCK_RECOVERED")

    def test_replacement_and_manual_edit_preserve_newer_bytes(self):
        cases = {case["case_id"]: case for case in self.report["cases"]}
        replace = cases["replacement_lock_preserved"]["observed"]
        self.assertNotEqual(replace["old_lock_sha256"], replace["replacement_lock_sha256"])
        self.assertEqual(replace["child_exit"], 42)
        manual = cases["manual_active_json_cas_preserved"]["observed"]
        self.assertNotEqual(manual["state_sha256_before_edit"], manual["state_sha256_after_edit"])

    def _verify_rejected(self, report):
        path = self.work / ("hostile-" + str(len(list(self.work.glob("hostile-*.json")))) + ".json")
        path.write_text(json.dumps(report), encoding="utf-8")
        completed = subprocess.run([sys.executable, str(PROBE), "verify", "--report", str(path), "--work-root", str(self.evidence_root)],
                                   capture_output=True, text=True, timeout=10, check=False)
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stdout)["status"], "REJECTED")

    def test_missing_case_evidence_fails_closed(self):
        hostile = copy.deepcopy(self.report)
        hostile["cases"].pop()
        self._verify_rejected(hostile)

    def test_hostile_case_digest_or_status_fails_closed(self):
        hostile = copy.deepcopy(self.report)
        hostile["cases"][0]["observed"]["child_exit"] = 99
        self._verify_rejected(hostile)
        hostile = copy.deepcopy(self.report)
        hostile["cases"][0]["status"] = "PASS"
        hostile["cases"][0]["checks"]["recovery_refused_while_guard_held"] = False
        self._verify_rejected(hostile)


if __name__ == "__main__":
    unittest.main(verbosity=2)

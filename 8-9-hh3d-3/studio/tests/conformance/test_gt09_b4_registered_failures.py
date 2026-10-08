"""Focused B4 contract checks; no Godot or Blender process is started."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tests.conformance import run_gt09_b4_registered_failures as verifier


class GT09B4RegisteredFailureTests(unittest.TestCase):
    def test_hostile_markers_are_immediately_before_behaviour(self):
        report = verifier.verify_hostile_markers()
        self.assertTrue(report["verified"])
        self.assertGreaterEqual(len(report["rows"]), 7)
        for row in report["rows"]:
            self.assertEqual(row["behaviour_line"], row["marker_line"] + 1)

    def test_registered_profile_remains_private_and_scriptless(self):
        report = verifier.build_report(evidence_root=Path("missing-evidence-root"))
        profile = report["profile"]
        self.assertEqual(profile["authority"], 0)
        self.assertFalse(profile["runtime_enabled"])
        self.assertFalse(profile["script_enabled"])
        self.assertFalse(report["public_ack"])
        self.assertFalse(report["registered_script_route"])

    def test_b4_rows_are_explicit_open_gaps(self):
        report = verifier.build_report(evidence_root=Path("missing-evidence-root"))
        self.assertEqual([row["id"] for row in report["rows"]], ["K3", "K4", "K5", "K6", "K7"])
        self.assertTrue(all(row["status"] == "OPEN" for row in report["rows"]))
        self.assertTrue(report["diagnostic_only"])
        self.assertFalse(report["package_ready"])

    def test_existing_receipts_preserve_host_exit_without_promoting_status(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = root / "o2-publication-gt09-auth05-test" / "owner" / "runs" / "command"
            run.mkdir(parents=True)
            result = {
                "schema": "hh-gt03-linux-diagnostic-1",
                "run_id": "native-test",
                "diagnostic_process_clean": False,
                "source_closure_sha256": "a" * 64,
                "command_host": {"exit_code": 137, "timed_out": True},
                "container_state": {"ExitCode": 137},
            }
            (run / "result.json").write_text(json.dumps(result), encoding="utf-8")
            rows = verifier._raw_receipts(root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["actual_exit"], 137)
            self.assertFalse(rows[0]["status"])


if __name__ == "__main__":
    unittest.main()

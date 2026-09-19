"""Static checks for the owned S103 prefix planner; never launches Godot."""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("s103_owned_prefix_subject", HERE / "owned_prefix.py")
SUBJECT = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(SUBJECT)


class OwnedPrefixStaticTests(unittest.TestCase):
    def test_pins_load_fixture_before_source_files_and_verify_overlay(self):
        pins = SUBJECT.verify_pins()
        self.assertEqual(len(pins["sources"]), 53)
        self.assertEqual(pins["source_closure_sha256"], SUBJECT.SOURCE_CLOSURE_SHA256)
        self.assertEqual(pins["profile_sha256"], SUBJECT.PROFILE_SHA256)
        overlay = SUBJECT.generated_overlay()
        self.assertEqual(hashlib.sha256(overlay).hexdigest(),
                         "bb137f32f1fae3730cc139f03fc6902813b3742d5a08d437e957e291cfe0ec46")

    def test_plan_keeps_original_gate_heartbeat_workload_and_diagnostic_scope(self):
        value = SUBJECT.plan("gt06-s103-prefix-test")
        self.assertEqual(value["source_file_count"], 53)
        self.assertEqual(value["preflight"], {
            "exactly_one": True, "http_commands": 1000, "native_cycles": 100,
            "original_native_wall_seconds": 20})
        self.assertEqual(value["prefix"]["batch_indices"], list(range(7)))
        self.assertEqual(value["prefix"]["cycles_per_batch"], 100)
        self.assertEqual(value["prefix"]["status_gap_limit_ms"], 2000)
        self.assertTrue(value["prefix"]["heartbeat_preserved"])
        self.assertFalse(value["formal_acceptance"])
        self.assertFalse(value["eligible_for_dataset"])

    def test_run_id_and_root_are_fresh_and_scoped(self):
        with self.assertRaisesRegex(SUBJECT.OwnedPrefixError, "OWNED_RUN_ID"):
            SUBJECT.validate_run_id("gt06-s102-campaign-01")
        with patch.object(SUBJECT, "HERE", Path(self.id()).resolve().parent):
            # The scoped root check is exercised without creating a directory.
            root = SUBJECT.run_root("gt06-s103-prefix-test")
            self.assertTrue(root.is_relative_to(SUBJECT.HERE.resolve()))

    def test_launch_is_a_fail_closed_blocker_and_does_not_construct_engine(self):
        stream = io.StringIO()
        with patch.object(SUBJECT, "verify_pins", side_effect=AssertionError("launch must not preflight engine")), \
             patch.object(SUBJECT, "generated_overlay", side_effect=AssertionError("launch must not generate project")), \
             contextlib.redirect_stdout(stream):
            status = SUBJECT.main(["--launch", "--run-id", "gt06-s103-prefix-test"])
        self.assertEqual(status, 2)
        report = json.loads(stream.getvalue())
        self.assertEqual(report["status"], "BLOCKED_STATIC_ONLY")
        self.assertEqual(report["reason_code"], "NO_SAFE_BOUNDED_CAMPAIGN_CHILD")
        self.assertFalse(report["engine_started"])
        self.assertFalse(report["formal_acceptance"])

    def test_check_path_has_no_process_launch_symbols(self):
        stream = io.StringIO()
        with patch("subprocess.Popen", side_effect=AssertionError("static check launched process")), \
             contextlib.redirect_stdout(stream):
            status = SUBJECT.main(["--check", "--run-id", "gt06-s103-prefix-test"])
        self.assertEqual(status, 0)
        value = json.loads(stream.getvalue())
        self.assertFalse(value["launch"]["engine_started"])
        self.assertEqual(value["generated_overlay_sha256"], SUBJECT.GENERATED_OVERLAY_SHA256)


if __name__ == "__main__":
    unittest.main()

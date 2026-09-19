"""Unittest coverage for the S103 native save reader; no engine is launched."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("s103_read_native_save", HERE / "read_native_save.py")
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class NativeSaveReaderTests(unittest.TestCase):
    def setUp(self):
        self.source = b"frozen diagnostic source\n"
        self.native_sha = hashlib.sha256(self.source).hexdigest()
        self.identity = {
            "schema_id": reader.SCHEMA,
            "schema_version": "1.0.0",
            "formal_acceptance": False,
            "run_id": "s103-test-run",
            "pid": 4321,
            "batch": 0,
            "cycle": 0,
            "sequence": 1,
            "source_closure_sha256": "a" * 64,
            "profile_sha256": "b" * 64,
            "probe_source_sha256": self.native_sha,
            "save_start_us": 110,
            "process_entry_us": 100,
            "process_entry_frame": 10,
            "entry_event_us": 120,
        }

    def enter(self):
        return {**self.identity, "event": "save_enter"}

    def complete(self):
        return {
            **self.identity,
            "event": "save_complete",
            "call_entry_us": 130,
            "call_return_us": 200,
            "signal_us": 170,
            "signal_frame": 10,
            "save_process_exit_us": 300,
            "save_process_exit_frame": 10,
            "next_process_entry_us": 400,
            "next_process_entry_frame": 11,
            "next_process_exit_us": 600,
            "next_process_exit_frame": 11,
            "readback_end_us": 500,
            "save_result": 0,
            "failed": False,
            "observation_complete": True,
        }

    def write_case(self, stdout, lifecycle=None):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        stdout_path = root / "stdout.txt"
        source_path = root / "native.gd"
        stdout_path.write_bytes(stdout)
        source_path.write_bytes(self.source)
        lifecycle_path = None
        if lifecycle is not None:
            lifecycle_path = root / "lifecycle.json"
            lifecycle_path.write_text(json.dumps(lifecycle), encoding="utf-8")
        return reader.analyze(stdout_path, source_path, lifecycle_path=lifecycle_path)

    def test_complete_boundary_classifies_even_after_diagnostic_forced_stop(self):
        forced = {
            "completed": False,
            "failure_code": "BENCHMARK_CLOSED_BEFORE_FINISH",
            "wrapper_exit_code": 2,
            "job": {"closed": True},
            "wrapper_process_handle": {"closed": True},
        }
        payload = (reader.ENTER + json.dumps(self.enter()) + "\n" +
                   reader.COMPLETE + json.dumps(self.complete()) + "\n").encode()
        result = self.write_case(payload, forced)
        self.assertEqual(result["classification"], "OBSERVED_NATIVE_INTERVALS")
        self.assertEqual(result["lifecycle"]["state"], "DIAGNOSTIC_FORCED_STOP_RECORDED")
        self.assertEqual(result["cycles"][0]["classification"], "NO_OBSERVED_INTERVAL_OVER_THRESHOLD")
        self.assertNotIn("FORCED_OR_UNPROVEN_NATURAL_TARGET_EXIT", result["cycles"][0]["reasons"])

    def test_complete_record_is_usable_when_enter_marker_is_missing(self):
        payload = (reader.COMPLETE + json.dumps(self.complete()) + "\n").encode()
        result = self.write_case(payload)
        row = result["cycles"][0]
        self.assertEqual(row["classification"], "NO_OBSERVED_INTERVAL_OVER_THRESHOLD")
        self.assertIn("MISSING_SAVE_ENTER_EVENT", row["reasons"])

    def test_zero_boundary_is_unknown_and_names_the_missing_boundary(self):
        event = self.complete()
        event.update(call_return_us=0, save_result=-1, failed=True, observation_complete=False)
        payload = (reader.ENTER + json.dumps(self.enter()) + "\n" +
                   reader.COMPLETE + json.dumps(event) + "\n").encode()
        result = self.write_case(payload)
        row = result["cycles"][0]
        self.assertEqual(row["classification"], "UNKNOWN")
        self.assertEqual(row["missing_boundaries"], ["call_return_us"])
        self.assertIn("FAILED_OR_INCOMPLETE_NATIVE_OBSERVATION", row["reasons"])

    def test_missing_complete_event_is_unknown_even_with_legacy_timing_absent(self):
        payload = (reader.ENTER + json.dumps(self.enter()) + "\n").encode()
        result = self.write_case(payload)
        row = result["cycles"][0]
        self.assertEqual(row["classification"], "UNKNOWN")
        self.assertIn("MISSING_CALL_RETURN_AND_COMPLETE_EVENT", row["reasons"])

    def test_sequence_is_bounded_but_sparse_records_are_valid(self):
        event = self.complete()
        event.update(batch=6, cycle=74, sequence=675)
        payload = (reader.COMPLETE + json.dumps(event) + "\n").encode()
        result = self.write_case(payload)
        self.assertEqual((result["cycles"][0]["batch"], result["cycles"][0]["cycle"]), (6, 74))

    def test_sequence_regression_is_rejected(self):
        first = self.enter()
        second = self.enter()
        second.update(cycle=1, sequence=1)
        raw = (reader.ENTER + json.dumps(first) + "\n" +
               reader.ENTER + json.dumps(second) + "\n").encode()
        with self.assertRaisesRegex(reader.EvidenceError, "sequence reused"):
            reader.parse_markers(raw, self.native_sha)


if __name__ == "__main__":
    unittest.main()

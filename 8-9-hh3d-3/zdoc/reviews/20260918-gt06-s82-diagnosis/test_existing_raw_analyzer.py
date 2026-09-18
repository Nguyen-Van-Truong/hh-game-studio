"""Read-only sensitivity checks: corrupt decoded views, never evidence bytes."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

import analyze_existing_raw as analyzer


class EvidenceChecks(unittest.TestCase):
    def reject(self, suffix, tail, mutate, message):
        original = analyzer.load

        def altered(path):
            value = original(path)
            if str(path).replace("\\", "/").endswith(tail):
                value = deepcopy(value)
                mutate(value)
            return value

        with patch.object(analyzer, "load", side_effect=altered):
            with self.assertRaisesRegex(ValueError, message):
                analyzer.analyze(analyzer.SPECS[suffix])

    def test_original_both_runs(self):
        short = analyzer.analyze(analyzer.SPECS[0])[2]
        long = analyzer.analyze(analyzer.SPECS[1])[2]
        self.assertEqual((short["native_batches"], short["object_points"]), (6, 25))
        self.assertEqual((long["native_batches"], long["object_points"]), (16, 45))
        self.assertTrue(long["all_object_count_deltas_zero"])
        self.assertFalse(long["all_identity_deltas_zero_after_initial_inventory"])
        self.assertFalse(long["executed_helper_succeeded"])

    def test_reject_native_exit_relabel(self):
        self.reject(1, "editor-host/process-exit.json", lambda v: v.update(exit_code=1), "process-exit")

    def test_reject_native_batch_count(self):
        self.reject(1, "benchmark/out/index.json", lambda v: v.update(batches_completed=6), "native dimensions")

    def test_reject_snapshot_counter_change(self):
        self.reject(0, "object-0002.json", lambda v: v["counters_before"].update(objects=71130), "counter collection stability")

    def test_reject_erased_identity_churn(self):
        self.reject(1, "object-0002.json", lambda v: v.update(added=[], removed=[]), "snapshot identity delta")

    def test_reject_helper_failure_relabel(self):
        self.reject(1, "result-long-01/probe-host.json", lambda v: v.update(exit_code=0), "outer child exit")

    def test_reject_claimed_cleanup_with_retained_handle(self):
        self.reject(0, "editor-host/capture.json", lambda v: v["job"].update(handle_retained=True), "Job uncertainty")

    def test_reject_inconsistent_source_digest(self):
        self.reject(0, "diagnostic.json", lambda v: v["source_files"].update({"toolchain.lock.json": "0" * 64}), "source closure")

    def test_reject_erased_original_failure(self):
        self.reject(1, "failure.json", lambda v: v.update(type="Success"), "preserved helper failure")


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Pure tests for the offline O6.3 metric calculator.

These tests deliberately do not start a producer or inspect a live process.
They protect the window math and the fail-closed evidence-shape checks.
"""
from pathlib import Path
import copy
import math
import sys
import json
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.tests.replay import residency_metrics as metrics


class ResidencyMetricTests(unittest.TestCase):
    def fixture(self, private=100, private_tail=None, handles=10,
                lookup_tail=1.1, append_tail=1.1):
        identity = {"pid": 1234, "process_start": "2026-09-30T00:00:00Z"}
        summaries, timings, recoveries = [], [], []
        lookup_count = append_count = 0
        for index in range(35):
            value = private if index < 5 or private_tail is None else private_tail
            lookup_value = lookup_tail if index >= 30 else 1.0
            append_value = append_tail if index >= 30 else 1.0
            summaries.append({
                "index": index, "commands": 1000,
                "host_process": copy.deepcopy(identity),
                "memory_after_release": {
                    "process": copy.deepcopy(identity),
                    "counters": {
                        "private_commit_bytes": {"value": value,
                                                  "unavailable_reason": None},
                        "held_handles": {"value": handles,
                                          "unavailable_reason": None},
                    },
                },
                "max_status_gap_ms": 1.0,
            })
            lookup_values = [lookup_value, lookup_value]
            append_values = [append_value, append_value]
            lookup_count += len(lookup_values)
            append_count += len(append_values)
            timings.append({
                "counts": {"load": 1, "lookup": lookup_count,
                            "append": append_count},
                "latency_ms": {"lookup": lookup_values,
                               "append": append_values},
                "dropped": {"lookup": 0, "append": 0},
            })
            recoveries.append({"event_count_before": 0,
                               "event_count_after": 0,
                               "events": [], "all_reconciled": True})
        return summaries, timings, recoveries

    def test_pass_and_re_soak_are_separate_from_formal_acceptance(self):
        data = self.fixture(private=100, private_tail=108,
                            lookup_tail=1.07, append_tail=1.07)
        report = metrics.calculate(*data)
        self.assertTrue(report["metrics_pass"])
        self.assertTrue(report["additional_soak_required"])
        self.assertTrue(report["variation_triggered"])
        self.assertEqual(report["authority"], 0)
        self.assertFalse(report["formal_acceptance"])

    def test_private_and_handle_limits_are_checked_independently(self):
        data = self.fixture(private=100, handles=10)
        data[0][5]["memory_after_release"]["counters"][
            "private_commit_bytes"]["value"] = 111
        data[0][20]["memory_after_release"]["counters"][
            "held_handles"]["value"] = 13
        report = metrics.calculate(*data)
        self.assertIn("private_growth", report["failed_checks"])
        self.assertIn("host_handles_trend", report["failed_checks"])
        self.assertTrue(report["variation_triggered"])
        self.assertTrue(report["additional_soak_required"])

    def test_logical_command_windows_use_all_values_in_first_and_last_batches(self):
        data = self.fixture(private=100, lookup_tail=1.19, append_tail=1.19)
        report = metrics.calculate(*data)
        self.assertTrue(report["metrics_pass"])
        self.assertEqual(report["journal_latency"]["lookup"]["first_operations"], 10)
        self.assertEqual(report["journal_latency"]["lookup"]["last_operations"], 10)
        self.assertEqual(report["journal_latency"]["append"]["first_operations"], 10)

        failing = self.fixture(private=100, lookup_tail=1.21, append_tail=1.19)
        report = metrics.calculate(*failing)
        self.assertIn("lookup_p95", report["failed_checks"])
        self.assertNotIn("append_p95", report["failed_checks"])

    def test_evidence_shape_fails_closed_for_partial_or_unavailable_data(self):
        data = self.fixture()
        with self.assertRaisesRegex(ValueError, "FULL_35_REQUIRED"):
            metrics.calculate(data[0][:-1], data[1][:-1], data[2][:-1])
        data[0][0]["memory_after_release"]["counters"][
            "private_commit_bytes"]["unavailable_reason"] = "ACCESS_DENIED"
        with self.assertRaisesRegex(ValueError, "COUNTER_UNAVAILABLE"):
            metrics.calculate(*data)
        data = self.fixture()
        data[0][10]["memory_after_release"]["counters"][
            "private_commit_bytes"]["value"] = 0
        with self.assertRaisesRegex(ValueError, "COUNTER_UNAVAILABLE"):
            metrics.calculate(*data)

    def test_nonfinite_and_boolean_numbers_are_rejected(self):
        self.assertFalse(metrics.number(True))
        self.assertFalse(metrics.number(float("nan")))
        self.assertFalse(metrics.number(float("inf")))
        with self.assertRaisesRegex(ValueError, "TIMING_VALUES"):
            metrics.p95([1.0, math.inf])

    def test_o7_is_explicit_and_legacy_fail_is_preserved(self):
        """The O6.3 p95 verdict remains visible when O7's finite probe passes."""
        data = self.fixture(private=100, lookup_tail=1.21, append_tail=1.21)
        legacy = metrics.calculate(*data)
        self.assertFalse(legacy["metrics_pass"])
        self.assertIn("lookup_p95", legacy["failed_checks"])
        with self.assertRaisesRegex(ValueError, "INTERLEAVED_PROBE_REQUIRED"):
            metrics.calculate(*data, policy=metrics.O7_POLICY)

    def test_from_run_o7_reports_passing_probe_and_failing_legacy_verdict(self):
        """The O7 file path retains the historical O6.3 result for review."""
        data = self.fixture(private=100, lookup_tail=1.21, append_tail=1.21)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "o7-run"
            root.mkdir()
            summaries, timings, recoveries = data
            for index in range(35):
                batch = {"index": index, "run_id": root.name,
                         "host_process": summaries[index]["host_process"],
                         "commands": [None] * 1000, "max_status_gap_ms": 1.0,
                         "transport_recovery": recoveries[index]}
                for name, value in (("summary", summaries[index]),
                                    ("journal-timing", timings[index]), ("batch", batch)):
                    (root / f"{name}-{index:02}.json").write_text(json.dumps(value))
            retained = {"checks": {"lookup": True, "append": True},
                        "baseline_blocks": 12}
            with (mock.patch.object(metrics, "calculate", wraps=metrics.calculate) as calculate,
                  mock.patch("studio.tests.replay.journal_scaling_metrics.read_bound_probe",
                              return_value=retained)):
                report = metrics.from_run(root, policy=metrics.O7_POLICY,
                                          interleaved_probe=root / "probe-result.json",
                                          seed_directory=root / "seeds")
            self.assertTrue(report["metrics_pass"])
            self.assertEqual(report["policy"], metrics.O7_POLICY)
            self.assertFalse(report["legacy_policy_result"]["metrics_pass"])
            self.assertIn("lookup_p95", report["legacy_policy_result"]["failed_checks"])
            self.assertTrue(calculate.called)

    def test_o1_counters_and_legacy_policy_shape_are_unchanged(self):
        report = metrics.calculate(*self.fixture())
        self.assertEqual(report["load"], 1)
        self.assertEqual(report["recovery_event_count"], 0)
        self.assertEqual(report["policy"], metrics.LEGACY_POLICY)
        self.assertEqual(report["authority"], 0)
        self.assertFalse(report["formal_acceptance"])

    def test_windows_are_neither_5000_operations_nor_mean_batch_percentiles(self):
        data = self.fixture()
        for index, timing in enumerate(data[1]):
            # First logical window p95 = 10; first 5000 operations p95 = 1;
            # average of first five batch percentiles = 2.8. Only pooling the
            # entire logical window accepts the final p95 of 8.
            value = 10 if index == 4 else 8 if index >= 30 else 1
            for operation in ("lookup", "append"):
                timing["latency_ms"][operation] = [value] * 1200
                timing["counts"][operation] = (index + 1) * 1200
        report = metrics.calculate(*data)
        self.assertTrue(report["metrics_pass"])
        self.assertEqual(report["journal_latency"]["lookup"]["first_p95_ms"], 10)
        self.assertEqual(report["journal_latency"]["lookup"]["first_operations"], 6000)

    def test_memory_growth_and_late_trend_use_distinct_windows(self):
        data = self.fixture(private=100, private_tail=108)
        for row in data[0][20:]:
            row["memory_after_release"]["counters"]["private_commit_bytes"]["value"] = 104
        report = metrics.calculate(*data)
        self.assertEqual(report["private_commit"]["growth_percent"], 108)
        self.assertAlmostEqual(report["private_commit"]["late_over_early_percent"], 100 * 104 / 108)

    def test_exact_thresholds_and_warmup_gap(self):
        for peak, passed, repeat in ((107, True, False), (108, True, True),
                                     (110, True, True), (111, False, True)):
            with self.subTest(peak=peak):
                report = metrics.calculate(*self.fixture(private_tail=peak, lookup_tail=1.2,
                                                         append_tail=1.2))
                self.assertEqual(report["metrics_pass"], passed)
                self.assertEqual(report["additional_soak_required"], repeat)
        data = self.fixture()
        for row in data[0][20:]:
            row["memory_after_release"]["counters"]["private_commit_bytes"]["value"] = 105
        data[0][0]["max_status_gap_ms"] = 2000
        self.assertTrue(metrics.calculate(*data)["metrics_pass"])
        data[0][0]["max_status_gap_ms"] = 2000.01
        data[0][20]["memory_after_release"]["counters"]["private_commit_bytes"]["value"] = 106
        self.assertEqual(metrics.calculate(*data)["failed_checks"],
                         ["private_trend", "status_gap_all_batches"])

    def test_incomplete_samples_reload_transport_or_process_identity_rejected(self):
        mutations = (
            (lambda d: d[1][10]["dropped"].update(lookup=1), "TIMING_COVERAGE"),
            (lambda d: d[1][10]["latency_ms"]["lookup"].pop(), "TIMING_COVERAGE"),
            (lambda d: d[1][10]["counts"].update(load=2), "FULL_RELOAD"),
            (lambda d: d[2][10].update(all_reconciled=False), "TRANSPORT_UNRECONCILED"),
            (lambda d: d[2][10].update(event_count_after=1), "TRANSPORT_COVERAGE"),
            (lambda d: d[0][10]["host_process"].update(pid=4321), "PROCESS_IDENTITY"),
        )
        for mutate, code in mutations:
            with self.subTest(code=code):
                data = self.fixture()
                mutate(data)
                with self.assertRaisesRegex(ValueError, code):
                    metrics.calculate(*data)

    def test_file_reader_binds_raw_batch_to_summary_and_run(self):
        summaries, timings, recoveries = self.fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "diagnostic"
            root.mkdir()
            for index in range(35):
                batch = {"index": index, "run_id": root.name,
                         "host_process": summaries[index]["host_process"],
                         "commands": [None] * 1000, "max_status_gap_ms": 1.0,
                         "transport_recovery": recoveries[index]}
                for name, value in (("summary", summaries[index]),
                                    ("journal-timing", timings[index]), ("batch", batch)):
                    (root / f"{name}-{index:02}.json").write_text(json.dumps(value))
            self.assertTrue(metrics.from_run(root)["metrics_pass"])
            path = root / "batch-34.json"
            batch["run_id"] = "foreign-run"
            path.write_text(json.dumps(batch))
            with self.assertRaisesRegex(ValueError, "BATCH_BINDING"):
                metrics.from_run(root)
            batch["run_id"] = root.name
            batch["commands"] = "x" * 1000
            path.write_text(json.dumps(batch))
            with self.assertRaisesRegex(ValueError, "BATCH_BINDING"):
                metrics.from_run(root)
            batch["commands"] = [None] * 1000
            batch["index"] = True
            path.write_text(json.dumps(batch))
            with self.assertRaisesRegex(ValueError, "BATCH_BINDING"):
                metrics.from_run(root)


if __name__ == "__main__":
    unittest.main()

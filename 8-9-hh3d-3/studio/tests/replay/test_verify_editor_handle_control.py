"""Focused tests for the offline O6.5 editor-handle verifier."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.tests.replay import verify_editor_handle_control as verifier


class EditorHandleVerifierTests(unittest.TestCase):
    def write_samples(self, directory, values):
        path = Path(directory) / 'samples.jsonl'
        path.write_text('\n'.join(json.dumps({
            'host_mono_us': 1000 + index * 2,
            'handle_mono_us': 1001 + index * 2,
            'held_handles': value,
        }, sort_keys=True) for index, value in enumerate(values)) + '\n', encoding='utf-8')
        return path

    def test_window_boundaries_use_full_array_and_select_last_row(self):
        values = list(range(71))
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_samples(directory, values)
            result = verifier.analyze_control(path)
        self.assertEqual(result['sample_count'], 71)
        self.assertEqual(result['trimmed_samples'], 0)
        self.assertEqual(result['window_algorithm'], verifier.WINDOW_ALGORITHM)
        expected = [values[(index + 1) * 71 // 35 - 1] for index in range(35)]
        self.assertEqual(result['values'], expected)
        self.assertEqual(result['windows'][0]['selected_row_index'], 1)
        self.assertEqual(result['windows'][-1]['selected_row_index'], 70)

    def test_profile_rule_and_retained_trend_are_reused(self):
        values = [558, 556, 558, 558, 560] + [554] * 15 + [555] * 15
        result = verifier.evaluate_series(values)
        self.assertEqual(result['baseline'], 558)
        self.assertEqual(result['early_median'], 554)
        self.assertEqual(result['late_median'], 555)
        self.assertEqual(result['measured_max'], 555)
        self.assertEqual(result['diagnostic_result'], 'PASS')
        self.assertEqual(result['codes'], [])

    def test_missing_counter_or_nonmonotonic_clock_is_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'samples.jsonl'
            path.write_text('\n'.join(json.dumps({
                'host_mono_us': 1000 + index * 2,
                'handle_mono_us': (1001 + index * 2) if index else 999,
                'held_handles': 1,
            }) for index in range(35)) + '\n', encoding='utf-8')
            with self.assertRaisesRegex(verifier.HandleControlError, 'CONTROL_CLOCK_ORDER'):
                verifier.analyze_control(path)

    def test_formal_reference_binds_manifest_and_joint_hashes(self):
        root = Path(__file__).resolve().parents[3] / 'studio/.local/reviews/gt06-o4-formal-08/run-00-attempt-01'
        result = verifier.analyze_formal(root / 'assembly-manifest.json')
        self.assertEqual(result['run_id'], 'gt06-o4-formal-08.r00.a01')
        self.assertEqual(result['baseline'], 558)
        self.assertEqual(result['early_median'], 554)
        self.assertEqual(result['late_median'], 555)
        self.assertEqual(result['measured_max'], 562)
        self.assertEqual(result['diagnostic_result'], 'PASS')
        self.assertEqual(result['codes'], [])
        self.assertEqual(len(result['observations']), 35)

    def test_retained_control02_raw_reports_owner_review_numbers(self):
        root = Path(__file__).resolve().parents[3]
        samples = root / 'studio/.local/reviews/gt06-stock-editor-control-02/samples.jsonl'
        package = root / 'zdoc/reviews/20260929-gt06-stock-editor-control-02-package-manifest.json'
        result = verifier.analyze_control(samples, package_manifest=package)
        self.assertEqual(result['sample_count'], 2809)
        self.assertEqual(result['baseline'], 564)
        self.assertEqual(result['early_median'], 556)
        self.assertEqual(result['late_median'], 554)
        self.assertEqual(result['measured_max'], 566)
        self.assertEqual(result['diagnostic_result'], 'PASS')
        self.assertEqual(result['codes'], [])


if __name__ == '__main__':
    unittest.main()

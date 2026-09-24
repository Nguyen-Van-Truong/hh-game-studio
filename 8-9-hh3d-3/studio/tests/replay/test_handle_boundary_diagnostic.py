"""Engine-free failure preservation and diagnostic bound regressions."""
from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest
from unittest.mock import Mock, patch

from studio.tests.replay import run_handle_boundary_diagnostic as diagnostic


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.recorder = diagnostic.BoundaryRecorder(self.root, {
            'run_id': 'synthetic', 'source_closure_sha256': 'a' * 64,
            'profile_sha256': 'b' * 64, 'campaign_sha256': 'c' * 64})
        self.recorder.probe = SimpleNamespace(pid=12, process_start='windows:34',
            sample_with_handle_count=Mock(return_value={
                'handle_mono_us': 123, 'held_handles': 554, 'rss_bytes': 42}))
        self.recorder.log = SimpleNamespace(poll=Mock(return_value=None))
        self.recorder.stop = Mock(return_value=False)
        self.recorder.original_screen = Mock()

    def failure(self):
        return diagnostic.campaign.CampaignScreenError('CAMPAIGN_RETAINED_COUNTER_GROWTH',
            index=8, role='editor', counter='held_handles', baseline=552, observed=554, maximum=552)

    def test_first_failure_persisted_before_observation_and_same_exception_reraised(self):
        error = self.failure()
        self.recorder.original_screen.side_effect = error
        def collect(index):
            self.assertEqual(index, 8)
            retained = json.loads((self.root / 'diagnostic-first-failure.json').read_bytes())
            self.assertEqual(retained['screen_observation']['observed_value'], 554)
        self.recorder.collect_idle = Mock(side_effect=collect)
        with self.assertRaises(diagnostic.campaign.CampaignScreenError) as raised:
            self.recorder.screen({'index': 8}, {'original': 'baseline'})
        self.assertIs(raised.exception, error)

    def test_non_screen_fault_never_waits(self):
        self.recorder.original_screen.side_effect = ValueError('synthetic')
        self.recorder.collect_idle = Mock()
        with self.assertRaises(ValueError):
            self.recorder.screen({'index': 5}, None)
        self.recorder.collect_idle.assert_not_called()

    def test_successful_prefix_gets_no_idle_or_replacement(self):
        self.recorder.collect_idle = Mock()
        sample, baseline = {'index': 7}, {'retained': 'unchanged'}
        self.recorder.screen(sample, baseline)
        self.recorder.original_screen.assert_called_once_with(sample, baseline)
        self.recorder.collect_idle.assert_not_called()

    def test_ninth_success_stops_without_tenth_batch(self):
        self.recorder.collect_idle = Mock(return_value=None)
        with self.assertRaises(diagnostic.DiagnosticBoundReached):
            self.recorder.screen({'index': 8}, None)
        self.recorder.collect_idle.assert_called_once_with(8)

    def test_stop_wins_over_bound_complete(self):
        self.recorder.collect_idle = Mock(return_value='BENCHMARK_STOPPED')
        with self.assertRaises(diagnostic.campaign.BenchmarkJobError) as raised:
            self.recorder.screen({'index': 8}, None)
        self.assertEqual(raised.exception.code, 'BENCHMARK_STOPPED')

    def test_idle_stop_takes_no_sample(self):
        self.recorder.stop.return_value = True
        self.assertEqual(self.recorder.collect_idle(8), 'BENCHMARK_STOPPED')
        self.recorder.probe.sample_with_handle_count.assert_not_called()
        result = json.loads((self.root / 'handle-boundary.json').read_bytes())
        self.assertEqual(result['samples'], [])
        self.assertFalse(result['formal_acceptance'])

    def test_idle_has_count_bound_when_clock_stalls(self):
        with patch.object(diagnostic.time, 'monotonic', return_value=1), \
             patch.object(diagnostic.time, 'sleep'):
            self.assertIsNone(self.recorder.collect_idle(8))
        self.assertEqual(len(self.recorder.samples), 21)
        self.assertTrue(all(row['pid'] == 12 for row in self.recorder.samples))

    def test_target_disappearance_is_explicit(self):
        self.recorder.probe.sample_with_handle_count.return_value = None
        self.assertEqual(self.recorder.collect_idle(8), 'DIAGNOSTIC_TARGET_EXITED')
        result = json.loads((self.root / 'handle-boundary.json').read_bytes())
        self.assertEqual(result['collection_error'], 'DIAGNOSTIC_TARGET_EXITED')

    def test_original_failure_survives_supplement_write_error(self):
        error = self.failure()
        self.recorder.original_screen.side_effect = error
        self.recorder.collect_idle = Mock(side_effect=OSError('synthetic'))
        with self.assertRaises(diagnostic.campaign.CampaignScreenError) as raised:
            self.recorder.screen({'index': 8}, None)
        self.assertIs(raised.exception, error)
        self.assertTrue((self.root / 'diagnostic-collector-error.json').exists())

    def test_hooks_restored_after_exception(self):
        c = diagnostic.campaign
        before = (c.open_probe, c.sample_editor, c.NativeLog, c.screen_sample)
        with self.assertRaises(ValueError):
            with self.recorder.installed():
                raise ValueError('synthetic')
        self.assertEqual(before, (c.open_probe, c.sample_editor, c.NativeLog, c.screen_sample))


if __name__ == '__main__':
    unittest.main()

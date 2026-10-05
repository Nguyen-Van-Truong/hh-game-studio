"""Synthetic launch telemetry; no native processes, Docker queries or timed waits."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from studio.tests.replay import run_benchmark_campaign as campaign
from studio.tests.replay.test_benchmark_environment import sample
from studio.tests.replay.benchmark_job import BenchmarkJobError


_COLLECT = campaign.observe_pair_launch


def collect_synthetic(output, context, check_campaign_stop=lambda: None, *, start=0):
    if not callable(check_campaign_stop):  # Explicit fixture start convenience.
        start, check_campaign_stop = check_campaign_stop, lambda: None
    with patch.object(campaign, 'environment_snapshot', side_effect=[sample(t) for t in range(start, start + 61, 5)]), \
         patch.object(campaign, 'verify_sources'), patch.object(campaign.time, 'sleep'):
        _COLLECT(output, context, check_campaign_stop)


class LaunchObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.context = {'run_id': 'gt06-synthetic.r00.a01', 'source_closure_sha256': 'a' * 64,
                        'campaign_sha256': 'b' * 64, 'source_files': {},
                        'launch_observation_schema': campaign.LAUNCH_OBSERVATION_SCHEMA}

    def test_two_pairs_require_their_own_fresh_minute(self):
        first = self.root / 'first'; second = self.root / 'second'
        first.mkdir(); second.mkdir()
        later = {**self.context, 'run_id': 'gt06-synthetic.r01.a01'}
        collect_synthetic(first, self.context)
        collect_synthetic(second, later, start=1000)
        campaign.verify_launch_observation(first, self.context, sample(65))
        campaign.verify_launch_observation(second, later, sample(1065))
        with self.assertRaisesRegex(BenchmarkJobError, 'BINDING'):
            campaign.verify_launch_observation(first, later, sample(1065))
        with self.assertRaisesRegex(BenchmarkJobError, 'STALE'):
            campaign.verify_launch_observation(first, self.context, sample(1065))

    def test_missing_old_marker_short_stream_or_forged_summary_is_rejected(self):
        collect_synthetic(self.root, self.context)
        with self.assertRaisesRegex(BenchmarkJobError, 'REQUIRED_CURRENT_VERIFIER'):
            campaign.verify_launch_observation(self.root, {**self.context, 'launch_observation_schema': None}, sample(65))
        summary_path = self.root / 'launch-observation.json'
        original_summary = summary_path.read_bytes()
        summary = json.loads(original_summary); summary['cpu_max_percent'] = 0
        summary_path.write_bytes(campaign.encoded(summary))
        with self.assertRaisesRegex(BenchmarkJobError, 'OBSERVATION_CHANGED'):
            campaign.verify_launch_observation(self.root, self.context, sample(65))
        summary_path.write_bytes(original_summary)
        path = self.root / 'environment-launch-samples.jsonl'
        lines = path.read_bytes().splitlines(); path.write_bytes(b'\n'.join(lines[:3]) + b'\n')
        with self.assertRaises(BenchmarkJobError):
            campaign.verify_launch_observation(self.root, self.context, sample(65))

    def test_pressure_sleep_and_sustained_cpu_prevent_launch_receipt(self):
        cases = ('memory', 'commit', 'foreign', 'sleep', 'cpu', 'clock_stalled')
        for case in cases:
            with self.subTest(case=case):
                output = self.root / case; output.mkdir()
                rows = [sample(t) for t in range(0, 66, 5)]
                if case == 'memory': rows[-2]['available_memory_bytes'] = 3 * campaign.environment.GIB
                if case == 'commit': rows[-2]['commit_total_bytes'] = 86 * campaign.environment.GIB
                if case == 'foreign': rows[-2]['foreign_engines'] = [{'pid': 10, 'name': 'godot.exe'}]
                if case == 'sleep': rows[-2]['awake_100ns'] -= 20_000_000
                if case == 'cpu':
                    for row in rows: row['cpu_idle_100ns'] = 0
                if case == 'clock_stalled': rows = [sample()] * 14
                with patch.object(campaign, 'environment_snapshot', side_effect=deepcopy(rows)), \
                     patch.object(campaign, 'verify_sources'), patch.object(campaign.time, 'sleep'), \
                     self.assertRaises(BenchmarkJobError):
                    campaign.observe_pair_launch(output, self.context, lambda: None)
                self.assertFalse((output / 'launch-observation.json').exists())

    def test_stop_or_source_drift_keeps_raw_and_forbids_success(self):
        for kind in ('stop', 'source'):
            output = self.root / kind; output.mkdir()
            stop = Mock(side_effect=[None, BenchmarkJobError('CAMPAIGN_STOP_LATCHED')]) if kind == 'stop' else Mock()
            with patch.object(campaign, 'environment_snapshot', return_value=sample()), \
                 patch.object(campaign, 'verify_sources', side_effect=BenchmarkJobError('CAMPAIGN_SOURCE_CHANGED') if kind == 'source' else None), \
                 patch.object(campaign.time, 'sleep'), self.assertRaises(BenchmarkJobError):
                campaign.observe_pair_launch(output, self.context, stop)
            self.assertTrue((output / 'environment-launch-samples.jsonl').exists())
            self.assertFalse((output / 'launch-observation.json').exists())

    def test_sleep_between_minute_and_first_run_sample_is_not_fresh(self):
        collect_synthetic(self.root, self.context)
        with self.assertRaisesRegex(BenchmarkJobError, 'STALE'):
            campaign.verify_launch_observation(self.root, self.context, sample(65, awake_100ns=610_000_000))


if __name__ == '__main__':
    unittest.main()

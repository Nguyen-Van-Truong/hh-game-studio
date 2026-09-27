"""O4 deterministic policy, failure attribution and stop integration regressions."""
from copy import deepcopy
from pathlib import Path
import json
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.tests.replay import benchmark_environment as env
from studio.tests.replay import run_benchmark_campaign as campaign
from studio.tests.replay.benchmark_job import BenchmarkJobError


def sample(second=0, **changes):
    return {'observed_utc': '2026-09-27T09:00:00Z', 'available_memory_bytes': 4 * env.GIB,
            'commit_total_bytes': 80 * env.GIB, 'commit_limit_bytes': 100 * env.GIB,
            'uptime_ms': second * 1000, 'awake_100ns': second * 10_000_000,
            'cpu_total_100ns': second * 10_000_000, 'cpu_idle_100ns': second * 5_000_000,
            'owned_private_bytes': 0, 'owned_inventory_complete': True,
            'foreign_engines': [], 'heavy_processes': [], **changes}


class EnvironmentTests(unittest.TestCase):
    def test_heavy_apps_are_inventory_with_boundary_resources(self):
        row = sample(commit_total_bytes=85 * env.GIB,
                     heavy_processes=[{'name': 'chrome.exe', 'pid': 123}, {'name': 'vmmemwsl', 'pid': 456}])
        result = env.preflight(row)
        self.assertTrue(result['pass'])
        env.require_preflight(result)
        for changes in ({'available_memory_bytes': 4 * env.GIB - 1},
                        {'commit_total_bytes': 85 * env.GIB + 1},
                        {'foreign_engines': [{'pid': 7, 'name': 'Godot_unknown.exe'}]}):
            with self.subTest(changes=changes), self.assertRaises(BenchmarkJobError):
                env.require_preflight(env.preflight({**row, **changes}))

    def test_unknown_inventory_or_fake_pass_is_not_launch_permission(self):
        result = env.preflight(sample())
        for changes in ({'foreign_engines': None}, {'heavy_processes': None},
                        {'commit_limit_bytes': True}, {'available_memory_bytes': True},
                        {'commit_total_bytes': 86 * env.GIB}, {'pass': False},
                        {'schema_version': '1.1.0'}):
            with self.subTest(changes=changes), self.assertRaises(BenchmarkJobError):
                env.require_preflight({**result, **changes})

    def test_commit_93_external_pressure_aborts_immediately(self):
        policy = env.Policy()
        self.assertIsNone(policy.observe(sample()))
        result = policy.observe(sample(5, commit_total_bytes=93 * env.GIB))
        self.assertEqual((result['reason'], result['classification']), ('COMMIT_PRESSURE', 'INFRA_ABORT'))

    def test_owned_or_unknown_pressure_remains_product_failure(self):
        for complete, owned in ((True, 2 * env.GIB), (False, 0)):
            result = env.Policy().observe(sample(commit_total_bytes=93 * env.GIB,
                owned_private_bytes=owned, owned_inventory_complete=complete))
            self.assertEqual(result['classification'], 'PRODUCT_FAIL')

    def test_foreign_engine_aborts_but_owned_engine_does_not(self):
        result = env.Policy().observe(sample(foreign_engines=[{'pid': 77, 'name': 'blender.exe'}]))
        self.assertEqual((result['reason'], result['classification']), ('FOREIGN_ENGINE', 'INFRA_ABORT'))
        self.assertIsNone(env.Policy().observe(sample(owned_private_bytes=env.GIB,
            owned_processes=[{'pid': 78, 'name': 'godot.exe'}])))

    def test_low_available_needs_full_continuous_60_seconds(self):
        policy = env.Policy()
        for second in range(0, 60, 5):
            self.assertIsNone(policy.observe(sample(second, available_memory_bytes=env.GIB)))
        result = policy.observe(sample(60, available_memory_bytes=env.GIB))
        self.assertEqual(result['reason'], 'AVAILABLE_PRESSURE')
        self.assertEqual(result['classification'], 'INFRA_ABORT')

    def test_available_owned_contribution_is_not_infrastructure(self):
        policy = env.Policy()
        for second in range(0, 61, 5):
            result = policy.observe(sample(second, available_memory_bytes=env.GIB, owned_private_bytes=env.GIB))
        self.assertEqual(result['classification'], 'PRODUCT_FAIL')

    def test_low_memory_timer_resets_at_boundary(self):
        policy = env.Policy()
        for second in range(0, 61, 5):
            available = int(1.5 * env.GIB) if second == 55 else env.GIB
            self.assertIsNone(policy.observe(sample(second, available_memory_bytes=available)))

    def test_cpu_95_is_inclusive_and_hot_requires_60_seconds(self):
        policy = env.Policy()
        for second in range(0, 61, 5):
            self.assertIsNone(policy.observe(sample(second, cpu_idle_100ns=second * 500_000)))
        policy = env.Policy()
        for second in range(0, 60, 5):
            self.assertIsNone(policy.observe(sample(second, cpu_idle_100ns=0)))
        self.assertEqual(policy.observe(sample(60, cpu_idle_100ns=0))['reason'], 'CPU_PRESSURE')

    def test_sleep_clock_difference_aborts_before_sampling_gap(self):
        policy = env.Policy()
        policy.observe(sample())
        result = policy.observe(sample(120, awake_100ns=5 * 10_000_000))
        self.assertEqual((result['reason'], result['classification']), ('SLEEP_RESUME', 'INFRA_ABORT'))

    def test_missing_sampling_budget_is_harness_failure(self):
        policy = env.Policy()
        policy.observe(sample())
        result = policy.observe(sample(11))
        self.assertEqual((result['reason'], result['classification']), ('SAMPLE_GAP', 'HARNESS_FAIL'))

    def test_invalid_native_values_fail_closed(self):
        for key, value in (('commit_limit_bytes', 0), ('available_memory_bytes', float('nan')),
                           ('cpu_total_100ns', True), ('foreign_engines', None)):
            with self.subTest(key=key), self.assertRaises(BenchmarkJobError):
                env.Policy().observe(sample(**{key: value}))

    def test_failure_without_watchdog_is_product_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(env.failure_classification(BenchmarkJobError('CAMPAIGN_STATUS_GAP'),
                                                       Path(directory)), 'PRODUCT_FAIL')

    def test_child_failure_cannot_be_downgraded_by_later_watchdog(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'child-failure.json').write_text('{"code":"CAMPAIGN_STATUS_GAP"}')
            error = BenchmarkJobError('CAMPAIGN_WATCHDOG_FOREIGN_ENGINE')
            error.classification = 'INFRA_ABORT'
            self.assertEqual(env.failure_classification(error, root), 'PRODUCT_FAIL')

    def test_watchdog_persists_bound_latch_and_raw_before_raising(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binding = {'run_id': 'test', 'source_closure_sha256': 'a' * 64, 'campaign_sha256': 'b' * 64}
            watch = env.Watchdog(root, lambda: sample(commit_total_bytes=93 * env.GIB),
                                 binding, campaign.write)
            try:
                with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_WATCHDOG_COMMIT_PRESSURE'):
                    watch.poll()
            finally:
                watch.close()
            event = json.loads((root / 'watchdog-stop.json').read_bytes())
            self.assertEqual(event['source_closure_sha256'], binding['source_closure_sha256'])
            self.assertEqual(event['classification'], 'INFRA_ABORT')
            self.assertFalse(event['formal_acceptance'])
            self.assertTrue((root / 'environment-samples.jsonl').read_bytes())
            with self.assertRaisesRegex(BenchmarkJobError, 'STOP_LATCHED'):
                env.verify_watchdog(root, campaign.read_regular)

    def test_owner_failure_wins_before_watchdog_sampling(self):
        with tempfile.TemporaryDirectory() as directory:
            owner = SimpleNamespace(tick=Mock(side_effect=BenchmarkJobError('BENCHMARK_WALL_LIMIT')))
            watch = Mock()
            with self.assertRaisesRegex(BenchmarkJobError, 'BENCHMARK_WALL_LIMIT'):
                campaign.wait_owned_run(owner, Path(directory), run_id='test',
                    source_closure_sha256='a' * 64, campaign_sha256='b' * 64, watchdog=watch)
            watch.poll.assert_not_called()

    def test_success_capture_replays_every_sample_not_pass_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            samples = root / 'environment-samples.jsonl'
            samples.write_text('\n'.join(json.dumps(sample(s)) for s in (0, 5)))
            env.verify_watchdog(root, campaign.read_regular)
            with self.assertRaisesRegex(BenchmarkJobError, 'COVERAGE'):
                env.verify_watchdog(root, campaign.read_regular, elapsed_seconds=100)
            samples.write_text('\n'.join(json.dumps(row) for row in (
                sample(), sample(5, commit_total_bytes=93 * env.GIB))))
            with self.assertRaisesRegex(BenchmarkJobError, 'REPLAY_FAILED'):
                env.verify_watchdog(root, campaign.read_regular)

    def test_keepawake_restores_prior_state_on_failure(self):
        kernel = SimpleNamespace(SetThreadExecutionState=Mock(side_effect=[0x80000002, 0x80000001]))
        with patch.object(env.ctypes, 'WinDLL', return_value=kernel):
            with self.assertRaisesRegex(ValueError, 'original'):
                with env.KeepAwake():
                    raise ValueError('original')
        self.assertEqual([call.args[0] for call in kernel.SetThreadExecutionState.call_args_list],
                         [0x80000001, 0x80000002])

    def test_two_infrastructure_aborts_block_further_daily_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index in range(2):
                env.require_infra_budget(root, campaign.read_regular)
                campaign.write(root / f'gt06-test{index}/run-00-attempt-01/parent-failure.json',
                    {'classification': 'INFRA_ABORT', 'attempt_local_date': env.time.strftime('%Y-%m-%d')})
            with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_INFRA_DAILY_LIMIT'):
                env.require_infra_budget(root, campaign.read_regular)


if __name__ == '__main__':
    unittest.main()

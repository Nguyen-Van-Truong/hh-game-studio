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
            'foreign_engines': [], 'heavy_processes': [], 'docker_wsl_processes': [],
            'top_private_processes': [], 'owned_processes': [], 'processes': [],
            'unavailable_process_count': 0, **changes}


class EnvironmentTests(unittest.TestCase):
    def test_cpu_inventory_encoding_is_lossless_bounded_and_tamper_rejected(self):
        value = sample(processes=[{'pid': n, 'name': 'python.exe', 'owned': False,
            'cpu_total_100ns': n * 100, 'process_start_100ns': n + 1} for n in range(500)])
        packed = env.pack_sample(value)
        self.assertNotIn('processes', packed)
        self.assertEqual(env.unpack_sample(json.loads(json.dumps(packed))), value)
        self.assertLess(len(json.dumps(packed)), len(json.dumps(value)) / 3)
        packed['process_inventory_zlib_b64'] = 'bad!'
        with self.assertRaisesRegex(BenchmarkJobError, 'CPU_ENCODING'):
            env.unpack_sample(packed)

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

    def test_simultaneous_infrastructure_trigger_cannot_mask_product_memory(self):
        for extra, other in (({'foreign_engines': [{'pid': 77}]}, 'FOREIGN_ENGINE'),
                             ({'awake_100ns': 0}, 'SLEEP_RESUME'),
                             ({'uptime_ms': 11000, 'awake_100ns': 110000000}, 'SAMPLE_GAP')):
            with self.subTest(other=other):
                policy = env.Policy()
                policy.observe(sample())
                result = policy.observe(sample(5, commit_total_bytes=93 * env.GIB,
                                               owned_private_bytes=2 * env.GIB, **extra))
                self.assertEqual((result['reason'], result['classification']),
                                 ('COMMIT_PRESSURE', 'PRODUCT_FAIL'))
                self.assertIn(other, result['reasons'])

    def test_external_commit_pressure_cannot_mask_owned_available_pressure(self):
        policy = env.Policy()
        for second in range(0, 60, 5):
            self.assertIsNone(policy.observe(sample(second, available_memory_bytes=env.GIB,
                                                    owned_private_bytes=env.GIB)))
        result = policy.observe(sample(60, available_memory_bytes=env.GIB,
                                       owned_private_bytes=env.GIB, commit_total_bytes=95 * env.GIB))
        self.assertEqual((result['reason'], result['classification']),
                         ('AVAILABLE_PRESSURE', 'PRODUCT_FAIL'))

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

    def test_system_cpu_pressure_alone_does_not_abort(self):
        policy = env.Policy()
        for second in range(0, 61, 5):
            self.assertIsNone(policy.observe(sample(second, cpu_idle_100ns=second * 500_000)))

    def test_external_process_cpu_requires_50_percent_for_60_seconds(self):
        policy = env.Policy()
        for second in range(0, 60, 5):
            self.assertIsNone(policy.observe(sample(second, processes=[
                {'pid': 77, 'name': 'compiler.exe', 'owned': False,
                 'process_start_100ns': 10, 'cpu_total_100ns': second * 10_000_000 * 60 // 100}])))
        result = policy.observe(sample(60, processes=[
            {'pid': 77, 'name': 'compiler.exe', 'owned': False,
             'process_start_100ns': 10, 'cpu_total_100ns': 60 * 10_000_000 * 60 // 100}]))
        self.assertEqual((result['reason'], result['classification']), ('EXTERNAL_CPU_PRESSURE', 'INFRA_ABORT'))
        self.assertEqual(result['top_cpu_processes'][0]['pid'], 77)

    def test_campaign_process_cpu_is_not_external_pressure(self):
        policy = env.Policy()
        for second in range(0, 60, 5):
            self.assertIsNone(policy.observe(sample(second, processes=[
                {'pid': 78, 'name': 'godot.exe', 'owned': True,
                 'process_start_100ns': 11, 'cpu_total_100ns': second * 10_000_000 * 90 // 100}])))
        self.assertIsNone(policy.observe(sample(60, processes=[
            {'pid': 78, 'name': 'godot.exe', 'owned': True,
             'process_start_100ns': 11, 'cpu_total_100ns': 60 * 10_000_000 * 90 // 100}])))

    def test_process_cpu_is_normalized_by_machine_capacity_and_top10_includes_owned(self):
        before = sample(processes=[{'pid': pid, 'name': 'vmmemwsl' if pid == 1 else 'python.exe',
            'owned': pid == 2, 'process_start_100ns': pid, 'cpu_total_100ns': 0} for pid in range(1, 13)])
        after = sample(5, cpu_total_100ns=5 * 16 * 10_000_000,
            processes=[{**p, 'cpu_total_100ns': (13 - p['pid']) * 1_000_000} for p in before['processes']])
        result = env.cpu_interval(before, after)
        self.assertEqual(len(result['top_processes']), 10)
        self.assertEqual(result['top_processes'][0]['name'], 'vmmemwsl')
        self.assertTrue(result['top_processes'][1]['owned'])
        self.assertEqual(result['top_processes'][0]['interval_cpu_percent'], 1.5)
        self.assertFalse(result['hot_external_processes'])

    def test_cpu_timer_resets_for_pid_reuse_missing_counter_or_cool_interval(self):
        for reset in ('pid_reuse', 'missing', 'cool'):
            with self.subTest(reset=reset):
                policy = env.Policy()
                for second in range(0, 66, 5):
                    start = 2 if reset == 'pid_reuse' and second >= 55 else 1
                    ticks = second * 5_000_000
                    if reset == 'missing' and second == 55:
                        ticks = None
                    if reset == 'cool' and second >= 55:
                        ticks -= 10_000_000
                    self.assertIsNone(policy.observe(sample(second, processes=[{
                        'pid': 77, 'name': 'external.exe', 'owned': False,
                        'process_start_100ns': start, 'cpu_total_100ns': ticks}])))

    def test_cpu_exact_50_percent_aborts_and_49_99_does_not(self):
        for percent, aborts in ((50, True), (49.99, False)):
            policy = env.Policy()
            for second in range(0, 61, 5):
                result = policy.observe(sample(second, processes=[{
                    'pid': 77, 'name': 'external.exe', 'owned': False,
                    'process_start_100ns': 1,
                    'cpu_total_100ns': int(second * 10_000_000 * percent / 100)}]))
                if second < 60:
                    self.assertIsNone(result)
            self.assertEqual(result is not None, aborts)

    def test_missing_cpu_inventory_is_not_silently_zero_and_idle_pid_is_allowed(self):
        row = sample()
        del row['processes']
        with self.assertRaisesRegex(BenchmarkJobError, 'CPU_INVENTORY'):
            env.Policy().observe(row)
        self.assertIsNone(env.Policy().observe(sample(processes=[{
            'pid': 0, 'name': '[system process]', 'owned': False,
            'process_start_100ns': None, 'cpu_total_100ns': None}])))

    def test_docker_inventory_is_local_readonly_and_query_failure_is_not_empty(self):
        processes = [{'name': 'com.docker.backend.exe'}]
        with patch.object(env.Path, 'is_file', return_value=True), patch.object(env.subprocess, 'run') as run:
            run.return_value = SimpleNamespace(returncode=0, stdout=b'hh-gameplay-1\nother\n')
            self.assertEqual(env.running_containers(processes), ['hh-gameplay-1', 'other'])
            argv = run.call_args.args[0]
            self.assertEqual(argv[1:4], ['--host', 'npipe:////./pipe/dockerDesktopLinuxEngine', 'ps'])
            self.assertEqual(run.call_args.kwargs['timeout'], 2)
            run.return_value = SimpleNamespace(returncode=1, stdout=b'')
            with self.assertRaisesRegex(BenchmarkJobError, 'DOCKER_INVENTORY'):
                env.running_containers(processes)

    def test_docker_inventory_retries_one_transient_read(self):
        processes = [{'name': 'com.docker.backend.exe'}]
        timeout = env.subprocess.TimeoutExpired('docker', 2)
        with patch.object(env.Path, 'is_file', return_value=True), patch.object(env.subprocess, 'run') as run:
            run.side_effect = [timeout, SimpleNamespace(returncode=0, stdout=b'hh-gameplay-1\n')]
            self.assertEqual(env.running_containers(processes), ['hh-gameplay-1'])
            self.assertEqual(run.call_count, 2)
            self.assertEqual(run.call_args.kwargs['timeout'], 2)

    def test_perfproc_fallback_keeps_raw_ticks_without_double_normalization(self):
        processes = [{'pid': 1480, 'name': 'vmmemwsl', 'cpu_total_100ns': None},
                     {'pid': 42, 'name': 'docker', 'cpu_total_100ns': 7}]
        payload = b'[{"IDProcess":1480,"PercentProcessorTime":120,"ElapsedTime":999}]'
        with patch.object(env.Path, 'is_file', return_value=True), patch.object(env.os, 'cpu_count', return_value=12), \
             patch.object(env.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=payload)) as run:
            result = env.perf_process_times(processes)
        self.assertEqual(result[1480], {'cpu_total_100ns': 120, 'process_start_100ns': 999,
                                        'cpu_source': 'PerfProcRaw'})
        self.assertIn('-NoProfile', run.call_args.args[0])
        script = run.call_args.args[0][-1]
        self.assertIn("-Filter 'IDProcess = 1480'", script)
        self.assertNotIn('IDProcess = 42', script)
        self.assertIn('ConvertTo-Json -Compress -InputObject @(', script)
        self.assertEqual(run.call_args.kwargs['timeout'], 8)

    def test_perfproc_fallback_failure_is_unknown_not_zero(self):
        processes = [{'pid': 1480, 'name': 'vmmemwsl', 'cpu_total_100ns': None}]
        with patch.object(env.Path, 'is_file', return_value=True), \
             patch.object(env.subprocess, 'run', side_effect=env.subprocess.TimeoutExpired('powershell', 8)):
            with self.assertRaisesRegex(BenchmarkJobError, 'PERF_COUNTER_QUERY'):
                env.perf_process_times(processes)

    def test_watchdog_cpu_top_is_persisted_and_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binding = {'run_id': 'test', 'source_closure_sha256': 'a' * 64, 'campaign_sha256': 'b' * 64}
            rows = [sample(s, processes=[{'pid': 77, 'name': 'vmmemwsl', 'owned': False,
                'process_start_100ns': 1, 'cpu_total_100ns': s * 1_000_000}]) for s in (0, 5)]
            watch = env.Watchdog(root, Mock(side_effect=rows), binding, campaign.write)
            try:
                watch.poll(force=True)
                watch.poll(force=True)
            finally:
                watch.close()
            env.verify_watchdog(root, campaign.read_regular, expected_binding=binding)
            path = root / 'environment-samples.jsonl'
            captured = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(captured[-1]['cpu_observation']['top_processes'][0]['interval_cpu_percent'], 10)
            captured[-1]['cpu_observation']['top_processes'][0]['interval_cpu_percent'] = 0
            path.write_text('\n'.join(json.dumps(row) for row in captured) + '\n')
            with self.assertRaisesRegex(BenchmarkJobError, 'CPU_OBSERVATION_MISMATCH'):
                env.verify_watchdog(root, campaign.read_regular, expected_binding=binding)

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

    def test_invalid_observer_row_is_durable_harness_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binding = {'run_id': 'test', 'source_closure_sha256': 'a' * 64,
                       'campaign_sha256': 'b' * 64}
            watch = env.Watchdog(root, lambda: {**sample(), 'available_memory_bytes': 'unavailable'},
                                 binding, campaign.write)
            try:
                with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_WATCHDOG_OBSERVER_ERROR') as raised:
                    watch.poll()
            finally:
                watch.close()
            self.assertEqual(getattr(raised.exception, 'classification', None), 'HARNESS_FAIL')
            self.assertTrue((root / 'environment-samples.jsonl').read_bytes())
            self.assertTrue((root / 'watchdog-stop.json').exists())
            self.assertTrue((root / 'watchdog-observation-error.json').exists())

    def test_watchdog_stream_binding_and_timestamp_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binding = {'run_id': 'test', 'source_closure_sha256': 'a' * 64,
                       'campaign_sha256': 'b' * 64}
            watch = env.Watchdog(root, lambda: sample(), binding, campaign.write)
            watch.poll()
            watch.poll(force=True)
            watch.close()
            env.verify_watchdog(root, campaign.read_regular, expected_binding=binding)
            raw = (root / 'environment-samples.jsonl').read_text()
            rows = raw.splitlines()
            rows[0] = json.dumps({**binding, 'schema': 'wrong'})
            (root / 'environment-samples.jsonl').write_text('\n'.join(rows) + '\n')
            with self.assertRaisesRegex(BenchmarkJobError, 'BINDING'):
                env.verify_watchdog(root, campaign.read_regular, expected_binding=binding)

    def test_bad_binding_does_not_create_a_stream(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(BenchmarkJobError, 'WATCHDOG_BINDING'):
                env.Watchdog(root, lambda: sample(), {}, campaign.write)
            self.assertFalse((root / 'environment-samples.jsonl').exists())

    def test_observer_error_still_writes_stop_if_diagnostic_write_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binding = {'run_id': 'test', 'source_closure_sha256': 'a' * 64, 'campaign_sha256': 'b' * 64}
            def write(path, payload):
                if path.name == 'watchdog-observation-error.json':
                    raise OSError('injected write failure')
                campaign.write(path, payload)
            watch = env.Watchdog(root, Mock(side_effect=ValueError('bad sample')), binding, write)
            try:
                with self.assertRaisesRegex(BenchmarkJobError, 'OBSERVER_ERROR') as raised:
                    watch.poll()
            finally:
                watch.close()
            self.assertEqual(raised.exception.classification, 'HARNESS_FAIL')
            self.assertEqual(raised.exception.watchdog_persistence_errors,
                             ['watchdog-observation-error.json:OSError'])
            self.assertTrue((root / 'watchdog-stop.json').is_file())

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
            binding = {'run_id': 'test', 'source_closure_sha256': 'a' * 64,
                       'campaign_sha256': 'b' * 64}
            rows = [json.dumps({'schema': env.SAMPLE_STREAM_SCHEMA, **binding})]
            previous = None
            for second in (0, 5):
                row = sample(second)
                row['cpu_observation'] = env.cpu_interval(previous, row)
                rows.append(json.dumps(row))
                previous = row
            samples.write_text('\n'.join(rows) + '\n')
            env.verify_watchdog(root, campaign.read_regular, expected_binding=binding)
            with self.assertRaisesRegex(BenchmarkJobError, 'COVERAGE'):
                env.verify_watchdog(root, campaign.read_regular, elapsed_seconds=100,
                                    expected_binding=binding)
            rows = [json.dumps({'schema': env.SAMPLE_STREAM_SCHEMA, **binding})]
            previous = None
            for row in (sample(), sample(5, commit_total_bytes=93 * env.GIB)):
                row['cpu_observation'] = env.cpu_interval(previous, row)
                rows.append(json.dumps(row))
                previous = row
            samples.write_text('\n'.join(rows) + '\n')
            with self.assertRaisesRegex(BenchmarkJobError, 'REPLAY_FAILED'):
                env.verify_watchdog(root, campaign.read_regular, expected_binding=binding)

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

"""Synthetic complete raw campaigns; never benchmark or native evidence."""
import copy
import contextlib
from dataclasses import FrozenInstanceError, replace
import io
import json
from pathlib import Path
import sys
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import benchmark_profile as benchmark


def memory():
    return {'phase': 'post_batch_quiescent', **{role: {
        name: ({'value': None, 'unavailable_reason': benchmark.HOST_NOT_APPLICABLE}
               if role == 'host' and name in ('objects', 'resources')
               else {'value': value, 'unavailable_reason': None}) for name, value in
        (('rss_bytes', 1000 if role == 'host' else 2000), ('objects', 10), ('resources', 5), ('held_handles', 2))}
        for role in ('host', 'editor')}}


def synthetic_dataset():
    runs = []
    for run_index in range(10):
        processes = {role: {'pid': 100 + run_index * 2 + i, 'process_start': f'windows:{1000 + run_index * 2 + i}'}
                     for i, role in enumerate(('host', 'editor'))}
        samples = []
        root = 1
        for index in range(35):
            cycles = []
            for number in range(100):
                cycles.append({'index': number, 'root_before': root, 'root_after': root + 1,
                    'before_sha256': 'a' * 64, 'created_sha256': 'b' * 64, 'undone_sha256': 'a' * 64,
                    'saved_file_sha256': 'c' * 64, 'reloaded_sha256': 'a' * 64,
                    'latency_ms': dict.fromkeys(('create', 'undo', 'save', 'reload'), 1),
                    'effects': dict.fromkeys(('create', 'undo', 'save', 'reload'), 1), 'main_thread': True})
                root += 1
            samples.append({'index': index, 'warmup': index < 5, 'processes': copy.deepcopy(processes),
                'started_mono_us': 1 + index * 100_000_000, 'ended_mono_us': (index + 1) * 100_000_000,
                'latency_ms': {kind: [1000 if index < 5 else 100] * count
                               for kind, count in (('inspect', 500), ('rejected', 300), ('admitted', 200))},
                'effects_per_admission': [1] * 200, 'stop_target_instance_id': f'stop.r{run_index}.b{index}',
                'stop_receipt_ms': 1000 if index < 5 else 100, 'max_status_gap_ms': 50,
                'cycles': cycles, 'memory': memory(), 'evidence_sha256': 'd' * 64,
                'dropped_commands': 0, 'dropped_telemetry': 0})
        runs.append({'run_id': f'benchmark.run.{run_index}', 'index': run_index, 'processes': processes,
            'baseline': {'after_batch_index': 4, 'memory': memory()}, 'samples': samples,
            'cleanup': {'host_exit_code': 0, 'editor_exit_code': 0, 'owned_tree_zero': True, 'held_handles': 0}})
    return {'schema_id': 'hh-studio.tools-ux-benchmark', 'schema_version': '1.1.0',
        'profile_sha256': benchmark.PROFILE_SHA256, 'evidence_kind': 'synthetic',
        'provenance': dict.fromkeys(('source_closure_sha256', 'toolchain_sha256',
            'workstation_profile_sha256', 'driver_sha256', 'capture_manifest_sha256'), 'e' * 64), 'runs': runs}


class BenchmarkProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = synthetic_dataset()

    def setUp(self):
        self.data = copy.deepcopy(self.template)

    def rejected(self, code):
        with self.assertRaises(benchmark.BenchmarkError) as caught:
            benchmark.validate_dataset(self.data)
        self.assertEqual(caught.exception.code, code)

    def test_profile_cannot_be_mutated_or_shrunk_under_same_version(self):
        with self.assertRaises(FrozenInstanceError):
            benchmark.PROFILE.process_runs = 1
        with self.assertRaisesRegex(benchmark.BenchmarkError, 'PROFILE_VERSION_REQUIRED'):
            replace(benchmark.PROFILE, measured_batches=1)
        with self.assertRaisesRegex(benchmark.BenchmarkError, 'PROFILE_VERSION_REQUIRED'):
            replace(benchmark.PROFILE, process_runs=True)

    def test_exact_full_campaign_and_warmup_exclusion(self):
        result = benchmark.summarize_dataset(self.data)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['evidence_kind'], 'synthetic')
        self.assertFalse(result['native_acceptance'])
        self.assertEqual(result['command_lane'], 'host_api_50_30_20_mock_effect_allowed')
        self.assertEqual(result['cycle_lane'], 'native_editor_direct_semantic_test_fixture')
        self.assertEqual((result['measured_batches'], result['measured_commands'], result['measured_cycles']),
                         (300, 300000, 30000))
        self.assertEqual(result['excluded_warmup_batches'], 50)
        for run in result['runs']:
            self.assertEqual(run['metrics']['inspect']['count'], 15000)
            self.assertEqual(run['metrics']['inspect']['p95_ms'], 100)
            self.assertEqual(run['metrics']['stop_receipt']['count'], 30)
            self.assertEqual(run['metrics']['stop_receipt']['p95_ms'], 100)
            self.assertEqual(len(run['batches']), 30)

    def test_type7_statistic_goldens_and_per_run_failure_not_hidden(self):
        for sample in self.data['runs'][0]['samples'][5:]:
            sample['latency_ms']['inspect'] = list(range(1, 501))
            sample['stop_receipt_ms'] = 501
        result = benchmark.summarize_dataset(self.data)
        stats = result['runs'][0]['batches'][0]['metrics']['inspect']
        self.assertEqual(stats['p50_ms'], 250.5)
        self.assertAlmostEqual(stats['p95_ms'], 475.05)
        self.assertAlmostEqual(stats['p99_ms'], 495.01)
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['failures'], [{'run_id': 'benchmark.run.0', 'code': 'STOP_RECEIPT_P95', 'value': 501.0}])

    def test_threshold_boundaries_rss_and_status_gap(self):
        for sample in self.data['runs'][0]['samples'][5:]:
            sample['latency_ms']['inspect'] = [500] * 500
            sample['stop_receipt_ms'] = 500
            sample['max_status_gap_ms'] = 2000
            sample['memory']['host']['rss_bytes']['value'] = 1100
        self.assertEqual(benchmark.summarize_dataset(self.data)['status'], 'PASS')
        self.data['runs'][0]['samples'][14]['memory']['host']['rss_bytes']['value'] = 1101
        self.data['runs'][0]['samples'][9]['max_status_gap_ms'] = 2001
        result = benchmark.summarize_dataset(self.data)
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual({row['code'] for row in result['failures']}, {'RSS_GROWTH', 'STATUS_UPDATE_GAP'})
        self.assertEqual(result['runs'][0]['memory']['host']['rss_bytes']['repetition_10'], 1101)

    def test_held_handles_or_retained_objects_cannot_grow_silently(self):
        self.data['runs'][0]['samples'][34]['memory']['editor']['held_handles']['value'] = 3
        result = benchmark.summarize_dataset(self.data)
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['failures'][0]['counter'], 'held_handles')

    def test_explicit_unavailable_counter_is_gap_never_zero_or_pass(self):
        self.data['runs'][0]['samples'][12]['memory']['host']['held_handles'] = {
            'value': None, 'unavailable_reason': 'host OS does not expose this counter'}
        result = benchmark.summarize_dataset(self.data)
        self.assertEqual(result['status'], 'GAP')
        self.assertIsNone(result['runs'][0]['memory']['host']['held_handles'])
        self.assertEqual(result['gaps'][0]['code'], 'COUNTER_UNAVAILABLE')

    def test_missing_counter_reason_is_rejected(self):
        self.data['runs'][0]['samples'][12]['memory']['host']['held_handles']['value'] = None
        self.rejected('COUNTER_REASON')

    def test_missing_run_batch_command_and_cycle_cannot_pass(self):
        for key in ('run', 'batch', 'command', 'cycle'):
            with self.subTest(key=key):
                self.data = copy.deepcopy(self.template)
                if key == 'run':
                    self.data['runs'].pop()
                elif key == 'batch':
                    self.data['runs'][0]['samples'].pop()
                elif key == 'command':
                    self.data['runs'][0]['samples'][0]['latency_ms']['inspect'].pop()
                else:
                    self.data['runs'][0]['samples'][0]['cycles'].pop()
                self.rejected('INCOMPLETE_ARRAY')

    def test_boolean_and_nonfinite_latency_rejected(self):
        self.data['runs'][0]['samples'][0]['latency_ms']['inspect'][0] = True
        self.rejected('LATENCY')
        self.data['runs'][0]['samples'][0]['latency_ms']['inspect'][0] = 10 ** 1000
        self.rejected('LATENCY')
        self.data['runs'][0]['samples'][0]['latency_ms']['inspect'][0] = float('nan')
        self.rejected('INVALID_JSON_VALUE')

    def test_warmup_cannot_be_relabelled_or_baseline_shifted(self):
        self.data['runs'][0]['samples'][0]['warmup'] = False
        self.rejected('WARMUP_LABEL')
        self.data['runs'][0]['samples'][0]['warmup'] = True
        self.data['runs'][0]['baseline']['memory']['host']['rss_bytes']['value'] = 2000
        self.rejected('WARM_BASELINE')

    def test_lost_and_duplicate_admitted_effects_rejected(self):
        for count in (0, 2, True):
            self.data['runs'][0]['samples'][0]['effects_per_admission'][0] = count
            self.rejected('DUPLICATE_OR_LOST_EFFECT')

    def test_process_restart_and_reused_process_run_rejected(self):
        self.data['runs'][0]['samples'][12]['processes']['editor']['process_start'] = 'windows:99999'
        self.rejected('PROCESS_RESTART')
        self.data = copy.deepcopy(self.template)
        self.data['runs'][1]['processes'] = copy.deepcopy(self.data['runs'][0]['processes'])
        self.rejected('REUSED_PROCESS_RUN')

    def test_duplicate_stop_scope_rejected(self):
        self.data['runs'][0]['samples'][1]['stop_target_instance_id'] = 'stop.r0.b0'
        self.rejected('REUSED_STOP_SCOPE')

    def test_incorrect_undo_or_reload_root_rejected(self):
        self.data['runs'][0]['samples'][0]['cycles'][0]['undone_sha256'] = 'f' * 64
        self.rejected('CYCLE_READBACK')
        self.data['runs'][0]['samples'][0]['cycles'][0]['undone_sha256'] = 'a' * 64
        self.data['runs'][0]['samples'][0]['cycles'][1]['root_before'] = 999
        self.rejected('RELOAD_ROOT_CHAIN')

    def test_held_cleanup_and_boolean_exit_rejected(self):
        self.data['runs'][0]['cleanup']['held_handles'] = 1
        self.rejected('UNCLEAN_RUN')
        self.data['runs'][0]['cleanup']['held_handles'] = 0
        self.data['runs'][0]['cleanup']['editor_exit_code'] = False
        self.rejected('UNCLEAN_RUN')

    def test_raw_contract_closed_and_detached(self):
        detached = benchmark.validate_dataset(self.data)
        detached['runs'][0]['samples'][0]['latency_ms']['inspect'][0] = 7
        self.assertEqual(self.data['runs'][0]['samples'][0]['latency_ms']['inspect'][0], 1000)
        self.data['summary'] = {'status': 'PASS'}
        self.rejected('FIELDS')

    def test_parser_duplicate_nonfinite_and_byte_cap(self):
        for raw, code in ((b'{"a":1,"a":2}', 'DUPLICATE_KEY'), (b'{"a":NaN}', 'NONFINITE_JSON'),
                          (b' ' * (benchmark.MAX_BYTES + 1), 'DATASET_BYTE_CAP')):
            with self.assertRaises(benchmark.BenchmarkError) as caught:
                benchmark.parse_dataset(raw)
            self.assertEqual(caught.exception.code, code)


class BenchmarkCliTests(unittest.TestCase):
    def test_applicability_is_closed_and_cannot_waive_required_counters(self):
        value = memory()
        benchmark._memory(value, '$.memory')
        value['host']['objects'] = {'value': 0, 'unavailable_reason': None}
        with self.assertRaisesRegex(benchmark.BenchmarkError, 'HOST_COUNTER_APPLICABILITY'):
            benchmark._memory(value, '$.memory')
        for role, counter in (('host', 'rss_bytes'), ('host', 'held_handles'),
                              ('editor', 'objects'), ('editor', 'resources')):
            value = memory()
            value[role][counter] = {'value': None, 'unavailable_reason': benchmark.HOST_NOT_APPLICABLE}
            with self.assertRaisesRegex(benchmark.BenchmarkError, 'COUNTER_APPLICABILITY'):
                benchmark._memory(value, '$.memory')

    def test_profile_cli_and_missing_input_are_read_only(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(benchmark.main(['--profile']), 0)
        self.assertEqual(json.loads(output.getvalue())['profile_sha256'], benchmark.PROFILE_SHA256)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(benchmark.main(['--input', str(Path(__file__).parent / '__missing_benchmark__.json')]), 2)
        self.assertEqual(json.loads(output.getvalue()), {'status': 'INVALID', 'code': 'INPUT_IO', 'path': '$'})


if __name__ == '__main__':
    unittest.main()

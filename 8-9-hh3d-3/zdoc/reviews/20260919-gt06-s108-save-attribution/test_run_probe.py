"""Fake-only S108 runner integration; no engines, processes or native calls."""
from copy import deepcopy
import importlib.util
import io
import json
import ntpath
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
spec = importlib.util.spec_from_file_location('s108_runner_test', HERE / 'run_probe.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
sys.path.insert(0, str(REPO))
from studio.tests.replay import run_benchmark_campaign as campaign

RAW = REPO / 'studio/.local/reviews/gt06-s105-handles-03'


class IntegratedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'gt06-s108-save-test'
        self.root.mkdir()
        old = r.c.decode(r.c.read(RAW / 'context.json'))
        self.context = {'schema': 'gt06-s108-save-attribution-context-v1',
            'run_id': self.root.name, 'index': 0, 'attempt': 1, 'source_files': old['source_files'],
            'source_closure_sha256': r.c.SOURCE_SHA, 'profile_sha256': r.c.PROFILE_SHA,
            'core_sha256': r.CORE_SHA256, 'local_helper_pins': r.LOCAL_PINS,
            'historical_helper_pins': r.c.HELPER_PINS, 'diagnostic_files': {'frozen/a.py': 'a' * 64},
            'godot_executable': 'C:\\pinned\\Godot.exe', 'limit_batches': 7, 'sample_batches': [5, 6],
            'outer_seconds': 1200, 'max_thread_samples': 8000, 'http_commands_per_batch': 1000,
            'native_cycles_per_batch': 100, 'formal_acceptance': False, 'eligible_for_dataset': False,
            'generated_overlay_sha256': r.c.sha(b'generated-overlay\n')}
        self.context['diagnostic_closure_sha256'] = r.c.closure(self.context['diagnostic_files'])
        self.context['campaign_sha256'] = r.c.binding_hash(self.context)
        r.c.write_new(self.root / 'context.json', self.context)
        self.samples = [r.c.decode(r.c.read(RAW / f'sample-preview-{i:02d}.json')) for i in range(6)]
        self.samples.append(deepcopy(self.samples[5]))
        self.samples[6]['index'] = 6
        for index in (5, 6):
            self.samples[index]['memory'] = deepcopy(self.samples[4]['memory'])
            self.samples[index]['max_status_gap_ms'] = 10
        self.editor = self.samples[0]['processes']['editor']
        self.probe = SimpleNamespace(**self.editor, handle=33, close_uncertain=False)
        self.calls, self.created = [], []
        self.fail_sample = self.fail_close = self.fail_publish = None
        self.original_gate_error = None
        self.writer_failure = False
        self.sampler = SimpleNamespace(ThreadProbe=self.thread_factory)
        self.module = self.fake_campaign()

    def thread_factory(self, process, expected, hwnd, *, max_samples):
        self.assertIs(process, self.probe)
        self.assertEqual(max_samples, 8000)
        self.calls.append(('attach',))
        outer = self
        class Thread:
            def __init__(self):
                self.identity = {**expected, 'executable': ntpath.normcase(expected['executable']),
                    'hwnd': hwnd, 'tid': 99, 'thread_created_100ns': 1234,
                    'query_access': 0x100800, 'owned_window_handles': [hwnd]}
                self.records, self.errors = [], []
                self.handle, self.closed, self.close_uncertain = 44, False, False
                self.close_receipt = None
            def sample(self, batch):
                outer.calls.append(('sample', batch))
                if outer.fail_sample:
                    raise outer.fail_sample
                # Real shape, monotonic timestamp brackets, no native API.
                start = time.perf_counter_ns()
                if self.records and start - self.records[-1]['sample_started_perf_ns'] < 50_000_000:
                    return None
                identity = {key: self.identity[key] for key in ('pid', 'process_start', 'tid', 'thread_created_100ns')}
                row = {**identity, 'schema': 'gt06-s108-thread-cpu-sample-v1',
                    'index': len(self.records), 'batch': batch,
                    'sample_started_perf_ns': start, 'host_before_ns': start,
                    'host_after_ns': start, 'sample_ended_perf_ns': start,
                    'times_api_duration_ns': 0, 'sample_duration_ns': 0,
                    'kernel_100ns': len(self.records) * 10, 'user_100ns': len(self.records) * 10,
                    'formal_acceptance': False, 'eligible_for_dataset': False}
                self.records.append(row)
                return row
            def close(self):
                outer.calls.append(('close',))
                outer.assertTrue((outer.root / 'fake-original-cleanup.json').is_file())
                self.close_receipt = {'status': 'CLOSED', 'native_close_result': True,
                                      'started_perf_ns': 1, 'ended_perf_ns': 2}
                if outer.fail_close:
                    self.close_receipt['status'] = 'FAILED'
                    self.close_receipt['native_close_result'] = False
                    raise outer.fail_close
                self.handle, self.closed = None, True
                return self.close_receipt
        thread = Thread()
        self.created.append(thread)
        return thread

    def marker(self):
        return {'schema_id': 'hh-studio.s108-main-window', 'schema_version': '1.0.0',
            'run_id': self.context['run_id'], 'pid': self.editor['pid'], 'hwnd': 123,
            'window_id': 0, 'display_server': 'Windows', 'main_thread': True,
            'logical_thread': 'godot_editor_main', 'windows_thread_id': None,
            'base_source_sha256': r.c.NATIVE_SHA, 'source_closure_sha256': r.c.SOURCE_SHA,
            'profile_sha256': r.c.PROFILE_SHA, 'generated_overlay_sha256': self.context['generated_overlay_sha256'],
            'diagnostic_closure_sha256': self.context['diagnostic_closure_sha256'],
            'context_sha256': r.c.sha(r.c.read(self.root / 'project/benchmark/s108-context.json')),
            'formal_acceptance': False, 'eligible_for_dataset': False}

    def fake_campaign(self):
        def prepare(project, factory, trusted, binding):
            path = project / 'addons/hh_benchmark/benchmark_native.gd'
            r.c.write_new(path, r.c.read(REPO / 'studio/tests/replay/benchmark_native.gd'))
            (project / 'benchmark/input').mkdir(parents=True)
            return {'addons/hh_benchmark/benchmark_native.gd': r.c.NATIVE_SHA}
        def publish(path, value):
            self.calls.append(('publish', value['batch_index'], value['schema_id']))
            if self.fail_publish:
                raise self.fail_publish
            return campaign.publish(path, value)
        def gate(sample, baseline):
            self.calls.append(('gate', sample['index']))
            if self.original_gate_error and sample['index'] == 5:
                raise self.original_gate_error
            campaign.screen_sample(sample, baseline)
        module = SimpleNamespace(prepare=prepare, open_probe=lambda *a: self.probe,
            publish=publish, NativeLog=campaign.NativeLog, screen_sample=gate)
        def run_child(root):
            baseline = None
            try:
                module.prepare(root / 'project', None, None, {'mode': 'full'})
                owner = SimpleNamespace(output=root / 'editor-host', tick=lambda: None)
                owner.output.mkdir()
                lines = [r.WINDOW_MARKER + json.dumps(self.marker())]
                for i in range(7):
                    for suffix in ('READY', 'BATCH', 'ACK'):
                        lines.append('HH_GT06_BENCHMARK_' + suffix + ' ' + json.dumps(
                            {'batch_index': i, 'ack_observed_mono_us': i + 100}))
                (owner.output / 'stdout.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
                (owner.output / 'stderr.txt').write_bytes(b'')
                log = module.NativeLog(owner)
                module.open_probe(owner, self.context['godot_executable'])
                for index in range(7):
                    log.wait('READY', index, 20)
                    self.calls.append(('http-start', index))
                    before = len([x for x in self.calls if x[0] == 'sample'])
                    log.poll()  # The real CampaignProducer polls during HTTP.
                    self.assertEqual(before, len([x for x in self.calls if x[0] == 'sample']))
                    for kind in ('start', 'ack'):
                        payload = {'schema_id': 'hh-studio.native-cycle-batch-' + kind,
                                   'batch_index': index, 'deadline_mono_us': 1000 + index}
                        module.publish(root / f'project/benchmark/input/{kind}-{index:02d}.json', payload)
                        log.wait('BATCH' if kind == 'start' else 'ACK', index, 185 if kind == 'start' else 30)
                    r.c.write_new(root / f'sample-preview-{index:02d}.json', self.samples[index])
                    module.screen_sample(self.samples[index], baseline)
                    if index == 4:
                        baseline = self.samples[index]['memory']
            finally:
                self.calls.append(('original-cleanup',))
                r.c.write_new(root / 'fake-original-cleanup.json', {'done': True})
        module.run_child = run_child
        return module

    def execute(self, code='S108_PREFIX_BOUNDARY', writer=r.c.write_new):
        originals = {name: getattr(self.module, name) for name in
                     ('prepare', 'publish', 'NativeLog', 'open_probe', 'screen_sample')}
        with self.assertRaises(BaseException) as raised, mock.patch('sys.stdout', new=io.StringIO()):
            r.execute_child(self.root, self.context, self.module, self.sampler, b'generated-overlay\n', writer=writer)
        self.assertEqual(getattr(raised.exception, 'code', None), code)
        for name, value in originals.items():
            self.assertIs(getattr(self.module, name), value)
        return raised.exception

    def test_actual_s105_sample_context_shape(self):
        self.assertNotIn('run_id', self.samples[4])
        self.assertNotIn('campaign_sha256', r.c.decode(r.c.read(RAW / 'context.json')))
        r.validate_context(self.context, self.root)
        for key in ('index', 'attempt', 'campaign_sha256', 'source_files'):
            value = deepcopy(self.context)
            value.pop(key)
            with self.assertRaises((KeyError, r.c.DiagnosticError)):
                r.validate_context(value, self.root)

    def test_real_native_log_prepare_publish_and_gate_integrate_seven_batches(self):
        self.execute()
        raw = r.c.decode(r.c.read(self.root / 'attribution-raw.json'))
        self.assertEqual([row['index'] for row in raw['gates']], list(range(7)))
        self.assertEqual(len(raw['publications']), 14)
        self.assertEqual([row['batch'] for row in raw['anchors']], list(range(7)))
        self.assertEqual({row[1] for row in self.calls if row[0] == 'sample'}, {5, 6})
        self.assertLess(self.calls.index(('attach',)), self.calls.index(('http-start', 0)))
        self.assertLess(self.calls.index(('original-cleanup',)), self.calls.index(('close',)))
        self.assertEqual(raw['thread_close']['native_close_result'], True)
        self.assertEqual(raw['collector_errors'], [])
        self.assertEqual(raw['primary_error']['code'], 'S108_PREFIX_BOUNDARY')
        self.assertEqual((self.root / 'project/addons/hh_benchmark/benchmark_native.gd').read_bytes(), b'generated-overlay\n')
        for publication in raw['publications']:
            self.assertEqual(publication['published_payload']['deadline_mono_us'], 1000 + publication['batch'])
            self.assertLessEqual(publication['host_before_publish_us'], publication['publish_return_host_us'])

    def test_gate_failure_wins_over_sampler_failure_and_cleanup_failure(self):
        self.original_gate_error = r.c.DiagnosticError('CAMPAIGN_STATUS_GAP')
        self.fail_sample = r.c.DiagnosticError('S108_SAMPLE_FAILURE')
        self.fail_close = r.c.DiagnosticError('S108_CLOSE_FAILURE')
        error = self.execute('CAMPAIGN_STATUS_GAP')
        self.assertIs(error, self.original_gate_error)
        raw = r.c.decode(r.c.read(self.root / 'attribution-raw.json'))
        self.assertEqual(raw['gates'][-1]['result'], 'FAILED')
        self.assertEqual(len(raw['gates']), 6)
        self.assertEqual([row['stage'] for row in raw['collector_errors']], ['thread_sample', 'thread_close'])

    def test_sampler_failure_deferred_until_original_gate_passes(self):
        self.fail_sample = r.c.DiagnosticError('S108_SAMPLE_FAILURE')
        self.execute('S108_INSTRUMENTATION_FAILED')
        raw = r.c.decode(r.c.read(self.root / 'attribution-raw.json'))
        self.assertEqual(raw['gates'][-1]['index'], 5)
        self.assertEqual(raw['gates'][-1]['result'], 'PASSED')

    def test_constructor_first_close_failure_survives_successful_cleanup_retry(self):
        factory = self.thread_factory
        first = r.c.DiagnosticError('S108_THREAD_ENDED')
        first.winerror, first.thread_exit_code = 6, 259
        first.cleanup_error = r.c.DiagnosticError('S108_THREAD_CLOSE_FAILED')
        first.cleanup_error.winerror = 5
        def failing(*args, **kwargs):
            owner = factory(*args, **kwargs)
            owner.close_receipt = {'status': 'FAILED', 'native_close_result': False, 'winerror': 5}
            first.cleanup_owner = owner
            raise first
        self.sampler.ThreadProbe = failing
        self.assertIs(self.execute('S108_THREAD_ENDED'), first)
        raw = r.c.decode(r.c.read(self.root / 'attribution-raw.json'))
        self.assertEqual(raw['thread_close']['status'], 'CLOSED')
        retained = raw['collector_errors'][0]
        self.assertEqual(retained['winerror'], 6)
        self.assertEqual(retained['thread_exit_code'], 259)
        self.assertEqual(retained['first_cleanup_error']['code'], 'S108_THREAD_CLOSE_FAILED')
        self.assertEqual(retained['first_cleanup_error']['winerror'], 5)
        self.assertFalse(any(row[0] == 'http-start' for row in self.calls))

    def test_native_error_metadata_is_bounded_and_does_not_copy_exception_text(self):
        error = RuntimeError('secret-path-must-not-be-retained')
        error.winerror, error.thread_exit_code = 'secret', 2**33
        error.cleanup_error = error
        value = r.diagnostic_error_record(error)
        self.assertNotIn('secret', json.dumps(value))
        self.assertNotIn('winerror', value)
        self.assertNotIn('thread_exit_code', value)
        self.assertNotIn('first_cleanup_error', value['first_cleanup_error'])

    def test_raw_writer_error_never_replaces_gate_error(self):
        self.original_gate_error = r.c.DiagnosticError('CAMPAIGN_RETAINED_COUNTER_GROWTH')
        def writer(*args):
            self.assertTrue((self.root / 'fake-original-cleanup.json').is_file())
            raise r.c.DiagnosticError('S108_WRITER_FAILED')
        error = self.execute('CAMPAIGN_RETAINED_COUNTER_GROWTH', writer)
        self.assertIs(error, self.original_gate_error)
        self.assertEqual(error.s108_finalization_errors[0]['code'], 'S108_WRITER_FAILED')

    def test_original_publish_failure_is_primary_and_no_thread_sampling(self):
        self.fail_publish = r.c.DiagnosticError('CAMPAIGN_INPUT_READBACK')
        error = self.execute('CAMPAIGN_INPUT_READBACK')
        self.assertIs(error, self.fail_publish)
        self.assertFalse(any(row[0] == 'sample' for row in self.calls))

    def test_missing_native_announcement_stops_before_http(self):
        with mock.patch.object(self, 'marker', return_value={}):
            with self.assertRaises(BaseException), mock.patch('sys.stdout', new=io.StringIO()):
                r.execute_child(self.root, self.context, self.module, self.sampler, b'generated-overlay\n')
        self.assertFalse(any(row[0] == 'http-start' for row in self.calls))
        raw = r.c.decode(r.c.read(self.root / 'attribution-raw.json'))
        self.assertEqual(raw['collector_errors'][0]['stage'], 'native_ready')

    def test_generated_source_drift_rejected_before_editor(self):
        with self.assertRaises(r.c.DiagnosticError) as raised, mock.patch('sys.stdout', new=io.StringIO()):
            r.execute_child(self.root, self.context, self.module, self.sampler, b'wrong overlay\n')
        self.assertEqual(raised.exception.code, 'S108_OVERLAY_PIN')
        self.assertEqual(self.created, [])

    def test_stop_before_owner_constructor(self):
        factory = mock.Mock(side_effect=AssertionError('must not dispatch'))
        result, owner = r.c.own_run(factory, self.root, self.context, lambda *a, **k: True, 1200)
        factory.assert_not_called()
        self.assertIsNone(owner)
        self.assertEqual(result['primary_error']['code'], 'BENCHMARK_STOPPED')

    def test_stop_during_wait_and_close(self):
        stop = iter((False, True))
        owner = SimpleNamespace(tick=mock.Mock(side_effect=r.c.DiagnosticError('BENCHMARK_STOPPED')), close=mock.Mock())
        result, found = r.c.own_run(lambda: owner, self.root, self.context, lambda *a, **k: next(stop), 1200)
        self.assertIs(owner, found)
        owner.tick.assert_called_once_with(stop=True)
        owner.close.assert_called_once()
        self.assertEqual(result['primary_error']['code'], 'BENCHMARK_STOPPED')

    def test_outer_bound_and_close_failure_separate(self):
        owner = SimpleNamespace(tick=lambda **k: None, close=mock.Mock(side_effect=r.c.DiagnosticError('CLOSE_FAILED')))
        ticks = iter((0, 1201))
        wait = lambda *a: r.c.wait_owner(*a, clock=lambda: next(ticks), sleep=lambda _: None)
        result, _ = r.c.own_run(lambda: owner, self.root, self.context, lambda *a, **k: False, 1200, wait=wait)
        self.assertTrue(result['timed_out'])
        self.assertEqual(result['primary_error']['code'], 'S106_OUTER_TIMEOUT')
        self.assertEqual(result['cleanup_errors'][0]['code'], 'CLOSE_FAILED')

    def test_helper_drift_rejected_before_native_import(self):
        with mock.patch.object(r.c, 'checked_pins', return_value=({}, b'old', {})), \
             mock.patch.object(r.c, 'read', return_value=b'drift'), \
             mock.patch.object(r.c, 'frozen_module') as loader:
            with self.assertRaises(r.c.DiagnosticError) as raised:
                r.check()
            self.assertEqual(raised.exception.code, 'S108_HELPER_PIN')
            loader.assert_not_called()

    def test_capture_allowlist_excludes_caches_secrets_and_journals(self):
        for relative in ('editor-host/localappdata/private.json', 'project/.godot/cache.bin',
                         'commands/commands.jsonl', 'project/private-token.txt', 'editor-host/temp/a.json'):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'do-not-retain')
        r.c.write_new(self.root / 'editor-host/process-start.json', {'pid': 12})
        selected = [path.relative_to(self.root).as_posix() for path in r.selected_capture_paths(self.root)]
        self.assertEqual(selected, ['context.json', 'editor-host/process-start.json'])

    def test_missing_lifecycle_does_not_erase_valid_capture(self):
        failure = {'run_id': self.context['run_id'], 'completed': False, 'formal_acceptance': False,
                   'completed_batches': 7, 'phase': {'batch': 6}, 'code': 'S108_PREFIX_BOUNDARY'}
        r.c.write_new(self.root / 'child-failure.json', failure)
        r.c.write_new(self.root / 'attribution-raw.json', {'raw': 'preserved'})
        owner = {'primary_error': None, 'cleanup_errors': [], 'helper_exit_observed_by_tick': 1}
        with mock.patch.object(r, 'validate_batches', return_value={'count': 7}), \
             mock.patch.object(r, 'validate_raw', return_value={'raw': 'preserved'}):
            result = r.summarize(self.root, self.context, owner, campaign)
        self.assertEqual(result['capture_status'], 'COMPLETE')
        self.assertEqual(result['capture'], {'raw': 'preserved'})
        self.assertEqual(result['status'], 'INCOMPLETE')
        self.assertTrue(result['errors'])

    def test_wrong_helper_exit_never_claims_captured(self):
        failure = {'run_id': self.context['run_id'], 'completed': False, 'formal_acceptance': False,
                   'completed_batches': 7, 'phase': {'batch': 6}, 'code': 'S108_PREFIX_BOUNDARY'}
        r.c.write_new(self.root / 'child-failure.json', failure)
        r.c.write_new(self.root / 'attribution-raw.json', {'raw': 'preserved'})
        for exit_code in (0, 2, None):
            owner = {'primary_error': None, 'cleanup_errors': [], 'helper_exit_observed_by_tick': exit_code}
            with mock.patch.object(r, 'validate_batches', return_value={'count': 7}), \
                 mock.patch.object(r, 'validate_raw', return_value={'raw': 'preserved'}), \
                 mock.patch.object(r.c, 'validate_lifecycle') as lifecycle:
                result = r.summarize(self.root, self.context, owner, campaign)
            self.assertEqual(result['status'], 'INCOMPLETE')
            lifecycle.assert_not_called()

    def test_real_prior_raw_batches_reconstruct_without_shape_invention(self):
        context = r.c.decode(r.c.read(RAW / 'context.json'))
        result = r.validate_batches(RAW, context, 6, campaign)
        self.assertEqual(result['count'], 6)
        self.assertEqual([(row['http_commands'], row['native_cycles']) for row in result['rows']], [(1000, 100)] * 6)


if __name__ == '__main__':
    unittest.main()

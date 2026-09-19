"""Fake-only integration regression tests; no process/engine/native API launch."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
spec = importlib.util.spec_from_file_location('s106_owned_handles', HERE / 'owned_handles.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
sys.path.insert(0, str(REPO))
from studio.tests.replay import run_benchmark_campaign as campaign

RAW = REPO / 'studio/.local/reviews/gt06-s105-handles-03'


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'gt06-s106-handles-test'
        self.root.mkdir()
        old = json.loads((RAW / 'context.json').read_bytes())
        self.samples = [json.loads((RAW / f'sample-preview-{i:02d}.json').read_bytes()) for i in range(6)]
        observed = json.loads((RAW / 'pss/batch-04-after-gate.json').read_bytes())['capture']
        self.context = {**old, 'schema': 'gt06-s106-handle-boundary-context-v1',
                        'run_id': self.root.name, 'index': 0, 'attempt': 1,
                        'helper_original_pins': r.HELPER_PINS,
                        'diagnostic_files': {'frozen/runner.py': 'a' * 64},
                        'diagnostic_paths': {'owned_handles.py': 'frozen/runner.py'},
                        'godot_executable': observed['identity']['executable']}
        self.context.pop('child_script_sha256', None)
        self.context['diagnostic_closure_sha256'] = r.closure(self.context['diagnostic_files'])
        self.calls = []
        self.capture_error = None
        self.capture_status = 'OBSERVED'
        self.capture_cleanup = True
        self.writer_error = None
        self.save_context()
        self.write_samples()
        # Summary tests remint gate metadata over sample-shape fixtures. Raw
        # batch reconstruction has independent tests against unmodified S105.
        patch = mock.patch.object(r, 'validate_batches', side_effect=lambda root, context, count: {
            'count': count, 'rows': [], 'processes': self.samples[0]['processes']})
        patch.start()
        self.addCleanup(patch.stop)

    def save_context(self):
        self.context['campaign_sha256'] = r.binding_hash(self.context)
        # Test fixture setup, not production evidence publication.
        (self.root / 'context.json').write_bytes(r.encoded(self.context))

    def write_samples(self):
        for index, value in enumerate(self.samples):
            (self.root / f'sample-preview-{index:02d}.json').write_bytes(campaign.encoded(value))

    def capture(self, probe):
        index = self.observer.seen[-1]
        gate = r.decode(r.read(self.root / 'gates' / f'batch-{index:02d}.json'))
        self.calls.append((index, gate['result'], gate['error']))
        if self.capture_error:
            raise self.capture_error
        return {'status': self.capture_status, 'binding_verified': True,
                'errors': [] if self.capture_status == 'OBSERVED' else [{'code': 'PSS_TIME_BUDGET'}],
                'cleanup': {'all_released': self.capture_cleanup,
                            'held_resources': [] if self.capture_cleanup else ['snapshot']},
                'identity': {**self.samples[index]['processes']['editor'],
                             'executable': self.context['godot_executable']},
                'handles_captured': 0, 'entries': []}

    def writer(self, path, value):
        if self.writer_error and path.parent.name == 'pss':
            raise self.writer_error
        r.write_new(path, value)

    def make_observer(self, original=None):
        self.observer = r.GateObserver(self.root, self.context, original or campaign.screen_sample,
                                      SimpleNamespace(capture_owned=self.capture), writer=self.writer)
        identity = self.samples[0]['processes']['editor']
        self.observer.probe = SimpleNamespace(**identity, handle=7)
        return self.observer

    def through(self, last=5):
        for index in range(last + 1):
            self.observer(self.samples[index], self.samples[4]['memory'] if index >= 5 else None)

    def expect_code(self, code, fn):
        with self.assertRaises(BaseException) as raised:
            fn()
        self.assertEqual(getattr(raised.exception, 'code', None), code)
        return raised.exception

    def one_batch(self):
        self.context['limit_batches'], self.context['capture_boundaries'] = 1, [0]
        self.save_context()

    def fail_b5(self):
        self.samples[5]['memory']['editor']['held_handles']['value'] = (
            self.samples[4]['memory']['editor']['held_handles']['value'] + 1)
        self.write_samples()

    def lifecycle_fixture(self, code='S106_PREFIX_BOUNDARY'):
        count = self.context['limit_batches']
        failure = r.decode(r.read(RAW / 'child-failure.json'))
        failure.update(run_id=self.context['run_id'], code=code, completed_batches=count,
                       phase={'batch': count - 1, 'phase': 'joint_observation'})
        r.write_new(self.root / 'child-failure.json', failure)
        terminal = r.decode(r.read(RAW / 'child-terminal-cleanup.json'))
        terminal.update(run_id=self.context['run_id'], context=r.ref(self.root, self.root / 'context.json'),
                        completed_batches=count, phase=failure['phase'])
        terminal['primary_error']['code'] = code
        r.write_new(self.root / 'child-terminal-cleanup.json', terminal)
        for name in ('host-owner/cleanup-001.json', 'host-owner/process-start.json',
                     'host-owner/process-exit.json', 'editor-host/process-start.json',
                     'import-host/process-start.json', 'import-host/process-exit.json',
                     'import-host/capture.json'):
            r.write_new(self.root / name, r.read(RAW / name))
        return {'primary_error': None, 'cleanup_errors': [],
                'helper_exit_observed_by_tick': 1, 'timed_out': False}

    def completed(self):
        self.make_observer()
        self.expect_code('S106_PREFIX_BOUNDARY', self.through)
        owner = self.lifecycle_fixture()
        return r.summarize(self.root, self.context, owner)

    def test_actual_sample_has_no_run_id_and_s105_context_is_not_s106_context(self):
        self.assertNotIn('run_id', self.samples[4])
        old = r.decode(r.read(RAW / 'context.json'))
        self.assertNotIn('campaign_sha256', old)
        self.assertNotIn('index', old)
        r.validate_context(self.context, self.root)
        self.context.pop('attempt')
        with self.assertRaises((KeyError, r.DiagnosticError)):
            r.validate_context(self.context, self.root)

    def test_preflight_captures_b0_after_durable_original_pass(self):
        self.one_batch()
        self.make_observer()
        self.expect_code('S106_PREFIX_BOUNDARY', lambda: self.through(0))
        self.assertEqual(self.calls, [(0, 'PASSED', None)])
        self.assertEqual(self.observer.seen, [0])

    def test_preflight_original_failure_is_recorded_before_capture_and_preserved(self):
        self.one_batch()
        primary = campaign.BenchmarkJobError('CAMPAIGN_COUNTER_UNAVAILABLE')
        self.make_observer(lambda *_: (_ for _ in ()).throw(primary))
        actual = self.expect_code(primary.code, lambda: self.through(0))
        self.assertIs(actual, primary)
        self.assertEqual(self.calls[0][:2], (0, 'FAILED'))

    def test_b4_and_successful_b5_both_captured_exact_raw_refs(self):
        self.make_observer()
        self.expect_code('S106_PREFIX_BOUNDARY', self.through)
        self.assertEqual([row[:2] for row in self.calls], [(4, 'PASSED'), (5, 'PASSED')])
        pss = r.decode(r.read(self.root / 'pss/batch-05.json'))
        self.assertEqual(pss['sample'], r.ref(self.root, self.root / 'sample-preview-05.json'))
        self.assertEqual(pss['baseline'], r.ref(self.root, self.root / 'sample-preview-04.json'))
        self.assertLessEqual(r.decode(r.read(self.root / 'gates/batch-05.json'))['recorded_perf_ns'],
                             pss['capture_started_perf_ns'])
        self.assertEqual(self.observer.seen, list(range(6)))

    def test_b5_original_counter_failure_captured_and_preserved(self):
        self.fail_b5()
        self.make_observer()
        self.expect_code('CAMPAIGN_RETAINED_COUNTER_GROWTH', self.through)
        self.assertEqual(self.calls[-1][:2], (5, 'FAILED'))
        self.assertEqual(self.calls[-1][2]['code'], 'CAMPAIGN_RETAINED_COUNTER_GROWTH')

    def test_capture_exception_does_not_mask_original_b5_error(self):
        self.fail_b5()
        self.make_observer()
        self.through(4)
        self.capture_error = r.DiagnosticError('S106_FAKE_CAPTURE_FAILURE')
        actual = self.expect_code('CAMPAIGN_RETAINED_COUNTER_GROWTH',
                                  lambda: self.observer(self.samples[5], self.samples[4]['memory']))
        self.assertIs(actual.s106_instrumentation_errors[0], self.capture_error)
        self.assertEqual(self.calls[-1][:2], (5, 'FAILED'))

    def test_snapshot_write_failure_does_not_mask_original_error(self):
        self.fail_b5()
        self.make_observer()
        self.through(4)
        self.writer_error = OSError('fake full disk')
        actual = self.expect_code('CAMPAIGN_RETAINED_COUNTER_GROWTH',
                                  lambda: self.observer(self.samples[5], self.samples[4]['memory']))
        self.assertIs(actual.s106_instrumentation_errors[0], self.writer_error)
        self.assertTrue((self.root / 'gates/batch-05.json').is_file())

    def test_gate_write_failure_prevents_pss_and_preserves_primary(self):
        self.one_batch()
        primary = campaign.BenchmarkJobError('CAMPAIGN_COUNTER_UNAVAILABLE')
        observer = self.make_observer(lambda *_: (_ for _ in ()).throw(primary))
        observer.writer = lambda *_: (_ for _ in ()).throw(OSError('fake gate disk failure'))
        self.assertIs(self.expect_code(primary.code, lambda: self.through(0)), primary)
        self.assertEqual(self.calls, [])
        self.assertEqual(len(primary.s106_instrumentation_errors), 2)

    def test_unknown_capture_stops_at_b4(self):
        self.make_observer()
        self.capture_status = 'UNKNOWN'
        self.expect_code('S106_PSS_UNKNOWN', self.through)
        self.assertEqual(self.observer.seen, list(range(5)))
        self.assertEqual([row[0] for row in self.calls], [4])

    def test_cleanup_held_stops_at_b4(self):
        self.make_observer()
        self.capture_cleanup = False
        self.expect_code('S106_PSS_UNKNOWN', self.through)
        self.assertEqual(self.observer.seen[-1], 4)

    def test_baseline_mismatch_fails_before_b5_snapshot(self):
        self.make_observer()
        self.through(4)
        other = deepcopy(self.samples[4]['memory'])
        other['editor']['held_handles']['value'] += 1
        self.expect_code('S106_BASELINE_BINDING', lambda: self.observer(self.samples[5], other))
        self.assertEqual([row[0] for row in self.calls], [4])

    def test_complete_boundary_keeps_missing_editor_actual_exit_unknown(self):
        result = self.completed()
        self.assertEqual(result['status'], 'BOUNDARY_CAPTURED', result)
        self.assertEqual(result['lifecycle']['editor_actual_exit_status'], 'UNKNOWN')
        self.assertEqual(result['lifecycle']['editor_helper_exit'], 2)
        self.assertIsNone(result['lifecycle']['actual_exits']['editor-host']['actual_exit'])
        self.assertFalse(result['formal_acceptance'])

    def test_original_failure_classification_inspects_actual_code(self):
        self.fail_b5()
        self.make_observer()
        self.expect_code('CAMPAIGN_RETAINED_COUNTER_GROWTH', self.through)
        owner = self.lifecycle_fixture('CAMPAIGN_RETAINED_COUNTER_GROWTH')
        result = r.summarize(self.root, self.context, owner)
        self.assertEqual(result['status'], 'ORIGINAL_GATE_FAILURE_CAPTURED', result)

    def test_missing_second_snapshot_is_incomplete_not_gate_recorded(self):
        self.make_observer()
        self.through(4)
        owner = self.lifecycle_fixture()
        result = r.summarize(self.root, self.context, owner)
        self.assertEqual(result['status'], 'INCOMPLETE')
        self.assertEqual(result['errors'][-1]['code'], 'S106_SNAPSHOT_SET')

    def test_arbitrary_key_error_failure_is_incomplete(self):
        self.make_observer()
        self.expect_code('S106_PREFIX_BOUNDARY', self.through)
        owner = self.lifecycle_fixture('KeyError')
        result = r.summarize(self.root, self.context, owner)
        self.assertEqual(result['status'], 'INCOMPLETE')

    def test_missing_host_actual_exit_is_incomplete(self):
        self.completed()
        (self.root / 'host-owner/process-exit.json').unlink()
        owner = {'primary_error': None, 'cleanup_errors': [], 'helper_exit_observed_by_tick': 1, 'timed_out': False}
        result = r.summarize(self.root, self.context, owner)
        self.assertEqual(result['status'], 'INCOMPLETE')
        self.assertEqual(result['errors'][-1]['code'], 'S106_LIFECYCLE_MISSING')

    def test_missing_terminal_is_incomplete(self):
        self.completed()
        (self.root / 'child-terminal-cleanup.json').unlink()
        owner = {'primary_error': None, 'cleanup_errors': [], 'helper_exit_observed_by_tick': 1, 'timed_out': False}
        self.assertEqual(r.summarize(self.root, self.context, owner)['status'], 'INCOMPLETE')

    def test_changed_sample_raw_bytes_reject_binding(self):
        self.completed()
        path = self.root / 'sample-preview-05.json'
        path.write_bytes(path.read_bytes() + b'\n')
        owner = {'primary_error': None, 'cleanup_errors': [], 'helper_exit_observed_by_tick': 1, 'timed_out': False}
        result = r.summarize(self.root, self.context, owner)
        self.assertEqual(result['errors'][-1]['code'], 'S106_SNAPSHOT_BINDING')

    def test_helper_drift_rejected_before_import(self):
        file = self.root / 'helper.py'
        file.write_bytes(b'raise RuntimeError("must not execute")\n')
        self.expect_code('S106_FILE_DRIFT', lambda: r.verify_files(self.root, {'helper.py': '0' * 64}))

    def test_frozen_child_executes_prepare_probe_and_screen_hooks_without_engine(self):
        repo = Path(self.temp.name) / 'relocated-repo'
        root = repo / 'studio/.local/reviews' / self.context['run_id']
        frozen_dir = repo / 'zdoc/reviews/s106/owned' / self.context['run_id']
        root.mkdir(parents=True)
        frozen_dir.mkdir(parents=True)
        source = REPO / 'studio'
        for name in self.context['source_files']:
            r.write_new(repo / 'studio' / name, r.read(source / name))
        probe_path = REPO / 'zdoc/reviews/20260919-gt06-s103-status-gap/native_probe.py'
        native_probe = r.frozen_module(probe_path, r.read(probe_path), '_s106_test_native_probe')
        overlay = native_probe.transform(r.read(source / 'tests/replay/benchmark_native.gd'))
        self.assertEqual(r.sha(overlay), r.OVERLAY_SHA)
        values = {'owned_handles.py': r.read(HERE / 'owned_handles.py'),
                  'pss_adapter.py': r.read(REPO / 'zdoc/reviews/20260919-gt06-s105-handles/pss_adapter.py'),
                  'overlay.gd': overlay}
        context = deepcopy(self.context)
        context['diagnostic_files'], context['diagnostic_paths'] = {}, {}
        for name, value in values.items():
            path = frozen_dir / name
            r.write_new(path, value)
            relative = path.relative_to(repo).as_posix()
            context['diagnostic_files'][relative] = r.sha(value)
            context['diagnostic_paths'][name] = relative
        context['diagnostic_closure_sha256'] = r.closure(context['diagnostic_files'])
        context['campaign_sha256'] = r.binding_hash(context)
        r.write_new(root / 'context.json', context)
        loaded = r.frozen_module(frozen_dir / 'owned_handles.py', values['owned_handles.py'], '_s106_relocated_child')
        fake = SimpleNamespace(load_fixture=lambda: None, source_files=lambda: context['source_files'],
                               screen_sample=campaign.screen_sample)
        events = []
        def prepare(project, factory, trusted, binding):
            events.append('prepare')
            native = project / 'addons/hh_benchmark/benchmark_native.gd'
            r.write_new(native, r.read(source / 'tests/replay/benchmark_native.gd'))
            return {'addons/hh_benchmark/benchmark_native.gd': r.NATIVE_SHA}
        def open_probe(owner, executable):
            events.append('probe')
            return SimpleNamespace(handle=7, **self.samples[0]['processes']['editor'])
        fake.prepare, fake.open_probe = prepare, open_probe
        def run_child(child_root):
            initial = fake.prepare(child_root / 'project', None, None, {})
            self.assertEqual(initial['addons/hh_benchmark/benchmark_native.gd'], r.OVERLAY_SHA)
            self.assertEqual(r.sha(r.read(child_root / 'project/addons/hh_benchmark/benchmark_native.gd')), r.OVERLAY_SHA)
            fake.open_probe(None, context['godot_executable'])
            for index, sample in enumerate(self.samples):
                r.write_new(child_root / f'sample-preview-{index:02d}.json', campaign.encoded(sample))
                fake.screen_sample(sample, self.samples[4]['memory'] if index == 5 else None)
        fake.run_child = run_child
        original_loader = loaded.frozen_module
        def load_adapter(*args):
            module = original_loader(*args)
            self.assertTrue(callable(module.capture_owned))
            def capture(probe):
                index = 5 if (root / 'gates/batch-05.json').exists() else 4
                self.assertTrue((root / 'gates' / f'batch-{index:02d}.json').is_file())
                events.append(('capture', index))
                return {'status': 'OBSERVED', 'binding_verified': True, 'errors': [],
                        'cleanup': {'all_released': True, 'held_resources': []},
                        'identity': {**self.samples[index]['processes']['editor'],
                                     'executable': context['godot_executable']},
                        'handles_captured': 0, 'entries': []}
            module.capture_owned = capture
            return module
        with mock.patch.object(sys.modules['studio.tests.replay'], 'run_benchmark_campaign', fake), \
             mock.patch.object(loaded, 'frozen_module', side_effect=load_adapter):
            self.expect_code('S106_PREFIX_BOUNDARY', lambda: loaded.child(root))
        self.assertEqual(events, ['prepare', 'probe', ('capture', 4), ('capture', 5)])
        self.assertIs(fake.prepare, prepare)
        self.assertIs(fake.open_probe, open_probe)
        self.assertIs(fake.screen_sample, campaign.screen_sample)

    def test_wrong_host_exit_not_accepted_as_boundary(self):
        self.completed()
        path = self.root / 'host-owner/process-exit.json'
        value = r.decode(r.read(path))
        value['exit_code'] = 2
        path.write_bytes(r.encoded(value))
        owner = {'primary_error': None, 'cleanup_errors': [], 'helper_exit_observed_by_tick': 1, 'timed_out': False}
        result = r.summarize(self.root, self.context, owner)
        self.assertEqual(result['errors'][-1]['code'], 'S106_EXPECTED_EXCEPTION_EXIT')


class RawBatchTests(unittest.TestCase):
    def test_actual_s105_six_batches_reconstruct_with_exact_refs(self):
        context = r.decode(r.read(RAW / 'context.json'))
        result = r.validate_batches(RAW, context, 6)
        self.assertEqual(result['count'], 6)
        self.assertEqual([row['http_commands'] for row in result['rows']], [1000] * 6)
        self.assertEqual([row['native_cycles'] for row in result['rows']], [100] * 6)

    def test_count_claim_cannot_hide_extra_batch_capture(self):
        context = r.decode(r.read(RAW / 'context.json'))
        with self.assertRaises(r.DiagnosticError) as raised:
            r.validate_batches(RAW, context, 5)
        self.assertEqual(raised.exception.code, 'S106_BATCH_CAPTURE_SET')

    def test_changed_raw_reference_rejected(self):
        context = r.decode(r.read(RAW / 'context.json'))
        original_read = r.read
        def changed(path, *args):
            raw = original_read(path, *args)
            if Path(path).name == 'batch-capture-00.json':
                value = r.decode(raw)
                value['command']['sha256'] = '0' * 64
                return r.encoded(value)
            return raw
        with mock.patch.object(r, 'read', side_effect=changed):
            with self.assertRaises(Exception):
                r.validate_batches(RAW, context, 6)


class FakeOwner:
    def __init__(self, terminal=None, close_error=None):
        self.terminal, self.close_error, self.closed, self.stop_values = terminal, close_error, False, []
    def tick(self, *, stop=False):
        self.stop_values.append(stop)
        if stop:
            raise campaign.BenchmarkJobError('BENCHMARK_STOPPED')
        return self.terminal
    def close(self):
        self.closed = True
        if self.close_error:
            raise self.close_error


class OwnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.context = {'run_id': 'gt06-s106-handles-stop-test', 'source_closure_sha256': r.SOURCE_SHA,
                        'campaign_sha256': 'b' * 64}

    def stop_request(self, **changes):
        value = {'schema': 'HH-GT06-CAMPAIGN-STOP-1', **self.context, 'reason': 'OPERATOR_STOP'}
        value.update(changes)
        r.write_new(self.root / 'stop-request.json', value)

    def test_bound_stop_prevents_factory_dispatch(self):
        self.stop_request()
        owner = FakeOwner()
        factory = mock.Mock(return_value=owner)
        result, returned = r.own_run(factory, self.root, self.context, campaign.stop_requested, 10)
        self.assertEqual(result['primary_error']['code'], 'BENCHMARK_STOPPED')
        factory.assert_not_called()
        self.assertFalse(owner.closed)
        self.assertEqual(owner.stop_values, [])
        self.assertIsNone(returned)

    def test_stale_stop_fails_closed(self):
        self.stop_request(campaign_sha256='c' * 64)
        owner = FakeOwner()
        result, _ = r.own_run(lambda: owner, self.root, self.context, campaign.stop_requested, 10)
        self.assertEqual(result['primary_error']['code'], 'CAMPAIGN_STOP_BINDING')
        self.assertFalse(owner.closed)
        self.assertEqual(owner.stop_values, [])

    def test_stop_race_after_terminal_detection(self):
        values = iter([False, False, True])
        owner = FakeOwner(terminal=1)
        result, _ = r.own_run(lambda: owner, self.root, self.context, lambda *_a, **_k: next(values), 10)
        self.assertEqual(result['primary_error']['code'], 'BENCHMARK_STOPPED')
        self.assertTrue(owner.closed)

    def test_close_failure_does_not_mask_stop(self):
        values = iter([False, True])
        owner = FakeOwner(close_error=r.DiagnosticError('S106_FAKE_CLOSE_FAILURE'))
        result, _ = r.own_run(lambda: owner, self.root, self.context, lambda *_a, **_k: next(values), 10)
        self.assertEqual(result['primary_error']['code'], 'BENCHMARK_STOPPED')
        self.assertEqual(result['cleanup_errors'][0]['code'], 'S106_FAKE_CLOSE_FAILURE')

    def test_constructor_cleanup_owner_retained_and_closed(self):
        owner = FakeOwner()
        primary = campaign.BenchmarkJobError('BENCHMARK_CONSTRUCTOR_FAILED', cleanup_owner=owner)
        def factory():
            raise primary
        result, returned = r.own_run(factory, self.root, self.context, campaign.stop_requested, 10)
        self.assertIs(returned, owner)
        self.assertTrue(owner.closed)
        self.assertEqual(result['primary_error']['code'], primary.code)

    def test_outer_timeout_closes_owner(self):
        owner = FakeOwner()
        values = iter([0, 20])
        def wait(*args):
            return r.wait_owner(*args, clock=lambda: next(values), sleep=lambda _: None)
        result, _ = r.own_run(lambda: owner, self.root, self.context, campaign.stop_requested, 10, wait=wait)
        self.assertTrue(result['timed_out'])
        self.assertTrue(owner.closed)


if __name__ == '__main__':
    unittest.main()

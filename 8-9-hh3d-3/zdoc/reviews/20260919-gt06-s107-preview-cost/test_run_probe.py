"""S107 runner integration with fake engine owners; no native calls or launch."""
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
spec = importlib.util.spec_from_file_location('s107_runner_test', HERE / 'run_probe.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
c = r.c
sys.path.insert(0, str(REPO))
from studio.tests.replay import run_benchmark_campaign as real


def clean_job():
    return {'closed': True, 'zero_observed': True, 'active_count': 0, 'handle_retained': False,
            'tainted': False, 'create_uncertain': False, 'close_uncertain': False, 'failed_operations': []}


def clean_handle():
    return {'closed': True, 'handle_retained': False, 'close_uncertain': False, 'required': True}


class Observer:
    def __init__(self, *_):
        self.closed = False
    def start(self):
        pass
    def close(self):
        self.closed = True
    def snapshot(self):
        return {'closed': self.closed, 'thread_alive': False, 'handle_retained': False,
                'handle_close_uncertain': False, 'probe_handles_released': True,
                'global_held_probe_count': 0, 'error_count': 0}


class RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        old = c.decode(c.read(REPO / 'studio/.local/reviews/gt06-s105-handles-03/context.json'))
        cls.sources = old['source_files']
        cls.source_bytes = {name: c.read(REPO / 'studio' / name) for name in cls.sources}
        cls.helper = c.frozen_module(HERE / 'native_probe.py', c.read(HERE / 'native_probe.py'), '_s107_test_helper')
        cls.overlay = cls.helper.build_overlay(cls.source_bytes['tests/replay/benchmark_native.gd'])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'repo'
        self.root = self.repo / 'studio/.local/reviews/gt06-s107-preview-test'
        self.root.mkdir(parents=True)
        for name, raw in self.source_bytes.items():
            c.write_new(self.repo / 'studio' / name, raw)
        self.owned = self.repo / 'zdoc/reviews/s107/owned/test'
        c.write_new(self.owned / 'overlay.gd', self.overlay)
        relative = (self.owned / 'overlay.gd').relative_to(self.repo).as_posix()
        files = {relative: c.sha(self.overlay)}
        self.context = {'schema': 'gt06-s107-preview-cost-context-v1', 'run_id': self.root.name,
            'source_files': self.sources, 'source_closure_sha256': c.SOURCE_SHA, 'profile_sha256': c.PROFILE_SHA,
            'core_sha256': r.CORE_SHA256, 'native_helper_sha256': r.NATIVE_HELPER_SHA256,
            'diagnostic_files': files, 'diagnostic_paths': {'overlay.gd': relative},
            'diagnostic_closure_sha256': c.closure(files), 'generated_overlay_sha256': c.sha(self.overlay),
            'recipe_sha256': self.helper.RECIPE_SHA256, 'godot_executable': 'C:/owned/godot.exe',
            'godot_sha256': 'a' * 64, 'reader_sha256': 'b' * 64,
            'index': 0, 'attempt': 1, 'cycles': 40, 'groups': 10, 'sequence': 'ABBA',
            'outer_seconds': 180, 'formal_acceptance': False, 'eligible_for_dataset': False}
        self.context['campaign_sha256'] = r.campaign_hash(self.context)
        c.write_new(self.root / 'context.json', self.context)
        self.events, self.owners, self.probes = [], [], []
        self.stopped, self.import_error, self.editor_exit, self.finish_error = False, None, 0, None
        self.campaign = SimpleNamespace(
            load_fixture=lambda: (None, {}), source_files=lambda: self.sources,
            prepare=self.prepare, project_files=self.project_files, MUTABLE_SCENE='scenes/fixture.tscn',
            ImportObserver=Observer, _observed_import=self.import_stage,
            native_job=SimpleNamespace(verify_captured_stage=lambda *_: None),
            BenchmarkProcess=self.owner_factory, open_probe=self.open_probe,
            verify_capture=lambda *_a, **_k: None, stop_requested=lambda *_a, **_k: self.stopped,
            _probe_cleanup_state=real._probe_cleanup_state,
            _editor_cleanup_state=real._editor_cleanup_state,
            _import_cleanup_state=real._import_cleanup_state)

    def project_files(self, project):
        return {p.relative_to(project).as_posix(): c.sha(p.read_bytes())
                for p in sorted(project.rglob('*')) if p.is_file()
                and p.relative_to(project).parts[:2] != ('benchmark', 'out')}

    def prepare(self, project, factory, trusted, binding):
        self.events.append('prepare')
        self.assertEqual(binding['mode'], 'diagnostic')
        c.write_new(project / 'addons/hh_benchmark/benchmark_native.gd', self.source_bytes['tests/replay/benchmark_native.gd'])
        c.write_new(project / 'scenes/fixture.tscn', b'[gd_scene format=3]\n')
        c.write_new(project / 'scripts/fixture_actor.gd', b'extends Node3D\n')
        c.write_new(project / 'benchmark/input.json', binding)
        (project / 'benchmark/out').mkdir()
        return self.project_files(project)

    def stage_files(self, role, pid, exit_code=0):
        directory = self.root / role
        directory.mkdir(exist_ok=True)
        c.write_new(directory / 'process-start.json', {'pid': pid})
        c.write_new(directory / 'process-exit.json', {'pid': pid, 'exit_code': exit_code})
        value = {'actual_process_exit': {'pid': pid, 'exit_code': exit_code},
                 'wrapper_exit_code': exit_code, 'job': clean_job(), 'wrapper_process_handle': clean_handle()}
        c.write_new(directory / 'capture.json', value)
        return value

    def import_stage(self, root, context, project, executable, binary_hash, observer, errors):
        self.events.append('import')
        if self.import_error:
            raise self.import_error
        value = self.stage_files('import-host', 301)
        observer.close()
        return value

    def owner_factory(self, argv, **kwargs):
        self.events.append('editor_dispatch')
        test = self
        class Owner:
            def __init__(self):
                self.closed = False
                self.job = SimpleNamespace(snapshot=clean_job)
                self.process = SimpleNamespace(pid=403, returncode=test.editor_exit)
                self.threads = []
            def tick(self, *, stop=False):
                if stop:
                    raise c.DiagnosticError('BENCHMARK_STOPPED')
                return test.editor_exit
            def finish(self):
                test.events.append('finish_naturally')
                if test.finish_error:
                    raise test.finish_error
                self.close()
                return test.stage_files('editor-host', 402, test.editor_exit)
            def close(self):
                if not self.closed:
                    test.events.append('editor_close')
                    self.closed = True
            def process_handle_snapshot(self):
                return clean_handle()
        owner = Owner()
        self.owners.append(owner)
        return owner

    def open_probe(self, owner, executable):
        self.events.append('probe')
        probe = SimpleNamespace(pid=402, process_start='windows:1234', handle=7, close_uncertain=False)
        def close():
            self.events.append('probe_close')
            probe.handle = None
        probe.close = close
        self.probes.append(probe)
        return probe

    def collector(self, *_args):
        self.events.append('collect')
        return {'schema': 'gt06-s107-native-output-capture-v1', 'run_id': self.context['run_id'],
                'cycles': 40, 'groups': 10, 'sequence': 'ABBA', 'pid': 402,
                'formal_acceptance': False, 'eligible_for_dataset': False}

    def execute(self, **kwargs):
        return r.execute_child(self.root, self.context, self.campaign,
                    collector=kwargs.pop('collector', self.collector), **kwargs)

    def test_actual_prepare_and_fake_child_natural_lifecycle(self):
        result = self.execute()
        self.assertEqual(result['cycles'], 40)
        self.assertEqual(self.events[:5], ['prepare', 'import', 'editor_dispatch', 'probe', 'finish_naturally'])
        self.assertTrue(self.owners[0].closed)
        self.assertIsNone(self.probes[0].handle)
        sidecar = self.root / 'project/benchmark/s107-context.json'
        self.assertEqual(set(c.decode(c.read(sidecar))), set(r.supplemental_binding(self.context)))
        self.assertEqual(c.sha(c.read(self.root / 'project/addons/hh_benchmark/benchmark_native.gd')), c.sha(self.overlay))
        terminal = c.decode(c.read(self.root / 'child-terminal-cleanup.json'))
        self.assertIsNone(terminal['primary_error'])
        self.assertEqual(terminal['errors'], [])
        self.assertEqual(terminal['observations']['editor_target']['actual_exit']['exit_code'], 0)

    def test_wrong_runtime_source_prevents_import_and_editor(self):
        (self.repo / 'studio/tests/replay/benchmark_native.gd').write_bytes(b'wrongsource')
        with self.assertRaises(c.DiagnosticError) as raised:
            self.execute()
        self.assertEqual(raised.exception.code, 'S106_FILE_DRIFT')
        self.assertEqual(self.events, [])

    def test_wrong_overlay_pin_prevents_engine(self):
        (self.owned / 'overlay.gd').write_bytes(b'wrongoverlay')
        with self.assertRaises(c.DiagnosticError):
            self.execute()
        self.assertEqual(self.events, [])

    def test_bound_stop_before_import_dispatch(self):
        self.stopped = True
        with self.assertRaises(c.DiagnosticError) as raised:
            self.execute()
        self.assertEqual(raised.exception.code, 'BENCHMARK_STOPPED')
        self.assertEqual(self.events, [])

    def test_stop_after_import_prevents_editor_dispatch(self):
        original = self.import_stage
        def importing(*args):
            result = original(*args)
            self.stopped = True
            return result
        self.campaign._observed_import = importing
        with self.assertRaises(c.DiagnosticError) as raised:
            self.execute()
        self.assertEqual(raised.exception.code, 'BENCHMARK_STOPPED')
        self.assertNotIn('editor_dispatch', self.events)

    def test_import_abort_prevents_editor_and_retains_primary(self):
        self.import_error = c.DiagnosticError('S107_FAKE_IMPORT_ABORT')
        with self.assertRaises(c.DiagnosticError) as raised:
            self.execute()
        self.assertIs(raised.exception, self.import_error)
        self.assertNotIn('editor_dispatch', self.events)
        self.assertEqual(c.decode(c.read(self.root / 'child-failure.json'))['primary_error']['code'], self.import_error.code)

    def test_nonzero_editor_exit_never_calls_natural_finish_or_collector(self):
        self.editor_exit = 2
        with self.assertRaises(c.DiagnosticError) as raised:
            self.execute()
        self.assertEqual(raised.exception.code, 'S107_EDITOR_HELPER_EXIT')
        self.assertNotIn('finish_naturally', self.events)
        self.assertNotIn('collect', self.events)
        self.assertTrue(self.owners[0].closed)
        self.assertIsNone(self.probes[0].handle)

    def test_collector_failure_preserves_natural_exit_and_primary(self):
        primary = ValueError('reader rejected missing boundary')
        def collector(*_):
            raise primary
        with self.assertRaises(ValueError) as raised:
            self.execute(collector=collector)
        self.assertIs(raised.exception, primary)
        self.assertEqual(c.target_exit(self.root, 'editor-host')['actual_exit']['exit_code'], 0)
        self.assertTrue(self.owners[0].closed)

    def test_collector_primary_survives_terminal_and_failure_writer_errors(self):
        primary = c.DiagnosticError('S107_FAKE_READER_REJECT')
        def collector(*_):
            raise primary
        def writer(path, value):
            if path.name in ('child-terminal-cleanup.json', 'child-failure.json'):
                raise OSError('fake full disk')
            c.write_new(path, value)
        with self.assertRaises(c.DiagnosticError) as raised:
            self.execute(collector=collector, writer=writer)
        self.assertIs(raised.exception, primary)
        self.assertEqual(len(primary.s107_secondary_errors), 2)
        self.assertEqual(c.target_exit(self.root, 'editor-host')['actual_exit']['exit_code'], 0)

    def test_success_summary_requires_actual_exits_and_handle_cleanup(self):
        self.execute()
        self.stage_files('host-owner', 201)
        outcome = {'primary_error': None, 'cleanup_errors': [], 'helper_exit_observed_by_tick': 0}
        result = r.summarize(self.root, self.context, outcome, [])
        self.assertEqual(result['status'], 'CAPTURED', result)
        self.assertIsNone(result['outer_runner_actual_exit'])
        self.assertEqual(result['import_wrapper_native_handle_closure'], 'UNKNOWN_NOT_RECORDED')
        (self.root / 'host-owner/process-exit.json').unlink()
        result = r.summarize(self.root, self.context, outcome, [])
        self.assertEqual(result['status'], 'INCOMPLETE')

    def test_collector_rejects_missing_boundary_before_analysis(self):
        project, _initial = r.prepare(self.root, self.context, self.campaign)
        directory = self.root / 'editor-host'
        directory.mkdir()
        (directory / 'stdout.txt').write_bytes(b'no timing boundaries\n')
        (directory / 'stderr.txt').write_bytes(b'')
        analyzer = mock.Mock()
        with self.assertRaises(c.DiagnosticError) as raised:
            r.collect(self.root, self.context, self.project_files(project),
                      {'actual_process_exit': {'pid': 402, 'exit_code': 0}, 'wrapper_exit_code': 0},
                      self.campaign, analyzer=analyzer)
        self.assertEqual(raised.exception.code, 'S107_BOUNDARY_COUNT')
        analyzer.assert_not_called()

    def test_binding_separates_base_source_from_diagnostic_recipe(self):
        r.validate_context(self.context, self.root)
        self.assertEqual(r.native_binding(self.context)['source_closure_sha256'], c.SOURCE_SHA)
        self.assertNotEqual(self.context['diagnostic_closure_sha256'], c.SOURCE_SHA)
        self.assertEqual(r.supplemental_binding(self.context)['recipe_sha256'], self.helper.RECIPE_SHA256)
        changed = deepcopy(self.context)
        changed['source_closure_sha256'] = '0' * 64
        with self.assertRaises(c.DiagnosticError):
            r.validate_context(changed, self.root)


class ParentOwnerTests(unittest.TestCase):
    def test_capture_selection_excludes_private_and_cache_domains(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('context.json', 'host-owner/process-start.json',
                         'project/benchmark/out/preview-cost.json', 'localappdata/private.json',
                         'temp/private.json', 'project/.godot/private.json',
                         'host-owner/localappdata/private.json'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'{}')
            self.assertEqual({p.relative_to(root).as_posix() for p in r.selected_capture_paths(root)},
                             {'context.json', 'host-owner/process-start.json',
                              'project/benchmark/out/preview-cost.json'})

    def test_parent_stop_prevents_child_factory(self):
        context = {'run_id': 'gt06-s107-preview-stop', 'source_closure_sha256': c.SOURCE_SHA,
                   'campaign_sha256': 'a' * 64}
        factory = mock.Mock()
        result, _ = c.own_run(factory, Path('.'), context, lambda *_a, **_k: True, 180)
        factory.assert_not_called()
        self.assertEqual(result['primary_error']['code'], 'BENCHMARK_STOPPED')

    def test_parent_timeout_is_bounded_and_owner_closed(self):
        owner = SimpleNamespace(tick=lambda **_: None, close=mock.Mock())
        context = {'run_id': 'gt06-s107-preview-timeout', 'source_closure_sha256': c.SOURCE_SHA,
                   'campaign_sha256': 'a' * 64}
        times = iter([0, 181])
        def wait(*args):
            return c.wait_owner(*args, clock=lambda: next(times), sleep=lambda _: None)
        result, _ = c.own_run(lambda: owner, Path('.'), context, lambda *_a, **_k: False, 180, wait=wait)
        self.assertTrue(result['timed_out'])
        owner.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()

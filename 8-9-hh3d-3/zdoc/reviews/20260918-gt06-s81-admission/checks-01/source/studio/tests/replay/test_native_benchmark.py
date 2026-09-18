"""Negative checks for the native diagnostic evidence boundary; no engine."""
from configparser import ConfigParser
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from studio.tests.replay import run_native_benchmark as subject
from studio.tests.replay.test_benchmark_readiness import readiness_fixture


class ProjectConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.trusted = (subject.STUDIO / 'godot-addon/fixture_profile/project.godot').read_bytes()

    def test_generated_overrides_pin_exact_typed_cadence_without_other_settings(self):
        raw = subject.benchmark_project_config(self.trusted)
        config = ConfigParser(interpolation=None)
        config.read_string('[root]\n' + raw.decode('utf-8'))
        self.assertEqual(dict(config['editor_overrides']), {
            'interface/editor/display/update_continuously': 'false',
            'interface/editor/timers/low_processor_mode_sleep_usec': '6900',
            'interface/editor/timers/unfocused_low_processor_mode_sleep_usec': '6900',
            'run/output/max_lines': '100',
        })
        self.assertEqual(set(config.sections()), {
            'root', 'application', 'editor_overrides', 'editor_plugins', 'rendering', 'threading'})
        self.assertEqual(config['root']['config_version'], '5')
        self.assertEqual(config['threading']['worker_pool/max_threads'], '4')
        self.assertEqual(config['rendering']['renderer/rendering_method'], '"gl_compatibility"')
        self.assertNotIn(b'\r', raw)
        self.assertFalse(raw.startswith(b'\xef\xbb\xbf'))

    def test_config_serialization_is_deterministic_across_input_line_endings(self):
        lf = self.trusted.replace(b'\r\n', b'\n')
        expected = subject.benchmark_project_config(lf)
        self.assertEqual(subject.benchmark_project_config(lf.replace(b'\n', b'\r\n')), expected)
        self.assertEqual(subject.benchmark_project_config(b'; ignored comment\n' + lf), expected)
        self.assertEqual(subject.benchmark_project_config(lf), expected)

    def test_caller_supplied_overrides_are_rejected_instead_of_normalized(self):
        # Only the pinned trusted fixture is input. Preexisting keys, even valid
        # ones, cannot replace or silently select the benchmark configuration.
        for setting in (
            b'interface/editor/timers/unfocused_low_processor_mode_sleep_usec=100000',
            b'interface/editor/unfocused_low_processor_mode_sleep_usec=6900',
            b'interface/editor/timers/low_processor_mode_sleep_usec="6900"',
            b'interface/editor/display/update_continuously=0',
            b'interface/editor/timers/unfocused_low_processor_mode_sleep_usec=6900',
        ):
            with self.subTest(setting=setting):
                with self.assertRaisesRegex(subject.DiagnosticError, 'DIAGNOSTIC_PLUGIN_CONFIG'):
                    subject.benchmark_project_config(
                        self.trusted + b'\n[editor_overrides]\n' + setting + b'\n')


class TimingProofTests(unittest.TestCase):
    def setUp(self):
        self.timing = {
            'index': 0, 'generation_before': 1, 'generation_after': 2,
            'create': {'start_us': 10, 'end_us': 20},
            'undo': {'start_us': 30, 'end_us': 40},
            'save': {'start_us': 50, 'end_us': 70},
            'reload': {'start_us': 80, 'end_us': 100},
            'save_signal_mono_us': 60, 'reload_observed_process_frame': 10,
        }
        self.cycle = {'index': 0, 'latency_ms': {'create': .01, 'undo': .01, 'save': .02, 'reload': .02}}
        self.memory = {'process_frame': 15, 'settle_frames': 4}
        self.batch = {'started_mono_us': 1, 'ended_mono_us': 150}

    def validate(self):
        subject.validate_cycle_timing(self.timing, self.cycle, self.memory, self.batch)

    def test_retained_signal_and_reload_witnesses(self):
        self.validate()

    def test_missing_or_unknown_raw_fields_rejected(self):
        original = deepcopy(self.timing)
        for key in ('save_signal_mono_us', 'reload_observed_process_frame', 'save'):
            with self.subTest(missing=key):
                self.timing = deepcopy(original)
                del self.timing[key]
                with self.assertRaisesRegex(subject.DiagnosticError, 'TIMING_SHAPE'):
                    self.validate()
        self.timing = {**original, 'invented': True}
        with self.assertRaisesRegex(subject.DiagnosticError, 'TIMING_SHAPE'):
            self.validate()

    def test_save_signal_must_precede_reload_and_follow_save_call(self):
        for signal in (49, 71, 110, True, None):
            with self.subTest(signal=signal):
                self.timing['save_signal_mono_us'] = signal
                with self.assertRaisesRegex(subject.DiagnosticError, 'SAVE_SIGNAL'):
                    self.validate()

    def test_reload_must_precede_quiescent_frame_window(self):
        for frame in (0, 11, 15, 16, True):
            with self.subTest(frame=frame):
                self.timing['reload_observed_process_frame'] = frame
                with self.assertRaisesRegex(subject.DiagnosticError, 'RELOAD_FRAME'):
                    self.validate()

    def test_timings_must_be_inside_same_batch(self):
        self.batch['started_mono_us'] = 11
        with self.assertRaisesRegex(subject.DiagnosticError, 'STEP_CLOCK'):
            self.validate()
        self.batch['started_mono_us'] = 1
        self.batch['ended_mono_us'] = 99
        with self.assertRaisesRegex(subject.DiagnosticError, 'STEP_CLOCK'):
            self.validate()

    def test_forged_duration_and_generation_rejected(self):
        self.cycle['latency_ms']['save'] = .03
        with self.assertRaisesRegex(subject.DiagnosticError, 'LATENCY'):
            self.validate()
        self.cycle['latency_ms']['save'] = .02
        self.timing['generation_after'] = 3
        with self.assertRaisesRegex(subject.DiagnosticError, 'GENERATION'):
            self.validate()


class StartupProofTests(unittest.TestCase):
    """Synthetic diagnostic artifacts exercise the actual native validator."""
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='native-startup-unit-')
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name)
        (self.project / 'benchmark/out').mkdir(parents=True)
        (self.project / 'scenes').mkdir()
        scene = b'; synthetic initial scene\n'
        (self.project / subject.MUTABLE_SCENE).write_bytes(scene)
        self.scene_hash = subject.sha(scene)
        self.binding = {'schema_id': 'hh-studio.native-cycle-benchmark-run', 'schema_version': '1.2.0',
            'run_id': 'gt06-native-startup-unit', 'mode': 'diagnostic', 'source_closure_sha256': 'd' * 64,
            'profile_sha256': 'e' * 64, 'batch_barrier': 'diagnostic_none', 'batch_start': 'diagnostic_immediate'}
        names = ('addons/hh_studio/plugin.gd', 'addons/hh_studio/scene_commands.gd', 'addons/hh_studio/jcs_godot.gd',
                 'addons/hh_studio/plugin.cfg', 'scripts/fixture_actor.gd', 'addons/hh_benchmark/benchmark_native.gd',
                 'addons/hh_benchmark/plugin.cfg', 'project.godot', 'benchmark/input.json', 'benchmark/.gdignore')
        self.snapshot = {name: 'f' * 64 for name in names}
        self.snapshot[subject.MUTABLE_SCENE] = self.scene_hash
        sources = {'res://' + name: self.snapshot[name] for name in names}
        timing = {'index': 0, 'generation_before': 1, 'generation_after': 2,
            'create': {'start_us': 2001100, 'end_us': 2001200},
            'undo': {'start_us': 2001300, 'end_us': 2001400},
            'save': {'start_us': 2001500, 'end_us': 2001600},
            'reload': {'start_us': 2001700, 'end_us': 2001800},
            'save_signal_mono_us': 2001550, 'reload_observed_process_frame': 101}
        cycle = {'index': 0, 'root_before': 1000, 'root_after': 1001, 'before_sha256': 'a' * 64,
            'created_sha256': 'b' * 64, 'undone_sha256': 'a' * 64, 'reloaded_sha256': 'a' * 64,
            'saved_file_sha256': self.scene_hash, 'latency_ms': dict.fromkeys(('create', 'undo', 'save', 'reload'), .1),
            'effects': dict.fromkeys(('create', 'undo', 'save', 'reload'), 1), 'main_thread': True}
        self.batch = {'schema_id': 'hh-studio.native-cycle-batch', 'schema_version': '1.2.0',
            'run_id': self.binding['run_id'], 'pid': 202, 'index': 0, 'mode': 'diagnostic', 'warmup': False,
            'barrier': {'mode': 'diagnostic_none', 'required': False}, 'start_permit': None,
            'started_mono_us': 2001000, 'ended_mono_us': 3102000,
            'cycles': [cycle], 'raw_timings': [timing], 'memory': {
                'phase': 'post_batch_quiescent', 'settle_frames': 4, 'settle_us': 1100000,
                'monotonic_us': 3102000, 'process_frame': 106,
                'editor': {'objects': {'value': 500, 'unavailable_reason': None},
                           'resources': {'value': 6, 'unavailable_reason': None}}},
            'dropped_commands': 0, 'dropped_telemetry': 0}
        self.index = {'schema_id': 'hh-studio.native-cycle-benchmark', 'schema_version': '1.3.0',
            'input': self.binding, 'pid': 202, 'completed': True, 'benchmark_complete': False,
            'formal_acceptance': False, 'host_integrated': False, 'host_barriers': [], 'start_permits': [],
            'batch_order': 'diagnostic_native_cycle_only', 'host_start_timeout_us': 600000000,
            'host_barrier_timeout_us': 30000000, 'batches_completed': 1, 'cycles_per_batch': 1,
            'editor_hint': True, 'main_thread': True, 'display_server': 'Windows', 'engine': {'hash': 'pinned'},
            'source_files': sources, 'baseline_revision': 'sha256:' + 'a' * 64, 'started_mono_us': 1,
            'heartbeat_target_met': True, 'max_status_gap_ms': 1,
            'quiescence': {'minimum_frames': 4, 'minimum_us': 1100000},
            'startup_readiness': readiness_fixture(binding=self.binding, source_files=sources,
                                                   scene_file_sha256=self.scene_hash)}

    def validate(self):
        batch_raw = subject.encoded(self.batch)
        self.index['batches'] = [{'index': 0, 'file': 'batch-00.json', 'sha256': subject.sha(batch_raw), 'size_bytes': len(batch_raw)}]
        (self.project / 'benchmark/out/batch-00.json').write_bytes(batch_raw)
        (self.project / 'benchmark/out/index.json').write_bytes(subject.encoded(self.index))
        return subject.validate_native(self.project, self.binding, self.snapshot,
            {'actual_process_exit': {'pid': 202, 'exit_code': 0}},
            {'identity': {'pid': 202}, 'samples': [{'visible_window_handles': ['1']}], 'errors': []},
            {'source_commit': 'pinned'})

    def test_current_receipt_passes_and_saved_scene_bytes_do_not_replace_startup_hash(self):
        self.validate()
        canonical = b'; synthetic canonical save\n'
        (self.project / subject.MUTABLE_SCENE).write_bytes(canonical)
        self.batch['cycles'][0]['saved_file_sha256'] = subject.sha(canonical)
        self.validate()  # startup is still bound to the initial snapshot's hash

    def test_missing_old_or_late_startup_receipt_rejected(self):
        original = deepcopy(self.index)
        for change, code in (
            (lambda value: value.pop('startup_readiness'), 'STARTUP_READINESS_FIELDS'),
            (lambda value: value.update(schema_version='1.2.0'), 'DIAGNOSTIC_INDEX_BINDING'),
            (lambda value: value['startup_readiness']['settled'].update(mono_us=2001001), 'STARTUP_READINESS_AFTER_BATCH'),
            (lambda value: value['startup_readiness']['before'].update(scene_file_sha256='0' * 64), 'STARTUP_READINESS_SCENE_DRIFT')):
            with self.subTest(code=code):
                self.index = deepcopy(original)
                change(self.index)
                with self.assertRaisesRegex(subject.DiagnosticError, code):
                    self.validate()


if __name__ == '__main__':
    unittest.main(verbosity=2)

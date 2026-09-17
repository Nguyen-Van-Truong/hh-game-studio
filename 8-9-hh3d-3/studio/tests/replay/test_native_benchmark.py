"""Negative checks for the native diagnostic evidence boundary; no engine."""
from configparser import ConfigParser
from copy import deepcopy
import unittest

from studio.tests.replay import run_native_benchmark as subject


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


if __name__ == '__main__':
    unittest.main(verbosity=2)

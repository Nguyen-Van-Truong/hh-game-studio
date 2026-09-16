"""Mocked diagnostic capture rejection; these rows are never native evidence."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
spec = importlib.util.spec_from_file_location('s51_probe_capture_tests', Path(__file__).with_name('run_semantic_probe.py'))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class SemanticProbeCaptureTests(unittest.TestCase):
    def capture(self, *, pid=77, duplicate=False, warning=False, mutate=False, missing=False):
        with tempfile.TemporaryDirectory() as folder:
            case = Path(folder)
            binary = case / 'fake-executable'
            binary.write_bytes(b'not-an-executable')
            bundle = SimpleNamespace(files={'addons/hh_studio/plugin.cfg': b'script="plugin.gd"\n'})
            report = {'schema': 'hh-editor-semantic-probe-1', 'public_ack': False,
                'context_kind': 'live_editor', 'editor_hint': True, 'pid': pid,
                'engine_version': '4.7.2-stable (official)', 'snapshot': {'ok': True}}

            def run(argv, *, cwd, output, **kwargs):
                (output / 'editor-stdout.txt').write_bytes(b'')
                (output / 'editor-stderr.txt').write_bytes(b'')
                log = Path(argv[argv.index('--log-file') + 1])
                line = 'HH_EDITOR_SEMANTIC ' + json.dumps(report) + '\n'
                if not missing:
                    log.write_text(('WARNING: invalid\n' if warning else '') + line * (2 if duplicate else 1),
                                   encoding='utf-8')
                if mutate: (cwd / 'addons/hh_studio/plugin.cfg').write_bytes(b'changed')
                return {'exit_code': 0, 'wrapper_exit_code': 0, 'tree_verified': True, 'timed_out': False,
                        'target_pid': 77, 'stdout': 'editor-stdout.txt', 'stderr': 'editor-stderr.txt'}

            runner = SimpleNamespace(run_process=run, _isolated_user_env=lambda path: {})
            return probe.editor_observation(bundle, case, runner, binary)

    def test_pinned_gui_explicit_log_can_supply_report_with_empty_stdout(self):
        row = self.capture()
        self.assertTrue(row['passed'])
        self.assertEqual(row['observation_source'], 'editor-engine.log')

    def test_wrong_process_pid_is_not_this_editor_observation(self):
        self.assertFalse(self.capture(pid=78)['passed'])

    def test_duplicate_or_missing_marker_never_passes(self):
        self.assertFalse(self.capture(duplicate=True)['passed'])
        self.assertFalse(self.capture(missing=True)['passed'])

    def test_engine_log_warning_cannot_hide_behind_empty_stderr(self):
        self.assertFalse(self.capture(warning=True)['passed'])

    def test_changed_executed_plugin_config_rejected(self):
        self.assertFalse(self.capture(mutate=True)['passed'])


if __name__ == '__main__': unittest.main(verbosity=2)

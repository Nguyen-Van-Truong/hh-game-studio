"""Admission lifecycle regression without engines, Docker, or native APIs."""
from contextlib import contextmanager, ExitStack
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('refresh_under_test', Path(__file__).with_name('run_refresh.py'))
refresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refresh)


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.output = self.root / 'group'; self.output.mkdir()
        self.lanes = self.output / 'lanes'; self.lanes.mkdir()
        (self.output / 'driver-freeze.json').write_text('{}')
        self.release = []

        @contextmanager
        def window(*args, safe_to_release, **kwargs):
            try:
                yield
            finally:
                self.release.append(safe_to_release())

        self.stack.enter_context(patch.object(refresh, 'OUTPUT', self.output))
        self.stack.enter_context(patch.object(refresh.helper, 'OUTPUT', self.lanes))
        self.stack.enter_context(patch.object(refresh, 'measurement_window', window))
        self.stack.enter_context(patch.object(refresh, 'verify_envelope', return_value={}))
        self.stack.enter_context(patch.object(refresh.helper, 'unused_ids'))
        self.stack.enter_context(patch.object(refresh.campaign, 'environment_preflight', return_value={'pass': True}))
        self.require = self.stack.enter_context(patch.object(refresh.campaign, 'require_environment_preflight'))
        self.observe = self.stack.enter_context(patch.object(refresh.campaign, 'observe_pair_launch'))
        self.stack.enter_context(patch.object(refresh.campaign, 'source_files', return_value={'x.py': 'a' * 64}))
        self.stack.enter_context(patch.object(refresh.campaign, 'verify_sources'))
        self.run = self.stack.enter_context(patch.object(refresh.helper, 'run', return_value=0))

    def error(self, code):
        return refresh.helper.RefreshError(code)

    def test_resource_defer_preserves_freeze_and_allows_one_later_launch(self):
        original = (self.output / 'driver-freeze.json').read_bytes()
        self.require.side_effect = self.error('CAMPAIGN_PREFLIGHT_RESOURCE_LIMIT')
        self.assertEqual(refresh.run_once(), 75)
        self.run.assert_not_called(); self.observe.assert_not_called()
        first = self.output / 'admissions/0001/result.json'
        before = first.read_bytes()
        self.assertEqual(json.loads(before)['state'], 'DEFERRED')
        self.assertFalse((self.output / 'terminal.json').exists())
        self.assertFalse((self.lanes / 'run-started.json').exists())
        self.assertTrue(self.release[-1])
        self.require.side_effect = None
        self.assertEqual(refresh.run_once(), 0)
        self.assertEqual(self.run.call_count, 1)
        self.assertEqual(first.read_bytes(), before)
        self.assertEqual((self.output / 'driver-freeze.json').read_bytes(), original)
        self.assertTrue((self.output / 'admissions/0002/admitted.json').exists())
        with self.assertRaisesRegex(refresh.helper.RefreshError, 'GROUP_TERMINAL'):
            refresh.run_once()
        self.assertEqual(self.run.call_count, 1)

    def test_cpu_minute_failure_does_not_launch_or_mark_group_terminal(self):
        self.observe.side_effect = self.error('CAMPAIGN_PREFLIGHT_CPU_BUSY')
        self.assertEqual(refresh.run_once(), 75)
        self.run.assert_not_called()
        self.assertFalse((self.output / 'terminal.json').exists())

    def test_native_failure_preserves_guard_and_cannot_be_restarted(self):
        self.run.side_effect = self.error('OUTER_ACTUAL_EXIT')
        self.assertEqual(refresh.run_once(), 1)
        self.assertFalse(self.release[-1])
        terminal = json.loads((self.output / 'terminal.json').read_bytes())
        self.assertTrue(terminal['engine_launch_attempted'])
        releases = list(self.release)
        with self.assertRaisesRegex(refresh.helper.RefreshError, 'GROUP_TERMINAL'):
            refresh.run_once()
        self.assertEqual(self.run.call_count, 1)
        self.assertEqual(self.release, releases)

    def test_incomplete_started_group_cannot_launch_again(self):
        (self.lanes / 'run-started.json').write_text('{}')
        with self.assertRaisesRegex(refresh.helper.RefreshError, 'RUN_ALREADY_STARTED'):
            refresh.run_once()
        self.run.assert_not_called()

    def test_source_failure_is_not_resource_deferral(self):
        self.observe.side_effect = self.error('CAMPAIGN_SOURCE_CHANGED')
        self.assertEqual(refresh.run_once(), 1)
        self.run.assert_not_called()
        self.assertTrue((self.output / 'terminal.json').exists())
        self.assertTrue(self.release[-1])


if __name__ == '__main__':
    unittest.main()

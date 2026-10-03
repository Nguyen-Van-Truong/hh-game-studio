"""F06 admission/ownership regressions; no engine or Docker execution."""
from contextlib import ExitStack
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('managed_under_test', Path(__file__).with_name('run_managed.py'))
managed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(managed)
from studio.tests.replay.measure_window import measurement_window
from studio.tests.replay.benchmark_job import BenchmarkJobError


class ManagedGuardTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.marker = self.root / 'measure-window.lock'
        self.stack.enter_context(patch.object(managed, 'default_path', return_value=self.marker))
        # Admission tests must not depend on whether real, terminal native IDs
        # already exist on the workstation. Keep their raw namespace disposable.
        self.stack.enter_context(patch.object(managed, 'STUDIO', self.root / 'studio'))

    def test_lazy_profile_verification_cannot_expand_driver_domain(self):
        before = managed.driver_sources()
        self.assertIn('studio/godot-addon/script_profile.py', before)
        managed.helper.native.configuration('0.0')
        managed.helper.native.configuration('3.0')
        self.assertEqual(managed.driver_sources(), before)

    def test_existing_measurement_marker_is_never_removed(self):
        with measurement_window('formal', 'test', path=self.marker):
            before = self.marker.read_bytes()
            with self.assertRaisesRegex(managed.helper.native.ReplayError, 'MANAGED_MEASUREMENT_ACTIVE'):
                with managed.functional_guard():
                    self.fail('must not enter')
            self.assertEqual(self.marker.read_bytes(), before)

    def test_functional_guard_excludes_formal_without_blocking_validator_marker_check(self):
        with managed.functional_guard():
            self.assertFalse(self.marker.exists())
            with self.assertRaises(BenchmarkJobError):
                with measurement_window('formal', 'test', path=self.marker):
                    self.fail('must not enter')
        with measurement_window('after', 'test', path=self.marker):
            self.assertTrue(self.marker.exists())

    def test_second_functional_owner_cannot_enter(self):
        with managed.functional_guard():
            with self.assertRaises(OSError):
                with managed.functional_guard():
                    self.fail('must not enter')

    def test_existing_lane_rejected_before_touching_guard(self):
        output = self.root / 'managed'; (output / 'repair').mkdir(parents=True)
        with patch.object(managed.helper, 'OUTPUT', output), \
             patch.object(managed, 'functional_guard') as guard, \
             patch.object(managed.helper, 'run') as run:
            with self.assertRaisesRegex(managed.helper.native.ReplayError, 'MANAGED_NO_RETRY'):
                managed.run_lane('repair')
            guard.assert_not_called(); run.assert_not_called()

    def test_missing_verified_repair_prevents_replay_admission(self):
        output = self.root / 'managed'; output.mkdir()
        with patch.object(managed.helper, 'OUTPUT', output), \
             patch.object(managed, 'verify_freeze'), \
             patch.object(managed.helper, 'verify', side_effect=ValueError('unverified repair')) as verify, \
             patch.object(managed.campaign, 'environment_preflight') as preflight, \
             patch.object(managed.helper, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'unverified repair'):
                managed.run_lane('replay')
            verify.assert_called_once_with('repair')
            preflight.assert_not_called(); run.assert_not_called()

    def test_existing_raw_id_rejected_before_touching_guard(self):
        raw = managed.STUDIO / '.local/reviews' / managed.helper.REPAIR
        raw.mkdir(parents=True)
        with patch.object(managed.helper, 'OUTPUT', self.root / 'unused'), \
             patch.object(managed, 'functional_guard') as guard, \
             patch.object(managed.helper, 'run') as run:
            with self.assertRaisesRegex(managed.helper.native.ReplayError, 'MANAGED_NO_RETRY'):
                managed.run_lane('repair')
            guard.assert_not_called(); run.assert_not_called()

    def test_driver_change_during_native_work_prevents_success_publication(self):
        output = self.root / 'packet'; output.mkdir()
        (output / 'driver-freeze.json').write_text('{}')
        native = output / 'managed'; native.mkdir()
        with patch.object(managed, 'OUTPUT', output), \
             patch.object(managed.helper, 'OUTPUT', native), \
             patch.object(managed, 'verify_freeze', side_effect=[{}, ValueError('driver changed')]), \
             patch.object(managed.campaign, 'environment_preflight', return_value={}), \
             patch.object(managed.campaign, 'require_environment_preflight'), \
             patch.object(managed.campaign, 'source_files', return_value={}), \
             patch.object(managed.campaign, 'observe_pair_launch'), \
             patch.object(managed.helper, 'run', return_value={'actual_target': {}}) as run:
            with self.assertRaisesRegex(ValueError, 'driver changed'):
                managed.run_lane('repair')
            run.assert_called_once_with('repair')
            self.assertTrue((output / 'admission-repair/0001/admitted.json').exists())
            self.assertFalse((output / 'admission-repair/0001/result.json').exists())


if __name__ == '__main__':
    unittest.main()

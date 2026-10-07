"""Engine-free checks for the private adapter native diagnostic helpers."""
import argparse
import copy
import unittest
from unittest import mock

from studio.tests.godot import linux_probe_fixtures as fixtures
from studio.tests.godot import run_gameplay_adapter_probe as probe
from studio.tests.godot import run_linux_probe as linux_probe


class GameplayAdapterProbeTests(unittest.TestCase):
    def test_variants_are_distinct_and_keep_the_existing_oracle(self):
        original = copy.deepcopy(fixtures.FIXTURES[probe.FIXTURE])
        original.update(scene=fixtures.SCENE, project='config_version=5\n')
        before = copy.deepcopy(original)
        first, second = probe.source_cases(original)
        self.assertEqual(original, before)
        self.assertEqual(first, original)
        self.assertEqual(first['dependency_files'], second['dependency_files'])
        self.assertEqual(first['expect'], second['expect'])
        a, b = linux_probe.case_files(first), linux_probe.case_files(second)
        self.assertEqual(set(a), set(b))
        self.assertEqual([name for name in a if a[name] != b[name]], ['scripts/fixture_actor.gd'])

    def test_native_exits_are_copied_and_bool_or_conflicting_alias_rejected(self):
        value = {'command_host': {'exit_code': 0, 'timed_out': False},
                 'container_state': {'ExitCode': 0, 'Running': False}, 'docker_wait_exit': 0}
        self.assertEqual(probe.native_exit_observation(value),
                         {'command_host_exit': 0, 'container_exit': 0,
                          'docker_wait_exit': 0, 'timed_out': False})
        for group, key in (('command_host', 'exit_code'), ('container_state', 'ExitCode'),
                           (None, 'docker_wait_exit')):
            broken = copy.deepcopy(value)
            (broken[group] if group else broken)[key] = False
            with self.subTest(group=group), self.assertRaisesRegex(RuntimeError, 'ADAPTER_NATIVE_EXIT_INVALID'):
                probe.native_exit_observation(broken)
        with self.assertRaisesRegex(RuntimeError, 'ADAPTER_NATIVE_EXIT_ALIASES'):
            probe.native_exit_observation({**value, 'commandhost': {'exit_code': 1}})

    def test_contender_is_bounded_and_requires_the_typed_busy_error(self):
        class Busy(ValueError):
            code = 'GAMEPLAY_OWNER_BUSY'

        def busy():
            raise Busy('do not record arbitrary exception text')

        row = probe.busy_contender(busy)
        self.assertEqual(row['error_code'], 'GAMEPLAY_OWNER_BUSY')
        self.assertTrue(row['source_job_overlap_observed'])
        self.assertFalse(row['native_overlap_observed'])
        self.assertEqual(row['authority'], 0)
        self.assertNotIn('do not record', str(row))
        with self.assertRaisesRegex(RuntimeError, 'ADAPTER_CONTENDER_NOT_BUSY'):
            probe.busy_contender(lambda: None)

    def test_run_id_rejects_traversal_before_publication_admission(self):
        for run_id in ('../outside', 'o2-adapter-../outside', 'o2-publication-wrong-prefix'):
            with self.subTest(run_id=run_id), mock.patch.object(probe.publication, 'dry_run') as check:
                with self.assertRaisesRegex(RuntimeError, 'ADAPTER_RUN_ID_INVALID'):
                    probe.dry_run(argparse.Namespace(run_id=run_id))
                check.assert_not_called()


if __name__ == '__main__':
    unittest.main()

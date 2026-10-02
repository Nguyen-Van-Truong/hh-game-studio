import unittest
from unittest.mock import patch

from tests.godot import run_gameplay_failure_probe as probe
from tests.godot import linux_probe_fixtures


class GameplayFailureProbeMappingTests(unittest.TestCase):
    def test_auth05_cases_use_hostile_gameplay_fixtures(self):
        expected = {
            'boundary': ('gameplay_source_boundary', 'boundary_observation'),
            'spawn': ('gameplay_source_spawn', 'spawn_observation'),
            'busy': ('gameplay_source_busy', 'watchdog'),
            'wall': ('gameplay_source_wall_wait', 'watchdog'),
        }
        for name, (fixture_name, expectation) in expected.items():
            with self.subTest(name=name):
                self.assertTrue(probe.is_auth05_failure(name))
                self.assertEqual(probe.failure_case_name(name), fixture_name)
                self.assertEqual(linux_probe_fixtures.FIXTURES[fixture_name]['expect'], expectation)

    def test_cpu_busy_and_wall_wait_have_distinct_loops_under_the_same_caps(self):
        busy = linux_probe_fixtures.FIXTURES[probe.failure_case_name('busy')]
        wall = linux_probe_fixtures.FIXTURES[probe.failure_case_name('wall')]
        prefix = ('extends Node3D\nfunc _ready() -> void:\n'
                  '\tprint("HH_PROBE_BUSY_ENTERED")\n\twhile true:\n')
        self.assertEqual(busy['script'], prefix + '\t\tpass\n')
        self.assertEqual(wall['script'], prefix + '\t\tOS.delay_msec(1000)\n')
        for fixture in (busy, wall):
            self.assertEqual(fixture['mode'], 'gameplay-source')
            self.assertEqual(fixture['timeout'], 20)
            self.assertEqual(fixture['expect'], 'watchdog')

    def test_wall_cli_routes_to_auth05_before_any_native_or_output_work(self):
        argv = ['run_gameplay_failure_probe.py', '--run-id', 'o2-auth05-native-wall-unit',
                '--failure-fixture', 'wall']
        with patch.object(probe.sys, 'argv', argv), patch.object(
                probe, 'idle_window', side_effect=RuntimeError('STOP_BEFORE_IO')) as idle:
            with self.assertRaisesRegex(RuntimeError, '^STOP_BEFORE_IO$'):
                probe.main()
            idle.assert_called_once_with()

    def test_auth03_cases_remain_secondary_parse_rejections(self):
        for name in ('syntax', 'type'):
            with self.subTest(name=name):
                self.assertFalse(probe.is_auth05_failure(name))
                fixture = linux_probe_fixtures.FIXTURES[probe.failure_case_name(name)]
                self.assertEqual(fixture['expect'], 'engine_rejection')
                self.assertEqual(fixture['mode'], 'gameplay-source')

    def test_unknown_case_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'UNKNOWN_FAILURE_FIXTURE'):
            probe.failure_case_name('unknown')


if __name__ == '__main__':
    unittest.main()

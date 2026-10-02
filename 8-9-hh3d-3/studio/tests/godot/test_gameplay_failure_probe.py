import unittest

from tests.godot import run_gameplay_failure_probe as probe
from tests.godot import linux_probe_fixtures


class GameplayFailureProbeMappingTests(unittest.TestCase):
    def test_auth05_cases_use_hostile_gameplay_fixtures(self):
        expected = {
            'boundary': ('gameplay_source_boundary', 'boundary_observation'),
            'spawn': ('gameplay_source_spawn', 'spawn_observation'),
            'busy': ('gameplay_source_busy', 'watchdog'),
        }
        for name, (fixture_name, expectation) in expected.items():
            with self.subTest(name=name):
                self.assertTrue(probe.is_auth05_failure(name))
                self.assertEqual(probe.failure_case_name(name), fixture_name)
                self.assertEqual(linux_probe_fixtures.FIXTURES[fixture_name]['expect'], expectation)

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

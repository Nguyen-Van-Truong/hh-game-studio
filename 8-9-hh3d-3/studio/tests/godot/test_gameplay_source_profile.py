"""The gameplay-source admission profile is closed before Docker is touched."""
import importlib.util
from pathlib import Path
import unittest

STUDIO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('gameplay_source_profile_tests',
                                              STUDIO / 'godot-addon/gameplay_source_profile.py')
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)

VALID = b'''extends Node3D
var ticks: int = 0
func _physics_process(_delta: float) -> void:
\tticks += 1
'''


class GameplaySourceProfileTests(unittest.TestCase):
    def test_valid_typed_source_is_diagnostic_only(self):
        result = profile.validate_source(VALID)
        self.assertEqual(result['profile'], profile.PROFILE)
        self.assertEqual(result['authority'], 0)
        self.assertFalse(result['syntax_and_types_verified'])
        self.assertFalse(result['dependency_closure_verified'])
        self.assertFalse(result['sandbox_acceptance'])

    def test_hostile_source_is_admitted_for_os_observation_not_trusted(self):
        source = b'extends Node3D\nfunc _ready() -> void:\n\tOS.execute("x")\n'
        result = profile.validate_source(source)
        self.assertEqual(result['authority'], 0)
        self.assertFalse(result['syntax_and_types_verified'])

    def test_rejects_bad_bytes_and_limits(self):
        for source in (b'extends Node3D\x00\n', b'\xef\xbb\xbfextends Node3D\n',
                       b'x' * (profile.MAX_BYTES + 1)):
            with self.assertRaises(profile.GameplaySourceError):
                profile.validate_source(source)

    def test_driver_has_fixed_parse_import_play_order(self):
        driver = profile.driver()
        self.assertLess(driver.index('"parse"'), driver.index('"import"'))
        self.assertLess(driver.index('"import"'), driver.index('"play"'))
        self.assertIn('/harness/gameplay_sandbox.py', driver)


if __name__ == '__main__':
    unittest.main()

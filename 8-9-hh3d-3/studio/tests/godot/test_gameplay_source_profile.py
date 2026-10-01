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
DEPENDENCY = b'''extends "res://scripts/base.gd"
func _ready() -> void:
\tpass
'''
BASE = b'''extends Node3D
'''
GLB = b'glTF' + (2).to_bytes(4, 'little') + (12).to_bytes(4, 'little')
PNG = b'\x89PNG\r\n\x1a\nfixture'


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

    def test_source_bundle_is_bounded_and_hash_bound_but_not_closure_proof(self):
        result = profile.validate_source_bundle(
            {'scripts/main.gd': DEPENDENCY, 'scripts/base.gd': BASE},
            entrypoint='scripts/main.gd')
        self.assertTrue(result['dependency_inventory_verified'])
        self.assertFalse(result['dependency_closure_verified'])
        self.assertFalse(result['syntax_and_types_verified'])
        self.assertEqual(set(result['files']), {'scripts/base.gd', 'scripts/main.gd'})

    def test_source_bundle_does_not_infer_missing_or_unreferenced_files(self):
        result = profile.validate_source_bundle(
            {'scripts/main.gd': DEPENDENCY}, entrypoint='scripts/main.gd')
        self.assertFalse(result['dependency_closure_verified'])
        result = profile.validate_source_bundle(
            {'scripts/main.gd': VALID, 'scripts/unused.gd': BASE}, entrypoint='scripts/main.gd')
        self.assertEqual(len(result['files']), 2)

    def test_dependency_closure_rejects_traversal_and_non_bytes(self):
        with self.assertRaisesRegex(profile.GameplaySourceError, 'GAMEPLAY_DEPENDENCY_SHAPE'):
            profile.validate_source_bundle({'../outside.gd': BASE}, entrypoint='../outside.gd')
        with self.assertRaisesRegex(profile.GameplaySourceError, 'GAMEPLAY_DEPENDENCY_FILE'):
            profile.validate_source_bundle({'scripts/main.gd': 'text'}, entrypoint='scripts/main.gd')

    def test_source_bundle_rejects_res_alias_and_dot_segments(self):
        for name in ('res://scripts/main.gd', 'scripts/./main.gd', 'scripts/a/../main.gd',
                     'scripts/CON.gd', 'scripts/main.gd:stream', 'scripts/main.gd\x00'):
            with self.assertRaisesRegex(profile.GameplaySourceError,
                                        'GAMEPLAY_DEPENDENCY_SHAPE|GAMEPLAY_DEPENDENCY_FILE'):
                profile.validate_source_bundle({name: BASE}, entrypoint=name)

    def test_source_bundle_rejects_cross_platform_case_aliases(self):
        with self.assertRaisesRegex(profile.GameplaySourceError, 'GAMEPLAY_DEPENDENCY_ALIAS'):
            profile.validate_source_bundle(
                {'scripts/Main.gd': BASE, 'scripts/main.gd': BASE},
                entrypoint='scripts/Main.gd')

    def test_allowlisted_binary_assets_are_hash_bound_separately(self):
        result = profile.validate_source_bundle(
            {'scripts/main.gd': BASE, 'scenes/main.tscn': b'[gd_scene format=3]\n',
             'assets/avatar.glb': GLB, 'assets/sprite_sheet.png': PNG},
            entrypoint='scripts/main.gd')
        self.assertEqual(set(result['assets']), {'assets/avatar.glb', 'assets/sprite_sheet.png'})
        self.assertEqual(result['assets']['assets/avatar.glb']['size_bytes'], len(GLB))
        self.assertFalse(result['assets']['assets/avatar.glb']['asset_import_verified'])

    def test_binary_asset_caps_signatures_and_aliases_fail_closed(self):
        base = {'scripts/main.gd': BASE, 'scenes/main.tscn': b'[gd_scene format=3]\n'}
        cases = (
            ({**base, 'assets/avatar.glb': b'bad'}, 'GAMEPLAY_ASSET_GLB'),
            ({**base, 'assets/sprite_sheet.png': b'bad'}, 'GAMEPLAY_ASSET_PNG'),
            ({**base, 'assets/avatar.glb': GLB, 'assets/Avatar.glb': GLB}, 'GAMEPLAY_DEPENDENCY_FILE|GAMEPLAY_DEPENDENCY_ALIAS'),
            ({**base, 'assets/avatar.glb': b'glTF' + (2).to_bytes(4, 'little') + (13).to_bytes(4, 'little')}, 'GAMEPLAY_ASSET_GLB'),
            ({**base, 'assets/not-allowed.bin': GLB}, 'GAMEPLAY_ASSET_FILE|GAMEPLAY_DEPENDENCY_FILE'),
        )
        for files, code in cases:
            with self.subTest(code=code):
                with self.assertRaisesRegex(profile.GameplaySourceError, code):
                    profile.validate_source_bundle(files, entrypoint='scripts/main.gd')

    def test_asset_total_is_separate_from_source_cap(self):
        base = {'scripts/main.gd': BASE, 'scenes/main.tscn': b'[gd_scene format=3]\n'}
        oversized = b'glTF' + (2).to_bytes(4, 'little') + (profile.MAX_ASSET_BYTES + 12).to_bytes(4, 'little')
        oversized += b'x' * (profile.MAX_ASSET_BYTES - 12)
        with self.assertRaisesRegex(profile.GameplaySourceError, 'GAMEPLAY_ASSET_SIZE|GAMEPLAY_ASSET_GLB'):
            profile.validate_source_bundle({**base, 'assets/avatar.glb': oversized}, entrypoint='scripts/main.gd')


if __name__ == '__main__':
    unittest.main()

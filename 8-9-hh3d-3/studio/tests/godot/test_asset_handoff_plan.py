import copy
import importlib.util
from pathlib import Path
import sys
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
SPEC = importlib.util.spec_from_file_location("o2_asset_handoff", STUDIO / "tests/godot/asset_handoff_plan.py")
asset = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = asset
SPEC.loader.exec_module(asset)

PROFILE_SPEC = importlib.util.spec_from_file_location(
    "o2_gameplay_source_profile", STUDIO / "godot-addon/gameplay_source_profile.py")
profile = importlib.util.module_from_spec(PROFILE_SPEC)
sys.modules[PROFILE_SPEC.name] = profile
PROFILE_SPEC.loader.exec_module(profile)


class AssetHandoffPlanTests(unittest.TestCase):
    def test_build_and_validate_is_deterministic(self):
        first = asset.build_plan()
        second = asset.build_plan()
        self.assertEqual(first, second)
        self.assertEqual(asset.validate_plan(first), first)
        self.assertEqual([row["format"] for row in first["assets"]], ["GLB", "PNG"])

    def test_paths_match_the_existing_gameplay_source_adapter(self):
        value = asset.build_plan()
        self.assertEqual(set(asset.ADAPTER_ASSET_PATHS), set(profile._ASSET_FILES))
        self.assertEqual(
            {row["path"] for row in value["assets"]}, set(profile._ASSET_FILES))
        changed = copy.deepcopy(value)
        changed["assets"][1]["path"] = "assets/arena_sprite_atlas.png"
        changed["canonical_sha256"] = asset._sha(
            {key: changed[key] for key in changed if key != "canonical_sha256"})
        with self.assertRaises(ValueError) as raised:
            asset.validate_plan(changed)
        self.assertEqual(raised.exception.args[0], "ASSET_ADAPTER_PATH")

    def test_glb_requires_geometry_material_uv_and_readback(self):
        value = asset.build_plan()
        row = value["assets"][0]
        self.assertEqual(row["pipeline_steps"][:3], ["geometry", "material", "uv"])
        self.assertFalse(row["asset_import_verified"])
        for key in ("geometry", "material", "uv"):
            changed = copy.deepcopy(value)
            changed["assets"][0]["pipeline_profiles"].pop(key)
            changed["canonical_sha256"] = "0" * 64
            with self.assertRaises(ValueError) as raised:
                asset.validate_plan(changed)
            self.assertIn(raised.exception.args[0], {"GLB_PROFILE_KEYS", "PLAN_HASH"})

    def test_sprite_is_separate_from_glb_and_unknown_fields_reject(self):
        value = asset.build_plan()
        sprite = value["assets"][1]
        self.assertEqual(sprite["pipeline_steps"], ["pose_render", "sprite_sheet", "godot_texture_readback"])
        changed = copy.deepcopy(value)
        changed["assets"][1]["import_readback_required"] = False
        with self.assertRaises(ValueError) as raised:
            asset.validate_plan(changed)
        self.assertEqual(raised.exception.args[0], "ASSET_AUTHORITY")
        changed = copy.deepcopy(value)
        changed["assets"][0]["unexpected"] = True
        with self.assertRaises(ValueError) as raised:
            asset.validate_plan(changed)
        self.assertEqual(raised.exception.args[0], "ASSET_ROW_SHAPE")

    def test_tampered_hash_path_and_verification_reject(self):
        for field, replacement, code in (("sha256", "f" * 64, "PLAN_HASH"),
                                          ("path", "../avatar.glb", "ASSET_PATH"),
                                          ("asset_import_verified", True, "ASSET_AUTHORITY")):
            changed = copy.deepcopy(asset.build_plan())
            changed["assets"][0][field] = replacement
            with self.assertRaises(ValueError) as raised:
                asset.validate_plan(changed)
            self.assertEqual(raised.exception.args[0], code)


if __name__ == "__main__":
    unittest.main()




"""Host tests for vfx preset ops. Scene apply is mocked, so Godot stays off."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio.gamekit import common as C
from studio.gamekit import scene as S
from studio.gamekit import vfx
from studio.gamekit.selftests import effects_smoke


def _invoke(argv: list[str]) -> tuple[int, dict]:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    vfx.register(sub)
    args = parser.parse_args(argv)
    try:
        result = args.func(args)
    except C.GamekitError as exc:
        return 2, exc.to_json()
    return (0 if result.get("ok", False) else 1), result


def _particle(ops: list[dict]) -> dict:
    for op in ops:
        if op.get("op") == "node.create" and op.get("type") in ("GPUParticles2D", "GPUParticles3D"):
            return op
    raise AssertionError("no particle node")


class VfxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self._old_state = os.environ.get("HH_GAMEKIT_STATE")
        os.environ["HH_GAMEKIT_STATE"] = str(self.root / "state")
        game = self.root / "game"
        game.mkdir()
        (game / "project.godot").write_text("config_version=5\n", encoding="utf-8")
        self.project = C.register_project(game, "game")
        self.catalog = S.load_catalog()

    def tearDown(self) -> None:
        if self._old_state is None:
            os.environ.pop("HH_GAMEKIT_STATE", None)
        else:
            os.environ["HH_GAMEKIT_STATE"] = self._old_state
        self.tmp.cleanup()

    def test_smoke_module_is_callable_without_running(self) -> None:
        self.assertTrue(callable(effects_smoke.run))

    def test_presets_cover_both_dimensions_and_document_retrigger(self) -> None:
        listed = vfx.presets()
        self.assertTrue(listed["ok"])
        self.assertTrue(listed["seed_supported"])
        self.assertIn("use_fixed_seed", listed["seed_reason"])
        self.assertEqual(listed["seed_limits"], {"min": 0, "max": 4294967295, "property": "seed"})
        ids = [row["id"] for row in listed["presets"]]
        self.assertEqual(ids, list(vfx.PRESET_IDS))
        for dimension in ("2d", "3d"):
            kinds = {row["kind"] for row in listed["presets"] if row["dimension"] == dimension}
            self.assertIn("sparks", kinds)
            self.assertIn("impact", kinds)
            self.assertIn("smoke", kinds)
            self.assertIn("burst", kinds)
        self.assertEqual(listed["retrigger"]["method"], "restart")
        self.assertIn("PreviewCamera", " ".join(listed["retrigger"]["steps"]))
        self.assertIn("2d", listed["camera_limits"])
        self.assertIn("3d", listed["camera_limits"])
        self.assertIn("Compatibility", listed["renderer"])

    def test_ops_match_the_scene_schema(self) -> None:
        for preset in vfx.PRESET_IDS:
            built = vfx.plan(preset)
            self.assertEqual(S.validate_ops(self.project, built["ops"], self.catalog), built["ops"])
            self.assertIn(built["create"]["root_type"], self.catalog["classes"])
            particle = _particle(built["ops"])
            props = particle["props"]
            self.assertEqual(props["process_material"]["$type"], "ParticleProcessMaterial")
            self.assertGreaterEqual(props["amount"], 8)
            self.assertLessEqual(props["amount"], 96)
            self.assertGreaterEqual(props["lifetime"], 0.15)
            self.assertLessEqual(props["lifetime"], 2.5)
            self.assertGreaterEqual(props["explosiveness"], 0.0)
            self.assertLessEqual(props["explosiveness"], 1.0)
            self.assertEqual(props["emitting"], True)
            self.assertNotIn("seed", props)
            self.assertNotIn("use_fixed_seed", props)
            self.assertIsNone(built["seed"])
            self.assertFalse(built["use_fixed_seed"])
            for op in built["ops"]:
                self.assertNotEqual(op.get("op"), "instance.add")
                self.assertNotIn("scene", op)
            self._assert_no_external_res(built["ops"])
            if preset.endswith("_2d"):
                self.assertEqual(particle["type"], "GPUParticles2D")
                self.assertEqual(props["texture"]["$type"], "GradientTexture2D")
                self.assertEqual(props["texture"]["props"]["width"], 32)
                self.assertNotIn("draw_pass_1", props)
            else:
                self.assertEqual(particle["type"], "GPUParticles3D")
                draw = props["draw_pass_1"]
                self.assertEqual(draw["$type"], "QuadMesh")
                material = draw["props"]["material"]
                self.assertEqual(material["$type"], "StandardMaterial3D")
                self.assertEqual(material["props"]["shading_mode"], "Unshaded")
                self.assertEqual(material["props"]["billboard_mode"], "Particle Billboard")
                self.assertLessEqual(max(draw["props"]["size"]), 0.5)
            camera = built["ops"][0]
            self.assertEqual(camera["name"], "PreviewCamera")
            camera_key = "enabled" if preset.endswith("_2d") else "current"
            self.assertTrue(camera["props"][camera_key])

    def test_overrides_and_ranges(self) -> None:
        built = vfx.plan("sparks_2d", count=16, intensity=0.25, color="#FF00AA", lifetime=0.5, seed=0x12345678)
        props = _particle(built["ops"])["props"]
        self.assertEqual(props["amount"], 16)
        self.assertEqual(props["explosiveness"], 0.25)
        self.assertEqual(props["lifetime"], 0.5)
        self.assertEqual(props["process_material"]["props"]["color"], "#ff00aa")
        self.assertTrue(props["use_fixed_seed"])
        self.assertEqual(props["seed"], 0x12345678)
        self.assertEqual(built["seed"], 0x12345678)
        self.assertTrue(built["use_fixed_seed"])
        self.assertEqual(vfx.plan("sparks_2d", count=8)["count"], 8)
        self.assertEqual(vfx.plan("sparks_2d", count=96)["count"], 96)
        self.assertEqual(vfx.plan("sparks_2d", intensity=0)["intensity"], 0.0)
        self.assertEqual(vfx.plan("sparks_2d", intensity=1)["intensity"], 1.0)
        for kwargs in (
            {"count": 4},
            {"count": 97},
            {"count": True},
            {"intensity": -0.01},
            {"intensity": 1.01},
            {"color": "#fff"},
            {"color": "red"},
            {"lifetime": 0.8},
            {"lifetime": 0.05},
            {"seed": -1},
            {"seed": 0x100000000},
            {"seed": True},
        ):
            with self.assertRaises(C.GamekitError) as cm:
                vfx.plan("sparks_2d", **kwargs)
            self.assertEqual(cm.exception.code, "VALIDATION_FAILED", kwargs)
        with self.assertRaises(C.GamekitError) as unknown:
            vfx.plan("not_a_preset")
        self.assertEqual(unknown.exception.code, "BAD_REQUEST")
        smoke = _particle(vfx.plan("smoke_3d")["ops"])["props"]["draw_pass_1"]["props"]["material"]["props"]
        sparks = _particle(vfx.plan("sparks_3d")["ops"])["props"]["draw_pass_1"]["props"]["material"]["props"]
        self.assertEqual(smoke["transparency"], "Alpha")
        self.assertNotIn("transparency", sparks)

    def test_create_delegates_retry_and_does_not_write_tscn(self) -> None:
        seen: list[str] = []

        def fake_apply(project, scene, ops, command_id, **kwargs):
            seen.append(json.dumps({"scene": scene, "ops": ops, "create": kwargs.get("create"), "id": command_id}, sort_keys=True))
            return {"ok": True, "status": "COMMITTED", "kind": "scene.apply", "command_id": command_id, "replayed": len(seen) > 1}

        with patch.object(C, "atomic_write_bytes", side_effect=AssertionError("vfx wrote bytes")), patch.object(S, "apply", side_effect=fake_apply):
            first = vfx.create(self.project, "res://effects/sparks_2d.tscn", "sparks_2d", "vfx.sparks.1", count=24)
            second = vfx.create(self.project, "res://effects/sparks_2d.tscn", "sparks_2d", "vfx.sparks.1", count=24)
        self.assertEqual(seen[0], seen[1])
        self.assertTrue(first["ok"])
        self.assertFalse(first["replayed"])
        self.assertTrue(second["replayed"])
        self.assertEqual(second["vfx"]["preset"], "sparks_2d")
        self.assertEqual(second["vfx"]["count"], 24)
        self.assertTrue(second["vfx"]["seed_supported"])
        self.assertIsNone(second["vfx"]["seed"])
        self.assertFalse(second["vfx"]["use_fixed_seed"])
        self.assertEqual(second["vfx"]["instantiate"]["scene"], "res://effects/sparks_2d.tscn")
        self.assertEqual(second["vfx"]["instantiate"]["op"], "instance.add")
        self.assertIn("restart", second["vfx"]["retrigger"]["method"])
        with patch.object(S, "apply", side_effect=C.GamekitError("CONFLICT", "command_id was already used")):
            with self.assertRaises(C.GamekitError) as conflict:
                vfx.create(self.project, "res://effects/sparks_2d.tscn", "sparks_2d", "vfx.other.1")
        self.assertEqual(conflict.exception.code, "CONFLICT")

    def test_create_rejects_before_apply(self) -> None:
        with patch.object(S, "apply", side_effect=AssertionError("apply should not run")) as apply:
            for bad_seed in (-1, 0x100000000, True):
                with self.assertRaises(C.GamekitError) as seed:
                    vfx.create(self.project, "res://effects/sparks_2d.tscn", "sparks_2d", "vfx.seed.1", seed=bad_seed)
                self.assertEqual(seed.exception.code, "VALIDATION_FAILED")
            with self.assertRaises(C.GamekitError) as count:
                vfx.create(self.project, "res://effects/sparks_2d.tscn", "sparks_2d", "vfx.count.1", count=1000)
            self.assertEqual(count.exception.code, "VALIDATION_FAILED")
            with self.assertRaises(C.GamekitError) as scene:
                vfx.create(self.project, "res://effects/sparks_2d.txt", "sparks_2d", "vfx.path.1")
            self.assertEqual(scene.exception.code, "BAD_PATH")
            with self.assertRaises(C.GamekitError) as command:
                vfx.create(self.project, "res://effects/sparks_2d.tscn", "sparks_2d", "x")
            self.assertEqual(command.exception.code, "BAD_REQUEST")
            apply.assert_not_called()

    def test_cli_presets_and_create(self) -> None:
        code, listed = _invoke(["vfx", "presets"])
        self.assertEqual(code, 0)
        self.assertIn("smoke_2d", [row["id"] for row in listed["presets"]])
        self.assertIn("burst_3d", [row["id"] for row in listed["presets"]])
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command", required=True)
        vfx.register(sub)
        parsed = parser.parse_args([
            "vfx", "create", "--project", "game", "--scene", "res://effects/sparks_2d.tscn",
            "--preset", "sparks_2d", "--command-id", "vfx.sparks.1", "--seed", "1",
        ])
        self.assertEqual(parsed.seed, 1)
        with patch.object(C, "get_project", return_value=self.project), patch.object(
            S, "apply", return_value={"ok": True, "status": "COMMITTED", "replayed": True, "kind": "scene.apply"}
        ) as apply:
            code, created = _invoke([
                "vfx", "create", "--project", "game", "--scene", "res://effects/impact_3d.tscn",
                "--preset", "impact_3d", "--command-id", "vfx.impact.1", "--count", "12", "--seed", "9",
            ])
        self.assertEqual(code, 0, created)
        self.assertTrue(created["replayed"])
        self.assertEqual(created["vfx"]["count"], 12)
        self.assertEqual(created["vfx"]["dimension"], "3d")
        self.assertEqual(created["vfx"]["seed"], 9)
        self.assertTrue(created["vfx"]["use_fixed_seed"])
        apply.assert_called_once()
        with patch.object(C, "get_project", return_value=self.project), patch.object(S, "apply") as apply:
            code, bad = _invoke([
                "vfx", "create", "--project", "game", "--scene", "res://effects/impact_3d.tscn",
                "--preset", "impact_3d", "--command-id", "vfx.impact.2", "--count", "4",
            ])
        self.assertEqual(code, 2)
        self.assertEqual(bad["error"], "VALIDATION_FAILED")
        apply.assert_not_called()

    def test_no_camera_and_doctor_lock_sync(self) -> None:
        from studio.gamekit import doctor
        built_2d = vfx.plan("sparks_2d", no_camera=True)
        built_3d = vfx.plan("impact_3d", no_camera=True)
        for built in (built_2d, built_3d):
            names = [op.get("name") for op in built["ops"] if op.get("op") == "node.create"]
            groups = [op.get("group") for op in built["ops"] if op.get("op") == "group.add"]
            self.assertNotIn("PreviewCamera", names)
            self.assertNotIn("hh_vfx_preview_camera", groups)
        rep = doctor.run_doctor(verify_hashes=False)
        self.assertEqual(rep["kind"], "doctor")
        self.assertEqual(rep["pin"], {"godot": C.GODOT_VERSION, "blender": C.BLENDER_VERSION})

    def _assert_no_external_res(self, value: object) -> None:
        if isinstance(value, dict):
            self.assertNotIn("$res", value)
            for child in value.values():
                self._assert_no_external_res(child)
        elif isinstance(value, list):
            for child in value:
                self._assert_no_external_res(child)

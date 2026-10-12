"""Fast unit tests (no Blender) for gamekit W8 recipe validation."""

from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio.gamekit import blender_recipe as B
from studio.gamekit import common as C


def _recipe(steps: list, name: str = "Demo") -> dict:
    return {"schema": B.SCHEMA, "name": name, "steps": steps}


class RecipeValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "box.obj").write_text("o Box\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _code(self, data: object, code: str) -> None:
        with self.assertRaises(C.GamekitError) as caught:
            B.validate_recipe(data, self.dir)
        self.assertEqual(caught.exception.code, code, caught.exception.detail)

    def test_examples_and_every_op_shape(self) -> None:
        examples = C.GAMEKIT_DIR / "blender" / "examples"
        for name in ("crate.json", "walker.json"):
            path = examples / name
            data = C.read_json(path)
            self.assertIs(B.validate_recipe(data, path.parent), data)
        steps = [
            {"op": "clear"},
            {"op": "primitive", "type": "cube", "name": "Box", "size": 1, "location": [0, 0, 0],
             "rotation_deg": [0, 0, 90], "scale": [1, 1, 1]},
            {"op": "primitive", "type": "uv_sphere", "name": "Ball", "radius": 0.2, "segments": 8},
            {"op": "primitive", "type": "ico_sphere", "name": "Ico", "radius": 0.2, "segments": 2},
            {"op": "primitive", "type": "cylinder", "name": "Cyl", "radius": 0.1, "depth": 1, "segments": 8},
            {"op": "primitive", "type": "cone", "name": "Cone", "radius": 0.1, "depth": 1, "segments": 8},
            {"op": "primitive", "type": "torus", "name": "Tor", "radius": 0.4, "size": 0.1, "segments": 8},
            {"op": "primitive", "type": "plane", "name": "Floor", "size": 2},
            {"op": "primitive", "type": "monkey", "name": "Suz"},
            {"op": "modifier", "object": "Box", "type": "bevel", "params": {"width": 0.05, "segments": 2, "affect": "EDGES"}},
            {"op": "modifier", "object": "Box", "type": "subsurf", "params": {"levels": 1, "subdivision_type": "CATMULL_CLARK"}},
            {"op": "modifier", "object": "Box", "type": "mirror", "params": {"use_x": True, "use_clip": True}},
            {"op": "modifier", "object": "Box", "type": "array", "params": {"count": 2, "relative_offset": [1.2, 0, 0]}},
            {"op": "modifier", "object": "Box", "type": "solidify", "params": {"thickness": 0.02, "offset": 0}},
            {"op": "modifier", "object": "Box", "type": "decimate", "params": {"ratio": 0.5, "decimate_type": "COLLAPSE"}},
            {"op": "modifier", "object": "Box", "type": "weld", "params": {"merge_threshold": 0.001, "mode": "ALL"}},
            {"op": "modifier", "object": "Box", "type": "triangulate",
             "params": {"quad_method": "SHORTEST_DIAGONAL", "ngon_method": "BEAUTY", "min_vertices": 4}},
            {"op": "apply_modifiers", "object": "Box"},
            {"op": "material", "object": "Box", "name": "Wood", "base_color": [0.4, 0.2, 0.1, 1],
             "metallic": 0, "roughness": 0.5, "emission": [0, 0, 0], "emission_strength": 0},
            {"op": "transform", "object": "Box", "location": [1, 0, 0], "rotation_deg": [0, 45, 0], "scale": [2, 2, 2]},
            {"op": "join", "objects": ["Box", "Ball"], "name": "Joined"},
            {"op": "parent", "child": "Cone", "parent": "Joined"},
            {"op": "import", "path": "box.obj", "format": "obj"},
            {"op": "import", "path": "meshes/hero.glb", "format": "gltf"},
            {"op": "armature", "name": "Rig", "bones": [
                {"name": "Root", "head": [0, 0, 0], "tail": [0, 0, 1]},
                {"name": "Spine", "head": [0, 0, 1], "tail": [0, 0, 2], "parent": "Root"},
            ]},
            {"op": "skin", "mesh": "Joined", "armature": "Rig"},
            {"op": "keyframes", "object": "Rig", "bone": "Spine", "action": "Walk", "fps": 24,
             "interpolation": "LINEAR", "keys": [
                 {"frame": 1, "rotation_deg": [0, 0, 0]},
                 {"frame": 12, "location": [0, 0, 0.1], "scale": [1, 1, 1]},
             ]},
            {"op": "render_sprites", "target": "Joined", "action": "Walk", "directions": 4,
             "frames": [1, 9, 4], "size": [32, 32], "ortho_scale": 2, "elevation_deg": 90,
             "engine": "workbench", "transparent": True, "out": "walk.png"},
            {"op": "export_gltf", "out": "out.glb", "objects": ["Joined", "Rig"], "animations": True},
            {"op": "save_blend", "out": "out.blend"},
        ]
        (self.dir / "meshes").mkdir()
        (self.dir / "meshes" / "hero.glb").write_bytes(b"glTF")
        self.assertEqual(B.validate_recipe(_recipe(steps), self.dir)["name"], "Demo")
        self.assertEqual(len(B.validate_recipe(_recipe([{"op": "clear"}] * B.MAX_STEPS), self.dir)["steps"]), B.MAX_STEPS)

    def test_rejection_table(self) -> None:
        cube = {"op": "primitive", "type": "cube", "name": "Box", "size": 1}
        cases = [
            ("not an object", [], "BAD_REQUEST"),
            ("bad schema", {"schema": "nope", "name": "Demo", "steps": [cube]}, "BAD_REQUEST"),
            ("unknown field", {**_recipe([cube]), "extra": 1}, "VALIDATION_FAILED"),
            ("empty steps", _recipe([]), "VALIDATION_FAILED"),
            ("steps not a list", {"schema": B.SCHEMA, "name": "Demo", "steps": {}}, "VALIDATION_FAILED"),
            ("too many steps", _recipe([{"op": "clear"}] * (B.MAX_STEPS + 1)), "VALIDATION_FAILED"),
            ("unknown op", _recipe([{"op": "explode"}]), "VALIDATION_FAILED"),
            ("bad name", _recipe([cube], name="has space"), "VALIDATION_FAILED"),
            ("nan size", _recipe([{"op": "primitive", "type": "cube", "name": "Box", "size": float("nan")}]), "VALIDATION_FAILED"),
            ("inf size", _recipe([{"op": "primitive", "type": "cube", "name": "Box", "size": float("inf")}]), "VALIDATION_FAILED"),
            ("size zero", _recipe([{"op": "primitive", "type": "cube", "name": "Box", "size": 0}]), "VALIDATION_FAILED"),
            ("size huge", _recipe([{"op": "primitive", "type": "cube", "name": "Box", "size": 10000}]), "VALIDATION_FAILED"),
            ("bool as size", _recipe([{"op": "primitive", "type": "cube", "name": "Box", "size": True}]), "VALIDATION_FAILED"),
            ("cube radius", _recipe([{**cube, "radius": 1}]), "VALIDATION_FAILED"),
            ("bad primitive", _recipe([{"op": "primitive", "type": "teapot", "name": "Box"}]), "VALIDATION_FAILED"),
            ("segments float", _recipe([{"op": "primitive", "type": "uv_sphere", "name": "Ball", "radius": 1, "segments": 8.0}]), "VALIDATION_FAILED"),
            ("ico segments", _recipe([{"op": "primitive", "type": "ico_sphere", "name": "Ico", "radius": 1, "segments": 8}]), "VALIDATION_FAILED"),
            ("scale zero", _recipe([{"op": "transform", "object": "Box", "scale": [1, 0, 1]}]), "VALIDATION_FAILED"),
            ("unknown modifier", _recipe([{"op": "modifier", "object": "Box", "type": "wave"}]), "VALIDATION_FAILED"),
            ("unknown param", _recipe([{"op": "modifier", "object": "Box", "type": "bevel", "params": {"width": 0.1, "nope": 1}}]), "VALIDATION_FAILED"),
            ("nan param", _recipe([{"op": "modifier", "object": "Box", "type": "bevel", "params": {"width": float("nan")}}]), "VALIDATION_FAILED"),
            ("bevel segments high", _recipe([{"op": "modifier", "object": "Box", "type": "bevel", "params": {"segments": 12}}]), "VALIDATION_FAILED"),
            ("subsurf levels", _recipe([{"op": "modifier", "object": "Box", "type": "subsurf", "params": {"levels": 6}}]), "VALIDATION_FAILED"),
            ("bad enum", _recipe([{"op": "modifier", "object": "Box", "type": "weld", "params": {"mode": "MAYBE"}}]), "VALIDATION_FAILED"),
            ("join one", _recipe([{"op": "join", "objects": ["Box"], "name": "J"}]), "VALIDATION_FAILED"),
            ("parent self", _recipe([{"op": "parent", "child": "Box", "parent": "Box"}]), "VALIDATION_FAILED"),
            ("import dotdot", _recipe([{"op": "import", "path": "../box.obj", "format": "obj"}]), "BAD_PATH"),
            ("import nested dotdot", _recipe([{"op": "import", "path": "sub/../../box.obj", "format": "obj"}]), "BAD_PATH"),
            ("import absolute", _recipe([{"op": "import", "path": str(self.dir / "box.obj"), "format": "obj"}]), "BAD_PATH"),
            ("import missing", _recipe([{"op": "import", "path": "missing.obj", "format": "obj"}]), "NOT_FOUND"),
            ("import bad format", _recipe([{"op": "import", "path": "box.obj", "format": "dae"}]), "VALIDATION_FAILED"),
            ("bone cycle", _recipe([{"op": "armature", "name": "Rig", "bones": [
                {"name": "A", "head": [0, 0, 0], "tail": [0, 0, 1], "parent": "B"},
                {"name": "B", "head": [0, 0, 1], "tail": [0, 0, 2], "parent": "A"},
            ]}]), "VALIDATION_FAILED"),
            ("zero bone", _recipe([{"op": "armature", "name": "Rig", "bones": [
                {"name": "A", "head": [0, 0, 0], "tail": [0, 0, 0]},
            ]}]), "VALIDATION_FAILED"),
            ("unknown parent", _recipe([{"op": "armature", "name": "Rig", "bones": [
                {"name": "A", "head": [0, 0, 0], "tail": [0, 0, 1], "parent": "Nope"},
            ]}]), "VALIDATION_FAILED"),
            ("key without channel", _recipe([{"op": "keyframes", "object": "Rig", "action": "Walk", "fps": 24,
                                              "interpolation": "LINEAR", "keys": [{"frame": 1}]}]), "VALIDATION_FAILED"),
            ("bad interpolation", _recipe([{"op": "keyframes", "object": "Rig", "action": "Walk", "fps": 24,
                                            "interpolation": "SMOOTH", "keys": [{"frame": 1, "location": [0, 0, 0]}]}]), "VALIDATION_FAILED"),
            ("directions 0", _recipe([{"op": "render_sprites", "target": "Box", "directions": 0, "frames": [1, 1, 1],
                                       "size": [8, 8], "ortho_scale": 1, "elevation_deg": 0, "out": "s.png"}]), "VALIDATION_FAILED"),
            ("directions 17", _recipe([{"op": "render_sprites", "target": "Box", "directions": 17, "frames": [1, 1, 1],
                                        "size": [8, 8], "ortho_scale": 1, "elevation_deg": 0, "out": "s.png"}]), "VALIDATION_FAILED"),
            ("pixel 513", _recipe([{"op": "render_sprites", "target": "Box", "directions": 1, "frames": [1, 1, 1],
                                    "size": [513, 8], "ortho_scale": 1, "elevation_deg": 0, "out": "s.png"}]), "VALIDATION_FAILED"),
            ("elevation 91", _recipe([{"op": "render_sprites", "target": "Box", "directions": 1, "frames": [1, 1, 1],
                                       "size": [8, 8], "ortho_scale": 1, "elevation_deg": 91, "out": "s.png"}]), "VALIDATION_FAILED"),
            ("bad engine", _recipe([{"op": "render_sprites", "target": "Box", "directions": 1, "frames": [1, 1, 1],
                                     "size": [8, 8], "ortho_scale": 1, "elevation_deg": 0, "engine": "octane", "out": "s.png"}]), "VALIDATION_FAILED"),
            ("out slash", _recipe([{"op": "export_gltf", "out": "dir/crate.glb"}]), "BAD_PATH"),
            ("out dotdot", _recipe([{"op": "export_gltf", "out": "../crate.glb"}]), "BAD_PATH"),
            ("out wrong suffix", _recipe([{"op": "export_gltf", "out": "crate.txt"}]), "VALIDATION_FAILED"),
            ("reserved sidecar", _recipe([{"op": "render_sprites", "target": "Box", "directions": 1, "frames": [1, 1, 1],
                                           "size": [8, 8], "ortho_scale": 1, "elevation_deg": 0, "out": "manifest.png"}]), "VALIDATION_FAILED"),
            ("duplicate out", _recipe([
                {"op": "export_gltf", "out": "a.glb"},
                {"op": "export_gltf", "out": "a.glb"},
            ]), "VALIDATION_FAILED"),
            ("animations not bool", _recipe([{"op": "export_gltf", "out": "a.glb", "animations": 1}]), "VALIDATION_FAILED"),
            ("too many sprite cells", _recipe([{"op": "render_sprites", "target": "Box", "directions": 16, "frames": [0, 31, 1],
                                                 "size": [8, 8], "ortho_scale": 1, "elevation_deg": 0, "out": "s.png"}]), "VALIDATION_FAILED"),
        ]
        for label, data, code in cases:
            with self.subTest(label):
                self._code(data, code)

    def test_run_rejects_before_blender(self) -> None:
        path = self.dir / "bad.json"
        path.write_text(json.dumps(_recipe([{"op": "explode"}])), encoding="utf-8")
        called: list[int] = []
        original = C.run_blender
        C.run_blender = lambda *args, **kwargs: called.append(1)
        try:
            with self.assertRaises(C.GamekitError) as caught:
                B.run_recipe(path, self.dir / "out")
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
            dotdot = self.dir / "dot.json"
            dotdot.write_text(json.dumps(_recipe([{"op": "import", "path": "../x.obj", "format": "obj"}])), encoding="utf-8")
            with self.assertRaises(C.GamekitError) as caught:
                B.run_recipe(dotdot, self.dir / "out")
            self.assertEqual(caught.exception.code, "BAD_PATH")
            nan = self.dir / "nan.json"
            nan.write_text(
                '{"schema":"hh-blender-recipe-1","name":"bad","steps":[{"op":"primitive","type":"cube","name":"Box","size":NaN}]}',
                encoding="utf-8",
            )
            with self.assertRaises(C.GamekitError) as caught:
                B.run_recipe(nan, self.dir / "out")
            self.assertEqual(caught.exception.code, "BAD_REQUEST")
            self.assertEqual(called, [])
            overflow = self.dir / "overflow.json"
            overflow.write_text(
                '{"schema":"hh-blender-recipe-1","name":"bad","steps":[{"op":"primitive","type":"cube","name":"Box","size":1e309}]}',
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                B._parse_float("1e309")
            self.assertEqual(B._parse_float("1.25"), 1.25)
            with self.assertRaises(C.GamekitError) as caught:
                B.load_recipe(overflow)
            self.assertEqual(caught.exception.code, "BAD_REQUEST")
            self.assertIn("non-finite", caught.exception.detail)
            finite = self.dir / "finite.json"
            finite.write_text(json.dumps(_recipe([{"op": "primitive", "type": "cube", "name": "Box", "size": 1.5}])), encoding="utf-8")
            _loaded, data = B.load_recipe(finite)
            self.assertEqual(data["steps"][0]["size"], 1.5)
        finally:
            C.run_blender = original

    def test_cli_validate_does_not_need_blender(self) -> None:
        path = self.dir / "ok.json"
        path.write_text(json.dumps(_recipe([{"op": "clear"}])), encoding="utf-8")
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command", required=True)
        B.register(sub)
        args = parser.parse_args(["blender", "validate", str(path)])
        result = args.func(args)
        self.assertEqual(result, {"ok": True, "name": "Demo", "steps": 1})
        run_args = parser.parse_args(["blender", "run", str(path), "--out-dir", str(self.dir / "out"),
                                      "--out", str(self.dir / "receipt.json"), "--timeout", "12"])
        self.assertEqual(run_args.timeout, 12.0)
        self.assertEqual(Path(run_args.out), self.dir / "receipt.json")
        self.assertTrue(callable(run_args.func))

    def test_receipt_cannot_overwrite_recipe_assets_or_project(self) -> None:
        recipe = self.dir / "recipe.json"
        data = _recipe([
            {"op": "render_sprites", "target": "Box", "directions": 1, "frames": [1, 1, 1],
             "size": [8, 8], "ortho_scale": 1, "elevation_deg": 0, "out": "sprite.png"},
        ])
        recipe.write_text(json.dumps(data), encoding="utf-8")
        out = self.dir / "assets"
        project = self.dir / "project"
        project.mkdir()
        (project / "project.godot").write_text("config_version=5\n", encoding="utf-8")
        with patch.object(C, "run_blender") as native:
            for path in (recipe, out / "manifest.json", out / "sprite.json", project / "receipt.json"):
                with self.subTest(path=str(path)), self.assertRaises(C.GamekitError):
                    B.run_recipe(recipe, out, receipt_out=path)
            native.assert_not_called()
        self.assertFalse(out.exists())
        self.assertEqual(json.loads(recipe.read_text(encoding="utf-8")), data)


if __name__ == "__main__":
    unittest.main()

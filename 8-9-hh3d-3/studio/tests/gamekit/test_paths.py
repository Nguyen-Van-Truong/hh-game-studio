"""Windows junction and editor-query checks for gamekit host paths."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from studio.gamekit import asset as A
from studio.gamekit import blender_recipe as B
from studio.gamekit import common as C
from studio.gamekit import inputmap as IM
from studio.gamekit import perf as P
from studio.gamekit import play as Play
from studio.gamekit import scene as Scene
from studio.gamekit import shot
from studio.gamekit import vcheck

_EDITOR_DETAIL = (
    "could not check for an open Godot editor; close it and retry, or pass --allow-open-editor"
)


def _make_junction(link: Path, target: Path) -> None:
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        check=True,
        capture_output=True,
    )


def _load_runner():
    path = Path(__file__).resolve().parents[2] / "gamekit" / "blender" / "recipe_runner.py"
    previous = sys.dont_write_bytecode
    spec = importlib.util.spec_from_file_location("hh_recipe_runner_paths", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.dont_write_bytecode = previous
    return module


class PathSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows junction checks")
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.target = self.root / "target"
        self.other = self.root / "other"
        self.target.mkdir()
        self.other.mkdir()
        (self.other / "note.txt").write_bytes(b"marker")
        self.link = self.root / "link"
        self._junctions = [self.link]
        _make_junction(self.link, self.other)
        self._old_state = os.environ.get("HH_GAMEKIT_STATE")
        os.environ["HH_GAMEKIT_STATE"] = str(self.root / "state")

    def _make_dangling(self, link: Path, target: Path) -> None:
        target.mkdir()
        _make_junction(link, target)
        self._junctions.append(link)
        shutil.rmtree(target)

    def tearDown(self) -> None:
        for link in getattr(self, "_junctions", []):
            try:
                os.rmdir(link)
            except OSError:
                pass
        if hasattr(self, "_old_state"):
            if self._old_state is None:
                os.environ.pop("HH_GAMEKIT_STATE", None)
            else:
                os.environ["HH_GAMEKIT_STATE"] = self._old_state
        if hasattr(self, "tmp"):
            self.tmp.cleanup()

    def test_helper_accepts_a_normal_temp_path(self) -> None:
        plain = self.target / "plain.txt"
        plain.write_bytes(b"abc")
        got = C.refuse_unsafe_host_path(plain, what="probe")
        self.assertEqual(os.path.normcase(str(got)), os.path.normcase(str(plain.resolve())))
        project = C.Project("game", self.target)
        outside = self.root / "out.json"
        accepted = C.refuse_unsafe_host_path(
            outside, what="--out", project=project, must_be_outside_project=True,
        )
        self.assertEqual(os.path.normcase(str(accepted)), os.path.normcase(str(outside.resolve())))

    def test_helper_refuses_junction_and_ancestor(self) -> None:
        with self.assertRaises(C.GamekitError) as direct:
            C.refuse_unsafe_host_path(self.link, what="probe")
        self.assertEqual(direct.exception.code, "FORBIDDEN_PATH")
        with self.assertRaises(C.GamekitError) as child:
            C.refuse_unsafe_host_path(self.link / "note.txt", what="probe")
        self.assertEqual(child.exception.code, "FORBIDDEN_PATH")
        with self.assertRaises(C.GamekitError) as nested:
            C.refuse_unsafe_host_path(self.link / "missing" / "file.txt", what="probe")
        self.assertEqual(nested.exception.code, "FORBIDDEN_PATH")

    def test_helper_refuses_private_raw_name_and_patched_local_dir(self) -> None:
        missing = self.target / "private.raw"
        with self.assertRaises(C.GamekitError) as named:
            C.refuse_unsafe_host_path(missing, what="probe")
        self.assertEqual(named.exception.code, "FORBIDDEN_PATH")
        self.assertFalse(missing.exists())
        studio = self.root / "fakestudio"
        secret = studio / ".local" / "secret.txt"
        secret.parent.mkdir(parents=True)
        secret.write_bytes(b"x")
        with mock.patch.object(C, "STUDIO_DIR", studio):
            with self.assertRaises(C.GamekitError) as local:
                C.refuse_unsafe_host_path(secret, what="probe")
        self.assertEqual(local.exception.code, "FORBIDDEN_PATH")
        project = C.Project("game", self.target)
        with self.assertRaises(C.GamekitError) as inside:
            C.refuse_unsafe_host_path(
                self.target / "in.json", what="--out", project=project, must_be_outside_project=True,
            )
        self.assertEqual(inside.exception.code, "FORBIDDEN_PATH")

    def test_asset_source_through_junction_is_refused(self) -> None:
        with self.assertRaises(C.GamekitError) as cm:
            A._refuse_source(self.link / "note.txt")
        self.assertEqual(cm.exception.code, "FORBIDDEN_PATH")
        plain = self.target / "ok.txt"
        plain.write_bytes(b"ok")
        self.assertTrue(A._refuse_source(plain).is_file())

    def test_prepare_out_dir_refuses_junction(self) -> None:
        before = sorted(path.name for path in self.other.iterdir())
        with self.assertRaises(C.GamekitError) as cm:
            B._prepare_out_dir(self.link)
        self.assertEqual(cm.exception.code, "FORBIDDEN_PATH")
        with self.assertRaises(C.GamekitError) as nested:
            B._prepare_out_dir(self.link / "nested-out")
        self.assertEqual(nested.exception.code, "FORBIDDEN_PATH")
        self.assertEqual(sorted(path.name for path in self.other.iterdir()), before)
        self.assertFalse((self.other / "nested-out").exists())
        made = B._prepare_out_dir(self.root / "real-out")
        self.assertTrue(made.is_dir())

    def test_runner_out_file_and_non_finite_json(self) -> None:
        runner = _load_runner()
        with self.assertRaises(runner.RecipeFailure):
            runner._out_file(self.link, "crate.glb")
        with self.assertRaises(runner.RecipeFailure):
            runner._out_file(self.link / "sub", "crate.glb")
        self.assertFalse((self.other / "crate.glb").exists())
        self.assertFalse((self.other / "sub").exists())
        normal = self.root / "blend-out"
        normal.mkdir()
        self.assertEqual(runner._out_file(normal, "crate.glb"), normal / "crate.glb")
        with self.assertRaises(runner.RecipeFailure):
            json.loads('{"size": NaN}', parse_constant=runner._reject_non_finite)
        with self.assertRaises(runner.RecipeFailure):
            json.loads('{"size": Infinity}', parse_constant=runner._reject_non_finite)
        with self.assertRaises(runner.RecipeFailure):
            json.loads('{"size": -Infinity}', parse_constant=runner._reject_non_finite)
        self.assertEqual(json.loads('{"size": 1}', parse_constant=runner._reject_non_finite), {"size": 1})
        with self.assertRaises(runner.RecipeFailure):
            json.loads('{"size": 1e309}', parse_float=runner._parse_float)
        with self.assertRaises(runner.RecipeFailure):
            runner._parse_float("1e309")
        self.assertEqual(runner._parse_float("1.25"), 1.25)

    def test_output_helpers_refuse_junction_and_keep_inside_code(self) -> None:
        project = C.Project("game", self.target)
        with self.assertRaises(C.GamekitError) as play_cm:
            Play.play(project, out=str(self.link / "play.json"), frames=1)
        self.assertEqual(play_cm.exception.code, "FORBIDDEN_PATH")
        with self.assertRaises(C.GamekitError) as shot_cm:
            shot._external_png(project, self.link / "a.png", "--out")
        self.assertEqual(shot_cm.exception.code, "FORBIDDEN_PATH")
        png = self.root / "ok.png"
        self.assertEqual(shot._external_png(project, png, "--out").suffix.lower(), ".png")
        with self.assertRaises(C.GamekitError) as diff_cm:
            vcheck._refuse_project_write(self.link / "d.png")
        self.assertEqual(diff_cm.exception.code, "FORBIDDEN_PATH")
        with self.assertRaises(C.GamekitError) as inside:
            P._outside_project(project, self.target / "inside.json")
        self.assertEqual(inside.exception.code, "BAD_REQUEST")
        with self.assertRaises(C.GamekitError) as perf_cm:
            P._outside_project(project, self.link / "out.json")
        self.assertEqual(perf_cm.exception.code, "FORBIDDEN_PATH")
        accepted = P._outside_project(project, self.root / "report.json")
        self.assertFalse(C.is_within(accepted, self.target))

    def test_dangling_junction_is_refused_and_creates_nothing(self) -> None:
        link, target = self.root / "dangling", self.root / "dangling-target"
        self._make_dangling(link, target)
        # exists() follows the junction and can raise WinError 448 on Windows.
        # Test the missing target and the link's own no-follow metadata instead.
        self.assertFalse(target.exists())
        self.assertTrue(os.lstat(link).st_file_attributes & C._REPARSE_POINT)
        self.assertTrue(C._is_junction(link))
        with self.assertRaises(C.GamekitError) as direct:
            C.refuse_unsafe_host_path(link, what="probe")
        self.assertEqual(direct.exception.code, "FORBIDDEN_PATH")
        with self.assertRaises(C.GamekitError) as child:
            C.refuse_unsafe_host_path(link / "secret.txt", what="probe")
        self.assertEqual(child.exception.code, "FORBIDDEN_PATH")
        project = C.Project("game", self.target)
        with self.assertRaises(C.GamekitError) as play_cm:
            Play._checked_out(project, str(link / "play-out.json"))
        self.assertEqual(play_cm.exception.code, "FORBIDDEN_PATH")
        with self.assertRaises(C.GamekitError) as prep:
            B._prepare_out_dir(link)
        self.assertEqual(prep.exception.code, "FORBIDDEN_PATH")
        with self.assertRaises(C.GamekitError):
            B._prepare_out_dir(link / "nested-out")
        runner = _load_runner()
        with self.assertRaises(runner.RecipeFailure):
            runner._out_file(link, "crate.glb")
        with self.assertRaises(runner.RecipeFailure):
            runner._out_file(link / "sub", "crate.glb")
        self.assertFalse(target.exists())
        self.assertFalse((target / "play-out.json").exists())
        self.assertFalse((target / "crate.glb").exists())
        self.assertFalse((target / "nested-out").exists())
        game = self.root / "proj"
        game.mkdir()
        (game / "project.godot").write_text("config_version=5\n", encoding="utf-8")
        inside = game / "addons"
        inside_target = self.root / "addons-target"
        self._make_dangling(inside, inside_target)
        with self.assertRaises(C.GamekitError) as res_cm:
            C.Project("proj", game).res_to_path("res://addons/plugin.gd")
        self.assertEqual(res_cm.exception.code, "FORBIDDEN_PATH")
        self.assertFalse(inside_target.exists())

    def test_readers_refuse_local_junction_and_private_raw(self) -> None:
        studio = self.root / "fakestudio"
        local = studio / ".local"
        local.mkdir(parents=True)
        trace = {"fps": 60, "events": [{"frame": 0, "action": "junctionread", "pressed": True}]}
        (local / "trace.json").write_text(json.dumps(trace), encoding="utf-8")
        (local / "budget.json").write_text('{"frame_ms_p95": 1.0}\n', encoding="utf-8")
        recipe = {"schema": B.SCHEMA, "name": "x", "steps": [{"op": "clear"}]}
        (local / "recipe.json").write_text(json.dumps(recipe), encoding="utf-8")
        (local / "ops.json").write_text("[]\n", encoding="utf-8")
        (local / "actions.json").write_text('{"move": {"events": []}}\n', encoding="utf-8")
        link = self.root / "via-local"
        _make_junction(link, local)
        self._junctions.append(link)
        readers = (
            ("trace", lambda path: P.load_trace(path)),
            ("budget", lambda path: P.load_budget(path)),
            ("recipe", lambda path: B.load_recipe(path)),
            ("play", lambda path: Play._load_trace(str(path))),
            ("ops", lambda path: Scene._load_ops(str(path))),
            ("actions", lambda path: IM._load_actions(str(path))),
            ("png", lambda path: vcheck._load(path, what="png")),
            ("blank", lambda path: vcheck._load(path, what="--blank")),
        )
        names = {
            "trace": "trace.json",
            "budget": "budget.json",
            "recipe": "recipe.json",
            "play": "trace.json",
            "ops": "ops.json",
            "actions": "actions.json",
            "png": "trace.json",
            "blank": "trace.json",
        }
        with mock.patch.object(C, "STUDIO_DIR", studio):
            for label, call in readers:
                with self.subTest(label):
                    with self.assertRaises(C.GamekitError) as cm:
                        call(link / names[label])
                    self.assertEqual(cm.exception.code, "FORBIDDEN_PATH")
            missing = self.root / "private.raw"
            for label, call in readers:
                with self.subTest(label + "-name"):
                    with self.assertRaises(C.GamekitError) as cm:
                        call(missing)
                    self.assertEqual(cm.exception.code, "FORBIDDEN_PATH")
            with self.assertRaises(C.GamekitError) as cli:
                Play._cmd_play(SimpleNamespace(trace=str(missing)))
            self.assertEqual(cli.exception.code, "FORBIDDEN_PATH")
            self.assertFalse(missing.exists())
        plain = self.root / "ok-trace.json"
        plain.write_text(json.dumps(trace), encoding="utf-8")
        self.assertEqual(P.load_trace(plain)["events"][0]["action"], "junctionread")

    def test_editor_check_fails_closed_and_allows_no_editor(self) -> None:
        project = C.Project("game", self.target)
        with mock.patch(
            "studio.gamekit.common.subprocess.run",
            side_effect=subprocess.TimeoutExpired("powershell", 20),
        ):
            with self.assertRaises(C.GamekitError) as timed:
                C.refuse_if_editor_open(project)
            self.assertEqual(timed.exception.code, "EDITOR_CHECK_FAILED")
            self.assertEqual(timed.exception.detail, _EDITOR_DETAIL)
            C.refuse_if_editor_open(project, allow=True)
        empty = subprocess.CompletedProcess(["powershell"], 0, b"", b"")
        bad = subprocess.CompletedProcess(["powershell"], 0, b"not-json", b"")
        clear = subprocess.CompletedProcess(["powershell"], 0, b"[]\r\n", b"")
        with mock.patch("studio.gamekit.common.subprocess.run", return_value=empty):
            with self.assertRaises(C.GamekitError) as empty_cm:
                C.refuse_if_editor_open(project)
            self.assertEqual(empty_cm.exception.code, "EDITOR_CHECK_FAILED")
        with mock.patch("studio.gamekit.common.subprocess.run", return_value=bad):
            with self.assertRaises(C.GamekitError) as bad_cm:
                C.refuse_if_editor_open(project)
            self.assertEqual(bad_cm.exception.code, "EDITOR_CHECK_FAILED")
        with mock.patch("studio.gamekit.common.subprocess.run", return_value=clear):
            C.refuse_if_editor_open(project)
        with mock.patch(
            "studio.gamekit.common.subprocess.run",
            side_effect=OSError("query failed"),
        ):
            with self.assertRaises(C.GamekitError) as os_cm:
                C.refuse_if_editor_open(project)
            self.assertEqual(os_cm.exception.code, "EDITOR_CHECK_FAILED")

    def test_live_editor_query_returns_a_list(self) -> None:
        hits = C.godot_processes_for(self.target)
        self.assertIsInstance(hits, list)

    def test_project_add_same_folder_is_idempotent(self) -> None:
        game = self.root / "idem"
        game.mkdir()
        (game / "project.godot").write_text("config_version=5\n", encoding="utf-8")
        first = C.register_project(game, "idem")
        second = C.register_project(game, "idem")
        self.assertEqual(first.project_id, second.project_id)
        self.assertEqual(os.path.normcase(str(first.root)), os.path.normcase(str(second.root)))
        self.assertEqual(first.registered_at, second.registered_at)
        self.assertEqual(list(C.load_registry()["projects"]), ["idem"])
        loaded = C.get_project("idem")
        self.assertEqual(loaded.project_id, "idem")

    def test_get_project_refuses_root_replaced_by_junction(self) -> None:
        game = self.root / "game"
        game.mkdir()
        (game / "project.godot").write_text("config_version=5\n", encoding="utf-8")
        C.register_project(game, "game")
        shutil.rmtree(game)
        self._junctions.append(game)
        _make_junction(game, self.other)
        with self.assertRaises(C.GamekitError) as cm:
            C.get_project("game")
        self.assertEqual(cm.exception.code, "FORBIDDEN_PATH")


if __name__ == "__main__":
    unittest.main()

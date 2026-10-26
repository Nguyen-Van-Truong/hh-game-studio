"""Quality profiles: known Godot 4.7 settings, dry-run, preservation, rollback, retry."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from studio.gamekit import common as C
from studio.gamekit import hh
from studio.gamekit import project_config as PC
from studio.gamekit import quality as Q

ROOT = Path(__file__).resolve().parents[3]

EXPECTED_KEYS = (
    "rendering/renderer/rendering_method",
    "rendering/renderer/rendering_method.mobile",
    "rendering/anti_aliasing/quality/msaa_2d",
    "rendering/anti_aliasing/quality/msaa_3d",
    "rendering/anti_aliasing/quality/screen_space_aa",
    "rendering/anti_aliasing/quality/use_taa",
    "rendering/lights_and_shadows/directional_shadow/size",
    "rendering/lights_and_shadows/directional_shadow/size.mobile",
    "rendering/lights_and_shadows/directional_shadow/soft_shadow_filter_quality",
    "rendering/lights_and_shadows/directional_shadow/soft_shadow_filter_quality.mobile",
    "rendering/lights_and_shadows/positional_shadow/atlas_size",
    "rendering/lights_and_shadows/positional_shadow/atlas_size.mobile",
    "rendering/2d/shadow_atlas/size",
)

EXPECTED_DEFAULTS = {
    "rendering/renderer/rendering_method": "forward_plus",
    "rendering/renderer/rendering_method.mobile": "mobile",
    "rendering/anti_aliasing/quality/msaa_2d": 0,
    "rendering/anti_aliasing/quality/msaa_3d": 0,
    "rendering/anti_aliasing/quality/screen_space_aa": 0,
    "rendering/anti_aliasing/quality/use_taa": False,
    "rendering/lights_and_shadows/directional_shadow/size": 4096,
    "rendering/lights_and_shadows/directional_shadow/size.mobile": 2048,
    "rendering/lights_and_shadows/directional_shadow/soft_shadow_filter_quality": 2,
    "rendering/lights_and_shadows/directional_shadow/soft_shadow_filter_quality.mobile": 0,
    "rendering/lights_and_shadows/positional_shadow/atlas_size": 4096,
    "rendering/lights_and_shadows/positional_shadow/atlas_size.mobile": 2048,
    "rendering/2d/shadow_atlas/size": 2048,
}

ORIGINAL_TEXT = """config_version=5

[application]
config/name="Hoan Hao"
config/features=PackedStringArray("4.7", "GL Compatibility")

[display]
window/size/viewport_width=1280

[internationalization]
locale/fallback="vi"

[rendering]
renderer/rendering_method="mobile"
renderer/rendering_method.mobile="mobile"
renderer/rendering_method.web="gl_compatibility"
anti_aliasing/quality/use_taa=true
lights_and_shadows/directional_shadow/size=8192
environment/ssao/quality=1

[custom]
data={
"literal": "[display] key=value \\";{}[]()",
"list": [1, 2, {"nested": true}]
}
"""

ORIGINAL_EFFECTIVE = {
    "rendering/renderer/rendering_method": "mobile",
    "rendering/renderer/rendering_method.mobile": "mobile",
    "rendering/anti_aliasing/quality/msaa_2d": 0,
    "rendering/anti_aliasing/quality/msaa_3d": 0,
    "rendering/anti_aliasing/quality/screen_space_aa": 0,
    "rendering/anti_aliasing/quality/use_taa": True,
    "rendering/lights_and_shadows/directional_shadow/size": 8192,
    "rendering/lights_and_shadows/directional_shadow/size.mobile": 2048,
    "rendering/lights_and_shadows/directional_shadow/soft_shadow_filter_quality": 2,
    "rendering/lights_and_shadows/directional_shadow/soft_shadow_filter_quality.mobile": 0,
    "rendering/lights_and_shadows/positional_shadow/atlas_size": 4096,
    "rendering/lights_and_shadows/positional_shadow/atlas_size.mobile": 2048,
    "rendering/2d/shadow_atlas/size": 2048,
}


def _crlf(text: str) -> bytes:
    return text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")


def _lit(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return json.dumps(value)


def _echo(settings: dict) -> dict[str, str]:
    out = {}
    for key, value in settings.items():
        out[key] = "true" if value is True else "false" if value is False else str(value)
    return out


def _generated(settings: dict) -> bytes:
    """Godot-like dump: poison unrelated keys, omit non-string engine defaults."""
    lines = [
        "config_version=5",
        "",
        "[application]",
        'config/name="poison"',
        'config/features=PackedStringArray("4.7")',
        "",
        "[internationalization]",
        'locale/fallback="en"',
        "",
        "[rendering]",
        "environment/ssao/quality=3",
    ]
    for key in Q.MANAGED_KEYS:
        value = settings[key]
        if not isinstance(value, str) and value == Q.ENGINE_DEFAULTS[key]:
            continue
        lines.append(f"{key.split('/', 1)[1]}={_lit(value)}")
    lines += ["", "[custom]", "injected=1", ""]
    return ("\n".join(lines)).encode("utf-8")


def _run(result: dict, errors: list[str] | None = None) -> C.ProcessRun:
    return C.ProcessRun(["godot"], 0, 0.01, "", "", result=result, errors=list(errors or []))


def _catalog_profile(name: str) -> dict:
    for item in Q.list_profiles()["profiles"]:
        if item["name"] == name:
            return item
    raise AssertionError(name)


class _Boundary:
    def __init__(self, project: C.Project) -> None:
        self.project = project
        self.modes: list[str] = []
        self.fail: str | None = None
        self.last: dict | None = None

    def __call__(self, root: object, script: str, request: dict, **kwargs: object) -> C.ProcessRun:
        del root, kwargs
        if script != "settings_tool.gd":
            raise AssertionError(script)
        mode = request["mode"]
        self.modes.append(mode)
        path = self.project.root / "project.godot"
        if mode == "apply":
            if self.fail == "touch":
                path.write_bytes(path.read_bytes() + b"\n; touched\n")
            if self.fail == "reject":
                return _run({"ok": False, "error": "VALIDATION_FAILED", "detail": "bad setting"})
            if self.fail == "nofile":
                return _run({"ok": True})
            target = self.project.res_to_path(request["temp_out"])
            if self.fail == "malformed":
                target.write_bytes(b"not a project\n")
            else:
                target.write_bytes(_generated(request["settings"]))
                self.last = request["settings"]
            return _run({"ok": True, "temp_out": request["temp_out"]})
        if mode != "readback":
            raise AssertionError(mode)
        if self.fail == "timeout":
            raise C.GamekitError("TIMEOUT", "injected readback failure")
        if self.fail == "errors":
            return _run({"ok": True, "settings": {}}, errors=["ERROR: boom"])
        if self.fail == "corrupt":
            path.write_bytes(path.read_bytes().replace(b'fallback="vi"', b'fallback="en"'))
        source = self.last if self.last is not None else ORIGINAL_EFFECTIVE
        echoed = _echo(source)
        if self.fail == "mismatch":
            echoed["rendering/renderer/rendering_method"] = "forward_plus"
        if Q.WEB_KEY in request.get("setting_keys", []):
            echoed[Q.WEB_KEY] = "gl_compatibility"
        keys = request["setting_keys"]
        return _run({"ok": True, "settings": {key: echoed[key] for key in keys}})


class QualityCatalogTests(unittest.TestCase):
    def test_profiles_use_known_godot_47_settings(self) -> None:
        payload = Q.list_profiles()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["pin"], {"godot": "4.7.2.stable", "blender": "5.2.3"})
        self.assertFalse(payload["beauty_guarantee"])
        self.assertEqual(tuple(payload["managed_keys"]), EXPECTED_KEYS)
        self.assertEqual(Q.MANAGED_KEYS, EXPECTED_KEYS)
        self.assertEqual(payload["engine_defaults"], EXPECTED_DEFAULTS)
        self.assertTrue(set(payload["not_managed"]).isdisjoint(EXPECTED_KEYS))
        self.assertIn("rendering/renderer/rendering_method.web", payload["not_managed"])
        self.assertIn("rendering/environment/ssao/quality", payload["not_managed"])
        self.assertIn("rendering/textures/vram_compression/import_etc2_astc", payload["not_managed"])
        by_name = {item["name"]: item for item in payload["profiles"]}
        self.assertEqual(list(by_name), ["compatibility", "mobile", "desktop"])
        expected = {
            "compatibility": ("gl_compatibility", "gl_compatibility", 1024, 1024, 0, 0, 1024),
            "mobile": ("mobile", "mobile", 2048, 2048, 0, 0, 2048),
            "desktop": ("forward_plus", "mobile", 4096, 2048, 2, 0, 2048),
        }
        for name, (renderer, mobile, directional, directional_mobile, soft, soft_mobile, shadow_2d) in expected.items():
            item = by_name[name]
            settings = item["settings"]
            self.assertEqual(tuple(settings), EXPECTED_KEYS)
            self.assertEqual(item["renderer"], renderer)
            self.assertEqual(item["mobile_renderer"], mobile)
            self.assertEqual(settings["rendering/renderer/rendering_method"], renderer)
            self.assertEqual(settings["rendering/renderer/rendering_method.mobile"], mobile)
            self.assertEqual(settings["rendering/anti_aliasing/quality/msaa_2d"], 0)
            self.assertEqual(settings["rendering/anti_aliasing/quality/msaa_3d"], 0)
            self.assertEqual(settings["rendering/anti_aliasing/quality/screen_space_aa"], 0)
            self.assertIs(settings["rendering/anti_aliasing/quality/use_taa"], False)
            self.assertEqual(settings["rendering/lights_and_shadows/directional_shadow/size"], directional)
            self.assertEqual(settings["rendering/lights_and_shadows/directional_shadow/size.mobile"], directional_mobile)
            self.assertEqual(settings["rendering/lights_and_shadows/directional_shadow/soft_shadow_filter_quality"], soft)
            self.assertEqual(settings["rendering/lights_and_shadows/directional_shadow/soft_shadow_filter_quality.mobile"], soft_mobile)
            self.assertEqual(settings["rendering/lights_and_shadows/positional_shadow/atlas_size"], directional)
            self.assertEqual(settings["rendering/lights_and_shadows/positional_shadow/atlas_size.mobile"], directional_mobile)
            self.assertEqual(settings["rendering/2d/shadow_atlas/size"], shadow_2d)
            self.assertFalse(item["beauty_guarantee"])
            self.assertFalse(item["costly_effects_enabled"])
            self.assertIn("does not make a game look better", " ".join(item["limitations"]))
            self.assertIn("are 0", item["headroom"]["aa"])
            self.assertTrue(item["capabilities"])
            self.assertTrue(item["costs"])
        desktop_limits = " ".join(by_name["desktop"]["limitations"])
        self.assertIn("not switched to Forward+", desktop_limits)
        self.assertIn("mobile", by_name["desktop"]["settings"]["rendering/renderer/rendering_method.mobile"])

    def test_parser_and_profiles_command(self) -> None:
        self.assertEqual(hh.MODULES[-3:], ("quality", "sfx", "vfx"))
        parser = hh.build_parser()
        args = parser.parse_args([
            "quality", "apply", "--project", "game", "--profile", "desktop",
            "--command-id", "cmd.quality.1", "--dry-run", "--allow-open-editor",
        ])
        self.assertEqual(args.project, "game")
        self.assertEqual(args.profile, "desktop")
        self.assertEqual(args.command_id, "cmd.quality.1")
        self.assertTrue(args.dry_run)
        self.assertTrue(args.allow_open_editor)
        self.assertEqual(args.func.__name__, "_cmd_apply")
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            parser.parse_args(["quality", "apply", "--project", "game", "--profile", "ultra", "--command-id", "q.ultra.1"])
        self.assertEqual(caught.exception.code, 2)
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = hh.main(["quality", "profiles"])
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual([item["name"] for item in payload["profiles"]], ["compatibility", "mobile", "desktop"])
        self.assertFalse(payload["beauty_guarantee"])

    def test_profiles_subprocess_exits_zero(self) -> None:
        proc = subprocess.run(
            [sys.executable, "-B", "-m", "studio.gamekit.hh", "quality", "profiles"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual([item["name"] for item in payload["profiles"]], ["compatibility", "mobile", "desktop"])
        self.assertFalse(payload["beauty_guarantee"])

    def test_smoke_module_imports_without_starting_godot(self) -> None:
        from studio.gamekit.selftests import quality_smoke

        self.assertTrue(callable(quality_smoke.run))


class QualityMutationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"HH_GAMEKIT_STATE": str(self.root / "state")})
        self.env.start()
        self.game = self.root / "game"
        self.game.mkdir()
        self.original = _crlf(ORIGINAL_TEXT)
        self.path = self.game / "project.godot"
        self.path.write_bytes(self.original)
        self.project = C.register_project(self.game, "game")

    def tearDown(self) -> None:
        self.env.stop()
        self.temp.cleanup()

    def _patches(self, boundary: _Boundary):
        return (
            patch.object(C, "refuse_if_editor_open"),
            patch.object(C, "run_godot_tool", side_effect=boundary),
        )

    def test_dry_run_and_inspect_do_not_mutate(self) -> None:
        boundary = _Boundary(self.project)
        editor, godot = self._patches(boundary)
        buf = io.StringIO()
        with editor, godot, redirect_stdout(buf):
            code = hh.main([
                "quality", "apply", "--project", "game", "--profile", "compatibility",
                "--command-id", "q.dry.1", "--dry-run",
            ])
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["status"], "DRY_RUN")
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["profile"], "compatibility")
        self.assertFalse(payload["beauty_guarantee"])
        self.assertFalse(payload["costly_effects_enabled"])
        self.assertEqual(payload["settings"], _catalog_profile("compatibility")["settings"])
        self.assertEqual(payload["current_settings"], ORIGINAL_EFFECTIVE)
        self.assertEqual(payload["current_renderer"], "mobile")
        self.assertEqual(payload["renderer"], "gl_compatibility")
        self.assertIn("rendering/renderer/rendering_method", payload["changed_keys"])
        self.assertNotIn("rendering/anti_aliasing/quality/msaa_2d", payload["changed_keys"])
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertFalse((self.project.state / "journal.jsonl").exists())
        self.assertFalse((self.project.state / "checkpoints").exists())
        self.assertEqual(boundary.modes, ["readback"])
        buf = io.StringIO()
        with editor, godot, redirect_stdout(buf):
            code = hh.main(["quality", "inspect", "--project", "game"])
        self.assertEqual(code, 0)
        inspected = json.loads(buf.getvalue())
        self.assertIsNone(inspected["matched_profile"])
        self.assertEqual(inspected["renderer"], "mobile")
        self.assertEqual(inspected["mobile_renderer"], "mobile")
        self.assertEqual(inspected["web_renderer"], "gl_compatibility")
        self.assertIs(inspected["settings"]["rendering/anti_aliasing/quality/use_taa"], True)
        self.assertEqual(inspected["settings"]["rendering/lights_and_shadows/directional_shadow/size"], 8192)
        self.assertEqual(inspected["readback"], "FRESH_PROCESS_MATCH")
        self.assertFalse(inspected["beauty_guarantee"])
        self.assertIn("not the compatibility", " ".join(inspected["limitations"]))
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(list(self.game.glob("hh_quality_tmp_*")), [])
        buf = io.StringIO()
        with patch.object(C, "run_godot_tool", side_effect=AssertionError("Godot must not start")), redirect_stdout(buf):
            code = hh.main([
                "quality", "apply", "--project", "missing", "--profile", "mobile",
                "--command-id", "q.missing.1", "--dry-run",
            ])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(buf.getvalue())["error"], "NOT_FOUND")
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_apply_preserves_unrelated_sections_and_removes_owned_defaults(self) -> None:
        boundary = _Boundary(self.project)
        editor, godot = self._patches(boundary)
        with editor, godot:
            applied = Q.apply_profile(self.project, "compatibility", "q.preserve.1")
            compat = self.path.read_bytes()
            desktop = Q.apply_profile(self.project, "desktop", "q.preserve.2")
            inspected = Q.inspect_quality(self.project)
        final = self.path.read_bytes()
        owned = set(Q.MANAGED_KEYS)
        self.assertEqual(applied["status"], "COMMITTED")
        self.assertEqual(applied["readback"], "FRESH_PROCESS_MATCH")
        self.assertEqual(applied["profile"], "compatibility")
        self.assertEqual(applied["renderer"], "gl_compatibility")
        self.assertEqual(applied["mobile_renderer"], "gl_compatibility")
        self.assertEqual(applied["settings"], _catalog_profile("compatibility")["settings"])
        self.assertFalse(applied["beauty_guarantee"])
        self.assertIn("rendering/anti_aliasing/quality/use_taa", applied["changed_keys"])
        self.assertNotIn("rendering/anti_aliasing/quality/msaa_2d", applied["changed_keys"])
        self.assertNotIn("rendering/lights_and_shadows/directional_shadow/soft_shadow_filter_quality.mobile", applied["changed_keys"])
        self.assertNotEqual(applied["before_sha256"], applied["after_sha256"])
        self.assertEqual(compat.count(b"[rendering]"), 1)
        self.assertEqual(compat.count(b'="gl_compatibility"'), 3)
        self.assertIn(b'renderer/rendering_method="gl_compatibility"\r\n', compat)
        self.assertIn(b'renderer/rendering_method.mobile="gl_compatibility"\r\n', compat)
        self.assertIn(b'renderer/rendering_method.web="gl_compatibility"\r\n', compat)
        self.assertIn(b"directional_shadow/size=1024\r\n", compat)
        self.assertIn(b"directional_shadow/size.mobile=1024\r\n", compat)
        self.assertIn(b"directional_shadow/soft_shadow_filter_quality=0\r\n", compat)
        self.assertIn(b"2d/shadow_atlas/size=1024\r\n", compat)
        self.assertNotIn(b"use_taa", compat)
        self.assertNotIn(b"=8192", compat)
        self.assertNotIn(b"soft_shadow_filter_quality.mobile=", compat)
        self.assertEqual(desktop["profile"], "desktop")
        self.assertEqual(desktop["renderer"], "forward_plus")
        self.assertEqual(desktop["mobile_renderer"], "mobile")
        self.assertEqual(desktop["settings"], _catalog_profile("desktop")["settings"])
        self.assertEqual(desktop["readback"], "FRESH_PROCESS_MATCH")
        self.assertEqual(final.count(b"[rendering]"), 1)
        self.assertEqual(final.count(b'="gl_compatibility"'), 1)
        self.assertIn(b'renderer/rendering_method="forward_plus"\r\n', final)
        self.assertIn(b'renderer/rendering_method.mobile="mobile"\r\n', final)
        self.assertIn(b'renderer/rendering_method.web="gl_compatibility"\r\n', final)
        self.assertNotIn(b"use_taa", final)
        self.assertNotIn(b"=1024", final)
        self.assertNotIn(b"=8192", final)
        self.assertNotIn(b"directional_shadow/size", final)
        self.assertNotIn(b"shadow_atlas/size", final)
        self.assertIn(b"environment/ssao/quality=1\r\n", final)
        self.assertIn(b'locale/fallback="vi"\r\n', final)
        self.assertIn(b'config/name="Hoan Hao"\r\n', final)
        self.assertIn(b'config/features=PackedStringArray("4.7", "GL Compatibility")\r\n', final)
        self.assertIn(b'"nested": true', final)
        self.assertNotIn(b"poison", final)
        self.assertNotIn(b'fallback="en"', final)
        self.assertNotIn(b"injected=", final)
        self.assertNotIn(b"ssao/quality=3", final)
        self.assertEqual(PC.preserved_entries(self.original, owned), PC.preserved_entries(final, owned))
        self.assertEqual(inspected["matched_profile"], "desktop")
        self.assertEqual(inspected["renderer"], "forward_plus")
        self.assertEqual(inspected["mobile_renderer"], "mobile")
        self.assertEqual(inspected["web_renderer"], "gl_compatibility")
        self.assertEqual(inspected["settings"], desktop["settings"])
        self.assertFalse(inspected["beauty_guarantee"])
        self.assertEqual(list(self.game.glob("hh_quality_tmp_*")), [])
        self.assertEqual(list(self.game.glob("*.uid")), [])

    def test_retry_is_idempotent_and_changed_payload_conflicts(self) -> None:
        boundary = _Boundary(self.project)
        editor_calls: list[str] = []

        def editor(*_args: object, **_kwargs: object) -> None:
            editor_calls.append("open-check")

        with patch.object(C, "refuse_if_editor_open", side_effect=editor), patch.object(C, "run_godot_tool", side_effect=boundary):
            first = Q.apply_profile(self.project, "compatibility", "q.retry.1")
            committed = self.path.read_bytes()
            modes = list(boundary.modes)
            replay = Q.apply_profile(self.project, "compatibility", "q.retry.1")
            self.assertEqual(boundary.modes, modes)
            self.assertEqual(editor_calls, ["open-check"])
            preview = Q.apply_profile(self.project, "desktop", "q.retry.1", dry_run=True)
            with self.assertRaises(C.GamekitError) as caught:
                Q.apply_profile(self.project, "desktop", "q.retry.1")
        self.assertEqual(first["status"], "COMMITTED")
        self.assertNotIn("replayed", first)
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["command_id"], "q.retry.1")
        self.assertEqual(replay["profile"], "compatibility")
        self.assertEqual(replay["settings"], first["settings"])
        self.assertEqual(preview["status"], "DRY_RUN")
        self.assertNotIn("replayed", preview)
        self.assertEqual(preview["profile"], "desktop")
        self.assertEqual(caught.exception.code, "CONFLICT")
        self.assertEqual(self.path.read_bytes(), committed)
        self.assertEqual(len(C.Journal(self.project).records()), 1)
        self.assertEqual(editor_calls, ["open-check"])
        self.assertEqual(boundary.modes, modes + ["readback"])

    def test_failures_restore_exact_original_bytes(self) -> None:
        cases = (
            ("touch", "GODOT_FAILED"),
            ("reject", "VALIDATION_FAILED"),
            ("nofile", "GODOT_FAILED"),
            ("malformed", "GODOT_FAILED"),
            ("timeout", "TIMEOUT"),
            ("errors", "READBACK_MISMATCH"),
            ("corrupt", "READBACK_MISMATCH"),
            ("mismatch", "READBACK_MISMATCH"),
        )
        boundary = _Boundary(self.project)
        editor, godot = self._patches(boundary)
        for name, code in cases:
            with self.subTest(name=name):
                self.path.write_bytes(self.original)
                boundary.fail = name
                boundary.last = None
                command_id = f"q.fail.{name}"
                with editor, godot:
                    with self.assertRaises(C.GamekitError) as caught:
                        Q.apply_profile(self.project, "compatibility", command_id)
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(self.path.read_bytes(), self.original)
                self.assertIsNone(C.Journal(self.project).find(command_id))
                self.assertEqual(list(self.game.glob("hh_quality_tmp_*")), [])
        self.assertEqual(C.Journal(self.project).records(), [])

    def test_unknown_profile_and_editor_do_not_write(self) -> None:
        def forbid(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("Godot must not start")

        with patch.object(C, "run_godot_tool", side_effect=forbid):
            with self.assertRaises(C.GamekitError) as bad_profile:
                Q.apply_profile(self.project, "ultra", "q.bad.1")
            with self.assertRaises(C.GamekitError) as bad_id:
                Q.apply_profile(self.project, "mobile", "no")
        self.assertEqual(bad_profile.exception.code, "VALIDATION_FAILED")
        self.assertEqual(bad_id.exception.code, "BAD_REQUEST")
        with patch.object(C, "refuse_if_editor_open", side_effect=C.GamekitError("EDITOR_OPEN", "open")), patch.object(C, "run_godot_tool", side_effect=forbid):
            with self.assertRaises(C.GamekitError) as opened:
                Q.apply_profile(self.project, "compatibility", "q.editor.1")
        self.assertEqual(opened.exception.code, "EDITOR_OPEN")
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertFalse((self.project.state / "journal.jsonl").exists())
        self.assertEqual(list(self.game.glob("hh_quality_tmp_*")), [])


if __name__ == "__main__":
    unittest.main()

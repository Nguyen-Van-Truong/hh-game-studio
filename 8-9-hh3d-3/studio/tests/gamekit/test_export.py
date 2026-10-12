"""Fast unit tests (no Godot) for gamekit W10 export presets and path rules."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from studio.gamekit import common as C
from studio.gamekit import export as E


USER_PRESET = """[preset.0]

name="Player Build"
platform="Windows Desktop"
runnable=false
custom_features=""
export_filter="all_resources"
include_filter=""
exclude_filter=""
export_path="keep/player.exe"

[preset.0.options]

custom_template/debug="C:/do-not-touch"
binary_format/embed_pck=true
"""


class PresetMergeTest(unittest.TestCase):
    def test_render_windows_and_web_fields(self) -> None:
        windows, changed = E.merge_presets("", "windows", "D:/out/Game.exe")
        self.assertTrue(changed)
        self.assertIn('[preset.0]', windows)
        self.assertIn('name="HH Windows"', windows)
        self.assertIn('platform="Windows Desktop"', windows)
        self.assertIn("runnable=true", windows)
        self.assertIn('export_filter="all_resources"', windows)
        self.assertIn('export_path="D:/out/Game.exe"', windows)
        self.assertIn("[preset.0.options]", windows)
        self.assertIn("binary_format/embed_pck=false", windows)
        self.assertIn('binary_format/architecture="x86_64"', windows)
        self.assertIn("debug/export_console_wrapper=0", windows)

        web, web_changed = E.merge_presets("", "web", "D:/out/index.html")
        self.assertTrue(web_changed)
        self.assertIn('name="HH Web"', web)
        self.assertIn('platform="Web"', web)
        self.assertIn("variant/thread_support=false", web)
        self.assertIn("variant/extensions_support=false", web)
        self.assertIn("progressive_web_app/ensure_cross_origin_isolation_headers=false", web)
        self.assertNotIn("variant/thread_support=true", web)

        linux, _ = E.merge_presets("", "linux", "D:/out/Game.x86_64")
        self.assertIn('name="HH Linux"', linux)
        self.assertIn('platform="Linux"', linux)
        self.assertIn('export_path="D:/out/Game.x86_64"', linux)

    def test_merge_appends_and_keeps_user_preset_bytes(self) -> None:
        merged, changed = E.merge_presets(USER_PRESET, "linux", "D:/out/Game.x86_64")
        self.assertTrue(changed)
        self.assertTrue(merged.startswith(USER_PRESET))
        self.assertEqual(merged[: len(USER_PRESET)], USER_PRESET)
        self.assertIn("[preset.1]", merged)
        self.assertIn('name="HH Linux"', merged)
        self.assertIn('custom_template/debug="C:/do-not-touch"', merged)
        self.assertEqual(merged.count("binary_format/embed_pck=true"), 1)
        self.assertIn("binary_format/embed_pck=false", merged)
        self.assertNotIn("[preset.0.options]\n\nbinary_format/embed_pck=false", merged.split("[preset.1]")[0])

        again, again_changed = E.merge_presets(merged, "linux", "E:/other/Nope.x86_64")
        self.assertFalse(again_changed)
        self.assertEqual(again, merged)

        with_web, web_changed = E.merge_presets(merged, "web", "D:/out/index.html")
        self.assertTrue(web_changed)
        self.assertTrue(with_web.startswith(USER_PRESET))
        self.assertEqual(with_web.count('name="HH Web"'), 1)
        self.assertIn("variant/thread_support=false", with_web.split("[preset.2]", 1)[1])

    def test_crlf_user_preset_stays_a_prefix(self) -> None:
        user = "[preset.0]\r\n\r\nname=\"Mine\"\r\nplatform=\"Linux\"\r\n"
        merged, changed = E.merge_presets(user, "windows", "C:/out/Game.exe")
        self.assertTrue(changed)
        self.assertTrue(merged.startswith(user))
        self.assertIn("\r\nname=\"Mine\"\r\n", merged)
        self.assertIn("[preset.1]", merged)

    def test_first_free_index_and_no_renumber(self) -> None:
        user = "[preset.0]\n\nname=\"A\"\nplatform=\"Windows Desktop\"\n\n[preset.2]\n\nname=\"B\"\nplatform=\"Linux\"\n"
        merged, changed = E.merge_presets(user, "web", "D:/o/index.html")
        self.assertTrue(changed)
        self.assertTrue(merged.startswith(user))
        self.assertIn("[preset.1]\n", merged)
        self.assertNotIn("[preset.3]", merged)
        self.assertEqual(merged.count('name="A"'), 1)
        self.assertEqual(merged.count('name="B"'), 1)

    def test_existing_hh_preset_is_not_rewritten(self) -> None:
        text, _ = E.merge_presets("", "windows", "D:/first/Game.exe")
        again, changed = E.merge_presets(text, "windows", "D:/second/Other.exe")
        self.assertFalse(changed)
        self.assertEqual(again, text)
        self.assertIn('export_path="D:/first/Game.exe"', again)
        self.assertNotIn("D:/second/Other.exe", again)

    def test_wrong_platform_and_web_threads_conflict(self) -> None:
        bad = '[preset.0]\n\nname="HH Windows"\nplatform="Web"\n'
        with self.assertRaises(C.GamekitError) as cm:
            E.merge_presets(bad, "windows", "D:/out/Game.exe")
        self.assertEqual(cm.exception.code, "CONFLICT")
        self.assertIn("HH Windows", bad)

        threaded = (
            '[preset.0]\n\nname="HH Web"\nplatform="Web"\n\n'
            '[preset.0.options]\n\nvariant/thread_support=true\n'
        )
        with self.assertRaises(C.GamekitError) as cm2:
            E.merge_presets(threaded, "web", "D:/out/index.html")
        self.assertEqual(cm2.exception.code, "CONFLICT")
        self.assertIn("thread_support=true", threaded)

    def test_names_and_output_filenames(self) -> None:
        self.assertEqual(E.validate_name("Game"), "Game")
        self.assertEqual(E.validate_preset("web"), "web")
        for bad in ("", "../Game", "Game/Win", "Game win", "a" * 65):
            with self.assertRaises(C.GamekitError) as cm:
                E.validate_name(bad)
            self.assertEqual(cm.exception.code, "BAD_REQUEST")
        with self.assertRaises(C.GamekitError) as cm:
            E.validate_preset("android")
        self.assertEqual(cm.exception.code, "BAD_REQUEST")
        self.assertEqual(E.output_filenames("windows", "Game"), ["Game.exe", "Game.pck"])
        self.assertEqual(E.output_filenames("linux", "Game"), ["Game.x86_64", "Game.pck"])
        self.assertEqual(E.output_filenames("web", "Game"), ["index.html", "index.js", "index.wasm", "index.pck"])


class TemplateSelectionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.names = [
            "templates/version.txt",
            "templates/windows_release_x86_64.exe",
            "templates/windows_debug_x86_64.exe",
            "templates/windows_release_x86_64_console.exe",
            "templates/linux_release.x86_64",
            "templates/linux_debug.x86_64",
            "templates/web_nothreads_release.zip",
            "templates/web_nothreads_debug.zip",
            "templates/web_release.zip",
            "templates/web_debug.zip",
            "templates/web_dlink_release.zip",
            "templates/android_release.apk",
        ]

    def test_all_selects_needed_members_only(self) -> None:
        files = [dest for _, dest in E.select_template_members(self.names, "all")]
        self.assertEqual(files[0], "version.txt")
        for name in (
            "windows_release_x86_64.exe",
            "windows_debug_x86_64.exe",
            "linux_release.x86_64",
            "linux_debug.x86_64",
            "web_nothreads_release.zip",
            "web_nothreads_debug.zip",
            "web_release.zip",
            "web_debug.zip",
        ):
            self.assertIn(name, files)
        self.assertNotIn("web_dlink_release.zip", files)
        self.assertNotIn("android_release.apk", files)
        self.assertNotIn("windows_release_x86_64_console.exe", files)

    def test_windows_slice_and_missing_member(self) -> None:
        files = [dest for _, dest in E.select_template_members(self.names, "windows")]
        self.assertEqual(files, ["version.txt", "windows_release_x86_64.exe", "windows_debug_x86_64.exe"])
        with self.assertRaises(C.GamekitError) as cm:
            E.select_template_members(["templates/version.txt"], "linux")
        self.assertEqual(cm.exception.code, "TOOL_MISSING")

    def test_web_without_optional_threaded_zips(self) -> None:
        names = [n for n in self.names if "web_release" not in n and "web_debug.zip" not in n]
        files = [dest for _, dest in E.select_template_members(names, "web")]
        self.assertEqual(files, ["version.txt", "web_nothreads_release.zip", "web_nothreads_debug.zip"])

    def test_cache_key_is_size_mtime_and_expected_hash(self) -> None:
        good = {"size": 5, "mtime_ns": 9, "sha256": E.ARCHIVE_SHA256}
        self.assertTrue(E.cache_matches(good, 5, 9))
        self.assertFalse(E.cache_matches({"size": 5, "mtime_ns": 9, "sha256": "abc"}, 5, 9))
        self.assertFalse(E.cache_matches({"size": 4, "mtime_ns": 9, "sha256": E.ARCHIVE_SHA256}, 5, 9))
        self.assertFalse(E.cache_matches({"size": 5, "mtime_ns": 8, "sha256": E.ARCHIVE_SHA256}, 5, 9))
        self.assertFalse(E.cache_matches(None, 5, 9))


class PathRulesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.game = self.root / "game"
        self.game.mkdir()
        (self.game / "project.godot").write_text("config_version=5\n", encoding="utf-8")
        self.project = C.Project("game", self.game)
        self._cwd = os.getcwd()

    def tearDown(self) -> None:
        os.chdir(self._cwd)
        self.tmp.cleanup()

    def test_outside_directory_is_accepted(self) -> None:
        out = self.root / "dist"
        got = E.validate_out_dir(self.project, out)
        self.assertFalse(C.is_within(got, self.game))
        self.assertTrue(C.is_within(got, self.root))
        self.assertFalse(got.exists())

    def test_inside_project_and_file_are_refused(self) -> None:
        with self.assertRaises(C.GamekitError) as inside:
            E.validate_out_dir(self.project, self.game / "build")
        self.assertEqual(inside.exception.code, "FORBIDDEN_PATH")
        with self.assertRaises(C.GamekitError) as root:
            E.validate_out_dir(self.project, self.game)
        self.assertEqual(root.exception.code, "FORBIDDEN_PATH")
        target = self.root / "not-a-dir.txt"
        target.write_text("x", encoding="utf-8")
        with self.assertRaises(C.GamekitError) as filed:
            E.validate_out_dir(self.project, target)
        self.assertEqual(filed.exception.code, "BAD_PATH")

    def test_relative_path_inside_project_is_refused(self) -> None:
        os.chdir(self.game)
        with self.assertRaises(C.GamekitError) as cm:
            E.validate_out_dir(self.project, "build")
        self.assertEqual(cm.exception.code, "FORBIDDEN_PATH")
        os.chdir(self.root)
        got = E.validate_out_dir(self.project, "dist")
        self.assertFalse(C.is_within(got, self.game))

    def test_forbidden_scope_out_dir(self) -> None:
        bad = self.root / "godot" / "dogfood" / "kho-bi-an" / "out"
        with self.assertRaises(C.GamekitError) as cm:
            E.validate_out_dir(self.project, bad)
        self.assertEqual(cm.exception.code, "FORBIDDEN_PATH")

    def test_cli_registers_export(self) -> None:
        from studio.gamekit.hh import build_parser

        parser = build_parser()
        templates = parser.parse_args(["export", "templates", "--install", "--platform", "windows"])
        self.assertTrue(templates.install)
        self.assertEqual(templates.platform, "windows")
        self.assertTrue(callable(templates.func))
        run = parser.parse_args([
            "export", "run", "game", "--preset", "web", "--out-dir", "C:/out",
            "--command-id", "cmd.export.1", "--debug", "--name", "Demo", "--allow-open-editor",
        ])
        self.assertEqual(run.preset, "web")
        self.assertEqual(run.out_dir, "C:/out")
        self.assertEqual(run.command_id, "cmd.export.1")
        self.assertTrue(run.debug)
        self.assertEqual(run.name, "Demo")
        self.assertTrue(run.allow_open_editor)
        self.assertTrue(callable(run.func))


if __name__ == "__main__":
    unittest.main()

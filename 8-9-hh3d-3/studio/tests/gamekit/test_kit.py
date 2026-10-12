"""Fast unit tests (no Godot) for gamekit W9: kit manifests and the install file plan."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from studio.gamekit import common as C
from studio.gamekit import hh
from studio.gamekit import kit as K


_LAYOUT_OK = (
    '[gd_resource type="AudioBusLayout" format=3]\n\n[resource]\n'
    'bus/1/name = &"Music"\nbus/1/send = &"Master"\n'
    'bus/2/name = &"SFX"\nbus/2/send = &"Master"\n'
)


class _TempState(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self._old_state = os.environ.get("HH_GAMEKIT_STATE")
        self._old_godot = os.environ.get("HH_GODOT")
        os.environ["HH_GAMEKIT_STATE"] = str(self.root / "state")
        os.environ["HH_GODOT"] = str(self.root / "no-godot.exe")
        self.game = self.root / "game"
        self.game.mkdir()
        (self.game / "project.godot").write_text('config_version=5\n\n[application]\n\nconfig/name="game"\n', encoding="utf-8")
        self.project = C.register_project(self.game, "game")

    def tearDown(self) -> None:
        if self._old_state is None:
            os.environ.pop("HH_GAMEKIT_STATE", None)
        else:
            os.environ["HH_GAMEKIT_STATE"] = self._old_state
        if self._old_godot is None:
            os.environ.pop("HH_GODOT", None)
        else:
            os.environ["HH_GODOT"] = self._old_godot
        self.tmp.cleanup()


class ManifestTest(unittest.TestCase):
    def test_builtin_kits(self) -> None:
        kits = K.list_kits()
        names = [kit["name"] for kit in kits]
        self.assertEqual(names, ["audio", "pause", "rebind", "save", "settings"])
        by_name = {kit["name"]: kit for kit in kits}
        self.assertEqual(by_name["audio"]["files"], [])
        self.assertEqual(by_name["audio"]["autoloads"], {})
        self.assertEqual(by_name["pause"]["autoloads"], {})
        self.assertEqual(by_name["save"]["autoloads"]["HHSave"], "res://addons/hh_kits/save/hh_save.gd")
        self.assertEqual(by_name["settings"]["autoloads"]["HHSettings"], "res://addons/hh_kits/settings/hh_settings.gd")
        self.assertEqual(by_name["rebind"]["autoloads"]["HHRebind"], "res://addons/hh_kits/rebind/hh_rebind.gd")
        for kit in kits:
            self.assertEqual(kit["version"], "1")
            self.assertEqual(kit["requires"], [])
            for rel in kit["files"]:
                text = (K.KITS_DIR / kit["name"] / rel).read_text(encoding="utf-8")
                if rel.endswith(".gd"):
                    self.assertTrue(text.startswith(K.license_line(kit["name"]) + "\n") or text.startswith(K.license_line(kit["name"]) + "\r\n"))
                if rel.endswith(".tscn"):
                    self.assertTrue(text.startswith("[gd_scene"))
                    self.assertIn(f"res://addons/hh_kits/{kit['name']}/", text)

    def test_rejects_bad_manifests(self) -> None:
        folder = Path(tempfile.mkdtemp())
        try:
            script = folder / "a.gd"
            script.write_text(K.license_line("bad") + "\nextends Node\n", encoding="utf-8")
            good = {"name": "bad", "version": "1", "files": ["a.gd"], "autoloads": {}, "requires": []}
            self.assertEqual(K.validate_manifest(good, folder, folder_name="bad")["name"], "bad")

            def reject(data: dict, code: str = "VALIDATION_FAILED") -> None:
                with self.assertRaises(C.GamekitError) as cm:
                    K.validate_manifest(data, folder, folder_name="bad")
                self.assertEqual(cm.exception.code, code, cm.exception.detail)

            reject({**good, "extra": 1})
            reject({k: v for k, v in good.items() if k != "version"})
            reject({**good, "name": "nope"})
            reject({**good, "version": ""})
            reject({**good, "files": ["../a.gd"]})
            reject({**good, "files": ["missing.gd"]})
            reject({**good, "requires": ["bad"]})
            reject({**good, "requires": ["NotAKit"]})
            reject({**good, "autoloads": {"hh": "res://addons/hh_kits/bad/a.gd"}})
            reject({**good, "autoloads": {"HHSave": "res://addons/hh_kits/bad/nope.gd"}})
            reject({**good, "autoloads": {"HHSave": "res://other.gd"}})
            reject({**good, "autoloads": {"HHSave": "*res://addons/hh_kits/bad/a.gd"}})
            script.write_text("extends Node\n", encoding="utf-8")
            reject(good)
        finally:
            script = folder / "a.gd"
            if script.exists():
                script.unlink()
            folder.rmdir()

    def test_cli_list_and_parser(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = hh.main(["kit", "list"])
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertTrue(payload["ok"])
        self.assertIn("save", [kit["name"] for kit in payload["kits"]])
        parser = hh.build_parser()
        args = parser.parse_args(["kit", "add", "game", "save", "--command-id", "cmd.kit.1", "--replace", "--allow-open-editor"])
        self.assertEqual(args.kit, "save")
        self.assertTrue(args.replace)
        self.assertTrue(args.allow_open_editor)
        self.assertTrue(callable(args.func))
        removed = parser.parse_args(["kit", "remove", "game", "pause", "--command-id", "cmd.kit.rm"])
        self.assertEqual(removed.func.__name__, "_cmd_remove")
        self.assertFalse(removed.force)
        forced = parser.parse_args(["kit", "remove", "game", "pause", "--command-id", "cmd.kit.rm", "--force"])
        self.assertTrue(forced.force)

    def test_persist_kits_keep_a_backup(self) -> None:
        expected = {
            "save": "user://saves/.%s.json.bak",
            "settings": "user://.settings.cfg.bak",
            "rebind": "user://.input_map.cfg.bak",
        }
        for name, bak in expected.items():
            text = (K.KITS_DIR / name / f"hh_{name}.gd").read_text(encoding="utf-8")
            self.assertIn(bak, text)
            self.assertIn("loaded backup", text)
            self.assertNotIn("remove_absolute(final_abs)", text)
            self.assertIn("rename_absolute(final_abs, bak_abs)", text)
            self.assertIn("rename_absolute(temp_abs, final_abs)", text)
            self.assertIn("rename_absolute(bak_abs, final_abs)", text)


class FilePlanTest(_TempState):
    def test_new_files_are_writes(self) -> None:
        plan = K.plan_add(self.project, K.load_kit("save"), replace=False)
        self.assertEqual(len(plan["files"]), 1)
        item = plan["files"][0]
        self.assertEqual(item["res"], "res://addons/hh_kits/save/hh_save.gd")
        self.assertFalse(item["existed"])
        self.assertTrue(item["write"])
        self.assertEqual(plan["autoloads"]["HHSave"], "*res://addons/hh_kits/save/hh_save.gd")
        self.assertTrue(plan["touch_project"])

    def test_overwrite_refusal(self) -> None:
        kit = K.load_kit("save")
        dest = self.project.res_to_path("res://addons/hh_kits/save/hh_save.gd")
        dest.parent.mkdir(parents=True)
        dest.write_text("extends Node\n# different\n", encoding="utf-8")
        with self.assertRaises(C.GamekitError) as cm:
            K.plan_add(self.project, kit, replace=False)
        self.assertEqual(cm.exception.code, "CONFLICT")
        self.assertIn("hh_save.gd", cm.exception.detail)
        replaced = K.plan_add(self.project, kit, replace=True)
        self.assertTrue(replaced["files"][0]["write"])
        dest.write_bytes((K.KITS_DIR / "save" / "hh_save.gd").read_bytes())
        same = K.plan_add(self.project, kit, replace=False)
        self.assertTrue(same["files"][0]["same"])
        self.assertFalse(same["files"][0]["write"])

    def test_audio_layout_refusal(self) -> None:
        kit = K.load_kit("audio")
        fresh = K.plan_add(self.project, kit, replace=False)
        self.assertTrue(fresh["audio_write"])
        self.assertEqual(fresh["settings"]["audio/buses/default_bus_layout"], K.AUDIO_LAYOUT_RES)
        dest = self.project.res_to_path(K.AUDIO_LAYOUT_RES)
        dest.write_text("[gd_resource type=\"AudioBusLayout\" format=3]\n", encoding="utf-8")
        with self.assertRaises(C.GamekitError) as cm:
            K.plan_add(self.project, kit, replace=False)
        self.assertEqual(cm.exception.code, "CONFLICT")
        dest.write_text(_LAYOUT_OK, encoding="utf-8")
        kept = K.plan_add(self.project, kit, replace=False)
        self.assertFalse(kept["audio_write"])
        self.assertTrue(K.kit_installed(self.project, "audio"))

    def test_unmet_requires_and_ids(self) -> None:
        fake = dict(K.load_kit("save"))
        fake["requires"] = ["audio"]
        self.assertEqual(K.unmet_requires(self.project, fake), ["audio"])
        with self.assertRaises(C.GamekitError) as cm:
            K.add_kit(self.project, "no-such", "cmd.kit.missing")
        self.assertEqual(cm.exception.code, "BAD_REQUEST")
        with self.assertRaises(C.GamekitError) as cm2:
            K.add_kit(self.project, "missingkit", "cmd.kit.missing")
        self.assertEqual(cm2.exception.code, "NOT_FOUND")
        with self.assertRaises(C.GamekitError) as cm3:
            K.add_kit(self.project, "save", "x")
        self.assertEqual(cm3.exception.code, "BAD_REQUEST")

    def test_replay_and_conflict_do_not_launch_godot(self) -> None:
        command_id = "cmd.kit.replay"
        digest = K.add_request_digest("pause", False)
        C.Journal(self.project).append(command_id, digest, {
            "ok": True, "status": "COMMITTED", "kind": "kit.add", "command_id": command_id, "kit": "pause",
        })
        replayed = K.add_kit(self.project, "pause", command_id)
        self.assertTrue(replayed.get("replayed"))
        self.assertEqual(replayed.get("kit"), "pause")
        with self.assertRaises(C.GamekitError) as cm:
            K.add_kit(self.project, "save", command_id)
        self.assertEqual(cm.exception.code, "CONFLICT")
        self.assertFalse((self.game / "addons").exists())

    def test_remove_refuses_modified_files(self) -> None:
        save = K.load_kit("save")
        dest = self.project.res_to_path("res://addons/hh_kits/save/hh_save.gd")
        dest.parent.mkdir(parents=True)
        src = (K.KITS_DIR / "save" / "hh_save.gd").read_bytes()
        dest.write_bytes(src)
        self.assertEqual(K.plan_remove(self.project, save)["modified"], [])
        dest.write_bytes(src + b"\n# edited by the game\n")
        project_before = (self.game / "project.godot").read_bytes()
        file_before = dest.read_bytes()
        planned = K.plan_remove(self.project, save)
        self.assertEqual(planned["modified"], ["res://addons/hh_kits/save/hh_save.gd"])
        with self.assertRaises(C.GamekitError) as cm:
            K.remove_kit(self.project, "save", "cmd.kit.rm.mod")
        self.assertEqual(cm.exception.code, "CONFLICT")
        self.assertEqual(
            cm.exception.detail,
            "1 kit file(s) changed since install: res://addons/hh_kits/save/hh_save.gd; keep them or pass --force",
        )
        self.assertEqual(cm.exception.extra.get("modified"), ["res://addons/hh_kits/save/hh_save.gd"])
        self.assertEqual((self.game / "project.godot").read_bytes(), project_before)
        self.assertEqual(dest.read_bytes(), file_before)
        self.assertFalse((self.project.state / "checkpoints" / "cmd.kit.rm.mod").exists())
        self.assertIsNone(C.Journal(self.project).find("cmd.kit.rm.mod"))

        layout = self.project.res_to_path(K.AUDIO_LAYOUT_RES)
        layout.write_bytes(_LAYOUT_OK.encode("utf-8"))
        self.assertEqual(K.plan_remove(self.project, K.load_kit("audio"))["modified"], [])
        bad = b'[gd_resource type="AudioBusLayout" format=3]\n'
        layout.write_bytes(bad)
        with self.assertRaises(C.GamekitError) as cm_audio:
            K.remove_kit(self.project, "audio", "cmd.kit.rm.audio")
        self.assertEqual(cm_audio.exception.code, "CONFLICT")
        self.assertEqual(cm_audio.exception.extra.get("modified"), [K.AUDIO_LAYOUT_RES])
        self.assertEqual(layout.read_bytes(), bad)
        self.assertEqual((self.game / "project.godot").read_bytes(), project_before)

        self.assertEqual(K.remove_request_digest("save"), K.remove_request_digest("save", False))
        self.assertNotEqual(K.remove_request_digest("save", False), K.remove_request_digest("save", True))


if __name__ == "__main__":
    unittest.main()

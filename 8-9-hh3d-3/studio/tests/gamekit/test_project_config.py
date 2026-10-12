"""Focused regressions for project.godot preservation; no engine required."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio.gamekit import common as C
from studio.gamekit import inputmap as IM
from studio.gamekit import kit as K
from studio.gamekit import project_config as PC


BASE = b'''config_version=5

[application]
config/name="Hoan Hao"
config/features=PackedStringArray("4.7", "GL Compatibility")

[display]
window/size/viewport_width=1280
window/stretch/mode="canvas_items"

[internationalization]
locale/fallback="vi"

[physics]
common/physics_ticks_per_second=60

[custom]
data={
"literal": "[display] key=value \\";{}[]()",
"list": [1, 2, {"nested": true}]
}

[input]
old_action={
"deadzone": 0.5,
"events": [Object(InputEventKey,"keycode":65)]
}
ui_accept={"deadzone": 0.6, "events": []}
'''

GENERATED = b'''config_version=5

[application]
config/name="wrong generated name"
config/features=PackedStringArray("4.7")

[input]
jump={
"deadzone": 0.5,
"events": [Object(InputEventKey,"keycode":32)]
}
old_action={"deadzone": 0.1, "events": []}
ui_accept={"deadzone": 0.2, "events": []}
'''


class ConfigMergeTests(unittest.TestCase):
    def test_input_add_keeps_whole_unrelated_sections_and_multiline_values(self):
        changed = {"input/jump"}
        merged = PC.merge_project_godot(BASE, GENERATED, drop_keys=changed)
        self.assertEqual(PC.preserved_entries(BASE, changed), PC.preserved_entries(merged, changed))
        self.assertIn(b'old_action={\n"deadzone": 0.5', merged)
        self.assertIn(b'jump={\n"deadzone": 0.5', merged)
        self.assertNotIn(b"wrong generated name", merged)

    def test_input_replace_removes_only_explicit_non_ui_actions(self):
        before = [{"name": "old_action"}, {"name": "ui_accept"}]
        changed = IM._project_drop_keys(before, {"jump": {}}, True)
        self.assertEqual(changed, {"input/old_action", "input/jump"})
        generated = GENERATED.replace(b'old_action={"deadzone": 0.1, "events": []}\n', b"")
        merged = PC.merge_project_godot(BASE, generated, drop_keys=changed)
        self.assertNotIn(b"old_action=", merged)
        self.assertIn(b'ui_accept={"deadzone": 0.6', merged)

    def test_explicit_ui_override_is_owned(self):
        changed = IM._project_drop_keys([], {"ui_accept": {}}, False)
        merged = PC.merge_project_godot(BASE, GENERATED, drop_keys=changed)
        self.assertIn(b'ui_accept={"deadzone": 0.2', merged)

    def test_kit_add_and_remove_preserve_other_autoloads(self):
        original = BASE + b'\n[autoload]\nHHState="*res://state.gd"\n'
        generated = GENERATED + b'\n[autoload]\nHHSave="*res://save.gd"\n'
        changed = {"autoload/HHSave"}
        merged = PC.merge_project_godot(original, generated, drop_keys=changed)
        self.assertIn(b'HHState="*res://state.gd"', merged)
        self.assertIn(b'HHSave="*res://save.gd"', merged)
        removed = PC.merge_project_godot(merged, GENERATED, drop_keys=changed)
        self.assertNotIn(b"HHSave=", removed)
        self.assertEqual(PC.preserved_entries(original, changed), PC.preserved_entries(removed, changed))

    def test_adding_new_section_preserves_crlf_and_comments(self):
        original = b'; keep\r\nconfig_version=5\r\n[application]\r\nconfig/name="game"'
        generated = b'config_version=5\n[autoload]\nHHSave="*res://save.gd"\n'
        merged = PC.merge_project_godot(original, generated, drop_keys={"autoload/HHSave"})
        self.assertTrue(merged.startswith(original))
        self.assertIn(b'\r\n[autoload]\r\nHHSave=', merged)

    def test_requested_multiple_keys_in_same_section(self):
        source = b'config_version=5\n[input]\nleft={"events": []}\n'
        generated = b'config_version=5\n[input]\nleft={"deadzone": 0.4, "events": []}\nright={"events": []}\n'
        merged = PC.merge_project_godot(source, generated, drop_keys={"input/left", "input/right"})
        self.assertIn(b'left={"deadzone": 0.4', merged)
        self.assertEqual(merged.count(b"right="), 1)

    def test_malformed_or_ambiguous_output_is_rejected(self):
        for data in (b"", b'config_version=5\n[input]\njump={\n', b'config_version=5\n[x]\na=1\n[x]\nb=2\n', b'config_version=5\n[x]\na=1\na=2\n'):
            with self.subTest(data=data), self.assertRaises(C.GamekitError):
                PC.merge_project_godot(BASE, data, drop_keys={"input/jump"})

    def test_post_readback_rejects_changed_unrelated_setting(self):
        with self.assertRaises(C.GamekitError) as raised:
            PC.require_preserved(BASE, BASE.replace(b'fallback="vi"', b'fallback="en"'), {"input/jump"})
        self.assertEqual(raised.exception.code, "READBACK_MISMATCH")


class PreservationRollbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"HH_GAMEKIT_STATE": str(self.root / "state")})
        self.env.start()
        self.game = self.root / "game"
        self.game.mkdir()
        self.original = b'config_version=5\n[application]\nconfig/name="game"\n[internationalization]\nlocale/fallback="vi"\n'
        self.path = self.game / "project.godot"
        self.path.write_bytes(self.original)
        self.project = C.register_project(self.game, "game")

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def _corrupt(self):
        self.path.write_bytes(self.path.read_bytes().replace(b'fallback="vi"', b'fallback="en"'))

    def test_input_rolls_back_when_readback_changes_unrelated_source(self):
        action = {"name": "jump", "deadzone": 0.5, "events": [{"key": "Space"}]}

        def apply(_root, _script, request, **_kwargs):
            Path(request["temp_out"]).write_bytes(GENERATED)
            return C.ProcessRun([], 0, 0.0, "", "", result={"ok": True, "before": [], "written": [action]})

        def readback(*_args):
            self._corrupt()
            return [action], {}

        with patch.object(C, "refuse_if_editor_open"), patch.object(C, "run_godot_tool", side_effect=apply), patch.object(IM, "_list", side_effect=readback):
            with self.assertRaises(C.GamekitError) as caught:
                IM.set_actions(self.project, {"jump": {"events": [{"key": "Space"}]}}, "fault.input.1")
        self.assertEqual(caught.exception.code, "READBACK_MISMATCH")
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertIsNone(C.Journal(self.project).find("fault.input.1"))

    def test_kit_rolls_back_config_and_copied_files_on_preservation_failure(self):
        def apply(_project, request, _timeout):
            target = self.project.res_to_path(request["temp_out"])
            target.write_bytes(b'config_version=5\n[autoload]\nHHSave="*res://addons/hh_kits/save/hh_save.gd"\n')
            return {"ok": True}

        def readback(*_args):
            self._corrupt()
            return {"autoloads": {"HHSave": "*res://addons/hh_kits/save/hh_save.gd"}, "scripts": [], "scenes": []}

        with patch.object(C, "refuse_if_editor_open"), patch.object(K, "_apply_settings_tool", side_effect=apply), patch.object(K, "_readback", side_effect=readback), patch.object(K, "_scene_clean", return_value={}):
            with self.assertRaises(C.GamekitError) as caught:
                K.add_kit(self.project, "save", "fault.kit.1")
        self.assertEqual(caught.exception.code, "READBACK_MISMATCH")
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertFalse((self.game / "addons/hh_kits/save/hh_save.gd").exists())
        self.assertIsNone(C.Journal(self.project).find("fault.kit.1"))


if __name__ == "__main__":
    unittest.main()

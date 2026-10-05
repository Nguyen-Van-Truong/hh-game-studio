"""Owner publication eligibility tests (no Godot process is needed).

These tests exercise only the narrow lexical/file-policy boundary.  Native
Godot remains responsible for GDScript grammar, types, and dependency closure.
"""
import importlib.util
from pathlib import Path
import unittest


STUDIO = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "gameplay_source_eligibility_tests",
    STUDIO / "godot-addon/gameplay_source_eligibility.py",
)
eligibility = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(eligibility)


def _gd(body: str) -> bytes:
    return body.encode("utf-8")


def _scene(body: str) -> bytes:
    return body.encode("utf-8")


class GameplaySourceEligibilityTests(unittest.TestCase):
    def assert_accepts(self, files):
        self.assertIsNone(eligibility.validate_publication_sources(files))

    def assert_rejects(self, files):
        with self.assertRaises(eligibility.PublicationEligibilityError):
            eligibility.validate_publication_sources(files)

    def test_tool_in_comment_and_quoted_forms_is_not_an_annotation(self):
        self.assert_accepts({
            "scripts/main.gd": _gd(
                '# @tool\n'
                'var ordinary = "@tool"\n'
                "var single = '@tool'\n"
                'var escaped = "quote: \\\" then @tool"\n'
                'var triple = """@tool\ninside triple"""\n'
                "var triple_single = '''@tool'''\n"
                'var raw = r"@tool \\\" still raw text"\n'
                "var raw_single = r'@tool \\' still raw text'\n"
                'extends Node3D\n'
            ),
        })

    def test_tool_in_a_secondary_script_is_still_rejected(self):
        self.assert_rejects({
            "scripts/main.gd": _gd("extends Node3D\n"),
            "scripts/secondary.gd": _gd(
                "# harmless header\n@tool\nextends Node3D\n"
            ),
        })

    def test_unterminated_gd_string_fails_closed(self):
        self.assert_rejects({
            "scripts/main.gd": _gd('extends Node3D\nvar text = "unterminated\n'),
        })

    def test_scene_external_script_and_normal_data_are_allowed(self):
        self.assert_accepts({
            "scripts/main.gd": _gd("extends Node3D\n"),
            "scenes/main.tscn": _scene(
                '[gd_scene load_steps=2 format=3]\n'
                '[ext_resource type="Script" path="res://scripts/main.gd" id="1"]\n'
                '[node name="Main" type="Node3D"]\n'
                'script = ExtResource("1")\n'
                'metadata/description = "script/source and Object(GDScript) are text"\n'
                'metadata/color = #ff00ff\n'
            ),
        })

    def test_scene_embedded_script_declarations_are_rejected(self):
        for source in (
            '[sub_resource type="GDScript" id="Script_1"]\n',
            '[sub_resource type="CSharpScript" id="Script_1"]\n',
            '[sub_resource type="NativeScript" id="Script_1"]\n',
            '[sub_resource type="GDExtension" id="Script_1"]\n',
            '[sub_resource type="Script" id="Script_1"]\n',
            'script/source = "extends Node3D\\n"\n',
            'source_code = "extends Node3D\\n"\n',
        ):
            with self.subTest(source=source):
                self.assert_rejects({"scenes/main.tscn": _scene(source)})

    def test_scene_reserved_keys_and_types_decode_escaped_spellings(self):
        cases = (
            'script\\u002fsource = "extends Node3D\\n"\n',
            'source\\u005fcode = "extends Node3D\\n"\n',
            '[sub_resource type="\\u0047DScript" id="Script_1"]\n',
            '[sub_resource type="\\u0047DExtension" id="Script_1"]\n',
        )
        for source in cases:
            with self.subTest(source=source):
                self.assert_rejects({"scenes/main.tscn": _scene(source)})

    def test_scene_split_reserved_keys_are_rejected_and_comments_are_ignored(self):
        self.assert_rejects({
            "scenes/main.tscn": _scene(
                'script / source = "extends Node3D\\n"\n'
                '; source_code = "this is a comment"\n'
            ),
        })
        self.assert_accepts({
            "scenes/main.tscn": _scene(
                '; script/source = "comment only"\n'
                '[node name="Main" type="Node3D"]\n'
            ),
        })

    def test_scene_object_construction_is_rejected_outside_strings(self):
        self.assert_rejects({
            "scenes/main.tscn": _scene(
                '[node name="Main" type="Node3D"]\n'
                'metadata/payload = Object(GDScript)\n'
            ),
        })
        self.assert_accepts({
            "scenes/main.tscn": _scene(
                '[node name="Main" type="Node3D"]\n'
                'metadata/payload = "Object(GDScript); script/source"\n'
            ),
        })

    def test_unterminated_scene_quote_fails_closed(self):
        self.assert_rejects({
            "scenes/main.tscn": _scene(
                '[node name="Main" type="Node3D"]\n'
                'metadata/description = "unterminated; Object(GDScript)\n'
            ),
        })

    def test_unsupported_file_kinds_are_rejected(self):
        for name in (
            "scripts/plugin.gdextension",
            "scripts/legacy.cs",
            "scenes/data.tres",
            "assets/texture.png",
        ):
            with self.subTest(name=name):
                self.assert_rejects({name: b"opaque bytes"})


if __name__ == "__main__":
    unittest.main()

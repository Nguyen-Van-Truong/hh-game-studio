"""Pure closed-profile tests. No Godot, sandbox or publication assertions."""
from dataclasses import FrozenInstanceError, replace
import hashlib
import importlib.util
import itertools
from pathlib import Path
import sys
import unittest


STUDIO = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('gt03_script_profile', STUDIO / 'godot-addon/script_profile.py')
profile = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = profile
SPEC.loader.exec_module(profile)


def script(fixture='23', move=None, turn=None, enabled=None):
    rows = ['extends Node3D', f'@export var fixture_value: int = {fixture}']
    for name, gd_type, value in (('move_speed', 'float', move), ('turn_speed', 'float', turn), ('enabled', 'bool', enabled)):
        if value is not None:
            rows.append(f'@export var {name}: {gd_type} = {value}')
    return ('\n'.join(rows) + '\n').encode('utf-8')


class ScriptProfileTests(unittest.TestCase):
    def reject(self, raw, code='UNSUPPORTED_SCRIPT_PROFILE'):
        with self.assertRaises(profile.ScriptProfileError) as caught:
            profile.validate_script(raw)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_minimal_original_bytes_and_digest(self):
        raw = script()
        result = profile.validate_script(raw)
        self.assertIs(result.source_bytes, raw)
        self.assertEqual(result.sha256, hashlib.sha256(raw).hexdigest())
        self.assertEqual(result.profile, 'hh-godot-declarative-1')
        self.assertEqual(result.defaults, {'fixture_value': 23})

    def test_all_typed_values_and_original_literals(self):
        result = profile.validate_script(script('-42', '7.0', '90.125', 'false'))
        self.assertEqual(result.defaults, {'fixture_value': -42, 'move_speed': 7.0, 'turn_speed': 90.125, 'enabled': False})
        self.assertEqual([type(item.value) for item in result.declarations], [int, float, float, bool])
        self.assertEqual([(item.name, item.gd_type, item.literal) for item in result.declarations],
            [('fixture_value', 'int', '-42'), ('move_speed', 'float', '7.0'), ('turn_speed', 'float', '90.125'), ('enabled', 'bool', 'false')])

    def test_every_optional_combination(self):
        for present in itertools.product((False, True), repeat=3):
            with self.subTest(present=present):
                result = profile.validate_script(script(move='1.0' if present[0] else None,
                    turn='2.0' if present[1] else None, enabled='true' if present[2] else None))
                self.assertEqual(len(result.declarations), 1 + sum(present))
                self.assertEqual('move_speed' in result.defaults, present[0])
                self.assertEqual('turn_speed' in result.defaults, present[1])
                self.assertEqual('enabled' in result.defaults, present[2])

    def test_integer_boundaries(self):
        for value in ('-1000000', '0', '1000000'):
            with self.subTest(value=value):
                self.assertEqual(profile.validate_script(script(value)).defaults['fixture_value'], int(value))

    def test_float_boundaries_and_fraction(self):
        for move, turn in (('0.0', '0.0'), ('100.0', '360.0'), ('0.000001', '359.999999')):
            with self.subTest(move=move, turn=turn):
                values = profile.validate_script(script(move=move, turn=turn)).defaults
                self.assertEqual(values['move_speed'], float(move))
                self.assertEqual(values['turn_speed'], float(turn))

    def test_exact_byte_cap_is_eligible(self):
        prefix = script() + b'@export var move_speed: float = 0.'
        raw = prefix + b'1' * (profile.MAX_SCRIPT_BYTES - len(prefix) - 1) + b'\n'
        self.assertEqual(len(raw), 16384)
        self.assertEqual(profile.validate_script(raw).sha256, hashlib.sha256(raw).hexdigest())

    def test_oversized_even_if_invalid_utf8(self):
        for raw in (b'A' * 16385, b'\xff' * 16385):
            with self.subTest(kind=raw[:1]):
                error = self.reject(raw, 'BAD_SCRIPT_BYTES')
                self.assertEqual(error.reason, 'byte limit')

    def test_reject_nonbytes_and_subclasses(self):
        class BytesSubclass(bytes):
            pass
        for raw in (None, '', bytearray(script()), memoryview(script()), BytesSubclass(script()), 42):
            with self.subTest(kind=type(raw)):
                self.reject(raw, 'BAD_SCRIPT_BYTES')

    def test_invalid_utf8(self):
        for suffix in (b'\xff', b'\xc0\xaf', b'\xed\xa0\x80', b'\xe2\x82'):
            with self.subTest(suffix=suffix):
                self.reject(script() + suffix, 'BAD_SCRIPT_BYTES')

    def test_empty_missing_fixture_and_blank_source(self):
        for raw in (b'', b'\n', b'extends Node3D\n', b'extends Node3D\n@export var enabled: bool = true\n'):
            with self.subTest(raw=raw):
                self.reject(raw)

    def test_exact_lf_and_spacing(self):
        raw = script()
        variants = (raw.rstrip(b'\n'), raw + b'\n', b'\n' + raw, raw.replace(b'\n', b'\r\n'),
            raw.replace(b'\n', b'\r'), raw.replace(b' = ', b'='), raw.replace(b': ', b':'),
            raw.replace(b'@export ', b'@export\t'), raw.replace(b'Node3D\n', b'Node3D \n'),
            raw.replace(b'@export', b' @export'), raw.replace(b'23\n', b'23 \n'))
        for mutated in variants:
            with self.subTest(mutated=mutated):
                self.reject(mutated)

    def test_bom_nul_and_ascii_control_characters(self):
        for raw in (b'\xef\xbb\xbf' + script(), script() + b'\x00', script().replace(b'23', b'2\x003'),
                    script().replace(b'\n', b'\x0b'), script().replace(b'23', b'23\x1b[0m')):
            with self.subTest(raw=raw):
                self.reject(raw)

    def test_unicode_digits_identifiers_and_whitespace(self):
        for source in (script().decode().replace('23', '２３'), script().decode().replace('23', '٢٣'),
            script().decode().replace('fixture', 'fıxture'), script().decode().replace(' ', '\u00a0'),
            script().decode().replace('\n', '\u2028'), script().decode().replace('23', '2\u200b3')):
            with self.subTest(source=source):
                self.reject(source.encode('utf-8'))

    def test_escaped_unicode_and_line_continuations(self):
        for replacement in (b'\\u0032\\u0033', b'\\x32\\x33', b'2\\\n3', b'23\\n@tool', b'23\\\n'):
            with self.subTest(replacement=replacement):
                self.reject(script().replace(b'23', replacement))

    def test_exact_native_base_only(self):
        for base in (b'Node', b'node3D', b'Node3D ', b'"res://base.gd"', b'Node3D.Inner', b'Node3D; @tool'):
            with self.subTest(base=base):
                self.reject(script().replace(b'Node3D', base))

    def test_names_types_and_annotations(self):
        for old, new in ((b'fixture_value', b'unknown'), (b'fixture_value', b'_fixture_value'),
            (b': int', b': float'), (b': int', b': Int'), (b'@export', b'@export_range(0, 100)'),
            (b'@export var', b'var'), (b'@export var', b'@export static var')):
            with self.subTest(new=new):
                self.reject(script().replace(old, new))

    def test_optional_type_mismatch(self):
        for old, new in ((b'move_speed: float', b'move_speed: int'), (b'turn_speed: float', b'turn_speed: String'),
                         (b'enabled: bool', b'enabled: int')):
            with self.subTest(new=new):
                self.reject(script(move='7.0', turn='90.0', enabled='true').replace(old, new))

    def test_duplicate_declarations_and_too_many(self):
        for raw in (script() + b'@export var fixture_value: int = 24\n',
                    script(move='1.0') + b'@export var move_speed: float = 2.0\n',
                    script(move='1.0', turn='2.0', enabled='true') + b'@export var enabled: bool = false\n'):
            with self.subTest(raw=raw):
                self.reject(raw)

    def test_fixed_order_for_required_and_optional_names(self):
        rows = script(move='1.0', turn='2.0', enabled='true').splitlines(keepends=True)
        for indices in ((0, 2, 1, 3, 4), (0, 1, 3, 2, 4), (0, 1, 4, 2, 3)):
            with self.subTest(indices=indices):
                self.reject(b''.join(rows[index] for index in indices))

    def test_integer_spelling_and_range(self):
        values = ('-0', '+0', '+23', '00', '023', '-023', '23.0', '1e2', '0x17', '0b10', '1_000',
                  '1000001', '-1000001', '9' * 8000, 'true', 'false', 'NaN', 'INF', 'null')
        for value in values:
            with self.subTest(value=value[:30]):
                self.reject(script(value))

    def test_float_spelling_and_range(self):
        values = ('-0.0', '+0.0', '-1.0', '0', '7', '.5', '7.', '07.0', '7.00', '1.230', '1e1',
                  '1_0.0', '0x1.0', 'nan', 'NaN', 'INF', 'Infinity', '100.000001', '101.0', 'true')
        for value in values:
            with self.subTest(value=value):
                self.reject(script(move=value))
        self.reject(script(turn='360.000001'))

    def test_float_rounding_cannot_bypass_exact_range(self):
        self.assertEqual(float('100.00000000000000001'), 100.0)
        self.reject(script(move='100.00000000000000001'))
        self.reject(script(turn='360.00000000000000001'))

    def test_nonzero_float_underflow_is_unsupported(self):
        self.reject(script(move='0.' + '0' * 1000 + '1'))

    def test_boolean_spelling(self):
        for value in ('True', 'False', '1', '0', 'true or false', 'not false', 'null', '"true"'):
            with self.subTest(value=value):
                self.reject(script(enabled=value))

    def test_expression_and_call_injection(self):
        values = ('1 + 2', '(23)', 'abs(23)', 'int("23")', '1; print("forged")',
                  '23 # ignored', '23\nprint("forged")', '23\n@tool', '23\nfunc _init() -> void:\n\tpass')
        for value in values:
            with self.subTest(value=value):
                self.reject(script(value))

    def test_no_comments_or_multiline_strings(self):
        for raw in (b'# comment\n' + script(), script() + b'# comment\n', script().replace(b'23', b'23 # comment'),
                    script().replace(b'23', b'"""23\n@tool\n"""'), script().replace(b'23', b"'''23'''")):
            with self.subTest(raw=raw):
                self.reject(raw)

    def test_no_tool_static_init_or_methods(self):
        additions = (b'@tool\n', b'class_name Candidate\n', b'static var x: int = 1\n',
            b'static func _static_init() -> void:\n\tprint("forged")\n',
            b'func _ready() -> void:\n\tget_tree().quit(0)\n', b'class Inner:\n\textends Node3D\n')
        for extra in additions:
            with self.subTest(extra=extra):
                self.reject(extra + script())
                self.reject(script() + extra)

    def test_property_hooks_are_unsupported(self):
        for suffix in (b':\n\tset(value):\n\t\tpass\n', b':\n\tget:\n\t\treturn 23\n'):
            with self.subTest(suffix=suffix):
                self.reject(script().rstrip(b'\n') + suffix)
        self.reject(script() + b'func _get(property: StringName) -> Variant:\n\treturn null\n')

    def test_resources_and_external_inheritance_are_unsupported(self):
        for value in ('preload("res://evil.gd")', 'load("res://evil.tres")', 'ResourceLoader.load("res://evil.gd")',
                      'FileAccess.open("/tmp/report", FileAccess.WRITE)', 'OS.execute("sh", [])'):
            with self.subTest(value=value):
                self.reject(script(value))
        self.reject(script() + b'const Other = preload("res://evil.gd")\n')

    def test_detached_defaults_cannot_modify_result(self):
        result = profile.validate_script(script(move='7.0'))
        defaults = result.defaults
        defaults.clear()
        defaults['fixture_value'] = 100
        self.assertEqual(result.defaults, {'fixture_value': 23, 'move_speed': 7.0})
        self.assertIsNot(result.defaults, result.defaults)

    def test_result_and_declarations_are_frozen(self):
        result = profile.validate_script(script())
        for name, value in (('source_bytes', script('24')), ('sha256', '0' * 64), ('declarations', ()), ('profile', 'fake')):
            with self.subTest(name=name), self.assertRaises(FrozenInstanceError):
                setattr(result, name, value)
        with self.assertRaises(FrozenInstanceError):
            result.declarations[0].literal = '24'
        self.assertIsInstance(result.declarations, tuple)

    def test_direct_construction_and_replace_revalidate(self):
        self.assertEqual(profile.ValidatedScriptProfile(script()).defaults, {'fixture_value': 23})
        with self.assertRaises(profile.ScriptProfileError):
            profile.ValidatedScriptProfile(b'@tool\n')
        result = profile.validate_script(script())
        with self.assertRaises(profile.ScriptProfileError):
            replace(result, source_bytes=b'@tool\n')
        with self.assertRaises(ValueError):
            replace(result, sha256='0' * 64)
        with self.assertRaises(TypeError):
            profile.ValidatedScriptProfile(script(), sha256='0' * 64)

    def test_changed_original_literal_changes_hash_without_rewriting(self):
        first, second = profile.validate_script(script('23')), profile.validate_script(script('24'))
        self.assertNotEqual(first.sha256, second.sha256)
        self.assertEqual(second.source_bytes, script('24'))
        self.assertEqual(second.declarations[0].literal, '24')

    def test_errors_do_not_echo_candidate_source(self):
        marker = 'DO_NOT_REFLECT_CANDIDATE'
        error = self.reject(script(marker))
        self.assertNotIn(marker, str(error))
        self.assertNotIn(marker, error.reason)


if __name__ == '__main__':
    unittest.main()

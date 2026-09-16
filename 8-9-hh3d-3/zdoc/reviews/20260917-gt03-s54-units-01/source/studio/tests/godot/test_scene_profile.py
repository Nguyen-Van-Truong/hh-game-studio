"""Closed scene grammar tests only; no Godot process or publication evidence."""
from dataclasses import FrozenInstanceError, replace
import hashlib
import importlib.util
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest


STUDIO = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


scene = load('gt03_scene_profile', STUDIO / 'godot-addon/scene_profile.py')
SCRIPT = b'extends Node3D\n@export var fixture_value: int = 7\n'
ALL_SCRIPT = SCRIPT + (b'@export var move_speed: float = 2.5\n'
    b'@export var turn_speed: float = 90.0\n@export var enabled: bool = true\n')
UID = b'uid://dc8011bj471fi\n'
ROOT = '[node name="Fixture" type="Node3D"]\nscript = ExtResource("1_script")\nmetadata/hh_studio_id = "root"'
EXTERNAL = '[ext_resource type="Script" path="res://scripts/fixture_actor.gd" id="1_script"]'
# Copied byte-for-byte from S48 editor-02/packed-scene.tscn (original LF form).
ACTUAL = b'''[gd_scene format=3 uid="uid://c4p3hprrm2xq3"]

[ext_resource type="Script" uid="uid://dc8011bj471fi" path="res://scripts/fixture_actor.gd" id="1_ycb52"]

[sub_resource type="BoxMesh" id="BoxMesh_23b4i"]
size = Vector3(3, 3, 3)

[node name="Fixture" type="Node3D" unique_id=1841640435]
script = ExtResource("1_ycb52")
fixture_value = 23
metadata/hh_studio_id = "root"

[node name="BoxOne" type="MeshInstance3D" parent="." unique_id=1178873135]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 4, 5, 6)
mesh = SubResource("BoxMesh_23b4i")
metadata/hh_studio_id = "box-one"
'''


def child(name='Child', parent='.', stable_id='child', mesh=None, transform=None, extras=''):
    node_type = 'Node3D' if mesh is None else 'MeshInstance3D'
    rows = [f'[node name="{name}" type="{node_type}" parent="{parent}"{extras}]']
    if transform is not None:
        rows.append(f'transform = Transform3D({transform})')
    if mesh is not None:
        rows.append(f'mesh = SubResource("{mesh}")')
    rows.append(f'metadata/hh_studio_id = "{stable_id}"')
    return '\n'.join(rows)


def source(*blocks, header='[gd_scene load_steps=2 format=3]', external=EXTERNAL, root=ROOT):
    return ('\n\n'.join((header, external, root, *blocks)) + '\n').encode()


def with_box(*, transform=None, size='Vector3(1, 1, 1)', mesh_properties=None):
    resource = '[sub_resource type="BoxMesh" id="BoxMesh_one"]'
    if size is not None:
        resource += '\nsize = ' + size
    if mesh_properties is not None:
        resource += '\n' + mesh_properties
    return ('\n\n'.join(('[gd_scene load_steps=3 format=3]', EXTERNAL, resource, ROOT,
                        child(mesh='BoxMesh_one', transform=transform))) + '\n').encode()


class SceneProfileTests(unittest.TestCase):
    def valid(self, raw, *, script=SCRIPT, uid=UID):
        return scene.validate_scene(raw, script_uid=uid, script_source=script)

    def reject(self, raw, *, script=SCRIPT, uid=UID, code='UNSUPPORTED_SCENE_PROFILE'):
        with self.assertRaises((scene.SceneProfileError, scene.script_profile.ScriptProfileError)) as caught:
            self.valid(raw, script=script, uid=uid)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_actual_godot_saved_scene(self):
        self.assertEqual(hashlib.sha256(ACTUAL).hexdigest(), '632f01d8f10becd46bc3b813087ffa4d0fc749e27232dae27a0778c7c5cd7242')
        result = self.valid(ACTUAL)
        self.assertIs(result.source_bytes, ACTUAL)
        self.assertEqual(result.sha256, hashlib.sha256(ACTUAL).hexdigest())
        self.assertEqual(result.scene_uid, 'uid://c4p3hprrm2xq3')
        self.assertEqual(result.script_uid, UID.decode().rstrip('\n'))
        self.assertTrue(result.script_uid_declared)
        self.assertEqual(result.script_sha256, hashlib.sha256(SCRIPT).hexdigest())
        self.assertEqual(result.script_uid_sha256, hashlib.sha256(UID).hexdigest())
        self.assertEqual(result.nodes[0].export_values[0].value, 23)
        self.assertEqual(result.nodes[1].transform_rows_origin[9:], (4.0, 5.0, 6.0))
        self.assertEqual(result.nodes[1].box_size, (3.0, 3.0, 3.0))
        self.assertEqual(result.nodes[1].unique_id, 1178873135)

    def test_initial_scene_without_uids_and_effective_defaults(self):
        result = self.valid(source())
        self.assertIsNone(result.scene_uid)
        self.assertFalse(result.script_uid_declared)
        node = result.nodes[0]
        self.assertEqual(node.path, '.')
        self.assertEqual(node.owner_id, '')
        self.assertEqual(node.scale, (1.0, 1.0, 1.0))
        self.assertEqual(node.export_values[0].value, 7)
        self.assertNotIn('fixture_value', {prop.name for prop in node.declared_properties})

    def test_uid_header_without_load_steps(self):
        self.assertEqual(len(self.valid(source(header='[gd_scene format=3 uid="uid://b"]')).nodes), 1)

    def test_nested_owner_paths_and_sibling_order(self):
        result = self.valid(source(child('A', stable_id='a'), child('B', parent='A', stable_id='b', extras=' owner="."'),
                                   child('C', stable_id='c')))
        self.assertEqual([(n.path, n.parent_id, n.owner_id, n.sibling_index) for n in result.nodes],
                         [('.', '', '', 0), ('A', 'root', 'root', 0), ('A/B', 'a', 'root', 0), ('C', 'root', 'root', 1)])

    def test_boxmesh_default_and_explicit_size(self):
        default = self.valid(with_box(size=None)).resources[0]
        self.assertEqual(default.size, (1.0, 1.0, 1.0))
        self.assertEqual(default.declared_properties, ())
        explicit = self.valid(with_box(size='Vector3(0.001, 1e+2, 1000)')).resources[0]
        self.assertEqual(explicit.size, (struct.unpack('!f', struct.pack('!f', 0.001))[0], 100.0, 1000.0))

    def test_rotation_nonuniform_scale_uses_basis_columns(self):
        result = self.valid(with_box(transform='0, -3, 0, 2, 0, 0, 0, 0, 4, -10000, 0, 10000'))
        self.assertEqual(result.nodes[1].scale, (2.0, 3.0, 4.0))
        self.assertEqual(result.nodes[1].transform_rows_origin[:9], (0.0, -3.0, 0.0, 2.0, 0.0, 0.0, 0.0, 0.0, 4.0))

    def test_scientific_and_signed_zero_transforms(self):
        result = self.valid(with_box(transform='1, -4.37114e-08, 0, 4.37114e-08, 1, -0, 0, 0, 1, 1e-03, -0.0, 0'))
        self.assertEqual(len(result.nodes[1].transform_rows_origin), 12)
        self.assertGreater(result.nodes[1].transform_rows_origin[9], 0)

    def test_rounded_rotation_is_eligible(self):
        self.valid(with_box(transform='0.707107, -1.41421, 0, 0.707107, 1.41421, 0, 0, 0, 3, 0, 0, 0'))

    def test_positive_scale_boundaries(self):
        for scale in ('0.001', '1000'):
            with self.subTest(scale=scale):
                self.valid(with_box(transform=f'{scale}, 0, 0, 0, {scale}, 0, 0, 0, {scale}, 0, 0, 0'))

    def test_declared_root_overrides_and_effective_metadata(self):
        root = ROOT.replace('metadata/', 'fixture_value = -1000000\nmove_speed = 7\nturn_speed = 3.6e+2\nenabled = false\nmetadata/')
        snapshot = self.valid(source(root=root), script=ALL_SCRIPT).snapshot()
        self.assertEqual(snapshot['nodes'][0]['exports'], {
            'fixture_value': {'kind': 'int', 'value': -1000000}, 'move_speed': {'kind': 'float', 'value': 7.0},
            'turn_speed': {'kind': 'float', 'value': 360.0}, 'enabled': {'kind': 'bool', 'value': False}})
        self.assertEqual(snapshot['nodes'][0]['declared_properties']['move_speed'], {'kind': 'int', 'value': 7})
        self.assertEqual(snapshot['nodes'][0]['declared_properties']['turn_speed'], {'kind': 'float', 'value': 360.0})

    def test_partial_overrides_leave_script_defaults(self):
        root = ROOT.replace('metadata/', 'fixture_value = 23\nmetadata/')
        result = self.valid(source(root=root), script=ALL_SCRIPT)
        self.assertEqual([prop.value for prop in result.nodes[0].export_values], [23, 2.5, 90.0, True])

    def test_64_nodes_supported_65_rejected(self):
        blocks = [child(f'N{index}', stable_id=f'n{index}') for index in range(1, 65)]
        self.assertEqual(len(self.valid(source(*blocks[:63])).nodes), 64)
        self.reject(source(*blocks))

    def test_complete_maximum_unshared_resource_graph(self):
        resources = [f'[sub_resource type="BoxMesh" id="BoxMesh_{index}"]' for index in range(63)]
        children = [child(f'N{index}', stable_id=f'n{index}', mesh=f'BoxMesh_{index}') for index in range(63)]
        raw = ('\n\n'.join(('[gd_scene load_steps=65 format=3]', EXTERNAL, *resources, ROOT, *children)) + '\n').encode()
        result = self.valid(raw)
        self.assertEqual(len(result.nodes), 64)
        self.assertEqual(len(result.resources), 63)

    def test_maximum_name_stable_id_and_resource_id_lengths(self):
        name, stable_id = 'A' * 48, 'a' * 64
        self.assertEqual(self.valid(source(child(name, stable_id=stable_id))).nodes[1].stable_id, stable_id)
        raw = with_box().replace(b'BoxMesh_one', b'B' * 64).replace(b'1_script', b'C' * 64)
        self.assertEqual(len(self.valid(raw).resources[0].resource_id), 64)

    def test_depth_16_supported_17_rejected(self):
        blocks, parent = [], '.'
        for index in range(1, 17):
            name = f'N{index}'
            blocks.append(child(name, parent=parent, stable_id=f'n{index}'))
            parent = name if parent == '.' else parent + '/' + name
        self.assertEqual(len(self.valid(source(*blocks[:15])).nodes), 16)
        self.reject(source(*blocks))

    def test_bad_byte_envelopes(self):
        for raw in (None, '', bytearray(source()), b'\xff', b'x' * (scene.MAX_SCENE_BYTES + 1)):
            with self.subTest(kind=type(raw)):
                self.reject(raw, code='BAD_SCENE_BYTES')

    def test_bad_uid_byte_envelopes(self):
        for uid in (None, '', bytearray(UID), b'\xff', b'x' * 129):
            with self.subTest(kind=type(uid)):
                self.reject(source(), uid=uid, code='BAD_SCRIPT_UID_BYTES')

    def test_unsupported_uid_sidecar(self):
        for uid in (b'', b'uid://b', b'uid://b\r\n', b'uid://b\n\n', b'uid://z\n', b'uid://9\n',
                    b'uid://ab\n', b'uid://8888888888888\n', b'uid://<invalid>\n', b'uid://b\\n\n'):
            with self.subTest(uid=uid):
                self.reject(source(), uid=uid)

    def test_uid_range_and_zero_canonical_spelling(self):
        self.valid(source(), uid=b'uid://a\n')
        self.valid(source(), uid=b'uid://d4n4ub6itg400\n')
        self.reject(source(), uid=b'uid://d4n4ub6itg401\n')

    def test_explicit_uid_mismatch_or_collision(self):
        self.reject(ACTUAL, uid=b'uid://b\n')
        self.reject(source(header='[gd_scene format=3 uid="uid://dc8011bj471fi"]'))

    def test_script_profile_reused_and_errors_propagate(self):
        self.reject(source(), script=b'@tool\nextends Node3D\n', code='UNSUPPORTED_SCRIPT_PROFILE')
        self.reject(source(), script=b'\xff', code='BAD_SCRIPT_BYTES')
        self.assertEqual(scene.script_profile._source_sha256, scene.SCRIPT_PROFILE_SHA256)

    def test_source_bound_dependency_rejects_modified_sibling(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            shutil.copyfile(STUDIO / 'godot-addon/scene_profile.py', path / 'scene_profile.py')
            (path / 'script_profile.py').write_bytes(b'raise RuntimeError("must not execute")\n')
            with self.assertRaisesRegex(ImportError, 'source mismatch'):
                load('scene_profile_changed_sibling', path / 'scene_profile.py')

    def test_dependency_modules_do_not_cross_snapshot_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            for name in ('scene_profile.py', 'script_profile.py'):
                shutil.copyfile(STUDIO / 'godot-addon' / name, path / name)
            other = load('scene_profile_other_snapshot', path / 'scene_profile.py')
            self.assertIsNot(scene.script_profile, other.script_profile)
            self.assertEqual(other.validate_scene(source(), script_uid=UID, script_source=SCRIPT).sha256,
                             self.valid(source()).sha256)

    def test_line_and_section_caps(self):
        self.reject(source(root=ROOT + '\n' + 'x' * 4097))
        self.reject(source(*['[connection]'] * 130))

    def test_noncanonical_whitespace_and_comments(self):
        raw = source()
        variants = (raw.rstrip(b'\n'), raw + b'\n', b'\n' + raw, raw.replace(b'\n', b'\r\n'),
            raw.replace(b'\n\n', b'\n\n\n'), raw.replace(b'\n\n', b'\n'), raw.replace(b' = ', b'='),
            b'# comment\n' + raw, raw.replace(b'format=3', b'format=3 # comment'),
            raw.replace(b'"root"', b'"root" # comment'))
        for mutated in variants:
            with self.subTest(mutated=mutated[:80]):
                self.reject(mutated)

    def test_unicode_bom_nul_and_escaped_strings(self):
        for raw in (b'\xef\xbb\xbf' + source(), source() + b'\x00', source().replace(b'Fixture', 'Fıxture'.encode()),
            source().replace(b'Fixture', b'Fix\\u0074ure'), source().replace(b'root', b'ro\\x6ft'),
            source().replace(b'root', b'ro\not'), source().replace(b'root', b'ro\\not')):
            with self.subTest(raw=raw[:100]):
                self.reject(raw)

    def test_quote_terminator_and_section_injection(self):
        for replacement in (b'root"]', b'root"\nscript = preload("evil")\n"', b'root\\"', b'root"; print(1); "'):
            with self.subTest(replacement=replacement):
                self.reject(source().replace(b'root', replacement))

    def test_unknown_header_fields_and_duplicate_fields(self):
        for header in ('[gd_scene format=2]', '[gd_scene format=3 format=3]', '[gd_scene format=3 script="x"]',
                       '[gd_scene format=3 load_steps=2]', '[gd_scene load_steps=3 format=3]', '[gd_scene load_steps=0 format=3]'):
            with self.subTest(header=header):
                self.reject(source(header=header))

    def test_external_resource_graph_closed(self):
        for external in (EXTERNAL.replace('fixture_actor.gd', 'other.gd'), EXTERNAL.replace('Script', 'PackedScene'),
            EXTERNAL.replace('res://', '../'), EXTERNAL.replace('res://', 'user://'),
            EXTERNAL + '\n\n' + EXTERNAL, EXTERNAL.replace(' id=', ' preload="x" id='),
            EXTERNAL.replace('id="1_script"', 'id="1_script" id="other"')):
            with self.subTest(external=external):
                self.reject(source(external=external))

    def test_external_and_internal_resource_id_limits(self):
        self.reject(source().replace(b'1_script', b'A' * 65))
        self.reject(with_box().replace(b'BoxMesh_one', b'A' * 65))
        self.reject(with_box().replace(b'BoxMesh_one', b'1_script'))

    def test_unknown_resource_type_or_fields(self):
        self.reject(with_box().replace(b'type="BoxMesh"', b'type="GDScript"'))
        for field in ('script = ExtResource("1_script")', 'resource_path = "res://evil"', 'resource_local_to_scene = true',
                      'material = ExtResource("other")', 'subdivide_width = 2', 'code = "@tool"'):
            with self.subTest(field=field):
                self.reject(with_box(mesh_properties=field))

    def test_missing_shared_unused_and_duplicate_resources(self):
        self.reject(source(child(mesh='missing')))
        self.reject(with_box().replace(b'\nmesh = SubResource("BoxMesh_one")', b''))
        self.reject(with_box() + ('\n' + child('Other', stable_id='other', mesh='BoxMesh_one') + '\n').encode())
        self.reject(with_box().split(b'\n\n[node name="Child"')[0] + b'\n')
        duplicate = b'[sub_resource type="BoxMesh" id="BoxMesh_one"]\nsize = Vector3(1, 1, 1)\n\n'
        self.reject(with_box().replace(b'[node name="Fixture"', duplicate + b'[node name="Fixture"'))

    def test_resources_cannot_follow_nodes(self):
        self.reject(source('[sub_resource type="BoxMesh" id="BoxMesh_one"]'))

    def test_missing_root_or_stable_id(self):
        self.reject(source().replace(b'\nmetadata/hh_studio_id = "root"', b''))
        self.reject(source(root='[node name="Fixture" type="MeshInstance3D"]\nmetadata/hh_studio_id = "root"'))
        self.reject(('[gd_scene format=3]\n\n' + EXTERNAL + '\n').encode())

    def test_root_and_child_stable_id_scope(self):
        self.reject(source().replace(b'"root"', b'"other"'))
        self.reject(source(child(stable_id='root')))
        self.reject(source(child('A', stable_id='a'), child('B', stable_id='a')))
        for value in ('Upper', 'a' * 65, '', '../x', 'a/b'):
            with self.subTest(value=value):
                self.reject(source(child(stable_id=value)))

    def test_case_insensitive_sibling_names_and_invalid_names(self):
        self.reject(source(child('A', stable_id='a'), child('a', stable_id='b')))
        for name in ('A' * 49, '_A', '1A', 'A.B', 'A/B', 'A:B'):
            with self.subTest(name=name):
                self.reject(source(child(name=name)))

    def test_parent_path_and_owner_scope(self):
        for parent in ('missing', '..', './Child', '/root/Fixture', 'res://x', '.', 'A/../B'):
            if parent == '.':
                continue
            with self.subTest(parent=parent):
                self.reject(source(child(parent=parent)))
        self.reject(source(child(extras=' owner="Child"')))
        self.reject(source(root=ROOT.replace('type="Node3D"', 'type="Node3D" owner="."')))

    def test_depth_first_order_and_no_forward_parent(self):
        self.reject(source(child('A', stable_id='a'), child('B', stable_id='b'), child('C', parent='A', stable_id='c')))
        self.reject(source(child('B', parent='A', stable_id='b'), child('A', stable_id='a')))

    def test_node_unique_ids(self):
        self.valid(source(child(extras=' unique_id=2147483647')))
        for value in ('0', '-1', '01', '2147483648', '99999999999'):
            with self.subTest(value=value):
                self.reject(source(child(extras=' unique_id=' + value)))
        self.reject(source(child('A', stable_id='a', extras=' unique_id=1'), child('B', stable_id='b', extras=' unique_id=1')))

    def test_unknown_node_fields_sections_connections_and_inheritance(self):
        for extra in (' visible=false', ' groups=["x"]', ' instance=ExtResource("1_script")', ' index="0"',
                      ' node_paths=PackedStringArray("script")', ' parent_id_path=PackedInt32Array(1)'):
            with self.subTest(extra=extra):
                self.reject(source(child(extras=extra)))
        for section in ('[connection signal="ready" from="." to="." method="foo"]', '[editable path="."]', '[resource]'):
            with self.subTest(section=section):
                self.reject(source(section))
        self.reject(source().replace(b'type="Node3D"', b'instance=ExtResource("1_script")'))

    def test_unknown_properties_and_duplicate_assignments(self):
        for line in ('visible = false', 'position = Vector3(1, 2, 3)', 'rotation_degrees = Vector3(0, 0, 0)',
                     'scale = Vector3(1, 1, 1)', 'metadata/other = "x"', 'process_mode = 1',
                     'script/source = "@tool"', 'metadata/hh_studio_id = "root"'):
            with self.subTest(line=line):
                self.reject(source(root=ROOT + '\n' + line))

    def test_script_only_root_and_exact_attachment(self):
        self.reject(source(root=ROOT.replace('script = ExtResource("1_script")\n', '')))
        self.reject(source(root=ROOT.replace('ExtResource("1_script")', 'ExtResource("missing")')))
        self.reject(source(child() + '\nscript = ExtResource("1_script")'))
        self.reject(source(root=ROOT.replace('script = ExtResource("1_script")', 'script = GDScript.new()')))

    def test_exports_only_declared_root_and_after_script(self):
        self.reject(source(root=ROOT + '\nmove_speed = 7'))
        self.reject(source(child() + '\nfixture_value = 23'))
        root = ROOT.replace('script =', 'fixture_value = 23\nscript =')
        self.reject(source(root=root))

    def test_export_types_ranges_and_injection(self):
        for name, value in (('fixture_value', '23.0'), ('fixture_value', 'true'), ('fixture_value', '1000001'),
                           ('fixture_value', '-0'), ('move_speed', '100.00000000000000001'), ('move_speed', '-1'),
                           ('turn_speed', '361'), ('enabled', '1'), ('enabled', 'True'),
                           ('fixture_value', 'preload("res://x.gd")'), ('move_speed', '1 + 2')):
            with self.subTest(name=name, value=value):
                self.reject(source(root=ROOT + f'\n{name} = {value}'), script=ALL_SCRIPT)

    def test_bad_vector_shapes_and_numeric_forms(self):
        values = ('Vector3(1,2,3)', 'Vector3(1, 2)', 'Vector3(1, 2, 3, 4)', 'Vector3(INF, 1, 1)',
                  'Vector3(NaN, 1, 1)', 'Vector3(1e999, 1, 1)', 'Vector3(0x10, 1, 1)',
                  'Vector3(.5, 1, 1)', 'Vector3(01, 1, 1)', 'Vector3(1_0, 1, 1)',
                  'Vector3(0.000999, 1, 1)', 'Vector3(1000.0001, 1, 1)', 'Vector3(-1, 1, 1)',
                  'Vector3(1, 1, 1); print("fake")', 'Vector3(1, 1, load("x"))')
        for size in values:
            with self.subTest(size=size):
                self.reject(with_box(size=size))

    def test_bad_transform_ranges_shear_reflection_and_singularity(self):
        values = ('1, 0, 0, 0, 1, 0, 0, 0, 1, 10000.00001, 0, 0',
                  '1001, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0',
                  '0.0001, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0',
                  '0.000999999, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0',
                  '600, -800.001, 0, 800.001, 600, 0, 0, 0, 1, 0, 0, 0',
                  '1, 0.1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0',
                  '-1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0',
                  '1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0',
                  '1, 0, 0, 0, 1, 0, 0, 0, 1, 1e-100, 0, 0', '1, 0, 0')
        for transform in values:
            with self.subTest(transform=transform):
                self.reject(with_box(transform=transform))

    def test_missing_and_shared_mesh_no_false_defaults(self):
        raw = with_box().replace(b'mesh = SubResource("BoxMesh_one")', b'mesh = null')
        self.reject(raw)
        self.reject(source(root=ROOT + '\nmesh = SubResource("BoxMesh_one")'))

    def test_snapshot_detachment_and_result_immutability(self):
        result = self.valid(ACTUAL)
        snapshot = result.snapshot()
        snapshot['nodes'][0]['exports']['fixture_value']['value'] = 100
        snapshot['nodes'][1]['transform_rows_origin'].clear()
        snapshot['resources'].clear()
        self.assertEqual(result.snapshot()['nodes'][0]['exports']['fixture_value']['value'], 23)
        self.assertEqual(len(result.nodes[1].transform_rows_origin), 12)
        self.assertEqual(len(result.resources), 1)
        with self.assertRaises(FrozenInstanceError):
            result.nodes[0].name = 'Changed'
        with self.assertRaises(FrozenInstanceError):
            result.sha256 = '0' * 64
        with self.assertRaises(FrozenInstanceError):
            result.resources[0].size = ()

    def test_direct_constructor_and_replace_revalidate(self):
        self.assertEqual(scene.ValidatedSceneProfile(source(), UID, SCRIPT).script_uid, UID.decode().strip())
        result = self.valid(source())
        with self.assertRaises(scene.SceneProfileError):
            replace(result, source_bytes=b'evil\n')
        with self.assertRaises(ValueError):
            replace(result, sha256='0' * 64)

    def test_original_hash_changes_without_normalization(self):
        first = self.valid(source())
        second = self.valid(source(header='[gd_scene format=3]'))
        self.assertNotEqual(first.sha256, second.sha256)
        self.assertEqual(first.nodes, second.nodes)

    def test_errors_do_not_reflect_untrusted_source(self):
        marker = 'DO_NOT_REFLECT_CANDIDATE'
        error = self.reject(source(root=ROOT + '\n' + marker))
        self.assertNotIn(marker, str(error))


if __name__ == '__main__':
    unittest.main()

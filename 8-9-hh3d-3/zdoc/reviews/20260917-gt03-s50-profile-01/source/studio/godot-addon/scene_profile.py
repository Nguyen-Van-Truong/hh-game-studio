"""Closed managed-scene eligibility. Never loads a Godot resource or grants ACK.

Import reads only the approved sibling script-profile source. Validation itself
is pure and preserves every original input byte; this is not a Variant parser.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
import hashlib
import importlib.util
import math
from pathlib import Path
import re
import struct
import sys


PROFILE = 'hh-godot-managed-scene-1'
SCRIPT_PATH = 'res://scripts/fixture_actor.gd'
MAX_SCENE_BYTES = 1024 * 1024
MAX_NODES = 64
MAX_DEPTH = 16
MAX_LINE_BYTES = 4096
ORTHOGONAL_EPSILON = 0.000002
SCRIPT_PROFILE_SHA256 = '0aff8d103982e56280b04ad4faca93cf3bd96d086016818daf7b3a432b4de7a5'

_script_path = Path(__file__).with_name('script_profile.py').resolve()
_script_bytes = _script_path.read_bytes()
if hashlib.sha256(_script_bytes).hexdigest() != SCRIPT_PROFILE_SHA256:
    raise ImportError('scene profile script-profile source mismatch')
_script_key = '_hh_scene_script_profile_' + hashlib.sha256(str(_script_path).encode() + b'\0' + _script_bytes).hexdigest()
if _script_key not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_script_key, _script_path)
    _module = importlib.util.module_from_spec(_spec)
    _module._source_sha256 = SCRIPT_PROFILE_SHA256
    sys.modules[_script_key] = _module
    try:
        exec(compile(_script_bytes, str(_script_path), 'exec'), _module.__dict__)
    except BaseException:
        del sys.modules[_script_key]
        raise
script_profile = sys.modules[_script_key]
if (getattr(script_profile, '__file__', None) != str(_script_path)
        or getattr(script_profile, '_source_sha256', None) != SCRIPT_PROFILE_SHA256):
    raise ImportError('scene profile script-profile cache mismatch')

_NAME = r'[A-Za-z][A-Za-z0-9_]{0,47}'
_RESOURCE_ID = r'[A-Za-z0-9_]{1,64}'
_UID = r'uid://[a-y0-8]{1,13}'
_PARENT = rf'(?:\.|{_NAME}(?:/{_NAME}){{0,14}})'
_HEADER = re.compile(rf'\[gd_scene(?: load_steps=([1-9][0-9]{{0,2}}))? format=3(?: uid="({_UID})")?\]\Z')
_EXTERNAL = re.compile(rf'\[ext_resource type="Script"(?: uid="({_UID})")? path="res://scripts/fixture_actor\.gd" id="({_RESOURCE_ID})"\]\Z')
_RESOURCE = re.compile(rf'\[sub_resource type="BoxMesh" id="({_RESOURCE_ID})"\]\Z')
_NODE = re.compile(rf'\[node name="({_NAME})" type="(Node3D|MeshInstance3D)"(?: parent="({_PARENT})")?(?: owner="(\.)")?(?: unique_id=([1-9][0-9]{{0,9}}))?\]\Z')
_ASSIGNMENT = re.compile(r'([a-z_][a-z0-9_/]*) = (.+)\Z')
_STABLE = re.compile(r'"([a-z][a-z0-9._-]{0,63})"\Z')
_NUMBER = re.compile(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:e[+-]?[0-9]{1,3})?\Z')
_INT = re.compile(r'(?:0|-?[1-9][0-9]*)\Z')
_IDENTITY = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0)
_EXPORTS = {'fixture_value': ('int', -1_000_000, 1_000_000), 'move_speed': ('float', 0, 100),
            'turn_speed': ('float', 0, 360), 'enabled': ('bool', None, None)}


class SceneProfileError(ValueError):
    def __init__(self, code: str, reason: str):
        self.code, self.reason = code, reason
        super().__init__(f'{code}: {reason}')


def _need(condition: object, reason: str) -> None:
    if not condition:
        raise SceneProfileError('UNSUPPORTED_SCENE_PROFILE', reason)


def _decode(raw: bytes, limit: int, code: str) -> str:
    if type(raw) is not bytes or len(raw) > limit:
        raise SceneProfileError(code, 'exact bytes within cap required')
    try:
        return raw.decode('utf-8', 'strict')
    except UnicodeDecodeError:
        raise SceneProfileError(code, 'invalid UTF-8') from None


def _uid(value: str) -> str:
    _need(re.fullmatch(_UID, value) is not None, 'UID spelling')
    digits = value[6:]
    _need(len(digits) == 1 or digits[0] != 'a', 'canonical UID')
    alphabet = 'abcdefghijklmnopqrstuvwxy012345678'
    number = 0
    for char in digits:
        number = number * 34 + alphabet.index(char)
    _need(number <= 0x7fffffffffffffff, 'UID range')
    return value


def _number(text: str, lower: float, upper: float, *, real32: bool = False) -> float:
    _need(len(text) <= 64 and _NUMBER.fullmatch(text) is not None, 'numeric literal')
    exact = Decimal(text)
    _need(Decimal(str(lower)) <= exact <= Decimal(str(upper)), 'numeric range')
    value = float(text)
    _need(math.isfinite(value) and (value != 0 or exact == 0), 'numeric representation')
    if real32:
        value = struct.unpack('!f', struct.pack('!f', value))[0]
        _need(math.isfinite(value) and (value != 0 or exact == 0), 'binary32 representation')
    return value


def _vector(text: str) -> tuple[float, float, float]:
    _need(text.startswith('Vector3(') and text.endswith(')'), 'Vector3 form')
    values = text[8:-1].split(', ')
    _need(len(values) == 3, 'Vector3 arity')
    return tuple(_number(value, 0.001, 1000, real32=True) for value in values)


def _transform(text: str) -> tuple[tuple[float, ...], tuple[float, ...]]:
    _need(text.startswith('Transform3D(') and text.endswith(')'), 'Transform3D form')
    values = text[12:-1].split(', ')
    _need(len(values) == 12, 'Transform3D arity')
    result = tuple(_number(value, -1000 if index < 9 else -10000,
                           1000 if index < 9 else 10000, real32=True) for index, value in enumerate(values))
    # VariantWriter serializes basis rows; positive scales are column lengths.
    columns = tuple(tuple(result[row * 3 + col] for row in range(3)) for col in range(3))
    scale = tuple(math.hypot(*column) for column in columns)
    _need(all(0.001 <= value <= 1000 for value in scale), 'positive scale range')
    for left in range(3):
        for right in range(left + 1, 3):
            dot = sum(a * b for a, b in zip(columns[left], columns[right]))
            _need(abs(dot) <= ORTHOGONAL_EPSILON * scale[left] * scale[right], 'sheared basis')
    a, b, c, d, e, f, g, h, i = result[:9]
    determinant = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    _need(determinant > 0, 'reflected or singular basis')
    return result, scale


def _export_value(name: str, text: str) -> int | float | bool:
    gd_type, lower, upper = _EXPORTS[name]
    if gd_type == 'bool':
        _need(text in ('true', 'false'), 'export boolean')
        return text == 'true'
    if gd_type == 'int':
        _need(len(text) <= 8 and _INT.fullmatch(text) is not None, 'export integer')
        value = int(text)
        _need(lower <= value <= upper, 'export range')
        return value
    # Godot text resources may serialize a float without a decimal point.
    value = _number(text, lower, upper)
    return float(int(text)) if '.' not in text and 'e' not in text else value


@dataclass(frozen=True, slots=True)
class SceneProperty:
    name: str
    kind: str
    value: str | int | float | bool | tuple[float, ...]


@dataclass(frozen=True, slots=True)
class BoxResource:
    resource_id: str
    size: tuple[float, ...]
    declared_properties: tuple[SceneProperty, ...]
    resource_type: str = field(default='BoxMesh', init=False)


@dataclass(frozen=True, slots=True)
class SceneNode:
    name: str
    node_type: str
    path: str
    parent_path: str | None
    stable_id: str
    parent_id: str
    owner_id: str
    sibling_index: int
    unique_id: int | None
    transform_rows_origin: tuple[float, ...]
    scale: tuple[float, ...]
    mesh_id: str | None
    box_size: tuple[float, ...] | None
    export_values: tuple[SceneProperty, ...]
    declared_properties: tuple[SceneProperty, ...]


def _properties(lines: list[str]) -> dict[str, str]:
    result = {}
    for line in lines:
        match = _ASSIGNMENT.fullmatch(line)
        _need(match is not None, 'property assignment')
        name, text = match.groups()
        _need(name not in result, 'duplicate property')
        result[name] = text
    return result


def _parse(raw: bytes, script_uid: str, declared_script):
    source = _decode(raw, MAX_SCENE_BYTES, 'BAD_SCENE_BYTES')
    _need(source.isascii() and source.endswith('\n') and '\r' not in source and '\x00' not in source, 'ASCII LF source')
    _need(all(len(line) <= MAX_LINE_BYTES for line in source.split('\n')), 'line limit')
    blocks = [block.split('\n') for block in source[:-1].split('\n\n')]
    _need(3 <= len(blocks) <= 129 and all(block and all(block) for block in blocks), 'section layout')
    header = _HEADER.fullmatch(blocks[0][0]) if len(blocks[0]) == 1 else None
    _need(header is not None, 'scene header')
    load_steps, scene_uid = header.groups()
    if scene_uid is not None:
        _uid(scene_uid)
        _need(scene_uid != script_uid, 'scene/script UID collision')
    external = _EXTERNAL.fullmatch(blocks[1][0]) if len(blocks[1]) == 1 else None
    _need(external is not None, 'exactly one fixed Script external resource')
    external_uid, external_id = external.groups()
    if external_uid is not None:
        _need(_uid(external_uid) == script_uid, 'script UID mismatch')
    resources, nodes, paths, identifiers, unique_ids = {}, [], {}, set(), set()
    used_meshes, siblings, ancestors = set(), {}, []
    script_declarations = {item.name: item for item in declared_script.declarations}
    for block in blocks[2:]:
        resource = _RESOURCE.fullmatch(block[0])
        if resource is not None:
            _need(not nodes and len(resources) < MAX_NODES - 1, 'resource order or count')
            resource_id = resource.group(1)
            _need(resource_id not in resources and resource_id != external_id, 'resource ID collision')
            fields = _properties(block[1:])
            _need(set(fields) <= {'size'}, 'BoxMesh fields')
            size = _vector(fields['size']) if 'size' in fields else (1.0, 1.0, 1.0)
            properties = (SceneProperty('size', 'Vector3', size),) if fields else ()
            resources[resource_id] = BoxResource(resource_id, size, properties)
            continue
        match = _NODE.fullmatch(block[0])
        _need(match is not None and len(nodes) < MAX_NODES, 'node header or limit')
        name, node_type, parent_path, owner, unique_id = match.groups()
        is_root = not nodes
        _need((parent_path is None and owner is None and node_type == 'Node3D') if is_root
              else parent_path is not None and parent_path in paths, 'root/parent scope')
        if is_root:
            path, parent_id, sibling_index = '.', '', 0
            ancestors = ['.']
        else:
            _need(parent_path in ancestors, 'depth-first node order')
            ancestors = ancestors[:ancestors.index(parent_path) + 1]
            path = name if parent_path == '.' else parent_path + '/' + name
            _need(len(ancestors) < MAX_DEPTH, 'node depth')
            ancestors.append(path)
            parent_id = paths[parent_path].stable_id
            sibling_names = siblings.setdefault(parent_path, [])
            _need(name.lower() not in sibling_names, 'sibling name collision')
            sibling_index = len(sibling_names)
            sibling_names.append(name.lower())
        _need(path not in paths, 'node path collision')
        if unique_id is not None:
            unique_id = int(unique_id)
            _need(1 <= unique_id <= 2147483647 and unique_id not in unique_ids, 'node unique_id')
            unique_ids.add(unique_id)
        fields = _properties(block[1:])
        allowed = {'transform', 'metadata/hh_studio_id'}
        if is_root:
            allowed |= {'script'} | set(script_declarations)
        if node_type == 'MeshInstance3D':
            allowed.add('mesh')
        _need(set(fields) <= allowed and 'metadata/hh_studio_id' in fields, 'node fields')
        stable = _STABLE.fullmatch(fields['metadata/hh_studio_id'])
        _need(stable is not None, 'stable ID spelling')
        stable_id = stable.group(1)
        _need((stable_id == 'root') == is_root and stable_id not in identifiers, 'stable ID scope or collision')
        identifiers.add(stable_id)
        if is_root:
            _need(fields.get('script') == f'ExtResource("{external_id}")', 'root script attachment')
            # No exporter can be assigned before the script attachment.
            ordered = list(fields)
            _need(all(ordered.index('script') < ordered.index(key) for key in script_declarations if key in fields),
                  'script attachment before exports')
        transform, scale = _transform(fields['transform']) if 'transform' in fields else (_IDENTITY, (1.0, 1.0, 1.0))
        mesh_id, box_size = None, None
        if node_type == 'MeshInstance3D':
            mesh = re.fullmatch(rf'SubResource\("({_RESOURCE_ID})"\)', fields.get('mesh', ''))
            _need(mesh is not None, 'BoxMesh attachment required')
            mesh_id = mesh.group(1)
            _need(mesh_id in resources and mesh_id not in used_meshes, 'missing or shared BoxMesh')
            used_meshes.add(mesh_id)
            box_size = resources[mesh_id].size
        exports = []
        if is_root:
            for declaration in declared_script.declarations:
                value = _export_value(declaration.name, fields[declaration.name]) if declaration.name in fields else declaration.value
                exports.append(SceneProperty(declaration.name, declaration.gd_type, value))
        effective_exports = {item.name: item for item in exports}
        properties = []
        for key in fields:
            if key == 'transform':
                properties.append(SceneProperty(key, 'Transform3D', transform))
            elif key == 'script':
                properties.append(SceneProperty(key, 'ExtResource', external_id))
            elif key == 'mesh':
                properties.append(SceneProperty(key, 'SubResource', mesh_id))
            elif key == 'metadata/hh_studio_id':
                properties.append(SceneProperty(key, 'String', stable_id))
            else:
                effective = effective_exports[key]
                if effective.kind == 'float' and '.' not in fields[key] and 'e' not in fields[key]:
                    properties.append(SceneProperty(key, 'int', int(fields[key])))
                else:
                    properties.append(effective)
        node = SceneNode(name, node_type, path, parent_path, stable_id, parent_id, '' if is_root else 'root',
                         sibling_index, unique_id, transform, scale, mesh_id, box_size, tuple(exports), tuple(properties))
        nodes.append(node)
        paths[path] = node
    _need(bool(nodes) and used_meshes == set(resources), 'missing root or unused resource')
    _need(load_steps is None or int(load_steps) == len(resources) + 2, 'load_steps mismatch')
    return scene_uid, external_id, external_uid is not None, tuple(nodes), tuple(resources.values())


def _property_snapshot(properties: tuple[SceneProperty, ...]) -> dict:
    return {item.name: {'kind': item.kind, 'value': list(item.value) if type(item.value) is tuple else item.value}
            for item in properties}


@dataclass(frozen=True, slots=True)
class ValidatedSceneProfile:
    source_bytes: bytes
    script_uid_bytes: bytes
    script_source: bytes
    sha256: str = field(init=False)
    script_sha256: str = field(init=False)
    script_uid_sha256: str = field(init=False)
    script_uid: str = field(init=False)
    scene_uid: str | None = field(init=False)
    external_script_id: str = field(init=False)
    script_uid_declared: bool = field(init=False)
    nodes: tuple[SceneNode, ...] = field(init=False)
    resources: tuple[BoxResource, ...] = field(init=False)
    profile: str = field(default=PROFILE, init=False)

    def __post_init__(self) -> None:
        declared_script = script_profile.validate_script(self.script_source)
        uid_source = _decode(self.script_uid_bytes, 128, 'BAD_SCRIPT_UID_BYTES')
        _need(uid_source.endswith('\n') and uid_source.count('\n') == 1, 'UID sidecar LF')
        script_uid = _uid(uid_source[:-1])
        scene_uid, external_id, uid_declared, nodes, resources = _parse(self.source_bytes, script_uid, declared_script)
        values = {'sha256': hashlib.sha256(self.source_bytes).hexdigest(), 'script_sha256': declared_script.sha256,
                  'script_uid_sha256': hashlib.sha256(self.script_uid_bytes).hexdigest(), 'script_uid': script_uid,
                  'scene_uid': scene_uid, 'external_script_id': external_id, 'script_uid_declared': uid_declared,
                  'nodes': nodes, 'resources': resources}
        for name, value in values.items():
            object.__setattr__(self, name, value)

    def snapshot(self) -> dict:
        """Detached comparison data; declared properties remain separate."""
        return {'profile': self.profile, 'sha256': self.sha256, 'scene_uid': self.scene_uid,
                'script': {'path': SCRIPT_PATH, 'sha256': self.script_sha256, 'uid': self.script_uid,
                           'uid_sha256': self.script_uid_sha256, 'external_id': self.external_script_id,
                           'uid_declared': self.script_uid_declared},
                'nodes': [{'name': node.name, 'node_type': node.node_type, 'path': node.path, 'parent_path': node.parent_path,
                           'stable_id': node.stable_id, 'parent_id': node.parent_id, 'owner_id': node.owner_id,
                           'sibling_index': node.sibling_index, 'unique_id': node.unique_id,
                           'transform_rows_origin': list(node.transform_rows_origin), 'scale': list(node.scale),
                           'mesh_id': node.mesh_id, 'box_size': list(node.box_size) if node.box_size is not None else None,
                           'exports': _property_snapshot(node.export_values),
                           'declared_properties': _property_snapshot(node.declared_properties)} for node in self.nodes],
                'resources': [{'resource_id': resource.resource_id, 'resource_type': resource.resource_type,
                               'size': list(resource.size), 'declared_properties': _property_snapshot(resource.declared_properties)}
                              for resource in self.resources]}


def validate_scene(raw: bytes, *, script_uid: bytes, script_source: bytes) -> ValidatedSceneProfile:
    return ValidatedSceneProfile(raw, script_uid, script_source)

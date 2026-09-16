"""Compare fixed native observations to eligible bytes; not transport trust.

The caller must separately prove which pinned process/helper produced a report,
its containment, actual clean exit and unchanged inputs. This pure comparator
cannot authenticate a caller-supplied dictionary or issue publication receipts.
"""
from __future__ import annotations

import hashlib
import importlib.util
import math
from pathlib import Path
import re
import sys

_path = Path(__file__).with_name('fixture_profile.py').resolve()
_raw = _path.read_bytes()
_key = '_hh_readback_factory_' + hashlib.sha256(str(_path).encode() + b'\0' + _raw).hexdigest()
if _key not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_key, _path)
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_key] = _module
    try:
        exec(compile(_raw, str(_path), 'exec'), _module.__dict__)
    except BaseException:
        del sys.modules[_key]
        raise
factory = sys.modules[_key]
SEMANTIC_SCHEMA = 'hh-godot-semantic-snapshot-1'
REPORT_SCHEMA = 'hh-godot-profile-readback-2'
MAX_SEMANTIC_BYTES = 262144


class ReadbackError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _need(value, code='PROFILE_READBACK_MISMATCH'):
    if not value:
        raise ReadbackError(code)


def _shape(value, keys):
    _need(type(value) is dict and set(value) == set(keys), 'PROFILE_READBACK_SHAPE')


def _equal(actual, expected, *, epsilon=0.0):
    if type(expected) is float:
        _need(type(actual) in (int, float) and math.isfinite(actual)
              and (actual != 0 or expected == 0)
              and math.isclose(actual, expected, rel_tol=epsilon, abs_tol=epsilon))
    elif type(expected) is dict:
        _shape(actual, expected)
        for key in expected:
            # Vector/basis values are native binary32. Exported GDScript float
            # properties stay binary64 and must not inherit the vector epsilon.
            vector_value = (key == 'transform_rows_origin' or
                key == 'size' and expected.get('type') == 'BoxMesh' or
                key == 'value' and expected.get('type') in ('Vector3', 'Transform3D'))
            _equal(actual[key], expected[key], epsilon=2e-6 if vector_value else epsilon)
    elif type(expected) in (list, tuple):
        _need(type(actual) is list and len(actual) == len(expected))
        for received, wanted in zip(actual, expected):
            _equal(received, wanted, epsilon=epsilon)
    else:
        _need(type(actual) is type(expected) and actual == expected)


def _exports(properties):
    return {row.name: {'type': row.kind, 'value': row.value} for row in properties}


def _property(prop, eligible, node):
    if prop.kind == 'ExtResource':
        return {'type': 'GDScript', 'path': 'res://scripts/fixture_actor.gd',
                'source_sha256': eligible.script.sha256}
    if prop.kind == 'SubResource':
        return {'type': 'BoxMesh', 'id': node.mesh_id, 'size': list(node.box_size)}
    return {'type': 'string' if prop.kind == 'String' else prop.kind, 'value': prop.value}


def semantic_state_bytes(semantic: dict) -> bytes:
    """Exact shared JCS value bytes, never proof of process/editor attribution."""
    _shape(semantic, {'schema', 'context_kind', 'serializer_sha256', 'jcs_sha256', 'state', 'revision'})
    _need(semantic['schema'] == SEMANTIC_SCHEMA
          and semantic['context_kind'] == 'isolated_candidate', 'PROFILE_SEMANTIC_CONTEXT')
    for key in ('serializer_sha256', 'jcs_sha256'):
        _need(type(semantic[key]) is str and re.fullmatch('[0-9a-f]{64}', semantic[key]),
              'PROFILE_SEMANTIC_PIN')
    _shape(semantic['state'], {'nodes'})
    _need(type(semantic['state']['nodes']) is list and 1 <= len(semantic['state']['nodes']) <= 64,
          'PROFILE_SEMANTIC_LIMIT')
    try:
        raw = factory.bundle_codec.canonical_bytes(semantic['state'])
    except (ValueError, TypeError, OverflowError, RecursionError) as error:
        raise ReadbackError('PROFILE_SEMANTIC_CANONICAL') from error
    _need(len(raw) <= MAX_SEMANTIC_BYTES, 'PROFILE_SEMANTIC_LIMIT')
    _need(semantic['revision'] == 'sha256:' + hashlib.sha256(raw).hexdigest(),
          'PROFILE_SEMANTIC_REVISION')
    return raw


def _semantic(bundle, eligible, semantic):
    raw = semantic_state_bytes(semantic)
    for key, path in (('serializer_sha256', 'addons/hh_studio/scene_commands.gd'),
                      ('jcs_sha256', 'addons/hh_studio/jcs_godot.gd')):
        _need(semantic[key] == hashlib.sha256(bundle.files[path]).hexdigest(), 'PROFILE_SEMANTIC_PIN')
    rows = semantic['state']['nodes']
    _need(len(rows) == len(eligible.scene.nodes), 'PROFILE_SEMANTIC_NODES')
    identities = {node.path: node.stable_id for node in eligible.scene.nodes}
    siblings = {}
    for index, (row, node) in enumerate(zip(rows, eligible.scene.nodes)):
        keys = {'node_type', 'name', 'position', 'rotation_degrees', 'scale',
                'stable_id', 'parent_id', 'sibling_index', 'owner_id', 'stored', 'groups'}
        if node.mesh_id is not None:
            keys.add('box_size')
        _shape(row, keys)
        sibling_index = siblings.get(node.parent_path, 0)
        siblings[node.parent_path] = sibling_index + 1
        _equal({key: row[key] for key in ('node_type', 'name', 'stable_id', 'parent_id',
                                        'sibling_index', 'owner_id', 'groups')},
               {'node_type': node.node_type, 'name': node.name, 'stable_id': node.stable_id,
                'parent_id': '' if index == 0 else identities[node.parent_path],
                'sibling_index': 0 if index == 0 else sibling_index,
                'owner_id': '' if index == 0 else 'root', 'groups': []})
        for key in ('position', 'rotation_degrees', 'scale'):
            _need(type(row[key]) is list and len(row[key]) == 3
                  and all(type(v) in (int, float) and math.isfinite(v) for v in row[key]),
                  'PROFILE_SEMANTIC_VECTOR')
        # Position and mesh size are direct stored binary32 values. This uses
        # exact JCS bytes; no vector epsilon is carried into semantic binding.
        _need(factory.bundle_codec.canonical_bytes(row['position']) ==
              factory.bundle_codec.canonical_bytes(list(node.transform_rows_origin[9:])),
              'PROFILE_SEMANTIC_POSITION')
        stored = row['stored']
        _need(type(stored) is dict and 1 <= len(stored) <= 192, 'PROFILE_SEMANTIC_STORED')
        _equal(stored.get('metadata/hh_studio_id'), node.stable_id)
        _equal(stored.get('script'), None if index else {'type': 'GDScript',
            'path': 'res://scripts/fixture_actor.gd', 'source_sha256': eligible.script.sha256})
        for prop in node.export_values:
            _need(prop.name in stored, 'PROFILE_SEMANTIC_STORED')
            _equal(stored[prop.name], prop.value)
        if node.mesh_id is not None:
            _need(factory.bundle_codec.canonical_bytes(row['box_size']) ==
                  factory.bundle_codec.canonical_bytes(list(node.box_size)), 'PROFILE_SEMANTIC_MESH')
            mesh = stored.get('mesh')
            _shape(mesh, {'type', 'stored'})
            _need(mesh['type'] == 'BoxMesh' and type(mesh['stored']) is dict
                  and 1 <= len(mesh['stored']) <= 192, 'PROFILE_SEMANTIC_MESH')
    return {'semantic_observed': True, 'semantic_revision': semantic['revision'],
            'semantic_state_sha256': hashlib.sha256(raw).hexdigest()}


def compare_observation(bundle, report: dict) -> dict:
    """Reject any changed/missing fact; return internal comparison metadata only."""
    eligible = factory.qualify(bundle)
    semantic_report = type(report) is dict and report.get('schema') == REPORT_SCHEMA
    keys = {'schema', 'engine_version', 'pid', 'public_ack', 'ok', 'script',
            'fresh_script', 'scene', 'instance_nodes'}
    _shape(report, keys | ({'semantic'} if semantic_report else set()))
    _need(report['schema'] in ('hh-godot-profile-readback-1', REPORT_SCHEMA) and report['public_ack'] is False
          and report['ok'] is True and report['engine_version'] == '4.7.2-stable (official)'
          and type(report['pid']) is int and 0 < report['pid'] <= 2147483647)
    defaults = {row.name: {'type': row.gd_type, 'value': row.value}
                for row in eligible.script.declarations}
    expected_script = {'source_sha256': eligible.script.sha256, 'disk_sha256': eligible.script.sha256,
        'uid_source': eligible.scene.script_uid_bytes.decode('ascii'), 'resource_uid': eligible.scene.script_uid,
        'reload_code': 0, 'can_instantiate': True, 'base_type': 'Node3D', 'is_tool': False,
        'has_base_script': False, 'global_name': '', 'methods': [], 'signals': [], 'constants': [],
        'defaults': defaults}
    _equal(report['script'], expected_script)
    _equal(report['fresh_script'], {'type': 'Node3D', 'source_sha256': eligible.script.sha256,
                                   'exports': defaults})
    expected_state = []
    expected_instances = []
    for index, node in enumerate(eligible.scene.nodes):
        # SceneState retains a './' prefix on non-root relative paths. The
        # instantiated Node.get_path_to representation omits that prefix.
        expected_state.append({'index': index, 'path': '.' if index == 0 else './' + node.path, 'name': node.name,
            'type': node.node_type, 'parent': ('' if node.parent_path is None else
                '.' if node.parent_path == '.' else './' + node.parent_path),
            'owner': '' if index == 0 else '.', 'instanced': False, 'placeholder': '', 'groups': [],
            'properties': [{'name': prop.name, 'value': _property(prop, eligible, node)}
                           for prop in node.declared_properties]})
        expected_instances.append({'path': node.path, 'name': node.name, 'type': node.node_type,
            'owner': '' if index == 0 else '.', 'stable_id': node.stable_id,
            'transform_rows_origin': node.transform_rows_origin,
            'mesh': None if node.mesh_id is None else
                    {'type': 'BoxMesh', 'id': node.mesh_id, 'size': list(node.box_size)},
            'script_sha256': eligible.script.sha256 if index == 0 else None,
            'exports': _exports(node.export_values), 'groups': []})
    _equal(report['scene'], {'node_count': len(expected_state), 'connections': 0, 'inherited': False,
        'source_sha256': eligible.scene.sha256, 'nodes': expected_state})
    _equal(report['instance_nodes'], expected_instances)
    semantic = (_semantic(bundle, eligible, report['semantic']) if semantic_report else
                {'semantic_observed': False, 'semantic_revision': None, 'semantic_state_sha256': None})
    return {'status': 'PROFILE_OBSERVATIONS_MATCH', 'public_ack': False,
        'process_attribution_proven': False, 'sandbox_acceptance': False,
        'project_revision': bundle.project_revision, 'script_sha256': eligible.script.sha256,
        'scene_sha256': eligible.scene.sha256, 'uid_sha256': eligible.scene.script_uid_sha256,
        'nodes': len(eligible.scene.nodes), 'resources': len(eligible.scene.resources), **semantic}

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


def compare_observation(bundle, report: dict) -> dict:
    """Reject any changed/missing fact; return internal comparison metadata only."""
    eligible = factory.qualify(bundle)
    _shape(report, {'schema', 'engine_version', 'pid', 'public_ack', 'ok', 'script',
                    'fresh_script', 'scene', 'instance_nodes'})
    _need(report['schema'] == 'hh-godot-profile-readback-1' and report['public_ack'] is False
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
        expected_state.append({'index': index, 'path': node.path, 'name': node.name,
            'type': node.node_type, 'parent': '' if node.parent_path is None else node.parent_path,
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
    return {'status': 'PROFILE_OBSERVATIONS_MATCH', 'public_ack': False,
        'process_attribution_proven': False, 'sandbox_acceptance': False,
        'project_revision': bundle.project_revision, 'script_sha256': eligible.script.sha256,
        'scene_sha256': eligible.scene.sha256, 'uid_sha256': eligible.scene.script_uid_sha256,
        'nodes': len(eligible.scene.nodes), 'resources': len(eligible.scene.resources)}

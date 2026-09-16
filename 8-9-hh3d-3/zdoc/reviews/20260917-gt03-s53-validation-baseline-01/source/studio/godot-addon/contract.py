"""Pure GT-03 catalog validation and projection, not runtime authorization.

Only operations.json is read by this module. Caller-supplied snapshots and
lease observations must come from a trusted host; validation neither opens
project paths nor calls Godot, parses scripts, changes files or commits work.
"""
from __future__ import annotations

from dataclasses import dataclass
import difflib
import hashlib
import math
from pathlib import Path
import re
from typing import Any, Mapping

from studio.protocol.core import (Capability, Discovery, PROTOCOL_VERSION,
    Request, SCHEMA_VERSION, SAFE_INTEGER, ValidationError, canonical_bytes, parse_json)

_CATALOG = parse_json(Path(__file__).with_name('operations.json').read_bytes())
SCENE_PATH = _CATALOG['scene_path']
SCRIPT_PATH = _CATALOG['script_path']
ROOT_ID = _CATALOG['root_stable_id']
SCOPE = _CATALOG['scope']
CATALOG_DIGEST = 'sha256:' + hashlib.sha256(canonical_bytes(_CATALOG)).hexdigest()
_OPS = _CATALOG['operations']
_LIMITS = _CATALOG['limits']
_ID = re.compile(r'[a-z][a-z0-9._-]{0,63}\Z')
_NAME = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,47}\Z')
_HASH = re.compile(r'[0-9a-f]{64}\Z')
_REV = re.compile(r'sha256:[0-9a-f]{64}\Z')


class ContractError(ValidationError):
    def __init__(self, code: str):
        super().__init__(code, 'Godot catalog validation')


def _need(condition: object, code: str) -> None:
    if not condition:
        raise ContractError(code)


def _shape(value: object, required: set[str], optional: set[str] = frozenset()) -> None:
    _need(type(value) is dict and required <= set(value) <= required | optional, 'GODOT_INVALID_SHAPE')


def _integer(value: object, lower: int = 0, upper: int = SAFE_INTEGER) -> None:
    _need(type(value) is int and lower <= value <= upper, 'GODOT_INVALID_INTEGER')


def _stable_id(value: object) -> None:
    _need(type(value) is str and _ID.fullmatch(value), 'GODOT_INVALID_STABLE_ID')


def _hash(value: object) -> None:
    _need(type(value) is str and _HASH.fullmatch(value), 'GODOT_INVALID_FILE_HASH')


def _property(name: str, value: object) -> None:
    _need(name in _CATALOG['properties'], 'GODOT_UNSUPPORTED_PROPERTY')
    if name == 'name':
        _need(type(value) is str and _NAME.fullmatch(value), 'GODOT_INVALID_NAME')
        return
    rule = _CATALOG['properties'][name]
    _need(type(value) in (tuple, list) and len(value) == rule['length'], 'GODOT_INVALID_VECTOR')
    for component in value:
        _need(type(component) in (int, float) and math.isfinite(component)
              and rule['minimum'] <= component <= rule['maximum'], 'GODOT_INVALID_COMPONENT')


def _plain(value: Any) -> Any:
    return parse_json(canonical_bytes(value))


@dataclass(frozen=True)
class NodeState:
    stable_id: str
    parent_id: str | None
    node_type: str
    name: str
    position: tuple[float, float, float] = (0, 0, 0)
    rotation_degrees: tuple[float, float, float] = (0, 0, 0)
    scale: tuple[float, float, float] = (1, 1, 1)
    box_size: tuple[float, float, float] | None = None

    def as_dict(self) -> dict[str, Any]:
        value = {'stable_id': self.stable_id, 'parent_id': self.parent_id,
            'node_type': self.node_type, 'name': self.name, 'position': self.position,
            'rotation_degrees': self.rotation_degrees, 'scale': self.scale}
        if self.box_size is not None:
            value['box_size'] = self.box_size
        return _plain(value)


@dataclass(frozen=True)
class ValidationContext:
    """Trusted observations, never fields extracted from the remote request.

    A lease ID in this record is only an observation. A real dispatcher must
    authenticate, own/checkpoint/journal and recheck authority at effect time.
    """
    project_id: str
    revision: str
    project_revision: str
    generation: int
    lease_id: str
    fencing_epoch: int
    lease_expires_ms: int
    now_ms: int
    nodes: tuple[NodeState, ...]
    file_hashes: tuple[tuple[str, str], ...]
    can_undo: bool = False
    can_redo: bool = False
    stopped: bool = False


@dataclass(frozen=True)
class ValidatedCommand:
    """Immutable copied JSON. Accessors return fresh data, not retained inputs."""
    request_digest: str
    requested_operation: str
    _projection: bytes
    _preview: bytes

    @property
    def projection(self) -> dict[str, Any]:
        return parse_json(self._projection)

    @property
    def preview(self) -> dict[str, Any]:
        return parse_json(self._preview)


def catalog() -> dict[str, Any]:
    """Declaration only: static implemented/runtime_enabled flags stay false."""
    return _plain(_CATALOG)


def discovery(project_id: str, *, implemented: frozenset[str] = frozenset(),
              runtime_enabled: frozenset[str] = frozenset()) -> Discovery:
    """A trusted backend explicitly supplies both sets; defaults advertise none."""
    _need(type(implemented) is frozenset and type(runtime_enabled) is frozenset
          and runtime_enabled <= implemented <= set(_OPS), 'GODOT_INVALID_RUNTIME_CATALOG')
    caps = tuple(Capability(name, (SCOPE,), () if _OPS[name]['kind'] in ('inspect', 'preview') else (SCOPE,),
                           {'max_payload_bytes': _LIMITS['max_payload_bytes']})
                 for name in sorted(runtime_enabled))
    return Discovery(PROTOCOL_VERSION, SCHEMA_VERSION, CATALOG_DIGEST,
                     'gt03-godot-catalog', '2.0', project_id, caps, dict(_LIMITS))


def _context(context: ValidationContext) -> tuple[dict[str, dict], dict[str, str]]:
    _need(type(context) is ValidationContext, 'GODOT_TRUSTED_CONTEXT_REQUIRED')
    _need(type(context.revision) is str and _REV.fullmatch(context.revision), 'GODOT_INVALID_REVISION')
    _need(type(context.project_revision) is str and _REV.fullmatch(context.project_revision),
          'GODOT_INVALID_PROJECT_REVISION')
    _integer(context.generation, 1, 2147483647)
    for value in (context.now_ms, context.lease_expires_ms, context.fencing_epoch):
        _integer(value)
    for value in (context.can_undo, context.can_redo, context.stopped):
        _need(type(value) is bool, 'GODOT_INVALID_CONTEXT')
    _need(type(context.nodes) is tuple and 1 <= len(context.nodes) <= _LIMITS['max_nodes'], 'GODOT_NODE_LIMIT')
    nodes: dict[str, dict] = {}
    for node in context.nodes:
        _need(type(node) is NodeState, 'GODOT_INVALID_NODE_STATE')
        _stable_id(node.stable_id)
        _need(node.stable_id not in nodes, 'GODOT_DUPLICATE_STABLE_ID')
        _need(node.node_type in _CATALOG['node_types'], 'GODOT_UNSUPPORTED_NODE_TYPE')
        for name in ('name', 'position', 'rotation_degrees', 'scale'):
            _property(name, getattr(node, name))
        if node.node_type == 'MeshInstance3D':
            _property('box_size', node.box_size)
        else:
            _need(node.box_size is None, 'GODOT_RESOURCE_SCOPE')
        if node.stable_id == ROOT_ID:
            _need(node.parent_id is None and node.node_type == 'Node3D', 'GODOT_INVALID_ROOT')
        else:
            _stable_id(node.parent_id)
        nodes[node.stable_id] = node.as_dict()
    _need(ROOT_ID in nodes, 'GODOT_INVALID_ROOT')
    for node in nodes.values():
        seen, current = set(), node['stable_id']
        while current is not None:
            _need(current in nodes and current not in seen, 'GODOT_INVALID_HIERARCHY')
            seen.add(current)
            _need(len(seen) <= _LIMITS['max_depth'], 'GODOT_DEPTH_LIMIT')
            current = nodes[current]['parent_id']
        siblings = [x['name'].lower() for x in nodes.values() if x['parent_id'] == node['parent_id']]
        _need(len(siblings) == len(set(siblings)), 'GODOT_DUPLICATE_SIBLING_NAME')
    _need(type(context.file_hashes) is tuple and len(context.file_hashes) == 2, 'GODOT_INVALID_FILE_STATE')
    files = {}
    for item in context.file_hashes:
        _need(type(item) is tuple and len(item) == 2, 'GODOT_INVALID_FILE_STATE')
        path, digest = item
        _need(type(path) is str and path in (SCENE_PATH, SCRIPT_PATH) and path not in files, 'GODOT_PATH_NOT_ALLOWED')
        _hash(digest)
        files[path] = digest
    return nodes, files


def _semantic(operation: str, target: dict, payload: dict, context: ValidationContext,
              nodes: dict[str, dict], files: dict[str, str]) -> tuple[dict, dict]:
    _need(type(operation) is str and operation in _OPS, 'GODOT_UNSUPPORTED_OPERATION')
    descriptor = _OPS[operation]
    _shape(payload, set(descriptor['required']), set(descriptor['optional']))
    _integer(payload['expected_generation'], 1, 2147483647)
    _need(payload['expected_generation'] == context.generation, 'GODOT_STALE_GENERATION')
    if descriptor['kind'] != 'inspect':
        project_revision = payload['expected_project_revision']
        _need(type(project_revision) is str and _REV.fullmatch(project_revision),
              'GODOT_INVALID_PROJECT_REVISION')
        _need(project_revision == context.project_revision, 'GODOT_STALE_PROJECT_REVISION')
    if descriptor['target'] == 'script':
        # Exact spelling rejects aliases before any script parser/file opening.
        _need(type(target) is dict and target == {'path': SCRIPT_PATH}, 'GODOT_PATH_NOT_ALLOWED')
        target_id = None
    else:
        _shape(target, {'stable_id'})
        _stable_id(target['stable_id'])
        target_id = target['stable_id']
        _need(target_id in nodes, 'GODOT_STALE_STABLE_ID')
        if descriptor['target'] == 'root':
            _need(target_id == ROOT_ID, 'GODOT_ROOT_TARGET_REQUIRED')
    # The project CAS belongs to the trusted host, not the narrow scene API.
    engine_payload = {key: value for key, value in payload.items() if key != 'expected_project_revision'}
    projection = {'operation': operation, 'expected_generation': context.generation,
                  'target_stable_id': target_id, 'payload': engine_payload}
    if target_id is None:
        projection['target_path'] = SCRIPT_PATH
    preview = {'operation': operation, 'affected_files': [], 'diff': [],
        'checkpoint_required': False, 'recovery': descriptor['recovery'],
        'requires_runtime_validation': descriptor['kind'] not in ('inspect', 'preview'),
        'changes_applied': False, 'runtime_authorized': False}
    if operation == 'scene.inspect':
        _integer(payload['offset'], 0, _LIMITS['max_nodes'])
        _integer(payload['limit'], 1, _LIMITS['max_inspect_nodes'])
    elif operation == 'scene.node.create':
        _need(len(nodes) < _LIMITS['max_nodes'], 'GODOT_NODE_LIMIT')
        _stable_id(payload['stable_id'])
        _need(payload['stable_id'] not in nodes, 'GODOT_DUPLICATE_STABLE_ID')
        _need(payload['node_type'] in _CATALOG['node_types'], 'GODOT_UNSUPPORTED_NODE_TYPE')
        for name in ('name', 'position', 'rotation_degrees', 'scale'):
            _property(name, payload[name])
        _need(('box_size' in payload) == (payload['node_type'] == 'MeshInstance3D'), 'GODOT_RESOURCE_SCOPE')
        if 'box_size' in payload:
            _property('box_size', payload['box_size'])
        _need(not any(n['parent_id'] == target_id and n['name'].lower() == payload['name'].lower() for n in nodes.values()),
              'GODOT_DUPLICATE_SIBLING_NAME')
        depth, current = 1, target_id
        while current is not None:
            depth += 1
            current = nodes[current]['parent_id']
        _need(depth <= _LIMITS['max_depth'], 'GODOT_DEPTH_LIMIT')
        new = {key: value for key, value in engine_payload.items() if key != 'expected_generation'}
        new['parent_id'] = target_id
        preview['diff'] = [{'kind': 'node.create', 'before': None, 'after': new}]
    elif operation == 'scene.node.update':
        changes = payload['changes']
        _need(type(changes) is dict and 1 <= len(changes) <= 5, 'GODOT_INVALID_CHANGES')
        for name, value in changes.items():
            _property(name, value)
        _need('box_size' not in changes or nodes[target_id]['node_type'] == 'MeshInstance3D', 'GODOT_RESOURCE_SCOPE')
        if 'name' in changes:
            _need(not any(n['stable_id'] != target_id and n['parent_id'] == nodes[target_id]['parent_id']
                          and n['name'].lower() == changes['name'].lower() for n in nodes.values()), 'GODOT_DUPLICATE_SIBLING_NAME')
        preview['diff'] = [{'kind': 'node.update', 'stable_id': target_id,
            'before': {key: nodes[target_id][key] for key in changes}, 'after': changes}]
    elif operation == 'scene.node.remove':
        _need(target_id != ROOT_ID, 'GODOT_ROOT_REMOVE_FORBIDDEN')
        _need(not any(n['parent_id'] == target_id for n in nodes.values()), 'GODOT_NONLEAF_REMOVE_FORBIDDEN')
        preview['checkpoint_required'] = True
        preview['diff'] = [{'kind': 'node.remove', 'before': nodes[target_id], 'after': None}]
    elif operation == 'script_text.replace':
        _hash(payload['expected_sha256'])
        _need(payload['expected_sha256'] == files[SCRIPT_PATH], 'GODOT_STALE_SCRIPT')
        text = payload['text']
        _need(type(text) is str and '\x00' not in text and '\r' not in text, 'GODOT_INVALID_SCRIPT_TEXT')
        raw = text.encode('utf-8', 'strict')
        _need(len(raw) <= _LIMITS['max_script_utf8_bytes'], 'GODOT_SCRIPT_LIMIT')
        preview['checkpoint_required'] = True
        preview['affected_files'] = [SCRIPT_PATH]
        preview['diff'] = [{'kind': 'script.replace', 'path': SCRIPT_PATH,
            'before_sha256': files[SCRIPT_PATH], 'after_sha256': hashlib.sha256(raw).hexdigest(),
            'after_utf8_bytes': len(raw), 'after_lines': len(text.splitlines())}]
        preview['script_parse_status'] = 'NOT_RUN'
    elif operation in ('scene.undo', 'scene.redo'):
        _integer(payload['steps'], 1, 1)
        _need(context.can_undo if operation == 'scene.undo' else context.can_redo, 'GODOT_HISTORY_UNAVAILABLE')
        preview['checkpoint_required'] = True
        preview['diff'] = [{'kind': operation, 'steps': 1, 'content': 'requires_revision_bound_runtime_history'}]
    elif operation == 'scene.preview':
        nested = payload['operation']
        _need(type(nested) is str and nested in _CATALOG['preview_operations'], 'GODOT_PREVIEW_OPERATION_FORBIDDEN')
        inner, preview = _semantic(nested, payload['target'], payload['payload'], context, nodes, files)
        engine_payload['payload'] = inner['payload']
        projection = {'operation': operation, 'expected_generation': context.generation,
                      'target_stable_id': ROOT_ID, 'payload': engine_payload, 'preview_command': inner}
        preview['preview_of'] = nested
    elif operation == 'scene.save':
        expected = payload['expected_files']
        _shape(expected, {SCENE_PATH, SCRIPT_PATH})
        for path, digest in expected.items():
            _hash(digest)
            _need(digest == files[path], 'GODOT_STALE_FILE')
        preview['checkpoint_required'] = True
        preview['affected_files'] = [SCENE_PATH]
        preview['save_policy'] = _plain(_CATALOG['managed_save_policy'])
        preview['diff'] = [{'kind': 'scene.save', 'before_files': expected,
                           'after_files': 'requires_godot_staged_save_readback'}]
    if operation.startswith('scene.node.') or operation in ('scene.undo', 'scene.redo'):
        preview['affected_files'] = [SCENE_PATH]
    return projection, preview


def validate_request(request: Request | Mapping[str, Any], context: ValidationContext) -> ValidatedCommand:
    """Validate/copy once and return a proposed effect; never authorize/apply it."""
    nodes, files = _context(context)
    original = request.as_dict() if type(request) is Request else request
    checked = Request.from_dict(_plain(original))
    _need(type(checked.command_id) is str and _ID.fullmatch(checked.command_id), 'GODOT_INVALID_COMMAND_ID')
    _need(checked.project_id == context.project_id, 'GODOT_PROJECT_MISMATCH')
    _need(checked.expected_revision == context.revision, 'GODOT_STALE_REVISION')
    _need(checked.lease_id == context.lease_id and checked.fencing_epoch == context.fencing_epoch, 'GODOT_STALE_LEASE')
    horizon = _LIMITS['max_save_deadline_ms'] if checked.operation in ('scene.save','script_text.replace') else _LIMITS['max_deadline_ms']
    _need(context.now_ms < checked.deadline_ms <= min(context.lease_expires_ms,
          context.now_ms + horizon), 'GODOT_DEADLINE_EXPIRED')
    _need(not context.stopped or checked.operation in ('scene.inspect','scene.preview'), 'GODOT_STOPPED')
    _need(len(canonical_bytes(checked.payload)) <= _LIMITS['max_payload_bytes'], 'GODOT_PAYLOAD_LIMIT')
    projection, preview = _semantic(checked.operation, dict(checked.target), dict(checked.payload), context, nodes, files)
    projection.update(command_id=checked.command_id, expected_revision=checked.expected_revision)
    if checked.operation == 'scene.preview':
        projection['preview_command'].update(command_id=checked.command_id,
                                             expected_revision=checked.expected_revision)
    preview.update(command_id=checked.command_id, expected_revision=context.revision,
                   scene_revision=context.revision, project_revision=context.project_revision,
                   expected_generation=context.generation, request_digest=checked.digest)
    encoded, plan = canonical_bytes(projection), canonical_bytes(preview)
    _need(max(len(encoded), len(plan)) <= _LIMITS['max_projection_bytes'], 'GODOT_PROJECTION_LIMIT')
    return ValidatedCommand(checked.digest, checked.operation, encoded, plan)


def script_preview(before: bytes, command: ValidatedCommand) -> dict[str, Any]:
    """Bounded actual text diff from trusted current bytes; no parsing/effects.

    Hashes always cover the complete input, including when display truncates.
    The publication owner separately qualifies the closed script profile.
    """
    _need(type(before) is bytes and len(before) <= _LIMITS['max_script_utf8_bytes'], 'GODOT_SCRIPT_LIMIT')
    _need(type(command) is ValidatedCommand, 'GODOT_INVALID_PREVIEW')
    projection = command.projection
    if command.requested_operation == 'scene.preview':
        projection = projection['preview_command']
    _need(projection['operation'] == 'script_text.replace', 'GODOT_INVALID_PREVIEW')
    payload = projection['payload']
    _need(hashlib.sha256(before).hexdigest() == payload['expected_sha256'], 'GODOT_STALE_SCRIPT')
    try:
        old_text = before.decode('utf-8',errors='strict')
    except UnicodeDecodeError:
        raise ContractError('GODOT_INVALID_SCRIPT_TEXT') from None
    # Input line caps bound difflib work independently of output byte caps.
    old_lines, new_lines = old_text.splitlines(keepends=True), payload['text'].splitlines(keepends=True)
    _need(max(len(old_lines),len(new_lines)) <= 512, 'GODOT_PREVIEW_LINE_LIMIT')
    lines = list(difflib.unified_diff(old_lines,new_lines,fromfile=SCRIPT_PATH,tofile=SCRIPT_PATH,n=3))
    kept, used = [], 0
    for line in lines:
        size = len(line.encode('utf-8'))
        if len(kept) == 256 or used + size > 32768:
            break
        kept.append(line); used += size
    preview = command.preview
    preview['diff'][0].update(unified_diff=kept,diff_truncated=len(kept)!=len(lines),
                             full_diff_lines=len(lines),display_utf8_bytes=used)
    _need(len(canonical_bytes(preview)) <= _LIMITS['max_projection_bytes'], 'GODOT_PROJECTION_LIMIT')
    return preview

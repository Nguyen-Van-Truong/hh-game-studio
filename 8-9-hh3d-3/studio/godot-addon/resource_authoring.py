"""Pure O2 candidate contract for a small set of Godot shape resources.

This module validates proposals only.  It does not load a Resource, inspect
ClassDB, edit a scene, use UndoRedo, or issue an ACK.  ``NodeState`` and
``ResourceState`` are trusted host observations supplied by a future owner;
request fields can never create those observations.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from types import MappingProxyType
from typing import Any, Mapping

from studio.protocol.core import Request, SAFE_INTEGER, ValidationError, canonical_bytes, parse_json

PROFILE = 'hh-godot-shape-resource-1'
OPERATIONS = ('scene.resource.create', 'scene.resource.update')
AUTHORITY = 0
_ID = re.compile(r'[a-z][a-z0-9._-]{0,63}\Z')
_CLASS = re.compile(r'[A-Z][A-Za-z0-9_]*\Z')
_REV = re.compile(r'sha256:[0-9a-f]{64}\Z')
_SHAPE_TYPES = frozenset(('RectangleShape2D', 'CapsuleShape2D', 'BoxShape3D', 'CapsuleShape3D'))
_NODE_TYPES = frozenset(('CollisionShape2D', 'CollisionShape3D'))
_CONTEXT_NODE_TYPES = _NODE_TYPES | frozenset((
    'Node', 'Node2D', 'Node3D', 'CharacterBody2D', 'StaticBody2D', 'Area2D', 'Camera2D',
    'CharacterBody3D', 'StaticBody3D', 'Area3D', 'MeshInstance3D', 'Camera3D',
    'CanvasLayer', 'Label'))
_DIMENSION_LIMIT = 10000.0


class ContractError(ValidationError):
    def __init__(self, code: str):
        super().__init__(code, 'O2 resource candidate validation; no effect authorized')


def _need(condition: object, code: str) -> None:
    if not condition:
        raise ContractError(code)


def _shape(value: object, required: set[str], optional: set[str] = frozenset()) -> None:
    _need(type(value) is dict and required <= set(value) <= required | optional, 'AUTHORING_INVALID_SHAPE')


def _matches(value: object, pattern: re.Pattern[str]) -> bool:
    return type(value) is str and pattern.fullmatch(value) is not None


def _number(value: object) -> bool:
    return type(value) in (int, float) and abs(value) <= SAFE_INTEGER and math.isfinite(value)


def _integer(value: object, minimum: int = 0, maximum: int = SAFE_INTEGER) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _copy(value: Any) -> Any:
    return parse_json(canonical_bytes(value))


@dataclass(frozen=True, slots=True)
class NodeState:
    stable_id: str
    parent_id: str | None
    node_type: str
    name: str


@dataclass(frozen=True, slots=True, init=False)
class ResourceState:
    """Trusted resource identity, owner and class assertion.

    ``properties`` is optional because a host may only have identity metadata.
    A partial update then has to carry all shape dimensions.  ``base`` and
    ``owner_id`` are accepted aliases for callers using the node contract's
    vocabulary; the canonical fields remain ``resource_type`` and
    ``owner_stable_id``.
    """

    resource_id: str
    owner_stable_id: str
    resource_type: str
    shared: bool
    properties: Mapping[str, Any]

    def __init__(self, resource_id: str, owner_stable_id: str | None = None,
                 resource_type: str | None = None, shared: bool | Mapping[str, Any] = False,
                 properties: Mapping[str, Any] | None = None, *, owner_id: str | None = None,
                 base: str | None = None) -> None:
        if owner_stable_id is None:
            owner_stable_id = owner_id
        if resource_type is None:
            resource_type = base
        if isinstance(shared, Mapping):
            # Convenient positional form: ResourceState(id, owner, class,
            # {current properties}).  A boolean shared flag remains strict.
            properties, shared = shared, False
        if properties is None:
            properties = {}
        object.__setattr__(self, 'resource_id', resource_id)
        object.__setattr__(self, 'owner_stable_id', owner_stable_id)
        object.__setattr__(self, 'resource_type', resource_type)
        object.__setattr__(self, 'shared', shared)
        object.__setattr__(self, 'properties', MappingProxyType(_copy(dict(properties))))

    @property
    def owner_id(self) -> str:
        return self.owner_stable_id

    @property
    def base(self) -> str:
        return self.resource_type


@dataclass(frozen=True, slots=True)
class ValidationContext:
    """Host observations bound to one project/scene generation and lease."""

    project_id: str
    revision: str
    project_revision: str
    generation: int
    lease_id: str
    fencing_epoch: int
    lease_expires_ms: int
    now_ms: int
    nodes: tuple[NodeState, ...]
    resources: tuple[ResourceState, ...] = ()
    stopped: bool = False
    profile: str = PROFILE


@dataclass(frozen=True, slots=True)
class ValidatedCommand:
    """Detached proposed effect.  Properties parse a fresh copy every time."""

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


def _context(context: ValidationContext) -> tuple[dict[str, NodeState], dict[str, ResourceState]]:
    _need(type(context) is ValidationContext and context.profile == PROFILE, 'AUTHORING_TRUSTED_CONTEXT_REQUIRED')
    _need(_matches(context.project_id, _ID) and _matches(context.lease_id, _ID), 'AUTHORING_CONTEXT_ID')
    _need(_matches(context.revision, _REV) and _matches(context.project_revision, _REV), 'AUTHORING_REVISION')
    _need(_integer(context.generation, 1, 2147483647) and type(context.stopped) is bool, 'AUTHORING_CONTEXT')
    _need(all(_integer(value) for value in (context.fencing_epoch, context.lease_expires_ms, context.now_ms)),
          'AUTHORING_CONTEXT')
    _need(type(context.nodes) is tuple and 1 <= len(context.nodes) <= 64, 'AUTHORING_NODE_LIMIT')
    nodes: dict[str, NodeState] = {}
    for node in context.nodes:
        _need(type(node) is NodeState and _matches(node.stable_id, _ID)
              and node.stable_id not in nodes and _matches(node.node_type, _CLASS)
              and node.node_type in _CONTEXT_NODE_TYPES and _matches(node.name, re.compile(r'[A-Za-z][A-Za-z0-9_]{0,47}\Z')),
              'AUTHORING_NODE_STATE')
        _need(node.parent_id is None or _matches(node.parent_id, _ID), 'AUTHORING_NODE_STATE')
        nodes[node.stable_id] = node
    _need('root' in nodes and nodes['root'].parent_id is None
          and sum(node.parent_id is None for node in nodes.values()) == 1, 'AUTHORING_HIERARCHY')
    for node in nodes.values():
        seen: set[str] = set()
        current: str | None = node.stable_id
        while current is not None:
            _need(current in nodes and current not in seen, 'AUTHORING_HIERARCHY')
            seen.add(current)
            _need(len(seen) <= 16, 'AUTHORING_DEPTH_LIMIT')
            current = nodes[current].parent_id
    _need(type(context.resources) is tuple and len(context.resources) <= 64, 'AUTHORING_RESOURCE_LIMIT')
    resources: dict[str, ResourceState] = {}
    for resource in context.resources:
        _need(type(resource) is ResourceState and _matches(resource.resource_id, _ID)
              and resource.resource_id not in resources and _matches(resource.owner_stable_id, _ID)
              and resource.owner_stable_id in nodes and type(resource.resource_type) is str
              and resource.resource_type in _SHAPE_TYPES
              and type(resource.shared) is bool and type(resource.properties) is MappingProxyType,
              'AUTHORING_RESOURCE_STATE')
        # A host observation must preserve the native shape-node ancestry.  A
        # resource class alone is insufficient: accepting a 2D shape owned by
        # a 3D collider (or vice versa) would let a detached fixture snapshot
        # drift from the node/resource topology the adapter is meant to bind.
        _need((resource.resource_type.endswith('2D')
               and nodes[resource.owner_stable_id].node_type == 'CollisionShape2D')
              or (resource.resource_type.endswith('3D')
                  and nodes[resource.owner_stable_id].node_type == 'CollisionShape3D'),
              'AUTHORING_RESOURCE_NODE_TYPE')
        _need(_shape_properties(resource.resource_type, resource.properties, allow_empty=True),
              'AUTHORING_RESOURCE_STATE')
        resources[resource.resource_id] = resource
    return nodes, resources


def _shape_properties(resource_type: str, properties: object, *, allow_empty: bool = False) -> bool:
    if type(properties) is not MappingProxyType and type(properties) is not dict:
        return False
    required = {'size'} if resource_type in ('RectangleShape2D', 'BoxShape3D') else {'radius', 'height'}
    keys = set(properties)
    if allow_empty and not keys:
        return True
    if keys != required:
        return False
    if 'size' in required:
        values = properties['size']
        arity = 2 if resource_type == 'RectangleShape2D' else 3
        return (type(values) in (list, tuple) and len(values) == arity and
                all(_number(value) and 0 < value <= _DIMENSION_LIMIT for value in values))
    radius, height = properties['radius'], properties['height']
    return (_number(radius) and _number(height) and 0 < radius <= _DIMENSION_LIMIT
            and 0 < height <= _DIMENSION_LIMIT and height >= 2 * radius)


def _validate_properties(resource_type: str, properties: object, *, allow_partial: bool) -> dict[str, Any]:
    required = {'size'} if resource_type in ('RectangleShape2D', 'BoxShape3D') else {'radius', 'height'}
    _need(type(properties) is dict, 'AUTHORING_RESOURCE_PROPERTY_SHAPE')
    _need(bool(properties), 'AUTHORING_EMPTY_UPDATE')
    _need(set(properties) <= required, 'AUTHORING_RESOURCE_PROPERTY_REJECTED')
    if not allow_partial:
        _need(set(properties) == required, 'AUTHORING_RESOURCE_PROPERTY_SHAPE')
    checked: dict[str, Any] = {}
    if 'size' in properties:
        values = properties['size']
        arity = 2 if resource_type == 'RectangleShape2D' else 3
        _need(type(values) is list and len(values) == arity
              and all(_number(value) and 0 < value <= _DIMENSION_LIMIT for value in values),
              'AUTHORING_RESOURCE_PROPERTY_TYPE')
        checked['size'] = list(values)
    for name in ('radius', 'height'):
        if name in properties:
            value = properties[name]
            _need(_number(value) and 0 < value <= _DIMENSION_LIMIT, 'AUTHORING_RESOURCE_PROPERTY_TYPE')
            checked[name] = value
    return checked


def validate_request(request: Request | Mapping[str, Any], context: ValidationContext) -> ValidatedCommand:
    """Validate a resource proposal against trusted scene/resource state."""
    nodes, resources = _context(context)
    checked = Request.from_dict(_copy(request.as_dict() if type(request) is Request else request))
    _need(checked.operation in OPERATIONS, 'AUTHORING_OPERATION_DISABLED')
    _need(_matches(checked.command_id, _ID), 'AUTHORING_COMMAND_ID')
    _need(checked.project_id == context.project_id, 'AUTHORING_PROJECT_MISMATCH')
    _need(checked.expected_revision == context.revision, 'AUTHORING_STALE_REVISION')
    _need(checked.lease_id == context.lease_id and checked.fencing_epoch == context.fencing_epoch,
          'AUTHORING_STALE_LEASE')
    _need(context.now_ms < checked.deadline_ms <= min(context.lease_expires_ms, context.now_ms + 30000),
          'AUTHORING_DEADLINE_EXPIRED')
    _need(not context.stopped, 'AUTHORING_STOPPED')
    _need(len(canonical_bytes(checked.payload)) <= 65536, 'AUTHORING_PAYLOAD_LIMIT')
    target = dict(checked.target)
    payload = dict(checked.payload)
    _shape(target, {'stable_id'})
    stable_id = target['stable_id']
    _need(_matches(stable_id, _ID) and stable_id in nodes, 'AUTHORING_STALE_STABLE_ID')
    common = {'expected_generation', 'expected_project_revision', 'resource_id', 'resource_type'}
    create = checked.operation == 'scene.resource.create'
    _shape(payload, common | ({'properties'} if create else {'changes'}))
    _need(_integer(payload['expected_generation'], 1, 2147483647)
          and payload['expected_generation'] == context.generation, 'AUTHORING_STALE_GENERATION')
    _need(payload['expected_project_revision'] == context.project_revision, 'AUTHORING_STALE_PROJECT_REVISION')
    resource_id, resource_type = payload['resource_id'], payload['resource_type']
    _need(_matches(resource_id, _ID), 'AUTHORING_RESOURCE_ID')
    _need(type(resource_type) is str and resource_type in _SHAPE_TYPES, 'AUTHORING_RESOURCE_TYPE')
    node_type = nodes[stable_id].node_type
    _need((resource_type.endswith('2D') and node_type == 'CollisionShape2D')
          or (resource_type.endswith('3D') and node_type == 'CollisionShape3D'), 'AUTHORING_RESOURCE_NODE_TYPE')
    if create:
        _need(resource_id not in resources, 'AUTHORING_DUPLICATE_RESOURCE_ID')
        changes = _validate_properties(resource_type, payload['properties'], allow_partial=False)
        effective = changes
        _need(_shape_properties(resource_type, effective), 'AUTHORING_CAPSULE_DIMENSIONS')
    else:
        state = resources.get(resource_id)
        _need(state is not None, 'AUTHORING_UNKNOWN_RESOURCE')
        _need(not state.shared, 'AUTHORING_RESOURCE_SHARED')
        _need(state.owner_stable_id == stable_id, 'AUTHORING_RESOURCE_OWNER_MISMATCH')
        _need(state.resource_type == resource_type, 'AUTHORING_RESOURCE_TYPE_MISMATCH')
        changes = _validate_properties(resource_type, payload['changes'], allow_partial=True)
        effective = dict(state.properties)
        effective.update(changes)
        # A capsule's invariant applies to the resulting resource, even when a
        # partial update changes only radius or only height.
        _need(_shape_properties(resource_type, effective), 'AUTHORING_CAPSULE_DIMENSIONS')
    projection_payload = {key: value for key, value in payload.items() if key != 'expected_project_revision'}
    projection = {'operation': checked.operation, 'command_id': checked.command_id,
                  'expected_revision': checked.expected_revision, 'expected_generation': context.generation,
                  'target_stable_id': stable_id, 'payload': projection_payload}
    preview = {'profile': PROFILE, 'authority': AUTHORITY, 'command_id': checked.command_id,
               'request_digest': checked.digest, 'scene_revision': context.revision,
               'project_revision': context.project_revision, 'resource_id': resource_id,
               'resource_type': resource_type, 'effective_properties': effective,
               'changes_applied': False, 'runtime_authorized': False,
               'resource_identity_verified': False, 'native_tests_pending': ['classdb', 'readback', 'undo']}
    return ValidatedCommand(checked.digest, checked.operation, canonical_bytes(projection), canonical_bytes(preview))

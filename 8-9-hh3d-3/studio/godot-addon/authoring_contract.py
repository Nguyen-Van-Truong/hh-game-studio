"""Pure O2 typed-authoring candidate; no engine, writes, ACK, or capability grant.

Reuse the shared Request envelope and existing scene operation names. The new
payload belongs to a separately selected, unregistered profile. Its hand-authored
catalog is NOT a ClassDB extraction. Native readback, UndoRedo, resource identity,
lease rechecks, deduplication and AUTH-01..05 isolation remain integration work.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Mapping

from studio.protocol.core import Request, SAFE_INTEGER, ValidationError, canonical_bytes, parse_json

SCHEMA_PATH = Path(__file__).resolve().parents[1] / 'contracts/godot-authoring-schema-v1.json'
PROFILE = 'hh-godot-gameplay-source-1'
SCRIPT_GATES = ('AUTH-01', 'AUTH-02', 'AUTH-03', 'AUTH-04', 'AUTH-05')
_ID = re.compile(r'[a-z][a-z0-9._-]{0,63}\Z')
_NAME = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,47}\Z')
_CLASS = re.compile(r'[A-Z][A-Za-z0-9_]*\Z')
_PROPERTY = re.compile(r'[a-z][a-z0-9_]*\Z')
_REV = re.compile(r'sha256:[0-9a-f]{64}\Z')
_TYPES = frozenset(('bool', 'int', 'float', 'string', 'vector2', 'vector3', 'enum', 'resource'))
_OPERATIONS = ('scene.node.create', 'scene.node.update')


class ContractError(ValidationError):
    def __init__(self, code: str):
        super().__init__(code, 'O2 candidate validation; no effect authorized')


def _need(condition: object, code: str) -> None:
    if not condition:
        raise ContractError(code)


def _shape(value: object, required: set[str], optional: set[str] = frozenset()) -> None:
    _need(type(value) is dict and required <= set(value) <= required | optional, 'AUTHORING_INVALID_SHAPE')


def _matches(value: object, pattern: re.Pattern) -> bool:
    return type(value) is str and pattern.fullmatch(value) is not None


def _number(value: object) -> bool:
    return type(value) in (int, float) and abs(value) <= SAFE_INTEGER and math.isfinite(value)


def _integer(value: object, minimum: int = 0, maximum: int = SAFE_INTEGER) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _copy(value: Any) -> Any:
    return parse_json(canonical_bytes(value))


@dataclass(frozen=True, slots=True)
class PropertySpec:
    type: str
    writable: bool
    minimum: float | None = None
    maximum: float | None = None
    values: tuple[int, ...] = ()
    resource_base: str | None = None


@dataclass(frozen=True, slots=True)
class ClassSpec:
    class_name: str
    kind: str
    instantiable: bool
    properties: Mapping[str, PropertySpec]


@dataclass(frozen=True, slots=True)
class Catalog:
    """Closed candidate metadata, never native ClassDB or a runtime registry."""
    digest: str
    classes: Mapping[str, ClassSpec]
    resource_bases: frozenset[str]
    _encoded: bytes

    def as_dict(self) -> dict[str, Any]:
        return parse_json(self._encoded)


def load_catalog(path: Path = SCHEMA_PATH) -> Catalog:
    """Read trusted declaration data, rejecting unknown/malformed metadata."""
    document = parse_json(path.read_bytes())
    _need(type(document) is dict and document.get('$id') == 'urn:hh:godot-authoring-catalog:1',
          'AUTHORING_SCHEMA_VERSION')
    raw = document.get('x-candidate')
    required = {'catalog_version', 'profile', 'change_request', 'status', 'native_evidence',
                'runtime_enabled', 'script_enabled', 'required_script_gates', 'operations',
                'resource_bases', 'classes'}
    _shape(raw, required)
    _need(type(raw['catalog_version']) is int and raw['catalog_version'] == 1,
          'AUTHORING_SCHEMA_VERSION')
    fixed = {'profile': PROFILE, 'change_request': 'CR-GODOT-AUTHORING-01',
             'status': 'CANDIDATE_ONLY', 'native_evidence': 'UNVERIFIED',
             'required_script_gates': list(SCRIPT_GATES), 'operations': list(_OPERATIONS)}
    _need(all(raw[k] == v for k, v in fixed.items()), 'AUTHORING_CATALOG_METADATA')
    _need(raw['runtime_enabled'] is False and raw['script_enabled'] is False,
          'AUTHORING_RUNTIME_DISABLED')
    bases = raw['resource_bases']
    _need(type(bases) is list and bases and all(_matches(v, _CLASS) for v in bases)
          and len(bases) == len(set(bases)), 'AUTHORING_RESOURCE_CATALOG')
    rows = raw['classes']
    _need(type(rows) is list and rows, 'AUTHORING_CLASS_CATALOG')
    pending: dict[str, tuple[str | None, str, bool, dict[str, PropertySpec]]] = {}
    for row in rows:
        _shape(row, {'class_name', 'property_base', 'native_base', 'domain', 'kind', 'instantiable', 'properties'})
        name, base, kind = row['class_name'], row['property_base'], row['kind']
        _need(_matches(name, _CLASS) and name not in pending, 'AUTHORING_CLASS_CATALOG')
        _need((base is None or _matches(base, _CLASS)) and _matches(row['native_base'], _CLASS),
              'AUTHORING_CLASS_CATALOG')
        _need(type(row['domain']) is str and row['domain'] in ('2d', '3d', 'ui', 'audio', 'animation', 'input')
              and type(kind) is str and kind in ('node', 'singleton')
              and row['instantiable'] is (kind == 'node'), 'AUTHORING_CLASS_CATALOG')
        _need(type(row['properties']) is dict, 'AUTHORING_PROPERTY_CATALOG')
        _need(kind != 'singleton' or (base is None and not row['properties']), 'AUTHORING_CLASS_CATALOG')
        props = {}
        for prop_name, p in row['properties'].items():
            _need(_matches(prop_name, _PROPERTY), 'AUTHORING_PROPERTY_CATALOG')
            _shape(p, {'type', 'writable'}, {'minimum', 'maximum', 'values', 'resource_base'})
            ptype = p['type']
            _need(type(ptype) is str and ptype in _TYPES and type(p['writable']) is bool,
                  'AUTHORING_PROPERTY_CATALOG')
            extra = {'minimum', 'maximum'} if ptype in ('int', 'float', 'vector2', 'vector3') else (
                {'values'} if ptype == 'enum' else {'resource_base'} if ptype == 'resource' else set())
            _need(set(p) == {'type', 'writable'} | extra, 'AUTHORING_PROPERTY_CATALOG')
            if 'minimum' in extra:
                _need(_number(p['minimum']) and _number(p['maximum']) and p['minimum'] <= p['maximum'],
                      'AUTHORING_PROPERTY_CATALOG')
                _need(ptype != 'int' or (type(p['minimum']) is int and type(p['maximum']) is int),
                      'AUTHORING_PROPERTY_CATALOG')
            if ptype == 'enum':
                values = p['values']
                _need(type(values) is list and values and all(_integer(v, -SAFE_INTEGER) for v in values)
                      and len(values) == len(set(values)), 'AUTHORING_PROPERTY_CATALOG')
            if ptype == 'resource':
                _need(type(p['resource_base']) is str and p['resource_base'] in bases, 'AUTHORING_RESOURCE_CATALOG')
            props[prop_name] = PropertySpec(ptype, p['writable'], p.get('minimum'), p.get('maximum'),
                                             tuple(p.get('values', ())), p.get('resource_base'))
        pending[name] = (base, kind, row['instantiable'], props)
    resolved: dict[str, ClassSpec] = {}

    def resolve(name: str, seen: frozenset[str] = frozenset()) -> ClassSpec:
        _need(name in pending and name not in seen, 'AUTHORING_CLASS_INHERITANCE')
        if name not in resolved:
            base, kind, instantiable, own = pending[name]
            inherited = {} if base is None else dict(resolve(base, seen | {name}).properties)
            _need(base is None or pending[base][1] == kind, 'AUTHORING_CLASS_INHERITANCE')
            _need(not set(own) & set(inherited), 'AUTHORING_PROPERTY_OVERRIDE')
            resolved[name] = ClassSpec(name, kind, instantiable, MappingProxyType({**inherited, **own}))
        return resolved[name]

    for name in pending:
        resolve(name)
    encoded = canonical_bytes(raw)
    return Catalog('sha256:' + hashlib.sha256(encoded).hexdigest(), MappingProxyType(resolved),
                   frozenset(bases), encoded)


@dataclass(frozen=True, slots=True)
class NodeState:
    stable_id: str
    parent_id: str | None
    node_type: str
    name: str


@dataclass(frozen=True, slots=True)
class ResourceState:
    """Trusted manifest identity/class assertion; this module does not load it."""
    resource_id: str
    base: str


@dataclass(frozen=True, slots=True)
class ValidationContext:
    """Host observations only. Never build this from remote request fields."""
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
    """Immutable proposed effect. Access returns copies; this is not an ACK."""
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


def _context(context: ValidationContext, catalog: Catalog) -> tuple[dict[str, NodeState], dict[str, ResourceState]]:
    _need(type(context) is ValidationContext and context.profile == PROFILE, 'AUTHORING_TRUSTED_CONTEXT_REQUIRED')
    _need(_matches(context.project_id, _ID) and _matches(context.lease_id, _ID), 'AUTHORING_CONTEXT_ID')
    _need(_matches(context.revision, _REV) and _matches(context.project_revision, _REV), 'AUTHORING_REVISION')
    _need(_integer(context.generation, 1, 2147483647) and type(context.stopped) is bool, 'AUTHORING_CONTEXT')
    _need(all(_integer(v) for v in (context.fencing_epoch, context.lease_expires_ms, context.now_ms)), 'AUTHORING_CONTEXT')
    _need(type(context.nodes) is tuple and 1 <= len(context.nodes) <= 64, 'AUTHORING_NODE_LIMIT')
    nodes = {}
    for node in context.nodes:
        _need(type(node) is NodeState, 'AUTHORING_NODE_STATE')
        _need(_matches(node.stable_id, _ID) and node.stable_id not in nodes and _matches(node.name, _NAME),
              'AUTHORING_NODE_STATE')
        _need(_matches(node.node_type, _CLASS) and node.node_type in catalog.classes
              and catalog.classes[node.node_type].instantiable, 'AUTHORING_CLASS_REJECTED')
        _need(node.parent_id is None or _matches(node.parent_id, _ID), 'AUTHORING_NODE_STATE')
        nodes[node.stable_id] = node
    _need('root' in nodes and nodes['root'].parent_id is None
          and sum(node.parent_id is None for node in nodes.values()) == 1, 'AUTHORING_HIERARCHY')
    for node in nodes.values():
        seen, current = set(), node.stable_id
        while current is not None:
            _need(current in nodes and current not in seen, 'AUTHORING_HIERARCHY')
            seen.add(current)
            _need(len(seen) <= 16, 'AUTHORING_DEPTH_LIMIT')
            current = nodes[current].parent_id
        siblings = [n.name.lower() for n in nodes.values() if n.parent_id == node.parent_id]
        _need(len(siblings) == len(set(siblings)), 'AUTHORING_DUPLICATE_NAME')
    _need(type(context.resources) is tuple and len(context.resources) <= 64, 'AUTHORING_RESOURCE_LIMIT')
    resources = {}
    for resource in context.resources:
        _need(type(resource) is ResourceState and _matches(resource.resource_id, _ID)
              and resource.resource_id not in resources and type(resource.base) is str
              and resource.base in catalog.resource_bases, 'AUTHORING_RESOURCE_STATE')
        resources[resource.resource_id] = resource
    return nodes, resources


def _properties(changes: object, spec: ClassSpec, resources: Mapping[str, ResourceState]) -> None:
    _need(type(changes) is dict and len(changes) <= 32, 'AUTHORING_PROPERTY_SHAPE')
    for name, value in changes.items():
        _need(name in spec.properties, 'AUTHORING_PROPERTY_REJECTED')
        prop = spec.properties[name]
        _need(prop.writable, 'AUTHORING_PROPERTY_READ_ONLY')
        if prop.type == 'bool':
            valid = type(value) is bool
        elif prop.type in ('int', 'float'):
            valid = _number(value) and (prop.type != 'int' or type(value) is int)
            valid = valid and prop.minimum <= value <= prop.maximum
        elif prop.type in ('vector2', 'vector3'):
            valid = type(value) is list and len(value) == int(prop.type[-1]) and all(
                _number(v) and prop.minimum <= v <= prop.maximum for v in value)
        elif prop.type == 'string':
            valid = type(value) is str and len(value) <= 4096 and '\x00' not in value
        elif prop.type == 'enum':
            valid = type(value) is int and value in prop.values
        else:
            valid = type(value) is dict and set(value) == {'resource_id'} and _matches(value['resource_id'], _ID)
            _need(valid, 'AUTHORING_RESOURCE_REFERENCE')
            resource = resources.get(value['resource_id'])
            _need(resource is not None and resource.base == prop.resource_base, 'AUTHORING_RESOURCE_REFERENCE')
        _need(valid, 'AUTHORING_PROPERTY_TYPE')


def validate_request(request: Request | Mapping[str, Any], context: ValidationContext,
                     catalog: Catalog | None = None) -> ValidatedCommand:
    """Check a typed proposal without authorizing or contacting an engine.

    Script submissions always reject. AUTH gate flags/receipts in a request are
    not trusted evidence. A future registered owner must verify the actual gates
    and implement isolated execution before this profile can ever be enabled.
    """
    catalog = load_catalog() if catalog is None else catalog
    _need(type(catalog) is Catalog, 'AUTHORING_CATALOG_REQUIRED')
    nodes, resources = _context(context, catalog)
    checked = Request.from_dict(_copy(request.as_dict() if type(request) is Request else request))
    _need(checked.operation != 'script_text.replace', 'AUTHORING_SCRIPT_PROFILE_DISABLED')
    _need(checked.operation in _OPERATIONS, 'AUTHORING_OPERATION_DISABLED')
    _need(_matches(checked.command_id, _ID), 'AUTHORING_COMMAND_ID')
    _need(checked.project_id == context.project_id, 'AUTHORING_PROJECT_MISMATCH')
    _need(checked.expected_revision == context.revision, 'AUTHORING_STALE_REVISION')
    _need(checked.lease_id == context.lease_id and checked.fencing_epoch == context.fencing_epoch, 'AUTHORING_STALE_LEASE')
    _need(context.now_ms < checked.deadline_ms <= min(context.lease_expires_ms, context.now_ms + 30000),
          'AUTHORING_DEADLINE_EXPIRED')
    _need(not context.stopped, 'AUTHORING_STOPPED')
    _need(len(canonical_bytes(checked.payload)) <= 65536, 'AUTHORING_PAYLOAD_LIMIT')
    target, payload = dict(checked.target), dict(checked.payload)
    _shape(target, {'stable_id'})
    _need(_matches(target['stable_id'], _ID) and target['stable_id'] in nodes, 'AUTHORING_STALE_STABLE_ID')
    common = {'expected_generation', 'expected_project_revision'}
    create = checked.operation == 'scene.node.create'
    _shape(payload, common | ({'stable_id', 'node_type', 'name', 'properties'} if create else {'changes'}))
    _need(_integer(payload['expected_generation'], 1, 2147483647)
          and payload['expected_generation'] == context.generation, 'AUTHORING_STALE_GENERATION')
    _need(payload['expected_project_revision'] == context.project_revision, 'AUTHORING_STALE_PROJECT_REVISION')
    if create:
        _need(_matches(payload['stable_id'], _ID) and payload['stable_id'] not in nodes, 'AUTHORING_DUPLICATE_STABLE_ID')
        _need(_matches(payload['name'], _NAME) and all(n.name.lower() != payload['name'].lower()
              for n in nodes.values() if n.parent_id == target['stable_id']), 'AUTHORING_DUPLICATE_NAME')
        node_type = payload['node_type']
        _need(_matches(node_type, _CLASS) and node_type in catalog.classes
              and catalog.classes[node_type].instantiable, 'AUTHORING_CLASS_REJECTED')
        _need(len(nodes) < 64, 'AUTHORING_NODE_LIMIT')
        depth, ancestor = 1, target['stable_id']
        while ancestor is not None:
            depth, ancestor = depth + 1, nodes[ancestor].parent_id
        _need(depth <= 16, 'AUTHORING_DEPTH_LIMIT')
        changes = payload['properties']
    else:
        node_type = nodes[target['stable_id']].node_type
        changes = payload['changes']
        _need(type(changes) is dict and bool(changes), 'AUTHORING_EMPTY_UPDATE')
    _properties(changes, catalog.classes[node_type], resources)
    # Exactly the same envelope/projection vocabulary as the accepted adapter;
    # payload shape is selected only by this separate candidate profile.
    projection = {'operation': checked.operation, 'command_id': checked.command_id,
                  'expected_revision': checked.expected_revision, 'expected_generation': context.generation,
                  'target_stable_id': target['stable_id'],
                  'payload': {k: v for k, v in payload.items() if k != 'expected_project_revision'}}
    preview = {'profile': PROFILE, 'catalog_version': 1, 'catalog_digest': catalog.digest,
               'command_id': checked.command_id, 'request_digest': checked.digest,
               'scene_revision': context.revision, 'project_revision': context.project_revision,
               'changes_applied': False, 'runtime_authorized': False, 'classdb_verified': False,
               'native_tests_pending': ['classdb_extraction', 'reject', 'readback', 'undo'],
               'script_enabled': False, 'required_script_gates': list(SCRIPT_GATES)}
    return ValidatedCommand(checked.digest, checked.operation, canonical_bytes(projection), canonical_bytes(preview))

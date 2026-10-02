"""Fixed, candidate-only recipe for a natively serialized 2D physics world.

All Requests are validated before this module returns. ValidationContext here
describes a private planning model, never an editor observation, live lease or
permission to apply. The native builder must independently bind its root and
read back each effect. This module does not create nodes, write TSCN, save,
execute gameplay, enable a profile or acknowledge a native mutation.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import re
import sys

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.protocol.core import Request, ValidationError, canonical_bytes, parse_json

SCHEMA = 'hh-o2-saved-arena-recipe-1'
ADMISSION_SCHEMA = 'hh-o2-saved-arena-admission-binding-1'
_OWNER_ID = re.compile(r'[a-z][a-z0-9._-]{0,63}\Z')
_OWNER_REV = re.compile(r'sha256:[0-9a-f]{64}\Z')


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, STUDIO / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_NODE = _load('hh_saved_arena_node_contract', 'godot-addon/authoring_contract.py')
_RESOURCE = _load('hh_saved_arena_resource_contract', 'godot-addon/resource_authoring.py')


def source_paths() -> tuple[str, ...]:
    """Exact source inputs for the recipe; the runner binds their actual bytes."""
    return ('tests/godot/saved_arena_recipe.py',
            'contracts/godot-authoring-schema-v1.json',
            'godot-addon/authoring_contract.py', 'godot-addon/resource_authoring.py',
            'protocol/__init__.py', 'protocol/core.py',
            'protocol/_rfc8785/__init__.py', 'protocol/_rfc8785/_impl.py')


def _copy(value):
    return parse_json(canonical_bytes(value))


def _revision(value):
    return 'sha256:' + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _node_properties(position):
    return {'position': list(position), 'rotation': 0, 'scale': [1, 1], 'visible': True}


def _planned_context(module, snapshot, project_revision):
    # The model's digest changes after each proposed effect. These are stable
    # planning placeholders, explicitly not runtime credentials or observations.
    nodes = tuple(module.NodeState(row['stable_id'], row['parent_id'],
                                  row['node_type'], row['name']) for row in snapshot['nodes'])
    resources = ()
    if module is _RESOURCE:
        resources = tuple(module.ResourceState(row['resource_id'], row['owner_stable_id'],
                          row['resource_type'], properties=row['properties'])
                          for row in snapshot['resources'])
    return module.ValidationContext('project.saved.arena.plan', _revision(snapshot),
        project_revision, 1, 'lease.recipe.plan', 1, 30000, 0, nodes, resources)


def _request(context, operation, command_id, target, payload):
    body = {**payload, 'expected_generation': context.generation,
            'expected_project_revision': context.project_revision}
    return Request(command_id=command_id, project_id=context.project_id,
        operation=operation, lease_id=context.lease_id, fencing_epoch=context.fencing_epoch,
        expected_revision=context.revision, target={'stable_id': target}, payload=body,
        payload_hash=_revision(body), deadline_ms=1000)


def _admission_need(condition, code):
    if not condition:
        raise ValidationError(code, 'saved-arena owner admission binding')


def _admission_context(module, snapshot, admission):
    """Create candidate trusted context from an owner admission observation.

    This is an adapter only: the owner supplies these fields after its own
    inspect/lease checks.  It never authenticates, submits, or mutates.
    """
    nodes = tuple(module.NodeState(row['stable_id'], row['parent_id'], row['node_type'], row['name'])
                  for row in snapshot['nodes'])
    resources = ()
    if module is _RESOURCE:
        resources = tuple(module.ResourceState(row['resource_id'], row['owner_stable_id'],
                          row['resource_type'], properties=row['properties'])
                          for row in snapshot['resources'])
    return module.ValidationContext(admission['project_id'], admission['revision'],
        admission['project_revision'], admission['generation'], admission['lease_id'],
        admission['fencing_epoch'], admission['lease_expires_ms'], admission['now_ms'],
        nodes, resources)


def bind_recipe_to_owner_admission(recipe, admission, *, deadline_ms=None):
    """Bind planned recipe projections to a registered owner's admission fields.

    The result contains detached requests and candidate projections suitable for
    a future owner call.  Existing node/resource validators run against the
    supplied owner observation, so stale generations, leases, revisions and
    malformed projections fail closed.  This function does not call the owner,
    issue ACKs, or imply native/readback proof.
    """
    _admission_need(type(recipe) is dict and recipe.get('schema') == SCHEMA,
                    'ARENA_RECIPE_SCHEMA')
    _admission_need(recipe.get('authority') == 0 and recipe.get('state_kind') == 'PLANNED_NOT_NATIVE'
                    and recipe.get('runtime_authorized') is False and recipe.get('native_observed') is False,
                    'ARENA_RECIPE_AUTHORITY')
    required = {'project_id', 'revision', 'project_revision', 'generation', 'lease_id',
                'fencing_epoch', 'lease_expires_ms', 'now_ms'}
    _admission_need(type(admission) is dict and set(admission) == required, 'ARENA_ADMISSION_SHAPE')
    _admission_need(_OWNER_ID.fullmatch(admission['project_id']) is not None
                    and _OWNER_ID.fullmatch(admission['lease_id']) is not None
                    and _OWNER_REV.fullmatch(admission['revision']) is not None
                    and _OWNER_REV.fullmatch(admission['project_revision']) is not None,
                    'ARENA_ADMISSION_ID')
    for field in ('generation', 'fencing_epoch', 'lease_expires_ms', 'now_ms'):
        _admission_need(type(admission[field]) is int and admission[field] >= 0,
                        'ARENA_ADMISSION_INTEGER')
    _admission_need(admission['generation'] >= 1 and admission['now_ms'] < admission['lease_expires_ms'],
                    'ARENA_ADMISSION_LIFETIME')
    if deadline_ms is None:
        deadline_ms = min(admission['lease_expires_ms'] - 1, admission['now_ms'] + 1000)
    _admission_need(type(deadline_ms) is int and admission['now_ms'] < deadline_ms <= admission['lease_expires_ms'],
                    'ARENA_ADMISSION_DEADLINE')

    snapshot = _copy(recipe.get('initial_snapshot'))
    expected = _copy(recipe.get('expected_snapshot'))
    _admission_need(type(snapshot) is dict and type(expected) is dict
                    and snapshot.get('nodes') and snapshot.get('resources') == [],
                    'ARENA_RECIPE_SNAPSHOT')
    nodes = list(snapshot['nodes'])
    resources = []
    bound = []
    seen_commands = set()
    catalog = _NODE.load_catalog()

    def bind_one(module, projection, current):
        _admission_need(type(projection) is dict and set(projection) == {
            'operation', 'command_id', 'expected_revision', 'expected_generation',
            'target_stable_id', 'payload'}, 'ARENA_PROJECTION_SHAPE')
        command_id, operation = projection['command_id'], projection['operation']
        _admission_need(command_id not in seen_commands, 'ARENA_COMMAND_DUPLICATE')
        seen_commands.add(command_id)
        payload = _copy(projection['payload'])
        payload['expected_generation'] = admission['generation']
        payload['expected_project_revision'] = admission['project_revision']
        request = Request(command_id=command_id, project_id=admission['project_id'],
            operation=operation, lease_id=admission['lease_id'],
            fencing_epoch=admission['fencing_epoch'], expected_revision=admission['revision'],
            target={'stable_id': projection['target_stable_id']}, payload=payload,
            payload_hash=_revision(payload), deadline_ms=deadline_ms)
        context = _admission_context(module, {'nodes': nodes, 'resources': resources}, admission)
        validated = module.validate_request(request, context, catalog) if module is _NODE \
            else module.validate_request(request, context)
        bound.append({'command_id': command_id, 'operation': operation,
                      'target_stable_id': projection['target_stable_id'],
                      'request': request.as_dict(),
                      'request_digest': request.digest,
                      'projection_sha256': hashlib.sha256(canonical_bytes(validated.projection)).hexdigest()})
        return request

    for projection in recipe.get('node_commands', ()):
        request = bind_one(_NODE, projection, nodes)
        payload = request.payload
        nodes.append({'stable_id': payload['stable_id'], 'parent_id': request.target['stable_id'],
                      'node_type': payload['node_type'], 'name': payload['name'],
                      'properties': _copy(payload['properties'])})
    for projection in recipe.get('resource_commands', ()):
        request = bind_one(_RESOURCE, projection, resources)
        payload = request.payload
        resources.append({'resource_id': payload['resource_id'],
                          'owner_stable_id': request.target['stable_id'],
                          'resource_type': payload['resource_type'],
                          'properties': _copy(payload['properties'])})
    _admission_need({'nodes': nodes, 'resources': resources} == expected,
                    'ARENA_EXPECTED_SNAPSHOT_MISMATCH')
    return _copy({'schema': ADMISSION_SCHEMA, 'authority': 0, 'state_kind': 'PLANNED_NOT_NATIVE',
        'native_observed': False, 'public_ack': False,
        'admission': {**admission, 'deadline_ms': deadline_ms},
        'commands': bound, 'node_command_count': len(recipe.get('node_commands', ())),
        'resource_command_count': len(recipe.get('resource_commands', ()))})


def build_recipe() -> dict:
    """Return detached, canonical-JSON-compatible planned commands and semantics.

    node_commands and resource_commands are the existing validators' immutable
    projections copied into this document. Their envelope preconditions describe
    only the planning model. expected_snapshot uses stable IDs and resource IDs,
    with no ObjectIDs or claims that native objects have been observed.
    """
    catalog = _NODE.load_catalog()
    root = {'stable_id': 'root', 'node_type': 'Node2D', 'name': 'Arena',
            'properties': _node_properties((0, 0))}
    snapshot = {'nodes': [{**_copy(root), 'parent_id': None}], 'resources': []}
    project_revision = _revision({'schema': SCHEMA, 'root': root, 'state_kind': 'PLANNED_NOT_NATIVE'})
    initial_snapshot = _copy(snapshot)
    node_commands, resource_commands, request_digests = [], [], {}
    collision_objects = (
        ('player', 'Player', 'CharacterBody2D', (32, 174), (16, 32), 2, 1),
        ('floor', 'Floor', 'StaticBody2D', (200, 200), (400, 20), 1, 1),
        ('wall', 'Wall', 'StaticBody2D', (300, 110), (20, 160), 1, 1),
        ('pickup', 'Pickup', 'Area2D', (70, 174), (16, 16), 4, 2),
        ('bot', 'Bot', 'Area2D', (220, 174), (20, 28), 8, 16))
    node_specs = []
    for stable_id, name, node_type, position, _size, layer, mask in collision_objects:
        properties = {**_node_properties(position), 'collision_layer': layer, 'collision_mask': mask}
        if node_type == 'CharacterBody2D':
            properties.update(velocity=[0, 0], motion_mode=0, up_direction=[0, -1])
        elif node_type == 'Area2D':
            properties.update(monitoring=True, monitorable=True)
        node_specs.extend(((stable_id, 'root', node_type, name, properties),
                           (stable_id + '_shape', stable_id, 'CollisionShape2D', 'Shape',
                            {**_node_properties((0, 0)), 'disabled': False})))
    node_specs.append(('camera', 'root', 'Camera2D', 'Camera',
                       {**_node_properties((0, 0)), 'enabled': True, 'zoom': [1, 1]}))
    node_specs.extend((('hud_layer', 'root', 'CanvasLayer', 'HUD', {}),
                       ('hud_label', 'hud_layer', 'Label', 'Status',
                        {'position': [8, 8], 'visible': True, 'mouse_filter': 2,
                         'text': 'HP 3'})))
    # Every node request is validated first, in parent-before-child order.
    for identity, parent, kind, node_name, values in node_specs:
        context = _planned_context(_NODE, snapshot, project_revision)
        request = _request(context, 'scene.node.create', 'recipe.node.' + identity, parent,
            {'stable_id': identity, 'node_type': kind, 'name': node_name, 'properties': values})
        command = _NODE.validate_request(request, context, catalog)
        node_commands.append(command.projection)
        request_digests[request.command_id] = command.request_digest
        snapshot['nodes'].append({'stable_id': identity, 'parent_id': parent,
                                  'node_type': kind, 'name': node_name, 'properties': _copy(values)})
    # Resource contexts retain the actual planned collision ancestry; no flattened
    # Collider->root fiction is used to satisfy the resource contract.
    for stable_id, _name, _kind, _position, size, _layer, _mask in collision_objects:
        context = _planned_context(_RESOURCE, snapshot, project_revision)
        owner_id, resource_id = stable_id + '_shape', 'shape.' + stable_id
        properties = {'size': list(size)}
        request = _request(context, 'scene.resource.create', 'recipe.resource.' + owner_id, owner_id,
            {'resource_id': resource_id, 'resource_type': 'RectangleShape2D', 'properties': properties})
        command = _RESOURCE.validate_request(request, context)
        resource_commands.append(command.projection)
        request_digests[request.command_id] = command.request_digest
        snapshot['resources'].append({'resource_id': resource_id, 'owner_stable_id': owner_id,
                                     'resource_type': 'RectangleShape2D', 'properties': properties})
    return _copy({'schema': SCHEMA, 'authority': 0, 'state_kind': 'PLANNED_NOT_NATIVE',
        'runtime_authorized': False, 'public_ack': False, 'native_observed': False,
        'catalog_sha256': catalog.digest.removeprefix('sha256:'), 'root': root,
        'root_bootstrap': {'kind': 'FIXED_SCRIPT_FREE_ROOT', 'create_command': False,
                           'properties_are_planned_defaults': True, 'native_readback_required': True},
        'ownership': {'root_owner': None, 'descendant_owner_stable_id': 'root'},
        'validation_scope': 'STATIC_RECIPE_ONLY; planning preconditions are not runtime grants',
        'planned_project_revision': project_revision, 'initial_snapshot': initial_snapshot,
        'node_commands': node_commands, 'resource_commands': resource_commands,
        'request_digests': request_digests, 'expected_snapshot': snapshot})

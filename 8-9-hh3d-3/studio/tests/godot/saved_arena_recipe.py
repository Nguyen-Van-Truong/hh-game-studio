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
import sys

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.protocol.core import Request, canonical_bytes, parse_json

SCHEMA = 'hh-o2-saved-arena-recipe-1'


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

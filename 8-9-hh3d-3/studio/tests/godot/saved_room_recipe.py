"""Detached, candidate-only recipe for a small Blender-to-Godot 3D room.

The recipe is deliberately pure: it validates typed node/resource projections,
binds an owner admission for planning provenance, and records an explicit
GLB/manifest hash reference.  It never imports Blender output, contacts an
editor, saves a scene, or grants runtime/ACK authority.
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

SCHEMA = 'hh-o2-saved-room-recipe-1'
ADMISSION_SCHEMA = 'hh-o2-saved-room-admission-binding-1'
_ID = re.compile(r'[a-z][a-z0-9._-]{0,63}\Z')
_REV = re.compile(r'sha256:[0-9a-f]{64}\Z')
_HEX = re.compile(r'[0-9a-f]{64}\Z')
_ASSET_PATH = re.compile(r'assets/[a-z][a-z0-9._-]{0,63}\.(?:glb|json)\Z')


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, STUDIO / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_NODE = _load('hh_saved_room_node_contract', 'godot-addon/authoring_contract.py')
_RESOURCE = _load('hh_saved_room_resource_contract', 'godot-addon/resource_authoring.py')


def source_paths() -> tuple[str, ...]:
    return ('tests/godot/saved_room_recipe.py',
            'contracts/godot-authoring-schema-v1.json',
            'godot-addon/authoring_contract.py', 'godot-addon/resource_authoring.py',
            'protocol/__init__.py', 'protocol/core.py',
            'protocol/_rfc8785/__init__.py', 'protocol/_rfc8785/_impl.py')


def _copy(value):
    return parse_json(canonical_bytes(value))


def _revision(value):
    return 'sha256:' + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _need(condition, code):
    if not condition:
        raise ValidationError(code, 'saved-room owner admission binding')


def _node_properties(position=(0, 0, 0)):
    return {'position': list(position), 'rotation': [0, 0, 0],
            'scale': [1, 1, 1], 'visible': True}


def _node_context(snapshot, project_revision):
    rows = tuple(_NODE.NodeState(row['stable_id'], row['parent_id'],
                                 row['node_type'], row['name'])
                 for row in snapshot['nodes'])
    resources = tuple(_NODE.ResourceState(row['resource_id'], row['base'])
                      for row in snapshot.get('asset_resources', ()))
    # Shape resources are retained in the candidate snapshot after creation;
    # expose them for node resource-reference validation too.
    resources += tuple(_NODE.ResourceState(row['resource_id'], 'Shape3D')
                       for row in snapshot.get('resources', ()))
    return _NODE.ValidationContext('project.saved.room.plan', _revision(snapshot),
        project_revision, 1, 'lease.recipe.plan', 1, 30000, 0, rows, resources)


def _resource_context(snapshot, project_revision):
    rows = tuple(_RESOURCE.NodeState(row['stable_id'], row['parent_id'],
                                     row['node_type'], row['name'])
                 for row in snapshot['nodes'])
    resources = tuple(_RESOURCE.ResourceState(row['resource_id'], row['owner_stable_id'],
                          row['resource_type'], properties=row['properties'])
                      for row in snapshot.get('resources', ()))
    return _RESOURCE.ValidationContext('project.saved.room.plan', _revision(snapshot),
        project_revision, 1, 'lease.recipe.plan', 1, 30000, 0, rows, resources)


def _request(context, operation, command_id, target, payload):
    body = {**payload, 'expected_generation': context.generation,
            'expected_project_revision': context.project_revision}
    return Request(command_id=command_id, project_id=context.project_id,
        operation=operation, lease_id=context.lease_id,
        fencing_epoch=context.fencing_epoch, expected_revision=context.revision,
        target={'stable_id': target}, payload=body,
        payload_hash=_revision(body), deadline_ms=1000)


def _admission_context(module, snapshot, admission):
    nodes = tuple(module.NodeState(row['stable_id'], row['parent_id'],
                                   row['node_type'], row['name'])
                  for row in snapshot['nodes'])
    if module is _NODE:
        resources = tuple(_NODE.ResourceState(row['resource_id'], row['base'])
                          for row in snapshot.get('asset_resources', ()))
        resources += tuple(_NODE.ResourceState(row['resource_id'], 'Shape3D')
                           for row in snapshot.get('resources', ()))
    else:
        resources = tuple(_RESOURCE.ResourceState(row['resource_id'], row['owner_stable_id'],
                             row['resource_type'], properties=row['properties'])
                          for row in snapshot.get('resources', ()))
    return module.ValidationContext(admission['project_id'], admission['revision'],
        admission['project_revision'], admission['generation'], admission['lease_id'],
        admission['fencing_epoch'], admission['lease_expires_ms'], admission['now_ms'],
        nodes, resources)


def _validate_admission(recipe, admission, deadline_ms):
    _need(type(recipe) is dict and recipe.get('schema') == SCHEMA, 'ROOM_RECIPE_SCHEMA')
    _need(recipe.get('authority') == 0 and recipe.get('state_kind') == 'PLANNED_NOT_NATIVE'
          and recipe.get('runtime_authorized') is False
          and recipe.get('native_observed') is False, 'ROOM_RECIPE_AUTHORITY')
    required = {'project_id', 'revision', 'project_revision', 'generation', 'lease_id',
                'fencing_epoch', 'lease_expires_ms', 'now_ms'}
    _need(type(admission) is dict and set(admission) == required, 'ROOM_ADMISSION_SHAPE')
    _need(_ID.fullmatch(admission['project_id']) and _ID.fullmatch(admission['lease_id'])
          and _REV.fullmatch(admission['revision']) and _REV.fullmatch(admission['project_revision']),
          'ROOM_ADMISSION_ID')
    for field in ('generation', 'fencing_epoch', 'lease_expires_ms', 'now_ms'):
        _need(type(admission[field]) is int and admission[field] >= 0, 'ROOM_ADMISSION_INTEGER')
    _need(admission['generation'] >= 1 and admission['now_ms'] < admission['lease_expires_ms'],
          'ROOM_ADMISSION_LIFETIME')
    if deadline_ms is None:
        deadline_ms = min(admission['lease_expires_ms'] - 1, admission['now_ms'] + 1000)
    _need(type(deadline_ms) is int and admission['now_ms'] < deadline_ms <= admission['lease_expires_ms'],
          'ROOM_ADMISSION_DEADLINE')
    assets = recipe.get('asset_bindings')
    _need(type(assets) is list and len(assets) == 1, 'ROOM_ASSET_BINDINGS')
    asset = assets[0]
    _need(type(asset) is dict and set(asset) == {
        'asset_id', 'source', 'path', 'format', 'sha256', 'manifest_path',
        'manifest_sha256', 'import_readback_required', 'asset_import_verified',
        'native_observed'}, 'ROOM_ASSET_SHAPE')
    _need(_ID.fullmatch(asset['asset_id']) and asset['source'] == 'Blender'
          and asset['format'] == 'GLB' and _ASSET_PATH.fullmatch(asset['path'])
          and _ASSET_PATH.fullmatch(asset['manifest_path'])
          and _HEX.fullmatch(asset['sha256']) and _HEX.fullmatch(asset['manifest_sha256']),
          'ROOM_ASSET_IDENTITY')
    _need(asset['import_readback_required'] is True and asset['asset_import_verified'] is False
          and asset['native_observed'] is False, 'ROOM_ASSET_AUTHORITY')
    refs = recipe.get('asset_resource_refs')
    _need(type(refs) is dict and refs == {'mesh.avatar': asset['asset_id']},
          'ROOM_ASSET_REFERENCE')
    return deadline_ms


def bind_recipe_to_owner_admission(recipe, admission, *, deadline_ms=None):
    """Bind projections to one owner observation as detached planning data.

    Every envelope deliberately retains the same observed revision.  It is not
    a sequential command stream: a native owner must re-admit before each
    effect and perform readback/ACK independently.
    """
    deadline_ms = _validate_admission(recipe, admission, deadline_ms)
    snapshot = _copy(recipe['initial_snapshot'])
    expected = _copy(recipe['expected_snapshot'])
    catalog = _NODE.load_catalog()
    bound = []
    seen = set()

    def bind(module, projection, phase):
        _need(type(projection) is dict and set(projection) == {
            'operation', 'command_id', 'expected_revision', 'expected_generation',
            'target_stable_id', 'payload'}, 'ROOM_PROJECTION_SHAPE')
        _need(projection['command_id'] not in seen, 'ROOM_COMMAND_DUPLICATE')
        seen.add(projection['command_id'])
        payload = _copy(projection['payload'])
        payload['expected_generation'] = admission['generation']
        payload['expected_project_revision'] = admission['project_revision']
        request = Request(command_id=projection['command_id'],
            project_id=admission['project_id'], operation=projection['operation'],
            lease_id=admission['lease_id'], fencing_epoch=admission['fencing_epoch'],
            expected_revision=admission['revision'],
            target={'stable_id': projection['target_stable_id']}, payload=payload,
            payload_hash=_revision(payload), deadline_ms=deadline_ms)
        context = _admission_context(module, snapshot, admission)
        validated = (module.validate_request(request, context, catalog)
                     if module is _NODE else module.validate_request(request, context))
        bound.append({'phase': phase, 'command_id': request.command_id,
                      'operation': request.operation,
                      'target_stable_id': request.target['stable_id'],
                      'request': request.as_dict(), 'request_digest': request.digest,
                      'projection_sha256': hashlib.sha256(
                          canonical_bytes(validated.projection)).hexdigest()})
        if module is _NODE and request.operation == 'scene.node.create':
            row = {'stable_id': payload['stable_id'], 'parent_id': request.target['stable_id'],
                   'node_type': payload['node_type'], 'name': payload['name'],
                   'properties': _copy(payload['properties'])}
            snapshot['nodes'].append(row)
        elif module is _NODE and request.operation == 'scene.node.update':
            target = request.target['stable_id']
            for row in snapshot['nodes']:
                if row['stable_id'] == target:
                    row['properties'].update(_copy(payload['changes']))
                    break
        elif module is _RESOURCE:
            snapshot['resources'].append({
                'resource_id': payload['resource_id'],
                'owner_stable_id': request.target['stable_id'],
                'resource_type': payload['resource_type'],
                'properties': _copy(payload['properties'])})

    creates = [p for p in recipe['node_commands'] if p['operation'] == 'scene.node.create']
    updates = [p for p in recipe['node_commands'] if p['operation'] == 'scene.node.update']
    for projection in creates:
        bind(_NODE, projection, 'node.create')
    for projection in recipe['resource_commands']:
        bind(_RESOURCE, projection, 'resource.create')
    for projection in updates:
        bind(_NODE, projection, 'node.update')
    _need(snapshot == expected, 'ROOM_EXPECTED_SNAPSHOT_MISMATCH')
    return _copy({'schema': ADMISSION_SCHEMA, 'authority': 0,
        'state_kind': 'PLANNED_NOT_NATIVE', 'runtime_authorized': False,
        'native_observed': False, 'public_ack': False,
        'execution': {'mode': 'DETACHED_PLAN_ONLY', 'sequential_apply_supported': False,
                      'requires_fresh_owner_admission_per_effect': True},
        'admission': {**admission, 'deadline_ms': deadline_ms}, 'commands': bound,
        'node_command_count': len(recipe['node_commands']),
        'resource_command_count': len(recipe['resource_commands']),
        'asset_bindings': _copy(recipe['asset_bindings'])})


def build_recipe() -> dict:
    catalog = _NODE.load_catalog()
    root = {'stable_id': 'root', 'node_type': 'Node3D', 'name': 'Room',
            'properties': _node_properties()}
    snapshot = {'nodes': [{**_copy(root), 'parent_id': None}], 'resources': [],
                'asset_resources': [{'resource_id': 'mesh.avatar', 'base': 'Mesh'}]}
    project_revision = _revision({'schema': SCHEMA, 'root': root,
                                  'state_kind': 'PLANNED_NOT_NATIVE'})
    node_commands, resource_commands, request_digests = [], [], {}

    node_specs = [
        ('avatar', 'root', 'CharacterBody3D', 'Avatar',
         {**_node_properties((0, 1, 0)), 'velocity': [0, 0, 0], 'motion_mode': 0,
          'up_direction': [0, 1, 0]}),
        ('avatar_shape', 'avatar', 'CollisionShape3D', 'AvatarShape', {'disabled': False}),
        ('avatar_mesh', 'avatar', 'MeshInstance3D', 'AvatarMesh',
         {'mesh': {'resource_id': 'mesh.avatar'}}),
        ('platform', 'root', 'StaticBody3D', 'Platform',
         {**_node_properties((0, 0, 0)), 'collision_layer': 1, 'collision_mask': 1}),
        ('platform_shape', 'platform', 'CollisionShape3D', 'PlatformShape', {'disabled': False}),
        ('trigger', 'root', 'Area3D', 'Trigger',
         {**_node_properties((0, 1, -3)), 'monitoring': True, 'monitorable': True}),
        ('trigger_shape', 'trigger', 'CollisionShape3D', 'TriggerShape', {'disabled': False}),
        ('camera', 'root', 'Camera3D', 'Camera', {**_node_properties((0, 2, 6)),
                                                   'current': True, 'fov': 65}),
    ]
    for identity, parent, kind, name, properties in node_specs:
        context = _node_context(snapshot, project_revision)
        request = _request(context, 'scene.node.create', 'room.node.' + identity,
                           parent, {'stable_id': identity, 'node_type': kind,
                                    'name': name, 'properties': properties})
        command = _NODE.validate_request(request, context, catalog)
        node_commands.append(command.projection)
        request_digests[request.command_id] = request.digest
        snapshot['nodes'].append({'stable_id': identity, 'parent_id': parent,
                                  'node_type': kind, 'name': name,
                                  'properties': _copy(properties)})

    resources = [
        ('avatar_shape', 'shape.avatar', 'CapsuleShape3D', {'radius': 0.35, 'height': 1.8}),
        ('platform_shape', 'shape.platform', 'BoxShape3D', {'size': [8, 0.4, 4]}),
        ('trigger_shape', 'shape.trigger', 'BoxShape3D', {'size': [2, 1, 0.5]}),
    ]
    for owner, resource_id, resource_type, properties in resources:
        context = _resource_context(snapshot, project_revision)
        request = _request(context, 'scene.resource.create', 'room.resource.' + owner,
                           owner, {'resource_id': resource_id, 'resource_type': resource_type,
                                   'properties': properties})
        command = _RESOURCE.validate_request(request, context)
        resource_commands.append(command.projection)
        request_digests[request.command_id] = request.digest
        snapshot['resources'].append({'resource_id': resource_id, 'owner_stable_id': owner,
                                      'resource_type': resource_type,
                                      'properties': _copy(properties)})

    # Assign each shape after its owning node and resource exist.  This keeps
    # parent-before-child and resource-owner checks explicit in the plan.
    for node_id, resource_id in (('avatar_shape', 'shape.avatar'),
                                 ('platform_shape', 'shape.platform'),
                                 ('trigger_shape', 'shape.trigger')):
        context = _node_context(snapshot, project_revision)
        request = _request(context, 'scene.node.update', 'room.bind.' + node_id,
                           node_id, {'changes': {'shape': {'resource_id': resource_id}}})
        command = _NODE.validate_request(request, context, catalog)
        node_commands.append(command.projection)
        request_digests[request.command_id] = request.digest
        for row in snapshot['nodes']:
            if row['stable_id'] == node_id:
                row['properties']['shape'] = {'resource_id': resource_id}
                break

    asset = {'asset_id': 'avatar_blender', 'source': 'Blender', 'path': 'assets/avatar.glb',
             'format': 'GLB', 'sha256': 'a' * 64, 'manifest_path': 'assets/manifest.json',
             'manifest_sha256': 'b' * 64, 'import_readback_required': True,
             'asset_import_verified': False, 'native_observed': False}
    return _copy({'schema': SCHEMA, 'authority': 0,
        'state_kind': 'PLANNED_NOT_NATIVE', 'runtime_authorized': False,
        'public_ack': False, 'native_observed': False,
        'catalog_sha256': catalog.digest.removeprefix('sha256:'), 'root': root,
        'asset_bindings': [asset],
        'asset_resource_refs': {'mesh.avatar': 'avatar_blender'},
        'validation_scope': 'STATIC_RECIPE_ONLY; Blender import/readback remains pending',
        'planned_project_revision': project_revision,
        'initial_snapshot': {'nodes': [{**_copy(root), 'parent_id': None}],
                             'resources': [], 'asset_resources': snapshot['asset_resources']},
        'node_commands': node_commands, 'resource_commands': resource_commands,
        'request_digests': request_digests,
        'expected_snapshot': snapshot})

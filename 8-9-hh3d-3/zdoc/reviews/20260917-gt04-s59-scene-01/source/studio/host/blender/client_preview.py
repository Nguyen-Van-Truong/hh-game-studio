"""Pure bounded preview binding and diffs of received Blender observations.

Native revisions remain opaque: their float-preserving JSON domain differs
from the received JCS snapshot. These helpers neither call Blender nor issue
authority, reserve a command ID, predict an apply revision, or prove an effect.
"""
import hashlib
import math
import re

from studio.protocol.core import Request, ValidationError, canonical_bytes, parse_json
from . import client_write_catalog as catalog
from . import publication_state as publication

queue = catalog.queue
MAX_OBJECTS = queue.c.MAX_OBJECTS
MAX_MATERIALS = queue.base.materials.MAX_MATERIALS
MAX_OBSERVATION_BYTES = catalog.MAX_WIRE // 2
MAX_PREVIEW_BYTES = catalog.MAX_WIRE
MAX_DIFF_BYTES = catalog.MAX_WIRE
MAX_NAME_BYTES = 256
PREVIEW_SCHEMA = 'HH-BLENDER-UI-PREVIEW-1'
CLIENT_PREVIEW_SCHEMA = 'HH-BLENDER-CLIENT-PREVIEW-1'
UNDO_POLICY = 'native-revision-checked-session-history'
VALUE_POLICY = 'requested-values; apply-readback-uses-native-binary32'
DIFF_DOMAIN = 'received-jcs-snapshot-context-v1'
_HASH = re.compile(r'sha256:[0-9a-f]{64}\Z')
_GENERATION = re.compile(r'[0-9a-f]{32}\Z')
_OBJECT_FIELDS = frozenset({'object_id', 'name', 'mesh_name', 'location', 'rotation', 'scale', 'vertices', 'faces'})
_MATERIAL_FIELDS = frozenset({'material_id', 'name', 'base_color', 'metallic', 'roughness', 'double_sided', 'alpha_mode'})


def _need(value, code):
    if not value:
        raise ValidationError(code, 'bounded registered Blender observation required')


def _shape(value, fields, code='BLENDER_PREVIEW_SHAPE'):
    _need(type(value) is dict and set(value) == set(fields), code)


def _strict_json(value):
    if type(value) is dict:
        for child in value.values():
            _strict_json(child)
    elif type(value) is list:
        for child in value:
            _strict_json(child)
    else:
        _need(type(value) in (str, int, float, bool, type(None)), 'BLENDER_PREVIEW_JSON_TYPE')


def _wire(value, cap, code):
    # Common validation bounds depth/Unicode/finiteness before our recursion.
    raw = canonical_bytes(value)
    _strict_json(value)
    _need(len(raw) <= cap, code)
    return raw


def _number(value):
    _need(type(value) in (int, float) and math.isfinite(value), 'BLENDER_PREVIEW_NUMBER')


def _vector(value, size):
    _need(type(value) is list and len(value) == size, 'BLENDER_PREVIEW_VECTOR')
    for item in value:
        _number(item)


def _identifier(value):
    try:
        queue.c.identifier(value)
    except queue.c.Rejected as error:
        raise ValidationError('BLENDER_PREVIEW_IDENTIFIER', 'native stable ID required') from error


def _name(value):
    _need(type(value) is str and 0 < len(value.encode('utf-8')) <= MAX_NAME_BYTES,
          'BLENDER_PREVIEW_NAME_LIMIT')


def _material(value):
    _shape(value, _MATERIAL_FIELDS)
    _identifier(value['material_id']); _name(value['name'])
    _need(value['name'] == 'HH_Material_' + value['material_id'], 'BLENDER_PREVIEW_MATERIAL')
    _vector(value['base_color'], 4)
    _number(value['metallic']); _number(value['roughness'])
    _need(value['base_color'][3] == 1 and all(0 <= number <= 1 for number in value['base_color'])
          and 0 <= value['metallic'] <= 1 and 0 <= value['roughness'] <= 1
          and value['double_sided'] is True and value['alpha_mode'] == 'OPAQUE',
          'BLENDER_PREVIEW_MATERIAL')


def _object(value):
    _need(type(value) is dict and set(value) in (_OBJECT_FIELDS, _OBJECT_FIELDS | {'material'}),
          'BLENDER_PREVIEW_OBJECT_SHAPE')
    _identifier(value['object_id']); _name(value['name']); _name(value['mesh_name'])
    for field in ('location', 'rotation', 'scale'):
        _vector(value[field], 3)
    vertices, faces = value['vertices'], value['faces']
    _need(type(vertices) is list and len(vertices) == 8 and type(faces) is list and len(faces) == 6,
          'BLENDER_PREVIEW_MESH_LIMIT')
    for vertex in vertices:
        _vector(vertex, 3)
    for face in faces:
        _need(type(face) is list and 3 <= len(face) <= 8
              and all(type(index) is int and 0 <= index < 8 for index in face)
              and len(set(face)) == len(face), 'BLENDER_PREVIEW_FACE')
    if 'material' in value:
        _material(value['material'])


def observation(value):
    """Validate and detach an exact supported received observation, without bpy."""
    raw = _wire(value, MAX_OBSERVATION_BYTES, 'BLENDER_PREVIEW_OBSERVATION_LIMIT')
    _shape(value, {'snapshot', 'revision', 'context', 'public_ack', 'undo_supported'})
    _need(type(value['revision']) is str and _HASH.fullmatch(value['revision']), 'BLENDER_PREVIEW_REVISION')
    _need(value['public_ack'] is False and value['undo_supported'] is True, 'BLENDER_PREVIEW_OBSERVATION_FLAGS')
    snapshot = value['snapshot']
    _shape(snapshot, {'schema', 'objects', 'units'})
    _need(snapshot['schema'] == 'HH-BLENDER-FIXTURE-SCENE-1', 'BLENDER_PREVIEW_SCENE_SCHEMA')
    rows = snapshot['objects']
    _need(type(rows) is list and len(rows) <= MAX_OBJECTS, 'BLENDER_PREVIEW_OBJECT_LIMIT')
    for row in rows:
        _object(row)
    ids = [row['object_id'] for row in rows]
    _need(ids == sorted(set(ids)), 'BLENDER_PREVIEW_OBJECT_IDS')
    material_ids = [row['material']['material_id'] for row in rows if 'material' in row]
    _need(len(material_ids) <= MAX_MATERIALS and len(set(material_ids)) == len(material_ids),
          'BLENDER_PREVIEW_MATERIAL_IDS')
    units = snapshot['units']
    _shape(units, {'system', 'scale_length'})
    _need(units['system'] in ('NONE', 'METRIC', 'IMPERIAL'), 'BLENDER_PREVIEW_UNITS')
    _number(units['scale_length'])
    _need(units['scale_length'] > 0, 'BLENDER_PREVIEW_UNITS')
    context = value['context']
    _shape(context, {'mode', 'active_id', 'selected_ids'})
    selected = context['selected_ids']
    _need(context['mode'] in ('OBJECT', 'EDIT_MESH') and type(selected) is list
          and len(selected) <= MAX_OBJECTS and all(type(item) is str for item in selected),
          'BLENDER_PREVIEW_CONTEXT')
    _need(selected == sorted(set(selected)) and set(selected) <= set(ids)
          and (context['active_id'] is None or type(context['active_id']) is str and context['active_id'] in ids)
          and (context['mode'] != 'EDIT_MESH' or context['active_id'] in selected), 'BLENDER_PREVIEW_CONTEXT')
    return parse_json(raw)


def _sha(value):
    return 'sha256:' + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _compared(value):
    return {'snapshot': value['snapshot'], 'context': value['context']}


def actual_diff(before, after, *, operation):
    """Exact diff of two observed states, never a prediction of native results.

    Added/removed values are complete object rows. Changed values retain both
    complete rows and the exact changed field names, including material removal.
    Numeric equality is only the named received-JCS domain, with no epsilon.
    """
    _need(type(operation) is str and operation in catalog.EDIT_OPERATIONS, 'BLENDER_PREVIEW_OPERATION')
    before, after = observation(before), observation(after)
    left = {row['object_id']: row for row in before['snapshot']['objects']}
    right = {row['object_id']: row for row in after['snapshot']['objects']}
    added = [right[key] for key in sorted(right.keys() - left.keys())]
    removed = [left[key] for key in sorted(left.keys() - right.keys())]
    changed = []
    for key in sorted(left.keys() & right.keys()):
        old, new = left[key], right[key]
        fields = sorted(name for name in old.keys() | new.keys()
                        if name not in old or name not in new or canonical_bytes(old[name]) != canonical_bytes(new[name]))
        if fields:
            changed.append({'object_id': key, 'changed_fields': fields, 'before': old, 'after': new})
    def change(old, new):
        return None if canonical_bytes(old) == canonical_bytes(new) else {'before': old, 'after': new}
    context = change(before['context'], after['context'])
    units = change(before['snapshot']['units'], after['snapshot']['units'])
    result = {'operation': operation, 'comparison_domain': DIFF_DOMAIN, 'epsilon': 0,
        'before_hash': _sha(_compared(before)), 'after_hash': _sha(_compared(after)),
        'native_revisions': {'before': before['revision'], 'after': after['revision']},
        'changed': bool(added or removed or changed or context or units),
        'objects': {'added': added, 'removed': removed, 'changed': changed},
        'context': context, 'units': units, 'affected_files': [], 'scene_state_durable': False}
    return parse_json(_wire(result, MAX_DIFF_BYTES, 'BLENDER_PREVIEW_DIFF_LIMIT'))


def _requested_diff(command, before):
    operation, payload = command['operation'], command['payload']
    if operation in ('history.undo', 'history.redo'):
        return {'kind': 'owned-history-step', 'direction': operation.rsplit('.', 1)[1],
                'basis': 'guarded recorded history target; apply has not run'}
    objects = {row['object_id']: row for row in before['snapshot']['objects']}
    key = payload['object_id']; current = objects.get(key)
    if operation == 'mesh.create_box':
        _need(current is None and len(objects) < MAX_OBJECTS, 'BLENDER_PREVIEW_CREATE_PRECONDITION')
        return {'kind': 'create-box', 'object_id': key, 'before': None, 'requested': {'size': payload['size']}}
    _need(current is not None, 'BLENDER_PREVIEW_OBJECT_MISSING')
    if operation == 'object.transform.set':
        fields = ('location', 'rotation', 'scale')
        return {'kind': 'set-transform', 'object_id': key,
                'before': {name: current[name] for name in fields},
                'requested': {name: payload[name] for name in fields}}
    material = current.get('material')
    existing = {row['material']['material_id'] for row in objects.values() if 'material' in row}
    _need((material is not None and material['material_id'] == payload['material_id'])
          or (material is None and payload['material_id'] not in existing and len(existing) < MAX_MATERIALS),
          'BLENDER_PREVIEW_MATERIAL_PRECONDITION')
    return {'kind': 'set-principled-material', 'object_id': key, 'before': material,
            'requested': {name: payload[name] for name in payload if name != 'object_id'}}


def normalize_preview(request, native_command, native_response, *, source_sha256, generation):
    """Bind a no-effect native preview to the owner's exact private translation.

    source_sha256/generation are supplied by the registered owner; syntax here
    cannot authenticate that owner. The result grants no lease or apply permit.
    All native revision strings remain opaque, including recorded history.
    """
    _need(type(request) is Request, 'BLENDER_PREVIEW_REQUEST')
    _need(type(source_sha256) is str and _HASH.fullmatch(source_sha256)
          and type(generation) is str and _GENERATION.fullmatch(generation), 'BLENDER_PREVIEW_OWNER_BINDING')
    request = catalog.validate_request(request.as_dict(), project_id=request.project_id, source_sha256=source_sha256)
    _need(request.operation in catalog.EDIT_OPERATIONS, 'BLENDER_PREVIEW_OPERATION')
    _wire(native_command, queue.c.MAX_BYTES, 'BLENDER_PREVIEW_COMMAND_LIMIT')
    try:
        command = queue.parse(queue.c.canonical(native_command))
    except queue.c.Rejected as error:
        raise ValidationError('BLENDER_PREVIEW_COMMAND', 'exact private edit command required') from error
    _need(command['operation'] == request.operation and command['expected_revision'] == request.expected_revision
          and canonical_bytes(command['expected_context']) == canonical_bytes(request.payload['expected_context'])
          and canonical_bytes(command['payload']) == canonical_bytes(request.payload['arguments']),
          'BLENDER_PREVIEW_REQUEST_BINDING')
    _wire(native_response, MAX_PREVIEW_BYTES, 'BLENDER_PREVIEW_RESPONSE_LIMIT')
    _shape(native_response, {'schema', 'command_id', 'command_digest', 'operation', 'before', 'requested_changes',
        'history_target', 'affected_files', 'undo_policy', 'value_policy', 'no_effect', 'apply_id_reserved',
        'public_ack', 'scene_state_durable'})
    _need(native_response['schema'] == PREVIEW_SCHEMA and native_response['command_id'] == command['command_id']
          and native_response['command_digest'] == queue.c.digest(command)
          and native_response['operation'] == command['operation'], 'BLENDER_PREVIEW_NATIVE_BINDING')
    _need(native_response['no_effect'] is True and native_response['apply_id_reserved'] is False
          and native_response['public_ack'] is False and native_response['scene_state_durable'] is False
          and native_response['affected_files'] == [] and native_response['undo_policy'] == UNDO_POLICY
          and native_response['value_policy'] == VALUE_POLICY, 'BLENDER_PREVIEW_NO_EFFECT_REQUIRED')
    _need(canonical_bytes(native_response['requested_changes']) == canonical_bytes(command['payload']),
          'BLENDER_PREVIEW_REQUEST_BINDING')
    before = observation(native_response['before'])
    _need(before['revision'] == request.expected_revision
          and canonical_bytes(before['context']) == canonical_bytes(request.payload['expected_context']),
          'BLENDER_PREVIEW_BEFORE_BINDING')
    history = request.operation in ('history.undo', 'history.redo')
    _need((native_response['history_target'] is not None) == history, 'BLENDER_PREVIEW_HISTORY_TARGET')
    target = observation(native_response['history_target']) if history else None
    result = {'schema': CLIENT_PREVIEW_SCHEMA, 'command_id': request.command_id,
        'project_id': request.project_id, 'operation': request.operation,
        'request_digest': request.digest, 'request_sha256': _sha(request.as_dict()),
        'native_command_digest': queue.c.digest(command), 'source_sha256': source_sha256, 'generation': generation,
        'before': before, 'before_hash': _sha(_compared(before)), 'comparison_domain': DIFF_DOMAIN,
        'requested_changes': command['payload'], 'requested_diff': _requested_diff(command, before),
        'history_target': target, 'history_target_diff': actual_diff(before, target, operation=request.operation) if history else None,
        'affected_files': [], 'undo_policy': UNDO_POLICY, 'value_policy': VALUE_POLICY,
        'no_effect': True, 'apply_id_reserved': False, 'authority_granted': False,
        'public_ack': False, 'scene_state_durable': False}
    return parse_json(_wire(result, MAX_PREVIEW_BYTES, 'BLENDER_PREVIEW_RESULT_LIMIT'))


def normalize_publication_preview(request, native_command, value, *, source_sha256, generation, storage_id):
    """Bind live file preflight without inventing future file bytes or revisions."""
    _need(type(request) is Request, 'BLENDER_PREVIEW_REQUEST')
    request = catalog.validate_request(request.as_dict(), project_id=request.project_id, source_sha256=source_sha256)
    _need(request.operation in publication.PROFILES and type(source_sha256) is str and _HASH.fullmatch(source_sha256)
          and type(generation) is str and _GENERATION.fullmatch(generation)
          and type(storage_id) is str and _GENERATION.fullmatch(storage_id), 'BLENDER_PREVIEW_OWNER_BINDING')
    _wire(value, MAX_PREVIEW_BYTES, 'BLENDER_PREVIEW_RESPONSE_LIMIT')
    _shape(value, {'schema','command_id','request_sha256','profile','storage_id','native_command','native_preview',
                   'no_effect','apply_id_reserved','public_ack'})
    private = (publication.validate_request(native_command) if request.operation == 'export.publish'
               else publication.save_request(native_command, request.operation))
    _need(private['expected_revision'] == request.expected_revision
          and canonical_bytes(private['expected_context']) == canonical_bytes(request.payload['expected_context'])
          and request.payload['arguments'] == {}, 'BLENDER_PREVIEW_REQUEST_BINDING')
    expected = publication.preparation_command(private, {'publication_profile':request.operation})
    _need(value['schema']=='HH-BLENDER-PUBLICATION-PREVIEW-1' and value['command_id']==private['command_id']
          and value['request_sha256']==publication.sha(canonical_bytes(private))
          and value['profile']==request.operation and value['storage_id']==storage_id
          and value['native_command']==expected and value['no_effect'] is True
          and value['apply_id_reserved'] is False and value['public_ack'] is False, 'BLENDER_PREVIEW_NATIVE_BINDING')
    native=value['native_preview']
    _shape(native, {'schema','command_id','command_digest','operation','before','requested_changes','history_target',
                   'affected_files','undo_policy','value_policy','no_effect','apply_id_reserved','public_ack','scene_state_durable'})
    _need(native['schema']==PREVIEW_SCHEMA and native['command_id']==expected['command_id']
          and native['command_digest']==queue.c.digest(expected) and native['operation']==expected['operation']
          and native['requested_changes']==expected['payload'] and native['history_target'] is None
          and native['affected_files']==[expected['payload']['slot']+'.blend']
          and native['undo_policy']=='immutable-private-copy-no-file-undo'
          and native['value_policy']=='native-preflight-only; artifact-hashes-require-publication'
          and native['no_effect'] is True and native['apply_id_reserved'] is False
          and native['public_ack'] is False and native['scene_state_durable'] is False, 'BLENDER_PREVIEW_NO_EFFECT_REQUIRED')
    before=observation(native['before'])
    _need(before['revision']==request.expected_revision and before['context']==private['expected_context']
          and before['context']['mode']=='OBJECT' and before['snapshot']['objects'], 'BLENDER_PREVIEW_BEFORE_BINDING')
    result={'schema':CLIENT_PREVIEW_SCHEMA,'command_id':request.command_id,'project_id':request.project_id,
        'operation':request.operation,'request_digest':request.digest,'request_sha256':_sha(request.as_dict()),
        'native_command_digest':queue.c.digest(native_command),'preparation_digest':queue.c.digest(expected),
        'source_sha256':source_sha256,'generation':generation,'storage_id':storage_id,
        'before':before,'before_hash':_sha(_compared(before)),'comparison_domain':DIFF_DOMAIN,
        'requested_changes':{},'requested_diff':{'kind':'create-immutable-bundle','existing_bundle':None,
            'create_files':[*publication.NAMES,'manifest.json','active.json'],'artifact_hashes':None},
        'affected_files':[*publication.NAMES,'manifest.json','active.json'],
        'staging_slot':expected['payload']['slot']+'.blend','undo_policy':'immutable-bundle-no-file-undo',
        'value_policy':'native-preflight-only; artifact-hashes-require-publication',
        'no_effect':True,'apply_id_reserved':False,'authority_granted':False,'public_ack':False,'scene_state_durable':False}
    return parse_json(_wire(result, MAX_PREVIEW_BYTES, 'BLENDER_PREVIEW_RESULT_LIMIT'))

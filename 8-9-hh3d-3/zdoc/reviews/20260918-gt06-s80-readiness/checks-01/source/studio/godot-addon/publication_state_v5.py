"""V5 edit extensions in an unchanged V4 publication stream; replay grants no authority."""
from __future__ import annotations
from dataclasses import dataclass, field
import hashlib
import importlib.util
from pathlib import Path
import re
import sys
from studio.protocol.core import Response, Status, canonical_bytes, parse_json

_path = Path(__file__).with_name('publication_state_v4.py').resolve()
_raw = _path.read_bytes()
_key = '_hh_publication_v5_values_' + hashlib.sha256(str(_path).encode() + b'\0' + _raw).hexdigest()
if _key not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_key, _path)
    _module = importlib.util.module_from_spec(_spec); sys.modules[_key] = _module
    try: exec(compile(_raw, str(_path), 'exec'), _module.__dict__)
    except BaseException:
        del sys.modules[_key]
        raise
v4 = sys.modules[_key]
values, PublicationError = v4.values, v4.PublicationError
shape, same, integer, digest = v4.shape, v4.same, v4.integer, v4.digest
hash_value, identifier, editor_identity = v4.hash_value, v4.identifier, v4.editor_identity
activation_current, selection_identity = v4.activation_current, v4.selection_identity
SCHEMA = v4.SCHEMA  # Existing CONFIG/publication bytes are never relabeled.
EDIT_SCHEMA = 'hh-godot-publication-event-5'
MAX_EVENT_BYTES, MAX_EVENTS, MAX_COMMANDS, MAX_SNAPSHOT_BYTES = v4.MAX_EVENT_BYTES, v4.MAX_EVENTS, v4.MAX_COMMANDS, v4.MAX_SNAPSHOT_BYTES
MAX_SCENE_BYTES, MAX_OBSERVATION_BYTES = 1048576, 524288
MAX_BLOB_COUNT, MAX_BLOB_BYTES = 63, 8 * 1048576
EDIT_SNAPSHOT_RESERVE = 32768  # READY, terminal receipt/response and held Stop metadata.
EDIT_OPERATIONS = ('scene.node.create', 'scene.node.update', 'scene.node.remove', 'scene.undo', 'scene.redo')
_COMMON, _CMD = v4._COMMON, v4._CMD
_FIELDS = {
    'EDIT_INTENT': _CMD | {'operation','projection_sha256','projection_size_bytes','before_project_revision',
        'before_scene_revision','expected_files','parent_selection','previous_selector_version','previous_selector_sha256',
        'editor','editor_generation','root_instance_id','admission','scratch_name','lease_owner'},
    'EDIT_READY': _CMD | {'scene_blob','capture_blob','capture'},
    'EDIT_COMMITTED': _CMD | {'observation_blob','observation','response'},
    'EDIT_FAILED': _CMD | {'reason','response'}, 'EDIT_UNKNOWN': _CMD | {'reason','response'},
}
_BASE_OBSERVATION = {'schema','context_kind','kind','command_id','request_digest','editor_session_id','editor_pid',
    'editor_creation_time','project_root_identity','editor_engine_sha256','source_release_sha256','generation_before',
    'generation_after','root_before','root_after','effect_started_ms','effect_completed_ms','semantic_revision',
    'semantic_sha256','semantic_state','working_files','history_boundary','can_undo','can_redo','public_ack','observation_id'}
_EDIT_OBSERVATION = {'operation','projection_sha256','checkpoint_observation_id','checkpoint_scene_sha256',
    'before_revision','before_semantic_sha256','history_id_before','history_id_after','files_saved','live_state_durable'}
_CAPTURE_SUMMARY = {'observation_id','observation_sha256','semantic_revision','semantic_sha256','scene_sha256',
    'scene_size_bytes','effect_started_ms','effect_completed_ms','can_undo','can_redo'}
_EDIT_SUMMARY = {'observation_id','observation_sha256','semantic_revision','semantic_sha256','effect_started_ms',
    'effect_completed_ms','can_undo','can_redo','history_id_before','history_id_after'}


def need(value, code):
    v4.v3.need(value, 'PUBLICATION_V5_' + code)


def _metadata(files):
    return {name: {key: row[key] for key in ('sha256','size_bytes')} for name,row in files.items()}


def blob_descriptor(value, limit):
    shape(value, {'object_id','identity','sha256'})
    need(type(value['object_id']) is str and re.fullmatch(r'blob-[0-9a-f]{32}',value['object_id']), 'BLOB_NAME')
    shape(value['identity'], {'volume','file_id','size'})
    values._identity({key:value['identity'][key] for key in ('volume','file_id')})
    integer(value['identity']['size'], 1, limit); hash_value(value['sha256'])


def _add_blob(state, value, limit):
    blob_descriptor(value, limit)
    rows = state['edit_blobs']
    need(all(row['object_id'] != value['object_id'] and
             (row['identity']['volume'],row['identity']['file_id']) !=
             (value['identity']['volume'],value['identity']['file_id']) for row in rows), 'BLOB_REUSED')
    need(len(rows) < MAX_BLOB_COUNT and sum(row['identity']['size'] for row in rows) + value['identity']['size'] <= MAX_BLOB_BYTES,
         'BLOB_CAPACITY')
    rows.append(value)


def projection_binding(projection, command_id, operation, revision, generation):
    shape(projection, {'operation','command_id','expected_revision','expected_generation','target_stable_id','payload'})
    need(operation in EDIT_OPERATIONS and projection['operation'] == operation and projection['command_id'] == command_id
         and projection['expected_revision'] == revision, 'PROJECTION_BINDING')
    integer(projection['expected_generation'],1,2147483647)
    need(projection['expected_generation'] == generation and type(projection['payload']) is dict, 'PROJECTION_GENERATION')
    integer(projection['payload'].get('expected_generation'),1,2147483647)
    need(projection['payload']['expected_generation'] == generation, 'PROJECTION_GENERATION')
    identifier(projection['target_stable_id'])
    raw = canonical_bytes(projection); need(len(raw) <= 65536, 'PROJECTION_LIMIT')
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _observation_common(value, prepared, observed_ms, kind):
    need(type(value) is dict, 'OBSERVATION_TYPE')
    shape(value, _BASE_OBSERVATION | ({'scene_sha256','scene_size_bytes'} if kind == 'capture' else _EDIT_OBSERVATION))
    identity = prepared['editor']
    need(value['schema'] == 'hh-godot-live-editor-observation-1' and value['context_kind'] == 'live_editor'
         and value['kind'] == kind and value['command_id'] == prepared['command_id']
         and value['request_digest'] == prepared['digest'] and value['editor_session_id'] == identity['session_id']
         and type(value['editor_pid']) is int and value['editor_pid'] == identity['pid']
         and value['editor_creation_time'] == identity['creation_filetime']
         and same(value['project_root_identity'],identity['root_identity'])
         and value['editor_engine_sha256'] == identity['engine_sha256']
         and value['source_release_sha256'] == identity['installed_source_sha256'], 'OBSERVATION_IDENTITY')
    for key in ('generation_before','generation_after'): integer(value[key],1,2147483647)
    need(value['generation_before'] == value['generation_after'] == prepared['editor_generation'], 'OBSERVATION_GENERATION')
    for key in ('root_before','root_after'):
        need(type(value[key]) is str and re.fullmatch(r'[1-9][0-9]{0,15}',value[key])
             and int(value[key]) == prepared['root_instance_id'], 'OBSERVATION_ROOT')
    need(same(value['working_files'],_metadata(prepared['expected_files'])) and value['history_boundary'] is False
         and value['public_ack'] is False and type(value['can_undo']) is bool and type(value['can_redo']) is bool,
         'OBSERVATION_CONTEXT')
    for key in ('effect_started_ms','effect_completed_ms'): integer(value[key])
    admission = prepared['admission']
    need(prepared['observed_ms'] <= value['effect_started_ms'] < min(admission['deadline_ms'],admission['lease_expires_ms'])
         and value['effect_started_ms'] <= value['effect_completed_ms'] <= observed_ms, 'OBSERVATION_TIME')
    identifier(value['observation_id']); hash_value(value['semantic_sha256'])
    shape(value['semantic_state'], {'nodes'})
    nodes = value['semantic_state']['nodes']
    need(type(nodes) is list and 1 <= len(nodes) <= 64 and len(canonical_bytes(value['semantic_state'])) <= 262144
         and digest(value['semantic_state']) == value['semantic_sha256']
         and value['semantic_revision'] == 'sha256:' + value['semantic_sha256'], 'OBSERVATION_SEMANTICS')
    need(len(canonical_bytes(value)) <= MAX_OBSERVATION_BYTES, 'OBSERVATION_LIMIT')


def capture_summary(value, prepared, observed_ms):
    _observation_common(value,prepared,observed_ms,'capture')
    hash_value(value['scene_sha256']); integer(value['scene_size_bytes'],1,MAX_SCENE_BYTES)
    need(value['semantic_revision'] == prepared['before_scene_revision'], 'CAPTURE_REVISION')
    return {**{key:value[key] for key in _CAPTURE_SUMMARY if key != 'observation_sha256'},
            'observation_sha256':digest(value)}


def observation_summary(value, command, observed_ms):
    p, checkpoint = command['edit_prepared'],command['checkpoint']
    _observation_common(value,p,observed_ms,'edit')
    need(value['operation'] == p['operation'] and value['projection_sha256'] == p['projection_sha256']
         and value['checkpoint_observation_id'] == checkpoint['capture']['observation_id']
         and value['checkpoint_scene_sha256'] == checkpoint['capture']['scene_sha256']
         and value['before_revision'] == p['before_scene_revision']
         and value['before_semantic_sha256'] == p['before_scene_revision'][7:]
         and value['files_saved'] is False and value['live_state_durable'] is False
         and checkpoint['observed_ms'] <= value['effect_started_ms'], 'EDIT_BINDING')
    for key in ('history_id_before','history_id_after'): integer(value[key],1,2147483647)
    need(value['history_id_before'] == value['history_id_after'], 'EDIT_HISTORY')
    return {**{key:value[key] for key in _EDIT_SUMMARY if key != 'observation_sha256'},
            'observation_sha256':digest(value)}


def _summary(value, fields, state, command, *, edit=False):
    shape(value,fields); identifier(value['observation_id'])
    for key in ('observation_sha256','semantic_sha256'): hash_value(value[key])
    need(value['semantic_revision'] == 'sha256:' + value['semantic_sha256'], 'SUMMARY_REVISION')
    for key in ('effect_started_ms','effect_completed_ms'): integer(value[key])
    p = command['edit_prepared']; a = p['admission']
    minimum = command['checkpoint']['observed_ms'] if edit else p['observed_ms']
    need(minimum <= value['effect_started_ms'] < min(a['deadline_ms'],a['lease_expires_ms'])
         and value['effect_started_ms'] <= value['effect_completed_ms'] <= state['last_observed_ms']
         and type(value['can_undo']) is bool and type(value['can_redo']) is bool, 'SUMMARY_TIME_OR_HISTORY')
    if edit:
        for key in ('history_id_before','history_id_after'): integer(value[key],1,2147483647)
        need(value['history_id_before'] == value['history_id_after'], 'EDIT_HISTORY')
    else:
        hash_value(value['scene_sha256']); integer(value['scene_size_bytes'],1,MAX_SCENE_BYTES)
        need(value['semantic_revision'] == p['before_scene_revision'], 'CAPTURE_REVISION')


def terminal_plan(state,command,status='COMMITTED',reason='verified'):
    if 'edit_prepared' not in command: return v4.terminal_plan(state,command,status,reason)
    need(status in ('COMMITTED','FAILED','UNKNOWN'),'TERMINAL_STATUS'); identifier(reason)
    p = command['edit_prepared']; selected = state['selected']; observation = command.get('edit_observation')
    if status == 'COMMITTED': need(command['phase'] == 'EDIT_READY' and observation is not None, 'TERMINAL_PHASE')
    receipt = {'schema':'hh-godot-editor-terminal-5','command_id':command['command_id'],'digest':command['digest'],
        'operation':p['operation'],'status':status,'reason':reason,'effect_scope':'editor_session',
        'before_project_revision':p['before_project_revision'],'before_scene_revision':p['before_scene_revision'],
        'after_project_revision':selected['bundle_manifest']['project_revision'],
        'selection':selected['selector']['selection'],'selector_version':selected['selector_version'],
        'editor':p['editor'],'generation':p['editor_generation'],'root_instance_id':p['root_instance_id'],
        'checkpoint':command.get('checkpoint'),'observation':observation,'observation_blob':command.get('observation_blob'),
        'files_saved':False,'live_state_durable':False,'public_ack':False,'engine_effects_verified':False,'durable_owner_required':True}
    receipt_hash = digest(receipt)
    if status == 'COMMITTED':
        response = Response(Status.COMMITTED,'GODOT_EDITOR_EDITED',command['command_id'],postconditions={
            'request_digest':command['digest'],'durable_receipt_sha256':receipt_hash,'effect_scope':'editor_session',
            'files_saved':False,'live_state_durable':False,'journal_receipt_durable':True,'public_ack':True,
            'project_revision':p['before_project_revision'],'scene_revision':observation['semantic_revision'],
            'selection':p['parent_selection'],'editor_session_id':p['editor']['session_id'],'generation':p['editor_generation'],
            'history_boundary':False,'history_id':observation['history_id_after'],'can_undo':observation['can_undo'],
            'can_redo':observation['can_redo'],'checkpoint_scene_sha256':command['checkpoint']['scene_blob']['sha256'],
            'checkpoint_observation_id':command['checkpoint']['capture']['observation_id'],'managed_fixture_only':True}).as_dict()
    else:
        post = {'request_digest':command['digest'],'reason':reason,'public_ack':False,'effect_scope':'editor_session',
                'files_saved':False,'live_state_durable':False}
        if status == 'UNKNOWN': post['next_action'] = 'lookup.reconcile'
        response = Response(Status.UNKNOWN if status=='UNKNOWN' else Status.REJECTED,
            'GODOT_PUBLICATION_RECONCILE_REQUIRED' if status=='UNKNOWN' else 'GODOT_PUBLICATION_REJECTED',
            command['command_id'],postconditions=post).as_dict()
    need(len(canonical_bytes(response)) <= 8192, 'RESPONSE_LIMIT')
    return {'receipt':receipt,'receipt_sha256':receipt_hash,'response':response,'response_sha256':digest(response)}


def _finish(state,command,status,reason,response):
    result = terminal_plan(state,command,status,reason)
    need(same(response,result['response']), 'ORIGINAL_RESPONSE_MISMATCH')
    if status == 'UNKNOWN':
        command['uncertain_phase'] = command['phase']; state['held'] = True
    else: state['pending_command_id'] = None
    command.update(phase=status,reason=reason,**result)


def _step(state,event,raw):
    need(type(event) is dict, 'EVENT_TYPE')
    if event.get('schema') == SCHEMA:
        # V4 Stop must not interpret an edit as a scene publication.
        pending = None if state is None else next((c for c in state['commands'] if c['command_id']==state['pending_command_id']),None)
        if event.get('kind') == 'STOP' and pending and 'edit_prepared' in pending:
            shape(event,_COMMON | {'reason'}); integer(event['sequence'],1,MAX_EVENTS); integer(event['observed_ms'])
            need(event['sequence']==state['event_count']+1 and event['project_id']==state['project_id']
                 and event['observed_ms']>=state['last_observed_ms'] and not state['stopped'],'EVENT_ORDER')
            identifier(event['reason']); state.update(event_count=event['sequence'],last_observed_ms=event['observed_ms'],stopped=True)
            if pending['phase'] != 'UNKNOWN':
                status = 'FAILED' if pending['phase']=='EDIT_INTENT' else 'UNKNOWN'
                _finish(state,pending,status,event['reason'],terminal_plan(state,pending,status,event['reason'])['response'])
            return state
        need(not (pending and 'edit_prepared' in pending and event.get('command_id')==pending['command_id']),
             'EDIT_VERSION_REQUIRED')
        result = v4._step(state,event,raw)
        if state is None: result['edit_blobs'] = []
        return result
    kind = event.get('kind'); need(event.get('schema')==EDIT_SCHEMA and kind in _FIELDS, 'SCHEMA_OR_KIND')
    shape(event,_COMMON | _FIELDS[kind]); need(state is not None,'CONFIG_FIRST')
    integer(event['sequence'],1,MAX_EVENTS); integer(event['observed_ms'])
    need(event['sequence']==state['event_count']+1 and event['project_id']==state['project_id']
         and event['observed_ms']>=state['last_observed_ms'],'EVENT_ORDER')
    identifier(event['command_id']); hash_value(event['digest'],revision=True)
    command = next((c for c in state['commands'] if c['command_id']==event['command_id']),None)
    if command: need(command['digest']==event['digest'],'COMMAND_CONFLICT')
    need(not state['held'] and not state['stopped'],'HELD_OR_STOPPED')
    state.update(event_count=event['sequence'],last_observed_ms=event['observed_ms'])
    if kind == 'EDIT_INTENT':
        need(command is None and state['pending_command_id'] is None and len(state['commands'])<MAX_COMMANDS
             and event['sequence']+3 <= MAX_EVENTS, 'CAPACITY_OR_DUPLICATE')
        need(len(canonical_bytes(state))+len(raw)+EDIT_SNAPSHOT_RESERVE<=MAX_SNAPSHOT_BYTES,'SNAPSHOT_CAPACITY')
        blobs = state['edit_blobs']
        need(len(blobs)+3 <= MAX_BLOB_COUNT and sum(row['identity']['size'] for row in blobs)
             +MAX_SCENE_BYTES+2*MAX_OBSERVATION_BYTES <= MAX_BLOB_BYTES,'BLOB_CAPACITY')
        p = event; selected = state['selected']; manifest = selected['bundle_manifest']
        need(p['operation'] in EDIT_OPERATIONS,'OPERATION'); hash_value(p['projection_sha256'])
        integer(p['projection_size_bytes'],1,65536); hash_value(p['before_scene_revision'],revision=True)
        need(p['before_project_revision']==manifest['project_revision'] and same(p['expected_files'],manifest['files'])
             and same(p['parent_selection'],selected['selector']['selection'])
             and same(p['previous_selector_version'],selected['selector_version'])
             and p['previous_selector_sha256']==digest(selected['selector']), 'SELECTED_CONTEXT')
        editor_identity(p['editor'],state['editor_engine_sha256']); integer(p['editor_generation'],1,2147483647)
        integer(p['root_instance_id'],1); identifier(p['lease_owner'])
        a = p['admission']; shape(a,v4.v3._ADMISSION_FIELDS)
        for key in ('session_id','lease_id'): identifier(a[key])
        need(p['lease_owner']==a['session_id'],'LEASE_OWNER')
        hash_value(a['catalog_digest'],revision=True)
        for key in ('fencing_epoch','admitted_ms','deadline_ms','lease_expires_ms'): integer(a[key],1)
        need(a['fencing_epoch']>=state['highest_fencing_epoch'] and a['admitted_ms']<=p['observed_ms']
             <a['deadline_ms']<=min(a['lease_expires_ms'],a['admitted_ms']+v4.MAX_SAVE_ADMISSION_MS), 'ADMISSION')
        state['highest_fencing_epoch'] = a['fencing_epoch']
        need(type(p['scratch_name']) is str and re.fullmatch(r'capture-[0-9a-f]{32}\.tscn',p['scratch_name'])
             and p['scratch_name'] not in state['scratch_names'],'SCRATCH')
        state['scratch_names'].append(p['scratch_name'])
        state['commands'].append({'command_id':p['command_id'],'digest':p['digest'],'phase':'EDIT_INTENT','edit_prepared':p})
        state['pending_command_id'] = p['command_id']; return state
    need(command is not None and 'edit_prepared' in command and state['pending_command_id']==event['command_id'],'PENDING')
    if kind in ('EDIT_FAILED','EDIT_UNKNOWN'):
        status = kind.removeprefix('EDIT_')
        if status=='FAILED': need(command['phase']=='EDIT_INTENT','FAILURE_AFTER_EFFECT_PERMISSION')
        _finish(state,command,status,event['reason'],event['response']); return state
    if kind == 'EDIT_READY':
        need(command['phase']=='EDIT_INTENT','PHASE'); _summary(event['capture'],_CAPTURE_SUMMARY,state,command)
        v4._fresh(state,event['capture']['observation_id'])
        _add_blob(state,event['scene_blob'],MAX_SCENE_BYTES); _add_blob(state,event['capture_blob'],MAX_OBSERVATION_BYTES)
        need(event['scene_blob']['sha256']==event['capture']['scene_sha256']
             and event['scene_blob']['identity']['size']==event['capture']['scene_size_bytes']
             and event['capture_blob']['sha256']==event['capture']['observation_sha256'],'CHECKPOINT_BLOBS')
        command['checkpoint'] = {key:event[key] for key in ('scene_blob','capture_blob','capture','observed_ms')}
        command['phase'] = 'EDIT_READY'; return state
    need(command['phase']=='EDIT_READY','PHASE'); _summary(event['observation'],_EDIT_SUMMARY,state,command,edit=True)
    v4._fresh(state,event['observation']['observation_id']); _add_blob(state,event['observation_blob'],MAX_OBSERVATION_BYTES)
    need(event['observation_blob']['sha256']==event['observation']['observation_sha256'],'OBSERVATION_BLOB')
    command.update(edit_observation=event['observation'],observation_blob=event['observation_blob'])
    _finish(state,command,'COMMITTED','verified',event['response']); return state


@dataclass(frozen=True,slots=True)
class PublicationState:
    events: tuple[bytes,...]
    _snapshot: bytes = field(init=False,repr=False)
    def __post_init__(self):
        need(type(self.events) is tuple and 1<=len(self.events)<=MAX_EVENTS,'HISTORY')
        state = None
        for raw in self.events:
            need(type(raw) is bytes,'HISTORY'); raw = v4._event_bytes(raw)
            state = _step(state,parse_json(raw),raw)
        encoded = canonical_bytes(state); need(len(encoded)<=MAX_SNAPSHOT_BYTES,'SNAPSHOT_LIMIT')
        object.__setattr__(self,'_snapshot',encoded)
    @property
    def event_count(self): return len(self.events)
    def snapshot(self): return parse_json(self._snapshot)


def reduce_event(state,event):
    need(state is None or type(state) is PublicationState,'STATE_TYPE')
    return PublicationState((() if state is None else state.events)+(v4._event_bytes(event),))


def replay(events): return PublicationState(tuple(v4._event_bytes(event) for event in events))
def lookup(state,command_id,command_digest=None): return v4.lookup(state,command_id,command_digest)
def lookup_response(state,command_id,command_digest): return v4.lookup_response(state,command_id,command_digest)

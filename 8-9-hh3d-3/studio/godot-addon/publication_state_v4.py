"""Typed complete-bundle publication v4; pure replay is never engine authority.

Both save and script replacement share one capture/native-selection history.
The unchanged v3 value checks are reused; v3 events are never rewritten as v4.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import hashlib
import importlib.util
from pathlib import Path
import re
import sys
from studio.protocol.core import Response, Status, canonical_bytes, parse_json

_path = Path(__file__).with_name('publication_state_v3.py').resolve()
_raw = _path.read_bytes()
_key = '_hh_publication_v4_values_' + hashlib.sha256(str(_path).encode()+b'\0'+_raw).hexdigest()
if _key not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_key, _path)
    _module = importlib.util.module_from_spec(_spec); sys.modules[_key] = _module
    try: exec(compile(_raw,str(_path),'exec'),_module.__dict__)
    except BaseException:
        del sys.modules[_key]
        raise
v3 = sys.modules[_key]
values = v3.values
PublicationError = v3.PublicationError
shape, same, integer, digest = v3.shape, v3.same, v3.integer, v3.digest
hash_value, identifier, selector_version = v3.hash_value, v3.identifier, v3.selector_version
editor_identity, manifest, descriptor = v3.editor_identity, v3.manifest, v3.descriptor
selector, selection_identity, activation_current = v3.selector, v3.selection_identity, v3.activation_current
_deadline, _fresh = v3._deadline, v3._fresh
PATHS, SCENE_PATH, SCRIPT_PATH = v3.PATHS, v3.SCENE_PATH, values.SCRIPT_PATH
SCHEMA = 'hh-godot-publication-event-4'
MAX_EVENT_BYTES, MAX_EVENTS, MAX_COMMANDS, MAX_SNAPSHOT_BYTES = 12288, 256, 64, 524288
MAX_SAVE_ADMISSION_MS = 90000
_COMMON, _CMD = v3._COMMON, v3._CMD
_FIELDS = {**v3._FIELDS,
    'CAPTURE_PREPARED': v3._FIELDS['CAPTURE_PREPARED'] | {'script_change'},
    'RETIRE_PREPARED': _CMD | {'current','retirement_intent_id','deadline_ms'},
    'RETIRED': _CMD | {'retirement'},
    'COMMITTED': _CMD | {'readback_event_sha256','response'},
    'FAILED': _CMD | {'reason','response'}, 'UNKNOWN': _CMD | {'reason','response'}}
_NEXT = {**v3._NEXT,'RETIRE_PREPARED':'VALIDATED','RETIRED':'RETIRE_PREPARED'}
_EARLY = v3._EARLY
RETIREMENT_FIELDS = {'observation_id','observation_sha256','command_id','request_digest','retirement_intent_id',
    'editor','before_generation','before_root_instance_id','before_revision','before_snapshot_sha256',
    'effect_started_ms','effect_completed_ms','close_completed_ms','next_generation','actual_exit_code',
    'wrapper_exit_code','job_active_count','job_zero_observed','job_closed','job_tainted','handles_retained','public_ack'}
FRESH_ADOPTION_FIELDS = {'mode','observation_id','command_id','request_digest','old_editor','new_editor',
    'generation_before','generation_after','root_before','root_after','retirement_observation_id',
    'retirement_sha256','semantic_revision','semantic_sha256','project_revision','manifest_sha256',
    'selection','selector_version','files','effect_started_ms','observed_ms','history_boundary','public_ack'}


def need(value,code): v3.need(value,'PUBLICATION_V4_'+code)


def _script_change(value,prepared):
    if prepared['operation']=='scene.save':
        need(value is None,'UNEXPECTED_SCRIPT_CHANGE'); return
    shape(value,{'path','expected_sha256','sha256','size_bytes'})
    need(value['path']==SCRIPT_PATH,'SCRIPT_PATH')
    hash_value(value['expected_sha256']);hash_value(value['sha256']);integer(value['size_bytes'],1,16384)
    need(value['expected_sha256']==prepared['expected_files'][SCRIPT_PATH]['sha256'],'STALE_SCRIPT')


def candidate_binding(prepared,captured,candidate,state):
    manifest(candidate,state)
    before,old,new=prepared['expected_files'],captured['files'],candidate['files']
    need(same(new[SCENE_PATH],old[SCENE_PATH]),'CAPTURED_SCENE_BYTES')
    if prepared['operation']=='scene.save':
        need(same(new,old) and candidate['caller_observations']['scene_revision']==captured['semantic_revision'],
             'SAVE_BINDING')
    else:
        change=prepared['script_change']
        need(all(new[SCRIPT_PATH][key]==change[key] for key in ('sha256','size_bytes')),'SCRIPT_BYTES')
        need(all(same(new[name],old[name]) for name in PATHS if name not in (SCENE_PATH,SCRIPT_PATH)),
             'SCRIPT_IMMUTABLE_INPUT')


def _retirement(value,state,command):
    shape(value,RETIREMENT_FIELDS)
    p,r=command['capture_prepared'],command['retire_prepared']
    _fresh(state,value['observation_id'])
    for key in ('observation_sha256','before_snapshot_sha256'):hash_value(value[key])
    for key in ('actual_exit_code','wrapper_exit_code','job_active_count'):integer(value[key],0,0)
    need(value['job_zero_observed'] is True and value['job_closed'] is True and value['job_tainted'] is False
         and value['handles_retained'] is False and value['public_ack'] is False,'RETIREMENT_NOT_CLEAN')
    for key in ('before_generation','before_root_instance_id','next_generation'):
        integer(value[key],1,2147483647 if 'generation' in key else 2**53-1)
    for key in ('effect_started_ms','effect_completed_ms','close_completed_ms'):integer(value[key])
    need(value['command_id']==command['command_id'] and value['request_digest']==command['digest']
         and value['retirement_intent_id']==r['retirement_intent_id'] and same(value['editor'],p['editor'])
         and value['before_generation']==p['editor_generation'] and value['before_root_instance_id']==p['root_instance_id']
         and value['before_revision']==p['before_scene_revision'] and value['next_generation']==p['editor_generation']+1,
         'RETIREMENT_BINDING')
    need(r['observed_ms']<=value['effect_started_ms']<r['deadline_ms']
         and value['effect_started_ms']<=value['effect_completed_ms']<=value['close_completed_ms']
         <=state['last_observed_ms'],'RETIREMENT_TIME')
    _deadline(command,value['effect_started_ms'])


def _fresh_adoption(value,state,command):
    shape(value,FRESH_ADOPTION_FIELDS)
    p,r,m=command['capture_prepared'],command['retirement'],command['bundle_manifest']
    _fresh(state,value['observation_id'])
    for identity in (value['old_editor'],value['new_editor']):editor_identity(identity,state['editor_engine_sha256'])
    old,new=value['old_editor'],value['new_editor']
    need(same(old,p['editor']) and new['session_id']!=old['session_id']
         and (new['pid'],new['creation_filetime'])!=(old['pid'],old['creation_filetime'])
         and not same(new['root_identity'],old['root_identity'])
         and new['installed_source_sha256']==old['installed_source_sha256'],'NEW_EDITOR_IDENTITY')
    for key in ('generation_before','generation_after','root_before','root_after'):
        integer(value[key],1,2147483647 if 'generation' in key else 2**53-1)
    for key in ('effect_started_ms','observed_ms'):integer(value[key])
    need(value['mode']=='fresh_editor' and value['command_id']==command['command_id']
         and value['request_digest']==command['digest'] and value['generation_before']==p['editor_generation']
         and value['generation_after']==r['next_generation'] and value['root_before']==p['root_instance_id']
         and value['retirement_observation_id']==r['observation_id']
         and value['retirement_sha256']==r['observation_sha256']
         and r['close_completed_ms']<=command['selected_observed_ms']<=value['effect_started_ms']
         <=value['observed_ms']<=state['last_observed_ms']
         and value['history_boundary'] is True and value['public_ack'] is False,'FRESH_EDITOR_BINDING')
    _deadline(command,value['effect_started_ms'])
    hash_value(value['semantic_sha256']);values._files(value['files'])
    selector_version(value['selector_version'],state['content_root_identity'])
    need(value['semantic_revision']=='sha256:'+value['semantic_sha256']==m['caller_observations']['scene_revision']
         and value['project_revision']==m['project_revision'] and value['manifest_sha256']==digest(m)
         and same(value['files'],m['files']) and same(value['selection'],command['selector']['selection'])
         and same(value['selector_version'],command['selector_version']),'FRESH_EDITOR_SELECTED_BYTES')


def terminal_plan(state,command,status='COMMITTED',reason='verified'):
    p=command['capture_prepared']; selected=state['selected'];m=selected['bundle_manifest']
    need(status in ('COMMITTED','FAILED','UNKNOWN'),'TERMINAL_STATUS');identifier(reason)
    if status=='COMMITTED':need(command['phase']=='READBACK','TERMINAL_PHASE')
    receipt={'schema':'hh-godot-publication-terminal-4','command_id':command['command_id'],
        'digest':command['digest'],'operation':p['operation'],'status':status,'reason':reason,
        'before_project_revision':p['before_project_revision'],'before_scene_revision':p['before_scene_revision'],
        'after_project_revision':m['project_revision'],'selection':selected['selector']['selection'],
        'selector_version':selected['selector_version'],'readback_event_sha256':command.get('readback_event_sha256'),
        'public_ack':False,'engine_effects_verified':False,'durable_owner_required':True}
    if status=='COMMITTED':
        receipt.update(scene_revision=m['caller_observations']['scene_revision'],adoption_sha256=digest(command['adoption']))
    receipt_hash=digest(receipt)
    if status=='COMMITTED':
        code={'scene.save':'GODOT_MANAGED_SCENE_SAVED','script_text.replace':'GODOT_MANAGED_SCRIPT_REPLACED'}[p['operation']]
        response=Response(Status.COMMITTED,code,command['command_id'],postconditions={
            'request_digest':command['digest'],'project_revision':m['project_revision'],
            'scene_revision':m['caller_observations']['scene_revision'],'selection':selected['selector']['selection'],
            'generation':command['adoption']['generation_after'],'history_boundary':True,'managed_fixture_only':True,
            'public_ack':True,'durable_receipt_sha256':receipt_hash}).as_dict()
    else:
        post={'request_digest':command['digest'],'reason':reason,'public_ack':False}
        if status=='UNKNOWN':post['next_action']='lookup.reconcile'
        response=Response(Status.UNKNOWN if status=='UNKNOWN' else Status.REJECTED,
            'GODOT_PUBLICATION_RECONCILE_REQUIRED' if status=='UNKNOWN' else 'GODOT_PUBLICATION_REJECTED',
            command['command_id'],postconditions=post).as_dict()
    need(len(canonical_bytes(response))<=8192,'RESPONSE_LIMIT')
    return {'receipt':receipt,'receipt_sha256':receipt_hash,'response':response,'response_sha256':digest(response)}


def _finish(state,command,status,reason,response):
    result=terminal_plan(state,command,status,reason)
    need(same(response,result['response']),'ORIGINAL_RESPONSE_MISMATCH')
    if status=='UNKNOWN':
        command['uncertain_phase']=command['phase'];command.update(phase='UNKNOWN',reason=reason,**result)
        state['held']=True
    else:
        if status=='COMMITTED':state['last_good']=state['selected']
        command.clear();command.update(command_id=result['receipt']['command_id'],digest=result['receipt']['digest'],
            phase=status,**result)
        state['pending_command_id']=None


def _initial(event):
    # CONFIG has the exact v3 field contract. Reuse its value validation, not
    # its replay: the original v4 bytes remain in this reducer's event history.
    configured=v3._step(None,{**event,'schema':v3.SCHEMA},canonical_bytes(event))
    configured['retirement_intent_ids']=[]
    return configured


def _step(state,event,raw):
    need(type(event) is dict and type(event.get('kind')) is str and event['kind'] in _FIELDS,'KIND')
    kind=event['kind'];shape(event,_COMMON|_FIELDS[kind]);need(event['schema']==SCHEMA,'SCHEMA')
    integer(event['sequence'],1,MAX_EVENTS);integer(event['observed_ms'])
    values._matches(event['project_id'],values._PROJECT)
    if state is None:
        need(kind=='CONFIG' and event['sequence']==1,'CONFIG_FIRST');return _initial(event)
    need(kind!='CONFIG' and event['sequence']==state['event_count']+1
         and event['project_id']==state['project_id'] and event['observed_ms']>=state['last_observed_ms'],'EVENT_ORDER')
    state['event_count'],state['last_observed_ms']=event['sequence'],event['observed_ms']
    if kind=='STOP':
        identifier(event['reason']);need(not state['stopped'],'DUPLICATE_STOP');state['stopped']=True
        command=next((c for c in state['commands'] if c['command_id']==state['pending_command_id']),None)
        if command and command['phase']!='UNKNOWN':
            status='FAILED' if command['phase'] in _EARLY else 'UNKNOWN'
            response=terminal_plan(state,command,status,event['reason'])['response']
            _finish(state,command,status,event['reason'],response)
        return state
    identifier(event['command_id']);hash_value(event['digest'],revision=True)
    command=next((c for c in state['commands'] if c['command_id']==event['command_id']),None)
    if command:need(command['digest']==event['digest'],'COMMAND_CONFLICT')
    need(not state['held'] and not state['stopped'],'HELD_OR_STOPPED')
    if kind=='CAPTURE_PREPARED':
        need(command is None,'DUPLICATE_COMMAND')
        need(state['pending_command_id'] is None and len(state['commands'])<MAX_COMMANDS
             and event['sequence']+15<=MAX_EVENTS,'CAPACITY')
        need(event['operation'] in ('scene.save','script_text.replace'),'OPERATION')
        values._matches(event['candidate_id'],re.compile(r'candidate-[0-9a-f]{32}\Z'))
        need(event['candidate_id'] not in state['candidate_ids'],'CANDIDATE_REUSED');state['candidate_ids'].append(event['candidate_id'])
        m=state['selected']['bundle_manifest']
        need(event['before_project_revision']==m['project_revision'] and same(event['expected_files'],m['files'])
             and same(event['parent_selection'],state['selected']['selector']['selection'])
             and same(event['checkpoint_descriptor'],state['selected']['selector']['descriptor'])
             and same(event['previous_selector_version'],state['selected']['selector_version'])
             and event['previous_selector_sha256']==digest(state['selected']['selector']),'CHECKPOINT')
        hash_value(event['before_scene_revision'],revision=True);editor_identity(event['editor'],state['editor_engine_sha256'])
        integer(event['editor_generation'],1,2147483647);integer(event['root_instance_id'],1)
        _script_change(event['script_change'],event)
        a=event['admission'];shape(a,v3._ADMISSION_FIELDS)
        for key in ('session_id','lease_id'):identifier(a[key])
        hash_value(a['catalog_digest'],revision=True)
        for key in ('fencing_epoch','admitted_ms','deadline_ms','lease_expires_ms'):integer(a[key],1)
        need(a['fencing_epoch']>=state['highest_fencing_epoch'] and a['admitted_ms']<=event['observed_ms']
             <a['deadline_ms']<=min(a['lease_expires_ms'],a['admitted_ms']+MAX_SAVE_ADMISSION_MS),'ADMISSION')
        state['highest_fencing_epoch']=a['fencing_epoch']
        need(type(event['scratch_name']) is str and re.fullmatch(r'capture-[0-9a-f]{32}\.tscn',event['scratch_name'])
             and event['scratch_name'] not in state['scratch_names'],'SCRATCH')
        state['scratch_names'].append(event['scratch_name'])
        command={'command_id':event['command_id'],'digest':event['digest'],'phase':kind,'capture_prepared':event}
        state['commands'].append(command);state['pending_command_id']=event['command_id'];return state
    need(command is not None and state['pending_command_id']==event['command_id'],'PENDING')
    if kind in ('FAILED','UNKNOWN'):
        if kind=='FAILED':need(command['phase'] in _EARLY,'FAILURE_AFTER_EFFECT')
        _finish(state,command,kind,event['reason'],event['response']);return state
    expected=('RETIRED' if command['capture_prepared']['operation']=='script_text.replace' else 'VALIDATED') if kind=='ACTIVATING' else _NEXT[kind]
    need(command['phase']==expected,'PHASE');p=command['capture_prepared']
    if kind=='CAPTURED':
        v3._capture(event['capture'],state,command);command['capture']=event['capture']
        command['capture_event_sha256']=hashlib.sha256(raw).hexdigest()
    elif kind=='PREPARED':
        shape(event['planned_names'],(*PATHS,'@manifest'));names=list(event['planned_names'].values())
        need(all(type(n) is str and re.fullmatch(r'obj-[0-9a-f]{32}',n) for n in names)
             and len(set(names))==12 and not set(names).intersection(state['planned_names']),'NAMES')
        state['planned_names'].extend(names);candidate_binding(p,command['capture'],event['bundle_manifest'],state)
        command['planned_names'],command['bundle_manifest']=event['planned_names'],event['bundle_manifest']
        _deadline(command,event['observed_ms'])
    elif kind=='STAGED':
        descriptor(event['descriptor'],command['bundle_manifest'],state,command['planned_names'])
        ids=[r['file_id'] for r in (*event['descriptor']['files'].values(),event['descriptor']['manifest'])]
        need(not set(ids).intersection(state['content_file_ids'])
             and state['selected']['selector_version']['file_id'] not in ids,'NATIVE_ALIAS')
        state['content_file_ids'].extend(ids);command['descriptor']=event['descriptor']
    elif kind=='VALIDATED':
        v3._validation(event['validation'],state,command);command['validation']=event['validation']
    elif kind=='RETIRE_PREPARED':
        need(p['operation']=='script_text.replace' and p['editor_generation']<2147483647,'RETIRE_OPERATION_OR_GENERATION')
        need(same(event['current'],activation_current(p)),'RETIRE_CONTEXT')
        identifier(event['retirement_intent_id']);integer(event['deadline_ms'])
        need(event['retirement_intent_id'] not in state['retirement_intent_ids'],'RETIRE_INTENT_REUSED')
        state['retirement_intent_ids'].append(event['retirement_intent_id'])
        need(event['observed_ms']<event['deadline_ms']<=min(p['admission']['deadline_ms'],
             p['admission']['lease_expires_ms'],event['observed_ms']+10000),'RETIRE_DEADLINE')
        command['retire_prepared']=event
    elif kind=='RETIRED':
        _retirement(event['retirement'],state,command);command['retirement']=event['retirement']
    elif kind=='ACTIVATING':
        need(same(event['current'],activation_current(p)),'EFFECT_GUARD')
        need(same(event['expected_selector_version'],state['selected']['selector_version']),'OLD_SELECTOR')
        selected={'generation':p['parent_selection']['generation']+1,'identity':selection_identity(state['project_id'],
            command['command_id'],command['digest'],p['parent_selection'],command['descriptor'],command['bundle_manifest'])}
        selector(event['selector'],command['descriptor'],selected,p['parent_selection'],command['command_id'])
        _deadline(command,event['observed_ms']);command['selector']=event['selector']
        command['activation_event_sha256']=hashlib.sha256(raw).hexdigest()
    elif kind=='SELECTED':
        selector_version(event['selector_version'],state['content_root_identity'])
        need(event['activation_event_sha256']==command['activation_event_sha256']
             and event['selector_sha256']==event['selector_version']['sha256']==digest(command['selector'])
             and event['selector_version']['size_bytes']==len(canonical_bytes(command['selector']))
             and event['selector_version']['file_id']!=state['selected']['selector_version']['file_id'],'SELECTED_VERSION')
        need(event['selector_version']['file_id'] not in state['content_file_ids'],'NATIVE_ALIAS')
        command['selector_version']=event['selector_version'];command['selected_observed_ms']=event['observed_ms']
        state['selected']={'bundle_manifest':command['bundle_manifest'],'selector':command['selector'],
                           'selector_version':event['selector_version']}
    elif kind=='READBACK':
        a=event['adoption'];need(type(a) is dict and 'mode' in a,'ADOPTION_MODE')
        if p['operation']=='scene.save':
            need(a['mode']=='same_editor','ADOPTION_MODE');v3._adoption({k:v for k,v in a.items() if k!='mode'},state,command)
        else:_fresh_adoption(a,state,command)
        command['adoption']=a;command['readback_event_sha256']=hashlib.sha256(raw).hexdigest()
    else:
        need(event['readback_event_sha256']==command['readback_event_sha256'],'READBACK_HASH')
        _finish(state,command,'COMMITTED','verified',event['response']);return state
    command['phase']=kind
    return state


def _event_bytes(event):
    raw=v3._event_bytes(event)
    need(len(raw)<=MAX_EVENT_BYTES,'EVENT_BYTES')
    return raw


@dataclass(frozen=True,slots=True)
class PublicationState:
    events:tuple[bytes,...]
    _snapshot:bytes=field(init=False,repr=False)
    def __post_init__(self):
        need(type(self.events) is tuple and 1<=len(self.events)<=MAX_EVENTS,'HISTORY')
        state=None
        for raw in self.events:
            need(type(raw) is bytes,'HISTORY');state=_step(state,parse_json(_event_bytes(raw)),raw)
        encoded=canonical_bytes(state);need(len(encoded)<=MAX_SNAPSHOT_BYTES,'SNAPSHOT_LIMIT')
        object.__setattr__(self,'_snapshot',encoded)
    @property
    def event_count(self):return len(self.events)
    def snapshot(self):return parse_json(self._snapshot)


def reduce_event(state,event):
    need(state is None or type(state) is PublicationState,'STATE_TYPE')
    return PublicationState((() if state is None else state.events)+(_event_bytes(event),))


def replay(events):return PublicationState(tuple(_event_bytes(event) for event in events))


def lookup(state,command_id,command_digest=None):return v3.lookup(state,command_id,command_digest)


def lookup_response(state,command_id,command_digest):
    command=lookup(state,command_id,command_digest)
    need(command is not None and command['phase'] in ('COMMITTED','FAILED','UNKNOWN')
         and 'response' in command,'RESPONSE_NOT_DURABLE')
    need(digest(command['response'])==command['response_sha256'],'RESPONSE_CHANGED')
    return canonical_bytes(command['response'])

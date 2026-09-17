"""Closed one-publication history. Pure validation; no engine or disk effects."""
import hashlib
import re
from studio.protocol.core import canonical_bytes,parse_json
from studio.host.core.custody import identity_from
from studio.host.core.private_store import StagedBlob,MAX_BLOB_BYTES
from .durable_session import queue

SCHEMA='HH-BLENDER-PUBLICATION-1'
PROJECT='blender.owned-publication'
NAMES=('checkpoint.blend','scene.glb')
PROFILES=frozenset({'export.publish','scene.save','checkpoint.save'})
_SLOTS={'export.publish':'export','scene.save':'fixture','checkpoint.save':'checkpoint'}

class PublicationError(ValueError):
    def __init__(self,code,*,outcome_unknown=False,cleanup_owner=None):
        self.code=code;self.outcome_unknown=outcome_unknown;self.cleanup_owner=cleanup_owner
        super().__init__(code)

def need(value,code='PUBLICATION_HISTORY_INVALID'):
    if not value:raise PublicationError(code)
def exact(value,keys):need(type(value) is dict and set(value)==set(keys))
def sha(raw):return hashlib.sha256(raw).hexdigest()
def hash_value(value):need(type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None)
def profile(config):
    value=config.get('publication_profile','export.publish')
    need(type(value) is str and value in PROFILES,'PUBLICATION_PROFILE_REQUIRED')
    return value

def preparation(config):
    value=profile(config)
    return ('export.prepare' if value=='export.publish' else 'checkpoint.save',_SLOTS[value])

def save_request(command,operation):
    """Exact public-ledger native save projected into the one-bundle reducer.

    The immutable CONFIG supplies the closed operation/slot. No path, new
    authority, or caller-selected preparation code enters publication history.
    """
    need(type(operation) is str and operation in PROFILES-{'export.publish'},'PUBLICATION_SAVE_PROFILE')
    command=queue.parse(queue.c.canonical(command))
    need(command['operation']=='checkpoint.save' and command['payload']=={'slot':_SLOTS[operation]},
         'PUBLICATION_SAVE_TRANSLATION')
    return validate_request({'schema':SCHEMA,'command_id':command['command_id'],
        'expected_revision':command['expected_revision'],'expected_context':command['expected_context']})
def snapshot_wire(snapshot,revision):
    # The engine contract distinguishes integral floats from integers. JCS
    # receipts do not, so preserve its canonical bytes as text across storage.
    raw=queue.c.canonical(snapshot)
    need(queue.c.digest(snapshot)==revision,'PUBLICATION_NATIVE_REVISION')
    return raw.decode('ascii')

def check_snapshot_wire(text,snapshot,revision):
    need(type(text) is str and 0<len(text)<=MAX_BLOB_BYTES,'PUBLICATION_NATIVE_SNAPSHOT_WIRE')
    native=parse_json(text.encode('ascii'))
    need(snapshot_wire(native,revision)==text and canonical_bytes(native)==canonical_bytes(snapshot),
        'PUBLICATION_NATIVE_SNAPSHOT_WIRE')
    return native

def validate_request(value):
    exact(value,('schema','command_id','expected_revision','expected_context'))
    need(value['schema']==SCHEMA,'PUBLICATION_SCHEMA')
    queue.parse(queue.c.canonical({'schema':queue.SCHEMA,'command_id':value['command_id'],
        'operation':'export.prepare','expected_revision':value['expected_revision'],
        'expected_context':value['expected_context'],'payload':{'slot':'export'}}))
    need(value['expected_context']['mode']=='OBJECT','PUBLICATION_OBJECT_MODE_REQUIRED')
    return parse_json(canonical_bytes(value))

def blob(value):
    exact(value,('object_id','identity','sha256','file_version'));hash_value(value['sha256'])
    need(type(value['object_id']) is str and re.fullmatch('blob-[0-9a-f]{32}',value['object_id']) is not None)
    identity=identity_from(value['identity']);need(0<identity.size<=MAX_BLOB_BYTES)
    exact(value['file_version'],('identity','sha256'))
    durable=identity_from(value['file_version']['identity'])
    need(durable.size==identity.size and value['file_version']['sha256']==value['sha256'])
    return StagedBlob(value['object_id'],identity,value['sha256'])

def selection(staged):
    return {'schema':SCHEMA,'generation':1,'command_id':staged['command_id'],
        'request_sha256':staged['request_sha256'],'manifest':staged['manifest']}

def response(intent,staged=None,selector=None,*,reason=None):
    value={'schema':SCHEMA,'command_id':intent['request']['command_id'],
        'request_sha256':intent['request_sha256'],'status':'REJECTED' if reason else 'COMMITTED',
        'public_ack':False,'reason':reason,'live_scene_recovered':False,'selection':None,'artifacts':None}
    if reason is None:
        value.update(selection={'generation':1,'manifest_sha256':staged['manifest']['sha256'],
            'selector_sha256':sha(canonical_bytes(selector))},artifacts={name:{'sha256':d['sha256'],
            'size_bytes':d['identity']['size']} for name,d in staged['artifacts'].items()})
    return value

def reduce(state,event):
    state=parse_json(canonical_bytes(state));event=parse_json(canonical_bytes(event))
    need(event.get('schema')==SCHEMA)
    kind=event.get('kind');phase=state.get('phase')
    if kind=='CONFIG':
        fields={'schema','kind','generation','source_sha256','binary_sha256'}
        need(set(event) in (fields,fields|{'publication_profile'}))
        profile(event)
        need(not state and re.fullmatch('[0-9a-f]{32}',event['generation']) is not None)
        hash_value(event['source_sha256']);hash_value(event['binary_sha256'])
        return {'phase':'EMPTY','config':event,'stopped':False}
    need(phase is not None)
    if kind=='STOP':
        exact(event,('schema','kind'));need(not state['stopped']);state['stopped']=True;return state
    need(not state['stopped'])
    if kind=='INTENT':
        exact(event,('schema','kind','request','request_sha256','lease_epoch'))
        need(phase=='EMPTY');validate_request(event['request'])
        need(event['request_sha256']==sha(canonical_bytes(event['request']))
            and type(event['lease_epoch']) is int and event['lease_epoch']>0)
        state.update(phase='INTENT',intent=event)
    elif kind=='STAGED':
        exact(event,('schema','kind','command_id','request_sha256','manifest','artifacts'))
        need(phase=='INTENT' and event['command_id']==state['intent']['request']['command_id']
            and event['request_sha256']==state['intent']['request_sha256'])
        exact(event['artifacts'],NAMES);blob(event['manifest'])
        for value in event['artifacts'].values():blob(value)
        ids=[event['manifest']['object_id'],*(value['object_id'] for value in event['artifacts'].values())]
        need(len(set(ids))==3);state.update(phase='STAGED',staged=event)
    elif kind=='SELECTING':
        exact(event,('schema','kind','selector'));need(phase=='STAGED' and event['selector']==selection(state['staged']))
        state.update(phase='SELECTING',selector=event['selector'])
    elif kind=='TERMINAL':
        exact(event,('schema','kind','response','response_sha256','selector_version'))
        result=event['response'];reason=result.get('reason')
        if phase=='INTENT':
            need(reason=='NATIVE_PREPARE_REJECTED' and event['selector_version'] is None)
            expected=response(state['intent'],reason=reason)
        else:
            need(phase=='SELECTING' and reason is None)
            expected=response(state['intent'],state['staged'],state['selector'])
            exact(event['selector_version'],('identity','sha256'));identity_from(event['selector_version']['identity'])
            need(event['selector_version']['sha256']==sha(canonical_bytes(state['selector'])))
        need(result==expected and event['response_sha256']==sha(canonical_bytes(expected)))
        state.update(phase='TERMINAL',terminal=event)
    else:need(False)
    return state

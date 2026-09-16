"""Deterministic shared-envelope vectors for an owned editor integration probe.

generate_vectors() is SYNTHETIC_TEST_ONLY. Pass a complete trusted actual
inspection to bind engine projections to its native revision verbatim. Cases
are alternatives against that one state, NOT a sequential script. Reinspect
and regenerate between effects, or restore the exact fixture before each case.
The fixed local lease/time is test data and never runtime authorization.

Godot JSON numbers require a fixed typed decoder: after bounded JSON/schema
validation, convert ONLY integral finite expected_generation (top + payload,
1..2147483647), inspect offset (0..64)/limit (1..64), and history steps (=1).
Reject bool/string/fraction/nonfinite/out-of-range values; no generic recursive
coercion, str_to_var, eval or changes to shared Request validation. Preview's
inner validated projection follows the same rules. Vectors are serialized by
the shared JCS serializer, never by Godot Variant serialization.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import importlib.util
from pathlib import Path
import re
import sys

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
_NAME = '_hh_gt03_vector_contract'
if _NAME not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_NAME, STUDIO/'godot-addon/contract.py')
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_NAME] = _module
    _spec.loader.exec_module(_module)
contract = sys.modules[_NAME]
from studio.protocol.core import Request, ValidationError, canonical_bytes, parse_json

NOW_MS = 1_800_000_000_000
PROJECT_ID = 'project.fixture'
LEASE_ID = 'lease.contract-vectors'
FENCE = 7


def _copy(value):
    return parse_json(canonical_bytes(value))


def _require(value, code='VECTOR_INVALID_SNAPSHOT'):
    if not value:
        raise ValueError(code)


def _synthetic_snapshot():
    nodes = [contract.NodeState('root', None, 'Node3D', 'Fixture'),
             contract.NodeState('vector-box', 'root', 'MeshInstance3D', 'VectorBox', box_size=(1,1,1))]
    rows=[]
    for node in nodes:
        row=node.as_dict()
        row.update(parent_id=row['parent_id'] or '',owner_id='' if node.stable_id=='root' else 'root',
                   sibling_index=0,stored={},groups=[])
        rows.append(row)
    state={'nodes':rows}
    return {'ok':True,'code':'SYNTHETIC_MODEL_ONLY','generation':1,'offset':0,'total':2,
            'held':False,'state':state,'revision':'sha256:'+hashlib.sha256(canonical_bytes(state)).hexdigest()}


def context_from_snapshot(snapshot, *, can_undo=False, can_redo=False, file_hashes=None):
    """Project vetted editable rows; retain the observed native revision.

    stored/groups/sibling_index/owner_id remain in the caller's complete native
    observation. This adapter does not replace that state by a partial hash.
    Completeness and owner checks prevent a paginated/foreign row set becoming
    the local semantic graph. This is not proof of observation provenance.
    """
    observed=_copy(snapshot)
    _require(type(observed) is dict and observed.get('ok') is True and observed.get('held') is False)
    _require(type(observed.get('revision')) is str and re.fullmatch(r'sha256:[0-9a-f]{64}',observed['revision']))
    _require(type(observed.get('generation')) is int and 1<=observed['generation']<=2147483647)
    _require(observed.get('offset')==0 and type(observed.get('state')) is dict
             and set(observed['state'])=={'nodes'})
    rows=observed['state']['nodes']
    _require(type(rows) is list and type(observed.get('total')) is int
             and observed['total']==len(rows) and 1<=len(rows)<=64,'VECTOR_INCOMPLETE_SNAPSHOT')
    nodes=[]
    required={'stable_id','parent_id','sibling_index','owner_id','node_type','name',
              'position','rotation_degrees','scale','stored','groups'}
    for row in rows:
        _require(type(row) is dict and required<=set(row)<=required|{'box_size'})
        root=row['stable_id']=='root'
        _require(row['owner_id']==('' if root else 'root'),'VECTOR_OWNER_SCOPE')
        _require(type(row['parent_id']) is str and ((row['parent_id']=='')==root),'VECTOR_PARENT_SCOPE')
        _require(type(row['sibling_index']) is int and 0<=row['sibling_index']<64)
        _require(type(row['stored']) is dict and type(row['groups']) is list
                 and all(type(v) is str for v in row['groups']))
        _require(row['groups']==sorted(set(row['groups'])))
        for field in ('position','rotation_degrees','scale'):
            _require(type(row[field]) is list and len(row[field])==3)
        nodes.append(contract.NodeState(row['stable_id'],None if root else row['parent_id'],
            row['node_type'],row['name'],tuple(row['position']),tuple(row['rotation_degrees']),
            tuple(row['scale']),tuple(row['box_size']) if 'box_size' in row else None))
    if file_hashes is None:
        file_hashes={contract.SCENE_PATH:hashlib.sha256(b'fixture-unread-scene').hexdigest(),
                     contract.SCRIPT_PATH:hashlib.sha256(b'fixture-unread-script').hexdigest()}
    context=contract.ValidationContext(PROJECT_ID,observed['revision'],observed['generation'],
        LEASE_ID,FENCE,NOW_MS+30_000,NOW_MS,tuple(nodes),tuple(sorted(file_hashes.items())),can_undo,can_redo)
    # Apply the existing complete context checks; do not invent a second schema.
    request=_request('vector.context','scene.inspect',{'stable_id':'root'},
                     {'expected_generation':context.generation,'offset':0,'limit':64},context)
    contract.validate_request(request,context)
    return context


def _request(identifier,operation,target,payload,context,**changes):
    values=dict(command_id=identifier,project_id=PROJECT_ID,operation=operation,
        lease_id=LEASE_ID,fencing_epoch=FENCE,expected_revision=context.revision,
        target=target,payload=payload,payload_hash='sha256:'+hashlib.sha256(canonical_bytes(payload)).hexdigest(),
        deadline_ms=NOW_MS+10_000)
    values.update(changes)
    return Request(**values)


def generate_vectors(actual_snapshot=None, *, can_undo=None, can_redo=None, file_hashes=None):
    """Return JSON-safe envelopes, validated projections and rejection cases.

    For actual observations, history flags default false and absent operations
    are deferred with explicit preconditions. Supply the actual local history
    observations to obtain undo/redo vectors. No action is applied here.
    """
    synthetic=actual_snapshot is None
    observed=_synthetic_snapshot() if synthetic else _copy(actual_snapshot)
    context=context_from_snapshot(observed,can_undo=synthetic if can_undo is None else can_undo,
        can_redo=synthetic if can_redo is None else can_redo,file_hashes=file_hashes)
    generation=context.generation
    nodes={node.stable_id:node for node in context.nodes}
    children=[node for node in context.nodes if node.stable_id!='root']
    target=sorted(children,key=lambda n:n.stable_id)[0].stable_id if children else 'root'
    leaves=[node for node in children if not any(other.parent_id==node.stable_id for other in children)]
    valid=[];rejected=[];deferred=[]
    integer_fields={'common':[{'path':'expected_generation','minimum':1,'maximum':2147483647},
                               {'path':'payload.expected_generation','minimum':1,'maximum':2147483647}],
                    'scene.inspect':[{'path':'payload.offset','minimum':0,'maximum':64},
                                     {'path':'payload.limit','minimum':1,'maximum':64}],
                    'scene.undo':[{'path':'payload.steps','minimum':1,'maximum':1}],
                    'scene.redo':[{'path':'payload.steps','minimum':1,'maximum':1}]}

    def good(name,operation,node_id,payload,expectation):
        request=_request('vector.'+name,operation,{'stable_id':node_id},payload,context)
        result=contract.validate_request(request,context)
        projection=result.projection
        engine=projection['preview_command'] if operation=='scene.preview' else projection
        route='inspect' if operation=='scene.inspect' else ('preview' if operation=='scene.preview' else 'apply')
        valid.append({'id':name,'request':request.as_dict(),'wire_json':canonical_bytes(request.as_dict()).decode(),
            'projection':projection,'engine_projection':engine,'engine_projection_json':canonical_bytes(engine).decode(),
            'engine_route':route,'integer_decode':integer_fields['common']+integer_fields.get(engine['operation'],[]),
            'expect':{'python':'VALIDATED','runtime_authorized':False,'committed':False,
                      'before_revision':context.revision,'generation':generation,**expectation}})

    good('inspect','scene.inspect','root',{'expected_generation':generation,'offset':0,'limit':64},
         {'engine_ok':True,'engine_code':'SCENE_INSPECTED','same_revision':True,'total':len(nodes)})
    suffix=1
    while 'vector-created-'+str(suffix) in nodes or any(n.parent_id=='root' and n.name.lower()==('VectorCreated'+str(suffix)).lower() for n in nodes.values()):
        suffix+=1
    create={'expected_generation':generation,'stable_id':'vector-created-'+str(suffix),
            'node_type':'MeshInstance3D','name':'VectorCreated'+str(suffix),'position':[1,2,3],
            'rotation_degrees':[0,0,0],'scale':[1,1,1],'box_size':[2,2,2]}
    if len(nodes)<64:
        good('create','scene.node.create','root',create,{'engine_ok':True,'engine_code':'SCENE_APPLIED_IN_MEMORY',
             'total':len(nodes)+1,'node':{'stable_id':create['stable_id'],'parent_id':'root','owner_id':'root',
                                       'position':[1,2,3],'box_size':[2,2,2]}})
    else:
        deferred.append({'id':'create','reason':'requires_one_free_node_slot'})
    changes={'position':[4,5,6]}
    good('update','scene.node.update',target,{'expected_generation':generation,'changes':changes},
         {'engine_ok':True,'engine_code':'SCENE_APPLIED_IN_MEMORY','total':len(nodes),
          'node':{'stable_id':target,'position':[4,5,6]}})
    if leaves:
        leaf=sorted(leaves,key=lambda n:n.stable_id)[0]
        good('remove','scene.node.remove',leaf.stable_id,{'expected_generation':generation},
             {'engine_ok':True,'engine_code':'SCENE_APPLIED_IN_MEMORY','total':len(nodes)-1,'absent_id':leaf.stable_id})
    else:
        deferred.append({'id':'remove','reason':'requires_observed_nonroot_leaf'})
    for operation,available in (('scene.undo',context.can_undo),('scene.redo',context.can_redo)):
        name=operation.split('.')[1]
        if available:
            good(name,operation,'root',{'expected_generation':generation,'steps':1},
                 {'engine_ok':True,'engine_code':'SCENE_APPLIED_IN_MEMORY',
                  'post_state':'must_match_actual_revision_bound_history_record'})
        else:
            deferred.append({'id':name,'reason':'requires_trusted_owned_history_available'})
    good('preview','scene.preview','root',{'expected_generation':generation,'operation':'scene.node.update',
         'target':{'stable_id':target},'payload':{'expected_generation':generation,'changes':changes}},
         {'engine_ok':True,'engine_code':'SCENE_PREVIEW','same_revision':True,'total':len(nodes)})

    base=_request('vector.invalid','scene.node.update',{'stable_id':target},
                  {'expected_generation':generation,'changes':{'position':[1,2,3]}},context)

    def bad(name,wire,expected):
        before=canonical_bytes(asdict(context))
        try:
            request=Request.from_json(wire)
            contract.validate_request(request,context)
        except ValidationError as error:
            _require(error.code==expected,'VECTOR_UNEXPECTED_REJECTION_'+name)
        else:
            raise AssertionError('VECTOR_INVALID_ACCEPTED_'+name)
        _require(canonical_bytes(asdict(context))==before)
        encoded=wire.hex()
        rejected.append({'id':name,'wire_hex_chunks':[encoded[i:i+4096] for i in range(0,len(encoded),4096)],'expected_code':expected,
                         'expected_no_effect':True,'engine_projection':None})

    def changed(name,code,**fields):
        body=base.as_dict();body.update(fields);body.pop('digest',None)
        body['payload_hash']='sha256:'+hashlib.sha256(canonical_bytes(body['payload'])).hexdigest()
        bad(name,canonical_bytes(body),code)

    raw=canonical_bytes(base.as_dict())
    bad('duplicate_key',raw[:-1]+b',"command_id":"vector.duplicate"}','DUPLICATE_KEY')
    bad('invalid_utf8',b'{"command_id":"\xff"}','INVALID_JSON')
    bad('nan_wire',raw.replace(b'[1,2,3]',b'[NaN,2,3]'),'INVALID_NUMBER')
    changed('wrong_lease','GODOT_STALE_LEASE',lease_id='lease.stale')
    changed('wrong_fence','GODOT_STALE_LEASE',fencing_epoch=FENCE+1)
    changed('stale_revision','GODOT_STALE_REVISION',expected_revision='sha256:'+('0'*64 if context.revision!='sha256:'+'0'*64 else '1'*64))
    stale_generation=generation+1 if generation<2147483647 else generation-1
    changed('stale_generation','GODOT_STALE_GENERATION',payload={'expected_generation':stale_generation,'changes':changes})
    changed('wrong_type','GODOT_INVALID_COMPONENT',payload={'expected_generation':generation,'changes':{'position':[True,0,0]}})
    changed('bad_command_id','GODOT_INVALID_COMMAND_ID',command_id='Vector/Outside')
    changed('expired_deadline','GODOT_DEADLINE_EXPIRED',deadline_ms=NOW_MS)
    changed('unsupported_property','GODOT_UNSUPPORTED_PROPERTY',payload={'expected_generation':generation,'changes':{'script':'res://evil.gd'}})
    script_payload={'expected_generation':generation,'expected_sha256':dict(context.file_hashes)[contract.SCRIPT_PATH],'text':'extends Node3D\n'}
    changed('confusing_script_path','GODOT_PATH_NOT_ALLOWED',operation='script_text.replace',
            target={'path':'scripts/../scripts/fixture_actor.gd'},payload=script_payload)
    changed('oversize_script','GODOT_SCRIPT_LIMIT',operation='script_text.replace',target={'path':contract.SCRIPT_PATH},
            payload={**script_payload,'text':'é'*8193})
    tampered=base.as_dict();tampered['payload_hash']='sha256:'+'0'*64
    bad('tampered_payload_hash',canonical_bytes(tampered),'PAYLOAD_HASH_MISMATCH')

    result={'schema':'hh-gt03-contract-vectors-1','catalog_digest':contract.CATALOG_DIGEST,
        'snapshot_mode':'SYNTHETIC_TEST_ONLY' if synthetic else 'SUPPLIED_NATIVE_OBSERVATION',
        'execution_mode':'INDEPENDENT_CASES_AGAINST_ONE_SNAPSHOT',
        'authority_mode':'SYNTHETIC_LOCAL_FIXTURE_ONLY','runtime_authorized':False,'acceptance':False,
        'revision_recomputed':False,'native_observation':observed,'context':asdict(context),
        'file_hashes_observed':file_hashes is not None,'valid':valid,'rejected':rejected,'deferred':deferred,
        'decoder_policy':{'json_only':True,'generic_coercion':False,'variant_decode':False,
            'integer_fields':integer_fields,'reject':['bool','string','fraction','nonfinite','out_of_range'],
            'notes':'Typed integral conversion only after exact closed schema validation; all other numbers stay untouched.'}}
    return _copy(result)


if __name__=='__main__':
    # Stdout is a test-only artifact; no file writes or process launches here.
    print(canonical_bytes(generate_vectors()).decode())

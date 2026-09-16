"""Bounded same-stream publication reconciliation, with readonly selected files.

RecoveryJournal accepts trusted internal attestations. PublicationRecovery is
the enforcing facade: fresh registered authority, actual owned editor readback,
then a durable terminal. It grants no subsequent editing or publication power.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import importlib.util
from pathlib import Path
import re
import sys
import threading
import time
import uuid
from studio.protocol.core import canonical_bytes, parse_json
from studio.host.core.limits import SafetyViolation

HERE = Path(__file__).resolve().parent


def _load(name):
    path=HERE/(name+'.py');raw=path.read_bytes()
    key='_hh_recovery_'+hashlib.sha256(str(path).encode()+b'\0'+raw).hexdigest()
    if key not in sys.modules:
        spec=importlib.util.spec_from_file_location(key,path)
        module=importlib.util.module_from_spec(spec);sys.modules[key]=module
        try:exec(compile(raw,str(path),'exec'),module.__dict__)
        except BaseException:
            del sys.modules[key]
            raise
    return sys.modules[key]


def _sha(raw):return hashlib.sha256(raw).hexdigest()
def _same(left,right):return canonical_bytes(left)==canonical_bytes(right)
def _now():return time.time_ns()//1_000_000


class RecoveryError(SafetyViolation):
    def __init__(self,code,*,cleanup_owner=None):
        self.cleanup_owner=cleanup_owner
        super().__init__(code)


def _need(condition,code):
    if not condition:raise RecoveryError(code)


def _restorable_unknown(snapshot,command,selected):
    return (command['phase']=='UNKNOWN' and not snapshot['stopped']
            and _same(selected,snapshot['last_good']))


def classify(snapshot,command):
    """Pure planning from a verified snapshot; it is never a recovery receipt."""
    phase=command['phase'];selected=snapshot['selected'];last_good=snapshot['last_good']
    same_good=_same(selected,last_good)
    terminal=phase in ('COMMITTED','FAILED','UNKNOWN') and 'response' in command
    current_terminal=phase=='COMMITTED' and _same(command['receipt']['selection'],selected['selector']['selection'])
    recovery=snapshot.get('recovery',{})
    blocked=command['command_id'] in recovery.get('blocked_original_commands',[])
    if _restorable_unknown(snapshot,command,selected):route='RESTORE_LAST_GOOD_REQUIRES_EXPLICIT_RECONCILIATION'
    elif snapshot['stopped'] or snapshot['held'] or phase=='UNKNOWN':route='HOLD_UNKNOWN_OR_STOP'
    elif 'edit_prepared' in command and phase=='COMMITTED':route='HISTORICAL_TERMINAL'
    elif 'edit_prepared' in command and phase in ('EDIT_INTENT','EDIT_READY') and same_good:route='RESTORE_LAST_GOOD'
    elif blocked and phase=='COMMITTED':route='SELECTED_REQUIRES_DURABLE_COMPLETION'
    elif phase=='COMMITTED':route='COMMITTED_ORIGINAL' if current_terminal else 'HISTORICAL_TERMINAL'
    elif phase=='FAILED':route='HISTORICAL_TERMINAL'
    elif phase in ('SELECTED','READBACK') and not same_good:route='SELECTED_REQUIRES_DURABLE_COMPLETION'
    elif phase in ('CAPTURE_PREPARED','CAPTURED','PREPARED','STAGED','VALIDATED','RETIRE_PREPARED','RETIRED','ACTIVATING') and same_good:
        route='RESTORE_LAST_GOOD'
    elif phase=='ACTIVATING' and 'recovery' in snapshot:route='SELECTED_REQUIRES_DURABLE_COMPLETION'
    else:route='HOLD_UNCLASSIFIED'
    return {'schema':'hh-godot-recovery-plan-1','command_id':command['command_id'],'digest':command['digest'],
        'phase':phase,'route':route,'terminal_response_available':terminal and not blocked,'selected_is_last_good':same_good,
        'project_revision':selected['bundle_manifest']['project_revision'],'selection':selected['selector']['selection'],
        'selector_version':selected['selector_version'],'project_files_read_only':True,'public_ack':False,
        'engine_readback_verified':False,'recovery_complete':False,'new_mutation_permitted':False,
        'missing_durability':[] if phase in ('COMMITTED','FAILED') else
            ['recovery-admission','registered-fresh-readback','same-custody-terminal']}


@dataclass(frozen=True,slots=True)
class RecoveryObservation:
    command_id:str
    digest:str
    observation_id:str
    observation_sha256:str


class PublicationRecovery:
    """Owned readonly selection with a narrow registered reconciliation path."""
    def __init__(self):raise TypeError('use PublicationRecovery.open')

    @classmethod
    def open(cls,storage_id,*,project_id,expected_source_closure_sha256):
        _need(type(expected_source_closure_sha256) is str and re.fullmatch('[0-9a-f]{64}',expected_source_closure_sha256),
              'RECOVERY_SOURCE_CLOSURE_REQUIRED')
        owner=object.__new__(cls);owner._lock=threading.RLock();owner._closed=owner._held=False
        owner._journal=owner._editor=None;owner._cleanup=[];owner._records={};owner._expected_source=expected_source_closure_sha256
        owner._journal_model=_load('publication_journal_v4');owner._editor_model=_load('editor_owner')
        owner._authority=None
        try:
            owner._journal=RecoveryJournal.open(storage_id,project_id=project_id,
                expected_source_closure_sha256=expected_source_closure_sha256)
            owner._snapshot()
            return owner
        except BaseException as exc:
            extra=getattr(exc,'cleanup_owner',None)
            if extra is not None and extra is not owner:owner._cleanup.append(extra)
            try:owner.close()
            except BaseException as cleanup_error:
                raise RecoveryError('RECOVERY_OPEN_CLEANUP_REQUIRED',cleanup_owner=owner) from cleanup_error
            raise

    def _healthy(self):_need(not self._closed and not self._held,'RECOVERY_HELD_OR_CLOSED')

    def _snapshot(self):
        self._healthy();snapshot=self._journal.snapshot()
        _need(snapshot['journal_read_only'] is True and snapshot['source_closure_sha256']==self._expected_source,
              'RECOVERY_SOURCE_OR_READONLY_MISMATCH')
        return snapshot

    def _inspection(self,command_id,digest):
        with self._lock:
            self._healthy()
            _need(type(self._journal) is RecoveryJournal,'RECOVERY_JOURNAL_OWNER_REQUIRED')
            snapshot,command,bundle,context=self._journal.inspect_command(command_id,digest)
            _need(snapshot['journal_read_only'] is True and snapshot['source_closure_sha256']==self._expected_source,
                  'RECOVERY_SOURCE_OR_READONLY_MISMATCH')
            _need(command is not None,'RECOVERY_COMMAND_UNKNOWN')
            _need(canonical_bytes(snapshot['selected']['bundle_manifest'])==bundle.manifest_bytes
                  and _same(context['selected'],snapshot['selected']),'RECOVERY_SELECTION_CHANGED')
            return snapshot,command,bundle,context

    def _view(self,command_id,digest):
        snapshot,command,bundle,context=self._inspection(command_id,digest)
        return snapshot,command,bundle,classify(snapshot,command)

    def inspect(self,command_id,digest):
        with self._lock:return self._view(command_id,digest)[3]

    def authority_context(self):
        with self._lock:
            self._healthy()
            _need(type(self._journal) is RecoveryJournal,'RECOVERY_JOURNAL_OWNER_REQUIRED')
            return self._journal.authority_context()

    def original_response(self,command_id,digest):
        """Historical bytes only; never a newly recovered success."""
        with self._lock:
            self._view(command_id,digest)
            return self._journal.lookup_response(command_id,digest)

    def _original_editor(self,command_id,digest):
        # Original v4 bytes remain immutable. COMMITTED's compact command no
        # longer carries CAPTURE_PREPARED, so derive it from that exact prefix.
        rows=[parse_json(raw) for raw in self._journal._state.events]
        prepared=[r for r in rows if r['kind'] in ('CAPTURE_PREPARED','EDIT_INTENT')
                  and r['command_id']==command_id and r['digest']==digest]
        _need(len(prepared)==1,'RECOVERY_ORIGINAL_EDITOR_MISSING')
        return prepared[0]['editor']

    def _editor_readback(self,bundle,original):
        _need(type(self._editor) is self._editor_model.EditorOwner,'RECOVERY_EDITOR_OWNER_REQUIRED')
        current=self._editor.script_observation();snapshot=current['snapshot'];identity=self._editor.identity
        files=parse_json(bundle.manifest_bytes)['files']
        expected={path:{key:row[key] for key in ('sha256','size_bytes')} for path,row in files.items()}
        _need(_same(snapshot['working_files'],expected) and snapshot['revision']==bundle.scene_revision
              and 'sha256:'+_sha(canonical_bytes(snapshot['state']))==bundle.scene_revision,
              'RECOVERY_EDITOR_SELECTED_BYTES_OR_SEMANTICS')
        _need(identity['engine_sha256']==original['engine_sha256']
              and identity['installed_source_sha256']==original['installed_source_sha256']
              and identity['session_id']!=original['session_id']
              and (identity['pid'],identity['creation_filetime'])!=(original['pid'],original['creation_filetime'])
              and not _same(identity['root_identity'],original['root_identity']), 'RECOVERY_EDITOR_IDENTITY')
        _need(snapshot['can_undo'] is False and snapshot['can_redo'] is False,'RECOVERY_EDITOR_HISTORY')
        _need(type(snapshot['root_instance_id']) is str and re.fullmatch('[1-9][0-9]{0,15}',snapshot['root_instance_id'])
              and int(snapshot['root_instance_id'])<=2**53-1,'RECOVERY_ROOT_INSTANCE')
        return {'editor':identity,'semantic_revision':snapshot['revision'],
            'semantic_sha256':bundle.scene_revision[7:],'semantic_state':snapshot['state'],
            'generation':snapshot['generation'],'root_instance_id':int(snapshot['root_instance_id']),
            'working_files':snapshot['working_files'],'script':current['script']}

    def observe_selected(self,command_id,digest,*,editor_parent,editor_binary,deadline_ms):
        with self._lock:
            _need(type(deadline_ms) is int and _now()<deadline_ms<=_now()+30000,'RECOVERY_OBSERVATION_DEADLINE')
            _need(self._editor is None and not self._records,'RECOVERY_OBSERVATION_ALREADY_OWNED')
            snapshot,command,bundle,plan=self._view(command_id,digest)
            _need(plan['route'] in ('COMMITTED_ORIGINAL','RESTORE_LAST_GOOD','SELECTED_REQUIRES_DURABLE_COMPLETION'),
                  'RECOVERY_OBSERVATION_NOT_PERMITTED')
            original=self._original_editor(command_id,digest);started=_now()
            try:
                # This creates a separate owned readback mirror, never writes
                # the selected protected project or enables public mutation.
                self._editor=self._editor_model.EditorOwner(editor_parent,bundle,editor_binary=editor_binary)
                actual=self._editor_readback(bundle,original)
                after=self._view(command_id,digest)
                _need(_same(plan,after[3]) and bundle==after[2] and _now()<deadline_ms,'RECOVERY_OBSERVATION_CHANGED_OR_EXPIRED')
                facts={**actual,'schema':'hh-godot-recovery-observation-1','command_id':command_id,'digest':digest,
                    'route':plan['route'],'project_revision':bundle.project_revision,'manifest_sha256':_sha(bundle.manifest_bytes),
                    'selection':plan['selection'],'selector_version':plan['selector_version'],
                    'started_ms':started,'observed_ms':_now(),'history_boundary':True,
                    'engine_readback_verified':True,'selected_project_mutated':False,'editor_mirror_created':True,
                    'public_ack':False,'recovery_complete':False,'durable_completion':False,'new_mutation_permitted':False}
                raw=canonical_bytes(facts)
                receipt=RecoveryObservation(command_id,digest,'recovery-'+uuid.uuid4().hex,_sha(raw))
                self._records[receipt.observation_id]=(receipt,tuple(getattr(receipt,key) for key in receipt.__slots__),raw,bundle,original)
                return receipt
            except BaseException as exc:
                self._held=True;extra=getattr(exc,'cleanup_owner',None)
                if extra is not None and extra is not self and extra is not self._editor:self._cleanup.append(extra)
                if not isinstance(exc,Exception):exc.cleanup_owner=self;raise
                raise RecoveryError('RECOVERY_OBSERVATION_UNCERTAIN',cleanup_owner=self) from exc

    def observation(self,receipt):
        with self._lock:
            self._healthy();_need(type(receipt) is RecoveryObservation,'RECOVERY_REGISTERED_OBSERVATION_REQUIRED')
            row=self._records.get(receipt.observation_id)
            _need(row is not None and row[0] is receipt and row[1]==tuple(getattr(receipt,key) for key in receipt.__slots__)
                  and _sha(row[2])==receipt.observation_sha256,'RECOVERY_REGISTERED_OBSERVATION_REQUIRED')
            facts=parse_json(row[2]);snapshot,command,bundle,plan=self._view(receipt.command_id,receipt.digest)
            actual=self._editor_readback(bundle,row[4])
            _need(bundle==row[3] and all(_same(actual[key],facts[key]) for key in actual)
                  and _same(plan['selection'],facts['selection'])
                  and _same(plan['selector_version'],facts['selector_version']),'RECOVERY_READBACK_CHANGED')
            return facts

    def reconcile(self,authority,command_id,digest,*,editor_parent,editor_binary,deadline_ms):
        """Reconcile once under a fresh registered grant; return durable bytes.

        The original command is never executed again. A fresh owned mirror loads
        the exact protected selection; only recovery events are appended.
        """
        with self._lock:
            self._healthy()
            _need(type(authority) is ReconciliationAuthority,'RECOVERY_AUTHORITY_REQUIRED')
            _need(self._authority is None and self._editor is None and not self._records,
                  'RECOVERY_ATTEMPT_ALREADY_OWNED')
            permit=authority.bind(self,command_id,digest,deadline_ms=deadline_ms)
            self._authority=authority
            try:
                def admit():
                    admitted=_now()
                    return self._journal.admit(command_id,digest,recovery_id=permit.recovery_id,
                        admission={'session_id':authority.session_id,'authority_epoch':permit.authority_epoch,
                            'admitted_ms':admitted,'deadline_ms':permit.deadline_ms,'explicit_reconcile':True},
                        observed_ms=admitted)
                recovery=authority._phase(permit,'capture',admit)
                attempt=recovery['attempts'][-1]
                def observe():
                    snapshot,command,bundle,plan=self._view(command_id,digest)
                    original=self._original_editor(command_id,digest);started=_now()
                    self._editor=self._editor_model.EditorOwner(editor_parent,bundle,editor_binary=editor_binary,
                        initial_generation=attempt['editor_generation'])
                    actual=self._editor_readback(bundle,original)
                    _need(actual['generation']==attempt['editor_generation'],'RECOVERY_EDITOR_GENERATION')
                    after=self._view(command_id,digest)
                    _need(bundle==after[2] and _same(plan,after[3]),'RECOVERY_OBSERVATION_CHANGED')
                    facts={**actual,'schema':'hh-godot-recovery-observation-1','command_id':command_id,'digest':digest,
                        'recovery_id':permit.recovery_id,'route':attempt['route'],'project_revision':bundle.project_revision,
                        'manifest_sha256':_sha(bundle.manifest_bytes),'selection':attempt['selected']['selector']['selection'],
                        'selector_version':attempt['selected']['selector_version'],'started_ms':started,'observed_ms':_now(),
                        'history_boundary':True,'engine_readback_verified':True,'selected_project_mutated':False,
                        'editor_mirror_created':True,'public_ack':False,'recovery_complete':False,
                        'durable_completion':False,'new_mutation_permitted':False}
                    raw=canonical_bytes(facts)
                    receipt=RecoveryObservation(command_id,digest,'recovery-'+uuid.uuid4().hex,_sha(raw))
                    self._records[receipt.observation_id]=(receipt,tuple(getattr(receipt,k) for k in receipt.__slots__),raw,bundle,original)
                    return receipt
                receipt=authority._phase(permit,'adopt',observe)
                def complete():
                    facts=self.observation(receipt)
                    _need(facts['recovery_id']==permit.recovery_id and facts['generation']==attempt['editor_generation'],
                          'RECOVERY_REGISTERED_ATTEMPT_REQUIRED')
                    selected=self._journal.snapshot()['selected']
                    observation={key:facts[key] for key in _READBACK_FIELDS
                        if key not in ('observation_id','observation_sha256','files')}
                    observation.update(observation_id=receipt.observation_id,observation_sha256=receipt.observation_sha256,
                        files=selected['bundle_manifest']['files'])
                    self._journal.readback_recovered(command_id,digest,recovery_id=permit.recovery_id,
                        observation=observation,observed_ms=_now())
                    # Recheck the live engine and scheduling authority immediately
                    # before the terminal append. Stop/revoke may arrive during I/O.
                    self.observation(receipt)
                    authority._check_live(permit)
                    self._journal.terminal_recovered(command_id,digest,recovery_id=permit.recovery_id,observed_ms=_now())
                    return self._journal.recovered_response(command_id,digest)
                return authority._phase(permit,'commit',complete)
            except BaseException as exc:
                self._held=True
                extra=getattr(exc,'cleanup_owner',None)
                if extra is not None and extra is not self and extra is not self._editor and extra not in self._cleanup:
                    self._cleanup.append(extra)
                try:self._journal.hold_reconciliation(command_id,digest,recovery_id=permit.recovery_id,
                    reason='reconciliation-interrupted',observed_ms=_now())
                except BaseException:pass  # Retain exact owners; reopen classifies the durable cut.
                authority.halt()
                if not isinstance(exc,Exception):exc.cleanup_owner=self;raise
                raise RecoveryError('RECOVERY_RECONCILIATION_UNCERTAIN',cleanup_owner=self) from exc

    def close(self):
        if not self._lock.acquire(timeout=2):raise RecoveryError('RECOVERY_CLOSE_BUSY',cleanup_owner=self)
        try:
            self._closed=True
            if getattr(self,'_authority',None) is not None:self._authority.halt()
            for resources in (self._cleanup,):
                while resources:
                    try:resources[0].close()
                    except BaseException as exc:raise RecoveryError('RECOVERY_CLOSE_REQUIRED',cleanup_owner=self) from exc
                    resources.pop(0)
            for name in ('_editor','_journal'):
                resource=getattr(self,name,None)
                if resource is not None:
                    try:resource.close()
                    except BaseException as exc:raise RecoveryError('RECOVERY_CLOSE_REQUIRED',cleanup_owner=self) from exc
                    setattr(self,name,None)
        finally:self._lock.release()


# The storage fold validates durable attestations; only the facade below checks
# the actual authority issuer and live engine observation before writing them.
from dataclasses import asdict
from studio.host.core.custody import WitnessCustody, identity_from, binding_value
from studio.host.core.custody_registry import RegistryCustody
from studio.host.core.private_events import PrivateEventLog, EventRecord
from studio.host.core.private_store import PrivateBlobStore
from studio.host.core.safe_replace import ProtectedFileRoot

_v4 = _load('publication_journal_v4')
_model = _v4.state_model
RECOVERY_SCHEMA = 'hh-godot-publication-recovery-1'
MAX_RECOVERY_EVENTS = 32
MAX_COMPOSITE_EVENTS = _model.MAX_EVENTS + MAX_RECOVERY_EVENTS
_RECOVERY_COMMON = {'schema','kind','sequence','project_id','observed_ms','publication_prefix_sha256'}
_RECOVERY_FIELDS = {
    'HOLD': {'saved_head','observed_head','reason','blocked_original_commands','selected'},
    'ADMITTED': {'command_id','digest','recovery_id','admission','route','selected','native_head','editor_generation'},
    'READBACK': {'command_id','digest','recovery_id','observation'},
    'TERMINAL': {'command_id','digest','recovery_id','response'},
    'STOPPED': {'reason'},
}
_READBACK_FIELDS = {'command_id','digest','observation_id','observation_sha256','editor',
    'generation','root_instance_id','semantic_revision','semantic_sha256','project_revision',
    'manifest_sha256','selection','selector_version','files','started_ms','observed_ms','history_boundary','public_ack'}


def _prefix_hash(publication):
    return _sha(canonical_bytes([_sha(raw) for raw in publication.events]))


def _head_shape(value):
    _model.shape(value,{'sequence','sha256','size'})
    _model.integer(value['sequence'],1,512);_model.hash_value(value['sha256']);_model.integer(value['size'],37,8*1024*1024)


def _original_terminal_positions(publication):
    positions={};pending=None
    for index,raw in enumerate(publication.events):
        row=parse_json(raw);kind=row['kind'];native_sequence=index+5
        if kind in ('CAPTURE_PREPARED','EDIT_INTENT'):pending=row['command_id']
        elif kind in ('COMMITTED','FAILED','UNKNOWN','EDIT_COMMITTED','EDIT_FAILED','EDIT_UNKNOWN'):
            positions[row['command_id']]=native_sequence
            if kind not in ('UNKNOWN','EDIT_UNKNOWN'):pending=None
        elif kind=='STOP' and pending is not None:
            positions.setdefault(pending,native_sequence)
    return positions


def _original_prepared(publication,command_id):
    rows=[parse_json(raw) for raw in publication.events]
    result=[r for r in rows if r['kind'] in ('CAPTURE_PREPARED','EDIT_INTENT') and r['command_id']==command_id]
    _need(len(result)==1,'RECOVERY_ORIGINAL_COMMAND_MISSING')
    return result[0]


def _next_editor_generation(publication,attempts):
    highest=0
    for raw in publication.events:
        row=parse_json(raw)
        if row['kind'] in ('CAPTURE_PREPARED','EDIT_INTENT'):highest=max(highest,row['editor_generation'])
        elif row['kind']=='READBACK':highest=max(highest,row['adoption']['generation_after'])
    highest=max([highest]+[attempt['editor_generation'] for attempt in attempts])
    _need(highest<2147483647,'RECOVERY_EDITOR_GENERATION_EXHAUSTED')
    return highest+1


def _recovery_response(publication,attempt,blocked):
    original=_model.lookup(publication,attempt['command_id'],attempt['digest'])
    observation=attempt['observation'];selected=attempt['selected'];manifest=selected['bundle_manifest']
    receipt={'schema':'hh-godot-recovered-terminal-1','command_id':attempt['command_id'],'digest':attempt['digest'],
        'recovery_id':attempt['recovery_id'],'route':attempt['route'],'project_revision':manifest['project_revision'],
        'scene_revision':manifest['caller_observations']['scene_revision'],'selection':selected['selector']['selection'],
        'selector_version':selected['selector_version'],'readback_event_sha256':attempt['readback_event_sha256'],
        'editor':observation['editor'],'generation':observation['generation'],'public_ack':False,'durable_owner_required':True}
    receipt_sha256=_sha(canonical_bytes(receipt))
    if attempt['route'] in ('verify-original','verify-historical-edit'):
        _need(original['phase']=='COMMITTED' and attempt['command_id'] not in blocked,'RECOVERY_ORIGINAL_NOT_WITNESSED')
        response=original['response']
    else:
        restored=attempt['route']=='restore-last-good'
        operation=_original_prepared(publication,attempt['command_id'])['operation']
        from studio.protocol.core import Response,Status
        code='GODOT_RECOVERED_LAST_GOOD' if restored else {
            'scene.save':'GODOT_MANAGED_SCENE_SAVED','script_text.replace':'GODOT_MANAGED_SCRIPT_REPLACED'}[operation]
        response=Response(Status.REJECTED if restored else Status.COMMITTED,code,attempt['command_id'],
            postconditions={'request_digest':attempt['digest'],'project_revision':manifest['project_revision'],
                'scene_revision':manifest['caller_observations']['scene_revision'],'selection':selected['selector']['selection'],
                'generation':observation['generation'],'history_boundary':True,'managed_fixture_only':True,
                'reconciled':True,'restored_last_good':restored,'public_ack':not restored,
                'original_outcome_unknown':original['phase']=='UNKNOWN' or attempt['command_id'] in blocked,
                'restored_editor_history':False,'files_saved':not restored,
                'durable_receipt_sha256':receipt_sha256}).as_dict()
    return {'receipt':receipt,'receipt_sha256':receipt_sha256,'response':response,'response_sha256':_sha(canonical_bytes(response))}


def _selected_value(publication,selected):
    snapshot=publication.snapshot();_model.shape(selected,{'bundle_manifest','selector','selector_version'})
    _model.manifest(selected['bundle_manifest'],snapshot)
    _model.descriptor(selected['selector']['descriptor'],selected['bundle_manifest'],snapshot)
    _model.selector_version(selected['selector_version'],snapshot['content_root_identity'])
    _need(selected['selector_version']['sha256']==_sha(canonical_bytes(selected['selector']))
        and selected['selector_version']['size_bytes']==len(canonical_bytes(selected['selector'])),'RECOVERY_SELECTOR_VERSION')
    if _same(selected,snapshot['selected']):return
    command=_model.lookup(publication,snapshot['pending_command_id']) if snapshot['pending_command_id'] else None
    _need(command is not None and command['phase']=='ACTIVATING' and _same(command['selector'],selected['selector'])
        and _same(command['bundle_manifest'],selected['bundle_manifest']),'RECOVERY_UNEXPECTED_SELECTOR')
    ids=set(snapshot['content_file_ids'])|{snapshot['content_root_identity']['file_id'],snapshot['selected']['selector_version']['file_id']}
    _need(selected['selector_version']['file_id'] not in ids,'RECOVERY_SELECTOR_ALIAS')


def _fold_recovery(publication,tail):
    """Typed suffix fold; shape checks never establish native/engine authority."""
    snapshot=publication.snapshot();prefix=_prefix_hash(publication);positions=_original_terminal_positions(publication)
    result={'attempts':[],'blocked_original_commands':[],'held':False,'stopped':False,
        'selected':None,'last_observed_ms':snapshot['last_observed_ms']}
    ids=set();observations=set();epoch=snapshot['highest_fencing_epoch']
    _need(len(tail)<=MAX_RECOVERY_EVENTS,'RECOVERY_EVENT_LIMIT')
    for index,raw in enumerate(tail):
        _need(type(raw) is bytes,'RECOVERY_EVENT_BYTES')
        row=parse_json(raw);_need(type(row) is dict and type(row.get('kind')) is str,'RECOVERY_EVENT_KIND')
        kind=row['kind'];_need(kind in _RECOVERY_FIELDS,'RECOVERY_EVENT_KIND')
        _model.shape(row,_RECOVERY_COMMON|_RECOVERY_FIELDS[kind]);_model.integer(row['sequence'],1,MAX_RECOVERY_EVENTS)
        _model.integer(row['observed_ms']);_need(canonical_bytes(row)==raw,'RECOVERY_NONCANONICAL_EVENT')
        _need(row['schema']==RECOVERY_SCHEMA and row['sequence']==index+1 and row['project_id']==snapshot['project_id']
              and row['publication_prefix_sha256']==prefix and row['observed_ms']>=result['last_observed_ms'],'RECOVERY_EVENT_ORDER')
        _need(len(raw)<=12288,'RECOVERY_EVENT_BYTES');result['last_observed_ms']=row['observed_ms']
        if kind=='STOPPED':
            _model.identifier(row['reason'])
            _need(not result['stopped'],'RECOVERY_ALREADY_STOPPED')
            result['stopped']=result['held']=True
            if result['attempts'] and result['attempts'][-1]['phase']!='TERMINAL':
                result['attempts'][-1]['phase']='HELD'
            continue
        if kind=='HOLD':
            _head_shape(row['saved_head']);_head_shape(row['observed_head']);_model.identifier(row['reason'])
            _need(row['saved_head']['sequence']<=row['observed_head']['sequence'],'RECOVERY_HOLD_HEADS')
            _selected_value(publication,row['selected'])
            _need(result['selected'] is None or _same(result['selected'],row['selected']),'RECOVERY_SELECTION_CHANGED')
            result['selected']=row['selected']
            expected=sorted(cid for cid,position in positions.items() if position>row['saved_head']['sequence'])
            _need(_same(row['blocked_original_commands'],expected),'RECOVERY_BLOCKED_TERMINAL_MAP')
            result['blocked_original_commands']=sorted(set(result['blocked_original_commands'])|set(expected))
            if result['attempts']:
                latest=result['attempts'][-1]
                witnessed_terminal=(latest['phase']=='TERMINAL'
                    and latest['terminal_native_sequence']<=row['saved_head']['sequence'])
                if not witnessed_terminal:latest['phase']='HELD'
            result['held']=True;continue
        for name in ('command_id','recovery_id'):_model.identifier(row[name])
        _model.hash_value(row['digest'],revision=True)
        original=_model.lookup(publication,row['command_id'],row['digest'])
        _need(original is not None,'RECOVERY_COMMAND_UNKNOWN')
        if kind=='ADMITTED':
            _need(not result['stopped'],'RECOVERY_STOPPED')
            _need(not result['attempts'] or result['attempts'][-1]['phase'] in ('HELD','TERMINAL'),'RECOVERY_ATTEMPT_ALREADY_PENDING')
            _need(row['recovery_id'] not in ids,'RECOVERY_ID_REUSED');ids.add(row['recovery_id'])
            restorable_unknown=_restorable_unknown(snapshot,original,row['selected'])
            _need(not snapshot['stopped'] and (not snapshot['held'] or restorable_unknown)
                and (original['phase']!='UNKNOWN' or restorable_unknown),'RECOVERY_STOP_OR_UNKNOWN')
            admission=row['admission'];_model.shape(admission,{'session_id','authority_epoch','admitted_ms','deadline_ms','explicit_reconcile'})
            _model.identifier(admission['session_id'])
            for name in ('authority_epoch','admitted_ms','deadline_ms'):_model.integer(admission[name],1)
            _need(admission['authority_epoch']>epoch and admission['explicit_reconcile'] is True
                and admission['admitted_ms']<=row['observed_ms']<admission['deadline_ms']<=admission['admitted_ms']+30000,
                'RECOVERY_FRESH_ADMISSION')
            epoch=admission['authority_epoch'];_head_shape(row['native_head'])
            _model.integer(row['editor_generation'],1,2147483647)
            _need(row['editor_generation']==_next_editor_generation(publication,result['attempts']),'RECOVERY_EDITOR_GENERATION')
            selected=row['selected'];_model.shape(selected,{'bundle_manifest','selector','selector_version'})
            _model.manifest(selected['bundle_manifest'],snapshot)
            _model.descriptor(selected['selector']['descriptor'],selected['bundle_manifest'],snapshot)
            _model.selector_version(selected['selector_version'],snapshot['content_root_identity'])
            _need(selected['selector_version']['sha256']==_sha(canonical_bytes(selected['selector']))
                and selected['selector_version']['size_bytes']==len(canonical_bytes(selected['selector'])),'RECOVERY_SELECTOR_VERSION')
            is_old=_same(selected,snapshot['last_good'])
            is_edit='edit_prepared' in original
            if row['route']=='verify-original':
                _need(not is_edit and original['phase']=='COMMITTED' and row['command_id'] not in result['blocked_original_commands']
                    and _same(selected,snapshot['selected']) and _same(original['receipt']['selection'],selected['selector']['selection']),
                    'RECOVERY_ORIGINAL_SELECTION')
            elif row['route']=='verify-historical-edit':
                _need(is_edit and original['phase']=='COMMITTED' and row['command_id'] not in result['blocked_original_commands']
                    and _same(selected,snapshot['selected']) and _same(original['receipt']['selection'],selected['selector']['selection']),
                    'RECOVERY_HISTORICAL_EDIT_SELECTION')
            elif row['route']=='restore-last-good':
                orphan_edit=(is_edit and original['phase']=='COMMITTED' and row['command_id'] in result['blocked_original_commands']
                    and _same(original['receipt']['selection'],selected['selector']['selection']))
                _need(is_old and (original['phase'] not in ('COMMITTED','FAILED','SELECTED','READBACK') or orphan_edit),
                      'RECOVERY_RESTORE_NOT_LAST_GOOD')
            elif row['route']=='complete-selected':
                _need(not is_edit and original['phase']!='UNKNOWN','RECOVERY_SELECTED_COMPLETION')
                if original['phase']=='ACTIVATING':
                    _need(_same(selected['selector'],original['selector'])
                        and _same(selected['bundle_manifest'],original['bundle_manifest'])
                        and selected['selector_version']['file_id']!=snapshot['selected']['selector_version']['file_id'],
                        'RECOVERY_ACTIVATING_SELECTOR')
                else:
                    _need(original['phase'] in ('SELECTED','READBACK','COMMITTED') and _same(selected,snapshot['selected'])
                        and (original['phase']!='COMMITTED' or row['command_id'] in result['blocked_original_commands']),
                        'RECOVERY_SELECTED_COMPLETION')
            else:raise RecoveryError('RECOVERY_ROUTE')
            _selected_value(publication,selected)
            _need(result['selected'] is None or _same(result['selected'],selected),'RECOVERY_SELECTION_CHANGED')
            result['selected']=selected
            result['attempts'].append({**row,'phase':'ADMITTED'});result['held']=False;continue
        _need(result['attempts'] and not result['held'],'RECOVERY_ADMISSION_REQUIRED');attempt=result['attempts'][-1]
        _need(all(row[k]==attempt[k] for k in ('command_id','digest','recovery_id')),'RECOVERY_ATTEMPT_CONFLICT')
        if kind=='READBACK':
            _need(attempt['phase']=='ADMITTED','RECOVERY_READBACK_PHASE');facts=row['observation'];_model.shape(facts,_READBACK_FIELDS)
            p=_original_prepared(publication,row['command_id']);selected=attempt['selected'];manifest=selected['bundle_manifest']
            _model.identifier(facts['observation_id']);_model.hash_value(facts['observation_sha256'])
            _need(facts['observation_id'] not in observations,'RECOVERY_OBSERVATION_REUSED');observations.add(facts['observation_id'])
            _model.editor_identity(facts['editor'],snapshot['editor_engine_sha256'])
            _model.integer(facts['generation'],1,2147483647);_model.integer(facts['root_instance_id'],1);_model.integer(facts['started_ms']);_model.integer(facts['observed_ms'])
            _model.values._files(facts['files']);_model.hash_value(facts['semantic_sha256'])
            old,new=p['editor'],facts['editor']
            _need(new['session_id']!=old['session_id'] and (new['pid'],new['creation_filetime'])!=(old['pid'],old['creation_filetime'])
                and not _same(new['root_identity'],old['root_identity']) and new['installed_source_sha256']==old['installed_source_sha256'],
                'RECOVERY_FRESH_EDITOR_REQUIRED')
            _need(facts['command_id']==row['command_id'] and facts['digest']==row['digest']
                and facts['generation']==attempt['editor_generation']
                and facts['semantic_revision']=='sha256:'+facts['semantic_sha256']==manifest['caller_observations']['scene_revision']
                and facts['project_revision']==manifest['project_revision'] and facts['manifest_sha256']==_model.digest(manifest)
                and _same(facts['selection'],selected['selector']['selection']) and _same(facts['selector_version'],selected['selector_version'])
                and _same(facts['files'],manifest['files']) and facts['history_boundary'] is True and facts['public_ack'] is False
                and attempt['observed_ms']<=facts['started_ms']<=facts['observed_ms']<=row['observed_ms']<attempt['admission']['deadline_ms'],
                'RECOVERY_READBACK_BINDING')
            attempt.update(phase='READBACK',observation=facts,readback_event_sha256=_sha(raw));continue
        _need(attempt['phase']=='READBACK' and row['observed_ms']<attempt['admission']['deadline_ms'],'RECOVERY_TERMINAL_PHASE_OR_DEADLINE')
        expected=_recovery_response(publication,attempt,result['blocked_original_commands'])
        _need(_same(row['response'],expected['response']),'RECOVERY_TERMINAL_RESPONSE_MISMATCH')
        attempt.update(phase='TERMINAL',terminal_native_sequence=len(publication.events)+4+row['sequence'],**expected)
    return result


class RecoveryJournal(_v4.PublicationJournalV4):
    """Same protected stream; readonly selected files, no inherited writer API."""
    @classmethod
    def create(cls,*args,**kwargs):raise RecoveryError('RECOVERY_REOPEN_ONLY')

    @classmethod
    def reopen(cls,*args,**kwargs):raise RecoveryError('RECOVERY_EXPLICIT_OPEN_REQUIRED')

    @classmethod
    def open(cls,storage_id,*,project_id,expected_source_closure_sha256):
        _model.hash_value(expected_source_closure_sha256)
        owner=cls._owner(storage_id,project_id,readonly=True);owner._bound=False;owner._events=None
        owner._expected_source=expected_source_closure_sha256;owner._recovery=None
        try:
            owner._registry=RegistryCustody.reopen(storage_id)
            owner._custody=WitnessCustody(owner._registry,storage_id=storage_id,project_id=project_id)
            record=owner._custody.record;_need(record['phase']=='READY','RECOVERY_INCOMPLETE_PROVISIONING')
            owner._files=ProtectedFileRoot.reopen_readonly(record['files']['path'],identity_from(record['files']['identity']))
            owner._store=_v4.store_model.ProtectedBundleStore(owner._files)
            owner._blobs=PrivateBlobStore.reopen(record['blobs']['path'],identity_from(record['blobs']['identity']))
            owner._custody.confirm_current();saved=owner._custody.binding
            owner._log=PrivateEventLog.reopen(record['events']['path'],saved);owner._head=owner._log.binding().witnessed
            records=owner._read_unbound();owner._bootstrap=tuple(records[:3])
            publication,recovery,events,actual=owner._validate(records)
            ahead=saved.witnessed!=owner._head
            cas_gap=not _same(actual,publication.snapshot()['selected']) and recovery['selected'] is None
            interrupted=bool(recovery['attempts'] and recovery['attempts'][-1]['phase'] in ('ADMITTED','READBACK'))
            if ahead or cas_gap or interrupted:
                tail=events[len(publication.events):]
                previous=parse_json(tail[-1]) if tail else None
                reusable=previous is not None and previous['kind']=='HOLD' and previous['saved_head']==asdict(saved.witnessed)
                if not reusable:
                    event=owner._recovery_event(publication,tail,'HOLD',max(_now(),recovery['last_observed_ms']),
                        saved_head=asdict(saved.witnessed),observed_head=asdict(owner._head),
                        reason='unwitnessed-tail' if ahead else 'unwitnessed-selection' if cas_gap else 'interrupted-reconciliation',selected=actual,
                        blocked_original_commands=sorted(cid for cid,pos in _original_terminal_positions(publication).items() if pos>saved.witnessed.sequence))
                    _fold_recovery(publication,(*tail,canonical_bytes(event)))
                    owner._head=owner._log.append(event,owner._head,reserve_records=3,reserve_bytes=3*12800)
                    publication,recovery,events,actual=owner._validate(owner._read_unbound())
                # HOLD must be durable in this exact stream before high-water
                # advancement, even if a previous opener died before this call.
                _need(parse_json(events[-1])['kind']=='HOLD','RECOVERY_HOLD_REQUIRED')
                owner._custody.persist_binding(owner._log.binding())
            owner._log.bind_custody(owner._custody);owner._bound=True
            owner._state,owner._recovery,owner._events=publication,recovery,events
            owner._verify_owners();owner._refresh()
            return owner
        except BaseException as exc:owner._init_failure(exc)

    def _verify_unbound(self):
        # Same retained owners as V4, but deliberately do not require equality
        # between log tail and saved custody until typed HOLD reconciliation.
        _need(type(self._registry) is RegistryCustody and type(self._custody) is WitnessCustody
            and type(self._files) is ProtectedFileRoot and type(self._blobs) is PrivateBlobStore
            and type(self._log) is PrivateEventLog,'RECOVERY_EXACT_OWNERS')
        _need(type(self._store) is _v4.store_model.ProtectedBundleStore and self._store.readonly is True,'RECOVERY_READONLY_STORE')
        with self._store._mutex:self._store._healthy();self._store._inventory()
        for resource in (self._files,self._blobs):
            _need(resource._mutex.acquire(timeout=2),'RECOVERY_NATIVE_BUSY')
            try:resource._check()
            finally:resource._mutex.release()
        self._custody.confirm_current();record=self._custody.record
        _need(record['storage_id']==self._storage_id==self._registry.local_id and record['project_id']==self._project_id,'RECOVERY_CUSTODY_IDENTITY')
        for key,resource in (('files',self._files),('blobs',self._blobs)):
            _need(str(resource.root)==record[key]['path'] and resource.root_identity.same_file(identity_from(record[key]['identity'])),
                'RECOVERY_ROOT_IDENTITY')
        binding=self._log.binding();saved=self._custody.binding
        _need(str(self._log.root)==record['events']['path'] and binding.root.same_file(saved.root)
            and binding.stream.same_file(saved.stream) and binding.witnessed==self._head,'RECOVERY_STREAM_IDENTITY')
        return binding

    def _read_unbound(self):
        binding=self._verify_unbound()
        def collect(events,record):
            _need(type(record) is EventRecord,'RECOVERY_EXACT_EVENT_RECORD')
            if record.head.sequence==1:
                genesis={'kind':'GENESIS','store_id':self._log.root.name,'volume':str(binding.stream.volume),
                    'file_id':binding.stream.file_id,'root_file_id':binding.root.file_id}
                _need(not events and _same(parse_json(record.event),genesis),'RECOVERY_GENESIS');return events
            _need(len(events)<MAX_COMPOSITE_EVENTS+3,'RECOVERY_COMPOSITE_LIMIT')
            return (*events,record.event)
        head,records=self._log.fold((),collect)
        _need(head==self._head and head.sequence==len(records)+1,'RECOVERY_NATIVE_SEQUENCE')
        return records

    def _validate_view(self,records):
        _need(len(records)>=4 and tuple(records[:3])==self._bootstrap,'RECOVERY_BOOTSTRAP_PREFIX')
        config=self._verify_bootstrap();events=tuple(records[3:]);_need(events[0]==canonical_bytes(config),'RECOVERY_CONFIG_PREFIX')
        split=next((i for i,raw in enumerate(events) if parse_json(raw).get('schema')==RECOVERY_SCHEMA),len(events))
        prefix=events[:split]
        has_edits=any(parse_json(raw).get('schema')=='hh-godot-publication-event-5' for raw in prefix)
        publication=(_load('publication_state_v5') if has_edits else _model).replay(prefix);snapshot=publication.snapshot()
        _need(snapshot['source_closure_sha256']==self._expected_source and snapshot['project_id']==self._project_id
            and _same(snapshot['content_root_identity'],_v4._identity(self._files)),'RECOVERY_SOURCE_OR_ROOT')
        if has_edits:_load('publication_journal_v5').PublicationJournalV5._verify_edit_blobs(self,snapshot)
        tail=events[split:];recovery=_fold_recovery(publication,tail)
        for tail_index,raw in enumerate(tail):
            row=parse_json(raw);native_sequence=len(publication.events)+5+tail_index
            for name in ('saved_head','observed_head','native_head'):
                if name in row:
                    _need(row[name]['sequence']<native_sequence and asdict(self._log.read(row[name]['sequence']).head)==row[name],'RECOVERY_NATIVE_HEAD_REFERENCE')
                    if name in ('observed_head','native_head'):_need(row[name]['sequence']==native_sequence-1,'RECOVERY_IMMEDIATE_NATIVE_HEAD')
        actual=self._store.inspect_selection();bundle=self._store.read_descriptor(actual.descriptor)
        selected={'bundle_manifest':parse_json(bundle.manifest_bytes),'selector':parse_json(actual.source_bytes),
            'selector_version':_v4._version(actual.version)}
        if not _same(selected,snapshot['selected']):
            pending=_model.lookup(publication,snapshot['pending_command_id']) if snapshot['pending_command_id'] else None
            _need(pending is not None and pending['phase']=='ACTIVATING' and _same(selected['selector'],pending['selector'])
                and _same(selected['bundle_manifest'],pending['bundle_manifest']),'RECOVERY_UNEXPECTED_SELECTOR')
            ids=set(snapshot['content_file_ids'])|{snapshot['content_root_identity']['file_id'],snapshot['selected']['selector_version']['file_id']}
            _need(selected['selector_version']['file_id'] not in ids,'RECOVERY_SELECTOR_ALIAS')
        if recovery['selected'] is not None:
            _need(_same(selected,recovery['selected']),'RECOVERY_SELECTED_AFTER_ADMISSION_CHANGED')
        return publication,recovery,events,selected,bundle

    def _validate(self,records):
        return self._validate_view(records)[:4]

    def _read_edit_blob(self,descriptor):
        return _load('publication_journal_v5').PublicationJournalV5._read_edit_blob(self,descriptor)

    def _refresh_view(self):
        self._verify_owners()
        publication,recovery,events,selected,bundle=self._validate_view(self._read_unbound())
        _need(self._events==events,'RECOVERY_HISTORY_CHANGED')
        return publication,recovery,selected,bundle

    def _refresh(self):
        publication,recovery,selected,bundle=self._refresh_view()
        return publication,recovery,selected

    def _recovery_event(self,publication,tail,kind,observed_ms,**fields):
        return {'schema':RECOVERY_SCHEMA,'kind':kind,'sequence':len(tail)+1,'project_id':self._project_id,
            'observed_ms':observed_ms,'publication_prefix_sha256':_prefix_hash(publication),**fields}

    def _append_recovery(self,kind,observed_ms,**fields):
        publication,recovery,selected=self._refresh();tail=self._events[len(publication.events):]
        event=self._recovery_event(publication,tail,kind,observed_ms,**fields)
        prospective=_fold_recovery(publication,(*tail,canonical_bytes(event)))
        try:
            reserve=MAX_RECOVERY_EVENTS-len(tail)-1
            self._head=self._log.append(event,self._head,reserve_records=reserve,reserve_bytes=reserve*12800)
            observed,replayed,events,actual=self._validate(self._read_unbound())
            _need(events==(*self._events,canonical_bytes(event)) and _same(prospective,replayed),'RECOVERY_APPEND_READBACK')
            self._state,self._recovery,self._events=observed,replayed,events
            return replayed
        except BaseException as exc:self._poison(exc)

    def _snapshot_value(self,publication,recovery,selected):
        snapshot=publication.snapshot()
        return {**snapshot,'selected':selected,'recovery':recovery,'journal_read_only':True,
            'stopped':snapshot['stopped'] or recovery['stopped'],
            'public_ack':False,'new_mutation_permitted':False,'engine_effects_verified':False}

    def _authority_value(self,publication,recovery,selected):
        snapshot=publication.snapshot()
        epoch=max([snapshot['highest_fencing_epoch']]+[a['admission']['authority_epoch'] for a in recovery['attempts']])
        return {'storage_id':self._storage_id,'project_id':self._project_id,
            'source_closure_sha256':self._expected_source,'editor_engine_sha256':snapshot['editor_engine_sha256'],
            'publication_prefix_sha256':_prefix_hash(publication),'native_head':asdict(self._head),
            'selected':selected,'minimum_authority_epoch':epoch}

    def inspect_command(self,command_id,digest):
        """One fresh native verification for one coherent, detached observation.

        Nothing is cached across calls, engine I/O, append or authority phases.
        The bundle is the one already read and checked in this native pass.
        """
        with self._locked():
            publication,recovery,selected,bundle=self._refresh_view()
            snapshot=self._snapshot_value(publication,recovery,selected)
            context=self._authority_value(publication,recovery,selected)
            command=_model.lookup(publication,command_id,digest)
            # Do not expose a mutable journal/selection object to the caller.
            snapshot,command,context=parse_json(canonical_bytes([snapshot,command,context]))
            return snapshot,command,bundle,context

    def snapshot(self):
        with self._locked():return self._snapshot_value(*self._refresh())

    def stop_recovery(self,*,reason,observed_ms):
        """Persist a deliberate Stop in this stream without rewriting its prefix."""
        with self._locked():
            publication,recovery,selected=self._refresh()
            _model.identifier(reason);_model.integer(observed_ms)
            if recovery['stopped'] or publication.snapshot()['stopped']:
                return recovery
            return self._append_recovery('STOPPED',max(observed_ms,_now(),recovery['last_observed_ms']),
                reason=reason)

    def authority_context(self):
        """Fresh native binding for registered admission; no authority is minted."""
        with self._locked():
            return self._authority_value(*self._refresh())

    def selection_facts(self):
        with self._locked():
            publication,recovery,selected=self._refresh()
            return {k:selected[k] for k in ('selector','selector_version')}

    def read_selected_bundle(self):
        with self._locked():
            publication,recovery,selected=self._refresh()
            return self._store.read_descriptor(selected['selector']['descriptor'])

    def lookup(self,command_id,command_digest=None):
        with self._locked():
            publication,recovery,selected=self._refresh()
            return _model.lookup(publication,command_id,command_digest)

    def original_response(self,command_id,digest):
        with self._locked():
            publication,recovery,selected=self._refresh()
            _need(command_id not in recovery['blocked_original_commands'],'RECOVERY_ORIGINAL_NOT_WITNESSED')
            return _model.lookup_response(publication,command_id,digest)

    def lookup_response(self,command_id,command_digest):return self.original_response(command_id,command_digest)

    def admit(self,command_id,digest,*,recovery_id,admission,observed_ms):
        """Internal authority attestation; outer owner validates a fresh grant."""
        with self._locked():
            publication,recovery,selected=self._refresh();command=_model.lookup(publication,command_id,digest)
            _need(command is not None,'RECOVERY_COMMAND_UNKNOWN')
            witnessed=command['phase']=='COMMITTED' and command_id not in recovery['blocked_original_commands']
            is_edit='edit_prepared' in command
            route=('verify-historical-edit' if witnessed and is_edit else 'verify-original' if witnessed
                else 'restore-last-good' if is_edit and _same(selected,publication.snapshot()['last_good'])
                else 'restore-last-good' if _same(selected,publication.snapshot()['last_good']) and command['phase']!='COMMITTED'
                else 'complete-selected')
            tail=self._events[len(publication.events):]
            # Leave STOPPED plus the mandatory HOLD if its custody update fails.
            _need(len(tail)+5<=MAX_RECOVERY_EVENTS,'RECOVERY_TERMINAL_RESERVE')
            editor_generation=_next_editor_generation(publication,recovery['attempts'])
            proposed=self._recovery_event(publication,tail,'ADMITTED',observed_ms,command_id=command_id,digest=digest,
                recovery_id=recovery_id,admission=admission,route=route,selected=selected,native_head=asdict(self._head),editor_generation=editor_generation)
            _fold_recovery(publication,(*tail,canonical_bytes(proposed)))
            # Reapply actual barriers while the immutable project stays readonly.
            for row in (*selected['selector']['descriptor']['files'].values(),selected['selector']['descriptor']['manifest']):
                version,raw=self._files.read(row['name']);_need(_v4._version(version)=={k:row[k] for k in ('volume','file_id','size_bytes','sha256')},'RECOVERY_CONTENT_BARRIER_IDENTITY')
                self._files.confirm_barrier(row['name'],version)
            version,raw=self._files.read('active.json')
            _need(_v4._version(version)==selected['selector_version'] and raw==canonical_bytes(selected['selector']),'RECOVERY_SELECTOR_BARRIER_IDENTITY')
            self._files.confirm_barrier('active.json',version)
            return self._append_recovery('ADMITTED',max(observed_ms,_now()),command_id=command_id,digest=digest,recovery_id=recovery_id,
                admission=admission,route=route,selected=selected,native_head=asdict(self._head),editor_generation=editor_generation)

    def readback_recovered(self,command_id,digest,*,recovery_id,observation,observed_ms):
        with self._locked():return self._append_recovery('READBACK',observed_ms,command_id=command_id,digest=digest,
            recovery_id=recovery_id,observation=observation)

    def terminal_recovered(self,command_id,digest,*,recovery_id,observed_ms):
        with self._locked():
            publication,recovery,selected=self._refresh();_need(recovery['attempts'],'RECOVERY_ADMISSION_REQUIRED')
            attempt=recovery['attempts'][-1]
            _need(attempt['phase']=='READBACK','RECOVERY_READBACK_REQUIRED')
            response=_recovery_response(publication,attempt,recovery['blocked_original_commands'])['response']
            return self._append_recovery('TERMINAL',observed_ms,command_id=command_id,digest=digest,
                recovery_id=recovery_id,response=response)

    def recovered_response(self,command_id,digest):
        with self._locked():
            publication,recovery,selected=self._refresh();_model.lookup(publication,command_id,digest)
            _need(recovery['attempts'] and recovery['attempts'][-1]['phase']=='TERMINAL','RECOVERY_TERMINAL_REQUIRED')
            attempt=recovery['attempts'][-1]
            _need(attempt['command_id']==command_id and attempt['digest']==digest,'RECOVERY_COMMAND_CONFLICT')
            return canonical_bytes(attempt['response'])

    def hold_reconciliation(self,command_id,digest,*,recovery_id,reason,observed_ms):
        with self._locked():
            publication,recovery,selected=self._refresh()
            _need(recovery['attempts'],'RECOVERY_ADMISSION_REQUIRED');attempt=recovery['attempts'][-1]
            _need(attempt['command_id']==command_id and attempt['digest']==digest and attempt['recovery_id']==recovery_id
                  and attempt['phase'] in ('ADMITTED','READBACK'),'RECOVERY_PENDING_ATTEMPT_REQUIRED')
            return self._append_recovery('HOLD',observed_ms,saved_head=asdict(self._head),observed_head=asdict(self._head),
                reason=reason,blocked_original_commands=[],selected=selected)


session_model=_load('publication_session')


@dataclass(frozen=True,slots=True)
class ReconciliationPermit:
    command_id:str
    digest:str
    recovery_id:str
    binding_sha256:str
    authority_epoch:int
    deadline_ms:int


class ReconciliationAuthority:
    """One registered grant/lease, bound once to one native recovery owner.

    Construct using ``session_model.PublicationSession`` exported by this module
    so class identity is exact across the addon's source-addressed loaders.
    Caller dictionaries, copied dataclasses and old publication credentials do
    not establish recovery authority.
    """
    def __init__(self,sessions,grant,lease):
        _need(type(sessions) is session_model.PublicationSession,'RECOVERY_SESSION_ISSUER_REQUIRED')
        _need(type(grant) is session_model.GodotGrant and type(lease) is session_model.GodotLease,
              'RECOVERY_REGISTERED_AUTHORITY_REQUIRED')
        self._sessions,self._grant,self._lease=sessions,grant,lease
        self._mutex=threading.RLock();self._permit=None;self._owner=None;self._next_phase=0;self._held=False
        self._encoded=self._binding=self._expected_head=None
        sessions.check(grant,lease,deadline_ms=min(_now()+30000,lease.expires_ms),operation='project.reconcile')

    @property
    def session_id(self):return self._grant.session_id

    def bind(self,owner,command_id,digest,*,deadline_ms):
        with self._mutex:
            _need(type(owner) is PublicationRecovery,'RECOVERY_OWNER_REQUIRED')
            _need(self._permit is None and not self._held,'RECOVERY_AUTHORITY_ALREADY_BOUND')
            _model.identifier(command_id);_model.hash_value(digest,revision=True)
            _need(type(deadline_ms) is int and _now()<deadline_ms<=_now()+30000,'RECOVERY_ADMISSION_DEADLINE')
            self._sessions.check(self._grant,self._lease,deadline_ms=deadline_ms,operation='project.reconcile')
            self._sessions.validate_public_identifier(command_id)
            snapshot,command,bundle,context=owner._inspection(command_id,digest)
            _need(command is not None,'RECOVERY_COMMAND_UNKNOWN')
            restorable_unknown=_restorable_unknown(snapshot,command,context['selected'])
            _need(command['phase']!='FAILED' and (command['phase']!='UNKNOWN' or restorable_unknown)
                  and not snapshot['stopped'] and (not snapshot['held'] or restorable_unknown),'RECOVERY_STOP_OR_UNKNOWN')
            _need(self._sessions.project_id==context['project_id'] and self._lease.fencing_epoch>context['minimum_authority_epoch'],
                  'RECOVERY_FRESH_AUTHORITY_EPOCH_REQUIRED')
            self._binding=canonical_bytes(context);self._expected_head=context['native_head']
            permit=ReconciliationPermit(command_id,digest,'reconcile-'+uuid.uuid4().hex,_sha(self._binding),
                self._lease.fencing_epoch,deadline_ms)
            self._permit=permit;self._encoded=canonical_bytes(asdict(permit));self._owner=owner
            return permit

    def _registered(self,permit):
        _need(type(permit) is ReconciliationPermit and self._permit is permit
              and canonical_bytes(asdict(permit))==self._encoded and not self._held,'RECOVERY_REGISTERED_PERMIT_REQUIRED')

    def _check_live(self,permit):
        with self._mutex:
            self._registered(permit)
            self._sessions.check(self._grant,self._lease,deadline_ms=permit.deadline_ms,operation='project.reconcile')

    def _check_context(self,permit):
        self._check_live(permit)
        actual=self._owner.authority_context();bound=parse_json(self._binding)
        _need(_same(actual['native_head'],self._expected_head),'RECOVERY_AUTHORITY_HEAD_CHANGED')
        for key in ('storage_id','project_id','source_closure_sha256','editor_engine_sha256','publication_prefix_sha256','selected'):
            _need(_same(actual[key],bound[key]),'RECOVERY_AUTHORITY_BINDING_CHANGED')
        return actual

    def _phase(self,permit,phase,effect):
        # Do not retain this wrapper/session lock across disk or editor I/O.
        with self._mutex:
            self._check_context(permit)
            _need(self._next_phase<3 and phase==('capture','adopt','commit')[self._next_phase],
                  'RECOVERY_PHASE_ALREADY_USED_OR_ORDER')
            ticket=self._sessions.reserve_phase(self._grant,self._lease,command_id=permit.command_id,digest=permit.digest,
                phase=phase,deadline_ms=permit.deadline_ms,operation='project.reconcile')
            try:self._sessions.start_effect(ticket)
            except BaseException:
                self._sessions.cancel_reserved(ticket)
                raise
            self._next_phase+=1
        try:
            result=effect()
            actual=self._owner.authority_context();bound=parse_json(self._binding)
            for key in ('storage_id','project_id','source_closure_sha256','editor_engine_sha256','publication_prefix_sha256','selected'):
                _need(_same(actual[key],bound[key]),'RECOVERY_AUTHORITY_BINDING_CHANGED')
            self._expected_head=actual['native_head']
        except BaseException:
            self._held=True
            self._sessions.finish_effect(ticket,known=False)
            raise
        self._sessions.finish_effect(ticket,known=True)
        return result

    def halt(self):
        self._held=True
        return self._sessions.halt()

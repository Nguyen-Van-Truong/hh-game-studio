"""Fresh read-only GUI from one verified committed owned checkpoint.

Internal readback only. No durable recovery receipt, write lease, original
command replay, arbitrary file input or public ACK. Caller owns publication;
this owner must close the fresh GUI before that read-only publication closes.
"""
import hashlib
import threading
from studio.protocol.core import canonical_bytes,parse_json
from .publication_owner import BlenderPublicationOwner,model
from .ui_host import BlenderUIHost,source_files,BLENDER_SHA256

SCHEMA='HH-BLENDER-CHECKPOINT-RECOVERY-1'
_LOCK=threading.Lock();_SEEDS={};MAX_SEEDS=4

class RecoveryError(ValueError):
    def __init__(self,code,*,cleanup_owner=None):
        self.code=code;self.cleanup_owner=cleanup_owner;super().__init__(code)

def need(value,code):
    if not value:raise RecoveryError(code)

class _Seed:
    __slots__=()

def _claim_seed(seed):
    # Private local registration, never a bootstrap/IPC authority object.
    with _LOCK:
        value=_SEEDS.pop(id(seed),None)
        need(value is not None and value[0] is seed,'RECOVERY_REGISTERED_SEED_REQUIRED')
        return value[1],parse_json(value[2])

def _retired(predecessor,generation):
    need(type(predecessor) is BlenderUIHost and predecessor._session==generation
        and predecessor._closed and predecessor._process is not None
        and predecessor._process.poll()==0,'RECOVERY_CLOSED_PREDECESSOR_REQUIRED')
    result=predecessor._cleanup
    need(result['closed'] is True and result['actual_process_exit']=={'pid':predecessor.pid,'exit_code':0}
        and result['wrapper_exit_code']==0 and result['job']['zero_observed'] is True
        and result['job']['active_count']==0 and result['job']['closed'] is True
        and result['job']['handle_retained'] is False,'RECOVERY_PREDECESSOR_EXIT_REQUIRED')

def _descriptor(publication,predecessor):
    need(type(publication) is BlenderPublicationOwner and publication._readonly
        and publication.host is None and publication.session is None and not publication._closed,
        'RECOVERY_READONLY_PUBLICATION_REQUIRED')
    manifest,artifacts=publication.read_selected()
    _retired(predecessor,manifest['generation'])
    current=source_files()
    need(manifest['source_files']==current and manifest['binary_sha256']==BLENDER_SHA256,
        'RECOVERY_PRODUCER_PIN_MISMATCH')
    state=publication._state;selector_version=state['terminal']['selector_version']
    need(state['terminal']['response']['status']=='COMMITTED','RECOVERY_COMMITTED_REQUIRED')
    context=state['intent']['request']['expected_context']
    need(context['mode']=='OBJECT','RECOVERY_OBJECT_MODE_REQUIRED')
    raw=artifacts['checkpoint.blend']
    need(0<len(raw)<=1024**2 and hashlib.sha256(raw).hexdigest()==manifest['native']['input_sha256'],
        'RECOVERY_CHECKPOINT_BINDING')
    descriptor={'schema':SCHEMA,'storage_id':publication.storage_id,'producer_generation':manifest['generation'],
        'checkpoint_sha256':hashlib.sha256(raw).hexdigest(),'selector_version':selector_version,
        'source_sha256':hashlib.sha256(canonical_bytes(current)).hexdigest(),'binary_sha256':BLENDER_SHA256,
        'revision':manifest['scene_revision'],'snapshot_native_json':manifest['snapshot_native_json'],
        'context':context,'profile':manifest['native']['profile'],'readonly':True,'public_ack':False}
    model.check_snapshot_wire(descriptor['snapshot_native_json'],manifest['snapshot'],descriptor['revision'])
    return raw,parse_json(canonical_bytes(descriptor))

def validate_observation(value,descriptor,*,pid,descriptor_sha256):
    model.exact(value,('schema','checkpoint_sha256','descriptor_sha256','source_sha256','revision',
        'snapshot_native_json','context','profile','pid','readonly','undo_history_restored','public_ack'))
    expected={key:descriptor[key] for key in ('schema','checkpoint_sha256','source_sha256','revision',
        'snapshot_native_json','context','profile','readonly','public_ack')}
    expected.update(pid=pid,descriptor_sha256=descriptor_sha256,undo_history_restored=False)
    need(canonical_bytes(value)==canonical_bytes(expected),'RECOVERY_NATIVE_READBACK_MISMATCH')

class CheckpointRecoveryOwner:
    def __init__(self):raise TypeError('use CheckpointRecoveryOwner.open')

    @classmethod
    def open(cls,parent,*,binary,publication,predecessor):
        raw,descriptor=_descriptor(publication,predecessor)
        owner=object.__new__(cls);owner._host=None;owner._closed=False;owner._held=False
        owner.publication=publication;owner.descriptor=canonical_bytes(descriptor);owner._count=0
        seed=_Seed()
        with _LOCK:
            need(len(_SEEDS)<MAX_SEEDS,'RECOVERY_SEED_CAPACITY')
            _SEEDS[id(seed)]=(seed,raw,owner.descriptor)
        try:
            owner._host=BlenderUIHost(parent,binary=binary,session_seconds=120,_recovery_seed=seed)
            validate_observation(owner._host._recovery_observation,descriptor,pid=owner._host.pid,
                descriptor_sha256=hashlib.sha256(owner.descriptor).hexdigest())
            owner.inspect()
            return owner
        except BaseException as error:
            if owner._host is None and type(getattr(error,'cleanup_owner',None)) is BlenderUIHost:
                owner._host=error.cleanup_owner
            owner._held=True
            try:owner.close()
            except BaseException:pass
            raise RecoveryError('RECOVERY_GUI_READBACK_HELD',cleanup_owner=owner) from error
        finally:
            with _LOCK:_SEEDS.pop(id(seed),None)

    def inspect(self):
        need(not self._closed and not self._held,'RECOVERY_OWNER_HELD_OR_CLOSED')
        descriptor=parse_json(self.descriptor)
        # Recheck the protected selected bundle before observing its consumer.
        manifest,_=self.publication.read_selected()
        need(manifest['native']['input_sha256']==descriptor['checkpoint_sha256']
            and self.publication._state['terminal']['selector_version']==descriptor['selector_version'],
            'RECOVERY_SELECTION_CHANGED')
        self._count+=1;need(self._count<=16,'RECOVERY_INSPECT_CAPACITY')
        request={'schema':'HH-BLENDER-UI-COMMAND-1','command_id':'recovery-read-'+str(self._count),
            'operation':'scene.inspect','expected_revision':None,'expected_context':None,'payload':{}}
        try:
            reply=self._host.execute(request);need(reply['state']=='COMPLETED','RECOVERY_INSPECT_INCOMPLETE')
            observed=reply['result']
            need(observed['revision']==descriptor['revision'] and observed['context']==descriptor['context']
                and canonical_bytes(observed['snapshot'])==canonical_bytes(parse_json(descriptor['snapshot_native_json'].encode())),
                'RECOVERY_LIVE_SCENE_CHANGED')
            return {'schema':SCHEMA,'storage_id':descriptor['storage_id'],'producer_generation':descriptor['producer_generation'],
                'consumer_generation':self._host._session,'pid':self._host.pid,'checkpoint_sha256':descriptor['checkpoint_sha256'],
                'selector_version':descriptor['selector_version'],'readback':parse_json(canonical_bytes(observed)),
                'live_scene_readback_verified':True,'recovery_durable':False,'new_edit_grant':False,
                'undo_history_restored':False,'public_ack':False}
        except BaseException:
            self._held=True;raise

    def stop(self):
        need(not self._closed,'RECOVERY_OWNER_CLOSED');self._held=True
        return self._host.stop()

    def close(self):
        if self._closed:return
        if self._host is not None:
            try:self._host.close()
            except BaseException as error:raise RecoveryError('RECOVERY_GUI_CLEANUP_HELD',cleanup_owner=self) from error
        self._closed=True

"""Trusted fixed Blender checkpoint/GLB publication on existing native primitives.

One publication per storage owner. Reopen is read-only; interrupted effects are
never replayed. The caller owns the GUI/session and closes this owner first.
"""
from pathlib import Path
import threading
import uuid
from studio.protocol.core import canonical_bytes,parse_json
from studio.host.core.custody import WitnessCustody,identity_from,identity_value
from studio.host.core.custody_registry import RegistryCustody
from studio.host.core.private_events import PrivateEventLog
from studio.host.core.private_store import PrivateBlobStore,MAX_BLOB_BYTES
from studio.host.core.safe_replace import ProtectedFileRoot
from studio.host.core.limits import SafePathResolver
from studio.host.core.journal import Lease
from . import publication_state as model
from .durable_session import DurableBlenderSession,queue,PROJECT,TARGET,epoch_ms
from .ui_host import BlenderUIHost,BLENDER_SHA256,source_files
from .export_job import ExportJob
from .deadline import AbsoluteDeadline
from .glb_preflight import inspect_glb,bind_snapshot

need=model.need

def descriptor(blob):
    return {'object_id':blob.object_id,'identity':identity_value(blob.identity),'sha256':blob.sha256}
def version(value):return {'identity':identity_value(value.identity),'sha256':value.sha256}

class BlenderPublicationOwner:
    def __init__(self):
        self.registry=self.custody=self.files=self.store=self.log=None
        self.session=self.host=None;self._job=None;self._extra=[]
        self._mutex=threading.RLock();self._stop=threading.Event();self._held=False;self._closed=False
        self._readonly=True;self._head=None;self._state={}

    @classmethod
    def create(cls,parent,*,session,profile='export.publish'):
        model.profile({'publication_profile':profile})
        need(type(session) is DurableBlenderSession and type(session.host) is BlenderUIHost,'PUBLICATION_OWNED_SESSION')
        SafePathResolver(parent);owner=cls();owner.session=session;owner.host=session.host
        try:
            need(source_files()==owner.host._source,'PUBLICATION_SOURCE_CHANGED')
            RegistryCustody.provision_base();owner.storage_id=uuid.uuid4().hex
            owner.registry=RegistryCustody.create(owner.storage_id)
            owner.custody=WitnessCustody(owner.registry,storage_id=owner.storage_id,project_id=model.PROJECT,create=True)
            owner.files=ProtectedFileRoot.create(parent)
            owner.store=PrivateBlobStore.create(parent);owner.log=PrivateEventLog.create(parent)
            owner.custody.activate(file_root=owner.files.root,file_identity=owner.files.root_identity,
                blob_root=owner.store.root,blob_identity=owner.store.root_identity,
                event_root=owner.log.root,event_binding=owner.log.binding())
            owner.log.bind_custody(owner.custody);owner._readonly=False;owner._head=owner.log.binding().witnessed
            owner._append('CONFIG',generation=owner.host._session,
                source_sha256=model.sha(canonical_bytes(owner.host._source)),binary_sha256=BLENDER_SHA256,
                publication_profile=profile)
            return owner
        except BaseException as error:owner._failed_init(error)

    @classmethod
    def reopen(cls,storage_id):
        owner=cls();owner.storage_id=storage_id
        try:
            owner.registry=RegistryCustody.reopen(storage_id)
            owner.custody=WitnessCustody(owner.registry,storage_id=storage_id,project_id=model.PROJECT)
            record=owner.custody.record;need(record['phase']=='READY','PUBLICATION_PROVISIONING_INCOMPLETE')
            owner.files=ProtectedFileRoot.reopen_readonly(record['files']['path'],identity_from(record['files']['identity']))
            owner.custody.confirm_current()
            owner.store=PrivateBlobStore.reopen(record['blobs']['path'],identity_from(record['blobs']['identity']))
            owner.log=PrivateEventLog.reopen(record['events']['path'],owner.custody.binding)
            owner.log.bind_custody(owner.custody)  # A suffix beyond witnessed custody is held, never replayed.
            owner._head=owner.log.binding().witnessed;owner._refresh()
            if owner._state['phase']=='TERMINAL' and owner._state['terminal']['response']['status']=='COMMITTED':
                owner.read_selected()
            return owner
        except BaseException as error:owner._failed_init(error)

    def _failed_init(self,error):
        extra=getattr(error,'cleanup_owner',None) or getattr(error,'cleanup_api',None)
        if extra is not None:self._extra.append(extra)
        try:self.close()
        except BaseException:pass
        raise model.PublicationError('PUBLICATION_OPEN_HELD',outcome_unknown=True,cleanup_owner=self) from error

    def _owners(self):
        need(not self._closed,'PUBLICATION_CLOSED')
        self.custody.confirm_current();record=self.custody.record
        need(record['storage_id']==self.storage_id and record['project_id']==model.PROJECT,'PUBLICATION_CUSTODY_BINDING')
        for key,resource in (('files',self.files),('blobs',self.store)):
            need(str(resource.root)==record[key]['path'] and resource.root_identity.same_file(identity_from(record[key]['identity'])),
                'PUBLICATION_ROOT_BINDING')
            with resource._mutex:resource._check(**({'mutation':False} if key=='files' else {}))
        binding=self.log.binding();saved=self.custody.binding
        need(str(self.log.root)==record['events']['path'] and binding.root.same_file(saved.root)
            and binding.stream.same_file(saved.stream) and binding.witnessed==saved.witnessed==self._head,
            'PUBLICATION_CUSTODY_HEAD')

    def _refresh(self):
        self._owners()
        def fold(state,row):
            if row.head.sequence==1:
                binding=self.custody.binding
                need(parse_json(row.event)=={'kind':'GENESIS','store_id':self.log.root.name,
                    'volume':str(binding.stream.volume),'file_id':binding.stream.file_id,
                    'root_file_id':binding.root.file_id},'PUBLICATION_GENESIS_BINDING')
                return state
            need(row.head.sequence<=8,'PUBLICATION_HISTORY_CAP')
            return model.reduce(state,parse_json(row.event))
        head,state=self.log.fold({},fold);need(head==self._head and state,'PUBLICATION_HISTORY_BINDING')
        self._state=state;return state

    def _append(self,kind,**fields):
        event=dict(schema=model.SCHEMA,kind=kind,**fields)
        expected=model.reduce(self._state,event)
        try:
            self._owners()
            self._head=self.log.append(event,self._head,reserve_records=7-self._head.sequence,
                reserve_bytes=(7-self._head.sequence)*17000)
            need(self._refresh()==expected,'PUBLICATION_EVENT_READBACK')
        except BaseException as error:
            self._held=True
            raise model.PublicationError('PUBLICATION_EVENT_UNKNOWN',outcome_unknown=True,cleanup_owner=self) from error

    def _authorize(self,lease):
        need(not self._readonly and not self._held and not self._stop.is_set() and not self._state.get('stopped'),
            'PUBLICATION_READONLY_OR_HELD')
        need(type(lease) is Lease and lease.project_id==PROJECT and lease.target==TARGET,'PUBLICATION_WRITER_REQUIRED')
        need(self.host is self.session.host and self.host._session==self._state['config']['generation']
            and not self.host._held and not self.host._stopped and source_files()==self.host._source
            and model.sha(canonical_bytes(self.host._source))==self._state['config']['source_sha256'],
            'PUBLICATION_HOST_GENERATION_OR_SOURCE')
        self.session.journal.check_running();self.session.journal.check_lease(lease,now_ms=epoch_ms())

    def _native(self,key,operation,lease,request=None,*,deadline_ms=None):
        command={'schema':queue.SCHEMA,'command_id':key,'operation':operation,
            'expected_revision':request['expected_revision'] if request else None,
            'expected_context':request['expected_context'] if request else None,
            'payload':{'slot':model.preparation(self._state['config'])[1]}
                if operation in ('export.prepare','checkpoint.save') else {}}
        options={'lease':{'fencing_epoch':lease.fencing_epoch,'expires_ms':lease.expires_ms}}
        if deadline_ms is not None:options['deadline_ms']=deadline_ms
        return self.host.execute(command,**options)

    def _owned_bytes(self,path,expected):
        # Native Blender/Python outputs inherit ACLs; they are not yet private
        # store objects. Pin their private owned directory and exact file bytes,
        # then copy into the protected primitive's independently checked files.
        need(self._job is not None and path.parent==self._job.directory
            and path.name in ('input.blend','output.glb'),'PUBLICATION_FIXED_CAPTURE_PATH')
        api=self.host._api;parent=api.open(path.parent,directory=True);handle=None
        try:
            parent_identity=api.inspect(parent,path.parent,directory=True);api.check_security(parent)
            handle=api.open(path);before=api.inspect(handle,path)
            need(0<before.size<=MAX_BLOB_BYTES,'PUBLICATION_ARTIFACT_CAP')
            raw=api.read(handle,MAX_BLOB_BYTES)
            need(before==api.inspect(handle,path) and len(raw)==before.size and model.sha(raw)==expected,
                'PUBLICATION_ARTIFACT_IDENTITY_OR_HASH')
            need(parent_identity.same_file(api.inspect(parent,path.parent,directory=True)),
                'PUBLICATION_CAPTURE_DIRECTORY_CHANGED')
            api.check_security(parent)
            return raw,identity_value(before)
        finally:
            if handle is not None:api.close(handle)
            api.close(parent)

    def _put(self,name,raw):
        stored=self.store.put_bytes(raw);need(self.store.read_blob(stored)==raw,'PUBLICATION_BLOB_READBACK')
        # The blob mirror has no per-entry namespace barrier. Publish the
        # canonical bytes through checked protected-file creation instead.
        durable=self.files.create_new(name,raw)
        observed,data=self.files.read(name)
        need(observed==durable and data==raw,'PUBLICATION_PROTECTED_BYTES_READBACK')
        return dict(descriptor(stored),file_version=version(durable))

    def _read_protected(self,name,value):
        model.blob(value)  # Validate staging provenance and durable version shape.
        observed,raw=self.files.read(name)
        need(version(observed)==value['file_version'] and model.sha(raw)==value['sha256'],
            'PUBLICATION_PROTECTED_VERSION_CHANGED')
        self.files.confirm_barrier(name,observed)
        return raw

    def lookup_bytes(self,command_id,request_sha256=None):
        queue.c.identifier(command_id)
        with self._mutex:
            state=self._refresh();intent=state.get('intent')
            if intent is None or intent['request']['command_id']!=command_id:return None
            need(request_sha256 is None or request_sha256==intent['request_sha256'],'PUBLICATION_COMMAND_CONFLICT')
            if state['phase']=='TERMINAL':return canonical_bytes(state['terminal']['response'])
            return canonical_bytes({'schema':model.SCHEMA,'command_id':command_id,'status':'UNKNOWN',
                'phase':state['phase'],'public_ack':False})

    def publish(self,request,lease,*,deadline_ms=None,phase_guard=None):
        request=model.validate_request(request);digest=model.sha(canonical_bytes(request));key=request['command_id']
        with self._mutex:
            previous=self.lookup_bytes(key,digest)
            if previous is not None:return previous
            need(self._state['phase']=='EMPTY','PUBLICATION_ONE_BUNDLE_CAPACITY')
            need(phase_guard is None or callable(phase_guard),'PUBLICATION_PHASE_GUARD_REQUIRED')
            budget=AbsoluteDeadline(deadline_ms,host_deadline=getattr(self.host,'_deadline',None))
            def check_phase():
                budget.check()
                self._authorize(lease)
                if phase_guard is not None:phase_guard()
                budget.check()
                need(not self._stop.is_set() and not self.host._stopped,'PUBLICATION_READONLY_OR_HELD')
            check_phase();self.files.check_mutation_available()
            need({p.name for p in self.files.root.iterdir()}=={'.writer'},'PUBLICATION_INITIAL_NAMESPACE')
            check_phase()
            self._append('INTENT',request=request,request_sha256=digest,lease_epoch=lease.fencing_epoch)
            try:
                check_phase()
                token='pub-'+digest[:20]
                operation,slot=model.preparation(self._state['config'])
                prepared=self._native(token,operation,lease,request,deadline_ms=deadline_ms)
                check_phase()
                if prepared['state']=='REJECTED':
                    result=model.response(self._state['intent'],reason='NATIVE_PREPARE_REJECTED')
                    self._append('TERMINAL',response=result,response_sha256=model.sha(canonical_bytes(result)),selector_version=None)
                    return self.lookup_bytes(key,digest)
                need(prepared['state']=='COMPLETED','PUBLICATION_NATIVE_PREPARE_UNKNOWN')
                prepared=prepared['result'];check_phase()
                options={}
                if slot!='export':options['input_name']=slot+'.blend'
                if deadline_ms is not None:options['deadline_ms']=deadline_ms
                if deadline_ms is not None or phase_guard is not None:options['phase_guard']=check_phase
                self._job=ExportJob(self.host,prepared,**options);export=self._job.run()
                check_phase()
                need(export['completed'] is True and export['snapshot_geometry_bound'] is True,'PUBLICATION_EXPORT_UNKNOWN')
                job=self._job
                blend,input_identity=self._owned_bytes(job.directory/'input.blend',prepared['artifact']['sha256'])
                glb,_=self._owned_bytes(job.directory/'output.glb',export['artifact']['sha256'])
                snapshot=prepared['after']['snapshot'];preflight=inspect_glb(glb);bind_snapshot(preflight,snapshot)
                need(export['native']['snapshot']==snapshot and export['native']['scene_revision']==request['expected_revision']
                    ,'PUBLICATION_NATIVE_SNAPSHOT')
                snapshot_text=model.snapshot_wire(export['native']['snapshot'],request['expected_revision'])
                check_phase()
                after=self._native(token+'-after','scene.inspect',lease,deadline_ms=deadline_ms)
                need(after['state']=='COMPLETED' and after['result']==prepared['after'],'PUBLICATION_SCENE_CHANGED_DURING_EXPORT')
                check_phase()
                artifacts={}
                for name,raw in zip(model.NAMES,(blend,glb)):
                    check_phase();artifacts[name]=self._put(name,raw)
                manifest={'schema':model.SCHEMA,'command_id':key,'request_sha256':digest,
                    'generation':self.host._session,'scene_revision':request['expected_revision'],'snapshot':snapshot,
                    'snapshot_native_json':snapshot_text,
                    'artifacts':artifacts,'source_files':self.host._source,'binary_sha256':BLENDER_SHA256,
                    'license':'original-fixture','external_inputs':[],'input_identity':input_identity,
                    'native':{'input_sha256':model.sha(blend),'glb_sha256':model.sha(glb),
                        'profile':export['native']['profile'],'main_thread_save':True,'background_reopen':True},
                    'public_ack':False}
                if 'publication_profile' in self._state['config']:
                    manifest['publication_profile']=model.profile(self._state['config'])
                check_phase();staged=self._put('manifest.json',canonical_bytes(manifest))
                check_phase()
                self._append('STAGED',command_id=key,request_sha256=digest,manifest=staged,artifacts=artifacts)
                check_phase()
                self._read_bundle(self._state['staged'])
                check_phase();selected=model.selection(self._state['staged'])
                self._append('SELECTING',selector=selected);check_phase()
                observed=self.files.create_new('active.json',canonical_bytes(selected))
                actual,raw=self.files.read('active.json')
                need(actual==observed and raw==canonical_bytes(selected),'PUBLICATION_SELECTOR_READBACK')
                self.files.confirm_barrier('active.json',actual);self._read_bundle(self._state['staged'])
                check_phase()
                result=model.response(self._state['intent'],self._state['staged'],selected)
                self._append('TERMINAL',response=result,response_sha256=model.sha(canonical_bytes(result)),selector_version=version(actual))
                return self.lookup_bytes(key,digest)
            except BaseException as error:
                self._held=True
                raise model.PublicationError('PUBLICATION_OUTCOME_UNKNOWN',outcome_unknown=True,cleanup_owner=self) from error

    def publish_save(self,command,lease,*,deadline_ms=None,phase_guard=None):
        request=model.save_request(command,model.profile(self._state['config']))
        return self.publish(request,lease,deadline_ms=deadline_ms,phase_guard=phase_guard)

    def _read_bundle(self,staged):
        raw=self._read_protected('manifest.json',staged['manifest']);manifest=parse_json(raw)
        need(raw==canonical_bytes(manifest),'PUBLICATION_MANIFEST_CANONICAL')
        fields={'schema','command_id','request_sha256','generation','scene_revision','snapshot','snapshot_native_json','artifacts',
            'source_files','binary_sha256','license','external_inputs','input_identity','native','public_ack'}
        if 'publication_profile' in self._state['config']:
            fields.add('publication_profile')
            need(manifest.get('publication_profile')==model.profile(self._state['config']),'PUBLICATION_MANIFEST_PROFILE')
        model.exact(manifest,fields)
        config=self._state['config'];intent=self._state['intent']
        need(manifest['schema']==model.SCHEMA and manifest['artifacts']==staged['artifacts']
            and manifest['command_id']==staged['command_id'] and manifest['request_sha256']==intent['request_sha256']
            and manifest['generation']==config['generation'] and manifest['binary_sha256']==config['binary_sha256']
            and model.sha(canonical_bytes(manifest['source_files']))==config['source_sha256']
            and manifest['scene_revision']==intent['request']['expected_revision']
            and manifest['public_ack'] is False and manifest['external_inputs']==[]
            and manifest['license']=='original-fixture','PUBLICATION_MANIFEST_BINDING')
        model.check_snapshot_wire(manifest['snapshot_native_json'],manifest['snapshot'],manifest['scene_revision'])
        data={name:self._read_protected(name,value) for name,value in staged['artifacts'].items()}
        model.exact(manifest['native'],('input_sha256','glb_sha256','profile','main_thread_save','background_reopen'))
        need(manifest['native']['input_sha256']==model.sha(data['checkpoint.blend'])
            and manifest['native']['glb_sha256']==model.sha(data['scene.glb'])
            and manifest['native']['main_thread_save'] is True and manifest['native']['background_reopen'] is True,
            'PUBLICATION_NATIVE_HASH_BINDING')
        identity=identity_from(manifest['input_identity']);need(identity.size==len(data['checkpoint.blend']),'PUBLICATION_INPUT_IDENTITY')
        bind_snapshot(inspect_glb(data['scene.glb']),manifest['snapshot'])
        return manifest,data

    def read_selected(self):
        with self._mutex:
            state=self._refresh();need(state['phase']=='TERMINAL' and state['terminal']['response']['status']=='COMMITTED',
                'PUBLICATION_NOT_COMMITTED')
            actual,raw=self.files.read('active.json')
            need(version(actual)==state['terminal']['selector_version'] and raw==canonical_bytes(state['selector']),
                'PUBLICATION_SELECTOR_CHANGED')
            self.files.confirm_barrier('active.json',actual)
            return self._read_bundle(state['staged'])

    def request_stop(self):
        self._stop.set()
        if self._job is not None:self._job.request_stop()

    def stop(self):
        self.request_stop()
        if self.session is not None:self.session.stop()
        with self._mutex:
            self._refresh()
            if not self._state['stopped']:self._append('STOP')
        return {'stopped':True,'public_ack':False}

    def close(self):
        self._stop.set()
        if self._job is not None:self._job.request_stop()
        with self._mutex:
            if self._job is not None:
                if not self._job.done.is_set():
                    raise model.PublicationError('PUBLICATION_EXPORT_ACTIVE',outcome_unknown=True,cleanup_owner=self)
                try:self._job.retry_cleanup()
                except BaseException as error:
                    raise model.PublicationError('PUBLICATION_EXPORT_CLEANUP_HELD',outcome_unknown=True,cleanup_owner=self) from error
                self._job=None
            for name in ('log','store','files','registry'):
                resource=getattr(self,name)
                if resource is None:continue
                try:resource.close()
                except BaseException as error:
                    raise model.PublicationError('PUBLICATION_CLOSE_HELD',outcome_unknown=True,cleanup_owner=self) from error
                setattr(self,name,None)
            pending=[]
            for resource in self._extra:
                try:resource.close_owned() if hasattr(resource,'close_owned') else resource.close()
                except BaseException:pending.append(resource)
            self._extra=pending
            if pending:raise model.PublicationError('PUBLICATION_EXTRA_CLEANUP_HELD',outcome_unknown=True,cleanup_owner=self)
            self._closed=True

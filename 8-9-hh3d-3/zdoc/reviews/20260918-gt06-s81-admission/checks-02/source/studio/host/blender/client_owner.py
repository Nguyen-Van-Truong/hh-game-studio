"""Authenticated read observations for one registered live owned Blender GUI.

Only this facade's bounded volatile responses can be looked up. No writer,
private receipt import, publication, restart adoption or durable recovery ACK.
"""
import hashlib
import re
import secrets
import threading
import time
import weakref
from studio.protocol.core import Request,Response,Status,ValidationError,canonical_bytes,parse_json
from studio.host.core.limits import SafetyViolation
from studio.host.core.transport import epoch_ms
from .ui_host import BlenderUIHost,source_files,BLENDER_SHA256,load
from .client_session import BlenderClientSession,need
from . import client_catalog as catalog

_OWNERS=weakref.WeakKeyDictionary();_REGISTER=threading.Lock()
queue=load('blender-addon/ui_queue.py')

def digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()

def shape(body,keys):
    need(type(body) is dict and set(body)==set(keys),'BLENDER_INVALID_ENVELOPE')

def response(status,code,key,**postconditions):
    return Response(status,code,key,postconditions={'public_ack':False,'durable':False,'read_only':True,**postconditions})

class BlenderClientOwner:
    def __init__(self):raise TypeError('use BlenderClientOwner.from_host')

    @classmethod
    def from_host(cls,host,*,project_id='blender.owned-fixture'):
        need(type(host) is BlenderUIHost,'BLENDER_EXACT_HOST_REQUIRED')
        owner=object.__new__(cls);owner._host=host;owner._process=host._process;owner._job=host._job
        owner._mutex=threading.RLock();owner._records={};owner._active=None;owner._held=False
        owner._stop_response=None;owner._stop_pending=False
        owner._prefix='client-'+secrets.token_hex(8);owner._counter=0
        owner._source=canonical_bytes(source_files());owner._source_sha256=digest(owner._source)
        owner._pin=canonical_bytes({'pid':host.pid,'generation':host._session,'binary_sha256':BLENDER_SHA256})
        owner._deadline=host._deadline
        owner.project_id=project_id;owner.catalog_digest=catalog.CATALOG_DIGEST
        owner._check_native()
        remaining=int((owner._deadline-time.monotonic())*1000)
        need(remaining>0,'BLENDER_OWNER_EXPIRED')
        owner.sessions=BlenderClientSession(project_id,host.directory,owner_deadline_ms=epoch_ms()+remaining)
        with _REGISTER:
            need(host not in _OWNERS,'BLENDER_HOST_ALREADY_REGISTERED')
            _OWNERS[host]=weakref.ref(owner)
        try:
            observed=owner._read_native(owner._prefix+'-registration',epoch_ms()+min(remaining,catalog.MAX_READ_MS))
            owner._baseline=canonical_bytes(observed);owner.revision=observed['revision']
            owner._check_native()
            return owner
        except BaseException:
            with _REGISTER:
                if _OWNERS.get(host) is not None and _OWNERS[host]() is owner:del _OWNERS[host]
            raise

    def _check_native(self,*,control=False):
        host=self._host
        need(type(host) is BlenderUIHost and host._process is self._process and host._job is self._job
            and host._process is not None and host._process.poll() is None and not host._closed,
            'BLENDER_LIVE_OWNER_REQUIRED')
        need(canonical_bytes({'pid':host.pid,'generation':host._session,'binary_sha256':BLENDER_SHA256})==self._pin
            and type(host.pid) is int and host.pid>0 and re.fullmatch(r'[0-9a-f]{32}',host._session)
            and host._deadline==self._deadline,'BLENDER_OWNER_IDENTITY_CHANGED')
        active=host._job.active_count();job=host._job.snapshot()
        need(job['assigned'] is True and job['configured'] is True and job['tainted'] is False
            and job['closed'] is False and job['handle_retained'] is True and type(active) is int
            and active>=2 and job['active_count']==active,
            'BLENDER_LIVE_JOB_REQUIRED')
        if not control:
            need(not host._held and not host._stopped and not self._held,'BLENDER_OWNER_HELD_OR_STOPPED')
            need(time.monotonic()<self._deadline,'BLENDER_OWNER_EXPIRED')
            need(canonical_bytes(host._source)==self._source==canonical_bytes(source_files()),'BLENDER_SOURCE_CHANGED')

    def _auth(self,body,authorization,catalog_digest,operation=None,keys=None):
        if keys is not None:shape(body,keys)
        need(type(body) is dict,'BLENDER_INVALID_ENVELOPE')
        grant=self.sessions.authenticate(authorization)
        need(body.get('project_id')==self.project_id and catalog_digest==self.catalog_digest,'BLENDER_GRANT_BINDING')
        if operation is not None:
            grant=self.sessions.authorize(authorization,operation,project_id=self.project_id,catalog_digest=catalog_digest)
        return grant

    def discover(self,body,*,authorization,catalog_digest):
        grant=self._auth(body,authorization,catalog_digest,keys={'project_id'})
        self._check_native(control=self.sessions._stopped.is_set())
        return catalog.discovery(self.project_id,source_sha256=self._source_sha256,
            readable=catalog.READ in grant.operations and not self.sessions._stopped.is_set())

    def lease(self,body,*,authorization,catalog_digest):
        grant=self._auth(body,authorization,catalog_digest,catalog.READ,{'project_id','ttl_ms','access'})
        need(body['access']=='read','BLENDER_READ_ONLY');self._check_native()
        lease=self.sessions.read_lease(grant,ttl_ms=body['ttl_ms'])
        return {'lease_id':lease.lease_id,'fencing_epoch':0,'expires_ms':lease.expires_ms,'access':'read',
            'revision':self.revision,'target':{'stable_id':catalog.TARGET},'catalog_digest':self.catalog_digest,
            'public_ack':False,'durable':False}

    def _read_native(self,key,deadline_ms):
        command={'schema':'HH-BLENDER-UI-COMMAND-1','command_id':key,'operation':catalog.READ,
            'expected_revision':None,'expected_context':None,'payload':{}}
        def remaining():
            value=min(deadline_ms-epoch_ms(),int((self._deadline-time.monotonic())*1000))
            need(value>0,'BLENDER_DEADLINE_EXPIRED');return value
        self._check_native()
        row=self._host.submit(command,ttl_ms=remaining())
        while row.get('state')=='PENDING':
            need(not self.sessions._stopped.is_set(),'BLENDER_STOPPED')
            timeout=remaining()/1000
            row=self._host._ask('control','result',{'command_id':key},timeout=min(2,timeout))
            if row.get('state')=='PENDING':time.sleep(min(.005,remaining()/1000))
        need(row.get('state')=='COMPLETED' and row.get('command_id')==key
            and row.get('command_digest')==queue.c.digest(command) and row.get('public_ack') is False,
            'BLENDER_NATIVE_READBACK_UNKNOWN')
        observed=row['result']
        shape(observed,{'snapshot','revision','context','public_ack','undo_supported'})
        need(observed['public_ack'] is False and observed['undo_supported'] is True
            and type(observed['revision']) is str and re.fullmatch(r'sha256:[0-9a-f]{64}',observed['revision']),
            'BLENDER_NATIVE_READBACK_UNKNOWN')
        shape(observed['context'],{'mode','active_id','selected_ids'})
        need(observed['context']['mode'] in ('OBJECT','EDIT_MESH'),'BLENDER_NATIVE_READBACK_UNKNOWN')
        encoded=canonical_bytes(observed);need(len(encoded)<=catalog.MAX_WIRE//2,'BLENDER_READBACK_CAP')
        remaining();self._check_native()
        return parse_json(encoded)

    def submit(self,body,*,authorization,catalog_digest):
        grant=self._auth(body,authorization,catalog_digest)
        key=body.get('command_id','transport.request');self.sessions.validate_public_identifier(key)
        try:
            request=Request.from_dict(body)
            identity=(grant.session_id,key)
            with self._mutex:
                old=self._records.get(identity)
                if old is not None:
                    if old['digest']!=request.digest:return response(Status.REJECTED,'COMMAND_CONFLICT',key)
                    return Response.from_dict(parse_json(old['wire']))
            request=catalog.validate_request(body,project_id=self.project_id,source_sha256=self._source_sha256)
            self.sessions.authorize(authorization,catalog.READ,project_id=self.project_id,catalog_digest=catalog_digest)
        except (ValidationError,SafetyViolation) as error:
            return response(Status.REJECTED,error.code,key)
        identity=(grant.session_id,key)
        with self._mutex:
            old=self._records.get(identity)
            if old is not None:
                if old['digest']!=request.digest:return response(Status.REJECTED,'COMMAND_CONFLICT',key)
                return Response.from_dict(parse_json(old['wire']))
            if self._active is not None:return response(Status.REJECTED,'BLENDER_READ_BUSY',key)
            if len(self._records)>=catalog.MAX_COMMANDS:return response(Status.REJECTED,'BLENDER_COMMAND_LIMIT',key)
            pending=response(Status.ACCEPTED_PENDING,'BLENDER_READ_PENDING',key)
            self._records[identity]={'digest':request.digest,'wire':canonical_bytes(pending.as_dict())}
            self._active=identity;self._counter+=1;native_key=self._prefix+'-'+str(self._counter)
        permit=None
        try:
            self._check_native()
            need(request.expected_revision==parse_json(self._baseline)['revision'],'BLENDER_STALE_REVISION')
            lease=self.sessions.resolve_lease(grant,request.lease_id,request.fencing_epoch)
            permit=self.sessions.start_read(grant,lease,deadline_ms=request.deadline_ms)
            try:
                observed=self._read_native(native_key,request.deadline_ms)
            except Exception:
                # A read may still be pending at the native boundary. Keep
                # admission held rather than release another native read.
                self._held=True
                raise
            self.sessions.check_read(grant,lease,deadline_ms=request.deadline_ms)
            need(observed['revision']==request.expected_revision and canonical_bytes(observed)==self._baseline,
                'BLENDER_STALE_REVISION')
            self._check_native()
            # The authenticated native revision is preserved verbatim. The hash
            # is of these named JCS observation bytes, not Blender float JSON.
            observation={'native_revision':observed['revision'],'scene':observed,'pid':self._host.pid,
                'generation':self._host._session,'source_sha256':self._source_sha256}
            result=Response(Status.COMMITTED,'BLENDER_READ_CONFIRMED',key,observed['revision'],
                digest(canonical_bytes(observation)),{'observation':observation,'hash_domain':'jcs-observation-v1',
                    'public_ack':False,'durable':False,'read_only':True})
            raw=canonical_bytes(result.as_dict())
            need(len(raw)<=catalog.MAX_WIRE,'BLENDER_RESPONSE_CAP')
            detached=Response.from_dict(parse_json(raw))
            self._check_native()
            # No native wait or response construction inside the publication
            # guard. Stop/revoke and successful new read publication have one
            # ordering; a later lookup may still return a historical result.
            with self.sessions.publish_read(grant,lease,deadline_ms=request.deadline_ms):
                need(self.sessions.encode_output(result.as_dict())==raw,'BLENDER_SENSITIVE_OBSERVATION')
                self.sessions.check_read(grant,lease,deadline_ms=request.deadline_ms)
                with self._mutex:
                    self.sessions.finish_read(permit);permit=None
                    self._records[identity]['wire']=raw;self._active=None
            return detached
        except (SafetyViolation,ValidationError) as error:
            stopped=self.sessions._stopped.is_set()
            result=response(Status.CANCELED if stopped else Status.REJECTED,'BLENDER_STOPPED' if stopped else error.code,key)
        except Exception:
            self._held=True;result=response(Status.UNKNOWN,'BLENDER_NATIVE_READBACK_UNKNOWN',key)
        finally:
            if permit is not None:self.sessions.finish_read(permit)
        raw=canonical_bytes(result.as_dict())
        with self._mutex:
            self._records[identity]['wire']=raw;self._active=None
        return Response.from_dict(parse_json(raw))

    def lookup(self,body,*,authorization,catalog_digest):
        grant=self._auth(body,authorization,catalog_digest,'control.lookup',{'project_id','command_id'})
        self.sessions.validate_public_identifier(body['command_id'])
        with self._mutex:
            row=self._records.get((grant.session_id,body['command_id']))
            if row is None:return response(Status.REJECTED,'COMMAND_NOT_FOUND',body['command_id'])
            return Response.from_dict(parse_json(row['wire']))

    def stop(self,body,*,authorization,catalog_digest):
        grant=self._auth(body,authorization,catalog_digest,'control.stop',{'project_id','command_id'})
        key=body['command_id'];self.sessions.validate_public_identifier(key)
        state=self.sessions.stop(grant)
        with self._mutex:
            if self._stop_response is not None:
                value=parse_json(self._stop_response);value['command_id']=key;return Response.from_dict(value)
            if self._stop_pending:return response(Status.ACCEPTED_PENDING,'BLENDER_STOP_PENDING',key,**state)
            self._stop_pending=True
        try:
            self._check_native(control=True)
            native=self._host.stop()
            need(native=={'stopped':True,'public_ack':False},'BLENDER_STOP_UNKNOWN')
            result=response(Status.COMMITTED,'BLENDER_STOP_OBSERVED',key,**state)
        except Exception:
            result=response(Status.UNKNOWN,'BLENDER_STOP_UNKNOWN',key,**state)
        with self._mutex:
            self._stop_response=canonical_bytes(result.as_dict());self._stop_pending=False
        return result

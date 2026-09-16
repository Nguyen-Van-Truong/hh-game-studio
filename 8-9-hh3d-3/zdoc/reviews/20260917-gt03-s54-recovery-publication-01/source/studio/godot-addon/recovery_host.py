"""Authenticated, single-attempt recovery host; never reopens a writable project.

The separate endpoint consumes a new registered authority and returns durable
responses for the original command. No path or original bearer is accepted as
recovery authority. Stop has its own bounded listener and in-memory latch.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import importlib.util
from pathlib import Path
import re
import sys
import threading

from studio.host.core.limits import SafetyViolation
from studio.host.core.transport import epoch_ms
from studio.protocol.core import Response,Status,canonical_bytes,parse_json

HERE=Path(__file__).resolve().parent


def _load(name):
    path=HERE/(name+'.py');raw=path.read_bytes()
    key='_hh_recovery_host_'+hashlib.sha256(str(path).encode()+b'\0'+raw).hexdigest()
    if key not in sys.modules:
        spec=importlib.util.spec_from_file_location(key,path)
        module=importlib.util.module_from_spec(spec);sys.modules[key]=module
        try:exec(compile(raw,str(path),'exec'),module.__dict__)
        except BaseException:
            del sys.modules[key];raise
    return sys.modules[key]


CATALOG={'schema':'hh-godot-recovery-catalog-1','operation':'project.reconcile',
    'scope':'godot.fixture','path':'/v1/reconcile','max_deadline_ms':30000,
    'new_mutation_permitted':False,'project_files_read_only':True,
    'request_fields':['project_id','command_id','digest','lease_id','fencing_epoch','deadline_ms']}
CATALOG_DIGEST='sha256:'+hashlib.sha256(canonical_bytes(CATALOG)).hexdigest()
GRANTS=frozenset({'project.reconcile','control.lookup','control.stop'})


class RecoveryHostError(SafetyViolation):
    def __init__(self,code,*,cleanup_owner=None):
        self.cleanup_owner=cleanup_owner
        super().__init__(code)


def _need(value,code):
    if not value:raise RecoveryHostError(code)


class RecoveryTransport(_load('publication_transport').PublicationTransport):
    work_routes={'/v1/discovery':'discover','/v1/lease':'lease','/v1/reconcile':'reconcile'}


class GodotRecoveryHost:
    def __init__(self):raise TypeError('use open')

    @classmethod
    def open(cls,parent:Path,*,storage_id,project_id,expected_source_closure_sha256,editor_binary:Path):
        _need(parent.is_absolute() and parent.is_dir(),'GODOT_OWNED_PARENT_REQUIRED')
        value=object.__new__(cls)
        value._lock=threading.RLock();value._work=threading.Lock()
        value._closed=value._held=False;value._attempt=None;value._lease=None
        value._recovery=None;value._cleanup=[];value.sessions=None
        value.project_id=project_id;value._binary=editor_binary
        value.model=_load('publication_recovery')
        try:
            value._editor_parent=parent/'recovery-editor';value._editor_parent.mkdir(exist_ok=False)
            value._recovery=value.model.PublicationRecovery.open(storage_id,project_id=project_id,
                expected_source_closure_sha256=expected_source_closure_sha256)
            context=value._recovery.authority_context()
            value.sessions=value.model.session_model.PublicationSession(project_id,parent,CATALOG_DIGEST,
                minimum_fencing_epoch=context['minimum_authority_epoch'])
            value._restore_terminal()
            return value
        except BaseException as error:
            retained=getattr(error,'cleanup_owner',None)
            if retained is not None and retained is not value:value._cleanup.append(retained)
            try:value.close()
            except BaseException as cleanup:
                raise RecoveryHostError('RECOVERY_HOST_OPEN_CLEANUP',cleanup_owner=value) from cleanup
            raise

    def _auth(self,body,operation,authorization,catalog_digest,keys):
        _need(type(body) is dict and set(body)==keys,'GODOT_INVALID_ENVELOPE')
        _need(not self._closed,'GODOT_OWNER_CLOSED')
        return self.sessions.authorize(authorization,operation,
            project_id=body['project_id'],catalog_digest=catalog_digest)

    def discover(self,body,*,authorization,catalog_digest):
        self._auth(body,'project.reconcile',authorization,catalog_digest,{'project_id'})
        return {**CATALOG,'catalog_digest':CATALOG_DIGEST,'project_id':self.project_id,
            'runtime_enabled':not self._held and not self.sessions.status()['stopped'],
            'public_ack':False}

    def lease(self,body,*,authorization,catalog_digest):
        grant=self._auth(body,'project.reconcile',authorization,catalog_digest,{'project_id','ttl_ms'})
        _need(type(body['ttl_ms']) is int and 0<body['ttl_ms']<=30000,'GODOT_INVALID_LEASE')
        with self._lock:
            _need(not self._held and self._attempt is None,'RECOVERY_ATTEMPT_ALREADY_OWNED')
            self._lease=self.sessions.lease(grant,ttl_ms=body['ttl_ms'])
            return asdict(self._lease)

    def _terminal(self,command,digest):
        raw=self._recovery._journal.recovered_response(command,digest)
        _need(type(raw) is bytes,'RECOVERY_DURABLE_RESPONSE_REQUIRED')
        response=Response.from_dict(parse_json(raw))
        _need(canonical_bytes(response.as_dict())==raw and response.command_id==command,
              'RECOVERY_DURABLE_RESPONSE_MISMATCH')
        return response

    def _restore_terminal(self):
        """Read verified custody first; a fresh process is not fresh work."""
        snapshot=self._recovery._journal.snapshot()
        attempts=snapshot.get('recovery',{}).get('attempts',[])
        if attempts and attempts[-1]['phase']=='TERMINAL':
            latest=attempts[-1]
            self._terminal(latest['command_id'],latest['digest'])
            self._attempt=(latest['command_id'],latest['digest'],'TERMINAL')

    def reconcile(self,body,*,authorization,catalog_digest):
        grant=self._auth(body,'project.reconcile',authorization,catalog_digest,set(CATALOG['request_fields']))
        command,digest=body['command_id'],body['digest']
        self.sessions.validate_public_identifier(command)
        _need(type(digest) is str and re.fullmatch('sha256:[0-9a-f]{64}',digest),'RECOVERY_INVALID_DIGEST')
        with self._lock:
            if self._attempt is not None:
                _need((command,digest)==self._attempt[:2],'RECOVERY_COMMAND_CONFLICT')
                return self._reply()
            _need(not self._held,'RECOVERY_HOST_HELD')
            lease=self._lease
            _need(lease is not None and body['lease_id']==lease.lease_id
                and type(body['fencing_epoch']) is int and body['fencing_epoch']==lease.fencing_epoch,
                'GODOT_STALE_LEASE')
            deadline=body['deadline_ms']
            _need(type(deadline) is int and epoch_ms()<deadline<=epoch_ms()+30000,'GODOT_DEADLINE_EXPIRED')
            self.sessions.check(grant,lease,deadline_ms=deadline,operation='project.reconcile')
            _need(self._work.acquire(blocking=False),'GODOT_OWNER_BUSY')
            self._attempt=(command,digest,'PENDING')
        try:
            authority=self.model.ReconciliationAuthority(self.sessions,grant,lease)
            self._recovery.reconcile(authority,command,digest,editor_parent=self._editor_parent,
                editor_binary=self._binary,deadline_ms=deadline)
            response=self._terminal(command,digest)
            with self._lock:self._attempt=(command,digest,'TERMINAL')
            return response
        except BaseException as error:
            self._held=True;self.sessions.halt();self._last_error=error
            retained=getattr(error,'cleanup_owner',None)
            if retained is not None and retained not in (self,self._recovery):self._cleanup.append(retained)
            # A lost return after a durable terminal is not a second execution.
            try:
                response=self._terminal(command,digest)
                with self._lock:self._attempt=(command,digest,'TERMINAL')
            except Exception:
                with self._lock:self._attempt=(command,digest,'UNKNOWN')
                response=Response(Status.UNKNOWN,'GODOT_RECOVERY_RECONCILE_REQUIRED',command,
                    postconditions={'request_digest':digest,'public_ack':False,'new_mutation_permitted':False})
            if isinstance(error,(KeyboardInterrupt,SystemExit)):raise
            return response
        finally:self._work.release()

    def _reply(self):
        command,digest,state=self._attempt
        if state=='TERMINAL':
            try:return self._terminal(command,digest)
            except Exception:
                self._held=True;self.sessions.halt()
        return Response(Status.ACCEPTED_PENDING if state=='PENDING' else Status.UNKNOWN,
            'GODOT_RECOVERY_PENDING' if state=='PENDING' else 'GODOT_RECOVERY_RECONCILE_REQUIRED',command,
            postconditions={'request_digest':digest,'public_ack':False,'new_mutation_permitted':False})

    def lookup(self,body,*,authorization,catalog_digest):
        self._auth(body,'control.lookup',authorization,catalog_digest,{'project_id','command_id'})
        self.sessions.validate_public_identifier(body['command_id'])
        with self._lock:
            if self._attempt is not None and self._attempt[0]==body['command_id']:return self._reply()
        command=self._recovery._journal.lookup(body['command_id'])
        if command is not None:
            raw=self._recovery.original_response(body['command_id'],command['digest'])
            if raw is not None:
                response=Response.from_dict(parse_json(raw))
                _need(canonical_bytes(response.as_dict())==raw and response.command_id==body['command_id'],
                      'RECOVERY_DURABLE_RESPONSE_MISMATCH')
                return response
        return Response(Status.UNKNOWN,'GODOT_RECOVERY_NOT_REQUESTED',body['command_id'])

    def stop(self,body,*,authorization,catalog_digest):
        grant=self._auth(body,'control.stop',authorization,catalog_digest,{'project_id','command_id'})
        self.sessions.validate_public_identifier(body['command_id'])
        return self.sessions.stop(grant)

    def close(self):
        self._closed=True
        if self.sessions is not None:self.sessions.halt()
        if not self._work.acquire(timeout=2):
            raise RecoveryHostError('GODOT_OWNER_WORK_DRAIN_REQUIRED',cleanup_owner=self)
        try:
            while self._cleanup:
                self._cleanup[0].close();self._cleanup.pop(0)
            if self._recovery is not None:
                self._recovery.close();self._recovery=None
        except BaseException as error:
            raise RecoveryHostError('RECOVERY_HOST_CLOSE_REQUIRED',cleanup_owner=self) from error
        finally:self._work.release()

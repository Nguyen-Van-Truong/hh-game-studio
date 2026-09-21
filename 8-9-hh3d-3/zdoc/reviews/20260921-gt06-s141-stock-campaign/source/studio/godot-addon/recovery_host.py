"""Authenticated, single-attempt recovery host; never reopens a writable project.

The separate endpoint consumes a new registered authority and returns durable
responses for the original command. No path or original bearer is accepted as
recovery authority. Stop latches immediately; an owned drain persists it in
the same recovery stream before it is reported durable.
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
        value._stop_thread=None;value._stop_persistence='NOT_REQUESTED';value._durable_stopped=False
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
            'runtime_enabled':not self._held and not self.sessions.status()['stopped']
                and not getattr(self,'_durable_stopped',False) and self._attempt is None,
            'durable_stopped':getattr(self,'_durable_stopped',False),
            'stop_persistence':getattr(self,'_stop_persistence','NOT_REQUESTED'),
            'max_attempts_per_host':1,
            'public_ack':False}

    def lease(self,body,*,authorization,catalog_digest):
        grant=self._auth(body,'project.reconcile',authorization,catalog_digest,{'project_id','ttl_ms'})
        _need(type(body['ttl_ms']) is int and 0<body['ttl_ms']<=30000,'GODOT_INVALID_LEASE')
        with self._lock:
            _need(not getattr(self,'_durable_stopped',False),'RECOVERY_DURABLY_STOPPED')
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
        self._durable_stopped=snapshot.get('stopped',False) is True
        if self._durable_stopped:self._stop_persistence='DURABLE'
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
            previous=self._attempt
            if previous is not None:
                _need((command,digest)==previous[:2],'RECOVERY_COMMAND_CONFLICT')
            else:
                _need(not getattr(self,'_durable_stopped',False),'RECOVERY_DURABLY_STOPPED')
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
        if previous is not None:return self._reply(previous)
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

    def _reply(self,attempt):
        command,digest,state=attempt
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
            attempt=self._attempt
        if attempt is not None and attempt[0]==body['command_id']:return self._reply(attempt)
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
        stopped=self.sessions.stop(grant)
        with self._lock:
            _need(not self._closed,'GODOT_OWNER_CLOSED')
            if not getattr(self,'_durable_stopped',False) and getattr(self,'_stop_thread',None) is None:
                self._stop_persistence='PENDING'
                self._stop_thread=threading.Thread(target=self._persist_stop,
                    name='hh-godot-recovery-stop',daemon=True)
                try:self._stop_thread.start()
                except BaseException:
                    self._stop_persistence='UNKNOWN';self._held=True
                    raise
            return {**stopped,'stop_persistence':self._stop_persistence}

    def _persist_stop(self):
        acquired=self._work.acquire(timeout=35)
        try:
            _need(acquired,'RECOVERY_STOP_DRAIN_TIMEOUT')
            journal=self._recovery._journal
            journal.stop_recovery(reason='recovery.owner.stop',observed_ms=epoch_ms())
            _need(journal.snapshot()['stopped'] is True,'RECOVERY_STOP_NOT_DURABLE')
            with self._lock:
                self._durable_stopped=True;self._stop_persistence='DURABLE'
        except BaseException as error:
            with self._lock:
                self._stop_persistence='UNKNOWN';self._held=True;self._stop_error=error
        finally:
            if acquired:self._work.release()

    def close(self):
        with self._lock:
            self._closed=True
            stop_thread=getattr(self,'_stop_thread',None)
        if self.sessions is not None:self.sessions.halt()
        if stop_thread is not None and stop_thread.ident is not None:
            stop_thread.join(timeout=2)
            if stop_thread.is_alive():
                raise RecoveryHostError('RECOVERY_STOP_DRAIN_REQUIRED',cleanup_owner=self)
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

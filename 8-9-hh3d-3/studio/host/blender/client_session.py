"""Registered Blender read grants; immutable GT02 issuer has empty fixture scopes."""
from contextlib import contextmanager
from dataclasses import dataclass,asdict
from pathlib import Path
import re
import secrets
import threading
from studio.host.core.transport import SessionAuthority,SessionCredential,TransportLimits,epoch_ms
from studio.host.core.limits import SafetyViolation
from studio.protocol.core import canonical_bytes
from . import client_catalog as catalog

def need(value,code):
    if not value:raise SafetyViolation(code)

@dataclass(frozen=True)
class BlenderGrant:
    session_id:str
    project_id:str
    catalog_digest:str
    operations:tuple

@dataclass(frozen=True)
class BlenderReadLease:
    session_id:str
    lease_id:str
    fencing_epoch:int
    expires_ms:int

class _ReadPermit:
    __slots__=()

def credential_value(value):
    return (value.session_id,value.project_id,value.expires_ms,value.scopes,value.bearer)

class BlenderClientSession:
    def __init__(self,project_id,root,*,owner_deadline_ms,catalog_digest=catalog.CATALOG_DIGEST):
        need(type(project_id) is str and re.fullmatch(r'[a-z][a-z0-9._-]{0,63}',project_id),'BLENDER_INVALID_PROJECT')
        need(catalog_digest==catalog.CATALOG_DIGEST,'BLENDER_CATALOG_MISMATCH')
        need(type(owner_deadline_ms) is int and epoch_ms()<owner_deadline_ms<=epoch_ms()+120000,
            'BLENDER_OWNER_DEADLINE_REQUIRED')
        self.project_id,self.catalog_digest=project_id,catalog_digest
        self._owner_deadline_ms=owner_deadline_ms
        self._issuer=SessionAuthority(project_id,Path(root),TransportLimits(max_sessions=8,max_session_history=32,
            max_session_ttl_ms=120000,max_pending=1,max_response_bytes=catalog.MAX_WIRE))
        self._mutex=threading.RLock();self._grants={};self._leases={};self._lease_count=0
        self._stopped=threading.Event();self._active=None

    def issue(self,*,operations=catalog.OPERATIONS,ttl_ms=60000):
        need(type(operations) is frozenset and operations and operations<=catalog.OPERATIONS,'BLENDER_INVALID_GRANT')
        with self._mutex:
            need(not self._stopped.is_set(),'BLENDER_STOPPED')
            need(type(ttl_ms) is int and 0<ttl_ms<=120000,'BLENDER_INVALID_SESSION_TTL')
            ttl_ms=min(ttl_ms,self._owner_deadline_ms-epoch_ms());need(ttl_ms>0,'BLENDER_OWNER_EXPIRED')
            credential=self._issuer.issue(scopes=frozenset(),ttl_ms=ttl_ms)
            self._register(credential,operations)
            return credential

    def _register(self,credential,operations):
        grant=BlenderGrant(credential.session_id,self.project_id,self.catalog_digest,tuple(sorted(operations)))
        current=self._issuer.authenticate('Bearer '+credential.bearer)
        self._grants[credential.session_id]=(grant,canonical_bytes(asdict(grant)),current,credential_value(credential))

    def _check_grant(self,grant,operation=None):
        need(type(grant) is BlenderGrant,'BLENDER_GRANT_REQUIRED')
        row=self._grants.get(grant.session_id)
        need(row is not None and row[0] is grant and row[1]==canonical_bytes(asdict(grant)),'BLENDER_GRANT_REQUIRED')
        need(credential_value(row[2].credential)==row[3],'BLENDER_CREDENTIAL_CHANGED')
        self._issuer.check_current(row[2])
        need(operation is None or operation in grant.operations,'BLENDER_OPERATION_FORBIDDEN')

    def authenticate(self,authorization):
        need(type(authorization) is str,'AUTH_REQUIRED')
        with self._mutex:
            current=self._issuer.authenticate(authorization);row=self._grants.get(current.credential.session_id)
            need(row is not None and row[2] is current,'BLENDER_GRANT_REQUIRED')
            self._check_grant(row[0]);return row[0]

    def authorize(self,authorization,operation,*,project_id,catalog_digest):
        with self._mutex:
            grant=self.authenticate(authorization)
            need(project_id==self.project_id and catalog_digest==self.catalog_digest,'BLENDER_GRANT_BINDING')
            self._check_grant(grant,operation);return grant

    def rotate(self,credential,*,ttl_ms=60000):
        with self._mutex:
            need(type(credential) is SessionCredential,'BLENDER_CREDENTIAL_REQUIRED')
            grant=self.authenticate('Bearer '+credential.bearer)
            need(type(ttl_ms) is int and 0<ttl_ms<=120000,'BLENDER_INVALID_SESSION_TTL')
            ttl_ms=min(ttl_ms,self._owner_deadline_ms-epoch_ms());need(ttl_ms>0,'BLENDER_OWNER_EXPIRED')
            rotated=self._issuer.rotate(credential,ttl_ms=ttl_ms)
            self._register(rotated,grant.operations)
            self._leases.pop(grant.session_id,None)
            return rotated

    def revoke(self,credential):
        with self._mutex:
            need(type(credential) is SessionCredential,'BLENDER_CREDENTIAL_REQUIRED')
            grant=self.authenticate('Bearer '+credential.bearer)
            self._issuer.revoke(credential);self._grants.pop(grant.session_id);self._leases.pop(grant.session_id,None)
            return {'revoked':True,'read_draining':self._active is not None,'public_ack':False}

    def read_lease(self,grant,*,ttl_ms):
        need(type(ttl_ms) is int and 0<ttl_ms<=catalog.MAX_LEASE_MS,'BLENDER_INVALID_LEASE')
        with self._mutex:
            self._check_grant(grant,catalog.READ);need(not self._stopped.is_set(),'BLENDER_STOPPED')
            need(epoch_ms()<self._owner_deadline_ms,'BLENDER_OWNER_EXPIRED')
            need(self._lease_count<32,'BLENDER_LEASE_LIMIT')
            lease=BlenderReadLease(grant.session_id,'read.'+secrets.token_hex(16),0,
                min(epoch_ms()+ttl_ms,self._grants[grant.session_id][2].credential.expires_ms,self._owner_deadline_ms))
            self._leases[grant.session_id]=(lease,canonical_bytes(asdict(lease)));self._lease_count+=1
            return lease

    def resolve_lease(self,grant,lease_id,fencing_epoch):
        with self._mutex:
            self._check_grant(grant,catalog.READ);row=self._leases.get(grant.session_id)
            need(row is not None and type(fencing_epoch) is int and fencing_epoch==0
                and row[0].lease_id==lease_id and row[1]==canonical_bytes(asdict(row[0])),'BLENDER_READ_LEASE_REQUIRED')
            return row[0]

    def check_read(self,grant,lease,*,deadline_ms):
        with self._mutex:
            self._check_grant(grant,catalog.READ);need(not self._stopped.is_set(),'BLENDER_STOPPED')
            row=self._leases.get(grant.session_id)
            need(type(lease) is BlenderReadLease and row is not None and row[0] is lease
                and row[1]==canonical_bytes(asdict(lease)),'BLENDER_READ_LEASE_REQUIRED')
            now=epoch_ms()
            need(type(deadline_ms) is int and now<deadline_ms<=min(lease.expires_ms,self._owner_deadline_ms,now+catalog.MAX_READ_MS),
                'BLENDER_DEADLINE_EXPIRED')

    def start_read(self,grant,lease,*,deadline_ms):
        with self._mutex:
            self.check_read(grant,lease,deadline_ms=deadline_ms)
            need(self._active is None,'BLENDER_READ_BUSY')
            permit=_ReadPermit();self._active=(permit,grant,lease,deadline_ms);return permit

    def finish_read(self,permit):
        with self._mutex:
            need(self._active is not None and self._active[0] is permit,'BLENDER_READ_PERMIT_REQUIRED')
            self._active=None

    @contextmanager
    def publish_read(self,grant,lease,*,deadline_ms):
        """Linearize the bounded response publication against Stop/revocation.

        Native calls and initial response construction must finish before
        entering. Only bounded output validation and recording run under it.
        """
        with self._mutex:
            self.check_read(grant,lease,deadline_ms=deadline_ms)
            yield

    def stop(self,grant):
        with self._mutex:
            self._check_grant(grant,'control.stop');self._stopped.set()
            return {'stopped':True,'read_draining':self._active is not None,'public_ack':False}

    def validate_public_identifier(self,identifier):
        need(type(identifier) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}',identifier),
            'BLENDER_INVALID_COMMAND_ID')
        self._issuer.validate_public_identifier(identifier)

    def redact_output(self,value):return self._issuer.redact_output(value)
    def encode_output(self,value):
        with self._mutex:
            encoded=self._issuer.encode_output(value)
            if type(value) is dict and value.get('code')=='BLENDER_READ_CONFIRMED':
                # Result hashes name exact observation bytes. Neither a native
                # path/name nor newly registered token may be silently scrubbed
                # into a different successful observation at the wire boundary.
                need(encoded==canonical_bytes(value),'BLENDER_SENSITIVE_OBSERVATION')
            return encoded

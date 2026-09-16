"""Godot grants and bounded effect admission; no engine or publication claims.

The accepted fixture issuer supplies only bearer lifecycle, with empty scopes.
Godot authority is separately registered here. A phase becomes in-flight at
start_effect, immediately before the trusted owner sends its bounded effect.
Revocation/Stop deny subsequent phases but report an already-started phase as
draining. They never claim that an effect already sent to an editor was undone.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import re
import secrets
import threading

from studio.host.core.transport import SessionAuthority, SessionCredential, TransportLimits, epoch_ms
from studio.host.core.limits import SafetyViolation
from studio.protocol.core import canonical_bytes

OPERATIONS = frozenset({'scene.inspect', 'scene.save', 'control.lookup', 'control.stop'})
PHASES = frozenset({'capture', 'stage', 'select', 'adopt', 'commit'})
MAX_SAVE_MS = 90_000
_ID = re.compile(r'[a-z][a-z0-9._-]{0,63}\Z')
_DIGEST = re.compile(r'sha256:[0-9a-f]{64}\Z')


class PublicationSessionError(SafetyViolation):
    pass


def _need(condition, code):
    if not condition:
        raise PublicationSessionError(code)


def _credential_value(credential):
    return (credential.session_id, credential.project_id, credential.expires_ms,
            credential.scopes, credential.bearer)


@dataclass(frozen=True)
class GodotGrant:
    session_id: str
    project_id: str
    catalog_digest: str
    operations: tuple[str, ...]


@dataclass(frozen=True)
class GodotLease:
    session_id: str
    lease_id: str
    fencing_epoch: int
    expires_ms: int


@dataclass(frozen=True)
class EffectPermit:
    command_id: str
    digest: str
    phase: str
    deadline_ms: int
    phase_id: str


class PublicationSession:
    """One owner/project, bounded grants, one lease and one in-flight effect.

    All returned authority objects are issuer registered and compared against
    independent immutable bytes. Dataclass copies or in-place field edits are
    not authority. Public callers supply bearers, never these internal objects.
    """
    def __init__(self, project_id: str, root: Path, catalog_digest: str):
        _need(type(project_id) is str and _ID.fullmatch(project_id), 'GODOT_INVALID_PROJECT')
        _need(type(catalog_digest) is str and _DIGEST.fullmatch(catalog_digest), 'GODOT_INVALID_CATALOG')
        self.project_id, self.catalog_digest = project_id, catalog_digest
        self._issuer = SessionAuthority(project_id, root, TransportLimits())
        self._mutex = threading.RLock()
        self._stopped = threading.Event()
        self._grants = {}
        self._lease = None
        self._lease_bytes = None
        self._fence = 0
        self._active = None
        self._permits = {}
        self._held = False

    def issue(self, *, operations=OPERATIONS, ttl_ms=120_000) -> SessionCredential:
        _need(type(operations) is frozenset and operations and operations <= OPERATIONS,
              'GODOT_INVALID_GRANT')
        with self._mutex:
            _need(not self._stopped.is_set() and not self._held, 'GODOT_STOPPED')
            credential = self._issuer.issue(scopes=frozenset(), ttl_ms=ttl_ms)
            grant = GodotGrant(credential.session_id, self.project_id,
                               self.catalog_digest, tuple(sorted(operations)))
            authenticated = self._issuer.authenticate('Bearer ' + credential.bearer)
            self._grants[credential.session_id] = (grant, canonical_bytes(asdict(grant)), authenticated,
                                                  _credential_value(credential))
            return credential

    def authorize(self, authorization: str, operation: str, *, project_id: str,
                  catalog_digest: str) -> GodotGrant:
        _need(type(authorization) is str, 'AUTH_REQUIRED')
        with self._mutex:
            session = self._issuer.authenticate(authorization)
            row = self._grants.get(session.credential.session_id)
            _need(row is not None and row[2] is session, 'GODOT_GRANT_REQUIRED')
            grant = row[0]
            self._check_grant(grant, operation)
            _need(project_id == self.project_id and catalog_digest == self.catalog_digest,
                  'GODOT_GRANT_BINDING')
            return grant

    def authenticate(self, authorization: str) -> GodotGrant:
        """Header precheck for the shared bounded HTTP reader; no operation grant."""
        _need(type(authorization) is str, 'AUTH_REQUIRED')
        with self._mutex:
            session = self._issuer.authenticate(authorization)
            row = self._grants.get(session.credential.session_id)
            _need(row is not None and row[2] is session, 'GODOT_GRANT_REQUIRED')
            self._check_grant(row[0], row[0].operations[0])
            return row[0]

    def _check_grant(self, grant, operation):
        _need(type(grant) is GodotGrant, 'GODOT_GRANT_REQUIRED')
        row = self._grants.get(grant.session_id)
        _need(row is not None and row[0] is grant and row[1] == canonical_bytes(asdict(grant)),
              'GODOT_GRANT_REQUIRED')
        _need(_credential_value(row[2].credential) == row[3], 'GODOT_CREDENTIAL_CHANGED')
        self._issuer.check_current(row[2])
        _need(operation in grant.operations, 'GODOT_OPERATION_FORBIDDEN')

    def rotate(self, credential: SessionCredential, *, ttl_ms=120_000) -> SessionCredential:
        with self._mutex:
            session = self._issuer.authenticate('Bearer ' + credential.bearer)
            row = self._grants.get(session.credential.session_id)
            _need(row is not None and row[2] is session, 'GODOT_GRANT_REQUIRED')
            self._check_grant(row[0], row[0].operations[0])
            rotated = self._issuer.rotate(credential, ttl_ms=ttl_ms)
            grant = GodotGrant(rotated.session_id, self.project_id, self.catalog_digest, row[0].operations)
            self._grants[rotated.session_id] = (grant, canonical_bytes(asdict(grant)),
                self._issuer.authenticate('Bearer ' + rotated.bearer), _credential_value(rotated))
            self._invalidate_unused(session.credential.session_id)
            if self._lease and self._lease.session_id == session.credential.session_id:
                self._lease = self._lease_bytes = None
            return rotated

    def revoke(self, credential: SessionCredential) -> dict:
        with self._mutex:
            session = self._issuer.authenticate('Bearer ' + credential.bearer)
            self._issuer.revoke(credential)
            self._grants.pop(session.credential.session_id, None)
            self._invalidate_unused(session.credential.session_id)
            if self._lease and self._lease.session_id == session.credential.session_id:
                self._lease = self._lease_bytes = None
            return self._drain_status()

    def _invalidate_unused(self, session_id=None):
        if self._active:
            row = self._permits[self._active]
            if row['state'] == 'RESERVED' and (session_id is None or row['grant'].session_id == session_id):
                row['state'] = 'CANCELLED'
                self._active = None

    def read_lease(self, grant: GodotGrant, *, ttl_ms=30_000) -> GodotLease:
        _need(type(ttl_ms) is int and 0 < ttl_ms <= 30_000,'GODOT_INVALID_LEASE')
        with self._mutex:
            self._check_grant(grant,'scene.inspect')
            return GodotLease(grant.session_id,'read.'+secrets.token_hex(16),0,
                min(epoch_ms()+ttl_ms,self._grants[grant.session_id][2].credential.expires_ms))

    def lease(self, grant: GodotGrant, *, ttl_ms=MAX_SAVE_MS) -> GodotLease:
        _need(type(ttl_ms) is int and 0 < ttl_ms <= MAX_SAVE_MS, 'GODOT_INVALID_LEASE')
        with self._mutex:
            self._check_grant(grant, 'scene.save')
            _need(not self._stopped.is_set() and not self._held, 'GODOT_STOPPED')
            _need(self._active is None, 'GODOT_EFFECT_DRAIN_REQUIRED')
            now = epoch_ms()
            _need(self._lease is None or self._lease_bytes == canonical_bytes(asdict(self._lease)),
                  'GODOT_STALE_LEASE')
            _need(self._lease is None or self._lease.expires_ms <= now, 'GODOT_LEASE_BUSY')
            self._fence += 1
            self._lease = GodotLease(grant.session_id, 'lease.' + secrets.token_hex(16), self._fence,
                                    min(now + ttl_ms, self._grants[grant.session_id][2].credential.expires_ms))
            self._lease_bytes = canonical_bytes(asdict(self._lease))
            return self._lease

    def check(self, grant: GodotGrant, lease: GodotLease, *, deadline_ms: int):
        """Recheck scheduling authority without retaining a lock across I/O."""
        with self._mutex:
            self._check_grant(grant, 'scene.save')
            _need(not self._stopped.is_set() and not self._held, 'GODOT_STOPPED')
            _need(type(lease) is GodotLease and self._lease is lease
                  and self._lease_bytes == canonical_bytes(asdict(lease))
                  and lease.session_id == grant.session_id, 'GODOT_STALE_LEASE')
            now = epoch_ms()
            _need(type(deadline_ms) is int and now < deadline_ms <= lease.expires_ms,
                  'GODOT_DEADLINE_EXPIRED')

    def reserve_phase(self, grant: GodotGrant, lease: GodotLease, *, command_id: str,
                      digest: str, phase: str, deadline_ms: int) -> EffectPermit:
        _need(type(command_id) is str and _ID.fullmatch(command_id), 'GODOT_INVALID_COMMAND_ID')
        _need(type(digest) is str and _DIGEST.fullmatch(digest) and type(phase) is str and phase in PHASES,
              'GODOT_INVALID_PHASE')
        with self._mutex:
            self.check(grant, lease, deadline_ms=deadline_ms)
            self._issuer.validate_public_identifier(command_id)
            _need(self._active is None, 'GODOT_EFFECT_BUSY')
            _need(len(self._permits) < 256, 'GODOT_PHASE_LIMIT')
            permit = EffectPermit(command_id, digest, phase, deadline_ms, secrets.token_hex(16))
            self._permits[permit.phase_id] = dict(permit=permit, encoded=canonical_bytes(asdict(permit)),
                grant=grant, lease=lease, state='RESERVED')
            self._active = permit.phase_id
            return permit

    def _row(self, permit):
        _need(type(permit) is EffectPermit, 'GODOT_UNKNOWN_PERMIT')
        row = self._permits.get(permit.phase_id)
        _need(row is not None and row['permit'] is permit and row['encoded'] == canonical_bytes(asdict(permit)),
              'GODOT_UNKNOWN_PERMIT')
        return row

    def start_effect(self, permit: EffectPermit):
        """Linearization point. The owner must next send exactly this effect.

        The editor separately rechecks its session/root/revision/deadline on
        the main thread. Until finish_effect, revocation reports draining.
        """
        with self._mutex:
            row = self._row(permit)
            _need(row['state'] == 'RESERVED' and self._active == permit.phase_id,
                  'GODOT_PERMIT_ALREADY_USED')
            self.check(row['grant'], row['lease'], deadline_ms=permit.deadline_ms)
            row['state'] = 'STARTED'

    def finish_effect(self, permit: EffectPermit, *, known: bool):
        _need(type(known) is bool, 'GODOT_INVALID_OUTCOME')
        with self._mutex:
            row = self._row(permit)
            _need(row['state'] == 'STARTED' and self._active == permit.phase_id,
                  'GODOT_EFFECT_NOT_STARTED')
            row['state'] = 'DRAINED' if known else 'UNKNOWN'
            self._active = None
            if not known:
                self._held = True
                self._stopped.set()

    def cancel_reserved(self, permit: EffectPermit):
        with self._mutex:
            row = self._row(permit)
            _need(row['state'] == 'RESERVED', 'GODOT_EFFECT_NOT_RESERVED')
            row['state'] = 'CANCELLED'
            self._active = None

    def stop(self, grant: GodotGrant) -> dict:
        # Validate before latching, but do not wait for the disk/IPC effect.
        # This lock only guards in-memory transitions and never surrounds I/O.
        with self._mutex:
            self._check_grant(grant, 'control.stop')
            self._stopped.set()
            self._invalidate_unused()
            return self._drain_status()

    def _drain_status(self):
        return {'stopped': self._stopped.is_set(), 'held': self._held,
                'draining': self._active is not None, 'public_ack': False}

    def status(self) -> dict:
        with self._mutex:
            return self._drain_status()

    def halt(self):
        """Trusted local lifecycle latch; no public route bypasses authentication."""
        self._stopped.set()
        with self._mutex:
            self._invalidate_unused()
            return self._drain_status()

    def redact_output(self, value):
        return self._issuer.redact_output(value)

    def encode_output(self, value):
        return self._issuer.encode_output(value)

    def validate_public_identifier(self, identifier):
        _need(type(identifier) is str and _ID.fullmatch(identifier), 'GODOT_INVALID_COMMAND_ID')
        self._issuer.validate_public_identifier(identifier)

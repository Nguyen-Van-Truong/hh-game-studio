"""Bounded replay grants over the unchanged GT02 bearer issuer.

The issuer receives empty fixture scopes. Replay authority is separately bound
to one immutable run/source/snapshot catalog. Objects returned by this module
are registered by identity and by independently stored bytes; copying a frozen
dataclass does not copy authority.

This module has no engine, I/O effects, transport, durable journal or ACK. The
owner validates command bodies and implements project-wide durable dedupe. A
permit admits one bounded native phase, not the lifetime of a Play process.
Stop cancels reserved work and reports started work as draining; it does not
claim that a running process has stopped. No lock is retained across owner I/O.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
import secrets
import threading

from studio.host.core.limits import SafetyViolation
from studio.host.core.transport import SessionAuthority, SessionCredential, TransportLimits, epoch_ms
from studio.protocol.core import SAFE_INTEGER, canonical_bytes

WORK_OPERATIONS = frozenset({'play.start', 'play.inspect', 'play.capture'})
CONTROL_OPERATIONS = frozenset({'control.lookup', 'control.stop'})
OPERATIONS = WORK_OPERATIONS | CONTROL_OPERATIONS
MAX_COMMANDS = 64
MAX_COMMAND_MS = 20_000
MAX_OWNER_MS = 120_000
MAX_SESSIONS = 8
MAX_CREDENTIAL_HISTORY = 32
BINDING_FIELDS = frozenset({'run_id', 'command_id', 'runtime_instance_id',
    'source_closure_sha256', 'runtime_snapshot_sha256', 'trace_sha256', 'glb_sha256', 'generation'})
_ID = re.compile(r'[a-z][a-z0-9._-]{0,63}\Z')
_BOUND_ID = re.compile(r'[a-z][a-z0-9._-]{0,127}\Z')
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_DIGEST = re.compile(r'sha256:[0-9a-f]{64}\Z')


class ReplaySessionError(SafetyViolation):
    pass


def _need(value, code):
    if not value:
        raise ReplaySessionError(code)


def _binding_bytes(value):
    _need(type(value) is dict and set(value) == BINDING_FIELDS, 'REPLAY_BINDING_FIELDS')
    for name in ('run_id', 'command_id', 'runtime_instance_id'):
        _need(type(value[name]) is str and _BOUND_ID.fullmatch(value[name]), 'REPLAY_BINDING_ID')
    for name in ('source_closure_sha256', 'runtime_snapshot_sha256', 'trace_sha256', 'glb_sha256'):
        _need(type(value[name]) is str and _SHA.fullmatch(value[name]), 'REPLAY_BINDING_HASH')
    _need(type(value['generation']) is int and 1 <= value['generation'] <= min(SAFE_INTEGER, 2147483647),
          'REPLAY_BINDING_GENERATION')
    return canonical_bytes(value)


def _credential_value(value):
    return (value.session_id, value.project_id, value.expires_ms, value.scopes, value.bearer)


@dataclass(frozen=True, slots=True)
class ReplayGrant:
    session_id: str
    project_id: str
    catalog_digest: str
    binding_sha256: str
    run_id: str
    runtime_instance_id: str
    source_closure_sha256: str
    runtime_snapshot_sha256: str
    operations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReplayPermit:
    command_id: str
    request_digest: str
    operation: str
    deadline_ms: int
    permit_id: str
    binding_sha256: str


class ReplaySession:
    """One run context, one reserved/started phase, finite retained tombstones."""

    def __init__(self, project_id: str, root: Path, *, catalog_digest: str,
                 binding: dict, owner_deadline_ms: int):
        _need(type(project_id) is str and _ID.fullmatch(project_id), 'REPLAY_INVALID_PROJECT')
        _need(type(catalog_digest) is str and _DIGEST.fullmatch(catalog_digest), 'REPLAY_INVALID_CATALOG')
        now = epoch_ms()
        _need(type(owner_deadline_ms) is int and now < owner_deadline_ms <= now + MAX_OWNER_MS,
              'REPLAY_OWNER_DEADLINE')
        self._binding = _binding_bytes(binding)
        self.binding_sha256 = hashlib.sha256(self._binding).hexdigest()
        self.project_id, self.catalog_digest = project_id, catalog_digest
        self._owner_deadline_ms = owner_deadline_ms
        self._issuer = SessionAuthority(project_id, Path(root), TransportLimits(
            max_sessions=MAX_SESSIONS, max_session_history=MAX_CREDENTIAL_HISTORY,
            max_session_ttl_ms=MAX_OWNER_MS, max_pending=1))
        self._mutex = threading.RLock()
        self._stopped = threading.Event()
        self._held = False
        self._grants = {}
        self._commands = {}
        self._active = None

    @property
    def binding(self):
        """A detached JSON value, never a mutable reference to granted scope."""
        return json.loads(self._binding)

    def _ttl(self, value):
        _need(type(value) is int and 0 < value <= MAX_OWNER_MS, 'REPLAY_INVALID_SESSION_TTL')
        remaining = self._owner_deadline_ms - epoch_ms()
        _need(remaining > 0, 'REPLAY_OWNER_EXPIRED')
        return min(value, remaining)

    def _register(self, credential, operations):
        _need(epoch_ms() < self._owner_deadline_ms, 'REPLAY_OWNER_EXPIRED')
        binding = self.binding
        # Public identifiers are checked after minting too: none may contain a
        # newly issued credential, including a credential retained after rotate.
        self._issuer.validate_public_identifier(self.project_id)
        for name in ('run_id', 'command_id', 'runtime_instance_id'):
            self._issuer.validate_public_identifier(binding[name])
        grant = ReplayGrant(credential.session_id, self.project_id, self.catalog_digest,
            self.binding_sha256, binding['run_id'], binding['runtime_instance_id'],
            binding['source_closure_sha256'], binding['runtime_snapshot_sha256'], tuple(sorted(operations)))
        current = self._issuer.authenticate('Bearer ' + credential.bearer)
        self._grants[credential.session_id] = (grant, canonical_bytes(asdict(grant)), current,
                                               _credential_value(credential))
        return grant

    def issue(self, *, operations=OPERATIONS, ttl_ms=60_000) -> SessionCredential:
        _need(type(operations) is frozenset and operations and operations <= OPERATIONS, 'REPLAY_INVALID_GRANT')
        with self._mutex:
            _need(not self._stopped.is_set() and not self._held, 'REPLAY_STOPPED')
            credential = self._issuer.issue(scopes=frozenset(), ttl_ms=self._ttl(ttl_ms))
            try:
                self._register(credential, operations)
            except BaseException:
                self._issuer.revoke(credential)
                raise
            return credential

    def _registered(self, grant):
        _need(type(grant) is ReplayGrant, 'REPLAY_GRANT_REQUIRED')
        row = self._grants.get(grant.session_id)
        _need(row is not None and row[0] is grant and row[1] == canonical_bytes(asdict(grant)), 'REPLAY_GRANT_REQUIRED')
        _need(_credential_value(row[2].credential) == row[3], 'REPLAY_CREDENTIAL_CHANGED')
        self._issuer.check_current(row[2])
        _need(epoch_ms() < self._owner_deadline_ms, 'REPLAY_OWNER_EXPIRED')
        return row

    def _check_grant(self, grant, operation):
        row = self._registered(grant)
        _need(type(operation) is str and operation in grant.operations, 'REPLAY_OPERATION_FORBIDDEN')
        return row

    def authenticate(self, authorization: str) -> ReplayGrant:
        """Shared HTTP header precheck. No operation is admitted by this call."""
        _need(type(authorization) is str, 'AUTH_REQUIRED')
        with self._mutex:
            current = self._issuer.authenticate(authorization)
            row = self._grants.get(current.credential.session_id)
            _need(row is not None and row[2] is current, 'REPLAY_GRANT_REQUIRED')
            self._registered(row[0])
            return row[0]

    def authorize(self, authorization: str, operation: str, *, project_id: str,
                  catalog_digest: str, binding: dict) -> ReplayGrant:
        with self._mutex:
            grant = self.authenticate(authorization)
            self._check_grant(grant, operation)
            _need(project_id == self.project_id and catalog_digest == self.catalog_digest
                  and _binding_bytes(binding) == self._binding, 'REPLAY_GRANT_BINDING')
            if operation in WORK_OPERATIONS:
                _need(not self._stopped.is_set() and not self._held, 'REPLAY_STOPPED')
            return grant

    def _credential(self, credential):
        _need(type(credential) is SessionCredential, 'REPLAY_CREDENTIAL_REQUIRED')
        row = self._grants.get(credential.session_id)
        _need(row is not None and row[2].credential is credential
              and _credential_value(credential) == row[3], 'REPLAY_CREDENTIAL_REQUIRED')
        self._registered(row[0])
        return row

    def rotate(self, credential: SessionCredential, *, ttl_ms=60_000) -> SessionCredential:
        with self._mutex:
            row = self._credential(credential)
            rotated = self._issuer.rotate(credential, ttl_ms=self._ttl(ttl_ms))
            self._cancel_unused(row[0])
            try:
                self._register(rotated, frozenset(row[0].operations))
            except BaseException:
                self._grants.pop(credential.session_id, None)
                self._issuer.revoke(rotated)
                raise
            return rotated

    def revoke(self, credential: SessionCredential) -> dict:
        with self._mutex:
            row = self._credential(credential)
            self._issuer.revoke(credential)
            self._grants.pop(credential.session_id)
            self._cancel_unused(row[0])
            return self._status()

    def _check_work(self, grant, operation, deadline_ms):
        row = self._check_grant(grant, operation)
        _need(operation in WORK_OPERATIONS, 'REPLAY_WORK_OPERATION_REQUIRED')
        _need(not self._stopped.is_set() and not self._held, 'REPLAY_STOPPED')
        now = epoch_ms()
        _need(type(deadline_ms) is int and now < deadline_ms <= min(now + MAX_COMMAND_MS,
              self._owner_deadline_ms, row[2].credential.expires_ms), 'REPLAY_DEADLINE_EXPIRED')

    def reserve(self, grant: ReplayGrant, *, command_id: str, request_digest: str,
                operation: str, deadline_ms: int) -> ReplayPermit:
        """Reserve one phase. Duplicates stay tombstones; owner handles lookup."""
        with self._mutex:
            self._check_work(grant, operation, deadline_ms)
            self.validate_public_identifier(command_id)
            _need(type(request_digest) is str and _DIGEST.fullmatch(request_digest), 'REPLAY_INVALID_REQUEST_DIGEST')
            previous = self._commands.get(command_id)
            if previous is not None:
                _need(previous['permit'].request_digest == request_digest and previous['permit'].operation == operation,
                      'REPLAY_COMMAND_ID_COLLISION')
                raise ReplaySessionError('REPLAY_COMMAND_ALREADY_REGISTERED')
            _need(len(self._commands) < MAX_COMMANDS, 'REPLAY_COMMAND_LIMIT')
            _need(self._active is None, 'REPLAY_WORK_BUSY')
            permit = ReplayPermit(command_id, request_digest, operation, deadline_ms,
                                  'permit.' + secrets.token_hex(16), self.binding_sha256)
            self._commands[command_id] = {'permit': permit, 'encoded': canonical_bytes(asdict(permit)),
                                          'grant': grant, 'state': 'RESERVED'}
            self._active = command_id
            return permit

    def _row(self, permit):
        _need(type(permit) is ReplayPermit, 'REPLAY_PERMIT_REQUIRED')
        row = self._commands.get(permit.command_id)
        _need(row is not None and row['permit'] is permit and row['encoded'] == canonical_bytes(asdict(permit)),
              'REPLAY_PERMIT_REQUIRED')
        return row

    def start_effect(self, permit: ReplayPermit) -> None:
        """Linearization immediately before the owner sends its fixed effect."""
        with self._mutex:
            row = self._row(permit)
            _need(row['state'] == 'RESERVED' and self._active == permit.command_id, 'REPLAY_PERMIT_ALREADY_USED')
            self._check_work(row['grant'], permit.operation, permit.deadline_ms)
            row['state'] = 'STARTED'

    def finish_effect(self, permit: ReplayPermit, *, known: bool) -> None:
        """A started phase may drain after revoke/expiry; this grants no reply."""
        _need(type(known) is bool, 'REPLAY_INVALID_OUTCOME')
        with self._mutex:
            row = self._row(permit)
            _need(row['state'] == 'STARTED' and self._active == permit.command_id, 'REPLAY_EFFECT_NOT_STARTED')
            row['state'] = 'DRAINED' if known else 'UNKNOWN'
            self._active = None
            if not known:
                self._held = True
                self._stopped.set()

    def cancel_reserved(self, permit: ReplayPermit) -> None:
        with self._mutex:
            row = self._row(permit)
            _need(row['state'] == 'RESERVED' and self._active == permit.command_id, 'REPLAY_EFFECT_NOT_RESERVED')
            row['state'] = 'CANCELED'
            self._active = None

    def _cancel_unused(self, grant=None):
        if self._active is not None:
            row = self._commands[self._active]
            if row['state'] == 'RESERVED' and (grant is None or row['grant'] is grant):
                row['state'] = 'CANCELED'
                self._active = None

    def check_delivery(self, grant: ReplayGrant, *, operation: str, deadline_ms: int) -> None:
        """Recheck just before delivery; completion alone never revives a grant."""
        with self._mutex:
            self._check_work(grant, operation, deadline_ms)

    def stop(self, grant: ReplayGrant) -> dict:
        with self._mutex:
            self._check_grant(grant, 'control.stop')
            self._stopped.set()
            self._cancel_unused()
            return self._status()

    def halt(self) -> dict:
        """Trusted owner lifecycle latch; not an unauthenticated public route."""
        self._stopped.set()
        with self._mutex:
            self._cancel_unused()
            return self._status()

    def _status(self):
        state = self._commands[self._active]['state'] if self._active is not None else None
        return {'stopped': self._stopped.is_set(), 'held': self._held,
                'draining': state == 'STARTED', 'reserved': state == 'RESERVED',
                'commands_used': len(self._commands), 'command_capacity': MAX_COMMANDS, 'public_ack': False}

    def status(self) -> dict:
        with self._mutex:
            return self._status()

    def permit_status(self, permit: ReplayPermit) -> str:
        with self._mutex:
            return self._row(permit)['state']

    def validate_public_identifier(self, identifier: str) -> None:
        _need(type(identifier) is str and _ID.fullmatch(identifier), 'REPLAY_INVALID_COMMAND_ID')
        self._issuer.validate_public_identifier(identifier)

    def redact_output(self, value):
        return self._issuer.redact_output(value)

    def encode_output(self, value) -> bytes:
        """Never silently rewrite a hash-bound observation or command identity."""
        with self._mutex:
            clean = self._issuer.encode_output(value)
            _need(clean == canonical_bytes(value), 'REPLAY_SENSITIVE_OUTPUT')
            return clean

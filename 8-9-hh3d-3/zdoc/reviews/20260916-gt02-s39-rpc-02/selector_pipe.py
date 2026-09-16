"""Internal authenticated fixture-release IPC, with an explicit broker pump.

No engine operation, public discovery capability or general file write is
enabled. The caller owns endpoint/process/Job lifetimes and schedules advance()
only for a newly admitted local job. Reopen and lookup never schedule effects.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import threading

from ...protocol.core import Request, Response, Status, ValidationError
from .fixture_selector import FixtureSelector, _name
from .limits import SafetyViolation, parse_json_utf8
from .pipe_endpoint import AppContainerEndpoint
from .pipe_io import MAX_FRAME_BYTES
from .transport import SessionAuthority, SessionCredential, TransportLimits, epoch_ms, _response

_BROKER_BIND = threading.Lock()


def _shape(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise SafetyViolation('INVALID_ENVELOPE')


def _reply(value, command_id):
    if value is None:
        return _response(Status.REJECTED, 'COMMAND_NOT_FOUND', command_id)
    if 'code' in value:
        return Response.from_dict(value)
    return _response(Status(value['status']), 'SELECTOR_PENDING', command_id,
                     phase=value['phase'], request_digest=value['digest'])


@dataclass
class _Activation:
    command_id: str
    session: object = field(repr=False)
    cancel: threading.Event = field(default_factory=threading.Event)


class SelectorFixtureBroker:
    """One private selector and one pending job; no worker creation or eval.

    Authorization admits one phase at a time. A revoked session prevents the
    next phase; already admitted synchronous native I/O may finish. Session
    locks are never held over disk I/O, so control authentication remains free.
    """
    def __init__(self, selector: FixtureSelector, *, limits=TransportLimits()):
        if type(selector) is not FixtureSelector or type(limits) is not TransportLimits:
            raise SafetyViolation('SELECTOR_TRUSTED_COMPONENT_REQUIRED')
        self.selector, self.limits = selector, limits
        self.project_id = selector.project_id
        self.sessions = SessionAuthority(self.project_id, selector.store.root, limits)
        self._admission = threading.Lock()
        self._pump = threading.Lock()
        self._state_lock = threading.Lock()
        self._job = None
        self._leases = {}
        self._hold = threading.Event()
        self._diagnostics = deque(maxlen=limits.max_diagnostics)
        self._closed = False
        with _BROKER_BIND:
            if getattr(selector, '_pipe_broker', None) is not None:
                raise SafetyViolation('SELECTOR_BROKER_ALREADY_BOUND')
            selector._pipe_broker = self

    def close(self):
        # Supervisor must first join its pump/endpoint threads. Do not transfer
        # ownership while an already admitted phase still holds these locks.
        if not self._admission.acquire(blocking=False):
            raise SafetyViolation('SELECTOR_BROKER_BUSY')
        try:
            if not self._pump.acquire(blocking=False):
                raise SafetyViolation('SELECTOR_BROKER_BUSY')
            try:
                self._closed = True
                self._hold.set()
                with _BROKER_BIND:
                    if getattr(self.selector, '_pipe_broker', None) is self:
                        self.selector._pipe_broker = None
            finally:
                self._pump.release()
        finally:
            self._admission.release()

    def _check_open(self):
        if self._closed:
            raise SafetyViolation('SELECTOR_BROKER_CLOSED')

    def _scope(self, session, name):
        self.sessions.check_current(session)
        if name not in session.credential.scopes:
            raise SafetyViolation('SCOPE_DENIED')

    def _diagnostic(self, code):
        # Only fixed codes; no bearer, request body, paths or exception strings.
        self._diagnostics.append(self.sessions.encode_output({'code':code}))

    def _lookup(self, command_id):
        result = _reply(self.selector.lookup(command_id), command_id)
        with self._state_lock:
            owned = self._job is not None and self._job.command_id == command_id
        if result.status is Status.ACCEPTED_PENDING and (not owned or self._hold.is_set()):
            return _response(Status.UNKNOWN, 'SELECTOR_EXPLICIT_RECONCILE_REQUIRED', command_id,
                             **dict(result.postconditions))
        return result

    def dispatch(self, route, body, session, *, control):
        self._check_open()
        allowed = {'/v1/lookup','/v1/cancel','/v1/stop'} if control else {'/v1/lease','/v1/commands'}
        if route not in allowed:
            raise SafetyViolation('UNSUPPORTED_ROUTE')
        if type(body) is not dict or body.get('project_id') != self.project_id:
            raise SafetyViolation('PROJECT_MISMATCH')
        self.sessions.check_current(session)
        # Reject secret-bearing data before it can become an intent or asset.
        # Redaction must not silently change command identity or content hashes.
        if self.sessions.redact_output(body) != body:
            raise SafetyViolation('SENSITIVE_INPUT_FORBIDDEN')
        if route == '/v1/lease':
            _shape(body, ('project_id','ttl_ms'))
            self._scope(session, 'fixture.write')
            if self._hold.is_set() or self.selector.snapshot()['stopped']:
                raise SafetyViolation('SELECTOR_STOPPED')
            lease = self.selector.lease(session.credential.session_id, now_ms=epoch_ms(), ttl_ms=body['ttl_ms'])
            with self._state_lock:
                # One current lease exists in the selector, so retain only it.
                self._leases = {session.credential.session_id: lease}
            return {key:lease[key] for key in ('lease_id','fencing_epoch','expires_ms')}
        if route == '/v1/commands':
            self._scope(session, 'fixture.write')
            request = Request.from_dict(body)
            if (request.operation != 'fixture.release.activate' or request.target != {'stable_id':'active-release'}
                    or request.expected_revision != request.payload.get('expected_game_revision')):
                raise SafetyViolation('SELECTOR_REQUEST_SCOPE')
            self.sessions.validate_public_identifier(request.command_id)
            if not self._admission.acquire(timeout=2):
                raise SafetyViolation('SELECTOR_ADMISSION_BUSY')
            try:
                self._check_open()
                # Terminal retry survives lease/session replacement, but its
                # project, immutable digest and current read/write auth do not.
                existing = self.selector.lookup(request.command_id, request.digest)
                if existing is not None:
                    return self._lookup(request.command_id)
                if self._hold.is_set():
                    raise SafetyViolation('SELECTOR_RECONCILIATION_REQUIRED')
                self._scope(session, 'fixture.write')
                with self._state_lock:
                    lease = self._leases.get(session.credential.session_id)
                if (lease is None or request.lease_id != lease['lease_id']
                        or request.fencing_epoch != lease['fencing_epoch']):
                    raise SafetyViolation('SELECTOR_STALE_LEASE')
                result = self.selector.prepare(body, now_ms=epoch_ms())
                with self._state_lock:
                    self._job = _Activation(request.command_id, session)
                return _reply(result, request.command_id)
            finally:
                self._admission.release()
        _shape(body, ('project_id','command_id'))
        identifier = body['command_id']
        if type(identifier) is not str:
            raise SafetyViolation('INVALID_COMMAND_ID')
        _name(identifier)
        self.sessions.validate_public_identifier(identifier)
        if route == '/v1/lookup':
            self._scope(session, 'fixture.read')
            return self._lookup(identifier)
        self._scope(session, 'control.stop' if route == '/v1/stop' else 'control.cancel')
        with self._state_lock:
            job = self._job
            if job is not None and (route == '/v1/stop' or job.command_id == identifier):
                job.cancel.set()
        if route == '/v1/stop':
            # command_id identifies the work whose receipt the caller wants;
            # this reply reports durable stop state, not a second command ACK.
            snapshot = self.selector.stop()
            return {'stopped':snapshot['stopped'], 'pending_command':snapshot['pending_command'],
                    'command':self._lookup(identifier).as_dict()}
        return self._cancel_current(identifier)

    def _cancel_current(self, identifier):
        # Stage/select may have progressed while control waited for disk. Check
        # and cancel under the same selector lock, never from a stale phase.
        with self.selector._mutex:
            current = self.selector.lookup(identifier)
            if current is None or 'code' in current:
                return _reply(current, identifier)
            if current['phase'] in ('SELECTED','RESTORING'):
                return _response(Status.UNKNOWN, 'CANCEL_TOO_LATE_LOOKUP', identifier, next_action='lookup.reconcile')
            return _reply(self.selector.reconcile(identifier, 'cancel'), identifier)

    def advance(self):
        """Trusted scheduler advances one newly admitted local phase only.

        No queue is reconstructed from disk. Recovery is an explicit separate
        coordinator action. Storage uncertainty holds further automatic work.
        """
        if not self._pump.acquire(blocking=False):
            raise SafetyViolation('SELECTOR_PUMP_BUSY')
        try:
            self._check_open()
            with self._state_lock:
                job = self._job
            if job is None:
                return None
            if self._hold.is_set():
                return self._lookup(job.command_id)
            current = self.selector.lookup(job.command_id)
            if 'code' in current:
                with self._state_lock:
                    if self._job is job: self._job = None
                return _reply(current, job.command_id)
            try:
                self._scope(job.session, 'fixture.write')
            except SafetyViolation:
                job.cancel.set()
            if job.cancel.is_set():
                if current['phase'] in ('INTENT','STAGING','STAGED'):
                    return self._cancel_current(job.command_id)
                self._hold.set()
                return _response(Status.UNKNOWN, 'SELECTOR_EXPLICIT_RECONCILE_REQUIRED', job.command_id)
            # Authorization was just checked. No session lock covers I/O;
            # revocation/Stop may race with this admitted phase, never the next.
            if current['phase'] == 'INTENT':
                self.selector.stage(job.command_id, now_ms=epoch_ms())
            elif current['phase'] == 'STAGED':
                self.selector.select(job.command_id, now_ms=epoch_ms())
            elif current['phase'] == 'SELECTED':
                self.selector.adopt(job.command_id, now_ms=epoch_ms())
            else:
                self._hold.set()
                return _response(Status.UNKNOWN, 'SELECTOR_EXPLICIT_RECONCILE_REQUIRED', job.command_id)
            return self._lookup(job.command_id)
        except BaseException:
            self._hold.set()
            raise
        finally:
            self._pump.release()


class SelectorPipeServer:
    """Endpoint role/process binding and bearer/session auth precede parsing."""
    def __init__(self, endpoint: AppContainerEndpoint, broker: SelectorFixtureBroker,
                 credential: SessionCredential):
        if type(endpoint) is not AppContainerEndpoint or type(broker) is not SelectorFixtureBroker:
            raise SafetyViolation('BOUND_ENDPOINT_REQUIRED')
        session = broker.sessions.authenticate('Bearer '+credential.bearer)
        if session.credential != credential:
            raise SafetyViolation('SESSION_BINDING_MISMATCH')
        self.endpoint, self.broker = endpoint, broker
        self.session_id = credential.session_id

    def serve_one(self):
        broker, identifier = self.broker, 'transport.request'
        raw = self.endpoint.read_frame(timeout_ms=broker.limits.request_timeout_ms)
        dispatch_started = False
        try:
            parts = raw.split(b'\n', 2)
            if len(parts) != 3 or len(parts[0]) > 128 or len(parts[1]) > 64:
                raise SafetyViolation('INVALID_PIPE_HEADER')
            try:
                authorization, route = parts[0].decode('ascii'), parts[1].decode('ascii')
            except UnicodeError:
                raise SafetyViolation('INVALID_PIPE_HEADER') from None
            session = broker.sessions.authenticate(authorization)
            if session.credential.session_id != self.session_id:
                raise SafetyViolation('SESSION_BINDING_MISMATCH')
            if len(parts[2]) > broker.limits.max_body_bytes:
                raise SafetyViolation('ENVELOPE_TOO_LARGE')
            body = parse_json_utf8(parts[2])
            if type(body) is dict and type(body.get('command_id')) is str:
                _name(body['command_id'])
                broker.sessions.validate_public_identifier(body['command_id'])
                identifier = body['command_id']
            dispatch_started = True
            result = broker.dispatch(route, body, session, control=self.endpoint.role == 'control')
        except (SafetyViolation, ValidationError) as exc:
            # Selector/storage uncertainty cannot become a no-effect rejection.
            # Other SafetyViolation codes are validations before effects; native
            # store errors after dispatch are conservatively held as UNKNOWN.
            from .private_store import PrivateStoreError
            from .private_events import EventLogError
            uncertain = bool(getattr(exc, 'outcome_unknown', False)
                             or (dispatch_started and isinstance(exc, (PrivateStoreError, EventLogError))))
            if uncertain: broker._hold.set()
            broker._diagnostic(exc.code)
            result = _response(Status.UNKNOWN if uncertain else Status.REJECTED, exc.code, identifier)
        except Exception:
            broker._hold.set()
            broker._diagnostic('SELECTOR_DISPATCH_UNKNOWN')
            result = _response(Status.UNKNOWN, 'SELECTOR_DISPATCH_UNKNOWN', identifier)
        value = result.as_dict() if isinstance(result, Response) else result
        encoded = broker.sessions.encode_output(value)
        if len(encoded) > min(MAX_FRAME_BYTES, broker.limits.max_response_bytes):
            result = _response(Status.UNKNOWN, 'RESULT_TOO_LARGE', identifier)
            encoded = broker.sessions.encode_output(result.as_dict())
        # Delivery failure propagates to the owned supervisor; never resend or
        # undo a durable intent/receipt to make an I/O error look effect-free.
        self.endpoint.write_frame(encoded, timeout_ms=broker.limits.request_timeout_ms)
        return result

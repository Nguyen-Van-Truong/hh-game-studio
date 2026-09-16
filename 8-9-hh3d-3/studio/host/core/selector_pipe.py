"""Authenticated fixed fixture-release IPC, with an explicit broker pump.

Only from_managed registers the bounded public active-release scope. Direct
construction stays internal. No engine operation or general file write is
enabled. The caller owns endpoint/process/Job lifetimes and the explicit pump.
"""
from __future__ import annotations

from collections import deque
from contextlib import nullcontext
from dataclasses import dataclass, field
import threading
import time

from ...protocol.core import (Capability, Discovery, PROTOCOL_VERSION, SCHEMA_VERSION,
                              Request, Response, Status, ValidationError, canonical_bytes)
from .fixture_selector import FixtureSelector, FileFixtureReleaseConsumer, _name
from .limits import SafetyViolation, parse_json_utf8
from .pipe_endpoint import AppContainerEndpoint
from .pipe_io import MAX_FRAME_BYTES
from .transport import SessionAuthority, SessionCredential, TransportLimits, epoch_ms, _response
from .selector_contract import (SELECTOR_SCHEMA_DIGEST, SELECTOR_SCOPE,
                                SELECTOR_INSPECT_MAX_BYTES, SELECTOR_PAYLOAD_MAX_BYTES)

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
    @classmethod
    def from_managed(cls, owner, *, limits=TransportLimits()):
        from .managed_fixture import ManagedFixtureOwner
        if cls is not SelectorFixtureBroker or type(owner) is not ManagedFixtureOwner:
            raise SafetyViolation('SELECTOR_MANAGED_OWNER_REQUIRED')
        with owner._lifecycle_lock:
            cls._verify_managed(owner)
            broker = cls(owner.selector, limits=limits)
            broker._managed_owner = owner
            return broker

    @staticmethod
    def _verify_managed(owner):
        """Read-only live binding check; no registry update, lease or admission."""
        from .custody import WitnessCustody, identity_from
        from .custody_registry import RegistryCustody
        from .managed_fixture import ManagedFixtureOwner
        from .private_events import PrivateEventLog
        from .private_store import PrivateBlobStore
        from .safe_replace import ProtectedFileRoot
        if (type(owner) is not ManagedFixtureOwner or type(owner.registry) is not RegistryCustody
                or type(owner.custody) is not WitnessCustody or type(owner.files) is not ProtectedFileRoot
                or type(owner.store) is not PrivateBlobStore or type(owner.log) is not PrivateEventLog
                or type(owner.selector) is not FixtureSelector or type(owner.consumer) is not FileFixtureReleaseConsumer):
            raise SafetyViolation('SELECTOR_MANAGED_BINDING_INVALID')
        selector = owner.selector
        with selector._mutex:
            if (selector._closed or owner.consumer._closed or owner._cleanup_errors
                    or selector.project_id != owner.project_id or owner.registry.local_id != owner.storage_id
                    or owner.custody._registry is not owner.registry or owner.log._custody is not owner.custody
                    or selector.log is not owner.log or selector.store is not owner.store
                    or selector.consumer is not owner.consumer or owner.consumer.files is not owner.files
                    or getattr(owner.files, '_fixture_file_consumer', None) is not owner.consumer
                    or any(getattr(item, '_fixture_selector', None) is not selector
                           for item in (owner.log, owner.store, owner.consumer))):
                raise SafetyViolation('SELECTOR_MANAGED_BINDING_INVALID')
            owner.custody.confirm_current()
            record = owner.custody.record
            if (record['phase'] != 'READY' or record['project_id'] != owner.project_id
                    or record['storage_id'] != owner.storage_id):
                raise SafetyViolation('SELECTOR_MANAGED_BINDING_INVALID')
            for name, component in (('files', owner.files), ('blobs', owner.store)):
                if (record[name]['path'] != str(component.root)
                        or not identity_from(record[name]['identity']).same_file(component.root_identity)):
                    raise SafetyViolation('SELECTOR_MANAGED_BINDING_INVALID')
            with owner.files._mutex:
                owner.files._check()
            with owner.store._mutex:
                owner.store._check()
            saved, actual = owner.custody.binding, owner.log.binding()
            if (record['events']['path'] != str(owner.log.root)
                    or not saved.root.same_file(actual.root) or not saved.stream.same_file(actual.stream)
                    or saved.witnessed != actual.witnessed):
                raise SafetyViolation('SELECTOR_MANAGED_BINDING_INVALID')

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
        self._managed_owner = None
        self._service_owner = None
        self._wake = threading.Event()
        with _BROKER_BIND:
            if getattr(selector, '_pipe_broker', None) is not None:
                raise SafetyViolation('SELECTOR_BROKER_ALREADY_BOUND')
            selector._pipe_broker = self

    def close(self):
        # Supervisor must first join its pump/endpoint threads. Do not transfer
        # ownership while an already admitted phase still holds these locks.
        owner = self._managed_owner
        with owner._lifecycle_lock if owner is not None else nullcontext():
            if self._service_owner is not None:
                raise SafetyViolation('SELECTOR_SERVICE_ACTIVE')
            self._close_unserved()

    def _close_unserved(self):
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

    def _check_registration(self):
        if self._managed_owner is not None:
            self._verify_managed(self._managed_owner)
            if self._managed_owner.selector is not self.selector:
                raise SafetyViolation('SELECTOR_MANAGED_BINDING_INVALID')

    def discovery(self, session):
        self._check_open()
        if self._managed_owner is None:
            raise SafetyViolation('SELECTOR_NOT_REGISTERED')
        self.sessions.check_current(session)
        self._check_registration()
        state = self.selector.snapshot()
        capabilities = []
        if 'fixture.read' in session.credential.scopes:
            capabilities.append(Capability('fixture.release.inspect', (SELECTOR_SCOPE,), (),
                                           {'max_response_bytes':min(SELECTOR_INSPECT_MAX_BYTES, self.limits.max_response_bytes)}))
        available = (not self._hold.is_set() and not self.selector._stop_requested.is_set()
                     and not state['stopped'] and state['pending_command'] is None)
        if available and 'fixture.write' in session.credential.scopes:
            from .safe_replace import SafeReplaceError
            try:
                self.selector.consumer.check_mutation_available()
            except SafeReplaceError as exc:
                if exc.code != 'SAFE_REOPEN_REQUIRES_RECONCILIATION' or exc.outcome_unknown:
                    raise
            else:
                capabilities.append(Capability('fixture.release.activate', (), (SELECTOR_SCOPE,),
                    {'max_payload_bytes':SELECTOR_PAYLOAD_MAX_BYTES,'max_assets':16,'max_references_per_asset':16}))
        self.sessions.check_current(session)
        return Discovery(PROTOCOL_VERSION, SCHEMA_VERSION, SELECTOR_SCHEMA_DIGEST,
                         'gt02-managed-selector', '1.0', self.project_id, tuple(capabilities),
                         {'max_body_bytes':min(self.limits.max_body_bytes, MAX_FRAME_BYTES),
                          'max_response_bytes':min(self.limits.max_response_bytes, MAX_FRAME_BYTES),
                          'max_payload_bytes':SELECTOR_PAYLOAD_MAX_BYTES,
                          'max_inspect_bytes':min(SELECTOR_INSPECT_MAX_BYTES, self.limits.max_response_bytes),
                          'max_pending':1,'max_lease_ttl_ms':30_000,
                          'request_timeout_ms':self.limits.request_timeout_ms})

    def inspect(self, session):
        self._check_open()
        if self._managed_owner is None:
            raise SafetyViolation('SELECTOR_NOT_REGISTERED')
        self._scope(session, 'fixture.read')
        self._check_registration()
        state = self.selector.snapshot()
        def selection(value):
            if value is None:
                return None
            release = value['release']
            return {'generation':value['generation'],'selection_hash':value['selection_hash'],
                    'release_id':release['release_id'] if release else None,
                    'manifest_sha256':release['manifest']['sha256'] if release else None}
        result = {'project_id':self.project_id,'protocol_version':PROTOCOL_VERSION,'schema_digest':SELECTOR_SCHEMA_DIGEST,
                  'generation':state['generation'],'selection_hash':state['selection_hash'],
                  'revisions':state['revisions'],'stopped':state['stopped'],'ready':state['ready'],
                  'pending_command':state['pending_command'],'selected':selection(state['selected']),
                  'last_verified_adopted':selection(state['last_verified_adopted'])}
        self.sessions.check_current(session)
        if len(canonical_bytes(result)) > min(SELECTOR_INSPECT_MAX_BYTES, self.limits.max_response_bytes):
            raise SafetyViolation('SELECTOR_INSPECT_LIMIT')
        return result

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
        allowed = {'/v1/lookup','/v1/cancel','/v1/stop','/v1/inspect'} if control else {'/v1/lease','/v1/commands','/v1/discovery'}
        if route not in allowed:
            raise SafetyViolation('UNSUPPORTED_ROUTE')
        if type(body) is not dict or body.get('project_id') != self.project_id:
            raise SafetyViolation('PROJECT_MISMATCH')
        self.sessions.check_current(session)
        # Reject secret-bearing data before it can become an intent or asset.
        # Redaction must not silently change command identity or content hashes.
        if self.sessions.redact_output(body) != body:
            raise SafetyViolation('SENSITIVE_INPUT_FORBIDDEN')
        if route in ('/v1/discovery','/v1/inspect'):
            _shape(body, ('project_id','protocol_version'))
            if body['protocol_version'] != PROTOCOL_VERSION:
                raise SafetyViolation('UNSUPPORTED_VERSION')
            return self.discovery(session) if route == '/v1/discovery' else self.inspect(session)
        if route == '/v1/lease':
            _shape(body, ('project_id','ttl_ms'))
            self._scope(session, 'fixture.write')
            self._check_registration()
            if self._hold.is_set() or self.selector.snapshot()['stopped']:
                raise SafetyViolation('SELECTOR_STOPPED')
            if self._managed_owner is not None:
                self.selector.consumer.check_mutation_available()
            lease = self.selector.lease(session.credential.session_id, now_ms=epoch_ms(), ttl_ms=body['ttl_ms'])
            with self._state_lock:
                # One current lease exists in the selector, so retain only it.
                self._leases = {session.credential.session_id: lease}
            return {key:lease[key] for key in ('lease_id','fencing_epoch','expires_ms')}
        if route == '/v1/commands':
            self._scope(session, 'fixture.write')
            self._check_registration()
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
                    self._wake.set()  # Publish to the owned pump before response I/O.
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
            self._check_registration()
            return self._lookup(identifier)
        self._scope(session, 'control.stop' if route == '/v1/stop' else 'control.cancel')
        with self._state_lock:
            job = self._job
            if job is not None and (route == '/v1/stop' or job.command_id == identifier):
                job.cancel.set()
        if route == '/v1/stop':
            # Authenticated control must fence the next effect before waiting
            # for a phase's selector/storage locks in registration validation.
            self.selector._stop_requested.set()
        self._check_registration()
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
            self._check_registration()
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

    def serve_one(self, *, deadline=None):
        broker, identifier = self.broker, 'transport.request'
        raw = self.endpoint.read_frame(timeout_ms=broker.limits.request_timeout_ms)
        # Local supervisor budget only, never a wire field. A reader may have
        # waited across expiry while the watchdog was awaiting CPU scheduling.
        if deadline is not None and time.monotonic() >= deadline:
            raise SafetyViolation('SELECTOR_SESSION_DEADLINE')
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
            if deadline is not None and time.monotonic() >= deadline:
                raise SafetyViolation('SELECTOR_SESSION_DEADLINE')
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
        value = result.as_dict() if isinstance(result, (Response, Discovery)) else result
        encoded = broker.sessions.encode_output(value)
        if len(encoded) > min(MAX_FRAME_BYTES, broker.limits.max_response_bytes):
            result = _response(Status.UNKNOWN, 'RESULT_TOO_LARGE', identifier)
            encoded = broker.sessions.encode_output(result.as_dict())
        # Delivery failure propagates to the owned supervisor; never resend or
        # undo a durable intent/receipt to make an I/O error look effect-free.
        self.endpoint.write_frame(encoded, timeout_ms=broker.limits.request_timeout_ms)
        return result

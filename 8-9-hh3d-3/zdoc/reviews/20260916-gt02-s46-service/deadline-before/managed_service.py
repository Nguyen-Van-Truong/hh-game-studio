"""Bounded owned lifecycle for one authenticated managed-fixture pipe session.

The trusted launcher first binds and connects both AppContainer endpoints to
one retained process. This service does not launch arbitrary executables or
own the OS Job. The launcher's Job deadline is the final bound for stalled
native storage calls. A cleanup error retains every resource still in use.
"""
from __future__ import annotations

import threading
import time

from ...protocol.core import canonical_bytes
from .limits import SafetyViolation
from .managed_fixture import ManagedFixtureOwner
from .pipe_endpoint import AppContainerEndpoint
from .selector_pipe import SelectorFixtureBroker, SelectorPipeServer
from .transport import SessionCredential

_SERVICE_BIND = threading.Lock()


class ManagedServiceError(SafetyViolation):
    def __init__(self, code, *, cleanup_owner=None):
        self.outcome_unknown = cleanup_owner is not None
        self.cleanup_owner = cleanup_owner
        super().__init__(code)


class ManagedPipeService:
    """Transfer broker/endpoints after validation; borrow durable storage.

    start() sends credentials only on the verified work channel, then starts
    separate work/control readers and an admission-driven phase pump. The
    caller must close this service before closing its ManagedFixtureOwner.
    """
    def __init__(self, owner, broker, work, control, credential, *,
                 session_timeout_ms=60_000, drain_timeout_ms=2000):
        if (type(owner) is not ManagedFixtureOwner or type(broker) is not SelectorFixtureBroker
                or type(work) is not AppContainerEndpoint or type(control) is not AppContainerEndpoint
                or type(credential) is not SessionCredential):
            raise ManagedServiceError('SERVICE_TRUSTED_COMPONENT_REQUIRED')
        if (type(session_timeout_ms) is not int or not 1 <= session_timeout_ms <= 60_000
                or type(drain_timeout_ms) is not int or not 1 <= drain_timeout_ms <= 5000):
            raise ManagedServiceError('SERVICE_INVALID_LIMIT')
        if (work is control or work.role != 'work' or control.role != 'control'
                or work._package != control._package or work._identity is None
                or work._identity != control._identity):
            raise ManagedServiceError('SERVICE_ENDPOINT_BINDING_MISMATCH')
        self.owner, self.broker = owner, broker
        self.work, self.control, self._credential = work, control, credential
        self._session_ms, self._drain_ms = session_timeout_ms, drain_timeout_ms
        self._state_lock, self._lifecycle = threading.Lock(), threading.Lock()
        self._stop = threading.Event()
        self._threads = []
        self._started = self._closed = self._work_failed = False
        self._reason = None
        self._deadline = None
        with owner._lifecycle_lock, _SERVICE_BIND:
            if (broker._managed_owner is not owner or owner.selector is not broker.selector
                    or owner._service is not None or broker._service_owner is not None
                    or getattr(work, '_managed_service', None) is not None
                    or getattr(control, '_managed_service', None) is not None):
                raise ManagedServiceError('SERVICE_MANAGED_OWNER_REQUIRED')
            broker._check_open()
            broker._check_registration()
            # Validation does not transfer ownership. Any error here leaves
            # endpoints with the trusted caller, including poisoned handles.
            for endpoint in (work, control):
                with endpoint._guard():
                    endpoint._check_peer()
            self._work_server = SelectorPipeServer(work, broker, credential)
            self._control_server = SelectorPipeServer(control, broker, credential)
            owner._service = broker._service_owner = self
            work._managed_service = control._managed_service = self

    def status(self):
        with self._state_lock:
            return {'started':self._started, 'closed':self._closed,
                    'work_failed':self._work_failed, 'session_ended':self._stop.is_set(),
                    'reason':self._reason, 'live_threads':sum(t.is_alive() for t in self._threads)}

    def _end_session(self, reason):
        self.broker._hold.set()
        with self._state_lock:
            if self._reason is None:
                self._reason = reason
            self._stop.set()
        # End every rotation of this locally issued session ID, even when the
        # original bearer expired. No caller-supplied session ID is used here.
        with self.broker.sessions._lock:
            self.broker.sessions._sessions.pop(self._credential.session_id, None)
        self.work.request_stop()
        self.control.request_stop()
        self.broker._wake.set()

    def _fail_work(self):
        self.broker._hold.set()
        with self._state_lock:
            self._work_failed = True
        self.work.request_stop()
        self.broker._wake.set()
        # Control keeps its auth and transport, so lookup/Cancel/Stop remain
        # available. Already admitted synchronous I/O may finish; no next phase.

    def _serve(self, server, is_work):
        try:
            while not self._stop.is_set():
                if time.monotonic() >= self._deadline:
                    self._end_session('SERVICE_SESSION_EXPIRED')
                    return
                server.serve_one()
        except BaseException:
            # Never log raw exception text, frames, credentials or paths.
            if not self._stop.is_set():
                if is_work:
                    self._fail_work()
                else:
                    self._end_session('SERVICE_CONTROL_FAILED')

    def _pump(self):
        try:
            while not self._stop.is_set():
                remaining = self._deadline - time.monotonic()
                if remaining <= 0:
                    self._end_session('SERVICE_SESSION_EXPIRED')
                    return
                self.broker._wake.wait(remaining)
                # Clear before inspecting state, so a concurrent admission
                # either appears below or leaves a new wake for the next loop.
                self.broker._wake.clear()
                while not self._stop.is_set() and not self.broker._hold.is_set():
                    if time.monotonic() >= self._deadline:
                        self._end_session('SERVICE_SESSION_EXPIRED')
                        return
                    with self.broker._state_lock:
                        pending = self.broker._job is not None
                    if not pending:
                        break
                    self.broker.advance()
        except BaseException:
            # Native uncertainty holds work but leaves receipt/Stop control.
            self._fail_work()

    def start(self):
        if not self._lifecycle.acquire(blocking=False):
            raise ManagedServiceError('SERVICE_LIFECYCLE_BUSY', cleanup_owner=self)
        failed = False
        try:
            if self._started or self._closed or self._stop.is_set():
                raise ManagedServiceError('SERVICE_ALREADY_STARTED_OR_CLOSED', cleanup_owner=self)
            self._started = True
            self._deadline = time.monotonic() + self._session_ms / 1000
            try:
                self.broker.sessions.authenticate('Bearer '+self._credential.bearer)
                credential = self._credential
                # Deliberately secret-bearing only on this verified private
                # channel. Never pass through diagnostics/environment/argv.
                frame = canonical_bytes({'schema':'hh-selector-session-1', 'project_id':credential.project_id,
                    'session_id':credential.session_id, 'expires_ms':credential.expires_ms,
                    'scopes':sorted(credential.scopes), 'bearer':credential.bearer})
                self.work.write_frame(frame, timeout_ms=min(self._session_ms, self.broker.limits.request_timeout_ms))
                for name, target, args in (
                    ('pump', self._pump, ()),
                    ('control', self._serve, (self._control_server, False)),
                    ('work', self._serve, (self._work_server, True)),
                ):
                    thread = threading.Thread(target=target, args=args, name='hh-selector-'+name, daemon=False)
                    self._threads.append(thread)
                    thread.start()
            except BaseException:
                failed = True
                self._end_session('SERVICE_START_FAILED')
        finally:
            self._lifecycle.release()
        if failed:
            # close() is explicit and retryable; ownership survives failures
            # even when only some threads were successfully started.
            raise ManagedServiceError('SERVICE_START_FAILED', cleanup_owner=self)
        return self

    def close(self):
        if not self._lifecycle.acquire(blocking=False):
            raise ManagedServiceError('SERVICE_LIFECYCLE_BUSY', cleanup_owner=self)
        try:
            if self._closed:
                return
            self._end_session('SERVICE_CLOSED')
            deadline = time.monotonic() + self._drain_ms / 1000
            for thread in self._threads:
                if thread is threading.current_thread():
                    raise ManagedServiceError('SERVICE_DRAIN_PENDING', cleanup_owner=self)
                if thread.ident is not None:
                    thread.join(max(0, deadline - time.monotonic()))
            if any(thread.is_alive() for thread in self._threads):
                raise ManagedServiceError('SERVICE_DRAIN_PENDING', cleanup_owner=self)
            # Pending native operations retain their exact owner. No storage or
            # broker teardown occurs while either endpoint cleanup is uncertain.
            for endpoint in (self.work, self.control):
                if time.monotonic() >= deadline:
                    raise ManagedServiceError('SERVICE_DRAIN_PENDING', cleanup_owner=self)
                try:
                    endpoint.close()
                except BaseException:
                    raise ManagedServiceError('SERVICE_ENDPOINT_CLEANUP_PENDING', cleanup_owner=self) from None
            with self.owner._lifecycle_lock, _SERVICE_BIND:
                self.broker._service_owner = None
                try:
                    self.broker.close()
                except BaseException:
                    self.broker._service_owner = self
                    raise ManagedServiceError('SERVICE_BROKER_CLEANUP_PENDING', cleanup_owner=self) from None
                self.owner._service = None
                self.work._managed_service = self.control._managed_service = None
                self._closed = True
        finally:
            self._lifecycle.release()

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.close()

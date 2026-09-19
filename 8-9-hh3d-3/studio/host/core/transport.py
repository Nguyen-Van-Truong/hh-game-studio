"""GT-02 authenticated, bounded loopback transport and typed mock client.

Only the fixed ``fixture.inspect``/``fixture.set`` catalog is executable. The
fixture is deliberately in-process state, not an editor, file writer or eval
adapter. Credentials are issued locally, never through HTTP/argv/discovery.
Two listeners reserve connection capacity for Stop/Cancel/lookup when the work
listener is saturated. HTTP compression, chunking, redirects and pipelining
are unsupported. A stopped host cannot be resumed by connecting again.

Requests use Unix epoch milliseconds. Durable admission precedes PENDING;
COMMITTED follows fixture readback and a durable terminal receipt. Lost HTTP
responses and orphaned pending records mean UNKNOWN, never implicit retry.
The fixture does not claim durable engine-state recovery across process exit.
"""
from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
import base64
import hashlib
import hmac
import http.client
from pathlib import Path
import re
import secrets
import socket
import socketserver
import threading
import time
from typing import Any, Mapping

from ...protocol.core import (Capability, Discovery, PROTOCOL_VERSION,
                              Request, Response, SCHEMA_VERSION, Status,
                              ValidationError, canonical_bytes,
                              validate_for_dispatch)
from .journal import Journal, JournalError, Lease
from .limits import (DEFAULT_LIMITS, SafetyViolation, parse_json_utf8,
                     payload_digest, validate_envelope)
from .redaction import RedactedBoundary, RedactionLimits, Redactor


def epoch_ms() -> int:
    return time.time_ns() // 1_000_000


_SCOPES = frozenset({"fixture.read", "fixture.write", "control.stop", "control.cancel"})
_TOKEN = re.compile(r"Bearer ([A-Za-z0-9_-]{43})\Z")
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_TARGET = {"stable_id": "fixture.counter"}
_UNCERTAIN_JOURNAL_CODES = frozenset({
    "JOURNAL_DURABILITY_UNCONFIRMED", "JOURNAL_UNREADABLE", "JOURNAL_WRITE_FAILED",
    "JOURNAL_COMPACT_FAILED", "JOURNAL_RECORD_INVALID", "JOURNAL_TRUNCATED",
    "JOURNAL_CHECKSUM_MISMATCH", "JOURNAL_HISTORY_INVALID", "JOURNAL_PATH_UNSAFE",
})
_SCHEMA = {"schema_version": SCHEMA_VERSION, "operations": {
    "fixture.inspect": {"target": _TARGET, "payload": {}},
    "fixture.set": {"target": _TARGET, "payload": {"value": "int:-1000000..1000000",
                                                       "delay_ms": "int:0..1000"}}}}


@dataclass(frozen=True)
class TransportLimits:
    max_header_bytes: int = 8192
    max_header_count: int = 24
    max_body_bytes: int = DEFAULT_LIMITS.max_envelope_bytes
    max_response_bytes: int = DEFAULT_LIMITS.max_result_bytes
    max_connections: int = 8
    max_control_connections: int = 2
    max_pending: int = 16
    max_sessions: int = 16
    max_session_history: int = 64
    max_session_ttl_ms: int = 15 * 60 * 1000
    request_timeout_ms: int = 1000
    readback_timeout_ms: int = 2000
    max_diagnostics: int = 32

    def __post_init__(self) -> None:
        if any(type(value) is not int or value <= 0 for value in asdict(self).values()):
            raise SafetyViolation("INVALID_TRANSPORT_LIMITS")
        if (self.max_body_bytes > DEFAULT_LIMITS.max_envelope_bytes or self.max_response_bytes < 512
                or self.max_session_history > 127):
            raise SafetyViolation("INVALID_TRANSPORT_LIMITS")


@dataclass(frozen=True)
class SessionCredential:
    session_id: str
    project_id: str
    expires_ms: int
    scopes: frozenset[str]
    bearer: str = field(repr=False)


@dataclass(frozen=True)
class _Session:
    credential: SessionCredential
    verifier: bytes = field(repr=False)
    redactor: Redactor = field(repr=False)


class SessionAuthority:
    """Bounded local issuer. Rotation invalidates the old bearer immediately."""

    def __init__(self, project_id: str, project_root: Path, limits: TransportLimits) -> None:
        self.project_id, self.project_root, self.limits = project_id, project_root, limits
        self._sessions: dict[str, _Session] = {}
        self._lock = threading.RLock()
        # Invalidating authentication does not make an old bearer public data.
        # Keep every issued secret for this host lifetime; deny issuance at the
        # bounded budget instead of forgetting one and later persisting it.
        self._issued: list[str] = []
        self._output_redactor = Redactor(host_paths=(str(project_root),))

    def issue(self, *, scopes: frozenset[str] = frozenset({"fixture.read"}),
              ttl_ms: int = 60_000) -> SessionCredential:
        if (type(ttl_ms) is not int or not 0 < ttl_ms <= self.limits.max_session_ttl_ms
                or not isinstance(scopes, frozenset) or not scopes <= _SCOPES):
            raise SafetyViolation("INVALID_SESSION_POLICY")
        with self._lock:
            now = epoch_ms()
            self._sessions = {key: item for key, item in self._sessions.items()
                              if item.credential.expires_ms > now}
            if len(self._sessions) >= self.limits.max_sessions:
                raise SafetyViolation("SESSION_LIMIT")
            return self._mint("session." + secrets.token_hex(16), scopes, now + ttl_ms)

    def _mint(self, session_id: str, scopes: frozenset[str], expires_ms: int) -> SessionCredential:
        if len(self._issued) >= self.limits.max_session_history:
            raise SafetyViolation("CREDENTIAL_HISTORY_LIMIT")
        bearer = secrets.token_urlsafe(32)
        registered = set()
        for issued in (*self._issued, bearer):
            registered.update((issued, base64.b64encode(issued.encode()).decode().rstrip("="),
                               base64.urlsafe_b64encode(issued.encode()).decode().rstrip("=")))
        redactor = Redactor(secrets=sorted(registered), host_paths=(str(self.project_root),),
            limits=RedactionLimits(max_secrets=3 * self.limits.max_session_history + 1))
        credential = SessionCredential(session_id, self.project_id, expires_ms, scopes, bearer)
        self._sessions[session_id] = _Session(
            credential, hashlib.sha256(bearer.encode("ascii")).digest(),
            Redactor(secrets=(bearer,), host_paths=(str(self.project_root),)))
        self._issued.append(bearer)
        self._output_redactor = redactor
        return credential

    def rotate(self, credential: SessionCredential, *, ttl_ms: int = 60_000) -> SessionCredential:
        if type(ttl_ms) is not int or not 0 < ttl_ms <= self.limits.max_session_ttl_ms:
            raise SafetyViolation("INVALID_SESSION_POLICY")
        with self._lock:
            session = self.authenticate("Bearer " + credential.bearer)
            return self._mint(session.credential.session_id, session.credential.scopes, epoch_ms() + ttl_ms)

    def revoke(self, credential: SessionCredential) -> None:
        with self._lock:
            session = self.authenticate("Bearer " + credential.bearer)
            self._sessions.pop(session.credential.session_id, None)

    def authenticate(self, authorization: str) -> _Session:
        match = _TOKEN.fullmatch(authorization)
        if not match:
            raise SafetyViolation("AUTH_REQUIRED")
        verifier = hashlib.sha256(match.group(1).encode("ascii")).digest()
        with self._lock:
            for session in self._sessions.values():
                if hmac.compare_digest(session.verifier, verifier):
                    if session.credential.expires_ms <= epoch_ms():
                        raise SafetyViolation("SESSION_EXPIRED")
                    return session
        raise SafetyViolation("AUTH_REQUIRED")

    def check_current(self, session: _Session) -> None:
        with self._lock:
            if (self._sessions.get(session.credential.session_id) is not session
                    or session.credential.expires_ms <= epoch_ms()):
                raise SafetyViolation("SESSION_INVALIDATED")

    @contextmanager
    def apply_authorization(self, session: _Session):
        """Linearize revocation against the fixture's bounded atomic effect."""
        with self._lock:
            self.check_current(session)
            yield

    def validate_public_identifier(self, identifier: str) -> None:
        # Command IDs are persisted as journal metadata. Do not accept a live
        # credential disguised as an otherwise valid public identifier, and do
        # not silently redact an ID into a different command identity.
        with self._lock:
            if self._output_redactor.redact(identifier) != identifier:
                raise SafetyViolation("SENSITIVE_IDENTIFIER_FORBIDDEN")

    def redact_output(self, value: Any) -> Any:
        with self._lock:
            return self._output_redactor.redact(value)

    def encode_output(self, value: Any) -> bytes:
        with self._lock:
            return self._output_redactor.encode(value)


@dataclass
class FixtureState:
    """Mock engine object; the host owns its writes while running."""
    value: int = 0
    revision: int = 0
    effect_count: int = 0

    def snapshot(self) -> dict[str, Any]:
        return {"value": self.value, "revision": "rev-" + str(self.revision),
                "effect_count": self.effect_count}


@dataclass
class FixtureFaults:
    """Trusted local test controls; these are never part of the wire catalog."""
    readback_gate: threading.Event | None = None
    applied: threading.Event = field(default_factory=threading.Event)
    drop_submit_response_once: bool = False
    disconnect_once: tuple[str, str] | None = None
    disconnect_observed: threading.Event = field(default_factory=threading.Event)
    disconnected_status: str | None = None


@dataclass
class _Job:
    request: Request
    lease: Lease | None
    session: _Session
    cancel: threading.Event = field(default_factory=threading.Event)
    phase: str = "QUEUED"


class _Listener(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = False
    daemon_threads = True
    block_on_close = False
    request_queue_size = 8

    def __init__(self, owner: "LoopbackFixtureHost", control: bool) -> None:
        self.owner, self.control = owner, control
        self.slots = threading.BoundedSemaphore(owner.limits.max_control_connections
                                               if control else owner.limits.max_connections)
        super().__init__(("127.0.0.1", 0), _Handler)

    def process_request(self, request: socket.socket, client_address: Any) -> None:
        if not self.slots.acquire(blocking=False):
            request.settimeout(0.05)
            try:
                self.owner._send(request, _response(Status.REJECTED, "CONNECTION_LIMIT"), 429)
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request: socket.socket, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def handle_error(self, request: socket.socket, client_address: Any) -> None:
        self.owner._diagnostic("TRANSPORT_HANDLER_FAILED")


class _Handler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        self.server.owner._handle(self.request, self.server)  # type: ignore[attr-defined]


def _response(status: Status, code: str, command_id: str = "transport.request",
              **postconditions: Any) -> Response:
    return Response(status, code, command_id, postconditions=postconditions)


class LoopbackFixtureHost:
    """One project, fixed operation catalog, one worker, two bounded listeners."""

    def __init__(self, project_id: str, project_root: Path, journal: Journal, *,
                 limits: TransportLimits = TransportLimits(),
                 allowed_origins: frozenset[str] = frozenset(),
                 fixture: FixtureState | None = None, faults: FixtureFaults | None = None) -> None:
        if not _IDENTIFIER.fullmatch(project_id) or not project_root.is_dir() or project_root.is_symlink():
            raise SafetyViolation("INVALID_PROJECT")
        if (not isinstance(allowed_origins, frozenset)
                or any(not re.fullmatch(r"http://127\.0\.0\.1:[1-9][0-9]{0,4}", item)
                       for item in allowed_origins)):
            raise SafetyViolation("INVALID_ORIGIN_POLICY")
        self.project_id, self.project_root = project_id, project_root.resolve(strict=True)
        self.journal, self.limits, self.allowed_origins = journal, limits, allowed_origins
        self.sessions = SessionAuthority(project_id, self.project_root, limits)
        self.fixture, self.faults = fixture or FixtureState(), faults or FixtureFaults()
        self._lock = threading.RLock()
        # Fault controls are local test seams. They must not serialize a
        # read-only transport request behind host state or journal work.
        self._disconnect_lock = threading.Lock()
        self._wake, self._closing, self._stopped = threading.Event(), threading.Event(), threading.Event()
        self._queue: deque[_Job] = deque()
        self._jobs: dict[str, _Job] = {}
        # Published only by the host lock and never mutated in place. Lookup
        # can read this immutable-by-convention snapshot without waiting for
        # a worker that is finishing a durable terminal record.
        self._pending_snapshot: dict[str, tuple[Response, int]] = {}
        self._leases: dict[str, Lease] = {}
        self._stop_commands: dict[str, str] = {}
        self._diagnostics: deque[bytes] = deque(maxlen=limits.max_diagnostics)
        self._redactor = Redactor(host_paths=(str(self.project_root),))
        self._boundary = RedactedBoundary(self._diagnostics.append, redactor=self._redactor)
        self._main = _Listener(self, False)
        try:
            self._control = _Listener(self, True)
        except BaseException:
            self._main.server_close()
            raise
        self._threads: list[threading.Thread] = []

    @property
    def port(self) -> int:
        return self._main.server_address[1]

    @property
    def control_port(self) -> int:
        return self._control.server_address[1]

    @property
    def diagnostics(self) -> tuple[bytes, ...]:
        return tuple(self._diagnostics)

    def _diagnostic(self, code: str) -> None:
        safe_code = code if re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", code) else "TRANSPORT_ERROR"
        self._boundary.emit("log", {"code": safe_code})

    def start(self) -> "LoopbackFixtureHost":
        if self._threads or self._closing.is_set():
            raise SafetyViolation("HOST_ALREADY_STARTED")
        for target in (lambda: self._main.serve_forever(poll_interval=0.05),
                       lambda: self._control.serve_forever(poll_interval=0.05), self._worker):
            thread = threading.Thread(target=target, daemon=True, name="gt02-fixture")
            self._threads.append(thread)
            thread.start()
        return self

    def close(self) -> None:
        self._stopped.set()
        self._closing.set()
        self._wake.set()
        if self._threads:
            self._main.shutdown()
            self._control.shutdown()
        self._main.server_close()
        self._control.server_close()
        for thread in self._threads:
            thread.join(self.limits.readback_timeout_ms / 1000 + 2)
        if any(thread.is_alive() for thread in self._threads):
            raise SafetyViolation("HOST_DRAIN_TIMEOUT")

    def __enter__(self) -> "LoopbackFixtureHost":
        return self.start()

    def __exit__(self, *_: Any) -> None:
        self.close()

    def discovery(self, session: _Session) -> Discovery:
        capabilities = []
        if "fixture.read" in session.credential.scopes:
            capabilities.append(Capability("fixture.inspect", ("fixture.counter",)))
        if "fixture.write" in session.credential.scopes:
            capabilities.append(Capability("fixture.set", (), ("fixture.counter",)))
        return Discovery(PROTOCOL_VERSION, SCHEMA_VERSION,
                         "sha256:" + hashlib.sha256(canonical_bytes(_SCHEMA)).hexdigest(),
                         "gt02-fixture", "1.0", self.project_id, tuple(capabilities), asdict(self.limits))

    def _read_request(self, stream: socket.socket) -> tuple[str, dict[str, str], bytes]:
        end = time.monotonic() + self.limits.request_timeout_ms / 1000
        buffer = bytearray()
        while b"\r\n\r\n" not in buffer:
            remaining = end - time.monotonic()
            if remaining <= 0:
                raise SafetyViolation("REQUEST_TIMEOUT")
            stream.settimeout(remaining)
            chunk = stream.recv(min(4096, self.limits.max_header_bytes + 1 - len(buffer)))
            if not chunk:
                raise SafetyViolation("INCOMPLETE_REQUEST")
            buffer.extend(chunk)
            marker = buffer.find(b"\r\n\r\n")
            if (marker < 0 and len(buffer) > self.limits.max_header_bytes
                    or marker >= 0 and marker + 4 > self.limits.max_header_bytes):
                raise SafetyViolation("HEADER_TOO_LARGE")
        header, initial_body = bytes(buffer).split(b"\r\n\r\n", 1)
        try:
            lines = header.decode("ascii", "strict").split("\r\n")
        except UnicodeError:
            raise SafetyViolation("INVALID_HEADER") from None
        parts = lines[0].split(" ")
        if len(parts) != 3 or parts[0] != "POST" or parts[2] != "HTTP/1.1":
            raise SafetyViolation("UNSUPPORTED_HTTP")
        path = parts[1]
        if len(lines) - 1 > self.limits.max_header_count:
            raise SafetyViolation("HEADER_COUNT_LIMIT")
        headers: dict[str, str] = {}
        for line in lines[1:]:
            key, separator, value = line.partition(":")
            key = key.lower()
            if (not separator or not re.fullmatch(r"[a-z0-9-]+", key) or key in headers
                    or any(ord(char) < 32 or ord(char) == 127 for char in value)):
                raise SafetyViolation("INVALID_HEADER")
            headers[key] = value.strip(" ")
        if ("transfer-encoding" in headers or "expect" in headers
                or headers.get("content-encoding", "identity") != "identity"):
            raise SafetyViolation("UNSUPPORTED_ENCODING")
        length_text = headers.get("content-length", "")
        if not re.fullmatch(r"0|[1-9][0-9]{0,8}", length_text):
            raise SafetyViolation("INVALID_CONTENT_LENGTH")
        length = int(length_text)
        if length > self.limits.max_body_bytes:
            raise SafetyViolation("ENVELOPE_TOO_LARGE")
        if headers.get("content-type") != "application/json":
            raise SafetyViolation("UNSUPPORTED_CONTENT_TYPE")
        # Every size/encoding gate above is enforced before auth or JSON parse.
        if len(initial_body) > length:
            raise SafetyViolation("PIPELINING_UNSUPPORTED")
        if headers.get("host") not in {f"127.0.0.1:{self.port}", f"127.0.0.1:{self.control_port}"}:
            raise SafetyViolation("HOST_REJECTED")
        if "origin" in headers and headers["origin"] not in self.allowed_origins:
            raise SafetyViolation("ORIGIN_REJECTED")
        self.sessions.authenticate(headers.get("authorization", ""))
        body = bytearray(initial_body)
        while len(body) < length:
            remaining = end - time.monotonic()
            if remaining <= 0:
                raise SafetyViolation("REQUEST_TIMEOUT")
            stream.settimeout(remaining)
            chunk = stream.recv(min(4096, length - len(body)))
            if not chunk:
                raise SafetyViolation("INCOMPLETE_REQUEST")
            body.extend(chunk)
        return path, headers, bytes(body)

    def _send(self, stream: socket.socket, value: Response | Discovery | dict[str, Any],
              status: int = 200, redactor: Redactor | None = None) -> None:
        body = self.sessions.encode_output(value.as_dict() if hasattr(value, "as_dict") else value)
        if len(body) > self.limits.max_response_bytes:
            status, body = 413, self._redactor.encode(_response(Status.REJECTED, "RESULT_TOO_LARGE").as_dict())
        header = (f"HTTP/1.1 {status} Result\r\nContent-Type: application/json\r\n"
                  f"Content-Length: {len(body)}\r\nConnection: close\r\n"
                  "Cache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n\r\n").encode("ascii")
        stream.settimeout(self.limits.request_timeout_ms / 1000)
        stream.sendall(header + body)
        # A pre-auth rejection may precede the client's body bytes. On Windows
        # closing with unread bytes can reset away an otherwise valid reply.
        # Half-close the response then drain only bounded bytes/time; never
        # parse, decompress or retain an unauthenticated body.
        stream.shutdown(socket.SHUT_WR)
        end = time.monotonic() + min(.05, self.limits.request_timeout_ms / 1000)
        remaining_bytes = self.limits.max_body_bytes
        while remaining_bytes and time.monotonic() < end:
            stream.settimeout(max(.001, end - time.monotonic()))
            try:
                chunk = stream.recv(min(4096, remaining_bytes))
            except (OSError, TimeoutError):
                break
            if not chunk:
                break
            remaining_bytes -= len(chunk)

    def _disconnect_probe(self, path: str, phase: str, result: Any = None) -> bool:
        """Local fixture fault only; closing here cuts a real HTTP connection.

        The peer sees EOF before a reply, or a complete reply when the cut is
        after sendall. No wire field can arm this probe or grant an operation.
        """
        with self._disconnect_lock:
            if self.faults.disconnect_once != (path, phase):
                return False
            self.faults.disconnect_once = None
            self.faults.disconnected_status = result.status.value if isinstance(result, Response) else None
            self.faults.disconnect_observed.set()
            return True

    def _handle(self, stream: socket.socket, listener: _Listener) -> None:
        session: _Session | None = None
        safe_command_id = "transport.request"
        try:
            path, headers, raw = self._read_request(stream)
            session = self.sessions.authenticate(headers.get("authorization", ""))
            body = parse_json_utf8(raw)
            # Only echo an identifier after the same public-ID redaction check
            # used by dispatch. A malformed or sensitive value stays generic.
            candidate_id = body.get("command_id") if isinstance(body, dict) else None
            if isinstance(candidate_id, str) and _IDENTIFIER.fullmatch(candidate_id):
                try:
                    self.sessions.validate_public_identifier(candidate_id)
                except SafetyViolation:
                    pass
                else:
                    safe_command_id = candidate_id
            if self._disconnect_probe(path, "before_dispatch"):
                return
            result = self._dispatch(path, body, session, listener.control)
            if self._disconnect_probe(path, "after_dispatch", result):
                return
            if path == "/v1/commands" and self.faults.drop_submit_response_once:
                with self._lock:
                    self.faults.drop_submit_response_once = False
                return  # Deliberately lost network response; admission is already durable.
            if self._disconnect_probe(path, "before_reply", result):
                return
            self._send(stream, result, redactor=session.redactor)
            self._disconnect_probe(path, "after_reply", result)
        except JournalError as exc:
            try:
                result, status = self._journal_failure(exc, safe_command_id)
                self._send(stream, result, status, session.redactor if session else None)
            except OSError:
                pass
        except (SafetyViolation, ValidationError) as exc:
            self._diagnostic(exc.code)
            try:
                self._send(stream, _response(Status.REJECTED, exc.code, safe_command_id), 400,
                           session.redactor if session else None)
            except OSError:
                pass
        except (OSError, TimeoutError):
            self._diagnostic("TRANSPORT_DISCONNECTED")
        except Exception:
            self._diagnostic("TRANSPORT_FAILED")
            try:
                self._send(stream, _response(Status.UNKNOWN, "TRANSPORT_FAILED"), 500)
            except OSError:
                pass

    def _journal_failure(self, exc: JournalError, command_id: str) -> tuple[Response, int]:
        """Shared HTTP/pipe phase semantics; transport choice cannot erase UNKNOWN."""
        self._diagnostic(exc.code)
        uncertain = exc.outcome_unknown or exc.code in _UNCERTAIN_JOURNAL_CODES
        if uncertain:
            self._stopped.set()
        details = {"accepting_work": False, "next_action": "lookup.reconcile"} if uncertain else {}
        return (_response(Status.UNKNOWN if uncertain else Status.REJECTED, exc.code, command_id, **details),
                503 if uncertain else 400)

    @staticmethod
    def _shape(body: Any, keys: set[str]) -> None:
        if not isinstance(body, dict) or set(body) != keys:
            raise SafetyViolation("INVALID_ENVELOPE")

    def _dispatch(self, path: str, body: Any, session: _Session, control: bool) -> Response | Discovery | dict[str, Any]:
        control_paths = {"/v1/stop", "/v1/cancel", "/v1/lookup", "/v1/archive"}
        work_paths = {"/v1/discovery", "/v1/lease", "/v1/commands"}
        if path not in (control_paths if control else work_paths):
            raise SafetyViolation("UNSUPPORTED_ROUTE")
        if not isinstance(body, dict) or body.get("project_id") != self.project_id:
            raise SafetyViolation("PROJECT_MISMATCH")
        # Read-only lookup can answer a known pending admission from the
        # published snapshot without waiting behind worker journal I/O.
        self.sessions.check_current(session)
        if path == "/v1/lookup":
            self._shape(body, {"project_id", "command_id"})
            command_id = body["command_id"]
            if not isinstance(command_id, str) or not _IDENTIFIER.fullmatch(command_id):
                raise SafetyViolation("INVALID_COMMAND_ID")
            self.sessions.validate_public_identifier(command_id)
            self._scope(session, "fixture.read")
            return self._lookup(command_id)
        with self._lock:
            if path == "/v1/discovery":
                self._shape(body, {"project_id", "protocol_version"})
                if body["protocol_version"] != PROTOCOL_VERSION:
                    raise SafetyViolation("UNSUPPORTED_VERSION")
                return self.discovery(session)
            if path == "/v1/lease":
                self._shape(body, {"project_id", "ttl_ms"})
                self._scope(session, "fixture.write")
                if self._stopped.is_set():
                    raise SafetyViolation("HOST_STOPPED")
                lease = self.journal.acquire_lease(project_id=self.project_id,
                    target="fixture.counter", owner=session.credential.session_id,
                    now_ms=epoch_ms(), ttl_ms=body["ttl_ms"])
                self._leases = {key: item for key, item in self._leases.items()
                                if item.expires_ms > epoch_ms()}
                self._leases[session.credential.session_id] = lease
                return {"lease_id": lease.owner, "fencing_epoch": lease.fencing_epoch,
                        "expires_ms": lease.expires_ms, "revision": self.fixture.snapshot()["revision"]}
            if path in control_paths:
                self._shape(body, {"project_id", "command_id"})
                command_id = body["command_id"]
                if not isinstance(command_id, str) or not _IDENTIFIER.fullmatch(command_id):
                    raise SafetyViolation("INVALID_COMMAND_ID")
                self.sessions.validate_public_identifier(command_id)
                if path == "/v1/archive":
                    self._scope(session, "fixture.read")
                    return self._archive(command_id)
                self._scope(session, "control.stop" if path == "/v1/stop" else "control.cancel")
                return self._stop(command_id) if path == "/v1/stop" else self._cancel(command_id)
            return self._submit(body, session)

    @staticmethod
    def _scope(session: _Session, scope: str) -> None:
        if scope not in session.credential.scopes:
            raise SafetyViolation("SCOPE_DENIED")

    def _lookup(self, command_id: str, *, fast_pending: bool = True) -> Response:
        if fast_pending:
            pending = self._pending_snapshot.get(command_id)
            if pending is not None and epoch_ms() <= pending[1]:
                return pending[0]
        receipt = self.journal.lookup(project_id=self.project_id, command_id=command_id, now_ms=epoch_ms())["receipt"]
        result = Response.from_dict(receipt)
        if result.status is Status.ACCEPTED_PENDING:
            # Admission may have been durably written just before its
            # snapshot publication. Recheck the published view before
            # classifying a record as an orphan.
            pending = self._pending_snapshot.get(command_id)
            if (fast_pending and pending is not None and epoch_ms() <= pending[1]):
                return pending[0]
            return _response(Status.UNKNOWN, "RECOVERY_REQUIRED", command_id,
                             request_digest=result.postconditions.get("request_digest"), next_action="lookup.reconcile")
        return result

    def _existing(self, command_id: str, digest: str) -> Response | None:
        try:
            existing = self._lookup(command_id, fast_pending=False)
        except JournalError as exc:
            if exc.code == "COMMAND_NOT_FOUND":
                return None
            raise
        if existing.postconditions.get("request_digest") != digest:
            raise SafetyViolation("COMMAND_ID_PAYLOAD_CONFLICT")
        return existing

    def _archive(self, command_id: str) -> dict[str, Any]:
        record = self.journal.lookup_archive(project_id=self.project_id, command_id=command_id, now_ms=epoch_ms())
        original = Response.from_dict(record["receipt"])
        if (original.command_id != command_id or original.status.value != record["status"]
                or original.postconditions.get("request_digest") != record["digest"]):
            raise SafetyViolation("ARCHIVE_RECEIPT_MISMATCH")
        # Preserve original evidence, but an expired intent is not a terminal
        # result. Returning UNKNOWN cannot enable resubmission of the old ID.
        resolved = original
        if original.status is Status.ACCEPTED_PENDING:
            resolved = _response(Status.UNKNOWN, "RECOVERY_REQUIRED", command_id,
                request_digest=record["digest"], next_action="lookup.reconcile")
        return {**record, "receipt": resolved.as_dict(), "original_receipt": original.as_dict()}

    def _submit(self, body: dict[str, Any], session: _Session) -> Response:
        request = Request.from_dict(body)
        self.sessions.validate_public_identifier(request.command_id)
        validate_for_dispatch(request, self.discovery(session))
        if request.target != _TARGET:
            raise SafetyViolation("TARGET_OUTSIDE_SCOPE")
        if request.operation == "fixture.set":
            if (set(request.payload) != {"value", "delay_ms"}
                    or type(request.payload["value"]) is not int or abs(request.payload["value"]) > 1_000_000
                    or type(request.payload["delay_ms"]) is not int or not 0 <= request.payload["delay_ms"] <= 1000):
                raise SafetyViolation("INVALID_FIXTURE_PAYLOAD")
        elif request.payload:
            raise SafetyViolation("INVALID_FIXTURE_PAYLOAD")
        existing = self._existing(request.command_id, request.digest)
        if existing is not None:
            return existing
        validate_envelope(body, now_ms=epoch_ms())
        if self._stopped.is_set():
            raise SafetyViolation("HOST_STOPPED")
        if len(self._jobs) >= self.limits.max_pending or len(self._queue) >= self.limits.max_pending:
            raise SafetyViolation("QUEUE_FULL")
        lease = self._leases.get(session.credential.session_id) if request.operation == "fixture.set" else None
        if request.operation == "fixture.set":
            if lease is None or request.lease_id != lease.owner or request.fencing_epoch != lease.fencing_epoch:
                raise SafetyViolation("STALE_LEASE")
            self.journal.check_lease(lease, now_ms=epoch_ms())
            self.journal.check_revision(expected_revision=request.expected_revision,
                                        current_revision=self.fixture.snapshot()["revision"])
        pending = _response(Status.ACCEPTED_PENDING, "QUEUED", request.command_id, request_digest=request.digest)
        admitted_ms = epoch_ms()
        self.journal.append_command(project_id=self.project_id, command_id=request.command_id,
            digest=request.digest, receipt=self.sessions.redact_output(pending.as_dict()), now_ms=admitted_ms, pending=True)
        self._pending_snapshot = {**self._pending_snapshot, request.command_id:
                                  (pending, admitted_ms + self.journal.limits.retry_horizon_ms)}
        job = _Job(request, lease, session)
        self._jobs[request.command_id] = job
        self._queue.append(job)
        self._wake.set()
        return pending

    def _stop(self, command_id: str) -> Response:
        digest = "sha256:" + hashlib.sha256(canonical_bytes({"operation": "control.stop", "project_id": self.project_id})).hexdigest()
        try:
            existing = self._existing(command_id, digest)
        except JournalError:
            self._stopped.set()
            self._wake.set()
            self._diagnostic("STOP_DURABILITY_UNKNOWN")
            return _response(Status.UNKNOWN, "STOP_DURABILITY_UNKNOWN", command_id,
                             accepting_work=False, stopped_in_memory=True, next_action="lookup.reconcile")
        if existing is not None:
            return existing
        if len(self._stop_commands) >= self.limits.max_pending:
            raise SafetyViolation("STOP_COMMAND_LIMIT")
        pending = _response(Status.ACCEPTED_PENDING, "STOP_DRAINING", command_id,
                            request_digest=digest, accepting_work=False)
        # Human Stop still closes admission when storage is full. The returned
        # UNKNOWN explicitly avoids claiming a durable Stop receipt.
        self._stopped.set()
        self._wake.set()
        admitted_ms = epoch_ms()
        try:
            self.journal.append_command(project_id=self.project_id, command_id=command_id,
                digest=digest, receipt=self.sessions.redact_output(pending.as_dict()), now_ms=admitted_ms, pending=True)
        except JournalError:
            self._diagnostic("STOP_DURABILITY_UNKNOWN")
            return _response(Status.UNKNOWN, "STOP_DURABILITY_UNKNOWN", command_id,
                             accepting_work=False, stopped_in_memory=True, next_action="lookup.reconcile")
        self._pending_snapshot = {**self._pending_snapshot, command_id:
                                  (pending, admitted_ms + self.journal.limits.retry_horizon_ms)}
        self._stop_commands[command_id] = digest
        return pending

    def _cancel(self, command_id: str) -> Response:
        existing = self._lookup(command_id)
        job = self._jobs.get(command_id)
        if job is None:
            return existing
        if job.phase == "APPLIED":
            return _response(Status.UNKNOWN, "CANCEL_TOO_LATE_LOOKUP", command_id, next_action="lookup")
        job.cancel.set()
        canceled = _response(Status.CANCELED, "CANCELED_BEFORE_APPLY", command_id,
                             request_digest=job.request.digest, no_effect=True)
        self._finish(job, canceled)
        if job in self._queue:
            self._queue.remove(job)
        self._wake.set()
        return canceled

    def _finish(self, job: _Job, response: Response) -> None:
        self.journal.finish_command(project_id=self.project_id, command_id=job.request.command_id,
            status=response.status.value, receipt=self.sessions.redact_output(response.as_dict()), now_ms=epoch_ms())
        job.phase = "TERMINAL"
        self._jobs.pop(job.request.command_id, None)
        pending = dict(self._pending_snapshot)
        pending.pop(job.request.command_id, None)
        self._pending_snapshot = pending

    def _worker(self) -> None:
        while True:
            self._wake.wait(0.1)
            self._wake.clear()
            with self._lock:
                job = self._queue.popleft() if self._queue else None
            if job is not None:
                try:
                    self._execute(job)
                except Exception:
                    # No success ACK on durable write/readback failure. Lookup
                    # becomes UNKNOWN; reconnect must reconcile, never reapply.
                    with self._lock:
                        self._jobs.pop(job.request.command_id, None)
                        pending = dict(self._pending_snapshot)
                        pending.pop(job.request.command_id, None)
                        self._pending_snapshot = pending
                        self._stopped.set()
                    self._diagnostic("FIXTURE_RECOVERY_REQUIRED")
                self._wake.set()
                continue
            with self._lock:
                if not self._jobs:
                    for command_id, digest in list(self._stop_commands.items()):
                        terminal = _response(Status.COMMITTED, "STOPPED", command_id,
                                             request_digest=digest, accepting_work=False, active=0, pending=0)
                        try:
                            self.journal.finish_command(project_id=self.project_id, command_id=command_id,
                                status=terminal.status.value, receipt=self.sessions.redact_output(terminal.as_dict()),
                                now_ms=epoch_ms())
                        except Exception:
                            self._diagnostic("STOP_RECOVERY_REQUIRED")
                        del self._stop_commands[command_id]
                        pending = dict(self._pending_snapshot)
                        pending.pop(command_id, None)
                        self._pending_snapshot = pending
            if self._closing.is_set():
                return

    def _execute(self, job: _Job) -> None:
        request = job.request
        with self._lock:
            if job.phase == "TERMINAL":
                return
            job.phase = "ACTIVE"
        end = time.monotonic() + request.payload.get("delay_ms", 0) / 1000
        while time.monotonic() < end and not job.cancel.is_set() and not self._stopped.is_set():
            job.cancel.wait(min(0.01, max(0, end - time.monotonic())))
        with self._lock:
            if job.phase == "TERMINAL":
                return
            if self._stopped.is_set() or job.cancel.is_set():
                self._finish(job, _response(Status.CANCELED, "CANCELED_BEFORE_APPLY", request.command_id,
                             request_digest=request.digest, no_effect=True))
                return
            if epoch_ms() >= request.deadline_ms:
                self._finish(job, _response(Status.REJECTED, "DEADLINE_BEFORE_APPLY", request.command_id,
                             request_digest=request.digest, no_effect=True))
                return
            if job.lease is None:
                try:
                    with self.sessions.apply_authorization(job.session):
                        self._scope(job.session, "fixture.read")
                        job.phase = "APPLIED"
                except SafetyViolation as exc:
                    self._finish(job, _response(Status.REJECTED, exc.code, request.command_id,
                                 request_digest=request.digest, no_effect=True))
                    return
            if job.lease is not None:
                effect_started = False
                try:
                    with self.journal.lease_guard(job.lease, now_ms=epoch_ms()):
                        self.journal.check_revision(expected_revision=request.expected_revision,
                                                    current_revision=self.fixture.snapshot()["revision"])
                        with self.sessions.apply_authorization(job.session):
                            if epoch_ms() >= request.deadline_ms:
                                raise SafetyViolation("DEADLINE_BEFORE_APPLY")
                            if epoch_ms() >= job.lease.expires_ms:
                                raise SafetyViolation("STALE_LEASE")
                            # A guard-exit or partially applied setter failure
                            # cannot turn an effect into REJECTED/no_effect.
                            effect_started = True
                            self.fixture.value = request.payload["value"]
                            self.fixture.revision += 1
                            self.fixture.effect_count += 1
                except (JournalError, SafetyViolation) as exc:
                    if (effect_started or isinstance(exc, JournalError)
                            and (exc.outcome_unknown or exc.code in _UNCERTAIN_JOURNAL_CODES)):
                        raise  # Worker closes admission; durable pending needs reconciliation.
                    self._finish(job, _response(Status.REJECTED, exc.code, request.command_id,
                                 request_digest=request.digest, no_effect=True))
                    return
            job.phase = "APPLIED"
            self.faults.applied.set()
        if self.faults.readback_gate is not None:
            if not self.faults.readback_gate.wait(self.limits.readback_timeout_ms / 1000):
                raise SafetyViolation("READBACK_TIMEOUT")
        with self._lock:
            snapshot = self.fixture.snapshot()
            if job.lease is not None and snapshot["value"] != request.payload["value"]:
                raise SafetyViolation("READBACK_FAILED")
            committed = Response(Status.COMMITTED, "READBACK_CONFIRMED", request.command_id,
                snapshot["revision"], "sha256:" + hashlib.sha256(canonical_bytes(snapshot)).hexdigest(),
                {"request_digest": request.digest, "snapshot": snapshot})
            self._finish(job, committed)


@dataclass(frozen=True)
class FixtureLease:
    lease_id: str
    fencing_epoch: int
    expires_ms: int
    revision: str


@dataclass(frozen=True)
class ArchivedResult:
    """Read-only historical evidence, never an execution authorization."""
    receipt: Response
    original_receipt: Response
    original_status: Status
    digest: str
    created_ms: int
    expires_ms: int
    archived: bool = True
    execution_permitted: bool = False

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ArchivedResult":
        required = {"receipt", "original_receipt", "status", "digest", "created_ms",
                    "expires_ms", "archived", "execution_permitted"}
        if (set(value) != required or value["archived"] is not True
                or value["execution_permitted"] is not False
                or type(value["created_ms"]) is not int or type(value["expires_ms"]) is not int
                or not 0 <= value["created_ms"] <= value["expires_ms"] <= (1 << 53) - 1):
            raise SafetyViolation("INVALID_ARCHIVE_RESPONSE")
        original = Response.from_dict(value["original_receipt"])
        receipt = Response.from_dict(value["receipt"])
        if (original.status.value != value["status"]
                or original.command_id != receipt.command_id
                or original.postconditions.get("request_digest") != value["digest"]
                or not isinstance(value["digest"], str)
                or not re.fullmatch(r"sha256:[0-9a-f]{64}", value["digest"])
                or original.status is Status.ACCEPTED_PENDING and receipt.status is not Status.UNKNOWN
                or original.status is not Status.ACCEPTED_PENDING and receipt != original):
            raise SafetyViolation("INVALID_ARCHIVE_RESPONSE")
        return cls(receipt, original, original.status, value["digest"], value["created_ms"], value["expires_ms"])


class FixtureClient:
    """Explicit typed calls, no redirect, no automatic retry after uncertainty."""

    def __init__(self, port: int, control_port: int, credential: SessionCredential, *, timeout: float = 2.0) -> None:
        if (type(port) is not int or type(control_port) is not int
                or not 0 < port < 65536 or not 0 < control_port < 65536):
            raise SafetyViolation("INVALID_LOOPBACK_PORT")
        self.port, self.control_port, self._credential, self.timeout = port, control_port, credential, timeout

    def _call(self, path: str, body: Mapping[str, Any], *, control: bool = False) -> dict[str, Any]:
        port = self.control_port if control else self.port
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=self.timeout)
        try:
            connection.request("POST", path, canonical_bytes(dict(body)), {
                "Authorization": "Bearer " + self._credential.bearer, "Content-Type": "application/json"})
            reply = connection.getresponse()
            if reply.status != 200 and reply.status < 400:
                raise SafetyViolation("UNSUPPORTED_HTTP_RESPONSE")
            raw = reply.read(DEFAULT_LIMITS.max_result_bytes + 1)
            if len(raw) > DEFAULT_LIMITS.max_result_bytes:
                raise SafetyViolation("RESULT_TOO_LARGE")
            data = parse_json_utf8(raw)
            if not isinstance(data, dict):
                raise SafetyViolation("INVALID_RESPONSE")
            return data
        except (OSError, http.client.HTTPException):
            command_id = body.get("command_id", "transport.request")
            return _response(Status.UNKNOWN, "CONNECTION_LOST_LOOKUP", command_id, next_action="lookup").as_dict()
        finally:
            connection.close()

    def discover(self) -> Discovery:
        result = self._call("/v1/discovery", {"project_id": self._credential.project_id, "protocol_version": PROTOCOL_VERSION})
        if "status" in result:
            raise SafetyViolation(result["code"])
        return Discovery.from_dict(result)

    def lease(self, *, ttl_ms: int = 60_000) -> FixtureLease:
        result = self._call("/v1/lease", {"project_id": self._credential.project_id, "ttl_ms": ttl_ms})
        if set(result) != {"lease_id", "fencing_epoch", "expires_ms", "revision"}:
            raise SafetyViolation(result.get("code", "INVALID_LEASE_RESPONSE"))
        return FixtureLease(**result)

    def request(self, command_id: str, *, value: int | None = None,
                lease: FixtureLease | None = None, delay_ms: int = 0, timeout_ms: int = 10_000) -> Request:
        operation = "fixture.inspect" if value is None else "fixture.set"
        payload = {} if value is None else {"value": value, "delay_ms": delay_ms}
        return Request(command_id, self._credential.project_id, operation,
            lease.lease_id if lease else "read", lease.fencing_epoch if lease else 0,
            lease.revision if lease else "any", dict(_TARGET), payload,
            payload_digest(operation, _TARGET, payload, SCHEMA_VERSION), epoch_ms() + timeout_ms)

    def submit(self, request: Request) -> Response:
        return Response.from_dict(self._call("/v1/commands", request.as_dict()))

    def lookup(self, command_id: str) -> Response:
        return Response.from_dict(self._call("/v1/lookup", {"project_id": self._credential.project_id,
                                                           "command_id": command_id}, control=True))

    def lookup_archive(self, command_id: str) -> ArchivedResult | Response:
        result = self._call("/v1/archive", {"project_id": self._credential.project_id,
                                           "command_id": command_id}, control=True)
        if "code" in result:
            return Response.from_dict(result)
        return ArchivedResult.from_dict(result)

    def cancel(self, command_id: str) -> Response:
        return Response.from_dict(self._call("/v1/cancel", {"project_id": self._credential.project_id,
                                                           "command_id": command_id}, control=True))

    def stop(self, command_id: str = "control.stop") -> Response:
        return Response.from_dict(self._call("/v1/stop", {"project_id": self._credential.project_id,
                                                         "command_id": command_id}, control=True))

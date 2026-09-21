"""Internal bytes-only IPC for the existing typed GT-02 counter fixture.

Two pre-created, process-bound endpoint roles share the existing host's
session authority, queue, journal, fencing, Stop and readback. This adds no
operation and does not route private staging or engine mutation. The native
launcher is responsible for its owned Job/lifecycle; this layer never launches
or kills processes, issues tokens over IPC, or accepts a caller-supplied path.
"""
from __future__ import annotations

from typing import Any

from ...protocol.core import Response, Status, ValidationError, canonical_bytes
from .journal import JournalError
from .limits import SafetyViolation, parse_json_utf8
from .pipe_endpoint import AppContainerEndpoint
from .pipe_io import MAX_FRAME_BYTES
from .transport import LoopbackFixtureHost, SessionCredential, _IDENTIFIER, _response

_ROUTES = frozenset({"/v1/discovery", "/v1/lease", "/v1/commands",
                     "/v1/lookup", "/v1/archive", "/v1/stop", "/v1/cancel"})


def fixture_frame(credential: SessionCredential, route: str, body: dict[str, Any]) -> bytes:
    """Trusted typed-client encoder; auth metadata stays outside request JSON."""
    if route not in _ROUTES:
        raise SafetyViolation("UNSUPPORTED_ROUTE")
    frame = ("Bearer " + credential.bearer + "\n" + route + "\n").encode("ascii") + canonical_bytes(body)
    if len(frame) > MAX_FRAME_BYTES:
        raise SafetyViolation("ENVELOPE_TOO_LARGE")
    return frame


class FixturePipeServer:
    """One endpoint bound to one locally issued session, serial bounded frames.

    A worker cannot change endpoint role, process identity or session by putting
    their values into a frame. Rotation/revocation requires rebinding through
    trusted launch configuration; connecting with another live token is denied.
    A reply lost after dispatch leaves the same durable command for lookup.
    """

    def __init__(self, endpoint: AppContainerEndpoint, host: LoopbackFixtureHost,
                 credential: SessionCredential) -> None:
        if type(endpoint) is not AppContainerEndpoint:
            raise SafetyViolation("BOUND_ENDPOINT_REQUIRED")
        session = host.sessions.authenticate("Bearer " + credential.bearer)
        if session.credential != credential:
            raise SafetyViolation("SESSION_BINDING_MISMATCH")
        self._endpoint, self._host = endpoint, host
        self._session_id = credential.session_id

    def serve_one(self) -> Any:
        host = self._host
        # Peer identity is checked both before and after the bounded frame read.
        # Transport errors propagate to the local supervisor, never to a forged
        # application REJECTED/no_effect response or an automatic resend.
        raw = self._endpoint.read_frame(timeout_ms=host.limits.request_timeout_ms)
        safe_command_id = "transport.request"
        try:
            parts = raw.split(b"\n", 2)
            if len(parts) != 3 or len(parts[0]) > 128 or len(parts[1]) > 64:
                raise SafetyViolation("INVALID_PIPE_HEADER")
            try:
                authorization, route = parts[0].decode("ascii"), parts[1].decode("ascii")
            except UnicodeError:
                raise SafetyViolation("INVALID_PIPE_HEADER") from None
            session = host.sessions.authenticate(authorization)
            if session.credential.session_id != self._session_id:
                raise SafetyViolation("SESSION_BINDING_MISMATCH")
            if len(parts[2]) > host.limits.max_body_bytes:
                raise SafetyViolation("ENVELOPE_TOO_LARGE")
            body = parse_json_utf8(parts[2])
            command = body.get("command_id") if isinstance(body, dict) else None
            if isinstance(command, str) and _IDENTIFIER.fullmatch(command):
                try:
                    host.sessions.validate_public_identifier(command)
                except SafetyViolation:
                    pass
                else:
                    safe_command_id = command
            result = host._dispatch(route, body, session, self._endpoint.role == "control")
        except JournalError as exc:
            result, _ = host._journal_failure(exc, safe_command_id)
        except (SafetyViolation, ValidationError) as exc:
            host._diagnostic(exc.code)
            result = _response(Status.REJECTED, exc.code, safe_command_id)
        except Exception:
            host._diagnostic("PIPE_DISPATCH_FAILED")
            host._stopped.set()
            result = _response(Status.UNKNOWN, "PIPE_DISPATCH_FAILED", safe_command_id)
        value = result.as_dict() if hasattr(result, "as_dict") else result
        encoded = host.sessions.encode_output(value)
        if len(encoded) > min(MAX_FRAME_BYTES, host.limits.max_response_bytes):
            result = _response(Status.UNKNOWN, "RESULT_TOO_LARGE", safe_command_id)
            encoded = host.sessions.encode_output(result.as_dict())
        self._endpoint.write_frame(encoded, timeout_ms=host.limits.request_timeout_ms)
        return result

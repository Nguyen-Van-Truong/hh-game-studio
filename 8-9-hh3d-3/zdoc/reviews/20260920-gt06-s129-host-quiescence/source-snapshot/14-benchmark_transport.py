"""Benchmark-local observation and disconnect hooks over the accepted transport.

Admission, journal authority, worker execution, Stop, socket responses, timeouts
and retry behavior remain inherited. This removes only disconnect-test control
contention from the benchmark ACK path; it is not a claim about S80's cause.
"""
from __future__ import annotations

import http.client
import threading
import time
from typing import Any, Mapping

from studio.host.core.limits import DEFAULT_LIMITS, SafetyViolation, parse_json_utf8
from studio.host.core.transport import FixtureClient, LoopbackFixtureHost, _response
from studio.protocol.core import Response, Status, canonical_bytes


_ENDPOINTS = {
    "/v1/discovery": "discovery", "/v1/lease": "lease", "/v1/commands": "commands",
    "/v1/lookup": "lookup", "/v1/archive": "archive", "/v1/cancel": "cancel", "/v1/stop": "stop",
}


class BenchmarkFixtureHost(LoopbackFixtureHost):
    """Same handler and state machine; independently synchronized test cuts."""

    def __init__(self, *args, **kwargs):
        self._disconnect_lock = threading.Lock()
        super().__init__(*args, **kwargs)

    def arm_disconnect(self, path: str, phase: str) -> None:
        with self._disconnect_lock:
            self.faults.disconnect_once = (path, phase)
            self.faults.disconnected_status = None
            self.faults.disconnect_observed.clear()

    def _disconnect_probe(self, path: str, phase: str, result: Any = None) -> bool:
        # Never hold this mutex across host/journal/session access or socket I/O.
        # Both arm and consume use it; no unlocked unarmed fast path is needed.
        with self._disconnect_lock:
            if self.faults.disconnect_once != (path, phase):
                return False
            self.faults.disconnect_once = None
            self.faults.disconnected_status = result.status.value if isinstance(result, Response) else None
            self.faults.disconnect_observed.set()
            return True


class BenchmarkFixtureClient(FixtureClient):
    """One local sanitized failure observation; no protocol field or retry."""

    _last_transport_failure: dict[str, str | float] | None = None

    @property
    def last_transport_failure(self) -> dict[str, str | float] | None:
        return None if self._last_transport_failure is None else dict(self._last_transport_failure)

    def _connection(self, port: int):
        """Local observation seam; the default constructor and timeout are unchanged."""
        return http.client.HTTPConnection("127.0.0.1", port, timeout=self.timeout)

    def _call(self, path: str, body: Mapping[str, Any], *, control: bool = False) -> dict[str, Any]:
        # Deliberate small copy of accepted FixtureClient._call so the accepted
        # source stays pinned. Differential tests protect all wire/error paths.
        self._last_transport_failure = None
        # Use the producer's QPC clock domain. On pinned Windows Python 3.11,
        # monotonic_ns uses coarse GetTickCount64 and can report an inner
        # elapsed interval larger than the enclosing perf_counter_ns attempt.
        started_ns = time.perf_counter_ns()
        stage = "request"
        port = self.control_port if control else self.port
        connection = self._connection(port)
        try:
            connection.request("POST", path, canonical_bytes(dict(body)), {
                "Authorization": "Bearer " + self._credential.bearer, "Content-Type": "application/json"})
            stage = "getresponse"
            reply = connection.getresponse()
            if reply.status != 200 and reply.status < 400:
                raise SafetyViolation("UNSUPPORTED_HTTP_RESPONSE")
            stage = "read"
            raw = reply.read(DEFAULT_LIMITS.max_result_bytes + 1)
            if len(raw) > DEFAULT_LIMITS.max_result_bytes:
                raise SafetyViolation("RESULT_TOO_LARGE")
            data = parse_json_utf8(raw)
            if not isinstance(data, dict):
                raise SafetyViolation("INVALID_RESPONSE")
            return data
        except (OSError, http.client.HTTPException) as error:
            category = ("timeout" if isinstance(error, TimeoutError) else
                        "connection" if isinstance(error, ConnectionError) else
                        "http" if isinstance(error, http.client.HTTPException) else "os")
            self._last_transport_failure = {
                "endpoint": _ENDPOINTS.get(path, "unknown"), "stage": stage,
                "category": category, "elapsed_ms": (time.perf_counter_ns() - started_ns) / 1_000_000,
            }
            command_id = body.get("command_id", "transport.request")
            return _response(Status.UNKNOWN, "CONNECTION_LOST_LOOKUP", command_id, next_action="lookup").as_dict()
        finally:
            connection.close()

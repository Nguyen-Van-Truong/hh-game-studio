"""Benchmark-local observation and disconnect hooks over the accepted transport.

Admission, journal authority, worker execution and Stop remain inherited.
O6 permits three retries only when connect fails before request bytes are sent.
All later failures remain UNKNOWN and require caller-side reconciliation.
"""
from __future__ import annotations

from collections import deque
import copy
import http.client
import threading
import time
from typing import Any, Mapping

from studio.host.core.limits import DEFAULT_LIMITS, SafetyViolation, parse_json_utf8
from studio.host.core.transport import FixtureClient, LoopbackFixtureHost, _response
from studio.protocol.core import Response, Status, canonical_bytes
from studio.tests.replay.benchmark_transport_metadata import (
    TransportMetadataError, validate_transport_event,
)


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
    """Bounded phase-aware transport observations for the benchmark client.

    A connection failure is retried only while ``HTTPConnection.connect`` has
    proved that no request bytes were sent. Once request construction starts,
    the result remains UNKNOWN and the caller must reconcile by lookup. The
    retry uses the same canonical bytes and command ID; it never resubmits a
    request after a send-side failure.
    """

    _CONNECT_RETRIES = 3
    _CONNECT_BACKOFF_SECONDS = (0.025, 0.05, 0.1)

    @property
    def last_transport_failure(self) -> dict[str, Any] | None:
        value = getattr(self, "_last_transport_failure", None)
        return None if value is None else copy.deepcopy(value)

    @property
    def transport_event_total(self) -> int:
        return getattr(self, "_transport_event_count", 0)

    def transport_events_since(self, cursor: int) -> list[dict[str, Any]]:
        if type(cursor) is not int or cursor < 0 or cursor > self.transport_event_total:
            raise SafetyViolation("TRANSPORT_EVENT_CURSOR")
        events = list(getattr(self, "_transport_events", ()))
        first = self.transport_event_total - len(events)
        if cursor < first:
            raise SafetyViolation("TRANSPORT_EVENT_WINDOW_LOST")
        return copy.deepcopy(events[cursor - first:])

    @staticmethod
    def _category(error: BaseException) -> str:
        return ("timeout" if isinstance(error, TimeoutError) else
                "connection" if isinstance(error, ConnectionError) else
                "http" if isinstance(error, http.client.HTTPException) else "os")

    @classmethod
    def _error_detail(cls, error: BaseException, *, endpoint: str, stage: str,
                      elapsed_ms: float) -> dict[str, Any]:
        errno_value = getattr(error, "errno", None)
        winerror_value = getattr(error, "winerror", None)
        return {
            "endpoint": endpoint,
            "stage": stage,
            "category": cls._category(error),
            "exception": next((cls.__name__ for cls in
                               (TimeoutError, ConnectionRefusedError, ConnectionResetError,
                                ConnectionAbortedError, BrokenPipeError,
                                http.client.RemoteDisconnected, ConnectionError,
                                http.client.HTTPException, OSError)
                               if isinstance(error, cls)), "OSError"),
            "errno": errno_value if type(errno_value) is int else None,
            "winerror": winerror_value if type(winerror_value) is int else None,
            "elapsed_ms": elapsed_ms,
        }

    def _record_transport_event(self, event: dict[str, Any]) -> None:
        try:
            validate_transport_event(event)
        except TransportMetadataError as error:
            raise SafetyViolation("INVALID_TRANSPORT_EVENT") from error
        if not hasattr(self, "_transport_events"):
            self._transport_events = deque(maxlen=128)
            self._transport_event_count = 0
        self._transport_events.append(copy.deepcopy(event))
        self._transport_event_count += 1

    def _connection(self, port: int):
        """Local observation seam; the default constructor and timeout are unchanged."""
        return http.client.HTTPConnection("127.0.0.1", port, timeout=self.timeout)

    def _call(self, path: str, body: Mapping[str, Any], *, control: bool = False) -> dict[str, Any]:
        # Deliberate small copy of accepted FixtureClient._call. Explicitly
        # separating connect from request is required to distinguish a safe
        # pre-send retry from an UNKNOWN after bytes may have been sent.
        self._last_transport_failure = None
        port = self.control_port if control else self.port
        endpoint = _ENDPOINTS.get(path, "unknown")
        payload = canonical_bytes(dict(body))
        headers = {"Authorization": "Bearer " + self._credential.bearer,
                   "Content-Type": "application/json"}
        call_started_ns = time.perf_counter_ns()
        deadline_ns = call_started_ns + int(self.timeout * 1_000_000_000)
        connect_failures: list[dict[str, Any]] = []
        for retry_index in range(self._CONNECT_RETRIES + 1):
            connection = self._connection(port)
            started_ns = time.perf_counter_ns()
            try:
                try:
                    connection.connect()
                except (OSError, http.client.HTTPException) as error:
                    detail = self._error_detail(error, endpoint=endpoint, stage="connect",
                                                elapsed_ms=(time.perf_counter_ns() - started_ns) / 1_000_000)
                    connect_failures.append(detail)
                    delay = (self._CONNECT_BACKOFF_SECONDS[retry_index]
                             if retry_index < self._CONNECT_RETRIES else None)
                    remaining = (deadline_ns - time.perf_counter_ns()) / 1_000_000_000
                    if delay is not None and remaining > delay:
                        connection.close()
                        time.sleep(delay)
                        continue
                    event = {**detail, "attempts": len(connect_failures),
                             "attempt_details": list(connect_failures),
                             "recovered": False, "bytes_sent": False}
                    self._last_transport_failure = event
                    self._record_transport_event(event)
                    command_id = body.get("command_id", "transport.request")
                    return _response(Status.UNKNOWN, "CONNECTION_LOST_LOOKUP", command_id,
                                     next_action="lookup").as_dict()

                # Disable HTTPConnection's implicit reconnect. If the connected
                # socket disappears before request(), this attempt must remain
                # uncertain instead of opening an unobserved second connection.
                connection.auto_open = 0
                stage = "request"
                connection.request("POST", path, payload, headers)
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
                if connect_failures:
                    self._record_transport_event({
                        **connect_failures[-1], "attempts": len(connect_failures) + 1,
                        "attempt_details": list(connect_failures),
                        "recovered": True, "bytes_sent": False})
                return data
            except (OSError, http.client.HTTPException) as error:
                detail = self._error_detail(error, endpoint=endpoint, stage=stage,
                                            elapsed_ms=(time.perf_counter_ns() - started_ns) / 1_000_000)
                event = {**detail, "attempts": len(connect_failures) + 1,
                         "attempt_details": list(connect_failures) + [detail],
                         "recovered": False, "bytes_sent": True}
                self._last_transport_failure = event
                self._record_transport_event(event)
                command_id = body.get("command_id", "transport.request")
                return _response(Status.UNKNOWN, "CONNECTION_LOST_LOOKUP", command_id,
                                 next_action="lookup").as_dict()
            finally:
                connection.close()

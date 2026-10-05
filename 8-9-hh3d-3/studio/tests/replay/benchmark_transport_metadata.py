"""Strict, secret-free metadata contract for benchmark HTTP transport failures.

The transport client records class identity and bounded numeric facts only.  A
failure event may contain connect retry details and, when request bytes might
have been sent, one terminal send-side detail.  This module is deliberately
independent of the client and of either evidence consumer so both paths apply
the same closed schema.
"""
from __future__ import annotations

import math
from typing import Any, Mapping


ENDPOINTS = frozenset({
    "discovery", "lease", "commands", "lookup", "archive", "cancel", "stop", "unknown",
})
STAGES = frozenset({"connect", "request", "getresponse", "read"})
CATEGORIES = frozenset({"timeout", "connection", "http", "os"})
# Keep this allowlist closed.  In particular, exception messages and arbitrary
# user-defined class names must never become evidence metadata.
EXCEPTIONS = frozenset({
    "TimeoutError", "ConnectionRefusedError", "ConnectionResetError",
    "ConnectionAbortedError", "BrokenPipeError", "RemoteDisconnected",
    "ConnectionError", "HTTPException", "OSError",
})
EVENT_FIELDS = frozenset({
    "endpoint", "stage", "category", "exception", "errno", "winerror",
    "elapsed_ms", "attempts", "attempt_details", "recovered", "bytes_sent",
})
DETAIL_FIELDS = frozenset({
    "endpoint", "stage", "category", "exception", "errno", "winerror", "elapsed_ms",
})
MAX_ELAPSED_MS = 600000
MAX_ATTEMPTS = 4
MAX_ERRNO = 2**31 - 1


class TransportMetadataError(ValueError):
    """A stable, non-secret validation code for callers to map to their errors."""

    def __init__(self, code: str, path: str = "$"):
        self.code = code
        self.path = path
        super().__init__(f"{code}: {path}")


def _fail(code: str, path: str) -> None:
    raise TransportMetadataError(code, path)


def _detail(value: Any, *, path: str, expected_endpoint: str | None = None,
            elapsed_max: float = MAX_ELAPSED_MS) -> None:
    if type(value) is not dict or set(value) != DETAIL_FIELDS:
        _fail("FIELDS", path)
    endpoint = value["endpoint"]
    if type(endpoint) is not str or endpoint not in ENDPOINTS:
        _fail("ENDPOINT", f"{path}.endpoint")
    if expected_endpoint is not None and endpoint != expected_endpoint:
        _fail("ENDPOINT", f"{path}.endpoint")
    if type(value["stage"]) is not str or value["stage"] not in STAGES:
        _fail("STAGE", f"{path}.stage")
    if type(value["category"]) is not str or value["category"] not in CATEGORIES:
        _fail("CATEGORY", f"{path}.category")
    if type(value["exception"]) is not str or value["exception"] not in EXCEPTIONS:
        _fail("EXCEPTION", f"{path}.exception")
    for key in ("errno", "winerror"):
        item = value[key]
        if item is not None and (type(item) is not int or not 0 <= item <= MAX_ERRNO):
            _fail("INTEGER", f"{path}.{key}")
    elapsed = value["elapsed_ms"]
    if (type(elapsed) not in (int, float) or not math.isfinite(elapsed)
            or not 0 <= elapsed <= elapsed_max):
        _fail("NUMBER", f"{path}.elapsed_ms")


def validate_transport_event(value: Mapping[str, Any], *,
                             expected_endpoint: str | None = None,
                             expected_recovered: bool | None = None,
                             expected_bytes_sent: bool | None = None,
                             elapsed_max: float = MAX_ELAPSED_MS) -> None:
    """Validate an event and all retry details, raising no secret-bearing text.

    A recovered event represents successful work after pre-send connect
    retries: all details are connect failures and ``attempts = details + 1``.
    An exhausted connect retry or a post-send failure has
    ``details = attempts``.  At most one non-connect terminal detail is allowed,
    and it must be the final detail.
    """
    if type(value) is not dict or set(value) != EVENT_FIELDS:
        _fail("FIELDS", "$")
    endpoint = value["endpoint"]
    if type(endpoint) is not str or endpoint not in ENDPOINTS:
        _fail("ENDPOINT", "$.endpoint")
    if expected_endpoint is not None and endpoint != expected_endpoint:
        _fail("ENDPOINT", "$.endpoint")
    if type(value["stage"]) is not str or value["stage"] not in STAGES:
        _fail("STAGE", "$.stage")
    if type(value["category"]) is not str or value["category"] not in CATEGORIES:
        _fail("CATEGORY", "$.category")
    if type(value["exception"]) is not str or value["exception"] not in EXCEPTIONS:
        _fail("EXCEPTION", "$.exception")
    for key in ("errno", "winerror"):
        item = value[key]
        if item is not None and (type(item) is not int or not 0 <= item <= MAX_ERRNO):
            _fail("INTEGER", f"$.{key}")
    elapsed = value["elapsed_ms"]
    if (type(elapsed) not in (int, float) or not math.isfinite(elapsed)
            or not 0 <= elapsed <= elapsed_max):
        _fail("NUMBER", "$.elapsed_ms")
    attempts = value["attempts"]
    if type(attempts) is not int or not 1 <= attempts <= MAX_ATTEMPTS:
        _fail("ATTEMPTS", "$.attempts")
    if type(value["recovered"]) is not bool or type(value["bytes_sent"]) is not bool:
        _fail("BOOLEAN", "$")
    if expected_recovered is not None and value['recovered'] is not expected_recovered:
        _fail('RECOVERED', '$.recovered')
    if expected_bytes_sent is not None and value['bytes_sent'] is not expected_bytes_sent:
        _fail('BYTES_SENT', '$.bytes_sent')
    details = value["attempt_details"]
    if type(details) is not list or not 1 <= len(details) <= MAX_ATTEMPTS:
        _fail("ATTEMPT_DETAILS", "$.attempt_details")
    for index, detail in enumerate(details):
        _detail(detail, path=f"$.attempt_details[{index}]", expected_endpoint=endpoint,
                elapsed_max=elapsed_max)

    terminal = [item for item in details if item["stage"] != "connect"]
    # Connect failures form one prefix.  Once request bytes may be involved,
    # only the single terminal send failure can follow; no later reconnect.
    if terminal:
        if len(terminal) != 1 or details[-1]["stage"] == "connect":
            _fail("RETRY_SEQUENCE", "$.attempt_details")
        if value["recovered"] or not value["bytes_sent"]:
            _fail("RETRY_CONSISTENCY", "$")
    elif value['bytes_sent']:
        _fail('RETRY_CONSISTENCY', '$.bytes_sent')

    if value["recovered"]:
        if value["bytes_sent"] or attempts != len(details) + 1:
            _fail("RETRY_CONSISTENCY", "$")
    elif attempts != len(details):
        _fail("RETRY_CONSISTENCY", "$")
    # Event-level stage must agree with the final observed failure, except for a
    # recovered event whose final detail is the last connect failure.
    if value["stage"] != details[-1]["stage"]:
        _fail("STAGE", "$.stage")
    for key in DETAIL_FIELDS - {'stage'}:
        if value[key] != details[-1][key]:
            _fail('DETAIL_MISMATCH', '$.' + key)


def validate_transport_detail(value: Mapping[str, Any], *,
                              expected_endpoint: str | None = None,
                              elapsed_max: float = MAX_ELAPSED_MS) -> None:
    """Validate one 7-field retry detail using the same closed enums."""
    _detail(value, path="$", expected_endpoint=expected_endpoint, elapsed_max=elapsed_max)

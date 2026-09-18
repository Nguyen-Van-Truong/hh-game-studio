"""Bounded queries over a verified, completed Play report, never a live runtime.

The service supplies its trusted host-capture anchor; callers cannot register
arbitrary paths through the query payload. Admission validates observation once
and retains only immutable, allowed property projections. Queries perform no
filesystem or engine access. This is an internal Python capability boundary,
not a sandbox against code that can modify this module's private globals.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import hmac
import json
from pathlib import Path
import re
import secrets
import threading
import weakref

from .observation import MAX_REPORT_BYTES, ObservationRejected, _strict, validate_observation
from .trace import ValidatedTrace

MAX_PAGE_ROWS = 8
MAX_RESULT_BYTES = 262144
MAX_CURSOR_CHARS = 2048
MAX_REGISTERED_VIEWS = 8
MAX_PROJECTION_BYTES = 524288
PROPERTIES = frozenset(("sim_tick", "ui_tick", "phase", "body_position", "body_velocity",
                       "animation", "camera", "outfit_visible", "emote_count", "prop_count", "tree_paused"))
EXPECTED_FIELDS = frozenset(("runtime_instance_id", "generation", "source_closure_sha256",
                           "runtime_snapshot_sha256", "report_sha256", "pid", "process_start"))
_CAPTURE_FIELDS = frozenset(("schema", "run_id", "completed_native", "formal_acceptance", "public_ack",
    "binding", "process", "report_sha256", "source_unchanged", "import_capture_sha256",
    "runtime_capture_sha256", "process_metrics_sha256"))
_PAYLOAD_FIELDS = frozenset(("expected", "properties", "phase", "tick_min", "tick_max", "page_size", "cursor"))
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_CURSOR = re.compile(r"[A-Za-z0-9_-]+\.[0-9a-f]{64}\Z")
_LOCK = threading.RLock()


class InspectorRejected(ValueError):
    """Stable code only; never echo private paths or candidate data."""
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _need(ok, code):
    if not ok:
        raise InspectorRejected(code)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _whole(value, low, high):
    return type(value) is int and low <= value <= high


def _object(value, keys, code):
    _need(type(value) is dict and set(value) == keys, code)
    return value


def _parse(raw, cap, code):
    try:
        return _strict(raw, cap)
    except ObservationRejected:
        raise InspectorRejected(code) from None


class RetainedView:
    """Opaque registered capability. Its rows and provenance are private."""
    __slots__ = ("_token", "__weakref__")

    def __new__(cls):
        raise InspectorRejected("INSPECT_VIEW_FACTORY")

    def __setattr__(self, name, value):
        raise AttributeError("RetainedView is immutable")

    def __repr__(self):
        return "<RetainedView historical completed>"


@dataclass(frozen=True, slots=True)
class _Registered:
    token: str
    cursor_key: bytes
    context_sha256: str
    expected_json: bytes
    provenance_json: bytes
    semantics_json: bytes
    rows_json: bytes


_REGISTERED = weakref.WeakKeyDictionary()


def _lookup(view):
    _need(type(view) is RetainedView, "INSPECT_VIEW")
    with _LOCK:
        registered = _REGISTERED.get(view)
    _need(registered is not None and getattr(view, "_token", None) == registered.token, "INSPECT_VIEW")
    return registered


def register_view(report_raw: bytes, *, native_capture_raw: bytes, native_capture_sha256: str,
                  trace: ValidatedTrace, binding: dict, process_raw: bytes,
                  project: Path, config_speed: float) -> RetainedView:
    """Admit a host-anchored completed report; call observation validation once.

    The trusted service owns the capture hash, actual process-exit/source audit,
    and fixed project directory. Exact process bytes are required because the
    native capture binds their raw digest, not a new JSON serialization.
    """
    with _LOCK:
        _need(len(_REGISTERED) < MAX_REGISTERED_VIEWS, "INSPECT_VIEW_CAP")
    _need(type(native_capture_raw) is bytes and 0 < len(native_capture_raw) <= 16384, "INSPECT_CAPTURE_BYTES")
    _need(type(report_raw) is bytes and 0 < len(report_raw) <= MAX_REPORT_BYTES, "INSPECT_REPORT_BYTES")
    _need(type(process_raw) is bytes and 0 < len(process_raw) <= 1048576, "INSPECT_PROCESS_BYTES")
    _need(type(native_capture_sha256) is str and _HASH.fullmatch(native_capture_sha256), "INSPECT_CAPTURE_ANCHOR")
    _need(type(native_capture_raw) is bytes and _sha(native_capture_raw) == native_capture_sha256, "INSPECT_CAPTURE_ANCHOR")
    capture = _object(_parse(native_capture_raw, 16384, "INSPECT_CAPTURE_JSON"), _CAPTURE_FIELDS, "INSPECT_CAPTURE_FIELDS")
    _need(capture["schema"] == "HH-GT06-NATIVE-CAPTURE-1" and capture["completed_native"] is True
          and capture["source_unchanged"] is True and capture["formal_acceptance"] is False
          and capture["public_ack"] is False, "INSPECT_CAPTURE_COMPLETION")
    for key in ("report_sha256", "import_capture_sha256", "runtime_capture_sha256", "process_metrics_sha256"):
        _need(type(capture[key]) is str and _HASH.fullmatch(capture[key]), "INSPECT_CAPTURE_HASH")
    _need(type(report_raw) is bytes and _sha(report_raw) == capture["report_sha256"], "INSPECT_REPORT_HASH")
    _need(type(process_raw) is bytes and _sha(process_raw) == capture["process_metrics_sha256"], "INSPECT_PROCESS_HASH")
    process = _parse(process_raw, 1048576, "INSPECT_PROCESS_JSON")
    _need(type(binding) is dict and type(capture["binding"]) is dict
          and capture["binding"] == binding and type(capture["binding"].get("generation")) is int
          and capture["run_id"] == binding.get("run_id")
          and type(capture["process"]) is dict and capture["process"] == process.get("identity")
          and type(capture["process"].get("pid")) is int, "INSPECT_CAPTURE_BINDING")
    binding = capture["binding"]  # Detach from the caller's mutable dictionary.
    # Validate immutable source/input/PNG identity, exact native JSON hashes,
    # real callback postconditions, clocks and host PID/window context once.
    checks = validate_observation(report_raw, trace=trace, binding=binding, config_speed=config_speed,
                                  project=project, process=process)
    report = json.loads(report_raw)  # Safe only after the bounded validator above.
    rows = [{"tick": row["trace_tick"], "properties": {key: row["state"][key] for key in sorted(PROPERTIES)}}
            for row in report["observations"]]
    rows_json = _encoded(rows)
    _need(len(rows_json) <= MAX_PROJECTION_BYTES, "INSPECT_PROJECTION_BYTES")
    expected = {key: binding[key] for key in ("runtime_instance_id", "generation", "source_closure_sha256", "runtime_snapshot_sha256")}
    expected.update(report_sha256=capture["report_sha256"], **process["identity"])
    _expected(expected, expected)
    expected_json = _encoded(expected)
    provenance = {"binding": binding, "native_capture_sha256": native_capture_sha256,
                  "report_sha256": capture["report_sha256"], "process": process["identity"]}
    provenance_json = _encoded(provenance)
    semantics = {key: checks[key] for key in ("complete", "all_postconditions", "movement_fault_observed")}
    registration = _Registered(secrets.token_hex(16), secrets.token_bytes(32), _sha(provenance_json),
                               expected_json, provenance_json, _encoded(semantics), rows_json)
    with _LOCK:
        _need(len(_REGISTERED) < MAX_REGISTERED_VIEWS, "INSPECT_VIEW_CAP")
        view = object.__new__(RetainedView)
        object.__setattr__(view, "_token", registration.token)
        _REGISTERED[view] = registration
    return view


def close_view(view: RetainedView) -> None:
    """Release a registered view; a repeated close is harmless."""
    _need(type(view) is RetainedView, "INSPECT_VIEW")
    with _LOCK:
        _REGISTERED.pop(view, None)


def _expected(value, admitted):
    _object(value, EXPECTED_FIELDS, "INSPECT_EXPECTED_FIELDS")
    _need(type(value["runtime_instance_id"]) is str and len(value["runtime_instance_id"]) <= 128
          and _whole(value["generation"], 1, 2147483647) and _whole(value["pid"], 1, 0xffffffff)
          and type(value["process_start"]) is str and re.fullmatch(r"windows:[1-9][0-9]{0,19}", value["process_start"])
          and all(type(value[k]) is str and _HASH.fullmatch(value[k]) for k in
                  ("source_closure_sha256", "runtime_snapshot_sha256", "report_sha256")), "INSPECT_EXPECTED_TYPE")
    _need(int(value["process_start"].split(":", 1)[1]) <= 18446744073709551615, "INSPECT_EXPECTED_TYPE")
    _need(value == admitted, "INSPECT_STALE_CONTEXT")


def _cursor_encode(registered, query_sha, offset):
    raw = _encoded({"context": registered.context_sha256, "query": query_sha, "offset": offset})
    token = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return token + "." + hmac.new(registered.cursor_key, raw, hashlib.sha256).hexdigest()


def _cursor_offset(cursor, registered, query_sha, page_size, total):
    if cursor is None:
        return 0
    _need(type(cursor) is str and 0 < len(cursor) <= MAX_CURSOR_CHARS and _CURSOR.fullmatch(cursor), "INSPECT_CURSOR")
    try:
        token, signature = cursor.split(".")
        raw = base64.b64decode(token + "="*((-len(token)) % 4), altchars=b"-_", validate=True)
        _need(base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=") == token
              and hmac.compare_digest(signature, hmac.new(registered.cursor_key, raw, hashlib.sha256).hexdigest()), "INSPECT_CURSOR")
        value = _object(_parse(raw, 2048, "INSPECT_CURSOR"), {"context", "query", "offset"}, "INSPECT_CURSOR")
        _need(value["context"] == registered.context_sha256 and value["query"] == query_sha
              and _whole(value["offset"], 1, total-1) and value["offset"] % page_size == 0, "INSPECT_CURSOR")
        return value["offset"]
    except (ValueError, UnicodeError):
        raise InspectorRejected("INSPECT_CURSOR") from None


def query_view(view: RetainedView, payload: dict) -> dict:
    """Return up to eight detached rows from this historical completed view."""
    registered = _lookup(view)
    _need(type(payload) is dict and {"expected", "properties"} <= set(payload) <= _PAYLOAD_FIELDS, "INSPECT_QUERY_FIELDS")
    _expected(payload["expected"], json.loads(registered.expected_json))
    properties = payload["properties"]
    _need(type(properties) is list and 1 <= len(properties) <= len(PROPERTIES)
          and all(type(key) is str and key in PROPERTIES for key in properties)
          and len(set(properties)) == len(properties), "INSPECT_PROPERTIES")
    properties = list(properties)
    phase = payload.get("phase")
    tick_min, tick_max, page_size = payload.get("tick_min", 0), payload.get("tick_max", 599), payload.get("page_size", MAX_PAGE_ROWS)
    _need(phase is None or type(phase) is str and phase in ("MENU", "PLAY", "PAUSED", "QUITTING"), "INSPECT_FILTER")
    _need(_whole(tick_min, 0, 599) and _whole(tick_max, tick_min, 599), "INSPECT_FILTER")
    _need(_whole(page_size, 1, MAX_PAGE_ROWS), "INSPECT_PAGE_SIZE")
    query = {"properties": properties, "phase": phase, "tick_min": tick_min, "tick_max": tick_max, "page_size": page_size}
    query_sha = _sha(_encoded(query))
    rows = [row for row in json.loads(registered.rows_json) if tick_min <= row["tick"] <= tick_max
            and (phase is None or row["properties"]["phase"] == phase)]
    offset = _cursor_offset(payload.get("cursor"), registered, query_sha, page_size, len(rows))
    page = [{"tick": row["tick"], "properties": {key: row["properties"][key] for key in properties}}
            for row in rows[offset:offset + page_size]]
    next_offset = offset + len(page)
    result = {"schema_id": "hh-studio.retained-play-inspection", "schema_version": "1.0.0",
        "historical": True, "completed": True, "live": False, "formal_acceptance": False,
        "provenance": json.loads(registered.provenance_json), "semantics": json.loads(registered.semantics_json),
        "rows": page, "returned_count": len(page), "total_matches": len(rows),
        "next_cursor": _cursor_encode(registered, query_sha, next_offset) if next_offset < len(rows) else None}
    _need(len(_encoded(result)) <= MAX_RESULT_BYTES, "INSPECT_RESULT_BYTES")
    return result

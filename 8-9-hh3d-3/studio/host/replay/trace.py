"""Bounded GT06 input-trace artifact admission; no engine or filesystem I/O.

This has its own artifact limits. It does not relax the GT02 command-envelope
array cap. A trace is input intent, not evidence that a runtime consumed it.
Ticks are authored 60 Hz input frames, including paused frames; they are not a
simulation clock. ``held`` is the state AFTER that frame's edges are applied.
Captures request a tick; actual fresh-frame capture timing belongs in runtime
receipts. Multiple capture labels may share a tick, in request-array order.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from types import MappingProxyType
from typing import Any, Mapping

SCHEMA_ID = "hh-studio.input-trace"
SCHEMA_VERSION = "1.0.0"
FPS = 60
MAX_BYTES = 256 * 1024
MAX_FRAMES = 600
MAX_CAPTURES = 16
MAX_DEPTH = 4
MAX_LABEL_CHARS = 48
MAX_SEED = (1 << 32) - 1
KEYS = ("ENTER", "TAB", "RIGHT", "LEFT", "UP", "DOWN", "E", "O", "M", "ESCAPE", "C", "Q")
_KEYS = frozenset(KEYS)
_ROOT_FIELDS = {"schema_id", "schema_version", "fps", "seed", "frames", "captures"}
_FRAME_FIELDS = {"tick", "pressed", "held", "released"}
_CAPTURE_FIELDS = {"tick", "label"}
_LABEL = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*\Z")
_DEVICE = re.compile(r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])\Z")


class TraceRejected(ValueError):
    """Stable error code without echoing candidate bytes, keys or labels."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _need(value: bool, code: str) -> None:
    if not value:
        raise TraceRejected(code)


def _integer(value: Any, low: int, high: int) -> bool:
    return type(value) is int and low <= value <= high


def _decode(raw: bytes) -> dict:
    _need(type(raw) is bytes, "TRACE_BYTES_REQUIRED")
    _need(0 < len(raw) <= MAX_BYTES, "TRACE_BYTE_LIMIT")
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError:
        raise TraceRejected("TRACE_UTF8") from None

    # Reject excessive nesting before the recursive JSON parser allocates its
    # containers. Byte cap bounds the scan and all remaining parser allocations.
    depth = 0
    quoted = escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            _need(depth <= MAX_DEPTH, "TRACE_DEPTH_LIMIT")
        elif char in "]}":
            depth -= 1
            _need(depth >= 0, "TRACE_JSON")

    def pairs(rows):
        _need(len(rows) <= len(_ROOT_FIELDS), "TRACE_OBJECT_LIMIT")
        result = {}
        for key, value in rows:
            _need(key not in result, "TRACE_DUPLICATE_KEY")
            result[key] = value
        return result

    def integer(token):
        _need(len(token) <= 11, "TRACE_NUMBER_LIMIT")
        return int(token)

    def noninteger(_token):
        raise TraceRejected("TRACE_INTEGER_REQUIRED")

    def nonfinite(_token):
        raise TraceRejected("TRACE_NONFINITE")

    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_int=integer,
                           parse_float=noninteger, parse_constant=nonfinite)
    except (json.JSONDecodeError, RecursionError):
        raise TraceRejected("TRACE_JSON") from None
    _need(type(value) is dict, "TRACE_ROOT_OBJECT")
    return value


def _fields(value: Any, fields: set[str]) -> None:
    _need(type(value) is dict and set(value) == fields, "TRACE_FIELDS")


def _keyset(value: Any) -> set[str]:
    _need(type(value) is list and len(value) <= len(KEYS), "TRACE_KEY_LIMIT_OR_TYPE")
    _need(all(type(key) is str and key in _KEYS for key in value), "TRACE_KEY_UNSUPPORTED")
    result = set(value)
    _need(len(result) == len(value), "TRACE_KEY_DUPLICATE")
    return result


def _check(value: dict) -> None:
    _fields(value, _ROOT_FIELDS)
    _need(value["schema_id"] == SCHEMA_ID and value["schema_version"] == SCHEMA_VERSION,
          "TRACE_SCHEMA")
    _need(type(value["fps"]) is int and value["fps"] == FPS, "TRACE_FPS")
    _need(_integer(value["seed"], 0, MAX_SEED), "TRACE_SEED")
    frames, captures = value["frames"], value["captures"]
    _need(type(frames) is list and 1 <= len(frames) <= MAX_FRAMES, "TRACE_FRAME_LIMIT_OR_TYPE")
    _need(type(captures) is list and len(captures) <= MAX_CAPTURES, "TRACE_CAPTURE_LIMIT_OR_TYPE")
    previous: set[str] = set()
    for tick, frame in enumerate(frames):
        _fields(frame, _FRAME_FIELDS)
        _need(type(frame["tick"]) is int and frame["tick"] == tick, "TRACE_TICK_CONTIGUOUS")
        pressed, held, released = (_keyset(frame[name]) for name in ("pressed", "held", "released"))
        _need(not pressed & released, "TRACE_EDGE_OVERLAP")
        _need(not pressed & previous, "TRACE_REPEATED_PRESS")
        _need(released <= previous, "TRACE_NONHELD_RELEASE")
        _need(held == (previous | pressed) - released, "TRACE_HELD_STATE")
        previous = held
    _need(not previous, "TRACE_FINAL_HELD")

    labels: set[str] = set()
    for capture in captures:
        _fields(capture, _CAPTURE_FIELDS)
        _need(_integer(capture["tick"], 0, len(frames) - 1), "TRACE_CAPTURE_TICK")
        label = capture["label"]
        _need(type(label) is str and 1 <= len(label) <= MAX_LABEL_CHARS
              and _LABEL.fullmatch(label) is not None and _DEVICE.fullmatch(label) is None,
              "TRACE_CAPTURE_LABEL")
        _need(label not in labels, "TRACE_CAPTURE_DUPLICATE")
        labels.add(label)


def _freeze(value: Any) -> Any:
    if type(value) is dict:
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if type(value) is list:
        return tuple(_freeze(item) for item in value)
    return value


def _copy(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _copy(item) for key, item in value.items()}
    if type(value) is tuple:
        return [_copy(item) for item in value]
    return value


@dataclass(frozen=True, slots=True, init=False)
class ValidatedTrace:
    """Validation cannot be skipped by constructing this type directly.

    ``raw_sha256`` hashes the exact admitted UTF-8 bytes, including whitespace;
    it is not a semantic/canonical digest. ``value`` is recursively immutable.
    Use ``as_dict()`` for a defensive mutable copy or ``raw`` to write an artifact.
    """

    raw: bytes
    raw_sha256: str
    value: Mapping[str, Any]

    def __init__(self, raw: bytes):
        value = _decode(raw)
        _check(value)
        object.__setattr__(self, "raw", raw)
        object.__setattr__(self, "raw_sha256", hashlib.sha256(raw).hexdigest())
        object.__setattr__(self, "value", _freeze(value))

    def as_dict(self) -> dict:
        return _copy(self.value)


def validate_trace(raw: bytes) -> ValidatedTrace:
    """Validate one bounded bytes artifact without applying any input."""
    return ValidatedTrace(raw)


def default_trace(seed: int = 0) -> ValidatedTrace:
    """Deterministic six-second fixture intent; runtime evidence is separate.

    Seed is carried unchanged to the runtime. Input timing does not vary by seed,
    allowing an identically scheduled seeded-fault/fix comparison. Q enters the
    fixture's quitting phase; the runtime must consume its release and flush
    pending captures before exiting the owned process.
    """
    _need(_integer(seed, 0, MAX_SEED), "TRACE_SEED")
    intervals = (("ENTER", 10, 11), ("RIGHT", 30, 60), ("E", 80, 81),
                 ("O", 100, 101), ("M", 120, 121), ("ESCAPE", 150, 151),
                 ("RIGHT", 160, 180), ("ESCAPE", 200, 201), ("C", 230, 231),
                 ("Q", 350, 351))
    frames = []
    for tick in range(360):
        frames.append({"tick": tick,
            "pressed": [key for key, start, end in intervals if tick == start],
            "held": [key for key, start, end in intervals if start <= tick < end],
            "released": [key for key, start, end in intervals if tick == end]})
    captures = [{"tick": tick, "label": label} for tick, label in (
        (0, "menu"), (61, "moved"), (125, "interact"), (165, "paused_a"),
        (175, "paused_b"), (210, "resumed"), (240, "camera"))]
    value = {"schema_id": SCHEMA_ID, "schema_version": SCHEMA_VERSION,
             "fps": FPS, "seed": seed, "frames": frames, "captures": captures}
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
    return validate_trace(raw)

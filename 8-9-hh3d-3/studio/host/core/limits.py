"""Fail-closed safety limits shared by the GT-02 host adapters.

This module deliberately contains policy and validation only.  It does not
launch a process, evaluate agent supplied code, or perform a mutation.  A
consumer must validate an envelope before acquiring a lease or applying an
operation.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping

try:  # package import from repository root
    from studio.protocol.core import (
        SCHEMA_VERSION as CANONICAL_SCHEMA_VERSION,
        canonical_json as canonical_protocol_json,
    )
except ImportError:  # direct studio-root test/CLI invocation
    from protocol.core import (  # type: ignore[no-redef]
        SCHEMA_VERSION as CANONICAL_SCHEMA_VERSION,
        canonical_json as canonical_protocol_json,
    )


SAFE_INTEGER_MAX = (1 << 53) - 1
_WINDOWS_DEVICE = re.compile(r"^(?:\\\\[?.]\\|[A-Za-z]:\\\\|CON(?:$|[.:])|PRN(?:$|[.:])|AUX(?:$|[.:])|NUL(?:$|[.:])|COM[1-9](?:$|[.:])|LPT[1-9](?:$|[.:]))", re.I)


class SafetyViolation(ValueError):
    """Stable, machine-readable rejection for an unsafe request."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclass(frozen=True)
class LimitsProfile:
    """Resource and wire caps.  Values are intentionally conservative."""

    profile_id: str = "gt02-safe-v1"
    max_envelope_bytes: int = 256 * 1024
    max_payload_bytes: int = 128 * 1024
    max_result_bytes: int = 256 * 1024
    max_command_id_chars: int = 128
    max_project_id_chars: int = 128
    max_operation_chars: int = 128
    max_target_chars: int = 2_048
    max_lease_ttl_ms: int = 15 * 60 * 1_000
    max_deadline_horizon_ms: int = 30 * 60 * 1_000
    max_retry_horizon_ms: int = 24 * 60 * 60 * 1_000
    max_journal_bytes: int = 64 * 1024 * 1024
    max_pending_commands: int = 1_024
    max_depth: int = 32
    max_object_members: int = 256
    max_array_items: int = 256
    max_string_chars: int = 16_384

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            if name == "profile_id":
                continue
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"invalid positive limit: {name}")


DEFAULT_LIMITS = LimitsProfile()


def _reject_non_finite(value: Any, path: str = "$", depth: int = 0, *, limits: LimitsProfile = DEFAULT_LIMITS) -> None:
    if depth > limits.max_depth:
        raise SafetyViolation("DEPTH_LIMIT", path)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SafetyViolation("INVALID_NUMBER", path)
        return
    if isinstance(value, int) and not isinstance(value, bool):
        if abs(value) > SAFE_INTEGER_MAX:
            raise SafetyViolation("INTEGER_REQUIRES_DECIMAL_STRING", path)
    if isinstance(value, str):
        if len(value) > limits.max_string_chars:
            raise SafetyViolation("STRING_LIMIT", path)
        # Python can hold lone UTF-16 surrogates after decoding JSON.  They
        # cannot be represented in the canonical UTF-8 wire format.
        try:
            value.encode("utf-8", "strict")
        except UnicodeEncodeError as exc:
            raise SafetyViolation("INVALID_UNICODE", path) from exc
    if isinstance(value, Mapping):
        if len(value) > limits.max_object_members:
            raise SafetyViolation("OBJECT_MEMBER_LIMIT", path)
        for key, child in value.items():
            if not isinstance(key, str):
                raise SafetyViolation("INVALID_OBJECT_KEY", path)
            _reject_non_finite(child, f"{path}.{key}", depth + 1, limits=limits)
    elif isinstance(value, list):
        if len(value) > limits.max_array_items:
            raise SafetyViolation("ARRAY_ITEM_LIMIT", path)
        for index, child in enumerate(value):
            _reject_non_finite(child, f"{path}[{index}]", depth + 1, limits=limits)


def parse_json_utf8(raw: bytes | str, *, limits: LimitsProfile = DEFAULT_LIMITS) -> Any:
    """Parse canonical-wire JSON, rejecting ambiguity before application."""
    if isinstance(raw, bytes):
        if len(raw) > limits.max_envelope_bytes:
            raise SafetyViolation("ENVELOPE_TOO_LARGE")
        try:
            text = raw.decode("utf-8", "strict")
        except UnicodeDecodeError as exc:
            raise SafetyViolation("INVALID_UTF8") from exc
    elif isinstance(raw, str):
        try:
            encoded = raw.encode("utf-8", "strict")
        except UnicodeEncodeError as exc:
            raise SafetyViolation("INVALID_UTF8") from exc
        if len(encoded) > limits.max_envelope_bytes:
            raise SafetyViolation("ENVELOPE_TOO_LARGE")
        text = raw
    else:
        raise SafetyViolation("INVALID_JSON_INPUT")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise SafetyViolation("DUPLICATE_KEY", key)
            result[key] = value
        return result

    def constant(value: str) -> Any:
        raise SafetyViolation("NON_FINITE_NUMBER", value)

    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except SafetyViolation:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SafetyViolation("INVALID_JSON") from exc
    _reject_non_finite(value, limits=limits)
    return value


def canonical_json(value: Any, *, limits: LimitsProfile = DEFAULT_LIMITS) -> bytes:
    """Return the shared RFC 8785 canonical UTF-8 profile."""
    _reject_non_finite(value, limits=limits)
    try:
        encoded = canonical_protocol_json(value).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise SafetyViolation("NON_CANONICAL_JSON") from exc
    if len(encoded) > limits.max_payload_bytes:
        raise SafetyViolation("PAYLOAD_TOO_LARGE")
    return encoded


def payload_digest(operation: str, target: Mapping[str, str], payload: Any,
                   schema_version: str, *, limits: LimitsProfile = DEFAULT_LIMITS) -> str:
    """Hash the payload exactly as the typed protocol does.

    Operation/target/schema are authenticated by ``request_digest``; keeping
    this helper payload-only makes the field name ``payload_hash`` unambiguous.
    """
    if not isinstance(operation, str) or not operation or len(operation) > limits.max_operation_chars:
        raise SafetyViolation("INVALID_FIELD", "operation")
    if not isinstance(target, Mapping) or set(target) not in ({"stable_id"}, {"path"}):
        raise SafetyViolation("INVALID_FIELD", "target")
    for value in target.values():
        if not isinstance(value, str) or not value or len(value) > limits.max_target_chars:
            raise SafetyViolation("INVALID_FIELD", "target")
    if schema_version != CANONICAL_SCHEMA_VERSION:
        raise SafetyViolation("UNSUPPORTED_SCHEMA", str(schema_version))
    return "sha256:" + hashlib.sha256(canonical_json(payload, limits=limits)).hexdigest()


def request_digest(operation: str, target: Mapping[str, str], payload: Any,
                   schema_version: str, *, limits: LimitsProfile = DEFAULT_LIMITS) -> str:
    body = canonical_json({"operation": operation, "target": dict(target),
                           "payload": payload, "schema_version": schema_version}, limits=limits)
    return "sha256:" + hashlib.sha256(body).hexdigest()


def validate_envelope(envelope: Mapping[str, Any], *, now_ms: int,
                      limits: LimitsProfile = DEFAULT_LIMITS) -> dict[str, Any]:
    """Validate an agent request before lease/apply.  No side effects occur."""
    if not isinstance(envelope, Mapping):
        raise SafetyViolation("INVALID_ENVELOPE")
    required = ("schema_version", "command_id", "project_id", "operation",
                "lease_id", "fencing_epoch", "expected_revision", "target",
                "payload", "payload_hash", "deadline_ms")
    if set(envelope) != set(required):
        unknown = set(envelope) - set(required)
        if unknown:
            raise SafetyViolation("UNKNOWN_FIELD", sorted(unknown)[0])
    missing = [key for key in required if key not in envelope]
    if missing:
        raise SafetyViolation("MISSING_FIELD", ",".join(missing))
    _reject_non_finite(dict(envelope))
    text_caps = (("schema_version", 64), ("command_id", limits.max_command_id_chars),
                 ("project_id", limits.max_project_id_chars),
                 ("operation", limits.max_operation_chars), ("lease_id", 128),
                 ("expected_revision", 256))
    for key, cap in text_caps:
        value = envelope[key]
        if not isinstance(value, str) or not value or len(value) > cap:
            raise SafetyViolation("INVALID_FIELD", key)
    if not isinstance(envelope["fencing_epoch"], int) or isinstance(envelope["fencing_epoch"], bool) or envelope["fencing_epoch"] < 0:
        raise SafetyViolation("INVALID_FIELD", "fencing_epoch")
    if not isinstance(envelope["target"], Mapping) or set(envelope["target"]) not in ({"stable_id"}, {"path"}):
        raise SafetyViolation("INVALID_FIELD", "target")
    for key, value in envelope["target"].items():
        if not isinstance(value, str) or not value or len(value) > limits.max_target_chars:
            raise SafetyViolation("INVALID_FIELD", "target")
    if not isinstance(envelope["deadline_ms"], int) or isinstance(envelope["deadline_ms"], bool):
        raise SafetyViolation("INVALID_DEADLINE")
    if envelope["deadline_ms"] < now_ms or envelope["deadline_ms"] > now_ms + limits.max_deadline_horizon_ms:
        raise SafetyViolation("DEADLINE_OUT_OF_RANGE")
    digest = payload_digest(envelope["operation"], envelope["target"], envelope["payload"], envelope["schema_version"], limits=limits)
    if not isinstance(envelope["payload_hash"], str) or envelope["payload_hash"].lower() != digest:
        raise SafetyViolation("PAYLOAD_HASH_MISMATCH")
    return dict(envelope)


class SafePathResolver:
    """Lexical root guard; write opens require an OS no-reparse primitive."""

    def __init__(self, root: str | os.PathLike[str], *, safe_open_supported: bool = False) -> None:
        self.root = Path(root).resolve(strict=True)
        self.safe_open_supported = safe_open_supported

    def resolve(self, relative: str, *, for_write: bool = False, require_existing: bool = False) -> Path:
        if not isinstance(relative, str) or not relative or "\x00" in relative:
            raise SafetyViolation("INVALID_PATH")
        if len(relative) > DEFAULT_LIMITS.max_target_chars:
            raise SafetyViolation("PATH_TOO_LONG")
        # pathlib uses host semantics (on Linux it does not split '\\').
        # Inspect the wire spelling first so a Windows path cannot bypass a
        # Linux test runner, and vice versa.
        wire_parts = re.split(r"[\\/]", relative)
        if any(part in ("", ".", "..") for part in wire_parts):
            raise SafetyViolation("PATH_TRAVERSAL")
        if (relative.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", relative)
                or _WINDOWS_DEVICE.match(relative)):
            raise SafetyViolation("DEVICE_OR_ADS_PATH")
        if ":" in wire_parts[-1]:
            raise SafetyViolation("DEVICE_OR_ADS_PATH")
        # Build from validated wire components so separator semantics are
        # identical when tests run on a different host OS.
        candidate = Path(*wire_parts)
        if candidate.is_absolute() or any(part in ("", ".", "..") for part in candidate.parts):
            raise SafetyViolation("PATH_TRAVERSAL")
        if for_write and not self.safe_open_supported:
            raise SafetyViolation("UNSUPPORTED_SAFE_OPEN_WINDOWS" if os.name == "nt" else "UNSUPPORTED_SAFE_OPEN_LINUX")
        resolved = (self.root / candidate).resolve(strict=False)
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise SafetyViolation("PATH_ESCAPE") from exc
        current = self.root
        for part in wire_parts:
            current = current / part
            if current.exists() and (current.is_symlink() or getattr(current.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400):
                raise SafetyViolation("REPARSE_OR_SYMLINK")
        if require_existing and not resolved.exists():
            raise SafetyViolation("PATH_NOT_FOUND")
        if resolved.exists() and stat.S_ISREG(resolved.stat().st_mode) and resolved.stat().st_nlink != 1:
            raise SafetyViolation("HARDLINK_UNSAFE")
        return resolved

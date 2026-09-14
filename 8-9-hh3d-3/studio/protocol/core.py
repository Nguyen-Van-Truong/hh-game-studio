"""Canonical JSON envelopes and fail-closed validation (GT-02).

The wire profile is intentionally conservative: UTF-8 JSON objects, finite
numbers, duplicate-key rejection, bounded nesting and explicit schema/version
checks.  It is a deterministic profile suitable for Python/Node/Godot golden
vectors; it does not claim to be a complete transport implementation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import math
import os
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from ._rfc8785 import CanonicalizationError as _JCSCanonicalizationError
from ._rfc8785 import IntegerDomainError as _JCSIntegerDomainError
from ._rfc8785 import dumps as _jcs_dumps

PROTOCOL_VERSION = "1.0"
SCHEMA_VERSION = "hh-studio-0.1"
MAX_DEPTH = 32
MAX_BYTES = 1_048_576
MAX_PAYLOAD_BYTES = 512_000
MAX_OBJECT_MEMBERS = 256
MAX_ARRAY_ITEMS = 256
MAX_STRING_CHARS = 16_384
SAFE_INTEGER = 9_007_199_254_740_991
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_OP = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def _reject_unknown(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    """Reject typo/ambiguous fields; extension negotiation is explicit later."""
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError("UNKNOWN_FIELD", f"{field}.{sorted(unknown)[0]}")
_FORBIDDEN_KEYS = re.compile(r"(?:secret|password|passwd|token|api[_-]?key|private[_-]?key|credential)", re.I)
_FORBIDDEN_PATH = re.compile(r"^(?:\\\\\?\\|\\\\\.\\|//\.?/|[A-Za-z]:[\\/]{2})")


def redact_for_evidence(value: Any) -> Any:
    """Return a JSON-safe copy with sensitive fields removed from evidence.

    Redaction is deliberately separate from validation: a request containing a
    secret-shaped field is still rejected, while diagnostics can safely retain
    its structure without retaining the secret value.
    """
    if isinstance(value, Mapping):
        return {key: "[REDACTED]" if _FORBIDDEN_KEYS.search(str(key))
                else redact_for_evidence(child) for key, child in value.items()}
    if isinstance(value, list):
        return [redact_for_evidence(child) for child in value]
    if isinstance(value, tuple):
        return [redact_for_evidence(child) for child in value]
    return value


class ValidationError(ValueError):
    """Stable fail-closed protocol error."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def _reject_constant(value: str) -> None:
    raise ValidationError("INVALID_NUMBER", f"non-finite number {value}")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError("DUPLICATE_KEY", key)
        result[key] = value
    return result


def _walk(value: Any, depth: int = 0, *, key: str = "") -> None:
    if depth > MAX_DEPTH:
        raise ValidationError("DEPTH_LIMIT", str(MAX_DEPTH))
    if key and _FORBIDDEN_KEYS.search(key):
        raise ValidationError("SECRET_FIELD_FORBIDDEN", key)
    if isinstance(value, str):
        if len(value) > MAX_STRING_CHARS:
            raise ValidationError("STRING_LIMIT", key or "string")
        if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ValidationError("INVALID_UNICODE", key or "string")
    elif isinstance(value, bool) or value is None:
        return
    elif isinstance(value, int):
        if abs(value) > SAFE_INTEGER:
            raise ValidationError("INTEGER_REQUIRES_DECIMAL_STRING", key or "integer")
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise ValidationError("INVALID_NUMBER", key or "number")
    elif isinstance(value, Mapping):
        if len(value) > MAX_OBJECT_MEMBERS:
            raise ValidationError("OBJECT_MEMBER_LIMIT", key or "object")
        for item_key, item_value in value.items():
            if not isinstance(item_key, str):
                raise ValidationError("INVALID_KEY", "object keys must be strings")
            _walk(item_value, depth + 1, key=item_key)
    elif isinstance(value, Sequence):
        if len(value) > MAX_ARRAY_ITEMS:
            raise ValidationError("ARRAY_ITEM_LIMIT", key or "array")
        for item in value:
            _walk(item, depth + 1, key=key)
    else:
        raise ValidationError("INVALID_TYPE", type(value).__name__)


def canonical_json(value: Any) -> str:
    """Return RFC 8785 JCS text after strict profile validation.

    JCS fixes ECMAScript-compatible number rendering and UTF-16 property
    ordering, avoiding the cross-language drift of ``json.dumps(sort_keys)``.
    """
    _walk(value)
    try:
        encoded = _jcs_dumps(value)
        text = encoded.decode("utf-8", "strict")
    except _JCSIntegerDomainError as exc:
        raise ValidationError("INTEGER_REQUIRES_DECIMAL_STRING", str(exc)) from exc
    except (_JCSCanonicalizationError, TypeError, ValueError, UnicodeError) as exc:
        raise ValidationError("INVALID_JSON", str(exc)) from exc
    if len(encoded) > MAX_BYTES:
        raise ValidationError("MESSAGE_TOO_LARGE", str(MAX_BYTES))
    return text


def canonical_bytes(value: Any) -> bytes:
    return canonical_json(value).encode("utf-8")


def parse_json(data: str | bytes) -> Any:
    if isinstance(data, str):
        raw = data.encode("utf-8", "strict")
    else:
        raw = bytes(data)
    if len(raw) > MAX_BYTES:
        raise ValidationError("MESSAGE_TOO_LARGE", str(MAX_BYTES))
    try:
        value = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=_pairs,
                           parse_constant=_reject_constant)
    except ValidationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("INVALID_JSON", str(exc)) from exc
    _walk(value)
    return value


def _text(value: Any, field_name: str, *, pattern: re.Pattern[str] = _NAME) -> str:
    if not isinstance(value, str) or not value or not pattern.fullmatch(value):
        raise ValidationError("INVALID_FIELD", field_name)
    return value


def _payload_hash(payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(canonical_bytes(payload)).hexdigest()
    return f"sha256:{digest}"


@dataclass(frozen=True)
class Capability:
    operation: str
    read_scopes: tuple[str, ...] = ()
    write_scopes: tuple[str, ...] = ()
    limits: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _text(self.operation, "capability.operation", pattern=_OP)
        for scope in (*self.read_scopes, *self.write_scopes):
            _text(scope, "capability.scope")
        for key, limit in self.limits.items():
            _text(key, "capability.limit")
            if not isinstance(limit, int) or limit < 0 or limit > SAFE_INTEGER:
                raise ValidationError("INVALID_LIMIT", key)

    def as_dict(self) -> dict[str, Any]:
        return {"operation": self.operation, "read_scopes": list(self.read_scopes),
                "write_scopes": list(self.write_scopes), "limits": dict(self.limits)}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Capability":
        if not isinstance(value, Mapping):
            raise ValidationError("INVALID_CAPABILITY", "object required")
        _reject_unknown(value, {"operation", "read_scopes", "write_scopes", "limits"}, "capability")
        return cls(value.get("operation", ""), tuple(value.get("read_scopes", ())),
                   tuple(value.get("write_scopes", ())), value.get("limits", {}))


@dataclass(frozen=True)
class Discovery:
    protocol_version: str
    schema_version: str
    schema_digest: str
    server: str
    build: str
    project_id: str
    capabilities: tuple[Capability, ...] = ()
    limits: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.protocol_version != PROTOCOL_VERSION:
            raise ValidationError("UNSUPPORTED_VERSION", self.protocol_version)
        if self.schema_version != SCHEMA_VERSION:
            raise ValidationError("UNSUPPORTED_SCHEMA", self.schema_version)
        if not isinstance(self.schema_digest, str) or not _DIGEST.fullmatch(self.schema_digest):
            raise ValidationError("INVALID_DIGEST", "discovery.schema_digest")
        for name in ("server", "build", "project_id"):
            _text(getattr(self, name), f"discovery.{name}")
        _validate_limits(self.limits)

    def as_dict(self) -> dict[str, Any]:
        return {"protocol_version": self.protocol_version, "schema_version": self.schema_version,
                "schema_digest": self.schema_digest, "server": self.server, "build": self.build,
                "project_id": self.project_id, "capabilities": [c.as_dict() for c in self.capabilities],
                "limits": dict(self.limits)}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Discovery":
        if not isinstance(value, Mapping):
            raise ValidationError("INVALID_DISCOVERY", "object required")
        _reject_unknown(value, {"protocol_version", "schema_version", "schema_digest", "server",
                                 "build", "project_id", "capabilities", "limits"}, "discovery")
        capabilities = value.get("capabilities", ())
        if not isinstance(capabilities, Sequence) or isinstance(capabilities, (str, bytes)):
            raise ValidationError("INVALID_CAPABILITY", "list required")
        return cls(value.get("protocol_version", ""), value.get("schema_version", ""),
                   value.get("schema_digest", ""), value.get("server", ""),
                   value.get("build", ""), value.get("project_id", ""),
                   tuple(Capability.from_dict(item) for item in capabilities),
                   value.get("limits", {}))

    def supports(self, operation: str) -> bool:
        return any(cap.operation == operation for cap in self.capabilities)


def _validate_limits(limits: Mapping[str, Any]) -> None:
    if not isinstance(limits, Mapping) or len(limits) > 64:
        raise ValidationError("INVALID_LIMIT", "limits")
    for key, value in limits.items():
        _text(key, "limit.name")
        if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > SAFE_INTEGER:
            raise ValidationError("INVALID_LIMIT", key)


class Status(str, Enum):
    ACCEPTED_PENDING = "ACCEPTED_PENDING"
    COMMITTED = "COMMITTED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"
    CANCELED = "CANCELED"


@dataclass(frozen=True)
class Request:
    command_id: str
    project_id: str
    operation: str
    lease_id: str
    fencing_epoch: int
    expected_revision: str
    target: Mapping[str, str]
    payload: Mapping[str, Any]
    payload_hash: str
    deadline_ms: int
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _text(self.command_id, "command_id")
        _text(self.project_id, "project_id")
        _text(self.operation, "operation", pattern=_OP)
        _text(self.lease_id, "lease_id")
        _text(self.expected_revision, "expected_revision")
        if not isinstance(self.fencing_epoch, int) or isinstance(self.fencing_epoch, bool) or self.fencing_epoch < 0:
            raise ValidationError("INVALID_FIELD", "fencing_epoch")
        if not isinstance(self.deadline_ms, int) or self.deadline_ms <= 0 or self.deadline_ms > 86_400_000:
            raise ValidationError("INVALID_DEADLINE", "deadline_ms")
        if self.schema_version != SCHEMA_VERSION:
            raise ValidationError("UNSUPPORTED_SCHEMA", self.schema_version)
        if not isinstance(self.target, Mapping) or set(self.target) not in ({"stable_id"}, {"path"}):
            raise ValidationError("INVALID_TARGET", "exactly stable_id or path")
        for key, value in self.target.items():
            _text(value, f"target.{key}")
        if not isinstance(self.payload, Mapping) or len(canonical_bytes(self.payload)) > MAX_PAYLOAD_BYTES:
            raise ValidationError("PAYLOAD_TOO_LARGE", str(MAX_PAYLOAD_BYTES))
        expected = _payload_hash(self.payload)
        if self.payload_hash != expected:
            raise ValidationError("PAYLOAD_HASH_MISMATCH", expected)

    @property
    def digest(self) -> str:
        body = {"operation": self.operation, "target": dict(self.target),
                "payload": self.payload, "schema_version": self.schema_version}
        return "sha256:" + hashlib.sha256(canonical_bytes(body)).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        return {"command_id": self.command_id, "schema_version": self.schema_version,
                "project_id": self.project_id, "operation": self.operation,
                "lease_id": self.lease_id, "fencing_epoch": self.fencing_epoch,
                "expected_revision": self.expected_revision, "target": dict(self.target),
                "payload": self.payload, "payload_hash": self.payload_hash,
                "deadline_ms": self.deadline_ms, "digest": self.digest}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Request":
        if not isinstance(value, Mapping):
            raise ValidationError("INVALID_ENVELOPE", "request object required")
        required = {"command_id", "schema_version", "project_id", "operation", "lease_id",
                    "fencing_epoch", "expected_revision", "target", "payload", "payload_hash", "deadline_ms"}
        # ``digest`` is a derived, optional readback field emitted by as_dict.
        _reject_unknown(value, required | {"digest"}, "request")
        missing = required - set(value)
        if missing:
            raise ValidationError("MISSING_FIELD", sorted(missing)[0])
        request = cls(*(value[name] for name in ("command_id", "project_id", "operation", "lease_id",
                    "fencing_epoch", "expected_revision", "target", "payload", "payload_hash", "deadline_ms", "schema_version")))
        if "digest" in value and value["digest"] != request.digest:
            raise ValidationError("DIGEST_MISMATCH", "request.digest")
        return request

    @classmethod
    def from_json(cls, data: str | bytes) -> "Request":
        value = parse_json(data)
        return cls.from_dict(value)


@dataclass(frozen=True)
class Response:
    status: Status
    code: str
    command_id: str
    result_revision: str | None = None
    result_hash: str | None = None
    postconditions: Mapping[str, Any] = field(default_factory=dict)
    retry_after_ms: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, Status):
            try:
                object.__setattr__(self, "status", Status(self.status))
            except ValueError as exc:
                raise ValidationError("INVALID_STATUS", str(self.status)) from exc
        _text(self.code, "code")
        _text(self.command_id, "command_id")
        if self.retry_after_ms is not None and (not isinstance(self.retry_after_ms, int) or self.retry_after_ms < 0):
            raise ValidationError("INVALID_FIELD", "retry_after_ms")
        _walk(self.postconditions)

    def as_dict(self) -> dict[str, Any]:
        result = {"status": self.status.value, "code": self.code, "command_id": self.command_id,
                  "result_revision": self.result_revision, "result_hash": self.result_hash,
                  "postconditions": self.postconditions}
        if self.retry_after_ms is not None:
            result["retry_after_ms"] = self.retry_after_ms
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Response":
        if not isinstance(value, Mapping):
            raise ValidationError("INVALID_RESPONSE", "object required")
        required = {"status", "code", "command_id"}
        _reject_unknown(value, required | {"result_revision", "result_hash", "postconditions", "retry_after_ms"}, "response")
        missing = required - set(value)
        if missing:
            raise ValidationError("MISSING_FIELD", sorted(missing)[0])
        return cls(value["status"], value["code"], value["command_id"],
                   value.get("result_revision"), value.get("result_hash"),
                   value.get("postconditions", {}), value.get("retry_after_ms"))


def validate_for_dispatch(request: Request, discovery: Discovery) -> None:
    """Apply capability/project gates before lease acquisition or mutation."""
    if request.schema_version != discovery.schema_version:
        raise ValidationError("UNSUPPORTED_SCHEMA", request.schema_version)
    if request.project_id != discovery.project_id:
        raise ValidationError("PROJECT_MISMATCH", request.project_id)
    if not discovery.supports(request.operation):
        raise ValidationError("UNSUPPORTED_OPERATION", request.operation)


def resolve_project_path(root: str | os.PathLike[str], relative: str) -> Path:
    """Resolve a project-relative path and reject traversal/reparse escapes."""
    if not isinstance(relative, str) or not relative or "\x00" in relative:
        raise ValidationError("INVALID_PATH", "path")
    wire_parts = re.split(r"[\\/]", relative)
    if (_FORBIDDEN_PATH.search(relative) or os.path.isabs(relative)
            or relative.startswith(("/", "\\"))
            or re.match(r"^[A-Za-z]:", relative)
            or any(part in ("", ".", "..") for part in wire_parts)
            or ":" in wire_parts[-1]):
        raise ValidationError("PATH_OUTSIDE_ROOT", relative)
    root_path = Path(root).resolve(strict=True)
    candidate = (root_path / Path(relative)).resolve(strict=False)
    try:
        candidate.relative_to(root_path)
    except ValueError as exc:
        raise ValidationError("PATH_OUTSIDE_ROOT", relative) from exc
    current = root_path
    for part in Path(relative).parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise ValidationError("REPARSE_OR_SYMLINK", relative)
    return candidate

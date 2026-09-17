"""Bounded redaction at host log, receipt and tool-output boundaries.

This is an output policy, never permission to execute returned content. Raw
argv/environment/capture fields are omitted wholesale: a textual scrubber
cannot prove that an arbitrary argument or image does not contain a secret.
Callers register session secrets before accepting input and must send every
diagnostic/output through ``encode`` or ``RedactedBoundary``. Do not log the
original value on rejection. Exceptions contain fixed codes only.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import math
import re
from typing import Any, Callable, Iterable
from urllib.parse import quote, quote_plus

from .limits import SafetyViolation

try:
    from studio.protocol._rfc8785 import dumps as _jcs_dumps
except ImportError:
    from protocol._rfc8785 import dumps as _jcs_dumps


REDACTED = "[REDACTED]"
_SENSITIVE = re.compile(
    r"token|secret|password|passwd|credential|authorization|cookie|privatekey|apikey",
    re.IGNORECASE,
)
_OPAQUE_KEYS = frozenset({"argv", "args", "commandline", "environment", "environ", "env",
                          "environmentdump", "environmentvariables", "envdump",
                          "screenshot", "capture", "image", "binary", "rawbody", "rawrequest"})
_SECRET_LINE = re.compile(
    r"(?:authorization|bearer|password|passwd|api[_-]?key|access[_-]?token|"
    r"session[_-]?token|token|private[_ -]?key|secret|credential|cookie)[\"']?\s*(?:[=:]|\s)", re.IGNORECASE,
)
_WIN_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\)[^\r\n\"'<>|]*")
_POSIX_PATH = re.compile(r"(?<![\w/])/(?!/)[^\s\"'<>|]+")


@dataclass(frozen=True)
class RedactionLimits:
    max_depth: int = 16
    max_nodes: int = 4096
    max_items: int = 256
    max_text_chars: int = 65_536
    max_total_text_chars: int = 262_144
    max_output_bytes: int = 262_144
    max_secrets: int = 128
    max_secret_chars: int = 8192
    max_registered_chars: int = 65_536

    def __post_init__(self) -> None:
        for value in self.__dict__.values():
            if type(value) is not int or value <= 0:
                raise SafetyViolation("INVALID_REDACTION_LIMITS")


class Redactor:
    """Deterministic JSON copy with bounded traversal and no object repr calls."""

    def __init__(self, *, secrets: Iterable[str] = (), host_paths: Iterable[str] = (),
                 limits: RedactionLimits = RedactionLimits()) -> None:
        self.limits = limits
        replacements: set[str] = set()
        count = total = 0
        # Consume iterables incrementally; never materialize an unbounded iterable.
        for values, is_path in ((secrets, False), (host_paths, True)):
            for value in values:
                count += 1
                if count > limits.max_secrets:
                    raise SafetyViolation("REDACTION_REGISTRATION_LIMIT")
                if type(value) is not str or not value or len(value) > limits.max_secret_chars:
                    raise SafetyViolation("INVALID_REDACTION_REGISTRATION")
                total += len(value)
                if total > limits.max_registered_chars:
                    raise SafetyViolation("REDACTION_REGISTRATION_LIMIT")
                try:
                    encoded = value.encode("utf-8", "strict")
                except UnicodeError:
                    raise SafetyViolation("INVALID_REDACTION_REGISTRATION") from None
                variants = {value, json.dumps(value, ensure_ascii=True)[1:-1],
                            quote(value, safe=""), quote_plus(value, safe="")}
                if is_path:
                    variants.update({value.replace("\\", "/"), value.replace("/", "\\")})
                else:
                    variants.add(base64.b64encode(encoded).decode("ascii"))
                replacements.update(variants)
        self._replacements = tuple(sorted(replacements, key=lambda item: (-len(item), item)))
        self._replacement_pattern = (re.compile("|".join(re.escape(item) for item in self._replacements))
                                     if self._replacements else None)

    def __repr__(self) -> str:
        return "Redactor(<private registrations>)"

    def text(self, value: str | bytes) -> str:
        if type(value) is bytes:
            if len(value) > self.limits.max_text_chars:
                raise SafetyViolation("REDACTION_TEXT_LIMIT")
            try:
                value = value.decode("utf-8", "strict")
            except UnicodeError:
                return "[REDACTED:INVALID_UTF8]"
        if type(value) is not str:
            raise SafetyViolation("REDACTION_UNSUPPORTED_TYPE")
        if len(value) > self.limits.max_text_chars:
            raise SafetyViolation("REDACTION_TEXT_LIMIT")
        try:
            value.encode("utf-8", "strict")
        except UnicodeError:
            return "[REDACTED:INVALID_UNICODE]"
        if self._replacement_pattern is not None:
            # One pass avoids recursively replacing markers for short secrets.
            value = self._replacement_pattern.sub(REDACTED, value)
        # Whole-line redaction safely covers malformed parser fragments and
        # quoted values containing spaces without trying to repair hostile JSON.
        value = "\n".join(REDACTED if _SECRET_LINE.search(line) else line
                          for line in value.split("\n"))
        value = _WIN_PATH.sub("[HOST_PATH]", value)
        value = _POSIX_PATH.sub("[HOST_PATH]", value)
        if len(value) > self.limits.max_text_chars:
            raise SafetyViolation("REDACTION_TEXT_LIMIT")
        return value

    def redact(self, value: Any) -> Any:
        active: set[int] = set()
        nodes = 0
        total_text = 0

        def scrub_text(item: str) -> str:
            nonlocal total_text
            total_text += len(item)
            if total_text > self.limits.max_total_text_chars:
                raise SafetyViolation("REDACTION_TOTAL_TEXT_LIMIT")
            return self.text(item)

        def visit(item: Any, depth: int) -> Any:
            nonlocal nodes
            nodes += 1
            if nodes > self.limits.max_nodes:
                raise SafetyViolation("REDACTION_NODE_LIMIT")
            if depth > self.limits.max_depth:
                raise SafetyViolation("REDACTION_DEPTH_LIMIT")
            if item is None or type(item) is bool:
                return item
            if type(item) is int:
                if abs(item) > (1 << 53) - 1:
                    raise SafetyViolation("REDACTION_INVALID_NUMBER")
                return item
            if type(item) is float:
                if not math.isfinite(item):
                    raise SafetyViolation("REDACTION_INVALID_NUMBER")
                return item
            if type(item) is str:
                return scrub_text(item)
            if type(item) not in (dict, list, tuple):
                raise SafetyViolation("REDACTION_UNSUPPORTED_TYPE")
            if len(item) > self.limits.max_items:
                raise SafetyViolation("REDACTION_ITEM_LIMIT")
            identity = id(item)
            if identity in active:
                raise SafetyViolation("REDACTION_CYCLE")
            active.add(identity)
            try:
                if type(item) is dict:
                    result: dict[str, Any] = {}
                    if any(type(key) is not str for key in item):
                        raise SafetyViolation("REDACTION_INVALID_KEY")
                    # Stable order includes the collision failure behavior.
                    for key in sorted(item):
                        clean_key = scrub_text(key)
                        if clean_key in result:
                            raise SafetyViolation("REDACTION_KEY_COLLISION")
                        normalized = re.sub(r"[^a-z0-9]", "", key.lower())
                        if _SENSITIVE.search(normalized) or normalized in _OPAQUE_KEYS:
                            result[clean_key] = REDACTED
                        else:
                            result[clean_key] = visit(item[key], depth + 1)
                    return result
                return [visit(child, depth + 1) for child in item]
            finally:
                active.remove(identity)

        return visit(value, 0)

    def encode(self, value: Any) -> bytes:
        clean = self.redact(value)
        try:
            # Request validation forbids secret-shaped keys. Evidence instead
            # retains those keys with redacted values, so serialize this already
            # bounded tree with the same vendored JCS encoder, not Request policy.
            encoded = _jcs_dumps(clean)
        except (TypeError, ValueError, UnicodeError):
            raise SafetyViolation("REDACTION_ENCODING_FAILED") from None
        if len(encoded) > self.limits.max_output_bytes:
            raise SafetyViolation("REDACTION_OUTPUT_LIMIT")
        return encoded


class RedactedBoundary:
    """The only bytes handed to a sink have passed the complete output policy.

    ``emit_bytes`` may be a binary file's ``write``, socket sender or bounded
    in-memory collector. Partial writes and sink errors fail with static codes;
    never fall back to writing the unredacted input or an exception repr.
    """

    def __init__(self, emit_bytes: Callable[[bytes], object], *, redactor: Redactor) -> None:
        self._emit_bytes = emit_bytes
        self._redactor = redactor

    def emit(self, kind: str, payload: Any) -> dict[str, Any]:
        if kind not in ("log", "receipt", "output"):
            raise SafetyViolation("INVALID_OUTPUT_KIND")
        encoded = self._redactor.encode({"kind": kind, "payload": payload}) + b"\n"
        try:
            written = self._emit_bytes(encoded)
        except Exception:
            raise SafetyViolation("OUTPUT_SINK_FAILED") from None
        if written is not None and (type(written) is not int or written != len(encoded)):
            raise SafetyViolation("OUTPUT_SINK_FAILED")
        return json.loads(encoded)

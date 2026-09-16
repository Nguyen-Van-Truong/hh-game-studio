"""Bounded display-name validation before constructing a semantic command.

This fixture-level domain policy is separate from JSON/JCS validation. Call
``validate_name`` on a display name before putting it into a new command.
It returns the exact input or rejects it; it never normalizes, truncates or
rewrites a payload, command ID, target path or digest. Future operation domains
may add their own naming rules without changing canonical wire semantics.
"""
from __future__ import annotations

import unicodedata

MAX_NAME_CHARS = 128
MAX_NAME_UTF8_BYTES = 512
_CONTROL_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Zl", "Zp"})


class NameValidationError(ValueError):
    """Static code only: rejected names must never become error output."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def validate_name(value: str) -> str:
    """Accept a nonempty NFC name of at most 128 scalars and 512 UTF-8 bytes.

    Control/format characters and line/paragraph separators are excluded so
    a display name cannot inject terminal controls or conceal its spelling.
    Surrogates are rejected before normalization. Spaces and ordinary Unicode
    text are allowed; this does not assert any game-specific naming policy.
    """
    if type(value) is not str:
        raise NameValidationError("NAME_INVALID_TYPE")
    if not value:
        raise NameValidationError("NAME_EMPTY")
    if len(value) > MAX_NAME_CHARS:
        raise NameValidationError("NAME_TOO_LONG")
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeError:
        raise NameValidationError("NAME_INVALID_UNICODE") from None
    if len(encoded) > MAX_NAME_UTF8_BYTES:
        raise NameValidationError("NAME_TOO_LONG")
    if any(unicodedata.category(char) in _CONTROL_CATEGORIES for char in value):
        raise NameValidationError("NAME_CONTROL_FORBIDDEN")
    if unicodedata.normalize("NFC", value) != value:
        raise NameValidationError("NAME_NOT_NFC")
    return value

"""Small, dependency-free protocol core for HH Studio adapters.

This module deliberately contains no transport or execution primitive.  It
only validates and canonicalises envelopes before an adapter is allowed to
dispatch an operation.  Consumers should treat :class:`ValidationError`
codes as stable wire values.
"""
from .core import (
    PROTOCOL_VERSION,
    SCHEMA_VERSION,
    Capability,
    Discovery,
    Request,
    Response,
    Status,
    ValidationError,
    canonical_bytes,
    canonical_json,
    parse_json,
    resolve_project_path,
    validate_for_dispatch,
    redact_for_evidence,
)

__all__ = [
    "PROTOCOL_VERSION", "SCHEMA_VERSION", "Capability", "Discovery",
    "Request", "Response", "Status", "ValidationError", "canonical_bytes",
    "canonical_json", "parse_json", "resolve_project_path", "validate_for_dispatch",
    "redact_for_evidence",
]

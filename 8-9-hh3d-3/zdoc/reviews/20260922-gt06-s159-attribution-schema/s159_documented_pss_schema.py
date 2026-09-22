"""Process-free schema gate for documented PSS handle observations.

The S157 attribution experiment cannot use reserved PSS_HANDLE_ENTRY fields
for temporal or ownership inference.  This module accepts only fields whose
meaning is documented for the capture and keeps object identity explicit as
UNKNOWN unless another proof exists.
"""
from __future__ import annotations

DOCUMENTED_FIELDS = frozenset({
    "handle",
    "type",
    "object_type",
    "type_name",
    "name_state",
    "name_sha256",
    "attributes",
    "type_specific_information",
    "capture_time_filetime",
    "object_identity",
})
RESERVED_FIELDS = frozenset({
    "creation_time_filetime",
    "granted_access",
    "handle_count",
    "pointer_count",
    "paged_pool_charge",
    "nonpaged_pool_charge",
})
PRIMARY_SOURCE = "https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ns-processsnapshot-pss_handle_entry"


class SchemaError(ValueError):
    pass


def validate_entry(entry: dict) -> dict:
    if not isinstance(entry, dict):
        raise SchemaError("S159_ENTRY_OBJECT_REQUIRED")
    keys = set(entry)
    reserved = sorted(keys & RESERVED_FIELDS)
    if reserved:
        raise SchemaError("S159_RESERVED_PSS_FIELD:" + ",".join(reserved))
    unknown = sorted(keys - DOCUMENTED_FIELDS)
    if unknown:
        raise SchemaError("S159_UNDOCUMENTED_PSS_FIELD:" + ",".join(unknown))
    if entry.get("object_identity", "UNKNOWN") != "UNKNOWN":
        raise SchemaError("S159_OBJECT_IDENTITY_UNPROVEN")
    return {
        "valid": True,
        "causal_timing_eligible": False,
        "object_identity": "UNKNOWN",
        "fields": sorted(keys),
        "primary_source": PRIMARY_SOURCE,
        "authority": 0,
        "formal_acceptance": False,
    }

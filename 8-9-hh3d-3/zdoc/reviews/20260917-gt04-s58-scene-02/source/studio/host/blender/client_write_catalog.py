"""Pure GT04 write-catalog integration candidate, separate from read-only owners.

Validation and translation establish syntax and byte identity only. They do not
register a writer, acquire a lease, inspect Blender, dispatch work, or grant a
durable public ACK. The integrating owner must check its exact live host, grant,
fence, revision/context and absolute deadline again before native execution.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping

from studio.protocol.core import (
    Capability, Discovery, PROTOCOL_VERSION, Request, SCHEMA_VERSION,
    ValidationError, canonical_bytes, parse_json, validate_for_dispatch,
)
from . import client_ledger as ledger
from . import publication_state

queue = ledger.queue
TARGET = "blender.owned-scene"
READ = "scene.inspect"
EDIT_OPERATIONS = frozenset({
    "mesh.create_box", "object.transform.set", "material.set_principled",
    "history.undo", "history.redo",
})
WRITE_OPERATIONS = EDIT_OPERATIONS | {"scene.save", "checkpoint.save", "export.publish"}
OPERATIONS = WRITE_OPERATIONS | {READ, "control.lookup", "control.stop"}
MAX_COMMANDS = ledger.MAX_COMMANDS
MAX_REQUEST_BYTES = ledger.MAX_REQUEST_BYTES
MAX_WIRE = ledger.MAX_RESPONSE_BYTES
MAX_READ_MS = 2000
MAX_LEASE_MS = 30000
MAX_UI_MS = 5000
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_PROJECT = re.compile(r"[a-z][a-z0-9._-]{0,63}\Z")
_SAVE_SLOTS = {"scene.save": "fixture", "checkpoint.save": "checkpoint"}
_VALIDATION_ID = "client-" + "0" * 40


def _operation_descriptor(operation: str) -> dict[str, Any]:
    """Describe the existing validator, without a second domain schema."""
    edit = operation in EDIT_OPERATIONS
    publication = operation in publication_state.PROFILES
    return {
        "read_scopes": ["blender.scene.read"],
        "write_scopes": ["blender.scene.write"],
        "payload_fields": ["expected_context", "arguments"],
        "expected_context": "exact native context: mode, active_id, selected_ids",
        "arguments_validator": (
            "HH-BLENDER-FIXTURE-COMMAND-1:" + operation + ":payload"
            if operation in {"mesh.create_box", "object.transform.set", "material.set_principled"}
            else "exact empty object"
        ),
        "native_protocol": publication_state.SCHEMA if operation == 'export.publish' else queue.SCHEMA,
        "writer_lease_required": True,
        "expected_revision": "exact live native revision; owner must compare",
        "dry_run": ("/v1/preview: native no-effect precondition inspection; no apply ID reservation"
                    if edit else "schema validation only; publication preview not connected"),
        "diff_supported": edit,
        "diff_policy": "observed received-JCS before/after; native revisions remain opaque" if edit else None,
        "affected_files": (
            [] if edit else list(publication_state.NAMES) + ["protected manifest and selector"]
        ),
        "undo_policy": (
            "native revision-checked transient UI history; newer manual edits must not be overwritten"
            if edit else "one immutable verified bundle per profile; no writable restart or automatic replay"
        ),
        "scene_state_durable": False,
        "live_edits_unsaved": edit,
        "publication_owner_required": publication,
        "publication_profile": operation if publication else None,
        "publication_limits": ("OBJECT mode, nonempty supported fixture; checkpoint.blend + verified GLB sidecar"
                               if publication else None),
        "public_ack": False,
    }


DESCRIPTOR = {
    "schema": "HH-BLENDER-WRITE-CLIENT-1",
    "protocol_version": PROTOCOL_VERSION,
    "schema_version": SCHEMA_VERSION,
    "integration_candidate": True,
    "registration": "requires exact owned native host, durable session and authenticated writer binding",
    "request": "Request",
    "response": "Response",
    "target": {"stable_id": TARGET},
    "operations": {
        READ: {
            "read_scopes": ["blender.scene.read"], "write_scopes": [], "payload": {},
            "read_lease_required": True, "expected_revision": "exact live native revision",
        },
        **{operation: _operation_descriptor(operation) for operation in sorted(WRITE_OPERATIONS)},
    },
    "controls": ["discovery", "read-lease", "write-lease", "lookup-own-session", "stop"],
    "limits": {
        "max_commands": MAX_COMMANDS, "max_pending": 1,
        "max_request_bytes": MAX_REQUEST_BYTES, "max_native_bytes": queue.c.MAX_BYTES,
        "max_response_bytes": MAX_WIRE, "max_read_ms": MAX_READ_MS,
        "max_lease_ms": MAX_LEASE_MS, "max_ui_ms": MAX_UI_MS,
    },
    "retention": "public/private ledger binding required before dispatch; unresolved lookup never redispatches",
    "scene_durable": False,
    "native_checkpoint_protected_publication": True,
    "public_ack": False,
    "external_inputs": [],
    "unsupported": [
        "arbitrary paths or blend intake", "linked libraries or textures", "remote code execution",
        "writable restart", "restored undo history", "durable public ACK",
    ],
}
CATALOG_DIGEST = "sha256:" + hashlib.sha256(canonical_bytes(DESCRIPTOR)).hexdigest()
# The exported descriptor is documentation, not mutable validation authority.
_DESCRIPTOR_RAW = canonical_bytes(DESCRIPTOR)


def _need(condition: Any, code: str, message: str) -> None:
    if not condition:
        raise ValidationError(code, message)


def _json_types(value: Any) -> None:
    """Reject Python-only containers before serialization can coerce their type."""
    if type(value) is dict:
        for child in value.values():
            _json_types(child)
    elif type(value) is list:
        for child in value:
            _json_types(child)
    elif type(value) not in (str, int, float, bool, type(None)):
        raise ValidationError("BLENDER_INVALID_JSON_TYPE", "strict JSON values required")


def discovery(project_id: str, *, source_sha256: str, readable: bool = True,
              writable: bool = False) -> Discovery:
    """Describe candidate capabilities; booleans do not constitute a grant."""
    _need(type(project_id) is str and _PROJECT.fullmatch(project_id),
          "BLENDER_INVALID_PROJECT", "registered project identifier required")
    _need(type(source_sha256) is str and _HASH.fullmatch(source_sha256),
          "BLENDER_INVALID_SOURCE", "source closure digest required")
    _need(type(readable) is bool and type(writable) is bool,
          "BLENDER_INVALID_CAPABILITY", "boolean visibility required")
    limits = parse_json(_DESCRIPTOR_RAW)["limits"]
    operations = ([READ] if readable else []) + (sorted(WRITE_OPERATIONS) if writable else [])
    capabilities = tuple(
        Capability(operation, ("blender.scene.read",),
                   () if operation == READ else ("blender.scene.write",), dict(limits))
        for operation in operations
    )
    return Discovery(PROTOCOL_VERSION, SCHEMA_VERSION, CATALOG_DIGEST,
                     "hh.blender.writer-candidate", source_sha256, project_id,
                     capabilities, limits)


def _native_command(request: Request, private_id: str) -> dict[str, Any]:
    """Delegate all native argument, finite/range and context checks."""
    if request.operation == READ:
        native = {
            "schema": queue.SCHEMA, "command_id": private_id, "operation": READ,
            "expected_revision": None, "expected_context": None, "payload": {},
        }
    elif request.operation == "export.publish":
        native = {
            "schema": publication_state.SCHEMA, "command_id": private_id,
            "expected_revision": request.expected_revision,
            "expected_context": request.payload["expected_context"],
        }
    else:
        native = {
            "schema": queue.SCHEMA, "command_id": private_id,
            "operation": "checkpoint.save" if request.operation in _SAVE_SLOTS else request.operation,
            "expected_revision": request.expected_revision,
            "expected_context": request.payload["expected_context"],
            "payload": ({"slot": _SAVE_SLOTS[request.operation]} if request.operation in _SAVE_SLOTS
                        else request.payload["arguments"]),
        }
    try:
        if request.operation == "export.publish":
            return publication_state.validate_request(native)
        return queue.parse(queue.c.canonical(native))
    except (queue.c.Rejected, publication_state.PublicationError, TypeError,
            ValueError, OverflowError, RecursionError) as error:
        raise ValidationError("BLENDER_INVALID_PAYLOAD", "native command validation rejected") from error


def validate_request(body: Mapping[str, Any], *, project_id: str, source_sha256: str) -> Request:
    """Validate detached public syntax, never an actual lease or native state."""
    raw = canonical_bytes(body)  # Common depth/finite/Unicode/secret limits first.
    _need(len(raw) <= MAX_REQUEST_BYTES, "BLENDER_REQUEST_LIMIT", "bounded public request required")
    _json_types(body)
    # JCS deliberately renders 1.0 as 1. Check envelope integer types before
    # the detached wire copy could erase that difference.
    Request.from_dict(body)
    request = Request.from_dict(parse_json(raw))
    validate_for_dispatch(request, discovery(project_id, source_sha256=source_sha256, writable=True))
    _need(dict(request.target) == {"stable_id": TARGET},
          "BLENDER_TARGET_MISMATCH", "fixed owned scene required")
    _need(_HASH.fullmatch(request.expected_revision),
          "BLENDER_INVALID_REVISION", "native revision digest required")
    if request.operation == READ:
        _need(request.payload == {}, "BLENDER_INVALID_PAYLOAD", "empty inspect payload required")
        _need(request.fencing_epoch == 0, "BLENDER_READ_LEASE_REQUIRED", "read fence must be zero")
    else:
        _need(request.fencing_epoch > 0, "BLENDER_WRITER_FENCE_REQUIRED", "positive writer fence required")
        _need(set(request.payload) == {"expected_context", "arguments"},
              "BLENDER_INVALID_PAYLOAD", "exact context and arguments required")
        if request.operation not in EDIT_OPERATIONS:
            _need(request.payload["arguments"] == {},
                  "BLENDER_INVALID_PAYLOAD", "empty arguments and owner-fixed artifacts required")
            _need(type(request.payload['expected_context']) is dict and request.payload['expected_context'].get('mode') == 'OBJECT',
                  'BLENDER_PUBLICATION_OBJECT_MODE_REQUIRED', 'fixed publication profile requires OBJECT mode')
    _native_command(request, _VALIDATION_ID)
    return request


def translate(request: Request, *, binding: ledger.LedgerBinding, session_id: str) -> bytes:
    """Return canonical private bytes bound to the complete public identity.

    The caller must persist these bytes through the client ledger before effect.
    Export bytes belong to PublicationState, never to the UI command endpoint.
    """
    _need(type(request) is Request, "BLENDER_INVALID_REQUEST", "common Request required")
    try:
        bound = ledger.binding_value(binding)
        _need(bound["catalog_digest"] == CATALOG_DIGEST,
              "BLENDER_CATALOG_MISMATCH", "write-catalog binding required")
        validated = validate_request(request.as_dict(), project_id=bound["project_id"],
                                     source_sha256=bound["source_sha256"])
        private_id = ledger.private_alias(binding, session_id, validated.command_id)
        native = _native_command(validated, private_id)
        # Keep exactly the same cross-protocol checks as persisted admission.
        intent = ledger.make_intent(binding, session_id, validated, native)
        return ledger.unchunk(intent["native_chunks"], queue.c.MAX_BYTES)
    except ledger.LedgerError as error:
        raise ValidationError(error.code, "public/private binding rejected") from error

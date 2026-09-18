"""Finite, local operator/client guidance for GT-02 result and error codes.

No exception detail or unknown input is interpolated into this reference.
Guidance never grants a capability, changes a wire field, performs a retry or
turns UNKNOWN/PENDING into success. The response status and durable lookup
remain authoritative. ERRORS.md documents how consumers use this catalog.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class ErrorGuidance:
    code: str
    meaning: str
    next_action: str


# Explicit finite membership, grouped only where the remedy is the same.
# These strings are reviewed source, never generated from a received message.
_GROUPS: tuple[tuple[str, str, str], ...] = (
    ("INVALID_JSON INVALID_JSON_INPUT INVALID_UTF8 INVALID_UNICODE NON_CANONICAL_JSON",
     "The input cannot be admitted as unambiguous UTF-8 JSON.",
     "Encode strict UTF-8 JSON with valid Unicode scalars; validate locally before submitting a corrected command."),
    ("DUPLICATE_KEY",
     "An object repeats a JSON member name.",
     "Remove duplicate members at the source; do not choose a first or last value silently."),
    ("INVALID_NUMBER NON_FINITE_NUMBER REDACTION_INVALID_NUMBER",
     "A number is outside the finite JSON numeric domain.",
     "Use a finite value allowed by the operation schema; never serialize NaN or Infinity."),
    ("INTEGER_REQUIRES_DECIMAL_STRING",
     "An integer exceeds the exact IEEE-754 safe-integer range.",
     "Represent the integer as decimal text where the schema allows it; do not round it to binary64."),
    ("INVALID_KEY INVALID_OBJECT_KEY REDACTION_INVALID_KEY",
     "An object key is not a valid Unicode string.",
     "Supply Unicode string keys without surrogates; validate the corrected object before submission."),
    ("INVALID_TYPE INVALID_FIELD INVALID_ENVELOPE INVALID_TARGET INVALID_FIXTURE_PAYLOAD INVALID_COMMAND_ID MISSING_FIELD UNKNOWN_FIELD",
     "The request does not match the declared command schema.",
     "Read discovery and the operation schema, correct fields/types/target, and compute the corrected command digest before submitting."),
    ("INVALID_DIGEST DIGEST_MISMATCH PAYLOAD_HASH_MISMATCH",
     "The supplied digest is malformed or differs from canonical content.",
     "Recompute JCS payload and request hashes from the exact intended content; investigate any unexpected change before submission."),
    ("UNSUPPORTED_VERSION UNSUPPORTED_SCHEMA UNSUPPORTED_OPERATION UNSUPPORTED_ROUTE",
     "The server does not expose the requested protocol, schema or operation.",
     "Use the current discovery contract or a compatible reviewed client; do not fall back to arbitrary execution."),
    ("UNSUPPORTED_OPEN_LANE",
     "Arbitrary-code execution is disabled by the host policy.",
     "Use the declared semantic operations; a wire request cannot enable an open execution lane."),
    ("INVALID_CAPABILITY INVALID_DISCOVERY INVALID_RESPONSE INVALID_STATUS INVALID_LEASE_RESPONSE INVALID_ARCHIVE_RESPONSE",
     "A peer response or capability description violates the typed contract.",
     "Reject the response as evidence of success; compare the pinned client/server schemas and use authenticated lookup for uncertain commands."),
    ("INVALID_LIMIT INVALID_TRANSPORT_LIMITS INVALID_REDACTION_LIMITS INVALID_SESSION_POLICY INVALID_ORIGIN_POLICY INVALID_LOOPBACK_PORT INVALID_PENDING INVALID_OUTPUT_KIND",
     "Trusted local configuration is invalid.",
     "Correct the local configuration against the documented bounded profile before starting the host; do not relax it from received data."),
    ("INVALID_CLOCK INVALID_DEADLINE DEADLINE_OUT_OF_RANGE DEADLINE_BEFORE_APPLY",
     "The command clock or deadline is invalid or elapsed before application.",
     "Check Unix-epoch milliseconds and the negotiated deadline horizon; lookup any existing command ID before planning another attempt."),
    ("MESSAGE_TOO_LARGE ENVELOPE_TOO_LARGE PAYLOAD_TOO_LARGE RESULT_TOO_LARGE STRING_LIMIT DEPTH_LIMIT OBJECT_MEMBER_LIMIT ARRAY_ITEM_LIMIT",
     "A message exceeds a declared byte, shape or text bound.",
     "Reduce the request or use supported pagination/operation granularity; do not increase host limits from the wire."),
    ("PROJECT_MISMATCH TARGET_OUTSIDE_SCOPE SCOPE_DENIED",
     "The authenticated request is outside its project or capability scope.",
     "Select the already-authorized project and operation; request access through the local authority if required, never infer it from payload text."),
    ("AUTH_REQUIRED SESSION_EXPIRED SESSION_INVALIDATED",
     "The session credential is missing, expired, revoked or replaced.",
     "Obtain a credential through the private local channel, then lookup outstanding command IDs; never put credentials in arguments or diagnostics."),
    ("SESSION_LIMIT CREDENTIAL_HISTORY_LIMIT",
     "The bounded session or retained-secret budget is exhausted.",
     "Stop issuing credentials; let the local operator drain and establish a new host boundary when required, without forgetting secrets in the current host."),
    ("SECRET_FIELD_FORBIDDEN SENSITIVE_IDENTIFIER_FORBIDDEN",
     "A secret-bearing field or identifier is forbidden in retained command data.",
     "Remove the credential from command data and use the private credential channel; keep command identifiers public and stable."),
    ("INVALID_PATH INVALID_PATH_UNICODE PATH_TRAVERSAL PATH_ESCAPE PATH_OUTSIDE_ROOT DEVICE_OR_ADS_PATH PATH_ALIAS_OR_INVALID PATH_CASE_ALIAS PATH_TOO_LONG",
     "The path spelling violates project confinement or alias rules.",
     "Use an exact project-relative path within the allowed root; do not decode aliases or bypass the resolver with raw filesystem calls."),
    ("PATH_NOT_FOUND DESTINATION_EXISTS UNEXPECTED_FILE_TYPE",
     "The destination does not have the required existence or file type.",
     "Inspect the current allowed project state, then select an existing compatible target or an unused destination as required by the operation."),
    ("PATH_DIRECTORY_LIMIT SAFE_FILE_SIZE_LIMIT",
     "A filesystem inspection exceeds its bounded directory or file size.",
     "Use a smaller staged input or directory within the documented limits; keep the same confinement checks."),
    ("REPARSE_OR_SYMLINK HARDLINK_UNSAFE FILE_DELETE_PENDING ROOT_PATH_CHANGED ROOT_IDENTITY_CHANGED DIRECTORY_IDENTITY_CHANGED FILE_IDENTITY_CHANGED FINAL_PATH_MISMATCH UNVERIFIED_FINAL_PATH",
     "The file namespace or held-handle identity cannot be trusted.",
     "Stop using the affected path, preserve diagnostics, and rebuild a private verified staging root; never retry through a followed link or stale path."),
    ("INVALID_PROJECT INVALID_PROJECT_ROOT",
     "The configured project root is invalid or unsafe.",
     "Configure an existing canonical private project directory, then repeat the root and capability probe."),
    ("UNSUPPORTED_SAFE_OPEN_WINDOWS UNSUPPORTED_SAFE_OPEN_LINUX",
     "The required platform-safe mutation primitive is unavailable.",
     "Keep consumer file mutation disabled and report the capability gap; use only independently verified supported read operations."),
    ("SAFE_OPEN_DENIED SAFE_READ_FAILED",
     "A held-handle file operation was denied or failed.",
     "Inspect permissions and conflicting handles on the private root; reprobe identity before retrying the supported read operation."),
    ("COMMAND_ID_PAYLOAD_CONFLICT",
     "A command ID already names a different canonical command.",
     "Lookup the original ID and reconcile intent; assign a new ID only to a distinct authorized command, never to evade deduplication."),
    ("COMMAND_ALREADY_TERMINAL",
     "The durable command already has a final result.",
     "Return or inspect the stored result; do not overwrite it or apply the command again."),
    ("COMMAND_NOT_FOUND",
     "The journal has no retained entry for that project and command ID.",
     "Check the project and exact ID, including the archive/recovery context; absence alone is not proof that an uncertain external effect never occurred."),
    ("RETRY_HORIZON_EXPIRED",
     "The retained command is beyond its active retry horizon.",
     "Use authenticated archive lookup for the original result; never execute the expired ID again."),
    ("ARCHIVE_NOT_EXPIRED",
     "The command is still in the active lookup horizon.",
     "Use normal command lookup for the same project and command ID."),
    ("ARCHIVE_RESULT_UNAVAILABLE ARCHIVE_RECEIPT_MISMATCH",
     "The archived result is missing or inconsistent with retained command metadata.",
     "Preserve the journal and reconcile from verified checkpoints/readback; do not fabricate a receipt or replay the expired command."),
    ("INVALID_RECEIPT JOURNAL_RECORD_INVALID JOURNAL_CHECKSUM_MISMATCH JOURNAL_HISTORY_INVALID JOURNAL_TRUNCATED JOURNAL_PATH_UNSAFE JOURNAL_LOCK_UNSAFE",
     "Journal data or its namespace fails integrity validation.",
     "Stop mutation and preserve the original journal for recovery; restore only a verified checkpoint and reconcile effects before resuming."),
    ("JOURNAL_FULL JOURNAL_RECORD_LIMIT PENDING_LIMIT QUEUE_FULL CONNECTION_LIMIT STOP_COMMAND_LIMIT",
     "A bounded persistence, queue or connection budget is exhausted.",
     "Stop adding work, use the reserved control path to inspect/drain, and reclaim only safely retainable capacity; lookup admitted IDs before retrying."),
    ("JOURNAL_LOCKED LEASE_BUSY",
     "Another live owner currently holds the required lock or lease.",
     "Wait with a bounded backoff and inspect ownership; do not steal a live lock or bypass the current fencing epoch."),
    ("JOURNAL_LEGACY_LOCK_RECOVERY_REQUIRED",
     "Legacy lock ownership cannot be safely established.",
     "Preserve lock metadata and verify the original owner through the local recovery procedure before allowing another writer."),
    ("JOURNAL_LOCK_FAILED JOURNAL_UNREADABLE JOURNAL_WRITE_FAILED JOURNAL_DURABILITY_UNCONFIRMED JOURNAL_COMPACT_FAILED",
     "An operating-system journal operation failed.",
     "Preserve staging and diagnose disk/permissions/handles; lookup and reconcile potentially admitted work before restoring service."),
    ("INVALID_LEASE LEASE_TTL_OUT_OF_RANGE STALE_LEASE REVISION_MISMATCH",
     "The lease, fencing epoch or expected revision is invalid or stale.",
     "Read the current revision and obtain a valid lease from the local authority, then reconcile the intended change; lookup an old command ID before replanning."),
    ("REDACTION_REGISTRATION_LIMIT INVALID_REDACTION_REGISTRATION",
     "Secret or host-path registration exceeds the bounded output policy.",
     "Stop the output/admission boundary and correct local registrations; never drop registered secrets to make room silently."),
    ("REDACTION_TEXT_LIMIT REDACTION_TOTAL_TEXT_LIMIT REDACTION_NODE_LIMIT REDACTION_DEPTH_LIMIT REDACTION_ITEM_LIMIT REDACTION_OUTPUT_LIMIT",
     "The output exceeds bounded redaction limits.",
     "Emit a smaller supported diagnostic without the original payload; never bypass redaction to report this failure."),
    ("REDACTION_CYCLE REDACTION_UNSUPPORTED_TYPE REDACTION_KEY_COLLISION REDACTION_ENCODING_FAILED OUTPUT_SINK_FAILED",
     "The output cannot be safely encoded or delivered through the redaction boundary.",
     "Preserve a fixed failure code and repair the supported output shape or sink; do not print raw input, object representations or exception details."),
    ("HEADER_TOO_LARGE HEADER_COUNT_LIMIT INVALID_HEADER INVALID_CONTENT_LENGTH INCOMPLETE_REQUEST",
     "The HTTP frame violates the bounded request format.",
     "Send one complete HTTP/1.1 POST with valid nonduplicated headers and an exact bounded Content-Length."),
    ("UNSUPPORTED_HTTP UNSUPPORTED_HTTP_RESPONSE UNSUPPORTED_ENCODING UNSUPPORTED_CONTENT_TYPE PIPELINING_UNSUPPORTED",
     "The transport feature or response mode is unsupported.",
     "Use a single uncompressed application/json request on the supported typed transport; do not follow redirects or retry uncertain effects automatically."),
    ("HOST_REJECTED ORIGIN_REJECTED",
     "The HTTP Host or browser Origin is outside the allowlist.",
     "Use the configured literal loopback endpoint and explicitly authorized Origin; do not enable wildcard CORS."),
    ("REQUEST_TIMEOUT CONNECTION_LOST_LOOKUP TRANSPORT_DISCONNECTED TRANSPORT_FAILED TRANSPORT_ERROR TRANSPORT_HANDLER_FAILED",
     "The connection failed or the response outcome is uncertain.",
     "Reconnect through authenticated transport and lookup the original command ID before retry/cancel; retain only redacted diagnostics."),
    ("RECOVERY_REQUIRED FIXTURE_RECOVERY_REQUIRED READBACK_FAILED READBACK_TIMEOUT STOP_DURABILITY_UNKNOWN STOP_RECOVERY_REQUIRED HOST_DRAIN_TIMEOUT",
     "Readback, durable completion or owned-work draining is unproven.",
     "Keep mutation stopped, preserve staging/journal, and reconcile the original ID against verified state; do not claim success, cancellation or no effect."),
    ("HOST_ALREADY_STARTED",
     "This host instance has already been started or closed.",
     "Use its existing lifecycle owner or construct a fresh local instance after draining; do not start duplicate writers."),
    ("HOST_STOPPED",
     "Stop has closed work admission for this host.",
     "Use lookup/control to inspect remaining work; reconnecting does not authorize automatic resume."),
    ("QUEUED STOP_DRAINING",
     "A durable intent exists but completion is still pending.",
     "Wait with bounded polling on the original ID; do not interpret pending admission as COMMITTED."),
    ("CANCELED_BEFORE_APPLY",
     "The host canceled this command before its effect.",
     "Retain the original terminal receipt; a new action requires a distinct authorized command."),
    ("CANCEL_TOO_LATE_LOOKUP",
     "Cancellation arrived after the possible effect.",
     "Lookup the original ID and inspect its readback; do not report that the effect was canceled."),
    ("STOPPED READBACK_CONFIRMED",
     "The response reports an observed terminal postcondition.",
     "Check the response status, revision, hash and postconditions and retain its receipt; the code alone is not proof of success."),
    ("NAME_INVALID_TYPE NAME_EMPTY",
     "A display name must be a nonempty Unicode string.",
     "Choose the intended text and validate it before constructing the semantic command."),
    ("NAME_TOO_LONG",
     "The display name exceeds 128 Unicode scalars or 512 UTF-8 bytes.",
     "Choose a shorter name explicitly, then validate it; do not silently truncate existing payloads."),
    ("NAME_INVALID_UNICODE NAME_CONTROL_FORBIDDEN",
     "The display name contains invalid scalars or control/format/line-separator characters.",
     "Choose visible valid Unicode text and validate it before constructing the command; keep rejected text out of diagnostics."),
    ("NAME_NOT_NFC",
     "The display name is not in Unicode NFC form.",
     "Prepare the intended NFC name explicitly before constructing a new command; never normalize an existing payload or digest."),
    ("UNKNOWN_ERROR",
     "The received code is not part of this pinned catalog.",
     "Keep the outcome unproven, compare the pinned client/server contract, and lookup the original command; do not echo the unknown value or expand permissions."),
)


def _build_registry() -> Mapping[str, ErrorGuidance]:
    rows: dict[str, ErrorGuidance] = {}
    for names, meaning, next_action in _GROUPS:
        for code in names.split():
            if code in rows:
                raise ValueError("DUPLICATE_ERROR_REGISTRY_CODE")
            rows[code] = ErrorGuidance(code, meaning, next_action)
    return MappingProxyType(rows)


ERROR_REGISTRY = _build_registry()


def error_guidance(code: str) -> ErrorGuidance:
    """Return fixed guidance without retaining or formatting unknown input."""
    if type(code) is not str or len(code) > 64:
        return ERROR_REGISTRY["UNKNOWN_ERROR"]
    return ERROR_REGISTRY.get(code, ERROR_REGISTRY["UNKNOWN_ERROR"])

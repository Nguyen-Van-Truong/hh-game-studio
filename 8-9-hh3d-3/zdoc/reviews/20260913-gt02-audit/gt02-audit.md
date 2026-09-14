# GT-02 protocol / capability / safety baseline — read-only audit

**Audit id:** `GT02-AUDIT-20260913-01`  
**Date:** 2026-09-13 (Asia/Saigon)  
**Scope:** `8-9-hh3d-3/studio/protocol`, `studio/host/core`,
`studio/tests/protocol` and the GT-02 contract in the tools plan.  
**Role:** independent design and test audit; no source mutation, no plan tick,
no acceptance claim.

## Executive finding

The GT-02 contract is directionally strong and is the right safety boundary for
an agent-facing Godot/Blender host. It explicitly requires canonical JSON,
capability discovery, leases/fencing, revision checks, bounded persistence,
path protection, loopback authentication and rejection before mutation. At the
time of this audit the three allowed implementation directories were absent or
empty, so there is no implementation evidence to accept yet. GT-02 must remain
`IN_PROGRESS` until a source freeze, executable tests and two critics cover the
same closure hash.

The highest risks are subtle interoperability and fail-open behaviours:

* different runtimes canonicalize numbers, Unicode and duplicate JSON keys
  differently;
* a valid lease or revision can become invalid between path validation and the
  actual open/replace operation;
* a bounded journal can evict a command result before a delayed retry and then
  execute a mutation twice;
* capability metadata can advertise an operation that is not actually
  authorized by the active lease/scope;
* a timeout/`UNKNOWN` response can be retried without first looking up the
  original command;
* Windows reparse points, hard links, ADS, UNC/device paths and case aliases
  defeat a `realpath()`-only check;
* malformed output, parser errors or tool output can be mistaken for an ACK or
  become a prompt-injection privilege escalation.

## Contract audit

The following requirements are transcribed from section 2.2 and the GT-02
block of `8-9-godot-blender-agent-studio-plan.txt` and converted into checks.
The requirement is considered implemented only when the check has a stable test
id, observed output and an artifact bound to the frozen source hash.

| ID | Requirement | Required observable | Priority | Initial state |
|---|---|---|---|---|
| P-01 | UTF-8 JSON, duplicate keys/invalid Unicode/NaN/Infinity rejected | parser returns stable error code before dispatch | P0 | PENDING implementation |
| P-02 | Canonical digest (JCS/RFC 8785 or locked equivalent) | Python/Node/Godot golden vectors produce identical bytes/hash | P0 | PENDING implementation |
| P-03 | Safe integer boundary | values outside IEEE-754 safe range are decimal strings; no rounding | P0 | PENDING implementation |
| P-04 | Name NFC is domain validation, not payload-hash normalization | decomposed/composed names hash as sent; NFC policy tested separately | P1 | PENDING implementation |
| P-05 | Envelope contains command/project/schema/operation/lease/fence/revision/target/payload/hash/deadline | schema validator rejects missing/unknown/wrong types | P0 | PENDING implementation |
| P-06 | Response distinguishes pending, committed, rejected, unknown, canceled | pending cannot be interpreted as committed | P0 | PENDING implementation |
| P-07 | Capability discovery is explicit and scoped | metadata has protocol/schema/build/project/capabilities/read/write scopes/limits | P0 | PENDING implementation |
| P-08 | Unsupported version/capability fails closed | no operation or side effect on unsupported request | P0 | PENDING implementation |
| P-09 | Lease expiry/fencing and expected revision are checked before apply | stale lease/fence/revision produces deterministic rejection | P0 | PENDING implementation |
| P-10 | Dedupe key is `(project_id, command_id)` and digest includes operation/target/payload/schema | same id+same digest returns original result; same id+different digest conflicts | P0 | PENDING implementation |
| P-11 | Lease changes do not turn an old command id into a new command | lookup is independent of current lease | P0 | PENDING implementation |
| P-12 | Journal/result/tombstone retention spans retry horizon | terminal id cannot be re-executed after in-memory eviction | P0 | PENDING implementation |
| P-13 | Journal and queue are bounded by bytes, records, depth and deadline | full journal rejects before mutation; no unbounded RAM growth | P0 | PENDING implementation |
| P-14 | Path is project-root confined and race safe | reparse/symlink/junction/hardlink/ADS/device/UNC/case alias tests fail closed | P0 | PENDING implementation |
| P-15 | Windows safe-open uses handle identity or returns `UNSUPPORTED_SAFE_OPEN_WINDOWS` | CreateFileW/open-reparse-point and final identity checked | P0 | PENDING implementation |
| P-16 | Loopback is authenticated for reads and writes | wrong/missing token and bad project scope are rejected; no wildcard Origin | P0 | PENDING implementation |
| P-17 | No remote arbitrary Python/GDScript/shell eval | no operation maps to shell/node-call/execute-code | P0 | PENDING implementation |
| P-18 | Secrets never appear in args/logs/screenshots/errors | redaction test covers parser, argv, env dump and tool output | P0 | PENDING implementation |
| P-19 | Deadline/Stop semantics preserve `UNKNOWN` and terminate only owned tree | timeout/cancel leaves staged diagnostic; killed process is not PASS | P0 | PENDING implementation |
| P-20 | Prompt/tool output is data, not authorization | hostile strings cannot expand capability or scope | P0 | PENDING implementation |
| P-21 | Cross-language vectors cover Python, Node and Godot | one checked-in vector set and independent consumers | P0 | PENDING implementation |
| P-22 | Error codes are finite, documented and actionable | every rejection has stable code and remediation, no exception text leak | P1 | PENDING implementation |

## Machine-checkable checklist

This block is intentionally suitable for a verifier. `status` must not be
changed to `PASS` from a code inspection alone; it requires a test artifact and
the same `source_closure_sha256` as the candidate package.

```json
{
  "schema": "hh-gt02-audit-checklist-v1",
  "audit_id": "GT02-AUDIT-20260913-01",
  "scope": ["studio/protocol", "studio/host/core", "studio/tests/protocol"],
  "source_closure_sha256": null,
  "status": "AUDIT_PENDING_IMPLEMENTATION",
  "checks": [
    {"id":"P-01","test":"PROTO-JSON-001","severity":"P0","status":"PENDING","evidence":null},
    {"id":"P-02","test":"PROTO-CANON-001","severity":"P0","status":"PENDING","evidence":null},
    {"id":"P-03","test":"PROTO-NUM-001","severity":"P0","status":"PENDING","evidence":null},
    {"id":"P-05","test":"PROTO-ENVELOPE-001","severity":"P0","status":"PENDING","evidence":null},
    {"id":"P-06","test":"PROTO-STATUS-001","severity":"P0","status":"PENDING","evidence":null},
    {"id":"P-07","test":"PROTO-CAP-001","severity":"P0","status":"PENDING","evidence":null},
    {"id":"P-08","test":"PROTO-UNSUPPORTED-001","severity":"P0","status":"PENDING","evidence":null},
    {"id":"P-09","test":"PROTO-FENCE-001","severity":"P0","status":"PENDING","evidence":null},
    {"id":"P-10","test":"PROTO-DEDUPE-001","severity":"P0","status":"PENDING","evidence":null},
    {"id":"P-11","test":"PROTO-DEDUPE-002","severity":"P0","status":"PENDING","evidence":null},
    {"id":"P-12","test":"PROTO-TOMBSTONE-001","severity":"P0","status":"PENDING","evidence":null},
    {"id":"P-13","test":"PROTO-LIMIT-001","severity":"P0","status":"PENDING","evidence":null},
    {"id":"P-14","test":"PROTO-PATH-FUZZ-001","severity":"P0","status":"PENDING","evidence":null},
    {"id":"P-15","test":"PROTO-WIN-SAFEOPEN-001","severity":"P0","status":"PENDING","evidence":null},
    {"id":"P-16","test":"PROTO-AUTH-001","severity":"P0","status":"PENDING","evidence":null},
    {"id":"P-17","test":"PROTO-NO-EXEC-001","severity":"P0","status":"PENDING","evidence":null},
    {"id":"P-18","test":"PROTO-REDACT-001","severity":"P0","status":"PENDING","evidence":null},
    {"id":"P-19","test":"PROTO-CANCEL-001","severity":"P0","status":"PENDING","evidence":null},
    {"id":"P-20","test":"PROTO-INJECTION-001","severity":"P0","status":"PENDING","evidence":null},
    {"id":"P-21","test":"PROTO-GOLDEN-001","severity":"P0","status":"PENDING","evidence":null}
  ],
  "promotion_rule": "all P0 checks PASS on one frozen closure, no unexplained warning/error/secret, two independent critics TICK=yes"
}
```

## Required test vectors and edge cases

### Canonical JSON and envelope

1. Parse bytes that begin with UTF-8 BOM, UTF-16, invalid UTF-8, an unpaired
   surrogate, duplicate object names, trailing data, comments and deeply nested
   arrays. Every case must reject with a stable code and zero journal entry.
2. Reject `NaN`, `Infinity`, `-Infinity`, exponent overflow and negative zero if
   the locked canonical profile disallows it. Verify shortest-number rendering
   and `1`, `1.0`, `1e0` equivalence only where JCS defines equivalence.
3. Test integer `2^53-1`, `2^53`, `2^53+1`, and larger values through Python,
   Node and Godot. Values beyond safe range must be decimal strings in the
   envelope and digest.
4. Hash the same object with reordered keys, escaped versus literal Unicode,
   composed/decomposed names and different whitespace. Key order/whitespace
   should canonicalize; payload Unicode bytes must not be silently normalized.
5. Validate every envelope field, reject unknown fields unless the schema
   explicitly permits an extension namespace, and cap target/payload depth,
   string length, array/object count and total bytes.

### Capability, lease and revision

1. Discovery must be bound to a session/project and include a schema digest,
   server/build identity, read/write scope and numeric limits. Mutating requests
   must be authorized against current capabilities again at dispatch time.
2. Exercise expired lease, wrong owner, stale fencing epoch, expected revision
   mismatch, project mismatch, unknown operation and unsupported schema. Assert
   no file/journal/revision change for each.
3. Race two commands at one revision. Exactly one may commit; the other returns
   a conflict with current revision and no partial output. A late result from an
   old fence can never overwrite a newer commit.
4. Return `ACCEPTED_PENDING` only after durable intent is recorded. Simulate
   response loss after commit and require lookup to return the original receipt,
   not a second mutation.

### Journal, dedupe and limits

1. Fill record and byte limits, queue depth and per-command payload limits.
   Full conditions must reject before apply and must not allocate unbounded
   memory while constructing the error.
2. Restart after each journal phase (`PREPARED`, `VALIDATED`, `ACTIVATING`,
   `COMMITTED`) and replay. Terminal tombstones must survive RAM eviction and
   span the configured retry horizon; expired IDs go to archive lookup and are
   never executed again.
3. Retry same `(project_id, command_id, digest)` repeatedly, including after
   compaction and process restart: one side effect and one receipt only. Retry
   same id with a changed payload/operation/schema: deterministic conflict.
4. Crash while writing a result, truncate a record, reorder lines and alter a
   checksum. Recovery must fail closed or quarantine the journal; it must not
   invent `COMMITTED`.

### Path and transport security

1. Fuzz `../`, `..\\`, percent/double encoding, mixed separators, NUL, trailing
   dots/spaces, case aliases, UNC, device names, ADS (`file:stream`), junctions,
   symlinks and hard links. Include link swap between validation and open and
   between open and replace.
2. Windows implementation must use a no-follow handle (`CreateFileW` with
   `FILE_FLAG_OPEN_REPARSE_POINT`) and compare final handle identity/path. If
   that primitive is unavailable, return the fixed `UNSUPPORTED_SAFE_OPEN_WINDOWS`
   code. A `Path.resolve()`/`realpath()` check alone is insufficient.
3. Test loopback HTTP/WebSocket host/origin allowlists, absent/expired/rotated
   token, wrong project token, CSRF, DNS rebinding and oversized compressed
   frames. Authenticate read and write paths, apply caps before expensive parse,
   and never use wildcard CORS. Stdio needs session/OS binding rather than HTTP
   Origin headers.
4. Put secrets in payload, environment, argv, parser errors and hostile tool
   output. Evidence, logs and screenshots must contain deterministic redaction,
   never the original token.

### Prompt injection and no-effect rejection

1. Put strings such as `execute shell`, `open_lane`, `grant write`, JSON-looking
   capability objects and fake ACKs in payload/tool output/source text. They
   must remain data and cannot change operation, scope, lease or limits.
2. Ensure no generic operation dispatches to Python/GDScript/shell/node-call or
   downloads a script. Open lane remains `UNSUPPORTED_OPEN_LANE` by default.
3. For every rejected request compare a before/after snapshot of source files,
   revision, journal bytes, queue counters and external process list. All must
   be unchanged except an allowed rejection audit record.

## Integration and implementation risks

* **GT-03/GT-04 envelope coupling:** adapters must consume the frozen protocol
  package read-only. Changing a field or canonicalization rule later requires a
  schema version, migration vectors and a new closure; never silently adapt.
* **GT-07 recovery overlap:** GT-02 must define durable receipt semantics and
  fencing primitives without claiming the complete multi-agent scheduler. Mark
  fairness, crash orchestration and publish reconciliation as deferred GT-07
  gates, but keep the primitives testable now.
* **GT-09 conformance:** capability matrices must identify the exact client,
  model, host and build. A README or a single mock client is not conformance.
* **Cross-language drift:** canonical JSON, error codes and safe integer rules
  need golden vectors consumed by every runtime. Avoid language-native map
  iteration and floating-point serialization.
* **Windows versus Linux:** do not report Linux `openat2` coverage as Windows
  safe-open coverage. Unsupported OS primitives must produce `UNSUPPORTED_*` and
  disable mutation.
* **Resource exhaustion:** limits must cover decompressed size, nesting, object
  count, journal bytes, retained tombstones, process output, timeout and disk
  space. Check limits before authentication-dependent expensive work where
  feasible, but do not expose sensitive existence information.
* **Evidence contamination:** use a disposable project/user-data root and one
  writer. Hash source closure, tests, vectors and report; redact machine paths
  before packaging. A passing test run from a dirty tree is not acceptance.

## Recommended implementation order

1. Lock the profile and numeric limits in a versioned schema plus cross-language
   golden vectors; add a strict parser that rejects duplicate keys and invalid
   numbers before any dispatch.
2. Implement pure envelope/capability validation and deterministic error codes.
   Prove no-effect rejection with snapshot tests.
3. Implement command identity/digest, durable receipt/tombstone and bounded
   journal. Add crash/response-loss/retry tests before exposing mutation hooks.
4. Implement lease/fencing/revision checks and a mock typed operation with an
   explicit postcondition. Keep operation catalog separate from generic eval.
5. Implement Windows/Linux safe-open behind capability probes. Return fixed
   `UNSUPPORTED_SAFE_OPEN_*` when primitives cannot be proved; never downgrade
   to realpath-only.
6. Add loopback session authentication, token rotation/revocation hooks,
   frame/queue caps and redaction. Exercise hostile output and prompt injection.
7. Freeze closure, run all tests on a clean disposable root, package logs/hashes,
   and dispatch two independent read-only critics. Only the coordinator may
   promote GT-02 after matching `TICK=yes` records.

## Sources consulted

* RFC 8785, *JSON Canonicalization Scheme* — deterministic property sorting and
  hashable JSON representation: https://www.rfc-editor.org/rfc/rfc8785
* RFC 8259, *The JavaScript Object Notation (JSON) Data Interchange Format* —
  interoperability and Unicode/number constraints:
  https://datatracker.ietf.org/doc/html/rfc8259
* OWASP, *Path Traversal* — encoded traversal and Windows separator cases:
  https://owasp.org/www-community/attacks/Path_Traversal
* Godot editor/plugin and self-contained data-path documentation was already
  consulted for GT-01; GT-02 must keep protocol tests independent of editor UI.

## Audit disposition

`AUDIT_ONLY / NO_TICK / NO_ACCEPTANCE`. The contract should remain unchanged in
scope, but the implementation must satisfy every P0 row above with executable,
closure-bound evidence. Any worker result claiming PASS without the vectors,
no-effect snapshots, crash/retry tests and platform-specific safe-open proof is
insufficient and must be returned for revision.

## Spot-check of the in-progress worker tree (2026-09-13)

This section records observations made after the initial empty-tree audit. It is
not an acceptance review and must be rerun after workers finish:

* `studio/protocol/core.py` and `studio/host/core/limits.py` currently define
  different schema constants (`hh-studio-0.1` versus `studio.command.v1`) and
  different target representations (object `{path|stable_id}` versus a target
  string). They also expose two canonicalizers. A single cross-module fixture
  must be selected before adapter work; otherwise Python/Node/Godot clients can
  compute different digests while each local test passes.
* Both canonicalizers call Python `json.dumps(sort_keys=True)`. That is not
  automatically RFC 8785 JCS: key ordering (UTF-16 code units), negative zero,
  exponent rendering and integer handling need an explicit locked profile and
  golden vectors. Do not label this PASS from key-order tests alone.
* `host.core.limits.parse_json_utf8` caps bytes but has no depth, object-member,
  array-length or string-length limits. Add those limits before recursive walk
  and test deeply nested and wide inputs; otherwise a bounded envelope can still
  cause CPU/RAM exhaustion.
* `protocol.Request.from_dict` does not reject unknown keys and ignores a
  caller-supplied `digest` field. Define extension handling and reject/record
  unknown fields before dispatch. `validate_envelope` likewise accepts extra
  keys and currently does not bind lease/fencing/revision fields.
* `SafePathResolver` is intentionally fail-closed by default, but the
  `safe_open_supported=True` path still needs platform handle identity/no-follow
  evidence and a race test. `resolve()` is lexical/read-only validation, not a
  safe write-open primitive.
* Existing tests cover basic duplicate/UTF-8/non-finite/size/path cases only;
  they do not exercise journal durability, dedupe after response loss, lease
  fencing races, loopback token rotation, hostile tool output, no-effect
  snapshots, or cross-language vectors. These omissions map directly to
  `PROTO-TOMBSTONE-001`, `PROTO-FENCE-001`, `PROTO-AUTH-001`,
  `PROTO-INJECTION-001` and `PROTO-GOLDEN-001` above.

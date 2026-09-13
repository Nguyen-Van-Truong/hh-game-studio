# GT-02 preparation audit (read-only)

**Run:** 20260914-r14-gt02  
**Scope:** `8-9-hh3d-3/studio`  
**Plan state at review:** `GT-01=IN_PROGRESS`, `GT-02=PLANNED`, `PLAN_REVISION=S21`  
**Role:** preparation/audit only; no source mutation, no checkbox tick, no external installation.

## Decision

GT-02 must remain **PLANNED** until GT-01 has one frozen source closure, an official
runtime remint, complete evidence, and two independent acceptance critics. The plan's
GT-02 contract is directionally sound and intentionally narrower than a generic
"all Godot buttons" API. The first implementation slice should be a local JSON/CLI
contract library and a fake in-memory host; it should prove rejection and retry
semantics before any Godot EditorPlugin or MCP adapter is connected.

The external MCP repositories remain compatibility candidates only. They must wrap
the typed contract and cannot become the authority for leases, path safety, journal,
postconditions, or capability enforcement.

## Current implementation observations

The existing `studio/build/bootstrap` code already has useful GT-01 safeguards:

- duplicate-key rejection and bounded JSON reads in the archive/runner paths;
- cooperative install lease, process identity and CAS rollback checks;
- source/binary hash binding, path-ancestor checks, warning/error scanning and
  host-captured process evidence.

No `studio/protocol/`, `studio/contracts/`, or `studio/host/` GT-02 implementation was
present in the read-only inventory. Therefore the following remain design requirements,
not demonstrated capabilities: canonical wire encoding, capability negotiation,
command dedupe/tombstones, protocol-level lease/fencing, session token enforcement,
safe-open primitives, and durable result lookup after a lost response.

GT-01 helpers must not be treated as proof of GT-02. In particular, a bootstrap lock
is not a multi-agent command lease, and a toolchain state token is not a command
idempotency key.

## Minimal first slice (after GT-01 acceptance)

Implement only these files/surfaces in a dedicated GT-02 lease:

1. `studio/protocol/schema.json` (or equivalent versioned schemas) for request,
   response, capability profile, lease, error codes and limits.
2. `studio/protocol/canonical.py` (plus golden vectors) implementing strict UTF-8
   JSON parsing, duplicate-key rejection, finite-number checks, bounded depth/size,
   and the chosen canonicalization profile. Do not silently Unicode-normalize the
   bytes used by `payload_hash`; NFC validation belongs to domain names.
3. `studio/host/journal.py` with bounded durable records, result lookup,
   `(project_id, command_id)` dedupe, payload/schema digest binding, terminal
   tombstones and retry-horizon policy. It must survive a process restart without
   loading all history into RAM.
4. `studio/host/capabilities.py` with explicit read/write scopes, limits and
   `UNSUPPORTED` responses. Capabilities are enforced at the host boundary, not only
   advertised in prompts.
5. A fake host/CLI test harness under `studio/tests/protocol/` that exercises the
   contract without Godot or Blender. This is preparation, not an acceptance run.

Do not add editor mutation, Blender `bpy`, arbitrary code execution, shell dispatch,
network fetch, MCP transport, or multi-agent recovery in this first slice. Those
belong to GT-03/GT-04/GT-07 after the contract is frozen.

## Contract checklist

### Envelope and canonical bytes

- [ ] `protocol_version`, `schema_version`, server/build identity, `project_id`,
  capabilities and limits are returned before dispatch.
- [ ] Request fields include `command_id`, operation, target stable ID/path,
  `lease_id` plus `fencing_epoch`, `expected_revision`, payload, payload digest and
  deadline.
- [ ] Response distinguishes `ACCEPTED_PENDING`, `COMMITTED`, `REJECTED`, `UNKNOWN`
  and `CANCELED`; `ACCEPTED_PENDING` never means mutation succeeded.
- [ ] Duplicate JSON keys, invalid UTF-8, NaN/Infinity, excessive depth/size and
  unsafe integer representations are rejected deterministically.
- [ ] JCS (RFC 8785) or a precisely specified equivalent is selected and locked with
  Python/Node/Godot golden vectors. Numbers outside the safe integer range use
  decimal strings.
- [ ] Digest covers operation, target, payload and schema; changing a lease does
  not turn an old command ID into a new command.

Reference: [RFC 8785 JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html).

### Idempotency and journal

- [ ] Same `(project_id, command_id, digest)` returns the original terminal result;
  same ID with a different digest returns a stable conflict code.
- [ ] A timeout or lost response triggers lookup before retry. The host never assumes
  that a deadline means the mutation did not commit.
- [ ] Journal retention covers the retry horizon; terminal tombstones are not removed
  early enough to execute an old ID again.
- [ ] Crash between prepare/apply/publish yields `UNKNOWN` or a recoverable result,
  never an ACK without a postcondition.
- [ ] Journal records are bounded, redacted and independently integrity-checked;
  secrets, tokens, private chat and host paths are excluded.

### Capability profile and safety boundary

- [ ] Capabilities are typed (`read_only`, `mutating`, `destructive`, `runtime`),
  scoped per project/session and include explicit operation/size/rate limits.
- [ ] Missing capability returns `UNSUPPORTED`; the client cannot escalate by
  changing a prompt, operation name or MCP metadata.
- [ ] Open/eval lane remains `UNSUPPORTED_OPEN_LANE` by default and requires the
  later ADR, isolated worktree/user-data, no secrets, network denial, process/job
  limits and a separate evidence class.
- [ ] MCP is an adapter over this host contract. `execute_code`, `node_call`, shell,
  arbitrary Python/GDScript and destructive tools are denied in the compatibility
  spike.

### Lease, fencing and revision

- [ ] Lease acquisition is project-scoped, owner-bound, expiring and monotonic in
  `fencing_epoch`; every mutation checks the epoch at apply and publish time.
- [ ] Revision preconditions are explicit. A stale writer gets a conflict and cannot
  overwrite a newer source revision.
- [ ] Renewal/release/recovery have bounded timeouts and no ambiguous success. A
  crashed owner leaves a journal-visible state for recovery rather than silent reuse.
- [ ] The GT-01 cooperative install lock is not reused as the GT-02 command lease
  without a separate schema and tests.

### Path and transport boundary

- [ ] Canonical project-root allowlist rejects traversal, symlink/junction/reparse,
  hardlink, ADS/device/UNC and case-alias escapes according to platform.
- [ ] Validate/open/replace uses a race-resistant OS primitive. If unavailable,
  return `UNSUPPORTED_SAFE_OPEN_WINDOWS` or `UNSUPPORTED_SAFE_OPEN_LINUX` rather
  than falling back to `realpath` alone.
- [ ] Loopback HTTP/WebSocket (if later selected) checks Host/Origin, session token,
  frame/decompression/queue caps and redirect/IP policy. Stdio uses OS/session
  binding and does not inherit HTTP Origin assumptions.
- [ ] Error, argv, environment and screenshot redaction tests cover malformed
  tokens and parser failures.

## Test matrix for the first slice

| ID | Scenario | Expected result |
|---|---|---|
| P-01 | Valid request with fixed golden vector | deterministic digest and response |
| P-02 | Duplicate key / invalid UTF-8 / NaN / deep or oversized JSON | reject before dispatch |
| P-03 | Same command ID and digest twice | one apply, same result lookup |
| P-04 | Same command ID with changed payload/schema | conflict, no second apply |
| P-05 | Lost response after commit | lookup returns committed postcondition |
| P-06 | Restart with journal present | result/tombstone remains queryable |
| P-07 | Expired command or lease | stable rejection; no mutation |
| P-08 | Stale fencing epoch/revision | conflict; newer writer preserved |
| P-09 | Missing capability or open-lane request | `UNSUPPORTED`; no fallback execution |
| P-10 | Traversal/symlink/reparse/UNC/ADS target | reject before opening |
| P-11 | Oversized payload, queue flood, duplicate retry flood | bounded resource use and fair rejection |
| P-12 | Prompt/asset/log contains hostile instruction | treated as data; no scope/model/token change |

Acceptance evidence for this slice must include source hash, schema digest, test
invocation, raw exit, redacted logs and expected/observed postconditions. It cannot
unlock GT-02 until GT-01 is accepted and the coordinator records the dependency.

## External MCP adapter boundary

The two candidate repositories may be benchmarked later against the same fake host
and then the real fixture:

- [NPGameDev Godot MCP Toolkit](https://github.com/NPGameDev/godot-mcp-toolkit)
- [hybridindie godot-mcp](https://github.com/hybridindie/godot-mcp)

Repository README counts, stars, commit totals and self-reported CI are not proof.
The bake-off must pin exact commits and record transport, reconnect behavior,
capability filtering, timeout/queue behavior, path handling, lease propagation,
postcondition/readback, and license notices. An adapter fails closed when a required
host capability is absent. Blender export remains a separate Blender-to-GLB job;
MCP cannot claim that export is safe merely because a Godot node operation succeeded.

## Risks and follow-up

- Canonicalization differences across Python, Node and Godot can invalidate hashes;
  golden vectors are mandatory before any consumer is written.
- A durable journal can become a memory or disk DoS; enforce record, queue, retention
  and per-project/session limits and test restart/compaction.
- Cooperative leases do not defend against hostile processes. GT-02 should expose
  unsupported safe-open capability until platform primitives are implemented.
- A read-only MCP label is insufficient if the bridge can still execute arbitrary
  code or write files outside the project root.
- Android/device and Blender threading concerns stay in GT-04/GT-08; do not pull
  them into GT-02's protocol implementation prematurely.

## Coordinator handoff

No plan checkbox was changed. No GT-02 source was changed. Recommended next action is
to finish and freeze GT-01, then dispatch the minimal protocol/journal slice under a
new base hash and independent file leases. After its tests pass, run the adapter
bake-off as a compatibility experiment; do not promote either external repository to
core authority without the same postcondition/hash/lease/critic gates.

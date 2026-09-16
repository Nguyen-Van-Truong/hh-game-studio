# Protected immutable bundle files and internal selector

AUTHORITY=0. Internal GT-03 storage, not public save, engine validation,
authorization, journal commitment or GT-03 acceptance. Accepted GT-02 code and
the historical `bundle_staging.py` remain unchanged.

`ProtectedBundleStore(exact ProtectedFileRoot)` takes exclusive use and close
ownership only after successful constructor validation. The caller must stop
using the native root at transfer. The future lifecycle is journal → bundle
store → native files, with one close owner at each edge. Do not share a live
journal's root or construct this around an inert fixture consumer.

One store RLock serializes operations; lock order is store → native root. A
marker on the exact native object prevents a second wrapper, including one
loaded from another module copy. Constructor failure leaves the root owned by
the caller. No arbitrary paths, subclass/duck-typed native owners, callbacks,
native-core changes, inert-consumer marker or write rearm are accepted.
Same-process trusted code can still violate ownership deliberately; Python
immutability is not isolation against malicious host code.

## API and preparation

The exported `bundle_codec` is exactly
`fixture_profile.staging.bundle_codec`, loaded through resolved sibling paths
and exact source bytes. Construct bundles with that class. Independent codec
lookalike classes are rejected; no worker chooses a module or source path.

- `prepare(command_id, bundle) -> ProtectedBundleIntent` performs native reads,
  quota admission and in-memory reservation, with **no file writes**. The
  frozen registered intent contains `command_id`, `project_revision`,
  `root_identity` and `names`, a tuple of eleven `(logical_path, obj-<32hex>)`
  pairs in codec order followed by `('@manifest', obj-<32hex>)`.
- These names exist before the caller persists journal PREPARED. The caller
  must durably record intent before invoking `stage`; this API itself owns no
  journal and does not make preparation durable.
- One unfinished preparation is allowed. Same command and identical bundle
  returns its original intent; changed bytes/revision under that ID conflict.
  Another pending command rejects without writes. At most 64 attempts,
  including canceled tombstones, are retained. No retry or freeing reserved
  names is inferred from process exit.
- `stage(intent) -> ProtectedBundleReceipt` accepts only the original intent
  registered by this store. An equal copy or another owner's intent fails.
- `readback(receipt) -> CompleteFixtureBundle` reads and compares all actual
  retained versions/bytes and native inventory. It accepts only the exact
  original registered receipt. Later batches registered by this owner remain
  compatible with earlier receipts.
- `lookup(command_id, project_revision=None)` checks native ownership and
  inventory, then returns the original receipt or `None` (absent/prepared).
  It is internal historical receipt lookup, not new engine or public authority.
- `snapshot()` returns frozen `ProtectedBundleAttempt` diagnostics containing
  planned names, reservation, attempted-write count and all returned versions.
  It remains usable when held/closed and does not claim live native health.
- `root`, `root_identity`, `readonly` are readonly identity facts. They expose
  no native owner handle or write/rearm operation.
- `cancel_unused_prepare(intent)` accepts the original registered intent only
  while zero native writes were attempted and no versions/receipt exist. It
  rechecks complete inventory and absence of every planned name, then returns
  a frozen registered `ProtectedPrepareCancellation`. Duplicate cancellation
  returns that object; reserved count/bytes become zero. ID, payload and names
  remain tombstoned. Same-ID prepare or stage rejects; new IDs may prepare.
  Cancellation deletes no files and cannot clear an uncertain/held owner.

## Actual namespace durability

All eleven files and the separate manifest are immutable flat `obj-<uuid>`
names. They are created through the unchanged native `create_new`, never
replaced. The manifest is created last. Each returned FileVersion is retained
before readback; full-set decode and native inventory comparison follow.
The store then calls actual `confirm_barrier(manifest_name, manifest_version)`
and re-reads every content file and the manifest plus complete native inventory
before registering a receipt. This is the accepted native file/directory
barrier; it does not depend on the earlier blob store's missing generic barrier.

Receipt status is `DURABLE_BUNDLE_BYTES_READ_BACK`. It records
`namespace_durability_verified=true` only on this successful owner path;
`public_ack=false` and `engine_effects_verified=false` remain fixed. The flag
describes historical protected byte/barrier observations within the accepted
Windows NTFS assumptions, not protection from later privileged host mutation.
An invented dataclass flag has no authority without owner registration/readback.

The constructor's baseline inventory may contain only `.writer`, generated
object names and optional `active.json` (at most 16 KiB). Existing orphans count.
Every file version/hash comes from checked native handles, not directory-entry
metadata. Subsequent inventory must equal that baseline plus this owner's
registered returned versions and the separately tracked mutable `active.json`
FileVersion; added, removed or changed names/bytes hold it. A successful
store-owned selector transition updates only that tracked slot, so older
immutable bundle receipts remain readable. There is no second selector writer.
Constructor inventory admission alone does not parse or prove an existing
selector; `inspect_selection()` supplies that explicit complete check.

Before preparation, reserve all twelve files and actual bytes **plus two file
slots and 32 KiB** for conservative selector replacement headroom, even if an
old `active.json` already exists. Native limits remain 64 files, 8 MiB total
and 1 MiB per file. No quota reclamation/GC or deletion is supplied. Known
capacity exhaustion is an ordinary rejection, retaining existing receipts.

## Internal selector API and fixed bytes

`inspect_selection() -> ProtectedSelectionSnapshot | None` reads the actual
tracked selector, parses its strict canonical schema, verifies all twelve
referenced immutable files and re-reads the selector. Absence returns `None`,
meaning UNSELECTED. The frozen issuer-registered snapshot exposes `.source_bytes`
and `.version`; `.selection` and `.descriptor` return fresh detached JSON.
An observation from readonly reopen grants no mutation authority.

`prepare_selection(bundle_receipt, selection, *, expected)` performs reads and
returns a frozen registered `ProtectedSelectionIntent` without file writes.
`selection` is exactly `{generation: safe_nonnegative_integer, identity:
"sha256:<64hex>"}`. `expected=None` means explicit initialization, requires
native selector absence, and requires generation 0. Otherwise `expected` must
be the exact current registered snapshot and generation must increase by one.
The intent exposes command/project/root identity, `.source_bytes`, `.expected`
and `public_ack=false`, before the caller journals its effect intent.
Equal copies, other owners, stale snapshots and changed same-ID payloads reject.
One pending selector intent and at most 64 selector attempts are retained.

The exact six-key JSON schema, canonical UTF-8 and at most 16 KiB, is:

```text
{schema: "hh-godot-active-selection-1", command_id,
 parent_selection: null | {generation, identity}, selection: {generation, identity},
 descriptor_sha256: plain_64hex, descriptor: existing_complete_bundle_descriptor}
```

`descriptor_sha256` hashes the descriptor's shared canonical bytes. The
descriptor already binds native root identity, project revision, eleven files
and manifest. Parent is null only at generation 0. Normal transitions carry
the exact expected snapshot's selection. This storage layer validates identity
syntax and generation, **not** semantic selection-identity derivation, session,
lease, Stop, profile eligibility or engine observations. The sole trusted
journal/consumer owner must enforce those immediately before `select` under
its lifecycle lock. There are no imported journal types or caller callbacks.

`select(intent) -> ProtectedSelectionReceipt` counts the effect attempt before
native `create_new('active.json', bytes)` or
`atomic_replace('active.json', bytes, expected=exact_old_FileVersion)`. It checks
the returned version and bytes, performs actual `confirm_barrier`, re-reads
every referenced file/manifest and exact inventory, then re-reads the selector.
Only afterward are the new tracked slot and registered receipt published.
The receipt exposes `.snapshot` for the next expected token, forwarding
`.source_bytes`, `.version`, `.selection`, `.descriptor`, and command/project
identity. Its status is `DURABLE_SELECTION_BYTES_READ_BACK`; namespace durability
is true while `public_ack` and `engine_effects_verified` remain false.

Duplicate `select` on a completed registered intent returns its original
historical receipt after current selection/bundle checks, without another CAS.
`lookup_selection(command_id)` does the same lookup; absence/prepared returns
None. Neither claims the historical receipt is still current: call
`inspect_selection()` for current facts. `selection_snapshot()` returns bounded
in-memory diagnostics including source bytes, expected/returned FileVersions,
attempt count and status, even when held/closed. It grants no resume permission.

Fresh CONFIG metadata is not selected-root proof. The caller must durably log
explicit bootstrap preparation and selector intent before the first native
create, and verify the actual receipt before accepting an initial baseline.
Later engine readback and journal COMMITTED remain separate required work.
Reopen stays readonly, accepts strict descriptors/selector observations only,
and cannot adopt intents/receipts or rearm native writes.

## Descriptors and readonly reopen

`descriptor(receipt)` performs registered native readback and returns a fresh
detached JSON value with exactly:

```text
{root_identity: {volume: decimal_string, file_id: 32hex},
 project_revision: "sha256:...",
 files: {each_of_eleven_logical_paths:
   {name: "obj-...", volume: decimal_string, file_id: 32hex,
    size_bytes: integer, sha256: 64hex}},
 manifest: {name, volume, file_id, size_bytes, sha256}}
```

The manifest is not an entry in `files`. All twelve native names/file IDs are
unique; sizes and hashes must match the exact codec caps and actual bytes.
Malformed/foreign descriptors reject before native effects, without changing a
healthy owner. Native mismatch/read failure holds it.

The trusted caller may reopen the exact registered root through
`ProtectedFileRoot.reopen_readonly(root, FileIdentity)` and transfer it to a new
store. `read_descriptor(value)` checks strict descriptor shape, native root and
file identities, complete byte hashes, canonical manifest/project revision and
unchanged complete inventory. It returns a decoded bundle, **not a receipt**.
It neither adopts a command nor registers historical intents/receipts, flushes
a new publication barrier, resumes work, enables writes or clears readonly.
Descriptor provenance must come from the future trusted journal/custody layer;
this storage API does not authenticate arbitrary caller metadata.

## Uncertainty and test scope

Each native write attempt is counted before the call. A call that creates a
file but loses its return still leaves its planned name and full reservation
owned. Any stage/barrier/readback failure holds the store, records UNKNOWN and
retains all returned versions; there is no second write attempt or automatic
cleanup. Close failure keeps the same exact cleanup owner/marker and marks
retained attempts UNKNOWN; close can be retried, no mutation can resume.
Readonly replay does not infer orphan adoption or new write authority.
Selector failures after effect-start likewise retain UNKNOWN and the cleanup
owner; no retry, rollback or inferred success from a newer selector is allowed.
Native verification failure before selector write also holds the owner but
reports `outcome_unknown=false` for that selector effect when its count is zero.
Ordinary malformed/copied/stale supplied values reject without native writes.

Focused tests use actual fresh Windows protected roots and synthetic inert
bundles. They exercise preparation, exact manifests/barriers/reopen, quota and
selector headroom, identity/copy rejection, response dedupe, concurrency and
faults after native writes/barrier/readback/close. No Godot, Docker, eligible
script claim, public transport or durable coordinator is exercised here.
`test_protected_selector.py` additionally covers actual initialization A -> CAS
B, old A readback, readonly reopen, historical duplicates, full-schema checks,
unreturned selector effects, barrier/bundle faults and bounded cancellation.

# Protected immutable bundle files

AUTHORITY=0. Internal GT-03 storage, not public save, engine validation,
selection, journal commitment or GT-03 acceptance. Accepted GT-02 code and
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
  Another pending command rejects without writes. No cancellation/retry or
  freeing reserved names is inferred from process exit.
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
registered returned versions; added, removed or changed names/bytes hold it.
`active.json` is reserved for a future selector; this API does not write it.

Before preparation, reserve all twelve files and actual bytes **plus two file
slots and 32 KiB** for conservative selector replacement headroom, even if an
old `active.json` already exists. Native limits remain 64 files, 8 MiB total
and 1 MiB per file. No quota reclamation/GC or deletion is supplied. Known
capacity exhaustion is an ordinary rejection, retaining existing receipts.

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

Focused tests use actual fresh Windows protected roots and synthetic inert
bundles. They exercise preparation, exact manifests/barriers/reopen, quota and
selector headroom, identity/copy rejection, response dedupe, concurrency and
faults after native writes/barrier/readback/close. No Godot, Docker, eligible
script claim, public transport or durable coordinator is exercised here.

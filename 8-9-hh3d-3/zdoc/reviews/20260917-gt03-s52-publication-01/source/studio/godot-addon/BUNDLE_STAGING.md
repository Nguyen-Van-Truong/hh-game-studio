# Internal complete fixture staging

AUTHORITY=0. `BundleStager` stores and independently reads actual protected
bytes using the unchanged GT-02 `studio.host.core.private_store` APIs. It does
not select a project, append a publication event, validate an engine result,
materialize or run code, or return public COMMITTED/ACK authority.

## Ownership and API

Successful `BundleStager(store)` construction transfers exclusive use and
close ownership of an **exact** `studio.host.core.private_store.PrivateBlobStore`.
The trusted caller owns its provisioning parent and native store. No root
string, worker descriptor, callback, duck-typed substitute or other namespace's
lookalike class is accepted. Before a successful constructor returns, failed
construction leaves the supplied store owned by the caller.

The caller must stop all direct store use at transfer. One lifecycle RLock
serializes staging, lookup, readback and close. A marker on the exact store
prevents two wrappers even when this module is independently imported twice.
It cannot prohibit deliberately bypassing the API from trusted same-process
code. Sharing a journal's private store with a new stager is unsupported; a
future publication owner needs one explicit ownership chain and lock design.
This standalone slice does not supply that integration or an external-lock
parameter.

The module exports `bundle_codec`, loaded from its exact sibling path and
source bytes using a path/content-derived module key. Construct bundles through
that object to satisfy exact class checks. This prevents silently reusing the
codec loaded from another checkout; it is not a release authenticity claim.

* `stage(command_id, bundle) -> StageReceipt`: validates an exact complete v2
  bundle, admits worst-case capacity, writes eleven files and the manifest,
  then reads and decodes the entire set. Manifest is written last.
* `lookup(command_id, project_revision=None) -> StageReceipt | None`: returns
  the original receipt object after a fresh native owner check. A supplied
  mismatching revision is an ordinary no-effect command conflict.
* `readback(receipt) -> CompleteFixtureBundle`: accepts only the exact receipt
  object registered by this owner for its command/project/source bytes. A
  copied dataclass, another owner's receipt or manually constructed descriptor
  is rejected before I/O. Every file and manifest is actually read, compared
  with retained original bytes and decoded again; native identities, sizes and
  hashes are checked by the actual store.
* `snapshot() -> tuple[StageAttempt, ...]`: reports retained **in-memory**
  ownership, including partial UNKNOWN attempts. It remains usable after hold
  or close and does not verify current native state or authorize cleanup.
* `close()`: closes the transferred native store. On failure the exception's
  `cleanup_owner` retains this exact object and its native registry so close
  can be retried. It does not delete blobs or release unknown allocations.

`StageReceipt` always has `public_ack=false`, `engine_effects_verified=false`
and `namespace_durability_verified=false`. Its status
`STAGED_BYTES_READ_BACK` describes a completed historical internal readback,
not continuing validity after outside mutation. `readback` checks again when
current validity matters. No supplied scene hash, binary hash, provenance,
successful native put or receipt field supplies engine proof.

## Admission and uncertain effects

Before the first put, the owner inventories all existing blobs from native
handles, verifies their identities/DACLs and admits **all twelve new objects**
and their complete actual byte budget against GT-02's unchanged 64-object,
8-MiB aggregate and 1-MiB per-object limits. This counts unrelated existing
and orphan objects too. Enumeration provides names only; untrusted directory
entry metadata is never used as proof. GT-02 still rechecks its own quota for
each put. The exclusive lifecycle plus native writer guard protects the batch;
the owner verifies the resulting entire inventory against its original
inventory and exact returned descriptors after staging.

This addon intentionally calls private GT-02 `_mutex`, `_check` and
`_api.open/inspect/check_security/close` for fresh native read/verification and
complete-batch quota admission. No GT-02 code, ownership marker for an inert
consumer, write-rearm hook or security setting is modified. Unsupported native
identity/security/closure/inventory changes hold this owner; they do not get
converted into ordinary quota rejection.

A bounded in-memory record reserves twelve objects before any put. Each put
is marked attempted before calling native code, because a failed call may
have created a blob without returning its descriptor. Every returned exact
descriptor is retained before immediate byte readback; a second complete-set
readback plus manifest decode is required before returning a receipt.

Malformed data, capacity exhaustion and changed content under the same command
ID reject before effects without holding a healthy owner. Exact same-ID retry
returns the original internal receipt without another put. Native owner or
readback failures hold. Any failure after the first put is attempted retains
the full reservation and all returned descriptors, records `UNKNOWN`, attaches
the cleanup owner and prevents all further effects. There is no automatic put
retry, cleanup, adoption, rollback, resume or garbage collector. A descriptor
lost after native creation remains an unknown orphan even when a directory
entry exists.

Reservations, receipts and dedupe are not durable across process exit. Native
blobs can be independently reopened and read with trusted typed root identity
and descriptors, but this owner has no receipt import/recovery API. Creating
another owner does not recover a failed command or authorize retrying it.
The future publication lifecycle must persist intent/descriptor ownership and
reconcile unknown allocations before effects; this standalone implementation
does not claim that gate.

The store supplies file flush and retained-handle readback. A generic blob
namespace durability barrier is not exposed, so these records make no
power-loss-safe publication claim. Protected selection, event-v2 initialization,
actual engine validation, public availability and restart write authority are
separate future work. Generic Godot rearm is unavailable: no fixed inert
FixtureSelector hook, `_fixture_file_consumer` marker or `_readonly` mutation
is part of this slice.

Tests use fresh random Windows protected roots and synthetic source/UID/engine
values. They exercise actual native storage and known fault cuts. They are not
Godot import, sandbox, production save, release trust or GT-03 acceptance proof.

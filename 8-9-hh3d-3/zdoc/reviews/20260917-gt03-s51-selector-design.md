# S51 store-owned selector integration proposal

AUTHORITY=0. Design only, 2026-09-17; no source changes, engines, tests, acceptance signature, or DoD waiver.
S50 is frozen and running. These are proposed next-checkpoint APIs, not implemented capabilities.
Reviewed source SHA256 (paths below are relative to `studio/`):
- `godot-addon/protected_bundle.py`: `660e40fc3dd0e7301216b55edb8aa7b8c194056bcc7dab2249c954d8c05933e7`.
- `godot-addon/publication_state_v2.py`: `ae484cd1c7f5ccbe2b1739d3e7106c3fc38f188ac1d7812cd3444bbe5a4620e4`.
- `godot-addon/validation_owner.py`: `bd81cc5d6f06888c2825921296eeee06d0edfc13a881d1c13599de2941d514e4`.
- `host/core/safe_replace.py`: `369459bb5fca4ebaf11a4ce9ac848024a9f63502a0df4bbe68d5aa585e2e3fb9`.
No `publication_journal_v2.py` exists at review time; JournalV2 below names the planned owner contract.

## Ownership and inventory

Use one lifecycle chain: JournalV2 owns store; store owns the exact accepted `ProtectedFileRoot` and its close.
JournalV2 owns its separate event-log/custody chain. It never writes or closes the store's raw file owner.
Today `_baseline_inventory` and per-attempt inventory capture `active.json`; an external selector writer would invalidate old bundle receipts.
Separate immutable object inventory from one tracked mutable selector slot `(canonical_bytes, FileVersion) | absent`.
Expected native inventory remains exact: baseline objects + returned attempt objects + the tracked selector slot, including every orphan.
Only `active.json` receives this special treatment; immutable object identities, bytes, and counts remain checked on every readback.
After successful selection update the tracked selector slot; old bundle receipts must still read their unchanged objects successfully.
Keep the current conservative reservation: 12 new objects plus two selector slots and 32 KiB; selector bytes are at most 16 KiB.
Count all existing bytes/files, including the old selector. Recheck native limits before CAS; no GC or deletion is introduced.

## Minimal API additions

`inspect_selection() -> SelectedSnapshot | None`: read strict selector bytes/version and the complete referenced bundle; absent means UNSELECTED.
`select(receipt, context) -> SelectionReceipt`: exact registered bundle receipt and one-use owner context; normal transition requires an existing selector.
`initialize_selection(receipt, context) -> SelectionReceipt`: explicit first-selection path requiring proven absence and an initialization context.
Both methods are store-owned; neither accepts raw paths, caller-chosen selector bytes, guard booleans, or arbitrary callbacks.
SelectionReceipt is frozen and issuer-registered: command/digest/candidate, parent/new selection, descriptor digest, exact selector bytes and FileVersion.
It attests durable selector/bundle readback only; `public_ack=false`, `engine_effects_verified=false`. Historical receipt is not current-selection truth.
`cancel_unused_prepare(intent) -> PrepareCancellation` requires the exact registered PREPARED intent, zero attempted writes, no versions, and no receipt.
Under the store lock, verify native inventory and absence of all 12 planned names before releasing the reservation; delete no files.
Retain command ID, project digest and planned-name tombstones; duplicate cancellation returns the same registered result, changed payload conflicts.
Canceled intents can never stage, and duplicate prepare cannot restore them. Bound attempts plus cancellation tombstones to 64 before accepting prepare.
Any attempted write, unexpected planned name, or uncertain native read prevents cancellation and retains the held owner; cancellation cannot clear a journal hold.

## Fixed selector bytes

Use exact-key canonical JSON, schema `hh-godot-active-selection-1`, at most 16 KiB:
`{schema, project_id, command_id, digest, candidate_id, parent_selection, selection, descriptor}`.
`selection` and non-null parent are exactly `{generation, identity}` using reducer types/bounds; normal selection is parent generation + 1.
`descriptor` is the existing exact `{root_identity, project_revision, files, manifest}` shape, containing all 11 file descriptors plus manifest descriptor.
Normal identity must equal reducer `selection_identity(project_id, command_id, digest, parent, candidate)`; re-read the manifest to recompute it.
The selector's own FileVersion is returned separately, never recursively embedded. Reject extra keys, noncanonical bytes and duplicated IDs/names.
Explicit initialization alone permits `parent_selection=null`; its initial identity/event semantics require a versioned initialization contract below.

## Publication ordering and guard ownership

JournalV2 persists the complete staged/validated candidate and ACTIVATING intent, then verifies its native append/readback/custody barrier.
Use lock order JournalV2 lifecycle lock -> store lock -> one validation/native-owner lock at a time; never call back to acquire journal from store.
The context is an exact issuer-registered object bound to this journal/store, command, original admission, candidate, expected parent and selector FileVersion.
Immediately before native publication, its fixed owner implementation rechecks live session/revocation, original lease/fence/expiry/deadline and Stop latch.
Also recheck editor session/generation, semantic revision, expected project/selection and exact validation receipt against the entire candidate bundle.
Use `ValidationOwner.observation(receipt, bundle)` for registered historical evidence; this is not fresh post-selection engine readback.
Caller-replayed event fields or flags such as `validated=true` cannot supply these live authority checks. Existing GT02 inert scopes do not grant Godot authority.
The store re-reads all 12 candidate files, manifest, current selector and exact inventory before this final guard check.
Mark effect attempted before `atomic_replace('active.json', bytes, expected=old_version)`; initialization uses `create_new` only after native absence proof.
Verify returned FileVersion/bytes, call actual `confirm_barrier('active.json', returned_version)`, then re-read selector, complete bundle and exact inventory.
Only then register SelectionReceipt and update the tracked selector slot; use a private prospective-slot check during verification, not premature success state.
The native consumer next opens the actually selected bundle and obtains new trusted engine postconditions; READBACK time must be at/after ACTIVATING.
Journal READBACK/COMMITTED and public terminal delivery follow that proof, not selector receipt, candidate validation, or a process marker alone.
Set Stop intent before waiting for lifecycle locks; it fences the next admitted native effect, with no promise to interrupt an already admitted syscall.
Known guard rejection before effect performs no selector write. Any ambiguity from effect-start through barrier/readback/terminal persistence is UNKNOWN/held.
Never retry CAS, roll back, accept a newer pointer as success, or release ownership automatically after ambiguity; preserve original lookup evidence.
Lost terminal responses replay the identical durable journal result without selecting again; changed payload under the same ID conflicts.

## Initial baseline and restart

Current CONFIG.initial contains caller-attested metadata/selection, not a native descriptor or proof that any bundle is selected.
Journal readiness therefore starts UNSELECTED unless actual selector/full-bundle evidence establishes the configured baseline; metadata equality alone cannot do so.
For a fresh root, explicitly initialize real bundle A before permitting ordinary transition A -> B; never fabricate a selected generation-zero baseline.
Minimal prerequisite is a versioned initialization intent/result contract and durable owner ordering before the first `active.json` create; current reducer has no such phase.
An optional root-bootstrap helper must use that contract and real validation/native/readback evidence. Until implemented, absence is a blocking UNSELECTED condition.
Readonly reopen can inspect selection and strict descriptors, but cannot register mutation authority, adopt a pending intent, cancel historical work, or rearm.
Use no accepted-core changes or `_rearm_verified_snapshot`/inert-consumer marker spoofing. Replayed events never authorize the next filesystem effect.

## Required two-bundle safety cuts

Initialize eligible A, publish eligible B using A's exact selector FileVersion, and verify both complete immutable receipts remain readable afterward.
Reject wrong root/name/hash/manifest, changed selector/version, expired or revoked admission, stale editor/semantic state, and unregistered validation before effect.
Exercise Stop before/after CAS; lost syscall reply; failures after file flush, selector barrier, bundle readback and before journal terminal; require held UNKNOWN as appropriate.
Exercise terminal response loss/identical lookup, payload conflict, strict readonly reopen, and refusal to resume either initialization or transition after restart.
Exercise unused cancellation, copied intent, canceled restage, attempted-write cancellation, unexpected planned file, and 64 tombstone capacity without disk mutation.
Implementation scope: GT03 store plus new owner/initialization integration and focused tests; accepted core and historical staging stay unchanged.

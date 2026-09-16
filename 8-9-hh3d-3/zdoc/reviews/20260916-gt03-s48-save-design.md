# S48 — Godot scene/script durable publication reuse audit

AUTHORITY=0. READ_ONLY_DESIGN=1. IMPLEMENTATION=NONE. TESTS_RUN=NONE.
No engine launch, acceptance verdict, plan tick, core edit or commit was made.

Audit date: 2026-09-16, Asia/Saigon. Baseline HEAD:
`0c3b00a0450e6a7255e40ae02c69ae1db6d3d6c3`.
Routing read: `../../AGENTS.md`; governing tool plan sections GT-03, 2.3,
2.5 and TX09 in `../8-9-godot-blender-agent-studio-plan.txt`.
The working addon/tests are untracked implementation in progress, not the
accepted GT-02 closure. `git diff --stat` for `studio/host/core` and
`studio/protocol` was empty. Godot/Blender process inventory was empty at the
start and at the final source inspection (23:31 +07). Other lanes may work in
this shared tree; the hashes below identify this audit's relevant inputs.

## Recommendation and limits

Add a small **Godot publication owner and engine consumer under
`studio/godot-addon/`**, using the accepted storage primitives without changing
GT-02. Use one typed Godot event stream for command, lease, publication and
terminal state. Do not subclass/inject a Godot consumer into `FixtureSelector`,
and do not translate its inert `COMMITTED` into a Godot ACK.

This can support implementation of admission, bounded staging and actual
trusted-fixture save/readback next. A complete restart-and-write implementation
cannot currently be assembled from the public primitive APIs alone: protected
file rearm is restricted to the fixed fixture consumer. Arbitrary submitted
scripts have a separate unresolved sandbox prerequisite. Neither limitation
is waived here; full GT-03 remains unproved.

Existing S47 `editor-07` evidence has closure
`f43ca8d6f12ea9e15386859d593ae5e0b7bed1be73e2e7a16ee26965c92fc28a` and explicitly
sets `production_save_verified=false` and
`hostile_script_sandbox_verified=false`. Its actual trusted editor pack/reopen
results do not prove the new state machine or script publication described
below. No tests were repeated for this audit.

## APIs that can actually be reused

Paths in this section are relative to `studio/`.

| Existing implementation | Reusable operation | Exact boundary |
| --- | --- | --- |
| `godot-addon/contract.py` | `validate_request`, immutable `ValidatedCommand`, catalog/discovery | Pure validation and projection. Trusted context is an observation, not lease or filesystem authority. Save/script backend remains absent. |
| `godot-addon/bundle.py` | `create_bundle`, `decode_bundle`, `replace_script`, `FixtureBundle.files` | Exact two-path, immutable byte bundle; scene up to 1 MiB, script 16 KiB, manifest 4 KiB. Caller semantic/engine observations are not verified by the codec. |
| `host/core/private_store.py:223` | `PrivateBlobStore.create/reopen`, `put_bytes(bytes) -> StagedBlob`, `read_blob(StagedBlob)` | Fresh owner-only roots, handle/identity checks and flush/readback. Each blob up to 1 MiB; 64 blobs/8 MiB store. No publish, reservation ownership, semantic validation or orphan repair. |
| `host/core/private_events.py:88` | `PrivateEventLog.create/reopen`, `binding`, `bind_custody`, `append(event, expected, reserve_records, reserve_bytes)`, `read`, `fold` | CAS on event head, retained native guards and durable frame readback. Bound custody must persist before append returns. A pure addon reducer must validate Godot phases and own reservations. |
| `host/core/custody.py:127` | Exact `WitnessCustody(registry, storage_id, project_id, create=...)`; `activate`, `confirm_current`, `persist_binding` | Already binds three roots and event high-water. Use this exact class, not a subclass/callback; `bind_custody` rejects other types. Its fixed `hh-fixture-custody-1` storage schema/ManagedFixture registry namespace remains unchanged. A separate Godot CONFIG event must identify the new owner domain; custody alone does not. |
| `host/core/custody_registry.py` | `RegistryCustody.create/reopen`, `read`, `store(data, expected=...)`, `close` | Protected bounded bytes/flush/readback. Not interprocess CAS: retain the unique file writer guard throughout updates. No worker-provided storage ID or root authority. |
| `host/core/safe_replace.py:93` | `ProtectedFileRoot.create`, `create_new`, `atomic_replace(..., expected=FileVersion)`, `read`, `reopen_readonly`, `confirm_barrier` | Atomic expected-version replace only in a newly minted protected flat NTFS root. Suitable for one compact active manifest, not the `scenes/` and `scripts/` directory tree. Reopen does not authorize subsequent writes. |
| `host/core/journal.py` | `Journal.append_command(pending=True)`, `finish_command`, `lookup`, `lookup_archive`, leases/`lease_guard` | Useful reference for durable dedupe, expiry and capacity. Avoid a second terminal authority alongside the proposed Godot event stream. `append_command` defaults to `pending=False` and creates COMMITTED immediately; it must never be used as admission for this async engine transaction. |
| `godot-addon/addons/hh_studio/plugin.gd`, `scene_commands.gd` | Fixed main-thread inspect/apply/undo/redo projections, complete semantic snapshot | Existing result is `SCENE_APPLIED_IN_MEMORY`; neither serialization nor durable save ACK. Checkpoints, public authentication and durable receipts remain host responsibilities. |
| `build/bootstrap/run_fixture.py:212` | `run_process` for bounded owned diagnostic processes | Captures actual exits/tree. It is not the hostile-script sandbox or a production persistent engine bridge. |

`FixtureSelector` explicitly accepts only exact `FixtureReleaseConsumer` or
`FileFixtureReleaseConsumer` types (`fixture_selector.py:418`). The latter
serializes inert fixture JSON to `active.json`; its readback proves that JSON,
not Godot resources. `ManagedPipeService` likewise requires exact managed
fixture/broker types. None is a generic backend registration point. Shared
protocol `Request`, `Response`, JCS and digest code can be imported unchanged;
the Godot dispatcher/IPC and its work/control lifecycle still need implementation.

Do not nest a second managed fixture journal merely to obtain a rearm hook.
Such a composition could only treat its inner receipt as storage evidence and
would require an additional cross-journal recovery proof. It is more machinery
than the small single-owner design and is not acceptance already obtained.

## Minimal new responsibilities

Suggested names are design labels, not new files created by this audit:

1. `publication.py`: one `GodotPublicationOwner`, strict event reducer and
   compact active-manifest codec. It owns the storage chain, command IDs,
   checkpoint/pending/last-good pins, project lease/fence, phase reservations,
   Stop and explicit recovery. Only one publication is pending per project.
2. `engine_consumer.py` plus a fixed plugin save/readback entry: one owned
   engine session at a time per snapshot, finite messages and main-thread
   dispatch. It captures the edited scene into candidate storage, validates
   the complete candidate with the pinned engine, and reopens the selected
   pair. It never hands private storage/registry handles to Godot.

Use the existing bundle codec for exact content and a small separate storage
manifest for local blob descriptors, release ID, parent revision and tool/source
closure. Resolve both files through the same pinned manifest. No independent
"latest scene" and "latest script" lookup. Generated `.godot` import caches are
disposable validation output, not part of the immutable release.

Checkpoints must preserve the actual before-state, including unsaved scene
changes before a destructive command. A saved last-good bundle alone is not
a checkpoint of an already dirty editor. Capture through the approved engine
serializer, not raw writes into the open scene. Preserve owner edits and
candidate/diff on conflict; never replace newer user bytes to make a test pass.

## Revision contract that must be explicit

Keep these independent values:

| Value | Meaning / check |
| --- | --- |
| Semantic scene revision | Full `scene_commands.gd` canonical state hash, including persisted native properties; guard at main-thread mutation and again around capture. |
| Editor generation | Reload/session binding epoch, not a project content version. A restarted plugin currently begins its local generation again; a new authenticated session binding must fence old projections. |
| Base project revision | Bundle revision of the complete previously selected scene+script pair. A script-only change must invalidate stale save/mutation admission even when the script is not attached to the scene. |
| Candidate project revision | Bundle revision from exact candidate bytes and actual verified scene/engine observations. It becomes the selected revision only through publication. |
| Publication generation/selection identity | Monotonic journal/active-manifest identity that distinguishes repeated content or a restore. Same content hash is not permission to replay an old effect. |

Minimal addon-only contract change: retain the current envelope
`expected_revision` as the semantic scene revision, and add a required
`expected_project_revision` to mutating/save/script payloads and their previews,
with a matching trusted field in `ValidationContext`. Rev the Godot catalog
digest/version; do not alter `studio/protocol`. Strip the host-only project
precondition from the narrow engine projection after validating it; the engine
still guards the semantic revision/generation itself. Discovery/inspect must
return both revisions distinctly. This is a proposed explicit contract change,
not a reinterpretation of already tested messages.

Dirty in-memory node edits change the scene revision while leaving the base
published project revision unchanged. Save compares both. Existing save
`expected_files` and script `expected_sha256` remain necessary raw-byte checks.
The shared request digest covers operation/target/payload/schema, not the lease,
deadline or envelope revision: retain the admitted base observations in the
journal and return the original outcome on same-ID retry; never execute that
ID again with refreshed envelope values.

## Command phases and ACK barrier

Authentication and duplicate lookup precede **new** admission. For new work,
verify capability, fixed paths, both revisions, live source hashes, writer
lease/fence/deadline, current root identity, available backend and Stop state.
No external `force`, consumer callback, path or engine method is an authority.

| Phase | Required work and durable facts | Allowed public meaning |
| --- | --- | --- |
| PREPARED | Persist intent with command/digest, original preconditions, checkpoint ownership, minted candidate ID and remaining record/blob budgets before staging effects. Capture the approved tree to owned candidate output and retain the exact existing script, or the admitted replacement bytes. | Pending only. |
| STAGED | Read and pin complete scene/script/manifest via retained checked handles; persist all descriptors/hashes. Partial writes are preserved and never selected. | Pending; byte validity is not parser validity. |
| VALIDATED | Owned pinned Godot editor performs actual parse/type/import and semantic inspection of those exact bytes. Host verifies result binding, complete files, actual process outcome, logs and tree drain, then persists the verified candidate reference. | Pending; no activation yet. |
| ACTIVATING | Recheck source/project/scene/generation/lease/fence/Stop after slow validation. Persist active-parent CAS intent before native manifest create/replace. Read actual selected manifest/version and pin both files. | Unknown/pending while effect may have occurred. |
| READBACK | Reopen the **selected** immutable pair with an owned clean engine context; resolve stable IDs again. Compare actual scene semantic revision and raw scene/script hashes, engine/source closure and selection identity. Confirm the active file and durability barrier again; preserve last-good until complete. | No COMMITTED yet. |
| COMMITTED | Append bounded terminal receipt to the Godot event stream; event flush/readback and custody high-water barrier both succeed. Receipt includes original command/digest, before/after project revisions, scene revision, selection generation/hash, both file hashes and actual engine observation binding. | Only now a durable Godot save ACK. |
| FAILED / RECOVERY_REQUIRED | Record known pre-effect rejection or preserve uncertainty and last-good pins, based on the phase actually reached. | No successful ACK; report whether staging or active selection may exist. |

`ResourceSaver.save == OK`, a child exit code, a JSON `passed` field, an inert
consumer receipt, and an UndoRedo commit each cover only part of this chain.
The child report is untrusted output: cap it, bind it to the host-owned
process/session/run/selection and verify raw bytes independently. A sandbox
does not make arbitrary `@tool` code in the reporter's process trustworthy;
hostile-code attempts to forge/suppress verification completion also need a
fail-closed result-attribution test before opening that lane.

The initial usable save lane can retain only the exact trusted fixture script
hash and approved native scene graph. This is a restricted implementation step,
not fulfillment of GT-03's script replacement requirement. Do not load submitted
script text in the live trusted editor. Real replacement requires the complete
disposable validation boundary, including implicit `@tool`/import behavior;
validation does not grant a later Play capability.

### Bounded journal and staging details

`PrivateEventLog` has a 16 KiB frame-body cap, 512-record/8 MiB total cap. A
maximal 16 KiB script plus JSON escaping and envelope cannot safely be copied
into one INTENT. Persist exact request/content digests, lengths and original
preconditions in the intent, then store raw candidate/request bytes as bounded
private blobs and journal their descriptors. Do not truncate text or increase
accepted-core limits to fit it.

Persist ownership/reservation before each potentially uncertain put. Reserve
worst-case stage/validation/activation/readback/terminal/Stop records and blob
bytes; count ambiguous/orphan allocation against the budget after restart.
One pending command and exclusive store ownership keep this bounded. A crash
after `put_bytes` but before its descriptor record does not prove absence and
does not authorize a second put. Without a verified matching descriptor or a
separately implemented checked orphan-discovery path, hold/preserve it. Capacity
exhaustion fails closed; no automatic deletion or compaction is proposed.

## Lost response, restart and Stop

* **Lost response after terminal:** fresh read/flush of the original durable
  event plus matching custody returns the same receipt, even when the old
  lease/deadline expired. Changed payload conflicts. It performs no new scene
  edit, stage, import, selection or serialization. Distinguish historical
  COMMITTED from whether a newly started editor is currently ready.
* **Exit before activation:** reopen only the recorded identities and validate
  the whole event chain with its high-water witness. Leave the pending command
  held; no automatic replay. Verified unchanged active selection keeps last-good
  available. Missing/partial/ambiguous candidate data stays preserved.
* **Exit between replace and terminal:** read actual `active.json`, native file
  version and all referenced blobs. Exact candidate permits an explicit fresh
  fenced recovery to repeat verification/readback and finish the original
  command; exact prior selection may remain last-good. Any third/mismatched
  value or newer owner edit requires reconciliation, never overwrite.
* **Complete log ahead of custody:** validate typed phase and actual publication
  state before advancing the witness. A valid checksum/scan alone does not make
  an engine result valid. Torn or missing witnessed history remains held.
* **Restore:** explicit, journaled and revision-checked selection of a verified
  last-good pair. Never undo newer owner edits. A canceled/unknown restored
  command remains terminal for dedupe. Under today's public APIs, a restarted
  Godot root cannot yet perform this manifest write; expose that hold honestly.
* **Stop:** latch before waiting for storage/engine work, reserve its durable
  record, and use an independent responsive control path/watchdog. Recheck after
  scans, import and readback before each new effect. A native call already
  admitted may finish; uncertain outcomes remain UNKNOWN. Drain owned workers
  with actual exit/tree evidence. Restart never clears STOP or reconnects old
  sessions; Stop does not discard lookup or terminal records.

Never hold a generic journal `lease_guard` across asynchronous engine work and
then claim its old admission time covers publication. Fresh authority and source
checks are required at each effect. OS/file calls may block despite byte caps;
the owner process/job must remain bounded, with ownership retained through failed
cleanup rather than closing buffers/handles still in use.

## Concrete unavailable primitives and next work

1. **Godot publication rearm:** `ProtectedFileRoot.reopen_readonly` is safe for
   lookup/barrier. Its only rearm method (`safe_replace.py:182`) is private,
   demands `_fixture_file_consumer`, and permits only `.writer` + `active.json`.
   Do not assign that private tag, flip `_readonly`, substitute a subclass or
   relax core checks. A separately implemented/reviewed Godot-specific native
   publication lifecycle under the addon is needed if core must remain frozen;
   it is new safety implementation, not an accepted API already available.
   Until that exists, restart can inspect/hold/verify, but cannot claim complete
   write-resume or rollback support. The alternative of changing core would
   require its own explicit scope/acceptance decision and is not proposed here.
2. **Engine-readable snapshot bridge:** private blob roots are intentionally
   unreadable to the confined worker; the flat protected root is not a Godot
   project tree. Implement and test a fixed-path, complete snapshot materializer
   and bounded output reader under owned sandbox identities. Do not grant Godot
   private-root rights or use unchecked pathname copies as a publish primitive.
   Existing trusted diagnostic `shutil`/temporary-project setup is not this
   production boundary or generic safe-write proof.
3. **Arbitrary-script sandbox:** S47 run-02 proves startup with zero AppContainer
   capabilities, selected access denials and trusted fixture execution only.
   `20260916-gt03-s47-sandbox/HANDOFF.md` records remaining engine diagnostics,
   unexercised network/child denials and missing hard disk bound. Its
   `DISK-CAP-DECISION.md` requires an externally provisioned bounded volume plus
   proof for every writable surface, including AppContainer/profile/registry
   storage and inherited handles. This audit does not provision, elevate, waive
   or reclassify that prerequisite. Preflight must return an unavailable result
   before arbitrary parse/import; a periodic directory-size scan is insufficient.
4. **Public Godot transport/admission:** current plugin has no authenticated
   queue/receipt transport. Existing fixture services are type/scope fixed.
   Add the finite Godot work/control adapter under the allowed addon scope and
   prove its actual caller/process binding; do not advertise save/script
   capabilities from static catalog declarations or from an engine startup test.

These are bounded next implementation tasks and blockers, not extra plan
checkboxes. Trusted scene transaction work can proceed independently of the
arbitrary-script boundary, while the full GT-03 DoD remains unchanged.

## Required tests for the new implementation

All rows are proposed; none was run in S48. Each actual process cut needs a new
run ID, frozen complete source/tool closure, armed cut marker, real host exit,
separate logs and actual remaining process/handle cleanup observations.

| Test group | Required observable result |
| --- | --- |
| Actual save/undo/redo/reopen | Edit approved native scene, retain real dirty checkpoint, serialize staged scene, validate then reopen selected pair in a fresh process. Exact stable IDs/owners/semantics and raw script hash match; no direct live-scene file overwrite. |
| Two revisions and late edits | Script-only change invalidates old project CAS, scene-only dirty edit invalidates old semantic CAS, same-content restore has a distinct selection generation, manual edit during parse blocks late activation, restarted session rejects old generation/projection. |
| Parse/import failures | Actual invalid syntax/type/import, oversize UTF-8, stale script hash and missing dependency prevent activation. No report/file/process-exit shortcut to COMMITTED. Arbitrary `@tool` tests wait for proven sandbox availability. |
| Phase cuts | Cut after intent, first blob write, blob readback before descriptor, complete stage, validation, activation intent, native replace, reopen observation, terminal event and custody update. Restart observes old or complete new pair, never mixed files or automatic command replay. |
| Lost reply | Drop replies before and after terminal. Same ID returns pending/UNKNOWN or original receipt; changed content conflicts. No duplicate node, second stage or extra selection. Current engine-ready status remains distinct from historical receipt. |
| Storage/TX09 | Actual antivirus-style held-file lock, configured capacity refusal, short write, failed flush, disk-full on approved disposable bounded storage, cross-volume rejection and corrupt/missing descriptor. Old pair/uncertainty is preserved; cached bytes alone do not authorize success. |
| Stop/control | Stop during validation, quota scan, replace and blocked engine response; saturated/lost work channel still allows control lookup/Stop. Durable Stop survives owner restart, no new phase starts after latch, owned tree drains or remains explicitly held. |
| Recovery authority | Second owner guard conflict; stale fence rejected; custody suffix loss/ahead records, manifest FileID substitution and orphan staging held; actual restore/write-resume tested only once Godot rearm exists. |
| Evidence attribution | Forged/stale run ID, source/tool/selection hashes, truncated result, missing marker, success banner with nonzero/hung exit, stale cache and hostile-code forged completion all fail closed. Byte pin and engine semantic observation must refer to the same candidate. |

Two independent critics must assess the final frozen implementation/evidence;
no S46 or S47 signature transfers to this design or later source.

## Inspected source hashes

SHA-256 of selected inputs at 2026-09-16T23:31:08+07:00; this is a read-only
audit binding, not a complete execution closure. Paths are relative to `studio/`.

```text
host/core/private_store.py c914b5a66a45660c782ecd43fd2321c238702340f3b33062e284feada4d46476
host/core/private_events.py 5beb556dda4e9c7f137ece366b1ed231bf3b5039e365299f657b089911cf9171
host/core/safe_replace.py 369459bb5fca4ebaf11a4ce9ac848024a9f63502a0df4bbe68d5aa585e2e3fb9
host/core/custody.py aa4320faeccb3b729d0eebf29ac3e962d2590bca1e3aba14b0aef620b021fbc9
host/core/custody_registry.py 54a45327faf5630f750108781e427c0b01f04ae6482df7d2572dfba1b6ea3db2
host/core/journal.py 826bc5e4c60817e3a22dd2e0b6a199eb522a4eb78532cb5300249fe9056c0cc6
host/core/managed_fixture.py 5be6efa0c9daab785cbc1661a5e03a71d6fb14bd30892f15f2fd75ab81191b3b
host/core/fixture_selector.py 07537994a695039b2217d0b46cd336ba4adcb11b63751c24ab3008837c6a7597
godot-addon/contract.py 17d2360a0f99fa1537e868172922794e33b2223368ff0ae18cdf9d1abb41a904
godot-addon/bundle.py c246403fb0e40e49d33c638c29fd097a32d72631d22166b19f6acc483c25824f
godot-addon/addons/hh_studio/scene_commands.gd ac4bf9e239b082efe9dd542f14c6cb8e202597bdfa1b8160e5da7905413aa0ea
godot-addon/addons/hh_studio/plugin.gd 2a5eeb10e9adf0b705293545936f2abd8e352cfbe6b4df7d13411b0cf610243b
```

S48_SAVE_DESIGN_END

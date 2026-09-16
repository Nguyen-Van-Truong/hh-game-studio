# S49 native Godot publication integration — bounded implementation design

AUTHORITY=0. Date: 2026-09-17. Read-only design, not a formal critic verdict or GT-03 acceptance.
Baseline HEAD: `e09f7806a6e3198e82c4ac1dd42dffd342531ef5`; S49 addon files are working drafts.
Scope: tools plan §§2.3/2.5, GT-03/TQ03/TX09. No engine, container, test, source edit, commit or tick performed for this report.
The eligible declarative profile is a proposed availability restriction; actual sandbox import and editor reload/readback remain required.

## Decision and smallest next slice

Build one GT03 publication coordinator over a **v2 journal-owned stager**, first proving native PREPARED→STAGED, exact lookup, Stop and restart-held behavior.
Keep discovery for public save/replace disabled until protected selection, namespace durability and a real Godot consumer are connected and tested.
This first slice is useful durable plumbing; its successful staging receipt is explicitly not COMMITTED and does not complete GT-03.
Keep accepted `studio/host/core` and `studio/protocol` unchanged; do not wrap Godot in the accepted inert fixture consumer.

## Reusable APIs and boundaries

| Existing API | Reuse in the addon | Boundary |
| --- | --- | --- |
| `PrivateBlobStore.create/reopen`, `put_bytes`, `read_blob` | Exact native protected bytes and typed `StagedBlob` descriptors | 64 objects/8 MiB total/1 MiB each; no generic blob namespace durability barrier |
| `PrivateEventLog.binding/bind_custody/fold/append` | Expected-head append, exact `WitnessCustody`, verified replay | Native first GENESIS only; reserve remaining records/bytes before effect |
| `RegistryCustody`, `WitnessCustody.activate/confirm_current` | One storage-ID registration binding exact file/blob/event roots | Not an arbitrary additional-root registry or engine proof |
| `ProtectedFileRoot.create/read/create_new/atomic_replace/confirm_barrier` | Flat active-manifest pointer, retained `FileVersion` CAS, file+directory barrier | Flat names only; reopened root stays readonly |
| `SessionAuthority.issue/authenticate/check_current/rotate/revoke` | Dedicated Godot-fixture issuer, current authentication and secret redaction | Existing scope names only; never reuse the inert broker's credential registry |
| Shared `Request`, `canonical_bytes`, `parse_json`, addon `contract.py` | Original command digest, exact framing/schema and project-CAS validation | Strip host project guard only after validating it, never before hashing |

`ManagedFixtureOwner.reopen` revalidates an inert `FileFixtureReleaseConsumer`, issues its own recovery fence and calls the fixture-only rearm hook.
`SelectorFixtureBroker.from_managed`, `SelectorPipeServer` and `ManagedPipeService` require exact inert types/registrations; they are patterns, not generic Godot adapters.
Do not set `_fixture_file_consumer`, modify `_readonly`, call `_rearm_verified_snapshot`, or infer a Godot ACK from an inert COMMITTED record.
The older `Journal.acquire_lease/check_lease/lease_guard` uses a separate journal/lock and forbids I/O under its guard; do not add it as a second publication authority.

## One owner, one authority

Proposed ownership: `GodotPublicationCoordinator → PublicationJournal(v2) → {registry/custody, protected pointer root, event log, BundleStager → PrivateBlobStore}`.
Journal creation provisions the native store, binds custody, then explicitly transfers exclusive store use and close ownership to the stager.
After transfer, journal verification uses narrow stager owner-identity/native-check methods; journal must stop directly using or closing the raw store.
Do not construct today's stager around today's journal `_blobs`: both currently own lifecycle and closing, so that composition is unsupported.
Lock order is outer journal lifecycle RLock → stager RLock → native owner locks. No stager callback acquires the journal lock.
The coordinator owns the journal lifetime, not duplicate native handles; service threads must drain before coordinator close, and failed cleanup retains the exact owner.
Reserve all twelve objects (eleven content files plus manifest), actual aggregate bytes and terminal journal capacity before the first put.
Native inventory includes orphans. Five complete bundles consume 60/64 objects; an initial baseline plus four candidates can exhaust the bounded fixture without GC.
No deletion, capacity reclamation, abandoned-descriptor adoption or automatic retry is part of this slice.

## V2 schema and historical compatibility

Add `publication_state_v2.py`; keep `publication_state.py` and all v1 histories/receipts byte-semantic compatible.
Select a source-bound reducer once from the first CONFIG schema. Reject mixed-version events, later CONFIG/GENESIS and unknown event fields.
V2 CONFIG binds project/storage identity, profile, engine/validator source closure and the expected baseline; CONFIG alone proves no selected project or engine effects.
Use a fresh v2 owner for migration. Preserve the original v1 storage ID/head and two-file revision as historical linkage only.
Initialize readiness only through a separate verified baseline transaction over all eleven actual files; never synthesize missing UID/config/addon bytes or upgrade an old receipt.
V2 candidates bind manifest schema/profile/hash/size, all eleven fixed path→role/hash/size entries, twelve native descriptors and trusted-source revision.
They also bind before/after full project revision, semantic scene revision, parent/new selection identity+generation, command digest and original admission authority.
Retain phase order PREPARED→STAGED→VALIDATED→ACTIVATING→READBACK→COMMITTED, plus FAILED/UNKNOWN/STOP; add bounded durable LEASE events to this same stream.
Persist descriptor metadata and hashes, never script text or a full manifest. Bound each canonical event below the native 16-KiB event cap, with terminal capacity reserved.
Do not raise caps merely to fit a redundant event; references to prior event hashes can bind immutable metadata already recorded in this command.
`project_revision` means the v2 full eleven-file bundle plus its bound observations; semantic `scene_revision`, editor reload generation and selection generation remain distinct.
`bundle_v2.replace_script` preserves supplied observations: recompute/verify candidate semantic state; copying the old observation does not make it true after replacement.
Candidate expectations may be predicted before validation, but VALIDATED requires the real engine result to agree; if it differs, fail the candidate rather than rewrite its staged identity.
Version the catalog for the v2 revision meaning. Keep the two editable-file guards in `scene.save.expected_files`, while the host independently checks every selected v2 file via full project CAS.
This avoids eleven worker-controlled paths while still fencing UID/config/addon changes. Preserve old catalog fixtures as historical tests; no silent revision reinterpretation.

## Admission, effect and receipt sequence

1. Authenticate the dedicated session/project and validate the full original Request/canonical size. Reject sensitive identifiers/content, unsupported profile and unknown operations before intent.
2. Lookup command ID+digest first under owner admission serialization. An identical terminal command returns its stored response; different payload/digest conflicts without another effect.
3. For new work require writable/healthy owner, no pending command, selected verified baseline, current lease/fence/session, deadline, editor session+generation, semantic revision and v2 project CAS.
4. Persist PREPARED with original authority/deadline, checkpoint/last-good selection and candidate expectation; only then start one local in-memory job and native staging.
5. Stage all eleven bytes plus manifest through the owned stager, read/decode the entire set, then append STAGED with exact returned descriptors. A put error retains reservations and UNKNOWN ownership.
6. The owned validator consumes a newly checked complete source closure in its bounded sandbox. Persist VALIDATED only from actual parse/import/readback with pinned engine, source, UID and semantic postconditions.
7. After slow validation, recheck the original lease/fence/session/deadline, Stop, editor identity/generation, current semantic revision, selected FileVersion and all selected byte hashes.
8. Persist ACTIVATING, then recheck authority/deadline/Stop immediately before atomic selection CAS under the same owner admission discipline. Never substitute a newly issued lease for the original admission.
9. Select a small canonical active pointer identifying the complete candidate manifest/descriptors, parent identity and incremented selection generation. CAS, native readback and `confirm_barrier` must agree.
10. A Godot consumer resolves the **actual selected pointer**, reads every selected blob again and opens that exact graph in a fresh owned engine session; compare source/UID, nodes, properties and semantic revision.
11. Complete required editor adoption/reload readback under the recorded editor binding. A preselection validation result or same-process cached ResourceLoader object cannot satisfy this step.
12. Append READBACK then a terminal event containing the exact bounded public Response body and proof references; return it only after native journal/custody readback verifies persistence.

Only the live coordinator may supply trusted observations, from its owned executor/consumer; worker JSON flags and reducer consistency checks are not that authority.
A terminal pure state remains nonpublic. Public COMMITTED needs selected-byte durability, actual engine/editor readback and durable response ownership together.
Use a dedicated issuer with existing `fixture.read`, `fixture.write`, `control.stop`, `control.cancel` scopes, plus the Godot broker's exact operation/target allowlist; no core scope monkeypatch.
Session revocation/Stop fences the next phase, including a fresh pre-CAS check; do not hold session locks over unbounded engine/I/O waits or promise to interrupt an already-admitted native call.
Keep one pending publication. Busy admission rejects without intent; this bounded slice does not claim GT-07 multiwriter FIFO scheduling.

## Failures, response loss and restart

Stop sets the in-memory fence before waiting on storage locks. Before ACTIVATING, known canceled/invalid work may finish FAILED with `publication_not_started=true` and `staging_may_exist=true`.
After ACTIVATING, selection error, timeout, lost readback, stale editor or Stop yields UNKNOWN/held until a separate reconciler proves the outcome; do not claim no effect or blindly restore last-good.
If native append/custody is ambiguous, retain cleanup ownership and hold immediately; do not force a new UNKNOWN event into an already-poisoned log.
A socket loss after terminal persistence is ordinary: current authenticated lookup returns the identical stored response without another lease, engine run, selection or put.
Lookup of a historical COMMITTED receipt is not a claim that the current selected project is healthy. Current inspection separately checks live selection and engine state.
Restart reconstructs history from custody/high-water and native descriptors, never an execution queue. Pending PREPARED may already have orphan blobs; never restage it automatically.
Reopened owners stay readonly even after complete terminal history; offer verified lookup/inspection only. Writable recovery needs a new Godot-specific reconciliation/rearm design and evidence.
Do not import a reconstructed dataclass as today's `StageReceipt`: the current stager accepts only original registered object identities; durable descriptor readback needs an explicit readonly recovery API.

## Minimal files and verification for the next implementation

Next slice: new addon `publication_state_v2.py`, `publication_coordinator.py`; modify addon `publication_journal.py` and `bundle_staging.py` for explicit ownership transfer, v2 dispatch and readonly descriptor verification.
Add focused `studio/tests/godot` pure reducer and actual Windows native owner tests. Preserve v1 tests unchanged; no accepted-core edits.
After the blocking consumer work: new addon `publication_consumer.py` and `publication_pipe.py` own Godot-specific selection/adoption/service; update addon `contract.py`/`operations.json` and their tests/docs.
The transport mirrors work `/v1/discovery`, `/v1/lease`, `/v1/commands` and separate control `/v1/lookup`, `/v1/inspect`, `/v1/cancel`, `/v1/stop`; use exact connected native endpoints, not inherited inert broker types.
Advertise only connected operations. Inspect combines live semantic observation and selected v2 project revision; save/replace cannot be enabled from the static catalog or platform name.
Required tests: all phase-cut replays; duplicate vs changed-payload conflict; old v1/mixed-v2 rejects; eleven-file/UID/trusted-source tamper; native descriptor identity and orphan quotas; exclusive ownership/close fault cuts.
Exercise expiry/revoke/Stop immediately before and around activation; stale editor/base/FileVersion; process restart at every append/put/selection/readback cut; lost terminal reply with byte-identical lookup.
Inject antivirus-style sharing failure, disk full and post-effect readback/barrier/custody failures; require UNKNOWN with no second effect. Engine tests must observe actual pinned processes and fresh postconditions.
Check actual encoded request/response bounds separately: pipe framing allows 256 KiB, catalog payload 64 KiB, script 16 KiB, native event 16 KiB; these are different limits.

## Explicit blocking gaps

No generic blob-directory durability barrier is exposed; file flush/readback alone cannot prove a power-loss-safe immutable selected graph.
No Godot publication consumer currently binds native selection to the exact eleven-file project and required editor reload/readback; sandbox validation alone is prepublication evidence.
ProtectedFileRoot is flat and readonly on reopen. Use immutable blobs plus a protected selection pointer and an owned fixed-path materializer, not sequential overwrites of the active scene/script.
The materializer must prove exact input inventory/hash/UID/trusted source mapping; it does not need a second independently mutable authoritative project tree.
Generic write rearm, durable stager receipt recovery, authenticated Godot service and actual receipt-producing lifecycle remain unimplemented. Root's profile/validator review remains separate.
These are availability/implementation gates, not grounds to weaken §2.3, §2.5, TQ03 or TX09.

## Exact reviewed source hashes

Paths below are relative to `8-9-hh3d-3/studio`; addon drafts were rehashed after reading. This list is a review snapshot, not a complete runtime freeze manifest.

| Path | SHA-256 |
| --- | --- |
| `host/core/managed_fixture.py` | `5be6efa0c9daab785cbc1661a5e03a71d6fb14bd30892f15f2fd75ab81191b3b` |
| `host/core/fixture_selector.py` | `07537994a695039b2217d0b46cd336ba4adcb11b63751c24ab3008837c6a7597` |
| `host/core/selector_pipe.py` | `dfc4fbc94c45e515c43fcd3424eaf9098497fb3b687648b48f766fd09d4231be` |
| `host/core/managed_service.py` | `4fdd446894dc9ab7d3a2fb0426aa0b622611c4f2fe43825f73d05e199ce5bc7b` |
| `host/core/transport.py` | `1ec03356b1cb8c8987e1604bcb164aea6a9934dbe259451c19e12de36398aba0` |
| `host/core/journal.py` | `826bc5e4c60817e3a22dd2e0b6a199eb522a4eb78532cb5300249fe9056c0cc6` |
| `host/core/pipe_io.py` | `647e420b7d72506b8b1611a54a2f9bcef2e590a34230dd4a5f54fb136fcd6946` |
| `host/core/private_store.py` | `c914b5a66a45660c782ecd43fd2321c238702340f3b33062e284feada4d46476` |
| `host/core/private_events.py` | `5beb556dda4e9c7f137ece366b1ed231bf3b5039e365299f657b089911cf9171` |
| `host/core/safe_replace.py` | `369459bb5fca4ebaf11a4ce9ac848024a9f63502a0df4bbe68d5aa585e2e3fb9` |
| `godot-addon/publication_journal.py` | `aa230fc6f31bec6ae69c7192cba92bbd6438cf00a4a0680fd2ce26f55cd02f23` |
| `godot-addon/publication_state.py` | `cee38e70be71c0d143dff7fa07103246bbbec0ea9d56e7d51ed4fb1077e5fbf1` |
| `godot-addon/bundle_v2.py` | `2c5cdc71cdaf80f58bb93ec791e84bab8bd02cd4d9bdbd93d635db13583de62a` |
| `godot-addon/bundle_staging.py` | `3d614edbec8e9a7f5ad3caf2b9694d7498df129de95683952268621f91d68e43` |
| `godot-addon/contract.py` | `bc34eac25f2e03a026c89e7cb77ee56bb7244559c518c6b432d306ba43d41b1c` |
| `godot-addon/operations.json` | `8c42540668be350e5dc67a384fd077de7606c0e54deef3e40bba52c7f788c61c` |

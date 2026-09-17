# GT05 staged publication readiness — 2026-09-17

NON_AUTHORITATIVE=1. Read-only design review, not acceptance or a critic signature.
Base HEAD inspected: `70fb50f447f50d2abf449d69047374da555fab8b`; pipeline files are
active work and are not frozen by this report. No native processes or tests were
launched for this review. Only this report was written.

Authority: [GT05 plan](../8-9-godot-blender-agent-studio-plan.txt), GT05 DoD,
TQ05, TX04/07/08/09 and sections 2.4–2.5. GT05 publishes a **staged snapshot**;
active editor activation, cross-application revisions/reload and the GT07
multiwriter recovery protocol remain outside this slice.

## Recommendation

Add one closed pipeline snapshot adapter and a small pure history reducer over
the existing protected storage primitives. Publish already validated fixed
bytes into a fresh protected root, make its completion selector durable, then
return a receipt for that staged snapshot. Keep a previous completed snapshot
untouched. Do not turn the diagnostic directory into a release or broaden the
accepted GT04 publication profiles.

Suggested new scope: `studio/pipeline/snapshot_state.py`,
`snapshot_owner.py`, `tests/pipeline/test_snapshot_state.py`,
`test_snapshot_owner.py`, and one bounded native protected-storage fault probe.
These are proposed files/APIs, not existing implementation.

## Exact reuse boundary

| Existing file / API | Reuse and constraint |
| --- | --- |
| `host/core/safe_replace.py`: `ProtectedFileRoot.create(parent)`, `create_new(name, bytes)`, `read(name)`, `confirm_barrier(name, FileVersion)`, `reopen_readonly(root, expected_root)` | Actual protected release bytes, identity/hash readback and directory barriers. Flat, fixed names only. Reopen does not regain mutation authority. |
| Same file: `atomic_replace(name, bytes, expected=FileVersion)` | Available CAS primitive for a later managed selector, but unnecessary for the first fresh-root GT05 snapshot. Do not replace a user editor's active manifest. |
| `host/core/private_store.py`: `PrivateBlobStore.create`, `put_bytes`, `read_blob`, `reopen` | Optional provenance mirrors following the existing custody owner composition. A blob receipt alone is not the durable protected file version. |
| `host/core/custody_registry.py`: `RegistryCustody.provision_base/create/reopen`; `host/core/custody.py`: `WitnessCustody(..., create=True)`, `activate`, `confirm_current`, `binding` | Bind the storage ID to exact file/blob/event roots and the witnessed history. The current custody schema expects all three roots. |
| `host/core/private_events.py`: `PrivateEventLog.create/reopen`, `bind_custody`, `append(event, expected_head, reserve_records=..., reserve_bytes=...)`, `fold` | Persist and verify the closed snapshot history. Reserve terminal/Stop capacity before starting effects; hold untrusted/unwitnessed suffixes. |
| `host/core/journal.py`: `Journal.acquire_lease`, `check_lease`, `check_revision`, `lookup`; `Lease` | Reuse a coordinator-owned lease/fence for the specific staged target and expected source revision. A caller-created `Lease` is not authority. `lease_guard` explicitly forbids I/O/waits inside its non-reentrant guard. |
| `host/blender/deadline.py`: `AbsoluteDeadline`; `pipeline/native_job.py`: `run_trusted_stage`, `verify_captured_stage` | Preserve the original deadline/Stop signal; verify captured child exit/tree/log hashes. Run heavy intake in `admission_worker.py`, outside the publisher lock/supervisor. |

Do not directly invoke `BlenderPublicationOwner.publish()` for GT05 bytes. Its
`create()` requires `DurableBlenderSession`/`BlenderUIHost`; it binds the GUI
generation, the box snapshot validator, `checkpoint.blend`/`scene.glb`, and only
`export.publish`, `scene.save`, `checkpoint.save`. Its `_put`, `_read_protected`,
`_append`, read-only reopen and `UNKNOWN` handling are the reference behavior,
not public extension hooks. Keep its accepted schema and fixtures unchanged.

Likewise, `godot-addon/protected_bundle.py` loads the exact trusted
`fixture_profile.py` / `bundle_staging.py` / `bundle_v2.py` codec. That managed
scene/script profile is not a generic GLB bundle factory. Reuse the lower
storage primitives; do not relax its closed source membership to add GT05.

## Small staged snapshot contract

1. Bind one command ID/digest to a fixed profile, source/tool/profile/preset
   closure hashes, expected source revision, artifact hashes, and the verified
   producer/admission/Khronos/Godot comparison evidence. Validate all gates and
   capacities before `INTENT`; a process exit or caller `completed=true` alone
   is insufficient.
2. Use a new custody-bound root per candidate. Minimal asset closure:
   `fixture.blend`, `fixture.glb`, `producer-report.json`, `asset-manifest.json`,
   and a small `snapshot.json` completion selector. Packed textures must be
   inside the asset bytes; no external executable/runtime dependency is
   satisfied merely by listing its path/hash.
3. This is an **asset snapshot**, not a self-contained launchable Godot project.
   If the receipt instead promises a launchable project, enumerate and carry
   the existing fixed authored sources/preset/consumer seed as explicit slots,
   with a logical-name-to-flat-file mapping. Do not publish `.godot` caches,
   native temporary files or arbitrary directory contents.
4. Use a closed history equivalent to `CONFIG → INTENT → STAGED → SELECTING →
   TERMINAL`, with persistent Stop. `STAGED` binds every protected `FileVersion`
   and content hash. Create the selector only after all bytes are read back;
   reread and `confirm_barrier` the selector and bundle before terminal receipt.
   The receipt says staged snapshot only, `public_ack=false`, and no editor
   activation. It is not GT05 acceptance.
5. Recheck custody, source revision/fence, deadline and Stop at effect boundaries.
   Pre-intent failures reject without storage effects; uncertainty after intent
   returns/retains `UNKNOWN`, keeps cleanup ownership and preserves diagnostics.
   Retry of the same ID/digest looks up the exact receipt or unresolved prefix;
   it never reruns export/import or writes a second snapshot. A conflicting
   digest rejects. Reopen is read-only and verifies journal/custody/selector and
   all bytes; an incomplete prefix cannot become committed by inference.
6. Previous completed roots remain immutable throughout a failed new attempt.
   GT05 need not switch a shared editor pointer to demonstrate last-good
   preservation. GT07 owns that later switch/reload/readback contract.

## Capacity and serialization

- Protected files and blobs: **1,048,576 bytes each**, **64 entries/objects**,
  **8 MiB total per store**. Reserve space for manifest/selector and temporary
  replacement files before intent. Do not change accepted core constants.
- `PrivateEventLog`: 16 KiB/event, 512 records, 8 MiB/log; custody/registry
  state: 16 KiB. Journal events should contain bounded descriptors/hashes,
  not full producer reports or accessor arrays.
- Admission worker `semantic.json` cap is **16 MiB of private diagnostic data**,
  not a publication exemption. Either omit that derived array dump from the
  runtime release and retain its evidence hash, or explicitly enforce the
  1 MiB publication cap if it is included. Do not add chunking/compression just
  to evade the existing profile in this slice.
- Observed candidate sizes: producer-native-05 `.blend` 134,559 bytes, GLB
  216,436, producer report 328,463; validation-native-04 manifest 6,682,
  preflight 1,297, semantic dump 418,650. These fit today; independent capacity
  checks must still guard future candidates before any intent.
- Preserve exact external report bytes and their hash domain. Admission marker
  `semantic_sha256` hashes the serialized file including LF; the preflight
  semantic fingerprint hashes compact sorted JSON without that LF. Protocol
  JCS must not silently rewrite native floating-point JSON or reuse its hash.

## Current requirements and remaining proof

The table records what was visible during this review, not a frozen pass/fail
audit. `gt05-validation-native-04/validation.json` is a completed diagnostic
bound to producer-native-05 and both admission/Khronos captures. Its preflight
reports 114 accessors, 54,885 decoded scalars, 192 RGBA bytes. The inspected
consumer-native-03 directory had no final `consumer.json` at that time.

| Requirement | Existing code/evidence | Smallest remaining closure |
| --- | --- | --- |
| TQ05 / TX07 axis, rig, PBR, LOD, sockets | Producer checks LOD 8k/2k, material count, exact bone/object sets; numeric intake exists. `godot/consumer.compare_observation` checks bounds/TRS, skin binds/vertices, materials/pixels/channels, poses and roles. | Finish captured Godot baseline and comparisons on one frozen closure. Add actual renderer draw-call readback/guard for the **150** limit; none was found. Confirm six views and idle/walk visually, not solely report hashes. |
| Naming before publish | `naming.validate_catalog` and negative unit vectors; consumer binds exact mesh/clip sets, then bones/materials/socket identities in readback. | Publication gate must invoke/require the complete name binding, not only accept a syntactically valid caller catalog. Add bad-name candidate → no protected output/selector test. |
| Changed-bone migration | `CONSUMER_BONE_MIGRATION_REQUIRED` checks exact observed bone sets; no native rename/delete campaign was found. | Fixed rename and deletion negatives must produce migration-required with affected authored socket/skin consumers identified, preserve the baseline, and never guess name/index remapping. Do not implement a general migration editor. |
| TX04 unsupported input/material/missing texture | Accepted GT04 protections remain; GT05 producer uses generated original inputs and has explicit profile checks. GLB/PNG/accessor negative suites and isolated intake exist. | Carry applicable unchanged GT04 proof by exact closure; add GT05-specific missing embedded texture, unsupported shader/bake requirement and fixed generated-source negative proofs. An arbitrary `.blend` intake feature is not required and must not appear accidentally. |
| Malformed / wrong axis/scale/clip/skin | Extensive byte/value negatives exist; consumer numeric comparison and fixed texture/preset checks exist. | One integrated reject campaign must show malformed GLB and semantic mismatches stop before import where detectable, otherwise before staged selection, with last-good unchanged. Include shortened clip, wrong scale/axis and LOD skin mismatch. |
| TX08 repeat and real edit | `preflight.compare_repeat` plus position/pixel edit unit vectors; producer-repeat-01 exists. | Bind two actual export captures to their separate SHAs and a recorded semantic comparison. Validate edited producer variant and show its actual semantic signature changes. Presence of a repeat directory alone is not comparison evidence. |
| TX08 reimport | `consumer.replace_inputs`, probe `reimport`, and authored-source/attachment checks exist. `run_consumer.run()` currently drives `import` + `baseline` only. | Preserve baseline source/evidence, stop engine, use `replace_inputs`, rerun import in the **same private project/cache**, then bind reimport observations proving authored script/material override/attachment state survives and changed asset geometry appears. Sequential temp+replace here is only a fixture update, not publication. |
| TQ05 visual | Probe/verification expects 6 static views plus 31 frames each of idle and walk (68 PNGs), source/PID/hash-bound. | Drive the real visual phase under the owned Job and review those images under Godot lighting. Preserve failed captures; no Blender beauty render substitution. |
| TX09 staged publication; lease/Stop | Core primitives and accepted GT04 recovery/Stop tests exist; no GT05 snapshot owner exists yet. `native_job` cancellation is not durable snapshot publication. | Implement only the staged adapter above and its fault matrix. Full editor activation, shared active revision, fairness and cross-app recovery stay GT07. |
| Manifest / final gate | Current manifest carries artifact/profile/catalog/license/source pins and validation hashes. | Close source/creator/attribution (original-fixture attribution may be explicitly empty), timestamp, import preset/Godot pin, source/tool closure, tolerance/domain, geometry/material/LOD summaries and Godot evidence references in the release manifest or embedded fixed report. Then freeze final closure and obtain both independent critics. |

## Required new publication tests

1. Pure reducer: reject skipped/reordered phases, profile/slot substitution,
   mismatched source/manifest/artifact hashes, forged terminal receipts and
   invalid selector versions; every interrupted prefix remains uncommitted.
2. Owner: one successful snapshot has exact protected readbacks; duplicate
   ID/digest returns identical receipt with zero native/storage work; changed
   digest rejects; direct caller metadata cannot substitute captured validation.
3. Caps and authority: every file/aggregate/count/reserved-journal boundary;
   bad name, hardlink/reparse/outside capture, stale lease, changed source and
   expired deadline all fail before the relevant effect. A fresh root does not
   imply permission to activate a user editor.
4. Stop at each publication boundary, including just before selector and while
   native work is active: signal the owned Job before waiting on owner locks;
   preserve last-good and do not convert killed work into PASS.
5. Native protected-storage probe: interruption after intent, each artifact,
   manifest, staging record, selecting record, selector/barrier and before
   terminal/receipt. Reopen verifies the actual custody/head/bytes, never replays
   effects, and returns exact terminal or explicit unresolved state.
6. Faults: sharing/antivirus lock, disk/quota/journal-full, partial write,
   readback/flush failure, root/selector identity replacement, unwitnessed suffix,
   same-volume/NTFS failure and cross-volume/network rejection. Preserve old
   completed snapshot bytes; retain poisoned cleanup owners for explicit retry.

Use `tests/blender/test_publication.py`, `test_publication_profiles.py`,
`test_publication_deadline.py` and `run_publication_recovery_probe.py` as the
behavioral templates, plus the core protected-storage tests. Passing those old
tests is useful regression coverage; it does not certify the new GT05 adapter.

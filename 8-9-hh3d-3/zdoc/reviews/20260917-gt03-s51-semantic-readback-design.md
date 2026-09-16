# S51 candidate semantic readback design

AUTHORITY=0; 2026-09-17; read-only source research during S50 freeze. No tests, engines, containers, or source edits. This is not GT03 acceptance.
Paths below are relative to `8-9-hh3d-3/studio/`. SHA256 identities are listed at the end.

The bounded route is one existing profile-validation run whose readback phase also computes the exact shared scene snapshot, followed by trusted manifest binding and immutable staging.
It does not require a second validation run merely because the manifest gains the observed revision: that manifest is not among the eleven engine-input files.
The present run still has three sequential Godot subprocesses, parse/import/readback (`godot-addon/linux_executor.py:192`); this proposal does not claim one subprocess.

Current evidence and the missing contract:

- `addons/hh_studio/scene_commands.gd:423` hashes JCS of `{nodes: rows}`; each row includes editable values, identity/order/owner, groups, and full supported stored properties.
- Lines 484–582 filter `PROPERTY_USAGE_STORAGE`, exclude exactly three existing fields, encode typed Variants/local BoxMesh recursively, and include GDScript source SHA256.
- `godot-addon/validation_bootstrap.gd:95,149` instead reports a narrower projection of a detached `GEN_EDIT_STATE_DISABLED` instance. It does not produce the editor snapshot.
- `profile_readback.py:45` allows 2e-6 vector tolerance. This establishes neither exact canonical-byte equality nor equal semantic hashes.
- `bundle_v2.py:189` copies the old `scene_revision` after script replacement; `create_bundle:177` explicitly treats observations as unverified.
- `validation_owner.py:301` binds receipts to the supplied manifest/project revision. Its registered receipt cannot safely be relabeled for a different final manifest.

Proposed shared serializer, without weakening the editor:

1. Extract the existing read-only snapshot/value encoding into a fixed `StoredSceneSnapshot` inner class in the already pinned `scene_commands.gd`.
2. This preserves the current eleven-file profile and twelve staged entries. A new standalone GDScript plus UID would require explicit profile/count/storage changes; do not add it silently.
3. The serializer accepts a root Node3D on the main thread, owns bounded scratch/error state, and returns plain state/revision; it has no command, save, UndoRedo, or editor-context override API.
4. Keep `SceneCommands.initialize:45`, `inspect:70`, and `_context:661` enforcing the real EditorInterface root, scene path, manager/history, generation, and editor hint before live delegation.
5. Preserve `_nodes` used by mutations and shared `_node_signature:584` / `_resource_signature:602` semantics; retain object maps only inside the trusted adapter, never in serialized output.
6. Preserve exact traversal (`get_children(true)`), stored fields, variant tags, limits, rejection rules, and JCS bytes. Do not substitute the helper's narrower rows or patch a previous snapshot's script hash.
7. The fixed readback helper loads only the hash-approved serializer/JCS already in the qualified project, applies it before freeing the detached instance, and emits state plus revision and schema identity.
8. Never instantiate SceneCommands with invented `_root`/`_initialized` state or bypass `_context`; the independent serializer grants observation only.
9. Keep the closed script grammar: native reads/instantiation may invoke script hooks on an expanded profile. No arbitrary methods, getters, @tool code, or caller-selected helper becomes eligible.
10. Bound the combined report before printing. The current 262144-byte snapshot limit plus existing report can exceed the 262144-byte stdout cap; reject oversized combined observations and retain existing hard caps.

Exact parity gate and engine identity:

- Detached readback and live editor states may differ in placeholder/script behavior, stored defaults, internal children, local resources, or floating-point values. This is a required native comparison, not an established defect or equality.
- Compare full canonical UTF-8 bytes on both actual platforms/builds, not only hashes or approximate vectors; preserve mismatch evidence and fail closed without rounding/dropping fields to force equality.
- Script-only replacement must change the revision through `stored.script.source_sha256`, even when a scene override masks a changed exported default.
- Candidate observation must identify `context_kind=isolated_candidate`, owned run/process, exact input identity, serializer schema/hash and engine build. It is not a live EditorPlugin observation.
- `publication_state_v2.py:186` currently names candidate fields `editor_session_id/editor_generation`; a trusted adapter/schema must distinguish isolated candidate context explicitly rather than forge live-editor identity.
- The Linux binary SHA is `8d106cbe6144c2dc7e881d61d2429c1a8a76e6b22ef48bd5e48dcf934953f71e`; Windows console SHA is `c8f0a6bc45a19b33541501e57f6f7cd972ab18453743266339d495cbbe846643`.
- Both lockfiles name source commit `ed1daf0bf001b61586d9930840f2f1394092c079`, but their executable identities are different. Retain validator/editor binary pins separately; a single `engine_sha256` cannot truthfully attest both actual processes.
- Until exact cross-context parity is observed for the eligible profile, keep this as candidate semantic observation and prohibit claims of live-editor adoption or public save completion.

Trusted binding order and one-run reuse:

1. Under the existing admission/lease/CAS context, construct pending candidate files and a content identity over exact eleven-file metadata, profile, source closure, serializer/JCS identity, and actual validator pin; exclude the final manifest/revision to avoid a cycle.
2. Validate those immutable bytes once. Require owned phase exits, complete bounded streams, checked cleanup, unchanged source/harness/binary, and exact before/after input and snapshot hashes before accepting any semantic observation.
3. Host-recompute JCS and SHA256 from the complete emitted state and compare the helper revision. Pin the schema; reject duplicate/missing fields, altered source, unsupported values, and truncated output.
4. Only the trusted issuer computes `create_bundle(same_files, scene_revision=observed_revision, engine_sha256=actual_validator_pin)`; a caller-supplied digest or callback cannot mint this binding.
5. Issue a new registered final receipt binding command/candidate/content identity, final manifest SHA/project revision, observed state hash, source closure, exact pins and owned run/evidence. Retain the original observation provenance; never modify today's receipt object.
6. Prepare/stage the twelve final immutable entries once, then read back all native descriptors/bytes/barriers and compare the eleven engine inputs plus exact new manifest. This requires no second engine run when every engine-input byte is identical.
7. The current S50 component demonstration stages before validation. Its already staged manifest must not be overwritten or its descriptor/receipt relabeled; production ordering needs the explicit pending-candidate-to-final-bundle transition.
8. `publication_state_v2.py:250` already permits the same exact candidate observation at STAGED→VALIDATED. Reuse this only through registered provenance plus content binding, not arbitrary caller JSON.
9. Ordinary v2 `caller_observations` remain inert codec data. Receipt provenance may confer trusted origin in the owner; do not claim every decoded v2 manifest has native observations.
10. After actual selection, obtain a new live EditorPlugin observation of adopted bytes/tree under its unchanged context guards, actual editor pin and newer observation identity. Candidate validation is not that adoption or ACK.

Focused future verification:

- Extraction preserves current editor snapshot/signature bytes and all rejection behavior; helper compilation/load works without a fabricated EditorInterface context.
- Windows live editor versus Linux detached canonical state: baseline, script-default replacement with/without scene override, nontrivial transforms, BoxMesh, null native properties, groups/metadata and boundary values.
- Rebinding consumes no second executor run; rejects changed script/UID/trusted file, changed pins/source, mismatched content identity, stale/wrong-command observation and copied/forged receipt.
- Final manifest changes with fresh revision while exactly eleven engine-input bytes remain equal; post-staging corruption/alias/barrier failure prevents progression; later editor adoption requires fresh evidence.
- Combined-report overflow, unsupported stored properties, failed cleanup, and cross-context mismatch all retain evidence and issue no accepted final receipt.

Primary documentation, consulted 2026-09-17 (API context only; actual pins require native proof):

- [PackedScene.instantiate](https://docs.godotengine.org/en/stable/classes/class_packedscene.html#class-packedscene-method-instantiate) documents edit-state modes and instantiation notification; detached instantiation is not live editor ownership.
- [Engine.is_editor_hint](https://docs.godotengine.org/en/stable/classes/class_engine.html#class-engine-method-is-editor-hint) distinguishes execution inside the editor from merely using an editor build.
- [Object.get_property_list](https://docs.godotengine.org/en/stable/classes/class_object.html#class-object-method-get-property-list) exposes usage flags and script-provided properties; shared filtering must preserve the current exact contract.

Inspected SHA256 identities (`godot-addon/` prefix unless noted):

- `addons/hh_studio/scene_commands.gd`: `ac4bf9e239b082efe9dd542f14c6cb8e202597bdfa1b8160e5da7905413aa0ea`
- `validation_bootstrap.gd`: `1e67888029b75945eb11d2730936e98a5028884d7746a4a2be9a7304cf5298cf`; `profile_readback.py`: `14e4eaef581b12797e59b90a3510f8b90938d390cc8c5fe32ab0d218a90c9c1c`
- `bundle_v2.py`: `2c5cdc71cdaf80f58bb93ec791e84bab8bd02cd4d9bdbd93d635db13583de62a`; `validation_owner.py`: `bd81cc5d6f06888c2825921296eeee06d0edfc13a881d1c13599de2941d514e4`
- `publication_state_v2.py`: `ae484cd1c7f5ccbe2b1739d3e7106c3fc38f188ac1d7812cd3444bbe5a4620e4`; `../protocol/jcs_godot.gd`: `61114350432d4ac6309f7f6f43d92c2940ef979ccea140a054d430948f15d2c5`

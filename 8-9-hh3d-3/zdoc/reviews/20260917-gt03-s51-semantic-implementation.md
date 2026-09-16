# S51 shared semantic observation — implementation evidence

AUTHORITY=0. No GT03 acceptance, independent-critic signature, selected-state claim, or public ACK.
Implemented against S50 checkpoint `c4fac2e6d8643da4c57c9049168bdd45460282b8`; 2026-09-17, Asia/Saigon.
Paths below are relative to `8-9-hh3d-3/studio/` unless marked as review evidence.

`SceneCommands.StoredSceneSnapshot.capture(root)` now contains the shared read-only full-property snapshot implementation.
The live adapter retains its original `initialize`, `inspect`, and `_context` bodies unchanged and delegates only observation/signature encoding.
A source comparison to `c4fac2e` confirmed all twelve moved traversal/value/signature/helper method bodies unchanged after removing one indentation level.
Capture additionally checks the main thread and a valid root. Object identity maps remain internal; the serialized result contains only state/revision.
The exact eleven-file qualified profile and twelve-entry immutable bundle remain unchanged in count; `scene_commands.gd` receives a new trusted content pin.

Fixed helper output is now `hh-godot-profile-readback-2`, with this extra `semantic` object:

```text
schema: hh-godot-semantic-snapshot-1
context_kind: isolated_candidate
serializer_sha256, jcs_sha256: exact approved project-source digests
state: {nodes: full shared stored-property rows}
revision: sha256:<SHA256 of exact JCS state UTF-8>
```

`profile_readback.semantic_state_bytes(semantic)` verifies the fixed shape/context and exact JCS hash; it returns canonical bytes, not process attribution.
`compare_observation` checks current serializer/JCS pins, scene structure/identity/owner/order, exact direct positions/mesh sizes, script identity and export values.
It returns `semantic_observed`, `semantic_revision`, and `semantic_state_sha256`; original byte/property comparisons remain present.
Historical v1 reports return false/None semantic fields. They cannot supply a fresh candidate revision to the owner's new final-binding path.
Existing tolerant binary32 comparison remains only in the old narrow input projection; semantic hashing and native parity have no epsilon or rounding downgrade.
Helper output is capped at 196608 UTF-8 bytes before print; existing executor hard stdout/stderr caps still apply. Oversized reports exit 44, without a usable observation.

Native evidence is `zdoc/reviews/20260917-gt03-s51-semantic-03/`.
Command: `python -B studio/tests/godot/run_semantic_probe.py --output zdoc/reviews/20260917-gt03-s51-semantic-03 --run-id GT03-S51-SEMANTIC-03` from `8-9-hh3d-3/`.
Executed frozen closure: `cd03592ff99c1d4b38055f04175a30383b6e1a449a55166600812fa77570fbdd`.
All six cases had byte-for-byte equal full canonical states and equal recomputed semantic revisions:

| Case | Exact shared revision |
| --- | --- |
| defaults_override | `sha256:97d020e63a03d5cdf99d1256feee64bdd8a8b20bf8111ea5f5be6321349832b8` |
| script_replaced | `sha256:117fe58159b2398e07abdaa1b2f9593922d86704dd9364d1c8cb33e3c24b7007` |
| transformed_box | `sha256:20d4f7f823728d3f998c5b167482eeb379d9a925e1429e96432d7f13158609ca` |
| typed_scene_override | `sha256:23604ba66b5e05b777ea3bcfdfbd1dc7abdc0424d1147b1e9b253a6adb21fb7e` |
| tiny_export | `sha256:78530c149c2e71bffdb195322099c8f157c954c3d880173884f3761882522f52` |
| nested_node | `sha256:9d2badafdd26498ad21baaa7b3a87c17cba90576f568fb95746b6ebdd8399eaf` |

The script-replacement case preserves scene bytes and its exported override, but changes the full revision through observed script source bytes.
Each Linux container recorded actual exit 0, stopped PID 0, owned removal, clean bounded streams, and unchanged inputs/snapshot/harness/binary.
Each Windows editor recorded actual target/wrapper exit 0 and drained Job; its observed PID matched the host's actual target PID.
Windows used the pinned GUI binary and a documented trusted plugin-config/probe overlay in a disposable project; the original addon, scene/script and remaining bundle bytes stayed identical.
The probe reached the original live EditorPlugin `inspect_scene` guards; it did not invent editor context for the isolated candidate helper.
The outer owned process exited 0; `snapshot_unchanged=true`, `windows_binary_unchanged=true`. No Godot/Blender process was observed after completion.
`origin_source_unchanged=false` records parallel coordinator edits/new tests; evidence applies to the immutable executed closure, not a later whole-tree acceptance claim.

Preserved earlier attempts: `semantic-01` rejected the changed lock hash before admission/container creation; `semantic-02` ran a clean matching baseline but the probe mistakenly looked for GUI output in stdout.
The corrected probe requires the explicit `editor-engine.log` marker, actual PID, complete clean process result and unchanged inputs; empty stdout alone is never failure or proof.
Actual raw replay data is `semantic-03/validation-run-semantic-baseline.json`, SHA256 `6ff0b00a34aa1f324df32b64df4b18a82cd042497ee210db088b3bf8051f8d4a`.
The original S49 fixtures remain unchanged and labeled historical. Current owner replay tests must use the new actual fixture, not repinned old observations.

Pure verification: 11 new semantic rejection tests, 13 existing profile comparisons, 5 existing profile preflight tests, 5 new mocked editor-capture rejection tests and 17 historical evidence rejections passed (51 total across focused invocations).
They reject missing/forged semantic context/pins, revised script/export/owner facts, tiny exact-hash differences, nonfinite values, wrong actual PID, duplicate/missing log markers, warnings and changed plugin config.
The new capture tests use explicit mock process facts and are not native evidence. No additional engine process was launched by those tests.

Final owned source identities (SHA256):

| File | SHA256 |
| --- | --- |
| godot-addon/addons/hh_studio/scene_commands.gd | `dbb2f3163c5442c9b5696490676ba533c4a1ca9aab7b4a089acaea321f27c042` |
| godot-addon/validation_bootstrap.gd | `efde8370a6157ed2f66544ee13b82ee2556b59130f5306e9e0774ed0e3be79a5` |
| godot-addon/profile_readback.py | `0236697c298c80a965d880087d6bc63b4378161d3e7142fe1b0c81b8e2e19c7a` |
| godot-addon/fixture_profile/source-pins.json | `ec0f7df9d3469948350d0af8c196bbb7307d8276634ad07fbc8c4f0c1d826654` |
| godot-addon/validator-toolchain.lock.json | `1441452e54279d94fe4a3bd946f2f494426179301bfe3202ae103b5fb469374d` |
| godot-addon/linux_executor.py (only two release-pin constants changed) | `6516bfb996d540532111160ac729f016247211a8f2de4129a6cac359228779e4` |
| tests/godot/test_profile_readback.py | `ab4a755fd2d26e606c8a43b388381142aa34a93751fa5bf97dbf129833864887` |
| tests/godot/test_semantic_readback.py | `93e50df7f0b7d1e1fe4250c287741cb1d99ee6147f6677eb952c4f1a22fc620c` |
| tests/godot/semantic_editor_probe.gd | `79f7e8ab354471301673a753694fde0db4c10e9d4189fd8b8cf73a855933fa9a` |
| tests/godot/run_semantic_probe.py | `294275d1bc8a673ee62c20f812e9d4c147c90d21cc94f8ab601b0f4c8bb01268` |
| tests/godot/test_semantic_probe.py | `9aedac637ba6c64f3b832bae16eff68eaa6153d34e131b6fb4918de2cc70c7bd` |
| tests/godot/test_profile_probe_evidence.py | `d3078cfeb67cccf521be59f3962c5851b8c270ff9833805e111979dc243df535` |

Remaining gates: final combined frozen suite/full editor mutation regression, registered native receipt/manifest rebind integration, and later actual selected-state editor adoption.
Six parity cases do not establish equality for every future engine build or expanded profile. Validator and Windows editor binary identities stay separate; no selected-state/public-save claim follows from this diagnostic.

# O2 authoring state — 2026-09-27

Authority 0. Separate branch: codex/o2-authoring-contract.
Merge only after GT-06 acceptance. Tools-plan O4 is authoritative; this file
tracks implementation gaps and does not create another acceptance plan.

## Verified candidate evidence

| Area | Source checkpoint | Evidence / limit |
| --- | --- | --- |
| Typed nodes / ClassDB | 95b89f78, b99d2640, ab9b7318 | Candidate validation and native readback |
| Signal, groups, InputMap | 9010633b, cbe48fa4, f7b8c858 | Revision binding, native do/undo/redo |
| Collision resources | ffbc251c, 51b8490b | Four shapes; proposal-bound readback |
| Scene instance | 26710772, 9192200f | Trusted PackedScene, transform, undo/redo |
| TileMapLayer | f6b2e17b | One-cell native atlas probe; not a playable map |
| 2D/3D animation | b4dfe799 | Validated proposals; six tracks; playback values |
| Gameplay shortcut | d0019fca, d9a99713 | Six typed effects; deterministic native dispatch |
| Declarative script profile | 5516db41 | Parse/attach/export readback; not gameplay scripts |
| Blender armature/action/keyframe | dbf6d0ba, 5c47c5ed | Native template geometry, undo/redo/reopen |

The combined static O2 suite last passed 151 tests. Godot native run
o2-native-20260927-33 passed 396 checks with host/wrapper exit 0, clean logs,
verified owned tree and unchanged source/project. Frozen 20-file closure:
278df6de3137f74fb9bf2f536e4c247d1637a89c63ddd8b68f02f4bca9478d43.
Failed runs -30 and -32 remain preserved; no retroactive PASS.

Blender o2-blender-native-20260927-17 passed 18 checks, actual native and
reopen exits 0, verified tree and unchanged source/project. Five-file closure:
eef74f5d3f39579887e05fdfec96396b4915ea9692c821127093982c8188b0b5.
Archive and executable match Blender 5.2.1 toolchain.lock.json.
Legacy raw remains in its original local worktree directories; new evidence
goes into .local with ZIP and manifest hashes per O4.4.

Current terminology is **PATH_ISOLATION**, not AUTH_ISOLATION. These probes
isolate paths and disposable projects; they do not prove OS sandbox/AUTH-05.
Historical raw labels/hashes are not rewritten.

## 2026-09-27 guarded execution checkpoint

The fixture probe `o2-sandbox-20260927-04` completed with host exit 0 and
observed all 9/9 selected fixtures. Its frozen source closure is
`f1bc187653c3036731c3e48cf8173fc2caf31e3ea7d17dc69e3d6efcb86d1030`.
The scoped regression command completed 109 tests with exit 0. The package
manifest is `studio/.local/reviews/o2-sandbox-20260927-04-package-manifest.json`
(`0dce20f99a2d4f1033636d363337baafcbbb2c688df9a15e02e8ce53dafb0f6d`); the
raw/evidence package is
`studio/.local/reviews/o2-sandbox-20260927-04-package.zip`
(`108ab4ae469a0028121cb5f31d9cfb1e68640e399cb07546b99fa6675f6d3de0`).

This is a diagnostic checkpoint only: `AUTHORITY=0`, `public_ack=false`,
`sandbox_acceptance=false`, and `validation_attribution_proven=false`. It does
not close AUTH-05, publish a gameplay-source capability, or unlock GT-06.
Guarded modes are separate from the existing stock executor modes because
stock Godot startup invokes `xdg-user-dir`; that startup diagnostic and its raw
error remain in the package rather than being relabeled as a clean run.

## Fixture-driven gap queue (O4.5)

### 2026-09-28 gameplay-source checkpoint (native follow-up pending)

The contained diagnostic now has a separate byte-envelope profile and a pinned
parent driver that runs parse, editor import and play under one wall deadline.
Byte admission does not prove syntax, typing, dependencies or safe publication.
The existing validator modes and the six-effect vocabulary remain unchanged.

`o2-gameplay-source-20260928-03` is **3/4 observed**, not an all-fixture PASS.
Frozen closure: `ba0af2d6b2280eed44c535e9b8bc915824029e0665dfe68413be762ad89ee948`.
The play, spawn and boundary cases exited 0; the busy case exited 124 during
import, before `HH_PROBE_BUSY_ENTERED`. All four containers were removed.
The probe's outer tool handle is gone and its actual outer exit was not
captured; the earlier chat claim of outer exit 0 was unsupported. Raw/capture
is retained unchanged under `studio/.local/reviews/`.

Static follow-up binds the entire inspected command, entrypoint, container ID,
read-only harness mount and bootstrap/profile hashes to trusted source. Phase
and guard events must be in exact order. Only the pinned fixture-specific
startup/spawn/network diagnostics are explained; extra errors/warnings/leaks
fail the fixture check. Explained diagnostics never become a clean process,
public ACK or sandbox acceptance. No archived evidence Python is executed by
the verifier. The busy fixture now has one 12s diagnostic wall budget to cover
the observed ~8s parse/import/play startup and reach its loop before the CPU
limit. This is unverified natively and changes no GT-06 timeout or OS limit.

Pure evidence unit tests: **28, actual exit 0**, 0.222s; no Docker or engine.
Receipt: `studio/.local/reviews/o2-gameplay-evidence-20260928-01/exit.json`.
Log SHA256: `adda88037d5bc0608ccc2a4561833825540884fe344535d12933c95196d0dbad`.
This focused result overlaps prior test counts; do not add them together.

Next outside formal measurement: freeze new source, run the four native cases
with a new ID and persist the outer process exit; add syntax/type negatives;
then seal ZIP/member hashes before committing this milestone. No native rerun,
package compression or heavy suite runs during GT-06 formal measurement.
AUTH-05/public gameplay-source remains incomplete; all candidate evidence is
AUTHORITY=0. No GT-06 or AUTH checkbox changes follow from this checkpoint.

Lessons: budget the entire multi-phase diagnostic, require proof that a hostile
callback entered, and distinguish child exits from the probe runner's exit.
Do not infer all-fixture success from clean cleanup or partial success.

| Fixture requirement | Existing reusable candidate | Remaining proof / implementation |
| --- | --- | --- |
| 2D platforms, player movement, camera | TileMap, CharacterBody2D, InputMap, animation | Adapter transactions; real collision/input replay |
| Projectile, pickup, health, defeat/respawn | Scene instance, Area/CollisionShape, signals | Typed gameplay GDScript, validation and runtime postconditions |
| Simple bot and win/loss loop | Six-effect shortcut only | Fixture-specific typed GDScript; seeded repeatable play |
| HUD, audio, pause/restart | Typed nodes and GT-06 Play controls | Public adapter integration and actual fixture E2E |
| 3D avatar from Blender | Armature/action/keyframe and GT-05 pipeline | Geometry/material/UV -> GLB -> Godot on authored avatar |
| 3D movement, follow camera, two interactions | CharacterBody3D/Camera3D/Area candidates | Typed gameplay source, collision/input and UI evidence |
| 2D sprite sheet | No completed candidate evidence | Blender render/export and Godot import |
| Both: save/reload, ACK, lease/recovery | Existing accepted narrow adapters | AUTH-02..04 integration for new candidates |
| Both: hostile source execution | Existing GT-03 Docker executor only | AUTH-05 gameplay profile and OS-observed hostile tests |

Next: reuse linux_executor.py for bounded headless gameplay validation/replay.
Its existing narrow fixture allowlist must not simply be switched off.
Writing outside the root, process spawning, networking and infinite-loop
tests need observed OS restrictions/termination, not just parser rejection.
Docker availability alone is not AUTH-05; a container PASS does not make
arbitrary native Windows gameplay code safe.

Freeze the six-effect DSL vocabulary. Do not invent more catalog features
unless one of these two fixtures needs them. Host-windowed Play only receives
the exact source/dependency closure admitted by AUTH-01..05.

No engine run during GT-06 formal measurement. Static preparation is allowed.
This branch must not change plan or AGENTS.md again. Existing governance
differences must be excluded/reconciled when integrating code after GT-06.

### 2026-09-28 gameplay-source follow-up (run05)

The fresh native diagnostic `o2-gameplay-source-20260928-05` observed all four
fixtures (`gameplay_source`, `gameplay_source_spawn`,
`gameplay_source_boundary`, and `gameplay_source_busy`). The probe runner's
captured host exit is **0** and each owned container has a confirmed removal
inspection. The busy fixture reached its intended loop and produced the bounded
diagnostic exit; this is an observation of the watchdog path, not a product
failure. Source closure is
`485c3dbf98592db3945edc6c08bf08b245e56d589fca09b3e07323af1bc8e822`.
Raw evidence remains under
`studio/.local/reviews/o2-gameplay-source-20260928-05/` and is not rewritten.

This improves the earlier run03 checkpoint: the outer exit is now captured,
the spawn and busy cases are interpreted from the exact transcript, and
cleanup is confirmed after removal. It still remains `AUTHORITY=0`:
`public_ack=false`, `sandbox_acceptance=false`, and
`validation_attribution_proven=false` for every case. It does not close
AUTH-05 or alter GT-06. The bounded container probe demonstrates the guarded
diagnostic path only; it is not evidence that arbitrary gameplay source is
safe for publication.

The focused static regression suite now passes **122 tests**, actual exit 0 in
16.323 seconds. Receipt:
`studio/.local/reviews/o2-gameplay-evidence-20260928-03/exit.json`; log SHA256
`1f938ec83aa5b406a8d76a12d5f73c5042eb4c0ad52c065081f480ef5ca7afcd`.
This count overlaps earlier checkpoints and must not be added to them.

Remaining O2 work is unchanged: add syntax/type/dependency negative fixtures,
prove source-closure/public adapter integration, and obtain the owner critic
package after GT-06. Do not run another native gameplay probe during formal
measurement; preserve both run03 and run05 as separate historical evidence.

The static negative-fixture gap now has a separate `dependency_error` case
(missing `res://scripts/missing_dependency.gd`) alongside the existing syntax
and typed-assignment failures. The catalog assertion and related evidence
suite pass 62 tests with actual exit 0 in commit `fa392dab`; this is static
coverage only and still requires a fresh native run after GT-06 formal work.

### 2026-09-28 dependency-closure static checkpoint (superseded wording)

The earlier f29fdbb7 checkpoint described a bounded
`validate_dependency_closure` helper. That description is historical and is
superseded by the correction below; it must not be read as proof that a regex
walk established a Godot dependency closure.

Pure static checks passed with actual exit 0: gameplay contract/edge/behavior,
dependency profile, probe evidence, sandbox policy, and guarded executor
tests (42 tests); the focused profile/executor/evidence/sandbox/guarded set
passed 48 tests. No Docker, Godot, Blender, network, or evidence rewrite was
performed. This closes only the dependency-admission static gap; public
adapter integration and AUTH-05 acceptance remain open.

The gameplay executor now invokes the corrected source-bundle inventory before
admission, so the native diagnostic cannot silently bypass the bounded input
boundary. This source change invalidated earlier native closure hashes; a
fresh four-fixture native run was required and is recorded below.
The focused pure suite was rerun after integration: 66 tests, actual exit 0,
2.0 seconds, with no engine, Docker, network, or generated evidence.

### 2026-09-28 dependency-claim correction

Review of the f29fdbb7 helper found that its regex walk was too strong to call
a Godot dependency-closure proof: it could miss scene ext_resources, UID and
dynamic loads, and could mistake comments or strings for references. The
helper is now `validate_source_bundle`. It binds an exact UTF-8 byte inventory,
canonical `scripts/`/`scenes/` paths, size limits and SHA-256 values, while
returning `dependency_closure_verified=false`. The executor still validates
the bounded bundle before Docker admission; no native result or old raw file
was rewritten. The profile pin and lock manifest were reminted for this source.

The former static tests that claimed missing/unreferenced inference were
replaced by regression tests proving the honest boundary, including rejection
of `res://` aliases and dot segments. Actual Godot import/runtime dependency
closure, scene-resource coverage, and AUTH-05 remain open work; this repair
does not create an acceptance claim.

### 2026-09-28 gameplay-source native checkpoint (run08)

After the profile-pin repair, the four bounded fixtures ran against the pinned
Godot Linux binary with a captured outer host exit of **0**. The ordinary,
spawn, boundary, and busy-watchdog cases all recorded `fixture_observed=true`;
the busy case ended with the expected supervisor exit 124. Source closure is
`36e4016e868097008272d27e0e9894232c5dd664a7e6df61a68caf810543b23c`, with 219
frozen source files. Each case has host/container exit records, closed zero
Job handles, confirmed owned-container removal, unchanged inputs, and the
matching source/profile hashes. The run was independently re-read from raw
evidence before packaging.

Package ZIP SHA-256 is
`461ecee7dbe57fc49c7bbe39e459ac8259d02a9223c90547d4e2d879dffcee4b`; package
manifest SHA-256 is
`936f8428307d0a025f5a1107b7d3efe49d05dab4808da12e6d8d67d07945fc35`.
Raw evidence remains in `studio/.local/reviews/o2-gameplay-source-20260928-08`.
This is still `AUTHORITY=0`: `public_ack=false`, `sandbox_acceptance=false`,
and `validation_attribution_proven=false`. It does not close AUTH-05, prove a
general Godot dependency closure, or change GT-06.

### 2026-09-28 gameplay-source parse rejection checkpoint

Three new gameplay-source negative fixtures (`gameplay_syntax_error`,
`gameplay_type_error`, and `gameplay_dependency_error`) ran in native run
`o2-gameplay-rejection-20260928-01`. The host exit is **0** for the campaign;
each fixture has an actual host/container exit of **45**, closed Job handles,
confirmed owned-container removal, and `fixture_observed=true`. The transcript
contains only `parse` plus the OS guard and parse-end failure; no `import`,
`play`, or probe callback is accepted. This proves fail-closed phase ordering
for these pinned diagnostics, not arbitrary-source safety or public ACK.

Source closure is
`f56bd4c184c375259352723bd6a3e56cd247f2145f3d6147e7d5126b1d120545`.
Package ZIP SHA-256 is
`49afc8a23cea48542fa7f541d4c8b78a9c8f2d1a0da368da2d68e1cf38acbc25`; package
manifest SHA-256 is
`08505a94646ceff29f75950628e175c1f61c48bc03824891ed5f27b4a5c55958`.
Raw evidence remains under `studio/.local/reviews/` and all claims remain
`AUTHORITY=0`; AUTH-05, adapter integration and GT-06 are open.

### 2026-09-29 static envelope hardening (formal06 outside measured source)

The gameplay-source byte envelope now rejects Windows device names, alternate
data-stream syntax, control/NUL bytes, trailing dot/space names, non-NFC
components, and case-folded path aliases. This closes a cross-platform path
ambiguity in the bounded inventory before Docker admission; it does not infer
Godot dependencies, prove a sandbox, or grant public ACK. Focused pure profile
tests pass **9 tests**, actual exit 0 (`python -B -m unittest
studio.tests.godot.test_gameplay_source_profile`). No Godot, Blender, Docker,
network, or measured GT-06 source was run or changed. A fresh native O2
diagnostic remains required after formal06 before any broader claim.


### 2026-09-29 bounded scene/script inventory and native follow-up

The gameplay-source executor now admits the exact bounded inventory under
`scenes/` and `scripts/`, while still requiring `fixture.tscn` and
`fixture_actor.gd`. Every admitted byte is read with the profile limits and
bound through `validate_source_bundle`; the implementation still reports
`dependency_closure_verified=false` because it does not infer Godot's complete
scene/UID/dynamic-load closure. The runner now binds extra fixture files into
raw input and observation manifests, so a multi-file case cannot pass by
checking only the primary script.

Focused static regression tests passed **68 tests**, actual exit 0, after the
executor/profile pin and lock were reminted. Native campaign
`o2-gameplay-source-20260929-02` ran five selected fixtures with the pinned
Godot binary and Docker executor; the outer host process exited 0, all five
fixtures were observed, source remained unchanged, and all owned containers and
handles were released. The cases were the ordinary gameplay source, a
scene-plus-shared-script multi-file case, spawn observation, path/network
boundary observation, and the busy watchdog. Frozen source closure is
`f849eff75ef72ff9cbdf66d0680a8ca8b537c2b2533a30e82ee05728f60c1872`. The raw
package has 460 members; ZIP SHA-256
`66e8cd278edb8590c4b99be18520a155903270415caf23a130c34c23546aef98`; manifest
SHA-256
`d3d9b8f2cb24803e1399e6ae0a59ed9e2006e311ca4bd894518a6c1438ea666c`.

The prior 01 raw package remains unchanged as historical evidence; 02 was
reminted because the capture now states `authority=0` explicitly and therefore
has a different frozen source closure.

This remains `AUTHORITY=0`: no public ACK, sandbox acceptance, or complete
Godot dependency-closure proof follows from this diagnostic. The native run
revalidates bounded admission and lifecycle behavior only. Remaining O2 gaps
are the real fixture gap table, public adapter/save-reload integration,
AUTH-05 review, and Blender GLB/sprite-sheet pipeline checks. Do not merge this
branch or open GT-07 before GT-06 is accepted.

### 2026-09-29 secondary-script parse hardening — corrected evidence

The earlier run05 note claiming a generated preload wrapper had proved every
secondary script is **superseded and withdrawn**. Godot's `--check-only`
wrapper could report errors from a preloaded module while the wrapper itself
returned zero and continued to import/play. Its raw directory and package stay
unchanged as historical evidence, but it is not parse-rejection proof. The
preserved negative attempt `o2-secondary-rejection-01` records this flaw with
zero accepted fixture observations; it must not be promoted by a banner or
prefix.

The repair invokes the pinned Godot binary directly with
`--check-only --script res://scripts/<validated-module>.gd` once for the primary
entrypoint and then each sorted secondary script. A nonzero child exit stops
before import/play. The path is selected only from the exact admitted inventory;
the sandbox rejects caller-supplied aliases and traversal. Docker limits,
profile deadlines and GT-06 gates were unchanged. Source files were normalized
to the repository LF contract and the lock pin was reminted before the fresh
run.

Fresh native run `o2-direct-parse-20260929-05` observed **11/11** fixtures with
captured outer exit **0**: four ordinary gameplay cases plus the busy watchdog,
three secondary-script syntax/type/dependency rejection cases, and three primary
syntax/type/dependency rejection cases. Each rejection had actual host and
container exit **45**, parse-only transcript with no import/play callback; the
busy case had the bounded diagnostic exit **124**. Every case retained exact
input/snapshot hashes, closed Job handles, removed owned containers and an
unchanged source tree. Frozen source closure is
`5cd33be9308406a48c9e335a75bb2af5349597bf2072ed4615678de23f0b39f6` with 219
files. The sealed raw package has 750 members, ZIP SHA-256
`075c843558ff10056cf2b9e10bfc9b18aa63d96f4d9d03e073280b10ea494b39`, and
external manifest SHA-256
`e13c0ffe25f4b4228bf846c7f4cdfc8721c502947bc2fd518c2308fa80fd5f8b`.
The initial missing-binary attempt `o2-direct-parse-20260929-04` is retained
as an actual exit-1 diagnostic and is not included in the success claim.

The focused pure suite remains **79 tests**, actual exit 0. This checkpoint
proves direct parse-phase coverage and lifecycle evidence for these fixtures;
it does not prove arbitrary Godot dependency closure, AUTH-05 OS isolation,
public adapter/save-reload integration or a publishable gameplay capability.
`AUTHORITY=0`, `public_ack=false`, `sandbox_acceptance=false`; GT-06 remains
unaccepted and this branch must not merge or open GT-07.


### 2026-09-29 typed gameplay fixture checkpoint

Two fixture-scoped typed GDScript cases now run through the same guarded
`gameplay-source` profile. `gameplay_source_arena_2d` exercises a deterministic
health, pickup, projectile-hit, bot-defeat and win transition;
`gameplay_source_room_3d` exercises typed avatar movement, camera-follow state,
two interactions and UI visibility. The evidence parser requires the exact
JSON state and the complete parse/import/play transcript, so a forged or partial
marker is rejected.

Native run `o2-fixture-state-20260929-01` observed **2/2** cases with captured
outer exit **0**, actual child/container exits 0, closed Jobs, removed owned
containers and unchanged source. Closure is
`6e542b9d0a40c1bd734666854ae269b327e1d76f62f7047e5fa8e0049c4e144b` (219
files). Sealed ZIP has 317 members, SHA-256
`bfb7515be963d09013ab9cb1fa9da516aa4cc54a67ab998b6bb4d564a0b4a0d5`; external
manifest SHA-256 is
`9defe8a5d489edbf09e7cde2fae6913ddb4510a8beb33584a3386eda73f30ec3`. Focused
pure regression now passes **80 tests**, actual exit 0.

These are deterministic logic fixtures, not complete playable mini-games: they
do not prove collision/input replay, Blender asset import, save/reload ACK,
AUTH-05 acceptance or a public gameplay-source capability. `AUTHORITY=0` and
GT-06/GT-07 status are unchanged.


### 2026-09-29 Blender native revalidation

The current O2 source was revalidated with the pinned Blender 5.2.1 executable
in `o2-blender-native-20260929-18`. Native authoring and reopen both exited 0;
all 18 checks passed, source snapshots matched the live five-file closure
`eef74f5d3f39579887e05fdfec96396b4915ea9692c821127093982c8188b0b5`, and the
sealed package has 17 members. ZIP SHA-256 is
`ee9d18a3293e275b3e59334993dcbd92b3762da3f11352588d3b8b1e064908b9`; external
manifest SHA-256 is
`d01f6f7f7caf8d23c573f06c7725d7908c205f9e5feb858192c23cf03b37ecfd`.
The run remains `AUTHORITY=0`: it revalidates armature/action/keyframe native
readback and reopen only. Geometry/material/UV-to-GLB, sprite-sheet export,
Godot import, and the two-fixture end-to-end content loop remain open.


### 2026-09-29 Blender geometry/UV/material → GLB checkpoint

The Blender probe now creates a four-vertex authored quad with a UVMap and
Principled material, exports `avatar.glb` through Blender's pinned glTF exporter,
and checks the mesh/material/GLB again after reopening the saved `.blend`. Two
failed attempts are preserved: run19 caught an incorrect `diffuse_color`
assertion, and run20/run21 caught Blender 5.2 `use_nodes` deprecation warnings
that correctly made the strict log gate fail. The repair reads the shader's
Base Color directly and avoids the deprecated property.

Fresh run `o2-blender-asset-native-20260929-22` passed **22/22** checks with
native and reopen exits 0, clean owned trees, unchanged source and
`asset_reopened=true`. Frozen closure is
`187f9c6ed916803554c3242752b84d41e4eca38ebf3fc2cecbe165c3da47b396`. The GLB
is 1,792 bytes with SHA-256
`5f78b1d15a8391c2a77fc3dd87d9afe69909c99c4703e78e33196b60b5b13054`; sealed
package ZIP SHA-256 is
`eb83daa7e6d16f5884888909d51597b6c6ca8204048a8947a4e59ad879754547`, and the
external manifest SHA-256 is
`49d85c24e32603a6dd23c8cbbaa125205d2fc01cf9f964e2dfc3d52b0bd19f52`.
This proves Blender-side geometry/UV/material and export/reopen only. Godot GLB
import/readback, sprite-sheet rendering, and full two-fixture content E2E remain
open; `AUTHORITY=0`.


### 2026-09-29 Blender GLB → Godot import/readback checkpoint

Disposable run `o2-blender-godot-import-20260929-03` imported the GLB produced by
the pinned Blender run into the pinned Godot 4.7.2 Windows console binary. The
editor import exited **0**, then the declared main scene instantiated the
imported asset and read back **4 vertices, 4 UVs and a StandardMaterial3D** with
the expected base color; the runtime exited **0** and emitted the structured
`HH_GLB_IMPORT` record. The run ended with no owned process or Job residue and
the source project was unchanged.

The Godot executable SHA-256 is
`c8f0a6bc45a19b33541501e57f6f7cd972ab18453743266339d495cbbe846643`; the GLB
SHA-256 remains
`5f78b1d15a8391c2a77fc3dd87d9afe69909c99c4703e78e33196b60b5b13054`. Raw
evidence is sealed in `o2-blender-godot-import-20260929-03-sealed.zip` (ZIP
SHA-256 `8b16238f992416425aad7bfbf3e581f196028af497fbe73159027ea1c4953258`)
with external manifest SHA-256
`1659b759620d063bf9b9c1d3c82a7541971b6c134a62a7df1db3941026992adf`.
The earlier run01 direct-script attempt is retained as a harness failure and is
not included in the PASS claim. This checkpoint proves asset import/readback
only; sprite-sheet rendering, gameplay fixture E2E, save/reload ACK and AUTH-05
remain open. `AUTHORITY=0`; GT-06 is still unaccepted.


### 2026-09-29 Blender sprite-sheet → Godot import checkpoint

The pinned Blender probe now renders a deterministic four-cell 128×128 PNG
through Blender Workbench, saves it beside the authored GLB, and verifies the
image dimensions after reopening the `.blend`. Run
`o2-blender-spritesheet-native-20260929-23` passed **24/24** with native and
reopen exits 0; source closure is
`ce3b08187196efe1d56e343a7ba27bc2b55c8fdcc09dcf55b88a0e02e7a17f84` and the
sheet SHA-256 is
`135c89ba646d3ee77ab7efddb890d2f8871cf936eefd035c3793c93e7eaed708` (14,635
bytes).

Disposable Godot run `o2-blender-godot-import-20260929-07` imported both the
GLB and PNG with the pinned 4.7.2 Windows console binary. The editor and main
scene exited 0 with no warnings; runtime readback observed the expected 4
vertices, 4 UVs, material, and 128×128 opaque sprite pixel. The combined raw
package is `o2-blender-spritesheet-godot-20260929-01-sealed.zip` (43 members,
ZIP SHA-256
`3d50b2ab48d637c6d0b349ce3664330d37cda0b14ad9649744b097266fd4c4e7`, external
manifest SHA-256
`e9697c2799083877b77716764e0bfced7021c851e2df74547345e98bcc6b939d`).
The earlier warning-producing run05 and harness-fix attempts remain raw and are
not used for the PASS claim. This closes only the Blender asset → Godot import
readback path; sprite animation timing, gameplay integration, save/reload ACK
and AUTH-05 remain open. `AUTHORITY=0`; GT-06 is still unaccepted.

The PNG is deliberately evidence of a render/import path only: the current
four-cell diagnostic camera also captures the authored quad, so it is not being
claimed as a production sprite atlas. A future sprite fixture must isolate the
render layer and verify cell boundaries before any art-quality claim.


### 2026-09-29 physics/input fixture diagnostic — bounded, not promoted

The new `gameplay_arena_physics` fixture exercised a real Godot
`CharacterBody2D`/`StaticBody2D`/`Area2D` scene through the guarded Docker
executor. The child reached 150 physics ticks and emitted actual input events,
pickup collection, jump/apex/landing, projectile hit, bot defeat, wall
contacts, camera-follow and HUD state; the container exited 0 and all owned
handles/containers were cleaned. Raw evidence is sealed in
`o2-arena-physics-20260929-03-sealed.zip` (275 members, ZIP SHA-256
`287a2c21cdd8bd9ced3ee2960b7f197d7435e38988cbe7af6b5a93adbcb668ab`, manifest
SHA-256 `710e4d50be9073c281e91980f59422fea5a9b5a453cdc5ccef8789d9f901bdd2`).

The outer verifier exited **1** because its frozen transcript expected the
input marker's tick instead of Godot's next-tick `just_pressed` observation;
that is a verifier repair, not a promoted PASS. The post-run source repair now
models the one-tick boundary and rejects missing/duplicated input, early finish,
wrong wall/contact telemetry and bool-for-int substitutions. O3's three-attempt
diagnostic budget is spent, so this branch does not rerun the native case under
the repaired verifier until a later owner-approved checkpoint. `AUTHORITY=0`;
this is not AUTH-05, GT-06 or GT09 acceptance.

### 2026-09-29 isolated sprite atlas repair

Adapter integration is still open. The attempted wrapper around the inert
fixture selector was removed before commit: serializing source into fixture
JSON does not integrate the existing Godot publication/editor owner. Future
work must use that actual adapter and retain its save/reload, fencing and
recovery contracts; test counts from the discarded wrapper are not progress.

The Blender sprite diagnostic was repaired by rendering in a separate scene so
the authored GLB quad cannot cover the atlas. The native pinned run
`o2-blender-spritesheet-native-20260929-24` passed with native and reopen exits
0, clean owned trees, four colored 48×48 interiors, transparent gutters,
and a scene-isolation check. The pixel oracle rejects the prior gray-quad
overlap, missing/swapped cells and non-finite channels. Raw evidence is sealed
under `studio/.local/reviews/o2-blender-spritesheet-native-20260929-24`; it has
20 members, ZIP SHA-256
`9903160cdc7f6bebc97fa7590e99b8188d4ed614cd3a782726f1f32240f216f8`, external
manifest SHA-256
`876a8075cf232da0959e8ce6797e1b145087b1793d1938302d1af5a7f5f4c02a`, and
sheet SHA-256
`9a83eedab1d4e05d20d8976db0ed2e256669fc17d2ab78b048e522e4c15c481f`.
Run24 did not persist a fresh resource preflight; keep it as limited diagnostic
evidence, not a formal or preflight-qualified result. Future native runs need
a fresh observed preflight before dispatch.
This closes only the isolated Blender render/readback defect; Godot atlas
animation timing, gameplay-source dependency closure, native gameplay E2E,
AUTH-05 and public publication remain open. `AUTHORITY=0`; GT-06 is still
unaccepted.

The follow-up Godot atlas run `o2-sprite-atlas-godot-20260929-02` used a fresh
O4.1 resource observation (available 8.09 GiB, commit 73.5857%, no foreign
engines) and the pinned Godot 4.7.2 console binary. Import, author and a fresh
process reload all exited 0 with clean owned trees and no unexplained stderr.
The author phase created four `AtlasTexture` regions and an 8 FPS looping
`AnimatedSprite2D`; the reload phase read the saved `SpriteFrames` and scene,
then observed 100 fixed-FPS ticks, the real frame sequence, pause at ticks
38–49 and resume at tick 51. The first run was retained as a harness failure:
Godot correctly recorded the resume call at tick 50 without advancing a frame,
while the verifier had expected advancement in that same observation. The
repaired verifier models this boundary and has seven pure tests including
negative traces. The sealed follow-up has 35 members, ZIP SHA-256
`b2047720296c3de9f240668ac515dfac39cc0263ca6b6984fea12e90c5a9ddde`, external
manifest SHA-256
`20703eba22a4c3b6295c0773f2d6e1a5ff7aa97a1ba1277de2ee81f770b76b8b8`, result
SHA-256 `ee3c990d2a2bce5dd3182b0666c1f14e01974552b08b88bf7c2ba59f1438996b`,
and source closure
`9866af853cbfb6876f204baccd4a8ab616ec3680829f14f344c924f72fd15b51`.
This closes the Blender atlas → Godot import/save/reload/animation diagnostic
path only; it does not close gameplay-source adapter integration, AUTH-05,
GT-06 or public ACK. `AUTHORITY=0`.

### 2026-09-29 AUTH-05 gameplay-source executor closure diagnostic

The first four-fixture dispatch `o2-gameplay-source-native-20260929-04` is retained as a host-preflight failure: the pinned Godot 4.7.2 Linux binary was absent from the local tooling root, so the executor stopped before Docker (`EXECUTOR_HOST_FileNotFoundError`, no command host/container evidence). The binary was restored from the declared official archive; archive SHA-256 is `cadd3204e728a35d3f13adb7fd0d7902636b79f6b95c40c265eb73b6c35329e4` and executable SHA-256 is `8d106cbe6144c2dc7e881d61d2429c1a8a76e6b22ef48bd5e48dcf934953f71e`.

Fresh run `o2-gameplay-source-native-20260929-05` then exercised `gameplay_source`, `gameplay_source_arena_2d`, `gameplay_source_room_3d` and `gameplay_source_spawn`. All four child/container exits and host attach exits were 0; each had `fixture_observed=true`, supervisor binding verified, Job active count 0, owned container removed, input/snapshot/binary hashes unchanged, no timeout, no stream errors and no retained owner record. The frozen source closure is `c96be8d92cd9b2573663a1dbfc0121dbc8a26ee2c784df20653347024b91344b`; 62 focused pure tests pass with exit 0. Raw evidence is preserved under `studio/.local/reviews/o2-gameplay-source-native-20260929-05`; sealed package has 417 members, ZIP SHA-256 `6a6dc31e7c0193535ff6874c298d4182c930192e126f853eb2ad412e5eb00eb0`, external manifest SHA-256 `261b64f2007a5aa2210c405af8bd4f3f937eb672af49c5778a688c95f3726124`.

This is AUTHORITY=0 diagnostic evidence that the bounded Docker executor can validate the four gameplay-source fixture profiles and clean up its owned process/container. It does not prove OS sandbox acceptance, real Godot gameplay authoring, adapter publication/save-reload ACK, or GT-06 acceptance. `GT07` remains unopened and O2 remains unmerged.

### 2026-09-29 AUTH-05 source-closure negative diagnostics

A separate fresh run `o2-gameplay-source-native-20260929-06` exercised the multi-file gameplay fixture plus the three negative profiles for an unused syntax error, typed assignment error and missing dependency. All four observations were bound to the same frozen source closure `c96be8d92cd9b2573663a1dbfc0121dbc8a26ee2c784df20653347024b91344b` and reported `fixture_observed=true`; the multi-file case exited 0, while each intentional engine rejection exited 45 in both the container and host attach record. Every Job had active count 0, every owned container was removed and input/snapshot/binary hashes remained unchanged. The expected rejection rows retain `EXECUTOR_ENGINE_OR_HOST_NOT_CLEAN` because the child deliberately exits nonzero; this is not relabeled as a clean process.

The sealed raw package has 427 members, ZIP SHA-256 `d01085ee12b53f3cd243f28a930719a3a19b6ef2a9ca8941aebb6c3eebb10b82`, external manifest SHA-256 `c37e607dc440f1ce2df20844679eb962ff25066334a3ab1066bc0e7b7d71ea42`. This extends native evidence for bounded source inventory and rejection attribution only. It does not prove Godot's complete arbitrary dependency closure, OS sandbox acceptance, adapter publication/save-reload ACK, or AUTH-05/GT-06 acceptance. `AUTHORITY=0`; GT07 remains unopened.

### 2026-09-30 gameplay-source publication adapter (static lifecycle milestone)

`studio/godot-addon/gameplay_source_owner.py` now binds the existing
`PublicationSession` grant/lease/fencing lifecycle to the bounded
`gameplay-source` executor. A candidate is staged as an immutable revision,
validated by the real executor before selection, selected through an atomic
`CURRENT` pointer, re-read by hash, and appended to a durable journal. Exact
command retry is idempotent, digest conflict is rejected, stale project
revisions are rejected before native execution, and `reopen()` restores only
the selected revision with no old bearer or lease. The receipt is explicitly
`READBACK_ACK` with `readback_ack=true` and `public_ack=false`; it is a
candidate adapter observation, not a public capability or GT06 evidence.

The focused pure suite (`linux_executor`, source profile, sandbox, probe
evidence, and the new adapter tests) passed **66 tests**, exit 0. A first
native adapter attempt was retained as a rejected input/watchdog diagnostic;
the repaired fixture then ran as
`o2-gameplay-source-adapter-native-20260930-04`. Its multifile GDScript and
PackedScene source reached real Godot parse/import/play, with child/container
and host exits 0, Job active count 0, owned container removed, unchanged
input/snapshot/binary hashes, and an atomic selector plus durable journal
`READBACK_ACK`. The exact runtime closure is
`69e72c10f71e0c092717a98abcc9c8bac65c75c8669326edff31618f839ccfdc`; raw
evidence and `adapter-closeout.json` remain under
`studio/.local/reviews/o2-gameplay-source-adapter-native-20260930-04/`.
The receipt still has `public_ack=false` and this is one fixture-backed
candidate run, not AUTH-05 acceptance or GT06 evidence. Arbitrary dependency
closure, hostile sandbox acceptance, owner critic review, public ACK, GT-06
acceptance, and GT07 remain open.

### 2026-09-30 owner ACK cleanliness correction (pure static)

A review found that `gameplay_source_owner._validate_native()` accepted a
native diagnostic with `diagnostic_process_clean=false`, `log_clean=false`, or
`owner_record_retained=true` when the executor reported the explanatory
`EXECUTOR_ENGINE_OR_HOST_NOT_CLEAN` error. That could let a dirty diagnostic
reach selector adoption and a `READBACK_ACK`. The validator now requires
`gameplay_profile_unchanged=true`, `diagnostic_process_clean=true`,
`log_clean=true`, `owner_record_retained=false`, and `errors=[]` before any
adoption phase. Five pure tests pass with actual exit 0, including one negative
case for each dirty field; no Godot, Docker, Blender, or native evidence was
run or rewritten. This remains `AUTHORITY=0`, does not close AUTH-05, and does
not change GT-06.

### 2026-09-30 gameplay-source retry identity and authorization

The owner now derives a canonical request digest from project/profile,
command ID, expected revision, entrypoint and sorted path/hash/size records.
It validates a private copy of immutable source bytes before consulting cached
receipts. Changed source/entrypoint/revision with an old digest is rejected;
an exact retry (including reordered file mappings) remains idempotent after
the selected revision advances. Cached receipts also require an open owner,
live grant, current lease and valid deadline. Caller mutation after validation
cannot change the selected bytes.

`python -B studio/tests/godot/test_gameplay_source_owner.py`: 10 pure tests,
actual exit 0, 0.647s. Negatives verify unchanged selector/journal and no
repeated native-runner call. No native engine, Docker run or public capability
was enabled; `AUTHORITY=0`, no merge before GT-06 acceptance.

Remaining AUTH-02..04 work: persist/rebuild command deduplication on reopen;
reconcile a crash between selector replacement and terminal journal append;
bind native result to the owned executor run and full runtime closure. Reuse
the existing publication owner's
capture/prepare/select/readback recovery design rather than extending this
candidate with an unrelated recovery protocol. Current pure tests and old
native evidence do not establish those guarantees or authoring acceptance.

### 2026-09-30 publication writer and lifecycle boundary (static)

The candidate publication owner now admits only one complete publish writer at
a time. A competing request fails closed with `GAMEPLAY_OWNER_BUSY` before it
can reserve a session phase, touch a revision, selector or journal, and the
active writer remains usable for an exact retry. The lifecycle lock is kept
only across the short selector-adoption and durable-journal commit boundary;
the native executor remains interruptible by `close()` while it is running.
This prevents `CURRENT` from advancing beyond the last `COMMITTED` journal row
if Stop arrives at the selector replacement boundary. A barrier test closes
at that exact point, proves close waits for the boundary, then reopens and
reads the committed revision and generation.

`python -B studio/tests/godot/test_gameplay_source_owner.py`: **16 pure
tests**, actual exit 0, 2.879s. The cases cover competing writers, close
during a blocked native run, close at selector adoption, exact retry after
reopen without a second native call, rejection of a tampered terminal
receipt, native input hash binding, and run-directory `result.json` readback.
Journal reopen now validates canonical
bounded rows, project/profile/source-closure identity, monotonic generation,
receipt digest/readback, and the revision manifest before it repairs only
`CURRENT` from the terminal journal row. No native engine, Docker, Blender or
formal GT06 run was started. This remains `AUTHORITY=0`; full arbitrary
runtime closure remains open, and the branch must not merge before GT06 is
accepted.

The reconciliation cases are covered by the same pure suite: a selector behind
the committed journal is advanced back to the durable receipt, while a
selector ahead of a journal whose terminal row is missing is rolled back to
the last durable revision. No selector-only revision is adopted.

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

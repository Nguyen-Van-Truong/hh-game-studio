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

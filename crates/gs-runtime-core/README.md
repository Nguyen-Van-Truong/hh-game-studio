# gs-runtime-core

Frozen play-world projection + fixed 60Hz phase schedule (MASTER 6.2) and
the Luau VM host (MASTER 7.1–7.3, WP-M3-1 / M3-2).

Builds a `BTreeMap` world from `scene.json` entities (numeric id order).
`step` runs input → script_on_update → commit → physics → collisions →
timers stub → emit_trace → `RenderSnapshot` (gs-render2d).

Without attached source, `script_on_update` only visits entity ids (no-op).
`World::from_scene` registers `extra.script` (file + props).
`World::load_script_sources` reads UTF-8 from a script root.
`World::attach_script` + `ScriptVm` compile **source text only** (I4).

Lifecycle / `self.state` / disable / `gs.spawn` need a long-lived
`ScriptHost` owned by the caller (`step_with_host` / `ScriptHost::step`).
Do not store the VM on `World` (mlua is `!Send`). `step(&mut World, &input)`
without a host still works: no scripts → no VM; attached scripts → ephemeral
VM (M3-1 compat).

Rapier2d (`0.22` + `enhanced-determinism`) lives on caller-owned
`PhysicsHost` (`step_with_physics` / `step_with_hosts`). Do not store it on
`World` (`World` is `Clone`). Bare `step` / `step_with_host` with no
`RigidBody2D`/`Collider2D` keeps the old no-op physics path. If those
components exist and no host is passed, an ephemeral Rapier world is built
for that step only (velocity does not persist — fine for single-step tests).

After commit, transforms sync into Rapier (entity id ascending, including
`rt_N`). After the Rapier step, `x`/`y`/`rot` are written **directly** onto
`World` transforms. Collision/sensor pairs are sorted `(min_id, max_id,
is_sensor)` then queued as `collision_enter` / `collision_exit` on both
entities. NaN/Inf transforms are not sent to Rapier (GS-EC-01); NaN from
physics resets the last finite pose.

Tilemap cells are RLE `[[x,y,len,tile]]`. World Y-up: cell `(cx, cy)` is a
box whose bottom-left is `entity.transform.xy + (cx * cell_w, cy * cell_h)`,
size `cell_size` (rotation/scale not applied). Render expands occupied
cells (`tile >= 0`) into `RenderItem` quads, grouped conceptually into
16×16 chunks (`iter_tilemap_chunks`); emission is capped at 4096 quads.
Solid layers bake one static box per valid RLE run onto the tilemap
entity's Rapier body (multi-collider; `user_data` = entity id — no reserved
bake-id range; `RUNTIME_ID_BASE` stays `1 << 40`). Empty/negative `len`
runs are skipped here (GS-EC-06 bounds live in gs-scene).

`gs.velocity` / `gs.impulse` commit onto `World` pending maps;
`PhysicsHost::integrate` applies them (then clears) before the Rapier
step. `gs.raycast` / `gs.overlaps` read the **previous** integrated
`PhysicsHost` passed into `script_on_update` (physics still runs after
scripts). Bare `step` with no host keeps those queries empty/nil.

Editor must not depend on this Luau host (I3). No audio, no bevy_ecs.
Accumulator lives in `gs-player`, not here.

Host API: `docs/LUAU_API.md`. Sample: `templates/scripts/door.luau`.

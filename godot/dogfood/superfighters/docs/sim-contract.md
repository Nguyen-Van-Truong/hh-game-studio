# Vault Fighters — simulation contract (VF1-WP2)

Timezone: **Asia/Saigon**. Display title: **Vault Fighters**.
This is a **product** clock/schema, not a Y8 play observation.

Does **not** claim Y8 parity, V0–V6, R9-WP4, G6, GX, or 60/60.

## What this WP ships

- Typed `InputFrame` (`tick`, `held`, `pressed`, `released`, `move_x`/`move_y`)
- Match `seed`, collision-layer names, snapshot schema, event-order list
- Gameplay steps at fixed **60 Hz** through an accumulator
- `snapshot()` / `snapshot_hash()` are read-only (no state mutate)

Replay traces are **VF1-WP3** (`tests/traces/`, `SimReplay`). Official
MATCH uses typed `InputFrame` + `apply_frames`, not cmd-dict
`step_fixed`. This file is the clock/schema those traces obey.

## Clock (ledger:RL-SIM-FIXED-60)

Class: `assumption`. Source: product invariant V-A14, not a live Y8 page
or play session. **Do not** cite 60 Hz as “Y8-like”.

- `TICK_DT = 1/60`
- Live `_physics_process` feeds wall time into `SimClock`; each consumed
  slice runs one sim tick
- Pause freezes the clock; resume **zeros** leftover accum so a paused
  hitch cannot catch up and jump ticks
- `step_fixed` always uses `TICK_DT` (the `delta` argument is ignored)

## InputFrame

Allowed actions: `left right up down jump crouch melee fire grenade roll`.

Listing-page keys stay on ledger:RL-CTRL-P1-MOVE, RL-CTRL-P1-PUNCH,
RL-CTRL-P1-SHOOT, RL-CTRL-P1-NADE, RL-CTRL-P2-MOVE, RL-CTRL-P2-ATK.
Jump/crouch vs aim-up/down is ledger:RL-MOVE-JUMP-CROUCH (`assumption`).
Hold-to-aim / release-to-fire is first-playable behavior and
ledger:RL-CTRL-HOLD-AIM (`assumption`) — **not** promoted to `observed`.
`roll` is a shipped action (`ledger:RL-MOVE-ROLL`, `assumption`).
`dive` / `kick` stay reserved and **rejected** as unknown
(ledger:RL-MOVE-ROLL-DIVE `unavailable`).
F11 is page chrome, not a fighter action (ledger:RL-CTRL-FULLSCREEN).

Malformed frames (missing tick, negative tick, tick mismatch, unknown
action, non-array held/pressed/released, non-finite axis) are rejected
and **do not** advance the clock.

## Event order

`input_validate → locomotion → melee → fire_spawn → grenade_spawn →
weapon_respawn → projectiles → explosives → match_resolve`

This is the first-playable `GameSession` order, written down so later
WPs cannot silently reorder it.

## Collision layers

`world=1 platform=2 fighter=4 pickup=8 hurt=16 prop=32`.
Must match `Maps.COL_*`. Godot 2D physics, not Box2D
(ledger:RL-DELTA-PHYSICS).

## Snapshot / hash

Schema `vf.sim.snapshot.v1`. Positions quantized at `epsilon=0.001`
(recorded in the snapshot). Hash is SHA-256 of a canonical payload that
omits presentation (HUD, camera, VFX, audio). Calling snapshot/hash
twice without a tick must return the same digest and must not move
actors.

## Seed

`7 + stage * 13` — first-playable weapon-spawn RNG. Not an observed Y8
table (ledger:RL-ITEM-RANDOM-SPAWN / ledger:RL-MODE-CHAOS).

## Locomotion (VF2-WP2)

Walk / jump / crouch / pit / camera numbers live in
`data/sim/locomotion.json`. They are product tuning
(`ledger:RL-MOVE-LOCO-BASE`, `assumption`), not Y8 play.
Jump/crouch stay `ledger:RL-MOVE-JUMP-CROUCH`. Camera stays
`ledger:RL-CAM-ARENA`. Official MATCH uses `apply_frames`.
60 Hz stays ledger:RL-SIM-FIXED-60.

## Runtime observe (VF1-WP4)

Agents read `RuntimeApi` (`docs/runtime-diagnostics.md`,
ledger:RL-RUNTIME-OBSERVE). That WP does not change this snapshot
hash payload. 60 Hz stays ledger:RL-SIM-FIXED-60.

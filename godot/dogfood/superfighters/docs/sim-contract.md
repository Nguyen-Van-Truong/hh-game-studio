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

Allowed actions: `left right up down jump crouch melee fire grenade roll dive kick`.

Listing-page keys stay on ledger:RL-CTRL-P1-MOVE, RL-CTRL-P1-PUNCH,
RL-CTRL-P1-SHOOT, RL-CTRL-P1-NADE, RL-CTRL-P2-MOVE, RL-CTRL-P2-ATK.
Jump/crouch vs aim-up/down is ledger:RL-MOVE-JUMP-CROUCH (`assumption`).
Hold-to-aim / release-to-fire is first-playable behavior and
ledger:RL-CTRL-HOLD-AIM (`assumption`) — **not** promoted to `observed`.
`roll` is a shipped action (`ledger:RL-MOVE-ROLL`, `assumption`).
`dive` / `kick` are shipped (`ledger:RL-MOVE-DIVE` /
`ledger:RL-MOVE-JUMP-KICK`, `assumption`). Y8 observation stays
ledger:RL-MOVE-ROLL-DIVE (`unavailable`). InputFrame `ledge` stays
reserved; ledge *behavior* is shipped (`ledger:RL-MOVE-LEDGE`,
`assumption`).
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

## Combat (VF3-WP1)

Melee phases, AABB boxes, friendly-fire, and presentation hitstop
live in `data/sim/combat.json`. They are product tuning
(`ledger:RL-HIT-PHASES`, `ledger:RL-HIT-BOX`, `ledger:RL-HIT-FF`,
`ledger:RL-HIT-HITSTOP`, `assumption`), not Y8 play. Kick stays
`ledger:RL-MOVE-JUMP-KICK`. Official MATCH uses `apply_frames`.
60 Hz stays ledger:RL-SIM-FIXED-60. Hitstop does not pause the clock.

## Hit reaction (VF3-WP2)

Knockback, knockdown/get-up, exact-tick invuln, and punch disarm
live in `data/sim/combat.json` `hit_reaction`. They are product
tuning (`ledger:RL-HIT-KNOCK`, `ledger:RL-HIT-DOWN`,
`ledger:RL-HIT-INVULN`, `ledger:RL-HIT-DISARM`, `assumption`),
not Y8 play. Official MATCH uses `apply_frames`. Official death
causes stay `damage` / `pit`. 60 Hz stays ledger:RL-SIM-FIXED-60.

## Aim / fire (VF3-WP3)

Hold-to-aim, aim dirs, semi release, auto cadence, muzzle, recoil,
and swept ballistic collision live in `data/sim/aim.json`. They
are product tuning (`ledger:RL-CTRL-HOLD-AIM`, `ledger:RL-AIM-DIRS`,
`ledger:RL-FIRE-SEMI`, `ledger:RL-FIRE-AUTO`, `ledger:RL-FIRE-AMMO`,
`ledger:RL-FIRE-MUZZLE`, `ledger:RL-FIRE-RECOIL`,
`ledger:RL-FIRE-BALLISTIC`, `ledger:RL-FIRE-SWEEP`, `assumption`),
not Y8 play. Hitscan is rejected. Official MATCH uses
`apply_frames`. 60 Hz stays ledger:RL-SIM-FIXED-60.

## Grenade / explosive (VF3-WP4)

Arc, bounce, fuse, radial falloff, owner/team rules, one-shot
explosion, timeout cleanup, and swept nade collision live in
`data/sim/explosive.json`. They are product tuning
(`ledger:RL-NADE-HOLD`, `ledger:RL-NADE-ARC`,
`ledger:RL-NADE-BOUNCE`, `ledger:RL-NADE-FUSE`,
`ledger:RL-NADE-FALLOFF`, `ledger:RL-NADE-OWNER`,
`ledger:RL-NADE-ONCE`, `ledger:RL-NADE-TIMEOUT`,
`ledger:RL-NADE-SWEEP`, `assumption`), not Y8 play. Prop break
stays `ledger:RL-NADE-PROP` (`deferred`). Official MATCH uses
`apply_frames`. 60 Hz stays ledger:RL-SIM-FIXED-60.

## Roster / inventory (VF3-WP5)

Four slots and the original roster live in
`data/weapons/roster.json`. They are product tuning
(`ledger:RL-ITEM-SLOTS-4`, `ledger:RL-ITEM-ROSTER`,
`ledger:RL-ITEM-PICK-SLOT`, `ledger:RL-ITEM-KEEP-GUN`,
`ledger:RL-ITEM-AMMO-RELOAD`, `assumption`), not Y8 play.
Values are not claimed as original exact numbers. Official
MATCH uses `apply_frames`. 60 Hz stays ledger:RL-SIM-FIXED-60.

## Runtime observe (VF1-WP4)

Agents read `RuntimeApi` (`docs/runtime-diagnostics.md`,
ledger:RL-RUNTIME-OBSERVE). That WP does not change this snapshot
hash payload. 60 Hz stays ledger:RL-SIM-FIXED-60.

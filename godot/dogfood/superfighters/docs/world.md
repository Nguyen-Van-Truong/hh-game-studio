# World / prop schema — VF4-WP1

Display title: **Vault Fighters**. This document does **not** claim Y8 parity.

Sidecar evidence: `docs/evidence/VF4WP1-20260829-ASIA-SAIGON-01/`.

## Contract

Typed `PropSpec` rows live in `data/world/catalog.json`, gated by
`data/world/schema.json`. Kinds this WP: static, dynamic, one-way,
breakable, pickup, explosive.

Layer/mask names are in `data/sim/collision_layers.json` (`prop_masks`).
Bits stay equal to `Maps.COL_*`.

`WorldOwner` is the only spawn/despawn writer. `PropView` is
presentation-only and cannot despawn, move, or set health.

Editor and runtime share `WorldPaths`. Visual/collision paths must stay
inside the product root (`res://`, no `..`, no absolute, no `user://`).

Official MATCH uses `GameSession.apply_frames` on typed `InputFrame`s.
Clock is `ledger:RL-SIM-FIXED-60` (`assumption`).

## Authoring

Map authors add a catalog spec and a placement row. GameSession calls
`world_owner.spawn_map(map_id)` once. It does **not** hard-code a node
per crate/barrel/glass.

Live rooftops/storage/police/hazardous have **no** world placements this
WP. `c`/`b` stay painted tiles (VF5-WP1 prop/hazard layers) so prior
official hashes do not drift.

Fixture `fx_world_open` (display **Prop Yard**) places one of each kind.

## Later WPs

- Break / fragments / cover destroy: VF4-WP2 (`docs/break.md`,
  `ledger:RL-PROP-BREAK`)
- Dynamic throw/shove: VF4-WP2 (`ledger:RL-PROP-DYNAMIC`)
- Barrel chain / fire / hang: VF4-WP3 (`docs/hazard.md`, `ledger:RL-PROP-EXPL`)
- Nade prop destroy stays `ledger:RL-NADE-PROP` (`deferred`)
- Doors / elevators / boarding: VF4-WP4 (`docs/moving.md`,
  `ledger:RL-WORLD-DOOR`, `ledger:RL-WORLD-LIFT`,
  `ledger:RL-WORLD-BOARD`, `ledger:RL-WORLD-TRIGGER`)
- Toxic / water / machines / ArenaSpec: VF4-WP5 (`docs/env.md`,
  `ledger:RL-ENV-INSTANT`, `ledger:RL-ENV-DEFER`,
  `ledger:RL-ENV-WATER`, `ledger:RL-ENV-ROTOR`,
  `ledger:RL-ENV-SPAWN`, `ledger:RL-ENV-ARENA`)

## Honesty

- Schema / layers / ownership stay assumption:
  `ledger:RL-WORLD-SCHEMA`, `ledger:RL-WORLD-LAYERS`,
  `ledger:RL-WORLD-OWN`.
- Break / throw live in VF4-WP2 as assumption (`ledger:RL-PROP-BREAK`,
  `ledger:RL-PROP-DYNAMIC`).
- Nade destroy stays `ledger:RL-NADE-PROP` deferred.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption.
- Y8 roll/dive stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Values are tuning. No copied Y8 table.

## Hash and orphan

Restart rebuilds from the catalog. Prior `PropBody` instance ids are
invalid. Idle ticks and a second boot keep the same world hash.
No leftover `vf_world_prop` after title restart (orphan proof).

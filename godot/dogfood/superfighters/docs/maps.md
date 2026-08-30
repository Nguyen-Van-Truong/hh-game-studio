# Map schema and authoring — VF5-WP1

Display title: **Vault Fighters**. This document does **not** claim Y8 parity.

Sidecar evidence: `docs/evidence/VF5WP1-20260830-ASIA-SAIGON-01/`.
That `run_id` is unique. Do **not** remint it.

Official MATCH uses `GameSession.apply_frames` on typed `InputFrame`s
for the live walk. Clock is `ledger:RL-SIM-FIXED-60` (`assumption`).

## Contract

Live arenas load from layered JSON under `data/maps/arenas/`, gated by
`data/maps/schema.json` and `data/maps/catalog.json`. Layers this WP:
solid, one-way, ladder, hazard, prop, spawn, pickup.

ASCII character strings are no longer the source of truth. `Maps.grid()`
is a derived compatibility view. Adding a new kind does **not** require
inventing a new character.

`MapValidator` checks width, overlapping blockers, reachable spawn
floors, pit boundary, safe camera (fits 1280×720), and graph reach.
`MapGraph` walks, climbs ladders, falls, and jumps with a product
envelope (`jump_dx=10`, `jump_dy=4`) — tuning, not observed Y8 reach
(`ledger:RL-MAP-GRAPH`).

Editor agents create maps with `MapAuthor` semantic commands
(`map.create`, `map.paint_rect`, `map.set_cell`, `map.set_spawn`,
`map.set_pickup`, `map.validate`, `map.serialize`, `map.deserialize`,
`map.persist`). Commands have unique `command_id`, validate before
apply, retry from ACK, and persist with temp+rename under `user://`.

Official author proof rebuilds **Draft Yard** (`fx_map_author`) from
`tests/traces/maps/map_author.json` and matches the shipped hash.

## Live maps

Geometry of rooftops / storage / police / hazardous is unchanged this
WP. Display names stay as first-playable debt
(`ledger:RL-DELTA-MAP-NAMES`) until VF5-WP2+. `c` / `b` now live on
prop / hazard layers but still **paint as tiles**. Combat/env fixture
ASCII rows stay import-only.

## Honesty

- Layers / graph / validator / author stay assumption:
  `ledger:RL-MAP-LAYERS`, `ledger:RL-MAP-GRAPH`,
  `ledger:RL-MAP-VALID`, `ledger:RL-MAP-AUTHOR`.
- `ledger:RL-NADE-PROP` stays deferred.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption.
- Y8 roll/dive stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Values are tuning. No copied Y8 table. Not a VF7 art rewrite.
- No new in-game Y8 play. Not a VF5-WP2 layout pass.

DoD window stills wait for `frame_post_draw` after `start_fight` and
a standing settle. Setup is rooftops. Rooftops / storage / police /
hazardous / Draft Yard must be pairwise-distinct bytes.

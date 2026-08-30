# Toxic pits, fall, water, and machines — VF4-WP5

Display title: **Vault Fighters**. This document does **not** claim Y8 parity.

Sidecar evidence: `docs/evidence/VF4WP5-20260830-ASIA-SAIGON-01/`.
That `run_id` is unique. Do **not** remint it.

Official MATCH uses `GameSession.apply_frames` on typed `InputFrame`s.
Clock is `ledger:RL-SIM-FIXED-60` (`assumption`).

## Contract

Instant death, deferred toxic, water, and rotor machines live in
`data/world/env.json`. Per-map hazard lists live in
`data/maps/arena_spec.json`. Env kinds are **not** catalog
`allowed_kinds` rows. That keeps VF4-WP1/2/3/4 catalog ids unchanged.

`WorldOwner` is the only writer. It spawns `EnvBody` rows, steps
overlap after movers, and writes enter/exit/damage/death/extinguish
ledger events. `PropView` cannot mutate.

Instant (`ledger:RL-ENV-INSTANT`): overlap kills with `die_env("pit")`.
Dive does not cancel. Cause stays `pit` so VF3 death-cause checks
stay green.

Deferred toxic (`ledger:RL-ENV-DEFER`): acid contact, then
`take_env_tick` every 8 ticks (12 HP). Death cause is `damage`.
Melee invuln does not grant.

Water (`ledger:RL-ENV-WATER`): overlap sets `wet` and extinguishes
burn. Selected in `env.json` (`water_extinguish: true`). Roll
extinguish stays selected in `hazard.json`. `hazard.json`
`water_selected` stays **false**.

Rotor (`ledger:RL-ENV-ROTOR`): mill overlap ticks every 10 ticks
(8 HP) and advances 6 deg/tick. First hit is at contact count 10.

Fall (`ledger:RL-MOVE-FALL`): Drop Well walk-off applies fall
damage; dive landing emits `fall_immune`. Land must be standing
`on_floor`, not hang. Policy is declared in ArenaSpec.

Spawn (`ledger:RL-ENV-SPAWN`): P/1 spawn AABBs must not overlap
instant/toxic/rotor. Pause freezes rotor spin; restart rebuilds
env at rest (`wet`/`acid` clear).

ArenaSpec (`ledger:RL-ENV-ARENA`) names hazards per map. Live maps
declare pit/fall only. Machines/water/toxic stay on fixtures.
VF5-WP1 retires ASCII as the live source (`layered_maps`). Live
`c`/`b` stay painted tiles.

`ledger:RL-NADE-PROP` stays `deferred`.

## Fixtures

- `fx_env_instant` display **Void Cut** — walk into the void
- `fx_env_toxic` display **Acid Trench** — enter / idle / exit
- `fx_env_water` display **Wash Channel** — walk through wash
- `fx_env_rotor` display **Mill Shaft** — walk + idle on mill
- `fx_env_fall` display **Drop Well** — standing walk-off
- `fx_env_yard` display **Hazard Yard** — water, mill, acid (no instant)

Live police/hazardous paint `c`/`b` as tiles from
prop/hazard layers (VF5-WP1). Skyline Relay (VF5-WP2) adds original
breakable cover placements. Pallet Annex (VF5-WP3) places cover,
hanging cargo, door, and lift because that WP asks for them.
Machines/water/toxic stay fixture-only. Character/map readability
art is VF7.

DoD window stills wait for `frame_post_draw` after the matching
`start_fight` and after the frames that wet, spin, acid, kill, or
land standing. Setup is Hazard Yard spawn. Water/rotor/toxic/instant/fall
must be pairwise-distinct bytes, not leftover framebuffer copies.

## Honesty

- Instant / defer / water / rotor / spawn / arena stay assumption:
  `ledger:RL-ENV-INSTANT`, `ledger:RL-ENV-DEFER`,
  `ledger:RL-ENV-WATER`, `ledger:RL-ENV-ROTOR`,
  `ledger:RL-ENV-SPAWN`, `ledger:RL-ENV-ARENA`.
- Fall stays `ledger:RL-MOVE-FALL` assumption.
- `ledger:RL-NADE-PROP` stays deferred.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption.
- Y8 roll/dive stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Values are tuning. No copied Y8 table. Not a VF7 art rewrite.
- Original acid/water/void/rotor art only. No Y8 rip.
- No new in-game Y8 play this WP. Do **not** mark ledger observed.

# Break / throw — VF4-WP2

Display title: **Vault Fighters**. This document does **not** claim Y8 parity.

Sidecar evidence: `docs/evidence/VF4WP2-20260829-ASIA-SAIGON-01/`.

## Contract

Glass and wood breakables have health and material resistance in
`data/world/catalog.json`. A bullet or melee hit scales by material
then subtracts health. One `break` event disables collision, hides
the sprite, and spawns a deterministic debris count. Debris cleans
up after `debris_life_ticks`.

Cover stays solid until that break. The next projectile may pass.
That opens a fire lane (tactics), not a cosmetic flicker.

Dynamic crates can be shoved by melee or carried (crouch+melee)
then thrown on grenade release. Official throw/shove maps use `#`
floors only.

`WorldOwner` is still the only writer. `PropView` cannot despawn,
move, or set health.

Official MATCH uses `GameSession.apply_frames` on typed `InputFrame`s.
Clock is `ledger:RL-SIM-FIXED-60` (`assumption`).

## Fixtures

- `fx_break_cover` display **Shatter Lane** — glass pane between P1 and P2
- `fx_break_yard` display **Break Yard** — wood crate on the walk
  lane, then a loose crate. Shove/throw first break the wood so the
  lane opens (tactic, not a teleport).

Live rooftops/storage/police/hazardous still paint ASCII `c`/`b` as
tiles. This WP does not migrate them.

## Honesty

- Break stays assumption: `ledger:RL-PROP-BREAK`.
- Shove/throw stay assumption: `ledger:RL-PROP-DYNAMIC`.
- Nade destroy stays `ledger:RL-NADE-PROP` deferred.
- Explosive chain waits VF4-WP3 (`ledger:RL-PROP-EXPL`).
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption.
- Y8 roll/dive stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Values are tuning. No copied Y8 table. Original glass/debris art only.

# Bots — Vault Fighters

Sidecar for VF6-WP5. Display title remains **Vault Fighters**.
Planner rows are `ledger:RL-BOT-*` (`assumption`). Not observed Y8.
Not a Superfighters trademark use.

Official `run_id` is `VF6WP5-20260903-ASIA-SAIGON-03`
(`cmd.vf6-wp5.bots.3`). Packs `-01` and `-02` are void.

## What shipped

Bots use a seeded planner instead of the old greedy weapon-then-chase
loop:

- platform / ladder graph from `MapGraph` + bounded A*
- threat / cover / pickup / attack / retreat / patrol intents
- two live weapon classes proven from ledger (`fire_spawn` plus
  `explosion` or melee `hit`), not starter-kit hold counters
- aim error rotates the actual shot direction (`aim_x`/`aim_y`);
  official proof is a measured miss versus the geometric center.
  Bots do not have perfect aim.
- pit avoid is a route-around (backtrack / other platform / jump),
  not a freeze at the lip
- knockdown recovery wait
- recruit / regular / veteran profiles in `data/sim/bots.json`

Difficulty knobs are reaction delay, aim error degrees, tactical
budget, and recovery ticks. They are HUD-visible on the VS stage line
(`Bot skill regular · delay … · aim±…°`). Values are product tuning.

Greedy baseline walks straight at the foe with no pit graph. Planner
compare must show a differential death or a goal only the planner
reaches.

Finish proof botifies every slot. The winner must have moved and
fired or melee-hit. An AFK P1 last-standing statue is not a finish.

## Honesty

- No teleport. Official proof is `think()` → `apply_frames` on the six
  catalog VS maps.
- No hidden HP/ammo through walls. Perception is line-of-sight only.
  `hearing_px` is a nearer react range still blocked by world. Last
  seen expires in 8 ticks and is not used without a fresh LOS. A null
  physics space is not a foe.
- Map topology is public (a player who knows the arena).
- Hold-to-aim stays the human discrete cone
  (`ledger:RL-CTRL-HOLD-AIM` assumption). Bot aim error is an analog
  override on that command so the bullet leaves on the erred vector.
- Official `run_all` does not default `HH_VF_BOTS_COMPACT`.
- Survival / Stage official banners stay `NOT_AI=1` because those
  packages did not remint planner postconditions. Live Survival/Stage
  bots still use this brain.
- Not Y8 parity.

## Residual

Overlay 31-8 3 seed × 2 skill × 2 opponent matrix is AUTHORITY=0 and
not claimed. Art is VF7.

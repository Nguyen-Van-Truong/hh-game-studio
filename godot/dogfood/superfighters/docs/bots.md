# Bots — Vault Fighters

Sidecar for VF6-WP5. Display title remains **Vault Fighters**.
Planner rows are `ledger:RL-BOT-*` (`assumption`). Not observed Y8.
Not a Superfighters trademark use.

Official `run_id` is `VF6WP5-20260904-ASIA-SAIGON-08`
(`cmd.vf6-wp5.bots.8`). Packs `-01`…`-07` and the 20260903 `-04`
id are void.

## What shipped

Bots use a seeded planner instead of the old greedy weapon-then-chase
loop:

- platform / ladder graph from `MapGraph` + bounded A*
- threat / cover / pickup / attack / retreat / patrol intents
- two live weapon classes proven in combat: ledger `fire_spawn` plus
  a melee `hit` on a living foe, or a nade explosion that hits after
  a fight close. A starter-kit nade dump is not a second class.
- aim error rotates the actual shot direction (`aim_x`/`aim_y` on
  `Bullet.setup`). Bots do not have perfect aim. A measured `shot_off`
  is telemetry. `perfect_aim=0` is not advertised as proof — a real
  near-zero roll may occur.
- pit avoid is a route-around (backtrack / other platform / jump),
  not a freeze at the lip. Same-Y pit lips are not A* walk edges.
  Rooftops must show a lower goal/waypoint or a successful detour,
  not 44 freezes then a park.
- airborne spawn/fall paths from the landing floor, not an air cell
  treated as a high deck. A held hop keeps air-x so a closed door
  can be cleared; falling before a hop does not air-walk into crates.
- knockdown recovery wait
- recruit / regular / veteran profiles in `data/sim/bots.json`
- vs1 can spawn a 2-body roster (`vs1_bot_count=1`). Official finish
  uses that spawn. It does not cull extras after `sync_physics`.

Difficulty knobs are reaction delay, aim error degrees, tactical
budget, and recovery ticks. They are HUD-visible on the VS stage line
(`Bot skill regular · delay … · aim±…°`). Values are product tuning.

Greedy baseline walks straight at the foe with no pit graph. Planner
compare may use a greedy pit-death delta as supporting evidence, but
the planner must also arrive (`goal < 36` or `engage < 48`) on that
rooftops seed. Fire deaths are not pit deaths.

Finish proof starts with exactly two fighters (bot vs bot). The
champion must have moved and fought; the loser must die by damage.
An idle full-HP teammate is not last-standing.

Reach proof is the named opponent start (`goal_dist < 36`), melee /
inside fire range (`engage_dist < 48`), or the named foe down after
a proven close (`closest_engage < 48`). Parking at engage in
`[71, 72)` is not reach. A long-range shot, a 27px shuffle, walking
away, or a reroute counter is not reach.

Bots keep walking toward the foe or a named platform after they
start firing. Walk-stop is the melee pocket only. It is not the
harness reach constant.

## Honesty

- No teleport. Official proof is `think()` → `apply_frames` on the six
  catalog VS maps.
- No hidden HP/ammo through walls. Perception is line-of-sight only
  (no 320px sight cap; walls still block). `hearing_px` only ranks
  already-visible foes. After LOS breaks, bots may walk to the frozen
  last-seen point for 16 ticks, then patrol public spawn pads. They
  do not track a live body through walls. A null physics space is not
  a foe.
- Map topology is public (a player who knows the arena).
- Hold-to-aim stays the human discrete cone
  (`ledger:RL-CTRL-HOLD-AIM` assumption). Bot aim error is an analog
  override on that command so the bullet leaves on the erred vector.
- Official leftover is host `WaitForExit` on product `--path` only.
  A PASS banner is not remapped to exit 0. Critic iso exclude is not
  required.
- Official `run_all` does not default `HH_VF_BOTS_COMPACT`.
- Survival / Stage official banners stay `NOT_AI=1` because those
  packages did not remint planner postconditions. Live Survival/Stage
  bots still use this brain.
- Not Y8 parity.

## Residual

Overlay 31-8 3 seed × 2 skill × 2 opponent matrix is AUTHORITY=0 and
not claimed. Art is VF7.

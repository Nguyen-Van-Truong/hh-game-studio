# VF3-WP6 critical / chaos tuning and combat balance

Display title: **Vault Fighters**. This WP does **not** claim Y8 parity
and does **not** ship a copied stat table. Values are original
product tuning. Official proof is `apply_frames` plus live
InputEvent inject plus 1000 seed-controlled resolution rolls.
Clock is `ledger:RL-SIM-FIXED-60` (`assumption`).

Chaos stays `ledger:RL-MODE-CHAOS` (developer note is
`secondary`; product ship is `assumption`). Crit stays
`ledger:RL-BAL-CRIT` (`assumption`). Knock jitter stays
`ledger:RL-BAL-KNOCK-JITTER` (`assumption`). Spread jitter
stays `ledger:RL-BAL-SPREAD-RNG` (`assumption`). Caps stay
`ledger:RL-BAL-CAP` (`assumption`). Stamina stays
`ledger:RL-BAL-STAMINA` (`assumption`). Hold-to-aim stays
`ledger:RL-CTRL-HOLD-AIM` (`assumption`). Y8 roll/dive
observation stays `ledger:RL-MOVE-ROLL-DIVE` (`unavailable`).

## Why these numbers

| Knob | Value | Rationale |
|---|---|---|
| crit chance | 0.12 | Enough to feel unfair some of the time, not a coin flip. |
| crit multiplier | 1.35 | Burst without one-shotting 100 HP from a punch. |
| knock jitter | ±18% | Reads as scramble, stays boardable. |
| spread jitter | 0.55 × data spread | Chaos-on only; VF3-WP3 fan stays the base. |
| hit cap | 56 | Per-hit via `take_damage` / `clamp_hit`. Above live nade 42 / launcher 40; below 100 HP. |
| tick cap | 80 | Per-tick via `tick_room`. Shotgun pellets cannot stack past a life in one tick. |
| stamina | 28 / 22 / 22 / 18 | Same VF2-WP3 drain/recover so sprint traces stay. |

These are **not** Y8 wiki numbers. `copied_stat_table` is false.

Hit cap is **per-hit** (one `take_damage` call). Tick cap is
**per-tick** (`damage_taken_tick` resets each sim tick). Two
grenades on different ticks can sum above 56; each hit is still
clamped to 56, and one tick cannot exceed 80.

## Published dominance bar (written before the `-03` batch)

The 1000-batch is **formula rolls**, not 1000 live matches.
Each scenario rolls every roster weapon through `roll_weapon`
and scores `damage * rate + knock * 0.25`, then multiplies by a
**slot context fitness** for that advertised context. Winner ids
are computed from the batch. They are **not** hard-coded.

This bar is published **before** the `-03` numbers. It is the
bar that `-02` knife **0.761** and **5/5** `context_best=knife`
must fail. Soft `0.72` and `dominates = (win_rate >= 1.0)` are
rejected; those move the Verify line.

A batch **fails** “no weapon always dominates” when any of:

1. `win_rate_max >= 0.55` (a sweep, not “someone led”).
2. fewer than **2** weapons have a batch win share.
3. fewer than **3** distinct `context_best` values.
4. winners are hard-coded ids.
5. method is not `formula_rolls`.

`-02` knife 0.761 with one context winner fails (1) and (3).
A 0.40 leader with three context winners would pass. Raising
`max_win_rate` above 0.55 to fit a later batch is a Verify
change and is a schema reject.

Slot fitness is designer intent (`assumption`, not Y8 observed).
It exists so a clinch is not scored as if it were a grenade
chain. Multipliers are by **slot**, never by weapon id.

| context | melee | firearm | explosive | power |
|---|---:|---:|---:|---:|
| close_melee | 1.35 | 0.55 | 0.40 | 0.40 |
| high_ground | 0.45 | 1.40 | 0.70 | 0.70 |
| pit | 0.70 | 0.80 | 1.35 | 1.20 |
| grenade_chain | 0.35 | 0.50 | 1.80 | 1.50 |
| friendly_fire | 1.20 | 0.85 | 0.30 | 0.30 |

## Fire-path hit cap

HIGH proves a live pistol hit (`damage > 0`) on Shelf Shot.
That pistol is 18 and cannot overcap.

OVERCAP is the cap proof: a test-only `overcap_rifle` (aim data,
damage 90, not in the roster spawn pool) is given to P1 and
fired through `_do_fire` → ballistic sweep → `_apply_bullet_hit`
→ `take_damage` / `clamp_hit` on **that** event. Required:

- `last_incoming_raw > 56` on the target (take_damage saw overcap)
- applied HP delta `<= 56` and `> 0`
- path is `bullet`
- `min(raw, tick_cap) > 56` so identity-`clamp_hit` would fail
  (applied would be 80, or the fighter would die)

A later `take_damage(999)` poke on the shooter is **not** the
cap proof. Removing `clamp_hit` must make OVERCAP fail.

## Chaos gate

Live play (`test_driven=false`) enables a dedicated chaos stream
seeded from `sim_seed + 10007`. Official VF3-WP1..5 traces do
not set `chaos` and stay deterministic. VF3-WP6 traces set
`"chaos": true` and replay twice to the same hash.

## Scripted scenarios

| id | map | beat |
|---|---|---|
| close melee | Clinch Alley | fists land, damage finite |
| high ground | Shelf Shot | hold-to-aim down-right **must hit** (pistol live `> 0`) |
| overcap | Shelf Shot | test-only rifle fire-path raw `> 56`, applied `<= 56` |
| pit | Gap Fall | P2 walks into the pit, death_cause `pit` |
| grenade chain | Twin Fuse | two downward throws on `#` only; P2 inside radius; live blast `> 0`; once-per-nade |
| friendly fire | Cross Fire | vs2 P1 melee damages P2 |

HIGH does not waive a miss. CHAIN does not pass on two off-map
explosions. VF3-WP4 `=` nade residual is unchanged; CHAIN stays
on `#`.

## Official run

`VF3WP6-20260829-ASIA-SAIGON-03` / `cmd.vf3-wp6.balance.3`

First-pass pack `VF3WP6-20260829-ASIA-SAIGON-01` and retry
`VF3WP6-20260829-ASIA-SAIGON-02` are not reminted.

## Evidence (V-A18 / §18.3)

Official `run_id`: `VF3WP6-20260829-ASIA-SAIGON-03`.
Layout is `.evidence/<run_id>/` plus review copies under
`docs/evidence/<run_id>/`.

```
python godot/dogfood/superfighters/tests/check_balance.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_balance.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_balance.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

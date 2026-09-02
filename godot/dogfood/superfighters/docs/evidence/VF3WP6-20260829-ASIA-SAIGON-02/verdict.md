# VF3-WP6 verdict

PASS critical/chaos tuning and combat balance harness (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF3-WP6)

Verify: 1000 seeded scenarios no NaN/infinite damage; distribution report,
no weapon always dominates; all scenarios replayable; no copied stat table.

DoD: combat feels chaotic yet bounded, with documented tuning rationale.

## Run

- `run_id`: `VF3WP6-20260829-ASIA-SAIGON-02`
- `command_id`: `cmd.vf3-wp6.balance.2`
- seed `7`, mode `vs2`, map `fx_balance_melee`
- SCHEMA=pass BATCH=pass DIST=pass DOM=pass MELEE=pass HIGH=pass PIT=pass CHAIN=pass FF=pass STAMINA=pass DATA=pass LIVE=pass REPLAY=match
- BATCH count=1000 replay=True real=True
- DIST n=11000 mean=21.3196818110726 p95=42.0 real=True
- DOM leader=knife rate=0.761 winners=3 live=3 method=formula_rolls real=True
- MELEE damage=10.0 real=True
- HIGH damage=18.0 clamp=56.0 real=True
- CHAIN explosions=2 damage=40.9162886142731 once=True real=True
- PIT dead=True cause=pit real=True
- events kinds include hit/explosion/bullet=True
- window screenshot=True
- `USED_APPLY_FRAMES=1010` attempted=1010
- source_tree_sha256 `7e1781a8d696127fed1e188e911179145fed381f026803342005aeced032c939`
- base_head `ebc9f82779f6ba70ccbfdfcba08b4e2c964a0d77`
- Banners copy `BalanceCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_balance.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_balance.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_balance.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT 0 / 0 / 0 / 0. leftover Godot on product `--path` = 0.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Chaos / crit / knock jitter / spread jitter stay assumption
  (`ledger:RL-MODE-CHAOS`, `ledger:RL-BAL-CRIT`,
  `ledger:RL-BAL-KNOCK-JITTER`, `ledger:RL-BAL-SPREAD-RNG`).
  Developer note “IT AIN'T FAIR” is designer intent, not an RNG spec.
- Damage caps stay `ledger:RL-BAL-CAP` assumption.
  Hit cap is per-hit (`clamp_hit`); tick cap is per-tick (`tick_room`).
- 1000-batch is formula rolls, not 1000 live matches.
- Stamina numbers stay `ledger:RL-BAL-STAMINA` assumption; same VF2-WP3
  drain/recover so official sprint hashes do not drift.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption, not observed.
- All RL-ITEM-* / RL-NADE-* / RL-FIRE-* rows stay assumption.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- No new in-game Y8 play this WP.
- Not Y8 parity. Not V0.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

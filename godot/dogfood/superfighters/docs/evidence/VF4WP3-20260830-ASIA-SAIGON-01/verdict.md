# VF4-WP3 verdict

PASS explosive barrels, hanging containers, and fire/burning (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF4-WP3)

Verify: seeded chain scenario; fire damage ticks and cleanup; roll behavior;
no duplicate explosion or unbounded particles.

DoD: hazards interact with fighters and props in a visible real run.

## Run

- `run_id`: `VF4WP3-20260830-ASIA-SAIGON-01`
- `command_id`: `cmd.vf4-wp3.hazard.1`
- seed `7`, mode `vs2`, map `fx_hazard_yard`
- DATA=pass CHAIN=pass FIRE=pass CLEANUP=pass ROLL=pass DUP=pass VFX=pass HANG=pass LIVE=pass REPLAY=match
- CHAIN events=3 depth=2 real=True
- FIRE ticks=4 hp0=100.0 hp1=88.0 real=True
- CLEANUP burning=False fire_end=1 real=True
- VFX spawned=4 rejected=2 real=True
- HANG y0=24.0 y1=39.5000038146973 drops=1 real=True
- events kinds include prop_explode=True
- window screenshot chain=True fire=True
- `USED_APPLY_FRAMES=723` attempted=723
- source_tree_sha256 `b93f98585c134f4814c053f306f0e02d717a85f5ac81c36afa12237002b4a0e3`
- base_head `14b99cce145f7ddd0022de6186521b3dd76c784d`
- Banners copy `HazardCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_hazard.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_hazard.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_hazard.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT 0 / 0 / 0 / 0. leftover Godot on product `--path` = 0.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Chain / fire / hang / extinguish stay assumption (`ledger:RL-PROP-EXPL`,
  `ledger:RL-PROP-CHAIN`, `ledger:RL-PROP-FIRE`, `ledger:RL-PROP-HANG`,
  `ledger:RL-PROP-EXTINGUISH`).
- Selected extinguish rule is roll. Water is not selected (VF4-WP5).
- `ledger:RL-NADE-PROP` stays `deferred`. Nades may start a barrel chain;
  they still do not destroy glass/wood.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption, not observed.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Live maps still paint `c`/`b` as tiles; this WP does not migrate them.
- Official chain/fire/hang uses `#` floors only. The VF3-WP4 `=` bounce residual is unchanged.
- Original explode/fire VFX only. Not a VF7 presentation rewrite. Not a Y8 rip.
- No new in-game Y8 play this WP.
- Not Y8 parity. Not V0.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

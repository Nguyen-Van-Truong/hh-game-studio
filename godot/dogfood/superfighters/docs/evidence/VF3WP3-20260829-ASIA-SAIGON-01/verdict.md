# VF3-WP3 verdict

PASS aim model and fire/release evidence (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF3-WP3)

Verify: pressed/held/released trace; 0 ammo không bắn; projectile collision
continuous (không xuyên vật thể ở tốc độ cao); aim pose/hit direction đúng.

DoD: pistol/SMG/shotgun khác nhau bằng data, không copy stat mù quáng.

## Run

- `run_id`: `VF3WP3-20260829-ASIA-SAIGON-01`
- `command_id`: `cmd.vf3-wp3.aim-fire.1`
- seed `7`, mode `vs2`, map `fx_aim_open`
- HOLD=pass DIRS=pass SEMI=pass AUTO=pass AMMO=pass MUZZLE=pass RECOIL=pass DATA=pass SWEEP=pass LIVE=pass REPLAY=match
- HOLD aiming=True spawns=0 real=True
- SEMI during=0 after=1 real=True
- AMMO shots=0 spawns=0 real=True
- MUZZLE dir_y=-1.0 real=True
- SWEEP past_wall=0 hp0=100.0 hp1=100.0 real=True
- events include bullet=True
- `USED_APPLY_FRAMES=508` attempted=508
- source_tree_sha256 `a433848db4df2fb5e3c929d6a463ffe873b938c9e9fa6536f1d88c7bd3c182ce`
- base_head `396b6b9aed4538d51c4dccdd06ba6a19a4152d44`
- Banners copy `AimCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_aim.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_aim.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_aim.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT 0 / 0 / 0 / 0. leftover Godot on product `--path` = 0.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption, not observed.
- Aim dirs stay `ledger:RL-AIM-DIRS` assumption, not observed.
- Semi release stays `ledger:RL-FIRE-SEMI` assumption, not observed.
- Auto cadence stays `ledger:RL-FIRE-AUTO` assumption, not observed.
- Empty ammo stays `ledger:RL-FIRE-AMMO` assumption, not observed.
- Muzzle stays `ledger:RL-FIRE-MUZZLE` assumption, not observed.
- Recoil/spread stay `ledger:RL-FIRE-RECOIL` assumption, not observed.
- Guns are ballistic, not hitscan (`ledger:RL-FIRE-BALLISTIC` assumption).
- Swept collision stays `ledger:RL-FIRE-SWEEP` assumption, not observed.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- No new in-game Y8 play this WP.
- Not Y8 parity. Not V0.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

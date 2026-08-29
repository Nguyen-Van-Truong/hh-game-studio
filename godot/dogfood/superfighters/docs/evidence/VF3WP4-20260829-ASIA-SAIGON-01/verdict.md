# VF3-WP4 verdict

PASS grenade / explosive evidence (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF3-WP4)

Verify: high-speed collision no tunneling; deterministic grenade trace;
owner không tự damage nếu rule cấm; explosion chỉ một lần; timeout cleanup.

DoD: bắn/ném có tác động quan sát được trong real window.

## Run

- `run_id`: `VF3WP4-20260829-ASIA-SAIGON-01`
- `command_id`: `cmd.vf3-wp4.explosive.1`
- seed `7`, mode `vs2`, map `fx_nade_open`
- HOLD=pass THROW=pass ARC=pass BOUNCE=pass FUSE=pass FALLOFF=pass OWNER=pass ONCE=pass TIMEOUT=pass SWEEP=pass DATA=pass LIVE=pass REPLAY=match
- HOLD aiming=True spawns=0 real=True
- THROW during=0 after=1 real=True
- OWNER hp0=100.0 hp1=100.0 real=True
- ONCE blasts=1 later=1 real=True
- TIMEOUT leftover=0 real=True
- FALLOFF near=31.4977219104767 far=10.4992389678955 real=True
- SWEEP past_wall=0 hp0=100.0 hp1=100.0 real=True
- events include nade+explosion=True
- `USED_APPLY_FRAMES=807` attempted=807
- source_tree_sha256 `f4612e56d399f181cdf8d75318c0ce158cc75eb3d51c403fa357ea7408acf7f1`
- base_head `d95d4d08a818bee1741b1c622090d8c25e3897a0`
- Banners copy `ExplosiveCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_explosive.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_explosive.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_explosive.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT 0 / 0 / 0 / 0. leftover Godot on product `--path` = 0.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Hold-to-throw stays `ledger:RL-NADE-HOLD` assumption, not observed.
- Arc stays `ledger:RL-NADE-ARC` assumption, not observed.
- Bounce stays `ledger:RL-NADE-BOUNCE` assumption, not observed.
- Fuse stays `ledger:RL-NADE-FUSE` assumption, not observed.
- Falloff stays `ledger:RL-NADE-FALLOFF` assumption, not observed.
- Owner skip stays `ledger:RL-NADE-OWNER` assumption, not observed.
- One explosion stays `ledger:RL-NADE-ONCE` assumption, not observed.
- Timeout cleanup stays `ledger:RL-NADE-TIMEOUT` assumption, not observed.
- Swept nade collision stays `ledger:RL-NADE-SWEEP` assumption, not observed.
- Prop break stays `ledger:RL-NADE-PROP` deferred VF4.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption, not observed.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- No new in-game Y8 play this WP.
- Not Y8 parity. Not V0.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

# VF2-WP4 verdict

PASS dive, jump-kick, and fall evidence (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF2-WP4)

Verify: real input trace trên từng map archetype; projectile dodge, landing,
edge case ledge/pit; no infinite invulnerability.

DoD: dive/roll/kick distinguishable in snapshot, animation and hit events.

## Run

- `run_id`: `VF2WP4-20260829-ASIA-SAIGON-01`
- `command_id`: `cmd.vf2-wp4.dive-jump-kick.1`
- seed `1`, mode `vs2`, map `police`
- DIVE=pass KICK=pass TACKLE=pass FALL=pass PIT=pass DODGE=pass INVULN=pass DIST=pass MAPS=pass LIVE=pass REPLAY=match
- `USED_APPLY_FRAMES=1225` attempted=1225
- source_tree_sha256 `3e0b3ffb76bfab730a6c0753e64d073da530cf8c919fdb63803680fabc7c6134`
- base_head `29795b861be2bed5647652a01fd1185d0b28cf0b`
- Banners copy `DiveCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_dive.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_dive.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_dive.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT 0 / 0 / 0 / 0. leftover Godot on product `--path` = 0.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Sprint stays `ledger:RL-MOVE-SPRINT` assumption, not observed.
- Roll stays `ledger:RL-MOVE-ROLL` assumption, not observed.
- Dive stays `ledger:RL-MOVE-DIVE` assumption, not observed.
- Jump-kick stays `ledger:RL-MOVE-JUMP-KICK` assumption, not observed.
- Fall stays `ledger:RL-MOVE-FALL` assumption, not observed.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- No new in-game Y8 play this WP.
- Not Y8 parity. Not V0.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

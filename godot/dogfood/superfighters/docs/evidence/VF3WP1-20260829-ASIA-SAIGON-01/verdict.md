# VF3-WP1 verdict

PASS melee phase / hitbox evidence (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF3-WP1)

Verify: frame-by-frame trace cho miss/hit/behind/above/below; one hit per
active window; damage/knockback snapshot; pause trong attack an toàn.

DoD: melee không còn là distance check đơn giản không có phase.

## Run

- `run_id`: `VF3WP1-20260829-ASIA-SAIGON-01`
- `command_id`: `cmd.vf3-wp1.melee-phases.1`
- seed `7`, mode `vs2`, map `fx_melee_close`
- HIT=pass MISS=pass BEHIND=pass ABOVE=pass BELOW=pass ONCE=pass SNAP=pass PAUSE=pass LIVE=pass REPLAY=match PHASES=pass REACH=pass FF=pass HITSTOP=pass CROUCH=pass KICK=pass
- HIT hp0=100.0 hp1=90.0 damage=10.0 expected=10.0 press_phase=startup real=True
- MISS geometry kinds + unchanged HP=True
- ONCE hit_events=1 damage=10.0 real=True
- PAUSE tick 9->9 phase startup real=True
- REACH fists_miss=True pipe_hit=True
- FF vs1_block=True vs2_hit=True
- HITSTOP left=1 clock 13->14
- events kinds include startup/active/hit=True
- `USED_APPLY_FRAMES=930` attempted=931
- source_tree_sha256 `bb7101a82ae1c4f45f15628657e9e880a5e202835a7a2cc8460e681af15f1ac4`
- base_head `cce07f4c50dda47fd68b1978f525c3eb6659edfc`
- Banners copy `CombatCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_combat.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_combat.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_combat.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT 0 / 0 / 0 / 0. leftover Godot on product `--path` = 0.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Phases stay `ledger:RL-HIT-PHASES` assumption, not observed.
- Boxes stay `ledger:RL-HIT-BOX` assumption, not observed.
- Friendly-fire stays `ledger:RL-HIT-FF` assumption, not observed.
- Hitstop stays `ledger:RL-HIT-HITSTOP` assumption, presentation only.
- Kick stays `ledger:RL-MOVE-JUMP-KICK` assumption, not observed.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- No new in-game Y8 play this WP.
- Not Y8 parity. Not V0.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

# VF4-WP2 verdict

PASS breakable glass/wood and throwable/shootable props (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF4-WP2)

Verify: one break event, deterministic debris count, projectile passes only
after break, no collision ghost; screenshot before/after and replay hash.

DoD: destructibility changes tactics, not cosmetic-only animation.

## Run

- `run_id`: `VF4WP2-20260829-ASIA-SAIGON-01`
- `command_id`: `cmd.vf4-wp2.break.1`
- seed `7`, mode `vs2`, map `fx_break_cover`
- DATA=pass BREAK=pass DEBRIS=pass PASS=pass GHOST=pass MELEE=pass SHOVE=pass THROW=pass TACTIC=pass LIVE=pass REPLAY=match
- BREAK events=1 real=True
- DEBRIS count=6 real=True
- PASS blocked_before=True p2_mid=100.0 p2_after=82.0 real=True
- GHOST cover_after=False real=True
- TACTIC lane_opens=True real=True
- events kinds include break=True
- window screenshot before=True after=True
- `USED_APPLY_FRAMES=880` attempted=880
- source_tree_sha256 `66347a499b99748dcca34ac9db327606ad21e519d9a93ed27e4a6cd2d0afa860`
- base_head `a1d1e05f27fe8525540ebc3daaae9e48ceacaa27`
- Banners copy `BreakCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_break.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_break.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_break.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT 0 / 0 / 0 / 0. leftover Godot on product `--path` = 0.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Break / material / debris stay `ledger:RL-PROP-BREAK` assumption.
- Shove / throw stay `ledger:RL-PROP-DYNAMIC` assumption.
- `ledger:RL-NADE-PROP` stays `deferred`. Nades do not destroy props this WP.
- Explosive chain stays unimplemented (`ledger:RL-PROP-EXPL`).
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption, not observed.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Live maps still paint `c`/`b` as tiles; this WP does not migrate them.
- Official throw/shove uses `#` floors only. The VF3-WP4 `=` bounce residual is unchanged.
- Original glass/debris art only. Not a VF7 presentation rewrite. Not a Y8 rip.
- No new in-game Y8 play this WP.
- Not Y8 parity. Not V0.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

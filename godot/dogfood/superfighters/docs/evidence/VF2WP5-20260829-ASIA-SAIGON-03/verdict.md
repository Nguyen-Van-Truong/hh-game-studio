# VF2-WP5 verdict

PASS ladder, ledge, and drop-through evidence (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF2-WP5)

Verify: traverse up/down/all four directions on every map fixture; no stuck,
teleport or ladder climb through solid; replay hash stable.

DoD: topology can actually be navigated, not merely drawn.

## Run

- `run_id`: `VF2WP5-20260829-ASIA-SAIGON-03`
- `command_id`: `cmd.vf2-wp5.ladder-ledge.3`
- seed `1`, mode `vs2`, map `fx_ladder`
- LADDER=pass LEDGE=pass DROP=pass BLOCK=pass DIRS=pass MAPS=fixtures_only STUCK=pass CONTACT=pass LIVE=pass REPLAY=match
- LEDGE boarded=True on_floor=True stand_dist=2.236 end=(150.999969482422, 35.9999389648438) stand=(152.0, 34.0) idle_wedged=False pose=idle
- DROP y0=35.9991302490234 y1=99.9965286254883 dy=63.997 eps=8.0 fell=True
- DIRS measured displacements=True
- events kinds include drop_through/ledge_grab/ledge_recover=True
- MAPS stage_navigated=false (fixtures-only; rooftops/storage/police/hazardous not claimed)
- `USED_APPLY_FRAMES=2614` attempted=2614
- source_tree_sha256 `40edb0195cf027e0f9d0a0be0463ff78d0a4e5ee6c791afbe99b0b6773e7f4df`
- base_head `66a8ca8ac885c48796228de3566e2aa83c0932b5`
- Banners copy `TraversalCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_traversal.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_traversal.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_traversal.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT 0 / 0 / 0 / 0. leftover Godot on product `--path` = 0.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Ladder stays `ledger:RL-MOVE-LADDER` assumption, not observed.
- Ledge stays `ledger:RL-MOVE-LEDGE` assumption, not observed.
- Drop stays `ledger:RL-MOVE-DROP` assumption, not observed.
- InputFrame action `ledge` stays reserved.
- Sprint / roll / dive / kick / fall stay assumption.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- No new in-game Y8 play this WP.
- Not Y8 parity. Not V0.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

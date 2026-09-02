# VF4-WP4 verdict

PASS doors, elevators/moving platforms, and traversal triggers (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF4-WP4)

Verify: actors ride without tunneling, platform carries/drop safely, door
blocks/opens at correct state, fixed-tick replay equal.

DoD: vertical map routes are functional rather than decorative.

## Run

- `run_id`: `VF4WP4-20260830-ASIA-SAIGON-01`
- `command_id`: `cmd.vf4-wp4.moving.1`
- seed `7`, mode `vs2`, map `fx_move_yard` display **Relay Shaft**
- DATA=pass RIDE=pass CARRY=pass DROP=pass DOOR=pass TRIGGER=pass PAUSE=pass RESET=pass LIVE=pass REPLAY=match
- RIDE y0=160.0 y1=68.0 tunnels=0 real=True
- CARRY ly0=180.0 ly1=84.0 boards=2 real=True
- DROP y_end=87.1818161010742 ly_end=180.0 unboards=3 real=True
- DOOR x_block=234.992477416992 x_open=339.111267089844 real=True
- TRIGGER events=1 real=True
- events kinds include door/board/trigger=True kinds=['board', 'door_open', 'ledge_grab', 'mover_spawn', 'platform_call', 'trigger_fire', 'unboard']
- window stills setup=True door=True ride=True drop=True pairwise_distinct=True
- still hashes: {'move_setup_1280x720.png': {'sha256': 'f944c13e3ff30b250cd7e9d808a682ab3512c9763aff69a15d5d391135bb946c', 'bytes': 35001}, 'move_door_1280x720.png': {'sha256': '51e67ae77a08eab87d3da3c47546810a4f0a9d84f744d53a482f8b0d142240ad', 'bytes': 32492}, 'move_ride_1280x720.png': {'sha256': '48d5f730ac3e94b5d51441933e206bd6086173202919a02df2589a9ed94c830c', 'bytes': 34748}, 'move_drop_1280x720.png': {'sha256': '268cf2a2c5c9984924bb3df03a0de4f1b4fbd0557876f858b2e7a244df50dc69', 'bytes': 34820}}
- still errors: []
- `USED_APPLY_FRAMES=1794` attempted=1795
- source_tree_sha256 `1b961f9e2cc2534710a3f9afdc6e80c866ec4d069965cdba6dc97106b55ccc22`
- base_head `e66c18e9bd4116a5d2fd92544167a74ddf92ea57`
- Banners copy `MovingCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_moving.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_moving.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_moving.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT 0 / 0 / 0 / 0. leftover Godot on product `--path` = 0.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Door / lift / board / trigger stay assumption (`ledger:RL-WORLD-DOOR`,
  `ledger:RL-WORLD-LIFT`, `ledger:RL-WORLD-BOARD`,
  `ledger:RL-WORLD-TRIGGER`).
- `ledger:RL-NADE-PROP` stays `deferred`.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption, not observed.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Live maps still paint `c`/`b` as tiles; this WP does not migrate them.
- Water is not selected (VF4-WP5).
- Original door/lift/trigger art only. Not a VF7 presentation rewrite. Not a Y8 rip.
- No new in-game Y8 play this WP.
- Not Y8 parity. Not V0.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

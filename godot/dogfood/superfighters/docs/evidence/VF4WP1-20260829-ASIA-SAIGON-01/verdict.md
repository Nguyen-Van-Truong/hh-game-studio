# VF4-WP1 verdict

PASS world/prop schema and collision ownership (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF4-WP1)

Verify: schema rejects missing collision/visual; prop snapshot/hash stable;
no orphan after restart; editor/runtime paths remain inside product root.

DoD: map authoring không cần hard-code từng node trong GameSession.

## Run

- `run_id`: `VF4WP1-20260829-ASIA-SAIGON-01`
- `command_id`: `cmd.vf4-wp1.world.1`
- seed `7`, mode `vs2`, map `fx_world_open`
- SCHEMA=pass LAYERS=pass SPAWN=pass HASH=pass ORPHAN=pass PATH=pass PRESENT=pass AUTHOR=pass DATA=pass LIVE=pass REPLAY=match
- SCHEMA reject_collision=True reject_visual=True real=True
- SPAWN count=6 kinds=['breakable', 'dynamic', 'explosive', 'one-way', 'pickup', 'static'] real=True
- HASH idle=True reboot=True real=True
- ORPHAN leftover=0 old=6 real=True
- PATH traversal=True absolute=True real=True
- PRESENT despawn=presentation cannot despawn real=True
- AUTHOR rooftops=0 fixture=6 real=True
- events kinds include prop_spawn=True
- window screenshot=True
- `USED_APPLY_FRAMES=116` attempted=116
- source_tree_sha256 `c6632f0bb0e297ad343d99ed7323f6f1b8f6d1156bcd94aeceee77ceabc1f1cd`
- base_head `7747ad274c084d644a23c4681d4b2326b5b36f94`
- Banners copy `WorldCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_world.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_world.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_world.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT 0 / 0 / 0 / 0. leftover Godot on product `--path` = 0.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- World schema / layers / ownership stay assumption
  (`ledger:RL-WORLD-SCHEMA`, `ledger:RL-WORLD-LAYERS`,
  `ledger:RL-WORLD-OWN`).
- Static / dynamic / one-way / pickup stay assumption.
  Dynamic throw waits VF4-WP2.
- Breakable is schema only (`ledger:RL-PROP-BREAK`). Destroy waits VF4-WP2.
- Explosive prop is schema only (`ledger:RL-PROP-EXPL`). Chain waits VF4-WP3.
- `ledger:RL-NADE-PROP` stays `deferred`.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption, not observed.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Live maps still paint `c`/`b` as tiles; this WP does not migrate them.
- No new in-game Y8 play this WP.
- Not Y8 parity. Not V0.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

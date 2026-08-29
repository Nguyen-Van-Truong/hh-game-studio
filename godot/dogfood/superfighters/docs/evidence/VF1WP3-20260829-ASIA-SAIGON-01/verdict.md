# VF1-WP3 verdict

PASS official InputFrame record/replay harness.
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8)

Verify: replay original và replay lần hai cùng hash; đổi một key làm
fail; không teleport/force_kill trong official trace.

DoD: mọi bug parity có thể ghi thành trace tái hiện được.

## What ran (2026-08-29 Asia/Saigon)

- Official traces (`title→fight`, walk/jump/crouch, fire/throw,
  death/win/restart) replayed twice through `apply_frames(InputFrame)`.
  Snapshot hashes every 15 ticks, final state, and event ledger matched.
- Mutating one key on `walk_jump_crouch` changed the replay hash.
- Official JSON has no `teleport` / `force_kill`. Fixture replay logs
  those ops and is rejected if `kind` is rewritten to official.
- Live record: `Input.action_press` → `read_player_frame` → typed
  InputFrame → replay.
- 60 Hz is product V-A14 / `ledger:RL-SIM-FIXED-60` (`assumption`).
  Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` (`assumption`).
  Roll/dive stay `ledger:RL-MOVE-ROLL-DIVE` (`unavailable`).
- Title remains **Vault Fighters**.

## Verify

```
python godot/dogfood/superfighters/tests/check_golden_traces.py
$godot --headless --path godot/dogfood/superfighters --script res://tests/run_golden_traces.gd
$godot --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT 0 / 0 / 0. leftover Godot on product `--path` = 0.

## Gaps (none blocking this WP)

- Window replay is supported (`HH_VF_TRACE_WINDOW=1` / harness
  `--window`) but official leftover-0 verify is headless.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

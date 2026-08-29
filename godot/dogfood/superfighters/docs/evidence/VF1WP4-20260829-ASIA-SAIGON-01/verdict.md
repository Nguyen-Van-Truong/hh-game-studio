# VF1-WP4 verdict

PASS runtime observe / checkpoint API.
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8)

Verify: snapshot trước/sau pause và restart; checkpoint restore hash đúng;
malformed/unauthorized request không mutate.

DoD: agent quan sát được game bằng dữ liệu có cấu trúc, không cần đoán từ UI.

## What ran (2026-08-29 Asia/Saigon)

- `observe` returns seed/map/mode/tick/pause_reason, actor/weapon/prop
  event channels, snapshot hash, and UI flags. Observe does not advance
  the clock.
- Snapshot hash is unchanged across authorized pause; observe reports
  `paused=true` and `pause_reason=agent`. Restart hash matches a fresh
  start (ledger:RL-RUNTIME-OBSERVE).
- `checkpoint.create` does not mutate the fight. After a walk,
  `checkpoint.restore` returns the captured snapshot hash.
- Malformed and unauthorized requests (wrong token, empty server token,
  path/`../` id) do not change tick, hash, pause, or P1 position.
- Responses redact tokens and password fields (V-A8).
- 60 Hz is product V-A14 / `ledger:RL-SIM-FIXED-60` (`assumption`).
  Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` (`assumption`).
  Roll/dive stay `ledger:RL-MOVE-ROLL-DIVE` (`unavailable`).
- Prop events are empty in this slice (no interactive props yet).
- Title remains **Vault Fighters**.

## Verify

```
python godot/dogfood/superfighters/tests/check_runtime_api.py
$godot --headless --path godot/dogfood/superfighters --script res://tests/run_runtime_api.gd
$godot --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT 0 / 0 / 0. leftover Godot on product `--path` = 0.

## Gaps (none blocking this WP)

- In-process API only; VF8-WP1 owns the live editor/MCP adapter.
- LOOP teleport still in `run_all` (V-A16 residual from VF1-WP3; not
  this DoD).
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

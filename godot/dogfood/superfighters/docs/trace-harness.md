# Vault Fighters — golden InputFrame traces (VF1-WP3)

Timezone: **Asia/Saigon**. Display title: **Vault Fighters**.
Product record/replay, not a Y8 play observation.

Does **not** claim Y8 parity, V0–V6, R9-WP4, G6, GX, or 60/60.

## What this WP ships

- Official traces under `tests/traces/official/` for title→fight,
  walk/jump/crouch, fire/throw, death/win/restart
- Fixture traces under `tests/traces/fixture/` may `teleport` /
  `force_kill` (V-A16: not official E2E)
- Record from real Godot `Input` via `InputActions.read_player_frame`
- Replay through `GameSession.apply_frames(InputFrame)` — not cmd-dict
  `step_fixed` (fixes the VF1-WP2 MATCH residual)
- Snapshot hash every N ticks (`snapshot_every=15`), final state, and
  event ledger

## Clock (ledger:RL-SIM-FIXED-60)

Class: `assumption`. **Do not** cite 60 Hz as “Y8-like”.
Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` (`assumption`).
Roll/dive stay `ledger:RL-MOVE-ROLL-DIVE` (`unavailable`).

## Official vs fixture

Official JSON must not contain `teleport` or `force_kill`. Replay of an
official trace that logs those events is FAIL. Fixture replay of those
ops is allowed and must be rejected if `kind` is rewritten to
`official`.

## Verify

```
python godot/dogfood/superfighters/tests/check_golden_traces.py
$godot --headless --path godot/dogfood/superfighters --script res://tests/run_golden_traces.gd
```

Window replay (not leftover-0 official):

```
python tools/godot/vf_trace_harness.py replay --window
```

Changing one InputFrame key on `walk_jump_crouch` must change the
replay hash. Two clean replays of each official file must match.

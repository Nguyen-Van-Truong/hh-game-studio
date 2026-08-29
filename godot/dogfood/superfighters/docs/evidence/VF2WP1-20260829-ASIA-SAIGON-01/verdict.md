# VF2-WP1 verdict

PASS real P1/P2/gamepad InputEvent mapping.
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8)

Verify: inject real InputEvent vào running window; trace P1/P2 độc lập;
gamepad smoke nếu thiết bị có, otherwise deterministic synthetic device
được đánh dấu non-hardware.

DoD: input behavior khớp ledger; không chỉ gọi `step_fixed` trực tiếp.

## What ran (2026-08-29 Asia/Saigon)

- Physical-keycode keyboard map matches listing rows
  `ledger:RL-CTRL-P1-MOVE`, `ledger:RL-CTRL-P1-PUNCH`,
  `ledger:RL-CTRL-P1-SHOOT`, `ledger:RL-CTRL-P1-NADE`,
  `ledger:RL-CTRL-P2-MOVE`, `ledger:RL-CTRL-P2-ATK`.
  F11 is not a fighter bind (`ledger:RL-CTRL-FULLSCREEN`).
- Analog dead-zone 0.25 (`ledger:RL-CTRL-DEADZONE`, `assumption`).
  Stick 0.10 does not hold; 0.85 does.
- Pressed / held / released edges are per-tick InputFrame diffs
  (`ledger:RL-SIM-INPUT-FRAME`).
- P1 pad is device 0, P2 pad is device 1
  (`ledger:RL-CTRL-DEVICE-SPLIT`). Device-0 joy does not fill P2;
  device-1 does not fill P1. Keyboard arrows vs WASD stay split.
- Title/Pause Controls remap UI saves `user://vf_input/remap.json`
  via temp+rename with schema hash (`ledger:RL-CTRL-REMAP`).
  F11 and same-device payloads are rejected.
- Official inject uses `Input.parse_input_event` + Viewport
  `push_input`. `used_step_fixed=0`, `used_action_press=0`.
  Live motion uses `GameSession.step_from_live_input` →
  `apply_frames(InputFrame)`.
- No hardware pad was connected. Official pad proof is a
  deterministic synthetic device marked non-hardware
  (`ledger:RL-CTRL-SYNTH-PAD`).
- Windowed run (`DISPLAY=Windows`) injected the same InputEvents
  into a real running window and quit leftover-0.
- 60 Hz is product V-A14 / `ledger:RL-SIM-FIXED-60` (`assumption`).
  Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` (`assumption`).
  Roll/dive stay `ledger:RL-MOVE-ROLL-DIVE` (`unavailable`).
- Title remains **Vault Fighters**.

## Verify

```
python godot/dogfood/superfighters/tests/check_input_map.py
$godot --headless --path godot/dogfood/superfighters --script res://tests/run_input_map.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_input_map.gd
$godot --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT 0 / 0 / 0 / 0. leftover Godot on product `--path` = 0.

## Gaps (none blocking this WP)

- Hold-to-aim / roll were not observed (VF1-WP1 did not observe
  them; this WP does not promote them).
- Hardware gamepad smoke is unproven (0 pads connected); synthetic
  path is the official leftover-0 proof.
- LOOP teleport residual remains in `run_all` (V-A16; not this DoD).
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

# VF1-WP2 verdict

PASS typed simulation schema + fixed 60 Hz clock.
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8)

Verify: cùng seed + trace tạo cùng hash trên >=3 runs; pause/resume không
nhảy tick; malformed frame bị reject.

DoD: simulation contract là nền cho replay và mọi gameplay WP.

## What ran (2026-08-29 Asia/Saigon)

- Same seed (`7`, vs1/rooftops) + scripted walk/crouch trace → identical
  SHA-256 snapshot hash on **3** fresh sessions.
- Pause + 2.0s wall `feed` + `step_fixed` while paused: tick unchanged.
  Resume zeros accum; next step is `t+1`.
- Malformed frames (missing tick, negative tick, `roll`, non-array
  `held`, NaN axis, tick mismatch) rejected; tick and P1 `x` unchanged.
- `snapshot()` / `snapshot_hash()` twice: same digest, no mutate.

## Honesty

- 60 Hz is product V-A14 / `ledger:RL-SIM-FIXED-60` (`assumption`).
  **Not** an observed Y8 clock.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` (`assumption`).
- Roll/dive stay `ledger:RL-MOVE-ROLL-DIVE` (`unavailable`) and are
  rejected if sent as InputFrame actions.
- Title remains **Vault Fighters**.

## Verify

```
python godot/dogfood/superfighters/tests/check_sim_contract.py
$godot --headless --path godot/dogfood/superfighters --script res://tests/run_sim_contract.gd
$godot --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT 0 / 0 / 0. leftover Godot on product `--path` = 0.

## Gaps (none blocking this WP)

- Official replay record/replay harness is VF1-WP3.
- VF1-WP1 `hashes.txt` ledger line was refreshed because this WP
  appended dated rows (ledger § “How later WPs must extend”).
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

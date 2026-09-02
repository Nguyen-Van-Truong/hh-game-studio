# VF2-WP3 verdict

PASS sprint, stamina, and roll with InputFrame traces.
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8)

Verify: trace tap timing; damage projectile trong/outside invuln; stamina
conservation; repeated roll cannot duplicate state/events.

DoD: roll có cảm giác/feedback và contract rõ, không chỉ đổi velocity.

## What ran (2026-08-29 Asia/Saigon)

- Double-tap same direction inside `tap_window` starts sprint
  (`ledger:RL-MOVE-SPRINT`, `assumption`). Late second tap stays walk.
- Stamina drains while sprinting, recovers while idle, and pays a
  flat roll cost. Values stay inside `[0, 100]`.
- Crouch-while-sprint or InputFrame `roll` starts a grounded roll
  (`ledger:RL-MOVE-ROLL`, `assumption`) with a distinct AABB, `roll`
  pose, HUD `ROLL`, SFX `last_id=roll`, and a procedural dust flash.
- Roll sets an invuln window. A real `Bullet` does not reduce HP
  inside that window and does reduce HP after it expires.
- `extinguish_fire()` increments on each successful roll start
  (`roll_extinguish` ledger event). VF4 fire is not implemented.
- Dead / paused / airborne / low-stamina rolls are rejected.
  Repeated roll presses keep `roll_seq` and `roll_start` unique.
- Official MATCH is `apply_frames` + live `parse_input_event`.
  `used_step_fixed=0`, `used_action_press=0`.
- 60 Hz is product V-A14 / `ledger:RL-SIM-FIXED-60` (`assumption`).
  Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` (`assumption`).
  Dive/kick stay `ledger:RL-MOVE-ROLL-DIVE` (`unavailable`).
  Roll is **not** marked `observed`.
- Title remains **Vault Fighters**.

## Verify

```
python godot/dogfood/superfighters/tests/check_sprint.py
$godot --headless --path godot/dogfood/superfighters --script res://tests/run_sprint.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_sprint.gd
$godot --headless --path godot/dogfood/superfighters --script res://tests/run_locomotion.gd
$godot --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT 0 / 0 / 0 / 0 / 0. leftover Godot on product `--path` = 0.

## Gaps (none blocking this WP)

- Hold-to-aim / roll were not observed on Y8 (no new play session).
  This WP ships product contracts as `assumption` only.
- Dive / kick / drop-through remain later WPs.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

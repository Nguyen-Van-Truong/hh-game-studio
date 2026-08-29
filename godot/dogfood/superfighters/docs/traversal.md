# Vault Fighters — ladder, ledge, drop (VF2-WP5)

Timezone: **Asia/Saigon**. Display title: **Vault Fighters**.
Product traversal contract. This file does **not** claim Y8 parity.

## What this WP ships

- Ladder attach / snap / climb / drop
  (`ledger:RL-MOVE-LADDER`, `assumption`)
- Ledge detection / hang / recover
  (`ledger:RL-MOVE-LEDGE`, `assumption`)
- One-way drop-through on crouch/down
  (`ledger:RL-MOVE-DROP`, `assumption`)
- Blocked climb into solid and quantized contact normals
- Temporary collision fixtures `fx_ladder`, `fx_block`, `fx_ledge`,
  `fx_drop`, `fx_cross` (not a VF5 map pass; not in `stage_ids`)

Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` (`assumption`).
Sprint / roll / dive / kick / fall stay assumption. InputFrame action
`ledge` stays reserved (no dedicated remap key). Y8 observation stays
`ledger:RL-MOVE-ROLL-DIVE` (`unavailable`). 60 Hz stays
`ledger:RL-SIM-FIXED-60` (`assumption`).

Official MATCH uses `GameSession.apply_frames` on typed `InputFrame`s.
Live window proof injects real `InputEvent`s (`parse_input_event`) and
steps with `step_from_live_input`.

`LADDER`, `LEDGE`, `DROP`, `BLOCK`, `DIRS`, `MAPS`, `STUCK`, `CONTACT`,
`LIVE`, and `REPLAY` banners copy `TraversalCases.outcome_*`
verdicts. They are not inferred from the absence of fail-substrings.
`DROP` requires a measured Y increase (`drop_fall_min`), not a
`drop_through` event alone. A short crouch on `=` stays crouched. Holding crouch past
`drop_hold_min` (0.25s) drops through. `DIRS` records left/right/up/down
displacement vs the start of each direction. `MAPS=fixtures_only`
means temporary fixtures only; rooftops/storage/police/hazardous are
**not** claimed as climbed. Ledge recover is velocity-stepped
(`recover_mode=velocity_step`, `recover_path=outside_then_board`):
climb outside the lip, then board. Official `LEDGE` requires
`on_floor`, distance to stand `< recover_board_eps`, pose not hang,
and idle after recover not wedged. It must not pass on grab + a
small rise + `max_step<16` alone. Per-frame step stays below one tile.
`USED_APPLY_FRAMES` is `used_apply_frames_succeeded` after a true
`apply_frames` return (attempted/succeeded are printed separately).

## Verify

```
python godot/dogfood/superfighters/tests/check_traversal.py
$godot --headless --path godot/dogfood/superfighters --script res://tests/run_traversal.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_traversal.gd
```

Traverse up/down and left/right on every fixture. No stuck mid-air,
no official teleport, no climb through solid. Replay the same seed +
frames twice.

## Evidence (V-A18 / §18.3)

Official `run_id`: `VF2WP5-20260829-ASIA-SAIGON-03`.
Layout is `.evidence/<run_id>/` plus review copies under
`docs/evidence/<run_id>/`.

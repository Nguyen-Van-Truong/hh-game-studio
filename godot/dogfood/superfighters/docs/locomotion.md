# Vault Fighters — locomotion baseline (VF2-WP2)

Timezone: **Asia/Saigon**. Display title: **Vault Fighters**.
Product movement contract. This file does **not** claim Y8 parity.

## What this WP ships

- Data-driven walk / jump / crouch / pit / camera constants in
  `data/sim/locomotion.json` (`ledger:RL-MOVE-LOCO-BASE`)
- Acceleration and friction (not instant walk speed)
- Variable jump (early release cuts upward velocity)
- Coyote time and jump buffer
- Crouch collision AABB smaller than stand
- Pit death from walking off a ledge (no official teleport)
- Arena-fit camera (`ledger:RL-CAM-ARENA`)
- Official 60 Hz `InputFrame` traces plus live `InputEvent` inject

Jump / crouch stay `ledger:RL-MOVE-JUMP-CROUCH` (`assumption`).
Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` (`assumption`).
Y8 observation stays `ledger:RL-MOVE-ROLL-DIVE` (`unavailable`).
Sprint / roll are owned by VF2-WP3 (`ledger:RL-MOVE-SPRINT` /
`ledger:RL-MOVE-ROLL`, `assumption`). Product dive / kick / fall
are VF2-WP4 (`assumption`). See `docs/dive-kick.md`.

## Clock (ledger:RL-SIM-FIXED-60)

Class: `assumption`. **Do not** cite 60 Hz as “Y8-like”.

Official MATCH uses `GameSession.apply_frames` on typed `InputFrame`s.
Live window proof injects real `InputEvent`s (`parse_input_event`) and
steps with `step_from_live_input`. Cases must not call cmd-dict
`step_fixed` or `Input.action_press`.

## Camera (ledger:RL-CAM-ARENA)

Class: `assumption`. No in-game Y8 frame was observed. Product camera
is `arena_fit`: center on the map, zoom so the whole arena is visible
in the designed 1280×720 view. Not a Y8 camera claim.

## Verify

```
python godot/dogfood/superfighters/tests/check_locomotion.py
$godot --headless --path godot/dogfood/superfighters --script res://tests/run_locomotion.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_locomotion.gd
```

Replay the same seed + frames twice; snapshot positions must stay
within epsilon `0.001`. Solid walls and one-way platforms must not be
tunneled.

## Evidence (V-A18 / §18.3)

Official correction-gate `run_id`: `VF2WP2-20260829-ASIA-SAIGON-03`.
Do **not** reuse `VF2WP2-20260829-ASIA-SAIGON-01` or
`VF2WP2-20260829-ASIA-SAIGON-02-continue`. Layout is
`.evidence/<run_id>/` plus review copies under
`docs/evidence/<run_id>/`.

`HASH2`, `TUNNEL`, and `CAMERA` banners copy
`LocomotionCases.outcome_*` verdicts. They are not inferred from the
absence of fail-substrings. Camera proof reads
`Viewport.get_visible_rect`, `Viewport.get_camera_2d`, and live
`Camera2D` zoom/position — not `GameSession.camera_framing()`.
`USED_APPLY_FRAMES` is `used_apply_frames_succeeded` after a true
`apply_frames` return (attempted/succeeded are printed separately).

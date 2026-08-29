# Vault Fighters — sprint, stamina, roll (VF2-WP3)

Timezone: **Asia/Saigon**. Display title: **Vault Fighters**.
Product movement contract. This file does **not** claim Y8 parity.

## What this WP ships

- Double-tap same direction inside `tap_window` starts sprint
  (`ledger:RL-MOVE-SPRINT`, `assumption`)
- Stamina drain while sprinting, recover while idle, flat roll cost
- Crouch-while-sprint or explicit InputFrame `roll` starts a committed
  roll (`ledger:RL-MOVE-ROLL`, `assumption`)
- Roll collision footprint, animation, SFX, HUD, and dust VFX
- Roll invulnerability window and `extinguish_fire` hook (VF4 fire
  is not implemented here)
- No roll when dead, paused, airborne, aiming, on a ladder, already
  rolling, or below the stamina cost
- Repeated roll presses do not duplicate `roll_start` / `roll_seq`

Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` (`assumption`).
Y8 observation stays `ledger:RL-MOVE-ROLL-DIVE` (`unavailable`).
Product dive / kick / fall are VF2-WP4 (`ledger:RL-MOVE-DIVE` /
`ledger:RL-MOVE-JUMP-KICK` / `ledger:RL-MOVE-FALL`, `assumption`).
See `docs/dive-kick.md`. 60 Hz stays `ledger:RL-SIM-FIXED-60`
(`assumption`).

## Clock (ledger:RL-SIM-FIXED-60)

Class: `assumption`. **Do not** cite 60 Hz as “Y8-like”.

Official MATCH uses `GameSession.apply_frames` on typed `InputFrame`s.
Live window proof injects real `InputEvent`s (`parse_input_event`) and
steps with `step_from_live_input`.

`TAP`, `STAMINA`, `ROLL`, `INVULN`, `DUP`, `LIVE`, and `REPLAY` banners
copy `SprintCases.outcome_*` verdicts. They are not inferred from the
absence of fail-substrings. `USED_APPLY_FRAMES` is
`used_apply_frames_succeeded` after a true `apply_frames` return
(attempted/succeeded are printed separately).

## Verify

```
python godot/dogfood/superfighters/tests/check_sprint.py
$godot --headless --path godot/dogfood/superfighters --script res://tests/run_sprint.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_sprint.gd
```

Tap timing, projectile damage inside/outside invuln, stamina
conservation, and repeated-roll uniqueness must pass. Replay the same
seed + frames twice.

## Evidence (V-A18 / §18.3)

Official `run_id`: `VF2WP3-20260829-ASIA-SAIGON-02`.
Do **not** reuse `VF2WP3-20260829-ASIA-SAIGON-01`. Layout is
`.evidence/<run_id>/` plus review copies under
`docs/evidence/<run_id>/`.

# Vault Fighters — dive, jump-kick, fall (VF2-WP4)

Timezone: **Asia/Saigon**. Display title: **Vault Fighters**.
Product movement contract. This file does **not** claim Y8 parity.

## What this WP ships

- Airborne sprint+crouch or explicit InputFrame `dive` starts a dive
  (`ledger:RL-MOVE-DIVE`, `assumption`)
- Grounded sprint+crouch remains a roll (`ledger:RL-MOVE-ROLL`)
- Aerial melee or InputFrame `kick` starts a jump-kick impulse
  (`ledger:RL-MOVE-JUMP-KICK`, `assumption`); grounded `kick` is blocked
- Dive tackle and kick hit apply a knockdown hook
- Landing from a dive is fall-immune (`ledger:RL-MOVE-FALL`,
  `assumption`); a high drop without dive can hurt
- Pit death still kills during a dive
- Dive invuln is a finite window; it is not infinite
- Distinct AABB, pose, HUD, SFX, and snapshot flags for roll / dive /
  kick

Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` (`assumption`).
Sprint / roll stay `ledger:RL-MOVE-SPRINT` / `ledger:RL-MOVE-ROLL`
(`assumption`). Y8 observation stays `ledger:RL-MOVE-ROLL-DIVE`
(`unavailable`). 60 Hz stays `ledger:RL-SIM-FIXED-60` (`assumption`).
Ledge stays reserved for VF2-WP5.

## Clock (ledger:RL-SIM-FIXED-60)

Class: `assumption`. **Do not** cite 60 Hz as “Y8-like”.

Official MATCH uses `GameSession.apply_frames` on typed `InputFrame`s.
Live window proof injects real `InputEvent`s (`parse_input_event`) and
steps with `step_from_live_input`.

`DIVE`, `KICK`, `TACKLE`, `FALL`, `PIT`, `DODGE`, `INVULN`, `DIST`,
`MAPS`, `LIVE`, and `REPLAY` banners copy `DiveCases.outcome_*`
verdicts. They are not inferred from the absence of fail-substrings.
`USED_APPLY_FRAMES` is `used_apply_frames_succeeded` after a true
`apply_frames` return (attempted/succeeded are printed separately).

## Verify

```
python godot/dogfood/superfighters/tests/check_dive.py
$godot --headless --path godot/dogfood/superfighters --script res://tests/run_dive.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_dive.gd
```

Real InputFrame traces on rooftops / storage / police / hazardous,
projectile dodge inside the dive window, landing, pit death, and
expired invuln must pass. Replay the same seed + frames twice.

## Evidence (V-A18 / §18.3)

Official `run_id`: `VF2WP4-20260829-ASIA-SAIGON-01`.
Layout is `.evidence/<run_id>/` plus review copies under
`docs/evidence/<run_id>/`.

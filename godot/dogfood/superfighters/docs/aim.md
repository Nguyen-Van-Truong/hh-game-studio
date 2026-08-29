# Vault Fighters — aim model and fire/release (VF3-WP3)

Timezone: **Asia/Saigon**. Display title: **Vault Fighters**.
Product aim/fire contract. This file does **not** claim Y8 parity.

## What this WP ships

- Hold-to-aim, release-to-fire for semi-auto
  (`ledger:RL-CTRL-HOLD-AIM` / `ledger:RL-FIRE-SEMI`, `assumption`)
- Up / down / side aim poses
  (`ledger:RL-AIM-DIRS`, `assumption`)
- Auto cadence while fire is held
  (`ledger:RL-FIRE-AUTO`, `assumption`)
- Data-driven muzzle origin
  (`ledger:RL-FIRE-MUZZLE`, `assumption`)
- Ammo exhaustion: 0 ammo does not fire
  (`ledger:RL-FIRE-AMMO`, `assumption`)
- Recoil impulse and deterministic pellet spread
  (`ledger:RL-FIRE-RECOIL`, `assumption`)
- Ballistic projectiles, not hitscan
  (`ledger:RL-FIRE-BALLISTIC`, `assumption`)
- Swept segment collision so high-speed shots do not tunnel
  (`ledger:RL-FIRE-SWEEP`, `assumption`). Spawn overlap with the
  floor tile the shooter stands on is uncollided (lift / step back);
  grid sweep counts first entry into a solid, not t=0 occupancy.
- Temporary collision fixtures `fx_aim_open`, `fx_aim_wall`
  (not a VF5 map pass)

Pistol, Uzi (SMG), and Shotgun numbers live in `data/sim/aim.json`.
They differ by cadence, auto/semi, pellets, spread, recoil, muzzle,
damage, and ammo. Values are product tuning, not copied Y8 stats.

Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` (`assumption`).
Sprint / roll / dive / fall stay assumption. Y8 observation stays
`ledger:RL-MOVE-ROLL-DIVE` (`unavailable`). 60 Hz stays
`ledger:RL-SIM-FIXED-60` (`assumption`). Controls stay remappable
via the existing VF2-WP1 map.

Official MATCH uses `GameSession.apply_frames` on typed `InputFrame`s.
Live window proof injects real `InputEvent`s (`parse_input_event`) and
steps with `step_from_live_input`.

`HOLD`, `DIRS`, `SEMI`, `AUTO`, `AMMO`, `MUZZLE`, `RECOIL`, `DATA`,
`SWEEP`, `LIVE`, and `REPLAY` banners copy `AimCases.outcome_*`
verdicts. They are not inferred from the absence of fail-substrings.
`HOLD` requires aim pose and zero `fire_spawn` while fire is held.
`SEMI` fires once on release only. `AUTO` fires on cadence while
held. `AMMO` is zero shots at 0 ammo. `SWEEP` is a 4000 px/s
ballistic that stops at Cover Wall. `USED_APPLY_FRAMES` is
`used_apply_frames_succeeded` after a true `apply_frames` return
(attempted/succeeded are printed separately).

## Verify

```
python godot/dogfood/superfighters/tests/check_aim.py
$godot --headless --path godot/dogfood/superfighters --script res://tests/run_aim.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_aim.gd
```

Pressed/held/released fire traces. 0 ammo does not fire. High-speed
projectile does not tunnel. Aim pose and hit direction match.

## Evidence (V-A18 / §18.3)

Official `run_id`: `VF3WP3-20260829-ASIA-SAIGON-01`.
Layout is `.evidence/<run_id>/` plus review copies under
`docs/evidence/<run_id>/`.

# Vault Fighters — grenade / explosive physics (VF3-WP4)

Timezone: **Asia/Saigon**. Display title: **Vault Fighters**.
Product grenade contract. This file does **not** claim Y8 parity.

## What this WP ships

- Hold-to-aim a throw, release-to-throw
  (`ledger:RL-NADE-HOLD`, `assumption`)
- Ballistic arc with data gravity
  (`ledger:RL-NADE-ARC`, `assumption`)
- Floor / wall bounce with rest damping
  (`ledger:RL-NADE-BOUNCE`, `assumption`)
- Fuse ticks then one explosion
  (`ledger:RL-NADE-FUSE` / `ledger:RL-NADE-ONCE`, `assumption`)
- Radial damage falloff and knock
  (`ledger:RL-NADE-FALLOFF`, `assumption`)
- Owner does not self-damage when the rule forbids it
  (`ledger:RL-NADE-OWNER`, `assumption`)
- Timeout cleanup so a leftover nade leaves the array
  (`ledger:RL-NADE-TIMEOUT`, `assumption`)
- Swept segment collision so a high-speed nade does not tunnel
  (`ledger:RL-NADE-SWEEP`, `assumption`)
- Explosion event carries `prop_break=deferred_vf4`
  (`ledger:RL-NADE-PROP`, deferred; no prop destroy this WP)

Numbers live in `data/sim/explosive.json`. They are product tuning,
not copied Y8 stats. Hold-to-aim stays
`ledger:RL-CTRL-HOLD-AIM` (`assumption`). 60 Hz stays
`ledger:RL-SIM-FIXED-60` (`assumption`). Y8 observation stays
`ledger:RL-MOVE-ROLL-DIVE` (`unavailable`).

Temporary collision fixtures: `fx_nade_open`, `fx_nade_wall`,
`fx_nade_blast` (not a VF5 map pass). Display names are original
(Nade Lane / Nade Cover / Blast Pocket).

Official MATCH uses `GameSession.apply_frames` on typed `InputFrame`s.
Live window proof injects real `InputEvent`s (`parse_input_event`) and
steps with `step_from_live_input`.

`HOLD`, `THROW`, `ARC`, `BOUNCE`, `FUSE`, `FALLOFF`, `OWNER`, `ONCE`,
`TIMEOUT`, `SWEEP`, `DATA`, `LIVE`, and `REPLAY` banners copy
`ExplosiveCases.outcome_*` verdicts. They are not inferred from the
absence of fail-substrings. `USED_APPLY_FRAMES` is
`used_apply_frames_succeeded` after a true `apply_frames` return.

## Verify

```
python godot/dogfood/superfighters/tests/check_explosive.py
$godot --headless --path godot/dogfood/superfighters --script res://tests/run_explosive.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_explosive.gd
```

High-speed collision does not tunnel. Grenade traces replay equal.
Owner is not self-damaged. Explosion fires once. Timeout cleans up.

## Evidence (V-A18 / §18.3)

Official `run_id`: `VF3WP4-20260829-ASIA-SAIGON-01`.
Layout is `.evidence/<run_id>/` plus review copies under
`docs/evidence/<run_id>/`.

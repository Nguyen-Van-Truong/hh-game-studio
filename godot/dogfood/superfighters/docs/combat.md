# Vault Fighters — melee phases and hitboxes (VF3-WP1)

Timezone: **Asia/Saigon**. Display title: **Vault Fighters**.
Product combat contract. This file does **not** claim Y8 parity.

## What this WP ships

- Startup / active / recovery attack phases
  (`ledger:RL-HIT-PHASES`, `assumption`)
- AABB hitbox / hurtbox overlap, not a same-tick distance check
  (`ledger:RL-HIT-BOX`, `assumption`)
- Mode-scoped friendly-fire
  (`ledger:RL-HIT-FF`, `assumption`)
- Presentation hitstop that does not freeze `SimClock`
  (`ledger:RL-HIT-HITSTOP`, `assumption`)
- Crouch melee style and aerial jump-kick hitbox
  (`ledger:RL-MOVE-JUMP-KICK`, `assumption`)
- Temporary collision fixtures `fx_melee_close`, `fx_melee_far`,
  `fx_melee_behind`, `fx_melee_above`, `fx_melee_below`, `fx_melee_mid`
  (not a VF5 map pass)

Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` (`assumption`).
Sprint / roll / dive / fall stay assumption. Y8 observation stays
`ledger:RL-MOVE-ROLL-DIVE` (`unavailable`). 60 Hz stays
`ledger:RL-SIM-FIXED-60` (`assumption`).

Official MATCH uses `GameSession.apply_frames` on typed `InputFrame`s.
Live window proof injects real `InputEvent`s (`parse_input_event`) and
steps with `step_from_live_input`.

`HIT`, `MISS`, `BEHIND`, `ABOVE`, `BELOW`, `ONCE`, `SNAP`, `PAUSE`,
`LIVE`, `REPLAY`, `PHASES`, `REACH`, `FF`, `HITSTOP`, `CROUCH`, and
`KICK` banners copy `CombatCases.outcome_*` verdicts. They are not
inferred from the absence of fail-substrings. `HIT` requires an HP
delta equal to fists damage after a startup press tick (HP unchanged
in startup). Miss cases require unchanged HP plus
`Combat.classify_miss` geometry and zero hit events. `ONCE` is one
HP drop across the active window. `PAUSE` freezes tick/phase/HP mid
startup, then resume finishes the hit. `REACH` is the same mid-gap
spawn: fists miss, pipe connects. `USED_APPLY_FRAMES` is
`used_apply_frames_succeeded` after a true `apply_frames` return
(attempted/succeeded are printed separately).

## Verify

```
python godot/dogfood/superfighters/tests/check_combat.py
$godot --headless --path godot/dogfood/superfighters --script res://tests/run_combat.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_combat.gd
```

Frame-by-frame traces for miss/hit/behind/above/below. One hit per
active window. Damage/knockback snapshot. Pause during attack is
safe. Replay the same seed + frames twice.

## Evidence (V-A18 / §18.3)

Official `run_id`: `VF3WP1-20260829-ASIA-SAIGON-01`.
Layout is `.evidence/<run_id>/` plus review copies under
`docs/evidence/<run_id>/`.

# Vault Fighters — knockback, knockdown, invuln, disarm (VF3-WP2)

Timezone: **Asia/Saigon**. Display title: **Vault Fighters**.
Product combat-reaction contract. This file does **not** claim Y8 parity.

## What this WP ships

- Hit impulse and airborne launch
  (`ledger:RL-HIT-KNOCK`, `assumption`)
- Knockdown then get-up recovery, with chain-lock block
  (`ledger:RL-HIT-DOWN`, `assumption`)
- Exact-tick hit invulnerability (5 ticks on punch; knockdown
  covers down + get-up)
  (`ledger:RL-HIT-INVULN`, `assumption`)
- Punch (not kick) disarms a gun-holder; dropped item has a uid
  and can be picked once
  (`ledger:RL-HIT-DISARM`, `assumption`)
- Official death cause is only `damage` or `pit`

Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` (`assumption`).
Sprint / roll / dive / fall stay assumption. Y8 observation stays
`ledger:RL-MOVE-ROLL-DIVE` (`unavailable`). 60 Hz stays
`ledger:RL-SIM-FIXED-60` (`assumption`).

Official MATCH uses `GameSession.apply_frames` on typed `InputFrame`s.
Live window proof injects real `InputEvent`s (`parse_input_event`) and
steps with `step_from_live_input`.

`DAMAGE`, `KNOCK`, `AIR`, `DOWN`, `GETUP`, `INVULN`, `CHAIN`,
`DISARM`, `DROP`, `DEATH`, `EVENTS`, `LIVE`, and `REPLAY` banners
copy `ReactionCases.outcome_*` verdicts. They are not inferred from
the absence of fail-substrings. `INVULN` requires armed ticks equal
to `hit_invuln_ticks`, a projectile blocked inside the window, then
damage after expiry. `DROP` requires one uid that persists and is
consumed once. `DEATH` requires `cause=damage` from a death event,
not `script` / `force_kill`. `USED_APPLY_FRAMES` is
`used_apply_frames_succeeded` after a true `apply_frames` return.

## Verify

```
python godot/dogfood/superfighters/tests/check_reaction.py
$godot --headless --path godot/dogfood/superfighters --script res://tests/run_reaction.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_reaction.gd
```

Damage / knockdown / disarm traces. Invulnerability exact ticks.
Dropped item does not vanish or duplicate. Death cause only from a
valid event. States emit entry/exit events. Replay the same seed +
frames twice.

## Evidence (V-A18 / §18.3)

Official `run_id`: `VF3WP2-20260829-ASIA-SAIGON-01`.
Layout is `.evidence/<run_id>/` plus review copies under
`docs/evidence/<run_id>/`.

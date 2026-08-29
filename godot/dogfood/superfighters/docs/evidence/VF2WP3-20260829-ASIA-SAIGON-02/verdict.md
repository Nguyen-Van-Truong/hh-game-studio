# VF2-WP3 verdict

PASS sprint, stamina, and roll evidence (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF2-WP3)

Verify: trace tap timing; damage projectile trong/outside invuln; stamina
conservation; repeated roll cannot duplicate state/events.

DoD: roll có cảm giác/feedback và contract rõ, không chỉ đổi velocity.

## Run

- `run_id`: `VF2WP3-20260829-ASIA-SAIGON-02`
- `command_id`: `cmd.vf2-wp3.sprint-stamina-roll.2`
- seed `1`, mode `vs2`, map `police`
- TAP=pass STAMINA=pass ROLL=pass INVULN=pass DUP=pass LIVE=pass REPLAY=match
- `USED_APPLY_FRAMES=717` attempted=718
- source_tree_sha256 `7b923799c3aad6cf4cb55a51bd80f40f8a91aca130b584235f22eb7880aa0305`
- base_head `eb6973f49ccc32fdd6fdda803bef9ee3518771f0`
- Banners copy `SprintCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_sprint.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_sprint.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_sprint.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT 0 / 0 / 0 / 0. leftover Godot on product `--path` = 0.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Sprint stays `ledger:RL-MOVE-SPRINT` assumption, not observed.
- Roll stays `ledger:RL-MOVE-ROLL` assumption, not observed.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption.
- Dive/kick stay `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- No new in-game Y8 play this WP.
- Not Y8 parity. Not V0.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

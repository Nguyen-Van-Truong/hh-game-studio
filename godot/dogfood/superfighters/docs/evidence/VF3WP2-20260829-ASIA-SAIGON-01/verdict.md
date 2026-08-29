# VF3-WP2 verdict

PASS knockback / knockdown / invuln / disarm evidence (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF3-WP2)

Verify: damage/knockdown/disarm traces; invulnerability exact ticks;
dropped item không mất hoặc nhân đôi; death cause chỉ từ event hợp lệ.

DoD: các trạng thái có entry/exit event và replay hash.

## Run

- `run_id`: `VF3WP2-20260829-ASIA-SAIGON-01`
- `command_id`: `cmd.vf3-wp2.knock-disarm.1`
- seed `7`, mode `vs2`, map `fx_melee_close`
- DAMAGE=pass KNOCK=pass AIR=pass DOWN=pass GETUP=pass INVULN=pass CHAIN=pass DISARM=pass DROP=pass DEATH=pass EVENTS=pass LIVE=pass REPLAY=match
- DAMAGE hp0=100.0 hp1=90.0 damage=10.0 expected=10.0 real=True
- INVULN armed=5 expected=5 blocked=True expired=True real=True
- DISARM held_before=True holds_after=False pick 0->1 real=True
- DROP persist uid=1 after_pick=0 real=True
- DEATH cause=damage dead=True real=True
- events include knockdown_start/getup_end/invuln_start/disarm/item_drop=True
- `USED_APPLY_FRAMES=1038` attempted=1038
- source_tree_sha256 `bcec2614f997c79434fb77c01d977c981d7fe78ab81d68286c3cab67e0b5e742`
- base_head `e831f81ad3fb680562270bff53eab27e4cb9125a`
- Banners copy `ReactionCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_reaction.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_reaction.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_reaction.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT 0 / 0 / 0 / 0. leftover Godot on product `--path` = 0.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Knockback stays `ledger:RL-HIT-KNOCK` assumption, not observed.
- Knockdown/getup stay `ledger:RL-HIT-DOWN` assumption, not observed.
- Hit invuln stays `ledger:RL-HIT-INVULN` assumption, not observed.
- Punch disarm stays `ledger:RL-HIT-DISARM` assumption, not observed.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- No new in-game Y8 play this WP.
- Not Y8 parity. Not V0.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

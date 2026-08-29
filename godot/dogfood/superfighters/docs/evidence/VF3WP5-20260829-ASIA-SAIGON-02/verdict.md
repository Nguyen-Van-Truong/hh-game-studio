# VF3-WP5 verdict

PASS weapon roster / inventory evidence (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF3-WP5)

Verify: schema validation; every roster item spawns, equips, attacks, drops,
serializes; no gun loss when grenade/melee picked; ammo edge cases.

DoD: roster đủ để tạo chiến thuật đa dạng; values là tuning, không claim
original exact numbers.

## Run

- `run_id`: `VF3WP5-20260829-ASIA-SAIGON-02`
- `command_id`: `cmd.vf3-wp5.roster.2`
- seed `7`, mode `vs2`, map `fx_roster_open`
- SCHEMA=pass SPAWN=pass EQUIP=pass ATTACK=pass DROP=pass SERIALIZE=pass KEEP=pass AMMO=pass DATA=pass LIVE=pass REPLAY=match
- SPAWN spawned=11 ids=['baton', 'cinder', 'fists', 'grenade', 'knife', 'launcher', 'pipe', 'pistol', 'rifle', 'shotgun', 'uzi'] expected=11 real=True
- EQUIP ids=['baton', 'cinder', 'fists', 'grenade', 'knife', 'launcher', 'pipe', 'pistol', 'rifle', 'shotgun', 'uzi'] real=True
- ATTACK attacked=11 ids=['baton', 'cinder', 'fists', 'grenade', 'knife', 'launcher', 'pipe', 'pistol', 'rifle', 'shotgun', 'uzi'] real=True
- DROP ids=['baton', 'cinder', 'fists', 'grenade', 'knife', 'launcher', 'pipe', 'pistol', 'rifle', 'shotgun', 'uzi'] real=True
- KEEP melee=True nade=True power=True real=True
- SERIALIZE ids=['baton', 'cinder', 'fists', 'grenade', 'knife', 'launcher', 'pipe', 'pistol', 'rifle', 'shotgun', 'uzi'] hash_fields=True real=True
- AMMO empty=True reload=True roster_reserve=8 real=True
- events kinds include pickup/fire/throw=True
- window screenshot=True
- `USED_APPLY_FRAMES=563` attempted=563
- source_tree_sha256 `1ca8083c43dadf4ce766064c0d197ba5f2f046ca44157224c2648647fe38534d`
- base_head `eb5286a90b3ac5ade53640bc9ee55956d847437a`
- Banners copy `RosterCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_roster.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_roster.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_roster.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT 0 / 0 / 0 / 0. leftover Godot on product `--path` = 0.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Four slots stay `ledger:RL-ITEM-SLOTS-4` assumption, not observed.
- Roster stays `ledger:RL-ITEM-ROSTER` assumption; values are tuning.
- Pickup slot replace stays `ledger:RL-ITEM-PICK-SLOT` assumption, not observed.
- Keep-gun stays `ledger:RL-ITEM-KEEP-GUN` assumption, not observed.
- Ammo/reload stay `ledger:RL-ITEM-AMMO-RELOAD` assumption, not observed.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption, not observed.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- No new in-game Y8 play this WP.
- Not Y8 parity. Not V0.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

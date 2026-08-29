# VF3-WP5 weapon roster and inventory

Display title: **Vault Fighters**. This WP does **not** claim Y8 parity
and does **not** claim original exact numbers. Values are product
tuning. Official proof is `apply_frames` plus live InputEvent inject.
Clock is `ledger:RL-SIM-FIXED-60` (`assumption`).

Four slots stay `ledger:RL-ITEM-SLOTS-4` (`assumption`): melee,
firearm, explosive, power. The roster stays
`ledger:RL-ITEM-ROSTER` (`assumption`). Pickup replaces the matching
slot and drops the old item (`ledger:RL-ITEM-PICK-SLOT`,
`assumption`). A grenade / melee / power pickup does not strip the
gun (`ledger:RL-ITEM-KEEP-GUN`, `assumption`). Ammo, reload ticks,
cooldown, and weight live on each row
(`ledger:RL-ITEM-AMMO-RELOAD`, `assumption`). Weight does not change
VF2 locomotion this WP. Hold-to-aim stays
`ledger:RL-CTRL-HOLD-AIM` (`assumption`). Y8 roll/dive observation
stays `ledger:RL-MOVE-ROLL-DIVE` (`unavailable`).

## Roster (original names)

| id | name | slot | role |
|---|---|---|---|
| fists | Fists | melee | default |
| pipe | Pipe | melee | slow, long |
| knife | Knife | melee | fast, short |
| baton | Baton | melee | mid |
| pistol | Pistol | firearm | semi start gun |
| uzi | Uzi | firearm | SMG / auto |
| shotgun | Shotgun | firearm | pellet fan |
| rifle | Longarm | firearm | precision |
| launcher | Thumper | firearm | heavy slug |
| grenade | Grenade | explosive | fuse blast |
| cinder | Cinder Flask | power | fire / area throw |

Start kit stays fists + pistol×12 + 3 grenades. Empty power.
Fists are default-equip **and** a world spawn. Official proof is
11/11 spawn, equip, attack, drop, and serialize. Pickup-replace
drops the old item (including fists) with one uid. Grenade and
Cinder Flask are singleton slots, so their drop uses the same
`_drop_specific` path via `drop_held_slot`. Fighter snapshot rows
hash `explosive` / `power` / `reserve` / `reload`. Rifle reload
copies reserve/mag from roster data. Values stay tuning.

## Data

- Gate: `data/weapons/schema.json`
- Roster: `data/weapons/roster.json`
- Loader: `src/data/weapons/roster.gd`
- Slots: `src/data/weapons/inventory.gd`
- Gun fire numbers also stay in `data/sim/aim.json` (VF3-WP3)
- Throw numbers also stay in `data/sim/explosive.json` (VF3-WP4)

## Official run

`VF3WP5-20260829-ASIA-SAIGON-02` / `cmd.vf3-wp5.roster.2`

Prior remint `VF3WP5-20260829-ASIA-SAIGON-01` is not reused.

```
python godot/dogfood/superfighters/tests/check_roster.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_roster.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_roster.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

# VF5-WP3 verdict

PASS Pallet Annex warehouse/storage-like arena (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF5-WP3)

Verify: cover blocks then breaks, cargo interacts, all spawns reachable,
camera fits, weapon respawn positions safe.

DoD: close-quarters cover and vertical ambushes are functional.

## Run

- `run_id`: `VF5WP3-20260830-ASIA-SAIGON-01`
- `command_id`: `cmd.vf5-wp3.pallet-annex.1`
- seed `13`, mode `vs2`, map `storage` display **Pallet Annex**
- NAME=pass COVER=pass CARGO=pass SPAWN=pass CAMERA=pass WEAPON=pass P1=pass P2=pass BOT=pass ZONE=pass DOOR=pass LIVE=pass REPLAY=match
- LIVE hud=Pallet Annex real=True
- P1 hits={'east_catwalk': True, 'east_floor': True, 'mid_catwalk': True, 'mid_floor': True, 'office_loft': True, 'west_catwalk': True, 'west_floor': True} P2 hits={'mid_catwalk': True, 'mid_floor': True} BOT hits={'mid_catwalk': True, 'mid_floor': True}
- live_reach p1_all=True climb_up_on_ladder=True office_standing=True east_catwalk=True
- catwalk_still={'alive': True, 'allow_lose': False, 'climbing': False, 'hanging': False, 'lose_visible': False, 'on_floor': True, 'on_ladder': False, 'x': 401.834594726563, 'y': 19.9934940338135, 'zone': 'west_catwalk'} cover_still={'alive': True, 'allow_lose': False, 'climbing': False, 'hanging': False, 'lose_visible': False, 'on_floor': True, 'on_ladder': False, 'x': 216.0, 'y': 163.98112487793, 'zone': 'west_floor'} cargo_still={'alive': True, 'allow_lose': False, 'climbing': False, 'hanging': False, 'lose_visible': False, 'on_floor': True, 'on_ladder': False, 'x': 410.813049316406, 'y': 19.813081741333, 'zone': 'west_catwalk'} office_still={'alive': True, 'allow_lose': False, 'climbing': False, 'hanging': False, 'lose_visible': False, 'on_floor': True, 'on_ladder': False, 'x': 599.389099121094, 'y': 163.813125610352, 'zone': 'office_loft'}
- COVER blocked_before=True breaks=1 real=True
- CARGO hung_before=True drops=1 real=True
- CAMERA covers=True WEAPON homes=4
- events kinds include name/zone/p1/cover/cargo=True kinds=['ware_bot', 'ware_camera', 'ware_cargo', 'ware_cover', 'ware_door', 'ware_live', 'ware_name', 'ware_p1', 'ware_p2', 'ware_replay', 'ware_weapon', 'ware_zone', 'ware_zone_hit']
- window stills pairwise_distinct=True
- still hashes: {'warehouse_setup_1280x720.png': {'sha256': '5ab11c0bf61753b62d427cfc73f5dcbe5622f1545fc1b616d2c124ea47bac807', 'bytes': 36802}, 'warehouse_title_1280x720.png': {'sha256': 'eae721a6354215abd37e857e1bb4b15654e4fbb236462866037bbdcb84821aec', 'bytes': 47831}, 'warehouse_catwalk_1280x720.png': {'sha256': '767ea721ab82145e1aea36f5239340d730bf9f8f5c9c1ce5130bd5eddf60f8ff', 'bytes': 51024}, 'warehouse_cover_1280x720.png': {'sha256': '50492d1e727eac7660255a07938b35f4b4dc7e2ab275a994f3d121d31bf7ce51', 'bytes': 50948}, 'warehouse_cargo_1280x720.png': {'sha256': 'c259a07c863bf245e97d257831b395375a2f7af78c6a7fb9d09f325cedd857d4', 'bytes': 51027}, 'warehouse_office_1280x720.png': {'sha256': 'a316abdc201f2a3789b29202bc94df8cbe29dd4c8bc6c018afcc50e1aed1a2d7', 'bytes': 51027}}
- still errors: []
- `USED_APPLY_FRAMES=2647` attempted=2647
- source_tree_sha256 `e24d46bf2d2d90ea4739377d6777ecab9f822344531e3b2991be10cc90878649`
- base_head `535e29dade4f215d8beadc5181a21ebbd868dee8`
- Banners copy `WarehouseCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_warehouse.py
python godot/dogfood/superfighters/tests/check_map.py
python godot/dogfood/superfighters/tests/check_rooftop.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_warehouse.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_warehouse.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT 0 / 0 / 0 / 0. leftover Godot on product `--path` = 0.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Pallet Annex topology stays assumption (`ledger:RL-MAP-PALLET`).
- Jump envelope is product tuning (dx=10 / dy=4); live apex is ~3.4 tiles.
- ZONE / P1 / P2 / BOT / SPAWN are live body positions during apply_frames.
  MapGraph is a helper only. Official routes hold `up` on ladder cells.
- `ledger:RL-NADE-PROP` stays `deferred`.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption, not observed.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Live `c`/`b` still paint as tiles. This WP placed original breakable
  cover, hanging cargo, door, and lift on Pallet Annex only.
- Machines / water / toxic stay fixture-only. Door/lift are placed here
  because VF5-WP3 asks for them.
- Skyline Relay is unchanged. Display names Police Station / Hazardous
  stay `ledger:RL-DELTA-MAP-NAMES` debt until VF5-WP4+.
- No new in-game Y8 play this WP. Not a copied billboard or Y8 collision map.
- Not Y8 parity. Not V0. No legal self-conclusion that the layout is
  close enough to Y8 to ship.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

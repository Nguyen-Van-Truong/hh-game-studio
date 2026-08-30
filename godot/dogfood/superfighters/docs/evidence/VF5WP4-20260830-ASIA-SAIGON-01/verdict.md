# VF5-WP4 verdict

PASS Signal Court station-like arena (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF5-WP4)

Verify: traversal graph, machine event, safe floor collision, no pit spawn,
screenshot and trace for each floor.

DoD: multi-route station fight, not a flat rectangular grid.

## Run

- `run_id`: `VF5WP4-20260830-ASIA-SAIGON-01`
- `command_id`: `cmd.vf5-wp4.signal-court.1`
- seed `14`, mode `vs2`, map `police` display **Signal Court**
- NAME=pass GRAPH=pass MACHINE=pass FLOOR=pass SPAWN=pass COVER=pass DOOR=pass CAMERA=pass P1=pass P2=pass BOT=pass ZONE=pass LIVE=pass REPLAY=match
- LIVE hud=Signal Court real=True
- P1 hits={'court_ground': True, 'court_low': True, 'court_mid': True, 'east_hall': True, 'east_mid': True, 'east_top': True, 'sky_bridge': True, 'west_hall': True, 'west_loft': True} P2 hits={'court_ground': True, 'court_low': True, 'west_hall': True, 'west_loft': True} BOT hits={'east_hall': True, 'east_mid': True, 'east_top': True}
- live_reach p1_all=True climb_up_on_ladder=True east_top=True
- court_still={'alive': True, 'allow_lose': False, 'climbing': False, 'hanging': False, 'lose_visible': False, 'on_floor': True, 'on_ladder': False, 'x': 72.0, 'y': 115.999130249023, 'zone': 'court_mid'} floor1={'alive': True, 'allow_lose': False, 'climbing': False, 'hanging': False, 'lose_visible': False, 'on_floor': True, 'on_ladder': False, 'x': 475.611602783203, 'y': 179.985626220703, 'zone': 'west_hall'} floor2={'alive': True, 'allow_lose': False, 'climbing': False, 'hanging': False, 'lose_visible': False, 'on_floor': True, 'on_ladder': False, 'x': 491.612396240234, 'y': 99.9934997558594, 'zone': 'west_loft'} floor3={'alive': True, 'allow_lose': False, 'climbing': False, 'hanging': False, 'lose_visible': False, 'on_floor': True, 'on_ladder': False, 'x': 837.702270507813, 'y': 19.813138961792, 'zone': 'east_top'} machine_still={'alive': True, 'allow_lose': False, 'climbing': False, 'hanging': False, 'lose_visible': False, 'on_floor': True, 'on_ladder': False, 'x': 152.666610717773, 'y': 179.985626220703, 'zone': 'court_ground'}
- MACHINE jammed=True jams=1 real=True
- FLOOR interior=True floors={'east_top': True, 'west_hall': True, 'west_loft': True}
- events kinds include name/zone/p1/machine/floor=True kinds=['stat_bot', 'stat_camera', 'stat_cover', 'stat_door', 'stat_floor', 'stat_graph', 'stat_live', 'stat_machine', 'stat_name', 'stat_p1', 'stat_p2', 'stat_replay', 'stat_spawn', 'stat_zone', 'stat_zone_hit']
- window stills pairwise_distinct=True
- still hashes: {'station_setup_1280x720.png': {'sha256': '34e760ab8b4b56426edefa8dca107f969ea34ce3b475f5a6ef0fe9ee616deeb0', 'bytes': 36353}, 'station_title_1280x720.png': {'sha256': '361b52fe32e1f2548b190bef3c13cacda2ac7192c20634dfdb99dbbfccade342', 'bytes': 48164}, 'station_court_1280x720.png': {'sha256': '3dcdb8cec80839a9c04c2ce3fa4050c59b015a20599ddc5cfb5c91f0ddf81bec', 'bytes': 55633}, 'station_floor1_1280x720.png': {'sha256': '3f186ce41f109c495f9cb898c3c5ae67dc8f7323e96012e31eb6838e297177e6', 'bytes': 55787}, 'station_floor2_1280x720.png': {'sha256': '64f22005ee6e6e7916a08cd3b0211a3bbbd6c040d466732eb2d118b192aa9551', 'bytes': 55355}, 'station_floor3_1280x720.png': {'sha256': '33e0980e2e0d2fb61dc3fd5b6bee018b5bc0e4e8ab21a3fb7d21c6164b5bcec7', 'bytes': 55740}, 'station_machine_1280x720.png': {'sha256': '967c51f62e74033519bcc1bdaf13ecd52821f8703980285198a92276c9bc4fd2', 'bytes': 55629}}
- still errors: []
- `USED_APPLY_FRAMES=4205` attempted=4205
- source_tree_sha256 `d6e32228d14d5dcfc1fe95e39ba9c481d640c38290bb4f2287b207db8bb4d6b6`
- base_head `d9a09af`
- Banners copy `StationCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_station.py
python godot/dogfood/superfighters/tests/check_warehouse.py
python godot/dogfood/superfighters/tests/check_rooftop.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_station.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_station.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT 0 / 0 / 0 / 0. leftover Godot on product `--path` = 0.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Signal Court topology stays assumption (`ledger:RL-MAP-SIGNAL`).
- Jump envelope is product tuning (dx=10 / dy=4); live apex is ~3.4 tiles.
- ZONE / P1 / P2 / BOT / SPAWN / FLOOR / MACHINE are live body positions
  during apply_frames. MapGraph is a helper only. Official routes hold
  `up` on ladder cells. Machine shots use `give_weapon` only as inventory
  setup; the fire is `apply_frames`.
- `ledger:RL-NADE-PROP` stays `deferred`.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption, not observed.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Live `c`/`b` still paint as tiles. This WP placed original breakable
  panes, a door, a lift, and a shootable rotor on Signal Court only.
- Water / toxic stay fixture-only. Hazardous remains
  `ledger:RL-DELTA-MAP-NAMES` debt. Skyline Relay and Pallet Annex
  are unchanged. Pallet Annex unused `annex_lift` and P2/bot 2/7
  are not reminted.
- No new in-game Y8 play this WP. Not a copied billboard or Y8 collision map.
- Not Y8 parity. Not V0. No legal self-conclusion that the layout is
  close enough to Y8 to ship.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

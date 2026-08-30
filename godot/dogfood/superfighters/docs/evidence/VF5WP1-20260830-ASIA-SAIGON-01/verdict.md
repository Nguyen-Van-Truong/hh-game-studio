# VF5-WP1 verdict

PASS layered map schema, topology validator, and semantic authoring (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF5-WP1)

Verify: serialize/deserialize hash; graph reaches every required platform;
validator bắt map hỏng; editor agent tạo map bằng semantic commands.

DoD: map không còn phụ thuộc chuỗi ký tự khó mở rộng.

## Run

- `run_id`: `VF5WP1-20260830-ASIA-SAIGON-01`
- `command_id`: `cmd.vf5-wp1.map-schema.1`
- seed `11`, mode `vs2`, map `rooftops` display **Rooftops**
- authored map `fx_map_author` display **Draft Yard**
- SCHEMA=pass ROUNDTRIP=pass GRAPH=pass REJECT=pass AUTHOR=pass WIDTH=pass SPAWN=pass PIT=pass CAMERA=pass OVERLAP=pass LIVE=pass REPLAY=match
- LIVE on_floor=True moved=True author_on_floor=True real=True
- AUTHOR hash=695e5643484a442eedd3630d1122e8bdd9a06b91b15a8e5d99f3f52f665cfe92 shipped=695e5643484a442eedd3630d1122e8bdd9a06b91b15a8e5d99f3f52f665cfe92 real=True
- events kinds include schema/graph/reject/author=True kinds=['map_author', 'map_graph', 'map_live', 'map_reject', 'map_replay', 'map_roundtrip', 'map_schema']
- window stills pairwise_distinct=True
- still hashes: {'map_setup_1280x720.png': {'sha256': '88a34a04b0f313353b3031f37cb6285bf66683353be296e8533f5442efe167db', 'bytes': 35393}, 'map_rooftops_1280x720.png': {'sha256': '43574a1e8554aadeb16e5fefbeba406ed09955270f09ac6879d8d3962046e4e4', 'bytes': 35410}, 'map_storage_1280x720.png': {'sha256': '0b51a21c17b52dec425c1f5b4ba36ab82580f395b926e01508f0a38aa789a76a', 'bytes': 35000}, 'map_police_1280x720.png': {'sha256': 'c9c6851a4f70a5759e67294469ec8b8281991609a6e23370ea9d86455955ef68', 'bytes': 35646}, 'map_hazardous_1280x720.png': {'sha256': '8d0e12d6a716288b83673220006a6dbfd409309d4a0e2a7f9247d7abd8500962', 'bytes': 33427}, 'map_author_1280x720.png': {'sha256': '52f7d8995a10b7010b7270eff7b3fefc3107b77da35f0750cd873bea719414f5', 'bytes': 33846}}
- still errors: []
- `USED_APPLY_FRAMES=36` attempted=36
- source_tree_sha256 `609204e3afb1a6ddf69f833af19d2a803cfbbe4e1b3e185c415774ab7239a793`
- base_head `c6c85650bd250e34065af4c21c39acee3f5dd36a`
- Banners copy `MapCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_map.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_map.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_map.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT 0 / 0 / 0 / 0. leftover Godot on product `--path` = 0.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Layer / graph / validator / author stay assumption
  (`ledger:RL-MAP-LAYERS`, `ledger:RL-MAP-GRAPH`,
  `ledger:RL-MAP-VALID`, `ledger:RL-MAP-AUTHOR`).
- Jump envelope is product tuning (dx=10 / dy=4), not observed Y8 reach.
- `ledger:RL-NADE-PROP` stays `deferred`.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption, not observed.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Live `c`/`b` now live on prop/hazard layers but still paint as tiles.
- Combat/env fixture ASCII rows stay import-only; not a VF5-WP2..6 layout pass.
- Display names Rooftops/Storage/Police Station/Hazardous stay known debt
  (`ledger:RL-DELTA-MAP-NAMES`) until VF5-WP2+.
- Draft Yard is an original authoring demo, not a Y8 map name.
- Geometry of the four live maps is unchanged this WP (no new layout).
- No new in-game Y8 play this WP.
- Not Y8 parity. Not V0.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

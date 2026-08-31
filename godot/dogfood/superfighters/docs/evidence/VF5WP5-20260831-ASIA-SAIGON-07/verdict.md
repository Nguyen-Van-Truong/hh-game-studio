# VF5-WP5 verdict

PASS Vitriol Sump sewer arena (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF5-WP5)

Verify: toxic contact/death, dive/roll edge cases, route connectivity,
suspended object collision, camera bounds.

DoD: hazard changes movement and weapon strategy.

## Run

- `run_id`: `VF5WP5-20260831-ASIA-SAIGON-07`
- `command_id`: `cmd.vf5-wp5.vitriol-sump.8`
- seed `15`, mode `vs2`, map `hazardous` display **Vitriol Sump**
- NAME=pass GRAPH=pass TOXIC=pass DIVE=pass ROLL=pass CARGO=pass SPAWN=pass CAMERA=pass TACTIC=pass P1=pass P2=pass BOT=pass ZONE=pass LIVE=pass REPLAY=match VARIANTS=pass
- LIVE hud=Vitriol Sump real=True
- P1 hits={'east_bank': True, 'east_high': True, 'mid_east': True, 'mid_low': True, 'mid_west': True, 'sump_lip': True, 'west_bank': True, 'west_high': True, 'west_mid': True, 'west_span': True} P2 hits={'mid_west': True, 'west_bank': True, 'west_high': True, 'west_mid': True, 'west_span': True} BOT hits={'east_bank': True, 'east_high': True}
- live_reach p1_all=True climb_up_on_ladder=True
- pipes_still={'acid': False, 'alive': True, 'allow_lose': False, 'climbing': False, 'hanging': False, 'lose_visible': False, 'on_floor': True, 'on_ladder': False, 'x': 179.223236083984, 'y': 19.8131732940674, 'zone': 'west_high'} crossing={'acid': False, 'alive': True, 'allow_lose': False, 'climbing': False, 'hanging': False, 'lose_visible': False, 'on_floor': True, 'on_ladder': False, 'x': 471.226837158203, 'y': 67.9994430541992, 'zone': 'mid_east'} cargo_still={'acid': False, 'alive': True, 'allow_lose': False, 'climbing': False, 'hanging': False, 'lose_visible': False, 'on_floor': True, 'on_ladder': False, 'x': 274.813110351563, 'y': 67.8130264282227, 'zone': 'mid_west'} lip={'acid': False, 'alive': True, 'allow_lose': False, 'climbing': False, 'hanging': False, 'lose_visible': False, 'on_floor': True, 'on_ladder': False, 'x': 381.889923095703, 'y': 163.813110351563, 'zone': 'sump_lip'} toxic_still={'acid': True, 'alive': True, 'allow_lose': True, 'climbing': False, 'hanging': False, 'lose_visible': False, 'on_floor': True, 'on_ladder': False, 'x': 381.889923095703, 'y': 179.986938476563, 'zone': 'sump_lip'}
- TOXIC dead=True cause=damage real=True
- DIVE dived=True acid=True acid_at_kill=True cause=damage y=179.999145507813 real=True
- ROLL rolled=True acid=True
- CARGO hung_after=False drops=1 real=True
- TACTIC floor_dead=True pipe_alive=True pickup_id=4 weapon=cinder tick=459 give_weapon=False real=True
- events kinds include name/zone/p1/toxic/tactic=True kinds=['stat_bot', 'stat_camera', 'stat_cargo', 'stat_dive', 'stat_graph', 'stat_live', 'stat_name', 'stat_p1', 'stat_p2', 'stat_replay', 'stat_roll', 'stat_spawn', 'stat_tactic', 'stat_toxic', 'stat_variants', 'stat_zone', 'stat_zone_hit']
- window stills pairwise_distinct=True
- still hashes: {'sewer_setup_1280x720.png': {'sha256': 'b0a5ac220027cbc3f4d418098b282fbcc5cf59e745fd7918fd80e44cf3b4897b', 'bytes': 34969}, 'sewer_title_1280x720.png': {'sha256': 'c4fe8186a39ce856e5d4a81c5d310b475d7f729e493ad5aac88f1a980ac1c262', 'bytes': 47920}, 'sewer_pipes_1280x720.png': {'sha256': '50eec9a143ea76b317c07bd0735cb454ad07c5446fb3c52fa085b142b41f71a5', 'bytes': 53768}, 'sewer_crossing_1280x720.png': {'sha256': '9fe1cd2c3ce1fb2dc5bdffa55106f3453dca596866b67bb58e893b40c3b8fcf1', 'bytes': 53680}, 'sewer_cargo_1280x720.png': {'sha256': 'e5391963fa919c6b32f54bdff968ece4609385d8b6cc3e61d901d1753312cc4d', 'bytes': 53658}, 'sewer_lip_1280x720.png': {'sha256': '2b3baf92833ddd387829b9a45df6ca75676aa657ed814e15da2c23517232fd66', 'bytes': 53656}, 'sewer_toxic_1280x720.png': {'sha256': '7555c503ab8133972f807aba666b881ba42337bfdc43852f51ff5d9f370fe044', 'bytes': 54699}}
- still errors: []
- `USED_APPLY_FRAMES=5523` attempted=5523
- live stdout banners APPLY headless=4255 window=4255 (printed before still staging; packer copies logs verbatim and does not rewrite these lines)
- EVIDENCE_DIR headless=`d:\dataDiskD\intellji\hoanhaosocial\hoanhaonew-20-6-2025\hh-game-studio\godot\dogfood\superfighters\docs\evidence\VF5WP5-20260831-ASIA-SAIGON-07` window=`d:\dataDiskD\intellji\hoanhaosocial\hoanhaonew-20-6-2025\hh-game-studio\godot\dogfood\superfighters\docs\evidence\VF5WP5-20260831-ASIA-SAIGON-07`
- source_tree_sha256 `b04556d6b3980a6411112e7967c7261cf583e1d062565f3df0f9f544acefffee`
- base_head `06197394aa5b22a7385c46c21f73a8e8faad77db`
- Banners copy `SewerCases.outcome_*`. They are not inferred from fail-substrings.
- window.log / headless.log are live process stdout/stderr, not rebuilt from `run_partial`.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_sewer.py
python godot/dogfood/superfighters/tests/check_station.py
python godot/dogfood/superfighters/tests/check_warehouse.py
python godot/dogfood/superfighters/tests/check_rooftop.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_sewer.gd
$godot_console --path godot/dogfood/superfighters --script res://tests/run_sewer.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT 0 / 0 / 0 / 0. leftover Godot on product `--path` = 0.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Vitriol Sump topology stays assumption (`ledger:RL-MAP-SUMP`).
- Jump envelope is product tuning (dx=10 / dy=4); live apex is ~3.4 tiles.
- ZONE / P1 / P2 / BOT / SPAWN / TOXIC / DIVE / ROLL / CARGO / TACTIC
  are live body positions during apply_frames. MapGraph is a helper only.
  Official routes hold `up` on ladder cells. Dive/roll invuln does not
  cancel toxic (`take_env_tick` ignores invuln).
- P2_COVERAGE=smoke and BOT_COVERAGE=smoke: preset ladder / short chase,
  not AI and not Y8 parity. P1 tours every safe combat zone.
- `ledger:RL-NADE-PROP` stays `deferred`.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption, not observed.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Hazardous display is retired to **Vitriol Sump**
  (`ledger:RL-DELTA-MAP-NAMES`). Internal id stays `hazardous`.
- Water stays fixture-only. Signal Court rotor is VF5-WP4 and is not
  reminted. Unused `annex_lift` / `signal_lift` stay honesty nits.
- No new in-game Y8 play this WP. Not a copied billboard or Y8 collision map.
- Not Y8 parity. Not V0. No legal self-conclusion that the layout is
  close enough to Y8 to ship.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

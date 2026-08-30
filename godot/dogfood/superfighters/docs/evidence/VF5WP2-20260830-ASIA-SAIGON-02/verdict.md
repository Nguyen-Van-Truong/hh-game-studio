# VF5-WP2 verdict

PASS Skyline Relay rooftop/bridge arena (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF5-WP2)

Verify: P1/P2/bot reach all combat zones; pit and fallback tests; screenshot
landmarks; no copied billboard/geometry.

DoD: vertical scramble và high-ground tactics hoạt động.

## Run

- `run_id`: `VF5WP2-20260830-ASIA-SAIGON-02`
- `command_id`: `cmd.vf5-wp2.skyline-relay.2`
- seed `12`, mode `vs2`, map `rooftops` display **Skyline Relay**
- NAME=pass ELEV=pass ZONE=pass COVER=pass P1=pass P2=pass BOT=pass PIT=pass FALLBACK=pass LIVE=pass REPLAY=match
- LIVE hud=Skyline Relay real=True
- P1 hits={'east_bridge': True, 'east_deck': True, 'mid_deck': True, 'west_bridge': True, 'west_deck': True, 'west_spire': True} P2 hits={'east_bridge': True, 'mid_deck': True} BOT hits={'east_bridge': True, 'mid_deck': True}
- live_reach p1_all=True climb_up_on_ladder=True west_spire_standing=True east_deck=True
- bridge_still={'alive': True, 'allow_lose': False, 'climbing': False, 'hanging': False, 'lose_visible': False, 'on_floor': True, 'on_ladder': False, 'x': 218.833267211914, 'y': 67.8131866455078, 'zone': 'west_bridge'} cover_still={'alive': True, 'allow_lose': False, 'climbing': False, 'hanging': False, 'lose_visible': False, 'on_floor': True, 'on_ladder': False, 'x': 153.000030517578, 'y': 51.9999389648438, 'zone': 'west_spire'} bridge_ok=True cover_still_ok=True
- COVER blocked_before=True breaks=1 real=True
- events kinds include name/zone/p1/pit=True kinds=['roof_bot', 'roof_cover', 'roof_elev', 'roof_live', 'roof_name', 'roof_p1', 'roof_p2', 'roof_pit', 'roof_replay', 'roof_zone', 'roof_zone_hit']
- window stills pairwise_distinct=True
- still hashes: {'rooftop_setup_1280x720.png': {'sha256': '4277660e61a9b5c8f41597e52a288372d1b9cf73ccacee8a6903b21604f01a0d', 'bytes': 36733}, 'rooftop_title_1280x720.png': {'sha256': '4cfb29a75753609970bf3365bfe06443e4e32a838ff382be4ee99ac7708022f1', 'bytes': 48353}, 'rooftop_bridge_1280x720.png': {'sha256': 'ac50f91a66f78d5a281f4d14014d2a388ce4e0484ce4c3a5d741645e61ba83e5', 'bytes': 56169}, 'rooftop_cover_1280x720.png': {'sha256': 'f8a60cfe949da9aa7fb5f8038d0ed7ab963c13ef121b2ea90eb15ddda35f80aa', 'bytes': 56150}, 'rooftop_pit_1280x720.png': {'sha256': '46523073ae0c6bbbede5998a490368034311b725b28359071b020d3885848cc8', 'bytes': 44486}}
- still errors: []
- `USED_APPLY_FRAMES=1624` attempted=1624
- source_tree_sha256 `d3e9867c85da114bd6fcd2bb7b2cd8707bc8c99d5bf2842b0d600e05c3c71ad3`
- base_head `65399c8f0dce4d51ef28685a1529bdfd9114506b`
- Banners copy `RooftopCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_rooftop.py
python godot/dogfood/superfighters/tests/check_map.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_rooftop.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_rooftop.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT 0 / 0 / 0 / 0. leftover Godot on product `--path` = 0.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Skyline Relay topology stays assumption (`ledger:RL-MAP-SKYLINE`).
- Jump envelope is product tuning (dx=10 / dy=4); live apex is ~3.4 tiles.
  Additive ladders, including a west_spire climb, make high ground reachable
  without rewriting that envelope into observed Y8.
- ZONE / P1 / P2 / BOT are live body positions during apply_frames.
  MapGraph is a helper only. Official routes hold `up` on ladder cells.
- `ledger:RL-NADE-PROP` stays `deferred`.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption, not observed.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Live `c`/`b` still paint as tiles on other maps. This WP placed original
  breakable cover on Skyline Relay only.
- Machines / water / toxic / lifts / doors stay fixture-only. Ladders satisfy
  the ladder/elevator-or-moving-route beat.
- Display names Storage / Police Station / Hazardous stay
  `ledger:RL-DELTA-MAP-NAMES` debt until VF5-WP3+.
- No new in-game Y8 play this WP. Not a copied billboard or Y8 collision map.
- Not Y8 parity. Not V0.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

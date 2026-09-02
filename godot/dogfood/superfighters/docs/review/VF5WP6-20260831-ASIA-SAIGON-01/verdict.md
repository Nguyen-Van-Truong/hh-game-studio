# VF5-WP6 verdict

PASS six-map VS roster (V-A18).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF5-WP6)

Verify: six maps load from clean project; each has >=2 routes, valid spawns,
weapon points, camera fit and one unique interaction; map-cycle wraps safely.

DoD: six-map VS coverage; no hidden map only in code.

## Run

- `run_id`: `VF5WP6-20260831-ASIA-SAIGON-01`
- `command_id`: `cmd.vf5-wp6.vs-roster.1`
- seed `16`, mode `vs2`, setup map `rooftops`
- roster rooftops/Skyline Relay, storage/Pallet Annex, police/Signal Court, hazardous/Vitriol Sump, lantern/Lantern Cut, gauge/Gauge Deck
- Stage stays four. Draft Yard is author-only.
- ROSTER=pass CYCLE=pass LOAD=pass ROUTES=pass COVER=pass CARGO=pass DOOR=pass ROTOR=pass TOXIC=pass WATER=pass LIFT=pass LANTERN=pass GAUGE=pass CAMERA=pass LIVE=pass REPLAY=match
- WATER wet_before=False wet_after=True real=True
- LIFT y0=96.0 y1=40.0 boards=1 real=True
- TOXIC give_weapon=False real=True
- LIVE hud=['Skyline Relay', 'Pallet Annex', 'Signal Court', 'Vitriol Sump', 'Lantern Cut', 'Gauge Deck'] real=True
- window stills pairwise_distinct=True
- still hashes: {'vs_setup_1280x720.png': {'sha256': '4277660e61a9b5c8f41597e52a288372d1b9cf73ccacee8a6903b21604f01a0d', 'bytes': 36733}, 'vs_title_1280x720.png': {'sha256': '4cfb29a75753609970bf3365bfe06443e4e32a838ff382be4ee99ac7708022f1', 'bytes': 48353}, 'vs_rooftops_1280x720.png': {'sha256': '8b13e215a8dfd56b32259d564a51c0f40855522885f1a23869a391e4f0dff999', 'bytes': 36697}, 'vs_storage_1280x720.png': {'sha256': '03c38fd0e9e64438d28f14a4dd814047373ad61b2acba58b3cf47eb6d7be8320', 'bytes': 36785}, 'vs_police_1280x720.png': {'sha256': '3cbdd3c3cbff2081905b931b3342b4370bc3e42cb25ba2ac770e1a4afa880b5e', 'bytes': 36447}, 'vs_hazardous_1280x720.png': {'sha256': '17b9325a475210da2af3803f703f6647fafebf3bcae96750f0c2125e532f35e7', 'bytes': 34982}, 'vs_lantern_1280x720.png': {'sha256': 'f77c101dc1a85f73fffd36c47fddba487540c54f0d8269fabecc07f3795393d4', 'bytes': 36050}, 'vs_gauge_1280x720.png': {'sha256': '686b39e888a63457b691db6afd42ced8a20498596244f70d66ae76246a017af5', 'bytes': 35746}, 'vs_lantern_water_1280x720.png': {'sha256': '0228063f2c32cce384e049419478a063e702eb27758576a5a3b51401d96be528', 'bytes': 36525}, 'vs_gauge_lift_1280x720.png': {'sha256': '58132a9729d9c641f213e42247c367f8a055177f28e05d63dc9ea5e79d3e2da5', 'bytes': 35844}}
- still errors: []
- `USED_APPLY_FRAMES=3543` attempted=3543
- live stdout banners APPLY headless=2600 window=2600 (printed before still staging; packer copies logs verbatim and does not rewrite these lines)
- EVIDENCE_DIR headless=`d:\dataDiskD\intellji\hoanhaosocial\hoanhaonew-20-6-2025\hh-game-studio\godot\dogfood\superfighters\.evidence\VF5WP6-20260831-ASIA-SAIGON-01-H` window=`d:\dataDiskD\intellji\hoanhaosocial\hoanhaonew-20-6-2025\hh-game-studio\godot\dogfood\superfighters\.evidence\VF5WP6-20260831-ASIA-SAIGON-01-W`
- source_tree_sha256 `771fdc8445b5e814c1827a1d938e0202a2d6dad9543219f01038bc244206698a`
- base_head `eb26035c260fb77225325533f819e75ffdda1684`
- window.log / headless.log are live process stdout/stderr, not rebuilt from `run_partial`.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_vs_roster.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_vs_roster.gd
$godot_console --path godot/dogfood/superfighters --script res://tests/run_vs_roster.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT 0 / 0 / 0 / 0. leftover Godot on product `--path` = 0.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Lantern Cut / Gauge Deck / VS roster stay assumption
  (`ledger:RL-MAP-LANTERN`, `ledger:RL-MAP-GAUGE`, `ledger:RL-MAP-VS-ROSTER`).
- Jump envelope is product tuning (dx=10 / dy=4).
- Unique interactions are live `apply_frames` bodies.
- P2_COVERAGE=smoke and BOT_COVERAGE=smoke: not AI and not Y8 parity.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Art still VF7. Overlay Q2 854×480 contact sheet was not a second official size.
- No new in-game Y8 play this WP. Not a copied billboard or Y8 collision map.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

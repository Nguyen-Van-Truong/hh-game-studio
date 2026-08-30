# VF4-WP5 verdict

PASS toxic pits, fall damage, water, and environmental machines (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF4-WP5)

Verify: each hazard has enter/exit/damage/death trace; no spawn soft-lock;
pause and restart clear hazard state; screenshot/evidence per map.

DoD: hazards are readable, deterministic and materially affect match.

## Run

- `run_id`: `VF4WP5-20260830-ASIA-SAIGON-01`
- `command_id`: `cmd.vf4-wp5.env.1`
- seed `7`, mode `vs2`, map `fx_env_yard` display **Hazard Yard**
- DATA=pass INSTANT=pass TOXIC=pass WATER=pass ROTOR=pass FALL=pass SPAWN=pass PAUSE=pass RESET=pass LIVE=pass REPLAY=match
- INSTANT dead=True cause=pit real=True
- TOXIC enter=1 exit=1 damage=2 deaths=1 real=True
- WATER wet=True extinguish=1 real=True
- ROTOR hp=92.0 hits=1 real=True
- FALL on_floor=True hang=False pose=idle immune=True real=True
- SPAWN locked=0 real=True
- events kinds include enter/exit/damage/death=True kinds=['env_damage', 'env_death', 'env_enter', 'env_exit', 'env_spawn', 'fall_damage', 'invuln_end', 'invuln_start', 'lose', 'rotor_hit']
- window stills pairwise_distinct=True map_stills=True
- still hashes: {'env_setup_1280x720.png': {'sha256': '0e9653b3745ef226d30a3f259574749cbd8802887080f776bcbe65868e11e0bc', 'bytes': 32594}, 'env_water_1280x720.png': {'sha256': 'ee0863d9e0a6d4230c4a451d69adcf4c5a6678684aef15002926ded27ebc3092', 'bytes': 33667}, 'env_rotor_1280x720.png': {'sha256': '21a2fdd4189eda180b981251d4c37ed313ce2e9e49b4db0479620f22d90a68c9', 'bytes': 32962}, 'env_toxic_1280x720.png': {'sha256': '74b05d5334c57a6c4dd02da2dc896b92224f29157132d1229e1bde9454abba8e', 'bytes': 33803}, 'env_instant_1280x720.png': {'sha256': '2a6760969675bea91af447202d1fd0dc9593181148e5d971538a85e7e8aa885f', 'bytes': 26041}, 'env_fall_1280x720.png': {'sha256': 'da532098b42b22deaff1e096ff1c7bb1b5cd5373c791192b3167533d72ece508', 'bytes': 33329}}
- still errors: []
- `USED_APPLY_FRAMES=1723` attempted=1724
- source_tree_sha256 `87acc8796e7fbcb30befa753e8c687a1a4ade12ed829520b60f56829cb5d8aa7`
- base_head `ab16c620ba68b2a222ec53691101f7af2ed406c7`
- Banners copy `EnvCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_env.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_env.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_env.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT 0 / 0 / 0 / 0. leftover Godot on product `--path` = 0.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Instant / toxic / water / rotor / spawn stay assumption
  (`ledger:RL-ENV-INSTANT`, `ledger:RL-ENV-DEFER`, `ledger:RL-ENV-WATER`,
  `ledger:RL-ENV-ROTOR`, `ledger:RL-ENV-SPAWN`, `ledger:RL-ENV-ARENA`).
- Fall stays `ledger:RL-MOVE-FALL` assumption.
- `ledger:RL-NADE-PROP` stays `deferred`.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption, not observed.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Live maps still paint `c`/`b` as tiles; this WP does not migrate them.
- Live maps declare pit/fall in ArenaSpec; machines/water/toxic stay on fixtures (VF5).
- Water extinguish is selected in env.json. Roll extinguish stays selected in hazard.json.
- Original acid/water/void/rotor art only. Not a VF7 presentation rewrite. Not a Y8 rip.
- No new in-game Y8 play this WP.
- Not Y8 parity. Not V0.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

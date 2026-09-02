# VF6-WP1 verdict

PASS one canonical match state machine (V-A18).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF6-WP1)

Verify: real input traces for win/loss/tie/quit/restart; no double signal;
snapshot after every transition; pause cannot advance simulation.

DoD: one canonical match state machine used by every mode.

## Run

- `run_id`: `VF6WP1-20260901-ASIA-SAIGON-03`
- `command_id`: `cmd.vf6-wp1.match-machine.3`
- seed `7`, mode `vs2`, setup map `police` / Signal Court
- SCHEMA=pass MACHINE=pass WIN=pass LOSE=pass TIE=pass QUIT=pass RESTART=pass PAUSE=pass SIGNAL=pass SEED=pass FF=pass LIVE=pass REPLAY=match
- `USED_APPLY_FRAMES=642` attempted=644 `USED_FORCE_KILL=0` `USED_STEP_FIXED=0`
- window stills pairwise_distinct=True
- still hashes: {'match_setup_1280x720.png': {'sha256': 'ded9881e3f7b6f2763c7b3978d7294afaf5124f8851684e49a382a90ea9a139a', 'bytes': 36345}, 'match_title_1280x720.png': {'sha256': '361b52fe32e1f2548b190bef3c13cacda2ac7192c20634dfdb99dbbfccade342', 'bytes': 48164}, 'match_win_1280x720.png': {'sha256': '6e94d2bbff421526ea1a720fa34de5ebff86f5a3e394c88319cbf7203af2c7d6', 'bytes': 49992}, 'match_lose_1280x720.png': {'sha256': 'f8a531a05c68b3b0223220df148e208b1de4f74bb5b14cdc8645217d5080d35e', 'bytes': 42870}, 'match_tie_1280x720.png': {'sha256': 'f1e4ac04f07fa2338fd1dab27f08f65f6ac0e1b0a4695b68a91633c77138516d', 'bytes': 55895}, 'match_pause_1280x720.png': {'sha256': 'a695248d2f152a855dbc0704646bb80495a2b59eed9696675ff09f339e45fb5b', 'bytes': 44500}, 'match_quit_1280x720.png': {'sha256': '59d38a09ff6acad7b8f7f412d525a54373640ee9f2c667ef4ddf06fa2ac393eb', 'bytes': 54924}, 'match_restart_1280x720.png': {'sha256': '8edc773e407a5cfd233ed21e8fdaf08b289f6cce11f1be5e924011deb6c9a38d', 'bytes': 36484}}
- still errors: []
- EVIDENCE_DIR headless=`d:\dataDiskD\intellji\hoanhaosocial\hoanhaonew-20-6-2025\hh-game-studio\godot\dogfood\superfighters\.evidence\VF6WP1-20260901-ASIA-SAIGON-03\headless` window=`d:\dataDiskD\intellji\hoanhaosocial\hoanhaonew-20-6-2025\hh-game-studio\godot\dogfood\superfighters\.evidence\VF6WP1-20260901-ASIA-SAIGON-03\window`
- source_tree_sha256 `de9f28b7dcea25fbd3e550cc86f565b153fbf4b38189101ba16698a458895c6c`
- freeze `de9f28b7dcea25fbd3e550cc86f565b153fbf4b38189101ba16698a458895c6c`
- base_head `2b1e0a2e8ff2e7b4b8bfa35080b7f551be091db8`
- window.log / headless.log are live process stdout/stderr, not rebuilt from `run_partial`.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_match.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_match.gd
$godot_console --path godot/dogfood/superfighters --script res://tests/run_match.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT 0 / 0 / 0 / 0. leftover Godot on product `--path` = 0.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption.
- Round timer / countdown stay assumption, not observed. Official tie is a labeled timeout approximation (`round_timer_ticks=36`).
- P2_COVERAGE=smoke and BOT_COVERAGE=smoke until VF6-WP5. Not AI. Not Y8 parity.
- `force_kill` remains fixture-only. Official MATCH traces and `apply_frames` do not call it.
- Art still VF7.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

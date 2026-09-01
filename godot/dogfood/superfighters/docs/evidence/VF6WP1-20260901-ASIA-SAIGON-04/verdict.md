# VF6-WP1 verdict

PASS one canonical match state machine (V-A18).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF6-WP1)

Verify: real typed input traces plus real window/menu/input E2E for
win/loss/tie/quit/restart/pause; no direct apply_eval, private method,
synthetic .pressed.emit() or force_kill may be the sole proof. Pause
must not advance sim. Host captures actual Godot process exits; hung/killed is FAIL.

DoD: one canonical match state machine used by every mode.

## Run

- `run_id`: `VF6WP1-20260901-ASIA-SAIGON-04`
- `command_id`: `cmd.vf6-wp1.match-machine.4`
- seed `7`, mode `vs2`, setup map `police` / Signal Court
- SCHEMA=pass MACHINE=pass WIN=pass LOSE=pass TIE=pass QUIT=pass RESTART=pass PAUSE=pass SIGNAL=pass SEED=pass FF=pass LIVE=pass REPLAY=match
- `USED_APPLY_FRAMES=380` attempted=382 `USED_FORCE_KILL=0` `USED_STEP_FIXED=0`
- window stills pairwise_distinct=True
- still hashes: {'match_setup_1280x720.png': {'sha256': '34e760ab8b4b56426edefa8dca107f969ea34ce3b475f5a6ef0fe9ee616deeb0', 'bytes': 36353}, 'match_title_1280x720.png': {'sha256': '57aed1095b3ce0404b67432adcbae4c3d0e5a277752d116790ee1a866209112f', 'bytes': 64955}, 'match_win_1280x720.png': {'sha256': 'e5d2371880a924756cd39202ae3b66986a11115968b0716d784306f190a20158', 'bytes': 50067}, 'match_lose_1280x720.png': {'sha256': '2d5bf605fba7a82b93024b7b654d271380c3490523d3fd0210cb76044f8f91dc', 'bytes': 42880}, 'match_tie_1280x720.png': {'sha256': '26cf40c5a7419423362a6a3987bc3eb7d15f65d769d395ff1b453b646c4946ea', 'bytes': 55913}, 'match_pause_1280x720.png': {'sha256': 'b091c80c31bf906abef725c151b428520b4faeb00254bd771c96b5880f21c36e', 'bytes': 44498}, 'match_quit_1280x720.png': {'sha256': '59d38a09ff6acad7b8f7f412d525a54373640ee9f2c667ef4ddf06fa2ac393eb', 'bytes': 54924}, 'match_restart_1280x720.png': {'sha256': '111019e7e82706697e01a30e0bf195b25e5cb7cf2b9691dad528930b89ff09b2', 'bytes': 36505}}
- still errors: []
- EVIDENCE_DIR headless=`d:\dataDiskD\intellji\hoanhaosocial\hoanhaonew-20-6-2025\hh-game-studio\godot\dogfood\superfighters\.evidence\VF6WP1-20260901-ASIA-SAIGON-04\headless` window=`d:\dataDiskD\intellji\hoanhaosocial\hoanhaonew-20-6-2025\hh-game-studio\godot\dogfood\superfighters\.evidence\VF6WP1-20260901-ASIA-SAIGON-04\window`
- source_tree_sha256 `2636b77489438a74e570b18cfbd61bce866506096bb8c3b17d686a1c9d00b461`
- freeze `2636b77489438a74e570b18cfbd61bce866506096bb8c3b17d686a1c9d00b461`
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

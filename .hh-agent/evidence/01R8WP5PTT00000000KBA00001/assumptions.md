# Assumptions — R8-WP5 playtest

Run: `01R8WP5PTT00000000KBA00001`

Filled from plan §6.2 (Godot 4.7.1-stable conventions, easiest to test,
fewest dependencies, then player-facing quality). Not E1–E4.

1. Relic-reached stays the only win flag. Seeded runs and the soak
   never assign `relic_reached = true`. Win happens only by walking
   to the relic and interacting after the door is open.
2. "bỏ item" means leave the key (skip pickup), not a new drop
   action. Schema v1 has no drop. Skip-item runs prove the door
   stays closed and the run is still playable.
3. Save schema v1 is unchanged: room id, key, door, relic flags.
   Position is not persisted. Mid-run save/load restores room spawn.
4. Ten minutes continuous play is 600 s wall-clock of the
   production play loop: test_driven=false, Engine.time_scale=1,
   _physics_process running, input via parse_input_event. A
   36000-step_fixed accounting identity is not SOAK. FAST/dev skip
   must not stamp SOAK=proven. That soak is R8-WP5 verify, not G5
   human dogfood. Windowed Viewport.get_image is plan §7.3
   UI-visible capture, not G5.
5. Collision/nav stuck means a true softlock: the player cannot
   move in any cardinal and cannot keep playing. A cardinal-hold
   tile-lip snag that sidesteps or retargets is not a blocker.
   Walking into a wall or a closed door is not a blocker. There is
   no NavigationAgent; the vault is a TileMapLayer corridor.
6. Perf budgets come from PROJECT_BRIEF: first Play load < 3 s,
   60 fps (p95 <= 16.67 ms) is the only proven target. Do not stamp
   PERF=proven against an invented 50 ms floor. Miss 16.67 ms:
   leave PERF=unproven and file P2. Soak memory growth under 256 MiB.
7. Official verify is `python tests/bootstrap/test_kho_bi_an_playtest.py`
   exit 0. Kill leftover Godot on kho-bi-an first. Sequential only.
   Graybox `run_all.gd` stays green. `--provider plan` is unused.
   No API key. G5 stays [ ]. GX stays [ ]. R8-WP6 is not started.
8. P0/P1 found in the bash are fixed in product code. Opening-lip
   snags at divider y=8 were P1: player collider went 12×12 → 10×10
   so the AABB does not sit on the tile edge. Interact VFX is capped
   at 3 live bursts during mash. P2 goes in `backlog.md` with
   evidence.
9. ColorRect Body nodes stay as invisible colliders. Polish art
   wiring is not reopened. No snake demo. No secret material.

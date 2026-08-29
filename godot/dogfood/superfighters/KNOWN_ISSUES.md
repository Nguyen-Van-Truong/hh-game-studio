# KNOWN_ISSUES — Vault Fighters

First playable slice. Not G6. Not 60/60.

- No bullet-time, no destroyable floors, no Box2D gibs
- Ledge grab / ladder snap / one-way drop-through are product-shipped
  as assumption (`ledger:RL-MOVE-LEDGE`, `ledger:RL-MOVE-LADDER`,
  `ledger:RL-MOVE-DROP`). InputFrame action `ledge` stays reserved.
- Dive / jump-kick / fall are product-shipped as assumption
  (`ledger:RL-MOVE-DIVE`, `ledger:RL-MOVE-JUMP-KICK`,
  `ledger:RL-MOVE-FALL`). Y8 observation stays
  `ledger:RL-MOVE-ROLL-DIVE` (`unavailable`). Not observed.
- Bots are greedy (weapon then chase); they can walk into fire
- Stage is one win per map (Bronze-like), not Bronze/Silver/Gold ×4
- Survival mode is out of this slice
- 2P shares one keyboard; no online
- Procedural SFX, not the Y8 soundtrack
- Skins intentionally differ (helmet crew, not ripped Flash sheets)
- Live play now steps through a 60 Hz accumulator (`src/sim/`). That
  clock is a product contract (V-A14, ledger:RL-SIM-FIXED-60
  `assumption`), not an observed Y8 tick rate. Official InputFrame
  traces live under `tests/traces/official/` and replay through
  `apply_frames` (VF1-WP3). Fixture traces may teleport / force_kill;
  official traces must not.
- Official headless tests set `test_driven`, which mutes `SfxBank`: no
  `AudioStreamPlayer` allocation and no stream load/play. Fight logic
  still records `last_id`. This split exists so WASAPI/AudioServer does
  not hold streams at process exit (VF0-WP2). Normal play
  (`test_driven=false`) still starts music and SFX; `shutdown()` stops
  players, clears streams, and restores the Music bus before free.
- Runtime observe/checkpoint (`src/runtime/`, VF1-WP4) is an in-process
  API, not the VF8 editor bridge. Prop event channel is empty because
  this slice has no interactive barrels/glass. 60 Hz remains
  ledger:RL-SIM-FIXED-60 (`assumption`). Hold-to-aim / roll are still
  not observed.
- VF2-WP1 maps real InputEvents for P1/P2/gamepad and an atomic remap
  UI. Official pad proof is a synthetic non-hardware device
  (ledger:RL-CTRL-SYNTH-PAD) unless a pad is plugged in for extra smoke.
  Hold-to-aim stays ledger:RL-CTRL-HOLD-AIM (`assumption`). Roll/dive
  stay ledger:RL-MOVE-ROLL-DIVE (`unavailable`).
- VF2-WP2 ships data-driven walk/jump/crouch/pit/camera
  (`data/sim/locomotion.json`). Official proof is InputFrame
  `apply_frames` plus live InputEvent inject, not teleport-to-pit.
  Jump/crouch stay ledger:RL-MOVE-JUMP-CROUCH (`assumption`). Camera
  stays ledger:RL-CAM-ARENA (`assumption`). 60 Hz stays
  ledger:RL-SIM-FIXED-60 (`assumption`). Hold-to-aim stays
  not observed. Sprint/roll are product-shipped as
  ledger:RL-MOVE-SPRINT / ledger:RL-MOVE-ROLL (`assumption`), not
  observed. Y8 dive/kick observation stays ledger:RL-MOVE-ROLL-DIVE
  (`unavailable`). Product dive/kick/fall are VF2-WP4 assumption rows.
- VF2-WP4 ships dive, jump-kick, and fall-immune landing as
  assumption (`ledger:RL-MOVE-DIVE`, `ledger:RL-MOVE-JUMP-KICK`,
  `ledger:RL-MOVE-FALL`). Official proof is InputFrame
  `apply_frames` plus live InputEvent inject. Pit death still kills.
  Dive invuln is finite. No new Y8 play.
- VF2-WP5 ships ladder attach/snap/climb, ledge grab/recover, and
  one-way drop-through as assumption. Official proof is InputFrame
  `apply_frames` plus live InputEvent inject. `=` one-way tiles live
  on `COL_PLATFORM` so drop actually falls. Ledge recover is a
  velocity step around the lip (`outside_then_board`), not a
  `global_position` teleport, and must finish on the floor.
  Fixtures are
  temporary collision maps, not a VF5 pass (`MAPS=fixtures_only`).
  InputFrame `ledge` stays reserved.

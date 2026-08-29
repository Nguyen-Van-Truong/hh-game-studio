# KNOWN_ISSUES — Vault Fighters

First playable slice. Not G6. Not 60/60.

- No bullet-time, no destroyable floors, no Box2D gibs
- Kick / roll / dive not in this slice
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

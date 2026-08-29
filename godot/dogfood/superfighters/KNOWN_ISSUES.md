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
- VF3-WP1 ships melee startup/active/recovery, AABB hitboxes,
  mode-scoped friendly-fire, and presentation hitstop as assumption
  (`ledger:RL-HIT-PHASES`, `ledger:RL-HIT-BOX`, `ledger:RL-HIT-FF`,
  `ledger:RL-HIT-HITSTOP`). Official proof is InputFrame
  `apply_frames` plus live InputEvent inject. Hitstop does not freeze
  the 60 Hz clock (`ledger:RL-SIM-FIXED-60` assumption). Kick stays
  `ledger:RL-MOVE-JUMP-KICK` assumption. Hold-to-aim stays
  `ledger:RL-CTRL-HOLD-AIM` assumption. Y8 roll/dive observation
  stays `ledger:RL-MOVE-ROLL-DIVE` (`unavailable`). No new Y8 play.
- VF3-WP2 ships knockback, knockdown/get-up, exact-tick invuln,
  and punch disarm as assumption (`ledger:RL-HIT-KNOCK`,
  `ledger:RL-HIT-DOWN`, `ledger:RL-HIT-INVULN`,
  `ledger:RL-HIT-DISARM`). Official proof is InputFrame
  `apply_frames` plus live InputEvent inject. Knockdown pose
  reuses the crouch clip (no new art this WP). Official death
  cause is `damage` or `pit` only. Invuln whiffs do not consume the
  melee window. Crouch-pickup takes the nearest drop. The vs1 LOOP
  smoke in `tests/run_all.gd` pins P1 and the living foe at the
  map spawn (after flushing the prior session TileMap) and uses
  pistol release plus melee so leftover geometry / pit does not
  stall last-standing. No new Y8 play.
- VF3-WP3 ships hold-to-aim, up/down/side aim, release-to-fire
  semi, auto cadence, muzzle, recoil/spread, and swept ballistic
  collision as assumption (`ledger:RL-CTRL-HOLD-AIM`,
  `ledger:RL-AIM-DIRS`, `ledger:RL-FIRE-SEMI`,
  `ledger:RL-FIRE-AUTO`, `ledger:RL-FIRE-AMMO`,
  `ledger:RL-FIRE-MUZZLE`, `ledger:RL-FIRE-RECOIL`,
  `ledger:RL-FIRE-BALLISTIC`, `ledger:RL-FIRE-SWEEP`). Official
  proof is InputFrame `apply_frames` plus live InputEvent inject.
  Guns are ballistic, not hitscan. Sweep uncollides a muzzle that
  clips the stand-on floor tile so live-map shots are not spent at
  t=0; high-speed first entry into cover still blocks. Hold-to-aim
  is **not** promoted
  to `observed`. Y8 roll/dive observation stays
  `ledger:RL-MOVE-ROLL-DIVE` (`unavailable`). No new Y8 play.
- VF3-WP4 ships grenade hold/release throw, gravity arc, bounce,
  fuse, radial falloff, owner skip, one explosion, timeout
  cleanup, and swept nade collision as assumption
  (`ledger:RL-NADE-HOLD`, `ledger:RL-NADE-ARC`,
  `ledger:RL-NADE-BOUNCE`, `ledger:RL-NADE-FUSE`,
  `ledger:RL-NADE-FALLOFF`, `ledger:RL-NADE-OWNER`,
  `ledger:RL-NADE-ONCE`, `ledger:RL-NADE-TIMEOUT`,
  `ledger:RL-NADE-SWEEP`). Prop break is an explosion event
  only (`ledger:RL-NADE-PROP`, `deferred`); VF4 destroys props.
  Official proof is InputFrame `apply_frames` plus live
  InputEvent inject. High-speed no-tunnel proof plants a 4000
  px/s nade at Nade Cover (fixture spawn, same class as VF3-WP3
  bullet sweep). Owner self-damage stays off. Hold-to-aim is
  **not** promoted to `observed`. Y8 roll/dive observation stays
  `ledger:RL-MOVE-ROLL-DIVE` (`unavailable`). No new Y8 play.

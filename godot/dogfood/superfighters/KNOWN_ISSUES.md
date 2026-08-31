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
  API, not the VF8 editor bridge. Observe `props` is the WorldOwner
  snapshot (empty on live maps this WP). Break events stay deferred.
  60 Hz remains ledger:RL-SIM-FIXED-60 (`assumption`). Hold-to-aim /
  roll are still not observed.
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
- VF3-WP6 ships seed-controlled crit / knock jitter / spread
  jitter, hit/tick caps, and a 1000-scenario balance harness as
  assumption (`ledger:RL-MODE-CHAOS`, `ledger:RL-BAL-CRIT`,
  `ledger:RL-BAL-KNOCK-JITTER`, `ledger:RL-BAL-SPREAD-RNG`,
  `ledger:RL-BAL-CAP`, `ledger:RL-BAL-STAMINA`). Live play
  enables chaos; official VF3-WP1..5 traces stay chaos-off.
  The 1000-batch is formula rolls, not 1000 live matches.
  HIGH must land live damage then prove `take_damage(999)`
  clamps to 56. CHAIN must land live blast damage on a fighter
  (owner-skip stays off; once-per-nade). Values are original
  tuning, not a copied stat table. Hold-to-aim is **not**
  promoted to `observed`. Y8 roll/dive observation stays
  `ledger:RL-MOVE-ROLL-DIVE` (`unavailable`). No new Y8 play.
  Residual: nade bounce vs live `=` / `COL_PLATFORM` rooftops is
  unchanged; official CHAIN uses `#` only.
- VF4-WP1 ships a typed PropSpec catalog, named layer/mask
  contract, and WorldOwner spawn/despawn as assumption
  (`ledger:RL-WORLD-SCHEMA`, `ledger:RL-WORLD-LAYERS`,
  `ledger:RL-WORLD-OWN`, `ledger:RL-PROP-*`). Official proof is
  InputFrame `apply_frames` plus live InputEvent inject. Chain
  stays schema only. `ledger:RL-NADE-PROP` stays `deferred`.
  Live maps do not receive world placements; ASCII `c`/`b` stay
  tiles. Hold-to-aim is **not** promoted to `observed`. Y8
  roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE`
  (`unavailable`). No new Y8 play.
- VF4-WP2 ships glass/wood health + resistance, one break event,
  deterministic debris, bullet/melee destroy, cover-until-break,
  melee shove, and crouch-carry / grenade-release throw as
  assumption (`ledger:RL-PROP-BREAK`, `ledger:RL-PROP-DYNAMIC`).
  Official proof is InputFrame `apply_frames` plus live
  InputEvent inject. `ledger:RL-NADE-PROP` stays `deferred`.
  Official throw/shove stays on `#` fixtures; the VF3-WP4 `=`
  bounce residual is unchanged. Live `c`/`b` stay tiles.
  Hold-to-aim is **not** promoted to `observed`. Y8 roll/dive
  observation stays `ledger:RL-MOVE-ROLL-DIVE` (`unavailable`).
  No new Y8 play. Not a VF7 art rewrite.
- VF4-WP3 ships barrel chain (depth cap 2), burn ticks + cleanup,
  roll extinguish, hanging drop impulse, and capped explosion VFX
  as assumption (`ledger:RL-PROP-EXPL`, `ledger:RL-PROP-CHAIN`,
  `ledger:RL-PROP-FIRE`, `ledger:RL-PROP-HANG`,
  `ledger:RL-PROP-EXTINGUISH`). Official proof is InputFrame
  `apply_frames` plus live InputEvent inject. Water extinguish is
  **not** selected in `hazard.json` (`water_selected` stays false).
  VF4-WP5 selects water in `env.json`. `ledger:RL-NADE-PROP` stays
  `deferred` for glass/wood; a nade may start a barrel chain.
  Official maps use `#` floors only; the VF3-WP4 `=` bounce
  residual is unchanged. Live `c`/`b` stay tiles. Hold-to-aim is
  **not** promoted to `observed`. Y8 roll/dive observation stays
  `ledger:RL-MOVE-ROLL-DIVE` (`unavailable`). No new Y8 play.
  Not a VF7 art rewrite.
- VF4-WP4 ships closed-door block, stand-to-open plate, deterministic
  lift path, boarding/unboarding, pause freeze, and restart reset as
  assumption (`ledger:RL-WORLD-DOOR`, `ledger:RL-WORLD-LIFT`,
  `ledger:RL-WORLD-BOARD`, `ledger:RL-WORLD-TRIGGER`). Official
  proof is InputFrame `apply_frames` plus live InputEvent inject.
  Board requires `on_floor`; walk-off must stand on the solid deck
  (hang under the lip is a fail). Foot lock stays `snap_eps=4`;
  Y warp `>=16` is a tunnel. `ledger:RL-NADE-PROP` stays `deferred`.
  Live `c`/`b` stay tiles. Hold-to-aim is **not** promoted to
  `observed`. Y8 roll/dive observation stays
  `ledger:RL-MOVE-ROLL-DIVE` (`unavailable`). Water is not selected
  in `hazard.json`; VF4-WP5 selects it in `env.json`. No new Y8 play.
  Not a VF7 art rewrite.
- VF4-WP5 ships instant death zones, deferred toxic, water
  extinguish, mill/rotor machines, fall policy, and ArenaSpec
  hazard lists as assumption (`ledger:RL-ENV-INSTANT`,
  `ledger:RL-ENV-DEFER`, `ledger:RL-ENV-WATER`,
  `ledger:RL-ENV-ROTOR`, `ledger:RL-ENV-SPAWN`,
  `ledger:RL-ENV-ARENA`, `ledger:RL-MOVE-FALL`). Official proof
  is InputFrame `apply_frames` plus live InputEvent inject.
  Instant death uses cause `pit`. Toxic/rotor death uses `damage`.
  Fall land must stand `on_floor` (hang is a fail). Water
  extinguish is selected in `env.json`; roll extinguish stays
  selected in `hazard.json`. `ledger:RL-NADE-PROP` stays
  `deferred`. Live `c`/`b` stay tiles. Live maps declare pit/fall
  only; machines/water/toxic stay on fixtures (VF5). Hold-to-aim
  is **not** promoted to `observed`. Y8 roll/dive observation
  stays `ledger:RL-MOVE-ROLL-DIVE` (`unavailable`). No new Y8
  play. Not a VF7 art rewrite.
- VF5-WP1 retires ASCII as the live-map source. Layered JSON plus
  `MapValidator` / `MapAuthor` ship as assumption
  (`ledger:RL-MAP-LAYERS`, `ledger:RL-MAP-GRAPH`,
  `ledger:RL-MAP-VALID`, `ledger:RL-MAP-AUTHOR`). Jump envelope
  is product tuning, not observed. Live `c`/`b` still paint as
  tiles. Combat/env fixture ASCII stays import-only. Display
  name Hazardous is now **Vitriol Sump** (VF5-WP5,
  `ledger:RL-DELTA-MAP-NAMES`). Rooftops display is
  **Skyline Relay** (VF5-WP2). Storage display is
  **Pallet Annex** (VF5-WP3). Police display is
  **Signal Court** (VF5-WP4). Draft Yard is an authoring
  demo, not a VS roster map. No new Y8 play.
- VF5-WP2 ships Skyline Relay as assumption
  (`ledger:RL-MAP-SKYLINE`): 3+ elevations, rooftop/bridge
  routes, ladders to the catwalk (west_spire boarded from the
  west climb), a walkable sky catwalk (mid mast opened at
  shoulder height),
  open pits, varied weapon risk, and original breakable cover.
  Official proof is InputFrame `apply_frames` live body
  positions: P1 tours every combat zone, P2/bot leave spawn,
  routes hold `up` on ladder cells, pit, fallback, and cover.
  Jump envelope stays product tuning. Machines/water/toxic
  stay fixture-only. Live `c`/`b` still tiles except this
  arena's cover placements. No new Y8 play. Not a VF7 art
  rewrite.
- VF5-WP3 ships Pallet Annex as assumption
  (`ledger:RL-MAP-PALLET`): enclosed warehouse, crate stacks,
  catwalks, office loft behind a plate door, hanging cargo,
  cargo lift, and original breakable cover. Official proof is
  InputFrame `apply_frames` live body positions. Door/lift are
  placed because this WP asks for them. Hazardous name is now
  **Vitriol Sump** (VF5-WP5). No new Y8 play. Not a VF7 art rewrite.
- VF5-WP4 ships Signal Court as assumption
  (`ledger:RL-MAP-SIGNAL`): three interior floors, open
  courtyard, plate door shortcut, west/east ladders, court
  lift, shootable signal rotor, and breakable window panes.
  Official proof is InputFrame `apply_frames` live body
  positions. Door/lift/rotor are placed because this WP asks
  for them. Water stays fixture-only. Hazardous name is now
  **Vitriol Sump** (VF5-WP5). Unused `signal_lift` is honesty-only
  (same class as unused `annex_lift`). Jump envelope stays product
  tuning. No new Y8 play. Not a VF7 art rewrite.
- VF5-WP5 ships Vitriol Sump as assumption
  (`ledger:RL-MAP-SUMP`): isolated pipes, wide toxic pool,
  west/east ladders, painted telegraph, hanging cargo, and an
  open pit. Official proof is InputFrame `apply_frames` live
  body positions. Toxic is placed because this WP asks for it.
  Dive/roll invuln does not cancel toxic. P2/bot routes are
  **smoke** (preset ladder / short chase), not AI or Y8 parity.
  Water stays fixture-only. Signal Court rotor is not reminted.
  Unused prior lifts stay honesty nits. Jump envelope stays
  product tuning. No new Y8 play. Not a VF7 art rewrite.
  Q0 (31-8): repo-root `tmp_sf*` / `tmp_y8*` / `tmp_shot*` and
  sibling web dumps were hashed without reading and moved out
  of this tree. See `docs/provenance.md`.
- VF3-WP4 ships grenade hold/release throw, gravity arc, bounce,
  fuse, radial falloff, owner skip, one explosion, timeout
  cleanup, and swept nade collision as assumption
  (`ledger:RL-NADE-HOLD`, `ledger:RL-NADE-ARC`,
  `ledger:RL-NADE-BOUNCE`, `ledger:RL-NADE-FUSE`,
  `ledger:RL-NADE-FALLOFF`, `ledger:RL-NADE-OWNER`,
  `ledger:RL-NADE-ONCE`, `ledger:RL-NADE-TIMEOUT`,
  `ledger:RL-NADE-SWEEP`). Prop break is an explosion event
  only (`ledger:RL-NADE-PROP`, `deferred`); VF4-WP2 destroys props.
  Official proof is InputFrame `apply_frames` plus live
  InputEvent inject. High-speed no-tunnel proof plants a 4000
  px/s nade at Nade Cover (fixture spawn, same class as VF3-WP3
  bullet sweep). Owner self-damage stays off. Hold-to-aim is
  **not** promoted to `observed`. Y8 roll/dive observation stays
  `ledger:RL-MOVE-ROLL-DIVE` (`unavailable`). No new Y8 play.
  Residual: nade bounce vs live `=` / `COL_PLATFORM` rooftops can
  fall through ~156px; official BOUNCE/SWEEP used `#` only. VF3-WP5
  official paths stay on `#` fixtures and do not expand that fix.
- VF3-WP5 ships a data-driven roster and four slots as assumption
  (`ledger:RL-ITEM-SLOTS-4`, `ledger:RL-ITEM-ROSTER`,
  `ledger:RL-ITEM-PICK-SLOT`, `ledger:RL-ITEM-KEEP-GUN`,
  `ledger:RL-ITEM-AMMO-RELOAD`). Official proof is InputFrame
  `apply_frames` plus live InputEvent inject. Values are tuning;
  this WP does not claim original exact numbers. Weight is data
  only and does not change VF2 locomotion. Hold-to-aim is **not**
  promoted to `observed`. Y8 roll/dive observation stays
  `ledger:RL-MOVE-ROLL-DIVE` (`unavailable`). No new Y8 play.

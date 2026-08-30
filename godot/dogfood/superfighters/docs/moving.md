# Doors and moving platforms — VF4-WP4

Display title: **Vault Fighters**. This document does **not** claim Y8 parity.

Sidecar evidence: `docs/evidence/VF4WP4-20260830-ASIA-SAIGON-02/`.
That run_id is unique. Do **not** remint it.
`VF4WP4-20260830-ASIA-SAIGON-01` is spent (hang/snap residual). Do **not** remint `-01`.

## Contract

Doors, lifts, and call plates live in `data/world/moving.json`, not as
new catalog `kinds`. That keeps VF4-WP1/2/3 `allowed_kinds` / required
ids unchanged.

`WorldOwner` is the only writer. It spawns `MovingBody` rows, steps
platforms **after** fighters, carries boarded actors by the platform
delta, and arms triggers. `PropView` cannot mutate.

Closed door (`ledger:RL-WORLD-DOOR`) is solid on `world`. Walking across
the 16 px plate does **not** open it. Standing still on the plate for
`arm_ticks=8` opens it: collision off, sprite alpha 0.22.

Lift (`ledger:RL-WORLD-LIFT`) follows a fixed tick path
`(176, 180) → (188, 84)` in 44 ticks, dwells 24, returns 44, then idle.
The dest docks 12 px over the right upper-deck tiles so walk-off is onto
solid, not the shaft lip. `max_step_px=3.0`. Boarding
(`ledger:RL-WORLD-BOARD`) requires `on_floor` (or already riding),
not hanging, and feet within `board_eps` of the plate top. Jump
`vy < -40` unboards. Carry is platform delta plus a foot lock of at most
`snap_eps=4` px. A would-be Y snap `>= warp_px=16`, a snap-reboard of
`>=16` px within 8 ticks, or `Maps.solid_at` at body or feet+10, counts
as a tunnel and is not applied. Riders set `platform_riding` so ledge
grab cannot fire mid-ride (VF2-WP5: board `on_floor`, no ≥16 px warp).

Call plates (`ledger:RL-WORLD-TRIGGER`) are `pickup` Area2D. They fire
once `hold_ticks` reaches `arm_ticks` while the fighter is standing
still on the plate.

Pause: `apply_frames` rejects when `clock.paused`; path frozen. Restart:
`start_fight` rebuilds movers at rest.

Official MATCH uses `GameSession.apply_frames` on typed `InputFrame`s.
Clock is `ledger:RL-SIM-FIXED-60` (`assumption`).
`ledger:RL-NADE-PROP` stays `deferred`.

## Fixtures

- `fx_move_door` display **Gate Hall** — corridor `#.#` gap, door + plate
- `fx_move_lift` display **Lift Shaft** — 12-row unjumpable shaft
- `fx_move_yard` display **Relay Shaft** — door on ground then lift to
  the upper deck (official window map)

Live rooftops/hazardous still paint ASCII `c`/`b` as tiles.
VF5-WP3 places a door and lift on Pallet Annex. VF5-WP4 places a
door and lift on Signal Court.

DoD window stills wait for `frame_post_draw` after the matching
`start_fight` and after the frames that open the gate, raise the lift,
or leave P1 **standing on the upper deck** (`on_floor`, pose not hang).
Setup is Relay Shaft spawn. Door/ride/drop must be pairwise-distinct
bytes, not leftover framebuffer copies. Ride still is on the lift.
Drop still is walk-off onto solid deck, not a hang under the lip.

## Honesty

- Door / lift / board / trigger stay assumption:
  `ledger:RL-WORLD-DOOR`, `ledger:RL-WORLD-LIFT`,
  `ledger:RL-WORLD-BOARD`, `ledger:RL-WORLD-TRIGGER`.
- `ledger:RL-NADE-PROP` stays deferred.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption.
- Y8 roll/dive stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Water is not selected in `hazard.json`. VF4-WP5 selects it in
  `env.json` (`docs/env.md`, `ledger:RL-ENV-WATER`).
- Values are tuning. No copied Y8 table. Not a VF7 art rewrite.
- Original door/lift/trigger art only. No Y8 rip.

# Pallet Annex — VF5-WP3

Display title: **Vault Fighters**. This document does **not** claim Y8 parity.
The Superfighters trademark is not used on the title card or this map name.

Sidecar evidence: `docs/evidence/VF5WP3-20260830-ASIA-SAIGON-01/`.
That `run_id` is unique. Do **not** remint it.

Official MATCH uses `GameSession.apply_frames` on typed `InputFrame`s
for P1 / P2 / bot tours, cover break, hanging cargo drop, office door,
camera fit, and weapon-home safety. Clock is
`ledger:RL-SIM-FIXED-60` (`assumption`).

## Contract

Internal id stays `storage`. Display name is **Pallet Annex**
(`ledger:RL-DELTA-MAP-NAMES` resolved for this arena).

The live grid keeps the VF5-WP1 layered source. This WP adds:

- enclosed warehouse walls, ceiling, and floor (no pit columns)
- crate/barrel stacks as painted `c` tiles plus original breakable cover
- catwalks at three elevations for vertical ambushes
- office loft side route behind a plate door
- hanging cargo that drops on melee
- cargo lift from the east floor to the east landing
- original name/art only

Skyline Relay is unchanged. Police Station / Hazardous display names
remain debt until VF5-WP4+.

## Verify is live locomotion

COVER / CARGO / SPAWN / P1 / P2 / BOT pass from **live body
positions** recorded during `apply_frames`. MapGraph is a helper only.

Official routes hold `up` while overlapping a ladder cell so
`on_ladder` / `climbing` is true for multiple frames. Office entry
stands on the call plate until the door opens, then walks in.

Landmark stills: setup, title, standing catwalk (alive, `on_floor`,
no lose overlay), cover occupancy, cargo route, office loft after the
door. No pit still (this arena has no pit).

## Honesty

- Pallet Annex stays `ledger:RL-MAP-PALLET` (`assumption`).
- Graph stay `ledger:RL-MAP-GRAPH` (`assumption`).
- Door / lift stay `ledger:RL-WORLD-DOOR` / `ledger:RL-WORLD-LIFT`
  (`assumption`). They are placed because this WP asks for them.
- `ledger:RL-NADE-PROP` stays deferred.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption.
- Y8 roll/dive stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Jump envelope dx=10 / dy=4 is product tuning (live apex ~3.4 tiles).
- No copied billboard or collision map. Backdrop is original `bg_city`.
- No new in-game Y8 play. Not a VF7 art look-pass.
- Do not self-conclude the layout is close enough to Y8 to ship.

DoD window stills wait for `frame_post_draw`. Landmarks: setup, title,
catwalk, cover, cargo, office. Bytes must be pairwise-distinct.
Official pack is the windowed leftover-0 run.

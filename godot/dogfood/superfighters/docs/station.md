# Signal Court — VF5-WP4

Display title: **Vault Fighters**. This document does **not** claim Y8 parity.
The Superfighters trademark is not used on the title card or this map name.

Sidecar evidence: `docs/evidence/VF5WP4-20260830-ASIA-SAIGON-01/`.
That `run_id` is unique. Do **not** remint it.

Official MATCH uses `GameSession.apply_frames` on typed `InputFrame`s
for P1 / P2 / bot tours, door shortcut, shootable rotor jam, floor
settles, cover break, camera fit, and no-pit spawn. Clock is
`ledger:RL-SIM-FIXED-60` (`assumption`).

## Contract

Internal id stays `police`. Display name is **Signal Court**
(`ledger:RL-DELTA-MAP-NAMES` resolved for this arena).

The live grid keeps the VF5-WP1 layered source. This WP adds:

- three interior floors plus an open courtyard (not a flat rectangle)
- a plate door shortcut into the west hall
- ladders on both halls and a court lift
- a shootable signal rotor (`signal_rotor`) that jams on bullet hits
- breakable window panes / wood cover
- a left courtyard pit
- original name/art only

Skyline Relay and Pallet Annex are unchanged. Hazardous display is
now **Vitriol Sump** (VF5-WP5, `ledger:RL-DELTA-MAP-NAMES`).

## Verify is live locomotion

GRAPH is a MapGraph helper. MACHINE / FLOOR / SPAWN / P1 / P2 / BOT
pass from **live body positions** recorded during `apply_frames`.
Official routes hold `up` while overlapping a ladder cell so
`on_ladder` / `climbing` is true for multiple frames. Door entry
stands on the call plate until the door opens, then walks in.
Machine fire uses `give_weapon` only as inventory setup.

Landmark stills: setup, title, courtyard, floor1 (west hall),
floor2 (west loft), floor3 (east top), machine approach. Success
stills are alive / standing / no lose overlay.

Each floor also writes a `stat_zone_hit` trace row with `floor`.

## Honesty

- Signal Court stays `ledger:RL-MAP-SIGNAL` (`assumption`).
- Graph stay `ledger:RL-MAP-GRAPH` (`assumption`).
- Door / lift stay `ledger:RL-WORLD-DOOR` / `ledger:RL-WORLD-LIFT`
  (`assumption`). They are placed because this WP asks for them.
- Rotor stay `ledger:RL-ENV-ROTOR` (`assumption`).
- `ledger:RL-NADE-PROP` stays deferred.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption.
- Y8 roll/dive stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Jump envelope dx=10 / dy=4 is product tuning (live apex ~3.4 tiles).
- No copied billboard or collision map. Backdrop is original `bg_city`.
- No new in-game Y8 play. Not a VF7 art look-pass.
- Do not self-conclude the layout is close enough to Y8 to ship.

DoD window stills wait for `frame_post_draw`. Landmarks: setup, title,
court, floor1, floor2, floor3, machine. Bytes must be pairwise-distinct.
Official pack is the windowed leftover-0 run.

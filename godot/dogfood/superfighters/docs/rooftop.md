# Skyline Relay — VF5-WP2

Display title: **Vault Fighters**. This document does **not** claim Y8 parity.
The Superfighters trademark is not used on the title card or this map name.

Sidecar evidence: `docs/evidence/VF5WP2-20260830-ASIA-SAIGON-02/`.
That `run_id` is unique. Do **not** remint it.
`VF5WP2-20260830-ASIA-SAIGON-01` is void (graph-only reach, no live
`up` climb, lose-overlay bridge still).

Official MATCH uses `GameSession.apply_frames` on typed `InputFrame`s
for P1 / P2 / bot tours, cover break, pit, and fallback. Clock is
`ledger:RL-SIM-FIXED-60` (`assumption`).

## Contract

Internal id stays `rooftops`. Display name is **Skyline Relay**
(`ledger:RL-DELTA-MAP-NAMES` resolved for this arena only).

The live grid keeps the VF5-WP1 layered source. This WP adds:

- three combat elevations (deck / bridge / spire)
- rooftop and bridge routes
- ladders from each deck to the catwalk; west_spire is boarded from
  the west ladder climb plus a short walk onto the #### shoulder
  (live jump apex is ~3.4 tiles; the graph envelope dx=10 / dy=4
  stays product tuning, not observed Y8)
- mid-span mast cells on the sky walkway cleared so the catwalk is a
  standing route (original geometry change, not a Y8 copy)
- bottomless gaps
- varied weapon risk (bridge vs gap pickups)
- original breakable cover on the mid deck (`sky_cover_wood`,
  `sky_cover_glass`)

Machines, water, toxic, lifts, and doors stay fixture-only. Ladders
satisfy the ladder / elevator / moving-route beat.

Storage / Police Station / Hazardous display names remain debt until
VF5-WP3+.

## Verify is live locomotion

ZONE / P1 / P2 / BOT pass from **live body positions** recorded
during `apply_frames`. MapGraph is a helper only.

Official routes hold `up` while overlapping a ladder cell so
`on_ladder` / `climbing` is true for multiple frames. High ground
is boarded from that climb plus a documented walk, not a jump box.

Landmark stills: setup, title, standing catwalk/bridge (alive,
`on_floor`, no lose overlay), cover/high-ground occupancy
(`west_spire` standing), pit after a dedicated walk-off (lose UI
allowed only on the pit still).

## Honesty

- Skyline Relay stays `ledger:RL-MAP-SKYLINE` (`assumption`).
- Graph stay `ledger:RL-MAP-GRAPH` (`assumption`).
- `ledger:RL-NADE-PROP` stays deferred.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption.
- Y8 roll/dive stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- No copied billboard or collision map. Backdrop is original `bg_city`.
- No new in-game Y8 play. Not a VF7 art look-pass.

DoD window stills wait for `frame_post_draw`. Landmarks: setup, title,
bridge, cover, pit. Bytes must be pairwise-distinct. Official pack is
the windowed leftover-0 run. Prefer bitwise match of outcomes/events;
stills must be pairwise-distinct and must not use lose-overlay as the
bridge/high-ground landmark.

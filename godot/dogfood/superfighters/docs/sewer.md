# Vitriol Sump — VF5-WP5

Display title: **Vault Fighters**. This document does **not** claim Y8 parity.
The Superfighters trademark is not used on the title card or this map name.
The first-playable display Hazardous is **retired**.

Sidecar evidence: `docs/evidence/VF5WP5-20260831-ASIA-SAIGON-07/`.
That `run_id` is unique. Earlier `…20260831…-01` through `-06`
are superseded (`-05` failed V-A18 provenance; `-06` kept
gameplay and live logs but the packer treated
`used_step_fixed=0` as falsy). Do **not** remint those ids.

Official MATCH uses `GameSession.apply_frames` on typed `InputFrame`s
for P1 / P2 / bot tours, toxic stay-to-death, dive/roll into the pool,
hanging-cargo collision, camera fit, no-pit spawn, and the floor-vs-pipe
tactic. Clock is `ledger:RL-SIM-FIXED-60` (`assumption`).

## Contract

Internal id stays `hazardous`. Display name is **Vitriol Sump**
(`ledger:RL-DELTA-MAP-NAMES` resolved for this arena).

The live grid keeps the VF5-WP1 layered source. This WP adds:

- isolated one-way pipes at four elevations (not a flat rectangle)
- a wide vitriol pool (`acid_trench` placements) in the open pit
- painted `b` telegraph tiles on the pit floor (not a lip wall)
- west/east ladders with lossless `L` cells; west column is left of
  P1 spawn so VF2 DIVE sprint-jump does not attach (`ladder` block)
- y=9 bank/span is a same-height walkway (safe crossing). Isolated
  pipes stay on the mid and high one-ways, not a drop-through shelf
- hanging crate `sump_cargo_hang` on the mid-west pipe
- original name/art only

Skyline Relay, Pallet Annex, and Signal Court are unchanged. Water
stays fixture-only. Signal Court rotor is VF5-WP4 and is not reminted.

## Verify is live locomotion

GRAPH is a MapGraph helper. TOXIC / DIVE / ROLL / CARGO / TACTIC /
SPAWN / P1 / P2 / BOT pass from **live body positions** recorded
during `apply_frames`. Official routes hold `up` while overlapping a
ladder cell so `on_ladder` / `climbing` is true for multiple frames.
Dive/roll invuln does not cancel toxic (`take_env_tick` ignores invuln).

Three morphologies (drop / dive / roll) record trajectory samples and
toxic contact. A recorded InputFrame trace is replayed for a live
state hash. P2/bot each have one live ladder route; that is **smoke**,
not AI or multi-agent parity.

Landmark stills: setup, title, isolated pipes, safe crossing, hanging
cargo, sump lip (alive / standing / no lose overlay), toxic contact
(death allowed).

## Honesty

- Vitriol Sump stays `ledger:RL-MAP-SUMP` (`assumption`).
- Graph stay `ledger:RL-MAP-GRAPH` (`assumption`).
- Toxic stay `ledger:RL-ENV-DEFER` (`assumption`).
- `ledger:RL-NADE-PROP` stays deferred.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption.
- Y8 roll/dive stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Jump envelope dx=10 / dy=4 is product tuning (live apex ~3.4 tiles).
- P2/bot routes are smoke (preset ladder / short chase).
- No copied billboard or collision map. Backdrop is original `bg_city`.
- No new in-game Y8 play. Not a VF7 art look-pass.
- Do not self-conclude the layout is close enough to Y8 to ship.

DoD window stills wait for `frame_post_draw`. Landmarks: setup, title,
pipes, crossing, cargo, lip, toxic. Bytes must be pairwise-distinct.
Official pack is the windowed leftover-0 run.

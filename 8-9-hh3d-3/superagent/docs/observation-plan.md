# Superagent Classic — Y8 observation plan (SA-02)

This plan records what a clean-room observer will measure in the current public
Y8 page. It does not claim that any row is observed. Until a run is captured,
every row in `reference-ledger.tsv` remains `UNVERIFIED` and Classic parity is
blocked.

## Rules and evidence

- Play the public page normally in a browser. Do not download the embed, inspect
  developer tools or network responses, save game packages, or retain screenshots
  or video as product assets. Captures, if needed for measuring, stay under the
  untracked `.local/reference-captures/` directory and are deleted afterward.
- Record `run_id`, UTC/local timestamps, browser viewport, mode/map selection,
  input trace (tick, key, pressed/held/released), sample count, measurement
  method, uncertainty, and a transcript/source reference for each observation.
- Keep source citation in the ledger `source` field and the measured fact in
  `observation`; never turn a plan seed or an assumption into an observation.
- Lengths use character height (`H`); time uses seconds and 60-Hz ticks. Use the
  default tolerances in the plan unless the row records a justified exception.
  Random rates need at least 30 samples before `MATCHED`; fewer samples remain
  uncertain.
- A row may become `OBSERVED` only with a dated observation and evidence source.
  It may become `IMPLEMENTED` only with product code and a test. `MATCHED`
  requires both sides and a measured tolerance. Use `NOT_IN_CURRENT` only when
  the current page was checked and the absence is recorded with evidence.

## Scenarios

| Scenario | Path and inputs | Measure | Ledger rows |
|---|---|---|---|
| S01 controls | Focus game; tap each P1 and P2 binding once, hold, release; repeat on touch viewport | action mapping, simultaneous key behavior, page fullscreen separation | R01-01..R01-11 |
| S02 locomotion | Empty arena; walk, reverse, press each vertical direction, approach ladder/pit/platform; repeat 3+ times | speed/acceleration, jump/crouch/aim, ladder/drop-through/fall/roll/ledge timing | R02-01..R02-06 |
| S03 melee | Two fighters; punch from known spacing; repeat until hit and miss cases | startup/active/recovery, range, damage, knockback, down/get-up, combo/block/kick presence | R03-01..R03-03, R06-01..R06-04 |
| S04 ranged | Pick up each visible gun; tap/hold/release aim and fire at a stationary target | aim directions, fire cadence, projectile/hit model, recoil, ammo/reload, critical outcomes | R04-01..R04-04, R07-01..R07-03 |
| S05 throws | Pick up grenade/object; throw at marked spacing and surfaces; repeat | arc, fuse, bounce, blast radius/timing, weapon throw | R05-01..R05-03 |
| S06 items | Replay same map long enough to see every pickup; log spawn positions and intervals | item/power-up catalog, spawn law, bullet-time scope/duration | R08-01..R08-03 |
| S07 world/map | Visit every offered stage without saving captures; traverse floors, ladders, pits, cover and hazards | map count, mode×map matrix, topology roles, spawn points, object/material/fire/debris behavior | R09-01..R09-03, R10-01..R10-03 |
| S08 bot/modes | Run solo, local 2P, each offered mode and difficulty; complete a short round | bot navigation/attack/avoidance, difficulty, mode rules, win/loss/tie/round timing | R11-01..R11-03, R12-01..R12-05 |
| S09 UI/platform | Open menu, select hero/stage/weapon, pause/settings/fullscreen; resize desktop and emulate touch | menu/HUD state transitions, settings/save, viewport/touch behavior | R13-01..R13-04 |
| S10 camera/feedback | Follow fighters through traversal and a fight; observe pause, hit and any slow-motion event | camera framing/pacing, functional audio/hit-stop/vibration feedback | R14-01..R14-03, R15-01..R15-03 |

For every scenario, note unavailable actions explicitly. An unavailable action
is not evidence of absence until the relevant menu/mode/map has been checked;
record `NOT_IN_CURRENT` only after that check. The coordinator may promote rows
from this plan after reviewing the observation transcript and source hash.

# Reference research review — 4 October 2026

Scope: Superagent Classic. This reviews the owner-supplied research; it is not
an acceptance record. `CURRENT_VALID_WP=SA-02` remains unchanged.

## Sources and confidence

- [Y8 forum, 20 June 2016](https://forum.y8.com/t/superfighters-game/1609)
  hosts a 1400×1300 image and attributes its 18 tips to the developers. The
  forum poster is not established here as a developer.
- [The linked tip sheet](https://forum.y8.com/uploads/default/original/1X/143c5a91f0556fe807acf2eff34fa68fa7a94938.jpg)
  was read directly in the browser. All 18 numbered panels are present. No
  reference image, code, package or asset was saved into this product.
- [Original author comments on Newgrounds](https://www.newgrounds.com/portal/view/575163)
  confirm random player/weapon/object spawns and gun critical hits, Box2D,
  bullet time, 1P/2P, a Stage unlock, and the historical 13-weapon/4-map scope.
  The July 2011 update says Stage advancement requires one win and adds solo
  or co-op Survival. These are historical claims, not current HTML5 measurements.
- Current Y8 UI observations stay in OBS records. The live tips seen for drop,
  team damage and knockdown immunity agree with the sheet, but seeing a tip
  does not prove its runtime implementation or timing.

## Eighteen-tip coverage map

The following is a compact checklist derived from the owner's supplied list
and checked against the image. Every entry is `DOCUMENTED_LEAD`, with current
runtime verification still required. Link to existing broad rows; do not add
trivial rows or increase OBSERVED/MATCHED counts from this checklist.

| Tip | Behavior to test | Ledger | Implement in |
| --- | --- | --- | --- |
| 01 | Double-down platform drop | R02-05 | SA-03 |
| 02 | Melee kicks props / lower opponent | R03-02, R09-03 | SA-04/06 |
| 03 | Three weapon categories; crouch+melee swap | R07-02 | SA-04/05 |
| 04 | Bullet time: 5/10-second labels; toggle cancel | R08-01/03 | SA-05 |
| 05 | Activator and own bullets slowed less | R08-03 | SA-05 |
| 06 | Roll extinguishes burning | R02-06, R09-02 | SA-03/06 |
| 07 | Punch drawn gun: disarm, gun disappears | R03-02, R07-02 | SA-04 |
| 08 | Props and flammables used offensively | R09-01/02/03 | SA-06 |
| 09 | Melee weapons extend reach / damage | R03-01, R07-01 | SA-05 |
| 10 | Powerful shot destroys multiple wooden props | R04-03, R09-01 | SA-05/06 |
| 11 | Rocket victim steers briefly left/right | R02-06, R07-01 | SA-05 |
| 12 | Team melee harmless; bullets hurt | R06-01, R12-01 | SA-04/07 |
| 13 | Airborne melee kick | R03-02 | SA-04 |
| 14 | Faster idle stamina regeneration | R02-01/06 | SA-03 |
| 15 | Random shot knockback / knockdown | R06-02/04 | SA-04/05 |
| 16 | Walkover healing: pills 25%, kit 50% | R06-01, R08-01 | SA-05 |
| 17 | Dive: tackle, evade, fall protection, glass | R02-06, R06-03, R09-03 | SA-03/04/06 |
| 18 | Brief post-knockdown invulnerability | R06-04 | SA-04 |

## Corrections and exclusions from the supplied specification

Tip 7 describes an enemy with the gun already out, not specifically a draw
animation. Its endpoint is disappearance, not a recoverable ground pickup.
Do not implement disarm-as-drop from that mistranslation. Current Y8 still
needs an isolated trial before accepting either behavior.

The tips do not give sprint bindings, stamina capacity/drain, roll count to
extinguish, an exact immunity window, spread distributions, or rocket steering
duration. The document's HP/stamina rates, gravity, speeds, fuse, fall-damage
thresholds, blast formula, hit-stop, time-scales and spawn weights are proposed
engineering values. The 20-second spawn interval and detailed weapon list come
from secondary sources and are not current-runtime measurements. Health
regeneration, grenade cooking/cancel, door behavior and map-specific machinery
also need direct current-version evidence. Do not treat qualitative knockdown
chance as proof of a particular critical-damage multiplier.

Keep Godot 4.7.2 and the existing fixed-step simulation/presentation boundary.
The author's use of Box2D does not require us to switch to Phaser/Planck or
make Godot RigidBody2D a second gameplay authority. Props must produce real
collision/impulse/destruction consequences; cosmetic animation alone is not
physics parity. Architecture and AI pseudocode in the attachment are design
suggestions, not observations of the original implementation.

## Execution decision

This research is sufficient to build and refine a provisional playable core
while targeted SA-02 observation continues. All numerical seeds remain labeled
and data-driven. Prioritize movement/stamina, then close-range combat and its
interruptions, ranged/throw actions, then props/fire interactions through the
same input path. Avoid more menu-entry repetition as a substitute for gameplay.

Ordinary characters share these movement/combat rules. Stamina is a Classic
movement resource, not mana, a passive, or one of the four future hero skills.
Owner keymap stays WASD + J/K/L/; and arrows + Numpad 1/2/3/4. Hero keys remain
inactive. Implementation checkpoints do not waive SA-02, core-signoff, critic,
MATCHED, or final Classic acceptance gates.

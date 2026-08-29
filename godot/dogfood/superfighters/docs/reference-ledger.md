# Vault Fighters — reference ledger

This file is the product provenance and **behavior observation** ledger.
Timezone: **Asia/Saigon**. Display title remains **Vault Fighters**.
This document does **not** claim Y8 parity, V0–V6, R9-WP4, G6, GX, or 60/60.

**Citation rule (DoD VF1-WP1):** every later tuning or “Y8-like” claim
must point at a row ID in this file (`ledger:RL-…`). Rows without
`observed` class are not live play proof (V-A19 / V-A20).

Sidecar for this WP:
`docs/evidence/VF1WP1-20260829-ASIA-SAIGON-01/`

---

## Product identity

| Field | Value |
|---|---|
| Display title (on-screen) | **Vault Fighters** |
| Product folder | `godot/dogfood/superfighters/` |
| Engine pin | Godot **4.7.1-stable** stock (`4.7.1.stable.official.a13da4feb`) |
| Frozen first-playable HEAD | `094822467edfe97d20f99890366a0103dc93b9b1` |
| Ledger WP HEAD (pre-commit) | `5ec84bb59551261fa774c31dabc4db6c0ac44c3e` |
| Product tree at that HEAD | `9b05a2c299e42fd46ea7aecbf211d67aec2e7440` |
| Working title vs trademark | Folder name `superfighters` is historical path only. Title card, fighter names, map display names, and ship metadata must not say Superfighters / Super Fighter. |

Title-card check: `src/ui/title_screen.gd` sets `TitleLabel` to
`Vault Fighters`. Subtitle is `2D arena deathmatch — last standing wins`.

---

## New-folder decision (VF0 seed, unchanged)

| Decision | Status | Meaning for this product |
|---|---|---|
| `GODOT-VF-Y8-2026-08-28` | owner-direction | New folder; Vault Fighters; Y8 Superfighters is the **behavior/topology reference**, not a rip source; parent R9-WP4 / G6 / GX / 60/60 stay frozen. |
| `GODOT-VF-PLAN-2026-08-29` | owner-direction | Product authority is `zdocs/29-8-vault-fighters-y8-parity-plan.txt`. |

Parent platform (do not open or tick from this product):
`CURRENT_VALID_WP=R9-WP4` on the 20-8 plan; 59/60; G6 `[ ]`; GX `[ ]`.

---

## Clean-room status

**Allowed:** observe publicly documented listing/developer/wiki **page
text** to learn mechanics, controls, modes, and functional map beats.

**Forbidden:** download, rip, trace, reverse-engineer, bundle, or ship
Y8 / Newgrounds / MythoLogic / wiki **packages, SWF, Flash, HTML5
builds, sprites, audio, code, screenshots, or trademarked title
cards**. Network is not a runtime dependency.

**This session (VF1-WP1, 2026-08-29):** listing HTML and archive/search
text only. The Y8 page exposes an HTML5 iframe `data-src` on
`html5.gamedistribution.com`. **That embed was not fetched.** No SWF,
no screenshot, no title-card image is stored.

**Clean-room state label:** `in_force`.

---

## VF1-WP1 observation session

| Field | Value |
|---|---|
| `run_id` | `VF1WP1-20260829-ASIA-SAIGON-01` |
| `command_id` | `cmd.vf1-wp1.observe-public-pages.1` |
| Window | 2026-08-29 10:23–10:25 Asia/Saigon |
| In-game play | **no** (would require loading the HTML5/Flash package) |
| Screenshots saved | **no** |
| Godot used | **no** (Verify is URL/date/source/hash, not a play run) |

Class vocabulary:

| Class | Meaning |
|---|---|
| `observed` | Read from a page body this session (live HTML/text). |
| `secondary` | Independent cited write-up or archive/search excerpt. Plan §3.1 `reported`. |
| `assumption` | Needed for later WPs; not fact from this session. |
| `unavailable` | URL opened or attempted; no usable body (403/soft-404/timeout). |

---

## Reference URLs (minimum set, plan §3.2)

| ID | URL | Role | Status this session | Class |
|---|---|---|---|---|
| RL-SRC-Y8-LIVE | https://www.y8.com/games/superfighters | Primary public listing | HTTP 200 at 2026-08-29 10:23:03 +07. Title `Superfighters - Play Now on Y8.com`. Listing HTML 687608 bytes. Embed **not** followed. | `observed` |
| RL-SRC-NG-LIVE | https://www.newgrounds.com/portal/view/575163 | Original release listing | HTTP 403 (urllib 10:23:03) and WebFetch timeout. No full live body. | `unavailable` |
| RL-SRC-ML-LIVE | https://mythologicinteractive.com/Superfighters | Developer controls/loop | HTTP 200, 768-byte SPA shell, visible text `MythoLogic Interactive` only. Same on `www`. Rendered WebFetch: **Page not found**. | `unavailable` |
| RL-SRC-Y8-WAYBACK | https://web.archive.org/web/20110924070405/http://www.y8.com:80/games/Superfighters | Historical same listing | WebFetch 2026-08-29 ~10:24 +07. Flash not downloaded. | `secondary` |
| RL-SRC-NG-INDEX | https://www.newgrounds.com/portal/view/575163 | Search-index excerpt of NG listing | Same hour; not a substitute for a live 200. | `secondary` |
| RL-SRC-WIKI-INDEX | https://mythologicinteractivesuperfighters.fandom.com/wiki/Superfighters | Community map list | Live wiki 403; Wayback 404/timeout. Snippet only. | `secondary` |
| RL-SRC-ML-HOME | https://www.mythologicinteractive.com/ | Developer home | HTTP 200 SPA shell via urllib; WebFetch rendered studio blurb, no original-game control list. | `observed` (home only) |

Transcript hashes (UTF-8) live in
`docs/evidence/VF1WP1-20260829-ASIA-SAIGON-01/hashes.txt`.

---

## Behavior rows

Numbers that are not on a cited page are **tuning targets**, not
invariants. Calibrate later with traces (VF1-WP3+).

### Controls

| ID | Topic | Class | Conf. | Source | When | Behavior to reproduce | Tuning-only | Notes |
|---|---|---|---|---|---|---|---|---|
| RL-CTRL-P1-MOVE | P1 move | `observed` | high | RL-SRC-Y8-LIVE CSS `key-arrows` + action `Move` | 2026-08-29 10:24 +07 | P1 uses arrow keys to move | walk/accel numbers | Listing does not split jump vs crouch vs aim-up/down. |
| RL-CTRL-P1-PUNCH | P1 melee | `observed` | high | live Y8 `key-n` / `Punch` | 2026-08-29 10:24 +07 | P1 N = punch/melee | melee frames | Label on page is Punch, not “kick”. |
| RL-CTRL-P1-SHOOT | P1 shoot | `observed` | high | live Y8 `key-m` / `Shoot` | 2026-08-29 10:24 +07 | P1 M = shoot | fire rate, hold vs tap | **Hold-to-aim is not written on the listing.** |
| RL-CTRL-P1-NADE | P1 grenade | `observed` | high | live Y8 `key-comma` / `Throw Grenade` | 2026-08-29 10:24 +07 | P1 comma = throw grenade | arc, fuse | Hold-to-aim-throw is not written on the listing. |
| RL-CTRL-P2-MOVE | P2 move | `observed` | high | live Y8 `key-wasd` / `Move` | 2026-08-29 10:24 +07 | P2 WASD move on same keyboard | same as P1 | Local 2P tag also on the page. |
| RL-CTRL-P2-ATK | P2 attack trio | `observed` | high | live Y8 `key-1` `key-2` `key-3` / `Punch/Shoot/Throw` | 2026-08-29 10:24 +07 | P2 1/2/3 = punch / shoot / throw | which key is which | Order implied by the label, not proven in play. |
| RL-CTRL-FULLSCREEN | Page fullscreen | `observed` | high | live Y8 `key-f11` | 2026-08-29 10:24 +07 | F11 is **page** fullscreen, not a fighter action | — | Do not bind F11 as a combat input. |
| RL-CTRL-P1-ARCHIVE | 2011 listing keys | `secondary` | med | RL-SRC-Y8-WAYBACK | 2026-08-29 10:24 +07 | P1 arrows + N punch + comma nade; P2 WASD + 1/2/3; period and 4 = power-up | — | 2011 text omits P1 shoot. Cross-check live `key-m`. |
| RL-CTRL-HOLD-AIM | Hold aim, release fire | `assumption` | low | not on live listing; first-playable `PROJECT_BRIEF.md` | 2026-08-29 | Do **not** cite as observed. VF2/VF3 must prove or drop | aim cone, charge | Deferred until a legal play observation or a dated secondary that states hold/release. |
| RL-CTRL-POWERUP | Period / 4 power-up | `secondary` | med | 2011 Y8 archive | 2026-08-29 10:24 +07 | Reference listing had a power-up key | duration | First-playable has **no** power-up. Not a VF1-WP1 ship claim. |

### Camera

| ID | Topic | Class | Conf. | Source | When | Behavior to reproduce | Tuning-only | Notes |
|---|---|---|---|---|---|---|---|---|
| RL-CAM-ARENA | Whole-arena camera | `assumption` | low | plan §1.1 + first-playable brief; **not** on Y8 listing | 2026-08-29 | Side-view arena, not top-down / SF 1v1 | zoom, follow slack | No in-game frame was observed. Do not claim “matches Y8 camera”. |
| RL-CAM-FULLSCREEN | Fullscreen exists | `observed` | high | Y8 page + F11 control | 2026-08-29 10:23 +07 | Site offers fullscreen play | — | Page chrome, not camera math. |

### Modes

| ID | Topic | Class | Conf. | Source | When | Behavior to reproduce | Tuning-only | Notes |
|---|---|---|---|---|---|---|---|---|
| RL-MODE-PVP-PVE | PVP and PVE | `observed` | high | live Y8 description | 2026-08-29 10:23 +07 | Both player-vs-player and vs-AI exist | bot count | Exact mode names not on the live blurb. |
| RL-MODE-1P-2P | Solo and local 2P | `observed` | high | live Y8 text + tags `1 player` `2 player` `Local Multiplayer` | 2026-08-29 10:23 +07 | Solo or one-keyboard two player | — | “with a friend in two player mode”. |
| RL-MODE-HTML5 | HTML5 remaster on Y8 | `observed` | high | live Y8 “Flash … remastered with HTML5” | 2026-08-29 10:23 +07 | Reference **platform** is browser HTML5 now | — | Product ships Godot Windows, not that remaster. |
| RL-MODE-ADDED | Y8 add date | `observed` | high | live Y8 “Added on 23 Jul 2011” | 2026-08-29 10:23 +07 | Provenance only | — | Not a gameplay invariant. |
| RL-MODE-STAGE | Stage, win-once | `secondary` | med | RL-SRC-NG-INDEX 2011-07-23 update | 2026-08-29 | Stage advances after **one** win (best-of-3 removed) | Bronze/Silver/Gold | First-playable Stage is one win/map; Deluxe-style 3-tier is **not** claimed from this excerpt. |
| RL-MODE-SURVIVAL | Survival added 2011-07-28 | `secondary` | med | RL-SRC-NG-INDEX | 2026-08-29 | Endless spawn stand, solo or co-op | spawn rate | First-playable has **no** Survival (`KNOWN_ISSUES.md`). |
| RL-MODE-CHAOS | Random spawns / crits | `secondary` | med | RL-SRC-NG-INDEX developer note | 2026-08-29 | Player/weapon/object spawns and gun crits described as random | tables | “IT AIN'T FAIR” is designer intent, not a RNG spec. |
| RL-MODE-TEAMS-AI | Teams vs AI, 1 life/round | `secondary` | med | 2011 Y8 archive description | 2026-08-29 | Teams of player + computer; 1 life per round | stock lives | Live 2026 blurb does not repeat “1 life per round”. |

### Maps / landmarks

| ID | Topic | Class | Conf. | Source | When | Behavior to reproduce | Tuning-only | Notes |
|---|---|---|---|---|---|---|---|---|
| RL-MAP-CHOOSE | Choose stages | `observed` | med | live Y8 “choose from different heroes, stages, and weapons” | 2026-08-29 10:23 +07 | Multiple stages exist | count | Names not on the live listing. |
| RL-MAP-COUNT-4 | Four maps (2011 NG) | `secondary` | med | RL-SRC-NG-INDEX “13 weapons and 4 maps” | 2026-08-29 | Early public build had 4 maps | — | Conflicts with 6-name wiki list; both are secondary. |
| RL-MAP-COUNT-6 | Six named arenas | `secondary` | med | RL-SRC-WIKI-INDEX | 2026-08-29 | Functional archetypes: Storage, Rooftops, Police Station, Hazardous, Backstreets, Testing Floor | geometry | **Names are reference archetypes only.** VF display names must be original (plan §3.3). |
| RL-MAP-LANDMARKS | Pits, cover, ladders | `assumption` | low | plan §1.1 / first-playable grids; **not** seen in play this WP | 2026-08-29 | Keep functional beats, change size/landmarks/tiles | cell sizes | No wiki landmark page was retrieved. Do not claim observed rooftop/warehouse coordinates. |

### Item / combat loop

| ID | Topic | Class | Conf. | Source | When | Behavior to reproduce | Tuning-only | Notes |
|---|---|---|---|---|---|---|---|---|
| RL-ITEM-GRAB-GUNS | Grab guns, shoot, last standing | `observed` | med | live Y8 “intense shooting” / “survive in the chaotic arenas” plus 2011 “grab guns … blast the AI” | 2026-08-29 | Pickup + shoot + arena survival | — | Win condition “last standing” is first-playable + plan, not a live Y8 sentence. |
| RL-ITEM-13-WEAPONS | 13 weapons (2011) | `secondary` | med | RL-SRC-NG-INDEX | 2026-08-29 | Broad roster, not fists-only | which 13 | VF3-WP5 product roster is 11 original items; not a claim that it matches the 2011 13. |
| RL-ITEM-RANDOM-SPAWN | Random weapon/object spawn | `secondary` | med | RL-SRC-NG-INDEX | 2026-08-29 | Spawns are not a fixed fair draft | period, tables | `maps.gd` `WEAPON_RESPAWN = 20.0` is a **tuning target**, not observed. |
| RL-ITEM-BULLET-TIME | Bullet-time power-up | `secondary` | med | RL-SRC-NG-INDEX + 2011 power-up keys | 2026-08-29 | Reference had a combat speed power-up | duration | First-playable / `KNOWN_ISSUES.md`: not in this slice. |
| RL-ITEM-BOX2D | Box2D spectacle | `secondary` | low | RL-SRC-NG-INDEX | 2026-08-29 | Physics debris/gibs were a reference feature | — | Product uses Godot physics; no Box2D rip. Not a VF1-WP1 ship claim. |

### Special movement

| ID | Topic | Class | Conf. | Source | When | Behavior to reproduce | Tuning-only | Notes |
|---|---|---|---|---|---|---|---|---|
| RL-MOVE-BASIC | Move / punch / shoot / throw | `observed` | high | live Y8 control block | 2026-08-29 10:24 +07 | Those four actions exist for P1 | — | Jump/crouch not named on the live block (arrows only). |
| RL-MOVE-JUMP-CROUCH | Jump / crouch on vertical | `assumption` | low | first-playable + plan VF2; not labeled on live Y8 | 2026-08-29 | Up/down often mean jump/crouch **and** aim | coyote, crouch AABB | Deferred to VF2 with a new dated row after play or a better secondary. |
| RL-MOVE-SPRINT | Double-tap sprint + stamina | `assumption` | none | not on any page body retrieved this session | 2026-08-29 | Do not claim observed | tap window, drain | First-playable implements a sprint; **not** VF1-WP1 observed. |
| RL-MOVE-ROLL-DIVE | Roll / dive / kick / ledge | `unavailable` | none | not on listing/archive/NG excerpt; no play | 2026-08-29 | Plan VF2 still wants them | i-frames | Honest gap. Community clone-site tips were **not** fetched (those hosts embed the game). |

---

## Delta table (legal / original product)

| ID | Keep or change | Item | Product now / later | Legal or product reason |
|---|---|---|---|---|
| RL-DELTA-TITLE | **Change** | Game title | **Vault Fighters** on title card and `project.godot` `config_name` | Do not ship Superfighters / Super Fighter as product name. |
| RL-DELTA-SKINS | **Change** | Fighter look / names | Original helmet-crew skins; no Jeff/Funnyman/etc. | No character or sprite rip. |
| RL-DELTA-AUDIO | **Change** | Music / SFX | Procedural original tones (`NOTICE.md`) | No Y8/Newgrounds audio rip. |
| RL-DELTA-ENGINE | **Change** | Runtime | Godot 4.7.1-stable Windows | Reference is Flash/HTML5 browser; not a dependency. |
| RL-DELTA-MAP-NAMES | **Change** | Display map names | First-playable still echoes Rooftops / Storage / Police Station / Hazardous. **VF5 must replace display names.** | Plan §3.3: names must be original. Echo names are a known honesty debt, not a VF1-WP1 rename. |
| RL-DELTA-MAP-GEO | **Change** | Coordinates, landmarks, tiles | Echo functional beats (pit, ladder, cover, platforms); original tiles and grids | No collision-map rip. If a later pass is too close for commercial release, stop for legal review. Agents must not self-certify fair use. |
| RL-DELTA-LOOP | **Keep** | Side-view chaotic arena; guns + melee + nades; 1P/2P; PVP/PVE | Functional target for VF2–VF6 | Mechanics/genre ideas; not assets. |
| RL-DELTA-CTRL-LAYOUT | **Keep (intent)** | Split keyboard P1 arrows+N/M/, P2 WASD+1/2/3 | Already in `input_actions.gd` | Cite RL-CTRL-* . Hold-to-aim stays assumption (RL-CTRL-HOLD-AIM). |
| RL-DELTA-PHYSICS | **Change** | Box2D gibs / exact Flash sim | Godot 2D physics, original VFX | No engine or binary rip. |
| RL-DELTA-DELUXE | **Out of scope** | Superfighters Deluxe / online | Not this product | Sequel is a different work. |

---

## How later WPs must extend this file

Append dated rows with:

- URL, Asia/Saigon datetime, page/version status
- `observed` / `secondary` (`reported`) / `assumption` / `unavailable`
- behavior to reproduce vs tuning-only numbers
- intentional original deltas
- hash of the related spec/trace — **no reference assets**

If a play observation becomes legal (public page only, no package saved),
add a new `observed` row. Do not back-date this session as play.

Until a row is `observed` or a calibrated trace exists, no agent may
claim Y8 parity for that behavior.

---

## VF0 notes (not Y8 observation)

VF0-WP1 seeded this file and deferred URL observation to VF1-WP1.
VF0-WP2 headless `tests/run_all.gd` uses `App.test_driven` →
`SfxBank.muted` so the official process does not load `AudioStream`
resources. That is hygiene, not parity.

---

## Honesty / gaps (VF1-WP1)

- Live Y8 **keys** are from listing CSS classes, not from playing.
- Newgrounds live page blocked (403). Developer blurb is a search excerpt.
- MythoLogic `/Superfighters` is a live **Page not found** / empty shell.
- Wiki map page blocked (403). Six names are a snippet, not a layout study.
- Special movement (sprint/roll/dive/kick/ledge) **not observed**.
- Camera framing **not observed**.
- Item respawn `20s` is first-playable tuning, not observed.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

---

## VF1-WP2 simulation contract (not a play observation)

Dated 2026-08-29 Asia/Saigon. No in-game Y8 play. No HTML5/Flash
package. `src/sim/` and `data/sim/` are a **product** clock/schema so
later WPs can replay. Sidecar: `docs/sim-contract.md` and
`docs/evidence/VF1WP2-20260829-ASIA-SAIGON-01/`.

| ID | Topic | Class | Conf. | Source | When | Behavior to reproduce | Tuning-only | Notes |
|---|---|---|---|---|---|---|---|---|
| RL-SIM-FIXED-60 | Fixed 60 Hz accumulator | `assumption` | none | product V-A14; **not** on Y8 listing | 2026-08-29 | Gameplay ticks at 1/60; pause/resume must not jump tick | catch-up cap=8 | **Not a Y8 tick-rate claim.** Do not promote to `observed` without a dated play row. |
| RL-SIM-INPUT-FRAME | InputFrame tick/held/pressed/released | `assumption` | none | V-A14 + first-playable `input_actions.gd` | 2026-08-29 | One frame per fighter per tick; malformed rejected | — | Action names map listing keys via RL-CTRL-*. Hold-to-aim stays RL-CTRL-HOLD-AIM. Roll/dive stay RL-MOVE-ROLL-DIVE and are rejected if sent. |

How later WPs must cite: `ledger:RL-SIM-FIXED-60` for the clock,
`ledger:RL-CTRL-*` for keys, never “60 Hz like Y8”.

---

## VF1-WP3 golden traces (not a play observation)

Dated 2026-08-29 Asia/Saigon. No in-game Y8 play. No HTML5/Flash
package. Official traces are product InputFrames so a parity bug can be
recorded and replayed. Sidecar: `docs/trace-harness.md` and
`docs/evidence/VF1WP3-20260829-ASIA-SAIGON-01/`.

| ID | Topic | Class | Conf. | Source | When | Behavior to reproduce | Tuning-only | Notes |
|---|---|---|---|---|---|---|---|---|
| RL-SIM-TRACE-REPLAY | Official InputFrame record/replay | `assumption` | none | V-A14 + VF1-WP2 contract | 2026-08-29 | Same seed+frames → same snapshot/event hashes twice; one key change fails; official forbids teleport/force_kill | snapshot_every=15 | Not Y8 parity. Clock stays RL-SIM-FIXED-60. Hold-to-aim stays RL-CTRL-HOLD-AIM. Roll/dive stay RL-MOVE-ROLL-DIVE. |

---

## VF1-WP4 runtime observe (not a play observation)

Dated 2026-08-29 Asia/Saigon. No in-game Y8 play. No HTML5/Flash
package. `src/runtime/` is a **product** observe/checkpoint API so an
agent can read structured state. Sidecar: `docs/runtime-diagnostics.md`
and `docs/evidence/VF1WP4-20260829-ASIA-SAIGON-01/`.

| ID | Topic | Class | Conf. | Source | When | Behavior to reproduce | Tuning-only | Notes |
|---|---|---|---|---|---|---|---|---|
| RL-RUNTIME-OBSERVE | Structured observe + checkpoint | `assumption` | none | V-A8 / V-A10 / VF1-WP2 snapshot | 2026-08-29 | observe is read-only; pause keeps snapshot hash; restore hash matches capture; unauthorized/malformed do not mutate | — | Not Y8 parity. Clock stays RL-SIM-FIXED-60. Hold-to-aim stays RL-CTRL-HOLD-AIM. Roll/dive stay RL-MOVE-ROLL-DIVE. Prop events empty in this slice. |

---

## VF2-WP1 product input map (not a play observation)

Dated 2026-08-29 Asia/Saigon. No in-game Y8 play. No HTML5/Flash
package. Sidecar: `docs/input-mapping.md` and
`docs/evidence/VF2WP1-20260829-ASIA-SAIGON-01/`.

Listing keys stay `observed` from VF1-WP1 (`ledger:RL-CTRL-P1-*` /
`ledger:RL-CTRL-P2-*`). The rows below are **product** mapping rules
so P1/P2 and gamepad can be tested with real `InputEvent`s.

| ID | Topic | Class | Conf. | Source | When | Behavior to reproduce | Tuning-only | Notes |
|---|---|---|---|---|---|---|---|---|
| RL-CTRL-DEADZONE | Analog dead-zone | `assumption` | none | VF2-WP1 product map; **not** on Y8 listing | 2026-08-29 | Stick values below 0.25 do not become held left/right | 0.25 | Not a Y8 stick claim. Clock stays RL-SIM-FIXED-60. |
| RL-CTRL-DEVICE-SPLIT | P1 pad 0 / P2 pad 1 | `assumption` | none | VF2-WP1; keyboard split is RL-CTRL-P1-MOVE + RL-CTRL-P2-MOVE | 2026-08-29 | Device-0 joy must not fill P2 InputFrame; device-1 must not fill P1 | — | Keyboard still arrows vs WASD. Do not mark observed. |
| RL-CTRL-REMAP | Atomic remap persist | `assumption` | none | V-A13 + title/pause Controls UI | 2026-08-29 | temp+rename; schema hash stored; F11 rejected; same-device payload rejected | — | Not Y8. Hold-to-aim stays RL-CTRL-HOLD-AIM. |
| RL-CTRL-SYNTH-PAD | Synthetic non-hardware pad | `assumption` | none | VF2-WP1 verify when no hardware | 2026-08-29 | Official inject uses InputEventJoypad* marked non-hardware | — | Hardware smoke is extra if a pad is connected; golden trace stays synthetic. |

Hold-to-aim is still `ledger:RL-CTRL-HOLD-AIM` (`assumption`). VF1-WP1
did **not** observe hold-to-aim or roll. Roll/dive stay
`ledger:RL-MOVE-ROLL-DIVE` (`unavailable`). 60 Hz stays
`ledger:RL-SIM-FIXED-60` (`assumption`).

---

## VF2-WP2 locomotion baseline (not a play observation)

Dated 2026-08-29 Asia/Saigon. No in-game Y8 play. No HTML5/Flash
package. Sidecar: `docs/locomotion.md` and
`docs/evidence/VF2WP2-20260829-ASIA-SAIGON-03/`.

Jump / crouch stay `ledger:RL-MOVE-JUMP-CROUCH` (`assumption`) — VF1-WP1
did not observe them; this WP does **not** promote the class. Camera
stays `ledger:RL-CAM-ARENA` (`assumption`). Hold-to-aim stays
`ledger:RL-CTRL-HOLD-AIM` (`assumption`). Roll/dive stay
`ledger:RL-MOVE-ROLL-DIVE` (`unavailable`). 60 Hz stays
`ledger:RL-SIM-FIXED-60` (`assumption`).

| ID | Topic | Class | Conf. | Source | When | Behavior to reproduce | Tuning-only | Notes |
|---|---|---|---|---|---|---|---|---|
| RL-MOVE-LOCO-BASE | Walk / accel / friction / var-jump / coyote / buffer / crouch AABB / pit | `assumption` | none | VF2-WP2 product loco; **not** on Y8 listing or play | 2026-08-29 | Accel ramps; release frictions; tap jump lower than hold; coyote ~5 ticks; buffer on landing; crouch shrinks AABB; walk-off pit kills | gravity 1700, walk 170, accel 2400, friction 2000, coyote 0.09, jump_buf 0.10 | Not Y8 parity. Numbers are first-playable tuning. Sprint leftovers stay in JSON; VF2-WP3 owns sprint/roll. |

---

## VF2-WP3 sprint, stamina, roll (not a play observation)

Dated 2026-08-29 Asia/Saigon. No in-game Y8 play. No HTML5/Flash
package. Sidecar: `docs/sprint-roll.md` and
`docs/evidence/VF2WP3-20260829-ASIA-SAIGON-02/`.

Sprint stays `ledger:RL-MOVE-SPRINT` (`assumption`). Roll stays
`ledger:RL-MOVE-ROLL` (`assumption`). Neither row is promoted to
`observed`. Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM`
(`assumption`). Dive / kick stay `ledger:RL-MOVE-ROLL-DIVE`
(`unavailable`). 60 Hz stays `ledger:RL-SIM-FIXED-60` (`assumption`).

Product contract: double-tap same direction inside `tap_window`
starts sprint and drains stamina; crouch-while-sprint or InputFrame
`roll` starts a grounded roll with a distinct AABB, invuln window,
animation / SFX / HUD / VFX, and an `extinguish_fire` hook. Dead,
paused, airborne, aiming, ladder, already-rolling, and low-stamina
inputs do not start a roll. A second roll press during the same seq
does not emit another `roll_start`.

| ID | Topic | Class | Conf. | Source | When | Behavior to reproduce | Tuning-only | Notes |
|---|---|---|---|---|---|---|---|---|
| RL-MOVE-ROLL | Grounded roll + i-frame window + extinguish hook | `assumption` | none | VF2-WP3 product contract; **not** observed on Y8 this session | 2026-08-29 | Crouch-while-sprint or InputFrame `roll` starts a committed roll; AABB shrinks; invuln ticks; unique `roll_start` | tap_window 0.22, roll 0.28s, invuln 0.20s, cost 22 | Not Y8 parity. Do not mark observed. Y8 dive/kick observation stays RL-MOVE-ROLL-DIVE. |

---

## VF2-WP4 dive, jump-kick, fall (not a play observation)

Dated 2026-08-29 Asia/Saigon. No in-game Y8 play. No HTML5/Flash
package. Sidecar: `docs/dive-kick.md` and
`docs/evidence/VF2WP4-20260829-ASIA-SAIGON-01/`.

Dive stays `ledger:RL-MOVE-DIVE` (`assumption`). Jump-kick stays
`ledger:RL-MOVE-JUMP-KICK` (`assumption`). Fall stays
`ledger:RL-MOVE-FALL` (`assumption`). None of these rows is promoted
to `observed`. Sprint / roll stay assumption. Hold-to-aim stays
`ledger:RL-CTRL-HOLD-AIM` (`assumption`). Y8 observation stays
`ledger:RL-MOVE-ROLL-DIVE` (`unavailable`). 60 Hz stays
`ledger:RL-SIM-FIXED-60` (`assumption`). Ledge stays reserved.

Product contract: airborne sprint+crouch or InputFrame `dive` starts
a dive with a distinct AABB, finite invuln, and fall-immune landing.
Aerial melee or InputFrame `kick` applies a downward impulse. Dive
tackle and kick hit apply knockdown. A high drop without dive can
hurt. Pit death still kills. Grounded `kick` is blocked. Grounded
sprint+crouch remains a roll.

| ID | Topic | Class | Conf. | Source | When | Behavior to reproduce | Tuning-only | Notes |
|---|---|---|---|---|---|---|---|---|
| RL-MOVE-DIVE | Airborne dive + finite invuln + fall-immune land | `assumption` | none | VF2-WP4 product contract; **not** observed on Y8 this session | 2026-08-29 | Sprint+crouch in air or InputFrame `dive`; AABB differs from roll; pit still kills | dive 0.36s, invuln 0.16s, cost 18 | Not Y8 parity. Do not mark observed. Y8 row stays RL-MOVE-ROLL-DIVE unavailable. |
| RL-MOVE-JUMP-KICK | Aerial kick impulse | `assumption` | none | VF2-WP4 product contract; **not** observed on Y8 this session | 2026-08-29 | Aerial melee or InputFrame `kick`; grounded kick blocked; pose is kick not melee | impulse 90/220, 0.18s | Not Y8 parity. Do not mark observed. |
| RL-MOVE-FALL | Fall damage vs dive immunity | `assumption` | none | VF2-WP4 product contract; **not** observed on Y8 this session | 2026-08-29 | High drop without dive can damage; dive landing emits fall_immune; spawn land does not | drop_min 28, dmg 16 | Not Y8 parity. Do not mark observed. |

---

## VF2-WP5 ladder, ledge, drop (not a play observation)

Dated 2026-08-29 Asia/Saigon. No in-game Y8 play. No HTML5/Flash
package. Sidecar: `docs/traversal.md` and
`docs/evidence/VF2WP5-20260829-ASIA-SAIGON-03/`.

Ladder stays `ledger:RL-MOVE-LADDER` (`assumption`). Ledge stays
`ledger:RL-MOVE-LEDGE` (`assumption`). Drop stays
`ledger:RL-MOVE-DROP` (`assumption`). None of these rows is promoted
to `observed`. InputFrame action `ledge` stays reserved (no dedicated
remap). Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` (`assumption`).
Y8 observation stays `ledger:RL-MOVE-ROLL-DIVE` (`unavailable`).
60 Hz stays `ledger:RL-SIM-FIXED-60` (`assumption`).

Product contract: overlapping a ladder plus up/down attaches and
snaps X to the column center. Climb is blocked by solid cells.
Crouch/down on a one-way platform drops through. Falling past a
solid/platform lip can grab; jump/up recovers. Official proof uses
`apply_frames` plus live InputEvent inject. Fixtures are temporary
collision maps, not a VF5 pass.

| ID | Topic | Class | Conf. | Source | When | Behavior to reproduce | Tuning-only | Notes |
|---|---|---|---|---|---|---|---|---|
| RL-MOVE-LADDER | Ladder attach / snap / climb / drop | `assumption` | none | VF2-WP5 product contract; **not** observed on Y8 this session | 2026-08-29 | Vertical intent attaches; snap to column; climb blocked by solid | climb 140, snap 1 | Not Y8 parity. Do not mark observed. |
| RL-MOVE-LEDGE | Ledge grab / hang / recover | `assumption` | none | VF2-WP5 product contract; **not** observed on Y8 this session | 2026-08-29 | Fall past a lip grabs; jump/up recovers outside-then-board onto the lip floor; down drops | grab 12/18, recover 0.28s step | InputFrame `ledge` stays reserved. Not observed. Official LEDGE requires on_floor + stand epsilon, not rise-only. |
| RL-MOVE-DROP | One-way drop-through | `assumption` | none | VF2-WP5 product contract; **not** observed on Y8 this session | 2026-08-29 | Hold crouch on `=` past 0.25s clears COL_PLATFORM; Y must increase | hold 0.25s, fall>=8 | Short crouch stays crouched. Not observed. |

---

## VF3-WP1 melee phases and hitboxes (not a play observation)

Dated 2026-08-29 Asia/Saigon. No in-game Y8 play. No HTML5/Flash
package. Sidecar: `docs/combat.md` and
`docs/evidence/VF3WP1-20260829-ASIA-SAIGON-01/`.

Phases stay `ledger:RL-HIT-PHASES` (`assumption`). Boxes stay
`ledger:RL-HIT-BOX` (`assumption`). Friendly-fire stays
`ledger:RL-HIT-FF` (`assumption`). Hitstop stays
`ledger:RL-HIT-HITSTOP` (`assumption`, presentation only). None of
these rows is promoted to `observed`. Kick stays
`ledger:RL-MOVE-JUMP-KICK` (`assumption`). Hold-to-aim stays
`ledger:RL-CTRL-HOLD-AIM` (`assumption`). Y8 observation stays
`ledger:RL-MOVE-ROLL-DIVE` (`unavailable`). 60 Hz stays
`ledger:RL-SIM-FIXED-60` (`assumption`).

Product contract: melee press enters startup, then active, then
recovery. Hits are AABB overlap during active only, one target per
window. vs1 same-team is blocked; vs2 PVP hits. Hitstop freezes the
sprite scale, not `SimClock`. Official proof uses `apply_frames`
plus live InputEvent inject. Fixtures are temporary collision maps,
not a VF5 pass.

| ID | Topic | Class | Conf. | Source | When | Behavior to reproduce | Tuning-only | Notes |
|---|---|---|---|---|---|---|---|---|
| RL-HIT-PHASES | Melee startup / active / recovery | `assumption` | none | VF3-WP1 product contract; **not** observed on Y8 this session | 2026-08-29 | Press is startup with no HP change; active may hit; then recovery | fists 3/3/8 | Not Y8 parity. Do not mark observed. |
| RL-HIT-BOX | AABB hitbox vs hurtbox | `assumption` | none | VF3-WP1 product contract; **not** observed on Y8 this session | 2026-08-29 | Overlap hits; miss classifies behind/above/below/reach | fists 16x12 offset 10,-2 | Not a distance check. Not observed. |
| RL-HIT-FF | Mode-scoped friendly-fire | `assumption` | none | VF3-WP1 product contract; **not** observed on Y8 this session | 2026-08-29 | vs1 same-team HP frozen; vs2 different teams take damage | vs1=false vs2=true stage=false | Not observed. |
| RL-HIT-HITSTOP | Presentation hitstop | `assumption` | none | VF3-WP1 product contract; **not** observed on Y8 this session | 2026-08-29 | Sprite scale 0 for 2 ticks; SimClock still +1 | 2 ticks | Clock stays RL-SIM-FIXED-60. Not observed. |

---

## VF3-WP2 knockback, knockdown, invuln, disarm (not a play observation)

Dated 2026-08-29 Asia/Saigon. No in-game Y8 play. No HTML5/Flash
package. Sidecar: `docs/reaction.md` and
`docs/evidence/VF3WP2-20260829-ASIA-SAIGON-01/`.

Knockback stays `ledger:RL-HIT-KNOCK` (`assumption`). Knockdown /
get-up stay `ledger:RL-HIT-DOWN` (`assumption`). Hit invuln stays
`ledger:RL-HIT-INVULN` (`assumption`). Punch disarm stays
`ledger:RL-HIT-DISARM` (`assumption`). None of these rows is
promoted to `observed`. Hold-to-aim stays
`ledger:RL-CTRL-HOLD-AIM` (`assumption`). Y8 observation stays
`ledger:RL-MOVE-ROLL-DIVE` (`unavailable`). 60 Hz stays
`ledger:RL-SIM-FIXED-60` (`assumption`).

Product contract: a landed punch applies impulse and may launch.
A knockdown style (kick / dive tackle) enters knockdown, then
get-up. Invuln is tick-exact. A second knockdown while down is
blocked. Punch (not kick) disarms a held gun; the drop has a uid
and is not duplicated. Official death cause is `damage` or `pit`.
Official proof uses `apply_frames` plus live InputEvent inject.

| ID | Topic | Class | Conf. | Source | When | Behavior to reproduce | Tuning-only | Notes |
|---|---|---|---|---|---|---|---|---|
| RL-HIT-KNOCK | Hit impulse / airborne | `assumption` | none | VF3-WP2 product contract; **not** observed on Y8 this session | 2026-08-29 | Landed hit adds knock vector; negative Y tags airborne | melee 80/-40 | Not Y8 parity. Do not mark observed. |
| RL-HIT-DOWN | Knockdown then get-up | `assumption` | none | VF3-WP2 product contract; **not** observed on Y8 this session | 2026-08-29 | Kick/dive enter knockdown; then getup; chain-lock blocks refresh | 18 + 10 ticks | Not observed. |
| RL-HIT-INVULN | Exact-tick hit invuln | `assumption` | none | VF3-WP2 product contract; **not** observed on Y8 this session | 2026-08-29 | Punch 5 ticks; knockdown covers down+getup; then damage lands | 5 / 28 ticks | Not infinite. Not observed. |
| RL-HIT-DISARM | Punch disarms a gun | `assumption` | none | VF3-WP2 product contract; **not** observed on Y8 this session | 2026-08-29 | Melee/crouch punch vs gun-holder drops one uid; pickup consumes it | punch only | Kick does not disarm. Not observed. |

---

## VF3-WP3 aim model and fire/release (not a play observation)

Dated 2026-08-29 Asia/Saigon. No in-game Y8 play. No HTML5/Flash
package. Sidecar: `docs/aim.md` and
`docs/evidence/VF3WP3-20260829-ASIA-SAIGON-01/`.

Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` (`assumption`). Aim
dirs stay `ledger:RL-AIM-DIRS` (`assumption`). Semi release stays
`ledger:RL-FIRE-SEMI` (`assumption`). Auto cadence stays
`ledger:RL-FIRE-AUTO` (`assumption`). Empty ammo stays
`ledger:RL-FIRE-AMMO` (`assumption`). Muzzle stays
`ledger:RL-FIRE-MUZZLE` (`assumption`). Recoil/spread stay
`ledger:RL-FIRE-RECOIL` (`assumption`). Ballistic-not-hitscan stays
`ledger:RL-FIRE-BALLISTIC` (`assumption`). Swept collision stays
`ledger:RL-FIRE-SWEEP` (`assumption`). None of these rows is
promoted to `observed`. Y8 observation stays
`ledger:RL-MOVE-ROLL-DIVE` (`unavailable`). 60 Hz stays
`ledger:RL-SIM-FIXED-60` (`assumption`).

Product contract: hold fire aims; pistol/shotgun fire on release;
Uzi fires on cadence while held; 0 ammo does not fire; muzzle and
recoil are data-driven; all three guns are ballistic projectiles
with swept collision. Official proof uses `apply_frames` plus live
InputEvent inject. Fixtures are temporary collision maps, not a VF5
pass.

| ID | Topic | Class | Conf. | Source | When | Behavior to reproduce | Tuning-only | Notes |
|---|---|---|---|---|---|---|---|---|
| RL-AIM-DIRS | Up / down / side aim | `assumption` | none | VF3-WP3 product contract; **not** observed on Y8 this session | 2026-08-29 | Hold fire + jump/crouch/none sets aim_up/aim_down/aim_side | cone | Not Y8 parity. Do not mark observed. |
| RL-FIRE-SEMI | Release-to-fire semi | `assumption` | none | VF3-WP3 product contract; **not** observed on Y8 this session | 2026-08-29 | Hold pistol does not spawn; release spawns one | cadence 23 | Keep last_aim_dir on the release tick. |
| RL-FIRE-AUTO | Hold cadence auto | `assumption` | none | VF3-WP3 product contract; **not** observed on Y8 this session | 2026-08-29 | Held Uzi fires every cadence tick | 5 ticks | Not observed. |
| RL-FIRE-AMMO | 0 ammo no fire | `assumption` | none | VF3-WP3 product contract; **not** observed on Y8 this session | 2026-08-29 | Empty gun hold/release spawns nothing | start 12/24/6 | Not observed. |
| RL-FIRE-MUZZLE | Data muzzle origin | `assumption` | none | VF3-WP3 product contract; **not** observed on Y8 this session | 2026-08-29 | Shot starts at aim * forward + lift | 14/-4 pistol | Per-gun data. Not observed. |
| RL-FIRE-RECOIL | Recoil and spread | `assumption` | none | VF3-WP3 product contract; **not** observed on Y8 this session | 2026-08-29 | Fire kicks opposite aim; shotgun fans pellets | 24 / 10 / 56 | Deterministic fan; no RNG. |
| RL-FIRE-BALLISTIC | Ballistic, not hitscan | `assumption` | none | VF3-WP3 product decision; **not** observed on Y8 this session | 2026-08-29 | Pistol/Uzi/Shotgun spawn traveling bullets | speeds 560/580/500 | Hitscan rejected. Not observed. |
| RL-FIRE-SWEEP | Continuous bullet collision | `assumption` | none | VF3-WP3 product contract; **not** observed on Y8 this session | 2026-08-29 | Segment from last_pos to predicted hits wall first | 4000 px/s proof | No 4px probe. Not observed. |

---

## VF3-WP4 projectile / grenade / explosion (not a play observation)

Dated 2026-08-29 Asia/Saigon. No in-game Y8 play. No HTML5/Flash
package. Sidecar: `docs/explosive.md` and
`docs/evidence/VF3WP4-20260829-ASIA-SAIGON-01/`.

Hold-to-throw stays `ledger:RL-NADE-HOLD` (`assumption`). Arc stays
`ledger:RL-NADE-ARC` (`assumption`). Bounce stays
`ledger:RL-NADE-BOUNCE` (`assumption`). Fuse stays
`ledger:RL-NADE-FUSE` (`assumption`). Falloff stays
`ledger:RL-NADE-FALLOFF` (`assumption`). Owner skip stays
`ledger:RL-NADE-OWNER` (`assumption`). One explosion stays
`ledger:RL-NADE-ONCE` (`assumption`). Timeout cleanup stays
`ledger:RL-NADE-TIMEOUT` (`assumption`). Swept nade collision stays
`ledger:RL-NADE-SWEEP` (`assumption`). Prop break stays
`ledger:RL-NADE-PROP` (`deferred`). None of these rows is promoted
to `observed`. Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM`
(`assumption`). Y8 observation stays `ledger:RL-MOVE-ROLL-DIVE`
(`unavailable`). 60 Hz stays `ledger:RL-SIM-FIXED-60` (`assumption`).

Product contract: hold comma aims a throw; release throws one
ballistic nade; gravity makes an arc; floor/wall bounce; fuse then
exactly one explosion; radial falloff; owner is not self-damaged;
timeout frees leftovers; high-speed sweep does not tunnel. Prop
destroy is deferred to VF4 (event only). Official proof uses
`apply_frames` plus live InputEvent inject. Fixtures are temporary
collision maps, not a VF5 pass.

| ID | Topic | Class | Conf. | Source | When | Behavior to reproduce | Tuning-only | Notes |
|---|---|---|---|---|---|---|---|---|
| RL-NADE-HOLD | Hold-to-aim throw | `assumption` | none | VF3-WP4 product contract; **not** observed on Y8 this session | 2026-08-29 | Hold grenade aims; no spawn until release | throw_cd 48 | Do **not** cite as observed. |
| RL-NADE-ARC | Gravity arc | `assumption` | none | VF3-WP4 product contract; **not** observed on Y8 this session | 2026-08-29 | Thrown nade vy increases under data gravity | 900 | Not observed. |
| RL-NADE-BOUNCE | Floor / wall bounce | `assumption` | none | VF3-WP4 product contract; **not** observed on Y8 this session | 2026-08-29 | Contact flips/damps velocity; rest_vy stops chatter | 0.55 / 0.35 | Not observed. |
| RL-NADE-FUSE | Fuse then blast | `assumption` | none | VF3-WP4 product contract; **not** observed on Y8 this session | 2026-08-29 | fuse_ticks then explosion event | 81 ticks | Not observed. |
| RL-NADE-FALLOFF | Radial damage falloff | `assumption` | none | VF3-WP4 product contract; **not** observed on Y8 this session | 2026-08-29 | Closer fighter takes more damage | 42 / 48 | Not observed. |
| RL-NADE-OWNER | Owner self-damage off | `assumption` | none | VF3-WP4 product contract; **not** observed on Y8 this session | 2026-08-29 | Owner HP unchanged inside radius | owner_self_damage=false | Not observed. |
| RL-NADE-ONCE | One explosion | `assumption` | none | VF3-WP4 product contract; **not** observed on Y8 this session | 2026-08-29 | applied flag; second pulse does not fire | once | Not observed. |
| RL-NADE-TIMEOUT | Timeout cleanup | `assumption` | none | VF3-WP4 product contract; **not** observed on Y8 this session | 2026-08-29 | life_ticks expiry frees the node | 180 | Not observed. |
| RL-NADE-SWEEP | Continuous nade collision | `assumption` | none | VF3-WP4 product contract; **not** observed on Y8 this session | 2026-08-29 | Segment from last_pos to predicted hits wall first | 4000 px/s proof | Not observed. |
| RL-NADE-PROP | Explosion prop event | `deferred` | none | VF3-WP4 event only; destroy waits VF4 | 2026-08-29 | explosion payload prop_break=deferred_vf4 | VF4 | Not a prop destroy. |

---

## VF3-WP5 data-driven roster and inventory slots (not a play observation)

Dated 2026-08-29 Asia/Saigon. No in-game Y8 play. No HTML5/Flash
package. Sidecar: `docs/roster.md` and
`docs/evidence/VF3WP5-20260829-ASIA-SAIGON-02/`.
Prior remint `VF3WP5-20260829-ASIA-SAIGON-01` is not reused.

Four slots stay `ledger:RL-ITEM-SLOTS-4` (`assumption`). Roster stays
`ledger:RL-ITEM-ROSTER` (`assumption`). Pickup slot replace stays
`ledger:RL-ITEM-PICK-SLOT` (`assumption`). Keep-gun stays
`ledger:RL-ITEM-KEEP-GUN` (`assumption`). Ammo/reload stay
`ledger:RL-ITEM-AMMO-RELOAD` (`assumption`). None of these rows is
promoted to `observed`. Hold-to-aim stays
`ledger:RL-CTRL-HOLD-AIM` (`assumption`). Y8 observation stays
`ledger:RL-MOVE-ROLL-DIVE` (`unavailable`). 60 Hz stays
`ledger:RL-SIM-FIXED-60` (`assumption`). Values are tuning; this
WP does **not** claim original exact numbers.

Product contract: melee / firearm / explosive / power slots;
original item names and art; fists + three melee + pistol + Uzi +
shotgun + Longarm + Thumper + grenade + Cinder Flask; pickup
replaces the matching slot and drops the old item; grenade/melee/
power pickups do not strip the gun; empty firearm stays equipped;
rifle can reload from reserve. Official proof uses `apply_frames`
plus live InputEvent inject.

| ID | Topic | Class | Conf. | Source | When | Behavior to reproduce | Tuning-only | Notes |
|---|---|---|---|---|---|---|---|---|
| RL-ITEM-SLOTS-4 | Four inventory slots | `assumption` | none | VF3-WP5 product contract; **not** observed on Y8 this session | 2026-08-29 | melee / firearm / explosive / power | slot names | Do **not** cite as observed. |
| RL-ITEM-ROSTER | Data-driven roster | `assumption` | none | VF3-WP5 product contract; **not** observed on Y8 this session | 2026-08-29 | schema rejects missing fields; 11 original ids | all numbers | Tuning, not Y8 tables. |
| RL-ITEM-PICK-SLOT | Pickup replaces slot | `assumption` | none | VF3-WP5 product contract; **not** observed on Y8 this session | 2026-08-29 | new item occupies its slot; old item drops | same-id stacks | Not observed. |
| RL-ITEM-KEEP-GUN | Nade/melee keep gun | `assumption` | none | VF3-WP5 product contract; **not** observed on Y8 this session | 2026-08-29 | pipe / grenade / cinder pickup leaves pistol | — | Not observed. |
| RL-ITEM-AMMO-RELOAD | Ammo / reload data | `assumption` | none | VF3-WP5 product contract; **not** observed on Y8 this session | 2026-08-29 | 0 ammo no fire; empty gun stays; rifle reloads | reload_ticks | Weight is data only. |

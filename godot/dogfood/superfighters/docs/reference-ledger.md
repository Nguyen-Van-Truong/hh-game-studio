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
| RL-ITEM-13-WEAPONS | 13 weapons (2011) | `secondary` | med | RL-SRC-NG-INDEX | 2026-08-29 | Broad roster, not fists-only | which 13 | First-playable roster is smaller (fists/pistol/uzi/shotgun/pipe/knife/grenade). |
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

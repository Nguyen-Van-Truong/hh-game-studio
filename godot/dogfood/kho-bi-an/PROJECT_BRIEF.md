# PROJECT_BRIEF — Kho Bí Ẩn

Dogfood vertical slice for R8. This file is the locked product brief.
Later WPs implement graybox, art, and polish from these acceptance lines.
Happy path must not say the owner clicks. No secrets belong in this file.

Relic-reached is win. Door-open is not win. Key pickup is not win.
Relic-after-door is the path; the win flag is relic-reached only.
R8-WP2 graybox is required and legal. Color-rect reject applies at
release / G5 only. Room graph, LOS, and 4-dir animation sheets stay
in the art bible as R8-WP3+ / G5 polish, not as a WP1 reject-bar.

---

## genre

- **value:** top-down 2D action-adventure
- **player fantasy:** explore Kho Bí Ẩn, a small sealed vault. Relic-after-door is the path (key pickup, then door-open, then relic-reached). Relic-reached is win. Door-open is not win. Key pickup is not win.
- **out of scope:** multiplayer, crafting, skill trees, open world, 3D, C#, online accounts, extra biomes

## camera

- **mode:** follow
- **zoom / limits:** 2.0, clamp to the vault map, no rotation
- **multi-camera:** no

## resolution

- **base design resolution:** 1280x720
- **stretch mode:** canvas_items
- **aspect:** keep
- **integer scale:** no

## input

- **devices:** keyboard and gamepad
- **actions:** move, interact, pause
- **remap UI:** not in v1
- **keyboard map:** WASD or arrows move 4-dir, E or Enter interact, Escape pause
- **gamepad map:** left stick or d-pad move 4-dir, South/A interact, Start pause
- **mouse:** not required for the critical path

## platform

- **ship target:** Windows desktop
- **also-run:** editor Play and later Windows export smoke
- **store / signing:** never implied

## art

- **style:** readable silhouette sprites, limited palette, nearest-neighbor, no photoreal paint
- **palette / silhouette notes:** R8-WP3+ / G5 polish: midnight indigo, brass gold, parchment cream, rust red, moss teal; dark-on-light actors; door and key read at 32px
- **scale:** 16px tiles, 32px actors, one tile equals 16 world units
- **filter:** nearest, no mipmaps on sprites
- **animation states:** R8-WP3+ / G5 polish: 4-dir idle/walk sheets; not a WP1/WP2 reject-bar
- **font:** Open Sans SemiBold, Godot 4.7.1-stable bundled default project font
- **font license:** SIL Open Font License 1.1 OFL; OFL allowed only for this Godot bundled default font
- **placeholder policy:** assets labeled PLACEHOLDER must not ship in release
- **AI / generated assets:** original procedural first; no CC0 URL pinned yet; R8-WP3 will pin a CC0/MIT URL or reject UNKNOWN; remote imagegen only if already authorized; skip otherwise; every shipped image needs source, tool, prompt if any, license, and hash in the later manifest
- **bible:** vault stone and brass, warm lantern accent, consistent outline weight, no random style mix; room graph and LOS are R8-WP3+ / G5 polish, not a WP1/WP2 reject-bar

## audio

- **music:** later WP, nice if free; not a WP1 slice lock
- **SFX set:** R8-WP3+ / G5 polish: pickup, door open, caught, win, lose, interact
- **bus layout:** Master / Music / SFX
- **license source:** original procedural tones until R8-WP3 pins a CC0 URL or rejects UNKNOWN
- **ducking:** later WP, nice if free

## ui

- **flow:** Title to Play to Pause to Resume; Win and Lose both offer Restart
- **hud:** key icon plus a one-line interact hint; no health bar
- **settings:** later WP, nice if free
- **tutorial:** one-line prompt on first move and first interact; no modal lock
- **focus:** keyboard and gamepad can reach Title, Pause, Win, Lose, Restart; five-screen neighbor focus is later WP
- **readability:** body text contrast against indigo panels at 1280x720; no cutoff at keep-aspect
- **quit:** later WP, nice if free

## save

- **needed:** yes
- **slots / autosave:** 1 slot, autosave on key pickup, door open, and relic reached
- **location:** user data, not the project tree
- **contents:** schema v1 room id, inventory key flag, door open flag, relic reached flag. Relic-reached is win. Door-open is not win. Key pickup is not win.
- **load:** Title Continue restores an unfinished v1 slot; if relic reached, Continue starts a new run; Restart always starts a new run; missing or foreign schema starts new

## content / license

- **original vs third-party:** original procedural first; third-party only if CC0 or MIT and pinned with NOTICE.md
- **allowed licenses for shipped content:** original, CC0, MIT; OFL only for Godot bundled default font
- **forbidden:** unlicensed rips; commercial packs that need spend
- **attribution file:** NOTICE.md in the game project
- **sbom:** later release lists exact pins; this slice names the license set only
- **fallback:** original procedural art and SFX if no CC0 URL yet; R8-WP3 will pin or reject UNKNOWN

## performance

- **target GPU class:** integrated laptop GPU
- **frame budget:** target 60 fps at base resolution
- **entity / draw caps (soft):** 1 player, 1 warden, at most 80 physics bodies, 4 lights, one TileMapLayer plus sprites
- **load budget:** first Play room target under 3 seconds on the same class
- **do not cite unverified numbers as facts:** the numbers above are budgets, not measured claims

## asset budget

- **art count cap:** 16
- **audio count cap:** 8
- **font count cap:** 1
- **font:** Open Sans SemiBold
- **license set:** original procedural, CC0, MIT; OFL only for Godot bundled default font
- **spend:** none
- **art inventory:** tileset_vault, actor_player, actor_warden, item_key, prop_door, item_relic
- **audio inventory:** sfx_pickup, sfx_door, sfx_caught, sfx_win, sfx_lose, sfx_interact
- **rooms cap:** 3
- **actors cap:** 2
- **keys cap:** 1
- **doors cap:** 1
- **feasibility:** original procedural art and SFX if no CC0 URL yet; R8-WP3 will pin or reject UNKNOWN; finishable without remote services; spend none

## forbidden

- **systems:** multiplayer, crafting, skill trees, open world, 3D, C#, extra biomes
- **content:** unlicensed rips, unlabeled generated art, more than one guardian
- **release:** PLACEHOLDER-labeled assets, addon, token, evidence, test-only runtime
- **process:** owner clicks, pixel RPA mutation, Godot C++ fork, giant untyped script
- **scope creep:** second dungeon, crafting loop, dialogue tree, online accounts, locking Settings or Quit as WP1

## quality bar

R8-WP2 graybox (colored rectangles, complete loop) is required and legal.
The color-rect reject applies at release / G5 only. A release or G5 build
that is only colored rectangles fails this brief even if a scripted path
is green. A WP2 graybox of colored rectangles with a complete loop does
not fail this brief.

Release / G5 also reject PLACEHOLDER-labeled assets, missing
win/lose/restart, and a silent key pickup / door open / caught path.
Interact feedback and cohesive art/audio are R8-WP3+ / G5 polish, not a
WP2 reject.

G5 / R8-WP5 soak: 10 minutes continuous play with no blocker. That soak is
not a WP1 script.write proof of content density.

## acceptance

- player can move 4-dir
- player input interact
- key pickup
- door open
- relic-reached is win
- door-open is not win
- key pickup is not win
- warden contact is lose
- Title Restart starts a new run
- keyboard and gamepad bind move, interact, and pause
- save and load restore room, key flag, door open flag, and relic reached flag from user data
- overworld scene contains the vault rooms as a TileMapLayer
- UI Title, Pause, Win, Lose, and Restart are reachable without a mouse
- R8-WP2 graybox of colored rectangles with a complete loop is required and legal; release and G5 reject PLACEHOLDER-labeled assets and solid-color rectangle stand-ins
- tests: GUT unit plus MCP/E2E evidence on 4.7.1-stable with seed and fixed-step input timeline
- export: later Windows smoke only; no addon, token, or evidence in the game

## assumption policy

The agent may fill unspecified details without asking, in this order
(plan §6.2):

1. Godot 4.7.1-stable conventions and pinned templates
2. easiest to test and revert
3. fewest dependencies and public Editor API only
4. better player-facing quality when cost is comparable

Write each assumption to `.hh-agent/evidence/<run>/assumptions.md` and continue.

**STOP and ask the owner only for E1–E4** (plan §0.4 / §6.5):

| Gate | Stop when |
|------|-----------|
| **E1** | secret, account, or API key the machine does not already have |
| **E2** | money, paid quota, or buying assets/licenses |
| **E3** | code signing, store upload, public publish, or sending project data off-machine |
| **E4** | brief contradicts itself, or genre / audience / scope must change |

Pause is always available and takes priority over new mutations (A10, A14).
Destructive slices need a recoverable checkpoint first (A10).
Game code is typed GDScript (A19). C++ stays locked at GX.

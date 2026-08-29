# PROJECT_BRIEF — Vault Fighters

New-folder dogfood after the owner stopped the 20-8 plan at **59/60**
(no G6 tick). This is **not** R9-WP4 and does **not** claim 60/60.

Y8 goal (binding): match **mechanics and maps** of the real Y8 game as
closely as is legal and honest. Character skins may differ a bit.

---

## Y8 game matched (looked up first; not guessed)

- **Title:** Superfighters
- **URL:** https://www.y8.com/games/superfighters
- **Developer:** MythoLogic Interactive (Johan Hjärpe, Alexander Siigur)
- **Added on Y8:** 23 Jul 2011 (Flash; later HTML5 remaster)
- **Genre:** 2D side-view arena deathmatch / action platformer
- **Not this game:** a 1v1 Street Fighter clone, or Superfighters Deluxe
  (Steam sequel). Y8 Superfighters is little fighters on platforms with
  guns, melee, grenades, and last-standing wins.

Official developer page (controls / loop cross-check):
https://mythologicinteractive.com/Superfighters

---

## Loop copied (mechanics / maps)

- Side-view 2D platformer arenas, not top-down and not a fighter plane
- Last fighter standing wins; falling into a pit is death
- P1: arrows move / jump / crouch / aim; N melee; hold M to aim, release
  to fire; hold comma to aim a throw, release to throw
- P2 (same keyboard): WASD + 1 melee / hold 2 fire / hold 3 throw
- Double-tap left/right to sprint (stamina)
- Hold-to-aim, aim with up/down, release to shoot
- Three slots: melee + gun + grenades. Start fists + pistol×12 + 3 nades
- Crouch + melee near a grounded weapon to pick up / swap (standing
  melee does not loot). A grenade pickup does not strip the gun
- Hold comma (P2: 3) to aim a throw, release to throw
- Health + stamina bars; stamina drains on sprint
- Random-ish weapon spawns (~20s respawn): pipe, knife, pistol, shotgun,
  uzi, grenade
- VS 1P (vs bots), local VS 2P, and Stage (Rooftops → Storage →
  Police Station → Hazardous — the Y8 Stage order)
- Camera frames the whole arena
- Title → fight → win/lose → restart; Escape / Start pause

Map layouts **echo** the four Y8 Stage arenas (platforms, pits, crates,
ladders, cover) with original tiles. `=` is a Godot one-way / jump-through
platform. They are not ripped collision maps.

---

## Not copied (legal / honest)

- Product title is **Vault Fighters**, not Superfighters / Super Fighter
- No Y8, Newgrounds, Flash, SWF, PNG, or audio rip
- No MythoLogic character names (Jeff, Funnyman, …) on the title screen
- Skins are original: helmet + visor + harness vault crew, not the
  original Flash bodybuilder sheets
- Music and SFX are original procedural tones
- No Deluxe online multiplayer, no bullet-time powerup, no destroyable
  terrain, no Box2D ragdoll gibs (first slice)

---

## genre

- **value:** 2D arena deathmatch platformer
- **player fantasy:** scramble for guns, stay on the platforms, be last
  standing
- **out of scope:** online, C#, Godot C++ fork, Hoan Hao social, Kho Bí Ẩn
  smash, R9-WP4 clean VM, G6 tick

## camera

- **mode:** arena fit (whole stage). Slight living follow is **not**
  in this WP (`ledger:RL-CAM-ARENA`, `assumption`; no Y8 frame seen)
- **zoom / limits:** fit 1280x720 from `data/sim/locomotion.json`, no rotation
- **multi-camera:** no

## resolution

- **base design resolution:** 1280x720
- **stretch mode:** canvas_items
- **aspect:** keep

## input

- **devices:** keyboard and gamepad
- **P1 keyboard:** arrows, N, M, comma, Escape
- **P2 keyboard:** WASD, 1, 2, 3
- **gamepad P1 (device 0):** stick/dpad move, South jump, East crouch,
  West melee, RT/Y fire, LB grenade, Start pause
- **gamepad P2 (device 1):** same layout; must not share P1's device
- **remap:** title/pause Controls UI; atomic temp+rename save
- **hold-to-aim:** first-playable assumption (`ledger:RL-CTRL-HOLD-AIM`),
  not an observed listing behavior

## platform

- **ship target:** Windows desktop, Godot 4.7.1-stable stock
- **store / signing:** never implied; G6 stays [ ]

## art

- **style:** original 32px crew, nearest-neighbor, limited palette
- **filter:** nearest, no mipmaps
- **placeholder policy:** ColorRect colliders may be invisible; the
  visible look is sprites, not ColorRect-only

## ui

- **flow:** Title to Fight to Pause to Resume; Win and Lose offer Restart
- **hud:** health + stamina per living fighter, weapon name, map name

## forbidden

- Y8/SWF/PNG/audio rips; trademarked Superfighters title card
- Tick R9-WP4 / G6 / GX / 60/60
- Fake clean VM; invented API key; `--provider` other than plan
- Smash `godot/dogfood/kho-bi-an`; Hoan Hao social; Godot C++ fork

## assumption policy

Unspecified details: Godot 4.7.1-stable conventions, easiest to test,
fewest deps. Stop only for E1–E4.

# Superfighters (Y8 HTML5) — technical & scenario handbook

**Scope:** Reference for parity research and art direction. Sources: Y8 live observations
(`superagent/docs/observations/OBS-*`), Y8 forum 18-tip sheet, Superfighters Deluxe Wiki
(Deluxe detail; Y8 may differ). Reference rips allowed in `../reference/` per
owner waiver `zdoc/16-10-owner-reference-asset-waiver.txt` (2026-10-16).

**Confidence key:** `Y8-OBS` = observed on Y8 browser; `WIKI-SFD` = Deluxe wiki text;
`TIP` = 18-panel tip sheet; `LEAD` = documentary, needs Y8 re-measure.

---

## 1. Engine & product context

| Topic | Detail | Source |
|-------|--------|--------|
| Platform Y8 | HTML5 remaster of 2011 Flash; Box2D-style physics cited historically | Newgrounds author comments (LEAD) |
| Tick / sim | Reference not published; Superagent uses fixed 60 Hz clean-room sim | product plan |
| Player height (Deluxe editor) | ~20 WU; grid square = 8 WU | WIKI-SFD Category:Melee |
| Historical Classic scope | ~13 weapons, 4 maps (2011); Y8 may expose broader roster over time | LEAD |

---

## 2. Controls (Y8 default labels)

### 2.1 Simple bindings (observed in Setup)

| Action | P1 | P2 |
|--------|----|----|
| Move | Arrow keys | W A S D |
| Melee (punch) | N | 1 |
| Shoot | M | 2 |
| Grenade | `,` | 3 |
| Power slot | `.` | 4 |

### 2.2 Advanced P2 (labels only)

- W: aim/climb-up **and** jump (same key, context-dependent)
- S: aim/climb-down **and** kneel/roll/dive
- A/D: aim/run
- Sprint toggle: present, **unbound** in observed panel

Superagent product remap (not Y8): see `docs/from-superagent/control-bindings.md`.

**Y8-OBS:** isolated punch/shoot/grenade keys produce animations and ammo counter changes;
hold-to-aim, release-to-fire, cadence, and damage are **UNVERIFIED** (ledger R04).

---

## 3. Character action / animation inventory (reference)

Wiki pages include **infobox sprites** (open URL → save image locally if needed; do not commit ripped art to product).

### 3.1 Locomotion & body states

| Action | Behavior (summary) | Wiki / evidence |
|--------|-------------------|-----------------|
| Walk / run | Acceleration, braking UNVERIFIED on Y8 | R02-01 LEAD |
| Jump | P1 Up → airborne observed | R02-02 Y8-OBS partial |
| Crouch | Down; sustained crouch not fully measured | R02-02 |
| Ladder climb | P2 W on ladder → climbing pose | R02-04 partial |
| Drop-through platform | Double-Down sequence observed qualitatively | R02-05, TIP 01 |
| Sprint | Toggle unbound on observed Y8 setup; sprint+dive on Deluxe wiki | WIKI-SFD Special Movements |
| Roll | Down + direction; dodge bullets (??%); **1–2 rolls extinguish fire** | WIKI-SFD, TIP 06 |
| Dive | Sprint + crouch; dodge; **no fall damage**; ends in roll; grab/tackle; breaks glass | WIKI-SFD, TIP 17 |
| Ledge grab | Hold toward ledge | WIKI-SFD |
| Block | Timed block with melee can absorb/deflect bullets (metal) | WIKI-SFD |
| Grab / tackle follow-up | Punch ~17 HP or throw; pit throw kill | WIKI-SFD |

### 3.2 Melee

| Action | Behavior | Wiki |
|--------|----------|------|
| Punch (fists) | Default melee; ~8.5 HP, 11 WU (Deluxe) | Fists |
| Kick | Default S; 3 HP, 11 WU; stagger/push; usable while holding gun/grenade | Kicks |
| Jump kick | Mid-air; farther knockback; landing kneel ~1s (vulnerable) | Kicks, TIP 13 |
| Combo / knockdown | UNVERIFIED timing on Y8 | R03 LEAD |
| Disarm | Hit opponent **while aiming** → gun knocked away | WIKI-SFD; TIP 7 says gun **disappears** on Y8 tip (not ground pickup) |
| Melee weapon swing | Katana 15 HP / 20 WU; Fire Axe 14 HP / 16 WU; metal reflects bullets | Katana, Fire Axe |
| Throw melee | Drains durability; risk losing weapon | Category:Melee |
| Kick props | Tilt/displace objects (cabinet, cylinder observed qualitatively) | TIP 02, R09 partial |

### 3.3 Ranged

| Action | Behavior | Evidence |
|--------|----------|----------|
| Hip fire / aim | Hold aim + release fire UNVERIFIED on Y8 | R04-01 |
| Pistol | 12 rounds start observed; magazine exhaust then new gun spawn | R04-04 Y8-OBS partial |
| Shotgun / spread | Pellet behavior UNVERIFIED | LEAD |
| Flamethrower | Ignites players; no bullet damage; short range; fire stacks to “blaze” | WIKI-SFD; label seen on Y8 pickup |
| Grenade arc | Throw reduces counter 03→02 observed | R01-04 Y8-OBS |
| Grenade jump | Self-damage boost for height | WIKI-SFD |
| Rocket / bazooka | Victim brief steer after hit (tip 11, not exercised on Y8) | TIP 11 LEAD |
| Bullet time | Clock item “5” / “10”; overlay observed | R01-05, TIP 04–05 |

### 3.4 Fire, hazards, props

| Entity | Behavior | Source |
|--------|----------|--------|
| **Gas Can** | Destroyed → **releases fire**; adjacent players **level 2 fire** | WIKI-SFD Gas Can |
| **Explosive Barrel** | Shot or heavy fall → **explosion + fire spread**; **double explosion** (wreck relaunch) | WIKI-SFD Explosive Barrel |
| Wooden props | Flammable; spread fire; debris | WIKI-SFD Category:Wooden |
| Gas + explosives | Setting mine/C4 next to gas can may snuff fire (Deluxe) | Gas Can wiki |
| Roll while burning | Extinguishes (tip 6) | TIP 06 |
| Glass | Break via dive/kick/bullets; grenade needs height to smash through | WIKI-SFD Glass, TIP 17 |
| Walkover heal | Pills 25%, medkit 50% (tip 16) | TIP 16 LEAD |

### 3.5 Inventory slots (Deluxe model; Y8 UI similar)

1. Melee (fists or weapon)
2. Sidearm / primary gun
3. Thrown (grenades, molotovs, …)
4. Equipment / power
5. Sheath toggle (Deluxe default Q) — Y8 uses crouch+melee swap per tip 3

---

## 4. Y8 vs Deluxe disclaimer

Deluxe wiki numbers (HP, WU, durability 100 on melee) are **engineering leads** until
re-measured on Y8 HTML5. Explosion/fire trials on Y8 were **incomplete** (OBS-2026-10-03-06).

---

## 5. Related files in this folder

| File | Purpose |
|------|---------|
| `catalog/character-actions-manifest.csv` | URLs for every action + weapon + hazard page |
| `catalog/download-manifest.csv` | Items & props |
| `docs/TEST-SCENARIOS.csv` | QA scenario matrix |
| `docs/ANIMATION-POSE-CHECKLIST.md` | Pose list vs Superagent pilot clips |
| `reference/y8-dev-tips-18panels.jpg` | Tip sheet image |
| `docs/from-superagent/*` | Copied project research (no Y8 sprites) |

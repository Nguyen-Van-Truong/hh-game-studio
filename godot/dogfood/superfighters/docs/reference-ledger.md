# Vault Fighters — reference ledger (VF0-WP1 seed)

This file is the product provenance ledger. **VF0-WP1 only seeds
new-folder and clean-room status.** Full Y8/control/map observation
rows belong to **VF1-WP1**. This document does **not** claim Y8
parity, V0–V6 gates, R9-WP4, G6, GX, or 60/60.

Timezone for this freeze: **Asia/Saigon**. Recorded **2026-08-29**.

---

## Product identity

| Field | Value |
|---|---|
| Display title (on-screen) | **Vault Fighters** |
| Product folder | `godot/dogfood/superfighters/` |
| Engine pin | Godot **4.7.1-stable** stock (`4.7.1.stable.official.a13da4feb`) |
| Frozen git HEAD | `094822467edfe97d20f99890366a0103dc93b9b1` |
| Frozen product tree | `aa2e2c998e64f39efa9e10f905d0320f602a760e` (`HEAD:godot/dogfood/superfighters`) |
| Working title vs trademark | Folder name `superfighters` is historical path only. Title card, fighter names, map display names, and ship metadata must not say Superfighters / Super Fighter. |

Title-card check at freeze: `src/ui/title_screen.gd` sets `TitleLabel` to
`Vault Fighters`. Subtitle is `2D arena deathmatch — last standing wins`
(no Superfighters string). Headless test `tests/run_all.gd` asserts the
same.

---

## New-folder decision

Owner opened a **new product folder** after stopping the parent Godot
agent-autopilot plan at **59/60**. This is not a continuation of
R9-WP4 and not a 60/60 claim.

| Decision | Status | Meaning for this product |
|---|---|---|
| `GODOT-VF-Y8-2026-08-28` | owner-direction | New folder `godot/dogfood/superfighters/`; working title Vault Fighters; Y8 Superfighters is the **behavior/topology reference**, not a rip source; Kho Bí Ẩn untouched; parent R9-WP4 / G6 / GX / 60/60 stay open and frozen. |
| `GODOT-VF-PLAN-2026-08-29` | owner-direction | Product WP authority is `zdocs/29-8-vault-fighters-y8-parity-plan.txt` (`PRODUCT_PLAN_AUTHORITY=1`, `PLAN_SCOPE=godot/dogfood/superfighters`). Parent `zdocs/20-8-godot-agent-autopilot-plan.txt` remains platform closeout history only. |

Parent platform (do not open or tick from this product):

- `CURRENT_VALID_WP=R9-WP4` on the 20-8 plan
- 59/60, G6 `[ ]`, GX `[ ]`
- Not a source of Vault Fighters progress

Product plan at this freeze:

- `CURRENT_VALID_WP=VF0-WP1`
- VF0–VF10 checkboxes **0/50**, none pre-ticked
- Implementer must not tick VF0-WP1

---

## Clean-room status (as of VF0-WP1)

**Allowed:** observe publicly documented behavior (Y8 page, original
game page, developer page, secondary write-ups) to learn mechanics,
controls, modes, and functional map beats.

**Forbidden:** download, rip, trace, reverse-engineer, bundle, or ship
Y8 / Newgrounds / MythoLogic / wiki **packages, SWF, Flash, HTML5
builds, sprites, audio, code, screenshots, or trademarked title
cards**. Do not treat the network as a runtime dependency.

**Shipped content at HEAD `094822467…`:** original GDScript, original
procedural tiles/fighters/weapons/props/VFX/SFX/music. Provenance
pointers already in-tree:

- `NOTICE.md` — original procedural art/audio; Godot MIT; Open Sans OFL
- `assets/ASSET_MANIFEST.json` — per-file SHA-256 of generated assets
- `PROJECT_BRIEF.md` — mechanics intent vs legal/honest non-copy list

The generator script `tools/godot/gen_vault_fighters_art.py` exists on
the working tree as **untracked** at this freeze. It is product-related
provenance, **not** Snake, and is **not** part of HEAD. It is not added
by VF0-WP1 (file scope is `docs/` + manifest). Later WPs that own art
tooling may commit it.

**Geometry / names:** first-playable maps echo four Stage archetypes
(rooftops / storage / police / hazardous) with original tiles and
display names. Exact coordinate copy of the reference is not claimed
and is not a VF0-WP1 acceptance. If a later map pass is too close for
commercial release, stop for legal review (plan §3.3); agents must not
self-certify fair use.

**Clean-room state label:** `in_force`. No reference binary or ripped
asset is in the product tree at the frozen HEAD. VF1-WP1 must add
dated observation rows before any “matches Y8” claim (V-A20).

---

## Reference URLs (observation deferred)

These URLs are the plan’s minimum reference set. **VF0-WP1 did not
open or cache them.** Status is `deferred_to_VF1-WP1`, confidence
`none`. Do not treat the table below as `observed`.

| URL | Role | Status this WP |
|---|---|---|
| https://www.y8.com/games/superfighters | Primary public reference page | `deferred_to_VF1-WP1` |
| https://www.newgrounds.com/portal/view/575163 | Original release context | `deferred_to_VF1-WP1` |
| https://mythologicinteractive.com/Superfighters | Developer controls/loop cross-check | `deferred_to_VF1-WP1` |

No reference screenshot, SWF, or HTML5 package is stored in this
folder or in `docs/`.

---

## Baseline honesty (not parity)

HEAD `094822467…` is a **first playable slice**: title → fight →
win/lose → restart; VS 1P/2P; four grid maps; basic movement; simple
ladder; fists/pistol/UZI/shotgun/pipe/knife/grenade; HUD/pause;
headless `tests/run_all.gd`.

It is **not** “closest possible to Y8”. Known gaps at freeze are in
`KNOWN_ISSUES.md` plus plan §2 (ObjectDB/AudioStream leak on process
exit; tests teleport/reset; missing roll/dive/kick, Survival, six-map
set, etc.). VF0-WP2 owns teardown hygiene. Gameplay parity WPs start
at VF1.

---

## Ledger hash / how later WPs must extend this file

VF1-WP1 (and later) must append dated rows with:

- URL, Asia/Saigon datetime, page version/status
- `observed` / `reported` / `assumption` (never guess-as-fact)
- behavior to reproduce vs tuning-only numbers
- intentional original deltas (names, art, topology)
- hash of the related spec/trace — **no reference assets**

Until those rows exist, no agent may claim Y8 parity.

---

## VF0-WP2 hygiene note (not Y8 observation)

Headless `tests/run_all.gd` uses `App.test_driven` → `SfxBank.muted` so
the official process does not load or play `AudioStream` resources.
Windowed `tests/run_window_hygiene.gd` uses live music/SFX and must
`shutdown()` stop/clear players. This is resource hygiene, not a
parity claim.

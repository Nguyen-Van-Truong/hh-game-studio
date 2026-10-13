# Superagent visual audit — 13-10-2026

`STATUS=BLOCKED_BY_RUNTIME_SCREENSHOT`
`SCOPE=GROKDO_SA10_RELAY_YARD_SLICE_AND_MAIN_PLAN_LESSONS`
`NOT_A_CHECKBOX=1`

This audit records the owner screenshot, a read-only inspection of the current
Grokdo source/assets, and a small public reference review. It is a design and
triage document, not an acceptance critic. It does not tick SA-10, SA-02, or
any Classic gate.

## What the current build actually shows

The owner screenshot (`codex-clipboard-1e813a27-66a6-4c94-9ea8-7e38660b2010.png`)
is a wide Relay Yard frame. The two fighters are only a few pixels of detail
at that framing, the floor props read as repeated rectangles, the lower half is
mostly empty dark fill, and the HUD is dense enough to feel like a debug view.
The P1/P2 readout uses the same Vale identity in this frame. This is a visual
blocker, not a gameplay or physics verdict.

The newer close still (`superagent-grokdo/docs/evidence/relay-vale-brisk-near.png`)
does make Vale and Brisk distinguishable and gives pickups separate marks, but
it is still a prototype presentation. Static inspection found:

- `tools/make_fighter_sheet.py` authors most fighter pixels with `rect`/`paint`
  primitives. A 64×64 cell and a 46-pixel standing body add padding and pose
  coverage; they do not by themselves provide facial, hair, cloth, lighting or
  silhouette detail. The PNG and tests prove geometry, not visual quality.
- `tools/make_world_sheet.py` contains an eight-tile 16×16 kit. It has useful
  color seeds, but it is too small and too uniform to carry a complete arena
  by itself. Repeated flat fills are the reason props still look like debug
  blocks when scaled up.
- `game/fighter/fighter_view.gd` already has a reusable package/anchor path,
  health/stamina bars, held-item drawing and presentation cues. Keep this
  boundary; replace the art data and item/world pictures before adding more
  renderer branches.
- The evidence log repeatedly says that audio was not heard in a match clip
  and that the stills are disposable-copy captures. These are useful progress
  records, not owner visual approval.

## Reference observations, used only as broad targets

Public pages are references for composition and readability. No screenshot,
sprite, logo, sign, HUD label, map name, sound or distinctive silhouette may be
copied or shipped.

| Source | Safe observation for this project |
|---|---|
| [Y8 Superfighters page](https://www.y8.com/games/superfighters) | Retro pixel presentation, local two-player arena, weapons and vertical platform play are the functional context. |
| [Developer's Newgrounds page](https://www.newgrounds.com/portal/view/575163) | The author explicitly called out an update that improved player/weapon visibility; readability is a first-class target. The page also describes 13 weapons, four maps and Box2D spectacle. |
| [MythoLogic site](https://mythologicinteractive.com/Superfighters) | Public promo views show compact high-contrast fighters, a darker but structured industrial/city background, stacked platforms/ladders, warm muzzle/explosion accents and a compact top HUD. |
| [Official Steam page for Superfighters Deluxe](https://store.steampowered.com/app/855860/Superfighters_Deluxe/) | The developer describes movable, destructible, burnable and throwable objects and a retro sci-fi world. Props must communicate material and purpose, not be decorative rectangles. |
| [SteamDB screenshot gallery](https://steamdb.info/app/855860/screenshots/) | Useful for studying varied composition and density; it is not a pixel-diff or a source of asset dimensions. |

These observations imply five project corrections: readable fighter silhouettes
at play scale, thick and layered walkable architecture, distinct material/icon
language for pickups and weapons, a controlled dark-to-light contrast hierarchy,
and a compact HUD with room for the arena. They do **not** imply copying the
reference palette, billboard, title, UI, map landmarks or sprite style.

## Corrective route (one slice, then expand)

The following is the implementation order for SA-10's existing visual lane; it
does not create new WPs.

1. **Freeze the current checkpoint.** Stop adding isolated micro-fixes and
   record the current source hash. A generator may pack/validate art, but
   rectangle primitives are not an acceptable final fighter or prop source.
   Keep gameplay, collider, shot origin, map topology and replay state intact.
2. **Fix composition and HUD blockers.** Set one documented near/far camera
   framing, reserve a safe margin for both panels, and remove the large empty
   visual void with authored background layers. Do not move physics bodies or
   change simulation units to make a screenshot look fuller.
3. **Author fighter A, then B.** Create editable source layers under
   `art/source/characters/<id>/` (body, face/hair, outfit, accessory and
   pose guides), export the existing atlas/JSON/anchor contract, and draw
   silhouette, face, hands, boots, cloth highlights and action poses by hand in
   the chosen pixel tool. B must have a genuinely different silhouette, not a
   recolor. If no legitimate authoring tool is available, record a GAP and keep
   the generated sheet provisional; do not call it finished art.
4. **Replace the prop/item kit.** Give floor items and held weapons distinct
   silhouettes, 2–3 value steps, a one-pixel edge/highlight and a shared icon
   identity. Letters can remain as an accessibility/debug aid, but never be the
   primary identity in the final play view. Build a small authored set of wood,
   steel, glass, fire and concrete motifs with visible thickness and damage
   states. Use the current data IDs and collision bodies.
5. **Dress Relay Yard.** Use three visual depth layers (far, architecture,
   foreground), a clear theme, visible platform edges, ladders, cover and a
   few landmarks. Keep negative space around fighters and hazards; do not fill
   every pixel with noise. Reuse the tile/prop contract only after the one
   scene reads correctly.
6. **Tune presentation after the art exists.** Add only event-bound VFX/SFX:
   muzzle, hit, metal spark, wood/glass break, fire, smoke, landing and pickup.
   Use CPU/flipbook fallbacks for Compatibility/Web, cap lifetime/voices and
   keep effects out of simulation/hash. Capture a short clip and listen to it.
7. **Review the slice before roster/map expansion.** Capture the same build at
   far, near and action framing plus a HUD/resize frame. The owner review must
   answer whether fighters, items, platforms, hazards and P1/P2 panels read
   without zooming or debug labels. A technical test or file count cannot answer
   this.

## Visual slice gate (feeds Q6/Q7; no new checkbox)

Keep SA-10 open until all rows have a runtime artifact and status:

| Check | Required artifact | Failure means |
|---|---|---|
| Fighter readability | Far + near stills and a short action clip | Replace art/scale/composition; do not add particles to hide it. |
| Item/weapon identity | Still with floor items and held weapons, plus pickup/throw clip | Rework silhouettes/icons/material cues. |
| World depth/material | Relay Yard still showing far/architecture/foreground layers | Add authored architecture and material motifs; preserve collision. |
| HUD/camera | 960×540, 1280×720 and 1366×768 frames with both panels intact | Fix containers/safe margins/camera contract. |
| Motion/audio | 20–60 second clip actually viewed and heard | Mark audio/animation GAP; do not infer from WAV files or assertions. |
| Provenance | Source-layer paths, tool/version, export hash and `LICENSES.tsv` | Keep the asset provisional and block roster expansion. |

This gate is deliberately visual and human-readable. It is not a claim that a
single screenshot proves Superfighters parity. Functional parity, SA-02
measurement and owner release approval remain separate gates.

## Lessons to keep visible

- “64×64 sheet”, “more frames”, “more particles”, a passing pixel assertion or
  a successful export does not mean the art is good. Inspect the running frame.
- The previous approach improved technical pose coverage before improving the
  authored pixels. The next change must replace the source art itself, not add
  another presentation overlay.
- A wide camera can make correct art look like dots; prove both far and near
  framing before choosing a final scale. Do not compensate by changing hitboxes.
- Finish one readable scene and two real silhouettes before six maps or a large
  roster. Keep the current renderer/data contract so the work remains reusable.
- Keep the current status/NEXT short. Put detailed micro-fix receipts in
  `docs/evidence/` or a dated history file; never let them become a second
  progress ledger.


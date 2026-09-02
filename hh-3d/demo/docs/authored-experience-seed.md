# Authored experience seed — Hòn Gió person

Cite this file from a future **HH World R4-WP1** (authored experience layer / F2).
This demo is the seed. It is not that work package.

## What this seed is

A small original WebGL diorama in `hh-3d/demo`:

- a stylized **person** you can walk and run on authored pads
- **board / deboard** a thúng (round basket boat) with a sit pose and oar
- **Chơi** follow camera vs **Toàn cảnh** (and look-at bookmarks)
- a slim Vietnamese HUD (status, hint, E prompt)
- local **over-head chat bubble**: Enter opens chat, draft text appears above
  the player character on every keystroke, Enter speaks, Escape cancels

The fresh-load presentation is **Toàn cảnh**; entering **Chơi** is an explicit
user action so a first-time visitor sees the authored place before controls.

Later plans can drop this experience on a map marker. Do not start
`hh-3d/app/` or R0+ from this seed.

## What this is not

- Not a real map (no Cesium, MapLibre, OSM, tiles, search, or place cards)
- Not GTA / open-world systems (no traffic AI, wanted, interiors, vehicles)
- Not the HH World MVP
- Not Vault Fighters / Godot / Kho Bí Ẩn / Snake
- Not a licensed character pack

## Stable ids and contracts to reuse

| Kind | Id / file | Role |
| --- | --- | --- |
| Player root | `name="player"` in `src/scene/World.tsx` | Transform the later GLB keeps |
| Person visual | `name="person"` in `src/scene/Person.tsx` | Mesh + pose API |
| Pose API | `applyWalkPose(limbs, time, seated, moving, running, reducedMotion, sailing)` | Idle breathe, walk, run, sit, oar dip |
| Limbs | `PersonLimbs` in `Person.tsx` | root, torso, two-segment arms/legs, oar |
| Boardable boat | `name="boat"` in `src/scene/Boat.tsx` | `ThungHull`, `occupied` hides hull oar |
| Idle boat | `name="idle-thung"` | Decoration only |
| Input | `src/lib/input.ts` | WASD / arrows, Shift run, `interactEdge` on E |
| Walk pads | `WALK_PADS`, `BOARD_DISTANCE` in `src/lib/walk.ts` | Collision + deboard landing |
| Board loop | `src/scene/SimClock.tsx` | E when near; sit on boat; `nearestWalkable` on leave |
| HUD | `PlayHud` in `src/lib/play.ts` | `boarded`, `nearBoat`, `hasMoved` |
| Play camera | `playFollow` + `playFollowCamera()` in `sceneConfig.ts` / `CameraRig.tsx` | Chest look-at, closer offset |
| Overview camera | `sceneConfig.presets.overview` | Whole-island bookmark |
| Chat state | `src/lib/chat.ts` | `typing` / `spoken`, max length and visible timeout |
| Chat composer | `src/ui/ChatComposer.tsx` | Enter-to-chat input; gameplay input is blocked while typing |
| Chat bubble | `src/scene/PlayerChatBubble.tsx` | Drei `Html` anchored above the player group |
| Forced routes | `/?boat=1`, `/?walk=1`, `/?preset=overview` | Start boarded / short walk still / overview |

Board contract (keep this if the mesh is swapped):

1. Near boat when XZ distance ≤ `BOARD_DISTANCE`.
2. `E` / `interactEdge` toggles `boarded`.
3. Board: person parent-equivalent sits at boat XZ/yaw; oar visible; WASD steers in the bay.
4. Deboard: stand on `nearestWalkable` (pier / pad), not in open water.

Camera contract:

- **Chơi** (`viewMode === "play"`) follows `player` at `playFollow` chest height.
- **Toàn cảnh / Bến / Hải đăng / Đảo** are look-ats. Do not reuse play offsets for the globe.

Chat contract:

1. Enter only opens chat in **Chơi**; opening chat releases pointer lock.
2. While the composer is focused, movement/look/jump/boat/punch input is
   blocked so typed WASD/F/E/Space cannot mutate gameplay.
3. The local bubble is attached to the player world transform, not to a fixed
   screen coordinate. Draft characters render immediately with phase `typing`.
4. Enter normalizes/submits the message as phase `spoken`; Escape discards the
   draft. Spoken bubbles currently expire locally after a short timeout.
5. Future multiplayer should reuse the same `PlayerChatBubble` view per remote
   player. Do not send raw keystrokes directly to every peer: throttle optional
   typing-preview updates, and send final spoken messages through a server-side
   validation/rate-limit/moderation path.

## Upgrade path

1. Keep input, walk pads, board distance, HUD, and camera mode split.
2. Replace the procedural children of `name="person"` with a **licensed** GLB (tiny, ledger written).
3. Map clips to the same verbs: `idle`, `walk`, `run`, `sit`, `row`.
4. Keep `applyWalkPose` as a facade, or drive an `AnimationMixer` from the same flags SimClock already sets.
5. Do not rip Y8 / marketplace characters. Do not add Cesium or GTA systems here.

## License

All geometry in this seed is **original** and authored for the Hòn Gió demo
(primitives / procedural capsules only). No third-party GLB, rip, or
trademarked title card. Palette is a soft Vietnamese-coastal diorama, not a
copy of another product.

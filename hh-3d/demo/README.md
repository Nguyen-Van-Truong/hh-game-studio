# Hòn Gió — WebGL demo

Interactive 3D coastal diorama for HH-3D. This is a **developer-only demo**.
There is **no public URL** yet.

Requires **Node.js** (this lock was created with Node v24 / npm 11).

## Open the demo

```bash
cd hh-3d/demo
npm ci
npm run dev -- --host 127.0.0.1
```

Then open the printed local URL (default `http://127.0.0.1:5173`).

Production preview:

```bash
npm run typecheck
npm run build
npm run preview -- --host 127.0.0.1
```

Vite does not typecheck; always run `npm run typecheck` as its own gate.

## Performance notes

High quality caps the drawing buffer at `devicePixelRatio <= 1.5` and uses
the actual display density; Low quality uses DPR 1, fewer instances, and no
shadows. The production bundle contains the Three/R3F/Drei vendor stack, so
Vite may report a large-chunk advisory (it is not a runtime error). A later
public release should add vendor caching/code-splitting after measuring a real
deployment; this developer demo does not hide that advisory by changing the
warning threshold.

## Controls

On-screen actions are Vietnamese. Keyboard:

- **WASD** or **arrow keys** — walk (or steer the thúng when boarded)
- **Shift** — run
- **Mouse drag** (left or right) — orbit around the person in Chơi, or around the island in Toàn cảnh
- **Scroll** — zoom (Chơi stays close enough to read the body; it will not sit inside the head)
- **E** — lên thuyền / xuống thuyền when the prompt appears
- **Esc** — close a landmark card or help
- **?** — open help
- Touch: on-screen arrows, **Chạy**, and **E** on narrow / coarse-pointer screens

On a fresh load the demo opens in **Toàn cảnh** so the island reads immediately. **Chơi** follows a bit higher and farther back so the full person, walking surface, pier, and thúng remain visible; **Toàn cảnh** looks at the whole island; **Bến / Hải đăng / Đảo** are look-at bookmarks. Portrait screens use a pulled-back composition so the lighthouse does not disappear off the edge.

A later HH World plan can cite `docs/authored-experience-seed.md` (walk + board thúng + follow cam). That file is a seed note only — this folder is not HH World.

Forced routes: `/?preset=overview`, `/?boat=1` (start already on the thúng), `/?walk=1` (hold a short forward walk for capture), `/?select=lighthouse`, `/?quality=low`, `/?fallback=1`, `/?debug=1`.

## What a first-time user can do in 30 seconds

1. See the whole pastel diorama, title **Hòn Gió**, and the four landmark controls.
2. Press **Chơi**, walk onto the island, press **E** by the thúng, sail the bay, then leave the boat.
3. Return to **Toàn cảnh** or click a landmark for a short card.

## Smoke

Follow `tests/smoke.md`. Official screenshots belong under `evidence/` and must be of the running app, not mockups.

## What this is

A small authored browser scene: pastel sea, terraced island, striped lighthouse,
wooden pier, a person you can walk, a thúng you can board, and a slim DOM overlay.
It is an interactive web diorama, not a still image, not a city, and not a real map.

## Non-goals

- Not a real map, OSM/Overture/Google tiles, or “map thật”
- Not GTA, Pelago, Saltwind, or any copied brand/layout
- Not Vault Fighters / Godot / Kho Bí Ẩn / Snake
- Not a public product, login, backend, or multiplayer service
- Boat motion is a toy on a water plane (bay bound + gentle bob), not vehicle physics

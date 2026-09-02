# Hòn Gió smoke checklist

Developer-only. No public URL. Requires Node, then:

```bash
cd hh-3d/demo
npm ci
npm run typecheck
npm run build
npm run preview -- --host 127.0.0.1
```

Open `http://127.0.0.1:4173/`. This is an interactive 3D place, not a still image.

Do not claim 60 FPS. Debug frame time is only at `/?debug=1` and must come from runtime. If you cannot read it, write `UNMEASURED`.

## Trace

1. **Boot** — page is not white. Loading overlay may flash, then the pastel sea, island, lighthouse, pier, and thúng appear in **Toàn cảnh**. Header reads **Hòn Gió** and **Diorama WebGL**. The story card and landmark dock are readable.
2. **Walk** — WASD or arrows move the person. Shift runs. They stay on pier / stairs / terraces / beach and do not walk the open ocean. They do not fall through the pier or slide through the lighthouse or houses.
3. **Boat** — walk to the thúng. Prompt **E — lên thuyền**. Board: person sits with hands on an oar; WASD steers inside the bay and the oar dips; **E — xuống thuyền** leaves them standing on nearby walkable ground if possible.
4. **Camera** — Chơi follows the person. Toàn cảnh / Bến / Hải đăng / Đảo are look-ats. Drag orbit and scroll zoom stay clamped.
5. **Select** — click the lighthouse or press **Hải đăng sọc**. The object card opens. Escape or **Đóng** closes it and focus returns.
6. **Hint** — Toàn cảnh explains orbit/select/Chơi; Chơi explains movement. The hint collapses after the first move. **?** still opens help.
7. **Quality** — press **Cao** so it becomes **Thấp**. Shadows/DPR/instances drop. Do not treat this as Y8/AI parity.
8. **Resize** — 1280x720, 1024x768, and a narrow phone width. The island and lighthouse stay readable; the camera dock and landmark dock remain separate. No wall of cards.
9. **Fallback** — **?** then **Xem bản tĩnh**, or open `/?fallback=1`. SVG + landmark names + descriptions + “Open 3D view”. Also try `/?error=1`.

## Forced routes

- `/?fallback=1` — static view
- `/?error=1` — runtime error fallback
- `/?preset=harbor` — Harbor camera
- `/?preset=overview` — Overview camera
- `/?boat=1` — start boarded on the thúng
- `/?walk=1` — short automatic forward walk (for stills)
- `/?select=lighthouse` — object card open
- `/?quality=low` — low tier
- `/?debug=1` — runtime frame readout (never hard-coded 60)

## Pass / fail

Record FAIL as FAIL. Do not change the expected result to make a run look green.

The build may print Vite's large-chunk advisory for the Three/R3F/Drei vendor
stack. Treat it as a documented bundle-size follow-up, not as a hidden runtime
pass; runtime console errors and unexplained warnings are still failures.

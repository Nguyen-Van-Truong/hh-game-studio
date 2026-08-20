# gs-editor

Editor bus, authority, confirmation, activity feed (WP-M0-4), the
eframe/wgpu 5-region viewport (WP-M1-2), gizmo move/rotate/scale
(WP-M1-3), and hierarchy / schema-driven inspector / png import (WP-M1-4).

Does **not** load Luau gameplay (I3). Document mutations go through `gs-scene`.
Pan/zoom/grid/snap/local selection are **view-state** and never call
`Session::dispatch` (I1). `human_ui` is in-process only — never issued over TCP
(I8 / 4.4).

## Public API

```rust
let bus = gs_editor::start(runtime_root)?;
// binds 127.0.0.1, writes {root}/.gs/runtime/endpoint.json
// {host, port, token, pid}

let mut agent = bus.connect_agent("coder")?; // TCP hello → principal agent
agent.call("entity.spawn", serde_json::json!({
    "command_id": ulid,
    "name": "hero"
}))?;

let ui = bus.ui(); // in-process human_ui (act_01)
ui.begin_gizmo_drag("e_000001", gs_editor::GizmoKind::Move)?;
ui.update_gizmo_drag(gs_editor::GizmoDragUpdate::move_by(1.0, 0.0))?;
ui.end_gizmo_drag()?; // one component.set; feed badge Human / [BẠN]
ui.call("undo.perform", serde_json::json!({}))?;
ui.feed();
ui.session_panel();
ui.viewport_entities(); // document → viewport (read-only; preview while dragging)
ui.hierarchy();         // parent/order tree
ui.inspector("e_000001"); // schema fields + values
ui.call("entity.reparent", json!({ "ids":[id], "new_parent": parent })); // keep_world defaults true
ui.call("asset.import", json!({ "src_abs": src, "dest_rel": "assets/a.png" }));
```

`gs-editor <project-dir>` starts the bus and `project.open`s that directory.
With no argv: open `cwd` if it has `project.json`, else `games/snake` (must
have `project.json`), else `games/platformer` if that folder exists. Otherwise
print `usage: gs-editor <project-dir>` and show the window with no session
(demo IR only). Never `project.open` the repo root just because it is cwd.

`cargo test -p gs-editor` uses [`start`](crate::start) only — no window.

## Viewport (WP-M1-2)

- Camera / grid / snap live in `ViewState`. `apply_view_navigation` has no
  Session argument.
- Pick uses `gs_render2d::pick` (CPU alpha > 0.1, G1).
- Open project entities become `RenderItem`s (Transform2D + Sprite color/pivot;
  missing sprite → solid quad). Tilemap RLE cells expand to earth-tone quads
  (cap 2048). Camera-only entities are not drawn as a body quad. Demo IR only
  when no session is open.
- Overlays: world-space grid, Collider2D box/circle/capsule, script-error badge
  placeholder (empty/missing `.luau` file — no Luau until M3).
- Frame-time budget is **unmeasured** (I13). Do not cite 60fps from this crate.

## Gizmo (WP-M1-3)

- `UiHandle::begin_gizmo_drag` / `update_gizmo_drag` / `end_gizmo_drag`.
  Updates are preview-only (no dispatch). Release commits **one**
  `component.set` Transform2D via the dispatcher (I1 / 2.8).
- Soft lock (editor-layer, TTL 2s, renew on update): agent
  `component.set` / `entity.destroy` / `entity.reparent` /
  `transaction.execute` that touches the entity → `-32002` `E_LOCKED`
  with owner + "gizmo drag". `human_ui` can still finish the drag.
- Viewport draws axis / ring / scale-box handles; Q/W/E/R pick the tool.
  Tests do not open the window.

## Hierarchy / Inspector / import (WP-M1-4)

- `UiHandle::hierarchy` builds a parent/order forest from the open document.
  Drag-reparent in the eframe panel calls `entity.reparent` with
  `keep_world: true` (also the default when the field is omitted).
- Inspector widgets iterate `component.registry` field kinds (`f32`, `bool`,
  `asset`, …). Adding a MASTER 5.2 type is a schema-table row, not a new
  widget function. Field edits dispatch `component.set`. Add/remove buttons
  call `component.add` / `component.remove`.
- `asset.import` / `asset.list` are editor-layer (gs-scene has no import
  command). `src_abs` may be outside the project (I7 exception). `dest_rel`
  is jailed with canonicalize+prefix; `..` and Windows reserved names are
  rejected. Preview is PNG IHDR width/height — no GPU atlas streaming yet.

## Gaps

- `entity.lock` / `entity.unlock` protocol methods are still unimplemented
  in gs-scene; this crate uses an in-memory gizmo soft lock instead
- Imported PNG is not uploaded into the viewport atlas (preview is header-only)
- `asset.import` is not a gs-scene WAL command (editor-layer copy + index)
- No jobs, so pause cannot cancel in-flight jobs
- Capability grants are in-memory (not WAL-audited)
- `play.start` / `stop` / `status` / `pause` / `resume` / `step_frames` /
  `set_timescale` are editor-layer: spawn `gs-player --control-port 0
  --headless` and forward. Agents never receive the player token or port.
  Live-view and `runtime.copy_to_scene` are M2-4.
- `script.create` / `set_source` / `get_source` / `ingest_external` /
  `reload` / watcher / conflict / `script.diagnostics` are wired.
  `luau-analyze` is resolved from `GS_LUAU_ANALYZE`, `tools/`, then PATH
  (sync spawn, 2s timeout). Missing or broken binary → `type_check: "off"`
  and banner `"type check off"`; findings are warnings and do not block
  run/save. Editor does not load Luau (I3).
- `judge.run_test` loads `tests/*.gtest.json`, starts headless play (rewrites
  a tape header from the live snapshot when `tape` is set; otherwise injects
  a short `move_x=1` walk), drives asserts, and writes an evidence bundle
  under `.gs/runtime/evidence/<test>-<ts>/`. Fail is `E_ASSERT` with the
  bundle path in `error.data.reason`. `artifact.list` / `get` / `gc` index
  `.gs/runtime/` (get returns a file path, not a blob).
- `build.game` / `build.status` / `build.cancel` pack a standalone Play
  folder via `gs_player::pack_project` (T7A.1). `out_dir` must sit
  outside the project (I7). Export is unsigned (`docs/EXPORT_SIGNING.md`).
- Later-milestone methods (other `asset.*`, leftover `script.*`,
  leftover `build.*`, blueprint over bus) return `-32601`

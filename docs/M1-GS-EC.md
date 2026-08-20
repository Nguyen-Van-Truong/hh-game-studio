# M1 GS-EC matrix (WP-M1-5)

Checklist for MASTER T1.5 / 12.1. Status is `pass` only when a real automated
test exists. Do not treat a written target (60 fps, 16.7 ms) as measured.

Kind: **I** integration, **perf** measure, **M/T** manual.

| test_id | case | test location | kind | status |
|---|---|---|---|---|
| GS-EC-05 | scene 100k entity; cap `scene_max` 50k; warn 20k; culling 10k visible | `m1::gs_ec::gs_ec_05_document_accepts_count_above_warn_threshold`; `m1::gs_ec::gs_ec_05_session_max_txn_spawn_is_uncapped_by_scene_max`; 10k draw in `m1::perf::measure_10k_sprites_offscreen` + `docs/M1-PERF.md` | I,perf | **gap** — `gs-scene` has no `scene_max` / 20k warning (Error has no cap variant). Document `apply_txn` accepts 20 200 entities. Dispatcher 200-spawn txn (txn command cap) succeeds. No sprite culling in `gs-render2d`. 10k offscreen time is measured; see M1-PERF (do not assume 60 fps). Cap must not be added in this WP. |
| GS-EC-12 | person drags gizmo on entity an agent is setting → soft lock 2s; agent `E_LOCKED` + note | `gs-editor::wp_m1_3::agent_component_set_during_gizmo_drag_is_locked` (also `gizmo_drag_commits_one_revision_and_undo_restores`, `agent_can_set_transform_after_gizmo_drag_ends`) | I | pass — already automated in WP-M1-3; not re-implemented here |
| GS-EC-46 | GPU device lost / driver update → recreate surface + reload texture cache | — | M/T | **manual** — needs a real device-lost / TDR / driver-reset. `gs-render2d` has no injected lost-device hook and no recreate path under test. Checklist: trigger lost device, confirm editor/player survive, surface + atlas cache reload, document stays intact. |
| GS-EC-47 | DPI changes mid-session → viewport follows physical px | — | M/T | **manual** — needs an OS DPI change or drag between monitors. Viewport already takes physical px (MASTER 2.3); this WP cannot change display scale from a unit test. Checklist: drag the viewport between two displays (or change scale), pick/gizmo stay aligned to the sprite. |

## Manual reasons (only these)

- **GS-EC-46**: device-lost is a GPU/OS event; no safe synthetic path without changing `gs-render2d` (out of scope).
- **GS-EC-47**: DPI is an OS/window property; automated tests pass a fixed physical size into `render_offscreen_png` / the viewport callback.

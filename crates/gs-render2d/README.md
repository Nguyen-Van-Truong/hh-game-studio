# gs-render2d

Production 2D sprite renderer (WP-M1-1). One `RenderSnapshot` IR drives
offscreen PNG, eframe (`CallbackTrait`) viewport, and winit/player surface.

Does **not** load Luau. Does **not** depend on `gs-scene` / `gs-editor`.

## Public API

| Item | Role |
|------|------|
| `RenderSnapshot` / `Camera2D` / `RenderItem` | IR (Y-up, pivot BL, sort z then id) |
| `TextureId`, `AtlasCpu`, `pack_atlas` | CPU atlas (sRGB, 2px pad, nearest) |
| `PPU_DEFAULT` (16), `ATLAS_PADDING_PX` (2), `PICK_ALPHA_THRESHOLD` (0.1) | Locked constants |
| `sort_items`, `pick` | CPU pick (alpha > 0.1, front-to-back) |
| `render_offscreen_png` | Target 1 — PNG bytes |
| `ViewportCallback` / `install_sprite_gpu` | Target 2 — eframe physical-px canvas |
| `render_snapshot_to_surface` / `render_snapshot_to_view` | Target 3 — wgpu surface |
| `SpriteGpu` | Shared vertex/GPU path (`sprite.wgsl`) |

## Gaps vs full MASTER 2.3

- **glyphon / text** — later WP
- **tilemap chunks** — later WP (M4)
- **10k sprite @ 60fps** — I13 target; not measured in this crate

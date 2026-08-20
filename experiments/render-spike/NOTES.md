# WP-M-1-a — renderer 3-target spike

**Status:** spike only. Not production. Not `gs-render2d`.
**Date:** 2026-08-16
**Host rustc:** 1.93.1 (01f6ddf75 2026-02-11)
**Host cargo:** 1.93.1
**GPU used for offscreen:** NVIDIA GeForce GTX 1660 Ti (Vulkan, DiscreteGpu)

One crate (`experiments/render-spike`, standalone package, not a workspace member)
draws the **same** `RenderSnapshot` IR on three wgpu targets.

## Version table (known-good pin, not independent “latest”)

Pinned to the **egui 0.31.1** line (wgpu 24 + winit 0.30). Cargo resolved
patch versions within that pin. Do not bump one crate without re-testing the set.

| Crate     | Cargo.toml pin | Locked (Cargo.lock) |
|-----------|----------------|---------------------|
| egui      | =0.31.1        | 0.31.1              |
| eframe    | =0.31.1 (default-features=false, `default_fonts`+`wgpu`) | 0.31.1 |
| egui-wgpu | =0.31.1        | 0.31.1              |
| wgpu      | 24.0.3 + features `wgsl`, `dx12`, `metal`, `vulkan-portability` | 24.0.5 |
| image     | 0.25.6 (png only) | 0.25.10          |
| winit     | 0.30.9         | 0.30.13             |
| pollster  | 0.4.0          | 0.4.0               |
| bytemuck  | 1.21           | 1.25.2              |

`eframe` 0.31 only enables wgpu backends `metal`+`webgpu` by default. This crate
depends on `wgpu` directly so Windows gets **DX12** and **Vulkan**.

## Locked constants (MASTER 2.3 — do not invent different ones)

| Constant | Value | Where in spike |
|----------|-------|----------------|
| PPU default | **16** | `PPU_DEFAULT` — 16px sprite = 1 world unit at native scale |
| Axis | **Y-up** | clip.y = +(world.y − camera.y) |
| World origin | **(0,0) at default camera center** | `Camera2D::default().position = [0,0]` |
| Pivot | **[0..1]², origin = bottom-left of sprite** | `RenderItem.pivot`, default `[0,0]` so `(x,y)` is BL |
| Textures | **sRGB** | atlas `Rgba8UnormSrgb` |
| Blend | **premultiplied alpha** | upload PMA; blend `One / OneMinusSrcAlpha` |
| Output surface | **sRGB** | offscreen `Rgba8UnormSrgb`; player prefers `is_srgb()` format |
| Sort | **z_index then entity_id (stable)** | `sort_items` — lower draws first |
| Atlas padding | **2px** | `ATLAS_PADDING_PX` |
| Filter | **nearest** | mag/min/mip `Nearest` |
| Picking | **alpha > 0.1 on small CPU sample** (see below) | `pick` / `PICK_ALPHA_THRESHOLD` |
| DPI | **viewport in physical pixels**; **egui points only for UI chrome** | viewport bin: canvas size = rect × `pixels_per_point` |

### Picking (one method, chốt)

**Chosen:** alpha > 0.1 via a **small CPU sample** of the atlas texel (or solid
color alpha) under the cursor after converting physical pixels → world.

- Walk items **front-to-back** (reverse of draw sort).
- Hit test the Y-up AABB (pivot-aware).
- Sample atlas alpha at the sprite UV. Transparent 2px gutter on `TEX_HERO`
  can miss even when the pointer is inside the AABB.
- **Not** a GPU framebuffer readback. **Not** collider-based.
- Returns `entity_id` (an ID-buffer readback would also work later; not in this spike).

## Three targets

| Target | How | Compiles | Runs in this session |
|--------|-----|----------|----------------------|
| 1. eframe + `egui_wgpu::CallbackTrait` viewport | `cargo run --bin viewport` | **YES** (`cargo test` built `src/bin/viewport.rs`) | **not launched** (needs interactive window) |
| 2. winit window | `cargo run --bin player` | **YES** (`src/bin/player.rs`) | **not launched** (needs interactive window) |
| 3. offscreen headless PNG | `cargo run --bin offscreen` or `cargo test` | **YES** | **YES** — `out/spike.png` written |

No target was dropped. eframe + winit compiled together on the pin set above.

### How to run

```powershell
cd experiments/render-spike
cargo test
cargo run --bin offscreen
cargo run --bin viewport
cargo run --bin player
```

All three bins call `demo_snapshot()` + `demo_atlas()` — the same IR.

- **viewport:** chrome (title / pick / ppp) is egui **points**. The canvas
  `CallbackTrait` prepares vertices in **physical px** and sets
  `set_viewport` / `set_scissor_rect` from `PaintCallbackInfo::viewport_in_pixels()`.
- **player:** winit window, physical inner size, hover pick updates the title.
- **offscreen:** 640×360 → `out/spike.png`.

## VERIFY log (2026-08-16)

```
$ rustc --version
rustc 1.93.1 (01f6ddf75 2026-02-11)

$ cargo test
running 8 tests
test tests::default_camera_centers_world_origin ... ok
test tests::locked_constants ... ok
test tests::pick_hits_frontmost_opaque ... ok
test tests::pick_misses_transparent_hero_border ... ok
test tests::pivot_origin_is_bottom_left ... ok
test tests::pick_hits_hero_center ... ok
test tests::sort_is_z_then_entity_id ... ok
test tests::offscreen_writes_real_png ... ok
test result: ok. 8 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 1.08s
(also compiled bins viewport / player / offscreen as part of cargo test)

$ cargo run --bin offscreen
wrote ...\experiments\render-spike\out\spike.png (5610 bytes) via NVIDIA GeForce GTX 1660 Ti (Vulkan, DiscreteGpu)

$ spike.png
exists; size=5610; magic=89 50 4E 47 0D 0A 1A 0A  (real PNG, not 0 bytes)
```

`cargo clippy --all-targets -- -D warnings` also clean after the pin compiled.

## GO / NO-GO

**GO — one `RenderSnapshot` IR can drive all three targets** (eframe CallbackTrait
viewport, winit player, offscreen PNG) in a single crate. Offscreen is the
CI-proof path and produced a real PNG of the demo scene.

This is a **spike**, not a production renderer. No 10k-sprite @ 60fps number
was measured (I13). Atlas is a tiny 3-sprite pack, not a streaming atlas.
Text (glyphon) is out of scope. Fallback to full Bevy is **not** indicated
by this spike.

## IR (real types, used by every target)

```text
RenderSnapshot { camera: Camera2D, items: Vec<RenderItem> }
Camera2D      { ortho_height, position }
RenderItem    { entity_id, z_index, x, y, w, h, color rgba, texture: Option<TextureId>, pivot }
```

`build_vertices` + `SpriteGpu` are the only draw path.

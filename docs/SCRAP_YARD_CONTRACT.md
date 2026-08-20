# Scrap Yard — texture pipeline contract (parent-owned)

Shared contract for the four parallel work streams that make `games/scrap-yard`
render real pixel art instead of solid quads. **Nobody edits this file except
the parent agent.** If a stream needs a change here, it must stop and report.

Scope note: this is an **original** game in the 2D arena-brawler genre. Do not
copy Superfighters art, map layouts, level names, or character designs. Names,
silhouettes, palette, and arena layout are ours.

## Why this exists

`gs_runtime_core::render::entity_to_render_item` hardcodes `texture: None`, and
`gs-player` builds its atlas from `gs_render2d::demo_atlas()`. So every sprite
draws as a flat color rectangle and `Sprite.flip_x` is ignored.

## A. `gs-render2d` public API (owned by stream A1)

```rust
/// RGBA8, straight alpha, rows top-down.
pub struct SpriteSource {
    pub id: TextureId,
    pub w: u32,
    pub h: u32,
    pub pixels: Vec<u8>,
}

/// Decode a PNG into RGBA8 straight-alpha rows (top-down).
pub fn decode_png_rgba(bytes: &[u8]) -> Result<(u32, u32, Vec<u8>), Error>;

/// Shelf-pack many sprites into rows. Gutters are ATLAS_PADDING_PX.
/// Must handle 40+ sprites without exceeding 2048 px in either dimension.
pub fn pack_atlas_sources(sources: &[SpriteSource]) -> AtlasCpu;
```

`RenderItem` gains two fields:

```rust
pub flip_x: bool,
pub flip_y: bool,
```

`RenderItem::new` keeps its existing 8 arguments and sets both to `false`.
`build_vertices` swaps `u0`/`u1` when `flip_x`, and `v0`/`v1` when `flip_y`.

## B. `gs-runtime-core` (owned by stream A1)

`World` gains:

```rust
/// Scene `$asset` id (e.g. `a_000020`) → `TextureId.0`. Empty = untextured.
pub texture_ids: BTreeMap<String, u32>,
```

- `entity_to_render_item`: when `Sprite.asset.id` is a key of `texture_ids`,
  emit `texture: Some(TextureId(v))`, and copy `Sprite.flip_x` / `flip_y` onto
  the item. Unknown asset id → `texture: None` (solid quad, current behavior).
- `append_tilemap_render_items`: when the tilemap `tileset` id is in
  `texture_ids`, emit that texture on every cell quad with
  `color: [1.0, 1.0, 1.0, 1.0]`; otherwise keep today's flat `TILE_QUAD_COLOR`.
- `entity_to_render_item` needs `&World` (or the map) to resolve — threading the
  map through `build_render_snapshot` is fine, but keep a public
  `entity_to_render_item(&Entity)` shim that resolves no textures so existing
  callers and tests keep compiling.

New Luau host functions:

- `gs.set_flip(id, flip_x, flip_y)` — buffered like other mutations.
  `flip_y` optional (default: leave unchanged).
- `gs.get_velocity(id)` → `vx, vy` or `nil, nil`. Reads the bound `PhysicsHost`
  exactly like `gs.raycast` does (physics runs after scripts, so this is last
  frame's velocity). Dead id → `nil, nil`, never an error.
- `gs.set_component(id, "Sprite", { flip_x = bool, flip_y = bool })` accepts the
  two new keys in addition to `asset`.

Document all three in `docs/LUAU_API.md`.

## C. `gs-player` (owned by stream A2)

New module `crates/gs-player/src/atlas.rs`:

```rust
/// Build the play atlas from the snapshot's own PNG files.
/// Returns the atlas plus the `asset_id → TextureId.0` map for `World`.
pub fn load_play_atlas(play_dir: &Path) -> Result<(AtlasCpu, BTreeMap<String, u32>), Error>;
```

Rules:

- Read `play_dir/asset-manifest.json` (`asset_id → { path, hash }`).
- `TextureId(0)` is always a 1×1 opaque white sprite (`TEX_SOLID`) so
  untextured quads keep working.
- Assign `TextureId(1..)` in **ascending `asset_id` order** so the atlas is
  deterministic.
- Only `.png` files that exist under `play_dir` are decoded. A missing or
  undecodable PNG is a **warning**, not a `REJECT`: skip it and leave that
  asset untextured.
- Never read outside `play_dir` (I7).

Wire-up:

- `run_window` (`window.rs`): call `load_play_atlas`, assign
  `world.texture_ids`, and pass the atlas to `SpriteGpu::new` instead of
  `demo_atlas()`.
- Headless `run.rs` and the control-server `sim.rs`: also set
  `world.texture_ids` so the render IR is byte-identical to the window path.
  Determinism depends on this.
- `pack.rs` already copies `assets/index.json` entries into the snapshot via
  `AssetInput.content`; do not rewrite that path.

## D. Project asset table (streams A3 and A4 must both follow exactly)

`games/scrap-yard/assets/index.json`:

```json
{ "assets": [ { "asset_id": "a_000001", "dest_rel": "assets/tile_floor.png" } ] }
```

Sizes are in pixels. `PPU = 16`, so a 24×32 sprite is 1.5 × 2.0 world units.

| asset_id | dest_rel | px | content |
| --- | --- | --- | --- |
| a_000001 | assets/tile_floor.png | 16×16 | dark steel deck plate, subtle rivets |
| a_000002 | assets/tile_wall.png | 16×16 | riveted hull wall, vertical girder |
| a_000003 | assets/tile_plat.png | 16×16 | pale catwalk beam, thin top highlight |
| a_000010 | assets/bg_panel.png | 32×32 | dark blue machinery panel (background) |
| a_000011 | assets/lamp.png | 16×16 | caged ceiling lamp, warm glow |
| a_000012 | assets/crate.png | 16×16 | wooden crate with cross-brace |
| a_000013 | assets/barrel.png | 16×16 | red hazard barrel |
| a_000014 | assets/ladder.png | 16×16 | metal ladder rung, tileable vertically |
| a_000020 | assets/vela_idle.png | 24×32 | Vela idle |
| a_000021 | assets/vela_walk_a.png | 24×32 | Vela walk frame A |
| a_000022 | assets/vela_walk_b.png | 24×32 | Vela walk frame B |
| a_000023 | assets/vela_punch.png | 24×32 | Vela punch, arm extended right |
| a_000024 | assets/vela_crouch.png | 24×32 | Vela crouched (art sits in lower 24 px) |
| a_000025 | assets/vela_hurt.png | 24×32 | Vela hurt, head back |
| a_000030 | assets/rook_idle.png | 24×32 | Rook idle |
| a_000031 | assets/rook_walk_a.png | 24×32 | Rook walk frame A |
| a_000032 | assets/rook_walk_b.png | 24×32 | Rook walk frame B |
| a_000033 | assets/rook_punch.png | 24×32 | Rook punch, arm extended right |
| a_000034 | assets/rook_crouch.png | 24×32 | Rook crouched |
| a_000035 | assets/rook_hurt.png | 24×32 | Rook hurt |
| a_000040 | assets/pipe.png | 16×16 | steel pipe weapon |
| a_000041 | assets/blaster.png | 16×16 | stubby blaster |
| a_000042 | assets/bomb.png | 16×16 | scrap bomb with fuse |
| a_000043 | assets/clock.png | 16×16 | brass stopwatch (slow-mo pickup) |
| a_000044 | assets/bolt.png | 8×8 | energy bolt projectile |
| a_000050 | assets/hp_back.png | 16×4 | health bar background |
| a_000051 | assets/hp_fill.png | 16×4 | health bar fill (white, tinted by color) |

### Character art rules (both fighters)

- **All sprites face right.** Left is `flip_x = true` at runtime.
- A readable **face**: two eye pixels plus a mouth or visor line. This is the
  whole point of the work — a silhouette with no face is a failure.
- Feet on the bottom edge of the 32 px canvas (scene pivot is `[0.5, 0.0]`).
- Transparent background (alpha 0), 1 px dark outline around the body.
- Walk A and walk B must differ visibly at the legs and the trailing arm.
- Keep each character to about 6 palette colors so it reads at small size.
- **Vela** — lean courier, cyan/teal jacket, goggles pushed up, short hair,
  taller and narrower (about 12 px wide body).
- **Rook** — heavy breaker, rust orange, welding mask up over a squared jaw,
  broad shoulders (about 18 px wide body).

Neither design may resemble Superfighters' flat-headed men.

### `project.json`

`next_asset` must be **60** (above every id above).

## E. Canonical JSON gotcha (hard-won, do not relearn)

`gs-player --project ... --out ...` **rejects** a scene whose numbers do not
round-trip through the canonical writer (shortest-round-trip `ryu` floats). In
practice, use only values exactly representable in binary:

- Safe: `0.0 0.125 0.25 0.5 0.75 1.0 1.5 2.25 3.5 12.0`
- Rejected: `0.62 4.15 7.4 0.42 1.18`

Any scene edit must be followed by a real pack:

```
target\release\gs-player.exe --project games\scrap-yard --out %TEMP%\sy-check
```

`OK b_...` means the scene is canonical. `REJECT ... not canonical JSON` means a
number needs rounding.

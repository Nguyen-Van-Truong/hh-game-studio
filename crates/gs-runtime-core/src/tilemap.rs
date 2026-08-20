//! Tilemap cell expansion for render (T4.2) and solid-layer collider bake.
//!
//! # Cell origin (world Y-up)
//!
//! Cell `(cx, cy)` is an axis-aligned box whose **bottom-left** corner is
//!
//! `entity.transform.xy + (cx * cell_w, cy * cell_h)`
//!
//! and whose size is `tilemap.cell_size`. Transform rotation and scale are
//! **not** applied to cell placement.
//!
//! # Chunks
//!
//! Occupied cells (`tile >= 0`, `len > 0`) group into [`TILEMAP_CHUNK_SIZE`]²
//! (16×16) cell chunks. [`iter_tilemap_chunks`] is the deterministic iterator
//! (BTreeMap order). Render still emits one [`RenderItem`] quad per occupied
//! cell so the GPU path stays unchanged, capped at [`TILEMAP_QUAD_CAP`].
//!
//! # Bake id scheme
//!
//! Solid-layer colliders are **parented to the tilemap entity's Rapier body**
//! (multiple colliders per body). Collider `user_data` is the tilemap entity
//! id. No reserved bake-id range is allocated — this is distinct from
//! [`crate::RUNTIME_ID_BASE`] (`1 << 40`, `gs.spawn`). If a later WP needs
//! detached bake bodies, use `1 << 48` (above the runtime-spawn range).

use std::collections::BTreeMap;

use gs_render2d::{RenderItem, TextureId};
use gs_scene::{Entity, Tilemap, Transform2D};

/// Cells per side of a render chunk (T4.2).
pub const TILEMAP_CHUNK_SIZE: i32 = 16;

/// Maximum tile quads written into one [`gs_render2d::RenderSnapshot`].
pub const TILEMAP_QUAD_CAP: usize = 4096;

const TILE_QUAD_COLOR: [f32; 4] = [0.42, 0.56, 0.38, 1.0];

/// 16×16 chunk address for a cell. Negative cells use Euclidean division.
pub fn tilemap_chunk_coord(cx: i64, cy: i64) -> (i64, i64) {
    let n = i64::from(TILEMAP_CHUNK_SIZE);
    (cx.div_euclid(n), cy.div_euclid(n))
}

/// Bottom-left world position of cell `(cx, cy)` (Y-up). See module docs.
pub fn tile_cell_origin(
    origin_x: f32,
    origin_y: f32,
    cell_size: [f32; 2],
    cx: i64,
    cy: i64,
) -> [f32; 2] {
    [
        origin_x + cx as f32 * cell_size[0],
        origin_y + cy as f32 * cell_size[1],
    ]
}

/// Chunk key. `Ord` is entity, layer, chunk_x, chunk_y (no HashMap).
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct TilemapChunkKey {
    pub entity_id: u64,
    pub layer: u32,
    pub chunk_x: i64,
    pub chunk_y: i64,
}

/// One occupied cell inside a chunk.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct TilemapChunkCell {
    pub cx: i64,
    pub cy: i64,
    pub tile: i64,
}

/// Occupied cells in one 16×16 region of one layer.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TilemapChunk {
    pub key: TilemapChunkKey,
    pub cells: Vec<TilemapChunkCell>,
}

/// Expand valid RLE runs into 16×16 chunks (BTreeMap order).
///
/// Empty (`len == 0`) and negative `len` runs are skipped. `tile < 0` is
/// skipped (no quad). Does not apply [`TILEMAP_QUAD_CAP`].
pub fn iter_tilemap_chunks(entity_id: u64, tilemap: &Tilemap) -> Vec<TilemapChunk> {
    let mut grouped: BTreeMap<TilemapChunkKey, Vec<TilemapChunkCell>> = BTreeMap::new();
    for (layer_i, layer) in tilemap.layers.iter().enumerate() {
        let layer_id = u32::try_from(layer_i).unwrap_or(u32::MAX);
        for run in &layer.cells {
            if !is_valid_rle_run(*run) {
                continue;
            }
            let [x, y, len, tile] = *run;
            for i in 0..len {
                let cx = x + i;
                let cy = y;
                let (chunk_x, chunk_y) = tilemap_chunk_coord(cx, cy);
                grouped
                    .entry(TilemapChunkKey {
                        entity_id,
                        layer: layer_id,
                        chunk_x,
                        chunk_y,
                    })
                    .or_default()
                    .push(TilemapChunkCell { cx, cy, tile });
            }
        }
    }
    grouped
        .into_iter()
        .map(|(key, mut cells)| {
            cells.sort_by_key(|c| (c.cy, c.cx));
            TilemapChunk { key, cells }
        })
        .collect()
}

/// Append one solid quad per occupied cell. Returns `true` if the cap fired.
///
/// When `tilemap.tileset` is in `texture_ids`, each cell uses that texture and
/// white tint; otherwise the flat [`TILE_QUAD_COLOR`] quad is kept.
pub fn append_tilemap_render_items(
    entity: &Entity,
    items: &mut Vec<RenderItem>,
    emitted: &mut usize,
    texture_ids: &BTreeMap<String, u32>,
) -> bool {
    if entity.extra.visibility.as_ref().is_some_and(|v| !v.visible) {
        return false;
    }
    let Some(tilemap) = entity.extra.tilemap.as_ref() else {
        return false;
    };
    if !cell_size_ok(tilemap.cell_size) {
        return false;
    }
    let transform = entity
        .transform
        .clone()
        .unwrap_or_else(Transform2D::identity);
    let (color, texture) = match texture_ids.get(&tilemap.tileset.id) {
        Some(&v) => ([1.0, 1.0, 1.0, 1.0], Some(TextureId(v))),
        None => (TILE_QUAD_COLOR, None),
    };
    let mut overflow = false;
    for chunk in iter_tilemap_chunks(entity.id, tilemap) {
        for cell in chunk.cells {
            if *emitted >= TILEMAP_QUAD_CAP {
                overflow = true;
                break;
            }
            let [x, y] = tile_cell_origin(
                transform.x,
                transform.y,
                tilemap.cell_size,
                cell.cx,
                cell.cy,
            );
            items.push(RenderItem {
                entity_id: entity.id,
                z_index: transform.z_index,
                x,
                y,
                w: tilemap.cell_size[0],
                h: tilemap.cell_size[1],
                color,
                texture,
                pivot: [0.0, 0.0],
                flip_x: false,
                flip_y: false,
            });
            *emitted += 1;
        }
        if overflow {
            break;
        }
    }
    overflow
}

pub(crate) fn is_valid_rle_run(run: [i64; 4]) -> bool {
    let [_x, _y, len, tile] = run;
    len > 0 && tile >= 0
}

pub(crate) fn cell_size_ok(cell_size: [f32; 2]) -> bool {
    cell_size[0].is_finite() && cell_size[1].is_finite() && cell_size[0] > 0.0 && cell_size[1] > 0.0
}

pub(crate) fn tilemap_has_solid_bake(entity: &Entity) -> bool {
    let Some(tilemap) = entity.extra.tilemap.as_ref() else {
        return false;
    };
    if !cell_size_ok(tilemap.cell_size) {
        return false;
    }
    tilemap
        .layers
        .iter()
        .any(|layer| layer.solid && layer.cells.iter().copied().any(is_valid_rle_run))
}

/// One static box for a solid RLE run, in the tilemap body's local space.
#[derive(Clone, Copy, Debug, PartialEq)]
pub(crate) struct TilemapBakeRun {
    pub half_w: f32,
    pub half_h: f32,
    pub offset_x: f32,
    pub offset_y: f32,
}

pub(crate) fn tilemap_bake_runs(entity: &Entity) -> Vec<TilemapBakeRun> {
    let Some(tilemap) = entity.extra.tilemap.as_ref() else {
        return Vec::new();
    };
    if !cell_size_ok(tilemap.cell_size) {
        return Vec::new();
    }
    let cell_w = tilemap.cell_size[0];
    let cell_h = tilemap.cell_size[1];
    let mut runs = Vec::new();
    for layer in &tilemap.layers {
        if !layer.solid {
            continue;
        }
        for run in &layer.cells {
            if !is_valid_rle_run(*run) {
                continue;
            }
            let [cx, cy, len, _tile] = *run;
            let w = len as f32 * cell_w;
            let h = cell_h;
            if !w.is_finite() || !h.is_finite() || w <= 0.0 || h <= 0.0 {
                continue;
            }
            runs.push(TilemapBakeRun {
                half_w: w * 0.5,
                half_h: h * 0.5,
                offset_x: cx as f32 * cell_w + w * 0.5,
                offset_y: cy as f32 * cell_h + h * 0.5,
            });
        }
    }
    runs
}

pub(crate) fn tilemap_bake_fingerprint(entity: &Entity) -> u64 {
    let mut h = 0xcbf2_9ce4_8422_2325;
    if let Some(t) = &entity.transform {
        h = mix_f32(h, t.x);
        h = mix_f32(h, t.y);
        h = mix_f32(h, t.rot);
        h = mix_f32(h, t.sx);
        h = mix_f32(h, t.sy);
        h = mix(h, t.z_index as u64);
    }
    let Some(tilemap) = entity.extra.tilemap.as_ref() else {
        return h;
    };
    h = mix_f32(h, tilemap.cell_size[0]);
    h = mix_f32(h, tilemap.cell_size[1]);
    for (i, layer) in tilemap.layers.iter().enumerate() {
        h = mix(h, i as u64);
        h = mix(h, u64::from(layer.solid));
        h = mix(h, layer.cells.len() as u64);
        for run in &layer.cells {
            h = mix(h, run[0] as u64);
            h = mix(h, run[1] as u64);
            h = mix(h, run[2] as u64);
            h = mix(h, run[3] as u64);
        }
    }
    h
}

fn mix(h: u64, v: u64) -> u64 {
    h ^ v.wrapping_mul(0x9E37_79B9_7F4A_7C15)
}

fn mix_f32(h: u64, v: f32) -> u64 {
    mix(h, u64::from(v.to_bits()))
}

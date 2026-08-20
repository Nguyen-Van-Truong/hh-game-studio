use std::collections::BTreeMap;

use gs_render2d::{sort_items, Camera2D, RenderItem, RenderSnapshot, TextureId};
use gs_scene::{format_entity_id, Entity, Transform2D};

use crate::error::Error;
use crate::tilemap::append_tilemap_render_items;
use crate::world::World;

/// Active cameras: 0 → error; 2+ → smallest entity id + GS-EC-29 warning.
pub fn select_active_camera(world: &mut World) -> Result<(u64, Camera2D), Error> {
    let mut active: Vec<(u64, f32, [f32; 2])> = Vec::new();
    for (id, entity) in &world.entities {
        let Some(cam) = entity.extra.camera.as_ref() else {
            continue;
        };
        if !cam.active {
            continue;
        }
        let t = entity
            .transform
            .clone()
            .unwrap_or_else(Transform2D::identity);
        active.push((*id, cam.ortho_height, [t.x, t.y]));
    }
    if active.is_empty() {
        return Err(Error::NoActiveCamera);
    }
    // BTreeMap walk is already id-ascending; first entry is the smallest id.
    let (id, ortho_height, position) = active[0];
    if active.len() > 1 {
        let msg = format!(
            "GS-EC-29: {} active cameras; using entity {}",
            active.len(),
            format_entity_id(id)
        );
        if !world.warnings.iter().any(|w| w.starts_with("GS-EC-29")) {
            world.warnings.push(msg);
        }
    }
    Ok((
        id,
        Camera2D {
            ortho_height,
            position,
        },
    ))
}

/// Project Transform2D + Sprite (or a solid quad) into the render IR.
/// Y-up, pivot bottom-left default, size in world units (PPU 16).
///
/// Tilemap-only entities are skipped here; [`build_render_snapshot`] expands
/// occupied cells into quads (one [`RenderItem`] per cell).
///
/// This shim does not resolve textures (`texture: None`). Prefer
/// [`entity_to_render_item_with`] when a `World.texture_ids` map is available.
pub fn entity_to_render_item(entity: &Entity) -> Option<RenderItem> {
    entity_to_render_item_with(entity, &BTreeMap::new())
}

/// Like [`entity_to_render_item`], but maps `Sprite.asset.id` through `texture_ids`.
/// Unknown asset id → `texture: None` (solid quad).
pub fn entity_to_render_item_with(
    entity: &Entity,
    texture_ids: &BTreeMap<String, u32>,
) -> Option<RenderItem> {
    if entity.extra.visibility.as_ref().is_some_and(|v| !v.visible) {
        return None;
    }
    if entity.extra.camera.is_some() && entity.extra.sprite.is_none() {
        return None;
    }
    if entity.extra.tilemap.is_some() && entity.extra.sprite.is_none() {
        return None;
    }
    let transform = entity
        .transform
        .clone()
        .unwrap_or_else(Transform2D::identity);
    let (color, pivot, flip_x, flip_y, texture) = match &entity.extra.sprite {
        Some(sprite) => {
            let texture = texture_ids.get(&sprite.asset.id).copied().map(TextureId);
            (
                sprite.color,
                sprite.pivot,
                sprite.flip_x,
                sprite.flip_y,
                texture,
            )
        }
        None => ([0.72, 0.76, 0.84, 1.0], [0.0, 0.0], false, false, None),
    };
    let w = transform.sx.abs().max(0.001);
    let h = transform.sy.abs().max(0.001);
    Some(RenderItem {
        entity_id: entity.id,
        z_index: transform.z_index,
        x: transform.x,
        y: transform.y,
        w,
        h,
        color,
        texture,
        pivot,
        flip_x,
        flip_y,
    })
}

pub fn build_render_snapshot(world: &mut World) -> Result<RenderSnapshot, Error> {
    world.apply_camera_follow();
    let (_id, mut camera) = select_active_camera(world)?;
    camera.position[0] += world.camera_shake_offset[0];
    camera.position[1] += world.camera_shake_offset[1];
    let mut items = Vec::new();
    let mut tile_emitted = 0usize;
    let mut tile_overflow = false;
    for entity in world.entities.values() {
        if let Some(item) = entity_to_render_item_with(entity, &world.texture_ids) {
            items.push(item);
        }
        tile_overflow |=
            append_tilemap_render_items(entity, &mut items, &mut tile_emitted, &world.texture_ids);
    }
    if tile_overflow
        && !world
            .warnings
            .iter()
            .any(|w| w.contains("tilemap quad cap"))
    {
        world.warnings.push(format!(
            "tilemap quad cap {cap} exceeded; extra cells dropped",
            cap = crate::TILEMAP_QUAD_CAP
        ));
    }
    sort_items(&mut items);
    Ok(RenderSnapshot { camera, items })
}

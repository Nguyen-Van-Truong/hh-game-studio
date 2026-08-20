//! Document → [`gs_render2d::RenderSnapshot`] (production viewport path).

use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

use gs_render2d::{RenderItem, RenderSnapshot};
use gs_scene::{parse_entity_id, ColliderShape, Document, Entity};
use serde_json::Value;

use crate::view_state::ViewState;

/// Max occupied tile cells drawn in one viewport snapshot.
pub const TILEMAP_VIEW_QUAD_CAP: usize = 2048;

/// Distinct earth tone for editor tile quads (not the default gray body).
pub const TILE_QUAD_COLOR: [f32; 4] = [0.58, 0.40, 0.24, 1.0];

/// Toolbar / chrome fields copied off the in-process editor (read-only).
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct ProjectChrome {
    pub open: bool,
    pub name: Option<String>,
    pub scene_id: Option<String>,
    pub revision: Option<String>,
    pub entity_count: usize,
    pub wal_seq: u64,
    /// `off` / `ok` / `error` — toolbar banner when not `ok` (MASTER 7.3).
    pub type_check: String,
}

/// Demo IR (smiley/blocks) only when no project session is open.
pub fn use_demo_ir(chrome: &ProjectChrome) -> bool {
    !chrome.open
}

/// Occupied Tilemap RLE copied onto a viewport entity for expansion.
#[derive(Clone, Debug, PartialEq)]
pub struct ViewportTilemap {
    pub cell_size: [f32; 2],
    pub runs: Vec<[i64; 4]>,
}

/// One document entity projected for the viewport (sprites + overlays).
#[derive(Clone, Debug, PartialEq)]
pub struct ViewportEntity {
    pub id: u64,
    pub name: String,
    pub x: f32,
    pub y: f32,
    pub rot: f32,
    pub sx: f32,
    pub sy: f32,
    pub z_index: i32,
    pub color: [f32; 4],
    pub pivot: [f32; 2],
    pub has_sprite: bool,
    pub has_camera: bool,
    pub tilemap: Option<ViewportTilemap>,
    pub collider: Option<ColliderOverlay>,
    pub script_badge: bool,
    pub visible: bool,
}

#[derive(Clone, Debug, PartialEq)]
pub enum ColliderOverlay {
    Box {
        w: f32,
        h: f32,
        offset: [f32; 2],
    },
    Circle {
        r: f32,
        offset: [f32; 2],
    },
    Capsule {
        half_h: f32,
        r: f32,
        offset: [f32; 2],
    },
}

pub fn collect_viewport_entities(doc: &Document) -> Vec<ViewportEntity> {
    let root = doc.project_root.as_deref();
    doc.scene
        .entities
        .values()
        .map(|entity| project_entity(entity, root))
        .collect()
}

/// Occupied Tilemap cells as extra viewport quads (earth tone, cap 2048).
pub fn collect_tilemap_viewport_quads(doc: &Document) -> Vec<ViewportEntity> {
    let mut out = Vec::new();
    for entity in collect_viewport_entities(doc) {
        append_entity_tile_quads(&entity, &mut out);
    }
    out
}

pub fn entities_to_snapshot(entities: &[ViewportEntity], view: &ViewState) -> RenderSnapshot {
    let mut items = Vec::new();
    let mut tile_quads = Vec::new();
    for entity in entities {
        if let Some(item) = entity_to_render_item(entity) {
            items.push(item);
        }
        append_entity_tile_quads(entity, &mut tile_quads);
    }
    for quad in &tile_quads {
        if let Some(item) = entity_to_render_item(quad) {
            items.push(item);
        }
    }
    RenderSnapshot {
        camera: view.camera(),
        items,
    }
}

/// Production conversion: Transform2D + Sprite color/pivot; missing sprite → solid quad.
pub fn document_to_snapshot(doc: &Document, view: &ViewState) -> RenderSnapshot {
    entities_to_snapshot(&collect_viewport_entities(doc), view)
}

#[derive(Clone, Copy, Debug)]
struct LivePose {
    id: u64,
    x: f32,
    y: f32,
    rot: f32,
    sx: f32,
    sy: f32,
    z_index: i32,
    has_sprite: bool,
    has_camera: bool,
}

/// Overlay a play `obs.world_dump` / live-view JSON onto document viewport entities.
/// Updates poses, hides destroyed sprites, and adds runtime-only quads (`rt_*`).
pub fn apply_live_dump(entities: &mut Vec<ViewportEntity>, dump: &Value) {
    let Some(arr) = dump.get("entities").and_then(Value::as_array) else {
        return;
    };
    let mut live = BTreeMap::new();
    for item in arr {
        if let Some(pose) = live_pose_from_dump(item) {
            live.insert(pose.id, pose);
        }
    }
    let live_ids: BTreeSet<u64> = live.keys().copied().collect();
    for entity in entities.iter_mut() {
        if let Some(pose) = live.get(&entity.id) {
            entity.x = pose.x;
            entity.y = pose.y;
            entity.rot = pose.rot;
            entity.sx = pose.sx;
            entity.sy = pose.sy;
            entity.z_index = pose.z_index;
            entity.visible = true;
        } else if entity.has_sprite && !live_ids.is_empty() {
            entity.visible = false;
        }
    }
    for pose in live.values() {
        if entities.iter().any(|e| e.id == pose.id) {
            continue;
        }
        entities.push(runtime_live_quad(*pose));
    }
}

fn parse_dump_id(id: &str) -> Option<u64> {
    if let Ok(n) = parse_entity_id(id) {
        return Some(n);
    }
    let rest = id.strip_prefix("rt_")?;
    if rest.is_empty() || !rest.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    let seq: u64 = rest.parse().ok()?;
    if seq == 0 {
        return None;
    }
    (1u64 << 40).checked_add(seq)
}

fn live_pose_from_dump(item: &Value) -> Option<LivePose> {
    let id = item
        .get("id")
        .and_then(Value::as_str)
        .and_then(parse_dump_id)?;
    let t = item.get("transform")?;
    Some(LivePose {
        id,
        x: t.get("x").and_then(Value::as_f64)? as f32,
        y: t.get("y").and_then(Value::as_f64)? as f32,
        rot: t.get("rot").and_then(Value::as_f64).unwrap_or(0.0) as f32,
        sx: t.get("sx").and_then(Value::as_f64).unwrap_or(1.0) as f32,
        sy: t.get("sy").and_then(Value::as_f64).unwrap_or(1.0) as f32,
        z_index: t.get("z_index").and_then(Value::as_i64).unwrap_or(0) as i32,
        has_sprite: item
            .get("has_sprite")
            .and_then(Value::as_bool)
            .unwrap_or(false),
        has_camera: item
            .get("has_camera")
            .and_then(Value::as_bool)
            .unwrap_or(false),
    })
}

fn runtime_live_quad(pose: LivePose) -> ViewportEntity {
    ViewportEntity {
        id: pose.id,
        name: format!("rt_{}", pose.id),
        x: pose.x,
        y: pose.y,
        rot: pose.rot,
        sx: pose.sx.abs().max(0.001),
        sy: pose.sy.abs().max(0.001),
        z_index: pose.z_index,
        color: [0.85, 0.85, 0.9, 1.0],
        pivot: [0.5, 0.5],
        has_sprite: pose.has_sprite,
        has_camera: pose.has_camera,
        tilemap: None,
        collider: None,
        script_badge: false,
        visible: !pose.has_camera || pose.has_sprite,
    }
}

pub fn entity_to_render_item(entity: &ViewportEntity) -> Option<RenderItem> {
    if !entity.visible {
        return None;
    }
    // Camera-only: do not draw a body quad (ortho scale must not fill the view).
    if entity.has_camera && !entity.has_sprite {
        return None;
    }
    // Tilemap-only: cells are expanded separately; skip the 1×1 transform quad.
    if entity.tilemap.is_some() && !entity.has_sprite {
        return None;
    }
    let w = entity.sx.abs().max(0.001);
    let h = entity.sy.abs().max(0.001);
    Some(RenderItem {
        entity_id: entity.id,
        z_index: entity.z_index,
        x: entity.x,
        y: entity.y,
        w,
        h,
        color: entity.color,
        texture: None,
        pivot: entity.pivot,
        flip_x: false,
        flip_y: false,
    })
}

/// Expand occupied RLE cells into viewport quads. Cell origin is bottom-left at
/// `origin + (cx * cw, cy * ch)` (Y-up). `cap` is the maximum number of quads.
pub fn expand_tilemap_quads(
    entity_id: u64,
    origin: [f32; 2],
    z_index: i32,
    cell_size: [f32; 2],
    runs: &[[i64; 4]],
    cap: usize,
) -> Vec<ViewportEntity> {
    let mut out = Vec::new();
    if !cell_size_ok(cell_size) || cap == 0 {
        return out;
    }
    for run in runs {
        let [x0, cy, len, tile] = *run;
        if len <= 0 || tile < 0 {
            continue;
        }
        for i in 0..len {
            if out.len() >= cap {
                return out;
            }
            let cx = x0 + i;
            let x = origin[0] + cx as f32 * cell_size[0];
            let y = origin[1] + cy as f32 * cell_size[1];
            out.push(tile_cell_entity(entity_id, x, y, z_index, cell_size));
        }
    }
    out
}

fn append_entity_tile_quads(entity: &ViewportEntity, out: &mut Vec<ViewportEntity>) {
    if !entity.visible {
        return;
    }
    let Some(tilemap) = entity.tilemap.as_ref() else {
        return;
    };
    let remaining = TILEMAP_VIEW_QUAD_CAP.saturating_sub(out.len());
    if remaining == 0 {
        return;
    }
    out.extend(expand_tilemap_quads(
        entity.id,
        [entity.x, entity.y],
        entity.z_index,
        tilemap.cell_size,
        &tilemap.runs,
        remaining,
    ));
}

fn tile_cell_entity(
    entity_id: u64,
    x: f32,
    y: f32,
    z_index: i32,
    cell_size: [f32; 2],
) -> ViewportEntity {
    ViewportEntity {
        id: entity_id,
        name: String::new(),
        x,
        y,
        rot: 0.0,
        sx: cell_size[0],
        sy: cell_size[1],
        z_index,
        color: TILE_QUAD_COLOR,
        pivot: [0.0, 0.0],
        has_sprite: false,
        has_camera: false,
        tilemap: None,
        collider: None,
        script_badge: false,
        visible: true,
    }
}

fn cell_size_ok(cell_size: [f32; 2]) -> bool {
    cell_size[0].is_finite() && cell_size[1].is_finite() && cell_size[0] > 0.0 && cell_size[1] > 0.0
}

fn project_entity(entity: &Entity, root: Option<&Path>) -> ViewportEntity {
    let transform = entity
        .transform
        .clone()
        .unwrap_or_else(gs_scene::Transform2D::identity);
    let (color, pivot, has_sprite) = match &entity.extra.sprite {
        Some(sprite) => (sprite.color, sprite.pivot, true),
        None => ([0.72, 0.76, 0.84, 1.0], [0.0, 0.0], false),
    };
    let visible = entity
        .extra
        .visibility
        .as_ref()
        .map(|v| v.visible)
        .unwrap_or(true);
    let name = entity
        .name
        .as_ref()
        .map(|n| n.value.clone())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| entity.id_str());
    let tilemap = entity.extra.tilemap.as_ref().map(|tm| ViewportTilemap {
        cell_size: tm.cell_size,
        runs: tm
            .layers
            .iter()
            .flat_map(|layer| layer.cells.iter().copied())
            .collect(),
    });
    ViewportEntity {
        id: entity.id,
        name,
        x: transform.x,
        y: transform.y,
        rot: transform.rot,
        sx: transform.sx,
        sy: transform.sy,
        z_index: transform.z_index,
        color,
        pivot,
        has_sprite,
        has_camera: entity.extra.camera.is_some(),
        tilemap,
        collider: entity.extra.collider.as_ref().map(|c| match c.shape {
            ColliderShape::Box { w, h } => ColliderOverlay::Box {
                w,
                h,
                offset: c.offset,
            },
            ColliderShape::Circle { r } => ColliderOverlay::Circle {
                r,
                offset: c.offset,
            },
            ColliderShape::Capsule { half_h, r } => ColliderOverlay::Capsule {
                half_h,
                r,
                offset: c.offset,
            },
        }),
        script_badge: script_error_placeholder(entity, root),
        visible,
    }
}

/// Placeholder until M3 Luau: badge if Script exists and the file is empty or missing.
fn script_error_placeholder(entity: &Entity, root: Option<&Path>) -> bool {
    let Some(script) = &entity.extra.script else {
        return false;
    };
    if script.file.trim().is_empty() {
        return true;
    }
    let Some(root) = root else {
        return false;
    };
    let path = root.join(&script.file);
    match std::fs::metadata(&path) {
        Ok(meta) => meta.len() == 0,
        Err(_) => true,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeMap;

    use gs_scene::{Command, DispatchRequest, Session, DEFAULT_SCENE_ID};
    use serde_json::json;
    use tempfile::TempDir;
    use ulid::Ulid;

    fn expand_row(len: i64) -> Vec<ViewportEntity> {
        expand_tilemap_quads(7, [0.0, 0.0], 0, [1.0, 1.0], &[[0, 0, len, 1]], 2048)
    }

    fn spawn_tilemap_doc(cells: serde_json::Value) -> (TempDir, Document) {
        let dir = TempDir::new().expect("tempdir");
        let mut session = Session::open(dir.path()).expect("open");
        let mut comps = BTreeMap::new();
        comps.insert(
            "Tilemap".into(),
            json!({
                "tileset": { "$asset": "a_000001" },
                "cell_size": [1.0, 1.0],
                "layers": [{ "name": "ground", "solid": true, "cells": cells }]
            }),
        );
        session
            .dispatch(DispatchRequest::new(
                Ulid::new().to_string(),
                "act_01",
                Command::entity_spawn(DEFAULT_SCENE_ID, Some("floor".into()), None, comps),
            ))
            .expect("spawn");
        let doc = session.document().clone();
        (dir, doc)
    }

    #[test]
    fn expand_tilemap_quads_emits_eleven_cells_for_rle_row() {
        let quads = expand_row(11);
        assert_eq!(quads.len(), 11);
        for (i, quad) in quads.iter().enumerate() {
            assert_eq!(quad.id, 7);
            assert!((quad.x - i as f32).abs() < f32::EPSILON);
            assert!((quad.y - 0.0).abs() < f32::EPSILON);
            assert!((quad.sx - 1.0).abs() < f32::EPSILON);
            assert!((quad.sy - 1.0).abs() < f32::EPSILON);
            assert_eq!(quad.color, TILE_QUAD_COLOR);
            assert_eq!(quad.pivot, [0.0, 0.0]);
        }
    }

    #[test]
    fn expand_tilemap_quads_uses_transform_plus_cell_origin() {
        let quads = expand_tilemap_quads(
            1,
            [2.0, 3.0],
            0,
            [1.5, 2.0],
            &[[1, 2, 1, 1]],
            TILEMAP_VIEW_QUAD_CAP,
        );
        assert_eq!(quads.len(), 1);
        assert!((quads[0].x - (2.0 + 1.5)).abs() < f32::EPSILON);
        assert!((quads[0].y - (3.0 + 4.0)).abs() < f32::EPSILON);
        assert!((quads[0].sx - 1.5).abs() < f32::EPSILON);
        assert!((quads[0].sy - 2.0).abs() < f32::EPSILON);
    }

    #[test]
    fn collect_tilemap_viewport_quads_emits_eleven_from_document() {
        let (_dir, doc) = spawn_tilemap_doc(json!([[0, 0, 11, 1]]));
        let entities = collect_viewport_entities(&doc);
        assert_eq!(entities.len(), 1, "one document entity");
        assert!(entities[0].tilemap.is_some());

        let quads = collect_tilemap_viewport_quads(&doc);
        assert_eq!(quads.len(), 11);

        let snap = document_to_snapshot(&doc, &ViewState::default());
        assert_eq!(snap.items.len(), 11);
        assert!((snap.items[0].x - 0.0).abs() < f32::EPSILON);
        assert!((snap.items[10].x - 10.0).abs() < f32::EPSILON);
        assert_eq!(snap.items[0].color, TILE_QUAD_COLOR);
    }

    #[test]
    fn camera_only_entity_is_not_a_body_quad() {
        let entity = ViewportEntity {
            id: 1,
            name: "cam".into(),
            x: 0.0,
            y: 0.0,
            rot: 0.0,
            sx: 12.0,
            sy: 12.0,
            z_index: 0,
            color: [1.0, 1.0, 1.0, 1.0],
            pivot: [0.0, 0.0],
            has_sprite: false,
            has_camera: true,
            tilemap: None,
            collider: None,
            script_badge: false,
            visible: true,
        };
        assert!(entity_to_render_item(&entity).is_none());
    }

    #[test]
    fn use_demo_ir_only_when_no_session() {
        let mut chrome = ProjectChrome {
            open: false,
            entity_count: 0,
            ..ProjectChrome::default()
        };
        assert!(use_demo_ir(&chrome));
        chrome.open = true;
        chrome.entity_count = 0;
        assert!(!use_demo_ir(&chrome));
        chrome.entity_count = 3;
        assert!(!use_demo_ir(&chrome));
    }

    fn sprite_entity(id: u64, x: f32, y: f32) -> ViewportEntity {
        ViewportEntity {
            id,
            name: format!("e_{id:06}"),
            x,
            y,
            rot: 0.0,
            sx: 1.0,
            sy: 1.0,
            z_index: 1,
            color: [0.2, 0.8, 0.3, 1.0],
            pivot: [0.5, 0.5],
            has_sprite: true,
            has_camera: false,
            tilemap: None,
            collider: None,
            script_badge: false,
            visible: true,
        }
    }

    #[test]
    fn apply_live_dump_moves_and_hides_sprites() {
        let mut entities = vec![sprite_entity(10, 5.0, 6.0), sprite_entity(11, 10.0, 8.0)];
        let dump = json!({
            "entities": [
                {
                    "id": "e_000010",
                    "transform": { "x": 7.0, "y": 6.0, "rot": 0.0, "sx": 1.0, "sy": 1.0, "z_index": 3 },
                    "has_sprite": true
                }
            ]
        });
        apply_live_dump(&mut entities, &dump);
        assert!((entities[0].x - 7.0).abs() < f32::EPSILON);
        assert!(entities[0].visible);
        assert!(
            !entities[1].visible,
            "missing sprite must hide (destroyed coin)"
        );
    }

    #[test]
    fn apply_live_dump_adds_runtime_quad() {
        let mut entities = vec![sprite_entity(10, 1.0, 1.0)];
        let dump = json!({
            "entities": [
                {
                    "id": "e_000010",
                    "transform": { "x": 1.0, "y": 1.0, "rot": 0.0, "sx": 1.0, "sy": 1.0, "z_index": 1 },
                    "has_sprite": true
                },
                {
                    "id": "rt_1",
                    "transform": { "x": 3.0, "y": 4.0, "rot": 0.0, "sx": 1.0, "sy": 1.0, "z_index": 2 },
                    "has_sprite": true
                }
            ]
        });
        apply_live_dump(&mut entities, &dump);
        assert_eq!(entities.len(), 2);
        assert!((entities[1].x - 3.0).abs() < f32::EPSILON);
        assert!((entities[1].y - 4.0).abs() < f32::EPSILON);
    }
}

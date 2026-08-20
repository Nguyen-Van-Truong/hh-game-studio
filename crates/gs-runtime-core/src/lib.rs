//! Play-world projection, the fixed 6.2 phase schedule, and the Luau VM host.
//!
//! Rapier lives on caller-owned [`PhysicsHost`] (not [`World`]). No bevy_ecs.
//! Entities live in a `BTreeMap` keyed by numeric id so gameplay iteration is
//! deterministic (MASTER 6.2). Editor crates must not depend on this Luau
//! host (I3).

mod error;
mod phase;
mod physics;
mod render;
mod schedule;
mod script;
mod tilemap;
mod world;

pub use error::Error;
pub use phase::Phase;
pub use physics::{PhysicsHost, RaycastHit};
pub use render::{
    build_render_snapshot, entity_to_render_item, entity_to_render_item_with, select_active_camera,
};
pub use schedule::{step, step_with_host, step_with_hosts, step_with_physics};
pub use script::{
    format_play_id, parse_play_id, run_init, RunReport, ScriptError, ScriptFailure,
    ScriptFrameReport, ScriptHost, ScriptLog, ScriptTimeHook, ScriptVm, DEADLINE_MESSAGE,
    DISABLE_ERROR_COUNT, DISABLE_ERROR_WINDOW, DISABLE_HARD_STREAK, GLOBAL_HARD, GLOBAL_SOFT,
    INIT_BUDGET, MEMORY_LIMIT_BYTES, RUNTIME_ID_BASE, SCRIPT_HARD, SCRIPT_SOFT,
    SPAWN_CAP_PER_FRAME,
};
pub use tilemap::{
    iter_tilemap_chunks, tile_cell_origin, tilemap_chunk_coord, TilemapChunk, TilemapChunkCell,
    TilemapChunkKey, TILEMAP_CHUNK_SIZE, TILEMAP_QUAD_CAP,
};
pub use world::{
    CameraShake, InputFrame, PlayEvent, QueuedScriptEvent, ScriptBinding, SfxRequest, SystemEvent,
    World, FIXED_DT,
};

pub fn crate_name() -> &'static str {
    "gs-runtime-core"
}

#[cfg(test)]
mod tests {
    use std::collections::BTreeMap;

    use gs_render2d::TextureId;
    use gs_scene::{AssetRef, Camera2D, Entity, Name, Scene, Sprite, Transform2D};

    use super::*;

    fn transform_at(x: f32, y: f32) -> Transform2D {
        Transform2D {
            x,
            y,
            rot: 0.0,
            sx: 1.0,
            sy: 1.0,
            z_index: 0,
        }
    }

    fn camera_entity(id: u64, active: bool, ortho: f32, x: f32, y: f32) -> Entity {
        let mut entity = Entity::new(id, None, 0);
        entity.name = Some(Name {
            value: format!("cam{id}"),
        });
        entity.transform = Some(transform_at(x, y));
        entity.extra.camera = Some(Camera2D {
            ortho_height: ortho,
            active,
        });
        entity
    }

    fn sprite_entity(id: u64, x: f32, y: f32) -> Entity {
        let mut entity = Entity::new(id, None, 1);
        entity.name = Some(Name {
            value: format!("sprite{id}"),
        });
        entity.transform = Some(Transform2D {
            x,
            y,
            rot: 0.0,
            sx: 2.0,
            sy: 2.0,
            z_index: 0,
        });
        entity.extra.sprite = Some(Sprite {
            asset: AssetRef {
                id: "a_000001".into(),
            },
            color: [1.0, 0.2, 0.2, 1.0],
            flip_x: false,
            flip_y: false,
            pivot: [0.0, 0.0],
        });
        entity
    }

    fn world_with(entities: Vec<Entity>) -> World {
        let mut scene = Scene::default();
        for entity in entities {
            scene.entities.insert(entity.id, entity);
        }
        World::from_scene(scene, 42)
    }

    #[test]
    fn smoke() {
        assert_eq!(crate_name(), "gs-runtime-core");
        assert!((FIXED_DT - 1.0 / 60.0).abs() < f64::EPSILON);
    }

    #[test]
    fn phase_order_matches_master_6_2() {
        let mut world = world_with(vec![
            camera_entity(1, true, 10.0, 0.0, 0.0),
            sprite_entity(2, 1.0, 2.0),
        ]);
        step(&mut world, &InputFrame::default()).expect("step");
        assert_eq!(
            world.last_phase_names(),
            vec![
                "input",
                "script_on_update",
                "commit_mutations",
                "physics",
                "collisions",
                "timers",
                "emit_trace",
                "build_render_snapshot",
            ]
        );
        assert_eq!(world.script_visit_order, vec![1, 2]);
        assert_eq!(world.events, vec![SystemEvent::FrameAdvanced { frame: 1 }]);
    }

    #[test]
    fn zero_active_cameras_is_error() {
        let mut world = world_with(vec![
            camera_entity(1, false, 10.0, 0.0, 0.0),
            sprite_entity(2, 0.0, 0.0),
        ]);
        let err = step(&mut world, &InputFrame::default()).expect_err("need camera");
        assert!(matches!(err, Error::NoActiveCamera));
    }

    #[test]
    fn two_active_cameras_picks_smallest_id() {
        let mut world = world_with(vec![
            camera_entity(5, true, 8.0, 3.0, 4.0),
            camera_entity(2, true, 12.0, -1.0, 0.5),
            sprite_entity(9, 0.0, 0.0),
        ]);
        let snap = step(&mut world, &InputFrame::default()).expect("step");
        assert!((snap.camera.ortho_height - 12.0).abs() < f32::EPSILON);
        assert_eq!(snap.camera.position, [-1.0, 0.5]);
        assert!(world
            .warnings
            .iter()
            .any(|w| w.contains("GS-EC-29") && w.contains("e_000002")));
    }

    #[test]
    fn render_snapshot_has_sprite_not_camera_quad() {
        let mut world = world_with(vec![
            camera_entity(1, true, 10.0, 0.0, 0.0),
            sprite_entity(2, 1.5, -0.5),
        ]);
        let snap = build_render_snapshot(&mut world).expect("snapshot");
        assert_eq!(snap.items.len(), 1);
        assert_eq!(snap.items[0].entity_id, 2);
        assert_eq!(snap.items[0].x, 1.5);
        assert_eq!(snap.items[0].y, -0.5);
        assert_eq!(snap.items[0].pivot, [0.0, 0.0]);
        assert!((snap.camera.ortho_height - 10.0).abs() < f32::EPSILON);
        assert_eq!(snap.items[0].texture, None);
        assert!(!snap.items[0].flip_x);
        assert!(!snap.items[0].flip_y);
    }

    fn flipped_sprite(id: u64) -> Entity {
        let mut entity = sprite_entity(id, 0.0, 0.0);
        if let Some(sprite) = entity.extra.sprite.as_mut() {
            sprite.flip_x = true;
            sprite.flip_y = true;
        }
        entity
    }

    #[test]
    fn entity_to_render_item_shim_resolves_no_textures() {
        let entity = flipped_sprite(2);
        let item = entity_to_render_item(&entity).expect("item");
        assert_eq!(item.texture, None);
        assert!(item.flip_x);
        assert!(item.flip_y);
    }

    #[test]
    fn entity_to_render_item_with_resolves_texture_and_copies_flips() {
        let entity = flipped_sprite(2);
        let mut ids = BTreeMap::new();
        ids.insert("a_000001".into(), 7);
        let hit = entity_to_render_item_with(&entity, &ids).expect("hit");
        assert_eq!(hit.texture, Some(TextureId(7)));
        assert!(hit.flip_x);
        assert!(hit.flip_y);

        let mut other = BTreeMap::new();
        other.insert("a_000099".into(), 7);
        let miss = entity_to_render_item_with(&entity, &other).expect("miss");
        assert_eq!(miss.texture, None);
        assert!(miss.flip_x);
        assert!(miss.flip_y);
    }

    fn tilemap_entity(id: u64) -> Entity {
        let file = serde_json::json!({
            "schema_version": 1,
            "mode": "2d",
            "entities": [{
                "id": format!("e_{id:06}"),
                "parent": null,
                "order": 0,
                "components": {
                    "Tilemap": {
                        "tileset": { "$asset": "a_000001" },
                        "cell_size": [1.0, 1.0],
                        "layers": [{
                            "name": "ground",
                            "solid": false,
                            "cells": [[0, 0, 1, 1]]
                        }]
                    }
                }
            }]
        });
        let scene = Scene::from_file(serde_json::from_value(file).expect("file")).expect("scene");
        let mut entity = scene.entities.get(&id).cloned().expect("tilemap");
        entity.transform = Some(transform_at(0.0, 0.0));
        entity
    }

    #[test]
    fn tilemap_quads_use_texture_when_tileset_is_mapped() {
        let mut world = world_with(vec![
            camera_entity(1, true, 10.0, 0.0, 0.0),
            tilemap_entity(5),
        ]);
        let flat = build_render_snapshot(&mut world).expect("flat");
        assert_eq!(flat.items.len(), 1);
        assert_eq!(flat.items[0].texture, None);
        assert_eq!(flat.items[0].color, [0.42, 0.56, 0.38, 1.0]);

        world.texture_ids.insert("a_000001".into(), 4);
        let textured = build_render_snapshot(&mut world).expect("textured");
        assert_eq!(textured.items[0].texture, Some(TextureId(4)));
        assert_eq!(textured.items[0].color, [1.0, 1.0, 1.0, 1.0]);
    }

    #[test]
    fn world_texture_ids_default_empty() {
        let world = world_with(vec![camera_entity(1, true, 10.0, 0.0, 0.0)]);
        assert!(world.texture_ids.is_empty());
    }
}

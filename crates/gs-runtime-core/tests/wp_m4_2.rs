use gs_runtime_core::{
    build_render_snapshot, iter_tilemap_chunks, step_with_physics, tile_cell_origin,
    tilemap_chunk_coord, InputFrame, PhysicsHost, World, TILEMAP_CHUNK_SIZE,
};
use gs_scene::{
    Camera2D, Collider2D, ColliderShape, Entity, Name, RigidBody2D, Scene, Tilemap, Transform2D,
};

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

fn camera() -> Entity {
    let mut entity = Entity::new(1, None, 0);
    entity.name = Some(Name {
        value: "cam".into(),
    });
    entity.transform = Some(transform_at(0.0, 0.0));
    entity.extra.camera = Some(Camera2D {
        ortho_height: 20.0,
        active: true,
    });
    entity
}

fn parse_tilemap(cell_size: [f32; 2], solid: bool, cells: &[[i64; 4]]) -> Tilemap {
    let cells_json: Vec<serde_json::Value> = cells
        .iter()
        .map(|c| serde_json::json!([c[0], c[1], c[2], c[3]]))
        .collect();
    let file = serde_json::json!({
        "schema_version": 1,
        "mode": "2d",
        "entities": [{
            "id": "e_000099",
            "parent": null,
            "order": 0,
            "components": {
                "Tilemap": {
                    "tileset": { "$asset": "a_000001" },
                    "cell_size": cell_size,
                    "layers": [{
                        "name": "ground",
                        "solid": solid,
                        "cells": cells_json
                    }]
                }
            }
        }]
    });
    let scene = Scene::from_file(serde_json::from_value(file).expect("file")).expect("scene");
    scene
        .entities
        .get(&99)
        .and_then(|e| e.extra.tilemap.clone())
        .expect("tilemap")
}

fn tilemap_entity(
    id: u64,
    x: f32,
    y: f32,
    cell_size: [f32; 2],
    solid: bool,
    cells: &[[i64; 4]],
) -> Entity {
    let mut entity = Entity::new(id, None, 1);
    entity.transform = Some(transform_at(x, y));
    entity.extra.tilemap = Some(parse_tilemap(cell_size, solid, cells));
    entity
}

fn dynamic_box(id: u64, x: f32, y: f32) -> Entity {
    let mut entity = Entity::new(id, None, 2);
    entity.transform = Some(transform_at(x, y));
    entity.extra.rigid_body = Some(RigidBody2D {
        kind: "dynamic".into(),
        ccd: false,
        gravity_scale: 1.0,
        fixed_rotation: true,
        linear_damping: 0.0,
    });
    entity.extra.collider = Some(Collider2D {
        shape: ColliderShape::Box { w: 1.0, h: 1.0 },
        is_sensor: false,
        offset: [0.0, 0.0],
        layer: 1,
        mask: u32::MAX,
        friction: 0.5,
        restitution: 0.0,
    });
    entity
}

fn world_from(entities: Vec<Entity>) -> World {
    let mut scene = Scene::default();
    for entity in entities {
        scene.entities.insert(entity.id, entity);
    }
    World::from_scene(scene, 1)
}

fn pose_y(world: &World, id: u64) -> f32 {
    world
        .entities
        .get(&id)
        .and_then(|e| e.transform.as_ref())
        .expect("transform")
        .y
}

#[test]
fn solid_row_emits_quads_with_world_y() {
    assert_eq!(TILEMAP_CHUNK_SIZE, 16);
    assert_eq!(tilemap_chunk_coord(16, 16), (1, 1));
    assert_eq!(tilemap_chunk_coord(-1, -1), (-1, -1));

    // 17 cells at cy=1 so the run spans two 16×16 chunks. cell_h=2.
    let origin_x = 2.0;
    let origin_y = 4.0;
    let cell_size = [1.0, 2.0];
    let cells = [[0, 1, 17, 1]];
    let mut world = world_from(vec![
        camera(),
        tilemap_entity(5, origin_x, origin_y, cell_size, true, &cells),
    ]);
    let snap = build_render_snapshot(&mut world).expect("snapshot");
    let tiles: Vec<_> = snap.items.iter().filter(|i| i.entity_id == 5).collect();
    assert_eq!(
        tiles.len(),
        17,
        "one quad per occupied cell, not a transform solid"
    );

    let expect_y = tile_cell_origin(origin_x, origin_y, cell_size, 0, 1)[1];
    assert!((expect_y - 6.0).abs() < f32::EPSILON);
    for (i, item) in tiles.iter().enumerate() {
        let cx = i as i64;
        let [x, y] = tile_cell_origin(origin_x, origin_y, cell_size, cx, 1);
        assert!((item.x - x).abs() < 1e-5, "x[{i}]: {} vs {x}", item.x);
        assert!((item.y - y).abs() < 1e-5, "y[{i}]: {} vs {y}", item.y);
        assert!((item.w - 1.0).abs() < f32::EPSILON);
        assert!((item.h - 2.0).abs() < f32::EPSILON);
        assert_eq!(item.pivot, [0.0, 0.0]);
    }

    let tm = world
        .entities
        .get(&5)
        .and_then(|e| e.extra.tilemap.as_ref())
        .expect("tilemap");
    let chunks = iter_tilemap_chunks(5, tm);
    assert_eq!(chunks.len(), 2);
    assert_eq!(chunks[0].key.chunk_x, 0);
    assert_eq!(chunks[0].key.chunk_y, 0);
    assert_eq!(chunks[0].cells.len(), 16);
    assert_eq!(chunks[1].key.chunk_x, 1);
    assert_eq!(chunks[1].key.chunk_y, 0);
    assert_eq!(chunks[1].cells.len(), 1);
    assert_eq!(chunks[1].cells[0].cx, 16);
}

#[test]
fn dynamic_box_rests_on_solid_tiles() {
    let mut world = world_from(vec![
        camera(),
        tilemap_entity(5, 0.0, 0.0, [1.0, 1.0], true, &[[0, 0, 8, 1]]),
        dynamic_box(3, 2.0, 4.0),
    ]);
    let mut phys = PhysicsHost::new();
    let input = InputFrame::default();
    for _ in 0..60 {
        step_with_physics(&mut world, &input, &mut phys).expect("step");
    }
    let y = pose_y(&world, 3);
    assert!(
        y > 0.4 && y < 4.0,
        "box should rest on tiles, not fall to -100 (y={y})"
    );
    let hit = phys
        .physics_raycast(5.0, 4.0, 5.0, -1.0, None)
        .expect("baked tiles should be hittable");
    assert_eq!(hit.id, 5);
}

#[test]
fn non_solid_layer_does_not_bake() {
    let mut world = world_from(vec![
        camera(),
        tilemap_entity(5, 0.0, 0.0, [1.0, 1.0], false, &[[0, 0, 8, 1]]),
        dynamic_box(3, 2.0, 4.0),
    ]);
    let mut phys = PhysicsHost::new();
    let input = InputFrame::default();
    step_with_physics(&mut world, &input, &mut phys).expect("insert");
    assert!(
        phys.physics_raycast(5.0, 4.0, 5.0, -1.0, None).is_none(),
        "non-solid layer must not bake colliders"
    );
    for _ in 0..60 {
        step_with_physics(&mut world, &input, &mut phys).expect("step");
    }
    let y = pose_y(&world, 3);
    assert!(y < 0.5, "box should fall through non-solid tiles (y={y})");
}

#[test]
fn empty_and_negative_len_runs_are_skipped() {
    // GS-EC-06 rejects these at scene parse; inject so runtime still skips.
    let mut entity = tilemap_entity(5, 0.0, 0.0, [1.0, 1.0], true, &[[3, 0, 2, 1]]);
    if let Some(tm) = entity.extra.tilemap.as_mut() {
        let cells = &mut tm.layers[0].cells;
        cells.insert(0, [0, 0, 0, 1]);
        cells.insert(1, [1, 0, -3, 1]);
        cells.insert(2, [0, 2, 4, -1]);
    }
    let mut world = world_from(vec![camera(), entity, dynamic_box(3, 2.0, 4.0)]);

    let tm = world
        .entities
        .get(&5)
        .and_then(|e| e.extra.tilemap.as_ref())
        .expect("tilemap");
    let chunks = iter_tilemap_chunks(5, tm);
    assert_eq!(chunks.len(), 1);
    assert_eq!(chunks[0].cells.len(), 2);
    assert_eq!(chunks[0].cells[0].cx, 3);
    assert_eq!(chunks[0].cells[1].cx, 4);

    let snap = build_render_snapshot(&mut world).expect("snapshot");
    let tiles: Vec<_> = snap.items.iter().filter(|i| i.entity_id == 5).collect();
    assert_eq!(tiles.len(), 2);
    assert!((tiles[0].x - 3.0).abs() < 1e-5);
    assert!((tiles[1].x - 4.0).abs() < 1e-5);

    let mut phys = PhysicsHost::new();
    step_with_physics(&mut world, &InputFrame::default(), &mut phys).expect("step");
    assert!(
        phys.physics_raycast(0.5, 3.0, 0.5, -1.0, None).is_none(),
        "empty/negative/tile<0 runs must not bake"
    );
    let hit = phys
        .physics_raycast(3.5, 3.0, 3.5, -1.0, None)
        .expect("valid run should bake");
    assert_eq!(hit.id, 5);
}

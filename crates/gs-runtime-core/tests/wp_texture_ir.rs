//! Texture IR + `gs.get_velocity` (stream A1 / scrap-yard contract B).

use std::collections::BTreeMap;

use gs_render2d::TextureId;
use gs_runtime_core::{
    build_render_snapshot, entity_to_render_item, step_with_hosts, InputFrame, PhysicsHost,
    ScriptHost, World,
};
use gs_scene::{
    AssetRef, Camera2D, Collider2D, ColliderShape, Entity, Name, RigidBody2D, Scene, Sprite,
    Transform2D,
};

fn transform_at(x: f32, y: f32, sx: f32, sy: f32) -> Transform2D {
    Transform2D {
        x,
        y,
        rot: 0.0,
        sx,
        sy,
        z_index: 0,
    }
}

fn camera() -> Entity {
    let mut entity = Entity::new(1, None, 0);
    entity.name = Some(Name {
        value: "cam".into(),
    });
    entity.transform = Some(transform_at(0.0, 0.0, 1.0, 1.0));
    entity.extra.camera = Some(Camera2D {
        ortho_height: 10.0,
        active: true,
    });
    entity
}

fn sprite_entity(id: u64, asset: &str, flip_x: bool, flip_y: bool) -> Entity {
    let mut entity = Entity::new(id, None, 1);
    entity.transform = Some(transform_at(id as f32, 0.0, 1.5, 2.0));
    entity.extra.sprite = Some(Sprite {
        asset: AssetRef { id: asset.into() },
        color: [1.0, 0.5, 0.25, 1.0],
        flip_x,
        flip_y,
        pivot: [0.5, 0.0],
    });
    entity
}

fn rigid(id: u64, x: f32, y: f32) -> Entity {
    let mut entity = Entity::new(id, None, 1);
    entity.transform = Some(transform_at(x, y, 1.0, 1.0));
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

#[test]
fn texture_ids_resolve_known_sprite_unknown_stays_none() {
    let mut world = world_from(vec![
        camera(),
        sprite_entity(2, "a_000020", true, false),
        sprite_entity(3, "a_000099", false, true),
    ]);
    world.texture_ids = BTreeMap::from([("a_000020".into(), 7)]);

    let mapped = world.entities.get(&2).expect("sprite 2");
    let shim = entity_to_render_item(mapped).expect("shim");
    assert_eq!(shim.texture, None, "single-arg shim must not resolve ids");
    assert!(shim.flip_x);
    assert!(!shim.flip_y);

    let snap = build_render_snapshot(&mut world).expect("snapshot");
    let known = snap
        .items
        .iter()
        .find(|i| i.entity_id == 2)
        .expect("known sprite");
    assert_eq!(known.texture, Some(TextureId(7)));
    assert!(known.flip_x);
    assert!(!known.flip_y);
    assert_eq!(known.color, [1.0, 0.5, 0.25, 1.0]);

    let unknown = snap
        .items
        .iter()
        .find(|i| i.entity_id == 3)
        .expect("unknown sprite");
    assert_eq!(unknown.texture, None);
    assert!(!unknown.flip_x);
    assert!(unknown.flip_y);
}

#[test]
fn gs_get_velocity_falling_body_and_nil_for_destroyed_id() {
    let source = r#"
        return {
          on_update = function(self)
            local vx, vy = gs.get_velocity(self.id)
            if vy ~= nil then
              gs.emit("vel", { vx = vx, vy = vy })
            end
            if gs.exists("e_000003") then
              gs.destroy("e_000003")
              local dx, dy = gs.get_velocity("e_000003")
              gs.emit("dead", { ok = (dx == nil and dy == nil) })
            end
            local mx, my = gs.get_velocity("e_000999")
            gs.emit("missing", { ok = (mx == nil and my == nil) })
          end
        }
    "#;
    let mut world = world_from(vec![camera(), rigid(2, 0.0, 8.0), rigid(3, 3.0, 8.0)]);
    world.attach_script(2, source);
    let mut host = ScriptHost::new().expect("host");
    let mut phys = PhysicsHost::new();
    let input = InputFrame::default();
    for _ in 0..8 {
        step_with_hosts(&mut world, &input, &mut host, &mut phys).expect("step");
    }
    assert!(
        world.script_errors.is_empty(),
        "get_velocity must not error: {:?}",
        world.script_errors
    );

    let vys: Vec<f64> = world
        .play_events
        .iter()
        .filter(|e| e.name == "vel")
        .filter_map(|e| e.data.get("vy").and_then(|v| v.as_f64()))
        .collect();
    assert!(
        vys.iter().any(|vy| *vy < 0.0),
        "falling body should report negative vy, got {vys:?}"
    );
    assert!(
        world
            .play_events
            .iter()
            .any(|e| e.name == "dead" && e.data.get("ok") == Some(&serde_json::Value::Bool(true))),
        "destroyed id must yield nil, nil: {:?}",
        world.play_events
    );
    assert!(
        world.play_events.iter().any(
            |e| e.name == "missing" && e.data.get("ok") == Some(&serde_json::Value::Bool(true))
        ),
        "missing id must yield nil, nil: {:?}",
        world.play_events
    );
    assert!(!world.entities.contains_key(&3));
}

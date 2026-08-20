use gs_runtime_core::{step, step_with_hosts, InputFrame, PhysicsHost, ScriptHost, World};
use gs_scene::{
    AssetRef, Camera2D, Collider2D, ColliderShape, Entity, Name, RigidBody2D, Scene, Sprite,
    Transform2D,
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
        ortho_height: 10.0,
        active: true,
    });
    entity
}

fn sprite_body(id: u64) -> Entity {
    let mut entity = Entity::new(id, None, 1);
    entity.transform = Some(transform_at(0.0, 0.0));
    entity.extra.sprite = Some(Sprite {
        asset: AssetRef {
            id: "a_000020".into(),
        },
        color: [1.0, 1.0, 1.0, 1.0],
        flip_x: false,
        flip_y: false,
        pivot: [0.5, 0.0],
    });
    entity
}

fn rigid(id: u64, x: f32, y: f32) -> Entity {
    let mut entity = Entity::new(id, None, 1);
    entity.transform = Some(transform_at(x, y));
    entity.extra.rigid_body = Some(RigidBody2D {
        kind: "dynamic".into(),
        ccd: false,
        gravity_scale: 0.0,
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

fn sprite_flips(world: &World, id: u64) -> (bool, bool) {
    let sprite = world
        .entities
        .get(&id)
        .and_then(|e| e.extra.sprite.as_ref())
        .expect("sprite");
    (sprite.flip_x, sprite.flip_y)
}

#[test]
fn gs_set_flip_commits_and_optional_flip_y_leaves_unchanged() {
    let mut world = world_from(vec![camera(), sprite_body(2)]);
    world.attach_script(
        2,
        r#"
            return {
              on_update = function(self)
                gs.set_flip(self.id, true)
                gs.set_flip("e_000999", true, true)
                local mid = gs.get_component(self.id, "Sprite")
                gs.emit("mid_flip", { flip_x = mid.flip_x, flip_y = mid.flip_y })
                gs.set_flip(self.id, false, true)
              end
            }
        "#,
    );
    let mut host = ScriptHost::new().expect("host");
    host.step(&mut world, &InputFrame::default()).expect("step");
    let mid = world
        .play_events
        .iter()
        .find(|e| e.name == "mid_flip")
        .expect("mid_flip");
    assert_eq!(mid.data["flip_x"], true);
    assert_eq!(mid.data["flip_y"], false);
    assert_eq!(sprite_flips(&world, 2), (false, true));
    assert!(world.script_errors.is_empty());
}

#[test]
fn gs_set_flip_discards_on_error() {
    let mut world = world_from(vec![camera(), sprite_body(2)]);
    world.attach_script(
        2,
        r#"
            gs.set_flip("e_000002", true, true)
            error("boom")
        "#,
    );
    step(&mut world, &InputFrame::default()).expect("step");
    assert_eq!(sprite_flips(&world, 2), (false, false));
}

#[test]
fn gs_set_component_sprite_accepts_flips() {
    let mut world = world_from(vec![camera(), sprite_body(2)]);
    world.attach_script(
        2,
        r#"
            return {
              on_update = function(self)
                gs.set_component(self.id, "Sprite", {
                  asset = { ["$asset"] = "a_000021" },
                  flip_x = true,
                  flip_y = true,
                })
              end
            }
        "#,
    );
    let mut host = ScriptHost::new().expect("host");
    host.step(&mut world, &InputFrame::default()).expect("step");
    let sprite = world
        .entities
        .get(&2)
        .and_then(|e| e.extra.sprite.as_ref())
        .expect("sprite");
    assert_eq!(sprite.asset.id, "a_000021");
    assert!(sprite.flip_x);
    assert!(sprite.flip_y);
}

#[test]
fn gs_get_velocity_reads_last_frame_or_nil() {
    let mut world = world_from(vec![camera(), rigid(2, 0.0, 4.0)]);
    world.attach_script(
        2,
        r#"
            return {
              on_update = function(self)
                local vx, vy = gs.get_velocity(self.id)
                local dx, dy = gs.get_velocity("e_000999")
                gs.emit("vel", {
                  vx = vx,
                  vy = vy,
                  dead_nil = dx == nil and dy == nil,
                })
              end
            }
        "#,
    );
    let mut host = ScriptHost::new().expect("host");
    let mut phys = PhysicsHost::new();
    let input = InputFrame::default();
    step_with_hosts(&mut world, &input, &mut host, &mut phys).expect("insert");
    phys.set_linear_velocity(2, 3.0, -1.5);
    world.play_events.clear();
    step_with_hosts(&mut world, &input, &mut host, &mut phys).expect("query");
    let ev = world
        .play_events
        .iter()
        .rev()
        .find(|e| e.name == "vel")
        .expect("vel emit");
    assert_eq!(ev.data["dead_nil"], true);
    let vx = ev.data["vx"].as_f64().expect("vx");
    let vy = ev.data["vy"].as_f64().expect("vy");
    assert!((vx - 3.0).abs() < 0.05, "vx={vx}");
    assert!((vy + 1.5).abs() < 0.05, "vy={vy}");
}

#[test]
fn gs_get_velocity_nil_without_physics_host() {
    let mut world = world_from(vec![camera(), sprite_body(2)]);
    world.attach_script(
        2,
        r#"
            return {
              on_update = function(self)
                local vx, vy = gs.get_velocity(self.id)
                if vx ~= nil or vy ~= nil then
                  error("expected nil,nil without PhysicsHost")
                end
              end
            }
        "#,
    );
    let mut host = ScriptHost::new().expect("host");
    host.step(&mut world, &InputFrame::default()).expect("step");
    assert!(world.script_errors.is_empty());
}

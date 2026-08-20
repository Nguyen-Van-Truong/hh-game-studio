use gs_runtime_core::{
    step, step_with_hosts, InputFrame, PhysicsHost, ScriptHost, World, RUNTIME_ID_BASE,
};
use gs_scene::{
    Camera2D, Collider2D, ColliderShape, Entity, Name, RigidBody2D, Scene, Tags, Transform2D,
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

fn rigid(id: u64, x: f32, y: f32, kind: &str, shape: ColliderShape, sensor: bool) -> Entity {
    let mut entity = Entity::new(id, None, 1);
    entity.transform = Some(transform_at(x, y));
    entity.extra.rigid_body = Some(RigidBody2D {
        kind: kind.into(),
        ccd: false,
        gravity_scale: 1.0,
        fixed_rotation: true,
        linear_damping: 0.0,
    });
    entity.extra.collider = Some(Collider2D {
        shape,
        is_sensor: sensor,
        offset: [0.0, 0.0],
        layer: 1,
        mask: u32::MAX,
        friction: 0.5,
        restitution: 0.0,
    });
    entity
}

fn tagged(id: u64, x: f32, y: f32, tags: &[&str]) -> Entity {
    let mut entity = Entity::new(id, None, 1);
    entity.transform = Some(transform_at(x, y));
    entity.tags = Some(Tags {
        values: tags.iter().map(|t| (*t).to_string()).collect(),
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
        .map(|t| t.y)
        .expect("transform")
}

fn emit_ids(world: &World, name: &str) -> Vec<Vec<String>> {
    world
        .play_events
        .iter()
        .filter(|e| e.name == name)
        .map(|e| {
            e.data["ids"]
                .as_array()
                .unwrap_or(&Vec::new())
                .iter()
                .filter_map(|v| v.as_str().map(str::to_string))
                .collect()
        })
        .collect()
}

#[test]
fn gs_impulse_raises_dynamic_against_gravity() {
    let source = r#"
        return {
          on_init = function(self)
            gs.impulse(self.id, 0, 40)
            gs.impulse("e_000999", 0, 40)
            gs.velocity("nope", 1, 1)
          end
        }
    "#;
    let mut jumped = world_from(vec![
        camera(),
        rigid(
            2,
            0.0,
            5.0,
            "dynamic",
            ColliderShape::Box { w: 1.0, h: 1.0 },
            false,
        ),
    ]);
    jumped.attach_script(2, source);
    let mut host = ScriptHost::new().expect("host");
    let mut phys = PhysicsHost::new();
    step_with_hosts(&mut jumped, &InputFrame::default(), &mut host, &mut phys).expect("jump");

    let mut control = world_from(vec![
        camera(),
        rigid(
            2,
            0.0,
            5.0,
            "dynamic",
            ColliderShape::Box { w: 1.0, h: 1.0 },
            false,
        ),
    ]);
    let mut host2 = ScriptHost::new().expect("host");
    let mut phys2 = PhysicsHost::new();
    step_with_hosts(&mut control, &InputFrame::default(), &mut host2, &mut phys2).expect("control");

    let jumped_y = pose_y(&jumped, 2);
    let control_y = pose_y(&control, 2);
    assert!(
        jumped_y > control_y,
        "impulse should raise y vs gravity-only: jumped={jumped_y} control={control_y}"
    );
    assert!(
        jumped_y > 5.0,
        "impulse should increase y against gravity, got {jumped_y}"
    );
    assert!(
        jumped.script_errors.is_empty(),
        "dead id must not error: {:?}",
        jumped.script_errors
    );
}

#[test]
fn gs_raycast_hits_static_box_on_second_step() {
    let mut world = world_from(vec![
        camera(),
        rigid(
            2,
            0.0,
            0.0,
            "static",
            ColliderShape::Box { w: 4.0, h: 1.0 },
            false,
        ),
    ]);
    world.attach_script(
        1,
        r#"
            return {
              on_update = function(self)
                local r = gs.raycast(0, 4, 0, -2)
                if r and r.hit then
                  gs.emit("ray_hit", { id = r.hit.id, x = r.hit.x, y = r.hit.y })
                else
                  gs.emit("ray_miss", {})
                end
              end
            }
        "#,
    );
    let mut host = ScriptHost::new().expect("host");
    let mut phys = PhysicsHost::new();
    let input = InputFrame::default();
    step_with_hosts(&mut world, &input, &mut host, &mut phys).expect("insert");
    assert!(
        world.play_events.iter().any(|e| e.name == "ray_miss"),
        "first step has no last-frame bodies: {:?}",
        world.play_events
    );

    step_with_hosts(&mut world, &input, &mut host, &mut phys).expect("query");
    let hit = world
        .play_events
        .iter()
        .rev()
        .find(|e| e.name == "ray_hit")
        .expect("second step should hit last-frame box");
    assert_eq!(hit.data["id"], "e_000002");
}

#[test]
fn gs_overlaps_returns_other_id_after_sensor_step() {
    let mut world = world_from(vec![
        camera(),
        rigid(
            3,
            0.0,
            1.0,
            "static",
            ColliderShape::Box { w: 2.0, h: 2.0 },
            true,
        ),
        rigid(
            RUNTIME_ID_BASE + 1,
            0.0,
            1.0,
            "static",
            ColliderShape::Box { w: 1.0, h: 1.0 },
            false,
        ),
    ]);
    world.attach_script(
        3,
        r#"
            return {
              on_update = function(self)
                local o = gs.overlaps(self.id)
                gs.emit("ov", { ids = o.ids })
                local dead = gs.overlaps("e_000999")
                gs.emit("ov_dead", { n = #dead.ids })
              end
            }
        "#,
    );
    let mut host = ScriptHost::new().expect("host");
    let mut phys = PhysicsHost::new();
    let input = InputFrame::default();
    step_with_hosts(&mut world, &input, &mut host, &mut phys).expect("insert");
    let first = emit_ids(&world, "ov");
    assert_eq!(first.last(), Some(&Vec::<String>::new()));

    step_with_hosts(&mut world, &input, &mut host, &mut phys).expect("query");
    let second = emit_ids(&world, "ov");
    assert_eq!(second.last(), Some(&vec!["rt_1".to_string()]));
    assert!(world
        .play_events
        .iter()
        .any(|e| { e.name == "ov_dead" && e.data["n"].as_i64() == Some(0) }));
}

#[test]
fn gs_find_by_tag_returns_sorted_ids() {
    let mut world = world_from(vec![
        camera(),
        tagged(5, 0.0, 0.0, &["mob", "z"]),
        tagged(2, 1.0, 0.0, &["mob"]),
        tagged(3, 2.0, 0.0, &["mob"]),
        tagged(4, 3.0, 0.0, &["other"]),
    ]);
    world.attach_script(
        1,
        r#"
            return {
              on_update = function(self)
                local all = gs.find_by_tag("mob", 1000)
                gs.emit("found", { ids = all.ids })
                local limited = gs.find_by_tag("mob", 2)
                gs.emit("found2", { ids = limited.ids })
                local r = gs.raycast(0, 1, 0, 0)
                if r ~= nil then
                  error("bare step raycast must be nil")
                end
                local o = gs.overlaps(self.id)
                if #o.ids ~= 0 then
                  error("bare step overlaps must be empty")
                end
              end
            }
        "#,
    );
    step(&mut world, &InputFrame::default()).expect("step");
    assert!(world.script_errors.is_empty(), "{:?}", world.script_errors);
    assert_eq!(
        emit_ids(&world, "found").last(),
        Some(&vec![
            "e_000002".to_string(),
            "e_000003".to_string(),
            "e_000005".to_string()
        ])
    );
    assert_eq!(
        emit_ids(&world, "found2").last(),
        Some(&vec!["e_000002".to_string(), "e_000003".to_string()])
    );
}

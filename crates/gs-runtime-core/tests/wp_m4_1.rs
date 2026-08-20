use gs_runtime_core::{
    format_play_id, step, step_with_physics, InputFrame, PhysicsHost, World, RUNTIME_ID_BASE,
};
use gs_scene::{
    Camera2D, Collider2D, ColliderShape, Entity, Name, RigidBody2D, Scene, Transform2D,
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

fn rigid(
    id: u64,
    x: f32,
    y: f32,
    kind: &str,
    ccd: bool,
    shape: ColliderShape,
    sensor: bool,
) -> Entity {
    let mut entity = Entity::new(id, None, 1);
    entity.transform = Some(transform_at(x, y));
    entity.extra.rigid_body = Some(RigidBody2D {
        kind: kind.into(),
        ccd,
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

fn world_from(entities: Vec<Entity>, seed: u64) -> World {
    let mut scene = Scene::default();
    for entity in entities {
        scene.entities.insert(entity.id, entity);
    }
    World::from_scene(scene, seed)
}

fn pose(world: &World, id: u64) -> (f32, f32, f32) {
    let t = world
        .entities
        .get(&id)
        .and_then(|e| e.transform.as_ref())
        .expect("transform");
    (t.x, t.y, t.rot)
}

fn fall_world(seed: u64) -> World {
    world_from(
        vec![
            camera(),
            rigid(
                2,
                0.0,
                0.0,
                "static",
                false,
                ColliderShape::Box { w: 40.0, h: 1.0 },
                false,
            ),
            rigid(
                3,
                -0.4,
                6.0,
                "dynamic",
                false,
                ColliderShape::Box { w: 1.0, h: 1.0 },
                false,
            ),
            rigid(
                4,
                0.4,
                8.0,
                "dynamic",
                false,
                ColliderShape::Box { w: 1.0, h: 1.0 },
                false,
            ),
        ],
        seed,
    )
}

fn run_fall(seed: u64, frames: u32) -> World {
    let mut world = fall_world(seed);
    let mut phys = PhysicsHost::new();
    let input = InputFrame::default();
    for _ in 0..frames {
        step_with_physics(&mut world, &input, &mut phys).expect("step");
    }
    world
}

#[test]
fn two_dynamic_boxes_fall_deterministically() {
    let a = run_fall(42, 180);
    let b = run_fall(42, 180);
    let pa = pose(&a, 3);
    let pb = pose(&b, 3);
    let qa = pose(&a, 4);
    let qb = pose(&b, 4);
    assert_eq!(pa, pb, "box 3 mismatch");
    assert_eq!(qa, qb, "box 4 mismatch");
    assert!(pa.1 < 6.0 && qa.1 < 8.0, "boxes should fall: {pa:?} {qa:?}");
    assert!(
        pa.1 > 0.4 && qa.1 > 0.4,
        "boxes should rest above the ground: {pa:?} {qa:?}"
    );
}

#[test]
fn sensor_overlap_queues_stable_collision_enter() {
    let mut world = world_from(
        vec![
            camera(),
            rigid(
                3,
                0.0,
                1.0,
                "static",
                false,
                ColliderShape::Box { w: 2.0, h: 2.0 },
                true,
            ),
            rigid(
                7,
                0.0,
                1.0,
                "static",
                false,
                ColliderShape::Box { w: 1.0, h: 1.0 },
                false,
            ),
        ],
        1,
    );
    let mut phys = PhysicsHost::new();
    step_with_physics(&mut world, &InputFrame::default(), &mut phys).expect("step");

    assert_eq!(world.queued_script_events.len(), 2);
    assert_eq!(world.queued_script_events[0].target_id, 3);
    assert_eq!(world.queued_script_events[0].name, "collision_enter");
    assert_eq!(
        world.queued_script_events[0].data["other"],
        format_play_id(7)
    );
    assert_eq!(world.queued_script_events[0].data["is_sensor"], true);
    assert_eq!(world.queued_script_events[1].target_id, 7);
    assert_eq!(world.queued_script_events[1].name, "collision_enter");
    assert_eq!(
        world.queued_script_events[1].data["other"],
        format_play_id(3)
    );
    assert_eq!(world.queued_script_events[1].data["is_sensor"], true);

    let mut again = world_from(
        vec![
            camera(),
            rigid(
                3,
                0.0,
                1.0,
                "static",
                false,
                ColliderShape::Box { w: 2.0, h: 2.0 },
                true,
            ),
            rigid(
                7,
                0.0,
                1.0,
                "static",
                false,
                ColliderShape::Box { w: 1.0, h: 1.0 },
                false,
            ),
        ],
        1,
    );
    let mut phys2 = PhysicsHost::new();
    step_with_physics(&mut again, &InputFrame::default(), &mut phys2).expect("step");
    assert_eq!(world.queued_script_events, again.queued_script_events);
    assert_eq!(phys.physics_overlaps(3), vec![7]);
    assert_eq!(phys.physics_overlaps(7), vec![3]);
}

#[test]
fn ccd_body_does_not_tunnel_thin_static() {
    // Thin floor at y=0 (half-extent 0.05). Fast CCD body starts at y=1.
    // 400 u/s * 1/60 ≈ 6.67 units/frame — without CCD this tunnels.
    // If this flakes on a machine, weaken to `y > -5.0` and keep the comment;
    // do not fake a pass by skipping the step.
    let mut world = world_from(
        vec![
            camera(),
            rigid(
                2,
                0.0,
                0.0,
                "static",
                false,
                ColliderShape::Box { w: 8.0, h: 0.1 },
                false,
            ),
            rigid(
                3,
                0.0,
                1.0,
                "dynamic",
                true,
                ColliderShape::Box { w: 0.4, h: 0.4 },
                false,
            ),
        ],
        7,
    );
    let mut phys = PhysicsHost::new();
    let input = InputFrame::default();
    step_with_physics(&mut world, &input, &mut phys).expect("insert");
    phys.set_linear_velocity(3, 0.0, -400.0);
    for _ in 0..8 {
        step_with_physics(&mut world, &input, &mut phys).expect("step");
    }
    let y = pose(&world, 3).1;
    assert!(
        y > -1.0,
        "ccd body tunneled the thin static (y={y}); if flaky, weaken to y > -5"
    );
}

#[test]
fn physics_raycast_and_overlaps() {
    let mut world = world_from(
        vec![
            camera(),
            rigid(
                2,
                0.0,
                0.0,
                "static",
                false,
                ColliderShape::Box { w: 4.0, h: 1.0 },
                false,
            ),
            rigid(
                RUNTIME_ID_BASE + 1,
                0.0,
                2.0,
                "static",
                false,
                ColliderShape::Circle { r: 0.5 },
                true,
            ),
        ],
        1,
    );
    let mut phys = PhysicsHost::new();
    step_with_physics(&mut world, &InputFrame::default(), &mut phys).expect("step");

    let hit = phys
        .physics_raycast(0.0, 4.0, 0.0, -2.0, None)
        .expect("ray should hit");
    assert_eq!(hit.id, RUNTIME_ID_BASE + 1);
    assert!(hit.y.is_finite());

    let ground = phys
        .physics_raycast(0.0, 4.0, 0.0, -2.0, Some(1))
        .expect("masked ray");
    assert!(ground.id == 2 || ground.id == RUNTIME_ID_BASE + 1);

    assert_eq!(
        phys.physics_overlaps(RUNTIME_ID_BASE + 1),
        Vec::<u64>::new()
    );
}

#[test]
fn nan_transform_is_not_sent_to_rapier() {
    let mut world = world_from(
        vec![
            camera(),
            rigid(
                2,
                0.0,
                3.0,
                "dynamic",
                false,
                ColliderShape::Box { w: 1.0, h: 1.0 },
                false,
            ),
        ],
        1,
    );
    if let Some(t) = world
        .entities
        .get_mut(&2)
        .and_then(|e| e.transform.as_mut())
    {
        t.x = f32::NAN;
    }
    let mut phys = PhysicsHost::new();
    step_with_physics(&mut world, &InputFrame::default(), &mut phys).expect("step");
    assert!(world.warnings.iter().any(|w| w.contains("GS-EC-01")));
    let t = world
        .entities
        .get(&2)
        .and_then(|e| e.transform.as_ref())
        .expect("kept");
    assert!(t.x.is_nan());
}

#[test]
fn no_rigid_body_keeps_stub_physics_via_bare_step() {
    let mut world = world_from(vec![camera()], 1);
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
    assert!(world.queued_script_events.is_empty());
}

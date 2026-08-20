//! WP-M4-3: `gs.play_sfx` / camera follow+shake / AudioSource queue (no speaker).

use gs_runtime_core::{step, step_with_host, InputFrame, ScriptHost, World};
use gs_scene::{AssetRef, AudioSource, Camera2D, Entity, Name, Scene, Script, Transform2D};

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

fn target() -> Entity {
    let mut entity = Entity::new(2, None, 1);
    entity.name = Some(Name {
        value: "hero".into(),
    });
    entity.transform = Some(transform_at(5.0, 2.0));
    entity
}

fn script_entity() -> Entity {
    let mut entity = Entity::new(3, None, 2);
    entity.transform = Some(transform_at(0.0, 0.0));
    entity.extra.script = Some(Script {
        file: "scripts/cam.luau".into(),
        props: Default::default(),
    });
    entity
}

fn loop_source() -> Entity {
    let mut entity = Entity::new(4, None, 3);
    entity.transform = Some(transform_at(0.0, 0.0));
    entity.extra.audio = Some(AudioSource {
        asset: AssetRef {
            id: "a_loop".into(),
        },
        volume: 0.4,
        pan: 0.1,
        loop_play: true,
        autoplay: true,
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

fn cam_xy(world: &World) -> (f32, f32) {
    let t = world
        .entities
        .get(&1)
        .and_then(|e| e.transform.as_ref())
        .expect("camera transform");
    (t.x, t.y)
}

const SCRIPT: &str = r#"
local M = {}
function M.on_init(self)
  gs.play_sfx({["$asset"]="a_000008"}, {volume=0.8, pan=-0.25})
  gs.camera_follow("e_000002")
  gs.camera_shake(1.5, 0.25)
end
function M.on_update(self, dt)
  gs.set_pos("e_000002", 12, 4)
end
return M
"#;

#[test]
fn play_sfx_camera_follow_and_shake() {
    let mut world = world_from(vec![camera(), target(), script_entity(), loop_source()]);
    world.attach_script(3, SCRIPT);
    let mut host = ScriptHost::new().expect("host");

    let snap = step_with_host(&mut world, &InputFrame::default(), &mut host).expect("step 1");
    let (cx, cy) = cam_xy(&world);
    assert!(
        (cx - 12.0).abs() < 1e-5 && (cy - 4.0).abs() < 1e-5,
        "follow camera should track target, got {cx},{cy}"
    );
    let first_shake = world.camera_shake_offset[0].abs();
    assert!(
        first_shake > 0.0,
        "shake offset should be non-zero after start, got {:?}",
        world.camera_shake_offset
    );
    assert!(
        (snap.camera.position[0] - (cx + world.camera_shake_offset[0])).abs() < 1e-5,
        "snapshot camera should include shake offset"
    );
    assert!(
        world.sfx_queue.iter().any(|r| r.asset_id == "a_000008"
            && !r.looping
            && (r.volume - 0.8).abs() < 1e-5
            && (r.pan + 0.25).abs() < 1e-5),
        "play_sfx queue missing a_000008: {:?}",
        world.sfx_queue
    );
    assert!(
        world
            .sfx_queue
            .iter()
            .any(|r| r.asset_id == "a_loop" && r.looping),
        "AudioSource autoplay/loop should enqueue: {:?}",
        world.sfx_queue
    );

    let mut later_shake = first_shake;
    for _ in 0..8 {
        step_with_host(&mut world, &InputFrame::default(), &mut host).expect("step");
        let (cx, cy) = cam_xy(&world);
        assert!(
            (cx - 12.0).abs() < 1e-5 && (cy - 4.0).abs() < 1e-5,
            "follow should keep tracking, got {cx},{cy}"
        );
        later_shake = world.camera_shake_offset[0].abs();
    }
    assert!(
        later_shake < first_shake,
        "shake should decay: first={first_shake} later={later_shake}"
    );
}

#[test]
fn camera_follow_nil_stops_tracking() {
    let mut world = world_from(vec![camera(), target()]);
    world.attach_script(
        2,
        r#"
local M = {}
function M.on_init(self)
  gs.camera_follow("e_000002")
end
function M.on_update(self)
  if gs.time().frame >= 1 then
    gs.camera_follow(nil)
    gs.set_pos("e_000002", 99, 99)
  end
end
return M
"#,
    );
    let mut host = ScriptHost::new().expect("host");
    step_with_host(&mut world, &InputFrame::default(), &mut host).expect("step 1");
    let (cx, _) = cam_xy(&world);
    assert!(
        (cx - 5.0).abs() < 1e-5,
        "first frame follows spawn x, got {cx}"
    );
    step_with_host(&mut world, &InputFrame::default(), &mut host).expect("step 2");
    let (cx, cy) = cam_xy(&world);
    assert!(
        (cx - 5.0).abs() < 1e-5 && (cy - 2.0).abs() < 1e-5,
        "nil follow should leave camera, got {cx},{cy}"
    );
}

#[test]
fn missing_audio_file_is_only_a_queue_entry() {
    let mut world = world_from(vec![camera()]);
    world.attach_script(1, r#"gs.play_sfx({id="no_such_asset"})"#);
    step(&mut world, &InputFrame::default()).expect("step");
    assert_eq!(world.sfx_queue.len(), 1);
    assert_eq!(world.sfx_queue[0].asset_id, "no_such_asset");
}

//! WP-M5-2: `judge.*` on the player control server (MASTER 4.2 / 6.3 / T5.2 / GS-EC-35).

use std::net::{IpAddr, Ipv4Addr, SocketAddr};

use gs_player::{ControlConfig, ControlServer};
use gs_runtime_core::World;
use gs_scene::{Camera2D, Entity, Name, Scene, Transform2D};
use serde_json::{json, Value};
use tempfile::TempDir;

const EMIT_SRC: &str = r#"
local M = {}
function M.on_update(self)
  gs.emit("CoinPicked", { coin = self.id })
end
return M
"#;

fn bind() -> SocketAddr {
    SocketAddr::new(IpAddr::V4(Ipv4Addr::LOCALHOST), 0)
}

fn transform() -> Transform2D {
    Transform2D {
        x: 0.0,
        y: 0.0,
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
    entity.transform = Some(transform());
    entity.extra.camera = Some(Camera2D {
        ortho_height: 10.0,
        active: true,
    });
    entity
}

fn camera_world() -> World {
    let mut scene = Scene::default();
    scene.entities.insert(1, camera());
    World::from_scene(scene, 7)
}

fn emit_world() -> World {
    let mut scene = Scene::default();
    scene.entities.insert(1, camera());
    let mut emitter = Entity::new(2, None, 1);
    emitter.name = Some(Name {
        value: "coin".into(),
    });
    emitter.transform = Some(transform());
    scene.entities.insert(2, emitter);
    let mut world = World::from_scene(scene, 7);
    world.attach_script(2, EMIT_SRC);
    world
}

fn no_render() -> ControlConfig {
    ControlConfig {
        no_render: true,
        ..ControlConfig::default()
    }
}

fn camera_dump(x: f64) -> Value {
    json!({
        "frame": 0,
        "seed": 7,
        "entity_count": 1,
        "entities": [{
            "id": "e_000001",
            "parent": null,
            "order": 0,
            "name": "cam",
            "transform": {
                "x": x,
                "y": 0.0,
                "rot": 0.0,
                "sx": 1.0,
                "sy": 1.0,
                "z_index": 0
            },
            "has_sprite": false,
            "has_camera": true
        }]
    })
}

#[test]
fn run_until_event_registers_then_sees_emit() {
    let tmp = TempDir::new().expect("temp");
    let handle = ControlServer::start_with_config(
        emit_world(),
        bind(),
        Some(tmp.path().to_path_buf()),
        no_render(),
    )
    .expect("control");
    let play_id = handle.status().play_id.clone();

    let hit = handle
        .judge_run_until_event(json!({
            "play_id": play_id,
            "name": "CoinPicked",
            "timeout_frames": 8
        }))
        .expect("judge.run_until_event");
    assert_eq!(hit["ok"], json!(true));
    assert_eq!(hit["name"], json!("CoinPicked"));
    let seq = hit["seq"].as_u64().expect("seq");
    assert!(seq > 0, "expected a ring seq, got {hit}");
    assert_eq!(hit["event"]["name"], json!("CoinPicked"));
}

#[test]
fn run_until_event_missing_fails_gs_ec_35() {
    let tmp = TempDir::new().expect("temp");
    let handle = ControlServer::start_with_config(
        camera_world(),
        bind(),
        Some(tmp.path().to_path_buf()),
        no_render(),
    )
    .expect("control");

    let err = handle
        .judge_run_until_event(json!({
            "name": "NeverHappens",
            "timeout_frames": 8
        }))
        .expect_err("missing event must fail");
    let msg = err.to_string();
    assert!(msg.contains("GS-EC-35"), "expected GS-EC-35, got {msg}");
    assert!(
        !msg.to_ascii_lowercase().contains("ok\":true"),
        "must not false-pass: {msg}"
    );
}

#[test]
fn wait_event_sees_coin_picked_already_in_ring() {
    let tmp = TempDir::new().expect("temp");
    let handle = ControlServer::start_with_config(
        emit_world(),
        bind(),
        Some(tmp.path().to_path_buf()),
        no_render(),
    )
    .expect("control");
    let play_id = handle.status().play_id.clone();
    handle
        .step_frames(1)
        .expect("step so CoinPicked is in the ring");

    let before = handle
        .obs_events(&play_id, 0, Some("CoinPicked"), 8)
        .expect("obs.events");
    let events = before["events"].as_array().expect("events");
    assert!(
        !events.is_empty(),
        "ring must already hold CoinPicked: {before}"
    );

    let hit = handle
        .judge_wait_event(json!({
            "play_id": play_id,
            "name": "CoinPicked",
            "after_seq": 0
        }))
        .expect("judge.wait_event");
    assert_eq!(hit["name"], json!("CoinPicked"));
    assert!(hit["seq"].as_u64().unwrap_or(0) > 0);

    let missing = handle
        .judge_wait_event(json!({
            "name": "NeverHappens",
            "after_seq": 0
        }))
        .expect_err("wait_event must not hang on a missing name");
    assert!(
        missing.to_string().contains("GS-EC-35"),
        "expected GS-EC-35, got {missing}"
    );
}

#[test]
fn assert_world_epsilon_1e_minus_5_passes_and_1_fails() {
    let tmp = TempDir::new().expect("temp");
    let handle = ControlServer::start_with_config(
        camera_world(),
        bind(),
        Some(tmp.path().to_path_buf()),
        no_render(),
    )
    .expect("control");

    handle
        .judge_assert_world(json!({
            "expected": camera_dump(1e-5),
            "epsilon": 1e-5
        }))
        .expect("dumps that differ by 1e-5 must pass");

    let err = handle
        .judge_assert_world(json!({
            "expected": camera_dump(1.0),
            "epsilon": 1e-5
        }))
        .expect_err("dumps that differ by 1.0 must fail");
    let msg = err.to_string();
    assert!(
        msg.contains("E_ASSERT") || msg.contains("epsilon"),
        "expected assert/epsilon fail, got {msg}"
    );
}

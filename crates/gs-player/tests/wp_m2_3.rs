//! WP-M2-3: event trace + obs.events on the control server.

use std::net::{IpAddr, Ipv4Addr, SocketAddr};

use gs_player::ControlServer;
use gs_runtime_core::World;
use gs_scene::{Camera2D, Entity, Name, Scene, Transform2D};
use tempfile::TempDir;

fn camera_world() -> World {
    let mut scene = Scene::default();
    let mut entity = Entity::new(1, None, 0);
    entity.name = Some(Name {
        value: "cam".into(),
    });
    entity.transform = Some(Transform2D {
        x: 0.0,
        y: 0.0,
        rot: 0.0,
        sx: 1.0,
        sy: 1.0,
        z_index: 0,
    });
    entity.extra.camera = Some(Camera2D {
        ortho_height: 10.0,
        active: true,
    });
    scene.entities.insert(1, entity);
    World::from_scene(scene, 7)
}

fn bind() -> SocketAddr {
    SocketAddr::new(IpAddr::V4(Ipv4Addr::LOCALHOST), 0)
}

#[test]
fn step_frames_then_obs_events_sees_frame_advanced() {
    let tmp = TempDir::new().expect("temp");
    let handle = ControlServer::start_in(camera_world(), bind(), tmp.path()).expect("control");
    let play_id = handle.status().play_id.clone();
    handle.step_frames(3).expect("step");

    let result = handle
        .obs_events(&play_id, 0, Some("FrameAdvanced"), 64)
        .expect("obs.events");
    let events = result["events"].as_array().expect("events array");
    assert_eq!(events.len(), 3, "expected three FrameAdvanced events");
    for (idx, event) in events.iter().enumerate() {
        assert_eq!(event["name"], "FrameAdvanced");
        assert_eq!(event["frame"].as_u64(), Some((idx + 1) as u64));
        assert!(event["seq"].as_u64().unwrap_or(0) > 0);
    }
}

#[test]
fn obs_events_wrong_play_id_is_rejected() {
    let tmp = TempDir::new().expect("temp");
    let handle = ControlServer::start_in(camera_world(), bind(), tmp.path()).expect("control");
    handle.step_frames(1).expect("step");

    let err = handle
        .obs_events("p_wrong_play_id", 0, None, 16)
        .expect_err("wrong play_id");
    assert!(
        err.to_string().contains("E_NOT_FOUND"),
        "expected E_NOT_FOUND, got {err}"
    );
}

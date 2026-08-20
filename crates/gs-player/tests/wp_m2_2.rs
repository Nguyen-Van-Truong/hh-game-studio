//! WP-M2-2: control server pause/step, stale player.json, token secrecy.

use std::net::{IpAddr, Ipv4Addr, SocketAddr};

use gs_player::{read_player_file, write_player_file, ControlServer, PlayerFile};
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
fn pause_then_step_frames_advances_exactly_two() {
    let handle = ControlServer::start(camera_world(), bind()).expect("control");
    let paused = handle.pause();
    assert!(paused.paused);
    let before = handle.status().frame;
    let after = handle.step_frames(2).expect("step");
    assert_eq!(after.frame, before + 2);
    assert!(after.paused);
    assert_eq!(handle.status().frame, before + 2);
}

#[test]
fn step_when_not_paused_auto_pauses_then_steps() {
    let handle = ControlServer::start(camera_world(), bind()).expect("control");
    assert!(!handle.status().paused);
    let before = handle.status().frame;
    let after = handle.step_frames(2).expect("step");
    assert!(after.paused, "GS-EC-30: step must pause first");
    assert_eq!(after.frame, before + 2);
    let again = handle.status();
    assert!(again.paused);
    assert_eq!(again.frame, before + 2);
}

#[test]
fn stale_player_json_with_dead_pid_is_removed_on_start() {
    let tmp = TempDir::new().expect("temp");
    let path = tmp.path().join(".gs").join("runtime").join("player.json");
    std::fs::create_dir_all(path.parent().expect("parent")).expect("dirs");
    let stale = PlayerFile::new(
        999_999_999,
        1,
        "p_stale",
        "2026-08-16T00:00:00Z",
        "stale-secret-token-must-not-survive",
    );
    write_player_file(&path, &stale).expect("write stale");
    assert!(path.is_file());
    let handle = ControlServer::start_in(camera_world(), bind(), tmp.path()).expect("start");
    let written = handle.player_json_path().expect("player.json path");
    assert_eq!(written, path);
    let live = read_player_file(written).expect("live file");
    assert_ne!(live.pid, 999_999_999);
    assert_eq!(live.pid, std::process::id());
    assert_ne!(live.token(), "stale-secret-token-must-not-survive");
    assert_ne!(live.port, 0);
}

#[test]
fn token_is_not_in_debug_or_status_strings() {
    let tmp = TempDir::new().expect("temp");
    let handle = ControlServer::start_in(camera_world(), bind(), tmp.path()).expect("start");
    let path = handle.player_json_path().expect("path");
    let file = read_player_file(path).expect("player.json");
    let token = file.token().to_owned();
    assert!(token.len() >= 16, "token should be a real secret");

    let blobs = [
        format!("{handle:?}"),
        format!("{:?}", handle.status()),
        format!("{file:?}"),
        serde_json::to_string(&handle.status()).expect("status json"),
    ];
    for blob in &blobs {
        assert!(!blob.contains(&token), "secret leaked into {blob}");
    }
}

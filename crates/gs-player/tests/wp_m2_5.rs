//! WP-M2-5: no-render, watchdog, step cap, persistent control.

use std::fs;
use std::net::{IpAddr, Ipv4Addr, SocketAddr};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::time::{Duration, Instant};

use gs_player::{
    memory_guard_trip, read_player_file, run_headless_frames, sha256_hex, ControlClient,
    ControlConfig, ControlServer, PlaySource, EXIT_OOM_GUARD, EXIT_SCRIPT_HANG, MAX_STEP_FRAMES,
    OOM_GUARD_BYTES,
};
use gs_runtime_core::World;
use gs_scene::{to_canonical_vec, AssetRef, Camera2D, Entity, Name, Scene, Sprite, Transform2D};
use serde_json::{json, Value};
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

fn write_canonical(path: &Path, value: &Value) {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).expect("parent");
    }
    fs::write(path, to_canonical_vec(value)).expect("write canonical");
}

fn scene_one_cam_one_sprite() -> Scene {
    let mut scene = Scene::default();
    let mut cam = Entity::new(1, None, 0);
    cam.name = Some(Name {
        value: "cam1".into(),
    });
    cam.transform = Some(Transform2D {
        x: 0.0,
        y: 0.0,
        rot: 0.0,
        sx: 1.0,
        sy: 1.0,
        z_index: 0,
    });
    cam.extra.camera = Some(Camera2D {
        ortho_height: 10.0,
        active: true,
    });
    let mut hero = Entity::new(2, None, 1);
    hero.name = Some(Name {
        value: "Hero".into(),
    });
    hero.transform = Some(Transform2D {
        x: 1.0,
        y: 2.0,
        rot: 0.0,
        sx: 1.0,
        sy: 1.0,
        z_index: 0,
    });
    hero.extra.sprite = Some(Sprite {
        asset: AssetRef {
            id: "a_000001".into(),
        },
        color: [1.0, 1.0, 1.0, 1.0],
        flip_x: false,
        flip_y: false,
        pivot: [0.0, 0.0],
    });
    scene.entities.insert(1, cam);
    scene.entities.insert(2, hero);
    scene
}

fn write_play_snapshot(dir: &Path) -> PathBuf {
    let play_dir = dir.join("play").join("p-000001");
    fs::create_dir_all(play_dir.join("scripts")).expect("scripts dir");
    let scene = scene_one_cam_one_sprite();
    let scene_bytes = to_canonical_vec(&scene.to_canonical_value());
    fs::write(play_dir.join("scene.json"), &scene_bytes).expect("scene");
    write_canonical(
        &play_dir.join("project-settings.json"),
        &json!({ "fixed_dt": 1.0 / 60.0, "ppu": 16, "schema_version": 1 }),
    );
    write_canonical(&play_dir.join("input-map.json"), &json!({ "actions": [] }));
    write_canonical(&play_dir.join("asset-manifest.json"), &json!({}));
    let script = b"-- fixture only; player must not execute this\n";
    fs::write(play_dir.join("scripts").join("noop.luau"), script).expect("script");
    let mut listing = serde_json::Map::new();
    listing.insert(
        "scripts/noop.luau".into(),
        Value::String(sha256_hex(script)),
    );
    let scripts_hash = sha256_hex(&to_canonical_vec(&Value::Object(listing)));
    let input_bytes = fs::read(play_dir.join("input-map.json")).expect("input");
    let assets_bytes = fs::read(play_dir.join("asset-manifest.json")).expect("assets");
    let manifest = json!({
        "actor": "act_test",
        "created_at": "2026-08-16T00:00:00Z",
        "document_revision": "r-000001",
        "engine_ver": "0.1.0-m2-5",
        "hashes": {
            "assets": sha256_hex(&assets_bytes),
            "inputmap": sha256_hex(&input_bytes),
            "scene": sha256_hex(&scene_bytes),
            "scripts": scripts_hash,
        },
        "play_id": "p-000001",
        "protocol_ver": "1.0",
        "seed": 42,
    });
    write_canonical(&play_dir.join("manifest.json"), &manifest);
    play_dir.join("manifest.json")
}

fn player_exe() -> Option<PathBuf> {
    option_env!("CARGO_BIN_EXE_gs_player").map(PathBuf::from)
}

struct KillOnDrop(Option<Child>);

impl Drop for KillOnDrop {
    fn drop(&mut self) {
        if let Some(mut child) = self.0.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

fn wait_file(path: &Path, timeout: Duration) -> bool {
    let start = Instant::now();
    while start.elapsed() < timeout {
        if path.is_file() {
            return true;
        }
        std::thread::sleep(Duration::from_millis(20));
    }
    false
}

#[test]
fn no_render_steps_and_screenshot_returns_no_gpu() {
    let tmp = TempDir::new().expect("temp");
    let manifest = write_play_snapshot(tmp.path());
    let report = run_headless_frames(&manifest, 2).expect("headless frames");
    assert_eq!(report.frames, 2);

    let handle = ControlServer::start_with_config(
        camera_world(),
        bind(),
        None,
        ControlConfig {
            no_render: true,
            ..ControlConfig::default()
        },
    )
    .expect("control");
    let before = handle.status().frame;
    let after = handle.step_frames(3).expect("step");
    assert_eq!(after.frame, before + 3);
    let err = handle.obs_screenshot(None).expect_err("screenshot");
    assert!(
        err.to_string().contains("no_gpu"),
        "expected app_code no_gpu, got {err}"
    );
    assert!(!handle.is_stopped());
}

#[test]
fn watchdog_inject_reports_exit_13() {
    let handle =
        ControlServer::start_with_config(camera_world(), bind(), None, ControlConfig::default())
            .expect("control");
    handle.inject_test_hang_ms(2001);
    let err = handle.step_frames(1).expect_err("hang");
    assert!(
        err.to_string().contains("SCRIPT_HANG"),
        "expected SCRIPT_HANG, got {err}"
    );
    assert!(handle.is_stopped());
    assert_eq!(handle.last_error().as_deref(), Some("SCRIPT_HANG"));
    let report = handle.exit_report().expect("exit_report");
    assert_eq!(report.exit_code, EXIT_SCRIPT_HANG);
}

#[test]
fn step_frames_over_cap_is_rejected() {
    let handle = ControlServer::start(camera_world(), bind()).expect("control");
    let err = handle.step_frames(MAX_STEP_FRAMES + 1).expect_err("cap");
    let msg = err.to_string();
    assert!(
        msg.contains("exceeds cap") && msg.contains("3600"),
        "expected cap error, got {msg}"
    );
    assert!(!handle.is_stopped());
    assert_eq!(handle.status().frame, 0);
}

#[test]
fn memory_guard_inject_reports_exit_14() {
    assert!(memory_guard_trip(OOM_GUARD_BYTES + 1, OOM_GUARD_BYTES));
    let handle = ControlServer::start(camera_world(), bind()).expect("control");
    handle.inject_memory_bytes(OOM_GUARD_BYTES + 1);
    let err = handle.step_frames(1).expect_err("oom");
    assert!(
        err.to_string().contains("OOM_GUARD"),
        "expected OOM_GUARD, got {err}"
    );
    assert!(handle.is_stopped());
    assert_eq!(handle.last_error().as_deref(), Some("OOM_GUARD"));
    let report = handle.exit_report().expect("exit_report");
    assert_eq!(report.exit_code, EXIT_OOM_GUARD);
}

#[test]
fn persistent_tcp_survives_hello_step_and_obs() {
    let tmp = TempDir::new().expect("temp");
    let manifest = write_play_snapshot(tmp.path());
    let handle = ControlServer::start_with_config(
        PlaySource::Snapshot(manifest),
        bind(),
        Some(tmp.path().to_path_buf()),
        ControlConfig {
            no_render: true,
            ..ControlConfig::default()
        },
    )
    .expect("control");
    let path = handle.player_json_path().expect("player.json");
    let file = read_player_file(path).expect("read player.json");
    let play_id = file.play_id.clone();
    let mut client = ControlClient::connect_player_file(&file).expect("hello");
    let status = client.status().expect("status");
    assert_eq!(status.play_id, play_id);
    let stepped = client.step_frames(2).expect("step_frames");
    assert_eq!(stepped.frame, 2);
    let events = client
        .events(&play_id, 0, Some("FrameAdvanced"), 16)
        .expect("obs.events");
    assert_eq!(
        events["events"].as_array().map(Vec::len),
        Some(2),
        "{events}"
    );
    let dump = client.world_dump(&play_id).expect("obs.world_dump");
    let dump_path = dump["path"].as_str().expect("path");
    assert!(Path::new(dump_path).is_file(), "{dump_path}");
    let shot = client.screenshot(&play_id, None).expect_err("screenshot");
    assert!(
        shot.to_string().contains("no_gpu"),
        "expected no_gpu, got {shot}"
    );
    let report = client.stop(false).expect("stop");
    assert_eq!(report.exit_code, 0);
}

#[test]
fn player_bin_no_render_screenshot_is_no_gpu() {
    let Some(exe) = player_exe() else {
        return;
    };
    let tmp = TempDir::new().expect("temp");
    let manifest = write_play_snapshot(tmp.path());
    let child = Command::new(&exe)
        .arg("--snapshot")
        .arg(&manifest)
        .arg("--headless")
        .arg("--no-render")
        .arg("--control-port")
        .arg("0")
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .expect("spawn gs-player");
    let mut guard = KillOnDrop(Some(child));
    let play_dir = manifest.parent().expect("play dir");
    let player_json = play_dir.join(".gs").join("runtime").join("player.json");
    assert!(
        wait_file(&player_json, Duration::from_secs(10)),
        "player.json missing at {}",
        player_json.display()
    );
    let file = read_player_file(&player_json).expect("player.json");
    let mut client = ControlClient::connect_player_file(&file).expect("hello");
    client.step_frames(1).expect("step");
    let err = client
        .screenshot(&file.play_id, None)
        .expect_err("screenshot");
    assert!(
        err.to_string().contains("no_gpu"),
        "expected no_gpu, got {err}"
    );
    let _ = client.stop(false);
    if let Some(mut child) = guard.0.take() {
        let _ = child.wait();
    }
}

#[test]
fn player_bin_watchdog_exits_13() {
    let Some(exe) = player_exe() else {
        return;
    };
    let tmp = TempDir::new().expect("temp");
    let manifest = write_play_snapshot(tmp.path());
    let child = Command::new(&exe)
        .arg("--snapshot")
        .arg(&manifest)
        .arg("--headless")
        .arg("--no-render")
        .arg("--control-port")
        .arg("0")
        .env("GS_TEST_HANG_MS", "2001")
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .expect("spawn gs-player");
    let mut guard = KillOnDrop(Some(child));
    let play_dir = manifest.parent().expect("play dir");
    let player_json = play_dir.join(".gs").join("runtime").join("player.json");
    assert!(
        wait_file(&player_json, Duration::from_secs(10)),
        "player.json missing"
    );
    if let Ok(file) = read_player_file(&player_json) {
        if let Ok(mut client) = ControlClient::connect_player_file(&file) {
            let _ = client.step_frames(1);
        }
    }
    let mut child = guard.0.take().expect("child");
    let start = Instant::now();
    let status = loop {
        if let Some(status) = child.try_wait().expect("try_wait") {
            break status;
        }
        if start.elapsed() > Duration::from_secs(5) {
            let _ = child.kill();
            panic!("gs-player did not exit after injected hang");
        }
        std::thread::sleep(Duration::from_millis(20));
    };
    assert_eq!(
        status.code(),
        Some(EXIT_SCRIPT_HANG),
        "expected exit 13, got {status:?}"
    );
}

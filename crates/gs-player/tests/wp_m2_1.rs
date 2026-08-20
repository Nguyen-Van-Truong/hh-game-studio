//! WP-M2-1: snapshot verify + headless simulate (no window).

use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use gs_player::{run_headless_frames, sha256_hex, verify_snapshot};
use gs_scene::{to_canonical_vec, AssetRef, Camera2D, Entity, Name, Scene, Sprite, Transform2D};
use serde_json::{json, Value};
use tempfile::TempDir;

fn write_canonical(path: &Path, value: &Value) {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).expect("parent");
    }
    fs::write(path, to_canonical_vec(value)).expect("write canonical");
}

fn camera_entity(id: u64, active: bool, ortho: f32, x: f32, y: f32) -> Entity {
    let mut entity = Entity::new(id, None, 0);
    entity.name = Some(Name {
        value: format!("cam{id}"),
    });
    entity.transform = Some(Transform2D {
        x,
        y,
        rot: 0.0,
        sx: 1.0,
        sy: 1.0,
        z_index: 0,
    });
    entity.extra.camera = Some(Camera2D {
        ortho_height: ortho,
        active,
    });
    entity
}

fn sprite_entity(id: u64) -> Entity {
    let mut entity = Entity::new(id, None, 1);
    entity.name = Some(Name {
        value: "Hero".into(),
    });
    entity.transform = Some(Transform2D {
        x: 1.0,
        y: 2.0,
        rot: 0.0,
        sx: 1.0,
        sy: 1.0,
        z_index: 0,
    });
    entity.extra.sprite = Some(Sprite {
        asset: AssetRef {
            id: "a_000001".into(),
        },
        color: [1.0, 1.0, 1.0, 1.0],
        flip_x: false,
        flip_y: false,
        pivot: [0.0, 0.0],
    });
    entity
}

fn scene_one_cam_one_sprite() -> Scene {
    let mut scene = Scene::default();
    scene
        .entities
        .insert(1, camera_entity(1, true, 10.0, 0.0, 0.0));
    scene.entities.insert(2, sprite_entity(2));
    scene
}

fn write_play_snapshot(dir: &Path, scene: &Scene) -> PathBuf {
    let play_dir = dir.join("play").join("p-000001");
    fs::create_dir_all(play_dir.join("scripts")).expect("scripts dir");

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

    let scene_hash = sha256_hex(&scene_bytes);
    let input_bytes = fs::read(play_dir.join("input-map.json")).expect("input");
    let assets_bytes = fs::read(play_dir.join("asset-manifest.json")).expect("assets");

    let manifest = json!({
        "actor": "act_test",
        "created_at": "2026-08-16T00:00:00Z",
        "document_revision": "r-000001",
        "engine_ver": "0.1.0-m2-1",
        "hashes": {
            "assets": sha256_hex(&assets_bytes),
            "inputmap": sha256_hex(&input_bytes),
            "scene": scene_hash,
            "scripts": scripts_hash,
        },
        "play_id": "p-000001",
        "protocol_ver": "1.0",
        "seed": 42,
    });
    write_canonical(&play_dir.join("manifest.json"), &manifest);
    play_dir.join("manifest.json")
}

#[test]
fn verify_ok_on_canonical_snapshot() {
    let tmp = TempDir::new().expect("temp");
    let manifest = write_play_snapshot(tmp.path(), &scene_one_cam_one_sprite());
    let verified = verify_snapshot(&manifest).expect("verify");
    assert_eq!(verified.play_id, "p-000001");
    assert_eq!(verified.document_revision, "r-000001");
    assert_eq!(verified.manifest.seed, 42);
}

#[test]
fn tampered_scene_is_rejected() {
    let tmp = TempDir::new().expect("temp");
    let manifest = write_play_snapshot(tmp.path(), &scene_one_cam_one_sprite());
    let scene_path = manifest.parent().expect("dir").join("scene.json");
    let mut bytes = fs::read(&scene_path).expect("read scene");
    match bytes.iter_mut().find(|b| **b == b'2') {
        Some(b) => *b = b'3',
        None => bytes[0] ^= 0x01,
    }
    fs::write(&scene_path, &bytes).expect("tamper");

    let err = verify_snapshot(&manifest).expect_err("must reject");
    assert!(err.is_reject(), "{err}");
    let msg = err.to_string();
    assert!(
        msg.contains("hash mismatch") || msg.contains("not canonical"),
        "{msg}"
    );
}

#[test]
fn missing_scene_is_rejected() {
    let tmp = TempDir::new().expect("temp");
    let manifest = write_play_snapshot(tmp.path(), &scene_one_cam_one_sprite());
    fs::remove_file(manifest.parent().expect("dir").join("scene.json")).expect("rm");
    let err = verify_snapshot(&manifest).expect_err("missing");
    assert!(err.is_reject(), "{err}");
    assert!(err.to_string().contains("missing file"), "{err}");
}

#[test]
fn run_headless_frames_advances_to_three() {
    let tmp = TempDir::new().expect("temp");
    let manifest = write_play_snapshot(tmp.path(), &scene_one_cam_one_sprite());
    let report = run_headless_frames(&manifest, 3).expect("headless");
    assert_eq!(report.frames, 3);
    assert_eq!(report.play_id, "p-000001");
    assert!((report.snapshot.camera.ortho_height - 10.0).abs() < f32::EPSILON);
    assert_eq!(report.snapshot.camera.position, [0.0, 0.0]);
    assert!(
        report.snapshot.items.iter().any(|i| i.entity_id == 2),
        "sprite missing: {:?}",
        report.snapshot.items
    );
}

fn player_exe() -> Option<PathBuf> {
    option_env!("CARGO_BIN_EXE_gs_player").map(PathBuf::from)
}

#[test]
fn player_bin_rejects_tampered_scene() {
    let Some(exe) = player_exe() else {
        return;
    };
    let tmp = TempDir::new().expect("temp");
    let manifest = write_play_snapshot(tmp.path(), &scene_one_cam_one_sprite());
    let scene_path = manifest.parent().expect("dir").join("scene.json");
    let mut bytes = fs::read(&scene_path).expect("read");
    bytes[0] ^= 0x01;
    fs::write(&scene_path, &bytes).expect("tamper");

    let output = Command::new(exe)
        .arg("--snapshot")
        .arg(&manifest)
        .arg("--frames")
        .arg("1")
        .output()
        .expect("spawn gs-player");
    assert!(
        !output.status.success(),
        "stdout={} stderr={}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(stderr.contains("REJECT"), "stderr={stderr}");
}

#[test]
fn player_bin_ok_headless() {
    let Some(exe) = player_exe() else {
        return;
    };
    let tmp = TempDir::new().expect("temp");
    let manifest = write_play_snapshot(tmp.path(), &scene_one_cam_one_sprite());
    let output = Command::new(exe)
        .arg("--snapshot")
        .arg(&manifest)
        .arg("--headless")
        .arg("--frames")
        .arg("2")
        .output()
        .expect("spawn gs-player");
    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(output.status.success(), "stdout={stdout} stderr={stderr}");
    assert!(stdout.contains("OK"), "stdout={stdout}");
    assert!(stdout.contains("p-000001"), "stdout={stdout}");
    assert!(stdout.contains("frames=2"), "stdout={stdout}");
}

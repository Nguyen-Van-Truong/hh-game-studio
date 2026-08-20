//! WP-M4-1 player half: long-lived `PhysicsHost` so Rapier velocity persists.

use std::collections::BTreeMap;
use std::fs;
use std::net::{IpAddr, Ipv4Addr, SocketAddr};
use std::path::Path;

use gs_player::{
    build_snapshot, read_player_file, run_headless_frames, ControlClient, ControlConfig,
    ControlServer, PlaySource, SnapshotRequest,
};
use gs_scene::{
    format_entity_id, Camera2D, Collider2D, ColliderShape, Entity, Name, RigidBody2D, Scene,
    Transform2D,
};
use serde_json::{json, Value};
use tempfile::TempDir;

const BOX_ID: u64 = 3;
const START_Y: f32 = 6.0;
/// Isolated (ephemeral) steps drop ~0.04 over 30 frames; persistent velocity
/// drops ~1.2. Anything above this is clearly accumulated motion.
const PERSIST_DROP: f32 = 0.5;
const DETERMINISM_EPS: f32 = 1e-4;

fn bind() -> SocketAddr {
    SocketAddr::new(IpAddr::V4(Ipv4Addr::LOCALHOST), 0)
}

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

fn rigid(id: u64, x: f32, y: f32, kind: &str, shape: ColliderShape) -> Entity {
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
        is_sensor: false,
        offset: [0.0, 0.0],
        layer: 1,
        mask: u32::MAX,
        friction: 0.5,
        restitution: 0.0,
    });
    entity
}

fn fall_scene() -> Scene {
    let mut scene = Scene::default();
    for entity in [
        camera(),
        rigid(
            2,
            0.0,
            0.0,
            "static",
            ColliderShape::Box { w: 40.0, h: 1.0 },
        ),
        rigid(
            BOX_ID,
            0.0,
            START_Y,
            "dynamic",
            ColliderShape::Box { w: 1.0, h: 1.0 },
        ),
    ] {
        scene.entities.insert(entity.id, entity);
    }
    scene
}

fn build_fall_snapshot(root: &Path, play_id: &str) -> gs_player::BuiltSnapshot {
    let req = SnapshotRequest {
        play_id: play_id.into(),
        document_revision: "r-000001".into(),
        engine_ver: "0.1.0-m4-1".into(),
        protocol_ver: "1.0".into(),
        seed: 42,
        created_at: "2026-08-17T00:00:00Z".into(),
        actor: "act_test".into(),
        scene: fall_scene().to_canonical_value(),
        project_settings: json!({
            "fixed_dt": 1.0 / 60.0,
            "ppu": 16,
            "schema_version": 1
        }),
        input_map: json!({ "actions": [] }),
        scripts: BTreeMap::new(),
        assets: BTreeMap::new(),
    };
    build_snapshot(root, &req).expect("build snapshot")
}

fn no_render() -> ControlConfig {
    ControlConfig {
        no_render: true,
        ..ControlConfig::default()
    }
}

fn entity_y(dump: &Value, id: u64) -> f32 {
    let want = format_entity_id(id);
    let entities = dump["entities"].as_array().expect("entities");
    let entity = entities
        .iter()
        .find(|e| e["id"] == want)
        .unwrap_or_else(|| panic!("missing {want} in {dump}"));
    entity["transform"]["y"].as_f64().expect("y") as f32
}

fn read_world_dump(client: &mut ControlClient, play_id: &str) -> Value {
    let dump = client.world_dump(play_id).expect("world_dump");
    let path = dump["path"].as_str().expect("path");
    let text = fs::read_to_string(path).expect("read dump");
    serde_json::from_str(&text).expect("dump json")
}

/// One play session: `play.step_frames` 1, then 29 more (30 total).
fn play_step_ys(play_id: &str) -> (f32, f32) {
    let tmp = TempDir::new().expect("temp");
    let built = build_fall_snapshot(tmp.path(), play_id);
    let handle = ControlServer::start_with_config(
        PlaySource::Snapshot(built.manifest_path),
        bind(),
        Some(tmp.path().to_path_buf()),
        no_render(),
    )
    .expect("control");
    let path = handle.player_json_path().expect("player.json");
    let file = read_player_file(path).expect("read player.json");
    let mut client = ControlClient::connect_player_file(&file).expect("hello");
    client.step_frames(1).expect("play.step_frames 1");
    let y1 = entity_y(&read_world_dump(&mut client, &file.play_id), BOX_ID);
    client.step_frames(29).expect("play.step_frames 29");
    let y30 = entity_y(&read_world_dump(&mut client, &file.play_id), BOX_ID);
    let _ = client.stop(false);
    (y1, y30)
}

#[test]
fn play_step_frames_dynamic_box_keeps_falling() {
    let (y1, y30) = play_step_ys("p-m4-1-a");
    assert!(
        y30 < y1 - PERSIST_DROP,
        "y must keep falling across frames (persistent Rapier velocity); y1={y1} y30={y30}"
    );
    assert!(
        y30 > 0.5,
        "box should still be above the ground after 30 frames, y30={y30}"
    );

    let (y1_b, y30_b) = play_step_ys("p-m4-1-b");
    assert!(
        (y1 - y1_b).abs() < DETERMINISM_EPS && (y30 - y30_b).abs() < DETERMINISM_EPS,
        "same setup must match within {DETERMINISM_EPS}: ({y1},{y30}) vs ({y1_b},{y30_b})"
    );
}

#[test]
fn headless_frames_dynamic_box_keeps_falling() {
    let tmp = TempDir::new().expect("temp");
    let built = build_fall_snapshot(tmp.path(), "p-m4-1-headless");
    let one = run_headless_frames(&built.manifest_path, 1).expect("1 frame");
    let thirty = run_headless_frames(&built.manifest_path, 30).expect("30 frames");
    let y1 = one
        .snapshot
        .items
        .iter()
        .find(|item| item.entity_id == BOX_ID)
        .map(|item| item.y)
        .expect("box after 1");
    let y30 = thirty
        .snapshot
        .items
        .iter()
        .find(|item| item.entity_id == BOX_ID)
        .map(|item| item.y)
        .expect("box after 30");
    assert!(
        y30 < y1 - PERSIST_DROP,
        "headless path must keep PhysicsHost; y1={y1} y30={y30}"
    );
}

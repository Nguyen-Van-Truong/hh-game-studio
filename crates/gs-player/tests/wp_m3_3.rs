//! WP-M3-3: long-lived ScriptHost in the player + hot reload between frames.

use std::collections::BTreeMap;
use std::fs;
use std::net::{IpAddr, Ipv4Addr, SocketAddr};
use std::path::Path;

use gs_player::{
    build_snapshot, read_player_file, run_headless_frames, ControlClient, ControlConfig,
    ControlServer, PlaySource, SnapshotRequest,
};
use gs_runtime_core::World;
use gs_scene::{
    format_entity_id, AssetRef, Camera2D, Collider2D, ColliderShape, Entity, Name, Scene, Script,
    Sprite, Tags, Transform2D, DOOR_SCRIPT_SOURCE,
};
use serde_json::{json, Value};
use tempfile::TempDir;

const DOOR_ID: u64 = 42;
const RELOAD_MOVE: &str = r#"
local M = {}
function M.on_update(self)
  gs.set_pos(self.id, 9, 9)
end
return M
"#;

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
        value: "MainCamera".into(),
    });
    entity.transform = Some(transform_at(0.0, 0.0));
    entity.extra.camera = Some(Camera2D {
        ortho_height: 10.0,
        active: true,
    });
    entity
}

fn door_entity() -> Entity {
    let mut entity = Entity::new(DOOR_ID, None, 1);
    entity.name = Some(Name {
        value: "door_1".into(),
    });
    entity.tags = Some(Tags {
        values: vec!["door".into(), "interactive".into()],
    });
    entity.transform = Some(Transform2D {
        x: 4.5,
        y: 2.0,
        rot: 0.0,
        sx: 1.0,
        sy: 1.0,
        z_index: 10,
    });
    entity.extra.sprite = Some(Sprite {
        asset: AssetRef {
            id: "a_000007".into(),
        },
        color: [1.0, 1.0, 1.0, 1.0],
        flip_x: false,
        flip_y: false,
        pivot: [0.5, 0.0],
    });
    entity.extra.collider = Some(Collider2D {
        shape: ColliderShape::Box { w: 1.0, h: 2.0 },
        is_sensor: false,
        offset: [0.0, 1.0],
        layer: 1,
        mask: u32::MAX,
        friction: 0.5,
        restitution: 0.0,
    });
    let mut props = BTreeMap::new();
    props.insert("locked".into(), json!(true));
    props.insert("key_tag".into(), json!("key_gold"));
    props.insert("open_sprite".into(), json!({ "$asset": "a_000008" }));
    entity.extra.script = Some(Script {
        file: "scripts/door.luau".into(),
        props,
    });
    entity
}

fn player() -> Entity {
    let mut entity = Entity::new(99, None, 2);
    entity.name = Some(Name {
        value: "player".into(),
    });
    entity.tags = Some(Tags {
        values: vec!["player".into(), "key_gold".into()],
    });
    entity.transform = Some(transform_at(4.5, 2.0));
    entity
}

fn door_scene() -> Scene {
    let mut scene = Scene::default();
    for entity in [camera(), door_entity(), player()] {
        scene.entities.insert(entity.id, entity);
    }
    scene
}

fn camera_world() -> World {
    let mut scene = Scene::default();
    scene.entities.insert(1, camera());
    World::from_scene(scene, 7)
}

fn build_door_snapshot(root: &Path) -> gs_player::BuiltSnapshot {
    let mut scripts = BTreeMap::new();
    scripts.insert(
        "door.luau".to_string(),
        DOOR_SCRIPT_SOURCE.as_bytes().to_vec(),
    );
    let req = SnapshotRequest {
        play_id: "p-m3-3".into(),
        document_revision: "r-000001".into(),
        engine_ver: "0.1.0-m3-3".into(),
        protocol_ver: "1.0".into(),
        seed: 1,
        created_at: "2026-08-17T00:00:00Z".into(),
        actor: "act_test".into(),
        scene: door_scene().to_canonical_value(),
        project_settings: json!({
            "fixed_dt": 1.0 / 60.0,
            "ppu": 16,
            "schema_version": 1
        }),
        input_map: json!({ "actions": [] }),
        scripts,
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

fn door_transform(dump: &Value) -> (f32, f32) {
    let id = format_entity_id(DOOR_ID);
    let entities = dump["entities"].as_array().expect("entities");
    let door = entities
        .iter()
        .find(|e| e["id"] == id)
        .unwrap_or_else(|| panic!("missing {id} in {dump}"));
    let x = door["transform"]["x"].as_f64().expect("x") as f32;
    let y = door["transform"]["y"].as_f64().expect("y") as f32;
    (x, y)
}

fn read_world_dump(client: &mut ControlClient, play_id: &str) -> Value {
    let dump = client.world_dump(play_id).expect("world_dump");
    let path = dump["path"].as_str().expect("path");
    let text = fs::read_to_string(path).expect("read dump");
    serde_json::from_str(&text).expect("dump json")
}

#[test]
fn snapshot_door_script_loads_and_stays_locked() {
    let tmp = TempDir::new().expect("temp");
    let built = build_door_snapshot(tmp.path());
    let report = run_headless_frames(&built.manifest_path, 2).expect("headless");
    assert_eq!(report.frames, 2);
    assert!(
        report
            .snapshot
            .items
            .iter()
            .any(|item| item.entity_id == DOOR_ID),
        "door sprite missing: {:?}",
        report.snapshot.items
    );

    let handle = ControlServer::start_with_config(
        PlaySource::Snapshot(built.manifest_path.clone()),
        bind(),
        Some(tmp.path().to_path_buf()),
        no_render(),
    )
    .expect("control");
    let path = handle.player_json_path().expect("player.json");
    let file = read_player_file(path).expect("read player.json");
    let mut client = ControlClient::connect_player_file(&file).expect("hello");
    client.step_frames(1).expect("play.step");
    let dump = read_world_dump(&mut client, &file.play_id);
    let (x, y) = door_transform(&dump);
    assert!(
        (x - 4.5).abs() < 0.01 && (y - 2.0).abs() < 0.01,
        "door should stay locked/unmoved, got {x},{y}"
    );
    assert!(client.status().expect("status").alive);
    let _ = client.stop(false);
}

#[test]
fn script_reload_applies_between_frames() {
    let tmp = TempDir::new().expect("temp");
    let built = build_door_snapshot(tmp.path());
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
    client.step_frames(1).expect("first step");
    let queued = client
        .script_reload(
            Some(&file.play_id),
            None,
            Some(RELOAD_MOVE),
            Some(&format_entity_id(DOOR_ID)),
        )
        .expect("script.reload");
    assert_eq!(queued["ok"], true);
    client.step_frames(1).expect("step after reload");
    let dump = read_world_dump(&mut client, &file.play_id);
    let (x, y) = door_transform(&dump);
    assert!(
        (x - 9.0).abs() < 0.01 && (y - 9.0).abs() < 0.01,
        "expected door at 9,9 after reload, got {x},{y}"
    );
    let _ = client.stop(false);
}

#[test]
fn script_reload_bad_source_keeps_player_alive() {
    let tmp = TempDir::new().expect("temp");
    let built = build_door_snapshot(tmp.path());
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
    client.step_frames(1).expect("first step");
    client
        .script_reload(
            Some(&file.play_id),
            None,
            Some(r#"error("bad")"#),
            Some(&format_entity_id(DOOR_ID)),
        )
        .expect("queue bad reload");
    let after = client.step_frames(1).expect("step after bad reload");
    assert!(after.alive, "player must survive a broken reload");
    assert!(!handle.is_stopped());
    let dump = read_world_dump(&mut client, &file.play_id);
    let (x, y) = door_transform(&dump);
    assert!(
        (x - 4.5).abs() < 0.01 && (y - 2.0).abs() < 0.01,
        "previous door behavior should remain, got {x},{y}"
    );
    let _ = client.stop(false);
}

#[test]
fn play_source_world_boxed_starts() {
    let source = PlaySource::World(Box::new(camera_world()));
    let handle = ControlServer::start(source, bind()).expect("boxed World starts");
    let after = handle.step_frames(1).expect("step boxed world");
    assert_eq!(after.frame, 1);
    assert!(after.alive);
}

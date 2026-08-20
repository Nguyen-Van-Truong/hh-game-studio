//! WP-M3-4 player half: load `input-map.json` and `input.inject` → `gs.action`.

use std::collections::BTreeMap;
use std::fs;
use std::net::{IpAddr, Ipv4Addr, SocketAddr};
use std::path::Path;

use gs_player::{
    build_snapshot, read_player_file, ControlClient, ControlConfig, ControlServer, PlaySource,
    SnapshotRequest,
};
use gs_scene::{format_entity_id, Camera2D, Entity, Name, Scene, Script, Transform2D};
use serde_json::{json, Value};
use tempfile::TempDir;

const MOVER_ID: u64 = 2;
const MOVER_SCRIPT: &str = r#"
local M = {}
function M.on_update(self)
  local _ = gs.action("nope")
  gs.set_pos(self.id, gs.action("move_x"), 0)
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

fn mover_entity() -> Entity {
    let mut entity = Entity::new(MOVER_ID, None, 1);
    entity.name = Some(Name {
        value: "mover".into(),
    });
    entity.transform = Some(transform_at(0.0, 0.0));
    entity.extra.script = Some(Script {
        file: "scripts/mover.luau".into(),
        props: BTreeMap::new(),
    });
    entity
}

fn mover_scene() -> Scene {
    let mut scene = Scene::default();
    for entity in [camera(), mover_entity()] {
        scene.entities.insert(entity.id, entity);
    }
    scene
}

fn build_mover_snapshot(root: &Path) -> gs_player::BuiltSnapshot {
    let mut scripts = BTreeMap::new();
    scripts.insert("mover.luau".to_string(), MOVER_SCRIPT.as_bytes().to_vec());
    let req = SnapshotRequest {
        play_id: "p-m3-4".into(),
        document_revision: "r-000001".into(),
        engine_ver: "0.1.0-m3-4".into(),
        protocol_ver: "1.0".into(),
        seed: 1,
        created_at: "2026-08-17T00:00:00Z".into(),
        actor: "act_test".into(),
        scene: mover_scene().to_canonical_value(),
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

fn mover_x(dump: &Value) -> f32 {
    let id = format_entity_id(MOVER_ID);
    let entities = dump["entities"].as_array().expect("entities");
    let mover = entities
        .iter()
        .find(|e| e["id"] == id)
        .unwrap_or_else(|| panic!("missing {id} in {dump}"));
    mover["transform"]["x"].as_f64().expect("x") as f32
}

fn read_world_dump(client: &mut ControlClient, play_id: &str) -> Value {
    let dump = client.world_dump(play_id).expect("world_dump");
    let path = dump["path"].as_str().expect("path");
    let text = fs::read_to_string(path).expect("read dump");
    serde_json::from_str(&text).expect("dump json")
}

fn start_client(tmp: &TempDir) -> (gs_player::ControlHandle, ControlClient, String) {
    let built = build_mover_snapshot(tmp.path());
    let handle = ControlServer::start_with_config(
        PlaySource::Snapshot(built.manifest_path),
        bind(),
        Some(tmp.path().to_path_buf()),
        no_render(),
    )
    .expect("control");
    let path = handle.player_json_path().expect("player.json");
    let file = read_player_file(path).expect("read player.json");
    let client = ControlClient::connect_player_file(&file).expect("hello");
    (handle, client, file.play_id)
}

#[test]
fn input_inject_move_x_sets_entity_x() {
    let tmp = TempDir::new().expect("temp");
    let (_handle, mut client, play_id) = start_client(&tmp);
    let queued = client
        .input_inject(
            Some(&play_id),
            json!([{ "frame_offset": 0, "action": "move_x", "value": 1 }]),
        )
        .expect("input.inject");
    assert_eq!(queued["ok"], true);
    client.step_frames(1).expect("play.step_frames");
    let dump = read_world_dump(&mut client, &play_id);
    let x = mover_x(&dump);
    assert!(
        (x - 1.0).abs() < 0.01,
        "expected x == 1 after inject move_x=1, got {x}"
    );
    assert!(client.status().expect("status").alive);
    let _ = client.stop(false);
}

#[test]
fn missing_inject_keeps_x_zero_and_unknown_action_is_safe() {
    let tmp = TempDir::new().expect("temp");
    let (handle, mut client, play_id) = start_client(&tmp);
    let after = client.step_frames(1).expect("play.step_frames");
    assert!(after.alive, "gs.action(\"nope\") must not crash the player");
    assert!(!handle.is_stopped());
    let dump = read_world_dump(&mut client, &play_id);
    let x = mover_x(&dump);
    assert!(
        x.abs() < 0.01,
        "missing inject should leave x at 0, got {x}"
    );
    assert!(handle.last_error().is_none());
    let _ = client.stop(false);
}

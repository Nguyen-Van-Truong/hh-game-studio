//! WP-M2-4: snapshot isolation, copy_to_scene, GC, live-view data.

use std::path::Path;

use gs_editor::{gc_play_snapshots, start, RpcError};
use serde_json::{json, Value};
use tempfile::TempDir;
use ulid::Ulid;

fn app_code(err: &RpcError) -> &str {
    err.data.as_ref().map(|d| d.app_code.as_str()).unwrap_or("")
}

fn cid() -> String {
    Ulid::new().to_string()
}

fn open_project(agent: &mut gs_editor::AgentClient, path: &Path) {
    agent
        .call("project.open", json!({ "path": path.to_string_lossy() }))
        .expect("project.open");
}

fn spawn_named(agent: &mut gs_editor::AgentClient, name: &str) -> String {
    agent
        .call(
            "entity.spawn",
            json!({
                "command_id": cid(),
                "scene_id": "s_main",
                "name": name,
            }),
        )
        .expect("entity.spawn")["spawned_ids"][0]
        .as_str()
        .expect("id")
        .to_owned()
}

fn set_transform(agent: &mut gs_editor::AgentClient, id: &str, x: f64, y: f64, rot: f64) {
    agent
        .call(
            "component.set",
            json!({
                "command_id": cid(),
                "id": id,
                "type": "Transform2D",
                "patch": { "x": x, "y": y, "rot": rot, "sx": 2.0, "sy": 2.0 },
            }),
        )
        .expect("component.set Transform2D");
}

fn revision(agent: &mut gs_editor::AgentClient) -> String {
    agent.call("scene.stats", json!({})).expect("scene.stats")["revision"]
        .as_str()
        .expect("revision")
        .to_owned()
}

fn play_start(agent: &mut gs_editor::AgentClient) -> Value {
    agent
        .call(
            "play.start",
            json!({ "headless": true, "command_id": cid() }),
        )
        .expect("play.start")
}

fn read_world_dump(agent: &mut gs_editor::AgentClient, play_id: &str) -> Value {
    let dump = agent
        .call("obs.world_dump", json!({ "play_id": play_id }))
        .expect("obs.world_dump");
    let path = dump["path"].as_str().expect("path");
    serde_json::from_str(&std::fs::read_to_string(path).expect("read dump")).expect("dump json")
}

fn transform_xy(agent: &mut gs_editor::AgentClient, id: &str) -> (f64, f64, f64) {
    let value = agent
        .call("component.get", json!({ "id": id, "type": "Transform2D" }))
        .expect("component.get")["value"]
        .clone();
    (
        value["x"].as_f64().expect("x"),
        value["y"].as_f64().expect("y"),
        value["rot"].as_f64().unwrap_or(0.0),
    )
}

#[test]
fn play_start_then_document_spawn_does_not_change_player_dump_count() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());
    let _frozen = spawn_named(&mut agent, "frozen");

    let started = play_start(&mut agent);
    let play_id = started["play_id"].as_str().expect("play_id").to_owned();
    let before = read_world_dump(&mut agent, &play_id);
    let count = before["entity_count"].as_u64().expect("count");
    assert_eq!(count, 1);

    let _after = spawn_named(&mut agent, "after_play");
    let stats = agent.call("scene.stats", json!({})).expect("stats");
    assert_eq!(stats["entity_count"].as_u64(), Some(2));

    let after = read_world_dump(&mut agent, &play_id);
    assert_eq!(
        after["entity_count"].as_u64(),
        Some(count),
        "player dump must stay frozen after document spawn"
    );

    let _ = agent.call("play.stop", json!({})).expect("stop");
}

#[test]
fn copy_to_scene_applies_play_transform_to_document() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());
    let id = spawn_named(&mut agent, "hero");
    set_transform(&mut agent, &id, 3.0, 4.0, 0.25);

    let started = play_start(&mut agent);
    let play_id = started["play_id"].as_str().expect("play_id").to_owned();

    set_transform(&mut agent, &id, 99.0, 88.0, 1.0);
    let (x, y, _) = transform_xy(&mut agent, &id);
    assert_eq!((x, y), (99.0, 88.0));

    let rev = revision(&mut agent);
    let copied = agent
        .call(
            "runtime.copy_to_scene",
            json!({
                "command_id": cid(),
                "play_id": play_id,
                "entity_ids": [id],
                "expected_revision": rev,
            }),
        )
        .expect("copy_to_scene");
    assert!(copied.get("token").is_none());
    let copied_ids = copied["copied"].as_array().expect("copied");
    assert_eq!(copied_ids.len(), 1);

    let (x, y, rot) = transform_xy(&mut agent, &id);
    assert_eq!(x, 3.0);
    assert_eq!(y, 4.0);
    assert!((rot - 0.25).abs() < 1e-5);

    let _ = agent.call("play.stop", json!({})).expect("stop");
}

#[test]
fn copy_to_scene_stale_revision_is_conflict() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());
    let id = spawn_named(&mut agent, "hero");
    set_transform(&mut agent, &id, 1.0, 2.0, 0.0);

    let started = play_start(&mut agent);
    let play_id = started["play_id"].as_str().expect("play_id").to_owned();
    let stale = revision(&mut agent);

    set_transform(&mut agent, &id, 7.0, 8.0, 0.0);
    let err = agent
        .call(
            "runtime.copy_to_scene",
            json!({
                "command_id": cid(),
                "play_id": play_id,
                "expected_revision": stale,
            }),
        )
        .expect_err("stale revision");
    assert_eq!(err.code, -32002);
    assert_eq!(app_code(&err), "E_CONFLICT");

    let _ = agent.call("play.stop", json!({})).expect("stop");
}

#[test]
fn copy_to_scene_without_player_is_not_found() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());
    let err = agent
        .call(
            "runtime.copy_to_scene",
            json!({
                "command_id": cid(),
                "expected_revision": "r-000000",
            }),
        )
        .expect_err("no player");
    assert_eq!(app_code(&err), "E_NOT_FOUND");
}

#[test]
fn gc_play_snapshots_keeps_at_most_ten_dirs() {
    let dir = TempDir::new().expect("tempdir");
    let play = dir.path().join(".gs").join("runtime").join("play");
    std::fs::create_dir_all(&play).expect("play root");
    for i in 0..11 {
        std::fs::create_dir_all(play.join(format!("p_fake_{i:02}"))).expect("fake play dir");
    }
    let deleted = gc_play_snapshots(dir.path());
    assert!(deleted >= 1, "GC should delete extras, deleted={deleted}");
    let left = std::fs::read_dir(&play)
        .expect("read play")
        .filter_map(|e| e.ok())
        .filter(|e| e.path().is_dir())
        .count();
    assert!(left <= 10, "kept {left} play dirs");
}

#[test]
fn live_view_snapshot_reuses_cache_within_100ms() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());
    let _ = spawn_named(&mut agent, "hero");
    let _ = play_start(&mut agent);

    let first = bus.ui().live_view_snapshot().expect("live view");
    let second = bus.ui().live_view_snapshot().expect("live view cached");
    assert_eq!(first["cached"], json!(false));
    assert_eq!(
        second["cached"],
        json!(true),
        "second call within 100ms must reuse the live-view cache"
    );
    assert_eq!(first["entity_count"], second["entity_count"]);
    assert!(first.get("token").is_none());
    assert!(second.get("token").is_none());

    let _ = agent.call("play.stop", json!({})).expect("stop");
}

//! WP-M2-3: editor forwards obs.* to player (I8).

use std::path::Path;

use gs_editor::{start, RpcError};
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

fn spawn_camera(agent: &mut gs_editor::AgentClient) -> String {
    let id = agent
        .call(
            "entity.spawn",
            json!({
                "command_id": cid(),
                "scene_id": "s_main",
                "name": "PlayCam",
            }),
        )
        .expect("entity.spawn")["spawned_ids"][0]
        .as_str()
        .expect("id")
        .to_owned();
    agent
        .call(
            "component.add",
            json!({
                "command_id": cid(),
                "id": id,
                "type": "Camera2D",
                "value": { "ortho_height": 10.0, "active": true },
            }),
        )
        .expect("camera");
    id
}

fn play_start(agent: &mut gs_editor::AgentClient) -> Value {
    spawn_camera(agent);
    agent
        .call(
            "play.start",
            json!({ "headless": true, "command_id": cid() }),
        )
        .expect("play.start")
}

fn contains_token(value: &Value, token: &str) -> bool {
    value.to_string().contains(token)
}

#[test]
fn step_then_obs_events_sees_frame_advanced() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

    let started = play_start(&mut agent);
    let play_id = started["play_id"].as_str().expect("play_id").to_owned();

    agent.call("play.pause", json!({})).expect("pause");
    let before = agent
        .call("obs.events", json!({ "play_id": play_id, "after_seq": 0 }))
        .expect("events before step");
    let after_seq = before["last_seq"].as_u64().unwrap_or(0);

    agent
        .call("play.step_frames", json!({ "n": 3 }))
        .expect("step");

    let events = agent
        .call(
            "obs.events",
            json!({
                "play_id": play_id,
                "after_seq": after_seq,
                "name": "FrameAdvanced"
            }),
        )
        .expect("obs.events");
    let list = events["events"].as_array().expect("events");
    assert_eq!(
        list.len(),
        3,
        "expected three FrameAdvanced events after step"
    );
    let first_frame = list[0]["frame"].as_u64().expect("frame");
    for (idx, event) in list.iter().enumerate() {
        assert_eq!(event["name"], "FrameAdvanced");
        assert_eq!(event["frame"].as_u64(), Some(first_frame + idx as u64));
    }

    let _ = agent.call("play.stop", json!({})).expect("stop");
}

#[test]
fn obs_world_dump_returns_existing_path() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

    let started = play_start(&mut agent);
    let play_id = started["play_id"].as_str().expect("play_id").to_owned();

    let dump = agent
        .call("obs.world_dump", json!({ "play_id": play_id }))
        .expect("obs.world_dump");
    let path = dump["path"].as_str().expect("path");
    assert!(Path::new(path).is_file(), "world dump file should exist");

    let _ = agent.call("play.stop", json!({})).expect("stop");
}

#[test]
fn obs_results_omit_player_token() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

    let started = play_start(&mut agent);
    let play_id = started["play_id"].as_str().expect("play_id").to_owned();
    let path = dir.path().join(".gs").join("runtime").join("player.json");
    let file: Value =
        serde_json::from_str(&std::fs::read_to_string(&path).expect("player.json")).expect("json");
    let token = file["token"].as_str().expect("token").to_owned();

    agent
        .call("play.step_frames", json!({ "n": 1 }))
        .expect("step");

    let events = agent
        .call("obs.events", json!({ "play_id": play_id, "after_seq": 0 }))
        .expect("obs.events");
    let dump = agent
        .call("obs.world_dump", json!({ "play_id": play_id }))
        .expect("obs.world_dump");
    let perf = agent
        .call("obs.perf", json!({ "play_id": play_id }))
        .expect("obs.perf");

    assert!(!contains_token(&events, &token));
    assert!(!contains_token(&dump, &token));
    assert!(!contains_token(&perf, &token));
    assert!(events.get("token").is_none());
    assert!(dump.get("token").is_none());

    let _ = agent.call("play.stop", json!({})).expect("stop");
}

#[test]
fn obs_without_player_is_not_found() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

    let err = agent
        .call("obs.events", json!({ "after_seq": 0 }))
        .expect_err("no player");
    assert_eq!(app_code(&err), "E_NOT_FOUND");
}

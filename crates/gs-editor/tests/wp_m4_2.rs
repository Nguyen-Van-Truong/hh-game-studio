//! WP-M4-2 editor half: tilemap.* + input.inject + scene.dump over the bus.

use std::path::Path;
use std::process::Command;
use std::time::Duration;

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

fn kill_leftover_players() {
    #[cfg(windows)]
    {
        let _ = Command::new("taskkill")
            .args(["/IM", "gs-player.exe", "/F"])
            .output();
    }
    #[cfg(not(windows))]
    {
        let _ = Command::new("pkill").args(["-9", "gs-player"]).output();
    }
}

fn spawn_camera(agent: &mut gs_editor::AgentClient) {
    let id = agent
        .call(
            "entity.spawn",
            json!({
                "command_id": cid(),
                "scene_id": "s_main",
                "name": "PlayCam",
            }),
        )
        .expect("entity.spawn camera")["spawned_ids"][0]
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
        .expect("Camera2D");
}

fn play_start_retry(agent: &mut gs_editor::AgentClient) -> Value {
    let mut last = None;
    for _ in 0..3 {
        match agent.call(
            "play.start",
            json!({ "headless": true, "command_id": cid() }),
        ) {
            Ok(value) => return value,
            Err(err) => {
                let msg = err.message.to_ascii_lowercase();
                let denied = msg.contains("access denied")
                    || msg.contains("os error 5")
                    || msg.contains("being used");
                last = Some(err);
                if !denied {
                    break;
                }
                kill_leftover_players();
                std::thread::sleep(Duration::from_millis(250));
            }
        }
    }
    panic!("play.start: {last:?}");
}

fn spawn_tilemap(agent: &mut gs_editor::AgentClient, cells: Value) -> String {
    agent
        .call(
            "entity.spawn",
            json!({
                "command_id": cid(),
                "scene_id": "s_main",
                "name": "map",
                "components": {
                    "Tilemap": {
                        "tileset": { "$asset": "a_000001" },
                        "cell_size": [1.0, 1.0],
                        "layers": [{ "name": "ground", "solid": true, "cells": cells }]
                    }
                }
            }),
        )
        .expect("entity.spawn Tilemap")["spawned_ids"][0]
        .as_str()
        .expect("id")
        .to_owned()
}

fn tilemap_cells(agent: &mut gs_editor::AgentClient, id: &str) -> Value {
    agent
        .call("component.get", json!({ "id": id, "type": "Tilemap" }))
        .expect("component.get Tilemap")["value"]["layers"][0]["cells"]
        .clone()
}

#[test]
fn agent_tilemap_fill_rect_shows_rle_and_revert_own_restores() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

    let id = spawn_tilemap(&mut agent, json!([[0, 0, 3, 1]]));
    assert_eq!(tilemap_cells(&mut agent, &id), json!([[0, 0, 3, 1]]));

    let filled = agent
        .call(
            "tilemap.fill_rect",
            json!({
                "command_id": cid(),
                "id": id,
                "layer": "ground",
                "x": 3,
                "y": 0,
                "w": 2,
                "h": 1,
                "tile": 1
            }),
        )
        .expect("tilemap.fill_rect");
    let txn_id = filled["txn_id"].as_str().expect("txn_id").to_owned();

    let after = tilemap_cells(&mut agent, &id);
    assert_eq!(
        after,
        json!([[0, 0, 5, 1]]),
        "fill_rect must merge into row RLE, got {after}"
    );

    agent
        .call(
            "undo.revert_own",
            json!({ "command_id": cid(), "txn_id": txn_id }),
        )
        .expect("undo.revert_own");
    assert_eq!(
        tilemap_cells(&mut agent, &id),
        json!([[0, 0, 3, 1]]),
        "revert_own must restore the original RLE"
    );
}

#[test]
fn agent_input_inject_requires_play_then_step_stays_alive() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

    let err = agent
        .call(
            "input.inject",
            json!({
                "actions": [{ "action": "move_x", "value": 1, "frame_offset": 0 }]
            }),
        )
        .expect_err("input.inject without play");
    assert_eq!(app_code(&err), "E_NOT_FOUND");

    spawn_camera(&mut agent);
    let started = play_start_retry(&mut agent);
    assert!(started.get("token").is_none());
    let play_id = started["play_id"].as_str().expect("play_id").to_owned();

    let injected = agent
        .call(
            "input.inject",
            json!({
                "play_id": play_id,
                "actions": [{ "action": "move_x", "value": 1, "frame_offset": 0 }]
            }),
        )
        .expect("input.inject");
    assert!(injected.get("token").is_none());

    agent
        .call("play.step_frames", json!({ "n": 1 }))
        .expect("play.step_frames");
    let status = agent.call("play.status", json!({})).expect("play.status");
    assert_eq!(status["alive"], json!(true));
    assert_eq!(status["play_id"], json!(play_id));
    assert!(status.get("token").is_none());

    let _ = agent.call("play.stop", json!({})).expect("play.stop");
}

#[test]
fn scene_dump_returns_entities_array() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

    let id = spawn_tilemap(&mut agent, json!([[0, 0, 1, 1]]));
    let dump = agent.call("scene.dump", json!({})).expect("scene.dump");
    let entities = dump["entities"]
        .as_array()
        .expect("scene.dump must return an entities array");
    assert!(
        entities
            .iter()
            .any(|e| e.get("id").and_then(Value::as_str) == Some(id.as_str())),
        "dump must include spawned entity {id}, got {dump}"
    );

    let found = agent
        .call("entity.find", json!({ "name": "map" }))
        .expect("entity.find");
    let ids = found["ids"].as_array().expect("ids");
    assert!(
        ids.iter().any(|v| v.as_str() == Some(id.as_str())),
        "entity.find by name must return {id}, got {found}"
    );
}

#[test]
fn agent_cannot_call_ui_only_methods() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

    let err = agent
        .call("undo.perform", json!({ "steps": 1 }))
        .expect_err("agent undo.perform must fail");
    assert_eq!(err.code, -32001);
    assert_eq!(app_code(&err), "E_UNAUTHORIZED");

    let err = agent
        .call(
            "script.buffer_set",
            json!({
                "path": "scripts/hello.luau",
                "source": "local typed = true\n",
            }),
        )
        .expect_err("agent buffer_set must fail");
    assert_eq!(err.code, -32001);
    assert_eq!(app_code(&err), "E_UNAUTHORIZED");
}

//! WP-M5-3: `.gtest.json` + `judge.run_test` + evidence bundle + `artifact.*`.
//!
//! Fail contract: `judge.run_test` returns RPC `E_ASSERT`; the bundle directory
//! is `error.data.reason` (`field` is `"path"`). `result.json` has `passed:false`.

use std::fs;
use std::path::{Path, PathBuf};
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

fn spawn_id(agent: &mut gs_editor::AgentClient, params: Value) -> String {
    agent.call("entity.spawn", params).expect("entity.spawn")["spawned_ids"][0]
        .as_str()
        .expect("spawned_ids[0]")
        .to_owned()
}

fn template_script(name: &str) -> String {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..");
    let primary = root.join("templates/2d-platformer/scripts").join(name);
    let fallback = root.join("templates/scripts").join(name);
    std::fs::read_to_string(&primary)
        .or_else(|_| std::fs::read_to_string(&fallback))
        .unwrap_or_else(|e| {
            panic!(
                "read {name} from {} or {}: {e}",
                primary.display(),
                fallback.display()
            )
        })
}

fn upload_script(agent: &mut gs_editor::AgentClient, path: &str, source: &str) {
    agent
        .call(
            "script.create",
            json!({ "command_id": cid(), "path": path }),
        )
        .expect("script.create");
    agent
        .call(
            "script.set_source",
            json!({
                "command_id": cid(),
                "path": path,
                "source": source,
            }),
        )
        .expect("script.set_source");
}

fn write_gtest(root: &Path, rel: &str, body: &Value) {
    let path = root.join(rel);
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).expect("mkdir tests");
    }
    fs::write(path, serde_json::to_vec_pretty(body).expect("gtest")).expect("write gtest");
}

fn read_result(bundle: &Path) -> Value {
    serde_json::from_str(&fs::read_to_string(bundle.join("result.json")).expect("result.json"))
        .expect("result json")
}

fn build_platformer(agent: &mut gs_editor::AgentClient) {
    let player_src = template_script("player_move.luau");
    let coin_src = template_script("coin.luau");
    assert!(coin_src.contains("CoinPicked"));
    upload_script(agent, "scripts/player_move.luau", &player_src);
    upload_script(agent, "scripts/coin.luau", &coin_src);

    let camera_id = spawn_id(
        agent,
        json!({
            "command_id": cid(),
            "scene_id": "s_main",
            "name": "camera",
            "components": {
                "Transform2D": { "x": 5.0, "y": 3.0, "rot": 0.0, "sx": 1.0, "sy": 1.0, "z_index": 0 }
            }
        }),
    );
    agent
        .call(
            "component.add",
            json!({
                "command_id": cid(),
                "id": camera_id,
                "type": "Camera2D",
                "value": { "ortho_height": 12.0, "active": true },
            }),
        )
        .expect("Camera2D");

    let floor_id = spawn_id(
        agent,
        json!({
            "command_id": cid(),
            "scene_id": "s_main",
            "name": "floor",
            "components": {
                "Transform2D": { "x": 0.0, "y": 0.0, "rot": 0.0, "sx": 1.0, "sy": 1.0, "z_index": 0 },
                "Tilemap": {
                    "tileset": { "$asset": "a_000001" },
                    "cell_size": [1.0, 1.0],
                    "layers": [{ "name": "ground", "solid": true, "cells": [] }]
                }
            }
        }),
    );
    agent
        .call(
            "tilemap.fill_rect",
            json!({
                "command_id": cid(),
                "id": floor_id,
                "layer": "ground",
                "x": 0,
                "y": 0,
                "w": 11,
                "h": 1,
                "tile": 1
            }),
        )
        .expect("tilemap.fill_rect");

    spawn_id(
        agent,
        json!({
            "command_id": cid(),
            "scene_id": "s_main",
            "name": "player",
            "components": {
                "Tags": { "values": ["player"] },
                "Transform2D": { "x": 2.0, "y": 2.2, "rot": 0.0, "sx": 1.0, "sy": 1.0, "z_index": 1 },
                "Sprite": {
                    "asset": { "$asset": "a_000002" },
                    "color": [0.2, 0.55, 0.95, 1.0],
                    "flip_x": false,
                    "flip_y": false,
                    "pivot": [0.5, 0.0]
                },
                "RigidBody2D": {
                    "kind": "dynamic",
                    "ccd": false,
                    "gravity_scale": 1.0,
                    "fixed_rotation": true,
                    "linear_damping": 0.0
                },
                "Collider2D": {
                    "shape": { "box": { "w": 1.0, "h": 1.0 } },
                    "is_sensor": false,
                    "offset": [0.0, 0.0],
                    "layer": 1,
                    "mask": 4294967295u32,
                    "friction": 0.5,
                    "restitution": 0.0
                },
                "Script": { "file": "scripts/player_move.luau", "props": {} }
            }
        }),
    );

    spawn_id(
        agent,
        json!({
            "command_id": cid(),
            "scene_id": "s_main",
            "name": "coin",
            "components": {
                "Tags": { "values": ["coin"] },
                "Transform2D": { "x": 3.4, "y": 1.5, "rot": 0.0, "sx": 1.0, "sy": 1.0, "z_index": 2 },
                "Sprite": {
                    "asset": { "$asset": "a_000003" },
                    "color": [1.0, 0.84, 0.2, 1.0],
                    "flip_x": false,
                    "flip_y": false,
                    "pivot": [0.5, 0.0]
                },
                "Collider2D": {
                    "shape": { "box": { "w": 0.5, "h": 0.5 } },
                    "is_sensor": true,
                    "offset": [0.0, 0.0],
                    "layer": 1,
                    "mask": 4294967295u32,
                    "friction": 0.0,
                    "restitution": 0.0
                },
                "Script": { "file": "scripts/coin.luau", "props": {} }
            }
        }),
    );

    agent
        .call(
            "inputmap.set",
            json!({
                "command_id": cid(),
                "actions": [
                    {
                        "name": "move_x",
                        "type": "axis",
                        "keys": [["A", -1.0], ["D", 1.0], ["Left", -1.0], ["Right", 1.0]],
                        "gamepad_axis": "left_x"
                    },
                    {
                        "name": "jump",
                        "type": "button",
                        "keys": ["Space", "W", "Up"],
                        "gamepad_button": "south"
                    }
                ]
            }),
        )
        .expect("inputmap.set");
}

fn run_test_retry(agent: &mut gs_editor::AgentClient, gtest_rel: &str) -> Result<Value, RpcError> {
    let mut last = None;
    for _ in 0..3 {
        match agent.call(
            "judge.run_test",
            json!({ "command_id": cid(), "gtest_rel": gtest_rel }),
        ) {
            Ok(value) => return Ok(value),
            Err(err) => {
                let msg = err.message.to_ascii_lowercase();
                let denied = msg.contains("access denied")
                    || msg.contains("os error 5")
                    || msg.contains("being used");
                if !denied {
                    return Err(err);
                }
                last = Some(err);
                kill_leftover_players();
                std::thread::sleep(Duration::from_millis(250));
            }
        }
    }
    Err(last.expect("retry"))
}

#[test]
fn coin_picked_run_test_passes_with_bundle() {
    kill_leftover_players();
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());
    build_platformer(&mut agent);

    write_gtest(
        dir.path(),
        "tests/coin_picked.gtest.json",
        &json!({
            "name": "coin_picked",
            "scene": "scenes/main.gscene.json",
            "seed": 7,
            "max_frames": 600,
            "asserts": [{"event": {"name": "CoinPicked"}}],
            "expect_diagnostics_max": 0
        }),
    );

    let result = run_test_retry(&mut agent, "tests/coin_picked.gtest.json").expect("run_test pass");
    assert_eq!(result["passed"], json!(true), "{result}");
    let path = result["path"].as_str().expect("path");
    let bundle = PathBuf::from(path);
    assert!(bundle.is_dir(), "bundle dir {path}");
    let report = read_result(&bundle);
    assert_eq!(report["passed"], json!(true), "{report}");
    assert!(bundle.join("world_dump.json").is_file(), "world dump");
    assert!(bundle.join("events.jsonl").is_file(), "event trace");
    let events = fs::read_to_string(bundle.join("events.jsonl")).expect("events");
    assert!(
        events.contains("CoinPicked"),
        "event trace must mention CoinPicked: {events}"
    );

    let listed = agent
        .call("artifact.list", json!({ "kind": "evidence" }))
        .expect("artifact.list");
    let arts = listed["artifacts"].as_array().expect("artifacts");
    assert!(
        arts.iter().any(|a| a["artifact_id"]
            .as_str()
            .is_some_and(|id| path.replace('\\', "/").contains(id) || id.contains("coin_picked"))),
        "list must see the bundle: {listed}"
    );
    let id = arts[0]["artifact_id"].as_str().expect("artifact_id");
    let got = agent
        .call("artifact.get", json!({ "artifact_id": id }))
        .expect("artifact.get");
    let file = PathBuf::from(got["path"].as_str().expect("get path"));
    assert!(file.is_file(), "get must return a file: {got}");
}

#[test]
fn never_happens_run_test_fails_with_bundle() {
    kill_leftover_players();
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());
    let camera_id = spawn_id(
        &mut agent,
        json!({
            "command_id": cid(),
            "scene_id": "s_main",
            "name": "camera",
        }),
    );
    agent
        .call(
            "component.add",
            json!({
                "command_id": cid(),
                "id": camera_id,
                "type": "Camera2D",
                "value": { "ortho_height": 10.0, "active": true },
            }),
        )
        .expect("Camera2D");

    write_gtest(
        dir.path(),
        "tests/never_happens.gtest.json",
        &json!({
            "name": "never_happens",
            "max_frames": 8,
            "asserts": [{"event": {"name": "NeverHappens"}}]
        }),
    );

    let err = run_test_retry(&mut agent, "tests/never_happens.gtest.json")
        .expect_err("NeverHappens must fail");
    assert_eq!(app_code(&err), "E_ASSERT", "{err:?}");
    let path = err
        .data
        .as_ref()
        .and_then(|d| d.reason.as_ref())
        .expect("bundle path in data.reason");
    let bundle = PathBuf::from(path);
    assert!(bundle.is_dir(), "fail bundle {path}");
    let report = read_result(&bundle);
    assert_eq!(report["passed"], json!(false), "{report}");
    assert!(bundle.join("world_dump.json").is_file());
    assert!(bundle.join("events.jsonl").is_file());
}

#[test]
fn artifact_list_get_gc_keeps_newest() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

    let ev = dir.path().join(".gs").join("runtime").join("evidence");
    fs::create_dir_all(ev.join("old-1")).expect("old");
    fs::write(ev.join("old-1/result.json"), b"{\"passed\":true}").expect("old result");
    std::thread::sleep(Duration::from_millis(30));
    fs::create_dir_all(ev.join("new-2")).expect("new");
    fs::write(ev.join("new-2/result.json"), b"{\"passed\":false}").expect("new result");

    let listed = agent
        .call("artifact.list", json!({ "kind": "evidence" }))
        .expect("list");
    assert_eq!(
        listed["artifacts"].as_array().map(|a| a.len()),
        Some(2),
        "{listed}"
    );
    let id = listed["artifacts"][0]["artifact_id"]
        .as_str()
        .expect("id")
        .to_owned();
    let got = agent
        .call("artifact.get", json!({ "artifact_id": id }))
        .expect("get");
    let file = PathBuf::from(got["path"].as_str().expect("path"));
    assert!(file.is_file(), "{got}");
    assert_eq!(
        file.file_name().and_then(|s| s.to_str()),
        Some("result.json")
    );

    let gc = agent
        .call(
            "artifact.gc",
            json!({ "command_id": cid(), "keep_last": 1 }),
        )
        .expect("gc");
    assert_eq!(gc["deleted"], json!(1), "{gc}");
    let listed = agent
        .call("artifact.list", json!({ "kind": "evidence" }))
        .expect("list after gc");
    assert_eq!(
        listed["artifacts"].as_array().map(|a| a.len()),
        Some(1),
        "{listed}"
    );
}

#[test]
fn gtest_rel_rejects_dotdot() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

    let err = agent
        .call(
            "judge.run_test",
            json!({ "command_id": cid(), "gtest_rel": "../secret.gtest.json" }),
        )
        .expect_err("I7");
    assert_eq!(app_code(&err), "E_PATH", "{err:?}");

    let err = agent
        .call(
            "judge.run_test",
            json!({
                "command_id": cid(),
                "gtest_rel": "tests/../../outside.gtest.json"
            }),
        )
        .expect_err("I7 nested");
    assert_eq!(app_code(&err), "E_PATH", "{err:?}");
}

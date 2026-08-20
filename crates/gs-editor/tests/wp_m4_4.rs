//! WP-M4-4: build the 2D platformer 100% through the editor bus, then play
//! until `CoinPicked` (or the coin is gone from `obs.world_dump`).

use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::Duration;

use gs_editor::start;
use serde_json::{json, Value};
use tempfile::TempDir;
use ulid::Ulid;

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
    let got = agent
        .call("script.get_source", json!({ "path": path }))
        .expect("script.get_source");
    assert_eq!(
        got["source"].as_str(),
        Some(source),
        "set_source must persist {path}"
    );
}

fn read_world_dump(agent: &mut gs_editor::AgentClient, play_id: &str) -> Value {
    let dump = agent
        .call("obs.world_dump", json!({ "play_id": play_id }))
        .expect("obs.world_dump");
    let path = dump["path"].as_str().expect("world_dump path");
    serde_json::from_str(&std::fs::read_to_string(path).expect("read dump")).expect("dump json")
}

fn dump_has_id(dump: &Value, id: &str) -> bool {
    dump["entities"]
        .as_array()
        .into_iter()
        .flatten()
        .any(|e| e.get("id").and_then(Value::as_str) == Some(id))
}

fn events_have_name(events: &Value, name: &str) -> bool {
    events["events"]
        .as_array()
        .into_iter()
        .flatten()
        .any(|e| e.get("name").and_then(Value::as_str) == Some(name))
        || events.to_string().contains(name)
}

fn inject_axis(
    agent: &mut gs_editor::AgentClient,
    play_id: &str,
    action: &str,
    value: f64,
    frames: u32,
) {
    let actions: Vec<Value> = (0..frames)
        .map(|frame_offset| {
            json!({
                "action": action,
                "value": value,
                "frame_offset": frame_offset,
            })
        })
        .collect();
    agent
        .call(
            "input.inject",
            json!({
                "play_id": play_id,
                "actions": actions,
            }),
        )
        .expect("input.inject");
}

#[test]
fn agent_builds_platformer_on_bus_and_picks_coin() {
    kill_leftover_players();

    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

    let player_src = template_script("player_move.luau");
    let coin_src = template_script("coin.luau");
    assert!(
        player_src.contains("gs.action(\"move_x\")"),
        "player_move.luau must be the template"
    );
    assert!(
        coin_src.contains("CoinPicked"),
        "coin.luau must emit CoinPicked"
    );
    upload_script(&mut agent, "scripts/player_move.luau", &player_src);
    upload_script(&mut agent, "scripts/coin.luau", &coin_src);

    let camera_id = spawn_id(
        &mut agent,
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
        &mut agent,
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
    let cells = agent
        .call(
            "component.get",
            json!({ "id": floor_id, "type": "Tilemap" }),
        )
        .expect("component.get Tilemap")["value"]["layers"][0]["cells"]
        .clone();
    assert_eq!(
        cells,
        json!([[0, 0, 11, 1]]),
        "fill_rect must write a solid row, got {cells}"
    );

    let player_id = spawn_id(
        &mut agent,
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

    let coin_id = spawn_id(
        &mut agent,
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

    let started = play_start_retry(&mut agent);
    assert!(started.get("token").is_none());
    let play_id = started["play_id"].as_str().expect("play_id").to_owned();

    // Land on the solid row before walking (timing is otherwise flaky).
    agent
        .call("play.step_frames", json!({ "n": 20 }))
        .expect("settle 20");

    inject_axis(&mut agent, &play_id, "move_x", 1.0, 24);
    agent
        .call("play.step_frames", json!({ "n": 24 }))
        .expect("walk 24");
    agent
        .call("play.step_frames", json!({ "n": 5 }))
        .expect("post-walk");

    let events = agent
        .call("obs.events", json!({ "play_id": play_id, "after_seq": 0 }))
        .expect("obs.events");
    let dump = read_world_dump(&mut agent, &play_id);
    let coin_picked = events_have_name(&events, "CoinPicked");
    let coin_gone = !dump_has_id(&dump, &coin_id);
    eprintln!(
        "WP-M4-4 CoinPicked observed={coin_picked} coin_gone={coin_gone} coin={coin_id} player={player_id}"
    );
    assert!(
        coin_picked,
        "WP-M4-4 requires CoinPicked on obs.events; coin_gone={coin_gone} events={events} dump={dump}"
    );
    assert!(
        coin_gone,
        "coin {coin_id} must be gone from world_dump after CoinPicked; dump={dump}"
    );
    assert!(
        dump_has_id(&dump, &player_id),
        "player {player_id} must still exist, dump={dump}"
    );

    let status = agent.call("play.status", json!({})).expect("play.status");
    assert_eq!(status["alive"], json!(true));
    assert_eq!(status["play_id"], json!(play_id));
    assert!(status.get("token").is_none());

    let _ = agent.call("play.stop", json!({})).expect("play.stop");
}

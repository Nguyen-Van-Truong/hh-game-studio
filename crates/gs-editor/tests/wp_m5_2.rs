//! WP-M5-2: editor forwards `judge.*` to the player (MASTER 4.2 / 6.3 / T5.2).

use std::path::Path;
use std::process::Command;
use std::time::Duration;

use gs_editor::{start, RpcError};
use serde_json::{json, Value};
use tempfile::TempDir;
use ulid::Ulid;

const EMIT_SRC: &str = r#"
local M = {}
function M.on_update(self)
  gs.emit("CoinPicked", { coin = self.id })
end
return M
"#;

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

fn upload_emit_script(agent: &mut gs_editor::AgentClient) {
    agent
        .call(
            "script.create",
            json!({ "command_id": cid(), "path": "scripts/emit.luau" }),
        )
        .expect("script.create");
    agent
        .call(
            "script.set_source",
            json!({
                "command_id": cid(),
                "path": "scripts/emit.luau",
                "source": EMIT_SRC,
            }),
        )
        .expect("script.set_source");
}

fn spawn_emitter(agent: &mut gs_editor::AgentClient) {
    agent
        .call(
            "entity.spawn",
            json!({
                "command_id": cid(),
                "scene_id": "s_main",
                "name": "coin",
                "components": {
                    "Transform2D": {
                        "x": 0.0, "y": 0.0, "rot": 0.0, "sx": 1.0, "sy": 1.0, "z_index": 0
                    },
                    "Script": { "file": "scripts/emit.luau", "props": {} }
                }
            }),
        )
        .expect("spawn emitter");
}

fn start_emit_play(agent: &mut gs_editor::AgentClient) -> String {
    spawn_camera(agent);
    upload_emit_script(agent);
    spawn_emitter(agent);
    let started = play_start_retry(agent);
    agent.call("play.pause", json!({})).expect("pause");
    started["play_id"].as_str().expect("play_id").to_owned()
}

fn read_world_dump(agent: &mut gs_editor::AgentClient, play_id: &str) -> Value {
    let dump = agent
        .call("obs.world_dump", json!({ "play_id": play_id }))
        .expect("obs.world_dump");
    let path = dump["path"].as_str().expect("world_dump path");
    serde_json::from_str(&std::fs::read_to_string(path).expect("read dump")).expect("dump json")
}

fn nudge_first_number(value: &mut Value, delta: f64) -> bool {
    match value {
        Value::Number(n) => {
            if let Some(x) = n.as_f64() {
                *value = json!(x + delta);
                return true;
            }
            false
        }
        Value::Array(items) => items.iter_mut().any(|item| nudge_first_number(item, delta)),
        Value::Object(map) => map.values_mut().any(|item| nudge_first_number(item, delta)),
        _ => false,
    }
}

#[test]
fn run_until_event_registers_then_sees_emit() {
    kill_leftover_players();
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());
    let play_id = start_emit_play(&mut agent);

    let hit = agent
        .call(
            "judge.run_until_event",
            json!({
                "play_id": play_id,
                "name": "CoinPicked",
                "timeout_frames": 8
            }),
        )
        .expect("judge.run_until_event");
    assert_eq!(hit["ok"], json!(true));
    assert_eq!(hit["name"], json!("CoinPicked"));
    assert!(hit["seq"].as_u64().unwrap_or(0) > 0, "{hit}");

    let _ = agent.call("play.stop", json!({})).expect("stop");
}

#[test]
fn run_until_event_missing_fails_gs_ec_35() {
    kill_leftover_players();
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());
    spawn_camera(&mut agent);
    let started = play_start_retry(&mut agent);
    agent.call("play.pause", json!({})).expect("pause");
    let play_id = started["play_id"].as_str().expect("play_id").to_owned();

    let err = agent
        .call(
            "judge.run_until_event",
            json!({
                "play_id": play_id,
                "name": "NeverHappens",
                "timeout_frames": 8
            }),
        )
        .expect_err("missing event must fail");
    assert_eq!(app_code(&err), "GS-EC-35", "{err:?}");

    let _ = agent.call("play.stop", json!({})).expect("stop");
}

#[test]
fn wait_event_sees_coin_picked_already_in_ring() {
    kill_leftover_players();
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());
    let play_id = start_emit_play(&mut agent);

    agent
        .call("play.step_frames", json!({ "n": 1 }))
        .expect("step so CoinPicked is in the ring");
    let events = agent
        .call(
            "obs.events",
            json!({ "play_id": play_id, "after_seq": 0, "name": "CoinPicked" }),
        )
        .expect("obs.events");
    assert!(
        events["events"]
            .as_array()
            .is_some_and(|list| !list.is_empty()),
        "ring must already hold CoinPicked: {events}"
    );

    let hit = agent
        .call(
            "judge.wait_event",
            json!({
                "play_id": play_id,
                "name": "CoinPicked",
                "after_seq": 0
            }),
        )
        .expect("judge.wait_event");
    assert_eq!(hit["name"], json!("CoinPicked"));

    let _ = agent.call("play.stop", json!({})).expect("stop");
}

#[test]
fn assert_world_epsilon_1e_minus_5_passes_and_1_fails() {
    kill_leftover_players();
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());
    spawn_camera(&mut agent);
    let started = play_start_retry(&mut agent);
    agent.call("play.pause", json!({})).expect("pause");
    let play_id = started["play_id"].as_str().expect("play_id").to_owned();

    let dump = read_world_dump(&mut agent, &play_id);
    let mut close = dump.clone();
    assert!(
        nudge_first_number(&mut close, 1e-5),
        "dump should contain a number: {dump}"
    );
    agent
        .call(
            "judge.assert_world",
            json!({
                "play_id": play_id,
                "expected": close,
                "epsilon": 1e-5
            }),
        )
        .expect("dumps that differ by 1e-5 must pass");

    let mut far = dump;
    assert!(nudge_first_number(&mut far, 1.0));
    let err = agent
        .call(
            "judge.assert_world",
            json!({
                "play_id": play_id,
                "expected": far,
                "epsilon": 1e-5
            }),
        )
        .expect_err("dumps that differ by 1.0 must fail");
    assert_eq!(app_code(&err), "E_ASSERT", "{err:?}");

    let _ = agent.call("play.stop", json!({})).expect("stop");
}

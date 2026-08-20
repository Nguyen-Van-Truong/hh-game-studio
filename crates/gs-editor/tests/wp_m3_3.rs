//! WP-M3-3 editor half: script.* bus, poll watcher, conflict, play reload.

use std::path::Path;
use std::process::Command;
use std::time::Duration;

use gs_editor::{start, RpcError};
use gs_scene::DEFAULT_SCRIPT_SOURCE;
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

#[test]
fn agent_script_create_get_set_and_revert_own() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

    let path = "scripts/hello.luau";
    agent
        .call(
            "script.create",
            json!({ "command_id": cid(), "path": path }),
        )
        .expect("script.create");

    let got = agent
        .call("script.get_source", json!({ "path": path }))
        .expect("get_source");
    assert_eq!(got["path"], json!(path));
    assert_eq!(got["source"].as_str(), Some(DEFAULT_SCRIPT_SOURCE));
    assert_eq!(got["conflict"], json!(false));

    let changed = "local after = true\n";
    let set = agent
        .call(
            "script.set_source",
            json!({
                "command_id": cid(),
                "path": path,
                "source": changed,
            }),
        )
        .expect("set_source");
    let txn_id = set["txn_id"].as_str().expect("txn_id").to_owned();

    let after = agent
        .call("script.get_source", json!({ "path": path }))
        .expect("get after set");
    assert_eq!(after["source"].as_str(), Some(changed));

    agent
        .call(
            "undo.revert_own",
            json!({ "command_id": cid(), "txn_id": txn_id }),
        )
        .expect("revert_own");
    let restored = agent
        .call("script.get_source", json!({ "path": path }))
        .expect("get after revert");
    assert_eq!(restored["source"].as_str(), Some(DEFAULT_SCRIPT_SOURCE));
}

#[test]
fn agent_cannot_call_script_buffer_set() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

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

#[test]
fn external_write_poll_ingests_when_not_dirty() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

    let path = "scripts/watched.luau";
    agent
        .call(
            "script.create",
            json!({ "command_id": cid(), "path": path }),
        )
        .expect("create");

    let disk = "local from_disk = true\n";
    std::fs::write(dir.path().join(path), disk).expect("external write");

    let poll = bus.ui().poll_script_watcher().expect("poll");
    let ingested = poll["ingested"].as_array().expect("ingested");
    assert!(
        ingested.iter().any(|v| v.as_str() == Some(path)),
        "expected ingest of {path}, got {poll}"
    );

    let got = agent
        .call("script.get_source", json!({ "path": path }))
        .expect("get after ingest");
    assert_eq!(got["source"].as_str(), Some(disk));

    bus.ui()
        .call("undo.perform", json!({}))
        .expect("undo ingest");
    let restored = agent
        .call("script.get_source", json!({ "path": path }))
        .expect("get after undo");
    assert_eq!(restored["source"].as_str(), Some(DEFAULT_SCRIPT_SOURCE));
}

#[test]
fn dirty_buffer_external_write_is_conflict_not_overwrite() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

    let path = "scripts/conflict.luau";
    agent
        .call(
            "script.create",
            json!({ "command_id": cid(), "path": path }),
        )
        .expect("create");

    let buffer = "local mine = true\n";
    bus.ui()
        .call(
            "script.buffer_set",
            json!({ "path": path, "source": buffer }),
        )
        .expect("buffer_set");

    let disk = "local theirs = true\n";
    std::fs::write(dir.path().join(path), disk).expect("external write");

    let poll = bus.ui().poll_script_watcher().expect("poll");
    assert!(
        poll["ingested"]
            .as_array()
            .is_some_and(|a| !a.iter().any(|v| v.as_str() == Some(path))),
        "dirty path must not ingest, got {poll}"
    );
    assert!(
        poll["conflicts"]
            .as_array()
            .is_some_and(|a| a.iter().any(|v| v.as_str() == Some(path))),
        "conflict must be visible on poll, got {poll}"
    );

    let listed = agent
        .call("script.conflicts", json!({}))
        .expect("agent can read conflicts");
    let rows = listed["conflicts"].as_array().expect("conflicts");
    assert!(
        rows.iter().any(|row| row["path"].as_str() == Some(path)
            && row["disk_source"].as_str() == Some(disk)
            && row["buffer_source"].as_str() == Some(buffer)),
        "agent must see conflict, got {listed}"
    );

    let got = agent
        .call("script.get_source", json!({ "path": path }))
        .expect("get during conflict");
    assert_eq!(got["source"].as_str(), Some(buffer));
    assert_eq!(got["conflict"], json!(true));
    assert_ne!(got["source"].as_str(), Some(disk));

    bus.ui()
        .call(
            "script.conflict_resolve",
            json!({ "path": path, "choice": "disk" }),
        )
        .expect("take disk");

    let after = agent
        .call("script.get_source", json!({ "path": path }))
        .expect("get after take-disk");
    assert_eq!(after["source"].as_str(), Some(disk));
    assert_eq!(after["conflict"], json!(false));
}

#[test]
fn set_source_while_playing_keeps_player_alive() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

    let path = "scripts/foo.luau";
    agent
        .call(
            "script.create",
            json!({ "command_id": cid(), "path": path }),
        )
        .expect("create foo.luau");

    let spawned = agent
        .call(
            "entity.spawn",
            json!({
                "command_id": cid(),
                "scene_id": "s_main",
                "name": "scripted",
            }),
        )
        .expect("spawn");
    let id = spawned["spawned_ids"][0].as_str().expect("id").to_owned();
    agent
        .call(
            "component.set",
            json!({
                "command_id": cid(),
                "id": id,
                "type": "Script",
                "patch": { "file": path, "props": {} },
            }),
        )
        .expect("attach Script");

    let started = play_start_retry(&mut agent);
    assert!(started.get("token").is_none());
    let play_id = started["play_id"].as_str().expect("play_id").to_owned();

    agent
        .call(
            "script.set_source",
            json!({
                "command_id": cid(),
                "path": path,
                "source": "local M = {}\nfunction M.on_update(self, dt)\nend\nreturn M\n",
            }),
        )
        .expect("set_source while playing");

    let status = agent.call("play.status", json!({})).expect("status");
    assert_eq!(status["alive"], json!(true));
    assert_eq!(status["play_id"], json!(play_id));
    assert!(status.get("token").is_none());

    let _ = agent.call("play.stop", json!({}));
}

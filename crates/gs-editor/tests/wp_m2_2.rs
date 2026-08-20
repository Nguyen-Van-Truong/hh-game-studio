//! WP-M2-2: editor Play start/stop/status; agent goes through the bus (I8).
//! Tests do not open an eframe window.

use std::process::Command;
use std::time::{Duration, Instant};

use gs_editor::{start, RpcError};
use serde_json::{json, Value};
use tempfile::TempDir;
use ulid::Ulid;

fn app_code(err: &RpcError) -> &str {
    err.data.as_ref().map(|d| d.app_code.as_str()).unwrap_or("")
}

fn open_project(agent: &mut gs_editor::AgentClient, path: &std::path::Path) {
    agent
        .call("project.open", json!({ "path": path.to_string_lossy() }))
        .expect("project.open");
}

fn play_start(agent: &mut gs_editor::AgentClient) -> Value {
    agent
        .call(
            "play.start",
            json!({ "headless": true, "command_id": Ulid::new().to_string() }),
        )
        .expect("play.start")
}

fn contains_token(value: &Value, token: &str) -> bool {
    value.to_string().contains(token)
}

fn kill_pid(pid: u32) {
    #[cfg(windows)]
    {
        let _ = Command::new("taskkill")
            .args(["/PID", &pid.to_string(), "/F", "/T"])
            .output();
    }
    #[cfg(not(windows))]
    {
        let _ = Command::new("kill").args(["-9", &pid.to_string()]).output();
    }
}

fn wait_until<F: FnMut() -> bool>(timeout: Duration, mut pred: F) -> bool {
    let start = Instant::now();
    while start.elapsed() < timeout {
        if pred() {
            return true;
        }
        std::thread::sleep(Duration::from_millis(50));
    }
    pred()
}

#[test]
fn play_start_twice_is_player_running() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

    let first = play_start(&mut agent);
    let pid = first["pid"].as_u64().expect("pid") as u32;
    assert!(first["play_id"].as_str().is_some());
    assert!(first["snapshot_manifest"].as_str().is_some());

    let err = agent
        .call(
            "play.start",
            json!({ "headless": true, "command_id": Ulid::new().to_string() }),
        )
        .expect_err("second start");
    assert_eq!(err.code, -32000);
    assert_eq!(app_code(&err), "E_PLAYER_RUNNING");
    assert!(
        err.message.contains(&pid.to_string())
            || err
                .data
                .as_ref()
                .and_then(|d| d.reason.as_deref())
                .is_some_and(|r| r.contains(&pid.to_string())),
        "E_PLAYER_RUNNING must include pid, got {err:?}"
    );

    let _ = agent.call("play.stop", json!({})).expect("stop");
}

#[test]
fn play_start_same_command_id_does_not_spawn_second() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

    let command_id = Ulid::new().to_string();
    let first = agent
        .call(
            "play.start",
            json!({ "headless": true, "command_id": command_id }),
        )
        .expect("play.start");
    let play_id = first["play_id"].as_str().expect("play_id").to_owned();
    let pid = first["pid"].as_u64().expect("pid");

    let second = agent
        .call(
            "play.start",
            json!({ "headless": true, "command_id": command_id }),
        )
        .expect("dedup play.start");
    assert_eq!(second["play_id"], play_id);
    assert_eq!(second["pid"], pid);

    let status = agent.call("play.status", json!({})).expect("status");
    assert_eq!(status["alive"], json!(true));
    assert_eq!(status["play_id"], json!(play_id));

    let _ = agent.call("play.stop", json!({})).expect("stop");
}

#[test]
fn play_start_status_alive_then_stop() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

    let started = play_start(&mut agent);
    let play_id = started["play_id"].as_str().expect("play_id").to_owned();

    let status = agent.call("play.status", json!({})).expect("status");
    assert_eq!(status["alive"], json!(true));
    assert_eq!(status["play_id"], json!(play_id));
    assert!(status.get("token").is_none());

    let stopped = agent.call("play.stop", json!({})).expect("stop");
    assert!(stopped.get("token").is_none());
    assert!(
        stopped.get("exit_code").is_some() || stopped.get("alive") == Some(&json!(false)),
        "stop should return exit_report, got {stopped}"
    );

    let after = agent.call("play.status", json!({})).expect("status after");
    assert_eq!(after["alive"], json!(false));
}

#[test]
fn kill_player_bus_still_answers_ping() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

    let started = play_start(&mut agent);
    let pid = started["pid"].as_u64().expect("pid") as u32;
    kill_pid(pid);

    let dead = wait_until(Duration::from_secs(5), || {
        agent
            .call("play.status", json!({}))
            .ok()
            .and_then(|s| s.get("alive").and_then(Value::as_bool))
            == Some(false)
    });
    assert!(dead, "play.status should report not alive after kill");

    let ping = agent.call("session.ping", json!({})).expect("ping");
    assert_eq!(ping["ok"], json!(true));

    let status = agent.call("play.status", json!({})).expect("status");
    assert_eq!(status["alive"], json!(false));
}

#[test]
fn play_results_and_feed_omit_player_token() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

    let started = play_start(&mut agent);
    let path = dir.path().join(".gs").join("runtime").join("player.json");
    let file: Value =
        serde_json::from_str(&std::fs::read_to_string(&path).expect("player.json")).expect("json");
    let token = file["token"].as_str().expect("token").to_owned();
    assert!(token.len() >= 16);

    let status = agent.call("play.status", json!({})).expect("status");
    let feed = bus.ui().feed();
    let notes = bus.ui().notifications();
    let feed_json = serde_json::to_value(&feed).expect("feed");
    let notes_json = serde_json::to_value(&notes).expect("notes");

    assert!(!contains_token(&started, &token), "start leaked token");
    assert!(!contains_token(&status, &token), "status leaked token");
    assert!(!contains_token(&feed_json, &token), "feed leaked token");
    assert!(!contains_token(&notes_json, &token), "events leaked token");
    assert!(started.get("token").is_none());
    assert!(started.get("port").is_none());

    let stopped = agent.call("play.stop", json!({})).expect("stop");
    assert!(!contains_token(&stopped, &token), "stop leaked token");
}

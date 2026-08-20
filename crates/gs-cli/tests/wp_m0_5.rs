//! WP-M0-5 bus client tests. Uses in-process `gs_editor::start` (no window).

use gs_cli::{
    ensure_command_id, load_live_endpoint, pid_is_alive, read_endpoint_file, BusClient, Endpoint,
    ENDPOINT_REL,
};
use serde_json::json;
use tempfile::TempDir;

fn start_bus() -> (TempDir, gs_editor::BusHandle) {
    let dir = TempDir::new().expect("tempdir");
    let bus = gs_editor::start(dir.path()).expect("start bus");
    (dir, bus)
}

#[test]
fn hello_returns_actor_id() {
    let (dir, _bus) = start_bus();
    let client = BusClient::connect(dir.path()).expect("connect");
    assert!(
        client.actor_id().starts_with("act_"),
        "actor_id={}",
        client.actor_id()
    );
    assert_eq!(client.principal(), "agent");
    assert_eq!(client.host(), "127.0.0.1");
    assert!(client.port() > 0);
}

#[test]
fn spawn_after_project_open_succeeds() {
    let (dir, _bus) = start_bus();
    let mut client = BusClient::connect(dir.path()).expect("connect");
    client
        .call(
            "project.open",
            json!({ "path": dir.path().to_string_lossy() }),
        )
        .expect("project.open");
    let result = client
        .call(
            "entity.spawn",
            json!({
                "scene_id": "s_main",
                "name": "crate",
            }),
        )
        .expect("entity.spawn");
    assert!(
        result.get("revision").is_some() || result.get("spawned_ids").is_some(),
        "spawn result={result}"
    );
}

#[test]
fn missing_command_id_is_filled_with_ulid() {
    let (params, id) = ensure_command_id("entity.spawn", json!({"name": "anon"}));
    let id = id.expect("generated command_id");
    assert!(ulid::Ulid::from_string(&id).is_ok(), "not a ULID: {id}");
    assert_eq!(params["command_id"], id);

    let (dir, _bus) = start_bus();
    let mut client = BusClient::connect(dir.path()).expect("connect");
    client
        .call(
            "project.open",
            json!({ "path": dir.path().to_string_lossy() }),
        )
        .expect("project.open");
    let invoked = client
        .invoke(
            "entity.spawn",
            json!({
                "scene_id": "s_main",
                "name": "filled",
            }),
        )
        .expect("spawn without command_id must succeed after fill");
    let command_id = invoked.command_id.expect("invoke returns command_id");
    assert!(
        ulid::Ulid::from_string(&command_id).is_ok(),
        "not a ULID: {command_id}"
    );
    assert!(
        invoked.result.get("revision").is_some() || invoked.result.get("spawned_ids").is_some()
    );
}

#[test]
fn unknown_method_returns_rpc_error() {
    let (dir, _bus) = start_bus();
    let mut client = BusClient::connect(dir.path()).expect("connect");
    let err = client
        .call("no.such.method", json!({}))
        .expect_err("unknown method must be RpcError, not panic");
    assert_eq!(err.code, -32601);
}

#[test]
fn stale_pid_is_rejected_without_hang() {
    let dir = TempDir::new().expect("tempdir");
    let path = dir.path().join(ENDPOINT_REL);
    std::fs::create_dir_all(path.parent().expect("parent")).expect("mkdir");
    let dead = Endpoint::new("127.0.0.1", 1, "secret-must-not-leak", 4_294_967_294);
    assert!(!pid_is_alive(dead.pid));
    std::fs::write(
        &path,
        serde_json::to_vec_pretty(&dead).expect("serialize endpoint"),
    )
    .expect("write endpoint");

    let err = load_live_endpoint(dir.path()).expect_err("stale");
    let msg = err.to_string();
    assert!(
        msg.contains("stale") || msg.contains("not running"),
        "{msg}"
    );
    assert!(!msg.contains("secret-must-not-leak"));

    let debug = format!("{:?}", read_endpoint_file(&path).expect("read"));
    assert!(debug.contains("<redacted>"));
    assert!(!debug.contains("secret-must-not-leak"));

    let started = std::time::Instant::now();
    let connect_err = BusClient::connect(dir.path()).expect_err("stale connect");
    assert!(started.elapsed() < std::time::Duration::from_secs(2));
    assert!(!connect_err.to_string().contains("secret-must-not-leak"));
}

#[test]
fn token_absent_from_hello_debug_and_result() {
    let (dir, bus) = start_bus();
    let token = bus.endpoint().token().to_owned();
    assert!(!token.is_empty());
    let client = BusClient::connect(dir.path()).expect("connect");
    let debug = format!("{:?} {}", client.endpoint(), client.hello().result);
    let result = serde_json::to_string(&client.hello().result).expect("json");
    assert!(!debug.contains(&token), "token leaked into Debug/result");
    assert!(!result.contains(&token), "token leaked into hello result");
    assert!(result.contains(client.actor_id()));
}

//! WP-M0-4 required bus / authority / confirmation tests (no GPU window).

use gs_editor::{start, Badge, RpcError};
use serde_json::{json, Value};
use tempfile::TempDir;
use ulid::Ulid;

fn cid() -> String {
    Ulid::new().to_string()
}

fn open_project(agent: &mut gs_editor::AgentClient, path: &std::path::Path) -> Value {
    agent
        .call("project.open", json!({ "path": path.to_string_lossy() }))
        .expect("project.open")
}

fn spawn(agent: &mut gs_editor::AgentClient, name: &str, command_id: &str) -> Value {
    agent
        .call(
            "entity.spawn",
            json!({
                "command_id": command_id,
                "scene_id": "s_main",
                "name": name,
            }),
        )
        .expect("entity.spawn")
}

fn entity_count(agent: &mut gs_editor::AgentClient) -> usize {
    let stats = agent.call("scene.stats", json!({})).expect("scene.stats");
    stats["entity_count"].as_u64().expect("entity_count") as usize
}

fn app_code(err: &RpcError) -> &str {
    err.data.as_ref().map(|d| d.app_code.as_str()).unwrap_or("")
}

#[test]
fn agent_tcp_undo_perform_is_unauthorized() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    assert_eq!(agent.principal(), "agent");
    let err = agent
        .call("undo.perform", json!({ "steps": 1 }))
        .expect_err("agent undo.perform must fail");
    assert_eq!(err.code, -32001);
    assert_eq!(app_code(&err), "E_UNAUTHORIZED");
}

#[test]
fn retry_same_command_id_does_not_duplicate_entity() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());
    let command_id = cid();
    let first = spawn(&mut agent, "once", &command_id);
    let retry = spawn(&mut agent, "once", &command_id);
    assert_eq!(first["spawned_ids"], retry["spawned_ids"]);
    assert_eq!(first["txn_id"], retry["txn_id"]);
    assert_eq!(entity_count(&mut agent), 1);
}

#[test]
fn confirmation_reuse_and_changed_params_are_invalid() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

    let mut commands = Vec::new();
    for i in 0..21 {
        commands.push(json!({
            "method": "entity.spawn",
            "params": { "scene_id": "s_main", "name": format!("e{i}") },
        }));
    }
    let seed = agent
        .call(
            "transaction.execute",
            json!({
                "label": "seed-21",
                "command_id": cid(),
                "commands": commands,
            }),
        )
        .expect("seed");
    let ids: Vec<String> = seed["spawned_ids"]
        .as_array()
        .expect("spawned_ids")
        .iter()
        .map(|v| v.as_str().expect("id").to_owned())
        .collect();
    assert_eq!(ids.len(), 21);

    let first = agent
        .call("entity.destroy", json!({ "command_id": cid(), "ids": ids }))
        .expect("destroy hold");
    assert_eq!(first["status"], "pending_confirmation");
    let c1 = first["confirmation_id"].as_str().expect("c1").to_owned();
    assert_eq!(entity_count(&mut agent), 21);

    let mut reversed = ids.clone();
    reversed.reverse();
    let second = agent
        .call(
            "entity.destroy",
            json!({ "command_id": cid(), "ids": reversed }),
        )
        .expect("destroy hold changed params");
    let c2 = second["confirmation_id"].as_str().expect("c2").to_owned();
    assert_ne!(c1, c2);

    let reuse_old = bus
        .ui()
        .call("confirmation.approve", json!({ "confirmation_id": c1 }))
        .expect_err("changed params invalidates c1");
    assert!(reuse_old.code == -32000, "code={}", reuse_old.code);
    assert_eq!(app_code(&reuse_old), "E_NOT_FOUND");

    let approved = bus
        .ui()
        .call("confirmation.approve", json!({ "confirmation_id": c2 }))
        .expect("approve c2");
    assert!(approved.get("revision").is_some());
    assert_eq!(entity_count(&mut agent), 0);

    let reuse = bus
        .ui()
        .call("confirmation.approve", json!({ "confirmation_id": c2 }))
        .expect_err("reuse c2");
    assert_eq!(app_code(&reuse), "E_NOT_FOUND");
}

#[test]
fn token_does_not_appear_in_feed_or_event_fixture() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let token = bus.endpoint().token().to_owned();
    assert!(!token.is_empty());
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());
    spawn(&mut agent, "hero", &cid());

    let fixture = serde_json::to_string(&json!({
        "feed": bus.ui().feed(),
        "notifications": bus.ui().notifications(),
        "session": bus.ui().session_panel(),
        "heuristic": bus.ui().heuristic_log(),
    }))
    .expect("fixture json");

    assert!(
        !fixture.contains(&token),
        "GS-EC-45: bus token leaked into feed/event fixture"
    );
    assert!(fixture.contains("hero") || fixture.contains("entity.spawn"));
    assert!(bus
        .ui()
        .feed()
        .iter()
        .any(|e| e.badge == Badge::Agent && e.actor.starts_with("act_")));
}

#[test]
fn duplicate_client_name_gets_distinct_actor_ids() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let a = bus.connect_agent("same-label").expect("hello a");
    let b = bus.connect_agent("same-label").expect("hello b");
    assert_eq!(a.principal(), "agent");
    assert_eq!(b.principal(), "agent");
    assert_ne!(a.actor_id(), b.actor_id());
    assert!(a.actor_id().starts_with("act_"));
    assert!(b.actor_id().starts_with("act_"));
}

#[test]
fn pause_blocks_mutating_but_ping_still_works() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());
    spawn(&mut agent, "keep", &cid());

    bus.ui()
        .call(
            "session.pause_actor",
            json!({ "actor_id": agent.actor_id() }),
        )
        .expect("pause");

    let err = agent
        .call(
            "entity.spawn",
            json!({
                "command_id": cid(),
                "scene_id": "s_main",
                "name": "blocked",
            }),
        )
        .expect_err("paused spawn");
    assert_eq!(err.code, -32000);
    assert_eq!(app_code(&err), "E_PAUSED");

    let ping = agent.call("session.ping", json!({})).expect("ping");
    assert_eq!(ping["ok"], true);
    assert_eq!(entity_count(&mut agent), 1);
}

#[test]
fn human_ui_undo_perform_after_agent_spawn() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());
    spawn(&mut agent, "temp", &cid());
    assert_eq!(entity_count(&mut agent), 1);

    let ack = bus
        .ui()
        .call("undo.perform", json!({ "steps": 1 }))
        .expect("human_ui undo.perform");
    assert!(ack.get("revision").is_some());
    assert_eq!(entity_count(&mut agent), 0);
    assert!(bus
        .ui()
        .feed()
        .iter()
        .any(|e| e.badge == Badge::Human && e.label == "undo.perform"));
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

fn set_x(agent: &mut gs_editor::AgentClient, id: &str, x: f64) -> Result<Value, RpcError> {
    agent.call(
        "component.set",
        json!({
            "command_id": cid(),
            "id": id,
            "type": "Transform2D",
            "patch": { "x": x },
        }),
    )
}

#[test]
fn lock_then_other_actor_component_set_is_locked() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut owner = bus.connect_agent("coder").expect("owner");
    let mut other = bus.connect_agent("other").expect("other");
    open_project(&mut owner, dir.path());
    let id = spawn_named(&mut owner, "hero");

    let locked = owner
        .call(
            "entity.lock",
            json!({
                "command_id": cid(),
                "ids": [id],
                "note": "editing sprite",
            }),
        )
        .expect("entity.lock");
    assert!(locked["owner_token"]
        .as_str()
        .is_some_and(|t| !t.is_empty()));

    let err = set_x(&mut other, &id, 99.0).expect_err("other set");
    assert!(
        err.code == -32000 || err.code == -32002,
        "code={}",
        err.code
    );
    assert_eq!(app_code(&err), "E_LOCKED");
    let note = err
        .data
        .as_ref()
        .and_then(|d| d.reason.as_deref())
        .unwrap_or(&err.message);
    assert!(note.contains(owner.actor_id()), "owner missing: {note}");
    assert!(note.contains("editing sprite"), "note missing: {note}");
}

#[test]
fn same_actor_can_mutate_locked_entity() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut owner = bus.connect_agent("coder").expect("owner");
    open_project(&mut owner, dir.path());
    let id = spawn_named(&mut owner, "hero");
    owner
        .call(
            "entity.lock",
            json!({
                "command_id": cid(),
                "ids": [id],
                "note": "mine",
            }),
        )
        .expect("lock");
    set_x(&mut owner, &id, 3.0).expect("owner set");
}

#[test]
fn unlock_releases_entity() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut owner = bus.connect_agent("coder").expect("owner");
    let mut other = bus.connect_agent("other").expect("other");
    open_project(&mut owner, dir.path());
    let id = spawn_named(&mut owner, "hero");
    owner
        .call(
            "entity.lock",
            json!({
                "command_id": cid(),
                "ids": [id],
                "note": "hold",
            }),
        )
        .expect("lock");
    owner
        .call("entity.unlock", json!({ "command_id": cid(), "ids": [id] }))
        .expect("unlock");
    set_x(&mut other, &id, 4.0).expect("other set after unlock");
}

#[test]
fn agent_cannot_force_unlock() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut owner = bus.connect_agent("coder").expect("owner");
    let mut other = bus.connect_agent("other").expect("other");
    open_project(&mut owner, dir.path());
    let id = spawn_named(&mut owner, "hero");
    owner
        .call(
            "entity.lock",
            json!({
                "command_id": cid(),
                "ids": [id],
                "note": "keep",
            }),
        )
        .expect("lock");
    let err = other
        .call(
            "entity.unlock",
            json!({
                "command_id": cid(),
                "ids": [id],
                "force": true,
            }),
        )
        .expect_err("agent force");
    assert_eq!(app_code(&err), "E_LOCKED");
}

#[test]
fn human_ui_force_unlock_releases() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut owner = bus.connect_agent("coder").expect("owner");
    let mut other = bus.connect_agent("other").expect("other");
    open_project(&mut owner, dir.path());
    let id = spawn_named(&mut owner, "hero");
    owner
        .call(
            "entity.lock",
            json!({
                "command_id": cid(),
                "ids": [id],
                "note": "keep",
            }),
        )
        .expect("lock");
    bus.ui()
        .call("entity.unlock", json!({ "command_id": cid(), "ids": [id] }))
        .expect("human force unlock");
    set_x(&mut other, &id, 1.0).expect("set after human unlock");
}

#[test]
fn settings_set_round_trip_keeps_unknown_field() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());
    agent
        .call(
            "project.settings_set",
            json!({
                "command_id": cid(),
                "patch": {
                    "fixed_dt": 0.02,
                    "ppu": 32,
                    "x-custom": "keep-me",
                },
            }),
        )
        .expect("settings_set");
    let got = agent
        .call("project.settings_get", json!({}))
        .expect("settings_get");
    assert_eq!(got["settings"]["x-custom"], "keep-me");
    assert_eq!(got["settings"]["ppu"], 32);

    bus.ui()
        .call("project.save_all", json!({}))
        .expect("save_all");
    let text = std::fs::read_to_string(dir.path().join("project.json")).expect("project.json");
    assert!(text.contains("keep-me"), "disk={text}");
    assert!(text.contains("32"), "disk={text}");
}

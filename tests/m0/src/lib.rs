//! M0 conformance, fault-injection, and GS-EC harness (WP-M0-6).
//!
//! Crash tests use [`gs_scene::Session::inject_crash`] (simulated MASTER 5.5
//! points). They do **not** send a real `kill -9`.

use std::path::Path;

use gs_editor::AgentClient;
use gs_protocol::RpcError;
use gs_scene::{DispatchRequest, Session, DEFAULT_SCENE_ID};
use serde_json::{json, Value};
use tempfile::TempDir;
use ulid::Ulid;

pub use gs_editor::{start, BusHandle};
pub use gs_protocol::{
    decode_message, read_ndjson_line, APP_CODE_PROTO, CONFLICT, INVALID_PARAMS, INVALID_REQUEST,
    MAX_LINE_BYTES, UNAUTHORIZED,
};
pub use gs_registry::{all_methods, get, Capability, MethodSpec};
pub use gs_scene::{Ack, Command, CrashPoint, Error as SceneError, Transform2D};

pub fn crate_name() -> &'static str {
    "m0"
}

pub fn cid() -> String {
    Ulid::new().to_string()
}

pub fn app_code(err: &RpcError) -> &str {
    err.data.as_ref().map(|d| d.app_code.as_str()).unwrap_or("")
}

pub fn ui_only_method_names() -> Vec<&'static str> {
    all_methods()
        .iter()
        .filter(|spec| spec.is_ui_only())
        .map(|spec| spec.name)
        .collect()
}

pub fn open_session() -> (TempDir, Session) {
    let dir = TempDir::new().expect("tempdir");
    let session = Session::open(dir.path()).expect("session");
    (dir, session)
}

pub fn spawn_session(session: &mut Session, name: &str) -> Ack {
    session
        .dispatch(DispatchRequest::spawn(
            cid(),
            "act_01",
            DEFAULT_SCENE_ID,
            name,
        ))
        .expect("spawn")
}

pub fn start_bus() -> (TempDir, BusHandle) {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("bus");
    (dir, bus)
}

pub fn open_project(agent: &mut AgentClient, path: &Path) -> Value {
    agent
        .call(
            "project.open",
            json!({ "path": path.to_string_lossy().into_owned() }),
        )
        .expect("project.open")
}

pub fn entity_count(agent: &mut AgentClient) -> usize {
    let stats = agent.call("scene.stats", json!({})).expect("scene.stats");
    stats["entity_count"].as_u64().expect("entity_count") as usize
}

pub fn spawn_named(agent: &mut AgentClient, name: &str, command_id: &str) -> Value {
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

pub fn revision(agent: &mut AgentClient) -> String {
    let stats = agent.call("scene.stats", json!({})).expect("scene.stats");
    stats["revision"].as_str().expect("revision").to_owned()
}

#[cfg(test)]
mod crate_smoke {
    #[test]
    fn package_name_and_registry_ui_only() {
        assert_eq!(super::crate_name(), "m0");
        assert!(
            !super::ui_only_method_names().is_empty(),
            "registry must declare at least one UiOnly method"
        );
        assert!(super::get("undo.perform").is_some_and(|s| s.is_ui_only()));
        assert!(matches!(
            super::get("entity.destroy").map(|s| s.capability),
            Some(super::Capability::Destructive(_))
        ));
    }
}

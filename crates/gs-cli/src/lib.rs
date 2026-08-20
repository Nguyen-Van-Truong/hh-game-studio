//! Thin bus client behind `tools/gs.ps1`.
//!
//! Reads `.gs/runtime/endpoint.json`, hellos, then sends JSON-RPC 2.0 NDJSON.
//! Does **not** contain document, WAL, or scene logic.

mod client;
mod command_id;
mod doctor;
mod endpoint;
mod error;
mod jobs;

pub use client::{BusClient, HelloInfo, InvokeResult};
pub use command_id::{
    commands_from_jsonl, ensure_command_id, needs_command_id, transaction_params,
};
pub use doctor::{imagegen_config_path, run_doctor, run_doctor_with, DoctorEnv, DoctorReport};
pub use endpoint::{
    endpoint_path, load_live_endpoint, pid_is_alive, read_endpoint_file, Endpoint, ENDPOINT_REL,
};
pub use error::Error;
pub use gs_protocol::{Notification, RpcError, PROTOCOL_VER};
pub use jobs::{jobs_claim, jobs_finish, jobs_heartbeat};

pub fn crate_name() -> &'static str {
    "gs-cli"
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn smoke() {
        assert_eq!(crate_name(), "gs-cli");
    }

    #[test]
    fn ensure_command_id_fills_ulid_for_spawn() {
        let (params, id) = ensure_command_id("entity.spawn", json!({"name": "crate"}));
        let id = id.expect("command_id");
        assert!(ulid::Ulid::from_string(&id).is_ok(), "not a ULID: {id}");
        assert_eq!(params["command_id"], id);
        assert_eq!(params["name"], "crate");
    }

    #[test]
    fn ensure_command_id_keeps_existing() {
        let (params, id) = ensure_command_id(
            "entity.spawn",
            json!({"name": "crate", "command_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV"}),
        );
        assert_eq!(id.as_deref(), Some("01ARZ3NDEKTSV4RRFFQ69G5FAV"));
        assert_eq!(params["command_id"], "01ARZ3NDEKTSV4RRFFQ69G5FAV");
    }

    #[test]
    fn ensure_command_id_skips_readonly() {
        let (params, id) = ensure_command_id("session.ping", json!({}));
        assert!(id.is_none());
        assert!(params.get("command_id").is_none());
    }

    #[test]
    fn ensure_command_id_fills_judge_run_test() {
        let (params, id) = ensure_command_id(
            "judge.run_test",
            json!({ "gtest_rel": "tests/coin.gtest.json" }),
        );
        let id = id.expect("command_id");
        assert!(ulid::Ulid::from_string(&id).is_ok(), "not a ULID: {id}");
        assert_eq!(params["command_id"], id);
        assert_eq!(params["gtest_rel"], "tests/coin.gtest.json");
    }

    #[test]
    fn jsonl_strips_utf8_bom() {
        let text = "\u{feff}{\"method\":\"entity.spawn\",\"params\":{\"name\":\"a\"}}\n";
        let commands = commands_from_jsonl(text).expect("jsonl");
        assert_eq!(commands.len(), 1);
        assert_eq!(commands[0]["method"], "entity.spawn");
    }

    #[test]
    fn endpoint_debug_redacts_token() {
        let endpoint = Endpoint::new("127.0.0.1", 9, "super-secret-token-value", 1);
        let debug = format!("{endpoint:?}");
        assert!(debug.contains("<redacted>"));
        assert!(!debug.contains("super-secret-token-value"));
    }
}

//! WP-M3-4 editor half: `script.diagnostics` + `inputmap.get` / `inputmap.set`.

use std::path::Path;
use std::sync::Mutex;

use gs_editor::start;
use gs_scene::DEFAULT_SCRIPT_SOURCE;
use serde_json::{json, Value};
use tempfile::TempDir;
use ulid::Ulid;

static ANALYZE_ENV: Mutex<()> = Mutex::new(());

fn cid() -> String {
    Ulid::new().to_string()
}

fn open_project(agent: &mut gs_editor::AgentClient, path: &Path) {
    agent
        .call("project.open", json!({ "path": path.to_string_lossy() }))
        .expect("project.open");
}

/// Force the exclusive env path to a missing absolute file so PATH cannot
/// accidentally enable type check during these tests.
fn with_analyze_missing<T>(f: impl FnOnce() -> T) -> T {
    let _guard = ANALYZE_ENV.lock().expect("analyze env lock");
    let prev = std::env::var_os("GS_LUAU_ANALYZE");
    let missing = if cfg!(windows) {
        r"C:\gs-missing-luau-analyze\luau-analyze.exe"
    } else {
        "/gs-missing-luau-analyze/luau-analyze"
    };
    // SAFETY: serialized by ANALYZE_ENV; restored before the guard drops.
    unsafe {
        std::env::set_var("GS_LUAU_ANALYZE", missing);
    }
    let out = f();
    unsafe {
        match prev {
            Some(value) => std::env::set_var("GS_LUAU_ANALYZE", value),
            None => std::env::remove_var("GS_LUAU_ANALYZE"),
        }
    }
    out
}

fn message_blob(value: &serde_json::Value) -> String {
    value.to_string()
}

#[test]
fn diagnostics_without_binary_is_type_check_off() {
    with_analyze_missing(|| {
        let dir = TempDir::new().expect("tempdir");
        let bus = start(dir.path()).expect("start bus");
        let mut agent = bus.connect_agent("coder").expect("hello");
        open_project(&mut agent, dir.path());

        let path = "scripts/strict.luau";
        agent
            .call(
                "script.create",
                json!({ "command_id": cid(), "path": path }),
            )
            .expect("script.create");

        let source = "--!strict\nlocal M = {}\nfunction M.on_update(self, dt)\nend\nreturn M\n";
        agent
            .call(
                "script.set_source",
                json!({
                    "command_id": cid(),
                    "path": path,
                    "source": source,
                }),
            )
            .expect("set_source");

        let got = agent
            .call("script.diagnostics", json!({ "path": path }))
            .expect("script.diagnostics");
        assert_eq!(got["type_check"], json!("off"));
        assert_eq!(got["path"], json!(path));
        assert!(
            message_blob(&got).contains("type check off"),
            "expected type check off message, got {got}"
        );
        let rows = got["diagnostics"].as_array().expect("diagnostics");
        assert!(
            rows.iter().any(|row| {
                row["kind"] == json!("warning")
                    && row["message"]
                        .as_str()
                        .is_some_and(|m| m.contains("type check off"))
            }),
            "warning diagnostic must mention type check off, got {got}"
        );
    });
}

#[test]
fn agent_can_call_script_diagnostics() {
    with_analyze_missing(|| {
        let dir = TempDir::new().expect("tempdir");
        let bus = start(dir.path()).expect("start bus");
        let mut agent = bus.connect_agent("coder").expect("hello");
        open_project(&mut agent, dir.path());

        let got = agent
            .call("script.diagnostics", json!({}))
            .expect("agent script.diagnostics");
        assert_eq!(got["type_check"], json!("off"));
        assert!(
            message_blob(&got).contains("type check off"),
            "agent must see type check off, got {got}"
        );
        assert!(got.get("token").is_none());
    });
}

#[test]
fn create_and_set_source_still_work() {
    with_analyze_missing(|| {
        let dir = TempDir::new().expect("tempdir");
        let bus = start(dir.path()).expect("start bus");
        let mut agent = bus.connect_agent("coder").expect("hello");
        open_project(&mut agent, dir.path());

        let path = "scripts/keep.luau";
        agent
            .call(
                "script.create",
                json!({ "command_id": cid(), "path": path }),
            )
            .expect("script.create");
        let created = agent
            .call("script.get_source", json!({ "path": path }))
            .expect("get after create");
        assert_eq!(created["source"].as_str(), Some(DEFAULT_SCRIPT_SOURCE));
        assert!(
            created["source"]
                .as_str()
                .is_some_and(|s| s.starts_with("--!strict")),
            "default template should encourage --!strict"
        );

        let changed = "--!strict\nlocal after = true\nreturn {}\n";
        agent
            .call(
                "script.set_source",
                json!({
                    "command_id": cid(),
                    "path": path,
                    "source": changed,
                }),
            )
            .expect("set_source");
        let after = agent
            .call("script.get_source", json!({ "path": path }))
            .expect("get after set");
        assert_eq!(after["source"].as_str(), Some(changed));
        assert_eq!(after["conflict"], json!(false));
    });
}

fn action_names(value: &Value) -> Vec<String> {
    value
        .get("actions")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(|row| {
            row.get("name")
                .and_then(Value::as_str)
                .map(ToOwned::to_owned)
        })
        .collect()
}

fn has_action(value: &Value, name: &str) -> bool {
    action_names(value).iter().any(|n| n == name)
}

#[test]
fn agent_inputmap_get_returns_default_actions() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

    let got = agent.call("inputmap.get", json!({})).expect("inputmap.get");
    assert!(
        has_action(&got, "move_x") && has_action(&got, "interact"),
        "fresh project must return the 6.4 sample, got {got}"
    );
}

#[test]
fn inputmap_set_get_round_trips_and_revert_own_restores() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

    let actions = json!([
        {
            "name": "jump",
            "type": "button",
            "keys": ["Space"],
            "gamepad_button": "south"
        }
    ]);
    let set = agent
        .call(
            "inputmap.set",
            json!({
                "command_id": cid(),
                "actions": actions,
            }),
        )
        .expect("inputmap.set");
    let txn_id = set["txn_id"].as_str().expect("txn_id").to_owned();

    let after = agent
        .call("inputmap.get", json!({}))
        .expect("get after set");
    assert_eq!(after["actions"], actions);

    agent
        .call(
            "undo.revert_own",
            json!({ "command_id": cid(), "txn_id": txn_id }),
        )
        .expect("undo.revert_own");
    let restored = agent
        .call("inputmap.get", json!({}))
        .expect("get after revert");
    assert!(
        has_action(&restored, "move_x") && has_action(&restored, "interact"),
        "revert_own must restore the default map, got {restored}"
    );
    assert!(
        !has_action(&restored, "jump"),
        "revert_own must drop the set actions, got {restored}"
    );
}

#[test]
fn play_start_snapshot_input_map_is_not_empty() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

    let started = agent
        .call(
            "play.start",
            json!({ "headless": true, "command_id": cid() }),
        )
        .expect("play.start");
    let manifest = started["snapshot_manifest"]
        .as_str()
        .expect("snapshot_manifest");
    let play_dir = Path::new(manifest)
        .parent()
        .expect("play dir is parent of manifest.json");
    let map_path = play_dir.join("input-map.json");
    let map: Value = serde_json::from_str(
        &std::fs::read_to_string(&map_path)
            .unwrap_or_else(|e| panic!("read {}: {e}", map_path.display())),
    )
    .expect("input-map.json");
    assert_ne!(
        map,
        json!({ "actions": [] }),
        "play snapshot must copy the real input map, not an empty actions list"
    );
    assert!(
        has_action(&map, "move_x"),
        "play snapshot input-map.json must contain move_x, got {map}"
    );

    let status = agent.call("play.status", json!({})).expect("play.status");
    assert_eq!(status["alive"], json!(true));
    let _ = agent.call("play.stop", json!({})).expect("play.stop");
}

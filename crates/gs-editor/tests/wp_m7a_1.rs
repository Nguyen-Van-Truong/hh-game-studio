//! WP-M7A-1: `build.game` / `status` / `cancel` (T7A.1 / I7 / I11).

use std::fs;
use std::path::Path;
use std::process::Command;

use gs_editor::{start, RpcError};
use serde_json::json;
use tempfile::TempDir;
use ulid::Ulid;

const SCRIPT_SRC: &str = r#"
local M = {}
function M.on_update(self)
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

fn upload_script(agent: &mut gs_editor::AgentClient) {
    agent
        .call(
            "script.create",
            json!({ "command_id": cid(), "path": "scripts/pack.luau" }),
        )
        .expect("script.create");
    agent
        .call(
            "script.set_source",
            json!({
                "command_id": cid(),
                "path": "scripts/pack.luau",
                "source": SCRIPT_SRC,
            }),
        )
        .expect("script.set_source");
}

fn attach_script(agent: &mut gs_editor::AgentClient, file: &str) {
    let id = agent
        .call(
            "entity.spawn",
            json!({
                "command_id": cid(),
                "scene_id": "s_main",
                "name": "Scripted",
            }),
        )
        .expect("entity.spawn scripted")["spawned_ids"][0]
        .as_str()
        .expect("id")
        .to_owned();
    agent
        .call(
            "component.add",
            json!({
                "command_id": cid(),
                "id": id,
                "type": "Script",
                "value": { "file": file, "props": {} },
            }),
        )
        .expect("Script");
}

fn player_name() -> &'static str {
    if cfg!(windows) {
        "gs-player.exe"
    } else {
        "gs-player"
    }
}

#[test]
fn build_game_writes_player_and_manifest_outside_project() {
    kill_leftover_players();
    let project = TempDir::new().expect("project");
    let out = TempDir::new().expect("out");
    let bus = start(project.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, project.path());
    spawn_camera(&mut agent);
    upload_script(&mut agent);
    attach_script(&mut agent, "scripts/pack.luau");

    let command_id = cid();
    let first = agent
        .call(
            "build.game",
            json!({
                "command_id": command_id,
                "out_dir": out.path().to_string_lossy(),
            }),
        )
        .expect("build.game");
    let build_id = first["build_id"].as_str().expect("build_id").to_owned();
    assert!(build_id.starts_with("b_"), "{build_id}");
    assert_eq!(first["state"], "done");
    assert!(out.path().join(player_name()).is_file(), "player exe");
    assert!(out.path().join("manifest.json").is_file(), "manifest");
    assert!(out.path().join("run.bat").is_file(), "run.bat");
    assert!(out.path().join("scene.json").is_file(), "scene");
    assert!(out.path().join("input-map.json").is_file(), "input-map");
    assert!(!out.path().join(".gs").exists(), "no WAL in pack");

    let retry = agent
        .call(
            "build.game",
            json!({
                "command_id": command_id,
                "out_dir": out.path().to_string_lossy(),
            }),
        )
        .expect("dedup build.game");
    assert_eq!(retry["build_id"], build_id);

    let status = agent
        .call("build.status", json!({ "build_id": build_id }))
        .expect("build.status");
    assert_eq!(status["state"], "done");
    assert!(status["path"].as_str().is_some());

    let cancel = agent
        .call(
            "build.cancel",
            json!({ "command_id": cid(), "build_id": build_id }),
        )
        .expect("cancel finished");
    assert_eq!(cancel["already_finished"], true);
}

#[test]
fn build_game_rejects_out_dir_inside_project() {
    kill_leftover_players();
    let project = TempDir::new().expect("project");
    let bus = start(project.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, project.path());
    spawn_camera(&mut agent);
    upload_script(&mut agent);

    let inside = project.path().join("inside-out");
    let err = agent
        .call(
            "build.game",
            json!({
                "command_id": cid(),
                "out_dir": inside.to_string_lossy(),
            }),
        )
        .expect_err("inside out_dir");
    assert_eq!(app_code(&err), "E_PATH");
    assert!(!inside.join(player_name()).exists());
}

#[test]
fn build_game_fails_before_copy_when_script_missing() {
    kill_leftover_players();
    let project = TempDir::new().expect("project");
    let out = TempDir::new().expect("out");
    let bus = start(project.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, project.path());
    spawn_camera(&mut agent);
    attach_script(&mut agent, "scripts/nope.luau");

    let err = agent
        .call(
            "build.game",
            json!({
                "command_id": cid(),
                "out_dir": out.path().to_string_lossy(),
            }),
        )
        .expect_err("missing script");
    assert_eq!(app_code(&err), "E_VALIDATION");
    assert!(
        err.message.contains("nope.luau") || err.message.contains("missing script"),
        "{err:?}"
    );
    assert!(
        !out.path().join(player_name()).exists(),
        "must not copy player after missing script"
    );
    let leftover: Vec<_> = fs::read_dir(out.path())
        .expect("read out")
        .filter_map(|e| e.ok())
        .collect();
    assert!(
        leftover.is_empty(),
        "out_dir should stay empty, got {leftover:?}"
    );
}

#[test]
fn build_cancel_unknown_id_is_not_found() {
    kill_leftover_players();
    let project = TempDir::new().expect("project");
    let bus = start(project.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, project.path());
    let err = agent
        .call(
            "build.cancel",
            json!({ "command_id": cid(), "build_id": "b_unknown" }),
        )
        .expect_err("unknown cancel");
    assert_eq!(app_code(&err), "E_NOT_FOUND");
}

#[test]
fn build_cancel_requires_command_id() {
    kill_leftover_players();
    let project = TempDir::new().expect("project");
    let bus = start(project.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, project.path());
    let err = agent
        .call("build.cancel", json!({ "build_id": "b_unknown" }))
        .expect_err("missing command_id");
    assert_eq!(app_code(&err), "E_VALIDATION");
    assert!(
        err.message.contains("command_id"),
        "missing command_id must say so, got {err:?}"
    );
}

#[test]
fn build_game_lists_pointer_under_runtime_build() {
    kill_leftover_players();
    let project = TempDir::new().expect("project");
    let out = TempDir::new().expect("out");
    let bus = start(project.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, project.path());
    spawn_camera(&mut agent);
    upload_script(&mut agent);
    attach_script(&mut agent, "scripts/pack.luau");

    let first = agent
        .call(
            "build.game",
            json!({
                "command_id": cid(),
                "out_dir": out.path().to_string_lossy(),
            }),
        )
        .expect("build.game");
    let build_id = first["build_id"].as_str().expect("build_id").to_owned();

    let listed = agent
        .call("artifact.list", json!({ "kind": "build" }))
        .expect("artifact.list");
    let artifacts = listed["artifacts"].as_array().expect("artifacts");
    let want = format!(".gs/runtime/build/{build_id}.json");
    assert!(
        artifacts
            .iter()
            .any(|a| a["artifact_id"].as_str() == Some(want.as_str())),
        "expected {want} in {listed}"
    );

    let pointer = project
        .path()
        .join(".gs")
        .join("runtime")
        .join("build")
        .join(format!("{build_id}.json"));
    let text = fs::read_to_string(&pointer).expect("pointer file");
    let body: serde_json::Value = serde_json::from_str(&text).expect("pointer json");
    assert_eq!(body["build_id"], build_id);
    assert_eq!(body["state"], "done");
    assert!(body.get("token").is_none(), "I8: no bus token in pointer");
    assert!(
        !out.path().join(".gs").exists(),
        "packed game stays outside project"
    );
}

#[test]
fn build_game_dedup_survives_editor_restart() {
    kill_leftover_players();
    let project = TempDir::new().expect("project");
    let out_root = TempDir::new().expect("out root");
    let out_dir = out_root.path().join("pack-out");
    fs::create_dir_all(&out_dir).expect("out dir");
    let command_id = cid();
    let build_id;
    {
        let bus = start(project.path()).expect("start bus");
        let mut agent = bus.connect_agent("coder").expect("hello");
        open_project(&mut agent, project.path());
        spawn_camera(&mut agent);
        upload_script(&mut agent);
        attach_script(&mut agent, "scripts/pack.luau");
        let first = agent
            .call(
                "build.game",
                json!({
                    "command_id": command_id,
                    "out_dir": out_dir.to_string_lossy(),
                }),
            )
            .expect("build.game");
        build_id = first["build_id"].as_str().expect("build_id").to_owned();
        assert_eq!(first["state"], "done");
    }

    fs::remove_dir_all(&out_dir).expect("remove packed out_dir");
    fs::write(&out_dir, b"not-a-directory").expect("block re-pack");

    let bus = start(project.path()).expect("restart bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, project.path());
    let retry = agent
        .call(
            "build.game",
            json!({
                "command_id": command_id,
                "out_dir": out_dir.to_string_lossy(),
            }),
        )
        .expect("dedup after restart");
    assert_eq!(retry["build_id"], build_id);
    assert_eq!(retry["state"], "done");
    assert!(
        out_dir.is_file(),
        "must return cached metadata, not re-pack into blocked out_dir"
    );
}

//! WP-M1-3: gizmo drag → one dispatcher txn + soft lock (GS-EC-12).
//! No eframe window is opened.

use gs_editor::{
    apply_view_navigation, start, Badge, GizmoDragUpdate, GizmoKind, RpcError, ViewState,
};
use serde_json::{json, Value};
use tempfile::TempDir;
use ulid::Ulid;

fn cid() -> String {
    Ulid::new().to_string()
}

fn app_code(err: &RpcError) -> &str {
    err.data.as_ref().map(|d| d.app_code.as_str()).unwrap_or("")
}

fn revision(ui: &gs_editor::UiHandle) -> String {
    ui.call("scene.stats", json!({})).expect("scene.stats")["revision"]
        .as_str()
        .expect("revision")
        .to_owned()
}

fn spawn_hero(agent: &mut gs_editor::AgentClient, path: &std::path::Path) -> String {
    agent
        .call("project.open", json!({ "path": path.to_string_lossy() }))
        .expect("project.open");
    let ack = agent
        .call(
            "entity.spawn",
            json!({
                "command_id": cid(),
                "scene_id": "s_main",
                "name": "hero",
            }),
        )
        .expect("entity.spawn");
    ack["spawned_ids"][0]
        .as_str()
        .expect("spawned id")
        .to_owned()
}

fn transform_of(ui: &gs_editor::UiHandle, id: &str) -> Value {
    ui.call("component.get", json!({ "id": id, "type": "Transform2D" }))
        .expect("component.get")["value"]
        .clone()
}

fn set_transform(agent: &mut gs_editor::AgentClient, id: &str, x: f64) -> Result<Value, RpcError> {
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
fn gizmo_drag_commits_one_revision_and_undo_restores() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    let id = spawn_hero(&mut agent, dir.path());
    let ui = bus.ui();

    let before_rev = revision(ui);
    let start_pose = transform_of(ui, &id);
    assert_eq!(start_pose["x"].as_f64().unwrap_or(-1.0), 0.0);
    assert_eq!(start_pose["y"].as_f64().unwrap_or(-1.0), 0.0);

    ui.begin_gizmo_drag(&id, GizmoKind::Move).expect("begin");
    ui.update_gizmo_drag(GizmoDragUpdate::move_by(1.0, 0.0))
        .expect("update 1");
    ui.update_gizmo_drag(GizmoDragUpdate::move_by(2.0, 1.0))
        .expect("update 2");
    ui.update_gizmo_drag(GizmoDragUpdate::move_by(3.0, -1.0))
        .expect("update 3");

    assert_eq!(
        revision(ui),
        before_rev,
        "preview updates must not write WAL"
    );
    let mid = transform_of(ui, &id);
    assert_eq!(mid["x"].as_f64().unwrap_or(-1.0), 0.0);
    assert_eq!(mid["y"].as_f64().unwrap_or(-1.0), 0.0);

    let entity_num: u64 = id
        .strip_prefix("e_")
        .and_then(|s| s.parse().ok())
        .expect("entity number");
    let preview = ui
        .viewport_entities()
        .into_iter()
        .find(|e| e.id == entity_num)
        .expect("preview entity");
    assert!((preview.x - 3.0).abs() < f32::EPSILON);
    assert!((preview.y + 1.0).abs() < f32::EPSILON);

    let humans_before = ui.feed().iter().filter(|e| e.badge == Badge::Human).count();
    let ack = ui.end_gizmo_drag().expect("end");
    assert_eq!(ack["revision"].as_str().expect("ack rev"), revision(ui));

    let after_rev = revision(ui);
    assert_ne!(after_rev, before_rev, "one commit must bump revision");
    let before_n: u64 = before_rev
        .strip_prefix("r-")
        .and_then(|s| s.parse().ok())
        .expect("before rev");
    let after_n: u64 = after_rev
        .strip_prefix("r-")
        .and_then(|s| s.parse().ok())
        .expect("after rev");
    assert_eq!(after_n, before_n + 1, "exactly one revision for the drag");

    let humans: Vec<_> = ui
        .feed()
        .into_iter()
        .filter(|e| e.badge == Badge::Human)
        .collect();
    assert_eq!(humans.len(), humans_before + 1);
    let entry = humans.last().expect("human feed");
    assert_eq!(entry.badge.feed_label(), "BẠN");
    assert!(
        entry.label.contains("gizmo") && entry.label.contains("move"),
        "label={}",
        entry.label
    );
    assert!(entry.entities.iter().any(|e| e == &id));

    let committed = transform_of(ui, &id);
    assert_eq!(committed["x"].as_f64(), Some(3.0));
    assert_eq!(committed["y"].as_f64(), Some(-1.0));

    ui.call("undo.perform", json!({}))
        .expect("human_ui undo.perform");
    let restored = transform_of(ui, &id);
    assert_eq!(restored["x"].as_f64(), start_pose["x"].as_f64());
    assert_eq!(restored["y"].as_f64(), start_pose["y"].as_f64());
    assert_eq!(restored["rot"].as_f64(), start_pose["rot"].as_f64());
}

#[test]
fn agent_component_set_during_gizmo_drag_is_locked() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    let id = spawn_hero(&mut agent, dir.path());
    let ui = bus.ui();

    ui.begin_gizmo_drag(&id, GizmoKind::Move).expect("begin");
    ui.update_gizmo_drag(GizmoDragUpdate::move_by(1.0, 0.0))
        .expect("update");

    let err = set_transform(&mut agent, &id, 99.0).expect_err("agent set while locked");
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
    assert!(note.contains("act_01"), "owner missing: {note}");
    assert!(note.contains("gizmo drag"), "note missing: {note}");

    let pose = transform_of(ui, &id);
    assert_eq!(pose["x"].as_f64(), Some(0.0));
}

#[test]
fn agent_can_set_transform_after_gizmo_drag_ends() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    let id = spawn_hero(&mut agent, dir.path());
    let ui = bus.ui();

    ui.begin_gizmo_drag(&id, GizmoKind::Rotate).expect("begin");
    ui.update_gizmo_drag(GizmoDragUpdate::rotate(0.5))
        .expect("update");
    ui.end_gizmo_drag().expect("end");

    let ack = set_transform(&mut agent, &id, 4.0).expect("agent set after unlock");
    assert!(ack.get("revision").is_some());
    let pose = transform_of(ui, &id);
    assert_eq!(pose["x"].as_f64(), Some(4.0));
}

#[test]
fn pan_zoom_during_and_after_gizmo_does_not_change_revision() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    let id = spawn_hero(&mut agent, dir.path());
    let ui = bus.ui();

    ui.begin_gizmo_drag(&id, GizmoKind::Move).expect("begin");
    ui.update_gizmo_drag(GizmoDragUpdate::move_by(0.5, 0.25))
        .expect("update");
    let during = revision(ui);

    let mut view = ViewState::default();
    apply_view_navigation(&mut view, [4.0, -1.0], 0.5);
    view.set_grid(false);
    view.set_snap(true);
    let _ = view.snap_point([1.2, 2.8]);
    let _ = ui.viewport_entities();

    assert_eq!(revision(ui), during, "pan/zoom during drag must not WAL");

    ui.end_gizmo_drag().expect("end");
    let after_commit = revision(ui);

    apply_view_navigation(&mut view, [-1.0, 2.0], 1.25);
    let _ = ui.viewport_entities();
    assert_eq!(
        revision(ui),
        after_commit,
        "pan/zoom after gizmo must not WAL"
    );
}

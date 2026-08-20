//! WP-M1-4: hierarchy, schema-driven inspector, png import (I7).
//! No eframe window is opened.

use std::path::Path;

use gs_editor::{find_node, start, MASTER_5_2_TYPES};
use serde_json::{json, Value};
use tempfile::TempDir;
use ulid::Ulid;

fn cid() -> String {
    Ulid::new().to_string()
}

fn revision(ui: &gs_editor::UiHandle) -> String {
    ui.call("scene.stats", json!({})).expect("scene.stats")["revision"]
        .as_str()
        .expect("revision")
        .to_owned()
}

fn spawn(agent: &mut gs_editor::AgentClient, name: &str) -> String {
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

fn write_tiny_png(path: &Path, width: u32, height: u32) {
    let mut bytes = vec![0u8; 24];
    bytes[..8].copy_from_slice(&[0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]);
    bytes[12..16].copy_from_slice(b"IHDR");
    bytes[16..20].copy_from_slice(&width.to_be_bytes());
    bytes[20..24].copy_from_slice(&height.to_be_bytes());
    std::fs::write(path, bytes).expect("write png");
}

fn field_value(view: &gs_editor::InspectorView, type_name: &str, field: &str) -> Value {
    view.components
        .iter()
        .find(|c| c.type_name == type_name && c.present)
        .and_then(|c| c.fields.iter().find(|f| f.name == field))
        .map(|f| f.value.clone())
        .unwrap_or(Value::Null)
}

#[test]
fn spawn_via_bus_appears_in_hierarchy() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    agent
        .call(
            "project.open",
            json!({ "path": dir.path().to_string_lossy() }),
        )
        .expect("project.open");
    let id = spawn(&mut agent, "hero");
    let tree = bus.ui().hierarchy();
    let node = find_node(&tree, &id).expect("spawned entity in hierarchy");
    assert_eq!(node.name, "hero");
    assert_eq!(node.parent, None);
    assert!(node.children.is_empty());
}

#[test]
fn inspector_component_set_name_and_transform_readback() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    agent
        .call(
            "project.open",
            json!({ "path": dir.path().to_string_lossy() }),
        )
        .expect("project.open");
    let id = spawn(&mut agent, "hero");
    let ui = bus.ui();
    let before = revision(ui);

    ui.call(
        "component.set",
        json!({
            "command_id": cid(),
            "id": id,
            "type": "Name",
            "patch": { "value": "renamed" },
        }),
    )
    .expect("set Name");
    let after_name = revision(ui);
    assert_ne!(after_name, before);

    ui.call(
        "component.set",
        json!({
            "command_id": cid(),
            "id": id,
            "type": "Transform2D",
            "patch": { "x": 3.5, "y": -1.0 },
        }),
    )
    .expect("set Transform2D");
    let after_xf = revision(ui);
    assert_ne!(after_xf, after_name);

    let tree = ui.hierarchy();
    let node = find_node(&tree, &id).expect("hierarchy after rename");
    assert_eq!(node.name, "renamed");

    let view = ui.inspector(&id).expect("inspector");
    assert_eq!(view.id, id);
    assert_eq!(view.revision, after_xf);
    assert_eq!(field_value(&view, "Name", "value"), json!("renamed"));
    assert_eq!(field_value(&view, "Transform2D", "x"), json!(3.5));
    assert_eq!(field_value(&view, "Transform2D", "y"), json!(-1.0));
}

#[test]
fn reparent_updates_hierarchy_keep_world_defaults_true() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    agent
        .call(
            "project.open",
            json!({ "path": dir.path().to_string_lossy() }),
        )
        .expect("project.open");
    let parent = spawn(&mut agent, "root");
    let child = spawn(&mut agent, "kid");
    let ui = bus.ui();

    ui.call(
        "component.set",
        json!({
            "command_id": cid(),
            "id": parent,
            "type": "Transform2D",
            "patch": { "x": 2.0 },
        }),
    )
    .expect("parent x");
    ui.call(
        "component.set",
        json!({
            "command_id": cid(),
            "id": child,
            "type": "Transform2D",
            "patch": { "x": 8.0 },
        }),
    )
    .expect("child x");

    ui.call(
        "entity.reparent",
        json!({
            "command_id": cid(),
            "ids": [child],
            "new_parent": parent,
        }),
    )
    .expect("reparent without keep_world (helper defaults true)");

    let tree = ui.hierarchy();
    let parent_node = find_node(&tree, &parent).expect("parent node");
    assert!(
        parent_node.children.iter().any(|c| c.id == child),
        "child must be under parent"
    );
    let child_node = find_node(&tree, &child).expect("child node");
    assert_eq!(child_node.parent.as_deref(), Some(parent.as_str()));

    let xf = ui
        .call(
            "component.get",
            json!({ "id": child, "type": "Transform2D" }),
        )
        .expect("child transform");
    let local_x = xf["value"]["x"].as_f64().expect("x");
    assert!(
        (local_x - 6.0).abs() < 1e-4,
        "keep_world=true should rewrite local x to 6, got {local_x}"
    );
}

#[test]
fn asset_import_src_outside_root_ok_and_dotdot_dest_rejected() {
    let project = TempDir::new().expect("project");
    let outside = TempDir::new().expect("outside");
    let bus = start(project.path()).expect("start bus");
    let mut agent = bus.connect_agent("coder").expect("hello");
    agent
        .call(
            "project.open",
            json!({ "path": project.path().to_string_lossy() }),
        )
        .expect("project.open");

    let src = outside.path().join("src.png");
    write_tiny_png(&src, 8, 4);
    assert!(
        !src.starts_with(project.path()),
        "src must be outside the project root"
    );

    let imported = agent
        .call(
            "asset.import",
            json!({
                "src_abs": src.to_string_lossy(),
                "dest_rel": "assets/from_outside.png",
            }),
        )
        .expect("import from outside root");
    let asset_id = imported["asset_id"].as_str().expect("asset_id");
    assert!(asset_id.starts_with("a_"), "asset_id={asset_id}");
    assert_eq!(
        imported["dest_rel"].as_str(),
        Some("assets/from_outside.png")
    );
    let dest = project.path().join("assets").join("from_outside.png");
    assert!(dest.is_file(), "dest missing: {}", dest.display());
    assert!(dest.starts_with(project.path()));

    let listed = agent.call("asset.list", json!({})).expect("asset.list");
    assert!(listed["assets"]
        .as_array()
        .expect("assets")
        .iter()
        .any(|a| a["asset_id"] == asset_id));

    let err = agent
        .call(
            "asset.import",
            json!({
                "src_abs": src.to_string_lossy(),
                "dest_rel": r"..\escape.png",
            }),
        )
        .expect_err("dotdot dest must be rejected (I7)");
    let code = err.data.as_ref().map(|d| d.app_code.as_str()).unwrap_or("");
    assert!(
        code == "E_PATH" || code == "E_VALIDATION",
        "app_code={code} message={}",
        err.message
    );
    assert!(!project.path().join("escape.png").exists());
}

#[test]
fn component_registry_lists_all_master_5_2_types() {
    let dir = TempDir::new().expect("tempdir");
    let bus = start(dir.path()).expect("start bus");
    let ui = bus.ui();
    let registry = ui
        .call("component.registry", json!({}))
        .expect("component.registry");
    let names: Vec<&str> = registry["names"]
        .as_array()
        .expect("names")
        .iter()
        .map(|v| v.as_str().expect("name"))
        .collect();
    for ty in MASTER_5_2_TYPES {
        assert!(names.contains(ty), "missing {ty} in names");
    }
    assert_eq!(names.len(), MASTER_5_2_TYPES.len());

    let types = registry["types"].as_array().expect("types");
    assert_eq!(types.len(), MASTER_5_2_TYPES.len());
    for ty in MASTER_5_2_TYPES {
        let spec = types
            .iter()
            .find(|t| t["type"].as_str() == Some(*ty))
            .unwrap_or_else(|| panic!("missing schema row {ty}"));
        let fields = spec["fields"].as_array().expect("fields");
        assert!(
            !fields.is_empty(),
            "{ty} must expose fields so inspector widgets stay data-driven"
        );
    }
}

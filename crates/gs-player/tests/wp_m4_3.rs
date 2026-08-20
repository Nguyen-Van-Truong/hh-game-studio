//! WP-M4-3: headless play_sfx with a missing file must not kill the process.

use std::collections::BTreeMap;
use std::path::Path;

use gs_player::{build_snapshot, run_headless_frames, AssetInput, SnapshotRequest};
use gs_scene::{Camera2D, Entity, Name, Scene, Script, Transform2D};
use serde_json::json;
use tempfile::TempDir;

fn transform_at(x: f32, y: f32) -> Transform2D {
    Transform2D {
        x,
        y,
        rot: 0.0,
        sx: 1.0,
        sy: 1.0,
        z_index: 0,
    }
}

fn camera() -> Entity {
    let mut entity = Entity::new(1, None, 0);
    entity.name = Some(Name {
        value: "cam".into(),
    });
    entity.transform = Some(transform_at(0.0, 0.0));
    entity.extra.camera = Some(Camera2D {
        ortho_height: 10.0,
        active: true,
    });
    entity
}

fn sfx_script() -> Entity {
    let mut entity = Entity::new(2, None, 1);
    entity.transform = Some(transform_at(0.0, 0.0));
    entity.extra.script = Some(Script {
        file: "scripts/sfx.luau".into(),
        props: BTreeMap::new(),
    });
    entity
}

fn scene() -> Scene {
    let mut scene = Scene::default();
    scene.entities.insert(1, camera());
    scene.entities.insert(2, sfx_script());
    scene
}

fn build_missing_sfx_snapshot(root: &Path) -> gs_player::BuiltSnapshot {
    let mut scripts = BTreeMap::new();
    scripts.insert(
        "sfx.luau".to_string(),
        b"gs.play_sfx({[\"$asset\"]=\"a_missing\"}, {volume=0.5})\n".to_vec(),
    );
    let mut assets = BTreeMap::new();
    assets.insert(
        "a_missing".into(),
        AssetInput {
            path: "does-not-exist.ogg".into(),
            content: None,
        },
    );
    let req = SnapshotRequest {
        play_id: "p-m4-3".into(),
        document_revision: "r-000001".into(),
        engine_ver: "0.1.0-m4-3".into(),
        protocol_ver: "1.0".into(),
        seed: 1,
        created_at: "2026-08-17T00:00:00Z".into(),
        actor: "act_test".into(),
        scene: scene().to_canonical_value(),
        project_settings: json!({
            "fixed_dt": 1.0 / 60.0,
            "ppu": 16,
            "schema_version": 1
        }),
        input_map: json!({
            "actions": [
                {
                    "name": "interact",
                    "type": "button",
                    "keys": ["E"],
                    "gamepad_button": "south"
                }
            ]
        }),
        scripts,
        assets,
    };
    build_snapshot(root, &req).expect("build snapshot")
}

#[test]
fn play_sfx_missing_file_does_not_kill_headless() {
    let tmp = TempDir::new().expect("temp");
    let built = build_missing_sfx_snapshot(tmp.path());
    let report = run_headless_frames(&built.manifest_path, 2).expect("headless must survive");
    assert_eq!(report.frames, 2);
    assert!(
        report
            .warnings
            .iter()
            .any(|w| w.contains("missing file") && w.contains("a_missing")),
        "expected missing-file warning, got {:?}",
        report.warnings
    );
}

//! WP-M5-4: GS-EC-36 + replay determinism ×2 (MASTER 12.1 / T5.4 / 6.2).
//!
//! MASTER 6.2: same machine + same build + same snapshot + same seed + same
//! tape → same per-frame result. This test does **not** claim cross-machine
//! determinism. GS-EC-35 (event miss) is covered in `wp_m5_2`.

use std::collections::BTreeMap;
use std::path::Path;

use gs_player::{
    append_action, build_snapshot, run_headless_frames_with, verify_snapshot, SnapshotRequest,
    TapeEvent, TapeHeader,
};
use gs_runtime_core::FIXED_DT;
use gs_scene::{
    format_entity_id, to_canonical_vec, Camera2D, Collider2D, ColliderShape, Entity, Name,
    RigidBody2D, Scene, Script, Transform2D,
};
use serde_json::{json, Value};
use tempfile::TempDir;

const FRAMES: u32 = 600;
const SEED: u64 = 42;
const MOVER_ID: u64 = 2;
const BOX_ID: u64 = 3;
const BOX_START_Y: f32 = 6.0;

const MOVER_SCRIPT: &str = r#"
local M = {}
function M.on_update(self)
  local x, y = gs.get_pos(self.id)
  if x == nil then
    return
  end
  gs.set_pos(self.id, x + gs.action("move_x") * (1 / 60), y)
end
return M
"#;

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

fn mover() -> Entity {
    let mut entity = Entity::new(MOVER_ID, None, 1);
    entity.name = Some(Name {
        value: "mover".into(),
    });
    entity.transform = Some(transform_at(0.0, 2.0));
    entity.extra.script = Some(Script {
        file: "scripts/mover.luau".into(),
        props: BTreeMap::new(),
    });
    entity
}

fn rigid(id: u64, x: f32, y: f32, kind: &str, shape: ColliderShape) -> Entity {
    let mut entity = Entity::new(id, None, 2);
    entity.transform = Some(transform_at(x, y));
    entity.extra.rigid_body = Some(RigidBody2D {
        kind: kind.into(),
        ccd: false,
        gravity_scale: 1.0,
        fixed_rotation: true,
        linear_damping: 0.0,
    });
    entity.extra.collider = Some(Collider2D {
        shape,
        is_sensor: false,
        offset: [0.0, 0.0],
        layer: 1,
        mask: u32::MAX,
        friction: 0.5,
        restitution: 0.0,
    });
    entity
}

fn scene() -> Scene {
    let mut scene = Scene::default();
    for entity in [
        camera(),
        mover(),
        rigid(
            BOX_ID,
            8.0,
            BOX_START_Y,
            "dynamic",
            ColliderShape::Box { w: 1.0, h: 1.0 },
        ),
        rigid(
            4,
            0.0,
            0.0,
            "static",
            ColliderShape::Box { w: 40.0, h: 1.0 },
        ),
    ] {
        scene.entities.insert(entity.id, entity);
    }
    scene
}

fn build_det_snapshot(root: &Path, play_id: &str) -> gs_player::BuiltSnapshot {
    let mut scripts = BTreeMap::new();
    scripts.insert("mover.luau".into(), MOVER_SCRIPT.as_bytes().to_vec());
    let req = SnapshotRequest {
        play_id: play_id.into(),
        document_revision: "r-000001".into(),
        engine_ver: "0.1.0-m5-4".into(),
        protocol_ver: "1.0".into(),
        seed: SEED,
        created_at: "2026-08-17T00:00:00Z".into(),
        actor: "act_test".into(),
        scene: scene().to_canonical_value(),
        project_settings: json!({
            "fixed_dt": FIXED_DT,
            "ppu": 16,
            "schema_version": 1
        }),
        input_map: json!({
            "actions": [
                { "name": "move_x", "type": "axis" }
            ]
        }),
        scripts,
        assets: BTreeMap::new(),
    };
    build_snapshot(root, &req).expect("build snapshot")
}

/// One JSONL action line per frame so both runs consume the same 600-step hold.
fn write_hold_move_x_tape(path: &Path, header: &TapeHeader, frames: u32) {
    gs_player::write_header(path, header).expect("tape header");
    for frame in 0..frames {
        append_action(
            path,
            &TapeEvent {
                frame: u64::from(frame),
                action: "move_x".into(),
                value: 1.0,
            },
        )
        .expect("tape line");
    }
}

fn entity_xy(dump: &Value, id: u64) -> (f64, f64) {
    let want = format_entity_id(id);
    let entities = dump["entities"].as_array().expect("entities");
    let entity = entities
        .iter()
        .find(|e| e["id"] == want)
        .unwrap_or_else(|| panic!("missing {want} in {dump}"));
    let x = entity["transform"]["x"].as_f64().expect("x");
    let y = entity["transform"]["y"].as_f64().expect("y");
    (x, y)
}

#[test]
fn replay_600_frames_twice_same_canonical_world_dump() {
    let tmp = TempDir::new().expect("temp");
    let built = build_det_snapshot(tmp.path(), "p-m5-4-det");
    let verified = verify_snapshot(&built.manifest_path).expect("verify");
    let header = TapeHeader::from_verified(&verified);
    assert!((header.fixed_dt - FIXED_DT).abs() < f64::EPSILON);
    assert_eq!(header.seed, SEED);

    let tape = tmp.path().join("hold_move_x_600.tape.jsonl");
    write_hold_move_x_tape(&tape, &header, FRAMES);

    let first = run_headless_frames_with(&built.manifest_path, FRAMES, Some(&tape), None, false)
        .expect("run 1 --no-render");
    let second = run_headless_frames_with(&built.manifest_path, FRAMES, Some(&tape), None, false)
        .expect("run 2 --no-render");

    assert_eq!(first.frames, u64::from(FRAMES));
    assert_eq!(second.frames, u64::from(FRAMES));
    assert!(first.evidence_ok);
    assert!(second.evidence_ok);

    let (mover_x, _) = entity_xy(&first.world_dump, MOVER_ID);
    assert!(
        mover_x > 9.0,
        "600 frames of move_x=1 must advance the mover; x={mover_x}"
    );
    let (_, box_y) = entity_xy(&first.world_dump, BOX_ID);
    assert!(
        box_y < f64::from(BOX_START_Y) - 0.5,
        "dynamic box must fall over 600 frames; y={box_y}"
    );

    let a = to_canonical_vec(&first.world_dump);
    let b = to_canonical_vec(&second.world_dump);
    assert_eq!(
        a, b,
        "final world_dump must match byte-for-byte (JSON canonical)"
    );
}

#[test]
fn replay_wrong_scene_hash_refuses_to_start_gs_ec_36() {
    let tmp = TempDir::new().expect("temp");
    let built = build_det_snapshot(tmp.path(), "p-m5-4-ec36");
    let verified = verify_snapshot(&built.manifest_path).expect("verify");
    let mut header = TapeHeader::from_verified(&verified);
    header.snapshot_hashes.scene = "ffffffffffffffff".into();

    let tape = tmp.path().join("bad_scene.tape.jsonl");
    write_hold_move_x_tape(&tape, &header, 1);

    let err = run_headless_frames_with(&built.manifest_path, 1, Some(&tape), None, false)
        .expect_err("mismatched scene hash must refuse to start");
    assert!(err.is_reject(), "{err}");
    let msg = err.to_string();
    assert!(msg.contains("GS-EC-36"), "expected GS-EC-36, got {msg}");
    assert!(
        msg.contains("snapshot_hashes.scene"),
        "expected scene field in reject, got {msg}"
    );
}

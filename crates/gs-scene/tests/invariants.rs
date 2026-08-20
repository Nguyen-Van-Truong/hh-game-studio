//! WP-M0-3 first-slice invariants (cargo test -p gs-scene).

use gs_scene::{
    Command, CrashPoint, DispatchRequest, Error, Session, Transform2D, DEFAULT_SCENE_ID,
};
use tempfile::TempDir;
use ulid::Ulid;

fn open_tmp() -> (TempDir, Session) {
    let dir = TempDir::new().expect("tempdir");
    let session = Session::open(dir.path()).expect("open");
    (dir, session)
}

fn cid() -> String {
    Ulid::new().to_string()
}

fn spawn(session: &mut Session, name: &str) -> gs_scene::Ack {
    session
        .dispatch(DispatchRequest::spawn(
            cid(),
            "act_01",
            DEFAULT_SCENE_ID,
            name,
        ))
        .expect("spawn")
}

#[test]
fn spawn_then_undo_restores_canonical_scene() {
    let (_dir, mut s) = open_tmp();
    let original = s.canonical_scene_bytes();
    spawn(&mut s, "hero");
    assert_eq!(s.document().entity_count(), 1);
    s.undo_last(&cid(), "act_01").expect("undo");
    assert_eq!(
        s.canonical_scene_bytes(),
        original,
        "scene bytes must match pre-spawn after undo"
    );
    assert_eq!(s.document().entity_count(), 0);
}

#[test]
fn nan_transform_rejected() {
    let (_dir, mut s) = open_tmp();
    let ack = spawn(&mut s, "npc");
    let id = ack.spawned_ids[0].clone();
    let mut t = Transform2D::identity();
    t.x = f32::NAN;
    let err = s
        .dispatch(DispatchRequest::set_transform(cid(), "act_01", id, t))
        .unwrap_err();
    match err {
        Error::Invalid { reason, .. } => {
            assert!(
                reason.contains("NaN") || reason.contains("finite"),
                "reason={reason}"
            );
        }
        other => panic!("expected Invalid, got {other:?}"),
    }
    assert_eq!(s.document().entity_count(), 1);
}

#[test]
fn reparent_cycle_rejected() {
    let (_dir, mut s) = open_tmp();
    let a = spawn(&mut s, "parent");
    let parent_id = a.spawned_ids[0].clone();
    let child = s
        .dispatch(DispatchRequest::new(
            cid(),
            "act_01",
            Command::entity_spawn(
                DEFAULT_SCENE_ID,
                Some("child".into()),
                Some(parent_id.clone()),
                Default::default(),
            ),
        ))
        .expect("child spawn");
    let child_id = child.spawned_ids[0].clone();
    let err = s
        .dispatch(DispatchRequest::reparent(
            cid(),
            "act_01",
            vec![parent_id],
            Some(child_id),
            false,
        ))
        .unwrap_err();
    assert!(matches!(err, Error::Cycle { .. }), "got {err:?}");
}

#[test]
fn command_id_retry_does_not_duplicate_entity() {
    let (_dir, mut s) = open_tmp();
    let command_id = cid();
    let req = DispatchRequest::spawn(command_id.clone(), "act_01", DEFAULT_SCENE_ID, "once");
    let a1 = s.dispatch(req.clone()).expect("first spawn");
    let a2 = s.dispatch(req).expect("retry");
    assert_eq!(a1, a2);
    assert_eq!(s.document().entity_count(), 1);
    assert_eq!(a1.spawned_ids.len(), 1);
}

#[test]
fn crash_a_mid_record_write() {
    let (dir, mut s) = open_tmp();
    let a1 = spawn(&mut s, "keep");
    assert_eq!(a1.revision, "r-000001");
    s.inject_crash(CrashPoint::MidRecordWrite);
    let err = s
        .dispatch(DispatchRequest::spawn(
            cid(),
            "act_01",
            DEFAULT_SCENE_ID,
            "lost",
        ))
        .unwrap_err();
    assert!(matches!(err, Error::Crash(CrashPoint::MidRecordWrite)));
    assert_eq!(s.last_ack().revision, "r-000001");
    assert_eq!(s.document().entity_count(), 1);

    let wal = std::fs::read_to_string(&s.paths().wal_file).unwrap();
    assert!(!wal.ends_with('\n'), "partial last line has no trailing LF");

    drop(s);
    let s2 = Session::open(dir.path()).expect("recover after (a)");
    assert_eq!(s2.last_ack().revision, "r-000001");
    assert_eq!(s2.last_ack().seq, 1);
    assert_eq!(s2.document().entity_count(), 1);
    assert_eq!(s2.document().revision_label(), "r-000001");

    let wal2 = std::fs::read_to_string(s2.paths().wal_file.as_path()).unwrap();
    assert!(wal2.ends_with('\n'));
    assert_eq!(wal2.lines().filter(|l| !l.is_empty()).count(), 1);
}

#[test]
fn crash_b_after_flush_before_apply() {
    let (dir, mut s) = open_tmp();
    spawn(&mut s, "keep");
    s.inject_crash(CrashPoint::AfterFlushBeforeApply);
    let err = s
        .dispatch(DispatchRequest::spawn(
            cid(),
            "act_01",
            DEFAULT_SCENE_ID,
            "unacked",
        ))
        .unwrap_err();
    assert!(matches!(
        err,
        Error::Crash(CrashPoint::AfterFlushBeforeApply)
    ));
    assert_eq!(s.document().entity_count(), 1, "in-memory apply skipped");
    assert_eq!(s.last_ack().revision, "r-000001");

    let wal = std::fs::read_to_string(s.paths().wal_file.as_path()).unwrap();
    assert!(
        wal.contains("unacked"),
        "flushed record is complete on disk"
    );
    assert_eq!(wal.lines().filter(|l| !l.is_empty()).count(), 2);

    drop(s);
    let s2 = Session::open(dir.path()).expect("recover after (b)");
    assert_eq!(s2.last_ack().revision, "r-000001");
    assert_eq!(s2.document().revision_label(), "r-000001");
    assert_eq!(
        s2.document().entity_count(),
        1,
        "un-ACK'd txn must not apply"
    );

    let wal2 = std::fs::read_to_string(s2.paths().wal_file.as_path()).unwrap();
    assert_eq!(
        wal2.lines().filter(|l| !l.is_empty()).count(),
        1,
        "un-ACK'd flushed record is cut, not replayed"
    );
}

#[test]
fn second_exclusive_open_fails() {
    let dir = TempDir::new().unwrap();
    let _s1 = Session::open(dir.path()).unwrap();
    let err = Session::open(dir.path()).unwrap_err();
    assert!(matches!(err, Error::AlreadyOpen));
    let ro = Session::open_read_only(dir.path()).expect("read-only fallback");
    assert!(ro.is_read_only());
    let err = Session::open_read_only(dir.path())
        .unwrap()
        .dispatch(DispatchRequest::spawn(
            cid(),
            "act_01",
            DEFAULT_SCENE_ID,
            "nope",
        ))
        .unwrap_err();
    assert!(matches!(err, Error::ReadOnly));
}

#[test]
fn scale_zero_and_name_too_long_rejected() {
    let (_dir, mut s) = open_tmp();
    let ack = spawn(&mut s, "npc");
    let id = ack.spawned_ids[0].clone();
    let mut t = Transform2D::identity();
    t.sx = 0.0;
    let err = s
        .dispatch(DispatchRequest::set_transform(
            cid(),
            "act_01",
            id.clone(),
            t,
        ))
        .unwrap_err();
    match err {
        Error::Invalid { reason, .. } => {
            assert!(reason.contains("scale") || reason.contains("0"), "{reason}");
        }
        other => panic!("expected Invalid, got {other:?}"),
    }

    let huge = "x".repeat(10 * 1024 * 1024);
    let err = s
        .dispatch(DispatchRequest::new(
            cid(),
            "act_01",
            Command::entity_rename(id, huge),
        ))
        .unwrap_err();
    match err {
        Error::Invalid { reason, .. } => {
            assert!(
                reason.contains("longer") || reason.contains("256"),
                "{reason}"
            );
        }
        other => panic!("expected Invalid, got {other:?}"),
    }
}

#[test]
fn bare_string_asset_ref_rejected() {
    use serde_json::json;
    use std::collections::BTreeMap;

    let (_dir, mut s) = open_tmp();
    let mut comps = BTreeMap::new();
    comps.insert(
        "Sprite".into(),
        json!({
            "asset": "a_000001",
            "color": [1,1,1,1],
            "flip_x": false,
            "flip_y": false,
            "pivot": [0.5, 0.0]
        }),
    );
    let err = s
        .dispatch(DispatchRequest::new(
            cid(),
            "act_01",
            Command::entity_spawn(DEFAULT_SCENE_ID, Some("bad".into()), None, comps),
        ))
        .unwrap_err();
    match err {
        Error::Invalid { reason, .. } => {
            assert!(
                reason.contains("bare") || reason.contains("$asset"),
                "{reason}"
            );
        }
        other => panic!("expected Invalid, got {other:?}"),
    }
}

#[test]
fn command_id_retry_survives_autosave_restart() {
    let (dir, mut s) = open_tmp();
    let command_id = cid();
    let req = DispatchRequest::spawn(command_id.clone(), "act_01", DEFAULT_SCENE_ID, "once");
    let a1 = s.dispatch(req.clone()).expect("first");
    s.autosave().expect("autosave");
    drop(s);
    let mut s2 = Session::open(dir.path()).expect("reopen");
    let a2 = s2.dispatch(req).expect("retry after restart");
    assert_eq!(a1, a2);
    assert_eq!(s2.document().entity_count(), 1);
}

#[test]
fn dry_run_does_not_wal_or_apply() {
    let (_dir, mut s) = open_tmp();
    let before = s.canonical_scene_bytes();
    let ack = s
        .dispatch(DispatchRequest::spawn(cid(), "act_01", DEFAULT_SCENE_ID, "ghost").as_dry_run())
        .expect("dry_run");
    assert_eq!(ack.spawned_ids.len(), 1);
    assert_eq!(s.document().entity_count(), 0);
    assert_eq!(s.canonical_scene_bytes(), before);
    assert_eq!(s.last_ack().seq, 0);
}

#[test]
fn disk_full_fsync_fail_rejects_mutating() {
    let (_dir, mut s) = open_tmp();
    spawn(&mut s, "keep");
    s.inject_crash(CrashPoint::FsyncFail);
    let err = s
        .dispatch(DispatchRequest::spawn(
            cid(),
            "act_01",
            DEFAULT_SCENE_ID,
            "nope",
        ))
        .unwrap_err();
    assert!(matches!(err, Error::DiskFull { .. }));
    assert_eq!(s.document().entity_count(), 1);
    let err = s
        .dispatch(DispatchRequest::spawn(
            cid(),
            "act_01",
            DEFAULT_SCENE_ID,
            "still_nope",
        ))
        .unwrap_err();
    assert!(matches!(err, Error::DiskFull { .. }));
}

#[test]
fn i6_corrupt_middle_stops() {
    let (dir, mut s) = open_tmp();
    spawn(&mut s, "a");
    spawn(&mut s, "b");
    spawn(&mut s, "c");
    let wal_path = s.paths().wal_file.clone();
    drop(s);

    let wal = std::fs::read_to_string(&wal_path).unwrap();
    let mut lines: Vec<String> = wal.lines().map(str::to_string).collect();
    assert_eq!(lines.len(), 3);
    lines[1] = r#"{"seq":2,"kind":"txn","txn_id":"t-000002","command_id":"x","actor_id":"a","base_revision":"r-000001","new_revision":"r-000002","commands":[],"inverses":[],"schema_version":1,"ts":"0","crc32":"deadbeef"}"#.into();
    std::fs::write(&wal_path, format!("{}\n", lines.join("\n"))).unwrap();

    let err = Session::open(dir.path()).unwrap_err();
    assert!(
        matches!(err, Error::CorruptMiddle { .. }),
        "middle crc fail must stop, got {err:?}"
    );
}

#[test]
fn git_conflict_marker_rejected() {
    let dir = tempfile::TempDir::new().unwrap();
    let s = Session::open(dir.path()).unwrap();
    drop(s);
    let scene = dir.path().join("scenes").join("main.gscene.json");
    std::fs::create_dir_all(scene.parent().unwrap()).unwrap();
    std::fs::write(
        dir.path().join("project.json"),
        r#"{"schema_version":1,"revision":0,"next_entity":1,"next_asset":1}"#,
    )
    .unwrap();
    std::fs::write(
        &scene,
        "{\n<<<<<<< HEAD\n  \"mode\": \"2d\"\n=======\n  \"mode\": \"2d\"\n>>>>>>> other\n}\n",
    )
    .unwrap();
    let err = Session::open(dir.path()).unwrap_err();
    assert!(matches!(err, Error::ConflictMarker { .. }), "got {err:?}");
}

#[test]
fn crash_c_mid_tmp_rename_autosave() {
    let (dir, mut s) = open_tmp();
    spawn(&mut s, "keep");
    s.autosave().expect("first autosave");
    let a2 = spawn(&mut s, "after_save");
    assert_eq!(a2.revision, "r-000002");

    s.inject_crash(CrashPoint::MidAutosaveRename);
    let err = s.autosave().unwrap_err();
    assert!(matches!(err, Error::Crash(CrashPoint::MidAutosaveRename)));

    let autosave_dir = s.paths().autosave_dir.clone();
    let tmps: Vec<_> = std::fs::read_dir(&autosave_dir)
        .unwrap()
        .filter_map(|e| e.ok())
        .filter(|e| e.file_name().to_string_lossy().ends_with(".tmp"))
        .collect();
    assert!(
        !tmps.is_empty(),
        "crash (c) must leave tmp files (rename never ran)"
    );

    drop(s);
    let s2 = Session::open(dir.path()).expect("recover after (c)");
    assert_eq!(s2.last_ack().revision, "r-000002");
    assert_eq!(s2.document().revision_label(), "r-000002");
    assert_eq!(s2.document().entity_count(), 2, "no lost ACK'd txn");
}

#[test]
fn crash_d_between_two_records() {
    let (dir, mut s) = open_tmp();
    let a1 = spawn(&mut s, "first");
    assert_eq!(a1.revision, "r-000001");

    s.inject_crash(CrashPoint::BetweenRecords);
    let err = s
        .dispatch(DispatchRequest::spawn(
            cid(),
            "act_01",
            DEFAULT_SCENE_ID,
            "second",
        ))
        .unwrap_err();
    assert!(matches!(err, Error::Crash(CrashPoint::BetweenRecords)));
    assert_eq!(s.document().entity_count(), 1);
    assert_eq!(s.last_ack().revision, "r-000001");

    drop(s);
    let mut s2 = Session::open(dir.path()).expect("recover after (d)");
    assert_eq!(s2.last_ack().revision, "r-000001");
    assert_eq!(s2.document().entity_count(), 1);
    let a2 = spawn(&mut s2, "second");
    assert_eq!(a2.revision, "r-000002");
}

#[test]
fn blueprint_stamp_independent_trees() {
    use serde_json::json;
    use std::collections::BTreeMap;

    let (dir, mut s) = open_tmp();
    let parent = spawn(&mut s, "root");
    let parent_id = parent.spawned_ids[0].clone();
    s.dispatch(DispatchRequest::new(
        cid(),
        "act_01",
        Command::entity_spawn(
            DEFAULT_SCENE_ID,
            Some("child".into()),
            Some(parent_id.clone()),
            BTreeMap::new(),
        ),
    ))
    .expect("child");

    s.dispatch(DispatchRequest::new(
        cid(),
        "act_01",
        Command::blueprint_create(parent_id, "blueprints/mob.gbp.json"),
    ))
    .expect("create");

    let gbp_path = dir.path().join("blueprints").join("mob.gbp.json");
    let gbp_text = std::fs::read_to_string(&gbp_path).expect("gbp");
    assert!(gbp_text.contains("\"b_1\""), "local ids not array index");
    assert!(gbp_text.contains("\"b_2\""));

    let i1 = s
        .dispatch(DispatchRequest::new(
            cid(),
            "act_01",
            Command::blueprint_instantiate(
                "blueprints/mob.gbp.json",
                Some(json!({"x": 3.0, "y": 4.0})),
                Some("A_".into()),
            ),
        ))
        .expect("inst1");
    let i2 = s
        .dispatch(DispatchRequest::new(
            cid(),
            "act_01",
            Command::blueprint_instantiate("blueprints/mob.gbp.json", None, Some("B_".into())),
        ))
        .expect("inst2");
    assert_eq!(i1.spawned_ids.len(), 2);
    assert_eq!(i2.spawned_ids.len(), 2);
    assert_ne!(i1.spawned_ids, i2.spawned_ids);

    let name_a = s
        .document()
        .entity(gs_scene::parse_entity_id(&i1.spawned_ids[0]).unwrap())
        .and_then(|e| e.name.as_ref())
        .map(|n| n.value.clone())
        .unwrap();
    assert!(name_a.starts_with("A_"), "name_prefix applied: {name_a}");

    let mut edited = serde_json::from_str::<serde_json::Value>(&gbp_text).unwrap();
    edited["entities"][0]["components"]["Name"]["value"] = json!("CHANGED");
    std::fs::write(&gbp_path, serde_json::to_string_pretty(&edited).unwrap()).unwrap();

    let name_after = s
        .document()
        .entity(gs_scene::parse_entity_id(&i1.spawned_ids[0]).unwrap())
        .and_then(|e| e.name.as_ref())
        .map(|n| n.value.clone())
        .unwrap();
    assert_eq!(name_after, name_a, "editing .gbp must not change stamps");

    let before_extra = s.canonical_scene_bytes();
    spawn(&mut s, "temp");
    s.undo_last(&cid(), "act_01").expect("undo");
    assert_eq!(
        s.canonical_scene_bytes(),
        before_extra,
        "spawn+undo still restores canonical scene bytes"
    );
}

#[test]
fn unknown_fields_round_trip_nested() {
    use gs_scene::Document;
    use serde_json::json;

    let scene = json!({
        "schema_version": 1,
        "mode": "2d",
        "extra_scene": { "note": "top" },
        "entities": [{
            "id": "e_000001",
            "parent": null,
            "order": 0,
            "note": "entity-level",
            "components": {
                "Name": { "value": "hero", "nick": "h" },
                "Transform2D": {
                    "x": 1.0, "y": 2.0, "rot": 0.0, "sx": 1.0, "sy": 1.0, "z_index": 0,
                    "debug": { "gizmo": true }
                },
                "Sprite": {
                    "asset": { "$asset": "a_000001" },
                    "color": [1.0, 1.0, 1.0, 1.0],
                    "flip_x": false,
                    "flip_y": false,
                    "pivot": [0.5, 0.0],
                    "meta": { "author": "qa" }
                },
                "CustomFx": { "amp": 2 }
            }
        }]
    });
    let parsed = gs_scene::Scene::from_file(serde_json::from_value(scene).unwrap()).unwrap();
    let bytes = Document {
        scene: parsed,
        ..Document::default()
    }
    .canonical_scene_bytes();
    let text = String::from_utf8(bytes).unwrap();
    assert!(text.contains("\"extra_scene\""), "{text}");
    assert!(text.contains("\"note\""));
    assert!(text.contains("\"nick\""));
    assert!(text.contains("\"debug\""));
    assert!(text.contains("\"meta\""));
    assert!(text.contains("\"CustomFx\""));
    assert!(text.contains("\"author\""));
}

#[test]
fn all_registry_components_store_on_spawn() {
    use serde_json::json;
    use std::collections::BTreeMap;

    let (_dir, mut s) = open_tmp();
    let mut comps = BTreeMap::new();
    comps.insert("Tags".into(), json!({ "values": ["npc", "mob"] }));
    comps.insert(
        "Sprite".into(),
        json!({
            "asset": { "$asset": "a_000001" },
            "color": [1.0, 1.0, 1.0, 1.0],
            "flip_x": false,
            "flip_y": false,
            "pivot": [0.5, 0.0]
        }),
    );
    comps.insert(
        "AnimFlipbook".into(),
        json!({
            "frames": [{ "$asset": "a_000002" }],
            "fps": 12.0,
            "playing": true,
            "loop": true,
            "frame_index": 0
        }),
    );
    comps.insert(
        "Camera2D".into(),
        json!({ "ortho_height": 10.0, "active": true }),
    );
    comps.insert(
        "RigidBody2D".into(),
        json!({
            "kind": "dynamic",
            "ccd": false,
            "gravity_scale": 1.0,
            "fixed_rotation": false,
            "linear_damping": 0.1
        }),
    );
    comps.insert(
        "Collider2D".into(),
        json!({
            "shape": { "box": { "w": 1.0, "h": 2.0 } },
            "is_sensor": false,
            "offset": [0.0, 1.0],
            "layer": 1,
            "mask": 4294967295u32,
            "friction": 0.5,
            "restitution": 0.0
        }),
    );
    comps.insert(
        "Tilemap".into(),
        json!({
            "tileset": { "$asset": "a_000003" },
            "cell_size": [1.0, 1.0],
            "layers": [{ "name": "ground", "solid": true, "cells": [[0, 0, 3, 1]] }]
        }),
    );
    comps.insert(
        "Text2D".into(),
        json!({
            "text": "hi",
            "font": null,
            "size_pt": 16.0,
            "color": [1.0, 1.0, 1.0, 1.0],
            "align": "left"
        }),
    );
    comps.insert(
        "AudioSource".into(),
        json!({
            "asset": { "$asset": "a_000004" },
            "volume": 1.0,
            "pan": 0.0,
            "loop": false,
            "autoplay": false
        }),
    );
    comps.insert(
        "Script".into(),
        json!({
            "file": "scripts/door.luau",
            "props": {
                "locked": true,
                "target": { "$entity": "e_000001" },
                "icon": { "$asset": "a_000005" }
            }
        }),
    );
    comps.insert("Visibility".into(), json!({ "visible": true }));

    let ack = s
        .dispatch(DispatchRequest::new(
            cid(),
            "act_01",
            Command::entity_spawn(DEFAULT_SCENE_ID, Some("full".into()), None, comps),
        ))
        .expect("spawn full registry");
    let id = gs_scene::parse_entity_id(&ack.spawned_ids[0]).unwrap();
    let ent = s.document().entity(id).expect("entity");
    assert!(ent.tags.is_some());
    assert!(ent.extra.sprite.is_some());
    assert!(ent.extra.anim_flipbook.is_some());
    assert!(ent.extra.camera.is_some());
    assert!(ent.extra.rigid_body.is_some());
    assert!(ent.extra.collider.is_some());
    assert!(ent.extra.tilemap.is_some());
    assert!(ent.extra.text.is_some());
    assert!(ent.extra.audio.is_some());
    assert!(ent.extra.script.is_some());
    assert!(ent.extra.visibility.is_some());
    let bytes = String::from_utf8(s.canonical_scene_bytes()).unwrap();
    assert!(bytes.contains("Camera2D"));
    assert!(bytes.contains("Tilemap"));
    assert!(bytes.contains("$entity"));
}

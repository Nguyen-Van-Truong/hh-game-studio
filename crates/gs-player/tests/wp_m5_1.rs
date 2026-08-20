//! WP-M5-1: input tape record/replay + header check (MASTER 6.2 / 6.4 / T5.1 / GS-EC-36).

use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

use gs_player::{
    append_action, load_tape, record_input_frames, tape_actions_for_frame, validate_header,
    validate_header_force, write_header, Manifest, SnapshotHashes, TapeEvent, TapeHeader,
    VerifiedSnapshot,
};
use gs_runtime_core::{InputFrame, FIXED_DT};
use tempfile::TempDir;

fn fake_hashes() -> SnapshotHashes {
    SnapshotHashes {
        scene: "aa".into(),
        scripts: "bb".into(),
        assets: "cc".into(),
        inputmap: "dd".into(),
    }
}

fn fake_verified() -> VerifiedSnapshot {
    let hashes = fake_hashes();
    VerifiedSnapshot {
        play_id: "p_tape".into(),
        document_revision: "r-000001".into(),
        manifest: Manifest {
            play_id: "p_tape".into(),
            document_revision: "r-000001".into(),
            engine_ver: "0.1.0-m5-1".into(),
            protocol_ver: "1.0".into(),
            seed: 42,
            hashes,
            created_at: "2026-08-17T00:00:00Z".into(),
            actor: "act_test".into(),
        },
    }
}

fn matching_header(verified: &VerifiedSnapshot) -> TapeHeader {
    TapeHeader::from_verified(verified)
}

fn write_line(path: &Path, line: &str) {
    use std::io::Write;
    let mut file = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .expect("append");
    writeln!(file, "{line}").expect("writeln");
}

#[test]
fn validate_header_accepts_matching_hashes() {
    let verified = fake_verified();
    let header = matching_header(&verified);
    let dir = TempDir::new().expect("temp");
    let path = dir.path().join("ok.tape.jsonl");
    write_header(&path, &header).expect("write header");
    let loaded = load_tape(&path).expect("load");
    validate_header(&loaded.header, &verified).expect("header matches verified snapshot");
}

#[test]
fn validate_header_rejects_scene_hash_mismatch() {
    let verified = fake_verified();
    let mut header = matching_header(&verified);
    header.snapshot_hashes.scene = "ff".into();
    let err = validate_header(&header, &verified).expect_err("scene hash must reject");
    assert!(err.is_reject(), "{err}");
    let msg = err.to_string();
    assert!(
        msg.contains("GS-EC-36"),
        "expected GS-EC-36 in reject, got {msg}"
    );
    assert!(
        msg.contains("snapshot_hashes.scene"),
        "expected scene field in reject, got {msg}"
    );
}

#[test]
fn validate_header_force_sets_evidence_ok_false() {
    let verified = fake_verified();
    let mut header = matching_header(&verified);
    header.engine_build = "other-build".into();
    let check = validate_header_force(&header, &verified);
    assert!(!check.evidence_ok);
    let warning = check.warning.expect("loud warning");
    assert!(
        warning.contains("GS-EC-36"),
        "expected GS-EC-36 in warning, got {warning}"
    );
    assert!(
        warning.contains("evidence_ok=false"),
        "expected evidence_ok=false in warning, got {warning}"
    );
    assert!(
        warning.contains("--force"),
        "expected --force in warning, got {warning}"
    );

    let ok = validate_header_force(&matching_header(&verified), &verified);
    assert!(ok.evidence_ok);
    assert!(ok.warning.is_none());
}

#[test]
fn tape_actions_for_frame_three_frames() {
    let events = vec![
        TapeEvent {
            frame: 0,
            action: "move_x".into(),
            value: 1.0,
        },
        TapeEvent {
            frame: 2,
            action: "move_x".into(),
            value: -1.0,
        },
        TapeEvent {
            frame: 2,
            action: "interact".into(),
            value: 1.0,
        },
    ];
    let f0 = tape_actions_for_frame(&events, 0);
    assert_eq!(f0.get("move_x"), Some(&1.0));
    assert_eq!(f0.len(), 1);

    let f1 = tape_actions_for_frame(&events, 1);
    assert!(f1.is_empty(), "frame 1 has no lines");

    let f2 = tape_actions_for_frame(&events, 2);
    assert_eq!(f2.get("move_x"), Some(&-1.0));
    assert_eq!(f2.get("interact"), Some(&1.0));
    assert_eq!(f2.len(), 2);
}

#[test]
fn record_input_frames_round_trips() {
    let verified = fake_verified();
    let header = matching_header(&verified);
    assert!((header.fixed_dt - FIXED_DT).abs() < f64::EPSILON);

    let frames = [
        InputFrame {
            actions: BTreeMap::from([("jump".into(), 0.0), ("move_x".into(), 1.0)]),
        },
        InputFrame {
            actions: BTreeMap::from([("jump".into(), 1.0), ("move_x".into(), 1.0)]),
        },
        InputFrame {
            actions: BTreeMap::from([("jump".into(), 0.0), ("move_x".into(), 0.0)]),
        },
    ];

    let dir = TempDir::new().expect("temp");
    let path = dir.path().join("rec.tape.jsonl");
    record_input_frames(&path, &header, &frames).expect("record");

    let text = fs::read_to_string(&path).expect("read tape");
    let mut lines = text.lines().filter(|l| !l.trim().is_empty());
    let first = lines.next().expect("header line");
    let parsed_header: TapeHeader = serde_json::from_str(first).expect("header json");
    assert_eq!(parsed_header, header);
    let body: Vec<&str> = lines.collect();
    assert!(
        !body.is_empty(),
        "expected action lines after header, got:\n{text}"
    );
    for line in &body {
        let event: TapeEvent = serde_json::from_str(line).expect("action json");
        assert!(event.frame <= 2, "frame {}", event.frame);
        assert!(event.action == "move_x" || event.action == "jump");
    }

    let loaded = load_tape(&path).expect("reload");
    assert_eq!(loaded.header, header);

    let mut expected = Vec::new();
    let mut last = BTreeMap::<String, f32>::new();
    for (i, frame) in frames.iter().enumerate() {
        for (name, value) in &frame.actions {
            let prev = last.get(name).copied().unwrap_or(0.0);
            if *value != 0.0 || *value != prev {
                expected.push(TapeEvent {
                    frame: i as u64,
                    action: name.clone(),
                    value: f64::from(*value),
                });
                last.insert(name.clone(), *value);
            }
        }
    }
    assert_eq!(loaded.events, expected);

    // Public append_action stays compatible with the same JSONL body format.
    let extra = dir.path().join("extra.tape.jsonl");
    write_header(&extra, &header).expect("header");
    append_action(
        &extra,
        &TapeEvent {
            frame: 0,
            action: "move_x".into(),
            value: -1.0,
        },
    )
    .expect("append");
    write_line(&extra, "");
    let extra_loaded = load_tape(&extra).expect("load extra");
    assert_eq!(extra_loaded.events.len(), 1);
    assert_eq!(extra_loaded.events[0].action, "move_x");
    assert_eq!(extra_loaded.events[0].value, -1.0);
}

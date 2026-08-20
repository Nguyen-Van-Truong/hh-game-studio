//! WP-M3-4 document/WAL half: inputmap.get / inputmap.set.

use gs_scene::{
    default_inputmap, Command, DispatchRequest, Document, Error, Session, INPUTMAP_REL,
};
use serde_json::{json, Value};
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

fn dispatch(session: &mut Session, command: Command) -> gs_scene::Ack {
    session
        .dispatch(DispatchRequest::new(cid(), "act_01", command))
        .expect("dispatch")
}

fn sample_actions() -> Value {
    json!([
        {
            "name": "move_x",
            "type": "axis",
            "keys": [["A", -1.0], ["D", 1.0]],
            "gamepad_axis": "left_x"
        },
        {
            "name": "jump",
            "type": "button",
            "keys": ["Space"],
            "gamepad_button": "south"
        }
    ])
}

#[test]
fn set_then_get_returns_actions() {
    let (_dir, mut s) = open_tmp();
    assert_eq!(
        s.read_inputmap().expect("default"),
        default_inputmap(),
        "missing file must return the 6.4 sample"
    );
    let err = s
        .dispatch(DispatchRequest::new(
            cid(),
            "act_01",
            Command::new("inputmap.get", json!({})),
        ))
        .unwrap_err();
    match err {
        Error::Invalid { method, reason } => {
            assert_eq!(method, "inputmap.get");
            assert!(reason.contains("read-only"), "reason={reason}");
        }
        other => panic!("expected Invalid, got {other:?}"),
    }

    let actions = sample_actions();
    dispatch(&mut s, Command::inputmap_set(actions.clone()));
    let got = s.read_inputmap().expect("get after set");
    assert_eq!(got["actions"], actions);
}

#[test]
fn undo_restores_previous_map() {
    let (_dir, mut s) = open_tmp();
    let first = sample_actions();
    let second = json!([
        {
            "name": "look_x",
            "type": "axis",
            "keys": [["Left", -1.0], ["Right", 1.0]],
            "gamepad_axis": "right_x"
        }
    ]);
    dispatch(&mut s, Command::inputmap_set(first.clone()));
    dispatch(&mut s, Command::inputmap_set(second.clone()));
    assert_eq!(s.read_inputmap().expect("after second")["actions"], second);
    s.undo_last(&cid(), "act_01").expect("undo second set");
    assert_eq!(s.read_inputmap().expect("restored first")["actions"], first);

    let (dir2, mut s2) = open_tmp();
    dispatch(&mut s2, Command::inputmap_set(first));
    s2.undo_last(&cid(), "act_01").expect("undo first set");
    assert_eq!(
        s2.read_inputmap().expect("default after undo"),
        default_inputmap()
    );
    assert!(
        !dir2.path().join(INPUTMAP_REL).exists(),
        "undo of the first set must remove the file so get returns the default"
    );
}

#[test]
fn invalid_type_and_duplicate_name_rejected() {
    let (dir, mut s) = open_tmp();
    let bad_type = json!([{
        "name": "move_x",
        "type": "trigger",
        "keys": [["A", -1.0]]
    }]);
    let err = s
        .dispatch(DispatchRequest::new(
            cid(),
            "act_01",
            Command::inputmap_set(bad_type),
        ))
        .unwrap_err();
    match err {
        Error::Invalid { method, reason } => {
            assert_eq!(method, "inputmap.set");
            assert!(
                reason.contains("axis or button") || reason.contains("type"),
                "reason={reason}"
            );
        }
        other => panic!("expected Invalid for type, got {other:?}"),
    }

    let dup = json!([
        {"name": "move_x", "type": "button", "keys": ["A"]},
        {"name": "move_x", "type": "button", "keys": ["D"]}
    ]);
    let err = s
        .dispatch(DispatchRequest::new(
            cid(),
            "act_01",
            Command::inputmap_set(dup),
        ))
        .unwrap_err();
    match err {
        Error::Invalid { method, reason } => {
            assert_eq!(method, "inputmap.set");
            assert!(reason.contains("duplicate"), "reason={reason}");
        }
        other => panic!("expected Invalid for duplicate, got {other:?}"),
    }
    assert!(
        !dir.path().join(INPUTMAP_REL).exists(),
        "rejected set must not create the file"
    );
}

#[test]
fn apply_without_persist_does_not_write_inputmap_file() {
    let dir = TempDir::new().expect("tempdir");
    let doc = Document {
        project_root: Some(dir.path().to_path_buf()),
        ..Document::default()
    };
    let actions = sample_actions();
    let planned = doc
        .plan_txn(&[Command::inputmap_set(actions.clone())])
        .expect("plan");
    assert!(
        !dir.path().join(INPUTMAP_REL).exists(),
        "plan_txn/apply must not write inputmap.json (persist is after WAL)"
    );
    planned
        .document
        .persist_inputmap_file(&planned.commands[0])
        .expect("persist after plan");
    let written: Value = serde_json::from_str(
        &std::fs::read_to_string(dir.path().join(INPUTMAP_REL)).expect("read"),
    )
    .expect("json");
    assert_eq!(written["actions"], actions);
}

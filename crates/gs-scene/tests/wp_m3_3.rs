//! WP-M3-3 document/WAL half: script.create / set_source / get_source / ingest_external.

use gs_scene::{
    Command, CrashPoint, DispatchRequest, Document, Error, Session, DEFAULT_SCRIPT_SOURCE,
    MAX_SCRIPT_SOURCE_BYTES,
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

fn dispatch(session: &mut Session, command: Command) -> gs_scene::Ack {
    session
        .dispatch(DispatchRequest::new(cid(), "act_01", command))
        .expect("dispatch")
}

fn script_abs(root: &std::path::Path, rel: &str) -> std::path::PathBuf {
    root.join(rel)
}

#[test]
fn set_source_writes_file_undo_restores_old_text() {
    let (dir, mut s) = open_tmp();
    let path = "scripts/hero.luau";
    dispatch(
        &mut s,
        Command::script_set_source(path, "local old = true\n"),
    );
    assert_eq!(
        s.read_script_source(path).expect("get after first write"),
        "local old = true\n"
    );
    dispatch(
        &mut s,
        Command::script_set_source(path, "local new = true\n"),
    );
    assert_eq!(
        std::fs::read_to_string(script_abs(dir.path(), path)).unwrap(),
        "local new = true\n"
    );
    s.undo_last(&cid(), "act_01").expect("undo set_source");
    assert_eq!(
        s.read_script_source(path).expect("restored"),
        "local old = true\n"
    );
}

#[test]
fn script_path_escape_rejected() {
    let (_dir, mut s) = open_tmp();
    for bad in ["../secret.luau", "scripts/../../x.luau"] {
        let err = s
            .dispatch(DispatchRequest::new(
                cid(),
                "act_01",
                Command::script_set_source(bad, "print(1)\n"),
            ))
            .unwrap_err();
        assert!(
            matches!(err, Error::PathEscapesRoot { .. }),
            "expected PathEscapesRoot for {bad}, got {err:?}"
        );
    }
}

#[test]
fn set_source_rejects_source_over_256kb() {
    let (_dir, mut s) = open_tmp();
    let too_big = "x".repeat(MAX_SCRIPT_SOURCE_BYTES + 1);
    let err = s
        .dispatch(DispatchRequest::new(
            cid(),
            "act_01",
            Command::script_set_source("scripts/big.luau", too_big),
        ))
        .unwrap_err();
    match err {
        Error::Invalid { method, reason } => {
            assert_eq!(method, "script.set_source");
            assert!(
                reason.contains(&MAX_SCRIPT_SOURCE_BYTES.to_string()) || reason.contains("exceeds"),
                "reason={reason}"
            );
        }
        other => panic!("expected Invalid, got {other:?}"),
    }
}

#[test]
fn ingest_external_with_previous_source_undo_restores() {
    let (dir, mut s) = open_tmp();
    let path = "scripts/watch.luau";
    dispatch(&mut s, Command::script_set_source(path, "previous\n"));
    std::fs::write(script_abs(dir.path(), path), "external\n").expect("external edit");
    assert_eq!(
        std::fs::read_to_string(script_abs(dir.path(), path)).unwrap(),
        "external\n"
    );
    let ack = s
        .dispatch(DispatchRequest::new(
            cid(),
            "system:file-watch",
            Command::script_ingest_external(path, Some("previous\n".into())),
        ))
        .expect("ingest_external");
    assert!(ack.seq >= 2, "ingest must commit a WAL record");
    assert_eq!(
        s.read_script_source(path).expect("after ingest"),
        "external\n"
    );
    s.undo_last(&cid(), "act_01").expect("undo ingest");
    assert_eq!(
        s.read_script_source(path).expect("undo previous_source"),
        "previous\n"
    );
}

#[test]
fn create_then_get_source_returns_template() {
    let (_dir, mut s) = open_tmp();
    let path = "scripts/new_script.luau";
    dispatch(&mut s, Command::script_create(path, None));
    assert_eq!(
        s.read_script_source(path).expect("get_source"),
        DEFAULT_SCRIPT_SOURCE
    );
}

#[test]
fn apply_without_persist_does_not_write_script_file() {
    let dir = TempDir::new().expect("tempdir");
    let doc = Document {
        project_root: Some(dir.path().to_path_buf()),
        ..Document::default()
    };
    let path = "scripts/planned.luau";
    let planned = doc
        .plan_txn(&[Command::script_set_source(path, "must not land\n")])
        .expect("plan");
    assert!(
        !script_abs(dir.path(), path).exists(),
        "plan_txn/apply must not write the .luau file (persist is after WAL)"
    );
    planned
        .document
        .persist_script_file(&planned.commands[0])
        .expect("persist after plan");
    assert_eq!(
        std::fs::read_to_string(script_abs(dir.path(), path)).unwrap(),
        "must not land\n"
    );
}

#[test]
fn crash_after_flush_before_apply_does_not_write_script_file() {
    let (dir, mut s) = open_tmp();
    let path = "scripts/crash.luau";
    dispatch(&mut s, Command::script_set_source(path, "stable\n"));
    s.inject_crash(CrashPoint::AfterFlushBeforeApply);
    let err = s
        .dispatch(DispatchRequest::new(
            cid(),
            "act_01",
            Command::script_set_source(path, "lost\n"),
        ))
        .unwrap_err();
    assert!(matches!(
        err,
        Error::Crash(CrashPoint::AfterFlushBeforeApply)
    ));
    assert_eq!(
        std::fs::read_to_string(script_abs(dir.path(), path)).unwrap(),
        "stable\n",
        "persist runs after apply; crash before apply must leave the file unchanged"
    );
}

#[test]
fn create_does_not_overwrite_existing_file() {
    let (dir, mut s) = open_tmp();
    let path = "scripts/once.luau";
    dispatch(&mut s, Command::script_create(path, None));
    let err = s
        .dispatch(DispatchRequest::new(
            cid(),
            "act_01",
            Command::script_create(path, None),
        ))
        .unwrap_err();
    match err {
        Error::Invalid { method, reason } => {
            assert_eq!(method, "script.create");
            assert!(reason.contains("exists"), "reason={reason}");
        }
        other => panic!("expected Invalid, got {other:?}"),
    }
    assert_eq!(
        std::fs::read_to_string(script_abs(dir.path(), path)).unwrap(),
        DEFAULT_SCRIPT_SOURCE
    );
}

#[test]
fn get_source_missing_file_is_not_found() {
    let (_dir, s) = open_tmp();
    let err = s.read_script_source("scripts/missing.luau").unwrap_err();
    assert!(matches!(err, Error::NotFound(p) if p == "scripts/missing.luau"));
}

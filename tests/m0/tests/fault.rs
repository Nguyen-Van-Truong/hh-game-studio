//! Simulated crash / fail-stop harness (MASTER 5.5, GS-EC-38 / 39).
//!
//! These tests call [`gs_scene::Session::inject_crash`]. They reconstruct
//! on-disk WAL/autosave state the same way a kill would, but they are **not**
//! a real `kill -9` of a child process.

use gs_scene::{CrashPoint, DispatchRequest, Error, Session, DEFAULT_SCENE_ID};
use m0::{cid, open_session, spawn_session};

#[test]
fn crash_a_mid_record_write() {
    let (dir, mut s) = open_session();
    let a1 = spawn_session(&mut s, "keep");
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
}

#[test]
fn crash_b_after_flush_before_apply() {
    let (dir, mut s) = open_session();
    spawn_session(&mut s, "keep");
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

    drop(s);
    let s2 = Session::open(dir.path()).expect("recover after (b)");
    assert_eq!(s2.last_ack().revision, "r-000001");
    assert_eq!(
        s2.document().entity_count(),
        1,
        "un-ACK'd txn must not apply"
    );
}

#[test]
fn crash_c_mid_tmp_rename_autosave() {
    let (dir, mut s) = open_session();
    spawn_session(&mut s, "keep");
    s.autosave().expect("first autosave");
    let a2 = spawn_session(&mut s, "after_save");
    assert_eq!(a2.revision, "r-000002");

    s.inject_crash(CrashPoint::MidAutosaveRename);
    let err = s.autosave().unwrap_err();
    assert!(matches!(err, Error::Crash(CrashPoint::MidAutosaveRename)));

    drop(s);
    let s2 = Session::open(dir.path()).expect("recover after (c)");
    assert_eq!(s2.last_ack().revision, "r-000002");
    assert_eq!(s2.document().entity_count(), 2, "no lost ACK'd txn");
}

#[test]
fn crash_d_between_two_records() {
    let (dir, mut s) = open_session();
    let a1 = spawn_session(&mut s, "first");
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
    let a2 = spawn_session(&mut s2, "second");
    assert_eq!(a2.revision, "r-000002");
}

#[test]
fn disk_full_fsync_fail_rejects_mutating() {
    let (_dir, mut s) = open_session();
    spawn_session(&mut s, "keep");
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

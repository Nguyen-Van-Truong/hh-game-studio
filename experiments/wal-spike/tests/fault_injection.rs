//! Four MASTER 5.5 / GS-EC-38 crash points. Simulation matches the durable
//! on-disk state of a kill at that instant (no real kill -9 required on Windows).

use serde_json::json;
use std::fs;
use tempfile::TempDir;
use wal_spike::{Command, CrashPoint, Error, Session};

fn cmd_inc(delta: i64) -> Command {
    Command::new("counter.inc", json!({ "delta": delta }))
}

fn cmd_set(id: &str, value: i64) -> Command {
    Command::new("entity.set", json!({ "id": id, "value": value }))
}

fn open_tmp() -> (TempDir, Session) {
    let dir = TempDir::new().expect("tempdir");
    let session = Session::open(dir.path()).expect("open");
    (dir, session)
}

/// (a) Crash mid-record write (partial last line). Recovery = last ACK.
#[test]
fn crash_a_mid_record_write() {
    let (dir, mut s) = open_tmp();
    let ack = s
        .commit("act_01", "01CMD00000000000000000001", vec![cmd_inc(5)])
        .unwrap();
    assert_eq!(ack.revision, "r-000001");
    assert_eq!(s.document().counter, 5);
    s.commit(
        "act_01",
        "01CMD00000000000000000002",
        vec![cmd_set("door", 1)],
    )
    .unwrap();
    assert_eq!(s.document().entities.get("door"), Some(&1));

    s.inject_crash(CrashPoint::MidRecordWrite);
    let err = s
        .commit("act_01", "01CMD00000000000000000003", vec![cmd_inc(99)])
        .unwrap_err();
    assert!(matches!(err, Error::Crash(CrashPoint::MidRecordWrite)));
    // In-memory session must not treat the crashed txn as ACK'd.
    assert_eq!(s.last_ack().revision, "r-000002");
    assert_eq!(s.document().counter, 5);

    let wal = fs::read_to_string(&s.paths().wal_file).unwrap();
    assert!(!wal.ends_with('\n'), "partial last line has no trailing LF");

    drop(s);
    let mut s2 = Session::open(dir.path()).expect("recover after (a)");
    assert_eq!(s2.last_ack().revision, "r-000002");
    assert_eq!(s2.last_ack().seq, 2);
    assert_eq!(s2.document().counter, 5, "no apply of un-ACK'd inc(99)");
    assert_eq!(s2.document().entities.get("door"), Some(&1));
    assert_eq!(s2.document().revision_label(), "r-000002");

    let wal2 = fs::read_to_string(s2.paths().wal_file.as_path()).unwrap();
    assert!(wal2.ends_with('\n'));
    assert_eq!(wal2.lines().filter(|l| !l.is_empty()).count(), 2);

    let ack3 = s2
        .commit("act_01", "01CMD00000000000000000004", vec![cmd_inc(1)])
        .expect("session continues after tail cut");
    assert_eq!(ack3.revision, "r-000003");
}

/// (b) Record written+flushed, crash BEFORE apply. Must not apply on recovery.
#[test]
fn crash_b_after_flush_before_apply() {
    let (dir, mut s) = open_tmp();
    s.commit(
        "act_01",
        "01CMD00000000000000000001",
        vec![cmd_set("door", 1), cmd_inc(5)],
    )
    .unwrap();

    s.inject_crash(CrashPoint::AfterFlushBeforeApply);
    let err = s
        .commit(
            "act_01",
            "01CMD00000000000000000002",
            vec![cmd_set("door", 2), cmd_inc(10)],
        )
        .unwrap_err();
    assert!(matches!(
        err,
        Error::Crash(CrashPoint::AfterFlushBeforeApply)
    ));
    assert_eq!(s.document().counter, 5, "in-memory apply skipped");
    assert_eq!(s.document().entities.get("door"), Some(&1));
    assert_eq!(s.last_ack().revision, "r-000001");

    let wal = fs::read_to_string(s.paths().wal_file.as_path()).unwrap();
    assert!(
        wal.contains("\"delta\":10"),
        "flushed record is complete on disk"
    );
    assert_eq!(wal.lines().filter(|l| !l.is_empty()).count(), 2);

    drop(s);
    let s2 = Session::open(dir.path()).expect("recover after (b)");
    assert_eq!(s2.last_ack().revision, "r-000001");
    assert_eq!(s2.document().revision_label(), "r-000001");
    assert_eq!(s2.document().counter, 5, "un-ACK'd txn must not apply");
    assert_eq!(
        s2.document().entities.get("door"),
        Some(&1),
        "door must stay at ACK'd value, not 2"
    );

    let wal2 = fs::read_to_string(s2.paths().wal_file.as_path()).unwrap();
    assert_eq!(
        wal2.lines().filter(|l| !l.is_empty()).count(),
        1,
        "un-ACK'd flushed record is cut, not replayed"
    );
}

/// (c) Crash mid tmp+rename autosave. Recovery uses last valid autosave + ACK'd WAL.
#[test]
fn crash_c_mid_tmp_rename_autosave() {
    let (dir, mut s) = open_tmp();
    s.commit("act_01", "01CMD00000000000000000001", vec![cmd_inc(5)])
        .unwrap();
    s.autosave("main").unwrap();
    s.commit(
        "act_01",
        "01CMD00000000000000000002",
        vec![cmd_inc(7), cmd_set("key", 42)],
    )
    .unwrap();
    assert_eq!(s.document().counter, 12);
    assert_eq!(s.last_ack().revision, "r-000002");

    s.inject_crash(CrashPoint::MidAutosaveRename);
    let err = s.autosave("main").unwrap_err();
    assert!(matches!(err, Error::Crash(CrashPoint::MidAutosaveRename)));

    let autosave_dir = s.paths().autosave_dir.clone();
    let tmps: Vec<_> = fs::read_dir(&autosave_dir)
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
    assert_eq!(
        s2.document().counter,
        12,
        "ACK'd txn after last autosave kept"
    );
    assert_eq!(s2.document().entities.get("key"), Some(&42));
    assert_eq!(s2.document().revision_label(), "r-000002");
}

/// (d) Crash between two records of the same session: first ACK'd, second never written.
#[test]
fn crash_d_between_two_records() {
    let (dir, mut s) = open_tmp();
    let a1 = s
        .commit("act_01", "01CMD00000000000000000001", vec![cmd_inc(5)])
        .unwrap();
    assert_eq!(a1.revision, "r-000001");

    // Crash between records: drop the process after ACK of record 1, before record 2.
    drop(s);

    let mut s2 = Session::open(dir.path()).expect("recover after (d)");
    assert_eq!(s2.last_ack().revision, "r-000001");
    assert_eq!(s2.document().counter, 5);
    assert!(s2.document().entities.is_empty());
    assert_eq!(s2.document().revision_label(), "r-000001");

    let a2 = s2
        .commit(
            "act_01",
            "01CMD00000000000000000002",
            vec![cmd_set("npc", 7)],
        )
        .unwrap();
    assert_eq!(a2.revision, "r-000002");
    assert_eq!(s2.document().entities.get("npc"), Some(&7));
}

/// I6: corrupt record in the MIDDLE of the chain → stop, do not guess.
#[test]
fn i6_corrupt_middle_stops() {
    let (dir, mut s) = open_tmp();
    s.commit("act_01", "01CMD00000000000000000001", vec![cmd_inc(1)])
        .unwrap();
    s.commit("act_01", "01CMD00000000000000000002", vec![cmd_inc(1)])
        .unwrap();
    s.commit("act_01", "01CMD00000000000000000003", vec![cmd_inc(1)])
        .unwrap();
    let wal_path = s.paths().wal_file.clone();
    drop(s);

    let wal = fs::read_to_string(&wal_path).unwrap();
    let mut lines: Vec<String> = wal.lines().map(str::to_string).collect();
    assert_eq!(lines.len(), 3);
    lines[1] = r#"{"seq":2,"kind":"txn","txn_id":"t-000002","command_id":"x","actor_id":"a","base_revision":"r-000001","new_revision":"r-000002","commands":[],"inverses":[],"schema_version":1,"ts":"0","crc32":"deadbeef"}"#.into();
    fs::write(&wal_path, format!("{}\n", lines.join("\n"))).unwrap();

    let err = Session::open(dir.path()).unwrap_err();
    assert!(
        matches!(err, Error::CorruptMiddle { .. }),
        "middle crc fail must stop, got {err:?}"
    );
}

#[test]
fn happy_path_replay_from_autosave_plus_wal() {
    let (dir, mut s) = open_tmp();
    s.commit("act_01", "01CMD00000000000000000001", vec![cmd_inc(3)])
        .unwrap();
    s.autosave("main").unwrap();
    s.commit("act_01", "01CMD00000000000000000002", vec![cmd_set("a", 8)])
        .unwrap();
    drop(s);

    let s2 = Session::open(dir.path()).unwrap();
    assert_eq!(s2.document().counter, 3);
    assert_eq!(s2.document().entities.get("a"), Some(&8));
    assert_eq!(s2.last_ack().revision, "r-000002");
}

/// Smoke-measure default every-record fsync (Appendix A). Not a pass/fail budget.
#[test]
fn fsync_overhead_smoke() {
    let dir = TempDir::new().unwrap();
    let mut s = Session::open(dir.path()).unwrap();
    let n = 20u32;
    let start = std::time::Instant::now();
    for i in 0..n {
        s.commit("act_01", &format!("01FS{i:022}"), vec![cmd_inc(1)])
            .unwrap();
    }
    let elapsed = start.elapsed();
    let per = elapsed / n;
    eprintln!("fsync-every-record: {n} txn in {elapsed:?} ({per:?}/txn)");
    assert_eq!(s.document().counter, i64::from(n));
}

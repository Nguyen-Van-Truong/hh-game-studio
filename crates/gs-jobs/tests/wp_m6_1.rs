//! WP-M6-1 job state machine (GS-EC-50, 51, 52, 55).

use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

use gs_jobs::{
    assert_worker_path_allowed, cancel, claim, enqueue, finish, heartbeat, load, quarantine_dir,
    staging_dir, staging_is_ingestible, sweep_timeouts, ImageSize, JobResult, JobSpec, JobState,
};
use tempfile::TempDir;

fn spec(command_id: &str) -> JobSpec {
    JobSpec {
        kind: "image".into(),
        prompt: "pixel crate".into(),
        negative: None,
        size: ImageSize { w: 64, h: 64 },
        seed: 1,
        style_preset: "pixel".into(),
        dest_rel_hint: "assets/sprites/crate.png".into(),
        command_id: command_id.into(),
        actor_id: "act_test".into(),
        created_at: 1_700_000_000_000,
        extra: BTreeMap::new(),
    }
}

fn result_ok() -> JobResult {
    JobResult {
        ok: true,
        provider: "stub".into(),
        ms: Some(1),
        error: None,
        extra: BTreeMap::new(),
    }
}

#[test]
fn same_command_id_does_not_create_a_second_queue_file() {
    let dir = TempDir::new().expect("tempdir");
    let root = dir.path();
    let id1 = enqueue(root, &spec("01ARZ3NDEKTSV4RRFFQ69G5FAV")).expect("enqueue 1");
    let id2 = enqueue(root, &spec("01ARZ3NDEKTSV4RRFFQ69G5FAV")).expect("enqueue 2");
    assert_eq!(id1, id2);
    assert_eq!(id1, "01ARZ3NDEKTSV4RRFFQ69G5FAV");
    let queue = root.join(".gs/jobs/queue");
    let count = fs::read_dir(&queue)
        .expect("queue")
        .filter(|e| {
            e.as_ref()
                .ok()
                .and_then(|e| e.file_name().to_str().map(|n| n.ends_with(".job.json")))
                .unwrap_or(false)
        })
        .count();
    assert_eq!(count, 1, "retry same command_id must reuse the job file");
}

#[test]
fn two_claim_only_one_gets_the_job() {
    let dir = TempDir::new().expect("tempdir");
    let root = dir.path();
    enqueue(root, &spec("01CLAIM000000000000000001")).expect("enqueue");
    let first = claim(root, "worker-a").expect("claim a");
    let second = claim(root, "worker-b").expect("claim b");
    assert!(first.is_some(), "first claimer wins");
    assert!(second.is_none(), "second claimer must not get the same job");
    assert_eq!(first.unwrap().lease.unwrap().worker_id, "worker-a");
}

#[test]
fn heartbeat_then_sweep_plus_31s_times_out() {
    let dir = TempDir::new().expect("tempdir");
    let root = dir.path();
    let id = enqueue(root, &spec("01SWEEP000000000000000001")).expect("enqueue");
    claim(root, "w1").expect("claim").expect("job");
    heartbeat(root, &id, "w1").expect("heartbeat");
    let job = load(root, &id).expect("load").expect("running");
    let hb = job.lease.expect("lease").heartbeat_at;
    let timed = sweep_timeouts(root, hb + 31_000).expect("sweep");
    assert_eq!(timed, vec![id.clone()]);
    let done = load(root, &id).expect("load done").expect("job");
    assert_eq!(done.state, JobState::TimedOut);
}

#[test]
fn finish_after_timed_out_quarantines_not_ingestible() {
    let dir = TempDir::new().expect("tempdir");
    let root = dir.path();
    let id = enqueue(root, &spec("01LATE0000000000000000001")).expect("enqueue");
    claim(root, "w1").expect("claim").expect("job");
    heartbeat(root, &id, "w1").expect("heartbeat");
    let hb = load(root, &id)
        .expect("load")
        .expect("job")
        .lease
        .expect("lease")
        .heartbeat_at;
    sweep_timeouts(root, hb + 31_000).expect("sweep");

    let staging = staging_dir(root, &id);
    fs::create_dir_all(&staging).expect("staging");
    let out = staging.join("out.png");
    let result = staging.join("result.json");
    assert_worker_path_allowed(root, &out).expect("out.png allowed");
    assert_worker_path_allowed(root, &result).expect("result.json allowed");
    fs::write(&out, [0x89, 0x50, 0x4E, 0x47]).expect("png");
    fs::write(&result, b"{\"ok\":true,\"provider\":\"stub\"}\n").expect("result");

    let outcome = finish(root, &id, &result_ok()).expect("finish");
    assert!(outcome.quarantined);
    assert_eq!(outcome.state, JobState::TimedOut);
    assert!(
        !staging_is_ingestible(root, &id),
        "staging/jobs/{id} must not remain ingestible"
    );
    assert!(
        !staging.exists()
            || fs::read_dir(&staging)
                .map(|mut i| i.next().is_none())
                .unwrap_or(true),
        "ingestible staging must be empty/gone"
    );
    let q = quarantine_dir(root, &id);
    assert!(q.join("out.png").exists() || q.join("result.json").exists());
}

#[test]
fn assert_worker_path_allowed_rejects_assets() {
    let dir = TempDir::new().expect("tempdir");
    let root = dir.path();
    let err = assert_worker_path_allowed(root, Path::new("assets/foo.png"));
    assert!(err.is_err(), "relative assets/foo.png must be rejected");
    let err = assert_worker_path_allowed(root, &root.join("assets/foo.png"));
    assert!(err.is_err(), "absolute assets/foo.png must be rejected");
    // dest_rel_hint looks like assets/ — still not a write path.
    let err = assert_worker_path_allowed(root, Path::new("assets/sprites/crate.png"));
    assert!(err.is_err());
}

#[test]
fn cancel_writes_marker_queued_moves() {
    let dir = TempDir::new().expect("tempdir");
    let root = dir.path();
    let id = enqueue(root, &spec("01CANCEL00000000000000001")).expect("enqueue");
    cancel(root, &id).expect("cancel");
    assert!(root
        .join(".gs/jobs/cancel")
        .join(format!("{id}.marker"))
        .exists());
    let job = load(root, &id).expect("load").expect("job");
    assert_eq!(job.state, JobState::Cancelled);
}

#[test]
fn job_json_strips_secret_keys() {
    let dir = TempDir::new().expect("tempdir");
    let root = dir.path();
    let mut spec = spec("01SECRET00000000000000001");
    spec.extra
        .insert("api_key".into(), serde_json::json!("sk-MUST-NOT-APPEAR"));
    spec.extra
        .insert("token".into(), serde_json::json!("bus-token-secret"));
    let id = enqueue(root, &spec).expect("enqueue");
    let raw = fs::read_to_string(root.join(".gs/jobs/queue").join(format!("{id}.job.json")))
        .expect("job file");
    assert!(!raw.contains("sk-MUST-NOT-APPEAR"));
    assert!(!raw.contains("bus-token-secret"));
    assert!(!raw.contains("api_key"));
    assert!(!raw.contains("\"token\""));
}

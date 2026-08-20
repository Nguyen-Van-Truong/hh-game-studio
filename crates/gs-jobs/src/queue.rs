//! Job state machine (MASTER 8.2 / GS-EC-50,51,52).
//!
//! `job_id` is the `command_id`. Retrying the same command_id reuses the same
//! job file — no `commands.json` sidecar.

use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

use serde_json::{json, Value};

use crate::error::Error;
use crate::io::{rename_exclusive, write_atomic};
use crate::job::{strip_secrets, Job, JobResult, JobSpec, JobState};
use crate::paths::{staging_dir, JobPaths, LEASE_TIMEOUT_MS};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum JobDir {
    Queue,
    Running,
    Done,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct HeartbeatOutcome {
    pub cancelled: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CancelOutcome {
    QueuedMoved,
    RunningMarked,
    AlreadyDone,
    NotFound,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct FinishOutcome {
    pub state: JobState,
    pub quarantined: bool,
}

pub fn now_ms() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as i64)
        .unwrap_or(0)
}

/// Enqueue `spec`. `job_id` = `command_id`. Same command_id does not create a
/// second queue file (looks in queue / running / done).
pub fn enqueue(root: &Path, spec: &JobSpec) -> Result<String, Error> {
    let paths = JobPaths::new(root);
    paths.ensure()?;
    let job_id = crate::paths::job_id_from_command_id(&spec.command_id)?;
    if locate(&paths, &job_id)?.is_some() {
        return Ok(job_id);
    }
    let mut map = spec.to_map();
    map.insert("job_id".into(), json!(job_id));
    map.insert("state".into(), json!(JobState::Queued.as_str()));
    strip_secrets(&mut map);
    write_map(&paths.queue_file(&job_id), &map)?;
    Ok(job_id)
}

/// Atomic claim: `rename` queue → running (Windows `MoveFile` fails if dest
/// exists; loser sees missing source). Then write lease via tmp+rename.
pub fn claim(root: &Path, worker_id: &str) -> Result<Option<Job>, Error> {
    if worker_id.is_empty() {
        return Err(Error::invalid("worker_id is required"));
    }
    let paths = JobPaths::new(root);
    paths.ensure()?;
    for job_id in list_ids(&paths.queue_dir())? {
        if cancel_marker_exists(&paths, &job_id) {
            let _ = cancel(root, &job_id);
            continue;
        }
        let src = paths.queue_file(&job_id);
        let dest = paths.running_file(&job_id);
        match rename_exclusive(&src, &dest) {
            Ok(()) => {
                let mut map = read_map(&dest)?;
                let hb = now_ms();
                map.insert("state".into(), json!(JobState::Running.as_str()));
                map.insert(
                    "lease".into(),
                    json!({ "worker_id": worker_id, "heartbeat_at": hb }),
                );
                strip_secrets(&mut map);
                write_map(&dest, &map)?;
                fs::create_dir_all(paths.staging_dir(&job_id))?;
                return Ok(Some(Job::from_map(&job_id, &map, JobState::Running)?));
            }
            Err(Error::Io(err))
                if err.kind() == std::io::ErrorKind::AlreadyExists
                    || err.kind() == std::io::ErrorKind::NotFound =>
            {
                continue;
            }
            Err(err) => {
                // Windows: "cannot find the file" / "already exists" as Other.
                if dest.exists() || !src.exists() {
                    continue;
                }
                return Err(err);
            }
        }
    }
    Ok(None)
}

pub fn heartbeat(root: &Path, job_id: &str, worker_id: &str) -> Result<HeartbeatOutcome, Error> {
    let paths = JobPaths::new(root);
    let path = paths.running_file(job_id);
    if !path.exists() {
        return Err(Error::NotRunning {
            job_id: job_id.to_string(),
        });
    }
    let mut map = read_map(&path)?;
    let job = Job::from_map(job_id, &map, JobState::Running)?;
    match &job.lease {
        Some(lease) if lease.worker_id == worker_id => {}
        Some(lease) => {
            return Err(Error::NotOwner {
                job_id: job_id.to_string(),
                worker_id: lease.worker_id.clone(),
            });
        }
        None => {
            return Err(Error::NotOwner {
                job_id: job_id.to_string(),
                worker_id: worker_id.to_string(),
            });
        }
    }
    map.insert(
        "lease".into(),
        json!({ "worker_id": worker_id, "heartbeat_at": now_ms() }),
    );
    strip_secrets(&mut map);
    write_map(&path, &map)?;
    Ok(HeartbeatOutcome {
        cancelled: cancel_marker_exists(&paths, job_id),
    })
}

/// Running jobs whose lease is older than 30s become `timed_out` (GS-EC-50).
pub fn sweep_timeouts(root: &Path, now: i64) -> Result<Vec<String>, Error> {
    let paths = JobPaths::new(root);
    paths.ensure()?;
    let mut timed = Vec::new();
    for job_id in list_ids(&paths.running_dir())? {
        let path = paths.running_file(&job_id);
        let map = match read_map(&path) {
            Ok(m) => m,
            Err(_) => continue,
        };
        let job = Job::from_map(&job_id, &map, JobState::Running)?;
        let hb = job.lease.as_ref().map(|l| l.heartbeat_at).unwrap_or(0);
        if now.saturating_sub(hb) <= LEASE_TIMEOUT_MS {
            continue;
        }
        if move_to_done(&paths, &job_id, JobDir::Running, JobState::TimedOut, None)? {
            timed.push(job_id);
        }
    }
    Ok(timed)
}

/// Write a cancel marker. Queued jobs move to `done/cancelled`; running jobs
/// keep the marker only (worker / sweep finishes them).
pub fn cancel(root: &Path, job_id: &str) -> Result<CancelOutcome, Error> {
    let paths = JobPaths::new(root);
    paths.ensure()?;
    write_cancel_marker(&paths, job_id)?;
    match locate(&paths, job_id)? {
        Some((JobDir::Queue, _)) => {
            move_to_done(&paths, job_id, JobDir::Queue, JobState::Cancelled, None)?;
            Ok(CancelOutcome::QueuedMoved)
        }
        Some((JobDir::Running, _)) => Ok(CancelOutcome::RunningMarked),
        Some((JobDir::Done, _)) => Ok(CancelOutcome::AlreadyDone),
        None => Ok(CancelOutcome::NotFound),
    }
}

/// Finish a job. If it is already `timed_out` / `cancelled`, staging is moved
/// to quarantine (GS-EC-52) so ingest cannot pick it up.
pub fn finish(root: &Path, job_id: &str, result: &JobResult) -> Result<FinishOutcome, Error> {
    let paths = JobPaths::new(root);
    paths.ensure()?;
    let clean = JobResult::from_map(&result.to_map());
    if let Some((JobDir::Done, path)) = locate(&paths, job_id)? {
        let map = read_map(&path)?;
        let job = Job::from_map(job_id, &map, JobState::Failed)?;
        if job.state.late_result_quarantine() {
            let quarantined = quarantine_staging(&paths, job_id)?;
            let mut map = map;
            map.insert("late_result".into(), json!(true));
            map.insert(
                "result".into(),
                Value::Object(clean.to_map().into_iter().collect()),
            );
            strip_secrets(&mut map);
            write_map(&path, &map)?;
            return Ok(FinishOutcome {
                state: job.state,
                quarantined,
            });
        }
        return Ok(FinishOutcome {
            state: job.state,
            quarantined: false,
        });
    }
    if cancel_marker_exists(&paths, job_id) {
        let from = if paths.running_file(job_id).exists() {
            JobDir::Running
        } else {
            JobDir::Queue
        };
        let quarantined = quarantine_staging(&paths, job_id)?;
        move_to_done(&paths, job_id, from, JobState::Cancelled, Some(&clean))?;
        return Ok(FinishOutcome {
            state: JobState::Cancelled,
            quarantined,
        });
    }
    let state = if clean.ok {
        JobState::Succeeded
    } else {
        JobState::Failed
    };
    let from = if paths.running_file(job_id).exists() {
        JobDir::Running
    } else {
        JobDir::Queue
    };
    if !paths.running_file(job_id).exists() && !paths.queue_file(job_id).exists() {
        return Err(Error::NotFound(job_id.to_string()));
    }
    move_to_done(&paths, job_id, from, state, Some(&clean))?;
    Ok(FinishOutcome {
        state,
        quarantined: false,
    })
}

pub fn load(root: &Path, job_id: &str) -> Result<Option<Job>, Error> {
    let paths = JobPaths::new(root);
    let Some((dir, path)) = locate(&paths, job_id)? else {
        return Ok(None);
    };
    let fallback = match dir {
        JobDir::Queue => JobState::Queued,
        JobDir::Running => JobState::Running,
        JobDir::Done => JobState::Failed,
    };
    let map = read_map(&path)?;
    Ok(Some(Job::from_map(job_id, &map, fallback)?))
}

pub fn cancel_marker_exists(paths: &JobPaths, job_id: &str) -> bool {
    paths.cancel_marker(job_id).exists()
}

fn write_cancel_marker(paths: &JobPaths, job_id: &str) -> Result<(), Error> {
    let mut map = BTreeMap::new();
    map.insert("job_id".into(), json!(job_id));
    map.insert("created_at".into(), json!(now_ms()));
    write_map(&paths.cancel_marker(job_id), &map)
}

fn locate(paths: &JobPaths, job_id: &str) -> Result<Option<(JobDir, std::path::PathBuf)>, Error> {
    let q = paths.queue_file(job_id);
    if q.exists() {
        return Ok(Some((JobDir::Queue, q)));
    }
    let r = paths.running_file(job_id);
    if r.exists() {
        return Ok(Some((JobDir::Running, r)));
    }
    let d = paths.done_file(job_id);
    if d.exists() {
        return Ok(Some((JobDir::Done, d)));
    }
    Ok(None)
}

fn move_to_done(
    paths: &JobPaths,
    job_id: &str,
    from: JobDir,
    state: JobState,
    result: Option<&JobResult>,
) -> Result<bool, Error> {
    let src = match from {
        JobDir::Queue => paths.queue_file(job_id),
        JobDir::Running => paths.running_file(job_id),
        JobDir::Done => paths.done_file(job_id),
    };
    let dest = paths.done_file(job_id);
    if src != dest {
        match rename_exclusive(&src, &dest) {
            Ok(()) => {}
            Err(_) if dest.exists() => {}
            Err(err) => {
                if !src.exists() && dest.exists() {
                    // lost the race; still patch state below
                } else if !src.exists() {
                    return Ok(false);
                } else {
                    return Err(err);
                }
            }
        }
    }
    if !dest.exists() {
        return Ok(false);
    }
    let mut map = read_map(&dest)?;
    map.insert("state".into(), json!(state.as_str()));
    if let Some(result) = result {
        map.insert(
            "result".into(),
            Value::Object(result.to_map().into_iter().collect()),
        );
    }
    strip_secrets(&mut map);
    write_map(&dest, &map)?;
    Ok(true)
}

fn quarantine_staging(paths: &JobPaths, job_id: &str) -> Result<bool, Error> {
    let src = paths.staging_dir(job_id);
    if !src.exists() {
        return Ok(false);
    }
    let dest = paths.quarantine_dir(job_id);
    if dest.exists() {
        for entry in fs::read_dir(&src)? {
            let entry = entry?;
            let to = dest.join(entry.file_name());
            if to.exists() {
                if to.is_dir() {
                    fs::remove_dir_all(&to)?;
                } else {
                    fs::remove_file(&to)?;
                }
            }
            fs::rename(entry.path(), to)?;
        }
        fs::remove_dir_all(&src)?;
    } else {
        if let Some(parent) = dest.parent() {
            fs::create_dir_all(parent)?;
        }
        fs::rename(&src, &dest)?;
    }
    if src.exists() {
        fs::remove_dir_all(&src)?;
    }
    Ok(true)
}

fn list_ids(dir: &Path) -> Result<Vec<String>, Error> {
    let mut ids = BTreeSet::new();
    if !dir.exists() {
        return Ok(Vec::new());
    }
    for entry in fs::read_dir(dir)? {
        let name = entry?.file_name();
        let name = name.to_string_lossy();
        if let Some(id) = name.strip_suffix(".job.json") {
            if !id.is_empty() && !id.starts_with('.') {
                ids.insert(id.to_string());
            }
        }
    }
    Ok(ids.into_iter().collect())
}

fn read_map(path: &Path) -> Result<BTreeMap<String, Value>, Error> {
    let bytes = fs::read(path)?;
    let mut map: BTreeMap<String, Value> = serde_json::from_slice(&bytes)?;
    strip_secrets(&mut map);
    Ok(map)
}

fn write_map(path: &Path, map: &BTreeMap<String, Value>) -> Result<(), Error> {
    let mut clean = map.clone();
    strip_secrets(&mut clean);
    let mut bytes = serde_json::to_vec_pretty(&clean)?;
    bytes.push(b'\n');
    write_atomic(path, &bytes)
}

/// Public so tests can see that ingestible staging is gone.
pub fn staging_is_ingestible(root: &Path, job_id: &str) -> bool {
    let dir = staging_dir(root, job_id);
    if !dir.exists() {
        return false;
    }
    fs::read_dir(&dir)
        .map(|mut it| it.next().is_some())
        .unwrap_or(false)
}

//! Job / staging paths under a project root (MASTER 8.2).

use std::ffi::OsStr;
use std::path::{Component, Path, PathBuf};

use crate::error::Error;

/// Editor sweeper: running lease older than this is `timed_out` (GS-EC-50).
pub const LEASE_TIMEOUT_MS: i64 = 30_000;
/// Spec: worker should heartbeat about this often.
pub const HEARTBEAT_INTERVAL_MS: i64 = 10_000;

const GS: &str = ".gs";
const JOBS: &str = "jobs";
const QUEUE: &str = "queue";
const RUNNING: &str = "running";
const DONE: &str = "done";
const CANCEL: &str = "cancel";
const STAGING: &str = "staging";
const QUARANTINE: &str = "quarantine";
const ASSETS: &str = "assets";

/// Layout helpers for one project root.
#[derive(Clone, Debug)]
pub struct JobPaths {
    root: PathBuf,
}

impl JobPaths {
    pub fn new(root: impl Into<PathBuf>) -> Self {
        Self { root: root.into() }
    }

    pub fn root(&self) -> &Path {
        &self.root
    }

    pub fn jobs_root(&self) -> PathBuf {
        self.root.join(GS).join(JOBS)
    }

    pub fn queue_dir(&self) -> PathBuf {
        self.jobs_root().join(QUEUE)
    }

    pub fn running_dir(&self) -> PathBuf {
        self.jobs_root().join(RUNNING)
    }

    pub fn done_dir(&self) -> PathBuf {
        self.jobs_root().join(DONE)
    }

    pub fn cancel_dir(&self) -> PathBuf {
        self.jobs_root().join(CANCEL)
    }

    pub fn staging_root(&self) -> PathBuf {
        self.root.join(GS).join(STAGING).join(JOBS)
    }

    pub fn quarantine_root(&self) -> PathBuf {
        self.root.join(GS).join(STAGING).join(QUARANTINE)
    }

    pub fn queue_file(&self, job_id: &str) -> PathBuf {
        self.queue_dir().join(job_file_name(job_id))
    }

    pub fn running_file(&self, job_id: &str) -> PathBuf {
        self.running_dir().join(job_file_name(job_id))
    }

    pub fn done_file(&self, job_id: &str) -> PathBuf {
        self.done_dir().join(job_file_name(job_id))
    }

    pub fn cancel_marker(&self, job_id: &str) -> PathBuf {
        self.cancel_dir().join(format!("{job_id}.marker"))
    }

    pub fn staging_dir(&self, job_id: &str) -> PathBuf {
        self.staging_root().join(job_id)
    }

    pub fn quarantine_dir(&self, job_id: &str) -> PathBuf {
        self.quarantine_root().join(job_id)
    }

    pub fn ensure(&self) -> Result<(), Error> {
        for dir in [
            self.queue_dir(),
            self.running_dir(),
            self.done_dir(),
            self.cancel_dir(),
            self.staging_root(),
            self.quarantine_root(),
        ] {
            std::fs::create_dir_all(dir)?;
        }
        Ok(())
    }
}

pub fn job_file_name(job_id: &str) -> String {
    format!("{job_id}.job.json")
}

/// The only directory a worker may write (`out.png`, `result.json`).
pub fn staging_dir(root: &Path, job_id: &str) -> PathBuf {
    JobPaths::new(root).staging_dir(job_id)
}

/// Late results after cancel/timeout land here (GS-EC-52). Not ingestible.
pub fn quarantine_dir(root: &Path, job_id: &str) -> PathBuf {
    JobPaths::new(root).quarantine_dir(job_id)
}

/// Reject any path under `assets/` (GS-EC-55). The only legal worker writes
/// are `.gs/staging/jobs/<job_id>/{out.png,result.json}`.
///
/// Jail is component-normalized **and** `canonicalize` + prefix (so a symlink
/// from staging into `assets/` is rejected). `dest_rel_hint` is not a write
/// path and is never consulted here.
pub fn assert_worker_path_allowed(root: &Path, path: &Path) -> Result<(), Error> {
    let abs = if path.is_absolute() {
        path.to_path_buf()
    } else {
        root.join(path)
    };
    let rel = match project_relative(root, &abs) {
        Ok(rel) => rel,
        Err(_) => project_relative(root, path)?,
    };
    if is_under(&rel, &[ASSETS]) {
        return Err(Error::worker_path(
            "worker must not write assets/ (GS-EC-55); only .gs/staging/jobs/<job_id>/{out.png,result.json}",
        ));
    }
    let name_ok = rel
        .file_name()
        .and_then(|s| s.to_str())
        .is_some_and(|n| n == "out.png" || n == "result.json");
    if !is_under(&rel, &[GS, STAGING, JOBS]) || !name_ok {
        return Err(Error::worker_path(
            "worker may only write .gs/staging/jobs/<job_id>/{out.png,result.json}",
        ));
    }
    assert_canonical_staging_prefix(root, &abs)
}

pub(crate) fn job_id_from_command_id(command_id: &str) -> Result<String, Error> {
    let id = command_id.trim();
    if id.is_empty() {
        return Err(Error::invalid("command_id is required"));
    }
    if id.contains('/') || id.contains('\\') || id.contains("..") {
        return Err(Error::invalid(
            "command_id is not a safe job_id (path separator)",
        ));
    }
    if id
        .chars()
        .any(|c| !(c.is_ascii_alphanumeric() || c == '_' || c == '-'))
    {
        return Err(Error::invalid(
            "command_id is not a safe job_id (use ULID / [A-Za-z0-9_-])",
        ));
    }
    Ok(id.to_string())
}

fn project_relative(root: &Path, path: &Path) -> Result<PathBuf, Error> {
    let raw = if path.is_absolute() {
        match path.strip_prefix(root) {
            Ok(rel) => rel.to_path_buf(),
            Err(_) => {
                // Compare after normalizing only when both are absolute.
                return Err(Error::PathEscape(path.to_path_buf()));
            }
        }
    } else {
        path.to_path_buf()
    };
    normalize_rel(&raw)
}

fn normalize_rel(path: &Path) -> Result<PathBuf, Error> {
    let mut out: Vec<&OsStr> = Vec::new();
    for c in path.components() {
        match c {
            Component::CurDir => {}
            Component::ParentDir => {
                if out.pop().is_none() {
                    return Err(Error::PathEscape(path.to_path_buf()));
                }
            }
            Component::Normal(s) => out.push(s),
            Component::Prefix(_) | Component::RootDir => {
                return Err(Error::PathEscape(path.to_path_buf()));
            }
        }
    }
    Ok(out.iter().collect())
}

fn is_under(rel: &Path, prefix: &[&str]) -> bool {
    let mut comps = rel.components();
    for expected in prefix {
        match comps.next() {
            Some(Component::Normal(s)) if eq_component(s, expected) => {}
            _ => return false,
        }
    }
    true
}

/// `canonicalize` both sides when possible; require `candidate` to stay under
/// `{root}/.gs/staging/jobs` and not resolve into `assets/`.
fn assert_canonical_staging_prefix(root: &Path, candidate: &Path) -> Result<(), Error> {
    let Ok(root_c) = root.canonicalize() else {
        return Ok(());
    };
    let staging = root_c.join(GS).join(STAGING).join(JOBS);
    let staging_c = if staging.exists() {
        staging.canonicalize().unwrap_or(staging)
    } else {
        staging
    };
    let cand_c = canonicalize_existing_prefix(candidate);
    let assets_c = root_c.join(ASSETS);
    if cand_c.starts_with(&assets_c) {
        return Err(Error::worker_path(
            "worker must not write assets/ (GS-EC-55); canonicalize resolved into assets/",
        ));
    }
    if cand_c == staging_c || cand_c.starts_with(&staging_c) {
        return Ok(());
    }
    Err(Error::worker_path(
        "worker path canonicalize+prefix jail: not under .gs/staging/jobs/",
    ))
}

fn canonicalize_existing_prefix(path: &Path) -> PathBuf {
    if path.exists() {
        return path.canonicalize().unwrap_or_else(|_| path.to_path_buf());
    }
    let mut tail = Vec::new();
    let mut cur = path.to_path_buf();
    loop {
        if cur.exists() {
            let mut canon = cur.canonicalize().unwrap_or(cur);
            for part in tail.iter().rev() {
                canon.push(part);
            }
            return canon;
        }
        match cur.file_name() {
            Some(name) => {
                tail.push(name.to_os_string());
                if !cur.pop() {
                    return path.to_path_buf();
                }
            }
            None => return path.to_path_buf(),
        }
    }
}

fn eq_component(s: &OsStr, expected: &str) -> bool {
    let Some(text) = s.to_str() else {
        return false;
    };
    if cfg!(windows) {
        text.eq_ignore_ascii_case(expected)
    } else {
        text == expected
    }
}

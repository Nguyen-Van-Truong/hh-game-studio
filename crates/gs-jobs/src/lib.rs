//! Imagegen job state machine (MASTER 8.2 / T6.1).
//!
//! Workers write **only** `.gs/staging/jobs/<job_id>/{out.png,result.json}`.
//! `dest_rel_hint` is not a write path. `job_id` is derived from `command_id`
//! (same command_id → same job file; no sidecar). Secrets are stripped from
//! job JSON (I8).

mod error;
mod io;
mod job;
mod paths;
mod queue;

pub use error::Error;
pub use job::{ImageSize, Job, JobResult, JobSpec, JobState, Lease};
pub use paths::{
    assert_worker_path_allowed, quarantine_dir, staging_dir, JobPaths, HEARTBEAT_INTERVAL_MS,
    LEASE_TIMEOUT_MS,
};
pub use queue::{
    cancel, claim, enqueue, finish, heartbeat, load, now_ms, staging_is_ingestible, sweep_timeouts,
    CancelOutcome, FinishOutcome, HeartbeatOutcome,
};

pub fn crate_name() -> &'static str {
    "gs-jobs"
}

#[cfg(test)]
mod tests {
    #[test]
    fn smoke() {
        assert_eq!(super::crate_name(), "gs-jobs");
    }
}

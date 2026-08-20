//! Offline job verbs for the imagegen worker. These do **not** open
//! `.gs/runtime/endpoint.json` and never print bus tokens or API keys.

use std::path::Path;

use gs_jobs::{claim, finish, heartbeat, Job, JobResult};
use serde_json::{json, Value};

use crate::error::Error;

pub fn jobs_claim(root: &Path, worker_id: &str) -> Result<Value, Error> {
    match claim(root, worker_id)? {
        Some(job) => Ok(job_to_value(&job)),
        None => Ok(json!({ "job_id": null })),
    }
}

pub fn jobs_heartbeat(root: &Path, job_id: &str, worker_id: &str) -> Result<Value, Error> {
    let out = heartbeat(root, job_id, worker_id)?;
    Ok(json!({ "ok": true, "cancelled": out.cancelled }))
}

pub fn jobs_finish(root: &Path, job_id: &str, result: &JobResult) -> Result<Value, Error> {
    let out = finish(root, job_id, result)?;
    Ok(json!({
        "ok": true,
        "state": out.state.as_str(),
        "quarantined": out.quarantined,
    }))
}

fn job_to_value(job: &Job) -> Value {
    Value::Object(job.to_map().into_iter().collect())
}

impl From<gs_jobs::Error> for Error {
    fn from(err: gs_jobs::Error) -> Self {
        Error::Args(err.to_string())
    }
}

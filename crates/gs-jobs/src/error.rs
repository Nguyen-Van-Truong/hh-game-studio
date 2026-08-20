//! Job-queue errors. Messages never include secrets (I8).

use std::io;
use std::path::PathBuf;

/// Failures while reading or mutating job files under a project root.
#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error("I/O error: {0}")]
    Io(#[from] io::Error),
    #[error("JSON error: {0}")]
    Json(String),
    #[error("invalid job spec: {0}")]
    Invalid(String),
    #[error("job {0} not found")]
    NotFound(String),
    #[error("job {job_id} is not running")]
    NotRunning { job_id: String },
    #[error("worker {worker_id} does not own job {job_id}")]
    NotOwner { job_id: String, worker_id: String },
    #[error("worker path not allowed: {0}")]
    WorkerPath(String),
    #[error("path escapes project root: {0}")]
    PathEscape(PathBuf),
}

impl Error {
    pub fn json(err: impl ToString) -> Self {
        Self::Json(err.to_string())
    }

    pub fn invalid(err: impl Into<String>) -> Self {
        Self::Invalid(err.into())
    }

    pub fn worker_path(err: impl Into<String>) -> Self {
        Self::WorkerPath(err.into())
    }
}

impl From<serde_json::Error> for Error {
    fn from(err: serde_json::Error) -> Self {
        Self::json(err)
    }
}

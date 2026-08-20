//! Bus / UI errors and JSON-RPC helpers.

use gs_protocol::{
    ErrorData, RpcError, APP, BUSY, CONFLICT, INVALID_PARAMS, METHOD_NOT_FOUND, UNAUTHORIZED,
};
use gs_scene::Error as SceneError;

/// Library-level failure (bind, endpoint file, TCP hello).
#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error(transparent)]
    Io(#[from] std::io::Error),
    #[error(transparent)]
    Json(#[from] serde_json::Error),
    #[error("another editor holds the bus (pid {0})")]
    AlreadyRunning(u32),
    #[error("protocol: {0}")]
    Protocol(String),
    #[error("window: {0}")]
    Window(String),
    #[error("rpc {code}: {message}")]
    Rpc {
        code: i32,
        message: String,
        app_code: Option<String>,
    },
}

impl From<RpcError> for Error {
    fn from(err: RpcError) -> Self {
        Self::Rpc {
            code: err.code,
            message: err.message.clone(),
            app_code: err.data.as_ref().map(|d| d.app_code.clone()),
        }
    }
}

pub(crate) fn rpc_data(
    code: i32,
    message: impl Into<String>,
    app_code: impl Into<String>,
) -> RpcError {
    RpcError::with_data(
        code,
        message,
        ErrorData {
            app_code: app_code.into(),
            retryable: None,
            field: None,
            reason: None,
        },
    )
}

pub(crate) fn unauthorized(message: impl Into<String>) -> RpcError {
    rpc_data(UNAUTHORIZED, message, "E_UNAUTHORIZED")
}

pub(crate) fn invalid_params(message: impl Into<String>) -> RpcError {
    rpc_data(INVALID_PARAMS, message, "E_VALIDATION")
}

pub(crate) fn app_err(app_code: impl Into<String>, message: impl Into<String>) -> RpcError {
    rpc_data(APP, message, app_code)
}

pub(crate) fn method_not_found(method: &str) -> RpcError {
    RpcError::new(METHOD_NOT_FOUND, format!("method not found: {method}"))
}

pub(crate) fn not_implemented(method: &str) -> RpcError {
    RpcError::new(
        METHOD_NOT_FOUND,
        format!("{method} is not implemented in this editor slice"),
    )
}

pub(crate) fn paused() -> RpcError {
    app_err(
        "E_PAUSED",
        "actor is paused; only pure-read methods are allowed",
    )
}

pub(crate) fn budget(retry_after_ms: u64) -> RpcError {
    RpcError::with_data(
        BUSY,
        "mutating budget exceeded",
        ErrorData {
            app_code: "E_BUDGET".into(),
            retryable: Some(true),
            field: None,
            reason: Some(format!("retry_after_ms={retry_after_ms}")),
        },
    )
}

pub(crate) fn conflict(message: impl Into<String>) -> RpcError {
    rpc_data(CONFLICT, message, "E_CONFLICT")
}

/// Agent touched an entity held by a human gizmo drag (GS-EC-12).
pub(crate) fn locked(owner: &str, note: &str) -> RpcError {
    RpcError::with_data(
        CONFLICT,
        format!("entity is locked by {owner} ({note})"),
        ErrorData {
            app_code: "E_LOCKED".into(),
            retryable: Some(true),
            field: None,
            reason: Some(format!("owner={owner}; {note}")),
        },
    )
}

pub(crate) fn scene_err(err: SceneError) -> RpcError {
    match err {
        SceneError::Invalid { method, reason } => rpc_data(
            INVALID_PARAMS,
            format!("{method}: {reason}"),
            "E_VALIDATION",
        ),
        SceneError::NotFound(id) => app_err("E_NOT_FOUND", format!("not found: {id}")),
        SceneError::Conflict { expected, current } => RpcError::with_data(
            CONFLICT,
            format!("revision conflict: expected {expected}, current {current}"),
            ErrorData {
                app_code: "E_CONFLICT".into(),
                retryable: Some(false),
                field: Some("expected_revision".into()),
                reason: Some(format!("current_revision={current}")),
            },
        ),
        SceneError::Locked { owner, note, .. } => locked(&owner, &note),
        SceneError::Cycle { id, new_parent } => app_err(
            "E_VALIDATION",
            format!("reparent cycle {id} -> {new_parent}"),
        ),
        SceneError::AlreadyOpen => app_err("E_PROJECT_OPEN", "project is already open"),
        SceneError::ReadOnly => app_err("E_VALIDATION", "session is read-only"),
        SceneError::InvalidCommandId => invalid_params("command_id is required and must be a ULID"),
        SceneError::UnknownMethod(name) => method_not_found(&name),
        SceneError::Io(err) => app_err("E_IO", err.to_string()),
        SceneError::Json(err) => invalid_params(err.to_string()),
        SceneError::Crash(_) => app_err("E_CRASH", "simulated crash"),
        SceneError::CorruptMiddle { at_byte } => app_err(
            "E_WAL",
            format!("WAL corrupt in the middle at byte {at_byte}"),
        ),
        SceneError::ChainBreak { seq, expected, got } => app_err(
            "E_WAL",
            format!("revision chain break at seq {seq}: expected {expected}, got {got}"),
        ),
        SceneError::AckAheadOfWal { ack_seq, wal_seq } => app_err(
            "E_WAL",
            format!("ACK seq {ack_seq} is ahead of WAL seq {wal_seq}"),
        ),
        SceneError::DiskFull { op } => app_err("E_DISK", format!("disk full during {op}")),
        SceneError::ConflictMarker { path } => app_err(
            "E_CONFLICT_MARKER",
            format!("git conflict marker in {path}"),
        ),
        SceneError::PathEscapesRoot { path } => app_err(
            "E_PATH",
            format!("path {path} is not under the project root"),
        ),
    }
}

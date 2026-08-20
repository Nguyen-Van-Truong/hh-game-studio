use thiserror::Error;

/// Simulated crash / fail-stop points (MASTER 5.5 / GS-EC-38 / GS-EC-39).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CrashPoint {
    /// (a) Mid JSONL record: only a prefix of the line is on disk.
    MidRecordWrite,
    /// (b) Full record written + fsynced; apply and ACK not reached.
    AfterFlushBeforeApply,
    /// (c) Autosave tmp files written; dest not replaced (rename skipped).
    MidAutosaveRename,
    /// (d) Previous record flushed+ACK'd; the next record is never written.
    BetweenRecords,
    /// WAL fsync / append fails (GS-EC-39). Session fail-stops mutating.
    FsyncFail,
}

#[derive(Debug, Error)]
pub enum Error {
    #[error("simulated crash at {0:?}")]
    Crash(CrashPoint),
    #[error(transparent)]
    Io(#[from] std::io::Error),
    #[error(transparent)]
    Json(#[from] serde_json::Error),
    #[error("unknown method {0}")]
    UnknownMethod(String),
    #[error("invalid params for {method}: {reason}")]
    Invalid { method: String, reason: String },
    #[error("entity {0} not found")]
    NotFound(String),
    #[error("revision conflict: expected {expected}, current {current}")]
    Conflict { expected: String, current: String },
    #[error("entity {id} is locked by {owner}: {note}")]
    Locked {
        id: String,
        owner: String,
        note: String,
    },
    #[error("reparent of {id} onto {new_parent} would create a cycle")]
    Cycle { id: String, new_parent: String },
    #[error("project is already open in another editor (editor.lock)")]
    AlreadyOpen,
    #[error("session is read-only")]
    ReadOnly,
    #[error("command_id is required and must be a ULID")]
    InvalidCommandId,
    #[error("WAL corrupt in the middle at byte {at_byte} (I6: stop, do not guess)")]
    CorruptMiddle { at_byte: u64 },
    #[error("revision chain break at seq {seq}: expected base {expected}, got {got}")]
    ChainBreak {
        seq: u64,
        expected: String,
        got: String,
    },
    #[error("ACK cursor seq {ack_seq} is ahead of WAL (last wal seq {wal_seq})")]
    AckAheadOfWal { ack_seq: u64, wal_seq: u64 },
    #[error("disk full or fsync failed during {op} (GS-EC-39 fail-stop)")]
    DiskFull { op: String },
    #[error("git conflict marker in {path} (GS-EC-10); try a valid autosave")]
    ConflictMarker { path: String },
    #[error("path {path} is not under the project root (I7)")]
    PathEscapesRoot { path: String },
}

impl Error {
    pub fn invalid(method: impl Into<String>, reason: impl Into<String>) -> Self {
        Self::Invalid {
            method: method.into(),
            reason: reason.into(),
        }
    }
}

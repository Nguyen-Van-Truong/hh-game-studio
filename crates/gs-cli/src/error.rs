//! Client-side errors. Messages never include the bus token (I8).

use std::fmt;
use std::io;
use std::path::PathBuf;

use gs_protocol::{ErrorData, RpcError, INVALID_REQUEST};

/// Failures while locating the endpoint or talking to the bus.
#[derive(Debug)]
pub enum Error {
    Io(io::Error),
    MissingEndpoint(PathBuf),
    Stale { pid: u32 },
    Protocol(String),
    Json(String),
    Args(String),
    Rpc(RpcError),
}

impl Error {
    pub fn json(err: impl ToString) -> Self {
        Self::Json(err.to_string())
    }

    /// Map connection / framing failures onto [`RpcError`] so `call` stays
    /// `Result<Value, RpcError>` (no panic on the error path).
    pub fn into_rpc(self) -> RpcError {
        match self {
            Self::Rpc(err) => err,
            other => {
                RpcError::with_data(INVALID_REQUEST, other.to_string(), ErrorData::new("E_IO"))
            }
        }
    }
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Io(err) => write!(f, "I/O error: {err}"),
            Self::MissingEndpoint(path) => {
                write!(f, "no live endpoint at {}; run gsopen", path.display())
            }
            Self::Stale { pid } => write!(f, "endpoint pid {pid} is not running (stale)"),
            Self::Protocol(msg) | Self::Json(msg) | Self::Args(msg) => f.write_str(msg),
            Self::Rpc(err) => match &err.data {
                Some(data) => write!(
                    f,
                    "JSON-RPC error {}: {} ({})",
                    err.code, err.message, data.app_code
                ),
                None => write!(f, "JSON-RPC error {}: {}", err.code, err.message),
            },
        }
    }
}

impl std::error::Error for Error {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Io(err) => Some(err),
            _ => None,
        }
    }
}

impl From<io::Error> for Error {
    fn from(err: io::Error) -> Self {
        Self::Io(err)
    }
}

impl From<RpcError> for Error {
    fn from(err: RpcError) -> Self {
        Self::Rpc(err)
    }
}

impl From<gs_protocol::ProtocolError> for Error {
    fn from(err: gs_protocol::ProtocolError) -> Self {
        match RpcError::from_protocol(&err) {
            Some(rpc) => Self::Rpc(rpc),
            None => Self::Protocol(err.to_string()),
        }
    }
}

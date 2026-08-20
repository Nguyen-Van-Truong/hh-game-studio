//! Standard JSON-RPC / app error codes and error payloads (MASTER 4.1).

use std::io;

/// JSON-RPC parse error.
pub const PARSE: i32 = -32700;
/// Invalid request, including unsupported batch arrays and framing/proto failures.
pub const INVALID_REQUEST: i32 = -32600;
/// Method not found.
pub const METHOD_NOT_FOUND: i32 = -32601;
/// Invalid params.
pub const INVALID_PARAMS: i32 = -32602;
/// Application error; business `app_code` lives in [`ErrorData`].
pub const APP: i32 = -32000;
/// Unauthorized / wrong principal.
pub const UNAUTHORIZED: i32 = -32001;
/// Conflict (revision, lock, …).
pub const CONFLICT: i32 = -32002;
/// Busy / budget exceeded.
pub const BUSY: i32 = -32003;

/// Framing / line-cap failure (`GS-EC-58`).
pub const APP_CODE_PROTO: &str = "E_PROTO";

/// `error.data` object. `app_code` is required when `data` is present.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub struct ErrorData {
    pub app_code: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub retryable: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub field: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub reason: Option<String>,
}

impl ErrorData {
    pub fn new(app_code: impl Into<String>) -> Self {
        Self {
            app_code: app_code.into(),
            retryable: None,
            field: None,
            reason: None,
        }
    }

    pub fn proto() -> Self {
        Self::new(APP_CODE_PROTO)
    }
}

/// JSON-RPC `error` object. `code` is always a JSON number.
#[derive(Debug, Clone, PartialEq, serde::Serialize, serde::Deserialize)]
pub struct RpcError {
    pub code: i32,
    pub message: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub data: Option<ErrorData>,
}

impl RpcError {
    pub fn new(code: i32, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
            data: None,
        }
    }

    pub fn with_data(code: i32, message: impl Into<String>, data: ErrorData) -> Self {
        Self {
            code,
            message: message.into(),
            data: Some(data),
        }
    }

    /// `-32600` + `E_PROTO` (caller must then close the connection).
    pub fn proto(message: impl Into<String>) -> Self {
        Self::with_data(INVALID_REQUEST, message, ErrorData::proto())
    }

    pub fn from_protocol(err: &ProtocolError) -> Option<Self> {
        match err {
            ProtocolError::Rpc {
                code,
                message,
                app_code,
            } => Some(Self {
                code: *code,
                message: message.clone(),
                data: app_code.as_ref().map(ErrorData::new),
            }),
            ProtocolError::Io(_) | ProtocolError::Eof => None,
        }
    }
}

/// Framing / envelope failure. RPC variants carry a numeric `code`.
#[derive(Debug, thiserror::Error)]
pub enum ProtocolError {
    #[error("JSON-RPC error {code}: {message}")]
    Rpc {
        code: i32,
        message: String,
        app_code: Option<String>,
    },
    #[error("I/O error: {0}")]
    Io(#[from] io::Error),
    #[error("unexpected end of stream")]
    Eof,
}

impl ProtocolError {
    pub fn parse(message: impl Into<String>) -> Self {
        Self::Rpc {
            code: PARSE,
            message: message.into(),
            app_code: None,
        }
    }

    pub fn invalid_request(message: impl Into<String>) -> Self {
        Self::Rpc {
            code: INVALID_REQUEST,
            message: message.into(),
            app_code: None,
        }
    }

    pub fn proto(message: impl Into<String>) -> Self {
        Self::Rpc {
            code: INVALID_REQUEST,
            message: message.into(),
            app_code: Some(APP_CODE_PROTO.to_owned()),
        }
    }

    pub fn code(&self) -> Option<i32> {
        match self {
            Self::Rpc { code, .. } => Some(*code),
            Self::Io(_) | Self::Eof => None,
        }
    }

    pub fn app_code(&self) -> Option<&str> {
        match self {
            Self::Rpc { app_code, .. } => app_code.as_deref(),
            Self::Io(_) | Self::Eof => None,
        }
    }

    pub fn message(&self) -> &str {
        match self {
            Self::Rpc { message, .. } => message,
            Self::Io(_) => "I/O error",
            Self::Eof => "unexpected end of stream",
        }
    }
}

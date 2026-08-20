use std::io;
use std::path::PathBuf;

use thiserror::Error;

/// Player / snapshot-verify failures. Binary prints `REJECT` and exits non-zero.
#[derive(Debug, Error)]
pub enum Error {
    #[error("{0}")]
    Reject(String),
    #[error("usage: {0}")]
    Usage(String),
    #[error("E_PATH: {0}")]
    Path(String),
    #[error("E_VALIDATION: {0}")]
    Validation(String),
    #[error("io error at {path}: {source}")]
    Io {
        path: PathBuf,
        #[source]
        source: io::Error,
    },
    #[error("json error at {path}: {source}")]
    Json {
        path: PathBuf,
        #[source]
        source: serde_json::Error,
    },
    #[error(transparent)]
    Runtime(#[from] gs_runtime_core::Error),
    #[error(transparent)]
    Render(#[from] gs_render2d::Error),
    #[error("{0}")]
    Window(String),
    #[error("control: {0}")]
    Control(String),
}

impl Error {
    pub fn reject(msg: impl Into<String>) -> Self {
        Self::Reject(msg.into())
    }

    pub fn usage(msg: impl Into<String>) -> Self {
        Self::Usage(msg.into())
    }

    pub fn path(msg: impl Into<String>) -> Self {
        Self::Path(msg.into())
    }

    pub fn validation(msg: impl Into<String>) -> Self {
        Self::Validation(msg.into())
    }

    /// Application code for editor/bus mapping (`E_PATH`, `E_VALIDATION`, …).
    pub fn app_code(&self) -> &'static str {
        match self {
            Self::Path(_) => "E_PATH",
            Self::Validation(_) => "E_VALIDATION",
            Self::Usage(_) => "E_VALIDATION",
            Self::Reject(_) => "E_VALIDATION",
            Self::Io { .. } | Self::Json { .. } => "E_IO",
            Self::Runtime(_) | Self::Render(_) | Self::Window(_) | Self::Control(_) => "E_IO",
        }
    }

    pub fn io(path: impl Into<PathBuf>, source: io::Error) -> Self {
        Self::Io {
            path: path.into(),
            source,
        }
    }

    pub fn json(path: impl Into<PathBuf>, source: serde_json::Error) -> Self {
        Self::Json {
            path: path.into(),
            source,
        }
    }

    pub fn is_reject(&self) -> bool {
        matches!(self, Self::Reject(_))
    }

    pub fn control(msg: impl Into<String>) -> Self {
        Self::Control(msg.into())
    }
}

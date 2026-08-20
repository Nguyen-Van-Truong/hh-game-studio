use std::fmt;
use std::io;
use std::path::PathBuf;

#[derive(Debug)]
pub enum SpikeError {
    Io {
        path: Option<PathBuf>,
        source: io::Error,
    },
    Json {
        path: Option<PathBuf>,
        source: serde_json::Error,
    },
    Usage(String),
    Reject(String),
}

impl SpikeError {
    pub fn io(path: impl Into<PathBuf>, source: io::Error) -> Self {
        Self::Io {
            path: Some(path.into()),
            source,
        }
    }

    pub fn json(path: impl Into<PathBuf>, source: serde_json::Error) -> Self {
        Self::Json {
            path: Some(path.into()),
            source,
        }
    }

    pub fn reject(msg: impl Into<String>) -> Self {
        Self::Reject(msg.into())
    }
}

impl fmt::Display for SpikeError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Io { path, source } => match path {
                Some(p) => write!(f, "io error at {}: {source}", p.display()),
                None => write!(f, "io error: {source}"),
            },
            Self::Json { path, source } => match path {
                Some(p) => write!(f, "json error at {}: {source}", p.display()),
                None => write!(f, "json error: {source}"),
            },
            Self::Usage(msg) | Self::Reject(msg) => f.write_str(msg),
        }
    }
}

impl std::error::Error for SpikeError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Io { source, .. } => Some(source),
            Self::Json { source, .. } => Some(source),
            Self::Usage(_) | Self::Reject(_) => None,
        }
    }
}

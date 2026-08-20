//! `.gs/runtime/endpoint.json` reader. Token stays in memory (I8).

use std::fs;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

use crate::error::Error;

/// Relative path of the bus locator (MASTER 2.7).
pub const ENDPOINT_REL: &str = ".gs/runtime/endpoint.json";

/// On-disk bus locator. `token` is a secret — never log or `Display` it.
#[derive(Clone, Serialize, Deserialize)]
pub struct Endpoint {
    pub host: String,
    pub port: u16,
    pub pid: u32,
    token: String,
}

impl Endpoint {
    pub fn new(host: impl Into<String>, port: u16, token: impl Into<String>, pid: u32) -> Self {
        Self {
            host: host.into(),
            port,
            token: token.into(),
            pid,
        }
    }

    /// Handshake secret. Callers must not write this into logs, events, or fixtures.
    pub fn token(&self) -> &str {
        &self.token
    }
}

impl std::fmt::Debug for Endpoint {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Endpoint")
            .field("host", &self.host)
            .field("port", &self.port)
            .field("pid", &self.pid)
            .field("token", &"<redacted>")
            .finish()
    }
}

/// `{root}/.gs/runtime/endpoint.json`.
pub fn endpoint_path(root: impl AsRef<Path>) -> PathBuf {
    root.as_ref().join(ENDPOINT_REL)
}

/// True when `pid` still refers to a running process.
pub fn pid_is_alive(pid: u32) -> bool {
    if pid == 0 {
        return false;
    }
    #[cfg(windows)]
    {
        let output = std::process::Command::new("tasklist")
            .args(["/FI", &format!("PID eq {pid}"), "/NH"])
            .output();
        match output {
            Ok(out) => {
                let stdout = String::from_utf8_lossy(&out.stdout);
                !stdout.contains("No tasks are running") && stdout.contains(&pid.to_string())
            }
            Err(_) => false,
        }
    }
    #[cfg(not(windows))]
    {
        std::path::Path::new(&format!("/proc/{pid}")).exists()
    }
}

/// Read endpoint.json. Does **not** check whether `pid` is alive.
pub fn read_endpoint_file(path: impl AsRef<Path>) -> Result<Endpoint, Error> {
    let path = path.as_ref();
    let text = fs::read_to_string(path).map_err(|err| {
        if err.kind() == std::io::ErrorKind::NotFound {
            Error::MissingEndpoint(path.to_path_buf())
        } else {
            Error::Io(err)
        }
    })?;
    // Do not include file text in the error — it contains the token (I8).
    serde_json::from_str(&text).map_err(|_| Error::Protocol("invalid endpoint.json".into()))
}

/// Load a **live** endpoint for `root`. Dead pid → [`Error::Stale`] (do not hang).
pub fn load_live_endpoint(root: impl AsRef<Path>) -> Result<Endpoint, Error> {
    let path = endpoint_path(root);
    if !path.exists() {
        return Err(Error::MissingEndpoint(path));
    }
    let endpoint = read_endpoint_file(&path)?;
    if !pid_is_alive(endpoint.pid) {
        return Err(Error::Stale { pid: endpoint.pid });
    }
    Ok(endpoint)
}

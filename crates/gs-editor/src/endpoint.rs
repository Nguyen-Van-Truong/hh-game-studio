//! `.gs/runtime/endpoint.json` (MASTER 2.7, GS-EC-44, I8).

use std::fs;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

use crate::error::Error;

pub const ENDPOINT_REL: &str = ".gs/runtime/endpoint.json";

/// On-disk / in-memory bus locator. `token` is a secret (I8) — never log it.
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

pub fn endpoint_path(runtime_root: &Path) -> PathBuf {
    runtime_root.join(ENDPOINT_REL)
}

/// Remove a leftover endpoint file when its pid is dead (GS-EC-44).
pub fn cleanup_stale(runtime_root: &Path) -> Result<(), Error> {
    let path = endpoint_path(runtime_root);
    if !path.exists() {
        return Ok(());
    }
    match read_file(&path) {
        Ok(existing) => {
            if existing.pid == std::process::id() {
                let _ = fs::remove_file(&path);
                return Ok(());
            }
            if pid_is_alive(existing.pid) {
                return Err(Error::AlreadyRunning(existing.pid));
            }
            fs::remove_file(&path)?;
        }
        Err(_) => {
            fs::remove_file(&path)?;
        }
    }
    Ok(())
}

pub fn write_file(runtime_root: &Path, endpoint: &Endpoint) -> Result<PathBuf, Error> {
    let path = endpoint_path(runtime_root);
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let tmp = path.with_extension("json.tmp");
    let bytes = serde_json::to_vec_pretty(endpoint)?;
    fs::write(&tmp, bytes)?;
    if path.exists() {
        fs::remove_file(&path)?;
    }
    fs::rename(&tmp, &path)?;
    Ok(path)
}

pub fn read_file(path: &Path) -> Result<Endpoint, Error> {
    let text = fs::read_to_string(path)?;
    Ok(serde_json::from_str(&text)?)
}

fn pid_is_alive(pid: u32) -> bool {
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

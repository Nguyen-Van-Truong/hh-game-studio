//! `.gs/runtime/player.json` locator (MASTER 6.1, GS-EC-44, I8).
//!
//! `token` is a secret — never log it, never put it in status/events/feed.

use std::fs;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};

use crate::error::Error;

pub const PLAYER_JSON_REL: &str = ".gs/runtime/player.json";

/// On-disk player control locator. `token` is a secret (I8).
#[derive(Clone, Serialize, Deserialize)]
pub struct PlayerFile {
    pub pid: u32,
    pub port: u16,
    pub play_id: String,
    pub started_at: String,
    token: String,
}

impl PlayerFile {
    pub fn new(
        pid: u32,
        port: u16,
        play_id: impl Into<String>,
        started_at: impl Into<String>,
        token: impl Into<String>,
    ) -> Self {
        Self {
            pid,
            port,
            play_id: play_id.into(),
            started_at: started_at.into(),
            token: token.into(),
        }
    }

    /// Handshake secret. Callers must not write this into logs, events, or fixtures.
    pub fn token(&self) -> &str {
        &self.token
    }
}

impl std::fmt::Debug for PlayerFile {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("PlayerFile")
            .field("pid", &self.pid)
            .field("port", &self.port)
            .field("play_id", &self.play_id)
            .field("started_at", &self.started_at)
            .field("token", &"<redacted>")
            .finish()
    }
}

/// `{root}/.gs/runtime/player.json`.
pub fn player_json_under(root: &Path) -> PathBuf {
    root.join(PLAYER_JSON_REL)
}

/// Infer where the player process should write `player.json`.
///
/// Prefer `{project}/.gs/runtime/player.json` when the snapshot lives under
/// `.gs/runtime/play/<play_id>/`. Otherwise `{play_dir}/.gs/runtime/player.json`.
pub fn player_json_for_snapshot(manifest: &Path) -> PathBuf {
    if let Some(runtime) = runtime_dir_from_snapshot(manifest) {
        return runtime.join("player.json");
    }
    match manifest.parent() {
        Some(play_dir) => play_dir.join(".gs").join("runtime").join("player.json"),
        None => PathBuf::from("player.json"),
    }
}

/// Walk up from a snapshot manifest to `.gs/runtime` when the layout matches MASTER 2.4.
pub fn runtime_dir_from_snapshot(manifest: &Path) -> Option<PathBuf> {
    let play_id_dir = manifest.parent()?;
    let play_root = play_id_dir.parent()?;
    if play_root.file_name().and_then(|n| n.to_str()) != Some("play") {
        return None;
    }
    let runtime = play_root.parent()?;
    if runtime.file_name().and_then(|n| n.to_str()) != Some("runtime") {
        return None;
    }
    Some(runtime.to_path_buf())
}

/// First existing player.json among the usual locations.
pub fn locate_player_json(runtime_root: &Path, play_dir: Option<&Path>) -> Option<PathBuf> {
    let primary = player_json_under(runtime_root);
    if primary.is_file() {
        return Some(primary);
    }
    if let Some(play_dir) = play_dir {
        let next_to = play_dir.join("player.json");
        if next_to.is_file() {
            return Some(next_to);
        }
        let nested = play_dir.join(".gs").join("runtime").join("player.json");
        if nested.is_file() {
            return Some(nested);
        }
    }
    None
}

/// Remove a leftover player.json when its pid is dead (GS-EC-44).
///
/// Returns `true` when the file was deleted.
pub fn cleanup_stale_player_json(path: &Path) -> Result<bool, Error> {
    if !path.exists() {
        return Ok(false);
    }
    match read_player_file(path) {
        Ok(existing) => {
            if existing.pid == std::process::id() {
                let _ = fs::remove_file(path);
                return Ok(true);
            }
            if pid_is_alive(existing.pid) {
                return Ok(false);
            }
            fs::remove_file(path).map_err(|e| Error::io(path, e))?;
            Ok(true)
        }
        Err(_) => {
            let _ = fs::remove_file(path);
            Ok(true)
        }
    }
}

pub fn write_player_file(path: &Path, file: &PlayerFile) -> Result<(), Error> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| Error::io(parent, e))?;
    }
    let tmp = path.with_extension("json.tmp");
    let bytes = serde_json::to_vec_pretty(file).map_err(|e| Error::json(path, e))?;
    fs::write(&tmp, bytes).map_err(|e| Error::io(&tmp, e))?;
    if path.exists() {
        fs::remove_file(path).map_err(|e| Error::io(path, e))?;
    }
    fs::rename(&tmp, path).map_err(|e| Error::io(path, e))?;
    Ok(())
}

pub fn read_player_file(path: &Path) -> Result<PlayerFile, Error> {
    let text = fs::read_to_string(path).map_err(|e| Error::io(path, e))?;
    serde_json::from_str(&text).map_err(|e| Error::json(path, e))
}

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

/// UTC timestamp `YYYY-MM-DDTHH:MM:SSZ` (no extra crate).
pub fn utc_now_rfc3339() -> String {
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    unix_secs_to_rfc3339(secs)
}

pub(crate) fn unix_secs_to_rfc3339(secs: u64) -> String {
    let z = i64::try_from(secs / 86_400).unwrap_or(0) + 719_468;
    let era = if z >= 0 { z } else { z - 146_096 } / 146_097;
    let doe = u64::try_from(z - era * 146_097).unwrap_or(0);
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let y = i64::try_from(yoe).unwrap_or(0) + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };
    let tod = secs % 86_400;
    let hh = tod / 3600;
    let mm = (tod % 3600) / 60;
    let ss = tod % 60;
    format!("{y:04}-{m:02}-{d:02}T{hh:02}:{mm:02}:{ss:02}Z")
}

#[cfg(test)]
mod tests {
    use super::unix_secs_to_rfc3339;

    #[test]
    fn known_unix_is_rfc3339() {
        assert_eq!(unix_secs_to_rfc3339(0), "1970-01-01T00:00:00Z");
        assert_eq!(unix_secs_to_rfc3339(1_786_838_400), "2026-08-16T00:00:00Z");
    }
}

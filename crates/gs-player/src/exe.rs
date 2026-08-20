//! Locate the `gs-player` binary for the editor and tests.

use std::env;
use std::path::PathBuf;

use crate::error::Error;

fn bin_name() -> &'static str {
    if cfg!(windows) {
        "gs-player.exe"
    } else {
        "gs-player"
    }
}

/// Search `GS_PLAYER_EXE`, `CARGO_BIN_EXE_gs_player`, `target/{debug,release}`, and cwd.
pub fn find_player_exe() -> Result<PathBuf, Error> {
    if let Ok(raw) = env::var("GS_PLAYER_EXE") {
        let path = PathBuf::from(raw);
        if path.is_file() {
            return Ok(path);
        }
    }
    for key in ["CARGO_BIN_EXE_gs_player", "CARGO_BIN_EXE_gs-player"] {
        if let Ok(raw) = env::var(key) {
            let path = PathBuf::from(raw);
            if path.is_file() {
                return Ok(path);
            }
        }
    }

    let name = bin_name();
    if let Ok(exe) = env::current_exe() {
        let mut dir = exe.parent().map(PathBuf::from);
        for _ in 0..4 {
            let Some(current) = dir else {
                break;
            };
            let candidate = current.join(name);
            if candidate.is_file() {
                return Ok(candidate);
            }
            dir = current.parent().map(PathBuf::from);
        }
    }

    if let Ok(target) = env::var("CARGO_TARGET_DIR") {
        for profile in ["debug", "release"] {
            let candidate = PathBuf::from(&target).join(profile).join(name);
            if candidate.is_file() {
                return Ok(candidate);
            }
        }
    }

    let mut roots = Vec::new();
    if let Ok(cwd) = env::current_dir() {
        roots.push(cwd);
    }
    if let Some(manifest) = option_env!("CARGO_MANIFEST_DIR") {
        roots.push(PathBuf::from(manifest));
    }

    for root in roots {
        let mut dir = root;
        for _ in 0..8 {
            for profile in ["debug", "release"] {
                let candidate = dir.join("target").join(profile).join(name);
                if candidate.is_file() {
                    return Ok(candidate);
                }
            }
            if !dir.pop() {
                break;
            }
        }
    }

    Err(Error::control(format!(
        "{} not found; build with `cargo build -p gs-player` or set GS_PLAYER_EXE",
        bin_name()
    )))
}

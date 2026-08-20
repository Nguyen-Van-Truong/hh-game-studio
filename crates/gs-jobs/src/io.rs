//! tmp+rename writes (I6) and exclusive rename used as the claim mutex (GS-EC-51).

use std::fs;
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::error::Error;

/// Write `bytes` via a same-directory temp file, then rename onto `path`.
///
/// On Windows `fs::rename` does not replace an existing dest, so a leftover
/// dest is removed immediately before the rename. Claim uses
/// [`rename_exclusive`] instead — that path must not replace.
pub fn write_atomic(path: &Path, bytes: &[u8]) -> Result<(), Error> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let tmp = tmp_beside(path);
    fs::write(&tmp, bytes)?;
    replace_rename(&tmp, path)?;
    Ok(())
}

/// Rename `src` → `dest` only if `dest` does not already exist.
///
/// This is the claim mutex: two claimers rename the same queue file; one
/// wins, the other gets `AlreadyExists` or a missing source.
pub fn rename_exclusive(src: &Path, dest: &Path) -> Result<(), Error> {
    if dest.exists() {
        return Err(Error::Io(std::io::Error::new(
            std::io::ErrorKind::AlreadyExists,
            "destination exists",
        )));
    }
    if let Some(parent) = dest.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::rename(src, dest)?;
    Ok(())
}

fn replace_rename(tmp: &Path, dest: &Path) -> Result<(), Error> {
    match fs::rename(tmp, dest) {
        Ok(()) => Ok(()),
        Err(err) => {
            if dest.exists() {
                fs::remove_file(dest)?;
                fs::rename(tmp, dest)?;
                Ok(())
            } else {
                Err(err.into())
            }
        }
    }
}

fn tmp_beside(path: &Path) -> std::path::PathBuf {
    let name = path
        .file_name()
        .map(|s| s.to_string_lossy().into_owned())
        .unwrap_or_else(|| "job".into());
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    path.with_file_name(format!(".{name}.{}.{nanos}.tmp", std::process::id()))
}

//! Paths, fsync helpers, ACK log, WAL append, tmp+rename autosave (I6).

use std::fs::{self, File, OpenOptions};
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::document::Document;
use crate::record::WalRecord;

pub const ACK_FILE: &str = "ack.jsonl";
pub const WAL_FILE: &str = "wal.jsonl";
pub const DIRTY_FILE: &str = "dirty";

#[derive(Clone, Debug)]
pub struct Paths {
    pub root: PathBuf,
    pub gs: PathBuf,
    pub wal_dir: PathBuf,
    pub wal_file: PathBuf,
    pub ack_file: PathBuf,
    pub autosave_dir: PathBuf,
    pub dirty: PathBuf,
}

impl Paths {
    pub fn new(root: impl Into<PathBuf>) -> Self {
        let root = root.into();
        let gs = root.join(".gs");
        let wal_dir = gs.join("wal");
        let autosave_dir = gs.join("autosave");
        Self {
            wal_file: wal_dir.join(WAL_FILE),
            ack_file: gs.join(ACK_FILE),
            dirty: gs.join(DIRTY_FILE),
            root,
            gs,
            wal_dir,
            autosave_dir,
        }
    }

    pub fn ensure_dirs(&self) -> io::Result<()> {
        fs::create_dir_all(&self.wal_dir)?;
        fs::create_dir_all(&self.autosave_dir)?;
        Ok(())
    }
}

/// fdatasync equivalent: `File::sync_data` (MASTER 5.5 default policy).
pub fn fdatasync(file: &File) -> io::Result<()> {
    file.sync_data()
}

pub fn append_and_sync(path: &Path, bytes: &[u8]) -> io::Result<()> {
    let mut file = OpenOptions::new().create(true).append(true).open(path)?;
    file.write_all(bytes)?;
    fdatasync(&file)?;
    Ok(())
}

/// Crash (a): persist a prefix of the next record with no trailing newline.
pub fn append_partial_and_sync(path: &Path, bytes: &[u8], keep: usize) -> io::Result<()> {
    let keep = keep.min(bytes.len());
    let mut file = OpenOptions::new().create(true).append(true).open(path)?;
    file.write_all(&bytes[..keep])?;
    fdatasync(&file)?;
    Ok(())
}

pub fn read_to_string_if_exists(path: &Path) -> io::Result<Option<String>> {
    if !path.exists() {
        return Ok(None);
    }
    let mut s = String::new();
    File::open(path)?.read_to_string(&mut s)?;
    Ok(Some(s))
}

/// Truncate `path` to `len` bytes (I6 cut truncated / un-ACK'd tail).
pub fn truncate_to(path: &Path, len: u64) -> io::Result<()> {
    let file = OpenOptions::new().write(true).open(path)?;
    file.set_len(len)?;
    fdatasync(&file)?;
    Ok(())
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct AckCursor {
    pub seq: u64,
    pub revision: String,
}

impl Default for AckCursor {
    fn default() -> Self {
        Self {
            seq: 0,
            revision: "r-000000".into(),
        }
    }
}

/// Append-only ACK log. Last complete line wins. Partial last line ignored (I6).
pub fn load_ack(path: &Path) -> io::Result<AckCursor> {
    let Some(text) = read_to_string_if_exists(path)? else {
        return Ok(AckCursor::default());
    };
    let mut last = AckCursor::default();
    for line in text.split('\n') {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        match serde_json::from_str::<AckCursor>(line) {
            Ok(c) => last = c,
            Err(_) => {
                // incomplete / corrupt last line: keep previous complete cursor
                break;
            }
        }
    }
    Ok(last)
}

pub fn append_ack(path: &Path, cursor: &AckCursor) -> io::Result<()> {
    let mut line = serde_json::to_string(cursor).map_err(io::Error::other)?;
    line.push('\n');
    append_and_sync(path, line.as_bytes())
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct AutosaveSidecar {
    pub last_committed_seq: u64,
    pub revision: String,
    pub doc_sha256: String,
}

#[derive(Clone, Debug)]
pub struct AutosaveSnapshot {
    pub seq: u64,
    pub document: Document,
}

pub fn doc_sha256(doc: &Document) -> Result<String, serde_json::Error> {
    let bytes = serde_json::to_vec(doc)?;
    let digest = Sha256::digest(&bytes);
    Ok(hex_lower(&digest))
}

fn hex_lower(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut out = String::with_capacity(bytes.len() * 2);
    for &b in bytes {
        out.push(HEX[(b >> 4) as usize] as char);
        out.push(HEX[(b & 0x0f) as usize] as char);
    }
    out
}

pub fn write_file_sync(path: &Path, bytes: &[u8]) -> io::Result<()> {
    let mut file = File::create(path)?;
    file.write_all(bytes)?;
    fdatasync(&file)?;
    Ok(())
}

/// Atomic document write: tmp + fsync + rename. Sidecar same pattern.
/// `crash_before_rename`: write both tmps, then stop (fault (c)).
pub fn autosave(
    paths: &Paths,
    scene: &str,
    seq: u64,
    doc: &Document,
    crash_before_rename: bool,
) -> io::Result<Option<PathBuf>> {
    paths.ensure_dirs()?;
    let ts = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0);
    let stem = format!("{scene}.{ts}");
    let json_name = format!("{stem}.json");
    let side_name = format!("{stem}.sidecar.json");
    let json_tmp = paths.autosave_dir.join(format!("{json_name}.tmp"));
    let side_tmp = paths.autosave_dir.join(format!("{side_name}.tmp"));
    let json_dest = paths.autosave_dir.join(&json_name);
    let side_dest = paths.autosave_dir.join(&side_name);

    let doc_bytes = serde_json::to_vec_pretty(doc).map_err(io::Error::other)?;
    let sha = doc_sha256(doc).map_err(io::Error::other)?;
    let sidecar = AutosaveSidecar {
        last_committed_seq: seq,
        revision: doc.revision_label(),
        doc_sha256: sha,
    };
    let side_bytes = serde_json::to_vec_pretty(&sidecar).map_err(io::Error::other)?;

    write_file_sync(&json_tmp, &doc_bytes)?;
    write_file_sync(&side_tmp, &side_bytes)?;

    if crash_before_rename {
        return Ok(None);
    }

    fs::rename(&json_tmp, &json_dest)?;
    fs::rename(&side_tmp, &side_dest)?;
    if paths.dirty.exists() {
        fs::remove_file(&paths.dirty)?;
    }
    Ok(Some(json_dest))
}

/// Latest autosave whose sidecar verifies (sha256 + parse). Invalid / tmp ignored.
pub fn load_latest_valid_autosave(paths: &Paths) -> io::Result<Option<AutosaveSnapshot>> {
    if !paths.autosave_dir.exists() {
        return Ok(None);
    }
    let mut best: Option<AutosaveSnapshot> = None;
    for entry in fs::read_dir(&paths.autosave_dir)? {
        let entry = entry?;
        let name = entry.file_name();
        let name = name.to_string_lossy();
        if !name.ends_with(".json") || name.ends_with(".sidecar.json") || name.ends_with(".tmp") {
            continue;
        }
        let json_path = entry.path();
        let stem = name.trim_end_matches(".json");
        let side_path = paths.autosave_dir.join(format!("{stem}.sidecar.json"));
        let Some(snap) = try_load_autosave(&json_path, &side_path)? else {
            continue;
        };
        let take = match &best {
            None => true,
            Some(b) => snap.seq > b.seq,
        };
        if take {
            best = Some(snap);
        }
    }
    Ok(best)
}

fn try_load_autosave(json_path: &Path, side_path: &Path) -> io::Result<Option<AutosaveSnapshot>> {
    if !side_path.exists() {
        return Ok(None);
    }
    let doc_text = fs::read_to_string(json_path)?;
    let side_text = fs::read_to_string(side_path)?;
    let sidecar: AutosaveSidecar = match serde_json::from_str(&side_text) {
        Ok(s) => s,
        Err(_) => return Ok(None),
    };
    let document: Document = match serde_json::from_str(&doc_text) {
        Ok(d) => d,
        Err(_) => return Ok(None),
    };
    let Ok(sha) = doc_sha256(&document) else {
        return Ok(None);
    };
    if sha != sidecar.doc_sha256 {
        return Ok(None);
    }
    if document.revision_label() != sidecar.revision {
        return Ok(None);
    }
    Ok(Some(AutosaveSnapshot {
        seq: sidecar.last_committed_seq,
        document,
    }))
}

/// Scan WAL JSONL. Returns complete crc-ok records plus a tail diagnosis.
pub fn scan_wal(path: &Path) -> io::Result<WalScan> {
    let Some(text) = read_to_string_if_exists(path)? else {
        return Ok(WalScan::default());
    };
    let bytes = text.as_bytes();
    let mut records = Vec::new();
    let mut record_ends: Vec<u64> = Vec::new();
    let mut offset: usize = 0;

    while offset < bytes.len() {
        let rest = &bytes[offset..];
        let nl = rest.iter().position(|&b| b == b'\n');
        let (line_bytes, next) = match nl {
            Some(i) => (&rest[..=i], offset + i + 1),
            None => (rest, bytes.len()),
        };
        let line = std::str::from_utf8(line_bytes).unwrap_or("");
        let trimmed = line.trim();
        if trimmed.is_empty() {
            offset = next;
            continue;
        }

        match WalRecord::from_json_line(trimmed) {
            Ok(rec) if rec.crc_ok() && rec.kind == "txn" => {
                records.push(rec);
                record_ends.push(next as u64);
            }
            _ => {
                let more_after = bytes[next..].iter().any(|&b| !b.is_ascii_whitespace());
                let tail = if more_after {
                    WalTail::CorruptMiddle {
                        at_byte: offset as u64,
                    }
                } else {
                    WalTail::Truncated {
                        at_byte: offset as u64,
                    }
                };
                return Ok(WalScan {
                    records,
                    record_ends,
                    tail,
                });
            }
        }
        offset = next;
    }

    Ok(WalScan {
        records,
        record_ends,
        tail: WalTail::Clean,
    })
}

#[derive(Clone, Debug, Default)]
pub struct WalScan {
    pub records: Vec<WalRecord>,
    /// File offset immediately after each complete record in `records`.
    pub record_ends: Vec<u64>,
    pub tail: WalTail,
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub enum WalTail {
    #[default]
    Clean,
    Truncated {
        at_byte: u64,
    },
    CorruptMiddle {
        at_byte: u64,
    },
}

pub fn mark_dirty(paths: &Paths) -> io::Result<()> {
    write_file_sync(&paths.dirty, b"")?;
    Ok(())
}

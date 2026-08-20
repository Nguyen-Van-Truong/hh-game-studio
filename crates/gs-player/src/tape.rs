//! Input tape record / replay (MASTER 6.2 header, 6.4 body, GS-EC-36).
//!
//! JSONL: first line is the header; later lines are
//! `{"frame":120,"action":"move_x","value":-1.0}`.
//! `engine_build` is the snapshot manifest's `engine_ver`.

use std::collections::{BTreeMap, BTreeSet};
use std::fs::{self, File, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};

use gs_runtime_core::{InputFrame, FIXED_DT};
use serde::{Deserialize, Serialize};

use crate::error::Error;
use crate::manifest::{SnapshotHashes, VerifiedSnapshot};

/// Default replay file in a play / snapshot directory.
pub const REPLAY_TAPE_FILE: &str = "replay.tape.jsonl";
/// Default `--record` file when the path is omitted / empty.
pub const RECORD_TAPE_FILE: &str = "record.tape.jsonl";
/// `tape.record` writes this under the play directory.
pub const INPUT_TAPE_FILE: &str = "input.tape.jsonl";

const FORCE_WARNING_SUFFIX: &str =
    " --force continues; result is NOT judge evidence (evidence_ok=false)";

/// MASTER 6.2 tape header.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct TapeHeader {
    pub engine_build: String,
    pub protocol_ver: String,
    pub fixed_dt: f64,
    pub seed: u64,
    pub snapshot_hashes: SnapshotHashes,
}

/// One MASTER 6.4 body line. `frame` is absolute from 0.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct TapeEvent {
    pub frame: u64,
    pub action: String,
    pub value: f64,
}

/// Header plus body events from a `.tape.jsonl` file.
#[derive(Debug, Clone, PartialEq)]
pub struct LoadedTape {
    pub header: TapeHeader,
    pub events: Vec<TapeEvent>,
}

/// Result of [`validate_header_force`].
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TapeHeaderCheck {
    pub evidence_ok: bool,
    pub warning: Option<String>,
}

/// Replay / record binding for a play start.
#[derive(Debug, Clone)]
pub struct BoundTape {
    pub replay: Option<LoadedTape>,
    pub record_path: Option<PathBuf>,
    pub header: Option<TapeHeader>,
    pub evidence_ok: bool,
    pub warning: Option<String>,
}

impl TapeHeader {
    /// Map a verified snapshot manifest onto the 6.2 header field names.
    pub fn from_verified(verified: &VerifiedSnapshot) -> Self {
        Self {
            engine_build: verified.manifest.engine_ver.clone(),
            protocol_ver: verified.manifest.protocol_ver.clone(),
            fixed_dt: FIXED_DT,
            seed: verified.manifest.seed,
            snapshot_hashes: verified.manifest.hashes.clone(),
        }
    }
}

/// Write (truncate) the tape and emit the header as the first JSONL line.
pub fn write_header(path: &Path, header: &TapeHeader) -> Result<(), Error> {
    if let Some(parent) = path.parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent).map_err(|e| Error::io(parent, e))?;
        }
    }
    let line = serde_json::to_string(header).map_err(|e| Error::json(path, e))?;
    let mut file = File::create(path).map_err(|e| Error::io(path, e))?;
    writeln!(file, "{line}").map_err(|e| Error::io(path, e))?;
    file.flush().map_err(|e| Error::io(path, e))?;
    Ok(())
}

/// Append one action line (MASTER 6.4).
pub fn append_action(path: &Path, event: &TapeEvent) -> Result<(), Error> {
    let line = serde_json::to_string(event).map_err(|e| Error::json(path, e))?;
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .map_err(|e| Error::io(path, e))?;
    writeln!(file, "{line}").map_err(|e| Error::io(path, e))?;
    Ok(())
}

/// Load header + body. Empty lines are skipped; a truncated tail is rejected.
pub fn load_tape(path: &Path) -> Result<LoadedTape, Error> {
    let text = fs::read_to_string(path).map_err(|e| Error::io(path, e))?;
    let mut lines = text.lines().filter(|line| !line.trim().is_empty());
    let first = lines
        .next()
        .ok_or_else(|| Error::reject(format!("empty tape {}", path.display())))?;
    let header: TapeHeader = serde_json::from_str(first).map_err(|e| Error::json(path, e))?;
    let mut events = Vec::new();
    for line in lines {
        let event: TapeEvent = serde_json::from_str(line).map_err(|e| Error::json(path, e))?;
        events.push(event);
    }
    Ok(LoadedTape { header, events })
}

/// Reject when `engine_build`, `protocol_ver`, or `snapshot_hashes` differ (GS-EC-36).
pub fn validate_header(header: &TapeHeader, verified: &VerifiedSnapshot) -> Result<(), Error> {
    match header_mismatch(header, verified) {
        None => Ok(()),
        Some(msg) => Err(Error::reject(msg)),
    }
}

/// Same check as [`validate_header`], but a mismatch is a warning and `evidence_ok=false`.
pub fn validate_header_force(header: &TapeHeader, verified: &VerifiedSnapshot) -> TapeHeaderCheck {
    match header_mismatch(header, verified) {
        None => TapeHeaderCheck {
            evidence_ok: true,
            warning: None,
        },
        Some(msg) => TapeHeaderCheck {
            evidence_ok: false,
            warning: Some(format!("{msg}{FORCE_WARNING_SUFFIX}")),
        },
    }
}

/// Actions listed on `frame` (missing frame → empty map; last line wins).
pub fn tape_actions_for_frame(events: &[TapeEvent], frame: u64) -> BTreeMap<String, f32> {
    let mut map = BTreeMap::new();
    for event in events {
        if event.frame == frame {
            map.insert(event.action.clone(), clamp_tape_value(event.value));
        }
    }
    map
}

/// Overlay tape values for `frame` onto a zeroed copy of `base` (input-map names).
pub fn apply_tape_to_frame(base: &InputFrame, events: &[TapeEvent], frame: u64) -> InputFrame {
    let mut actions: BTreeMap<String, f32> =
        base.actions.keys().map(|k| (k.clone(), 0.0)).collect();
    for (name, value) in tape_actions_for_frame(events, frame) {
        actions.insert(name, value);
    }
    InputFrame { actions }
}

/// Write header, then one line per non-zero or changed action on frames `0..frames.len()`.
pub fn record_input_frames(
    path: &Path,
    header: &TapeHeader,
    frames: &[InputFrame],
) -> Result<(), Error> {
    write_header(path, header)?;
    let mut last = BTreeMap::new();
    for (i, frame) in frames.iter().enumerate() {
        append_frame_actions(path, i as u64, frame, &mut last)?;
    }
    Ok(())
}

/// Append lines for this simulate frame (non-zero or changed vs `last`).
pub fn append_frame_actions(
    path: &Path,
    frame: u64,
    input: &InputFrame,
    last: &mut BTreeMap<String, f32>,
) -> Result<(), Error> {
    for (name, value) in &input.actions {
        let prev = last.get(name).copied().unwrap_or(0.0);
        if *value != 0.0 || *value != prev {
            append_action(
                path,
                &TapeEvent {
                    frame,
                    action: name.clone(),
                    value: f64::from(*value),
                },
            )?;
            last.insert(name.clone(), *value);
        }
    }
    Ok(())
}

/// When `known` is non-empty, every tape action must be in the input map (MASTER 6.4).
pub fn validate_actions_in_map(
    events: &[TapeEvent],
    known: &BTreeSet<String>,
) -> Result<(), Error> {
    if known.is_empty() {
        return Ok(());
    }
    for event in events {
        if !known.contains(&event.action) {
            return Err(Error::reject(format!(
                "tape action {:?} is not in the input map",
                event.action
            )));
        }
    }
    Ok(())
}

/// Resolve replay/record paths, validate the header, and write a record header if requested.
pub fn bind_tape(
    verified: Option<&VerifiedSnapshot>,
    play_dir: Option<&Path>,
    replay: Option<&Path>,
    record: Option<&Path>,
    force: bool,
) -> Result<BoundTape, Error> {
    let header = verified.map(TapeHeader::from_verified);
    let replay_path = discover_replay_path(play_dir, replay);
    let record_path = discover_record_path(play_dir, record);

    let mut evidence_ok = true;
    let mut warning = None;
    let mut replay_tape = None;

    if let Some(path) = &replay_path {
        let tape = load_tape(path)?;
        if let Some(verified) = verified {
            if force {
                let check = validate_header_force(&tape.header, verified);
                evidence_ok = check.evidence_ok;
                warning = check.warning;
            } else {
                validate_header(&tape.header, verified)?;
            }
        }
        replay_tape = Some(tape);
    }

    if let (Some(path), Some(header)) = (&record_path, &header) {
        write_header(path, header)?;
    }

    Ok(BoundTape {
        replay: replay_tape,
        record_path,
        header,
        evidence_ok,
        warning,
    })
}

pub fn discover_replay_path(play_dir: Option<&Path>, explicit: Option<&Path>) -> Option<PathBuf> {
    if let Some(path) = explicit {
        return Some(path.to_path_buf());
    }
    let dir = play_dir?;
    let path = dir.join(REPLAY_TAPE_FILE);
    path.is_file().then_some(path)
}

pub fn discover_record_path(play_dir: Option<&Path>, explicit: Option<&Path>) -> Option<PathBuf> {
    match explicit {
        Some(path) if path.as_os_str().is_empty() => play_dir.map(|dir| dir.join(RECORD_TAPE_FILE)),
        Some(path) => Some(path.to_path_buf()),
        None => None,
    }
}

fn header_mismatch(header: &TapeHeader, verified: &VerifiedSnapshot) -> Option<String> {
    let mut parts = Vec::new();
    if header.engine_build != verified.manifest.engine_ver {
        parts.push(format!(
            "engine_build {} != {}",
            header.engine_build, verified.manifest.engine_ver
        ));
    }
    if header.protocol_ver != verified.manifest.protocol_ver {
        parts.push(format!(
            "protocol_ver {} != {}",
            header.protocol_ver, verified.manifest.protocol_ver
        ));
    }
    let got = &header.snapshot_hashes;
    let want = &verified.manifest.hashes;
    if got.scene != want.scene {
        parts.push(format!(
            "snapshot_hashes.scene {} != {}",
            got.scene, want.scene
        ));
    }
    if got.scripts != want.scripts {
        parts.push(format!(
            "snapshot_hashes.scripts {} != {}",
            got.scripts, want.scripts
        ));
    }
    if got.assets != want.assets {
        parts.push(format!(
            "snapshot_hashes.assets {} != {}",
            got.assets, want.assets
        ));
    }
    if got.inputmap != want.inputmap {
        parts.push(format!(
            "snapshot_hashes.inputmap {} != {}",
            got.inputmap, want.inputmap
        ));
    }
    if parts.is_empty() {
        None
    } else {
        Some(format!(
            "GS-EC-36: replay tape header mismatch ({})",
            parts.join(", ")
        ))
    }
}

fn clamp_tape_value(value: f64) -> f32 {
    if !value.is_finite() {
        return 0.0;
    }
    (value as f32).clamp(-1.0, 1.0)
}

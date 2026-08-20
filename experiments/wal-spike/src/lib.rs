//! WAL spike (WP-M-1-c): replayable records, I2 flush-before-ACK, I6 tail vs middle.
//!
//! Protocol: validate → write record → FLUSH (`File::sync_data`) → apply → persist ACK → ACK.

mod document;
mod persist;
mod record;

pub use document::{ApplyError, Command, Document};
pub use persist::{AckCursor, AutosaveSidecar, Paths, WalTail};
pub use record::{WalRecord, SCHEMA_VERSION};

use persist::{
    append_ack, append_and_sync, append_partial_and_sync, autosave, load_ack,
    load_latest_valid_autosave, mark_dirty, scan_wal, truncate_to,
};
use thiserror::Error;

/// Simulated crash points matching MASTER 5.5 / GS-EC-38.
/// Tests close/truncate at these moments instead of `kill -9` (awkward on Windows);
/// the durable bytes on disk match a crash at that instant.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CrashPoint {
    /// (a) Mid JSONL record: only a prefix of the line is on disk.
    MidRecordWrite,
    /// (b) Full record written + fsynced; apply and ACK not reached.
    AfterFlushBeforeApply,
    /// (c) Autosave tmp files written + synced; rename not performed.
    MidAutosaveRename,
}

#[derive(Debug, Error)]
pub enum Error {
    #[error("simulated crash at {0:?}")]
    Crash(CrashPoint),
    #[error(transparent)]
    Apply(#[from] ApplyError),
    #[error(transparent)]
    Io(#[from] std::io::Error),
    #[error(transparent)]
    Json(#[from] serde_json::Error),
    #[error("WAL corrupt in the middle at byte {at_byte} (I6: stop, do not guess)")]
    CorruptMiddle { at_byte: u64 },
    #[error("revision chain break at seq {seq}: expected base {expected}, got {got}")]
    ChainBreak {
        seq: u64,
        expected: String,
        got: String,
    },
    #[error("ACK cursor seq {ack_seq} is ahead of WAL (last wal seq {wal_seq})")]
    AckAheadOfWal { ack_seq: u64, wal_seq: u64 },
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Ack {
    pub seq: u64,
    pub txn_id: String,
    pub command_id: String,
    pub revision: String,
}

#[derive(Debug)]
pub struct Session {
    paths: Paths,
    doc: Document,
    last_ack: AckCursor,
    next_seq: u64,
    crash: Option<CrashPoint>,
}

impl Session {
    pub fn open(root: impl Into<std::path::PathBuf>) -> Result<Self, Error> {
        let paths = Paths::new(root);
        paths.ensure_dirs()?;
        let recovered = recover(&paths)?;
        Ok(Self {
            next_seq: recovered.last_ack.seq.saturating_add(1),
            paths,
            doc: recovered.document,
            last_ack: recovered.last_ack,
            crash: None,
        })
    }

    pub fn inject_crash(&mut self, point: CrashPoint) {
        self.crash = Some(point);
    }

    pub fn document(&self) -> &Document {
        &self.doc
    }

    pub fn last_ack(&self) -> &AckCursor {
        &self.last_ack
    }

    pub fn paths(&self) -> &Paths {
        &self.paths
    }

    /// I2: validate → WAL write → FLUSH → apply → persist ACK → return ACK.
    pub fn commit(
        &mut self,
        actor_id: &str,
        command_id: &str,
        commands: Vec<Command>,
    ) -> Result<Ack, Error> {
        let commands: Vec<Command> = commands
            .iter()
            .map(Document::validate)
            .collect::<Result<_, _>>()?;

        let mut planned = self.doc.clone();
        let inverses = planned.apply_txn(&commands)?;

        let seq = self.next_seq;
        let record = WalRecord::new(
            seq,
            command_id,
            actor_id,
            self.doc.revision_label(),
            planned.revision_label(),
            commands,
            inverses,
        );
        let line = record.to_jsonl()?;

        if self.crash == Some(CrashPoint::MidRecordWrite) {
            let keep = (line.len() / 2).max(1).min(line.len().saturating_sub(1));
            append_partial_and_sync(&self.paths.wal_file, line.as_bytes(), keep)?;
            return Err(Error::Crash(CrashPoint::MidRecordWrite));
        }

        append_and_sync(&self.paths.wal_file, line.as_bytes())?;

        if self.crash == Some(CrashPoint::AfterFlushBeforeApply) {
            return Err(Error::Crash(CrashPoint::AfterFlushBeforeApply));
        }

        self.doc = planned;
        let cursor = AckCursor {
            seq,
            revision: self.doc.revision_label(),
        };
        append_ack(&self.paths.ack_file, &cursor)?;
        mark_dirty(&self.paths)?;
        self.last_ack = cursor;
        self.next_seq = seq.saturating_add(1);

        Ok(Ack {
            seq,
            txn_id: record.txn_id,
            command_id: record.command_id,
            revision: self.doc.revision_label(),
        })
    }

    pub fn autosave(&mut self, scene: &str) -> Result<(), Error> {
        let crash = self.crash == Some(CrashPoint::MidAutosaveRename);
        let wrote = autosave(&self.paths, scene, self.last_ack.seq, &self.doc, crash)?;
        if crash {
            return Err(Error::Crash(CrashPoint::MidAutosaveRename));
        }
        let _ = wrote;
        Ok(())
    }
}

struct Recovered {
    document: Document,
    last_ack: AckCursor,
}

/// Recovery (MASTER 5.5):
/// 1. Load latest valid autosave (sidecar + sha256).
/// 2. Replay WAL records with last_committed_seq < seq <= last_ack.seq.
/// 3. Truncated / un-ACK'd tail: cut, do not apply.
/// 4. Corrupt middle: stop, do not guess.
fn recover(paths: &Paths) -> Result<Recovered, Error> {
    let last_ack = load_ack(&paths.ack_file)?;
    let scan = scan_wal(&paths.wal_file)?;

    if let WalTail::CorruptMiddle { at_byte } = scan.tail {
        return Err(Error::CorruptMiddle { at_byte });
    }

    let last_wal_seq = scan.records.last().map(|r| r.seq).unwrap_or(0);
    if last_ack.seq > last_wal_seq {
        return Err(Error::AckAheadOfWal {
            ack_seq: last_ack.seq,
            wal_seq: last_wal_seq,
        });
    }

    let autosave = load_latest_valid_autosave(paths)?;
    let (mut doc, mut committed_seq) = match autosave {
        Some(s) if s.seq <= last_ack.seq => (s.document, s.seq),
        Some(_) | None => (Document::default(), 0),
    };

    for rec in &scan.records {
        if rec.seq <= committed_seq {
            continue;
        }
        if rec.seq > last_ack.seq {
            break;
        }
        if rec.base_revision != doc.revision_label() {
            return Err(Error::ChainBreak {
                seq: rec.seq,
                expected: doc.revision_label(),
                got: rec.base_revision.clone(),
            });
        }
        doc.apply_txn(&rec.commands)?;
        if doc.revision_label() != rec.new_revision {
            return Err(Error::ChainBreak {
                seq: rec.seq,
                expected: rec.new_revision.clone(),
                got: doc.revision_label(),
            });
        }
        committed_seq = rec.seq;
    }

    if doc.revision_label() != last_ack.revision {
        return Err(Error::ChainBreak {
            seq: last_ack.seq,
            expected: last_ack.revision.clone(),
            got: doc.revision_label(),
        });
    }

    // Cut truncated tail and any flushed-but-un-ACK'd records (never apply those).
    let cut_at = end_of_ackd_records(&scan, last_ack.seq);
    if paths.wal_file.exists() {
        let meta = std::fs::metadata(&paths.wal_file)?;
        if meta.len() > cut_at {
            truncate_to(&paths.wal_file, cut_at)?;
        }
    }

    Ok(Recovered {
        document: doc,
        last_ack,
    })
}

fn end_of_ackd_records(scan: &persist::WalScan, last_ack_seq: u64) -> u64 {
    if last_ack_seq == 0 {
        return 0;
    }
    let mut cut = 0u64;
    for (rec, end) in scan.records.iter().zip(scan.record_ends.iter()) {
        if rec.seq > last_ack_seq {
            break;
        }
        cut = *end;
    }
    cut
}

#[cfg(test)]
mod recovery_unit {
    use super::*;
    use persist::WalScan;

    #[test]
    fn unacked_complete_record_is_not_in_cut_length() {
        let rec1 = WalRecord::new(
            1,
            "c1",
            "a",
            "r-000000",
            "r-000001",
            vec![Command::new(
                "counter.inc",
                serde_json::json!({ "delta": 1 }),
            )],
            vec![Command::new(
                "counter.inc",
                serde_json::json!({ "delta": -1 }),
            )],
        );
        let rec2 = WalRecord::new(
            2,
            "c2",
            "a",
            "r-000001",
            "r-000002",
            vec![Command::new(
                "counter.inc",
                serde_json::json!({ "delta": 1 }),
            )],
            vec![Command::new(
                "counter.inc",
                serde_json::json!({ "delta": -1 }),
            )],
        );
        let l1 = rec1.to_jsonl().unwrap().len() as u64;
        let l2 = rec2.to_jsonl().unwrap().len() as u64;
        let scan = WalScan {
            records: vec![rec1, rec2],
            record_ends: vec![l1, l1 + l2],
            tail: WalTail::Clean,
        };
        assert_eq!(end_of_ackd_records(&scan, 1), l1);
    }
}

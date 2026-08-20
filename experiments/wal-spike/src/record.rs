//! Replayable WAL record: full commands + inverses + crc32 (MASTER 5.5).
//! One atomic JSONL record per txn — not begin/commit two lines.

use serde::{Deserialize, Serialize};

use crate::document::Command;

pub const SCHEMA_VERSION: u32 = 1;
pub const KIND_TXN: &str = "txn";

/// On-disk JSONL object. `crc32` is 8 lowercase hex digits of CRC-32/ISO-HDLC
/// over the UTF-8 JSON of this object with the `crc32` field omitted.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct WalRecord {
    pub seq: u64,
    pub kind: String,
    pub txn_id: String,
    pub command_id: String,
    pub actor_id: String,
    pub base_revision: String,
    pub new_revision: String,
    pub commands: Vec<Command>,
    pub inverses: Vec<Command>,
    pub schema_version: u32,
    pub ts: String,
    pub crc32: String,
}

#[derive(Serialize)]
struct WalRecordBody<'a> {
    seq: u64,
    kind: &'a str,
    txn_id: &'a str,
    command_id: &'a str,
    actor_id: &'a str,
    base_revision: &'a str,
    new_revision: &'a str,
    commands: &'a [Command],
    inverses: &'a [Command],
    schema_version: u32,
    ts: &'a str,
}

impl WalRecord {
    pub fn new(
        seq: u64,
        command_id: impl Into<String>,
        actor_id: impl Into<String>,
        base_revision: impl Into<String>,
        new_revision: impl Into<String>,
        commands: Vec<Command>,
        inverses: Vec<Command>,
    ) -> Self {
        let mut rec = Self {
            seq,
            kind: KIND_TXN.to_string(),
            txn_id: format!("t-{seq:06}"),
            command_id: command_id.into(),
            actor_id: actor_id.into(),
            base_revision: base_revision.into(),
            new_revision: new_revision.into(),
            commands,
            inverses,
            schema_version: SCHEMA_VERSION,
            ts: unix_millis_ts(),
            crc32: String::new(),
        };
        rec.crc32 = rec.compute_crc32();
        rec
    }

    pub fn compute_crc32(&self) -> String {
        crc32_hex(&self.body_bytes())
    }

    pub fn crc_ok(&self) -> bool {
        self.crc32 == self.compute_crc32()
    }

    /// One JSON object + LF. Atomic record = this whole line.
    pub fn to_jsonl(&self) -> Result<String, serde_json::Error> {
        let mut s = serde_json::to_string(self)?;
        s.push('\n');
        Ok(s)
    }

    pub fn from_json_line(line: &str) -> Result<Self, serde_json::Error> {
        serde_json::from_str(line.trim_end_matches(['\r', '\n']))
    }

    fn body_bytes(&self) -> Vec<u8> {
        let body = WalRecordBody {
            seq: self.seq,
            kind: &self.kind,
            txn_id: &self.txn_id,
            command_id: &self.command_id,
            actor_id: &self.actor_id,
            base_revision: &self.base_revision,
            new_revision: &self.new_revision,
            commands: &self.commands,
            inverses: &self.inverses,
            schema_version: self.schema_version,
            ts: &self.ts,
        };
        serde_json::to_vec(&body).expect("record body is always serializable")
    }
}

pub fn crc32_hex(bytes: &[u8]) -> String {
    format!("{:08x}", crc32fast::hash(bytes))
}

fn unix_millis_ts() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let ms = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0);
    format!("{ms}")
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::document::Command;
    use serde_json::json;

    #[test]
    fn crc_round_trip_and_tamper() {
        let rec = WalRecord::new(
            1,
            "01TEST",
            "act_01",
            "r-000000",
            "r-000001",
            vec![Command::new("counter.inc", json!({ "delta": 1 }))],
            vec![Command::new("counter.inc", json!({ "delta": -1 }))],
        );
        assert!(rec.crc_ok());
        let line = rec.to_jsonl().unwrap();
        let parsed = WalRecord::from_json_line(&line).unwrap();
        assert_eq!(parsed, rec);
        assert!(parsed.crc_ok());

        let mut bad = parsed;
        bad.commands[0].params = json!({ "delta": 99 });
        assert!(!bad.crc_ok());
    }
}

//! Session (lock + recovery) and Dispatcher (I1 — only mutator).

use std::collections::{BTreeSet, HashMap};
use std::fs::{File, OpenOptions};
use std::path::Path;
use std::time::Instant;

use fs2::FileExt;
use serde_json::{json, Value};
use ulid::Ulid;

use crate::command::{Command, DispatchRequest};
use crate::document::{id_list, Document};
use crate::error::{CrashPoint, Error};
use crate::id::format_entity_id;
use crate::inputmap::is_inputmap_persist_method;
use crate::locks::{is_lock_method, mutation_lock_ids, LockTable, LOCK_QUOTA_PER_ACTOR};
use crate::persist::{
    append_ack, append_and_sync, append_partial_and_sync, autosave, load_ack,
    load_latest_valid_autosave, load_saved_document, mark_dirty, resolve_current_wal,
    rotate_wal_if_needed, scan_all_wals, scan_wal, truncate_to, write_tmp_rename, AckCursor, Paths,
    WalScan, WalTail,
};
use crate::record::WalRecord;
use crate::script::is_script_persist_method;
use crate::settings::is_settings_persist_method;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Ack {
    pub seq: u64,
    pub txn_id: String,
    pub command_id: String,
    pub revision: String,
    pub spawned_ids: Vec<String>,
    pub owner_token: Option<String>,
}

#[derive(Clone, Debug)]
struct UndoEntry {
    txn_id: String,
    actor_id: String,
    inverses: Vec<Command>,
    commands: Vec<Command>,
    touched: BTreeSet<u64>,
}

/// Opened project: lock, document, WAL, undo stack, command_id dedup.
#[derive(Debug)]
pub struct Session {
    paths: Paths,
    doc: Document,
    last_ack: AckCursor,
    next_seq: u64,
    crash: Option<CrashPoint>,
    read_only: bool,
    fail_stop: bool,
    _lock: Option<File>,
    dedup: HashMap<String, DedupEntry>,
    undo: Vec<UndoEntry>,
    locks: LockTable,
    clock: Option<Instant>,
}

#[derive(Clone, Debug)]
struct DedupEntry {
    ack: Ack,
    ts_ms: u128,
}

const DEDUP_MAX: usize = 100_000;
const DEDUP_TTL_MS: u128 = 24 * 60 * 60 * 1000;

impl Session {
    /// Exclusive open. Second exclusive open → `Error::AlreadyOpen`.
    pub fn open(root: impl AsRef<Path>) -> Result<Self, Error> {
        Self::open_inner(root.as_ref(), false)
    }

    /// Open without taking `editor.lock`. Mutations are rejected.
    pub fn open_read_only(root: impl AsRef<Path>) -> Result<Self, Error> {
        Self::open_inner(root.as_ref(), true)
    }

    fn open_inner(root: &Path, read_only: bool) -> Result<Self, Error> {
        let paths = Paths::new(root);
        paths.ensure_dirs()?;
        let lock = if read_only {
            None
        } else {
            let file = OpenOptions::new()
                .create(true)
                .read(true)
                .write(true)
                .truncate(false)
                .open(&paths.lock_file)?;
            file.try_lock_exclusive().map_err(|_| Error::AlreadyOpen)?;
            Some(file)
        };
        let mut paths = paths;
        resolve_current_wal(&mut paths)?;
        let recovered = recover(&paths)?;
        let mut doc = recovered.document;
        doc.project_root = Some(paths.root.clone());
        Ok(Self {
            next_seq: recovered.last_ack.seq.saturating_add(1),
            paths,
            doc,
            last_ack: recovered.last_ack,
            crash: None,
            read_only,
            fail_stop: false,
            _lock: lock,
            dedup: recovered.dedup,
            undo: recovered.undo,
            locks: LockTable::default(),
            clock: None,
        })
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

    pub fn is_read_only(&self) -> bool {
        self.read_only
    }

    pub fn inject_crash(&mut self, point: CrashPoint) {
        self.crash = Some(point);
    }

    pub fn canonical_scene_bytes(&self) -> Vec<u8> {
        self.doc.canonical_scene_bytes()
    }

    pub fn canonical_project_bytes(&self) -> Vec<u8> {
        self.doc.canonical_project_bytes()
    }

    /// I1 mutation surface.
    pub fn dispatcher(&mut self) -> Dispatcher<'_> {
        Dispatcher { session: self }
    }

    pub fn dispatch(&mut self, request: DispatchRequest) -> Result<Ack, Error> {
        self.dispatcher().execute(request)
    }

    /// Read-only `script.get_source` (not a WAL command).
    pub fn read_script_source(&self, path: &str) -> Result<String, Error> {
        self.doc.read_script_source(path)
    }

    /// Read-only `inputmap.get` (not a WAL command).
    pub fn read_inputmap(&self) -> Result<Value, Error> {
        self.doc.read_inputmap()
    }

    /// Read-only `project.settings_get` (not a WAL command).
    pub fn read_project_settings(&self) -> Value {
        self.doc.project_settings()
    }

    pub fn expire_locks(&mut self, now: Instant) {
        self.locks.expire(now);
    }

    /// Test clock for TTL. `Dispatcher::execute` uses this instead of `Instant::now`.
    pub fn set_clock(&mut self, now: Instant) {
        self.clock = Some(now);
    }

    pub fn release_locks_for_actor(&mut self, actor_id: &str) {
        self.locks.release_actor(actor_id);
    }

    pub fn lock_count_for(&self, actor_id: &str) -> usize {
        self.locks.actor_count(actor_id)
    }

    fn now(&self) -> Instant {
        self.clock.unwrap_or_else(Instant::now)
    }

    fn apply_lock_table(
        &mut self,
        actor_id: &str,
        commands: &[Command],
        now: Instant,
    ) -> Option<String> {
        let mut token = None;
        for cmd in commands {
            match cmd.method.as_str() {
                "entity.lock" => {
                    token = Some(self.locks.apply_lock(actor_id, cmd, now));
                }
                "entity.unlock" => {
                    self.locks.apply_unlock(cmd);
                }
                _ => {}
            }
        }
        token
    }

    pub fn undo_last(&mut self, command_id: &str, actor_id: &str) -> Result<Ack, Error> {
        self.dispatcher().undo_last(command_id, actor_id)
    }

    pub fn revert_own(
        &mut self,
        command_id: &str,
        actor_id: &str,
        txn_id: &str,
    ) -> Result<Ack, Error> {
        self.dispatcher().revert_own(command_id, actor_id, txn_id)
    }

    pub fn save(&mut self) -> Result<(), Error> {
        if self.read_only {
            return Err(Error::ReadOnly);
        }
        let project = self.doc.canonical_project_bytes();
        write_tmp_rename(&self.paths.project_file, &project)?;
        let scene = self.doc.canonical_scene_bytes();
        write_tmp_rename(&self.paths.scene_file, &scene)?;
        if self.paths.dirty.exists() {
            std::fs::remove_file(&self.paths.dirty)?;
        }
        Ok(())
    }

    pub fn autosave(&mut self) -> Result<(), Error> {
        if self.read_only {
            return Err(Error::ReadOnly);
        }
        let crash = self.crash == Some(CrashPoint::MidAutosaveRename);
        if crash {
            self.crash = None;
        }
        autosave(&self.paths, "main", self.last_ack.seq, &self.doc, crash)?;
        if crash {
            return Err(Error::Crash(CrashPoint::MidAutosaveRename));
        }
        Ok(())
    }
}

/// The only document mutator (I1). Obtained from [`Session::dispatcher`].
pub struct Dispatcher<'a> {
    session: &'a mut Session,
}

impl Dispatcher<'_> {
    pub fn execute(&mut self, request: DispatchRequest) -> Result<Ack, Error> {
        request.validate_command_id()?;
        if self.session.read_only {
            return Err(Error::ReadOnly);
        }
        if self.session.fail_stop {
            return Err(Error::DiskFull {
                op: "wal".to_string(),
            });
        }
        if let Some(prev) = self.session.dedup.get(&request.command_id).cloned() {
            return Ok(prev.ack);
        }
        if self.session.crash == Some(CrashPoint::BetweenRecords) {
            self.session.crash = None;
            return Err(Error::Crash(CrashPoint::BetweenRecords));
        }
        if let Some(ref expected) = request.expected_revision {
            let current = self.session.doc.revision_label();
            if expected != &current {
                return Err(Error::Conflict {
                    expected: expected.clone(),
                    current,
                });
            }
        }

        let now = self.session.now();
        self.session.expire_locks(now);
        let mut commands = request.commands.clone();
        self.prepare_lock_commands(&request.actor_id, &mut commands)?;
        self.check_mutation_locks(&request.actor_id, &commands)?;

        let planned = self.session.doc.plan_txn(&commands)?;
        if request.dry_run {
            let spawned_ids = spawned_ids_from(&planned.commands);
            return Ok(Ack {
                seq: self.session.next_seq,
                txn_id: String::new(),
                command_id: request.command_id.clone(),
                revision: planned.document.revision_label(),
                spawned_ids,
                owner_token: owner_token_from(&planned.commands),
            });
        }
        self.commit_planned(
            &request.command_id,
            &request.actor_id,
            planned.commands,
            planned.inverses,
            planned.document,
            now,
        )
    }

    fn prepare_lock_commands(&self, actor_id: &str, commands: &mut [Command]) -> Result<(), Error> {
        let mut new_lock_ids = BTreeSet::new();
        for cmd in commands.iter() {
            if cmd.method != "entity.lock" {
                continue;
            }
            let ids = id_list(&cmd.params, "ids", "entity.lock")?;
            for id in ids {
                if let Some(lock) = self.session.locks.get(id) {
                    if lock.owner_actor != actor_id {
                        return Err(Error::Locked {
                            id: format_entity_id(id),
                            owner: lock.owner_actor.clone(),
                            note: lock.note.clone(),
                        });
                    }
                } else {
                    new_lock_ids.insert(id);
                }
            }
        }
        if self.session.locks.actor_count(actor_id) + new_lock_ids.len() > LOCK_QUOTA_PER_ACTOR {
            return Err(Error::invalid(
                "entity.lock",
                "lock quota exceeded (100 per actor)",
            ));
        }

        for cmd in commands.iter_mut() {
            match cmd.method.as_str() {
                "entity.lock" => {
                    let token = self.choose_lock_token(actor_id, cmd);
                    if let Value::Object(map) = &mut cmd.params {
                        map.insert("owner_token".into(), json!(token));
                    }
                }
                "entity.unlock" => {
                    let force = cmd
                        .params
                        .get("force")
                        .and_then(Value::as_bool)
                        .unwrap_or(false);
                    let ids = id_list(&cmd.params, "ids", "entity.unlock")?;
                    for id in ids {
                        if let Some(lock) = self.session.locks.get(id) {
                            if lock.owner_actor != actor_id && !force {
                                return Err(Error::Locked {
                                    id: format_entity_id(id),
                                    owner: lock.owner_actor.clone(),
                                    note: lock.note.clone(),
                                });
                            }
                        }
                    }
                }
                _ => {}
            }
        }
        Ok(())
    }

    fn choose_lock_token(&self, actor_id: &str, cmd: &Command) -> String {
        let ids = id_list(&cmd.params, "ids", "entity.lock").unwrap_or_default();
        let mut existing = None;
        for id in ids {
            match self.session.locks.get(id) {
                Some(lock) if lock.owner_actor == actor_id => {
                    if existing.is_none() {
                        existing = Some(lock.owner_token.clone());
                    }
                }
                _ => return Ulid::new().to_string(),
            }
        }
        existing.unwrap_or_else(|| Ulid::new().to_string())
    }

    fn check_mutation_locks(&self, actor_id: &str, commands: &[Command]) -> Result<(), Error> {
        for cmd in commands {
            if is_lock_method(&cmd.method) {
                continue;
            }
            for id in mutation_lock_ids(cmd) {
                self.session.locks.check_other(actor_id, id)?;
            }
        }
        Ok(())
    }

    pub fn undo_last(&mut self, command_id: &str, actor_id: &str) -> Result<Ack, Error> {
        let inverses = self
            .session
            .undo
            .last()
            .ok_or_else(|| Error::invalid("undo.perform", "undo stack is empty"))?
            .inverses
            .clone();
        self.execute(DispatchRequest::transaction(command_id, actor_id, inverses))
    }

    /// Agent revert: only the actor's own txn, and only if no later txn
    /// touches the same entities (MASTER 2.8).
    pub fn revert_own(
        &mut self,
        command_id: &str,
        actor_id: &str,
        txn_id: &str,
    ) -> Result<Ack, Error> {
        let idx = self
            .session
            .undo
            .iter()
            .rposition(|e| e.txn_id == txn_id)
            .ok_or_else(|| Error::NotFound(txn_id.to_string()))?;
        let entry = &self.session.undo[idx];
        if entry.actor_id != actor_id {
            return Err(Error::invalid(
                "undo.revert_own",
                "txn belongs to another actor",
            ));
        }
        if entry.commands.is_empty() {
            return Err(Error::invalid("undo.revert_own", "txn has no commands"));
        }
        let touched = entry.touched.clone();
        let inverses = entry.inverses.clone();
        for later in &self.session.undo[idx + 1..] {
            if later.touched.iter().any(|id| touched.contains(id)) {
                return Err(Error::Conflict {
                    expected: entry.txn_id.clone(),
                    current: later.txn_id.clone(),
                });
            }
        }
        self.execute(DispatchRequest::transaction(command_id, actor_id, inverses))
    }

    fn commit_planned(
        &mut self,
        command_id: &str,
        actor_id: &str,
        commands: Vec<Command>,
        inverses: Vec<Command>,
        planned: Document,
        now: Instant,
    ) -> Result<Ack, Error> {
        let seq = self.session.next_seq;
        let record = WalRecord::new(
            seq,
            command_id,
            actor_id,
            self.session.doc.revision_label(),
            planned.revision_label(),
            commands.clone(),
            inverses.clone(),
        );
        let line = record.to_jsonl()?;

        if self.session.crash == Some(CrashPoint::FsyncFail) {
            self.session.crash = None;
            self.session.fail_stop = true;
            return Err(Error::DiskFull {
                op: "wal.fsync".to_string(),
            });
        }

        if self.session.crash == Some(CrashPoint::MidRecordWrite) {
            self.session.crash = None;
            let keep = (line.len() / 2).max(1).min(line.len().saturating_sub(1));
            append_partial_and_sync(&self.session.paths.wal_file, line.as_bytes(), keep)?;
            return Err(Error::Crash(CrashPoint::MidRecordWrite));
        }

        rotate_wal_if_needed(&mut self.session.paths)?;
        append_and_sync(&self.session.paths.wal_file, line.as_bytes())?;

        if self.session.crash == Some(CrashPoint::AfterFlushBeforeApply) {
            self.session.crash = None;
            return Err(Error::Crash(CrashPoint::AfterFlushBeforeApply));
        }

        self.session.doc = planned;
        persist_file_commands(&self.session.doc, &commands)?;
        let owner_token = self.session.apply_lock_table(actor_id, &commands, now);
        let cursor = AckCursor {
            seq,
            revision: self.session.doc.revision_label(),
        };
        append_ack(&self.session.paths.ack_file, &cursor)?;
        mark_dirty(&self.session.paths)?;
        self.session.last_ack = cursor;
        self.session.next_seq = seq.saturating_add(1);

        let spawned_ids = spawned_ids_from(&commands);
        let ack = Ack {
            seq,
            txn_id: record.txn_id.clone(),
            command_id: record.command_id.clone(),
            revision: self.session.doc.revision_label(),
            spawned_ids,
            owner_token,
        };
        let ts_ms = record.ts.parse::<u128>().unwrap_or_else(|_| unix_now_ms());
        dedup_insert(
            &mut self.session.dedup,
            record.command_id.clone(),
            ack.clone(),
            ts_ms,
        );
        if !inverses.is_empty() {
            let touched = Document::touched_entity_ids(&commands);
            self.session.undo.push(UndoEntry {
                txn_id: record.txn_id,
                actor_id: actor_id.to_string(),
                inverses,
                commands,
                touched,
            });
        }
        Ok(ack)
    }
}

/// File side-effects run only after WAL fsync + in-memory apply (I2).
fn persist_file_commands(doc: &Document, commands: &[Command]) -> Result<(), Error> {
    for cmd in commands {
        if cmd.method == "blueprint.create" {
            doc.persist_blueprint_create(cmd)?;
        }
        if is_script_persist_method(&cmd.method) {
            doc.persist_script_file(cmd)?;
        }
        if is_inputmap_persist_method(&cmd.method) {
            doc.persist_inputmap_file(cmd)?;
        }
        if is_settings_persist_method(&cmd.method) {
            doc.persist_project_settings_file()?;
        }
    }
    Ok(())
}

fn owner_token_from(commands: &[Command]) -> Option<String> {
    commands.iter().rev().find_map(|cmd| {
        if cmd.method == "entity.lock" {
            cmd.params
                .get("owner_token")
                .and_then(Value::as_str)
                .map(ToOwned::to_owned)
        } else {
            None
        }
    })
}

fn spawned_ids_from(commands: &[Command]) -> Vec<String> {
    let mut ids = Vec::new();
    for cmd in commands {
        match cmd.method.as_str() {
            "entity.spawn" => {
                if let Some(id) = cmd.params.get("id").and_then(|v| v.as_str()) {
                    ids.push(id.to_string());
                }
            }
            "blueprint.instantiate" | "entity.duplicate" => {
                if let Some(arr) = cmd.params.get("entities").and_then(|v| v.as_array()) {
                    for e in arr {
                        if let Some(id) = e.get("id").and_then(|v| v.as_str()) {
                            ids.push(id.to_string());
                        }
                    }
                }
            }
            _ => {}
        }
    }
    ids
}

fn unix_now_ms() -> u128 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0)
}

fn dedup_insert(map: &mut HashMap<String, DedupEntry>, command_id: String, ack: Ack, ts_ms: u128) {
    map.insert(command_id, DedupEntry { ack, ts_ms });
    if map.len() <= DEDUP_MAX {
        return;
    }
    let cutoff = ts_ms.saturating_sub(DEDUP_TTL_MS);
    let mut oldest: Option<(String, u128)> = None;
    map.retain(|id, e| {
        if e.ts_ms < cutoff {
            return false;
        }
        match &oldest {
            None => oldest = Some((id.clone(), e.ts_ms)),
            Some((_, t)) if e.ts_ms < *t => oldest = Some((id.clone(), e.ts_ms)),
            _ => {}
        }
        true
    });
    if map.len() > DEDUP_MAX {
        if let Some((id, _)) = oldest {
            map.remove(&id);
        }
    }
}

struct Recovered {
    document: Document,
    last_ack: AckCursor,
    dedup: HashMap<String, DedupEntry>,
    undo: Vec<UndoEntry>,
}

fn recover(paths: &Paths) -> Result<Recovered, Error> {
    let last_ack = load_ack(&paths.ack_file)?;
    crate::id::parse_revision(&last_ack.revision)?;
    let scan = scan_all_wals(paths)?;

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
    let saved = load_saved_document(paths)?;
    let (mut doc, mut committed_seq) = match autosave {
        Some(s) if s.seq <= last_ack.seq => (s.document, s.seq),
        Some(_) | None => match saved {
            Some(d) if last_ack.seq == 0 => (d, 0),
            Some(_) | None => (Document::default(), 0),
        },
    };
    doc.project_root = Some(paths.root.clone());

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
        persist_file_commands(&doc, &rec.commands)?;
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

    let current_scan = if paths.wal_file.exists() {
        scan_wal(&paths.wal_file)?
    } else {
        WalScan::default()
    };
    let cut_at = end_of_ackd_records(&current_scan, last_ack.seq);
    if paths.wal_file.exists() {
        let meta = std::fs::metadata(&paths.wal_file)?;
        let should_cut = if current_scan
            .records
            .first()
            .map(|r| r.seq > last_ack.seq)
            .unwrap_or(false)
        {
            true
        } else {
            meta.len() > cut_at
        };
        if should_cut {
            truncate_to(&paths.wal_file, cut_at)?;
        }
    }

    let mut dedup = HashMap::new();
    let mut undo = Vec::new();
    for rec in &scan.records {
        if rec.seq > last_ack.seq {
            break;
        }
        let spawned_ids = spawned_ids_from(&rec.commands);
        let ack = Ack {
            seq: rec.seq,
            txn_id: rec.txn_id.clone(),
            command_id: rec.command_id.clone(),
            revision: rec.new_revision.clone(),
            spawned_ids,
            owner_token: owner_token_from(&rec.commands),
        };
        let ts_ms = rec.ts.parse::<u128>().unwrap_or(0);
        dedup_insert(&mut dedup, rec.command_id.clone(), ack, ts_ms);
        if !rec.inverses.is_empty() {
            undo.push(UndoEntry {
                txn_id: rec.txn_id.clone(),
                actor_id: rec.actor_id.clone(),
                inverses: rec.inverses.clone(),
                commands: rec.commands.clone(),
                touched: Document::touched_entity_ids(&rec.commands),
            });
        }
    }

    Ok(Recovered {
        document: doc,
        last_ack,
        dedup,
        undo,
    })
}

fn end_of_ackd_records(scan: &WalScan, last_ack_seq: u64) -> u64 {
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
    use crate::command::Command;
    use serde_json::json;

    #[test]
    fn unacked_complete_record_is_not_in_cut_length() {
        let rec1 = WalRecord::new(
            1,
            "c1",
            "a",
            "r-000000",
            "r-000001",
            vec![Command::new(
                "entity.spawn",
                json!({ "id": "e_000001", "scene_id": "s_main" }),
            )],
            vec![Command::new(
                "entity.destroy",
                json!({ "ids": ["e_000001"] }),
            )],
        );
        let rec2 = WalRecord::new(
            2,
            "c2",
            "a",
            "r-000001",
            "r-000002",
            vec![Command::new(
                "entity.spawn",
                json!({ "id": "e_000002", "scene_id": "s_main" }),
            )],
            vec![Command::new(
                "entity.destroy",
                json!({ "ids": ["e_000002"] }),
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

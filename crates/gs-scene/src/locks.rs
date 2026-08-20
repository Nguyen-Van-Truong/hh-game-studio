//! Session entity locks (MASTER 4.3). Table lives on Session; Dispatcher
//! expire/check/apply runs before document apply. WAL records the command
//! (I2/I11); Undo::None → empty inverse. Lock table is not rebuilt on open.

use std::collections::HashMap;
use std::time::{Duration, Instant};

use serde_json::{json, Value};

use crate::command::Command;
use crate::document::{id_list, optional_string, Document};
use crate::error::Error;
use crate::id::{format_entity_id, parse_entity_id};

pub const LOCK_TTL: Duration = Duration::from_secs(60);
pub const LOCK_QUOTA_PER_ACTOR: usize = 100;

#[derive(Clone, Debug)]
pub struct EntityLock {
    pub owner_actor: String,
    pub owner_token: String,
    pub note: String,
    pub expires_at: Instant,
}

#[derive(Clone, Debug, Default)]
pub struct LockTable {
    by_entity: HashMap<u64, EntityLock>,
}

impl LockTable {
    pub fn expire(&mut self, now: Instant) {
        self.by_entity.retain(|_, lock| lock.expires_at > now);
    }

    pub fn get(&self, id: u64) -> Option<&EntityLock> {
        self.by_entity.get(&id)
    }

    pub fn actor_count(&self, actor_id: &str) -> usize {
        self.by_entity
            .values()
            .filter(|lock| lock.owner_actor == actor_id)
            .count()
    }

    pub fn release_actor(&mut self, actor_id: &str) {
        self.by_entity
            .retain(|_, lock| lock.owner_actor != actor_id);
    }

    pub fn check_other(&self, actor_id: &str, entity_id: u64) -> Result<(), Error> {
        if let Some(lock) = self.by_entity.get(&entity_id) {
            if lock.owner_actor != actor_id {
                return Err(Error::Locked {
                    id: format_entity_id(entity_id),
                    owner: lock.owner_actor.clone(),
                    note: lock.note.clone(),
                });
            }
        }
        Ok(())
    }

    pub fn apply_lock(&mut self, actor_id: &str, cmd: &Command, now: Instant) -> String {
        let ids = lock_ids(cmd);
        let note = cmd
            .params
            .get("note")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string();
        let token = cmd
            .params
            .get("owner_token")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string();
        let expires_at = now + LOCK_TTL;
        for id in ids {
            self.by_entity.insert(
                id,
                EntityLock {
                    owner_actor: actor_id.to_string(),
                    owner_token: token.clone(),
                    note: note.clone(),
                    expires_at,
                },
            );
        }
        token
    }

    pub fn apply_unlock(&mut self, cmd: &Command) {
        for id in lock_ids(cmd) {
            self.by_entity.remove(&id);
        }
    }
}

pub fn is_lock_method(method: &str) -> bool {
    matches!(method, "entity.lock" | "entity.unlock")
}

pub fn mutation_lock_ids(cmd: &Command) -> Vec<u64> {
    if is_lock_method(&cmd.method) || cmd.method == "project.settings_set" {
        return Vec::new();
    }
    if matches!(
        cmd.method.as_str(),
        "script.create" | "script.set_source" | "script.ingest_external" | "inputmap.set"
    ) {
        return Vec::new();
    }
    let mut out = Vec::new();
    collect_ids(&cmd.params, &mut out);
    out
}

fn lock_ids(cmd: &Command) -> Vec<u64> {
    cmd.params
        .get("ids")
        .and_then(Value::as_array)
        .map(|arr| {
            arr.iter()
                .filter_map(|v| v.as_str())
                .filter_map(|s| parse_entity_id(s).ok())
                .collect()
        })
        .unwrap_or_default()
}

fn collect_ids(value: &Value, out: &mut Vec<u64>) {
    match value {
        Value::String(s) => {
            if let Ok(n) = parse_entity_id(s) {
                if !out.contains(&n) {
                    out.push(n);
                }
            }
        }
        Value::Array(items) => {
            for item in items {
                collect_ids(item, out);
            }
        }
        Value::Object(map) => {
            for key in [
                "id",
                "ids",
                "entity_id",
                "parent",
                "new_parent",
                "from_entity",
            ] {
                if let Some(v) = map.get(key) {
                    collect_ids(v, out);
                }
            }
        }
        _ => {}
    }
}

impl Document {
    pub(crate) fn normalize_entity_lock(&self, cmd: &Command) -> Result<Command, Error> {
        normalize_lock_ids(self, cmd, "entity.lock")
    }

    pub(crate) fn normalize_entity_unlock(&self, cmd: &Command) -> Result<Command, Error> {
        normalize_lock_ids(self, cmd, "entity.unlock")
    }

    pub(crate) fn apply_entity_lock(&self, _cmd: &Command) -> Result<Vec<Command>, Error> {
        Ok(Vec::new())
    }

    pub(crate) fn apply_entity_unlock(&self, _cmd: &Command) -> Result<Vec<Command>, Error> {
        Ok(Vec::new())
    }
}

fn normalize_lock_ids(doc: &Document, cmd: &Command, method: &str) -> Result<Command, Error> {
    let ids = id_list(&cmd.params, "ids", method)?;
    if ids.is_empty() {
        return Err(Error::invalid(method, "ids must be non-empty"));
    }
    for id in &ids {
        if !doc.scene.entities.contains_key(id) {
            return Err(Error::NotFound(format_entity_id(*id)));
        }
    }
    let mut params = serde_json::Map::new();
    params.insert(
        "ids".into(),
        json!(ids
            .iter()
            .copied()
            .map(format_entity_id)
            .collect::<Vec<_>>()),
    );
    if method == "entity.lock" {
        let note = optional_string(&cmd.params, "note", method)?.unwrap_or_default();
        params.insert("note".into(), json!(note));
        if let Some(token) = cmd.params.get("owner_token").and_then(Value::as_str) {
            params.insert("owner_token".into(), json!(token));
        }
    } else {
        let force = cmd
            .params
            .get("force")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        params.insert("force".into(), json!(force));
        if let Some(token) = cmd.params.get("owner_token").and_then(Value::as_str) {
            params.insert("owner_token".into(), json!(token));
        }
    }
    Ok(Command::new(method, Value::Object(params)))
}

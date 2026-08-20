//! Tiny in-memory document so apply / inverse is real (not a digest).
//!
//! Commands (params are JSON objects, fully normalized before WAL write):
//! - `counter.inc`  `{ "delta": <i64> }`
//! - `entity.set`   `{ "id": <string>, "value": <i64> }`
//! - `entity.delete` `{ "id": <string> }`

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum ApplyError {
    #[error("unknown method {0}")]
    UnknownMethod(String),
    #[error("invalid params for {method}: {reason}")]
    InvalidParams { method: String, reason: String },
    #[error("entity {0} not found")]
    EntityNotFound(String),
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct Command {
    pub method: String,
    pub params: Value,
}

impl Command {
    pub fn new(method: impl Into<String>, params: Value) -> Self {
        Self {
            method: method.into(),
            params,
        }
    }
}

#[derive(Clone, Debug, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct Document {
    pub revision: u64,
    pub counter: i64,
    pub entities: BTreeMap<String, i64>,
}

impl Document {
    pub fn revision_label(&self) -> String {
        format!("r-{:06}", self.revision)
    }

    /// Validate + normalize one command. Does not mutate.
    pub fn validate(cmd: &Command) -> Result<Command, ApplyError> {
        match cmd.method.as_str() {
            "counter.inc" => {
                let delta = i64_field(&cmd.params, "delta", "counter.inc")?;
                Ok(Command::new("counter.inc", json!({ "delta": delta })))
            }
            "entity.set" => {
                let id = string_field(&cmd.params, "id", "entity.set")?;
                let value = i64_field(&cmd.params, "value", "entity.set")?;
                if id.is_empty() {
                    return Err(ApplyError::InvalidParams {
                        method: "entity.set".into(),
                        reason: "id must be non-empty".into(),
                    });
                }
                Ok(Command::new(
                    "entity.set",
                    json!({ "id": id, "value": value }),
                ))
            }
            "entity.delete" => {
                let id = string_field(&cmd.params, "id", "entity.delete")?;
                if id.is_empty() {
                    return Err(ApplyError::InvalidParams {
                        method: "entity.delete".into(),
                        reason: "id must be non-empty".into(),
                    });
                }
                Ok(Command::new("entity.delete", json!({ "id": id })))
            }
            other => Err(ApplyError::UnknownMethod(other.to_string())),
        }
    }

    /// Apply one already-validated command. Returns its inverse. Does not bump revision.
    pub fn apply_command(&mut self, cmd: &Command) -> Result<Command, ApplyError> {
        let cmd = Self::validate(cmd)?;
        match cmd.method.as_str() {
            "counter.inc" => {
                let delta = i64_field(&cmd.params, "delta", "counter.inc")?;
                self.counter = self.counter.saturating_add(delta);
                Ok(Command::new("counter.inc", json!({ "delta": -delta })))
            }
            "entity.set" => {
                let id = string_field(&cmd.params, "id", "entity.set")?;
                let value = i64_field(&cmd.params, "value", "entity.set")?;
                match self.entities.insert(id.clone(), value) {
                    Some(old) => Ok(Command::new(
                        "entity.set",
                        json!({ "id": id, "value": old }),
                    )),
                    None => Ok(Command::new("entity.delete", json!({ "id": id }))),
                }
            }
            "entity.delete" => {
                let id = string_field(&cmd.params, "id", "entity.delete")?;
                match self.entities.remove(&id) {
                    Some(old) => Ok(Command::new(
                        "entity.set",
                        json!({ "id": id, "value": old }),
                    )),
                    None => Err(ApplyError::EntityNotFound(id)),
                }
            }
            other => Err(ApplyError::UnknownMethod(other.to_string())),
        }
    }

    /// Apply a transaction: all commands, then bump revision once.
    /// Inverses are stored in undo order (reverse of apply).
    pub fn apply_txn(&mut self, commands: &[Command]) -> Result<Vec<Command>, ApplyError> {
        if commands.is_empty() {
            return Err(ApplyError::InvalidParams {
                method: "txn".into(),
                reason: "empty command list".into(),
            });
        }
        let mut inverses = Vec::with_capacity(commands.len());
        for cmd in commands {
            inverses.push(self.apply_command(cmd)?);
        }
        inverses.reverse();
        self.revision = self.revision.saturating_add(1);
        Ok(inverses)
    }
}

fn i64_field(params: &Value, key: &str, method: &str) -> Result<i64, ApplyError> {
    let Some(v) = params.get(key) else {
        return Err(ApplyError::InvalidParams {
            method: method.into(),
            reason: format!("missing {key}"),
        });
    };
    v.as_i64().ok_or_else(|| ApplyError::InvalidParams {
        method: method.into(),
        reason: format!("{key} must be i64"),
    })
}

fn string_field(params: &Value, key: &str, method: &str) -> Result<String, ApplyError> {
    let Some(v) = params.get(key) else {
        return Err(ApplyError::InvalidParams {
            method: method.into(),
            reason: format!("missing {key}"),
        });
    };
    v.as_str()
        .map(str::to_string)
        .ok_or_else(|| ApplyError::InvalidParams {
            method: method.into(),
            reason: format!("{key} must be string"),
        })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn apply_then_inverses_restores_document() {
        let original = Document::default();
        let mut doc = original.clone();
        let commands = vec![
            Command::new("counter.inc", json!({ "delta": 5 })),
            Command::new("entity.set", json!({ "id": "door", "value": 3 })),
            Command::new("entity.set", json!({ "id": "door", "value": 9 })),
        ];
        let inverses = doc.apply_txn(&commands).unwrap();
        assert_eq!(doc.counter, 5);
        assert_eq!(doc.entities.get("door"), Some(&9));
        assert_eq!(doc.revision, 1);

        for inv in &inverses {
            doc.apply_command(inv).unwrap();
        }
        doc.revision = original.revision;
        assert_eq!(doc, original);
    }

    #[test]
    fn validate_rejects_unknown_method() {
        let err = Document::validate(&Command::new("nope", json!({}))).unwrap_err();
        assert!(matches!(err, ApplyError::UnknownMethod(_)));
    }
}

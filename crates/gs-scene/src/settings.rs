//! `project.settings_get` / `project.settings_set` (MASTER 4.2 / I5).
//! Settings live as extra keys on `project.json` (`Document.unknown`).

use std::collections::BTreeMap;

use serde_json::{json, Map, Value};

use crate::blueprint::resolve_under_root;
use crate::command::Command;
use crate::document::Document;
use crate::error::Error;
use crate::persist::write_tmp_rename;

const METHOD_SET: &str = "project.settings_set";
const METHOD_GET: &str = "project.settings_get";
const PROJECT_REL: &str = "project.json";

const RESERVED: &[&str] = &[
    "schema_version",
    "revision",
    "next_entity",
    "next_asset",
    "last_committed_seq",
    "scene_id",
];

pub fn default_project_settings() -> Value {
    json!({
        "fixed_dt": 1.0 / 60.0,
        "ppu": 16,
        "schema_version": 1,
    })
}

pub fn merged_settings(unknown: &BTreeMap<String, Value>) -> Value {
    let mut map = match default_project_settings() {
        Value::Object(m) => m,
        _ => Map::new(),
    };
    for (k, v) in unknown {
        map.insert(k.clone(), v.clone());
    }
    Value::Object(map)
}

pub(crate) fn is_settings_persist_method(method: &str) -> bool {
    method == METHOD_SET
}

pub(crate) fn get_is_readonly() -> Error {
    Error::invalid(
        METHOD_GET,
        "read-only; use Document::project_settings or Session::read_project_settings",
    )
}

impl Document {
    pub fn project_settings(&self) -> Value {
        merged_settings(&self.unknown)
    }

    pub(crate) fn normalize_settings_set(&self, cmd: &Command) -> Result<Command, Error> {
        let patch = cmd
            .params
            .get("patch")
            .ok_or_else(|| Error::invalid(METHOD_SET, "missing patch"))?;
        let obj = patch
            .as_object()
            .ok_or_else(|| Error::invalid(METHOD_SET, "patch must be an object"))?;
        let mut cleaned = Map::new();
        for (k, v) in obj {
            if RESERVED.contains(&k.as_str()) {
                return Err(Error::invalid(
                    METHOD_SET,
                    format!("{k} is not a settings field"),
                ));
            }
            validate_known(k, v)?;
            cleaned.insert(k.clone(), v.clone());
        }
        Ok(Command::new(
            METHOD_SET,
            json!({ "patch": Value::Object(cleaned) }),
        ))
    }

    pub(crate) fn apply_settings_set(&mut self, cmd: &Command) -> Result<Vec<Command>, Error> {
        let patch = cmd
            .params
            .get("patch")
            .and_then(Value::as_object)
            .ok_or_else(|| Error::invalid(METHOD_SET, "missing patch"))?;
        let mut previous = Map::new();
        for (k, v) in patch {
            previous.insert(
                k.clone(),
                self.unknown.get(k).cloned().unwrap_or(Value::Null),
            );
            if v.is_null() {
                self.unknown.remove(k);
            } else {
                self.unknown.insert(k.clone(), v.clone());
            }
        }
        Ok(vec![Command::new(
            METHOD_SET,
            json!({ "patch": Value::Object(previous) }),
        )])
    }

    pub fn persist_project_settings_file(&self) -> Result<(), Error> {
        let root = self.project_root(METHOD_SET)?;
        let abs = resolve_under_root(root, PROJECT_REL)?;
        write_tmp_rename(&abs, &self.canonical_project_bytes())?;
        Ok(())
    }
}

fn validate_known(key: &str, value: &Value) -> Result<(), Error> {
    match key {
        "fixed_dt" | "ppu" => {
            let n = value
                .as_f64()
                .ok_or_else(|| Error::invalid(METHOD_SET, format!("{key} must be a number")))?;
            if !n.is_finite() || n <= 0.0 {
                return Err(Error::invalid(
                    METHOD_SET,
                    format!("{key} must be a positive finite number"),
                ));
            }
            Ok(())
        }
        _ => Ok(()),
    }
}

//! Input map file commands (MASTER 4.2 / 6.4). Disk writes happen after WAL.

use std::collections::BTreeSet;
use std::fs;
use std::path::Path;

use serde_json::{json, Map, Value};

use crate::blueprint::resolve_under_root;
use crate::canonical::to_canonical_string;
use crate::command::Command;
use crate::document::Document;
use crate::error::Error;
use crate::persist::{reject_conflict_markers, write_tmp_rename};

/// Project-root input map (I7). Play snapshots copy content to `input-map.json`.
pub const INPUTMAP_REL: &str = "inputmap.json";

const METHOD_GET: &str = "inputmap.get";
const METHOD_SET: &str = "inputmap.set";
const MAX_ACTION_NAME_LEN: usize = 64;

/// MASTER 6.4 sample — returned when the project file is missing.
pub fn default_inputmap() -> Value {
    json!({
        "actions": [
            {
                "name": "move_x",
                "type": "axis",
                "keys": [["A", -1.0], ["D", 1.0]],
                "gamepad_axis": "left_x"
            },
            {
                "name": "interact",
                "type": "button",
                "keys": ["E"],
                "gamepad_button": "south"
            }
        ]
    })
}

pub(crate) fn is_inputmap_persist_method(method: &str) -> bool {
    method == METHOD_SET
}

pub(crate) fn get_is_readonly() -> Error {
    Error::invalid(
        METHOD_GET,
        "read-only; use Document::read_inputmap or Session::read_inputmap",
    )
}

impl Document {
    pub(crate) fn normalize_inputmap_set(&self, cmd: &Command) -> Result<Command, Error> {
        let actions = cmd
            .params
            .get("actions")
            .ok_or_else(|| Error::invalid(METHOD_SET, "missing actions"))?;
        let validated = validate_actions(actions, METHOD_SET)?;
        let extra = extra_inputmap_fields(&cmd.params);

        if cmd.params.get("previous").is_some() && cmd.params.get("payload").is_some() {
            let previous = cmd.params.get("previous").cloned().unwrap_or(Value::Null);
            validate_previous_value(&previous)?;
            let payload = cmd.params.get("payload").cloned().unwrap_or(Value::Null);
            validate_payload_value(&payload)?;
            return Ok(normalized_set_command(validated, previous, payload, extra));
        }

        let root = self.project_root(METHOD_SET)?;
        let existing = read_existing_inputmap(root, METHOD_SET)?;
        let previous = if let Some(prev) = cmd.params.get("previous") {
            validate_previous_value(prev)?;
            prev.clone()
        } else {
            match &existing {
                Some((text, _)) => Value::String(text.clone()),
                None => Value::Null,
            }
        };
        let payload = if let Some(p) = cmd.params.get("payload") {
            validate_payload_value(p)?;
            p.clone()
        } else {
            build_payload(existing.as_ref().map(|(_, v)| v), &validated, &extra)
        };
        Ok(normalized_set_command(validated, previous, payload, extra))
    }

    pub(crate) fn apply_inputmap_set(&self, cmd: &Command) -> Result<Vec<Command>, Error> {
        let previous = cmd.params.get("previous").cloned().unwrap_or(Value::Null);
        let payload = cmd.params.get("payload").cloned().unwrap_or(Value::Null);
        let inverse_payload = payload_from_previous_text(&previous)?;
        let inverse_actions = actions_from_payload(&inverse_payload);
        let inverse_previous = match &payload {
            Value::Null => Value::Null,
            other => Value::String(to_canonical_string(other)),
        };
        Ok(vec![normalized_set_command(
            inverse_actions,
            inverse_previous,
            inverse_payload,
            Map::new(),
        )])
    }

    /// Write or delete `inputmap.json` after WAL fsync (I2 / I6).
    pub fn persist_inputmap_file(&self, cmd: &Command) -> Result<(), Error> {
        if !is_inputmap_persist_method(&cmd.method) {
            return Err(Error::invalid(&cmd.method, "not an inputmap file command"));
        }
        let root = self.project_root(METHOD_SET)?;
        let abs = resolve_under_root(root, INPUTMAP_REL)?;
        match cmd.params.get("payload") {
            None | Some(Value::Null) => {
                if abs.exists() {
                    fs::remove_file(&abs)?;
                }
            }
            Some(payload) => {
                if !payload.is_object() {
                    return Err(Error::invalid(METHOD_SET, "payload must be an object"));
                }
                write_tmp_rename(&abs, &crate::canonical::to_canonical_vec(payload))?;
            }
        }
        Ok(())
    }

    /// Read-only helper for `inputmap.get` (not a WAL command).
    pub fn read_inputmap(&self) -> Result<Value, Error> {
        let root = self.project_root(METHOD_GET)?;
        match read_existing_inputmap(root, METHOD_GET)? {
            None => Ok(default_inputmap()),
            Some((_, value)) => Ok(value),
        }
    }
}

fn build_payload(existing: Option<&Value>, actions: &Value, extra: &Map<String, Value>) -> Value {
    let mut obj = match existing {
        Some(Value::Object(map)) => map.clone(),
        _ => Map::new(),
    };
    obj.insert("actions".into(), actions.clone());
    for (k, v) in extra {
        obj.insert(k.clone(), v.clone());
    }
    Value::Object(obj)
}

fn payload_from_previous_text(previous: &Value) -> Result<Value, Error> {
    match previous {
        Value::Null => Ok(Value::Null),
        Value::String(text) => {
            let value: Value = serde_json::from_str(text)
                .map_err(|_| Error::invalid(METHOD_SET, "previous is not valid JSON"))?;
            if !value.is_object() {
                return Err(Error::invalid(METHOD_SET, "previous must be a JSON object"));
            }
            Ok(value)
        }
        _ => Err(Error::invalid(
            METHOD_SET,
            "previous must be string or null",
        )),
    }
}

fn actions_from_payload(payload: &Value) -> Value {
    payload
        .get("actions")
        .cloned()
        .unwrap_or_else(|| default_inputmap()["actions"].clone())
}

fn validate_actions(actions: &Value, method: &str) -> Result<Value, Error> {
    let arr = actions
        .as_array()
        .ok_or_else(|| Error::invalid(method, "actions must be an array"))?;
    let mut names = BTreeSet::new();
    let mut out = Vec::with_capacity(arr.len());
    for action in arr {
        out.push(validate_action(action, &mut names, method)?);
    }
    Ok(Value::Array(out))
}

fn validate_action(
    action: &Value,
    names: &mut BTreeSet<String>,
    method: &str,
) -> Result<Value, Error> {
    let obj = action
        .as_object()
        .ok_or_else(|| Error::invalid(method, "action must be an object"))?;
    let name = obj
        .get("name")
        .and_then(Value::as_str)
        .ok_or_else(|| Error::invalid(method, "action name must be a string"))?;
    validate_action_name(name, method)?;
    if !names.insert(name.to_string()) {
        return Err(Error::invalid(
            method,
            format!("duplicate action name {name}"),
        ));
    }
    let type_name = obj
        .get("type")
        .and_then(Value::as_str)
        .ok_or_else(|| Error::invalid(method, "action type must be a string"))?;
    let keys = obj
        .get("keys")
        .ok_or_else(|| Error::invalid(method, "action missing keys"))?;
    match type_name {
        "axis" => validate_axis_keys(keys, method)?,
        "button" => validate_button_keys(keys, method)?,
        other => {
            return Err(Error::invalid(
                method,
                format!("action type must be axis or button, got {other}"),
            ));
        }
    }
    if let Some(axis) = obj.get("gamepad_axis") {
        if !axis.is_string() {
            return Err(Error::invalid(method, "gamepad_axis must be a string"));
        }
    }
    if let Some(button) = obj.get("gamepad_button") {
        if !button.is_string() {
            return Err(Error::invalid(method, "gamepad_button must be a string"));
        }
    }
    Ok(action.clone())
}

fn validate_action_name(name: &str, method: &str) -> Result<(), Error> {
    if name.is_empty() {
        return Err(Error::invalid(method, "action name must be non-empty"));
    }
    if name.len() > MAX_ACTION_NAME_LEN {
        return Err(Error::invalid(
            method,
            format!("action name longer than {MAX_ACTION_NAME_LEN}"),
        ));
    }
    if !name
        .bytes()
        .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'_')
    {
        return Err(Error::invalid(method, "action name must match [a-z0-9_]"));
    }
    Ok(())
}

fn validate_axis_keys(keys: &Value, method: &str) -> Result<(), Error> {
    let arr = keys
        .as_array()
        .ok_or_else(|| Error::invalid(method, "axis keys must be an array"))?;
    for entry in arr {
        let pair = entry
            .as_array()
            .ok_or_else(|| Error::invalid(method, "axis key must be [key, scale]"))?;
        if pair.len() != 2 {
            return Err(Error::invalid(method, "axis key must be [key, scale]"));
        }
        let key = pair[0]
            .as_str()
            .ok_or_else(|| Error::invalid(method, "axis key name must be a string"))?;
        if key.is_empty() {
            return Err(Error::invalid(method, "axis key name must be non-empty"));
        }
        let scale = pair[1]
            .as_f64()
            .ok_or_else(|| Error::invalid(method, "axis scale must be a number"))?;
        if !(-1.0..=1.0).contains(&scale) {
            return Err(Error::invalid(method, "axis scale must be in [-1, 1]"));
        }
    }
    Ok(())
}

fn validate_button_keys(keys: &Value, method: &str) -> Result<(), Error> {
    let arr = keys
        .as_array()
        .ok_or_else(|| Error::invalid(method, "button keys must be an array"))?;
    for entry in arr {
        let key = entry
            .as_str()
            .ok_or_else(|| Error::invalid(method, "button key must be a string"))?;
        if key.is_empty() {
            return Err(Error::invalid(method, "button key must be non-empty"));
        }
    }
    Ok(())
}

fn validate_inputmap_value(value: &Value, method: &str) -> Result<(), Error> {
    let obj = value
        .as_object()
        .ok_or_else(|| Error::invalid(method, "input map must be a JSON object"))?;
    let actions = obj
        .get("actions")
        .ok_or_else(|| Error::invalid(method, "input map missing actions"))?;
    validate_actions(actions, method)?;
    Ok(())
}

fn read_existing_inputmap(root: &Path, method: &str) -> Result<Option<(String, Value)>, Error> {
    let abs = resolve_under_root(root, INPUTMAP_REL)?;
    if !abs.exists() {
        return Ok(None);
    }
    let bytes = fs::read(&abs)?;
    let text = String::from_utf8(bytes)
        .map_err(|_| Error::invalid(method, "input map is not valid UTF-8"))?;
    reject_conflict_markers(&text, &abs)?;
    let value: Value = serde_json::from_str(&text)
        .map_err(|_| Error::invalid(method, "input map is not valid JSON"))?;
    validate_inputmap_value(&value, method)?;
    Ok(Some((text, value)))
}

fn validate_previous_value(value: &Value) -> Result<(), Error> {
    match value {
        Value::Null | Value::String(_) => Ok(()),
        _ => Err(Error::invalid(
            METHOD_SET,
            "previous must be string or null",
        )),
    }
}

fn validate_payload_value(value: &Value) -> Result<(), Error> {
    match value {
        Value::Null => Ok(()),
        Value::Object(_) => Ok(()),
        _ => Err(Error::invalid(METHOD_SET, "payload must be object or null")),
    }
}

fn extra_inputmap_fields(params: &Value) -> Map<String, Value> {
    let mut extra = Map::new();
    if let Some(obj) = params.as_object() {
        for (k, v) in obj {
            if matches!(k.as_str(), "actions" | "previous" | "payload") {
                continue;
            }
            extra.insert(k.clone(), v.clone());
        }
    }
    extra
}

fn normalized_set_command(
    actions: Value,
    previous: Value,
    payload: Value,
    extra: Map<String, Value>,
) -> Command {
    let mut params = Map::new();
    params.insert("actions".into(), actions);
    params.insert("previous".into(), previous);
    params.insert("payload".into(), payload);
    for (k, v) in extra {
        params.insert(k, v);
    }
    Command::new(METHOD_SET, Value::Object(params))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn apply_without_persist_does_not_write() {
        let doc = Document {
            project_root: Some(PathBuf::from("unused-root-for-unit")),
            ..Document::default()
        };
        let cmd = Command::new(
            METHOD_SET,
            json!({
                "actions": default_inputmap()["actions"],
                "previous": Value::Null,
                "payload": default_inputmap(),
            }),
        );
        let inverses = doc.apply_inputmap_set(&cmd).expect("apply");
        assert_eq!(inverses.len(), 1);
        assert_eq!(inverses[0].method, METHOD_SET);
        assert_eq!(inverses[0].params["payload"], Value::Null);
    }
}

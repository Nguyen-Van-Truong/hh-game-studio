//! `command_id` ULID helper (MASTER 10.1 / I11).

use serde_json::{json, Value};
use ulid::Ulid;

/// Methods that do **not** take a mutating/job `command_id`.
fn is_readonly_or_session(method: &str) -> bool {
    matches!(
        method,
        "session.hello"
            | "session.ping"
            | "session.goodbye"
            | "session.subscribe"
            | "session.list"
            | "project.info"
            | "project.open"
            | "scene.list"
            | "scene.dump"
            | "scene.stats"
            | "entity.find"
            | "component.get"
            | "component.registry"
            | "undo.history"
            | "capability.list"
            | "play.status"
            | "obs.screenshot"
            | "obs.world_dump"
            | "obs.query"
            | "obs.logs_tail"
            | "obs.perf"
            | "obs.events"
            | "asset.list"
            | "asset.meta_get"
            | "asset.job_status"
            | "artifact.list"
            | "artifact.get"
            | "inputmap.get"
            | "script.get_source"
            | "script.diagnostics"
            | "script.conflicts"
            | "judge.assert_world"
            | "judge.assert_perf"
            | "judge.assert_screenshot"
            | "build.status"
    )
}

/// True for mutating / Job methods that must carry a client-generated ULID.
pub fn needs_command_id(method: &str) -> bool {
    !is_readonly_or_session(method)
}

/// If `params` is an object for a mutating/job method and `command_id` is
/// missing, insert a new ULID. Returns the (possibly updated) params and the
/// command_id that should be printed (existing or generated).
pub fn ensure_command_id(method: &str, mut params: Value) -> (Value, Option<String>) {
    if !needs_command_id(method) {
        if let Some(existing) = existing_command_id(&params) {
            return (params, Some(existing));
        }
        return (params, None);
    }

    if !params.is_object() {
        if params.is_null() {
            params = json!({});
        } else {
            return (params, None);
        }
    }

    if let Some(existing) = existing_command_id(&params) {
        return (params, Some(existing));
    }

    let command_id = Ulid::new().to_string();
    if let Some(map) = params.as_object_mut() {
        map.insert("command_id".into(), Value::String(command_id.clone()));
    }
    (params, Some(command_id))
}

fn existing_command_id(params: &Value) -> Option<String> {
    params
        .get("command_id")
        .and_then(Value::as_str)
        .filter(|s| !s.is_empty())
        .map(ToOwned::to_owned)
}

/// Parse a JSONL file of `{method, params}` commands for `transaction.execute`.
pub fn commands_from_jsonl(text: &str) -> Result<Vec<Value>, crate::Error> {
    let text = text.strip_prefix('\u{feff}').unwrap_or(text);
    let mut commands = Vec::new();
    for (idx, line) in text.lines().enumerate() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let value: Value = serde_json::from_str(line)
            .map_err(|err| crate::Error::json(format!("jsonl line {}: {err}", idx + 1)))?;
        let obj = value.as_object().ok_or_else(|| {
            crate::Error::json(format!(
                "jsonl line {}: command must be a JSON object",
                idx + 1
            ))
        })?;
        if !obj.contains_key("method") {
            return Err(crate::Error::json(format!(
                "jsonl line {}: missing method",
                idx + 1
            )));
        }
        commands.push(value);
    }
    if commands.is_empty() {
        return Err(crate::Error::Args("jsonl file contains no commands".into()));
    }
    if commands.len() > 200 {
        return Err(crate::Error::Args(
            "transaction.execute allows at most 200 commands".into(),
        ));
    }
    Ok(commands)
}

/// Build `transaction.execute` params and a fresh outer `command_id`.
pub fn transaction_params(commands: Vec<Value>, label: Option<&str>) -> (Value, String) {
    let command_id = Ulid::new().to_string();
    let params = json!({
        "label": label.unwrap_or("gstxn"),
        "commands": commands,
        "command_id": command_id,
    });
    (params, command_id)
}

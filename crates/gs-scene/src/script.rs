//! Script file commands (MASTER 4.2 / 7.4 / 8.4). Disk writes happen after WAL.

use std::fs;
use std::path::Path;

use serde_json::{json, Map, Value};

use crate::blueprint::resolve_under_root;
use crate::command::Command;
use crate::document::Document;
use crate::error::Error;
use crate::persist::write_tmp_rename;

/// MASTER 4.2: `script.set_source` source cap.
pub const MAX_SCRIPT_SOURCE_BYTES: usize = 256 * 1024;

/// Default `script.create` body when `template` is omitted.
pub const DEFAULT_SCRIPT_SOURCE: &str =
    "--!strict\nlocal M = {}\nfunction M.on_update(self, dt)\nend\nreturn M\n";

/// Inline door skeleton (MASTER 7.5). Not loaded from `templates/` (I9/I10).
pub const DOOR_SCRIPT_SOURCE: &str = r#"--!strict
local M = {}

function M.on_init(self)
  -- self.props từ Script component (5.4): locked, key_tag, open_sprite
  if self.state.locked == nil then
    self.state.locked = self.props.locked
  end
end

function M.on_event(self, name, data)
  if name ~= "collision_enter" then return end
  if not self.state.locked then return end
  -- key_pickup.luau đã gs.add_tag(player, self.props.key_tag)
  if gs.has_tag(data.other, "player")
     and gs.has_tag(data.other, self.props.key_tag) then
    self.state.locked = false
    gs.set_sprite(self.id, self.props.open_sprite)
    gs.set_component(self.id, "Collider2D", { is_sensor = true })
    gs.emit("DoorOpened", { door = self.id, by = data.other })
  end
end

return M
"#;

pub(crate) fn is_script_persist_method(method: &str) -> bool {
    matches!(
        method,
        "script.create" | "script.set_source" | "script.ingest_external"
    )
}

pub(crate) fn get_source_is_readonly() -> Error {
    Error::invalid(
        "script.get_source",
        "read-only; use Document::read_script_source or Session::read_script_source",
    )
}

impl Document {
    pub(crate) fn normalize_script_create(&self, cmd: &Command) -> Result<Command, Error> {
        const METHOD: &str = "script.create";
        let path = string_field(&cmd.params, "path", METHOD)?;
        validate_script_rel(&path, METHOD)?;
        let root = self.project_root(METHOD)?;
        let abs = resolve_under_root(root, &path)?;

        if cmd.params.get("source").is_some() && cmd.params.get("previous").is_some() {
            let source = source_or_null(&cmd.params, METHOD)?;
            if let Some(ref text) = source {
                check_source_len(text, METHOD)?;
            }
            return Ok(normalized_file_command(
                METHOD,
                &path,
                source,
                cmd.params.get("previous").cloned().unwrap_or(Value::Null),
                extra_script_fields(&cmd.params),
            ));
        }

        if abs.exists() {
            return Err(Error::invalid(METHOD, "file already exists"));
        }
        let template = optional_string(&cmd.params, "template", METHOD)?;
        let source = resolve_template(template.as_deref())?;
        check_source_len(&source, METHOD)?;
        Ok(normalized_file_command(
            METHOD,
            &path,
            Some(source),
            Value::Null,
            extra_script_fields(&cmd.params),
        ))
    }

    pub(crate) fn normalize_script_set_source(&self, cmd: &Command) -> Result<Command, Error> {
        const METHOD: &str = "script.set_source";
        let path = string_field(&cmd.params, "path", METHOD)?;
        validate_script_rel(&path, METHOD)?;
        let root = self.project_root(METHOD)?;
        resolve_under_root(root, &path)?;
        let source = source_or_null(&cmd.params, METHOD)?;
        if let Some(ref text) = source {
            check_source_len(text, METHOD)?;
        }
        let previous = if let Some(prev) = cmd.params.get("previous") {
            validate_previous_value(prev, METHOD)?;
            prev.clone()
        } else {
            read_existing_source_value(root, &path, METHOD)?
        };
        Ok(normalized_file_command(
            METHOD,
            &path,
            source,
            previous,
            extra_script_fields(&cmd.params),
        ))
    }

    pub(crate) fn normalize_script_ingest_external(&self, cmd: &Command) -> Result<Command, Error> {
        const METHOD: &str = "script.ingest_external";
        let path = string_field(&cmd.params, "path", METHOD)?;
        validate_script_rel(&path, METHOD)?;
        let root = self.project_root(METHOD)?;
        resolve_under_root(root, &path)?;

        if cmd.params.get("source").is_some() && cmd.params.get("previous").is_some() {
            let source = source_or_null(&cmd.params, METHOD)?;
            if let Some(ref text) = source {
                check_source_len(text, METHOD)?;
            }
            validate_previous_value(cmd.params.get("previous").unwrap_or(&Value::Null), METHOD)?;
            return Ok(normalized_file_command(
                METHOD,
                &path,
                source,
                cmd.params.get("previous").cloned().unwrap_or(Value::Null),
                extra_script_fields(&cmd.params),
            ));
        }

        let disk = read_existing_source(root, &path, METHOD)?;
        let previous_source = optional_string(&cmd.params, "previous_source", METHOD)?;
        if let Some(ref prev) = previous_source {
            check_source_len(prev, METHOD)?;
        }
        let provided = optional_string(&cmd.params, "source", METHOD)?;
        if let Some(ref text) = provided {
            check_source_len(text, METHOD)?;
        }

        let new_source = if previous_source.is_some() {
            match disk.clone() {
                Some(text) => text,
                None => provided.ok_or_else(|| Error::NotFound(path.clone()))?,
            }
        } else if let Some(text) = provided {
            text
        } else {
            disk.clone().ok_or_else(|| Error::NotFound(path.clone()))?
        };
        check_source_len(&new_source, METHOD)?;

        let previous = match previous_source {
            Some(prev) => Value::String(prev),
            None => match disk {
                Some(text) => Value::String(text),
                None => Value::Null,
            },
        };
        Ok(normalized_file_command(
            METHOD,
            &path,
            Some(new_source),
            previous,
            extra_script_fields(&cmd.params),
        ))
    }

    pub(crate) fn apply_script_file(&self, cmd: &Command) -> Result<Vec<Command>, Error> {
        let method = cmd.method.as_str();
        let path = string_field(&cmd.params, "path", method)?;
        let previous = cmd.params.get("previous").cloned().unwrap_or(Value::Null);
        let source = cmd.params.get("source").cloned().unwrap_or(Value::Null);
        Ok(vec![Command::new(
            "script.set_source",
            json!({
                "path": path,
                "source": previous,
                "previous": source,
            }),
        )])
    }

    /// Write or delete a script file after WAL fsync (I2 / I6). Called from Dispatcher.
    pub fn persist_script_file(&self, cmd: &Command) -> Result<(), Error> {
        let method = cmd.method.as_str();
        if !is_script_persist_method(method) {
            return Err(Error::invalid(method, "not a script file command"));
        }
        let path = string_field(&cmd.params, "path", method)?;
        validate_script_rel(&path, method)?;
        let root = self.project_root(method)?;
        let abs = resolve_under_root(root, &path)?;
        if let Some(parent) = abs.parent() {
            fs::create_dir_all(parent)?;
        }
        match cmd.params.get("source") {
            None | Some(Value::Null) => {
                if abs.exists() {
                    fs::remove_file(&abs)?;
                }
            }
            Some(Value::String(text)) => {
                check_source_len(text, method)?;
                write_tmp_rename(&abs, text.as_bytes())?;
            }
            Some(_) => return Err(Error::invalid(method, "source must be string or null")),
        }
        Ok(())
    }

    /// Read-only helper for `script.get_source` (not a WAL command).
    pub fn read_script_source(&self, path: &str) -> Result<String, Error> {
        const METHOD: &str = "script.get_source";
        validate_script_rel(path, METHOD)?;
        let root = self.project_root(METHOD)?;
        let abs = resolve_under_root(root, path)?;
        if !abs.exists() {
            return Err(Error::NotFound(path.to_string()));
        }
        let bytes = fs::read(&abs)?;
        if bytes.len() > MAX_SCRIPT_SOURCE_BYTES {
            return Err(Error::invalid(
                METHOD,
                format!("source exceeds {MAX_SCRIPT_SOURCE_BYTES} bytes"),
            ));
        }
        String::from_utf8(bytes).map_err(|_| Error::invalid(METHOD, "source is not valid UTF-8"))
    }

    pub(crate) fn project_root(&self, method: &str) -> Result<&Path, Error> {
        self.project_root
            .as_deref()
            .ok_or_else(|| Error::invalid(method, "session has no project root"))
    }
}

fn resolve_template(template: Option<&str>) -> Result<String, Error> {
    match template {
        None => Ok(DEFAULT_SCRIPT_SOURCE.to_string()),
        Some("door") => Ok(DOOR_SCRIPT_SOURCE.to_string()),
        Some(other) => Err(Error::invalid(
            "script.create",
            format!("unknown template {other}"),
        )),
    }
}

fn validate_script_rel(rel: &str, method: &str) -> Result<(), Error> {
    if rel.contains("..") || rel.contains('\\') || Path::new(rel).is_absolute() {
        return Err(Error::PathEscapesRoot {
            path: rel.to_string(),
        });
    }
    if !rel.starts_with("scripts/") || !rel.ends_with(".luau") {
        return Err(Error::invalid(method, "path must be scripts/<name>.luau"));
    }
    Ok(())
}

fn check_source_len(source: &str, method: &str) -> Result<(), Error> {
    if source.len() > MAX_SCRIPT_SOURCE_BYTES {
        return Err(Error::invalid(
            method,
            format!("source exceeds {MAX_SCRIPT_SOURCE_BYTES} bytes"),
        ));
    }
    Ok(())
}

fn read_existing_source(root: &Path, rel: &str, method: &str) -> Result<Option<String>, Error> {
    let abs = resolve_under_root(root, rel)?;
    if !abs.exists() {
        return Ok(None);
    }
    let bytes = fs::read(&abs)?;
    if bytes.len() > MAX_SCRIPT_SOURCE_BYTES {
        return Err(Error::invalid(
            method,
            format!("source exceeds {MAX_SCRIPT_SOURCE_BYTES} bytes"),
        ));
    }
    let text = String::from_utf8(bytes)
        .map_err(|_| Error::invalid(method, "source is not valid UTF-8"))?;
    Ok(Some(text))
}

fn read_existing_source_value(root: &Path, rel: &str, method: &str) -> Result<Value, Error> {
    match read_existing_source(root, rel, method)? {
        Some(text) => Ok(Value::String(text)),
        None => Ok(Value::Null),
    }
}

fn validate_previous_value(value: &Value, method: &str) -> Result<(), Error> {
    match value {
        Value::Null => Ok(()),
        Value::String(text) => check_source_len(text, method),
        _ => Err(Error::invalid(method, "previous must be string or null")),
    }
}

fn source_or_null(params: &Value, method: &str) -> Result<Option<String>, Error> {
    match params.get("source") {
        None => Err(Error::invalid(method, "missing source")),
        Some(Value::Null) => Ok(None),
        Some(Value::String(s)) => Ok(Some(s.clone())),
        Some(_) => Err(Error::invalid(method, "source must be string or null")),
    }
}

fn extra_script_fields(params: &Value) -> Map<String, Value> {
    let mut extra = Map::new();
    if let Some(obj) = params.as_object() {
        for (k, v) in obj {
            if matches!(k.as_str(), "path" | "source" | "previous") {
                continue;
            }
            extra.insert(k.clone(), v.clone());
        }
    }
    extra
}

fn normalized_file_command(
    method: &str,
    path: &str,
    source: Option<String>,
    previous: Value,
    extra: Map<String, Value>,
) -> Command {
    let mut params = Map::new();
    params.insert("path".into(), json!(path));
    params.insert(
        "source".into(),
        source.map(Value::String).unwrap_or(Value::Null),
    );
    params.insert("previous".into(), previous);
    for (k, v) in extra {
        params.insert(k, v);
    }
    Command::new(method, Value::Object(params))
}

fn string_field(params: &Value, key: &str, method: &str) -> Result<String, Error> {
    let Some(v) = params.get(key) else {
        return Err(Error::invalid(method, format!("missing {key}")));
    };
    v.as_str()
        .map(str::to_string)
        .ok_or_else(|| Error::invalid(method, format!("{key} must be string")))
}

fn optional_string(params: &Value, key: &str, method: &str) -> Result<Option<String>, Error> {
    match params.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(v) => v
            .as_str()
            .map(|s| Some(s.to_string()))
            .ok_or_else(|| Error::invalid(method, format!("{key} must be string"))),
    }
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
            "script.set_source",
            json!({
                "path": "scripts/unit.luau",
                "source": "print(1)\n",
                "previous": Value::Null,
            }),
        );
        let inverses = doc.apply_script_file(&cmd).expect("apply");
        assert_eq!(inverses.len(), 1);
        assert_eq!(inverses[0].method, "script.set_source");
        assert_eq!(inverses[0].params["source"], Value::Null);
    }
}

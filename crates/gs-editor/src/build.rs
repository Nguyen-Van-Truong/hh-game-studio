//! Editor-layer `build.game` / `status` / `cancel` (T7A.1 / MASTER 4.2).
//!
//! Pack is synchronous. `command_id` is required; the same id returns the same
//! `build_id`. After a successful pack, a pointer is written under the project
//! at `.gs/runtime/build/<build_id>.json` plus a `commands.json` index
//! (I6 tmp+rename, I7). That is enough for restart dedup and
//! `artifact.list(kind=build)`. It is **not** WAL-backed command+inverse — I11
//! is not complete for `build.game`.
//!
//! `build.cancel` requires `command_id` (MASTER 4.3). Pack is sync, so cancel of
//! a finished job stays `already_finished` — no WAL, field presence is enough.
//!
//! `out_dir` (the packed game) must sit outside the project (I7). Never persist
//! the bus token (I8).

use std::collections::{BTreeMap, HashMap};
use std::fs::{self, File};
use std::io::Write;
use std::path::{Path, PathBuf};

use gs_player::{pack_project_with, PackOptions};
use gs_protocol::RpcError;
use gs_scene::to_canonical_vec;
use serde_json::{json, Value};
use ulid::Ulid;

use crate::editor::{string_field, take_command_id, CallContext, Editor};
use crate::error::{app_err, scene_err};

const COMMANDS_FILE: &str = "commands.json";

#[derive(Clone, Debug)]
pub(crate) struct BuildRecord {
    pub build_id: String,
    pub state: String,
    pub path: PathBuf,
}

pub(crate) fn is_build_method(method: &str) -> bool {
    matches!(method, "build.game" | "build.status" | "build.cancel")
}

pub(crate) fn build_is_mutating(method: &str) -> bool {
    matches!(method, "build.game" | "build.cancel")
}

impl Editor {
    pub(crate) fn build_game(
        &mut self,
        ctx: CallContext<'_>,
        mut params: Value,
    ) -> Result<Value, RpcError> {
        let command_id = take_command_id(&mut params)?;
        if let Some(existing) = self.build_by_command.get(&command_id).cloned() {
            if let Some(record) = self.builds.get(&existing) {
                return Ok(build_result(record));
            }
        }

        let out_dir = PathBuf::from(string_field(&params, "out_dir")?);
        let include_debug = params
            .get("include_debug")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let root = self
            .project_path
            .clone()
            .ok_or_else(|| app_err("E_NOT_FOUND", "no project open"))?;

        if let Some(session) = self.session.as_mut() {
            session.save().map_err(scene_err)?;
        } else {
            return Err(app_err("E_NOT_FOUND", "no project open"));
        }

        let build_id = format!("b_{}", Ulid::new());
        let packed = pack_project_with(
            &root,
            &out_dir,
            PackOptions {
                include_debug,
                actor: ctx.actor_id.to_owned(),
                build_id: Some(build_id.clone()),
            },
        )
        .map_err(pack_err)?;

        let record = BuildRecord {
            build_id: packed.build_id.clone(),
            state: "done".into(),
            path: packed.out_dir,
        };
        let mut next_index = self.build_by_command.clone();
        next_index.insert(command_id.clone(), record.build_id.clone());
        persist_successful_build(&root, &command_id, &record, &next_index)?;
        let result = build_result(&record);
        self.build_by_command = next_index;
        self.builds.insert(record.build_id.clone(), record);
        if let Some(actor) = self.actors.get_mut(ctx.actor_id) {
            actor.command_count = actor.command_count.saturating_add(1);
        }
        Ok(result)
    }

    /// Load pointer files + `commands.json` into memory (editor start / project.open).
    pub(crate) fn load_build_persist(&mut self, root: &Path) {
        self.builds.clear();
        self.build_by_command.clear();
        let dir = build_persist_dir(root);
        if let Ok(entries) = fs::read_dir(&dir) {
            for entry in entries.filter_map(Result::ok) {
                let path = entry.path();
                if !is_build_pointer_file(&path) {
                    continue;
                }
                if let Some((command_id, record)) = read_pointer(&path) {
                    self.build_by_command
                        .insert(command_id, record.build_id.clone());
                    self.builds.insert(record.build_id.clone(), record);
                }
            }
        }
        if let Some(index) = read_command_index(&dir.join(COMMANDS_FILE)) {
            for (command_id, build_id) in index {
                if self.builds.contains_key(&build_id) {
                    self.build_by_command.insert(command_id, build_id);
                }
            }
        }
    }

    pub(crate) fn build_status(&self, params: &Value) -> Result<Value, RpcError> {
        let build_id = string_field(params, "build_id")?;
        let record = self
            .builds
            .get(&build_id)
            .ok_or_else(|| app_err("E_NOT_FOUND", format!("unknown build_id {build_id}")))?;
        Ok(json!({
            "state": record.state,
            "path": record.path.to_string_lossy(),
            "build_id": record.build_id,
        }))
    }

    pub(crate) fn build_cancel(&self, mut params: Value) -> Result<Value, RpcError> {
        take_command_id(&mut params)?;
        let build_id = string_field(&params, "build_id")?;
        let Some(record) = self.builds.get(&build_id) else {
            return Err(app_err(
                "E_NOT_FOUND",
                format!("unknown build_id {build_id}"),
            ));
        };
        Ok(json!({
            "state": record.state,
            "already_finished": true,
            "build_id": record.build_id,
            "path": record.path.to_string_lossy(),
        }))
    }
}

fn build_result(record: &BuildRecord) -> Value {
    json!({
        "build_id": record.build_id,
        "state": record.state,
        "path": record.path.to_string_lossy(),
    })
}

fn pack_err(err: gs_player::Error) -> RpcError {
    app_err(err.app_code(), err.to_string())
}

fn build_persist_dir(root: &Path) -> PathBuf {
    root.join(".gs").join("runtime").join("build")
}

fn is_build_pointer_file(path: &Path) -> bool {
    if !path.is_file() {
        return false;
    }
    let name = path
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or_default();
    name.ends_with(".json")
        && name != COMMANDS_FILE
        && !name.starts_with('.')
        && !name.ends_with(".tmp")
}

fn persist_successful_build(
    root: &Path,
    command_id: &str,
    record: &BuildRecord,
    index: &HashMap<String, String>,
) -> Result<(), RpcError> {
    let dir = build_persist_dir(root);
    fs::create_dir_all(&dir).map_err(|err| app_err("E_IO", err.to_string()))?;
    let pointer = json!({
        "command_id": command_id,
        "build_id": record.build_id,
        "path": record.path.to_string_lossy(),
        "state": record.state,
    });
    write_tmp_rename(
        &dir.join(format!("{}.json", record.build_id)),
        &to_canonical_vec(&pointer),
    )?;
    let ordered: BTreeMap<&str, &str> = index
        .iter()
        .map(|(k, v)| (k.as_str(), v.as_str()))
        .collect();
    let index_json =
        serde_json::to_value(ordered).map_err(|err| app_err("E_IO", err.to_string()))?;
    write_tmp_rename(&dir.join(COMMANDS_FILE), &to_canonical_vec(&index_json))?;
    Ok(())
}

fn read_pointer(path: &Path) -> Option<(String, BuildRecord)> {
    let text = fs::read_to_string(path).ok()?;
    let value: Value = serde_json::from_str(&text).ok()?;
    let command_id = value.get("command_id")?.as_str()?.to_owned();
    let build_id = value.get("build_id")?.as_str()?.to_owned();
    let state = value.get("state")?.as_str()?.to_owned();
    let out_path = PathBuf::from(value.get("path")?.as_str()?);
    if command_id.is_empty() || build_id.is_empty() {
        return None;
    }
    Some((
        command_id,
        BuildRecord {
            build_id,
            state,
            path: out_path,
        },
    ))
}

fn read_command_index(path: &Path) -> Option<BTreeMap<String, String>> {
    let text = fs::read_to_string(path).ok()?;
    serde_json::from_str(&text).ok()
}

fn write_tmp_rename(path: &Path, bytes: &[u8]) -> Result<(), RpcError> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|err| app_err("E_IO", err.to_string()))?;
    }
    let mut tmp = path.as_os_str().to_owned();
    tmp.push(".tmp");
    let tmp = PathBuf::from(tmp);
    {
        let mut file = File::create(&tmp).map_err(|err| app_err("E_IO", err.to_string()))?;
        file.write_all(bytes)
            .map_err(|err| app_err("E_IO", err.to_string()))?;
        file.flush()
            .map_err(|err| app_err("E_IO", err.to_string()))?;
    }
    if path.exists() {
        fs::remove_file(path).map_err(|err| app_err("E_IO", err.to_string()))?;
    }
    fs::rename(&tmp, path).map_err(|err| {
        let _ = fs::remove_file(&tmp);
        app_err("E_IO", err.to_string())
    })
}

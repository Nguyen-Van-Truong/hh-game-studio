//! `artifact.list` / `get` / `gc` under `.gs/runtime/` (MASTER 4.2 / I7 / I8).
//!
//! `artifact.gc` requires `command_id` (MASTER 4.3). No WAL — field presence is
//! enough. `artifact_id` is the project-relative path (forward slashes). `get`
//! returns `{"path": "<absolute file>"}` only — never a blob.

use std::fs;
use std::path::{Path, PathBuf};
use std::time::SystemTime;

use gs_protocol::RpcError;
use serde_json::{json, Value};

use crate::editor::{take_command_id, Editor};
use crate::error::{app_err, invalid_params};
use crate::gtest::{rel_from_root, resolve_project_rel};

const RUNTIME_PREFIX: &str = ".gs/runtime/";
const KINDS: &[&str] = &["screenshot", "dump", "tape", "evidence", "build"];

pub(crate) fn is_artifact_method(method: &str) -> bool {
    matches!(method, "artifact.list" | "artifact.get" | "artifact.gc")
}

impl Editor {
    pub(crate) fn artifact_list(&self, params: &Value) -> Result<Value, RpcError> {
        let root = self.project_root()?;
        let kind = params
            .get("kind")
            .and_then(Value::as_str)
            .ok_or_else(|| invalid_params("kind is required"))?;
        if !KINDS.contains(&kind) {
            return Err(invalid_params(format!(
                "kind must be one of {}",
                KINDS.join("|")
            )));
        }
        let mut artifacts = list_kind(&root, kind);
        artifacts.sort_by(|a, b| a["artifact_id"].as_str().cmp(&b["artifact_id"].as_str()));
        Ok(json!({ "artifacts": artifacts, "kind": kind }))
    }

    pub(crate) fn artifact_get(&self, params: &Value) -> Result<Value, RpcError> {
        let root = self.project_root()?;
        let id = params
            .get("artifact_id")
            .and_then(Value::as_str)
            .ok_or_else(|| invalid_params("artifact_id is required"))?;
        let path = resolve_runtime_file(&root, id)?;
        Ok(json!({ "path": path.to_string_lossy() }))
    }

    pub(crate) fn artifact_gc(&self, mut params: Value) -> Result<Value, RpcError> {
        take_command_id(&mut params)?;
        let root = self.project_root()?;
        let keep_last = params
            .get("keep_last")
            .and_then(Value::as_u64)
            .ok_or_else(|| invalid_params("keep_last must be a u64"))?;
        let keep = usize::try_from(keep_last).unwrap_or(usize::MAX);
        let skip_play = self.play.as_ref().map(|p| p.play_id().to_owned());
        let evidence = gc_dirs(
            &root.join(".gs").join("runtime").join("evidence"),
            keep,
            None,
        );
        let play = gc_dirs(
            &root.join(".gs").join("runtime").join("play"),
            keep,
            skip_play.as_deref(),
        );
        let mut deleted = evidence;
        deleted.extend(play);
        Ok(json!({
            "keep_last": keep_last,
            "deleted": deleted.len(),
            "deleted_paths": deleted,
        }))
    }

    fn project_root(&self) -> Result<PathBuf, RpcError> {
        self.project_path
            .clone()
            .ok_or_else(|| app_err("E_NOT_FOUND", "no project open"))
    }
}

fn list_kind(root: &Path, kind: &str) -> Vec<Value> {
    let runtime = root.join(".gs").join("runtime");
    match kind {
        "evidence" => list_evidence(root, &runtime.join("evidence")),
        "screenshot" => list_files(root, &runtime, &["png"], Some("screenshot")),
        "dump" => list_files(root, &runtime, &["json"], Some("world_dump")),
        "tape" => list_files(root, &runtime, &["jsonl"], Some(".tape")),
        "build" => list_build(root, &runtime.join("build")),
        _ => Vec::new(),
    }
}

fn list_evidence(root: &Path, dir: &Path) -> Vec<Value> {
    let Ok(entries) = fs::read_dir(dir) else {
        return Vec::new();
    };
    let mut out = Vec::new();
    for entry in entries.filter_map(Result::ok) {
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }
        let name = path
            .file_name()
            .map(|s| s.to_string_lossy().into_owned())
            .unwrap_or_default();
        if name.starts_with('.') {
            continue;
        }
        let id = rel_from_root(root, &path);
        out.push(json!({
            "artifact_id": id,
            "kind": "evidence",
        }));
    }
    out
}

fn list_build(root: &Path, dir: &Path) -> Vec<Value> {
    let Ok(entries) = fs::read_dir(dir) else {
        return Vec::new();
    };
    entries
        .filter_map(Result::ok)
        .map(|e| e.path())
        .filter(|p| is_build_artifact(p))
        .map(|path| {
            json!({
                "artifact_id": rel_from_root(root, &path),
                "kind": "build",
            })
        })
        .collect()
}

fn is_build_artifact(path: &Path) -> bool {
    if !path.is_file() {
        return false;
    }
    let name = path
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or_default();
    name.ends_with(".json")
        && name != "commands.json"
        && !name.starts_with('.')
        && !name.ends_with(".tmp")
}

fn list_files(root: &Path, start: &Path, exts: &[&str], name_has: Option<&str>) -> Vec<Value> {
    let mut out = Vec::new();
    walk_files(start, &mut |path| {
        let name = path
            .file_name()
            .map(|s| s.to_string_lossy().into_owned())
            .unwrap_or_default();
        let ok_ext = path
            .extension()
            .and_then(|e| e.to_str())
            .is_some_and(|e| exts.iter().any(|want| e.eq_ignore_ascii_case(want)));
        let ok_name = name_has.is_none_or(|n| name.contains(n));
        if ok_ext && ok_name {
            out.push(json!({
                "artifact_id": rel_from_root(root, path),
                "kind": kind_from_name(&name),
            }));
        }
    });
    out
}

fn kind_from_name(name: &str) -> &'static str {
    if name.contains("screenshot") && name.ends_with(".png") {
        "screenshot"
    } else if name.contains("world_dump") {
        "dump"
    } else if name.contains(".tape") {
        "tape"
    } else {
        "dump"
    }
}

fn walk_files(dir: &Path, visit: &mut impl FnMut(&Path)) {
    let Ok(entries) = fs::read_dir(dir) else {
        return;
    };
    for entry in entries.filter_map(Result::ok) {
        let path = entry.path();
        if path.is_dir() {
            let name = path
                .file_name()
                .map(|s| s.to_string_lossy().into_owned())
                .unwrap_or_default();
            if name.starts_with('.') {
                continue;
            }
            walk_files(&path, visit);
        } else if path.is_file() {
            visit(&path);
        }
    }
}

fn resolve_runtime_file(root: &Path, artifact_id: &str) -> Result<PathBuf, RpcError> {
    let id = artifact_id.replace('\\', "/");
    if !id.starts_with(RUNTIME_PREFIX) {
        return Err(app_err(
            "E_PATH",
            format!("artifact_id {artifact_id} is not under .gs/runtime"),
        ));
    }
    let path = resolve_project_rel(root, &id, true)?;
    if path.is_dir() {
        let result = path.join("result.json");
        if result.is_file() {
            return Ok(result);
        }
        return Err(app_err(
            "E_NOT_FOUND",
            format!("artifact {artifact_id} is a directory without result.json"),
        ));
    }
    if path.is_file() {
        return Ok(path);
    }
    Err(app_err("E_NOT_FOUND", format!("not found: {artifact_id}")))
}

fn gc_dirs(dir: &Path, keep_last: usize, skip_name: Option<&str>) -> Vec<String> {
    let Ok(entries) = fs::read_dir(dir) else {
        return Vec::new();
    };
    let mut dirs: Vec<(SystemTime, PathBuf, String)> = entries
        .filter_map(Result::ok)
        .filter(|e| e.path().is_dir())
        .map(|e| {
            let path = e.path();
            let name = path
                .file_name()
                .map(|s| s.to_string_lossy().into_owned())
                .unwrap_or_default();
            let time = e
                .metadata()
                .ok()
                .map(|m| {
                    m.created()
                        .or_else(|_| m.modified())
                        .unwrap_or(SystemTime::UNIX_EPOCH)
                })
                .unwrap_or(SystemTime::UNIX_EPOCH);
            (time, path, name)
        })
        .filter(|(_, _, name)| !name.starts_with('.'))
        .collect();
    dirs.sort_by(|a, b| a.0.cmp(&b.0).then_with(|| a.2.cmp(&b.2)));
    let mut deleted = Vec::new();
    while dirs.len() > keep_last {
        let Some(idx) = dirs
            .iter()
            .position(|(_, _, name)| skip_name != Some(name.as_str()))
        else {
            break;
        };
        let (_, path, _) = dirs.remove(idx);
        let shown = path.to_string_lossy().replace('\\', "/");
        if fs::remove_dir_all(&path).is_ok() {
            deleted.push(shown);
        }
    }
    deleted
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[test]
    fn get_rejects_outside_runtime() {
        let dir = TempDir::new().expect("temp");
        fs::create_dir_all(dir.path().join("tests")).unwrap();
        fs::write(dir.path().join("tests/x.json"), b"{}").unwrap();
        let err = resolve_runtime_file(dir.path(), "tests/x.json").expect_err("jail");
        assert_eq!(
            err.data.as_ref().map(|d| d.app_code.as_str()),
            Some("E_PATH")
        );
    }

    #[test]
    fn gc_keeps_newest() {
        let dir = TempDir::new().expect("temp");
        let ev = dir.path().join("ev");
        fs::create_dir_all(ev.join("old")).unwrap();
        fs::write(ev.join("old/result.json"), b"{}").unwrap();
        std::thread::sleep(std::time::Duration::from_millis(20));
        fs::create_dir_all(ev.join("new")).unwrap();
        fs::write(ev.join("new/result.json"), b"{}").unwrap();
        let deleted = gc_dirs(&ev, 1, None);
        assert_eq!(deleted.len(), 1);
        assert!(ev.join("new").is_dir());
        assert!(!ev.join("old").exists());
    }
}

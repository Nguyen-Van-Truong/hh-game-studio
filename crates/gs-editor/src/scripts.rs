//! Editor-layer script buffers, poll watcher, and conflict (MASTER 8.4).
//!
//! Disk mutations go through the session dispatcher only (I1). The editor
//! never loads Luau (I3). Watcher ingest uses actor `system:file-watch`
//! (Session.dispatch does not require a registered actor; feed badge is System).

use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::SystemTime;

use gs_protocol::{Notification, RpcError};
use gs_scene::MAX_SCRIPT_SOURCE_BYTES;
use serde_json::{json, Value};
use ulid::Ulid;

use crate::analyze::{
    diagnostic_json, off_diagnostic, relativize_file, report_json, resolve_analyze_binary,
    run_luau_analyze, write_gs_defs, AnalyzeReport, TypeCheck, ANALYZE_TIMEOUT,
};
use crate::editor::{optional_string, string_field, CallContext, Editor};
use crate::error::{app_err, invalid_params, scene_err};
use crate::types::Principal;

/// Watcher ingest actor (MASTER 8.4 / 9.4). Not a TCP principal.
pub(crate) const FILE_WATCH_ACTOR: &str = "system:file-watch";
pub(crate) const EVENT_SCRIPT: &str = "event.script_changed";

#[derive(Clone, Debug)]
pub(crate) struct ScriptBuffer {
    last_known_source: String,
    dirty: bool,
    buffer_source: String,
    mtime: Option<SystemTime>,
    len: u64,
}

#[derive(Clone, Debug)]
pub(crate) struct ScriptConflict {
    path: String,
    disk_source: String,
    buffer_source: String,
}

struct ScriptFile {
    rel: String,
    snapshot_key: String,
    source: String,
    mtime: Option<SystemTime>,
    len: u64,
}

pub(crate) fn is_wired_script_method(method: &str) -> bool {
    matches!(
        method,
        "script.create" | "script.set_source" | "script.get_source" | "script.ingest_external"
    )
}

pub(crate) fn is_script_editor_layer(method: &str) -> bool {
    matches!(
        method,
        "script.buffer_set" | "script.conflicts" | "script.conflict_resolve" | "script.diagnostics"
    )
}

/// Every `script.*` method this crate implements (WAL + editor-layer).
/// Leftover `script.*` stay unimplemented — do not use a blanket prefix.
pub(crate) fn is_script_method(method: &str) -> bool {
    is_wired_script_method(method) || is_script_editor_layer(method)
}

pub(crate) fn is_script_ui_only(method: &str) -> bool {
    matches!(method, "script.buffer_set" | "script.conflict_resolve")
}

/// Snapshot builder keys are relative under `scripts/` (e.g. `foo.luau`).
pub(crate) fn collect_snapshot_scripts(root: &Path) -> BTreeMap<String, Vec<u8>> {
    scan_project_scripts(root)
        .into_iter()
        .map(|file| (file.snapshot_key, file.source.into_bytes()))
        .collect()
}

fn scan_project_scripts(root: &Path) -> Vec<ScriptFile> {
    let dir = root.join("scripts");
    let Ok(entries) = fs::read_dir(&dir) else {
        return Vec::new();
    };
    let mut out = Vec::new();
    for entry in entries.filter_map(Result::ok) {
        let path = entry.path();
        if !path.is_file() {
            continue;
        }
        let Some(name) = path.file_name().and_then(|s| s.to_str()) else {
            continue;
        };
        if !name.ends_with(".luau") || name.contains("..") {
            continue;
        }
        let Ok(meta) = entry.metadata() else {
            continue;
        };
        let Ok(bytes) = fs::read(&path) else {
            continue;
        };
        if bytes.len() > MAX_SCRIPT_SOURCE_BYTES {
            continue;
        }
        let Ok(source) = String::from_utf8(bytes) else {
            continue;
        };
        out.push(ScriptFile {
            rel: format!("scripts/{name}"),
            snapshot_key: name.to_owned(),
            source,
            mtime: meta.modified().ok(),
            len: meta.len(),
        });
    }
    out
}

fn validate_editor_script_path(path: &str) -> Result<(), RpcError> {
    if path.contains("..") || path.contains('\\') || Path::new(path).is_absolute() {
        return Err(app_err(
            "E_PATH",
            format!("path {path} is not under the project root"),
        ));
    }
    if !path.starts_with("scripts/") || !path.ends_with(".luau") {
        return Err(invalid_params("path must be scripts/<name>.luau"));
    }
    Ok(())
}

fn script_abs(root: &Path, rel: &str) -> PathBuf {
    root.join(rel)
}

impl Editor {
    pub(crate) fn arm_script_watcher(&mut self) {
        self.script_buffers.clear();
        self.script_conflicts.clear();
        let Some(root) = self.project_path.clone() else {
            return;
        };
        for file in scan_project_scripts(&root) {
            self.script_buffers.insert(
                file.rel,
                ScriptBuffer {
                    last_known_source: file.source,
                    dirty: false,
                    buffer_source: String::new(),
                    mtime: file.mtime,
                    len: file.len,
                },
            );
        }
    }

    pub(crate) fn script_mutating(
        &mut self,
        ctx: CallContext<'_>,
        method: &str,
        params: Value,
    ) -> Result<Value, RpcError> {
        let path = string_field(&params, "path")?;
        validate_editor_script_path(&path)?;
        let source_hint = optional_string(&params, "source");
        let mut result = self.dispatch_one(ctx, method, params)?;
        let source = match source_hint {
            Some(text) => text,
            None => self
                .session
                .as_ref()
                .and_then(|session| session.read_script_source(&path).ok())
                .unwrap_or_default(),
        };
        self.note_script_saved(&path, &source);
        if matches!(method, "script.set_source" | "script.ingest_external") {
            self.forward_script_reload_if_playing(&path, &source, None);
        }
        if method == "script.set_source" {
            let report = self.refresh_type_diagnostics(Some(&path));
            if let Value::Object(map) = &mut result {
                map.insert(
                    "diagnostics".into(),
                    json!(report
                        .diagnostics
                        .iter()
                        .map(diagnostic_json)
                        .collect::<Vec<_>>()),
                );
                map.insert("type_check".into(), json!(report.type_check.as_str()));
            }
        }
        Ok(result)
    }

    pub(crate) fn script_diagnostics(&mut self, params: &Value) -> Result<Value, RpcError> {
        if self.session.is_none() {
            return Err(app_err("E_NOT_FOUND", "no project open"));
        }
        let path = optional_string(params, "path");
        if let Some(ref path) = path {
            validate_editor_script_path(path)?;
        }
        let report = self.refresh_type_diagnostics(path.as_deref());
        Ok(report_json(&report, path.as_deref()))
    }

    pub(crate) fn ensure_analyze_resolved(&mut self) {
        if self.analyze_bin.is_some() {
            return;
        }
        let found = resolve_analyze_binary(self.project_path.as_deref(), &self.runtime_root);
        self.type_check = if found.is_some() {
            TypeCheck::Ok
        } else {
            TypeCheck::Off
        };
        self.analyze_bin = Some(found);
    }

    pub(crate) fn type_check_label(&self) -> &'static str {
        self.type_check.as_str()
    }

    fn refresh_type_diagnostics(&mut self, path: Option<&str>) -> AnalyzeReport {
        self.ensure_analyze_resolved();
        let Some(bin) = self.analyze_bin.as_ref().and_then(Option::as_ref).cloned() else {
            self.type_check = TypeCheck::Off;
            return AnalyzeReport {
                type_check: TypeCheck::Off,
                diagnostics: vec![off_diagnostic(path.unwrap_or(""))],
            };
        };
        let Some(root) = self.project_path.clone() else {
            self.type_check = TypeCheck::Off;
            return AnalyzeReport {
                type_check: TypeCheck::Off,
                diagnostics: vec![off_diagnostic(path.unwrap_or(""))],
            };
        };
        let rels: Vec<String> = match path {
            Some(p) => vec![p.to_owned()],
            None => self.script_buffers.keys().cloned().collect(),
        };
        let files: Vec<PathBuf> = rels
            .iter()
            .map(|rel| script_abs(&root, rel))
            .filter(|p| p.is_file())
            .collect();
        let defs = write_gs_defs(&root);
        let mut report = run_luau_analyze(&bin, &files, defs.as_deref(), ANALYZE_TIMEOUT);
        for diag in &mut report.diagnostics {
            diag.file = relativize_file(&root, &diag.file);
        }
        self.type_check = report.type_check;
        report
    }

    pub(crate) fn script_get_source(&mut self, params: &Value) -> Result<Value, RpcError> {
        let path = string_field(params, "path")?;
        validate_editor_script_path(&path)?;
        if let Some(conflict) = self.script_conflicts.get(&path) {
            return Ok(json!({
                "path": path,
                "source": conflict.buffer_source,
                "conflict": true,
                "dirty": true,
            }));
        }
        if let Some(buf) = self.script_buffers.get(&path) {
            if buf.dirty {
                return Ok(json!({
                    "path": path,
                    "source": buf.buffer_source,
                    "conflict": false,
                    "dirty": true,
                }));
            }
        }
        let source = {
            let session = self.session_ref()?;
            session.read_script_source(&path).map_err(scene_err)?
        };
        self.note_script_saved(&path, &source);
        Ok(json!({
            "path": path,
            "source": source,
            "conflict": false,
            "dirty": false,
        }))
    }

    pub(crate) fn script_buffer_set(&mut self, params: &Value) -> Result<Value, RpcError> {
        if self.session.is_none() {
            return Err(app_err("E_NOT_FOUND", "no project open"));
        }
        let path = string_field(params, "path")?;
        validate_editor_script_path(&path)?;
        let source = string_field(params, "source")?;
        if source.len() > MAX_SCRIPT_SOURCE_BYTES {
            return Err(invalid_params(format!(
                "source exceeds {MAX_SCRIPT_SOURCE_BYTES} bytes"
            )));
        }
        let last_known = self
            .script_buffers
            .get(&path)
            .map(|buf| buf.last_known_source.clone())
            .or_else(|| {
                self.session
                    .as_ref()
                    .and_then(|session| session.read_script_source(&path).ok())
            })
            .unwrap_or_default();
        let mtime = self.script_buffers.get(&path).and_then(|buf| buf.mtime);
        let len = self
            .script_buffers
            .get(&path)
            .map(|buf| buf.len)
            .unwrap_or(0);
        self.script_buffers.insert(
            path.clone(),
            ScriptBuffer {
                last_known_source: last_known,
                dirty: true,
                buffer_source: source,
                mtime,
                len,
            },
        );
        Ok(json!({ "ok": true, "path": path, "dirty": true }))
    }

    pub(crate) fn script_list_conflicts(&self) -> Result<Value, RpcError> {
        let conflicts: Vec<Value> = self
            .script_conflicts
            .values()
            .map(|conflict| {
                json!({
                    "path": conflict.path,
                    "disk_source": conflict.disk_source,
                    "buffer_source": conflict.buffer_source,
                })
            })
            .collect();
        Ok(json!({ "conflicts": conflicts }))
    }

    pub(crate) fn script_conflict_resolve(
        &mut self,
        ctx: CallContext<'_>,
        params: &Value,
    ) -> Result<Value, RpcError> {
        let path = string_field(params, "path")?;
        validate_editor_script_path(&path)?;
        let choice = string_field(params, "choice")?;
        match choice.as_str() {
            "keep" => {
                self.script_conflicts.remove(&path);
                Ok(json!({ "ok": true, "path": path, "choice": "keep" }))
            }
            "disk" => {
                let conflict = self.script_conflicts.get(&path).cloned().ok_or_else(|| {
                    app_err("E_NOT_FOUND", format!("no script conflict for {path}"))
                })?;
                if let Some(buf) = self.script_buffers.get_mut(&path) {
                    buf.dirty = false;
                    buf.buffer_source.clear();
                }
                let ingest = json!({
                    "command_id": Ulid::new().to_string(),
                    "path": path,
                    "previous_source": conflict.buffer_source,
                });
                match self.script_mutating(ctx, "script.ingest_external", ingest) {
                    Ok(value) => Ok(value),
                    Err(err) => {
                        if let Some(buf) = self.script_buffers.get_mut(&path) {
                            buf.dirty = true;
                            buf.buffer_source = conflict.buffer_source.clone();
                        }
                        self.script_conflicts.insert(path, conflict);
                        Err(err)
                    }
                }
            }
            _ => Err(invalid_params("choice must be keep or disk")),
        }
    }

    /// Poll `scripts/*.luau` mtimes/bytes. Call from the app tick and tests.
    pub fn poll_script_watcher(&mut self) -> Result<Value, RpcError> {
        let Some(root) = self.project_path.clone() else {
            return Ok(json!({ "ingested": [], "conflicts": [] }));
        };
        let files = scan_project_scripts(&root);
        let mut ingested = Vec::new();
        let mut conflicts = Vec::new();
        for file in files {
            let dirty = self
                .script_buffers
                .get(&file.rel)
                .is_some_and(|buf| buf.dirty);
            let last_known = self
                .script_buffers
                .get(&file.rel)
                .map(|buf| buf.last_known_source.clone());
            if last_known.as_deref() == Some(file.source.as_str()) {
                if let Some(buf) = self.script_buffers.get_mut(&file.rel) {
                    buf.mtime = file.mtime;
                    buf.len = file.len;
                } else {
                    self.note_script_saved(&file.rel, &file.source);
                }
                continue;
            }
            if dirty {
                let buffer_source = self
                    .script_buffers
                    .get(&file.rel)
                    .map(|buf| buf.buffer_source.clone())
                    .unwrap_or_default();
                self.record_script_conflict(file.rel.clone(), file.source, buffer_source);
                conflicts.push(file.rel);
                continue;
            }
            self.ingest_watched(&file.rel, last_known)?;
            ingested.push(file.rel);
        }
        Ok(json!({
            "ingested": ingested,
            "conflicts": conflicts,
        }))
    }

    pub(crate) fn refresh_known_clean_scripts(&mut self) {
        let paths: Vec<String> = self
            .script_buffers
            .iter()
            .filter(|(_, buf)| !buf.dirty)
            .map(|(path, _)| path.clone())
            .collect();
        for path in paths {
            match self
                .session
                .as_ref()
                .and_then(|session| session.read_script_source(&path).ok())
            {
                Some(source) => self.note_script_saved(&path, &source),
                None => {
                    self.script_buffers.remove(&path);
                    self.script_conflicts.remove(&path);
                }
            }
        }
    }

    fn ingest_watched(&mut self, path: &str, previous: Option<String>) -> Result<Value, RpcError> {
        let mut params = json!({
            "command_id": Ulid::new().to_string(),
            "path": path,
        });
        if let Some(prev) = previous {
            params["previous_source"] = json!(prev);
        }
        let ctx = CallContext {
            actor_id: FILE_WATCH_ACTOR,
            principal: Principal::HumanUi,
            skip_confirm: true,
        };
        self.script_mutating(ctx, "script.ingest_external", params)
    }

    fn record_script_conflict(&mut self, path: String, disk_source: String, buffer_source: String) {
        let already = self.script_conflicts.contains_key(&path);
        self.script_conflicts.insert(
            path.clone(),
            ScriptConflict {
                path: path.clone(),
                disk_source,
                buffer_source,
            },
        );
        if already {
            return;
        }
        self.emit(Notification::new(
            EVENT_SCRIPT,
            json!({
                "kind": "conflict",
                "path": path,
                "summary": "giữ của tôi / lấy của đĩa",
            }),
        ));
    }

    fn note_script_saved(&mut self, path: &str, source: &str) {
        let (mtime, len) = self.script_file_meta(path);
        self.script_conflicts.remove(path);
        self.script_buffers.insert(
            path.to_owned(),
            ScriptBuffer {
                last_known_source: source.to_owned(),
                dirty: false,
                buffer_source: String::new(),
                mtime,
                len,
            },
        );
    }

    fn script_file_meta(&self, rel: &str) -> (Option<SystemTime>, u64) {
        let Some(root) = &self.project_path else {
            return (None, 0);
        };
        match fs::metadata(script_abs(root, rel)) {
            Ok(meta) => (meta.modified().ok(), meta.len()),
            Err(_) => (None, 0),
        }
    }
}

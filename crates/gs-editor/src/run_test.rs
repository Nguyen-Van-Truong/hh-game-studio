//! `judge.run_test` orchestration (MASTER 10.3 / T5.3).
//!
//! Failures still write an evidence bundle. The RPC is then `E_ASSERT` with
//! `data.field = "path"` and `data.reason` = the bundle directory (so agents
//! can cite the path). Success is `{path, passed:true, evidence_ok}`.
//!
//! `command_id` is required (MASTER 4.3). Dedup is an in-memory map of the last
//! result (ok or error). I11 WAL-backed command+inverse is still incomplete.

use std::fs;
use std::path::{Path, PathBuf};

use gs_player::{sha256_hex, Manifest, REPLAY_TAPE_FILE};
use gs_protocol::{ErrorData, RpcError, APP, PROTOCOL_VER};
use serde_json::{json, Value};
use ulid::Ulid;

use crate::editor::{take_command_id, CallContext, Editor};
use crate::error::app_err;
use crate::evidence::{write_bundle, EvidenceDraft};
use crate::gtest::{check_world_assert, resolve_project_rel, GAssert, GTest};
use crate::play::PlayStartFlags;

const SETTLE_FRAMES: u32 = 20;
const WALK_FRAMES: u32 = 24;

impl Editor {
    pub(crate) fn judge_run_test(
        &mut self,
        ctx: CallContext<'_>,
        mut params: Value,
    ) -> Result<Value, RpcError> {
        let command_id = take_command_id(&mut params)?;
        if let Some(cached) = self.judge_run_by_command.get(&command_id).cloned() {
            return cached;
        }
        let result = self.judge_run_test_inner(ctx, params);
        self.judge_run_by_command.insert(command_id, result.clone());
        result
    }

    fn judge_run_test_inner(
        &mut self,
        ctx: CallContext<'_>,
        params: Value,
    ) -> Result<Value, RpcError> {
        let _ = self.session_ref()?;
        let root = self
            .project_path
            .clone()
            .ok_or_else(|| app_err("E_NOT_FOUND", "no project open"))?;
        let gtest_rel = params
            .get("gtest_rel")
            .and_then(Value::as_str)
            .ok_or_else(|| crate::error::invalid_params("gtest_rel is required"))?;
        let gtest = GTest::load(&root, gtest_rel)?;

        if self.play.is_some() {
            let _ = self.play_stop(&json!({ "force": true }));
        }

        let mut start = json!({
            "headless": true,
            "seed": gtest.seed,
            "command_id": Ulid::new().to_string(),
        });
        if let Some(tape) = &gtest.tape {
            start["replay_tape"] = json!(tape);
        }
        self.play_start_with(
            ctx,
            start,
            PlayStartFlags {
                rewrite_replay_header: gtest.tape.is_some(),
            },
        )?;

        if gtest.tape.is_none() {
            drive_without_tape(self, gtest.max_frames)?;
        }

        let mut draft = EvidenceDraft::default();
        let mut failed = None;
        let mut event_seq: std::collections::BTreeMap<String, u64> =
            std::collections::BTreeMap::new();
        let mut remaining = gtest.max_frames.max(1);

        for assert in &gtest.asserts {
            if failed.is_some() {
                break;
            }
            match assert {
                GAssert::Event(event) => {
                    let mut call = json!({
                        "name": event.name,
                        "max_frames": remaining,
                    });
                    if let Some(after) = &event.after {
                        if let Some(seq) = event_seq.get(after) {
                            call["after_seq"] = json!(seq);
                        }
                    }
                    match self.judge_run_until_event(&call) {
                        Ok(hit) => {
                            if let Some(seq) = hit.get("seq").and_then(Value::as_u64) {
                                event_seq.insert(event.name.clone(), seq);
                            }
                            if let Some(frame) = hit.get("frame").and_then(Value::as_u64) {
                                remaining = remaining.saturating_sub(frame as u32);
                            }
                        }
                        Err(err) => {
                            failed = Some(assert.label());
                            draft.failed_assert = Some(assert.label());
                            let _ = err;
                        }
                    }
                }
                GAssert::World(world) => match self.fetch_world_dump_json() {
                    Ok(dump) => {
                        if let Err(detail) = check_world_assert(&dump, self.session.as_ref(), world)
                        {
                            failed = Some(format!("{} ({detail})", assert.label()));
                        }
                    }
                    Err(_) => {
                        failed = Some(assert.label());
                    }
                },
                GAssert::Screenshot(shot) => {
                    let mut call = json!({
                        "per_px": shot.per_px,
                        "max_bad_ratio": shot.max_bad_ratio,
                    });
                    if let Some(golden) = &shot.golden {
                        if let Ok(path) = resolve_project_rel(&root, golden, true) {
                            call["golden_rel"] = json!(path.to_string_lossy());
                        }
                    }
                    if let Some(mask) = &shot.mask {
                        if let Ok(path) = resolve_project_rel(&root, mask, true) {
                            call["mask"] = json!(path.to_string_lossy());
                        }
                    }
                    match self.judge_assert_screenshot(&call) {
                        Ok(value) => {
                            draft.screenshot = value;
                            draft.screenshot_png = read_png_from_result(&draft.screenshot);
                        }
                        Err(err) if rpc_app_code(&err) == "no_gpu" => {
                            draft.screenshot = json!({
                                "app_code": "no_gpu",
                                "skipped": "no_gpu",
                            });
                        }
                        Err(_) => {
                            if shot.golden.is_some() {
                                failed = Some(assert.label());
                            } else {
                                draft.screenshot = json!({
                                    "app_code": "no_gpu",
                                    "skipped": "no_gpu",
                                });
                            }
                        }
                    }
                }
                GAssert::Unknown(_) => {}
            }
        }

        if failed.is_none() {
            if let Err(msg) = check_diagnostics(self, gtest.expect_diagnostics_max) {
                failed = Some(msg);
            }
        }

        fill_draft(self, &mut draft);
        let report = self.play_stop(&json!({ "force": false })).ok();
        if let Some(report) = report {
            if let Some(ok) = report.get("evidence_ok").and_then(Value::as_bool) {
                draft.evidence_ok = ok;
            }
        }
        draft.passed = failed.is_none();
        draft.failed_assert = failed.clone();

        let dest = write_bundle(&root, &gtest, &draft)?;
        let path = dest.to_string_lossy().replace('\\', "/");
        if let Some(failed_assert) = failed {
            return Err(RpcError::with_data(
                APP,
                format!("judge.run_test failed: {failed_assert}"),
                ErrorData {
                    app_code: "E_ASSERT".into(),
                    retryable: Some(false),
                    field: Some("path".into()),
                    reason: Some(path),
                },
            ));
        }
        Ok(json!({
            "path": path,
            "passed": true,
            "failed_assert": Value::Null,
            "evidence_ok": draft.evidence_ok,
        }))
    }
}

fn drive_without_tape(editor: &mut Editor, max_frames: u32) -> Result<(), RpcError> {
    let settle = SETTLE_FRAMES.min(max_frames.max(1));
    let _ = editor.play_step_frames(&json!({ "n": settle }));
    let walk = WALK_FRAMES.min(max_frames.max(1));
    let actions: Vec<Value> = (0..walk)
        .map(|frame_offset| {
            json!({
                "action": "move_x",
                "value": 1.0,
                "frame_offset": frame_offset,
            })
        })
        .collect();
    let _ = editor.input_inject(&json!({ "actions": actions }));
    Ok(())
}

fn fill_draft(editor: &mut Editor, draft: &mut EvidenceDraft) {
    draft.doc_hash = editor
        .session
        .as_ref()
        .map(|s| sha256_hex(&s.canonical_scene_bytes()))
        .unwrap_or_default();
    if let Ok(dump) = editor.fetch_world_dump_json() {
        draft.world_dump = dump;
    }
    if let Ok(events) = editor.obs_events(&json!({ "after_seq": 0, "limit": 4096 })) {
        draft.events = events;
    }
    if let Ok(logs) = editor.obs_logs_tail(&json!({ "n": 200 })) {
        draft.logs = logs;
    }
    if let Ok(perf) = editor.obs_perf(&json!({})) {
        draft.perf = perf;
    }
    if let Some(play) = editor.play.as_ref() {
        if let Ok(bytes) = fs::read(play.snapshot_manifest()) {
            if let Ok(manifest) = serde_json::from_slice::<Manifest>(&bytes) {
                draft.hashes = json!(manifest.hashes);
                draft.engine = json!({
                    "engine_build": manifest.engine_ver,
                    "protocol_ver": manifest.protocol_ver,
                    "play_id": manifest.play_id,
                });
            }
        }
        let events_file = play.play_dir().join("events.jsonl");
        if events_file.is_file() {
            if let Ok(text) = fs::read_to_string(&events_file) {
                draft.events = Value::String(text);
            }
        }
        let replay = play.play_dir().join(REPLAY_TAPE_FILE);
        if replay.is_file() {
            draft
                .hashes
                .as_object_mut()
                .map(|m| m.insert("replay_tape".into(), json!(replay.to_string_lossy())));
        }
    }
    if draft.engine.as_object().is_none_or(|o| o.is_empty()) {
        draft.engine = json!({
            "engine_build": env!("CARGO_PKG_VERSION"),
            "protocol_ver": PROTOCOL_VER,
        });
    }
    if draft.screenshot.get("app_code").is_none() && draft.screenshot_png.is_none() {
        match editor.obs_screenshot(&json!({})) {
            Ok(value) => {
                draft.screenshot = value;
                draft.screenshot_png = read_png_from_result(&draft.screenshot);
            }
            Err(err) if rpc_app_code(&err) == "no_gpu" => {
                draft.screenshot = json!({ "app_code": "no_gpu" });
            }
            Err(_) => {
                draft.screenshot = json!({ "app_code": "no_gpu" });
            }
        }
    }
}

fn check_diagnostics(editor: &mut Editor, max: u32) -> Result<(), String> {
    let report = editor
        .script_diagnostics(&json!({}))
        .map_err(|err| err.message)?;
    let errors = report
        .get("diagnostics")
        .and_then(Value::as_array)
        .map(|list| {
            list.iter()
                .filter(|d| d.get("kind").and_then(Value::as_str) == Some("error"))
                .count()
        })
        .unwrap_or(0);
    if errors > max as usize {
        Err(format!(
            "diagnostics {errors} exceeds expect_diagnostics_max {max}"
        ))
    } else {
        Ok(())
    }
}

fn read_png_from_result(value: &Value) -> Option<Vec<u8>> {
    let path = value.get("path").and_then(Value::as_str)?;
    let bytes = fs::read(path).ok()?;
    if bytes.starts_with(&[0x89, 0x50, 0x4E, 0x47]) {
        Some(bytes)
    } else {
        None
    }
}

fn rpc_app_code(err: &RpcError) -> &str {
    err.data.as_ref().map(|d| d.app_code.as_str()).unwrap_or("")
}

/// Copy `src` tape onto `dest` with the live snapshot header (no `--force`).
pub(crate) fn rewrite_tape_header(
    src: &Path,
    dest: &Path,
    manifest: &Manifest,
) -> Result<PathBuf, RpcError> {
    let tape = gs_player::load_tape(src).map_err(|err| app_err("E_VALIDATION", err.to_string()))?;
    let header = gs_player::TapeHeader {
        engine_build: manifest.engine_ver.clone(),
        protocol_ver: manifest.protocol_ver.clone(),
        fixed_dt: 1.0 / 60.0,
        seed: manifest.seed,
        snapshot_hashes: manifest.hashes.clone(),
    };
    if let Some(parent) = dest.parent() {
        fs::create_dir_all(parent).map_err(|err| app_err("E_IO", err.to_string()))?;
    }
    gs_player::write_header(dest, &header).map_err(|err| app_err("E_IO", err.to_string()))?;
    for event in &tape.events {
        gs_player::append_action(dest, event).map_err(|err| app_err("E_IO", err.to_string()))?;
    }
    Ok(dest.to_path_buf())
}

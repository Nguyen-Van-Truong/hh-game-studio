//! Editor-side Play: snapshot + spawn `gs-player` + forward `play.*` (I8).
//!
//! Agents never receive the player token or control port. They call these
//! methods on the editor bus; only this process connects to the player.
//!
//! `play.start` requires `command_id`. The same id returns the last successful
//! JSON without spawning again. That map is in-memory only — I11 WAL is still
//! incomplete.

use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::thread;
use std::time::{Duration, Instant, SystemTime};

use gs_player::{
    build_snapshot, cleanup_stale_player_json, find_player_exe, locate_player_json, pid_is_alive,
    read_player_file, utc_now_rfc3339, ControlClient, PlayStatus, SnapshotRequest,
};
use gs_protocol::{ErrorData, RpcError, APP, PROTOCOL_VER};
use gs_scene::{Command as SceneCommand, Error as SceneError};
use serde_json::{json, Map, Value};
use ulid::Ulid;

use crate::editor::{string_field, string_list, take_command_id, CallContext, Editor};
use crate::error::{app_err, invalid_params, scene_err};
use crate::gtest::resolve_project_rel;
use crate::run_test::rewrite_tape_header;
use crate::types::FeedEntry;

/// Extra flags for [`Editor::play_start_with`]. `rewrite_replay_header` is for
/// `judge.run_test` only — `play.start` over the bus never rewrites (GS-EC-36).
#[derive(Clone, Copy, Debug, Default)]
pub(crate) struct PlayStartFlags {
    pub rewrite_replay_header: bool,
}

const HUNG_AFTER: Duration = Duration::from_secs(5);
const START_WAIT: Duration = Duration::from_secs(15);
const EVENT_PLAY: &str = "event.play_changed";
const PLAY_SNAPSHOT_KEEP: usize = 10;
const LIVE_VIEW_MIN_INTERVAL: Duration = Duration::from_millis(100);

pub(crate) struct PlayBridge {
    play_id: String,
    pid: u32,
    token: String,
    child: Option<Child>,
    client: Option<ControlClient>,
    snapshot_manifest: PathBuf,
    player_json_path: PathBuf,
    play_dir: PathBuf,
    last_ok_status: Option<Instant>,
    last_status: Option<PlayStatus>,
    last_exit_report: Option<Value>,
    hung: bool,
    last_live_view: Option<Value>,
    last_live_view_at: Option<Instant>,
}

impl PlayBridge {
    pub(crate) fn play_id(&self) -> &str {
        &self.play_id
    }

    pub(crate) fn play_dir(&self) -> &Path {
        &self.play_dir
    }

    pub(crate) fn snapshot_manifest(&self) -> &Path {
        &self.snapshot_manifest
    }

    fn reap(&mut self) {
        let mut dead = false;
        if let Some(child) = &mut self.child {
            if let Ok(Some(_)) = child.try_wait() {
                dead = true;
            }
        }
        if !pid_is_alive(self.pid) {
            dead = true;
        }
        if dead {
            self.client = None;
            self.child = None;
            self.load_exit_report();
        }
    }

    fn alive(&self) -> bool {
        self.child.is_some() && pid_is_alive(self.pid)
    }

    fn load_exit_report(&mut self) {
        if self.last_exit_report.is_some() {
            return;
        }
        let path = self.play_dir.join("exit_report.json");
        if let Ok(bytes) = std::fs::read(&path) {
            if let Ok(value) = serde_json::from_slice::<Value>(&bytes) {
                self.last_exit_report = Some(strip_secret(value, &self.token));
            }
        }
    }

    fn drop_client(&mut self) {
        self.client = None;
    }

    fn connect_from_player_json(&mut self) -> Result<&mut ControlClient, RpcError> {
        self.client = None;
        let client = ControlClient::connect_player_json(&self.player_json_path)
            .map_err(|e| app_err("E_IO", e.to_string()))?;
        self.client = Some(client);
        self.client
            .as_mut()
            .ok_or_else(|| app_err("E_IO", "player control client is not connected"))
    }

    fn ensure_client(&mut self) -> Result<&mut ControlClient, RpcError> {
        if self.client.is_none() {
            self.connect_from_player_json()?;
        }
        self.client
            .as_mut()
            .ok_or_else(|| app_err("E_IO", "player control client is not connected"))
    }

    /// Run a control RPC. On I/O (dead TCP socket) drop the client, reconnect
    /// once from `player.json`, and retry the same call. Token stays in memory.
    fn call_player<T, F>(&mut self, mut op: F) -> Result<T, RpcError>
    where
        F: FnMut(&mut ControlClient) -> Result<T, gs_player::Error>,
    {
        let first = {
            let client = self.ensure_client()?;
            op(client)
        };
        match first {
            Ok(value) => Ok(value),
            Err(err) => {
                let message = err.to_string();
                if !is_control_io(&message) {
                    return Err(map_player_rpc(message));
                }
                self.drop_client();
                let client = self.connect_from_player_json()?;
                op(client).map_err(|e| map_player_rpc(e.to_string()))
            }
        }
    }

    fn shutdown(&mut self) {
        if let Some(client) = &mut self.client {
            let _ = client.stop(true);
        }
        self.client = None;
        if let Some(mut child) = self.child.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
        self.load_exit_report();
    }
}

impl Editor {
    pub(crate) fn play_start(
        &mut self,
        ctx: CallContext<'_>,
        params: Value,
    ) -> Result<Value, RpcError> {
        self.play_start_with(ctx, params, PlayStartFlags::default())
    }

    pub(crate) fn play_start_with(
        &mut self,
        ctx: CallContext<'_>,
        mut params: Value,
        flags: PlayStartFlags,
    ) -> Result<Value, RpcError> {
        // I11: in-memory command_id dedup only — not WAL-backed.
        let command_id = take_command_id(&mut params)?;
        if let Some(cached) = self.play_start_by_command.get(&command_id).cloned() {
            return Ok(cached);
        }

        if let Some(pid) = self.running_player_pid() {
            return Err(player_running(pid));
        }

        let root = self.play_root();
        if let Some(existing) = locate_player_json(&root, None) {
            if let Ok(file) = read_player_file(&existing) {
                if pid_is_alive(file.pid) {
                    return Err(player_running(file.pid));
                }
            }
            let _ = cleanup_stale_player_json(&existing);
        }

        if let Some(session) = self.session.as_mut() {
            session.autosave().map_err(scene_err)?;
        }

        if let Some(scene_id) = optional_str(&params, "scene_id") {
            if let Some(session) = &self.session {
                if scene_id != session.document().scene_id {
                    return Err(app_err("E_NOT_FOUND", format!("unknown scene {scene_id}")));
                }
            }
        }

        let seed = params.get("seed").and_then(Value::as_u64).unwrap_or(0);
        let force = params
            .get("force")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let replay_rel = optional_str(&params, "replay_tape").map(ToOwned::to_owned);
        let record_rel = optional_str(&params, "record_tape").map(ToOwned::to_owned);
        let play_id = format!("p_{}", Ulid::new());
        let revision = self
            .session
            .as_ref()
            .map(|s| s.document().revision_label())
            .unwrap_or_else(|| "r-000000".into());
        let scene = match &self.session {
            Some(session) => serde_json::from_slice(&session.canonical_scene_bytes())
                .map_err(|e| app_err("E_IO", e.to_string()))?,
            None => json!({
                "entities": [],
                "mode": "2d",
                "schema_version": 1,
            }),
        };

        let request = SnapshotRequest {
            play_id: play_id.clone(),
            document_revision: revision.clone(),
            engine_ver: env!("CARGO_PKG_VERSION").to_owned(),
            protocol_ver: PROTOCOL_VER.to_owned(),
            seed,
            created_at: utc_now_rfc3339(),
            actor: ctx.actor_id.to_owned(),
            scene,
            project_settings: match &self.session {
                Some(session) => session.read_project_settings(),
                None => gs_scene::default_project_settings(),
            },
            input_map: match &self.session {
                Some(session) => session.read_inputmap().map_err(scene_err)?,
                None => gs_scene::default_inputmap(),
            },
            scripts: crate::scripts::collect_snapshot_scripts(&root),
            assets: Default::default(),
        };
        let built = build_snapshot(&root, &request).map_err(|e| app_err("E_IO", e.to_string()))?;

        let replay_path = if let Some(rel) = replay_rel.as_deref() {
            let src = resolve_project_rel(&root, rel, true)?;
            let dest = built.play_dir.join(gs_player::REPLAY_TAPE_FILE);
            if flags.rewrite_replay_header {
                rewrite_tape_header(&src, &dest, &built.manifest)?;
            } else {
                if let Some(parent) = dest.parent() {
                    std::fs::create_dir_all(parent).map_err(|e| app_err("E_IO", e.to_string()))?;
                }
                std::fs::copy(&src, &dest).map_err(|e| app_err("E_IO", e.to_string()))?;
            }
            Some(dest)
        } else {
            None
        };
        let record_path = if let Some(rel) = record_rel.as_deref() {
            Some(resolve_project_rel(&root, rel, false)?)
        } else {
            None
        };

        let exe = find_player_exe().map_err(|e| app_err("E_IO", e.to_string()))?;
        let mut cmd = Command::new(&exe);
        cmd.arg("--snapshot")
            .arg(&built.manifest_path)
            .arg("--control-port")
            .arg("0")
            .arg("--headless");
        if let Some(path) = &replay_path {
            cmd.arg("--replay").arg(path);
        }
        if let Some(path) = &record_path {
            cmd.arg("--record").arg(path);
        }
        if force {
            cmd.arg("--force");
        }
        let mut child = cmd
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| app_err("E_IO", format!("spawn gs-player: {e}")))?;
        drain_child_stdio(&mut child);
        let pid = child.id();

        let player_json = match wait_for_player_json(&root, &built.play_dir, pid, &mut child) {
            Ok(path) => path,
            Err(err) => {
                let _ = child.kill();
                let _ = child.wait();
                return Err(err);
            }
        };
        let file = read_player_file(&player_json).map_err(|e| app_err("E_IO", e.to_string()))?;
        let token = file.token().to_owned();
        let client = ControlClient::connect_player_file(&file)
            .map_err(|e| app_err("E_IO", format!("connect player control: {e}")))?;

        let mut bridge = PlayBridge {
            play_id: play_id.clone(),
            pid,
            token: token.clone(),
            child: Some(child),
            client: Some(client),
            snapshot_manifest: built.manifest_path.clone(),
            player_json_path: player_json,
            play_dir: built.play_dir,
            last_ok_status: Some(Instant::now()),
            last_status: None,
            last_exit_report: None,
            hung: false,
            last_live_view: None,
            last_live_view_at: None,
        };
        if let Ok(status) = bridge.call_player(ControlClient::status) {
            bridge.last_status = Some(status);
            bridge.last_ok_status = Some(Instant::now());
        }
        self.play = Some(bridge);
        let _ = gc_play_snapshots_except(&root, Some(&play_id));

        if let Some(actor) = self.actors.get_mut(ctx.actor_id) {
            actor.command_count = actor.command_count.saturating_add(1);
        }
        let badge = self
            .actors
            .get(ctx.actor_id)
            .map(|a| a.principal.badge())
            .unwrap_or(crate::types::Badge::System);
        self.feed.push(FeedEntry {
            badge,
            actor: ctx.actor_id.to_owned(),
            label: format!("play.start {play_id}"),
            entities: Vec::new(),
            revision,
        });
        self.emit_play(json!({
            "play_id": play_id,
            "pid": pid,
            "alive": true,
            "snapshot_manifest": built.manifest_path.to_string_lossy(),
        }));

        let result = json!({
            "play_id": play_id,
            "pid": pid,
            "snapshot_manifest": built.manifest_path.to_string_lossy(),
        });
        let result = strip_secret(result, &token);
        self.play_start_by_command
            .insert(command_id, result.clone());
        Ok(result)
    }

    pub(crate) fn play_status(&mut self) -> Result<Value, RpcError> {
        self.reap_play();
        let Some(play) = self.play.as_mut() else {
            return Ok(json!({ "alive": false, "hung": false }));
        };
        if !play.alive() {
            play.load_exit_report();
            return Ok(dead_status(play));
        }
        match play.call_player(ControlClient::status) {
            Ok(status) => {
                play.last_ok_status = Some(Instant::now());
                play.last_status = Some(status.clone());
                play.hung = false;
                Ok(live_status(
                    &status,
                    false,
                    None,
                    &play.token,
                    &play.snapshot_manifest,
                ))
            }
            Err(_) => {
                let hung = play
                    .last_ok_status
                    .map(|t| t.elapsed() >= HUNG_AFTER)
                    .unwrap_or(true);
                play.hung = hung;
                let status = play.last_status.clone().unwrap_or(PlayStatus {
                    play_id: play.play_id.clone(),
                    pid: play.pid,
                    paused: false,
                    frame: 0,
                    timescale: 1.0,
                    alive: true,
                });
                Ok(live_status(
                    &status,
                    hung,
                    None,
                    &play.token,
                    &play.snapshot_manifest,
                ))
            }
        }
    }

    pub(crate) fn play_pause(&mut self) -> Result<Value, RpcError> {
        self.forward_play("play.pause", json!({}))
    }

    pub(crate) fn play_resume(&mut self) -> Result<Value, RpcError> {
        self.forward_play("play.resume", json!({}))
    }

    pub(crate) fn play_step_frames(&mut self, params: &Value) -> Result<Value, RpcError> {
        let n = match params.get("n") {
            None | Some(Value::Null) => 1,
            Some(v) => v
                .as_u64()
                .and_then(|n| u32::try_from(n).ok())
                .ok_or_else(|| invalid_params("n must be a u32"))?,
        };
        if n > gs_player::MAX_STEP_FRAMES {
            return Err(invalid_params(format!(
                "n={n} exceeds cap {}",
                gs_player::MAX_STEP_FRAMES
            )));
        }
        self.forward_play("play.step_frames", json!({ "n": n }))
    }

    /// Play-scoped `input.inject`. No live play → `E_NOT_FOUND`. Token is never logged (I8).
    pub(crate) fn input_inject(&mut self, params: &Value) -> Result<Value, RpcError> {
        self.reap_play();
        let play = self
            .play
            .as_mut()
            .ok_or_else(|| app_err("E_NOT_FOUND", "no player"))?;
        if !play.alive() {
            return Err(app_err("E_NOT_FOUND", "player is not alive"));
        }
        if let Some(id) = optional_str(params, "play_id") {
            if id != play.play_id {
                return Err(app_err(
                    "E_NOT_FOUND",
                    format!("play_id {id} is not the running play"),
                ));
            }
        }
        let actions = params
            .get("actions")
            .cloned()
            .ok_or_else(|| invalid_params("actions must be an array"))?;
        if !actions.is_array() {
            return Err(invalid_params("actions must be an array"));
        }
        let play_id = play.play_id.clone();
        let token = play.token.clone();
        let value = play.call_player(|c| c.input_inject(Some(&play_id), actions.clone()))?;
        Ok(strip_secret(value, &token))
    }

    pub(crate) fn script_reload(&mut self, params: &Value) -> Result<Value, RpcError> {
        self.reap_play();
        let play = self
            .play
            .as_mut()
            .ok_or_else(|| app_err("E_NOT_FOUND", "play is not running"))?;
        if !play.alive() {
            return Err(app_err("E_NOT_FOUND", "play is not running"));
        }
        let path = optional_str(params, "path");
        let source = optional_str(params, "source");
        let entity_id = optional_str(params, "entity_id");
        let play_id = play.play_id.clone();
        let token = play.token.clone();
        let value = play
            .call_player(|client| client.script_reload(Some(&play_id), path, source, entity_id))?;
        Ok(strip_secret(value, &token))
    }

    /// Best-effort hot reload while a player is alive. Compile failure stays
    /// on the player (old instance kept). Never logs the token (I8).
    pub(crate) fn forward_script_reload_if_playing(
        &mut self,
        path: &str,
        source: &str,
        entity_id: Option<&str>,
    ) {
        self.reap_play();
        let Some(play) = self.play.as_mut() else {
            return;
        };
        if !play.alive() {
            return;
        }
        let play_id = play.play_id.clone();
        let _ = play.call_player(|client| {
            client.script_reload(Some(&play_id), Some(path), Some(source), entity_id)
        });
    }

    pub(crate) fn play_set_timescale(&mut self, params: &Value) -> Result<Value, RpcError> {
        let t = params
            .get("timescale")
            .or_else(|| params.get("value"))
            .and_then(Value::as_f64)
            .ok_or_else(|| invalid_params("timescale must be a number"))?;
        if !(gs_player::TIMESCALE_MIN..=gs_player::TIMESCALE_MAX).contains(&t) {
            return Err(invalid_params(format!(
                "timescale {t} is outside {}..{}",
                gs_player::TIMESCALE_MIN,
                gs_player::TIMESCALE_MAX
            )));
        }
        self.forward_play("play.set_timescale", json!({ "timescale": t }))
    }

    pub(crate) fn play_stop(&mut self, params: &Value) -> Result<Value, RpcError> {
        let force = params
            .get("force")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        self.reap_play();
        if self.play.is_none() {
            return Ok(json!({ "alive": false }));
        }
        if !self.play.as_ref().is_some_and(PlayBridge::alive) {
            if let Some(play) = self.play.as_mut() {
                play.load_exit_report();
                let report = play
                    .last_exit_report
                    .clone()
                    .unwrap_or_else(|| json!({ "alive": false, "exit_code": -1 }));
                return Ok(strip_secret(report, &play.token));
            }
        }

        let token = self
            .play
            .as_ref()
            .map(|p| p.token.clone())
            .unwrap_or_default();
        let result = {
            let play = self.play.as_mut().expect("play present");
            play.call_player(|client| client.stop(force))
        };
        match result {
            Ok(report) => {
                let (value, play_id, pid) = {
                    let play = self.play.as_mut().expect("play present");
                    if let Some(mut child) = play.child.take() {
                        let _ = child.wait();
                    }
                    play.client = None;
                    play.load_exit_report();
                    let value = serde_json::to_value(&report)
                        .unwrap_or_else(|_| json!({ "exit_code": report.exit_code }));
                    let value = strip_secret(value, &token);
                    play.last_exit_report = Some(value.clone());
                    (value, play.play_id.clone(), play.pid)
                };
                self.emit_play(json!({
                    "play_id": play_id,
                    "pid": pid,
                    "alive": false,
                }));
                Ok(value)
            }
            Err(_) => {
                let play = self.play.as_mut().expect("play present");
                if let Some(mut child) = play.child.take() {
                    let _ = child.kill();
                    let deadline = Instant::now() + Duration::from_secs(1);
                    loop {
                        if child.try_wait().ok().flatten().is_some() {
                            break;
                        }
                        if Instant::now() >= deadline {
                            let _ = child.kill();
                            let _ = child.wait();
                            break;
                        }
                        thread::sleep(Duration::from_millis(20));
                    }
                }
                play.client = None;
                play.load_exit_report();
                let report = play.last_exit_report.clone().unwrap_or_else(|| {
                    json!({
                        "exit_code": if force { 1 } else { 0 },
                        "frames": play.last_status.as_ref().map(|s| s.frame).unwrap_or(0),
                        "log_tail": [],
                    })
                });
                Ok(strip_secret(report, &token))
            }
        }
    }

    pub(crate) fn obs_events(&mut self, params: &Value) -> Result<Value, RpcError> {
        self.forward_obs("obs.events", params.clone())
    }

    pub(crate) fn obs_world_dump(&mut self, params: &Value) -> Result<Value, RpcError> {
        self.forward_obs("obs.world_dump", params.clone())
    }

    pub(crate) fn obs_logs_tail(&mut self, params: &Value) -> Result<Value, RpcError> {
        self.forward_obs("obs.logs_tail", params.clone())
    }

    pub(crate) fn obs_perf(&mut self, params: &Value) -> Result<Value, RpcError> {
        self.forward_obs("obs.perf", params.clone())
    }

    pub(crate) fn obs_screenshot(&mut self, params: &Value) -> Result<Value, RpcError> {
        self.forward_obs("obs.screenshot", params.clone())
    }

    pub(crate) fn judge_run_until_event(&mut self, params: &Value) -> Result<Value, RpcError> {
        self.forward_obs("judge.run_until_event", params.clone())
    }

    pub(crate) fn judge_wait_event(&mut self, params: &Value) -> Result<Value, RpcError> {
        self.forward_obs("judge.wait_event", params.clone())
    }

    pub(crate) fn judge_assert_world(&mut self, params: &Value) -> Result<Value, RpcError> {
        self.forward_obs("judge.assert_world", params.clone())
    }

    pub(crate) fn judge_assert_perf(&mut self, params: &Value) -> Result<Value, RpcError> {
        self.forward_obs("judge.assert_perf", params.clone())
    }

    pub(crate) fn judge_assert_screenshot(&mut self, params: &Value) -> Result<Value, RpcError> {
        self.forward_obs("judge.assert_screenshot", params.clone())
    }

    pub(crate) fn shutdown_play(&mut self) {
        if let Some(mut play) = self.play.take() {
            play.shutdown();
        }
    }

    fn forward_play(&mut self, method: &str, params: Value) -> Result<Value, RpcError> {
        self.reap_play();
        let play = self
            .play
            .as_mut()
            .ok_or_else(|| app_err("E_NOT_FOUND", "no player"))?;
        if !play.alive() {
            return Err(app_err("E_NOT_FOUND", "player is not alive"));
        }
        let token = play.token.clone();
        let value = match method {
            "play.pause" => play.call_player(|c| c.pause().map(|s| json_status(&s)))?,
            "play.resume" => play.call_player(|c| c.resume().map(|s| json_status(&s)))?,
            "play.step_frames" => {
                let n = params.get("n").and_then(Value::as_u64).unwrap_or(1) as u32;
                play.call_player(|c| c.step_frames(n).map(|s| json_status(&s)))?
            }
            "play.set_timescale" => {
                let t = params
                    .get("timescale")
                    .and_then(Value::as_f64)
                    .unwrap_or(1.0);
                play.call_player(|c| c.set_timescale(t).map(|s| json_status(&s)))?
            }
            other => return Err(app_err("E_IO", format!("cannot forward {other}"))),
        };
        if let Ok(status) = serde_json::from_value::<PlayStatus>(value.clone()) {
            play.last_status = Some(status);
            play.last_ok_status = Some(Instant::now());
            play.hung = false;
        }
        Ok(strip_secret(value, &token))
    }

    fn forward_obs(&mut self, method: &str, mut params: Value) -> Result<Value, RpcError> {
        self.reap_play();
        let play = self
            .play
            .as_mut()
            .ok_or_else(|| app_err("E_NOT_FOUND", "no player"))?;
        if !play.alive() {
            return Err(app_err("E_NOT_FOUND", "player is not alive"));
        }
        if params.get("play_id").and_then(Value::as_str).is_none() {
            if let Value::Object(map) = &mut params {
                map.insert("play_id".into(), json!(play.play_id));
            }
        }
        let token = play.token.clone();
        let value = play.call_player(|c| c.call(method, params.clone()))?;
        Ok(strip_secret(value, &token))
    }

    pub(crate) fn runtime_copy_to_scene(
        &mut self,
        ctx: CallContext<'_>,
        mut params: Value,
    ) -> Result<Value, RpcError> {
        let command_id = take_command_id(&mut params)?;
        let expected = string_field(&params, "expected_revision")?;
        let play_id_param = optional_str(&params, "play_id").map(ToOwned::to_owned);
        let entity_ids = string_list(&params, "entity_ids")?;
        let fields = string_list(&params, "fields")?;

        self.reap_play();
        let play = self
            .play
            .as_ref()
            .ok_or_else(|| app_err("E_NOT_FOUND", "no player"))?;
        if !play.alive() {
            return Err(app_err("E_NOT_FOUND", "player is not alive"));
        }
        if let Some(id) = play_id_param.as_deref() {
            if id != play.play_id {
                return Err(app_err(
                    "E_NOT_FOUND",
                    format!("play_id {id} is not the running play"),
                ));
            }
        }

        let current = self.current_revision();
        if expected != current {
            return Err(scene_err(SceneError::Conflict { expected, current }));
        }

        let dump = self.fetch_world_dump_json()?;
        let entities = dump
            .get("entities")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        let known_ids: std::collections::BTreeSet<u64> = {
            let session = self.session_ref()?;
            session.document().scene.entities.keys().copied().collect()
        };

        let mut commands = Vec::new();
        let mut copied = Vec::new();
        let mut skipped = Vec::new();
        let mut warnings = Vec::new();

        let selected: Vec<Value> = if entity_ids.is_empty() {
            entities
        } else {
            let mut picked = Vec::new();
            for id in &entity_ids {
                if let Some(ent) = entities
                    .iter()
                    .find(|e| e.get("id").and_then(Value::as_str) == Some(id.as_str()))
                {
                    picked.push(ent.clone());
                } else if is_runtime_entity_id(id) {
                    skipped.push(id.clone());
                    warnings.push(format!("skipped runtime entity {id}"));
                } else {
                    skipped.push(id.clone());
                    warnings.push(format!("entity {id} is not in the play world dump"));
                }
            }
            picked
        };

        for ent in selected {
            let Some(id) = ent.get("id").and_then(Value::as_str).map(ToOwned::to_owned) else {
                continue;
            };
            if is_runtime_entity_id(&id) {
                skipped.push(id.clone());
                warnings.push(format!("skipped runtime entity {id}"));
                continue;
            }
            if !is_document_entity_id(&id) {
                skipped.push(id.clone());
                warnings.push(format!("skipped non-document entity {id}"));
                continue;
            }
            let n = match gs_scene::parse_entity_id(&id) {
                Ok(n) => n,
                Err(_) => {
                    skipped.push(id.clone());
                    warnings.push(format!("skipped invalid document id {id}"));
                    continue;
                }
            };
            if !known_ids.contains(&n) {
                skipped.push(id.clone());
                warnings.push(format!("document has no entity {id}"));
                continue;
            }
            let Some(transform) = ent.get("transform").filter(|v| v.is_object()) else {
                skipped.push(id.clone());
                warnings.push(format!("{id} dump has no Transform2D"));
                continue;
            };
            let Some(patch) = transform_patch(transform, &fields) else {
                skipped.push(id.clone());
                warnings.push(format!("{id} dump has no copyable Transform2D fields"));
                continue;
            };
            commands.push(SceneCommand::component_set(
                id.clone(),
                "Transform2D",
                patch,
            ));
            copied.push(id);
        }

        if commands.is_empty() {
            return Ok(json!({
                "play_id": self.play.as_ref().map(|p| p.play_id.clone()),
                "revision": current,
                "copied": copied,
                "skipped": skipped,
                "warnings": warnings,
            }));
        }

        let token = self
            .play
            .as_ref()
            .map(|p| p.token.clone())
            .unwrap_or_default();
        let ack = self.dispatch_request(
            ctx,
            command_id,
            Some(expected),
            commands,
            "runtime.copy_to_scene",
        )?;
        let mut result = ack;
        if let Some(obj) = result.as_object_mut() {
            obj.insert("copied".into(), json!(copied));
            obj.insert("skipped".into(), json!(skipped));
            obj.insert("warnings".into(), json!(warnings));
        }
        Ok(strip_secret(result, &token))
    }

    /// Last play world dump as JSON, throttled to 10 Hz. No eframe window.
    pub fn live_view_snapshot(&mut self) -> Result<Value, RpcError> {
        if let Some(play) = self.play.as_ref() {
            if let (Some(cached), Some(at)) = (&play.last_live_view, play.last_live_view_at) {
                if at.elapsed() < LIVE_VIEW_MIN_INTERVAL {
                    let mut value = cached.clone();
                    if let Some(obj) = value.as_object_mut() {
                        obj.insert("cached".into(), json!(true));
                    }
                    return Ok(strip_secret(value, &play.token));
                }
            }
        }
        self.reap_play();
        let play = self
            .play
            .as_ref()
            .ok_or_else(|| app_err("E_NOT_FOUND", "no player"))?;
        if !play.alive() {
            return Err(app_err("E_NOT_FOUND", "player is not alive"));
        }
        let play_id = play.play_id.clone();
        let token = play.token.clone();
        let dump = self.fetch_world_dump_json()?;
        let value = json!({
            "play_id": play_id,
            "cached": false,
            "frame": dump.get("frame").cloned().unwrap_or(json!(0)),
            "entity_count": dump.get("entity_count").cloned().unwrap_or(json!(0)),
            "entities": dump.get("entities").cloned().unwrap_or(json!([])),
        });
        if let Some(play) = self.play.as_mut() {
            play.last_live_view = Some(value.clone());
            play.last_live_view_at = Some(Instant::now());
        }
        Ok(strip_secret(value, &token))
    }

    pub(crate) fn fetch_world_dump_json(&mut self) -> Result<Value, RpcError> {
        let result = self.forward_obs("obs.world_dump", json!({}))?;
        if let Some(entities) = result.get("entities") {
            if entities.is_array() {
                return Ok(result);
            }
        }
        let path = result
            .get("path")
            .and_then(Value::as_str)
            .ok_or_else(|| app_err("E_IO", "world dump missing path"))?;
        let bytes = std::fs::read(path).map_err(|e| app_err("E_IO", e.to_string()))?;
        serde_json::from_slice(&bytes).map_err(|e| app_err("E_IO", e.to_string()))
    }

    fn running_player_pid(&mut self) -> Option<u32> {
        self.reap_play();
        let play = self.play.as_ref()?;
        if play.alive() {
            Some(play.pid)
        } else {
            None
        }
    }

    fn reap_play(&mut self) {
        if let Some(play) = self.play.as_mut() {
            play.reap();
        }
    }

    fn play_root(&self) -> PathBuf {
        self.project_path
            .clone()
            .unwrap_or_else(|| self.runtime_root.clone())
    }

    fn emit_play(&mut self, params: Value) {
        self.emit(gs_protocol::Notification::new(EVENT_PLAY, params));
    }
}

impl Drop for Editor {
    fn drop(&mut self) {
        self.shutdown_play();
    }
}

fn wait_for_player_json(
    root: &Path,
    play_dir: &Path,
    pid: u32,
    child: &mut Child,
) -> Result<PathBuf, RpcError> {
    let start = Instant::now();
    loop {
        if start.elapsed() > START_WAIT {
            return Err(app_err("E_IO", "timed out waiting for player.json"));
        }
        if let Ok(Some(status)) = child.try_wait() {
            return Err(app_err(
                "E_IO",
                format!("gs-player exited before writing player.json ({status})"),
            ));
        }
        if let Some(path) = locate_player_json(root, Some(play_dir)) {
            if let Ok(file) = read_player_file(&path) {
                if file.pid == pid && file.port != 0 {
                    return Ok(path);
                }
            }
        }
        thread::sleep(Duration::from_millis(20));
    }
}

fn drain_child_stdio(child: &mut Child) {
    if let Some(stdout) = child.stdout.take() {
        thread::spawn(move || {
            let mut reader = BufReader::new(stdout);
            let mut line = String::new();
            while reader.read_line(&mut line).ok().is_some_and(|n| n > 0) {
                line.clear();
            }
        });
    }
    if let Some(stderr) = child.stderr.take() {
        thread::spawn(move || {
            let mut reader = BufReader::new(stderr);
            let mut line = String::new();
            while reader.read_line(&mut line).ok().is_some_and(|n| n > 0) {
                line.clear();
            }
        });
    }
}

fn map_player_rpc(message: String) -> RpcError {
    let stripped = message
        .strip_prefix("control: ")
        .unwrap_or(message.as_str());
    if let Some((code, rest)) = stripped.split_once(':') {
        let code = code.trim();
        if looks_like_player_app_code(code) {
            return app_err(code, rest.trim());
        }
    }
    app_err("E_IO", message)
}

fn looks_like_player_app_code(code: &str) -> bool {
    matches!(
        code,
        "E_NOT_FOUND"
            | "E_IO"
            | "E_VALIDATION"
            | "E_PLAYER"
            | "E_ASSERT"
            | "no_gpu"
            | "GS-EC-35"
            | "GS-EC-36"
            | "SCRIPT_HANG"
            | "OOM_GUARD"
    )
}

fn player_running(pid: u32) -> RpcError {
    RpcError::with_data(
        APP,
        format!("a player is already running (pid {pid})"),
        ErrorData {
            app_code: "E_PLAYER_RUNNING".into(),
            retryable: Some(false),
            field: None,
            reason: Some(format!("pid={pid}")),
        },
    )
}

fn json_status(status: &PlayStatus) -> Value {
    json!({
        "play_id": status.play_id,
        "pid": status.pid,
        "paused": status.paused,
        "frame": status.frame,
        "timescale": status.timescale,
        "alive": status.alive,
    })
}

fn live_status(
    status: &PlayStatus,
    hung: bool,
    exit_report: Option<Value>,
    token: &str,
    snapshot_manifest: &Path,
) -> Value {
    let mut value = json_status(status);
    if let Some(obj) = value.as_object_mut() {
        obj.insert("hung".into(), json!(hung));
        obj.insert(
            "snapshot_manifest".into(),
            json!(snapshot_manifest.to_string_lossy()),
        );
        if let Some(report) = exit_report {
            obj.insert("exit_report".into(), report);
        }
    }
    strip_secret(value, token)
}

fn dead_status(play: &PlayBridge) -> Value {
    let mut value = json!({
        "play_id": play.play_id,
        "pid": play.pid,
        "paused": play.last_status.as_ref().map(|s| s.paused).unwrap_or(false),
        "frame": play.last_status.as_ref().map(|s| s.frame).unwrap_or(0),
        "timescale": play.last_status.as_ref().map(|s| s.timescale).unwrap_or(1.0),
        "alive": false,
        "hung": false,
        "snapshot_manifest": play.snapshot_manifest.to_string_lossy(),
    });
    if let Some(report) = &play.last_exit_report {
        if let Some(obj) = value.as_object_mut() {
            obj.insert("exit_report".into(), report.clone());
        }
    }
    strip_secret(value, &play.token)
}

fn optional_str<'a>(params: &'a Value, key: &str) -> Option<&'a str> {
    params
        .get(key)
        .and_then(Value::as_str)
        .filter(|s| !s.is_empty())
}

fn strip_secret(mut value: Value, token: &str) -> Value {
    if token.is_empty() {
        return value;
    }
    strip_secret_in(&mut value, token);
    value
}

fn strip_secret_in(value: &mut Value, token: &str) {
    match value {
        Value::String(s) if s.contains(token) => {
            *s = s.replace(token, "<redacted>");
        }
        Value::Array(items) => {
            for item in items {
                strip_secret_in(item, token);
            }
        }
        Value::Object(map) => {
            map.remove("token");
            for (key, item) in map.iter_mut() {
                if key == "token" {
                    *item = json!("<redacted>");
                } else {
                    strip_secret_in(item, token);
                }
            }
        }
        _ => {}
    }
}

pub(crate) fn play_topic(method: &str) -> bool {
    method == EVENT_PLAY
}

pub(crate) fn is_obs_method(method: &str) -> bool {
    matches!(
        method,
        "obs.events" | "obs.world_dump" | "obs.logs_tail" | "obs.perf" | "obs.screenshot"
    )
}

pub(crate) fn is_judge_method(method: &str) -> bool {
    matches!(
        method,
        "judge.run_until_event"
            | "judge.wait_event"
            | "judge.assert_world"
            | "judge.assert_perf"
            | "judge.assert_screenshot"
            | "judge.run_test"
    )
}

pub(crate) fn is_play_method(method: &str) -> bool {
    matches!(
        method,
        "play.start"
            | "play.stop"
            | "play.status"
            | "play.pause"
            | "play.resume"
            | "play.step_frames"
            | "play.set_timescale"
            | "script.reload"
    )
}

pub(crate) fn is_input_method(method: &str) -> bool {
    method == "input.inject"
}

pub(crate) fn is_runtime_method(method: &str) -> bool {
    method == "runtime.copy_to_scene"
}

pub(crate) fn play_is_mutating(method: &str) -> bool {
    (is_play_method(method) && method != "play.status")
        || is_input_method(method)
        || is_runtime_method(method)
        || method == "judge.run_until_event"
        || method == "judge.run_test"
}

/// Keep at most 10 play snapshot dirs under `{root}/.gs/runtime/play/`.
/// Returns how many directories were deleted. Tests may call this on fake dirs.
pub fn gc_play_snapshots(root: impl AsRef<Path>) -> usize {
    gc_play_snapshots_except(root.as_ref(), None)
}

fn gc_play_snapshots_except(root: &Path, keep_play_id: Option<&str>) -> usize {
    let play_root = root.join(".gs").join("runtime").join("play");
    let Ok(entries) = std::fs::read_dir(&play_root) else {
        return 0;
    };
    let mut dirs: Vec<(SystemTime, PathBuf, String)> = entries
        .filter_map(|e| e.ok())
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
                .map(|m| dir_time(&m))
                .unwrap_or(SystemTime::UNIX_EPOCH);
            (time, path, name)
        })
        .collect();
    dirs.sort_by(|a, b| a.0.cmp(&b.0).then_with(|| a.2.cmp(&b.2)));
    let mut deleted = 0;
    while dirs.len() > PLAY_SNAPSHOT_KEEP {
        let Some(idx) = dirs
            .iter()
            .position(|(_, _, name)| keep_play_id != Some(name.as_str()))
        else {
            break;
        };
        let (_, path, _) = dirs.remove(idx);
        let _ = std::fs::remove_dir_all(&path);
        deleted += 1;
    }
    deleted
}

fn dir_time(meta: &std::fs::Metadata) -> SystemTime {
    meta.created()
        .or_else(|_| meta.modified())
        .unwrap_or(SystemTime::UNIX_EPOCH)
}

fn is_control_io(message: &str) -> bool {
    let m = message.to_ascii_lowercase();
    m.contains("i/o error")
        || m.contains("os error")
        || m.contains("unexpected end of stream")
        || m.contains("broken pipe")
        || m.contains("connection abort")
        || m.contains("connection reset")
        || m.contains("forcibly closed")
        || m.contains("timed out")
        || m.contains("10053")
        || m.contains("10054")
}

fn is_document_entity_id(id: &str) -> bool {
    id.starts_with("e_") && gs_scene::parse_entity_id(id).is_ok()
}

fn is_runtime_entity_id(id: &str) -> bool {
    id.starts_with("rt_")
}

fn transform_patch(transform: &Value, fields: &[String]) -> Option<Value> {
    let mask = FieldMask::from_fields(fields);
    let mut patch = Map::new();
    for (key, sel) in [
        ("x", mask.x),
        ("y", mask.y),
        ("rot", mask.rot),
        ("sx", mask.sx),
        ("sy", mask.sy),
    ] {
        match sel {
            FieldSel::Never => {}
            FieldSel::Always => {
                patch.insert(key.into(), transform.get(key)?.clone());
            }
            FieldSel::IfPresent => {
                if let Some(v) = transform.get(key) {
                    patch.insert(key.into(), v.clone());
                }
            }
        }
    }
    if patch.is_empty() {
        None
    } else {
        Some(Value::Object(patch))
    }
}

#[derive(Clone, Copy)]
enum FieldSel {
    Always,
    IfPresent,
    Never,
}

struct FieldMask {
    x: FieldSel,
    y: FieldSel,
    rot: FieldSel,
    sx: FieldSel,
    sy: FieldSel,
}

impl FieldMask {
    fn from_fields(fields: &[String]) -> Self {
        if fields.is_empty() {
            return Self {
                x: FieldSel::Always,
                y: FieldSel::Always,
                rot: FieldSel::IfPresent,
                sx: FieldSel::IfPresent,
                sy: FieldSel::IfPresent,
            };
        }
        let mut mask = Self {
            x: FieldSel::Never,
            y: FieldSel::Never,
            rot: FieldSel::Never,
            sx: FieldSel::Never,
            sy: FieldSel::Never,
        };
        for field in fields {
            let name = field.rsplit('.').next().unwrap_or(field.as_str());
            if field == "Transform2D" || field == "*" {
                mask.x = FieldSel::Always;
                mask.y = FieldSel::Always;
                mask.rot = FieldSel::IfPresent;
                mask.sx = FieldSel::IfPresent;
                mask.sy = FieldSel::IfPresent;
                continue;
            }
            match name {
                "x" => mask.x = FieldSel::Always,
                "y" => mask.y = FieldSel::Always,
                "rot" => mask.rot = FieldSel::Always,
                "sx" => mask.sx = FieldSel::Always,
                "sy" => mask.sy = FieldSel::Always,
                _ => {}
            }
        }
        mask
    }
}

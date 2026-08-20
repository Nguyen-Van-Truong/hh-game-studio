//! In-process + TCP play control server (MASTER 6.1, 9.5, I8).
//!
//! Binds **127.0.0.1 only**. Token lives in `player.json` and is never logged.
//! The NDJSON connection stays open across many RPCs (read idle ≥ 120s).
//!
//! `World` + `ScriptHost` (`!Send`) + `PhysicsHost` live on a dedicated
//! simulate thread.

use std::fs;
use std::io::{self, BufReader, Write};
use std::net::{IpAddr, Ipv4Addr, Shutdown, SocketAddr, TcpListener, TcpStream};
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, OnceLock};
use std::thread::{self, JoinHandle};
use std::time::Duration;

use gs_protocol::{
    decode_message, read_ndjson_line, write_ndjson_line, ErrorData, Message, ProtocolError,
    Request, Response, ResponsePayload, RpcError, APP, IDLE_TIMEOUT_SECS, INVALID_PARAMS,
    METHOD_NOT_FOUND, PROTOCOL_VER, UNAUTHORIZED,
};
use gs_runtime_core::World;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use ulid::Ulid;

use crate::error::Error;
use crate::events::EventTrace;
use crate::guard::{test_hang_ms_from_env, OOM_GUARD_BYTES};
use crate::input::{load_input_map, parse_inject_actions};
use crate::player_file::{
    cleanup_stale_player_json, player_json_for_snapshot, utc_now_rfc3339, write_player_file,
    PlayerFile,
};
use crate::script_play::load_play_scripts;
use crate::sim::{
    check_offered_play_id, materialize_reload, parse_reload_job, queue_reload, start_sim,
    PlayInner, ReloadQueue, SimClient, SimFlags, SimRequest,
};
use crate::tape::{bind_tape, validate_actions_in_map};
use crate::verify::verify_snapshot;

pub const MAX_STEP_FRAMES: u32 = 3600;
pub const TIMESCALE_MIN: f64 = 0.1;
pub const TIMESCALE_MAX: f64 = 10.0;
pub const LOG_TAIL_MAX: usize = crate::events::OBS_LOG_TAIL_MAX;
const CONTROL_WRITE_TIMEOUT: Duration = Duration::from_secs(5);

static CRASH_REPORT_DIR: OnceLock<PathBuf> = OnceLock::new();

/// World already in memory, or a verified snapshot manifest path.
pub enum PlaySource {
    World(Box<World>),
    Snapshot(PathBuf),
}

impl From<World> for PlaySource {
    fn from(world: World) -> Self {
        Self::World(Box::new(world))
    }
}

impl From<PathBuf> for PlaySource {
    fn from(path: PathBuf) -> Self {
        Self::Snapshot(path)
    }
}

impl From<&Path> for PlaySource {
    fn from(path: &Path) -> Self {
        Self::Snapshot(path.to_path_buf())
    }
}

/// Options for [`ControlServer::start_with_config`].
#[derive(Clone, Debug, PartialEq)]
pub struct ControlConfig {
    /// Skip GPU. `obs.screenshot` returns `app_code: no_gpu`.
    pub no_render: bool,
    /// Next simulate frame pretends to have taken this many ms (tests / `GS_TEST_HANG_MS`).
    pub test_hang_ms: Option<u64>,
    /// Injected memory counter used by the OOM guard (tests). Not a real alloc.
    pub injected_memory_bytes: Option<u64>,
    /// Limit compared against RSS or [`Self::injected_memory_bytes`].
    pub memory_guard_bytes: u64,
    /// Write a tape while simulating (`--record` or `record.tape.jsonl`).
    pub record_tape: Option<PathBuf>,
    /// Drive input from this tape (`--replay` or `replay.tape.jsonl`).
    pub replay_tape: Option<PathBuf>,
    /// Replay a mismatched header with a warning; [`ExitReport::evidence_ok`] is false.
    pub force_tape: bool,
}

impl Default for ControlConfig {
    fn default() -> Self {
        Self {
            no_render: false,
            test_hang_ms: None,
            injected_memory_bytes: None,
            memory_guard_bytes: OOM_GUARD_BYTES,
            record_tape: None,
            replay_tape: None,
            force_tape: false,
        }
    }
}

impl ControlConfig {
    /// Read `GS_GPU` and `GS_TEST_HANG_MS`. Used by the `gs-player` binary.
    pub fn from_env() -> Self {
        let mut cfg = Self::default();
        if crate::gpu::GpuMode::from_env().forces_no_render() {
            cfg.no_render = true;
        }
        cfg.test_hang_ms = test_hang_ms_from_env();
        cfg
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct PlayStatus {
    pub play_id: String,
    pub pid: u32,
    pub paused: bool,
    pub frame: u64,
    pub timescale: f64,
    pub alive: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct ExitReport {
    pub exit_code: i32,
    pub frames: u64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub last_error: Option<String>,
    pub log_tail: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub event_trace_path: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub perf_summary: Option<Value>,
    /// False when a tape was replayed with `--force` after a header mismatch.
    #[serde(default = "default_true")]
    pub evidence_ok: bool,
}

fn default_true() -> bool {
    true
}

/// Running control server: in-process methods + NDJSON JSON-RPC on 127.0.0.1.
pub struct ControlHandle {
    sim: Option<SimClient>,
    sim_thread: Option<JoinHandle<()>>,
    reloads: ReloadQueue,
    play_id: String,
    pid: u32,
    play_dir: Option<PathBuf>,
    addr: SocketAddr,
    token: String,
    player_json_path: Option<PathBuf>,
    shutdown: Arc<AtomicBool>,
    stopped: Arc<AtomicBool>,
    accept: Option<JoinHandle<()>>,
}

impl std::fmt::Debug for ControlHandle {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("ControlHandle")
            .field("addr", &self.addr)
            .field("player_json_path", &self.player_json_path)
            .field(
                "token",
                &if self.token.is_empty() {
                    "<empty>"
                } else {
                    "<redacted>"
                },
            )
            .finish()
    }
}

/// Bind a play world or snapshot on `127.0.0.1` (port `0` = ephemeral).
pub struct ControlServer;

impl ControlServer {
    pub fn start(source: impl Into<PlaySource>, bind: SocketAddr) -> Result<ControlHandle, Error> {
        start_inner(source.into(), bind, None, ControlConfig::default())
    }

    /// Like [`start`], and write/cleanup `{runtime_root}/.gs/runtime/player.json`.
    pub fn start_in(
        source: impl Into<PlaySource>,
        bind: SocketAddr,
        runtime_root: impl AsRef<Path>,
    ) -> Result<ControlHandle, Error> {
        start_inner(
            source.into(),
            bind,
            Some(runtime_root.as_ref().to_path_buf()),
            ControlConfig::default(),
        )
    }

    /// Start with explicit no-render / watchdog / memory-guard options.
    pub fn start_with_config(
        source: impl Into<PlaySource>,
        bind: SocketAddr,
        runtime_root: Option<PathBuf>,
        config: ControlConfig,
    ) -> Result<ControlHandle, Error> {
        start_inner(source.into(), bind, runtime_root, config)
    }
}

fn start_inner(
    source: PlaySource,
    bind: SocketAddr,
    runtime_root: Option<PathBuf>,
    config: ControlConfig,
) -> Result<ControlHandle, Error> {
    if bind.ip() != IpAddr::V4(Ipv4Addr::LOCALHOST) {
        return Err(Error::reject("control server must bind 127.0.0.1 (I8)"));
    }

    let pid = std::process::id();
    let token = generate_token();
    let started_at = utc_now_rfc3339();

    let mut verified = None;
    let (world, play_id, play_dir) = match source {
        PlaySource::World(world) => (*world, format!("p_{}", Ulid::new()), None),
        PlaySource::Snapshot(manifest) => {
            let loaded = verify_snapshot(&manifest)?;
            let play_dir = manifest
                .parent()
                .ok_or_else(|| Error::reject("manifest path has no parent directory"))?
                .to_path_buf();
            let mut world =
                World::from_scene_path(&play_dir.join("scene.json"), loaded.manifest.seed)?;
            load_play_scripts(&mut world, &play_dir)?;
            let play_id = loaded.play_id.clone();
            verified = Some(loaded);
            (world, play_id, Some(play_dir))
        }
    };
    let bound = bind_tape(
        verified.as_ref(),
        play_dir.as_deref(),
        config.replay_tape.as_deref(),
        config.record_tape.as_deref(),
        config.force_tape,
    )?;

    let player_json_path = match (&runtime_root, &play_dir) {
        (Some(root), _) => Some(root.join(".gs").join("runtime").join("player.json")),
        (None, Some(dir)) => {
            if let Ok(manifest) = dir.join("manifest.json").canonicalize() {
                Some(player_json_for_snapshot(&manifest))
            } else {
                Some(player_json_for_snapshot(&dir.join("manifest.json")))
            }
        }
        (None, None) => None,
    };

    if let Some(path) = &player_json_path {
        let _ = cleanup_stale_player_json(path)?;
    }

    let listener = TcpListener::bind(bind).map_err(|e| Error::control(e.to_string()))?;
    listener
        .set_nonblocking(true)
        .map_err(|e| Error::control(e.to_string()))?;
    let addr = listener
        .local_addr()
        .map_err(|e| Error::control(e.to_string()))?;

    if let Some(path) = &player_json_path {
        let file = PlayerFile::new(pid, addr.port(), play_id.clone(), started_at, token.clone());
        write_player_file(path, &file)?;
    }

    let events_path = play_dir.as_ref().map(|dir| dir.join("events.jsonl"));
    let event_trace = EventTrace::new(events_path).map_err(|e| Error::control(e.to_string()))?;

    if let Some(dir) = &play_dir {
        let _ = CRASH_REPORT_DIR.set(dir.clone());
    }

    let mut inner = PlayInner::new(
        world,
        play_id.clone(),
        pid,
        play_dir.clone(),
        event_trace,
        config.no_render,
        config.test_hang_ms,
        config.injected_memory_bytes,
        config.memory_guard_bytes,
    );
    if let Some(dir) = &play_dir {
        inner.set_base_input(load_input_map(dir)?);
    }
    if let Some(tape) = &bound.replay {
        validate_actions_in_map(&tape.events, &inner.known_action_names())?;
    }
    if let Some(warning) = &bound.warning {
        eprintln!("WARNING {warning}");
    }
    inner.apply_bound_tape(bound);
    inner.push_log(format!("control listening on 127.0.0.1:{}", addr.port()));

    let shutdown = Arc::new(AtomicBool::new(false));
    let stopped = Arc::new(AtomicBool::new(false));
    let flags = SimFlags {
        shutdown: Arc::clone(&shutdown),
        stopped: Arc::clone(&stopped),
    };
    let reloads: ReloadQueue = Arc::new(Mutex::new(Vec::new()));
    let (sim, sim_thread) = start_sim(inner, Arc::clone(&reloads), flags)?;

    let accept_flag = Arc::clone(&shutdown);
    let accept_stopped = Arc::clone(&stopped);
    let accept_sim = sim.clone();
    let accept_reloads = Arc::clone(&reloads);
    let accept_token = token.clone();
    let accept_play_id = play_id.clone();
    let accept_play_dir = play_dir.clone();
    let accept = thread::Builder::new()
        .name("gs-player-accept".into())
        .spawn(move || {
            accept_loop(
                listener,
                accept_sim,
                accept_reloads,
                accept_flag,
                accept_stopped,
                accept_token,
                accept_play_id,
                accept_play_dir,
            )
        })
        .map_err(|e| Error::control(e.to_string()))?;

    Ok(ControlHandle {
        sim: Some(sim),
        sim_thread: Some(sim_thread),
        reloads,
        play_id,
        pid,
        play_dir,
        addr,
        token,
        player_json_path,
        shutdown,
        stopped,
        accept: Some(accept),
    })
}

impl ControlHandle {
    fn client(&self) -> Result<&SimClient, Error> {
        self.sim
            .as_ref()
            .ok_or_else(|| Error::control("simulate thread stopped"))
    }

    pub fn local_addr(&self) -> SocketAddr {
        self.addr
    }

    pub fn player_json_path(&self) -> Option<&Path> {
        self.player_json_path.as_deref()
    }

    pub fn status(&self) -> PlayStatus {
        self.client()
            .ok()
            .and_then(|c| c.ask(SimRequest::Status).ok())
            .unwrap_or_else(|| PlayStatus {
                play_id: self.play_id.clone(),
                pid: self.pid,
                paused: true,
                frame: 0,
                timescale: 1.0,
                alive: false,
            })
    }

    pub fn last_error(&self) -> Option<String> {
        self.client()
            .ok()
            .and_then(|c| c.ask(SimRequest::LastError).ok())
            .flatten()
    }

    pub fn is_stopped(&self) -> bool {
        self.stopped.load(Ordering::SeqCst)
    }

    pub fn exit_report(&self) -> Option<ExitReport> {
        self.client()
            .ok()
            .and_then(|c| c.ask(SimRequest::ExitReport).ok())
            .flatten()
    }

    /// Test hook: next `step()` pretends to have taken `ms` (no real sleep).
    pub fn inject_test_hang_ms(&self, ms: u64) {
        if let Ok(client) = self.client() {
            let _ = client.ask(|r| SimRequest::InjectHang(ms, r));
        }
    }

    /// Test hook: OOM guard sees at least this many bytes (no 2GB alloc).
    pub fn inject_memory_bytes(&self, bytes: u64) {
        if let Ok(client) = self.client() {
            let _ = client.ask(|r| SimRequest::InjectMemory(bytes, r));
        }
    }

    pub fn pause(&self) -> PlayStatus {
        self.client()
            .ok()
            .and_then(|c| c.ask(SimRequest::Pause).ok())
            .unwrap_or_else(|| self.status())
    }

    pub fn resume(&self) -> PlayStatus {
        self.client()
            .ok()
            .and_then(|c| c.ask(SimRequest::Resume).ok())
            .unwrap_or_else(|| self.status())
    }

    pub fn step_frames(&self, n: u32) -> Result<PlayStatus, Error> {
        self.client()?.ask(|r| SimRequest::Step(n, r))?
    }

    pub fn set_timescale(&self, t: f64) -> Result<PlayStatus, Error> {
        self.client()?.ask(|r| SimRequest::SetTimescale(t, r))?
    }

    /// Start writing `input.tape.jsonl` under the play directory.
    pub fn tape_record(&self) -> Result<Value, Error> {
        self.client()?
            .ask_rpc(SimRequest::StartRecord)
            .map_err(rpc_to_error)
    }

    /// Queue play-scoped action values for upcoming simulate steps.
    pub fn input_inject(&self, play_id: Option<&str>, actions: Value) -> Result<Value, Error> {
        let mut params = json!({ "actions": actions });
        if let Some(play_id) = play_id {
            params["play_id"] = json!(play_id);
        }
        let injects = parse_and_check_inject(&self.play_id, &params).map_err(rpc_to_error)?;
        self.client()?
            .ask_rpc(|r| SimRequest::InjectInput(injects, r))
            .map_err(rpc_to_error)
    }

    /// Queue a play-scoped hot reload. Applied after the current simulate frame.
    pub fn script_reload(
        &self,
        path: Option<&str>,
        source: Option<&str>,
        entity_id: Option<&str>,
    ) -> Result<Value, Error> {
        let mut params = json!({});
        if let Some(path) = path {
            params["path"] = json!(path);
        }
        if let Some(source) = source {
            params["source"] = json!(source);
        }
        if let Some(entity_id) = entity_id {
            params["entity_id"] = json!(entity_id);
        }
        queue_script_reload(&self.reloads, self.play_dir.as_deref(), &params).map_err(rpc_to_error)
    }

    pub fn obs_events(
        &self,
        play_id: &str,
        after_seq: u64,
        name: Option<&str>,
        limit: usize,
    ) -> Result<Value, Error> {
        let mut params = json!({
            "play_id": play_id,
            "after_seq": after_seq,
            "limit": limit,
        });
        if let Some(name) = name {
            params["name"] = json!(name);
        }
        self.client()?
            .ask_rpc(|r| SimRequest::ObsEvents(params, r))
            .map_err(rpc_to_error)
    }

    pub fn obs_screenshot(&self, play_id: Option<&str>) -> Result<Value, Error> {
        let params = match play_id {
            Some(id) => json!({ "play_id": id }),
            None => json!({}),
        };
        self.client()?
            .ask_rpc(|r| SimRequest::ObsScreenshot(params, r))
            .map_err(rpc_to_error)
    }

    pub fn judge_run_until_event(&self, params: Value) -> Result<Value, Error> {
        self.client()?
            .ask_rpc(|r| SimRequest::JudgeRunUntilEvent(params, r))
            .map_err(rpc_to_error)
    }

    pub fn judge_wait_event(&self, params: Value) -> Result<Value, Error> {
        self.client()?
            .ask_rpc(|r| SimRequest::JudgeWaitEvent(params, r))
            .map_err(rpc_to_error)
    }

    pub fn judge_assert_world(&self, params: Value) -> Result<Value, Error> {
        self.client()?
            .ask_rpc(|r| SimRequest::JudgeAssertWorld(params, r))
            .map_err(rpc_to_error)
    }

    pub fn judge_assert_perf(&self, params: Value) -> Result<Value, Error> {
        self.client()?
            .ask_rpc(|r| SimRequest::JudgeAssertPerf(params, r))
            .map_err(rpc_to_error)
    }

    pub fn judge_assert_screenshot(&self, params: Value) -> Result<Value, Error> {
        self.client()?
            .ask_rpc(|r| SimRequest::JudgeAssertScreenshot(params, r))
            .map_err(rpc_to_error)
    }

    pub fn stop(&self) -> ExitReport {
        self.stop_with(false)
    }

    pub fn stop_force(&self) -> ExitReport {
        self.stop_with(true)
    }

    fn stop_with(&self, force: bool) -> ExitReport {
        let report = self
            .client()
            .ok()
            .and_then(|c| c.ask(|r| SimRequest::Stop { force, reply: r }).ok())
            .unwrap_or_else(|| ExitReport {
                exit_code: if force { 1 } else { 0 },
                frames: 0,
                last_error: Some("simulate thread stopped".into()),
                log_tail: Vec::new(),
                event_trace_path: None,
                perf_summary: None,
                evidence_ok: true,
            });
        self.shutdown.store(true, Ordering::SeqCst);
        self.stopped.store(true, Ordering::SeqCst);
        let _ = TcpStream::connect(self.addr);
        report
    }

    /// 60Hz accumulator loop until [`Self::stop`]. Timescale only changes accumulation.
    pub fn run_until_stop(&self) -> Result<ExitReport, Error> {
        self.client()?.ask(|r| SimRequest::SetAutoRun(true, r))?;
        while !self.shutdown.load(Ordering::SeqCst) && !self.stopped.load(Ordering::SeqCst) {
            thread::sleep(Duration::from_millis(1));
        }
        // Give the control connection time to flush play.stop before we exit.
        thread::sleep(Duration::from_millis(50));
        Ok(self.stop())
    }
}

impl Drop for ControlHandle {
    fn drop(&mut self) {
        let _ = self.stop();
        if let Some(handle) = self.accept.take() {
            let _ = handle.join();
        }
        drop(self.sim.take());
        if let Some(handle) = self.sim_thread.take() {
            let _ = handle.join();
        }
        if let Some(path) = &self.player_json_path {
            let _ = fs::remove_file(path);
        }
    }
}

/// Best-effort `exit_report.json` if the play process panics (GS-EC-27).
pub fn install_panic_exit_report() {
    let previous = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |info| {
        if let Some(dir) = CRASH_REPORT_DIR.get() {
            let report = ExitReport {
                exit_code: 1,
                frames: 0,
                last_error: Some(format!("panic: {info}")),
                log_tail: Vec::new(),
                event_trace_path: None,
                perf_summary: None,
                evidence_ok: true,
            };
            let _ = write_exit_report_file(&dir.join("exit_report.json"), &report);
        }
        previous(info);
    }));
}

#[allow(clippy::too_many_arguments)]
fn accept_loop(
    listener: TcpListener,
    sim: SimClient,
    reloads: ReloadQueue,
    shutdown: Arc<AtomicBool>,
    stopped: Arc<AtomicBool>,
    token: String,
    play_id: String,
    play_dir: Option<PathBuf>,
) {
    while !shutdown.load(Ordering::SeqCst) {
        match listener.accept() {
            Ok((stream, _)) => {
                if shutdown.load(Ordering::SeqCst) {
                    break;
                }
                let sim = sim.clone();
                let reloads = Arc::clone(&reloads);
                let shutdown = Arc::clone(&shutdown);
                let stopped = Arc::clone(&stopped);
                let token = token.clone();
                let play_id = play_id.clone();
                let play_dir = play_dir.clone();
                let _ = thread::Builder::new()
                    .name("gs-player-conn".into())
                    .spawn(move || {
                        handle_connection(
                            stream, sim, reloads, shutdown, stopped, token, play_id, play_dir,
                        )
                    });
            }
            Err(err) if err.kind() == io::ErrorKind::WouldBlock => {
                thread::sleep(Duration::from_millis(10));
            }
            Err(_) => {
                if shutdown.load(Ordering::SeqCst) {
                    break;
                }
                thread::sleep(Duration::from_millis(20));
            }
        }
    }
}

#[allow(clippy::too_many_arguments)]
fn handle_connection(
    stream: TcpStream,
    sim: SimClient,
    reloads: ReloadQueue,
    shutdown: Arc<AtomicBool>,
    stopped: Arc<AtomicBool>,
    token: String,
    play_id: String,
    play_dir: Option<PathBuf>,
) {
    // Windows: sockets accepted from a non-blocking listener inherit FIONBIO.
    // Leave that on and the next read after hello returns WouldBlock → 10053.
    let _ = stream.set_nonblocking(false);
    let _ = stream.set_nodelay(true);
    let _ = stream.set_read_timeout(Some(Duration::from_secs(IDLE_TIMEOUT_SECS)));
    let _ = stream.set_write_timeout(Some(CONTROL_WRITE_TIMEOUT));
    let Ok(mut writer) = stream.try_clone() else {
        return;
    };
    let mut reader = BufReader::new(stream);
    let mut authed = false;
    let ctx = ConnCtx {
        sim,
        reloads,
        play_id,
        play_dir,
        stopped: Arc::clone(&stopped),
    };

    while !shutdown.load(Ordering::SeqCst) {
        let line = match read_ndjson_line(&mut reader) {
            Ok(line) => line,
            Err(err) if is_idle_io(&err) => {
                if shutdown.load(Ordering::SeqCst) || stopped.load(Ordering::SeqCst) {
                    break;
                }
                continue;
            }
            Err(ProtocolError::Eof) => break,
            Err(err) => {
                if let Some(rpc) = RpcError::from_protocol(&err) {
                    let _ = write_ndjson_line(&mut writer, &Response::err(0_i64, rpc));
                    let _ = writer.flush();
                }
                break;
            }
        };
        let request = match decode_message(&line) {
            Ok(Message::Request(request)) => request,
            Ok(_) => continue,
            Err(err) => {
                let rpc = RpcError::from_protocol(&err)
                    .unwrap_or_else(|| RpcError::proto(err.to_string()));
                let _ = write_ndjson_line(&mut writer, &Response::err(0_i64, rpc));
                let _ = writer.flush();
                break;
            }
        };
        let stopping = request.method == "play.stop";
        let id = request.id.clone();
        let response = match catch_unwind(AssertUnwindSafe(|| {
            dispatch_control(&ctx, &mut authed, &token, request)
        })) {
            Ok(response) => response,
            Err(_) => Response::err(
                id,
                RpcError::with_data(APP, "control handler panicked", ErrorData::new("E_PLAYER")),
            ),
        };
        let _ = write_ndjson_line(&mut writer, &response);
        let _ = writer.flush();
        if stopping {
            stopped.store(true, Ordering::SeqCst);
            shutdown.store(true, Ordering::SeqCst);
            break;
        }
        if matches!(response.payload, ResponsePayload::Error(_)) && !authed {
            break;
        }
        if stopped.load(Ordering::SeqCst) {
            shutdown.store(true, Ordering::SeqCst);
            break;
        }
    }
    let _ = writer.flush();
    let _ = writer.shutdown(Shutdown::Write);
}

struct ConnCtx {
    sim: SimClient,
    reloads: ReloadQueue,
    play_id: String,
    play_dir: Option<PathBuf>,
    stopped: Arc<AtomicBool>,
}

fn dispatch_control(
    ctx: &ConnCtx,
    authed: &mut bool,
    expected_token: &str,
    request: Request,
) -> Response {
    let id = request.id;
    let method = request.method;
    let params = request.params;

    if !*authed {
        if method != "session.hello" {
            return Response::err(id, unauthorized("first RPC must be session.hello"));
        }
        return match perform_hello(&params, expected_token) {
            Ok(result) => {
                *authed = true;
                Response::ok(id, result)
            }
            Err(err) => Response::err(id, err),
        };
    }

    let result = match method.as_str() {
        "play.status" => ctx
            .sim
            .ask(SimRequest::Status)
            .map(|s| status_json(&s))
            .map_err(control_rpc),
        "play.pause" => ctx
            .sim
            .ask(SimRequest::Pause)
            .map(|s| status_json(&s))
            .map_err(control_rpc),
        "play.resume" => ctx
            .sim
            .ask(SimRequest::Resume)
            .map(|s| status_json(&s))
            .map_err(control_rpc),
        "play.step_frames" => step_params(&params).and_then(|n| {
            ctx.sim
                .ask(|r| SimRequest::Step(n, r))
                .map_err(control_rpc)
                .and_then(|r| r.map(|s| status_json(&s)).map_err(control_rpc))
        }),
        "play.set_timescale" => timescale_params(&params).and_then(|t| {
            ctx.sim
                .ask(|r| SimRequest::SetTimescale(t, r))
                .map_err(control_rpc)
                .and_then(|r| r.map(|s| status_json(&s)).map_err(control_rpc))
        }),
        "tape.record" => ctx.sim.ask_rpc(SimRequest::StartRecord),
        "input.inject" => parse_and_check_inject(&ctx.play_id, &params)
            .and_then(|actions| ctx.sim.ask_rpc(|r| SimRequest::InjectInput(actions, r))),
        "play.stop" => {
            let force = params
                .get("force")
                .and_then(Value::as_bool)
                .unwrap_or(false);
            ctx.sim
                .ask(|r| SimRequest::Stop { force, reply: r })
                .map_err(control_rpc)
                .and_then(|report| {
                    ctx.stopped.store(true, Ordering::SeqCst);
                    serde_json::to_value(&report).map_err(|e| {
                        RpcError::with_data(APP, e.to_string(), ErrorData::new("E_IO"))
                    })
                })
        }
        "script.reload" => {
            let offered = params.get("play_id").and_then(Value::as_str);
            check_offered_play_id(&ctx.play_id, offered)
                .and_then(|_| queue_script_reload(&ctx.reloads, ctx.play_dir.as_deref(), &params))
        }
        "obs.events" => ctx.sim.ask_rpc(|r| SimRequest::ObsEvents(params, r)),
        "obs.world_dump" => ctx.sim.ask_rpc(|r| SimRequest::ObsWorldDump(params, r)),
        "obs.logs_tail" => ctx.sim.ask_rpc(|r| SimRequest::ObsLogsTail(params, r)),
        "obs.perf" => ctx.sim.ask_rpc(|r| SimRequest::ObsPerf(params, r)),
        "obs.screenshot" => ctx.sim.ask_rpc(|r| SimRequest::ObsScreenshot(params, r)),
        "judge.run_until_event" => ctx
            .sim
            .ask_rpc(|r| SimRequest::JudgeRunUntilEvent(params, r)),
        "judge.wait_event" => ctx.sim.ask_rpc(|r| SimRequest::JudgeWaitEvent(params, r)),
        "judge.assert_world" => ctx.sim.ask_rpc(|r| SimRequest::JudgeAssertWorld(params, r)),
        "judge.assert_perf" => ctx.sim.ask_rpc(|r| SimRequest::JudgeAssertPerf(params, r)),
        "judge.assert_screenshot" => ctx
            .sim
            .ask_rpc(|r| SimRequest::JudgeAssertScreenshot(params, r)),
        other => Err(RpcError::new(
            METHOD_NOT_FOUND,
            format!("method not found: {other}"),
        )),
    };
    match result {
        Ok(value) => Response::ok(id, value),
        Err(err) => Response::err(id, err),
    }
}

fn queue_script_reload(
    queue: &ReloadQueue,
    play_dir: Option<&Path>,
    params: &Value,
) -> Result<Value, RpcError> {
    let job = materialize_reload(play_dir, parse_reload_job(params)?)?;
    queue_reload(queue, job);
    Ok(json!({ "ok": true, "queued": true }))
}

fn perform_hello(params: &Value, expected: &str) -> Result<Value, RpcError> {
    let offered = params.get("token").and_then(Value::as_str).unwrap_or("");
    if expected.is_empty() || !tokens_eq(offered, expected) {
        return Err(unauthorized("invalid or missing token"));
    }
    if let Some(ver) = params.get("protocol_ver").and_then(Value::as_str) {
        if ver != PROTOCOL_VER {
            return Err(invalid_params(format!("unsupported protocol_ver {ver}")));
        }
    }
    Ok(json!({
        "ok": true,
        "protocol_ver": PROTOCOL_VER,
        "principal": "editor",
    }))
}

fn step_params(params: &Value) -> Result<u32, RpcError> {
    match params.get("n") {
        None | Some(Value::Null) => Ok(1),
        Some(v) => v
            .as_u64()
            .and_then(|n| u32::try_from(n).ok())
            .ok_or_else(|| invalid_params("n must be a u32")),
    }
}

fn parse_and_check_inject(
    expected_play_id: &str,
    params: &Value,
) -> Result<Vec<crate::input::PendingInject>, RpcError> {
    let offered = params.get("play_id").and_then(Value::as_str);
    check_offered_play_id(expected_play_id, offered)?;
    parse_inject_actions(params).map_err(invalid_params)
}

fn timescale_params(params: &Value) -> Result<f64, RpcError> {
    params
        .get("timescale")
        .or_else(|| params.get("value"))
        .and_then(Value::as_f64)
        .ok_or_else(|| invalid_params("timescale must be a number"))
}

fn status_json(status: &PlayStatus) -> Value {
    json!({
        "play_id": status.play_id,
        "pid": status.pid,
        "paused": status.paused,
        "frame": status.frame,
        "timescale": status.timescale,
        "alive": status.alive,
    })
}

pub(crate) fn control_rpc(err: Error) -> RpcError {
    let msg = err.to_string();
    if msg.contains("SCRIPT_HANG") {
        RpcError::with_data(APP, msg, ErrorData::new("SCRIPT_HANG"))
    } else if msg.contains("OOM_GUARD") {
        RpcError::with_data(APP, msg, ErrorData::new("OOM_GUARD"))
    } else if msg.contains("exceeds cap") || msg.contains("outside") {
        invalid_params(msg)
    } else {
        RpcError::with_data(APP, msg, ErrorData::new("E_PLAYER"))
    }
}

fn rpc_to_error(err: RpcError) -> Error {
    match &err.data {
        Some(ErrorData { app_code, .. }) => Error::control(format!("{app_code}: {}", err.message)),
        None => Error::control(err.message),
    }
}

fn unauthorized(message: impl Into<String>) -> RpcError {
    RpcError::with_data(UNAUTHORIZED, message, ErrorData::new("E_UNAUTHORIZED"))
}

pub(crate) fn invalid_params(message: impl Into<String>) -> RpcError {
    RpcError::with_data(INVALID_PARAMS, message, ErrorData::new("E_VALIDATION"))
}

pub(crate) fn not_found(message: impl Into<String>) -> RpcError {
    RpcError::with_data(APP, message, ErrorData::new("E_NOT_FOUND"))
}

pub(crate) fn no_gpu_error() -> RpcError {
    RpcError::with_data(
        APP,
        "no-render mode: screenshot requires a GPU",
        ErrorData::new("no_gpu"),
    )
}

pub(crate) fn play_id_mismatch() -> RpcError {
    RpcError::with_data(
        APP,
        "play_id does not match the running play",
        ErrorData::new("E_NOT_FOUND"),
    )
}

pub(crate) fn obs_io(err: Error) -> RpcError {
    RpcError::with_data(APP, err.to_string(), ErrorData::new("E_IO"))
}

fn is_idle_io(err: &ProtocolError) -> bool {
    match err {
        ProtocolError::Io(io_err) => matches!(
            io_err.kind(),
            io::ErrorKind::WouldBlock | io::ErrorKind::TimedOut | io::ErrorKind::Interrupted
        ),
        _ => false,
    }
}

fn tokens_eq(a: &str, b: &str) -> bool {
    if a.len() != b.len() {
        return false;
    }
    a.bytes()
        .zip(b.bytes())
        .fold(0u8, |acc, (x, y)| acc | (x ^ y))
        == 0
}

fn generate_token() -> String {
    format!("{}{}", Ulid::new(), Ulid::new())
}

pub(crate) fn write_exit_report_file(path: &Path, report: &ExitReport) -> Result<(), Error> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| Error::io(parent, e))?;
    }
    let bytes = serde_json::to_vec_pretty(report).map_err(|e| Error::json(path, e))?;
    let tmp = path.with_extension("json.tmp");
    fs::write(&tmp, bytes).map_err(|e| Error::io(&tmp, e))?;
    if path.exists() {
        fs::remove_file(path).map_err(|e| Error::io(path, e))?;
    }
    fs::rename(&tmp, path).map_err(|e| Error::io(path, e))?;
    Ok(())
}

/// SHA-256-free helper used by the binary to print a token-free start line.
pub fn control_ready_line(play_id: &str, port: u16, pid: u32) -> String {
    format!("OK {play_id} control port={port} pid={pid}")
}

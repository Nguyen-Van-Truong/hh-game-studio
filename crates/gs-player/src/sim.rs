//! Dedicated simulate thread. Owns `World` + `ScriptHost` (`!Send`) +
//! `PhysicsHost` for the life of the play. Control threads only send
//! requests and wait for replies.

use std::collections::{BTreeMap, BTreeSet, VecDeque};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{self, Receiver, RecvTimeoutError, Sender};
use std::sync::{Arc, Mutex};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

use gs_protocol::{ErrorData, RpcError, APP};
use gs_render2d::{render_offscreen_png, AtlasCpu, RenderSnapshot};
use gs_runtime_core::{
    build_render_snapshot, format_play_id, parse_play_id, InputFrame, PhysicsHost, ScriptHost,
    World, FIXED_DT,
};
use serde_json::{json, Value};
use ulid::Ulid;

use crate::control::{
    control_rpc, invalid_params, no_gpu_error, not_found, obs_io, play_id_mismatch,
    write_exit_report_file, ExitReport, PlayStatus, LOG_TAIL_MAX, MAX_STEP_FRAMES, TIMESCALE_MAX,
    TIMESCALE_MIN,
};
use crate::error::Error;
use crate::events::{
    self, EventTrace, OBS_EVENTS_DEFAULT_LIMIT, OBS_EVENTS_MAX_LIMIT, OBS_LOG_TAIL_MAX,
};
use crate::guard::{
    memory_guard_trip, process_rss_bytes, watchdog_trip, EXIT_OOM_GUARD, EXIT_SCRIPT_HANG,
    RAM_WARN_BYTES,
};
use crate::input::{advance_injects, compose_input, PendingInject};
use crate::judge;
use crate::script_play::{make_physics_host, step_world, world_needs_host};
use crate::tape::{
    append_frame_actions, apply_tape_to_frame, write_header, LoadedTape, TapeHeader,
    INPUT_TAPE_FILE,
};

const MAX_STEPS_PER_DISPLAY: u32 = 8;

#[derive(Clone)]
pub(crate) struct SimFlags {
    pub shutdown: Arc<AtomicBool>,
    pub stopped: Arc<AtomicBool>,
}

pub(crate) type ReloadQueue = Arc<Mutex<Vec<QueuedReload>>>;

#[derive(Clone, Debug)]
pub(crate) struct QueuedReload {
    pub entity_id: Option<u64>,
    pub path: Option<String>,
    pub source: Option<String>,
}

pub(crate) enum SimRequest {
    Status(Sender<PlayStatus>),
    LastError(Sender<Option<String>>),
    ExitReport(Sender<Option<ExitReport>>),
    InjectHang(u64, Sender<()>),
    InjectMemory(u64, Sender<()>),
    Pause(Sender<PlayStatus>),
    Resume(Sender<PlayStatus>),
    Step(u32, Sender<Result<PlayStatus, Error>>),
    SetTimescale(f64, Sender<Result<PlayStatus, Error>>),
    InjectInput(Vec<PendingInject>, Sender<Result<Value, RpcError>>),
    ObsEvents(Value, Sender<Result<Value, RpcError>>),
    ObsWorldDump(Value, Sender<Result<Value, RpcError>>),
    ObsLogsTail(Value, Sender<Result<Value, RpcError>>),
    ObsPerf(Value, Sender<Result<Value, RpcError>>),
    ObsScreenshot(Value, Sender<Result<Value, RpcError>>),
    JudgeRunUntilEvent(Value, Sender<Result<Value, RpcError>>),
    JudgeWaitEvent(Value, Sender<Result<Value, RpcError>>),
    JudgeAssertWorld(Value, Sender<Result<Value, RpcError>>),
    JudgeAssertPerf(Value, Sender<Result<Value, RpcError>>),
    JudgeAssertScreenshot(Value, Sender<Result<Value, RpcError>>),
    Stop {
        force: bool,
        reply: Sender<ExitReport>,
    },
    SetAutoRun(bool, Sender<()>),
    StartRecord(Sender<Result<Value, RpcError>>),
}

pub(crate) struct SimClient {
    tx: Sender<SimRequest>,
}

impl Clone for SimClient {
    fn clone(&self) -> Self {
        Self {
            tx: self.tx.clone(),
        }
    }
}

impl SimClient {
    pub(crate) fn ask<T>(&self, build: impl FnOnce(Sender<T>) -> SimRequest) -> Result<T, Error> {
        let (tx, rx) = mpsc::channel();
        self.tx
            .send(build(tx))
            .map_err(|_| Error::control("simulate thread stopped"))?;
        rx.recv()
            .map_err(|_| Error::control("simulate thread stopped"))
    }

    pub(crate) fn ask_rpc(
        &self,
        build: impl FnOnce(Sender<Result<Value, RpcError>>) -> SimRequest,
    ) -> Result<Value, RpcError> {
        match self.ask(build) {
            Ok(result) => result,
            Err(err) => Err(RpcError::with_data(
                APP,
                err.to_string(),
                ErrorData::new("E_PLAYER"),
            )),
        }
    }
}

pub(crate) struct PlayInner {
    world: World,
    play_id: String,
    pid: u32,
    paused: bool,
    timescale: f64,
    alive: bool,
    stopped: bool,
    last_error: Option<String>,
    log_tail: VecDeque<String>,
    exit_report: Option<ExitReport>,
    play_dir: Option<PathBuf>,
    event_trace: EventTrace,
    last_snapshot: Option<RenderSnapshot>,
    perf_last_step: Option<Instant>,
    last_frame_ms: Option<u64>,
    fps_est: Option<f64>,
    no_render: bool,
    test_hang_ms: Option<u64>,
    injected_memory_bytes: Option<u64>,
    memory_guard_bytes: u64,
    ram_warned: bool,
    base_input: InputFrame,
    pending_injects: Vec<PendingInject>,
    replay: Option<LoadedTape>,
    record_path: Option<PathBuf>,
    record_header: Option<TapeHeader>,
    last_recorded: BTreeMap<String, f32>,
    evidence_ok: bool,
    atlas: AtlasCpu,
}

impl PlayInner {
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn new(
        world: World,
        play_id: String,
        pid: u32,
        play_dir: Option<PathBuf>,
        event_trace: EventTrace,
        no_render: bool,
        test_hang_ms: Option<u64>,
        injected_memory_bytes: Option<u64>,
        memory_guard_bytes: u64,
    ) -> Self {
        Self {
            world,
            play_id,
            pid,
            paused: test_hang_ms.is_some(),
            timescale: 1.0,
            alive: true,
            stopped: false,
            last_error: None,
            log_tail: VecDeque::new(),
            exit_report: None,
            play_dir,
            event_trace,
            last_snapshot: None,
            perf_last_step: None,
            last_frame_ms: None,
            fps_est: None,
            no_render,
            test_hang_ms,
            injected_memory_bytes,
            memory_guard_bytes,
            ram_warned: false,
            base_input: InputFrame::default(),
            pending_injects: Vec::new(),
            replay: None,
            record_path: None,
            record_header: None,
            last_recorded: BTreeMap::new(),
            evidence_ok: true,
            atlas: crate::atlas::solid_white_atlas(),
        }
    }

    pub(crate) fn apply_bound_tape(&mut self, bound: crate::tape::BoundTape) {
        if let Some(warning) = bound.warning {
            self.push_log(warning);
        }
        self.evidence_ok = bound.evidence_ok;
        self.replay = bound.replay;
        self.record_path = bound.record_path;
        self.record_header = bound.header;
    }

    pub(crate) fn set_base_input(&mut self, input: InputFrame) {
        self.base_input = input;
    }

    pub(crate) fn known_action_names(&self) -> BTreeSet<String> {
        self.base_input.actions.keys().cloned().collect()
    }

    pub(crate) fn push_log(&mut self, line: impl Into<String>) {
        let line = line.into();
        if self.log_tail.len() == LOG_TAIL_MAX {
            self.log_tail.pop_front();
        }
        self.log_tail.push_back(line);
    }

    fn status(&self) -> PlayStatus {
        PlayStatus {
            play_id: self.play_id.clone(),
            pid: self.pid,
            paused: self.paused,
            frame: self.world.frame,
            timescale: self.timescale,
            alive: self.alive && !self.stopped,
        }
    }

    fn observed_memory_bytes(&self) -> u64 {
        let rss = process_rss_bytes().unwrap_or(0);
        self.injected_memory_bytes.unwrap_or(0).max(rss)
    }

    fn check_memory_guard(&mut self) -> Result<(), Error> {
        let used = self.observed_memory_bytes();
        if used > RAM_WARN_BYTES && !self.ram_warned {
            self.ram_warned = true;
            self.push_log(format!("memory warning: observed {used} bytes exceeds 1GB"));
        }
        if memory_guard_trip(used, self.memory_guard_bytes) {
            return Err(self.trip_oom());
        }
        Ok(())
    }

    fn write_hang_dump(&mut self) {
        let Some(dir) = self.play_dir.clone() else {
            return;
        };
        let dump = events::world_dump_value(&self.world);
        let _ = events::write_artifact(&dir.join("hang_dump.json"), &dump);
    }

    fn persist_exit_report(&self, report: &ExitReport) {
        if let Some(dir) = &self.play_dir {
            let _ = write_exit_report_file(&dir.join("exit_report.json"), report);
        }
    }

    fn trip_watchdog(&mut self) -> Error {
        self.last_error = Some("SCRIPT_HANG".into());
        self.push_log("watchdog: simulate frame exceeded 2000ms (SCRIPT_HANG)");
        self.write_hang_dump();
        let report = self.build_exit_report(EXIT_SCRIPT_HANG);
        self.persist_exit_report(&report);
        Error::control("SCRIPT_HANG")
    }

    fn trip_oom(&mut self) -> Error {
        self.last_error = Some("OOM_GUARD".into());
        self.push_log("oom guard: observed memory exceeds 2GB (OOM_GUARD)");
        self.write_hang_dump();
        let report = self.build_exit_report(EXIT_OOM_GUARD);
        self.persist_exit_report(&report);
        Error::control("OOM_GUARD")
    }

    fn step_one(
        &mut self,
        host: &mut Option<ScriptHost>,
        physics: &mut PhysicsHost,
        reloads: &ReloadQueue,
        audio: &mut crate::audio::AudioEngine,
    ) -> Result<RenderSnapshot, Error> {
        self.apply_pending_reloads(host, reloads);
        self.check_memory_guard()?;
        let frame_idx = self.world.frame;
        let input = if let Some(tape) = &self.replay {
            apply_tape_to_frame(&self.base_input, &tape.events, frame_idx)
        } else {
            compose_input(&self.base_input, &self.pending_injects)
        };
        if let Some(path) = &self.record_path {
            append_frame_actions(path, frame_idx, &input, &mut self.last_recorded)?;
        }
        let fake_ms = self.test_hang_ms.take();
        let frame_start = Instant::now();
        let result = step_world(&mut self.world, &input, host.as_mut(), Some(physics));
        audio.drain(&mut self.world);
        advance_injects(&mut self.pending_injects);
        let elapsed_ms = fake_ms.unwrap_or_else(|| instant_ms(frame_start));
        self.last_frame_ms = Some(elapsed_ms);
        if watchdog_trip(elapsed_ms) {
            return Err(self.trip_watchdog());
        }
        match result {
            Ok(snapshot) => {
                self.last_snapshot = Some(snapshot.clone());
                self.event_trace.drain_world_events(&mut self.world)?;
                self.apply_pending_reloads(host, reloads);
                Ok(snapshot)
            }
            Err(err) => {
                let msg = err.to_string();
                self.last_error = Some(msg.clone());
                self.push_log(msg);
                Err(Error::from(err))
            }
        }
    }

    fn step_n(
        &mut self,
        n: u32,
        host: &mut Option<ScriptHost>,
        physics: &mut PhysicsHost,
        reloads: &ReloadQueue,
        audio: &mut crate::audio::AudioEngine,
    ) -> Result<PlayStatus, Error> {
        if n > MAX_STEP_FRAMES {
            return Err(Error::control(format!(
                "step_frames n={n} exceeds cap {MAX_STEP_FRAMES}"
            )));
        }
        if self.stopped {
            return Err(Error::control("player is stopped"));
        }
        if !self.paused {
            self.paused = true;
        }
        let batch_start = Instant::now();
        for _ in 0..n {
            self.step_one(host, physics, reloads, audio)?;
        }
        self.update_fps_est(n, batch_start);
        Ok(self.status())
    }

    fn update_fps_est(&mut self, frames: u32, started: Instant) {
        let elapsed = started.elapsed().as_secs_f64();
        if elapsed > 0.0 && frames > 0 {
            self.fps_est = Some(f64::from(frames) / elapsed);
        }
        self.perf_last_step = Some(Instant::now());
    }

    fn ensure_snapshot(&mut self) -> Result<RenderSnapshot, Error> {
        if let Some(snapshot) = &self.last_snapshot {
            return Ok(snapshot.clone());
        }
        let snapshot = build_render_snapshot(&mut self.world)?;
        self.last_snapshot = Some(snapshot.clone());
        Ok(snapshot)
    }

    fn artifact_dir(&self) -> Option<&Path> {
        self.play_dir.as_deref()
    }

    fn check_play_id(&self, offered: Option<&str>) -> Result<(), RpcError> {
        match offered {
            None | Some("") => Ok(()),
            Some(id) if id == self.play_id => Ok(()),
            Some(_) => Err(play_id_mismatch()),
        }
    }

    fn queue_injects(&mut self, actions: Vec<PendingInject>) -> Result<Value, RpcError> {
        if self.stopped {
            return Err(crate::control::control_rpc(Error::control(
                "player is stopped",
            )));
        }
        self.pending_injects.extend(actions);
        Ok(json!({ "ok": true }))
    }

    fn set_timescale(&mut self, t: f64) -> Result<PlayStatus, Error> {
        if !(TIMESCALE_MIN..=TIMESCALE_MAX).contains(&t) {
            return Err(Error::control(format!(
                "timescale {t} is outside {TIMESCALE_MIN}..{TIMESCALE_MAX}"
            )));
        }
        self.timescale = t;
        Ok(self.status())
    }

    fn snapshot_exit_report(&mut self, exit_code: i32) -> ExitReport {
        if let Some(existing) = &self.exit_report {
            return existing.clone();
        }
        let report = ExitReport {
            exit_code,
            frames: self.world.frame,
            last_error: self.last_error.clone(),
            log_tail: self.log_tail.iter().cloned().collect(),
            event_trace_path: self
                .event_trace
                .events_path()
                .map(|p| p.to_string_lossy().into_owned()),
            perf_summary: self.fps_est.map(|fps| json!({ "fps_est": fps })),
            evidence_ok: self.evidence_ok,
        };
        self.exit_report = Some(report.clone());
        report
    }

    fn mark_stopped(&mut self, flags: &SimFlags) {
        self.stopped = true;
        self.alive = false;
        flags.stopped.store(true, Ordering::SeqCst);
    }

    fn build_exit_report(&mut self, exit_code: i32) -> ExitReport {
        let report = self.snapshot_exit_report(exit_code);
        self.stopped = true;
        self.alive = false;
        report
    }

    fn apply_pending_reloads(&mut self, host: &mut Option<ScriptHost>, reloads: &ReloadQueue) {
        let jobs = {
            let mut guard = reloads.lock().unwrap_or_else(|err| err.into_inner());
            std::mem::take(&mut *guard)
        };
        for job in jobs {
            self.apply_reload(host, job);
        }
    }

    fn apply_reload(&mut self, host: &mut Option<ScriptHost>, job: QueuedReload) {
        let targets = reload_targets(&self.world, &job);
        if targets.is_empty() {
            self.push_log("script.reload: no matching script entity");
            return;
        }
        for entity_id in targets {
            let previous = self.world.attached_scripts.get(&entity_id).cloned();
            if let Some(source) = job.source.as_ref() {
                self.world.attach_script(entity_id, source.clone());
            } else if previous.is_none() {
                self.push_log(format!(
                    "script.reload: no source attached for {}",
                    format_play_id(entity_id)
                ));
                continue;
            }
            if host.is_none() {
                match crate::script_play::make_script_host() {
                    Ok(created) => *host = Some(created),
                    Err(err) => {
                        if let Some(prev) = previous {
                            self.world.attach_script(entity_id, prev);
                        }
                        self.push_log(format!("script.reload: host unavailable: {err}"));
                        continue;
                    }
                }
            }
            let Some(host) = host.as_mut() else {
                continue;
            };
            if let Err(err) = host.reload(&mut self.world, entity_id) {
                if let Some(prev) = previous {
                    self.world.attach_script(entity_id, prev);
                }
                let msg = format!(
                    "script.reload failed for {}: {err}",
                    format_play_id(entity_id)
                );
                self.push_log(msg);
            }
        }
    }

    fn start_record(&mut self) -> Result<Value, RpcError> {
        let dir = self.play_dir.as_ref().ok_or_else(|| {
            crate::control::not_found("tape.record requires a snapshot play directory")
        })?;
        if let Some(existing) = &self.record_path {
            return Ok(json!({ "ok": true, "path": existing.to_string_lossy() }));
        }
        let header = self.record_header.clone().ok_or_else(|| {
            crate::control::invalid_params("tape.record requires a verified snapshot header")
        })?;
        let path = dir.join(INPUT_TAPE_FILE);
        write_header(&path, &header).map_err(crate::control::obs_io)?;
        self.record_path = Some(path.clone());
        Ok(json!({ "ok": true, "path": path.to_string_lossy() }))
    }
}

fn reload_targets(world: &World, job: &QueuedReload) -> Vec<u64> {
    if let Some(id) = job.entity_id {
        return vec![id];
    }
    if let Some(path) = &job.path {
        let want = path.replace('\\', "/");
        let hits: Vec<u64> = world
            .script_bindings
            .iter()
            .filter(|(_, binding)| binding.file.replace('\\', "/") == want)
            .map(|(id, _)| *id)
            .collect();
        if !hits.is_empty() {
            return hits;
        }
    }
    Vec::new()
}

/// Spawn the simulate thread. `ScriptHost` and `PhysicsHost` are constructed
/// on that thread (`ScriptHost` is `!Send`; Rapier stays with the same owner).
pub(crate) fn start_sim(
    mut inner: PlayInner,
    reloads: ReloadQueue,
    flags: SimFlags,
) -> Result<(SimClient, JoinHandle<()>), Error> {
    if let Some(dir) = inner.play_dir.clone() {
        inner.atlas = crate::atlas::bind_play_atlas(&mut inner.world, &dir)?;
    }
    let (tx, rx) = mpsc::channel();
    let (ready_tx, ready_rx) = mpsc::channel();
    let handle = thread::Builder::new()
        .name("gs-player-sim".into())
        .spawn(move || {
            let host = if world_needs_host(&inner.world) {
                match crate::script_play::make_script_host() {
                    Ok(host) => Some(host),
                    Err(err) => {
                        let _ = ready_tx.send(Err(err));
                        return;
                    }
                }
            } else {
                None
            };
            let physics = make_physics_host();
            let _ = ready_tx.send(Ok(()));
            let audio = crate::audio::AudioEngine::headless(inner.play_dir.as_deref());
            sim_loop(inner, host, physics, audio, rx, reloads, flags);
        })
        .map_err(|e| Error::control(e.to_string()))?;
    ready_rx
        .recv()
        .map_err(|_| Error::control("simulate thread stopped"))??;
    Ok((SimClient { tx }, handle))
}

fn sim_loop(
    mut inner: PlayInner,
    mut host: Option<ScriptHost>,
    mut physics: PhysicsHost,
    mut audio: crate::audio::AudioEngine,
    rx: Receiver<SimRequest>,
    reloads: ReloadQueue,
    flags: SimFlags,
) {
    let mut auto_run = false;
    let mut acc = 0.0;
    let mut last = Instant::now();
    loop {
        let block = !auto_run || inner.paused || inner.stopped;
        let request = if block {
            match rx.recv() {
                Ok(request) => Some(request),
                Err(_) => break,
            }
        } else {
            match rx.recv_timeout(Duration::from_millis(1)) {
                Ok(request) => Some(request),
                Err(RecvTimeoutError::Timeout) => None,
                Err(RecvTimeoutError::Disconnected) => break,
            }
        };
        if let Some(request) = request {
            handle_request(
                &mut inner,
                &mut host,
                &mut physics,
                &mut audio,
                &reloads,
                &flags,
                &mut auto_run,
                &mut last,
                &mut acc,
                request,
            );
            continue;
        }
        if auto_run && !inner.paused && !inner.stopped {
            display_tick(
                &mut inner,
                &mut host,
                &mut physics,
                &mut audio,
                &reloads,
                &mut acc,
                &mut last,
            );
        }
    }
}

#[allow(clippy::too_many_arguments)]
fn handle_request(
    inner: &mut PlayInner,
    host: &mut Option<ScriptHost>,
    physics: &mut PhysicsHost,
    audio: &mut crate::audio::AudioEngine,
    reloads: &ReloadQueue,
    flags: &SimFlags,
    auto_run: &mut bool,
    last: &mut Instant,
    acc: &mut f64,
    request: SimRequest,
) {
    match request {
        SimRequest::Status(reply) => {
            let _ = reply.send(inner.status());
        }
        SimRequest::LastError(reply) => {
            let _ = reply.send(inner.last_error.clone());
        }
        SimRequest::ExitReport(reply) => {
            let _ = reply.send(inner.exit_report.clone());
        }
        SimRequest::InjectHang(ms, reply) => {
            inner.test_hang_ms = Some(ms);
            let _ = reply.send(());
        }
        SimRequest::InjectMemory(bytes, reply) => {
            inner.injected_memory_bytes = Some(bytes);
            let _ = reply.send(());
        }
        SimRequest::Pause(reply) => {
            inner.paused = true;
            *acc = 0.0;
            let _ = reply.send(inner.status());
        }
        SimRequest::Resume(reply) => {
            inner.paused = false;
            *last = Instant::now();
            *acc = 0.0;
            let _ = reply.send(inner.status());
        }
        SimRequest::Step(n, reply) => {
            let _ = reply.send(inner.step_n(n, host, physics, reloads, audio));
            if inner.stopped {
                flags.stopped.store(true, Ordering::SeqCst);
            }
        }
        SimRequest::SetTimescale(t, reply) => {
            let _ = reply.send(inner.set_timescale(t));
        }
        SimRequest::InjectInput(actions, reply) => {
            let _ = reply.send(inner.queue_injects(actions));
        }
        SimRequest::ObsEvents(params, reply) => {
            let _ = reply.send(obs_events(&params, inner));
        }
        SimRequest::ObsWorldDump(params, reply) => {
            let _ = reply.send(obs_world_dump(&params, inner));
        }
        SimRequest::ObsLogsTail(params, reply) => {
            let _ = reply.send(obs_logs_tail(&params, inner));
        }
        SimRequest::ObsPerf(params, reply) => {
            let _ = reply.send(obs_perf(&params, inner));
        }
        SimRequest::ObsScreenshot(params, reply) => {
            let _ = reply.send(obs_screenshot(&params, inner));
        }
        SimRequest::JudgeRunUntilEvent(params, reply) => {
            let _ = reply.send(judge_run_until_event(
                &params, inner, host, physics, reloads, audio,
            ));
            if inner.stopped {
                flags.stopped.store(true, Ordering::SeqCst);
            }
        }
        SimRequest::JudgeWaitEvent(params, reply) => {
            let _ = reply.send(judge_wait_event(&params, inner));
        }
        SimRequest::JudgeAssertWorld(params, reply) => {
            let _ = reply.send(judge_assert_world(&params, inner));
        }
        SimRequest::JudgeAssertPerf(params, reply) => {
            let _ = reply.send(judge_assert_perf(&params, inner));
        }
        SimRequest::JudgeAssertScreenshot(params, reply) => {
            let _ = reply.send(judge_assert_screenshot(&params, inner));
        }
        SimRequest::Stop { force, reply } => {
            let code = if force { 1 } else { 0 };
            let report = inner.build_exit_report(code);
            inner.persist_exit_report(&report);
            inner.mark_stopped(flags);
            flags.shutdown.store(true, Ordering::SeqCst);
            let _ = reply.send(report);
        }
        SimRequest::SetAutoRun(enabled, reply) => {
            *auto_run = enabled;
            *last = Instant::now();
            let _ = reply.send(());
        }
        SimRequest::StartRecord(reply) => {
            let _ = reply.send(inner.start_record());
        }
    }
}

fn display_tick(
    inner: &mut PlayInner,
    host: &mut Option<ScriptHost>,
    physics: &mut PhysicsHost,
    audio: &mut crate::audio::AudioEngine,
    reloads: &ReloadQueue,
    acc: &mut f64,
    last: &mut Instant,
) {
    let dt = last.elapsed().as_secs_f64();
    *last = Instant::now();
    *acc += dt * inner.timescale;
    let mut steps = 0;
    let mut stepped = 0u32;
    let tick_start = Instant::now();
    while *acc >= FIXED_DT && steps < MAX_STEPS_PER_DISPLAY {
        match inner.step_one(host, physics, reloads, audio) {
            Ok(_) => {
                stepped += 1;
            }
            Err(err) => {
                if inner.last_error.is_none() {
                    let msg = err.to_string();
                    inner.last_error = Some(msg.clone());
                    inner.push_log(msg);
                }
                *acc = 0.0;
                break;
            }
        }
        *acc -= FIXED_DT;
        steps += 1;
    }
    if stepped > 0 {
        inner.update_fps_est(stepped, tick_start);
    }
    if *acc > FIXED_DT * f64::from(MAX_STEPS_PER_DISPLAY) {
        *acc = 0.0;
    }
}

fn instant_ms(start: Instant) -> u64 {
    u64::try_from(start.elapsed().as_millis()).unwrap_or(u64::MAX)
}

fn obs_events(params: &Value, inner: &PlayInner) -> Result<Value, RpcError> {
    let play_id = params
        .get("play_id")
        .and_then(Value::as_str)
        .unwrap_or(&inner.play_id);
    inner.check_play_id(Some(play_id))?;
    let after_seq = params.get("after_seq").and_then(Value::as_u64).unwrap_or(0);
    let name = params.get("name").and_then(Value::as_str);
    let limit = params
        .get("limit")
        .and_then(Value::as_u64)
        .and_then(|n| usize::try_from(n).ok())
        .unwrap_or(OBS_EVENTS_DEFAULT_LIMIT)
        .clamp(1, OBS_EVENTS_MAX_LIMIT);
    let events = inner.event_trace.query(after_seq, name, limit);
    Ok(json!({
        "play_id": play_id,
        "after_seq": after_seq,
        "last_seq": inner.event_trace.last_seq(),
        "events": events,
    }))
}

fn obs_world_dump(params: &Value, inner: &mut PlayInner) -> Result<Value, RpcError> {
    let play_id = params
        .get("play_id")
        .and_then(Value::as_str)
        .unwrap_or(&inner.play_id);
    inner.check_play_id(Some(play_id))?;
    let dir = inner
        .artifact_dir()
        .ok_or_else(|| not_found("world_dump requires a snapshot play directory"))?;
    let dump = events::world_dump_value(&inner.world);
    let path = dir.join(format!("world_dump_{}.json", Ulid::new()));
    events::write_artifact(&path, &dump).map_err(obs_io)?;
    Ok(json!({ "path": path.to_string_lossy() }))
}

fn obs_logs_tail(params: &Value, inner: &PlayInner) -> Result<Value, RpcError> {
    let play_id = params
        .get("play_id")
        .and_then(Value::as_str)
        .unwrap_or(&inner.play_id);
    inner.check_play_id(Some(play_id))?;
    let n = params
        .get("n")
        .and_then(Value::as_u64)
        .and_then(|v| usize::try_from(v).ok())
        .unwrap_or(50)
        .clamp(1, OBS_LOG_TAIL_MAX);
    let start = inner.log_tail.len().saturating_sub(n);
    let lines: Vec<&String> = inner.log_tail.iter().skip(start).collect();
    Ok(json!({
        "play_id": inner.play_id,
        "lines": lines,
    }))
}

fn obs_perf(params: &Value, inner: &PlayInner) -> Result<Value, RpcError> {
    let play_id = params
        .get("play_id")
        .and_then(Value::as_str)
        .unwrap_or(&inner.play_id);
    inner.check_play_id(Some(play_id))?;
    let mut out = json!({
        "play_id": inner.play_id,
        "frame": inner.world.frame,
    });
    if let Some(fps) = inner.fps_est {
        out["fps_est"] = json!(fps);
    }
    if let Some(ms) = inner.last_frame_ms {
        out["last_frame_ms"] = json!(ms);
    }
    Ok(out)
}

fn obs_screenshot(params: &Value, inner: &mut PlayInner) -> Result<Value, RpcError> {
    let play_id = params
        .get("play_id")
        .and_then(Value::as_str)
        .unwrap_or(&inner.play_id);
    inner.check_play_id(Some(play_id))?;
    if inner.no_render {
        return Err(no_gpu_error());
    }
    let dir = inner
        .artifact_dir()
        .ok_or_else(|| not_found("screenshot requires a snapshot play directory"))?
        .to_path_buf();
    let width = params
        .get("max_size")
        .and_then(Value::as_u64)
        .and_then(|n| u32::try_from(n).ok())
        .unwrap_or(640)
        .clamp(64, 4096);
    let height = (width as f32 * 9.0 / 16.0).round().max(64.0) as u32;
    let snapshot = inner.ensure_snapshot().map_err(obs_io)?;
    match render_offscreen_png(width, height, &snapshot, &inner.atlas) {
        Ok(png) => {
            let path = dir.join(format!("screenshot_{}.png", Ulid::new()));
            events::write_png_artifact(&path, &png).map_err(obs_io)?;
            Ok(json!({ "path": path.to_string_lossy() }))
        }
        Err(_) => Err(RpcError::with_data(
            APP,
            "GPU offscreen render unavailable",
            ErrorData::new("no_gpu"),
        )),
    }
}

fn offered_play_id<'a>(params: &'a Value, inner: &'a PlayInner) -> &'a str {
    params
        .get("play_id")
        .and_then(Value::as_str)
        .unwrap_or(&inner.play_id)
}

/// Register the matcher, then drive frames. Must not miss events that fire
/// during the drive (MASTER 6.3 / GS-EC-35).
fn judge_run_until_event(
    params: &Value,
    inner: &mut PlayInner,
    host: &mut Option<ScriptHost>,
    physics: &mut PhysicsHost,
    reloads: &ReloadQueue,
    audio: &mut crate::audio::AudioEngine,
) -> Result<Value, RpcError> {
    let play_id = offered_play_id(params, inner).to_owned();
    inner.check_play_id(Some(&play_id))?;
    let name = judge::required_name(params)?.to_owned();
    let timeout = judge::timeout_frames(params, MAX_STEP_FRAMES)?;
    let matcher = params.get("matcher").filter(|v| !v.is_null()).cloned();
    // REGISTER before any step_one — after_seq defaults to the current tail.
    let after_seq = judge::run_until_after_seq(params, inner.event_trace.last_seq());
    if let Some(hit) = judge::find_event(&inner.event_trace, after_seq, &name, matcher.as_ref()) {
        return Ok(judge::event_hit(&play_id, &hit));
    }
    let started = Instant::now();
    let mut stepped = 0u32;
    for _ in 0..timeout {
        inner
            .step_one(host, physics, reloads, audio)
            .map_err(control_rpc)?;
        stepped += 1;
        if let Some(hit) = judge::find_event(&inner.event_trace, after_seq, &name, matcher.as_ref())
        {
            if stepped > 0 {
                inner.update_fps_est(stepped, started);
            }
            return Ok(judge::event_hit(&play_id, &hit));
        }
    }
    if stepped > 0 {
        inner.update_fps_est(stepped, started);
    }
    Err(judge::event_miss(format!(
        "event {name} did not arrive after {timeout} frames (after_seq={after_seq})"
    )))
}

/// Query the existing ring only. Missing → fail immediately (do not hang).
fn judge_wait_event(params: &Value, inner: &PlayInner) -> Result<Value, RpcError> {
    let play_id = offered_play_id(params, inner);
    inner.check_play_id(Some(play_id))?;
    let name = judge::required_name(params)?;
    let after_seq = judge::required_after_seq(params)?;
    let matcher = params.get("matcher").filter(|v| !v.is_null());
    match judge::find_event(&inner.event_trace, after_seq, name, matcher) {
        Some(hit) => Ok(judge::event_hit(play_id, &hit)),
        None => Err(judge::event_miss(format!(
            "event {name} not in trace after_seq={after_seq}"
        ))),
    }
}

fn judge_assert_world(params: &Value, inner: &PlayInner) -> Result<Value, RpcError> {
    let play_id = offered_play_id(params, inner);
    inner.check_play_id(Some(play_id))?;
    let expected = judge::load_expected(params, inner.play_dir.as_deref())?;
    let epsilon = judge::epsilon(params)?;
    let actual = events::world_dump_value(&inner.world);
    judge::values_within_epsilon(&actual, &expected, epsilon)
        .map_err(|detail| judge::assert_err(format!("judge.assert_world failed: {detail}")))?;
    Ok(json!({
        "ok": true,
        "play_id": play_id,
        "epsilon": epsilon,
        "frame": inner.world.frame,
    }))
}

fn judge_assert_perf(params: &Value, inner: &PlayInner) -> Result<Value, RpcError> {
    let play_id = offered_play_id(params, inner);
    inner.check_play_id(Some(play_id))?;
    if inner.world.frame == 0 {
        return Err(judge::assert_err("judge.assert_perf: no frame advanced"));
    }
    if let Some(max) = params.get("max_frame_ms").and_then(Value::as_u64) {
        if let Some(ms) = inner.last_frame_ms {
            if ms > max {
                return Err(judge::assert_err(format!(
                    "last frame {ms}ms exceeds max_frame_ms {max}"
                )));
            }
        }
    }
    let mut out = json!({
        "ok": true,
        "play_id": play_id,
        "frame": inner.world.frame,
    });
    if let Some(ms) = inner.last_frame_ms {
        out["last_frame_ms"] = json!(ms);
    }
    if let Some(fps) = inner.fps_est {
        out["fps_est"] = json!(fps);
    }
    Ok(out)
}

fn judge_assert_screenshot(params: &Value, inner: &PlayInner) -> Result<Value, RpcError> {
    let play_id = offered_play_id(params, inner);
    inner.check_play_id(Some(play_id))?;
    // Stub: never fake a PNG pass (MASTER 6.4). Headless / no GPU → no_gpu.
    Err(no_gpu_error())
}

pub(crate) fn parse_entity_param(value: &Value) -> Result<Option<u64>, RpcError> {
    match value {
        Value::Null => Ok(None),
        Value::Number(n) => n
            .as_u64()
            .map(Some)
            .ok_or_else(|| invalid_params("entity_id must be a u64")),
        Value::String(s) => parse_play_id(s)
            .or_else(|| s.parse().ok())
            .ok_or_else(|| invalid_params("entity_id must be e_NNNNNN, rt_N, or a number"))
            .map(Some),
        _ => Err(invalid_params("entity_id must be a string or number")),
    }
}

pub(crate) fn parse_reload_job(params: &Value) -> Result<QueuedReload, RpcError> {
    let path = params
        .get("path")
        .and_then(Value::as_str)
        .map(str::to_string);
    let source = match params.get("source") {
        None | Some(Value::Null) => None,
        Some(Value::String(text)) => {
            if text.len() > gs_scene::MAX_SCRIPT_SOURCE_BYTES {
                return Err(invalid_params(format!(
                    "source exceeds {} bytes",
                    gs_scene::MAX_SCRIPT_SOURCE_BYTES
                )));
            }
            Some(text.clone())
        }
        Some(_) => return Err(invalid_params("source must be a string")),
    };
    let entity_id = match params.get("entity_id") {
        None => None,
        Some(v) => parse_entity_param(v)?,
    };
    if path.is_none() && source.is_none() && entity_id.is_none() {
        return Err(invalid_params(
            "script.reload requires path, source, or entity_id",
        ));
    }
    Ok(QueuedReload {
        entity_id,
        path,
        source,
    })
}

pub(crate) fn materialize_reload(
    play_dir: Option<&Path>,
    mut job: QueuedReload,
) -> Result<QueuedReload, RpcError> {
    if job.source.is_none() {
        if let Some(rel) = job.path.clone() {
            let dir = play_dir.ok_or_else(|| {
                not_found("script.reload path requires a snapshot play directory")
            })?;
            job.source = Some(read_script_under_root(dir, &rel)?);
        }
    }
    Ok(job)
}

fn read_script_under_root(root: &Path, rel: &str) -> Result<String, RpcError> {
    if rel.contains('\0')
        || Path::new(rel).is_absolute()
        || rel.split(['/', '\\']).any(|part| part == "..")
    {
        return Err(invalid_params("path escapes play directory"));
    }
    let path = root.join(rel);
    let text = std::fs::read_to_string(&path).map_err(|err| {
        RpcError::with_data(
            APP,
            format!("read {}: {err}", path.display()),
            ErrorData::new("E_IO"),
        )
    })?;
    if text.len() > gs_scene::MAX_SCRIPT_SOURCE_BYTES {
        return Err(invalid_params(format!(
            "source exceeds {} bytes",
            gs_scene::MAX_SCRIPT_SOURCE_BYTES
        )));
    }
    Ok(text)
}

pub(crate) fn queue_reload(queue: &ReloadQueue, job: QueuedReload) {
    queue
        .lock()
        .unwrap_or_else(|err| err.into_inner())
        .push(job);
}

pub(crate) fn check_offered_play_id(expected: &str, offered: Option<&str>) -> Result<(), RpcError> {
    match offered {
        None | Some("") => Ok(()),
        Some(id) if id == expected => Ok(()),
        Some(_) => Err(play_id_mismatch()),
    }
}

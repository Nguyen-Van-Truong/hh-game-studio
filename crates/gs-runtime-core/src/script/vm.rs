use std::cell::{Cell, RefCell};
use std::collections::{BTreeMap, BTreeSet, VecDeque};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use mlua::{Error as LuaError, Function, Lua, Result as LuaResult, StdLib, Table, Value, VmState};
use serde_json::Value as JsonValue;
use thiserror::Error;

use super::api::{begin_callback, commit_buffer, install_gs, HostInner, ScriptLog};
use super::convert::{json_object_from_map, json_to_lua, lua_to_json};
use super::ids::format_play_id;
use crate::error::Error;
use crate::physics::PhysicsHost;
use crate::world::{PlayEvent, World, FIXED_DT};

/// 64 MiB VM cap (MASTER 2.5 / 7.3).
pub const MEMORY_LIMIT_BYTES: usize = 64 * 1024 * 1024;

pub const GLOBAL_SOFT: Duration = Duration::from_millis(6);
pub const GLOBAL_HARD: Duration = Duration::from_millis(12);
pub const SCRIPT_SOFT: Duration = Duration::from_millis(2);
pub const SCRIPT_HARD: Duration = Duration::from_millis(4);
pub const INIT_BUDGET: Duration = Duration::from_millis(100);

pub const DEADLINE_MESSAGE: &str = "deadline exceeded";

pub const DISABLE_HARD_STREAK: u32 = 3;
pub const DISABLE_ERROR_COUNT: usize = 10;
pub const DISABLE_ERROR_WINDOW: Duration = Duration::from_secs(10);

/// Per-callback / per-chunk outcome (before or after the host cancel check).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct RunReport {
    pub lua_ok: bool,
    pub cancelled: bool,
    pub interrupts: u64,
    pub elapsed: Duration,
    pub used_memory: usize,
}

/// One frame of the two-tier scheduler (MASTER 7.3).
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct ScriptFrameReport {
    pub ran: Vec<u64>,
    pub starved: Vec<u64>,
    pub global_soft: bool,
    pub global_hard: bool,
}

/// Script callback failure recorded on [`World`] (step continues).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ScriptFailure {
    pub entity_id: u64,
    pub message: String,
    pub deadline: bool,
    pub memory: bool,
    pub file: Option<String>,
    pub line: Option<u32>,
    pub stack: Option<String>,
}

/// Test hook: budget accounting uses injected elapsed instead of `Instant`.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct ScriptTimeHook {
    pub advance_per_script: Duration,
}

#[derive(Debug, Error)]
pub enum ScriptError {
    #[error("deadline exceeded")]
    Deadline,
    #[error("luau memory limit exceeded")]
    Memory,
    #[error("luau: {0}")]
    Runtime(String),
    #[error("no script attached to entity {0}")]
    NotAttached(u64),
}

#[derive(Clone, Debug, Default)]
struct Diag {
    file: Option<String>,
    line: Option<u32>,
    stack: Option<String>,
}

struct ScriptInstance {
    env: Table,
    compiled: bool,
    implicit: bool,
    body_consumed: bool,
    module: Option<Table>,
    self_table: Option<Table>,
    state: Option<Table>,
    file: String,
    initialized: bool,
    disabled: bool,
    consecutive_hard: u32,
    error_times_ms: VecDeque<u64>,
}

impl ScriptInstance {
    fn raw(env: Table) -> Self {
        Self {
            env,
            compiled: false,
            implicit: false,
            body_consumed: false,
            module: None,
            self_table: None,
            state: None,
            file: String::new(),
            initialized: false,
            disabled: false,
            consecutive_hard: 0,
            error_times_ms: VecDeque::new(),
        }
    }
}

/// Sandboxed Luau VM with per-instance environments and a mutation buffer.
pub struct ScriptVm {
    lua: Lua,
    host: std::rc::Rc<RefCell<HostInner>>,
    deadline: std::rc::Rc<Cell<Option<Instant>>>,
    cancelled: std::rc::Rc<Cell<bool>>,
    interrupt_hits: std::rc::Rc<Cell<u64>>,
    budget: std::rc::Rc<Cell<Duration>>,
    started: std::rc::Rc<Cell<Option<Instant>>>,
    test_elapsed: std::rc::Rc<Cell<Option<Duration>>>,
    instances: RefCell<BTreeMap<u64, ScriptInstance>>,
    last_report: RefCell<Option<RunReport>>,
    last_diag: RefCell<Diag>,
    memory_limit: usize,
}

impl ScriptVm {
    pub fn new() -> Result<Self, ScriptError> {
        Self::with_memory_limit(MEMORY_LIMIT_BYTES)
    }

    /// Production uses [`MEMORY_LIMIT_BYTES`]. Tests may pass a smaller cap
    /// (GS-EC-23) so a memory bomb stays fast and non-flaky.
    pub fn with_memory_limit(limit: usize) -> Result<Self, ScriptError> {
        let lua = Lua::new_with(StdLib::ALL_SAFE, mlua::LuaOptions::default())
            .map_err(map_lua_new_err)?;
        lua.set_memory_limit(limit).map_err(map_lua_new_err)?;

        let host = std::rc::Rc::new(RefCell::new(HostInner::new()));
        let deadline = std::rc::Rc::new(Cell::new(None));
        let cancelled = std::rc::Rc::new(Cell::new(false));
        let interrupt_hits = std::rc::Rc::new(Cell::new(0u64));
        let budget = std::rc::Rc::new(Cell::new(Duration::MAX));
        let started = std::rc::Rc::new(Cell::new(None));
        let test_elapsed = std::rc::Rc::new(Cell::new(None));

        {
            let deadline = std::rc::Rc::clone(&deadline);
            let cancelled = std::rc::Rc::clone(&cancelled);
            let interrupt_hits = std::rc::Rc::clone(&interrupt_hits);
            let budget = std::rc::Rc::clone(&budget);
            let test_elapsed = std::rc::Rc::clone(&test_elapsed);
            lua.set_interrupt(move |_lua| {
                interrupt_hits.set(interrupt_hits.get().saturating_add(1));
                let over_budget = match test_elapsed.get() {
                    Some(forced) => forced >= budget.get(),
                    None => deadline.get().is_some_and(|limit| Instant::now() >= limit),
                };
                if over_budget {
                    cancelled.set(true);
                    // Error, not Yield. Yield suspends a coroutine; it does
                    // not abort a callback (MASTER 7.3 / C7).
                    return Err(LuaError::RuntimeError(DEADLINE_MESSAGE.into()));
                }
                Ok(VmState::Continue)
            });
        }

        install_gs(&lua, std::rc::Rc::clone(&host)).map_err(map_lua_new_err)?;
        lua.sandbox(true).map_err(map_lua_new_err)?;

        Ok(Self {
            lua,
            host,
            deadline,
            cancelled,
            interrupt_hits,
            budget,
            started,
            test_elapsed,
            instances: RefCell::new(BTreeMap::new()),
            last_report: RefCell::new(None),
            last_diag: RefCell::new(Diag::default()),
            memory_limit: limit,
        })
    }

    pub fn memory_limit(&self) -> usize {
        self.memory_limit
    }

    pub fn used_memory(&self) -> usize {
        self.lua.used_memory()
    }

    pub fn last_report(&self) -> Option<RunReport> {
        *self.last_report.borrow()
    }

    pub fn is_disabled(&self, entity_id: u64) -> bool {
        self.instances
            .borrow()
            .get(&entity_id)
            .is_some_and(|i| i.disabled)
    }

    pub fn state_json(&self, entity_id: u64) -> Option<JsonValue> {
        let instances = self.instances.borrow();
        let state = instances.get(&entity_id)?.state.as_ref()?;
        Some(lua_to_json(&Value::Table(state.clone())))
    }

    /// Compile `source` (text only) in a fresh environment and run it.
    pub fn exec(
        &self,
        world: &mut World,
        source: &str,
        budget: Duration,
    ) -> Result<RunReport, ScriptError> {
        self.exec_as(world, 0, source, budget)
    }

    /// Compile `source` (text only) in the environment for `entity_id`.
    pub fn exec_as(
        &self,
        world: &mut World,
        entity_id: u64,
        source: &str,
        budget: Duration,
    ) -> Result<RunReport, ScriptError> {
        self.run_chunk(
            world,
            entity_id,
            source,
            &chunk_name(entity_id, "exec"),
            budget,
        )
    }

    /// `on_init` budget is 100 ms (MASTER 7.3). Separate from the frame scheduler.
    pub fn run_init(
        &self,
        world: &mut World,
        entity_id: u64,
        source: &str,
    ) -> Result<RunReport, ScriptError> {
        self.run_chunk(
            world,
            entity_id,
            source,
            &chunk_name(entity_id, "init"),
            INIT_BUDGET,
        )
    }

    /// Two-tier frame scheduler for every attached script (MASTER 7.3 / 7.1).
    ///
    /// `physics` is last-frame Rapier (queries only). Bare `step` passes `None`.
    pub fn run_world_frame(&self, world: &mut World, physics: Option<&PhysicsHost>) {
        self.host.borrow_mut().bind_physics(physics);
        struct Unbind<'a>(&'a RefCell<HostInner>);
        impl Drop for Unbind<'_> {
            fn drop(&mut self) {
                self.0.borrow_mut().bind_physics(None);
            }
        }
        let _unbind = Unbind(&self.host);

        world.script_logs.clear();
        world.script_errors.clear();
        world.scripts_ran.clear();
        self.host.borrow_mut().reset_frame_spawns();

        let attached = world.attached_scripts.clone();
        if attached.is_empty() {
            world.last_script_frame = ScriptFrameReport::default();
            world.starved_scripts.clear();
            return;
        }

        let order = run_order(&attached, &world.starved_scripts);
        let hook = world.script_time_hook;
        let mut frame_elapsed = Duration::ZERO;
        let mut ran = Vec::new();
        let mut starved = Vec::new();
        let mut global_soft = false;
        let mut global_hard = false;
        let mut soft_warned = false;
        let mut processed = BTreeSet::new();

        for id in order {
            if self.is_disabled(id) {
                continue;
            }
            if !world.entities.contains_key(&id) {
                continue;
            }
            if frame_elapsed >= GLOBAL_HARD {
                starved.push(id);
                global_hard = true;
                continue;
            }

            let Some(source) = attached.get(&id) else {
                continue;
            };
            let remaining = GLOBAL_HARD.saturating_sub(frame_elapsed);
            let script_budget = SCRIPT_HARD.min(remaining);

            let used = self.run_attached_instance(world, id, source, script_budget, hook);
            frame_elapsed = frame_elapsed.saturating_add(used);

            if used >= SCRIPT_SOFT && !soft_warned {
                world.warnings.push(format!(
                    "script {} exceeded 2ms soft budget",
                    format_play_id(id)
                ));
                soft_warned = true;
            }
            if frame_elapsed >= GLOBAL_SOFT {
                global_soft = true;
            }

            ran.push(id);
            processed.insert(id);
        }

        self.test_elapsed.set(None);

        if global_soft {
            let msg = "script global soft budget 6ms";
            if !world.warnings.iter().any(|w| w == msg) {
                world.warnings.push(msg.to_string());
            }
        }

        world
            .queued_script_events
            .retain(|ev| !processed.contains(&ev.target_id) && !self.is_disabled(ev.target_id));

        world.scripts_ran = ran.clone();
        world.starved_scripts = starved.clone();
        world.last_script_frame = ScriptFrameReport {
            ran,
            starved,
            global_soft,
            global_hard,
        };
    }

    fn run_attached_instance(
        &self,
        world: &mut World,
        id: u64,
        source: &str,
        script_budget: Duration,
        hook: Option<ScriptTimeHook>,
    ) -> Duration {
        self.test_elapsed.set(None);
        if let Err(err) = self.ensure_compiled(world, id, source) {
            self.record_failure(world, id, &err);
            return elapsed_of(self, hook);
        }
        if let Some(h) = hook {
            self.test_elapsed.set(Some(h.advance_per_script));
        }

        let implicit = self.instances.borrow().get(&id).is_some_and(|i| i.implicit);
        let body_consumed = self
            .instances
            .borrow()
            .get(&id)
            .is_some_and(|i| i.body_consumed);

        if implicit {
            if body_consumed {
                if let Some(inst) = self.instances.borrow_mut().get_mut(&id) {
                    inst.body_consumed = false;
                }
                self.note_success(id);
                return elapsed_of(self, hook);
            }
            let result =
                self.run_chunk(world, id, source, &chunk_name(id, "update"), script_budget);
            self.finish_callback(world, id, result);
            return elapsed_of(self, hook);
        }

        if !self
            .instances
            .borrow()
            .get(&id)
            .is_some_and(|i| i.initialized)
        {
            let result = self.call_named(world, id, "on_init", INIT_BUDGET, CallbackArgs::Init);
            let failed = result.is_err();
            self.finish_callback(world, id, result);
            if failed {
                return elapsed_of(self, hook);
            }
            if let Some(inst) = self.instances.borrow_mut().get_mut(&id) {
                inst.initialized = true;
            }
        }

        let result = self.call_named(
            world,
            id,
            "on_update",
            script_budget,
            CallbackArgs::Update { dt: FIXED_DT },
        );
        let failed = result.is_err();
        self.finish_callback(world, id, result);
        if failed || self.is_disabled(id) {
            return elapsed_of(self, hook);
        }

        let events: Vec<_> = world
            .queued_script_events
            .iter()
            .filter(|ev| ev.target_id == id)
            .cloned()
            .collect();
        for ev in events {
            let result = self.call_named(
                world,
                id,
                "on_event",
                script_budget,
                CallbackArgs::Event {
                    name: ev.name.clone(),
                    data: ev.data.clone(),
                },
            );
            let failed = result.is_err();
            self.finish_callback(world, id, result);
            if failed || self.is_disabled(id) {
                break;
            }
        }

        elapsed_of(self, hook)
    }

    fn ensure_compiled(&self, world: &mut World, id: u64, source: &str) -> Result<(), ScriptError> {
        {
            let instances = self.instances.borrow();
            if instances.get(&id).is_some_and(|i| i.compiled) {
                return Ok(());
            }
        }

        let (file, props) = binding_of(world, id);
        let env = self.env_for(id).map_err(map_lua_err)?;
        let name = chunk_name(id, "load");
        // Compiling the chunk happens once per instance, so it belongs in the
        // one-shot bucket with on_init (MASTER 7.3), not the 4ms frame bucket.
        let evaluated = self.eval_chunk(world, id, source, &name, INIT_BUDGET)?;

        match evaluated {
            Value::Table(module) => {
                let state = {
                    let existing = self
                        .instances
                        .borrow()
                        .get(&id)
                        .and_then(|i| i.state.clone());
                    match existing {
                        Some(table) => table,
                        None => self.lua.create_table().map_err(map_lua_err)?,
                    }
                };
                let self_table = self
                    .make_self(id, &props, state.clone())
                    .map_err(map_lua_err)?;
                let mut instances = self.instances.borrow_mut();
                let inst = instances
                    .entry(id)
                    .or_insert_with(|| ScriptInstance::raw(env));
                inst.compiled = true;
                inst.implicit = false;
                inst.body_consumed = false;
                inst.module = Some(module);
                inst.state = Some(state);
                inst.self_table = Some(self_table);
                inst.file = file;
                inst.initialized = false;
            }
            _ => {
                let mut instances = self.instances.borrow_mut();
                let inst = instances
                    .entry(id)
                    .or_insert_with(|| ScriptInstance::raw(env));
                inst.compiled = true;
                inst.implicit = true;
                inst.body_consumed = true;
                inst.initialized = true;
                inst.file = file;
            }
        }
        Ok(())
    }

    fn make_self(
        &self,
        id: u64,
        props: &BTreeMap<String, JsonValue>,
        state: Table,
    ) -> LuaResult<Table> {
        let self_table = self.lua.create_table()?;
        self_table.set("id", format_play_id(id))?;
        self_table.set(
            "props",
            json_to_lua(&self.lua, &json_object_from_map(props))?,
        )?;
        self_table.set("state", state)?;
        Ok(self_table)
    }

    fn call_named(
        &self,
        world: &mut World,
        id: u64,
        method: &str,
        budget: Duration,
        args: CallbackArgs,
    ) -> Result<RunReport, ScriptError> {
        let (module, self_table) = {
            let instances = self.instances.borrow();
            let inst = instances.get(&id).ok_or(ScriptError::NotAttached(id))?;
            let module = inst
                .module
                .clone()
                .ok_or_else(|| ScriptError::Runtime("missing module".into()))?;
            let self_table = inst
                .self_table
                .clone()
                .ok_or_else(|| ScriptError::Runtime("missing self".into()))?;
            (module, self_table)
        };

        let func: Option<Function> = match module.get::<Value>(method).map_err(map_lua_err)? {
            Value::Function(f) => Some(f),
            _ => None,
        };

        self.with_callback(
            world,
            id,
            &chunk_name(id, method_kind(method)),
            budget,
            |lua| {
                let Some(func) = func else {
                    return Ok(());
                };
                match args {
                    CallbackArgs::Init => func.call::<()>((self_table,))?,
                    CallbackArgs::Update { dt } => func.call::<()>((self_table, dt))?,
                    CallbackArgs::Event { name, data } => {
                        let data_v = json_to_lua(lua, &data)?;
                        func.call::<()>((self_table, name, data_v))?;
                    }
                    CallbackArgs::Destroy => func.call::<()>((self_table,))?,
                }
                Ok(())
            },
        )
    }

    pub fn reload(&self, world: &mut World, entity_id: u64) -> Result<(), ScriptError> {
        let source = world
            .attached_scripts
            .get(&entity_id)
            .cloned()
            .ok_or(ScriptError::NotAttached(entity_id))?;
        let _ = self.call_on_destroy(world, entity_id);
        {
            let mut instances = self.instances.borrow_mut();
            if let Some(inst) = instances.get_mut(&entity_id) {
                inst.compiled = false;
                inst.implicit = false;
                inst.body_consumed = false;
                inst.module = None;
                inst.self_table = None;
                inst.initialized = false;
                inst.disabled = false;
                inst.consecutive_hard = 0;
                inst.error_times_ms.clear();
            }
        }
        self.ensure_compiled(world, entity_id, &source)?;
        if !self
            .instances
            .borrow()
            .get(&entity_id)
            .is_some_and(|i| i.implicit)
        {
            let result =
                self.call_named(world, entity_id, "on_init", INIT_BUDGET, CallbackArgs::Init);
            let failed = result.is_err();
            self.finish_callback(world, entity_id, result);
            if !failed {
                if let Some(inst) = self.instances.borrow_mut().get_mut(&entity_id) {
                    inst.initialized = true;
                }
            }
        }
        Ok(())
    }

    fn call_on_destroy(&self, world: &mut World, entity_id: u64) -> Result<RunReport, ScriptError> {
        let has = self
            .instances
            .borrow()
            .get(&entity_id)
            .is_some_and(|i| i.module.is_some() && i.self_table.is_some());
        if !has {
            return Ok(RunReport {
                lua_ok: true,
                cancelled: false,
                interrupts: 0,
                elapsed: Duration::ZERO,
                used_memory: self.lua.used_memory(),
            });
        }
        self.call_named(
            world,
            entity_id,
            "on_destroy",
            SCRIPT_HARD,
            CallbackArgs::Destroy,
        )
    }

    fn finish_callback(&self, world: &mut World, id: u64, result: Result<RunReport, ScriptError>) {
        match result {
            Ok(_) => self.note_success(id),
            Err(err) => self.record_failure(world, id, &err),
        }
    }

    fn note_success(&self, id: u64) {
        if let Some(inst) = self.instances.borrow_mut().get_mut(&id) {
            inst.consecutive_hard = 0;
        }
    }

    fn record_failure(&self, world: &mut World, id: u64, err: &ScriptError) {
        let diag = self.last_diag.borrow().clone();
        let file = diag.file.or_else(|| {
            self.instances
                .borrow()
                .get(&id)
                .map(|i| i.file.clone())
                .filter(|f| !f.is_empty())
        });
        world.script_errors.push(ScriptFailure {
            entity_id: id,
            message: err.to_string(),
            deadline: matches!(err, ScriptError::Deadline),
            memory: matches!(err, ScriptError::Memory),
            file,
            line: diag.line,
            stack: diag.stack,
        });

        let now = now_ms(world);
        let mut disable = false;
        let mut disable_file = String::new();
        {
            let mut instances = self.instances.borrow_mut();
            if let Some(inst) = instances.get_mut(&id) {
                if matches!(err, ScriptError::Deadline) {
                    inst.consecutive_hard = inst.consecutive_hard.saturating_add(1);
                } else {
                    inst.consecutive_hard = 0;
                }
                inst.error_times_ms.push_back(now);
                let window = DISABLE_ERROR_WINDOW.as_millis() as u64;
                while inst
                    .error_times_ms
                    .front()
                    .is_some_and(|t| now.saturating_sub(*t) > window)
                {
                    inst.error_times_ms.pop_front();
                }
                if inst.consecutive_hard >= DISABLE_HARD_STREAK
                    || inst.error_times_ms.len() >= DISABLE_ERROR_COUNT
                {
                    disable = !inst.disabled;
                    inst.disabled = true;
                    disable_file = inst.file.clone();
                }
            }
        }

        if disable {
            let _ = self.call_on_destroy(world, id);
            let last = world.script_errors.last();
            world.play_events.push(PlayEvent {
                name: "script_disabled".into(),
                entity_id: Some(id),
                data: serde_json::json!({
                    "file": if disable_file.is_empty() {
                        last.and_then(|e| e.file.clone())
                    } else {
                        Some(disable_file)
                    },
                    "line": last.and_then(|e| e.line),
                    "stack": last.and_then(|e| e.stack.clone()),
                }),
            });
        }
    }

    fn run_chunk(
        &self,
        world: &mut World,
        entity_id: u64,
        source: &str,
        name: &str,
        budget: Duration,
    ) -> Result<RunReport, ScriptError> {
        let env = self.env_for(entity_id).map_err(map_lua_err)?;
        self.with_callback(world, entity_id, name, budget, |lua| {
            lua.load(source).set_name(name).set_environment(env).exec()
        })
    }

    fn eval_chunk(
        &self,
        world: &mut World,
        entity_id: u64,
        source: &str,
        name: &str,
        budget: Duration,
    ) -> Result<Value, ScriptError> {
        let env = self.env_for(entity_id).map_err(map_lua_err)?;
        let out = RefCell::new(Value::Nil);
        self.with_callback(world, entity_id, name, budget, |lua| {
            let value = lua
                .load(source)
                .set_name(name)
                .set_environment(env)
                .eval::<Value>()?;
            *out.borrow_mut() = value;
            Ok(())
        })?;
        Ok(out.into_inner())
    }

    fn with_callback<F>(
        &self,
        world: &mut World,
        entity_id: u64,
        name: &str,
        budget: Duration,
        body: F,
    ) -> Result<RunReport, ScriptError>
    where
        F: FnOnce(&Lua) -> LuaResult<()>,
    {
        {
            let mut host = self.host.borrow_mut();
            begin_callback(&mut host, world, entity_id);
        }

        self.cancelled.set(false);
        self.interrupt_hits.set(0);
        self.budget.set(budget);
        let started = Instant::now();
        self.started.set(Some(started));
        self.deadline.set(Some(started + budget));
        *self.last_diag.borrow_mut() = Diag::default();

        let lua_result = body(&self.lua);

        self.deadline.set(None);
        self.started.set(None);
        self.budget.set(Duration::MAX);
        let elapsed = started.elapsed();
        let cancelled = self.cancelled.get();
        let interrupts = self.interrupt_hits.get();
        let used_memory = self.lua.used_memory();
        let lua_ok = lua_result.is_ok();

        let report = RunReport {
            lua_ok,
            cancelled,
            interrupts,
            elapsed,
            used_memory,
        };
        *self.last_report.borrow_mut() = Some(report);

        {
            let mut host = self.host.borrow_mut();
            let (mut logs, overflow) = host.take_logs();
            world.script_logs.append(&mut logs);
            if overflow > 0 {
                world.script_logs.push(ScriptLog {
                    entity_id,
                    level: "warn".into(),
                    message: format!("{overflow} log lines dropped"),
                });
            }
            for warning in host.take_warnings() {
                world.warnings.push(warning);
            }
        }

        if cancelled {
            self.host.borrow_mut().discard();
            *self.last_diag.borrow_mut() = Diag {
                file: Some(name.to_string()),
                line: None,
                stack: None,
            };
            return Err(ScriptError::Deadline);
        }

        match lua_result {
            Ok(()) => {
                let destroyed = commit_buffer(world, &mut self.host.borrow_mut());
                for dead in destroyed {
                    if dead != entity_id {
                        let _ = self.call_on_destroy(world, dead);
                    }
                    self.instances.borrow_mut().remove(&dead);
                }
                Ok(report)
            }
            Err(err) => {
                self.host.borrow_mut().discard();
                *self.last_diag.borrow_mut() = diag_from_lua(&err, name);
                Err(map_lua_err(err))
            }
        }
    }

    fn env_for(&self, entity_id: u64) -> LuaResult<Table> {
        let mut instances = self.instances.borrow_mut();
        if let Some(inst) = instances.get(&entity_id) {
            return Ok(inst.env.clone());
        }
        let env = make_script_env(&self.lua)?;
        instances.insert(entity_id, ScriptInstance::raw(env.clone()));
        Ok(env)
    }
}

enum CallbackArgs {
    Init,
    Update { dt: f64 },
    Event { name: String, data: JsonValue },
    Destroy,
}

fn method_kind(method: &str) -> &'static str {
    match method {
        "on_init" => "init",
        "on_update" => "update",
        "on_event" => "event",
        "on_destroy" => "destroy",
        _ => "cb",
    }
}

fn binding_of(world: &World, id: u64) -> (String, BTreeMap<String, JsonValue>) {
    if let Some(b) = world.script_bindings.get(&id) {
        return (b.file.clone(), b.props.clone());
    }
    if let Some(entity) = world.entities.get(&id) {
        if let Some(script) = &entity.extra.script {
            return (script.file.clone(), script.props.clone());
        }
    }
    (String::new(), BTreeMap::new())
}

fn elapsed_of(vm: &ScriptVm, hook: Option<ScriptTimeHook>) -> Duration {
    hook.map(|h| h.advance_per_script).unwrap_or_else(|| {
        vm.last_report()
            .map(|r| r.elapsed)
            .unwrap_or(Duration::ZERO)
    })
}

fn now_ms(world: &World) -> u64 {
    if let Some(ms) = world.script_now_ms {
        return ms;
    }
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

fn run_order(attached: &BTreeMap<u64, String>, starved: &[u64]) -> Vec<u64> {
    let mut out = Vec::with_capacity(attached.len());
    let mut seen = BTreeSet::new();
    for id in starved {
        if attached.contains_key(id) && seen.insert(*id) {
            out.push(*id);
        }
    }
    for id in attached.keys().copied() {
        if seen.insert(id) {
            out.push(id);
        }
    }
    out
}

fn chunk_name(entity_id: u64, kind: &str) -> String {
    if entity_id == 0 {
        kind.to_string()
    } else {
        format!("{kind}:{}", format_play_id(entity_id))
    }
}

fn make_script_env(lua: &Lua) -> LuaResult<Table> {
    let env = lua.create_table()?;
    let meta = lua.create_table()?;
    meta.set("__index", lua.globals())?;
    env.set_metatable(Some(meta))?;
    let g = env.clone();
    env.set("_G", g)?;
    Ok(env)
}

fn diag_from_lua(err: &LuaError, chunk_name: &str) -> Diag {
    let text = err.to_string();
    let stack = match err {
        LuaError::CallbackError { traceback, .. } => Some(traceback.clone()),
        _ if text.contains("stack traceback") => Some(text.clone()),
        _ => None,
    };
    let (file, line) = parse_file_line(&text).unwrap_or((Some(chunk_name.to_string()), None));
    Diag { file, line, stack }
}

fn parse_file_line(text: &str) -> Option<(Option<String>, Option<u32>)> {
    let bytes = text.as_bytes();
    let mut i = 0;
    while i + 2 < bytes.len() {
        if bytes[i] == b':' && bytes[i + 1].is_ascii_digit() {
            let start = i + 1;
            let mut end = start;
            while end < bytes.len() && bytes[end].is_ascii_digit() {
                end += 1;
            }
            if end < bytes.len() && bytes[end] == b':' {
                let line = text[start..end].parse::<u32>().ok();
                let file = text[..i].split_whitespace().last().map(str::to_string);
                return Some((file, line));
            }
        }
        i += 1;
    }
    None
}

fn map_lua_new_err(err: LuaError) -> ScriptError {
    ScriptError::Runtime(err.to_string())
}

fn map_lua_err(err: LuaError) -> ScriptError {
    if is_memory_error(&err) {
        return ScriptError::Memory;
    }
    if err.to_string().contains(DEADLINE_MESSAGE) {
        return ScriptError::Deadline;
    }
    ScriptError::Runtime(err.to_string())
}

fn is_memory_error(err: &LuaError) -> bool {
    match err {
        LuaError::MemoryError(_) => true,
        LuaError::CallbackError { cause, .. } => is_memory_error(cause),
        LuaError::BadArgument { cause, .. } => is_memory_error(cause),
        LuaError::WithContext { cause, .. } => is_memory_error(cause),
        other => {
            let s = other.to_string();
            s.contains("memory") || s.contains("Memory")
        }
    }
}

/// Run attached scripts during `script_on_update`. No attachments → caller stubs.
pub fn run_world_scripts(world: &mut World, physics: Option<&PhysicsHost>) -> Result<(), Error> {
    let vm = ScriptVm::new().map_err(|e| Error::LuauHost(e.to_string()))?;
    vm.run_world_frame(world, physics);
    Ok(())
}

/// `on_init` for one attached script (100 ms budget, not the frame scheduler).
pub fn run_init(world: &mut World, entity_id: u64) -> Result<RunReport, ScriptError> {
    let source = world
        .attached_scripts
        .get(&entity_id)
        .cloned()
        .ok_or(ScriptError::NotAttached(entity_id))?;
    let vm = ScriptVm::new()?;
    vm.run_init(world, entity_id, &source)
}

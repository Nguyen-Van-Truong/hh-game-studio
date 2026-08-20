//! WP-M-1-b spike: mlua + vendored Luau sandbox, memory limit, interrupt
//! deadline (error, not `VmState::Yield`), and a per-callback mutation buffer.
//!
//! Not production. Semantics follow real mlua/Luau APIs (MASTER 7.3 / I4).

use std::cell::{Cell, RefCell};
use std::rc::Rc;
use std::time::{Duration, Instant};

use mlua::{Error as LuaError, Lua, Result as LuaResult, StdLib, VmState};

/// 64 MiB VM cap from MASTER 2.5 / 7.3.
pub const MEMORY_LIMIT_BYTES: usize = 64 * 1024 * 1024;

const DEADLINE_MESSAGE: &str = "deadline exceeded";

/// Tiny authoritative world. `gs.set_*` never writes here directly.
#[derive(Clone, Debug, PartialEq)]
pub struct World {
    pub x: f64,
    pub y: f64,
}

impl Default for World {
    fn default() -> Self {
        Self { x: 0.0, y: 0.0 }
    }
}

#[derive(Clone, Debug)]
enum PendingWrite {
    SetPosition { x: f64, y: f64 },
    SetX { x: f64 },
    SetY { y: f64 },
}

#[derive(Default)]
struct MutationBuffer {
    writes: Vec<PendingWrite>,
}

impl MutationBuffer {
    fn push(&mut self, write: PendingWrite) {
        self.writes.push(write);
    }

    fn commit(&mut self, world: &mut World) {
        for write in self.writes.drain(..) {
            match write {
                PendingWrite::SetPosition { x, y } => {
                    world.x = x;
                    world.y = y;
                }
                PendingWrite::SetX { x } => world.x = x,
                PendingWrite::SetY { y } => world.y = y,
            }
        }
    }

    fn discard(&mut self) {
        self.writes.clear();
    }

    fn pending_len(&self) -> usize {
        self.writes.len()
    }
}

#[derive(Debug)]
pub enum CallbackError {
    Deadline,
    Script(LuaError),
}

impl std::fmt::Display for CallbackError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Deadline => write!(f, "{DEADLINE_MESSAGE}"),
            Self::Script(err) => write!(f, "{err}"),
        }
    }
}

impl std::error::Error for CallbackError {}

/// How the Lua chunk itself returned, before the host cancel-flag check.
#[derive(Clone, Copy, Debug)]
pub struct RunReport {
    pub lua_ok: bool,
    pub cancelled: bool,
    pub interrupts: u64,
    pub elapsed: Duration,
    pub used_memory: usize,
}

/// Sandboxed Luau VM with a host-side mutation buffer and safepoint deadline.
pub struct SpikeVm {
    lua: Lua,
    world: Rc<RefCell<World>>,
    buffer: Rc<RefCell<MutationBuffer>>,
    deadline: Rc<Cell<Option<Instant>>>,
    cancelled: Rc<Cell<bool>>,
    interrupt_hits: Rc<Cell<u64>>,
    last_report: RefCell<Option<RunReport>>,
    touched: Rc<Cell<bool>>,
}

impl SpikeVm {
    pub fn new() -> LuaResult<Self> {
        // Lua::new() loads StdLib::ALL_SAFE. We still pass ALL_SAFE explicitly
        // so NOTES can name the exact constructor.
        let lua = Lua::new_with(StdLib::ALL_SAFE, mlua::LuaOptions::default())?;
        lua.set_memory_limit(MEMORY_LIMIT_BYTES)?;

        let world = Rc::new(RefCell::new(World::default()));
        let buffer = Rc::new(RefCell::new(MutationBuffer::default()));
        let deadline = Rc::new(Cell::new(None));
        let cancelled = Rc::new(Cell::new(false));
        let interrupt_hits = Rc::new(Cell::new(0u64));
        let touched = Rc::new(Cell::new(false));

        {
            let deadline = Rc::clone(&deadline);
            let cancelled = Rc::clone(&cancelled);
            let interrupt_hits = Rc::clone(&interrupt_hits);
            lua.set_interrupt(move |_lua| {
                interrupt_hits.set(interrupt_hits.get().saturating_add(1));
                if let Some(limit) = deadline.get() {
                    if Instant::now() >= limit {
                        cancelled.set(true);
                        // Error, not Yield. Yield suspends a coroutine; it does
                        // not abort a callback (MASTER 7.3 / C7).
                        return Err(LuaError::RuntimeError(DEADLINE_MESSAGE.into()));
                    }
                }
                Ok(VmState::Continue)
            });
        }

        install_gs(&lua, Rc::clone(&buffer), Rc::clone(&touched))?;

        // Sandbox last so gs.* is already on the (then frozen) globals.
        lua.sandbox(true)?;

        Ok(Self {
            lua,
            world,
            buffer,
            deadline,
            cancelled,
            interrupt_hits,
            last_report: RefCell::new(None),
            touched,
        })
    }

    pub fn world(&self) -> World {
        self.world.borrow().clone()
    }

    pub fn last_report(&self) -> Option<RunReport> {
        *self.last_report.borrow()
    }

    pub fn pending_writes(&self) -> usize {
        self.buffer.borrow().pending_len()
    }

    /// True if `gs.touch()` ran — used to see whether a chunk continued after pcall.
    pub fn touched(&self) -> bool {
        self.touched.get()
    }

    pub fn used_memory(&self) -> usize {
        self.lua.used_memory()
    }

    pub fn luau_version_string(&self) -> LuaResult<String> {
        // Luau sets _VERSION to "Luau". Also surface _G._VERSION after sandbox.
        self.lua.globals().get::<String>("_VERSION")
    }

    /// Compile `source` (text only) and run it as one callback.
    ///
    /// Commit buffer iff the chunk returns OK *and* the deadline flag is clear.
    /// Any Lua error or deadline → discard every pending `gs.set_*`.
    pub fn run_callback(&self, source: &str, budget: Duration) -> Result<RunReport, CallbackError> {
        self.buffer.borrow_mut().discard();
        self.cancelled.set(false);
        self.interrupt_hits.set(0);
        self.touched.set(false);

        let started = Instant::now();
        self.deadline.set(Some(started + budget));

        // Source only — never load bytecode (I4).
        let lua_result = self.lua.load(source).set_name("callback").exec();

        self.deadline.set(None);
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

        if cancelled {
            self.buffer.borrow_mut().discard();
            return Err(CallbackError::Deadline);
        }

        match lua_result {
            Ok(()) => {
                self.buffer
                    .borrow_mut()
                    .commit(&mut self.world.borrow_mut());
                Ok(report)
            }
            Err(err) => {
                self.buffer.borrow_mut().discard();
                Err(CallbackError::Script(err))
            }
        }
    }

    /// Same as [`Self::run_callback`] but with interrupt removed (overhead baseline).
    pub fn run_without_interrupt(
        &self,
        source: &str,
        budget: Duration,
    ) -> Result<RunReport, CallbackError> {
        self.lua.remove_interrupt();
        let result = self.run_callback(source, budget);
        self.reinstall_interrupt();
        result
    }

    fn reinstall_interrupt(&self) {
        let deadline = Rc::clone(&self.deadline);
        let cancelled = Rc::clone(&self.cancelled);
        let interrupt_hits = Rc::clone(&self.interrupt_hits);
        self.lua.set_interrupt(move |_lua| {
            interrupt_hits.set(interrupt_hits.get().saturating_add(1));
            if let Some(limit) = deadline.get() {
                if Instant::now() >= limit {
                    cancelled.set(true);
                    return Err(LuaError::RuntimeError(DEADLINE_MESSAGE.into()));
                }
            }
            Ok(VmState::Continue)
        });
    }
}

fn install_gs(
    lua: &Lua,
    buffer: Rc<RefCell<MutationBuffer>>,
    touched: Rc<Cell<bool>>,
) -> LuaResult<()> {
    let gs = lua.create_table()?;

    let b = Rc::clone(&buffer);
    gs.set(
        "set_position",
        lua.create_function(move |_, (x, y): (f64, f64)| {
            b.borrow_mut().push(PendingWrite::SetPosition { x, y });
            Ok(())
        })?,
    )?;

    let b = Rc::clone(&buffer);
    gs.set(
        "set_x",
        lua.create_function(move |_, x: f64| {
            b.borrow_mut().push(PendingWrite::SetX { x });
            Ok(())
        })?,
    )?;

    let b = Rc::clone(&buffer);
    gs.set(
        "set_y",
        lua.create_function(move |_, y: f64| {
            b.borrow_mut().push(PendingWrite::SetY { y });
            Ok(())
        })?,
    )?;

    gs.set(
        "touch",
        lua.create_function(move |_, ()| {
            touched.set(true);
            Ok(())
        })?,
    )?;

    lua.globals().set("gs", gs)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use mlua::Value;

    fn error_mentions_deadline(err: &CallbackError) -> bool {
        match err {
            CallbackError::Deadline => true,
            CallbackError::Script(lua_err) => lua_err.to_string().contains(DEADLINE_MESSAGE),
        }
    }

    const TIGHT_LOOP: &str = r#"
        local i = 0
        while true do
            i += 1
        end
    "#;

    #[test]
    fn infinite_loop_stopped_by_deadline() {
        let vm = SpikeVm::new().expect("vm");
        let budget = Duration::from_millis(50);
        let started = Instant::now();
        let err = vm
            .run_callback(TIGHT_LOOP, budget)
            .expect_err("infinite loop must fail the callback");
        let elapsed = started.elapsed();

        assert!(
            error_mentions_deadline(&err),
            "expected deadline error, got {err}"
        );
        assert!(
            elapsed < Duration::from_secs(3),
            "deadline must stop the loop in a few seconds, took {elapsed:?}"
        );
        assert!(
            elapsed >= budget,
            "must run at least until the budget, took {elapsed:?}"
        );
        assert_eq!(vm.world(), World::default());
    }

    #[test]
    fn pcall_does_not_swallow_deadline() {
        let vm = SpikeVm::new().expect("vm");
        // pcall around the death loop, then a mutation that must not commit.
        // Also retry-pcall forever: if pcall could keep the callback alive,
        // this would hang and the host flag / re-fired interrupt must still kill it.
        let source = r#"
            local swallowed = 0
            while true do
                local ok = pcall(function()
                    local i = 0
                    while true do
                        i += 1
                    end
                end)
                if ok then
                    swallowed += 1
                end
            end
            gs.set_position(99, 99)
        "#;

        let budget = Duration::from_millis(80);
        let started = Instant::now();
        let err = vm
            .run_callback(source, budget)
            .expect_err("pcall must not let the callback succeed");
        let elapsed = started.elapsed();

        assert!(
            error_mentions_deadline(&err),
            "death sentence must still fail the callback, got {err}"
        );
        assert!(
            elapsed < Duration::from_secs(3),
            "must not hang; took {elapsed:?}"
        );
        assert_eq!(
            vm.world(),
            World::default(),
            "mutation after swallowed pcall must not commit"
        );
        assert!(
            matches!(err, CallbackError::Deadline),
            "host must treat cancel flag as callback failure (pcall-pierce), got {err:?}"
        );
        let report = vm.last_report().expect("report");
        eprintln!(
            "pcall-pierce (retry loop): lua_ok={} cancelled={} interrupts={} elapsed={:?}",
            report.lua_ok, report.cancelled, report.interrupts, report.elapsed
        );
        assert!(
            report.cancelled,
            "deadline flag must be set after a pcall-wrapped death loop"
        );

        // Single pcall, no outer retry: if lua_ok==false the interrupt Err
        // escaped pcall. If lua_ok==true the host flag is the death sentence.
        let vm = SpikeVm::new().expect("vm");
        let err = vm
            .run_callback(
                r#"
                    local ok, err = pcall(function()
                        while true do end
                    end)
                    gs.touch()
                    gs.set_position(1, 1)
                "#,
                Duration::from_millis(50),
            )
            .expect_err("single pcall must still fail the callback");
        assert!(error_mentions_deadline(&err), "{err}");
        assert_eq!(vm.world(), World::default());
        let report = vm.last_report().expect("report");
        eprintln!(
            "pcall-pierce (single pcall): lua_ok={} cancelled={} touched_after_pcall={} interrupts={} elapsed={:?}",
            report.lua_ok, report.cancelled, vm.touched(), report.interrupts, report.elapsed
        );
    }

    #[test]
    fn mutation_buffer_commit_on_success_discard_on_fail() {
        let vm = SpikeVm::new().expect("vm");

        vm.run_callback("gs.set_position(10, 20)", Duration::from_secs(1))
            .expect("success callback");
        assert_eq!(vm.world(), World { x: 10.0, y: 20.0 });

        let err = vm
            .run_callback(
                r#"
                    gs.set_position(1, 2)
                    gs.set_x(3)
                    error("boom")
                "#,
                Duration::from_secs(1),
            )
            .expect_err("script error must fail");
        assert!(matches!(err, CallbackError::Script(_)), "{err}");
        assert_eq!(
            vm.world(),
            World { x: 10.0, y: 20.0 },
            "error must discard the buffer; world stays at last commit"
        );

        let err = vm
            .run_callback(
                r#"
                    gs.set_position(7, 8)
                    while true do end
                "#,
                Duration::from_millis(40),
            )
            .expect_err("deadline must fail");
        assert!(error_mentions_deadline(&err), "{err}");
        assert_eq!(
            vm.world(),
            World { x: 10.0, y: 20.0 },
            "deadline must discard the buffer"
        );
        assert_eq!(vm.pending_writes(), 0);
    }

    #[test]
    fn sandbox_and_memory_limit_are_configured() {
        let vm = SpikeVm::new().expect("vm");
        let version = vm.luau_version_string().expect("version");
        assert!(
            version.starts_with("Luau"),
            "expected Luau _VERSION, got {version:?}"
        );
        eprintln!("Luau _VERSION = {version}");
        assert!(
            vm.used_memory() < MEMORY_LIMIT_BYTES,
            "used {} bytes",
            vm.used_memory()
        );

        // Globals are read-only under sandbox(true); assignment is local-env.
        vm.run_callback("var = 1", Duration::from_secs(1))
            .expect("local write via sandbox env");
        let global_var: Value = vm.lua.globals().get("var").expect("get");
        // Either nil (write stayed in chunk env) or the number if mlua
        // proxies the write — record the real behavior, do not invent.
        assert!(
            matches!(
                global_var,
                Value::Nil | Value::Integer(1) | Value::Number(_)
            ),
            "unexpected global var: {global_var:?}"
        );
    }

    #[test]
    fn interrupt_overhead_measurement() {
        // Fixed-iteration work so both sides finish well under the budget.
        let source = r#"
            local s = 0
            for i = 1, 200000 do
                s += i
            end
        "#;

        let with_vm = SpikeVm::new().expect("vm");
        let with = with_vm
            .run_callback(source, Duration::from_secs(5))
            .expect("with interrupt");

        let without_vm = SpikeVm::new().expect("vm");
        let without = without_vm
            .run_without_interrupt(source, Duration::from_secs(5))
            .expect("without interrupt");

        let hits = with.interrupts.max(1);
        let extra = with.elapsed.saturating_sub(without.elapsed).as_nanos() as f64;
        let ns_per_hit = extra / hits as f64;

        eprintln!(
            "interrupt overhead: with={:?} without={:?} hits={} extra_ns={:.0} ns_per_interrupt={:.1}",
            with.elapsed, without.elapsed, with.interrupts, extra, ns_per_hit
        );

        // Sanity: interrupt fired, both sides finished, no hang.
        assert!(with.interrupts > 0, "interrupt should fire on a 200k loop");
        assert!(with.elapsed < Duration::from_secs(3));
        assert!(without.elapsed < Duration::from_secs(3));
    }
}

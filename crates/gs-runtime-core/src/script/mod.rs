//! Luau VM host (WP-M3-1 / M3-2, MASTER 7.1–7.3, I4).
//!
//! One sandboxed VM; each script instance has its own environment table.
//! Compile from source text only. Interrupt returns an error at a safepoint
//! (never `VmState::Yield`). Mutation buffer commits only when the callback
//! returns OK and the host cancel flag is clear.
//!
//! `ScriptHost` is the long-lived owner. Do not store it on [`crate::World`].

mod api;
mod convert;
mod host;
mod ids;
mod vm;

pub use api::ScriptLog;
pub use host::ScriptHost;
pub use ids::{format_play_id, parse_play_id, RUNTIME_ID_BASE, SPAWN_CAP_PER_FRAME};
pub use vm::{
    run_init, run_world_scripts, RunReport, ScriptError, ScriptFailure, ScriptFrameReport,
    ScriptTimeHook, ScriptVm, DEADLINE_MESSAGE, DISABLE_ERROR_COUNT, DISABLE_ERROR_WINDOW,
    DISABLE_HARD_STREAK, GLOBAL_HARD, GLOBAL_SOFT, INIT_BUDGET, MEMORY_LIMIT_BYTES, SCRIPT_HARD,
    SCRIPT_SOFT,
};

#[cfg(test)]
mod tests;

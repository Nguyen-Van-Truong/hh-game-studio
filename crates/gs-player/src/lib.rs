//! Play process library: snapshot verify/build + control server (I3, I8).
//!
//! The play process owns a long-lived Luau [`gs_runtime_core::ScriptHost`] and
//! [`gs_runtime_core::PhysicsHost`] on its simulate thread. The editor may
//! depend on this crate for
//! [`build_snapshot`], [`pack_project`], [`verify_snapshot`], and
//! [`ControlClient`] only.

mod args;
mod atlas;
mod audio;
mod builder;
mod client;
mod control;
mod error;
mod events;
mod exe;
mod gamepad;
mod gpu;
mod guard;
mod hash;
mod input;
mod judge;
mod manifest;
mod pack;
mod player_file;
mod run;
mod script_play;
mod sim;
mod tape;
mod verify;
mod window;

pub use args::Args;
pub use atlas::load_play_atlas;
pub use builder::{build_snapshot, write_snapshot_dir, AssetInput, BuiltSnapshot, SnapshotRequest};
pub use client::ControlClient;
pub use control::{
    control_ready_line, install_panic_exit_report, ControlConfig, ControlHandle, ControlServer,
    ExitReport, PlaySource, PlayStatus, LOG_TAIL_MAX, MAX_STEP_FRAMES, TIMESCALE_MAX,
    TIMESCALE_MIN,
};
pub use error::Error;
pub use events::{TraceEvent, EVENT_RING_CAP, OBS_EVENTS_DEFAULT_LIMIT, OBS_LOG_TAIL_MAX};
pub use exe::find_player_exe;
pub use gpu::GpuMode;
pub use guard::{
    memory_guard_trip, process_rss_bytes, watchdog_trip, EXIT_OOM_GUARD, EXIT_SCRIPT_HANG,
    OOM_GUARD_BYTES, RAM_WARN_BYTES, WATCHDOG_FRAME_MS,
};
pub use hash::sha256_hex;
pub use manifest::{AssetRecord, Manifest, SnapshotHashes, VerifiedSnapshot};
pub use pack::{
    pack_project, pack_project_with, reject_out_dir_inside_project, PackOptions, PackedGame,
};
pub use player_file::{
    cleanup_stale_player_json, locate_player_json, pid_is_alive, player_json_for_snapshot,
    player_json_under, read_player_file, utc_now_rfc3339, write_player_file, PlayerFile,
    PLAYER_JSON_REL,
};
pub use run::{run_headless_frames, run_headless_frames_with, PlayReport};
pub use tape::{
    append_action, bind_tape, load_tape, record_input_frames, tape_actions_for_frame,
    validate_header, validate_header_force, write_header, BoundTape, LoadedTape, TapeEvent,
    TapeHeader, TapeHeaderCheck, INPUT_TAPE_FILE, RECORD_TAPE_FILE, REPLAY_TAPE_FILE,
};
pub use verify::verify_snapshot;
pub use window::run_window;

pub fn crate_name() -> &'static str {
    "gs-player"
}

#[cfg(test)]
mod tests {
    #[test]
    fn smoke() {
        assert_eq!(super::crate_name(), "gs-player");
    }
}

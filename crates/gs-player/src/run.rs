use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

use gs_render2d::RenderSnapshot;
use gs_runtime_core::{InputFrame, World};
use serde_json::Value;

use crate::audio::AudioEngine;
use crate::error::Error;
use crate::events;
use crate::input::load_input_map;
use crate::manifest::VerifiedSnapshot;
use crate::script_play::{
    load_play_scripts, make_physics_host, make_script_host, step_world, world_needs_host,
};
use crate::tape::{
    append_frame_actions, apply_tape_to_frame, bind_tape, validate_actions_in_map, BoundTape,
};
use crate::verify::verify_snapshot;

/// Result of a headless `--frames N` run (no window, no GPU required).
#[derive(Clone, Debug)]
pub struct PlayReport {
    pub play_id: String,
    pub document_revision: String,
    pub seed: u64,
    pub frames: u64,
    pub snapshot: RenderSnapshot,
    pub warnings: Vec<String>,
    /// `obs.world_dump` JSON after the last simulate step (not yet canonical).
    pub world_dump: Value,
    /// False when a tape was replayed with `--force` after a header mismatch.
    pub evidence_ok: bool,
}

/// Verify the snapshot, then run `n` simulate steps. Tests must use this path.
pub fn run_headless_frames(manifest: &Path, n: u32) -> Result<PlayReport, Error> {
    run_headless_frames_with(manifest, n, None, None, false)
}

/// Headless run with optional `--record` / `--replay` / `--force`.
pub fn run_headless_frames_with(
    manifest: &Path,
    n: u32,
    replay: Option<&Path>,
    record: Option<&Path>,
    force: bool,
) -> Result<PlayReport, Error> {
    let verified = verify_snapshot(manifest)?;
    run_verified_frames(manifest, &verified, n, replay, record, force)
}

fn run_verified_frames(
    manifest: &Path,
    verified: &VerifiedSnapshot,
    n: u32,
    replay: Option<&Path>,
    record: Option<&Path>,
    force: bool,
) -> Result<PlayReport, Error> {
    let play_dir = manifest
        .parent()
        .ok_or_else(|| Error::reject("manifest path has no parent directory"))?;
    let scene_path = play_dir.join("scene.json");
    let mut world = World::from_scene_path(&scene_path, verified.manifest.seed)?;
    crate::atlas::bind_play_atlas(&mut world, play_dir)?;
    load_play_scripts(&mut world, play_dir)?;
    let mut host = if world_needs_host(&world) {
        Some(make_script_host()?)
    } else {
        None
    };
    let mut physics = make_physics_host();
    let mut snapshot = gs_runtime_core::build_render_snapshot(&mut world)?;
    let input = load_input_map(play_dir)?;
    let bound = bind_tape(Some(verified), Some(play_dir), replay, record, force)?;
    check_replay_actions(&bound, &input)?;
    let mut last_recorded = BTreeMap::new();
    let mut audio = AudioEngine::headless(Some(play_dir));
    for _ in 0..n {
        let frame_idx = world.frame;
        let frame_input = if let Some(tape) = &bound.replay {
            apply_tape_to_frame(&input, &tape.events, frame_idx)
        } else {
            input.clone()
        };
        if let Some(path) = &bound.record_path {
            append_frame_actions(path, frame_idx, &frame_input, &mut last_recorded)?;
        }
        snapshot = step_world(&mut world, &frame_input, host.as_mut(), Some(&mut physics))?;
        audio.drain(&mut world);
    }
    let world_dump = events::world_dump_value(&world);
    let mut warnings = world.warnings;
    if let Some(warning) = bound.warning {
        warnings.push(warning);
    }
    Ok(PlayReport {
        play_id: verified.play_id.clone(),
        document_revision: verified.document_revision.clone(),
        seed: verified.manifest.seed,
        frames: world.frame,
        snapshot,
        warnings,
        world_dump,
        evidence_ok: bound.evidence_ok,
    })
}

fn check_replay_actions(bound: &BoundTape, input: &InputFrame) -> Result<(), Error> {
    let Some(tape) = &bound.replay else {
        return Ok(());
    };
    let known: BTreeSet<String> = input.actions.keys().cloned().collect();
    validate_actions_in_map(&tape.events, &known)
}

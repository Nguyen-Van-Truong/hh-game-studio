//! Play-side script loading and stepping. `ScriptHost` is created on the
//! calling thread (simulate / window / headless) because it is `!Send`.
//! `PhysicsHost` is created on that same thread so Rapier velocity persists.

use std::path::{Path, PathBuf};

use gs_render2d::RenderSnapshot;
use gs_runtime_core::{
    step, step_with_host, step_with_hosts, step_with_physics, InputFrame, PhysicsHost, ScriptHost,
    World,
};

use crate::error::Error;

/// Directory passed to [`World::load_script_sources`].
///
/// Bindings store paths like `scripts/door.luau`. The play/snapshot directory
/// is the folder that contains `scripts/` when present; otherwise it is still
/// the play dir (joins simply miss until a reload supplies source).
pub(crate) fn script_source_root(play_dir: &Path) -> PathBuf {
    play_dir.to_path_buf()
}

pub(crate) fn load_play_scripts(world: &mut World, play_dir: &Path) -> Result<(), Error> {
    if world.script_bindings.is_empty() {
        return Ok(());
    }
    let root = script_source_root(play_dir);
    world.load_script_sources(&root)?;
    Ok(())
}

pub(crate) fn world_needs_host(world: &World) -> bool {
    !world.script_bindings.is_empty() || !world.attached_scripts.is_empty()
}

pub(crate) fn make_script_host() -> Result<ScriptHost, Error> {
    ScriptHost::new().map_err(|err| Error::from(gs_runtime_core::Error::LuauHost(err.to_string())))
}

pub(crate) fn make_physics_host() -> PhysicsHost {
    PhysicsHost::new()
}

pub(crate) fn step_world(
    world: &mut World,
    input: &InputFrame,
    host: Option<&mut ScriptHost>,
    physics: Option<&mut PhysicsHost>,
) -> Result<RenderSnapshot, gs_runtime_core::Error> {
    match (host, physics) {
        (Some(host), Some(physics)) => step_with_hosts(world, input, host, physics),
        (None, Some(physics)) => step_with_physics(world, input, physics),
        (Some(host), None) => step_with_host(world, input, host),
        (None, None) => step(world, input),
    }
}

use gs_render2d::RenderSnapshot;

use crate::error::Error;
use crate::phase::Phase;
use crate::physics::{world_has_physics, PhysicsHost};
use crate::render::build_render_snapshot;
use crate::script::ScriptHost;
use crate::world::{InputFrame, SystemEvent, World};

/// Run one 6.2 simulate step.
///
/// Worlds with no attached scripts do not create a VM (player tests).
/// Attached scripts without a host use an ephemeral VM (M3-1 compat).
/// Worlds with no `RigidBody2D`/`Collider2D`/solid tilemap skip Rapier
/// (existing tests). If bodies exist and no [`PhysicsHost`] is passed, an
/// ephemeral Rapier world is created for this step only (velocity does not
/// persist).
pub fn step(world: &mut World, input: &InputFrame) -> Result<RenderSnapshot, Error> {
    step_inner(world, input, None, None)
}

/// Same schedule as [`step`], driving scripts through a long-lived host.
pub fn step_with_host(
    world: &mut World,
    input: &InputFrame,
    host: &mut ScriptHost,
) -> Result<RenderSnapshot, Error> {
    step_inner(world, input, Some(host), None)
}

/// Same schedule as [`step`], keeping a long-lived Rapier world.
pub fn step_with_physics(
    world: &mut World,
    input: &InputFrame,
    physics: &mut PhysicsHost,
) -> Result<RenderSnapshot, Error> {
    step_inner(world, input, None, Some(physics))
}

/// Scripts + persistent physics (caller owns both hosts, not [`World`]).
pub fn step_with_hosts(
    world: &mut World,
    input: &InputFrame,
    host: &mut ScriptHost,
    physics: &mut PhysicsHost,
) -> Result<RenderSnapshot, Error> {
    step_inner(world, input, Some(host), Some(physics))
}

fn step_inner(
    world: &mut World,
    input: &InputFrame,
    host: Option<&mut ScriptHost>,
    physics: Option<&mut PhysicsHost>,
) -> Result<RenderSnapshot, Error> {
    world.last_phases.clear();
    world.script_visit_order.clear();

    phase_input(world, input);
    phase_script_on_update(world, host, physics.as_deref())?;
    phase_commit_mutations(world);
    run_physics_phases(world, physics);
    world.apply_camera_follow();
    world.tick_camera_shake();
    world.enqueue_autoplay_audio();
    phase_timers(world);
    phase_emit_trace(world);
    let snapshot = build_render_snapshot(world)?;
    record(world, Phase::BuildRenderSnapshot);
    Ok(snapshot)
}

fn run_physics_phases(world: &mut World, physics: Option<&mut PhysicsHost>) {
    match physics {
        Some(physics) => {
            physics.integrate(world);
            record(world, Phase::Physics);
            physics.queue_collision_events(world);
            record(world, Phase::Collisions);
        }
        None if world_has_physics(world) => {
            let mut ephemeral = PhysicsHost::new();
            ephemeral.integrate(world);
            record(world, Phase::Physics);
            ephemeral.queue_collision_events(world);
            record(world, Phase::Collisions);
        }
        None => {
            world.pending_velocities.clear();
            world.pending_impulses.clear();
            record(world, Phase::Physics);
            record(world, Phase::Collisions);
        }
    }
}

fn record(world: &mut World, phase: Phase) {
    world.last_phases.push(phase);
}

fn phase_input(world: &mut World, input: &InputFrame) {
    world.input = input.clone();
    record(world, Phase::Input);
}

fn phase_script_on_update(
    world: &mut World,
    host: Option<&mut ScriptHost>,
    physics: Option<&PhysicsHost>,
) -> Result<(), Error> {
    // Always visit ids in BTreeMap order (existing fixtures / camera tests).
    for id in world.entities.keys().copied() {
        world.script_visit_order.push(id);
    }
    if let Some(host) = host {
        host.run_world_frame(world, physics);
    } else if !world.attached_scripts.is_empty() {
        crate::script::run_world_scripts(world, physics)?;
    }
    record(world, Phase::ScriptOnUpdate);
    Ok(())
}

fn phase_commit_mutations(world: &mut World) {
    // Per-callback commit already applied successful `gs.set_*` (MASTER 7.2).
    record(world, Phase::CommitMutations);
}

fn phase_timers(world: &mut World) {
    record(world, Phase::Timers);
}

fn phase_emit_trace(world: &mut World) {
    world.frame = world.frame.saturating_add(1);
    world
        .events
        .push(SystemEvent::FrameAdvanced { frame: world.frame });
    record(world, Phase::EmitTrace);
}

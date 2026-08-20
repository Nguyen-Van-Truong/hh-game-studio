use gs_render2d::RenderSnapshot;
use serde_json::Value as JsonValue;

use super::vm::{ScriptError, ScriptVm};
use crate::error::Error;
use crate::world::{InputFrame, World};

/// Long-lived Luau host. The caller owns this (not [`World`]): `ScriptVm` /
/// mlua without `send` is `!Send`, and `World` is `Clone` + used across
/// player threads.
pub struct ScriptHost {
    vm: ScriptVm,
}

impl ScriptHost {
    pub fn new() -> Result<Self, ScriptError> {
        Ok(Self {
            vm: ScriptVm::new()?,
        })
    }

    pub fn with_memory_limit(limit: usize) -> Result<Self, ScriptError> {
        Ok(Self {
            vm: ScriptVm::with_memory_limit(limit)?,
        })
    }

    pub fn vm(&self) -> &ScriptVm {
        &self.vm
    }

    /// Same 6.2 schedule as [`crate::step`], using this host's VM.
    pub fn step(&mut self, world: &mut World, input: &InputFrame) -> Result<RenderSnapshot, Error> {
        crate::schedule::step_with_host(world, input, self)
    }

    /// Same schedule, with a caller-owned [`crate::PhysicsHost`].
    pub fn step_with_physics(
        &mut self,
        world: &mut World,
        input: &InputFrame,
        physics: &mut crate::PhysicsHost,
    ) -> Result<RenderSnapshot, Error> {
        crate::schedule::step_with_hosts(world, input, self, physics)
    }

    pub fn run_world_frame(&self, world: &mut World, physics: Option<&crate::PhysicsHost>) {
        self.vm.run_world_frame(world, physics);
    }

    /// Re-enable a disabled instance, keep `self.state`, run `on_init` again.
    pub fn reload(&self, world: &mut World, entity_id: u64) -> Result<(), ScriptError> {
        self.vm.reload(world, entity_id)
    }

    pub fn is_disabled(&self, entity_id: u64) -> bool {
        self.vm.is_disabled(entity_id)
    }

    pub fn state_json(&self, entity_id: u64) -> Option<JsonValue> {
        self.vm.state_json(entity_id)
    }
}

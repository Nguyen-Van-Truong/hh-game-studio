/// Fixed simulate phases (MASTER 6.2). One thread; order is the contract.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Phase {
    Input,
    ScriptOnUpdate,
    CommitMutations,
    Physics,
    Collisions,
    Timers,
    EmitTrace,
    BuildRenderSnapshot,
}

impl Phase {
    /// Canonical 6.2 order. Timers are still a stub.
    /// `script_on_update` runs attached Luau when present; otherwise visits ids.
    /// Physics / collisions run Rapier when a [`crate::PhysicsHost`] is passed
    /// or the world has `RigidBody2D` / `Collider2D`.
    pub const ORDER: [Phase; 8] = [
        Phase::Input,
        Phase::ScriptOnUpdate,
        Phase::CommitMutations,
        Phase::Physics,
        Phase::Collisions,
        Phase::Timers,
        Phase::EmitTrace,
        Phase::BuildRenderSnapshot,
    ];

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Input => "input",
            Self::ScriptOnUpdate => "script_on_update",
            Self::CommitMutations => "commit_mutations",
            Self::Physics => "physics",
            Self::Collisions => "collisions",
            Self::Timers => "timers",
            Self::EmitTrace => "emit_trace",
            Self::BuildRenderSnapshot => "build_render_snapshot",
        }
    }
}

# SA5 N4 physics migration

This checkpoint completes the first authority migration requested by SA5:
movement state now emits intent, Godot `CharacterBody2D` resolves motion, and
the state machine reads the resolved position and velocity back once per Godot
physics frame. No Y8 parity or SA-03 acceptance is claimed by this file.

`MovementTuning.decode()` keeps tick counters, health, damage, stamina, and
inventory counts integral while returning movement distances and speeds as
`float`. Sub-pixel values such as `0.25` pixels per tick are accepted; a
fractional tick duration is rejected. The existing `sa03.tuning.v3` data file
continues to load.

`PhysicsArena2D` derives static fixtures from the read-only `ArenaState`
snapshot. Platforms use a 12-pixel top-surface shape, one-way platforms use a
separate collision layer, solids use their authored extents, and optional
boundary bodies preserve the old horizontal bounds. The adapter owns Nodes;
`ArenaState` remains a serializable `RefCounted` and does not gain engine
objects.

`PhysicsFighter2D` is a feet-origin `CharacterBody2D` adapter. Its collision
shape is offset by `-height/2`, and it converts state velocities expressed in
pixels per 60-Hz tick to Godot pixels per second at the boundary. Each normal
tick calls `set_tick_velocity()`, `set_drop_through()`, `move_fixed_step()`,
then copies the resolved body transform and motion into `FighterState`.
`sync_from_state()` is reserved for spawn/reset teleports; normal ticks do not
overwrite the body transform after `move_and_slide()`.

The focused adapter test is `tests/n4_physics_adapters.gd`. It checks decoder
validation, fixture counts, feet-origin shape geometry, drop-through mask
ownership, and velocity conversion. The guarded PASS is recorded in
`docs/n4-physics-migration-run-02.json` (16 assertions, source hash and real
host exit included).

`tests/n4_physics_tick.gd` remains a standalone live-physics probe. It attaches
the adapters to a live SceneTree, advances one body at the pinned 60-Hz
cadence, and observes solid-floor landing, one-way-deck landing,
per-fighter drop-through, authored stair contact, and the left boundary. The
guarded PASS and its command/source closure are recorded in
`docs/n4-physics-tick-run-04.json`.

The integrated migration was re-run with the full product closure in
`docs/sa5-physics-integration-run-01.json`. It includes focused movement,
sprint, combat, trace, and MovementRoom runs plus the 2,977-assertion
regression run. All commands exited 0 with empty diagnostics and no leftover
processes. These are implementation checks only; reference measurements
A01-A06 and the owner's five-minute side-by-side review are still required
before SA-03 can be accepted.

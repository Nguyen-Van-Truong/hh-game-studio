extends SceneTree
## Seeded movement checks: no claim that seed values match the Y8 reference.
const TraceCore = preload("res://tests/trace_core.gd")
const PhysicsFixture = preload("res://tests/physics_fixture.gd")
var failures: int = 0
var assertions: int = 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	await _test_speed_and_release()
	await _test_window_and_same_tick()
	await _test_exhaustion_and_regeneration()
	await _test_interruptions_and_hash()
	await _test_funded_tick_and_release_burst()
	if failures == 0:
		print("SA-03 sprint states PASS: %d assertions; seeded sprint/stamina/replay" % assertions)
	else:
		printerr("SA-03 sprint states FAIL: %d of %d assertions" % [failures, assertions])
	await PhysicsFixture.cleanup(self)
	quit(0 if failures == 0 else 1)

func _test_speed_and_release() -> void:
	var running := PhysicsFixture.create(self, 301)
	var walking := PhysicsFixture.create(self, 301)
	var twin := PhysicsFixture.create(self, 301)
	# Original east-floor fixture gives an unobstructed comparison lane. This
	# isolates displacement; the room test separately exercises live input.
	for sim: Simulation in [running, walking, twin]:
		sim.place_fighter(0, Vector2(940, sim.world.floor_y))
	var running_held: Dictionary = {}
	var walking_held: Dictionary = {}
	for tick_value: int in range(20):
		var desired: Dictionary = {&"p1_right": tick_value != 1}
		var frame: InputFrame = TraceCore.build_frame(tick_value, running_held, desired)
		_expect(await PhysicsFixture.advance_pair(running, twin, frame), "sprint trace advances both simulations")
		_expect(running.snapshot_hash() == twin.snapshot_hash(), "sprint replay hashes agree per tick")
		running_held = desired
		walking_held = await _step(walking, walking_held, {&"p1_right": true})
	var runner: FighterState = running.fighters[0]
	_expect(runner.position.x > walking.fighters[0].position.x, "double tap produces more displacement than continuous walk")
	_expect(is_equal_approx(runner.velocity.x, float(running.tuning[&"sprint_speed"])), "held sprint reaches its seeded speed")
	_expect(runner.sprint.stamina < int(running.tuning[&"max_stamina"]), "sprint spends stamina")
	_expect(walking.fighters[0].sprint.direction == 0, "single held press never starts sprint")
	_expect(running.fighters[1].sprint.stamina == int(running.tuning[&"max_stamina"]), "P2 resource is independent")
	running_held = await _step(running, running_held, {})
	_expect(runner.sprint.direction == 0, "release stops sprint without stale active input")

func _test_window_and_same_tick() -> void:
	for offset: int in [-1, 0, 1]:
		var sim := PhysicsFixture.create(self, 302 + offset)
		var second_tick: int = int(sim.tuning[&"sprint_tap_window_ticks"]) + offset
		var held: Dictionary = {}
		for tick_value: int in range(second_tick + 1):
			held = await _step(sim, held, {&"p1_right": tick_value == 0 or tick_value == second_tick})
		_expect((sim.fighters[0].sprint.direction == 1) == (offset <= 0), "sprint window includes N and excludes N+1")
	var burst := PhysicsFixture.create(self, 305)
	var buffer := InputBuffer.new()
	for code: int in [KEY_D, KEY_LEFT]:
		buffer.accept_event(_key(code, true))
		buffer.accept_event(_key(code, false))
		buffer.accept_event(_key(code, true))
	_expect(await PhysicsFixture.advance(burst, buffer.build_frame(0)), "same-tick dual-player taps advance")
	_expect(burst.fighters[0].sprint.direction == 1 and burst.fighters[1].sprint.direction == -1, "same-tick presses activate both player directions independently")
	var released := PhysicsFixture.create(self, 306)
	buffer = InputBuffer.new()
	for _tap: int in range(2):
		buffer.accept_event(_key(KEY_D, true))
		buffer.accept_event(_key(KEY_D, false))
	_expect(await PhysicsFixture.advance(released, buffer.build_frame(0)), "completed tap pair validates")
	_expect(released.fighters[0].sprint.direction == 0, "tap pair ending released cannot leave sprint held")

func _test_exhaustion_and_regeneration() -> void:
	var sim := PhysicsFixture.create(self, 307, {&"max_stamina": 12})
	var held: Dictionary = {}
	for tick_value: int in range(9):
		held = await _step(sim, held, {&"p1_right": tick_value != 1})
	_expect(sim.fighters[0].sprint.direction == 0, "exhaustion stops sprint despite held direction")
	_expect(sim.fighters[0].sprint.stamina >= 0, "stamina never underflows")
	for _tick: int in range(12):
		held = await _step(sim, held, {&"p1_right": true})
	_expect(sim.fighters[0].sprint.direction == 0, "regeneration alone does not restart a held sprint")
	var idle := PhysicsFixture.create(self, 308)
	var moving := PhysicsFixture.create(self, 308)
	idle.fighters[0].sprint.stamina = 100
	moving.fighters[0].sprint.stamina = 100
	var idle_held: Dictionary = {}
	var moving_held: Dictionary = {}
	for _tick: int in range(10):
		idle_held = await _step(idle, idle_held, {})
		moving_held = await _step(moving, moving_held, {&"p1_right": true})
	_expect(idle.fighters[0].sprint.stamina > moving.fighters[0].sprint.stamina, "stationary stamina recovery is faster than moving recovery")
	_expect(idle.fighters[0].sprint.stamina <= int(idle.tuning[&"max_stamina"]), "regeneration respects capacity")

func _test_interruptions_and_hash() -> void:
	var sim := PhysicsFixture.create(self, 309)
	var fighter: FighterState = sim.fighters[0]
	var before: String = sim.snapshot_hash()
	fighter.sprint.pending_ticks = 1
	_expect(sim.snapshot_hash() != before, "pending sprint affects canonical hash")
	fighter.sprint.pending_ticks = 0
	fighter.sprint.stamina -= 1
	_expect(sim.snapshot_hash() != before, "stamina affects canonical hash")
	var held: Dictionary = {}
	for tick_value: int in range(3):
		held = await _step(sim, held, {&"p1_right": tick_value != 1})
	_expect(fighter.sprint.direction == 1, "interruption trial starts active")
	held = await _step(sim, held, {&"p1_left": true})
	_expect(fighter.sprint.direction == 0, "reversal requires a new sprint gesture")
	held = await _step(sim, held, {&"p1_left": true, &"p1_right": true})
	_expect(fighter.sprint.direction == 0 and fighter.sprint.pending_ticks == 0, "opposed directions cancel pending and active sprint")
	# Death fixture checks lab reset isolation, not a match respawn law.
	fighter.sprint.pending_ticks = 5
	fighter.locomotion = FighterState.Locomotion.DOWNED
	fighter.downed_ticks = 0
	held = await _step(sim, held, {})
	_expect(fighter.sprint.pending_ticks == 0 and fighter.sprint.direction == 0, "respawn clears gesture")
	_expect(fighter.sprint.stamina == int(sim.tuning[&"max_stamina"]), "lab respawn restores capacity")

func _test_funded_tick_and_release_burst() -> void:
	var sim := PhysicsFixture.create(self, 310)
	var fighter: FighterState = sim.fighters[0]
	sim.place_fighter(0, Vector2(940, sim.world.floor_y))
	var buffer := InputBuffer.new()
	buffer.accept_event(_key(KEY_D, true))
	buffer.accept_event(_key(KEY_D, false))
	buffer.accept_event(_key(KEY_D, true))
	_expect(await PhysicsFixture.advance(sim, buffer.build_frame(sim.tick)), "burst starts seeded sprint")
	sim.place_fighter(0, fighter.position, Vector2(float(sim.tuning[&"sprint_speed"]), fighter.velocity.y), fighter.grounded)
	fighter.sprint.stamina = int(sim.tuning[&"sprint_drain_per_tick"])
	# Re-arm the explicit fixture after place_fighter resets gesture state; the
	# following ticks then isolate the funded movement contract.
	fighter.sprint.direction = 1
	var before_x: float = fighter.position.x
	_expect(await PhysicsFixture.advance(sim, buffer.build_frame(sim.tick)), "last funded sprint tick advances")
	_expect(absf(fighter.position.x - before_x - float(sim.tuning[&"sprint_speed"])) <= 0.1, "last stamina payment buys a complete sprint movement tick")
	_expect(fighter.sprint.stamina == 0, "last funded tick exhausts capacity exactly")
	_expect(await PhysicsFixture.advance(sim, buffer.build_frame(sim.tick)), "exhausted held tick advances")
	_expect(fighter.sprint.direction == 0, "unfunded next tick ends sprint")
	# Restart with enough energy, then release/repress between fixed ticks.
	fighter.sprint.stamina = int(sim.tuning[&"max_stamina"])
	for _tap: int in range(2):
		buffer.accept_event(_key(KEY_D, false))
		buffer.accept_event(_key(KEY_D, true))
	_expect(await PhysicsFixture.advance(sim, buffer.build_frame(sim.tick)), "fresh tap pair restarts sprint")
	_expect(fighter.sprint.direction == 1, "release-burst fixture starts active")
	buffer.accept_event(_key(KEY_D, false))
	buffer.accept_event(_key(KEY_D, true))
	_expect(await PhysicsFixture.advance(sim, buffer.build_frame(sim.tick)), "active release/repress burst advances")
	_expect(fighter.sprint.direction == 0, "one re-press after active release cannot preserve sprint")
	_expect(fighter.sprint.pending_direction == 1, "same-tick re-press arms a new first tap")

func _step(sim: Simulation, previous: Dictionary, desired: Dictionary) -> Dictionary:
	_expect(await PhysicsFixture.advance(sim, TraceCore.build_frame(sim.tick, previous, desired)), "valid movement frame advances")
	return desired.duplicate()

func _key(code: int, down: bool) -> InputEventKey:
	var event := InputEventKey.new()
	event.keycode = code
	event.pressed = down
	return event

func _expect(condition: bool, message: String) -> void:
	assertions += 1
	if not condition:
		failures += 1
		printerr("FAIL: %s" % message)

extends SceneTree
## Focused SA-03 state coverage for the original calibration room.
## These assertions exercise the deterministic core with authored InputFrames;
## the SceneTree movement-room test remains the real input-path proof. Values
## are provisional engineering placeholders and make no Y8 parity claim.

const TraceCore = preload("res://tests/trace_core.gd")

var _failures: int = 0
var _assertions: int = 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	_test_jump_and_land()
	_test_crouch()
	_test_ladder_climb()
	_test_drop_through()
	_test_drop_window_boundaries()
	_test_drop_interruption_and_hash()
	_test_pit_entry()
	if _failures == 0:
		print("SA-03 movement states PASS: %d assertions; jump/land, crouch, ladder, drop-through, pit" % _assertions)
	else:
		printerr("SA-03 movement states FAIL: %d of %d assertions" % [_failures, _assertions])
	quit(0 if _failures == 0 else 1)

func _test_jump_and_land() -> void:
	var simulation := Simulation.new(101)
	var held: Dictionary = {}
	held = _step(simulation, 0, held, {&"p1_up": true}, {&"p1_up": true})
	var jumping: FighterState = simulation.fighters[0]
	_expect(not jumping.grounded, "jump press leaves the floor")
	_expect(jumping.locomotion == FighterState.Locomotion.AIRBORNE, "jump press enters airborne state")
	_expect(jumping.velocity.y < 0, "jump press gives upward velocity")
	_expect(jumping.action_name == &"jump", "jump press records jump action")
	for frame_tick: int in range(1, 45):
		held = _step(simulation, frame_tick, held, {}, {})
	var landed: FighterState = simulation.fighters[0]
	_expect(landed.grounded, "fighter lands after a complete jump arc")
	_expect(landed.position.y == simulation.world.floor_y, "landing resolves to calibration floor")
	_expect(landed.locomotion == FighterState.Locomotion.GROUNDED, "landing returns to grounded state")

func _test_crouch() -> void:
	var simulation := Simulation.new(102)
	var held: Dictionary = {}
	held = _step(simulation, 0, held, {&"p1_down": true}, {&"p1_down": true})
	var fighter: FighterState = simulation.fighters[0]
	_expect(fighter.grounded, "down input keeps floor fighter grounded")
	_expect(fighter.action_name == &"crouch", "held down records crouch action")
	_expect(fighter.position.y == simulation.world.floor_y, "crouch does not move the floor fighter")

func _test_ladder_climb() -> void:
	var simulation := Simulation.new(103)
	var fighter: FighterState = simulation.fighters[0]
	# The authored stair solids intentionally block a straight floor run. Place
	# at the ladder foot so this test isolates the ladder state transition;
	# movement-room input coverage still exercises traversal through SceneTree.
	fighter.position = Vector2i(620, simulation.world.floor_y)
	fighter.grounded = true
	fighter.locomotion = FighterState.Locomotion.GROUNDED
	var held: Dictionary = {}
	held = _step(simulation, 0, held, {&"p1_up": true}, {&"p1_up": true})
	var climbing: FighterState = fighter
	_expect(climbing.locomotion == FighterState.Locomotion.CLIMBING, "up input on ladder enters climbing")
	_expect(climbing.position.y < simulation.world.floor_y, "first climb step moves above floor")
	for frame_tick: int in range(1, 61):
		held = _step(simulation, frame_tick, held, {&"p1_up": true}, {})
	var climbed: FighterState = simulation.fighters[0]
	_expect(climbed.locomotion == FighterState.Locomotion.CLIMBING, "held up remains climbing")
	_expect(climbed.position.y < 600, "held up ascends the ladder")

func _test_drop_through() -> void:
	var simulation := Simulation.new(104)
	var fighter: FighterState = simulation.fighters[0]
	# Fixture placement selects the authored one-way deck; movement-room input
	# coverage separately proves events arrive through the real SceneTree path.
	fighter.position = Vector2i(1100, 572)
	var deck_y: int = fighter.position.y
	fighter.grounded = true
	fighter.locomotion = FighterState.Locomotion.GROUNDED
	var held: Dictionary = {}
	held = _step(simulation, 0, held, {&"p1_down": true}, {&"p1_down": true})
	_expect(fighter.down_tap_window_remaining > 0, "first down tap opens the one-way drop window")
	_expect(fighter.drop_through_ticks == 0, "one down tap does not drop through")
	held = _step(simulation, 1, held, {}, {})
	_expect(fighter.grounded, "single down tap leaves fighter on the one-way deck")
	held = _step(simulation, 2, held, {&"p1_down": true}, {&"p1_down": true})
	_expect(fighter.drop_through_ticks > 0, "second down tap arms one-way drop-through")
	_expect(not fighter.grounded, "drop-through leaves one-way deck")
	_expect(fighter.locomotion == FighterState.Locomotion.FALLING, "drop-through enters falling state")
	for frame_tick: int in range(3, 23):
		held = _step(simulation, frame_tick, held, {}, {})
	_expect(fighter.position.y > deck_y, "drop-through descends below its starting deck")

	var held_simulation := Simulation.new(106)
	var held_fighter: FighterState = held_simulation.fighters[0]
	held_fighter.position = Vector2i(1100, 572)
	held_fighter.grounded = true
	held_fighter.locomotion = FighterState.Locomotion.GROUNDED
	var held_down: Dictionary = {}
	held_down = _step(held_simulation, 0, held_down, {&"p1_down": true}, {&"p1_down": true})
	for frame_tick: int in range(1, int(held_simulation.tuning[&"down_tap_window_ticks"]) + 2):
		held_down = _step(held_simulation, frame_tick, held_down, {&"p1_down": true}, {})
	_expect(held_fighter.grounded, "holding down does not synthesize a second tap")
	_expect(held_fighter.drop_through_ticks == 0, "holding down does not arm drop-through")

	var burst_simulation := Simulation.new(107)
	var burst_fighter: FighterState = burst_simulation.fighters[0]
	burst_fighter.position = Vector2i(1100, 572)
	burst_fighter.grounded = true
	burst_fighter.locomotion = FighterState.Locomotion.GROUNDED
	var burst_buffer: InputBuffer = preload("res://game/core/input_buffer.gd").new()
	burst_buffer.accept_event(_key_event(KEY_S, true))
	burst_buffer.accept_event(_key_event(KEY_S, false))
	burst_buffer.accept_event(_key_event(KEY_S, true))
	var burst_frame: InputFrame = burst_buffer.build_frame(0)
	_expect(burst_frame != null, "same-tick double tap produces a valid frame")
	_expect(burst_simulation.step(burst_frame), "same-tick double tap advances simulation")
	_expect(burst_fighter.drop_through_ticks > 0, "same-tick press-release-press drops through")

	var expired_simulation := Simulation.new(108)
	var expired_fighter: FighterState = expired_simulation.fighters[0]
	expired_fighter.position = Vector2i(1100, 572)
	expired_fighter.grounded = true
	expired_fighter.locomotion = FighterState.Locomotion.GROUNDED
	var expired_held: Dictionary = {}
	expired_held = _step(expired_simulation, 0, expired_held, {&"p1_down": true}, {&"p1_down": true})
	var expiry_tick: int = int(expired_simulation.tuning[&"down_tap_window_ticks"]) + 1
	for frame_tick: int in range(1, expiry_tick):
		expired_held = _step(expired_simulation, frame_tick, expired_held, {}, {})
	expired_held = _step(expired_simulation, expiry_tick, expired_held, {&"p1_down": true}, {&"p1_down": true})
	_expect(expired_fighter.grounded, "tap after the double-tap window stays on the deck")
	_expect(expired_fighter.drop_through_ticks == 0, "expired double-tap window does not drop through")

func _test_drop_window_boundaries() -> void:
	for offset: int in [-1, 0, 1]:
		var simulation: Simulation = _deck_simulation(109 + offset)
		var twin: Simulation = _deck_simulation(109 + offset)
		var window_ticks: int = int(simulation.tuning[&"down_tap_window_ticks"])
		var second_tick: int = window_ticks + offset
		var held: Dictionary = {}
		for frame_tick: int in range(second_tick + 2):
			var desired: Dictionary = {&"p1_down": frame_tick == 0 or frame_tick == second_tick}
			var frame: InputFrame = TraceCore.build_frame(frame_tick, held, desired)
			_expect(simulation.step(frame) and twin.step(frame), "boundary trace advances both deterministic simulations")
			_expect(simulation.snapshot_hash() == twin.snapshot_hash(), "double-tap replay hashes agree on every tick")
			held = desired
		var fighter: FighterState = simulation.fighters[0]
		if offset <= 0:
			_expect(fighter.position.y > 572 and not fighter.grounded, "second tap at N%+d descends below deck" % offset)
		else:
			_expect(fighter.position.y == 572 and fighter.grounded, "second tap after N ticks starts a fresh gesture")

func _test_drop_interruption_and_hash() -> void:
	var simulation: Simulation = _deck_simulation(111)
	var fighter: FighterState = simulation.fighters[0]
	var original_hash: String = simulation.snapshot_hash()
	fighter.down_tap_window_remaining = 1
	_expect(simulation.snapshot_hash() != original_hash, "pending tap participates in canonical replay hash")
	_expect(int(fighter.snapshot()[&"down_tap_window_remaining"]) == 1, "pending tap is visible in snapshot")
	fighter.down_tap_window_remaining = 0
	_expect(simulation.snapshot_hash() == original_hash, "restored tap state restores canonical hash")
	var held: Dictionary = _step(simulation, 0, {}, {&"p1_down": true}, {})
	_expect(fighter.down_tap_window_remaining > 0, "interruption trial first arms a gesture")
	held = _step(simulation, 1, held, {&"p1_up": true}, {})
	_expect(not fighter.grounded and fighter.down_tap_window_remaining == 0, "jump cancels pending platform gesture")
	# Explicit death fixture tests gesture cleanup, not a match elimination rule.
	fighter.locomotion = FighterState.Locomotion.DOWNED
	fighter.downed_ticks = 0
	fighter.down_tap_window_remaining = 5
	fighter.drop_through_ticks = 5
	held = _step(simulation, 2, held, {}, {})
	_expect(fighter.grounded and fighter.health > 0, "calibration-room respawn occurred")
	_expect(fighter.down_tap_window_remaining == 0 and fighter.drop_through_ticks == 0, "respawn carries no pending drop state")
	fighter.position = Vector2i(1100, 572)
	held = _step(simulation, 3, held, {&"p1_down": true}, {})
	_expect(fighter.grounded and fighter.drop_through_ticks == 0, "first press after respawn remains a single tap")
	var solid_simulation := Simulation.new(112)
	var buffer := InputBuffer.new()
	for _tap: int in range(2):
		buffer.accept_event(_key_event(KEY_S, true))
		buffer.accept_event(_key_event(KEY_S, false))
	_expect(solid_simulation.step(buffer.build_frame(0)), "solid-floor double tap advances normally")
	var solid_fighter: FighterState = solid_simulation.fighters[0]
	_expect(solid_fighter.grounded and solid_fighter.position.y == solid_simulation.world.floor_y, "double tap never bypasses a solid floor")
	_expect(solid_fighter.drop_through_ticks == 0 and solid_fighter.down_tap_window_remaining == 0, "solid floor arms no drop state")

func _deck_simulation(seed_value: int) -> Simulation:
	var simulation := Simulation.new(seed_value)
	simulation.fighters[0].position = Vector2i(1100, 572)
	return simulation

func _test_pit_entry() -> void:
	var simulation := Simulation.new(105)
	var fighter: FighterState = simulation.fighters[0]
	# Start at the west lip to isolate the pit transition from traversal.
	fighter.position = Vector2i(748, simulation.world.floor_y)
	fighter.grounded = true
	fighter.locomotion = FighterState.Locomotion.GROUNDED
	var held: Dictionary = {}
	for frame_tick: int in range(10):
		held = _step(simulation, frame_tick, held, {&"p1_right": true}, {&"p1_right": frame_tick == 0})
	_expect(fighter.position.x > 760, "right input crosses west pit lip")
	_expect(fighter.in_pit, "fighter is marked inside authored pit")
	_expect(not fighter.grounded, "pit entry removes grounded state")
	_expect(fighter.locomotion == FighterState.Locomotion.FALLING, "pit entry enters falling state")

func _step(simulation: Simulation, frame_tick: int, previous_held: Dictionary, desired_held: Dictionary, pressed: Dictionary) -> Dictionary:
	var frame: InputFrame = TraceCore.build_frame(frame_tick, previous_held, desired_held, pressed)
	_expect(frame != null, "movement frame %d validates" % frame_tick)
	if frame == null:
		return desired_held.duplicate()
	_expect(simulation.step(frame), "movement frame %d advances simulation" % frame_tick)
	var next_held: Dictionary = desired_held.duplicate()
	for action: StringName in pressed.keys():
		if bool(pressed[action]):
			next_held[action] = true
	return next_held

func _key_event(code: int, is_down: bool) -> InputEventKey:
	var event := InputEventKey.new()
	event.keycode = code
	event.physical_keycode = 0
	event.pressed = is_down
	event.echo = false
	return event

func _expect(condition: bool, message: String) -> void:
	_assertions += 1
	if not condition:
		_failures += 1
		printerr("FAIL: %s" % message)

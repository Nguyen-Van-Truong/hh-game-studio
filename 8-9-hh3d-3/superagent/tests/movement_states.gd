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
	fighter.grounded = true
	fighter.locomotion = FighterState.Locomotion.GROUNDED
	var held: Dictionary = {}
	held = _step(simulation, 0, held, {&"p1_down": true}, {&"p1_down": true})
	_expect(fighter.drop_through_ticks > 0, "down press arms one-way drop-through")
	_expect(not fighter.grounded, "drop-through leaves one-way deck")
	_expect(fighter.locomotion == FighterState.Locomotion.FALLING, "drop-through enters falling state")
	for frame_tick: int in range(1, 21):
		held = _step(simulation, frame_tick, held, {}, {})
	_expect(fighter.position.y > 520, "drop-through descends below deck")

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

func _expect(condition: bool, message: String) -> void:
	_assertions += 1
	if not condition:
		_failures += 1
		printerr("FAIL: %s" % message)

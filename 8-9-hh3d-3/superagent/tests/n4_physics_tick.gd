extends SceneTree
## Live SceneTree physics plumbing for the SA5 N4 adapter seam and regression probe.
##
## This standalone probe complements the integrated Simulation/FighterState path.
## It drives one CharacterBody2D through real physics frames so collision and
## one-way/drop-through postconditions remain independently observable.

const ARENA_SCRIPT = preload("res://game/world/arena_state.gd")
const PHYSICS_ARENA_SCRIPT = preload("res://game/world/physics_arena.gd")
const PHYSICS_FIGHTER_SCRIPT = preload("res://game/fighter/physics_fighter.gd")

const FIXED_DELTA: float = 1.0 / 60.0
const GRAVITY_PER_TICK: float = 5.0

var _assertions: int = 0
var _failures: int = 0


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var arena: RefCounted = ARENA_SCRIPT.new(23) as RefCounted
	var physics_arena: Node = PHYSICS_ARENA_SCRIPT.new() as Node
	get_root().add_child(physics_arena)
	physics_arena.call("configure", arena)
	await physics_frame
	_expect(int(physics_arena.call("fixture_count")) == 11, "live arena builds authored fixtures")
	_expect(int(physics_arena.call("one_way_fixture_count")) == 3, "live arena exposes three one-way decks")

	var floor_fighter: Node = PHYSICS_FIGHTER_SCRIPT.new() as Node
	get_root().add_child(floor_fighter)
	floor_fighter.call("configure", Vector2(28.0, 48.0))
	floor_fighter.call("sync_from_state", Vector2(80.0, 600.0), Vector2.ZERO)
	await physics_frame
	await _step_body(floor_fighter, 60)
	var floor_motion: Dictionary = floor_fighter.call("read_motion")
	var floor_position: Vector2 = Vector2(floor_motion[&"position"])
	_expect(is_equal_approx(floor_position.y, 740.0), "CharacterBody2D settles on solid floor top")
	_expect(bool(floor_motion[&"grounded"]), "solid floor reports grounded")
	_expect(Vector2(floor_motion[&"floor_normal"]).y < -0.9, "solid floor reports upward normal")

	var deck_fighter: Node = PHYSICS_FIGHTER_SCRIPT.new() as Node
	get_root().add_child(deck_fighter)
	deck_fighter.call("configure", Vector2(28.0, 48.0))
	deck_fighter.call("sync_from_state", Vector2(1100.0, 500.0), Vector2.ZERO)
	await physics_frame
	await _step_body(deck_fighter, 60)
	var deck_motion: Dictionary = deck_fighter.call("read_motion")
	var deck_position: Vector2 = Vector2(deck_motion[&"position"])
	_expect(absf(deck_position.y - 572.0) <= 0.05, "CharacterBody2D lands on one-way deck top")
	_expect(bool(deck_motion[&"grounded"]), "one-way deck reports grounded")
	deck_fighter.call("set_drop_through", true)
	await _step_body(deck_fighter, 12)
	var dropped_motion: Dictionary = deck_fighter.call("read_motion")
	var dropped_position: Vector2 = Vector2(dropped_motion[&"position"])
	_expect(dropped_position.y > 572.0, "per-fighter drop-through mask permits descent")
	_expect(bool(dropped_motion[&"drop_through"]), "drop-through state remains local to fighter")
	_expect(is_finite(dropped_position.x) and is_finite(dropped_position.y), "physics readback remains finite")

	var stair_fighter: Node = PHYSICS_FIGHTER_SCRIPT.new() as Node
	get_root().add_child(stair_fighter)
	stair_fighter.call("configure", Vector2(28.0, 48.0))
	stair_fighter.call("sync_from_state", Vector2(200.0, 600.0), Vector2.ZERO)
	await physics_frame
	await _step_body(stair_fighter, 60)
	var stair_motion: Dictionary = stair_fighter.call("read_motion")
	var stair_position: Vector2 = Vector2(stair_motion[&"position"])
	_expect(absf(stair_position.y - 692.0) <= 0.05, "CharacterBody2D settles on authored stair top")
	_expect(bool(stair_motion[&"grounded"]), "stair contact reports grounded")

	var boundary_fighter: Node = PHYSICS_FIGHTER_SCRIPT.new() as Node
	get_root().add_child(boundary_fighter)
	boundary_fighter.call("configure", Vector2(28.0, 48.0))
	boundary_fighter.call("sync_from_state", Vector2(30.0, 740.0), Vector2(-10.0, 0.0))
	await physics_frame
	for _tick: int in range(12):
		boundary_fighter.call("move_fixed_step")
		await physics_frame
	var boundary_motion: Dictionary = boundary_fighter.call("read_motion")
	var boundary_position: Vector2 = Vector2(boundary_motion[&"position"])
	_expect(boundary_position.x >= 13.9, "left boundary prevents body escape")

	floor_fighter.queue_free()
	deck_fighter.queue_free()
	stair_fighter.queue_free()
	boundary_fighter.queue_free()
	physics_arena.queue_free()
	if _failures == 0:
		print("SA5 N4 physics tick PASS: %d assertions; live floor/one-way/drop-through" % _assertions)
	else:
		printerr("SA5 N4 physics tick FAIL: %d of %d assertions" % [_failures, _assertions])
	quit(0 if _failures == 0 else 1)


func _step_body(body: Node, ticks: int) -> void:
	for _tick: int in range(ticks):
		body.call("add_tick_gravity", GRAVITY_PER_TICK, FIXED_DELTA)
		body.call("move_fixed_step")
		await physics_frame


func _expect(condition: bool, message: String) -> void:
	_assertions += 1
	if not condition:
		_failures += 1
		printerr("FAIL: %s" % message)

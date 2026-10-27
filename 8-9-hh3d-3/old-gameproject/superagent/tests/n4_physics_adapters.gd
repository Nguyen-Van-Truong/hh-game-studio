extends SceneTree
## Focused SA5 N4 seam checks.  These do not switch MovementRoom authority;
## they prove float tuning and the standalone Godot fixture adapters compile
## and expose the conversion/postcondition API for the next migration step.

const TUNING_SCRIPT = preload("res://game/core/movement_tuning.gd")
const ARENA_SCRIPT = preload("res://game/world/arena_state.gd")
const PHYSICS_ARENA_SCRIPT = preload("res://game/world/physics_arena.gd")
const PHYSICS_FIGHTER_SCRIPT = preload("res://game/fighter/physics_fighter.gd")

var _assertions: int = 0
var _failures: int = 0


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	_test_float_tuning()
	_test_physics_fixture_seam()
	if _failures == 0:
		print("SA5 N4 adapter seam PASS: %d assertions; float tuning/fixtures/conversion" % _assertions)
	else:
		printerr("SA5 N4 adapter seam FAIL: %d of %d assertions" % [_failures, _assertions])
	quit(0 if _failures == 0 else 1)


func _test_float_tuning() -> void:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://data/tuning.json"))
	_expect(typeof(parsed) == TYPE_DICTIONARY, "seed tuning JSON parses")
	if typeof(parsed) != TYPE_DICTIONARY:
		return
	var baseline: Dictionary = Dictionary(parsed)
	var baseline_values: Dictionary = TUNING_SCRIPT.decode(baseline)
	_expect(not baseline_values.is_empty(), "baseline tuning remains accepted")
	_expect(typeof(baseline_values.get(&"max_horizontal_speed")) == TYPE_FLOAT, "movement speed is float-capable")
	_expect(typeof(baseline_values.get(&"jump_lock_ticks")) == TYPE_INT, "tick duration remains integral")

	var fractional: Dictionary = baseline.duplicate(true)
	var fractional_movement: Dictionary = Dictionary(fractional["movement"])
	fractional_movement["max_horizontal_speed"] = 0.25
	fractional_movement["acceleration_per_tick"] = 0.125
	fractional["movement"] = fractional_movement
	var fractional_values: Dictionary = TUNING_SCRIPT.decode(fractional)
	_expect(not fractional_values.is_empty(), "sub-pixel movement tuning is accepted")
	if not fractional_values.is_empty():
		_expect(is_equal_approx(float(fractional_values[&"max_horizontal_speed"]), 0.25), "fractional speed is preserved")
		_expect(is_equal_approx(float(fractional_values[&"acceleration_per_tick"]), 0.125), "fractional acceleration is preserved")

	var invalid_duration: Dictionary = baseline.duplicate(true)
	var invalid_movement: Dictionary = Dictionary(invalid_duration["movement"])
	invalid_movement["jump_lock_ticks"] = 1.5
	invalid_duration["movement"] = invalid_movement
	_expect(TUNING_SCRIPT.decode(invalid_duration).is_empty(), "fractional tick duration is rejected")


func _test_physics_fixture_seam() -> void:
	var arena: RefCounted = ARENA_SCRIPT.new(11) as RefCounted
	var physics_arena: Node = PHYSICS_ARENA_SCRIPT.new() as Node
	get_root().add_child(physics_arena)
	physics_arena.call("configure", arena)
	_expect(int(physics_arena.call("fixture_count")) == 11, "fixture builder creates platforms, solids and boundaries")
	_expect(int(physics_arena.call("one_way_fixture_count")) == 3, "one-way platform count matches authored topology")

	var fighter: Node = PHYSICS_FIGHTER_SCRIPT.new() as Node
	get_root().add_child(fighter)
	fighter.call("configure", Vector2(28.0, 48.0))
	fighter.call("sync_from_state", Vector2(80.0, 740.0), Vector2(0.25, -1.5))
	var motion: Dictionary = fighter.call("read_motion")
	_expect(is_equal_approx(Vector2(motion[&"position"]).x, 80.0), "fighter seam preserves float position")
	_expect(is_equal_approx(Vector2(motion[&"velocity"]).y, -1.5), "tick velocity converts back from Godot units")
	_expect(fighter.get_node_or_null("CollisionShape2D") != null, "fighter seam creates a collision shape")
	var shape: CollisionShape2D = fighter.get_node("CollisionShape2D") as CollisionShape2D
	_expect(is_equal_approx(shape.position.y, -24.0), "feet-origin shape offset is explicit")
	fighter.call("set_drop_through", true)
	_expect(bool(fighter.call("is_drop_through_active")), "drop-through state is local to the fighter")
	fighter.call("set_drop_through", false)
	_expect(not bool(fighter.call("is_drop_through_active")), "drop-through can be restored")
	fighter.queue_free()
	physics_arena.queue_free()


func _expect(condition: bool, message: String) -> void:
	_assertions += 1
	if not condition:
		_failures += 1
		printerr("FAIL: %s" % message)

extends SceneTree
## SA-03 scene-level smoke checks. This verifies the provisional room consumes
## real InputEventKey instances through its semantic input handler; it does not
## claim reference parity. SceneTree dispatch itself is covered by SA-01.

const ROOM_SCENE = preload("res://movement_room.tscn")

var _failures: int = 0
var _assertions: int = 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var room := ROOM_SCENE.instantiate()
	get_root().add_child(room)
	await process_frame
	_expect(room is MovementRoom, "movement room scene must instantiate its typed controller")
	if not room is MovementRoom:
		quit(1)
		return
	var movement_room: MovementRoom = room as MovementRoom
	var initial: Dictionary = movement_room.read_snapshot()
	_expect(initial.get(&"schema", &"") == &"sa03.simulation.v2", "room exposes v2 simulation snapshot")
	_expect(int(initial.get(&"fixed_hz", 0)) == 60, "room simulation is fixed at 60 Hz")
	var world: Dictionary = initial.get(&"world", {})
	_expect(world.get(&"schema", &"") == &"sa03.arena.v2", "room exposes arena v2")
	_expect(_array_size(world, &"solids") >= 4, "room has original solid test geometry")
	_expect(_array_size(world, &"spawns") == 2, "room has two distinct fighter spawns")
	_expect(movement_room.get_node_or_null("Fighter1") is FighterView, "P1 view is visual-only FighterView")
	_expect(movement_room.get_node_or_null("Fighter2") is FighterView, "P2 view is visual-only FighterView")

	var p1_before_x: int = _fighter_x(initial, 0)
	movement_room._input(_key_event(KEY_RIGHT, true))
	_step_room(movement_room)
	var p1_frame: InputFrame = movement_room.read_last_frame()
	var p1_right: Dictionary = _record_for(p1_frame, &"p1_right", 1)
	_expect(bool(p1_right.get(&"pressed", false)), "P1 right pressed edge reaches room")
	_expect(bool(p1_right.get(&"held", false)), "P1 right held state reaches room")
	var p1_moved: Dictionary = movement_room.read_snapshot()
	_expect(_fighter_x(p1_moved, 0) != p1_before_x, "P1 movement changes simulation state")

	movement_room._input(_key_event(KEY_RIGHT, false))
	_step_room(movement_room)
	var p1_release: Dictionary = _record_for(movement_room.read_last_frame(), &"p1_right", 1)
	_expect(bool(p1_release.get(&"released", false)), "P1 release edge reaches room")
	_expect(not bool(p1_release.get(&"held", true)), "P1 held state clears after keyup")

	var p2_before_x: int = _fighter_x(movement_room.read_snapshot(), 1)
	movement_room._input(_key_event(KEY_D, true))
	_step_room(movement_room)
	var p2_frame: InputFrame = movement_room.read_last_frame()
	var p2_right: Dictionary = _record_for(p2_frame, &"p2_right", 2)
	_expect(bool(p2_right.get(&"pressed", false)), "P2 right pressed edge reaches room independently")
	_expect(bool(p2_right.get(&"held", false)), "P2 right held state reaches room independently")
	_expect(_fighter_x(movement_room.read_snapshot(), 1) != p2_before_x, "P2 movement changes simulation state")
	movement_room._input(_key_event(KEY_D, false))
	_step_room(movement_room)

	movement_room._input(_key_event(KEY_R, true))
	var reset_snapshot: Dictionary = movement_room.read_snapshot()
	_expect(int(reset_snapshot.get(&"tick", -1)) == 0, "R resets the room through its input path")
	_expect(movement_room.read_last_frame() == null, "reset clears the previous frame")

	movement_room._input(_key_event(KEY_RIGHT, false))
	movement_room._input(_key_event(KEY_D, false))
	room.queue_free()
	await process_frame
	if _failures == 0:
		print("SA-03 movement room PASS: %d assertions; scene/input/fixed-step/reset" % _assertions)
	else:
		printerr("SA-03 movement room FAIL: %d of %d assertions" % [_failures, _assertions])
	quit(0 if _failures == 0 else 1)

func _key_event(code: int, is_down: bool) -> InputEventKey:
	var event := InputEventKey.new()
	event.keycode = code
	event.physical_keycode = 0
	event.pressed = is_down
	event.echo = false
	return event

func _record_for(frame: InputFrame, action: StringName, player: int) -> Dictionary:
	if frame == null:
		return {}
	for record: Dictionary in frame.records():
		if record.get(&"action") == action and int(record.get(&"player", 0)) == player:
			return record
	return {}

func _step_room(room: MovementRoom) -> void:
	# One explicit fixed step avoids scheduler timing obscuring pressed/released
	# edges while still exercising the scene controller and InputBuffer together.
	room._physics_process(1.0 / 60.0)

func _array_size(container: Dictionary, key: StringName) -> int:
	var value: Variant = container.get(key, [])
	if typeof(value) != TYPE_ARRAY:
		return -1
	return Array(value).size()

func _fighter_x(snapshot: Dictionary, index: int) -> int:
	var value: Variant = snapshot.get(&"fighters", [])
	if typeof(value) != TYPE_ARRAY:
		return 0
	var fighters: Array = Array(value)
	if index < 0 or index >= fighters.size() or typeof(fighters[index]) != TYPE_DICTIONARY:
		return 0
	var fighter: Dictionary = Dictionary(fighters[index])
	return int(fighter.get(&"x", 0))

func _expect(condition: bool, message: String) -> void:
	_assertions += 1
	if not condition:
		_failures += 1
		printerr("FAIL: %s" % message)

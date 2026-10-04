extends SceneTree
## SA-03 scene-level checks. Input is injected through the live SceneTree and
## observations are taken only after the room's normal fixed-step signal. This
## is implementation evidence, not a reference-parity claim.

const BOOTSTRAP_SCENE: String = "res://main.tscn"

var _failures: int = 0
var _assertions: int = 0
var _trace: Array[Dictionary] = []
var _finished: bool = false

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	create_timer(15.0).timeout.connect(_on_timeout)
	change_scene_to_file(BOOTSTRAP_SCENE)
	_expect(await _await_scene_name(&"SuperagentBootstrap"), "bootstrap scene must load")
	if _failures > 0:
		_finish()
		return

	_parse_key(KEY_ENTER, true)
	_expect(await _await_scene_name(&"MovementRoom"), "Enter must enter movement room through SceneTree input")
	if _failures > 0:
		_finish()
		return
	_parse_key(KEY_ENTER, false)
	var movement_room: MovementRoom = current_scene as MovementRoom
	_expect(movement_room != null, "movement room scene must instantiate its typed controller")
	if movement_room == null:
		_finish()
		return

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
	_parse_key(KEY_D, true)
	var p1_frame: InputFrame = await _sample_step(movement_room, &"p1-right-pressed")
	var p1_right: Dictionary = _record_for(p1_frame, &"p1_right", 1)
	_expect(bool(p1_right.get(&"pressed", false)), "P1 right pressed edge reaches room")
	_expect(bool(p1_right.get(&"held", false)), "P1 right held state reaches room")
	var p1_moved: Dictionary = movement_room.read_snapshot()
	_expect(_fighter_x(p1_moved, 0) != p1_before_x, "P1 movement changes simulation state")

	var p1_held_frame: InputFrame = await _sample_step(movement_room, &"p1-right-held")
	var p1_held: Dictionary = _record_for(p1_held_frame, &"p1_right", 1)
	_expect(not bool(p1_held.get(&"pressed", true)), "P1 pressed edge clears on the next tick")
	_expect(bool(p1_held.get(&"initial_held", false)), "P1 held state carries across ticks")
	_expect(bool(p1_held.get(&"held", false)), "P1 remains held without a repeat keydown")

	var p2_before_x: int = _fighter_x(movement_room.read_snapshot(), 1)
	_parse_key(KEY_RIGHT, true)
	var p2_frame: InputFrame = await _sample_step(movement_room, &"p2-right-pressed")
	var p2_right: Dictionary = _record_for(p2_frame, &"p2_right", 2)
	_expect(bool(p2_right.get(&"pressed", false)), "P2 right pressed edge reaches room independently")
	_expect(bool(p2_right.get(&"held", false)), "P2 right held state reaches room independently")
	_expect(bool(_record_for(p2_frame, &"p1_right", 1).get(&"held", false)), "P1 remains held while P2 presses")
	_expect(_fighter_x(movement_room.read_snapshot(), 1) != p2_before_x, "P2 movement changes simulation state")

	_parse_key(KEY_D, false)
	_parse_key(KEY_RIGHT, false)
	var release_frame: InputFrame = await _sample_step(movement_room, &"p1-p2-release")
	var p1_release: Dictionary = _record_for(release_frame, &"p1_right", 1)
	var p2_release: Dictionary = _record_for(release_frame, &"p2_right", 2)
	_expect(bool(p1_release.get(&"released", false)), "P1 release edge reaches room")
	_expect(not bool(p1_release.get(&"held", true)), "P1 held state clears after keyup")
	_expect(bool(p2_release.get(&"released", false)), "P2 release edge reaches room independently")
	_expect(not bool(p2_release.get(&"held", true)), "P2 held state clears after keyup")
	var idle_frame: InputFrame = await _sample_step(movement_room, &"post-release-idle")
	_expect(_frame_is_idle(idle_frame), "released keys do not leave stale edges on the next tick")

	_parse_key(KEY_D, true)
	_parse_key(KEY_RIGHT, true)
	var focus_held_frame: InputFrame = await _sample_step(movement_room, &"focus-held")
	_expect(bool(_record_for(focus_held_frame, &"p1_right", 1).get(&"held", false)), "P1 is held before focus loss")
	_expect(bool(_record_for(focus_held_frame, &"p2_right", 2).get(&"held", false)), "P2 is held before focus loss")
	# Headless Godot cannot produce an OS focus transition; deliver the same
	# SceneTree notification that the runtime sends to the room controller.
	movement_room.notification(NOTIFICATION_APPLICATION_FOCUS_OUT)
	var focus_release_frame: InputFrame = await _sample_step(movement_room, &"focus-release")
	_expect(bool(_record_for(focus_release_frame, &"p1_right", 1).get(&"released", false)), "focus loss releases P1")
	_expect(bool(_record_for(focus_release_frame, &"p2_right", 2).get(&"released", false)), "focus loss releases P2")
	_expect(not bool(_record_for(focus_release_frame, &"p1_right", 1).get(&"held", true)), "focus loss clears P1 held")
	_expect(not bool(_record_for(focus_release_frame, &"p2_right", 2).get(&"held", true)), "focus loss clears P2 held")

	_parse_key(KEY_D, true)
	_parse_key(KEY_RIGHT, true)
	var reset_held_frame: InputFrame = await _sample_step(movement_room, &"reset-held")
	_expect(bool(_record_for(reset_held_frame, &"p1_right", 1).get(&"held", false)), "P1 held state exists before reset")
	_expect(bool(_record_for(reset_held_frame, &"p2_right", 2).get(&"held", false)), "P2 held state exists before reset")
	_parse_key(KEY_R, true)
	await process_frame
	await process_frame
	var reset_snapshot: Dictionary = movement_room.read_snapshot()
	_expect(int(reset_snapshot.get(&"tick", -1)) == 0, "R resets the room through its input path")
	_expect(movement_room.read_last_frame() == null, "reset clears the previous frame")
	_parse_key(KEY_R, false)
	var reset_first_frame: InputFrame = await _sample_step(movement_room, &"reset-first-tick")
	_expect(int(reset_first_frame.tick()) == 0, "reset first tick starts at zero")
	_expect(_frame_is_idle(reset_first_frame), "reset cancels held input without stale first-tick edges")

	_parse_key(KEY_ESCAPE, true)
	_expect(await _await_scene_name(&"SuperagentBootstrap"), "Escape must return to bootstrap through SceneTree input")
	_parse_key(KEY_ESCAPE, false)
	_expect(_trace.size() >= 9, "per-tick input trace captures the integration sequence")
	_finish()

func _on_timeout() -> void:
	if _finished:
		return
	_finished = true
	printerr("SA-03 movement room FAIL: watchdog; %d of %d assertions" % [_failures + 1, _assertions])
	quit(1)

func _finish() -> void:
	if _finished:
		return
	_finished = true
	if _failures == 0:
		print("SA-03 movement room PASS: %d assertions; SceneTree input/fixed-step/menu/reset/focus" % _assertions)
	else:
		printerr("SA-03 movement room FAIL: %d of %d assertions" % [_failures, _assertions])
	quit(0 if _failures == 0 else 1)

func _await_scene_name(expected: StringName) -> bool:
	for _attempt: int in range(90):
		var current: Node = current_scene
		if current != null and StringName(current.name) == expected:
			return true
		await process_frame
	return false

func _sample_step(room: MovementRoom, label: StringName) -> InputFrame:
	var frame: InputFrame = await room.fixed_step_completed
	_expect(frame != null, "%s must produce a typed fixed-step frame" % String(label))
	if frame != null:
		var snapshot: Dictionary = room.read_snapshot()
		_trace.append({&"label": label, &"tick": frame.tick(), &"snapshot": snapshot, &"frame": frame})
		_expect(int(snapshot.get(&"last_input_tick", -1)) == frame.tick(), "%s frame and simulation ticks agree" % String(label))
	return frame

func _frame_is_idle(frame: InputFrame) -> bool:
	if frame == null:
		return false
	for record: Dictionary in frame.records():
		if not _events_for(record).is_empty() or bool(record.get(&"initial_held", true)):
			return false
		if bool(record.get(&"pressed", true)) or bool(record.get(&"held", true)) or bool(record.get(&"released", true)):
			return false
	return true

func _parse_key(code: int, is_down: bool) -> void:
	Input.parse_input_event(_key_event(code, is_down))

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

func _events_for(record: Dictionary) -> Array:
	var events_value: Variant = record.get(&"events", [])
	if typeof(events_value) != TYPE_ARRAY:
		return []
	return Array(events_value)

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

extends SceneTree
## SA-01 focused checks. The coordinator runs this through run_guarded.py when GT06 is idle.

const InputFrameType = preload("res://game/core/input_frame.gd")
const InputBufferType = preload("res://game/core/input_buffer.gd")

const EXPECTED_CODES: Dictionary = {
	&"p1_left": 4194319, &"p1_right": 4194321, &"p1_up": 4194320, &"p1_down": 4194322,
	&"p1_punch": 78, &"p1_shoot": 77, &"p1_throw": 44, &"p1_power": 46,
	&"p2_left": 65, &"p2_right": 68, &"p2_up": 87, &"p2_down": 83,
	&"p2_punch": 49, &"p2_shoot": 50, &"p2_throw": 51, &"p2_power": 52,
}

var _failures: int = 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	_test_input_map()
	_test_input_frame_validation()
	_test_real_input_edges()
	if _failures == 0:
		print("SA-01 tests PASS: InputMap, immutable frame validation, and input edges")
	else:
		printerr("SA-01 tests FAIL: %d assertion(s)" % _failures)
	quit(_failures)

func _test_input_map() -> void:
	var seen_codes: Dictionary = {}
	for action: StringName in EXPECTED_CODES.keys():
		_expect(InputMap.has_action(action), "missing action %s" % action)
		var events: Array[InputEvent] = InputMap.action_get_events(action)
		_expect(events.size() == 1, "%s must have exactly one event" % action)
		if events.is_empty():
			continue
		var key_event: InputEventKey = events[0] as InputEventKey
		_expect(key_event != null, "%s event must be InputEventKey" % action)
		if key_event == null:
			continue
		var expected_code: int = int(EXPECTED_CODES[action])
		_expect(key_event.physical_keycode == expected_code, "%s physical key mismatch" % action)
		_expect(not seen_codes.has(expected_code), "duplicate physical key code %d" % expected_code)
		seen_codes[expected_code] = action
	_expect(seen_codes.size() == EXPECTED_CODES.size(), "P1/P2 key map must be one-to-one")

func _test_input_frame_validation() -> void:
	var valid_records: Array[Dictionary] = [{
		&"tick": 7, &"player": 1, &"action": &"p1_punch",
		&"pressed": true, &"held": true, &"released": false,
	}]
	var valid_frame: InputFrame = InputFrameType.create(7, valid_records)
	_expect(valid_frame != null, "valid frame should be accepted")
	if valid_frame != null:
		_expect(valid_frame.tick() == 7, "frame tick must be retained")
		_expect(valid_frame.records().is_read_only(), "records must be immutable")
	var pressed_without_held: Array[Dictionary] = [{
		&"tick": 7, &"player": 1, &"action": &"p1_punch",
		&"pressed": true, &"held": false, &"released": false,
	}]
	_expect(InputFrameType.create(7, pressed_without_held) == null, "pressed without held must reject")
	var both_edges: Array[Dictionary] = [{
		&"tick": 7, &"player": 1, &"action": &"p1_punch",
		&"pressed": true, &"held": true, &"released": true,
	}]
	_expect(InputFrameType.create(7, both_edges) == null, "pressed and released together must reject")

func _test_real_input_edges() -> void:
	var buffer: InputBuffer = InputBufferType.new()
	var down: InputEventKey = _key_event(78, true)
	buffer.accept_event(down)
	buffer.accept_event(down)
	var first: InputFrame = buffer.build_frame(1)
	var first_punch: Dictionary = _record_for(first, &"p1_punch")
	_expect(bool(first_punch[&"pressed"]), "first key event must produce pressed edge")
	_expect(bool(first_punch[&"held"]), "first key event must produce held state")
	_expect(not bool(first_punch[&"released"]), "first key event must not release")
	var held: InputFrame = buffer.build_frame(2)
	var held_punch: Dictionary = _record_for(held, &"p1_punch")
	_expect(not bool(held_punch[&"pressed"]), "duplicate keydown must be deduplicated")
	_expect(bool(held_punch[&"held"]), "held state survives frame boundary")
	var up: InputEventKey = _key_event(78, false)
	buffer.accept_event(up)
	var released: InputFrame = buffer.build_frame(3)
	var released_punch: Dictionary = _record_for(released, &"p1_punch")
	_expect(not bool(released_punch[&"held"]), "keyup must clear held state")
	_expect(bool(released_punch[&"released"]), "keyup must produce released edge")

func _key_event(physical_code: int, is_down: bool) -> InputEventKey:
	var event: InputEventKey = InputEventKey.new()
	event.physical_keycode = physical_code
	event.keycode = physical_code
	event.pressed = is_down
	event.echo = false
	return event

func _record_for(frame: InputFrame, action: StringName) -> Dictionary:
	for record: Dictionary in frame.records():
		if StringName(record[&"action"]) == action and int(record[&"player"]) == 1:
			return record
	return {}

func _expect(condition: bool, message: String) -> void:
	if not condition:
		_failures += 1
		printerr("FAIL: %s" % message)

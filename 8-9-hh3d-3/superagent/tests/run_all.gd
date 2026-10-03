extends SceneTree
## SA-01 focused checks. The coordinator runs this through run_guarded.py when GT06 is idle.

const InputFrameType = preload("res://game/core/input_frame.gd")
const InputBufferType = preload("res://game/core/input_buffer.gd")

class InputHarness extends RefCounted:
	var _buffer: InputBuffer

	func _init(buffer: InputBuffer) -> void:
		_buffer = buffer

	func _input(event: InputEvent) -> void:
		_buffer.accept_event(event)

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
	_test_focus_cancel_and_echo()
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
		_expect(key_event.keycode == expected_code, "%s keycode mismatch" % action)
		_expect(key_event.physical_keycode == 0, "%s must not use physical_keycode" % action)
		_expect(not seen_codes.has(expected_code), "duplicate key code %d" % expected_code)
		seen_codes[expected_code] = action
	_expect(seen_codes.size() == EXPECTED_CODES.size(), "P1/P2 key map must be one-to-one")

func _test_input_frame_validation() -> void:
	var valid_records: Array[Dictionary] = _empty_records(7)
	var valid_frame: InputFrame = InputFrameType.create(7, valid_records)
	_expect(valid_frame != null, "valid frame should be accepted")
	if valid_frame != null:
		_expect(valid_frame.tick() == 7, "frame tick must be retained")
		_expect(valid_frame.records().is_read_only(), "records must be immutable")
		_expect((valid_frame.records()[0][&"events"] as Array).is_read_only(), "edge list must be immutable")

	var extra: Array[Dictionary] = valid_records.duplicate()
	extra[0] = extra[0].duplicate()
	extra[0][&"extra"] = true
	_expect(InputFrameType.create(7, extra) == null, "extra record key must reject")

	var wrong_tick: Array[Dictionary] = valid_records.duplicate()
	wrong_tick[0] = wrong_tick[0].duplicate()
	wrong_tick[0][&"tick"] = "7"
	_expect(InputFrameType.create(7, wrong_tick) == null, "wrong tick type must reject")

	var wrong_player: Array[Dictionary] = valid_records.duplicate()
	wrong_player[0] = wrong_player[0].duplicate()
	wrong_player[0][&"player"] = 2
	_expect(InputFrameType.create(7, wrong_player) == null, "action-owner mismatch must reject")

	var unknown_action: Array[Dictionary] = valid_records.duplicate()
	unknown_action[0] = unknown_action[0].duplicate()
	unknown_action[0][&"action"] = &"p1_unknown"
	_expect(InputFrameType.create(7, unknown_action) == null, "unknown action must reject")

	var duplicate_action: Array[Dictionary] = valid_records.duplicate()
	duplicate_action[1] = duplicate_action[0].duplicate()
	_expect(InputFrameType.create(7, duplicate_action) == null, "duplicate action must reject")

	var wrong_schema: Array[Dictionary] = valid_records.duplicate()
	wrong_schema[0] = wrong_schema[0].duplicate()
	wrong_schema[0][&"schema_version"] = 99
	_expect(InputFrameType.create(7, wrong_schema) == null, "wrong schema version must reject")

	var fast_tap: Array[Dictionary] = valid_records.duplicate()
	fast_tap[0] = fast_tap[0].duplicate()
	fast_tap[0][&"events"] = [&"pressed", &"released", &"pressed"]
	fast_tap[0][&"pressed"] = true
	fast_tap[0][&"released"] = true
	fast_tap[0][&"held"] = true
	_expect(InputFrameType.create(7, fast_tap) != null, "ordered press-release-press must be accepted")

func _test_real_input_edges() -> void:
	var buffer: InputBuffer = InputBufferType.new()
	var harness := InputHarness.new(buffer)
	harness._input(_key_event(78, true))
	harness._input(_key_event(49, true))
	var frame: InputFrame = buffer.build_frame(1)
	var p1: Dictionary = _record_for(frame, &"p1_punch", 1)
	var p2: Dictionary = _record_for(frame, &"p2_punch", 2)
	_expect(bool(p1[&"pressed"]) and bool(p1[&"held"]), "P1 key must route independently")
	_expect(bool(p2[&"pressed"]) and bool(p2[&"held"]), "P2 key must route independently")
	_expect((p1[&"events"] as Array).size() == 1 and (p2[&"events"] as Array).size() == 1, "one edge per action")
	var held: InputFrame = buffer.build_frame(2)
	_expect(not bool(_record_for(held, &"p1_punch", 1)[&"pressed"]), "pressed resets at frame boundary")
	_expect(bool(_record_for(held, &"p1_punch", 1)[&"held"]), "held survives frame boundary")

	harness._input(_key_event(78, false))
	harness._input(_key_event(78, true))
	var tap_frame: InputFrame = buffer.build_frame(3)
	var tap: Dictionary = _record_for(tap_frame, &"p1_punch", 1)
	var tap_events: Array = tap[&"events"]
	_expect(tap_events.size() == 2 and tap_events[0] == &"released" and tap_events[1] == &"pressed", "ordered release-press must survive")
	_expect(bool(tap[&"held"]), "end-held state follows final edge")

func _test_focus_cancel_and_echo() -> void:
	var buffer: InputBuffer = InputBufferType.new()
	var harness := InputHarness.new(buffer)
	var echo_down := _key_event(78, true)
	echo_down.echo = true
	harness._input(echo_down)
	var no_echo_frame: InputFrame = buffer.build_frame(1)
	_expect(not bool(_record_for(no_echo_frame, &"p1_punch", 1)[&"pressed"]), "echo keydown must be ignored")
	harness._input(_key_event(78, true))
	var held_echo := _key_event(78, true)
	held_echo.echo = true
	harness._input(held_echo)
	buffer.cancel_all()
	var cancelled: Dictionary = _record_for(buffer.build_frame(2), &"p1_punch", 1)
	_expect(bool(cancelled[&"released"]) and not bool(cancelled[&"held"]), "cancel must release held action")
	_expect((cancelled[&"events"] as Array) == [&"pressed", &"released"], "cancel preserves press then release")

func _empty_records(frame_tick: int) -> Array[Dictionary]:
	var records: Array[Dictionary] = []
	for action: StringName in InputFrameType.ACTIONS:
		var player: int = 1 if String(action).begins_with("p1_") else 2
		records.append({
			&"schema_version": InputFrameType.SCHEMA_VERSION,
			&"tick": frame_tick,
			&"player": player,
			&"action": action,
			&"initial_held": false,
			&"events": [],
			&"pressed": false,
			&"held": false,
			&"released": false,
		})
	return records

func _key_event(code: int, is_down: bool) -> InputEventKey:
	var event := InputEventKey.new()
	event.keycode = code
		event.pressed = is_down
	event.echo = false
	return event

func _record_for(frame: InputFrame, action: StringName, player: int) -> Dictionary:
	for record: Dictionary in frame.records():
		if record[&"action"] == action and record[&"player"] == player:
			return record
	return {}

func _expect(condition: bool, message: String) -> void:
	if not condition:
		_failures += 1
		printerr("FAIL: %s" % message)

extends SceneTree
## SA-01 focused checks. The coordinator runs this through run_guarded.py when GT06 is idle.

const InputFrameType = preload("res://game/core/input_frame.gd")
const InputBufferType = preload("res://game/core/input_buffer.gd")

## Integration listener is registered in the live SceneTree before injection.
## Unit checks below call InputBuffer directly and make no dispatch claim.
class InputHarness extends Node:
	var _buffer: InputBuffer
	var received_keys: int = 0
	var focus_cancels: int = 0

	func _init(buffer: InputBuffer) -> void:
		_buffer = buffer

	func _input(event: InputEvent) -> void:
		if event is InputEventKey:
			received_keys += 1
		_buffer.accept_event(event)

	func _notification(what: int) -> void:
		if what == NOTIFICATION_APPLICATION_FOCUS_OUT and _buffer != null:
			focus_cancels += 1
			_buffer.cancel_all()

const EXPECTED_CODES: Dictionary = {
	&"p1_left": 4194319, &"p1_right": 4194321, &"p1_up": 4194320, &"p1_down": 4194322,
	&"p1_punch": 78, &"p1_shoot": 77, &"p1_throw": 44, &"p1_power": 46,
	&"p2_left": 65, &"p2_right": 68, &"p2_up": 87, &"p2_down": 83,
	&"p2_punch": 49, &"p2_shoot": 50, &"p2_throw": 51, &"p2_power": 52,
}

var _failures: int = 0
var _assertions: int = 0
var _finished: bool = false
var _live_harness: InputHarness

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	create_timer(15.0).timeout.connect(_on_timeout)
	_test_input_map()
	_test_input_frame_validation()
	_test_buffer_input_edges()
	_test_focus_cancel_and_echo()
	await _test_scene_input_dispatch()
	_finished = true
	if _failures == 0:
		print("SA-01 tests PASS: %d assertions; InputMap, immutable frames, cross-tick edges, SceneTree input dispatch and focus cancel" % _assertions)
	else:
		printerr("SA-01 tests FAIL: %d of %d assertions" % [_failures, _assertions])
	quit(0 if _failures == 0 else 1)

func _on_timeout() -> void:
	if _finished:
		return
	_expect(false, "test coroutine did not finish before watchdog deadline")
	# Also covers an unexpected script error: never leave a live listener or
	# report success merely because an asynchronous test stopped progressing.
	_release_injected_keys()
	if is_instance_valid(_live_harness):
		_live_harness.free()
	_live_harness = null
	_finished = true
	printerr("SA-01 tests FAIL: watchdog; %d of %d assertions" % [_failures, _assertions])
	quit(1)

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
		for record: Dictionary in valid_frame.records():
			_expect(record.is_read_only(), "each frame record must be immutable")
			var event_values: Array = record[&"events"]
			_expect_events_read_only(event_values)

	var extra: Array[Dictionary] = valid_records.duplicate()
	extra[0] = extra[0].duplicate()
	extra[0][&"extra"] = true
	_expect(InputFrameType.create(7, extra) == null, "extra record key must reject")

	var wrong_tick: Array[Dictionary] = valid_records.duplicate()
	wrong_tick[0] = wrong_tick[0].duplicate()
	wrong_tick[0][&"tick"] = "7"
	_expect(InputFrameType.create(7, wrong_tick) == null, "wrong tick type must reject")
	wrong_tick[0][&"tick"] = 7.0
	_expect(InputFrameType.create(7, wrong_tick) == null, "float tick must reject without coercion")

	var wrong_player: Array[Dictionary] = valid_records.duplicate()
	wrong_player[0] = wrong_player[0].duplicate()
	wrong_player[0][&"player"] = 2
	_expect(InputFrameType.create(7, wrong_player) == null, "action-owner mismatch must reject")
	wrong_player[0][&"player"] = "1"
	_expect(InputFrameType.create(7, wrong_player) == null, "string player must reject without coercion")
	wrong_player[0][&"player"] = 1.0
	_expect(InputFrameType.create(7, wrong_player) == null, "float player must reject without coercion")

	var unknown_action: Array[Dictionary] = valid_records.duplicate()
	unknown_action[0] = unknown_action[0].duplicate()
	unknown_action[0][&"action"] = &"p1_unknown"
	_expect(InputFrameType.create(7, unknown_action) == null, "unknown action must reject")
	unknown_action[0][&"action"] = "p1_left"
	_expect(InputFrameType.create(7, unknown_action) == null, "String action must reject; schema requires StringName")
	unknown_action[0][&"action"] = 1
	_expect(InputFrameType.create(7, unknown_action) == null, "integer action must reject")

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
	var tap_frame: InputFrame = InputFrameType.create(7, fast_tap)
	_expect(tap_frame != null, "ordered press-release-press must be accepted")
	if tap_frame != null:
		var tap_events_saved: Array = tap_frame.records()[0][&"events"]
		_expect_events_read_only(tap_events_saved)
		_append_edge(fast_tap[0], &"released")
		fast_tap[0][&"held"] = false
		_expect(_events_for(tap_frame.records()[0]) == [&"pressed", &"released", &"pressed"], "caller event mutation must not change saved frame")
		_expect(bool(tap_frame.records()[0][&"held"]), "caller record mutation must not change saved frame")
	fast_tap[0][&"events"] = [&"pressed", &"pressed"]
	_expect(InputFrameType.create(7, fast_tap) == null, "duplicate press edge must reject")
	fast_tap[0][&"events"] = [&"released"]
	_expect(InputFrameType.create(7, fast_tap) == null, "release from initially unheld state must reject")
	fast_tap[0][&"events"] = ["pressed"]
	_expect(InputFrameType.create(7, fast_tap) == null, "String edge must reject without coercion")

	var prior_held: Array[Dictionary] = _empty_records(8)
	prior_held[0][&"initial_held"] = true
	prior_held[0][&"held"] = true
	_expect(InputFrameType.create(8, prior_held) != null, "idle tick must retain initial held")
	prior_held[0][&"held"] = false
	_expect(InputFrameType.create(8, prior_held) == null, "idle tick must reject unexplained held loss")
	prior_held[0][&"events"] = [&"released", &"pressed"]
	prior_held[0][&"pressed"] = true
	prior_held[0][&"released"] = true
	prior_held[0][&"held"] = true
	_expect(InputFrameType.create(8, prior_held) != null, "initially held release-press must be accepted")
	prior_held[0][&"initial_held"] = 1
	_expect(InputFrameType.create(8, prior_held) == null, "initial held must be strictly boolean")

func _test_buffer_input_edges() -> void:
	var buffer: InputBuffer = InputBufferType.new()
	buffer.accept_event(_key_event(78, true))
	buffer.accept_event(_key_event(49, true))
	var frame: InputFrame = buffer.build_frame(1)
	var p1: Dictionary = _record_for(frame, &"p1_punch", 1)
	var p2: Dictionary = _record_for(frame, &"p2_punch", 2)
	_expect(bool(p1[&"pressed"]) and bool(p1[&"held"]), "P1 key must route independently")
	_expect(bool(p2[&"pressed"]) and bool(p2[&"held"]), "P2 key must route independently")
	_expect(_events_for(p1).size() == 1 and _events_for(p2).size() == 1, "one edge per action")
	var held: InputFrame = buffer.build_frame(2)
	_expect(not bool(_record_for(held, &"p1_punch", 1)[&"pressed"]), "pressed resets at frame boundary")
	_expect(bool(_record_for(held, &"p1_punch", 1)[&"held"]), "held survives frame boundary")
	_expect_continuity(frame, held)

	buffer.accept_event(_key_event(78, false))
	buffer.accept_event(_key_event(78, true))
	var tap_frame: InputFrame = buffer.build_frame(3)
	var tap: Dictionary = _record_for(tap_frame, &"p1_punch", 1)
	var tap_events: Array = _events_for(tap)
	_expect(tap_events.size() == 2 and tap_events[0] == &"released" and tap_events[1] == &"pressed", "ordered release-press must survive")
	_expect(bool(tap[&"held"]), "end-held state follows final edge")
	_expect_continuity(held, tap_frame)
	buffer.accept_event(_key_event(77, true))
	buffer.accept_event(_key_event(77, false))
	buffer.accept_event(_key_event(77, true))
	var rapid_frame: InputFrame = buffer.build_frame(4)
	var rapid: Dictionary = _record_for(rapid_frame, &"p1_shoot", 1)
	_expect(_events_for(rapid) == [&"pressed", &"released", &"pressed"], "buffer must preserve press-release-press between ticks")
	_expect(bool(rapid[&"held"]), "rapid tap ends held after final press")
	_expect_continuity(tap_frame, rapid_frame)

func _test_focus_cancel_and_echo() -> void:
	var buffer: InputBuffer = InputBufferType.new()
	var echo_down := _key_event(78, true)
	echo_down.echo = true
	buffer.accept_event(echo_down)
	var no_echo_frame: InputFrame = buffer.build_frame(1)
	_expect(not bool(_record_for(no_echo_frame, &"p1_punch", 1)[&"pressed"]), "echo keydown must be ignored")
	buffer.accept_event(_key_event(78, true))
	buffer.accept_event(_key_event(78, true))
	var held_echo := _key_event(78, true)
	held_echo.echo = true
	buffer.accept_event(held_echo)
	buffer.accept_event(held_echo)
	buffer.cancel_all()
	buffer.cancel_all()
	var cancelled: Dictionary = _record_for(buffer.build_frame(2), &"p1_punch", 1)
	_expect(bool(cancelled[&"released"]) and not bool(cancelled[&"held"]), "cancel must release held action")
	_expect(_events_for(cancelled) == [&"pressed", &"released"], "cancel preserves press then release")
	buffer.accept_event(_key_event(78, false))
	var after_cancel: Dictionary = _record_for(buffer.build_frame(3), &"p1_punch", 1)
	_expect(_events_for(after_cancel).is_empty() and not bool(after_cancel[&"held"]), "late keyup after repeated cancel must remain idle")

func _test_scene_input_dispatch() -> void:
	var buffer: InputBuffer = InputBufferType.new()
	_live_harness = InputHarness.new(buffer)
	_live_harness.set_process_input(true)
	get_root().add_child(_live_harness)
	await process_frame
	var p1_down := _key_event(78, true)
	var p2_down := _key_event(49, true)
	Input.parse_input_event(p1_down)
	Input.parse_input_event(p2_down)
	await process_frame
	_expect(_live_harness.received_keys >= 2, "registered Node must consume parsed P1/P2 key events")
	var routed: InputFrame = buffer.build_frame(20)
	_expect(bool(_record_for(routed, &"p1_punch", 1)[&"pressed"]), "SceneTree route must deliver P1")
	_expect(bool(_record_for(routed, &"p2_punch", 2)[&"pressed"]), "SceneTree route must deliver P2")
	_expect(bool(_record_for(routed, &"p1_punch", 1)[&"held"]), "P1 remains held before focus loss")
	_expect(bool(_record_for(routed, &"p2_punch", 2)[&"held"]), "P2 remains held before focus loss")

	_live_harness.notification(NOTIFICATION_APPLICATION_FOCUS_OUT)
	await process_frame
	_expect(_live_harness.focus_cancels == 1, "focus-out notification must invoke cancel")
	var cancelled: InputFrame = buffer.build_frame(21)
	_expect(_events_for(_record_for(cancelled, &"p1_punch", 1)) == [&"released"], "focus cancel must release P1")
	_expect(_events_for(_record_for(cancelled, &"p2_punch", 2)) == [&"released"], "focus cancel must release P2")
	_expect(not bool(_record_for(cancelled, &"p1_punch", 1)[&"held"]), "focus cancel clears P1 held")
	_expect(not bool(_record_for(cancelled, &"p2_punch", 2)[&"held"]), "focus cancel clears P2 held")
	_release_injected_keys()
	_live_harness.queue_free()
	await process_frame
	_live_harness = null

func _expect_continuity(previous: InputFrame, current: InputFrame) -> void:
	for previous_record: Dictionary in previous.records():
		var action: StringName = StringName(previous_record[&"action"])
		var player: int = int(previous_record[&"player"])
		var current_record: Dictionary = _record_for(current, action, player)
		_expect(bool(current_record[&"initial_held"]) == bool(previous_record[&"held"]), "initial_held must carry prior held state for %s" % action)

func _expect_events_read_only(events: Array) -> void:
	_expect(events.is_read_only(), "nested event array must be immutable")

func _append_edge(record: Dictionary, edge: StringName) -> void:
	var events: Array = record[&"events"]
	events.append(edge)

func _release_injected_keys() -> void:
	if not is_instance_valid(_live_harness) or not _live_harness.is_inside_tree() or _live_harness.received_keys == 0:
		return
	Input.parse_input_event(_key_event(78, false))
	Input.parse_input_event(_key_event(49, false))

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
	event.physical_keycode = 0
	event.pressed = is_down
	event.echo = false
	return event

func _events_for(record: Dictionary) -> Array:
	var events: Array = []
	for edge: Variant in record[&"events"]:
		events.append(edge)
	return events

func _record_for(frame: InputFrame, action: StringName, player: int) -> Dictionary:
	for record: Dictionary in frame.records():
		if record[&"action"] == action and record[&"player"] == player:
			return record
	return {}

func _expect(condition: bool, message: String) -> void:
	_assertions += 1
	if not condition:
		_failures += 1
		printerr("FAIL: %s" % message)

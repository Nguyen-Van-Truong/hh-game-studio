class_name InputFrame
extends RefCounted
## Immutable fixed-step input value passed into the future simulation.
## SA-01 deliberately contains no gameplay; this schema only captures edges.
## initial_held is the preceding frame's held state. Ordered events describe
## all transitions within this tick; pressed/released summarize their presence.
## An empty event list retains initial_held, and held is always the final state.

const SCHEMA_VERSION: int = 1
const ACTIONS: Array[StringName] = [
	&"p1_left", &"p1_right", &"p1_up", &"p1_down", &"p1_punch", &"p1_shoot", &"p1_throw", &"p1_power",
	&"p2_left", &"p2_right", &"p2_up", &"p2_down", &"p2_punch", &"p2_shoot", &"p2_throw", &"p2_power",
]
const EDGE_PRESSED: StringName = &"pressed"
const EDGE_RELEASED: StringName = &"released"
const REQUIRED_KEYS: Array[StringName] = [
	&"schema_version", &"tick", &"player", &"action", &"initial_held", &"events", &"pressed", &"held", &"released",
]

var _tick: int
var _records: Array[Dictionary] = []

static func create(frame_tick: int, records: Array[Dictionary]) -> InputFrame:
	if typeof(frame_tick) != TYPE_INT or frame_tick < 0:
		return null
	if records.size() != ACTIONS.size():
		return null
	var seen: Dictionary = {}
	for source_record: Dictionary in records:
		if not validate_record(frame_tick, source_record):
			return null
		var identity: String = "%d:%s" % [int(source_record[&"player"]), String(source_record[&"action"])]
		if seen.has(identity):
			return null
		seen[identity] = true
	if seen.size() != ACTIONS.size():
		return null
	for expected_action: StringName in ACTIONS:
		if not seen.has("%d:%s" % [_player_for_action(expected_action), String(expected_action)]):
			return null
	return InputFrame.new(frame_tick, records)

static func validate_record(frame_tick: int, record: Dictionary) -> bool:
	if typeof(frame_tick) != TYPE_INT or frame_tick < 0:
		return false
	if record.size() != REQUIRED_KEYS.size():
		return false
	for key: StringName in REQUIRED_KEYS:
		if not record.has(key):
			return false
	if typeof(record[&"schema_version"]) != TYPE_INT or int(record[&"schema_version"]) != SCHEMA_VERSION:
		return false
	if typeof(record[&"tick"]) != TYPE_INT or int(record[&"tick"]) != frame_tick:
		return false
	if typeof(record[&"player"]) != TYPE_INT:
		return false
	var player: int = int(record[&"player"])
	if player < 1 or player > 2:
		return false
	if typeof(record[&"action"]) != TYPE_STRING_NAME:
		return false
	var action: StringName = StringName(record[&"action"])
	if not ACTIONS.has(action) or _player_for_action(action) != player:
		return false
	if typeof(record[&"initial_held"]) != TYPE_BOOL:
		return false
	if typeof(record[&"events"]) != TYPE_ARRAY:
		return false
	var events: Array[StringName] = []
	for edge: Variant in record[&"events"]:
		if typeof(edge) != TYPE_STRING_NAME:
			return false
		events.append(StringName(edge))
	var saw_pressed: bool = false
	var saw_released: bool = false
	var expected_held: bool = bool(record[&"initial_held"])
	for edge: Variant in events:
		if typeof(edge) != TYPE_STRING_NAME:
			return false
		if edge == EDGE_PRESSED:
			if expected_held:
				return false
			expected_held = true
			saw_pressed = true
		elif edge == EDGE_RELEASED:
			if not expected_held:
				return false
			expected_held = false
			saw_released = true
		else:
			return false
	if typeof(record[&"pressed"]) != TYPE_BOOL or typeof(record[&"held"]) != TYPE_BOOL or typeof(record[&"released"]) != TYPE_BOOL:
		return false
	var pressed: bool = bool(record[&"pressed"])
	var held: bool = bool(record[&"held"])
	var released: bool = bool(record[&"released"])
	if pressed != saw_pressed or released != saw_released or held != expected_held:
		return false
	return true

static func _player_for_action(action: StringName) -> int:
	if String(action).begins_with("p1_"):
		return 1
	if String(action).begins_with("p2_"):
		return 2
	return 0

func _init(frame_tick: int, source_records: Array[Dictionary]) -> void:
	_tick = frame_tick
	for source_record: Dictionary in source_records:
		var record: Dictionary = source_record.duplicate(true)
		var events: Array[StringName] = []
		for edge: Variant in record[&"events"]:
			events.append(StringName(edge))
		events.make_read_only()
		record[&"events"] = events
		record.make_read_only()
		_records.append(record)
	_records.make_read_only()

func tick() -> int:
	return _tick

func records() -> Array[Dictionary]:
	return _records

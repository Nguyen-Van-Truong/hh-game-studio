class_name InputFrame
extends RefCounted
## Immutable fixed-step input value passed into the future simulation.
## SA-01 deliberately contains no gameplay; this schema only captures edges.

const REQUIRED_KEYS: Array[StringName] = [&"tick", &"player", &"action", &"pressed", &"held", &"released"]

var _tick: int
var _records: Array[Dictionary] = []

static func create(frame_tick: int, records: Array[Dictionary]) -> InputFrame:
	if frame_tick < 0:
		return null
	for source_record: Dictionary in records:
		if not validate_record(frame_tick, source_record):
			return null
	return InputFrame.new(frame_tick, records)

static func validate_record(frame_tick: int, record: Dictionary) -> bool:
	for key: StringName in REQUIRED_KEYS:
		if not record.has(key):
			return false
	if int(record[&"tick"]) != frame_tick:
		return false
	var player: int = int(record[&"player"])
	if player < 1 or player > 2:
		return false
	var action: StringName = StringName(record[&"action"])
	if action.is_empty():
		return false
	if typeof(record[&"pressed"]) != TYPE_BOOL or typeof(record[&"held"]) != TYPE_BOOL or typeof(record[&"released"]) != TYPE_BOOL:
		return false
	var pressed: bool = bool(record[&"pressed"])
	var held: bool = bool(record[&"held"])
	var released: bool = bool(record[&"released"])
	if pressed and released:
		return false
	if pressed and not held:
		return false
	if released and held:
		return false
	return true

func _init(frame_tick: int, source_records: Array[Dictionary]) -> void:
	_tick = frame_tick
	for source_record: Dictionary in source_records:
		var record: Dictionary = source_record.duplicate(true)
		record.make_read_only()
		_records.append(record)
	_records.make_read_only()

func tick() -> int:
	return _tick

func records() -> Array[Dictionary]:
	return _records

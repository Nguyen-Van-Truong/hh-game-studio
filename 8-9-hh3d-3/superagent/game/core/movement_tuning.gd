class_name MovementTuning
extends RefCounted
## Engineering seeds only. Loading is centralized so the lab and replay agree.

const REQUIRED: Array[StringName] = [
	&"max_health", &"acceleration_per_tick", &"max_horizontal_speed", &"friction_per_tick",
	&"gravity_per_tick", &"terminal_fall_speed", &"jump_speed", &"jump_lock_ticks",
	&"climb_speed", &"respawn_delay_ticks", &"char_height", &"char_width",
	&"down_tap_window_ticks", &"drop_through_ticks",
]

static func load_default() -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://data/tuning.json"))
	var values: Dictionary = decode(parsed)
	if values.is_empty():
		push_error("Invalid movement tuning; refusing to use hidden defaults")
	return values

static func decode(parsed: Variant) -> Dictionary:
	if typeof(parsed) != TYPE_DICTIONARY:
		return {}
	var config: Dictionary = parsed
	if config.get("schema") != "sa03.tuning.v2" or config.get("status") != "UNVERIFIED_PLACEHOLDER":
		return {}
	if config.get("fixed_hz") != 60 or typeof(config.get("movement")) != TYPE_DICTIONARY:
		return {}
	if typeof(config.get("references")) != TYPE_DICTIONARY:
		return {}
	var movement: Dictionary = config["movement"]
	var references: Dictionary = config["references"]
	if movement.size() != REQUIRED.size() or references.size() != REQUIRED.size():
		return {}
	var result: Dictionary = {}
	for key: StringName in REQUIRED:
		var label: String = String(key)
		var value: Variant = movement.get(label)
		if typeof(value) != TYPE_INT and typeof(value) != TYPE_FLOAT:
			return {}
		var number: float = float(value)
		if not is_finite(number) or number != floor(number) or number < 1 or number > 10000:
			return {}
		if typeof(references.get(label)) != TYPE_STRING or not String(references[label]).begins_with("R"):
			return {}
		result[key] = int(number)
	if int(result[&"char_width"]) > int(result[&"char_height"]):
		return {}
	return result

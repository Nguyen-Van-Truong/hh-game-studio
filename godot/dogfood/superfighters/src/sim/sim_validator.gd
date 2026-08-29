class_name SimValidator
extends RefCounted

static var ALLOWED: PackedStringArray = PackedStringArray([
	"left", "right", "up", "down", "jump", "crouch", "melee", "fire", "grenade"
])


static func validate_frame(raw: Variant, expected_tick: int) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	if raw == null:
		errors.append("frame is null")
		return errors
	var data: Dictionary = {}
	if raw is InputFrame:
		data = (raw as InputFrame).to_dict()
	elif raw is Dictionary:
		data = raw as Dictionary
	else:
		errors.append("frame is not InputFrame or Dictionary")
		return errors
	if not data.has("tick"):
		errors.append("missing tick")
	else:
		var tick_v: Variant = data["tick"]
		if typeof(tick_v) != TYPE_INT and typeof(tick_v) != TYPE_FLOAT:
			errors.append("tick is not a number")
		else:
			var tick: int = int(tick_v)
			if tick < 0:
				errors.append("tick is negative")
			elif tick != expected_tick:
				errors.append("tick mismatch expected=%d got=%d" % [expected_tick, tick])
	if data.has("schema_version"):
		var ver: int = int(data.get("schema_version", -1))
		if ver != SimConstants.SCHEMA_VERSION:
			errors.append("schema_version mismatch")
	if not data.has("slot"):
		errors.append("missing slot")
	else:
		var slot: int = int(data.get("slot", -1))
		if slot < 0:
			errors.append("slot is negative")
	_check_action_list(data, "held", errors)
	_check_action_list(data, "pressed", errors)
	_check_action_list(data, "released", errors)
	_check_axis(data, "move_x", errors)
	_check_axis(data, "move_y", errors)
	return errors


static func validate_bundle(frames: Array, expected_tick: int, fighter_count: int) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	if frames.size() != fighter_count:
		errors.append("frame count %d != fighter count %d" % [frames.size(), fighter_count])
		return errors
	var i: int = 0
	while i < frames.size():
		var one: PackedStringArray = validate_frame(frames[i], expected_tick)
		var j: int = 0
		while j < one.size():
			errors.append("slot_index=%d %s" % [i, String(one[j])])
			j += 1
		if frames[i] is InputFrame:
			var frame: InputFrame = frames[i] as InputFrame
			if frame.slot != i and fighter_count > 0:
				errors.append("slot_index=%d slot field %d" % [i, frame.slot])
		elif frames[i] is Dictionary:
			var d: Dictionary = frames[i] as Dictionary
			if d.has("slot") and int(d["slot"]) != i:
				errors.append("slot_index=%d slot field %d" % [i, int(d["slot"])])
		i += 1
	return errors


static func _check_action_list(data: Dictionary, key: String, errors: PackedStringArray) -> void:
	if not data.has(key):
		errors.append("missing %s" % key)
		return
	var raw: Variant = data[key]
	if raw is String:
		errors.append("%s must be an array" % key)
		return
	if not (raw is Array) and not (raw is PackedStringArray):
		errors.append("%s must be an array" % key)
		return
	var arr: PackedStringArray = InputFrame._to_packed(raw)
	var i: int = 0
	while i < arr.size():
		var action: String = String(arr[i])
		if not ALLOWED.has(action):
			errors.append("unknown action '%s' in %s" % [action, key])
		i += 1


static func _check_axis(data: Dictionary, key: String, errors: PackedStringArray) -> void:
	if not data.has(key):
		return
	var raw: Variant = data[key]
	if typeof(raw) != TYPE_INT and typeof(raw) != TYPE_FLOAT:
		errors.append("%s is not a number" % key)
		return
	var axis: float = float(raw)
	if is_nan(axis) or is_inf(axis):
		errors.append("%s is not finite" % key)
	elif axis < -1.0 or axis > 1.0:
		errors.append("%s out of range" % key)

class_name InputMapStore
extends RefCounted

## Default + remapped bindings. Persist is temp+rename (V-A13).
## P1 pad is device 0; P2 pad is device 1 (ledger:RL-CTRL-DEVICE-SPLIT).


static var last_payload: Dictionary = {}
static var last_save_path: String = ""
static var last_error: String = ""


static func apply_installed() -> PackedStringArray:
	return apply_saved_if_any()


static func apply_saved_if_any() -> PackedStringArray:
	var saved: Dictionary = load_saved()
	if saved.is_empty():
		return PackedStringArray()
	return apply(saved)


static func default_payload() -> Dictionary:
	return SimConstants.load_json(InputConstants.DEFAULTS_PATH)


static func apply(payload: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = validate(payload)
	if not errors.is_empty():
		last_error = String(errors[0])
		return errors
	_wipe_and_bind(payload)
	last_payload = payload.duplicate(true)
	last_error = ""
	return errors


static func validate(payload: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	if payload.is_empty():
		errors.append("empty remap payload")
		return errors
	if str(payload.get("schema", "")) != InputConstants.SCHEMA_ID:
		errors.append("remap schema mismatch")
	if str(payload.get("title", "")) != "Vault Fighters":
		errors.append("remap title must be Vault Fighters")
	if bool(payload.get("y8_parity_claimed", false)):
		errors.append("remap must not claim Y8 parity")
	var deadzone: float = float(payload.get("deadzone", InputConstants.DEADZONE))
	if deadzone < 0.05 or deadzone > 0.9:
		errors.append("deadzone out of range")
	var p1: int = int(payload.get("p1_device", InputConstants.P1_DEVICE))
	var p2: int = int(payload.get("p2_device", InputConstants.P2_DEVICE))
	if p1 == p2:
		errors.append("P1 and P2 gamepad devices must differ")
	var actions: Dictionary = payload.get("actions", {}) as Dictionary
	if actions.is_empty():
		errors.append("remap missing actions")
		return errors
	var i: int = 0
	while i < InputConstants.ACTION_NAMES.size():
		var name: String = String(InputConstants.ACTION_NAMES[i])
		if not actions.has(name):
			errors.append("missing action %s" % name)
		i += 1
	if _payload_binds_f11(actions):
		errors.append("F11 must not be a fighter action")
	if _payload_binds_reserved(actions):
		errors.append("dive/kick must stay unshipped")
	return errors


static func persist_atomic(payload: Dictionary, filename: String = InputConstants.STORE_FILE) -> String:
	last_error = ""
	var errors: PackedStringArray = validate(payload)
	if not errors.is_empty():
		last_error = String(errors[0])
		return ""
	if filename.contains("..") or filename.contains("/") or filename.contains("\\"):
		last_error = "illegal remap filename"
		return ""
	var to_write: Dictionary = payload.duplicate(true)
	to_write["schema_hash"] = FileAccess.get_sha256(InputConstants.SCHEMA_PATH)
	to_write["title"] = "Vault Fighters"
	to_write["y8_parity_claimed"] = false
	var dir_abs: String = ProjectSettings.globalize_path(InputConstants.STORE_DIR)
	DirAccess.make_dir_recursive_absolute(dir_abs)
	var rel: String = InputConstants.STORE_DIR + filename
	var tmp: String = rel + ".tmp"
	var file: FileAccess = FileAccess.open(tmp, FileAccess.WRITE)
	if file == null:
		last_error = "remap tmp open failed"
		return ""
	file.store_string(JSON.stringify(to_write))
	file.close()
	var abs_tmp: String = ProjectSettings.globalize_path(tmp)
	var abs_final: String = ProjectSettings.globalize_path(rel)
	if FileAccess.file_exists(rel):
		DirAccess.remove_absolute(abs_final)
	var err: Error = DirAccess.rename_absolute(abs_tmp, abs_final)
	if err != OK:
		DirAccess.remove_absolute(abs_tmp)
		last_error = "remap rename failed"
		return ""
	if FileAccess.file_exists(tmp):
		last_error = "remap tmp leftover"
		return ""
	last_save_path = rel
	last_payload = to_write
	return rel


static func load_saved(filename: String = InputConstants.STORE_FILE) -> Dictionary:
	if filename.contains("..") or filename.contains("/") or filename.contains("\\"):
		return {}
	var rel: String = InputConstants.STORE_DIR + filename
	if not FileAccess.file_exists(rel):
		return {}
	return SimConstants.load_json(rel)


static func reset_defaults() -> PackedStringArray:
	var payload: Dictionary = default_payload()
	var applied: PackedStringArray = apply(payload)
	if applied.is_empty():
		persist_atomic(payload)
	return applied


static func rebind_key(action: String, physical: Key) -> PackedStringArray:
	if physical == KEY_F11:
		return PackedStringArray(["F11 must not be a fighter action"])
	if physical == KEY_NONE:
		return PackedStringArray(["invalid key"])
	var payload: Dictionary = last_payload.duplicate(true)
	if payload.is_empty():
		payload = default_payload()
	var actions: Dictionary = payload.get("actions", {}) as Dictionary
	var rows: Array = []
	if actions.has(action):
		rows = (actions[action] as Array).duplicate(true)
	var kept: Array = []
	var i: int = 0
	var replaced: bool = false
	while i < rows.size():
		var row: Dictionary = rows[i] as Dictionary
		if str(row.get("kind", "")) == "key":
			if not replaced:
				kept.append({"kind": "key", "physical": InputConstants.name_from_key(physical)})
				replaced = true
		else:
			kept.append(row)
		i += 1
	if not replaced:
		kept.append({"kind": "key", "physical": InputConstants.name_from_key(physical)})
	actions[action] = kept
	payload["actions"] = actions
	return apply(payload)


static func current_label(action: String) -> String:
	var events: Array = InputMap.action_get_events(action)
	var parts: PackedStringArray = PackedStringArray()
	var i: int = 0
	while i < events.size():
		var ev: InputEvent = events[i] as InputEvent
		if ev is InputEventKey:
			parts.append(InputConstants.name_from_key((ev as InputEventKey).physical_keycode))
		elif ev is InputEventJoypadButton:
			var joy: InputEventJoypadButton = ev as InputEventJoypadButton
			parts.append("pad%d-%s" % [joy.device, InputConstants.name_from_joy_button(joy.button_index)])
		elif ev is InputEventJoypadMotion:
			var axis: InputEventJoypadMotion = ev as InputEventJoypadMotion
			parts.append("pad%d-%s" % [axis.device, InputConstants.name_from_joy_axis(axis.axis)])
		i += 1
	return " / ".join(parts)


static func action_joy_devices(action: String) -> PackedInt32Array:
	var out: PackedInt32Array = PackedInt32Array()
	if not InputMap.has_action(action):
		return out
	var events: Array = InputMap.action_get_events(action)
	var i: int = 0
	while i < events.size():
		var ev: InputEvent = events[i] as InputEvent
		if ev is InputEventJoypadButton or ev is InputEventJoypadMotion:
			var device: int = ev.device
			if not out.has(device):
				out.append(device)
		i += 1
	return out


static func binds_f11() -> bool:
	var i: int = 0
	while i < InputConstants.FIGHTER_ACTIONS.size():
		var action: String = String(InputConstants.FIGHTER_ACTIONS[i])
		if not InputMap.has_action(action):
			i += 1
			continue
		var events: Array = InputMap.action_get_events(action)
		var j: int = 0
		while j < events.size():
			var ev: InputEvent = events[j] as InputEvent
			if ev is InputEventKey and (ev as InputEventKey).physical_keycode == KEY_F11:
				return true
			j += 1
		i += 1
	return false


static func _wipe_and_bind(payload: Dictionary) -> void:
	var deadzone: float = float(payload.get("deadzone", InputConstants.DEADZONE))
	var actions: Dictionary = payload.get("actions", {}) as Dictionary
	var i: int = 0
	while i < InputConstants.ACTION_NAMES.size():
		var name: String = String(InputConstants.ACTION_NAMES[i])
		if InputMap.has_action(name):
			InputMap.action_erase_events(name)
			InputMap.action_set_deadzone(name, deadzone)
		else:
			InputMap.add_action(name, deadzone)
		var rows: Array = actions.get(name, []) as Array
		var j: int = 0
		while j < rows.size():
			_add_row(name, rows[j] as Dictionary)
			j += 1
		i += 1


static func _add_row(action: String, row: Dictionary) -> void:
	var kind: String = str(row.get("kind", ""))
	if kind == "key":
		var keycode: Key = InputConstants.key_from_name(str(row.get("physical", "")))
		if keycode == KEY_NONE or keycode == KEY_F11:
			return
		var ev: InputEventKey = InputEventKey.new()
		ev.physical_keycode = keycode
		ev.keycode = keycode
		InputMap.action_add_event(action, ev)
		return
	if kind == "joy_button":
		var button: JoyButton = InputConstants.joy_button_from_name(str(row.get("button", "")))
		if button == JOY_BUTTON_INVALID:
			return
		var joy: InputEventJoypadButton = InputEventJoypadButton.new()
		joy.device = int(row.get("device", -1))
		joy.button_index = button
		InputMap.action_add_event(action, joy)
		return
	if kind == "joy_axis":
		var axis: JoyAxis = InputConstants.joy_axis_from_name(str(row.get("axis", "")))
		if axis == JOY_AXIS_INVALID:
			return
		var motion: InputEventJoypadMotion = InputEventJoypadMotion.new()
		motion.device = int(row.get("device", -1))
		motion.axis = axis
		motion.axis_value = float(row.get("axis_value", 0.0))
		InputMap.action_add_event(action, motion)


static func _payload_binds_f11(actions: Dictionary) -> bool:
	var keys: Array = actions.keys()
	var i: int = 0
	while i < keys.size():
		var name: String = str(keys[i])
		if name == "pause":
			i += 1
			continue
		var rows: Array = actions[name] as Array
		var j: int = 0
		while j < rows.size():
			var row: Dictionary = rows[j] as Dictionary
			if str(row.get("kind", "")) == "key" and str(row.get("physical", "")) == "F11":
				return true
			j += 1
		i += 1
	return false


static func _payload_binds_reserved(actions: Dictionary) -> bool:
	var reserved: PackedStringArray = PackedStringArray(["dive", "kick"])
	var i: int = 0
	while i < reserved.size():
		if actions.has(String(reserved[i])):
			return true
		i += 1
	return false

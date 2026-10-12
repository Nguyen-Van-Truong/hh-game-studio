# HH gamekit kit rebind v1 - self-made (HH Studio)
extends Node
## Remembers InputMap overrides in user://input_map.cfg and applies them on start.

const _PATH: String = "user://input_map.cfg"
const _BAK: String = "user://.input_map.cfg.bak"

var _defaults: Dictionary = {}
var _booted: bool = false


func _enter_tree() -> void:
	if _booted:
		return
	_booted = true
	_capture_defaults()
	@warning_ignore("return_value_discarded") # a missing input_map.cfg keeps the engine defaults
	load_bindings()


func remap(action: String, event: InputEvent) -> void:
	if not InputMap.has_action(action):
		push_warning("HHRebind: no action " + action)
		return
	if event == null:
		push_warning("HHRebind: null event")
		return
	InputMap.action_erase_events(action)
	InputMap.action_add_event(action, _dup_event(event))


func reset(action: String) -> void:
	if not InputMap.has_action(action):
		push_warning("HHRebind: no action " + action)
		return
	InputMap.action_erase_events(action)
	var raw: Variant = _defaults.get(action, [])
	if raw is Array:
		var saved: Array = raw
		for ev: Variant in saved:
			if ev is InputEvent:
				var event: InputEvent = ev
				InputMap.action_add_event(action, _dup_event(event))


func reset_all() -> void:
	for action_name: Variant in _defaults.keys():
		reset(str(action_name))


func save_bindings() -> Error:
	var cfg: ConfigFile = ConfigFile.new()
	cfg.set_value("meta", "version", 1)
	for action_name: StringName in InputMap.get_actions():
		var aname: String = String(action_name)
		if _matches_default(aname):
			continue
		cfg.set_value("bindings", aname, _serialize_list(InputMap.action_get_events(action_name)))
	return _save_cfg(cfg, _PATH)


func load_bindings() -> Error:
	var path: String = _resolve_path()
	if path.is_empty():
		return ERR_FILE_NOT_FOUND
	var cfg: ConfigFile = ConfigFile.new()
	var err: Error = cfg.load(path)
	if err != OK:
		push_warning("HHRebind: cannot read input_map.cfg")
		return err
	if not cfg.has_section("bindings"):
		return OK
	for aname: String in cfg.get_section_keys("bindings"):
		if not InputMap.has_action(aname):
			InputMap.add_action(aname)
		InputMap.action_erase_events(aname)
		var rows: Variant = cfg.get_value("bindings", aname, [])
		if rows is Array:
			var saved: Array = rows
			for row: Variant in saved:
				if row is Dictionary:
					var body: Dictionary = row
					var ev: InputEvent = _deserialize_event(body)
					if ev != null:
						InputMap.action_add_event(aname, ev)
	return OK


func _capture_defaults() -> void:
	_defaults.clear()
	for action_name: StringName in InputMap.get_actions():
		var copies: Array = []
		for ev: InputEvent in InputMap.action_get_events(action_name):
			copies.append(ev.duplicate())
		_defaults[String(action_name)] = copies


func _matches_default(action_name: String) -> bool:
	var current: String = JSON.stringify(_serialize_list(InputMap.action_get_events(action_name)), "", true, true)
	var base_rows: Array = []
	var raw: Variant = _defaults.get(action_name, [])
	if raw is Array:
		var saved: Array = raw
		base_rows = _serialize_list(saved)
	return current == JSON.stringify(base_rows, "", true, true)


func _serialize_list(events: Array) -> Array:
	var out: Array = []
	for ev: Variant in events:
		if ev is InputEvent:
			var event: InputEvent = ev
			var row: Dictionary = _serialize_event(event)
			if not row.is_empty():
				out.append(row)
	return out


func _serialize_event(ev: InputEvent) -> Dictionary:
	if ev is InputEventKey:
		var key: InputEventKey = ev as InputEventKey
		return {
			"type": "key",
			"keycode": int(key.keycode),
			"physical_keycode": int(key.physical_keycode),
			"unicode": key.unicode,
			"alt": key.alt_pressed,
			"shift": key.shift_pressed,
			"ctrl": key.ctrl_pressed,
			"meta": key.meta_pressed,
		}
	if ev is InputEventJoypadButton:
		var btn: InputEventJoypadButton = ev as InputEventJoypadButton
		return {"type": "joy_button", "button": int(btn.button_index), "device": btn.device}
	if ev is InputEventJoypadMotion:
		var motion: InputEventJoypadMotion = ev as InputEventJoypadMotion
		return {"type": "joy_motion", "axis": int(motion.axis), "value": motion.axis_value, "device": motion.device}
	if ev is InputEventMouseButton:
		var mouse: InputEventMouseButton = ev as InputEventMouseButton
		return {"type": "mouse_button", "button": int(mouse.button_index), "device": mouse.device}
	return {}


func _deserialize_event(row: Dictionary) -> InputEvent:
	match str(row.get("type", "")):
		"key":
			var key: InputEventKey = InputEventKey.new()
			key.keycode = _to_int(row.get("keycode", 0)) as Key
			key.physical_keycode = _to_int(row.get("physical_keycode", 0)) as Key
			key.unicode = _to_int(row.get("unicode", 0))
			key.alt_pressed = _to_bool(row.get("alt", false))
			key.shift_pressed = _to_bool(row.get("shift", false))
			key.ctrl_pressed = _to_bool(row.get("ctrl", false))
			key.meta_pressed = _to_bool(row.get("meta", false))
			return key
		"joy_button":
			var btn: InputEventJoypadButton = InputEventJoypadButton.new()
			btn.button_index = _to_int(row.get("button", 0)) as JoyButton
			btn.device = _to_int(row.get("device", -1))
			return btn
		"joy_motion":
			var motion: InputEventJoypadMotion = InputEventJoypadMotion.new()
			motion.axis = _to_int(row.get("axis", 0)) as JoyAxis
			motion.axis_value = _to_float(row.get("value", 0.0))
			motion.device = _to_int(row.get("device", -1))
			return motion
		"mouse_button":
			var mouse: InputEventMouseButton = InputEventMouseButton.new()
			mouse.button_index = _to_int(row.get("button", 0)) as MouseButton
			mouse.device = _to_int(row.get("device", -1))
			return mouse
		_:
			return null


func _to_int(value: Variant) -> int:
	var converted: Variant = type_convert(value, TYPE_INT)
	if converted is int:
		return converted
	return 0


func _to_float(value: Variant) -> float:
	var converted: Variant = type_convert(value, TYPE_FLOAT)
	if converted is float:
		return converted
	return 0.0


func _to_bool(value: Variant) -> bool:
	var converted: Variant = type_convert(value, TYPE_BOOL)
	if converted is bool:
		return converted
	return false


func _dup_event(ev: InputEvent) -> InputEvent:
	var copy: Resource = ev.duplicate()
	if copy is InputEvent:
		return copy
	return ev


func _save_cfg(cfg: ConfigFile, res_path: String) -> Error:
	var temp_res: String = res_path + ".hhtmp"
	var err: Error = cfg.save(temp_res)
	if err != OK:
		return err
	var temp_abs: String = ProjectSettings.globalize_path(temp_res)
	var final_abs: String = ProjectSettings.globalize_path(res_path)
	return _replace(temp_abs, final_abs)

func _resolve_path() -> String:
	if FileAccess.file_exists(_PATH):
		return _PATH
	if FileAccess.file_exists(_BAK):
		push_warning("HHRebind: loaded backup input_map.cfg")
		return _BAK
	return ""

func _backup_abs(final_abs: String) -> String:
	var slash: int = maxi(final_abs.rfind("/"), final_abs.rfind("\\"))
	var file_name: String = final_abs.substr(slash + 1)
	var folder: String = final_abs.substr(0, slash + 1)
	var hidden: String = "." + file_name + ".bak"
	return folder + hidden


## Move the live file aside, then put the temp file in its place.
## Never delete the live file until the new bytes have its name.
func _replace(temp_abs: String, final_abs: String) -> Error:
	var bak_abs: String = _backup_abs(final_abs)
	var backed_up: bool = false
	if FileAccess.file_exists(final_abs):
		if FileAccess.file_exists(bak_abs):
			var cleared: Error = DirAccess.remove_absolute(bak_abs)
			if cleared != OK:
				@warning_ignore("return_value_discarded") # publish failed; drop the temp file
				DirAccess.remove_absolute(temp_abs)
				return cleared
		var parked: Error = DirAccess.rename_absolute(final_abs, bak_abs)
		if parked != OK:
			@warning_ignore("return_value_discarded") # publish failed; drop the temp file
			DirAccess.remove_absolute(temp_abs)
			return parked
		backed_up = true
	var placed: Error = DirAccess.rename_absolute(temp_abs, final_abs)
	if placed != OK:
		if backed_up:
			@warning_ignore("return_value_discarded") # put the previous file back and still return the rename error
			DirAccess.rename_absolute(bak_abs, final_abs)
		@warning_ignore("return_value_discarded") # publish failed; drop the temp file
		DirAccess.remove_absolute(temp_abs)
		return placed
	if FileAccess.file_exists(bak_abs):
		@warning_ignore("return_value_discarded") # the new file is in place; a leftover backup is not fatal
		DirAccess.remove_absolute(bak_abs)
	return OK

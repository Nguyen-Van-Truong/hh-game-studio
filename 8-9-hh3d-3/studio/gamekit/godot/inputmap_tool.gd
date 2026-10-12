extends SceneTree
## gamekit input tool: list ProjectSettings input/* actions, or write them to a temp project file.
## The host validates the request, checkpoints project.godot, and only then replaces it.
## Key names are resolved with OS.find_keycode_from_string before any setting is changed.

var HH: GDScript


func _initialize() -> void:
	HH = load(get_script().resource_path.get_base_dir().path_join("hhgk.gd"))
	var req: Variant = HH.read_request()
	var result: Dictionary
	if not (req is Dictionary):
		result = HH.fail("BAD_REQUEST", "missing or invalid --request file")
	else:
		var body: Dictionary = req
		match str(body.get("mode", "")):
			"list":
				result = {"ok": true, "actions": _collect(bool(body.get("all", false)))}
			"apply":
				result = _apply(body)
			_:
				result = HH.fail("BAD_REQUEST", "unknown mode")
	HH.emit(result)
	quit(0 if bool(result.get("ok", false)) else 3)


func _collect(include_all: bool) -> Array:
	var found: Dictionary = {}
	for prop: Dictionary in ProjectSettings.get_property_list():
		var pname := str(prop["name"])
		if not pname.begins_with("input/"):
			continue
		var action_name := pname.substr(6)
		if action_name.is_empty():
			continue
		if not include_all and action_name.begins_with("ui_"):
			continue
		var data: Variant = ProjectSettings.get_setting(pname)
		if not (data is Dictionary):
			continue
		var spec: Dictionary = data
		var events: Array = []
		var raw: Variant = spec.get("events", [])
		if raw is Array:
			for item: Variant in raw:
				if item is InputEvent:
					events.append(_event_json(item))
		found[action_name] = {
			"name": action_name,
			"deadzone": float(spec.get("deadzone", 0.5)),
			"events": events,
		}
	var keys: Array = found.keys()
	keys.sort()
	var out: Array = []
	for key: Variant in keys:
		out.append(found[str(key)])
	return out


func _event_json(ev: InputEvent) -> Dictionary:
	if ev is InputEventKey:
		var key_ev := ev as InputEventKey
		if key_ev.physical_keycode != KEY_NONE:
			return {"physical_key": OS.get_keycode_string(key_ev.physical_keycode)}
		return {"key": OS.get_keycode_string(key_ev.keycode)}
	if ev is InputEventJoypadButton:
		return {"joy_button": int((ev as InputEventJoypadButton).button_index)}
	if ev is InputEventJoypadMotion:
		var motion := ev as InputEventJoypadMotion
		return {"joy_axis": int(motion.axis), "value": motion.axis_value}
	if ev is InputEventMouseButton:
		return {"mouse_button": int((ev as InputEventMouseButton).button_index)}
	return {"unhandled": ev.get_class()}


func _fail_event(action_name: String, index: int, detail: String) -> Dictionary:
	return HH.fail("VALIDATION_FAILED", "%s events[%d]: %s" % [action_name, index, detail])


func _prepare(action_name: String, spec: Dictionary) -> Dictionary:
	var deadzone := float(spec.get("deadzone", 0.5))
	if deadzone < 0.0 or deadzone > 1.0 or is_nan(deadzone) or is_inf(deadzone):
		return HH.fail("VALIDATION_FAILED", "%s deadzone must be a finite number from 0 to 1" % action_name)
	var raw: Variant = spec.get("events", [])
	if not (raw is Array):
		return HH.fail("VALIDATION_FAILED", "%s events must be a list" % action_name)
	var events := raw as Array
	var built: Array = []
	var echoed: Array = []
	for index: int in events.size():
		var item: Variant = events[index]
		if not (item is Dictionary):
			return _fail_event(action_name, index, "event must be an object")
		var made := _make_event(action_name, index, item)
		if not bool(made.get("ok", false)):
			return made
		built.append(made["event"])
		echoed.append(made["json"])
	return {"ok": true, "deadzone": deadzone, "events": built, "json": echoed}


func _make_event(action_name: String, index: int, spec: Dictionary) -> Dictionary:
	var kind_count := 0
	if spec.has("key"):
		kind_count += 1
	if spec.has("physical_key"):
		kind_count += 1
	if spec.has("joy_button"):
		kind_count += 1
	if spec.has("joy_axis") or spec.has("value"):
		kind_count += 1
	if spec.has("mouse_button"):
		kind_count += 1
	if kind_count != 1:
		return _fail_event(action_name, index, "event must be one of key, physical_key, joy_button, joy_axis+value, mouse_button")
	if spec.has("key") or spec.has("physical_key"):
		var field := "physical_key" if spec.has("physical_key") else "key"
		if spec.size() != 1 or typeof(spec[field]) != TYPE_STRING or str(spec[field]).is_empty():
			return _fail_event(action_name, index, "bad %s" % field)
		var code: Key = OS.find_keycode_from_string(str(spec[field]))
		if code == KEY_NONE:
			return _fail_event(action_name, index, "unknown key '%s'" % str(spec[field]))
		var key_ev := InputEventKey.new()
		if field == "physical_key":
			key_ev.physical_keycode = code
		else:
			key_ev.keycode = code
		return {"ok": true, "event": key_ev, "json": {field: OS.get_keycode_string(code)}}
	if spec.has("joy_button"):
		if spec.size() != 1 or not _int_in(spec["joy_button"], 0, 127):
			return _fail_event(action_name, index, "joy_button must be an integer 0..127")
		var button := InputEventJoypadButton.new()
		button.button_index = int(spec["joy_button"]) as JoyButton
		return {"ok": true, "event": button, "json": {"joy_button": int(spec["joy_button"])}}
	if spec.has("joy_axis") or spec.has("value"):
		if not spec.has("joy_axis") or not spec.has("value") or spec.size() != 2:
			return _fail_event(action_name, index, "joy_axis event needs joy_axis and value")
		if not _int_in(spec["joy_axis"], 0, 9):
			return _fail_event(action_name, index, "joy_axis must be an integer 0..9")
		if not _axis_value(spec["value"]):
			return _fail_event(action_name, index, "joy axis value must be a finite non-zero number from -1 to 1")
		var motion := InputEventJoypadMotion.new()
		motion.axis = int(spec["joy_axis"]) as JoyAxis
		motion.axis_value = float(spec["value"])
		return {"ok": true, "event": motion, "json": {"joy_axis": int(spec["joy_axis"]), "value": float(spec["value"])}}
	if spec.size() != 1 or not _int_in(spec["mouse_button"], 1, 9):
		return _fail_event(action_name, index, "mouse_button must be an integer 1..9")
	var mouse := InputEventMouseButton.new()
	mouse.button_index = int(spec["mouse_button"]) as MouseButton
	return {"ok": true, "event": mouse, "json": {"mouse_button": int(spec["mouse_button"])}}


func _int_in(value: Variant, lo: int, hi: int) -> bool:
	if typeof(value) != TYPE_INT and typeof(value) != TYPE_FLOAT:
		return false
	if typeof(value) == TYPE_FLOAT and float(value) != floor(float(value)):
		return false
	var number := int(value)
	return number >= lo and number <= hi


func _axis_value(value: Variant) -> bool:
	if typeof(value) != TYPE_INT and typeof(value) != TYPE_FLOAT:
		return false
	var number := float(value)
	if is_nan(number) or is_inf(number) or number == 0.0:
		return false
	return number >= -1.0 and number <= 1.0


func _apply(body: Dictionary) -> Dictionary:
	var temp_out := str(body.get("temp_out", ""))
	if temp_out.is_empty() or not temp_out.to_lower().ends_with(".godot"):
		return HH.fail("BAD_REQUEST", "temp_out must be a .godot path inside the project")
	var incoming: Variant = body.get("actions", {})
	if not (incoming is Dictionary):
		return HH.fail("VALIDATION_FAILED", "actions must be an object")
	var actions := incoming as Dictionary
	var prepared: Dictionary = {}
	for key: Variant in actions.keys():
		var action_name := str(key)
		if not _action_name_ok(action_name):
			return HH.fail("VALIDATION_FAILED", "bad action name '%s'" % action_name)
		var spec: Variant = actions[key]
		if not (spec is Dictionary):
			return HH.fail("VALIDATION_FAILED", "%s must be an object" % action_name)
		var built := _prepare(action_name, spec)
		if not bool(built.get("ok", false)):
			return built
		prepared[action_name] = built
	var before := _collect(false)
	var replace := bool(body.get("replace", false))
	if replace:
		for item: Variant in before:
			var old := item as Dictionary
			var old_name := str(old["name"])
			if prepared.has(old_name):
				continue
			ProjectSettings.set_setting("input/" + old_name, null)
			if InputMap.has_action(old_name):
				InputMap.erase_action(old_name)
	var written: Array = []
	var names: Array = prepared.keys()
	names.sort()
	for key2: Variant in names:
		var action_name2 := str(key2)
		var built2: Dictionary = prepared[action_name2]
		ProjectSettings.set_setting("input/" + action_name2, {
			"deadzone": float(built2["deadzone"]),
			"events": built2["events"],
		})
		written.append({
			"name": action_name2,
			"deadzone": float(built2["deadzone"]),
			"events": built2["json"],
		})
	var save_err := ProjectSettings.save_custom(temp_out)
	if save_err != OK:
		return HH.fail("GODOT_FAILED", "save_custom failed: " + error_string(save_err))
	return {"ok": true, "before": before, "written": written, "replace": replace}


func _action_name_ok(action_name: String) -> bool:
	if action_name.is_empty() or action_name.length() > 64:
		return false
	var first := action_name.unicode_at(0)
	var head_ok := (first >= 65 and first <= 90) or (first >= 97 and first <= 122) or first == 95
	if not head_ok:
		return false
	for i: int in range(1, action_name.length()):
		var code := action_name.unicode_at(i)
		var ok := (code >= 65 and code <= 90) or (code >= 97 and code <= 122) or (code >= 48 and code <= 57) or code == 95
		if not ok:
			return false
	return true

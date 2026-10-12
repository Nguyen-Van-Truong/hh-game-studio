extends SceneTree
## gamekit input tool: list ProjectSettings input/* actions, or write them to a temp project file.
## The host validates the request, checkpoints project.godot, and only then replaces it.
## Key names are resolved with OS.find_keycode_from_string before any setting is changed.

const HH = preload("hhgk.gd")


func _initialize() -> void:
	var req: Variant = HH.read_request()
	var result: Dictionary
	if not (req is Dictionary):
		result = HH.fail("BAD_REQUEST", "missing or invalid --request file")
	else:
		var body: Dictionary = req
		match str(body.get("mode", "")):
			"list":
				result = {"ok": true, "actions": _collect(HH.variant_bool(body.get("all", false)))}
			"apply":
				result = _apply(body)
			_:
				result = HH.fail("BAD_REQUEST", "unknown mode")
	HH.emit(result)
	var ok_flag: bool = result.get("ok", false)
	quit(0 if ok_flag else 3)


func _collect(include_all: bool) -> Array:
	var found: Dictionary = {}
	for prop: Dictionary in ProjectSettings.get_property_list():
		var pname: String = str(prop["name"])
		if not pname.begins_with("input/"):
			continue
		var action_name: String = pname.substr(6)
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
			var raw_events: Array = raw
			for item: Variant in raw_events:
				if item is InputEvent:
					var ev: InputEvent = item
					events.append(_event_json(ev))
		found[action_name] = {
			"name": action_name,
			"deadzone": HH.variant_float(spec.get("deadzone", 0.5)),
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
		var key_ev: InputEventKey = ev
		if key_ev.physical_keycode != KEY_NONE:
			return {"physical_key": OS.get_keycode_string(key_ev.physical_keycode)}
		return {"key": OS.get_keycode_string(key_ev.keycode)}
	if ev is InputEventJoypadButton:
		var button_ev: InputEventJoypadButton = ev
		return {"joy_button": int(button_ev.button_index)}
	if ev is InputEventJoypadMotion:
		var motion: InputEventJoypadMotion = ev
		return {"joy_axis": int(motion.axis), "value": motion.axis_value}
	if ev is InputEventMouseButton:
		var mouse_ev: InputEventMouseButton = ev
		return {"mouse_button": int(mouse_ev.button_index)}
	return {"unhandled": ev.get_class()}


func _fail_event(action_name: String, index: int, detail: String) -> Dictionary:
	return HH.fail("VALIDATION_FAILED", "%s events[%d]: %s" % [action_name, index, detail])


func _prepare(action_name: String, spec: Dictionary) -> Dictionary:
	var deadzone: float = HH.variant_float(spec.get("deadzone", 0.5))
	if deadzone < 0.0 or deadzone > 1.0 or is_nan(deadzone) or is_inf(deadzone):
		return HH.fail("VALIDATION_FAILED", "%s deadzone must be a finite number from 0 to 1" % action_name)
	var raw: Variant = spec.get("events", [])
	if not (raw is Array):
		return HH.fail("VALIDATION_FAILED", "%s events must be a list" % action_name)
	var events: Array = raw
	var built: Array = []
	var echoed: Array = []
	for index: int in events.size():
		var item: Variant = events[index]
		if not (item is Dictionary):
			return _fail_event(action_name, index, "event must be an object")
		var item_d: Dictionary = item
		var made: Dictionary = _make_event(action_name, index, item_d)
		if not HH.variant_bool(made.get("ok", false)):
			return made
		built.append(made["event"])
		echoed.append(made["json"])
	return {"ok": true, "deadzone": deadzone, "events": built, "json": echoed}


func _make_event(action_name: String, index: int, spec: Dictionary) -> Dictionary:
	var kind_count: int = 0
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
		var field: String = "physical_key" if spec.has("physical_key") else "key"
		if spec.size() != 1 or typeof(spec[field]) != TYPE_STRING or str(spec[field]).is_empty():
			return _fail_event(action_name, index, "bad %s" % field)
		var code: Key = OS.find_keycode_from_string(str(spec[field]))
		if code == KEY_NONE:
			return _fail_event(action_name, index, "unknown key '%s'" % str(spec[field]))
		var key_ev: InputEventKey = InputEventKey.new()
		if field == "physical_key":
			key_ev.physical_keycode = code
		else:
			key_ev.keycode = code
		return {"ok": true, "event": key_ev, "json": {field: OS.get_keycode_string(code)}}
	if spec.has("joy_button"):
		if spec.size() != 1 or not _int_in(spec["joy_button"], 0, 127):
			return _fail_event(action_name, index, "joy_button must be an integer 0..127")
		var button: InputEventJoypadButton = InputEventJoypadButton.new()
		var joy_i: int = HH.variant_int(spec["joy_button"])
		button.button_index = joy_i as JoyButton
		return {"ok": true, "event": button, "json": {"joy_button": joy_i}}
	if spec.has("joy_axis") or spec.has("value"):
		if not spec.has("joy_axis") or not spec.has("value") or spec.size() != 2:
			return _fail_event(action_name, index, "joy_axis event needs joy_axis and value")
		if not _int_in(spec["joy_axis"], 0, 9):
			return _fail_event(action_name, index, "joy_axis must be an integer 0..9")
		if not _axis_value(spec["value"]):
			return _fail_event(action_name, index, "joy axis value must be a finite non-zero number from -1 to 1")
		var motion: InputEventJoypadMotion = InputEventJoypadMotion.new()
		var axis_i: int = HH.variant_int(spec["joy_axis"])
		var axis_v: float = HH.variant_float(spec["value"])
		motion.axis = axis_i as JoyAxis
		motion.axis_value = axis_v
		return {"ok": true, "event": motion, "json": {"joy_axis": axis_i, "value": axis_v}}
	if spec.size() != 1 or not _int_in(spec["mouse_button"], 1, 9):
		return _fail_event(action_name, index, "mouse_button must be an integer 1..9")
	var mouse: InputEventMouseButton = InputEventMouseButton.new()
	var mouse_i: int = HH.variant_int(spec["mouse_button"])
	mouse.button_index = mouse_i as MouseButton
	return {"ok": true, "event": mouse, "json": {"mouse_button": mouse_i}}


func _int_in(value: Variant, lo: int, hi: int) -> bool:
	if not (value is int) and not (value is float):
		return false
	if value is float:
		var f: float = value
		if f != floor(f):
			return false
	var number: int = HH.variant_int(value)
	return number >= lo and number <= hi


func _axis_value(value: Variant) -> bool:
	if not (value is int) and not (value is float):
		return false
	var number: float = HH.variant_float(value)
	if is_nan(number) or is_inf(number) or number == 0.0:
		return false
	return number >= -1.0 and number <= 1.0


func _apply(body: Dictionary) -> Dictionary:
	var temp_out: String = str(body.get("temp_out", ""))
	if temp_out.is_empty() or not temp_out.to_lower().ends_with(".godot"):
		return HH.fail("BAD_REQUEST", "temp_out must be a .godot path inside the project")
	var incoming: Variant = body.get("actions", {})
	if not (incoming is Dictionary):
		return HH.fail("VALIDATION_FAILED", "actions must be an object")
	var actions: Dictionary = incoming
	var prepared: Dictionary = {}
	for key: Variant in actions.keys():
		var action_name: String = str(key)
		if not _action_name_ok(action_name):
			return HH.fail("VALIDATION_FAILED", "bad action name '%s'" % action_name)
		var spec: Variant = actions[key]
		if not (spec is Dictionary):
			return HH.fail("VALIDATION_FAILED", "%s must be an object" % action_name)
		var spec_d: Dictionary = spec
		var built: Dictionary = _prepare(action_name, spec_d)
		if not HH.variant_bool(built.get("ok", false)):
			return built
		prepared[action_name] = built
	var before: Array = _collect(false)
	var replace: bool = HH.variant_bool(body.get("replace", false))
	if replace:
		for item: Variant in before:
			var old: Dictionary = item
			var old_name: String = str(old["name"])
			if prepared.has(old_name):
				continue
			ProjectSettings.set_setting("input/" + old_name, null)
			if InputMap.has_action(old_name):
				InputMap.erase_action(old_name)
	var written: Array = []
	var names: Array = prepared.keys()
	names.sort()
	for key2: Variant in names:
		var action_name2: String = str(key2)
		var built2: Dictionary = prepared[action_name2]
		var deadzone2: float = built2["deadzone"]
		ProjectSettings.set_setting("input/" + action_name2, {
			"deadzone": deadzone2,
			"events": built2["events"],
		})
		written.append({
			"name": action_name2,
			"deadzone": deadzone2,
			"events": built2["json"],
		})
	var save_err: Error = ProjectSettings.save_custom(temp_out)
	if save_err != OK:
		return HH.fail("GODOT_FAILED", "save_custom failed: " + error_string(save_err))
	return {"ok": true, "before": before, "written": written, "replace": replace}


func _action_name_ok(action_name: String) -> bool:
	if action_name.is_empty() or action_name.length() > 64:
		return false
	var first: int = action_name.unicode_at(0)
	var head_ok: bool = (first >= 65 and first <= 90) or (first >= 97 and first <= 122) or first == 95
	if not head_ok:
		return false
	for i: int in range(1, action_name.length()):
		var code: int = action_name.unicode_at(i)
		var ok_ch: bool = (code >= 65 and code <= 90) or (code >= 97 and code <= 122) or (code >= 48 and code <= 57) or code == 95
		if not ok_ch:
			return false
	return true

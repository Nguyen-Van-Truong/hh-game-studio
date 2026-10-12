extends SceneTree
## gamekit project-settings tool: autoloads, simple settings, and the audio bus layout.
## The host checkpoints project.godot, then atomically replaces it with the temp file this
## script writes via ProjectSettings.save_custom. Bus layouts are saved to a temp .tres
## the host renames into place.

var HH: GDScript


func _initialize() -> void:
	HH = load(get_script().resource_path.get_base_dir().path_join("hhgk.gd"))
	var req: Variant = HH.read_request()
	var result: Dictionary = _dispatch(req)
	HH.emit(result)
	quit(0 if bool(result.get("ok", false)) else 3)


func _dispatch(req: Variant) -> Dictionary:
	if not (req is Dictionary):
		return HH.fail("BAD_REQUEST", "missing or invalid --request file")
	var r: Dictionary = req
	match str(r.get("mode", "")):
		"apply":
			return _apply(r)
		"readback":
			return _readback(r)
		_:
			return HH.fail("BAD_REQUEST", "unknown mode")


func _apply(r: Dictionary) -> Dictionary:
	var temp_out: String = str(r.get("temp_out", ""))
	var path_err: String = _res_ok(temp_out, ".godot")
	if not path_err.is_empty():
		return HH.fail("BAD_REQUEST", path_err)
	if temp_out == "res://project.godot" or temp_out.ends_with("/project.godot"):
		return HH.fail("BAD_REQUEST", "temp_out must not be project.godot")
	var set_err: String = _apply_autoloads(r)
	if not set_err.is_empty():
		return HH.fail("VALIDATION_FAILED", set_err)
	var clear_err: String = _clear_autoloads(r.get("autoloads_clear", []))
	if not clear_err.is_empty():
		return HH.fail("VALIDATION_FAILED", clear_err)
	var setting_err: String = _apply_settings(r.get("settings", {}))
	if not setting_err.is_empty():
		return HH.fail("VALIDATION_FAILED", setting_err)
	var bus_temp: String = str(r.get("bus_temp_out", ""))
	if not bus_temp.is_empty():
		var bus_path_err: String = _res_ok(bus_temp, ".tres")
		if not bus_path_err.is_empty():
			return HH.fail("BAD_REQUEST", bus_path_err)
		var buses: Variant = r.get("buses", [])
		if not (buses is Array):
			return HH.fail("VALIDATION_FAILED", "buses must be a list")
		var berr: String = _write_buses(buses, bus_temp)
		if not berr.is_empty():
			return HH.fail("GODOT_FAILED", berr)
	var abs_out: String = ProjectSettings.globalize_path(temp_out)
	var serr: Error = ProjectSettings.save_custom(abs_out)
	if serr != OK:
		return HH.fail("GODOT_FAILED", "save_custom failed: " + error_string(serr))
	if not FileAccess.file_exists(abs_out):
		return HH.fail("GODOT_FAILED", "save_custom reported ok but wrote no file")
	return {"ok": true, "temp_out": temp_out, "bus_temp_out": bus_temp}


func _apply_autoloads(r: Dictionary) -> String:
	var set_map: Variant = r.get("autoloads_set", {})
	if not (set_map is Dictionary):
		return "autoloads_set must be an object"
	var mapping: Dictionary = set_map
	for key: Variant in mapping.keys():
		var name: String = str(key)
		if not _autoload_name_ok(name):
			return "bad autoload name " + name
		var raw: String = str(mapping[key])
		var script_path: String = raw.trim_prefix("*")
		if not script_path.begins_with("res://") or not script_path.ends_with(".gd") or script_path.contains(".."):
			return "bad autoload path " + raw
		if not FileAccess.file_exists(script_path):
			return "autoload script missing " + script_path
		var res: Resource = ResourceLoader.load(script_path, "Script", ResourceLoader.CACHE_MODE_IGNORE)
		if not (res is Script) or not (res as Script).can_instantiate():
			return "autoload script does not compile " + script_path
		var stored: String = raw if raw.begins_with("*") else "*" + raw
		ProjectSettings.set_setting("autoload/" + name, stored)
	return ""


func _clear_autoloads(clear_list: Variant) -> String:
	if not (clear_list is Array):
		return "autoloads_clear must be a list"
	for item: Variant in clear_list:
		var name: String = str(item)
		if not _autoload_name_ok(name):
			return "bad autoload name " + name
		var setting: String = "autoload/" + name
		if ProjectSettings.has_setting(setting):
			ProjectSettings.clear(setting)
	return ""


func _apply_settings(settings: Variant) -> String:
	if not (settings is Dictionary):
		return "settings must be an object"
	var table: Dictionary = settings
	for key: Variant in table.keys():
		var name: String = str(key)
		var err: String = _set_typed(name, table[key])
		if not err.is_empty():
			return err
	return ""


func _setting_name_ok(key: String) -> bool:
	if key.is_empty() or key.length() > 120 or key.contains("..") or key.begins_with("/") or key.ends_with("/"):
		return false
	for i: int in key.length():
		var c: String = key.substr(i, 1)
		var ok: bool = (c >= "a" and c <= "z") or (c >= "A" and c <= "Z") or (c >= "0" and c <= "9") or c == "_" or c == "." or c == "/"
		if not ok:
			return false
	return true


func _whole(f: float) -> bool:
	return not is_nan(f) and not is_inf(f) and f == floor(f)


func _set_typed(key: String, value: Variant) -> String:
	if not _setting_name_ok(key):
		return "bad setting name " + key
	if value == null:
		return key + " does not accept null"
	var existing: Variant = ProjectSettings.get_setting(key, null)
	var stored: Variant = value
	match typeof(existing):
		TYPE_BOOL:
			if typeof(value) != TYPE_BOOL:
				return key + " expects bool"
		TYPE_INT:
			if typeof(value) == TYPE_FLOAT and _whole(float(value)):
				stored = int(value)
			elif typeof(value) != TYPE_INT:
				return key + " expects int"
		TYPE_FLOAT:
			if typeof(value) != TYPE_FLOAT and typeof(value) != TYPE_INT:
				return key + " expects float"
			stored = float(value)
		TYPE_STRING:
			if typeof(value) != TYPE_STRING:
				return key + " expects string"
			if str(existing) == str(value):
				# Equal to the engine default, so save_custom would omit it. Shift the
				# initial value in this process so the explicit assignment is written.
				ProjectSettings.set_initial_value(key, "")
		TYPE_NIL:
			if typeof(value) == TYPE_FLOAT and _whole(float(value)):
				stored = int(value)
			elif typeof(value) != TYPE_BOOL and typeof(value) != TYPE_INT and typeof(value) != TYPE_FLOAT and typeof(value) != TYPE_STRING:
				return key + " supports bool, int, float, or string"
		_:
			return key + " is not a simple bool/int/float/string setting"
	ProjectSettings.set_setting(key, stored)
	return ""


func _write_buses(buses: Array, temp_out: String) -> String:
	if buses.is_empty():
		return "bus list is empty"
	if not (buses[0] is Dictionary) or str((buses[0] as Dictionary).get("name", "")) != "Master":
		return "first bus must be Master"
	while AudioServer.bus_count > 1:
		AudioServer.remove_bus(AudioServer.bus_count - 1)
	AudioServer.set_bus_name(0, "Master")
	for i: int in range(1, buses.size()):
		if not (buses[i] is Dictionary):
			return "bus spec must be an object"
		var spec: Dictionary = buses[i]
		var bname: String = str(spec.get("name", ""))
		if bname.is_empty() or bname.length() > 32 or bname.contains("/") or bname.contains(":"):
			return "bad bus name"
		AudioServer.add_bus()
		var idx: int = AudioServer.bus_count - 1
		AudioServer.set_bus_name(idx, bname)
		AudioServer.set_bus_send(idx, str(spec.get("send", "Master")))
	var layout: AudioBusLayout = AudioServer.generate_bus_layout()
	var err: Error = ResourceSaver.save(layout, temp_out)
	if err != OK:
		return "save bus layout failed: " + error_string(err)
	return ""


func _readback(r: Dictionary) -> Dictionary:
	var autoloads: Dictionary = {}
	for prop: Dictionary in ProjectSettings.get_property_list():
		var pname: String = str(prop["name"])
		if pname.begins_with("autoload/"):
			autoloads[pname.trim_prefix("autoload/")] = str(ProjectSettings.get_setting(pname))
	var scripts: Array = []
	var script_list: Variant = r.get("scripts", [])
	if script_list is Array:
		for item: Variant in script_list:
			var path: String = str(item)
			var res: Resource = null
			if FileAccess.file_exists(path):
				res = ResourceLoader.load(path, "Script", ResourceLoader.CACHE_MODE_IGNORE)
			var compiles: bool = res is Script and (res as Script).can_instantiate()
			scripts.append({"path": path, "compiles": compiles})
	var scenes: Array = []
	var scene_list: Variant = r.get("scenes", [])
	if scene_list is Array:
		for item2: Variant in scene_list:
			var spath: String = str(item2)
			var packed: Resource = null
			if FileAccess.file_exists(spath):
				packed = ResourceLoader.load(spath, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE)
			var scene_ok: bool = packed is PackedScene and (packed as PackedScene).can_instantiate()
			scenes.append({"path": spath, "compiles": scene_ok})
	var buses: Array = []
	for i: int in AudioServer.bus_count:
		buses.append({"name": AudioServer.get_bus_name(i), "send": AudioServer.get_bus_send(i)})
	var settings: Dictionary = {}
	var keys: Variant = r.get("setting_keys", [])
	if keys is Array:
		for key: Variant in keys:
			var ks: String = str(key)
			settings[ks] = str(ProjectSettings.get_setting(ks, ""))
	return {
		"ok": true,
		"autoloads": autoloads,
		"scripts": scripts,
		"scenes": scenes,
		"buses": buses,
		"bus_count": AudioServer.bus_count,
		"settings": settings,
	}


func _autoload_name_ok(name: String) -> bool:
	if name.is_empty() or name.length() > 40:
		return false
	var first: String = name.substr(0, 1)
	if not ((first >= "A" and first <= "Z") or first == "_"):
		return false
	for i: int in name.length():
		var c: String = name.substr(i, 1)
		var ok: bool = (c >= "a" and c <= "z") or (c >= "A" and c <= "Z") or (c >= "0" and c <= "9") or c == "_"
		if not ok:
			return false
	return true


func _res_ok(path: String, suffix: String) -> String:
	if path.is_empty() or not path.begins_with("res://") or path.contains("..") or path.contains("\\"):
		return "unsafe res path " + path
	if not path.ends_with(suffix):
		return "path must end with " + suffix
	return ""

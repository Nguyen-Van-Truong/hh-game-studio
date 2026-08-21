class_name HHAgentSettingsAdapter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")
const _CodecScript: GDScript = preload("res://addons/hh_agent/core/hh_variant_codec.gd")
const _MetaScript: GDScript = preload("res://addons/hh_agent/core/hh_scene_meta.gd")

## ProjectSettings / InputMap / autoload. Save then ConfigFile parse. Never handmade-text the project file.

const HH_PLUGIN_CFG: String = "res://addons/hh_agent/plugin.cfg"
const HH_PLUGIN_NAME: String = "hh_agent"
const FEATURES_KEY: String = "application/config/features"
const PLUGINS_KEY: String = "editor_plugins/enabled"
const PROJECT_TEXT: String = "res://project.godot"
const PROJECT_BIN: String = "res://project.binary"
const PROJECT_TMP: String = "res://project.godot.hh-tmp.godot"
const PROJECT_BAK: String = "res://project.godot.hh-bak"
const PROTECTED_AUTOLOAD: String = "HhReloadDriver"
const RELOAD_DRIVER_VALUE: String = "*res://hh_reload_driver.gd"


var _errors: HHAgentErrors = HHAgentErrors.new()
var _codec: HHAgentVariantCodec = HHAgentVariantCodec.new()
var _meta: HHAgentSceneMeta = HHAgentSceneMeta.new()
var _precondition_hold: Dictionary = {}


func handles(action: String) -> bool:
	return action == "settings" or action == "input" or action == "autoload" or action == "plugin"


func handle(
	command_id: String,
	method: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
	precondition: Dictionary,
) -> Dictionary:
	_precondition_hold = precondition
	if method != "godot.project":
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not a project verb", "")
	var def: Dictionary = actions.lookup(method, action)
	var post: String = str(def.get("postcondition", ""))
	if post.is_empty():
		post = _fallback_post(action)
	if action == "settings":
		return _settings(command_id, params, post)
	if action == "input":
		return _input(command_id, params, post)
	if action == "autoload":
		return _autoload(command_id, params, post)
	if action == "plugin":
		return _plugin(command_id, params, post)
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "project.%s is not a proven verb" % action, "")


func _fallback_post(action: String) -> String:
	if action == "settings":
		return "setting_equals_after_save"
	if action == "input":
		return "input_action_present"
	if action == "autoload":
		return "autoload_singleton_registered"
	if action == "plugin":
		return "plugin_enabled_matches"
	return "project_op"


func _settings(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var key: String = str(params.get("key", "")).strip_edges()
	if key.is_empty() or key.contains("..") or key.begins_with("/") or key.ends_with("/"):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "invalid setting key", "params.key")
	var op: String = _infer_settings_op(params)
	if op == "get":
		return _settings_get(command_id, key, post)
	if _dedicated_settings_key(key):
		return _errors.fail(command_id, HHAgentErrors.E_POLICY, "key requires a dedicated project verb", key)
	if op == "remove":
		var blocked_rm: Dictionary = _refuse_setting(command_id, key, null, true)
		if not blocked_rm.is_empty():
			return blocked_rm
		if ProjectSettings.has_setting(key):
			ProjectSettings.clear(key)
		return _save_setting(command_id, key, null, post, true, false)
	if op != "set":
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "op must be get, set, or remove", "params.op")
	if not params.has("value"):
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "set requires value", "params.value")
	var decoded: Dictionary = _codec.decode(params.get("value"), "params.value")
	if decoded.get("ok", false) != true:
		return _decode_fail(command_id, decoded)
	var value: Variant = decoded.get("value")
	var blocked: Dictionary = _refuse_setting(command_id, key, value, false)
	if not blocked.is_empty():
		return blocked
	ProjectSettings.set_setting(key, value)
	return _save_setting(command_id, key, value, post, false, true)


func _infer_settings_op(params: Dictionary) -> String:
	if params.has("op"):
		return str(params.get("op")).strip_edges()
	if params.has("value"):
		return "set"
	return "get"


func _settings_get(command_id: String, key: String, post: String) -> Dictionary:
	var exists: bool = ProjectSettings.has_setting(key)
	var memory: Variant = null
	if exists:
		memory = ProjectSettings.get_setting(key)
	var disk: Dictionary = _load_disk()
	if disk.get("ok", false) != true:
		return _unverified(command_id, str(disk.get("message", "project file unreadable")))
	var on_disk: bool = _disk_has(disk, key)
	var disk_val: Variant = _disk_get(disk, key)
	var readback: bool = exists == on_disk
	if exists and on_disk:
		readback = _values_match(memory, disk_val)
	if exists != on_disk:
		readback = false
	if not readback:
		return _unverified(command_id, "setting get memory/disk mismatch")
	var encoded: Dictionary = _encode_or_null(memory, exists)
	if encoded.get("ok", false) != true:
		return _unverified(command_id, "could not encode setting value")
	var after: Dictionary = _after_base(disk)
	after["key"] = key
	after["op"] = "get"
	after["exists"] = exists
	after["readback_equals"] = true
	after["value"] = {
		"schema": HHAgentVariantCodec.SCHEMA,
		"type": str(encoded.get("type", "")),
		"value": encoded.get("value"),
	}
	return _errors.ok_changed(command_id, _checks(post), after, false)


func _save_setting(
	command_id: String,
	key: String,
	value: Variant,
	post: String,
	removed: bool,
	changed: bool,
) -> Dictionary:
	var saved: Dictionary = _save_project(command_id)
	if saved.get("ok", false) != true:
		return saved
	var disk: Dictionary = saved.get("disk", {})
	if removed:
		if ProjectSettings.has_setting(key) or _disk_has(disk, key):
			return _unverified(command_id, "setting still present after clear")
	else:
		if not ProjectSettings.has_setting(key):
			return _unverified(command_id, "setting missing in memory after save")
		if not _disk_has(disk, key):
			return _unverified(command_id, "setting missing on disk after save")
		var memory: Variant = ProjectSettings.get_setting(key)
		var disk_val: Variant = _disk_get(disk, key)
		if not _values_match(memory, value) or not _values_match(disk_val, value):
			return _unverified(command_id, "setting disk parse did not match set value")
	var after: Dictionary = _after_base(disk)
	after["key"] = key
	after["op"] = "remove" if removed else "set"
	after["exists"] = not removed
	after["readback_equals"] = true
	return _errors.ok_changed(command_id, _checks(post), after, changed)


func _input(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var action_name: String = str(params.get("action_name", "")).strip_edges()
	if action_name.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "action_name required", "params.action_name")
	var op: String = "add"
	if params.has("op"):
		op = str(params.get("op")).strip_edges()
	var setting_key: String = "input/%s" % action_name
	if op == "remove":
		if InputMap.has_action(action_name):
			InputMap.erase_action(action_name)
		if ProjectSettings.has_setting(setting_key):
			ProjectSettings.clear(setting_key)
		var saved_rm: Dictionary = _save_project(command_id)
		if saved_rm.get("ok", false) != true:
			return saved_rm
		var disk_rm: Dictionary = saved_rm.get("disk", {})
		if InputMap.has_action(action_name) or _disk_has(disk_rm, setting_key):
			return _unverified(command_id, "input action still present after remove")
		var after_rm: Dictionary = _after_base(disk_rm)
		after_rm["action_name"] = action_name
		after_rm["op"] = "remove"
		after_rm["exists"] = false
		after_rm["readback_equals"] = true
		return _errors.ok_changed(command_id, _checks(post), after_rm, true)
	if op != "add":
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "op must be add or remove", "params.op")
	if not params.has("keycode"):
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "add requires keycode", "params.keycode")
	var keycode_name: String = str(params.get("keycode", "")).strip_edges()
	var code: int = _keycode_of(keycode_name)
	if code < 0:
		return _errors.fail(command_id, HHAgentErrors.E_OUT_OF_BOUNDS, "unknown keycode", "params.keycode")
	if not InputMap.has_action(action_name):
		InputMap.add_action(action_name)
	var ev: InputEventKey = InputEventKey.new()
	ev.keycode = code as Key
	ev.physical_keycode = code as Key
	if not _action_has_key(action_name, code):
		InputMap.action_add_event(action_name, ev)
	_persist_input_action(action_name)
	var saved: Dictionary = _save_project(command_id)
	if saved.get("ok", false) != true:
		return saved
	var disk: Dictionary = saved.get("disk", {})
	if not InputMap.has_action(action_name):
		return _unverified(command_id, "InputMap missing action after save")
	if not _disk_has(disk, setting_key):
		return _unverified(command_id, "input action missing on disk after save")
	if not _action_has_key(action_name, code):
		return _unverified(command_id, "InputMap event missing after save")
	var after: Dictionary = _after_base(disk)
	after["action_name"] = action_name
	after["keycode"] = keycode_name
	after["op"] = "add"
	after["exists"] = true
	after["readback_equals"] = true
	return _errors.ok_changed(command_id, _checks(post), after, true)


func _autoload(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var name_s: String = str(params.get("name", "")).strip_edges()
	if name_s.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "autoload name required", "params.name")
	if name_s == PROTECTED_AUTOLOAD:
		return _errors.fail(command_id, HHAgentErrors.E_POLICY, "protected autoload cannot be changed", "params.name")
	var op: String = "add"
	if params.has("op"):
		op = str(params.get("op")).strip_edges()
	var setting_key: String = "autoload/%s" % name_s
	if op == "remove":
		if ProjectSettings.has_setting(setting_key):
			ProjectSettings.clear(setting_key)
		var saved_rm: Dictionary = _save_project(command_id)
		if saved_rm.get("ok", false) != true:
			return saved_rm
		var disk_rm: Dictionary = saved_rm.get("disk", {})
		if ProjectSettings.has_setting(setting_key) or _disk_has(disk_rm, setting_key):
			return _unverified(command_id, "autoload still present after remove")
		var after_rm: Dictionary = _after_base(disk_rm)
		after_rm["name"] = name_s
		after_rm["op"] = "remove"
		after_rm["exists"] = false
		after_rm["readback_equals"] = true
		return _errors.ok_changed(command_id, _checks(post), after_rm, true)
	if op == "reorder":
		if not params.has("index"):
			return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "reorder requires index", "params.index")
		if not ProjectSettings.has_setting(setting_key):
			return _errors.fail(command_id, HHAgentErrors.E_PATH, "autoload not registered", "params.name")
		var index: int = int(params.get("index"))
		var reordered: Dictionary = _reorder_autoload(command_id, name_s, index)
		if reordered.get("ok", false) != true:
			return reordered
		var saved_ord: Dictionary = _save_project(command_id)
		if saved_ord.get("ok", false) != true:
			return saved_ord
		var disk_ord: Dictionary = saved_ord.get("disk", {})
		var names: PackedStringArray = _disk_autoload_names(disk_ord)
		var got_i: int = _index_of(names, name_s)
		if got_i != index:
			return _unverified(command_id, "autoload order on disk did not match")
		var after_ord: Dictionary = _after_base(disk_ord)
		after_ord["name"] = name_s
		after_ord["op"] = "reorder"
		after_ord["index"] = index
		after_ord["exists"] = true
		after_ord["readback_equals"] = true
		return _errors.ok_changed(command_id, _checks(post), after_ord, true)
	if op != "add":
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "op must be add, remove, or reorder", "params.op")
	if not params.has("path"):
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "add requires path", "params.path")
	var res_path: String = str(params.get("path", "")).strip_edges().replace("\\", "/")
	var ref: Dictionary = _ref_ok(command_id, res_path)
	if ref.get("ok", false) != true:
		return ref
	var stored: String = "*%s" % res_path
	ProjectSettings.set_setting(setting_key, stored)
	var saved: Dictionary = _save_project(command_id)
	if saved.get("ok", false) != true:
		return saved
	var disk: Dictionary = saved.get("disk", {})
	if not ProjectSettings.has_setting(setting_key) or not _disk_has(disk, setting_key):
		return _unverified(command_id, "autoload missing after save")
	var disk_val: String = str(_disk_get(disk, setting_key))
	if not disk_val.contains(res_path):
		return _unverified(command_id, "autoload path on disk did not match")
	var after: Dictionary = _after_base(disk)
	after["name"] = name_s
	after["path"] = res_path
	after["op"] = "add"
	after["exists"] = true
	after["readback_equals"] = true
	return _errors.ok_changed(command_id, _checks(post), after, true)


func _plugin(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var raw_name: String = str(params.get("plugin_name", "")).strip_edges().replace("\\", "/")
	if raw_name.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "plugin_name required", "params.plugin_name")
	var enabled: bool = params.get("enabled", false) == true
	var cfg: String = _plugin_cfg_of(raw_name)
	if enabled and not _is_hh_agent_plugin(raw_name, cfg):
		return _errors.fail(command_id, HHAgentErrors.E_POLICY, "third-party editor plugin enable is refused", "params.plugin_name")
	if not enabled and _is_hh_agent_plugin(raw_name, cfg):
		return _errors.fail(command_id, HHAgentErrors.E_POLICY, "hh_agent plugin cannot be disabled", "params.plugin_name")
	if not _is_hh_agent_plugin(raw_name, cfg):
		return _errors.fail(command_id, HHAgentErrors.E_POLICY, "only hh_agent may be toggled", "params.plugin_name")
	var current: PackedStringArray = _enabled_plugins()
	if enabled and _packed_has(current, HH_PLUGIN_CFG):
		var disk: Dictionary = _load_disk()
		if disk.get("ok", false) != true:
			return _unverified(command_id, str(disk.get("message", "project file unreadable")))
		var after: Dictionary = _after_base(disk)
		after["plugin_name"] = HH_PLUGIN_NAME
		after["enabled"] = true
		after["readback_equals"] = true
		return _errors.ok_changed(command_id, _checks(post), after, false)
	return _errors.fail(command_id, HHAgentErrors.E_POLICY, "plugin enable list is hh_agent-only", "params.plugin_name")


func _dedicated_settings_key(key: String) -> bool:
	return (
		key.begins_with("input/")
		or key.begins_with("autoload/")
		or key.begins_with("editor_plugins/")
		or key.begins_with("debug/gdscript/warnings/")
	)


func _refuse_setting(command_id: String, key: String, value: Variant, removing: bool) -> Dictionary:
	if _dedicated_settings_key(key):
		return _errors.fail(command_id, HHAgentErrors.E_POLICY, "key requires a dedicated project verb", key)
	if key == FEATURES_KEY:
		if removing:
			return _errors.fail(command_id, HHAgentErrors.E_POLICY, "application features cannot be cleared", key)
		var cur: PackedStringArray = _as_packed_strings(ProjectSettings.get_setting(FEATURES_KEY, PackedStringArray()))
		var nxt: PackedStringArray = _as_packed_strings(value)
		if not _packed_same(cur, nxt):
			return _errors.fail(command_id, HHAgentErrors.E_POLICY, "application features cannot be changed to a vendor set", key)
		return {}
	if _looks_like_addon_enable(key, value):
		return _errors.fail(command_id, HHAgentErrors.E_POLICY, "refusing a setting that enables a third-party addon", key)
	return {}


func _looks_like_addon_enable(key: String, value: Variant) -> bool:
	var blob: String = ("%s %s" % [key, str(value)]).replace("\\", "/").to_lower()
	if blob.contains("res://addons/") and not blob.contains("res://addons/hh_agent/"):
		return true
	return false


func _ref_ok(command_id: String, res_path: String) -> Dictionary:
	if not res_path.begins_with("res://"):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "path must be res://", res_path)
	if res_path.contains(".."):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "path escapes via ..", res_path)
	var norm: String = res_path.replace("\\", "/").to_lower()
	if norm == "res://project.godot" or norm.ends_with("/project.godot"):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "project.godot cannot be an autoload", res_path)
	if norm.begins_with("res://.godot/") or norm.begins_with("res://.hh-agent/"):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "autoload path is locked", res_path)
	if norm.begins_with("res://addons/") and not norm.begins_with("res://addons/hh_agent/"):
		return _errors.fail(command_id, HHAgentErrors.E_POLICY, "third-party addon autoload is refused", res_path)
	if not (res_path.ends_with(".gd") or res_path.ends_with(".tscn")):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "autoload must be .gd or .tscn", res_path)
	var abs_path: String = ProjectSettings.globalize_path(res_path)
	var root: String = ProjectSettings.globalize_path("res://")
	if not abs_path.begins_with(root):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "path is outside project root", res_path)
	if not FileAccess.file_exists(res_path):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "autoload script missing", res_path)
	return {"ok": true}


func _reorder_autoload(command_id: String, name_s: String, index: int) -> Dictionary:
	var names: PackedStringArray = _autoload_names()
	var cur: int = _index_of(names, name_s)
	if cur < 0:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "autoload not registered", "params.name")
	if index < 0 or index >= names.size():
		return _errors.fail(command_id, HHAgentErrors.E_OUT_OF_BOUNDS, "autoload index out of range", "params.index")
	var ordered: PackedStringArray = PackedStringArray()
	var i: int = 0
	while i < names.size():
		if i != cur:
			ordered.append(names[i])
		i += 1
	var next_names: PackedStringArray = PackedStringArray()
	var j: int = 0
	var inserted: bool = false
	while j < ordered.size() + 1:
		if j == index:
			next_names.append(name_s)
			inserted = true
		if j < ordered.size():
			next_names.append(ordered[j])
		j += 1
	if not inserted:
		next_names.append(name_s)
	var values: Dictionary = {}
	for item: String in names:
		values[item] = ProjectSettings.get_setting("autoload/%s" % item)
	for item2: String in names:
		ProjectSettings.clear("autoload/%s" % item2)
	for item3: String in next_names:
		ProjectSettings.set_setting("autoload/%s" % item3, values[item3])
	return {"ok": true}


func _persist_input_action(action_name: String) -> void:
	var events: Array = []
	if InputMap.has_action(action_name):
		for ev_v: Variant in InputMap.action_get_events(action_name):
			events.append(ev_v)
	var deadzone: float = 0.5
	if InputMap.has_action(action_name):
		deadzone = InputMap.action_get_deadzone(action_name)
	ProjectSettings.set_setting(
		"input/%s" % action_name,
		{"deadzone": deadzone, "events": events},
	)


func _save_project(command_id: String) -> Dictionary:
	var drift: Dictionary = _project_hash_conflict(command_id)
	if not drift.is_empty():
		return drift
	_ensure_reload_driver()
	_recover_project_bak()
	var dest: String = PROJECT_TEXT
	var tmp: String = PROJECT_TMP
	var bak: String = PROJECT_BAK
	var dest_abs: String = ProjectSettings.globalize_path(dest)
	var tmp_abs: String = ProjectSettings.globalize_path(tmp)
	var bak_abs: String = ProjectSettings.globalize_path(bak)
	if FileAccess.file_exists(tmp):
		DirAccess.remove_absolute(tmp_abs)
	var err: Error = ProjectSettings.save_custom(tmp)
	if err != OK:
		if FileAccess.file_exists(tmp):
			DirAccess.remove_absolute(tmp_abs)
		return _unverified(command_id, "ProjectSettings.save_custom failed (%d)" % int(err))
	if not FileAccess.file_exists(tmp):
		return _unverified(command_id, "save_custom tmp missing")
	var tmp_bytes: PackedByteArray = FileAccess.get_file_as_bytes(tmp)
	if tmp_bytes.is_empty():
		DirAccess.remove_absolute(tmp_abs)
		return _unverified(command_id, "save_custom tmp is empty")
	var tmp_cfg: ConfigFile = ConfigFile.new()
	if tmp_cfg.load(tmp) != OK:
		DirAccess.remove_absolute(tmp_abs)
		return _unverified(command_id, "ConfigFile.load tmp failed")
	var existed: bool = FileAccess.file_exists(dest)
	if existed:
		if FileAccess.file_exists(bak):
			DirAccess.remove_absolute(bak_abs)
		var bak_err: Error = DirAccess.rename_absolute(dest_abs, bak_abs)
		if bak_err != OK:
			DirAccess.remove_absolute(tmp_abs)
			return _unverified(command_id, "could not park project.godot for atomic replace")
	var ren: Error = DirAccess.rename_absolute(tmp_abs, dest_abs)
	if ren != OK:
		if existed:
			DirAccess.rename_absolute(bak_abs, dest_abs)
		if FileAccess.file_exists(tmp):
			DirAccess.remove_absolute(tmp_abs)
		return _unverified(command_id, "atomic rename failed: %s" % error_string(ren))
	if existed and FileAccess.file_exists(bak):
		DirAccess.remove_absolute(bak_abs)
	if FileAccess.file_exists(tmp):
		DirAccess.remove_absolute(tmp_abs)
	if not FileAccess.file_exists(dest):
		return _unverified(command_id, "dest missing after atomic rename")
	var prove: ConfigFile = ConfigFile.new()
	if prove.load(dest) != OK:
		return _unverified(command_id, "ConfigFile.load dest failed after atomic replace")
	var disk: Dictionary = _load_disk()
	if disk.get("ok", false) != true:
		return _unverified(command_id, str(disk.get("message", "project file unreadable after save")))
	var protect: Dictionary = _require_reload_driver(command_id, disk)
	if not protect.is_empty():
		return protect
	return {"ok": true, "disk": disk}


func _project_hash_conflict(command_id: String) -> Dictionary:
	var expected: String = str(_precondition_hold.get("scene_hash", ""))
	if expected.is_empty():
		return {}
	var now_hash: String = _meta.disk_hash(PROJECT_TEXT)
	if now_hash != expected:
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "project.godot hash drifted", PROJECT_TEXT)
	return {}


func _ensure_reload_driver() -> void:
	var key: String = "autoload/%s" % PROTECTED_AUTOLOAD
	if not ProjectSettings.has_setting(key) or str(ProjectSettings.get_setting(key)) != RELOAD_DRIVER_VALUE:
		ProjectSettings.set_setting(key, RELOAD_DRIVER_VALUE)


func _require_reload_driver(command_id: String, disk: Dictionary) -> Dictionary:
	var key: String = "autoload/%s" % PROTECTED_AUTOLOAD
	if not _disk_has(disk, key):
		return _unverified(command_id, "protected HhReloadDriver missing from project.godot")
	var got: String = str(_disk_get(disk, key))
	if got != RELOAD_DRIVER_VALUE and not got.contains("hh_reload_driver.gd"):
		return _unverified(command_id, "protected HhReloadDriver path drifted on disk")
	return {}


func _recover_project_bak() -> void:
	if FileAccess.file_exists(PROJECT_TEXT):
		if FileAccess.file_exists(PROJECT_BAK):
			DirAccess.remove_absolute(ProjectSettings.globalize_path(PROJECT_BAK))
		return
	if FileAccess.file_exists(PROJECT_BAK):
		DirAccess.rename_absolute(
			ProjectSettings.globalize_path(PROJECT_BAK),
			ProjectSettings.globalize_path(PROJECT_TEXT),
		)


func _load_disk() -> Dictionary:
	var cfg: ConfigFile = ConfigFile.new()
	if FileAccess.file_exists(PROJECT_TEXT):
		var err: Error = cfg.load(PROJECT_TEXT)
		if err != OK:
			return {"ok": false, "message": "ConfigFile.load project.godot failed"}
		return {
			"ok": true,
			"cfg": cfg,
			"source": "project.godot",
			"res": PROJECT_TEXT,
			"binary": false,
			"disk_hash": _meta.disk_hash(PROJECT_TEXT),
		}
	if FileAccess.file_exists(PROJECT_BIN):
		var bytes: PackedByteArray = FileAccess.get_file_as_bytes(PROJECT_BIN)
		if bytes.is_empty():
			return {"ok": false, "message": "project.binary is empty"}
		return {
			"ok": true,
			"cfg": cfg,
			"source": "project.binary",
			"res": PROJECT_BIN,
			"binary": true,
			"disk_hash": _meta.disk_hash(PROJECT_BIN),
		}
	return {"ok": false, "message": "project.godot / project.binary missing"}


func _after_base(disk: Dictionary) -> Dictionary:
	return {
		"disk_source": str(disk.get("source", "")),
		"disk_hash": str(disk.get("disk_hash", "")),
		"path": str(disk.get("res", PROJECT_TEXT)),
		"source": "editor",
	}


func _disk_has(disk: Dictionary, setting: String) -> bool:
	if disk.get("binary", false) == true:
		return ProjectSettings.has_setting(setting)
	var cfg_v: Variant = disk.get("cfg")
	if cfg_v is ConfigFile:
		var parts: PackedStringArray = _section_key(setting)
		if parts.size() != 2:
			return false
		return (cfg_v as ConfigFile).has_section_key(parts[0], parts[1])
	return false


func _disk_get(disk: Dictionary, setting: String) -> Variant:
	if disk.get("binary", false) == true:
		return ProjectSettings.get_setting(setting)
	var cfg_v: Variant = disk.get("cfg")
	if cfg_v is ConfigFile:
		var parts: PackedStringArray = _section_key(setting)
		if parts.size() != 2:
			return null
		return (cfg_v as ConfigFile).get_value(parts[0], parts[1], null)
	return null


func _disk_autoload_names(disk: Dictionary) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	if disk.get("binary", false) == true:
		return _autoload_names()
	var cfg_v: Variant = disk.get("cfg")
	if cfg_v is ConfigFile:
		var keys: PackedStringArray = (cfg_v as ConfigFile).get_section_keys("autoload")
		for item: String in keys:
			out.append(item)
	return out


func _section_key(setting: String) -> PackedStringArray:
	var slash: int = setting.find("/")
	if slash <= 0:
		return PackedStringArray()
	return PackedStringArray([setting.substr(0, slash), setting.substr(slash + 1)])


func _autoload_names() -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	var props: Array = ProjectSettings.get_property_list()
	for item_v: Variant in props:
		if item_v is Dictionary:
			var pname: String = str((item_v as Dictionary).get("name", ""))
			if pname.begins_with("autoload/"):
				out.append(pname.substr(9))
	return out


func _index_of(items: PackedStringArray, name_s: String) -> int:
	var i: int = 0
	while i < items.size():
		if items[i] == name_s:
			return i
		i += 1
	return -1


func _enabled_plugins() -> PackedStringArray:
	return _as_packed_strings(ProjectSettings.get_setting(PLUGINS_KEY, PackedStringArray()))


func _plugin_cfg_of(raw: String) -> String:
	if raw.begins_with("res://"):
		return raw
	if raw == HH_PLUGIN_NAME:
		return HH_PLUGIN_CFG
	return "res://addons/%s/plugin.cfg" % raw


func _is_hh_agent_plugin(raw: String, cfg: String) -> bool:
	if raw == HH_PLUGIN_NAME or raw == HH_PLUGIN_CFG:
		return true
	return cfg == HH_PLUGIN_CFG


func _keycode_of(name_s: String) -> int:
	if name_s == "KEY_SPACE":
		return KEY_SPACE
	if name_s == "KEY_ENTER":
		return KEY_ENTER
	if name_s == "KEY_ESCAPE":
		return KEY_ESCAPE
	if name_s == "KEY_LEFT":
		return KEY_LEFT
	if name_s == "KEY_RIGHT":
		return KEY_RIGHT
	if name_s == "KEY_UP":
		return KEY_UP
	if name_s == "KEY_DOWN":
		return KEY_DOWN
	if name_s.length() == 5 and name_s.begins_with("KEY_"):
		var ch: String = name_s.substr(4, 1)
		if ch >= "A" and ch <= "Z":
			return int(KEY_A) + (ch.unicode_at(0) - 65)
		if ch >= "0" and ch <= "9":
			return int(KEY_0) + (ch.unicode_at(0) - 48)
	return -1


func _action_has_key(action_name: String, code: int) -> bool:
	if not InputMap.has_action(action_name):
		return false
	for ev_v: Variant in InputMap.action_get_events(action_name):
		if ev_v is InputEventKey and int((ev_v as InputEventKey).keycode) == code:
			return true
	return false


func _values_match(a: Variant, b: Variant) -> bool:
	if typeof(a) == TYPE_PACKED_STRING_ARRAY or typeof(b) == TYPE_PACKED_STRING_ARRAY or typeof(a) == TYPE_ARRAY or typeof(b) == TYPE_ARRAY:
		return _packed_same(_as_packed_strings(a), _as_packed_strings(b))
	if typeof(a) == TYPE_STRING or typeof(a) == TYPE_STRING_NAME or typeof(b) == TYPE_STRING or typeof(b) == TYPE_STRING_NAME:
		return str(a) == str(b)
	if typeof(a) == TYPE_BOOL or typeof(a) == TYPE_INT or typeof(a) == TYPE_FLOAT:
		return _codec.same(a, b)
	if typeof(a) == typeof(b) and typeof(a) != TYPE_NIL:
		if _codec.same(a, b):
			return true
	return str(a) == str(b)


func _as_packed_strings(value: Variant) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	if value is PackedStringArray:
		for item: String in value:
			out.append(item)
		return out
	if value is Array:
		for item_v: Variant in value:
			out.append(str(item_v))
	elif typeof(value) == TYPE_STRING:
		out.append(str(value))
	return out


func _packed_same(a: PackedStringArray, b: PackedStringArray) -> bool:
	if a.size() != b.size():
		return false
	var i: int = 0
	while i < a.size():
		if a[i] != b[i]:
			return false
		i += 1
	return true


func _packed_has(items: PackedStringArray, needle: String) -> bool:
	for item: String in items:
		if item == needle:
			return true
	return false


func _encode_or_null(value: Variant, exists: bool) -> Dictionary:
	if not exists:
		return {"ok": true, "type": "string", "value": ""}
	return _codec.encode(value)


func _decode_fail(command_id: String, decoded: Dictionary) -> Dictionary:
	var err_v: Variant = decoded.get("error", {})
	var err: Dictionary = err_v if err_v is Dictionary else {}
	return _errors.fail(
		command_id,
		str(err.get("code", HHAgentErrors.E_INVALID_VARIANT)),
		str(err.get("message", "invalid variant")),
		str(err.get("path", "params.value")),
	)


func _checks(post: String) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	out.append(post)
	return out


func _unverified(command_id: String, message: String) -> Dictionary:
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, message, "")

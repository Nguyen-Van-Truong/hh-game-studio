class_name HHAgentReadAdapters
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")
const _MetaScript: GDScript = preload("res://addons/hh_agent/core/hh_scene_meta.gd")

## Main-thread read/view adapters. Mutate is never applied here.

var _errors: HHAgentErrors = HHAgentErrors.new()
var _meta: HHAgentSceneMeta = HHAgentSceneMeta.new()


func handle(command_id: String, method: String, action: String, params: Dictionary, actions: HHAgentActions) -> Dictionary:
	var def: Dictionary = actions.lookup(method, action)
	var post: String = _post_name(def, method, action)
	if method == "godot.capabilities" and action == "describe":
		return _describe(command_id, params, post)
	if method == "godot.project" and action == "inspect":
		return _project_inspect(command_id, params, post)
	if method == "godot.project" and action == "doctor":
		return _project_doctor(command_id, post)
	if method == "godot.editor" and action == "state":
		return _editor_state(command_id, params, post)
	if method == "godot.editor" and action == "select":
		return _editor_select(command_id, params, post)
	if method == "godot.scene" and action == "read":
		return _scene_read(command_id, params, post)
	if method == "godot.scene" and action == "list_tabs":
		return _scene_list_tabs(command_id, params, post)
	if method == "godot.scene" and action == "dependencies":
		return _scene_deps(command_id, params, post)
	if method == "godot.node" and action == "query":
		return _node_query(command_id, params, post)
	if method == "godot.property" and action == "get":
		return _property_get(command_id, params, post)
	if method == "godot.resource" and action == "load":
		return _resource_load(command_id, params, post)
	if method == "godot.resource" and action == "uid":
		return _resource_uid(command_id, params, post)
	if method == "godot.signal" and action == "list":
		return _signal_list(command_id, params, post)
	if method == "godot.signal" and action == "inspect":
		return _signal_inspect(command_id, params, post)
	if method == "godot.script" and action == "read":
		return _script_read(command_id, params, post)
	if method == "godot.script" and action == "validate":
		return _script_validate(command_id, params, post)
	if method == "godot.script" and action == "diagnostics":
		return _script_diagnostics(command_id, params, post)
	if method == "godot.script" and action == "open_at":
		return _script_open_at(command_id, params, post)
	if method == "godot.asset" and action == "dependencies":
		return _asset_deps(command_id, params, post)
	if method == "godot.asset" and action == "preview":
		return _unverified(command_id, "asset preview is async; no cached handle proven")
	if method == "godot.play" and action == "status":
		return _play_status(command_id, params, post)
	if method == "godot.play" and action == "logs":
		return _unverified(command_id, "play logs require the Play process log ring (R6)")
	if method == "godot.tilemap" and action == "query":
		return _tilemap_query(command_id, params, post)
	if method == "godot.ui" and action == "accessibility":
		return _ui_access(command_id, params, post)
	if method.begins_with("godot.runtime"):
		return _unverified(command_id, "runtime observation requires Play process (R6)")
	if method == "godot.test" or method == "godot.export":
		return _unverified(command_id, "%s read is not proven in R2-WP6" % method)
	if method == "godot.animation" and action == "preview":
		return _unverified(command_id, "animation preview has no proven playback getter")
	if method == "godot.editor":
		return _unverified(command_id, "editor.%s has no proven readback on stock EditorInterface" % action)
	if method == "godot.ui" and action == "focus":
		return _unverified(command_id, "focus owner getter not proven for this Control")
	return _unverified(command_id, "no read adapter")


func _post_name(def: Dictionary, method: String, action: String) -> String:
	if def.has("id"):
		var known: Dictionary = {
			"capabilities.describe": "describe_kind_payload_present",
			"project.inspect": "project_inspect_matches_project_godot",
			"project.doctor": "doctor_report_complete",
			"scene.read": "scene_tree_summary_matches",
			"scene.list_tabs": "open_scene_tabs_match",
			"scene.dependencies": "dependency_list_complete",
			"node.query": "query_hits_match_tree",
			"property.get": "property_value_matches_get",
			"resource.load": "resource_load_ok",
			"resource.uid": "uid_maps_to_path",
			"signal.list": "signal_list_complete",
			"signal.inspect": "connection_list_matches",
			"script.read": "script_text_matches_disk",
			"script.validate": "script_validate_clean",
			"script.diagnostics": "diagnostics_list_complete",
			"script.open_at": "script_editor_line_visible",
			"asset.dependencies": "dependency_owners_listed",
			"tilemap.query": "cell_query_matches_layer",
			"ui.accessibility": "accessibility_fields_present",
			"editor.state": "editor_state_snapshot",
			"editor.select": "selection_paths_match",
			"play.status": "play_status_known",
			"play.logs": "play_logs_returned",
		}
		var action_id: String = "%s.%s" % [method.trim_prefix("godot."), action]
		if method == "godot.capabilities":
			action_id = "capabilities.describe"
		if method == "godot.project":
			action_id = "project.%s" % action
		if known.has(action_id):
			return str(known[action_id])
	return "read_postcondition"


func _ok(command_id: String, check: String, after: Dictionary) -> Dictionary:
	var checks: PackedStringArray = PackedStringArray()
	checks.append(check)
	return _errors.ok_read(command_id, checks, after)


func _unverified(command_id: String, message: String) -> Dictionary:
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, message, "")


func _skew(command_id: String, message: String) -> Dictionary:
	return _errors.fail(command_id, HHAgentErrors.E_VERSION_SKEW, message, "godot.version")


func _path_err(command_id: String, message: String, raw: String) -> Dictionary:
	return _errors.fail(command_id, HHAgentErrors.E_PATH, message, raw)


func _page_limit(params: Dictionary) -> int:
	var limit: int = HHAgentConstants.DEFAULT_PAGE
	if params.has("limit"):
		limit = int(params.get("limit"))
	if limit < 1:
		limit = 1
	if limit > HHAgentConstants.MAX_PAGE:
		limit = HHAgentConstants.MAX_PAGE
	return limit


func _page_offset(params: Dictionary) -> int:
	if not params.has("cursor"):
		return 0
	var raw: String = str(params.get("cursor"))
	if raw.is_valid_int():
		return maxi(0, int(raw))
	return 0


func _as_str_array(raw: Variant) -> Array:
	var out: Array = []
	if raw is PackedStringArray:
		for item: String in raw:
			out.append(item)
		return out
	if raw is Array:
		for item_v: Variant in raw:
			out.append(str(item_v))
	return out


func _page_dict(items: Array, params: Dictionary) -> Dictionary:
	var limit: int = _page_limit(params)
	var offset: int = _page_offset(params)
	var total: int = items.size()
	var end: int = mini(offset + limit, total)
	var page: Array = []
	var i: int = offset
	while i < end:
		page.append(items[i])
		i += 1
	var next_cursor: String = ""
	if end < total:
		next_cursor = str(end)
	return {
		"items": page,
		"total": total,
		"offset": offset,
		"limit": limit,
		"next_cursor": next_cursor,
		"has_more": end < total,
	}


func _jail(command_id: String, res_path: String) -> Dictionary:
	if not res_path.begins_with("res://"):
		return _path_err(command_id, "path must be res://", res_path)
	if res_path.contains(".."):
		return _path_err(command_id, "path escapes via ..", res_path)
	var abs_path: String = ProjectSettings.globalize_path(res_path)
	var root: String = ProjectSettings.globalize_path("res://")
	if not abs_path.begins_with(root):
		return _path_err(command_id, "path is outside project root", res_path)
	return {"ok": true, "abs": abs_path}


func _godot_string() -> String:
	# Match `godot --version` / pin id: 4.7.1.stable.official.a13da4feb
	var info: Dictionary = Engine.get_version_info()
	var hash_s: String = str(info.get("hash", ""))
	if hash_s.length() > 9:
		hash_s = hash_s.substr(0, 9)
	return "%s.%s.%s.%s.%s.%s" % [
		str(info.get("major", 0)),
		str(info.get("minor", 0)),
		str(info.get("patch", 0)),
		str(info.get("status", "")),
		str(info.get("build", "")),
		hash_s,
	]


func _describe(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var kind: String = str(params.get("kind", ""))
	var observed: String = _godot_string()
	if observed != HHAgentConstants.PINNED_GODOT:
		return _skew(command_id, "Godot %s != pin %s" % [observed, HHAgentConstants.PINNED_GODOT])
	if kind == "version":
		var names: PackedStringArray = ClassDB.get_class_list()
		names.sort()
		var prefix: String = str(params.get("prefix", ""))
		var filtered: Array = []
		for class_name_v: String in names:
			if prefix.is_empty() or class_name_v.begins_with(prefix):
				filtered.append(class_name_v)
		var page: Dictionary = _page_dict(filtered, params)
		var after: Dictionary = {
			"kind": "version",
			"godot": observed,
			"protocol": HHAgentConstants.PROTOCOL,
			"plugin": HHAgentConstants.PLUGIN_VERSION,
			"classes": page,
		}
		return _ok(command_id, post, after)
	if kind == "class":
		var class_name_s: String = str(params.get("class_name", ""))
		if not ClassDB.class_exists(class_name_s):
			return _unverified(command_id, "ClassDB has no class %s" % class_name_s)
		var props: Array = _slim_props(ClassDB.class_get_property_list(class_name_s, true))
		var methods: Array = _slim_methods(ClassDB.class_get_method_list(class_name_s, true))
		var after_class: Dictionary = {
			"kind": "class",
			"class_name": class_name_s,
			"parent": str(ClassDB.get_parent_class(class_name_s)),
			"instantiable": ClassDB.can_instantiate(class_name_s),
			"properties": _page_dict(props, params),
			"methods": _page_dict(methods, params),
		}
		return _ok(command_id, post, after_class)
	if kind == "property":
		var cls: String = str(params.get("class_name", ""))
		var prop: String = str(params.get("property_name", ""))
		var found: Dictionary = {}
		for item_v: Variant in ClassDB.class_get_property_list(cls, false):
			if item_v is Dictionary and str((item_v as Dictionary).get("name", "")) == prop:
				found = _slim_prop(item_v as Dictionary)
				break
		if found.is_empty():
			return _unverified(command_id, "property %s.%s not in ClassDB" % [cls, prop])
		return _ok(command_id, post, {"kind": "property", "class_name": cls, "property": found})
	if kind == "method":
		var cls_m: String = str(params.get("class_name", ""))
		var meth: String = str(params.get("method_name", ""))
		var found_m: Dictionary = {}
		for item_v2: Variant in ClassDB.class_get_method_list(cls_m, false):
			if item_v2 is Dictionary and str((item_v2 as Dictionary).get("name", "")) == meth:
				found_m = _slim_method(item_v2 as Dictionary)
				break
		if found_m.is_empty():
			return _unverified(command_id, "method %s.%s not in ClassDB" % [cls_m, meth])
		return _ok(command_id, post, {"kind": "method", "class_name": cls_m, "method": found_m})
	if kind == "action":
		return _unverified(command_id, "action describe is answered by the sidecar")
	return _unverified(command_id, "unknown describe kind")


func _slim_props(raw: Array) -> Array:
	var out: Array = []
	for item_v: Variant in raw:
		if item_v is Dictionary:
			var item: Dictionary = item_v
			var usage: int = int(item.get("usage", 0))
			if usage & PROPERTY_USAGE_CATEGORY:
				continue
			if usage & PROPERTY_USAGE_GROUP:
				continue
			if usage & PROPERTY_USAGE_SUBGROUP:
				continue
			out.append(_slim_prop(item))
	return out


func _slim_prop(item: Dictionary) -> Dictionary:
	return {
		"name": str(item.get("name", "")),
		"type": int(item.get("type", 0)),
		"class_name": str(item.get("class_name", "")),
	}


func _slim_methods(raw: Array) -> Array:
	var out: Array = []
	for item_v: Variant in raw:
		if item_v is Dictionary:
			out.append(_slim_method(item_v as Dictionary))
	return out


func _slim_method(item: Dictionary) -> Dictionary:
	var args_out: Array = []
	var args_v: Variant = item.get("args", [])
	if args_v is Array:
		for arg_v: Variant in args_v:
			if arg_v is Dictionary:
				args_out.append({
					"name": str((arg_v as Dictionary).get("name", "")),
					"type": int((arg_v as Dictionary).get("type", 0)),
				})
	return {"name": str(item.get("name", "")), "args": args_out}


func _project_inspect(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var name: String = str(ProjectSettings.get_setting("application/config/name", ""))
	var main_scene: String = str(ProjectSettings.get_setting("application/run/main_scene", ""))
	var features: Array = _as_str_array(ProjectSettings.get_setting("application/config/features", PackedStringArray()))
	var readback: String = str(ProjectSettings.get_setting("application/config/name", ""))
	if readback != name:
		return _unverified(command_id, "project name changed during readback")
	var after: Dictionary = {
		"name": name,
		"main_scene": main_scene,
		"features": features,
		"hh_agent_enabled": _plugin_enabled(),
		"godot": _godot_string(),
		"source": "editor",
		"detail": str(params.get("detail", "short")),
	}
	return _ok(command_id, post, after)


func _plugin_enabled() -> bool:
	var raw: Variant = ProjectSettings.get_setting("editor_plugins/enabled", PackedStringArray())
	if raw is PackedStringArray:
		for item: String in raw:
			if item == "res://addons/hh_agent/plugin.cfg":
				return true
	if raw is Array:
		for item_v: Variant in raw:
			if str(item_v) == "res://addons/hh_agent/plugin.cfg":
				return true
	return false


func _project_doctor(command_id: String, post: String) -> Dictionary:
	var observed: String = _godot_string()
	var match_pin: bool = observed == HHAgentConstants.PINNED_GODOT
	var after: Dictionary = {
		"godot": observed,
		"pin": HHAgentConstants.PINNED_GODOT,
		"protocol": HHAgentConstants.PROTOCOL,
		"plugin": HHAgentConstants.PLUGIN_VERSION,
		"hh_agent_enabled": _plugin_enabled(),
		"source": "editor",
	}
	if not match_pin:
		return _skew(command_id, "Godot %s != pin %s" % [observed, HHAgentConstants.PINNED_GODOT])
	return _ok(command_id, post, after)


func _editor_state(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var edited: Node = EditorInterface.get_edited_scene_root()
	var edited_path: String = ""
	if edited != null:
		edited_path = edited.scene_file_path
	var open_scenes: Array = _as_str_array(EditorInterface.get_open_scenes())
	var selected: Array = _selection_paths()
	var playing_scene: String = ""
	if EditorInterface.is_playing_scene():
		playing_scene = str(EditorInterface.get_playing_scene())
	var after: Dictionary = {
		"edited_scene": edited_path,
		"open_scenes": open_scenes,
		"selection": selected,
		"playing": EditorInterface.is_playing_scene(),
		"playing_scene": playing_scene,
		"paused": HHAgentPauseGate.last_paused,
		"godot": _godot_string(),
		"detail": str(params.get("detail", "short")),
	}
	var again: Array = _selection_paths()
	if again != selected:
		return _unverified(command_id, "selection changed during readback")
	return _ok(command_id, post, after)


func _selection_paths() -> Array:
	var out: Array = []
	var selection: EditorSelection = EditorInterface.get_selection()
	if selection == null:
		return out
	var nodes_v: Variant = selection.get_selected_nodes()
	if not (nodes_v is Array):
		return out
	for node_v: Variant in nodes_v:
		if node_v is Node:
			out.append(str((node_v as Node).get_path()))
	return out


func _editor_select(command_id: String, _params: Dictionary, _post: String) -> Dictionary:
	return _unverified(command_id, "editor.select mutates EditorSelection; not a R2-WP6 read")


func _scene_read(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var scene: String = str(params.get("path", ""))
	var jail: Dictionary = _jail(command_id, scene)
	if jail.get("ok", false) != true:
		return jail
	var walk: Dictionary = _walk_scene(scene)
	if walk.get("ok", false) != true:
		return _unverified(command_id, str(walk.get("message", "scene unreadable")))
	var nodes_v: Variant = walk.get("nodes", [])
	var nodes: Array = nodes_v if nodes_v is Array else []
	var page: Dictionary = _page_dict(nodes, params)
	if int(page.get("limit", 0)) > HHAgentConstants.MAX_PAGE:
		return _unverified(command_id, "page exceeded max")
	if (page.get("items") as Array).size() > HHAgentConstants.MAX_PAGE:
		return _unverified(command_id, "adapter dumped more than one page")
	var edited: Node = EditorInterface.get_edited_scene_root()
	var snap: Dictionary = {}
	if edited != null and edited.scene_file_path == scene:
		snap = _meta.snapshot(edited, scene)
	else:
		snap = {
			"fingerprint": "",
			"history_version": "0",
			"disk_hash": _meta.disk_hash(scene),
			"dirty": false,
			"inherited": _meta.is_inherited_file(scene),
		}
	var after: Dictionary = {
		"path": scene,
		"root": str(walk.get("root", "")),
		"root_class": str(walk.get("root_class", "")),
		"source": str(walk.get("source", "")),
		"tree": page,
		"detail": str(params.get("detail", "short")),
		"fingerprint": str(snap.get("fingerprint", "")),
		"history_version": str(snap.get("history_version", "0")),
		"disk_hash": str(snap.get("disk_hash", "")),
		"dirty": snap.get("dirty", false) == true,
		"inherited": snap.get("inherited", false) == true,
	}
	return _ok(command_id, post, after)


func _scene_list_tabs(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var open_a: Array = _meta.open_scenes()
	var open_b: Array = _meta.open_scenes()
	if open_a != open_b:
		return _unverified(command_id, "open scene list changed during readback")
	var edited: Node = EditorInterface.get_edited_scene_root()
	var edited_path: String = _meta.edited_path()
	var tabs: Array = []
	for item_v: Variant in open_a:
		var path_s: String = str(item_v)
		var tab: Dictionary = {
			"path": path_s,
			"edited": path_s == edited_path,
		}
		if path_s == edited_path and edited != null:
			tab["dirty"] = _meta.is_dirty(edited)
			tab["fingerprint"] = _meta.fingerprint(edited)
			tab["history_version"] = str(_meta.history_version(edited))
		tabs.append(tab)
	var after: Dictionary = {
		"open_scenes": open_a,
		"edited_scene": edited_path,
		"tabs": tabs,
		"detail": str(params.get("detail", "short")),
		"source": "editor",
	}
	return _ok(command_id, post, after)


func _scene_deps(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var scene: String = str(params.get("path", ""))
	var jail: Dictionary = _jail(command_id, scene)
	if jail.get("ok", false) != true:
		return jail
	if not ResourceLoader.exists(scene):
		return _unverified(command_id, "scene missing")
	var deps: Array = _as_str_array(ResourceLoader.get_dependencies(scene))
	return _ok(command_id, post, {"path": scene, "dependencies": deps})


func _node_query(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var scene: String = str(params.get("scene", ""))
	var by: String = str(params.get("by", ""))
	var jail: Dictionary = _jail(command_id, scene)
	if jail.get("ok", false) != true:
		return jail
	var walk: Dictionary = _walk_scene(scene)
	if walk.get("ok", false) != true:
		return _unverified(command_id, str(walk.get("message", "scene unreadable")))
	var nodes_v: Variant = walk.get("nodes", [])
	var nodes: Array = nodes_v if nodes_v is Array else []
	var hits: Array = []
	for item_v: Variant in nodes:
		if not (item_v is Dictionary):
			continue
		var item: Dictionary = item_v
		var include: bool = false
		if by == "type":
			include = str(item.get("class_name", "")) == str(params.get("class_name", ""))
		elif by == "group":
			var want: String = str(params.get("group", ""))
			var groups_v: Variant = item.get("groups", [])
			include = groups_v is Array and want in (groups_v as Array)
		elif by == "path":
			var prefix: String = str(params.get("prefix", ""))
			include = prefix.is_empty() or str(item.get("path", "")).begins_with(prefix)
		else:
			return _unverified(command_id, "unknown query by")
		if include:
			hits.append(item)
	var page: Dictionary = _page_dict(hits, params)
	if (page.get("items") as Array).size() > HHAgentConstants.MAX_PAGE:
		return _unverified(command_id, "query page exceeded max")
	return _ok(command_id, post, {"scene": scene, "by": by, "hits": page})


func _property_get(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var scene: String = str(params.get("scene", ""))
	var node_path: String = str(params.get("node_path", ""))
	var prop: String = str(params.get("property", ""))
	var jail: Dictionary = _jail(command_id, scene)
	if jail.get("ok", false) != true:
		return jail
	var hold: Dictionary = _acquire_root(scene)
	if hold.get("ok", false) != true:
		return _unverified(command_id, str(hold.get("message", "scene unreadable")))
	var root: Node = hold.get("root") as Node
	var node: Node = root if node_path == "." or node_path == root.name else root.get_node_or_null(NodePath(node_path))
	var result: Dictionary = {}
	if node == null:
		result = _unverified(command_id, "node not found")
	elif not _has_property(node, prop):
		result = _unverified(command_id, "property %s missing on %s" % [prop, node_path])
	else:
		var value: Variant = node.get(prop)
		var again: Variant = node.get(prop)
		if str(value) != str(again):
			result = _unverified(command_id, "property changed during readback")
		else:
			result = _ok(command_id, post, {
				"scene": scene,
				"node_path": node_path,
				"property": prop,
				"value": _encode_variant(value),
			})
	if hold.get("borrowed", false) != true and root != null:
		root.free()
	return result


func _has_property(node: Object, prop: String) -> bool:
	for item_v: Variant in node.get_property_list():
		if item_v is Dictionary and str((item_v as Dictionary).get("name", "")) == prop:
			return true
	return false


func _resource_load(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var res_path: String = str(params.get("path", ""))
	var jail: Dictionary = _jail(command_id, res_path)
	if jail.get("ok", false) != true:
		return jail
	if not ResourceLoader.exists(res_path):
		return _unverified(command_id, "resource missing")
	var loaded: Resource = ResourceLoader.load(res_path)
	if loaded == null:
		return _unverified(command_id, "resource load failed")
	var uid: int = ResourceLoader.get_resource_uid(res_path)
	var import_sidecar: bool = FileAccess.file_exists("%s.import" % res_path)
	var after: Dictionary = {
		"path": res_path,
		"class_name": loaded.get_class(),
		"uid": ResourceUID.id_to_text(uid) if uid != ResourceUID.INVALID_ID else "",
		"import_sidecar": import_sidecar,
	}
	if ResourceLoader.exists(res_path):
		return _ok(command_id, post, after)
	return _unverified(command_id, "resource vanished during readback")


func _resource_uid(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var uid_text: String = str(params.get("uid", ""))
	if not uid_text.begins_with("uid://"):
		return _unverified(command_id, "uid format")
	var uid: int = ResourceUID.text_to_id(uid_text)
	if uid == ResourceUID.INVALID_ID or not ResourceUID.has_id(uid):
		return _unverified(command_id, "uid not in ResourceUID map")
	var mapped: String = ResourceUID.get_id_path(uid)
	if mapped.is_empty():
		return _unverified(command_id, "uid has no path")
	return _ok(command_id, post, {"uid": uid_text, "path": mapped})


func _signal_list(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var node: Node = _find_node(str(params.get("scene", "")), str(params.get("node_path", "")))
	if node == null:
		return _unverified(command_id, "node not found")
	var names: Array = []
	for item_v: Variant in node.get_signal_list():
		if item_v is Dictionary:
			names.append(str((item_v as Dictionary).get("name", "")))
	return _ok(command_id, post, {"signals": names})


func _signal_inspect(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var node: Node = _find_node(str(params.get("scene", "")), str(params.get("node_path", "")))
	var signal_name: String = str(params.get("signal", ""))
	if node == null:
		return _unverified(command_id, "node not found")
	var conns: Array = []
	for item_v: Variant in node.get_signal_connection_list(signal_name):
		if item_v is Dictionary:
			var item: Dictionary = item_v
			conns.append({
				"signal": signal_name,
				"target": str(item.get("callable", "")),
			})
	return _ok(command_id, post, {"signal": signal_name, "connections": conns})


func _script_read(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var res_path: String = str(params.get("path", ""))
	var jail: Dictionary = _jail(command_id, res_path)
	if jail.get("ok", false) != true:
		return jail
	if not FileAccess.file_exists(res_path):
		return _unverified(command_id, "script missing")
	var text: String = FileAccess.get_file_as_string(res_path)
	var again: String = FileAccess.get_file_as_string(res_path)
	if text != again:
		return _unverified(command_id, "script changed during readback")
	var lines: PackedStringArray = text.split("\n")
	var page: Dictionary = _page_dict(_lines_as_items(lines), params)
	return _ok(command_id, post, {
		"path": res_path,
		"line_count": lines.size(),
		"lines": page,
	})


func _lines_as_items(lines: PackedStringArray) -> Array:
	var out: Array = []
	var i: int = 0
	while i < lines.size():
		out.append({"n": i + 1, "text": lines[i]})
		i += 1
	return out


func _script_validate(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var res_path: String = str(params.get("path", ""))
	var jail: Dictionary = _jail(command_id, res_path)
	if jail.get("ok", false) != true:
		return jail
	if not ResourceLoader.exists(res_path):
		return _unverified(command_id, "script missing")
	var loaded: Resource = ResourceLoader.load(res_path)
	if loaded == null or not (loaded is Script):
		return _unverified(command_id, "script load failed")
	var script: Script = loaded as Script
	var base: String = script.get_instance_base_type()
	if base.is_empty():
		return _unverified(command_id, "script has no instance base type")
	return _ok(command_id, post, {"path": res_path, "base": base})


func _script_diagnostics(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var res_path: String = str(params.get("path", ""))
	var jail: Dictionary = _jail(command_id, res_path)
	if jail.get("ok", false) != true:
		return jail
	if not FileAccess.file_exists(res_path):
		return _unverified(command_id, "script missing")
	return _unverified(command_id, "script diagnostics API is not proven on this EditorInterface")


func _script_open_at(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var res_path: String = str(params.get("path", ""))
	var line: int = int(params.get("line", 1))
	var jail: Dictionary = _jail(command_id, res_path)
	if jail.get("ok", false) != true:
		return jail
	if not ResourceLoader.exists(res_path):
		return _unverified(command_id, "script missing")
	var loaded: Resource = ResourceLoader.load(res_path)
	if loaded == null or not (loaded is Script):
		return _unverified(command_id, "script load failed")
	EditorInterface.edit_script(loaded as Script, line, 0, true)
	var editor: ScriptEditor = EditorInterface.get_script_editor()
	if editor == null:
		return _unverified(command_id, "script editor unavailable")
	var current: Script = editor.get_current_script()
	if current == null or current.resource_path != res_path:
		return _unverified(command_id, "script editor did not show %s" % res_path)
	return _ok(command_id, post, {"path": res_path, "line": line})


func _asset_deps(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var res_path: String = str(params.get("path", ""))
	var jail: Dictionary = _jail(command_id, res_path)
	if jail.get("ok", false) != true:
		return jail
	if not ResourceLoader.exists(res_path):
		return _unverified(command_id, "asset missing")
	var deps: Array = _as_str_array(ResourceLoader.get_dependencies(res_path))
	var import_sidecar: bool = FileAccess.file_exists("%s.import" % res_path)
	return _ok(command_id, post, {
		"path": res_path,
		"dependencies": deps,
		"import_sidecar": import_sidecar,
	})


func _play_status(command_id: String, _params: Dictionary, post: String) -> Dictionary:
	var playing: bool = EditorInterface.is_playing_scene()
	var again: bool = EditorInterface.is_playing_scene()
	if playing != again:
		return _unverified(command_id, "play flag changed during readback")
	return _ok(command_id, post, {
		"playing": playing,
		"scene": EditorInterface.get_playing_scene(),
	})


func _tilemap_query(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var node: Node = _find_node(str(params.get("scene", "")), str(params.get("node_path", "")))
	if node == null or not (node is TileMapLayer):
		return _unverified(command_id, "TileMapLayer not found")
	var layer: TileMapLayer = node as TileMapLayer
	var x0: int = int(params.get("x", 0))
	var y0: int = int(params.get("y", 0))
	var w: int = int(params.get("w", 1))
	var h: int = int(params.get("h", 1))
	var cells: Array = []
	var y: int = y0
	while y < y0 + h:
		var x: int = x0
		while x < x0 + w:
			var cell: Vector2i = Vector2i(x, y)
			cells.append({
				"x": x,
				"y": y,
				"source_id": layer.get_cell_source_id(cell),
				"atlas": {"x": layer.get_cell_atlas_coords(cell).x, "y": layer.get_cell_atlas_coords(cell).y},
			})
			x += 1
		y += 1
	if cells.size() > HHAgentConstants.MAX_PAGE:
		return _unverified(command_id, "tilemap region exceeds one page")
	return _ok(command_id, post, {"cells": cells})


func _ui_access(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var node: Node = _find_node(str(params.get("scene", "")), str(params.get("node_path", "")))
	if node == null or not (node is Control):
		return _unverified(command_id, "Control not found")
	var control: Control = node as Control
	return _ok(command_id, post, {
		"tooltip": control.tooltip_text,
		"focus_mode": control.focus_mode,
		"visible": control.visible,
	})


func _acquire_root(scene: String) -> Dictionary:
	var edited: Node = EditorInterface.get_edited_scene_root()
	if edited != null and edited.scene_file_path == scene:
		return {"ok": true, "root": edited, "borrowed": true}
	if ResourceLoader.exists(scene):
		var packed_v: Resource = ResourceLoader.load(scene)
		if packed_v is PackedScene:
			return {"ok": true, "root": (packed_v as PackedScene).instantiate(), "borrowed": false}
	return {"ok": false, "message": "cannot load %s" % scene}


func _walk_scene(scene: String) -> Dictionary:
	var hold: Dictionary = _acquire_root(scene)
	if hold.get("ok", false) != true:
		return hold
	var root: Node = hold.get("root") as Node
	var nodes: Array = []
	_collect(root, ".", nodes, root)
	var summary: Dictionary = {
		"ok": true,
		"root": root.name,
		"root_class": root.get_class(),
		"source": "edited" if hold.get("borrowed", false) == true else "instantiate",
		"nodes": nodes,
	}
	if hold.get("borrowed", false) != true:
		root.free()
	return summary


func _collect(node: Node, path_s: String, out: Array, root: Node) -> void:
	var groups: Array = []
	for group_s: String in _as_str_array(node.get_groups()):
		if group_s.begins_with("_"):
			continue
		groups.append(group_s)
	groups.sort()
	var uid: String = ""
	if node.has_meta(HHAgentConstants.NODE_UID_META):
		uid = str(node.get_meta(HHAgentConstants.NODE_UID_META))
	elif node.has_meta(HHAgentConstants.NODE_UID_META_HIDDEN):
		uid = str(node.get_meta(HHAgentConstants.NODE_UID_META_HIDDEN))
	var owner_node: Node = node.owner
	var owner_path: String = ""
	if owner_node != null:
		owner_path = "." if owner_node == root else str(root.get_path_to(owner_node))
	var packed_internal: bool = false
	if node != root:
		var walk: Node = node.get_parent()
		var inst: Node = null
		while walk != null and walk != root:
			if not walk.scene_file_path.is_empty() and walk.scene_file_path != root.scene_file_path:
				inst = walk
				break
			walk = walk.get_parent()
		if inst != null:
			packed_internal = node.owner == inst or node.owner == null
	out.append({
		"name": node.name,
		"path": path_s,
		"class_name": node.get_class(),
		"child_count": node.get_child_count(),
		"groups": groups,
		"uid": uid,
		"owner": owner_path,
		"packed_internal": packed_internal,
	})
	var i: int = 0
	while i < node.get_child_count():
		var child: Node = node.get_child(i)
		if str(child.name).begins_with("__hh_"):
			i += 1
			continue
		var child_path: String = child.name if path_s == "." else "%s/%s" % [path_s, child.name]
		_collect(child, child_path, out, root)
		i += 1


func _find_node(scene: String, node_path: String) -> Node:
	var edited: Node = EditorInterface.get_edited_scene_root()
	if edited != null and (scene.is_empty() or edited.scene_file_path == scene):
		if node_path == "." or node_path == edited.name:
			return edited
		var found: Node = edited.get_node_or_null(NodePath(node_path))
		if found != null:
			return found
	if scene.is_empty() or not ResourceLoader.exists(scene):
		return null
	# Disk instances are only used for read snapshots; caller must not persist them.
	return null


func _encode_variant(value: Variant) -> Dictionary:
	var t: int = typeof(value)
	if t == TYPE_BOOL:
		return {"schema": "hh-godot-variant/1", "type": "bool", "value": value}
	if t == TYPE_INT:
		return {"schema": "hh-godot-variant/1", "type": "int", "value": value}
	if t == TYPE_FLOAT:
		return {"schema": "hh-godot-variant/1", "type": "float", "value": value}
	if t == TYPE_STRING:
		return {"schema": "hh-godot-variant/1", "type": "string", "value": value}
	if t == TYPE_VECTOR2:
		var v: Vector2 = value
		return {"schema": "hh-godot-variant/1", "type": "Vector2", "value": {"x": v.x, "y": v.y}}
	if t == TYPE_COLOR:
		var c: Color = value
		return {"schema": "hh-godot-variant/1", "type": "Color", "value": {"r": c.r, "g": c.g, "b": c.b, "a": c.a}}
	if t == TYPE_NODE_PATH:
		return {"schema": "hh-godot-variant/1", "type": "NodePath", "value": str(value)}
	if t == TYPE_OBJECT and value is Resource:
		var res: Resource = value as Resource
		return {"schema": "hh-godot-variant/1", "type": "Resource", "value": res.resource_path}
	return {"schema": "hh-godot-variant/1", "type": "string", "value": str(value)}

class_name HHAgentPresenter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")
const _IdentityScript: GDScript = preload("res://addons/hh_agent/core/hh_identity.gd")
const _StoreScript: GDScript = preload("res://addons/hh_agent/core/hh_activity_store.gd")

## Presentation-only EditorInterface adapter. No UndoRedo. No disk write.

var _errors: HHAgentErrors = HHAgentErrors.new()
var _identity: HHAgentIdentity = HHAgentIdentity.new()


func handle(
	command_id: String,
	method: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
	envelope: Dictionary,
) -> Dictionary:
	var def: Dictionary = actions.lookup(method, action)
	var post: String = str(def.get("postcondition", "selection_paths_match"))
	if method != "godot.editor":
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not an editor presentation verb", "")
	if action == "select" or action == "focus":
		return _select(command_id, params, envelope, post, action == "focus")
	if action == "main_screen":
		return _main_screen_set(command_id, params, envelope, post)
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "editor.%s is not a proven presentation verb" % action, "")


func after_success(
	result: Dictionary,
	method: String,
	action: String,
	params: Dictionary,
	envelope: Dictionary,
) -> Dictionary:
	if result.get("ok", false) != true:
		return result
	var hint: Dictionary = hint_from_mutation(method, action, params, result)
	if hint.is_empty():
		return result
	var applied: Dictionary = apply_presentation(hint, envelope, false)
	var after_v: Variant = result.get("after", {})
	var after: Dictionary = after_v if after_v is Dictionary else {}
	_merge_focus(after, applied)
	result["after"] = after
	return result


func hint_from_mutation(method: String, action: String, params: Dictionary, result: Dictionary) -> Dictionary:
	return _hint_from_mutation(method, action, params, result)


func live_snapshot() -> Dictionary:
	return _redact(_read_live())


func apply_presentation(params: Dictionary, envelope: Dictionary, fail_if_missing: bool) -> Dictionary:
	var failed: bool = false
	var prev_external: bool = _uses_external_editor()
	if params.get("hide_inspector", false) == true:
		_set_inspector_visible(false)
	if params.get("use_external_editor", false) == true:
		_set_external_editor(true)
	var cheap: bool = _cheap(envelope)
	var scene: String = str(params.get("scene", ""))
	var root: Node = null
	if not scene.is_empty():
		var opened: Dictionary = _ensure_scene(scene)
		if opened.get("ok", false) == true:
			root = opened.get("root") as Node
		elif fail_if_missing:
			return {"ok": false, "code": HHAgentErrors.E_UNVERIFIED, "message": str(opened.get("message", "scene missing"))}
		else:
			failed = true
	var node: Node = null
	if root != null:
		node = _resolve_node(root, params)
		if node == null and fail_if_missing and str(params.get("script_path", "")).is_empty() and str(params.get("filesystem_path", "")).is_empty() and str(params.get("resource_path", "")).is_empty():
			return {"ok": false, "code": HHAgentErrors.E_UNVERIFIED, "message": "node not found"}
		if node == null and not str(params.get("node_path", "")).is_empty() and str(params.get("script_path", "")).is_empty():
			failed = true
	if node != null:
		_present_node(node, str(params.get("property", "")), cheap)
	var resource_path: String = str(params.get("resource_path", ""))
	if not resource_path.is_empty():
		if not _present_resource(resource_path):
			failed = true
	var script_path: String = str(params.get("script_path", ""))
	var script_line: int = int(params.get("script_line", 1))
	var script_column: int = int(params.get("script_column", 0))
	if not script_path.is_empty():
		if not _present_script(script_path, script_line, script_column, cheap):
			failed = true
	var filesystem_path: String = str(params.get("filesystem_path", ""))
	if not filesystem_path.is_empty():
		_present_filesystem(filesystem_path)
	var screen: String = str(params.get("screen", params.get("main_screen", "")))
	if not screen.is_empty() and not cheap:
		EditorInterface.set_main_screen_editor(screen)
	elif node != null and not cheap:
		EditorInterface.set_main_screen_editor("2D")
	elif not script_path.is_empty() and not cheap:
		EditorInterface.set_main_screen_editor("Script")
	if params.get("use_external_editor", false) == true:
		_set_external_editor(prev_external)
	var snap: Dictionary = _read_live()
	if failed:
		snap["presentation_failed"] = true
	if node != null:
		_prove_node(snap, node, root)
	if not script_path.is_empty():
		_prove_script(snap, script_path, script_line)
	if not filesystem_path.is_empty():
		_prove_filesystem(snap, filesystem_path)
	if params.get("hide_inspector", false) == true and not _inspector_proved_visible():
		snap["presentation_failed"] = true
	return _redact(snap)


func _select(
	command_id: String,
	params: Dictionary,
	envelope: Dictionary,
	post: String,
	focus_inspector: bool,
) -> Dictionary:
	var applied: Dictionary = apply_presentation(params, envelope, true)
	if applied.get("ok", true) == false:
		return _errors.fail(
			command_id,
			str(applied.get("code", HHAgentErrors.E_UNVERIFIED)),
			str(applied.get("message", "presentation target missing")),
			"params.node_path",
		)
	# select and focus both present Inspector. hide_inspector stays a probe.
	# Do not change the read snapshot shape (applied is already _read_live).
	if params.get("hide_inspector", false) != true:
		_set_inspector_visible(true)
		if focus_inspector:
			_set_inspector_visible(true)
	return _errors.ok_read(command_id, _checks(post), applied)


func _main_screen_set(command_id: String, params: Dictionary, envelope: Dictionary, post: String) -> Dictionary:
	var screen: String = str(params.get("screen", ""))
	if screen.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "screen required", "params.screen")
	if not _cheap(envelope):
		EditorInterface.set_main_screen_editor(screen)
	var snap: Dictionary = _read_live()
	if str(snap.get("main_screen", "")) != screen:
		snap["presentation_failed"] = true
	return _errors.ok_read(command_id, _checks(post), _redact(snap))


func _hint_from_mutation(method: String, action: String, params: Dictionary, result: Dictionary) -> Dictionary:
	var after_v: Variant = result.get("after", {})
	var after: Dictionary = after_v if after_v is Dictionary else {}
	if method == "godot.node" and action == "add":
		return {
			"scene": str(params.get("scene", "")),
			"node_path": str(after.get("path", params.get("name", ""))),
			"uid": str(after.get("uid", "")),
			"screen": "2D",
		}
	if method == "godot.scene" and action == "create":
		return {
			"scene": str(params.get("path", "")),
			"node_path": ".",
			"screen": "2D",
		}
	if method == "godot.property" and action == "set":
		return {
			"scene": str(params.get("scene", "")),
			"node_path": str(params.get("node_path", "")),
			"property": str(params.get("property", "")),
			"screen": "2D",
		}
	if method == "godot.resource" and action == "assign":
		return {
			"scene": str(params.get("scene", "")),
			"node_path": str(params.get("node_path", "")),
			"property": str(params.get("property", "")),
			"screen": "2D",
		}
	if method == "godot.script" and action == "attach":
		return {
			"scene": str(params.get("scene", "")),
			"node_path": str(params.get("node_path", "")),
			"screen": "2D",
		}
	if method == "godot.script" and action == "write":
		var path_s: String = str(after.get("path", params.get("path", "")))
		return {
			"script_path": path_s,
			"script_line": 1,
			"script_column": 0,
			"filesystem_path": path_s,
		}
	return {}


func _merge_focus(after: Dictionary, focus: Dictionary) -> void:
	for key: String in [
		"selected_paths",
		"inspector_class",
		"inspector_path",
		"script_path",
		"script_line",
		"filesystem_path",
		"main_screen",
		"presentation_failed",
	]:
		after[key] = focus.get(key, after.get(key, _default_focus_value(key)))


func _default_focus_value(key: String) -> Variant:
	if key == "selected_paths":
		return []
	if key == "script_line":
		return 0
	if key == "presentation_failed":
		return false
	return ""


func _read_live() -> Dictionary:
	var selected: Array = _selection_paths()
	var inspector: Dictionary = _inspector_live()
	var script: Dictionary = _script_live()
	var filesystem_path: String = _filesystem_live()
	var failed: bool = false
	if not _inspector_proved_visible() and not str(inspector.get("class_name", "")).is_empty():
		# Object is known; visibility is unproven (hidden dock / headless).
		failed = not _inspector_proved_visible()
	return {
		"selected_paths": selected,
		"inspector_class": str(inspector.get("class_name", "")),
		"inspector_path": str(inspector.get("path", "")),
		"script_path": str(script.get("path", "")),
		"script_line": int(script.get("line", 0)),
		"filesystem_path": filesystem_path,
		"main_screen": _main_screen_live(),
		"presentation_failed": failed or script.get("failed", false) == true,
	}


func _selection_paths() -> Array:
	var out: Array = []
	var selection: EditorSelection = EditorInterface.get_selection()
	if selection == null:
		return out
	var nodes_v: Variant = selection.get_selected_nodes()
	if not (nodes_v is Array):
		return out
	var edited: Node = EditorInterface.get_edited_scene_root()
	for node_v: Variant in nodes_v:
		if not (node_v is Node):
			continue
		var node: Node = node_v as Node
		if edited != null and (node == edited or edited.is_ancestor_of(node)):
			out.append(_identity.tree_path(node, edited))
		else:
			out.append(str(node.name))
	return out


func _inspector_live() -> Dictionary:
	var inspector: EditorInspector = EditorInterface.get_inspector()
	if inspector == null:
		return {}
	var edited_obj: Object = inspector.get_edited_object()
	if edited_obj == null:
		return {}
	var class_s: String = edited_obj.get_class()
	var path_s: String = ""
	if edited_obj is Node:
		var node: Node = edited_obj as Node
		var root: Node = EditorInterface.get_edited_scene_root()
		if root != null and (node == root or root.is_ancestor_of(node)):
			path_s = _identity.tree_path(node, root)
		else:
			path_s = str(node.name)
	elif edited_obj is Resource:
		path_s = str((edited_obj as Resource).resource_path)
	return {"class_name": class_s, "path": path_s}


func _script_live() -> Dictionary:
	if _uses_external_editor():
		return {"path": "", "line": 0, "failed": true}
	var editor: ScriptEditor = EditorInterface.get_script_editor()
	if editor == null:
		return {"path": "", "line": 0, "failed": true}
	var current: Script = editor.get_current_script()
	var path_s: String = ""
	if current != null:
		path_s = str(current.resource_path)
	var line: int = 0
	if editor.has_method("get_current_editor"):
		var base_v: Variant = editor.call("get_current_editor")
		if base_v is Object:
			var base: Object = base_v as Object
			if base.has_method("get_base_editor"):
				var code_v: Variant = base.call("get_base_editor")
				if code_v is Object:
					var code: Object = code_v as Object
					if code.has_method("get_caret_line"):
						line = int(code.call("get_caret_line")) + 1
	return {"path": path_s, "line": line, "failed": false}


func _filesystem_live() -> String:
	if EditorInterface.has_method("get_selected_paths"):
		var selected_v: Variant = EditorInterface.call("get_selected_paths")
		if selected_v is PackedStringArray:
			var packed: PackedStringArray = selected_v
			if packed.size() > 0:
				return str(packed[0])
		if selected_v is Array:
			var arr: Array = selected_v
			if arr.size() > 0:
				return str(arr[0])
	if EditorInterface.has_method("get_current_path"):
		return str(EditorInterface.call("get_current_path"))
	return ""


func _main_screen_live() -> String:
	var main: VBoxContainer = EditorInterface.get_editor_main_screen()
	if main == null:
		return ""
	var i: int = 0
	while i < main.get_child_count():
		var child: Node = main.get_child(i)
		if child.visible:
			var cls: String = child.get_class()
			var name_s: String = str(child.name)
			if cls == "CanvasItemEditor" or name_s.contains("2D"):
				return "2D"
			if cls == "Node3DEditor" or name_s.contains("3D"):
				return "3D"
			if child is ScriptEditor or name_s.contains("Script"):
				return "Script"
			if name_s.contains("Game"):
				return "Game"
			if name_s.contains("Asset"):
				return "AssetLib"
			return name_s
		i += 1
	return ""


func _present_node(node: Node, property: String, cheap: bool) -> void:
	var selection: EditorSelection = EditorInterface.get_selection()
	if selection != null:
		selection.clear()
		selection.add_node(node)
	EditorInterface.edit_node(node)
	if property.is_empty():
		EditorInterface.inspect_object(node)
	else:
		EditorInterface.inspect_object(node, property, false)
	if not cheap:
		EditorInterface.set_main_screen_editor("2D")


func _present_resource(res_path: String) -> bool:
	if not _jail_ok(res_path):
		return false
	if not ResourceLoader.exists(res_path):
		return false
	var loaded: Resource = ResourceLoader.load(res_path)
	if loaded == null:
		return false
	EditorInterface.edit_resource(loaded)
	EditorInterface.inspect_object(loaded)
	return true


func _present_script(res_path: String, line: int, column: int, cheap: bool) -> bool:
	if not _jail_ok(res_path):
		return false
	if _uses_external_editor():
		return false
	if not FileAccess.file_exists(res_path):
		return false
	var loaded: Resource = ResourceLoader.load(res_path, "", ResourceLoader.CACHE_MODE_REUSE)
	if loaded == null or not (loaded is Script):
		var probe: GDScript = GDScript.new()
		probe.source_code = FileAccess.get_file_as_bytes(res_path).get_string_from_utf8()
		probe.resource_path = res_path
		if probe.reload() != OK:
			return false
		loaded = probe
	var grab: bool = not cheap
	EditorInterface.edit_script(loaded as Script, line, column, grab)
	if not cheap:
		EditorInterface.set_main_screen_editor("Script")
	return true


func _present_filesystem(res_path: String) -> void:
	if not _jail_ok(res_path):
		return
	EditorInterface.select_file(res_path)
	var dock: FileSystemDock = EditorInterface.get_file_system_dock()
	if dock != null and dock.has_method("navigate_to_path"):
		dock.call("navigate_to_path", res_path)


func _prove_node(snap: Dictionary, node: Node, root: Node) -> void:
	var want: String = _identity.tree_path(node, root) if root != null else str(node.name)
	var selected_v: Variant = snap.get("selected_paths", [])
	var selected: Array = selected_v if selected_v is Array else []
	var found: bool = false
	for item_v: Variant in selected:
		var item: String = str(item_v)
		if item == want or item.ends_with("/%s" % node.name) or item == str(node.name):
			found = true
			break
	if not found:
		snap["presentation_failed"] = true
	var inspector: Object = null
	var insp: EditorInspector = EditorInterface.get_inspector()
	if insp != null:
		inspector = insp.get_edited_object()
	if inspector != node:
		snap["presentation_failed"] = true
	if not _inspector_proved_visible():
		snap["presentation_failed"] = true


func _prove_script(snap: Dictionary, want_path: String, want_line: int) -> void:
	if _uses_external_editor():
		snap["presentation_failed"] = true
		return
	if str(snap.get("script_path", "")) != want_path:
		snap["presentation_failed"] = true
	if want_line > 0 and int(snap.get("script_line", 0)) != want_line:
		# Caret may land on a nearby line in headless; still require a live line.
		if int(snap.get("script_line", 0)) < 1:
			snap["presentation_failed"] = true


func _prove_filesystem(snap: Dictionary, want_path: String) -> void:
	var got: String = str(snap.get("filesystem_path", "")).replace("\\", "/")
	var want: String = want_path.replace("\\", "/")
	if got != want and not got.ends_with(want.get_file()):
		if EditorInterface.has_method("get_selected_paths"):
			var selected_v: Variant = EditorInterface.call("get_selected_paths")
			var matched: bool = false
			if selected_v is PackedStringArray:
				for item: String in selected_v:
					if str(item).replace("\\", "/") == want:
						matched = true
						snap["filesystem_path"] = str(item)
						break
			if selected_v is Array:
				for item_v: Variant in selected_v:
					if str(item_v).replace("\\", "/") == want:
						matched = true
						snap["filesystem_path"] = str(item_v)
						break
			if not matched:
				snap["presentation_failed"] = true
		else:
			snap["presentation_failed"] = true


func _ensure_scene(scene: String) -> Dictionary:
	if not _jail_ok(scene):
		return {"ok": false, "message": "path jail"}
	var edited: Node = EditorInterface.get_edited_scene_root()
	if edited != null and edited.scene_file_path == scene:
		return {"ok": true, "root": edited}
	if not FileAccess.file_exists(scene) and not ResourceLoader.exists(scene):
		return {"ok": false, "message": "scene missing"}
	EditorInterface.open_scene_from_path(scene)
	edited = EditorInterface.get_edited_scene_root()
	if edited == null or edited.scene_file_path != scene:
		return {"ok": false, "message": "EditorInterface did not edit %s" % scene}
	return {"ok": true, "root": edited}


func _resolve_node(root: Node, params: Dictionary) -> Node:
	var uid: String = str(params.get("uid", ""))
	if not uid.is_empty():
		var by_uid: Node = _find_uid(root, uid)
		if by_uid != null:
			return by_uid
	var node_path: String = str(params.get("node_path", ""))
	if node_path.is_empty():
		return null
	if node_path == "." or node_path == root.name:
		return root
	return root.get_node_or_null(NodePath(node_path))


func _find_uid(node: Node, uid: String) -> Node:
	if node == null or uid.is_empty():
		return null
	if _identity.read_uid(node) == uid:
		return node
	var i: int = 0
	while i < node.get_child_count():
		var child: Node = node.get_child(i)
		if str(child.name).begins_with("__hh_"):
			i += 1
			continue
		var found: Node = _find_uid(child, uid)
		if found != null:
			return found
		i += 1
	return null


func _set_inspector_visible(want: bool) -> void:
	if EditorInterface.has_method("set_inspector_visible"):
		EditorInterface.call("set_inspector_visible", want)
		return
	var insp: EditorInspector = EditorInterface.get_inspector()
	if insp == null:
		return
	var cur: Node = insp
	var hidden: bool = false
	while cur != null:
		var name_l: String = str(cur.name).to_lower()
		if cur is Control and (name_l.contains("inspector") or name_l.contains("dock")):
			(cur as Control).visible = want
			if name_l.contains("inspector") and cur != insp:
				hidden = true
				break
		cur = cur.get_parent()
	if not hidden and insp is Control:
		(insp as Control).visible = want


func _inspector_proved_visible() -> bool:
	if EditorInterface.has_method("is_inspector_visible"):
		return EditorInterface.call("is_inspector_visible") == true
	var insp: EditorInspector = EditorInterface.get_inspector()
	if insp == null:
		return false
	return insp.is_visible_in_tree()


func _uses_external_editor() -> bool:
	var settings: EditorSettings = EditorInterface.get_editor_settings()
	if settings == null:
		return false
	if settings.has_setting("text_editor/external/use_external_editor"):
		return settings.get_setting("text_editor/external/use_external_editor") == true
	return false


func _set_external_editor(want: bool) -> void:
	var settings: EditorSettings = EditorInterface.get_editor_settings()
	if settings == null:
		return
	if settings.has_setting("text_editor/external/use_external_editor"):
		settings.set_setting("text_editor/external/use_external_editor", want)


func _cheap(envelope: Dictionary) -> bool:
	if _mode(envelope) == HHAgentConstants.MODE_FAST:
		return true
	return DisplayServer.get_name() == "headless"


func _mode(envelope: Dictionary) -> String:
	var pres_v: Variant = envelope.get("presentation", {})
	if pres_v is Dictionary:
		var mode_s: String = str((pres_v as Dictionary).get("mode", ""))
		if mode_s == HHAgentConstants.MODE_FAST:
			return HHAgentConstants.MODE_FAST
		if mode_s == HHAgentConstants.MODE_WATCH:
			return HHAgentConstants.MODE_WATCH
	var store: HHAgentActivityStore = HHAgentActivityStore.current()
	if store != null:
		return store.mode()
	return HHAgentConstants.MODE_WATCH


func _jail_ok(res_path: String) -> bool:
	if not res_path.begins_with("res://"):
		return false
	if res_path.contains(".."):
		return false
	var abs_path: String = ProjectSettings.globalize_path(res_path)
	var root: String = ProjectSettings.globalize_path("res://")
	return abs_path.begins_with(root)


func _redact(after: Dictionary) -> Dictionary:
	var store: HHAgentActivityStore = HHAgentActivityStore.current()
	if store == null:
		return after
	var text: String = JSON.stringify(after)
	var cleaned: String = store.redact_text(text)
	if cleaned == text:
		return after
	var parsed: Variant = JSON.parse_string(cleaned)
	if parsed is Dictionary:
		return parsed
	return after


func _checks(post: String) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	out.append(post)
	return out

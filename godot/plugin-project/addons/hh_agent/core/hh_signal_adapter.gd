class_name HHAgentSignalAdapter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")
const _MetaScript: GDScript = preload("res://addons/hh_agent/core/hh_scene_meta.gd")

## Signal connect/disconnect via EditorUndoRedoManager. No raw connect outside UndoRedo.

var _errors: HHAgentErrors = HHAgentErrors.new()
var _meta: HHAgentSceneMeta = HHAgentSceneMeta.new()


func handles(action: String) -> bool:
	return action == "connect" or action == "disconnect"


func handle(
	command_id: String,
	method: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
	precondition: Dictionary,
) -> Dictionary:
	if method != "godot.signal":
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not a signal verb", "")
	var def: Dictionary = actions.lookup(method, action)
	var post: String = str(def.get("postcondition", ""))
	if post.is_empty():
		post = "connection_present" if action == "connect" else "connection_absent"
	if action == "connect":
		return _connect(command_id, params, precondition, post)
	if action == "disconnect":
		return _disconnect(command_id, params, precondition, post)
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "signal.%s is not a proven verb" % action, "")


func _connect(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var ready: Dictionary = _pair(command_id, edited, params)
	if ready.get("ok", false) != true:
		return ready
	var source: Node = ready.get("source") as Node
	var target: Node = ready.get("target") as Node
	var signal_name: String = str(ready.get("signal", ""))
	var method_name: String = str(ready.get("method", ""))
	var cb: Callable = Callable(target, method_name)
	if source.is_connected(StringName(signal_name), cb):
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"duplicate signal connection",
			"params.signal",
		)
	var action_name: String = "%ssignal.connect %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, signal_name]
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	mgr.add_do_method(source, "connect", StringName(signal_name), cb, CONNECT_PERSIST)
	mgr.add_undo_method(source, "disconnect", StringName(signal_name), cb)
	mgr.commit_action()
	if not source.is_connected(StringName(signal_name), cb):
		return _unverified(command_id, "connect readback missing")
	_meta.mark_dirty(str(params.get("scene", "")))
	return _ok_conn(command_id, post, action_name, edited, params, true)


func _disconnect(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var ready: Dictionary = _pair(command_id, edited, params)
	if ready.get("ok", false) != true:
		return ready
	var source: Node = ready.get("source") as Node
	var target: Node = ready.get("target") as Node
	var signal_name: String = str(ready.get("signal", ""))
	var method_name: String = str(ready.get("method", ""))
	var cb: Callable = Callable(target, method_name)
	if not source.is_connected(StringName(signal_name), cb):
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"connection does not exist",
			"params.signal",
		)
	var action_name: String = "%ssignal.disconnect %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, signal_name]
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	mgr.add_do_method(source, "disconnect", StringName(signal_name), cb)
	mgr.add_undo_method(source, "connect", StringName(signal_name), cb, CONNECT_PERSIST)
	mgr.commit_action()
	if source.is_connected(StringName(signal_name), cb):
		return _unverified(command_id, "disconnect readback still connected")
	_meta.mark_dirty(str(params.get("scene", "")))
	return _ok_conn(command_id, post, action_name, edited, params, false)


func _pair(command_id: String, edited: Node, params: Dictionary) -> Dictionary:
	var source: Node = _resolve(edited, str(params.get("source", "")))
	var target: Node = _resolve(edited, str(params.get("target", "")))
	if source == null:
		return _unverified(command_id, "source node not found")
	if target == null:
		return _unverified(command_id, "target node not found")
	var signal_name: String = str(params.get("signal", ""))
	var method_name: String = str(params.get("method", ""))
	if signal_name.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "signal is required", "params.signal")
	if method_name.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "method is required", "params.method")
	if not source.has_signal(signal_name):
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "signal %s does not exist on source" % signal_name, "params.signal")
	if not _has_target_method(target, method_name):
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"method %s does not exist on target" % method_name,
			"params.method",
		)
	return {"ok": true, "source": source, "target": target, "signal": signal_name, "method": method_name}


func _has_target_method(target: Object, method_name: String) -> bool:
	if target.has_method(method_name):
		return true
	var script_v: Variant = target.get_script()
	if script_v is Script:
		var script: Script = script_v
		if script.has_method(method_name):
			return true
	return false


func _ok_conn(
	command_id: String,
	post: String,
	action_name: String,
	edited: Node,
	params: Dictionary,
	connected: bool,
) -> Dictionary:
	var after: Dictionary = _meta.snapshot(edited, str(params.get("scene", "")))
	after["scene"] = str(params.get("scene", ""))
	after["source"] = str(params.get("source", ""))
	after["signal"] = str(params.get("signal", ""))
	after["target"] = str(params.get("target", ""))
	after["method"] = str(params.get("method", ""))
	after["connected"] = connected
	after["origin"] = "editor"
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _hold_scene(command_id: String, res_path: String, precondition: Dictionary) -> Dictionary:
	var gated: Dictionary = _meta.jail(command_id, res_path)
	if gated.get("ok", false) != true:
		return gated
	if not _meta.is_scene_path(res_path):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "path must be .tscn or .scn", res_path)
	if not FileAccess.file_exists(res_path):
		return _unverified(command_id, "scene missing")
	var edited: Node = EditorInterface.get_edited_scene_root()
	if edited == null or edited.scene_file_path != res_path:
		EditorInterface.open_scene_from_path(res_path)
		edited = EditorInterface.get_edited_scene_root()
	if edited == null or edited.scene_file_path != res_path:
		return _unverified(command_id, "edited_scene is not %s" % res_path)
	if not precondition.is_empty():
		var want_fp: String = str(precondition.get("fingerprint", ""))
		var want_hv: String = str(precondition.get("history_version", ""))
		var want_hash: String = str(precondition.get("scene_hash", ""))
		if not want_fp.is_empty() and want_fp != _meta.fingerprint(edited):
			return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "editor fingerprint changed; resync", "precondition.fingerprint")
		if not want_hv.is_empty() and want_hv != str(_meta.history_version(edited)):
			return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "editor history version changed; resync", "precondition.history_version")
		if not want_hash.is_empty() and want_hash != _meta.disk_hash(res_path):
			return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "disk hash changed (human/external edit); resync", "precondition.scene_hash")
	return {"ok": true, "root": edited}


func _resolve(root: Node, path_s: String) -> Node:
	if root == null:
		return null
	if path_s.is_empty() or path_s == "." or path_s == root.name:
		return root
	var found: Node = root.get_node_or_null(NodePath(path_s))
	if found != null:
		return found
	if path_s.begins_with(root.name + "/"):
		return root.get_node_or_null(NodePath(path_s.substr(root.name.length() + 1)))
	return null


func _mgr() -> EditorUndoRedoManager:
	return EditorInterface.get_editor_undo_redo()


func _unverified(command_id: String, message: String) -> Dictionary:
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, message, "")


func _checks(post: String) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	out.append(post)
	return out

class_name HHAgentTransactionAdapter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")
const _MetaScript: GDScript = preload("res://addons/hh_agent/core/hh_scene_meta.gd")
const _SceneScript: GDScript = preload("res://addons/hh_agent/core/hh_scene_adapter.gd")
const _NodeScript: GDScript = preload("res://addons/hh_agent/core/hh_node_adapter.gd")
const _PropertyScript: GDScript = preload("res://addons/hh_agent/core/hh_property_adapter.gd")
const _ScriptScript: GDScript = preload("res://addons/hh_agent/core/hh_script_adapter.gd")

## One UndoRedo for node/property steps; script.write is file compensation (not UndoRedo).
## Does not claim OS-global atomicity.

var _errors: HHAgentErrors = HHAgentErrors.new()
var _meta: HHAgentSceneMeta = HHAgentSceneMeta.new()
var _scenes: HHAgentSceneAdapter = HHAgentSceneAdapter.new()
var _nodes: HHAgentNodeAdapter = HHAgentNodeAdapter.new()
var _props: HHAgentPropertyAdapter = HHAgentPropertyAdapter.new()
var _scripts: HHAgentScriptAdapter = HHAgentScriptAdapter.new()


func handle(
	command_id: String,
	method: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
	precondition: Dictionary,
) -> Dictionary:
	if method != "godot.job" or action != "transaction":
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not a job.transaction", "")
	var raw_steps: Variant = params.get("steps", [])
	if typeof(raw_steps) != TYPE_ARRAY:
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "steps must be an array", "params.steps")
	var steps: Array = raw_steps
	if steps.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_OUT_OF_BOUNDS, "steps must not be empty", "params.steps")
	var want_save: bool = params.get("save", true) == true
	var graph: Array = []
	var reports: Array = []
	var scene_path: String = ""
	var script_compensated: bool = false
	var save_count: int = 0
	var undoredo_count: int = 0
	var applied_any: bool = false
	var i: int = 0
	while i < steps.size():
		if typeof(steps[i]) != TYPE_DICTIONARY:
			return _fail_applied(command_id, HHAgentErrors.E_INVALID_TYPE, "step must be an object", "params.steps/%d" % i, applied_any)
		var step: Dictionary = steps[i]
		var step_action: String = str(step.get("action", ""))
		var step_params_v: Variant = step.get("params", {})
		if typeof(step_params_v) != TYPE_DICTIONARY:
			return _fail_applied(command_id, HHAgentErrors.E_INVALID_TYPE, "step params must be an object", "params.steps/%d/params" % i, applied_any)
		var step_params: Dictionary = step_params_v
		if step_action == "node.add" or step_action == "property.set" or step_action == "property.batch":
			graph.append(step)
		else:
			var flushed: Dictionary = _flush_graph(command_id, actions, scene_path, graph, reports)
			if flushed.get("ok", false) != true:
				return flushed
			if str(flushed.get("scene", "")) != "":
				scene_path = str(flushed.get("scene", ""))
			if flushed.get("committed", false) == true:
				undoredo_count += 1
				applied_any = true
			graph.clear()
			var immediate: Dictionary = _apply_immediate(command_id, step_action, step_params, actions, precondition)
			if immediate.get("ok", false) != true:
				return _with_changed(immediate, applied_any)
			applied_any = true
			reports.append(_step_row(step_action, immediate))
			if step_action == "scene.create" or step_action == "scene.open" or step_action == "scene.save":
				scene_path = str(step_params.get("path", scene_path))
			if step_action == "scene.save" or step_action == "scene.create":
				save_count += 1
			if step_action == "script.write":
				script_compensated = true
		i += 1
	var last_flush: Dictionary = _flush_graph(command_id, actions, scene_path, graph, reports)
	if last_flush.get("ok", false) != true:
		return last_flush
	if str(last_flush.get("scene", "")) != "":
		scene_path = str(last_flush.get("scene", ""))
	if last_flush.get("committed", false) == true:
		undoredo_count += 1
		applied_any = true
	if want_save and scene_path != "" and save_count < 1:
		var saved: Dictionary = _scenes.handle(command_id, "godot.scene", "save", {"path": scene_path}, actions, {})
		if saved.get("ok", false) != true:
			return _with_changed(saved, applied_any)
		save_count += 1
		reports.append(_step_row("scene.save", saved))
	if reports.is_empty():
		return _unverified(command_id, "transaction produced no steps")
	var edited: Node = EditorInterface.get_edited_scene_root()
	var after: Dictionary = {}
	if edited != null and scene_path != "" and edited.scene_file_path == scene_path:
		after = _meta.snapshot(edited, scene_path)
	elif scene_path != "":
		after["path"] = scene_path
		after["disk_hash"] = _meta.disk_hash(scene_path)
	after["scene"] = scene_path
	after["path"] = scene_path
	after["steps"] = reports
	after["one_undoredo"] = undoredo_count == 1
	after["undoredo_count"] = undoredo_count
	after["save_count"] = save_count
	after["script_file_compensated"] = script_compensated
	after["os_global_atomic"] = false
	after["source"] = "editor"
	var action_name: String = "%sjob.transaction" % HHAgentConstants.UNDO_ACTION_PREFIX
	return _errors.ok_changed(command_id, _checks("transaction_steps_verified"), after, true, action_name)


func _flush_graph(
	command_id: String,
	_actions: HHAgentActions,
	scene_path: String,
	graph: Array,
	reports: Array,
) -> Dictionary:
	if graph.is_empty():
		return {"ok": true, "committed": false, "scene": scene_path}
	if scene_path.is_empty():
		for peek_v: Variant in graph:
			var peek: Dictionary = peek_v
			var peek_params_v: Variant = peek.get("params", {})
			var peek_params: Dictionary = peek_params_v if peek_params_v is Dictionary else {}
			var hinted: String = str(peek_params.get("scene", ""))
			if not hinted.is_empty():
				scene_path = hinted
				break
	if scene_path.is_empty():
		return _unverified(command_id, "transaction graph steps need a scene path")
	var edited: Node = EditorInterface.get_edited_scene_root()
	if edited == null or edited.scene_file_path != scene_path:
		EditorInterface.open_scene_from_path(scene_path)
		edited = EditorInterface.get_edited_scene_root()
	if edited == null or edited.scene_file_path != scene_path:
		return _unverified(command_id, "edited_scene is not %s" % scene_path)
	var mgr: EditorUndoRedoManager = EditorInterface.get_editor_undo_redo()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	var action_name: String = "%sjob.transaction" % HHAgentConstants.UNDO_ACTION_PREFIX
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	var minted: Dictionary = {}
	var planned_props: Array = []
	for step_v: Variant in graph:
		var step: Dictionary = step_v
		var step_action: String = str(step.get("action", ""))
		var step_params_v: Variant = step.get("params", {})
		var step_params: Dictionary = step_params_v if step_params_v is Dictionary else {}
		if step_action == "node.add":
			var queued: Dictionary = _nodes.queue_add(mgr, command_id, edited, step_params)
			if queued.get("ok", false) != true:
				_abandon_open_action(mgr, edited, _graph_had_ops(minted, planned_props))
				return queued
			var path_s: String = str(queued.get("path", ""))
			minted[path_s] = queued.get("child")
			reports.append({
				"action": "node.add",
				"path": path_s,
				"uid": str(queued.get("uid", "")),
				"ok": true,
			})
		elif step_action == "property.set":
			var planned: Dictionary = _plan_prop(command_id, edited, minted, step_params)
			if planned.get("ok", false) != true:
				_abandon_open_action(mgr, edited, _graph_had_ops(minted, planned_props))
				return planned
			_props.queue_planned(mgr, planned)
			planned_props.append(planned)
			reports.append({
				"action": "property.set",
				"node_path": str(step_params.get("node_path", "")),
				"property": str(step_params.get("property", "")),
				"ok": true,
			})
		elif step_action == "property.batch":
			var items_v: Variant = step_params.get("items", [])
			if typeof(items_v) != TYPE_ARRAY:
				_abandon_open_action(mgr, edited, _graph_had_ops(minted, planned_props))
				return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "items must be an array", "params.items")
			var items: Array = items_v
			var bi: int = 0
			while bi < items.size():
				if typeof(items[bi]) != TYPE_DICTIONARY:
					_abandon_open_action(mgr, edited, _graph_had_ops(minted, planned_props))
					return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "batch item must be an object", "params.items/%d" % bi)
				var item: Dictionary = items[bi]
				var one: Dictionary = _plan_prop(command_id, edited, minted, {
					"node_path": str(item.get("node_path", "")),
					"property": str(item.get("property", "")),
					"value": item.get("value"),
				})
				if one.get("ok", false) != true:
					_abandon_open_action(mgr, edited, _graph_had_ops(minted, planned_props))
					return one
				_props.queue_planned(mgr, one)
				planned_props.append(one)
				bi += 1
			reports.append({"action": "property.batch", "count": items.size(), "ok": true})
	mgr.commit_action()
	for minted_path: Variant in minted.keys():
		var child: Node = minted[minted_path] as Node
		if child == null or child.get_parent() == null:
			_rollback(mgr, edited)
			return _unverified(command_id, "transaction add did not attach %s" % str(minted_path))
	for prop_v: Variant in planned_props:
		var row: Dictionary = prop_v
		var target: Object = row.get("target") as Object
		var leaf: String = str(row.get("leaf", ""))
		if target == null or not _same_prop(target.get(leaf), row.get("new")):
			_rollback(mgr, edited)
			return _unverified(command_id, "transaction property readback failed for %s" % leaf)
	_meta.mark_dirty(scene_path)
	return {"ok": true, "committed": true, "scene": scene_path}


func _plan_prop(command_id: String, edited: Node, minted: Dictionary, params: Dictionary) -> Dictionary:
	var node_path: String = str(params.get("node_path", ""))
	var node: Node = null
	if minted.has(node_path):
		node = minted[node_path] as Node
	if node == null:
		node = _resolve(edited, node_path)
	return _props.plan_item_on(command_id, edited, node, node_path, str(params.get("property", "")), params.get("value"))


func _apply_immediate(
	command_id: String,
	step_action: String,
	step_params: Dictionary,
	actions: HHAgentActions,
	precondition: Dictionary,
) -> Dictionary:
	if step_action == "scene.create":
		return _scenes.handle(command_id, "godot.scene", "create", step_params, actions, precondition)
	if step_action == "scene.open":
		return _scenes.handle(command_id, "godot.scene", "open", step_params, actions, precondition)
	if step_action == "scene.save":
		return _scenes.handle(command_id, "godot.scene", "save", step_params, actions, precondition)
	if step_action == "script.write":
		return _scripts.handle(command_id, "godot.script", "write", step_params, actions, precondition)
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "unsupported transaction step %s" % step_action, "params.steps")


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


func _same_prop(now_v: Variant, want_v: Variant) -> bool:
	if typeof(now_v) != typeof(want_v):
		return false
	return now_v == want_v


func _graph_had_ops(minted: Dictionary, planned_props: Array) -> bool:
	return not minted.is_empty() or not planned_props.is_empty()


func _abandon_open_action(mgr: EditorUndoRedoManager, edited: Node, had_ops: bool) -> void:
	## Close a create_action that failed mid-queue so UndoRedo is not left open.
	if mgr == null:
		return
	if had_ops:
		mgr.commit_action()
		_rollback(mgr, edited)
		return
	mgr.commit_action(false)


func _rollback(mgr: EditorUndoRedoManager, edited: Node) -> void:
	var hid: int = _meta.history_id(edited)
	if hid == 0 or not mgr.has_method("get_history_undo_redo"):
		return
	var ur: UndoRedo = mgr.get_history_undo_redo(hid)
	if ur != null and ur.has_undo():
		ur.undo()


func _step_row(step_action: String, result: Dictionary) -> Dictionary:
	var after_v: Variant = result.get("after", {})
	var after: Dictionary = after_v if after_v is Dictionary else {}
	return {
		"action": step_action,
		"ok": result.get("ok", false) == true,
		"path": str(after.get("path", "")),
		"disk_hash": str(after.get("disk_hash", "")),
		"uid": str(after.get("uid", "")),
	}


func _fail_applied(command_id: String, code: String, message: String, path_s: String, applied: bool) -> Dictionary:
	var failed: Dictionary = _errors.fail(command_id, code, message, path_s)
	if applied:
		failed["changed"] = true
	return failed


func _with_changed(result: Dictionary, applied: bool) -> Dictionary:
	if applied:
		result["changed"] = true
	return result


func _unverified(command_id: String, message: String) -> Dictionary:
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, message, "")


func _checks(post: String) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	out.append(post)
	return out

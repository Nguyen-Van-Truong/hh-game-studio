class_name HHAgentNodeAdapter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")
const _MetaScript: GDScript = preload("res://addons/hh_agent/core/hh_scene_meta.gd")
const _IdentityScript: GDScript = preload("res://addons/hh_agent/core/hh_identity.gd")

## Proven node CRUD on the editor main thread via EditorUndoRedoManager.

var _errors: HHAgentErrors = HHAgentErrors.new()
var _meta: HHAgentSceneMeta = HHAgentSceneMeta.new()
var _identity: HHAgentIdentity = HHAgentIdentity.new()


func handles(action: String) -> bool:
	return (
		action == "add"
		or action == "remove"
		or action == "rename"
		or action == "reparent"
		or action == "reorder"
		or action == "duplicate"
		or action == "group"
		or action == "instantiate"
		or action == "make_local"
		or action == "undo"
		or action == "redo"
	)


func handle(
	command_id: String,
	method: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
	precondition: Dictionary,
) -> Dictionary:
	if method != "godot.node" and not (method == "godot.scene" and action == "instantiate"):
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not a node verb", "")
	var def: Dictionary = actions.lookup(method, action)
	var post: String = str(def.get("postcondition", ""))
	if post.is_empty():
		post = _fallback_post(action)
	if action == "add":
		return _add(command_id, params, precondition, post)
	if action == "remove":
		return _remove(command_id, params, precondition, post)
	if action == "rename":
		return _rename(command_id, params, precondition, post)
	if action == "reparent":
		return _reparent(command_id, params, precondition, post)
	if action == "reorder":
		return _reorder(command_id, params, precondition, post)
	if action == "duplicate":
		return _duplicate(command_id, params, precondition, post)
	if action == "group":
		return _group(command_id, params, precondition, post)
	if action == "instantiate":
		return _instantiate(command_id, params, precondition, post)
	if action == "make_local":
		return _make_local(command_id, params, precondition, post)
	if action == "undo":
		return _history(command_id, params, post, false)
	if action == "redo":
		return _history(command_id, params, post, true)
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "node.%s is not a proven CRUD verb" % action, "")


func queue_add(mgr: EditorUndoRedoManager, command_id: String, edited: Node, params: Dictionary) -> Dictionary:
	var parent: Node = _resolve(edited, str(params.get("parent", "")))
	if parent == null:
		return _unverified(command_id, "parent not found")
	_ensure_editable(edited, parent)
	var class_name_s: String = str(params.get("class_name", ""))
	var name_s: String = str(params.get("name", ""))
	var class_err: Dictionary = _instantiate_class(command_id, class_name_s)
	if class_err.get("ok", false) != true:
		return class_err
	var child: Node = class_err.get("node") as Node
	child.name = name_s
	if _sibling_taken(parent, name_s, child):
		child.free()
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "sibling name already used", "params.name")
	var owner: Node = _identity.pick_owner(parent, edited)
	var uid: String = _identity.mint()
	_identity.stamp(child, uid)
	_queue_root_stamp(mgr, edited)
	_queue_editable(mgr, edited, parent)
	mgr.add_do_method(parent, "add_child", child, true)
	mgr.add_do_method(child, "set_owner", owner)
	mgr.add_do_method(child, "set_meta", HHAgentConstants.NODE_UID_META, uid)
	mgr.add_do_method(child, "set_meta", HHAgentConstants.NODE_UID_META_HIDDEN, uid)
	mgr.add_undo_method(parent, "remove_child", child)
	mgr.add_undo_reference(child)
	var parent_path: String = "." if parent == edited else _identity.tree_path(parent, edited)
	var path_s: String = name_s if parent_path == "." else "%s/%s" % [parent_path, name_s]
	return {
		"ok": true,
		"child": child,
		"path": path_s,
		"uid": uid,
		"name": name_s,
		"parent": parent_path,
		"class_name": class_name_s,
	}


func _reject_packed(command_id: String, node: Node, edited: Node) -> Dictionary:
	if _identity.is_packed_internal(node, edited):
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"packed instance child requires make_local; refusing a flatten",
			"params.node_path",
		)
	return {}


func _fallback_post(action: String) -> String:
	if action == "add":
		return "node_exists_under_parent"
	if action == "remove":
		return "node_path_absent"
	if action == "rename":
		return "node_name_equals"
	if action == "reparent":
		return "node_parent_equals"
	if action == "reorder":
		return "node_index_equals"
	if action == "duplicate":
		return "duplicate_sibling_exists"
	if action == "group":
		return "node_group_membership"
	if action == "instantiate":
		return "instance_child_exists"
	if action == "make_local":
		return "instance_is_local"
	if action == "undo":
		return "history_undo_applied"
	if action == "redo":
		return "history_redo_applied"
	return "node_crud"


func _add(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var parent: Node = _resolve(edited, str(params.get("parent", "")))
	if parent == null:
		return _unverified(command_id, "parent not found")
	_ensure_editable(edited, parent)
	var class_name_s: String = str(params.get("class_name", ""))
	var name_s: String = str(params.get("name", ""))
	var class_err: Dictionary = _instantiate_class(command_id, class_name_s)
	if class_err.get("ok", false) != true:
		return class_err
	var child: Node = class_err.get("node") as Node
	child.name = name_s
	if _sibling_taken(parent, name_s, child):
		child.free()
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "sibling name already used", "params.name")
	var owner: Node = _identity.pick_owner(parent, edited)
	var uid: String = _identity.mint()
	_identity.stamp(child, uid)
	var action_name: String = "%snode.add %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, name_s]
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		child.free()
		return _unverified(command_id, "EditorUndoRedoManager missing")
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	_queue_root_stamp(mgr, edited)
	_queue_editable(mgr, edited, parent)
	mgr.add_do_method(parent, "add_child", child, true)
	mgr.add_do_method(child, "set_owner", owner)
	mgr.add_do_method(child, "set_meta", HHAgentConstants.NODE_UID_META, uid)
	mgr.add_do_method(child, "set_meta", HHAgentConstants.NODE_UID_META_HIDDEN, uid)
	mgr.add_undo_method(parent, "remove_child", child)
	mgr.add_undo_reference(child)
	mgr.commit_action()
	if child.get_parent() != parent:
		return _unverified(command_id, "add_child did not attach")
	if str(child.name) != name_s:
		if mgr.has_undo():
			mgr.undo()
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"add_child renamed sibling; refusing force-readable name",
			"params.name",
		)
	if child.owner != owner:
		return _unverified(command_id, "owner was not set")
	if _identity.read_uid(child) != uid:
		return _unverified(command_id, "uid missing after add")
	return _ok_node(command_id, post, action_name, edited, child, str(params.get("scene", "")), true)


func _remove(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var node: Node = _resolve(edited, str(params.get("node_path", "")))
	if node == null:
		return _unverified(command_id, "node not found")
	_ensure_editable(edited, node)
	var packed_err: Dictionary = _reject_packed(command_id, node, edited)
	if not packed_err.is_empty():
		return packed_err
	if node == edited:
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "cannot remove edited scene root", "params.node_path")
	var parent: Node = node.get_parent()
	if parent == null:
		return _unverified(command_id, "node has no parent")
	var old_index: int = node.get_index()
	var old_owner: Node = node.owner
	var uid: String = _identity.read_uid(node)
	var gone_path: String = _identity.tree_path(node, edited)
	var action_name: String = "%snode.remove %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, node.name]
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	mgr.add_do_method(parent, "remove_child", node)
	mgr.add_undo_method(parent, "add_child", node)
	mgr.add_undo_method(parent, "move_child", node, old_index)
	if old_owner != null:
		mgr.add_undo_method(node, "set_owner", old_owner)
	mgr.add_do_reference(node)
	mgr.commit_action()
	if node.get_parent() != null:
		return _unverified(command_id, "node still parented after remove")
	if _resolve(edited, gone_path) != null:
		return _unverified(command_id, "removed path still resolves")
	_meta.mark_dirty(str(params.get("scene", "")))
	var after: Dictionary = _meta.snapshot(edited, str(params.get("scene", "")))
	after["uid"] = uid
	after["path"] = gone_path
	after["absent"] = true
	after["owner"] = ""
	after["source"] = "editor"
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _rename(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var node: Node = _resolve(edited, str(params.get("node_path", "")))
	if node == null:
		return _unverified(command_id, "node not found")
	_ensure_editable(edited, node)
	var packed_rename: Dictionary = _reject_packed(command_id, node, edited)
	if not packed_rename.is_empty():
		return packed_rename
	var new_name: String = str(params.get("name", ""))
	var parent: Node = node.get_parent()
	if parent != null and _sibling_taken(parent, new_name, node):
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "sibling name already used", "params.name")
	var old_name: String = node.name
	var action_name: String = "%snode.rename %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, new_name]
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	mgr.add_do_property(node, "name", new_name)
	mgr.add_undo_property(node, "name", old_name)
	mgr.commit_action()
	if node.name != new_name:
		return _unverified(command_id, "rename did not stick")
	return _ok_node(command_id, post, action_name, edited, node, str(params.get("scene", "")), true)


func _reparent(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var node: Node = _resolve(edited, str(params.get("node_path", "")))
	if node == null:
		return _unverified(command_id, "node not found")
	if node == edited:
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "cannot reparent edited scene root", "params.node_path")
	var packed_reparent: Dictionary = _reject_packed(command_id, node, edited)
	if not packed_reparent.is_empty():
		return packed_reparent
	var new_parent: Node = _resolve(edited, str(params.get("new_parent", "")))
	if new_parent == null:
		return _unverified(command_id, "new_parent not found")
	if node == new_parent or node.is_ancestor_of(new_parent):
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "cannot reparent into own subtree", "params.new_parent")
	var keep_given: bool = params.has("keep_global_transform")
	var keep: bool = true
	if keep_given:
		keep = params.get("keep_global_transform") == true
		if not _identity.supports_global_transform(node):
			return _errors.fail(
				command_id,
				HHAgentErrors.E_INVALID_TYPE,
				"keep_global_transform is unsupported on %s" % node.get_class(),
				"params.keep_global_transform",
			)
	var old_parent: Node = node.get_parent()
	if old_parent == null:
		return _unverified(command_id, "node has no parent")
	var old_index: int = node.get_index()
	var old_owner: Node = node.owner
	_ensure_editable(edited, node)
	_ensure_editable(edited, new_parent)
	var new_owner: Node = _identity.owner_after_reparent(node, new_parent, edited)
	var action_name: String = "%snode.reparent %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, node.name]
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	var old_uid: String = _identity.read_uid(node)
	var fresh_uid: String = ""
	if new_owner == edited and not old_uid.is_empty() and _uid_owned_elsewhere(edited, node, old_uid):
		fresh_uid = _identity.mint()
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	_queue_editable(mgr, edited, new_parent)
	mgr.add_do_method(node, "reparent", new_parent, keep)
	mgr.add_do_method(node, "set_owner", new_owner)
	if not fresh_uid.is_empty():
		mgr.add_do_method(node, "set_meta", HHAgentConstants.NODE_UID_META, fresh_uid)
		mgr.add_do_method(node, "set_meta", HHAgentConstants.NODE_UID_META_HIDDEN, fresh_uid)
	mgr.add_undo_method(node, "reparent", old_parent, keep)
	mgr.add_undo_method(old_parent, "move_child", node, old_index)
	if old_owner != null:
		mgr.add_undo_method(node, "set_owner", old_owner)
	if not fresh_uid.is_empty():
		mgr.add_undo_method(node, "set_meta", HHAgentConstants.NODE_UID_META, old_uid)
		mgr.add_undo_method(node, "set_meta", HHAgentConstants.NODE_UID_META_HIDDEN, old_uid)
	mgr.commit_action()
	if node.get_parent() != new_parent:
		return _unverified(command_id, "reparent did not move the node")
	if node.owner != new_owner:
		return _unverified(command_id, "reparent owner incorrect")
	return _ok_node(command_id, post, action_name, edited, node, str(params.get("scene", "")), true)


func _reorder(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var node: Node = _resolve(edited, str(params.get("node_path", "")))
	if node == null:
		return _unverified(command_id, "node not found")
	_ensure_editable(edited, node)
	var packed_reorder: Dictionary = _reject_packed(command_id, node, edited)
	if not packed_reorder.is_empty():
		return packed_reorder
	var parent: Node = node.get_parent()
	if parent == null:
		return _unverified(command_id, "node has no parent")
	var index: int = int(params.get("index", 0))
	if index < 0 or index >= parent.get_child_count():
		return _errors.fail(command_id, HHAgentErrors.E_OUT_OF_BOUNDS, "index outside sibling range", "params.index")
	var old_index: int = node.get_index()
	var old_owner: Node = node.owner
	var action_name: String = "%snode.reorder %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, node.name]
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	mgr.add_do_method(parent, "move_child", node, index)
	if old_owner != null:
		mgr.add_do_method(node, "set_owner", old_owner)
	mgr.add_undo_method(parent, "move_child", node, old_index)
	if old_owner != null:
		mgr.add_undo_method(node, "set_owner", old_owner)
	mgr.commit_action()
	if node.get_index() != index:
		return _unverified(command_id, "reorder index mismatch")
	var after_ok: Dictionary = _ok_node(command_id, post, action_name, edited, node, str(params.get("scene", "")), true)
	if after_ok.get("ok", false) == true:
		var after_v: Variant = after_ok.get("after", {})
		if after_v is Dictionary:
			(after_v as Dictionary)["index"] = node.get_index()
	return after_ok


func _duplicate(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var node: Node = _resolve(edited, str(params.get("node_path", "")))
	if node == null:
		return _unverified(command_id, "node not found")
	_ensure_editable(edited, node)
	var packed_dup: Dictionary = _reject_packed(command_id, node, edited)
	if not packed_dup.is_empty():
		return packed_dup
	var parent: Node = node.get_parent()
	if parent == null:
		return _unverified(command_id, "node has no parent")
	var copy: Node = node.duplicate()
	if copy == null:
		copy = node.duplicate(Node.DUPLICATE_SIGNALS | Node.DUPLICATE_GROUPS | Node.DUPLICATE_SCRIPTS)
	if copy == null:
		return _unverified(command_id, "Node.duplicate failed")
	var owner: Node = _identity.pick_owner(parent, edited)
	_identity.remint_owned(copy, owner)
	var uid: String = _identity.read_uid(copy)
	var action_name: String = "%snode.duplicate %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, node.name]
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		copy.free()
		return _unverified(command_id, "EditorUndoRedoManager missing")
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	_queue_editable(mgr, edited, parent)
	mgr.add_do_method(parent, "add_child", copy, true)
	_queue_owner_ops(mgr, copy, owner)
	mgr.add_undo_method(parent, "remove_child", copy)
	mgr.add_undo_reference(copy)
	mgr.commit_action()
	if copy.get_parent() != parent:
		return _unverified(command_id, "duplicate was not attached")
	if _identity.read_uid(copy).is_empty() or _identity.read_uid(copy) == _identity.read_uid(node):
		return _unverified(command_id, "duplicate uid collision was not repaired")
	if uid != _identity.read_uid(copy) and not _identity.read_uid(copy).is_empty():
		uid = _identity.read_uid(copy)
	return _ok_node(command_id, post, action_name, edited, copy, str(params.get("scene", "")), true)


func _group(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var node: Node = _resolve(edited, str(params.get("node_path", "")))
	if node == null:
		return _unverified(command_id, "node not found")
	var packed_group: Dictionary = _reject_packed(command_id, node, edited)
	if not packed_group.is_empty():
		return packed_group
	var group: String = str(params.get("group", ""))
	var op: String = str(params.get("op", ""))
	if op != "add" and op != "remove":
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "op must be add or remove", "params.op")
	var action_name: String = "%snode.group %s %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, op, group]
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	_ensure_editable(edited, node)
	var was_in: bool = node.is_in_group(group)
	var want_in: bool = op == "add"
	var hid: int = _meta.history_id(edited)
	if hid == 0 or not mgr.has_method("get_history_undo_redo"):
		return _unverified(command_id, "scene history id unbound")
	var ur: UndoRedo = mgr.get_history_undo_redo(hid)
	if ur == null:
		return _unverified(command_id, "UndoRedo missing for edited scene")
	ur.create_action(action_name)
	ur.add_do_method(Callable(self, "_set_group").bind(node, group, want_in))
	ur.add_undo_method(Callable(self, "_set_group").bind(node, group, was_in))
	ur.commit_action()
	var in_group: bool = node.is_in_group(group)
	if op == "add" and not in_group:
		return _unverified(command_id, "group add did not stick")
	if op == "remove" and in_group:
		return _unverified(command_id, "group remove did not stick")
	var result: Dictionary = _ok_node(command_id, post, action_name, edited, node, str(params.get("scene", "")), true)
	if result.get("ok", false) == true:
		var after_v: Variant = result.get("after", {})
		if after_v is Dictionary:
			(after_v as Dictionary)["group"] = group
			(after_v as Dictionary)["op"] = op
			(after_v as Dictionary)["in_group"] = node.is_in_group(group)
	return result


func _instantiate(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var packed_path: String = str(params.get("packed", ""))
	var packed_jail: Dictionary = _meta.jail(command_id, packed_path)
	if packed_jail.get("ok", false) != true:
		return packed_jail
	if not _meta.is_scene_path(packed_path):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "packed must be .tscn or .scn", packed_path)
	if not FileAccess.file_exists(packed_path):
		return _unverified(command_id, "packed scene missing")
	var loaded: Resource = ResourceLoader.load(packed_path)
	if loaded == null or not (loaded is PackedScene):
		return _unverified(command_id, "packed is not a PackedScene")
	var parent: Node = _resolve(edited, str(params.get("parent", "")))
	if parent == null:
		return _unverified(command_id, "parent not found")
	_ensure_editable(edited, parent)
	var inst: Node = (loaded as PackedScene).instantiate(PackedScene.GEN_EDIT_STATE_INSTANCE)
	if inst == null:
		return _unverified(command_id, "PackedScene.instantiate failed")
	var owner: Node = _identity.pick_owner(parent, edited)
	_identity.remint_owned(inst, owner)
	var action_name: String = "%snode.instantiate %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, packed_path.get_file()]
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		inst.free()
		return _unverified(command_id, "EditorUndoRedoManager missing")
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	_queue_editable(mgr, edited, parent)
	mgr.add_do_method(parent, "add_child", inst, true)
	mgr.add_do_method(inst, "set_owner", owner)
	mgr.add_undo_method(parent, "remove_child", inst)
	mgr.add_undo_reference(inst)
	mgr.commit_action()
	if inst.get_parent() != parent:
		return _unverified(command_id, "instance was not attached")
	if inst.owner != owner:
		return _unverified(command_id, "instance owner incorrect")
	if _identity.read_uid(inst).is_empty():
		return _unverified(command_id, "instance uid missing")
	var result: Dictionary = _ok_node(command_id, post, action_name, edited, inst, str(params.get("scene", "")), true)
	if result.get("ok", false) == true:
		var after_v: Variant = result.get("after", {})
		if after_v is Dictionary:
			(after_v as Dictionary)["packed"] = packed_path
			(after_v as Dictionary)["scene_file_path"] = inst.scene_file_path
	return result


func _make_local(
	command_id: String,
	params: Dictionary,
	precondition: Dictionary,
	post: String,
) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var node: Node = _resolve(edited, str(params.get("node_path", "")))
	if node == null:
		return _unverified(command_id, "node not found")
	if node == edited:
		return _unverified(command_id, "edited root is already local")
	var packed: String = node.scene_file_path
	if packed.is_empty() or packed == edited.scene_file_path:
		return _unverified(command_id, "node is already local")
	_ensure_editable(edited, node)
	var rows: Array = []
	_collect_local_rows(node, rows)
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	var action_name: String = "%snode.make_local %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, node.name]
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	_queue_editable(mgr, edited, node)
	mgr.add_do_method(node, "set_scene_file_path", "")
	mgr.add_undo_method(node, "set_scene_file_path", packed)
	var i: int = 0
	while i < rows.size():
		var row: Dictionary = rows[i]
		var target: Node = row.get("node") as Node
		var old_owner: Node = row.get("owner") as Node
		var old_uid: String = str(row.get("uid", ""))
		var new_uid: String = _identity.mint()
		if target != edited:
			mgr.add_do_method(target, "set_owner", edited)
			if old_owner != null:
				mgr.add_undo_method(target, "set_owner", old_owner)
		mgr.add_do_method(target, "set_meta", HHAgentConstants.NODE_UID_META, new_uid)
		mgr.add_do_method(target, "set_meta", HHAgentConstants.NODE_UID_META_HIDDEN, new_uid)
		if old_uid.is_empty():
			mgr.add_undo_method(target, "remove_meta", HHAgentConstants.NODE_UID_META)
			mgr.add_undo_method(target, "remove_meta", HHAgentConstants.NODE_UID_META_HIDDEN)
		else:
			mgr.add_undo_method(target, "set_meta", HHAgentConstants.NODE_UID_META, old_uid)
			mgr.add_undo_method(target, "set_meta", HHAgentConstants.NODE_UID_META_HIDDEN, old_uid)
		i += 1
	mgr.commit_action()
	if not node.scene_file_path.is_empty():
		return _unverified(command_id, "make_local did not clear scene_file_path")
	if node.owner != edited:
		return _unverified(command_id, "make_local owner is not the edited root")
	if _identity.read_uid(node).is_empty():
		return _unverified(command_id, "make_local uid missing")
	var result: Dictionary = _ok_node(command_id, post, action_name, edited, node, str(params.get("scene", "")), true)
	if result.get("ok", false) == true:
		var after_v: Variant = result.get("after", {})
		if after_v is Dictionary:
			(after_v as Dictionary)["instance_is_local"] = true
			(after_v as Dictionary)["was_packed"] = packed
	return result


func _collect_local_rows(node: Node, rows: Array) -> void:
	rows.append({
		"node": node,
		"owner": node.owner,
		"uid": _identity.read_uid(node),
	})
	var i: int = 0
	while i < node.get_child_count():
		_collect_local_rows(node.get_child(i), rows)
		i += 1


func _history(command_id: String, params: Dictionary, post: String, redo: bool) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), {})
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var count: int = 1
	if params.has("count"):
		count = int(params.get("count"))
	if count < 1:
		return _errors.fail(command_id, HHAgentErrors.E_OUT_OF_BOUNDS, "count must be >= 1", "params.count")
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	var hid: int = _meta.history_id(edited)
	if hid == 0 or not mgr.has_method("get_history_undo_redo"):
		return _unverified(command_id, "scene history id unbound")
	var ur: UndoRedo = mgr.get_history_undo_redo(hid)
	if ur == null:
		return _unverified(command_id, "UndoRedo missing for edited scene")
	var applied: int = 0
	while applied < count:
		if redo:
			if not ur.has_redo():
				break
			ur.redo()
		else:
			if not ur.has_undo():
				break
			ur.undo()
		applied += 1
	if applied < 1:
		return _unverified(command_id, "nothing to %s" % ("redo" if redo else "undo"))
	if applied != count:
		return _unverified(command_id, "%s applied %d of %d; scene history is short" % ["redo" if redo else "undo", applied, count])
	_meta.mark_dirty(str(params.get("scene", "")))
	var after: Dictionary = _meta.snapshot(edited, str(params.get("scene", "")))
	after["source"] = "editor"
	after["applied"] = applied
	after["history_op"] = "redo" if redo else "undo"
	return _errors.ok_changed(command_id, _checks(post), after, true, "")


func _queue_owner_ops(mgr: EditorUndoRedoManager, node: Node, owner: Node) -> void:
	if node == null or owner == null:
		return
	if node != owner:
		mgr.add_do_method(node, "set_owner", owner)
	if not node.scene_file_path.is_empty() and node.scene_file_path != owner.scene_file_path:
		return
	var i: int = 0
	while i < node.get_child_count():
		_queue_owner_ops(mgr, node.get_child(i), owner)
		i += 1


func repair_open_collisions(edited: Node, res_path: String) -> int:
	if edited == null:
		return 0
	var repairs: Array = _identity.plan_collision_repairs(edited)
	if repairs.is_empty():
		return 0
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return 0
	mgr.create_action("%sidentity.repair" % HHAgentConstants.UNDO_ACTION_PREFIX, UndoRedo.MERGE_DISABLE, edited)
	for item_v: Variant in repairs:
		if not (item_v is Dictionary):
			continue
		var item: Dictionary = item_v
		var node: Node = item.get("node") as Node
		var old_uid: String = str(item.get("old", ""))
		var new_uid: String = str(item.get("new", ""))
		if node == null or new_uid.is_empty():
			continue
		mgr.add_do_method(node, "set_meta", HHAgentConstants.NODE_UID_META, new_uid)
		mgr.add_do_method(node, "set_meta", HHAgentConstants.NODE_UID_META_HIDDEN, new_uid)
		if old_uid.is_empty():
			mgr.add_undo_method(node, "remove_meta", HHAgentConstants.NODE_UID_META)
			mgr.add_undo_method(node, "remove_meta", HHAgentConstants.NODE_UID_META_HIDDEN)
		else:
			mgr.add_undo_method(node, "set_meta", HHAgentConstants.NODE_UID_META, old_uid)
			mgr.add_undo_method(node, "set_meta", HHAgentConstants.NODE_UID_META_HIDDEN, old_uid)
	mgr.commit_action()
	_meta.mark_dirty(res_path)
	return repairs.size()


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


func _instantiate_class(command_id: String, class_name_s: String) -> Dictionary:
	if not ClassDB.class_exists(class_name_s):
		return _unverified(command_id, "ClassDB has no class %s" % class_name_s)
	if not ClassDB.can_instantiate(class_name_s):
		return _unverified(command_id, "class %s is not instantiable" % class_name_s)
	if class_name_s != "Node" and not ClassDB.is_parent_class(class_name_s, "Node"):
		return _unverified(command_id, "class_name must extend Node")
	var obj: Variant = ClassDB.instantiate(class_name_s)
	if obj == null or not (obj is Node):
		if obj is Object:
			(obj as Object).free()
		return _unverified(command_id, "failed to instantiate %s" % class_name_s)
	return {"ok": true, "node": obj}


func _sibling_taken(parent: Node, name_s: String, except: Node) -> bool:
	var i: int = 0
	while i < parent.get_child_count():
		var child: Node = parent.get_child(i)
		if child != except and child.name == name_s:
			return true
		i += 1
	return false


func _set_group(node: Node, group: String, present: bool) -> void:
	if node == null or group.is_empty():
		return
	if present:
		if not node.is_in_group(group):
			node.add_to_group(group, true)
	elif node.is_in_group(group):
		node.remove_from_group(group)


func _ensure_editable(edited: Node, node: Node) -> void:
	if edited == null or node == null:
		return
	var inst: Node = _identity.instance_root(node, edited)
	if inst == null:
		return
	if edited.has_method("set_editable_instance"):
		edited.set_editable_instance(inst, true)


func _queue_editable(mgr: EditorUndoRedoManager, edited: Node, parent: Node) -> void:
	if edited == null or parent == null:
		return
	var inst: Node = _identity.instance_root(parent, edited)
	if inst == null:
		return
	if edited.has_method("set_editable_instance"):
		edited.set_editable_instance(inst, true)
		mgr.add_do_method(edited, "set_editable_instance", inst, true)


func _uid_owned_elsewhere(edited: Node, except: Node, uid: String) -> bool:
	if edited == null or uid.is_empty():
		return false
	return _uid_owned_walk(edited, edited, except, uid)


func _uid_owned_walk(node: Node, edited: Node, except: Node, uid: String) -> bool:
	if node != except and (node == edited or node.owner == edited) and _identity.read_uid(node) == uid:
		return true
	var i: int = 0
	while i < node.get_child_count():
		if _uid_owned_walk(node.get_child(i), edited, except, uid):
			return true
		i += 1
	return false


func _queue_root_stamp(mgr: EditorUndoRedoManager, edited: Node) -> void:
	if edited == null or not _identity.read_uid(edited).is_empty():
		return
	var uid: String = _identity.mint()
	mgr.add_do_method(edited, "set_meta", HHAgentConstants.NODE_UID_META, uid)
	mgr.add_do_method(edited, "set_meta", HHAgentConstants.NODE_UID_META_HIDDEN, uid)
	mgr.add_undo_method(edited, "remove_meta", HHAgentConstants.NODE_UID_META)
	mgr.add_undo_method(edited, "remove_meta", HHAgentConstants.NODE_UID_META_HIDDEN)


func _ok_node(
	command_id: String,
	post: String,
	action_name: String,
	edited: Node,
	node: Node,
	res_path: String,
	changed: bool,
) -> Dictionary:
	var uid: String = _identity.read_uid(node)
	if uid.is_empty():
		return _unverified(command_id, "postcondition uid missing")
	var path_s: String = _identity.tree_path(node, edited)
	if path_s.is_empty():
		return _unverified(command_id, "postcondition path missing")
	var owner_s: String = _identity.owner_path(node, edited)
	if node != edited and node.owner == null:
		_ensure_editable(edited, node)
		if node.owner == null:
			return _unverified(command_id, "postcondition owner missing")
	_meta.mark_dirty(res_path)
	var after: Dictionary = _meta.snapshot(edited, res_path)
	after["uid"] = uid
	after["path"] = path_s
	after["owner"] = owner_s
	after["name"] = node.name
	after["class_name"] = node.get_class()
	after["parent"] = "." if node.get_parent() == edited else _identity.tree_path(node.get_parent(), edited)
	after["groups"] = _group_list(node)
	after["source"] = "editor"
	if not action_name.begins_with(HHAgentConstants.UNDO_ACTION_PREFIX):
		return _unverified(command_id, "undo action is not Agent-prefixed")
	return _errors.ok_changed(command_id, _checks(post), after, changed, action_name)


func _group_list(node: Node) -> Array:
	var out: Array = []
	for item: String in node.get_groups():
		if item.begins_with("_"):
			continue
		out.append(item)
	return out


func _mgr() -> EditorUndoRedoManager:
	return EditorInterface.get_editor_undo_redo()


func _unverified(command_id: String, message: String) -> Dictionary:
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, message, "")


func _checks(post: String) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	out.append(post)
	return out

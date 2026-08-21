class_name HHAgentResourceAdapter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")
const _MetaScript: GDScript = preload("res://addons/hh_agent/core/hh_scene_meta.gd")
const _CodecScript: GDScript = preload("res://addons/hh_agent/core/hh_variant_codec.gd")

## Resource create/load/assign/duplicate/edit/save + referenced move/rename/delete.

var _errors: HHAgentErrors = HHAgentErrors.new()
var _meta: HHAgentSceneMeta = HHAgentSceneMeta.new()
var _codec: HHAgentVariantCodec = HHAgentVariantCodec.new()


func handles(action: String) -> bool:
	return (
		action == "create"
		or action == "assign"
		or action == "duplicate"
		or action == "edit"
		or action == "save"
	)


func handles_asset(action: String) -> bool:
	return action == "move" or action == "rename" or action == "delete"


func handle(
	command_id: String,
	method: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
	precondition: Dictionary,
) -> Dictionary:
	if method != "godot.resource":
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not a resource verb", "")
	var def: Dictionary = actions.lookup(method, action)
	var post: String = str(def.get("postcondition", ""))
	if post.is_empty():
		post = _fallback_post(action)
	if action == "create":
		return _create(command_id, params, precondition, post)
	if action == "assign":
		return _assign(command_id, params, precondition, post)
	if action == "duplicate":
		return _duplicate(command_id, params, post)
	if action == "edit":
		return _edit(command_id, params, precondition, post)
	if action == "save":
		return _save(command_id, params, post)
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "resource.%s is not a proven verb" % action, "")


func handle_asset(
	command_id: String,
	method: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
	_precondition: Dictionary,
) -> Dictionary:
	if method != "godot.asset":
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not an asset verb", "")
	var def: Dictionary = actions.lookup(method, action)
	var post: String = str(def.get("postcondition", ""))
	if post.is_empty():
		post = _fallback_asset_post(action)
	if action == "move":
		return _move(command_id, str(params.get("from", "")), str(params.get("to", "")), params.get("rewrite_plan", false) == true, post)
	if action == "rename":
		return _rename(command_id, params, post)
	if action == "delete":
		return _delete(command_id, params, post)
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "asset.%s is not a proven resource verb" % action, "")


func _fallback_post(action: String) -> String:
	if action == "create":
		return "resource_file_exists"
	if action == "assign":
		return "resource_property_path_equals"
	if action == "duplicate":
		return "duplicate_resource_uid_distinct"
	if action == "edit":
		return "resource_field_equals"
	if action == "save":
		return "resource_disk_hash_matches"
	return "resource_op"


func _fallback_asset_post(action: String) -> String:
	if action == "move":
		return "old_path_absent_new_path_present"
	if action == "rename":
		return "asset_renamed"
	if action == "delete":
		return "asset_absent_or_quarantined"
	return "asset_op"


func _create(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var class_name_s: String = str(params.get("class_name", ""))
	var res_path: String = str(params.get("path", ""))
	var builtin: bool = params.get("builtin", false) == true
	var made: Dictionary = _instantiate_resource(command_id, class_name_s)
	if made.get("ok", false) != true:
		return made
	var res: Resource = made.get("resource") as Resource
	if builtin:
		return _create_builtin(command_id, params, precondition, post, res)
	var jail: Dictionary = _meta.jail(command_id, res_path)
	if jail.get("ok", false) != true:
		return jail
	if not _is_external_res(res_path):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "external create requires .tres or .res", res_path)
	if FileAccess.file_exists(res_path):
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "resource already exists", res_path)
	if params.get("local_to_scene", false) == true:
		res.resource_local_to_scene = true
	var persisted: Dictionary = _persist_external(command_id, res, res_path)
	if persisted.get("ok", false) != true:
		return persisted
	var after: Dictionary = {
		"path": res_path,
		"class_name": res.get_class(),
		"uid": str(persisted.get("uid", "")),
		"disk_hash": str(persisted.get("disk_hash", "")),
		"builtin": false,
		"source": "editor",
	}
	return _errors.ok_changed(command_id, _checks(post), after, true)


func _create_builtin(
	command_id: String,
	params: Dictionary,
	precondition: Dictionary,
	post: String,
	res: Resource,
) -> Dictionary:
	var scene_path: String = str(params.get("scene", ""))
	if scene_path.is_empty():
		scene_path = str(params.get("path", ""))
	var node_path: String = str(params.get("node_path", ""))
	var prop: String = str(params.get("property", ""))
	if node_path.is_empty() or prop.is_empty():
		return _errors.fail(
			command_id,
			HHAgentErrors.E_MISSING_REQUIRED,
			"builtin create requires node_path and property",
			"params.property",
		)
	res.resource_local_to_scene = true
	var assigned: Dictionary = _assign_loaded(
		command_id, scene_path, node_path, prop, res, precondition, post, true
	)
	if assigned.get("ok", false) != true:
		return assigned
	var after_v: Variant = assigned.get("after", {})
	if after_v is Dictionary:
		var after: Dictionary = after_v
		after["builtin"] = true
		after["class_name"] = res.get_class()
		if str(after.get("path", "")).is_empty():
			after["path"] = scene_path
	return assigned


func _assign(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var loaded: Dictionary = _resolve_request_resource(command_id, params)
	if loaded.get("ok", false) != true:
		return loaded
	var res: Resource = loaded.get("resource") as Resource
	return _assign_loaded(
		command_id,
		str(params.get("scene", "")),
		str(params.get("node_path", "")),
		str(params.get("property", "")),
		res,
		precondition,
		post,
		false,
	)


func _assign_loaded(
	command_id: String,
	scene_path: String,
	node_path: String,
	prop: String,
	res: Resource,
	precondition: Dictionary,
	post: String,
	builtin: bool,
) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, scene_path, precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var node: Node = _resolve(edited, node_path)
	if node == null:
		return _unverified(command_id, "node not found")
	var walked: Dictionary = _walk_property(command_id, node, prop, edited.scene_file_path, true)
	if walked.get("ok", false) != true:
		return walked
	var target: Object = walked.get("target") as Object
	var leaf: String = str(walked.get("leaf", ""))
	var info: Dictionary = walked.get("info")
	var cycle: Dictionary = _reject_cycle(command_id, target, res)
	if not cycle.is_empty():
		return cycle
	var type_err: Dictionary = _codec.types_compatible(int(info.get("type", 0)), "Resource", res, str(info.get("class_name", "")))
	if not type_err.is_empty():
		var terr: Dictionary = type_err.get("error") if type_err.get("error") is Dictionary else {}
		return _errors.fail(
			command_id,
			str(terr.get("code", HHAgentErrors.E_INVALID_TYPE)),
			str(terr.get("message", "incompatible Resource")),
			"params.resource",
		)
	var old_v: Variant = target.get(leaf)
	var action_name: String = "%sresource.assign %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, prop]
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	mgr.add_do_property(target, leaf, res)
	mgr.add_undo_property(target, leaf, _codec.snapshot(old_v))
	mgr.commit_action()
	var now_v: Variant = target.get(leaf)
	if now_v != res:
		return _unverified(command_id, "assign readback did not equal Resource")
	_meta.mark_dirty(scene_path)
	var enc: Dictionary = _codec.encode(now_v)
	if enc.get("ok", false) != true:
		return _fail_enc(command_id, enc)
	var ref_v: Variant = enc.get("value")
	var ref: Dictionary = ref_v if ref_v is Dictionary else {}
	var after: Dictionary = _meta.snapshot(edited, scene_path)
	after["scene"] = scene_path
	after["node_path"] = node_path
	after["property"] = prop
	after["path"] = str(ref.get("path", res.resource_path))
	after["uid"] = str(ref.get("uid", ""))
	after["class_name"] = str(ref.get("class_name", res.get_class()))
	after["value"] = {"schema": HHAgentVariantCodec.SCHEMA, "type": "Resource", "value": enc.get("value")}
	after["readback_equals"] = true
	after["builtin"] = builtin
	after["source"] = "editor"
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _duplicate(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var src_path: String = str(params.get("path", ""))
	var dest: String = str(params.get("dest", ""))
	var src_jail: Dictionary = _meta.jail(command_id, src_path)
	if src_jail.get("ok", false) != true:
		return src_jail
	var dest_jail: Dictionary = _meta.jail(command_id, dest)
	if dest_jail.get("ok", false) != true:
		return dest_jail
	if not _is_external_res(dest):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "duplicate dest must be .tres or .res", dest)
	if FileAccess.file_exists(dest):
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "duplicate dest already exists", dest)
	var src: Resource = _load_res(src_path)
	if src == null:
		return _unverified(command_id, "source resource missing")
	var source_uid: String = _uid_of(src_path)
	var copy: Resource = src.duplicate(true)
	if copy == null:
		return _unverified(command_id, "Resource.duplicate failed")
	if params.get("local_to_scene", false) == true:
		copy.resource_local_to_scene = true
	var persisted: Dictionary = _persist_external(command_id, copy, dest)
	if persisted.get("ok", false) != true:
		return persisted
	var dest_uid: String = str(persisted.get("uid", ""))
	if dest_uid.is_empty() or dest_uid == source_uid:
		_cleanup_new_external(dest)
		return _unverified(command_id, "duplicate uid was not distinct")
	var after: Dictionary = {
		"path": dest,
		"source_path": src_path,
		"uid": dest_uid,
		"source_uid": source_uid,
		"class_name": copy.get_class(),
		"disk_hash": str(persisted.get("disk_hash", "")),
		"source": "editor",
	}
	return _errors.ok_changed(command_id, _checks(post), after, true)


func _edit(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var res_path: String = str(params.get("path", ""))
	var jail: Dictionary = _meta.jail(command_id, res_path)
	if jail.get("ok", false) != true:
		return jail
	var res: Resource = _load_res(res_path)
	if res == null:
		return _unverified(command_id, "resource missing")
	var shared_flag: bool = params.get("shared", false) == true
	var unique_flag: bool = params.get("unique", false) == true
	if shared_flag and unique_flag:
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "shared and unique cannot both be true", "params.shared")
	if unique_flag:
		return _unique_then_edit(command_id, params, precondition, post, res)
	var walked: Dictionary = _walk_property(command_id, res, str(params.get("property", "")), res_path, true)
	if walked.get("ok", false) != true:
		return walked
	var gated: Resource = _gated_edit_resource(res, walked)
	var owners: int = _owner_count(gated)
	if owners > 1 and not shared_flag:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"resource is shared by %d owners; pass shared=true or unique=true" % owners,
			"params.path" if gated == res else "params.property",
		)
	return _edit_resource(command_id, params, post, res, res_path, owners, shared_flag)


func _unique_then_edit(
	command_id: String,
	params: Dictionary,
	precondition: Dictionary,
	post: String,
	res: Resource,
) -> Dictionary:
	var src_path: String = str(params.get("path", ""))
	var dest: String = str(params.get("dest", ""))
	if dest.is_empty():
		dest = _unique_dest(src_path)
	var dest_jail: Dictionary = _meta.jail(command_id, dest)
	if dest_jail.get("ok", false) != true:
		return dest_jail
	if not _is_external_res(dest):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "unique dest must be .tres or .res", dest)
	if dest == src_path:
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "unique dest must differ from source", dest)
	if FileAccess.file_exists(dest):
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "unique dest already exists", dest)
	var copy: Resource = res.duplicate(true)
	if copy == null:
		return _unverified(command_id, "unique duplicate failed")
	var persisted: Dictionary = _persist_external(command_id, copy, dest)
	if persisted.get("ok", false) != true:
		return persisted
	var dest_res: Resource = _load_res(dest)
	if dest_res == null:
		dest_res = copy
	var scene_path: String = str(params.get("scene", ""))
	var node_path: String = str(params.get("node_path", ""))
	var assign_prop: String = str(params.get("assign_property", ""))
	var assigned_ok: bool = false
	if scene_path.is_empty() == false and node_path.is_empty() == false:
		if assign_prop.is_empty():
			assign_prop = "texture"
		var assigned: Dictionary = _assign_loaded(
			command_id, scene_path, node_path, assign_prop, dest_res, precondition, "resource_property_path_equals", false
		)
		if assigned.get("ok", false) != true:
			_cleanup_new_external(dest)
			return assigned
		assigned_ok = true
	var edit_params: Dictionary = params.duplicate()
	edit_params["path"] = dest
	var edited: Dictionary = _edit_resource(command_id, edit_params, post, dest_res, dest, 1, false)
	if edited.get("ok", false) != true:
		if assigned_ok:
			_rollback_unique_assign(scene_path, node_path, assign_prop, dest, dest_res)
		else:
			_cleanup_new_external(dest)
		return edited
	var after_v: Variant = edited.get("after", {})
	if after_v is Dictionary:
		var after: Dictionary = after_v
		after["path"] = dest
		after["uid"] = str(persisted.get("uid", ""))
		after["unique"] = true
		after["source_path"] = src_path
	else:
		if assigned_ok:
			_rollback_unique_assign(scene_path, node_path, assign_prop, dest, dest_res)
		else:
			_cleanup_new_external(dest)
		return _unverified(command_id, "unique edit missing after")
	return edited


func _gated_edit_resource(host: Resource, walked: Dictionary) -> Resource:
	var target: Object = walked.get("target") as Object
	if target == null or not (target is Resource):
		return host
	var leaf_res: Resource = target as Resource
	var leaf_path: String = leaf_res.resource_path
	if leaf_path.is_empty() or leaf_path.contains("::"):
		return host
	if not _is_external_res(leaf_path):
		return host
	if host != null and leaf_path.simplify_path() == host.resource_path.simplify_path():
		return host
	return leaf_res


func _rollback_unique_assign(
	scene_path: String,
	node_path: String,
	assign_prop: String,
	dest: String,
	copy: Resource,
) -> void:
	_undo_last_scene(scene_path)
	if _assignment_points_at(scene_path, node_path, assign_prop, dest, copy):
		_undo_last_scene(scene_path)
	if _assignment_points_at(scene_path, node_path, assign_prop, dest, copy):
		return
	_cleanup_new_external(dest)


func _undo_last_scene(scene_path: String) -> void:
	var edited: Node = EditorInterface.get_edited_scene_root()
	if edited == null:
		return
	if not scene_path.is_empty() and edited.scene_file_path != scene_path:
		EditorInterface.open_scene_from_path(scene_path)
		edited = EditorInterface.get_edited_scene_root()
	if edited == null:
		return
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return
	var hid: int = _meta.history_id(edited)
	if hid == 0 or not mgr.has_method("get_history_undo_redo"):
		return
	var ur: UndoRedo = mgr.get_history_undo_redo(hid)
	if ur != null and ur.has_undo():
		ur.undo()


func _assignment_points_at(
	scene_path: String,
	node_path: String,
	assign_prop: String,
	dest: String,
	copy: Resource,
) -> bool:
	var edited: Node = EditorInterface.get_edited_scene_root()
	if edited == null:
		return false
	if not scene_path.is_empty() and edited.scene_file_path != scene_path:
		return false
	var node: Node = _resolve(edited, node_path)
	if node == null:
		return false
	var walked: Dictionary = _walk_property("rollback", node, assign_prop, edited.scene_file_path, true)
	if walked.get("ok", false) != true:
		return false
	var target: Object = walked.get("target") as Object
	var leaf: String = str(walked.get("leaf", ""))
	if target == null or leaf.is_empty():
		return false
	var val: Variant = target.get(leaf)
	if not (val is Resource):
		return false
	var other: Resource = val as Resource
	if copy != null and other == copy:
		return true
	if dest.is_empty() or other.resource_path.is_empty():
		return false
	return other.resource_path.simplify_path() == dest.simplify_path()


func _edit_resource(
	command_id: String,
	params: Dictionary,
	post: String,
	res: Resource,
	res_path: String,
	owners: int,
	shared_flag: bool,
) -> Dictionary:
	var walked: Dictionary = _walk_property(command_id, res, str(params.get("property", "")), res_path, true)
	if walked.get("ok", false) != true:
		return walked
	var target: Object = walked.get("target") as Object
	var leaf: String = str(walked.get("leaf", ""))
	var info: Dictionary = walked.get("info")
	var decoded: Dictionary = _codec.decode(params.get("value"), "params.value")
	if decoded.get("ok", false) != true:
		return _fail_enc(command_id, decoded)
	var kind: String = str(decoded.get("type", ""))
	var new_v: Variant = decoded.get("value")
	if kind == "Resource" and new_v is Resource:
		var cycle: Dictionary = _reject_cycle(command_id, target, new_v as Resource)
		if not cycle.is_empty():
			return cycle
	var type_err: Dictionary = _codec.types_compatible(int(info.get("type", 0)), kind, new_v, str(info.get("class_name", "")))
	if not type_err.is_empty():
		var terr: Dictionary = type_err.get("error") if type_err.get("error") is Dictionary else {}
		return _errors.fail(
			command_id,
			str(terr.get("code", HHAgentErrors.E_INVALID_TYPE)),
			str(terr.get("message", "incompatible value")),
			"params.value",
		)
	var hint_err: Dictionary = _codec.validate_hints(info, new_v, kind)
	if not hint_err.is_empty():
		var herr: Dictionary = hint_err.get("error") if hint_err.get("error") is Dictionary else {}
		return _errors.fail(
			command_id,
			str(herr.get("code", HHAgentErrors.E_OUT_OF_BOUNDS)),
			str(herr.get("message", "hint")),
			"params.value",
		)
	var old_v: Variant = target.get(leaf)
	var action_name: String = "%sresource.edit %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, leaf]
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	var ctx: Object = res
	var edited: Node = EditorInterface.get_edited_scene_root()
	if edited != null:
		ctx = edited
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, ctx)
	mgr.add_do_property(target, leaf, _codec.snapshot(new_v))
	mgr.add_undo_property(target, leaf, _codec.snapshot(old_v))
	mgr.commit_action()
	var now_v: Variant = target.get(leaf)
	if not _codec.same(now_v, new_v):
		return _unverified(command_id, "edit readback did not equal set")
	var after: Dictionary = {
		"path": res_path,
		"property": str(params.get("property", "")),
		"owners": owners,
		"shared": shared_flag,
		"readback_equals": true,
		"source": "editor",
	}
	var enc: Dictionary = _codec.encode(now_v)
	if enc.get("ok", false) != true:
		return _fail_enc(command_id, enc)
	after["value"] = {"schema": HHAgentVariantCodec.SCHEMA, "type": str(enc.get("type", "")), "value": enc.get("value")}
	_meta.mark_dirty(res_path)
	var scene_path: String = str(params.get("scene", ""))
	if scene_path.is_empty() == false:
		_meta.mark_dirty(scene_path)
	var edited_now: Node = EditorInterface.get_edited_scene_root()
	if edited_now != null and not edited_now.scene_file_path.is_empty():
		_meta.mark_dirty(edited_now.scene_file_path)
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _save(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var res_path: String = str(params.get("path", ""))
	var jail: Dictionary = _meta.jail(command_id, res_path)
	if jail.get("ok", false) != true:
		return jail
	if not _is_external_res(res_path):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "resource.save requires .tres or .res", res_path)
	var res: Resource = _load_res(res_path)
	if res == null:
		return _unverified(command_id, "resource missing")
	var persisted: Dictionary = _persist_external(command_id, res, res_path)
	if persisted.get("ok", false) != true:
		return persisted
	var after: Dictionary = {
		"path": res_path,
		"uid": str(persisted.get("uid", "")),
		"class_name": res.get_class(),
		"disk_hash": str(persisted.get("disk_hash", "")),
		"source": "editor",
	}
	return _errors.ok_changed(command_id, _checks(post), after, true)


func _rename(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var src: String = str(params.get("path", ""))
	var name_s: String = str(params.get("name", ""))
	var jail: Dictionary = _meta.jail(command_id, src)
	if jail.get("ok", false) != true:
		return jail
	if name_s.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "name is required", "params.name")
	var ext: String = "." + src.get_extension()
	var dest: String = src.get_base_dir().rstrip("/") + "/" + name_s + ext
	return _move(command_id, src, dest, params.get("rewrite_plan", false) == true, post)


func _delete(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var res_path: String = str(params.get("path", ""))
	var jail: Dictionary = _meta.jail(command_id, res_path)
	if jail.get("ok", false) != true:
		return jail
	if not FileAccess.file_exists(res_path):
		return _unverified(command_id, "resource missing")
	var refs: PackedStringArray = _referencers(res_path)
	if refs.size() > 0:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"refusing delete of still-referenced resource (would orphan); move with rewrite_plan",
			res_path,
		)
	var abs_path: String = ProjectSettings.globalize_path(res_path)
	var err: Error = DirAccess.remove_absolute(abs_path)
	if err != OK and FileAccess.file_exists(res_path):
		return _unverified(command_id, "delete failed: %s" % error_string(err))
	var uid_sidecar: String = res_path + ".uid"
	if FileAccess.file_exists(uid_sidecar):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(uid_sidecar))
	var uid_id: int = ResourceLoader.get_resource_uid(res_path)
	if uid_id != ResourceUID.INVALID_ID and ResourceUID.has_id(uid_id):
		ResourceUID.remove_id(uid_id)
	_meta.refresh_fs(res_path)
	if FileAccess.file_exists(res_path):
		return _unverified(command_id, "resource still on disk after delete")
	var after: Dictionary = {"path": res_path, "absent": true, "source": "editor"}
	return _errors.ok_changed(command_id, _checks(post), after, true)


func _move(command_id: String, src: String, dest: String, rewrite_plan: bool, post: String) -> Dictionary:
	var src_jail: Dictionary = _meta.jail(command_id, src)
	if src_jail.get("ok", false) != true:
		return src_jail
	var dest_jail: Dictionary = _meta.jail(command_id, dest)
	if dest_jail.get("ok", false) != true:
		return dest_jail
	if not FileAccess.file_exists(src):
		return _unverified(command_id, "source missing")
	if FileAccess.file_exists(dest):
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "destination already exists", dest)
	var refs: PackedStringArray = _referencers(src)
	if refs.size() > 0:
		if rewrite_plan:
			return _errors.fail(
				command_id,
				HHAgentErrors.E_UNVERIFIED,
				"rewrite_plan is not proven; refusing in-place reference rewrite",
				src,
			)
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"resource is still referenced; rewrite_plan is not proven",
			src,
		)
	var uid_text: String = _uid_of(src)
	var uid_id: int = ResourceUID.INVALID_ID
	if not uid_text.is_empty():
		uid_id = ResourceUID.text_to_id(uid_text)
	var dir_err: Error = _meta.ensure_parent_dir(dest)
	if dir_err != OK:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "cannot create destination directory", dest)
	var rename_err: Error = DirAccess.rename_absolute(
		ProjectSettings.globalize_path(src), ProjectSettings.globalize_path(dest)
	)
	if rename_err != OK:
		return _unverified(command_id, "move failed: %s" % error_string(rename_err))
	var uid_sidecar: String = src + ".uid"
	if FileAccess.file_exists(uid_sidecar):
		DirAccess.rename_absolute(
			ProjectSettings.globalize_path(uid_sidecar), ProjectSettings.globalize_path(dest + ".uid")
		)
	if uid_id != ResourceUID.INVALID_ID:
		ResourceUID.set_id(uid_id, dest)
	_meta.refresh_fs(src)
	_meta.refresh_fs(dest)
	if FileAccess.file_exists(src) or not FileAccess.file_exists(dest):
		return _unverified(command_id, "move did not relocate the file")
	var new_uid: String = _uid_of(dest)
	if new_uid.is_empty() and uid_id != ResourceUID.INVALID_ID:
		ResourceUID.set_id(uid_id, dest)
		new_uid = ResourceUID.id_to_text(uid_id)
	if new_uid.is_empty():
		new_uid = _ensure_uid(dest)
	if not uid_text.is_empty() and not new_uid.is_empty() and uid_text != new_uid:
		return _unverified(command_id, "UID changed during move")
	var after: Dictionary = {
		"path": dest,
		"from": src,
		"uid": new_uid,
		"old_path_absent": true,
		"disk_hash": _meta.disk_hash(dest),
		"rewritten": 0,
		"source": "editor",
	}
	return _errors.ok_changed(command_id, _checks(post), after, true)


func _persist_external(command_id: String, res: Resource, res_path: String) -> Dictionary:
	var existed: bool = FileAccess.file_exists(res_path)
	var dir_err: Error = _meta.ensure_parent_dir(res_path)
	if dir_err != OK:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "cannot create resource directory", res_path)
	var save_err: Error = ResourceSaver.save(res, res_path)
	if save_err != OK:
		if not existed:
			_cleanup_new_external(res_path)
		if save_err == ERR_FILE_CANT_WRITE or save_err == ERR_CANT_CREATE or save_err == ERR_UNAUTHORIZED:
			return _errors.fail(command_id, HHAgentErrors.E_PATH, "ResourceSaver.save failed: %s" % error_string(save_err), res_path)
		return _unverified(command_id, "ResourceSaver.save failed: %s" % error_string(save_err))
	_meta.refresh_fs(res_path)
	if not FileAccess.file_exists(res_path):
		if not existed:
			_cleanup_new_external(res_path)
		return _unverified(command_id, "resource file missing after ResourceSaver.save")
	var bytes: PackedByteArray = FileAccess.get_file_as_bytes(res_path)
	if bytes.is_empty():
		if not existed:
			_cleanup_new_external(res_path)
		return _unverified(command_id, "ResourceSaver.save wrote zero bytes")
	var disk: String = _sha256_bytes(bytes)
	if disk.is_empty() or disk == "missing":
		if not existed:
			_cleanup_new_external(res_path)
		return _unverified(command_id, "resource disk SHA-256 missing after save")
	var again: String = _meta.disk_hash(res_path)
	if again != disk:
		if not existed:
			_cleanup_new_external(res_path)
		return _unverified(command_id, "resource disk SHA-256 raced during readback")
	var uid_text: String = _uid_of(res_path)
	if uid_text.is_empty():
		uid_text = _ensure_uid(res_path)
	if uid_text.is_empty():
		if not existed:
			_cleanup_new_external(res_path)
		return _unverified(command_id, "UID missing after ResourceSaver.save + disk readback")
	return {"ok": true, "disk_hash": disk, "uid": uid_text, "path": res_path}


func _resolve_request_resource(command_id: String, params: Dictionary) -> Dictionary:
	var uid: String = str(params.get("uid", ""))
	var class_name_s: String = str(params.get("class_name", ""))
	var res_path: String = str(params.get("resource", ""))
	if not uid.is_empty():
		var id: int = ResourceUID.text_to_id(uid)
		if id == ResourceUID.INVALID_ID or not ResourceUID.has_id(id):
			return _unverified(command_id, "uid is not in ResourceUID map")
		var mapped: String = ResourceUID.get_id_path(id)
		if mapped.is_empty():
			return _unverified(command_id, "uid has no path")
		var mapped_jail: Dictionary = _meta.jail(command_id, mapped)
		if mapped_jail.get("ok", false) != true:
			return mapped_jail
		if not FileAccess.file_exists(mapped) or not ResourceLoader.exists(mapped):
			return _unverified(command_id, "uid maps to a missing resource file")
		var loaded_uid: Resource = _load_res(mapped)
		if loaded_uid == null:
			return _unverified(command_id, "uid resource failed to load")
		return {"ok": true, "resource": loaded_uid}
	if not res_path.is_empty():
		var jail: Dictionary = _meta.jail(command_id, res_path)
		if jail.get("ok", false) != true:
			return jail
		var loaded: Resource = _load_res(res_path)
		if loaded == null:
			return _unverified(command_id, "resource path failed to load")
		return {"ok": true, "resource": loaded}
	if not class_name_s.is_empty():
		return _instantiate_resource(command_id, class_name_s)
	return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "resource needs path, uid, or class_name", "params.resource")


func _instantiate_resource(command_id: String, class_name_s: String) -> Dictionary:
	if not ClassDB.class_exists(class_name_s):
		return _unverified(command_id, "ClassDB has no class %s" % class_name_s)
	if not ClassDB.can_instantiate(class_name_s):
		return _unverified(command_id, "class %s is not instantiable" % class_name_s)
	if class_name_s != "Resource" and not ClassDB.is_parent_class(class_name_s, "Resource"):
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "class_name must extend Resource", "params.class_name")
	var inst: Variant = ClassDB.instantiate(class_name_s)
	if inst == null or not (inst is Resource):
		if inst is Node:
			(inst as Node).free()
		return _unverified(command_id, "failed to instantiate %s" % class_name_s)
	return {"ok": true, "resource": inst}


func _walk_property(command_id: String, host: Object, prop: String, scene_path: String, allow_external: bool) -> Dictionary:
	if prop.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "property is required", "params.property")
	var exact: Dictionary = _find_info(host, prop)
	if not exact.is_empty():
		return {"ok": true, "target": host, "leaf": prop, "info": exact}
	var parts: PackedStringArray = PackedStringArray()
	if prop.contains("/"):
		parts = prop.split("/")
	elif prop.contains(":"):
		parts = prop.split(":")
	else:
		return _unverified(command_id, "property %s missing" % prop)
	var cur: Object = host
	var i: int = 0
	while i < parts.size():
		var name_s: String = parts[i]
		var info: Dictionary = _find_info(cur, name_s)
		if info.is_empty():
			return _unverified(command_id, "property %s missing" % name_s)
		if i == parts.size() - 1:
			return {"ok": true, "target": cur, "leaf": name_s, "info": info}
		var nxt: Variant = cur.get(name_s)
		if nxt == null or typeof(nxt) != TYPE_OBJECT:
			return _unverified(command_id, "subresource %s is missing" % name_s)
		if not (nxt is Resource):
			return _errors.fail(command_id, HHAgentErrors.E_INVALID_VARIANT, "nested property is not a Resource", "params.property")
		var nested: Resource = nxt as Resource
		if not allow_external and not _is_current_scene_builtin(nested, scene_path):
			return _unverified(command_id, "external Resource field mutate is not proven here")
		cur = nested
		i += 1
	return _unverified(command_id, "property path empty")


func _is_current_scene_builtin(res: Resource, scene_path: String) -> bool:
	if res == null:
		return false
	var path_s: String = res.resource_path
	if path_s.is_empty():
		return true
	if not path_s.contains("::"):
		return false
	var prefix: String = path_s.get_slice("::", 0)
	if prefix.is_empty() or scene_path.is_empty():
		return false
	return prefix.simplify_path() == scene_path.simplify_path()


func _reject_cycle(command_id: String, host: Object, incoming: Resource) -> Dictionary:
	if incoming == null or not (host is Resource):
		return {}
	var host_res: Resource = host as Resource
	if incoming == host_res:
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "refusing to assign a Resource to itself", "params.value")
	var seen: Dictionary = {}
	if _reaches(incoming, host_res, seen, 0):
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "circular resource reference", "params.value")
	return {}


func _reaches(from_res: Resource, target: Resource, seen: Dictionary, depth: int) -> bool:
	if from_res == null or target == null:
		return false
	if from_res == target:
		return true
	if depth > 32:
		return true
	var key: int = from_res.get_instance_id()
	if seen.has(key):
		return false
	seen[key] = true
	for item_v: Variant in from_res.get_property_list():
		if not (item_v is Dictionary):
			continue
		var info: Dictionary = item_v
		var usage: int = int(info.get("usage", 0))
		if (usage & PROPERTY_USAGE_STORAGE) == 0:
			continue
		if int(info.get("type", 0)) != TYPE_OBJECT:
			continue
		var val: Variant = from_res.get(str(info.get("name", "")))
		if val is Resource and _reaches(val as Resource, target, seen, depth + 1):
			return true
	return false


func _owner_count(res: Resource) -> int:
	if res == null:
		return 0
	var n: int = 0
	var seen: Dictionary = {}
	var edited: Node = EditorInterface.get_edited_scene_root()
	var edited_path: String = ""
	if edited != null:
		edited_path = edited.scene_file_path
		var live: int = _count_in_tree(edited, res)
		n += live
		if not edited_path.is_empty():
			seen[edited_path] = true
			if live == 0 and _scene_file_refs_path(edited_path, res.resource_path):
				n += 1
	var open: PackedStringArray = EditorInterface.get_open_scenes()
	for scene_path: String in open:
		if seen.has(scene_path):
			continue
		if _scene_file_refs_path(scene_path, res.resource_path):
			n += 1
			seen[scene_path] = true
	n += _count_disk_scene_owners(res.resource_path, seen)
	return n


func _count_in_tree(root: Node, res: Resource) -> int:
	var n: int = 0
	var walk_seen: Dictionary = {}
	var stack: Array = [root]
	while not stack.is_empty():
		var node_v: Variant = stack.pop_back()
		if not (node_v is Node):
			continue
		var node: Node = node_v
		n += _count_on_object(node, res, walk_seen)
		var i: int = 0
		while i < node.get_child_count():
			stack.append(node.get_child(i))
			i += 1
	return n


func _count_on_object(obj: Object, res: Resource, walk_seen: Dictionary) -> int:
	if obj == null or res == null:
		return 0
	var key: int = obj.get_instance_id()
	if walk_seen.has(key):
		return 0
	walk_seen[key] = true
	var n: int = 0
	for item_v: Variant in obj.get_property_list():
		if not (item_v is Dictionary):
			continue
		var info: Dictionary = item_v
		if int(info.get("type", 0)) != TYPE_OBJECT:
			continue
		var val: Variant = obj.get(str(info.get("name", "")))
		if val is Resource:
			var other: Resource = val as Resource
			if other == res:
				n += 1
			elif not res.resource_path.is_empty() and other.resource_path == res.resource_path:
				n += 1
			else:
				n += _count_on_object(other, res, walk_seen)
	return n


func _referencers(res_path: String) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	var uid_text: String = _uid_of(res_path)
	var files: PackedStringArray = PackedStringArray()
	_collect_files("res://", files)
	for item: String in files:
		if item == res_path or item == res_path + ".uid" or item == res_path + ".import":
			continue
		if _file_refs(item, res_path, uid_text):
			out.append(item)
	var edited: Node = EditorInterface.get_edited_scene_root()
	if edited != null:
		var live: Resource = _load_res(res_path)
		if live != null and _count_in_tree(edited, live) > 0:
			var scene_p: String = edited.scene_file_path
			if not scene_p.is_empty() and not (scene_p in out):
				out.append(scene_p)
	return out


func _file_refs(file_path: String, res_path: String, uid_text: String) -> bool:
	if ResourceLoader.exists(file_path):
		var deps: PackedStringArray = ResourceLoader.get_dependencies(file_path)
		for dep: String in deps:
			if dep.contains(res_path):
				return true
			if not uid_text.is_empty() and dep.contains(uid_text):
				return true
	if not FileAccess.file_exists(file_path):
		return false
	var text: String = FileAccess.get_file_as_string(file_path)
	if text.contains(res_path):
		return true
	if not uid_text.is_empty() and text.contains(uid_text):
		return true
	return false


func _collect_files(dir_path: String, out: PackedStringArray) -> void:
	var abs_dir: String = ProjectSettings.globalize_path(dir_path)
	var da: DirAccess = DirAccess.open(abs_dir)
	if da == null:
		da = DirAccess.open(dir_path)
	if da == null:
		return
	da.list_dir_begin()
	var name_s: String = da.get_next()
	while name_s != "":
		if name_s == "." or name_s == "..":
			name_s = da.get_next()
			continue
		if name_s.begins_with("."):
			name_s = da.get_next()
			continue
		var child: String = dir_path
		if child.ends_with("/"):
			child += name_s
		else:
			child += "/" + name_s
		if da.current_is_dir():
			if name_s != "addons":
				_collect_files(child, out)
		elif (
			name_s.ends_with(".tscn")
			or name_s.ends_with(".scn")
			or name_s.ends_with(".tres")
			or name_s.ends_with(".res")
			or name_s.ends_with(".gd")
		):
			out.append(child)
		name_s = da.get_next()
	da.list_dir_end()


func _scene_file_refs_path(scene_path: String, res_path: String) -> bool:
	if res_path.is_empty() or scene_path.is_empty():
		return false
	if not scene_path.ends_with(".tscn") and not scene_path.ends_with(".scn"):
		return false
	if not FileAccess.file_exists(scene_path):
		return false
	var text: String = FileAccess.get_file_as_string(scene_path)
	return text.contains(res_path)


func _count_disk_scene_owners(res_path: String, seen: Dictionary) -> int:
	if res_path.is_empty():
		return 0
	var n: int = 0
	var files: PackedStringArray = PackedStringArray()
	_collect_files("res://", files)
	var uid_text: String = _uid_of(res_path)
	var target: Resource = _load_res(res_path)
	for item: String in files:
		if seen.has(item):
			continue
		if item == res_path or item == res_path + ".uid" or item == res_path + ".import":
			continue
		if (
			not item.ends_with(".tscn")
			and not item.ends_with(".scn")
			and not item.ends_with(".tres")
			and not item.ends_with(".res")
		):
			continue
		var hit: bool = _file_refs(item, res_path, uid_text)
		if not hit and target != null and (item.ends_with(".tres") or item.ends_with(".res")):
			var loaded: Resource = _load_res(item)
			if loaded != null:
				var walk_seen: Dictionary = {}
				hit = _count_on_object(loaded, target, walk_seen) > 0
		if hit:
			n += 1
			seen[item] = true
	return n


func _cleanup_new_external(res_path: String) -> void:
	if res_path.is_empty() or not _is_external_res(res_path):
		return
	var uid_id: int = ResourceLoader.get_resource_uid(res_path)
	if FileAccess.file_exists(res_path):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(res_path))
	var sidecar: String = res_path + ".uid"
	if FileAccess.file_exists(sidecar):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(sidecar))
	if uid_id != ResourceUID.INVALID_ID and ResourceUID.has_id(uid_id):
		ResourceUID.remove_id(uid_id)
	_meta.refresh_fs(res_path)


func _load_res(res_path: String) -> Resource:
	if res_path.is_empty():
		return null
	if ResourceLoader.exists(res_path):
		var loaded: Resource = ResourceLoader.load(res_path, "", ResourceLoader.CACHE_MODE_REUSE)
		if loaded != null:
			return loaded
	if FileAccess.file_exists(res_path):
		return ResourceLoader.load(res_path)
	return null


func _uid_of(res_path: String) -> String:
	if res_path.is_empty():
		return ""
	var id: int = ResourceLoader.get_resource_uid(res_path)
	if id != ResourceUID.INVALID_ID:
		return ResourceUID.id_to_text(id)
	return ""


func _ensure_uid(res_path: String) -> String:
	var existing: String = _uid_of(res_path)
	if not existing.is_empty():
		return existing
	var id: int = ResourceUID.create_id()
	ResourceUID.add_id(id, res_path)
	_meta.refresh_fs(res_path)
	if ResourceUID.has_id(id):
		return ResourceUID.id_to_text(id)
	return ""


func _unique_dest(src: String) -> String:
	var base: String = src.get_basename()
	var ext: String = src.get_extension()
	return "%s_unique.%s" % [base, ext]


func _is_external_res(res_path: String) -> bool:
	return res_path.ends_with(".tres") or res_path.ends_with(".res")


func _find_info(obj: Object, name_s: String) -> Dictionary:
	if obj == null or name_s.is_empty():
		return {}
	for item_v: Variant in obj.get_property_list():
		if item_v is Dictionary and str((item_v as Dictionary).get("name", "")) == name_s:
			return item_v
	return {}


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


func _sha256_bytes(bytes: PackedByteArray) -> String:
	var ctx: HashingContext = HashingContext.new()
	var start_err: Error = ctx.start(HashingContext.HASH_SHA256)
	if start_err != OK:
		return ""
	ctx.update(bytes)
	return ctx.finish().hex_encode()


func _unverified(command_id: String, message: String) -> Dictionary:
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, message, "")


func _fail_enc(command_id: String, enc: Dictionary) -> Dictionary:
	var err_v: Variant = enc.get("error", {})
	if err_v is Dictionary:
		var err: Dictionary = err_v
		return _errors.fail(
			command_id,
			str(err.get("code", HHAgentErrors.E_INVALID_VARIANT)),
			str(err.get("message", "variant")),
			str(err.get("path", "")),
		)
	return _unverified(command_id, "variant codec failed")


func _checks(post: String) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	out.append(post)
	return out

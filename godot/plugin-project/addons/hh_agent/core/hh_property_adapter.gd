class_name HHAgentPropertyAdapter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")
const _MetaScript: GDScript = preload("res://addons/hh_agent/core/hh_scene_meta.gd")
const _IdentityScript: GDScript = preload("res://addons/hh_agent/core/hh_identity.gd")
const _CodecScript: GDScript = preload("res://addons/hh_agent/core/hh_variant_codec.gd")

## Inspector property set/batch/reset via one EditorUndoRedoManager action.

var _errors: HHAgentErrors = HHAgentErrors.new()
var _meta: HHAgentSceneMeta = HHAgentSceneMeta.new()
var _identity: HHAgentIdentity = HHAgentIdentity.new()
var _codec: HHAgentVariantCodec = HHAgentVariantCodec.new()


func handles(action: String) -> bool:
	return action == "set" or action == "batch" or action == "reset"


func handle(
	command_id: String,
	method: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
	precondition: Dictionary,
) -> Dictionary:
	if method != "godot.property":
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not a property verb", "")
	var def: Dictionary = actions.lookup(method, action)
	var post: String = str(def.get("postcondition", ""))
	if post.is_empty():
		post = _fallback_post(action)
	if action == "set":
		return _set_one(command_id, params, precondition, post)
	if action == "batch":
		return _set_batch(command_id, params, precondition, post)
	if action == "reset":
		return _reset(command_id, params, precondition, post)
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "property.%s is not a proven verb" % action, "")


func _fallback_post(action: String) -> String:
	if action == "set":
		return "property_get_equals_set"
	if action == "batch":
		return "batch_properties_match"
	if action == "reset":
		return "property_is_default"
	return "property_set"


func _set_one(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var planned: Dictionary = _plan_item(
		command_id,
		edited,
		str(params.get("node_path", "")),
		str(params.get("property", "")),
		params.get("value"),
		str(params.get("expected_old_hash", "")),
		precondition,
	)
	if planned.get("ok", false) != true:
		return planned
	var action_name: String = "%sproperty.set %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, str(params.get("property", ""))]
	var applied: Dictionary = _commit(command_id, edited, action_name, [planned], str(params.get("scene", "")))
	if applied.get("ok", false) != true:
		return applied
	var row: Dictionary = (applied.get("items") as Array)[0]
	var after: Dictionary = _meta.snapshot(edited, str(params.get("scene", "")))
	after["scene"] = str(params.get("scene", ""))
	after["node_path"] = str(params.get("node_path", ""))
	after["property"] = str(params.get("property", ""))
	after["value"] = row.get("encoded")
	after["property_hash"] = str(row.get("hash", ""))
	after["readback_equals"] = true
	after["discovery"] = row.get("discovery")
	after["source"] = "editor"
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _set_batch(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var raw_items: Variant = params.get("items", [])
	if typeof(raw_items) != TYPE_ARRAY:
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "items must be an array", "params.items")
	var items: Array = raw_items
	if items.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_OUT_OF_BOUNDS, "items must not be empty", "params.items")
	var planned: Array = []
	var i: int = 0
	while i < items.size():
		if typeof(items[i]) != TYPE_DICTIONARY:
			return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "batch item must be an object", "params.items/%d" % i)
		var item: Dictionary = items[i]
		var one: Dictionary = _plan_item(
			command_id,
			edited,
			str(item.get("node_path", "")),
			str(item.get("property", "")),
			item.get("value"),
			str(item.get("expected_old_hash", "")),
			{},
		)
		if one.get("ok", false) != true:
			return one
		planned.append(one)
		i += 1
	var action_name: String = "%sproperty.batch" % HHAgentConstants.UNDO_ACTION_PREFIX
	var applied: Dictionary = _commit(command_id, edited, action_name, planned, str(params.get("scene", "")))
	if applied.get("ok", false) != true:
		return applied
	var after_items: Array = []
	for row_v: Variant in applied.get("items"):
		if row_v is Dictionary:
			var row: Dictionary = row_v
			after_items.append({
				"node_path": str(row.get("node_path", "")),
				"property": str(row.get("property", "")),
				"value": row.get("encoded"),
				"property_hash": str(row.get("hash", "")),
			})
	var after: Dictionary = _meta.snapshot(edited, str(params.get("scene", "")))
	after["scene"] = str(params.get("scene", ""))
	after["items"] = after_items
	after["readback_equals"] = true
	after["source"] = "editor"
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _reset(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var node: Node = _resolve(edited, str(params.get("node_path", "")))
	if node == null:
		return _unverified(command_id, "node not found")
	var packed_err: Dictionary = _reject_packed(command_id, node, edited)
	if not packed_err.is_empty():
		return packed_err
	var walked: Dictionary = _walk_property(command_id, node, str(params.get("property", "")))
	if walked.get("ok", false) != true:
		return walked
	var target: Object = walked.get("target") as Object
	var leaf: String = str(walked.get("leaf", ""))
	var revert_found: Dictionary = _revert_value(target, leaf)
	if revert_found.get("ok", false) != true:
		return _unverified(command_id, "no ClassDB/property_get_revert default for %s" % leaf)
	var revert_v: Variant = revert_found.get("value")
	var old_v: Variant = target.get(leaf)
	var action_name: String = "%sproperty.reset %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, leaf]
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	mgr.add_do_property(target, leaf, _codec.snapshot(revert_v))
	mgr.add_undo_property(target, leaf, _codec.snapshot(old_v))
	mgr.commit_action()
	var now_v: Variant = target.get(leaf)
	if not _codec.same(now_v, revert_v):
		return _unverified(command_id, "reset readback did not match property_get_revert / class default")
	_meta.mark_dirty(str(params.get("scene", "")))
	var enc: Dictionary = _codec.encode(now_v)
	if enc.get("ok", false) != true:
		return _fail_enc(command_id, enc)
	var after: Dictionary = _meta.snapshot(edited, str(params.get("scene", "")))
	after["scene"] = str(params.get("scene", ""))
	after["node_path"] = str(params.get("node_path", ""))
	after["property"] = str(params.get("property", ""))
	after["value"] = {"schema": HHAgentVariantCodec.SCHEMA, "type": str(enc.get("type", "")), "value": enc.get("value")}
	after["is_default"] = true
	after["reverted"] = true
	after["readback_equals"] = true
	after["property_hash"] = _codec.hash_encoded(enc)
	after["source"] = "editor"
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _plan_item(
	command_id: String,
	edited: Node,
	node_path: String,
	prop: String,
	raw_value: Variant,
	expected_hash: String,
	precondition: Dictionary,
) -> Dictionary:
	var node: Node = _resolve(edited, node_path)
	if node == null:
		return _unverified(command_id, "node not found")
	var packed_err: Dictionary = _reject_packed(command_id, node, edited)
	if not packed_err.is_empty():
		return packed_err
	var walked: Dictionary = _walk_property(command_id, node, prop)
	if walked.get("ok", false) != true:
		return walked
	var target: Object = walked.get("target") as Object
	var leaf: String = str(walked.get("leaf", ""))
	var info: Dictionary = walked.get("info")
	var usage_err: Dictionary = _codec.reject_usage(info)
	if not usage_err.is_empty():
		return _errors.fail(command_id, str((usage_err.get("error") as Dictionary).get("code", "")), str((usage_err.get("error") as Dictionary).get("message", "")), "params.property")
	var decoded: Dictionary = _codec.decode(raw_value, "params.value")
	if decoded.get("ok", false) != true:
		return _fail_enc(command_id, decoded)
	var kind: String = str(decoded.get("type", ""))
	var new_v: Variant = decoded.get("value")
	if kind == "TypedArray":
		new_v = _codec.to_packed(str(decoded.get("element", "")), decoded.get("value") as Array, int(info.get("type", 0)))
	var type_err: Dictionary = _codec.types_compatible(int(info.get("type", 0)), kind, new_v, str(info.get("class_name", "")))
	if not type_err.is_empty():
		return _errors.fail(command_id, str((type_err.get("error") as Dictionary).get("code", "")), str((type_err.get("error") as Dictionary).get("message", "")), "params.value")
	var hint_err: Dictionary = _codec.validate_hints(info, new_v, kind)
	if not hint_err.is_empty():
		return _errors.fail(command_id, str((hint_err.get("error") as Dictionary).get("code", "")), str((hint_err.get("error") as Dictionary).get("message", "")), "params.value")
	var old_v: Variant = target.get(leaf)
	var want_hash: String = expected_hash
	if want_hash.is_empty():
		want_hash = str(precondition.get("property_hash", ""))
	if not want_hash.is_empty():
		var cur_hash: String = _codec.hash_of(old_v)
		if cur_hash.is_empty() or cur_hash != want_hash:
			return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "Inspector/value drifted from expected-old-hash", "precondition.property_hash")
	return {
		"ok": true,
		"target": target,
		"leaf": leaf,
		"old": _codec.snapshot(old_v),
		"new": _codec.snapshot(new_v),
		"node_path": node_path,
		"property": prop,
		"kind": kind,
		"discovery": _codec.discover(info),
	}


func _commit(command_id: String, edited: Node, action_name: String, planned: Array, res_path: String) -> Dictionary:
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	for item_v: Variant in planned:
		var item: Dictionary = item_v
		var target: Object = item.get("target") as Object
		var leaf: String = str(item.get("leaf", ""))
		mgr.add_do_property(target, leaf, item.get("new"))
		mgr.add_undo_property(target, leaf, item.get("old"))
	mgr.commit_action()
	var after_items: Array = []
	for item_v2: Variant in planned:
		var row: Dictionary = item_v2
		var target2: Object = row.get("target") as Object
		var leaf2: String = str(row.get("leaf", ""))
		var now_v: Variant = target2.get(leaf2)
		if not _codec.same(now_v, row.get("new")):
			_rollback(mgr, edited)
			return _unverified(command_id, "readback did not equal set for %s" % leaf2)
		var enc: Dictionary = _codec.encode(now_v)
		if enc.get("ok", false) != true:
			_rollback(mgr, edited)
			return _fail_enc(command_id, enc)
		after_items.append({
			"node_path": str(row.get("node_path", "")),
			"property": str(row.get("property", "")),
			"encoded": {"schema": HHAgentVariantCodec.SCHEMA, "type": str(enc.get("type", "")), "value": enc.get("value")},
			"hash": _codec.hash_encoded(enc),
			"discovery": row.get("discovery"),
		})
	_meta.mark_dirty(res_path)
	return {"ok": true, "items": after_items}


func _rollback(mgr: EditorUndoRedoManager, edited: Node) -> void:
	var hid: int = _meta.history_id(edited)
	if hid == 0 or not mgr.has_method("get_history_undo_redo"):
		return
	var ur: UndoRedo = mgr.get_history_undo_redo(hid)
	if ur != null and ur.has_undo():
		ur.undo()


func _walk_property(command_id: String, node: Object, prop: String) -> Dictionary:
	if prop.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "property is required", "params.property")
	var exact: Dictionary = _find_info(node, prop)
	if not exact.is_empty():
		return {"ok": true, "target": node, "leaf": prop, "info": exact}
	var parts: PackedStringArray = PackedStringArray()
	if prop.contains("/"):
		parts = prop.split("/")
	elif prop.contains(":"):
		parts = prop.split(":")
	else:
		return _unverified(command_id, "property %s missing" % prop)
	var cur: Object = node
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
		var res: Resource = nxt as Resource
		if not res.resource_path.is_empty():
			return _unverified(command_id, "external Resource field mutate is not proven here")
		cur = res
		i += 1
	return _unverified(command_id, "property path empty")


func _revert_value(target: Object, leaf: String) -> Dictionary:
	if target == null or leaf.is_empty():
		return {}
	if target.has_method("property_can_revert") and target.has_method("property_get_revert"):
		if target.property_can_revert(leaf):
			return {"ok": true, "value": target.property_get_revert(leaf)}
	var cls: String = target.get_class()
	while not cls.is_empty():
		if _class_has_property(cls, leaf):
			return {"ok": true, "value": ClassDB.class_get_property_default_value(cls, leaf)}
		cls = ClassDB.get_parent_class(cls)
	var class_name_s: String = target.get_class()
	if ClassDB.class_exists(class_name_s) and ClassDB.can_instantiate(class_name_s):
		var inst: Variant = ClassDB.instantiate(class_name_s)
		if inst is Object:
			var fresh: Object = inst
			var val: Variant = fresh.get(leaf)
			fresh.free()
			return {"ok": true, "value": val}
	return {}


func _class_has_property(class_name_s: String, leaf: String) -> bool:
	if class_name_s.is_empty() or leaf.is_empty():
		return false
	for item_v: Variant in ClassDB.class_get_property_list(class_name_s, true):
		if item_v is Dictionary and str((item_v as Dictionary).get("name", "")) == leaf:
			return true
	return false


func _find_info(obj: Object, name_s: String) -> Dictionary:
	if obj == null:
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


func _reject_packed(command_id: String, node: Node, edited: Node) -> Dictionary:
	if _identity.is_packed_internal(node, edited):
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"packed instance child requires make_local; refusing a flatten",
			"params.node_path",
		)
	return {}


func _mgr() -> EditorUndoRedoManager:
	return EditorInterface.get_editor_undo_redo()


func _unverified(command_id: String, message: String) -> Dictionary:
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, message, "")


func _fail_enc(command_id: String, enc: Dictionary) -> Dictionary:
	var err_v: Variant = enc.get("error", {})
	if err_v is Dictionary:
		var err: Dictionary = err_v
		return _errors.fail(command_id, str(err.get("code", HHAgentErrors.E_INVALID_VARIANT)), str(err.get("message", "variant")), str(err.get("path", "")))
	return _unverified(command_id, "variant codec failed")


func _checks(post: String) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	out.append(post)
	return out

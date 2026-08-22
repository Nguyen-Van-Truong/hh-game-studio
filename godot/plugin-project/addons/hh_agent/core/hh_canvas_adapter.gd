class_name HHAgentCanvasAdapter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")
const _MetaScript: GDScript = preload("res://addons/hh_agent/core/hh_scene_meta.gd")
const _IdentityScript: GDScript = preload("res://addons/hh_agent/core/hh_identity.gd")
const _CodecScript: GDScript = preload("res://addons/hh_agent/core/hh_variant_codec.gd")
const _PropertyScript: GDScript = preload("res://addons/hh_agent/core/hh_property_adapter.gd")

## Typed Node2D/CanvasItem/Sprite2D/TextureRect/Camera2D verbs.
## Bounds/frame-view/readback use get_global_transform + get_rect.
## Never invent a 32px box when get_rect / get_global_rect is valid.
## camera.make_current is a typed verb (add_do_method on Camera2D).
## Catalog: register in actions.json. Generated plugin-validator.json /
## mcp-tools.json are coordinator-owned (`npm run generate`); no extra pipeline.

var _errors: HHAgentErrors = HHAgentErrors.new()
var _meta: HHAgentSceneMeta = HHAgentSceneMeta.new()
var _identity: HHAgentIdentity = HHAgentIdentity.new()
var _codec: HHAgentVariantCodec = HHAgentVariantCodec.new()
var _props: HHAgentPropertyAdapter = HHAgentPropertyAdapter.new()


func handles(method: String, action: String) -> bool:
	if method == "godot.canvas":
		return action == "bounds" or action == "layout_batch"
	if method == "godot.camera":
		return action == "make_current"
	return false


func handle(
	command_id: String,
	method: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
	precondition: Dictionary,
) -> Dictionary:
	if not handles(method, action):
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not a canvas/camera verb", "")
	var def: Dictionary = actions.lookup(method, action)
	var post: String = str(def.get("postcondition", ""))
	if post.is_empty():
		post = _fallback_post(action)
	if method == "godot.canvas" and action == "bounds":
		return _bounds(command_id, params, post)
	if method == "godot.canvas" and action == "layout_batch":
		return _layout_batch(command_id, params, actions, precondition, post)
	if method == "godot.camera" and action == "make_current":
		return _make_current(command_id, params, precondition, post)
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "%s.%s is not a proven verb" % [method, action], "")


static func engine_world_rect(node: Node) -> Dictionary:
	if node == null:
		return _rect_fail()
	if node is Control:
		var ctrl: Control = node as Control
		var global_rect: Rect2 = ctrl.get_global_rect()
		return {
			"ok": true,
			"rect": global_rect,
			"rect_source": "get_global_rect",
			"invented_box": false,
			"used_engine_transform": true,
		}
	if node is Sprite2D:
		var spr: Sprite2D = node as Sprite2D
		var local_spr: Rect2 = spr.get_rect()
		if local_spr.size.x > 0.0 and local_spr.size.y > 0.0:
			return {
				"ok": true,
				"rect": spr.get_global_transform() * local_spr,
				"rect_source": "get_rect",
				"invented_box": false,
				"used_engine_transform": true,
			}
	if node is AnimatedSprite2D:
		var anim: AnimatedSprite2D = node as AnimatedSprite2D
		var local_anim: Rect2 = anim.get_rect()
		if local_anim.size.x > 0.0 and local_anim.size.y > 0.0:
			return {
				"ok": true,
				"rect": anim.get_global_transform() * local_anim,
				"rect_source": "get_rect",
				"invented_box": false,
				"used_engine_transform": true,
			}
	if node is Node2D:
		var n2: Node2D = node as Node2D
		var xf: Transform2D = n2.get_global_transform()
		return {
			"ok": true,
			"rect": Rect2(xf.origin, Vector2.ZERO),
			"rect_source": "origin",
			"invented_box": false,
			"degenerate_extent": true,
			"used_engine_transform": true,
		}
	return _rect_fail()


static func _rect_fail() -> Dictionary:
	return {
		"ok": false,
		"rect": Rect2(),
		"rect_source": "none",
		"invented_box": false,
		"used_engine_transform": false,
	}


func _fallback_post(action: String) -> String:
	if action == "bounds":
		return "canvas_bounds_engine_rect"
	if action == "layout_batch":
		return "layout_batch_one_undo"
	if action == "make_current":
		return "camera_is_current"
	return "canvas_verb"


func _bounds(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), {})
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var node: Node = _resolve(edited, str(params.get("node_path", "")))
	if node == null:
		return _unverified(command_id, "node not found")
	if not (node is CanvasItem):
		return _errors.fail(
			command_id,
			HHAgentErrors.E_INVALID_TYPE,
			"canvas.bounds requires a CanvasItem",
			"params.node_path",
		)
	var ci: CanvasItem = node as CanvasItem
	var xf: Transform2D = ci.get_global_transform()
	var packed: Dictionary = engine_world_rect(node)
	if packed.get("ok", false) != true:
		return _unverified(command_id, "engine bounds unavailable")
	if packed.get("invented_box", false) == true:
		return _unverified(command_id, "refusing invented bounds box")
	var rect_v: Variant = packed.get("rect")
	if not (rect_v is Rect2):
		return _unverified(command_id, "engine rect missing")
	var world: Rect2 = rect_v
	var gp_enc: Dictionary = _encode_value(xf.origin)
	var xf_enc: Dictionary = _encode_value(xf)
	var rect_enc: Dictionary = _encode_value(world)
	if gp_enc.is_empty() or xf_enc.is_empty() or rect_enc.is_empty():
		return _unverified(command_id, "variant encode failed for engine transform")
	var after: Dictionary = _meta.snapshot(edited, str(params.get("scene", "")))
	after["scene"] = str(params.get("scene", ""))
	after["node_path"] = str(params.get("node_path", ""))
	after["class_name"] = node.get_class()
	after["global_position"] = gp_enc
	after["global_transform"] = xf_enc
	after["rect"] = rect_enc
	after["rect_source"] = str(packed.get("rect_source", ""))
	after["invented_box"] = packed.get("invented_box", false) == true
	after["degenerate_extent"] = packed.get("degenerate_extent", false) == true
	after["used_engine_transform"] = packed.get("used_engine_transform", false) == true
	after["source"] = "engine"
	after["visible"] = ci.visible
	after["modulate"] = _encode_value(ci.modulate)
	after["self_modulate"] = _encode_value(ci.self_modulate)
	after["z_index"] = ci.z_index
	after["z_as_relative"] = ci.z_as_relative
	if node is Node2D:
		var n2: Node2D = node as Node2D
		after["position"] = _encode_value(n2.position)
		after["rotation"] = n2.rotation
		after["scale"] = _encode_value(n2.scale)
		after["y_sort_enabled"] = n2.y_sort_enabled
	if node is Sprite2D:
		var spr: Sprite2D = node as Sprite2D
		after["flip_h"] = spr.flip_h
		after["flip_v"] = spr.flip_v
		after["region_enabled"] = spr.region_enabled
		after["region_rect"] = _encode_value(spr.region_rect)
		after["texture"] = _encode_value(spr.texture)
	if node is TextureRect:
		var tr: TextureRect = node as TextureRect
		after["flip_h"] = tr.flip_h
		after["flip_v"] = tr.flip_v
		after["texture"] = _encode_value(tr.texture)
	if node is Camera2D:
		var cam: Camera2D = node as Camera2D
		after["is_current"] = cam.is_current()
		after["limit_left"] = cam.limit_left
		after["limit_top"] = cam.limit_top
		after["limit_right"] = cam.limit_right
		after["limit_bottom"] = cam.limit_bottom
		after["limit_enabled"] = cam.limit_enabled
		after["zoom"] = _encode_value(cam.zoom)
	return _errors.ok_read(command_id, _checks(post), after)


func _layout_batch(
	command_id: String,
	params: Dictionary,
	_actions: HHAgentActions,
	precondition: Dictionary,
	post: String,
) -> Dictionary:
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
		var node_path: String = str(item.get("node_path", ""))
		var node: Node = _resolve(edited, node_path)
		var one: Dictionary = _props.plan_item_on(
			command_id,
			edited,
			node,
			node_path,
			str(item.get("property", "")),
			item.get("value"),
			str(item.get("expected_old_hash", "")),
		)
		if one.get("ok", false) != true:
			return one
		planned.append(one)
		i += 1
	var action_name: String = "%scanvas.layout_batch" % HHAgentConstants.UNDO_ACTION_PREFIX
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	for item_v: Variant in planned:
		if item_v is Dictionary:
			_props.queue_planned(mgr, item_v as Dictionary)
	mgr.commit_action()
	var after_items: Array = []
	for item_v2: Variant in planned:
		var row: Dictionary = item_v2
		var target2: Object = row.get("target") as Object
		var leaf2: String = str(row.get("leaf", ""))
		var now_v: Variant = target2.get(leaf2)
		if not _codec.same(now_v, row.get("new")):
			_rollback(mgr, edited)
			return _unverified(command_id, "layout readback did not equal set for %s" % leaf2)
		var enc: Dictionary = _codec.encode(now_v)
		if enc.get("ok", false) != true:
			_rollback(mgr, edited)
			return _unverified(command_id, "layout encode failed for %s" % leaf2)
		after_items.append({
			"node_path": str(row.get("node_path", "")),
			"property": str(row.get("property", "")),
			"value": {"schema": HHAgentVariantCodec.SCHEMA, "type": str(enc.get("type", "")), "value": enc.get("value")},
			"property_hash": _codec.hash_encoded(enc),
		})
	_meta.mark_dirty(str(params.get("scene", "")))
	var after: Dictionary = _meta.snapshot(edited, str(params.get("scene", "")))
	after["scene"] = str(params.get("scene", ""))
	after["items"] = after_items
	after["readback_equals"] = true
	after["source"] = "editor"
	var checks: PackedStringArray = PackedStringArray()
	checks.append(post)
	checks.append("batch_properties_match")
	return _errors.ok_changed(command_id, checks, after, true, action_name)


func _rollback(mgr: EditorUndoRedoManager, edited: Node) -> void:
	var hid: int = _meta.history_id(edited)
	if hid == 0 or not mgr.has_method("get_history_undo_redo"):
		return
	var ur: UndoRedo = mgr.get_history_undo_redo(hid)
	if ur != null and ur.has_undo():
		ur.undo()


func _make_current(
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
	var packed_err: Dictionary = _reject_packed(command_id, node, edited)
	if not packed_err.is_empty():
		return packed_err
	if not (node is Camera2D):
		return _errors.fail(
			command_id,
			HHAgentErrors.E_INVALID_TYPE,
			"camera.make_current requires Camera2D",
			"params.node_path",
		)
	var cam: Camera2D = node as Camera2D
	var prev: Camera2D = _find_current_camera(edited)
	var already: bool = cam.is_current()
	var action_name: String = "%scamera.make_current %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, cam.name]
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	mgr.add_do_method(cam, "make_current")
	if already:
		mgr.add_undo_method(cam, "make_current")
	elif prev != null and prev != cam:
		mgr.add_undo_method(prev, "make_current")
	else:
		mgr.add_undo_method(cam, "set_enabled", false)
	mgr.commit_action()
	if not cam.is_current():
		return _unverified(command_id, "Camera2D.make_current readback is not current")
	_meta.mark_dirty(str(params.get("scene", "")))
	var after: Dictionary = _meta.snapshot(edited, str(params.get("scene", "")))
	after["scene"] = str(params.get("scene", ""))
	after["node_path"] = str(params.get("node_path", ""))
	after["is_current"] = true
	after["class_name"] = "Camera2D"
	after["previous_path"] = "" if prev == null or prev == cam else _identity.tree_path(prev, edited)
	after["source"] = "editor"
	return _errors.ok_changed(command_id, _checks(post), after, not already, action_name)


func _find_current_camera(root: Node) -> Camera2D:
	if root == null:
		return null
	if root is Camera2D:
		var cam: Camera2D = root as Camera2D
		if cam.is_current():
			return cam
	var i: int = 0
	while i < root.get_child_count():
		var found: Camera2D = _find_current_camera(root.get_child(i))
		if found != null:
			return found
		i += 1
	return null


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


func _encode_value(value: Variant) -> Dictionary:
	var enc: Dictionary = _codec.encode(value)
	if enc.get("ok", false) != true:
		return {}
	return {
		"schema": HHAgentVariantCodec.SCHEMA,
		"type": str(enc.get("type", "")),
		"value": enc.get("value"),
	}


func _mgr() -> EditorUndoRedoManager:
	return EditorInterface.get_editor_undo_redo()


func _unverified(command_id: String, message: String) -> Dictionary:
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, message, "")


func _checks(post: String) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	out.append(post)
	return out

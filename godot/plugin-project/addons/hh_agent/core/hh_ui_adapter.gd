class_name HHAgentUiAdapter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")
const _MetaScript: GDScript = preload("res://addons/hh_agent/core/hh_scene_meta.gd")
const _IdentityScript: GDScript = preload("res://addons/hh_agent/core/hh_identity.gd")
const _CodecScript: GDScript = preload("res://addons/hh_agent/core/hh_variant_codec.gd")

## Typed Godot 4.7.1 Control / Theme / Container verbs.
## Presets via set_anchors_and_offsets_preset only (paper enum).
## Theme items via Theme.set_stylebox / set_font / Control.add_theme_*_override.
## Never mutate the stock ThemeDB default theme. Never the removed Control focus-owner getter.
## Owner getter is Viewport.gui_get_focus_owner. Bounds use get_global_rect.
## One EditorUndoRedoManager action per stroke. Agent: prefix.
## Catalog: register in actions.json. Generated plugin-validator.json /
## mcp-tools.json are coordinator-owned (`npm run generate`).
## Honest Alternative: editor grab_focus may not keep has_focus; neighbor
## graph + find_next_valid_focus is the Alternative. SystemFont if no FontFile.
## ProjectSettings window size is not the editor viewport matrix.

const PRESET_TOP_LEFT: String = "top_left"
const PRESET_CENTER: String = "center"
const PRESET_FULL_RECT: String = "full_rect"
const PRESET_BOTTOM_WIDE: String = "bottom_wide"

var _errors: HHAgentErrors = HHAgentErrors.new()
var _meta: HHAgentSceneMeta = HHAgentSceneMeta.new()
var _identity: HHAgentIdentity = HHAgentIdentity.new()
var _codec: HHAgentVariantCodec = HHAgentVariantCodec.new()


class ControlStroke:
	extends RefCounted
	var control: Control
	var preset: int = -1
	var old: Dictionary = {}
	var flags: Dictionary = {}

	func apply() -> void:
		if control == null:
			return
		if preset >= 0:
			control.set_anchors_and_offsets_preset(preset)
		HHAgentUiAdapter._write_layout_dict(control, flags)

	func revert() -> void:
		if control == null:
			return
		HHAgentUiAdapter._write_layout_dict(control, old)


class AnchorStroke:
	extends RefCounted
	var control: Control
	var old: Dictionary = {}
	var neu: Dictionary = {}

	func apply() -> void:
		if control == null:
			return
		HHAgentUiAdapter._write_anchor_dict(control, neu)

	func revert() -> void:
		if control == null:
			return
		HHAgentUiAdapter._write_anchor_dict(control, old)


class LayoutStroke:
	extends RefCounted
	var host: Control
	var old_sep: int = 0
	var new_sep: int = 0
	var sep_kind: String = ""
	var old_columns: int = 1
	var new_columns: int = 1
	var columns_set: bool = false
	var old_margins: Dictionary = {}
	var new_margins: Dictionary = {}
	var old_clip: bool = false
	var new_clip: bool = false
	var clip_set: bool = false
	var old_size: Vector2 = Vector2.ZERO
	var old_min: Vector2 = Vector2.ZERO
	var new_size: Vector2 = Vector2.ZERO
	var size_set: bool = false
	var child_nodes: Array[Control] = []
	var child_old: Array[Dictionary] = []
	var child_new: Array[Dictionary] = []

	func apply() -> void:
		if host == null:
			return
		if sep_kind == "box":
			host.add_theme_constant_override("separation", new_sep)
		elif sep_kind == "grid":
			host.add_theme_constant_override("h_separation", new_sep)
			host.add_theme_constant_override("v_separation", new_sep)
		if columns_set and host is GridContainer:
			(host as GridContainer).columns = new_columns
		for key_s: String in new_margins.keys():
			host.add_theme_constant_override(key_s, int(new_margins[key_s]))
		if clip_set:
			host.clip_contents = new_clip
		if size_set:
			host.custom_minimum_size = new_size
			host.set_size(new_size)
		var i: int = 0
		while i < child_nodes.size():
			HHAgentUiAdapter._write_child_flags(child_nodes[i], child_new[i])
			i += 1
		if host is Container:
			(host as Container).queue_sort()
			host.notification(Container.NOTIFICATION_SORT_CHILDREN)

	func revert() -> void:
		if host == null:
			return
		if sep_kind == "box":
			host.add_theme_constant_override("separation", old_sep)
		elif sep_kind == "grid":
			host.add_theme_constant_override("h_separation", old_sep)
			host.add_theme_constant_override("v_separation", old_sep)
		if columns_set and host is GridContainer:
			(host as GridContainer).columns = old_columns
		for key_s: String in old_margins.keys():
			host.add_theme_constant_override(key_s, int(old_margins[key_s]))
		if clip_set:
			host.clip_contents = old_clip
		if size_set:
			host.custom_minimum_size = old_min
			host.set_size(old_size)
		var i: int = 0
		while i < child_nodes.size():
			HHAgentUiAdapter._write_child_flags(child_nodes[i], child_old[i])
			i += 1
		if host is Container:
			(host as Container).queue_sort()
			host.notification(Container.NOTIFICATION_SORT_CHILDREN)


class ThemeStroke:
	extends RefCounted
	var control: Control
	var theme: Theme
	var old_theme: Theme
	var added_type: String = ""
	var items: Array[Dictionary] = []
	var overrides: Array[Dictionary] = []

	func apply() -> void:
		if theme != null and not added_type.is_empty():
			theme.add_type(added_type)
		if theme != null:
			var i: int = 0
			while i < items.size():
				HHAgentUiAdapter._theme_write(theme, items[i], false)
				i += 1
		if control != null:
			control.theme = theme
			var j: int = 0
			while j < overrides.size():
				HHAgentUiAdapter._override_write(control, overrides[j], false)
				j += 1

	func revert() -> void:
		if control != null:
			var j: int = overrides.size() - 1
			while j >= 0:
				HHAgentUiAdapter._override_write(control, overrides[j], true)
				j -= 1
			control.theme = old_theme
		if theme != null:
			var i: int = items.size() - 1
			while i >= 0:
				HHAgentUiAdapter._theme_write(theme, items[i], true)
				i -= 1
			if not added_type.is_empty() and theme.has_method("remove_type"):
				theme.remove_type(added_type)


func handles(action: String) -> bool:
	return (
		action == "control"
		or action == "theme"
		or action == "layout"
		or action == "anchor"
		or action == "focus"
		or action == "accessibility"
	)


func handle(
	command_id: String,
	method: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
	precondition: Dictionary,
) -> Dictionary:
	if method != "godot.ui" or not handles(action):
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not a ui verb", "")
	var def: Dictionary = actions.lookup(method, action)
	var post: String = str(def.get("postcondition", ""))
	if post.is_empty():
		post = _fallback_post(action)
	if action == "control":
		return _control(command_id, params, precondition, post)
	if action == "theme":
		return _theme(command_id, params, precondition, post)
	if action == "layout":
		return _layout(command_id, params, precondition, post)
	if action == "anchor":
		return _anchor(command_id, params, precondition, post)
	if action == "focus":
		return _focus(command_id, params, post)
	if action == "accessibility":
		return _accessibility(command_id, params, post)
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "ui.%s is not a proven verb" % action, "")


func _fallback_post(action: String) -> String:
	if action == "control":
		return "control_layout_flags_match"
	if action == "theme":
		return "control_theme_path_equals"
	if action == "layout":
		return "container_layout_matches"
	if action == "anchor":
		return "control_anchors_match"
	if action == "focus":
		return "focus_owner_matches"
	if action == "accessibility":
		return "accessibility_fields_present"
	return "ui_verb"


func _control(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_control(command_id, params, precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var control: Control = hold.get("control") as Control
	if _container_parent(control):
		return _unverified(command_id, "anchors on a Container child are ignored")
	var preset_s: String = str(params.get("preset", ""))
	var preset_id: int = _preset_id(preset_s)
	if preset_id < 0:
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "unknown control preset", "params.preset")
	var stroke: ControlStroke = ControlStroke.new()
	stroke.control = control
	stroke.preset = preset_id
	stroke.old = _read_layout_dict(control)
	stroke.flags = _flags_from_params(params)
	var action_name: String = "%sui.control %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, preset_s]
	var committed: Dictionary = _commit_stroke(command_id, edited, action_name, stroke)
	if committed.get("ok", false) != true:
		return committed
	_meta.mark_dirty(str(params.get("scene", "")))
	var after: Dictionary = _control_after(edited, params, control)
	after["preset"] = preset_s
	after["readback_equals"] = true
	after["container_child_anchors_acked"] = false
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _theme(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_control(command_id, params, precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var control: Control = hold.get("control") as Control
	var theme_path: String = str(params.get("theme", ""))
	if theme_path.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "theme path required", "params.theme")
	if theme_path.contains("::"):
		return _unverified(command_id, "refusing RAM-only Theme assign")
	var loaded: Dictionary = _load_theme(command_id, theme_path)
	if loaded.get("ok", false) != true:
		return loaded
	var theme: Theme = loaded.get("theme") as Theme
	var stroke: ThemeStroke = ThemeStroke.new()
	stroke.control = control
	stroke.theme = theme
	if control.theme is Theme:
		stroke.old_theme = control.theme as Theme
	stroke.added_type = str(params.get("add_type", ""))
	var built: Dictionary = _plan_theme_items(command_id, theme, params)
	if built.get("ok", false) != true:
		return built
	for built_v: Variant in built.get("items", []):
		if built_v is Dictionary:
			stroke.items.append(built_v as Dictionary)
	var over: Dictionary = _plan_overrides(command_id, control, params)
	if over.get("ok", false) != true:
		return over
	for over_v: Variant in over.get("items", []):
		if over_v is Dictionary:
			stroke.overrides.append(over_v as Dictionary)
	var action_name: String = "%sui.theme" % HHAgentConstants.UNDO_ACTION_PREFIX
	var committed: Dictionary = _commit_stroke(command_id, edited, action_name, stroke)
	if committed.get("ok", false) != true:
		return committed
	if control.theme != theme:
		return _unverified(command_id, "Control.theme assign readback missing")
	var persisted: Dictionary = {"ok": true, "disk_hash": ""}
	if _is_external_res(theme_path):
		persisted = _persist_res(command_id, theme, theme_path)
		if persisted.get("ok", false) != true:
			return persisted
	_meta.mark_dirty(str(params.get("scene", "")))
	var after: Dictionary = _control_after(edited, params, control)
	after["theme"] = theme_path
	after["theme_assigned"] = true
	after["theme_class"] = theme.get_class()
	after["disk_hash"] = str(persisted.get("disk_hash", ""))
	after["theme_durable"] = _is_external_res(theme_path)
	after["add_type"] = stroke.added_type
	after["colors"] = _theme_colors(control, theme)
	after["font_class"] = _theme_font_class(control, theme)
	after["has_stylebox"] = _theme_has_stylebox(control, theme)
	after["stylebox_class"] = _theme_stylebox_class(control, theme)
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _layout(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_control(command_id, params, precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var control: Control = hold.get("control") as Control
	if not (control is Container):
		return _errors.fail(
			command_id,
			HHAgentErrors.E_INVALID_TYPE,
			"ui.layout requires a Container",
			"params.node_path",
		)
	var stroke: LayoutStroke = LayoutStroke.new()
	stroke.host = control
	stroke.new_sep = int(params.get("separation", 0))
	if control is BoxContainer:
		stroke.sep_kind = "box"
		stroke.old_sep = control.get_theme_constant("separation")
	elif control is GridContainer:
		stroke.sep_kind = "grid"
		stroke.old_sep = control.get_theme_constant("h_separation")
	else:
		stroke.sep_kind = "none"
		stroke.old_sep = stroke.new_sep
	if params.has("columns"):
		if not (control is GridContainer):
			return _errors.fail(
				command_id,
				HHAgentErrors.E_INVALID_TYPE,
				"columns requires GridContainer",
				"params.columns",
			)
		stroke.columns_set = true
		stroke.old_columns = (control as GridContainer).columns
		stroke.new_columns = int(params.get("columns", 1))
	_fill_margins(stroke, control, params)
	if params.has("clip_contents"):
		stroke.clip_set = true
		stroke.old_clip = control.clip_contents
		stroke.new_clip = params.get("clip_contents") == true
	if params.has("viewport_size"):
		var vs: Vector2 = _vec2_param(params, "viewport_size")
		if vs.x < 1.0 or vs.y < 1.0:
			return _errors.fail(command_id, HHAgentErrors.E_OUT_OF_BOUNDS, "viewport_size out of range", "params.viewport_size")
		stroke.size_set = true
		stroke.old_size = control.get_size()
		stroke.old_min = control.custom_minimum_size
		stroke.new_size = vs
	var kids: Dictionary = _plan_children(command_id, edited, params)
	if kids.get("ok", false) != true:
		return kids
	for kn: Variant in kids.get("nodes", []):
		if kn is Control:
			stroke.child_nodes.append(kn as Control)
	for ko: Variant in kids.get("old", []):
		if ko is Dictionary:
			stroke.child_old.append(ko as Dictionary)
	for knw: Variant in kids.get("neu", []):
		if knw is Dictionary:
			stroke.child_new.append(knw as Dictionary)
	var action_name: String = "%sui.layout" % HHAgentConstants.UNDO_ACTION_PREFIX
	var committed: Dictionary = _commit_stroke(command_id, edited, action_name, stroke)
	if committed.get("ok", false) != true:
		return committed
	_flush_sort(control)
	_meta.mark_dirty(str(params.get("scene", "")))
	var rects: Array = _collect_rects(edited, control)
	var audit: Dictionary = _audit_rects(control, rects)
	var after: Dictionary = _control_after(edited, params, control)
	after["separation"] = stroke.new_sep
	after["queue_sort"] = true
	after["rects"] = rects
	after["overlap"] = audit.get("overlap", false) == true
	after["cutoff"] = audit.get("cutoff", false) == true
	after["container_child_anchors_acked"] = false
	if stroke.columns_set:
		after["columns"] = (control as GridContainer).columns
	if stroke.size_set:
		after["viewport_size"] = {"x": stroke.new_size.x, "y": stroke.new_size.y}
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _anchor(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_control(command_id, params, precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var control: Control = hold.get("control") as Control
	if _container_parent(control):
		return _unverified(command_id, "anchors on a Container child are ignored")
	var stroke: AnchorStroke = AnchorStroke.new()
	stroke.control = control
	stroke.old = _read_anchor_dict(control)
	stroke.neu = _anchor_from_params(params, control)
	var action_name: String = "%sui.anchor" % HHAgentConstants.UNDO_ACTION_PREFIX
	var committed: Dictionary = _commit_stroke(command_id, edited, action_name, stroke)
	if committed.get("ok", false) != true:
		return committed
	_meta.mark_dirty(str(params.get("scene", "")))
	var after: Dictionary = _control_after(edited, params, control)
	after["container_child_anchors_acked"] = false
	after["readback_equals"] = true
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _focus(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_control(command_id, params, {})
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var control: Control = hold.get("control") as Control
	var grab: bool = params.get("grab", false) == true
	var stuck: bool = false
	if grab:
		control.grab_focus()
		stuck = control.has_focus()
	var vp: Viewport = control.get_viewport()
	var owner_c: Control = null
	if vp != null:
		owner_c = vp.gui_get_focus_owner()
	var next_c: Control = control.find_next_valid_focus()
	var after: Dictionary = {
		"scene": str(params.get("scene", "")),
		"node_path": str(params.get("node_path", "")),
		"focus_mode": control.focus_mode,
		"has_focus": control.has_focus(),
		"focus_owner": _rel_path(edited, owner_c),
		"focus_owner_class": owner_c.get_class() if owner_c != null else "",
		"next_valid_focus": _rel_path(edited, next_c),
		"neighbors": {
			"left": str(control.focus_neighbor_left),
			"top": str(control.focus_neighbor_top),
			"right": str(control.focus_neighbor_right),
			"bottom": str(control.focus_neighbor_bottom),
		},
		"focus_next": str(control.focus_next),
		"focus_previous": str(control.focus_previous),
		"source": "editor",
	}
	if grab and not stuck:
		after["focus_alternative"] = true
		after["alternative"] = "editor grab_focus may not keep has_focus"
	return _errors.ok_read(command_id, _checks(post), after)


func _accessibility(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_control(command_id, params, {})
	if hold.get("ok", false) != true:
		return hold
	var control: Control = hold.get("control") as Control
	if not _has_prop(control, "accessibility_name"):
		return _unverified(command_id, "accessibility_name missing on this Control")
	var after: Dictionary = {
		"scene": str(params.get("scene", "")),
		"node_path": str(params.get("node_path", "")),
		"accessibility_name": str(control.get("accessibility_name")),
		"accessibility_description": str(control.get("accessibility_description")) if _has_prop(control, "accessibility_description") else "",
		"tooltip_text": control.tooltip_text,
		"focus_mode": control.focus_mode,
		"source": "editor",
	}
	return _errors.ok_read(command_id, _checks(post), after)


func _hold_control(command_id: String, params: Dictionary, precondition: Dictionary) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var node: Node = _resolve(edited, str(params.get("node_path", "")))
	if node == null:
		return _unverified(command_id, "node not found")
	if not (node is Control):
		return _errors.fail(
			command_id,
			HHAgentErrors.E_INVALID_TYPE,
			"ui verb requires a Control",
			"params.node_path",
		)
	var packed_err: Dictionary = _reject_packed(command_id, node, edited)
	if not packed_err.is_empty():
		return packed_err
	return {"ok": true, "root": edited, "control": node as Control}


func _commit_stroke(command_id: String, edited: Node, action_name: String, stroke: RefCounted) -> Dictionary:
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	mgr.add_do_method(stroke, "apply")
	mgr.add_undo_method(stroke, "revert")
	mgr.add_do_reference(stroke)
	mgr.commit_action()
	return {"ok": true}


func _control_after(edited: Node, params: Dictionary, control: Control) -> Dictionary:
	var after: Dictionary = _meta.snapshot(edited, str(params.get("scene", "")))
	after["scene"] = str(params.get("scene", ""))
	after["node_path"] = str(params.get("node_path", ""))
	after["class_name"] = control.get_class()
	after["path"] = str(params.get("node_path", ""))
	var sz: Vector2 = control.get_size()
	var pos: Vector2 = control.get_position()
	var r: Rect2 = control.get_rect()
	var gr: Rect2 = control.get_global_rect()
	after["offset_left"] = control.offset_left
	after["offset_top"] = control.offset_top
	after["offset_right"] = control.offset_right
	after["offset_bottom"] = control.offset_bottom
	after["anchor_left"] = control.anchor_left
	after["anchor_top"] = control.anchor_top
	after["anchor_right"] = control.anchor_right
	after["anchor_bottom"] = control.anchor_bottom
	after["grow_horizontal"] = control.grow_horizontal
	after["grow_vertical"] = control.grow_vertical
	after["size_flags_horizontal"] = control.size_flags_horizontal
	after["size_flags_vertical"] = control.size_flags_vertical
	after["stretch_ratio"] = control.size_flags_stretch_ratio
	after["clip_contents"] = control.clip_contents
	after["size"] = {"x": sz.x, "y": sz.y}
	after["position"] = {"x": pos.x, "y": pos.y}
	after["rect"] = _xywh(r)
	after["global_rect"] = _xywh(gr)
	after["rect_source"] = "get_global_rect"
	after["invented_box"] = false
	after["used_engine_transform"] = true
	after["min_size"] = {"x": control.get_combined_minimum_size().x, "y": control.get_combined_minimum_size().y}
	after["source"] = "editor"
	return after


static func _read_layout_dict(control: Control) -> Dictionary:
	return {
		"anchor_left": control.anchor_left,
		"anchor_top": control.anchor_top,
		"anchor_right": control.anchor_right,
		"anchor_bottom": control.anchor_bottom,
		"offset_left": control.offset_left,
		"offset_top": control.offset_top,
		"offset_right": control.offset_right,
		"offset_bottom": control.offset_bottom,
		"grow_horizontal": control.grow_horizontal,
		"grow_vertical": control.grow_vertical,
		"size_flags_horizontal": control.size_flags_horizontal,
		"size_flags_vertical": control.size_flags_vertical,
		"stretch_ratio": control.size_flags_stretch_ratio,
		"custom_minimum_size": control.custom_minimum_size,
		"clip_contents": control.clip_contents,
		"size": control.get_size(),
		"position": control.get_position(),
	}


static func _write_layout_dict(control: Control, d: Dictionary) -> void:
	if d.has("anchor_left"):
		control.anchor_left = float(d.get("anchor_left", 0.0))
	if d.has("anchor_top"):
		control.anchor_top = float(d.get("anchor_top", 0.0))
	if d.has("anchor_right"):
		control.anchor_right = float(d.get("anchor_right", 0.0))
	if d.has("anchor_bottom"):
		control.anchor_bottom = float(d.get("anchor_bottom", 0.0))
	if d.has("offset_left"):
		control.offset_left = float(d.get("offset_left", 0.0))
	if d.has("offset_top"):
		control.offset_top = float(d.get("offset_top", 0.0))
	if d.has("offset_right"):
		control.offset_right = float(d.get("offset_right", 0.0))
	if d.has("offset_bottom"):
		control.offset_bottom = float(d.get("offset_bottom", 0.0))
	if d.has("grow_horizontal"):
		control.grow_horizontal = int(d.get("grow_horizontal", 0))
	if d.has("grow_vertical"):
		control.grow_vertical = int(d.get("grow_vertical", 0))
	if d.has("size_flags_horizontal"):
		control.size_flags_horizontal = int(d.get("size_flags_horizontal", 0))
	if d.has("size_flags_vertical"):
		control.size_flags_vertical = int(d.get("size_flags_vertical", 0))
	if d.has("stretch_ratio"):
		control.size_flags_stretch_ratio = float(d.get("stretch_ratio", 1.0))
	if d.has("custom_minimum_size"):
		control.custom_minimum_size = d.get("custom_minimum_size") as Vector2
	if d.has("clip_contents"):
		control.clip_contents = d.get("clip_contents") == true
	if d.has("size"):
		control.set_size(d.get("size") as Vector2)
	if d.has("position"):
		control.set_position(d.get("position") as Vector2)


static func _read_anchor_dict(control: Control) -> Dictionary:
	return {
		"anchor_left": control.anchor_left,
		"anchor_top": control.anchor_top,
		"anchor_right": control.anchor_right,
		"anchor_bottom": control.anchor_bottom,
		"offset_left": control.offset_left,
		"offset_top": control.offset_top,
		"offset_right": control.offset_right,
		"offset_bottom": control.offset_bottom,
	}


static func _write_anchor_dict(control: Control, d: Dictionary) -> void:
	control.anchor_left = float(d.get("anchor_left", control.anchor_left))
	control.anchor_top = float(d.get("anchor_top", control.anchor_top))
	control.anchor_right = float(d.get("anchor_right", control.anchor_right))
	control.anchor_bottom = float(d.get("anchor_bottom", control.anchor_bottom))
	control.offset_left = float(d.get("offset_left", control.offset_left))
	control.offset_top = float(d.get("offset_top", control.offset_top))
	control.offset_right = float(d.get("offset_right", control.offset_right))
	control.offset_bottom = float(d.get("offset_bottom", control.offset_bottom))


static func _write_child_flags(control: Control, d: Dictionary) -> void:
	if d.has("size_flags_horizontal"):
		control.size_flags_horizontal = int(d.get("size_flags_horizontal", 0))
	if d.has("size_flags_vertical"):
		control.size_flags_vertical = int(d.get("size_flags_vertical", 0))
	if d.has("stretch_ratio"):
		control.size_flags_stretch_ratio = float(d.get("stretch_ratio", 1.0))


static func _theme_write(theme: Theme, item: Dictionary, undo: bool) -> void:
	var kind: String = str(item.get("kind", ""))
	var name_s: String = str(item.get("name", ""))
	var type_s: String = str(item.get("theme_type", ""))
	var existed: bool = item.get("existed", false) == true
	if kind == "stylebox":
		if undo:
			if existed:
				theme.set_stylebox(name_s, type_s, item.get("old") as StyleBox)
			else:
				theme.clear_stylebox(name_s, type_s)
		else:
			theme.set_stylebox(name_s, type_s, item.get("neu") as StyleBox)
	elif kind == "font":
		if undo:
			if existed:
				theme.set_font(name_s, type_s, item.get("old") as Font)
			else:
				theme.clear_font(name_s, type_s)
		else:
			theme.set_font(name_s, type_s, item.get("neu") as Font)
	elif kind == "font_size":
		if undo:
			if existed:
				theme.set_font_size(name_s, type_s, int(item.get("old", 0)))
			else:
				theme.clear_font_size(name_s, type_s)
		else:
			theme.set_font_size(name_s, type_s, int(item.get("neu", 0)))
	elif kind == "color":
		if undo:
			if existed:
				theme.set_color(name_s, type_s, item.get("old") as Color)
			else:
				theme.clear_color(name_s, type_s)
		else:
			theme.set_color(name_s, type_s, item.get("neu") as Color)
	elif kind == "constant":
		if undo:
			if existed:
				theme.set_constant(name_s, type_s, int(item.get("old", 0)))
			else:
				theme.clear_constant(name_s, type_s)
		else:
			theme.set_constant(name_s, type_s, int(item.get("neu", 0)))


static func _override_write(control: Control, item: Dictionary, undo: bool) -> void:
	var kind: String = str(item.get("kind", ""))
	var name_s: String = str(item.get("name", ""))
	if undo:
		if item.get("had", false) == true:
			if kind == "stylebox":
				control.add_theme_stylebox_override(name_s, item.get("old") as StyleBox)
			elif kind == "font":
				control.add_theme_font_override(name_s, item.get("old") as Font)
			elif kind == "font_size":
				control.add_theme_font_size_override(name_s, int(item.get("old", 0)))
			elif kind == "color":
				control.add_theme_color_override(name_s, item.get("old") as Color)
			elif kind == "constant":
				control.add_theme_constant_override(name_s, int(item.get("old", 0)))
		else:
			if kind == "stylebox":
				control.remove_theme_stylebox_override(name_s)
			elif kind == "font":
				control.remove_theme_font_override(name_s)
			elif kind == "font_size":
				control.remove_theme_font_size_override(name_s)
			elif kind == "color":
				control.remove_theme_color_override(name_s)
			elif kind == "constant":
				control.remove_theme_constant_override(name_s)
		return
	if kind == "stylebox":
		control.add_theme_stylebox_override(name_s, item.get("neu") as StyleBox)
	elif kind == "font":
		control.add_theme_font_override(name_s, item.get("neu") as Font)
	elif kind == "font_size":
		control.add_theme_font_size_override(name_s, int(item.get("neu", 0)))
	elif kind == "color":
		control.add_theme_color_override(name_s, item.get("neu") as Color)
	elif kind == "constant":
		control.add_theme_constant_override(name_s, int(item.get("neu", 0)))


func _flags_from_params(params: Dictionary) -> Dictionary:
	var out: Dictionary = {}
	if params.has("size_flags_horizontal"):
		out["size_flags_horizontal"] = int(params.get("size_flags_horizontal", 0))
	if params.has("size_flags_vertical"):
		out["size_flags_vertical"] = int(params.get("size_flags_vertical", 0))
	if params.has("stretch_ratio"):
		out["stretch_ratio"] = float(params.get("stretch_ratio", 1.0))
	if params.has("grow_horizontal"):
		out["grow_horizontal"] = int(params.get("grow_horizontal", 0))
	if params.has("grow_vertical"):
		out["grow_vertical"] = int(params.get("grow_vertical", 0))
	if params.has("custom_minimum_size"):
		out["custom_minimum_size"] = _vec2_param(params, "custom_minimum_size")
	if params.has("size"):
		out["size"] = _vec2_param(params, "size")
	if params.has("offset_left"):
		out["offset_left"] = float(params.get("offset_left", 0.0))
	if params.has("offset_top"):
		out["offset_top"] = float(params.get("offset_top", 0.0))
	if params.has("offset_right"):
		out["offset_right"] = float(params.get("offset_right", 0.0))
	if params.has("offset_bottom"):
		out["offset_bottom"] = float(params.get("offset_bottom", 0.0))
	if params.has("clip_contents"):
		out["clip_contents"] = params.get("clip_contents") == true
	return out


func _anchor_from_params(params: Dictionary, control: Control) -> Dictionary:
	return {
		"anchor_left": float(params.get("anchor_left", control.anchor_left)),
		"anchor_top": float(params.get("anchor_top", control.anchor_top)),
		"anchor_right": float(params.get("anchor_right", control.anchor_right)),
		"anchor_bottom": float(params.get("anchor_bottom", control.anchor_bottom)),
		"offset_left": float(params.get("offset_left", control.offset_left)),
		"offset_top": float(params.get("offset_top", control.offset_top)),
		"offset_right": float(params.get("offset_right", control.offset_right)),
		"offset_bottom": float(params.get("offset_bottom", control.offset_bottom)),
	}


func _plan_theme_items(command_id: String, theme: Theme, params: Dictionary) -> Dictionary:
	var items: Array[Dictionary] = []
	var boxes_v: Variant = params.get("styleboxes", [])
	if typeof(boxes_v) == TYPE_ARRAY:
		for item_v: Variant in boxes_v:
			if typeof(item_v) != TYPE_DICTIONARY:
				return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "stylebox item must be an object", "params.styleboxes")
			var row: Dictionary = item_v
			var res: Resource = _load_res(str(row.get("resource", "")))
			if res == null or not (res is StyleBox):
				return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "stylebox resource must be StyleBox", "params.styleboxes")
			var name_s: String = str(row.get("name", ""))
			var type_s: String = str(row.get("theme_type", ""))
			var existed: bool = theme.has_stylebox(name_s, type_s)
			items.append({
				"kind": "stylebox",
				"name": name_s,
				"theme_type": type_s,
				"existed": existed,
				"old": null,
				"neu": res as StyleBox,
			})
	var fonts_v: Variant = params.get("fonts", [])
	if typeof(fonts_v) == TYPE_ARRAY:
		for item_v2: Variant in fonts_v:
			if typeof(item_v2) != TYPE_DICTIONARY:
				return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "font item must be an object", "params.fonts")
			var frow: Dictionary = item_v2
			var fres: Resource = _load_res(str(frow.get("resource", "")))
			if fres == null or not (fres is Font):
				return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "font resource must be Font", "params.fonts")
			var fname: String = str(frow.get("name", ""))
			var ftype: String = str(frow.get("theme_type", ""))
			var fexisted: bool = theme.has_font(fname, ftype)
			items.append({
				"kind": "font",
				"name": fname,
				"theme_type": ftype,
				"existed": fexisted,
				"old": theme.get_font(fname, ftype) if fexisted else null,
				"neu": fres as Font,
			})
	var sizes_v: Variant = params.get("font_sizes", [])
	if typeof(sizes_v) == TYPE_ARRAY:
		for item_v3: Variant in sizes_v:
			if typeof(item_v3) != TYPE_DICTIONARY:
				return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "font_size item must be an object", "params.font_sizes")
			var srow: Dictionary = item_v3
			var sname: String = str(srow.get("name", ""))
			var stype: String = str(srow.get("theme_type", ""))
			var sexisted: bool = theme.has_font_size(sname, stype)
			items.append({
				"kind": "font_size",
				"name": sname,
				"theme_type": stype,
				"existed": sexisted,
				"old": theme.get_font_size(sname, stype) if sexisted else 0,
				"neu": int(srow.get("size", 16)),
			})
	var colors_v: Variant = params.get("colors", [])
	if typeof(colors_v) == TYPE_ARRAY:
		for item_v4: Variant in colors_v:
			if typeof(item_v4) != TYPE_DICTIONARY:
				return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "color item must be an object", "params.colors")
			var crow: Dictionary = item_v4
			var decoded: Dictionary = _codec.decode(crow.get("color"), "params.colors/color")
			if decoded.get("ok", false) != true:
				return _fail_enc(command_id, decoded)
			if str(decoded.get("type", "")) != "Color":
				return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "theme color must be Color", "params.colors")
			var cname: String = str(crow.get("name", ""))
			var ctype: String = str(crow.get("theme_type", ""))
			var cexisted: bool = theme.has_color(cname, ctype)
			items.append({
				"kind": "color",
				"name": cname,
				"theme_type": ctype,
				"existed": cexisted,
				"old": theme.get_color(cname, ctype) if cexisted else Color.WHITE,
				"neu": decoded.get("value"),
			})
	var consts_v: Variant = params.get("constants", [])
	if typeof(consts_v) == TYPE_ARRAY:
		for item_v5: Variant in consts_v:
			if typeof(item_v5) != TYPE_DICTIONARY:
				return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "constant item must be an object", "params.constants")
			var krow: Dictionary = item_v5
			var kname: String = str(krow.get("name", ""))
			var ktype: String = str(krow.get("theme_type", ""))
			var kexisted: bool = theme.has_constant(kname, ktype)
			items.append({
				"kind": "constant",
				"name": kname,
				"theme_type": ktype,
				"existed": kexisted,
				"old": theme.get_constant(kname, ktype) if kexisted else 0,
				"neu": int(krow.get("value", 0)),
			})
	return {"ok": true, "items": items}


func _plan_overrides(command_id: String, control: Control, params: Dictionary) -> Dictionary:
	var items: Array[Dictionary] = []
	var raw: Variant = params.get("overrides", [])
	if typeof(raw) != TYPE_ARRAY:
		return {"ok": true, "items": items}
	for item_v: Variant in raw:
		if typeof(item_v) != TYPE_DICTIONARY:
			return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "override item must be an object", "params.overrides")
		var row: Dictionary = item_v
		var kind: String = str(row.get("kind", ""))
		var name_s: String = str(row.get("name", ""))
		var rec: Dictionary = {"kind": kind, "name": name_s}
		if kind == "stylebox":
			var res: Resource = _load_res(str(row.get("resource", "")))
			if res == null or not (res is StyleBox):
				return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "override stylebox must be StyleBox", "params.overrides")
			rec["had"] = control.has_theme_stylebox_override(name_s)
			if rec["had"] == true:
				rec["old"] = control.get_theme_stylebox(name_s)
			rec["neu"] = res as StyleBox
		elif kind == "font":
			var fres: Resource = _load_res(str(row.get("resource", "")))
			if fres == null or not (fres is Font):
				return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "override font must be Font", "params.overrides")
			rec["had"] = control.has_theme_font_override(name_s)
			if rec["had"] == true:
				rec["old"] = control.get_theme_font(name_s)
			rec["neu"] = fres as Font
		elif kind == "font_size":
			rec["had"] = control.has_theme_font_size_override(name_s)
			if rec["had"] == true:
				rec["old"] = control.get_theme_font_size(name_s)
			rec["neu"] = int(row.get("value", 16))
		elif kind == "color":
			var decoded: Dictionary = _codec.decode(row.get("color"), "params.overrides/color")
			if decoded.get("ok", false) != true:
				return _fail_enc(command_id, decoded)
			rec["had"] = control.has_theme_color_override(name_s)
			if rec["had"] == true:
				rec["old"] = control.get_theme_color(name_s)
			rec["neu"] = decoded.get("value")
		elif kind == "constant":
			rec["had"] = control.has_theme_constant_override(name_s)
			if rec["had"] == true:
				rec["old"] = control.get_theme_constant(name_s)
			rec["neu"] = int(row.get("value", 0))
		else:
			return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "unknown override kind", "params.overrides")
		items.append(rec)
	return {"ok": true, "items": items}


func _plan_children(command_id: String, edited: Node, params: Dictionary) -> Dictionary:
	var nodes: Array[Control] = []
	var olds: Array[Dictionary] = []
	var neus: Array[Dictionary] = []
	var raw: Variant = params.get("children", [])
	if typeof(raw) != TYPE_ARRAY:
		return {"ok": true, "nodes": nodes, "old": olds, "neu": neus}
	for item_v: Variant in raw:
		if typeof(item_v) != TYPE_DICTIONARY:
			return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "layout child must be an object", "params.children")
		var row: Dictionary = item_v
		var node: Node = _resolve(edited, str(row.get("node_path", "")))
		if node == null or not (node is Control):
			return _unverified(command_id, "layout child Control not found")
		var child: Control = node as Control
		nodes.append(child)
		olds.append({
			"size_flags_horizontal": child.size_flags_horizontal,
			"size_flags_vertical": child.size_flags_vertical,
			"stretch_ratio": child.size_flags_stretch_ratio,
		})
		var neu: Dictionary = {}
		if row.has("size_flags_horizontal"):
			neu["size_flags_horizontal"] = int(row.get("size_flags_horizontal", 0))
		if row.has("size_flags_vertical"):
			neu["size_flags_vertical"] = int(row.get("size_flags_vertical", 0))
		if row.has("stretch_ratio"):
			neu["stretch_ratio"] = float(row.get("stretch_ratio", 1.0))
		neus.append(neu)
	return {"ok": true, "nodes": nodes, "old": olds, "neu": neus}


func _fill_margins(stroke: LayoutStroke, control: Control, params: Dictionary) -> void:
	var keys: PackedStringArray = PackedStringArray(["margin_left", "margin_top", "margin_right", "margin_bottom"])
	for key_s: String in keys:
		if not params.has(key_s):
			continue
		stroke.old_margins[key_s] = control.get_theme_constant(key_s)
		stroke.new_margins[key_s] = int(params.get(key_s, 0))


func _collect_rects(edited: Node, parent: Control) -> Array:
	var out: Array = []
	var i: int = 0
	while i < parent.get_child_count():
		var child: Node = parent.get_child(i)
		if child is Control:
			var c: Control = child as Control
			var r: Rect2 = c.get_rect()
			var gr: Rect2 = c.get_global_rect()
			var min_s: Vector2 = c.get_combined_minimum_size()
			out.append({
				"node_path": _rel_path(edited, c),
				"class_name": c.get_class(),
				"rect": _xywh(r),
				"global_rect": _xywh(gr),
				"min_size": {"x" : min_s.x, "y": min_s.y},
				"overflow": min_s.x > r.size.x + 0.5 or min_s.y > r.size.y + 0.5,
				"clip_contents": c.clip_contents,
			})
		i += 1
	return out


func _audit_rects(parent: Control, rows: Array) -> Dictionary:
	var overlap: bool = false
	var cutoff: bool = false
	var pr: Rect2 = parent.get_rect()
	var i: int = 0
	while i < rows.size():
		var a: Dictionary = rows[i]
		var ra: Rect2 = _rect_from(a.get("rect"))
		if not _inside(pr, ra):
			cutoff = true
		var j: int = i + 1
		while j < rows.size():
			var b: Dictionary = rows[j]
			var rb: Rect2 = _rect_from(b.get("rect"))
			if ra.intersects(rb):
				var inter: Rect2 = ra.intersection(rb)
				if inter.size.x > 0.5 and inter.size.y > 0.5:
					overlap = true
			j += 1
		i += 1
	return {"overlap": overlap, "cutoff": cutoff}


func _flush_sort(node: Node) -> void:
	if node is Container:
		var box: Container = node as Container
		box.queue_sort()
		box.notification(Container.NOTIFICATION_SORT_CHILDREN)
	var i: int = 0
	while i < node.get_child_count():
		_flush_sort(node.get_child(i))
		i += 1


func _theme_colors(control: Control, theme: Theme) -> Dictionary:
	var fg: Color = Color.WHITE
	var bg: Color = Color.BLACK
	if theme.has_color("font_color", "Label"):
		fg = theme.get_color("font_color", "Label")
	elif control.has_theme_color("font_color", "Label"):
		fg = control.get_theme_color("font_color", "Label")
	if control.has_theme_stylebox("panel", "Panel"):
		var box: StyleBox = control.get_theme_stylebox("panel", "Panel")
		if box is StyleBoxFlat:
			bg = (box as StyleBoxFlat).bg_color
	return {
		"fg": {"r": fg.r, "g": fg.g, "b": fg.b, "a": fg.a},
		"bg": {"r": bg.r, "g": bg.g, "b": bg.b, "a": bg.a},
	}


func _theme_font_class(control: Control, theme: Theme) -> String:
	var font: Font = null
	if theme.has_font("font", "Label"):
		font = theme.get_font("font", "Label")
	elif control.has_theme_font("font", "Label"):
		font = control.get_theme_font("font", "Label")
	if font == null:
		return ""
	return font.get_class()


func _theme_has_stylebox(control: Control, theme: Theme) -> bool:
	if theme.has_stylebox("panel", "Panel"):
		return true
	return control.has_theme_stylebox("panel", "Panel")


func _theme_stylebox_class(control: Control, theme: Theme) -> String:
	var box: StyleBox = null
	if control.has_theme_stylebox("panel", "Panel"):
		box = control.get_theme_stylebox("panel", "Panel")
	if box == null:
		return ""
	return box.get_class()


func _load_theme(command_id: String, theme_path: String) -> Dictionary:
	var jail: Dictionary = _meta.jail(command_id, theme_path)
	if jail.get("ok", false) != true:
		return jail
	var res: Resource = _load_res(theme_path)
	if res == null or not (res is Theme):
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "theme is not a Theme resource", "params.theme")
	return {"ok": true, "theme": res as Theme}


func _persist_res(command_id: String, res: Resource, res_path: String) -> Dictionary:
	var jail: Dictionary = _meta.jail(command_id, res_path)
	if jail.get("ok", false) != true:
		return jail
	if not _is_external_res(res_path):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "Theme persist requires .tres or .res", res_path)
	var dir_err: Error = _meta.ensure_parent_dir(res_path)
	if dir_err != OK:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "cannot create resource directory", res_path)
	var save_err: Error = ResourceSaver.save(res, res_path)
	if save_err != OK:
		return _unverified(command_id, "ResourceSaver.save failed: %s" % error_string(save_err))
	_meta.refresh_fs(res_path)
	if not FileAccess.file_exists(res_path):
		return _unverified(command_id, "Theme file missing after save")
	var disk: String = _meta.disk_hash(res_path)
	if disk.is_empty() or disk == "missing":
		return _unverified(command_id, "Theme disk hash missing after save")
	return {"ok": true, "disk_hash": disk, "path": res_path}


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


func _preset_id(preset_s: String) -> int:
	if preset_s == PRESET_TOP_LEFT:
		return Control.PRESET_TOP_LEFT
	if preset_s == PRESET_CENTER:
		return Control.PRESET_CENTER
	if preset_s == PRESET_FULL_RECT:
		return Control.PRESET_FULL_RECT
	if preset_s == PRESET_BOTTOM_WIDE:
		return Control.PRESET_BOTTOM_WIDE
	return -1


func _container_parent(node: Node) -> bool:
	var parent: Node = node.get_parent()
	return parent is Container


func _is_external_res(path_s: String) -> bool:
	return (path_s.ends_with(".tres") or path_s.ends_with(".res")) and not path_s.contains("::")


func _has_prop(obj: Object, name_s: String) -> bool:
	for item_v: Variant in obj.get_property_list():
		if item_v is Dictionary and str((item_v as Dictionary).get("name", "")) == name_s:
			return true
	return false


func _rel_path(root: Node, node: Node) -> String:
	if root == null or node == null:
		return ""
	if node == root:
		return "."
	return str(root.get_path_to(node))


func _xywh(r: Rect2) -> Dictionary:
	return {"x": r.position.x, "y": r.position.y, "w": r.size.x, "h": r.size.y}


func _rect_from(raw: Variant) -> Rect2:
	if raw is Dictionary:
		var d: Dictionary = raw
		return Rect2(float(d.get("x", 0.0)), float(d.get("y", 0.0)), float(d.get("w", 0.0)), float(d.get("h", 0.0)))
	return Rect2()


func _inside(parent_r: Rect2, child_r: Rect2) -> bool:
	var eps: float = 0.5
	return (
		child_r.position.x >= parent_r.position.x - eps
		and child_r.position.y >= parent_r.position.y - eps
		and child_r.end.x <= parent_r.end.x + eps
		and child_r.end.y <= parent_r.end.y + eps
	)


func _vec2_param(params: Dictionary, key: String) -> Vector2:
	var raw: Variant = params.get(key)
	if raw is Dictionary:
		var d: Dictionary = raw
		return Vector2(float(d.get("x", 0.0)), float(d.get("y", 0.0)))
	return Vector2.ZERO


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

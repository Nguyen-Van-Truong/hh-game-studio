class_name HHAgentOverlay
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")
const _IdentityScript: GDScript = preload("res://addons/hh_agent/core/hh_identity.gd")
const _MetaScript: GDScript = preload("res://addons/hh_agent/core/hh_scene_meta.gd")
const _StoreScript: GDScript = preload("res://addons/hh_agent/core/hh_activity_store.gd")

## Presentation-only viewport overlay + semantic drag replay.
## Draws from a live model (rects/labels/cursor/ghost). Never writes .tscn.
## Replay never calls node.add / property.set / the command router.

static var _current: HHAgentOverlay

var _errors: HHAgentErrors = HHAgentErrors.new()
var _identity: HHAgentIdentity = HHAgentIdentity.new()
var _meta: HHAgentSceneMeta = HHAgentSceneMeta.new()
var _mode: String = HHAgentConstants.MODE_WATCH
var _cursor: Vector2 = Vector2.ZERO
var _highlights: Array[Dictionary] = []
var _ghost: Array[Vector2] = []
var _framed: String = ""
var _last_replay: Dictionary = {"action": "", "ms": 0, "drawn": false}
var _records: Dictionary = {}
var _last: Dictionary = {}
var _anim_active: bool = false
var _anim_t_ms: float = 0.0
var _anim_ms: int = 0
var _anim_points: Array[Vector2] = []
var _lane_color_html: String = "#3db8ff"


static func current() -> HHAgentOverlay:
	return _current


func attach() -> void:
	_current = self


func detach() -> void:
	if _current == self:
		_current = null
	_anim_active = false
	_highlights.clear()
	_ghost.clear()
	_records.clear()
	_last = {}


func set_mode(mode: String) -> void:
	if mode == HHAgentConstants.MODE_FAST:
		_mode = HHAgentConstants.MODE_FAST
		_anim_active = false
	else:
		_mode = HHAgentConstants.MODE_WATCH


func is_draw_enabled() -> bool:
	return _mode == HHAgentConstants.MODE_WATCH and not _headless()


func is_draw_enabled_for(envelope: Dictionary) -> bool:
	return _mode_of(envelope) == HHAgentConstants.MODE_WATCH and not _headless()


func handle(
	command_id: String,
	method: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
	envelope: Dictionary,
) -> Dictionary:
	var def: Dictionary = actions.lookup(method, action)
	var post: String = str(def.get("postcondition", ""))
	if method == "godot.review" and action == "replay":
		return _replay(command_id, params, envelope, post)
	if method != "godot.editor":
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not an editor presentation verb", "")
	if action == "frame_view":
		return _frame_view(command_id, params, envelope, post)
	if action == "replay":
		return _replay(command_id, params, envelope, post)
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "editor.%s is not an overlay verb" % action, "")


func after_success(
	result: Dictionary,
	method: String,
	action: String,
	params: Dictionary,
	envelope: Dictionary,
) -> void:
	if result.get("ok", false) != true:
		return
	if not is_presentable_mutate(method, action):
		return
	var record: Dictionary = event_from_mutate(method, action, params, result)
	if record.is_empty():
		return
	record_event(record)


func record_event(record: Dictionary) -> void:
	var cid: String = str(record.get("command_id", ""))
	if not cid.is_empty():
		_records[cid] = record
	_last = record
	var store: HHAgentActivityStore = HHAgentActivityStore.current()
	if store != null:
		store.mark_replay_ready()


func event_from_mutate(method: String, action: String, params: Dictionary, result: Dictionary) -> Dictionary:
	return _record_from_mutate(method, action, params, result)


func apply_event(record: Dictionary, start_anim: bool, envelope: Dictionary) -> void:
	if record.is_empty():
		return
	_apply_record(record, true)
	if start_anim and is_draw_enabled_for(envelope):
		_start_anim(record, _duration_ms(envelope))
	else:
		_anim_active = false


func clear_focus() -> void:
	_highlights.clear()
	_ghost.clear()
	_framed = ""
	_anim_active = false


func is_animating() -> bool:
	return _anim_active


func last_event() -> Dictionary:
	if _last.is_empty():
		return {}
	return _last.duplicate(true)


func set_lane_color(html: String) -> void:
	if html.is_empty():
		return
	_lane_color_html = html


func is_presentable_mutate(method: String, action: String) -> bool:
	return _is_presentable_mutate(method, action)


func replay_last() -> Dictionary:
	return _replay("", {"command_id": str(_last.get("command_id", ""))}, {}, "replay_started")


func snapshot(envelope: Dictionary = {}) -> Dictionary:
	var mode_s: String = _mode_of(envelope)
	var enabled: bool = mode_s == HHAgentConstants.MODE_WATCH and not _headless()
	var view: Dictionary = _view_info()
	var edited: Node = EditorInterface.get_edited_scene_root()
	var scene: String = ""
	if edited != null:
		scene = str(edited.scene_file_path)
	elif not _last.is_empty():
		scene = str(_last.get("scene", ""))
	return _redact({
		"enabled": enabled,
		"mode": mode_s,
		"cursor": {"x": _cursor.x, "y": _cursor.y},
		"highlights": _highlights_json(),
		"ghost_path": _points_json(_ghost),
		"last_replay": {
			"action": str(_last_replay.get("action", "")),
			"ms": int(_last_replay.get("ms", 0)),
			"drawn": _last_replay.get("drawn", false) == true,
		},
		"framed": _framed,
		"scene": scene,
		"history_version": str(_meta.history_version(edited)),
		"history_count": _history_count(edited),
		"disk_hash": _meta.disk_hash(scene),
		"view": view,
	})


func tick(delta: float) -> bool:
	if not _anim_active:
		return false
	if not is_draw_enabled():
		_anim_active = false
		return false
	_anim_t_ms += delta * 1000.0
	var u: float = 1.0
	if _anim_ms > 0:
		u = clampf(_anim_t_ms / float(_anim_ms), 0.0, 1.0)
	_cursor = _sample_polyline(_anim_points, u)
	if u >= 1.0:
		_anim_active = false
		if not _anim_points.is_empty():
			_cursor = _anim_points[_anim_points.size() - 1]
	return true


func draw_canvas(overlay: Control) -> void:
	if overlay == null or not is_draw_enabled():
		return
	var xform: Transform2D = _canvas_xform()
	var scale_px: float = _stroke_px(overlay)
	_draw_ghost(overlay, xform, scale_px)
	_draw_highlights(overlay, xform, scale_px)
	_draw_cursor(overlay, xform, scale_px)


func draw_spatial(overlay: Control) -> void:
	if overlay == null or not is_draw_enabled():
		return
	var scale_px: float = _stroke_px(overlay)
	var i: int = 0
	while i < _highlights.size():
		var item: Dictionary = _highlights[i]
		if str(item.get("space", "world")) != "spatial":
			i += 1
			continue
		var origin: Vector3 = Vector3(
			float(item.get("sx", 0.0)),
			float(item.get("sy", 0.0)),
			float(item.get("sz", 0.0)),
		)
		var screen: Vector2 = _unproject(origin)
		_stroke_rect(overlay, Rect2(screen - Vector2(16, 16), Vector2(32, 32)), scale_px)
		_draw_label(overlay, screen + Vector2(8, -18), str(item.get("label", "")), scale_px)
		i += 1
	if _cursor != Vector2.ZERO:
		overlay.draw_circle(_cursor, 5.0 * scale_px, Color(1.0, 0.55, 0.12, 0.95))


func _frame_view(command_id: String, params: Dictionary, envelope: Dictionary, post: String) -> Dictionary:
	if post.is_empty():
		post = "view_framed_on_node"
	var scene: String = str(params.get("scene", ""))
	var opened: Dictionary = _ensure_scene(scene)
	if opened.get("ok", false) != true:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_UNVERIFIED,
			str(opened.get("message", "scene missing")),
			"params.scene",
		)
	var root: Node = opened.get("root") as Node
	var node: Node = _resolve_node(root, params)
	if node == null:
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "node not found", "params.node_path")
	var cheap: bool = not is_draw_enabled_for(envelope)
	_present_node(node, cheap)
	_framed = _identity.tree_path(node, root)
	var record: Dictionary = {
		"command_id": command_id,
		"action": "editor.frame_view",
		"method": "godot.editor",
		"scene": scene,
		"path": _framed,
		"uid": _identity.read_uid(node),
		"label": "%s %s" % [node.name, node.get_class()],
		"kind": "frame",
		"start": _world_center(node) - Vector2(48, 48),
		"end": _world_center(node),
	}
	_apply_record(record, false)
	_try_frame_camera(node, cheap)
	var checks: PackedStringArray = PackedStringArray()
	checks.append(post)
	var after: Dictionary = snapshot(envelope)
	after["framed"] = _framed
	after["node_path"] = _framed
	return _errors.ok_read(command_id, checks, after)


func _replay(command_id: String, params: Dictionary, envelope: Dictionary, post: String) -> Dictionary:
	if post.is_empty():
		post = "replay_started"
	var want: String = str(params.get("command_id", ""))
	var record: Dictionary = _lookup_record(want)
	var drawn: bool = is_draw_enabled_for(envelope) and not record.is_empty()
	var ms: int = 0
	var action_s: String = str(record.get("action", ""))
	if drawn:
		ms = _duration_ms(envelope)
		_apply_record(record, true)
		_start_anim(record, ms)
	elif not record.is_empty():
		_apply_record(record, true)
		_anim_active = false
	_last_replay = {"action": action_s, "ms": ms, "drawn": drawn}
	var checks: PackedStringArray = PackedStringArray()
	checks.append(post)
	var after: Dictionary = snapshot(envelope)
	after["last_replay"] = {
		"action": action_s,
		"ms": ms,
		"drawn": drawn,
	}
	after["replayed_command_id"] = want
	return _errors.ok_read(command_id, checks, after)


func _lookup_record(command_id: String) -> Dictionary:
	if not command_id.is_empty() and _records.has(command_id):
		var found_v: Variant = _records[command_id]
		if found_v is Dictionary:
			return found_v
	if not command_id.is_empty() and str(_last.get("command_id", "")) == command_id:
		return _last
	if not _last.is_empty():
		return _last
	return {}


func _record_from_mutate(method: String, action: String, params: Dictionary, result: Dictionary) -> Dictionary:
	var after_v: Variant = result.get("after", {})
	var after: Dictionary = after_v if after_v is Dictionary else {}
	var scene: String = str(params.get("scene", after.get("path", "")))
	var path_s: String = str(after.get("path", params.get("node_path", params.get("name", ""))))
	var uid: String = str(after.get("uid", params.get("uid", "")))
	var label: String = str(params.get("name", path_s.get_file()))
	var class_s: String = str(params.get("class_name", ""))
	if not class_s.is_empty():
		label = "%s %s" % [label, class_s]
	var end_p: Vector2 = _end_from_after(scene, path_s, uid, params)
	var start_p: Vector2 = _start_from_kind(method, action, params, end_p)
	var kind: String = action
	if method == "godot.resource" and action == "assign":
		kind = "asset_assign"
	elif method == "godot.property":
		kind = "property"
		var prop: String = str(params.get("property", ""))
		if prop == "position" or prop == "global_position" or prop == "transform" or prop == "rotation" or prop == "scale":
			kind = "transform"
	return {
		"command_id": str(result.get("command_id", "")),
		"action": ("%s.%s" % [method.trim_prefix("godot."), action]) if method.begins_with("godot.") else action,
		"method": method,
		"scene": scene,
		"path": path_s,
		"uid": uid,
		"label": label,
		"kind": kind,
		"property": str(params.get("property", "")),
		"start": start_p,
		"end": end_p,
	}


func _apply_record(record: Dictionary, _is_replay: bool) -> void:
	var end_p: Vector2 = _as_vec2(record.get("end", Vector2.ZERO))
	var start_p: Vector2 = _as_vec2(record.get("start", end_p))
	_cursor = end_p
	_ghost.clear()
	for point: Vector2 in _ghost_points(start_p, end_p):
		_ghost.append(point)
	_framed = str(record.get("path", ""))
	var rect: Rect2 = Rect2(end_p - Vector2(16, 16), Vector2(32, 32))
	var scene: String = str(record.get("scene", ""))
	var node: Node = _live_node(scene, str(record.get("path", "")), str(record.get("uid", "")))
	if node != null:
		rect = _world_rect(node)
		_cursor = rect.get_center()
		_framed = str(record.get("path", ""))
	_highlights.clear()
	var color_s: String = str(record.get("color", _lane_color_html))
	if color_s.is_empty():
		color_s = _lane_color_html
	_highlights.append({
		"path": str(record.get("path", "")),
		"uid": str(record.get("uid", "")),
		"label": str(record.get("label", record.get("path", ""))),
		"kind": str(record.get("kind", "bounds")),
		"color": color_s,
		"rect": {"x": rect.position.x, "y": rect.position.y, "w": rect.size.x, "h": rect.size.y},
		"space": "world",
	})


func _start_anim(record: Dictionary, ms: int) -> void:
	_anim_ms = ms
	_anim_t_ms = 0.0
	_anim_points.clear()
	for point: Vector2 in _ghost:
		_anim_points.append(point)
	if _anim_points.is_empty():
		_anim_points.append(_as_vec2(record.get("start", Vector2.ZERO)))
		_anim_points.append(_as_vec2(record.get("end", Vector2.ZERO)))
	_anim_active = _anim_ms > 0 and is_draw_enabled()
	if not _anim_points.is_empty():
		_cursor = _anim_points[0]


func _is_presentable_mutate(method: String, action: String) -> bool:
	if method == "godot.node":
		return (
			action == "add"
			or action == "reparent"
			or action == "rename"
			or action == "duplicate"
			or action == "instantiate"
		)
	if method == "godot.property":
		return action == "set" or action == "batch"
	if method == "godot.resource":
		return action == "assign"
	if method == "godot.script":
		return action == "attach"
	return false


func _end_from_after(scene: String, path_s: String, uid: String, params: Dictionary) -> Vector2:
	var node: Node = _live_node(scene, path_s, uid)
	if node != null:
		return _world_center(node)
	var value_v: Variant = params.get("value", {})
	if value_v is Dictionary:
		var inner_v: Variant = (value_v as Dictionary).get("value", {})
		if inner_v is Dictionary:
			var inner: Dictionary = inner_v
			if inner.has("x") and inner.has("y"):
				return Vector2(float(inner.get("x", 0.0)), float(inner.get("y", 0.0)))
	return Vector2.ZERO


func _start_from_kind(method: String, action: String, params: Dictionary, end_p: Vector2) -> Vector2:
	if method == "godot.resource" and action == "assign":
		return end_p + Vector2(-160, -24)
	if method == "godot.node" and action == "reparent":
		return end_p + Vector2(-80, -64)
	if method == "godot.property":
		if not _last.is_empty() and str(_last.get("path", "")) == str(params.get("node_path", "")):
			return _as_vec2(_last.get("end", end_p + Vector2(-48, 0)))
		return end_p + Vector2(-48, 0)
	return end_p + Vector2(-96, -72)


func _ghost_points(start_p: Vector2, end_p: Vector2) -> Array[Vector2]:
	var mid: Vector2 = start_p.lerp(end_p, 0.5) + Vector2(0, -36)
	var out: Array[Vector2] = []
	out.append(start_p)
	out.append(mid)
	out.append(end_p)
	return out


func _live_node(scene: String, path_s: String, uid: String) -> Node:
	var edited: Node = EditorInterface.get_edited_scene_root()
	if edited == null:
		return null
	if not scene.is_empty() and edited.scene_file_path != scene:
		return null
	if not uid.is_empty():
		var by_uid: Node = _find_uid(edited, uid)
		if by_uid != null:
			return by_uid
	if path_s.is_empty() or path_s == "." or path_s == edited.name:
		return edited
	return edited.get_node_or_null(NodePath(path_s))


func _ensure_scene(scene: String) -> Dictionary:
	if scene.is_empty() or scene.contains("..") or not scene.begins_with("res://"):
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


func _present_node(node: Node, cheap: bool) -> void:
	var selection: EditorSelection = EditorInterface.get_selection()
	if selection != null:
		selection.clear()
		selection.add_node(node)
	EditorInterface.edit_node(node)
	EditorInterface.inspect_object(node)
	if not cheap:
		EditorInterface.set_main_screen_editor("2D")


func _try_frame_camera(node: Node, cheap: bool) -> void:
	if cheap or node == null:
		return
	var main: VBoxContainer = EditorInterface.get_editor_main_screen()
	var editor: Node = _find_class(main, "CanvasItemEditor")
	if editor == null:
		return
	if editor.has_method("edit"):
		editor.call("edit", node)
	if editor.has_method("focus_over"):
		editor.call("focus_over")


func _find_class(root: Node, class_s: String) -> Node:
	if root == null:
		return null
	if root.get_class() == class_s:
		return root
	var i: int = 0
	while i < root.get_child_count():
		var found: Node = _find_class(root.get_child(i), class_s)
		if found != null:
			return found
		i += 1
	return null


func _world_rect(node: Node) -> Rect2:
	if node is Control:
		var ctrl: Control = node as Control
		return Rect2(ctrl.global_position, ctrl.size)
	if node is Node2D:
		var n2: Node2D = node as Node2D
		if n2.has_method("get_rect"):
			var local_v: Variant = n2.call("get_rect")
			if local_v is Rect2:
				var local: Rect2 = local_v
				if local.size.x > 0.0 and local.size.y > 0.0:
					return n2.get_global_transform() * local
		return Rect2(n2.global_position - Vector2(16, 16), Vector2(32, 32))
	if node is Node3D:
		var n3: Node3D = node as Node3D
		var screen: Vector2 = _unproject(n3.global_position)
		return Rect2(screen - Vector2(16, 16), Vector2(32, 32))
	return Rect2(-16, -16, 32, 32)


func _world_center(node: Node) -> Vector2:
	return _world_rect(node).get_center()


func _canvas_xform() -> Transform2D:
	if not EditorInterface.has_method("get_editor_viewport_2d"):
		return Transform2D.IDENTITY
	var vp_v: Variant = EditorInterface.call("get_editor_viewport_2d")
	if vp_v is Viewport:
		return (vp_v as Viewport).get_canvas_transform()
	return Transform2D.IDENTITY


func _unproject(world: Vector3) -> Vector2:
	if not EditorInterface.has_method("get_editor_viewport_3d"):
		return Vector2.ZERO
	var vp_v: Variant = EditorInterface.call("get_editor_viewport_3d", 0)
	if not (vp_v is Viewport):
		return Vector2.ZERO
	var cam: Camera3D = (vp_v as Viewport).get_camera_3d()
	if cam == null:
		return Vector2.ZERO
	return cam.unproject_position(world)


func _view_info() -> Dictionary:
	var xform: Transform2D = _canvas_xform()
	var zoom: float = xform.get_scale().x
	if zoom <= 0.0:
		zoom = 1.0
	var dpi: float = 1.0
	if DisplayServer.has_method("screen_get_scale"):
		dpi = float(DisplayServer.call("screen_get_scale"))
	if dpi <= 0.0:
		dpi = 1.0
	return {"space": "world", "zoom": zoom, "dpi_scale": dpi}


func _stroke_px(overlay: Control) -> float:
	var scale_px: float = 1.0
	if overlay != null:
		scale_px = maxf(1.0, overlay.get_theme_default_base_scale())
	var view: Dictionary = _view_info()
	scale_px *= maxf(1.0, float(view.get("dpi_scale", 1.0)))
	return scale_px


func _draw_ghost(overlay: Control, xform: Transform2D, scale_px: float) -> void:
	if _ghost.size() < 2:
		return
	var packed: PackedVector2Array = PackedVector2Array()
	var i: int = 0
	while i < _ghost.size():
		packed.append(xform * _ghost[i])
		i += 1
	overlay.draw_polyline(packed, Color(1.0, 0.72, 0.18, 0.85), 2.0 * scale_px, true)


func _draw_highlights(overlay: Control, xform: Transform2D, scale_px: float) -> void:
	var i: int = 0
	while i < _highlights.size():
		var item: Dictionary = _highlights[i]
		var rect_v: Variant = item.get("rect", {})
		var rect: Rect2 = Rect2(-16, -16, 32, 32)
		if rect_v is Dictionary:
			var rec: Dictionary = rect_v
			rect = Rect2(
				float(rec.get("x", 0.0)),
				float(rec.get("y", 0.0)),
				maxf(8.0, float(rec.get("w", 32.0))),
				maxf(8.0, float(rec.get("h", 32.0))),
			)
		var a: Vector2 = xform * rect.position
		var b: Vector2 = xform * (rect.position + Vector2(rect.size.x, 0.0))
		var c: Vector2 = xform * (rect.position + rect.size)
		var d: Vector2 = xform * (rect.position + Vector2(0.0, rect.size.y))
		var screen: Rect2 = Rect2(a, Vector2.ZERO)
		screen = screen.expand(b).expand(c).expand(d)
		var accent: Color = _color_of(item)
		_stroke_rect(overlay, screen.grow(2.0 * scale_px), scale_px, accent)
		_draw_label(overlay, screen.position + Vector2(4.0 * scale_px, -16.0 * scale_px), str(item.get("label", "")), scale_px)
		i += 1


func _draw_cursor(overlay: Control, xform: Transform2D, scale_px: float) -> void:
	var pos: Vector2 = xform * _cursor
	overlay.draw_circle(pos, 6.0 * scale_px, Color(1.0, 0.45, 0.08, 0.95))
	overlay.draw_circle(pos, 2.0 * scale_px, Color(1.0, 1.0, 1.0, 0.95))


func _color_of(item: Dictionary) -> Color:
	var html: String = str(item.get("color", _lane_color_html))
	if html.is_empty() or not html.begins_with("#"):
		return Color(0.2, 0.85, 1.0, 0.95)
	return Color.html(html)


func _stroke_rect(overlay: Control, rect: Rect2, scale_px: float, accent: Color = Color(0.2, 0.85, 1.0, 0.95)) -> void:
	var fill: Color = Color(accent.r, accent.g, accent.b, 0.12)
	overlay.draw_rect(rect, fill, true)
	overlay.draw_rect(rect, accent, false, 2.0 * scale_px)


func _draw_label(overlay: Control, pos: Vector2, text: String, scale_px: float) -> void:
	if text.is_empty():
		return
	var font: Font = overlay.get_theme_default_font()
	if font == null:
		return
	var size_i: int = int(round(12.0 * scale_px))
	if size_i < 10:
		size_i = 10
	overlay.draw_string(font, pos, text, HORIZONTAL_ALIGNMENT_LEFT, -1, size_i, Color(1.0, 1.0, 1.0, 0.95))


func _sample_polyline(points: Array[Vector2], u: float) -> Vector2:
	if points.is_empty():
		return Vector2.ZERO
	if points.size() == 1:
		return points[0]
	var t: float = clampf(u, 0.0, 1.0) * float(points.size() - 1)
	var i: int = mini(int(t), points.size() - 2)
	var f: float = t - float(i)
	return points[i].lerp(points[i + 1], f)


func _highlights_json() -> Array:
	var out: Array = []
	var i: int = 0
	while i < _highlights.size():
		out.append(_highlights[i].duplicate(true))
		i += 1
	return out


func _points_json(points: Array[Vector2]) -> Array:
	var out: Array = []
	var i: int = 0
	while i < points.size():
		out.append({"x": points[i].x, "y": points[i].y})
		i += 1
	return out


func _as_vec2(raw: Variant) -> Vector2:
	if typeof(raw) == TYPE_VECTOR2:
		return raw
	if raw is Dictionary:
		return Vector2(float((raw as Dictionary).get("x", 0.0)), float((raw as Dictionary).get("y", 0.0)))
	return Vector2.ZERO


func _history_count(root: Node) -> int:
	if root == null:
		return 0
	var mgr: EditorUndoRedoManager = EditorInterface.get_editor_undo_redo()
	if mgr == null:
		return 0
	var hid: int = _meta.history_id(root)
	if hid == 0 or not mgr.has_method("get_history_undo_redo"):
		return _meta.history_version(root)
	var ur: UndoRedo = mgr.get_history_undo_redo(hid)
	if ur == null:
		return 0
	if ur.has_method("get_history_count"):
		return int(ur.call("get_history_count"))
	return ur.get_version()


func _duration_ms(envelope: Dictionary) -> int:
	var ms: int = HHAgentConstants.OVERLAY_REPLAY_MS
	var pres_v: Variant = envelope.get("presentation", {})
	if pres_v is Dictionary and (pres_v as Dictionary).has("duration_ms"):
		ms = int((pres_v as Dictionary).get("duration_ms", ms))
	if ms < HHAgentConstants.OVERLAY_REPLAY_MIN_MS:
		ms = HHAgentConstants.OVERLAY_REPLAY_MIN_MS
	if ms > HHAgentConstants.OVERLAY_REPLAY_MAX_MS:
		ms = HHAgentConstants.OVERLAY_REPLAY_MAX_MS
	return ms


func _mode_of(envelope: Dictionary) -> String:
	var pres_v: Variant = envelope.get("presentation", {})
	if pres_v is Dictionary:
		var mode_s: String = str((pres_v as Dictionary).get("mode", ""))
		if mode_s == HHAgentConstants.MODE_FAST:
			return HHAgentConstants.MODE_FAST
		if mode_s == HHAgentConstants.MODE_WATCH:
			return HHAgentConstants.MODE_WATCH
	if _mode == HHAgentConstants.MODE_FAST:
		return HHAgentConstants.MODE_FAST
	var store: HHAgentActivityStore = HHAgentActivityStore.current()
	if store != null:
		return store.mode()
	return HHAgentConstants.MODE_WATCH


func _headless() -> bool:
	if DisplayServer.get_name() == "headless":
		return true
	if OS.has_feature("headless"):
		return true
	return false


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

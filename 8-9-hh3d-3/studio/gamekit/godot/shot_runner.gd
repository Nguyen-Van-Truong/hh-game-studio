extends SceneTree
## Capture viewport frames of a scene. The host (shot.py) passes captures, an optional
## input trace, and node paths. Each capture is saved after that frame has been processed
## and rendered. Return false from _process to keep running.

var _scene_path: String = ""
var _scene_root: Node = null
var _expect: PackedStringArray = PackedStringArray()
var _captures: Dictionary = {}
var _capture_count: int = 0
var _last_frame: int = 0
var _events: Dictionary = {}
var _tick: int = 0
var _capture_next: String = ""
var _capture_frame: int = -1
var _file_rows: Array = []
var _done: bool = false
var _width: int = 640
var _height: int = 360


const HH = preload("hhgk.gd")


func _initialize() -> void:
	var req_v: Variant = HH.read_request()
	if req_v == null or not (req_v is Dictionary):
		_fail("BAD_REQUEST", "missing or invalid --request file")
		return
	var req: Dictionary = req_v
	_scene_path = str(req.get("scene", ""))
	if _scene_path.is_empty():
		_fail("BAD_REQUEST", "scene missing")
		return
	if not ResourceLoader.exists(_scene_path):
		_fail("NOT_FOUND", "cannot load scene " + _scene_path)
		return
	var packed_v: Resource = ResourceLoader.load(_scene_path, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE)
	var packed: PackedScene = null
	if packed_v is PackedScene:
		packed = packed_v
	if packed == null:
		_fail("NOT_FOUND", "not a packed scene " + _scene_path)
		return
	_scene_root = packed.instantiate()
	if _scene_root == null:
		_fail("GODOT_FAILED", "cannot instantiate " + _scene_path)
		return
	_width = HH.variant_int(req.get("width", 640))
	_height = HH.variant_int(req.get("height", 360))
	root.mode = Window.MODE_WINDOWED
	root.content_scale_mode = Window.CONTENT_SCALE_MODE_DISABLED
	root.content_scale_factor = 1.0
	root.size = Vector2i(_width, _height)
	DisplayServer.window_set_size(Vector2i(_width, _height))
	if DisplayServer.has_method("window_set_ime_active"):
		DisplayServer.window_set_ime_active(false)
	root.add_child(_scene_root)
	current_scene = _scene_root
	if req.has("seed"):
		seed(HH.variant_int(req["seed"]))
	var expect_v: Variant = req.get("expect", [])
	if expect_v is Array:
		var expect_list: Array = expect_v
		for item: Variant in expect_list:
			var _added: bool = _expect.append(str(item))
	var caps: Variant = req.get("captures", [])
	if not (caps is Array):
		_fail("BAD_REQUEST", "no captures")
		return
	var cap_list: Array = caps
	if cap_list.is_empty():
		_fail("BAD_REQUEST", "no captures")
		return
	for cap_v: Variant in cap_list:
		if not (cap_v is Dictionary):
			_fail("BAD_REQUEST", "capture entry must be an object")
			return
		var entry: Dictionary = cap_v
		var frame_i: int = HH.variant_int(entry.get("frame", -1))
		var path: String = str(entry.get("path", ""))
		if frame_i < 0 or path.is_empty():
			_fail("BAD_REQUEST", "capture needs frame and path")
			return
		_captures[frame_i] = path
		if frame_i > _last_frame:
			_last_frame = frame_i
	_capture_count = _captures.size()
	var trace_v: Variant = req.get("trace", {})
	if trace_v is Dictionary:
		var trace_d: Dictionary = trace_v
		var evs: Variant = trace_d.get("events", [])
		if evs is Array:
			var ev_list: Array = evs
			for ev_v: Variant in ev_list:
				if not (ev_v is Dictionary):
					continue
				var ev: Dictionary = ev_v
				var fr: int = HH.variant_int(ev.get("frame", 0))
				if not _events.has(fr):
					_events[fr] = []
				var bucket: Array = _events[fr]
				bucket.append(ev)


func _process(_delta: float) -> bool:
	if _done:
		return true
	if _capture_next != "":
		var save_path: String = _capture_next
		var save_frame: int = _capture_frame
		_capture_next = ""
		if not _save(save_path, save_frame):
			return true
		if _file_rows.size() == _capture_count:
			_emit_ok()
			return true
	if _tick > _last_frame:
		_fail("GODOT_FAILED", "ended before every frame was captured")
		return true
	if _captures.has(_tick):
		_capture_next = str(_captures[_tick])
		_capture_frame = _tick
	_apply_trace(_tick)
	_tick += 1
	return false


func _apply_trace(frame_i: int) -> void:
	if not _events.has(frame_i):
		return
	var list: Array = _events[frame_i]
	for item: Variant in list:
		var ev: Dictionary = item
		var action_ev: InputEventAction = InputEventAction.new()
		action_ev.action = StringName(str(ev.get("action", "")))
		action_ev.pressed = HH.variant_bool(ev.get("pressed", false))
		if ev.has("strength"):
			action_ev.strength = HH.variant_float(ev["strength"])
		Input.parse_input_event(action_ev)
		Input.flush_buffered_events()


func _save(path: String, frame_i: int) -> bool:
	var tex: ViewportTexture = root.get_texture()
	if tex == null:
		_fail("GODOT_FAILED", "viewport has no texture")
		return false
	var img: Image = tex.get_image()
	if img == null or img.is_empty() or img.get_width() < 1 or img.get_height() < 1:
		_fail("GODOT_FAILED", "viewport image is empty")
		return false
	var err: int = img.save_png(path)
	if err != OK:
		_fail("GODOT_FAILED", "save_png failed: " + error_string(err))
		return false
	_file_rows.append({
		"frame": frame_i,
		"path": path,
		"width": img.get_width(),
		"height": img.get_height(),
	})
	return true


func _emit_ok() -> void:
	if _done:
		return
	_done = true
	var presence: Array = _collect_presence()
	_free_scene()
	var out: Dictionary = {
		"ok": true,
		"scene": _scene_path,
		"files": _file_rows,
		"presence": presence,
	}
	HH.emit(out)
	quit(0)


func _fail(code: String, detail: String) -> void:
	if _done:
		return
	_done = true
	_free_scene()
	HH.emit(HH.fail(code, detail))
	quit(3)


func _free_scene() -> void:
	current_scene = null
	if _scene_root != null and is_instance_valid(_scene_root):
		var node: Node = _scene_root
		_scene_root = null
		node.free()


func _collect_presence() -> Array:
	var out: Array = []
	for path: String in _expect:
		out.append(_presence(path))
	return out


func _presence(path: String) -> Dictionary:
	var node: Node = null if _scene_root == null else _scene_root.get_node_or_null(NodePath(path))
	var row: Dictionary = {
		"path": path,
		"exists": node != null,
		"visible_in_tree": false,
		"on_screen": false,
		"screen_rect": null,
	}
	if node == null:
		return row
	row["class"] = node.get_class()
	var vis: bool = _is_visible(node)
	row["visible_in_tree"] = vis
	if node is GPUParticles2D:
		var particles_2d: GPUParticles2D = node
		row["emitting"] = particles_2d.emitting
	elif node is GPUParticles3D:
		var particles_3d: GPUParticles3D = node
		row["emitting"] = particles_3d.emitting
	if node is Sprite2D:
		var sprite: Sprite2D = node
		var sprite_rect: Rect2 = _canvas_rect(sprite, sprite.get_rect())
		row["screen_rect"] = _rect_json(sprite_rect)
		row["on_screen"] = _rect_on_screen(sprite_rect, vis)
	elif node is AnimatedSprite2D:
		var anim_sprite: AnimatedSprite2D = node
		var anim_rect: Rect2 = _canvas_rect(anim_sprite, _animated_rect(anim_sprite))
		row["screen_rect"] = _rect_json(anim_rect)
		row["on_screen"] = _rect_on_screen(anim_rect, vis)
	elif node is Control:
		var control: Control = node
		var control_rect: Rect2 = control.get_global_rect()
		row["screen_rect"] = _rect_json(control_rect)
		row["on_screen"] = _rect_on_screen(control_rect, vis)
	elif node is CanvasItem:
		var canvas_item: CanvasItem = node
		var point: Vector2 = canvas_item.get_global_transform_with_canvas().origin
		row["screen_rect"] = [point.x, point.y, 0.0, 0.0]
		row["on_screen"] = _point_on_screen(point, vis)
	elif node is Node3D:
		var node_3d: Node3D = node
		_fill_node3d(row, node_3d, vis)
	return row


func _is_visible(node: Node) -> bool:
	if node is CanvasItem:
		var canvas_item: CanvasItem = node
		return canvas_item.is_visible_in_tree()
	if node is Node3D:
		var node_3d: Node3D = node
		return node_3d.is_visible_in_tree()
	return true


func _view() -> Rect2:
	return root.get_visible_rect()


func _rect_on_screen(rect: Rect2, visible: bool) -> bool:
	if not visible or rect.size.x <= 0.0 or rect.size.y <= 0.0:
		return false
	return rect.intersects(_view())


func _point_on_screen(point: Vector2, visible: bool) -> bool:
	if not visible:
		return false
	return _view().has_point(point)


# AnimatedSprite2D has no get_rect() in 4.7; mirror its internal rect from the current frame.
func _animated_rect(sprite: AnimatedSprite2D) -> Rect2:
	var frames: SpriteFrames = sprite.sprite_frames
	if frames == null or not frames.has_animation(sprite.animation):
		return Rect2()
	if sprite.frame < 0 or sprite.frame >= frames.get_frame_count(sprite.animation):
		return Rect2()
	var tex: Texture2D = frames.get_frame_texture(sprite.animation, sprite.frame)
	if tex == null:
		return Rect2()
	var size: Vector2 = tex.get_size()
	var pos: Vector2 = sprite.offset
	if sprite.centered:
		pos -= size / 2.0
	return Rect2(pos, size)


func _canvas_rect(item: CanvasItem, local: Rect2) -> Rect2:
	var xf: Transform2D = item.get_global_transform_with_canvas()
	var p0: Vector2 = xf * local.position
	var p1: Vector2 = xf * Vector2(local.position.x + local.size.x, local.position.y)
	var p2: Vector2 = xf * (local.position + local.size)
	var p3: Vector2 = xf * Vector2(local.position.x, local.position.y + local.size.y)
	var min_x: float = minf(minf(p0.x, p1.x), minf(p2.x, p3.x))
	var min_y: float = minf(minf(p0.y, p1.y), minf(p2.y, p3.y))
	var max_x: float = maxf(maxf(p0.x, p1.x), maxf(p2.x, p3.x))
	var max_y: float = maxf(maxf(p0.y, p1.y), maxf(p2.y, p3.y))
	return Rect2(min_x, min_y, max_x - min_x, max_y - min_y)


func _rect_json(rect: Rect2) -> Array:
	var out: Array = [rect.position.x, rect.position.y, rect.size.x, rect.size.y]
	return out


func _fill_node3d(row: Dictionary, node: Node3D, visible: bool) -> void:
	var cam: Camera3D = root.get_camera_3d()
	if cam == null:
		row["on_screen"] = false
		row["screen_rect"] = null
		return
	# A Node3D's origin can be off-screen while its mesh is visible (and the
	# origin can be on-screen while the mesh is entirely outside the viewport).
	# Project every corner of a VisualInstance3D's local AABB after applying its
	# global transform. Keep the origin-point fallback for empty/non-visual nodes.
	if node is VisualInstance3D:
		var visual: VisualInstance3D = node as VisualInstance3D
		var aabb: AABB = visual.get_aabb()
		if aabb.size.length_squared() > 0.0:
			row["presence_basis"] = "aabb_projection"
			var projected: Array[Vector2] = _project_aabb(cam, node.global_transform, aabb)
			if not projected.is_empty():
				var min_x: float = projected[0].x
				var min_y: float = projected[0].y
				var max_x: float = projected[0].x
				var max_y: float = projected[0].y
				for point: Vector2 in projected:
					min_x = minf(min_x, point.x)
					min_y = minf(min_y, point.y)
					max_x = maxf(max_x, point.x)
					max_y = maxf(max_y, point.y)
				var mesh_rect: Rect2 = Rect2(min_x, min_y, max_x - min_x, max_y - min_y)
				row["screen_rect"] = _rect_json(mesh_rect)
				var layer_visible: bool = (visual.layers & cam.cull_mask) != 0
				row["on_screen"] = _rect_on_screen(mesh_rect, visible and layer_visible)
				return
			# A non-empty visual entirely behind the camera has no screen bounds.
			row["screen_rect"] = null
			row["on_screen"] = false
			return
	# Empty AABB or a plain Node3D: report the origin as a point.
	var world: Vector3 = node.global_position
	var behind: bool = cam.is_position_behind(world)
	var screen: Vector2 = cam.unproject_position(world)
	row["screen_rect"] = [screen.x, screen.y, 0.0, 0.0]
	row["on_screen"] = visible and not behind and _point_on_screen(screen, true)
	row["presence_basis"] = "origin_point"


func _project_aabb(cam: Camera3D, transform: Transform3D, box: AABB) -> Array[Vector2]:
	var points: Array[Vector2] = []
	for i: int in range(8):
		var world_corner: Vector3 = transform * box.get_endpoint(i)
		if not cam.is_position_behind(world_corner):
			points.append(cam.unproject_position(world_corner))
	return points

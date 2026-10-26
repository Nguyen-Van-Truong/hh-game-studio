class_name DynamicCamera
extends Camera2D
## Dynamic multi-fighter framing & zoom Camera2D ported from Cam.as & PlayersKeeper.as (SF-M4).
## Computes bounding box of alive (or recently dead < 48 frames) fighters with margins:
## Left/Right ±25px, Top -35px, Bottom +15px + viewport padding +45px.
## Clamps target zoom in [1.85, 3.4] and target center position within map_bounds.

const MIN_ZOOM: float = 1.85
const MAX_ZOOM: float = 3.40

const MARGIN_LEFT: float = 25.0
const MARGIN_RIGHT: float = 25.0
const MARGIN_TOP: float = 35.0
const MARGIN_BOTTOM: float = 15.0
const VIEW_PADDING: float = 45.0

const DEAD_INCLUDE_FRAMES: float = 48.0
const REF_VIEW_WIDTH: float = 960.0
const REF_VIEW_HEIGHT: float = 540.0

var match_world: Node2D = null
var map_bounds: Rect2 = Rect2(-12.0, -110.0, 583.0, 510.0)
var show_all: bool = false

var target_position: Vector2 = Vector2(260.0, 180.0)
var target_zoom_scalar: float = 2.4
var current_zoom_scalar: float = 2.4

var screen_shake: float = 0.0
var _last_covered_pos: Vector2 = Vector2(260.0, 180.0)
var _dead_frame_timers: Dictionary = {} # instance_id -> frames_since_death


func _ready() -> void:
	enabled = true
	zoom = Vector2(current_zoom_scalar, current_zoom_scalar)


func reset_for_map(bounds: Rect2, initial_focus: Vector2 = Vector2.ZERO) -> void:
	map_bounds = bounds
	_dead_frame_timers.clear()
	if initial_focus != Vector2.ZERO:
		_last_covered_pos = initial_focus
	else:
		_last_covered_pos = bounds.get_center()
	target_position = _last_covered_pos
	target_zoom_scalar = 2.4
	current_zoom_scalar = 2.4
	global_position = target_position
	zoom = Vector2(current_zoom_scalar, current_zoom_scalar)
	offset = Vector2.ZERO
	screen_shake = 0.0


func add_screen_shake(intensity: float) -> void:
	screen_shake = clampf(screen_shake + intensity, 0.0, 14.0)


func trigger_shake(intensity: float) -> void:
	add_screen_shake(intensity)


func step_camera(step_24hz: float, fighters: Array = []) -> void:
	if match_world != null and is_instance_valid(match_world):
		var ml: Variant = match_world.get("map_loader")
		if ml != null and is_instance_valid(ml):
			var mb: Variant = ml.get("map_bounds")
			if typeof(mb) == TYPE_RECT2:
				map_bounds = mb as Rect2
		if fighters.is_empty():
			var mw_fighters: Variant = match_world.get("fighters")
			if typeof(mw_fighters) == TYPE_ARRAY:
				fighters = mw_fighters as Array

	var tracked_points: Array[Vector2] = []
	for f_var: Variant in fighters:
		if not (f_var is Node2D) or not is_instance_valid(f_var):
			continue
		var f: Node2D = f_var as Node2D
		var iid: int = f.get_instance_id()
		var dead: bool = bool(f.get("is_dead"))
		if not dead:
			_dead_frame_timers[iid] = 0.0
			tracked_points.append(f.global_position)
			_last_covered_pos = f.global_position
		else:
			var t_dead: float = float(_dead_frame_timers.get(iid, 0.0)) + step_24hz
			_dead_frame_timers[iid] = t_dead
			if t_dead < DEAD_INCLUDE_FRAMES:
				tracked_points.append(f.global_position)

	var cam_rect: Rect2
	if show_all:
		cam_rect = map_bounds
	elif tracked_points.is_empty():
		cam_rect = Rect2(
			_last_covered_pos.x - MARGIN_LEFT - VIEW_PADDING,
			_last_covered_pos.y - MARGIN_TOP - VIEW_PADDING,
			MARGIN_LEFT + MARGIN_RIGHT + VIEW_PADDING * 2.0,
			MARGIN_TOP + MARGIN_BOTTOM + VIEW_PADDING * 2.0
		)
	else:
		var min_x: float = INF
		var max_x: float = -INF
		var min_y: float = INF
		var max_y: float = -INF
		for pt: Vector2 in tracked_points:
			min_x = minf(min_x, pt.x - MARGIN_LEFT)
			max_x = maxf(max_x, pt.x + MARGIN_RIGHT)
			min_y = minf(min_y, pt.y - MARGIN_TOP)
			max_y = maxf(max_y, pt.y + MARGIN_BOTTOM)

		min_x -= VIEW_PADDING
		max_x += VIEW_PADDING
		min_y -= VIEW_PADDING
		max_y += VIEW_PADDING
		cam_rect = Rect2(min_x, min_y, maxf(1.0, max_x - min_x), maxf(1.0, max_y - min_y))

	# Enforce 16:9 / 4:3 aspect balance like PlayersKeeper.GetCamArea()
	var w_quarter: float = cam_rect.size.x / 4.0
	var h_third: float = cam_rect.size.y / 3.0
	if w_quarter < h_third:
		var extra_w: float = (h_third - w_quarter) * 4.0
		cam_rect.position.x -= extra_w * 0.5
		cam_rect.size.x += extra_w
	elif w_quarter > h_third:
		var extra_h: float = (w_quarter - h_third) * 3.0
		cam_rect.position.y -= extra_h * 0.5
		cam_rect.size.y += extra_h

	# Compute target zoom clamped in [MIN_ZOOM, MAX_ZOOM] = [1.85, 3.4]
	var zoom_from_w: float = REF_VIEW_WIDTH / maxf(80.0, cam_rect.size.x)
	var zoom_from_h: float = REF_VIEW_HEIGHT / maxf(60.0, cam_rect.size.y)
	target_zoom_scalar = clampf(minf(zoom_from_w, zoom_from_h), MIN_ZOOM, MAX_ZOOM)

	# Clamp camera center inside map_bounds
	var desired_center: Vector2 = cam_rect.get_center()
	var vp_size: Vector2 = Vector2(650.0, 400.0)
	if is_inside_tree() and get_viewport() != null:
		var vrect: Rect2 = get_viewport_rect()
		if vrect.size.x > 0.0 and vrect.size.y > 0.0:
			vp_size = vrect.size

	var half_view_w: float = minf(map_bounds.size.x * 0.45, (vp_size.x / target_zoom_scalar) * 0.5)
	var half_view_h: float = minf(map_bounds.size.y * 0.45, (vp_size.y / target_zoom_scalar) * 0.5)

	var min_cx: float = map_bounds.position.x + half_view_w
	var max_cx: float = map_bounds.end.x - half_view_w
	var min_cy: float = map_bounds.position.y + half_view_h
	var max_cy: float = map_bounds.end.y - half_view_h

	if min_cx <= max_cx:
		desired_center.x = clampf(desired_center.x, min_cx, max_cx)
	else:
		desired_center.x = map_bounds.get_center().x

	if min_cy <= max_cy:
		desired_center.y = clampf(desired_center.y, min_cy, max_cy)
	else:
		desired_center.y = map_bounds.get_center().y

	target_position = desired_center

	# Smooth interpolation per 24Hz step
	var lerp_alpha: float = clampf(0.22 * step_24hz, 0.05, 1.0)
	global_position = global_position.lerp(target_position, lerp_alpha)
	current_zoom_scalar = lerpf(current_zoom_scalar, target_zoom_scalar, lerp_alpha)
	current_zoom_scalar = clampf(current_zoom_scalar, MIN_ZOOM, MAX_ZOOM)
	zoom = Vector2(current_zoom_scalar, current_zoom_scalar)

	# Screen shake decay
	if screen_shake > 0.05:
		offset = Vector2(
			randf_range(-screen_shake, screen_shake),
			randf_range(-screen_shake, screen_shake)
		)
		screen_shake *= pow(0.75, step_24hz)
	else:
		screen_shake = 0.0
		offset = Vector2.ZERO

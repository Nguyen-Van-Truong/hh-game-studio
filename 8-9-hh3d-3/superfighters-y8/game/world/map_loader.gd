class_name MapLoader
extends Node2D
## Multi-layer XFL/AS3 Map Loader & World Geometry/Mechanics Manager (SF-M4).
## Loads compiled data from SFDataRegistry.get_map_data(map_id) for all 12 maps.
## Handles bg_layers, fg_layers (with Symbol 2499 mask_rects), Box2D center-based ground_boxes,
## ground_polygons (stairs/slopes), elevators, portals, breakable glass windows, and hanging lamps.

const RegistryScript = preload("res://game/core/sf_data_registry.gd")
const AudioScript = preload("res://game/core/audio_manager.gd")

static var _headless_registry: Node = null
static var _headless_audio: Node = null
static var _cached_tree_registry: Node = null
static var _cached_tree_audio: Node = null


static func get_registry() -> Node:
	if _cached_tree_registry != null and is_instance_valid(_cached_tree_registry):
		return _cached_tree_registry
	var ml: MainLoop = Engine.get_main_loop()
	if ml is SceneTree:
		var rt: Window = (ml as SceneTree).root
		if rt != null:
			var existing: Node = rt.get_node_or_null("SFDataRegistry")
			if existing != null:
				existing.call("ensure_loaded")
				_cached_tree_registry = existing
				return existing
			if _headless_registry == null or not is_instance_valid(_headless_registry):
				_headless_registry = RegistryScript.new()
				_headless_registry.name = "SFDataRegistry"
			if _headless_registry.get_parent() == null:
				rt.add_child(_headless_registry)
			_headless_registry.call("ensure_loaded")
			_cached_tree_registry = _headless_registry
			return _headless_registry
	if _headless_registry == null or not is_instance_valid(_headless_registry):
		_headless_registry = RegistryScript.new()
		_headless_registry.name = "SFDataRegistry"
		_headless_registry.call("ensure_loaded")
	_cached_tree_registry = _headless_registry
	return _headless_registry


static func get_audio() -> Node:
	if _cached_tree_audio != null and is_instance_valid(_cached_tree_audio):
		return _cached_tree_audio
	var ml: MainLoop = Engine.get_main_loop()
	if ml is SceneTree:
		var rt: Window = (ml as SceneTree).root
		if rt != null:
			var existing: Node = rt.get_node_or_null("AudioManager")
			if existing != null:
				existing.call("ensure_loaded")
				_cached_tree_audio = existing
				return existing
			if _headless_audio == null or not is_instance_valid(_headless_audio):
				_headless_audio = AudioScript.new()
				_headless_audio.name = "AudioManager"
			if _headless_audio.get_parent() == null:
				rt.add_child(_headless_audio)
			_headless_audio.call("ensure_loaded")
			_cached_tree_audio = _headless_audio
			return _headless_audio
	if _headless_audio == null or not is_instance_valid(_headless_audio):
		_headless_audio = AudioScript.new()
		_headless_audio.name = "AudioManager"
		_headless_audio.call("ensure_loaded")
	_cached_tree_audio = _headless_audio
	return _headless_audio


static func play_sfx(sound_id: String, volume_db: float = 0.0) -> void:
	var audio: Node = get_audio()
	if audio != null and is_instance_valid(audio) and audio.is_inside_tree() and audio.has_method("play_sfx"):
		audio.call("play_sfx", sound_id, volume_db)


static func play_sfx_at(sound_id: String, world_pos: Vector2, volume_db: float = 0.0) -> void:
	var audio: Node = get_audio()
	if audio != null and is_instance_valid(audio) and audio.is_inside_tree() and audio.has_method("play_sfx_at"):
		audio.call("play_sfx_at", sound_id, world_pos, volume_db)


static func cleanup_headless_singletons() -> void:
	var tree: SceneTree = Engine.get_main_loop() as SceneTree
	if tree != null and tree.root != null:
		var root_audio: Node = tree.root.get_node_or_null("AudioManager")
		if root_audio != null and is_instance_valid(root_audio):
			for child: Node in root_audio.get_children():
				if child is AudioStreamPlayer:
					(child as AudioStreamPlayer).stop()
					(child as AudioStreamPlayer).stream = null
			if root_audio.get("_streams") != null:
				(root_audio.get("_streams") as Dictionary).clear()
		var root_reg: Node = tree.root.get_node_or_null("SFDataRegistry")
		if root_reg != null and is_instance_valid(root_reg):
			if root_reg.get("_texture_cache") != null:
				(root_reg.get("_texture_cache") as Dictionary).clear()
			if root_reg.get("_tex_cache") != null:
				(root_reg.get("_tex_cache") as Dictionary).clear()
			if root_reg.get("_font_cache") != null:
				(root_reg.get("_font_cache") as Dictionary).clear()
	if _headless_audio != null and is_instance_valid(_headless_audio):
		for child: Node in _headless_audio.get_children():
			if child is AudioStreamPlayer:
				(child as AudioStreamPlayer).stop()
				(child as AudioStreamPlayer).stream = null
		if _headless_audio.get("_streams") != null:
			(_headless_audio.get("_streams") as Dictionary).clear()
		if _headless_audio.get_parent() != null:
			_headless_audio.get_parent().remove_child(_headless_audio)
		_headless_audio.free()
	_headless_audio = null
	if _headless_registry != null and is_instance_valid(_headless_registry):
		if _headless_registry.get("_texture_cache") != null:
			(_headless_registry.get("_texture_cache") as Dictionary).clear()
		if _headless_registry.get("_tex_cache") != null:
			(_headless_registry.get("_tex_cache") as Dictionary).clear()
		if _headless_registry.get("_font_cache") != null:
			(_headless_registry.get("_font_cache") as Dictionary).clear()
		if _headless_registry.get_parent() != null:
			_headless_registry.get_parent().remove_child(_headless_registry)
		_headless_registry.free()
	_headless_registry = null
	_cached_tree_registry = null
	_cached_tree_audio = null

var match_world: Node2D = null
var current_map_id: String = "rooftops"
var map_bounds: Rect2 = Rect2(-12.0, -110.0, 583.0, 510.0)
var _cached_intact_h_glass_rects: Array[Rect2] = []
var _h_glass_cache_dirty: bool = true

var solid_rects: Array[Rect2] = []
var cloud_rects: Array[Rect2] = []
var ladder_rects: Array[Rect2] = []
var slope_polygons: Array[Dictionary] = []
var portals: Array[Dictionary] = []
var elevators: Array[Dictionary] = []
var glasses: Array[Dictionary] = []
var hanging_lamps: Array[Dictionary] = []
var premade_props_data: Array[Dictionary] = []
var player_spawns: Array[Vector2] = []
var weapon_spawns: Array[Dictionary] = []
var ai_nodes: Array[Dictionary] = []
var ai_binds: Array[Dictionary] = []

var bg_color: Color = Color("#000080")
var acid_kill_y: float = 99999.0

var _bg_container: Node2D = null
var _collision_container: Node2D = null
var _elevator_container: Node2D = null
var _fx_overlay_node: Node2D = null
var _fg_container: Node2D = null

var _cloud_sprites: Array[Sprite2D] = []
var _fan_nodes: Array[Node2D] = []
var _portal_cooldowns: Dictionary = {} # instance_id -> remaining_frames_24hz
var _lamp_swing_time: float = 0.0


class MapFxOverlay extends Node2D:
	var loader: Node2D = null

	func _draw() -> void:
		if loader == null:
			return
		loader.call("_draw_map_fx_overlay", self)


func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_ensure_containers()


func _ensure_containers() -> void:
	if _bg_container == null or not is_instance_valid(_bg_container):
		_bg_container = Node2D.new()
		_bg_container.name = "BgLayers"
		_bg_container.z_index = -10
		add_child(_bg_container)
	if _collision_container == null or not is_instance_valid(_collision_container):
		_collision_container = Node2D.new()
		_collision_container.name = "Collisions"
		add_child(_collision_container)
	if _elevator_container == null or not is_instance_valid(_elevator_container):
		_elevator_container = Node2D.new()
		_elevator_container.name = "Elevators"
		_elevator_container.z_index = -2
		add_child(_elevator_container)
	if _fx_overlay_node == null or not is_instance_valid(_fx_overlay_node):
		var ov: MapFxOverlay = MapFxOverlay.new()
		ov.name = "GlassAndLampsOverlay"
		ov.z_index = 8
		ov.loader = self
		_fx_overlay_node = ov
		add_child(_fx_overlay_node)
	if _fg_container == null or not is_instance_valid(_fg_container):
		_fg_container = Node2D.new()
		_fg_container.name = "FgLayers"
		_fg_container.z_index = 20
		add_child(_fg_container)


func _clear_map_state() -> void:
	solid_rects.clear()
	cloud_rects.clear()
	ladder_rects.clear()
	slope_polygons.clear()
	portals.clear()
	elevators.clear()
	glasses.clear()
	hanging_lamps.clear()
	premade_props_data.clear()
	player_spawns.clear()
	weapon_spawns.clear()
	ai_nodes.clear()
	ai_binds.clear()
	_cloud_sprites.clear()
	_fan_nodes.clear()
	_portal_cooldowns.clear()
	_cached_intact_h_glass_rects.clear()
	_h_glass_cache_dirty = true
	acid_kill_y = 99999.0

	_ensure_containers()
	for container: Node2D in [_bg_container, _collision_container, _elevator_container, _fg_container]:
		for child: Node in container.get_children():
			container.remove_child(child)
			child.free()


func load_map(map_id: String) -> void:
	var reg: Node = get_registry()
	_clear_map_state()

	var normalized_id: String = map_id.to_lower().strip_edges().replace(" ", "_")
	if normalized_id == "police_office":
		normalized_id = "police_station"
	elif normalized_id == "sewer":
		normalized_id = "hazardous"

	var mdata: Dictionary = reg.call("get_map_data", normalized_id) as Dictionary
	if mdata.is_empty():
		normalized_id = "rooftops"
		mdata = reg.call("get_map_data", "rooftops") as Dictionary

	current_map_id = normalized_id
	bg_color = Color.from_string(str(mdata.get("bg_color", "#000080")), Color(0.0, 0.0, 0.5))
	if mdata.has("acid_kill_y"):
		acid_kill_y = float(mdata.get("acid_kill_y", 99999.0))

	var brect: Array = mdata.get("bounds_rect", [-12.0, -110.0, 583.0, 510.0]) as Array
	if brect.size() >= 4:
		map_bounds = Rect2(
			float(brect[0]),
			float(brect[1]),
			float(brect[2]),
			float(brect[3])
		)
	else:
		map_bounds = Rect2(-12.0, -110.0, 583.0, 510.0)

	_build_visual_layers(mdata)
	_build_ground_geometry(mdata)
	_build_elevators(mdata)
	_build_portals(mdata)
	_build_glasses_and_lamps(mdata)
	_build_spawns_and_ai(mdata)

	if _fx_overlay_node != null:
		_fx_overlay_node.queue_redraw()
	queue_redraw()


func _build_visual_layers(mdata: Dictionary) -> void:
	# 1. Sky backdrop Polygon2D covering wide camera area
	var sky_poly: Polygon2D = Polygon2D.new()
	sky_poly.name = "SkyBackdrop"
	sky_poly.color = bg_color
	sky_poly.z_index = -10
	var pad: float = 800.0
	var sx0: float = map_bounds.position.x - pad
	var sy0: float = map_bounds.position.y - pad
	var sx1: float = map_bounds.end.x + pad
	var sy1: float = map_bounds.end.y + pad
	sky_poly.polygon = PackedVector2Array([
		Vector2(sx0, sy0),
		Vector2(sx1, sy0),
		Vector2(sx1, sy1),
		Vector2(sx0, sy1)
	])
	_bg_container.add_child(sky_poly)

	# 2. Animated background props (drifting clouds & ventilation fans)
	var anim_props: Array = mdata.get("animated_props", []) as Array
	for ap_var: Variant in anim_props:
		if typeof(ap_var) != TYPE_DICTIONARY:
			continue
		var ap: Dictionary = ap_var as Dictionary
		var ap_type: String = str(ap.get("type", ""))
		var ax: float = float(ap.get("x", 0.0))
		var ay: float = float(ap.get("y", 0.0))
		if ap_type == "clouds":
			var cloud_tex: Texture2D = get_registry().call("load_cached_texture", "res://assets/maps/Bitmap 2210.png") as Texture2D
			if cloud_tex != null:
				for copy_idx: int in range(2):
					var cspr: Sprite2D = Sprite2D.new()
					cspr.name = "CloudLayer_" + str(copy_idx)
					cspr.centered = false
					cspr.texture = cloud_tex
					cspr.position = Vector2(ax + float(copy_idx) * float(cloud_tex.get_width()), ay)
					cspr.modulate = Color(1.0, 1.0, 1.0, 0.85)
					cspr.set_meta("base_x", ax)
					cspr.set_meta("copy_idx", copy_idx)
					_bg_container.add_child(cspr)
					_cloud_sprites.append(cspr)
		elif ap_type == "fan":
			var fan_holder: Node2D = Node2D.new()
			fan_holder.name = str(ap.get("name", "fan"))
			fan_holder.position = Vector2(ax, ay)
			var blade_a: Polygon2D = Polygon2D.new()
			blade_a.color = Color(0.18, 0.2, 0.24, 0.75)
			blade_a.polygon = PackedVector2Array([
				Vector2(-10.0, -2.0), Vector2(10.0, -2.0),
				Vector2(10.0, 2.0), Vector2(-10.0, 2.0)
			])
			var blade_b: Polygon2D = Polygon2D.new()
			blade_b.color = Color(0.18, 0.2, 0.24, 0.75)
			blade_b.polygon = PackedVector2Array([
				Vector2(-2.0, -10.0), Vector2(2.0, -10.0),
				Vector2(2.0, 10.0), Vector2(-2.0, 10.0)
			])
			fan_holder.add_child(blade_a)
			fan_holder.add_child(blade_b)
			_bg_container.add_child(fan_holder)
			_fan_nodes.append(fan_holder)

	# 3. Background layers (Symbol 2484.xml)
	var bg_layers: Array = mdata.get("bg_layers", []) as Array
	var layer_idx: int = 0
	for layer_var: Variant in bg_layers:
		if typeof(layer_var) != TYPE_DICTIONARY:
			continue
		var layer: Dictionary = layer_var as Dictionary
		var tex: Texture2D = _resolve_map_layer_texture(layer)
		if tex == null:
			continue
		var spr: Sprite2D = Sprite2D.new()
		spr.name = "BgSprite_" + str(layer_idx)
		spr.centered = false
		spr.texture = tex
		spr.position = Vector2(float(layer.get("tx", 0.0)), float(layer.get("ty", 0.0)))
		spr.scale = Vector2(float(layer.get("sx", 1.0)), float(layer.get("sy", 1.0)))
		spr.z_index = layer_idx
		_bg_container.add_child(spr)
		layer_idx += 1

	# 4. Foreground layers (Symbol 2499.xml - levels_front covering elevator shafts & portal doors)
	var fg_layers: Array = mdata.get("fg_layers", []) as Array
	var fg_idx: int = 0
	for fg_var: Variant in fg_layers:
		if typeof(fg_var) != TYPE_DICTIONARY:
			continue
		var fg: Dictionary = fg_var as Dictionary
		var fg_tex: Texture2D = _resolve_map_layer_texture(fg)
		if fg_tex == null:
			continue
		var tx: float = float(fg.get("tx", 0.0))
		var ty: float = float(fg.get("ty", 0.0))
		var sx: float = float(fg.get("sx", 1.0))
		var sy: float = float(fg.get("sy", 1.0))
		var mask_rects: Array = fg.get("mask_rects", []) as Array
		if mask_rects.is_empty():
			var fspr: Sprite2D = Sprite2D.new()
			fspr.name = "FgSprite_" + str(fg_idx)
			fspr.centered = false
			fspr.texture = fg_tex
			fspr.position = Vector2(tx, ty)
			fspr.scale = Vector2(sx, sy)
			_fg_container.add_child(fspr)
			fg_idx += 1
		else:
			# Cut out exact foreground patches defined in Symbol 2499.xml so only portal doors & elevator shafts are covered
			var tex_w: float = float(fg_tex.get_width())
			var tex_h: float = float(fg_tex.get_height())
			for m_var: Variant in mask_rects:
				if typeof(m_var) != TYPE_ARRAY:
					continue
				var mr: Array = m_var as Array
				if mr.size() < 4:
					continue
				var mx: float = float(mr[0])
				var my: float = float(mr[1])
				var mw: float = float(mr[2])
				var mh: float = float(mr[3])
				var reg_x: float = clampf(mx - tx, 0.0, maxf(0.0, tex_w - 1.0))
				var reg_y: float = clampf(my - ty, 0.0, maxf(0.0, tex_h - 1.0))
				var reg_w: float = clampf(mw, 1.0, maxf(1.0, tex_w - reg_x))
				var reg_h: float = clampf(mh, 1.0, maxf(1.0, tex_h - reg_y))
				var atex: AtlasTexture = AtlasTexture.new()
				atex.atlas = fg_tex
				atex.region = Rect2(reg_x, reg_y, reg_w, reg_h)
				var mspr: Sprite2D = Sprite2D.new()
				mspr.name = "FgPatch_" + str(fg_idx)
				mspr.centered = false
				mspr.texture = atex
				mspr.position = Vector2(tx + reg_x, ty + reg_y)
				mspr.scale = Vector2(sx, sy)
				_fg_container.add_child(mspr)
				fg_idx += 1


func _resolve_map_layer_texture(layer: Dictionary) -> Texture2D:
	var reg: Node = get_registry()
	var path: String = str(layer.get("path", ""))
	var tex: Texture2D = reg.call("load_cached_texture", path) as Texture2D
	if tex != null:
		return tex
	var alias_bmp: String = str(layer.get("alias_bitmap", ""))
	if not alias_bmp.is_empty():
		tex = reg.call("load_cached_texture", "res://assets/maps/" + alias_bmp) as Texture2D
		if tex != null:
			return tex
	var bmp: String = str(layer.get("bitmap", ""))
	if not bmp.is_empty():
		tex = reg.call("load_cached_texture", "res://assets/maps/" + bmp) as Texture2D
	return tex


func _build_ground_geometry(mdata: Dictionary) -> void:
	# 1. Ground Boxes (center_x, center_y, full_w, full_h)
	var gboxes: Array = mdata.get("ground_boxes", []) as Array
	var box_idx: int = 0
	for gb_var: Variant in gboxes:
		if typeof(gb_var) != TYPE_DICTIONARY:
			continue
		var gb: Dictionary = gb_var as Dictionary
		var cx: float = float(gb.get("x", 0.0))
		var cy: float = float(gb.get("y", 0.0))
		var w: float = float(gb.get("w", 0.0))
		var h: float = float(gb.get("h", 0.0))
		var angle: float = float(gb.get("angle", 0.0))
		if w <= 0.0 or h <= 0.0:
			continue
		var rect: Rect2 = Rect2(cx - w * 0.5, cy - h * 0.5, w, h)
		var raw_tags: Array = gb.get("tags", []) as Array
		var tags: Array[String] = []
		for t: Variant in raw_tags:
			tags.append(str(t).to_upper())

		if "LADDER" in tags:
			ladder_rects.append(rect)
		elif "CLOUD" in tags:
			if absf(angle) > 0.05:
				var hw: float = w * 0.5
				var hh: float = h * 0.5
				var corners: Array[Vector2] = [
					Vector2(-hw, -hh),
					Vector2(hw, -hh),
					Vector2(hw, hh),
					Vector2(-hw, hh),
				]
				var local_pts_c: PackedVector2Array = PackedVector2Array()
				var world_pts_c: PackedVector2Array = PackedVector2Array()
				var min_cx: float = INF
				var min_cy: float = INF
				var max_cx: float = -INF
				var max_cy: float = -INF
				for c_pt: Vector2 in corners:
					var lpt_c: Vector2 = c_pt.rotated(angle)
					var wpt_c: Vector2 = Vector2(cx, cy) + lpt_c
					local_pts_c.append(lpt_c)
					world_pts_c.append(wpt_c)
					min_cx = minf(min_cx, wpt_c.x)
					min_cy = minf(min_cy, wpt_c.y)
					max_cx = maxf(max_cx, wpt_c.x)
					max_cy = maxf(max_cy, wpt_c.y)
				var top_edge_idx: int = 0
				if world_pts_c.size() == 4:
					var len_01: float = world_pts_c[0].distance_to(world_pts_c[1])
					var len_12: float = world_pts_c[1].distance_to(world_pts_c[2])
					if len_01 >= len_12:
						var mid_y0: float = (world_pts_c[0].y + world_pts_c[1].y) * 0.5
						var mid_y2: float = (world_pts_c[2].y + world_pts_c[3].y) * 0.5
						top_edge_idx = 0 if mid_y0 <= mid_y2 else 2
					else:
						var mid_y1: float = (world_pts_c[1].y + world_pts_c[2].y) * 0.5
						var mid_y3: float = (world_pts_c[3].y + world_pts_c[0].y) * 0.5
						top_edge_idx = 1 if mid_y1 <= mid_y3 else 3
				slope_polygons.append({
					"x": cx,
					"y": cy,
					"angle": angle,
					"tilt_value": 2.0 if angle > 0.0 else -2.0,
					"is_cloud": true,
					"top_edge_idx": top_edge_idx,
					"local_points": local_pts_c,
					"world_points": world_pts_c,
					"bounds_rect": Rect2(min_cx, min_cy, max_cx - min_cx, max_cy - min_cy),
				})
			else:
				cloud_rects.append(rect)
			_create_static_box_body("CloudBox_" + str(box_idx), cx, cy, w, h, angle, true)
		else:
			solid_rects.append(rect)
			_create_static_box_body("SolidBox_" + str(box_idx), cx, cy, w, h, angle, false)
		box_idx += 1

	# 2. Ground Polygons (slopes / stairs with tilt_value)
	var gpolys: Array = mdata.get("ground_polygons", []) as Array
	var poly_idx: int = 0
	for gp_var: Variant in gpolys:
		if typeof(gp_var) != TYPE_DICTIONARY:
			continue
		var gp: Dictionary = gp_var as Dictionary
		var cx: float = float(gp.get("x", 0.0))
		var cy: float = float(gp.get("y", 0.0))
		var angle: float = float(gp.get("angle", 0.0))
		var tilt_val: float = float(gp.get("tilt_value", 0.0))
		var raw_verts: Array = gp.get("vertices", []) as Array
		var local_pts: PackedVector2Array = PackedVector2Array()
		var world_pts: PackedVector2Array = PackedVector2Array()
		var min_x: float = INF
		var min_y: float = INF
		var max_x: float = -INF
		var max_y: float = -INF
		for v_var: Variant in raw_verts:
			if typeof(v_var) == TYPE_ARRAY and (v_var as Array).size() >= 2:
				var va: Array = v_var as Array
				var lpt: Vector2 = Vector2(float(va[0]), float(va[1])).rotated(angle)
				var wpt: Vector2 = Vector2(cx, cy) + lpt
				local_pts.append(lpt)
				world_pts.append(wpt)
				min_x = minf(min_x, wpt.x)
				min_y = minf(min_y, wpt.y)
				max_x = maxf(max_x, wpt.x)
				max_y = maxf(max_y, wpt.y)
		if local_pts.size() >= 3:
			var sbody: StaticBody2D = StaticBody2D.new()
			sbody.name = "SlopePoly_" + str(poly_idx)
			sbody.position = Vector2(cx, cy)
			var cpoly: CollisionPolygon2D = CollisionPolygon2D.new()
			cpoly.polygon = local_pts
			sbody.add_child(cpoly)
			_collision_container.add_child(sbody)

			slope_polygons.append({
				"var_name": str(gp.get("var_name", "")),
				"x": cx,
				"y": cy,
				"angle": angle,
				"tilt_value": tilt_val,
				"local_points": local_pts,
				"world_points": world_pts,
				"bounds_rect": Rect2(min_x, min_y, max_x - min_x, max_y - min_y),
			})
			poly_idx += 1

	# 3. Ground Circles
	var gcircles: Array = mdata.get("ground_circles", []) as Array
	var circ_idx: int = 0
	for gc_var: Variant in gcircles:
		if typeof(gc_var) != TYPE_DICTIONARY:
			continue
		var gc: Dictionary = gc_var as Dictionary
		var cx: float = float(gc.get("x", 0.0))
		var cy: float = float(gc.get("y", 0.0))
		var r: float = float(gc.get("radius", 8.0))
		if r <= 0.0:
			continue
		var sbody: StaticBody2D = StaticBody2D.new()
		sbody.name = "SolidCircle_" + str(circ_idx)
		sbody.position = Vector2(cx, cy)
		var cshape: CollisionShape2D = CollisionShape2D.new()
		var ccircle: CircleShape2D = CircleShape2D.new()
		ccircle.radius = r
		cshape.shape = ccircle
		sbody.add_child(cshape)
		_collision_container.add_child(sbody)
		solid_rects.append(Rect2(cx - r, cy - r, r * 2.0, r * 2.0))
		circ_idx += 1


func _create_static_box_body(
	body_name: String,
	cx: float,
	cy: float,
	w: float,
	h: float,
	angle: float,
	one_way: bool
) -> StaticBody2D:
	var sbody: StaticBody2D = StaticBody2D.new()
	sbody.name = body_name
	sbody.position = Vector2(cx, cy)
	sbody.rotation = angle
	var cshape: CollisionShape2D = CollisionShape2D.new()
	var rshape: RectangleShape2D = RectangleShape2D.new()
	rshape.size = Vector2(w, h)
	cshape.shape = rshape
	cshape.one_way_collision = one_way
	sbody.add_child(cshape)
	_collision_container.add_child(sbody)
	return sbody


func _build_elevators(mdata: Dictionary) -> void:
	var reg: Node = get_registry()
	var raw_elevs: Array = mdata.get("elevators", []) as Array
	var idx: int = 0
	for el_var: Variant in raw_elevs:
		if typeof(el_var) != TYPE_DICTIONARY:
			continue
		var el: Dictionary = el_var as Dictionary
		var etype: String = str(el.get("type", "LIFT_SMALL_01")).to_upper()
		var def: Dictionary = reg.call("get_premade_item_def", etype) as Dictionary
		var ew: float = float(def.get("w", 26.0 if "SMALL" in etype else 42.0))
		var eh: float = float(def.get("h", 8.0))
		var start_x: float = float(el.get("x", 229.0))
		var start_y: float = float(el.get("y", 290.0))
		var dist: float = float(el.get("distance", 92.0))
		var speed: float = float(el.get("speed", 1.0))
		var dir_str: String = str(el.get("direction", "vertical")).to_lower()

		# In Maps.as CreateElevator(lift, distance, speed), the lift starts at start_y (bottom of shaft)
		# and oscillates smoothly between start_y and start_y - distance.
		# In Maps.as:1649-1662 CreateHorizontalElevator(lift, distance, speed), the motor is at start_x - distance * 2,
		# so the lift starts at start_x (right end of shaft) and oscillates smoothly between start_x - distance and start_x!
		var center_pos: Vector2 = Vector2(start_x, start_y - dist * 0.5)
		if dir_str == "horizontal":
			center_pos = Vector2(start_x - dist * 0.5, start_y)

		var ebody: AnimatableBody2D = AnimatableBody2D.new()
		ebody.name = "Elevator_" + str(idx)
		ebody.sync_to_physics = false
		ebody.position = Vector2(start_x, start_y)

		var cshape: CollisionShape2D = CollisionShape2D.new()
		var rshape: RectangleShape2D = RectangleShape2D.new()
		rshape.size = Vector2(ew, eh)
		cshape.shape = rshape
		cshape.one_way_collision = true
		ebody.add_child(cshape)

		var spr_path: String = str(def.get("sprite", "res://assets/sprites/props/obj_lift_small_01.png"))
		var tex: Texture2D = reg.call("load_cached_texture", spr_path) as Texture2D
		if tex != null:
			var espr: Sprite2D = Sprite2D.new()
			espr.texture = tex
			ebody.add_child(espr)

		_elevator_container.add_child(ebody)

		var rect: Rect2 = Rect2(start_x - ew * 0.5, start_y - eh * 0.5, ew, eh)
		elevators.append({
			"var_name": str(el.get("var_name", "lift")),
			"type": etype,
			"direction": dir_str,
			"start_x": start_x,
			"start_y": start_y,
			"center_pos": center_pos,
			"current_pos": Vector2(start_x, start_y),
			"delta_pos": Vector2.ZERO,
			"w": ew,
			"h": eh,
			"rect": rect,
			"distance": dist,
			"speed": speed,
			"phase": PI * 0.5, # sin(PI/2) = +1 -> starts at bottom (start_y)
			"body": ebody,
		})
		idx += 1


func _build_portals(mdata: Dictionary) -> void:
	var raw_portals: Array = mdata.get("portals", []) as Array
	for p_var: Variant in raw_portals:
		if typeof(p_var) != TYPE_DICTIONARY:
			continue
		var pd: Dictionary = p_var as Dictionary
		var r_en: Array = pd.get("entry_rect", []) as Array
		var r_ex: Array = pd.get("exit_rect", []) as Array
		var dir_arr: Array = pd.get("dir", [-1.0, 0.0]) as Array
		if r_en.size() < 4 or r_ex.size() < 4:
			continue
		var entry_rect: Rect2 = Rect2(float(r_en[0]), float(r_en[1]), float(r_en[2]), float(r_en[3]))
		var exit_rect: Rect2 = Rect2(float(r_ex[0]), float(r_ex[1]), float(r_ex[2]), float(r_ex[3]))
		var dir_vec: Vector2 = Vector2(
			float(dir_arr[0]) if dir_arr.size() >= 1 else -1.0,
			float(dir_arr[1]) if dir_arr.size() >= 2 else 0.0
		)
		# Check matching twin portal at exit_rect to see if entry.dir.x == exit.dir.x
		var twin_dir_x: float = dir_vec.x
		for other_var: Variant in raw_portals:
			if typeof(other_var) == TYPE_DICTIONARY:
				var od: Dictionary = other_var as Dictionary
				var o_en: Array = od.get("entry_rect", []) as Array
				if o_en.size() >= 4:
					if is_equal_approx(float(o_en[0]), exit_rect.position.x) and is_equal_approx(float(o_en[1]), exit_rect.position.y):
						var o_dir: Array = od.get("dir", [twin_dir_x, 0.0]) as Array
						if not o_dir.is_empty():
							twin_dir_x = float(o_dir[0])
						break

		var door_open: bool = bool(pd.get("door_open", true))
		var ignore_vel: bool = bool(pd.get("ignore_vel", false))
		var flip_x: bool = door_open or is_equal_approx(dir_vec.x, twin_dir_x)

		# Add solid backstop wall behind open-doorway portals so fighters/bots can never walk into the black foreground mask outside the map
		if door_open:
			if dir_vec.x > 0.0:
				solid_rects.append(Rect2(entry_rect.position.x + 5.0, entry_rect.position.y - 4.0, maxf(16.0, entry_rect.size.x), entry_rect.size.y + 8.0))
			elif dir_vec.x < 0.0:
				var back_end_x: float = entry_rect.end.x - 5.0
				var back_start_x: float = minf(entry_rect.position.x - 8.0, back_end_x - 16.0)
				solid_rects.append(Rect2(back_start_x, entry_rect.position.y - 4.0, back_end_x - back_start_x, entry_rect.size.y + 8.0))

		portals.append({
			"entry_rect": entry_rect,
			"exit_rect": exit_rect,
			"dir": dir_vec,
			"door_open": door_open,
			"ignore_vel": ignore_vel,
			"flip_x": flip_x,
		})


func _build_glasses_and_lamps(mdata: Dictionary) -> void:
	var raw_glasses: Array = mdata.get("glasses", []) as Array
	for g_var: Variant in raw_glasses:
		if typeof(g_var) != TYPE_DICTIONARY:
			continue
		var gd: Dictionary = g_var as Dictionary
		var x1: float = float(gd.get("x1", 0.0))
		var y1: float = float(gd.get("y1", 0.0))
		var x2: float = float(gd.get("x2", 0.0))
		var y2: float = float(gd.get("y2", 0.0))
		var min_x: float = minf(x1, x2) - 1.5
		var min_y: float = minf(y1, y2) - 1.5
		var max_x: float = maxf(x1, x2) + 1.5
		var max_y: float = maxf(y1, y2) + 1.5
		glasses.append({
			"x1": x1,
			"y1": y1,
			"x2": x2,
			"y2": y2,
			"p1": Vector2(x1, y1),
			"p2": Vector2(x2, y2),
			"rect": Rect2(min_x, min_y, max_x - min_x, max_y - min_y),
			"hp": 5.0,
			"broken": false,
		})

	var raw_lamps: Array = mdata.get("hanging_lamps", []) as Array
	for l_var: Variant in raw_lamps:
		if typeof(l_var) != TYPE_DICTIONARY:
			continue
		var ld: Dictionary = l_var as Dictionary
		hanging_lamps.append({
			"x": float(ld.get("x", 0.0)),
			"y": float(ld.get("y", 0.0)),
			"rope_length": float(ld.get("rope_length", 25.0)),
			"angle": 0.0,
		})


func _build_spawns_and_ai(mdata: Dictionary) -> void:
	var raw_pspawns: Array = mdata.get("player_spawns", []) as Array
	for ps_var: Variant in raw_pspawns:
		if typeof(ps_var) == TYPE_ARRAY and (ps_var as Array).size() >= 2:
			var pa: Array = ps_var as Array
			player_spawns.append(Vector2(float(pa[0]), float(pa[1])))

	var raw_wspawns: Array = mdata.get("weapon_spawns", []) as Array
	for ws_var: Variant in raw_wspawns:
		if typeof(ws_var) == TYPE_DICTIONARY:
			weapon_spawns.append((ws_var as Dictionary).duplicate(true))

	var raw_props: Array = mdata.get("premade_props", []) as Array
	for pr_var: Variant in raw_props:
		if typeof(pr_var) == TYPE_DICTIONARY:
			premade_props_data.append((pr_var as Dictionary).duplicate(true))

	var grid: Dictionary = mdata.get("ai_path_grid", {}) as Dictionary
	var raw_nodes: Array = grid.get("nodes", []) as Array
	for n_var: Variant in raw_nodes:
		if typeof(n_var) == TYPE_DICTIONARY:
			ai_nodes.append((n_var as Dictionary).duplicate(true))

	var raw_binds: Array = grid.get("binds", []) as Array
	for b_var: Variant in raw_binds:
		if typeof(b_var) == TYPE_DICTIONARY:
			ai_binds.append((b_var as Dictionary).duplicate(true))


func step_map(step_24hz: float) -> void:
	var dt_sec: float = step_24hz / 24.0

	# 1. Drift clouds and spin background fans
	for cspr: Sprite2D in _cloud_sprites:
		if is_instance_valid(cspr) and cspr.texture != null:
			cspr.position.x += 0.12 * step_24hz
			var base_x: float = float(cspr.get_meta("base_x", -110.0))
			var w: float = float(cspr.texture.get_width())
			if cspr.position.x > base_x + w:
				cspr.position.x -= w * 2.0

	for fan: Node2D in _fan_nodes:
		if is_instance_valid(fan):
			fan.rotation += 0.18 * step_24hz

	# 2. Oscillate elevators and carry riders (fighters & props) standing on them
	for i: int in range(elevators.size()):
		var el: Dictionary = elevators[i]
		var old_pos: Vector2 = el.get("current_pos", Vector2.ZERO) as Vector2
		var speed: float = float(el.get("speed", 1.0))
		var dist: float = float(el.get("distance", 92.0))
		var phase: float = float(el.get("phase", PI * 0.5)) + speed * dt_sec
		el["phase"] = phase

		var center_pos: Vector2 = el.get("center_pos", old_pos) as Vector2
		var dir_str: String = str(el.get("direction", "vertical"))
		var new_pos: Vector2 = center_pos
		if dir_str == "horizontal":
			new_pos.x = center_pos.x + sin(phase) * (dist * 0.5)
		else:
			new_pos.y = center_pos.y + sin(phase) * (dist * 0.5)

		var delta_pos: Vector2 = new_pos - old_pos
		el["current_pos"] = new_pos
		el["delta_pos"] = delta_pos
		var ew: float = float(el.get("w", 26.0))
		var eh: float = float(el.get("h", 8.0))
		var new_rect: Rect2 = Rect2(new_pos.x - ew * 0.5, new_pos.y - eh * 0.5, ew, eh)
		var old_rect: Rect2 = el.get("rect", new_rect) as Rect2
		el["rect"] = new_rect

		var ebody: Node2D = el.get("body", null) as Node2D
		if ebody != null and is_instance_valid(ebody):
			ebody.position = new_pos

		_carry_elevator_riders(old_rect, new_rect, delta_pos)

		# Update dynamic AI path nodes bound to this elevator var_name
		var vname: String = str(el.get("var_name", ""))
		if not vname.is_empty():
			for anode: Dictionary in ai_nodes:
				if str(anode.get("body_ref", "")) == vname:
					anode["y"] = new_rect.position.y
					if dir_str == "horizontal":
						anode["x"] = float(anode.get("x", new_pos.x)) + delta_pos.x

	# 3. Update portal cooldowns and check entities entering portals
	var expired_ids: Array = []
	for eid: Variant in _portal_cooldowns.keys():
		var rem: float = float(_portal_cooldowns[eid]) - step_24hz
		if rem <= 0.0:
			expired_ids.append(eid)
		else:
			_portal_cooldowns[eid] = rem
	for eid: Variant in expired_ids:
		_portal_cooldowns.erase(eid)

	_step_portals()

	# 4. Swing hanging lamps gently
	_lamp_swing_time += dt_sec * 2.2
	for i: int in range(hanging_lamps.size()):
		var lamp: Dictionary = hanging_lamps[i]
		lamp["angle"] = sin(_lamp_swing_time + float(i) * 1.1) * 0.08
	if not hanging_lamps.is_empty() and _fx_overlay_node != null:
		_fx_overlay_node.queue_redraw()


func _carry_elevator_riders(old_rect: Rect2, new_rect: Rect2, delta_pos: Vector2) -> void:
	if match_world == null or not is_instance_valid(match_world):
		return
	var top_old: float = old_rect.position.y
	var top_new: float = new_rect.position.y
	var min_x: float = old_rect.position.x - 3.0
	var max_x: float = old_rect.end.x + 3.0

	var fighters_var: Variant = match_world.get("fighters")
	if typeof(fighters_var) == TYPE_ARRAY:
		for f_var: Variant in fighters_var as Array:
			if f_var is Node2D and is_instance_valid(f_var):
				var f: Node2D = f_var as Node2D
				var f_on_ground: bool = bool(f.get("on_ground"))
				var f_av_v: Variant = f.get("air_velocity")
				var f_vy: float = (f_av_v as Vector2).y if typeof(f_av_v) == TYPE_VECTOR2 else 0.0
				# Do NOT yank a jumping fighter (f_vy < 0 or not on_ground) back down onto the elevator!
				if not f_on_ground or f_vy < -0.01:
					continue
				var pos: Vector2 = f.global_position
				if pos.x >= min_x and pos.x <= max_x and absf(pos.y - top_old) <= 6.0:
					f.global_position = Vector2(pos.x + delta_pos.x, top_new)
					f.set("on_ground", true)
					f.set("_on_cloud_platform", true)

	var props_var: Variant = match_world.get("props")
	if typeof(props_var) == TYPE_ARRAY:
		for p_var: Variant in props_var as Array:
			if p_var is Node2D and is_instance_valid(p_var):
				var p: Node2D = p_var as Node2D
				var ph: float = float(p.get("height")) if p.get("height") != null else 14.0
				var bottom_y: float = p.global_position.y + ph * 0.5
				if p.global_position.x >= min_x and p.global_position.x <= max_x and absf(bottom_y - top_old) <= 6.0:
					p.global_position = Vector2(p.global_position.x + delta_pos.x, top_new - ph * 0.5)


func _step_portals() -> void:
	if portals.is_empty() or match_world == null or not is_instance_valid(match_world):
		return

	var fighters_var: Variant = match_world.get("fighters")
	if typeof(fighters_var) == TYPE_ARRAY:
		for f_var: Variant in fighters_var as Array:
			if f_var is Node2D and is_instance_valid(f_var):
				var f: Node2D = f_var as Node2D
				var move_dir_x: float = _infer_entity_portal_dir_x(f)
				try_teleport_entity(f, move_dir_x)

	var props_var: Variant = match_world.get("props")
	if typeof(props_var) == TYPE_ARRAY:
		for p_var: Variant in props_var as Array:
			if p_var is Node2D and is_instance_valid(p_var):
				var p: Node2D = p_var as Node2D
				var vel_v: Variant = p.get("velocity")
				if typeof(vel_v) == TYPE_VECTOR2:
					var pv: Vector2 = vel_v as Vector2
					if absf(pv.x) > 0.2:
						try_teleport_entity(p, signf(pv.x))


func _infer_entity_portal_dir_x(entity: Node2D) -> float:
	var av_var: Variant = entity.get("air_velocity")
	if typeof(av_var) == TYPE_VECTOR2:
		var av: Vector2 = av_var as Vector2
		if absf(av.x) > 0.05:
			return signf(av.x)
	if entity is CharacterBody2D:
		var cb: CharacterBody2D = entity as CharacterBody2D
		if absf(cb.velocity.x) > 0.5:
			return signf(cb.velocity.x)
	return 0.0


func try_teleport_entity(entity: Node2D, move_dir_x: float = 0.0) -> bool:
	if entity == null or not is_instance_valid(entity):
		return false
	var iid: int = entity.get_instance_id()
	if _portal_cooldowns.has(iid):
		return false

	var pos: Vector2 = entity.global_position
	var check_pt: Vector2 = Vector2(pos.x, pos.y - 6.0)

	for p: Dictionary in portals:
		var entry_rect: Rect2 = p.get("entry_rect", Rect2()) as Rect2
		if not entry_rect.has_point(check_pt) and not entry_rect.has_point(pos):
			continue
		var pdir: Vector2 = p.get("dir", Vector2(-1.0, 0.0)) as Vector2
		var door_open: bool = bool(p.get("door_open", true))
		var dir_x: float = move_dir_x if absf(move_dir_x) > 0.01 else _infer_entity_portal_dir_x(entity)
		var dir_matches: bool = (
			(pdir.x < 0.0 and (dir_x < 0.0 or (door_open and dir_x <= 0.0)))
			or (pdir.x > 0.0 and (dir_x > 0.0 or (door_open and dir_x >= 0.0)))
			or is_zero_approx(pdir.x)
		)
		if not dir_matches:
			continue

		var exit_rect: Rect2 = p.get("exit_rect", Rect2()) as Rect2
		var flip_x: bool = bool(p.get("flip_x", true))
		var dy: float = pos.y - entry_rect.position.y
		var new_x: float = exit_rect.position.x + exit_rect.size.x * 0.5
		if door_open:
			if pdir.x > 0.0:
				new_x = exit_rect.position.x - 2.0
			elif pdir.x < 0.0:
				new_x = exit_rect.end.x + 2.0
		var new_y: float = exit_rect.position.y + dy
		if door_open and bool(entity.get("on_ground")):
			var gy_exit: float = get_ground_y_below(new_x, exit_rect.end.y - 8.0, 16.0, true)
			if gy_exit < INF:
				new_y = gy_exit
		entity.global_position = Vector2(new_x, new_y)

		var eff_entry_dir: int = int(signf(dir_x)) if absf(dir_x) > 0.01 else int(signf(pdir.x))
		if flip_x:
			var facing_v: Variant = entity.get("facing")
			if typeof(facing_v) == TYPE_INT:
				entity.set("facing", -1 if pdir.x > 0.0 else (1 if pdir.x < 0.0 else -int(facing_v)))
			var av_v: Variant = entity.get("air_velocity")
			if typeof(av_v) == TYPE_VECTOR2:
				var av: Vector2 = av_v as Vector2
				entity.set("air_velocity", Vector2(-av.x, av.y))
			var vel_v: Variant = entity.get("velocity")
			if typeof(vel_v) == TYPE_VECTOR2:
				var vv: Vector2 = vel_v as Vector2
				entity.set("velocity", Vector2(-vv.x, vv.y))
		if entity.has_method("on_portal_teleported"):
			entity.call("on_portal_teleported", flip_x, eff_entry_dir)

		_portal_cooldowns[iid] = 4.0
		return true

	return false


func get_intact_horizontal_glass_rects() -> Array[Rect2]:
	if not _h_glass_cache_dirty:
		return _cached_intact_h_glass_rects
	_cached_intact_h_glass_rects.clear()
	for g: Dictionary in glasses:
		if bool(g.get("broken", false)):
			continue
		var y1: float = float(g.get("y1", 0.0))
		var y2: float = float(g.get("y2", 0.0))
		if absf(y1 - y2) <= 2.0:
			var x1: float = float(g.get("x1", 0.0))
			var x2: float = float(g.get("x2", 0.0))
			var min_x: float = minf(x1, x2)
			var max_x: float = maxf(x1, x2)
			var mid_y: float = (y1 + y2) * 0.5
			# In AS3 MapPremadeItems.as:1335-1345, horizontal glass has DrawHitBox=true, top surface at mid_y (flush with floor)
			_cached_intact_h_glass_rects.append(Rect2(min_x, mid_y, max_x - min_x, 4.0))
	_h_glass_cache_dirty = false
	return _cached_intact_h_glass_rects


func get_intact_vertical_glass_rects() -> Array[Rect2]:
	var out: Array[Rect2] = []
	for g: Dictionary in glasses:
		if bool(g.get("broken", false)):
			continue
		var x1: float = float(g.get("x1", 0.0))
		var x2: float = float(g.get("x2", 0.0))
		var y1: float = float(g.get("y1", 0.0))
		var y2: float = float(g.get("y2", 0.0))
		if absf(x1 - x2) <= 2.0 and absf(y1 - y2) > 2.0:
			var min_y: float = minf(y1, y2)
			var max_y: float = maxf(y1, y2)
			var mid_x: float = (x1 + x2) * 0.5
			out.append(Rect2(mid_x - 1.0, min_y, 2.0, max_y - min_y))
	return out


func damage_glass_in_rect(hit_rect: Rect2, damage: float, impact_vel: Vector2) -> bool:
	var broke_any: bool = false
	for i: int in range(glasses.size()):
		var g: Dictionary = glasses[i]
		if bool(g.get("broken", false)):
			continue
		var grect: Rect2 = (g.get("rect", Rect2()) as Rect2).grow(2.0)
		if grect.intersects(hit_rect):
			var next_hp: float = float(g.get("hp", 5.0)) - damage
			g["hp"] = next_hp
			if next_hp <= 0.0:
				g["broken"] = true
				broke_any = true
				_h_glass_cache_dirty = true
				var gp1: Vector2 = g.get("p1", Vector2.ZERO) as Vector2
				var gp2: Vector2 = g.get("p2", Vector2.ZERO) as Vector2
				var spawned_shards: bool = false
				if match_world != null and is_instance_valid(match_world):
					var fhs: Variant = match_world.get("fire_hazard_system")
					if fhs != null and is_instance_valid(fhs) and fhs.has_method("spawn_glass_shards"):
						fhs.call("spawn_glass_shards", gp1, gp2, impact_vel)
						spawned_shards = true
				if not spawned_shards:
					play_sfx_at("glass", (gp1 + gp2) * 0.5)
	if broke_any and _fx_overlay_node != null:
		_fx_overlay_node.queue_redraw()
	return broke_any


func has_kickable_glass_near(foot_pos: Vector2, facing_dir: int) -> bool:
	var check_rect: Rect2 = Rect2(
		foot_pos.x + (0.0 if facing_dir > 0 else -14.0),
		foot_pos.y - 16.0,
		14.0,
		20.0
	)
	for g: Dictionary in glasses:
		if bool(g.get("broken", false)):
			continue
		var grect: Rect2 = (g.get("rect", Rect2()) as Rect2).grow(2.0)
		if grect.intersects(check_rect):
			return true
	return false


func is_point_solid(pt: Vector2, include_clouds: bool = false) -> bool:
	for r: Rect2 in solid_rects:
		if r.has_point(pt):
			return true
	for gr: Rect2 in get_intact_horizontal_glass_rects():
		if gr.has_point(pt):
			return true
	for sp: Dictionary in slope_polygons:
		if bool(sp.get("is_cloud", false)) and not include_clouds:
			continue
		var brect: Rect2 = sp.get("bounds_rect", Rect2()) as Rect2
		if brect.has_point(pt):
			var wpts: PackedVector2Array = sp.get("world_points", PackedVector2Array()) as PackedVector2Array
			if Geometry2D.is_point_in_polygon(pt, wpts):
				return true
	if include_clouds:
		for cr: Rect2 in cloud_rects:
			if cr.has_point(pt):
				return true
		for el: Dictionary in elevators:
			var er: Rect2 = el.get("rect", Rect2()) as Rect2
			if er.has_point(pt):
				return true
	return false


func check_and_break_glass_segment(from_pt: Vector2, to_pt: Vector2, impact_vel: Vector2) -> bool:
	var broke_any: bool = false
	var seg_min_x: float = minf(from_pt.x, to_pt.x) - 3.0
	var seg_max_x: float = maxf(from_pt.x, to_pt.x) + 3.0
	var seg_min_y: float = minf(from_pt.y, to_pt.y) - 3.0
	var seg_max_y: float = maxf(from_pt.y, to_pt.y) + 3.0
	for i: int in range(glasses.size()):
		var g: Dictionary = glasses[i]
		if bool(g.get("broken", false)):
			continue
		var grect_raw: Rect2 = g.get("rect", Rect2()) as Rect2
		if seg_max_x < grect_raw.position.x or seg_min_x > grect_raw.end.x or seg_max_y < grect_raw.position.y or seg_min_y > grect_raw.end.y:
			continue
		var gp1: Vector2 = g.get("p1", Vector2.ZERO) as Vector2
		var gp2: Vector2 = g.get("p2", Vector2.ZERO) as Vector2
		var hit_var: Variant = Geometry2D.segment_intersects_segment(from_pt, to_pt, gp1, gp2)
		var is_hit: bool = hit_var != null
		if not is_hit:
			var grect: Rect2 = grect_raw.grow(2.0)
			if grect.has_point(from_pt) or grect.has_point(to_pt):
				is_hit = true
		if is_hit:
			g["broken"] = true
			g["hp"] = 0.0
			broke_any = true
			_h_glass_cache_dirty = true
			var spawned_shards2: bool = false
			if match_world != null and is_instance_valid(match_world):
				var fhs: Variant = match_world.get("fire_hazard_system")
				if fhs != null and is_instance_valid(fhs) and fhs.has_method("spawn_glass_shards"):
					fhs.call("spawn_glass_shards", gp1, gp2, impact_vel)
					spawned_shards2 = true
			if not spawned_shards2:
				play_sfx_at("glass", (gp1 + gp2) * 0.5)
	if broke_any and _fx_overlay_node != null:
		_fx_overlay_node.queue_redraw()
	return broke_any


const _EMPTY_RAY_HIT: Dictionary = {"hit": false}


func raycast_solid(from_pt: Vector2, to_pt: Vector2, ignore_cover_id: int = -1, include_props: bool = true) -> Dictionary:
	var best_t: float = INF
	var best_pos: Vector2 = to_pt
	var best_normal: Vector2 = Vector2.UP
	var best_prop: Node2D = null
	var hit_glass_idx: int = -1

	var seg_min_x: float = minf(from_pt.x, to_pt.x) - 1.0
	var seg_max_x: float = maxf(from_pt.x, to_pt.x) + 1.0
	var seg_min_y: float = minf(from_pt.y, to_pt.y) - 1.0
	var seg_max_y: float = maxf(from_pt.y, to_pt.y) + 1.0

	# Check glass intersections first (and record index)
	for gi: int in range(glasses.size()):
		var g: Dictionary = glasses[gi]
		if bool(g.get("broken", false)):
			continue
		var grect_g: Rect2 = g.get("rect", Rect2()) as Rect2
		if seg_max_x < grect_g.position.x or seg_min_x > grect_g.end.x or seg_max_y < grect_g.position.y or seg_min_y > grect_g.end.y:
			continue
		var gp1: Vector2 = g.get("p1", Vector2.ZERO) as Vector2
		var gp2: Vector2 = g.get("p2", Vector2.ZERO) as Vector2
		var ghit: Variant = Geometry2D.segment_intersects_segment(from_pt, to_pt, gp1, gp2)
		if ghit != null:
			hit_glass_idx = gi
			break

	# 1. Check solid rects (with AABB filter inside _segment_vs_rect)
	for r: Rect2 in solid_rects:
		if seg_max_x < r.position.x or seg_min_x > r.end.x or seg_max_y < r.position.y or seg_min_y > r.end.y:
			continue
		var hit_info: Dictionary = _segment_vs_rect(from_pt, to_pt, r)
		if bool(hit_info.get("hit", false)):
			var t: float = float(hit_info.get("t", 1.0))
			if t < best_t:
				best_t = t
				best_pos = hit_info.get("pos", to_pt) as Vector2
				best_normal = hit_info.get("normal", Vector2.UP) as Vector2
				best_prop = null

	# 2. Check slope polygons (with AABB bounds_rect pre-filter)
	for sp: Dictionary in slope_polygons:
		var sbounds: Rect2 = sp.get("bounds_rect", Rect2()) as Rect2
		if seg_max_x < sbounds.position.x or seg_min_x > sbounds.end.x or seg_max_y < sbounds.position.y or seg_min_y > sbounds.end.y:
			continue
		var wpts: PackedVector2Array = sp.get("world_points", PackedVector2Array()) as PackedVector2Array
		if wpts.size() >= 3 and sbounds.has_point(from_pt) and Geometry2D.is_point_in_polygon(from_pt, wpts):
			return {
				"hit": true,
				"pos": from_pt,
				"normal": Vector2.UP,
				"glass_idx": hit_glass_idx,
				"prop": null,
			}
		var n: int = wpts.size()
		var seg_len: float = maxf(0.0001, from_pt.distance_to(to_pt))
		for i: int in range(n):
			var a: Vector2 = wpts[i]
			var b: Vector2 = wpts[(i + 1) % n]
			var isect: Variant = Geometry2D.segment_intersects_segment(from_pt, to_pt, a, b)
			if isect != null:
				var ipos: Vector2 = isect as Vector2
				var t: float = from_pt.distance_to(ipos) / seg_len
				if t < best_t:
					best_t = t
					best_pos = ipos
					var edge: Vector2 = (b - a).normalized()
					var cand_n: Vector2 = Vector2(edge.y, -edge.x)
					if cand_n.dot(to_pt - from_pt) > 0.0:
						cand_n = -cand_n
					best_normal = cand_n
					best_prop = null

	# 3. Check active interactive props in match_world (only when include_props is true)
	if include_props and match_world != null and is_instance_valid(match_world):
		var props_var: Variant = match_world.get("props")
		if typeof(props_var) == TYPE_ARRAY:
			for p_var: Variant in props_var as Array:
				if not (p_var is Node2D) or not is_instance_valid(p_var):
					continue
				var prop: Node2D = p_var as Node2D
				if bool(prop.get("is_destroyed")):
					continue
				var ppos: Vector2 = prop.global_position
				if ppos.x + 28.0 < seg_min_x or ppos.x - 28.0 > seg_max_x or ppos.y + 28.0 < seg_min_y or ppos.y - 28.0 > seg_max_y:
					continue
				var pid: int = int(prop.get("prop_id")) if prop.get("prop_id") != null else prop.get_instance_id()
				if ignore_cover_id != -1 and (pid == ignore_cover_id or prop.get_instance_id() == ignore_cover_id):
					continue
				var prect: Rect2
				if prop.has_method("get_world_rect"):
					prect = prop.call("get_world_rect") as Rect2
				else:
					var pw: float = float(prop.get("width")) if prop.get("width") != null else 14.0
					var ph: float = float(prop.get("height")) if prop.get("height") != null else 14.0
					prect = Rect2(ppos.x - pw * 0.5, ppos.y - ph * 0.5, pw, ph)
				if seg_max_x < prect.position.x or seg_min_x > prect.end.x or seg_max_y < prect.position.y or seg_min_y > prect.end.y:
					continue
				var hit_info: Dictionary = _segment_vs_rect(from_pt, to_pt, prect)
				if bool(hit_info.get("hit", false)):
					var t: float = float(hit_info.get("t", 1.0))
					if t < best_t:
						best_t = t
						best_pos = hit_info.get("pos", to_pt) as Vector2
						best_normal = hit_info.get("normal", Vector2.UP) as Vector2
						best_prop = prop

	return {
		"hit": best_t <= 1.0,
		"pos": best_pos,
		"normal": best_normal,
		"prop": best_prop,
		"glass_idx": hit_glass_idx,
	}


func _segment_vs_rect(from_pt: Vector2, to_pt: Vector2, r: Rect2) -> Dictionary:
	var seg_min_x: float = minf(from_pt.x, to_pt.x)
	var seg_max_x: float = maxf(from_pt.x, to_pt.x)
	if seg_max_x < r.position.x or seg_min_x > r.end.x:
		return _EMPTY_RAY_HIT
	var seg_min_y: float = minf(from_pt.y, to_pt.y)
	var seg_max_y: float = maxf(from_pt.y, to_pt.y)
	if seg_max_y < r.position.y or seg_min_y > r.end.y:
		return _EMPTY_RAY_HIT

	if r.has_point(from_pt):
		return {"hit": true, "t": 0.0, "pos": from_pt, "normal": (from_pt - r.get_center()).normalized()}

	var c0: Vector2 = r.position
	var c1: Vector2 = Vector2(r.end.x, r.position.y)
	var c2: Vector2 = r.end
	var c3: Vector2 = Vector2(r.position.x, r.end.y)
	var best_t: float = INF
	var best_pos: Vector2 = to_pt
	var best_n: Vector2 = Vector2.UP
	var total_len: float = maxf(0.0001, from_pt.distance_to(to_pt))

	# Top edge (c0 -> c1, normal UP)
	var isect0: Variant = Geometry2D.segment_intersects_segment(from_pt, to_pt, c0, c1)
	if isect0 != null:
		var ip0: Vector2 = isect0 as Vector2
		var t0: float = from_pt.distance_to(ip0) / total_len
		if t0 < best_t:
			best_t = t0
			best_pos = ip0
			best_n = Vector2.UP

	# Right edge (c1 -> c2, normal RIGHT)
	var isect1: Variant = Geometry2D.segment_intersects_segment(from_pt, to_pt, c1, c2)
	if isect1 != null:
		var ip1: Vector2 = isect1 as Vector2
		var t1: float = from_pt.distance_to(ip1) / total_len
		if t1 < best_t:
			best_t = t1
			best_pos = ip1
			best_n = Vector2.RIGHT

	# Bottom edge (c2 -> c3, normal DOWN)
	var isect2: Variant = Geometry2D.segment_intersects_segment(from_pt, to_pt, c2, c3)
	if isect2 != null:
		var ip2: Vector2 = isect2 as Vector2
		var t2: float = from_pt.distance_to(ip2) / total_len
		if t2 < best_t:
			best_t = t2
			best_pos = ip2
			best_n = Vector2.DOWN

	# Left edge (c3 -> c0, normal LEFT)
	var isect3: Variant = Geometry2D.segment_intersects_segment(from_pt, to_pt, c3, c0)
	if isect3 != null:
		var ip3: Vector2 = isect3 as Vector2
		var t3: float = from_pt.distance_to(ip3) / total_len
		if t3 < best_t:
			best_t = t3
			best_pos = ip3
			best_n = Vector2.LEFT

	if best_t <= 1.0:
		return {"hit": true, "t": best_t, "pos": best_pos, "normal": best_n}
	return _EMPTY_RAY_HIT


func get_ladder_at(pt: Vector2) -> Rect2:
	for lr: Rect2 in ladder_rects:
		if lr.has_point(pt):
			return lr
	return Rect2()


func find_cover_prop_near(pt: Vector2, dir_x: int) -> int:
	var fdir: float = 1.0 if dir_x >= 0 else -1.0
	var probe_x: float = pt.x + fdir * 8.0
	var mid_y: float = pt.y - 8.0
	if match_world != null and is_instance_valid(match_world):
		var props_var: Variant = match_world.get("props")
		if typeof(props_var) == TYPE_ARRAY:
			for p_var: Variant in props_var as Array:
				if not (p_var is Node2D) or not is_instance_valid(p_var):
					continue
				var prop: Node2D = p_var as Node2D
				if bool(prop.get("is_destroyed")):
					continue
				var can_cover: bool = bool(prop.get("allow_cover"))
				if not can_cover:
					continue
				var prect: Rect2 = prop.call("get_world_rect") as Rect2 if prop.has_method("get_world_rect") else Rect2(prop.global_position.x - 7.0, prop.global_position.y - 7.0, 14.0, 14.0)
				var dx_center: float = (prop.global_position.x - pt.x) * fdir
				if dx_center > 0.0 and probe_x >= prect.position.x - 2.5 and probe_x <= prect.end.x + 2.5:
					if mid_y >= prect.position.y - 2.5 and mid_y <= prect.end.y + 2.5 and prect.position.y >= pt.y - 22.0:
						var pid: Variant = prop.get("prop_id")
						return int(pid) if pid != null else prop.get_instance_id()
	return -1


func get_ground_y_below(x: float, y_from: float, max_drop: float = 60.0, include_clouds: bool = true) -> float:
	var best_y: float = INF
	var y_limit: float = y_from + max_drop

	for r: Rect2 in solid_rects:
		if x >= r.position.x - 2.0 and x <= r.end.x + 2.0:
			var top_y: float = r.position.y
			if top_y >= y_from - 4.0 and top_y <= y_limit and top_y < best_y:
				best_y = top_y

	for gr: Rect2 in get_intact_horizontal_glass_rects():
		if gr.size.x >= gr.size.y and x >= gr.position.x - 1.0 and x <= gr.end.x + 1.0:
			var top_y: float = gr.position.y
			if top_y >= y_from - 4.0 and top_y <= y_limit and top_y < best_y:
				best_y = top_y

	if include_clouds:
		for cr: Rect2 in cloud_rects:
			if x >= cr.position.x - 2.0 and x <= cr.end.x + 2.0:
				var top_y: float = cr.position.y
				if top_y >= y_from - 4.0 and top_y <= y_limit and top_y < best_y:
					best_y = top_y
		for el: Dictionary in elevators:
			var er: Rect2 = el.get("rect", Rect2()) as Rect2
			if x >= er.position.x - 2.0 and x <= er.end.x + 2.0:
				var top_y: float = er.position.y
				if top_y >= y_from - 6.0 and top_y <= y_limit and top_y < best_y:
					best_y = top_y
		if match_world != null and is_instance_valid(match_world):
			var props_var: Variant = match_world.get("props")
			if typeof(props_var) == TYPE_ARRAY:
				for p_var: Variant in props_var as Array:
					if p_var is Node2D and is_instance_valid(p_var):
						var prop: Node2D = p_var as Node2D
						if not bool(prop.get("is_destroyed")) and bool(prop.get("is_hanging_crate")) and (not bool(prop.get("is_hanging_released")) or bool(prop.get("on_ground"))):
							var top_y: float = INF
							if prop.has_method("get_obb_top_y_at_x"):
								top_y = float(prop.call("get_obb_top_y_at_x", x, 2.0))
							else:
								var prect: Rect2 = prop.call("get_solid_support_rect") as Rect2 if prop.has_method("get_solid_support_rect") else Rect2()
								if prect.size.x > 0.0 and x >= prect.position.x - 2.0 and x <= prect.end.x + 2.0:
									top_y = prect.position.y
							if top_y < INF and top_y >= y_from - 6.0 and top_y <= y_limit and top_y < best_y:
								best_y = top_y

	for sp: Dictionary in slope_polygons:
		var brect: Rect2 = sp.get("bounds_rect", Rect2()) as Rect2
		if x >= brect.position.x - 1.0 and x <= brect.end.x + 1.0:
			var wpts: PackedVector2Array = sp.get("world_points", PackedVector2Array()) as PackedVector2Array
			var n: int = wpts.size()
			var top_idx: int = int(sp.get("top_edge_idx", -1))
			for i: int in range(n):
				if top_idx >= 0 and i != top_idx:
					continue
				var a: Vector2 = wpts[i]
				var b: Vector2 = wpts[(i + 1) % n]
				# Ignore bottom horizontal closing edge of stair polygons
				if minf(a.y, b.y) >= brect.end.y - 1.5 and maxf(a.y, b.y) >= brect.end.y - 1.5:
					continue
				var min_seg_x: float = minf(a.x, b.x)
				var max_seg_x: float = maxf(a.x, b.x)
				if x >= min_seg_x - 0.5 and x <= max_seg_x + 0.5 and absf(b.x - a.x) > 0.01:
					var t: float = clampf((x - a.x) / (b.x - a.x), 0.0, 1.0)
					var sy: float = lerpf(a.y, b.y, t)
					if sy >= y_from - 16.0 and sy <= y_limit and sy < best_y:
						best_y = sy

	return best_y


func get_slope_ground_y_below(
	x: float,
	foot_y: float,
	max_step_up: float = 6.5,
	max_step_down: float = 9.0,
	include_cloud_slopes: bool = true
) -> float:
	var best_y: float = INF
	for sp: Dictionary in slope_polygons:
		if bool(sp.get("is_cloud", false)) and not include_cloud_slopes:
			continue
		var brect: Rect2 = sp.get("bounds_rect", Rect2()) as Rect2
		if x >= brect.position.x - 1.0 and x <= brect.end.x + 1.0:
			var wpts: PackedVector2Array = sp.get("world_points", PackedVector2Array()) as PackedVector2Array
			var n: int = wpts.size()
			var top_idx_s: int = int(sp.get("top_edge_idx", -1))
			var poly_top_y: float = INF
			for i: int in range(n):
				if top_idx_s >= 0 and i != top_idx_s:
					continue
				var a: Vector2 = wpts[i]
				var b: Vector2 = wpts[(i + 1) % n]
				var min_seg_x: float = minf(a.x, b.x)
				var max_seg_x: float = maxf(a.x, b.x)
				if x >= min_seg_x - 0.5 and x <= max_seg_x + 0.5 and absf(b.x - a.x) > 0.01:
					var t: float = clampf((x - a.x) / (b.x - a.x), 0.0, 1.0)
					var sy: float = lerpf(a.y, b.y, t)
					if sy < poly_top_y:
						poly_top_y = sy
			if poly_top_y < INF and poly_top_y >= foot_y - max_step_up and poly_top_y <= foot_y + max_step_down and poly_top_y < best_y:
				best_y = poly_top_y
	return best_y


func _draw_map_fx_overlay(canvas: CanvasItem) -> void:
	# 1. Draw intact glass windows (translucent cyan/white panes)
	for g: Dictionary in glasses:
		if bool(g.get("broken", false)):
			continue
		var p1: Vector2 = g.get("p1", Vector2.ZERO) as Vector2
		var p2: Vector2 = g.get("p2", Vector2.ZERO) as Vector2
		canvas.draw_line(p1, p2, Color(0.55, 0.9, 1.0, 0.68), 3.0)
		canvas.draw_line(p1, p2, Color(0.92, 0.98, 1.0, 0.88), 1.0)

	# 2. Draw swinging hanging lamps
	for lamp: Dictionary in hanging_lamps:
		var anchor: Vector2 = Vector2(float(lamp.get("x", 0.0)), float(lamp.get("y", 0.0)))
		var rlen: float = float(lamp.get("rope_length", 25.0))
		var ang: float = float(lamp.get("angle", 0.0))
		var tip: Vector2 = anchor + Vector2(sin(ang) * rlen, cos(ang) * rlen)
		canvas.draw_line(anchor, tip, Color(0.18, 0.18, 0.2, 0.95), 1.2)
		canvas.draw_circle(tip, 3.0, Color(0.98, 0.92, 0.55, 0.95))
		canvas.draw_circle(tip + Vector2(0.0, 2.0), 7.0, Color(1.0, 0.95, 0.65, 0.16))

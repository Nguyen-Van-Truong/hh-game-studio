class_name FireHazardSystem
extends Node2D
## 36-Ray Explosion & Multi-Frame Authentic Sprite VFX System (Explosions.as, Fires.as, Particles) for Superfighters Y8.

const FIRE_GRAVITY_24HZ: float = 0.18
const SHELL_GRAVITY_24HZ: float = 0.48
const DEBRIS_GRAVITY_24HZ: float = 0.45
const PAPER_GRAVITY_24HZ: float = 0.12
const EXPLOSION_RAY_COUNT: int = 36

const MAX_FIRE_PARTICLES: int = 64
const MAX_FLAME_PUFFS: int = 110
const MAX_SMOKE_PUFFS: int = 80
const MAX_DEBRIS: int = 56
const MAX_SPARKS: int = 40
const MAX_SHELLS: int = 36
const MAX_SHARDS: int = 48

var match_world: Node2D = null
var external_fighters: Array = []
var default_floor_y: float = 154.0
var _frame_support_rects: Array[Rect2] = []
var _frame_support_cached: bool = false

var fire_particles: Array[Dictionary] = []
var flame_puffs: Array[Dictionary] = []
var explosions: Array[Dictionary] = []
var explosion_rings: Array[Dictionary] = []
var smoke_puffs: Array[Dictionary] = []
var muzzle_flashes: Array[Dictionary] = []
var shell_casings: Array[Dictionary] = []
var hit_sparks: Array[Dictionary] = []
var prop_debris: Array[Dictionary] = []
var electric_sparks: Array[Dictionary] = []
var melee_traces: Array[Dictionary] = []
var glass_shards: Array[Dictionary] = []
var gibs: Array[Dictionary] = []

var total_explosions_triggered: int = 0
var total_fire_bursts_triggered: int = 0
var _fire_sfx_cooldown: float = 0.0
var _shell_sfx_cooldown: float = 0.0
var _visual_tick: float = 0.0
var _tracked_fighter_states: Dictionary = {}
var _fighter_burn_emit_state: Dictionary = {}

var _textures_loaded: bool = false
var _fire_01_seq: Array[Texture2D] = []
var _fire_02_seq: Array[Texture2D] = []
var _fire_03_seq: Array[Texture2D] = []
var _fire_big_seq: Array[Texture2D] = []
var _fire_ground_seq: Array[Texture2D] = []
var _flamethrower_seq: Array[Texture2D] = []
var _explosion_centrum_seq: Array[Texture2D] = []
var _explosion_circle_seq: Array[Texture2D] = []
var _smoke_trace_seq: Array[Texture2D] = []
var _smoke_light_seq: Array[Texture2D] = []

var _muzzle_pistol_seq: Array[Texture2D] = []
var _muzzle_rifle_seq: Array[Texture2D] = []
var _muzzle_shotgun_seq: Array[Texture2D] = []
var _muzzle_sniper_seq: Array[Texture2D] = []
var _muzzle_bazooka_seq: Array[Texture2D] = []
var _muzzle_smoke_seq: Array[Texture2D] = []

var _tex_shell_small: Texture2D = null
var _tex_shell_big: Texture2D = null
var _tex_shell_shotgun: Texture2D = null

var _hit_metal_seq: Array[Texture2D] = []
var _electric_seq: Array[Texture2D] = []
var _trace_axe_seq: Array[Texture2D] = []
var _trace_machete_seq: Array[Texture2D] = []
var _trace_sword_seq: Array[Texture2D] = []

var _debris_crate_seq: Array[Texture2D] = []
var _debris_barrel_seq: Array[Texture2D] = []
var _debris_table_seq: Array[Texture2D] = []
var _debris_paper_seq: Array[Texture2D] = []

var _tex_glass: Texture2D = null
var _tex_blood: Texture2D = null
var _tex_gib: Texture2D = null


func _init() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	z_index = 15


func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	z_index = 15
	_load_effect_textures()


func _load_tex(res_path: String) -> Texture2D:
	var reg: Object = _get_registry()
	if reg != null and reg.has_method("load_cached_texture"):
		var t: Texture2D = reg.call("load_cached_texture", res_path) as Texture2D
		if t != null:
			return t
	if ResourceLoader.exists(res_path):
		var res: Resource = ResourceLoader.load(res_path)
		if res is Texture2D:
			return res as Texture2D
	var abs_path: String = ProjectSettings.globalize_path(res_path)
	if FileAccess.file_exists(abs_path):
		var img: Image = Image.load_from_file(abs_path)
		if img != null and not img.is_empty():
			return ImageTexture.create_from_image(img)
	return null


func _load_seq(prefix_path: String, count: int, digits: int = 2) -> Array[Texture2D]:
	var out: Array[Texture2D] = []
	for i: int in range(1, count + 1):
		var num_str: String = str(i).pad_zeros(digits)
		var tex: Texture2D = _load_tex(prefix_path + num_str + ".png")
		if tex != null:
			out.append(tex)
	return out


func _load_effect_textures() -> void:
	if _textures_loaded:
		return
	_textures_loaded = true

	_fire_01_seq = _load_seq("res://assets/sprites/effects/fire_01_f", 11, 2)
	_fire_02_seq = _load_seq("res://assets/sprites/effects/fire_02_f", 11, 2)
	_fire_03_seq = _load_seq("res://assets/sprites/effects/fire_03_f", 10, 2)
	_fire_big_seq = _load_seq("res://assets/sprites/effects/fire_big_f", 11, 2)
	_fire_ground_seq = _load_seq("res://assets/sprites/effects/fire_ground_", 3, 2)
	_flamethrower_seq = _load_seq("res://assets/sprites/effects/fire_flamethrower_f", 12, 2)

	_explosion_centrum_seq = _load_seq("res://assets/sprites/effects/explosion_centrum_f", 14, 2)
	_explosion_circle_seq = _load_seq("res://assets/sprites/effects/explosion_circle_f", 8, 2)
	_smoke_trace_seq = _load_seq("res://assets/sprites/effects/smoke_trace_f", 10, 2)
	_smoke_light_seq = _load_seq("res://assets/sprites/effects/smoke_light_f", 9, 2)

	_muzzle_pistol_seq = _load_seq("res://assets/sprites/effects/muzzle_pistol_", 2, 2)
	_muzzle_rifle_seq = _load_seq("res://assets/sprites/effects/muzzle_rifle_", 2, 2)
	_muzzle_shotgun_seq = _load_seq("res://assets/sprites/effects/muzzle_shotgun_", 2, 2)
	_muzzle_sniper_seq = _load_seq("res://assets/sprites/effects/muzzle_sniper_", 3, 2)
	_muzzle_bazooka_seq = _load_seq("res://assets/sprites/effects/muzzle_bazooka_", 4, 2)
	_muzzle_smoke_seq = _load_seq("res://assets/sprites/effects/muzzle_smoke_f", 13, 2)

	_tex_shell_small = _load_tex("res://assets/sprites/effects/shell_small.png")
	_tex_shell_big = _load_tex("res://assets/sprites/effects/shell_big.png")
	_tex_shell_shotgun = _load_tex("res://assets/sprites/effects/shell_shotgun.png")

	_hit_metal_seq = _load_seq("res://assets/sprites/effects/hit_metal_f", 6, 2)
	_electric_seq = _load_seq("res://assets/sprites/effects/electric_f", 9, 2)
	_trace_axe_seq = _load_seq("res://assets/sprites/effects/trace_axe_", 3, 2)
	_trace_machete_seq = _load_seq("res://assets/sprites/effects/trace_machete_", 3, 2)
	_trace_sword_seq = _load_seq("res://assets/sprites/effects/trace_sword_", 3, 2)

	_debris_crate_seq = _load_seq("res://assets/sprites/props/debris_crate_", 3, 2)
	_debris_barrel_seq = _load_seq("res://assets/sprites/props/debris_barrel_", 3, 2)
	_debris_table_seq = _load_seq("res://assets/sprites/props/debris_table_", 3, 2)
	_debris_paper_seq = _load_seq("res://assets/sprites/props/debris_paper_", 4, 2)

	_tex_glass = _load_tex("res://assets/sprites/effects/glass_shard_1.png")
	_tex_blood = _load_tex("res://assets/sprites/effects/blood_1.png")
	_tex_gib = _load_tex("res://assets/sprites/effects/char_gib_01.png")


func _get_registry() -> Object:
	var tree: SceneTree = Engine.get_main_loop() as SceneTree
	if tree != null and tree.root != null:
		return tree.root.get_node_or_null("SFDataRegistry")
	return null


func _play_sfx(sound_id: String, pos: Vector2) -> void:
	if DisplayServer.get_name() == "headless":
		return
	var tree: SceneTree = Engine.get_main_loop() as SceneTree
	if tree != null and tree.root != null:
		var audio: Node = tree.root.get_node_or_null("AudioManager")
		if audio != null and audio.is_inside_tree() and audio.has_method("play_sfx_at"):
			audio.call("play_sfx_at", sound_id, pos)


func _get_map_loader() -> Object:
	if match_world != null:
		var ml: Variant = match_world.get("map_loader")
		if ml is Object:
			return ml as Object
	return null


func _get_fighters() -> Array:
	var out: Array = []
	if match_world != null:
		var f_var: Variant = match_world.get("fighters")
		if typeof(f_var) == TYPE_ARRAY:
			for item: Variant in f_var as Array:
				if is_instance_valid(item) and not out.has(item):
					out.append(item)
	for ef: Variant in external_fighters:
		if is_instance_valid(ef) and not out.has(ef):
			out.append(ef)
	return out


func _get_props() -> Array:
	if match_world != null:
		var p_var: Variant = match_world.get("props")
		if typeof(p_var) == TYPE_ARRAY:
			return p_var as Array
	return []


func _rebuild_support_rects_cache() -> void:
	_frame_support_rects.clear()
	for p_var: Variant in _get_props():
		if not is_instance_valid(p_var):
			continue
		var prop: Node2D = p_var as Node2D
		if bool(prop.get("is_destroyed")) or not bool(prop.get("has_solid_hitbox")):
			continue
		if not bool(prop.get("on_ground")) and not bool(prop.get("kinematic")):
			continue
		if prop.has_method("get_solid_support_rect"):
			var pr: Rect2 = prop.call("get_solid_support_rect") as Rect2
			if pr.size.x > 0.0:
				_frame_support_rects.append(pr)
	_frame_support_cached = true


func _is_point_on_floor(pt: Vector2) -> bool:
	var ml: Object = _get_map_loader()
	if ml != null and ml.has_method("is_point_solid"):
		if bool(ml.call("is_point_solid", pt, true)):
			return true
	if not _frame_support_cached:
		_rebuild_support_rects_cache()
	for pr: Rect2 in _frame_support_rects:
		if pr.has_point(pt):
			return true
	if ml != null:
		return false
	return pt.y >= default_floor_y


func _find_floor_y_between(prev_pt: Vector2, next_pt: Vector2) -> float:
	if next_pt.y >= prev_pt.y:
		var ml: Object = _get_map_loader()
		if ml != null and ml.has_method("get_ground_y_below"):
			var drop_dist: float = maxf(4.0, (next_pt.y - prev_pt.y) + 3.0)
			var gy: float = float(ml.call("get_ground_y_below", next_pt.x, prev_pt.y - 2.0, drop_dist, true))
			if gy < INF and next_pt.y >= gy - 0.5:
				return gy
	if _is_point_on_floor(next_pt):
		return next_pt.y
	return INF


func _segment_hits_rect(p1: Vector2, p2: Vector2, rect: Rect2) -> bool:
	var min_x: float = minf(p1.x, p2.x)
	var max_x: float = maxf(p1.x, p2.x)
	if max_x < rect.position.x or min_x > rect.end.x:
		return false
	var min_y: float = minf(p1.y, p2.y)
	var max_y: float = maxf(p1.y, p2.y)
	if max_y < rect.position.y or min_y > rect.end.y:
		return false
	if rect.has_point(p1) or rect.has_point(p2):
		return true
	var tl: Vector2 = rect.position
	var tr: Vector2 = Vector2(rect.end.x, rect.position.y)
	var br: Vector2 = rect.end
	var bl: Vector2 = Vector2(rect.position.x, rect.end.y)
	if Geometry2D.segment_intersects_segment(p1, p2, tl, tr) != null:
		return true
	if Geometry2D.segment_intersects_segment(p1, p2, tr, br) != null:
		return true
	if Geometry2D.segment_intersects_segment(p1, p2, br, bl) != null:
		return true
	if Geometry2D.segment_intersects_segment(p1, p2, bl, tl) != null:
		return true
	return false


func is_explosion_line_blocked(from_pt: Vector2, to_pt: Vector2, target_prop: Node2D = null) -> bool:
	var total_dist: float = from_pt.distance_to(to_pt)
	if total_dist <= 1.0:
		return false
	var ml: Object = _get_map_loader()
	if ml != null and ml.has_method("raycast_solid"):
		var ray_from: Vector2 = from_pt.move_toward(to_pt, minf(2.0, total_dist * 0.25))
		var occ: Dictionary = ml.call("raycast_solid", ray_from, to_pt, -1, false) as Dictionary
		if bool(occ.get("hit", false)):
			var hit_p: Vector2 = occ.get("pos", to_pt) as Vector2
			if ray_from.distance_to(hit_p) + 2.5 < ray_from.distance_to(to_pt):
				return true

	# AS3 Explosions.as:237-263 & MapPremadeItems.as:1585:
	# CRATE_HANGING (CanBlockExplosions = true, Indestructible = true) completely shields CRATE_HANGING_HOLDER above it from blasts below!
	if target_prop != null and is_instance_valid(target_prop) and bool(target_prop.get("is_hanging_holder")):
		var hcrate: Node2D = target_prop.get("attached_hanging_crate") as Node2D
		if hcrate != null and is_instance_valid(hcrate) and not bool(hcrate.get("is_destroyed")) and not bool(hcrate.get("is_hanging_released")):
			var c_rect: Rect2 = hcrate.call("get_world_rect") as Rect2 if hcrate.has_method("get_world_rect") else Rect2(hcrate.global_position.x - 14.0, hcrate.global_position.y - 7.5, 28.0, 15.0)
			if _segment_hits_rect(from_pt, to_pt, c_rect.grow(1.0)) or (from_pt.y >= c_rect.position.y + 1.0 and absf(from_pt.x - hcrate.global_position.x) <= c_rect.size.x * 0.65):
				return true

	# Check all explosion-blocking obstacles (CanBlockExplosions: CRATE_HANGING, STATUE, DESK, POOL_TABLE, FILECAB, BARREL)
	for p_var: Variant in _get_props():
		if not is_instance_valid(p_var):
			continue
		var p: Node2D = p_var as Node2D
		if p == target_prop or bool(p.get("is_destroyed")) or not bool(p.get("can_block_explosions")):
			continue
		if from_pt.distance_to(p.global_position) < 2.5 and not bool(p.get("indestructible")):
			continue
		var p_rect: Rect2 = p.call("get_world_rect") as Rect2 if p.has_method("get_world_rect") else Rect2(p.global_position.x - 8.0, p.global_position.y - 8.0, 16.0, 16.0)
		var shrink_rect: Rect2 = p_rect.grow(-0.5) if (p_rect.size.x > 4.0 and p_rect.size.y > 4.0) else p_rect
		if shrink_rect.has_point(to_pt):
			continue
		if _segment_hits_rect(from_pt, to_pt, shrink_rect):
			return true
	return false


func trigger_explosion(
	world_pos: Vector2,
	base_radius: float = 33.0,
	player_damage: float = 20.0,
	player_power: float = 5.0,
	source_fighter: Node2D = null
) -> void:
	_load_effect_textures()
	total_explosions_triggered += 1
	_play_sfx("explosion", world_pos)

	var ml: Object = _get_map_loader()
	var props: Array = _get_props()
	var blocking_prop_rects: Array[Rect2] = []
	for bp_var: Variant in props:
		if not is_instance_valid(bp_var):
			continue
		var bp: Node2D = bp_var as Node2D
		if bool(bp.get("is_destroyed")) or not bool(bp.get("can_block_explosions")):
			continue
		var bpr: Rect2 = bp.call("get_world_rect") as Rect2 if bp.has_method("get_world_rect") else Rect2(bp.global_position.x - 8.0, bp.global_position.y - 8.0, 16.0, 16.0)
		blocking_prop_rects.append(bpr)

	var ray_endpoints: PackedVector2Array = PackedVector2Array()
	var unblocked_count: int = 0
	var blocked_sum: float = 0.0

	# 1. Cast 36 rays for occlusion & glass breaking (Explosions.as:152-266: walls & CanBlockExplosions props stop rays)
	for i: int in range(EXPLOSION_RAY_COUNT):
		var angle_rad: float = float(i) * TAU / float(EXPLOSION_RAY_COUNT)
		var dir: Vector2 = Vector2(cos(angle_rad), sin(angle_rad))
		var ray_len: float = base_radius * randf_range(1.0, 1.35)
		var end_pt: Vector2 = world_pos + dir * ray_len
		var hit_solid_ray: bool = false

		if ml != null:
			if ml.has_method("check_and_break_glass_segment"):
				ml.call("check_and_break_glass_segment", world_pos, end_pt, dir * 8.0)
			if ml.has_method("raycast_solid"):
				var hit: Dictionary = ml.call("raycast_solid", world_pos, end_pt, -1, false) as Dictionary
				if bool(hit.get("hit", false)):
					end_pt = hit.get("pos", end_pt) as Vector2
					hit_solid_ray = true
		for bpr: Rect2 in blocking_prop_rects:
			if _segment_hits_rect(world_pos, end_pt, bpr):
				# Step-clip ray against blocking prop (Explosions.as:242-262)
				for s_step: int in range(1, 14):
					var test_pt: Vector2 = world_pos.lerp(end_pt, float(s_step) / 14.0)
					if bpr.has_point(test_pt):
						end_pt = test_pt
						hit_solid_ray = true
						break
		var actual_len: float = world_pos.distance_to(end_pt)
		if hit_solid_ray and actual_len < base_radius:
			blocked_sum += (base_radius - actual_len)
		else:
			unblocked_count += 1
		ray_endpoints.append(end_pt)

	# AS3 Explosions.as:212: confined-space pressure redistribution (up to 1.5x radius when blocked)
	var eff_radius: float = base_radius
	if unblocked_count > 0 and blocked_sum > 0.0:
		eff_radius = base_radius + minf((blocked_sum / float(unblocked_count)) * 0.25, base_radius * 0.5)
	var max_reach: float = maxf(eff_radius, base_radius * 1.35)

	# 2. Damage and knockback fighters in blast radius (Explosions.as:345-378: occluded by walls & CanBlockExplosions props)
	var fighters: Array = _get_fighters()
	for f_var: Variant in fighters:
		if not is_instance_valid(f_var):
			continue
		var f: Node2D = f_var as Node2D
		var f_mid: Vector2 = f.global_position + Vector2(0.0, -8.0)
		if f.has_method("get_mid_pos"):
			f_mid = f.call("get_mid_pos") as Vector2
		var dist: float = world_pos.distance_to(f_mid)
		if dist <= max_reach:
			var blocked: bool = false
			if dist > 2.5:
				var check_pts: Array[Vector2] = [
					f_mid,
					f.global_position + Vector2(0.0, -3.0),
					f.global_position + Vector2(0.0, -14.0),
				]
				var clear_rays: int = 0
				for t_pt: Vector2 in check_pts:
					if not is_explosion_line_blocked(world_pos, t_pt, null):
						clear_rays += 1
				if clear_rays == 0:
					blocked = true
			if not blocked:
				var half_r: float = maxf(eff_radius * 0.5, 1.0)
				var falloff: float = 1.0 if dist <= half_r else clampf(1.0 - ((dist - half_r) / maxf(max_reach - half_r, 1.0)), 0.15, 1.0)
				var final_dmg: float = player_damage * falloff
				var final_pow: float = player_power * falloff
				var angle_to_f: float = atan2(f_mid.y - world_pos.y - 4.0, f_mid.x - world_pos.x)
				if f.has_method("apply_explosion_hit"):
					f.call("apply_explosion_hit", angle_to_f, final_pow, final_dmg)

	# 3. Damage / trigger interactive props (Explosions.as:387-422: occluded by walls, floors & CanBlockExplosions props!)
	for p_var: Variant in props:
		if not is_instance_valid(p_var):
			continue
		var prop: Node2D = p_var as Node2D
		var p_dist: float = world_pos.distance_to(prop.global_position)
		if p_dist <= max_reach + 10.0:
			if is_explosion_line_blocked(world_pos, prop.global_position, prop):
				continue
			var half_rp: float = maxf(eff_radius * 0.5, 1.0)
			var falloff_p: float = 1.0 if p_dist <= half_rp else clampf(1.0 - ((p_dist - half_rp) / maxf(max_reach + 10.0 - half_rp, 1.0)), 0.25, 1.0)
			var dir_p: Vector2 = (prop.global_position - world_pos).normalized()
			if prop.has_method("apply_explosion_damage"):
				prop.call("apply_explosion_damage", player_damage * falloff_p, dir_p * player_power * 2.0, source_fighter)
			elif prop.has_method("apply_damage"):
				prop.call("apply_damage", player_damage * falloff_p, dir_p * player_power * 2.0)

	# 3b. Chain-detonate nearby active throwables (grenades/molotovs/mines/C4) caught in the blast wave
	if match_world != null and is_instance_valid(match_world):
		var pm_var: Variant = match_world.get("projectile_manager")
		if pm_var is Object and (pm_var as Object).has_method("detonate_throwables_in_radius"):
			(pm_var as Object).call("detonate_throwables_in_radius", world_pos, max_reach + 6.0)

	# 4. Authentic Y8 Multi-Frame Explosion Centrum (Effects.as:182-203)
	# 1 center explosion_circle + 6 surrounding explosion_circles at 0, 60, 120, 180, 240, 300 deg
	var sub_circles: Array[Dictionary] = [
		{"offset": Vector2.ZERO, "scale": 1.35, "delay": 0.0, "rot": randf() * TAU}
	]
	for c_i: int in range(6):
		var c_ang: float = deg_to_rad(float(c_i) * 60.0 + randf_range(-10.0, 10.0))
		var c_dist: float = randf_range(12.0, 19.0) * (base_radius / 33.0)
		sub_circles.append({
			"offset": Vector2(cos(c_ang), sin(c_ang)) * c_dist,
			"scale": randf_range(0.95, 1.25),
			"delay": randf_range(0.0, 2.0),
			"rot": randf() * TAU,
		})

	var ex_entry: Dictionary = {
		"pos": world_pos,
		"radius": base_radius,
		"max_radius": max_reach,
		"age": 0.0,
		"max_age": 14.0,
		"rays": ray_endpoints,
		"sub_circles": sub_circles,
	}
	explosions.append(ex_entry)
	explosion_rings.append(ex_entry)

	# Spawn expanding smoke puffs along rays & center (Explosions.as:152-425: pure blast + smoke, NO fire particles!)
	for s_i: int in range(12):
		var ray_idx: int = (s_i * 3) % maxi(1, ray_endpoints.size())
		var target_pt: Vector2 = ray_endpoints[ray_idx] if not ray_endpoints.is_empty() else (world_pos + Vector2.RIGHT.rotated(float(s_i) * TAU / 12.0) * 24.0)
		var ray_dir: Vector2 = (target_pt - world_pos).normalized()
		var spd_s: float = randf_range(0.8, 2.8)
		smoke_puffs.append({
			"pos": world_pos + ray_dir * randf_range(2.0, 12.0),
			"vel": ray_dir * spd_s + Vector2(0.0, randf_range(-0.8, -0.2)),
			"age": 0.0,
			"max_age": randf_range(12.0, 22.0),
			"scale": randf_range(0.9, 1.45),
			"rot": randf() * TAU,
			"light": (s_i % 3 == 0),
		})

	# Spawn metal/debris hit sparks
	for sp_i: int in range(8):
		var s_ang: float = randf() * TAU
		var s_spd: float = randf_range(1.6, 5.2)
		hit_sparks.append({
			"pos": world_pos + Vector2(cos(s_ang), sin(s_ang)) * randf_range(2.0, 8.0),
			"vel": Vector2(cos(s_ang) * s_spd, sin(s_ang) * s_spd - 1.2),
			"is_blood": false,
			"is_smoke": false,
			"age": 0.0,
			"max_age": randf_range(8.0, 14.0),
		})
	queue_redraw()


func trigger_fire_burst(source_type: String, world_pos: Vector2, count: int = 18) -> void:
	_load_effect_textures()
	total_fire_bursts_triggered += 1
	if _fire_sfx_cooldown <= 0.0:
		_play_sfx("fireplosion", world_pos)
		_fire_sfx_cooldown = 4.0

	var instant_radius: float = 20.0 if source_type.to_upper() == "MOLOTOV" else 16.0
	var fighters: Array = _get_fighters()
	for f_var: Variant in fighters:
		if not is_instance_valid(f_var):
			continue
		var f: Node2D = f_var as Node2D
		var f_mid: Vector2 = f.global_position + Vector2(0.0, -8.0)
		if f.has_method("get_mid_pos"):
			f_mid = f.call("get_mid_pos") as Vector2
		if world_pos.distance_to(f_mid) <= instant_radius and not is_explosion_line_blocked(world_pos, f_mid, null):
			if f.has_method("add_burn"):
				f.call("add_burn", 100.0, true)

	var props: Array = _get_props()
	for p_var: Variant in props:
		if not is_instance_valid(p_var):
			continue
		var prop: Node2D = p_var as Node2D
		if world_pos.distance_to(prop.global_position) <= instant_radius + 6.0 and not is_explosion_line_blocked(world_pos, prop.global_position, prop):
			if prop.has_method("ignite"):
				prop.call("ignite")

	var num_particles: int = maxi(1, count)
	for i: int in range(num_particles):
		var spread_x: float = (float(i) / float(num_particles) - 0.5) * 4.8 + randf_range(-0.9, 0.9)
		var spread_y: float = randf_range(-3.2, -0.4)
		var p_pos: Vector2 = world_pos + Vector2(randf_range(-4.0, 4.0), randf_range(-4.0, 1.0))
		fire_particles.append({
			"pos": p_pos,
			"vel": Vector2(spread_x, spread_y),
			"grounded": false,
			"attached_to": "air",
			"age": 0.0,
			"max_age": randf_range(65.0, 110.0),
			"source_type": source_type,
			"source_fighter": null,
			"variant": i % 6,
			"effect_timer": randf_range(0.0, 2.5),
		})
		if i % 2 == 0:
			_emit_flame_puff(p_pos, false, 1.25)
	queue_redraw()


func _emit_flame_puff(emit_pos: Vector2, is_ground_base: bool = false, init_scale: float = 1.25) -> void:
	if flame_puffs.size() >= MAX_FLAME_PUFFS:
		return
	if is_ground_base:
		flame_puffs.append({
			"pos": emit_pos + Vector2(randf_range(-3.0, 3.0), -1.0),
			"vel": Vector2(randf_range(-0.6, 0.6), 0.0),
			"age": 0.0,
			"max_age": 14.0,
			"scale": init_scale,
			"is_ground": true,
			"seq_id": randi() % 3,
		})
	else:
		flame_puffs.append({
			"pos": emit_pos + Vector2(randf_range(-3.0, 3.0), randf_range(-1.0, 1.0)),
			"vel": Vector2(randf_range(-0.35, 0.35), randf_range(-1.35, -1.0)),
			"age": 0.0,
			"max_age": 15.0,
			"scale": init_scale,
			"is_ground": false,
			"seq_id": randi() % 3,
		})


func spawn_flamethrower_particle(world_pos: Vector2, angle_deg: float, source_fighter: Node2D = null) -> void:
	_load_effect_textures()
	if _fire_sfx_cooldown <= 0.0:
		_play_sfx("flamethrower", world_pos)
		_fire_sfx_cooldown = 5.0
	var rad: float = deg_to_rad(angle_deg + randf_range(-5.0, 5.0))
	var spd: float = 8.5
	fire_particles.append({
		"pos": world_pos,
		"vel": Vector2(cos(rad) * spd, sin(rad) * spd),
		"grounded": false,
		"attached_to": "air",
		"age": 0.0,
		"max_age": 32.0,
		"source_type": "FLAMETHROWER",
		"source_fighter": source_fighter,
		"variant": 0,
	})
	queue_redraw()


func spawn_flamethrower_stream(world_pos: Vector2, dir_or_angle: Variant, owner_or_id: Variant = null) -> void:
	var angle_deg: float = 0.0
	if typeof(dir_or_angle) == TYPE_VECTOR2:
		var d: Vector2 = dir_or_angle as Vector2
		angle_deg = rad_to_deg(atan2(d.y, d.x))
	else:
		angle_deg = float(dir_or_angle)
	var src_f: Node2D = owner_or_id as Node2D if (owner_or_id is Node2D) else null
	spawn_flamethrower_particle(world_pos, angle_deg, src_f)


func spawn_muzzle_flash(world_pos: Vector2, dir_or_angle: Variant, weapon_id: String = "PISTOL") -> void:
	_load_effect_textures()
	var angle_deg: float = 0.0
	if typeof(dir_or_angle) == TYPE_VECTOR2:
		var d: Vector2 = dir_or_angle as Vector2
		angle_deg = rad_to_deg(atan2(d.y, d.x))
	else:
		angle_deg = float(dir_or_angle)

	var wid: String = weapon_id.to_upper()
	muzzle_flashes.append({
		"pos": world_pos,
		"angle_deg": angle_deg,
		"weapon_id": wid,
		"age": 0.0,
		"max_age": 3.0,
	})

	# Also spawn muzzle_weapon_smoke rising from barrel (DefineSprite_268 / DefineSprite_1046)
	var rad: float = deg_to_rad(angle_deg)
	var dir_vec: Vector2 = Vector2(cos(rad), sin(rad))
	smoke_puffs.append({
		"pos": world_pos + dir_vec * 4.0,
		"vel": dir_vec * 0.45 + Vector2(randf_range(-0.2, 0.2), -0.65),
		"age": 0.0,
		"max_age": 13.0,
		"scale": 0.85,
		"rot": randf() * TAU,
		"is_muzzle_smoke": true,
	})
	queue_redraw()


func spawn_shell_casing(world_pos: Vector2, eject_dir: int, weapon_id: String = "PISTOL") -> void:
	_load_effect_textures()
	var dir_f: float = -1.0 if eject_dir >= 0 else 1.0
	var wid: String = weapon_id.to_upper()
	var shell_type: String = "small"
	if wid in ["SHOTGUN", "SAWED_OFF", "FLARE_GUN"]:
		shell_type = "shotgun"
	elif wid in ["RIFLE", "M60", "SNIPER", "MAGNUM", "TOMMY_GUN"]:
		shell_type = "big"

	shell_casings.append({
		"pos": world_pos,
		"vel": Vector2(dir_f * randf_range(1.2, 2.4), randf_range(-2.6, -1.4)),
		"rot": randf() * TAU,
		"rot_vel": dir_f * 0.45,
		"shell_type": shell_type,
		"bounced": false,
		"age": 0.0,
		"max_age": 54.0,
	})
	queue_redraw()


func spawn_smoke_puff(world_pos: Vector2, vel: Vector2 = Vector2(0.0, -0.4), scale_val: float = 1.0, max_age: float = 12.0) -> void:
	_load_effect_textures()
	smoke_puffs.append({
		"pos": world_pos,
		"vel": vel,
		"age": 0.0,
		"max_age": max_age,
		"scale": scale_val,
		"rot": randf() * TAU,
		"light": false,
	})
	queue_redraw()


func spawn_melee_trace(world_pos: Vector2, facing: int, weapon_id: String, combo_step: int = 1) -> void:
	_load_effect_textures()
	var wid: String = weapon_id.to_upper()
	var trace_kind: String = "machete"
	if wid in ["SWORD", "BASEBALL_BAT"]:
		trace_kind = "sword"
	elif wid in ["AXE", "CHAINSAW"]:
		trace_kind = "axe"
	melee_traces.append({
		"pos": world_pos,
		"facing": -1 if facing < 0 else 1,
		"trace_kind": trace_kind,
		"combo_step": clampi(combo_step, 1, 3),
		"age": 0.0,
		"max_age": 4.0,
	})
	queue_redraw()


func spawn_prop_debris(prop_type: String, world_pos: Vector2, hit_dir: Vector2 = Vector2.UP, count: int = 4) -> void:
	_load_effect_textures()
	var ptype: String = prop_type.to_upper()
	var category: String = "crate"
	var spawn_electric: bool = false
	var spawn_paper: bool = false

	if "BARREL" in ptype or "GASCAN" in ptype or "FILECAB" in ptype or "LAMP" in ptype:
		category = "barrel"
		if "LAMP" in ptype:
			spawn_electric = true
	elif "TABLE" in ptype or "DESK" in ptype or "CHAIR" in ptype:
		category = "table"
		if "DESK" in ptype:
			spawn_paper = true
	elif "COMP" in ptype:
		category = "barrel"
		spawn_electric = true
		spawn_paper = true
	elif "PAPER" in ptype:
		category = "paper"

	var base_dir: Vector2 = hit_dir.normalized() if hit_dir.length_squared() > 0.01 else Vector2(0.0, -1.0)
	var num: int = maxi(1, count)
	for i: int in range(num):
		var is_paper_piece: bool = (category == "paper") or (spawn_paper and i % 2 == 1)
		var cat_piece: String = "paper" if is_paper_piece else category
		var vx: float = base_dir.x * randf_range(0.8, 2.8) + randf_range(-2.2, 2.2)
		var vy: float = randf_range(-3.6, -1.2)
		if is_paper_piece:
			vx = randf_range(-1.8, 1.8)
			vy = randf_range(-2.4, -0.6)
		prop_debris.append({
			"pos": world_pos + Vector2(randf_range(-5.0, 5.0), randf_range(-6.0, 2.0)),
			"vel": Vector2(vx, vy),
			"rot": randf() * TAU,
			"rot_vel": randf_range(-0.38, 0.38),
			"category": cat_piece,
			"variant": i % 4,
			"age": 0.0,
			"max_age": randf_range(55.0, 85.0),
			"bounced": false,
		})

	if spawn_electric:
		for e_i: int in range(3):
			electric_sparks.append({
				"pos": world_pos + Vector2(randf_range(-6.0, 6.0), randf_range(-6.0, 4.0)),
				"age": float(e_i),
				"max_age": 9.0,
				"rot": randf() * TAU,
			})
	queue_redraw()


func spawn_hit_sparks(world_pos: Vector2, is_blood: bool = false) -> void:
	_load_effect_textures()
	var count: int = 5 if is_blood else 4
	for i: int in range(count):
		var ang: float = randf() * TAU
		var spd: float = randf_range(1.0, 3.2)
		hit_sparks.append({
			"pos": world_pos,
			"vel": Vector2(cos(ang) * spd, sin(ang) * spd - 0.8),
			"is_blood": is_blood,
			"is_smoke": false,
			"rot": ang,
			"age": 0.0,
			"max_age": randf_range(6.0, 12.0),
		})
	queue_redraw()


func spawn_glass_shards(p1: Vector2, p2: Vector2, impact_vel: Vector2) -> void:
	_load_effect_textures()
	_play_sfx("glass", (p1 + p2) * 0.5)
	var length: float = p1.distance_to(p2)
	var steps: int = maxi(3, int(length / 6.0))
	for i: int in range(steps):
		var t: float = float(i) / float(maxi(1, steps - 1))
		var pt: Vector2 = p1.lerp(p2, t)
		glass_shards.append({
			"pos": pt,
			"vel": impact_vel * randf_range(0.35, 0.75) + Vector2(randf_range(-1.5, 1.5), randf_range(-2.0, 0.5)),
			"rot": randf() * TAU,
			"rot_vel": randf_range(-0.4, 0.4),
			"age": 0.0,
			"max_age": 48.0,
		})
	queue_redraw()


func spawn_gibs(world_pos: Vector2, impulse: Vector2) -> void:
	_load_effect_textures()
	_play_sfx("gib", world_pos)
	for i: int in range(6):
		gibs.append({
			"pos": world_pos + Vector2(randf_range(-4.0, 4.0), randf_range(-12.0, -2.0)),
			"vel": impulse * randf_range(0.5, 1.1) + Vector2(randf_range(-3.0, 3.0), randf_range(-4.5, -1.0)),
			"rot": randf() * TAU,
			"rot_vel": randf_range(-0.35, 0.35),
			"age": 0.0,
			"max_age": 90.0,
		})
	spawn_hit_sparks(world_pos + Vector2(0.0, -8.0), true)
	queue_redraw()


func step_hazards(step_24hz: float) -> void:
	_load_effect_textures()
	_visual_tick += step_24hz
	if _fire_sfx_cooldown > 0.0:
		_fire_sfx_cooldown = maxf(0.0, _fire_sfx_cooldown - step_24hz)
	if _shell_sfx_cooldown > 0.0:
		_shell_sfx_cooldown = maxf(0.0, _shell_sfx_cooldown - step_24hz)

	_rebuild_support_rects_cache()

	var fighters: Array = _get_fighters()
	var props: Array = _get_props()

	# Pre-cache fighter rects and prop world rects once per step to eliminate O(particles * props) dynamic call() overhead
	var cached_fighters: Array[Dictionary] = []
	for f_var: Variant in fighters:
		if not is_instance_valid(f_var):
			continue
		var f: Node2D = f_var as Node2D
		var fid: int = f.get_instance_id()
		var cur_st: String = str(f.get("current_state"))
		var prev_st: String = str(_tracked_fighter_states.get(fid, ""))
		if cur_st != prev_st:
			_tracked_fighter_states[fid] = cur_st
			if cur_st.begins_with("SWORD_") or cur_st.begins_with("MACHETE_") or cur_st.begins_with("AXE_"):
				var f_facing: int = int(f.get("facing")) if f.get("facing") != null else 1
				var c_step: int = int(cur_st.right(1)) if cur_st.right(1).is_valid_int() else 1
				var w_kind: String = "SWORD" if cur_st.begins_with("SWORD_") else ("AXE" if cur_st.begins_with("AXE_") else "MACHETE")
				spawn_melee_trace(f.global_position + Vector2(float(f_facing) * 10.0, -11.0), f_facing, w_kind, c_step)
		var f_rect: Rect2 = f.call("get_hit_rect") as Rect2 if f.has_method("get_hit_rect") else Rect2(f.global_position.x - 6.0, f.global_position.y - 18.0, 12.0, 18.0)
		cached_fighters.append({
			"node": f,
			"rect": f_rect,
			"contact_rect": f_rect.grow_individual(3.5, 2.5, 3.5, 5.0),
			"rolling": bool(f.get("rolling")),
		})

	var cached_props: Array[Dictionary] = []
	for p_var: Variant in props:
		if not is_instance_valid(p_var):
			continue
		var prop: Node2D = p_var as Node2D
		if bool(prop.get("is_destroyed")):
			continue
		var p_rect: Rect2 = prop.call("get_world_rect") as Rect2 if prop.has_method("get_world_rect") else Rect2(prop.global_position.x - 8.0, prop.global_position.y - 8.0, 16.0, 16.0)
		cached_props.append({
			"node": prop,
			"rect": p_rect,
			"fire_rect": p_rect.grow(4.5),
		})

	if fire_particles.size() > MAX_FIRE_PARTICLES:
		fire_particles = fire_particles.slice(fire_particles.size() - MAX_FIRE_PARTICLES)

	# 1. Step fire particles (Fires.as)
	var next_fires: Array[Dictionary] = []
	for fp: Dictionary in fire_particles:
		var age: float = float(fp.get("age", 0.0)) + step_24hz
		var max_age: float = float(fp.get("max_age", 80.0))
		if age >= max_age:
			continue
		var pos: Vector2 = fp.get("pos", Vector2.ZERO) as Vector2
		var vel: Vector2 = fp.get("vel", Vector2.ZERO) as Vector2
		var grounded: bool = bool(fp.get("grounded", false))
		var src_type: String = str(fp.get("source_type", "")).to_upper()

		if not grounded:
			var grav: float = 0.08 if src_type == "FLAMETHROWER" else FIRE_GRAVITY_24HZ
			vel.y += grav * step_24hz
			var candidate: Vector2 = pos + vel * step_24hz
			var hit_fy: float = _find_floor_y_between(pos, candidate) if vel.y >= 0.0 else INF
			if hit_fy < INF:
				pos = Vector2(candidate.x, hit_fy)
				vel = Vector2(vel.x * 0.35, 0.0)
				grounded = true
				fp["attached_to"] = "ground"
				_emit_flame_puff(pos, false, 1.25)
				_emit_flame_puff(pos, true, 1.25)
			else:
				pos = candidate
		else:
			vel.x *= pow(0.85, step_24hz)
			pos.x += vel.x * step_24hz
			# If a supporting prop/glass underneath grounded fire broke, drop the fire to the floor below!
			if not _is_point_on_floor(pos + Vector2(0.0, 2.0)):
				grounded = false

		# AS3 FireNodeData.as:189-216: emit independent rising fire_effect & fire_effect_ground puffs every 3..5 frames
		var eff_timer: float = float(fp.get("effect_timer", 0.0)) - step_24hz
		if eff_timer <= 0.0:
			eff_timer = randf_range(2.4, 4.4)
			if src_type != "FLAMETHROWER" or grounded:
				_emit_flame_puff(pos, false, 1.25)
				if grounded and randf() < 0.42:
					_emit_flame_puff(pos, true, 1.25)
					if randf() < 0.5 and smoke_puffs.size() < MAX_SMOKE_PUFFS:
						smoke_puffs.append({
							"pos": pos + Vector2(randf_range(-2.5, 2.5), -6.0),
							"vel": Vector2(randf_range(-0.22, 0.22), -1.8),
							"age": 0.0,
							"max_age": 16.0,
							"scale": 0.8,
							"rot": randf() * TAU,
							"light": false,
						})
		fp["effect_timer"] = eff_timer

		# Check contact with fighters -> ignite burn_state (including flames burning at the fighter's feet!)
		var src_f: Node2D = fp.get("source_fighter", null) as Node2D
		for cf: Dictionary in cached_fighters:
			var f: Node2D = cf["node"] as Node2D
			if f == src_f and age < 4.0:
				continue
			if bool(cf["rolling"]):
				continue
			var contact_rect: Rect2 = cf["contact_rect"] as Rect2
			if contact_rect.has_point(pos) or contact_rect.has_point(pos + Vector2(0.0, -5.0)):
				if f.has_method("add_burn"):
					var burn_add: float = (12.0 if src_type == "FLAMETHROWER" else 5.5) * step_24hz
					f.call("add_burn", burn_add, false)

		# Check contact with props using pre-cached rects
		for cp: Dictionary in cached_props:
			var fire_rect: Rect2 = cp["fire_rect"] as Rect2
			if fire_rect.has_point(pos):
				var prop: Node2D = cp["node"] as Node2D
				if prop.has_method("add_fire_heat"):
					prop.call("add_fire_heat", 8.0 * step_24hz)
				elif prop.has_method("ignite"):
					prop.call("ignite")

		fp["pos"] = pos
		fp["vel"] = vel
		fp["grounded"] = grounded
		fp["age"] = age
		next_fires.append(fp)
	fire_particles = next_fires

	# 1b. Emit world-space rising flame puffs AND gradual fire contagion from burning fighters (Fires.as:117-182 PlayerOverlap & ObjectOverlap)
	for f_var: Variant in fighters:
		if not is_instance_valid(f_var):
			continue
		var f: Node2D = f_var as Node2D
		var fid: int = f.get_instance_id()
		var b_state: float = float(f.get("burn_state")) if f.get("burn_state") != null else 0.0
		var is_charred: bool = bool(f.get("burned"))
		if (b_state >= 15.0 or is_charred) and not bool(f.get("rolling")):
			var f_rect_c: Rect2 = f.call("get_hit_rect") as Rect2 if f.has_method("get_hit_rect") else Rect2(f.global_position.x - 6.0, f.global_position.y - 18.0, 12.0, 18.0)
			var f_prop_rect: Rect2 = f_rect_c.grow_individual(5.0, 3.0, 5.0, 3.0)
			# Contagion 1: Burning fighter gradually heats/ignites nearby flammable props (~5 ticks of sustained proximity)
			for p_var_c: Variant in props:
				if not is_instance_valid(p_var_c):
					continue
				var prop_c: Node2D = p_var_c as Node2D
				if bool(prop_c.get("is_destroyed")) or bool(prop_c.get("is_burning")) or not bool(prop_c.get("can_burn")):
					continue
				var p_rect_c: Rect2 = prop_c.call("get_world_rect") as Rect2 if prop_c.has_method("get_world_rect") else Rect2(prop_c.global_position.x - 7.0, prop_c.global_position.y - 7.0, 14.0, 14.0)
				if f_prop_rect.intersects(p_rect_c):
					if prop_c.has_method("add_fire_heat"):
						prop_c.call("add_fire_heat", 3.5 * step_24hz)
					elif prop_c.has_method("ignite"):
						prop_c.call("ignite")
			# Contagion 2: Burning fighter gradually spreads heat to other fighters in close contact (~2.4 burn/tick; blocked during Roll & Roll immunity!)
			var f_fighter_rect: Rect2 = f_rect_c.grow_individual(3.0, 2.0, 3.0, 2.0)
			for other_f_var: Variant in fighters:
				if not is_instance_valid(other_f_var) or other_f_var == f:
					continue
				var other_f: Node2D = other_f_var as Node2D
				if bool(other_f.get("is_dead")) or bool(other_f.get("rolling")):
					continue
				var o_rect: Rect2 = other_f.call("get_hit_rect") as Rect2 if other_f.has_method("get_hit_rect") else Rect2(other_f.global_position.x - 6.0, other_f.global_position.y - 18.0, 12.0, 18.0)
				if f_fighter_rect.intersects(o_rect) and other_f.has_method("add_burn"):
					other_f.call("add_burn", 2.4 * step_24hz, false)
		if b_state >= 10.0:
			var st: Dictionary = _fighter_burn_emit_state.get(fid, {"timer": 0.0, "last_pos": f.global_position}) as Dictionary
			var b_timer: float = float(st.get("timer", 0.0)) - step_24hz
			var last_p: Vector2 = st.get("last_pos", f.global_position) as Vector2
			var moved_d: float = f.global_position.distance_to(last_p)
			if b_timer <= 0.0 or moved_d >= 4.0:
				b_timer = randf_range(2.0, 3.2)
				last_p = f.global_position
				var f_mid: Vector2 = f.global_position + Vector2(0.0, -10.0)
				_emit_flame_puff(f_mid + Vector2(randf_range(-3.5, 3.5), randf_range(-4.0, 4.0)), false, 1.2)
				if b_state >= 65.0 or bool(f.get("burned")):
					_emit_flame_puff(f_mid + Vector2(randf_range(-4.5, 4.5), randf_range(-5.0, 3.0)), false, 1.3)
					if randf() < 0.35:
						smoke_puffs.append({
							"pos": f_mid + Vector2(randf_range(-2.0, 2.0), -6.0),
							"vel": Vector2(randf_range(-0.2, 0.2), -1.8),
							"age": 0.0,
							"max_age": 14.0,
							"scale": 0.75,
							"rot": randf() * TAU,
							"light": false,
						})
			_fighter_burn_emit_state[fid] = {"timer": b_timer, "last_pos": last_p}
		elif _fighter_burn_emit_state.has(fid):
			_fighter_burn_emit_state.erase(fid)

	# 1b-2. Emit world-space rising flame puffs from burning props (e.g. phase-1 BARREL_EXPLOSIVE / ignited crates)
	for p_var: Variant in props:
		if not is_instance_valid(p_var):
			continue
		var prop: Node2D = p_var as Node2D
		if bool(prop.get("is_burning")) and not bool(prop.get("is_destroyed")):
			var pid: int = prop.get_instance_id()
			var pst: Dictionary = _fighter_burn_emit_state.get(pid, {"timer": 0.0, "last_pos": prop.global_position}) as Dictionary
			var p_timer: float = float(pst.get("timer", 0.0)) - step_24hz
			var p_last: Vector2 = pst.get("last_pos", prop.global_position) as Vector2
			if p_timer <= 0.0 or prop.global_position.distance_to(p_last) >= 4.0:
				p_timer = randf_range(2.2, 3.6)
				p_last = prop.global_position
				_emit_flame_puff(prop.global_position + Vector2(randf_range(-3.0, 3.0), -6.0), false, 1.25)
			_fighter_burn_emit_state[pid] = {"timer": p_timer, "last_pos": p_last}

	# 1c. Step rising flame_puffs (fire_effect.as & fire_effect_ground.as)
	var next_flame_puffs: Array[Dictionary] = []
	for flp: Dictionary in flame_puffs:
		var f_age: float = float(flp.get("age", 0.0)) + step_24hz
		var f_max: float = float(flp.get("max_age", 15.0))
		if f_age >= f_max:
			continue
		var f_pos: Vector2 = flp.get("pos", Vector2.ZERO) as Vector2
		var f_vel: Vector2 = flp.get("vel", Vector2.ZERO) as Vector2
		flp["pos"] = f_pos + f_vel * step_24hz
		flp["age"] = f_age
		next_flame_puffs.append(flp)
	flame_puffs = next_flame_puffs

	# 2. Step explosions
	var next_explosions: Array[Dictionary] = []
	for ex: Dictionary in explosions:
		var age: float = float(ex.get("age", 0.0)) + step_24hz
		if age < float(ex.get("max_age", 14.0)):
			ex["age"] = age
			next_explosions.append(ex)
	explosions = next_explosions
	explosion_rings = next_explosions.duplicate()

	# 3. Step smoke puffs
	if smoke_puffs.size() > MAX_SMOKE_PUFFS:
		smoke_puffs = smoke_puffs.slice(smoke_puffs.size() - MAX_SMOKE_PUFFS)
	var next_smoke: Array[Dictionary] = []
	for sp: Dictionary in smoke_puffs:
		var age: float = float(sp.get("age", 0.0)) + step_24hz
		if age >= float(sp.get("max_age", 14.0)):
			continue
		var pos: Vector2 = sp.get("pos", Vector2.ZERO) as Vector2
		var vel: Vector2 = sp.get("vel", Vector2.ZERO) as Vector2
		vel.y -= 0.04 * step_24hz
		vel *= pow(0.92, step_24hz)
		sp["pos"] = pos + vel * step_24hz
		sp["vel"] = vel
		sp["age"] = age
		next_smoke.append(sp)
	smoke_puffs = next_smoke

	# 4. Step muzzle flashes
	var next_flashes: Array[Dictionary] = []
	for mf: Dictionary in muzzle_flashes:
		var age: float = float(mf.get("age", 0.0)) + step_24hz
		if age < float(mf.get("max_age", 3.0)):
			mf["age"] = age
			next_flashes.append(mf)
	muzzle_flashes = next_flashes

	# 5. Step shell casings
	if shell_casings.size() > MAX_SHELLS:
		shell_casings = shell_casings.slice(shell_casings.size() - MAX_SHELLS)
	var next_shells: Array[Dictionary] = []
	for sc: Dictionary in shell_casings:
		var age: float = float(sc.get("age", 0.0)) + step_24hz
		if age >= float(sc.get("max_age", 54.0)):
			continue
		if bool(sc.get("resting", false)):
			sc["age"] = age
			next_shells.append(sc)
			continue
		var pos: Vector2 = sc.get("pos", Vector2.ZERO) as Vector2
		var vel: Vector2 = sc.get("vel", Vector2.ZERO) as Vector2
		vel.y += SHELL_GRAVITY_24HZ * step_24hz
		var cand: Vector2 = pos + vel * step_24hz
		var floor_y_sc: float = _find_floor_y_between(pos, cand) if vel.y > 0.0 else INF
		if floor_y_sc < INF and vel.y > 0.0:
			pos = Vector2(cand.x, minf(cand.y, floor_y_sc - 0.5))
			vel.y = -vel.y * 0.42
			vel.x *= 0.65
			sc["rot_vel"] = float(sc.get("rot_vel", 0.2)) * 0.5
			if absf(vel.y) < 0.35:
				vel.y = 0.0
				vel.x = 0.0
				sc["rot_vel"] = 0.0
				sc["resting"] = true
			if not bool(sc.get("bounced", false)) and _shell_sfx_cooldown <= 0.0:
				_play_sfx("shell_bounce", pos)
				_shell_sfx_cooldown = 3.0
				sc["bounced"] = true
		else:
			pos = cand
		sc["pos"] = pos
		sc["vel"] = vel
		sc["rot"] = float(sc.get("rot", 0.0)) + float(sc.get("rot_vel", 0.2)) * step_24hz
		sc["age"] = age
		next_shells.append(sc)
	shell_casings = next_shells

	# 6. Step hit sparks
	if hit_sparks.size() > MAX_SPARKS:
		hit_sparks = hit_sparks.slice(hit_sparks.size() - MAX_SPARKS)
	var next_sparks: Array[Dictionary] = []
	for hs: Dictionary in hit_sparks:
		var age: float = float(hs.get("age", 0.0)) + step_24hz
		if age >= float(hs.get("max_age", 12.0)):
			continue
		var pos: Vector2 = hs.get("pos", Vector2.ZERO) as Vector2
		var vel: Vector2 = hs.get("vel", Vector2.ZERO) as Vector2
		vel.y += 0.25 * step_24hz
		hs["pos"] = pos + vel * step_24hz
		hs["vel"] = vel
		hs["age"] = age
		next_sparks.append(hs)
	hit_sparks = next_sparks

	# 7. Step physical prop debris (crate, barrel, table, paper)
	if prop_debris.size() > MAX_DEBRIS:
		prop_debris = prop_debris.slice(prop_debris.size() - MAX_DEBRIS)
	var next_debris: Array[Dictionary] = []
	for pd: Dictionary in prop_debris:
		var age: float = float(pd.get("age", 0.0)) + step_24hz
		if age >= float(pd.get("max_age", 75.0)):
			continue
		if bool(pd.get("resting", false)):
			pd["age"] = age
			next_debris.append(pd)
			continue
		var pos: Vector2 = pd.get("pos", Vector2.ZERO) as Vector2
		var vel: Vector2 = pd.get("vel", Vector2.ZERO) as Vector2
		var cat: String = str(pd.get("category", "crate"))
		if cat == "paper":
			vel.y = minf(1.2, vel.y + PAPER_GRAVITY_24HZ * step_24hz)
			vel.x = sin(age * 0.25 + float(pd.get("variant", 0))) * 0.85
		else:
			vel.y += DEBRIS_GRAVITY_24HZ * step_24hz
		var cand: Vector2 = pos + vel * step_24hz
		var floor_y_pd: float = _find_floor_y_between(pos, cand) if vel.y > 0.0 else INF
		if floor_y_pd < INF and vel.y > 0.0:
			pos = Vector2(cand.x, minf(cand.y, floor_y_pd - 0.5))
			vel.y = -absf(vel.y) * (0.15 if cat == "paper" else 0.4)
			vel.x *= 0.68
			pd["rot_vel"] = float(pd.get("rot_vel", 0.2)) * 0.52
			if absf(vel.y) < 0.38:
				vel.y = 0.0
				vel.x = 0.0
				pd["rot_vel"] = 0.0
				pd["resting"] = true
		else:
			pos = cand
		pd["pos"] = pos
		pd["vel"] = vel
		pd["rot"] = float(pd.get("rot", 0.0)) + float(pd.get("rot_vel", 0.0)) * step_24hz
		pd["age"] = age
		next_debris.append(pd)
	prop_debris = next_debris

	# 8. Step electric sparks & melee traces
	var next_elec: Array[Dictionary] = []
	for el: Dictionary in electric_sparks:
		var age: float = float(el.get("age", 0.0)) + step_24hz
		if age < float(el.get("max_age", 9.0)):
			el["age"] = age
			next_elec.append(el)
	electric_sparks = next_elec

	var next_traces: Array[Dictionary] = []
	for mt: Dictionary in melee_traces:
		var age: float = float(mt.get("age", 0.0)) + step_24hz
		if age < float(mt.get("max_age", 4.0)):
			mt["age"] = age
			next_traces.append(mt)
	melee_traces = next_traces

	# 9. Step glass shards & gibs
	if glass_shards.size() > MAX_SHARDS:
		glass_shards = glass_shards.slice(glass_shards.size() - MAX_SHARDS)
	var next_shards: Array[Dictionary] = []
	for gs: Dictionary in glass_shards:
		var age: float = float(gs.get("age", 0.0)) + step_24hz
		if age >= float(gs.get("max_age", 48.0)):
			continue
		if bool(gs.get("resting", false)):
			gs["age"] = age
			next_shards.append(gs)
			continue
		var pos: Vector2 = gs.get("pos", Vector2.ZERO) as Vector2
		var vel: Vector2 = gs.get("vel", Vector2.ZERO) as Vector2
		vel.y += DEBRIS_GRAVITY_24HZ * step_24hz
		var cand: Vector2 = pos + vel * step_24hz
		var floor_y_gs: float = _find_floor_y_between(pos, cand) if vel.y > 0.0 else INF
		if floor_y_gs < INF and vel.y > 0.0:
			pos = Vector2(cand.x, minf(cand.y, floor_y_gs - 0.5))
			vel.y = -vel.y * 0.3
			vel.x *= 0.65
			if absf(vel.y) < 0.35:
				vel.y = 0.0
				vel.x = 0.0
				gs["rot_vel"] = 0.0
				gs["resting"] = true
		else:
			pos = cand
		gs["pos"] = pos
		gs["vel"] = vel
		gs["rot"] = float(gs.get("rot", 0.0)) + float(gs.get("rot_vel", 0.25)) * step_24hz
		gs["age"] = age
		next_shards.append(gs)
	glass_shards = next_shards

	var next_gibs: Array[Dictionary] = []
	for gb: Dictionary in gibs:
		var age: float = float(gb.get("age", 0.0)) + step_24hz
		if age >= float(gb.get("max_age", 90.0)):
			continue
		if bool(gb.get("resting", false)):
			gb["age"] = age
			next_gibs.append(gb)
			continue
		var pos: Vector2 = gb.get("pos", Vector2.ZERO) as Vector2
		var vel: Vector2 = gb.get("vel", Vector2.ZERO) as Vector2
		vel.y += DEBRIS_GRAVITY_24HZ * step_24hz
		var cand: Vector2 = pos + vel * step_24hz
		var floor_y_gb: float = _find_floor_y_between(pos, cand) if vel.y > 0.0 else INF
		if floor_y_gb < INF and vel.y > 0.0:
			pos = Vector2(cand.x, minf(cand.y, floor_y_gb - 0.5))
			vel.y = -vel.y * 0.32
			vel.x *= 0.55
			if absf(vel.y) < 0.38:
				vel.y = 0.0
				vel.x = 0.0
				gb["rot_vel"] = 0.0
				gb["resting"] = true
		else:
			pos = cand
		gb["pos"] = pos
		gb["vel"] = vel
		gb["rot"] = float(gb.get("rot", 0.0)) + float(gb.get("rot_vel", 0.25)) * step_24hz
		gb["age"] = age
		next_gibs.append(gb)
	gibs = next_gibs

	if (
		not fire_particles.is_empty() or not flame_puffs.is_empty() or not explosions.is_empty()
		or not smoke_puffs.is_empty() or not muzzle_flashes.is_empty() or not shell_casings.is_empty()
		or not hit_sparks.is_empty() or not prop_debris.is_empty() or not electric_sparks.is_empty()
		or not melee_traces.is_empty() or not glass_shards.is_empty() or not gibs.is_empty()
		or not _fighter_burn_emit_state.is_empty()
	):
		queue_redraw()


func clear_all() -> void:
	fire_particles.clear()
	flame_puffs.clear()
	explosions.clear()
	explosion_rings.clear()
	smoke_puffs.clear()
	muzzle_flashes.clear()
	shell_casings.clear()
	hit_sparks.clear()
	prop_debris.clear()
	electric_sparks.clear()
	melee_traces.clear()
	glass_shards.clear()
	gibs.clear()
	_tracked_fighter_states.clear()
	_fighter_burn_emit_state.clear()
	queue_redraw()


func _draw_tex_xform(tex: Texture2D, pos: Vector2, rot: float = 0.0, scale_vec: Vector2 = Vector2.ONE, modulate_col: Color = Color.WHITE, pivot_ratio: Vector2 = Vector2(0.5, 0.5)) -> void:
	if tex == null:
		return
	var sz: Vector2 = tex.get_size()
	if is_zero_approx(rot) and scale_vec.x > 0.0 and scale_vec.y > 0.0:
		var scaled_sz: Vector2 = Vector2(sz.x * scale_vec.x, sz.y * scale_vec.y)
		var top_left: Vector2 = pos - Vector2(scaled_sz.x * pivot_ratio.x, scaled_sz.y * pivot_ratio.y)
		draw_texture_rect(tex, Rect2(top_left, scaled_sz), false, modulate_col)
		return
	draw_set_transform(pos, rot, scale_vec)
	draw_texture(tex, -Vector2(sz.x * pivot_ratio.x, sz.y * pivot_ratio.y), modulate_col)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)


func _draw() -> void:
	# 1. Draw smoke puffs (smoke_trace_f01..10, smoke_light_f01..09, muzzle_smoke_f01..13)
	for sp: Dictionary in smoke_puffs:
		var pos: Vector2 = sp.get("pos", Vector2.ZERO) as Vector2
		var age: float = float(sp.get("age", 0.0))
		var max_age: float = maxf(1.0, float(sp.get("max_age", 12.0)))
		var t: float = clampf(age / max_age, 0.0, 1.0)
		var alpha: float = clampf(1.0 - t * 0.85, 0.0, 1.0)
		var sc: float = float(sp.get("scale", 1.0)) * (0.75 + t * 0.65)
		var rot: float = float(sp.get("rot", 0.0))
		var seq: Array[Texture2D] = _smoke_trace_seq
		if bool(sp.get("is_muzzle_smoke", false)) and not _muzzle_smoke_seq.is_empty():
			seq = _muzzle_smoke_seq
		elif bool(sp.get("light", false)) and not _smoke_light_seq.is_empty():
			seq = _smoke_light_seq
		if not seq.is_empty():
			var f_idx: int = clampi(int(t * float(seq.size())), 0, seq.size() - 1)
			_draw_tex_xform(seq[f_idx], pos, rot, Vector2(sc, sc), Color(1.0, 1.0, 1.0, alpha))

	# 2. Draw authentic multi-frame explosions (explosion_centrum_f01..14 + 6 sub_circles)
	for ex: Dictionary in explosions:
		var pos: Vector2 = ex.get("pos", Vector2.ZERO) as Vector2
		var age: float = float(ex.get("age", 0.0))
		var max_age: float = maxf(1.0, float(ex.get("max_age", 14.0)))
		var t: float = clampf(age / max_age, 0.0, 1.0)
		var alpha: float = clampf(1.2 - t * 1.15, 0.0, 1.0)

		var sub_list: Array = ex.get("sub_circles", []) as Array
		if not _explosion_centrum_seq.is_empty():
			if sub_list.is_empty():
				var idx_c: int = clampi(int(t * float(_explosion_centrum_seq.size())), 0, _explosion_centrum_seq.size() - 1)
				var ex_col: Color = Color(1.0, 0.88, 0.35, alpha) if t < 0.35 else (Color(1.0, 0.52, 0.12, alpha) if t < 0.72 else Color(0.28, 0.24, 0.22, alpha))
				_draw_tex_xform(_explosion_centrum_seq[idx_c], pos, 0.0, Vector2(1.15, 1.15), ex_col)
			else:
				for sub_v: Variant in sub_list:
					var sub: Dictionary = sub_v as Dictionary
					var local_age: float = age - float(sub.get("delay", 0.0))
					if local_age < 0.0 or local_age >= max_age:
						continue
					var local_t: float = clampf(local_age / max_age, 0.0, 1.0)
					var f_idx: int = clampi(int(local_t * float(_explosion_centrum_seq.size())), 0, _explosion_centrum_seq.size() - 1)
					var sc_val: float = float(sub.get("scale", 1.0)) * (0.72 + local_t * 0.38)
					var sub_pos: Vector2 = pos + (sub.get("offset", Vector2.ZERO) as Vector2) * (0.65 + local_t * 0.45)
					var sub_alpha: float = clampf(1.1 - local_t, 0.0, 0.92)
					var sub_col: Color = Color(1.0, 0.92, 0.42, sub_alpha) if local_t < 0.32 else (Color(1.0, 0.50, 0.10, sub_alpha) if local_t < 0.70 else Color(0.25, 0.22, 0.20, sub_alpha))
					_draw_tex_xform(
						_explosion_centrum_seq[f_idx],
						sub_pos,
						float(sub.get("rot", 0.0)),
						Vector2(sc_val, sc_val),
						sub_col
					)

	# 3. Draw airborne fire sparks & flamethrower stream + rising world-space flame_puffs (fire_effect.as & fire_effect_ground.as)
	for fp: Dictionary in fire_particles:
		var pos: Vector2 = fp.get("pos", Vector2.ZERO) as Vector2
		var vel: Vector2 = fp.get("vel", Vector2.ZERO) as Vector2
		var age: float = float(fp.get("age", 0.0))
		var max_age: float = maxf(1.0, float(fp.get("max_age", 80.0)))
		var grounded: bool = bool(fp.get("grounded", false)) or str(fp.get("attached_to", "")) == "ground"
		var src_type: String = str(fp.get("source_type", "")).to_upper()
		var alpha: float = clampf(1.0 - (age / max_age) * 0.65, 0.25, 1.0)

		if src_type == "FLAMETHROWER" and not grounded and not _flamethrower_seq.is_empty():
			var ft_idx: int = clampi(int((age / max_age) * float(_flamethrower_seq.size())), 0, _flamethrower_seq.size() - 1)
			var rot_ft: float = vel.angle()
			var sc_ft: float = 0.85 + (age / max_age) * 0.55
			_draw_tex_xform(_flamethrower_seq[ft_idx], pos, rot_ft, Vector2(sc_ft, sc_ft), Color(1.0, 1.0, 1.0, alpha))
			continue

		if not grounded:
			var var_num: int = int(fp.get("variant", 0))
			var f_seq: Array[Texture2D] = _fire_01_seq if var_num % 2 == 0 else _fire_02_seq
			if not f_seq.is_empty():
				var anim_i: int = clampi(int((age / maxf(12.0, max_age * 0.35)) * float(f_seq.size())), 0, f_seq.size() - 1)
				var rot_f: float = (vel.angle() + PI * 0.5) * 0.35
				_draw_tex_xform(f_seq[anim_i], pos, rot_f, Vector2(1.05, 1.05), Color(1.0, 1.0, 1.0, alpha), Vector2(0.5, 0.75))

	# Draw rising flame_puffs (fire_effect.as + Symbol 517..519.xml exact color & alpha gradient: yellow core -> orange body -> red tip)
	for flp: Dictionary in flame_puffs:
		var fl_pos: Vector2 = flp.get("pos", Vector2.ZERO) as Vector2
		var fl_age: float = float(flp.get("age", 0.0))
		var fl_max: float = maxf(1.0, float(flp.get("max_age", 15.0)))
		var pct: float = clampf(fl_age / fl_max, 0.0, 1.0)
		var fl_alpha: float = clampf(0.85 - pct * 0.62, 0.18, 0.88)
		var fl_sc: float = float(flp.get("scale", 1.0)) * (1.05 - pct * 0.32)
		var seq_id: int = int(flp.get("seq_id", 0))
		var fl_col: Color
		if pct < 0.35:
			fl_col = Color(1.0, 0.95, 0.38, fl_alpha).lerp(Color(1.0, 0.68, 0.16, fl_alpha), pct / 0.35)
		elif pct < 0.72:
			fl_col = Color(1.0, 0.68, 0.16, fl_alpha).lerp(Color(0.98, 0.34, 0.08, fl_alpha), (pct - 0.35) / 0.37)
		else:
			fl_col = Color(0.98, 0.34, 0.08, fl_alpha).lerp(Color(0.65, 0.16, 0.05, fl_alpha * 0.75), (pct - 0.72) / 0.28)

		if bool(flp.get("is_ground", false)):
			if not _fire_ground_seq.is_empty():
				var g_i: int = seq_id % _fire_ground_seq.size()
				_draw_tex_xform(_fire_ground_seq[g_i], fl_pos, 0.0, Vector2(fl_sc * 0.95, fl_sc * 0.75), Color(1.0, 0.88, 0.32, fl_alpha * 0.85), Vector2(0.5, 0.85))
		else:
			var r_seq: Array[Texture2D] = _fire_01_seq
			if seq_id % 3 == 1 and not _fire_02_seq.is_empty():
				r_seq = _fire_02_seq
			elif seq_id % 3 == 2 and not _fire_03_seq.is_empty():
				r_seq = _fire_03_seq
			if not r_seq.is_empty():
				var fr_i: int = clampi(int(pct * float(r_seq.size())), 0, r_seq.size() - 1)
				_draw_tex_xform(r_seq[fr_i], fl_pos, 0.0, Vector2(fl_sc, fl_sc), fl_col, Vector2(0.5, 0.75))

	# 4. Draw 2-Stage Burning on fighters (FireNodeData.as:256-291):
	#    Stage 1 (15 <= burn_state < 100): compact single flame (fire_01)
	#    Stage 2 (burn_state >= 100 or freshly burning corpse): large enveloping fire_big + inner core flame
	var fighters: Array = _get_fighters()
	for f_var: Variant in fighters:
		if not is_instance_valid(f_var):
			continue
		var f: Node2D = f_var as Node2D
		var b_state: float = float(f.get("burn_state")) if f.get("burn_state") != null else 0.0
		if b_state >= 15.0:
			var f_pos: Vector2 = f.global_position
			var is_stage_2: bool = (b_state >= 100.0) or (bool(f.get("is_dead")) and bool(f.get("burned")) and b_state >= 25.0)
			if is_stage_2 and not _fire_big_seq.is_empty():
				var b_idx: int = int(_visual_tick * 1.2) % _fire_big_seq.size()
				_draw_tex_xform(_fire_big_seq[b_idx], f_pos + Vector2(0.0, -9.0), 0.0, Vector2(0.92, 0.96), Color(1.0, 0.68, 0.16, 0.78), Vector2(0.5, 0.78))
				if not _fire_02_seq.is_empty():
					var c_idx: int = int(_visual_tick * 1.4) % _fire_02_seq.size()
					_draw_tex_xform(_fire_02_seq[c_idx], f_pos + Vector2(0.0, -7.0), 0.0, Vector2(0.95, 0.95), Color(1.0, 0.92, 0.35, 0.85), Vector2(0.5, 0.75))
			elif not _fire_01_seq.is_empty():
				var s_idx: int = int(_visual_tick * 1.3) % _fire_01_seq.size()
				_draw_tex_xform(_fire_01_seq[s_idx], f_pos + Vector2(0.0, -8.0), 0.0, Vector2(0.76, 0.76), Color(1.0, 0.78, 0.25, 0.76), Vector2(0.5, 0.75))

	# 5. Draw weapon-specific muzzle flashes (muzzle_pistol / rifle / shotgun / sniper / bazooka)
	for mf: Dictionary in muzzle_flashes:
		var pos: Vector2 = mf.get("pos", Vector2.ZERO) as Vector2
		var ang_rad: float = deg_to_rad(float(mf.get("angle_deg", 0.0)))
		var wid: String = str(mf.get("weapon_id", "PISTOL")).to_upper()
		var age: float = float(mf.get("age", 0.0))

		var m_seq: Array[Texture2D] = _muzzle_pistol_seq
		if wid in ["RIFLE", "TOMMY_GUN", "SMG", "M60"]:
			m_seq = _muzzle_rifle_seq
		elif wid in ["SHOTGUN", "SAWED_OFF"]:
			m_seq = _muzzle_shotgun_seq
		elif wid in ["BAZOOKA"] and not _muzzle_bazooka_seq.is_empty():
			m_seq = _muzzle_bazooka_seq
		elif wid in ["SNIPER", "BAZOOKA", "LASER_GUN"]:
			m_seq = _muzzle_sniper_seq

		if not m_seq.is_empty():
			var m_idx: int = clampi(int(age), 0, m_seq.size() - 1)
			_draw_tex_xform(m_seq[m_idx], pos, ang_rad, Vector2.ONE, Color.WHITE, Vector2(0.15, 0.5))

	# 6. Draw melee weapon slash traces (trace_axe_01..03, trace_machete_01..03, trace_sword_01..03)
	for mt: Dictionary in melee_traces:
		var pos: Vector2 = mt.get("pos", Vector2.ZERO) as Vector2
		var facing_i: int = int(mt.get("facing", 1))
		var t_kind: String = str(mt.get("trace_kind", "machete"))
		var c_step: int = clampi(int(mt.get("combo_step", 1)), 1, 3)
		var age: float = float(mt.get("age", 0.0))
		var max_age: float = maxf(1.0, float(mt.get("max_age", 4.0)))
		var alpha: float = clampf(1.0 - (age / max_age) * 0.7, 0.0, 1.0)

		var t_seq: Array[Texture2D] = _trace_machete_seq
		if t_kind == "sword":
			t_seq = _trace_sword_seq
		elif t_kind == "axe":
			t_seq = _trace_axe_seq
		if not t_seq.is_empty():
			var tex_t: Texture2D = t_seq[clampi(c_step - 1, 0, t_seq.size() - 1)]
			_draw_tex_xform(tex_t, pos, 0.0, Vector2(float(facing_i), 1.0), Color(1.0, 1.0, 1.0, alpha))

	# 7. Draw physical shell casings (shell_small / shell_big / shell_shotgun)
	for sc: Dictionary in shell_casings:
		var pos: Vector2 = sc.get("pos", Vector2.ZERO) as Vector2
		var rot: float = float(sc.get("rot", 0.0))
		var s_type: String = str(sc.get("shell_type", "small"))
		var s_tex: Texture2D = _tex_shell_small
		if s_type == "shotgun" and _tex_shell_shotgun != null:
			s_tex = _tex_shell_shotgun
		elif s_type == "big" and _tex_shell_big != null:
			s_tex = _tex_shell_big
		if s_tex != null:
			_draw_tex_xform(s_tex, pos, rot, Vector2.ONE, Color.WHITE)

	# 8. Draw physical prop debris (crate, barrel, table, paper) & electric sparks
	for pd: Dictionary in prop_debris:
		var pos: Vector2 = pd.get("pos", Vector2.ZERO) as Vector2
		var rot: float = float(pd.get("rot", 0.0))
		var age: float = float(pd.get("age", 0.0))
		var max_age: float = maxf(1.0, float(pd.get("max_age", 75.0)))
		var alpha: float = clampf((max_age - age) / 15.0, 0.0, 1.0)
		var cat: String = str(pd.get("category", "crate"))
		var var_idx: int = int(pd.get("variant", 0))
		var d_seq: Array[Texture2D] = _debris_crate_seq
		if cat == "barrel":
			d_seq = _debris_barrel_seq
		elif cat == "table":
			d_seq = _debris_table_seq
		elif cat == "paper":
			d_seq = _debris_paper_seq
		if not d_seq.is_empty():
			var d_tex: Texture2D = d_seq[var_idx % d_seq.size()]
			_draw_tex_xform(d_tex, pos, rot, Vector2.ONE, Color(1.0, 1.0, 1.0, alpha))

	for el: Dictionary in electric_sparks:
		if not _electric_seq.is_empty():
			var pos_e: Vector2 = el.get("pos", Vector2.ZERO) as Vector2
			var age_e: int = clampi(int(el.get("age", 0.0)), 0, _electric_seq.size() - 1)
			_draw_tex_xform(_electric_seq[age_e], pos_e, float(el.get("rot", 0.0)), Vector2.ONE, Color.WHITE)

	# 9. Draw hit sparks (single subtle metal spark or crisp 2x2 pixel impact dust & blood_1..3)
	for hs: Dictionary in hit_sparks:
		var pos: Vector2 = hs.get("pos", Vector2.ZERO) as Vector2
		var age: float = float(hs.get("age", 0.0))
		var max_age: float = maxf(1.0, float(hs.get("max_age", 10.0)))
		var alpha: float = clampf(1.0 - age / max_age, 0.0, 1.0)
		if bool(hs.get("is_blood", false)):
			if _tex_blood != null:
				_draw_tex_xform(_tex_blood, pos, float(hs.get("rot", 0.0)), Vector2.ONE, Color(1.0, 1.0, 1.0, alpha))
		else:
			draw_rect(Rect2(pos.x - 1.0, pos.y - 1.0, 2.0, 2.0), Color(1.0, 0.92, 0.38, alpha), true)

	# 10. Draw glass shards & character gibs
	for gs: Dictionary in glass_shards:
		var pos: Vector2 = gs.get("pos", Vector2.ZERO) as Vector2
		if _tex_glass != null:
			_draw_tex_xform(_tex_glass, pos, float(gs.get("rot", 0.0)), Vector2.ONE, Color(1.0, 1.0, 1.0, 0.9))
	for gb: Dictionary in gibs:
		var pos: Vector2 = gb.get("pos", Vector2.ZERO) as Vector2
		if _tex_gib != null:
			_draw_tex_xform(_tex_gib, pos, float(gb.get("rot", 0.0)), Vector2.ONE, Color.WHITE)

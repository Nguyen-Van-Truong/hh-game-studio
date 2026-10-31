class_name ProjectileManager
extends Node2D
## Visible Ballistic Projectiles, Rockets (with Rocket Riding), Flamethrower Stream,
## Deflection, and Throwables (Grenade, Molotov, C4, Mine, MUGEN Chakra Wave)
## for Superfighters Y8 Remake (SF-M3 / SF-M6 / SF-M8).
## Uses authentic Flash sprite frames (bullet_normal, bullet_shotgun, bullet_sniper,
## bullet_slomo_f01..11, bazooka_rocket_f01..04, fire_flamethrower_f01..12,
## wpn_grenade_thrown, wpn_molotov_thrown).

const THROWABLE_GRAVITY_24HZ: float = 0.45
const GRENADE_RESTITUTION: float = 0.35
const GRENADE_FRICTION: float = 0.60

const BALLISTIC_SPECS: Dictionary = {
	"PISTOL": {"speed": 30.0, "range": 1200.0, "damage": 10.0, "crit_chance": 0.05, "crit_dmg": 15.0, "pushback": 15.0, "spread": 1.0, "pellets": 1, "strength": 5},
	"SILENCED_PISTOL": {"speed": 32.0, "range": 1200.0, "damage": 9.0, "crit_chance": 0.10, "crit_dmg": 14.0, "pushback": 12.0, "spread": 0.8, "pellets": 1, "strength": 5},
	"MAGNUM": {"speed": 40.0, "range": 1200.0, "damage": 25.0, "crit_chance": 0.40, "crit_dmg": 35.0, "pushback": 50.0, "spread": 0.5, "pellets": 1, "strength": 15},
	"UZI": {"speed": 30.0, "range": 1200.0, "damage": 7.0, "crit_chance": 0.04, "crit_dmg": 10.0, "pushback": 10.0, "spread": 6.0, "pellets": 1, "strength": 5},
	"FLARE_GUN": {"speed": 22.0, "range": 1200.0, "damage": 8.0, "crit_chance": 0.0, "crit_dmg": 8.0, "pushback": 20.0, "spread": 1.5, "pellets": 1, "strength": 1, "is_flare": true},
	"SHOTGUN": {"speed": 30.0, "range": 1200.0, "damage": 6.0, "crit_chance": 0.0, "crit_dmg": 6.0, "pushback": 33.0, "spread": 4.3, "pellets": 4, "strength": 5},
	"SAWED_OFF": {"speed": 28.0, "range": 1200.0, "damage": 6.0, "crit_chance": 0.0, "crit_dmg": 6.0, "pushback": 35.0, "spread": 7.5, "pellets": 4, "strength": 5},
	"RIFLE": {"speed": 35.0, "range": 1200.0, "damage": 8.0, "crit_chance": 0.06, "crit_dmg": 10.0, "pushback": 20.0, "spread": 3.0, "pellets": 1, "strength": 5},
	"TOMMY_GUN": {"speed": 32.0, "range": 1200.0, "damage": 7.5, "crit_chance": 0.05, "crit_dmg": 11.0, "pushback": 15.0, "spread": 4.5, "pellets": 1, "strength": 5},
	"SMG": {"speed": 32.0, "range": 1200.0, "damage": 7.5, "crit_chance": 0.05, "crit_dmg": 11.0, "pushback": 15.0, "spread": 4.5, "pellets": 1, "strength": 5},
	"M60": {"speed": 34.0, "range": 1200.0, "damage": 9.0, "crit_chance": 0.08, "crit_dmg": 13.0, "pushback": 25.0, "spread": 4.0, "pellets": 1, "strength": 10},
	"SNIPER": {"speed": 40.0, "range": 1200.0, "damage": 30.0, "crit_chance": 0.75, "crit_dmg": 60.0, "pushback": 50.0, "spread": 0.0, "pellets": 1, "strength": 30},
	"LASER_GUN": {"speed": 45.0, "range": 1200.0, "damage": 42.0, "crit_chance": 0.25, "crit_dmg": 60.0, "pushback": 35.0, "spread": 0.0, "pellets": 1, "strength": 30},
	"BAZOOKA": {"speed": 18.0, "range": 1200.0, "damage": 20.0, "crit_chance": 0.0, "crit_dmg": 20.0, "pushback": 60.0, "spread": 2.0, "pellets": 1, "strength": 1, "is_rocket": true},
	"FLAMETHROWER": {"speed": 8.5, "range": 102.0, "damage": 1.2, "crit_chance": 0.0, "crit_dmg": 1.2, "pushback": 2.0, "spread": 4.5, "pellets": 1, "strength": 1, "is_flame": true},
	"CHAKRA_WAVE": {"speed": 22.0, "range": 320.0, "damage": 20.0, "crit_chance": 0.0, "crit_dmg": 20.0, "pushback": 35.0, "spread": 0.0, "pellets": 1, "strength": 10, "is_mugen_wave": true},
}

var match_world: Node2D = null
var external_fighters: Array = []
var fire_hazard_system_override: Node2D = null
var default_floor_y: float = 154.0

var bullets: Array[Dictionary] = []
var throwables: Array[Dictionary] = []
var slomo_rings: Array[Dictionary] = []

var total_bullets_spawned: int = 0
var total_throwables_spawned: int = 0
var _last_elevator_motion_serial: int = -1

var _textures_loaded: bool = false
var _tex_rocket: Texture2D = null
var _tex_rocket_frames: Array[Texture2D] = []
var _tex_grenade: Texture2D = null
var _tex_molotov: Texture2D = null
var _tex_bullet_normal: Texture2D = null
var _tex_bullet_pistol: Texture2D = null
var _tex_bullet_rifle: Texture2D = null
var _tex_bullet_uzi: Texture2D = null
var _tex_bullet_magnum: Texture2D = null
var _tex_bullet_shotgun: Texture2D = null
var _tex_bullet_sniper: Texture2D = null
var _tex_bullet_slomo_frames: Array[Texture2D] = []
var _tex_flamethrower_frames: Array[Texture2D] = []
var _tex_fire_small_frames: Array[Texture2D] = []


func _init() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	z_index = 12


func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	z_index = 12
	_load_projectile_textures()


func _load_tex(reg: Node, res_path: String) -> Texture2D:
	if reg != null and reg.has_method("load_cached_texture"):
		var t: Texture2D = reg.call("load_cached_texture", res_path) as Texture2D
		if t != null:
			return t
	var abs_p: String = ProjectSettings.globalize_path(res_path)
	if FileAccess.file_exists(abs_p):
		var img: Image = Image.load_from_file(abs_p)
		if img != null and not img.is_empty():
			return ImageTexture.create_from_image(img)
	return null


func _load_seq(reg: Node, prefix: String, count: int) -> Array[Texture2D]:
	var arr: Array[Texture2D] = []
	for i: int in range(1, count + 1):
		var p: String = "%s_f%02d.png" % [prefix, i]
		var t: Texture2D = _load_tex(reg, p)
		if t != null:
			arr.append(t)
	return arr


func _load_projectile_textures() -> void:
	if _textures_loaded:
		return
	var reg: Node = null
	var tree: SceneTree = Engine.get_main_loop() as SceneTree
	if tree != null and tree.root != null:
		reg = tree.root.get_node_or_null("SFDataRegistry")

	_tex_rocket = _load_tex(reg, "res://assets/sprites/effects/bazooka_rocket.png")
	_tex_rocket_frames = _load_seq(reg, "res://assets/sprites/effects/bazooka_rocket", 4)
	_tex_grenade = _load_tex(reg, "res://assets/sprites/weapons/wpn_grenade_thrown.png")
	_tex_molotov = _load_tex(reg, "res://assets/sprites/weapons/wpn_molotov_thrown.png")

	_tex_bullet_normal = _load_tex(reg, "res://assets/sprites/effects/bullet_normal.png")
	_tex_bullet_pistol = _load_tex(reg, "res://assets/sprites/effects/bullet_pistol.png")
	_tex_bullet_rifle = _load_tex(reg, "res://assets/sprites/effects/bullet_rifle.png")
	_tex_bullet_uzi = _load_tex(reg, "res://assets/sprites/effects/bullet_uzi.png")
	_tex_bullet_magnum = _load_tex(reg, "res://assets/sprites/effects/bullet_magnum.png")
	_tex_bullet_shotgun = _load_tex(reg, "res://assets/sprites/effects/bullet_shotgun.png")
	_tex_bullet_sniper = _load_tex(reg, "res://assets/sprites/effects/bullet_sniper.png")

	_tex_bullet_slomo_frames = _load_seq(reg, "res://assets/sprites/effects/bullet_slomo", 11)
	_tex_flamethrower_frames = _load_seq(reg, "res://assets/sprites/effects/fire_flamethrower", 12)
	_tex_fire_small_frames = _load_seq(reg, "res://assets/sprites/effects/fire_01", 11)
	_textures_loaded = true


func _is_slowmo_active() -> bool:
	if match_world != null and is_instance_valid(match_world):
		var gs: Variant = match_world.get("game_speed")
		if gs != null and float(gs) < 0.8:
			return true
	return false


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


func _get_fire_hazard_system() -> Object:
	if fire_hazard_system_override != null:
		return fire_hazard_system_override
	if match_world != null:
		var fhs: Variant = match_world.get("fire_hazard_system")
		if fhs is Object:
			return fhs as Object
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


func spawn_bullet(
	owner_fighter: Node2D,
	weapon_id: String,
	start_pos: Vector2,
	angle_deg: float,
	ignore_cover_id: int = -1
) -> void:
	_load_projectile_textures()
	var key: String = weapon_id.to_upper()
	var spec: Dictionary = BALLISTIC_SPECS.get(key, BALLISTIC_SPECS["PISTOL"]) as Dictionary
	var pellets: int = int(spec.get("pellets", 1))
	var spread_deg: float = float(spec.get("spread", 1.0))
	var spd: float = float(spec.get("speed", 30.0))
	var max_range: float = float(spec.get("range", 1200.0))
	var base_dmg: float = float(spec.get("damage", 10.0))
	var crit_chance: float = float(spec.get("crit_chance", 0.05))
	var crit_dmg: float = float(spec.get("crit_dmg", 15.0))
	var pushback: float = float(spec.get("pushback", 15.0))
	var b_strength: int = int(spec.get("strength", 5))
	var is_rocket: bool = bool(spec.get("is_rocket", false))
	var is_flare: bool = bool(spec.get("is_flare", false))
	var is_flame: bool = bool(spec.get("is_flame", false))
	var is_mugen_wave: bool = bool(spec.get("is_mugen_wave", false))

	for i: int in range(pellets):
		var pellet_offset: float = 0.0
		if pellets > 1:
			var t: float = (float(i) / float(pellets - 1)) - 0.5
			pellet_offset = t * spread_deg * 2.0 + randf_range(-0.6, 0.6)
		elif spread_deg > 0.0:
			pellet_offset = randf_range(-spread_deg, spread_deg)

		var final_deg: float = angle_deg + pellet_offset
		var rad: float = deg_to_rad(final_deg)
		var dir: Vector2 = Vector2(cos(rad), sin(rad)).normalized()
		var is_crit: bool = (crit_chance > 0.0 and randf() < crit_chance)
		var dmg: float = crit_dmg if is_crit else base_dmg
		var origin_pos: Vector2 = start_pos
		if is_instance_valid(owner_fighter):
			var f_face: float = float(owner_fighter.get("facing")) if owner_fighter.get("facing") != null else 1.0
			var shoulder_y: float = -8.5 if bool(owner_fighter.get("kneeling")) else -12.5
			origin_pos = owner_fighter.global_position + Vector2(f_face * -2.5, shoulder_y)

		bullets.append({
			"owner": owner_fighter,
			"weapon_id": key,
			"pos": start_pos,
			"prev_pos": start_pos,
			"origin_pos": origin_pos,
			"dir": dir,
			"vel": dir * spd,
			"angle_deg": final_deg,
			"speed": spd,
			"traveled": 0.0,
			"max_range": max_range,
			"damage": dmg,
			"is_crit": is_crit,
			"pushback": pushback,
			"strength_left": b_strength,
			"penetrated_prop_ids": [],
			"ignore_cover_id": ignore_cover_id,
			"is_rocket": is_rocket,
			"is_flare": is_flare,
			"is_flame": is_flame,
			"is_mugen_wave": is_mugen_wave,
			"deflected": false,
			"rider": null,
			"wobble_phase": randf() * TAU,
			"age": 0.0,
			"max_age": 12.0 if is_flame else 240.0,
			"slomo_ring_accum": 0.0,
		})
		total_bullets_spawned += 1
	queue_redraw()


func spawn_mugen_projectile(
	owner_fighter: Node2D,
	proj_id: String,
	start_pos: Vector2,
	angle_deg: float,
	speed_24hz: float = 22.0,
	damage: float = 20.0,
	pushback: float = 35.0
) -> void:
	_load_projectile_textures()
	var rad: float = deg_to_rad(angle_deg)
	var dir: Vector2 = Vector2(cos(rad), sin(rad)).normalized()
	bullets.append({
		"owner": owner_fighter,
		"weapon_id": proj_id.to_upper(),
		"pos": start_pos,
		"prev_pos": start_pos,
		"dir": dir,
		"vel": dir * speed_24hz,
		"angle_deg": angle_deg,
		"speed": speed_24hz,
		"traveled": 0.0,
		"max_range": 320.0,
		"damage": damage,
		"is_crit": false,
		"pushback": pushback,
		"strength_left": 10,
		"penetrated_prop_ids": [],
		"ignore_cover_id": -1,
		"is_rocket": false,
		"is_flare": false,
		"is_flame": false,
		"is_mugen_wave": true,
		"deflected": false,
		"rider": null,
		"wobble_phase": 0.0,
		"age": 0.0,
		"max_age": 240.0,
		"slomo_ring_accum": 0.0,
	})
	total_bullets_spawned += 1
	queue_redraw()


func spawn_throwable(
	owner_fighter: Node2D,
	weapon_id: String,
	start_pos: Vector2,
	angle_deg: float,
	remaining_fuse_frames: float = 72.0,
	ignore_cover_id: int = -1
) -> void:
	_load_projectile_textures()
	var key: String = weapon_id.to_upper()
	var rad: float = deg_to_rad(angle_deg)
	# AS3 Player.as:2738-2740 throw velocity: vx = cos(angle)*6.8, vy = sin(angle)*6.8 - 2.5 (in px/frame 24Hz)
	var vel: Vector2 = Vector2(cos(rad) * 6.8, sin(rad) * 6.8 - 2.5)
	if key == "C4" or key == "MINE":
		vel = Vector2(cos(rad) * 5.0, sin(rad) * 5.0 - 1.8)

	# When throwing upward near the bottom/body of a ladder shaft, ensure vertical impulse can reach the upper floor opening
	var ml_sp: Object = _get_map_loader()
	if ml_sp != null and sin(rad) < -0.5 and ml_sp.get("ladder_rects") != null:
		for lr_v: Variant in ml_sp.get("ladder_rects") as Array:
			var lr: Rect2 = lr_v as Rect2
			var cx: float = lr.position.x + lr.size.x * 0.5
			if absf(start_pos.x - cx) <= 28.0 and start_pos.y >= lr.position.y + 12.0 and start_pos.y <= lr.end.y + 28.0:
				var target_top_y: float = lr.position.y - 18.0
				var needed_rise: float = maxf(0.0, start_pos.y - target_top_y)
				var min_up_vy: float = -sqrt(2.0 * THROWABLE_GRAVITY_24HZ * needed_rise) - 0.85
				if vel.y > min_up_vy:
					vel.y = min_up_vy
				var exit_vx: float = cos(rad) * (3.2 if (key != "C4" and key != "MINE") else 2.4)
				if absf(exit_vx) < 1.35:
					exit_vx = (1.6 if cos(rad) >= 0.0 else -1.6)
				var dx_to_shaft: float = cx - start_pos.x
				var ticks_to_top: float = maxf(6.0, absf(vel.y) / THROWABLE_GRAVITY_24HZ)
				vel.x = clampf(dx_to_shaft / ticks_to_top + exit_vx * 0.35, -2.8, 2.8)
				break

	var init_exit_vx: float = cos(rad) * (3.2 if (key != "C4" and key != "MINE") else 2.4)
	if absf(init_exit_vx) < 1.2:
		init_exit_vx = 1.5 if cos(rad) >= 0.0 else -1.5

	throwables.append({
		"owner": owner_fighter,
		"weapon_id": key,
		"pos": start_pos,
		"prev_pos": start_pos,
		"vel": vel,
		"shaft_exit_vx": init_exit_vx,
		"portal_cd": 0.0,
		"rot": 0.0,
		"rot_vel": 0.35 if vel.x >= 0.0 else -0.35,
		"fuse_frames": clampf(remaining_fuse_frames, 1.0, 600.0),
		"age": 0.0,
		"settled": false,
		"spark_accum": 0.0,
		"ignore_cover_id": ignore_cover_id,
	})
	total_throwables_spawned += 1
	queue_redraw()


func deflect_bullets_in_box(deflector: Node2D, rect: Rect2, facing_dir: int) -> int:
	var count: int = 0
	for b: Dictionary in bullets:
		if bool(b.get("is_flame", false)):
			continue
		if b.get("owner") == deflector and not bool(b.get("deflected", false)):
			continue
		var pos: Vector2 = b.get("pos", Vector2.ZERO) as Vector2
		var prev_pos: Vector2 = b.get("prev_pos", pos) as Vector2
		if rect.has_point(pos) or rect.has_point(prev_pos) or _segment_intersects_rect(prev_pos, pos, rect):
			var cur_dir: Vector2 = b.get("dir", Vector2.RIGHT) as Vector2
			var new_dir: Vector2 = Vector2(float(facing_dir), -cur_dir.y + randf_range(-0.18, 0.18)).normalized()
			b["dir"] = new_dir
			b["angle_deg"] = rad_to_deg(atan2(new_dir.y, new_dir.x))
			b["owner"] = deflector
			b["deflected"] = true
			b["traveled"] = 0.0
			count += 1
			_play_sfx("ricochet", pos)
	if count > 0:
		queue_redraw()
	return count


func has_kickable_throwable_near(foot_pos: Vector2, facing_dir: int) -> bool:
	# AS3 MapPremadeItems.as:603-605 & Player.as:7214-7229 (KickHit):
	# Live GRENADE_THROWN / C4 / MINE near the fighter's feet are Kickable dynamic bodies!
	var fdir: int = 1 if facing_dir >= 0 else -1
	var k_rect: Rect2 = Rect2(
		foot_pos.x - 4.0 if fdir >= 0 else (foot_pos.x - 14.0),
		foot_pos.y - 12.0,
		18.0,
		18.0
	)
	for th: Dictionary in throwables:
		var wid: String = str(th.get("weapon_id", "GRENADE")).to_upper()
		if wid == "MOLOTOV":
			continue
		var pos: Vector2 = th.get("pos", Vector2.ZERO) as Vector2
		if k_rect.has_point(pos):
			return true
	return false


func kick_throwables_in_rect(k_rect: Rect2, facing_dir: int, kicker: Node2D = null) -> int:
	# AS3 MapPremadeItems.as:603-605 (KickPower = 3.5, KickWeightCalculation = true) & Player.as:5731-5762:
	# Kicking a live grenade at the feet launches it far across the arena!
	var fdir: float = 1.0 if facing_dir >= 0 else -1.0
	var search_rect: Rect2 = k_rect.grow(4.0)
	var kicked_count: int = 0
	var fhs: Object = _get_fire_hazard_system()
	for th: Dictionary in throwables:
		var wid: String = str(th.get("weapon_id", "GRENADE")).to_upper()
		if wid == "MOLOTOV":
			continue
		var pos: Vector2 = th.get("pos", Vector2.ZERO) as Vector2
		if search_rect.has_point(pos):
			th["vel"] = Vector2(fdir * 3.5, -2.15)
			th["pos"] = pos + Vector2(fdir * 1.5, -1.0)
			th["settled"] = false
			th["rot_vel"] = fdir * 0.35
			if kicker != null and is_instance_valid(kicker):
				th["owner"] = kicker
			kicked_count += 1
			_play_sfx("kick", pos)
			if fhs != null and fhs.has_method("spawn_hit_sparks"):
				fhs.call("spawn_hit_sparks", pos, true)
	if kicked_count > 0:
		queue_redraw()
	return kicked_count


func step_projectiles(step_24hz: float) -> void:
	var had_any: bool = not bullets.is_empty() or not throwables.is_empty() or not slomo_rings.is_empty()
	_step_bullets(step_24hz)
	_step_throwables(step_24hz)
	_step_slomo_rings(step_24hz)
	if had_any or not bullets.is_empty() or not throwables.is_empty() or not slomo_rings.is_empty():
		queue_redraw()


func _step_slomo_rings(step_24hz: float) -> void:
	if slomo_rings.is_empty():
		return
	var next_rings: Array[Dictionary] = []
	var total_f: int = maxi(1, _tex_bullet_slomo_frames.size())
	for sr: Dictionary in slomo_rings:
		var frame_f: float = float(sr.get("frame", 0.0)) + step_24hz * 1.15
		if int(frame_f) < total_f:
			sr["frame"] = frame_f
			next_rings.append(sr)
	slomo_rings = next_rings


func _step_bullets(step_24hz: float) -> void:
	if bullets.is_empty():
		return
	var ml: Object = _get_map_loader()
	var fhs: Object = _get_fire_hazard_system()
	var fighters: Array = _get_fighters()
	var props: Array = _get_props()
	var slowmo_now: bool = _is_slowmo_active()

	# Pre-cache active prop rects once per step to avoid O(bullets * props) dynamic call() overhead
	var cached_props: Array[Dictionary] = []
	for p_var: Variant in props:
		if not is_instance_valid(p_var):
			continue
		var prop: Node2D = p_var as Node2D
		if bool(prop.get("is_destroyed")):
			continue
		var pid: int = int(prop.get("prop_id")) if prop.get("prop_id") != null else prop.get_instance_id()
		var p_rect: Rect2 = prop.call("get_hit_rect") as Rect2 if prop.has_method("get_hit_rect") else Rect2(prop.global_position.x - 8.0, prop.global_position.y - 14.0, 16.0, 14.0)
		cached_props.append({"node": prop, "id": pid, "rect": p_rect})

	var next_bullets: Array[Dictionary] = []
	for b: Dictionary in bullets:
		var prev_pos: Vector2 = b.get("pos", Vector2.ZERO) as Vector2
		var spd: float = float(b.get("speed", 30.0))
		var is_rocket: bool = bool(b.get("is_rocket", false))
		var is_flare: bool = bool(b.get("is_flare", false))
		var is_flame: bool = bool(b.get("is_flame", false))
		var angle_deg: float = float(b.get("angle_deg", 0.0))
		var age: float = float(b.get("age", 0.0)) + step_24hz
		var max_age: float = float(b.get("max_age", 240.0))
		b["age"] = age

		if age >= max_age:
			continue

		if is_rocket:
			var cur_rider: Node2D = b.get("rider", null) as Node2D
			if is_instance_valid(cur_rider) and not bool(cur_rider.get("is_dead")):
				# AS3 ProjectilesUpdater.as:822-826: rocket speed halves when carrying a player
				spd *= 0.5
				var r_timer: float = float(b.get("ride_timer", 0.0)) + step_24hz
				b["ride_timer"] = r_timer
				if r_timer > 150.0:
					_detonate_rocket(b, prev_pos, fhs)
					continue
				# AS3 Player.as:414-421 + Up/Down steering: rider steers the rocket in flight!
				var r_inp: Dictionary = {}
				if cur_rider.has_method("get_last_input_state"):
					r_inp = cur_rider.call("get_last_input_state") as Dictionary
				elif typeof(cur_rider.get("_prev_input")) == TYPE_DICTIONARY:
					r_inp = cur_rider.get("_prev_input") as Dictionary
				var steer_deg: float = 0.0
				if bool(r_inp.get("right", false)):
					steer_deg += 20.0 * step_24hz
				if bool(r_inp.get("left", false)):
					steer_deg -= 20.0 * step_24hz
				var cur_cos: float = cos(deg_to_rad(angle_deg))
				if bool(r_inp.get("up", false)):
					steer_deg += (-18.0 if cur_cos >= 0.0 else 18.0) * step_24hz
				if bool(r_inp.get("down", false)):
					steer_deg += (18.0 if cur_cos >= 0.0 else -18.0) * step_24hz
				angle_deg += steer_deg
			else:
				var w_phase: float = float(b.get("wobble_phase", 0.0)) + 0.55 * step_24hz
				b["wobble_phase"] = w_phase
				angle_deg += sin(w_phase) * 3.5 * step_24hz
			b["angle_deg"] = angle_deg
			var r_rad: float = deg_to_rad(angle_deg)
			b["dir"] = Vector2(cos(r_rad), sin(r_rad)).normalized()
			# Spawn authentic smoke_trace_f01..10 puff at rocket tail at 24Hz cadence
			var r_smk: float = float(b.get("smoke_accum", 1.0)) + step_24hz
			if r_smk >= 1.0:
				r_smk -= 1.0
				if fhs != null and fhs.has_method("spawn_smoke_puff"):
					var r_dir: Vector2 = b["dir"] as Vector2
					fhs.call("spawn_smoke_puff", prev_pos - r_dir * 7.0, -r_dir * 0.35 + Vector2(randf_range(-0.15, 0.15), randf_range(-0.22, 0.12)), randf_range(0.85, 1.15))
			b["smoke_accum"] = r_smk

		var dir: Vector2 = b.get("dir", Vector2.RIGHT) as Vector2
		var step_dist: float = spd * step_24hz
		var next_pos: Vector2 = prev_pos + dir * step_dist
		if is_flame:
			var fvel: Vector2 = b.get("vel", dir * spd) as Vector2
			fvel.y += 0.08 * step_24hz
			fvel.x *= pow(0.96, step_24hz)
			b["vel"] = fvel
			next_pos = prev_pos + fvel * step_24hz
			if fvel.length_squared() > 0.001:
				dir = fvel.normalized()
				b["dir"] = dir
			step_dist = prev_pos.distance_to(next_pos)

		# Spawn Slow-Mo bullet ring trail when game_speed < 0.8
		if slowmo_now and not is_rocket and not is_flame and not is_flare and not bool(b.get("is_mugen_wave", false)):
			var s_acc: float = float(b.get("slomo_ring_accum", 0.0)) + step_dist
			if s_acc >= 9.0:
				s_acc = 0.0
				slomo_rings.append({
					"pos": prev_pos.lerp(next_pos, 0.5),
					"rot": dir.angle(),
					"frame": 0.0,
				})
			b["slomo_ring_accum"] = s_acc

		# Flare Gun fire trail sparks in flight (throttled to 24Hz)
		if is_flare and fhs != null and fhs.has_method("spawn_smoke_puff"):
			var fl_smk: float = float(b.get("smoke_accum", 0.0)) + step_24hz
			if fl_smk >= 1.8:
				fl_smk = 0.0
				fhs.call("spawn_smoke_puff", prev_pos - dir * 4.0, -dir * 0.25 + Vector2(0.0, -0.2), 0.55)
			b["smoke_accum"] = fl_smk

		var ignore_cover_id: int = int(b.get("ignore_cover_id", -1))
		var vel_vec: Vector2 = dir * spd

		# 1. Glass windows: break glass and let bullet continue!
		if ml != null and ml.has_method("check_and_break_glass_segment"):
			ml.call("check_and_break_glass_segment", prev_pos, next_pos, vel_vec)

		# 2. Portals: teleport bullet if entering portal (top <-> bottom, flipping dir.x when flip_x == true)
		if ml != null and not bool(b.get("teleported", false)) and ml.has_method("try_teleport_ballistic_segment"):
			var tp_b: Dictionary = ml.call("try_teleport_ballistic_segment", prev_pos, next_pos, dir, 2.0) as Dictionary
			if bool(tp_b.get("teleported", false)):
				dir = (tp_b.get("vel", dir) as Vector2).normalized()
				b["dir"] = dir
				if bool(tp_b.get("flip_x", false)):
					var v_b: Vector2 = b.get("vel", dir * spd) as Vector2
					v_b.x = -v_b.x
					b["vel"] = v_b
					b["angle_deg"] = rad_to_deg(atan2(dir.y, dir.x))
				prev_pos = tp_b.get("exit_origin", next_pos) as Vector2
				var rem_step: float = maxf(2.0, step_dist * float(tp_b.get("remaining_ratio", 0.5)))
				next_pos = prev_pos + dir * rem_step
				b["pos"] = prev_pos
				b["teleported"] = true

		# 3. Solid wall/floor raycast (static map geometry only; props are checked in step 4)
		var hit_wall: bool = false
		var wall_hit_pos: Vector2 = next_pos
		if ml != null and ml.has_method("raycast_solid"):
			# AS3 ordinary bullets penetrate CLOUD supports. Tilted CLOUD boxes
			# must behave like the flat ones instead of becoming bullet walls.
			var ray_res: Dictionary = ml.call("raycast_solid", prev_pos, next_pos, ignore_cover_id, false, false) as Dictionary
			if bool(ray_res.get("hit", false)):
				var cand_wall_pos: Vector2 = ray_res.get("pos", next_pos) as Vector2
				var ignore_ladder_lip: bool = false
				if absf(dir.y) > 0.15 and ml.get("ladder_rects") != null:
					for lr_v: Variant in ml.get("ladder_rects") as Array:
						var lr: Rect2 = lr_v as Rect2
						if cand_wall_pos.x >= lr.position.x - 4.0 and cand_wall_pos.x <= lr.end.x + 4.0 and cand_wall_pos.y >= lr.position.y - 6.0 and cand_wall_pos.y <= lr.end.y - 6.0:
							ignore_ladder_lip = true
							break
				if not ignore_ladder_lip:
					hit_wall = true
					wall_hit_pos = cand_wall_pos

		# 4. Props collision & Overkill Penetration (ProjectilesUpdater.as:601-621 + Damage Attenuation)
		var owner_f: Node2D = b.get("owner", null) as Node2D
		var deflected: bool = bool(b.get("deflected", false))
		var rider_f: Node2D = b.get("rider", null) as Node2D
		var earliest_non_prop_t: float = INF
		if not throwables.is_empty():
			for th_entry_chk: Dictionary in throwables:
				var th_pos_chk: Vector2 = th_entry_chk.get("pos", Vector2.ZERO) as Vector2
				var th_rect_chk: Rect2 = Rect2(th_pos_chk.x - 5.0, th_pos_chk.y - 5.0, 10.0, 10.0)
				var th_t: float = _segment_rect_entry_t(prev_pos, wall_hit_pos, th_rect_chk)
				if th_t <= 1.0 and th_t < earliest_non_prop_t:
					earliest_non_prop_t = th_t
		for f_chk_var: Variant in fighters:
			if not is_instance_valid(f_chk_var):
				continue
			var f_chk: Node2D = f_chk_var as Node2D
			if f_chk == owner_f and not deflected:
				continue
			if f_chk == rider_f:
				continue
			if bool(f_chk.get("is_dead")):
				if is_rocket and not bool(f_chk.get("is_gibbed")):
					var dead_rect_chk: Rect2 = Rect2(f_chk.global_position.x - 7.0, f_chk.global_position.y - 10.0, 14.0, 10.0)
					var dt_chk: float = _segment_rect_entry_t(prev_pos, wall_hit_pos, dead_rect_chk)
					if dt_chk <= 1.0 and dt_chk < earliest_non_prop_t:
						earliest_non_prop_t = dt_chk
				continue
			var f_rect_chk: Rect2 = f_chk.call("get_hit_rect") as Rect2 if f_chk.has_method("get_hit_rect") else Rect2(f_chk.global_position.x - 6.0, f_chk.global_position.y - 18.0, 12.0, 18.0)
			var ft_chk: float = _segment_rect_entry_t(prev_pos, wall_hit_pos, f_rect_chk)
			if ft_chk <= 1.0 and ft_chk < earliest_non_prop_t:
				earliest_non_prop_t = ft_chk

		var hit_prop: Node2D = null
		var prop_hit_pos: Vector2 = wall_hit_pos
		var stopped_by_prop: bool = false
		var pen_ids: Array = b.get("penetrated_prop_ids", []) as Array
		var is_first_step: bool = (age <= step_24hz + 0.01)
		var origin_pos: Vector2 = b.get("origin_pos", prev_pos) as Vector2
		var prop_hits: Array[Dictionary] = []
		for cp: Dictionary in cached_props:
			var prop: Node2D = cp["node"] as Node2D
			if not is_instance_valid(prop) or bool(prop.get("is_destroyed")):
				continue
			var cp_id: int = int(cp["id"])
			if cp_id == ignore_cover_id or pen_ids.has(cp_id):
				continue
			var is_holder: bool = bool(prop.get("is_hanging_holder"))
			# AS3 ProjectilesUpdater.as:489-500 (CollisionObjectRocket -> DynamicHitBoxObjectList):
			# Rockets only collide directly with props that have DrawHitBox = true (never with CRATE_HANGING_HOLDER)
			if is_rocket and is_holder:
				continue
			var p_rect: Rect2 = cp["rect"] as Rect2
			var ray_start: Vector2 = origin_pos if (is_first_step and is_holder) else prev_pos
			var hit_t: float = _segment_rect_entry_t(ray_start, wall_hit_pos, p_rect)
			if hit_t <= 1.0 and prop.has_method("check_segment_hit_obb"):
				hit_t = float(prop.call("check_segment_hit_obb", ray_start, wall_hit_pos))
			elif is_holder and prop.has_method("check_segment_hit_obb"):
				hit_t = float(prop.call("check_segment_hit_obb", ray_start, wall_hit_pos))

			# Aim-Down Chain Assist (Screenshot 1): if the shooter is standing on top of the attached CRATE_HANGING
			# and firing downward (dir.y > 0.18), ensure the bullet connects with CRATE_HANGING_HOLDER before the crate!
			if hit_t > 1.0 and is_first_step and is_holder and is_instance_valid(owner_f) and dir.y > 0.18:
				var att_crate: Node2D = prop.get("attached_hanging_crate") as Node2D
				if is_instance_valid(att_crate) and not bool(att_crate.get("is_hanging_released")):
					var cw: float = float(att_crate.get("width")) if att_crate.get("width") != null else 28.0
					var ch: float = float(att_crate.get("height")) if att_crate.get("height") != null else 16.0
					var crate_top: float = att_crate.global_position.y - ch * 0.5
					if absf(owner_f.global_position.y - crate_top) <= 4.5 and absf(owner_f.global_position.x - att_crate.global_position.x) <= cw * 0.5 + 4.5:
						var dx_holder: float = prop.global_position.x - owner_f.global_position.x
						if absf(dx_holder) <= 13.5 and (absf(dir.x) <= 0.72 or dx_holder * dir.x >= -3.0):
							hit_t = 0.0

			if hit_t <= 1.0:
				if is_flame:
					# Flamethrower stream penetrates and ignites props
					if prop.has_method("ignite"):
						prop.call("ignite")
					if prop.has_method("take_damage"):
						prop.call("take_damage", 1.2 * step_24hz, dir * 0.5)
					continue
				prop_hits.append({
					"prop": prop,
					"id": cp_id,
					"t": hit_t,
					"is_holder": is_holder,
					"pos": ray_start.lerp(wall_hit_pos, maxf(0.0, hit_t - 0.02)),
				})

		if prop_hits.size() > 1:
			prop_hits.sort_custom(func(a: Dictionary, b_item: Dictionary) -> bool:
				var a_h: bool = bool(a.get("is_holder", false))
				var b_h: bool = bool(b_item.get("is_holder", false))
				if a_h != b_h and absf(float(a["t"]) - float(b_item["t"])) <= 0.45:
					return a_h
				return float(a["t"]) < float(b_item["t"])
			)

		for ph: Dictionary in prop_hits:
			var ph_t: float = float(ph["t"])
			if ph_t > earliest_non_prop_t:
				break
			var p_node: Node2D = ph["prop"] as Node2D
			var p_pos: Vector2 = ph["pos"] as Vector2
			var p_id: int = int(ph["id"])
			if not is_instance_valid(p_node) or bool(p_node.get("is_destroyed")):
				continue
			if is_rocket:
				hit_prop = p_node
				prop_hit_pos = p_pos
				break
			var hp_before: float = maxf(0.0, float(p_node.get("hp"))) if p_node.get("hp") != null else 25.0
			var max_hp_p: float = maxf(1.0, float(p_node.get("max_hp"))) if p_node.get("max_hp") != null else maxf(1.0, hp_before)
			var b_res: float = maxf(0.05, float(p_node.get("bullet_resistance"))) if p_node.get("bullet_resistance") != null else 1.0
			var p_strength: int = int(p_node.get("prop_strength")) if p_node.get("prop_strength") != null else 10
			var p_indestructible: bool = bool(p_node.get("indestructible"))
			var p_type_u: String = str(p_node.get("prop_type")).to_upper()
			var p_explosive: bool = p_type_u in ["BARREL_EXPLOSIVE", "GASCAN"]
			var cur_dmg: float = float(b.get("damage", 10.0))
			var cur_pb: float = float(b.get("pushback", 15.0))
			var cur_str_left: int = int(b.get("strength_left", 5))
			var prop_dir_x: int = 1 if dir.x >= 0.0 else -1

			if p_node.has_method("apply_bullet_hit"):
				p_node.call("apply_bullet_hit", cur_dmg, cur_pb, prop_dir_x, p_pos, cur_str_left)
			elif p_node.has_method("apply_damage"):
				p_node.call("apply_damage", cur_dmg, vel_vec)
			if is_flare:
				if p_node.has_method("ignite"):
					p_node.call("ignite")
				if fhs != null and fhs.has_method("trigger_fire_burst"):
					fhs.call("trigger_fire_burst", "FLARE", p_pos, 10)
			if fhs != null and fhs.has_method("spawn_hit_sparks"):
				fhs.call("spawn_hit_sparks", p_pos, false)
			_play_sfx("bullet_hit", p_pos)

			# Overkill Penetration: if the bullet shattered the destructible prop with remaining caliber strength or overkill damage,
			# attenuate the bullet's damage & pushback by the energy absorbed by the prop and let the bullet penetrate through!
			var prop_destroyed_now: bool = bool(p_node.get("is_destroyed"))
			var penetrated: bool = false
			if prop_destroyed_now and not p_indestructible and not is_flare and not p_explosive and str(p_node.get("prop_type")).to_upper() != "BARREL_WRECK":
				if p_strength <= cur_str_left:
					var next_str: int = cur_str_left - p_strength
					var dmg_absorbed: float = clampf(float(p_strength) * (hp_before / max_hp_p) * 0.85, 1.5, cur_dmg * 0.60)
					var rem_dmg: float = maxf(2.0, cur_dmg - dmg_absorbed)
					if next_str > 0 and rem_dmg >= 1.5:
						penetrated = true
						b["strength_left"] = next_str
						b["damage"] = rem_dmg
						b["pushback"] = cur_pb * clampf(rem_dmg / maxf(1.0, cur_dmg), 0.35, 0.90)
				else:
					var dmg_needed: float = hp_before / maxf(0.1, b_res)
					if cur_dmg > dmg_needed + 1.0:
						var rem_dmg2: float = maxf(1.5, (cur_dmg - dmg_needed) * 0.85)
						penetrated = true
						b["strength_left"] = maxi(1, cur_str_left - p_strength)
						b["damage"] = rem_dmg2
						b["pushback"] = cur_pb * clampf(rem_dmg2 / maxf(1.0, cur_dmg), 0.25, 0.85)
			if penetrated:
				if not pen_ids.has(p_id):
					pen_ids.append(p_id)
				b["penetrated_prop_ids"] = pen_ids
				continue
			else:
				hit_prop = p_node
				prop_hit_pos = p_pos
				stopped_by_prop = true
				break

		# 4b. Active throwables collision (ProjectilesUpdater.as:597-623: shooting a grenade/molotov/mine/C4 detonates it immediately!)
		var hit_throwable_idx: int = -1
		var throwable_hit_pos: Vector2 = prop_hit_pos
		if not throwables.is_empty():
			for th_i: int in range(throwables.size()):
				var th_entry: Dictionary = throwables[th_i]
				var th_pos: Vector2 = th_entry.get("pos", Vector2.ZERO) as Vector2
				var th_rect: Rect2 = Rect2(th_pos.x - 5.0, th_pos.y - 5.0, 10.0, 10.0)
				if _segment_intersects_rect(prev_pos, prop_hit_pos, th_rect):
					hit_throwable_idx = th_i
					throwable_hit_pos = th_pos
					break
		if hit_throwable_idx >= 0 and hit_throwable_idx < throwables.size():
			var hit_th: Dictionary = throwables[hit_throwable_idx]
			throwables.remove_at(hit_throwable_idx)
			_detonate_throwable_entry(hit_th, fhs)
			if is_rocket:
				_detonate_rocket(b, throwable_hit_pos, fhs)
			else:
				if fhs != null and fhs.has_method("spawn_hit_sparks"):
					fhs.call("spawn_hit_sparks", throwable_hit_pos, false)
				_play_sfx("bullet_hit", throwable_hit_pos)
			continue

		# 5. Fighters collision
		var hit_fighter: Node2D = null
		var fighter_hit_pos: Vector2 = prop_hit_pos

		for f_var: Variant in fighters:
			if not is_instance_valid(f_var):
				continue
			var f: Node2D = f_var as Node2D
			if f == owner_f and not deflected:
				continue
			if f == rider_f:
				continue
			if bool(f.get("is_dead")):
				if is_rocket and not bool(f.get("is_gibbed")):
					var dead_rect: Rect2 = Rect2(f.global_position.x - 7.0, f.global_position.y - 10.0, 14.0, 10.0)
					if _segment_intersects_rect(prev_pos, prop_hit_pos, dead_rect):
						if f.has_method("gib_fighter"):
							f.call("gib_fighter", dir * 5.5)
						hit_fighter = f
						fighter_hit_pos = prev_pos.lerp(prop_hit_pos, 0.5)
						break
				continue
			var f_rect: Rect2 = Rect2(f.global_position.x - 6.0, f.global_position.y - 18.0, 12.0, 18.0)
			if f.has_method("get_hit_rect"):
				f_rect = f.call("get_hit_rect") as Rect2
			if _segment_intersects_rect(prev_pos, prop_hit_pos, f_rect):
				var candidate_hit_pos: Vector2 = prev_pos.lerp(prop_hit_pos, 0.5)
				var dir_x: int = 1 if dir.x >= 0.0 else -1
				if is_flame:
					# Flamethrower stream penetrates fighters and adds burn_state += 18
					if f.has_method("add_burn"):
						f.call("add_burn", 18.0 * step_24hz, false)
					elif f.get("burn_state") != null:
						var nb: float = clampf(float(f.get("burn_state")) + 18.0 * step_24hz, 0.0, 100.0)
						f.set("burn_state", nb)
						if nb >= 100.0:
							f.set("burned", true)
					if f.get("hp") != null:
						var nhp: float = maxf(0.0, float(f.get("hp")) - 1.2 * step_24hz)
						f.set("hp", nhp)
						if nhp <= 0.0:
							f.set("is_dead", true)
					continue
				elif is_rocket and rider_f == null:
					# Check rocket dodge (50% during Roll/Dive); if not dodged, start Rocket Riding!
					var rocket_took: bool = true
					if f.has_method("check_projectile_dodge"):
						rocket_took = not bool(f.call("check_projectile_dodge", true))
					if rocket_took:
						b["rider"] = f
						rider_f = f
						# Snap rocket to fighter attachment point on the capture tick so the rider visibly rides the rocket
						next_pos = candidate_hit_pos
						hit_wall = false
						hit_prop = null
						f.global_position = next_pos + Vector2(0.0, 9.0)
						if f.has_method("start_rocket_ride"):
							f.call("start_rocket_ride", dir_x)
						if f.has_method("update_rocket_ride_pose"):
							f.call("update_rocket_ride_pose", angle_deg, dir * spd)
						_play_sfx("dive_catch", candidate_hit_pos)
						break
				elif is_rocket and is_instance_valid(rider_f):
					# AS3 ProjectilesUpdater.as:906-912: Rocket already carrying a rider hits a 2nd fighter -> gibs both and detonates!
					if f.has_method("gib_fighter"):
						f.call("gib_fighter", dir * 6.0)
					hit_fighter = f
					fighter_hit_pos = candidate_hit_pos
					break
				else:
					var took_hit: bool = true
					if f.has_method("apply_bullet_hit"):
						took_hit = bool(f.call(
							"apply_bullet_hit",
							float(b.get("damage", 10.0)),
							float(b.get("pushback", 15.0)),
							dir_x,
							bool(b.get("is_crit", false)),
							candidate_hit_pos,
							is_rocket
						))
					if took_hit:
						hit_fighter = f
						fighter_hit_pos = candidate_hit_pos
						break

		if hit_fighter != null:
			if is_rocket:
				_detonate_rocket(b, fighter_hit_pos, fhs)
			else:
				if is_flare:
					if hit_fighter.has_method("add_burn"):
						hit_fighter.call("add_burn", 100.0, true)
					if fhs != null and fhs.has_method("trigger_fire_burst"):
						fhs.call("trigger_fire_burst", "FLARE", fighter_hit_pos, 10)
				if fhs != null and fhs.has_method("spawn_hit_sparks"):
					fhs.call("spawn_hit_sparks", fighter_hit_pos, true)
			continue

		if hit_prop != null:
			if is_rocket:
				if bool(hit_prop.get("is_hanging_crate")) and not bool(hit_prop.get("is_hanging_released")) and hit_prop.has_method("apply_pendulum_impulse"):
					var r_dir_x: float = 1.0 if dir.x >= -0.01 else -1.0
					hit_prop.call("apply_pendulum_impulse", r_dir_x * 0.16)
				_detonate_rocket(b, prop_hit_pos, fhs)
			elif stopped_by_prop:
				pass
			continue

		if hit_wall:
			if is_rocket:
				_detonate_rocket(b, wall_hit_pos, fhs)
			elif is_flame:
				if fhs != null and fhs.has_method("spawn_ground_flame"):
					fhs.call("spawn_ground_flame", wall_hit_pos, 65.0)
			else:
				if is_flare and fhs != null and fhs.has_method("trigger_fire_burst"):
					fhs.call("trigger_fire_burst", "FLARE", wall_hit_pos, 10)
				elif fhs != null and fhs.has_method("spawn_hit_sparks"):
					fhs.call("spawn_hit_sparks", wall_hit_pos, false)
				_play_sfx("bullet_hit", wall_hit_pos)
			continue

		# Carry rocket rider if attached (body_pivot is at (0, -9), so +9 places body_pivot right on the rocket center)
		if is_rocket and is_instance_valid(rider_f):
			rider_f.global_position = next_pos + Vector2(0.0, 9.0)
			if rider_f.has_method("update_rocket_ride_pose"):
				rider_f.call("update_rocket_ride_pose", angle_deg, dir * spd)
			elif rider_f.get("air_velocity") != null:
				rider_f.set("air_velocity", dir * spd * 0.5)

		var traveled: float = float(b.get("traveled", 0.0)) + step_dist
		if traveled >= float(b.get("max_range", 1200.0)) or _is_outside_world(next_pos, ml):
			if is_rocket and is_instance_valid(rider_f):
				if rider_f.has_method("end_rocket_ride"):
					rider_f.call("end_rocket_ride")
				if rider_f.has_method("gib_fighter"):
					rider_f.call("gib_fighter", Vector2(dir.x * 5.0, -4.5))
			continue

		b["prev_pos"] = prev_pos
		b["pos"] = next_pos
		b["traveled"] = traveled
		next_bullets.append(b)

	bullets = next_bullets


func _is_outside_world(pt: Vector2, ml: Object) -> bool:
	if ml != null and ml.get("map_bounds") != null:
		var mb: Rect2 = ml.get("map_bounds") as Rect2
		if mb.size.x > 10.0 and mb.size.y > 10.0:
			return not mb.grow(48.0).has_point(pt)
	return pt.x < -800.0 or pt.x > 1200.0 or pt.y < -600.0 or pt.y > 800.0


func _detonate_rocket(b: Dictionary, pos: Vector2, fhs: Object) -> void:
	var dir_vec: Vector2 = (b.get("dir", Vector2.RIGHT) as Vector2).normalized()
	var explode_pos: Vector2 = pos - dir_vec * 3.0
	var rider_f: Node2D = b.get("rider", null) as Node2D
	if is_instance_valid(rider_f):
		if rider_f.has_method("end_rocket_ride"):
			rider_f.call("end_rocket_ride")
		# AS3 ProjectilesUpdater.as:946-951: Rocket rider impacting wall/ground/prop is ALWAYS gibbed (banh xác)!
		if rider_f.has_method("gib_fighter"):
			rider_f.call("gib_fighter", Vector2(dir_vec.x * 5.0, -4.5))
	var owner_f: Node2D = b.get("owner", null) as Node2D
	if fhs != null and fhs.has_method("trigger_explosion"):
		# AS3 ProjectilesUpdater.as:971 & Explosions.as:17-86: authentic blast radius=33.0, player_damage=20.0, player_power=5.0
		fhs.call("trigger_explosion", explode_pos, 33.0, 20.0, 5.0, owner_f)


func _detonate_throwable_entry(th: Dictionary, fhs: Object = null) -> void:
	var fhs_ref: Object = fhs if fhs != null else _get_fire_hazard_system()
	var wid: String = str(th.get("weapon_id", "GRENADE")).to_upper()
	var pos: Vector2 = th.get("pos", Vector2.ZERO) as Vector2
	var owner_f: Node2D = th.get("owner", null) as Node2D
	if wid == "MOLOTOV":
		_play_sfx("glass", pos)
		if fhs_ref != null and fhs_ref.has_method("trigger_fire_burst"):
			fhs_ref.call("trigger_fire_burst", "MOLOTOV", pos, 22)
	else:
		if fhs_ref != null and fhs_ref.has_method("trigger_explosion"):
			fhs_ref.call("trigger_explosion", pos, 33.0, 20.0, 5.0, owner_f)


func detonate_throwables_in_radius(center: Vector2, radius: float) -> int:
	if throwables.is_empty():
		return 0
	var fhs: Object = _get_fire_hazard_system()
	var to_detonate: Array[Dictionary] = []
	var remaining: Array[Dictionary] = []
	for th: Dictionary in throwables:
		var tpos: Vector2 = th.get("pos", Vector2.ZERO) as Vector2
		var dist_t: float = center.distance_to(tpos)
		var blocked_t: bool = false
		if dist_t <= radius and dist_t > 0.5 and fhs != null and fhs.has_method("is_explosion_line_blocked"):
			blocked_t = bool(fhs.call("is_explosion_line_blocked", center, tpos, null))
		if dist_t <= radius and dist_t > 0.5 and not blocked_t:
			to_detonate.append(th)
		else:
			remaining.append(th)
	throwables = remaining
	for th_det: Dictionary in to_detonate:
		_detonate_throwable_entry(th_det, fhs)
	return to_detonate.size()


func _ray_vs_expanded_rect(from_pt: Vector2, to_pt: Vector2, exp_rect: Rect2) -> Dictionary:
	# If starting point is already inside exp_rect (e.g. a prop slid into a resting grenade or close-range throw),
	# push out to the nearest face of exp_rect so the grenade never phases through the prop!
	if exp_rect.has_point(from_pt):
		var d_left: float = absf(from_pt.x - exp_rect.position.x)
		var d_right: float = absf(exp_rect.end.x - from_pt.x)
		var d_top: float = absf(from_pt.y - exp_rect.position.y)
		var d_bot: float = absf(exp_rect.end.y - from_pt.y)
		var min_d: float = minf(minf(d_left, d_right), minf(d_top, d_bot))
		var out_pos: Vector2 = from_pt
		var out_n: Vector2 = Vector2.UP
		if is_equal_approx(min_d, d_left):
			out_pos.x = exp_rect.position.x
			out_n = Vector2.LEFT
		elif is_equal_approx(min_d, d_right):
			out_pos.x = exp_rect.end.x
			out_n = Vector2.RIGHT
		elif is_equal_approx(min_d, d_top):
			out_pos.y = exp_rect.position.y
			out_n = Vector2.UP
		else:
			out_pos.y = exp_rect.end.y
			out_n = Vector2.DOWN
		return {"hit": true, "t": 0.0, "pos": out_pos, "normal": out_n}

	var d: Vector2 = to_pt - from_pt
	var t_min: float = -INF
	var t_max: float = INF
	var n_min: Vector2 = Vector2.UP

	if absf(d.x) < 0.00001:
		if from_pt.x < exp_rect.position.x or from_pt.x > exp_rect.end.x:
			return {"hit": false}
	else:
		var inv_dx: float = 1.0 / d.x
		var tx1: float = (exp_rect.position.x - from_pt.x) * inv_dx
		var tx2: float = (exp_rect.end.x - from_pt.x) * inv_dx
		var nx: Vector2 = Vector2.LEFT if d.x > 0.0 else Vector2.RIGHT
		if tx1 > tx2:
			var tmp_x: float = tx1
			tx1 = tx2
			tx2 = tmp_x
		if tx1 > t_min:
			t_min = tx1
			n_min = nx
		t_max = minf(t_max, tx2)
		if t_min > t_max:
			return {"hit": false}

	if absf(d.y) < 0.00001:
		if from_pt.y < exp_rect.position.y or from_pt.y > exp_rect.end.y:
			return {"hit": false}
	else:
		var inv_dy: float = 1.0 / d.y
		var ty1: float = (exp_rect.position.y - from_pt.y) * inv_dy
		var ty2: float = (exp_rect.end.y - from_pt.y) * inv_dy
		var ny: Vector2 = Vector2.UP if d.y > 0.0 else Vector2.DOWN
		if ty1 > ty2:
			var tmp_y: float = ty1
			ty1 = ty2
			ty2 = tmp_y
		if ty1 > t_min:
			t_min = ty1
			n_min = ny
		t_max = minf(t_max, ty2)
		if t_min > t_max:
			return {"hit": false}

	if t_max < 0.0 or t_min > 1.0:
		return {"hit": false}
	var t_hit: float = clampf(t_min, 0.0, 1.0)
	return {
		"hit": true,
		"t": t_hit,
		"pos": from_pt.lerp(to_pt, t_hit),
		"normal": n_min,
	}


func _find_active_ladder_shaft(ml: Object, from_pt: Vector2, to_pt: Vector2, vel: Vector2) -> Rect2:
	if ml == null or absf(vel.y) <= 0.35 or ml.get("ladder_rects") == null:
		return Rect2()
	for lr_v: Variant in ml.get("ladder_rects") as Array:
		var lr: Rect2 = lr_v as Rect2
		var in_x: bool = (from_pt.x >= lr.position.x - 4.0 and from_pt.x <= lr.end.x + 4.0) or (to_pt.x >= lr.position.x - 4.0 and to_pt.x <= lr.end.x + 4.0)
		if not in_x:
			continue
		var min_y: float = minf(from_pt.y, to_pt.y)
		var max_y: float = maxf(from_pt.y, to_pt.y)
		if max_y >= lr.position.y - 14.0 and min_y <= lr.end.y - 4.0:
			return lr
	return Rect2()


func _step_throwables(step_24hz: float) -> void:
	var ml: Object = _get_map_loader()
	var fhs: Object = _get_fire_hazard_system()
	var fighters: Array = _get_fighters()
	var props: Array = _get_props()
	var motion_serial: int = int(ml.get("_elevator_motion_serial")) if ml != null else -1
	var sweep_elevator_motion: bool = motion_serial != _last_elevator_motion_serial
	_last_elevator_motion_serial = motion_serial

	var next_throwables: Array[Dictionary] = []
	for th: Dictionary in throwables:
		var wid: String = str(th.get("weapon_id", "GRENADE")).to_upper()
		var pos: Vector2 = th.get("pos", Vector2.ZERO) as Vector2
		var sweep_from: Vector2 = th.get("_elevator_pre_carry_pos", pos) as Vector2
		var carried_elevator: int = int(th.get("_elevator_carried_index", -1)) if th.has("_elevator_pre_carry_pos") else -1
		th.erase("_elevator_pre_carry_pos")
		th.erase("_elevator_carried_index")
		var vel: Vector2 = th.get("vel", Vector2.ZERO) as Vector2
		var fuse: float = float(th.get("fuse_frames", 72.0)) - step_24hz
		var age: float = float(th.get("age", 0.0)) + step_24hz
		var owner_f: Node2D = th.get("owner", null) as Node2D
		var ignore_cid: int = int(th.get("ignore_cover_id", -1))

		if carried_elevator >= 0:
			# MapLoader already supplied this tick's lift displacement. A resting
			# grenade must not accumulate a second vertical motion into its lift.
			vel.y = 0.0
			th["settled"] = absf(vel.x) < 0.05
		else:
			vel.y += THROWABLE_GRAVITY_24HZ * step_24hz
			if wid == "GRENADE":
				th["settled"] = false
		var next_pos: Vector2 = pos + vel * step_24hz

		# Molotov in flight drops tiny fire sparks / smoke along its trajectory
		if wid == "MOLOTOV" and fhs != null:
			var sp_acc: float = float(th.get("spark_accum", 0.0)) + step_24hz
			if sp_acc >= 2.0:
				sp_acc = 0.0
				if fhs.has_method("spawn_smoke_puff"):
					fhs.call("spawn_smoke_puff", pos + Vector2(0.0, -3.0), Vector2(randf_range(-0.2, 0.2), -0.35), 0.5)
			th["spark_accum"] = sp_acc

		if ml != null and ml.has_method("check_and_break_glass_segment"):
			ml.call("check_and_break_glass_segment", sweep_from, next_pos, vel)

		# 0. Portal Doorways: allow thrown bombs (GRENADE, MOLOTOV, C4, MINE) to traverse portals (top <-> bottom)
		var portal_cd: float = maxf(0.0, float(th.get("portal_cd", 0.0)) - step_24hz)
		th["portal_cd"] = portal_cd
		if ml != null and portal_cd <= 0.0 and not bool(th.get("settled", false)) and ml.has_method("try_teleport_ballistic_segment"):
			var tp_th: Dictionary = ml.call("try_teleport_ballistic_segment", sweep_from, next_pos, vel, 2.5) as Dictionary
			if bool(tp_th.get("teleported", false)):
				vel = tp_th.get("vel", vel) as Vector2
				if bool(tp_th.get("flip_x", false)):
					th["rot_vel"] = -float(th.get("rot_vel", 0.25))
					th["shaft_exit_vx"] = -float(th.get("shaft_exit_vx", vel.x))
				var exit_pt: Vector2 = tp_th.get("exit_origin", next_pos) as Vector2
				var rem_t: float = float(tp_th.get("remaining_ratio", 0.5))
				sweep_from = exit_pt
				pos = exit_pt
				next_pos = exit_pt + vel * (step_24hz * rem_t)
				th["pos"] = pos
				th["vel"] = vel
				th["portal_cd"] = 4.0

		# 0b. Ladder Hatch / Shaft Channeling (top -> bottom and bottom -> top)
		var active_shaft: Rect2 = _find_active_ladder_shaft(ml, sweep_from, next_pos, vel)
		if active_shaft.size.x > 0.0:
			if absf(vel.x) > 0.05:
				if not th.has("shaft_exit_vx") or absf(float(th.get("shaft_exit_vx", 0.0))) < 0.2:
					th["shaft_exit_vx"] = signf(vel.x) * maxf(1.5, absf(vel.x))
				if vel.y > 0.35 or (vel.y < -0.35 and next_pos.y > active_shaft.position.y - 2.0):
					next_pos.x = clampf(next_pos.x, active_shaft.position.x + 1.5, active_shaft.end.x - 1.5)
					vel.x *= 0.65
			if vel.y < 0.0 and next_pos.y <= active_shaft.position.y - 2.0 and not bool(th.get("_shaft_top_cleared", false)):
				th["_shaft_top_cleared"] = true
				vel.x = float(th.get("shaft_exit_vx", 1.6))

		var hit_surface: bool = false
		var surface_pos: Vector2 = next_pos
		var surface_normal: Vector2 = Vector2.UP
		var best_hit_dist: float = INF
		var hit_prop: Node2D = null
		var surface_remainder: Vector2 = Vector2.ZERO
		var moving_one_way: bool = false
		var blocked_carry: bool = false

		# 1. Static world geometry raycast (walls, floors, ceilings, slopes)
		if ml != null and ml.has_method("raycast_solid"):
			var r_hit: Dictionary = ml.call("raycast_solid", sweep_from, next_pos, -1, false, false) as Dictionary
			if bool(r_hit.get("hit", false)):
				var cand_spos: Vector2 = r_hit.get("pos", next_pos) as Vector2
				var skip_shaft_wall: bool = (active_shaft.size.x > 0.0 and cand_spos.y < active_shaft.end.y - 6.0 and cand_spos.x >= active_shaft.position.x - 4.5 and cand_spos.x <= active_shaft.end.x + 4.5)
				if not skip_shaft_wall:
					hit_surface = true
					surface_pos = cand_spos
					surface_normal = r_hit.get("normal", Vector2.UP) as Vector2
					best_hit_dist = sweep_from.distance_to(surface_pos)
		elif sweep_from.y <= default_floor_y and next_pos.y >= default_floor_y and next_pos.y > sweep_from.y:
			hit_surface = true
			var floor_t: float = (default_floor_y - sweep_from.y) / (next_pos.y - sweep_from.y)
			surface_pos = sweep_from.lerp(next_pos, floor_t)
			surface_normal = Vector2.UP
			best_hit_dist = sweep_from.distance_to(surface_pos)

		# 2. Sweep the top surfaces of flat/tilted CLOUD platforms and lifts.
		# Ladder rectangles are sensors and never participate in these queries.
		if ml != null and ml.has_method("raycast_one_way"):
			var c_hit: Dictionary = ml.call("raycast_one_way", sweep_from, next_pos, carried_elevator, sweep_elevator_motion) as Dictionary
			if bool(c_hit.get("hit", false)):
				var c_pos: Vector2 = c_hit.get("pos", next_pos) as Vector2
				var skip_shaft_cloud: bool = (active_shaft.size.x > 0.0 and c_pos.y < active_shaft.end.y - 6.0 and c_pos.x >= active_shaft.position.x - 4.5 and c_pos.x <= active_shaft.end.x + 4.5)
				var c_dist: float = sweep_from.distance_to(c_pos)
				if not skip_shaft_cloud and c_dist < best_hit_dist:
					hit_surface = true
					surface_pos = c_pos
					surface_normal = c_hit.get("normal", Vector2.UP) as Vector2
					best_hit_dist = c_dist
					hit_prop = null
					surface_remainder = c_hit.get("surface_remainder", Vector2.ZERO) as Vector2
					moving_one_way = bool(c_hit.get("moving_one_way", false))

		# 3. Solid interactive props (AS3 MapPremadeItems.as:595,626 & b2FilterData.as:21-22: maskBits=65535 -> collides with all solid props!)
		for p_var: Variant in props:
			if not is_instance_valid(p_var):
				continue
			var prop: Node2D = p_var as Node2D
			if bool(prop.get("is_destroyed")) or bool(prop.get("is_hanging_holder")) or not bool(prop.get("has_solid_hitbox")):
				continue
			var pid: int = int(prop.get("prop_id")) if prop.get("prop_id") != null else prop.get_instance_id()
			# AS3 b2ContactFilter.as:83-102: ignore the cover object that the thrower is actively taking cover behind
			if ignore_cid != -1 and (pid == ignore_cid or prop.get_instance_id() == ignore_cid):
				continue
			var p_rect: Rect2 = prop.call("get_solid_support_rect") as Rect2 if prop.has_method("get_solid_support_rect") else (prop.call("get_world_rect") as Rect2 if prop.has_method("get_world_rect") else Rect2())
			if p_rect.size.x <= 0.0 or p_rect.size.y <= 0.0:
				continue
			# Expand prop hitbox by 1.8px to account for the 5x5px octagon body of GRENADE_THROWN / MOLOTOV_THROWN
			var exp_rect: Rect2 = p_rect.grow(1.8)
			var p_hit: Dictionary = _ray_vs_expanded_rect(sweep_from, next_pos, exp_rect)
			if bool(p_hit.get("hit", false)):
				var cand_pos: Vector2 = p_hit.get("pos", next_pos) as Vector2
				var cand_dist: float = sweep_from.distance_to(cand_pos)
				if cand_dist < best_hit_dist:
					hit_surface = true
					surface_pos = cand_pos
					surface_normal = p_hit.get("normal", Vector2.UP) as Vector2
					best_hit_dist = cand_dist
					hit_prop = prop
					surface_remainder = Vector2.ZERO
					moving_one_way = false

		# A moving lift can continue carrying an impact point after the first
		# contact. Sweep that remainder as well, so it cannot pass a low ceiling
		# or solid prop that lies beyond the first contact along this tick.
		if hit_surface and wid != "MOLOTOV" and surface_remainder.length_squared() > 0.000001:
			var carried_start: Vector2 = surface_pos + surface_normal * 0.5
			var blocker: Dictionary = _throwable_carry_blocker(carried_start, carried_start + surface_remainder, ml, props, ignore_cid)
			if bool(blocker.get("hit", false)):
				surface_pos = blocker["pos"] as Vector2
				surface_normal = blocker.get("normal", Vector2.UP) as Vector2
				hit_prop = blocker.get("prop", null) as Node2D
				surface_remainder = Vector2.ZERO
				moving_one_way = false
				blocked_carry = true

		# Check direct contact with enemy fighters for MOLOTOV or proximity MINE
		var touched_fighter: bool = false
		for f_var: Variant in fighters:
			if not is_instance_valid(f_var):
				continue
			var f: Node2D = f_var as Node2D
			if f == owner_f and age < 8.0:
				continue
			if bool(f.get("is_dead")):
				continue
			var f_rect: Rect2 = Rect2(f.global_position.x - 6.0, f.global_position.y - 18.0, 12.0, 18.0)
			if f.has_method("get_hit_rect"):
				f_rect = f.call("get_hit_rect") as Rect2
			if f_rect.grow(2.0).has_point(next_pos):
				touched_fighter = true
				break

		if wid == "MOLOTOV":
			if hit_surface or touched_fighter or fuse <= 0.0:
				_play_sfx("glass", surface_pos)
				if hit_prop != null and is_instance_valid(hit_prop) and hit_prop.has_method("ignite"):
					hit_prop.call("ignite")
				if fhs != null and fhs.has_method("trigger_fire_burst"):
					fhs.call("trigger_fire_burst", "MOLOTOV", surface_pos, 22)
				continue
		elif wid == "GRENADE" or wid == "C4" or wid == "MINE":
			if hit_surface:
				if surface_normal.length_squared() < 0.01:
					surface_normal = Vector2.UP
				else:
					surface_normal = surface_normal.normalized()
				if carried_elevator < 0 and not moving_one_way and not blocked_carry and surface_normal.dot(vel) > 0.0 and vel.length_squared() > 0.04:
					surface_normal = -surface_normal
				next_pos = surface_pos + surface_remainder + surface_normal * 0.5

				# Transfer physical impact impulse to movable dynamic props when hit by a fast-moving grenade (b2ContactListener.as:50-114)
				var prop_vel: Vector2 = Vector2.ZERO
				if hit_prop != null and is_instance_valid(hit_prop):
					if hit_prop.get("velocity") != null:
						prop_vel = hit_prop.get("velocity") as Vector2
					var rel_vel: Vector2 = vel - prop_vel
					if rel_vel.length() >= 2.0:
						if bool(hit_prop.get("is_hanging_crate")) and not bool(hit_prop.get("is_hanging_released")) and hit_prop.has_method("apply_pendulum_impulse"):
							hit_prop.call("apply_pendulum_impulse", clampf(vel.x * 0.012, -0.09, 0.09))
						elif not bool(hit_prop.get("kinematic")) and hit_prop.get("velocity") != null:
							var pmass: float = maxf(0.5, float(hit_prop.get("mass")) if hit_prop.get("mass") != null else 1.0)
							if pmass <= 2.5:
								var n_imp: Vector2 = Vector2(clampf(vel.x * (0.20 / pmass), -1.4, 1.4), 0.0)
								hit_prop.set("velocity", prop_vel + n_imp)
						if rel_vel.length() >= 3.0 and fhs != null and fhs.has_method("spawn_hit_sparks"):
							fhs.call("spawn_hit_sparks", surface_pos, false)

				if wid == "C4" or wid == "MINE":
					vel = Vector2.ZERO
					th["settled"] = true
					th["rot_vel"] = 0.0
				else:
					var n: Vector2 = surface_normal
					var vn: float = vel.dot(n)
					var vt: Vector2 = vel - n * vn
					if absf(n.x) > 0.5:
						# Bounce horizontally off vertical walls or prop sides
						if vn < 0.0:
							vel = vt * 0.82 + n * maxf(-vn * 0.42, 0.85)
						else:
							vel.x = n.x * maxf(absf(vel.x) * 0.42, 0.85)
						th["rot_vel"] = -float(th.get("rot_vel", 0.25)) * 0.65
						th["settled"] = false
					elif n.y > 0.5:
						# Bounce downward off ceilings or underside of hanging crates
						if vn < 0.0:
							vel = vt * 0.85 + n * maxf(-vn * 0.38, 0.6)
						else:
							vel.y = maxf(0.6, absf(vel.y) * 0.38)
						th["settled"] = false
					elif vn < 0.0:
						if -vn > 0.65:
							vel = vt * 0.78 - n * (vn * 0.34)
							th["rot_vel"] = clampf(vel.x * 0.16, -0.45, 0.45)
							th["settled"] = false
						else:
							vel = vt
							# Roll down slopes (like stairs) and apply natural rolling friction on floors / prop tops
							if absf(n.x) > 0.05 and n.y < -0.35:
								vel.x += n.x * THROWABLE_GRAVITY_24HZ * step_24hz * 0.85
							vel.x *= pow(0.90, step_24hz)
							if hit_prop != null and absf(vel.x) < 0.08:
								vel.x = prop_vel.x
							if absf(vel.x) < 0.05:
								vel.x = 0.0
								th["rot_vel"] = 0.0
								th["settled"] = true
							else:
								th["rot_vel"] = vel.x * 0.16
			# Safety de-penetration so throwables never sink into floors or stair slope polygons
			if ml != null and ml.has_method("is_point_solid") and bool(ml.call("is_point_solid", next_pos, false)):
				if ml.has_method("get_ground_y_below"):
					var gy_safe: float = float(ml.call("get_ground_y_below", next_pos.x, pos.y - 14.0, 32.0, true))
					if gy_safe < INF:
						next_pos.y = minf(next_pos.y, gy_safe - 0.5)
						if vel.y > 0.0:
							vel.y = 0.0
			if wid == "MINE" and age >= 18.0 and touched_fighter:
				fuse = 0.0
			if fuse <= 0.0:
				if fhs != null and fhs.has_method("trigger_explosion"):
					fhs.call("trigger_explosion", next_pos, 33.0, 20.0, 5.0, owner_f)
				continue

		th["prev_pos"] = sweep_from
		th["pos"] = next_pos
		th["vel"] = vel
		th["fuse_frames"] = fuse
		th["age"] = age
		th["rot"] = float(th.get("rot", 0.0)) + float(th.get("rot_vel", 0.25)) * step_24hz
		next_throwables.append(th)

	throwables = next_throwables


func _throwable_carry_blocker(from_pos: Vector2, to_pos: Vector2, ml: Object, props: Array, ignore_cover_id: int) -> Dictionary:
	var best: Dictionary = {"hit": false}
	var best_distance: float = INF
	if ml != null and ml.has_method("raycast_solid"):
		best = ml.call("raycast_solid", from_pos, to_pos, -1, false, false) as Dictionary
		if bool(best.get("hit", false)):
			best_distance = from_pos.distance_to(best["pos"] as Vector2)
	for value: Variant in props:
		if not is_instance_valid(value):
			continue
		var prop: Node2D = value as Node2D
		if prop.get("is_destroyed") == true or prop.get("is_hanging_holder") == true or prop.get("has_solid_hitbox") != true:
			continue
		var prop_id: int = int(prop.get("prop_id")) if prop.get("prop_id") != null else prop.get_instance_id()
		if ignore_cover_id != -1 and (prop_id == ignore_cover_id or prop.get_instance_id() == ignore_cover_id):
			continue
		var rect: Rect2 = prop.call("get_solid_support_rect") as Rect2 if prop.has_method("get_solid_support_rect") else Rect2()
		if rect.size.x <= 0.0 or rect.size.y <= 0.0:
			continue
		var hit: Dictionary = _ray_vs_expanded_rect(from_pos, to_pos, rect.grow(1.8))
		if bool(hit.get("hit", false)) and from_pos.distance_to(hit["pos"] as Vector2) < best_distance:
			best = hit
			best["prop"] = prop
			best_distance = from_pos.distance_to(hit["pos"] as Vector2)
	return best


func _segment_rect_entry_t(p1: Vector2, p2: Vector2, rect: Rect2) -> float:
	var min_x: float = minf(p1.x, p2.x)
	var max_x: float = maxf(p1.x, p2.x)
	if max_x < rect.position.x or min_x > rect.end.x:
		return INF
	var min_y: float = minf(p1.y, p2.y)
	var max_y: float = maxf(p1.y, p2.y)
	if max_y < rect.position.y or min_y > rect.end.y:
		return INF
	if rect.has_point(p1):
		return 0.0
	var d: Vector2 = p2 - p1
	var t_min: float = 0.0
	var t_max: float = 1.0
	if absf(d.x) < 0.00001:
		if p1.x < rect.position.x or p1.x > rect.end.x:
			return INF
	else:
		var inv_dx: float = 1.0 / d.x
		var tx1: float = (rect.position.x - p1.x) * inv_dx
		var tx2: float = (rect.end.x - p1.x) * inv_dx
		if tx1 > tx2:
			var tmp_x: float = tx1
			tx1 = tx2
			tx2 = tmp_x
		t_min = maxf(t_min, tx1)
		t_max = minf(t_max, tx2)
		if t_min > t_max:
			return INF
	if absf(d.y) < 0.00001:
		if p1.y < rect.position.y or p1.y > rect.end.y:
			return INF
	else:
		var inv_dy: float = 1.0 / d.y
		var ty1: float = (rect.position.y - p1.y) * inv_dy
		var ty2: float = (rect.end.y - p1.y) * inv_dy
		if ty1 > ty2:
			var tmp_y: float = ty1
			ty1 = ty2
			ty2 = tmp_y
		t_min = maxf(t_min, ty1)
		t_max = minf(t_max, ty2)
		if t_min > t_max:
			return INF
	return t_min


func _segment_intersects_rect(p1: Vector2, p2: Vector2, rect: Rect2) -> bool:
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


func clear_all() -> void:
	bullets.clear()
	throwables.clear()
	slomo_rings.clear()
	queue_redraw()


func _draw_centered_tex(tex: Texture2D, pos: Vector2, rot: float = 0.0, scale_vec: Vector2 = Vector2.ONE, modulate_col: Color = Color.WHITE) -> void:
	if tex == null:
		return
	draw_set_transform(pos, rot, scale_vec)
	draw_texture(tex, -tex.get_size() * 0.5, modulate_col)


func _select_brass_bullet_tex(wid: String) -> Texture2D:
	if wid in ["SHOTGUN", "SAWED_OFF"] and _tex_bullet_shotgun != null:
		return _tex_bullet_shotgun
	if wid in ["SNIPER", "LASER_GUN"] and _tex_bullet_sniper != null:
		return _tex_bullet_sniper
	if wid == "MAGNUM" and _tex_bullet_magnum != null:
		return _tex_bullet_magnum
	if wid in ["UZI", "SMG", "TOMMY_GUN"] and _tex_bullet_uzi != null:
		return _tex_bullet_uzi
	if wid in ["RIFLE", "M60"] and _tex_bullet_rifle != null:
		return _tex_bullet_rifle
	if _tex_bullet_pistol != null:
		return _tex_bullet_pistol
	return _tex_bullet_normal


func _draw() -> void:
	_load_projectile_textures()
	var slowmo_now: bool = _is_slowmo_active()

	# 0. Draw Slow-Mo bullet ring trails (bullet_slomo_f01..11)
	if not _tex_bullet_slomo_frames.is_empty():
		var sl_count: int = _tex_bullet_slomo_frames.size()
		for sr: Dictionary in slomo_rings:
			var idx: int = clampi(int(sr.get("frame", 0.0)), 0, sl_count - 1)
			var stex: Texture2D = _tex_bullet_slomo_frames[idx]
			var alpha: float = clampf(1.0 - float(sr.get("frame", 0.0)) / float(sl_count + 1), 0.25, 0.9)
			_draw_centered_tex(
				stex,
				sr.get("pos", Vector2.ZERO) as Vector2,
				float(sr.get("rot", 0.0)),
				Vector2.ONE,
				Color(1.0, 1.0, 1.0, alpha)
			)

	# 1. Draw visible ballistic bullets, rockets, flamethrower stream, flares & MUGEN Chakra Waves
	for b: Dictionary in bullets:
		var pos: Vector2 = b.get("pos", Vector2.ZERO) as Vector2
		var dir: Vector2 = b.get("dir", Vector2.RIGHT) as Vector2
		var rot: float = dir.angle()
		var wid: String = str(b.get("weapon_id", "PISTOL")).to_upper()
		var age: float = float(b.get("age", 0.0))

		if bool(b.get("is_flame", false)):
			if not _tex_flamethrower_frames.is_empty():
				var max_a: float = maxf(1.0, float(b.get("max_age", 12.0)))
				var ratio: float = clampf(age / max_a, 0.0, 0.999)
				var f_idx: int = clampi(int(ratio * float(_tex_flamethrower_frames.size())), 0, _tex_flamethrower_frames.size() - 1)
				var ftex: Texture2D = _tex_flamethrower_frames[f_idx]
				var sc: float = lerpf(0.6, 1.4, ratio)
				_draw_centered_tex(ftex, pos, rot, Vector2(sc, sc), Color(1.0, 1.0, 1.0, clampf(1.15 - ratio * 0.5, 0.35, 1.0)))
		elif bool(b.get("is_rocket", false)):
			if not _tex_fire_small_frames.is_empty():
				var fl_idx: int = int(age * 2.0) % _tex_fire_small_frames.size()
				_draw_centered_tex(_tex_fire_small_frames[fl_idx], pos - dir * 7.0, rot - PI * 0.5, Vector2(0.65, 0.65))
			# In Symbol 708.xml, Layer 1 (Symbol 707) is only the rider body sprite and Layer 2 (Symbol 521..526) is the rocket sprite underneath
			var rtex: Texture2D = _tex_rocket
			if not _tex_rocket_frames.is_empty():
				var r_idx: int = int(age * 1.5) % _tex_rocket_frames.size()
				rtex = _tex_rocket_frames[r_idx]
			if rtex != null:
				_draw_centered_tex(rtex, pos, rot, Vector2.ONE)
			else:
				draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
				draw_line(pos - dir * 5.0, pos + dir * 4.0, Color(0.35, 0.4, 0.35, 1.0), 2.2)
		elif bool(b.get("is_mugen_wave", false)):
			if not _tex_bullet_slomo_frames.is_empty():
				var mw_idx: int = int(age * 1.5) % _tex_bullet_slomo_frames.size()
				_draw_centered_tex(_tex_bullet_slomo_frames[mw_idx], pos, rot, Vector2(1.35, 1.35), Color(0.45, 0.95, 1.0, 0.95))
			draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
			draw_line(pos - dir * 8.0, pos + dir * 2.0, Color(0.55, 0.96, 1.0, 0.92), 2.4)
		elif bool(b.get("is_flare", false)):
			draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
			draw_line(pos - dir * 12.0, pos, Color(1.0, 0.25, 0.08, 0.9), 2.2)
			if not _tex_fire_small_frames.is_empty():
				var flr_idx: int = int(age * 2.0) % _tex_fire_small_frames.size()
				_draw_centered_tex(_tex_fire_small_frames[flr_idx], pos, rot, Vector2(0.65, 0.65), Color(1.0, 0.65, 0.35, 0.98))
		else:
			if slowmo_now:
				var brass_tex: Texture2D = _select_brass_bullet_tex(wid)
				if brass_tex != null:
					_draw_centered_tex(brass_tex, pos, rot, Vector2.ONE)
			else:
				var btex: Texture2D = _tex_bullet_normal
				var sx: float = 1.35
				if wid in ["SHOTGUN", "SAWED_OFF"] and _tex_bullet_shotgun != null:
					btex = _tex_bullet_shotgun
					sx = 1.15
				elif wid in ["SNIPER", "LASER_GUN"] and _tex_bullet_sniper != null:
					btex = _tex_bullet_sniper
					sx = 1.65
				if btex != null:
					_draw_centered_tex(btex, pos - dir * 5.0, rot, Vector2(sx, 1.0))
				else:
					draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
					draw_line(pos - dir * 16.0, pos, Color(1.0, 0.92, 0.38, 0.95), 1.35)

	# 2. Draw thrown grenades, molotovs, C4, mines using authentic weapon sprites
	for th: Dictionary in throwables:
		var pos: Vector2 = th.get("pos", Vector2.ZERO) as Vector2
		var rot: float = float(th.get("rot", 0.0))
		var wid: String = str(th.get("weapon_id", "GRENADE")).to_upper()
		var age: float = float(th.get("age", 0.0))

		if wid == "MOLOTOV":
			if _tex_molotov != null:
				_draw_centered_tex(_tex_molotov, pos, rot, Vector2.ONE)
			else:
				draw_set_transform(pos, rot, Vector2.ONE)
				draw_rect(Rect2(-1.5, -2.5, 3.0, 5.0), Color(0.68, 0.36, 0.12, 0.95), true)
			if not _tex_fire_small_frames.is_empty():
				var m_idx: int = int(age * 1.8) % _tex_fire_small_frames.size()
				var neck_offset: Vector2 = Vector2(0.0, -3.5).rotated(rot)
				_draw_centered_tex(_tex_fire_small_frames[m_idx], pos + neck_offset, 0.0, Vector2(0.55, 0.55))
		elif wid == "MINE":
			draw_set_transform(pos, 0.0, Vector2.ONE)
			draw_rect(Rect2(-2.5, -1.5, 5.0, 2.0), Color(0.28, 0.32, 0.28, 1.0), true)
			if int(age * 0.5) % 2 == 0:
				draw_rect(Rect2(-0.8, -2.2, 1.6, 1.0), Color(1.0, 0.15, 0.15, 0.95), true)
		else:
			if _tex_grenade != null:
				_draw_centered_tex(_tex_grenade, pos, rot, Vector2.ONE)
			else:
				draw_set_transform(pos, rot, Vector2.ONE)
				draw_rect(Rect2(-2.0, -2.5, 4.0, 5.0), Color(0.25, 0.42, 0.22, 1.0), true)

	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)

class_name InteractiveProp
extends Node2D
## Interactive Physics Prop & Hazard Object (SF-M4 / SF-M8).
## Implements destructible crates, 2-phase explosive barrels (BARREL_EXPLOSIVE -> BARREL_WRECK),
## gascans (18-fireball burst), hanging crates with shootable holders, tables/chairs/computers,
## sky-dropped SupplyParachuteCrates, damaged sprite states, and physical bouncing debris.

const MapLoaderScript = preload("res://game/world/map_loader.gd")
const PROP_GRAVITY: float = 0.6
const TERMINAL_VELOCITY_Y: float = 11.0
const PARACHUTE_FALL_SPEED: float = 1.35

const SUPPLY_WEAPON_POOL: Array[String] = [
	"SHOTGUN",
	"BAZOOKA",
	"SNIPER",
	"SWORD",
	"AXE",
	"M60",
	"FLAMETHROWER",
	"GRENADE",
	"MOLOTOV",
	"MEDKIT",
	"SLOMO05",
]

var prop_id: int = 0
var prop_type: String = "CRATE"
var var_name: String = ""

var hp: float = 25.0
var max_hp: float = 25.0
var width: float = 15.0
var height: float = 15.0
var base_width: float = 15.0
var base_height: float = 15.0
var mass: float = 1.2
var prop_material: String = "Wood"

var explosive: bool = false
var ignites: bool = false
var can_burn: bool = true
var bullet_resistance: float = 1.0
var explosion_resistance: float = 1.0
var player_fragile: bool = false
var allow_cover: bool = false
var cover_level: int = 0
var kick_power: float = 1.35
var kick_weight_calculation: bool = true
var ground_friction_24hz: float = 0.70
var kinematic: bool = false
var has_solid_hitbox: bool = false
var kickable: bool = true
var indestructible: bool = false
var prop_strength: int = 10
var can_gibb: bool = false
var can_block_explosions: bool = false
var crush_damage: float = 0.0
var last_attacker: Node2D = null
var _attacker_ignore_frames: float = 0.0

var blast_damage: float = 20.0
var blast_radius: float = 42.0

var velocity: Vector2 = Vector2.ZERO
var angular_velocity: float = 0.0
var _target_rest_rot: float = 0.0
var _ledge_overhang_dir: float = 0.0
var _ledge_fulcrum_x: float = NAN
var _ledge_fulcrum_y: float = INF
var on_ground: bool = false
var is_destroyed: bool = false
var is_sleeping: bool = false
var _sleep_frames: float = 0.0
var _sleep_glass_version: int = 0

var is_burning: bool = false
var burn_timer: float = 0.0
var _fire_heat: float = 0.0
var barrel_phase: int = 0 # 0 = intact BARREL_EXPLOSIVE, 1 = burning BARREL_WRECK, 2 = exploded 2nd time

var is_hanging_crate: bool = false
var is_hanging_holder: bool = false
var is_hanging_released: bool = false
var ceiling_anchor_y: float = 51.0
var holder_prop: Node2D = null
var attached_hanging_crate: Node2D = null
var _had_holder_linked: bool = false
var _hang_anchor: Vector2 = Vector2.ZERO
var _hang_rope_len: float = 0.0
var _hang_angle: float = 0.0
var _hang_ang_vel: float = 0.0
var crushed_fighter_ids: Dictionary = {}
var crushed_prop_ids: Dictionary = {}
var _prop_impact_cooldowns: Dictionary = {}

var is_parachute_crate: bool = false
var parachute_attached: bool = false
var contained_weapon_id: String = ""
var _parachute_sway_time: float = 0.0

var _settling_frames: float = 18.0
var _is_damaged_visual: bool = false
var _damage_visual_stage: int = 0
var _impact_shudder_frames: float = 0.0
var _fire_anim_frame: float = 0.0
var _tex_fire_frames: Array[Texture2D] = []

var match_world: Node2D = null
var map_loader: Node2D = null

var _sprite: Sprite2D = null


func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_ensure_sprite()
	_load_fire_textures()


func _ensure_sprite() -> void:
	if _sprite == null or not is_instance_valid(_sprite):
		_sprite = Sprite2D.new()
		_sprite.name = "PropSprite"
		_sprite.centered = true
		add_child(_sprite)


func _load_fire_textures() -> void:
	if not _tex_fire_frames.is_empty():
		return
	var reg: Node = MapLoaderScript.get_registry()
	for i: int in range(1, 12):
		var p: String = "res://assets/sprites/effects/fire_01_f%02d.png" % i
		var t: Texture2D = reg.call("load_cached_texture", p) as Texture2D
		if t != null:
			_tex_fire_frames.append(t)


func setup_prop(
	p_type: String,
	p_pos: Vector2,
	p_angle: float = 0.0,
	p_var_name: String = "",
	p_id: int = 0
) -> void:
	var reg: Node = MapLoaderScript.get_registry()
	_ensure_sprite()
	_load_fire_textures()

	prop_id = p_id if p_id > 0 else get_instance_id()
	var_name = p_var_name
	prop_type = p_type.to_upper().strip_edges()
	global_position = p_pos
	rotation = p_angle
	velocity = Vector2.ZERO
	angular_velocity = 0.0
	on_ground = false
	is_destroyed = false
	is_burning = false
	burn_timer = 0.0
	_fire_heat = 0.0
	barrel_phase = 0
	is_parachute_crate = false
	parachute_attached = false
	_settling_frames = 18.0
	_is_damaged_visual = false
	_damage_visual_stage = 0
	_impact_shudder_frames = 0.0
	crushed_fighter_ids.clear()
	crushed_prop_ids.clear()
	_prop_impact_cooldowns.clear()

	var def: Dictionary = reg.call("get_premade_item_def", prop_type) as Dictionary
	if def.is_empty():
		def = reg.call("get_premade_item_def", "CRATE") as Dictionary

	hp = float(def.get("hp", 25.0))
	max_hp = hp
	width = float(def.get("w", 15.0))
	height = float(def.get("h", 15.0))
	mass = maxf(0.2, float(def.get("mass", 1.0)))
	prop_material = str(def.get("material", "Wood"))
	explosive = bool(def.get("explosive", false))
	ignites = bool(def.get("ignites", false))
	can_burn = ignites
	bullet_resistance = 1.0
	explosion_resistance = 1.65
	kinematic = bool(def.get("kinematic", false))
	allow_cover = bool(def.get("allow_cover", false))
	cover_level = 0
	indestructible = false
	can_gibb = false
	can_block_explosions = false
	kick_power = 1.35
	kick_weight_calculation = true
	ground_friction_24hz = 0.70

	# AS3 MapPremadeItems.as per-prop mass, kick_power, kick_weight_calculation, friction, durability & flammability calibration:
	if prop_type in ["CRATE", "SUPPLY_CRATE"]:
		width = 15.0
		height = 15.0
		mass = 1.15
		kick_power = 1.35
		kick_weight_calculation = true
		ground_friction_24hz = 0.70
		can_burn = true
		ignites = true
		hp = 40.0
		max_hp = 40.0
		bullet_resistance = 0.8
	elif prop_type == "BARREL":
		width = 11.0
		height = 15.0
		mass = 1.85
		kick_power = 1.15
		kick_weight_calculation = true
		ground_friction_24hz = 0.72
		can_burn = false
		ignites = false
		hp = 140.0
		max_hp = 140.0
		bullet_resistance = 0.35
		prop_material = "Metal"
	elif prop_type == "BARREL_EXPLOSIVE":
		width = 11.0
		height = 15.0
		mass = 1.75
		kick_power = 1.20
		kick_weight_calculation = true
		ground_friction_24hz = 0.72
		can_burn = true
		ignites = true
		hp = 24.0
		max_hp = 24.0
		bullet_resistance = 1.0
		prop_material = "Metal"
	elif prop_type == "GASCAN":
		# AS3 MapPremadeItems.as:1654 & BodyDataExplosiveBarrel: Strength=5, _resistance_bullet=100 (1 bullet detonates immediately!)
		width = 9.0
		height = 11.0
		mass = 1.05
		kick_power = 1.35
		kick_weight_calculation = true
		ground_friction_24hz = 0.72
		can_burn = true
		ignites = true
		hp = 5.0
		max_hp = 5.0
		bullet_resistance = 100.0
		prop_material = "Metal"
	elif prop_type == "TRASHCAN":
		width = 12.0
		height = 14.0
		mass = 1.65
		kick_power = 1.20
		kick_weight_calculation = true
		ground_friction_24hz = 0.70
		can_burn = false
		ignites = false
		hp = 110.0
		max_hp = 110.0
		bullet_resistance = 0.35
		prop_material = "Metal"
	elif prop_type == "TABLE":
		width = 18.0
		height = 10.0
		mass = 1.45
		kick_power = 0.90
		kick_weight_calculation = false
		cover_level = 1
		ground_friction_24hz = 0.66
		can_burn = true
		ignites = true
		hp = 40.0
		max_hp = 40.0
		bullet_resistance = 1.0
	elif prop_type == "TABLE_SMALL":
		width = 13.0
		height = 7.0
		mass = 1.05
		kick_power = 0.95
		kick_weight_calculation = false
		cover_level = 1
		ground_friction_24hz = 0.68
		can_burn = true
		ignites = true
		hp = 40.0
		max_hp = 40.0
		bullet_resistance = 1.0
	elif prop_type in ["CHAIR", "CHAIR_R"]:
		width = 9.0
		height = 12.0
		mass = 0.75
		kick_power = 0.85
		kick_weight_calculation = false
		ground_friction_24hz = 0.68
		can_burn = true
		ignites = true
		hp = 35.0
		max_hp = 35.0
		bullet_resistance = 1.0
	elif prop_type == "COMFY_CHAIR":
		width = 15.0
		height = 17.0
		mass = 1.55
		kick_power = 0.95
		kick_weight_calculation = false
		ground_friction_24hz = 0.65
		can_burn = true
		ignites = true
		hp = 45.0
		max_hp = 45.0
		bullet_resistance = 0.9
	elif prop_type in ["DESK", "DESK_1", "POOL_TABLE"]:
		if prop_type == "POOL_TABLE":
			width = 42.0
			height = 14.0
		elif prop_type == "DESK_1":
			width = 26.0
			height = 14.0
		else:
			width = 27.0
			height = 14.0
		mass = 4.60 if prop_type == "POOL_TABLE" else 3.20
		kick_power = 0.50
		kick_weight_calculation = false
		ground_friction_24hz = 0.58
		can_burn = false
		ignites = false
		can_gibb = true
		hp = 120.0
		max_hp = 120.0
		bullet_resistance = 0.35
	elif prop_type == "CRATE_HANGING":
		# AS3 MapPremadeItems.as:1575-1595: size 28x16 (obj_crate_hanging.png 29x16), BodyData(..., _indestructible = true), CanGibb = true, Kickable = true
		width = 28.0
		height = 16.0
		mass = 3.80
		kick_power = 0.42
		kick_weight_calculation = false
		ground_friction_24hz = 0.58
		can_burn = false
		ignites = false
		indestructible = true
		can_gibb = true
		hp = 400.0
		max_hp = 400.0
		bullet_resistance = 0.0
		contained_weapon_id = ""
	elif prop_type == "FILECAB":
		width = 13.0
		height = 15.0
		mass = 2.25
		kick_power = 0.80
		kick_weight_calculation = false
		ground_friction_24hz = 0.60
		can_burn = false
		ignites = false
		hp = 120.0
		max_hp = 120.0
		bullet_resistance = 0.35
		prop_material = "Metal"
	elif prop_type in ["COMP", "COMP_SCREEN"]:
		width = 11.0 if prop_type == "COMP_SCREEN" else 7.0
		height = 12.0
		mass = 0.95
		kick_power = 1.15
		kick_weight_calculation = true
		ground_friction_24hz = 0.70
		can_burn = true
		ignites = true
		hp = 12.0
		max_hp = 12.0
		bullet_resistance = 1.0
	elif prop_type == "PAPER":
		width = 9.0
		height = 9.0
		mass = 0.45
		kick_power = 1.10
		kick_weight_calculation = true
		ground_friction_24hz = 0.68
		can_burn = true
		ignites = true
		hp = 8.0
		max_hp = 8.0
		bullet_resistance = 100.0
		explosion_resistance = 100.0
	elif prop_type == "STATUE":
		width = 15.0
		height = 19.0
		mass = 4.00
		kick_power = 0.0
		kick_weight_calculation = false
		ground_friction_24hz = 0.50
		can_burn = false
		ignites = false
		indestructible = true
		hp = 400.0
		max_hp = 400.0
		bullet_resistance = 0.0
		explosion_resistance = 0.0
	elif prop_type == "LAMP_1":
		width = 23.0
		height = 7.0
		mass = 1.00
		kick_power = 0.0
		kick_weight_calculation = false
		ground_friction_24hz = 0.50
		can_burn = false
		ignites = false
		hp = 5.0
		max_hp = 5.0
		bullet_resistance = 100.0
		explosion_resistance = 100.0
		prop_material = "Glass"

	if prop_type == "BARREL":
		explosion_resistance = 0.25
	elif prop_type in ["TRASHCAN", "FILECAB", "DESK", "DESK_1", "POOL_TABLE"]:
		explosion_resistance = 0.50
	elif prop_type == "CRATE_HANGING":
		explosion_resistance = 0.0

	player_fragile = prop_type in ["CRATE", "SUPPLY_CRATE", "TABLE", "TABLE_SMALL", "CHAIR", "CHAIR_R"]

	if prop_type in ["CRATE", "CRATE_HANGING", "BARREL", "BARREL_EXPLOSIVE", "TRASHCAN", "TABLE", "TABLE_SMALL", "DESK", "DESK_1", "POOL_TABLE", "COMFY_CHAIR", "FILECAB", "STATUE"]:
		allow_cover = true

	# AS3 MapPremadeItems.as: DrawHitBox = true for solid standable/blocking props (including GASCAN & CRATE_HANGING)
	has_solid_hitbox = prop_type in [
		"CRATE", "CRATE_HANGING", "TABLE", "TABLE_SMALL", "DESK", "DESK_1", "POOL_TABLE",
		"FILECAB", "BARREL", "BARREL_EXPLOSIVE", "GASCAN", "TRASHCAN", "STATUE", "COMFY_CHAIR", "LAMP_1"
	]
	# AS3 MapPremadeItems.as:675,1585,1979,2002,2025 (CanBlockExplosions = true): heavy/indestructible obstacles block explosion shockwaves
	can_block_explosions = prop_type in [
		"CRATE_HANGING", "STATUE", "DESK", "DESK_1", "POOL_TABLE", "FILECAB", "BARREL"
	]
	kickable = not (prop_type in ["CRATE_HANGING_HOLDER", "STATUE", "LAMP_1"])

	# AS3 BodyData.as:97 & MapPremadeItems.as: CrushDamage is 0 by default; only heavy furniture crushes when falling from above
	if prop_type in ["FILECAB", "DESK", "DESK_1", "POOL_TABLE"]:
		crush_damage = 35.0
	elif prop_type == "COMFY_CHAIR":
		crush_damage = 25.0
	elif prop_type == "CRATE_HANGING":
		crush_damage = 100.0
	else:
		crush_damage = 0.0
	last_attacker = null
	_attacker_ignore_frames = 0.0

	if prop_type == "BARREL_EXPLOSIVE":
		blast_damage = 20.0
		blast_radius = 45.0
	elif prop_type == "GASCAN":
		blast_damage = 15.0
		blast_radius = 28.0
	else:
		blast_damage = float(def.get("blast_damage", 20.0))
		blast_radius = float(def.get("blast_radius", 40.0))

	# AS3 BodyData.as:115 & MapPremadeItems.as per-prop Strength (caliber overpower & penetration threshold):
	if prop_type in ["COMP", "COMP_SCREEN", "PAPER", "CRATE_HANGING_HOLDER"]:
		prop_strength = 1
	elif prop_type == "GASCAN":
		prop_strength = 5
	elif prop_type in ["BARREL_EXPLOSIVE", "BARREL_WRECK", "BARREL", "TRASHCAN", "STATUE"]:
		prop_strength = 30
	else:
		prop_strength = 10

	_had_holder_linked = false
	_hang_angle = 0.0
	_hang_ang_vel = 0.0
	if prop_type == "CRATE_HANGING":
		is_hanging_crate = true
		is_hanging_released = false
		kinematic = true
		var def_anchor_y: float = minf(ceiling_anchor_y, p_pos.y - 36.0)
		_hang_anchor = Vector2(p_pos.x, def_anchor_y)
		_hang_rope_len = maxf(24.0, p_pos.y - def_anchor_y)
	elif prop_type == "CRATE_HANGING_HOLDER":
		# AS3 MapPremadeItems.as:1556-1565: size 10x7 (9+1 x 6+1), DrawHitBox = false, Strength = 1, HP = 6
		is_hanging_holder = true
		width = 10.0
		height = 7.0
		hp = 6.0
		max_hp = 6.0
		bullet_resistance = 100.0
		explosion_resistance = 100.0
		can_burn = false
		ignites = false
		kickable = false
		kinematic = true
		prop_material = "Metal"
		_hang_anchor = Vector2(p_pos.x, minf(ceiling_anchor_y, p_pos.y - 24.0))
		_hang_rope_len = maxf(16.0, p_pos.y - _hang_anchor.y)
	elif prop_type == "LAMP_1":
		kinematic = true

	base_width = width
	base_height = height
	_target_rest_rot = p_angle
	_ledge_overhang_dir = 0.0
	_ledge_fulcrum_x = NAN
	_ledge_fulcrum_y = INF
	is_sleeping = false
	_sleep_frames = 0.0
	_sync_rotated_dimensions()

	var spr_path: String = str(def.get("sprite", "res://assets/sprites/props/obj_crate_01.png"))
	if prop_type == "TABLE" and not ResourceLoader.exists(spr_path):
		spr_path = "res://assets/sprites/props/obj_table_01.png"
	elif prop_type in ["CHAIR", "CHAIR_R"] and not ResourceLoader.exists(spr_path):
		spr_path = "res://assets/sprites/props/obj_chair_01.png"

	var tex: Texture2D = reg.call("load_cached_texture", spr_path) as Texture2D
	if tex == null:
		tex = reg.call("load_cached_texture", "res://assets/sprites/props/obj_crate_01.png") as Texture2D
	_sprite.texture = tex
	_sprite.modulate = Color.WHITE
	_sprite.rotation_degrees = 0.0
	_sprite.scale = Vector2.ONE
	_sprite.position = Vector2.ZERO
	if prop_type == "CHAIR_R":
		_sprite.flip_h = true
	else:
		_sprite.flip_h = false

	queue_redraw()


func setup_supply_parachute_crate(p_pos: Vector2, p_weapon_id: String = "", p_id: int = 0) -> void:
	setup_prop("CRATE", p_pos, 0.0, "supply_crate", p_id)
	prop_type = "SUPPLY_CRATE"
	is_parachute_crate = true
	parachute_attached = true
	kinematic = false
	on_ground = false
	_settling_frames = 0.0
	hp = 18.0
	max_hp = 18.0
	width = 16.0
	height = 16.0
	base_width = 16.0
	base_height = 16.0
	_target_rest_rot = 0.0
	_ledge_overhang_dir = 0.0
	_ledge_fulcrum_x = NAN
	_ledge_fulcrum_y = INF
	allow_cover = true
	if p_weapon_id.is_empty():
		contained_weapon_id = SUPPLY_WEAPON_POOL[randi() % SUPPLY_WEAPON_POOL.size()]
	else:
		contained_weapon_id = p_weapon_id.to_upper()
	velocity = Vector2(0.0, PARACHUTE_FALL_SPEED)
	queue_redraw()


func link_hanging_holder(holder: Node2D, anchor_y: float = 51.0) -> void:
	holder_prop = holder
	_had_holder_linked = (holder != null)
	ceiling_anchor_y = minf(anchor_y, global_position.y - 24.0)
	_hang_anchor = Vector2(global_position.x, ceiling_anchor_y)
	_hang_rope_len = maxf(24.0, global_position.y - ceiling_anchor_y)
	_hang_angle = 0.0
	_hang_ang_vel = 0.0
	if holder != null:
		holder.set("attached_hanging_crate", self)
		holder.set("ceiling_anchor_y", ceiling_anchor_y)
		holder.set("_hang_anchor", _hang_anchor)
		holder.queue_redraw()
	queue_redraw()


func apply_pendulum_impulse(ang_vel_delta: float) -> void:
	if not is_hanging_crate or is_hanging_released:
		return
	_hang_ang_vel = clampf(_hang_ang_vel + ang_vel_delta, -0.14, 0.14)
	_settling_frames = 0.0
	queue_redraw()


func _can_rotate_dynamically() -> bool:
	if kinematic or is_hanging_holder or is_parachute_crate:
		return false
	if is_hanging_crate and not is_hanging_released:
		return false
	return true


func _can_tip_horizontally() -> bool:
	if not _can_rotate_dynamically():
		return false
	return prop_type in [
		"BARREL", "BARREL_EXPLOSIVE", "BARREL_WRECK", "GASCAN",
		"TRASHCAN", "FILECAB", "CHAIR", "CHAIR_R",
		"CRATE", "SUPPLY_CRATE", "COMP", "COMP_SCREEN", "TABLE_SMALL",
	]


func _get_critical_balance_angle() -> float:
	var w0: float = maxf(base_width, 1.0)
	var h0: float = maxf(base_height, 1.0)
	return atan2(w0, h0)


func _is_tipped_on_side() -> bool:
	if not _can_tip_horizontally():
		return false
	var crit: float = _get_critical_balance_angle()
	return absf(rotation) >= crit


func get_obb_extents_at(rot: float) -> Vector2:
	var c: float = absf(cos(rot))
	var s: float = absf(sin(rot))
	return Vector2(base_width * c + base_height * s, base_width * s + base_height * c)


func _sync_rotated_dimensions(keep_bottom_y: float = INF) -> void:
	if base_width <= 0.0 or base_height <= 0.0:
		return
	var obb_half_h: float = get_obb_extents_at(rotation).y * 0.5
	var is_sideways: bool = _is_tipped_on_side()
	var new_w: float = base_height if is_sideways else base_width
	var new_h: float = base_width if is_sideways else base_height
	if not is_equal_approx(width, new_w) or not is_equal_approx(height, new_h):
		var old_w: float = width
		var anchor_bottom_y: float = keep_bottom_y if keep_bottom_y < INF else (global_position.y + obb_half_h)
		width = new_w
		height = new_h
		if keep_bottom_y < INF or on_ground:
			global_position.y = anchor_bottom_y - obb_half_h
		if new_w > old_w and map_loader != null and is_instance_valid(map_loader):
			global_position.x = _clamp_x_against_walls(global_position.x, global_position.y, global_position.x)
	elif keep_bottom_y < INF:
		global_position.y = keep_bottom_y - obb_half_h


func _step_rotational_balance(step_24hz: float, support_y: float = INF) -> void:
	if not _can_rotate_dynamically():
		rotation = 0.0
		angular_velocity = 0.0
		if _sprite != null:
			_sprite.position = Vector2.ZERO
		return

	var half_pi: float = PI * 0.5

	# Wide heavy props (released CRATE_HANGING 28x16, DESK, POOL_TABLE, TABLE, COMFY_CHAIR):
	# They tilt downward when overhanging a ledge or falling in mid-air (up to +-39 deg),
	# and slap their wide base back flat to 0 deg when supported on solid ground.
	if not _can_tip_horizontally():
		_target_rest_rot = 0.0
		if not on_ground or absf(_ledge_overhang_dir) > 0.01:
			angular_velocity = clampf(angular_velocity * pow(0.96, step_24hz), -0.22, 0.22)
			rotation = clampf(rotation + angular_velocity * step_24hz, -0.68, 0.68)
		else:
			if absf(rotation) > 0.0005 or absf(angular_velocity) > 0.0005:
				var prev_rot_w: float = rotation
				var restore_w: float = -signf(rotation) * (0.045 + absf(rotation) * 0.22) * step_24hz
				angular_velocity = clampf((angular_velocity + restore_w) * pow(0.80, step_24hz), -0.22, 0.22)
				rotation += angular_velocity * step_24hz
				if prev_rot_w * rotation <= 0.0 or (absf(rotation) < 0.015 and absf(angular_velocity) < 0.02):
					rotation = 0.0
					angular_velocity = 0.0
			else:
				rotation = 0.0
				angular_velocity = 0.0
			if support_y < INF:
				global_position.y = support_y - get_obb_extents_at(rotation).y * 0.5
		if _sprite != null:
			_sprite.position = Vector2.ZERO
		return

	var prev_rot_bal: float = rotation
	var crit_angle: float = _get_critical_balance_angle()
	var abs_rot: float = absf(rotation)
	var rot_sign: float = signf(rotation)
	if absf(rot_sign) < 0.001:
		rot_sign = signf(angular_velocity)

	# Housner Inverted-Pendulum Corner-Rocking & Toppling Solver:
	# 1. Sub-Critical Regime (|theta| < theta_crit = atan2(W0, H0)):
	#    The Center of Mass is still inside the bottom support corner. Gravity exerts a restoring torque
	#    that decelerates upward tilt and pulls the prop BACK upright to 0 deg (unless overhanging a ledge).
	# 2. Super-Critical Regime (|theta| >= theta_crit or overhanging a ledge):
	#    The Center of Mass has crossed the bottom support corner. The prop teeters near theta_crit and
	#    gravity smoothly accelerates it down onto its horizontal side at +-90 deg.
	if abs_rot < crit_angle and absf(_ledge_overhang_dir) <= 0.01 and (on_ground or absf(sin(_target_rest_rot)) < 0.5):
		_target_rest_rot = 0.0
		if abs_rot > 0.0005 or absf(angular_velocity) > 0.0005:
			var norm_tilt: float = clampf(abs_rot / maxf(crit_angle, 0.05), 0.0, 1.0)
			var grav_restore: float = -rot_sign * 0.019 * sin(norm_tilt * PI) * step_24hz
			var prev_rot: float = rotation
			angular_velocity = clampf((angular_velocity + grav_restore) * pow(0.935, step_24hz), -0.22, 0.22)
			rotation += angular_velocity * step_24hz
			if prev_rot * rotation < 0.0 or (absf(rotation) < 0.012 and absf(angular_velocity) < 0.016):
				rotation = 0.0
				angular_velocity = 0.0
			elif absf(rotation) >= crit_angle:
				_target_rest_rot = signf(rotation) * half_pi
		else:
			rotation = 0.0
			angular_velocity = 0.0
	else:
		var side_sign: float = _ledge_overhang_dir if absf(_ledge_overhang_dir) > 0.01 else (rot_sign if absf(rot_sign) > 0.001 else signf(_target_rest_rot))
		if absf(side_sign) < 0.001:
			side_sign = 1.0
		_target_rest_rot = side_sign * half_pi
		var span: float = maxf(half_pi - crit_angle, 0.05)
		var over_ratio: float = clampf((abs_rot - crit_angle) / span, 0.0, 1.0)
		var grav_topple: float = side_sign * 0.032 * (0.22 + 0.78 * sin(over_ratio * half_pi)) * step_24hz
		angular_velocity = clampf((angular_velocity + grav_topple) * pow(0.965, step_24hz), -0.22, 0.22)
		rotation += angular_velocity * step_24hz
		if absf(rotation) >= half_pi:
			rotation = side_sign * half_pi
			angular_velocity = 0.0

	# Corner-pivot horizontal translation: when tipping on floor support, pivoting around the bottom corner
	# advances the center of mass forward in the direction of rotation rather than spinning in place.
	var delta_rot_bal: float = rotation - prev_rot_bal
	if support_y < INF and absf(delta_rot_bal) > 0.0005 and base_height > base_width:
		var pivot_push: float = (delta_rot_bal / maxf(step_24hz, 0.01)) * (base_height * 0.12)
		if signf(pivot_push) == signf(velocity.x) or absf(velocity.x) < 0.35:
			velocity.x = clampf(velocity.x + pivot_push, -3.2, 3.2)

	_sync_rotated_dimensions(support_y)
	if _sprite != null:
		_sprite.position = Vector2.ZERO


func get_world_rect() -> Rect2:
	return Rect2(global_position.x - width * 0.5, global_position.y - height * 0.5, width, height)


func get_solid_support_rect() -> Rect2:
	if not has_solid_hitbox or is_destroyed:
		return Rect2()
	if prop_type in ["TABLE", "TABLE_SMALL"]:
		# AS3 MapPremadeItems.as:2254, 2410-2417: tabletop collision box is 5px tall at the top of the table
		return Rect2(global_position.x - width * 0.5, global_position.y - height * 0.5, width, 5.0)
	return get_world_rect()


func get_hit_rect() -> Rect2:
	if is_hanging_holder:
		# Compound Hitbox for CRATE_HANGING_HOLDER: covers the entire iron suspension chain from ceiling anchor
		# down to 3.5px inside the top of CRATE_HANGING so aiming down while standing on the crate always hits!
		var anchor_y: float = _hang_anchor.y if _hang_anchor != Vector2.ZERO else ceiling_anchor_y
		var min_y: float = minf(anchor_y, global_position.y - height * 0.5 - 2.0)
		var max_y: float = global_position.y + height * 0.5 + 3.5
		var anchor_x: float = _hang_anchor.x if _hang_anchor != Vector2.ZERO else global_position.x
		var min_x: float = minf(anchor_x, global_position.x) - 8.5
		var max_x: float = maxf(anchor_x, global_position.x) + 8.5
		return Rect2(min_x, min_y, max_x - min_x, max_y - min_y)
	if absf(rotation) > 0.01:
		var ext: Vector2 = get_obb_extents_at(rotation)
		return Rect2(global_position.x - ext.x * 0.5, global_position.y - ext.y * 0.5, ext.x, ext.y)
	return get_world_rect()


func get_obb_top_y_at_x(qx: float, half_span: float = 3.5) -> float:
	if not has_solid_hitbox or is_destroyed:
		return INF
	if absf(sin(rotation)) <= 0.015 or absf(cos(rotation)) <= 0.015:
		var sr: Rect2 = get_solid_support_rect()
		if sr.size.x > 0.0 and qx + half_span >= sr.position.x and qx - half_span <= sr.end.x:
			return sr.position.y
		return INF
	var hw: float = (base_width if base_width > 0.0 else width) * 0.5
	var hh: float = (base_height if base_height > 0.0 else height) * 0.5
	var c0: Vector2 = global_position + Vector2(-hw, -hh).rotated(rotation)
	var c1: Vector2 = global_position + Vector2(hw, -hh).rotated(rotation)
	var c2: Vector2 = global_position + Vector2(hw, hh).rotated(rotation)
	var c3: Vector2 = global_position + Vector2(-hw, hh).rotated(rotation)
	var pts: Array[Vector2] = [c0, c1, c2, c3]
	var min_qx: float = qx - half_span
	var max_qx: float = qx + half_span
	var best_top_y: float = INF
	for p: Vector2 in pts:
		if p.x >= min_qx and p.x <= max_qx and p.y < best_top_y:
			best_top_y = p.y
	for i: int in range(4):
		var a: Vector2 = pts[i]
		var b: Vector2 = pts[(i + 1) % 4]
		var seg_min_x: float = minf(a.x, b.x)
		var seg_max_x: float = maxf(a.x, b.x)
		if seg_max_x < min_qx or seg_min_x > max_qx:
			continue
		var dx: float = b.x - a.x
		if absf(dx) <= 0.0001:
			best_top_y = minf(best_top_y, minf(a.y, b.y))
		else:
			var xa: float = clampf(min_qx, seg_min_x, seg_max_x)
			var xb: float = clampf(max_qx, seg_min_x, seg_max_x)
			var ya: float = lerpf(a.y, b.y, clampf((xa - a.x) / dx, 0.0, 1.0))
			var yb: float = lerpf(a.y, b.y, clampf((xb - a.x) / dx, 0.0, 1.0))
			best_top_y = minf(best_top_y, minf(ya, yb))
	return best_top_y


func _liang_barsky_local_rect_t(p1: Vector2, p2: Vector2, rect: Rect2) -> float:
	if rect.has_point(p1):
		return 0.0
	var d: Vector2 = p2 - p1
	var t_min: float = 0.0
	var t_max: float = 1.0
	var p_arr: Array[float] = [-d.x, d.x, -d.y, d.y]
	var q_arr: Array[float] = [
		p1.x - rect.position.x,
		rect.end.x - p1.x,
		p1.y - rect.position.y,
		rect.end.y - p1.y,
	]
	for i: int in range(4):
		var p_val: float = p_arr[i]
		var q_val: float = q_arr[i]
		if is_zero_approx(p_val):
			if q_val < 0.0:
				return INF
		else:
			var t: float = q_val / p_val
			if p_val < 0.0:
				if t > t_max:
					return INF
				if t > t_min:
					t_min = t
			else:
				if t < t_min:
					return INF
				if t < t_max:
					t_max = t
	return t_min if t_min <= t_max else INF


func check_segment_hit_obb(from_pt: Vector2, to_pt: Vector2) -> float:
	if is_destroyed:
		return INF
	if is_hanging_holder:
		var clasp_rect: Rect2 = Rect2(global_position.x - 8.5, global_position.y - height * 0.5 - 2.0, 17.0, height + 5.5)
		var t_clasp: float = _liang_barsky_local_rect_t(from_pt, to_pt, clasp_rect)
		var anchor_w: Vector2 = _hang_anchor if _hang_anchor != Vector2.ZERO else Vector2(global_position.x, ceiling_anchor_y)
		var bottom_w: Vector2 = global_position + Vector2(0.0, height * 0.5 + 3.5)
		var closest_pts: PackedVector2Array = Geometry2D.get_closest_points_between_segments(from_pt, to_pt, anchor_w, bottom_w)
		var t_chain: float = INF
		if closest_pts.size() >= 2 and closest_pts[0].distance_to(closest_pts[1]) <= 8.5:
			var seg_len: float = from_pt.distance_to(to_pt)
			t_chain = (from_pt.distance_to(closest_pts[0]) / seg_len) if seg_len > 0.001 else 0.0
		return minf(t_clasp, t_chain)
	if absf(rotation) > 0.01:
		var local_from: Vector2 = (from_pt - global_position).rotated(-rotation)
		var local_to: Vector2 = (to_pt - global_position).rotated(-rotation)
		var local_rect: Rect2 = Rect2(-base_width * 0.5, -base_height * 0.5, base_width, base_height)
		return _liang_barsky_local_rect_t(local_from, local_to, local_rect)
	return _liang_barsky_local_rect_t(from_pt, to_pt, get_world_rect())


func _spawn_debris_burst(hit_pos: Vector2, hit_dir: Vector2, count: int) -> void:
	if match_world == null or not is_instance_valid(match_world):
		return
	var fhs: Variant = match_world.get("fire_hazard_system")
	if fhs != null and is_instance_valid(fhs) and fhs.has_method("spawn_prop_debris"):
		fhs.call("spawn_prop_debris", prop_type, hit_pos, hit_dir, count)


func _apply_sprite_visual_transform() -> void:
	if _sprite == null or not is_instance_valid(_sprite):
		return
	var base_scale: Vector2 = Vector2.ONE
	var base_pos: Vector2 = Vector2.ZERO
	if prop_type == "BARREL" and barrel_phase == 0:
		if _damage_visual_stage == 1:
			base_scale = Vector2(1.04, 0.96)
			base_pos = Vector2(0.0, height * 0.02)
		elif _damage_visual_stage >= 2:
			base_scale = Vector2(1.10, 0.90)
			base_pos = Vector2(0.0, height * 0.05)
	if _impact_shudder_frames > 0.0:
		var shudder_t: float = clampf(_impact_shudder_frames / 5.0, 0.0, 1.0)
		var osc: float = sin(_impact_shudder_frames * 2.2) * 0.45 * shudder_t
		var sq_x: float = 1.0 + 0.08 * shudder_t
		var sq_y: float = 1.0 - 0.07 * shudder_t
		_sprite.scale = Vector2(base_scale.x * sq_x, base_scale.y * sq_y)
		_sprite.position = base_pos + Vector2(osc, height * 0.035 * shudder_t)
	else:
		_sprite.scale = base_scale
		_sprite.position = base_pos


func _update_damaged_visual(_hit_dir_x: float = 1.0) -> void:
	if is_destroyed or hp <= 0.0:
		return
	if prop_type == "BARREL" and barrel_phase == 0:
		var target_stage: int = 0
		if hp <= max_hp * 0.42:
			target_stage = 2
		elif hp <= max_hp * 0.78:
			target_stage = 1
		if target_stage <= _damage_visual_stage:
			_apply_sprite_visual_transform()
			return
		_damage_visual_stage = target_stage
		_is_damaged_visual = true
		_ensure_sprite()
		var reg_b: Node = MapLoaderScript.get_registry()
		var dtex_b: Texture2D = reg_b.call("load_cached_texture", "res://assets/sprites/props/obj_barrel_dmg.png") as Texture2D
		if dtex_b != null:
			_sprite.texture = dtex_b
		_sprite.rotation_degrees = 0.0
		_sprite.modulate = Color(0.75, 0.72, 0.70, 1.0) if target_stage >= 2 else Color(0.90, 0.88, 0.86, 1.0)
		_apply_sprite_visual_transform()
		queue_redraw()
		return
	if hp >= max_hp * 0.65 or _is_damaged_visual:
		return
	_is_damaged_visual = true
	_damage_visual_stage = 1
	_ensure_sprite()
	var reg: Node = MapLoaderScript.get_registry()

	if prop_type == "BARREL_EXPLOSIVE" and barrel_phase == 0:
		var wtex: Texture2D = reg.call("load_cached_texture", "res://assets/sprites/props/obj_barrel_wreck.png") as Texture2D
		if wtex != null:
			_sprite.texture = wtex
		_sprite.rotation_degrees = 0.0
		_sprite.modulate = Color(0.86, 0.82, 0.78, 1.0)
	elif prop_type == "GASCAN":
		var gtex: Texture2D = reg.call("load_cached_texture", "res://assets/sprites/props/obj_gascan_dmg.png") as Texture2D
		if gtex != null:
			_sprite.texture = gtex
		_sprite.rotation_degrees = 0.0
		_sprite.modulate = Color(0.86, 0.80, 0.78, 1.0)
	elif prop_type == "LAMP_1":
		var ltex: Texture2D = reg.call("load_cached_texture", "res://assets/sprites/props/obj_hanging_lamp_off.png") as Texture2D
		if ltex != null:
			_sprite.texture = ltex
	else:
		_sprite.rotation_degrees = 0.0
		_sprite.modulate = Color(0.84, 0.80, 0.76, 1.0)


func _find_overlapping_ladder_hatch(at_x: float, at_y: float) -> Rect2:
	if _settling_frames > 0.0 or is_hanging_crate or map_loader == null or not is_instance_valid(map_loader) or map_loader.get("ladder_rects") == null:
		return Rect2()
	var half_w: float = width * 0.5
	for lr_v: Variant in map_loader.get("ladder_rects") as Array:
		var lr: Rect2 = lr_v as Rect2
		var cx: float = lr.position.x + lr.size.x * 0.5
		var hatch_half: float = maxf(half_w * 0.55, lr.size.x * 0.5 + 1.5)
		if absf(at_x - cx) <= hatch_half and at_y >= lr.position.y - height - 10.0 and at_y <= lr.end.y - 4.0:
			return lr
	return Rect2()


func _append_clipped_support_seg(segs: Array[Vector3], surf_y: float, c1: float, c2: float, min_w: float, hatch_r: Rect2, half_w: float) -> float:
	if hatch_r.size.x > 0.0 and surf_y < hatch_r.end.y - 6.0:
		var cut_l: float = hatch_r.position.x - maxf(2.0, half_w - 2.0)
		var cut_r: float = hatch_r.end.x + maxf(2.0, half_w - 2.0)
		var best: float = INF
		if c1 < cut_l:
			var r1: float = minf(c2, cut_l)
			if r1 - c1 >= min_w:
				segs.append(Vector3(surf_y, c1, r1))
				best = surf_y
		if c2 > cut_r:
			var l2: float = maxf(c1, cut_r)
			if c2 - l2 >= min_w:
				segs.append(Vector3(surf_y, l2, c2))
				best = surf_y
		return best
	if c2 - c1 >= min_w:
		segs.append(Vector3(surf_y, c1, c2))
		return surf_y
	return INF


func _query_ledge_contact_manifold(at_x: float, prev_bottom: float, next_bottom: float) -> Dictionary:
	# 1D Sutherland-Hodgman Contact Manifold Clipping (Box2D b2CollidePolygon.as):
	# Clips the prop's horizontal base interval [box_left, box_right] against all candidate support surfaces
	# (solid_rects, cloud_rects, intact glass, elevators, and grounded/kinematic props) to compute the exact
	# contact segment [c1, c2], fulcrum corner (fulcrum_x, fulcrum_y), and overhang direction (-1.0 left, +1.0 right).
	var half_w: float = width * 0.5
	var box_left: float = at_x - half_w + 0.5
	var box_right: float = at_x + half_w - 0.5
	var obb_extra_y: float = maxf(0.0, (get_obb_extents_at(rotation).y - height) * 0.5)
	var tilt_lift: float = half_w * absf(sin(rotation))
	var max_drop: float = maxf(10.0, next_bottom - prev_bottom + 8.0 + obb_extra_y)
	var settle_pad: float = 8.5 if (_settling_frames > 0.0 or on_ground) else 2.5
	var min_solid_y: float = prev_bottom - settle_pad - tilt_lift
	var min_cloud_y: float = prev_bottom - (4.5 if (_settling_frames > 0.0 or on_ground) else 2.5) - tilt_lift
	var max_surf_y: float = prev_bottom + max_drop
	var min_contact_w: float = minf(2.2, width * 0.22)
	var hatch_r: Rect2 = _find_overlapping_ladder_hatch(at_x, prev_bottom - height * 0.5)

	var segs: Array[Vector3] = [] # Vector3(surf_y, c1, c2)
	var best_y: float = INF

	if map_loader != null and is_instance_valid(map_loader):
		var s_var: Variant = map_loader.get("solid_rects")
		if typeof(s_var) == TYPE_ARRAY:
			for sr_v: Variant in s_var as Array:
				if sr_v is Rect2:
					var sr: Rect2 = sr_v as Rect2
					if sr.size.x >= 1.0 and sr.position.y >= min_solid_y and sr.position.y <= max_surf_y:
						var c1: float = maxf(box_left, sr.position.x)
						var c2: float = minf(box_right, sr.end.x)
						var sy: float = _append_clipped_support_seg(segs, sr.position.y, c1, c2, min_contact_w, hatch_r, half_w)
						if sy < best_y:
							best_y = sy

		var c_var: Variant = map_loader.get("cloud_rects")
		if typeof(c_var) == TYPE_ARRAY:
			for cr_v: Variant in c_var as Array:
				if cr_v is Rect2:
					var cr: Rect2 = cr_v as Rect2
					if cr.size.x >= 1.0 and cr.position.y >= min_cloud_y and cr.position.y <= max_surf_y:
						var c1: float = maxf(box_left, cr.position.x)
						var c2: float = minf(box_right, cr.end.x)
						var cy: float = _append_clipped_support_seg(segs, cr.position.y, c1, c2, min_contact_w, hatch_r, half_w)
						if cy < best_y:
							best_y = cy

		if map_loader.has_method("get_intact_horizontal_glass_rects"):
			for gr: Rect2 in map_loader.call("get_intact_horizontal_glass_rects") as Array[Rect2]:
				if gr.size.x >= 1.0 and gr.position.y >= min_solid_y and gr.position.y <= max_surf_y:
					var c1: float = maxf(box_left, gr.position.x)
					var c2: float = minf(box_right, gr.end.x)
					if c2 - c1 >= min_contact_w:
						segs.append(Vector3(gr.position.y, c1, c2))
						if gr.position.y < best_y:
							best_y = gr.position.y

		var el_var: Variant = map_loader.get("elevators")
		if typeof(el_var) == TYPE_ARRAY:
			for e_v: Variant in el_var as Array:
				if typeof(e_v) == TYPE_DICTIONARY:
					var er_v: Variant = (e_v as Dictionary).get("rect")
					if er_v is Rect2:
						var er: Rect2 = er_v as Rect2
						if er.size.x >= 1.0 and er.position.y >= min_solid_y and er.position.y <= max_surf_y:
							var c1: float = maxf(box_left, er.position.x)
							var c2: float = minf(box_right, er.end.x)
							if c2 - c1 >= min_contact_w:
								segs.append(Vector3(er.position.y, c1, c2))
								if er.position.y < best_y:
									best_y = er.position.y

		var sp_var: Variant = map_loader.get("slope_polygons")
		if typeof(sp_var) == TYPE_ARRAY and not (sp_var as Array).is_empty() and map_loader.has_method("get_slope_ground_y_below"):
			var slope_y: float = float(map_loader.call("get_slope_ground_y_below", at_x, prev_bottom, 8.0, max_drop, true))
			if slope_y < INF and slope_y <= max_surf_y:
				segs.append(Vector3(slope_y, box_left, box_right))
				if slope_y < best_y:
					best_y = slope_y

	if match_world != null and is_instance_valid(match_world):
		var props_var: Variant = match_world.get("props")
		if typeof(props_var) == TYPE_ARRAY:
			for p_var: Variant in props_var as Array:
				if not is_instance_valid(p_var) or not (p_var is Node2D) or p_var == self:
					continue
				var other: Node2D = p_var as Node2D
				var other_is_paper_support: bool = (prop_type == "PAPER" and str(other.get("prop_type")) == "PAPER")
				if bool(other.get("is_destroyed")) or bool(other.get("is_hanging_holder")) or (not bool(other.get("has_solid_hitbox")) and not other_is_paper_support):
					continue
				if not bool(other.get("on_ground")) and not bool(other.get("kinematic")):
					continue
				var ow: float = float(other.get("width")) if other.get("width") != null else 14.0
				var oh: float = float(other.get("height")) if other.get("height") != null else 14.0
				var other_top: float = other.global_position.y - oh * 0.5
				if other_top >= prev_bottom - 2.5 and other_top <= max_surf_y:
					var c1: float = maxf(box_left, other.global_position.x - ow * 0.5)
					var c2: float = minf(box_right, other.global_position.x + ow * 0.5)
					var omass_m: float = maxf(0.4, float(other.get("mass")) if other.get("mass") != null else 1.0)
					# CB-EC-66: A heavy falling prop (m1 >= 1.8 * m2) striking a light prop off-center must never treat
					# the light prop as an unyielding ledge fulcrum; instead it crushes or shoves the light prop aside.
					var com_over_other: bool = (at_x >= c1 - 0.5 and at_x <= c2 + 0.5)
					if not on_ground and velocity.y > 2.15 and mass >= omass_m * 1.8 and (not com_over_other or (c2 - c1) < minf(width * 0.55, ow * 0.75)):
						continue
					if c2 - c1 >= minf(3.0, ow * 0.25):
						segs.append(Vector3(other_top, c1, c2))
						if other_top < best_y:
							best_y = other_top

	if best_y == INF:
		return {
			"has_support": false,
			"y": INF,
			"c1": INF,
			"c2": -INF,
			"overhang_dir": 0.0,
			"fulcrum_x": at_x,
			"fulcrum_y": INF,
			"com_supported": false,
		}

	var best_com_y: float = INF
	for seg_c: Vector3 in segs:
		if at_x >= seg_c.y - 0.5 and at_x <= seg_c.z + 0.5 and seg_c.x < best_com_y:
			best_com_y = seg_c.x
	if best_com_y < INF and best_com_y - best_y >= 4.0:
		best_y = best_com_y

	var min_c1: float = INF
	var max_c2: float = -INF
	for seg: Vector3 in segs:
		if absf(seg.x - best_y) <= 2.0:
			if seg.y < min_c1:
				min_c1 = seg.y
			if seg.z > max_c2:
				max_c2 = seg.z

	var open_right: bool = (max_c2 < box_right - 1.5)
	var open_left: bool = (min_c1 > box_left + 1.5)
	var is_past_com_right: bool = open_right and (at_x >= max_c2 - 0.15)
	var is_past_com_left: bool = open_left and (at_x <= min_c1 + 0.15)
	var can_tip_edge: bool = _can_tip_horizontally()
	var is_near_edge_right: bool = (
		can_tip_edge
		and open_right
		and _settling_frames <= 0.0
		and at_x >= max_c2 - width * 0.10
		and rotation >= -0.02
		and (velocity.x > 0.02 or (angular_velocity > 0.005 and rotation >= 0.0) or rotation > 0.01)
	)
	var is_near_edge_left: bool = (
		can_tip_edge
		and open_left
		and _settling_frames <= 0.0
		and at_x <= min_c1 + width * 0.10
		and rotation <= 0.02
		and (velocity.x < -0.02 or (angular_velocity < -0.005 and rotation <= 0.0) or rotation < -0.01)
	)

	var overhang_dir: float = 0.0
	var fulcrum_x: float = clampf(at_x, min_c1, max_c2)
	var com_supported: bool = true

	if (is_past_com_right or is_near_edge_right) and not is_past_com_left:
		overhang_dir = 1.0
		fulcrum_x = max_c2
		com_supported = not is_past_com_right
	elif is_past_com_left or is_near_edge_left:
		overhang_dir = -1.0
		fulcrum_x = min_c1
		com_supported = not is_past_com_left

	return {
		"has_support": true,
		"y": best_y,
		"c1": min_c1,
		"c2": max_c2,
		"overhang_dir": overhang_dir,
		"fulcrum_x": fulcrum_x,
		"fulcrum_y": best_y,
		"com_supported": com_supported,
	}


func _resolve_obb_world_sat_contacts(cand_pos: Vector2, prev_pos: Vector2) -> Vector2:
	# 2D OBB-vs-AABB Separating Axis Theorem (SAT) Non-Penetration Solver (Box2D b2CollidePolygon.as):
	# Prevents rotated props (especially falling/pivoting crates on ledges) from ever penetrating solid walls,
	# floors, or one-way cloud platforms around a ledge fulcrum.
	if map_loader == null or not is_instance_valid(map_loader):
		return cand_pos

	var rot: float = rotation
	var c: float = absf(cos(rot))
	var s: float = absf(sin(rot))
	var cos_r: float = cos(rot)
	var sin_r: float = sin(rot)
	var hw: float = (base_width if base_width > 0.0 else width) * 0.5
	var hh: float = (base_height if base_height > 0.0 else height) * 0.5
	if absf(rot) <= 0.005:
		hw = width * 0.5
		hh = height * 0.5

	var r_obb_x: float = hw * c + hh * s
	var r_obb_y: float = hw * s + hh * c

	var obstacles: Array[Rect2] = _get_solid_world_obstacles()
	var c_var: Variant = map_loader.get("cloud_rects")
	if typeof(c_var) == TYPE_ARRAY and _ledge_fulcrum_y < INF:
		for cr_v: Variant in c_var as Array:
			if cr_v is Rect2:
				var cr: Rect2 = cr_v as Rect2
				if absf(cr.position.y - _ledge_fulcrum_y) <= 2.5:
					obstacles.append(cr)

	var sat_hatch_r: Rect2 = _find_overlapping_ladder_hatch(cand_pos.x, cand_pos.y) if absf(velocity.y) > 0.12 else Rect2()
	for sr: Rect2 in obstacles:
		if sr.size.x < 1.0 or sr.size.y < 1.5:
			continue
		if _is_shaft_side_obstacle(sr, sat_hatch_r):
			continue
		var sc: Vector2 = sr.position + sr.size * 0.5
		var sh: Vector2 = sr.size * 0.5
		var d: Vector2 = cand_pos - sc

		var pen_wx: float = (r_obb_x + sh.x) - absf(d.x)
		if pen_wx <= 0.001:
			continue
		var pen_wy: float = (r_obb_y + sh.y) - absf(d.y)
		if pen_wy <= 0.001:
			continue

		var proj_d_ux: float = d.x * cos_r + d.y * sin_r
		var r_aabb_ux: float = sh.x * c + sh.y * s
		var pen_ux: float = (hw + r_aabb_ux) - absf(proj_d_ux)
		if pen_ux <= 0.001:
			continue

		var proj_d_uy: float = -d.x * sin_r + d.y * cos_r
		var r_aabb_uy: float = sh.x * s + sh.y * c
		var pen_uy: float = (hh + r_aabb_uy) - absf(proj_d_uy)
		if pen_uy <= 0.001:
			continue

		# Special handling for a ledge fulcrum platform while the prop is overhanging and pivoting/sliding off its edge:
		var is_fulcrum_plat: bool = (absf(sr.position.y - _ledge_fulcrum_y) <= 2.5)
		if is_fulcrum_plat:
			var c_local: Array[Vector2] = [
				Vector2(-hw, -hh),
				Vector2(hw, -hh),
				Vector2(hw, hh),
				Vector2(-hw, hh),
			]
			for lp: Vector2 in c_local:
				var wp: Vector2 = cand_pos + lp.rotated(rot)
				if wp.x > sr.position.x and wp.x < sr.end.x and wp.y > sr.position.y and wp.y < sr.end.y + 8.0:
					var dx_edge: float = (wp.x - sr.position.x) if cand_pos.x < sr.position.x + sr.size.x * 0.5 else (sr.end.x - wp.x)
					var dy_top: float = wp.y - sr.position.y
					if cand_pos.y >= sr.position.y - 1.5 or dx_edge <= dy_top + 1.5:
						var push_dir: float = -1.0 if cand_pos.x < sr.position.x + sr.size.x * 0.5 else 1.0
						cand_pos.x += push_dir * (dx_edge + 0.15)
					else:
						cand_pos.y -= (dy_top + 0.15)
			continue

		# General Minimum Translation Vector (MTV) resolution across the 4 SAT axes
		if pen_wx < pen_wy and pen_wx <= pen_ux + 0.5 and pen_wx <= pen_uy + 0.5:
			var sx: float = 1.0 if d.x >= 0.0 else -1.0
			cand_pos.x += sx * pen_wx
		elif pen_wy <= pen_ux + 0.5 and pen_wy <= pen_uy + 0.5:
			var sy: float = 1.0 if d.y >= 0.0 else -1.0
			cand_pos.y += sy * pen_wy
		elif pen_ux < pen_uy:
			var sux: float = 1.0 if proj_d_ux >= 0.0 else -1.0
			cand_pos += Vector2(cos_r, sin_r) * (sux * pen_ux)
		else:
			var suy: float = 1.0 if proj_d_uy >= 0.0 else -1.0
			cand_pos += Vector2(-sin_r, cos_r) * (suy * pen_uy)

	return cand_pos


func _get_solid_world_obstacles() -> Array[Rect2]:
	var out: Array[Rect2] = []
	if map_loader == null or not is_instance_valid(map_loader):
		return out
	var s_var: Variant = map_loader.get("solid_rects")
	if typeof(s_var) == TYPE_ARRAY:
		for sr_v: Variant in s_var as Array:
			if sr_v is Rect2:
				out.append(sr_v as Rect2)
	if map_loader.has_method("get_intact_horizontal_glass_rects"):
		for gr: Rect2 in map_loader.call("get_intact_horizontal_glass_rects") as Array[Rect2]:
			out.append(gr)
	if map_loader.has_method("get_intact_vertical_glass_rects"):
		for vgr: Rect2 in map_loader.call("get_intact_vertical_glass_rects") as Array[Rect2]:
			out.append(vgr)
	return out


func _is_shaft_side_obstacle(sr: Rect2, hatch_r: Rect2) -> bool:
	if hatch_r.size.x <= 0.0:
		return false
	if sr.position.y >= hatch_r.end.y - 6.0 or sr.end.y <= hatch_r.position.y - 8.0:
		return false
	var near_x: bool = (sr.end.x >= hatch_r.position.x - 18.0 and sr.position.x <= hatch_r.end.x + 18.0)
	return near_x


func _clamp_x_against_walls(cand_x: float, at_y: float, from_x: float = INF) -> float:
	if map_loader == null or not is_instance_valid(map_loader):
		return cand_x
	var prev_x: float = global_position.x if from_x == INF else from_x
	var half_w: float = width * 0.5
	var half_h: float = height * 0.5
	var top_y: float = at_y - half_h + 2.0
	var bot_y: float = at_y + half_h - 2.0
	var hatch_r: Rect2 = _find_overlapping_ladder_hatch(cand_x, at_y) if absf(velocity.y) > 0.12 else Rect2()

	for sr: Rect2 in _get_solid_world_obstacles():
		if sr.size.y < 3.0 or sr.size.x < 1.0:
			continue
		if bot_y <= sr.position.y or top_y >= sr.end.y:
			continue
		if _is_shaft_side_obstacle(sr, hatch_r):
			continue
		if prev_x + half_w <= sr.position.x + 3.5 and cand_x + half_w > sr.position.x:
			cand_x = minf(cand_x, sr.position.x - half_w)
		elif prev_x - half_w >= sr.end.x - 3.5 and cand_x - half_w < sr.end.x:
			cand_x = maxf(cand_x, sr.end.x + half_w)
	return cand_x


func _clamp_x_against_other_props(cand_x: float, at_y: float, from_x: float = INF) -> float:
	if not has_solid_hitbox or match_world == null or not is_instance_valid(match_world):
		return cand_x
	var props_var: Variant = match_world.get("props")
	if typeof(props_var) != TYPE_ARRAY:
		return cand_x
	var prev_x: float = global_position.x if from_x == INF else from_x
	var my_bottom: float = at_y + height * 0.5
	var my_top: float = at_y - height * 0.5
	for p_var: Variant in props_var as Array:
		if not is_instance_valid(p_var) or not (p_var is Node2D) or p_var == self:
			continue
		var other: Node2D = p_var as Node2D
		if bool(other.get("is_destroyed")) or bool(other.get("is_hanging_holder")) or not bool(other.get("has_solid_hitbox")):
			continue
		var other_type: String = str(other.get("prop_type")).to_upper()
		if other_type == "LAMP_1":
			continue
		var ow: float = float(other.get("width")) if other.get("width") != null else 14.0
		var oh: float = float(other.get("height")) if other.get("height") != null else 14.0
		var other_top: float = other.global_position.y - oh * 0.5
		var other_bottom: float = other.global_position.y + oh * 0.5
		if my_bottom <= other_top + 2.0 or other_bottom <= my_top + 2.0:
			continue
		var min_dx: float = (width + ow) * 0.5
		if absf(cand_x - other.global_position.x) < min_dx:
			var side_sign: float = 1.0 if prev_x >= other.global_position.x else -1.0
			cand_x = other.global_position.x + side_sign * min_dx
	return cand_x


func _clamp_y_against_ceilings(cand_x: float, prev_y: float, cand_y: float) -> float:
	if cand_y >= prev_y:
		return cand_y
	var half_w: float = width * 0.5
	var half_h: float = height * 0.5
	var skin_x: float = minf(1.5, half_w * 0.25)
	var left_x: float = cand_x - half_w + skin_x
	var right_x: float = cand_x + half_w - skin_x
	var prev_top: float = prev_y - half_h
	var cand_top: float = cand_y - half_h
	var hatch_r: Rect2 = _find_overlapping_ladder_hatch(cand_x, cand_y)

	for sr: Rect2 in _get_solid_world_obstacles():
		if sr.size.y < 2.0 or right_x <= sr.position.x or left_x >= sr.end.x:
			continue
		if _is_shaft_side_obstacle(sr, hatch_r):
			continue
		if prev_top >= sr.end.y - 4.0 and cand_top < sr.end.y:
			cand_y = maxf(cand_y, sr.end.y + half_h)
			cand_top = cand_y - half_h

	if match_world != null and is_instance_valid(match_world):
		var props_var: Variant = match_world.get("props")
		if typeof(props_var) == TYPE_ARRAY:
			for p_var: Variant in props_var as Array:
				if not is_instance_valid(p_var) or not (p_var is Node2D) or p_var == self:
					continue
				var other: Node2D = p_var as Node2D
				if bool(other.get("is_destroyed")) or bool(other.get("is_hanging_holder")) or not bool(other.get("has_solid_hitbox")):
					continue
				var ow: float = float(other.get("width")) if other.get("width") != null else 14.0
				var oh: float = float(other.get("height")) if other.get("height") != null else 14.0
				if absf(cand_x - other.global_position.x) < (width + ow) * 0.5 - 1.5:
					var other_bottom: float = other.global_position.y + oh * 0.5
					if prev_top >= other_bottom - 4.0 and cand_top < other_bottom:
						cand_y = maxf(cand_y, other_bottom + half_h)
						cand_top = cand_y - half_h
	return cand_y


func wake_up() -> void:
	is_sleeping = false
	_sleep_frames = 0.0


func _wake_nearby_props(radius_pad: float = 28.0) -> void:
	if match_world == null or not is_instance_valid(match_world):
		return
	var props_v: Variant = match_world.get("props")
	if typeof(props_v) != TYPE_ARRAY:
		return
	var wake_rx: float = width * 0.5 + radius_pad
	var wake_ry: float = height + radius_pad + 18.0
	for p_v: Variant in props_v as Array:
		if p_v is Node2D and is_instance_valid(p_v) and p_v != self:
			var op: Node2D = p_v as Node2D
			if bool(op.get("is_sleeping")):
				if absf(op.global_position.x - global_position.x) <= wake_rx and absf(op.global_position.y - global_position.y) <= wake_ry:
					if op.has_method("wake_up"):
						op.call("wake_up")
					else:
						op.set("is_sleeping", false)


func extinguish_fire() -> void:
	if is_burning or _fire_heat > 0.0:
		is_burning = false
		_fire_heat = 0.0
		burn_timer = 0.0
		queue_redraw()


func step_prop(step_24hz: float) -> void:
	if is_destroyed:
		return

	if is_sleeping:
		var glass_ver: int = int(map_loader.get("h_glass_break_version")) if (map_loader != null and is_instance_valid(map_loader) and map_loader.get("h_glass_break_version") != null) else 0
		if (
			not on_ground
			or is_burning
			or _fire_heat > 0.0
			or barrel_phase != 0
			or velocity.length_squared() >= 0.0025
			or absf(angular_velocity) >= 0.002
			or (is_hanging_crate and not is_hanging_released)
			or (is_parachute_crate and parachute_attached)
			or glass_ver != _sleep_glass_version
		):
			is_sleeping = false
			_sleep_frames = 0.0
		else:
			if _settling_frames > 0.0:
				_settling_frames = maxf(0.0, _settling_frames - step_24hz)
			if _impact_shudder_frames > 0.0:
				_impact_shudder_frames = maxf(0.0, _impact_shudder_frames - step_24hz)
				_apply_sprite_visual_transform()
				queue_redraw()
			if _attacker_ignore_frames > 0.0:
				_attacker_ignore_frames = maxf(0.0, _attacker_ignore_frames - step_24hz)
				if _attacker_ignore_frames <= 0.0:
					last_attacker = null
			return

	if _settling_frames > 0.0:
		_settling_frames = maxf(0.0, _settling_frames - step_24hz)
	if _impact_shudder_frames > 0.0:
		_impact_shudder_frames = maxf(0.0, _impact_shudder_frames - step_24hz)
		_apply_sprite_visual_transform()
		queue_redraw()
	if _attacker_ignore_frames > 0.0:
		_attacker_ignore_frames = maxf(0.0, _attacker_ignore_frames - step_24hz)
		if _attacker_ignore_frames <= 0.0:
			last_attacker = null
	if not _prop_impact_cooldowns.is_empty():
		var expired_oids: Array[int] = []
		for oid_k: Variant in _prop_impact_cooldowns.keys():
			var rem_cd: float = float(_prop_impact_cooldowns[oid_k]) - step_24hz
			if rem_cd <= 0.0:
				expired_oids.append(int(oid_k))
			else:
				_prop_impact_cooldowns[oid_k] = rem_cd
		for ex_id: int in expired_oids:
			_prop_impact_cooldowns.erase(ex_id)

	# 1. Burning logic & Gradual Fire Contagion (Fires.as:142-182: gradual heat transfer to nearby fighters & adjacent flammable props)
	if is_burning and not can_burn and barrel_phase == 0:
		is_burning = false
	if not is_burning and _fire_heat > 0.0:
		_fire_heat = maxf(0.0, _fire_heat - 1.2 * step_24hz)
	if is_burning:
		burn_timer += step_24hz
		_fire_anim_frame += step_24hz * 1.15
		if match_world != null and is_instance_valid(match_world):
			var burn_rect_f: Rect2 = get_world_rect().grow(3.5)
			# 1a. Gradually heat/ignite any non-rolling fighter standing on or right against this burning prop
			var fighters_b: Variant = match_world.get("fighters")
			if typeof(fighters_b) == TYPE_ARRAY:
				for fb_var: Variant in fighters_b as Array:
					if not (fb_var is Node2D) or not is_instance_valid(fb_var):
						continue
					var fb: Node2D = fb_var as Node2D
					if bool(fb.get("is_dead")) or bool(fb.get("rolling")):
						continue
					var f_rect_b: Rect2 = fb.call("get_hit_rect") as Rect2 if fb.has_method("get_hit_rect") else Rect2(fb.global_position.x - 6.0, fb.global_position.y - 18.0, 12.0, 18.0)
					f_rect_b.size.y += 4.0
					if burn_rect_f.intersects(f_rect_b) and fb.has_method("add_burn"):
						fb.call("add_burn", 3.5 * step_24hz, false)
			# 1b. Gradually spread heat to adjacent or stacked flammable props after burning for >= 12 frames (~0.5s)
			if burn_timer >= 12.0:
				var burn_rect_p: Rect2 = get_world_rect().grow(4.5)
				var props_b: Variant = match_world.get("props")
				if typeof(props_b) == TYPE_ARRAY:
					for pb_var: Variant in props_b as Array:
						if not (pb_var is Node2D) or not is_instance_valid(pb_var) or pb_var == self:
							continue
						var other_p: Node2D = pb_var as Node2D
						if bool(other_p.get("is_destroyed")) or bool(other_p.get("is_burning")) or not bool(other_p.get("can_burn")):
							continue
						var op_rect: Rect2 = other_p.call("get_world_rect") as Rect2 if other_p.has_method("get_world_rect") else Rect2(other_p.global_position.x - 7.0, other_p.global_position.y - 7.0, 14.0, 14.0)
						if burn_rect_p.intersects(op_rect):
							if other_p.has_method("add_fire_heat"):
								other_p.call("add_fire_heat", 3.2 * step_24hz)
							elif other_p.has_method("ignite"):
								other_p.call("ignite")
		if barrel_phase == 1:
			# AS3 MapPremadeItems.as:1726-1744: BARREL_WRECK burns slower while airborne so it follows a physical arc,
			# and burns down on the ground (or detonates on hard landing impact).
			var burn_rate: float = 0.85 if on_ground else 0.35
			hp -= burn_rate * step_24hz
			if hp <= 0.0:
				_trigger_barrel_phase_2_explosion()
				return
		elif prop_type in ["BARREL_EXPLOSIVE", "GASCAN"]:
			if burn_timer >= 68.0:
				_trigger_explosive_prop_hit(Vector2.UP)
				return
		else:
			var wood_burn_rate: float = 2.0 if prop_type == "PAPER" else 0.85
			hp -= wood_burn_rate * step_24hz
			_update_damaged_visual(1.0)
			if hp <= 0.0:
				_destroy_prop(Vector2.UP)
				return
		queue_redraw()

	# 2. Check if hanging crate's holder was destroyed, or step physical pendulum swing while suspended
	if is_hanging_crate and not is_hanging_released:
		if _had_holder_linked and (holder_prop == null or not is_instance_valid(holder_prop) or bool(holder_prop.get("is_destroyed"))):
			release_hanging_crate()
		else:
			if _hang_rope_len <= 1.0:
				var eff_ay: float = minf(ceiling_anchor_y, global_position.y - 24.0)
				_hang_anchor = Vector2(global_position.x, eff_ay)
				_hang_rope_len = maxf(24.0, global_position.y - eff_ay)
			if absf(_hang_angle) > 0.0005 or absf(_hang_ang_vel) > 0.0005:
				var prev_hang_pos: Vector2 = global_position
				var g_pend: float = 0.52083 / maxf(20.0, _hang_rope_len) # AS3 Box2D g=10m/s^2 (0.52083 px/tick^2) / L
				_hang_ang_vel = (_hang_ang_vel - sin(_hang_angle) * g_pend * step_24hz) * pow(0.955, step_24hz)
				_hang_angle = clampf(_hang_angle + _hang_ang_vel * step_24hz, -0.22, 0.22)
				if absf(_hang_angle) < 0.0015 and absf(_hang_ang_vel) < 0.0015:
					_hang_angle = 0.0
					_hang_ang_vel = 0.0
				var cand_hang_pos: Vector2 = _hang_anchor + Vector2(sin(_hang_angle) * _hang_rope_len, cos(_hang_angle) * _hang_rope_len)
				# Enforce 4-way solid world & prop collision on swinging CRATE_HANGING so it NEVER penetrates platforms, walls, or crates!
				var clamped_hx: float = _clamp_x_against_walls(cand_hang_pos.x, cand_hang_pos.y, prev_hang_pos.x)
				clamped_hx = _clamp_x_against_other_props(clamped_hx, cand_hang_pos.y, prev_hang_pos.x)
				if absf(clamped_hx - cand_hang_pos.x) > 0.01:
					var sin_clamped: float = clampf((clamped_hx - _hang_anchor.x) / maxf(24.0, _hang_rope_len), -0.22, 0.22)
					_hang_angle = asin(sin_clamped)
					_hang_ang_vel = -_hang_ang_vel * 0.30
					cand_hang_pos = _hang_anchor + Vector2(sin(_hang_angle) * _hang_rope_len, cos(_hang_angle) * _hang_rope_len)
				global_position = cand_hang_pos
				velocity = (global_position - prev_hang_pos) / maxf(0.1, step_24hz)
				rotation = -_hang_angle
				if holder_prop != null and is_instance_valid(holder_prop) and not bool(holder_prop.get("is_destroyed")):
					var holder_r: float = maxf(8.0, _hang_rope_len - height * 0.5 - 3.5)
					holder_prop.global_position = _hang_anchor + Vector2(sin(_hang_angle) * holder_r, cos(_hang_angle) * holder_r)
					holder_prop.rotation = rotation
					holder_prop.set("_hang_anchor", _hang_anchor)
					holder_prop.queue_redraw()
				if match_world != null and is_instance_valid(match_world):
					var f_arr_h: Variant = match_world.get("fighters")
					if typeof(f_arr_h) == TYPE_ARRAY:
						var prev_top_y: float = prev_hang_pos.y - height * 0.5
						var new_top_y: float = global_position.y - height * 0.5
						var delta_hang: Vector2 = global_position - prev_hang_pos
						for fh_v: Variant in f_arr_h as Array:
							if fh_v is Node2D and is_instance_valid(fh_v):
								var fh: Node2D = fh_v as Node2D
								if not bool(fh.get("is_dead")) and bool(fh.get("on_ground")):
									if absf(fh.global_position.y - prev_top_y) <= 3.5 and absf(fh.global_position.x - prev_hang_pos.x) <= width * 0.5 + 3.0:
										fh.global_position = Vector2(fh.global_position.x + delta_hang.x, new_top_y)
				if absf(velocity.x) >= 1.4:
					_check_fighter_impacts(prev_hang_pos, global_position)
				queue_redraw()
			else:
				velocity = Vector2.ZERO
			return

	if kinematic:
		return

	# 3. Gravity, Ledge Fulcrum Overhang Torque & Sliding Solver, & Parachute descent
	var prev_pos: Vector2 = global_position
	var can_tip: bool = _can_tip_horizontally()
	var can_rot: bool = _can_rotate_dynamically()

	_ledge_overhang_dir = 0.0
	if on_ground and map_loader != null and is_instance_valid(map_loader):
		var cur_bottom: float = prev_pos.y + get_obb_extents_at(rotation).y * 0.5
		var manifold_g: Dictionary = _query_ledge_contact_manifold(prev_pos.x, cur_bottom, cur_bottom + 3.0)
		var has_sup_g: bool = bool(manifold_g.get("has_support", false))
		var odir_g: float = float(manifold_g.get("overhang_dir", 0.0))
		var sup_y_g: float = float(manifold_g.get("y", INF))

		var over_hatch_g: bool = _find_overlapping_ladder_hatch(prev_pos.x, prev_pos.y).size.x > 0.0
		var moving_onto_platform_g: bool = (velocity.x * odir_g < -0.02 and not is_hanging_crate and not over_hatch_g)
		if has_sup_g and absf(odir_g) > 0.01 and not moving_onto_platform_g:
			_ledge_overhang_dir = odir_g
			_ledge_fulcrum_x = float(manifold_g.get("fulcrum_x", prev_pos.x))
			_ledge_fulcrum_y = float(manifold_g.get("fulcrum_y", sup_y_g))
			var is_past_com: bool = not bool(manifold_g.get("com_supported", false))
			var rot_accel: float = 0.135 if is_past_com else 0.075
			var slide_accel: float = (0.38 if is_past_com else 0.22) + 1.15 * absf(sin(rotation))
			if can_rot:
				angular_velocity = clampf(angular_velocity + odir_g * rot_accel * step_24hz, -0.24, 0.24)
			velocity.x += odir_g * slide_accel * step_24hz
			if is_past_com and odir_g * velocity.x < 0.42:
				velocity.x = odir_g * 0.42
			if can_tip and absf(sin(_target_rest_rot)) < 0.5:
				_target_rest_rot = odir_g * (PI * 0.5)
			if is_past_com or absf(rotation) >= 0.08:
				on_ground = false
				velocity.y = maxf(velocity.y, 0.35 + absf(sin(rotation)) * 1.8)
		elif has_sup_g and absf(odir_g) > 0.01 and moving_onto_platform_g:
			# Prop is actively sliding ONTO the platform from a horizontal kick -> carry Center of Mass onto the platform!
			prev_pos.x += signf(velocity.x) * 0.55 * step_24hz
		elif not has_sup_g:
			on_ground = false
			_ledge_fulcrum_y = INF
			if can_rot and absf(velocity.x) > 0.02:
				var fall_dir: float = signf(velocity.x)
				if can_tip and absf(sin(_target_rest_rot)) < 0.5:
					_target_rest_rot = fall_dir * (PI * 0.5)
				angular_velocity += fall_dir * 0.12 * step_24hz
		else:
			_ledge_fulcrum_y = INF
			if velocity == Vector2.ZERO and is_zero_approx(angular_velocity) and absf(rotation - _target_rest_rot) <= 0.01 and not is_parachute_crate and _settling_frames <= 0.0:
				# Fast-path for stationary settled props well inside their platform support
				rotation = _target_rest_rot if can_tip else 0.0
				angular_velocity = 0.0
				_sync_rotated_dimensions(sup_y_g)
				return

	if is_parachute_crate and parachute_attached and not on_ground:
		_parachute_sway_time += step_24hz * 0.08
		velocity.x = sin(_parachute_sway_time) * 0.35
		velocity.y = PARACHUTE_FALL_SPEED
		rotation = sin(_parachute_sway_time) * 0.08
	else:
		if not on_ground:
			velocity.y = minf(TERMINAL_VELOCITY_Y, velocity.y + PROP_GRAVITY * step_24hz)
			_step_rotational_balance(step_24hz)
		else:
			var eff_friction: float = maxf(ground_friction_24hz, 0.80) if (can_tip and absf(angular_velocity) > 0.025) else ground_friction_24hz
			velocity.x *= pow(eff_friction, step_24hz)
			if absf(velocity.x) < 0.03:
				velocity.x = 0.0
			var sup_y_bal: float = prev_pos.y + get_obb_extents_at(rotation).y * 0.5
			_step_rotational_balance(step_24hz, sup_y_bal)
			prev_pos.y = global_position.y

	var next_pos: Vector2 = prev_pos + velocity * step_24hz

	# 4. Break glass windows if flying through them (suppressed during initial settling frames)
	if _settling_frames <= 0.0 and map_loader != null and is_instance_valid(map_loader) and velocity.length() > 0.8:
		if map_loader.has_method("check_and_break_glass_segment"):
			map_loader.call("check_and_break_glass_segment", prev_pos, next_pos, velocity)

	# 4b. Portal Doorways & Ladder Shaft Channeling before solid wall clamp
	if _settling_frames <= 0.0 and map_loader != null and is_instance_valid(map_loader):
		if absf(velocity.x) > 0.02 and map_loader.has_method("try_teleport_entity"):
			var saved_p: Vector2 = global_position
			global_position = next_pos
			if bool(map_loader.call("try_teleport_entity", self, signf(velocity.x))):
				next_pos = global_position
				prev_pos = next_pos
			else:
				global_position = saved_p
		var active_hatch: Rect2 = _find_overlapping_ladder_hatch(next_pos.x, next_pos.y)
		if active_hatch.size.x > 0.0 and absf(velocity.y) > 0.15 and next_pos.y < active_hatch.end.y - height * 0.5 - 4.0:
			var h_cx: float = active_hatch.position.x + active_hatch.size.x * 0.5
			next_pos.x = move_toward(next_pos.x, h_cx, 2.2 * step_24hz)
			velocity.x *= 0.65

	# 5. Horizontal wall collision & clamp (Swept AABB across full prop height)
	if map_loader != null and is_instance_valid(map_loader):
		var clamped_wall_x: float = _clamp_x_against_walls(next_pos.x, prev_pos.y, prev_pos.x)
		if absf(clamped_wall_x - next_pos.x) > 0.001:
			next_pos.x = clamped_wall_x
			velocity.x = -velocity.x * 0.25
		elif absf(velocity.x) > 0.05:
			var side_pt: Vector2 = Vector2(next_pos.x + signf(velocity.x) * (width * 0.5), prev_pos.y)
			if map_loader.has_method("is_point_solid") and bool(map_loader.call("is_point_solid", side_pt, false)):
				next_pos.x = prev_pos.x
				velocity.x = -velocity.x * 0.25

	# 5b. Horizontal Prop-vs-Prop collision & separation (prevents crates/barrels/gascans/hanging crates from overlapping horizontally)
	if has_solid_hitbox and match_world != null and is_instance_valid(match_world):
		var props_var: Variant = match_world.get("props")
		if typeof(props_var) == TYPE_ARRAY:
			for p_var: Variant in props_var as Array:
				if not is_instance_valid(p_var) or not (p_var is Node2D) or p_var == self:
					continue
				var other: Node2D = p_var as Node2D
				if bool(other.get("is_destroyed")) or bool(other.get("is_hanging_holder")) or not bool(other.get("has_solid_hitbox")):
					continue
				var other_type: String = str(other.get("prop_type")).to_upper()
				if other_type == "LAMP_1":
					continue
				var ow: float = float(other.get("width")) if other.get("width") != null else 14.0
				var oh: float = float(other.get("height")) if other.get("height") != null else 14.0
				# Only separate horizontally if on the same vertical band (not stacked one on top of the other)
				var my_bottom: float = next_pos.y + height * 0.5
				var other_top: float = other.global_position.y - oh * 0.5
				var other_bottom: float = other.global_position.y + oh * 0.5
				var my_top: float = next_pos.y - height * 0.5
				if my_bottom <= other_top + 2.5 or other_bottom <= my_top + 2.5:
					continue
				# Vertical Descent Guard: if this prop was already horizontally overlapping `other` while descending from above,
				# do NOT teleport/shunt either prop sideways in Step 5b; let Step 6b resolve the vertical top-down crush!
				var prev_bottom_5b: float = prev_pos.y + height * 0.5
				var prev_overlap_x: float = minf(prev_pos.x + width * 0.5, other.global_position.x + ow * 0.5) - maxf(prev_pos.x - width * 0.5, other.global_position.x - ow * 0.5)
				if not on_ground and velocity.y > 0.25 and prev_bottom_5b <= other_top + 4.5 and prev_overlap_x >= 2.0:
					continue
				var min_dx: float = (width + ow) * 0.5
				var dx_p: float = next_pos.x - other.global_position.x
				if absf(dx_p) < min_dx:
					var push_sign: float = 1.0 if dx_p >= 0.0 else -1.0
					if absf(dx_p) < 0.01:
						push_sign = 1.0 if prop_id > int(other.get("prop_id")) else -1.0
					var ovel_pre: Vector2 = other.get("velocity") as Vector2 if other.get("velocity") != null else Vector2.ZERO
					var v_rel_horiz: float = (velocity.x - ovel_pre.x) * (-push_sign)
					if _settling_frames <= 0.0 and v_rel_horiz > 2.40:
						_resolve_prop_collision_damage(other, v_rel_horiz, false, 1.0)
						if is_destroyed:
							return
						if bool(other.get("is_destroyed")) or int(other.get("barrel_phase")) > 0:
							var omass_br: float = maxf(0.4, float(other.get("mass")) if other.get("mass") != null else 1.0)
							velocity.x *= (mass / (mass + 0.30 * omass_br))
							continue
					var omass_sep: float = maxf(0.4, float(other.get("mass")) if other.get("mass") != null else 1.0)
					if not bool(other.get("kinematic")) and (absf(_ledge_overhang_dir) > 0.01 or mass >= omass_sep * 1.35):
						var overlap_p: float = min_dx - absf(dx_p)
						var share_o: float = 1.0 if (absf(_ledge_overhang_dir) > 0.01 or crushed_prop_ids.has(other.get_instance_id())) else (mass / (mass + omass_sep))
						var other_pushed_x: float = other.global_position.x - push_sign * overlap_p * share_o
						if other.has_method("_clamp_x_against_walls"):
							other_pushed_x = float(other.call("_clamp_x_against_walls", other_pushed_x, other.global_position.y))
						other.global_position.x = other_pushed_x
					var cand_x: float = _clamp_x_against_walls(other.global_position.x + push_sign * min_dx, prev_pos.y)
					if absf(cand_x - other.global_position.x) < min_dx - 0.1 and not bool(other.get("kinematic")):
						# This prop is against a wall, so push `other` out instead of overlapping!
						var other_new_x: float = cand_x - push_sign * min_dx
						if other.has_method("_clamp_x_against_walls"):
							other_new_x = float(other.call("_clamp_x_against_walls", other_new_x, other.global_position.y))
						other.global_position.x = other_new_x
						cand_x = _clamp_x_against_walls(other.global_position.x + push_sign * min_dx, prev_pos.y)
					next_pos.x = cand_x
					if absf(velocity.x) > 0.04 and velocity.x * push_sign < 0.0:
						if not bool(other.get("kinematic")) and other.get("velocity") != null:
							var omass: float = maxf(0.4, float(other.get("mass")) if other.get("mass") != null else 1.0)
							var transfer_ratio: float = (mass / (mass + omass)) * 0.45
							var ovel: Vector2 = other.get("velocity") as Vector2
							ovel.x = clampf(ovel.x + velocity.x * transfer_ratio, -2.5, 2.5)
							other.set("velocity", ovel)
						velocity.x *= 0.20

	# 5c. Horizontal Prop-vs-Fighter solid space occupancy (prevents props from phasing through standing/crouching/squeezed fighters!)
	var is_high_speed_gibb_horizontal: bool = can_gibb and (absf(velocity.x) >= 1.6 or velocity.length() >= 2.1)
	var is_falling_crush_descent: bool = (is_hanging_crate and is_hanging_released and not on_ground and velocity.y > 0.8)
	if has_solid_hitbox and not is_high_speed_gibb_horizontal and not is_falling_crush_descent and not (prop_type in ["TABLE", "TABLE_SMALL", "LAMP_1"]) and velocity.length() <= 3.8 and match_world != null and is_instance_valid(match_world):
		var fighters_s: Variant = match_world.get("fighters")
		if typeof(fighters_s) == TYPE_ARRAY:
			var my_top_s: float = next_pos.y - height * 0.5
			var my_bot_s: float = next_pos.y + height * 0.5
			var min_f_dx: float = width * 0.5 + 4.0
			for fs_var: Variant in fighters_s as Array:
				if not is_instance_valid(fs_var) or not (fs_var is Node2D):
					continue
				var f_node: Node2D = fs_var as Node2D
				if bool(f_node.get("is_dead")) or bool(f_node.get("climbing")) or bool(f_node.get("ledge_grabbing")):
					continue
				if f_node == last_attacker and _attacker_ignore_frames > 0.0:
					continue
				# Skip if fighter is standing on top of this prop
				if f_node.global_position.y <= my_top_s + 3.0 or f_node.global_position.y - 15.0 >= my_bot_s - 2.0:
					continue
				var dx_f: float = f_node.global_position.x - next_pos.x
				if absf(dx_f) < min_f_dx:
					var f_side: float = 1.0 if (f_node.global_position.x >= prev_pos.x) else -1.0
					if absf(f_node.global_position.x - prev_pos.x) < 0.05:
						f_side = 1.0 if velocity.x >= 0.0 else -1.0
					var desired_f_x: float = next_pos.x + f_side * min_f_dx
					var push_f_dx: float = desired_f_x - f_node.global_position.x
					if absf(push_f_dx) > 0.001 and f_node.has_method("try_push_horizontally_by_prop"):
						f_node.call("try_push_horizontally_by_prop", push_f_dx, self)
					# Re-verify fighter position; if fighter was blocked by a wall or another prop (Screenshot 1), stop this prop at the fighter's edge!
					if absf(f_node.global_position.x - next_pos.x) < min_f_dx - 0.01:
						next_pos.x = _clamp_x_against_walls(f_node.global_position.x - f_side * min_f_dx, prev_pos.y)
						velocity.x = 0.0

	# 6. Check falling crush / flying impact on fighters & props below/beside
	if _settling_frames <= 0.0 or (is_hanging_crate and is_hanging_released):
		if (is_hanging_crate and is_hanging_released and not on_ground and velocity.y > 0.8) or (can_gibb and ((not on_ground and velocity.y > 1.4) or absf(velocity.x) >= 1.6)) or velocity.length() >= 2.1:
			_check_fighter_impacts(prev_pos, next_pos)
	if ((_settling_frames <= 0.0 and not on_ground and velocity.y > 0.4) or (not on_ground and velocity.y > 2.15) or absf(velocity.x) > 2.40):
		_check_prop_impacts(prev_pos, next_pos)
		if is_destroyed:
			return

	# 7. Ground / Platform / Prop-stack landing, Ledge Fulcrum Corner Solver & Ceiling collision check
	on_ground = false
	if velocity.y < 0.0:
		var clamped_ceil_y: float = _clamp_y_against_ceilings(next_pos.x, prev_pos.y, next_pos.y)
		if clamped_ceil_y > next_pos.y + 0.001:
			next_pos.y = clamped_ceil_y
			velocity.y = 0.0
	elif map_loader != null and is_instance_valid(map_loader) and velocity.y >= 0.0:
		var obb_half_h: float = get_obb_extents_at(rotation).y * 0.5
		var eff_half_h: float = maxf(height * 0.5, obb_half_h)
		var prev_bottom: float = prev_pos.y + obb_half_h
		var next_obb_bottom: float = next_pos.y + eff_half_h
		var manifold: Dictionary = _query_ledge_contact_manifold(next_pos.x, prev_bottom, next_obb_bottom)
		var has_sup: bool = bool(manifold.get("has_support", false))
		var ground_y: float = float(manifold.get("y", INF))
		var odir: float = float(manifold.get("overhang_dir", 0.0))

		var over_hatch_f: bool = _find_overlapping_ladder_hatch(next_pos.x, next_pos.y).size.x > 0.0
		var moving_onto_platform: bool = (velocity.x * odir < -0.05 and not is_hanging_crate and not over_hatch_f)
		if has_sup and absf(odir) > 0.01 and not moving_onto_platform and next_obb_bottom >= ground_y - 0.5:
			# Case 7A: Partial Ledge Corner Strike / Fulcrum Slide (e.g. storage crate_hanging_1 at x=168 hitting Rect2(172, 166, 50, 2)):
			# The overhanging side (odir = -1.0 LEFT or +1.0 RIGHT) has no support under the Center of Mass!
			# The prop pivots around (fulcrum_x, fulcrum_y), tilts toward `odir`, and slides off `odir` with 0.0px platform penetration.
			_ledge_overhang_dir = odir
			_ledge_fulcrum_x = float(manifold.get("fulcrum_x", next_pos.x))
			_ledge_fulcrum_y = float(manifold.get("fulcrum_y", ground_y))
			var is_past_com: bool = not bool(manifold.get("com_supported", false))
			var lever_ratio: float = clampf(absf(_ledge_fulcrum_x - next_pos.x) / maxf(4.0, width * 0.5), 0.18, 0.85)

			if velocity.y > 0.45:
				if can_rot:
					var impact_spin: float = clampf(velocity.y * 0.060 * (0.65 + lever_ratio), 0.085, 0.22)
					if odir * angular_velocity < impact_spin:
						angular_velocity = odir * maxf(absf(angular_velocity), impact_spin)
					if odir * rotation < 0.02:
						rotation = odir * maxf(0.02, absf(angular_velocity) * step_24hz)
				var deflect_vx: float = maxf(0.62, velocity.y * 0.34 * (0.55 + lever_ratio) + absf(sin(rotation)) * 1.20)
				if odir * velocity.x < deflect_vx:
					velocity.x = odir * deflect_vx
				if can_tip and absf(sin(_target_rest_rot)) < 0.5:
					_target_rest_rot = odir * (PI * 0.5)
				if _settling_frames <= 0.0 and velocity.y >= 1.8:
					MapLoaderScript.play_sfx_at("wood_impact" if prop_material == "Wood" else "metal_impact", Vector2(_ledge_fulcrum_x, _ledge_fulcrum_y))

			if can_rot:
				angular_velocity = clampf(angular_velocity + odir * (0.135 if is_past_com else 0.075) * step_24hz, -0.24, 0.24)
			velocity.x += odir * ((0.38 if is_past_com else 0.22) + 1.15 * absf(sin(rotation))) * step_24hz
			next_pos.x = _clamp_x_against_walls(prev_pos.x + velocity.x * step_24hz, prev_pos.y, prev_pos.x)
			next_pos.x = _clamp_x_against_other_props(next_pos.x, prev_pos.y, prev_pos.x)

			var rot_f: float = clampf(rotation, -1.15, 1.15)
			var dx_f: float = _ledge_fulcrum_x - next_pos.x
			var cos_r: float = maxf(0.38, cos(rot_f))
			var fulcrum_tangent_y: float = _ledge_fulcrum_y - ((height * 0.5) + dx_f * sin(rot_f)) / cos_r
			if next_pos.y > fulcrum_tangent_y:
				next_pos.y = fulcrum_tangent_y
				velocity.y = clampf((next_pos.y - prev_pos.y) / maxf(0.1, step_24hz), 0.35, 2.4)
			on_ground = not is_past_com and absf(rotation) < 0.08
		elif has_sup and next_obb_bottom >= ground_y - 0.5:
			var impact_vy: float = velocity.y
			next_pos.y = ground_y - get_obb_extents_at(rotation).y * 0.5
			if moving_onto_platform and not bool(manifold.get("com_supported", false)):
				next_pos.x = _clamp_x_against_walls(next_pos.x + signf(velocity.x) * 0.65 * step_24hz, next_pos.y, prev_pos.x)
			if (_settling_frames <= 0.0 or (is_hanging_crate and is_hanging_released)) and ((is_hanging_crate and is_hanging_released) or can_gibb) and impact_vy > 1.0:
				# Final swept crush check right at the floor landing position (Player.as:6234-6286 CheckGibPlayer)
				_check_fighter_impacts(prev_pos, next_pos)
			velocity.y = 0.0
			on_ground = true
			_ledge_overhang_dir = 0.0
			_ledge_fulcrum_y = INF
			if can_tip:
				if impact_vy >= 3.5 and absf(rotation - _target_rest_rot) > 0.45:
					_target_rest_rot = clampf(round(rotation / (PI * 0.5)) * (PI * 0.5), -PI * 0.5, PI * 0.5)
				_sync_rotated_dimensions(ground_y)
				next_pos.y = ground_y - get_obb_extents_at(rotation).y * 0.5
			elif can_rot:
				# Wide heavy props (CRATE_HANGING, DESK, TABLE) slap their wide base down toward 0 deg on landing impact
				if absf(rotation) > 0.02:
					angular_velocity = -signf(rotation) * maxf(absf(angular_velocity) * 0.5, 0.14)
					next_pos.y = ground_y - get_obb_extents_at(rotation).y * 0.5
				else:
					rotation = 0.0
					angular_velocity = 0.0
					next_pos.y = ground_y - height * 0.5
			else:
				rotation = 0.0
				angular_velocity = 0.0
			if absf(velocity.x) < 0.25:
				crushed_fighter_ids.clear()
				crushed_prop_ids.clear()

			if is_parachute_crate and parachute_attached:
				# Detach parachute and stay intact on ground until hit or opened by player
				parachute_attached = false
				velocity = Vector2.ZERO
				global_position = next_pos
				queue_redraw()
				return

			if is_hanging_crate and is_hanging_released and impact_vy >= 1.5:
				# AS3 MapPremadeItems.as:1575-1595 & BodyData.as:618: CRATE_HANGING has _indestructible = true!
				# It lands completely intact on the floor as a super-heavy solid crate obstacle and never breaks!
				if _settling_frames <= 0.0:
					MapLoaderScript.play_sfx_at("wood_impact", next_pos)
				_spawn_debris_burst(next_pos + Vector2(0.0, height * 0.35), Vector2(0.0, -1.8), 3)

			if barrel_phase == 1 and burn_timer >= 6.0 and impact_vy >= 3.0:
				# AS3 MapPremadeItems.as:1741: flying BARREL_WRECK has impact resistance 100 after ObjectTimer=6 and detonates on hard landing!
				global_position = next_pos
				_trigger_barrel_phase_2_explosion()
				return

	# 8. 2D OBB-vs-AABB SAT Non-Penetration & Self-Healing Runtime Guardrails
	if _ledge_fulcrum_y < INF:
		var obb_ext_sat: Vector2 = get_obb_extents_at(rotation)
		if on_ground or next_pos.y - obb_ext_sat.y * 0.5 > _ledge_fulcrum_y + 2.0 or (not is_nan(_ledge_fulcrum_x) and absf(next_pos.x - _ledge_fulcrum_x) > obb_ext_sat.x * 0.5 + 2.0):
			_ledge_fulcrum_y = INF
	if absf(_ledge_overhang_dir) > 0.01 or (_ledge_fulcrum_y < INF and absf(rotation) > 0.01):
		next_pos = _resolve_obb_world_sat_contacts(next_pos, prev_pos)

	if is_nan(next_pos.x) or is_nan(next_pos.y) or is_inf(next_pos.x) or is_inf(next_pos.y):
		next_pos = prev_pos
		velocity = Vector2.ZERO
		angular_velocity = 0.0
		rotation = 0.0
	if is_nan(rotation) or is_inf(rotation):
		rotation = 0.0
		angular_velocity = 0.0

	if next_pos.distance_squared_to(prev_pos) > 0.25:
		_wake_nearby_props()
	global_position = next_pos
	if next_pos.y > 460.0 and not is_hanging_holder:
		is_destroyed = true
		visible = false
		return

	if (
		on_ground
		and not is_burning
		and _fire_heat <= 0.0
		and barrel_phase == 0
		and not (is_hanging_crate and not is_hanging_released)
		and not (is_parachute_crate and parachute_attached)
		and velocity.length_squared() < 0.04
		and absf(angular_velocity) < 0.01
		and absf(rotation - _target_rest_rot) <= 0.01
		and absf(_ledge_overhang_dir) <= 0.01
	):
		_sleep_frames += step_24hz
		if _sleep_frames >= 12.0:
			is_sleeping = true
			velocity = Vector2.ZERO
			angular_velocity = 0.0
			_sleep_glass_version = int(map_loader.get("h_glass_break_version")) if (map_loader != null and is_instance_valid(map_loader) and map_loader.get("h_glass_break_version") != null) else 0
	else:
		_sleep_frames = 0.0
		is_sleeping = false


func try_open_supply_crate() -> bool:
	if is_destroyed or not is_parachute_crate:
		return false
	_open_supply_crate()
	return true


func _check_fighter_impacts(prev_pos: Vector2, at_pos: Vector2) -> void:
	if match_world == null or not is_instance_valid(match_world):
		return
	var fighters_var: Variant = match_world.get("fighters")
	if typeof(fighters_var) != TYPE_ARRAY:
		return

	var min_rx: float = minf(prev_pos.x, at_pos.x) - width * 0.5
	var max_rx: float = maxf(prev_pos.x, at_pos.x) + width * 0.5
	var min_ry: float = minf(prev_pos.y, at_pos.y) - height * 0.5
	var max_ry: float = maxf(prev_pos.y, at_pos.y) + height * 0.5
	var my_rect: Rect2 = Rect2(min_rx, min_ry, max_rx - min_rx, max_ry - min_ry)
	var prop_top_y: float = min_ry
	var prev_bottom: float = prev_pos.y + height * 0.5
	var at_bottom: float = at_pos.y + height * 0.5
	var is_gibb_prop: bool = can_gibb or (is_hanging_crate and is_hanging_released)
	var is_falling_hanging_crate: bool = is_hanging_crate and is_hanging_released and not on_ground

	for f_var: Variant in fighters_var as Array:
		if not is_instance_valid(f_var) or not (f_var is Node2D):
			continue
		var f: Node2D = f_var as Node2D
		if bool(f.get("is_gibbed")) or bool(f.get("is_dead")):
			continue
		if f == last_attacker and _attacker_ignore_frames > 0.0:
			continue
		var fid: int = f.get_instance_id()
		if crushed_fighter_ids.has(fid):
			continue

		# AS3 Player.as:2987: never impact a fighter standing on top of this prop
		if f.global_position.y <= prop_top_y + 3.0 and absf(f.global_position.x - at_pos.x) <= width * 0.5 + 5.0:
			continue

		var f_mid: Vector2 = f.global_position + Vector2(0.0, -8.0)
		if f.has_method("get_mid_pos"):
			f_mid = f.call("get_mid_pos") as Vector2

		# AS3 Player.as:2135-2262 (CheckCollisionWithBody) & 6259-6286 (CheckGibPlayer):
		# 1. `falling_from_above`: prop's bottom edge descends from above a grounded fighter's legs/waist with real downward speed (vy >= 2.0).
		# 2. `crushing_downed_fighter`: released falling CRATE_HANGING lands from above onto a grounded knocked-down fighter underneath its span.
		# 3. `moving_towards_x`: prop is sliding/flying horizontally into the fighter at speed (|vx| >= 1.6).
		# A fighter who is already dead or falling from a height is NEVER gibbed into meat chunks!
		var f_grounded_not_falling: bool = bool(f.get("on_ground")) and not bool(f.get("falling"))
		var moving_towards_x: bool = (at_pos.x < f_mid.x and velocity.x >= 1.6) or (at_pos.x > f_mid.x and velocity.x <= -1.6)
		var falling_from_above: bool = f_grounded_not_falling and (prev_bottom <= f.global_position.y - 4.5 and velocity.y >= 2.0)
		var crushing_downed_fighter: bool = (
			is_falling_hanging_crate
			and f_grounded_not_falling
			and bool(f.get("knockdowned"))
			and prev_bottom <= f.global_position.y - 3.0
			and velocity.y >= 1.8
			and absf(f.global_position.x - at_pos.x) <= width * 0.5 + 2.0
			and at_bottom >= f.global_position.y - 4.0
		)
		if not moving_towards_x and not falling_from_above and not crushing_downed_fighter:
			continue

		var f_rect: Rect2 = Rect2(f.global_position.x - 6.0, f.global_position.y - 18.0, 12.0, 18.0)
		if f.has_method("get_hit_rect"):
			f_rect = f.call("get_hit_rect") as Rect2

		if my_rect.intersects(f_rect):
			var hit_dir: int = 1 if (velocity.x > 0.1 or (absf(velocity.x) <= 0.1 and f.global_position.x >= at_pos.x)) else -1
			var pinned_against_wall: bool = (
				is_falling_hanging_crate
				and f_grounded_not_falling
				and moving_towards_x
				and (absf(velocity.x) >= 3.0 or velocity.length() >= 3.8)
				and f.has_method("can_fighter_stand_at_x")
				and not bool(f.call("can_fighter_stand_at_x", f.global_position.x + float(hit_dir) * 3.5, f.global_position.y, self))
			)
			if is_falling_hanging_crate and (falling_from_above or crushing_downed_fighter or pinned_against_wall):
				# AS3 Player.as:1948, 6234-6286 (CanGibb -> GibPlayer): heavy CRATE_HANGING / DESK / POOL_TABLE
				# crushes a fighter when falling from above, landing on a knocked-down fighter, or blasting them into a solid wall!
				crushed_fighter_ids[fid] = true
				if f.has_method("gib_fighter"):
					f.call("gib_fighter", Vector2(float(hit_dir) * 2.5, -2.5))
			elif crush_damage > 0.0 and falling_from_above:
				# Heavy furniture (FILECAB, COMFY_CHAIR) falling from above deals CrushDamage
				crushed_fighter_ids[fid] = true
				var cur_hp: float = float(f.get("hp")) if f.get("hp") != null else 100.0
				f.set("hp", maxf(0.0, cur_hp - crush_damage))
				if float(f.get("hp")) <= 0.0:
					f.set("is_dead", true)
					f.set("current_state", "DEAD")
				elif f.has_method("force_fall"):
					f.call("force_fall", float(hit_dir) * 2.2, -2.0, true)
			elif is_gibb_prop and moving_towards_x and (absf(velocity.x) >= 1.6 or velocity.length() >= 2.1) and not bool(f.get("is_dead")):
				# Heavy crate blasted horizontally into a standing/kneeling fighter in open space deals impact damage and knocks them down!
				crushed_fighter_ids[fid] = true
				var cur_hp_g: float = float(f.get("hp")) if f.get("hp") != null else 100.0
				var imp_dmg: float = clampf(velocity.length() * 5.0, 14.0, 26.0)
				if f.has_method("_apply_raw_damage"):
					f.call("_apply_raw_damage", imp_dmg)
				else:
					f.set("hp", maxf(0.0, cur_hp_g - imp_dmg))
				if not bool(f.get("is_dead")) and f.has_method("force_fall"):
					f.call("force_fall", float(hit_dir) * 2.8, -2.0, true)
			elif velocity.length() > 3.8 and not bool(f.get("is_dead")):
				# AS3 BodyData.as:97 & Player.as:2193-2209: regular props (CrushDamage = 0) knock the target down without direct HP loss
				crushed_fighter_ids[fid] = true
				if f.has_method("force_fall"):
					f.call("force_fall", float(hit_dir) * 2.6, -1.8, false)


func _get_structural_hardness() -> float:
	if indestructible or prop_type in ["CRATE_HANGING", "STATUE"]:
		return 3.0
	if prop_type == "BARREL":
		return 2.20
	if prop_type in ["FILECAB", "TRASHCAN"]:
		return 1.65
	if prop_type in ["DESK", "DESK_1", "POOL_TABLE"]:
		return 1.25
	if prop_type in ["BARREL_EXPLOSIVE", "BARREL_WRECK"]:
		return 0.90
	if prop_type in ["TABLE", "COMFY_CHAIR"]:
		return 0.72
	if prop_type in ["CHAIR", "CHAIR_R", "TABLE_SMALL", "GASCAN", "COMP", "COMP_SCREEN"]:
		return 0.55
	if prop_type in ["PAPER", "LAMP_1"]:
		return 0.30
	return 1.0


func _resolve_prop_collision_damage(other: Node2D, v_rel: float, is_vertical: bool, overlap_ratio: float = 1.0) -> void:
	if other == null or not is_instance_valid(other) or is_destroyed or bool(other.get("is_destroyed")):
		return
	var oid: int = other.get_instance_id()
	if _prop_impact_cooldowns.has(oid) or (is_vertical and crushed_prop_ids.has(oid)):
		return
	var v_min: float = 2.15 if is_vertical else 2.40
	if v_rel <= v_min:
		return

	var cd_ticks: float = 18.0 if is_vertical else 8.0
	_prop_impact_cooldowns[oid] = cd_ticks
	if is_vertical:
		crushed_prop_ids[oid] = true
	var other_cds: Variant = other.get("_prop_impact_cooldowns")
	if typeof(other_cds) == TYPE_DICTIONARY:
		(other_cds as Dictionary)[get_instance_id()] = cd_ticks

	var m1: float = maxf(0.35, mass)
	var m2: float = maxf(0.35, float(other.get("mass")) if other.get("mass") != null else 1.0)
	var mu: float = (m1 * m2) / (m1 + m2)
	var v_eff: float = v_rel - v_min
	var h1: float = _get_structural_hardness()
	var h2: float = float(other.call("_get_structural_hardness")) if other.has_method("_get_structural_hardness") else 1.0
	var ov_factor: float = clampf(overlap_ratio / 0.45, 0.45, 1.0)

	var dmg_to_other: float = 0.0
	var dmg_to_self: float = 0.0

	if is_vertical:
		# Classical Overburden Crush Formula: E_crush = 1.85 * (0.5 * m1 * v_eff^2) * (m1 / m2)^0.65 + B_heavy
		var ke_crush: float = 1.85 * (0.5 * m1 * v_eff * v_eff) * pow(m1 / m2, 0.65)
		var heavy_bonus: float = 0.0
		if crush_damage > 0.0:
			heavy_bonus = crush_damage * clampf(v_rel / 4.5, 0.5, 2.0)
		elif m1 > 1.5:
			heavy_bonus = 8.0 * (m1 - 1.5) * v_eff
		dmg_to_other = (ke_crush + heavy_bonus) * (h1 / maxf(0.2, h2)) * ov_factor
		# Newton's 3rd Law upward normal reaction impulse on top prop
		dmg_to_self = (0.95 * (0.5 * mu * v_eff * v_eff) * pow(m2 / m1, 0.55)) * (h2 / maxf(0.2, h1)) * ov_factor
	else:
		# Horizontal / Ballistic kinetic impact formula
		var ke_horiz: float = 2.40 * (0.5 * mu * v_eff * v_eff) * sqrt(m1 / m2)
		var horiz_bonus: float = (crush_damage * 0.45 * clampf(v_eff / 2.0, 0.25, 1.2)) if (can_gibb or crush_damage > 0.0) else 0.0
		dmg_to_other = (ke_horiz + horiz_bonus) * (h1 / maxf(0.2, h2)) * ov_factor
		dmg_to_self = (1.10 * (0.5 * mu * v_eff * v_eff) * sqrt(m2 / m1)) * (h2 / maxf(0.2, h1)) * ov_factor

	if last_attacker != null and is_instance_valid(last_attacker):
		other.set("last_attacker", last_attacker)
		other.set("_attacker_ignore_frames", 18.0)

	var other_type: String = str(other.get("prop_type")).to_upper()
	var other_hp: float = float(other.get("hp")) if other.get("hp") != null else 25.0
	var other_max_hp: float = float(other.get("max_hp")) if other.get("max_hp") != null else 25.0
	var imp_vec: Vector2 = Vector2(velocity.x, velocity.y) if is_vertical else Vector2(velocity.x, -1.2)

	# Reinforced Cylindrical Steel Drum Calibration (CB-EC-68 / SF-M37.5):
	# Thick-walled steel drum (`BARREL`) absorbs vertical overburden impacts via progressive plastic buckling
	# (Stage 1 dent -> Stage 2 heavy buckle -> Stage 3 rupture), requiring > 2.5 full-height heavy crate drops (3 hits) to break.
	if other_type == "BARREL":
		if is_vertical:
			var barrel_crush_scale: float = clampf((m1 / 3.80) * (0.82 + 0.18 * clampf(v_eff / 8.85, 0.0, 1.0)), 0.15, 1.05)
			dmg_to_other = minf(dmg_to_other * 0.14, other_max_hp * 0.37 * barrel_crush_scale * ov_factor)
		else:
			dmg_to_other = minf(dmg_to_other * 0.25, other_max_hp * 0.28 * ov_factor)

	var other_mat: String = str(other.get("prop_material"))
	if _settling_frames <= 0.0:
		if prop_material == "Metal" or other_mat == "Metal":
			MapLoaderScript.play_sfx_at("metal_impact", other.global_position)
		else:
			MapLoaderScript.play_sfx_at("wood_impact", other.global_position)
		if (prop_material == "Metal" or other_mat == "Metal") and dmg_to_other >= 12.0 and match_world != null and is_instance_valid(match_world):
			var fhs_sp: Variant = match_world.get("fire_hazard_system")
			if fhs_sp != null and is_instance_valid(fhs_sp) and fhs_sp.has_method("spawn_hit_sparks"):
				fhs_sp.call("spawn_hit_sparks", other.global_position + Vector2(0.0, -float(other.get("height")) * 0.45), false)

	if dmg_to_other >= 1.0 and not bool(other.get("indestructible")):
		if other.has_method("_spawn_debris_burst"):
			other.call("_spawn_debris_burst", other.global_position + Vector2(0.0, -float(other.get("height")) * 0.4), Vector2(velocity.x * 0.4, -2.0), 2)
		if is_vertical and other_type == "BARREL_EXPLOSIVE" and int(other.get("barrel_phase")) == 0 and m1 >= 2.2 and dmg_to_other >= 50.0:
			# Catastrophic overburden crush: heavy falling prop flattens and detonates BARREL_EXPLOSIVE immediately on the spot!
			if other.has_method("_trigger_barrel_catastrophic_crush_explosion"):
				other.call("_trigger_barrel_catastrophic_crush_explosion")
			else:
				other.call("take_damage", dmg_to_other, imp_vec)
		elif other.has_method("take_damage"):
			other.call("take_damage", dmg_to_other, imp_vec)
			# If a sub-lethal hard impact dents BARREL_EXPLOSIVE below 65% HP, ignite its fuse just like a bullet hit!
			if not bool(other.get("is_destroyed")) and other_type == "BARREL_EXPLOSIVE" and int(other.get("barrel_phase")) == 0:
				var rem_hp: float = float(other.get("hp")) if other.get("hp") != null else other_hp
				if rem_hp <= other_max_hp * 0.65 and other.has_method("ignite"):
					other.call("ignite")

	if dmg_to_self >= 1.0 and not indestructible and not is_destroyed:
		take_damage(dmg_to_self, -imp_vec * 0.5)


func _check_prop_impacts(prev_pos: Vector2, at_pos: Vector2) -> void:
	if match_world == null or not is_instance_valid(match_world):
		return
	var props_var: Variant = match_world.get("props")
	if typeof(props_var) != TYPE_ARRAY:
		return

	var obb_half_h: float = maxf(height * 0.5, get_obb_extents_at(rotation).y * 0.5)
	var prev_bottom: float = prev_pos.y + height * 0.5
	var next_bottom: float = at_pos.y + obb_half_h
	var my_left: float = minf(prev_pos.x, at_pos.x) - width * 0.5
	var my_right: float = maxf(prev_pos.x, at_pos.x) + width * 0.5
	var my_top: float = minf(prev_pos.y, at_pos.y) - height * 0.5

	for p_var: Variant in props_var as Array:
		if not is_instance_valid(p_var) or not (p_var is Node2D) or p_var == self:
			continue
		var other: Node2D = p_var as Node2D
		if bool(other.get("is_destroyed")) or bool(other.get("is_hanging_holder")):
			continue
		var other_type: String = str(other.get("prop_type")).to_upper()
		if other_type == "LAMP_1":
			continue
		if bool(other.get("is_hanging_crate")) and not bool(other.get("is_hanging_released")):
			continue
		var oid: int = other.get_instance_id()
		if _prop_impact_cooldowns.has(oid):
			continue

		var ow: float = float(other.get("width")) if other.get("width") != null else 14.0
		var oh: float = float(other.get("height")) if other.get("height") != null else 14.0
		var o_left: float = other.global_position.x - ow * 0.5
		var o_right: float = other.global_position.x + ow * 0.5
		var other_top: float = other.global_position.y - oh * 0.5
		var other_bottom: float = other.global_position.y + oh * 0.5
		var overlap_x: float = minf(my_right, o_right) - maxf(my_left, o_left)
		if overlap_x < 1.8:
			continue

		var ovel: Vector2 = other.get("velocity") as Vector2 if other.get("velocity") != null else Vector2.ZERO
		var omass: float = maxf(0.4, float(other.get("mass")) if other.get("mass") != null else 1.0)

		# 1. Vertical top-down crush impact
		if not on_ground and velocity.y > 0.4 and prev_pos.y < other.global_position.y - 2.0 and prev_bottom <= other_top + oh * 0.65 + 2.0 and next_bottom >= other_top - 0.5:
			var v_rel_y: float = velocity.y - ovel.y
			var min_span: float = maxf(1.0, minf(width, ow))
			if v_rel_y > 2.15:
				_resolve_prop_collision_damage(other, v_rel_y, true, overlap_x / min_span)
				if is_destroyed:
					return
				if bool(other.get("is_destroyed")) or int(other.get("barrel_phase")) > 0:
					# Retain downward momentum after crushing/detonating the underlying prop
					velocity.y = maxf(1.5, velocity.y * (mass / (mass + 0.22 * omass)))
					continue
			# If `other` survived and `self` is much heavier striking off-center, shove/tip `other` aside
			var is_off_center_hit: bool = (overlap_x < min_span * 0.85 or absf(other.global_position.x - at_pos.x) > ow * 0.30)
			if not bool(other.get("is_destroyed")) and not bool(other.get("kinematic")) and mass >= omass * 1.65 and is_off_center_hit:
				var shove_dir: float = 1.0 if other.global_position.x >= at_pos.x else -1.0
				var shove_vx: float = shove_dir * clampf(maxf(v_rel_y, 1.5) * 0.40 * (mass / (mass + omass)), 0.85, 2.5)
				other.set("velocity", Vector2(shove_vx, ovel.y))
				if other.get("angular_velocity") != null:
					other.set("angular_velocity", shove_dir * 0.14)
				if other.has_method("wake_up"):
					other.call("wake_up")
		# 2. High-speed horizontal smash against non-solid fragile props (CHAIR, COMP, PAPER)
		elif not bool(other.get("has_solid_hitbox")) and absf(velocity.x) > 2.40 and next_bottom > other_top + 2.0 and my_top < other_bottom - 2.0:
			var dir_to_other: float = 1.0 if other.global_position.x >= prev_pos.x else -1.0
			var v_rel_x: float = (velocity.x - ovel.x) * dir_to_other
			if v_rel_x > 2.40:
				_resolve_prop_collision_damage(other, v_rel_x, false, 1.0)
				if is_destroyed:
					return
				if not bool(other.get("is_destroyed")) and not bool(other.get("kinematic")):
					other.set("velocity", Vector2(dir_to_other * clampf(v_rel_x * 0.55, 1.0, 2.8), -1.2))
					if other.get("angular_velocity") != null:
						other.set("angular_velocity", dir_to_other * 0.16)


func release_hanging_crate() -> void:
	if not is_hanging_crate or is_hanging_released:
		return
	wake_up()
	_wake_nearby_props()
	is_hanging_released = true
	kinematic = false
	on_ground = false
	_settling_frames = 0.0
	var tang_vx: float = clampf(cos(_hang_angle) * _hang_ang_vel * maxf(24.0, _hang_rope_len), -3.5, 3.5)
	var tang_vy: float = maxf(1.5, -sin(_hang_angle) * _hang_ang_vel * maxf(24.0, _hang_rope_len) + 1.5)
	velocity = Vector2(tang_vx, tang_vy)
	angular_velocity = -_hang_ang_vel * 0.5
	_target_rest_rot = 0.0
	crushed_fighter_ids.clear()
	crushed_prop_ids.clear()
	queue_redraw()


func apply_bullet_hit(
	damage: float,
	pushback_or_vel: Variant = 15.0,
	dir_or_owner: Variant = 1,
	hit_pos: Vector2 = Vector2.ZERO,
	bullet_strength: int = -1
) -> bool:
	if is_destroyed:
		return false
	wake_up()
	_wake_nearby_props()
	var pushback: float = 15.0
	var dir_x: int = 1
	if typeof(pushback_or_vel) == TYPE_VECTOR2:
		var vv: Vector2 = pushback_or_vel as Vector2
		pushback = clampf(vv.length() * 0.6, 10.0, 45.0)
		dir_x = 1 if vv.x >= 0.0 else -1
	else:
		pushback = float(pushback_or_vel)
		if typeof(dir_or_owner) == TYPE_INT or typeof(dir_or_owner) == TYPE_FLOAT:
			dir_x = 1 if float(dir_or_owner) >= 0.0 else -1
	var fdir: float = 1.0 if dir_x >= 0 else -1.0

	if is_parachute_crate:
		_open_supply_crate()
		return true

	if is_hanging_crate and not is_hanging_released:
		apply_pendulum_impulse(fdir * clampf(pushback * 0.0024, 0.025, 0.14))
	elif not kinematic and cover_level == 0:
		# AS3 Projectiles.as:48-138 & ProjectilesUpdater.as:601-610:
		# Bullets apply a small horizontal impulse scaled by 1/mass without popping grounded props into the air,
		# and cover tables (cover_level > 0) are not pushed by bullets!
		var min_b_imp: float = 0.04 if mass >= 3.0 else 0.15
		var bullet_impulse: float = clampf((pushback * 0.025) / maxf(0.65, mass), min_b_imp, 0.85)
		velocity.x = clampf(velocity.x + fdir * bullet_impulse, -2.2, 2.2)
		if not is_hanging_crate:
			angular_velocity += fdir * (0.004 if mass >= 3.0 else 0.03)

	if _settling_frames <= 0.0:
		if prop_material == "Metal":
			MapLoaderScript.play_sfx_at("bullet_hitmetal", global_position)
		elif prop_material == "Glass":
			MapLoaderScript.play_sfx_at("glass", global_position)
		else:
			MapLoaderScript.play_sfx_at("wood_impact", global_position)

	var impact_pt: Vector2 = hit_pos if hit_pos != Vector2.ZERO else global_position + Vector2(0.0, -height * 0.5)
	if match_world != null and is_instance_valid(match_world):
		var fhs: Variant = match_world.get("fire_hazard_system")
		if fhs != null and is_instance_valid(fhs):
			if fhs.has_method("spawn_hit_sparks"):
				fhs.call("spawn_hit_sparks", impact_pt, false)
			if fhs.has_method("spawn_prop_debris"):
				fhs.call("spawn_prop_debris", prop_type, impact_pt, Vector2(fdir * 1.8, -2.0), 2)

	var eff_dmg: float = damage * bullet_resistance
	if prop_type == "GASCAN":
		# AS3 MapPremadeItems.as:1654: 1 bullet hit immediately detonates GASCAN!
		_trigger_gascan_explosion()
		return true
	if prop_type == "BARREL_EXPLOSIVE":
		take_damage(eff_dmg, Vector2(fdir * 2.5, -2.0))
		if not is_destroyed and barrel_phase == 0 and hp <= max_hp * 0.65:
			ignite()
		return true

	# AS3 ProjectilesUpdater.as:606-615: if !Indestructible and prop.Strength <= bullet.StrengthLeft -> ForceDestruction() in 1 shot!
	var eff_b_strength: int = bullet_strength
	if eff_b_strength < 0:
		if damage >= 28.0:
			eff_b_strength = 30
		elif damage >= 22.0:
			eff_b_strength = 15
		else:
			eff_b_strength = 5
	if not indestructible and barrel_phase == 0 and prop_strength <= eff_b_strength:
		if not kinematic and cover_level == 0:
			velocity.x = clampf(velocity.x + fdir * 0.45, -2.8, 2.8)
		hp = 0.0
		_destroy_prop(Vector2(fdir * 3.2, -2.2))
		return true

	take_damage(eff_dmg, Vector2(fdir * 2.5, -2.0))
	return true


func apply_melee_hit(damage: float, dir_x: int, is_kick: bool = false, _weapon_id: String = "FISTS", attacker: Node2D = null) -> void:
	if is_destroyed:
		return
	wake_up()
	_wake_nearby_props()
	var fdir: float = 1.0 if dir_x >= 0 else -1.0
	last_attacker = attacker
	_attacker_ignore_frames = 24.0
	if is_parachute_crate:
		_open_supply_crate()
		return
	# AS3 MapPremadeItems.as:1556-1574 & Player.as:5727: CRATE_HANGING_HOLDER and non-kickable fixed props (STATUE, LAMP_1)
	# are 100% immune to melee punches, kicks, and melee weapons — only gunfire or explosions can break CRATE_HANGING_HOLDER!
	if is_hanging_holder or prop_type == "CRATE_HANGING_HOLDER" or not kickable:
		if _settling_frames <= 0.0:
			MapLoaderScript.play_sfx_at("metal_impact" if prop_material == "Metal" else "wood_impact", global_position)
		return

	if is_hanging_crate and not is_hanging_released:
		var rope_l: float = maxf(28.0, _hang_rope_len)
		var ang_imp: float = (fdir * (2.6 if is_kick else 1.3)) / (maxf(2.0, mass) * rope_l)
		apply_pendulum_impulse(ang_imp)
	elif not kinematic and kick_power > 0.0:
		# AS3 Player.as:5731-5762 (Kick) & MapPremadeItems.as per-prop KickPower / KickWeightCalculation:
		# 1. Primary Center-of-Mass impulse + eccentric upward foot lift at (x + dir*4, y - 4) launches light/medium
		#    props (BARREL, BARREL_EXPLOSIVE, TRASHCAN, GASCAN, CRATE, CHAIR, TABLE_SMALL) into a genuine airborne
		#    parabolic hop proportional to KickPower and 1/mass (matching Image 1 of original Superfighters Y8).
		# 2. Heavy props (FILECAB, TABLE, DESK, POOL_TABLE, CRATE_HANGING) scale inversely with mass so heavy furniture
		#    shifts/rocks modestly without exceeding horizontal gibb thresholds.
		var push_x: float = 1.0
		var push_y: float = -1.0
		if is_kick:
			if can_gibb or mass >= 3.0:
				# Super-heavy props (CRATE_HANGING mass=3.8, DESK mass=3.2, POOL_TABLE mass=4.6) nudge along floor (< 1.6 gibb threshold)
				push_x = clampf(kick_power * (0.48 + 0.55 / maxf(0.5, mass)), 0.32, 0.72)
				push_y = -0.35 if mass <= 3.5 else -0.22
			elif kick_weight_calculation or kick_power >= 0.85:
				# Light & medium kickable props (CRATE, BARREL, BARREL_EXPLOSIVE, GASCAN, TRASHCAN, CHAIR, TABLE, TABLE_SMALL, COMP, PAPER):
				# Authentic Box2D CoM launch + eccentric foot lift proportional to kick_power / mass!
				push_x = clampf(kick_power * (1.12 + 0.68 / maxf(0.55, mass)), 1.25, 2.35)
				push_y = -clampf(1.52 + 0.62 * kick_power / maxf(0.70, sqrt(mass)), 1.75, 2.35)
			else:
				# Heavy tall furniture (FILECAB mass=2.25, kick_power=0.80)
				push_x = clampf(kick_power * (0.85 + 0.65 / maxf(0.5, mass)), 0.55, 1.35)
				push_y = -clampf(0.55 + 0.75 * kick_power, 0.55, 1.25)
		else:
			if can_gibb or mass >= 3.0:
				push_x = clampf(kick_power * 0.42, 0.18, 0.45)
				push_y = 0.0
			else:
				push_x = clampf(kick_power * (0.45 + 0.22 / maxf(0.55, mass)), 0.32, 0.95)
				push_y = -0.60 if mass <= 1.25 else -0.25

		var attacker_on_top: bool = (
			attacker != null
			and is_instance_valid(attacker)
			and absf(attacker.global_position.y - (global_position.y - height * 0.5)) <= 3.5
			and absf(attacker.global_position.x - global_position.x) <= width * 0.5 + 4.5
		)
		if attacker_on_top and is_kick:
			# AS3 Player.as:5746-5762: when kicking a prop out from under the fighter's own feet, lever arm dx ~ 0 so the prop slides/hops out smoothly!
			push_x *= 1.05
			push_y = -0.45

		velocity = Vector2(fdir * push_x, push_y)
		if _can_tip_horizontally():
			# Housner Inverted-Pendulum Corner-Rocking & Toppling Impulse (AS3 Player.as:5750-5762):
			# - Light punches rock tall props to ~13 deg (1 punch) or ~28 deg (2 punches) within the sub-critical balance regime (|theta| < theta_crit),
			#   allowing gravity's restoring torque to pull them back upright to 0 deg! Only 3 rapid consecutive punches cross theta_crit.
			# - Kicking a tall slender prop (BARREL, BARREL_EXPLOSIVE, GASCAN, CHAIR, COMP: base_height >= base_width * 1.2) launches it into an airborne
			#   arc with a natural ~12-22 deg mid-air tilt (matching Image 1) before crossing theta_crit (~36.25 deg) and rolling onto its side at +-90 deg!
			# - Kicking a heavy/wide-based prop (FILECAB mass=2.25) imparts ~0.118 rad/tick, rocking it to ~20 deg and falling back upright
			#   on 1 kick, and only toppling on a 2nd consecutive kick while tilted!
			if attacker_on_top:
				angular_velocity = fdir * 0.05
			elif _is_tipped_on_side():
				var side_sign: float = signf(rotation) if absf(rotation) > 0.01 else fdir
				var side_rock: float = (0.075 if is_kick else 0.032) / maxf(sqrt(mass), 0.75)
				angular_velocity = clampf(angular_velocity - side_sign * side_rock, -0.14, 0.14)
			elif base_height > base_width:
				var rot_imp: float = 0.080
				if is_kick:
					if mass >= 2.0 or base_height < base_width * 1.20:
						rot_imp = 0.118
					else:
						rot_imp = 0.178
				if signf(angular_velocity) == fdir or signf(rotation) == fdir:
					angular_velocity = clampf(angular_velocity + fdir * rot_imp * 0.88, -0.22, 0.22)
				else:
					angular_velocity = fdir * rot_imp
			else:
				# Square/wide props (e.g. CRATE 15x15) rock gently on their corner and self-right back to 0 deg on flat ground
				angular_velocity = fdir * (0.095 if is_kick else 0.045)
		else:
			angular_velocity = fdir * (0.06 if is_kick else 0.03)
		if push_y < -0.1:
			on_ground = false
			_settling_frames = 0.0
		crushed_fighter_ids.clear()
		crushed_prop_ids.clear()
		if attacker != null and is_instance_valid(attacker):
			crushed_fighter_ids[attacker.get_instance_id()] = true

	# In AS3 (MapPremadeItems.as:1590,1661,1688 & BodyData.as:224-228,618), CRATE_HANGING, BARREL_EXPLOSIVE, GASCAN, BARREL,
	# TRASHCAN, FILECAB, DESK, COMP, and PAPER have _resistance_impact = 0 (melee punches/kicks ONLY push them, never explode/break!)
	var zero_impact_props: Array[String] = [
		"CRATE_HANGING_HOLDER", "CRATE_HANGING", "BARREL_EXPLOSIVE", "GASCAN", "BARREL",
		"TRASHCAN", "FILECAB", "DESK", "DESK_1", "POOL_TABLE", "COMP", "COMP_SCREEN", "PAPER"
	]
	if prop_type in zero_impact_props or indestructible:
		if _settling_frames <= 0.0:
			MapLoaderScript.play_sfx_at("wood_impact" if prop_material == "Wood" else "metal_impact", global_position)
		return

	if _settling_frames <= 0.0:
		MapLoaderScript.play_sfx_at("wood_impact", global_position)
	_spawn_debris_burst(global_position + Vector2(0.0, -height * 0.5), Vector2(fdir * 2.0, -2.0), 2)
	var wid_upper: String = _weapon_id.to_upper().strip_edges()
	var is_unarmed_strike: bool = is_kick or wid_upper.is_empty() or wid_upper == "FISTS"
	# Bare-handed punches/kicks deal light structural damage (3.5-4.0 HP, ~11 hits to break a crate) vs heavy melee weapons (10-18 HP)
	var final_dmg: float = (4.0 if is_kick else minf(damage, 3.5)) if is_unarmed_strike else maxf(damage * 1.25, 10.0)
	take_damage(final_dmg, Vector2(fdir * 3.0, -2.0))


var _ignoring_self_explosion: bool = false


func apply_explosion_hit(angle_rad: float, power: float, damage: float) -> void:
	if is_destroyed or _ignoring_self_explosion:
		return
	wake_up()
	_wake_nearby_props()
	if is_parachute_crate:
		_open_supply_crate()
		return
	var eff_mass: float = sqrt(maxf(0.65, mass)) if mass >= 2.5 else maxf(0.65, mass)
	var blast_speed: float = clampf((power * 0.95) / eff_mass, 1.2, 4.8)
	var impulse: Vector2 = Vector2(cos(angle_rad), sin(angle_rad)) * blast_speed
	if impulse.y > -1.1:
		impulse.y = clampf(-2.3 / maxf(0.75, eff_mass * 0.75), -2.5, -1.1)
	if is_hanging_crate and not is_hanging_released:
		var swing_dir: float = 1.0 if cos(angle_rad) >= -0.01 else -1.0
		var lat_factor: float = maxf(absf(cos(angle_rad)), 0.55)
		var p_swing: float = clampf(lat_factor * clampf(power, 2.0, 7.5) * 0.038, 0.08, 0.28)
		apply_pendulum_impulse(swing_dir * p_swing)
	elif not kinematic:
		if mass >= 3.0 and not on_ground and velocity.y > 0.8 and sin(angle_rad) < -0.20:
			# Downward Momentum Shielding: a heavy falling prop (e.g. 3.8t CRATE_HANGING) crushing an explosive barrel
			# underneath its base absorbs the upward shockwave and continues descending to the floor!
			velocity.y = maxf(1.5, velocity.y * 0.72)
			velocity.x = clampf(velocity.x + cos(angle_rad) * 0.12, -0.5, 0.5)
			angular_velocity = clampf(angular_velocity * 0.5, -0.05, 0.05)
		else:
			velocity = impulse
			angular_velocity = signf(impulse.x) * 0.16
			on_ground = false
		crushed_fighter_ids.clear()
		crushed_prop_ids.clear()

	if prop_type == "BARREL_EXPLOSIVE" and barrel_phase == 0:
		_trigger_barrel_phase_1_explosion(impulse)
		return
	if prop_type == "GASCAN":
		_trigger_gascan_explosion()
		return

	take_damage(damage * explosion_resistance, impulse)


func add_fire_heat(amount: float) -> void:
	if is_destroyed or is_burning or (not can_burn and barrel_phase == 0):
		return
	wake_up()
	_fire_heat += amount
	if _fire_heat >= 15.0:
		ignite()


func ignite() -> void:
	if is_destroyed or (not can_burn and barrel_phase == 0):
		return
	wake_up()
	_fire_heat = 15.0
	is_burning = true
	queue_redraw()


func apply_fall_impact_damage(damage: float, impulse: Vector2 = Vector2.ZERO, attacker: Node2D = null) -> bool:
	if is_destroyed or is_hanging_holder or prop_type == "CRATE_HANGING_HOLDER" or not kickable or indestructible:
		return false
	wake_up()
	_wake_nearby_props()
	last_attacker = attacker
	_attacker_ignore_frames = 18.0
	if is_parachute_crate:
		_open_supply_crate()
		return true
	if not kinematic and impulse != Vector2.ZERO:
		velocity.x += clampf(impulse.x * 0.35 / maxf(0.5, mass), -2.5, 2.5)
		angular_velocity += signf(impulse.x) * 0.08
	if _settling_frames <= 0.0:
		if prop_material == "Metal":
			MapLoaderScript.play_sfx_at("metal_impact", global_position)
		else:
			MapLoaderScript.play_sfx_at("wood_impact", global_position)
	_spawn_debris_burst(global_position + Vector2(0.0, -height * 0.5), Vector2(impulse.x * 0.5, -1.8), 2)
	var eff_fall_dmg: float = damage * (1.2 if player_fragile else 0.55)
	take_damage(eff_fall_dmg, impulse)
	return is_destroyed


func take_damage(amount: float, impulse: Vector2 = Vector2.ZERO) -> void:
	if is_destroyed or _ignoring_self_explosion or indestructible:
		return
	wake_up()
	if is_parachute_crate and amount > 0.0:
		_open_supply_crate()
		return
	hp -= amount
	if hp > 0.0:
		if amount >= 10.0:
			_impact_shudder_frames = 5.0
		_update_damaged_visual(impulse.x)
		_apply_sprite_visual_transform()
		queue_redraw()
		return
	if prop_type == "BARREL_EXPLOSIVE" and barrel_phase == 0:
		_trigger_barrel_phase_1_explosion(impulse)
	elif barrel_phase == 1:
		_trigger_barrel_phase_2_explosion()
	elif prop_type == "GASCAN":
		_trigger_gascan_explosion()
	else:
		_destroy_prop(impulse)


func apply_damage(amount: float, impulse: Vector2 = Vector2.ZERO) -> void:
	if not kinematic and impulse != Vector2.ZERO:
		velocity += impulse / maxf(0.6, mass)
		on_ground = false
	take_damage(amount, impulse)


func apply_kick_impulse(impulse: Vector2, _attacker: Node2D = null) -> void:
	var dir_x: int = 1 if impulse.x >= 0.0 else -1
	apply_melee_hit(4.0, dir_x, true)


func apply_explosion_damage(damage: float, impulse: Vector2 = Vector2.ZERO, _source: Node2D = null) -> void:
	var ang: float = impulse.angle() if impulse.length_squared() > 0.001 else -PI * 0.5
	var pwr: float = clampf(impulse.length() * 0.5, 2.5, 7.0)
	apply_explosion_hit(ang, pwr, damage)


func _trigger_explosive_prop_hit(impulse: Vector2) -> void:
	if prop_type == "BARREL_EXPLOSIVE" and barrel_phase == 0:
		_trigger_barrel_phase_1_explosion(impulse)
	elif prop_type == "GASCAN":
		_trigger_gascan_explosion()
	else:
		_destroy_prop(impulse)


func _trigger_barrel_catastrophic_crush_explosion() -> void:
	if is_destroyed:
		return
	var blast_pos: Vector2 = global_position
	barrel_phase = 2
	hp = 0.0
	is_destroyed = true
	visible = false
	_wake_nearby_props()
	_ignoring_self_explosion = true
	_notify_explosion_and_fire(blast_pos, 38.0, 24.0, 5.0, "BARREL_EXPLOSIVE", 16)
	_ignoring_self_explosion = false
	_spawn_debris_burst(blast_pos + Vector2(0.0, -height * 0.5), Vector2(0.0, -3.2), 6)


func _trigger_barrel_phase_1_explosion(_impulse: Vector2 = Vector2.ZERO) -> void:
	if barrel_phase != 0 or is_destroyed:
		return
	var blast_pos: Vector2 = global_position
	barrel_phase = 1
	prop_type = "BARREL_WRECK"

	_ignoring_self_explosion = true
	_notify_explosion_and_fire(blast_pos, 33.0, 20.0, 5.0, "BARREL_EXPLOSIVE", 14)
	_ignoring_self_explosion = false
	_spawn_debris_burst(blast_pos + Vector2(0.0, -height * 0.5), Vector2(0.0, -3.0), 4)

	# Set BARREL_WRECK state after self-explosion notification so own blast does not overwrite hp/velocity
	is_destroyed = false
	visible = true
	hp = 50.0
	max_hp = 50.0
	is_burning = true
	burn_timer = 0.0
	kinematic = false
	on_ground = false

	# Launch charred BARREL_WRECK into the air!
	var rx: float = randf_range(-5.0, 5.0)
	if absf(rx) < 1.2:
		rx = 2.4
	velocity = Vector2(rx, -4.5)
	angular_velocity = signf(rx) * 0.22

	if _sprite != null and is_instance_valid(_sprite):
		var reg: Node = MapLoaderScript.get_registry()
		var dtex: Texture2D = reg.call("load_cached_texture", "res://assets/sprites/props/obj_barrel_wreck.png") as Texture2D
		if dtex != null:
			_sprite.texture = dtex
		_sprite.modulate = Color(0.55, 0.48, 0.45, 1.0)
	queue_redraw()


func _trigger_barrel_phase_2_explosion() -> void:
	if is_destroyed:
		return
	var blast_pos: Vector2 = global_position
	barrel_phase = 2
	is_destroyed = true
	visible = false
	_wake_nearby_props()

	_notify_explosion_and_fire(blast_pos, 33.0, 20.0, 4.8, "BARREL_WRECK", 14)
	_spawn_debris_burst(blast_pos + Vector2(0.0, -height * 0.5), Vector2(0.0, -3.2), 5)


func _trigger_gascan_explosion() -> void:
	if is_destroyed:
		return
	var blast_pos: Vector2 = global_position
	is_destroyed = true
	visible = false
	_wake_nearby_props()

	# AS3 MapPremadeItems.as:1668-1672 & Fires.as:517-523: GASCAN only bursts into 18 fire particles (TriggerFireAt("GASCAN")), NO explosion shockwave!
	_spawn_debris_burst(blast_pos + Vector2(0.0, -height * 0.5), Vector2(0.0, -2.8), 4)
	if match_world != null and is_instance_valid(match_world):
		var fhs: Variant = match_world.get("fire_hazard_system")
		if fhs != null and is_instance_valid(fhs):
			if fhs.has_method("trigger_fire_burst"):
				fhs.call("trigger_fire_burst", "GASCAN", blast_pos, 18)


func _notify_explosion_and_fire(
	world_pos: Vector2,
	radius: float,
	dmg: float,
	power: float,
	burst_type: String,
	fire_count: int
) -> void:
	if match_world == null or not is_instance_valid(match_world):
		return
	var fhs: Variant = match_world.get("fire_hazard_system")
	if fhs != null and is_instance_valid(fhs):
		if fhs.has_method("trigger_explosion"):
			fhs.call("trigger_explosion", world_pos, radius, dmg, power, null)
		if fhs.has_method("trigger_fire_burst"):
			fhs.call("trigger_fire_burst", burst_type, world_pos, fire_count)
	var cam: Variant = match_world.get("dynamic_camera")
	if cam != null and is_instance_valid(cam) and cam.has_method("add_screen_shake"):
		cam.call("add_screen_shake", 5.5)


func _open_supply_crate() -> void:
	if is_destroyed:
		return
	is_destroyed = true
	visible = false
	MapLoaderScript.play_sfx_at("bustwood", global_position)
	_spawn_debris_burst(global_position + Vector2(0.0, -height * 0.5), Vector2(0.0, -2.5), 5)
	if match_world != null and is_instance_valid(match_world) and match_world.has_method("spawn_weapon_pickup"):
		var wid: String = contained_weapon_id if not contained_weapon_id.is_empty() else SUPPLY_WEAPON_POOL[randi() % SUPPLY_WEAPON_POOL.size()]
		match_world.call("spawn_weapon_pickup", wid, global_position, -999, true)


func _destroy_prop(_impulse: Vector2) -> void:
	if is_destroyed:
		return
	var was_burning: bool = is_burning
	is_destroyed = true
	visible = false
	_wake_nearby_props()

	_spawn_debris_burst(global_position + Vector2(0.0, -height * 0.5), Vector2(velocity.x, -2.5), 6)

	# AS3 Fires.as:227-244: destroying a burning prop scatters flaming debris embers that can spread fire nearby!
	if was_burning and match_world != null and is_instance_valid(match_world):
		var fhs_b: Variant = match_world.get("fire_hazard_system")
		if fhs_b != null and is_instance_valid(fhs_b) and fhs_b.has_method("trigger_fire_burst"):
			fhs_b.call("trigger_fire_burst", "PROP_FIRE", global_position, 4)

	if is_hanging_holder and attached_hanging_crate != null and is_instance_valid(attached_hanging_crate):
		if attached_hanging_crate.has_method("release_hanging_crate"):
			attached_hanging_crate.call("release_hanging_crate")

	if is_parachute_crate or (is_hanging_crate and not contained_weapon_id.is_empty()):
		if match_world != null and is_instance_valid(match_world) and match_world.has_method("spawn_weapon_pickup"):
			var wid: String = contained_weapon_id if not contained_weapon_id.is_empty() else SUPPLY_WEAPON_POOL[randi() % SUPPLY_WEAPON_POOL.size()]
			match_world.call("spawn_weapon_pickup", wid, global_position, -999, true)

	if prop_material == "Glass":
		MapLoaderScript.play_sfx_at("glass", global_position)
	elif prop_material == "Metal":
		MapLoaderScript.play_sfx_at("bullet_hitmetal", global_position)
	else:
		MapLoaderScript.play_sfx_at("bustwood", global_position)


func _draw() -> void:
	if is_destroyed:
		return

	# Draw Stage 2 structural stress-creases / buckled waist rim on heavily dented steel barrel
	if prop_type == "BARREL" and barrel_phase == 0 and _damage_visual_stage >= 2:
		var crease_col: Color = Color(0.14, 0.15, 0.17, 0.88)
		var hi_col: Color = Color(0.62, 0.64, 0.68, 0.55)
		draw_line(Vector2(-width * 0.36, -1.5), Vector2(width * 0.12, 0.8), crease_col, 1.1)
		draw_line(Vector2(-width * 0.10, 2.2), Vector2(width * 0.38, -0.8), crease_col, 1.1)
		draw_line(Vector2(-width * 0.32, -2.4), Vector2(width * 0.10, -0.2), hi_col, 0.9)

	# Draw suspension rope for hanging crate holder (connects from top of holder bracket to ceiling anchor)
	if is_hanging_holder:
		var anchor_w: Vector2 = _hang_anchor if _hang_anchor != Vector2.ZERO else Vector2(global_position.x, ceiling_anchor_y)
		var top_attach: Vector2 = Vector2(0.0, -height * 0.5)
		var top_offset: Vector2 = to_local(anchor_w)
		draw_line(top_attach, top_offset, Color(0.28, 0.26, 0.24, 0.95), 1.5)

	# Draw parachute canopy above sky supply crate
	if is_parachute_crate and parachute_attached and not on_ground:
		var canopy_center: Vector2 = Vector2(0.0, -22.0)
		draw_line(Vector2(-6.0, -height * 0.5), canopy_center + Vector2(-12.0, 2.0), Color(0.85, 0.85, 0.85, 0.85), 1.0)
		draw_line(Vector2(6.0, -height * 0.5), canopy_center + Vector2(12.0, 2.0), Color(0.85, 0.85, 0.85, 0.85), 1.0)
		var dome_pts: PackedVector2Array = PackedVector2Array([
			canopy_center + Vector2(-14.0, 2.0),
			canopy_center + Vector2(-9.0, -6.0),
			canopy_center + Vector2(0.0, -9.0),
			canopy_center + Vector2(9.0, -6.0),
			canopy_center + Vector2(14.0, 2.0),
		])
		draw_colored_polygon(dome_pts, Color(0.88, 0.82, 0.62, 0.92))

	# Draw authentic multi-frame flame sprite if burning (e.g. BARREL_WRECK phase 1)
	if is_burning and not _tex_fire_frames.is_empty():
		var f_idx: int = int(_fire_anim_frame) % _tex_fire_frames.size()
		var ftex: Texture2D = _tex_fire_frames[f_idx]
		if ftex != null:
			draw_texture(ftex, Vector2(-ftex.get_width() * 0.5, -height * 0.5 - ftex.get_height() * 0.65))

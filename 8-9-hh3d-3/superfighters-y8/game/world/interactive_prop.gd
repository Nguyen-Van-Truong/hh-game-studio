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
var player_bounce: bool = false
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
var _tip_accum: float = 0.0
var _ledge_overhang_dir: float = 0.0
var on_ground: bool = false
var is_destroyed: bool = false

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

var is_parachute_crate: bool = false
var parachute_attached: bool = false
var contained_weapon_id: String = ""
var _parachute_sway_time: float = 0.0

var _settling_frames: float = 18.0
var _is_damaged_visual: bool = false
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
	crushed_fighter_ids.clear()

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
		hp = 110.0
		max_hp = 110.0
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

	if prop_type in ["BARREL", "TRASHCAN", "FILECAB", "DESK", "DESK_1", "POOL_TABLE"]:
		explosion_resistance = 0.50
	elif prop_type == "CRATE_HANGING":
		explosion_resistance = 0.0

	player_fragile = prop_type in ["CRATE", "SUPPLY_CRATE", "TABLE", "TABLE_SMALL", "CHAIR", "CHAIR_R"]
	player_bounce = prop_type in ["BARREL", "BARREL_EXPLOSIVE", "TRASHCAN", "FILECAB", "DESK", "DESK_1", "POOL_TABLE", "COMFY_CHAIR"]

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
	_tip_accum = 0.0
	_ledge_overhang_dir = 0.0
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
	_tip_accum = 0.0
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
	return absf(rotation) >= crit or absf(sin(_target_rest_rot)) > 0.707


func _sync_rotated_dimensions(keep_bottom_y: float = INF) -> void:
	if base_width <= 0.0 or base_height <= 0.0:
		return
	var is_sideways: bool = _is_tipped_on_side()
	var new_w: float = base_height if is_sideways else base_width
	var new_h: float = base_width if is_sideways else base_height
	if not is_equal_approx(width, new_w) or not is_equal_approx(height, new_h):
		var old_w: float = width
		var old_h: float = height
		width = new_w
		height = new_h
		if keep_bottom_y < INF:
			global_position.y = keep_bottom_y - height * 0.5
		elif on_ground:
			global_position.y += (old_h - height) * 0.5
		if new_w > old_w and map_loader != null and is_instance_valid(map_loader):
			global_position.x = _clamp_x_against_walls(global_position.x, global_position.y, global_position.x)


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
			angular_velocity = clampf(angular_velocity * pow(0.96, step_24hz), -0.18, 0.18)
			rotation = clampf(rotation + angular_velocity * step_24hz, -0.68, 0.68)
		else:
			if absf(rotation) > 0.0005 or absf(angular_velocity) > 0.0005:
				var prev_rot_w: float = rotation
				var restore_w: float = -signf(rotation) * (0.028 + absf(rotation) * 0.18) * step_24hz
				angular_velocity = clampf((angular_velocity + restore_w) * pow(0.82, step_24hz), -0.18, 0.18)
				rotation += angular_velocity * step_24hz
				if prev_rot_w * rotation <= 0.0 or (absf(rotation) < 0.015 and absf(angular_velocity) < 0.02):
					rotation = 0.0
					angular_velocity = 0.0
			else:
				rotation = 0.0
				angular_velocity = 0.0
		if _sprite != null:
			if (on_ground or absf(_ledge_overhang_dir) > 0.01) and absf(rotation) > 0.001:
				var delta_w: float = minf(absf(rotation), 0.68)
				var lift_w: float = maxf(0.0, 0.5 * (height * cos(delta_w) + width * sin(delta_w) - height))
				_sprite.position = Vector2(0.0, -lift_w).rotated(-rotation)
			else:
				_sprite.position = Vector2.ZERO
		return

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
				_tip_accum = 0.0
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

	_sync_rotated_dimensions(support_y)

	# Exact geometric corner-pivot lift while rocking so the bottom support corner stays flush on the floor
	if _sprite != null:
		if on_ground and absf(rotation) > 0.001 and absf(absf(rotation) - half_pi) > 0.001:
			var delta_flat: float = minf(absf(rotation), absf(half_pi - absf(rotation)))
			var lift_y: float = maxf(
				0.0,
				0.5 * (height * cos(delta_flat) + width * sin(delta_flat) - height)
			)
			_sprite.position = Vector2(0.0, -lift_y).rotated(-rotation)
		else:
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
	return get_world_rect()


func _spawn_debris_burst(hit_pos: Vector2, hit_dir: Vector2, count: int) -> void:
	if match_world == null or not is_instance_valid(match_world):
		return
	var fhs: Variant = match_world.get("fire_hazard_system")
	if fhs != null and is_instance_valid(fhs) and fhs.has_method("spawn_prop_debris"):
		fhs.call("spawn_prop_debris", prop_type, hit_pos, hit_dir, count)


func _update_damaged_visual(_hit_dir_x: float = 1.0) -> void:
	if is_destroyed or hp <= 0.0 or hp >= max_hp * 0.65:
		return
	if _is_damaged_visual:
		return
	_is_damaged_visual = true
	_ensure_sprite()
	var reg: Node = MapLoaderScript.get_registry()

	if prop_type == "BARREL" and barrel_phase == 0:
		var dtex: Texture2D = reg.call("load_cached_texture", "res://assets/sprites/props/obj_barrel_dmg.png") as Texture2D
		if dtex != null:
			_sprite.texture = dtex
		_sprite.rotation_degrees = 0.0
		_sprite.modulate = Color(0.84, 0.82, 0.80, 1.0)
	elif prop_type == "BARREL_EXPLOSIVE" and barrel_phase == 0:
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


func _get_support_y_below(next_x: float, prev_bottom: float, next_bottom: float, check_span: bool = false) -> float:
	var best_y: float = INF
	var max_drop: float = maxf(10.0, next_bottom - prev_bottom + 8.0)
	if map_loader != null and is_instance_valid(map_loader) and map_loader.has_method("get_ground_y_below"):
		best_y = float(map_loader.call("get_ground_y_below", next_x, prev_bottom - 5.0, max_drop, true))

	# Also check resting on top of other grounded, non-destroyed solid props (using exact top-edge span ow * 0.5 + 2.0)
	if match_world != null and is_instance_valid(match_world):
		var props_var: Variant = match_world.get("props")
		if typeof(props_var) == TYPE_ARRAY:
			for p_var: Variant in props_var as Array:
				if not (p_var is Node2D) or not is_instance_valid(p_var) or p_var == self:
					continue
				var other: Node2D = p_var as Node2D
				var other_is_paper_support: bool = (prop_type == "PAPER" and str(other.get("prop_type")) == "PAPER")
				if bool(other.get("is_destroyed")) or bool(other.get("is_hanging_holder")) or (not bool(other.get("has_solid_hitbox")) and not other_is_paper_support):
					continue
				if not bool(other.get("on_ground")) and not bool(other.get("kinematic")):
					continue
				var ow: float = float(other.get("width")) if other.get("width") != null else 14.0
				var oh: float = float(other.get("height")) if other.get("height") != null else 14.0
				if absf(next_x - other.global_position.x) <= ow * 0.5 + 2.0:
					var other_top: float = other.global_position.y - oh * 0.5
					if other_top >= prev_bottom - 3.0 and other_top <= prev_bottom + max_drop and other_top < best_y:
						best_y = other_top

	# Only bridge across a gap when BOTH left and right ends have solid support (never when 1 side hangs over an abyss!)
	if check_span and best_y == INF and width >= 12.0:
		var span_dx: float = width * 0.30
		var left_y: float = _get_support_y_below(next_x - span_dx, prev_bottom, next_bottom, false)
		var right_y: float = _get_support_y_below(next_x + span_dx, prev_bottom, next_bottom, false)
		if left_y < INF and right_y < INF:
			best_y = minf(left_y, right_y)

	return best_y


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


func _clamp_x_against_walls(cand_x: float, at_y: float, from_x: float = INF) -> float:
	if map_loader == null or not is_instance_valid(map_loader):
		return cand_x
	var prev_x: float = global_position.x if from_x == INF else from_x
	var half_w: float = width * 0.5
	var half_h: float = height * 0.5
	var top_y: float = at_y - half_h + 2.0
	var bot_y: float = at_y + half_h - 2.0

	for sr: Rect2 in _get_solid_world_obstacles():
		if sr.size.y < 3.0 or sr.size.x < 1.0:
			continue
		if bot_y <= sr.position.y or top_y >= sr.end.y:
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
		if not (p_var is Node2D) or not is_instance_valid(p_var) or p_var == self:
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

	for sr: Rect2 in _get_solid_world_obstacles():
		if sr.size.y < 2.0 or right_x <= sr.position.x or left_x >= sr.end.x:
			continue
		if prev_top >= sr.end.y - 4.0 and cand_top < sr.end.y:
			cand_y = maxf(cand_y, sr.end.y + half_h)
			cand_top = cand_y - half_h

	if match_world != null and is_instance_valid(match_world):
		var props_var: Variant = match_world.get("props")
		if typeof(props_var) == TYPE_ARRAY:
			for p_var: Variant in props_var as Array:
				if not (p_var is Node2D) or not is_instance_valid(p_var) or p_var == self:
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


func step_prop(step_24hz: float) -> void:
	if is_destroyed:
		return

	if _settling_frames > 0.0:
		_settling_frames = maxf(0.0, _settling_frames - step_24hz)
	if _attacker_ignore_frames > 0.0:
		_attacker_ignore_frames = maxf(0.0, _attacker_ignore_frames - step_24hz)
		if _attacker_ignore_frames <= 0.0:
			last_attacker = null

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
	if on_ground and _tip_accum != 0.0:
		_tip_accum = move_toward(_tip_accum, 0.0, 0.04 * step_24hz)

	_ledge_overhang_dir = 0.0
	if on_ground and map_loader != null and is_instance_valid(map_loader):
		var cur_bottom: float = prev_pos.y + height * 0.5
		var center_sup: float = _get_support_y_below(prev_pos.x, cur_bottom, cur_bottom + 2.5, false)
		# Compensate for map_loader.get_ground_y_below's +-2.0px pad to test exact geometric overhang:
		# - right_com_sup / left_com_sup == INF means >50% of the prop's width hangs out in empty air (overhanging side is heavier!)
		# - right_inner_sup / left_inner_sup == INF means >42% of the prop's width hangs out past the ledge corner bevel.
		var right_com_sup: float = _get_support_y_below(prev_pos.x + 2.05, cur_bottom, cur_bottom + 3.0, false)
		var left_com_sup: float = _get_support_y_below(prev_pos.x - 2.05, cur_bottom, cur_bottom + 3.0, false)
		var right_inner_sup: float = _get_support_y_below(prev_pos.x + width * 0.08 + 2.05, cur_bottom, cur_bottom + 3.0, false)
		var left_inner_sup: float = _get_support_y_below(prev_pos.x - width * 0.08 - 2.05, cur_bottom, cur_bottom + 3.0, false)
		var left_tail_sup: float = _get_support_y_below(prev_pos.x - width * 0.42 + 2.0, cur_bottom, cur_bottom + 4.0, false)
		var right_tail_sup: float = _get_support_y_below(prev_pos.x + width * 0.42 - 2.0, cur_bottom, cur_bottom + 4.0, false)

		var overhang_right: bool = (
			(right_com_sup == INF and left_tail_sup < INF)
			or (_settling_frames <= 0.0 and right_inner_sup == INF and left_tail_sup < INF and (velocity.x > 0.02 or angular_velocity > 0.005 or rotation > 0.01))
		)
		var overhang_left: bool = (
			(left_com_sup == INF and right_tail_sup < INF)
			or (_settling_frames <= 0.0 and left_inner_sup == INF and right_tail_sup < INF and (velocity.x < -0.02 or angular_velocity < -0.005 or rotation < -0.01))
		)

		if overhang_right or overhang_left:
			var odir: float = 1.0 if overhang_right else -1.0
			_ledge_overhang_dir = odir
			var is_past_com: bool = (right_com_sup == INF) if odir > 0.0 else (left_com_sup == INF)
			var rot_accel: float = (0.135 if center_sup == INF else 0.105) if is_past_com else 0.070
			var slide_accel: float = (0.34 if is_past_com else 0.22) + 1.10 * absf(sin(rotation))
			if can_rot:
				angular_velocity += odir * rot_accel * step_24hz
			velocity.x += odir * slide_accel * step_24hz
			if is_past_com and absf(velocity.x) < 0.38:
				velocity.x = odir * 0.38
			if can_tip and absf(sin(_target_rest_rot)) < 0.5:
				_target_rest_rot = odir * (PI * 0.5)
			if is_past_com or absf(rotation) >= 0.12:
				on_ground = false
				var inner_tail_x: float = prev_pos.x - odir * maxf(1.0, width * 0.26 - 2.0)
				var inner_tail_sup: float = _get_support_y_below(inner_tail_x, cur_bottom, cur_bottom + 4.0, false)
				if inner_tail_sup < INF and absf(rotation) < 0.52:
					# Fulcrum-guided corner descent while the tail pivots off the ledge corner
					velocity.y = maxf(velocity.y, 0.35 + absf(sin(rotation)) * 2.2)
		elif center_sup == INF:
			on_ground = false
			if can_rot and absf(velocity.x) > 0.02:
				var fall_dir: float = signf(velocity.x)
				if can_tip and absf(sin(_target_rest_rot)) < 0.5:
					_target_rest_rot = fall_dir * (PI * 0.5)
				angular_velocity += fall_dir * 0.12 * step_24hz
		else:
			if velocity == Vector2.ZERO and is_zero_approx(angular_velocity) and absf(rotation - _target_rest_rot) <= 0.01 and not is_parachute_crate and _settling_frames <= 0.0:
				# Fast-path for stationary settled props well inside their platform support
				rotation = _target_rest_rot if can_tip else 0.0
				angular_velocity = 0.0
				_sync_rotated_dimensions(center_sup)
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
			velocity.x *= pow(ground_friction_24hz, step_24hz)
			if absf(velocity.x) < 0.03:
				velocity.x = 0.0
			_step_rotational_balance(step_24hz, prev_pos.y + height * 0.5)
			prev_pos.y = global_position.y

	var next_pos: Vector2 = prev_pos + velocity * step_24hz

	# 4. Break glass windows if flying through them (suppressed during initial settling frames)
	if _settling_frames <= 0.0 and map_loader != null and is_instance_valid(map_loader) and velocity.length() > 0.8:
		if map_loader.has_method("check_and_break_glass_segment"):
			map_loader.call("check_and_break_glass_segment", prev_pos, next_pos, velocity)

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
				if not (p_var is Node2D) or not is_instance_valid(p_var) or p_var == self:
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
				var min_dx: float = (width + ow) * 0.5
				var dx_p: float = next_pos.x - other.global_position.x
				if absf(dx_p) < min_dx:
					var push_sign: float = 1.0 if dx_p >= 0.0 else -1.0
					if absf(dx_p) < 0.01:
						push_sign = 1.0 if prop_id > int(other.get("prop_id")) else -1.0
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
	if has_solid_hitbox and not is_high_speed_gibb_horizontal and not (prop_type in ["TABLE", "TABLE_SMALL", "LAMP_1"] or (prop_type == "CRATE_HANGING" and not on_ground)) and velocity.length() <= 3.8 and match_world != null and is_instance_valid(match_world):
		var fighters_s: Variant = match_world.get("fighters")
		if typeof(fighters_s) == TYPE_ARRAY:
			var my_top_s: float = next_pos.y - height * 0.5
			var my_bot_s: float = next_pos.y + height * 0.5
			var min_f_dx: float = width * 0.5 + 4.0
			for fs_var: Variant in fighters_s as Array:
				if not (fs_var is Node2D) or not is_instance_valid(fs_var):
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

	# 6. Check falling crush / flying impact on fighters
	if _settling_frames <= 0.0 or (is_hanging_crate and is_hanging_released):
		if (is_hanging_crate and is_hanging_released and not on_ground and velocity.y > 0.8) or (can_gibb and ((not on_ground and velocity.y > 1.4) or absf(velocity.x) >= 1.6)) or velocity.length() >= 2.1:
			_check_fighter_impacts(prev_pos, next_pos)

	# 7. Ground / Platform / Prop-stack landing & Ceiling collision check
	on_ground = false
	if velocity.y < 0.0:
		var clamped_ceil_y: float = _clamp_y_against_ceilings(next_pos.x, prev_pos.y, next_pos.y)
		if clamped_ceil_y > next_pos.y + 0.001:
			next_pos.y = clamped_ceil_y
			velocity.y = 0.0
	elif map_loader != null and is_instance_valid(map_loader) and velocity.y >= 0.0:
		var prev_bottom: float = prev_pos.y + height * 0.5
		var next_bottom: float = next_pos.y + height * 0.5
		var ground_y: float = _get_support_y_below(next_pos.x, prev_bottom, next_bottom, true)
		if ground_y < INF and absf(_ledge_overhang_dir) > 0.01:
			# Do NOT snap back up onto the upper ledge while the Center of Mass is still overhanging past the fulcrum!
			var com_ground_y: float = _get_support_y_below(next_pos.x + _ledge_overhang_dir * 2.05, prev_bottom, next_bottom, false)
			if com_ground_y == INF:
				ground_y = INF
		if ground_y < INF and next_bottom >= ground_y - 0.5:
			var impact_vy: float = velocity.y
			next_pos.y = ground_y - height * 0.5
			if (_settling_frames <= 0.0 or (is_hanging_crate and is_hanging_released)) and ((is_hanging_crate and is_hanging_released) or can_gibb) and impact_vy > 1.0:
				# Final swept crush check right at the floor landing position (Player.as:6234-6286 CheckGibPlayer)
				_check_fighter_impacts(prev_pos, next_pos)
			velocity.y = 0.0
			on_ground = true
			_ledge_overhang_dir = 0.0
			if can_tip:
				if impact_vy >= 3.5 and absf(rotation - _target_rest_rot) > 0.45:
					_target_rest_rot = clampf(round(rotation / (PI * 0.5)) * (PI * 0.5), -PI * 0.5, PI * 0.5)
				_sync_rotated_dimensions(ground_y)
				next_pos.y = ground_y - height * 0.5
			elif can_rot:
				# Wide heavy props (CRATE_HANGING, DESK, TABLE) slap their wide base down toward 0 deg on landing impact
				if absf(rotation) > 0.02:
					angular_velocity = -signf(rotation) * maxf(absf(angular_velocity) * 0.5, 0.12)
				else:
					rotation = 0.0
					angular_velocity = 0.0
			else:
				rotation = 0.0
				angular_velocity = 0.0
			if absf(velocity.x) < 0.25:
				crushed_fighter_ids.clear()

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

	global_position = next_pos


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

	for f_var: Variant in fighters_var as Array:
		if not (f_var is Node2D) or not is_instance_valid(f_var):
			continue
		var f: Node2D = f_var as Node2D
		if bool(f.get("is_gibbed")):
			continue
		if bool(f.get("is_dead")) and not is_gibb_prop:
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
		# 1. `falling_from_above`: prop's bottom edge descends from above the fighter's legs/waist with real downward speed (vy >= 2.0).
		# 2. `crushing_downed_fighter`: heavy CanGibb prop lands onto a knocked-down fighter or corpse underneath its span (CheckGibPlayer).
		# 3. `moving_towards_x`: prop is sliding/flying horizontally into the fighter at speed (|vx| >= 1.6).
		# Small nudges/hops on the same floor (|vx| < 1.6 and prev_bottom > foot_y - 4.5) only push the fighter aside in Step 5, NEVER gibbing them!
		var moving_towards_x: bool = (at_pos.x < f_mid.x and velocity.x >= 1.6) or (at_pos.x > f_mid.x and velocity.x <= -1.6)
		var falling_from_above: bool = (prev_bottom <= f.global_position.y - 4.5 and velocity.y >= 2.0)
		var crushing_downed_fighter: bool = (
			is_gibb_prop
			and (bool(f.get("knockdowned")) or bool(f.get("is_dead")))
			and velocity.y >= 1.4
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
				is_gibb_prop
				and moving_towards_x
				and (absf(velocity.x) >= 3.0 or velocity.length() >= 3.8)
				and f.has_method("can_fighter_stand_at_x")
				and not bool(f.call("can_fighter_stand_at_x", f.global_position.x + float(hit_dir) * 3.5, f.global_position.y, self))
			)
			if is_gibb_prop and (falling_from_above or crushing_downed_fighter or pinned_against_wall):
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


func release_hanging_crate() -> void:
	if not is_hanging_crate or is_hanging_released:
		return
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
		var bullet_impulse: float = clampf((pushback * 0.025) / maxf(0.65, mass), 0.15, 0.85)
		velocity.x = clampf(velocity.x + fdir * bullet_impulse, -2.2, 2.2)
		angular_velocity += fdir * 0.03

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
		# Kicks & punches apply calibrated per-prop impulses so crates hop a short distance (~12-16px),
		# barrels slide moderately (~9-12px), and heavy desks/file cabinets barely shift (~2-5px)!
		var push_x: float = 1.0
		var push_y: float = -1.0
		if kick_weight_calculation:
			push_x = clampf(kick_power * (0.95 + 0.35 / maxf(0.5, mass)), 0.75, 1.85)
			push_y = clampf(-1.05 - kick_power * 0.45 / maxf(0.6, mass), -1.80, -0.90)
		elif mass >= 3.0:
			# Super-heavy props (CRATE_HANGING mass=4.2, POOL_TABLE mass=4.8) only nudge slightly along the floor when kicked/punched
			push_x = clampf(kick_power * 0.75, 0.32, 0.72)
			push_y = -0.22 if is_kick else 0.0
		else:
			push_x = clampf(kick_power * 0.85, 0.32, 1.10)
			push_y = clampf(-kick_power * 0.90, -1.10, -0.40)

		if not is_kick:
			# Punches/melee swings push props noticeably less than kicks
			push_x *= 0.55
			push_y = -0.60 if mass <= 1.25 else 0.0

		var attacker_on_top: bool = (
			attacker != null
			and is_instance_valid(attacker)
			and absf(attacker.global_position.y - (global_position.y - height * 0.5)) <= 3.5
			and absf(attacker.global_position.x - global_position.x) <= width * 0.5 + 4.5
		)
		if attacker_on_top and is_kick:
			# AS3 Player.as:5746-5762: when kicking a prop out from under the fighter's own feet, lever arm dx ~ 0 so the prop slides/hops out smoothly!
			push_x *= 1.15
			push_y = -0.45

		velocity = Vector2(fdir * push_x, push_y)
		if _can_tip_horizontally():
			# Housner Inverted-Pendulum Corner-Rocking & Toppling Impulse (AS3 Player.as:5750-5762):
			# - Light punches rock tall props to ~13 deg (1 punch) or ~28 deg (2 punches) within the sub-critical balance regime (|theta| < theta_crit),
			#   allowing gravity's restoring torque to pull them back upright to 0 deg! Only 3 rapid consecutive punches cross theta_crit.
			# - Kicking a tall slender prop (BARREL, BARREL_EXPLOSIVE, GASCAN, CHAIR, COMP: base_height >= base_width * 1.2) imparts ~0.178 rad/tick,
			#   which visibly decelerates as the Center of Mass climbs past theta_crit (~36.25 deg) before gravity topples it onto its side at +-90 deg!
			# - Kicking a heavy/wide-based prop (FILECAB mass=2.25, TRASHCAN) imparts ~0.118 rad/tick, rocking it to ~20 deg and falling back upright
			#   on 1 kick, and only toppling on a 2nd consecutive kick while tilted!
			if attacker_on_top:
				angular_velocity = fdir * 0.05
			elif _is_tipped_on_side():
				var side_sign: float = signf(rotation) if absf(rotation) > 0.01 else fdir
				angular_velocity = -side_sign * (0.045 if is_kick else 0.025)
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
		crushed_fighter_ids.clear()
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
		velocity = impulse
		angular_velocity = signf(impulse.x) * 0.16
		on_ground = false
		crushed_fighter_ids.clear()

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
	_fire_heat += amount
	if _fire_heat >= 15.0:
		ignite()


func ignite() -> void:
	if is_destroyed or (not can_burn and barrel_phase == 0):
		return
	_fire_heat = 15.0
	is_burning = true
	queue_redraw()


func apply_fall_impact_damage(damage: float, impulse: Vector2 = Vector2.ZERO, attacker: Node2D = null) -> bool:
	if is_destroyed or is_hanging_holder or prop_type == "CRATE_HANGING_HOLDER" or not kickable or indestructible:
		return false
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
	if is_parachute_crate and amount > 0.0:
		_open_supply_crate()
		return
	hp -= amount
	if hp > 0.0:
		_update_damaged_visual(impulse.x)
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

	_notify_explosion_and_fire(blast_pos, 33.0, 20.0, 4.8, "BARREL_WRECK", 14)
	_spawn_debris_burst(blast_pos + Vector2(0.0, -height * 0.5), Vector2(0.0, -3.2), 5)


func _trigger_gascan_explosion() -> void:
	if is_destroyed:
		return
	var blast_pos: Vector2 = global_position
	is_destroyed = true
	visible = false

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

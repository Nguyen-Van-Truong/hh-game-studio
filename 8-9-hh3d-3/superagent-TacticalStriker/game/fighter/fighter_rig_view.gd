class_name FighterRigView
extends Node2D
## 2-Layer Split Rig & Full-Body Renderer for Superfighters Y8 Remake (SF-M2 / SF-M3 / SF-M6).
## Strictly uses compiled XFL sub-pixel rects and pivots (no manual _trim_visible or 108px scaling).

const _PreloadMugenFighterAdapter = preload("res://game/fighter/mugen_fighter_adapter.gd")
const _PreloadTacticalStrikerRigPainter = preload("res://game/fighter/tactical_striker_rig_painter.gd")
const DEFAULT_BODY_PIVOT: Vector2 = Vector2(0.0, -9.0)
const DEFAULT_SHOULDER_PIVOT: Vector2 = Vector2(-3.0, -12.0)

const MELEE_TRACE_PATHS: Dictionary = {
	"MACHETE_01": "res://assets/sprites/effects/trace_machete_01.png",
	"MACHETE_02": "res://assets/sprites/effects/trace_machete_02.png",
	"MACHETE_03": "res://assets/sprites/effects/trace_machete_03.png",
	"AXE_01": "res://assets/sprites/effects/trace_axe_01.png",
	"AXE_02": "res://assets/sprites/effects/trace_axe_02.png",
	"AXE_03": "res://assets/sprites/effects/trace_axe_03.png",
	"SWORD_01": "res://assets/sprites/effects/trace_sword_01.png",
	"SWORD_02": "res://assets/sprites/effects/trace_sword_02.png",
	"SWORD_03": "res://assets/sprites/effects/trace_sword_03.png",
}

var character_id: String = "johnny"
var current_state: String = "IDLE"
var current_rig_type: String = "full_body"
var facing: int = 1
var anim_frame_idx: int = 1
var weapon_anim_frame_nr: int = 1
var current_aim_pitch: float = 0.0
var body_rotation_deg: float = 0.0
var hp: float = 100.0
var max_hp: float = 100.0
var burn_state: float = 0.0
var show_laser: bool = false
var show_aim_guide: bool = false

var mugen_adapter: RefCounted = null
var registry_override: Object = null

var body_pivot: Node2D = null
var body_sprite: Sprite2D = null
var blood_overlay: Sprite2D = null
var melee_trace_sprite: Sprite2D = null
var aim_pivot: Node2D = null
var weapon_arm_sprite: Sprite2D = null
var muzzle_socket: Marker2D = null
var shell_socket: Marker2D = null
var fire_socket: Marker2D = null
var aim_reticle_sprite: Sprite2D = null
var laser_sight: Line2D = null

var _body_atlas: AtlasTexture = null
var _blood_atlas: AtlasTexture = null
var _arm_atlas: AtlasTexture = null
var _fallback_aim_tex: Texture2D = null
static var _ledge_grab_tex_cache: Dictionary = {}

# TS-WP2..WP4: 3.5-Head Tactical Striker Rig & 7 Live Facial Expressions
var use_tactical_striker_rig: bool = true
var current_expression_id: String = "CONFIDENT_SMIRK"
var _expr_hold_timer: float = 0.0
var _breath_phase: float = 0.0
var _blink_timer: float = 2.8
var _is_blinking: bool = false
var _is_charred_cached: bool = false
var _is_hit_flashing_cached: bool = false
var _blood_alpha_cached: float = 0.0


func get_current_expression_id() -> String:
	return current_expression_id


func get_current_hud_portrait_key() -> String:
	return _PreloadTacticalStrikerRigPainter.get_hud_portrait_key(current_expression_id)


func get_current_head_tilt_deg() -> float:
	return _PreloadTacticalStrikerRigPainter.compute_head_tilt_deg(current_state, current_aim_pitch)


func force_expression(expr_id: String, hold_sec: float = 0.28) -> void:
	current_expression_id = expr_id
	_expr_hold_timer = maxf(_expr_hold_timer, hold_sec)
	queue_redraw()


func step_expression_and_breathing(dt: float, is_carrying: bool = false, is_victory: bool = false) -> void:
	if dt <= 0.0:
		return
	var prev_expr: String = current_expression_id
	var prev_blink: bool = _is_blinking
	var prev_breath_step: int = int(floor(_breath_phase * 3.0))

	_breath_phase = fmod(_breath_phase + dt * 4.2, TAU)
	if _expr_hold_timer > 0.0:
		_expr_hold_timer = maxf(0.0, _expr_hold_timer - dt)

	# Auto eye-blink (0.11s every ~3.2s) only when in calm/focus states and alive (TS-EC-05)
	if hp > 0.0 and current_expression_id in ["CONFIDENT_SMIRK", "BATTLE_FOCUS"]:
		_blink_timer -= dt
		if _blink_timer <= 0.0:
			if not _is_blinking:
				_is_blinking = true
				_blink_timer = 0.11
			else:
				_is_blinking = false
				_blink_timer = 3.1
	else:
		_is_blinking = false
		_blink_timer = 2.6

	var eval_dict: Dictionary = _PreloadTacticalStrikerRigPainter.evaluate_target_expression(
		current_state, hp, max_hp, is_carrying, is_victory
	)
	var target_id: String = str(eval_dict.get("id", "CONFIDENT_SMIRK"))
	var target_hold: float = float(eval_dict.get("hold", 0.0))
	var cur_prio: int = _PreloadTacticalStrikerRigPainter.get_expression_priority(current_expression_id)
	var tgt_prio: int = _PreloadTacticalStrikerRigPainter.get_expression_priority(target_id)

	if tgt_prio >= cur_prio or _expr_hold_timer <= 0.0 or hp <= 0.0:
		if current_expression_id != target_id:
			current_expression_id = target_id
			_expr_hold_timer = target_hold
		elif tgt_prio >= 4 and target_hold > _expr_hold_timer:
			_expr_hold_timer = target_hold

	var next_breath_step: int = int(floor(_breath_phase * 3.0))
	if prev_expr != current_expression_id or prev_blink != _is_blinking or prev_breath_step != next_breath_step:
		queue_redraw()


func _init() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS


func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	_ensure_nodes()
	apply_rig_state(
		character_id,
		current_state,
		anim_frame_idx,
		facing,
		current_aim_pitch,
		weapon_anim_frame_nr,
		hp,
		max_hp,
		body_rotation_deg,
		show_laser
	)


func _ensure_nodes() -> void:
	if _body_atlas == null:
		_body_atlas = AtlasTexture.new()
	if _blood_atlas == null:
		_blood_atlas = AtlasTexture.new()
	if _arm_atlas == null:
		_arm_atlas = AtlasTexture.new()

	body_pivot = get_node_or_null("BodyPivot") as Node2D
	if body_pivot == null:
		body_pivot = Node2D.new()
		body_pivot.name = "BodyPivot"
		body_pivot.position = DEFAULT_BODY_PIVOT
		add_child(body_pivot)

	body_sprite = body_pivot.get_node_or_null("BodySprite") as Sprite2D
	if body_sprite == null:
		body_sprite = Sprite2D.new()
		body_sprite.name = "BodySprite"
		body_sprite.centered = false
		body_sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		body_pivot.add_child(body_sprite)
	body_sprite.centered = false

	blood_overlay = body_pivot.get_node_or_null("BloodOverlay") as Sprite2D
	if blood_overlay == null:
		blood_overlay = Sprite2D.new()
		blood_overlay.name = "BloodOverlay"
		blood_overlay.centered = false
		blood_overlay.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		body_pivot.add_child(blood_overlay)
	blood_overlay.centered = false

	melee_trace_sprite = body_pivot.get_node_or_null("MeleeTraceSprite") as Sprite2D
	if melee_trace_sprite == null:
		melee_trace_sprite = Sprite2D.new()
		melee_trace_sprite.name = "MeleeTraceSprite"
		melee_trace_sprite.centered = true
		melee_trace_sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		melee_trace_sprite.z_index = 2
		melee_trace_sprite.visible = false
		body_pivot.add_child(melee_trace_sprite)

	aim_pivot = get_node_or_null("AimPivot") as Node2D
	if aim_pivot == null:
		aim_pivot = Node2D.new()
		aim_pivot.name = "AimPivot"
		aim_pivot.position = DEFAULT_SHOULDER_PIVOT
		aim_pivot.visible = false
		add_child(aim_pivot)

	weapon_arm_sprite = aim_pivot.get_node_or_null("WeaponArmSprite") as Sprite2D
	if weapon_arm_sprite == null:
		weapon_arm_sprite = Sprite2D.new()
		weapon_arm_sprite.name = "WeaponArmSprite"
		weapon_arm_sprite.centered = false
		weapon_arm_sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		aim_pivot.add_child(weapon_arm_sprite)
	weapon_arm_sprite.centered = false

	muzzle_socket = aim_pivot.get_node_or_null("MuzzleSocket") as Marker2D
	if muzzle_socket == null:
		muzzle_socket = Marker2D.new()
		muzzle_socket.name = "MuzzleSocket"
		muzzle_socket.position = Vector2(12.5, -3.5)
		aim_pivot.add_child(muzzle_socket)

	shell_socket = aim_pivot.get_node_or_null("ShellSocket") as Marker2D
	if shell_socket == null:
		shell_socket = Marker2D.new()
		shell_socket.name = "ShellSocket"
		shell_socket.position = Vector2(6.55, -3.5)
		aim_pivot.add_child(shell_socket)

	fire_socket = aim_pivot.get_node_or_null("FireSocket") as Marker2D
	if fire_socket == null:
		fire_socket = Marker2D.new()
		fire_socket.name = "FireSocket"
		fire_socket.position = Vector2(8.05, -3.5)
		aim_pivot.add_child(fire_socket)

	aim_reticle_sprite = aim_pivot.get_node_or_null("AimReticleSprite") as Sprite2D
	if aim_reticle_sprite == null:
		aim_reticle_sprite = Sprite2D.new()
		aim_reticle_sprite.name = "AimReticleSprite"
		aim_reticle_sprite.centered = true
		aim_reticle_sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		aim_reticle_sprite.z_index = 3
		aim_reticle_sprite.visible = false
		aim_pivot.add_child(aim_reticle_sprite)

	laser_sight = aim_pivot.get_node_or_null("LaserSight") as Line2D
	if laser_sight == null:
		laser_sight = Line2D.new()
		laser_sight.name = "LaserSight"
		laser_sight.width = 1.0
		laser_sight.default_color = Color(1.0, 0.1, 0.1, 0.85)
		laser_sight.points = PackedVector2Array([Vector2(12.5, -3.5), Vector2(1000.0, -3.5)])
		laser_sight.visible = false
		aim_pivot.add_child(laser_sight)


func _get_registry() -> Object:
	if registry_override != null:
		return registry_override
	var tree: SceneTree = Engine.get_main_loop() as SceneTree
	if tree != null and tree.root != null:
		var autoload_reg: Node = tree.root.get_node_or_null("SFDataRegistry")
		if autoload_reg != null:
			return autoload_reg
		var script: Script = load("res://game/core/sf_data_registry.gd") as Script
		if script != null:
			var inst: Node = script.new() as Node
			inst.name = "SFDataRegistry"
			tree.root.add_child(inst)
			if inst.has_method("ensure_loaded"):
				inst.call("ensure_loaded")
			_PreloadMugenFighterAdapter.ensure_registry_integration(inst)
			return inst
	return null


func set_facing(p_facing: int) -> void:
	facing = -1 if p_facing < 0 else 1
	scale.x = -1.0 if facing < 0 else 1.0
	scale.y = 1.0


func set_aim_pitch(p_pitch_deg: float) -> void:
	current_aim_pitch = clampf(p_pitch_deg, -90.0, 90.0)
	if aim_pivot != null:
		aim_pivot.rotation = deg_to_rad(current_aim_pitch)


func get_aim_direction_vector() -> Vector2:
	var rad: float = deg_to_rad(current_aim_pitch)
	var dir_x: float = cos(rad) * float(facing)
	var dir_y: float = sin(rad)
	var vec: Vector2 = Vector2(dir_x, dir_y)
	if vec.length_squared() <= 0.00001:
		return Vector2(float(facing), 0.0)
	return vec.normalized()


func get_aim_world_angle_deg() -> float:
	var dir: Vector2 = get_aim_direction_vector()
	return rad_to_deg(atan2(dir.y, dir.x))


func get_muzzle_global_pos() -> Vector2:
	_ensure_nodes()
	if is_inside_tree():
		return muzzle_socket.global_position
	return global_position + _local_socket_to_char_offset(muzzle_socket.position)


func get_shell_global_pos() -> Vector2:
	_ensure_nodes()
	if is_inside_tree():
		return shell_socket.global_position
	return global_position + _local_socket_to_char_offset(shell_socket.position)


func get_fire_global_pos() -> Vector2:
	_ensure_nodes()
	if is_inside_tree():
		return fire_socket.global_position
	return global_position + _local_socket_to_char_offset(fire_socket.position)


func _local_socket_to_char_offset(socket_local: Vector2) -> Vector2:
	var rotated: Vector2 = socket_local.rotated(deg_to_rad(current_aim_pitch))
	var in_rig: Vector2 = aim_pivot.position + rotated
	return Vector2(in_rig.x * float(facing), in_rig.y)


var _last_rig_hash: int = 0


func apply_rig_state(
	p_char_id: String,
	p_state_name: String,
	p_anim_frame_idx: int = 1,
	p_facing: int = 1,
	p_aim_pitch_deg: float = 0.0,
	p_weapon_anim_frame_nr: int = 1,
	p_hp: float = 100.0,
	p_max_hp: float = 100.0,
	p_body_rotation_deg: float = 0.0,
	p_show_laser: bool = false,
	p_show_aim_guide: bool = false,
	p_burn_state: float = 0.0,
	p_is_burnt_corpse: bool = false
) -> void:
	_ensure_nodes()
	var next_char: String = p_char_id.to_lower()
	var next_state: String = p_state_name.to_upper()
	var next_frame: int = maxi(1, p_anim_frame_idx)
	var next_wframe: int = maxi(1, p_weapon_anim_frame_nr)
	var is_charred: bool = p_is_burnt_corpse or (p_hp <= 0.0 and p_burn_state >= 15.0)
	var pnode_rv: Node = get_parent()
	var hit_flash_t: float = float(pnode_rv.get("_hit_flash_timer")) if (pnode_rv != null and pnode_rv.get("_hit_flash_timer") != null) else 0.0
	var is_hit_flashing: bool = (hit_flash_t > 0.0) and not is_charred
	var cur_hash: int = hash([
		next_char, next_state, next_frame, p_facing,
		int(roundf(p_aim_pitch_deg * 10.0)), next_wframe,
		int(roundf(p_hp)), int(roundf(p_max_hp)),
		int(roundf(p_body_rotation_deg * 10.0)),
		p_show_laser, p_show_aim_guide, is_charred, is_hit_flashing,
		int(roundf(_expr_hold_timer * 100.0))
	])
	if cur_hash == _last_rig_hash and body_sprite.texture != null:
		burn_state = p_burn_state
		return
	_last_rig_hash = cur_hash

	character_id = next_char
	current_state = next_state
	anim_frame_idx = next_frame
	weapon_anim_frame_nr = next_wframe
	hp = p_hp
	max_hp = maxf(1.0, p_max_hp)
	body_rotation_deg = p_body_rotation_deg
	show_laser = p_show_laser
	show_aim_guide = p_show_aim_guide
	burn_state = p_burn_state

	set_facing(p_facing)
	set_aim_pitch(p_aim_pitch_deg)

	var reg: Object = _get_registry()
	if reg == null:
		return
	_PreloadMugenFighterAdapter.ensure_registry_integration(reg)

	var char_sheet: Texture2D = reg.call("get_character_sheet", character_id) as Texture2D
	var blood_sheet: Texture2D = reg.call("get_blood_sheet") as Texture2D
	# AS3 Symbol 1292.xml (player_burnt) & PlayerState.as:1101:
	# Living burning fighters keep their normal sprite color; once killed by fire (Burned=true),
	# they turn pitch-black (redMultiplier=0, greenMultiplier=0, blueMultiplier=0) and BloodVisible=false!
	var blood_alpha: float = 0.0 if is_charred else clampf((1.0 - hp / max_hp) * 0.9, 0.0, 0.85)
	var burnt_modulate: Color = Color(0.05, 0.04, 0.04, 1.0) if is_charred else (Color(2.4, 2.4, 2.4, 1.0) if is_hit_flashing else Color(1.0, 1.0, 1.0, 1.0))
	body_sprite.modulate = burnt_modulate
	weapon_arm_sprite.modulate = burnt_modulate
	body_sprite.flip_h = false
	blood_overlay.flip_h = false

	_is_charred_cached = is_charred
	_is_hit_flashing_cached = is_hit_flashing
	_blood_alpha_cached = blood_alpha

	var is_carrying_prop: bool = (pnode_rv != null and pnode_rv.get("grabbed_target") != null)
	var eval_now: Dictionary = _PreloadTacticalStrikerRigPainter.evaluate_target_expression(
		current_state, hp, max_hp, is_carrying_prop, false
	)
	var tgt_expr_now: String = str(eval_now.get("id", "CONFIDENT_SMIRK"))
	var tgt_hold_now: float = float(eval_now.get("hold", 0.0))
	var cur_p_now: int = _PreloadTacticalStrikerRigPainter.get_expression_priority(current_expression_id)
	var tgt_p_now: int = _PreloadTacticalStrikerRigPainter.get_expression_priority(tgt_expr_now)
	if tgt_p_now >= cur_p_now or _expr_hold_timer <= 0.0 or hp <= 0.0:
		if current_expression_id != tgt_expr_now:
			current_expression_id = tgt_expr_now
			_expr_hold_timer = tgt_hold_now

	var sprite_vis_alpha: float = 0.0 if use_tactical_striker_rig else 1.0
	body_sprite.self_modulate = Color(1.0, 1.0, 1.0, sprite_vis_alpha)
	blood_overlay.self_modulate = Color(1.0, 1.0, 1.0, sprite_vis_alpha)
	weapon_arm_sprite.self_modulate = Color(1.0, 1.0, 1.0, sprite_vis_alpha)
	if use_tactical_striker_rig:
		queue_redraw()

	# 1. Check if MUGEN adapter handles this state with custom MUGEN frames
	if mugen_adapter != null and bool(mugen_adapter.call("is_mugen_state", current_state)):
		var m_vis: Dictionary = mugen_adapter.call("get_frame_visual_data", current_state, anim_frame_idx) as Dictionary
		if not m_vis.is_empty():
			current_rig_type = "full_body"
			aim_pivot.visible = false
			laser_sight.visible = false
			aim_reticle_sprite.visible = false
			melee_trace_sprite.visible = false
			body_pivot.position = DEFAULT_BODY_PIVOT
			body_pivot.rotation = deg_to_rad(body_rotation_deg)

			var m_rect: Rect2 = m_vis.get("rect", Rect2(20, 270, 28, 20)) as Rect2
			var m_piv: Vector2 = m_vis.get("pivot", Vector2(-8, -19)) as Vector2
			_body_atlas.atlas = char_sheet
			_body_atlas.region = m_rect
			body_sprite.texture = _body_atlas
			body_sprite.position = m_piv - body_pivot.position

			_blood_atlas.atlas = blood_sheet
			_blood_atlas.region = m_rect
			blood_overlay.texture = _blood_atlas
			blood_overlay.position = body_sprite.position
			blood_overlay.modulate = Color(1.0, 1.0, 1.0, blood_alpha)
			blood_overlay.visible = blood_alpha > 0.01
			return

	# 2. Standard Superfighters XFL state lookup
	if current_state == "LEDGE_GRAB":
		# Authentic Superfighters Deluxe side-profile ledge grab:
		# Side-profile torso/head facing the wall, clean back (no back-arm), front arm reaching up to hook the ledge corner, front foot braced on wall!
		current_rig_type = "full_body"
		laser_sight.visible = false
		aim_reticle_sprite.visible = false
		melee_trace_sprite.visible = false
		aim_pivot.visible = false
		body_pivot.position = DEFAULT_BODY_PIVOT
		body_pivot.rotation = 0.0
		var lg_tex: Texture2D = _get_ledge_grab_texture(character_id, char_sheet)
		if lg_tex != null:
			body_sprite.texture = lg_tex
			body_sprite.position = Vector2(-12.0, -18.0) - body_pivot.position
			var lg_blood: Texture2D = _get_ledge_grab_texture("blood_overlay", blood_sheet)
			if lg_blood != null:
				blood_overlay.texture = lg_blood
				blood_overlay.position = body_sprite.position
				blood_overlay.modulate = Color(1.0, 1.0, 1.0, blood_alpha)
				blood_overlay.visible = blood_alpha > 0.01
			else:
				blood_overlay.visible = false
		return

	var st_data: Dictionary = reg.call("get_state_data", current_state) as Dictionary
	if st_data.is_empty():
		st_data = reg.call("get_state_data", "IDLE") as Dictionary

	var st_type: String = str(st_data.get("type", "full_body"))

	# Split-rig only when in START_* or AIM_* states with split_rig_aim / split_rig_start
	if st_type == "split_rig_aim" or st_type == "split_rig_start":
		current_rig_type = "split_rig"
		body_pivot.position = DEFAULT_BODY_PIVOT
		body_pivot.rotation = 0.0
		melee_trace_sprite.visible = false

		# Torso (Layer 3 armless body: Symbol 663 / Symbol 694 / Symbol 700)
		var torso_dict: Dictionary = st_data.get("torso", {}) as Dictionary
		var torso_frames: Array = torso_dict.get("frames", []) as Array
		if not torso_frames.is_empty():
			var tf: Dictionary = torso_frames[0] as Dictionary
			var t_rect_arr: Array = tf.get("rect", [27.0, 84.0, 12.0, 16.0]) as Array
			var t_piv_arr: Array = tf.get("pivot", [-6.0, -15.0]) as Array
			var t_region: Rect2 = Rect2(
				float(t_rect_arr[0]),
				float(t_rect_arr[1]),
				float(t_rect_arr[2]),
				float(t_rect_arr[3])
			)
			var t_pivot: Vector2 = Vector2(float(t_piv_arr[0]), float(t_piv_arr[1]))
			var t_top_pad: float = 4.0 if (mugen_adapter != null and t_region.position.y >= 4.0 and t_region.size.y >= 15.0) else 0.0
			_body_atlas.atlas = char_sheet
			_body_atlas.region = Rect2(t_region.position.x, t_region.position.y - t_top_pad, t_region.size.x, t_region.size.y + t_top_pad)
			body_sprite.texture = _body_atlas
			body_sprite.position = t_pivot - body_pivot.position - Vector2(0.0, t_top_pad)

			_blood_atlas.atlas = blood_sheet
			_blood_atlas.region = t_region
			blood_overlay.texture = _blood_atlas
			blood_overlay.position = t_pivot - body_pivot.position
			blood_overlay.modulate = Color(1.0, 1.0, 1.0, blood_alpha)
			blood_overlay.visible = blood_alpha > 0.01

		# Shoulder & WeaponArm (Layer 2 ANIM_WPN)
		var sh_arr: Array = st_data.get("shoulder_pivot", [-3.0, -12.0]) as Array
		if sh_arr.size() >= 2:
			aim_pivot.position = Vector2(float(sh_arr[0]), float(sh_arr[1]))
		else:
			aim_pivot.position = DEFAULT_SHOULDER_PIVOT
		aim_pivot.rotation = deg_to_rad(current_aim_pitch)
		aim_pivot.visible = true

		var wpn_arm: Dictionary = st_data.get("weapon_arm", st_data.get("start_arm", {})) as Dictionary
		var arm_frames: Array = wpn_arm.get("frames", st_data.get("frames", [])) as Array
		var aim_origin: Vector2 = muzzle_socket.position
		if not arm_frames.is_empty():
			var arm_idx: int = clampi(weapon_anim_frame_nr - 1, 0, arm_frames.size() - 1)
			var af: Dictionary = arm_frames[arm_idx] as Dictionary
			var a_rect_arr: Array = af.get("rect", [46.0, 119.0, 18.0, 12.0]) as Array
			var a_piv_arr: Array = af.get("pivot", [-4.5, -8.0]) as Array
			var a_region: Rect2 = Rect2(
				float(a_rect_arr[0]),
				float(a_rect_arr[1]),
				float(a_rect_arr[2]),
				float(a_rect_arr[3])
			)
			_arm_atlas.atlas = char_sheet
			_arm_atlas.region = a_region
			weapon_arm_sprite.texture = _arm_atlas
			var arm_pivot_vec: Vector2 = Vector2(float(a_piv_arr[0]), float(a_piv_arr[1]))
			if st_type == "split_rig_start":
				weapon_arm_sprite.position = arm_pivot_vec - aim_pivot.position
			else:
				weapon_arm_sprite.position = arm_pivot_vec

			var muz_arr: Array = af.get("muzzle_center", wpn_arm.get("muzzle_center", [12.5, -3.5])) as Array
			var shl_arr: Array = af.get("shell_center", wpn_arm.get("shell_center", [6.55, -3.5])) as Array
			var fir_arr: Array = af.get("fire_center", wpn_arm.get("fire_center", [8.05, -3.5])) as Array
			var aim_arr: Array = af.get("aim_position", wpn_arm.get("aim_position", muz_arr)) as Array
			if muz_arr.size() >= 2:
				muzzle_socket.position = Vector2(float(muz_arr[0]), float(muz_arr[1]))
			if shl_arr.size() >= 2:
				shell_socket.position = Vector2(float(shl_arr[0]), float(shl_arr[1]))
			if fir_arr.size() >= 2:
				fire_socket.position = Vector2(float(fir_arr[0]), float(fir_arr[1]))
			if aim_arr.size() >= 2:
				aim_origin = Vector2(float(aim_arr[0]), float(aim_arr[1]))
			else:
				aim_origin = muzzle_socket.position

		# AS3 Player.as:6547-6597: Small white square aim reticle (player_aim) at 16px ahead of aim_position
		if show_aim_guide:
			aim_reticle_sprite.texture = _get_aim_reticle_texture(reg)
			aim_reticle_sprite.position = aim_origin + Vector2(16.0, 0.0)
			aim_reticle_sprite.visible = true
		else:
			aim_reticle_sprite.visible = false

		# AS3 Weapons.as: Red laser sight ONLY for SNIPER and LASER_GUN (never a 90px yellow line!)
		if show_laser:
			laser_sight.visible = true
			var start_p: Vector2 = muzzle_socket.position
			var line_len: float = _compute_laser_ray_length(1000.0)
			laser_sight.width = 1.0
			laser_sight.default_color = Color(1.0, 0.1, 0.1, 0.85)
			laser_sight.points = PackedVector2Array([start_p, start_p + Vector2(line_len, 0.0)])
		else:
			laser_sight.visible = false
	else:
		# Full-body state (IDLE, RUN, SPRINT, JUMP, KNEEL, COVER, ROLL, DIVE, PUNCH_01..03, MACHETE_01..03, AXE_01..03, SWORD_01..03, etc.)
		current_rig_type = "full_body"
		aim_pivot.visible = false
		laser_sight.visible = false
		aim_reticle_sprite.visible = false

		body_pivot.position = DEFAULT_BODY_PIVOT
		if st_type == "rotating_body" or current_state in ["DIVE", "FALL_F", "FALL_B", "GRABBED", "ROCKET_RIDE_R", "ROCKET_RIDE_L"]:
			body_pivot.rotation = deg_to_rad(body_rotation_deg)
		else:
			body_pivot.rotation = 0.0

		var frames: Array = st_data.get("frames", []) as Array
		if not frames.is_empty():
			var f_idx: int = clampi(anim_frame_idx - 1, 0, frames.size() - 1)
			var fd: Dictionary = frames[f_idx] as Dictionary
			var r_arr: Array = fd.get("rect", [46.0, 11.0, 17.0, 21.0]) as Array
			var p_arr: Array = fd.get("pivot", [-10.0, -20.0]) as Array
			var region: Rect2 = Rect2(
				float(r_arr[0]),
				float(r_arr[1]),
				float(r_arr[2]),
				float(r_arr[3])
			)
			var pivot_vec: Vector2 = Vector2(float(p_arr[0]), float(p_arr[1]))

			var is_rocket_ride: bool = current_state in ["ROCKET_RIDE_R", "ROCKET_RIDE_L"]
			var flip_body_h: bool = is_rocket_ride or current_state == "COVER" or bool(fd.get("flip_h", false))
			var base_pos: Vector2 = pivot_vec if is_rocket_ride else (pivot_vec - body_pivot.position)
			var f_top_pad: float = 4.0 if (mugen_adapter != null and region.position.y >= 4.0 and region.size.y >= 15.0) else 0.0
			_body_atlas.atlas = char_sheet
			_body_atlas.region = Rect2(region.position.x, region.position.y - f_top_pad, region.size.x, region.size.y + f_top_pad)
			body_sprite.texture = _body_atlas
			body_sprite.flip_h = flip_body_h
			# In Symbol 708.xml (ROCKET_RIDE), pivot_vec (-6.5, -10.5) is directly relative to the rocket rotation center (body_pivot)
			body_sprite.position = base_pos - Vector2(0.0, f_top_pad)

			_blood_atlas.atlas = blood_sheet
			_blood_atlas.region = region
			blood_overlay.texture = _blood_atlas
			blood_overlay.flip_h = flip_body_h
			blood_overlay.position = base_pos
			blood_overlay.modulate = Color(1.0, 1.0, 1.0, blood_alpha)
			blood_overlay.visible = blood_alpha > 0.01

		_update_melee_trace_sprite(reg)


func _get_ledge_grab_texture(cache_key: String, sheet_tex: Texture2D) -> Texture2D:
	if sheet_tex == null:
		return null
	if _ledge_grab_tex_cache.has(cache_key):
		return _ledge_grab_tex_cache[cache_key] as Texture2D
	var sheet_img: Image = sheet_tex.get_image()
	if sheet_img == null or sheet_img.get_width() < 500 or sheet_img.get_height() < 32:
		return null
	var out: Image = Image.create(18, 22, false, Image.FORMAT_RGBA8)
	out.fill(Color(0.0, 0.0, 0.0, 0.0))
	# 1. Copy side-profile head, torso, and wall-braced legs from (481, 10, 18, 22), excluding the back arm (dx<5) and chest-level front arm (dx>=12, dy=6..11)
	for dy: int in range(22):
		for dx: int in range(5, 18):
			if dy >= 6 and dy <= 11 and dx >= 12:
				continue
			out.set_pixel(dx, dy, sheet_img.get_pixel(481 + dx, 10 + dy))
	# 2. Add clean 1px black outline on the back of the shirt and front ribcage under the raised arm
	if cache_key != "blood_overlay":
		for dy: int in range(6, 13):
			if out.get_pixel(6, dy).a > 0.05:
				out.set_pixel(5, dy, Color(0.0, 0.0, 0.0, 1.0))
		for dy: int in range(8, 12):
			if out.get_pixel(11, dy).a > 0.05:
				out.set_pixel(12, dy, Color(0.0, 0.0, 0.0, 1.0))
	# 3. Copy the front arm/hand (dx=12..16, dy=6..11) shifted UP by 4px (to dy=2..7) so the hand hooks onto the top corner of the ledge!
	for dy: int in range(6, 12):
		for dx: int in range(12, 17):
			var px: Color = sheet_img.get_pixel(481 + dx, 10 + dy)
			if px.a > 0.05:
				out.set_pixel(dx, dy - 4, px)
	var tex: ImageTexture = ImageTexture.create_from_image(out)
	_ledge_grab_tex_cache[cache_key] = tex
	return tex


func _get_aim_reticle_texture(reg: Object) -> Texture2D:
	if reg != null and reg.has_method("load_cached_texture"):
		var tex: Texture2D = reg.call("load_cached_texture", "res://assets/sprites/effects/player_aim.png") as Texture2D
		if tex != null:
			return tex
	if _fallback_aim_tex == null:
		var img: Image = Image.create(5, 5, false, Image.FORMAT_RGBA8)
		img.fill(Color(0.0, 0.0, 0.0, 0.0))
		for x: int in range(5):
			for y: int in range(5):
				if x == 0 or x == 4 or y == 0 or y == 4:
					img.set_pixel(x, y, Color(0.0, 0.0, 0.0, 0.85))
				elif x == 1 or x == 3 or y == 1 or y == 3:
					img.set_pixel(x, y, Color(1.0, 1.0, 1.0, 0.95))
		_fallback_aim_tex = ImageTexture.create_from_image(img)
	return _fallback_aim_tex


func _compute_laser_ray_length(max_len: float = 1000.0) -> float:
	var parent_node: Node = get_parent()
	if parent_node != null and parent_node.has_method("_get_map_loader"):
		var ml: Object = parent_node.call("_get_map_loader")
		if ml != null and ml.has_method("raycast_solid"):
			var start_world: Vector2 = get_muzzle_global_pos()
			var dir_world: Vector2 = get_aim_direction_vector()
			var end_world: Vector2 = start_world + dir_world * max_len
			var ignore_cov: int = -1
			if bool(parent_node.get("taking_cover")) and parent_node.get("cover_object_id") != null:
				ignore_cov = int(parent_node.get("cover_object_id"))
			var hit_res: Dictionary = ml.call("raycast_solid", start_world, end_world, ignore_cov) as Dictionary
			if bool(hit_res.get("hit", false)):
				var hit_pos: Vector2 = hit_res.get("pos", end_world) as Vector2
				return clampf(start_world.distance_to(hit_pos), 4.0, max_len)
	return max_len


func _update_melee_trace_sprite(reg: Object) -> void:
	if melee_trace_sprite == null:
		return
	if MELEE_TRACE_PATHS.has(current_state) and anim_frame_idx >= 2:
		var trace_path: String = str(MELEE_TRACE_PATHS[current_state])
		var trace_tex: Texture2D = null
		if reg != null and reg.has_method("load_cached_texture"):
			trace_tex = reg.call("load_cached_texture", trace_path) as Texture2D
		if trace_tex != null:
			melee_trace_sprite.texture = trace_tex
			melee_trace_sprite.position = Vector2(8.0, -2.0)
			melee_trace_sprite.visible = true
			return
	melee_trace_sprite.visible = false


func _draw() -> void:
	var pnode: Node2D = get_parent() as Node2D
	if pnode == null:
		return
	var r_spec: Dictionary = pnode.get("resource_spec") as Dictionary if typeof(pnode.get("resource_spec")) == TYPE_DICTIONARY else {}
	var aura_hex: String = str(r_spec.get("bar_color", "#FFCC22"))
	var aura_col: Color = Color.from_string(aura_hex, Color(1.0, 0.82, 0.22, 1.0))

	# 0. Draw Afterimage Speed Ghost Trail (_afterimage_trail) behind the fighter (SA-WP9)
	var trail_var: Variant = pnode.get("_afterimage_trail")
	if typeof(trail_var) == TYPE_ARRAY:
		var f_sign: float = -1.0 if facing < 0 else 1.0
		for g_item: Variant in trail_var as Array:
			if typeof(g_item) != TYPE_DICTIONARY:
				continue
			var gd: Dictionary = g_item as Dictionary
			var g_pos: Vector2 = gd.get("world_pos", pnode.global_position) as Vector2
			var g_col: Color = gd.get("color", aura_col) as Color
			var g_t: float = float(gd.get("timer", 0.08))
			var g_max: float = maxf(0.04, float(gd.get("max_timer", 0.16)))
			var g_alpha: float = clampf(g_t / g_max, 0.0, 1.0) * 0.52
			var rel: Vector2 = g_pos - pnode.global_position
			var local_pt: Vector2 = Vector2(rel.x * f_sign, rel.y)
			# Silhouette afterimage body + head echo with 1px dark rim
			draw_rect(Rect2(local_pt.x - 5.0, local_pt.y - 19.0, 10.0, 18.0), Color(0.04, 0.05, 0.08, g_alpha * 0.85), false, 1.0)
			draw_rect(Rect2(local_pt.x - 4.0, local_pt.y - 18.0, 8.0, 16.0), Color(g_col.r, g_col.g, g_col.b, g_alpha), true)
			draw_rect(Rect2(local_pt.x - 2.5, local_pt.y - 16.5, 5.0, 5.0), Color(1.0, 1.0, 1.0, g_alpha * 0.7), true)

	# 1. Draw Awakening / Danger-Zone / Serious Aura around Powered Fighter
	var awk_t: float = float(pnode.get("awakening_timer")) if pnode.get("awakening_timer") != null else 0.0
	var ovh_t: float = float(pnode.get("overheat_timer")) if pnode.get("overheat_timer") != null else 0.0
	var def_t: float = float(pnode.get("bullet_deflect_timer")) if pnode.get("bullet_deflect_timer") != null else 0.0

	if awk_t > 0.0:
		draw_circle(Vector2(0.0, -10.0), 14.5, Color(0.04, 0.05, 0.08, 0.55))
		draw_circle(Vector2(0.0, -10.0), 13.5, Color(aura_col.r, aura_col.g, aura_col.b, 0.30))
		draw_arc(Vector2(0.0, -10.0), 14.5, 0.0, TAU, 20, Color(1.0, 0.96, 0.65, 0.86), 1.6)
	elif ovh_t > 0.0:
		draw_circle(Vector2(0.0, -10.0), 12.5, Color(1.0, 0.25, 0.12, 0.32))
	if def_t > 0.0:
		draw_arc(Vector2(2.0, -10.0), 15.5, -PI * 0.48, PI * 0.48, 16, Color(0.04, 0.06, 0.10, 0.92), 3.6)
		draw_arc(Vector2(2.0, -10.0), 15.5, -PI * 0.45, PI * 0.45, 16, Color(0.35, 0.85, 1.0, 0.95), 2.4)
		draw_arc(Vector2(2.0, -10.0), 15.5, -PI * 0.38, PI * 0.38, 14, Color(1.0, 1.0, 1.0, 0.92), 1.2)

	# 1.5. Draw 3.5-Head Tactical Striker Rig (TS-WP2..WP5: Mau A - Agent Zero & Roster)
	if use_tactical_striker_rig and body_pivot != null and body_pivot.visible:
		var is_carrying_now: bool = (pnode.get("grabbed_target") != null)
		var is_clone_now: bool = bool(pnode.get("is_summon_clone")) if pnode.get("is_summon_clone") != null else false
		var eq_wpn_now: String = ""
		if pnode.has_method("get_equipped_weapon_id"):
			eq_wpn_now = str(pnode.call("get_equipped_weapon_id"))
		var muz_local: Vector2 = Vector2.ZERO
		if aim_pivot != null and muzzle_socket != null:
			muz_local = aim_pivot.position + muzzle_socket.position.rotated(deg_to_rad(current_aim_pitch))
		var needs_rot: bool = current_state in ["DIVE", "FALL_F", "FALL_B", "GRABBED", "ROCKET_RIDE_R", "ROCKET_RIDE_L"] and absf(body_rotation_deg) > 0.1
		if needs_rot:
			draw_set_transform(DEFAULT_BODY_PIVOT, deg_to_rad(body_rotation_deg), Vector2.ONE)
			_PreloadTacticalStrikerRigPainter.draw_tactical_striker_rig(
				self,
				character_id,
				current_state,
				anim_frame_idx,
				current_aim_pitch,
				current_expression_id,
				_breath_phase,
				_is_blinking,
				_is_charred_cached,
				_is_hit_flashing_cached,
				awk_t > 0.0,
				is_carrying_now,
				is_clone_now,
				_blood_alpha_cached,
				muz_local - DEFAULT_BODY_PIVOT,
				eq_wpn_now
			)
			draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
		else:
			_PreloadTacticalStrikerRigPainter.draw_tactical_striker_rig(
				self,
				character_id,
				current_state,
				anim_frame_idx,
				current_aim_pitch,
				current_expression_id,
				_breath_phase,
				_is_blinking,
				_is_charred_cached,
				_is_hit_flashing_cached,
				awk_t > 0.0,
				is_carrying_now,
				is_clone_now,
				_blood_alpha_cached,
				muz_local,
				eq_wpn_now
			)

	# 2. Draw 3-Layer Pixel-Snapped Skill VFX Overlays (SA-WP9: Black Rim -> Elemental Mid -> White Core)
	var vfx_var: Variant = pnode.get("active_vfx_overlays")
	if typeof(vfx_var) == TYPE_ARRAY:
		for item: Variant in vfx_var as Array:
			if typeof(item) != TYPE_DICTIONARY:
				continue
			var vd: Dictionary = item as Dictionary
			var vkind: String = str(vd.get("kind", "beam"))
			var vcol: Color = vd.get("color", aura_col) as Color
			var vlen: float = float(vd.get("length", 64.0))
			var vrad: float = float(vd.get("radius", 24.0))
			var vt: float = float(vd.get("timer", 0.15))
			var vmax: float = maxf(0.05, float(vd.get("max_timer", 0.25)))
			var valpha: float = clampf(vt / vmax, 0.18, 1.0)
			var c_black: Color = Color(0.04, 0.05, 0.08, 0.94 * valpha)
			var c_rim: Color = Color(vcol.r * 0.62, vcol.g * 0.62, vcol.b * 0.72, 0.92 * valpha)
			var c_mid: Color = Color(vcol.r, vcol.g, vcol.b, 0.95 * valpha)
			var c_core: Color = Color(1.0, 0.99, 0.96, 0.98 * valpha)
			match vkind:
				"beam":
					# 3-Layer Kamehameha / Serious Punch / Bijuudama Beam + Charge Sphere + Shockwave Rings
					draw_rect(Rect2(6.0, -17.0, vlen, 13.0), c_black, true)
					draw_rect(Rect2(6.0, -16.0, vlen, 11.0), c_rim, true)
					draw_rect(Rect2(6.0, -14.0, vlen, 7.0), c_mid, true)
					draw_rect(Rect2(6.0, -12.0, vlen, 3.0), c_core, true)
					# Hand convergence sphere
					draw_circle(Vector2(6.0, -10.5), 8.5, c_black)
					draw_circle(Vector2(6.0, -10.5), 7.2, c_mid)
					draw_circle(Vector2(6.0, -10.5), 4.5, c_core)
					# Vertical shockwave rings along beam
					draw_arc(Vector2(18.0, -10.5), 9.5, 0.0, TAU, 16, c_core, 1.4)
					if vlen > 48.0:
						draw_arc(Vector2(38.0, -10.5), 11.0, 0.0, TAU, 16, c_mid, 1.4)
				"stretch_punch":
					# Segmented Rubber Arm (1px black outline + Haki front segment) + Giant Flaming Fist
					draw_rect(Rect2(4.0, -13.5, vlen, 6.0), c_black, true)
					draw_rect(Rect2(4.0, -12.5, vlen * 0.55, 4.0), Color(0.98, 0.76, 0.60, 0.96 * valpha), true)
					draw_rect(Rect2(4.0 + vlen * 0.55, -12.5, vlen * 0.45, 4.0), Color(0.45, 0.12, 0.16, 0.96 * valpha), true)
					var fx: float = 4.0 + vlen
					draw_rect(Rect2(fx - 4.0, -16.5, 13.0, 12.0), c_black, true)
					draw_rect(Rect2(fx - 3.0, -15.5, 11.0, 10.0), c_mid, true)
					draw_rect(Rect2(fx - 1.0, -13.5, 7.0, 6.0), Color(1.0, 0.82, 0.24, 0.96 * valpha), true)
					draw_rect(Rect2(fx + 1.0, -12.0, 4.0, 3.0), c_core, true)
					draw_arc(Vector2(fx + 3.0, -10.5), 9.0, -PI * 0.45, PI * 0.45, 12, c_core, 1.5)
				"whip":
					# Smooth 12-point S-curve Hydro Whip / Chakra Whip with 3 layers + foam crest
					var pts: PackedVector2Array = PackedVector2Array()
					for s_i: int in range(12):
						var t_w: float = float(s_i) / 11.0
						var wx: float = 4.0 + vlen * t_w
						var wy: float = -11.0 + sin(t_w * TAU * 1.25 + vt * 18.0) * 5.5
						pts.append(Vector2(wx, wy))
					draw_polyline(pts, c_black, 6.0)
					draw_polyline(pts, c_rim, 4.4)
					draw_polyline(pts, c_mid, 2.8)
					draw_polyline(pts, c_core, 1.2)
				"shockwave", "dome":
					var r_cur: float = vrad * (1.15 - 0.3 * valpha)
					draw_circle(Vector2(0.0, -9.0), r_cur, Color(vcol.r, vcol.g, vcol.b, 0.24 * valpha))
					draw_arc(Vector2(0.0, -9.0), r_cur + 1.2, 0.0, TAU, 24, c_black, 3.4)
					draw_arc(Vector2(0.0, -9.0), r_cur, 0.0, TAU, 24, c_mid, 2.2)
					draw_arc(Vector2(0.0, -9.0), maxf(2.0, r_cur - 1.2), 0.0, TAU, 24, c_core, 1.2)
				"slash", "crescent":
					var p0: Vector2 = Vector2(-3.0, -19.0)
					var p1: Vector2 = Vector2(vlen, -2.0)
					draw_line(p0, p1, c_black, 6.5)
					draw_line(p0, p1, c_mid, 4.0)
					draw_line(p0, p1, c_core, 1.8)
					var p2: Vector2 = Vector2(-3.0, -2.0)
					var p3: Vector2 = Vector2(vlen, -19.0)
					draw_line(p2, p3, c_black, 5.0)
					draw_line(p2, p3, c_rim, 3.0)
					draw_line(p2, p3, c_core, 1.2)

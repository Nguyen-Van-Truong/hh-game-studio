class_name FighterView
extends Node2D
## Visual-only presenter. The session owns the separate CharacterBody2D.
## Resizing the viewport changes the camera, never gameplay bodies.

const PROFILE = preload("res://game/fighter/fighter_visual_profile.gd")
const PILOT_TEXTURES: Array[Texture2D] = [
	preload("res://art/characters/courier/poses.png"),
	preload("res://art/characters/mechanic/poses.png"),
]
const PILOT_MANIFESTS: Array[String] = [
	"res://art/characters/courier/visual.json",
	"res://art/characters/mechanic/visual.json",
]
const SHEET = preload("res://game/fighter/fighter_pose_sheet.gd")
const WEAPON_VISUALS = preload("res://game/presentation/weapon_visuals.gd")
const SF_BANK = preload("res://game/presentation/sf_classic_bank.gd")

var player_id: int = 1
var body_width: float = 28
var body_height: float = 48
var stamina_capacity: int = 600
var _fighter: Dictionary = {}
var _pose: StringName = &"idle"
var _animation_phase: int = 0
var _pose_start_tick: int = 0
var _last_visual_tick: int = -1
var _clip: StringName = &"idle"
var _sheet: Dictionary = {}
var _texture: Texture2D
var _frame_offset := Vector2.ZERO
var _frame_rotation: float = 0.0

# Presentation scale is deliberately separate from the collision body.  The
# Classic art brief calls for a slightly larger, MUGEN-like readable fighter;
# the simulation still uses the original char_height/char_width values.
const ART_SCALE: float = 1.15

func configure(id: int, width: float, height: float, max_stamina: int) -> void:
	player_id = id
	body_width = width
	body_height = height
	stamina_capacity = max_stamina
	var index: int = clampi(id - 1, 0, PILOT_TEXTURES.size() - 1)
	_texture = PILOT_TEXTURES[index]
	_sheet = SHEET.read_manifest(PILOT_MANIFESTS[index], _texture)
	if _sheet.is_empty():
		push_error("Invalid fighter pose manifest: " + PILOT_MANIFESTS[index])
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	queue_redraw()

func apply_state(state: Dictionary, visual_tick: int = 0) -> void:
	_fighter = state
	_pose = PROFILE.pose_for_state(state)
	var next_clip: StringName = _clip_for_state()
	# Tick is read-only presentation input. Repeated pause/camera redraws do not
	# advance frames; restart/rewind and pose changes reset the local phase.
	if next_clip != _clip or visual_tick < _last_visual_tick or _last_visual_tick < 0:
		_pose_start_tick = visual_tick
	_clip = next_clip
	_last_visual_tick = visual_tick
	_animation_phase = maxi(0, visual_tick - _pose_start_tick)
	position = Vector2(float(state.get(&"x", 0)), float(state.get(&"y", 0)))
	queue_redraw()

func _has_authored_pose() -> bool:
	return _texture != null and not _sheet.is_empty()

func _clip_for_state() -> StringName:
	if _pose != &"attack":
		return _pose
	var action: StringName = StringName(_fighter.get(&"action", &"idle"))
	if action in [&"hit", &"knockdown"]:
		return &"hit"
	var attack: StringName = StringName(_fighter.get(&"attack", &"none"))
	if attack == &"punch_combo" or attack == &"grab_punch":
		return &"punch"
	if attack == &"kick":
		return &"jump_kick"
	if attack == &"tackle":
		return &"dive"
	if attack == &"grab_throw":
		return &"throw"
	return action if attack == &"none" else attack

func _draw() -> void:
	var tint: Color = Color("#45b8ff") if player_id == 1 else Color("#ffb23e")
	if bool(_fighter.get(&"in_pit", false)):
		tint = tint.darkened(0.35)
	var visual_height: float = PROFILE.body_height_for_pose(body_height * ART_SCALE, _pose)
	var half_width: float = float(body_width) * 0.5
	var outline := Color("#08121f")
	var used_classic: bool = _draw_classic_fighter(visual_height)
	if not used_classic:
		if _has_authored_pose():
			_draw_authored_pose()
		else:
			_draw_procedural_body(visual_height, half_width, outline, tint)
		_draw_held_weapon(visual_height, tint)
	elif not _classic_label().begins_with("AIM"):
		_draw_classic_weapon(visual_height)
	if not used_classic and int(_fighter.get(&"burning_ticks", 0)) > 0:
		var flame_phase: float = float(int(_fighter.get(&"burning_ticks", 0)) % 6) * 1.5
		draw_circle(Vector2(-7.0, -visual_height - 5.0 - flame_phase), 6.0, Color("#ff6b35"))
		draw_circle(Vector2(5.0, -visual_height - 2.0 + flame_phase * 0.4), 4.0, Color("#ffd166"))
	var facing: int = int(_fighter.get(&"facing", 1))
	if not used_classic and bool(_fighter.get(&"aiming", false)):
		var aim_angle: float = float(_fighter.get(&"aim_angle", 0.0))
		# Aim reticle is drawn in canvas space after the sprite mirror is reset,
		# so direction must include facing (unlike grip anchors inside the mirror).
		var aim_direction := WeaponVisuals.direction_for(facing, aim_angle, true)
		var aim_origin := Vector2(0.0, -visual_height * 0.56)
		var aim_tip := aim_origin + aim_direction * maxf(42.0, float(body_width) * 1.8)
		var guide_start := aim_origin + aim_direction * 14.0
		var guide_color := Color("#c7f5f3", 0.36)
		draw_line(guide_start, aim_tip, guide_color, 1.0)
		var reticle := PackedVector2Array([
			aim_tip + aim_direction * 5.0,
			aim_tip + aim_direction.rotated(PI * 0.72) * 4.0,
			aim_tip - aim_direction * 5.0,
			aim_tip + aim_direction.rotated(-PI * 0.72) * 4.0,
		])
		draw_polyline(reticle, Color("#e6f4ff", 0.82), 1.4, true)
	# last_damage is cleared by FighterState on the next fixed step, making it
	# a one-frame hit flash without introducing a second presentation clock.
	if int(_fighter.get(&"last_damage", 0)) > 0:
		var hit_center := Vector2(0.0, -visual_height * 0.58)
		var hit_color := Color(1.0, 0.92, 0.55, 0.9)
		draw_circle(hit_center, half_width * 0.72, Color(hit_color, 0.20))
		for spoke: int in range(4):
			var spoke_angle: float = float(spoke) * PI * 0.5 + 0.35
			var spoke_direction := Vector2.from_angle(spoke_angle)
			draw_line(hit_center + spoke_direction * 5.0, hit_center + spoke_direction * 13.0, hit_color, 2.0)
	_draw_action_feedback(visual_height, half_width, facing)
	var sprint_state: Dictionary = _fighter.get(&"sprint", {})
	var stamina_ratio: float = clampf(float(sprint_state.get(&"stamina", 0)) / float(maxi(1, stamina_capacity)), 0.0, 1.0)
	draw_rect(Rect2(-float(body_width) / 2.0, 4.0, float(body_width), 3.0), Color("#273348"))
	draw_rect(Rect2(-float(body_width) / 2.0, 4.0, float(body_width) * stamina_ratio, 3.0), Color("#b6ed70"))

func _draw_procedural_body(visual_height: float, half_width: float, outline: Color, tint: Color) -> void:
	if _pose == &"roll" or _pose == &"dive":
		draw_circle(Vector2(0.0, -visual_height * 0.48), maxf(8.0, half_width * 0.72), tint)
		draw_arc(Vector2(0.0, -visual_height * 0.48), maxf(8.0, half_width * 0.72), 0.0, TAU, 20, outline, 2.0)
	else:
		var facing: float = float(int(_fighter.get(&"facing", 1)))
		var head_radius: float = clampf(visual_height * 0.105, 5.0, 8.0)
		var head := Vector2(0.0, -visual_height + head_radius + 3.0)
		var shoulder: float = half_width * (0.82 if player_id == 1 else 0.96)
		var waist: float = half_width * (0.52 if player_id == 1 else 0.62)
		var torso_top: float = -visual_height * 0.70
		var hip_y: float = -visual_height * 0.28
		var jacket := Color("#176477") if player_id == 1 else Color("#8d3f4b")
		var jacket_light := Color("#36a6a9") if player_id == 1 else Color("#d46d55")
		var cloth := Color("#e7c36d") if player_id == 1 else Color("#8fe0d1")
		var pants := Color("#24304b") if player_id == 1 else Color("#362541")
		var skin := Color("#f1b27b") if player_id == 1 else Color("#d98b68")
		var leg_spread: float = half_width * (0.55 if _pose == &"downed" else (0.40 if player_id == 2 else 0.30))
		var leg_y: float = -visual_height * 0.21
		draw_colored_polygon(PackedVector2Array([Vector2(-waist, hip_y), Vector2(-leg_spread - 3.0, leg_y), Vector2(-leg_spread + 4.0, 0.0), Vector2(-waist * 0.18, leg_y)]), pants)
		draw_colored_polygon(PackedVector2Array([Vector2(waist, hip_y), Vector2(leg_spread + 3.0, leg_y), Vector2(leg_spread - 4.0, 0.0), Vector2(waist * 0.18, leg_y)]), pants)
		draw_line(Vector2(-leg_spread - 4.0, -2.0), Vector2(-leg_spread + 7.0, -2.0), cloth, 3.0)
		draw_line(Vector2(leg_spread - 7.0, -2.0), Vector2(leg_spread + 4.0, -2.0), cloth, 3.0)
		draw_colored_polygon(PackedVector2Array([Vector2(-shoulder, torso_top + 5.0), Vector2(-waist, hip_y), Vector2(waist, hip_y), Vector2(shoulder, torso_top + 5.0)]), jacket)
		draw_colored_polygon(PackedVector2Array([Vector2(-half_width * 0.18, torso_top + 8.0), Vector2(half_width * 0.18, torso_top + 8.0), Vector2(half_width * 0.30, hip_y - 3.0), Vector2(-half_width * 0.30, hip_y - 3.0)]), Color("#f0e1c5"))
		draw_line(Vector2(-shoulder * 0.72, torso_top + 2.0), Vector2(-half_width * 0.35, hip_y - 4.0), jacket_light, 2.0)
		draw_line(Vector2(shoulder * 0.72, torso_top + 2.0), Vector2(half_width * 0.35, hip_y - 4.0), jacket_light, 2.0)
		draw_circle(head, head_radius, skin)
		draw_colored_polygon(PackedVector2Array([head + Vector2(-head_radius, 0.0), head + Vector2(-head_radius * 0.45, -head_radius * 1.15), head + Vector2(head_radius * 0.75, -head_radius * 1.05), head + Vector2(head_radius, -head_radius * 0.15)]), Color("#172333"))
		draw_circle(head + Vector2(facing * head_radius * 0.48, -1.0), 1.35, Color("#f8f0b6"))
		var scarf_tail: float = -facing
		draw_colored_polygon(PackedVector2Array([head + Vector2(-facing * head_radius * 0.45, head_radius * 0.55), head + Vector2(scarf_tail * 17.0, head_radius * 1.75), head + Vector2(scarf_tail * 13.0, head_radius * 2.15)]), cloth)
		var arm_y: float = -visual_height * 0.55
		var arm_length: float = half_width * (1.10 if _pose == &"attack" else (0.88 if _pose == &"aim" else 0.72))
		var hand := Vector2(facing * arm_length, arm_y + (2.0 if _pose == &"attack" else 7.0))
		draw_line(Vector2(facing * half_width * 0.34, arm_y), hand, jacket_light, 6.0)
		draw_line(Vector2(facing * half_width * 0.34, arm_y), hand, outline, 1.5)
		draw_circle(hand, 4.0, Color("#202b3b"))
		draw_line(Vector2(-facing * half_width * 0.30, arm_y + 3.0), Vector2(-facing * half_width * 0.58, arm_y + 10.0), jacket_light, 5.0)

func _draw_authored_pose() -> void:
	var frames: Array = _sheet[&"frames"]
	var frame: Dictionary = frames[_pose_frame_index()]
	var source: Rect2 = frame[&"region"]
	var foot: Vector2 = frame[&"foot"]
	# One standing scale for every frame. Low poses are already low in the art.
	var scale_factor: float = body_height * ART_SCALE / float(frame[&"standing_height"])
	var destination := Rect2(-foot, source.size)
	var facing: float = float(int(_fighter.get(&"facing", 1)))
	var tint := Color(1.0, 1.0, 1.0, 0.42) if bool(_fighter.get(&"in_pit", false)) else Color.WHITE
	var attack: StringName = StringName(_fighter.get(&"attack", &"none"))
	var attack_timer: int = int(_fighter.get(&"attack_timer_ticks", 0))
	var attack_progress: float = 1.0 - clampf(float(attack_timer) / 8.0, 0.0, 1.0)
	var action_offset := Vector2.ZERO
	var action_rotation: float = 0.0
	if _pose == &"idle":
		# Authored idle cells carry the silhouette; this low-amplitude breath keeps
		# a standing fighter alive without moving the deterministic body.
		var breath_phase: float = fmod(float(_animation_phase), 72.0) / 72.0 * TAU
		var breath: float = sin(breath_phase)
		action_offset = Vector2(0.0, breath * 0.75)
		action_rotation = breath * 0.006
	if (attack == &"punch" or attack == &"punch_combo") and attack_timer > 0:
		action_offset = Vector2(facing * (2.0 + attack_progress * 4.0), -attack_progress * 1.5)
		action_rotation = -facing * 0.035 * sin(attack_progress * PI)
	elif attack == &"kick" and attack_timer > 0:
		action_offset = Vector2(facing * (1.0 + attack_progress * 5.0), attack_progress * 1.0)
		action_rotation = facing * 0.06 * sin(attack_progress * PI)
	elif attack == &"tackle" and attack_timer > 0:
		action_offset = Vector2(facing * attack_progress * 7.0, 3.0)
		action_rotation = -facing * 0.045
	elif attack == &"grab_punch" and attack_timer > 0:
		action_offset = Vector2(facing * (3.0 + attack_progress * 4.0), -attack_progress * 1.2)
		action_rotation = -facing * 0.04 * sin(attack_progress * PI)
	elif (attack == &"throw" or attack == &"grab_throw") and attack_timer > 0:
		action_offset = Vector2(-facing * 2.0, -attack_progress * 2.0)
		action_rotation = facing * 0.025 * sin(attack_progress * PI)
	elif attack == &"shoot" and attack_timer > 0:
		action_offset = Vector2(-facing * minf(2.5, float(attack_timer) * 0.7), 0.0)
	# Rotate/translate around the foot pivot, then restore the canvas state. This
	# gives anticipation and recovery without touching physics or replay state.
	_frame_offset = action_offset
	_frame_rotation = action_rotation
	draw_set_transform(action_offset, action_rotation, Vector2(facing * scale_factor, scale_factor))
	var textures: Array[Texture2D] = _sheet[&"textures"]
	var texture: Texture2D = textures[int(frame[&"atlas_index"])]
	draw_texture_rect_region(texture, destination, source, tint)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
	# Team marker remains visible even if both local players later use one skin.
	var team: Color = Color("#72d5ff") if player_id == 1 else Color("#ffc064")
	draw_line(Vector2(-8.0, 1.0), Vector2(8.0, 1.0), team, 2.0)

func _draw_held_weapon(visual_height: float, team_tint: Color) -> void:
	var active_slot: int = int(_fighter.get(&"active_slot", _fighter.get(&"active_weapon_slot", 1)))
	var weapon_id: StringName = StringName(_fighter.get(&"gun_id", &"none"))
	if active_slot == 0:
		weapon_id = StringName(_fighter.get(&"melee_id", &"fists"))
	elif active_slot != 1:
		return
	if weapon_id == &"none" or weapon_id == &"fists":
		return
	if _clip in [&"punch", &"punch_combo", &"kick", &"jump_kick", &"throw", &"downed", &"climb", &"roll", &"dive"] or StringName(_fighter.get(&"action", &"")) in [&"tackle", &"tackle_recover", &"grab", &"grabbed"]:
		return
	var facing: int = 1 if int(_fighter.get(&"facing", 1)) >= 0 else -1
	var aiming: bool = bool(_fighter.get(&"aiming", false)) or _clip == &"shoot"
	var aim_angle: float = float(_fighter.get(&"aim_angle", 0.0))
	var direction: Vector2 = WEAPON_VISUALS.direction_for(facing, aim_angle, aiming)
	var grip: Vector2 = WEAPON_VISUALS.grip_for(body_width, visual_height, facing, aiming)
	if _has_authored_pose():
		var frame: Dictionary = _sheet[&"frames"][_pose_frame_index()]
		var scale_factor: float = body_height * ART_SCALE / float(frame[&"standing_height"])
		# The sprite canvas is mirrored once by draw_set_transform. Anchors stay
		# in the source right-facing frame; multiplying by facing here would mirror
		# the grip a second time and put weapons on the wrong side.
		grip = (Vector2(frame[&"grip"]) - Vector2(frame[&"foot"])) * scale_factor
		grip.x *= float(facing)
		direction = WEAPON_VISUALS.direction_for(facing, aim_angle, aiming)
		grip = grip.rotated(_frame_rotation) + _frame_offset
	var attack: StringName = StringName(_fighter.get(&"attack", &"none"))
	var timer: int = int(_fighter.get(&"attack_timer_ticks", 0))
	var recoil: float = 0.0
	if attack == &"shoot" and timer > 0 and not _has_authored_pose():
		recoil = minf(4.0, float(timer) * 1.25)
	var scale: float = clampf(body_height * ART_SCALE / 55.2, 0.92, 1.62)
	WEAPON_VISUALS.draw_held(self, weapon_id, grip, direction, scale, recoil, team_tint)
	if attack == &"shoot" and timer > 0:
		var muzzle: Vector2 = WEAPON_VISUALS.muzzle_for(weapon_id, grip, direction, scale)
		var normal := Vector2(-direction.y, direction.x)
		var flash: float = clampf(float(timer) / 3.0, 0.0, 1.0)
		draw_colored_polygon(PackedVector2Array([muzzle - direction * 2.0, muzzle + direction * 7.0 + normal * 5.0, muzzle + direction * 18.0, muzzle + direction * 7.0 - normal * 5.0]), Color(1.0, 0.78, 0.22, flash))
		draw_line(muzzle, muzzle + direction * 12.0, Color(1.0, 0.98, 0.78, flash), 2.0)


func _draw_action_feedback(visual_height: float, half_width: float, facing: int) -> void:
	var attack: StringName = StringName(_fighter.get(&"attack", &"none"))
	var timer: int = int(_fighter.get(&"attack_timer_ticks", 0))
	if attack == &"none":
		var action: StringName = StringName(_fighter.get(&"action", &"none"))
		if action in [&"roll", &"roll_recover", &"hit", &"knockdown"]:
			attack = &"roll" if action in [&"roll", &"roll_recover"] else &"hit"
			timer = maxi(timer, 1)
	if attack == &"none" or timer <= 0:
		return
	var progress: float = 1.0 - clampf(float(timer) / 8.0, 0.0, 1.0)
	var accent: Color = Color("#ffcf72") if player_id == 1 else Color("#ff8f68")
	var shoulder := Vector2(float(facing) * half_width * 0.58, -visual_height * 0.57)
	# Punch/kick on Y8 read through body pose only — no visible swing arc overlay.
	if attack == &"dive":
		pass
	elif attack == &"tackle" or StringName(_fighter.get(&"action", &"")) in [&"tackle", &"tackle_recover"]:
		var tackle_center := Vector2(float(facing) * (half_width + 8.0), -visual_height * 0.32)
		draw_arc(tackle_center, 12.0 + progress * 6.0, -PI * 0.75, PI * 0.45, 14, Color(accent, 0.88), 2.4)
		for streak: int in range(3):
			var offset := Vector2(-float(facing) * (12.0 + float(streak) * 5.0), float(streak - 1) * 4.0)
			draw_line(tackle_center + offset, tackle_center + offset - Vector2(float(facing) * 13.0, 0.0), Color(accent, 0.52), 1.6)
	elif attack == &"roll":
		var roll_center := Vector2(-float(facing) * 8.0, -visual_height * 0.42)
		for streak: int in range(3):
			var y_offset: float = float(streak - 1) * 5.0
			draw_line(roll_center + Vector2(-float(facing) * (13.0 + float(streak) * 3.0), y_offset), roll_center + Vector2(-float(facing) * 3.0, y_offset), Color(accent, 0.52 - float(streak) * 0.08), 1.5)
	elif attack == &"hit":
		var guard_center := Vector2(-float(facing) * half_width * 0.12, -visual_height * 0.58)
		draw_arc(guard_center, half_width * 0.72, PI * 0.18, PI * 0.82, 10, Color("#fff0b8", 0.74), 2.0)
		for spoke: int in range(3):
			var direction := Vector2.from_angle(-PI * 0.75 + float(spoke) * PI * 0.25)
			draw_line(guard_center + direction * 8.0, guard_center + direction * 16.0, Color("#ffc76d", 0.72), 1.7)
	elif attack == &"throw" or attack == &"grab_throw":
		var throw_point := shoulder + Vector2(float(facing) * (10.0 + progress * 12.0), -8.0 - progress * 6.0)
		draw_circle(throw_point, 4.0 + progress * 2.0, Color("#d7e77f", 0.95))
		draw_arc(throw_point, 12.0 + progress * 10.0, -PI * 0.85, -PI * 0.15, 14, Color("#f6d98b", 0.65), 1.5)
	elif attack == &"power":
		var center := Vector2(0.0, -visual_height * 0.58)
		var core_radius: float = 4.0 + progress * 4.0
		draw_circle(center, core_radius + 4.0, Color(0.34, 0.86, 1.0, 0.16 + progress * 0.12))
		draw_circle(center, core_radius, Color("#a7e8ff", 0.88))
		draw_arc(center, 15.0 + progress * 11.0, 0.0, TAU, 20, Color("#a7e8ff", 0.78), 2.0)
		for shard: int in range(4):
			var shard_angle: float = float(shard) * PI * 0.5 + progress * 0.8
			var shard_dir := Vector2.from_angle(shard_angle)
			draw_line(center + shard_dir * (8.0 + progress * 5.0), center + shard_dir * (15.0 + progress * 9.0), Color("#d1b6ff", 0.70), 1.5)
	elif StringName(_fighter.get(&"action", &"")) in [&"grab", &"grabbed"]:
		var hold_center := Vector2(float(facing) * (half_width + 10.0), -visual_height * 0.54)
		draw_arc(hold_center, 10.0 + progress * 4.0, -PI * 0.8, PI * 0.7, 16, Color("#f7d57c", 0.88), 2.0)
		draw_circle(hold_center, 3.0, Color("#fff2be", 0.92))

func _pose_frame_index() -> int:
	return SHEET.frame_index(_sheet, _clip, _animation_phase)

func _classic_label() -> String:
	var attack: StringName = StringName(_fighter.get(&"attack", &"none"))
	var gun: String = String(_fighter.get(&"gun_id", &"none"))
	if bool(_fighter.get(&"aiming", false)) or attack == &"shoot" or _clip == &"shoot":
		if gun == "shotgun":
			return "AIM_SHOTGUN"
		if gun == "rocket_launcher":
			return "AIM_BAZOOKA"
		if gun == "grenade" or gun == "grenades":
			return "AIM_GRENADE"
		return "AIM_PISTOL"
	match _clip:
		&"run":
			return "RUN"
		&"sprint":
			return "SPRINT"
		&"jump":
			return "JUMP"
		&"fall":
			return "FALL_F"
		&"climb":
			return "CLIMB"
		&"roll":
			return "ROLL"
		&"dive":
			return "DIVE"
		&"kick", &"jump_kick":
			return "KICK"
		&"punch", &"punch_combo":
			return "PUNCH_0%d" % (1 + _animation_phase % 3)
		&"throw":
			return "THROW"
		&"downed", &"hit":
			return "KNOCKDOWN"
		&"cover":
			return "COVER"
		_:
			return "IDLE"

func _draw_classic_fighter(visual_height: float) -> bool:
	if not SF_BANK.available():
		return false
	var texture: Texture2D = SF_BANK.player_texture(player_id, _classic_label())
	if texture == null:
		texture = SF_BANK.player_texture(player_id, "IDLE")
	if texture == null:
		return false
	var facing: float = float(int(_fighter.get(&"facing", 1)))
	if facing == 0.0:
		facing = 1.0
	var scale_factor: float = visual_height / float(texture.get_height())
	var tint := Color(1.0, 1.0, 1.0, 0.42) if bool(_fighter.get(&"in_pit", false)) else Color.WHITE
	draw_set_transform(Vector2.ZERO, 0.0, Vector2(facing * scale_factor, scale_factor))
	draw_texture(texture, Vector2(-texture.get_width() * 0.5, -texture.get_height()), tint)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
	if int(_fighter.get(&"burning_ticks", 0)) > 0:
		var flame: Texture2D = SF_BANK.frame_texture("fire_circle", 1 + (int(_fighter.get(&"burning_ticks", 0)) % 6))
		if flame != null:
			var flame_scale: float = 1.6
			draw_texture_rect(flame, Rect2(Vector2(-flame.get_width() * flame_scale * 0.5, -visual_height), flame.get_size() * flame_scale), false)
	var team: Color = Color("#72d5ff") if player_id == 1 else Color("#ffc064")
	draw_line(Vector2(-8.0, 1.0), Vector2(8.0, 1.0), team, 2.0)
	return true

func _draw_classic_weapon(visual_height: float) -> void:
	var active_slot: int = int(_fighter.get(&"active_slot", _fighter.get(&"active_weapon_slot", 1)))
	var weapon_id: StringName = StringName(_fighter.get(&"gun_id", &"none"))
	if active_slot == 0:
		weapon_id = StringName(_fighter.get(&"melee_id", &"fists"))
	if weapon_id == &"none" or weapon_id == &"fists":
		return
	var texture: Texture2D = SF_BANK.weapon_texture(weapon_id)
	if texture == null:
		return
	var facing: float = float(int(_fighter.get(&"facing", 1)))
	if facing == 0.0:
		facing = 1.0
	var scale_factor: float = clampf(visual_height / 48.0, 0.8, 2.2)
	var grip := Vector2(facing * body_width * 0.35, -visual_height * 0.55)
	draw_set_transform(grip, 0.0, Vector2(facing * scale_factor, scale_factor))
	draw_texture(texture, Vector2(0.0, -texture.get_height() * 0.5), Color.WHITE)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)

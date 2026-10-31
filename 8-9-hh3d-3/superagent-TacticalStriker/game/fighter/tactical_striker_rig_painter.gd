class_name TacticalStrikerRigPainter
extends RefCounted
## TS-WP2..WP5: 3.5-Head "Tactical Striker" (Mau A - Agent Zero) Articulated 2D Rig Painter.
## Replaces the Superfighters Y8 hunchback 17x21 box and 5x1 black sunglasses bar with:
## - 3.5-Head Athletic S-Curve Spine Anatomy (feet at y=0.0, crown at y=-23.5 world units)
## - 7 Live Facial Expressions with Priority/Hysteresis & Natural Periodic Eye-Blink
## - 360-degree Head & Gaze Aim-Tracking (head tilts smoothly to look along the weapon aim angle)
## - Full 72+ State Kinematics & Bespoke Styling for Agent Zero ("johnny") and all 22 Fighters.

const OUTLINE_DARK: Color = Color(0.06, 0.07, 0.11, 1.0)
const EYE_WHITE: Color = Color(0.99, 0.99, 1.0, 1.0)
const MOUTH_INTERIOR: Color = Color(0.82, 0.24, 0.30, 1.0)
const SWEAT_CYAN: Color = Color(0.45, 0.88, 1.0, 0.92)

static var _agent_zero_pose_tex_cache: Dictionary = {}


static func get_agent_zero_pose_texture(pose_key: String) -> Texture2D:
	if _agent_zero_pose_tex_cache.has(pose_key):
		return _agent_zero_pose_tex_cache[pose_key] as Texture2D
	var res_path: String = "res://assets/sprites/agent_zero/pose_" + pose_key + ".png"
	var abs_path: String = ProjectSettings.globalize_path(res_path)
	if FileAccess.file_exists(abs_path):
		var img: Image = Image.load_from_file(abs_path)
		if img != null and not img.is_empty():
			img.generate_mipmaps()
			var tex: ImageTexture = ImageTexture.create_from_image(img)
			_agent_zero_pose_tex_cache[pose_key] = tex
			return tex
	return null


static func get_expression_priority(expr_id: String) -> int:
	match expr_id:
		"DIZZY_KO":
			return 6
		"HURT_SHOCK":
			return 5
		"ATTACK_SHOUT":
			return 4
		"VICTORY_WINK":
			return 3
		"BATTLE_FOCUS":
			return 2
		"LOW_HP_GRIT":
			return 1
		_:
			return 0


static func get_hud_portrait_key(expr_id: String) -> String:
	match expr_id:
		"DIZZY_KO", "HURT_SHOCK":
			return "hurt"
		"ATTACK_SHOUT":
			return "shout"
		"VICTORY_WINK":
			return "victory"
		"BATTLE_FOCUS", "LOW_HP_GRIT":
			return "fierce"
		_:
			return "confident"


static func evaluate_target_expression(
	state_name: String,
	hp: float,
	max_hp: float,
	is_carrying: bool = false,
	is_victory: bool = false
) -> Dictionary:
	var st: String = state_name.to_upper()
	if hp <= 0.0 or st in ["KNOCKDOWN", "DEAD", "LAY"]:
		return {"id": "DIZZY_KO", "hold": 0.35}
	if st in ["HURT", "FALL_F", "FALL_B", "GRABBED", "ROCKET_RIDE_R", "ROCKET_RIDE_L"]:
		return {"id": "HURT_SHOCK", "hold": 0.28}
	if (
		st.begins_with("PUNCH")
		or st.begins_with("JUMP_PUNCH")
		or st.begins_with("JUMP_KICK")
		or st.begins_with("MACHETE")
		or st.begins_with("AXE")
		or st.begins_with("SWORD")
		or st.begins_with("BAT")
		or st.begins_with("CHAINSAW")
		or st.begins_with("SKILL_")
		or st.begins_with("MUGEN_")
		or st in ["THROW", "GRAB_PUNCH"]
	):
		return {"id": "ATTACK_SHOUT", "hold": 0.22}
	if is_victory or st == "WIN":
		return {"id": "VICTORY_WINK", "hold": 0.50}
	if (
		st in ["RUN", "SPRINT", "ROLL", "DIVE", "CLIMB", "LEDGE_GRAB"]
		or st.begins_with("AIM_")
		or st.begins_with("START_")
		or is_carrying
	):
		return {"id": "BATTLE_FOCUS", "hold": 0.15}
	if hp > 0.0 and hp <= maxf(1.0, max_hp) * 0.30:
		return {"id": "LOW_HP_GRIT", "hold": 0.15}
	return {"id": "CONFIDENT_SMIRK", "hold": 0.0}


static func compute_head_tilt_deg(state_name: String, aim_pitch_deg: float) -> float:
	var st: String = state_name.to_upper()
	if st.begins_with("AIM_") or st.begins_with("START_"):
		return clampf(aim_pitch_deg * 0.48, -36.0, 36.0)
	if st in ["RUN", "SPRINT"]:
		return 8.0
	if st == "JUMP":
		return -6.0
	if st in ["HURT", "FALL_B"]:
		return -16.0
	return 0.0


static func get_character_style(char_id: String, is_awakened: bool = false) -> Dictionary:
	var cid: String = char_id.to_lower()
	# Default: AGENT ZERO ("johnny" - Mẫu A: 3.5-Head Tactical Striker)
	var style: Dictionary = {
		"skin_lit": Color(1.0, 0.86, 0.75, 1.0),
		"skin_mid": Color(0.93, 0.74, 0.61, 1.0),
		"skin_shd": Color(0.76, 0.55, 0.43, 1.0),
		"hair_lit": Color(0.24, 0.29, 0.40, 1.0),
		"hair_mid": Color(0.14, 0.17, 0.25, 1.0),
		"hair_style": "spiky_agent",
		"iris": Color(0.14, 0.58, 0.96, 1.0),
		"jacket_lit": Color(0.23, 0.28, 0.37, 1.0),
		"jacket_mid": Color(0.15, 0.19, 0.26, 1.0),
		"shirt": Color(0.12, 0.68, 0.76, 1.0),
		"glove": Color(0.16, 0.18, 0.23, 1.0),
		"pants_lit": Color(0.25, 0.29, 0.36, 1.0),
		"pants_shd": Color(0.16, 0.19, 0.25, 1.0),
		"boot": Color(0.76, 0.17, 0.21, 1.0),
		"boot_sole": Color(0.95, 0.96, 0.98, 1.0),
		"belt": Color(0.12, 0.14, 0.18, 1.0),
		"scarf": Color(0.0, 0.0, 0.0, 0.0),
		"has_cape": false,
		"has_straw_hat": false,
		"has_headband": false,
		"headband_col": Color(0.88, 0.18, 0.22, 1.0),
		"has_visor": false,
	}
	match cid:
		"goku":
			style["hair_style"] = "goku_spikes"
			if is_awakened:
				style["hair_lit"] = Color(1.0, 0.94, 0.32, 1.0)
				style["hair_mid"] = Color(0.92, 0.72, 0.12, 1.0)
				style["iris"] = Color(0.15, 0.92, 0.78, 1.0)
			else:
				style["hair_lit"] = Color(0.18, 0.20, 0.26, 1.0)
				style["hair_mid"] = Color(0.08, 0.09, 0.13, 1.0)
			style["jacket_lit"] = Color(0.98, 0.46, 0.12, 1.0)
			style["jacket_mid"] = Color(0.82, 0.32, 0.06, 1.0)
			style["shirt"] = Color(0.14, 0.36, 0.78, 1.0)
			style["glove"] = Color(0.14, 0.36, 0.78, 1.0)
			style["pants_lit"] = Color(0.98, 0.46, 0.12, 1.0)
			style["pants_shd"] = Color(0.78, 0.30, 0.06, 1.0)
			style["boot"] = Color(0.14, 0.34, 0.72, 1.0)
			style["belt"] = Color(0.14, 0.36, 0.78, 1.0)
		"luffy":
			style["hair_style"] = "straw_hat"
			style["has_straw_hat"] = true
			style["jacket_lit"] = Color(0.92, 0.18, 0.22, 1.0)
			style["jacket_mid"] = Color(0.72, 0.10, 0.14, 1.0)
			style["shirt"] = Color(0.93, 0.74, 0.61, 1.0)
			style["pants_lit"] = Color(0.18, 0.46, 0.85, 1.0)
			style["pants_shd"] = Color(0.11, 0.30, 0.62, 1.0)
			style["belt"] = Color(0.95, 0.80, 0.20, 1.0)
			style["boot"] = Color(0.72, 0.48, 0.26, 1.0)
		"naruto":
			style["hair_style"] = "spiky_agent"
			style["hair_lit"] = Color(1.0, 0.86, 0.22, 1.0)
			style["hair_mid"] = Color(0.88, 0.66, 0.10, 1.0)
			style["has_headband"] = true
			style["headband_col"] = Color(0.18, 0.36, 0.72, 1.0)
			style["jacket_lit"] = Color(1.0, 0.52, 0.12, 1.0) if not is_awakened else Color(1.0, 0.78, 0.18, 1.0)
			style["jacket_mid"] = Color(0.82, 0.36, 0.06, 1.0)
			style["shirt"] = Color(0.14, 0.16, 0.22, 1.0)
			style["pants_lit"] = Color(0.98, 0.50, 0.12, 1.0)
			style["pants_shd"] = Color(0.78, 0.34, 0.06, 1.0)
			style["boot"] = Color(0.16, 0.24, 0.42, 1.0)
		"saitama":
			style["hair_style"] = "bald"
			style["has_cape"] = true
			style["scarf"] = Color(0.95, 0.97, 1.0, 1.0)
			style["jacket_lit"] = Color(0.98, 0.84, 0.22, 1.0)
			style["jacket_mid"] = Color(0.84, 0.68, 0.12, 1.0)
			style["shirt"] = Color(0.98, 0.84, 0.22, 1.0)
			style["glove"] = Color(0.88, 0.16, 0.20, 1.0)
			style["pants_lit"] = Color(0.96, 0.80, 0.18, 1.0)
			style["pants_shd"] = Color(0.78, 0.62, 0.10, 1.0)
			style["boot"] = Color(0.88, 0.16, 0.20, 1.0)
		"solaria":
			style["hair_lit"] = Color(1.0, 0.98, 0.90, 1.0)
			style["hair_mid"] = Color(0.88, 0.82, 0.68, 1.0)
			style["iris"] = Color(1.0, 0.78, 0.18, 1.0)
			style["jacket_lit"] = Color(0.98, 0.95, 0.88, 1.0)
			style["jacket_mid"] = Color(0.85, 0.78, 0.65, 1.0)
			style["shirt"] = Color(0.98, 0.74, 0.18, 1.0)
			style["glove"] = Color(0.96, 0.72, 0.16, 1.0)
			style["pants_lit"] = Color(0.24, 0.22, 0.30, 1.0)
			style["boot"] = Color(0.92, 0.68, 0.14, 1.0)
		"atlas":
			style["hair_lit"] = Color(0.38, 0.44, 0.54, 1.0)
			style["hair_mid"] = Color(0.24, 0.28, 0.36, 1.0)
			style["has_visor"] = true
			style["iris"] = Color(0.20, 0.92, 1.0, 1.0)
			style["jacket_lit"] = Color(0.28, 0.46, 0.72, 1.0)
			style["jacket_mid"] = Color(0.18, 0.30, 0.52, 1.0)
			style["shirt"] = Color(1.0, 0.54, 0.14, 1.0)
			style["glove"] = Color(1.0, 0.52, 0.14, 1.0)
			style["boot"] = Color(0.24, 0.38, 0.62, 1.0)
		"shinobi":
			style["hair_lit"] = Color(0.72, 0.76, 0.88, 1.0)
			style["hair_mid"] = Color(0.48, 0.52, 0.66, 1.0)
			style["has_headband"] = true
			style["headband_col"] = Color(0.58, 0.24, 0.92, 1.0)
			style["has_cape"] = true
			style["scarf"] = Color(0.56, 0.22, 0.92, 1.0)
			style["iris"] = Color(0.75, 0.32, 1.0, 1.0)
			style["jacket_lit"] = Color(0.20, 0.18, 0.30, 1.0)
			style["jacket_mid"] = Color(0.12, 0.10, 0.20, 1.0)
			style["shirt"] = Color(0.48, 0.20, 0.78, 1.0)
			style["glove"] = Color(0.45, 0.18, 0.75, 1.0)
		"tideweaver":
			style["hair_lit"] = Color(0.92, 0.24, 0.34, 1.0)
			style["hair_mid"] = Color(0.68, 0.14, 0.22, 1.0)
			style["iris"] = Color(0.18, 0.90, 0.96, 1.0)
			style["jacket_lit"] = Color(0.14, 0.58, 0.86, 1.0)
			style["jacket_mid"] = Color(0.08, 0.38, 0.64, 1.0)
			style["shirt"] = Color(0.32, 0.88, 0.96, 1.0)
			style["glove"] = Color(0.16, 0.76, 0.92, 1.0)
			style["boot"] = Color(0.12, 0.46, 0.74, 1.0)
		_:
			if cid != "johnny":
				# Deterministic distinct tactical outfits for the remaining classic roster
				var h_val: float = fmod(float( abs(cid.hash()) % 360 ), 360.0) / 360.0
				style["jacket_lit"] = Color.from_hsv(h_val, 0.55, 0.68, 1.0)
				style["jacket_mid"] = Color.from_hsv(h_val, 0.62, 0.46, 1.0)
				style["shirt"] = Color.from_hsv(fmod(h_val + 0.35, 1.0), 0.50, 0.88, 1.0)
	return style


static func _tint(col: Color, is_charred: bool, is_hit_flash: bool, alpha_mul: float) -> Color:
	if is_charred:
		return Color(0.05, 0.04, 0.04, col.a * alpha_mul)
	if is_hit_flash:
		return Color(
			lerpf(col.r, 1.0, 0.80),
			lerpf(col.g, 1.0, 0.80),
			lerpf(col.b, 1.0, 0.80),
			col.a * alpha_mul
		)
	return Color(col.r, col.g, col.b, col.a * alpha_mul)


static func _draw_caps_limb(
	canvas: CanvasItem,
	p0: Vector2,
	p1: Vector2,
	radius: float,
	fill_col: Color,
	outline_col: Color
) -> void:
	canvas.draw_line(p0, p1, outline_col, radius * 2.0 + 1.5, true)
	canvas.draw_circle(p0, radius + 0.65, outline_col)
	canvas.draw_circle(p1, radius + 0.65, outline_col)
	canvas.draw_line(p0, p1, fill_col, radius * 2.0, true)
	canvas.draw_circle(p0, radius, fill_col)
	canvas.draw_circle(p1, radius, fill_col)


static func draw_tactical_striker_rig(
	canvas: CanvasItem,
	char_id: String,
	state_name: String,
	frame_idx: int,
	aim_pitch_deg: float,
	expr_id: String,
	breath_phase: float,
	is_blinking: bool,
	is_charred: bool,
	is_hit_flash: bool,
	is_awakened: bool,
	is_carrying: bool,
	is_clone: bool,
	blood_alpha: float,
	muzzle_local: Vector2,
	equipped_weapon_id: String = ""
) -> void:
	var st: String = state_name.to_upper()
	var alpha_mul: float = 0.85 if is_clone else 1.0

	# Studio HD-2D Sprite Renderer for Agent Zero ("johnny") and all Classic Tactical Agents
	var cid_low: String = char_id.to_lower()
	var is_powered_hero: bool = cid_low in ["goku", "luffy", "naruto", "saitama", "solaria", "atlas", "shinobi", "tideweaver"]
	if not is_powered_hero:
		var p_key: String = "idle"
		if st == "ROLL" or st == "DIVE":
			p_key = "roll"
		elif st in ["RUN", "SPRINT"]:
			p_key = "run"
		elif st in ["JUMP", "FALL", "CLIMB", "LEDGE_GRAB", "JUMP_KICK"]:
			p_key = "jump"
		elif st.begins_with("AIM_") or st.begins_with("START_"):
			p_key = "aim"
		elif (
			st.begins_with("PUNCH")
			or st.begins_with("JUMP_PUNCH")
			or st.begins_with("MACHETE")
			or st.begins_with("AXE")
			or st.begins_with("SWORD")
			or st.begins_with("BAT")
			or st.begins_with("SKILL_")
			or st.begins_with("MUGEN_")
		):
			p_key = "punch"
		var hd_tex: Texture2D = get_agent_zero_pose_texture(p_key)
		if hd_tex != null:
			var mod_col: Color = Color(1.0, 1.0, 1.0, alpha_mul)
			if cid_low not in ["johnny", "agent_zero"]:
				var h_tint: float = fmod(float(abs(cid_low.hash()) % 360), 360.0) / 360.0
				var c_tint: Color = Color.from_hsv(h_tint, 0.22, 1.04, 1.0)
				mod_col = Color(c_tint.r, c_tint.g, c_tint.b, alpha_mul)
			if is_charred:
				mod_col = Color(0.05, 0.04, 0.04, alpha_mul)
			elif is_hit_flash:
				mod_col = Color(2.4, 2.4, 2.4, alpha_mul)
			var target_h: float = 24.5
			if st in ["KNEEL", "COVER"]:
				target_h = 16.5
			elif p_key == "roll":
				target_h = 18.0
			var aspect: float = float(hd_tex.get_width()) / maxf(1.0, float(hd_tex.get_height()))
			var target_w: float = target_h * aspect
			var bob_h: float = sin(breath_phase) * 0.45 if p_key == "idle" else 0.0
			var d_rect: Rect2 = Rect2(-target_w * 0.46, -target_h - bob_h + 0.5, target_w, target_h + bob_h)
			if st in ["KNOCKDOWN", "DEAD", "LAY"]:
				canvas.draw_set_transform(Vector2(0.0, -4.0), deg_to_rad(-86.0), Vector2.ONE)
				canvas.draw_texture_rect(hd_tex, Rect2(-target_w * 0.5, -target_h * 0.5, target_w, target_h), false, mod_col)
				canvas.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
			elif p_key == "aim" and absf(aim_pitch_deg) > 1.0:
				var aim_tilt: float = deg_to_rad(clampf(aim_pitch_deg * 0.38, -28.0, 28.0))
				canvas.draw_set_transform(Vector2(0.0, -12.0), aim_tilt, Vector2.ONE)
				canvas.draw_texture_rect(hd_tex, Rect2(-target_w * 0.46, -target_h + 12.5, target_w, target_h), false, mod_col)
				canvas.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
			else:
				canvas.draw_texture_rect(hd_tex, d_rect, false, mod_col)
			if p_key == "punch":
				var smear_c: Vector2 = Vector2(target_w * 0.48, -13.0)
				canvas.draw_arc(smear_c, 4.2, -PI * 0.42, PI * 0.42, 10, OUTLINE_DARK, 2.4)
				canvas.draw_arc(smear_c, 4.2, -PI * 0.38, PI * 0.38, 10, Color(1.0, 0.84, 0.25, 0.95 * alpha_mul), 1.5)
				canvas.draw_arc(smear_c + Vector2(0.3, 0.0), 4.2, -PI * 0.25, PI * 0.25, 8, EYE_WHITE, 0.9)
			return
	var style: Dictionary = get_character_style(char_id, is_awakened)
	var out_col: Color = _tint(OUTLINE_DARK, is_charred, is_hit_flash, alpha_mul)
	var skin_lit: Color = _tint(style["skin_lit"], is_charred, is_hit_flash, alpha_mul)
	var skin_mid: Color = _tint(style["skin_mid"], is_charred, is_hit_flash, alpha_mul)
	var hair_lit: Color = _tint(style["hair_lit"], is_charred, is_hit_flash, alpha_mul)
	var hair_mid: Color = _tint(style["hair_mid"], is_charred, is_hit_flash, alpha_mul)
	var j_lit: Color = _tint(style["jacket_lit"], is_charred, is_hit_flash, alpha_mul)
	var j_mid: Color = _tint(style["jacket_mid"], is_charred, is_hit_flash, alpha_mul)
	var shirt_col: Color = _tint(style["shirt"], is_charred, is_hit_flash, alpha_mul)
	var glove_col: Color = _tint(style["glove"], is_charred, is_hit_flash, alpha_mul)
	var p_lit: Color = _tint(style["pants_lit"], is_charred, is_hit_flash, alpha_mul)
	var p_shd: Color = _tint(style["pants_shd"], is_charred, is_hit_flash, alpha_mul)
	var boot_col: Color = _tint(style["boot"], is_charred, is_hit_flash, alpha_mul)
	var sole_col: Color = _tint(style["boot_sole"], is_charred, is_hit_flash, alpha_mul)

	# Special Case 1: ROLL (Compact acrobatic somersault spin at y = -8.5)
	if st == "ROLL":
		var rc: Vector2 = Vector2(0.0, -8.5)
		var rot_a: float = float(frame_idx) * 1.25 + breath_phase * 2.0
		canvas.draw_circle(rc, 6.2, out_col)
		canvas.draw_circle(rc, 5.3, j_lit)
		var h_off: Vector2 = Vector2(cos(rot_a), sin(rot_a)) * 3.0
		canvas.draw_circle(rc + h_off, 2.8, skin_lit)
		canvas.draw_circle(rc - h_off, 2.5, boot_col)
		canvas.draw_arc(rc, 7.2, rot_a, rot_a + PI * 0.85, 10, Color(0.65, 0.90, 1.0, 0.75 * alpha_mul), 1.3)
		return

	# Special Case 2: KNOCKDOWN / DEAD / LAY (Horizontal body resting on floor at y = -3.2)
	if st in ["KNOCKDOWN", "DEAD", "LAY"]:
		var gy: float = -3.0
		_draw_caps_limb(canvas, Vector2(-2.0, gy), Vector2(-9.5, gy + 0.5), 1.6, p_lit, out_col)
		canvas.draw_rect(Rect2(-11.5, gy - 1.5, 3.0, 3.2), boot_col, true)
		_draw_caps_limb(canvas, Vector2(-2.0, gy - 0.5), Vector2(5.0, gy - 1.0), 2.3, j_lit, out_col)
		_draw_sculpted_head_and_face(
			canvas, Vector2(8.2, gy - 1.8), 15.0, "DIZZY_KO", true,
			style, skin_lit, skin_mid, hair_lit, hair_mid, out_col, is_charred, is_hit_flash, alpha_mul
		)
		return

	# Compute 3.5-Head Spine & Limb Joint Coordinates
	var bob: float = sin(breath_phase) * 0.45 if st == "IDLE" else 0.0
	var crouch_drop: float = 5.2 if st in ["KNEEL", "COVER"] else (1.5 if st == "LAND" else 0.0)
	var jump_lift: float = -2.2 if st in ["JUMP", "FALL", "JUMP_PUNCH", "JUMP_KICK"] else 0.0

	var spine_lean: float = 0.0
	if st in ["RUN", "SPRINT"]:
		spine_lean = 2.4
	elif st.begins_with("PUNCH") or st.begins_with("SKILL_") or st.begins_with("MUGEN_"):
		spine_lean = 2.8
	elif st in ["HURT", "FALL_B"]:
		spine_lean = -2.5
	elif st.begins_with("AIM_") or st.begins_with("START_"):
		spine_lean = clampf(aim_pitch_deg * 0.04, -1.6, 1.6)

	var hip: Vector2 = Vector2(0.0, -8.6 + crouch_drop + bob * 0.5 + jump_lift)
	var chest: Vector2 = Vector2(spine_lean, hip.y - (5.2 if crouch_drop > 3.0 else 7.2) + bob)
	var neck_top: Vector2 = chest + Vector2(spine_lean * 0.25, -1.6)
	var head_center: Vector2 = neck_top + Vector2(0.3, -2.8)
	var head_tilt: float = compute_head_tilt_deg(st, aim_pitch_deg)

	# 1. Cape / Scarf behind body
	if bool(style["has_cape"]):
		var sc_col: Color = _tint(style["scarf"], is_charred, is_hit_flash, alpha_mul)
		var wave: float = sin(breath_phase * 2.0 + float(frame_idx)) * 1.4
		var cape_pts: PackedVector2Array = PackedVector2Array([
			chest + Vector2(-1.5, -0.5),
			chest + Vector2(-8.5 - spine_lean, 2.0 + wave),
			chest + Vector2(-9.5 - spine_lean, 7.5 + wave),
			hip + Vector2(-2.0, 1.0)
		])
		canvas.draw_colored_polygon(cape_pts, sc_col)
		canvas.draw_polyline(cape_pts, out_col, 1.1)

	# 2. Legs & High-Top Boots (3.5-Head articulated knees & boots)
	var stride: float = sin(float(frame_idx) * 1.35 + breath_phase * 2.5) if st in ["RUN", "SPRINT"] else 0.0
	var b_knee: Vector2 = hip + Vector2(2.2 - stride * 3.8, 4.2 - crouch_drop * 0.4)
	var b_ankle: Vector2 = Vector2(3.0 - stride * 5.2, -1.8 + jump_lift * 0.6)
	var f_knee: Vector2 = hip + Vector2(-2.0 + stride * 4.2, 4.2 - crouch_drop * 0.4)
	var f_ankle: Vector2 = Vector2(-2.8 + stride * 5.2, -1.8 + jump_lift * 0.6)

	if st == "JUMP_KICK":
		f_knee = hip + Vector2(3.5, 0.5)
		f_ankle = hip + Vector2(9.5, -0.5)
	elif st == "CLIMB":
		var c_alt: float = 1.8 if (frame_idx % 2 == 0) else -1.8
		b_knee = hip + Vector2(2.0, 2.5 + c_alt)
		b_ankle = hip + Vector2(2.0, 6.2 + c_alt)
		f_knee = hip + Vector2(-1.8, 2.5 - c_alt)
		f_ankle = hip + Vector2(-1.8, 6.2 - c_alt)

	# Back Leg + High-Top Boot
	_draw_caps_limb(canvas, hip + Vector2(1.0, 0.0), b_knee, 1.55, p_shd, out_col)
	_draw_caps_limb(canvas, b_knee, b_ankle, 1.40, p_shd, out_col)
	_draw_boot(canvas, b_ankle, boot_col.darkened(0.18), sole_col, out_col)

	# 3. Back Arm (Guard or Stride)
	var sh_back: Vector2 = chest + Vector2(1.8, 0.8)
	var hand_back: Vector2 = sh_back + Vector2(3.8 - stride * 3.0, 2.2)
	if is_carrying:
		hand_back = sh_back + Vector2(5.2, -3.2)
	_draw_caps_limb(canvas, sh_back, hand_back, 1.25, j_mid, out_col)
	canvas.draw_circle(hand_back, 1.55, out_col)
	canvas.draw_circle(hand_back, 1.15, glove_col)

	# 4. V-Tapered S-Curve Torso + Inner Shirt + Tactical Belt
	var torso_pts: PackedVector2Array = PackedVector2Array([
		chest + Vector2(-3.2, -0.5),
		chest + Vector2(3.3, -0.5),
		hip + Vector2(2.3, 0.6),
		hip + Vector2(-2.3, 0.6)
	])
	canvas.draw_colored_polygon(torso_pts, j_lit)
	canvas.draw_polyline( PackedVector2Array([torso_pts[0], torso_pts[1], torso_pts[2], torso_pts[3], torso_pts[0]]), out_col, 1.25 )
	# Inner fitted tee stripe
	canvas.draw_line(chest + Vector2(0.6, 0.2), hip + Vector2(0.4, -0.4), shirt_col, 2.2)
	# Tactical utility belt + silver buckle
	canvas.draw_line(hip + Vector2(-2.4, 0.0), hip + Vector2(2.4, 0.0), _tint(style["belt"], is_charred, is_hit_flash, alpha_mul), 1.8)
	canvas.draw_rect(Rect2(hip.x - 0.6, hip.y - 0.7, 1.6, 1.4), sole_col, true)

	# Battle damage scratches when injured (TS-EC-19)
	if blood_alpha > 0.12 and not is_charred:
		canvas.draw_line(chest + Vector2(-1.5, 1.5), chest + Vector2(1.5, 3.5), Color(0.75, 0.10, 0.14, blood_alpha), 1.1)

	# 5. Front Leg + High-Top Boot
	_draw_caps_limb(canvas, hip + Vector2(-1.0, 0.0), f_knee, 1.65, p_lit, out_col)
	_draw_caps_limb(canvas, f_knee, f_ankle, 1.45, p_lit, out_col)
	_draw_boot(canvas, f_ankle, boot_col, sole_col, out_col)

	# 6. Upright Muscular Neck (Never hunched!)
	canvas.draw_line(chest + Vector2(0.0, -0.4), neck_top + Vector2(0.0, 0.5), out_col, 3.4)
	canvas.draw_line(chest + Vector2(0.0, -0.4), neck_top + Vector2(0.0, 0.5), skin_mid, 2.1)

	# 7. Sculpted 3.5-Head, 7 Live Facial Expressions & Dynamic Hair
	_draw_sculpted_head_and_face(
		canvas, head_center, head_tilt, expr_id, is_blinking,
		style, skin_lit, skin_mid, hair_lit, hair_mid, out_col, is_charred, is_hit_flash, alpha_mul
	)

	# 8. Front Arm, Weapon Aiming & Combat Actions
	var sh_front: Vector2 = chest + Vector2(-1.8, 0.9)
	if st == "LEDGE_GRAB":
		var hook_pt: Vector2 = Vector2(6.0, -18.0)
		_draw_caps_limb(canvas, sh_front, hook_pt, 1.35, j_lit, out_col)
		canvas.draw_circle(hook_pt, 1.6, glove_col)
	elif st.begins_with("AIM_") or st.begins_with("START_"):
		var aim_rad: float = deg_to_rad(aim_pitch_deg)
		var aim_dir: Vector2 = Vector2(cos(aim_rad), sin(aim_rad))
		var grip_pt: Vector2 = sh_front + aim_dir * 5.8
		_draw_caps_limb(canvas, sh_front, grip_pt, 1.35, j_lit, out_col)
		canvas.draw_circle(grip_pt, 1.55, glove_col)
		# Draw weapon aligned from grip_pt to muzzle_local (TS-EC-03)
		var barrel_end: Vector2 = grip_pt + aim_dir * 6.5
		if muzzle_local.length_squared() > 1.0:
			barrel_end = muzzle_local
		var is_heavy_wpn: bool = any_in_name(equipped_weapon_id, ["RIFLE", "SHOTGUN", "SNIPER", "BAZOOKA", "M60", "TOMMY", "LASER", "FLAME"])
		var w_thick: float = 2.6 if is_heavy_wpn else 1.9
		canvas.draw_line(grip_pt - aim_dir * 1.2, barrel_end, out_col, w_thick + 1.4)
		canvas.draw_line(grip_pt - aim_dir * 1.2, barrel_end, Color(0.58, 0.64, 0.74, alpha_mul), w_thick)
	elif (
		st.begins_with("PUNCH")
		or st.begins_with("JUMP_PUNCH")
		or st.begins_with("SKILL_")
		or st.begins_with("MUGEN_")
	):
		var punch_hand: Vector2 = sh_front + Vector2(8.8, -0.4)
		_draw_caps_limb(canvas, sh_front, punch_hand, 1.45, j_lit, out_col)
		canvas.draw_circle(punch_hand, 2.2, out_col)
		canvas.draw_circle(punch_hand, 1.7, glove_col)
		# 3-Layer kinetic punch impact smear arc
		canvas.draw_arc(punch_hand + Vector2(1.0, 0.0), 3.6, -PI * 0.42, PI * 0.42, 10, out_col, 2.4)
		canvas.draw_arc(punch_hand + Vector2(1.0, 0.0), 3.6, -PI * 0.38, PI * 0.38, 10, Color(1.0, 0.84, 0.25, 0.95 * alpha_mul), 1.5)
		canvas.draw_arc(punch_hand + Vector2(1.2, 0.0), 3.6, -PI * 0.25, PI * 0.25, 8, EYE_WHITE, 0.9)
	elif st.begins_with("MACHETE") or st.begins_with("AXE") or st.begins_with("SWORD") or st.begins_with("BAT"):
		var swing_ang: float = -0.85 if frame_idx == 1 else (0.35 if frame_idx == 2 else 0.95)
		var s_dir: Vector2 = Vector2(cos(swing_ang), sin(swing_ang))
		var m_hand: Vector2 = sh_front + s_dir * 5.2
		_draw_caps_limb(canvas, sh_front, m_hand, 1.4, j_lit, out_col)
		canvas.draw_circle(m_hand, 1.6, glove_col)
		var blade_tip: Vector2 = m_hand + s_dir * 8.5
		canvas.draw_line(m_hand, blade_tip, out_col, 2.8)
		canvas.draw_line(m_hand, blade_tip, Color(0.88, 0.94, 1.0, alpha_mul), 1.6)
	else:
		# Athletic bent elbow combat guard
		var elbow_f: Vector2 = sh_front + Vector2(-1.4 + stride * 2.2, 2.8)
		var hand_f: Vector2 = elbow_f + Vector2(3.6, -1.2 + bob * 0.6)
		if is_carrying:
			elbow_f = sh_front + Vector2(2.0, -0.5)
			hand_f = sh_front + Vector2(4.8, -3.5)
		_draw_caps_limb(canvas, sh_front, elbow_f, 1.35, j_lit, out_col)
		_draw_caps_limb(canvas, elbow_f, hand_f, 1.30, skin_lit, out_col)
		canvas.draw_circle(hand_f, 1.75, out_col)
		canvas.draw_circle(hand_f, 1.30, glove_col)


static func any_in_name(wpn_id: String, keys: Array) -> bool:
	var u: String = wpn_id.to_upper()
	for k: Variant in keys:
		if u.contains(str(k)):
			return true
	return false


static func _draw_boot(canvas: CanvasItem, ankle: Vector2, boot_col: Color, sole_col: Color, out_col: Color) -> void:
	var r: Rect2 = Rect2(ankle.x - 1.8, ankle.y - 1.0, 4.4, 2.6)
	canvas.draw_rect(Rect2(r.position.x - 0.6, r.position.y - 0.6, r.size.x + 1.2, r.size.y + 1.2), out_col, true)
	canvas.draw_rect(r, boot_col, true)
	canvas.draw_rect(Rect2(r.position.x, r.end.y - 0.8, r.size.x, 0.8), sole_col, true)


static func _draw_sculpted_head_and_face(
	canvas: CanvasItem,
	hc: Vector2,
	tilt_deg: float,
	expr_id: String,
	is_blinking: bool,
	style: Dictionary,
	skin_lit: Color,
	skin_mid: Color,
	hair_lit: Color,
	hair_mid: Color,
	out_col: Color,
	is_charred: bool,
	is_hit_flash: bool,
	alpha_mul: float
) -> void:
	var t_rad: float = deg_to_rad(tilt_deg)
	var look_off: Vector2 = Vector2(cos(t_rad) - 1.0, sin(t_rad)) * 1.4

	# Sculpted Cranium & Tapered Jaw (Never a blocky square!)
	canvas.draw_circle(hc, 3.65, out_col)
	var jaw_pts: PackedVector2Array = PackedVector2Array([
		hc + Vector2(-2.7, -0.5),
		hc + Vector2(3.1, -0.5),
		hc + Vector2(2.2, 2.8) + look_off * 0.4,
		hc + Vector2(-1.2, 2.7) + look_off * 0.4
	])
	canvas.draw_colored_polygon(jaw_pts, out_col)
	canvas.draw_circle(hc, 2.95, skin_lit)
	var jaw_inner: PackedVector2Array = PackedVector2Array([
		hc + Vector2(-2.1, -0.4),
		hc + Vector2(2.5, -0.4),
		hc + Vector2(1.8, 2.2) + look_off * 0.4,
		hc + Vector2(-0.8, 2.1) + look_off * 0.4
	])
	canvas.draw_colored_polygon(jaw_inner, skin_lit)
	# Ear
	canvas.draw_circle(hc + Vector2(-2.4, 0.4), 0.9, skin_mid)

	# Hair / Headgear (3.5-Head dynamic hair volume)
	var hstyle: String = str(style["hair_style"])
	if hstyle != "bald":
		var h_pts: PackedVector2Array = PackedVector2Array([
			hc + Vector2(-3.4, 0.4),
			hc + Vector2(-3.8, -2.2),
			hc + Vector2(-1.6, -4.2),
			hc + Vector2(1.4, -4.4),
			hc + Vector2(4.0, -2.5),
			hc + Vector2(2.8, -1.2),
			hc + Vector2(3.8, -0.6),
			hc + Vector2(1.2, -1.2),
			hc + Vector2(-2.0, -1.0)
		])
		if hstyle == "goku_spikes":
			h_pts.append(hc + Vector2(-4.8, -1.4))
			h_pts.append(hc + Vector2(4.6, -3.4))
		canvas.draw_colored_polygon(h_pts, hair_mid)
		canvas.draw_polyline(h_pts, out_col, 1.0)
		canvas.draw_circle(hc + Vector2(0.4, -2.6), 1.6, hair_lit)

	if bool(style["has_straw_hat"]):
		canvas.draw_line(hc + Vector2(-4.6, -1.8), hc + Vector2(4.6, -1.8), Color(0.95, 0.78, 0.22, alpha_mul), 1.8)
		canvas.draw_arc(hc + Vector2(0.0, -1.8), 3.1, PI, TAU, 10, Color(0.95, 0.78, 0.22, alpha_mul), 2.4)
		canvas.draw_line(hc + Vector2(-2.8, -2.1), hc + Vector2(2.8, -2.1), Color(0.88, 0.16, 0.20, alpha_mul), 1.1)

	if bool(style["has_headband"]):
		var hb_col: Color = _tint(style["headband_col"], is_charred, is_hit_flash, alpha_mul)
		canvas.draw_line(hc + Vector2(-3.0, -1.2), hc + Vector2(3.1, -1.2), hb_col, 1.4)
		canvas.draw_line(hc + Vector2(-3.0, -1.2), hc + Vector2(-5.8, -0.4), hb_col, 1.2)

	# 7 Live Expressive Eyes, Brows & Mouth (NO Y8 SUNGLASSES!)
	var eye_c: Vector2 = hc + Vector2(1.15, 0.15) + look_off * 0.55
	var iris_col: Color = _tint(style["iris"], is_charred, is_hit_flash, alpha_mul)
	var white_col: Color = _tint(EYE_WHITE, is_charred, is_hit_flash, alpha_mul)
	var mouth_c: Vector2 = hc + Vector2(1.1, 1.55) + look_off * 0.45

	if is_charred or expr_id == "DIZZY_KO":
		# X-eyes KO / Charred
		canvas.draw_line(eye_c + Vector2(-0.8, -0.7), eye_c + Vector2(0.8, 0.7), out_col, 1.1)
		canvas.draw_line(eye_c + Vector2(0.8, -0.7), eye_c + Vector2(-0.8, 0.7), out_col, 1.1)
		canvas.draw_line(mouth_c + Vector2(-0.6, 0.0), mouth_c + Vector2(0.7, 0.0), out_col, 1.0)
		return

	if expr_id == "HURT_SHOCK":
		# Wincing > < eye + shocked open mouth + cyan sweat drop
		canvas.draw_line(eye_c + Vector2(-0.9, -0.7), eye_c + Vector2(0.6, 0.0), out_col, 1.15)
		canvas.draw_line(eye_c + Vector2(0.6, 0.0), eye_c + Vector2(-0.9, 0.7), out_col, 1.15)
		canvas.draw_circle(mouth_c, 0.85, _tint(MOUTH_INTERIOR, is_charred, is_hit_flash, alpha_mul))
		canvas.draw_circle(hc + Vector2(-1.4, -0.4), 0.65, SWEAT_CYAN)
	elif expr_id == "VICTORY_WINK":
		# Happy curved wink ^ + bright smile
		canvas.draw_line(eye_c + Vector2(-0.9, 0.2), eye_c + Vector2(0.0, -0.6), out_col, 1.15)
		canvas.draw_line(eye_c + Vector2(0.0, -0.6), eye_c + Vector2(0.9, 0.2), out_col, 1.15)
		canvas.draw_line(mouth_c + Vector2(-0.9, -0.1), mouth_c + Vector2(0.9, -0.1), white_col, 1.3)
	elif is_blinking and expr_id in ["CONFIDENT_SMIRK", "BATTLE_FOCUS"]:
		# Natural 0.11s periodic blink
		canvas.draw_line(eye_c + Vector2(-0.9, 0.0), eye_c + Vector2(0.9, 0.0), out_col, 1.15)
		canvas.draw_line(mouth_c + Vector2(-0.7, 0.1), mouth_c + Vector2(0.7, -0.2), out_col, 1.0)
	else:
		# 2-Layer Anime Eye (Sclera + Colored Iris + Pupil + White Catchlight)
		canvas.draw_rect(Rect2(eye_c.x - 0.95, eye_c.y - 0.85, 1.9, 1.7), white_col, true)
		canvas.draw_rect(Rect2(eye_c.x - 0.35, eye_c.y - 0.75, 1.25, 1.55), iris_col, true)
		canvas.draw_rect(Rect2(eye_c.x - 0.05, eye_c.y - 0.50, 0.85, 1.10), out_col, true)
		canvas.draw_rect(Rect2(eye_c.x - 0.55, eye_c.y - 0.65, 0.55, 0.55), white_col, true)

		# Expressive Eyebrow
		var brow_slant: float = 0.45 if expr_id in ["BATTLE_FOCUS", "ATTACK_SHOUT", "LOW_HP_GRIT"] else 0.10
		canvas.draw_line(
			eye_c + Vector2(-1.1, -1.25 - brow_slant * 0.5),
			eye_c + Vector2(1.0, -1.25 + brow_slant),
			out_col,
			1.15
		)

		# Expressive Mouth
		if expr_id == "ATTACK_SHOUT":
			canvas.draw_rect(Rect2(mouth_c.x - 0.85, mouth_c.y - 0.55, 1.75, 1.35), _tint(MOUTH_INTERIOR, is_charred, is_hit_flash, alpha_mul), true)
			canvas.draw_line(mouth_c + Vector2(-0.75, -0.45), mouth_c + Vector2(0.75, -0.45), white_col, 0.85)
		elif expr_id == "LOW_HP_GRIT":
			canvas.draw_rect(Rect2(mouth_c.x - 0.85, mouth_c.y - 0.35, 1.7, 0.85), white_col, true)
			canvas.draw_circle(hc + Vector2(-1.3, -0.2), 0.55, SWEAT_CYAN)
		elif expr_id == "BATTLE_FOCUS":
			canvas.draw_line(mouth_c + Vector2(-0.75, 0.0), mouth_c + Vector2(0.75, 0.1), out_col, 1.05)
		else:
			# CONFIDENT_SMIRK upward smirk
			canvas.draw_line(mouth_c + Vector2(-0.75, 0.15), mouth_c + Vector2(0.85, -0.25), out_col, 1.05)

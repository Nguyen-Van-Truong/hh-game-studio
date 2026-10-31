class_name ChibiBrawlerRigPainter
extends RefCounted
## CB-WP2..WP5: 2.5-Head "Chibi-Tactical Expressive Brawler" (Mau B) Layered 2D Presentation Rig.
## - Calibrated 18.0 world-unit neutral skull-to-sole height (Head 40%=7.2u, Torso 32%=5.76u, Legs 28%=5.04u, +2.0u hair crest)
## - 7 Live Facial Expressions with Priority, Anti-Chatter Hysteresis (25%..30% HP) & Periodic Blink
## - Head Aim-Tracking (head_pitch_deg = clamp(aim_pitch_deg * 0.40, -28.0, 28.0)) & Exact Muzzle Socket Alignment
## - Zoom-Aware Face LOD (< 16 screen px) & Distinct Chibi 2.5-Head Identities for All 22 Fighters.

const OUTLINE_DARK: Color = Color(0.06, 0.07, 0.11, 1.0)
const EYE_WHITE: Color = Color(0.99, 0.99, 1.0, 1.0)
const MOUTH_INTERIOR: Color = Color(0.84, 0.22, 0.28, 1.0)
const SWEAT_CYAN: Color = Color(0.38, 0.90, 1.0, 0.95)
const STAR_GOLD: Color = Color(1.0, 0.88, 0.24, 0.98)

const CALIBRATED_BODY_HEIGHT: float = 18.0
const CALIBRATED_TOTAL_HEIGHT: float = 20.0
const ActionPose = preload("res://game/fighter/chibi_action_pose.gd")
const HeadAtlas = preload("res://game/fighter/chibi_head_atlas.gd")
const LimbGeometry = preload("res://game/fighter/chibi_limb_geometry.gd")
const LimbRenderer = preload("res://game/fighter/chibi_limb_renderer.gd")

static func get_expression_priority(expr_id: String) -> int:
	match expr_id:
		"KO_STARS":
			return 6
		"ECSTATIC_VICTORY_LAUGH":
			return 5
		"DIZZY_SPIRAL_HURT":
			return 4
		"WIDE_MOUTH_SHOUT":
			return 3
		"LOW_HP_SWEAT":
			return 2
		"BLAZING_GLARE":
			return 1
		_:
			return 0


static func get_hud_portrait_key(expr_id: String) -> String:
	match expr_id:
		"KO_STARS":
			return "ko_stars"
		"ECSTATIC_VICTORY_LAUGH":
			return "ecstatic_victory_laugh"
		"DIZZY_SPIRAL_HURT":
			return "dizzy_spiral_hurt"
		"WIDE_MOUTH_SHOUT":
			return "wide_mouth_shout"
		"LOW_HP_SWEAT":
			return "low_hp_sweat"
		"BLAZING_GLARE":
			return "blazing_glare"
		_:
			return "cheeky_smirk"


const EXPR_DICT_KO_STARS: Dictionary = {"id": "KO_STARS", "hold": 0.35}
const EXPR_DICT_VICTORY_LAUGH: Dictionary = {"id": "ECSTATIC_VICTORY_LAUGH", "hold": 0.50}
const EXPR_DICT_DIZZY_HURT: Dictionary = {"id": "DIZZY_SPIRAL_HURT", "hold": 0.14}
const EXPR_DICT_SHOUT: Dictionary = {"id": "WIDE_MOUTH_SHOUT", "hold": 0.12}
const EXPR_DICT_SWEAT: Dictionary = {"id": "LOW_HP_SWEAT", "hold": 0.0}
const EXPR_DICT_GLARE: Dictionary = {"id": "BLAZING_GLARE", "hold": 0.10}
const EXPR_DICT_SMIRK: Dictionary = {"id": "CHEEKY_SMIRK", "hold": 0.0}


static func evaluate_target_expression(
	state_name: String,
	hp: float,
	max_hp: float,
	is_carrying: bool = false,
	is_victory: bool = false,
	was_low_hp_sweat: bool = false
) -> Dictionary:
	var st: String = state_name if state_name == state_name.to_upper() else state_name.to_upper()
	# Priority 6: Dead / KO (CB-EC-10: KO always beats victory/hurt; temporary KNOCKDOWN with hp > 0 is HURT)
	if hp <= 0.0 or st in ["DEAD", "DEATH_KNEEL", "LAY"]:
		return EXPR_DICT_KO_STARS
	# Priority 5: Round winner still alive (CB-EC-10)
	if (is_victory or st == "WIN") and hp > 0.0:
		return EXPR_DICT_VICTORY_LAUGH
	# Priority 4: Hurt / Stun / Knockdown / Rocket Ride (CB-EC-09)
	if st in [
		"HURT",
		"STUN_01",
		"STUN_02",
		"STAGGER",
		"KNOCKDOWN",
		"FALL_F",
		"FALL_B",
		"GRABBED",
		"ROCKET_RIDE_R",
		"ROCKET_RIDE_L",
	]:
		return EXPR_DICT_DIZZY_HURT
	# Priority 3: Active Melee Attack or Skill Cast
	if (
		st.begins_with("PUNCH")
		or st.begins_with("JUMP_PUNCH")
		or st.begins_with("JUMP_KICK")
		or st.begins_with("JUMPKICK")
		or st.begins_with("JUMP_ATT")
		or st == "KICK"
		or st.begins_with("MACHETE")
		or st.begins_with("AXE")
		or st.begins_with("SWORD")
		or st.begins_with("BAT")
		or st.begins_with("PIPE")
		or st.begins_with("CHAINSAW")
		or st.begins_with("SKILL_")
		or st.begins_with("MUGEN_")
		or st in ["THROW", "GRAB_PUNCH", "SHUNPO_SLASH", "CHAKRA_WAVE"]
	):
		return EXPR_DICT_SHOUT
	# Priority 2: Low HP Sweat with Hysteresis (CB-EC-11: enters <= 25%, exits only > 30%)
	var safe_max: float = maxf(1.0, max_hp)
	var hp_ratio: float = hp / safe_max
	var low_hp_threshold: float = 0.30 if was_low_hp_sweat else 0.25
	if hp > 0.0 and hp_ratio <= low_hp_threshold:
		return EXPR_DICT_SWEAT
	# Priority 1: Blazing Glare on Sprint / Aim / Roll / Dive / Climb / Carry
	if (
		st in ["SPRINT", "ROLL", "DIVE", "CLIMB", "SLIDE", "LEDGE_GRAB"]
		or st.begins_with("AIM_")
		or st.begins_with("START_")
		or is_carrying
	):
		return EXPR_DICT_GLARE
	# Priority 0: Cheeky Confident Smirk (default IDLE / RUN)
	return EXPR_DICT_SMIRK


static func sanitize_aim_pitch_deg(raw_pitch_deg: float) -> float:
	if is_nan(raw_pitch_deg) or is_inf(raw_pitch_deg):
		return 0.0
	return clampf(raw_pitch_deg, -90.0, 90.0)


static func compute_head_tilt_deg(state_name: String, aim_pitch_deg: float) -> float:
	var clean_pitch: float = sanitize_aim_pitch_deg(aim_pitch_deg)
	var st: String = state_name.to_upper()
	if st.begins_with("AIM_") or st.begins_with("START_"):
		return clampf(clean_pitch * 0.40, -28.0, 28.0)
	if st in ["RUN", "SPRINT"]:
		return 7.0
	if st in ["JUMP", "JUMPKICK", "JUMP_KICK"]:
		return -5.0
	if st in ["HURT", "FALL_B", "STUN_01", "STUN_02"]:
		return -14.0
	return 0.0


static func get_character_style(char_id: String, is_awakened: bool = false) -> Dictionary:
	var cid: String = char_id.to_lower()
	# Default: Golden Fighter "Agent Zero / Johnny" — 2.5-Head Chibi Brawler (Orange/Navy Hoodie + Highlight)
	var style: Dictionary = {
		"character_id": cid + "_awakened" if is_awakened and cid in ["goku", "naruto"] else cid,
		"use_procedural_head": false,
		"skin_lit": Color(1.0, 0.85, 0.73, 1.0),
		"skin_mid": Color(0.92, 0.72, 0.58, 1.0),
		"hair_lit": Color(0.36, 0.24, 0.18, 1.0),
		"hair_mid": Color(0.22, 0.14, 0.11, 1.0),
		"hair_streak": Color(1.0, 0.47, 0.18, 1.0),
		"hair_style": "chibi_spikes",
		"iris": Color(0.55, 0.34, 0.18, 1.0),
		"hoodie_lit": Color(1.0, 0.50, 0.14, 1.0),
		"hoodie_mid": Color(0.14, 0.17, 0.24, 1.0),
		"sleeve": Color(0.58, 0.64, 0.72, 1.0),
		"glove": Color(0.16, 0.20, 0.28, 1.0),
		"glove_trim": Color(1.0, 0.52, 0.16, 1.0),
		"handwear": "bare",
		"wristband": false,
		"shorts": Color(0.15, 0.19, 0.27, 1.0),
		"sneaker": Color(0.14, 0.18, 0.26, 1.0),
		"sneaker_sole": Color(0.96, 0.97, 0.99, 1.0),
		"scarf": Color(0.0, 0.0, 0.0, 0.0),
		"has_cape": false,
		"has_straw_hat": false,
		"has_headband": false,
		"headband_col": Color(0.88, 0.18, 0.22, 1.0),
		"has_visor": false,
		"glasses": false,
		"beard": false,
		"hat": "none",
		"outfit": "hoodie",
		"badge": Color(1.0, 0.69, 0.22),
	}
	match cid:
		"boris":
			style.merge({"hair_style": "bald", "skin_lit": Color("c18e68"), "skin_mid": Color("966447"), "hoodie_lit": Color("617354"), "hoodie_mid": Color("344438"), "sleeve": Color("617354"), "outfit": "tactical", "beard": true}, true)
		"agent":
			style.merge({"hair_style": "slick", "hair_lit": Color("3b414e"), "hair_mid": Color("151c27"), "hair_streak": Color("596174"), "hoodie_lit": Color("39475e"), "hoodie_mid": Color("182334"), "sleeve": Color("39475e"), "glasses": true, "outfit": "suit"}, true)
		"hideki":
			style.merge({"hair_style": "swept", "hair_lit": Color("303b52"), "hair_mid": Color("131a29"), "hair_streak": Color("6d87aa"), "has_headband": true, "headband_col": Color("c53c4b"), "hoodie_lit": Color("587a9b"), "hoodie_mid": Color("263f5c"), "sleeve": Color("c9d5d5"), "outfit": "wrap"}, true)
		"blaire":
			style.merge({"hair_style": "ponytail", "hair_lit": Color("ffe4a0"), "hair_mid": Color("b98841"), "hair_streak": Color("fff4cd"), "hoodie_lit": Color("579ea8"), "hoodie_mid": Color("2d526a"), "sleeve": Color("638b9b"), "iris": Color("3b8a9f"), "outfit": "jacket"}, true)
		"savage":
			style.merge({"hair_style": "mohawk", "hair_lit": Color("be6f3e"), "hair_mid": Color("733d29"), "hair_streak": Color("e2a467"), "has_headband": true, "headband_col": Color("a8463b"), "hoodie_lit": Color("7d8350"), "hoodie_mid": Color("434c34"), "sleeve": Color("a97c58"), "outfit": "tactical"}, true)
		"cruger":
			style.merge({"hair_style": "slick", "hair_lit": Color("77543f"), "hair_mid": Color("422d25"), "hair_streak": Color("b08c63"), "hoodie_lit": Color("ba9b70"), "hoodie_mid": Color("625747"), "sleeve": Color("a08967"), "hat": "brim", "beard": true, "outfit": "coat"}, true)
		"ivan":
			style.merge({"hair_style": "crop", "hair_lit": Color("78604b"), "hair_mid": Color("463a30"), "hair_streak": Color("b39b7a"), "hoodie_lit": Color("8f6655"), "hoodie_mid": Color("453f41"), "sleeve": Color("8f6655"), "hat": "winter", "beard": true, "outfit": "coat"}, true)
		"brody":
			style.merge({"hair_style": "crop", "hair_lit": Color("5b4138"), "hair_mid": Color("302521"), "hair_streak": Color("a97450"), "hoodie_lit": Color("d36755"), "hoodie_mid": Color("713b40"), "sleeve": Color("ddd3ba"), "hat": "cap", "outfit": "jacket"}, true)
		"mac":
			style.merge({"skin_lit": Color("a97255"), "skin_mid": Color("7b4e3c"), "hair_style": "flat_top", "hair_lit": Color("343038"), "hair_mid": Color("191b22"), "hair_streak": Color("665453"), "hoodie_lit": Color("38928d"), "hoodie_mid": Color("244e54"), "sleeve": Color("38928d"), "outfit": "tactical"}, true)
		"billy":
			style.merge({"hair_style": "swept", "hair_lit": Color("b7c5cb"), "hair_mid": Color("738993"), "hair_streak": Color("e4edef"), "hoodie_lit": Color("e4e6dc"), "hoodie_mid": Color("688997"), "sleeve": Color("d0d6d5"), "glasses": true, "outfit": "coat", "badge": Color("64d7d1")}, true)
		"scott":
			style.merge({"hair_style": "swept", "hair_lit": Color("a36945"), "hair_mid": Color("603a2b"), "hair_streak": Color("d3a071"), "hoodie_lit": Color("5685b4"), "hoodie_mid": Color("293f64"), "sleeve": Color("cad3d6"), "outfit": "jacket"}, true)
		"funnyman":
			style.merge({"skin_lit": Color("f3ded8"), "skin_mid": Color("d1ada9"), "hair_style": "mohawk", "hair_lit": Color("b664c9"), "hair_mid": Color("643e83"), "hair_streak": Color("f3a3d7"), "hoodie_lit": Color("a85a9b"), "hoodie_mid": Color("3b7e83"), "sleeve": Color("ce9464"), "outfit": "clown", "iris": Color("6a4496")}, true)
		"jeff":
			style.merge({"hair_style": "ponytail", "hair_lit": Color("cb8a55"), "hair_mid": Color("7b4a30"), "hair_streak": Color("efbe7e"), "hoodie_lit": Color("6f7182"), "hoodie_mid": Color("313440"), "sleeve": Color("a89a87"), "beard": true, "outfit": "jacket"}, true)
		"goku":
			style["wristband"] = true
			style["hair_style"] = "goku_spikes"
			if is_awakened:
				style["hair_lit"] = Color(1.0, 0.94, 0.32, 1.0)
				style["hair_mid"] = Color(0.92, 0.72, 0.12, 1.0)
				style["hair_streak"] = Color(1.0, 0.99, 0.75, 1.0)
				style["iris"] = Color(0.15, 0.92, 0.78, 1.0)
			else:
				style["hair_lit"] = Color(0.18, 0.20, 0.26, 1.0)
				style["hair_mid"] = Color(0.08, 0.09, 0.13, 1.0)
				style["hair_streak"] = Color(0.28, 0.32, 0.42, 1.0)
			style["hoodie_lit"] = Color(0.98, 0.46, 0.12, 1.0)
			style["hoodie_mid"] = Color(0.14, 0.36, 0.78, 1.0)
			style["sleeve"] = Color(0.98, 0.46, 0.12, 1.0)
			style["glove"] = Color(0.14, 0.36, 0.78, 1.0)
			style["shorts"] = Color(0.96, 0.42, 0.10, 1.0)
			style["sneaker"] = Color(0.14, 0.34, 0.72, 1.0)
		"luffy":
			style["hair_style"] = "straw_hat"
			style["has_straw_hat"] = true
			style["hair_lit"] = Color(0.15, 0.16, 0.20, 1.0)
			style["hair_mid"] = Color(0.08, 0.09, 0.12, 1.0)
			style["hoodie_lit"] = Color(0.92, 0.18, 0.22, 1.0)
			style["hoodie_mid"] = Color(0.72, 0.10, 0.14, 1.0)
			style["sleeve"] = Color(1.0, 0.85, 0.73, 1.0)
			style["shorts"] = Color(0.18, 0.46, 0.85, 1.0)
			style["sneaker"] = Color(0.72, 0.48, 0.26, 1.0)
		"naruto":
			style["hair_style"] = "chibi_spikes"
			style["hair_lit"] = Color(1.0, 0.86, 0.22, 1.0)
			style["hair_mid"] = Color(0.88, 0.66, 0.10, 1.0)
			style["hair_streak"] = Color(1.0, 0.95, 0.55, 1.0)
			style["has_headband"] = true
			style["headband_col"] = Color(0.18, 0.36, 0.72, 1.0)
			style["iris"] = Color(0.18, 0.58, 0.96, 1.0)
			style["hoodie_lit"] = Color(1.0, 0.52, 0.12, 1.0) if not is_awakened else Color(1.0, 0.78, 0.18, 1.0)
			style["hoodie_mid"] = Color(0.14, 0.16, 0.22, 1.0)
			style["sleeve"] = Color(1.0, 0.52, 0.12, 1.0)
			style["shorts"] = Color(0.96, 0.48, 0.10, 1.0)
			style["sneaker"] = Color(0.16, 0.24, 0.42, 1.0)
		"saitama":
			style["handwear"] = "glove"
			style["hair_style"] = "bald"
			style["has_cape"] = true
			style["scarf"] = Color(0.95, 0.97, 1.0, 1.0)
			style["hoodie_lit"] = Color(0.98, 0.84, 0.22, 1.0)
			style["hoodie_mid"] = Color(0.84, 0.68, 0.12, 1.0)
			style["sleeve"] = Color(0.98, 0.84, 0.22, 1.0)
			style["glove"] = Color(0.88, 0.16, 0.20, 1.0)
			style["shorts"] = Color(0.92, 0.76, 0.16, 1.0)
			style["sneaker"] = Color(0.88, 0.16, 0.20, 1.0)
		"solaria":
			style["handwear"] = "glove"
			style["hair_lit"] = Color(1.0, 0.96, 0.78, 1.0)
			style["hair_mid"] = Color(0.92, 0.78, 0.38, 1.0)
			style["hair_streak"] = Color(1.0, 0.62, 0.16, 1.0)
			style["iris"] = Color(1.0, 0.78, 0.18, 1.0)
			style["hoodie_lit"] = Color(0.98, 0.94, 0.84, 1.0)
			style["hoodie_mid"] = Color(0.96, 0.70, 0.16, 1.0)
			style["glove"] = Color(0.96, 0.72, 0.16, 1.0)
			style["sneaker"] = Color(0.92, 0.68, 0.14, 1.0)
		"atlas":
			style["handwear"] = "gauntlet"
			style["hair_lit"] = Color(0.38, 0.44, 0.54, 1.0)
			style["hair_mid"] = Color(0.24, 0.28, 0.36, 1.0)
			style["has_visor"] = true
			style["iris"] = Color(0.20, 0.92, 1.0, 1.0)
			style["hoodie_lit"] = Color(0.28, 0.46, 0.72, 1.0)
			style["hoodie_mid"] = Color(1.0, 0.54, 0.14, 1.0)
			style["glove"] = Color(1.0, 0.52, 0.14, 1.0)
			style["sneaker"] = Color(0.24, 0.38, 0.62, 1.0)
		"shinobi":
			style["hair_lit"] = Color(0.76, 0.80, 0.92, 1.0)
			style["hair_mid"] = Color(0.48, 0.52, 0.66, 1.0)
			style["hair_streak"] = Color(0.68, 0.32, 1.0, 1.0)
			style["has_headband"] = true
			style["headband_col"] = Color(0.58, 0.24, 0.92, 1.0)
			style["has_cape"] = true
			style["scarf"] = Color(0.56, 0.22, 0.92, 1.0)
			style["iris"] = Color(0.75, 0.32, 1.0, 1.0)
			style["hoodie_lit"] = Color(0.22, 0.18, 0.34, 1.0)
			style["hoodie_mid"] = Color(0.48, 0.20, 0.78, 1.0)
			style["glove"] = Color(0.45, 0.18, 0.75, 1.0)
		"tideweaver":
			style["handwear"] = "glove"
			style["hair_lit"] = Color(0.92, 0.26, 0.38, 1.0)
			style["hair_mid"] = Color(0.68, 0.14, 0.22, 1.0)
			style["hair_streak"] = Color(0.28, 0.92, 0.98, 1.0)
			style["iris"] = Color(0.18, 0.90, 0.96, 1.0)
			style["hoodie_lit"] = Color(0.14, 0.62, 0.88, 1.0)
			style["hoodie_mid"] = Color(0.08, 0.38, 0.64, 1.0)
			style["glove"] = Color(0.16, 0.76, 0.92, 1.0)
			style["sneaker"] = Color(0.12, 0.46, 0.74, 1.0)
	if cid in ["johnny", "boris", "mac", "savage", "shinobi"]:
		style["handwear"] = "fingerless"
	style["sleeve_coverage"] = "bare" if cid in ["goku", "luffy", "savage"] else "long"
	if cid == "goku":
		style["sleeve_coverage"] = "short"
		style["sleeve"] = style["hoodie_mid"]
		style["outfit"] = "gi"
	elif cid == "luffy":
		style["outfit"] = "vest"
	elif cid == "saitama":
		style["outfit"] = "hero_suit"
	return style


static func _tint(col: Color, is_charred: bool, is_hit_flash: bool, alpha_mul: float) -> Color:
	return LimbRenderer.tint_color(col, is_charred, is_hit_flash, alpha_mul)


static func _draw_expression_world_badges(
	canvas: CanvasItem,
	head_top: Vector2,
	expr_id: String,
	breath_phase: float,
	is_charred: bool,
	alpha_mul: float,
	is_burning: bool = false
) -> void:
	if is_charred:
		return
	if expr_id == "KO_STARS":
		for i: int in range(3):
			var ang: float = breath_phase * 2.5 + float(i) * (TAU / 3.0)
			var sc: Vector2 = head_top + Vector2(cos(ang) * 4.2, sin(ang) * 1.1 - 0.8)
			canvas.draw_circle(sc, 1.35, OUTLINE_DARK)
			canvas.draw_circle(sc, 0.95, Color(STAR_GOLD.r, STAR_GOLD.g, STAR_GOLD.b, alpha_mul))
	elif expr_id in ["LOW_HP_SWEAT", "DIZZY_SPIRAL_HURT"] or is_burning:
		var sw_col: Color = Color(SWEAT_CYAN.r, SWEAT_CYAN.g, SWEAT_CYAN.b, alpha_mul)
		var sw_pt: Vector2 = head_top + Vector2(-5.1, 4.4)
		_draw_cel_polygon(canvas, PackedVector2Array([
			sw_pt + Vector2(0.9, -1.0),
			sw_pt + Vector2(-0.5, 0.2),
			sw_pt + Vector2(-0.2, 0.9),
			sw_pt + Vector2(0.5, 0.5),
		]), sw_col, OUTLINE_DARK, 0.42)
		if is_burning:
			var panic_bob: float = sin(breath_phase * 3.0) * 0.45
			var sw_r: Vector2 = head_top + Vector2(5.1, 4.0 + panic_bob)
			_draw_cel_polygon(canvas, PackedVector2Array([
				sw_r + Vector2(-0.9, -1.0),
				sw_r + Vector2(-0.5, 0.5),
				sw_r + Vector2(0.2, 0.9),
				sw_r + Vector2(0.5, 0.2),
			]), sw_col, OUTLINE_DARK, 0.42)


static func draw_chibi_brawler_rig(
	canvas: CanvasItem,
	char_id: String,
	state_name: String,
	frame_idx: int,
	aim_pitch_deg: float,
	expr_id: String,
	_breath_phase: float,
	is_blinking: bool,
	is_charred: bool,
	is_hit_flash: bool,
	is_awakened: bool,
	is_carrying: bool,
	is_clone: bool,
	blood_alpha: float,
	_muzzle_local: Vector2,
	equipped_weapon_id: String = "",
	camera_zoom_x: float = 2.8,
	source_frame: float = -1.0,
	body_rotation_deg: float = 0.0,
	presentation_transform: Transform2D = Transform2D.IDENTITY,
	stance: String = "",
	motion: Dictionary = {}
) -> void:
	# R5: one articulated renderer for all 22 identities. Presentation only;
	# source sockets stay authoritative; ChibiWeaponView owns gun art and hands.
	canvas.draw_set_transform_matrix(presentation_transform)
	var pose: Dictionary = ActionPose.sample(state_name, frame_idx, aim_pitch_deg, is_carrying, source_frame, body_rotation_deg, stance, motion)
	if str(pose["family"]) == "empty":
		return
	var alpha: float = 0.85 if is_clone else 1.0
	var style: Dictionary = get_character_style(char_id, is_awakened)
	var is_burning_active: bool = (bool(pose.get("burning_overlay", false)) or bool(motion.get("burning", false))) and not is_charred and not is_hit_flash
	var outline: Color = _tint(OUTLINE_DARK, is_charred, is_hit_flash, alpha)
	var shirt: Color = _tint(style["hoodie_lit"], is_charred, is_hit_flash, alpha)
	var shade: Color = _tint(style["hoodie_mid"], is_charred, is_hit_flash, alpha)
	var sleeve: Color = _tint(style["sleeve"], is_charred, is_hit_flash, alpha)
	var glove: Color = _tint(style["glove"], is_charred, is_hit_flash, alpha)
	var trim: Color = _tint(style["glove_trim"], is_charred, is_hit_flash, alpha)
	var pants: Color = _tint(style["shorts"], is_charred, is_hit_flash, alpha)
	var boot: Color = _tint(style["sneaker"], is_charred, is_hit_flash, alpha)
	var sole: Color = _tint(style["sneaker_sole"], is_charred, is_hit_flash, alpha)
	var skin: Color = _tint(style["skin_lit"], is_charred, is_hit_flash, alpha)
	if is_burning_active:
		# Warm fiery rim-illumination cast onto clothing and skin while ablaze
		var fire_glow: Color = Color(1.0, 0.46, 0.10, alpha)
		shirt = shirt.lerp(fire_glow, 0.22)
		sleeve = sleeve.lerp(fire_glow, 0.22)
		pants = pants.lerp(fire_glow, 0.18)
		skin = skin.lerp(Color(1.0, 0.72, 0.42, alpha), 0.16)
	var handwear: String = str(style["handwear"])
	var wristband: bool = bool(style["wristband"])
	var sleeve_coverage: String = str(style["sleeve_coverage"])
	var root_angle: float = deg_to_rad(float(pose["root_rotation_deg"]))
	var root_origin: Vector2 = pose["root_origin"]
	for key: String in ["hip", "chest", "head", "shoulder_front", "shoulder_back", "elbow_front", "elbow_back", "hand_front", "hand_back", "hip_front", "hip_back", "knee_front", "knee_back", "ankle_front", "ankle_back"]:
		pose[key] = root_origin + (pose[key] as Vector2).rotated(root_angle)
	var chest: Vector2 = pose["chest"]
	var hip: Vector2 = pose["hip"]
	var head: Vector2 = pose["head"]
	var side: Vector2 = Vector2.RIGHT.rotated(root_angle)
	var down: Vector2 = (hip - chest).normalized()
	var split: bool = bool(pose["split_arms"])
	var is_back_view: bool = str(pose["family"]) in ["climb", "slide"]
	var clock: float = float(pose["source_frame"])
	var clean_zoom: float = clampf(camera_zoom_x, 0.1, 32.0) if is_finite(camera_zoom_x) else 2.8

	# Cape silhouette follows this same sampled frame and stays behind the limbs in normal view.
	if bool(style["has_cape"]) and not is_back_view:
		var scarf: Color = _tint(style["scarf"], is_charred, is_hit_flash, alpha)
		var wave: float = sin(fposmod(clock, 12.0) * TAU / 12.0) * 0.8
		_draw_cel_polygon(canvas, PackedVector2Array([
			chest - side * 1.8,
			chest - side * 6.4 + down * (1.4 + wave),
			hip - side * 7.3 + down * 1.2,
			hip - side * 2.0,
		]), scarf, outline, 0.65)
		canvas.draw_line(chest - side * 3.3 + down, hip - side * 5.0, scarf.lightened(0.18), 0.7, true)

	# In rear-view ladder climbing/sliding, arms reach forward into the ladder rungs behind the torso and head.
	if is_back_view and not split:
		LimbRenderer.draw_arm(canvas, pose["shoulder_back"], pose["elbow_back"], pose["hand_back"], sleeve.darkened(0.08), skin.darkened(0.06), glove.darkened(0.08), trim, outline, false, str(pose["hand_back_shape"]), handwear, wristband, sleeve_coverage)
		LimbRenderer.draw_arm(canvas, pose["shoulder_front"], pose["elbow_front"], pose["hand_front"], sleeve, skin, glove, trim, outline, false, str(pose["hand_front_shape"]), handwear, wristband, sleeve_coverage)

	# Back leg, articulated at hip/knee/ankle, with a visibly bent running knee.
	_draw_jointed_leg(canvas, pose["hip_back"], pose["knee_back"], pose["ankle_back"], pants.darkened(0.08 if is_back_view else 0.18), boot.darkened(0.08 if is_back_view else 0.14), sole, outline, root_angle)
	_draw_jointed_leg(canvas, pose["hip_front"], pose["knee_front"], pose["ankle_front"], pants, boot, sole, outline, root_angle)
	if str(pose["family"]) in ["kick", "jumpkick"] and bool(pose["contact"]):
		var k_foot: Vector2 = pose["ankle_front"]
		var k_knee: Vector2 = pose["knee_front"]
		var k_dir: Vector2 = (k_foot - k_knee).normalized()
		canvas.draw_polyline(PackedVector2Array([k_knee - k_dir.orthogonal() * 1.2, k_foot + k_dir * 1.2, k_foot + k_dir * 2.8]), Color(trim.r, trim.g, trim.b, 0.62), 1.25, true)
	if not split and not is_back_view:
		LimbRenderer.draw_arm(canvas, pose["shoulder_back"], pose["elbow_back"], pose["hand_back"], sleeve.darkened(0.15), skin.darkened(0.12), glove.darkened(0.13), trim, outline, false, str(pose["hand_back_shape"]), handwear, wristband, sleeve_coverage)
	# Both thighs begin behind a single pelvis. No outlined hip disk is laid
	# over the belt; the continuous fabric bridges waist and leg origins.
	canvas.draw_colored_polygon(PackedVector2Array([
		hip - side * 2.3 - down * 0.6, hip + side * 2.3 - down * 0.6,
		(pose["hip_front"] as Vector2) + side * 1.05 + down * 0.85,
		hip + down * 1.0,
		(pose["hip_back"] as Vector2) - side * 1.05 + down * 0.85,
	]), pants)

	# Compact tapered torso: cel shadow panel, collar, belt and identity details.
	var torso: PackedVector2Array = PackedVector2Array([
		chest - side * 1.85 - down * 0.38,
		chest + side * 1.8 - down * 0.38,
		chest + side * 2.6 + down * 0.85,
		chest.lerp(hip, 0.62) + side * 1.9,
		hip + side * 2.15 + down * 0.2,
		hip - side * 2.2 + down * 0.2,
		chest.lerp(hip, 0.62) - side * 1.95,
		chest - side * 2.65 + down * 0.85,
	])
	_draw_cel_polygon(canvas, torso, shirt, outline, 0.85)
	var outfit: String = str(style["outfit"])
	var torso_shadow: Color = shirt.darkened(0.16) if outfit in ["gi", "hero_suit"] else shade
	if is_back_view:
		# Rear torso view: back collar band, center back seam, and rear belt without front tie/chest/buckle
		canvas.draw_colored_polygon(PackedVector2Array([torso[0], chest - side * 0.35, hip - side * 0.35, torso[5], torso[6], torso[7]]), torso_shadow)
		canvas.draw_line(chest + side * 1.65 + down * 0.7, hip + side * 1.4 - down * 0.8, shirt.lightened(0.14), 0.65, true)
		canvas.draw_line(chest - side * 1.6 - down * 0.15, chest + side * 1.6 - down * 0.15, shade.darkened(0.18), 0.9, true)
		canvas.draw_line(chest + down * 0.25, hip - down * 0.35, shade.darkened(0.16), 0.55, true)
		canvas.draw_line(hip - side * 2.2, hip + side * 2.2, shade.darkened(0.2), 1.2, true)
		if outfit == "gi":
			canvas.draw_line(hip - side * 2.0, hip + side * 2.0, shade, 1.0, true)
			canvas.draw_circle(hip, 0.65, shade.darkened(0.15))
		elif outfit == "tactical":
			canvas.draw_line(chest - side * 1.4 + down * 0.35, hip + side * 1.1 - down * 0.35, shade.lightened(0.12), 0.8, true)
			canvas.draw_line(chest + side * 1.4 + down * 0.35, hip - side * 1.1 - down * 0.35, shade.lightened(0.12), 0.8, true)
		if bool(style["has_cape"]):
			var scarf_back: Color = _tint(style["scarf"], is_charred, is_hit_flash, alpha)
			var wave_b: float = sin(fposmod(clock, 12.0) * TAU / 12.0) * 0.45
			_draw_cel_polygon(canvas, PackedVector2Array([
				chest - side * 1.85,
				chest + side * 1.85,
				hip + side * (2.3 + wave_b) + down * 1.3,
				hip - side * (2.3 - wave_b) + down * 1.3,
			]), scarf_back, outline, 0.65)
			canvas.draw_line(chest + down * 0.5, hip + down * 1.0, scarf_back.lightened(0.16), 0.65, true)
	else:
		canvas.draw_colored_polygon(PackedVector2Array([torso[0], chest + side * 0.1, hip + side * 0.3, torso[5], torso[6], torso[7]]), torso_shadow)
		canvas.draw_line(chest - side * 1.8 + down * 0.7, hip - side * 1.5 - down * 0.8, shirt.lightened(0.14), 0.65, true)
		if is_burning_active:
			# Fiery rim highlight along torso front edge
			canvas.draw_line(chest + side * 2.2 + down * 0.5, hip + side * 1.9, Color(1.0, 0.78, 0.22, 0.82 * alpha), 0.62, true)
		canvas.draw_line(hip - side * 2.2, hip + side * 2.2, shade.darkened(0.2), 1.2, true)
		canvas.draw_circle(hip + side * 0.4, 0.53, _tint(style["badge"], is_charred, is_hit_flash, alpha))
		if outfit == "gi":
			canvas.draw_colored_polygon(PackedVector2Array([chest - side * 1.45, chest + side * 1.45, chest + down * 1.8]), shade)
			canvas.draw_colored_polygon(PackedVector2Array([chest - side * 0.7, chest + side * 0.7, chest + down * 0.8]), skin)
			canvas.draw_line(hip - side * 2.0, hip + side * 2.0, shade, 0.95, true)
		elif outfit == "vest":
			canvas.draw_colored_polygon(PackedVector2Array([chest - side * 0.65, chest + side * 0.7, hip + side * 0.5 - down * 0.8, hip - side * 0.4 - down * 0.8]), skin)
			canvas.draw_line(hip - side * 2.0, hip + side * 2.0, trim, 0.75, true)
		elif outfit == "hero_suit":
			canvas.draw_line(chest - side * 1.6, chest, sole, 0.9, true)
			canvas.draw_line(chest, chest + side * 1.6, sole, 0.9, true)
			canvas.draw_line(chest, chest + down * 2.0, shade, 0.3, true)
		elif outfit == "suit":
			_draw_cel_polygon(canvas, PackedVector2Array([chest - side * 1.3, chest + side * 1.4, chest + down * 3.0]), sole, outline, 0.3)
			canvas.draw_line(chest + down * 0.7, chest + down * 3.0, trim, 0.8, true)
		elif outfit in ["tactical", "jacket", "coat"]:
			canvas.draw_line(chest + side * 0.3 + down * 0.4, hip + side * 0.3, outline, 0.45, true)
			canvas.draw_line(chest + side * 1.0 + down * 1.8, chest + side * 2.1 + down * 1.8, shade, 0.65, true)
			canvas.draw_line(chest - side * 2.0 + down * 1.8, chest - side * 0.8 + down * 1.8, shirt.lightened(0.22), 0.5, true)
			if outfit == "tactical":
				canvas.draw_line(chest - side * 2.0 + down * 0.4, hip - side * 1.2, shade.lightened(0.15), 1.15, true)
		elif outfit == "wrap":
			canvas.draw_line(chest - side * 1.8, hip + side * 1.3, sole.darkened(0.15), 1.1, true)
		elif outfit == "clown":
			for i: int in range(3):
				canvas.draw_circle(chest + down * (1.3 + float(i) * 1.2), 0.45, trim)
		else:
			canvas.draw_line(chest - side * 1.5 + down * 0.2, chest - side * 0.3 + down * 1.5, shade, 0.7, true)
			canvas.draw_line(chest + side * 1.5 + down * 0.2, chest + side * 0.3 + down * 1.5, shade, 0.7, true)
		if is_finite(blood_alpha) and blood_alpha > 0.12 and not is_charred:
			canvas.draw_line(chest - side * 0.9 + down * 1.7, chest + side * 0.7 + down * 2.4, Color(0.72, 0.10, 0.14, clampf(blood_alpha, 0.0, 0.9)), 0.8, true)

	# Head helper uses prewarmed authored art when available; procedural fallback
	# retains seven expression shapes and awakened hairstyle changes.
	_draw_chibi_head_and_face(
		canvas, head, float(pose["head_tilt_deg"]) + rad_to_deg(root_angle),
		expr_id, is_blinking, style, skin,
		_tint(style["skin_mid"], is_charred, is_hit_flash, alpha),
		_tint(style["hair_lit"], is_charred, is_hit_flash, alpha),
		_tint(style["hair_mid"], is_charred, is_hit_flash, alpha),
		_tint(style["hair_streak"], is_charred, is_hit_flash, alpha),
		outline, is_charred, is_hit_flash, alpha, clean_zoom, presentation_transform, is_back_view
	)
	if not split and not is_back_view:
		var cross_contact: bool = str(pose["family"]) == "punch_cross" and bool(pose["contact"])
		# A cross brings the rear fist across the chest in front of the body.
		if cross_contact:
			LimbRenderer.draw_arm(canvas, pose["shoulder_back"], pose["elbow_back"], pose["hand_back"], sleeve, skin, glove, trim, outline, true, str(pose["hand_back_shape"]), handwear, wristband, sleeve_coverage)
		LimbRenderer.draw_arm(canvas, pose["shoulder_front"], pose["elbow_front"], pose["hand_front"], sleeve, skin, glove, trim, outline, bool(pose["contact"]) and not cross_contact, str(pose["hand_front_shape"]), handwear, wristband, sleeve_coverage)
		if str(pose["family"]) in ["melee_blade", "melee_heavy", "chainsaw"]:
			_draw_melee_prop(canvas, pose["hand_front"], float(pose["weapon_angle_deg"]) + rad_to_deg(root_angle), equipped_weapon_id, str(pose["family"]), outline, sole, shade, trim)
	# For split arms ChibiWeaponView connects the actual posed shoulder to its
	# gun grips; don't draw a second connector to the old fixed shoulder.

	if not is_back_view:
		_draw_expression_world_badges(canvas, head + Vector2(0.0, -5.7), expr_id, clock * TAU / 24.0, is_charred, alpha, is_burning_active)
	canvas.draw_set_transform_matrix(presentation_transform)


static func _draw_cel_polygon(canvas: CanvasItem, points: PackedVector2Array, fill: Color, outline: Color, width: float = 0.7) -> void:
	canvas.draw_colored_polygon(points, fill)
	var closed: PackedVector2Array = points.duplicate()
	closed.append(points[0])
	canvas.draw_polyline(closed, outline, width, true)


static func _draw_jointed_leg(canvas: CanvasItem, hip: Vector2, knee: Vector2, ankle: Vector2, pants: Color, boot: Color, sole: Color, outline: Color, root_angle: float) -> void:
	var leg_geom: Dictionary = LimbRenderer.get_cached_leg_geometry(hip, knee, ankle)
	var contours: Array = leg_geom["contours"] as Array
	var outlines: Array = leg_geom["outlines"] as Array
	for idx: int in range(contours.size()):
		canvas.draw_colored_polygon(contours[idx] as PackedVector2Array, pants)
		canvas.draw_polyline(outlines[idx] as PackedVector2Array, outline, 0.48, true)
	var thigh: Vector2 = (knee - hip).normalized()
	var shin: Vector2 = (ankle - knee).normalized()
	canvas.draw_line(hip.lerp(knee, 0.35), knee.lerp(ankle, 0.72), pants.lightened(0.14), 0.45, true)
	canvas.draw_line(hip.lerp(knee, 0.35) - thigh.orthogonal() * 0.38, knee.lerp(ankle, 0.72) - shin.orthogonal() * 0.32, pants.darkened(0.18), 0.38, true)
	canvas.draw_line(knee - thigh.orthogonal() * 0.35, knee + thigh * 0.35, pants.darkened(0.16), 0.24, true)
	_draw_chibi_sneaker(canvas, ankle, boot, sole, outline, root_angle)




static func _draw_melee_prop(canvas: CanvasItem, grip: Vector2, angle_deg: float, weapon_id: String, family: String, outline: Color, metal: Color, shade: Color, accent: Color) -> void:
	var angle: float = deg_to_rad(angle_deg)
	var direction: Vector2 = Vector2.RIGHT.rotated(angle)
	var normal: Vector2 = direction.orthogonal()
	var tip: Vector2 = grip + direction * (8.6 if family == "melee_heavy" else 7.2)
	canvas.draw_line(grip - direction * 0.8, tip, outline, 1.55, true)
	canvas.draw_line(grip - direction * 0.6, tip, shade, 0.85, true)
	if family == "chainsaw":
		_draw_cel_polygon(canvas, PackedVector2Array([grip + normal * 1.2, tip + normal * 1.2, tip - normal * 1.2, grip - normal * 1.2]), metal, outline, 0.7)
		canvas.draw_line(grip - direction, grip + direction * 2.0, accent, 2.2, true)
		for i: int in range(4):
			canvas.draw_line(grip + direction * (2.0 + i * 1.3) + normal * 1.1, grip + direction * (2.4 + i * 1.3) + normal * 1.6, outline, 0.45, true)
	elif weapon_id.to_upper().contains("AXE"):
		_draw_cel_polygon(canvas, PackedVector2Array([tip - direction * 2.5 - normal * 0.6, tip + normal * 2.8, tip + direction * 1.8 + normal * 1.7, tip + direction * 0.5 - normal]), metal, outline, 0.6)
	elif family == "melee_heavy" or weapon_id.to_upper().contains("BAT"):
		canvas.draw_line(grip + direction * 3.0, tip, outline, 2.8, true)
		canvas.draw_line(grip + direction * 3.0, tip, metal.darkened(0.15) if weapon_id.to_upper().contains("PIPE") else accent.darkened(0.2), 1.8, true)
	else:
		_draw_cel_polygon(canvas, PackedVector2Array([grip + direction * 1.2 - normal * 0.45, tip - normal * 0.8, tip + direction * 0.9, grip + direction * 1.2 + normal * 1.0]), metal, outline, 0.5)
		canvas.draw_line(grip + normal * 1.5, grip - normal * 1.5, accent, 0.9, true)


static func _draw_chibi_sneaker(
	canvas: CanvasItem,
	ankle: Vector2,
	sneaker_col: Color,
	sole_col: Color,
	out_col: Color,
	angle: float = 0.0
) -> void:
	var side: Vector2 = Vector2.RIGHT.rotated(angle)
	var down: Vector2 = Vector2.DOWN.rotated(angle)
	_draw_cel_polygon(canvas, PackedVector2Array([
		ankle - side * 1.45 - down * 0.7,
		ankle + side * 1.2 - down * 0.65,
		ankle + side * 2.0 + down * 0.3,
		ankle + side * 1.9 + down * 0.95,
		ankle - side * 1.5 + down * 0.95,
	]), sneaker_col, out_col, 0.6)
	canvas.draw_line(ankle - side * 1.35 + down * 0.7, ankle + side * 1.8 + down * 0.7, sole_col, 0.5, true)
	canvas.draw_line(ankle - side * 0.1 - down * 0.1, ankle + side * 0.8 + down * 0.1, sole_col, 0.45, true)


static func _draw_chibi_head_and_face(
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
	hair_streak: Color,
	out_col: Color,
	is_charred: bool,
	is_hit_flash: bool,
	alpha_mul: float,
	camera_zoom_x: float = 2.8,
	presentation_transform: Transform2D = Transform2D.IDENTITY,
	is_back_view: bool = false
) -> void:
	var hstyle: String = str(style["hair_style"])
	var hat: String = str(style.get("hat", "none"))
	if is_back_view:
		# Rear view of the head (character faces into the ladder away from the camera):
		# Symmetric ears peeking out on both sides, cranium, full rear hair down to nape, and rear headgear.
		canvas.draw_circle(hc + Vector2(-3.55, 0.35), 1.15, out_col)
		canvas.draw_circle(hc + Vector2(3.55, 0.35), 1.15, out_col)
		canvas.draw_circle(hc + Vector2(-3.55, 0.35), 0.72, skin_mid)
		canvas.draw_circle(hc + Vector2(3.55, 0.35), 0.72, skin_lit)
		canvas.draw_circle(hc, 4.15, out_col)
		canvas.draw_circle(hc, 3.45, skin_mid)
		if hstyle != "bald":
			var h_pts_back: PackedVector2Array = PackedVector2Array([
				hc + Vector2(-3.9, 0.6),
				hc + Vector2(-4.5, -2.4),
				hc + Vector2(-1.8, -4.8),
				hc + Vector2(1.8, -5.0),
				hc + Vector2(4.6, -2.8),
				hc + Vector2(3.4, -1.2),
				hc + Vector2(4.2, -0.2),
				hc + Vector2(3.1, 2.1),
				hc + Vector2(0.0, 2.55),
				hc + Vector2(-3.1, 2.1),
			])
			if hstyle == "goku_spikes":
				h_pts_back = PackedVector2Array([
					hc + Vector2(-4.0, 0.4), hc + Vector2(-5.3, -3.6), hc + Vector2(-2.8, -3.0),
					hc + Vector2(-2.9, -6.4), hc + Vector2(-0.4, -4.4), hc + Vector2(1.2, -6.1),
					hc + Vector2(2.1, -4.0), hc + Vector2(5.1, -4.2), hc + Vector2(3.7, -0.4),
					hc + Vector2(3.1, 2.2), hc + Vector2(0.0, 2.6), hc + Vector2(-3.1, 2.2),
				])
			elif hstyle == "flat_top":
				h_pts_back = PackedVector2Array([
					hc + Vector2(-3.7, 0.4), hc + Vector2(-3.8, -4.2), hc + Vector2(3.6, -4.2),
					hc + Vector2(3.7, 0.4), hc + Vector2(3.0, 2.1), hc + Vector2(0.0, 2.4), hc + Vector2(-3.0, 2.1),
				])
			elif hstyle in ["slick", "crop"]:
				h_pts_back = PackedVector2Array([
					hc + Vector2(-3.7, 0.4), hc + Vector2(-3.8, -2.7), hc + Vector2(-2.1, -4.0),
					hc + Vector2(1.8, -4.2), hc + Vector2(3.9, -2.9), hc + Vector2(3.7, 0.4),
					hc + Vector2(2.9, 2.1), hc + Vector2(0.0, 2.4), hc + Vector2(-2.9, 2.1),
				])
			elif hstyle in ["swept", "ponytail"]:
				h_pts_back = PackedVector2Array([
					hc + Vector2(-3.8, 0.4), hc + Vector2(-4.0, -2.8), hc + Vector2(-1.8, -4.6),
					hc + Vector2(1.7, -4.7), hc + Vector2(4.2, -2.9), hc + Vector2(3.7, 0.4),
					hc + Vector2(3.0, 2.1), hc + Vector2(0.0, 2.5), hc + Vector2(-3.0, 2.1),
				])
			elif hstyle == "mohawk":
				# Shaved sides with center vertical mohawk crest down the back of the skull
				h_pts_back = PackedVector2Array([
					hc + Vector2(-1.3, 2.3), hc + Vector2(-1.5, -3.5), hc + Vector2(-0.4, -5.8),
					hc + Vector2(0.5, -5.8), hc + Vector2(1.5, -3.5), hc + Vector2(1.3, 2.3),
				])
			_draw_cel_polygon(canvas, h_pts_back, hair_mid, out_col, 0.85)
			canvas.draw_circle(hc + Vector2(0.0, -2.4), 1.65, hair_lit)
			# Rear hair accent streak & nape layering lines
			canvas.draw_colored_polygon(PackedVector2Array([
				hc + Vector2(0.2, -2.6),
				hc + Vector2(2.2, -0.4),
				hc + Vector2(0.9, 0.6),
			]), hair_streak)
			canvas.draw_line(hc + Vector2(-1.8, 0.2), hc + Vector2(-1.2, 2.0), out_col, 0.55, true)
			canvas.draw_line(hc + Vector2(1.8, 0.2), hc + Vector2(1.2, 2.0), out_col, 0.55, true)
			if hstyle == "ponytail":
				_draw_cel_polygon(canvas, PackedVector2Array([
					hc + Vector2(-1.1, -1.2), hc + Vector2(1.1, -1.2),
					hc + Vector2(1.5, 2.9), hc + Vector2(0.0, 3.6), hc + Vector2(-1.5, 2.9),
				]), hair_mid.darkened(0.08), out_col, 0.7)
		if bool(style["has_straw_hat"]):
			canvas.draw_line(hc + Vector2(-5.2, -2.0), hc + Vector2(5.2, -2.0), Color(0.95, 0.78, 0.22, alpha_mul), 2.0)
			canvas.draw_arc(hc + Vector2(0.0, -2.0), 3.5, PI, TAU, 10, Color(0.95, 0.78, 0.22, alpha_mul), 2.6)
		if bool(style["has_headband"]):
			var hb_back_col: Color = _tint(style["headband_col"], is_charred, is_hit_flash, alpha_mul)
			canvas.draw_line(hc + Vector2(-3.6, -1.1), hc + Vector2(3.6, -1.1), hb_back_col, 1.55)
			# Rear headband knot and twin tails
			canvas.draw_circle(hc + Vector2(0.0, -1.0), 0.85, hb_back_col.darkened(0.12))
			canvas.draw_line(hc + Vector2(-0.2, -0.8), hc + Vector2(-1.6, 1.4), hb_back_col, 0.95, true)
			canvas.draw_line(hc + Vector2(0.2, -0.8), hc + Vector2(1.4, 1.6), hb_back_col, 0.95, true)
		if hat != "none":
			var hat_back_col: Color = _tint(style["hoodie_mid"], is_charred, is_hit_flash, alpha_mul)
			if hat == "cap":
				_draw_cel_polygon(canvas, PackedVector2Array([
					hc + Vector2(-3.5, -2.5), hc + Vector2(-2.8, -4.8),
					hc + Vector2(2.8, -4.8), hc + Vector2(3.5, -2.5),
				]), hat_back_col, out_col, 0.65)
				canvas.draw_line(hc + Vector2(-3.6, -2.5), hc + Vector2(3.6, -2.5), out_col, 1.3, true)
			elif hat == "winter":
				canvas.draw_line(hc + Vector2(-3.8, -3.2), hc + Vector2(3.8, -3.2), out_col, 3.4, true)
				canvas.draw_line(hc + Vector2(-3.4, -3.2), hc + Vector2(3.4, -3.2), hat_back_col, 2.3, true)
			else:
				canvas.draw_line(hc + Vector2(-5.0, -2.6), hc + Vector2(5.0, -2.6), out_col, 1.7, true)
				canvas.draw_line(hc + Vector2(-4.7, -2.9), hc + Vector2(4.7, -2.9), hat_back_col, 1.0, true)
				_draw_cel_polygon(canvas, PackedVector2Array([
					hc + Vector2(-3.0, -3.0), hc + Vector2(-2.5, -5.4),
					hc + Vector2(2.5, -5.4), hc + Vector2(3.0, -3.0),
				]), hat_back_col, out_col, 0.6)
		return

	# All resources are warmed by the view. The live draw is cache-only.
	var authored_head: Texture2D = HeadAtlas.get_head(str(style.get("character_id", "johnny")), "blink" if is_blinking else expr_id)
	if authored_head != null and not bool(style.get("use_procedural_head", false)):
		var head_modulate: Color = _tint(Color.WHITE, is_charred, is_hit_flash, alpha_mul)
		canvas.draw_set_transform_matrix(presentation_transform * Transform2D(deg_to_rad(tilt_deg), hc))
		canvas.draw_texture_rect(authored_head, HeadAtlas.WORLD_RECT, false, head_modulate)
		canvas.draw_set_transform_matrix(presentation_transform)
		return
	var t_rad: float = deg_to_rad(tilt_deg)
	var look_off: Vector2 = Vector2(cos(t_rad) - 1.0, sin(t_rad)) * 1.3
	var is_far_lod: bool = (7.2 * camera_zoom_x) < 16.0

	# Rounded 2.5-Head Chibi Cranium & Cheek (radius ~ 3.6 world units -> 7.2u head height)
	canvas.draw_circle(hc, 4.15, out_col)
	canvas.draw_circle(hc, 3.45, skin_lit)
	canvas.draw_circle(hc + Vector2(-2.9, 0.4), 1.05, skin_mid)

	# Chibi Spiky Hair & Signature Highlight Streak (#FF7832)
	if hstyle != "bald":
		var h_pts: PackedVector2Array = PackedVector2Array([
			hc + Vector2(-3.9, 0.2),
			hc + Vector2(-4.5, -2.4),
			hc + Vector2(-1.8, -4.8),
			hc + Vector2(1.8, -5.0),
			hc + Vector2(4.6, -2.8),
			hc + Vector2(3.4, -1.2),
			hc + Vector2(4.4, -0.4),
			hc + Vector2(1.4, -1.4),
			hc + Vector2(-2.4, -1.2),
		])
		if hstyle == "goku_spikes":
			h_pts = PackedVector2Array([hc + Vector2(-4.0, 0.2), hc + Vector2(-5.3, -3.6), hc + Vector2(-2.8, -3.0), hc + Vector2(-2.9, -6.4), hc + Vector2(-0.4, -4.4), hc + Vector2(1.2, -6.1), hc + Vector2(2.1, -4.0), hc + Vector2(5.1, -4.2), hc + Vector2(3.6, -1.0), hc + Vector2(1.4, -1.4), hc + Vector2(-2.4, -1.2)])
		elif hstyle == "flat_top":
			h_pts = PackedVector2Array([hc + Vector2(-3.7, -0.3), hc + Vector2(-3.8, -4.2), hc + Vector2(3.4, -4.2), hc + Vector2(3.5, -1.5), hc + Vector2(0.3, -1.7), hc + Vector2(-2.4, -1.2)])
		elif hstyle in ["slick", "crop"]:
			h_pts = PackedVector2Array([hc + Vector2(-3.7, 0.0), hc + Vector2(-3.8, -2.7), hc + Vector2(-2.1, -4.0), hc + Vector2(1.8, -4.2), hc + Vector2(3.9, -2.9), hc + Vector2(3.5, -1.6), hc + Vector2(-0.5, -2.0), hc + Vector2(-2.8, -0.9)])
		elif hstyle in ["swept", "ponytail"]:
			h_pts = PackedVector2Array([hc + Vector2(-3.8, 0.0), hc + Vector2(-4.0, -2.8), hc + Vector2(-1.8, -4.6), hc + Vector2(1.7, -4.7), hc + Vector2(4.2, -2.9), hc + Vector2(3.0, -0.5), hc + Vector2(1.6, -2.0), hc + Vector2(-2.3, -0.9)])
			if hstyle == "ponytail":
				_draw_cel_polygon(canvas, PackedVector2Array([hc + Vector2(-3.1, -2.2), hc + Vector2(-6.5, -2.0), hc + Vector2(-6.2, 2.4), hc + Vector2(-3.7, 0.2)]), hair_mid, out_col, 0.7)
		elif hstyle == "mohawk":
			h_pts = PackedVector2Array([hc + Vector2(-2.9, -1.0), hc + Vector2(-2.0, -3.5), hc + Vector2(-0.5, -5.8), hc + Vector2(1.0, -4.4), hc + Vector2(2.6, -5.1), hc + Vector2(3.6, -2.7), hc + Vector2(1.0, -1.6)])
		canvas.draw_colored_polygon(h_pts, hair_mid)
		canvas.draw_polyline(h_pts, out_col, 1.1)
		canvas.draw_circle(hc + Vector2(-0.2, -2.9), 1.8, hair_lit)
		# Orange/Highlight front hair bang streak
		var streak_pts: PackedVector2Array = PackedVector2Array([
			hc + Vector2(-0.4, -2.4),
			hc + Vector2(2.6, -0.6),
			hc + Vector2(1.1, -0.3),
		])
		canvas.draw_colored_polygon(streak_pts, hair_streak)

	if bool(style["has_straw_hat"]):
		canvas.draw_line(
			hc + Vector2(-5.2, -2.0),
			hc + Vector2(5.2, -2.0),
			Color(0.95, 0.78, 0.22, alpha_mul),
			2.0
		)
		canvas.draw_arc(
			hc + Vector2(0.0, -2.0),
			3.5,
			PI,
			TAU,
			10,
			Color(0.95, 0.78, 0.22, alpha_mul),
			2.6
		)

	if bool(style["has_headband"]):
		var hb_col: Color = _tint(style["headband_col"], is_charred, is_hit_flash, alpha_mul)
		canvas.draw_line(hc + Vector2(-3.4, -1.3), hc + Vector2(3.5, -1.3), hb_col, 1.5)
	if hat != "none":
		var hat_col: Color = _tint(style["hoodie_mid"], is_charred, is_hit_flash, alpha_mul)
		if hat == "cap":
			canvas.draw_line(hc + Vector2(-3.7, -2.9), hc + Vector2(4.6, -2.9), out_col, 2.3, true)
			canvas.draw_line(hc + Vector2(-3.5, -3.2), hc + Vector2(4.2, -3.2), hat_col, 1.5, true)
		elif hat == "winter":
			canvas.draw_line(hc + Vector2(-3.8, -3.2), hc + Vector2(3.5, -3.2), out_col, 3.4, true)
			canvas.draw_line(hc + Vector2(-3.4, -3.2), hc + Vector2(3.1, -3.2), hat_col, 2.3, true)
			canvas.draw_line(hc + Vector2(-3.6, -2.5), hc + Vector2(-3.7, 0.1), hair_lit, 1.5, true)
		else:
			canvas.draw_line(hc + Vector2(-5.2, -2.6), hc + Vector2(4.6, -2.6), out_col, 1.7, true)
			canvas.draw_line(hc + Vector2(-4.9, -2.9), hc + Vector2(4.3, -2.9), hat_col, 1.0, true)
			_draw_cel_polygon(canvas, PackedVector2Array([hc + Vector2(-3.0, -3.0), hc + Vector2(-2.5, -5.4), hc + Vector2(2.2, -5.1), hc + Vector2(2.8, -3.0)]), hat_col, out_col, 0.6)

	# 7 Expressive Chibi Eyes, Brows & Mouth (with Far-Zoom LOD when face < 16 screen px)
	var eye_c: Vector2 = hc + Vector2(1.25, 0.20) + look_off * 0.55
	var iris_col: Color = _tint(style["iris"], is_charred, is_hit_flash, alpha_mul)
	var white_col: Color = _tint(EYE_WHITE, is_charred, is_hit_flash, alpha_mul)
	var mouth_c: Vector2 = hc + Vector2(1.15, 1.85) + look_off * 0.45

	if is_charred or expr_id == "KO_STARS":
		canvas.draw_line(eye_c + Vector2(-1.0, -0.9), eye_c + Vector2(1.0, 0.9), out_col, 1.25)
		canvas.draw_line(eye_c + Vector2(1.0, -0.9), eye_c + Vector2(-1.0, 0.9), out_col, 1.25)
		canvas.draw_line(mouth_c + Vector2(-0.8, 0.0), mouth_c + Vector2(0.8, 0.0), out_col, 1.15)
		return

	if expr_id == "DIZZY_SPIRAL_HURT":
		canvas.draw_arc(eye_c, 1.05, 0.0, TAU * 0.85, 8, out_col, 1.2)
		canvas.draw_circle(mouth_c, 0.95, _tint(MOUTH_INTERIOR, is_charred, is_hit_flash, alpha_mul))
	elif expr_id == "ECSTATIC_VICTORY_LAUGH":
		canvas.draw_line(eye_c + Vector2(-1.1, 0.2), eye_c + Vector2(0.0, -0.7), out_col, 1.25)
		canvas.draw_line(eye_c + Vector2(0.0, -0.7), eye_c + Vector2(1.1, 0.2), out_col, 1.25)
		canvas.draw_rect(
			Rect2(mouth_c.x - 1.0, mouth_c.y - 0.5, 2.0, 1.3),
			_tint(MOUTH_INTERIOR, is_charred, is_hit_flash, alpha_mul),
			true
		)
		canvas.draw_line(mouth_c + Vector2(-0.9, -0.4), mouth_c + Vector2(0.9, -0.4), white_col, 0.95)
	elif is_blinking and expr_id in ["CHEEKY_SMIRK", "LOW_HP_SWEAT"]:
		canvas.draw_line(eye_c + Vector2(-1.1, 0.0), eye_c + Vector2(1.1, 0.0), out_col, 1.25)
		canvas.draw_line(mouth_c + Vector2(-0.8, 0.1), mouth_c + Vector2(0.9, -0.2), out_col, 1.15)
	else:
		# Large Chibi Eye (with Face LOD simplification when < 16 screen px)
		canvas.draw_rect(Rect2(eye_c.x - 1.15, eye_c.y - 1.05, 2.3, 2.1), white_col, true)
		var active_iris: Color = Color(1.0, 0.90, 0.24, alpha_mul) if expr_id == "BLAZING_GLARE" else iris_col
		canvas.draw_rect(Rect2(eye_c.x - 0.45, eye_c.y - 0.95, 1.5, 1.9), active_iris, true)
		if not is_far_lod:
			canvas.draw_rect(Rect2(eye_c.x - 0.10, eye_c.y - 0.65, 0.95, 1.3), out_col, true)
			canvas.draw_rect(Rect2(eye_c.x - 0.65, eye_c.y - 0.80, 0.65, 0.65), white_col, true)

		var brow_slant: float = 0.55 if expr_id in ["BLAZING_GLARE", "WIDE_MOUTH_SHOUT", "LOW_HP_SWEAT"] else 0.12
		canvas.draw_line(
			eye_c + Vector2(-1.3, -1.45 - brow_slant * 0.5),
			eye_c + Vector2(1.2, -1.45 + brow_slant),
			out_col,
			1.30
		)

		if expr_id == "WIDE_MOUTH_SHOUT":
			canvas.draw_rect(
				Rect2(mouth_c.x - 1.0, mouth_c.y - 0.65, 2.0, 1.55),
				_tint(MOUTH_INTERIOR, is_charred, is_hit_flash, alpha_mul),
				true
			)
			canvas.draw_line(mouth_c + Vector2(-0.9, -0.55), mouth_c + Vector2(0.9, -0.55), white_col, 0.95)
		elif expr_id == "LOW_HP_SWEAT":
			canvas.draw_rect(Rect2(mouth_c.x - 0.95, mouth_c.y - 0.40, 1.9, 0.95), white_col, true)
		elif expr_id == "BLAZING_GLARE":
			canvas.draw_line(mouth_c + Vector2(-0.85, 0.05), mouth_c + Vector2(0.85, 0.15), out_col, 1.15)
		else:
			canvas.draw_line(mouth_c + Vector2(-0.85, 0.18), mouth_c + Vector2(0.95, -0.28), out_col, 1.15)
	if bool(style.get("beard", false)):
		canvas.draw_arc(hc + Vector2(0.1, 1.2), 2.0, 0.1, PI * 0.92, 7, hair_mid, 0.65, true)
	if bool(style.get("glasses", false)) or bool(style.get("has_visor", false)):
		var lens_col: Color = _tint(Color(0.20, 0.40, 0.52, 0.75), is_charred, is_hit_flash, alpha_mul)
		canvas.draw_rect(Rect2(eye_c - Vector2(1.6, 1.1), Vector2(3.3, 2.0)), lens_col)
		canvas.draw_rect(Rect2(eye_c - Vector2(1.6, 1.1), Vector2(3.3, 2.0)), out_col, false, 0.45)
		canvas.draw_line(eye_c + Vector2(-1.6, -0.8), hc + Vector2(-2.8, -0.6), out_col, 0.6, true)
		canvas.draw_line(eye_c + Vector2(-0.9, -0.7), eye_c + Vector2(0.4, -0.7), EYE_WHITE, 0.4, true)

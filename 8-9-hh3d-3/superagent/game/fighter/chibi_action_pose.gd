class_name ChibiActionPose
extends RefCounted
## Pure presentation sampling. All time is the controller's authored source
## frame; no wall clock, second animation clock, resources or gameplay mutation.

const STATE_LENGTHS: Dictionary = {
	"IDLE": 61.0, "WALK": 16.0, "RUN": 12.0, "SPRINT": 8.0,
	"JUMP": 8.0, "FALL": 8.0, "FALL_F": 8.0, "FALL_B": 8.0,
	"KNOCKDOWN": 13.0, "GETUP": 8.0, "GET_UP": 8.0,
	"KNEEL": 1.0, "CROUCH": 1.0, "COVER": 1.0,
	"ROLL": 6.0, "KICK": 8.0, "DIVE": 8.0,
	"PUNCH_01": 8.0, "PUNCH_02": 8.0, "PUNCH_03": 8.0,
	"MACHETE_01": 10.0, "MACHETE_02": 10.0, "MACHETE_03": 10.0,
	"AXE_01": 10.0, "AXE_02": 10.0, "AXE_03": 10.0,
	"SWORD_01": 10.0, "SWORD_02": 10.0, "SWORD_03": 10.0,
	"BAT_01": 10.0, "BAT_02": 10.0, "BAT_03": 10.0,
	"BATON_01": 10.0, "BATON_02": 10.0, "BATON_03": 10.0,
	"PIPE_01": 10.0, "PIPE_02": 10.0, "PIPE_03": 10.0,
	"CHAINSAW_01": 10.0, "CHAINSAW_02": 10.0,
	"THROW": 5.0, "CLIMB": 8.0, "SLIDE": 8.0, "LEDGE_GRAB": 8.0,
	"GRABBED": 8.0, "STUN_01": 8.0, "STUN_02": 8.0,
	"JUMPKICK": 8.0, "JUMP_KICK": 8.0, "JUMP_ATT": 8.0,
	"STAGGER": 12.0, "DEATH_KNEEL": 6.0, "DEAD": 6.0, "LAY": 6.0,
	"LAND": 4.0, "LAND_HEAVY": 13.0, "HURT": 8.0,
	"ROCKET_RIDE_R": 8.0, "ROCKET_RIDE_L": 8.0,
	"ROCKET_RIDE": 8.0, "GRAB": 8.0,
	"EMPTY": 1.0, "ROCKET_RIDE_EMPTY": 1.0,
	"MUGEN_COMBO_1": 5.0, "MUGEN_COMBO_2": 5.0,
	"MUGEN_COMBO_3": 5.0, "MUGEN_COMBO_4": 7.0,
	"SHUNPO_SLASH": 7.0, "CHAKRA_WAVE": 7.0,
	"SKILL_1": 7.0, "SKILL_2": 7.0, "SKILL_3": 7.0, "SKILL_4": 9.0,
}

const SOURCE_BODY_PIVOT: Vector2 = Vector2(0.0, -9.0)
# Authored Blender skull rect [20,27,88,92], pivot[64,73], 10/128u per texel.
# Hair/hats are decorative and deliberately excluded from this vulnerable core.
const SKULL_LOCAL_RECT: Rect2 = Rect2(-3.4375, -3.59375, 6.875, 7.1875)
const ROTATING_STATES: Array[String] = [
	"DIVE", "FALL_F", "FALL_B", "GRABBED",
	"ROCKET_RIDE_R", "ROCKET_RIDE_L", "ROCKET_RIDE",
]


static func _ease(v: float) -> float:
	var t: float = clampf(v, 0.0, 1.0)
	return t * t * (3.0 - 2.0 * t)


static func _strike_weight(t: float, hit: float, end: float) -> float:
	if t <= hit:
		return _ease((t - hit * 0.40) / maxf(0.1, hit * 0.60))
	return 1.0 - _ease((t - hit - 0.8) / maxf(0.2, end - hit - 0.8))


static func sample(
	state_name: String,
	frame_idx: int = 1,
	aim_pitch_deg: float = 0.0,
	is_carrying: bool = false,
	source_frame: float = -1.0,
	body_rotation_deg: float = 0.0,
	stance: String = "",
	motion: Dictionary = {}
) -> Dictionary:
	var st: String = state_name.to_upper().left(96)
	var frame: int = clampi(frame_idx, 1, 1000000)
	var t: float = float(frame - 1)
	if is_finite(source_frame) and source_frame >= 0.0:
		t = clampf(source_frame, 0.0, 1000000.0)
	var aim: float = clampf(aim_pitch_deg, -90.0, 90.0) if is_finite(aim_pitch_deg) else 0.0
	var length: float = float(STATE_LENGTHS.get(st, 8.0))
	# Optional context uses the controller's world units per 24 Hz source step.
	# Old callers retain authored state/frame defaults. Never inspect a node here.
	var velocity: Vector2 = Vector2.ZERO
	var motion_velocity: Variant = motion.get("velocity", null)
	var has_velocity: bool = motion_velocity is Vector2
	if has_velocity:
		velocity = motion_velocity as Vector2
		if not is_finite(velocity.x) or not is_finite(velocity.y):
			velocity = Vector2.ZERO
			has_velocity = false
		else:
			velocity = velocity.clamp(Vector2(-1000.0, -1000.0), Vector2(1000.0, 1000.0))
	var grounded: bool = bool(motion.get("grounded", st not in ["JUMP", "FALL", "FALL_F", "FALL_B", "DIVE", "GRABBED", "ROCKET_RIDE", "ROCKET_RIDE_R", "ROCKET_RIDE_L"]))
	var p: Dictionary = {
		"state": st, "frame": frame, "source_frame": t, "length": length,
		"family": "safe_fallback", "phase": "hold", "contact": false,
		"known_state": false, "fallback_reason": "unknown_state",
		"split_arms": false, "weapon_angle_deg": -60.0,
		"hand_front_shape": "relaxed", "hand_back_shape": "relaxed",
		"burning_overlay": false,
		"root_origin": Vector2.ZERO, "root_rotation_deg": 0.0,
		"body_rotation_deg": 0.0, "body_pivot": SOURCE_BODY_PIVOT,
		"hip": Vector2(-0.3, -5.6), "chest": Vector2(-0.2, -10.7),
		"head": Vector2(0.25, -14.40625), "head_tilt_deg": 0.0,
		"shoulder_back": Vector2(-2.0, -10.3),
		"elbow_back": Vector2(-3.25, -8.0), "hand_back": Vector2(-3.45, -5.6),
		"shoulder_front": Vector2(1.35, -10.2),
		"elbow_front": Vector2(2.65, -8.1), "hand_front": Vector2(3.05, -6.2),
		"hip_back": Vector2(-1.6, -5.35), "knee_back": Vector2(-2.5, -3.3),
		"ankle_back": Vector2(-2.5, -1.1),
		"hip_front": Vector2(1.1, -5.35), "knee_front": Vector2(2.0, -3.2),
		"ankle_front": Vector2(2.3, -1.1),
	}
	if st in ["WALK", "RUN", "SPRINT", "STAGGER"]:
		var cycle: float = fposmod(t, length) / length * TAU
		var stride: float = sin(cycle)
		var speed: float = 0.68 if st == "WALK" else (1.25 if st == "SPRINT" else 1.0)
		var lean: float = 1.85 if st == "SPRINT" else (0.35 if st == "WALK" else 1.0)
		var bob: float = -absf(cos(cycle)) * 0.52 * speed
		_shift_upper(p, Vector2(lean, bob))
		p["family"] = "locomotion"
		p["phase"] = "stride_front" if stride >= 0.0 else "stride_back"
		p["head_tilt_deg"] = lean * 1.9
		p["ankle_front"] = Vector2(2.0 + stride * 3.6 * speed, -1.1 - maxf(0.0, -cos(cycle)) * 2.6 * speed)
		p["ankle_back"] = Vector2(-1.8 - stride * 3.6 * speed, -1.1 - maxf(0.0, cos(cycle)) * 2.6 * speed)
		p["knee_front"] = Vector2(1.9 + stride * 2.0 * speed, -3.3 - maxf(0.0, -cos(cycle)) * 1.8)
		p["knee_back"] = Vector2(-1.5 - stride * 2.0 * speed, -3.3 - maxf(0.0, cos(cycle)) * 1.8)
		# A pendulum walk opens below the waist; faster gaits bend the elbow
		# and pump across the ribs. Opposite arm/leg pairs share one phase.
		var pump: float = 0.0 if st == "WALK" else (1.0 if st == "SPRINT" else 0.65)
		p["elbow_front"] = Vector2(2.8 - stride * (1.1 + pump) + lean, -8.0 + bob)
		p["hand_front"] = Vector2(3.0 - stride * (2.35 + pump * 1.8) + lean, -5.8 - pump * 1.7 - maxf(0.0, -stride) * pump * 1.3 + bob)
		p["elbow_back"] = Vector2(-3.0 + stride * (1.1 + pump) + lean, -8.2 + bob)
		p["hand_back"] = Vector2(-3.25 + stride * (2.35 + pump * 1.8) + lean, -5.9 - pump * 1.5 - maxf(0.0, stride) * pump * 1.3 + bob)
		if st != "WALK":
			p["hand_front_shape"] = "loose_fist"
			p["hand_back_shape"] = "loose_fist"
		if st == "STAGGER":
			_shift_upper(p, Vector2(-2.2, 0.8))
			p["family"] = "hurt"
			p["head_tilt_deg"] = -15.0 + stride * 5.0
			p["hand_front_shape"] = "open"
			p["hand_back_shape"] = "open"
	elif st in ["KNEEL", "CROUCH", "COVER", "LAND", "LAND_HEAVY"]:
		var cover: bool = st == "COVER"
		var drop: float = 4.5 if cover else 3.1
		if st in ["LAND", "LAND_HEAVY"]:
			drop = 2.8 * (1.0 - _ease(t / 4.0))
		_shift_upper(p, Vector2(-0.6 if cover else 0.6, drop))
		p["hip"] = Vector2(-1.5, -3.8)
		p["hip_back"] = Vector2(-2.5, -3.7)
		p["hip_front"] = Vector2(-0.5, -3.7)
		p["knee_back"] = Vector2(-4.0, -1.5)
		p["ankle_back"] = Vector2(-2.4, -0.9)
		p["knee_front"] = Vector2(3.2, -3.2)
		p["ankle_front"] = Vector2(3.8, -0.9)
		p["family"] = "cover" if cover else "crouch"
		if cover:
			p["elbow_front"] = Vector2(3.6, -6.8)
			p["hand_front"] = Vector2(3.1, -10.0)
			p["elbow_back"] = Vector2(-3.3, -5.0)
			p["hand_back"] = Vector2(0.0, -6.7)
			p["head_tilt_deg"] = 12.0
		if st in ["KNEEL", "CROUCH", "COVER"]:
			_apply_crouch(p, cover)
	elif st.begins_with("PUNCH") or st.begins_with("JUMP_PUNCH") or st == "GRAB_PUNCH":
		var combo: int = 2 if st.ends_with("02") else (3 if st.ends_with("03") else 1)
		var hit: float = 3.0 + float(combo - 1) * 0.5
		var strike: float = _strike_weight(t, hit, 8.0)
		p["family"] = ["punch_jab", "punch_cross", "punch_finisher"][combo - 1]
		p["hand_front_shape"] = "fist"
		p["hand_back_shape"] = "fist"
		p["phase"] = "windup" if t < hit else ("contact" if t <= hit + 0.8 else "recovery")
		p["contact"] = t >= hit and t <= hit + 0.8
		_shift_upper(p, Vector2(strike * (0.8 + combo * 0.45), -strike * 0.20))
		p["hand_back"] = Vector2(-0.8, -12.0)
		p["elbow_back"] = Vector2(-3.0, -9.4)
		if combo == 1:
			p["hand_front"] = Vector2(3.5, -11.5).lerp(Vector2(10.0, -10.8), strike)
			p["elbow_front"] = Vector2(1.0, -8.0).lerp(Vector2(6.2, -10.0), strike)
		elif combo == 2:
			p["hand_back"] = Vector2(-4.0, -12.5).lerp(Vector2(10.8, -12.6), strike)
			p["elbow_back"] = Vector2(-4.8, -9.6).lerp(Vector2(6.2, -9.0), strike)
			p["hand_front"] = Vector2(2.8, -12.0)
			p["head_tilt_deg"] = -8.0 * strike
		else:
			p["hand_front"] = Vector2(-1.2, -6.8).lerp(Vector2(12.0, -13.0), strike)
			p["elbow_front"] = Vector2(-1.7, -7.2).lerp(Vector2(7.0, -9.0), strike)
			p["ankle_back"] = Vector2(-4.8, -1.0)
			p["knee_back"] = Vector2(-3.0, -3.4)
			p["ankle_front"] = Vector2(3.0, -1.0)
			p["head_tilt_deg"] = -12.0 * strike
	elif st in ["KICK", "JUMPKICK", "JUMP_KICK", "JUMP_ATT"]:
		var air: bool = st != "KICK"
		var strike: float = _strike_weight(t, 1.0, 8.0)
		p["family"] = "jumpkick" if air else "kick"
		p["phase"] = "windup" if t < 1.0 else ("contact" if t < 2.2 else "recovery")
		p["contact"] = t >= 1.0 and t < 2.2
		_shift_upper(p, Vector2(-1.3 * strike, -1.3 if air else 0.0))
		p["knee_front"] = Vector2(2.0, -5.3).lerp(Vector2(4.8, -5.7 if air else -3.8), strike)
		p["ankle_front"] = Vector2(2.3, -3.7).lerp(Vector2(9.2, -6.0 if air else -2.6), strike)
		p["ankle_back"] = Vector2(-3.3, -4.1 if air else -1.1)
		p["knee_back"] = Vector2(-3.8, -5.6 if air else -3.4)
		p["hand_front"] = Vector2(2.6, -12.1)
		p["hand_back"] = Vector2(-4.7, -9.7)
		p["head_tilt_deg"] = -8.0
	elif st.begins_with("MACHETE") or st.begins_with("AXE") or st.begins_with("SWORD") or st.begins_with("BAT") or st.begins_with("PIPE") or st.begins_with("CHAINSAW"):
		_melee_weapon(p, st, t)
	elif st in ["START_MELEE_1H", "AIM_MELEE_1H", "START_MELEE_2H", "AIM_MELEE_2H", "AIM_FISTS", "AIM_TURN"]:
		# These are full-body compiled states, not a firearm split rig.
		p["family"] = "guard"
		p["hand_front_shape"] = "fist"
		p["hand_back_shape"] = "fist"
		p["hand_front"] = Vector2(3.4, -12.0)
		p["elbow_front"] = Vector2(3.7, -8.6)
		p["hand_back"] = Vector2(-2.0, -12.4)
		p["elbow_back"] = Vector2(-3.5, -9.2)
	elif st.begins_with("AIM_") or st.begins_with("START_"):
		p["family"] = "aim"
		p["split_arms"] = true
		p["head_tilt_deg"] = clampf(aim * 0.4, -28.0, 28.0)
		p["hand_front"] = Vector2(-3.0, -12.0) + Vector2(6.0, 0.0).rotated(deg_to_rad(aim))
		p["hand_back"] = Vector2(-3.0, -12.0) + Vector2(3.0, 1.0).rotated(deg_to_rad(aim))
		if stance.to_upper() in ["COVER", "KNEEL", "CROUCH"]:
			_apply_crouch(p, stance.to_upper() == "COVER")
			p["head_tilt_deg"] = clampf(aim * 0.4, -28.0, 28.0)
			_fit_skull_under(p, -12.0)
	elif st in ["JUMP", "FALL", "FALL_F", "FALL_B", "DIVE", "GRABBED", "ROCKET_RIDE_R", "ROCKET_RIDE_L", "ROCKET_RIDE"]:
		_airborne(p, st, t, velocity, has_velocity)
		if st == "DIVE" or st.begins_with("ROCKET_RIDE"):
			p["family"] = "rocket_ride" if st.begins_with("ROCKET_RIDE") else "dive"
			p["root_origin"] = Vector2(-4.0, -8.0)
			p["root_rotation_deg"] = 67.0
			p["hand_front"] = Vector2(3.0, -17.0)
			p["hand_back"] = Vector2(-2.0, -17.0)
			p["ankle_back"] = Vector2(-2.8, 1.4)
			p["ankle_front"] = Vector2(2.8, 0.0)
		elif st in ["FALL_F", "FALL_B", "GRABBED"]:
			# Impact tumble is a broken, asymmetric silhouette, separate from
			# an ordinary descent. Gameplay still supplies the rotating angle.
			p["phase"] = "hit_tumble_back" if st == "FALL_B" else "hit_tumble_front"
			p["elbow_front"] = Vector2(4.0, -8.8)
			p["hand_front"] = Vector2(6.1, -10.3)
			p["elbow_back"] = Vector2(-3.8, -8.0)
			p["hand_back"] = Vector2(-5.7, -5.2)
			p["knee_front"] = Vector2(3.6, -7.0)
			p["ankle_front"] = Vector2(5.0, -5.1)
			p["knee_back"] = Vector2(-2.6, -3.3)
			p["ankle_back"] = Vector2(-4.8, -0.3)
			p["head_tilt_deg"] = -16.0 if st == "FALL_B" else 13.0
			p["root_origin"] = Vector2(-3.5 if st != "FALL_B" else 3.5, -2.5)
			p["root_rotation_deg"] = 32.0 if st != "FALL_B" else -32.0
	elif st == "ROLL":
		p["family"] = "roll"
		p["phase"] = "tuck" if t < 1.0 else ("turn" if t < 5.0 else "uncoil")
		_shift_upper(p, Vector2(0.0, 3.1))
		p["knee_front"] = Vector2(3.0, -5.6)
		p["ankle_front"] = Vector2(0.8, -3.7)
		p["knee_back"] = Vector2(-3.4, -5.4)
		p["ankle_back"] = Vector2(-1.6, -3.2)
		p["hand_front"] = Vector2(3.3, -9.6)
		p["hand_back"] = Vector2(-3.0, -9.5)
		var angle: float = clampf(t / 6.0, 0.0, 1.0) * TAU
		# Rotate the articulated tucked body around its compact center.
		p["root_rotation_deg"] = rad_to_deg(angle)
		p["root_origin"] = Vector2(0.0, -7.0) - Vector2(0.0, -7.0).rotated(angle)
	elif st in ["CLIMB", "SLIDE", "LEDGE_GRAB"]:
		_climb(p, st, t)
	elif st in ["KNOCKDOWN", "GETUP", "GET_UP", "DEAD", "LAY", "DEATH_KNEEL"]:
		var dead: bool = st in ["DEAD", "LAY", "DEATH_KNEEL"]
		var getting_up: bool = st in ["GETUP", "GET_UP"] or (st == "KNOCKDOWN" and t >= 9.0)
		p["family"] = "getup" if getting_up else ("dead" if dead else "knockdown")
		if st == "DEATH_KNEEL":
			var fall_t: float = _ease(t / 4.5)
			p["root_rotation_deg"] = lerpf(28.0, 88.0, fall_t)
			p["root_origin"] = Vector2(-2.0, -1.2).lerp(Vector2(-8.7, -3.9), fall_t)
			p["hand_front"] = Vector2(2.6, -5.8).lerp(Vector2(3.4, -6.3), fall_t)
			p["hand_back"] = Vector2(-2.8, -6.4).lerp(Vector2(-3.9, -7.1), fall_t)
			p["head_tilt_deg"] = lerpf(18.0, 12.0, fall_t)
			p["phase"] = "kneel_fall" if fall_t < 0.95 else "prone"
		else:
			var rise: float = _ease((t - 9.0) / 4.0) if st == "KNOCKDOWN" else _ease(t / 8.0)
			if not getting_up:
				rise = 0.0
			p["root_rotation_deg"] = lerpf(88.0, 0.0, rise)
			p["root_origin"] = Vector2(-8.7, -3.9).lerp(Vector2.ZERO, rise)
			p["hand_front"] = Vector2(3.4, -6.3)
			p["hand_back"] = Vector2(-3.9, -7.1)
			p["head_tilt_deg"] = 12.0 * (1.0 - rise)
			p["phase"] = "rise" if getting_up else "prone"
	elif st in ["HURT", "STUN_01", "STUN_02"]:
		p["family"] = "hurt"
		var recoil: float = 1.0 - _ease(t / 8.0)
		_shift_upper(p, Vector2(-1.6 * recoil, 0.6 * recoil))
		p["elbow_front"] = Vector2(3.1, -7.8)
		p["hand_front"] = Vector2(4.7, -9.1)
		p["elbow_back"] = Vector2(-3.3, -8.0)
		p["hand_back"] = Vector2(-4.2, -5.9)
		p["hand_front_shape"] = "open"
		p["hand_back_shape"] = "open"
		p["head_tilt_deg"] = -20.0 * recoil
	elif st == "THROW":
		var release: float = _ease(t / 2.5)
		p["family"] = "throw"
		p["phase"] = "windup" if t < 1.7 else "release"
		p["elbow_front"] = Vector2(-4.3, -13.0).lerp(Vector2(4.7, -12.0), release)
		p["hand_front"] = Vector2(-4.0, -16.0).lerp(Vector2(8.0, -13.0), release)
		_shift_upper(p, Vector2(release * 1.2, 0.0))
	elif st.begins_with("SKILL_") or st.begins_with("MUGEN_") or st in ["SHUNPO_SLASH", "CHAKRA_WAVE"]:
		_powered(p, st, t)
	elif st == "GRAB":
		p["family"] = "grab"
		p["elbow_front"] = Vector2(3.3, -9.9)
		p["hand_front"] = Vector2(6.5, -11.0)
		p["elbow_back"] = Vector2(-2.2, -9.3)
		p["hand_back"] = Vector2(3.1, -10.1)
	elif st in ["EMPTY", "ROCKET_RIDE_EMPTY"]:
		# Source registry intentionally has no visible frame for these slots.
		p["family"] = "empty"
		p["phase"] = "hidden"
	elif st == "WIN":
		p["family"] = "victory"
		p["elbow_front"] = Vector2(4.1, -12.7)
		p["hand_front"] = Vector2(3.1, -17.0)
		p["elbow_back"] = Vector2(-4.2, -12.7)
		p["hand_back"] = Vector2(-3.3, -17.0)
	elif st == "IDLE":
		p["family"] = "idle"
		var breath: float = sin(fposmod(t, 30.0) * TAU / 30.0) * 0.18
		var sway: float = sin(fposmod(t, 61.0) * TAU / 61.0) * 0.16
		_shift_upper(p, Vector2(sway, breath))
		p["hip"] = Vector2(-0.5, -5.6)
		p["knee_front"] = Vector2(1.7, -3.2)
		p["hand_front"] = (p["hand_front"] as Vector2) + Vector2(sway * 0.5, breath * 0.5)
		_fit_skull_under(p, -18.0)
	p["known_state"] = str(p["family"]) != "safe_fallback"
	if bool(p["known_state"]):
		p["fallback_reason"] = ""
	var family: String = str(p["family"])
	if family in ["kick", "jumpkick"] or family.begins_with("powered_"):
		p["hand_front_shape"] = "fist"
		p["hand_back_shape"] = "fist"
	elif family in ["melee_blade", "melee_heavy", "chainsaw", "climb", "slide", "ledge", "rocket_ride"]:
		p["hand_front_shape"] = "grip"
		p["hand_back_shape"] = "grip"
	elif family in ["throw", "grab", "dead", "knockdown", "getup"]:
		p["hand_front_shape"] = "open"
		p["hand_back_shape"] = "open"
	# Fire is a presentation overlay only on controllable, unoccupied poses.
	# Attack/aim/carry/hurt/KO/climb/roll/victory always retain their silhouette.
	if bool(motion.get("burning", false)) and not is_carrying and st in ["IDLE", "WALK", "RUN", "SPRINT", "JUMP", "FALL", "KNEEL", "CROUCH"]:
		_burning_recoil(p, t, grounded)
	# Carry changes only upper limbs; walking legs and state progress survive.
	if is_carrying and st != "THROW" and str(p["family"]) != "empty" and not bool(p["split_arms"]):
		p["family"] = "carry_" + str(p["family"])
		p["hand_front_shape"] = "grip"
		p["hand_back_shape"] = "grip"
		var chest: Vector2 = p["chest"]
		p["elbow_front"] = chest + Vector2(4.0, 0.1)
		p["hand_front"] = chest + Vector2(4.6, -3.9)
		p["elbow_back"] = chest + Vector2(-3.6, -0.2)
		p["hand_back"] = chest + Vector2(-1.1, -4.3)
	# Gameplay owns this angle. Compose it about the original source body
	# pivot after the authored posture; Rig.scale performs the sole facing mirror.
	if st in ROTATING_STATES:
		var extra_deg: float = 0.0
		if is_finite(body_rotation_deg):
			extra_deg = fposmod(clampf(body_rotation_deg, -360000.0, 360000.0) + 180.0, 360.0) - 180.0
		var extra_rad: float = deg_to_rad(extra_deg)
		p["body_rotation_deg"] = extra_deg
		p["root_origin"] = SOURCE_BODY_PIVOT + ((p["root_origin"] as Vector2) - SOURCE_BODY_PIVOT).rotated(extra_rad)
		p["root_rotation_deg"] = fposmod(float(p["root_rotation_deg"]) + extra_deg + 180.0, 360.0) - 180.0
	return p


static func _airborne(p: Dictionary, st: String, t: float, velocity: Vector2, has_velocity: bool) -> void:
	# JUMP is also the controller's normal descent state. State name alone
	# cannot tell an ascending jump from its apex or a drop off a ledge.
	var vertical: float = velocity.y if has_velocity else (-3.0 if st == "JUMP" and t < 3.0 else 3.0)
	p["family"] = "air"
	p["hand_front_shape"] = "open"
	p["hand_back_shape"] = "open"
	if vertical < -0.6:
		p["phase"] = "ascent"
		p["knee_front"] = Vector2(3.3, -6.9)
		p["ankle_front"] = Vector2(2.5, -4.7)
		p["knee_back"] = Vector2(-2.9, -4.9)
		p["ankle_back"] = Vector2(-4.4, -1.9)
		p["elbow_front"] = Vector2(3.4, -8.4)
		p["hand_front"] = Vector2(4.7, -10.1)
		p["elbow_back"] = Vector2(-3.5, -8.2)
		p["hand_back"] = Vector2(-4.8, -6.2)
		p["head_tilt_deg"] = -4.0
	elif vertical <= 0.6:
		p["phase"] = "apex"
		p["knee_front"] = Vector2(3.6, -5.2)
		p["ankle_front"] = Vector2(4.0, -2.2)
		p["knee_back"] = Vector2(-3.5, -5.9)
		p["ankle_back"] = Vector2(-4.5, -3.7)
		p["elbow_front"] = Vector2(3.6, -8.8)
		p["hand_front"] = Vector2(5.5, -8.8)
		p["elbow_back"] = Vector2(-3.7, -9.2)
		p["hand_back"] = Vector2(-5.4, -9.9)
		p["head_tilt_deg"] = 0.0
	else:
		var freefall: bool = vertical >= 8.5
		p["phase"] = "freefall" if freefall else "descent"
		p["knee_front"] = Vector2(2.3, -3.9)
		p["ankle_front"] = Vector2(3.5, -0.8)
		p["knee_back"] = Vector2(-2.5, -4.7)
		p["ankle_back"] = Vector2(-3.0, -2.1)
		p["elbow_front"] = Vector2(3.7, -8.9 if freefall else -8.0)
		p["hand_front"] = Vector2(5.8, -10.3 if freefall else -7.2)
		p["elbow_back"] = Vector2(-3.9, -9.3 if freefall else -8.4)
		p["hand_back"] = Vector2(-5.5, -10.7 if freefall else -8.5)
		p["head_tilt_deg"] = 9.0 if freefall else 4.0


static func _burning_recoil(p: Dictionary, t: float, grounded: bool) -> void:
	# Alternating flinch uses the existing source clock, so pause/hitstop also
	# freezes panic. Hands wave high in panic beside the silhouette, staying clear
	# of the head atlas (`abs(hand.x - head.x) > 4.5`).
	var flinch: float = sin(fposmod(t, 7.0) * TAU / 7.0)
	var recoil: float = absf(flinch)
	var crouched: bool = str(p["family"]) == "crouch"
	var chest: Vector2 = p["chest"]
	p["burning_overlay"] = true
	p["phase"] = "burn_recoil_front" if flinch >= 0.0 else "burn_recoil_back"
	_shift_upper(p, Vector2(-0.55 * recoil, -0.45 * recoil))
	p["elbow_front"] = chest + Vector2(3.9, -0.6 - flinch * 1.1)
	p["hand_front"] = chest + Vector2(5.8, -3.2 - flinch * 2.1)
	p["elbow_back"] = chest + Vector2(-3.8, -0.4 + flinch * 1.1)
	p["hand_back"] = chest + Vector2(-5.6, -2.9 + flinch * 2.1)
	p["hand_front_shape"] = "splayed"
	p["hand_back_shape"] = "splayed"
	p["head_tilt_deg"] = -9.0 + flinch * 7.5
	if grounded:
		_fit_skull_under(p, -12.0 if crouched else -18.0)
		var fam: String = str(p["family"])
		if fam == "idle" or fam == "run":
			var hop_f: float = maxf(0.0, flinch) * 1.35
			var hop_b: float = maxf(0.0, -flinch) * 1.35
			p["knee_front"] = (p["knee_front"] as Vector2) + Vector2(0.45 * flinch, -hop_f)
			p["ankle_front"] = (p["ankle_front"] as Vector2) + Vector2(0.15 * flinch, -hop_f * 0.85)
			p["knee_back"] = (p["knee_back"] as Vector2) + Vector2(-0.45 * flinch, -hop_b)
			p["ankle_back"] = (p["ankle_back"] as Vector2) + Vector2(-0.15 * flinch, -hop_b * 0.85)


static func _shift_upper(p: Dictionary, shift: Vector2) -> void:
	for key: String in ["chest", "head", "shoulder_front", "shoulder_back", "elbow_front", "elbow_back", "hand_front", "hand_back"]:
		p[key] = (p[key] as Vector2) + shift


static func _fit_skull_under(p: Dictionary, top: float) -> void:
	var angle: float = deg_to_rad(float(p["head_tilt_deg"]))
	var highest: float = INF
	for corner: Vector2 in [SKULL_LOCAL_RECT.position, Vector2(SKULL_LOCAL_RECT.end.x, SKULL_LOCAL_RECT.position.y), SKULL_LOCAL_RECT.end, Vector2(SKULL_LOCAL_RECT.position.x, SKULL_LOCAL_RECT.end.y)]:
		highest = minf(highest, ((p["head"] as Vector2) + corner.rotated(angle)).y)
	if highest < top:
		p["head"] = (p["head"] as Vector2) + Vector2(0.0, top - highest)


static func _apply_crouch(p: Dictionary, cover: bool) -> void:
	# Foreshortened torso and folded knees, not a standing body shifted down.
	p["stance"] = "COVER" if cover else "KNEEL"
	p["head"] = Vector2(-0.35 if cover else 0.85, -8.40625)
	p["head_tilt_deg"] = 12.0 if cover else 0.0
	p["chest"] = Vector2(-0.8, -4.8)
	p["hip"] = Vector2(-1.5, -3.8)
	p["hip_back"] = Vector2(-2.5, -3.7)
	p["hip_front"] = Vector2(-0.5, -3.7)
	p["knee_back"] = Vector2(-4.0, -1.5)
	p["ankle_back"] = Vector2(-2.4, -0.9)
	p["knee_front"] = Vector2(3.2, -3.2)
	p["ankle_front"] = Vector2(3.8, -0.9)
	p["shoulder_front"] = Vector2(1.3, -4.8)
	p["shoulder_back"] = Vector2(-2.8, -4.8)
	p["elbow_front"] = Vector2(4.0, -4.0)
	p["hand_front"] = Vector2(3.2, -9.0 if cover else -5.6)
	p["elbow_back"] = Vector2(-4.5, -3.5)
	p["hand_back"] = Vector2(-2.1, -6.2)
	_fit_skull_under(p, -12.0)


static func _melee_weapon(p: Dictionary, st: String, t: float) -> void:
	var combo: int = 3 if st.ends_with("03") else (2 if st.ends_with("02") else 1)
	var hit: float = 3.0 + float(combo - 1) * 0.5
	var weight: float = _strike_weight(t, hit, 10.0)
	var heavy: bool = st.begins_with("AXE") or st.begins_with("BAT") or st.begins_with("PIPE")
	var saw: bool = st.begins_with("CHAINSAW")
	p["family"] = "chainsaw" if saw else ("melee_heavy" if heavy else "melee_blade")
	p["phase"] = "windup" if t < hit else ("contact" if t < hit + 0.8 else "recovery")
	p["contact"] = t >= hit and t < hit + 0.8
	_shift_upper(p, Vector2(weight * 1.6, 0.0))
	if saw:
		p["hand_front"] = Vector2(6.4, -9.4)
		p["hand_back"] = Vector2(3.3, -8.6)
		p["elbow_front"] = Vector2(4.2, -7.1)
		p["weapon_angle_deg"] = -5.0
	elif heavy:
		p["hand_front"] = Vector2(-1.7, -16.3).lerp(Vector2(7.4, -7.6), weight)
		p["hand_back"] = Vector2(-3.3, -14.4).lerp(Vector2(4.5, -7.4), weight)
		p["elbow_front"] = Vector2(2.8, -14.0).lerp(Vector2(5.0, -9.9), weight)
		p["weapon_angle_deg"] = lerpf(-126.0, 20.0, weight)
	else:
		var start: Vector2 = Vector2(-4.1, -12.0) if combo != 2 else Vector2(3.0, -5.7)
		var finish: Vector2 = Vector2(9.2, -8.6) if combo != 2 else Vector2(8.0, -13.8)
		p["hand_front"] = start.lerp(finish, weight)
		p["elbow_front"] = Vector2(0.0, -8.0).lerp(Vector2(5.0, -9.5), weight)
		p["hand_back"] = Vector2(-2.0, -10.8)
		p["weapon_angle_deg"] = lerpf(-115.0 if combo != 2 else 45.0, 18.0 if combo != 2 else -68.0, weight)


static func _climb(p: Dictionary, st: String, t: float) -> void:
	p["family"] = "ledge" if st == "LEDGE_GRAB" else ("slide" if st == "SLIDE" else "climb")
	var reach: float = sin(fposmod(t, 8.0) / 8.0 * TAU) if st == "CLIMB" else 0.0
	if st == "LEDGE_GRAB":
		_shift_upper(p, Vector2(-0.7, 0.0))
		p["elbow_front"] = Vector2(2.8, -12.2)
		p["hand_front"] = Vector2(4.0, -15.2)
		p["elbow_back"] = Vector2(-1.4, -12.2)
		p["hand_back"] = Vector2(1.2, -15.0)
		p["knee_front"] = Vector2(4.2, -6.9)
		p["ankle_front"] = Vector2(4.6, -4.6)
		p["knee_back"] = Vector2(-3.3, -5.3)
		p["ankle_back"] = Vector2(-1.9, -2.3)
		return
	# Symmetric rear-view ladder climbing / sliding posture (character faces into the ladder)
	p["hip"] = Vector2(0.0, -5.6)
	p["chest"] = Vector2(0.0, -10.7)
	p["head"] = Vector2(0.0, -14.40625)
	p["head_tilt_deg"] = 0.0
	p["shoulder_back"] = Vector2(-2.0, -10.3)
	p["shoulder_front"] = Vector2(2.0, -10.3)
	p["hip_back"] = Vector2(-1.5, -5.35)
	p["hip_front"] = Vector2(1.5, -5.35)
	if st == "SLIDE":
		p["elbow_back"] = Vector2(-3.1, -11.4)
		p["hand_back"] = Vector2(-2.3, -13.8)
		p["elbow_front"] = Vector2(3.1, -11.4)
		p["hand_front"] = Vector2(2.3, -13.8)
		p["knee_back"] = Vector2(-2.7, -4.4)
		p["ankle_back"] = Vector2(-2.1, -1.6)
		p["knee_front"] = Vector2(2.7, -4.4)
		p["ankle_front"] = Vector2(2.1, -1.6)
	else:
		p["elbow_back"] = Vector2(-3.2, -13.2)
		p["hand_back"] = Vector2(-2.4, -16.8 + reach * 1.5)
		p["elbow_front"] = Vector2(3.2, -13.2)
		p["hand_front"] = Vector2(2.4, -16.8 - reach * 1.5)
		p["knee_back"] = Vector2(-3.0, -5.3 - reach * 0.9)
		p["ankle_back"] = Vector2(-2.0, -2.3 - reach * 1.5)
		p["knee_front"] = Vector2(3.0, -5.3 + reach * 0.9)
		p["ankle_front"] = Vector2(2.0, -2.3 + reach * 1.5)


static func _powered(p: Dictionary, st: String, t: float) -> void:
	var slot: int = 3 if st == "SHUNPO_SLASH" else (2 if st == "CHAKRA_WAVE" else clampi(int(st.get_slice("_", st.get_slice_count("_") - 1)), 1, 4))
	# Current custom fighter JSONs start Clsn1 after the first 2-frame pose.
	var hit: float = 2.0
	var weight: float = _strike_weight(t, hit, float(p["length"]))
	p["family"] = "powered_" + str(slot)
	if st == "SHUNPO_SLASH":
		p["family"] = "powered_dash_slash"
	elif st == "CHAKRA_WAVE":
		p["family"] = "powered_wave"
	p["phase"] = "charge" if t < hit else "release"
	p["contact"] = t >= hit and t < float(p["length"])
	p["ankle_back"] = Vector2(-4.3, -1.0)
	p["ankle_front"] = Vector2(3.3, -1.0)
	if st.begins_with("MUGEN_COMBO") or slot == 3:
		p["hand_front"] = Vector2(1.0, -9.0).lerp(Vector2(11.7, -11.2), weight)
		p["elbow_front"] = Vector2(0.0, -7.2).lerp(Vector2(6.8, -10.0), weight)
		p["hand_back"] = Vector2(-2.5, -12.0)
		_shift_upper(p, Vector2(weight * 1.7, 0.0))
	elif slot == 2:
		p["hand_front"] = Vector2(2.7, -15.9)
		p["elbow_front"] = Vector2(4.1, -12.8)
		p["hand_back"] = Vector2(-4.0, -11.7)
	else:
		p["hand_front"] = Vector2(-0.4, -9.7).lerp(Vector2(8.0, -11.0), weight)
		p["hand_back"] = Vector2(-2.1, -10.4).lerp(Vector2(6.0, -10.7), weight)
		p["elbow_front"] = Vector2(0.7, -7.5).lerp(Vector2(4.3, -8.5), weight)
		p["elbow_back"] = Vector2(-3.0, -7.6).lerp(Vector2(1.6, -9.1), weight)

class_name Locomotion
extends RefCounted

## Data-driven walk/jump/crouch/sprint/roll/pit/camera constants.
## Clock is ledger:RL-SIM-FIXED-60 (assumption). Jump/crouch stay
## ledger:RL-MOVE-JUMP-CROUCH (assumption). Sprint stays
## ledger:RL-MOVE-SPRINT (assumption). Roll stays
## ledger:RL-MOVE-ROLL (assumption). Dive stays
## ledger:RL-MOVE-DIVE (assumption). Jump-kick stays
## ledger:RL-MOVE-JUMP-KICK (assumption). Fall stays
## ledger:RL-MOVE-FALL (assumption). Camera stays
## ledger:RL-CAM-ARENA (assumption). Hold-to-aim stays
## ledger:RL-CTRL-HOLD-AIM (assumption). Y8 dive/kick observation
## stays ledger:RL-MOVE-ROLL-DIVE (unavailable). Not a Y8 play observation.

const PATH: String = "res://data/sim/locomotion.json"
const SCHEMA_ID: String = "vf.sim.locomotion.v1"

static var _cache: Dictionary = {}


static func data() -> Dictionary:
	if _cache.is_empty():
		_cache = SimConstants.load_json(PATH)
	return _cache


static func movement() -> Dictionary:
	var raw: Variant = data().get("movement", {})
	if raw is Dictionary:
		return raw as Dictionary
	return {}


static func camera() -> Dictionary:
	var raw: Variant = data().get("camera", {})
	if raw is Dictionary:
		return raw as Dictionary
	return {}


static func f(key: String, fallback: float) -> float:
	return float(movement().get(key, fallback))


static func epsilon() -> float:
	return float(data().get("epsilon", SimConstants.EPSILON))


static func designed_view() -> Vector2:
	var cam: Dictionary = camera()
	return Vector2(
		float(cam.get("designed_view_x", Maps.DESIGNED_VIEW.x)),
		float(cam.get("designed_view_y", Maps.DESIGNED_VIEW.y))
	)


static func vec2(key: String, fallback: Vector2) -> Vector2:
	var raw: Variant = movement().get(key, [])
	if raw is Array:
		var arr: Array = raw as Array
		if arr.size() >= 2:
			return Vector2(float(arr[0]), float(arr[1]))
	return fallback


static func apply_to(fighter: Fighter) -> void:
	if fighter == null:
		return
	fighter.gravity = f("gravity", 1700.0)
	fighter.jump_vel = f("jump_vel", -430.0)
	fighter.walk = f("walk", 170.0)
	fighter.sprint = f("sprint", 260.0)
	fighter.crouch_speed = f("crouch_speed", 70.0)
	fighter.aim_speed = f("aim_speed", 55.0)
	fighter.climb = f("climb", 140.0)
	fighter.accel = f("accel", 2400.0)
	fighter.air_accel = f("air_accel", 1400.0)
	fighter.friction = f("friction", 2000.0)
	fighter.coyote_time = f("coyote", 0.09)
	fighter.jump_buf_time = f("jump_buf", 0.10)
	fighter.tap_window = f("tap_window", 0.22)
	fighter.stamina_sprint_drain = f("stamina_sprint_drain", 28.0)
	fighter.stamina_recover = f("stamina_recover", 22.0)
	fighter.stamina_roll_cost = f("stamina_roll_cost", 22.0)
	fighter.stamina_dive_cost = f("stamina_dive_cost", 18.0)
	fighter.roll_duration = f("roll_duration", 0.28)
	fighter.roll_invuln = f("roll_invuln", 0.20)
	fighter.roll_speed = f("roll_speed", 320.0)
	fighter.dive_duration = f("dive_duration", 0.36)
	fighter.dive_invuln = f("dive_invuln", 0.16)
	fighter.dive_speed = f("dive_speed", 300.0)
	fighter.dive_down = f("dive_down", 420.0)
	fighter.kick_duration = f("kick_duration", 0.18)
	fighter.kick_impulse_x = f("kick_impulse_x", 90.0)
	fighter.kick_impulse_y = f("kick_impulse_y", 220.0)
	fighter.kick_damage = f("kick_damage", 12.0)
	fighter.dive_tackle_damage = f("dive_tackle_damage", 14.0)
	fighter.fall_damage_speed = f("fall_damage_speed", 560.0)
	fighter.fall_drop_min = f("fall_drop_min", 28.0)
	fighter.fall_damage = f("fall_damage", 16.0)
	fighter.knockdown_time = f("knockdown_time", 0.28)
	fighter.variable_jump_cut = f("variable_jump_cut", 0.45)
	fighter.variable_jump_cut_vy = f("variable_jump_cut_vy", -80.0)
	fighter.max_fall_speed = f("max_fall_speed", 800.0)
	var stand: Vector2 = vec2("stand_size", Vector2(10, 22))
	var crouch: Vector2 = vec2("crouch_size", Vector2(10, 14))
	var roll: Vector2 = vec2("roll_size", Vector2(14, 12))
	var dive: Vector2 = vec2("dive_size", Vector2(12, 11))
	var stand_off: Vector2 = vec2("stand_offset", Vector2(0, 1))
	var crouch_off: Vector2 = vec2("crouch_offset", Vector2(0, 5))
	var roll_off: Vector2 = vec2("roll_offset", Vector2(0, 6))
	var dive_off: Vector2 = vec2("dive_offset", Vector2(0, 7))
	if fighter.stand_shape != null:
		fighter.stand_shape.size = stand
	if fighter.crouch_shape != null:
		fighter.crouch_shape.size = crouch
	if fighter.roll_shape != null:
		fighter.roll_shape.size = roll
	if fighter.dive_shape != null:
		fighter.dive_shape.size = dive
	fighter.stand_offset = stand_off
	fighter.crouch_offset = crouch_off
	fighter.roll_offset = roll_off
	fighter.dive_offset = dive_off
	fighter._apply_shape()

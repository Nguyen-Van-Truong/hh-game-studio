class_name Locomotion
extends RefCounted

## Data-driven walk/jump/crouch/pit/camera constants (VF2-WP2).
## Clock is ledger:RL-SIM-FIXED-60 (assumption). Jump/crouch stay
## ledger:RL-MOVE-JUMP-CROUCH (assumption). Camera stays
## ledger:RL-CAM-ARENA (assumption). Hold-to-aim stays
## ledger:RL-CTRL-HOLD-AIM (assumption). Roll/dive stay
## ledger:RL-MOVE-ROLL-DIVE (unavailable). Not a Y8 play observation.

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
	fighter.variable_jump_cut = f("variable_jump_cut", 0.45)
	fighter.variable_jump_cut_vy = f("variable_jump_cut_vy", -80.0)
	fighter.max_fall_speed = f("max_fall_speed", 800.0)
	var stand: Vector2 = vec2("stand_size", Vector2(10, 22))
	var crouch: Vector2 = vec2("crouch_size", Vector2(10, 14))
	var stand_off: Vector2 = vec2("stand_offset", Vector2(0, 1))
	var crouch_off: Vector2 = vec2("crouch_offset", Vector2(0, 5))
	if fighter.stand_shape != null:
		fighter.stand_shape.size = stand
	if fighter.crouch_shape != null:
		fighter.crouch_shape.size = crouch
	fighter.stand_offset = stand_off
	fighter.crouch_offset = crouch_off
	fighter._apply_shape()

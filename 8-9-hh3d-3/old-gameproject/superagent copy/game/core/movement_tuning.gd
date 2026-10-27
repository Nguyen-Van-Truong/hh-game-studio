class_name MovementTuning
extends RefCounted
## Engineering seeds only. Loading is centralized so the lab and replay agree.

const REQUIRED: Array[StringName] = [
	&"max_health", &"acceleration_per_tick", &"max_horizontal_speed", &"friction_per_tick",
	&"gravity_per_tick", &"terminal_fall_speed", &"jump_speed", &"jump_lock_ticks",
	&"climb_speed", &"respawn_delay_ticks", &"char_height", &"char_width",
	&"down_tap_window_ticks", &"drop_through_ticks",
	&"max_stamina", &"sprint_speed", &"sprint_tap_window_ticks", &"sprint_drain_per_tick",
	&"stamina_idle_regen_per_tick", &"stamina_moving_regen_per_tick",
	&"punch_damage", &"punch_range", &"jump_kick_damage", &"shoot_damage", &"shoot_range",
	&"attack_cooldown_ticks", &"hitstun_duration_ticks", &"knockdown_duration_ticks",
	&"knockdown_invulnerability_ticks", &"bullet_knockback", &"melee_knockback",
	&"grenade_damage", &"grenade_radius", &"grenade_fuse_ticks", &"grenade_throw_speed",
	&"grenade_count",
	&"roll_speed", &"roll_duration_ticks", &"roll_recovery_ticks", &"roll_height",
	&"burn_duration_ticks", &"burn_interval_ticks", &"burn_damage",
	&"dive_speed", &"dive_duration_ticks", &"dive_height", &"dive_damage", &"dive_invulnerability_ticks",
	&"tackle_speed", &"tackle_duration_ticks", &"tackle_height", &"tackle_damage",
	&"grab_duration_ticks", &"combo_window_ticks", &"combo_kick_damage", &"combo_kick_range",
	&"shoot_cooldown_ticks", &"grab_punch_damage", &"grab_throw_damage",
]

# SA5 N4 keeps tick counters/resources integral while allowing movement values
# to be calibrated below one pixel per tick.  Values are still expressed in
# simulation units (pixels per tick or pixels per tick squared); the physics
# adapter is responsible for converting them to Godot's per-second velocity.
const FLOAT_KEYS: Array[StringName] = [
	&"acceleration_per_tick", &"max_horizontal_speed", &"friction_per_tick",
	&"gravity_per_tick", &"terminal_fall_speed", &"jump_speed", &"climb_speed",
	&"char_height", &"char_width", &"sprint_speed", &"punch_range", &"shoot_range",
	&"bullet_knockback", &"melee_knockback", &"grenade_radius", &"grenade_throw_speed",
	&"roll_speed", &"roll_height", &"dive_speed", &"dive_height", &"tackle_speed", &"tackle_height", &"combo_kick_range",
]

const INTEGER_KEYS: Array[StringName] = [
	&"max_health", &"jump_lock_ticks", &"respawn_delay_ticks",
	&"down_tap_window_ticks", &"drop_through_ticks", &"max_stamina",
	&"sprint_tap_window_ticks", &"sprint_drain_per_tick",
	&"stamina_idle_regen_per_tick", &"stamina_moving_regen_per_tick",
	&"punch_damage", &"jump_kick_damage", &"shoot_damage", &"attack_cooldown_ticks",
	&"hitstun_duration_ticks", &"knockdown_duration_ticks",
	&"knockdown_invulnerability_ticks", &"grenade_damage", &"grenade_fuse_ticks",
	&"grenade_count",
	&"roll_duration_ticks", &"roll_recovery_ticks",
	&"burn_duration_ticks", &"burn_interval_ticks", &"burn_damage", &"dive_duration_ticks", &"dive_damage", &"dive_invulnerability_ticks",
	&"tackle_duration_ticks", &"tackle_damage", &"grab_duration_ticks", &"combo_window_ticks", &"combo_kick_damage", &"shoot_cooldown_ticks", &"grab_punch_damage", &"grab_throw_damage",
]

static func load_default() -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://data/tuning.json"))
	var values: Dictionary = decode(parsed)
	if values.is_empty():
		push_error("Invalid movement tuning; refusing to use hidden defaults")
	return values

static func decode(parsed: Variant) -> Dictionary:
	if typeof(parsed) != TYPE_DICTIONARY:
		return {}
	var config: Dictionary = parsed
	if config.get("schema") != "sa03.tuning.v3" or config.get("status") != "UNVERIFIED_PLACEHOLDER":
		return {}
	if config.get("fixed_hz") != 60 or typeof(config.get("movement")) != TYPE_DICTIONARY:
		return {}
	if typeof(config.get("references")) != TYPE_DICTIONARY:
		return {}
	var movement: Dictionary = config["movement"]
	var references: Dictionary = config["references"]
	if movement.size() != REQUIRED.size() or references.size() != REQUIRED.size():
		return {}
	var result: Dictionary = {}
	if FLOAT_KEYS.size() + INTEGER_KEYS.size() != REQUIRED.size():
		return {}
	for key: StringName in REQUIRED:
		if not FLOAT_KEYS.has(key) and not INTEGER_KEYS.has(key):
			return {}
		var label: String = String(key)
		var value: Variant = movement.get(label)
		if typeof(value) != TYPE_INT and typeof(value) != TYPE_FLOAT:
			return {}
		var number: float = float(value)
		var lower_bound: float = 0.000001 if FLOAT_KEYS.has(key) else 1.0
		if not is_finite(number) or number < lower_bound or number > 10000.0:
			return {}
		if INTEGER_KEYS.has(key) and number != floor(number):
			return {}
		if typeof(references.get(label)) != TYPE_STRING or not String(references[label]).begins_with("R"):
			return {}
		result[key] = number if FLOAT_KEYS.has(key) else int(number)
	if float(result[&"char_width"]) > float(result[&"char_height"]):
		return {}
	if float(result[&"roll_height"]) >= float(result[&"char_height"]):
		return {}
	if float(result[&"dive_height"]) >= float(result[&"char_height"]):
		return {}
	if float(result[&"sprint_speed"]) <= float(result[&"max_horizontal_speed"]):
		return {}
	if int(result[&"stamina_idle_regen_per_tick"]) <= int(result[&"stamina_moving_regen_per_tick"]):
		return {}
	if int(result[&"sprint_drain_per_tick"]) > int(result[&"max_stamina"]):
		return {}
	return result

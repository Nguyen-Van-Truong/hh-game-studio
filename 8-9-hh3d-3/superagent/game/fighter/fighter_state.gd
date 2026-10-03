class_name FighterState
extends RefCounted
## Integer-only fighter state advanced by Simulation at exactly 60 Hz.
## This class intentionally contains no Node or engine-physics authority.

enum Locomotion {
	GROUNDED,
	AIRBORNE,
	CLIMBING,
	FALLING,
	DOWNED,
}

const ACTION_SUFFIXES: Array[StringName] = [
	&"left", &"right", &"up", &"down", &"punch", &"shoot", &"throw", &"power",
]

var player_id: int
var position: Vector2i
var velocity: Vector2i = Vector2i.ZERO
var facing: int = 1
var health: int = 100
var grounded: bool = true
var in_pit: bool = false
var locomotion: int = Locomotion.GROUNDED
var action_name: StringName = &"idle"
var action_timer_ticks: int = 0
var jump_lock_ticks: int = 0
var hitstun_ticks: int = 0
var downed_ticks: int = 0

func _init(id: int, spawn: Vector2i) -> void:
	player_id = id
	position = spawn

func step(actions: Dictionary, arena: ArenaState, tuning: Dictionary) -> void:
	if action_timer_ticks > 0:
		action_timer_ticks -= 1
	if jump_lock_ticks > 0:
		jump_lock_ticks -= 1
	if hitstun_ticks > 0:
		hitstun_ticks -= 1

	if locomotion == Locomotion.DOWNED:
		_step_downed(arena, tuning)
		return

	var acceleration: int = int(tuning.get(&"acceleration_per_tick", 2))
	var max_speed: int = int(tuning.get(&"max_horizontal_speed", 72))
	var friction: int = int(tuning.get(&"friction_per_tick", 3))
	var gravity: int = int(tuning.get(&"gravity_per_tick", 5))
	var jump_speed: int = int(tuning.get(&"jump_speed", 88))
	var climb_speed: int = int(tuning.get(&"climb_speed", 4))
	var axis: int = 0
	if _held(actions, &"left"):
		axis -= 1
	if _held(actions, &"right"):
		axis += 1
	if axis != 0:
		velocity.x = clampi(velocity.x + axis * acceleration, -max_speed, max_speed)
		facing = axis
	else:
		velocity.x = _approach_zero(velocity.x, friction)

	var on_ladder: bool = arena.ladder_at(position.x, position.y)
	if on_ladder and (_held(actions, &"up") or _held(actions, &"down")):
		locomotion = Locomotion.CLIMBING
		grounded = false
		velocity.y = 0
		if _held(actions, &"up"):
			position.y -= climb_speed
		elif _held(actions, &"down"):
			position.y += climb_speed
		if _pressed(actions, &"jump"):
			locomotion = Locomotion.AIRBORNE
			velocity.y = -jump_speed
		else:
			position.y = clampi(position.y, 270, arena.floor_y)
			position.x = clampi(position.x, 0, arena.width)
			_update_action(actions, &"climb", 1)
			return

	if grounded and _pressed(actions, &"up") and jump_lock_ticks == 0:
		velocity.y = -jump_speed
		grounded = false
		locomotion = Locomotion.AIRBORNE
		jump_lock_ticks = int(tuning.get(&"jump_lock_ticks", 6))
		action_name = &"jump"
		action_timer_ticks = 1
	else:
		if not grounded:
			velocity.y = mini(velocity.y + gravity, int(tuning.get(&"terminal_fall_speed", 120)))
		else:
			velocity.y = 0

	var previous_y: int = position.y
	position.x = clampi(position.x + velocity.x, 0, arena.width)
	var candidate_y: int = position.y + velocity.y
	var landing: int = arena.landing_y(position.x, previous_y, candidate_y)
	if landing >= 0 and velocity.y >= 0:
		position.y = landing
		velocity.y = 0
		grounded = true
		locomotion = Locomotion.GROUNDED
		in_pit = false
	else:
		position.y = candidate_y
		grounded = false
		locomotion = Locomotion.FALLING if velocity.y >= 0 else Locomotion.AIRBORNE
		if arena.is_in_pit(position.x):
			in_pit = true
			locomotion = Locomotion.FALLING

	if position.y > arena.pit_death_y:
		health = 0
		locomotion = Locomotion.DOWNED
		downed_ticks = int(tuning.get(&"respawn_delay_ticks", 90))
		action_name = &"pit_fall"
		action_timer_ticks = downed_ticks
		return

	if grounded and _held(actions, &"down"):
		_update_action(actions, &"crouch", 1)
	else:
		_apply_explicit_action(actions)

func snapshot() -> Dictionary:
	var result: Dictionary = {
		&"player_id": player_id,
		&"x": position.x,
		&"y": position.y,
		&"vx": velocity.x,
		&"vy": velocity.y,
		&"facing": facing,
		&"health": health,
		&"grounded": grounded,
		&"in_pit": in_pit,
		&"locomotion": locomotion,
		&"action": action_name,
		&"action_timer_ticks": action_timer_ticks,
		&"jump_lock_ticks": jump_lock_ticks,
		&"hitstun_ticks": hitstun_ticks,
		&"downed_ticks": downed_ticks,
	}
	result.make_read_only()
	return result

func canonical_fragment() -> String:
	return "fighter=%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%s,%d,%d,%d,%d" % [
		player_id,
		position.x,
		position.y,
		velocity.x,
		velocity.y,
		facing,
		health,
		int(grounded),
		int(in_pit),
		locomotion,
		String(action_name),
		action_timer_ticks,
		jump_lock_ticks,
		hitstun_ticks,
		downed_ticks,
	]

func _step_downed(arena: ArenaState, tuning: Dictionary) -> void:
	if downed_ticks > 0:
		downed_ticks -= 1
		velocity = Vector2i.ZERO
		return
	var spawn: Vector2i = arena.spawn_for_player(player_id)
	position = spawn
	velocity = Vector2i.ZERO
	health = int(tuning.get(&"max_health", 100))
	grounded = true
	in_pit = false
	locomotion = Locomotion.GROUNDED
	action_name = &"respawn"
	action_timer_ticks = 1

func _apply_explicit_action(actions: Dictionary) -> void:
	if _pressed(actions, &"punch"):
		_update_action(actions, &"punch", 6)
	elif _pressed(actions, &"shoot"):
		_update_action(actions, &"shoot", 3)
	elif _pressed(actions, &"throw"):
		_update_action(actions, &"throw", 8)
	elif _pressed(actions, &"power"):
		_update_action(actions, &"power", 10)
	elif action_timer_ticks == 0:
		action_name = &"idle"

func _update_action(_actions: Dictionary, name: StringName, duration_ticks: int) -> void:
	action_name = name
	action_timer_ticks = duration_ticks

func _held(actions: Dictionary, suffix: StringName) -> bool:
	return bool(actions.get(StringName("%s_held" % String(suffix)), false))

func _pressed(actions: Dictionary, suffix: StringName) -> bool:
	return bool(actions.get(StringName("%s_pressed" % String(suffix)), false))

func _approach_zero(value: int, amount: int) -> int:
	if value > 0:
		return maxi(0, value - amount)
	if value < 0:
		return mini(0, value + amount)
	return 0

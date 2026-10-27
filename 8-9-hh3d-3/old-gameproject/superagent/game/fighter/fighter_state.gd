class_name FighterState
extends RefCounted
## Float gameplay state advanced at 60 Hz. CharacterBody2D owns movement
## resolution; this state owns intent, timers, resources and combat decisions.

enum Locomotion {
	GROUNDED,
	AIRBORNE,
	CLIMBING,
	FALLING,
	DOWNED,
}

const ACTION_SUFFIXES: Array[StringName] = [
	&"left", &"right", &"up", &"down", &"punch", &"shoot", &"throw", &"power", &"switch",
]
const SPRINT_SCRIPT = preload("res://game/fighter/sprint_state.gd")
const AIM_STEP_RADIANS: float = 0.08
const MAX_AIM_ANGLE_RADIANS: float = 0.9

var player_id: int
var position: Vector2
var velocity: Vector2 = Vector2.ZERO
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
var drop_through_ticks: int = 0
var down_tap_window_remaining: int = 0
var attack_name: StringName = &"none"
var attack_timer_ticks: int = 0
var attack_cooldown_ticks: int = 0
var queued_attack: StringName = &"none"
var aiming: bool = false
var aim_angle: float = 0.0
var knockdown_ticks: int = 0
var invulnerability_ticks: int = 0
var ammo: int = 6
var grenades: int = 3
var power_charges: int = 0
var power_duration_ticks: int = 300
var active_weapon_slot: int = 1
var bullet_time_active: bool = false
var tempo_divisor: int = 1
var tempo_phase: int = 0
var tempo_pending_actions: Dictionary = {}
var roll_ticks: int = 0
var roll_recovery_ticks: int = 0
var roll_direction: int = 0
var roll_low_posture: bool = false
var dive_ticks: int = 0
var dive_direction: int = 0
var dive_low_posture: bool = false
var tackle_ticks: int = 0
var tackle_direction: int = 0
var tackle_low_posture: bool = false
var grabbed_ticks: int = 0
var grabbed_by: int = 0
var hold_ticks: int = 0
var hold_target: int = 0
var combo_step: int = 0
var combo_window_ticks: int = 0
var combo_buffered: bool = false
var last_damage: int = 0
var last_hit_kind: StringName = &"none"
var sprint: SprintState = SPRINT_SCRIPT.new()

func _init(id: int, spawn: Vector2) -> void:
	player_id = id
	position = spawn

func step(actions: Dictionary, arena: ArenaState, tuning: Dictionary, body: PhysicsFighter2D) -> void:
	if tempo_divisor > 1:
		tempo_phase = (tempo_phase + 1) % tempo_divisor
		if tempo_phase != 0:
			_buffer_tempo_actions(actions)
			return
	actions = _consume_tempo_actions(actions)
	var down_tap_open: bool = down_tap_window_remaining > 0
	action_timer_ticks = maxi(0, action_timer_ticks - 1)
	jump_lock_ticks = maxi(0, jump_lock_ticks - 1)
	hitstun_ticks = maxi(0, hitstun_ticks - 1)
	drop_through_ticks = maxi(0, drop_through_ticks - 1)
	down_tap_window_remaining = maxi(0, down_tap_window_remaining - 1)
	attack_timer_ticks = maxi(0, attack_timer_ticks - 1)
	attack_cooldown_ticks = maxi(0, attack_cooldown_ticks - 1)
	combo_window_ticks = maxi(0, combo_window_ticks - 1)
	if combo_window_ticks == 0:
		combo_step = 0
		combo_buffered = false
	invulnerability_ticks = maxi(0, invulnerability_ticks - 1)
	roll_recovery_ticks = maxi(0, roll_recovery_ticks - 1)
	last_damage = 0
	last_hit_kind = &"none"
	_update_aim_state(actions)

	if locomotion == Locomotion.DOWNED:
		aiming = false
		down_tap_window_remaining = 0
		drop_through_ticks = 0
		sprint.cancel_gesture()
		_step_downed(arena, tuning)
		if action_name == &"respawn":
			body.set_posture_height(float(tuning[&"char_height"]))
			roll_low_posture = false
			dive_low_posture = false
			body.set_drop_through(false)
			body.sync_from_state(position, velocity)
		return

	if grabbed_ticks > 0:
		_step_grabbed(actions, arena, tuning, body)
		return
	if hold_ticks > 0:
		_step_hold(actions, arena, tuning, body)
		return

	# A roll can finish under a low ceiling. Keep the short collider until the
	# read-back query proves that the normal standing height is clear.
	if roll_ticks == 0 and dive_ticks == 0:
		_maintain_roll_posture(body, tuning)
		_maintain_dive_posture(body, tuning)

	if dive_ticks > 0:
		_step_dive(arena, tuning, body)
		return

	if tackle_ticks > 0:
		_step_tackle(arena, tuning, body)
		return

	if roll_ticks > 0:
		_step_roll(arena, tuning, body)
		return

	var gravity: float = float(tuning[&"gravity_per_tick"])
	var terminal_speed: float = float(tuning[&"terminal_fall_speed"])
	if knockdown_ticks > 0:
		aiming = false
		sprint.cancel_gesture()
		knockdown_ticks -= 1
		velocity.x = move_toward(velocity.x, 0.0, float(tuning[&"friction_per_tick"]))
		velocity.y = minf(velocity.y + gravity, terminal_speed)
		_move_body(body)
		_update_locomotion(arena, tuning)
		if locomotion != Locomotion.DOWNED:
			action_name = &"knockdown" if knockdown_ticks > 0 else &"idle"
		return

	var axis: int = int(_held(actions, &"right")) - int(_held(actions, &"left"))
	var shoot_held: bool = _held(actions, &"shoot")
	var shoot_event: bool = shoot_held or _pressed(actions, &"shoot") or _released(actions, &"shoot")
	if _can_start_tackle(actions, axis, shoot_event):
		_start_tackle(axis, arena, tuning, body)
		return
	if _can_start_dive(actions, axis, shoot_event):
		_start_dive(axis, arena, tuning, body)
		return
	if _can_start_roll(actions, axis, shoot_event, arena, tuning):
		_start_roll(axis, arena, tuning, body)
		return
	# Down+Punch is the Classic pickup gesture. It must win over ladder
	# traversal when a weapon/item is at the ladder foot; otherwise the
	# interaction can never reach MatchSession._collect_pickups.
	var entering_ladder: bool = not shoot_event and not _pressed(actions, &"punch") and arena.ladder_at(position.x, position.y) and (_held(actions, &"up") or _held(actions, &"down"))
	var can_sprint: bool = not entering_ladder and not _held(actions, &"down") and hitstun_ticks == 0
	sprint.step(actions, grounded, can_sprint, grounded and velocity.is_zero_approx(), tuning)
	var max_speed: float = float(tuning[&"sprint_speed"] if sprint.direction != 0 else tuning[&"max_horizontal_speed"])
	if axis != 0:
		velocity.x = clampf(velocity.x + float(axis) * float(tuning[&"acceleration_per_tick"]), -max_speed, max_speed)
		facing = axis
	else:
		velocity.x = move_toward(velocity.x, 0.0, float(tuning[&"friction_per_tick"]))

	if entering_ladder:
		down_tap_window_remaining = 0
		drop_through_ticks = 0
		var ladder_top: float = arena.ladder_top_at(position.x, position.y)
		var ladder_bottom: float = arena.ladder_bottom_at(position.x, position.y)
		var climb_direction: float = -1.0 if _held(actions, &"up") else 1.0
		var next_y: float = clampf(position.y + climb_direction * float(tuning[&"climb_speed"]), ladder_top, ladder_bottom)
		velocity = Vector2(0.0, next_y - position.y)
		_move_body(body, true)
		locomotion = Locomotion.CLIMBING
		grounded = false
		_update_action(actions, &"climb", 1)
		return

	if grounded and not shoot_event and _pressed(actions, &"up") and jump_lock_ticks == 0:
		down_tap_window_remaining = 0
		velocity.y = -float(tuning[&"jump_speed"])
		grounded = false
		jump_lock_ticks = int(tuning[&"jump_lock_ticks"])
		action_name = &"jump"
		action_timer_ticks = 1
	else:
		# Downward contact motion is needed even at rest for move_and_slide to
		# refresh floor contact. No second position integrator exists here.
		velocity.y = minf(velocity.y + gravity, terminal_speed)
		if not shoot_event and grounded and arena.on_one_way(position.x, position.y, float(tuning[&"char_width"]) * 0.5):
			for _press: int in range(int(actions.get(&"down_press_count", 0))):
				if down_tap_open:
					drop_through_ticks = int(tuning[&"drop_through_ticks"])
					down_tap_window_remaining = 0
					break
				down_tap_window_remaining = int(tuning[&"down_tap_window_ticks"])
				down_tap_open = true
		else:
			down_tap_window_remaining = 0

	_move_body(body)
	_update_locomotion(arena, tuning)
	if locomotion == Locomotion.DOWNED:
		return
	if grounded and not shoot_event and _held(actions, &"down") and not _pressed(actions, &"punch"):
		_update_action(actions, &"crouch", 1)
	else:
		_apply_explicit_action(actions, tuning)

func _move_body(body: PhysicsFighter2D, climbing: bool = false) -> void:
	body.floor_snap_length = 0.0 if climbing or drop_through_ticks > 0 else 5.0
	body.set_drop_through(climbing or drop_through_ticks > 0)
	body.set_tick_velocity(velocity)
	body.move_fixed_step()
	position = body.position
	velocity = body.velocity / PhysicsFighter2D.FIXED_HZ
	grounded = body.is_on_floor()

func _can_start_roll(actions: Dictionary, axis: int, shoot_event: bool, arena: ArenaState, tuning: Dictionary) -> bool:
	var on_one_way: bool = arena.on_one_way(position.x, position.y, float(tuning[&"char_width"]) * 0.5)
	return health > 0 and grounded and locomotion == Locomotion.GROUNDED and not on_one_way and axis != 0 and _pressed(actions, &"down") and roll_ticks == 0 and roll_recovery_ticks == 0 and not roll_low_posture and hitstun_ticks == 0 and not aiming and not shoot_event and not _pressed(actions, &"punch") and not _pressed(actions, &"throw") and not _pressed(actions, &"power") and sprint.direction == 0

func _can_start_tackle(actions: Dictionary, axis: int, shoot_event: bool) -> bool:
	return health > 0 and grounded and locomotion == Locomotion.GROUNDED and axis != 0 and _pressed(actions, &"down") and tackle_ticks == 0 and not tackle_low_posture and hitstun_ticks == 0 and not aiming and not shoot_event and not _pressed(actions, &"punch") and not _pressed(actions, &"throw") and not _pressed(actions, &"power") and sprint.direction != 0

func _start_tackle(axis: int, arena: ArenaState, tuning: Dictionary, body: PhysicsFighter2D) -> void:
	tackle_direction = axis if axis != 0 else sprint.direction
	facing = tackle_direction
	tackle_ticks = int(tuning.get(&"tackle_duration_ticks", 14))
	tackle_low_posture = true
	roll_ticks = 0
	roll_low_posture = false
	dive_ticks = 0
	dive_low_posture = false
	aiming = false
	sprint.cancel_gesture()
	body.set_posture_height(float(tuning.get(&"tackle_height", tuning[&"roll_height"])))
	velocity = Vector2(float(tackle_direction) * float(tuning.get(&"tackle_speed", tuning[&"sprint_speed"])), 0.0)
	queued_attack = &"tackle"
	attack_name = &"tackle"
	attack_timer_ticks = tackle_ticks
	attack_cooldown_ticks = int(tuning.get(&"tackle_duration_ticks", 14))
	action_name = &"tackle"
	action_timer_ticks = tackle_ticks
	_move_body(body)
	_update_locomotion(arena, tuning)

func _step_tackle(arena: ArenaState, tuning: Dictionary, body: PhysicsFighter2D) -> void:
	tackle_ticks = maxi(0, tackle_ticks - 1)
	body.set_posture_height(float(tuning.get(&"tackle_height", tuning[&"roll_height"])))
	velocity.x = float(tackle_direction) * float(tuning.get(&"tackle_speed", tuning[&"sprint_speed"]))
	velocity.y = minf(velocity.y + float(tuning[&"gravity_per_tick"]), float(tuning[&"terminal_fall_speed"]))
	_move_body(body)
	action_name = &"tackle" if tackle_ticks > 0 else &"tackle_recover"
	action_timer_ticks = tackle_ticks
	_update_locomotion(arena, tuning)
	if locomotion == Locomotion.DOWNED:
		tackle_ticks = 0
		tackle_low_posture = false
		return
	if tackle_ticks == 0:
		_maintain_tackle_posture(body, tuning)

func _maintain_tackle_posture(body: PhysicsFighter2D, tuning: Dictionary) -> void:
	if not tackle_low_posture:
		return
	body.set_posture_height(float(tuning.get(&"tackle_height", tuning[&"roll_height"])))
	if body.can_stand():
		body.set_posture_height(float(tuning[&"char_height"]))
		tackle_low_posture = false
		tackle_direction = 0
		if grounded:
			velocity = Vector2.ZERO

func _step_grabbed(actions: Dictionary, arena: ArenaState, tuning: Dictionary, body: PhysicsFighter2D) -> void:
	# A tackled fighter is briefly held in place, but still has the classic
	# escape rhythm: a punch breaks the hold before the attacker can throw.
	if _pressed(actions, &"punch"):
		grabbed_ticks = 0
		grabbed_by = 0
		hitstun_ticks = 0
		action_name = &"hit"
		action_timer_ticks = 2
		return
	grabbed_ticks = maxi(0, grabbed_ticks - 1)
	velocity = Vector2.ZERO
	aiming = false
	action_name = &"grabbed" if grabbed_ticks > 0 else &"hit"
	action_timer_ticks = grabbed_ticks
	_move_body(body)
	_update_locomotion(arena, tuning)

func _step_hold(actions: Dictionary, arena: ArenaState, tuning: Dictionary, body: PhysicsFighter2D) -> void:
	# The tackle is a real hold, not a dead-end animation. Punch hits the
	# grabbed opponent; throw releases them with a deterministic shove.
	if _pressed(actions, &"punch"):
		hold_ticks = 0
		hold_target = 0
		attack_name = &"grab_punch"
		queued_attack = attack_name
		attack_timer_ticks = 7
		attack_cooldown_ticks = 8
		action_name = attack_name
		return
	if _pressed(actions, &"throw"):
		hold_ticks = 0
		hold_target = 0
		attack_name = &"grab_throw"
		queued_attack = attack_name
		attack_timer_ticks = 8
		attack_cooldown_ticks = 10
		action_name = attack_name
		return
	hold_ticks = maxi(0, hold_ticks - 1)
	velocity = Vector2.ZERO
	aiming = false
	action_name = &"grab" if hold_ticks > 0 else &"idle"
	action_timer_ticks = hold_ticks
	_move_body(body)
	_update_locomotion(arena, tuning)

func _start_roll(axis: int, arena: ArenaState, tuning: Dictionary, body: PhysicsFighter2D) -> void:
	roll_direction = axis
	roll_ticks = int(tuning[&"roll_duration_ticks"])
	roll_recovery_ticks = 0
	roll_low_posture = true
	aiming = false
	sprint.cancel_gesture()
	body.set_posture_height(float(tuning[&"roll_height"]))
	velocity = Vector2(float(roll_direction) * float(tuning[&"roll_speed"]), 0.0)
	action_name = &"roll"
	action_timer_ticks = roll_ticks
	_move_body(body)
	_update_locomotion(arena, tuning)

func _can_start_dive(actions: Dictionary, axis: int, shoot_event: bool) -> bool:
	return health > 0 and not grounded and (locomotion == Locomotion.AIRBORNE or locomotion == Locomotion.FALLING) and axis != 0 and _pressed(actions, &"down") and dive_ticks == 0 and not dive_low_posture and hitstun_ticks == 0 and attack_cooldown_ticks == 0 and not shoot_event and not _pressed(actions, &"punch") and not _pressed(actions, &"throw") and not _pressed(actions, &"power")

func _start_dive(axis: int, arena: ArenaState, tuning: Dictionary, body: PhysicsFighter2D) -> void:
	dive_direction = axis
	facing = axis
	dive_ticks = int(tuning[&"dive_duration_ticks"])
	dive_low_posture = true
	roll_ticks = 0
	roll_low_posture = false
	aiming = false
	sprint.cancel_gesture()
	invulnerability_ticks = maxi(invulnerability_ticks, int(tuning[&"dive_invulnerability_ticks"]))
	body.set_posture_height(float(tuning[&"dive_height"]))
	velocity = Vector2(float(dive_direction) * float(tuning[&"dive_speed"]), maxf(velocity.y, 0.0))
	queued_attack = &"dive"
	attack_name = &"dive"
	attack_cooldown_ticks = int(tuning.get(&"attack_cooldown_ticks", 8))
	action_name = &"dive"
	action_timer_ticks = dive_ticks
	_move_body(body)
	_update_locomotion(arena, tuning)

func _step_dive(arena: ArenaState, tuning: Dictionary, body: PhysicsFighter2D) -> void:
	dive_ticks = maxi(0, dive_ticks - 1)
	body.set_posture_height(float(tuning[&"dive_height"]))
	velocity.x = float(dive_direction) * float(tuning[&"dive_speed"])
	velocity.y = minf(velocity.y + float(tuning[&"gravity_per_tick"]), float(tuning[&"terminal_fall_speed"]))
	_move_body(body)
	action_name = &"dive" if dive_ticks > 0 else &"dive_recover"
	action_timer_ticks = dive_ticks
	_update_locomotion(arena, tuning)
	if locomotion == Locomotion.DOWNED:
		dive_ticks = 0
		dive_low_posture = false
		return
	if dive_ticks == 0:
		_maintain_dive_posture(body, tuning)

func _maintain_dive_posture(body: PhysicsFighter2D, tuning: Dictionary) -> void:
	if not dive_low_posture:
		return
	body.set_posture_height(float(tuning[&"dive_height"]))
	if body.can_stand():
		body.set_posture_height(float(tuning[&"char_height"]))
		dive_low_posture = false
		dive_direction = 0
		if dive_ticks == 0 and grounded:
			velocity = Vector2.ZERO

func _step_roll(arena: ArenaState, tuning: Dictionary, body: PhysicsFighter2D) -> void:
	roll_ticks = maxi(0, roll_ticks - 1)
	body.set_posture_height(float(tuning[&"roll_height"]))
	velocity.x = float(roll_direction) * float(tuning[&"roll_speed"])
	velocity.y = minf(velocity.y + float(tuning[&"gravity_per_tick"]), float(tuning[&"terminal_fall_speed"]))
	_move_body(body)
	in_pit = not grounded and arena.is_in_pit(position.x)
	locomotion = FighterState.Locomotion.GROUNDED if grounded else FighterState.Locomotion.FALLING
	action_name = &"roll" if roll_ticks > 0 else &"roll_recover"
	action_timer_ticks = roll_ticks
	_update_locomotion(arena, tuning)
	if locomotion == Locomotion.DOWNED:
		roll_ticks = 0
		roll_low_posture = false
		return
	if roll_ticks == 0:
		roll_recovery_ticks = int(tuning[&"roll_recovery_ticks"])
		_maintain_roll_posture(body, tuning)

func _maintain_roll_posture(body: PhysicsFighter2D, tuning: Dictionary) -> void:
	if not roll_low_posture:
		return
	body.set_posture_height(float(tuning[&"roll_height"]))
	if body.can_stand():
		body.set_posture_height(float(tuning[&"char_height"]))
		roll_low_posture = false
		roll_direction = 0
		if roll_ticks == 0 and roll_recovery_ticks > 0:
			velocity = Vector2.ZERO

func _update_locomotion(arena: ArenaState, tuning: Dictionary) -> void:
	in_pit = not grounded and arena.is_in_pit(position.x)
	locomotion = Locomotion.GROUNDED if grounded else Locomotion.FALLING if velocity.y >= 0.0 else Locomotion.AIRBORNE
	if position.y > arena.pit_death_y:
		down_tap_window_remaining = 0
		drop_through_ticks = 0
		sprint.cancel_gesture()
		health = 0
		queued_attack = &"none"
		attack_name = &"none"
		attack_timer_ticks = 0
		locomotion = Locomotion.DOWNED
		downed_ticks = int(tuning[&"respawn_delay_ticks"])
		action_name = &"pit_fall"
		action_timer_ticks = downed_ticks

func consume_attack() -> StringName:
	var result: StringName = queued_attack
	queued_attack = &"none"
	return result

func apply_hit(damage: int, knockback: float, knockdown: bool, hit_kind: StringName, tuning: Dictionary) -> bool:
	if health <= 0 or invulnerability_ticks > 0:
		return false
	last_damage = maxi(0, damage)
	last_hit_kind = hit_kind
	roll_ticks = 0
	roll_recovery_ticks = 0
	dive_ticks = 0
	dive_direction = 0
	tackle_ticks = 0
	tackle_low_posture = false
	hold_ticks = 0
	hold_target = 0
	queued_attack = &"none"
	health = maxi(0, health - maxi(0, damage))
	velocity.x = knockback
	hitstun_ticks = int(tuning[&"hitstun_duration_ticks"])
	if health == 0:
		roll_low_posture = false
		dive_low_posture = false
		locomotion = Locomotion.DOWNED
		downed_ticks = int(tuning.get(&"respawn_delay_ticks", 90))
		action_name = &"defeated"
		action_timer_ticks = downed_ticks
		return true
	if knockdown:
		knockdown_ticks = int(tuning[&"knockdown_duration_ticks"])
		invulnerability_ticks = int(tuning[&"knockdown_invulnerability_ticks"])
		action_name = &"knockdown"
	else:
		action_name = &"hit"
	return true

func begin_grab(attacker_player: int, duration_ticks: int) -> void:
	grabbed_by = attacker_player
	grabbed_ticks = maxi(grabbed_ticks, duration_ticks)
	hitstun_ticks = maxi(hitstun_ticks, duration_ticks)
	knockdown_ticks = 0
	# A successful tackle is a live hold window; its follow-up punch/throw must
	# be able to connect immediately rather than inherit knockdown immunity.
	invulnerability_ticks = 0
	action_name = &"grabbed"
	action_timer_ticks = grabbed_ticks

func begin_hold(target_player: int, duration_ticks: int) -> void:
	hold_target = target_player
	hold_ticks = maxi(hold_ticks, duration_ticks)
	action_name = &"grab"
	action_timer_ticks = hold_ticks

func apply_burn_damage(damage: int, tuning: Dictionary) -> bool:
	if health <= 0 or invulnerability_ticks > 0:
		return false
	last_damage = maxi(0, damage)
	last_hit_kind = &"burn"
	roll_ticks = 0
	roll_recovery_ticks = 0
	dive_ticks = 0
	dive_direction = 0
	queued_attack = &"none"
	health = maxi(0, health - maxi(0, damage))
	if health == 0:
		roll_low_posture = false
		dive_low_posture = false
		locomotion = Locomotion.DOWNED
		downed_ticks = int(tuning.get(&"respawn_delay_ticks", 90))
		action_name = &"defeated"
		action_timer_ticks = downed_ticks
	return true

func snapshot() -> Dictionary:
	var pending_snapshot: Dictionary = tempo_pending_actions.duplicate(true)
	for suffix: StringName in pending_snapshot.keys():
		var row: Dictionary = pending_snapshot[suffix]
		row.make_read_only()
	pending_snapshot.make_read_only()
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
		&"drop_through_ticks": drop_through_ticks,
		&"down_tap_window_remaining": down_tap_window_remaining,
		&"attack": attack_name,
		&"attack_timer_ticks": attack_timer_ticks,
		&"attack_cooldown_ticks": attack_cooldown_ticks,
		&"aiming": aiming,
		&"aim_angle": aim_angle,
		&"knockdown_ticks": knockdown_ticks,
		&"invulnerability_ticks": invulnerability_ticks,
		&"roll_ticks": roll_ticks,
		&"roll_recovery_ticks": roll_recovery_ticks,
		&"roll_direction": roll_direction,
		&"roll_low_posture": roll_low_posture,
		&"dive_ticks": dive_ticks,
		&"dive_direction": dive_direction,
		&"dive_low_posture": dive_low_posture,
		&"tackle_ticks": tackle_ticks,
		&"tackle_direction": tackle_direction,
		&"tackle_low_posture": tackle_low_posture,
		&"grabbed_ticks": grabbed_ticks,
		&"grabbed_by": grabbed_by,
		&"hold_ticks": hold_ticks,
		&"hold_target": hold_target,
		&"combo_step": combo_step,
		&"combo_window_ticks": combo_window_ticks,
		&"combo_buffered": combo_buffered,
		&"ammo": ammo,
		&"grenades": grenades,
		&"power_charges": power_charges,
		&"active_weapon_slot": active_weapon_slot,
		&"power_duration_ticks": power_duration_ticks,
		&"bullet_time_active": bullet_time_active,
		&"tempo_divisor": tempo_divisor,
		&"tempo_phase": tempo_phase,
		&"tempo_pending_actions": pending_snapshot,
		&"last_damage": last_damage,
		&"last_hit_kind": last_hit_kind,
		&"sprint": sprint.snapshot(),
	}
	result.make_read_only()
	return result

func canonical_fragment() -> String:
	var base: String = "fighter=%d,%.3f,%.3f,%.3f,%.3f,%d,%d,%d,%d,%d,%s,%d,%d,%d,%d,%d,%d,%s,%d,%d,%d,%d,%d,%d,%d,%s,%d,%.3f|%s" % [
		player_id,
		snappedf(position.x, 0.001),
		snappedf(position.y, 0.001),
		snappedf(velocity.x, 0.001),
		snappedf(velocity.y, 0.001),
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
		drop_through_ticks,
		down_tap_window_remaining,
		String(attack_name),
		attack_timer_ticks,
		attack_cooldown_ticks,
		knockdown_ticks,
		invulnerability_ticks,
		ammo,
		grenades,
		last_damage,
		String(last_hit_kind),
		int(aiming),
		snappedf(aim_angle, 0.001),
		sprint.canonical_fragment(),
	]
	var pending_parts: Array[String] = []
	for suffix: StringName in ACTION_SUFFIXES:
		var pending: Dictionary = tempo_pending_actions.get(suffix, {})
		if not pending.is_empty():
			pending_parts.append("%s,%d,%d,%d" % [String(suffix), int(bool(pending.get(&"pressed", false))), int(bool(pending.get(&"released", false))), int(pending.get(&"press_count", 0))])
	return "%s|slot=%d|power=%d,%d,%d,%d,%d|roll=%d,%d,%d,%d|dive=%d,%d,%d|tackle=%d,%d,%d|grab=%d,%d,%d,%d|combo=%d,%d,%d|pending=%s" % [base, active_weapon_slot, power_charges, power_duration_ticks, int(bullet_time_active), tempo_divisor, tempo_phase, roll_ticks, roll_recovery_ticks, roll_direction, int(roll_low_posture), dive_ticks, dive_direction, int(dive_low_posture), tackle_ticks, tackle_direction, int(tackle_low_posture), grabbed_ticks, grabbed_by, hold_ticks, hold_target, combo_step, combo_window_ticks, int(combo_buffered), ";".join(pending_parts)]

func _step_downed(arena: ArenaState, tuning: Dictionary) -> void:
	if downed_ticks > 0:
		downed_ticks -= 1
		velocity = Vector2.ZERO
		return
	var spawn: Vector2 = arena.spawn_for_player(player_id)
	reset_for_round(tuning)
	position = spawn
	action_name = &"respawn"
	action_timer_ticks = 1

func reset_for_round(tuning: Dictionary) -> void:
	health = int(tuning.get(&"max_health", 100))
	velocity = Vector2.ZERO
	facing = 1
	sprint.reset(tuning)
	ammo = 6
	grenades = int(tuning.get(&"grenade_count", 3))
	power_charges = 0
	power_duration_ticks = 300
	active_weapon_slot = 1
	bullet_time_active = false
	set_tempo_divisor(1)
	tempo_phase = 0
	tempo_pending_actions.clear()
	action_name = &"idle"
	action_timer_ticks = 0
	jump_lock_ticks = 0
	hitstun_ticks = 0
	downed_ticks = 0
	drop_through_ticks = 0
	down_tap_window_remaining = 0
	attack_name = &"none"
	attack_timer_ticks = 0
	attack_cooldown_ticks = 0
	queued_attack = &"none"
	aiming = false
	aim_angle = 0.0
	knockdown_ticks = 0
	invulnerability_ticks = 0
	roll_ticks = 0
	roll_recovery_ticks = 0
	roll_direction = 0
	roll_low_posture = false
	dive_ticks = 0
	dive_direction = 0
	dive_low_posture = false
	tackle_ticks = 0
	tackle_direction = 0
	tackle_low_posture = false
	grabbed_ticks = 0
	grabbed_by = 0
	hold_ticks = 0
	hold_target = 0
	combo_step = 0
	combo_window_ticks = 0
	combo_buffered = false
	grounded = true
	in_pit = false
	locomotion = Locomotion.GROUNDED
	last_damage = 0
	last_hit_kind = &"none"

func _apply_explicit_action(actions: Dictionary, tuning: Dictionary) -> void:
	if _pressed(actions, &"punch"):
		if attack_cooldown_ticks > 0:
			combo_buffered = true
		else:
			_start_melee_attack(actions, tuning)
	elif combo_buffered and attack_cooldown_ticks == 0:
		combo_buffered = false
		_start_melee_attack(actions, tuning)
	elif _released(actions, &"shoot") and not _held(actions, &"shoot") and attack_cooldown_ticks == 0:
		if ammo > 0:
			ammo -= 1
			attack_name = &"shoot"
			queued_attack = attack_name
			attack_timer_ticks = 3
			attack_cooldown_ticks = int(tuning.get(&"shoot_cooldown_ticks", 20))
			action_name = attack_name
	elif _pressed(actions, &"throw") and attack_cooldown_ticks == 0 and grenades > 0:
		grenades -= 1
		attack_name = &"throw"
		queued_attack = attack_name
		attack_timer_ticks = 8
		attack_cooldown_ticks = 8
		action_name = attack_name
	elif _pressed(actions, &"power") and (power_charges > 0 or bullet_time_active) and (attack_cooldown_ticks == 0 or bullet_time_active):
		attack_name = &"power"
		queued_attack = attack_name
		attack_timer_ticks = 3
		attack_cooldown_ticks = 8
		_update_action(actions, &"power", 10)
	elif action_timer_ticks == 0:
		action_name = &"sprint" if sprint.direction != 0 else &"idle"

func _start_melee_attack(actions: Dictionary, tuning: Dictionary) -> void:
	if not grounded:
		combo_step = 0
		combo_window_ticks = 0
		attack_name = &"jump_kick"
		queued_attack = attack_name
		attack_timer_ticks = 7
		attack_cooldown_ticks = 10
		action_name = attack_name
		return
	if _held(actions, &"down"):
		combo_step = 0
		combo_window_ticks = 0
		attack_name = &"kick"
		queued_attack = attack_name
		attack_timer_ticks = 7
		attack_cooldown_ticks = 10
		action_name = attack_name
		return
	combo_step = 1 if combo_step <= 0 or combo_window_ticks <= 0 else mini(combo_step + 1, 3)
	combo_window_ticks = int(tuning.get(&"combo_window_ticks", 18))
	attack_name = &"punch" if combo_step == 1 else &"punch_combo" if combo_step == 2 else &"kick"
	queued_attack = attack_name
	attack_timer_ticks = 6 if combo_step < 3 else 8
	attack_cooldown_ticks = 8 if combo_step < 3 else 10
	if combo_step == 3:
		combo_step = 0
		combo_window_ticks = 0
	action_name = attack_name

func _update_aim_state(actions: Dictionary) -> void:
	var shoot_held: bool = _held(actions, &"shoot")
	if shoot_held:
		aiming = true
		var elevation: float = float(int(_held(actions, &"up")) - int(_held(actions, &"down")))
		if not is_zero_approx(elevation):
			aim_angle = clampf(aim_angle - elevation * AIM_STEP_RADIANS, -MAX_AIM_ANGLE_RADIANS, MAX_AIM_ANGLE_RADIANS)
	else:
		aiming = false

func _update_action(_actions: Dictionary, name: StringName, duration_ticks: int) -> void:
	action_name = name
	action_timer_ticks = duration_ticks

func set_tempo_divisor(value: int) -> void:
	tempo_divisor = maxi(1, value)
	if tempo_divisor == 1:
		tempo_phase = 0

func _buffer_tempo_actions(actions: Dictionary) -> void:
	for suffix: StringName in ACTION_SUFFIXES:
		if not _pressed(actions, suffix) and not _released(actions, suffix):
			continue
		var pending: Dictionary = tempo_pending_actions.get(suffix, {&"pressed": false, &"released": false, &"press_count": 0})
		pending[&"pressed"] = bool(pending.get(&"pressed", false)) or _pressed(actions, suffix)
		pending[&"released"] = bool(pending.get(&"released", false)) or _released(actions, suffix)
		pending[&"press_count"] = int(pending.get(&"press_count", 0)) + int(actions.get(StringName("%s_press_count" % String(suffix)), 0))
		tempo_pending_actions[suffix] = pending

func _consume_tempo_actions(actions: Dictionary) -> Dictionary:
	if tempo_pending_actions.is_empty():
		return actions
	var merged: Dictionary = actions.duplicate(true)
	for suffix: StringName in ACTION_SUFFIXES:
		var pending: Dictionary = tempo_pending_actions.get(suffix, {})
		if pending.is_empty():
			continue
		var pressed_key := StringName("%s_pressed" % String(suffix))
		var released_key := StringName("%s_released" % String(suffix))
		var count_key := StringName("%s_press_count" % String(suffix))
		merged[pressed_key] = bool(merged.get(pressed_key, false)) or bool(pending.get(&"pressed", false))
		merged[released_key] = bool(merged.get(released_key, false)) or bool(pending.get(&"released", false))
		merged[count_key] = int(merged.get(count_key, 0)) + int(pending.get(&"press_count", 0))
	tempo_pending_actions.clear()
	return merged

func _held(actions: Dictionary, suffix: StringName) -> bool:
	return bool(actions.get(StringName("%s_held" % String(suffix)), false))

func _pressed(actions: Dictionary, suffix: StringName) -> bool:
	return bool(actions.get(StringName("%s_pressed" % String(suffix)), false))

func _released(actions: Dictionary, suffix: StringName) -> bool:
	return bool(actions.get(StringName("%s_released" % String(suffix)), false))

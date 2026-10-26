class_name Simulation
extends Node2D
## Fixed 60-Hz session: state intent -> Godot motion -> combat -> snapshot.
## Each session owns its physics nodes; presentation never moves these bodies.

const SIM_SCHEMA: StringName = &"sa05.simulation.v1"
const FIXED_HZ: int = 60
const TUNING_SCRIPT = preload("res://game/core/movement_tuning.gd")

var physics_arena: PhysicsArena2D
var bodies: Array[PhysicsFighter2D] = []
var _last_physics_frame: int = -1

var seed_value: int
var tick: int = 0
var round_timer_ticks: int = 0
var world: ArenaState
var fighters: Array[FighterState] = []
var tuning: Dictionary = {}
var last_input_tick: int = -1
var grenades: Array[Dictionary] = []

func _init(seed_input: int = 1, tuning_input: Dictionary = {}) -> void:
	seed_value = seed_input if seed_input > 0 else 1
	tuning = _default_tuning()
	if tuning.is_empty():
		return
	for key: Variant in tuning_input.keys():
		tuning[key] = tuning_input[key]
	tuning.make_read_only()
	world = ArenaState.new(seed_value)
	var first_fighter: FighterState = FighterState.new(1, world.spawn_for_player(1))
	var second_fighter: FighterState = FighterState.new(2, world.spawn_for_player(2))
	first_fighter.health = int(tuning.get(&"max_health", 100))
	second_fighter.health = int(tuning.get(&"max_health", 100))
	first_fighter.grenades = int(tuning.get(&"grenade_count", 3))
	second_fighter.grenades = int(tuning.get(&"grenade_count", 3))
	first_fighter.sprint.reset(tuning)
	second_fighter.sprint.reset(tuning)
	fighters.append(first_fighter)
	fighters.append(second_fighter)

func _ready() -> void:
	physics_arena = PhysicsArena2D.new()
	physics_arena.name = &"PhysicsArena"
	add_child(physics_arena)
	physics_arena.configure(world)
	for fighter: FighterState in fighters:
		var body := PhysicsFighter2D.new()
		body.name = StringName("Body%d" % fighter.player_id)
		add_child(body)
		body.configure(Vector2(float(tuning[&"char_width"]), float(tuning[&"char_height"])))
		body.sync_from_state(fighter.position, fighter.velocity)
		bodies.append(body)

## Explicit spawn/reset/fixture operation. Normal ticks never copy a state
## position into a body; the body is the only collision/movement authority.
func place_fighter(index: int, at: Vector2, motion: Vector2 = Vector2.ZERO, on_floor: bool = true) -> void:
	var fighter: FighterState = fighters[index]
	fighter.position = at
	fighter.velocity = motion
	fighter.grounded = on_floor
	fighter.in_pit = false
	fighter.locomotion = FighterState.Locomotion.GROUNDED if on_floor else FighterState.Locomotion.AIRBORNE
	fighter.roll_ticks = 0
	fighter.roll_recovery_ticks = 0
	fighter.roll_direction = 0
	fighter.roll_low_posture = false
	fighter.dive_ticks = 0
	fighter.dive_direction = 0
	fighter.dive_low_posture = false
	fighter.tackle_ticks = 0
	fighter.tackle_direction = 0
	fighter.tackle_low_posture = false
	fighter.grabbed_ticks = 0
	fighter.grabbed_by = 0
	fighter.hold_ticks = 0
	fighter.hold_target = 0
	fighter.combo_step = 0
	fighter.combo_window_ticks = 0
	fighter.combo_buffered = false
	fighter.action_name = &"idle"
	fighter.action_timer_ticks = 0
	fighter.jump_lock_ticks = 0
	fighter.hitstun_ticks = 0
	fighter.downed_ticks = 0
	fighter.drop_through_ticks = 0
	fighter.down_tap_window_remaining = 0
	fighter.attack_name = &"none"
	fighter.attack_timer_ticks = 0
	fighter.attack_cooldown_ticks = 0
	fighter.queued_attack = &"none"
	fighter.queued_combo_step = 0
	fighter.combo_step = 0
	fighter.combo_window_ticks = 0
	fighter.aiming = false
	fighter.aim_angle = 0.0
	fighter.knockdown_ticks = 0
	fighter.invulnerability_ticks = 0
	fighter.last_damage = 0
	fighter.last_hit_kind = &"none"
	fighter.sprint.reset(tuning)
	if bodies.size() > index:
		bodies[index].set_drop_through(false)
		bodies[index].set_solid_collision_enabled(true)
		bodies[index].set_posture_height(float(tuning[&"char_height"]))
		bodies[index].sync_from_state(at, motion)

func step(frame: InputFrame) -> bool:
	if not is_inside_tree() or bodies.size() != 2 or frame == null or frame.tick() != tick:
		return false
	if not Engine.is_in_physics_frame() or _last_physics_frame == Engine.get_physics_frames():
		return false
	_last_physics_frame = Engine.get_physics_frames()
	var frame_actions: Array[Dictionary] = []
	for fighter: FighterState in fighters:
		var actions: Dictionary = _actions_for(frame, fighter.player_id)
		frame_actions.append(actions)
	for index: int in range(fighters.size()):
		fighters[index].step(frame_actions[index], world, tuning, bodies[index])
	_resolve_attacks()
	_step_grenades()
	world.advance_tick()
	tick += 1
	round_timer_ticks += 1
	last_input_tick = frame.tick()
	return true

func snapshot() -> Dictionary:
	var fighter_rows: Array[Dictionary] = []
	for fighter: FighterState in fighters:
		fighter_rows.append(fighter.snapshot())
	var result: Dictionary = {
		&"schema": SIM_SCHEMA,
		&"fixed_hz": FIXED_HZ,
		&"quantum": 0.001,
		&"seed": seed_value,
		&"tick": tick,
		&"round_timer_ticks": round_timer_ticks,
		&"last_input_tick": last_input_tick,
		&"tuning": tuning,
		&"world": world.snapshot(),
		&"fighters": fighter_rows,
		&"grenades": grenades,
	}
	result.make_read_only()
	return result

func canonical_snapshot() -> String:
	var fragments: Array[String] = []
	fragments.append("schema=%s" % String(SIM_SCHEMA))
	fragments.append("hz=%d" % FIXED_HZ)
	fragments.append("quantum=0.001")
	fragments.append("seed=%d" % seed_value)
	fragments.append("tick=%d" % tick)
	fragments.append("round=%d" % round_timer_ticks)
	fragments.append("input=%d" % last_input_tick)
	fragments.append(_canonical_tuning())
	fragments.append(world.canonical_fragment())
	var grenade_parts: Array[String] = []
	for grenade: Dictionary in grenades:
		# Throwable identity and projectile gravity are gameplay state.  Include
		# them in replay hashes so a rocket/molotov cannot alias a grenade merely
		# because the three objects share the same position and fuse tick.
		grenade_parts.append("%d,%s,%.3f,%.3f,%.3f,%.3f,%d,%.3f,%d,%d" % [int(grenade.get(&"owner", 0)), String(grenade.get(&"kind", &"grenade")), float(grenade.get(&"x", 0.0)), float(grenade.get(&"y", 0.0)), float(grenade.get(&"vx", 0.0)), float(grenade.get(&"vy", 0.0)), int(grenade.get(&"fuse", 0)), float(grenade.get(&"gravity", 0.0)), int(bool(grenade.get(&"rocket", false))), int(grenade.get(&"age", 0))])
	fragments.append("grenades=%s" % ";".join(grenade_parts))
	for fighter: FighterState in fighters:
		fragments.append(fighter.canonical_fragment())
	return "|".join(fragments)

func _canonical_tuning() -> String:
	var keys: Array[StringName] = []
	for key: StringName in tuning.keys():
		keys.append(key)
	keys.sort_custom(func(a: StringName, b: StringName) -> bool: return String(a) < String(b))
	var parts: Array[String] = []
	for key: StringName in keys:
		parts.append("%s=%s" % [String(key), str(tuning[key])])
	return "tuning=%s" % ";".join(parts)

func snapshot_hash() -> String:
	var value: int = 2166136261
	for byte_value: int in canonical_snapshot().to_utf8_buffer():
		value = (value ^ byte_value) & 0xffffffff
		value = (value * 16777619) & 0xffffffff
	return "%08x" % value

func _actions_for(frame: InputFrame, player: int) -> Dictionary:
	var action_state: Dictionary = {}
	for suffix: StringName in FighterState.ACTION_SUFFIXES:
		action_state[StringName("%s_pressed" % String(suffix))] = false
		action_state[StringName("%s_held" % String(suffix))] = false
		action_state[StringName("%s_released" % String(suffix))] = false
		action_state[StringName("%s_press_count" % String(suffix))] = 0
	for record: Dictionary in frame.records():
		if int(record[&"player"]) != player:
			continue
		var action: StringName = StringName(record[&"action"])
		for suffix: StringName in FighterState.ACTION_SUFFIXES:
			if action != StringName("p%d_%s" % [player, String(suffix)]):
				continue
			var pressed_key: StringName = StringName("%s_pressed" % String(suffix))
			var held_key: StringName = StringName("%s_held" % String(suffix))
			var released_key: StringName = StringName("%s_released" % String(suffix))
			action_state[pressed_key] = bool(action_state[pressed_key]) or bool(record[&"pressed"])
			action_state[held_key] = bool(action_state[held_key]) or bool(record[&"held"])
			action_state[released_key] = bool(action_state[released_key]) or bool(record[&"released"])
			var ordered_events: Array = record[&"events"]
			action_state[StringName("%s_press_count" % String(suffix))] = ordered_events.count(InputFrame.EDGE_PRESSED)
			break
	action_state.make_read_only()
	return action_state

func _default_tuning() -> Dictionary:
	return TUNING_SCRIPT.load_default()

func _resolve_attacks() -> void:
	var queued: Array[StringName] = []
	for fighter: FighterState in fighters:
		queued.append(fighter.consume_attack())
	for index: int in range(fighters.size()):
		var attack: StringName = queued[index]
		if attack == &"none":
			continue
		var attacker: FighterState = fighters[index]
		var target_index: int = 1 - index
		var target: FighterState = fighters[target_index]
		if attacker.health <= 0 or attacker.in_pit:
			continue
		if attack == &"throw":
			grenades.append({&"owner": attacker.player_id, &"x": attacker.position.x, &"y": attacker.position.y - 24, &"vx": attacker.facing * float(tuning[&"grenade_throw_speed"]), &"vy": -6, &"fuse": int(tuning[&"grenade_fuse_ticks"])})
			continue
		var distance_x: float = target.position.x - attacker.position.x
		var same_direction: bool = distance_x * attacker.facing > 0
		var vertical_close: bool = absf(target.position.y - attacker.position.y) <= float(tuning[&"char_height"])
		var range_limit: float = float(tuning[&"punch_range"]) if attack == &"punch" or attack == &"jump_kick" else float(tuning[&"shoot_range"])
		if not same_direction or not vertical_close or absf(distance_x) > range_limit:
			continue
		var damage: int = int(tuning[&"jump_kick_damage"]) if attack == &"jump_kick" else int(tuning.get(&"dive_damage", tuning[&"punch_damage"])) if attack == &"dive" else int(tuning[&"punch_damage"]) if attack == &"punch" else int(tuning[&"shoot_damage"])
		var knockback: float = float(tuning[&"melee_knockback"]) * 1.25 if attack == &"dive" else float(tuning[&"melee_knockback"]) if attack == &"punch" or attack == &"jump_kick" else float(tuning[&"bullet_knockback"])
		var knockdown: bool = attack == &"jump_kick" or attack == &"dive" or (attack == &"shoot" and (world.rng_state % 4 == 0))
		target.apply_hit(damage, attacker.facing * knockback, knockdown, attack, tuning)

func _step_grenades() -> void:
	var remaining: Array[Dictionary] = []
	for grenade: Dictionary in grenades:
		grenade[&"x"] = float(grenade[&"x"]) + float(grenade[&"vx"])
		grenade[&"y"] = float(grenade[&"y"]) + float(grenade[&"vy"])
		grenade[&"vy"] = float(grenade[&"vy"]) + 1
		if float(grenade[&"y"]) >= world.floor_y:
			grenade[&"y"] = world.floor_y
			grenade[&"vy"] = 0
		grenade[&"fuse"] = int(grenade[&"fuse"]) - 1
		if int(grenade[&"fuse"]) > 0:
			remaining.append(grenade)
			continue
		var center_x: float = float(grenade[&"x"])
		var center_y: float = float(grenade[&"y"])
		for target: FighterState in fighters:
			var dx: float = target.position.x - center_x
			var dy: float = target.position.y - center_y
			var radius: float = float(tuning[&"grenade_radius"])
			if dx * dx + dy * dy <= radius * radius:
				var push: int = 20 if dx >= 0 else -20
				target.apply_hit(int(tuning[&"grenade_damage"]), push, true, &"grenade", tuning)
	grenades = remaining

class_name Simulation
extends RefCounted
## Deterministic SA-03 gameplay core: two fighters, integer state, fixed 60 Hz.
## Presentation and engine physics are intentionally outside this class.

const SIM_SCHEMA: StringName = &"sa03.simulation.v3"
const FIXED_HZ: int = 60
const TUNING_SCRIPT = preload("res://game/core/movement_tuning.gd")

var seed_value: int
var tick: int = 0
var round_timer_ticks: int = 0
var world: ArenaState
var fighters: Array[FighterState] = []
var tuning: Dictionary = {}
var last_input_tick: int = -1

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
	fighters.append(first_fighter)
	fighters.append(second_fighter)

func step(frame: InputFrame) -> bool:
	if fighters.size() != 2 or frame == null or frame.tick() != tick:
		return false
	var frame_actions: Array[Dictionary] = []
	for fighter: FighterState in fighters:
		var actions: Dictionary = _actions_for(frame, fighter.player_id)
		frame_actions.append(actions)
	for index: int in range(fighters.size()):
		fighters[index].step(frame_actions[index], world, tuning)
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
		&"quantum": 1,
		&"seed": seed_value,
		&"tick": tick,
		&"round_timer_ticks": round_timer_ticks,
		&"last_input_tick": last_input_tick,
		&"tuning": tuning,
		&"world": world.snapshot(),
		&"fighters": fighter_rows,
	}
	result.make_read_only()
	return result

func canonical_snapshot() -> String:
	var fragments: Array[String] = []
	fragments.append("schema=%s" % String(SIM_SCHEMA))
	fragments.append("hz=%d" % FIXED_HZ)
	fragments.append("quantum=1")
	fragments.append("seed=%d" % seed_value)
	fragments.append("tick=%d" % tick)
	fragments.append("round=%d" % round_timer_ticks)
	fragments.append("input=%d" % last_input_tick)
	fragments.append(_canonical_tuning())
	fragments.append(world.canonical_fragment())
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
	var action_state: Dictionary = {&"down_press_count": 0}
	for suffix: StringName in FighterState.ACTION_SUFFIXES:
		action_state[StringName("%s_pressed" % String(suffix))] = false
		action_state[StringName("%s_held" % String(suffix))] = false
		action_state[StringName("%s_released" % String(suffix))] = false
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
			if suffix == &"down":
				var down_events: Array = record[&"events"]
				action_state[&"down_press_count"] = down_events.count(InputFrame.EDGE_PRESSED)
			break
	action_state.make_read_only()
	return action_state

func _default_tuning() -> Dictionary:
	return TUNING_SCRIPT.load_default()

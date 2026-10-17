class_name BotController
extends RefCounted
## Deterministic, snapshot-only bot policy.
##
## The controller has no dependency on a live MatchSession.  It accepts either
## a MatchSession-like object exposing snapshot(), a snapshot dictionary, or a
## dictionary containing self/opponent fighter rows.  `desired_actions()`
## returns held InputFrame action intents; `build_frame()` derives immutable
## pressed/held/released records when the caller wants to feed the simulation
## directly.  Invalid state fails closed to idle intents (or a null frame).

const INPUT_FRAME_SCRIPT = preload("res://game/core/input_frame.gd")

const MELEE_RANGE: float = 58.0
const SHOOT_RANGE: float = 320.0
const THROW_MIN_RANGE: float = 110.0
const THROW_MAX_RANGE: float = 260.0
const PICKUP_RANGE: float = 30.0
const VERTICAL_LANE: float = 58.0
const LADDER_X_RANGE: float = 26.0
const JUMP_VERTICAL_RANGE: float = 64.0
const MAX_AMMO: int = 6
const SHOOT_REPLAN_TICKS: int = 18
const MELEE_REPLAN_TICKS: int = 10

var _seed: int
var _player: int
var _valid_controller: bool = true
var _previous: Dictionary[StringName, bool] = {}
var _last_tick: int = -1
var _decision_tick: int = -1
var _drop_tap_phase: int = 0
var _shoot_until_tick: int = -1
var _next_shoot_tick: int = 0

func _init(seed_input: int = 1, player_input: int = 2) -> void:
	_seed = seed_input
	_player = player_input
	if player_input < 1 or player_input > 2:
		_valid_controller = false
	_player = clampi(player_input, 1, 2)
	_reset_previous()

## Return a complete held-intent map for both players.  Only this controller's
## player actions may be true; the other player's actions are always false.
func desired_actions(snapshot_source: Variant) -> Dictionary:
	var idle: Dictionary[StringName, bool] = _idle_actions()
	if not _valid_controller:
		return idle
	var state: Dictionary = _normalise_snapshot(snapshot_source)
	if state.is_empty():
		return idle
	var decision_tick: int = int(state[&"tick"])
	if _decision_tick >= 0 and decision_tick < _decision_tick:
		reset()
	_decision_tick = decision_tick
	return _decide(state)

## Alias used by callers that describe the return value as input intents.
func action_intents(snapshot_source: Variant) -> Dictionary:
	return desired_actions(snapshot_source)

## Short aliases for integration code that calls a controller's decision step.
func decide(snapshot_source: Variant) -> Dictionary:
	return desired_actions(snapshot_source)

## Build a validated immutable InputFrame from the normalized snapshot.  A
## malformed snapshot returns null and leaves held-edge history unchanged.
func build_frame(snapshot_source: Variant) -> InputFrame:
	if not _valid_controller:
		return null
	var state: Dictionary = _normalise_snapshot(snapshot_source)
	if state.is_empty():
		return null
	var tick: int = int(state[&"tick"])
	if _last_tick >= 0 and tick != _last_tick + 1:
		# Duplicate or skipped ticks cannot produce a trustworthy edge stream.
		# A backwards tick is a caller-visible session restart; every other
		# discontinuity fails closed until the caller resets explicitly.
		if tick < _last_tick:
			reset()
		else:
			return null
	var desired: Dictionary = _decide(state)
	var records: Array[Dictionary] = []
	for action: StringName in INPUT_FRAME_SCRIPT.ACTIONS:
		var owner: int = 1 if String(action).begins_with("p1_") else 2
		var was_held: bool = bool(_previous.get(action, false))
		var wants_held: bool = bool(desired.get(action, false))
		var events: Array[StringName] = []
		if not was_held and wants_held:
			events.append(INPUT_FRAME_SCRIPT.EDGE_PRESSED)
		elif was_held and not wants_held:
			events.append(INPUT_FRAME_SCRIPT.EDGE_RELEASED)
		records.append({
			&"schema_version": INPUT_FRAME_SCRIPT.SCHEMA_VERSION,
			&"tick": tick,
			&"player": owner,
			&"action": action,
			&"initial_held": was_held,
			&"events": events,
			&"pressed": events.has(INPUT_FRAME_SCRIPT.EDGE_PRESSED),
			&"held": wants_held,
			&"released": events.has(INPUT_FRAME_SCRIPT.EDGE_RELEASED),
		})
	var frame: InputFrame = INPUT_FRAME_SCRIPT.create(tick, records)
	if frame == null:
		return null
	_previous = desired.duplicate(true)
	_last_tick = tick
	return frame

func input_frame(snapshot_source: Variant) -> InputFrame:
	return build_frame(snapshot_source)

## Reset edge history after a pause, restart, or input-owner change.
func reset() -> void:
	_reset_previous()
	_last_tick = -1
	_decision_tick = -1
	_drop_tap_phase = 0
	_shoot_until_tick = -1
	_next_shoot_tick = 0

func _reset_previous() -> void:
	_previous.clear()
	for action: StringName in INPUT_FRAME_SCRIPT.ACTIONS:
		_previous[action] = false

func _idle_actions() -> Dictionary:
	var result: Dictionary[StringName, bool] = {}
	for action: StringName in INPUT_FRAME_SCRIPT.ACTIONS:
		result[action] = false
	return result

func _normalise_snapshot(snapshot_source: Variant) -> Dictionary:
	var source: Variant = snapshot_source
	if source is Object:
		@warning_ignore("unsafe_cast")
		var source_object: Object = source as Object
		if not source_object.has_method("snapshot"):
			return {}
		source = source_object.call("snapshot")
	if typeof(source) != TYPE_DICTIONARY:
		return {}
	var root: Dictionary = Dictionary(source).duplicate(true)
	var tick_value: Variant = root.get(&"tick", null)
	if not _is_nonnegative_int(tick_value):
		return {}
	var phase_value: Variant = root.get(&"phase", &"playing")
	if not _is_name(phase_value):
		return {}
	var phase: StringName = _to_name(phase_value)
	if phase != &"playing":
		# Result/invalid sessions are valid snapshots, but have no controllable
		# intent. Keep the normalized state so desired_actions returns idle.
		root[&"phase"] = phase
	else:
		root[&"phase"] = phase

	var fighters_value: Variant = root.get(&"fighters", null)
	var fighter_rows: Array[Dictionary] = []
	if typeof(fighters_value) == TYPE_ARRAY:
		for value: Variant in Array(fighters_value):
			var row: Dictionary = _normalise_fighter(value)
			if row.is_empty():
				return {}
			fighter_rows.append(row)
	else:
		# Lightweight fixtures may provide explicit self/opponent rows instead
		# of MatchSession's fighters array.
		var self_value: Variant = root.get(&"self", null)
		var enemy_value: Variant = root.get(&"opponent", root.get(&"enemy", null))
		var self_row: Dictionary = _normalise_fighter(self_value)
		var enemy_row: Dictionary = _normalise_fighter(enemy_value)
		if self_row.is_empty() or enemy_row.is_empty():
			return {}
		fighter_rows.append(self_row)
		fighter_rows.append(enemy_row)
	if fighter_rows.size() != 2:
		return {}
	var fighter_ids: Dictionary = {}
	for row: Dictionary in fighter_rows:
		var row_id: int = int(row[&"player_id"])
		if fighter_ids.has(row_id):
			return {}
		fighter_ids[row_id] = true
	if not fighter_ids.has(1) or not fighter_ids.has(2):
		return {}
	var self_row_for_player: Dictionary = {}
	var enemy_row_for_player: Dictionary = {}
	for row: Dictionary in fighter_rows:
		if int(row[&"player_id"]) == _player:
			if not self_row_for_player.is_empty():
				return {}
			self_row_for_player = row
		elif enemy_row_for_player.is_empty():
			enemy_row_for_player = row
	if self_row_for_player.is_empty() or enemy_row_for_player.is_empty():
		return {}

	var world_value: Variant = root.get(&"world", {})
	if world_value == null:
		world_value = {}
	if typeof(world_value) != TYPE_DICTIONARY:
		return {}
	var world: Dictionary = Dictionary(world_value).duplicate(true)
	if not _validate_world(world):
		return {}
	var pickup_value: Variant = root.get(&"pickups", world.get(&"pickups", []))
	if typeof(pickup_value) != TYPE_ARRAY:
		return {}
	if not _validate_rows(Array(pickup_value), &"pickup"):
		return {}
	root[&"tick"] = int(tick_value)
	root[&"fighters"] = fighter_rows
	root[&"world"] = world
	root[&"pickups"] = Array(pickup_value)
	root[&"_controller_self"] = self_row_for_player
	root[&"_controller_enemy"] = enemy_row_for_player
	return root

func _normalise_fighter(value: Variant) -> Dictionary:
	var source: Variant = value
	if source is Object:
		@warning_ignore("unsafe_cast")
		var source_object: Object = source as Object
		if not source_object.has_method("snapshot"):
			return {}
		source = source_object.call("snapshot")
	if typeof(source) != TYPE_DICTIONARY:
		return {}
	var row: Dictionary = Dictionary(source).duplicate(true)
	if not _is_int(row.get(&"player_id", null)):
		return {}
	var player_id: int = int(row[&"player_id"])
	if player_id < 1 or player_id > 2:
		return {}
	if not _is_number(row.get(&"x", null)) or not _is_number(row.get(&"y", null)):
		return {}
	if not _is_nonnegative_int(row.get(&"health", null)):
		return {}
	for key: StringName in [&"grounded", &"in_pit", &"aiming", &"bullet_time_active"]:
		if row.has(key) and typeof(row[key]) != TYPE_BOOL:
			return {}
	for key: StringName in [&"ammo", &"grenades", &"attack_cooldown_ticks", &"jump_lock_ticks", &"hitstun_ticks"]:
		if row.has(key) and not _is_nonnegative_int(row[key]):
			return {}
	if row.has(&"gun_id") and not _is_name(row[&"gun_id"]):
		return {}
	row[&"gun_id"] = _to_name(row.get(&"gun_id", &""))
	if not [&"", &"none", &"pistol", &"shotgun", &"rifle", &"rocket_launcher"].has(row[&"gun_id"]):
		return {}
	row[&"grounded"] = bool(row.get(&"grounded", true))
	row[&"in_pit"] = bool(row.get(&"in_pit", false))
	row[&"ammo"] = int(row.get(&"ammo", 0))
	row[&"grenades"] = int(row.get(&"grenades", 0))
	row[&"health"] = int(row[&"health"])
	row[&"attack_cooldown_ticks"] = int(row.get(&"attack_cooldown_ticks", 0))
	return row

func _validate_world(world: Dictionary) -> bool:
	for key: StringName in [&"ladders", &"pits", &"solids"]:
		if not world.has(key):
			continue
		if typeof(world[key]) != TYPE_ARRAY:
			return false
		if not _validate_rows(Array(world[key]), key):
			return false
	return true

func _validate_rows(rows: Array, kind: StringName) -> bool:
	for value: Variant in rows:
		if typeof(value) != TYPE_DICTIONARY:
			return false
		var row: Dictionary = value
		if row.has(&"active") and typeof(row[&"active"]) != TYPE_BOOL:
			return false
		if kind == &"pickup":
			if not _is_name(row.get(&"kind", null)) or not _is_number(row.get(&"x", null)) or not _is_number(row.get(&"y", null)):
				return false
		elif kind == &"ladders":
			if not _is_number(row.get(&"x", null)) or not _is_number(row.get(&"top", null)) or not _is_number(row.get(&"bottom", null)):
				return false
		elif kind == &"pits":
			if not _is_number(row.get(&"left", null)) or not _is_number(row.get(&"right", null)):
				return false
		elif kind == &"solids":
			for key: StringName in [&"left", &"right", &"top", &"bottom"]:
				if not _is_number(row.get(key, null)):
					return false
	return true

func _decide(state: Dictionary) -> Dictionary:
	var result: Dictionary[StringName, bool] = _idle_actions()
	if StringName(state.get(&"phase", &"playing")) != &"playing":
		return result
	var self_row: Dictionary = state[&"_controller_self"]
	var enemy_row: Dictionary = state[&"_controller_enemy"]
	if int(self_row.get(&"health", 0)) <= 0 or bool(self_row.get(&"in_pit", false)):
		return result
	if int(enemy_row.get(&"health", 0)) <= 0:
		return result
	var tick: int = int(state[&"tick"])
	var prefix: String = "p%d_" % _player
	var self_x: float = float(self_row[&"x"])
	var self_y: float = float(self_row[&"y"])
	var enemy_x: float = float(enemy_row[&"x"])
	var enemy_y: float = float(enemy_row[&"y"])
	var dx: float = enemy_x - self_x
	var dy: float = enemy_y - self_y
	var world: Dictionary = state[&"world"]
	var cooldown: int = int(self_row.get(&"attack_cooldown_ticks", 0))
	var vertical_match: bool = absf(dy) <= VERTICAL_LANE
	var distance: float = absf(dx)
	var ammo: int = int(self_row.get(&"ammo", 0))
	var grenades: int = int(self_row.get(&"grenades", 0))
	var gun_id: StringName = StringName(self_row.get(&"gun_id", &""))
	var enemy_in_combat_range: bool = vertical_match and (distance <= MELEE_RANGE or (distance <= SHOOT_RANGE and ammo > 0 and gun_id != &""))

	# Once an enemy is in the current lane and weapon range, finish the
	# engagement before diverting to a pickup. This prevents a wounded bot from
	# abandoning a live fight for a cross-map item.
	var pickup: Dictionary = {} if enemy_in_combat_range else _best_pickup(Array(state[&"pickups"]), self_row, tick)
	if not pickup.is_empty():
		var pickup_dx: float = float(pickup[&"x"]) - self_x
		var pickup_dy: float = float(pickup[&"y"]) - self_y
		if absf(pickup_dx) <= PICKUP_RANGE and absf(pickup_dy) <= JUMP_VERTICAL_RANGE:
			result[StringName(prefix + "down")] = true
			# The range is inside MatchSession's 32px collection radius, so this
			# edge is consumed on the first interaction frame.
			result[StringName(prefix + "punch")] = true
			return result
		_set_horizontal(result, prefix, pickup_dx)
		_drive_vertical(result, prefix, self_row, pickup[&"y"], world)
		return _avoid_obstacles(_avoid_danger(result, prefix, self_row, self_x, world), prefix, self_row, self_x, world)

	if vertical_match and distance <= MELEE_RANGE and cooldown == 0:
		# FighterState queues melee from a pressed edge.  Pulse the intent so a
		# controller cannot get stuck holding one punch after its first attack.
		if tick % MELEE_REPLAN_TICKS == 0:
			result[StringName(prefix + "punch")] = true
		return result

	var can_shoot: bool = vertical_match and distance <= SHOOT_RANGE and ammo > 0 and gun_id != &"" and cooldown == 0
	var can_throw: bool = vertical_match and distance >= THROW_MIN_RANGE and distance <= THROW_MAX_RANGE and grenades > 0 and cooldown == 0
	if can_shoot and can_throw:
		if _choice_index(tick, 2, 41) == 0:
			can_throw = false
		else:
			can_shoot = false
	if can_shoot:
		# A two-tick hold gives the simulation a release edge on the following
		# decision, matching the InputFrame contract for firing.
		if _shoot_until_tick < tick and tick >= _next_shoot_tick:
			_shoot_until_tick = tick + 1
			_next_shoot_tick = tick + SHOOT_REPLAN_TICKS
		if tick <= _shoot_until_tick:
			result[StringName(prefix + "shoot")] = true
			if distance > MELEE_RANGE:
				_set_horizontal(result, prefix, dx)
			return _avoid_obstacles(_avoid_danger(result, prefix, self_row, self_x, world), prefix, self_row, self_x, world)
	if can_throw:
		result[StringName(prefix + "throw")] = true
		return result

	_set_horizontal(result, prefix, dx)
	_drive_vertical(result, prefix, self_row, enemy_y, world)
	return _avoid_obstacles(_avoid_danger(result, prefix, self_row, self_x, world), prefix, self_row, self_x, world)

func _best_pickup(rows: Array, self_row: Dictionary, tick: int) -> Dictionary:
	var best: Dictionary = {}
	var best_distance: float = INF
	var self_x: float = float(self_row[&"x"])
	var self_y: float = float(self_row[&"y"])
	var health: int = int(self_row[&"health"])
	var ammo: int = int(self_row.get(&"ammo", 0))
	var grenades: int = int(self_row.get(&"grenades", 0))
	var gun_id: StringName = StringName(self_row.get(&"gun_id", &""))
	for value: Variant in rows:
		var row: Dictionary = value
		if row.has(&"active") and not bool(row[&"active"]):
			continue
		var kind: StringName = _to_name(row[&"kind"])
		var useful: bool = false
		if kind == &"medkit" or kind == &"health":
			useful = health < 80
		elif kind == &"pill":
			# The relay-yard center pill is above a gap with no direct ladder
			# landing.  A bot must fail closed on that unreachable target rather
			# than oscillating forever between the two ladder feet.
			useful = false
		elif kind == &"ammo":
			useful = ammo < MAX_AMMO
		elif kind == &"grenades" or kind == &"grenade":
			useful = grenades < 3
		elif kind == &"pistol" or kind == &"shotgun" or kind == &"rifle":
			# A full alternate gun is not a useful waypoint. Only seek a firearm
			# when unarmed or nearly out of ammunition.
			useful = gun_id == &"" or ammo <= 1
		if not useful:
			continue
		var distance: float = absf(float(row[&"x"]) - self_x) + absf(float(row[&"y"]) - self_y) * 0.5
		if distance < best_distance - 0.001:
			best_distance = distance
			best = row
		elif is_equal_approx(distance, best_distance) and _choice_index(tick, 2, 73) == 1:
			best = row
	return best

func _drive_vertical(result: Dictionary, prefix: String, self_row: Dictionary, target_y: Variant, world: Dictionary) -> void:
	if not _is_number(target_y):
		return
	var self_x: float = float(self_row[&"x"])
	var self_y: float = float(self_row[&"y"])
	var dy: float = float(target_y) - self_y
	if absf(dy) <= VERTICAL_LANE:
		_drop_tap_phase = 0
		return
	if dy > VERTICAL_LANE and bool(self_row.get(&"grounded", true)) and _on_one_way(world, self_x, self_y):
		# Down twice is the only authored drop-through gesture. Emit a real
		# release tick between the two presses so InputFrame validates it.
		if _drop_tap_phase == 0:
			result[StringName(prefix + "down")] = true
			_drop_tap_phase = 1
		elif _drop_tap_phase == 1:
			_drop_tap_phase = 2
		elif _drop_tap_phase == 2:
			result[StringName(prefix + "down")] = true
			_drop_tap_phase = 3
		else:
			_drop_tap_phase = 0
		return
	var ladder: Dictionary = _nearest_ladder(Array(world.get(&"ladders", [])), self_x, self_y, float(target_y))
	if not ladder.is_empty():
		var ladder_dx: float = float(ladder[&"x"]) - self_x
		if absf(ladder_dx) > LADDER_X_RANGE:
			_set_horizontal(result, prefix, ladder_dx)
		else:
			var locomotion_value: Variant = self_row.get(&"locomotion", &"")
			# FighterState snapshots intentionally use the stable enum integer;
			# accept the readable fixture spelling as well.
			var climbing: bool = (typeof(locomotion_value) == TYPE_INT and int(locomotion_value) == 2) or (_is_name(locomotion_value) and _to_name(locomotion_value) == &"climbing")
			if bool(self_row.get(&"grounded", true)) or climbing:
				result[StringName(prefix + ("down" if dy > 0.0 else "up"))] = true
		return
	if bool(self_row.get(&"grounded", true)):
		result[StringName(prefix + "up")] = true

func _on_one_way(world: Dictionary, x: float, y: float) -> bool:
	for value: Variant in Array(world.get(&"platforms", [])):
		var platform: Dictionary = value
		if not bool(platform.get(&"one_way", false)):
			continue
		if x >= float(platform.get(&"left", 0.0)) and x <= float(platform.get(&"right", 0.0)) and absf(y - float(platform.get(&"y", 0.0))) <= 3.0:
			return true
	return false

func _nearest_ladder(rows: Array, x: float, y: float, target_y: float) -> Dictionary:
	var best: Dictionary = {}
	var best_distance: float = INF
	for value: Variant in rows:
		var row: Dictionary = value
		var ladder_x: float = float(row[&"x"])
		var top: float = float(row[&"top"])
		var bottom: float = float(row[&"bottom"])
		if y < top - JUMP_VERTICAL_RANGE or y > bottom + JUMP_VERTICAL_RANGE:
			continue
		if target_y < top - JUMP_VERTICAL_RANGE or target_y > bottom + JUMP_VERTICAL_RANGE:
			continue
		var distance: float = absf(ladder_x - x)
		if distance < best_distance:
			best_distance = distance
			best = row
	return best

func _set_horizontal(result: Dictionary, prefix: String, dx: float) -> void:
	# Replanning can switch from target pursuit to a ladder/waypoint in the
	# same decision. Clear the old direction so contradictory left+right input
	# cannot cancel movement in the live frame.
	result[StringName(prefix + "left")] = false
	result[StringName(prefix + "right")] = false
	if dx < -8.0:
		result[StringName(prefix + "left")] = true
	elif dx > 8.0:
		result[StringName(prefix + "right")] = true

func _avoid_danger(result: Dictionary, prefix: String, self_row: Dictionary, x: float, world: Dictionary) -> Dictionary:
	var direction: float = 1.0 if bool(result.get(StringName(prefix + "right"), false)) else -1.0 if bool(result.get(StringName(prefix + "left"), false)) else 0.0
	if is_zero_approx(direction):
		return result
	var probe: float = x + direction * 42.0
	for value: Variant in Array(world.get(&"pits", [])):
		var pit: Dictionary = value
		if probe > float(pit[&"left"]) and probe < float(pit[&"right"]):
			if bool(self_row.get(&"grounded", true)):
				result[StringName(prefix + "up")] = true
			else:
				result[StringName(prefix + "left")] = false
				result[StringName(prefix + "right")] = false
			return result
	return result

func _avoid_obstacles(result: Dictionary, prefix: String, self_row: Dictionary, x: float, world: Dictionary) -> Dictionary:
	if not bool(self_row.get(&"grounded", true)):
		return result
	var direction: float = 1.0 if bool(result.get(StringName(prefix + "right"), false)) else -1.0 if bool(result.get(StringName(prefix + "left"), false)) else 0.0
	if is_zero_approx(direction):
		return result
	var self_y: float = float(self_row.get(&"y", 0.0))
	var probe: float = x + direction * 36.0
	for value: Variant in Array(world.get(&"solids", [])):
		var solid: Dictionary = value
		var left: float = float(solid.get(&"left", 0.0))
		var right: float = float(solid.get(&"right", 0.0))
		var top: float = float(solid.get(&"top", 0.0))
		var bottom: float = float(solid.get(&"bottom", 0.0))
		if probe >= left - 18.0 and probe <= right + 18.0 and self_y >= top - 70.0 and self_y <= bottom + 12.0:
			# A jump is the semantic escape from a shallow cover block. Keep the
			# horizontal intent so the body clears the obstacle instead of idling.
			result[StringName(prefix + "up")] = true
			return result
	return result

func _choice_index(tick: int, count: int, salt: int) -> int:
	if count <= 1:
		return 0
	var mixed: int = _seed
	mixed = int((mixed ^ (tick * 1103515245) ^ (salt * 2654435761)) & 0x7fffffff)
	mixed = int((mixed * 1664525 + 1013904223) & 0x7fffffff)
	return posmod(mixed, count)

func _is_int(value: Variant) -> bool:
	return typeof(value) == TYPE_INT

func _is_nonnegative_int(value: Variant) -> bool:
	return _is_int(value) and int(value) >= 0

func _is_number(value: Variant) -> bool:
	if typeof(value) != TYPE_INT and typeof(value) != TYPE_FLOAT:
		return false
	return is_finite(float(value))

func _is_name(value: Variant) -> bool:
	return typeof(value) == TYPE_STRING or typeof(value) == TYPE_STRING_NAME

func _to_name(value: Variant) -> StringName:
	if typeof(value) == TYPE_STRING_NAME:
		return StringName(value)
	return StringName(String(value))


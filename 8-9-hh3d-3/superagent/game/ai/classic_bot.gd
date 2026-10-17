class_name ClassicBot
extends RefCounted
## Small deterministic intent policy for the SA5 match session.
##
## This is a provisional bot policy.  It emits held action state only; the
## match input assembler owns edge generation and InputFrame construction.
## No reference-game behavior or assets are used here.

const ACTION_SUFFIXES: Array[StringName] = [
	&"left", &"right", &"up", &"down", &"punch", &"shoot", &"throw",
]
const NAVIGATION_SCRIPT = preload("res://game/ai/navigation_graph.gd")
const MELEE_RANGE: float = 58.0
const SHOOT_RANGE: float = 300.0
const PICKUP_RANGE: float = 34.0
const REPLAN_TICKS: int = 6
const JUMP_COOLDOWN_TICKS: int = 24
const PUNCH_COOLDOWN_TICKS: int = 9
const SHOOT_COOLDOWN_TICKS: int = 18
const THROW_COOLDOWN_TICKS: int = 54

var _next_punch_tick: int = 0
var _next_shoot_tick: int = 0
var _next_throw_tick: int = 0
var _next_jump_tick: int = 0
var _shoot_until_tick: int = -1
var _last_tick: int = -1
var _last_x: float = 0.0
var _stuck_ticks: int = 0
var difficulty: StringName = &"normal"
var _profile: Dictionary = {}
var _navigation_graph: NavigationGraph
var _navigation_fingerprint: String = ""

func _init(difficulty_input: StringName = &"normal") -> void:
	difficulty = difficulty_input if difficulty_input in [&"easy", &"normal", &"hard"] else &"normal"
	_profile = {
		&"replan_ticks": 10 if difficulty == &"easy" else 6 if difficulty == &"normal" else 4,
		&"jump_cooldown_ticks": 36 if difficulty == &"easy" else 24 if difficulty == &"normal" else 14,
		&"punch_cooldown_ticks": 12 if difficulty == &"easy" else 9 if difficulty == &"normal" else 6,
		&"shoot_cooldown_ticks": 26 if difficulty == &"easy" else 18 if difficulty == &"normal" else 12,
		&"throw_cooldown_ticks": 90 if difficulty == &"easy" else 54 if difficulty == &"normal" else 36,
		&"pickup_range": 26.0 if difficulty == &"easy" else 34.0 if difficulty == &"normal" else 42.0,
	}
	_profile.make_read_only()

func difficulty_profile() -> Dictionary:
	return _profile

func navigation_ready() -> bool:
	return _navigation_graph != null and _navigation_graph.valid

## Return desired held actions.  The dictionary has no pressed/released fields;
## the caller compares consecutive results and builds immutable input records.
func desired_actions(snapshot: Dictionary, player: int = 2) -> Dictionary:
	player = clampi(player, 1, 2)
	var tick: int = int(snapshot.get(&"tick", _last_tick + 1))
	if tick < _last_tick:
		# A restarted match gets a fresh deterministic policy state.
		_reset_policy()
	_last_tick = tick
	var prefix: String = "p%d_" % player
	var result: Dictionary = {}
	for suffix: StringName in ACTION_SUFFIXES:
		result[StringName(prefix + String(suffix))] = false

	var fighters: Array = snapshot.get(&"fighters", [])
	var self_row: Dictionary = _fighter_for_player(fighters, player)
	if self_row.is_empty() or int(self_row.get(&"health", 0)) <= 0:
		return result
	var enemy: Dictionary = _fighter_for_other(fighters, player)
	if enemy.is_empty():
		return result

	var self_x: float = float(self_row.get(&"x", 0.0))
	var self_y: float = float(self_row.get(&"y", 0.0))
	var enemy_x: float = float(enemy.get(&"x", self_x))
	var enemy_y: float = float(enemy.get(&"y", self_y))
	var dx: float = enemy_x - self_x
	var dy: float = enemy_y - self_y
	var grounded: bool = bool(self_row.get(&"grounded", true))
	var ammo: int = int(self_row.get(&"ammo", 0))
	var gun_id: String = String(self_row.get(&"gun_id", ""))
	var health: int = int(self_row.get(&"health", 100))
	var grenades: int = int(self_row.get(&"grenades", self_row.get(&"grenade_count", 0)))

	# Keep a cheap progress sensor so a blocked edge/cover does not make the bot
	# hold one direction forever.  All decisions remain tick and snapshot based.
	if _last_tick >= 0 and absf(self_x - _last_x) < 0.5:
		_stuck_ticks += 1
	else:
		_stuck_ticks = 0
	_last_x = self_x

	var world_value: Variant = snapshot.get(&"world", snapshot)
	if typeof(world_value) != TYPE_DICTIONARY:
		# Malformed world snapshots fail closed after returning the stable action
		# schema; callers can still assemble a release frame without a crash.
		return _finish(result)
	var world: Dictionary = Dictionary(world_value)
	_ensure_navigation_graph(world)
	var pickups: Array = snapshot.get(&"pickups", world.get(&"pickups", []))
	var pickup: Dictionary = _best_pickup(pickups, self_x, self_y, health, ammo, gun_id)
	var pickup_needed: bool = not pickup.is_empty()
	var pickup_x: float = float(pickup.get(&"x", self_x))
	var pickup_y: float = float(pickup.get(&"y", self_y))

	# Use a nearby useful pickup before seeking combat.  Down + a one-tick punch
	# is the semantic interaction; the input assembler creates both edges.
	if pickup_needed:
		var pickup_dx: float = pickup_x - self_x
		var pickup_dy: float = pickup_y - self_y
		if absf(pickup_dx) <= float(_profile[&"pickup_range"]) and absf(pickup_dy) <= 64.0:
			result[StringName(prefix + "down")] = true
			result[StringName(prefix + "punch")] = _pulse_punch(tick)
			return _finish(result)
		_set_horizontal(result, prefix, pickup_dx)
		if absf(pickup_dy) > 70.0 and grounded:
			_maybe_jump(result, prefix, tick)
		return _finish_with_navigation(result, prefix, tick, self_row, self_x, world)

	var attack_cooldown: int = int(self_row.get(&"attack_cooldown_ticks", 0))
	var vertical_match: bool = absf(dy) <= 64.0
	if vertical_match and absf(dx) <= MELEE_RANGE and attack_cooldown <= 0:
		result[StringName(prefix + "punch")] = _pulse_punch(tick)
		return _finish(result)

	# A short shoot hold models aim, release, and the shot edge.  The fighter
	# consumes the press edge while the held tail gives the UI an aim interval.
	if gun_id != "" and ammo > 0 and vertical_match and absf(dx) <= SHOOT_RANGE:
		if tick >= _next_shoot_tick and attack_cooldown <= 0:
			_shoot_until_tick = tick + 2
			_next_shoot_tick = tick + int(_profile[&"shoot_cooldown_ticks"])
		if tick <= _shoot_until_tick:
			result[StringName(prefix + "shoot")] = true
			if absf(dx) > MELEE_RANGE:
				_set_horizontal(result, prefix, dx)
			return _finish(result)

	# Throws are deliberately infrequent and reserved for a mid-range lane.
	if grenades > 0 and vertical_match and absf(dx) >= 120.0 and absf(dx) <= 240.0 and tick >= _next_throw_tick and attack_cooldown <= 0:
		_next_throw_tick = tick + int(_profile[&"throw_cooldown_ticks"])
		result[StringName(prefix + "throw")] = true
		return _finish(result)

	_set_horizontal(result, prefix, dx)
	if absf(dy) > 70.0 and grounded:
		_maybe_jump(result, prefix, tick)
	return _finish_with_navigation(result, prefix, tick, self_row, self_x, world)

func _finish(result: Dictionary) -> Dictionary:
	# Each call starts with a fresh all-false action dictionary, so held state
	# naturally releases when the shoot window expires.
	return result

func _finish_with_navigation(result: Dictionary, prefix: String, tick: int, self_row: Dictionary, self_x: float, world: Dictionary) -> Dictionary:
	var graph_requires_replan: bool = _graph_requires_replan(self_x, float(self_row.get(&"y", 0.0)), result, prefix)
	if graph_requires_replan or _is_danger_ahead(self_x, result, prefix, world):
		if bool(self_row.get(&"grounded", true)):
			_maybe_jump(result, prefix, tick)
		else:
			# Brake while airborne over a hazard; this avoids steering deeper into
			# the pit until the next floor contact is observed.
			result[StringName(prefix + "left")] = false
			result[StringName(prefix + "right")] = false
	if _stuck_ticks >= int(_profile[&"replan_ticks"]) and bool(self_row.get(&"grounded", true)):
		_maybe_jump(result, prefix, tick)
		if _stuck_ticks >= int(_profile[&"replan_ticks"]) * 2:
			var left_key: StringName = StringName(prefix + "left")
			var right_key: StringName = StringName(prefix + "right")
			result[left_key] = not bool(result[left_key])
			result[right_key] = not bool(result[right_key])
	return _finish(result)

func _ensure_navigation_graph(world: Dictionary) -> void:
	var fingerprint: String = String(world.get(&"canonical_topology", ""))
	if fingerprint.is_empty():
		# Lightweight fixtures often omit the runtime canonical topology.  Do not
		# cache a constant sentinel here: the same bot may receive a changed test
		# world on the next tick.  Live MatchSession snapshots always carry the
		# canonical fingerprint and keep the normal incremental path.
		_navigation_graph = NAVIGATION_SCRIPT.new()
		_navigation_graph.build_from_snapshot(world)
		_navigation_fingerprint = ""
		return
	if fingerprint == _navigation_fingerprint:
		return
	_navigation_graph = NAVIGATION_SCRIPT.new()
	_navigation_graph.build_from_snapshot(world)
	_navigation_fingerprint = fingerprint

func _graph_requires_replan(x: float, y: float, result: Dictionary, prefix: String) -> bool:
	if not navigation_ready():
		return false
	var direction: float = 1.0 if bool(result.get(StringName(prefix + "right"), false)) else -1.0 if bool(result.get(StringName(prefix + "left"), false)) else 0.0
	if is_zero_approx(direction):
		return false
	var current_id: StringName = _platform_at(x, y)
	var target_id: StringName = _platform_at(x + direction * 42.0, y)
	if current_id == &"" or target_id == &"" or current_id == target_id:
		return false
	return not _navigation_graph.reachable(current_id, target_id)

func _platform_at(x: float, y: float) -> StringName:
	for node: Dictionary in _navigation_graph.nodes:
		if StringName(node.get(&"kind", &"")) != &"platform":
			continue
		if absf(float(node.get(&"y", 0.0)) - y) <= 2.0 and x >= float(node.get(&"left", -INF)) and x <= float(node.get(&"right", INF)):
			return StringName(node[&"id"])
	return &""

func _set_horizontal(result: Dictionary, prefix: String, distance_x: float) -> void:
	if distance_x < -10.0:
		result[StringName(prefix + "left")] = true
	elif distance_x > 10.0:
		result[StringName(prefix + "right")] = true

func _maybe_jump(result: Dictionary, prefix: String, tick: int) -> void:
	if tick < _next_jump_tick:
		return
	_next_jump_tick = tick + int(_profile[&"jump_cooldown_ticks"])
	result[StringName(prefix + "up")] = true

func _pulse_punch(tick: int) -> bool:
	if tick < _next_punch_tick:
		return false
	_next_punch_tick = tick + int(_profile[&"punch_cooldown_ticks"])
	return true

func _best_pickup(rows: Array, x: float, y: float, health: int, ammo: int, gun_id: String) -> Dictionary:
	var best: Dictionary = {}
	var best_distance: float = INF
	for value: Variant in rows:
		if typeof(value) != TYPE_DICTIONARY:
			continue
		var row: Dictionary = value
		if row.has(&"active") and not bool(row[&"active"]):
			continue
		var kind: String = String(row.get(&"kind", ""))
		# A sidearm does not suppress a nearby shotgun pickup: weapon swaps are
		# part of the match path, while an already-full same-gun pickup is ignored.
		var useful: bool = (kind == "pistol" or kind == "shotgun") and (gun_id == "" or ammo <= 1 or (kind != gun_id and gun_id == "pistol"))
		useful = useful or (kind == "medkit" and health < 65)
		useful = useful or (kind == "pill" and health < 85)
		useful = useful or (kind == "grenades" and health >= 50)
		if not useful:
			continue
		var distance: float = absf(float(row.get(&"x", x)) - x) + absf(float(row.get(&"y", y)) - y) * 0.5
		if distance < best_distance:
			best_distance = distance
			best = row
	return best

func _is_danger_ahead(x: float, result: Dictionary, prefix: String, world: Dictionary) -> bool:
	var direction: float = 1.0 if bool(result.get(StringName(prefix + "right"), false)) else -1.0 if bool(result.get(StringName(prefix + "left"), false)) else 0.0
	if is_zero_approx(direction):
		return false
	var probe: float = x + direction * 42.0
	for value: Variant in world.get(&"pits", []):
		if typeof(value) != TYPE_DICTIONARY:
			continue
		var pit: Dictionary = value
		var left: float = float(pit.get(&"left", -INF))
		var right: float = float(pit.get(&"right", INF))
		if probe > left and probe < right:
			return true
	# Treat low authored cover and walls as a jump/replan cue when the fighter
	# is walking at their base.  The snapshot may omit `solids` in lightweight
	# unit fixtures, so this remains an optional sensor.
	for value: Variant in world.get(&"solids", []):
		if typeof(value) != TYPE_DICTIONARY:
			continue
		var solid: Dictionary = value
		var left: float = float(solid.get(&"left", -INF))
		var right: float = float(solid.get(&"right", INF))
		var top: float = float(solid.get(&"top", INF))
		var bottom: float = float(solid.get(&"bottom", INF))
		var floor_y: float = float(world.get(&"floor_y", INF))
		if probe > left and probe < right and top < bottom and top < floor_y:
			return true
	return false

func _fighter_for_player(fighters: Array, player: int) -> Dictionary:
	for value: Variant in fighters:
		if typeof(value) != TYPE_DICTIONARY:
			continue
		var row: Dictionary = value
		if int(row.get(&"player_id", 0)) == player:
			return row
	return {}

func _fighter_for_other(fighters: Array, player: int) -> Dictionary:
	for value: Variant in fighters:
		if typeof(value) != TYPE_DICTIONARY:
			continue
		var row: Dictionary = value
		if int(row.get(&"player_id", 0)) != player:
			return row
	return {}

func _reset_policy() -> void:
	_next_punch_tick = 0
	_next_shoot_tick = 0
	_next_throw_tick = 0
	_next_jump_tick = 0
	_shoot_until_tick = -1
	_last_tick = -1
	_last_x = 0.0
	_stuck_ticks = 0

class_name ArenaState
extends RefCounted
## Pure, integer-quantized arena topology for the SA-03 simulation.
##
## This is a gameplay data model only.  It has no Node, rendering, or physics
## server dependency.  Coordinates are world units and are advanced at 60 Hz.

const WORLD_SCHEMA: StringName = &"sa03.arena.v1"

var width: int = 1600
var height: int = 900
var floor_y: int = 420
var pit_death_y: int = 620
var tick: int = 0
var hazard_timer_ticks: int = 0
var rng_state: int = 1
var rng_counter: int = 0

var _platforms: Array[Dictionary] = []
var _ladders: Array[Dictionary] = []
var _pits: Array[Dictionary] = []

func _init(seed_value: int = 1) -> void:
	rng_state = seed_value if seed_value > 0 else 1
	# Original placeholder topology.  Dimensions are tuning scaffolding, not
	# an observation of any reference game.
	_platforms.append({&"id": &"floor", &"left": 0, &"right": width, &"y": floor_y})
	_platforms.append({&"id": &"north_deck", &"left": 180, &"right": 610, &"y": 270})
	_platforms.append({&"id": &"east_deck", &"left": 990, &"right": 1430, &"y": 300})
	_ladders.append({&"id": &"west_ladder", &"x": 520, &"top": 270, &"bottom": floor_y})
	_ladders.append({&"id": &"east_ladder", &"x": 1080, &"top": 300, &"bottom": floor_y})
	_pits.append({&"id": &"service_pit", &"left": 700, &"right": 900})
	_platforms.make_read_only()
	_ladders.make_read_only()
	_pits.make_read_only()

func advance_tick() -> void:
	tick += 1
	hazard_timer_ticks = (hazard_timer_ticks + 1) % 180
	rng_state = _next_rng(rng_state)
	rng_counter += 1

func is_in_pit(x: int) -> bool:
	for pit: Dictionary in _pits:
		if x > int(pit[&"left"]) and x < int(pit[&"right"]):
			return true
	return false

func ladder_at(x: int, y: int) -> bool:
	return ladder_index_at(x, y) >= 0

func ladder_index_at(x: int, y: int) -> int:
	var index: int = 0
	for ladder: Dictionary in _ladders:
		var ladder_x: int = int(ladder[&"x"])
		var top: int = int(ladder[&"top"])
		var bottom: int = int(ladder[&"bottom"])
		if abs(x - ladder_x) <= 18 and y >= top - 8 and y <= bottom + 8:
			return index
		index += 1
	return -1

func ladder_top_at(x: int, y: int) -> int:
	var index: int = ladder_index_at(x, y)
	return -1 if index < 0 else int(_ladders[index][&"top"])

func ladder_bottom_at(x: int, y: int) -> int:
	var index: int = ladder_index_at(x, y)
	return -1 if index < 0 else int(_ladders[index][&"bottom"])

func ladder_x_at(x: int, y: int) -> int:
	var index: int = ladder_index_at(x, y)
	return x if index < 0 else int(_ladders[index][&"x"])

func landing_y(x: int, previous_y: int, candidate_y: int) -> int:
	if candidate_y < previous_y:
		return -1
	var best_y: int = -1
	for platform: Dictionary in _platforms:
		var left: int = int(platform[&"left"])
		var right: int = int(platform[&"right"])
		var platform_y: int = int(platform[&"y"])
		if x < left or x > right:
			continue
		if previous_y <= platform_y and candidate_y >= platform_y:
			if best_y < 0 or platform_y < best_y:
				best_y = platform_y
	if best_y == floor_y and is_in_pit(x):
		return -1
	return best_y

func spawn_for_player(player_id: int) -> Vector2i:
	if player_id == 1:
		return Vector2i(360, floor_y)
	return Vector2i(1240, floor_y)

func snapshot() -> Dictionary:
	var platforms: Array[Dictionary] = []
	for platform: Dictionary in _platforms:
		var copy: Dictionary = platform.duplicate(true)
		copy.make_read_only()
		platforms.append(copy)
	var ladders: Array[Dictionary] = []
	for ladder: Dictionary in _ladders:
		var copy: Dictionary = ladder.duplicate(true)
		copy.make_read_only()
		ladders.append(copy)
	var pits: Array[Dictionary] = []
	for pit: Dictionary in _pits:
		var copy: Dictionary = pit.duplicate(true)
		copy.make_read_only()
		pits.append(copy)
	platforms.make_read_only()
	ladders.make_read_only()
	pits.make_read_only()
	var spawns: Array[Dictionary] = [
		{&"player_id": 1, &"x": spawn_for_player(1).x, &"y": spawn_for_player(1).y},
		{&"player_id": 2, &"x": spawn_for_player(2).x, &"y": spawn_for_player(2).y},
	]
	for spawn: Dictionary in spawns:
		spawn.make_read_only()
	spawns.make_read_only()
	var result: Dictionary = {
		&"schema": WORLD_SCHEMA,
		&"width": width,
		&"height": height,
		&"floor_y": floor_y,
		&"pit_death_y": pit_death_y,
		&"tick": tick,
		&"hazard_timer_ticks": hazard_timer_ticks,
		&"rng_state": rng_state,
		&"rng_counter": rng_counter,
		&"platforms": platforms,
		&"ladders": ladders,
		&"pits": pits,
		&"spawns": spawns,
		&"canonical_topology": canonical_topology(),
	}
	result.make_read_only()
	return result

func canonical_fragment() -> String:
	return "arena_topology=%s|arena_runtime=%d,%d,%d,%d" % [canonical_topology(), tick, hazard_timer_ticks, rng_state, rng_counter]

func canonical_topology() -> String:
	var parts: Array[String] = [
		"bounds=%d,%d" % [width, height],
		"floor=%d" % floor_y,
		"pitdeath=%d" % pit_death_y,
	]
	for platform: Dictionary in _platforms:
		parts.append("platform:%s,%d,%d,%d" % [String(platform[&"id"]), int(platform[&"left"]), int(platform[&"right"]), int(platform[&"y"])])
	for ladder: Dictionary in _ladders:
		parts.append("ladder:%s,%d,%d,%d" % [String(ladder[&"id"]), int(ladder[&"x"]), int(ladder[&"top"]), int(ladder[&"bottom"])])
	for pit: Dictionary in _pits:
		parts.append("pit:%s,%d,%d" % [String(pit[&"id"]), int(pit[&"left"]), int(pit[&"right"])])
	var p1: Vector2i = spawn_for_player(1)
	var p2: Vector2i = spawn_for_player(2)
	parts.append("spawn:1,%d,%d" % [p1.x, p1.y])
	parts.append("spawn:2,%d,%d" % [p2.x, p2.y])
	return ";".join(parts)

func _next_rng(value: int) -> int:
	# LCG state is retained only as a deterministic counter source for future
	# mechanics; no random presentation state is part of this core.
	return int((value * 1664525 + 1013904223) & 0x7fffffff)

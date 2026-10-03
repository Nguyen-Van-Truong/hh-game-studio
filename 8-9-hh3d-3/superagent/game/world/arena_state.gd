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
	for ladder: Dictionary in _ladders:
		var ladder_x: int = int(ladder[&"x"])
		var top: int = int(ladder[&"top"])
		var bottom: int = int(ladder[&"bottom"])
		if abs(x - ladder_x) <= 18 and y >= top - 8 and y <= bottom + 8:
			return true
	return false

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
		platforms.append(platform.duplicate(true))
	var ladders: Array[Dictionary] = []
	for ladder: Dictionary in _ladders:
		ladders.append(ladder.duplicate(true))
	var pits: Array[Dictionary] = []
	for pit: Dictionary in _pits:
		pits.append(pit.duplicate(true))
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
	}
	result.make_read_only()
	return result

func canonical_fragment() -> String:
	return "arena=%d,%d,%d,%d,%d,%d,%d,%d" % [
		width,
		height,
		floor_y,
		pit_death_y,
		tick,
		hazard_timer_ticks,
		rng_state,
		rng_counter,
	]

func _next_rng(value: int) -> int:
	# LCG state is retained only as a deterministic counter source for future
	# mechanics; no random presentation state is part of this core.
	return int((value * 1664525 + 1013904223) & 0x7fffffff)

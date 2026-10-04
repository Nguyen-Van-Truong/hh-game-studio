class_name ArenaState
extends RefCounted
## Pure, integer-quantized arena topology for the SA-03 simulation.
##
## This is a gameplay data model only.  It has no Node, rendering, or physics
## server dependency.  Coordinates are world units and are advanced at 60 Hz.

const WORLD_SCHEMA: StringName = &"sa03.arena.v2"

var width: int = 1600
var height: int = 900
var floor_y: int = 740
var pit_death_y: int = 980
var ladder_margin: int = 18
var tick: int = 0
var hazard_timer_ticks: int = 0
var rng_state: int = 1
var rng_counter: int = 0

var _platforms: Array[Dictionary] = []
var _ladders: Array[Dictionary] = []
var _pits: Array[Dictionary] = []
var _solids: Array[Dictionary] = []
var _spawns: Array[Dictionary] = []

func _init(seed_value: int = 1) -> void:
	rng_state = seed_value if seed_value > 0 else 1
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://data/movement_room.json"))
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("Missing movement-room geometry")
		return
	var layout: Dictionary = parsed
	if layout.get("schema") != "sa03.room.v1":
		push_error("Unsupported movement-room geometry")
		return
	width = int(layout["width"])
	height = int(layout["height"])
	floor_y = int(layout["floor_y"])
	pit_death_y = int(layout["pit_death_y"])
	ladder_margin = int(layout["ladder_margin"])
	_load_rows(layout["platforms"], _platforms)
	_load_rows(layout["ladders"], _ladders)
	_load_rows(layout["pits"], _pits)
	_load_rows(layout["solids"], _solids)
	_load_rows(layout["spawns"], _spawns)

func _load_rows(source: Array, destination: Array[Dictionary]) -> void:
	for value: Dictionary in source:
		var row: Dictionary = value.duplicate(true)
		row.make_read_only()
		destination.append(row)
	destination.make_read_only()

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
		if abs(x - ladder_x) <= ladder_margin and y >= top and y <= bottom:
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

func landing_y(x: int, previous_y: int, candidate_y: int, half_width: int = 0, ignore_one_way: bool = false) -> int:
	if candidate_y < previous_y:
		return -1
	var best_y: int = -1
	for platform: Dictionary in _platforms:
		var left: int = int(platform[&"left"])
		var right: int = int(platform[&"right"])
		var platform_y: int = int(platform[&"y"])
		if x + half_width <= left or x - half_width >= right:
			continue
		if ignore_one_way and bool(platform[&"one_way"]):
			continue
		if previous_y <= platform_y and candidate_y >= platform_y:
			if best_y < 0 or platform_y < best_y:
				best_y = platform_y
	for solid: Dictionary in _solids:
		var top: int = int(solid[&"top"])
		if x + half_width <= int(solid[&"left"]) or x - half_width >= int(solid[&"right"]):
			continue
		if previous_y <= top and candidate_y >= top and (best_y < 0 or top < best_y):
			best_y = top
	return best_y

func horizontal_stop(previous_x: int, candidate_x: int, feet_y: int, half_width: int, body_height: int) -> int:
	var result: int = clampi(candidate_x, half_width, width - half_width)
	for solid: Dictionary in _solids:
		if feet_y <= int(solid[&"top"]) or feet_y - body_height >= int(solid[&"bottom"]):
			continue
		var left: int = int(solid[&"left"])
		var right: int = int(solid[&"right"])
		if candidate_x > previous_x and previous_x + half_width <= left and result + half_width > left:
			result = left - half_width
		elif candidate_x < previous_x and previous_x - half_width >= right and result - half_width < right:
			result = right + half_width
	return result

func ceiling_stop(x: int, previous_y: int, candidate_y: int, half_width: int, body_height: int) -> int:
	var result: int = candidate_y
	for solid: Dictionary in _solids:
		if x + half_width <= int(solid[&"left"]) or x - half_width >= int(solid[&"right"]):
			continue
		var bottom: int = int(solid[&"bottom"])
		if previous_y - body_height >= bottom and result - body_height < bottom:
			result = bottom + body_height
	return result

func on_one_way(x: int, feet_y: int, half_width: int) -> bool:
	for platform: Dictionary in _platforms:
		if bool(platform[&"one_way"]) and feet_y == int(platform[&"y"]):
			if x + half_width > int(platform[&"left"]) and x - half_width < int(platform[&"right"]):
				return true
	return false

func spawn_for_player(player_id: int) -> Vector2i:
	for spawn: Dictionary in _spawns:
		if int(spawn[&"player_id"]) == player_id:
			return Vector2i(int(spawn[&"x"]), int(spawn[&"y"]))
	return Vector2i.ZERO

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
	var solids: Array[Dictionary] = _solids.duplicate(true)
	for solid: Dictionary in solids:
		solid.make_read_only()
	solids.make_read_only()
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
		&"solids": solids,
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
		"ladder_margin=%d" % ladder_margin,
	]
	for platform: Dictionary in _platforms:
		parts.append("platform:%s,%d,%d,%d,%d" % [String(platform[&"id"]), int(platform[&"left"]), int(platform[&"right"]), int(platform[&"y"]), int(bool(platform[&"one_way"]))])
	for solid: Dictionary in _solids:
		parts.append("solid:%s,%d,%d,%d,%d" % [String(solid[&"id"]), int(solid[&"left"]), int(solid[&"right"]), int(solid[&"top"]), int(solid[&"bottom"])])
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

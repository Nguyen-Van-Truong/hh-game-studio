class_name ArenaState
extends RefCounted
## Serializable arena topology and gameplay sensors; Godot owns collisions.
##
## This is a gameplay data model only.  It has no Node, rendering, or physics
## server dependency.  Coordinates are world units and are advanced at 60 Hz.

const WORLD_SCHEMA: StringName = &"sa03.arena.v2"

var width: float = 1600
var height: float = 900
var floor_y: float = 740
var pit_death_y: float = 980
var ladder_margin: float = 18
var tick: int = 0
var hazard_timer_ticks: int = 0
var rng_state: int = 1
var rng_counter: int = 0
var valid: bool = false
var load_error: StringName = &"not_loaded"

var _platforms: Array[Dictionary] = []
var _ladders: Array[Dictionary] = []
var _pits: Array[Dictionary] = []
var _solids: Array[Dictionary] = []
var _spawns: Array[Dictionary] = []
var _pickups: Array[Dictionary] = []
var _props: Array[Dictionary] = []
var _layout_path: String = "res://data/movement_room.json"

func _init(seed_value: int = 1, layout_path: String = "res://data/movement_room.json") -> void:
	rng_state = seed_value if seed_value > 0 else 1
	_layout_path = layout_path if not layout_path.is_empty() else "res://data/movement_room.json"
	if not _layout_path.begins_with("res://data/") or _layout_path.contains(".."):
		load_error = &"layout_path_outside_product_data"
		return
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(_layout_path))
	if typeof(parsed) != TYPE_DICTIONARY:
		load_error = &"layout_not_dictionary"
		return
	var layout: Dictionary = parsed
	if layout.get("schema") != "sa03.room.v1":
		load_error = &"unsupported_layout_schema"
		return
	var table_specs: Dictionary = {
		&"platforms": {&"required": [&"id", &"left", &"right", &"y", &"one_way"], &"numeric": [&"left", &"right", &"y"], &"strings": [&"id"], &"booleans": [&"one_way"]},
		&"ladders": {&"required": [&"id", &"x", &"top", &"bottom"], &"numeric": [&"x", &"top", &"bottom"], &"strings": [&"id"]},
		&"pits": {&"required": [&"id", &"left", &"right"], &"numeric": [&"left", &"right"], &"strings": [&"id"]},
		&"solids": {&"required": [&"id", &"left", &"right", &"top", &"bottom"], &"numeric": [&"left", &"right", &"top", &"bottom"], &"strings": [&"id"]},
		&"spawns": {&"required": [&"player_id", &"x", &"y"], &"numeric": [&"player_id", &"x", &"y"]},
		&"pickups": {&"required": [&"id", &"kind", &"x", &"y"], &"numeric": [&"x", &"y"], &"strings": [&"id", &"kind"]},
		&"props": {&"required": [&"id", &"kind", &"x", &"y"], &"numeric": [&"x", &"y"], &"strings": [&"id", &"kind"]},
	}
	for table_key: StringName in table_specs.keys():
		if not layout.has(table_key) and (table_key != &"pickups" and table_key != &"props"):
			load_error = StringName("missing_%s_rows" % String(table_key))
			return
		if not layout.has(table_key):
			continue
		var spec: Dictionary = table_specs[table_key]
		if not _valid_rows_shape(layout[table_key], spec):
			load_error = StringName("invalid_%s_rows" % String(table_key))
			return
	var spawn_rows: Array = Array(layout[&"spawns"])
	if not _valid_spawns(spawn_rows):
		load_error = &"invalid_player_spawns"
		return
	for scalar_key: StringName in [&"width", &"height", &"floor_y", &"pit_death_y", &"ladder_margin"]:
		var scalar_value: Variant = layout.get(scalar_key, null)
		if typeof(scalar_value) != TYPE_INT and typeof(scalar_value) != TYPE_FLOAT:
			load_error = StringName("invalid_%s_scalar" % String(scalar_key))
			return
	width = float(layout["width"])
	height = float(layout["height"])
	floor_y = float(layout["floor_y"])
	pit_death_y = float(layout["pit_death_y"])
	ladder_margin = float(layout["ladder_margin"])
	_load_rows(layout["platforms"], _platforms)
	_load_rows(layout["ladders"], _ladders)
	_load_rows(layout["pits"], _pits)
	_load_rows(layout["solids"], _solids)
	_load_rows(layout["spawns"], _spawns)
	var pickup_rows: Variant = layout.get("pickups", [])
	if typeof(pickup_rows) == TYPE_ARRAY:
		_load_rows(Array(pickup_rows), _pickups)
	var prop_rows: Variant = layout.get("props", [])
	if typeof(prop_rows) == TYPE_ARRAY:
		_load_rows(Array(prop_rows), _props)
	valid = true
	load_error = &""

func _valid_rows_shape(value: Variant, spec: Dictionary) -> bool:
	if typeof(value) != TYPE_ARRAY:
		return false
	for row: Variant in Array(value):
		if typeof(row) != TYPE_DICTIONARY:
			return false
		var dictionary: Dictionary = row
		for key: StringName in spec.get(&"required", []):
			if not dictionary.has(key):
				return false
		for key: StringName in spec.get(&"numeric", []):
			var numeric_value: Variant = dictionary.get(key, null)
			if typeof(numeric_value) != TYPE_INT and typeof(numeric_value) != TYPE_FLOAT:
				return false
		for key: StringName in spec.get(&"strings", []):
			if typeof(dictionary.get(key, null)) != TYPE_STRING:
				return false
		for key: StringName in spec.get(&"booleans", []):
			if typeof(dictionary.get(key, null)) != TYPE_BOOL:
				return false
		if dictionary.has(&"active") and typeof(dictionary[&"active"]) != TYPE_BOOL:
			return false
	return true

func _valid_spawns(rows: Array) -> bool:
	if rows.size() != 2:
		return false
	var seen: Dictionary = {}
	for value: Variant in rows:
		var row: Dictionary = value
		var player_id: int = int(row[&"player_id"])
		if player_id != 1 and player_id != 2:
			return false
		if seen.has(player_id):
			return false
		seen[player_id] = true
	var first: Dictionary = rows[0]
	var second: Dictionary = rows[1]
	return not is_equal_approx(float(first[&"x"]), float(second[&"x"])) or not is_equal_approx(float(first[&"y"]), float(second[&"y"]))

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

func is_in_pit(x: float) -> bool:
	for pit: Dictionary in _pits:
		if x > float(pit[&"left"]) and x < float(pit[&"right"]):
			return true
	return false

func supply_drop_target(requested_x: float, clearance: float = 28.0) -> Vector2:
	"""Return a reachable landing point for a falling supply crate.

	The visual drop is not a physics body, so choosing a raw map x can put the
	pickup inside a pit, a wall, or a cover block.  Probe deterministic nearby
	points, reject any point whose pickup radius crosses a pit/solid, then land
	on the highest walkable platform below the sky.  This keeps the item visible
	and collectible across every authored room without changing map geometry.
	"""
	var offsets: Array[float] = [0.0, -48.0, 48.0, -96.0, 96.0, -144.0, 144.0, -192.0, 192.0]
	for offset: float in offsets:
		var candidate: float = clampf(requested_x + offset, clearance + 4.0, width - clearance - 4.0)
		if not _drop_x_is_clear(candidate, clearance):
			continue
		var landing_y: float = _highest_walkable_y(candidate, clearance)
		return Vector2(candidate, landing_y)
	return Vector2(clampf(requested_x, clearance + 4.0, width - clearance - 4.0), floor_y)

func _drop_x_is_clear(candidate: float, clearance: float) -> bool:
	var left: float = candidate - clearance
	var right: float = candidate + clearance
	for pit: Dictionary in _pits:
		if right > float(pit[&"left"]) and left < float(pit[&"right"]):
			return false
	for solid: Dictionary in _solids:
		if right > float(solid[&"left"]) and left < float(solid[&"right"]):
			return false
	return true

func _highest_walkable_y(candidate: float, clearance: float) -> float:
	var landing_y: float = floor_y
	for platform: Dictionary in _platforms:
		var platform_left: float = float(platform[&"left"]) + clearance
		var platform_right: float = float(platform[&"right"]) - clearance
		var platform_y: float = float(platform[&"y"])
		if candidate >= platform_left and candidate <= platform_right and platform_y < landing_y:
			landing_y = platform_y
	return landing_y

func ladder_at(x: float, y: float) -> bool:
	return ladder_index_at(x, y) >= 0

func ladder_index_at(x: float, y: float) -> int:
	var index: int = 0
	for ladder: Dictionary in _ladders:
		var ladder_x: float = float(ladder[&"x"])
		var top: float = float(ladder[&"top"])
		var bottom: float = float(ladder[&"bottom"])
		if abs(x - ladder_x) <= ladder_margin and y >= top - 0.1 and y <= bottom + 0.1:
			return index
		index += 1
	return -1

func ladder_top_at(x: float, y: float) -> float:
	var index: int = ladder_index_at(x, y)
	return -1 if index < 0 else float(_ladders[index][&"top"])

func ladder_bottom_at(x: float, y: float) -> float:
	var index: int = ladder_index_at(x, y)
	return -1 if index < 0 else float(_ladders[index][&"bottom"])

func ladder_x_at(x: float, y: float) -> float:
	var index: int = ladder_index_at(x, y)
	return x if index < 0 else float(_ladders[index][&"x"])

func on_one_way(x: float, feet_y: float, half_width: float) -> bool:
	for platform: Dictionary in _platforms:
		if bool(platform[&"one_way"]) and absf(feet_y - float(platform[&"y"])) <= 0.1:
			if x + half_width > float(platform[&"left"]) and x - half_width < float(platform[&"right"]):
				return true
	return false

func spawn_for_player(player_id: int) -> Vector2:
	for spawn: Dictionary in _spawns:
		if int(spawn[&"player_id"]) == player_id:
			return Vector2(float(spawn[&"x"]), float(spawn[&"y"]))
	return Vector2.ZERO

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
	var pickups: Array[Dictionary] = _copy_rows(_pickups)
	var props: Array[Dictionary] = _copy_rows(_props)
	var result: Dictionary = {
		&"schema": WORLD_SCHEMA,
		&"valid": valid,
		&"load_error": load_error,
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
		&"pickups": pickups,
		&"props": props,
		&"layout_path": _layout_path,
		&"canonical_topology": canonical_topology(),
	}
	result.make_read_only()
	return result

func _copy_rows(source: Array[Dictionary]) -> Array[Dictionary]:
	var copied: Array[Dictionary] = []
	for row: Dictionary in source:
		var copy: Dictionary = row.duplicate(true)
		copy.make_read_only()
		copied.append(copy)
	copied.make_read_only()
	return copied

func canonical_fragment() -> String:
	return "arena_topology=%s|arena_runtime=%d,%d,%d,%d" % [canonical_topology(), tick, hazard_timer_ticks, rng_state, rng_counter]

func canonical_topology() -> String:
	var parts: Array[String] = [
		"layout=%s" % _layout_path,
		"bounds=%.3f,%.3f" % [width, height],
		"floor=%.3f" % floor_y,
		"pitdeath=%.3f" % pit_death_y,
		"ladder_margin=%.3f" % ladder_margin,
	]
	for platform: Dictionary in _platforms:
		parts.append("platform:%s,%.3f,%.3f,%.3f,%d" % [String(platform[&"id"]), float(platform[&"left"]), float(platform[&"right"]), float(platform[&"y"]), int(bool(platform[&"one_way"]))])
	for solid: Dictionary in _solids:
		parts.append("solid:%s,%.3f,%.3f,%.3f,%.3f" % [String(solid[&"id"]), float(solid[&"left"]), float(solid[&"right"]), float(solid[&"top"]), float(solid[&"bottom"])])
	for ladder: Dictionary in _ladders:
		parts.append("ladder:%s,%.3f,%.3f,%.3f" % [String(ladder[&"id"]), float(ladder[&"x"]), float(ladder[&"top"]), float(ladder[&"bottom"])])
	for pit: Dictionary in _pits:
		parts.append("pit:%s,%.3f,%.3f" % [String(pit[&"id"]), float(pit[&"left"]), float(pit[&"right"])])
	for pickup: Dictionary in _pickups:
		parts.append("pickup:%s,%s,%.3f,%.3f" % [String(pickup.get(&"id", &"")), String(pickup.get(&"kind", &"")), float(pickup.get(&"x", 0.0)), float(pickup.get(&"y", 0.0))])
	for prop: Dictionary in _props:
		parts.append("prop:%s,%s,%.3f,%.3f" % [String(prop.get(&"id", &"")), String(prop.get(&"kind", &"")), float(prop.get(&"x", 0.0)), float(prop.get(&"y", 0.0))])
	var p1: Vector2 = spawn_for_player(1)
	var p2: Vector2 = spawn_for_player(2)
	parts.append("spawn:1,%.3f,%.3f" % [p1.x, p1.y])
	parts.append("spawn:2,%.3f,%.3f" % [p2.x, p2.y])
	return ";".join(parts)

func _next_rng(value: int) -> int:
	# LCG state is retained only as a deterministic counter source for future
	# mechanics; no random presentation state is part of this core.
	return int((value * 1664525 + 1013904223) & 0x7fffffff)

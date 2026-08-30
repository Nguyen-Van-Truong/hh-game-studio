class_name Traversal
extends RefCounted

## Ladder / ledge / one-way drop queries (VF2-WP5).
## Clock is ledger:RL-SIM-FIXED-60 (assumption). Ladder stays
## ledger:RL-MOVE-LADDER (assumption). Ledge stays
## ledger:RL-MOVE-LEDGE (assumption). Drop stays
## ledger:RL-MOVE-DROP (assumption). InputFrame action `ledge`
## stays reserved (no dedicated remap). Y8 observation stays
## ledger:RL-MOVE-ROLL-DIVE (unavailable). Not a Y8 play observation.

const PATH: String = "res://data/sim/traversal.json"
const SCHEMA_ID: String = "vf.sim.traversal.v1"

static var _cache: Dictionary = {}


static func data() -> Dictionary:
	if _cache.is_empty():
		_cache = SimConstants.load_json(PATH)
	return _cache


static func movement() -> Dictionary:
	var raw: Variant = data().get("movement", {})
	if raw is Dictionary:
		return raw as Dictionary
	return {}


static func f(key: String, fallback: float) -> float:
	return float(movement().get(key, fallback))


static func fixtures() -> Dictionary:
	var raw: Variant = data().get("fixtures", {})
	if raw is Dictionary:
		return raw as Dictionary
	return {}


static func has_fixture(map_id: String) -> bool:
	return fixtures().has(map_id)


static func fixture_ids() -> PackedStringArray:
	var ids: PackedStringArray = PackedStringArray()
	var keys: Array = fixtures().keys()
	keys.sort()
	var i: int = 0
	while i < keys.size():
		ids.append(str(keys[i]))
		i += 1
	return ids


static func fixture_grid(map_id: String) -> PackedStringArray:
	var raw: Variant = fixtures().get(map_id, [])
	var out: PackedStringArray = PackedStringArray()
	if raw is Array:
		var arr: Array = raw as Array
		var i: int = 0
		while i < arr.size():
			out.append(str(arr[i]))
			i += 1
	return out


static func fixture_name(map_id: String) -> String:
	var names: Variant = data().get("fixture_names", {})
	if names is Dictionary:
		return str((names as Dictionary).get(map_id, map_id))
	return map_id


static func cell_at(pos: Vector2) -> Vector2i:
	return Vector2i(
		int(floor(pos.x / float(Maps.TILE))),
		int(floor(pos.y / float(Maps.TILE)))
	)


static func cell_center(cell: Vector2i) -> Vector2:
	return Vector2(
		float(cell.x * Maps.TILE) + float(Maps.TILE) * 0.5,
		float(cell.y * Maps.TILE) + float(Maps.TILE) * 0.5
	)


static func cell_top(cell: Vector2i) -> float:
	return float(cell.y * Maps.TILE)


static func cell_left(cell: Vector2i) -> float:
	return float(cell.x * Maps.TILE)


static func char_at(map_id: String, cell: Vector2i) -> String:
	var rows: PackedStringArray = Maps.grid(map_id)
	if cell.y < 0 or cell.y >= rows.size():
		return "#"
	var row: String = String(rows[cell.y])
	if cell.x < 0 or cell.x >= row.length():
		return "#"
	return row.substr(cell.x, 1)


static func is_solid_cell(map_id: String, cell: Vector2i) -> bool:
	return Maps.is_solid(char_at(map_id, cell))


static func is_platform_cell(map_id: String, cell: Vector2i) -> bool:
	return Maps.is_platform(char_at(map_id, cell))


static func is_ladder_cell(map_id: String, cell: Vector2i) -> bool:
	return Maps.is_ladder(char_at(map_id, cell))


static func is_empty_cell(map_id: String, cell: Vector2i) -> bool:
	var ch: String = char_at(map_id, cell)
	return ch == "." or ch == "P" or ch == "1" or ch == "2" or ch == "3" or ch == "w" or ch == "H" or ch == "L"


static func nearest_ladder_cell(arena: Arena, pos: Vector2) -> Vector2i:
	if arena == null:
		return cell_at(pos)
	var pts: Array[Vector2] = [
		pos,
		pos + Vector2(0, 8),
		pos + Vector2(0, -8),
		pos + Vector2(10, 0),
		pos + Vector2(-10, 0),
	]
	var i: int = 0
	while i < pts.size():
		var cell: Vector2i = cell_at(pts[i])
		if arena.ladder_cells.has(cell):
			return cell
		i += 1
	return cell_at(pos)


static func sample(arena: Arena, fighter: Fighter) -> Dictionary:
	var map_id: String = "rooftops"
	if arena != null:
		map_id = arena.map_id
	var pos: Vector2 = Vector2.ZERO
	var facing: float = 1.0
	if fighter != null:
		pos = fighter.global_position
		facing = fighter.facing
	var on_ladder: bool = arena != null and arena.has_ladder_at(pos)
	var snap_x: float = pos.x
	if on_ladder:
		snap_x = cell_center(nearest_ladder_cell(arena, pos)).x
	var up_cell: Vector2i = cell_at(pos + Vector2(0.0, -16.0))
	var up_cell2: Vector2i = cell_at(pos + Vector2(0.0, -22.0))
	var down_cell: Vector2i = cell_at(pos + Vector2(0.0, 12.0))
	var climb_up_blocked: bool = is_solid_cell(map_id, up_cell) or is_solid_cell(map_id, up_cell2)
	var climb_down_blocked: bool = is_solid_cell(map_id, down_cell)
	var feet: Vector2 = pos + Vector2(0.0, 12.0)
	var one_way_under: bool = is_platform_cell(map_id, cell_at(feet + Vector2(0.0, 4.0)))
	var solid_under: bool = is_solid_cell(map_id, cell_at(feet + Vector2(0.0, 4.0)))
	var ledge: Dictionary = detect_ledge(map_id, pos, facing)
	return {
		"map_id": map_id,
		"on_ladder": on_ladder,
		"snap_x": snap_x,
		"climb_up_blocked": climb_up_blocked,
		"climb_down_blocked": climb_down_blocked,
		"one_way_under": one_way_under and not solid_under,
		"ledge": ledge,
	}


static func detect_ledge(map_id: String, pos: Vector2, facing: float) -> Dictionary:
	var empty: Dictionary = {
		"valid": false,
		"x": pos.x,
		"y": pos.y,
		"stand_x": pos.x,
		"stand_y": pos.y,
		"side": 0.0,
		"nx": 0.0,
		"ny": 0.0,
	}
	var reach: float = f("grab_reach_x", 12.0)
	var window: float = f("grab_window_y", 18.0)
	var inset: float = f("hang_inset", 7.0)
	var below: float = f("hang_below", 6.0)
	var sides: Array[float] = [1.0, -1.0]
	if facing < 0.0:
		sides = [-1.0, 1.0]
	var s: int = 0
	while s < sides.size():
		var side: float = float(sides[s])
		var probe: Vector2 = pos + Vector2(side * reach, -2.0)
		var cell: Vector2i = cell_at(probe)
		var dy: int = -1
		while dy <= 1:
			var lip: Vector2i = Vector2i(cell.x, cell.y + dy)
			if not (is_solid_cell(map_id, lip) or is_platform_cell(map_id, lip)):
				dy += 1
				continue
			if not is_empty_cell(map_id, Vector2i(lip.x, lip.y - 1)):
				dy += 1
				continue
			var air: Vector2i = Vector2i(lip.x - int(side), lip.y)
			if not is_empty_cell(map_id, air):
				dy += 1
				continue
			var lip_y: float = cell_top(lip)
			if pos.y < lip_y + 2.0 or pos.y > lip_y + window:
				dy += 1
				continue
			var edge: Vector2i = lip
			var walk: int = 0
			while walk < 8:
				var inward: Vector2i = Vector2i(edge.x - int(side), edge.y)
				if not (is_solid_cell(map_id, inward) or is_platform_cell(map_id, inward)):
					break
				edge = inward
				walk += 1
			lip_y = cell_top(edge)
			var hang_x: float = cell_left(edge)
			if side > 0.0:
				hang_x = hang_x - inset
			else:
				hang_x = hang_x + float(Maps.TILE) + inset
			var hang_y: float = lip_y + below
			var stand_x: float = cell_center(edge).x
			var stand_y: float = lip_y - 14.0
			return {
				"valid": true,
				"x": hang_x,
				"y": hang_y,
				"stand_x": stand_x,
				"stand_y": stand_y,
				"side": side,
				"nx": -side,
				"ny": 0.0,
			}
		s += 1
	return empty


static func quantize_normal(n: Vector2) -> Vector2:
	return Vector2(
		float(SimConstants.quantize(n.x)) / SimConstants.HASH_SCALE,
		float(SimConstants.quantize(n.y)) / SimConstants.HASH_SCALE
	)

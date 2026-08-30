class_name MapGraph
extends RefCounted

## Walk/jump/ladder topology graph (VF5-WP1).
## Jump envelope is product tuning, not observed Y8.
## ledger:RL-MAP-GRAPH (assumption).

const _MapCatalog: GDScript = preload("res://src/maps/map_catalog.gd")
const _MapCodec: GDScript = preload("res://src/maps/map_codec.gd")

const DEFAULT_JUMP_DX: int = 10
const DEFAULT_JUMP_DY: int = 4
const DEFAULT_MIN_PLATFORM: int = 2


static func jump_dx() -> int:
	return int(_dict(_MapCatalog.schema().get("graph", {})).get("jump_dx", DEFAULT_JUMP_DX))


static func jump_dy() -> int:
	return int(_dict(_MapCatalog.schema().get("graph", {})).get("jump_dy", DEFAULT_JUMP_DY))


static func min_platform() -> int:
	return int(_dict(_MapCatalog.schema().get("graph", {})).get("min_platform", DEFAULT_MIN_PLATFORM))


static func walkable_cells(doc: Dictionary) -> Array:
	var out: Array = []
	var width: int = int(doc.get("width", 0))
	var height: int = int(doc.get("height", 0))
	var y: int = 0
	while y < height:
		var x: int = 0
		while x < width:
			if _is_walkable(doc, x, y):
				out.append([x, y])
			x += 1
		y += 1
	return out


static func platforms(doc: Dictionary) -> Array:
	var seen: Dictionary = {}
	var out: Array = []
	var width: int = int(doc.get("width", 0))
	var height: int = int(doc.get("height", 0))
	var y: int = 0
	while y < height:
		var x: int = 0
		while x < width:
			if (
				_MapCodec.is_walk_support(doc, x, y)
				and _is_walkable(doc, x, y - 1)
				and not seen.has(_key(x, y))
			):
				var run: Array = []
				var cx: int = x
				while (
					cx < width
					and _MapCodec.is_walk_support(doc, cx, y)
					and _is_walkable(doc, cx, y - 1)
				):
					seen[_key(cx, y)] = true
					run.append([cx, y])
					cx += 1
				if run.size() >= min_platform():
					out.append(run)
			x += 1
		y += 1
	return out


static func spawn_walkable(doc: Dictionary) -> Array:
	var out: Array = []
	var spawns: Array = _MapCodec.layer_cells(doc, "spawn")
	var i: int = 0
	while i < spawns.size():
		var cell: Array = _as_array(spawns[i])
		if cell.size() >= 2:
			var sx: int = int(cell[0])
			var sy: int = int(cell[1])
			var fy: int = sy
			var height: int = int(doc.get("height", 0))
			while fy < height:
				if _is_walkable(doc, sx, fy):
					out.append([sx, fy])
					break
				fy += 1
		i += 1
	return out


static func reach_from_spawns(doc: Dictionary) -> Dictionary:
	var start: Array = spawn_walkable(doc)
	var reached: Dictionary = {}
	var queue: Array = []
	var i: int = 0
	while i < start.size():
		var cell: Array = start[i] as Array
		var key: String = _key(int(cell[0]), int(cell[1]))
		if not reached.has(key):
			reached[key] = true
			queue.append(cell)
		i += 1
	var dx: int = jump_dx()
	var dy: int = jump_dy()
	var q: int = 0
	while q < queue.size():
		var cur: Array = queue[q] as Array
		var neighbors: Array = _neighbors(doc, int(cur[0]), int(cur[1]), dx, dy)
		var n: int = 0
		while n < neighbors.size():
			var nxt: Array = neighbors[n] as Array
			var nk: String = _key(int(nxt[0]), int(nxt[1]))
			if not reached.has(nk):
				reached[nk] = true
				queue.append(nxt)
			n += 1
		q += 1
	return reached


static func elevation_count(doc: Dictionary) -> int:
	var seen: Dictionary = {}
	var plats: Array = platforms(doc)
	var i: int = 0
	while i < plats.size():
		var run: Array = plats[i] as Array
		if not run.is_empty():
			var cell: Array = run[0] as Array
			seen[int(cell[1])] = true
		i += 1
	return seen.size()


static func zone_reached(doc: Dictionary, zone: Dictionary) -> bool:
	var reached: Dictionary = reach_from_spawns(doc)
	var x0: int = int(zone.get("x", 0))
	var y0: int = int(zone.get("y", 0))
	var w: int = int(zone.get("w", 1))
	var h: int = int(zone.get("h", 1))
	var y: int = y0
	while y < y0 + h:
		var x: int = x0
		while x < x0 + w:
			if reached.has(_key(x, y)) or reached.has(_key(x, y - 1)):
				return true
			x += 1
		y += 1
	return false


static func missing_platforms(doc: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var reached: Dictionary = reach_from_spawns(doc)
	if reached.is_empty():
		errors.append("%s graph has no reachable spawn walkable" % str(doc.get("id", "")))
		return errors
	var plats: Array = platforms(doc)
	var i: int = 0
	while i < plats.size():
		var run: Array = plats[i] as Array
		if not _run_reached(doc, run, reached):
			var cell: Array = run[0] as Array
			errors.append(
				"%s platform at %d,%d unreachable"
				% [str(doc.get("id", "")), int(cell[0]), int(cell[1])]
			)
		i += 1
	return errors


static func _run_reached(doc: Dictionary, run: Array, reached: Dictionary) -> bool:
	var i: int = 0
	while i < run.size():
		var cell: Array = run[i] as Array
		var x: int = int(cell[0])
		var y: int = int(cell[1])
		if reached.has(_key(x, y - 1)) and _is_walkable(doc, x, y - 1):
			return true
		if reached.has(_key(x, y)):
			return true
		i += 1
	return false


static func _neighbors(doc: Dictionary, x: int, y: int, jdx: int, jdy: int) -> Array:
	var out: Array = []
	var seen: Dictionary = {}
	_add_if_walk(doc, x - 1, y, out, seen)
	_add_if_walk(doc, x + 1, y, out, seen)
	if _MapCodec.has_xy(doc, "ladder", x, y) or _MapCodec.has_xy(doc, "ladder", x, y + 1) or _MapCodec.has_xy(doc, "ladder", x, y - 1):
		_add_if_walk(doc, x, y - 1, out, seen)
		_add_if_walk(doc, x, y + 1, out, seen)
		if _MapCodec.has_xy(doc, "ladder", x, y - 1):
			_add_if_walk(doc, x, y - 1, out, seen)
		if _MapCodec.has_xy(doc, "ladder", x, y + 1):
			_add_if_walk(doc, x, y + 1, out, seen)
	var fy: int = y + 1
	while fy < int(doc.get("height", 0)):
		if _is_walkable(doc, x, fy):
			_add_if_walk(doc, x, fy, out, seen)
			break
		if _MapCodec.is_blocker(doc, x, fy) and not _MapCodec.has_xy(doc, "one_way", x, fy):
			break
		fy += 1
	var oy: int = -jdy
	while oy <= 1:
		var ox: int = -jdx
		while ox <= jdx:
			if ox != 0 or oy != 0:
				_add_if_walk(doc, x + ox, y + oy, out, seen)
			ox += 1
		oy += 1
	return out


static func _add_if_walk(doc: Dictionary, x: int, y: int, out: Array, seen: Dictionary) -> void:
	if not _is_walkable(doc, x, y):
		return
	var key: String = _key(x, y)
	if seen.has(key):
		return
	seen[key] = true
	out.append([x, y])


static func _is_walkable(doc: Dictionary, x: int, y: int) -> bool:
	if not _MapCodec.in_bounds(doc, x, y):
		return false
	if _MapCodec.is_blocker(doc, x, y) and not _MapCodec.has_xy(doc, "one_way", x, y):
		return false
	if _MapCodec.has_xy(doc, "ladder", x, y):
		return true
	return _MapCodec.is_walk_support(doc, x, y + 1)


static func _key(x: int, y: int) -> String:
	return "%d,%d" % [x, y]


static func _as_array(value: Variant) -> Array:
	if value is Array:
		return value as Array
	return []


static func _dict(value: Variant) -> Dictionary:
	if value is Dictionary:
		return value as Dictionary
	return {}

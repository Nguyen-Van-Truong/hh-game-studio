class_name Maps
extends RefCounted

const TILE: int = 16
const COL_WORLD: int = 1
const COL_PLATFORM: int = 2
const COL_FIGHTER: int = 4
const COL_PICKUP: int = 8
const COL_HURT: int = 16
const COL_PROP: int = 32
const DESIGNED_VIEW: Vector2 = Vector2(1280, 720)
const WEAPON_RESPAWN: float = 20.0

const ATLAS_CONCRETE: Vector2i = Vector2i(0, 0)
const ATLAS_BRICK: Vector2i = Vector2i(1, 0)
const ATLAS_CRATE: Vector2i = Vector2i(2, 0)
const ATLAS_METAL: Vector2i = Vector2i(3, 0)
const ATLAS_POLICE: Vector2i = Vector2i(4, 0)
const ATLAS_PLATFORM: Vector2i = Vector2i(5, 0)
const ATLAS_HAZARD: Vector2i = Vector2i(6, 0)
const ATLAS_WALL: Vector2i = Vector2i(7, 0)
const TRAVERSAL_PATH: String = "res://data/sim/traversal.json"
const COMBAT_PATH: String = "res://data/sim/combat.json"
const AIM_PATH: String = "res://data/sim/aim.json"
const EXPLOSIVE_PATH: String = "res://data/sim/explosive.json"

static var _trav_cache: Dictionary = {}
static var _combat_cache: Dictionary = {}
static var _aim_cache: Dictionary = {}
static var _expl_cache: Dictionary = {}


static func _trav() -> Dictionary:
	if _trav_cache.is_empty():
		_trav_cache = SimConstants.load_json(TRAVERSAL_PATH)
	return _trav_cache


static func _combat() -> Dictionary:
	if _combat_cache.is_empty():
		_combat_cache = SimConstants.load_json(COMBAT_PATH)
	return _combat_cache


static func _aim() -> Dictionary:
	if _aim_cache.is_empty():
		_aim_cache = SimConstants.load_json(AIM_PATH)
	return _aim_cache


static func _expl() -> Dictionary:
	if _expl_cache.is_empty():
		_expl_cache = SimConstants.load_json(EXPLOSIVE_PATH)
	return _expl_cache


static func has_fixture(map_id: String) -> bool:
	return (
		_fixture_dict(_trav()).has(map_id)
		or _fixture_dict(_combat()).has(map_id)
		or _fixture_dict(_aim()).has(map_id)
		or _fixture_dict(_expl()).has(map_id)
	)


static func fixture_grid(map_id: String) -> PackedStringArray:
	var out: PackedStringArray = _grid_from(_trav(), map_id)
	if out.is_empty():
		out = _grid_from(_combat(), map_id)
	if out.is_empty():
		out = _grid_from(_aim(), map_id)
	if out.is_empty():
		out = _grid_from(_expl(), map_id)
	return out


static func fixture_name(map_id: String) -> String:
	var names: Dictionary = _name_dict(_trav())
	if names.has(map_id):
		return str(names.get(map_id, map_id))
	names = _name_dict(_combat())
	if names.has(map_id):
		return str(names.get(map_id, map_id))
	names = _name_dict(_aim())
	if names.has(map_id):
		return str(names.get(map_id, map_id))
	names = _name_dict(_expl())
	if names.has(map_id):
		return str(names.get(map_id, map_id))
	return map_id


static func _fixture_dict(payload: Dictionary) -> Dictionary:
	var raw: Variant = payload.get("fixtures", {})
	if raw is Dictionary:
		return raw as Dictionary
	return {}


static func _name_dict(payload: Dictionary) -> Dictionary:
	var raw: Variant = payload.get("fixture_names", {})
	if raw is Dictionary:
		return raw as Dictionary
	return {}


static func _grid_from(payload: Dictionary, map_id: String) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	var rows: Variant = _fixture_dict(payload).get(map_id, [])
	if rows is Array:
		var arr: Array = rows as Array
		var i: int = 0
		while i < arr.size():
			out.append(str(arr[i]))
			i += 1
	return out


static func display_name(map_id: String) -> String:
	if has_fixture(map_id):
		return fixture_name(map_id)
	if map_id == "rooftops":
		return "Rooftops"
	if map_id == "storage":
		return "Storage"
	if map_id == "police":
		return "Police Station"
	if map_id == "hazardous":
		return "Hazardous"
	return map_id


static func stage_ids() -> PackedStringArray:
	return PackedStringArray(["rooftops", "storage", "police", "hazardous"])


static func next_vs_map(map_id: String) -> String:
	var ids: PackedStringArray = stage_ids()
	var i: int = 0
	while i < ids.size():
		if String(ids[i]) == map_id:
			return String(ids[(i + 1) % ids.size()])
		i += 1
	return "rooftops"


static func stage_count() -> int:
	return 4


static func stage_map_at(index: int) -> String:
	var ids: PackedStringArray = stage_ids()
	if index < 0:
		return "rooftops"
	if index >= ids.size():
		return String(ids[ids.size() - 1])
	return String(ids[index])


static func grid(map_id: String) -> PackedStringArray:
	if has_fixture(map_id):
		return fixture_grid(map_id)
	if map_id == "storage":
		return _storage()
	if map_id == "police":
		return _police()
	if map_id == "hazardous":
		return _hazardous()
	return _rooftops()


static func tile_size(map_id: String) -> Vector2i:
	var rows: PackedStringArray = grid(map_id)
	var h: int = rows.size()
	var w: int = 0
	if h > 0:
		w = String(rows[0]).length()
	return Vector2i(w, h)


static func pixel_size(map_id: String) -> Vector2:
	var cells: Vector2i = tile_size(map_id)
	return Vector2(float(cells.x * TILE), float(cells.y * TILE))


static func kill_y(map_id: String) -> float:
	return pixel_size(map_id).y + 20.0


static func _rooftops() -> PackedStringArray:
	# Three buildings + gaps (pits) + ladders + jump-throughs. Echoes Y8 Rooftops.
	return PackedStringArray([
		"................................................................",
		"................................................................",
		".......##................................................##.....",
		".......##......................##........................##.....",
		"......####..........w..........##...........w...........####....",
		"...............========..................========...............",
		"................................................................",
		"....P.......................1.........................2.........",
		"..H#######............#H############............H#######........",
		"..H#######............#H############............H#######........",
		"..H#######......w.....#H...........#......w.....#H.....#........",
		"..H#######............#H############............H#######........",
		"..H#######............#H############............H#######........",
		"..H#######............#H############............H#######........",
		"................................................................",
		"................................................................",
	])


static func _storage() -> PackedStringArray:
	# Enclosed warehouse, crate stacks, catwalks, ladders. Echoes Y8 Storage.
	return PackedStringArray([
		"################################################################",
		"#..............................................................#",
		"#......========............................========............#",
		"#..H......................................................H....#",
		"#....cccc............w.................w...........cccc........#",
		"#....cccc..........................................cccc........#",
		"#..............========........========........................#",
		"#..............H................H..............................#",
		"#..P....cccc..............1..............cccc..............2...#",
		"#.......cccc.............................cccc..................#",
		"#..............................................................#",
		"################################################################",
	])


static func _police() -> PackedStringArray:
	# Left pit, two-floor station with walkable ground, ladders, right tower.
	return PackedStringArray([
		"................................................................",
		"......................................................####......",
		"......................................................#H.#......",
		".........................................w............#..#......",
		"......................................========........####......",
		".....................##########################.......#..#......",
		".....................#..........w....H........#.......#H.#......",
		".....................#....====.......H.====...#.......####......",
		"..............w......#...............H........#.......#..#......",
		".........========....#..cccc.........H.cccc...#.......#H.#......",
		".....................#..cccc.........H.cccc...#.......####......",
		"......P..........1...#...............H........#....2............",
		"......##########################################################",
		"......##########################################################",
		"................................................................",
		"................................................................",
	])


static func _hazardous() -> PackedStringArray:
	# Isolated pipes over a wide pit, ladders, jump-throughs. Echoes Y8 Hazardous.
	return PackedStringArray([
		"................................................................",
		"................................................................",
		"........========............................========............",
		"............w....................................w..............",
		"....bbbb................========......................bbbb......",
		"....H.....................................................H.....",
		"========................w................w..............========",
		"................................................................",
		"....P...............1...............========................2...",
		"...=======.........=======..............................=======.",
		"..............bbbb................................bbbb..........",
		"..............H......................................H..........",
		"................................................................",
		"................................................................",
		"................................................................",
		"................................................................",
	])


static func atlas_for(map_id: String, ch: String) -> Vector2i:
	if ch == "=":
		return ATLAS_PLATFORM
	if ch == "c":
		return ATLAS_CRATE
	if ch == "b":
		return ATLAS_HAZARD
	if map_id == "rooftops":
		return ATLAS_BRICK
	if map_id == "storage":
		return ATLAS_CONCRETE
	if map_id == "police":
		if ch == "#":
			return ATLAS_POLICE
		return ATLAS_CONCRETE
	return ATLAS_METAL


static func is_solid(ch: String) -> bool:
	return ch == "#" or ch == "c" or ch == "b"


static func solid_at(map_id: String, world_pos: Vector2) -> bool:
	var rows: PackedStringArray = grid(map_id)
	var cx: int = int(floor(world_pos.x / float(TILE)))
	var cy: int = int(floor(world_pos.y / float(TILE)))
	if cy < 0 or cy >= rows.size():
		return false
	var row: String = String(rows[cy])
	if cx < 0 or cx >= row.length():
		return false
	return is_solid(row.substr(cx, 1))


static func is_platform(ch: String) -> bool:
	return ch == "="


static func is_ladder(ch: String) -> bool:
	return ch == "H"


static func count_char(map_id: String, ch: String) -> int:
	var rows: PackedStringArray = grid(map_id)
	var n: int = 0
	var y: int = 0
	while y < rows.size():
		var row: String = String(rows[y])
		var x: int = 0
		while x < row.length():
			if row.substr(x, 1) == ch:
				n += 1
			x += 1
		y += 1
	return n


static func pit_column_count(map_id: String) -> int:
	var rows: PackedStringArray = grid(map_id)
	if rows.size() < 2:
		return 0
	var w: int = String(rows[0]).length()
	var h: int = rows.size()
	var n: int = 0
	var x: int = 0
	while x < w:
		var bottom: String = String(rows[h - 1]).substr(x, 1)
		var above: String = String(rows[h - 2]).substr(x, 1)
		if bottom == "." and above == ".":
			n += 1
		x += 1
	return n


static func spawn_floor_solid(map_id: String) -> bool:
	var rows: PackedStringArray = grid(map_id)
	var y: int = 0
	while y < rows.size():
		var row: String = String(rows[y])
		var x: int = 0
		while x < row.length():
			var ch: String = row.substr(x, 1)
			if ch == "P" or ch == "1" or ch == "2":
				var found: bool = false
				var dy: int = 1
				while dy <= 6 and y + dy < rows.size():
					var under: String = String(rows[y + dy]).substr(x, 1)
					if is_solid(under) or is_platform(under):
						found = true
						break
					dy += 1
				if not found:
					return false
			x += 1
		y += 1
	return true


static func police_interior_floor_solid() -> bool:
	var rows: PackedStringArray = _police()
	if rows.size() < 13:
		return false
	var floor_row: String = String(rows[12])
	var x: int = 22
	while x < 46:
		if floor_row.substr(x, 1) != "#":
			return false
		x += 1
	return true

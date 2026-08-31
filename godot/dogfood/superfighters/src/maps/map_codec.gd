class_name MapCodec
extends RefCounted

## Layered map codec (VF5-WP1). ASCII is import/export only.
## ledger:RL-MAP-LAYERS (assumption). Not a Y8 observation.

const LAYERS_ID: String = "vf.maps.layers.v1"
const LAYER_NAMES: PackedStringArray = [
	"solid", "one_way", "ladder", "hazard", "prop", "spawn", "pickup"
]


static func empty_doc(map_id: String, width: int, height: int, display_name: String, theme: String) -> Dictionary:
	return {
		"schema": LAYERS_ID,
		"schema_version": 1,
		"title": "Vault Fighters",
		"id": map_id,
		"display_name": display_name,
		"width": width,
		"height": height,
		"tile": 16,
		"theme": theme,
		"y8_parity_claimed": false,
		"original_exact_numbers_claimed": false,
		"values_are_tuning": true,
		"ascii_source_retired": true,
		"live_c_b_tiles": true,
		"layers": _empty_layers(),
	}


static func _empty_layers() -> Dictionary:
	return {
		"solid": [],
		"one_way": [],
		"ladder": [],
		"hazard": [],
		"prop": [],
		"spawn": [],
		"pickup": [],
	}


static func normalize(doc: Dictionary) -> Dictionary:
	var out: Dictionary = empty_doc(
		str(doc.get("id", "")),
		int(doc.get("width", 0)),
		int(doc.get("height", 0)),
		str(doc.get("display_name", "")),
		str(doc.get("theme", "concrete"))
	)
	out["tile"] = int(doc.get("tile", 16))
	var src: Dictionary = _dict(doc.get("layers", {}))
	var layers: Dictionary = _empty_layers()
	var i: int = 0
	while i < LAYER_NAMES.size():
		var name: String = String(LAYER_NAMES[i])
		layers[name] = _sorted_cells(src.get(name, []), name == "spawn")
		i += 1
	out["layers"] = layers
	return out


static func from_ascii(map_id: String, rows: PackedStringArray, display_name: String = "", theme: String = "") -> Dictionary:
	var height: int = rows.size()
	var width: int = 0
	if height > 0:
		width = String(rows[0]).length()
	if display_name == "":
		display_name = map_id
	if theme == "":
		theme = theme_for(map_id)
	var doc: Dictionary = empty_doc(map_id, width, height, display_name, theme)
	var layers: Dictionary = _empty_layers()
	var y: int = 0
	while y < height:
		var row: String = String(rows[y])
		var x: int = 0
		while x < row.length():
			var ch: String = row.substr(x, 1)
			if ch == "#":
				(layers["solid"] as Array).append([x, y])
			elif ch == "=":
				(layers["one_way"] as Array).append([x, y])
			elif ch == "H":
				(layers["ladder"] as Array).append([x, y])
			elif ch == "L":
				(layers["ladder"] as Array).append([x, y])
				(layers["one_way"] as Array).append([x, y])
			elif ch == "c":
				(layers["prop"] as Array).append([x, y])
			elif ch == "b":
				(layers["hazard"] as Array).append([x, y])
			elif ch == "P":
				(layers["spawn"] as Array).append([x, y, 0])
			elif ch == "1":
				(layers["spawn"] as Array).append([x, y, 1])
			elif ch == "2":
				(layers["spawn"] as Array).append([x, y, 2])
			elif ch == "3":
				(layers["spawn"] as Array).append([x, y, 3])
			elif ch == "w":
				(layers["pickup"] as Array).append([x, y])
			x += 1
		y += 1
	doc["layers"] = layers
	return normalize(doc)


static func to_ascii(doc: Dictionary) -> PackedStringArray:
	var width: int = int(doc.get("width", 0))
	var height: int = int(doc.get("height", 0))
	var rows: PackedStringArray = PackedStringArray()
	if width <= 0 or height <= 0:
		return rows
	var grid: Array = []
	var y: int = 0
	while y < height:
		var line: Array = []
		var x: int = 0
		while x < width:
			line.append(".")
			x += 1
		grid.append(line)
		y += 1
	_stamp_xy(grid, _dict(doc.get("layers", {})).get("solid", []), "#")
	_stamp_xy(grid, _dict(doc.get("layers", {})).get("one_way", []), "=")
	_stamp_xy(grid, _dict(doc.get("layers", {})).get("hazard", []), "b")
	_stamp_xy(grid, _dict(doc.get("layers", {})).get("prop", []), "c")
	_stamp_xy(grid, _dict(doc.get("layers", {})).get("ladder", []), "H")
	var decks: Array = _as_array(_dict(doc.get("layers", {})).get("one_way", []))
	var ladders: Array = _as_array(_dict(doc.get("layers", {})).get("ladder", []))
	var d: int = 0
	while d < decks.size():
		var deck: Array = _as_array(decks[d])
		if deck.size() >= 2:
			var dx: int = int(deck[0])
			var dy: int = int(deck[1])
			var li: int = 0
			while li < ladders.size():
				var lad: Array = _as_array(ladders[li])
				if lad.size() >= 2 and int(lad[0]) == dx and int(lad[1]) == dy:
					if dy >= 0 and dy < height and dx >= 0 and dx < width:
						(grid[dy] as Array)[dx] = "L"
					break
				li += 1
		d += 1
	_stamp_xy(grid, _dict(doc.get("layers", {})).get("pickup", []), "w")
	var spawns: Array = _as_array(_dict(doc.get("layers", {})).get("spawn", []))
	var s: int = 0
	while s < spawns.size():
		var cell: Array = _as_array(spawns[s])
		if cell.size() >= 3:
			var sx: int = int(cell[0])
			var sy: int = int(cell[1])
			var slot: int = int(cell[2])
			var mark: String = "P"
			if slot == 1:
				mark = "1"
			elif slot == 2:
				mark = "2"
			elif slot == 3:
				mark = "3"
			if sy >= 0 and sy < height and sx >= 0 and sx < width:
				(grid[sy] as Array)[sx] = mark
		s += 1
	y = 0
	while y < height:
		var text: String = ""
		var line: Array = grid[y] as Array
		var cx: int = 0
		while cx < line.size():
			text += str(line[cx])
			cx += 1
		rows.append(text)
		y += 1
	return rows


static func serialize(doc: Dictionary) -> String:
	return JSON.stringify(normalize(doc))


static func deserialize(raw: Variant) -> Dictionary:
	if raw is Dictionary:
		return normalize(raw as Dictionary)
	if raw is String:
		var parsed: Variant = JSON.parse_string(raw as String)
		if parsed is Dictionary:
			return normalize(parsed as Dictionary)
	return {}


static func stable_hash(doc: Dictionary) -> String:
	var ctx: HashingContext = HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(SimSnapshot.canonical(normalize(doc)).to_utf8_buffer())
	return ctx.finish().hex_encode()


static func theme_for(map_id: String) -> String:
	if map_id == "rooftops":
		return "brick"
	if map_id == "police":
		return "police"
	if map_id == "hazardous":
		return "metal"
	if map_id == "lantern":
		return "asphalt"
	if map_id == "gauge":
		return "range"
	return "concrete"


static func atlas_for(theme: String, layer: String) -> Vector2i:
	if layer == "one_way":
		return Maps.ATLAS_PLATFORM
	if layer == "prop":
		return Maps.ATLAS_CRATE
	if layer == "hazard":
		return Maps.ATLAS_HAZARD
	if theme == "brick":
		return Maps.ATLAS_BRICK
	if theme == "police":
		return Maps.ATLAS_POLICE
	if theme == "metal":
		return Maps.ATLAS_METAL
	if theme == "asphalt":
		return Maps.ATLAS_BRICK
	if theme == "range":
		return Maps.ATLAS_CONCRETE
	return Maps.ATLAS_CONCRETE


static func layer_cells(doc: Dictionary, layer: String) -> Array:
	return _as_array(_dict(doc.get("layers", {})).get(layer, []))


static func has_xy(doc: Dictionary, layer: String, x: int, y: int) -> bool:
	var cells: Array = layer_cells(doc, layer)
	var i: int = 0
	while i < cells.size():
		var cell: Array = _as_array(cells[i])
		if cell.size() >= 2 and int(cell[0]) == x and int(cell[1]) == y:
			return true
		i += 1
	return false


static func is_blocker(doc: Dictionary, x: int, y: int) -> bool:
	return (
		has_xy(doc, "solid", x, y)
		or has_xy(doc, "one_way", x, y)
		or has_xy(doc, "prop", x, y)
		or has_xy(doc, "hazard", x, y)
	)


static func is_walk_support(doc: Dictionary, x: int, y: int) -> bool:
	return is_blocker(doc, x, y)


static func in_bounds(doc: Dictionary, x: int, y: int) -> bool:
	return x >= 0 and y >= 0 and x < int(doc.get("width", 0)) and y < int(doc.get("height", 0))


static func _stamp_xy(grid: Array, raw: Variant, ch: String) -> void:
	var cells: Array = _as_array(raw)
	var i: int = 0
	while i < cells.size():
		var cell: Array = _as_array(cells[i])
		if cell.size() >= 2:
			var x: int = int(cell[0])
			var y: int = int(cell[1])
			if y >= 0 and y < grid.size():
				var line: Array = grid[y] as Array
				if x >= 0 and x < line.size():
					line[x] = ch
		i += 1


static func _sorted_cells(raw: Variant, with_slot: bool) -> Array:
	var cells: Array = _as_array(raw)
	var out: Array = []
	var i: int = 0
	while i < cells.size():
		var cell: Array = _as_array(cells[i])
		if cell.size() >= 2:
			var row: Array = [int(cell[0]), int(cell[1])]
			if with_slot:
				var slot: int = 0
				if cell.size() >= 3:
					slot = int(cell[2])
				row.append(slot)
			out.append(row)
		i += 1
	out.sort_custom(_cell_less)
	return out


static func _cell_less(a: Array, b: Array) -> bool:
	if int(a[1]) != int(b[1]):
		return int(a[1]) < int(b[1])
	if int(a[0]) != int(b[0]):
		return int(a[0]) < int(b[0])
	if a.size() > 2 and b.size() > 2:
		return int(a[2]) < int(b[2])
	return false


static func _as_array(value: Variant) -> Array:
	if value is Array:
		return value as Array
	return []


static func _dict(value: Variant) -> Dictionary:
	if value is Dictionary:
		return value as Dictionary
	return {}

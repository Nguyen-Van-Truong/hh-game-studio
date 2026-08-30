class_name MapValidator
extends RefCounted

## Topology validator (VF5-WP1): width, connectivity, spawn, pit,
## camera, overlapping blockers. ledger:RL-MAP-VALID (assumption).

const _MapCatalog: GDScript = preload("res://src/maps/map_catalog.gd")
const _MapCodec: GDScript = preload("res://src/maps/map_codec.gd")
const _MapGraph: GDScript = preload("res://src/maps/map_graph.gd")
const _ArenaSpec: GDScript = preload("res://src/maps/arena_spec.gd")

static func validate_doc(doc: Dictionary, require_pit: bool = false, require_routes: bool = true) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	_append(errors, _schema(doc))
	_append(errors, _width(doc))
	_append(errors, _overlap(doc))
	_append(errors, _spawns(doc))
	_append(errors, _camera(doc))
	_append(errors, _pits(doc, require_pit))
	if require_routes:
		_append(errors, _MapGraph.missing_platforms(doc))
	return errors


static func validate_map(map_id: String) -> PackedStringArray:
	var doc: Dictionary = _MapCatalog.document(map_id)
	if doc.is_empty():
		return PackedStringArray(["missing map %s" % map_id])
	var require_pit: bool = false
	var hazards: PackedStringArray = _ArenaSpec.hazards_of(map_id)
	if hazards.has("pit"):
		require_pit = true
	var require_routes: bool = _MapCatalog.has_id(map_id)
	return validate_doc(doc, require_pit, require_routes)


static func validate_catalog() -> PackedStringArray:
	var errors: PackedStringArray = _MapCatalog.validate()
	var ids: PackedStringArray = _MapCatalog.ids()
	var i: int = 0
	while i < ids.size():
		_append(errors, validate_map(String(ids[i])))
		i += 1
	return errors


static func broken_width() -> Dictionary:
	var doc: Dictionary = _MapCodec.empty_doc("fx_map_broken_width", 8, 6, "Broken Width", "concrete")
	var layers: Dictionary = doc["layers"] as Dictionary
	(layers["solid"] as Array).append([0, 5])
	(layers["solid"] as Array).append([9, 5])
	(layers["spawn"] as Array).append([1, 4, 0])
	return _MapCodec.normalize(doc)


static func broken_overlap() -> Dictionary:
	var doc: Dictionary = _MapCodec.empty_doc("fx_map_broken_overlap", 12, 8, "Broken Overlap", "concrete")
	var layers: Dictionary = doc["layers"] as Dictionary
	var x: int = 0
	while x < 12:
		(layers["solid"] as Array).append([x, 7])
		x += 1
	(layers["one_way"] as Array).append([4, 7])
	(layers["spawn"] as Array).append([2, 6, 0])
	return _MapCodec.normalize(doc)


static func broken_spawn() -> Dictionary:
	var doc: Dictionary = _MapCodec.empty_doc("fx_map_broken_spawn", 12, 8, "Broken Spawn", "concrete")
	var layers: Dictionary = doc["layers"] as Dictionary
	var x: int = 0
	while x < 12:
		(layers["solid"] as Array).append([x, 7])
		x += 1
	(layers["spawn"] as Array).append([2, 0, 0])
	return _MapCodec.normalize(doc)


static func broken_camera() -> Dictionary:
	var doc: Dictionary = _MapCodec.empty_doc("fx_map_broken_camera", 90, 8, "Broken Camera", "concrete")
	var layers: Dictionary = doc["layers"] as Dictionary
	var x: int = 0
	while x < 90:
		(layers["solid"] as Array).append([x, 7])
		x += 1
	(layers["spawn"] as Array).append([2, 6, 0])
	return _MapCodec.normalize(doc)


static func broken_graph() -> Dictionary:
	var doc: Dictionary = _MapCodec.empty_doc("fx_map_broken_graph", 16, 8, "Broken Graph", "concrete")
	var layers: Dictionary = doc["layers"] as Dictionary
	var x: int = 0
	while x < 4:
		(layers["solid"] as Array).append([x, 7])
		x += 1
	x = 14
	while x < 16:
		(layers["solid"] as Array).append([x, 3])
		x += 1
	(layers["spawn"] as Array).append([1, 6, 0])
	return _MapCodec.normalize(doc)


static func _schema(doc: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	if str(doc.get("schema", "")) != _MapCodec.LAYERS_ID:
		errors.append("map layers schema mismatch")
	if str(doc.get("title", "")) != "Vault Fighters":
		errors.append("map title must be Vault Fighters")
	if str(doc.get("title", "")).to_lower().contains("superfighter"):
		errors.append("map title uses Superfighters trademark")
	if str(doc.get("display_name", "")).to_lower().contains("superfighter"):
		errors.append("map display name uses Superfighters trademark")
	if bool(doc.get("y8_parity_claimed", true)):
		errors.append("map must not claim Y8 parity")
	return errors


static func _width(doc: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var limits: Dictionary = _dict(_MapCatalog.schema().get("limits", {}))
	var width: int = int(doc.get("width", 0))
	var height: int = int(doc.get("height", 0))
	if width < int(limits.get("width_min", 8)) or width > int(limits.get("width_max", 96)):
		errors.append("%s width %d outside limits" % [str(doc.get("id", "")), width])
	if height < int(limits.get("height_min", 6)) or height > int(limits.get("height_max", 48)):
		errors.append("%s height %d outside limits" % [str(doc.get("id", "")), height])
	var names: PackedStringArray = _MapCodec.LAYER_NAMES
	var i: int = 0
	while i < names.size():
		var layer: String = String(names[i])
		var cells: Array = _MapCodec.layer_cells(doc, layer)
		var c: int = 0
		while c < cells.size():
			var cell: Array = _as_array(cells[c])
			if cell.size() >= 2:
				var x: int = int(cell[0])
				var y: int = int(cell[1])
				if not _MapCodec.in_bounds(doc, x, y):
					errors.append("%s %s cell %d,%d out of bounds" % [str(doc.get("id", "")), layer, x, y])
			c += 1
		i += 1
	return errors


static func _overlap(doc: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var blockers: PackedStringArray = PackedStringArray(["solid", "one_way", "hazard", "prop"])
	var seen: Dictionary = {}
	var i: int = 0
	while i < blockers.size():
		var layer: String = String(blockers[i])
		var cells: Array = _MapCodec.layer_cells(doc, layer)
		var c: int = 0
		while c < cells.size():
			var cell: Array = _as_array(cells[c])
			if cell.size() >= 2:
				var key: String = "%d,%d" % [int(cell[0]), int(cell[1])]
				if seen.has(key):
					errors.append(
						"%s overlapping blockers at %s (%s/%s)"
						% [str(doc.get("id", "")), key, str(seen[key]), layer]
					)
				else:
					seen[key] = layer
			c += 1
		i += 1
	var ladders: Array = _MapCodec.layer_cells(doc, "ladder")
	i = 0
	while i < ladders.size():
		var cell: Array = _as_array(ladders[i])
		if cell.size() >= 2:
			var x: int = int(cell[0])
			var y: int = int(cell[1])
			if _MapCodec.has_xy(doc, "solid", x, y) or _MapCodec.has_xy(doc, "prop", x, y) or _MapCodec.has_xy(doc, "hazard", x, y):
				errors.append("%s ladder overlaps blocker at %d,%d" % [str(doc.get("id", "")), x, y])
		i += 1
	return errors


static func _spawns(doc: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var spawns: Array = _MapCodec.layer_cells(doc, "spawn")
	if spawns.is_empty():
		errors.append("%s has no spawn marks" % str(doc.get("id", "")))
		return errors
	var i: int = 0
	while i < spawns.size():
		var cell: Array = _as_array(spawns[i])
		if cell.size() < 3:
			errors.append("%s spawn missing slot" % str(doc.get("id", "")))
			i += 1
			continue
		var x: int = int(cell[0])
		var y: int = int(cell[1])
		if _MapCodec.is_blocker(doc, x, y):
			errors.append("%s spawn %d inside blocker" % [str(doc.get("id", "")), int(cell[2])])
		if _pit_column(doc, x) and not _has_floor_below(doc, x, y):
			errors.append("%s spawn %d in pit column %d" % [str(doc.get("id", "")), int(cell[2]), x])
		if not _has_floor_below(doc, x, y):
			errors.append("%s spawn %d has no walkable floor" % [str(doc.get("id", "")), int(cell[2])])
		i += 1
	return errors


static func _camera(doc: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var view: Dictionary = _dict(_MapCatalog.schema().get("designed_view", {}))
	var tile: int = int(doc.get("tile", 16))
	var px: int = int(doc.get("width", 0)) * tile
	var py: int = int(doc.get("height", 0)) * tile
	var vx: int = int(view.get("x", 1280))
	var vy: int = int(view.get("y", 720))
	if px > vx or py > vy:
		errors.append(
			"%s pixel size %dx%d exceeds camera %dx%d"
			% [str(doc.get("id", "")), px, py, vx, vy]
		)
	return errors


static func _pits(doc: Dictionary, require_pit: bool) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var n: int = pit_column_count(doc)
	if require_pit and n < 1:
		errors.append("%s must declare a pit boundary" % str(doc.get("id", "")))
	return errors


static func pit_column_count(doc: Dictionary) -> int:
	var width: int = int(doc.get("width", 0))
	var height: int = int(doc.get("height", 0))
	if height < 2:
		return 0
	var n: int = 0
	var x: int = 0
	while x < width:
		if _pit_column(doc, x):
			n += 1
		x += 1
	return n


static func _pit_column(doc: Dictionary, x: int) -> bool:
	var height: int = int(doc.get("height", 0))
	if height < 2:
		return false
	return (
		not _MapCodec.is_blocker(doc, x, height - 1)
		and not _MapCodec.is_blocker(doc, x, height - 2)
	)


static func _has_floor_below(doc: Dictionary, x: int, y: int) -> bool:
	var dy: int = 1
	while dy <= 6:
		if _MapCodec.is_walk_support(doc, x, y + dy):
			return true
		dy += 1
	return false


static func _as_array(value: Variant) -> Array:
	if value is Array:
		return value as Array
	return []


static func _dict(value: Variant) -> Dictionary:
	if value is Dictionary:
		return value as Dictionary
	return {}


static func _append(target: PackedStringArray, extra: PackedStringArray) -> void:
	var i: int = 0
	while i < extra.size():
		target.append(String(extra[i]))
		i += 1

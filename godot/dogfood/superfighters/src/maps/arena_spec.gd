class_name ArenaSpec
extends RefCounted

## Per-map hazard contract (VF4-WP5) plus VF5-WP1 layered source.
## ledger:RL-ENV-ARENA / RL-MAP-LAYERS (assumption).

const PATH: String = "res://data/maps/arena_spec.json"
const SCHEMA_ID: String = "vf.maps.arena.v1"
const _Env: GDScript = preload("res://src/world/env_spec.gd")
const _MapCatalog: GDScript = preload("res://src/maps/map_catalog.gd")
const _MapCodec: GDScript = preload("res://src/maps/map_codec.gd")

static var _cache: Dictionary = {}


static func data() -> Dictionary:
	if _cache.is_empty():
		_cache = SimConstants.load_json(PATH)
	return _cache


static func maps() -> Dictionary:
	return _dict(data().get("maps", {}))


static func map_row(map_id: String) -> Dictionary:
	return _dict(maps().get(map_id, {}))


static func hazards_of(map_id: String) -> PackedStringArray:
	return _to_packed(map_row(map_id).get("hazards", []))


static func fall_policy() -> Dictionary:
	return _dict(data().get("fall", {}))


static func validate() -> PackedStringArray:
	return validate_payload(data())


static func validate_payload(row: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	if str(row.get("schema", "")) != SCHEMA_ID:
		errors.append("arena spec schema id mismatch")
	if str(row.get("title", "")) != "Vault Fighters":
		errors.append("arena spec title must be Vault Fighters")
	if bool(row.get("y8_parity_claimed", true)):
		errors.append("arena spec must not claim Y8 parity")
	if bool(row.get("original_exact_numbers_claimed", true)):
		errors.append("arena spec must not claim original exact numbers")
	if not bool(row.get("values_are_tuning", false)):
		errors.append("arena spec values must be marked tuning")
	if not bool(row.get("env_implemented", false)):
		errors.append("arena spec env contract must be implemented")
	if bool(row.get("ascii_maps_kept", true)):
		errors.append("arena spec ASCII source must be retired")
	if not bool(row.get("layered_maps", false)):
		errors.append("arena spec must use layered maps")
	if not bool(row.get("live_c_b_tiles", false)):
		errors.append("live c/b tiles must stay tiles")
	if str(row.get("arena_class", "")) != "assumption":
		errors.append("arena spec must stay assumption")
	if str(row.get("spawn_class", "")) != "assumption":
		errors.append("spawn safety must stay assumption")
	if str(row.get("fall_class", "")) != "assumption":
		errors.append("fall policy must stay assumption")
	if str(row.get("nade_prop_class", "")) != "deferred":
		errors.append("RL-NADE-PROP must stay deferred")
	if str(row.get("hold_to_aim_class", "")) != "assumption":
		errors.append("hold-to-aim must stay assumption")
	if str(row.get("roll_dive_class", "")) != "unavailable":
		errors.append("Y8 roll/dive observation must stay unavailable")
	if str(row.get("title", "")).to_lower().contains("superfighter"):
		errors.append("arena spec title uses Superfighters trademark")
	var fall: Dictionary = _dict(row.get("fall", {}))
	if float(fall.get("drop_min", 0.0)) < 28.0:
		errors.append("fall drop_min must stay >= 28")
	if float(fall.get("damage", 0.0)) <= 0.0:
		errors.append("fall damage must be > 0")
	if not bool(fall.get("dive_immune", false)):
		errors.append("dive immunity must stay selected")
	if not bool(fall.get("pit_not_cancelled_by_dive", false)):
		errors.append("dive must not cancel pit death")
	var all_maps: Dictionary = _dict(row.get("maps", {}))
	var required: PackedStringArray = PackedStringArray([
		"rooftops", "storage", "police", "hazardous",
		"lantern", "gauge",
		"fx_env_instant", "fx_env_toxic", "fx_env_water",
		"fx_env_rotor", "fx_env_fall", "fx_env_yard"
	])
	var i: int = 0
	while i < required.size():
		var mid: String = String(required[i])
		if not all_maps.has(mid):
			errors.append("arena spec missing map %s" % mid)
			i += 1
			continue
		var spec: Dictionary = _dict(all_maps.get(mid, {}))
		if str(spec.get("id", "")) != mid:
			errors.append("arena spec %s id mismatch" % mid)
		var dname: String = str(spec.get("display_name", ""))
		if dname == "" or dname.to_lower().contains("superfighter"):
			errors.append("arena spec %s display name invalid" % mid)
		var hazards: PackedStringArray = _to_packed(spec.get("hazards", []))
		if hazards.is_empty():
			errors.append("arena spec %s must list hazards" % mid)
		i += 1
	if not _to_packed(_dict(all_maps.get("rooftops", {})).get("hazards", [])).has("pit"):
		errors.append("rooftops must declare pit")
	if not _to_packed(_dict(all_maps.get("rooftops", {})).get("hazards", [])).has("fall"):
		errors.append("rooftops must declare fall")
	var roof: Dictionary = _dict(all_maps.get("rooftops", {}))
	if str(roof.get("display_name", "")) != "Skyline Relay":
		errors.append("rooftops display name must be Skyline Relay")
	if int(roof.get("elevations", 0)) < 3:
		errors.append("Skyline Relay must declare 3+ elevations")
	if combat_zones("rooftops").size() < 3:
		errors.append("Skyline Relay must list combat zones")
	if landmarks("rooftops").is_empty():
		errors.append("Skyline Relay must list landmarks")
	_append(errors, _validate_skyline_zones(roof))
	var annex: Dictionary = _dict(all_maps.get("storage", {}))
	if str(annex.get("display_name", "")) != "Pallet Annex":
		errors.append("storage display name must be Pallet Annex")
	if int(annex.get("elevations", 0)) < 3:
		errors.append("Pallet Annex must declare 3+ elevations")
	if combat_zones("storage").size() < 5:
		errors.append("Pallet Annex must list combat zones")
	if landmarks("storage").is_empty():
		errors.append("Pallet Annex must list landmarks")
	_append(errors, _validate_pallet_zones(annex))
	_append(errors, validate_weapon_cells_safe("storage"))
	var court: Dictionary = _dict(all_maps.get("police", {}))
	if str(court.get("display_name", "")) != "Signal Court":
		errors.append("police display name must be Signal Court")
	if int(court.get("elevations", 0)) < 3:
		errors.append("Signal Court must declare 3+ elevations")
	if combat_zones("police").size() < 6:
		errors.append("Signal Court must list combat zones")
	if landmarks("police").is_empty():
		errors.append("Signal Court must list landmarks")
	_append(errors, _validate_signal_zones(court))
	_append(errors, validate_weapon_cells_safe("police"))
	if not _to_packed(_dict(all_maps.get("police", {})).get("hazards", [])).has("pit"):
		errors.append("police must declare pit")
	if not _to_packed(_dict(all_maps.get("police", {})).get("hazards", [])).has("rotor"):
		errors.append("Signal Court must declare rotor")
	var sump: Dictionary = _dict(all_maps.get("hazardous", {}))
	if str(sump.get("display_name", "")) != "Vitriol Sump":
		errors.append("hazardous display name must be Vitriol Sump")
	if int(sump.get("elevations", 0)) < 3:
		errors.append("Vitriol Sump must declare 3+ elevations")
	if combat_zones("hazardous").size() < 6:
		errors.append("Vitriol Sump must list combat zones")
	if landmarks("hazardous").is_empty():
		errors.append("Vitriol Sump must list landmarks")
	_append(errors, _validate_sump_zones(sump))
	_append(errors, validate_weapon_cells_safe("hazardous"))
	if not _to_packed(sump.get("hazards", [])).has("pit"):
		errors.append("hazardous must declare pit")
	if not _to_packed(sump.get("hazards", [])).has("toxic"):
		errors.append("Vitriol Sump must declare toxic")
	var cut: Dictionary = _dict(all_maps.get("lantern", {}))
	if str(cut.get("display_name", "")) != "Lantern Cut":
		errors.append("lantern display name must be Lantern Cut")
	if int(cut.get("elevations", 0)) < 3:
		errors.append("Lantern Cut must declare 3+ elevations")
	if combat_zones("lantern").size() < 4:
		errors.append("Lantern Cut must list combat zones")
	if landmarks("lantern").is_empty():
		errors.append("Lantern Cut must list landmarks")
	_append(errors, _validate_named_zones(cut, "Lantern Cut", PackedStringArray([
		"west_high", "west_stoop", "clothesline", "east_stoop",
		"west_street", "east_street"
	])))
	_append(errors, validate_weapon_cells_safe("lantern"))
	if not _to_packed(cut.get("hazards", [])).has("pit"):
		errors.append("lantern must declare pit")
	if not _to_packed(cut.get("hazards", [])).has("water"):
		errors.append("Lantern Cut must declare water")
	var deck: Dictionary = _dict(all_maps.get("gauge", {}))
	if str(deck.get("display_name", "")) != "Gauge Deck":
		errors.append("gauge display name must be Gauge Deck")
	if int(deck.get("elevations", 0)) < 3:
		errors.append("Gauge Deck must declare 3+ elevations")
	if combat_zones("gauge").size() < 4:
		errors.append("Gauge Deck must list combat zones")
	if landmarks("gauge").is_empty():
		errors.append("Gauge Deck must list landmarks")
	_append(errors, _validate_named_zones(deck, "Gauge Deck", PackedStringArray([
		"west_loft", "west_rail", "west_floor", "mid_lane",
		"east_loft", "east_floor"
	])))
	_append(errors, validate_weapon_cells_safe("gauge"))
	if not _to_packed(deck.get("hazards", [])).has("pit"):
		errors.append("gauge must declare pit")
	if not _to_packed(_dict(all_maps.get("fx_env_instant", {})).get("hazards", [])).has("instant"):
		errors.append("Void Cut must declare instant")
	if not _to_packed(_dict(all_maps.get("fx_env_toxic", {})).get("hazards", [])).has("toxic"):
		errors.append("Acid Trench must declare toxic")
	if not _to_packed(_dict(all_maps.get("fx_env_water", {})).get("hazards", [])).has("water"):
		errors.append("Wash Channel must declare water")
	if not _to_packed(_dict(all_maps.get("fx_env_rotor", {})).get("hazards", [])).has("rotor"):
		errors.append("Mill Shaft must declare rotor")
	if not _to_packed(_dict(all_maps.get("fx_env_fall", {})).get("hazards", [])).has("fall"):
		errors.append("Drop Well must declare fall")
	_append(errors, validate_spawns_safe())
	return errors


static func combat_zones(map_id: String) -> Array:
	return _as_array(map_row(map_id).get("combat_zones", []))


static func landmarks(map_id: String) -> Array:
	return _as_array(map_row(map_id).get("landmarks", []))


static func weapon_risk(map_id: String) -> Array:
	return _as_array(map_row(map_id).get("weapon_risk", []))


static func zone_contains(zone: Dictionary, world_pos: Vector2) -> bool:
	var x0: float = float(int(zone.get("x", 0))) * float(Maps.TILE)
	var y0: float = float(int(zone.get("y", 0))) * float(Maps.TILE)
	var w: float = float(int(zone.get("w", 1))) * float(Maps.TILE)
	var h: float = float(int(zone.get("h", 1))) * float(Maps.TILE)
	var box: Rect2 = Rect2(x0 - 4.0, y0 - 12.0, w + 8.0, h + 20.0)
	return box.has_point(world_pos)


static func _validate_skyline_zones(roof: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var seen_y: Dictionary = {}
	var zones: Array = _as_array(roof.get("combat_zones", []))
	var i: int = 0
	while i < zones.size():
		var zone: Dictionary = _dict(zones[i])
		if str(zone.get("id", "")) == "":
			errors.append("Skyline Relay combat zone missing id")
		seen_y[int(zone.get("y", -1))] = true
		i += 1
	if seen_y.size() < 3:
		errors.append("Skyline Relay combat zones must span 3+ elevations")
	return errors


static func _validate_pallet_zones(annex: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var seen_y: Dictionary = {}
	var need: PackedStringArray = PackedStringArray([
		"west_floor", "mid_floor", "east_floor", "office_loft",
		"west_catwalk", "mid_catwalk", "east_catwalk"
	])
	var found: Dictionary = {}
	var zones: Array = _as_array(annex.get("combat_zones", []))
	var i: int = 0
	while i < zones.size():
		var zone: Dictionary = _dict(zones[i])
		var zid: String = str(zone.get("id", ""))
		if zid == "":
			errors.append("Pallet Annex combat zone missing id")
		found[zid] = true
		seen_y[int(zone.get("y", -1))] = true
		i += 1
	i = 0
	while i < need.size():
		var zid: String = String(need[i])
		if not found.has(zid):
			errors.append("Pallet Annex missing combat zone %s" % zid)
		i += 1
	if seen_y.size() < 3:
		errors.append("Pallet Annex combat zones must span 3+ elevations")
	return errors


static func _validate_signal_zones(court: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var seen_y: Dictionary = {}
	var need: PackedStringArray = PackedStringArray([
		"court_mid", "court_low", "court_ground", "west_hall", "west_loft",
		"sky_bridge", "east_hall", "east_mid", "east_top"
	])
	var found: Dictionary = {}
	var zones: Array = _as_array(court.get("combat_zones", []))
	var i: int = 0
	while i < zones.size():
		var zone: Dictionary = _dict(zones[i])
		var zid: String = str(zone.get("id", ""))
		if zid == "":
			errors.append("Signal Court combat zone missing id")
		found[zid] = true
		seen_y[int(zone.get("y", -1))] = true
		i += 1
	i = 0
	while i < need.size():
		var zid: String = String(need[i])
		if not found.has(zid):
			errors.append("Signal Court missing combat zone %s" % zid)
		i += 1
	if seen_y.size() < 3:
		errors.append("Signal Court combat zones must span 3+ elevations")
	return errors


static func _validate_named_zones(
	row: Dictionary, label: String, need: PackedStringArray
) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var seen_y: Dictionary = {}
	var found: Dictionary = {}
	var zones: Array = _as_array(row.get("combat_zones", []))
	var i: int = 0
	while i < zones.size():
		var zone: Dictionary = _dict(zones[i])
		var zid: String = str(zone.get("id", ""))
		if zid == "":
			errors.append("%s combat zone missing id" % label)
		found[zid] = true
		seen_y[int(zone.get("y", -1))] = true
		i += 1
	i = 0
	while i < need.size():
		var zid: String = String(need[i])
		if not found.has(zid):
			errors.append("%s missing combat zone %s" % [label, zid])
		i += 1
	if seen_y.size() < 3:
		errors.append("%s combat zones must span 3+ elevations" % label)
	return errors


static func _validate_sump_zones(sump: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var seen_y: Dictionary = {}
	var need: PackedStringArray = PackedStringArray([
		"west_bank", "west_span", "west_high", "west_mid", "mid_west", "mid_east",
		"mid_low", "east_high", "east_bank", "sump_lip", "sump_wade"
	])
	var found: Dictionary = {}
	var zones: Array = _as_array(sump.get("combat_zones", []))
	var i: int = 0
	while i < zones.size():
		var zone: Dictionary = _dict(zones[i])
		var zid: String = str(zone.get("id", ""))
		if zid == "":
			errors.append("Vitriol Sump combat zone missing id")
		found[zid] = true
		seen_y[int(zone.get("y", -1))] = true
		i += 1
	i = 0
	while i < need.size():
		var zid: String = String(need[i])
		if not found.has(zid):
			errors.append("Vitriol Sump missing combat zone %s" % zid)
		i += 1
	if seen_y.size() < 3:
		errors.append("Vitriol Sump combat zones must span 3+ elevations")
	return errors


static func validate_weapon_cells_safe(map_id: String) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var doc: Dictionary = _MapCatalog.document(map_id)
	if doc.is_empty():
		errors.append("%s weapon safety missing layered doc" % map_id)
		return errors
	var cells: Array = _MapCodec.layer_cells(doc, "pickup")
	if cells.is_empty():
		errors.append("%s has no weapon cells" % map_id)
		return errors
	var i: int = 0
	while i < cells.size():
		var cell: Array = _as_array(cells[i])
		if cell.size() < 2:
			errors.append("%s weapon cell missing xy" % map_id)
			i += 1
			continue
		var x: int = int(cell[0])
		var y: int = int(cell[1])
		if _MapCodec.is_blocker(doc, x, y):
			errors.append("%s weapon %d,%d inside blocker" % [map_id, x, y])
		var floor_ok: bool = false
		var dy: int = 1
		while dy <= 6:
			if _MapCodec.is_walk_support(doc, x, y + dy):
				floor_ok = true
				break
			dy += 1
		if not floor_ok:
			errors.append("%s weapon %d,%d has no walkable floor" % [map_id, x, y])
		i += 1
	return errors


static func _as_array(value: Variant) -> Array:
	if value is Array:
		return value as Array
	return []


static func spawn_points(map_id: String) -> Array:
	var out: Array = []
	var rows: PackedStringArray = Maps.grid(map_id)
	var y: int = 0
	while y < rows.size():
		var row: String = String(rows[y])
		var x: int = 0
		while x < row.length():
			var ch: String = row.substr(x, 1)
			var slot: int = -1
			if ch == "P":
				slot = 0
			elif ch == "1":
				slot = 1
			elif ch == "2":
				slot = 2
			if slot >= 0:
				out.append({
					"slot": slot,
					"x": float(x * Maps.TILE) + float(Maps.TILE) * 0.5,
					"y": float(y * Maps.TILE) + float(Maps.TILE) * 0.5,
				})
			x += 1
		y += 1
	return out


static func validate_spawns_safe(map_id: String = "") -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var ids: PackedStringArray = PackedStringArray()
	if map_id != "":
		ids.append(map_id)
	else:
		var keys: Array = maps().keys()
		keys.sort()
		var k: int = 0
		while k < keys.size():
			ids.append(str(keys[k]))
			k += 1
	var i: int = 0
	while i < ids.size():
		var mid: String = String(ids[i])
		var spawns: Array = spawn_points(mid)
		if spawns.is_empty():
			errors.append("arena spec %s has no spawn marks" % mid)
			i += 1
			continue
		var places: Array = _Env.placements_for(mid)
		var s: int = 0
		while s < spawns.size():
			var spawn: Dictionary = spawns[s] as Dictionary
			var sx: float = float(spawn.get("x", 0.0))
			var sy: float = float(spawn.get("y", 0.0))
			var box: Rect2 = Rect2(sx - 6.0, sy - 14.0, 12.0, 24.0)
			var p: int = 0
			while p < places.size():
				var place: Dictionary = places[p] as Dictionary
				var spec: Dictionary = _Env.spec(str(place.get("spec", "")))
				var kind: String = str(spec.get("kind", ""))
				if kind != "zone_instant" and kind != "zone_toxic" and kind != "rotor":
					p += 1
					continue
				var w: float = float(_dict(spec.get("collision", {})).get("width", 0.0))
				var h: float = float(_dict(spec.get("collision", {})).get("height", 0.0))
				var hz: Rect2 = Rect2(
					float(place.get("x", 0.0)) - w * 0.5,
					float(place.get("y", 0.0)) - h * 0.5,
					w,
					h
				)
				if box.intersects(hz, false):
					errors.append(
						"spawn slot %d on %s overlaps %s"
						% [int(spawn.get("slot", -1)), mid, str(place.get("id", ""))]
					)
				p += 1
			s += 1
		i += 1
	return errors


static func _to_packed(value: Variant) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	if value is Array:
		var arr: Array = value as Array
		var i: int = 0
		while i < arr.size():
			out.append(str(arr[i]))
			i += 1
	elif value is PackedStringArray:
		return value as PackedStringArray
	return out


static func _dict(value: Variant) -> Dictionary:
	if value is Dictionary:
		return value as Dictionary
	return {}


static func _append(target: PackedStringArray, extra: PackedStringArray) -> void:
	var i: int = 0
	while i < extra.size():
		target.append(String(extra[i]))
		i += 1

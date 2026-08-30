class_name ArenaSpec
extends RefCounted

## Per-map hazard contract (VF4-WP5) plus VF5-WP1 layered source.
## ledger:RL-ENV-ARENA / RL-MAP-LAYERS (assumption).

const PATH: String = "res://data/maps/arena_spec.json"
const SCHEMA_ID: String = "vf.maps.arena.v1"
const _Env: GDScript = preload("res://src/world/env_spec.gd")

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
	if not _to_packed(_dict(all_maps.get("police", {})).get("hazards", [])).has("pit"):
		errors.append("police must declare pit")
	if not _to_packed(_dict(all_maps.get("hazardous", {})).get("hazards", [])).has("pit"):
		errors.append("hazardous must declare pit")
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

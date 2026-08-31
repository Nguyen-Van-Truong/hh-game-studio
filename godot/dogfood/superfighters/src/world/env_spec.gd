class_name EnvSpec
extends RefCounted

## Instant / deferred zones, water, rotor (VF4-WP5).
## ledger:RL-ENV-INSTANT / RL-ENV-DEFER / RL-ENV-WATER /
## RL-ENV-ROTOR (assumption). Not observed.
## Roll extinguish stays selected in hazard.json.
## Water extinguish is selected here. RL-NADE-PROP stays deferred.

const PATH: String = "res://data/world/env.json"
const SCHEMA_ID: String = "vf.world.env.v1"
const _Paths: GDScript = preload("res://src/world/world_paths.gd")
const _Spec: GDScript = preload("res://src/world/prop_spec.gd")

static var _cache: Dictionary = {}


static func data() -> Dictionary:
	if _cache.is_empty():
		_cache = SimConstants.load_json(PATH)
	return _cache


static func spec(spec_id: String) -> Dictionary:
	var specs: Dictionary = _dict(data().get("specs", {}))
	if specs.has(spec_id):
		return _dict(specs.get(spec_id, {}))
	return {}


static func placements_for(map_id: String) -> Array:
	var all: Dictionary = _dict(data().get("placements", {}))
	var raw: Variant = all.get(map_id, [])
	if raw is Array:
		return raw as Array
	return []


static func fixtures() -> Dictionary:
	return _dict(data().get("fixtures", {}))


static func fixture_names() -> Dictionary:
	return _dict(data().get("fixture_names", {}))


static func has_fixture(map_id: String) -> bool:
	return fixtures().has(map_id)


static func validate() -> PackedStringArray:
	return validate_payload(data())


static func validate_payload(row: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	if str(row.get("schema", "")) != SCHEMA_ID:
		errors.append("env schema id mismatch")
	if str(row.get("title", "")) != "Vault Fighters":
		errors.append("env title must be Vault Fighters")
	if bool(row.get("y8_parity_claimed", true)):
		errors.append("env must not claim Y8 parity")
	if bool(row.get("original_exact_numbers_claimed", true)):
		errors.append("env must not claim original exact numbers")
	if not bool(row.get("values_are_tuning", false)):
		errors.append("env values must be marked tuning")
	if not bool(row.get("env_implemented", false)):
		errors.append("env bodies must be implemented this WP")
	if not bool(row.get("water_extinguish", false)):
		errors.append("water extinguish must be selected this WP")
	if not bool(row.get("roll_extinguish_kept", false)):
		errors.append("roll extinguish must stay selected")
	if str(row.get("instant_class", "")) != "assumption":
		errors.append("instant zone must stay assumption")
	if str(row.get("defer_class", "")) != "assumption":
		errors.append("deferred toxic must stay assumption")
	if str(row.get("water_class", "")) != "assumption":
		errors.append("water must stay assumption")
	if str(row.get("rotor_class", "")) != "assumption":
		errors.append("rotor must stay assumption")
	if str(row.get("nade_prop_class", "")) != "deferred":
		errors.append("RL-NADE-PROP must stay deferred")
	if str(row.get("hold_to_aim_class", "")) != "assumption":
		errors.append("hold-to-aim must stay assumption")
	if str(row.get("roll_dive_class", "")) != "unavailable":
		errors.append("Y8 roll/dive observation must stay unavailable")
	if str(row.get("title", "")).to_lower().contains("superfighter"):
		errors.append("env title uses Superfighters trademark")
	if float(row.get("toxic_damage", 0.0)) <= 0.0:
		errors.append("toxic_damage must be > 0")
	if int(row.get("toxic_interval", 0)) < 1:
		errors.append("toxic_interval must be >= 1")
	if float(row.get("rotor_damage", 0.0)) <= 0.0:
		errors.append("rotor_damage must be > 0")
	if int(row.get("rotor_interval", 0)) < 1:
		errors.append("rotor_interval must be >= 1")
	var kinds: PackedStringArray = _to_packed(row.get("kinds", []))
	var required_kinds: PackedStringArray = PackedStringArray([
		"zone_instant", "zone_toxic", "zone_water", "rotor"
	])
	var k: int = 0
	while k < required_kinds.size():
		if not kinds.has(String(required_kinds[k])):
			errors.append("env missing kind %s" % String(required_kinds[k]))
		k += 1
	var specs: Dictionary = _dict(row.get("specs", {}))
	var seen: Dictionary = {}
	var keys: Array = specs.keys()
	keys.sort()
	var s: int = 0
	while s < keys.size():
		var sid: String = str(keys[s])
		var spec_row: Dictionary = _dict(specs.get(sid, {}))
		if str(spec_row.get("id", "")) != sid:
			errors.append("env spec %s id mismatch" % sid)
		var kind: String = str(spec_row.get("kind", ""))
		if not required_kinds.has(kind):
			errors.append("env spec %s kind %s is not allowed" % [sid, kind])
		seen[kind] = true
		var name_v: String = str(spec_row.get("name", ""))
		if name_v == "" or name_v.to_lower().contains("superfighter"):
			errors.append("env spec %s name invalid" % sid)
		var vpath: String = str(_dict(spec_row.get("visual", {})).get("path", ""))
		var path_err: String = str(_Paths.reject_reason(vpath))
		if path_err != "":
			errors.append("env spec %s visual %s" % [sid, path_err])
		s += 1
	k = 0
	while k < required_kinds.size():
		if not seen.has(String(required_kinds[k])):
			errors.append("env has no spec for kind %s" % String(required_kinds[k]))
		k += 1
	var fx: Dictionary = _dict(row.get("fixtures", {}))
	var names: Dictionary = _dict(row.get("fixture_names", {}))
	var need_fx: PackedStringArray = PackedStringArray([
		"fx_env_instant", "fx_env_toxic", "fx_env_water",
		"fx_env_rotor", "fx_env_fall", "fx_env_yard"
	])
	var f: int = 0
	while f < need_fx.size():
		var fid: String = String(need_fx[f])
		if not fx.has(fid):
			errors.append("env fixture %s missing" % fid)
		if str(names.get(fid, "")).to_lower().contains("superfighter"):
			errors.append("env fixture name uses Superfighters trademark")
		f += 1
	if str(names.get("fx_env_instant", "")) != "Void Cut":
		errors.append("instant fixture display name must be Void Cut")
	if str(names.get("fx_env_toxic", "")) != "Acid Trench":
		errors.append("toxic fixture display name must be Acid Trench")
	if str(names.get("fx_env_water", "")) != "Wash Channel":
		errors.append("water fixture display name must be Wash Channel")
	if str(names.get("fx_env_rotor", "")) != "Mill Shaft":
		errors.append("rotor fixture display name must be Mill Shaft")
	if str(names.get("fx_env_fall", "")) != "Drop Well":
		errors.append("fall fixture display name must be Drop Well")
	if str(names.get("fx_env_yard", "")) != "Hazard Yard":
		errors.append("yard fixture display name must be Hazard Yard")
	_append(errors, _validate_grids(fx))
	return errors


static func toxic_damage() -> float:
	return float(data().get("toxic_damage", 12.0))


static func toxic_interval() -> int:
	return maxi(int(data().get("toxic_interval", 8)), 1)


static func rotor_damage() -> float:
	return float(data().get("rotor_damage", 8.0))


static func rotor_interval() -> int:
	return maxi(int(data().get("rotor_interval", 10)), 1)


static func rotor_deg() -> float:
	return float(data().get("rotor_deg_per_tick", 6.0))


static func water_extinguish() -> bool:
	return bool(data().get("water_extinguish", true))


static func wet_walk_mul() -> float:
	return clampf(float(data().get("wet_walk_mul", 0.55)), 0.2, 0.9)


static func wet_jump_mul() -> float:
	return clampf(float(data().get("wet_jump_mul", 0.70)), 0.2, 0.9)


static func fighter_aabb(fighter: Fighter) -> Rect2:
	if fighter == null:
		return Rect2()
	var size: Vector2 = Vector2(10.0, 22.0)
	if fighter.stand_shape != null:
		size = fighter.stand_shape.size
	var off: Vector2 = fighter.stand_offset
	return Rect2(fighter.global_position + off - size * 0.5, size)


static func _validate_grids(fx: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var keys: Array = fx.keys()
	var i: int = 0
	while i < keys.size():
		var fid: String = str(keys[i])
		var rows: Variant = fx.get(fid, [])
		if not (rows is Array):
			errors.append("env fixture %s grid must be an array" % fid)
			i += 1
			continue
		var arr: Array = rows as Array
		if arr.is_empty():
			errors.append("env fixture %s empty" % fid)
			i += 1
			continue
		var w: int = str(arr[0]).length()
		var r: int = 0
		while r < arr.size():
			if str(arr[r]).length() != w:
				errors.append("env fixture %s row %d width mismatch" % [fid, r])
			r += 1
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

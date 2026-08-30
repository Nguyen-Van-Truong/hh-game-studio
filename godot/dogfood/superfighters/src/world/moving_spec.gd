class_name MovingSpec
extends RefCounted

## Doors, elevators, and triggers (VF4-WP4).
## ledger:RL-WORLD-DOOR / RL-WORLD-LIFT / RL-WORLD-BOARD /
## RL-WORLD-TRIGGER (assumption). Not observed.
## RL-NADE-PROP stays deferred. Water is not selected (VF4-WP5).

const PATH: String = "res://data/world/moving.json"
const SCHEMA_ID: String = "vf.world.moving.v1"
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
		errors.append("moving schema id mismatch")
	if str(row.get("title", "")) != "Vault Fighters":
		errors.append("moving title must be Vault Fighters")
	if bool(row.get("y8_parity_claimed", true)):
		errors.append("moving must not claim Y8 parity")
	if bool(row.get("original_exact_numbers_claimed", true)):
		errors.append("moving must not claim original exact numbers")
	if not bool(row.get("values_are_tuning", false)):
		errors.append("moving values must be marked tuning")
	if not bool(row.get("moving_implemented", false)):
		errors.append("moving bodies must be implemented this WP")
	if str(row.get("door_class", "")) != "assumption":
		errors.append("door must stay assumption")
	if str(row.get("lift_class", "")) != "assumption":
		errors.append("lift must stay assumption")
	if str(row.get("board_class", "")) != "assumption":
		errors.append("board must stay assumption")
	if str(row.get("trigger_class", "")) != "assumption":
		errors.append("trigger must stay assumption")
	if str(row.get("nade_prop_class", "")) != "deferred":
		errors.append("RL-NADE-PROP must stay deferred")
	if str(row.get("hold_to_aim_class", "")) != "assumption":
		errors.append("hold-to-aim must stay assumption")
	if str(row.get("roll_dive_class", "")) != "unavailable":
		errors.append("Y8 roll/dive observation must stay unavailable")
	if str(row.get("title", "")).to_lower().contains("superfighter"):
		errors.append("moving title uses Superfighters trademark")
	if int(row.get("travel_ticks", 0)) < 8:
		errors.append("travel_ticks must be >= 8")
	if float(row.get("max_step_px", 0.0)) <= 0.0 or float(row.get("max_step_px", 99.0)) > 4.0:
		errors.append("max_step_px must stay in (0, 4]")
	if float(row.get("snap_eps", 99.0)) <= 0.0 or float(row.get("snap_eps", 99.0)) > 8.0:
		errors.append("snap_eps must stay in (0, 8]")
	if float(row.get("warp_px", 0.0)) < 16.0:
		errors.append("warp_px must stay >= 16")
	var kinds: PackedStringArray = _to_packed(row.get("kinds", []))
	var required_kinds: PackedStringArray = PackedStringArray(["door", "platform", "trigger"])
	var k: int = 0
	while k < required_kinds.size():
		if not kinds.has(String(required_kinds[k])):
			errors.append("moving missing kind %s" % String(required_kinds[k]))
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
			errors.append("moving spec %s id mismatch" % sid)
		var kind: String = str(spec_row.get("kind", ""))
		if not required_kinds.has(kind):
			errors.append("moving spec %s kind %s is not allowed" % [sid, kind])
		seen[kind] = true
		var name_v: String = str(spec_row.get("name", ""))
		if name_v == "" or name_v.to_lower().contains("superfighter"):
			errors.append("moving spec %s name invalid" % sid)
		var vpath: String = str(_dict(spec_row.get("visual", {})).get("path", ""))
		var path_err: String = str(_Paths.reject_reason(vpath))
		if path_err != "":
			errors.append("moving spec %s visual %s" % [sid, path_err])
		s += 1
	k = 0
	while k < required_kinds.size():
		if not seen.has(String(required_kinds[k])):
			errors.append("moving has no spec for kind %s" % String(required_kinds[k]))
		k += 1
	var fx: Dictionary = _dict(row.get("fixtures", {}))
	var names: Dictionary = _dict(row.get("fixture_names", {}))
	var need_fx: PackedStringArray = PackedStringArray(["fx_move_door", "fx_move_lift", "fx_move_yard"])
	var f: int = 0
	while f < need_fx.size():
		var fid: String = String(need_fx[f])
		if not fx.has(fid):
			errors.append("moving fixture %s missing" % fid)
		if str(names.get(fid, "")).to_lower().contains("superfighter"):
			errors.append("moving fixture name uses Superfighters trademark")
		f += 1
	if str(names.get("fx_move_door", "")) != "Gate Hall":
		errors.append("door fixture display name must be Gate Hall")
	if str(names.get("fx_move_lift", "")) != "Lift Shaft":
		errors.append("lift fixture display name must be Lift Shaft")
	if str(names.get("fx_move_yard", "")) != "Relay Shaft":
		errors.append("yard fixture display name must be Relay Shaft")
	_append(errors, _validate_grids(fx))
	return errors


static func travel_ticks() -> int:
	return maxi(int(data().get("travel_ticks", 44)), 8)


static func dwell_ticks() -> int:
	return maxi(int(data().get("dwell_ticks", 24)), 1)


static func arm_ticks() -> int:
	return maxi(int(data().get("arm_ticks", 8)), 1)


static func open_delay_ticks() -> int:
	return maxi(int(data().get("open_delay_ticks", 8)), 1)


static func max_step_px() -> float:
	return clampf(float(data().get("max_step_px", 3.0)), 0.25, 4.0)


static func board_eps() -> float:
	return float(data().get("board_eps", 8.0))


static func snap_eps() -> float:
	return clampf(float(data().get("snap_eps", 4.0)), 0.25, 8.0)


static func warp_px() -> float:
	return maxf(float(data().get("warp_px", 16.0)), 16.0)


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
			errors.append("moving fixture %s grid must be an array" % fid)
			i += 1
			continue
		var arr: Array = rows as Array
		if arr.is_empty():
			errors.append("moving fixture %s empty" % fid)
			i += 1
			continue
		var w: int = str(arr[0]).length()
		var r: int = 0
		while r < arr.size():
			if str(arr[r]).length() != w:
				errors.append("moving fixture %s row %d width mismatch" % [fid, r])
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

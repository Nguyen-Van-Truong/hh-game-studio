class_name WorldCatalog
extends RefCounted

## Data-driven world catalog (VF4-WP1). Map authoring is placements,
## not GameSession node hard-codes. ledger:RL-WORLD-SCHEMA
## (assumption). Break/throw are VF4-WP2. Chain/fire/hang
## are VF4-WP3. RL-NADE-PROP stays deferred.

const PATH: String = "res://data/world/catalog.json"
const SCHEMA_PATH: String = "res://data/world/schema.json"
const LAYERS_PATH: String = "res://data/sim/collision_layers.json"
const SCHEMA_ID: String = "vf.world.catalog.v1"
const GATE_SCHEMA_ID: String = "vf.world.schema.v1"
const _Spec: GDScript = preload("res://src/world/prop_spec.gd")

static var _cache: Dictionary = {}
static var _schema_cache: Dictionary = {}
static var _layers_cache: Dictionary = {}


static func data() -> Dictionary:
	if _cache.is_empty():
		_cache = SimConstants.load_json(PATH)
	return _cache


static func schema() -> Dictionary:
	if _schema_cache.is_empty():
		_schema_cache = SimConstants.load_json(SCHEMA_PATH)
	return _schema_cache


static func layers() -> Dictionary:
	if _layers_cache.is_empty():
		_layers_cache = SimConstants.load_json(LAYERS_PATH)
	return _layers_cache


static func spec(spec_id: String) -> Dictionary:
	var specs: Dictionary = _dict(data().get("specs", {}))
	if specs.has(spec_id):
		return _dict(specs.get(spec_id, {}))
	return {}


static func ids() -> PackedStringArray:
	var specs: Dictionary = _dict(data().get("specs", {}))
	var keys: Array = specs.keys()
	keys.sort()
	var out: PackedStringArray = PackedStringArray()
	var i: int = 0
	while i < keys.size():
		out.append(str(keys[i]))
		i += 1
	return out


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
	var gate: Dictionary = schema()
	if str(row.get("schema", "")) != SCHEMA_ID:
		errors.append("world catalog schema id mismatch")
	if str(gate.get("schema", "")) != GATE_SCHEMA_ID:
		errors.append("world schema id mismatch")
	if str(row.get("title", "")) != "Vault Fighters":
		errors.append("world catalog title must be Vault Fighters")
	if bool(row.get("y8_parity_claimed", true)):
		errors.append("world catalog must not claim Y8 parity")
	if bool(row.get("original_exact_numbers_claimed", true)):
		errors.append("world catalog must not claim original exact numbers")
	if not bool(row.get("values_are_tuning", false)):
		errors.append("world catalog values must be marked tuning")
	if not bool(row.get("break_implemented", false)):
		errors.append("break must be implemented this WP")
	if not bool(row.get("chain_implemented", false)):
		errors.append("explosive chain must be implemented this WP")
	if not bool(row.get("moving_implemented", false)):
		errors.append("moving bodies must be implemented this WP")
	if str(row.get("door_class", "")) != "assumption":
		errors.append("door must stay assumption")
	if str(row.get("lift_class", "")) != "assumption":
		errors.append("lift must stay assumption")
	if not bool(row.get("throw_implemented", false)):
		errors.append("dynamic throw must be implemented this WP")
	if str(row.get("schema_class", "")) != "assumption":
		errors.append("world schema must stay assumption")
	if str(row.get("layers_class", "")) != "assumption":
		errors.append("world layers must stay assumption")
	if str(row.get("own_class", "")) != "assumption":
		errors.append("world ownership must stay assumption")
	if str(row.get("break_class", "")) != "assumption":
		errors.append("breakable must stay assumption")
	if str(row.get("expl_class", "")) != "assumption":
		errors.append("explosive prop must stay assumption")
	if str(row.get("nade_prop_class", "")) != "deferred":
		errors.append("RL-NADE-PROP must stay deferred")
	if str(row.get("hold_to_aim_class", "")) != "assumption":
		errors.append("hold-to-aim must stay assumption")
	if str(row.get("roll_dive_class", "")) != "unavailable":
		errors.append("Y8 roll/dive observation must stay unavailable")
	var allowed: PackedStringArray = _to_packed(gate.get("allowed_kinds", []))
	var required_ids: PackedStringArray = _to_packed(gate.get("required_ids", []))
	var specs: Dictionary = _dict(row.get("specs", {}))
	var i: int = 0
	while i < required_ids.size():
		var rid: String = String(required_ids[i])
		if not specs.has(rid):
			errors.append("world catalog missing required id %s" % rid)
		i += 1
	var kinds: PackedStringArray = _to_packed(row.get("kinds", []))
	if kinds.size() != allowed.size():
		errors.append("world catalog must list every allowed kind")
	var k: int = 0
	while k < allowed.size():
		if not kinds.has(String(allowed[k])):
			errors.append("world catalog missing kind %s" % String(allowed[k]))
		k += 1
	var seen_kind: Dictionary = {}
	var keys: Array = specs.keys()
	keys.sort()
	var s: int = 0
	while s < keys.size():
		var sid: String = str(keys[s])
		var spec_row: Dictionary = _dict(specs.get(sid, {}))
		if str(spec_row.get("id", "")) != sid:
			errors.append("world spec %s id mismatch" % sid)
		var kind: String = str(spec_row.get("kind", ""))
		if not allowed.has(kind):
			errors.append("world spec %s kind %s is not allowed" % [sid, kind])
		seen_kind[kind] = true
		_append(errors, _Spec.validate_row(spec_row, gate, layers()))
		s += 1
	k = 0
	while k < allowed.size():
		if not seen_kind.has(String(allowed[k])):
			errors.append("world catalog has no spec for kind %s" % String(allowed[k]))
		k += 1
	if not _dict(row.get("fixtures", {})).has("fx_world_open"):
		errors.append("world fixture fx_world_open missing")
	if not _dict(row.get("fixtures", {})).has("fx_break_cover"):
		errors.append("world fixture fx_break_cover missing")
	if not _dict(row.get("fixtures", {})).has("fx_break_yard"):
		errors.append("world fixture fx_break_yard missing")
	if not _dict(row.get("fixtures", {})).has("fx_hazard_chain"):
		errors.append("world fixture fx_hazard_chain missing")
	if not _dict(row.get("fixtures", {})).has("fx_hazard_fire"):
		errors.append("world fixture fx_hazard_fire missing")
	if not _dict(row.get("fixtures", {})).has("fx_hazard_yard"):
		errors.append("world fixture fx_hazard_yard missing")
	if placements_from(row, "fx_world_open").size() < 6:
		errors.append("fx_world_open must place all six kinds")
	if placements_from(row, "fx_break_cover").is_empty():
		errors.append("fx_break_cover must place glass cover")
	if placements_from(row, "fx_break_yard").size() < 2:
		errors.append("fx_break_yard must place wood and a loose crate")
	if placements_from(row, "fx_hazard_chain").size() < 6:
		errors.append("fx_hazard_chain must place five drums and a hanging crate")
	if placements_from(row, "fx_hazard_fire").is_empty():
		errors.append("fx_hazard_fire must place a drum")
	if placements_from(row, "fx_hazard_yard").size() < 4:
		errors.append("fx_hazard_yard must place chain drums and a hanging crate")
	if not bool(_dict(specs.get("crate_hanging", {})).get("hanging", false)):
		errors.append("crate_hanging must start hanging")
	var mats: Dictionary = _dict(row.get("materials", {}))
	if not mats.has("wood") or not mats.has("glass"):
		errors.append("world catalog must define wood and glass materials")
	if str(_dict(specs.get("pane_glass", {})).get("material", "")) != "glass":
		errors.append("pane_glass must use glass material")
	if str(_dict(specs.get("crate_breakable", {})).get("material", "")) != "wood":
		errors.append("crate_breakable must use wood material")
	_append(errors, _validate_placements(row, specs))
	return errors


static func placements_from(row: Dictionary, map_id: String) -> Array:
	var all: Dictionary = _dict(row.get("placements", {}))
	var raw: Variant = all.get(map_id, [])
	if raw is Array:
		return raw as Array
	return []


static func _validate_placements(row: Dictionary, specs: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var all: Dictionary = _dict(row.get("placements", {}))
	var maps: Array = all.keys()
	maps.sort()
	var i: int = 0
	while i < maps.size():
		var map_id: String = str(maps[i])
		var rows: Array = placements_from(row, map_id)
		var seen: Dictionary = {}
		var p: int = 0
		while p < rows.size():
			var place: Dictionary = _dict(rows[p])
			var pid: String = str(place.get("id", ""))
			var spec_id: String = str(place.get("spec", ""))
			if pid == "":
				errors.append("placement on %s missing id" % map_id)
			if seen.has(pid):
				errors.append("duplicate placement id %s on %s" % [pid, map_id])
			seen[pid] = true
			if not specs.has(spec_id):
				errors.append("placement %s unknown spec %s" % [pid, spec_id])
			p += 1
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

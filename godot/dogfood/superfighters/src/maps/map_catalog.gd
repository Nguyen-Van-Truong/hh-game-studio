class_name MapCatalog
extends RefCounted

## Layered map registry (VF5-WP1). Live arenas load from JSON layers.
## Fixture ASCII stays import-only. ledger:RL-MAP-LAYERS (assumption).

const _MapCodec: GDScript = preload("res://src/maps/map_codec.gd")

const PATH: String = "res://data/maps/catalog.json"
const SCHEMA_PATH: String = "res://data/maps/schema.json"
const SCHEMA_ID: String = "vf.maps.catalog.v1"
const GATE_SCHEMA_ID: String = "vf.maps.schema.v1"
const LAYERS_ID: String = "vf.maps.layers.v1"

static var _cache: Dictionary = {}
static var _schema_cache: Dictionary = {}
static var _docs: Dictionary = {}


static func data() -> Dictionary:
	if _cache.is_empty():
		_cache = SimConstants.load_json(PATH)
	return _cache


static func schema() -> Dictionary:
	if _schema_cache.is_empty():
		_schema_cache = SimConstants.load_json(SCHEMA_PATH)
	return _schema_cache


static func reload() -> void:
	_cache = {}
	_schema_cache = {}
	_docs = {}


static func map_paths() -> Dictionary:
	return _dict(data().get("maps", {}))


static func has_id(map_id: String) -> bool:
	return map_paths().has(map_id)


static func ids() -> PackedStringArray:
	var keys: Array = map_paths().keys()
	keys.sort()
	var out: PackedStringArray = PackedStringArray()
	var i: int = 0
	while i < keys.size():
		out.append(str(keys[i]))
		i += 1
	return out


static func document(map_id: String) -> Dictionary:
	if _docs.has(map_id):
		return (_docs[map_id] as Dictionary).duplicate(true)
	if has_id(map_id):
		var path: String = str(map_paths().get(map_id, ""))
		if not _path_ok(path):
			return {}
		var loaded: Dictionary = _MapCodec.normalize(SimConstants.load_json(path))
		_docs[map_id] = loaded
		return loaded.duplicate(true)
	if Maps.has_fixture(map_id):
		var imported: Dictionary = _MapCodec.from_ascii(
			map_id,
			Maps.fixture_grid(map_id),
			Maps.fixture_name(map_id),
			_MapCodec.theme_for(map_id)
		)
		_docs[map_id] = imported
		return imported.duplicate(true)
	return {}


static func display_name(map_id: String) -> String:
	var doc: Dictionary = document(map_id)
	var name: String = str(doc.get("display_name", ""))
	if name != "":
		return name
	return map_id


static func validate() -> PackedStringArray:
	return validate_payload(data())


static func validate_payload(row: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var gate: Dictionary = schema()
	if str(row.get("schema", "")) != SCHEMA_ID:
		errors.append("map catalog schema id mismatch")
	if str(gate.get("schema", "")) != GATE_SCHEMA_ID:
		errors.append("map schema id mismatch")
	if str(row.get("title", "")) != "Vault Fighters":
		errors.append("map catalog title must be Vault Fighters")
	if str(row.get("title", "")).to_lower().contains("superfighter"):
		errors.append("map catalog title uses Superfighters trademark")
	if bool(row.get("y8_parity_claimed", true)):
		errors.append("map catalog must not claim Y8 parity")
	if bool(row.get("original_exact_numbers_claimed", true)):
		errors.append("map catalog must not claim original exact numbers")
	if not bool(row.get("values_are_tuning", false)):
		errors.append("map catalog values must be marked tuning")
	if not bool(row.get("layered_maps", false)):
		errors.append("map catalog must use layered maps")
	if bool(row.get("ascii_maps_kept", true)):
		errors.append("map catalog must retire ASCII as source")
	if not bool(row.get("live_c_b_tiles", false)):
		errors.append("live c/b must stay painted tiles")
	if str(row.get("layers_class", "")) != "assumption":
		errors.append("map layers must stay assumption")
	if str(row.get("graph_class", "")) != "assumption":
		errors.append("map graph must stay assumption")
	if str(row.get("valid_class", "")) != "assumption":
		errors.append("map validator must stay assumption")
	if str(row.get("author_class", "")) != "assumption":
		errors.append("map author must stay assumption")
	if str(row.get("hold_to_aim_class", "")) != "assumption":
		errors.append("hold-to-aim must stay assumption")
	if str(row.get("roll_dive_class", "")) != "unavailable":
		errors.append("Y8 roll/dive observation must stay unavailable")
	if str(row.get("nade_prop_class", "")) != "deferred":
		errors.append("RL-NADE-PROP must stay deferred")
	if str(row.get("skyline_class", "")) != "" and str(row.get("skyline_class", "")) != "assumption":
		errors.append("Skyline Relay contract must stay assumption")
	var required: PackedStringArray = _to_packed(gate.get("required_live_ids", []))
	var maps: Dictionary = _dict(row.get("maps", {}))
	var i: int = 0
	while i < required.size():
		var mid: String = String(required[i])
		if not maps.has(mid):
			errors.append("map catalog missing live map %s" % mid)
		i += 1
	var author_id: String = str(gate.get("required_author_id", "fx_map_author"))
	if not maps.has(author_id):
		errors.append("map catalog missing authored map %s" % author_id)
	var keys: Array = maps.keys()
	keys.sort()
	i = 0
	while i < keys.size():
		var mid: String = str(keys[i])
		var path: String = str(maps.get(mid, ""))
		if not _path_ok(path):
			errors.append("map %s path escapes product root" % mid)
			i += 1
			continue
		var doc: Dictionary = _MapCodec.normalize(SimConstants.load_json(path))
		if str(doc.get("schema", "")) != LAYERS_ID:
			errors.append("map %s schema mismatch" % mid)
		if str(doc.get("id", "")) != mid:
			errors.append("map %s id mismatch" % mid)
		if str(doc.get("title", "")) != "Vault Fighters":
			errors.append("map %s title must be Vault Fighters" % mid)
		var dname: String = str(doc.get("display_name", ""))
		if dname == "" or dname.to_lower().contains("superfighter"):
			errors.append("map %s display name invalid" % mid)
		if bool(doc.get("y8_parity_claimed", true)):
			errors.append("map %s claimed Y8 parity" % mid)
		i += 1
	return errors


static func _path_ok(path: String) -> bool:
	if path == "" or not path.begins_with("res://data/maps/"):
		return false
	if path.contains("..") or path.contains("\\"):
		return false
	return FileAccess.file_exists(path)


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

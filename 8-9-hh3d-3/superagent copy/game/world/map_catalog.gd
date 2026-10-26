class_name MapCatalog
extends RefCounted
## Original product map registry. It is a selector seam, not reference-map parity.

const SCHEMA: StringName = &"sa09.map-catalog.v1"
const _ENTRIES: Array[Dictionary] = [
	{&"id": &"relay_yard", &"path": "res://data/relay_yard.json", &"display_name": "Relay Yard"},
	{&"id": &"cobalt_forge", &"path": "res://data/cobalt_forge.json", &"display_name": "Cobalt Forge"},
	{&"id": &"hollow_station", &"path": "res://data/hollow_station.json", &"display_name": "Hollow Station"},
	{&"id": &"ember_quarry", &"path": "res://data/ember_quarry.json", &"display_name": "Ember Quarry"},
	{&"id": &"tidal_lock", &"path": "res://data/tidal_lock.json", &"display_name": "Tidal Lock"},
	{&"id": &"glassway", &"path": "res://data/glassway.json", &"display_name": "Glassway"},
	{&"id": &"classic_rooftops", &"path": "res://data/classic_rooftops.json", &"display_name": "Classic Rooftops"},
]

static func entries() -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	for row: Dictionary in _ENTRIES:
		var copy: Dictionary = row.duplicate(true)
		copy.make_read_only()
		result.append(copy)
	result.make_read_only()
	return result

static func default_id() -> StringName:
	return &"relay_yard"

static func resolve(map_id: StringName) -> Dictionary:
	for row: Dictionary in _ENTRIES:
		if StringName(row[&"id"]) == map_id:
			var copy: Dictionary = row.duplicate(true)
			copy.make_read_only()
			return copy
	return {}

static func resolve_path(path: String) -> Dictionary:
	if path.is_empty() or not path.begins_with("res://data/") or path.contains(".."):
		return {}
	for row: Dictionary in _ENTRIES:
		if String(row[&"path"]) == path:
			return resolve(StringName(row[&"id"]))
	return {}

static func select(seed: int, index: int = 0) -> Dictionary:
	var rows: Array[Dictionary] = entries()
	if rows.is_empty():
		return {}
	var mixed: int = abs(seed * 1103515245 + index * 12345)
	return rows[mixed % rows.size()]

static func canonical_fingerprint() -> String:
	var parts: Array[String] = ["schema=%s" % String(SCHEMA)]
	for row: Dictionary in _ENTRIES:
		parts.append("%s,%s" % [String(row[&"id"]), String(row[&"path"])])
	return ";".join(parts)

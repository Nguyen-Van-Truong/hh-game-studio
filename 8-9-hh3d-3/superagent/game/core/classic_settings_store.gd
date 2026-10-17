class_name ClassicSettingsStore
extends RefCounted
## Validated local settings persistence for the Classic menu slice.
## The store is deliberately separate from simulation state and never enters a
## gameplay snapshot or deterministic hash.

const SCHEMA: StringName = &"sa07.settings.v1"
const DEFAULT_PATH: String = "user://superagent-settings.json"
const GRAPHICS_VALUES: Array[StringName] = [&"High", &"Medium", &"Low"]
const EFFECT_VALUES: Array[StringName] = [&"High", &"Medium", &"Low", &"Best"]
const CONTROL_VALUES: Array[StringName] = [&"Simple", &"Advanced"]
const ACTIONS: Array[StringName] = [
	&"p1_left", &"p1_right", &"p1_up", &"p1_down", &"p1_punch", &"p1_shoot", &"p1_throw", &"p1_power", &"p1_switch",
	&"p2_left", &"p2_right", &"p2_up", &"p2_down", &"p2_punch", &"p2_shoot", &"p2_throw", &"p2_power", &"p2_switch",
]
const DOCUMENT_KEYS: Array[StringName] = [&"schema", &"graphics", &"effects", &"volume", &"controls", &"bindings"]

var path: String = DEFAULT_PATH
var values: Dictionary = {}
var last_error: StringName = &""

func _init(path_input: String = DEFAULT_PATH) -> void:
	path = path_input if _valid_path(path_input) else DEFAULT_PATH
	reset()
	load_settings()

func reset() -> void:
	values = {
		&"schema": SCHEMA,
		&"graphics": &"High",
		&"effects": &"Best",
		&"volume": 80,
		&"controls": &"Simple",
		&"bindings": {},
	}
	last_error = &""

func load_settings() -> bool:
	if not FileAccess.file_exists(path):
		return false
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if file == null:
		last_error = &"open_failed"
		return false
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if not _valid_document(parsed):
		last_error = &"invalid_document"
		return false
	values = _normalise(Dictionary(parsed))
	last_error = &""
	return true

func save_settings(input: Dictionary = values) -> bool:
	if not _valid_document(input):
		last_error = &"invalid_document"
		return false
	var document: Dictionary = _normalise(input)
	var temporary_path: String = path + ".tmp"
	var file: FileAccess = FileAccess.open(temporary_path, FileAccess.WRITE)
	if file == null:
		last_error = &"temp_open_failed"
		return false
	file.store_string(JSON.stringify(document, "\t"))
	file.flush()
	file.close()
	var backup_path: String = path + ".bak"
	var had_existing: bool = FileAccess.file_exists(path)
	if FileAccess.file_exists(backup_path):
		DirAccess.remove_absolute(_global_path(backup_path))
	if had_existing and DirAccess.rename_absolute(_global_path(path), _global_path(backup_path)) != OK:
		last_error = &"replace_backup_failed"
		return false
	if DirAccess.rename_absolute(_global_path(temporary_path), _global_path(path)) != OK:
		if had_existing and not FileAccess.file_exists(path):
			DirAccess.rename_absolute(_global_path(backup_path), _global_path(path))
		if FileAccess.file_exists(temporary_path):
			DirAccess.remove_absolute(_global_path(temporary_path))
		last_error = &"replace_rename_failed"
		return false
	if had_existing and FileAccess.file_exists(backup_path):
		DirAccess.remove_absolute(_global_path(backup_path))
	values = document
	last_error = &""
	return true

func set_value(key: StringName, value: Variant) -> bool:
	var candidate: Dictionary = values.duplicate(true)
	candidate[key] = value
	if not _valid_document(candidate):
		last_error = &"invalid_value"
		return false
	values = _normalise(candidate)
	last_error = &""
	return true

func set_binding(action: StringName, keycode: int) -> bool:
	if action not in ACTIONS or keycode <= 0:
		last_error = &"invalid_binding"
		return false
	var bindings: Dictionary = Dictionary(values.get(&"bindings", {})).duplicate(true)
	bindings[action] = keycode
	return set_value(&"bindings", bindings)

func snapshot() -> Dictionary:
	var copy: Dictionary = values.duplicate(true)
	var bindings: Dictionary = Dictionary(copy.get(&"bindings", {})).duplicate(true)
	bindings.make_read_only()
	copy[&"bindings"] = bindings
	copy.make_read_only()
	return copy

func _valid_document(document: Variant) -> bool:
	if typeof(document) != TYPE_DICTIONARY:
		return false
	var row: Dictionary = document
	for key: Variant in row.keys():
		if not _valid_name(key) or StringName(key) not in DOCUMENT_KEYS:
			return false
	var schema_value: Variant = _field(row, &"schema", SCHEMA)
	if not _valid_name(schema_value) or StringName(schema_value) != SCHEMA:
		return false
	var graphics: Variant = _field(row, &"graphics", null)
	var effects: Variant = _field(row, &"effects", null)
	var controls: Variant = _field(row, &"controls", null)
	var volume: Variant = _field(row, &"volume", null)
	if not _valid_name(graphics) or StringName(graphics) not in GRAPHICS_VALUES:
		return false
	if not _valid_name(effects) or StringName(effects) not in EFFECT_VALUES:
		return false
	if not _valid_name(controls) or StringName(controls) not in CONTROL_VALUES:
		return false
	if not _valid_integer(volume) or int(volume) < 0 or int(volume) > 100:
		return false
	var binding_value: Variant = _field(row, &"bindings", {})
	if typeof(binding_value) != TYPE_DICTIONARY:
		return false
	for action: Variant in Dictionary(binding_value).keys():
		if not _valid_name(action) or StringName(action) not in ACTIONS:
			return false
		var keycode: Variant = Dictionary(binding_value)[action]
		if not _valid_integer(keycode) or int(keycode) <= 0:
			return false
	return true

func _normalise(document: Dictionary) -> Dictionary:
	var result: Dictionary = {
		&"schema": SCHEMA,
		&"graphics": StringName(_field(document, &"graphics", &"High")),
		&"effects": StringName(_field(document, &"effects", &"Best")),
		&"volume": int(_field(document, &"volume", 80)),
		&"controls": StringName(_field(document, &"controls", &"Simple")),
		&"bindings": {},
	}
	var bindings: Dictionary = {}
	var binding_value: Dictionary = Dictionary(_field(document, &"bindings", {}))
	for action: Variant in binding_value.keys():
		bindings[StringName(action)] = int(binding_value[action])
	result[&"bindings"] = bindings
	return result

func _valid_path(candidate: String) -> bool:
	return candidate.begins_with("user://") and not candidate.contains("..")

func _valid_name(value: Variant) -> bool:
	return typeof(value) == TYPE_STRING or typeof(value) == TYPE_STRING_NAME

func _valid_integer(value: Variant) -> bool:
	if typeof(value) == TYPE_INT:
		return true
	return typeof(value) == TYPE_FLOAT and is_finite(float(value)) and is_equal_approx(float(value), roundf(float(value)))

func _global_path(value: String) -> String:
	return ProjectSettings.globalize_path(value)

func _field(row: Dictionary, key: StringName, fallback: Variant) -> Variant:
	if row.has(key):
		return row[key]
	var text_key: String = String(key)
	return row.get(text_key, fallback)

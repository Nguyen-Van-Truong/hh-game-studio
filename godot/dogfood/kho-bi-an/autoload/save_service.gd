extends Node

const SAVE_PATH: String = "user://kho_bi_an_v1.cfg"
const TEST_PATH: String = "user://kho_bi_an_r8wp2_test.cfg"
const SCHEMA: int = 1

var _path: String = SAVE_PATH


func use_test_path() -> void:
	_path = TEST_PATH


func use_default_path() -> void:
	_path = SAVE_PATH


func current_path() -> String:
	return _path


func clear_slot() -> void:
	if FileAccess.file_exists(_path):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(_path))


func autosave(state: GameState) -> void:
	write_slot(state.to_dict())


func write_slot(data: Dictionary) -> void:
	var cfg: ConfigFile = ConfigFile.new()
	cfg.set_value("meta", "schema", int(data.get("schema", SCHEMA)))
	cfg.set_value("flags", "room_id", str(data.get("room_id", "start")))
	cfg.set_value("flags", "has_key", bool(data.get("has_key", false)))
	cfg.set_value("flags", "door_open", bool(data.get("door_open", false)))
	cfg.set_value("flags", "relic_reached", bool(data.get("relic_reached", false)))
	var err: Error = cfg.save(_path)
	if err != OK:
		push_error("SaveService write failed: %s" % str(err))


func load_slot() -> Dictionary:
	if not FileAccess.file_exists(_path):
		return {}
	var cfg: ConfigFile = ConfigFile.new()
	var err: Error = cfg.load(_path)
	if err != OK:
		return {}
	var schema: int = int(cfg.get_value("meta", "schema", 0))
	if schema != SCHEMA:
		return {}
	return {
		"schema": schema,
		"room_id": str(cfg.get_value("flags", "room_id", "start")),
		"has_key": bool(cfg.get_value("flags", "has_key", false)),
		"door_open": bool(cfg.get_value("flags", "door_open", false)),
		"relic_reached": bool(cfg.get_value("flags", "relic_reached", false)),
	}


func write_foreign_schema() -> void:
	var cfg: ConfigFile = ConfigFile.new()
	cfg.set_value("meta", "schema", 99)
	cfg.set_value("flags", "room_id", "door")
	cfg.set_value("flags", "has_key", true)
	var err: Error = cfg.save(_path)
	if err != OK:
		push_error("SaveService foreign write failed: %s" % str(err))

extends SceneTree

const STORE_SCRIPT = preload("res://game/core/classic_settings_store.gd")
var assertions: int = 0
var test_path: String = "user://sa07-settings-test.json"

func _init() -> void:
	if FileAccess.file_exists(test_path):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(test_path))
	var store: ClassicSettingsStore = STORE_SCRIPT.new(test_path)
	_expect(store.values[&"graphics"] == &"High" and store.values[&"volume"] == 80, "defaults are loaded")
	_expect(store.set_value(&"graphics", &"Medium"), "known graphics value is accepted")
	_expect(store.set_value(&"effects", &"Best"), "known effects value is accepted")
	_expect(store.set_value(&"volume", 55), "integer volume is accepted")
	_expect(store.set_value(&"controls", &"Advanced"), "known control mode is accepted")
	_expect(store.set_binding(&"p1_punch", 74), "owner action binding is accepted")
	_expect(store.save_settings(), "settings save succeeds")
	_expect(store.set_value(&"volume", 56) and store.save_settings(), "existing settings replace safely")
	var reloaded: ClassicSettingsStore = STORE_SCRIPT.new(test_path)
	_expect(reloaded.values[&"graphics"] == &"Medium" and reloaded.values[&"effects"] == &"Best", "quality choices survive reload")
	_expect(reloaded.values[&"volume"] == 56 and reloaded.values[&"controls"] == &"Advanced", "volume/control choices survive reload")
	_expect(Dictionary(reloaded.values[&"bindings"])[&"p1_punch"] == 74, "binding survives reload")
	_expect(not reloaded.set_value(&"volume", 101), "out-of-range volume fails closed")
	_expect(not reloaded.set_value(&"u_special", true), "unknown settings key fails closed")
	_expect(not reloaded.set_value(&"graphics", &"Ultra"), "unknown graphics value fails closed")
	_expect(not reloaded.set_binding(&"u_special", 85), "reserved special action cannot enter Classic settings")
	_expect(not reloaded.save_settings({&"schema": &"wrong", &"graphics": &"High", &"effects": &"Best", &"volume": 80, &"controls": &"Simple", &"bindings": {}}), "wrong schema cannot save")
	_expect(reloaded.snapshot().is_read_only(), "settings snapshot is immutable")
	if FileAccess.file_exists(test_path):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(test_path))
	if FileAccess.file_exists(test_path + ".tmp"):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(test_path + ".tmp"))
	print("SA-07 settings store PASS: %d assertions" % assertions)
	quit()

func _expect(condition: bool, message: String) -> void:
	assertions += 1
	if not condition:
		push_error("FAIL: " + message)
		quit(1)

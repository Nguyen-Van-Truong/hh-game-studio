# HH gamekit kit settings v1 - MIT License
extends Node
## Bus volumes, window, and locale persisted in user://settings.cfg (MIT).

signal changed(key: String)

const BUS_NAMES: PackedStringArray = ["Master", "Music", "SFX"]
const _PATH: String = "user://settings.cfg"
const _BAK: String = "user://.settings.cfg.bak"

var bus_volume: Dictionary = {"Master": 1.0, "Music": 1.0, "SFX": 1.0}
var fullscreen: bool = false
var vsync: bool = true
var max_fps: int = 0
var ui_scale: float = 1.0
var locale: String = "en"

var _booted: bool = false


func _enter_tree() -> void:
	if _booted:
		return
	_booted = true
	load_settings()
	apply()


func set_bus_volume(bus: String, linear: float) -> void:
	if not BUS_NAMES.has(bus):
		push_warning("HHSettings: unknown bus " + bus)
		return
	if is_nan(linear) or is_inf(linear):
		push_warning("HHSettings: non-finite volume")
		return
	var v: float = clampf(linear, 0.0, 1.0)
	bus_volume[bus] = v
	_apply_bus(bus, v)
	changed.emit("bus:" + bus)


func get_bus_volume(bus: String) -> float:
	return float(bus_volume.get(bus, 1.0))


func set_fullscreen(on: bool) -> void:
	fullscreen = on
	_apply_display()
	changed.emit("fullscreen")


func set_vsync(on: bool) -> void:
	vsync = on
	_apply_display()
	changed.emit("vsync")


func set_max_fps(fps: int) -> void:
	max_fps = maxi(fps, 0)
	Engine.max_fps = max_fps
	changed.emit("max_fps")


func set_ui_scale(scale: float) -> void:
	if is_nan(scale) or is_inf(scale):
		push_warning("HHSettings: non-finite ui scale")
		return
	ui_scale = clampf(scale, 0.25, 4.0)
	_apply_ui()
	changed.emit("ui_scale")


func set_locale(code: String) -> void:
	if not _locale_ok(code):
		push_warning("HHSettings: bad locale")
		return
	locale = code
	TranslationServer.set_locale(locale)
	changed.emit("locale")


func apply() -> void:
	for bus: String in BUS_NAMES:
		_apply_bus(bus, float(bus_volume.get(bus, 1.0)))
	_apply_display()
	_apply_ui()
	TranslationServer.set_locale(locale)


func save_settings() -> Error:
	var cfg: ConfigFile = ConfigFile.new()
	cfg.set_value("audio", "Master", float(bus_volume.get("Master", 1.0)))
	cfg.set_value("audio", "Music", float(bus_volume.get("Music", 1.0)))
	cfg.set_value("audio", "SFX", float(bus_volume.get("SFX", 1.0)))
	cfg.set_value("display", "fullscreen", fullscreen)
	cfg.set_value("display", "vsync", vsync)
	cfg.set_value("display", "max_fps", max_fps)
	cfg.set_value("interface", "ui_scale", ui_scale)
	cfg.set_value("interface", "locale", locale)
	return _save_cfg(cfg, _PATH)


func load_settings() -> Error:
	var path: String = _resolve_path()
	if path.is_empty():
		return ERR_FILE_NOT_FOUND
	var cfg: ConfigFile = ConfigFile.new()
	var err: Error = cfg.load(path)
	if err != OK:
		push_warning("HHSettings: cannot read settings.cfg")
		return err
	bus_volume["Master"] = _unit(cfg.get_value("audio", "Master", 1.0))
	bus_volume["Music"] = _unit(cfg.get_value("audio", "Music", 1.0))
	bus_volume["SFX"] = _unit(cfg.get_value("audio", "SFX", 1.0))
	fullscreen = bool(cfg.get_value("display", "fullscreen", false))
	vsync = bool(cfg.get_value("display", "vsync", true))
	max_fps = maxi(int(cfg.get_value("display", "max_fps", 0)), 0)
	ui_scale = clampf(float(cfg.get_value("interface", "ui_scale", 1.0)), 0.25, 4.0)
	var code: String = str(cfg.get_value("interface", "locale", "en"))
	locale = code if _locale_ok(code) else "en"
	return OK


func _apply_bus(bus: String, linear: float) -> void:
	var idx: int = AudioServer.get_bus_index(bus)
	if idx < 0:
		return
	var db: float = -80.0 if linear <= 0.0001 else linear_to_db(linear)
	AudioServer.set_bus_volume_db(idx, db)


func _apply_display() -> void:
	Engine.max_fps = max_fps
	if _headless():
		return
	var mode: DisplayServer.WindowMode = DisplayServer.WINDOW_MODE_FULLSCREEN if fullscreen else DisplayServer.WINDOW_MODE_WINDOWED
	DisplayServer.window_set_mode(mode)
	var sync: DisplayServer.VSyncMode = DisplayServer.VSYNC_ENABLED if vsync else DisplayServer.VSYNC_DISABLED
	DisplayServer.window_set_vsync_mode(sync)


func _apply_ui() -> void:
	if _headless():
		return
	var win: Window = get_window()
	if win != null:
		win.content_scale_factor = ui_scale


func _headless() -> bool:
	return DisplayServer.get_name() == "headless" or OS.has_feature("headless")


func _unit(value: Variant) -> float:
	var f: float = float(value)
	if is_nan(f) or is_inf(f):
		return 1.0
	return clampf(f, 0.0, 1.0)


func _locale_ok(code: String) -> bool:
	if code.is_empty() or code.length() > 16:
		return false
	for i: int in code.length():
		var c: String = code.substr(i, 1)
		var ok: bool = (c >= "a" and c <= "z") or (c >= "A" and c <= "Z") or (c >= "0" and c <= "9") or c == "_" or c == "-"
		if not ok:
			return false
	return true


func _save_cfg(cfg: ConfigFile, res_path: String) -> Error:
	var temp_res: String = res_path + ".hhtmp"
	var err: Error = cfg.save(temp_res)
	if err != OK:
		return err
	var temp_abs: String = ProjectSettings.globalize_path(temp_res)
	var final_abs: String = ProjectSettings.globalize_path(res_path)
	return _replace(temp_abs, final_abs)

func _resolve_path() -> String:
	if FileAccess.file_exists(_PATH):
		return _PATH
	if FileAccess.file_exists(_BAK):
		push_warning("HHSettings: loaded backup settings.cfg")
		return _BAK
	return ""

func _backup_abs(final_abs: String) -> String:
	var slash: int = maxi(final_abs.rfind("/"), final_abs.rfind("\\"))
	var file_name: String = final_abs.substr(slash + 1)
	var folder: String = final_abs.substr(0, slash + 1)
	var hidden: String = "." + file_name + ".bak"
	return folder + hidden


## Move the live file aside, then put the temp file in its place.
## Never delete the live file until the new bytes have its name.
func _replace(temp_abs: String, final_abs: String) -> Error:
	var bak_abs: String = _backup_abs(final_abs)
	var backed_up: bool = false
	if FileAccess.file_exists(final_abs):
		if FileAccess.file_exists(bak_abs):
			var cleared: Error = DirAccess.remove_absolute(bak_abs)
			if cleared != OK:
				DirAccess.remove_absolute(temp_abs)
				return cleared
		var parked: Error = DirAccess.rename_absolute(final_abs, bak_abs)
		if parked != OK:
			DirAccess.remove_absolute(temp_abs)
			return parked
		backed_up = true
	var renamed: Error = DirAccess.rename_absolute(temp_abs, final_abs)
	if renamed != OK:
		if backed_up:
			DirAccess.rename_absolute(bak_abs, final_abs)
		DirAccess.remove_absolute(temp_abs)
		return renamed
	if FileAccess.file_exists(bak_abs):
		DirAccess.remove_absolute(bak_abs)
	return OK

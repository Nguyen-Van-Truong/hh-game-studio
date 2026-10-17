extends Node2D
## Honest SA-01 startup scene. It exposes only the bootstrap status.

const MAP_CATALOG_SCRIPT = preload("res://game/world/map_catalog.gd")

@onready var _status: Label = $CanvasLayer/Status
var _input_buffer: InputBuffer
var settings: ClassicSettingsStore
var map_entries: Array[Dictionary] = []
var map_index: int = 0

func _ready() -> void:
	_input_buffer = InputBuffer.new()
	settings = ClassicSettingsStore.new()
	map_entries = MAP_CATALOG_SCRIPT.entries()
	var current_map: StringName = StringName(get_tree().get_meta(&"superagent_map_id", MAP_CATALOG_SCRIPT.default_id()))
	for index: int in range(map_entries.size()):
		if StringName(map_entries[index][&"id"]) == current_map:
			map_index = index
			break
	_refresh_status()

func _input(event: InputEvent) -> void:
	if _input_buffer != null:
		_input_buffer.accept_event(event)
	if event is InputEventKey:
		var key_event := event as InputEventKey
		if key_event.pressed and not key_event.echo and (key_event.keycode == KEY_ENTER or key_event.keycode == KEY_SPACE):
			_launch("res://movement_room.tscn")
		elif key_event.pressed and not key_event.echo and key_event.keycode == KEY_B:
			_launch("res://game/ui/match_room_bot.tscn")
		elif key_event.pressed and not key_event.echo and key_event.keycode == KEY_V:
			_launch("res://game/ui/match_room.tscn")
		elif key_event.pressed and not key_event.echo and key_event.keycode == KEY_1:
			_launch("res://game/ui/match_room.tscn")
		elif key_event.pressed and not key_event.echo and key_event.keycode == KEY_2:
			_launch("res://game/ui/match_room_stage.tscn")
		elif key_event.pressed and not key_event.echo and key_event.keycode == KEY_3:
			_launch("res://game/ui/match_room_survival.tscn")
		elif key_event.pressed and not key_event.echo and key_event.keycode == KEY_M:
			_cycle_map()
		elif key_event.pressed and not key_event.echo and key_event.keycode == KEY_G:
			_cycle_setting(&"graphics", ClassicSettingsStore.GRAPHICS_VALUES)
		elif key_event.pressed and not key_event.echo and key_event.keycode == KEY_E:
			_cycle_setting(&"effects", ClassicSettingsStore.EFFECT_VALUES)
		elif key_event.pressed and not key_event.echo and (key_event.keycode == KEY_MINUS or key_event.keycode == KEY_UNDERSCORE):
			_adjust_volume(-10)
		elif key_event.pressed and not key_event.echo and (key_event.keycode == KEY_EQUAL or key_event.keycode == KEY_PLUS):
			_adjust_volume(10)
		elif key_event.pressed and not key_event.echo and key_event.keycode == KEY_C:
			var next_controls: StringName = &"Advanced" if settings.values.get(&"controls", &"Simple") == &"Simple" else &"Simple"
			if settings.set_value(&"controls", next_controls):
				settings.save_settings()
				_refresh_status()

func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT and _input_buffer != null:
		_input_buffer.cancel_all()

func _cycle_setting(key: StringName, choices: Array[StringName]) -> void:
	if settings == null or choices.is_empty():
		return
	var current: StringName = StringName(settings.values.get(key, choices[0]))
	var index: int = choices.find(current)
	var next: StringName = choices[(index + 1) % choices.size()]
	if settings.set_value(key, next) and settings.save_settings():
		_refresh_status()

func _adjust_volume(delta: int) -> void:
	if settings == null:
		return
	var volume: int = clampi(int(settings.values.get(&"volume", 80)) + delta, 0, 100)
	if settings.set_value(&"volume", volume) and settings.save_settings():
		_refresh_status()

func _refresh_status() -> void:
	if _status == null or settings == null:
		return
	var map_label: String = String(map_entries[map_index].get(&"display_name", &"Relay Yard")) if not map_entries.is_empty() else "Relay Yard"
	_status.text = "Superagent\n\nClassic prototype\nEnter / Space  movement lab\n1  VS local 2P\n2  Stage local 2P\n3  Survival local 2P\nB  VS bot match\nV  VS local 2P\nM  next original map  [%s]\n\nG graphics  E effects  -/+ volume  C controls\n%s / %s / volume %d / %s\nReference tuning is still being measured." % [
		map_label, String(settings.values.get(&"graphics", &"High")), String(settings.values.get(&"effects", &"Best")), int(settings.values.get(&"volume", 80)), String(settings.values.get(&"controls", &"Simple"))]

func _cycle_map() -> void:
	if map_entries.is_empty():
		return
	map_index = (map_index + 1) % map_entries.size()
	get_tree().set_meta(&"superagent_map_id", map_entries[map_index][&"id"])
	_refresh_status()

func _launch(scene_path: String) -> void:
	if not map_entries.is_empty():
		get_tree().set_meta(&"superagent_map_id", map_entries[map_index][&"id"])
	get_tree().change_scene_to_file(scene_path)

func setting_value(key: StringName) -> Variant:
	return settings.values.get(key) if settings != null else null

func map_value() -> StringName:
	return StringName(map_entries[map_index][&"id"]) if not map_entries.is_empty() else MAP_CATALOG_SCRIPT.default_id()

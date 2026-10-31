extends Node2D
## Main scene bootstrap for Superfighters Y8 1:1 Remake (SF-M5).
## Coordinates MainMenuController and MatchController.
## Supports '--quick-2p' and '--quick-match' CLI flags to jump straight into a 2P match on Rooftops.

const MapLoaderScript = preload("res://game/world/map_loader.gd")
const MatchWorldScene: PackedScene = preload("res://scenes/match_world.tscn")
const MainMenuScene: PackedScene = preload("res://scenes/ui/main_menu.tscn")

var menu_layer: CanvasLayer = null
var main_menu: Control = null
var match_world: Node2D = null
var _quitting: bool = false


func _ready() -> void:
	get_tree().auto_accept_quit = false
	MapLoaderScript.get_registry()
	MapLoaderScript.get_audio()

	_setup_menu_and_world()

	var cli_config: Dictionary = _parse_cli_launch_args()
	if bool(cli_config.get("instant_start", false)):
		_on_start_match_requested(cli_config)
	else:
		show_main_menu()


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST and is_inside_tree():
		_quit_cleanly()


func _quit_cleanly() -> void:
	if _quitting:
		return
	_quitting = true
	process_mode = Node.PROCESS_MODE_DISABLED
	var audio: Node = get_node_or_null("/root/AudioManager")
	var drained: bool = true
	if audio != null and audio.has_method("stop_all_and_drain"):
		drained = bool(await audio.call("stop_all_and_drain"))
	get_tree().quit(0 if drained else 1)


func _setup_menu_and_world() -> void:
	if match_world == null or not is_instance_valid(match_world):
		match_world = MatchWorldScene.instantiate() as Node2D
		match_world.name = "MatchWorld"
		match_world.visible = false
		match_world.process_mode = Node.PROCESS_MODE_DISABLED
		if match_world.has_signal("request_return_to_menu"):
			match_world.connect("request_return_to_menu", show_main_menu)
		if match_world.has_signal("request_open_setup"):
			match_world.connect("request_open_setup", show_setup_from_match)
		add_child(match_world)

	if menu_layer == null or not is_instance_valid(menu_layer):
		menu_layer = CanvasLayer.new()
		menu_layer.name = "MenuCanvasLayer"
		menu_layer.layer = 25
		add_child(menu_layer)

	if main_menu == null or not is_instance_valid(main_menu):
		main_menu = MainMenuScene.instantiate() as Control
		main_menu.name = "MainMenu"
		if main_menu.has_signal("start_match_requested"):
			main_menu.connect("start_match_requested", _on_start_match_requested)
		menu_layer.add_child(main_menu)


func _parse_cli_launch_args() -> Dictionary:
	var all_args: PackedStringArray = OS.get_cmdline_args()
	var user_args: PackedStringArray = OS.get_cmdline_user_args()
	var combined: Array[String] = []
	for a: String in all_args:
		combined.append(a)
	for ua: String in user_args:
		combined.append(ua)

	var instant: bool = false
	var mode: String = "vs"
	var map_id: String = "rooftops"
	var two_player: bool = true

	for arg: String in combined:
		var lower: String = arg.to_lower().strip_edges()
		if lower == "--quick-2p" or lower == "--quick-match":
			instant = true
			two_player = true
		elif lower.begins_with("--map="):
			map_id = lower.substr(6)
		elif lower.begins_with("--mode="):
			var mval: String = lower.substr(7)
			if mval == "vs_2p":
				mode = "vs"
				two_player = true
			else:
				mode = mval

	return {
		"instant_start": instant,
		"mode": mode,
		"map_id": map_id,
		"two_player": two_player,
		"p1_char": "johnny",
		"p2_char": "agent",
		"bot_count": 0,
		"bot_difficulty": 2,
	}


func show_main_menu() -> void:
	show_setup_from_match("MAIN")


func show_setup_from_match(target_panel: String = "MAIN") -> void:
	if match_world != null and is_instance_valid(match_world):
		match_world.visible = false
		match_world.process_mode = Node.PROCESS_MODE_DISABLED
		var hud: CanvasLayer = match_world.get("hud_controller") as CanvasLayer
		if hud != null:
			hud.visible = false
	if main_menu != null and is_instance_valid(main_menu):
		main_menu.visible = true
		var panel_to_open: String = target_panel if not target_panel.is_empty() else "MAIN"
		main_menu.set("current_panel", panel_to_open)
		if panel_to_open == "MAP_SELECTION" and main_menu.get("map_select_row") != null:
			main_menu.set("map_select_row", 1)
		main_menu.queue_redraw()
	MapLoaderScript.get_audio().call("play_music", "superfighters_theme")


func _on_start_match_requested(config: Dictionary) -> void:
	if main_menu != null and is_instance_valid(main_menu):
		main_menu.visible = false
	if match_world != null and is_instance_valid(match_world):
		match_world.visible = true
		match_world.process_mode = Node.PROCESS_MODE_INHERIT
		match_world.call("start_match", config)
		var hud: CanvasLayer = match_world.get("hud_controller") as CanvasLayer
		if hud != null:
			hud.visible = true

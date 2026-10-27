class_name MainMenuController
extends Control
## Authentic Superfighters Y8 Classic Flash Menu & Setup UI (SF-M5 / SF-M16).
## Rebuilds MenuMain.as (Symbol 2316.xml) 1:1 on an 800x600 virtual stage scaled to the viewport:
## - Screen 0 (MAIN / first_choise): 1 PLAYER, 2 PLAYERS, TUTORIAL, SETUP + mode_selection preview
## - Screen 1 (MODE_SELECT / mode_selection): VS, STAGE, SURVIVAL
## - Screen 2 (VS_PLAYER_SETUP / vs_player_setup): P1 & P2 player_plate cards with 54x54 crimson
##   checkered live IDLE character preview, < Character > selector, and colored < Team > selector
## - Screen 3 (NO_BOTS / no_bots): NUMBER OF BOTS [0..7] selector box below player_plates
## - Screen 4 (BOT_SETUP / bot_setup): 6 or 7 COM bot_plate cards with 54x54 live character preview,
##   < Character >, < Team >, < EASY/NORMAL/HARD/EXPERT >, and '- EMPTY -' covers for inactive slots
## - Screen 5 (MAP_SELECTION / map_selection): 280x120 Map Thumbnail Preview + FIGHT / MAP / GAME MODE / RESET
## - Screen 6 (STAGE_SELECT / challenge_selection): 4x3 grid of 12 Stage Map Thumbnails (120x56) + BACK
## - Screen 8 & 9 (SETUP & CONTROLS): Audio/Zoom toggles + P1 & P2 Controls table

const MapLoaderScript = preload("res://game/world/map_loader.gd")
const MatchControllerScript = preload("res://game/core/match_controller.gd")
const _PreloadMugenFighterAdapter = preload("res://game/fighter/mugen_fighter_adapter.gd")

signal start_match_requested(config: Dictionary)

const MENU_ITEMS: Array[String] = [
	"1 PLAYER",
	"2 PLAYERS",
	"TUTORIAL",
	"SETUP",
]

const MODE_ITEMS: Array[String] = [
	"VS",
	"STAGE",
	"SURVIVAL",
]

const ROSTER_IDS: Array[String] = [
	"johnny",
	"boris",
	"agent",
	"hideki",
	"blaire",
	"savage",
	"cruger",
	"ivan",
	"brody",
	"mac",
	"billy",
	"scott",
	"funnyman",
	"jeff",
	"shinobi",
]

const CHAR_CHOICES: Array[String] = [
	"random",
	"johnny",
	"boris",
	"agent",
	"hideki",
	"blaire",
	"savage",
	"cruger",
	"ivan",
	"brody",
	"mac",
	"billy",
	"scott",
	"funnyman",
	"jeff",
	"shinobi",
]

const VS_MAP_IDS: Array[String] = [
	"rooftops",
	"storage",
	"police_station",
	"hazardous",
	"subway",
	"tower",
	"junkyard",
	"cargo",
	"steel_harbor",
]

const MAP_CHOICES: Array[String] = [
	"random",
	"rooftops",
	"storage",
	"police_station",
	"hazardous",
	"subway",
	"tower",
	"junkyard",
	"cargo",
	"steel_harbor",
]

const MAP_DISPLAY_NAMES: Dictionary = {
	"random": "RANDOM",
	"rooftops": "ROOFTOPS",
	"storage": "STORAGE",
	"police_station": "POLICE STATION",
	"hazardous": "HAZARDOUS",
	"subway": "SUBWAY",
	"tower": "TOWER",
	"junkyard": "JUNKYARD",
	"cargo": "CARGO",
	"steel_harbor": "STEEL HARBOR (NEW)",
	"backstreets": "BACKSTREETS",
	"testing_floor": "TESTING FLOOR",
	"survival": "SURVIVAL",
}

const MAP_THUMB_PATHS: Dictionary = {
	"rooftops": "res://assets/maps/Bitmap 2219.png",
	"storage": "res://assets/maps/Bitmap 2212.png",
	"police_station": "res://assets/maps/Bitmap 2217.png",
	"hazardous": "res://assets/maps/Bitmap 2221.png",
	"subway": "res://assets/maps/Bitmap 2213.png",
	"tower": "res://assets/sprites/ui/map_thumb_tower.png",
	"junkyard": "res://assets/maps/Bitmap 2482.png",
	"cargo": "res://assets/maps/Bitmap 2451.png",
	"steel_harbor": "res://assets/maps/steel_harbor_bg.png",
	"backstreets": "res://assets/maps/Bitmap 2233.png",
	"testing_floor": "res://assets/maps/Bitmap 2221.png",
	"survival": "res://assets/maps/Bitmap 2219.png",
}

const TEAM_NAMES: Array[String] = ["-", "TEAM 1", "TEAM 2", "TEAM 3", "TEAM 4"]
const TEAM_COLORS: Array[Color] = [
	Color(1.0, 1.0, 1.0, 1.0),          # 0: Solo (-) White
	Color(0.447, 0.624, 0.812, 1.0),    # 1: TEAM 1 (#729FCF Blue)
	Color(0.937, 0.161, 0.161, 1.0),    # 2: TEAM 2 (#EF2929 Red)
	Color(0.451, 0.824, 0.086, 1.0),    # 3: TEAM 3 (#73D216 Green)
	Color(0.988, 0.914, 0.310, 1.0),    # 4: TEAM 4 (#FCE94F Yellow)
]

const BOT_DIFF_NAMES: Array[String] = ["", "EASY", "NORMAL", "HARD", "EXPERT"]
const GAME_MODE_RULES: Array[String] = [
	"-",
	"FIRST TO 3",
	"FIRST TO 5",
	"FIRST TO 10",
	"BEST OF 3",
	"BEST OF 5",
	"BEST OF 10",
]

# Current active screen:
# "MAIN", "MODE_SELECT", "VS_PLAYER_SETUP" (or "VS_SETUP"), "NO_BOTS", "BOT_SETUP",
# "MAP_SELECTION", "STAGE_SELECT", "SETUP", "CONTROLS", "ROSTER"
var current_panel: String = "MAIN"
var selected_index: int = 0
var selected_mode_idx: int = 0 # 0: VS, 1: STAGE, 2: SURVIVAL

# Player & Mode Setup State
var vs_two_player: bool = false
var selected_game_mode: String = "vs" # "vs", "stage", "survival"
var vs_map_idx: int = 9 # Index into MAP_CHOICES (9 = steel_harbor NEW map default, 1 = rooftops, 0 = random)
var vs_game_rule_idx: int = 0 # Index into GAME_MODE_RULES
var vs_p1_char_idx: int = 1 # Index into CHAR_CHOICES (1 = johnny, 0 = random)
var vs_p2_char_idx: int = 3 # Index into CHAR_CHOICES (3 = agent, 0 = random)
var vs_p1_team: int = 1
var vs_p2_team: int = 2
var active_player_plate: int = 0 # 0 = P1 plate, 1 = P2 plate
var player_plate_row: int = 0 # 0 = Character, 1 = Team

# Bots Setup State (7 Bot Plates cp_1..cp_7 as in MenuMain.as)
var vs_bot_count: int = 1
var vs_bot_diff: int = 2
var bot_configs: Array[Dictionary] = []
var active_bot_plate: int = 0 # 0..6
var bot_plate_row: int = 0 # 0 = Character, 1 = Team, 2 = Difficulty

# Map Selection & Stage Selection State
var map_select_row: int = 0 # 0 = FIGHT, 1 = MAP, 2 = GAME MODE, 3 = RESET
var vs_setup_row: int = 0
var selected_stage: int = 1
var stage_back_selected: bool = false

# Setup & Audio State
var setup_row: int = 0 # 0 = SOUND, 1 = MUSIC, 2 = AUTO ZOOM, 3 = EDIT CONTROLS
var sound_enabled: bool = true
var music_enabled: bool = true
var auto_zoom_enabled: bool = true

# Fonts & Cached Textures
var _font_title: Font = null
var _font_body: Font = null
var _bg_tex: Texture2D = null
var _logo_tex: Texture2D = null
var _arrow_tex: Texture2D = null
var _char_bg_tex: Texture2D = null
var _no_bots_tex: Texture2D = null
var _bot_box_tex: Texture2D = null
var _lock_tex: Texture2D = null
var _hint_left_tex: Texture2D = null
var _hint_right_tex: Texture2D = null

var _anim_accum: float = 0.0
var _idle_frame_idx: int = 1


func _init() -> void:
	_reset_bot_configs()


func _reset_bot_configs() -> void:
	bot_configs.clear()
	var default_chars: Array[int] = [2, 4, 5, 6, 7, 8, 9] # boris, hideki, blaire, savage, cruger, ivan, brody
	for i: int in range(7):
		bot_configs.append({
			"char_idx": default_chars[i % default_chars.size()],
			"team": 0,
			"diff": 2,
		})


func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	var reg: Node = MapLoaderScript.get_registry()
	if reg != null:
		_PreloadMugenFighterAdapter.ensure_registry_integration(reg)
	MapLoaderScript.get_audio()
	_load_menu_assets()
	MapLoaderScript.get_audio().call("play_music", "superfighters_theme")
	set_process(true)
	queue_redraw()


func _process(delta: float) -> void:
	if not visible:
		return
	_anim_accum += delta
	if _anim_accum >= (1.0 / 8.0):
		_anim_accum = fmod(_anim_accum, 1.0 / 8.0)
		var reg: Node = MapLoaderScript.get_registry()
		var idle_frames: Array = reg.call("get_state_frames", "IDLE") as Array if reg != null else []
		var fcount: int = maxi(1, idle_frames.size())
		_idle_frame_idx = (_idle_frame_idx % fcount) + 1
		queue_redraw()


func _load_menu_assets() -> void:
	if ResourceLoader.exists("res://assets/fonts/106_04b03.ttf"):
		_font_body = load("res://assets/fonts/106_04b03.ttf") as Font
	elif ResourceLoader.exists("res://assets/fonts/12_PF Arma Five.ttf"):
		_font_body = load("res://assets/fonts/12_PF Arma Five.ttf") as Font
	if ResourceLoader.exists("res://assets/fonts/31_Capture it.ttf"):
		_font_title = load("res://assets/fonts/31_Capture it.ttf") as Font

	var reg: Node = MapLoaderScript.get_registry()
	_bg_tex = reg.call("load_cached_texture", "res://assets/maps/Bitmap 2219.png") as Texture2D
	if _bg_tex == null:
		_bg_tex = reg.call("load_cached_texture", "res://assets/sprites/ui/MenuBackground.png") as Texture2D
	_logo_tex = reg.call("load_cached_texture", "res://assets/sprites/ui/menu_logo.png") as Texture2D
	if _logo_tex == null:
		_logo_tex = reg.call("load_cached_texture", "res://assets/sprites/ui/GameLogo.png") as Texture2D
	_arrow_tex = reg.call("load_cached_texture", "res://assets/sprites/ui/menu_arrow.png") as Texture2D
	_char_bg_tex = reg.call("load_cached_texture", "res://assets/sprites/ui/menu_char_bg.png") as Texture2D
	_no_bots_tex = reg.call("load_cached_texture", "res://assets/sprites/ui/menu_no_bots.png") as Texture2D
	_bot_box_tex = reg.call("load_cached_texture", "res://assets/sprites/ui/menu_bot_box.png") as Texture2D
	_lock_tex = reg.call("load_cached_texture", "res://assets/sprites/ui/menu_lock.png") as Texture2D
	_hint_left_tex = reg.call("load_cached_texture", "res://assets/sprites/ui/menu_hint_left.png") as Texture2D
	_hint_right_tex = reg.call("load_cached_texture", "res://assets/sprites/ui/menu_hint_right.png") as Texture2D


# ------------------------------------------------------------------------------
# Coordinate Transform Helpers (800x600 Flash Canvas -> Current Viewport)
# ------------------------------------------------------------------------------
func _get_canvas_transform_params() -> Dictionary:
	var vp: Vector2 = get_viewport_rect().size
	if vp.x <= 0.0 or vp.y <= 0.0:
		vp = Vector2(1280.0, 720.0)
	var sc: float = vp.y / 600.0
	var ox: float = (vp.x - 800.0 * sc) * 0.5
	return {"vp": vp, "scale": sc, "ox": ox}


func _rect800(x: float, y: float, w: float, h: float) -> Rect2:
	var p: Dictionary = _get_canvas_transform_params()
	var sc: float = float(p["scale"])
	var ox: float = float(p["ox"])
	return Rect2(ox + x * sc, y * sc, w * sc, h * sc)


func _pt800(x: float, y: float) -> Vector2:
	var p: Dictionary = _get_canvas_transform_params()
	var sc: float = float(p["scale"])
	var ox: float = float(p["ox"])
	return Vector2(ox + x * sc, y * sc)


func _to_canvas800(screen_pt: Vector2) -> Vector2:
	var p: Dictionary = _get_canvas_transform_params()
	var sc: float = maxf(0.001, float(p["scale"]))
	var ox: float = float(p["ox"])
	return Vector2((screen_pt.x - ox) / sc, screen_pt.y / sc)


# ------------------------------------------------------------------------------
# Input Handling (Keyboard + Mouse Clicks across all Y8 Menu Screens)
# ------------------------------------------------------------------------------
func _unhandled_input(event: InputEvent) -> void:
	if not visible:
		return
	if event is InputEventMouseButton:
		var mb: InputEventMouseButton = event as InputEventMouseButton
		if mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT:
			_handle_mouse_click(_to_canvas800(mb.position))
			return
	if not (event is InputEventKey):
		return
	var kev: InputEventKey = event as InputEventKey
	if not kev.pressed or kev.echo:
		return

	var key: Key = kev.keycode if kev.keycode != KEY_NONE else kev.physical_keycode
	match current_panel:
		"MAIN":
			_handle_main_input(key)
		"MODE_SELECT":
			_handle_mode_select_input(key)
		"VS_PLAYER_SETUP", "VS_SETUP":
			_handle_vs_player_setup_input(key)
		"NO_BOTS":
			_handle_no_bots_input(key)
		"BOT_SETUP":
			_handle_bot_setup_input(key)
		"MAP_SELECTION":
			_handle_map_selection_input(key)
		"STAGE_SELECT":
			_handle_stage_select_input(key)
		"SETUP":
			_handle_setup_input(key)
		"ROSTER", "CONTROLS":
			if _is_confirm_key(key) or _is_cancel_key(key):
				MapLoaderScript.play_sfx("cancel")
				current_panel = "SETUP" if current_panel == "CONTROLS" else "MAIN"
				queue_redraw()


func _is_up_key(key: Key) -> bool:
	return key in [KEY_UP, KEY_W]


func _is_down_key(key: Key) -> bool:
	return key in [KEY_DOWN, KEY_S]


func _is_left_key(key: Key) -> bool:
	return key in [KEY_LEFT, KEY_A]


func _is_right_key(key: Key) -> bool:
	return key in [KEY_RIGHT, KEY_D]


func _is_confirm_key(key: Key) -> bool:
	return key in [KEY_ENTER, KEY_KP_ENTER, KEY_SPACE, KEY_N, KEY_KP_1, KEY_1, KEY_J]


func _is_cancel_key(key: Key) -> bool:
	return key in [KEY_ESCAPE, KEY_BACKSPACE, KEY_M, KEY_KP_2, KEY_2, KEY_K]


func _handle_main_input(key: Key) -> void:
	if _is_up_key(key):
		selected_index = (selected_index - 1 + MENU_ITEMS.size()) % MENU_ITEMS.size()
		MapLoaderScript.play_sfx("aim_small")
		queue_redraw()
	elif _is_down_key(key):
		selected_index = (selected_index + 1) % MENU_ITEMS.size()
		MapLoaderScript.play_sfx("aim_small")
		queue_redraw()
	elif _is_confirm_key(key):
		MapLoaderScript.play_sfx("accept")
		_activate_first_choice(selected_index)


func _activate_first_choice(idx: int) -> void:
	selected_index = clampi(idx, 0, MENU_ITEMS.size() - 1)
	match selected_index:
		0:
			# 1 PLAYER -> Mode Selection
			vs_two_player = false
			current_panel = "MODE_SELECT"
			queue_redraw()
		1:
			# 2 PLAYERS -> Mode Selection
			vs_two_player = true
			current_panel = "MODE_SELECT"
			queue_redraw()
		2:
			# TUTORIAL -> Instant 1P Tutorial Match on Storage
			start_match_requested.emit({
				"mode": "vs",
				"map_id": "storage",
				"two_player": false,
				"p1_char": "johnny",
				"p1_team": 1,
				"bot_count": 1,
				"bot_difficulty": 1,
				"bot_configs": [{"char": "boris", "team": 2, "diff": 1}],
			})
		3:
			# SETUP
			current_panel = "SETUP"
			setup_row = 0
			queue_redraw()


## Programmatic helper preserved for automated test suites (e.g. test_m4_m5_maps_props_ai_and_modes.gd).
func activate_menu_option(idx: int) -> void:
	match idx:
		0:
			vs_two_player = true
			start_match_requested.emit({
				"mode": "vs",
				"map_id": "rooftops",
				"two_player": true,
				"p1_char": _resolve_char_choice(vs_p1_char_idx),
				"p2_char": _resolve_char_choice(vs_p2_char_idx),
				"p1_team": vs_p1_team,
				"p2_team": vs_p2_team,
				"bot_count": 0,
				"bot_difficulty": 2,
			})
		1:
			current_panel = "VS_PLAYER_SETUP"
			active_player_plate = 0
			player_plate_row = 0
			queue_redraw()
		2:
			selected_game_mode = "stage"
			current_panel = "STAGE_SELECT"
			queue_redraw()
		3:
			selected_game_mode = "survival"
			start_match_requested.emit({
				"mode": "survival",
				"map_id": "survival",
				"two_player": vs_two_player,
				"p1_char": _resolve_char_choice(vs_p1_char_idx),
				"p2_char": _resolve_char_choice(vs_p2_char_idx),
				"bot_difficulty": 2,
			})
		4:
			current_panel = "ROSTER"
			queue_redraw()
		5:
			current_panel = "CONTROLS"
			queue_redraw()


func _handle_mode_select_input(key: Key) -> void:
	if _is_cancel_key(key):
		MapLoaderScript.play_sfx("cancel")
		current_panel = "MAIN"
		queue_redraw()
		return
	if _is_up_key(key):
		selected_mode_idx = (selected_mode_idx - 1 + MODE_ITEMS.size()) % MODE_ITEMS.size()
		MapLoaderScript.play_sfx("aim_small")
		queue_redraw()
	elif _is_down_key(key):
		selected_mode_idx = (selected_mode_idx + 1) % MODE_ITEMS.size()
		MapLoaderScript.play_sfx("aim_small")
		queue_redraw()
	elif _is_confirm_key(key):
		MapLoaderScript.play_sfx("accept")
		_enter_selected_mode(selected_mode_idx)


func _enter_selected_mode(mode_idx: int) -> void:
	selected_mode_idx = clampi(mode_idx, 0, MODE_ITEMS.size() - 1)
	match selected_mode_idx:
		0:
			selected_game_mode = "vs"
			if vs_two_player:
				vs_p1_team = 0
				vs_p2_team = 0
				vs_bot_count = 0
			else:
				vs_p1_team = 0
				vs_bot_count = maxi(1, vs_bot_count)
		1:
			selected_game_mode = "stage"
			vs_p1_team = 1
			vs_p2_team = 1
		2:
			selected_game_mode = "survival"
			vs_p1_team = 1
			vs_p2_team = 1
	active_player_plate = 0
	player_plate_row = 0
	current_panel = "VS_PLAYER_SETUP"
	queue_redraw()


func _handle_vs_player_setup_input(key: Key) -> void:
	var team_locked: bool = selected_game_mode in ["stage", "survival"]
	if _is_cancel_key(key):
		MapLoaderScript.play_sfx("cancel")
		if vs_two_player and active_player_plate == 1:
			active_player_plate = 0
			player_plate_row = 0
		else:
			current_panel = "MODE_SELECT"
		queue_redraw()
		return

	if _is_up_key(key) or _is_down_key(key):
		if not team_locked:
			player_plate_row = 1 - player_plate_row
			MapLoaderScript.play_sfx("aim_small")
			queue_redraw()
	elif _is_left_key(key) or _is_right_key(key):
		var step: int = -1 if _is_left_key(key) else 1
		if active_player_plate == 0:
			if player_plate_row == 0 or team_locked:
				vs_p1_char_idx = (vs_p1_char_idx + step + CHAR_CHOICES.size()) % CHAR_CHOICES.size()
			else:
				vs_p1_team = (vs_p1_team + step + TEAM_NAMES.size()) % TEAM_NAMES.size()
		else:
			if player_plate_row == 0 or team_locked:
				vs_p2_char_idx = (vs_p2_char_idx + step + CHAR_CHOICES.size()) % CHAR_CHOICES.size()
			else:
				vs_p2_team = (vs_p2_team + step + TEAM_NAMES.size()) % TEAM_NAMES.size()
		MapLoaderScript.play_sfx("aim_small")
		queue_redraw()
	elif _is_confirm_key(key):
		MapLoaderScript.play_sfx("accept")
		if vs_two_player and active_player_plate == 0:
			active_player_plate = 1
			player_plate_row = 0
			queue_redraw()
			return
		_advance_from_player_plates()


func _advance_from_player_plates() -> void:
	if selected_game_mode == "stage":
		current_panel = "STAGE_SELECT"
		stage_back_selected = false
		queue_redraw()
	elif selected_game_mode == "survival":
		start_match_requested.emit({
			"mode": "survival",
			"map_id": "survival",
			"two_player": vs_two_player,
			"p1_char": _resolve_char_choice(vs_p1_char_idx),
			"p2_char": _resolve_char_choice(vs_p2_char_idx),
			"p1_team": 1,
			"p2_team": 1,
			"bot_difficulty": 2,
		})
	else:
		# VS Mode -> Open NUMBER OF BOTS box below player plates
		var min_bots: int = _get_min_vs_bots()
		var max_bots: int = _get_max_vs_bots()
		vs_bot_count = clampi(vs_bot_count, min_bots, max_bots)
		current_panel = "NO_BOTS"
		queue_redraw()


func _get_min_vs_bots() -> int:
	if not vs_two_player:
		return 1
	if vs_p1_team != 0 and vs_p1_team == vs_p2_team:
		return 1
	return 0


func _get_max_vs_bots() -> int:
	return 6 if vs_two_player else 7


func _handle_no_bots_input(key: Key) -> void:
	if _is_cancel_key(key):
		MapLoaderScript.play_sfx("cancel")
		current_panel = "VS_PLAYER_SETUP"
		active_player_plate = 1 if vs_two_player else 0
		queue_redraw()
		return
	var min_bots: int = _get_min_vs_bots()
	var max_bots: int = _get_max_vs_bots()
	if _is_left_key(key) or _is_down_key(key):
		vs_bot_count = clampi(vs_bot_count - 1, min_bots, max_bots)
		MapLoaderScript.play_sfx("aim_small")
		queue_redraw()
	elif _is_right_key(key) or _is_up_key(key):
		vs_bot_count = clampi(vs_bot_count + 1, min_bots, max_bots)
		MapLoaderScript.play_sfx("aim_small")
		queue_redraw()
	elif _is_confirm_key(key):
		MapLoaderScript.play_sfx("accept")
		if vs_bot_count > 0:
			active_bot_plate = 0
			bot_plate_row = 0
			current_panel = "BOT_SETUP"
		else:
			map_select_row = 0
			current_panel = "MAP_SELECTION"
		queue_redraw()


func _handle_bot_setup_input(key: Key) -> void:
	if _is_cancel_key(key):
		MapLoaderScript.play_sfx("cancel")
		if active_bot_plate > 0:
			active_bot_plate -= 1
			bot_plate_row = 0
		else:
			current_panel = "NO_BOTS"
		queue_redraw()
		return

	if _is_up_key(key):
		bot_plate_row = (bot_plate_row - 1 + 3) % 3
		MapLoaderScript.play_sfx("aim_small")
		queue_redraw()
	elif _is_down_key(key):
		bot_plate_row = (bot_plate_row + 1) % 3
		MapLoaderScript.play_sfx("aim_small")
		queue_redraw()
	elif _is_left_key(key) or _is_right_key(key):
		var step: int = -1 if _is_left_key(key) else 1
		var bcfg: Dictionary = bot_configs[active_bot_plate]
		match bot_plate_row:
			0:
				var cidx: int = int(bcfg.get("char_idx", 0))
				bcfg["char_idx"] = (cidx + step + CHAR_CHOICES.size()) % CHAR_CHOICES.size()
			1:
				var tidx: int = int(bcfg.get("team", 0))
				bcfg["team"] = (tidx + step + TEAM_NAMES.size()) % TEAM_NAMES.size()
			2:
				var didx: int = int(bcfg.get("diff", 2))
				bcfg["diff"] = clampi(didx + step, 1, 4)
				vs_bot_diff = int(bcfg["diff"])
		MapLoaderScript.play_sfx("aim_small")
		queue_redraw()
	elif _is_confirm_key(key):
		MapLoaderScript.play_sfx("accept")
		if active_bot_plate + 1 < vs_bot_count:
			active_bot_plate += 1
			bot_plate_row = 0
		else:
			map_select_row = 0
			current_panel = "MAP_SELECTION"
		queue_redraw()


func _handle_map_selection_input(key: Key) -> void:
	if _is_cancel_key(key):
		MapLoaderScript.play_sfx("cancel")
		if vs_bot_count > 0:
			active_bot_plate = vs_bot_count - 1
			bot_plate_row = 0
			current_panel = "BOT_SETUP"
		else:
			current_panel = "NO_BOTS"
		queue_redraw()
		return

	if _is_up_key(key):
		map_select_row = (map_select_row - 1 + 4) % 4
		MapLoaderScript.play_sfx("aim_small")
		queue_redraw()
	elif _is_down_key(key):
		map_select_row = (map_select_row + 1) % 4
		MapLoaderScript.play_sfx("aim_small")
		queue_redraw()
	elif _is_left_key(key) or _is_right_key(key):
		var step: int = -1 if _is_left_key(key) else 1
		if map_select_row == 1:
			vs_map_idx = (vs_map_idx + step + MAP_CHOICES.size()) % MAP_CHOICES.size()
			MapLoaderScript.play_sfx("aim_small")
			queue_redraw()
		elif map_select_row == 2:
			vs_game_rule_idx = (vs_game_rule_idx + step + GAME_MODE_RULES.size()) % GAME_MODE_RULES.size()
			MapLoaderScript.play_sfx("aim_small")
			queue_redraw()
	elif _is_confirm_key(key):
		if map_select_row == 0 or map_select_row == 1 or map_select_row == 2:
			MapLoaderScript.play_sfx("accept")
			_emit_vs_match_start()
		elif map_select_row == 3:
			# RESET -> Return to VS_PLAYER_SETUP with defaults
			MapLoaderScript.play_sfx("cancel")
			_reset_bot_configs()
			vs_p1_char_idx = 0
			vs_p2_char_idx = 0
			vs_p1_team = 0
			vs_p2_team = 0
			vs_map_idx = 0
			vs_game_rule_idx = 0
			active_player_plate = 0
			player_plate_row = 0
			current_panel = "VS_PLAYER_SETUP"
			queue_redraw()


func _emit_vs_match_start() -> void:
	var compiled_bots: Array[Dictionary] = []
	for i: int in range(vs_bot_count):
		var bc: Dictionary = bot_configs[i]
		compiled_bots.append({
			"char": _resolve_char_choice(int(bc.get("char_idx", 0))),
			"team": int(bc.get("team", 0)),
			"diff": clampi(int(bc.get("diff", 2)), 1, 4),
		})
	var chosen_map: String = MAP_CHOICES[clampi(vs_map_idx, 0, MAP_CHOICES.size() - 1)]
	if chosen_map == "random":
		chosen_map = VS_MAP_IDS[randi() % VS_MAP_IDS.size()]
	start_match_requested.emit({
		"mode": "vs",
		"map_id": chosen_map,
		"two_player": vs_two_player,
		"p1_char": _resolve_char_choice(vs_p1_char_idx),
		"p2_char": _resolve_char_choice(vs_p2_char_idx),
		"p1_team": vs_p1_team,
		"p2_team": vs_p2_team,
		"bot_count": vs_bot_count,
		"bot_difficulty": vs_bot_diff,
		"bot_configs": compiled_bots,
		"score_limit_mode": GAME_MODE_RULES[vs_game_rule_idx],
	})


func _resolve_char_choice(choice_idx: int) -> String:
	var clamped: int = clampi(choice_idx, 0, CHAR_CHOICES.size() - 1)
	var cid: String = CHAR_CHOICES[clamped]
	if cid == "random":
		return ROSTER_IDS[randi() % ROSTER_IDS.size()]
	return cid


func _handle_stage_select_input(key: Key) -> void:
	if _is_cancel_key(key):
		MapLoaderScript.play_sfx("cancel")
		current_panel = "VS_PLAYER_SETUP"
		active_player_plate = 1 if vs_two_player else 0
		queue_redraw()
		return
	var col: int = (selected_stage - 1) % 4
	var row: int = (selected_stage - 1) / 4
	if _is_left_key(key) and not stage_back_selected:
		col = (col + 3) % 4
		selected_stage = row * 4 + col + 1
		MapLoaderScript.play_sfx("aim_small")
		queue_redraw()
	elif _is_right_key(key) and not stage_back_selected:
		col = (col + 1) % 4
		selected_stage = row * 4 + col + 1
		MapLoaderScript.play_sfx("aim_small")
		queue_redraw()
	elif _is_up_key(key):
		if stage_back_selected:
			stage_back_selected = false
			row = 2
		else:
			if row == 0:
				stage_back_selected = true
			else:
				row -= 1
		selected_stage = row * 4 + col + 1
		MapLoaderScript.play_sfx("aim_small")
		queue_redraw()
	elif _is_down_key(key):
		if stage_back_selected:
			stage_back_selected = false
			row = 0
		else:
			if row == 2:
				stage_back_selected = true
			else:
				row += 1
		selected_stage = row * 4 + col + 1
		MapLoaderScript.play_sfx("aim_small")
		queue_redraw()
	elif _is_confirm_key(key):
		if stage_back_selected:
			MapLoaderScript.play_sfx("cancel")
			stage_back_selected = false
			current_panel = "VS_PLAYER_SETUP"
			queue_redraw()
		else:
			MapLoaderScript.play_sfx("accept")
			start_match_requested.emit({
				"mode": "stage",
				"stage_level": selected_stage,
				"two_player": vs_two_player,
				"p1_char": _resolve_char_choice(vs_p1_char_idx),
				"p2_char": _resolve_char_choice(vs_p2_char_idx),
			})


func _handle_setup_input(key: Key) -> void:
	if _is_cancel_key(key):
		MapLoaderScript.play_sfx("cancel")
		current_panel = "MAIN"
		queue_redraw()
		return
	if _is_up_key(key):
		setup_row = (setup_row - 1 + 4) % 4
		MapLoaderScript.play_sfx("aim_small")
		queue_redraw()
	elif _is_down_key(key):
		setup_row = (setup_row + 1) % 4
		MapLoaderScript.play_sfx("aim_small")
		queue_redraw()
	elif _is_left_key(key) or _is_right_key(key) or _is_confirm_key(key):
		match setup_row:
			0:
				sound_enabled = not sound_enabled
				MapLoaderScript.play_sfx("aim_small")
			1:
				music_enabled = not music_enabled
				MapLoaderScript.play_sfx("aim_small")
			2:
				auto_zoom_enabled = not auto_zoom_enabled
				MapLoaderScript.play_sfx("aim_small")
			3:
				if _is_confirm_key(key):
					MapLoaderScript.play_sfx("accept")
					current_panel = "CONTROLS"
		queue_redraw()


func _handle_mouse_click(pt: Vector2) -> void:
	# Allow clicking items in first_choise or mode_selection when on MAIN / MODE_SELECT / SETUP
	if current_panel in ["MAIN", "MODE_SELECT", "SETUP"]:
		var first_box: Rect2 = Rect2(0.0, 168.0, 174.0, 149.0)
		if first_box.has_point(pt):
			var idx: int = clampi(int((pt.y - 178.0) / 31.0), 0, 3)
			MapLoaderScript.play_sfx("accept")
			_activate_first_choice(idx)
			return
		var mode_box: Rect2 = Rect2(183.0, 168.0, 195.0, 116.0)
		if current_panel in ["MAIN", "MODE_SELECT"] and mode_box.has_point(pt):
			var midx: int = clampi(int((pt.y - 180.0) / 31.0), 0, 2)
			MapLoaderScript.play_sfx("accept")
			_enter_selected_mode(midx)
			return
		if current_panel == "SETUP":
			var sbox: Rect2 = Rect2(183.0, 241.0, 225.0, 149.0)
			if sbox.has_point(pt):
				setup_row = clampi(int((pt.y - 252.0) / 31.0), 0, 3)
				_handle_setup_input(KEY_ENTER)
				return

	if current_panel in ["VS_PLAYER_SETUP", "VS_SETUP", "NO_BOTS", "BOT_SETUP"]:
		# Click on Player Plates
		var p1_x: float = 265.0 if vs_two_player else 342.0
		var p1_rect: Rect2 = Rect2(p1_x, 123.0, 134.0, 138.0)
		if p1_rect.has_point(pt):
			current_panel = "VS_PLAYER_SETUP"
			active_player_plate = 0
			var step_p1: int = -1 if pt.x < p1_x + 67.0 else 1
			if pt.y >= 123.0 + 108.0 and not (selected_game_mode in ["stage", "survival"]):
				player_plate_row = 1
				vs_p1_team = (vs_p1_team + step_p1 + TEAM_NAMES.size()) % TEAM_NAMES.size()
			else:
				player_plate_row = 0
				vs_p1_char_idx = (vs_p1_char_idx + step_p1 + CHAR_CHOICES.size()) % CHAR_CHOICES.size()
			MapLoaderScript.play_sfx("aim_small")
			queue_redraw()
			return
		if vs_two_player:
			var p2_rect: Rect2 = Rect2(419.0, 123.0, 134.0, 138.0)
			if p2_rect.has_point(pt):
				current_panel = "VS_PLAYER_SETUP"
				active_player_plate = 1
				var step_p2: int = -1 if pt.x < 419.0 + 67.0 else 1
				if pt.y >= 123.0 + 108.0 and not (selected_game_mode in ["stage", "survival"]):
					player_plate_row = 1
					vs_p2_team = (vs_p2_team + step_p2 + TEAM_NAMES.size()) % TEAM_NAMES.size()
				else:
					player_plate_row = 0
					vs_p2_char_idx = (vs_p2_char_idx + step_p2 + CHAR_CHOICES.size()) % CHAR_CHOICES.size()
				MapLoaderScript.play_sfx("aim_small")
				queue_redraw()
				return

		# Click on NUMBER OF BOTS box
		if current_panel == "NO_BOTS":
			var nb_rect: Rect2 = Rect2(288.0, 273.0, 242.0, 72.0)
			if nb_rect.has_point(pt):
				var clicked_num: int = clampi(int(round((pt.x - (288.0 + 34.0)) / 25.0)), _get_min_vs_bots(), _get_max_vs_bots())
				vs_bot_count = clicked_num
				MapLoaderScript.play_sfx("accept")
				_handle_no_bots_input(KEY_ENTER)
				return

		# Click on NEXT / CONTINUE button at bottom right
		var next_rect: Rect2 = Rect2(640.0, 534.0, 140.0, 32.0)
		if next_rect.has_point(pt):
			MapLoaderScript.play_sfx("accept")
			if current_panel in ["VS_PLAYER_SETUP", "VS_SETUP"]:
				_advance_from_player_plates()
			elif current_panel == "NO_BOTS":
				_handle_no_bots_input(KEY_ENTER)
			elif current_panel == "BOT_SETUP":
				map_select_row = 0
				current_panel = "MAP_SELECTION"
				queue_redraw()
			return

		# Click on Bot Plates in BOT_SETUP
		if current_panel == "BOT_SETUP":
			var bot_rects: Array[Rect2] = _get_bot_plate_rects800()
			for bi: int in range(mini(vs_bot_count, bot_rects.size())):
				var br: Rect2 = bot_rects[bi]
				if br.has_point(pt):
					active_bot_plate = bi
					var step_b: int = -1 if pt.x < br.position.x + br.size.x * 0.5 else 1
					var local_y: float = pt.y - br.position.y
					var bcfg: Dictionary = bot_configs[bi]
					if local_y >= 126.0:
						bot_plate_row = 2
						bcfg["diff"] = clampi(int(bcfg.get("diff", 2)) + step_b, 1, 4)
						vs_bot_diff = int(bcfg["diff"])
					elif local_y >= 106.0:
						bot_plate_row = 1
						bcfg["team"] = (int(bcfg.get("team", 0)) + step_b + TEAM_NAMES.size()) % TEAM_NAMES.size()
					else:
						bot_plate_row = 0
						bcfg["char_idx"] = (int(bcfg.get("char_idx", 0)) + step_b + CHAR_CHOICES.size()) % CHAR_CHOICES.size()
					MapLoaderScript.play_sfx("aim_small")
					queue_redraw()
					return

	if current_panel == "MAP_SELECTION":
		var mbox: Rect2 = Rect2(225.0, 185.0, 350.0, 280.0)
		if mbox.has_point(pt):
			if pt.y >= 338.0 and pt.y < 364.0:
				map_select_row = 0
				_handle_map_selection_input(KEY_ENTER)
			elif pt.y >= 364.0 and pt.y < 390.0:
				map_select_row = 1
				var step_m: int = -1 if pt.x < 440.0 else 1
				vs_map_idx = (vs_map_idx + step_m + MAP_CHOICES.size()) % MAP_CHOICES.size()
				MapLoaderScript.play_sfx("aim_small")
				queue_redraw()
			elif pt.y >= 390.0 and pt.y < 416.0:
				map_select_row = 2
				var step_g: int = -1 if pt.x < 440.0 else 1
				vs_game_rule_idx = (vs_game_rule_idx + step_g + GAME_MODE_RULES.size()) % GAME_MODE_RULES.size()
				MapLoaderScript.play_sfx("aim_small")
				queue_redraw()
			elif pt.y >= 416.0:
				map_select_row = 3
				_handle_map_selection_input(KEY_ENTER)
			return

	if current_panel == "STAGE_SELECT":
		for i: int in range(12):
			var c: int = i % 4
			var r: int = i / 4
			var srect: Rect2 = Rect2(167.0 + float(c) * 133.0, 216.0 + float(r) * 72.0, 120.0, 56.0)
			if srect.has_point(pt):
				selected_stage = i + 1
				stage_back_selected = false
				MapLoaderScript.play_sfx("accept")
				_handle_stage_select_input(KEY_ENTER)
				return
		if Rect2(350.0, 448.0, 154.0, 32.0).has_point(pt):
			stage_back_selected = true
			_handle_stage_select_input(KEY_ENTER)
			return


# ------------------------------------------------------------------------------
# Authentic Superfighters Y8 Drawing (Symbol 2316.xml & MenuMain.as)
# ------------------------------------------------------------------------------
func _draw() -> void:
	var params: Dictionary = _get_canvas_transform_params()
	var vp: Vector2 = params["vp"] as Vector2
	var sc: float = float(params["scale"])
	var font: Font = _font_body if _font_body != null else ThemeDB.fallback_font

	# 1. Full-viewport dark stage background + arena silhouette
	draw_rect(Rect2(Vector2.ZERO, vp), Color(0.05, 0.05, 0.06, 1.0), true)
	if _bg_tex != null:
		draw_texture_rect(_bg_tex, _rect800(0.0, 118.0, 800.0, 458.0), false, Color(0.68, 0.70, 0.74, 0.88))

	# 2. Fixed Top Black Bar (y = 0..118) & Bottom Black Bar (y = 576..600) spanning full viewport width
	draw_rect(Rect2(0.0, 0.0, vp.x, 118.0 * sc), Color.BLACK, true)
	draw_rect(Rect2(0.0, 576.0 * sc, vp.x, vp.y - 576.0 * sc), Color.BLACK, true)

	# 3. Authentic SUPERFIGHTERS Pixel Logo at (159, 16) size 482x98
	if _logo_tex != null:
		draw_texture_rect(_logo_tex, _rect800(159.0, 16.0, 482.0, 98.0), false, Color.WHITE)
	else:
		var tfont: Font = _font_title if _font_title != null else font
		_draw_text800(tfont, 0.0, 74.0, 800.0, "SUPERFIGHTERS", 36, Color(0.88, 0.18, 0.14, 1.0), HORIZONTAL_ALIGNMENT_CENTER)

	# 4. Fixed Bottom-Left Credits (only on MAIN / MODE_SELECT / SETUP screens, just like Symbol 2316.xml)
	if current_panel in ["MAIN", "MODE_SELECT", "SETUP"]:
		_draw_credits800(font)

	# 5. Render Active Screen Hierarchy (with authentic parent panel dimming)
	match current_panel:
		"MAIN":
			_draw_first_choice_box(font, false)
			_draw_mode_selection_box(font, true)
		"MODE_SELECT":
			_draw_first_choice_box(font, true)
			_draw_mode_selection_box(font, false)
		"SETUP":
			_draw_first_choice_box(font, true)
			_draw_setup_box(font)
		"VS_PLAYER_SETUP", "VS_SETUP":
			_draw_player_plates(font, false)
			if selected_game_mode == "vs":
				_draw_bot_plates_grid(font, true)
			_draw_navigation_footer_box(font, "SELECT CHARACTER & TEAM  —  PRESS [SPACE / ENTER] FOR NEXT")
		"NO_BOTS":
			_draw_player_plates(font, true)
			_draw_no_bots_box(font)
			_draw_navigation_footer_box(font, "CHOOSE NUMBER OF BOTS (0.." + str(_get_max_vs_bots()) + ")  —  PRESS [SPACE / ENTER] TO CONFIRM")
		"BOT_SETUP":
			_draw_player_plates(font, true)
			_draw_bot_plates_grid(font, false)
			_draw_navigation_footer_box(font, "CONFIGURE BOT " + str(active_bot_plate + 1) + "/" + str(vs_bot_count) + "  —  PRESS [SPACE / ENTER] FOR NEXT")
		"MAP_SELECTION":
			_draw_player_plates(font, true)
			if vs_bot_count > 0:
				_draw_bot_plates_grid(font, true)
			_draw_map_selection_box(font)
		"STAGE_SELECT":
			_draw_player_plates(font, true)
			_draw_stage_select_box(font)
		"CONTROLS":
			_draw_controls_box(font)
		"ROSTER":
			_draw_roster_box(font)

	# 6. Fixed Bottom Black Bar (y = 576..600) & Control Hints drawn on top so cards never overlap footer
	draw_rect(Rect2(0.0, 576.0 * sc, vp.x, vp.y - 576.0 * sc), Color.BLACK, true)
	if _hint_left_tex != null and _hint_right_tex != null:
		draw_texture_rect(_hint_left_tex, _rect800(402.0, 578.0, 181.0, 22.0), false, Color.WHITE)
		draw_texture_rect(_hint_right_tex, _rect800(572.0, 578.0, 228.0, 22.0), false, Color.WHITE)
	else:
		_draw_text800(
			font,
			16.0,
			592.0,
			768.0,
			"NAVIGATE: ARROWS / WASD   |   SELECT: ENTER / SPACE / NUM1 / J   |   BACK: ESC / NUM2 / K",
			8,
			Color(0.82, 0.82, 0.82, 1.0),
			HORIZONTAL_ALIGNMENT_RIGHT
		)
	if current_panel in ["VS_PLAYER_SETUP", "VS_SETUP", "NO_BOTS", "BOT_SETUP"]:
		_draw_text800(font, 16.0, 592.0, 380.0, _get_footer_hint_text(), 8, Color(0.95, 0.88, 0.38, 1.0), HORIZONTAL_ALIGNMENT_LEFT)


func _draw_y8_box800(x: float, y: float, w: float, h: float, dimmed: bool = false) -> Rect2:
	var r: Rect2 = _rect800(x, y, w, h)
	draw_rect(r, Color.BLACK, true)
	draw_rect(r, Color(0.45, 0.45, 0.45, 1.0) if dimmed else Color.WHITE, false, 1.0)
	return r


func _draw_dim_overlay800(x: float, y: float, w: float, h: float, alpha: float = 0.52) -> void:
	draw_rect(_rect800(x + 1.0, y + 1.0, w - 2.0, h - 2.0), Color(0.0, 0.0, 0.0, alpha), true)


func _draw_text800(
	font: Font,
	x: float,
	baseline_y: float,
	width: float,
	text: String,
	size_800: int = 8,
	color: Color = Color.WHITE,
	align: HorizontalAlignment = HORIZONTAL_ALIGNMENT_LEFT,
	shadow: bool = true
) -> void:
	var p: Dictionary = _get_canvas_transform_params()
	var sc: float = float(p["scale"])
	var pos: Vector2 = _pt800(x, baseline_y)
	var fsize: int = maxi(8, int(round(float(size_800) * sc)))
	var w_sc: float = width * sc
	if shadow:
		draw_string(font, pos + Vector2(1.0 * sc, 1.0 * sc), text, align, w_sc, fsize, Color(0.0, 0.0, 0.0, color.a))
	draw_string(font, pos, text, align, w_sc, fsize, color)


func _draw_arrow800(x: float, y: float, point_left: bool = true, color: Color = Color.WHITE) -> void:
	var r: Rect2 = _rect800(x, y, 8.0, 14.0)
	if _arrow_tex != null:
		if point_left:
			draw_texture_rect(_arrow_tex, r, false, color)
		else:
			var flipped: Rect2 = Rect2(r.position.x + r.size.x, r.position.y, -r.size.x, r.size.y)
			draw_texture_rect(_arrow_tex, flipped, false, color)
	else:
		var pts: PackedVector2Array
		if point_left:
			pts = PackedVector2Array([
				Vector2(r.end.x, r.position.y),
				Vector2(r.position.x, r.position.y + r.size.y * 0.5),
				Vector2(r.end.x, r.end.y),
			])
		else:
			pts = PackedVector2Array([
				Vector2(r.position.x, r.position.y),
				Vector2(r.end.x, r.position.y + r.size.y * 0.5),
				Vector2(r.position.x, r.end.y),
			])
		draw_colored_polygon(pts, color)


func _draw_credits800(font: Font) -> void:
	var c_white: Color = Color(0.92, 0.92, 0.92, 0.95)
	var c_gray: Color = Color(0.62, 0.62, 0.62, 0.95)
	_draw_text800(font, 12.0, 429.0, 260.0, "JOHAN HJARPE", 8, c_white)
	_draw_text800(font, 12.0, 444.0, 260.0, "Design, Art", 8, c_gray)
	_draw_text800(font, 12.0, 474.0, 260.0, "ALEXANDER SIIGUR", 8, c_white)
	_draw_text800(font, 12.0, 489.0, 260.0, "Program", 8, c_gray)
	_draw_text800(font, 12.0, 519.0, 260.0, "HZLANCER", 8, c_white)
	_draw_text800(font, 12.0, 534.0, 260.0, "Music", 8, c_gray)
	_draw_text800(font, 12.0, 563.0, 320.0, "mythologicinteractive.com", 8, c_white)


# ------------------------------------------------------------------------------
# Screen 0 & 1: first_choise (0, 168, 174, 149) & mode_selection (183, 168, 195, 116)
# ------------------------------------------------------------------------------
func _draw_first_choice_box(font: Font, dimmed: bool) -> void:
	_draw_y8_box800(0.0, 168.0, 174.0, 149.0, dimmed)
	for i: int in range(MENU_ITEMS.size()):
		var by: float = 197.0 + float(i) * 31.0
		_draw_text800(font, 22.0, by, 128.0, MENU_ITEMS[i], 8, Color.WHITE)
		if i == selected_index:
			_draw_arrow800(152.5, by - 11.0, true, Color.WHITE)
	if dimmed:
		_draw_dim_overlay800(0.0, 168.0, 174.0, 149.0, 0.55)


func _draw_mode_selection_box(font: Font, dimmed: bool) -> void:
	_draw_y8_box800(183.0, 168.0, 195.0, 116.0, dimmed)
	for i: int in range(MODE_ITEMS.size()):
		var by: float = 197.0 + float(i) * 31.0
		_draw_text800(font, 206.0, by, 140.0, MODE_ITEMS[i], 8, Color.WHITE)
		if not dimmed and i == selected_mode_idx:
			_draw_arrow800(355.6, by - 11.0, true, Color.WHITE)
	if dimmed:
		_draw_dim_overlay800(183.0, 168.0, 195.0, 116.0, 0.55)


# ------------------------------------------------------------------------------
# Screen 2: vs_player_setup (p1_plate & p2_plate at y = 123, size 134 x 138)
# ------------------------------------------------------------------------------
func _draw_player_plates(font: Font, dimmed: bool) -> void:
	if vs_two_player:
		var p1_dim: bool = dimmed or (current_panel in ["VS_PLAYER_SETUP", "VS_SETUP"] and active_player_plate != 0)
		var p2_dim: bool = dimmed or (current_panel in ["VS_PLAYER_SETUP", "VS_SETUP"] and active_player_plate != 1)
		_draw_single_player_plate(font, 265.0, 123.0, 0, "PLAYER 1", TEAM_COLORS[1], vs_p1_char_idx, vs_p1_team, not p1_dim, p1_dim)
		_draw_single_player_plate(font, 419.0, 123.0, 1, "PLAYER 2", TEAM_COLORS[2], vs_p2_char_idx, vs_p2_team, not p2_dim, p2_dim)
	else:
		var p1_dim_single: bool = dimmed
		_draw_single_player_plate(font, 342.0, 123.0, 0, "PLAYER 1", TEAM_COLORS[1], vs_p1_char_idx, vs_p1_team, not p1_dim_single, p1_dim_single)


func _draw_single_player_plate(
	font: Font,
	px: float,
	py: float,
	plate_idx: int,
	header_title: String,
	header_color: Color,
	char_choice_idx: int,
	team_idx: int,
	is_active_plate: bool,
	dimmed: bool
) -> void:
	_draw_y8_box800(px, py, 134.0, 138.0, dimmed)

	# 1. Header ("PLAYER 1" Blue or "PLAYER 2" Red)
	_draw_text800(font, px + 4.0, py + 20.0, 126.0, header_title, 8, header_color, HORIZONTAL_ALIGNMENT_CENTER)

	# 2. 54x54 Character Preview Box at local (38, 30)
	_draw_character_preview_box800(font, px + 38.0, py + 30.0, CHAR_CHOICES[clampi(char_choice_idx, 0, CHAR_CHOICES.size() - 1)])

	# 3. Row 0: Character Name (local y = 98)
	var cname: String = CHAR_CHOICES[clampi(char_choice_idx, 0, CHAR_CHOICES.size() - 1)].to_upper()
	_draw_text800(font, px + 18.0, py + 99.0, 98.0, cname, 8, Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER)
	if is_active_plate and player_plate_row == 0:
		# Note: in player_plate.as, left side arrow points outward/inward around the value
		_draw_arrow800(px + 8.0, py + 88.0, false, Color.WHITE)
		_draw_arrow800(px + 118.0, py + 88.0, true, Color.WHITE)

	# 4. Row 1: Team Name (local y = 118)
	var team_locked: bool = selected_game_mode in ["stage", "survival"]
	var t_clamped: int = clampi(team_idx, 0, TEAM_NAMES.size() - 1)
	var t_color: Color = TEAM_COLORS[t_clamped]
	if team_locked:
		t_color = Color(t_color.r * 0.45, t_color.g * 0.45, t_color.b * 0.45, 0.85)
	_draw_text800(font, px + 18.0, py + 119.0, 98.0, TEAM_NAMES[t_clamped], 8, t_color, HORIZONTAL_ALIGNMENT_CENTER)
	if is_active_plate and player_plate_row == 1 and not team_locked:
		_draw_arrow800(px + 8.0, py + 108.0, false, Color.WHITE)
		_draw_arrow800(px + 118.0, py + 108.0, true, Color.WHITE)

	if dimmed and plate_idx >= 0:
		_draw_dim_overlay800(px, py, 134.0, 138.0, 0.48)


func _draw_character_preview_box800(font: Font, bx: float, by: float, char_id: String) -> void:
	var box_r: Rect2 = _rect800(bx, by, 54.0, 54.0)
	if _char_bg_tex != null:
		draw_texture_rect(_char_bg_tex, box_r, false, Color.WHITE)
	else:
		draw_rect(box_r, Color(0.32, 0.08, 0.08, 1.0), true)
	draw_rect(box_r, Color.WHITE, false, 1.0)

	if char_id == "random" or char_id.is_empty():
		_draw_text800(font, bx, by + 35.0, 54.0, "?", 16, Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER)
		return

	var reg: Node = MapLoaderScript.get_registry()
	if reg == null:
		return
	var sheet: Texture2D = reg.call("get_character_sheet", char_id) as Texture2D
	if sheet == null:
		return
	var idle_frames: Array = reg.call("get_state_frames", "IDLE") as Array
	if idle_frames.is_empty():
		return
	var f_idx: int = clampi(_idle_frame_idx - 1, 0, idle_frames.size() - 1)
	var fd: Dictionary = idle_frames[f_idx] as Dictionary
	var r_arr: Array = fd.get("rect", [46.0, 11.0, 17.0, 21.0]) as Array
	var p_arr: Array = fd.get("pivot", [-10.0, -20.0]) as Array
	var src_region: Rect2 = Rect2(float(r_arr[0]), float(r_arr[1]), float(r_arr[2]), float(r_arr[3]))
	var piv: Vector2 = Vector2(float(p_arr[0]), float(p_arr[1]))

	# In Symbol 2135.xml (character_pic), the character stands at local (27, 49) drawn at 2x scale
	var dst_x800: float = bx + 27.0 + piv.x * 2.0
	var dst_y800: float = by + 49.0 + piv.y * 2.0
	var dst_w800: float = src_region.size.x * 2.0
	var dst_h800: float = src_region.size.y * 2.0
	var dst_rect: Rect2 = _rect800(dst_x800, dst_y800, dst_w800, dst_h800)
	draw_texture_rect_region(sheet, dst_rect, src_region, Color.WHITE, false)


# ------------------------------------------------------------------------------
# Screen 3: no_bots (NUMBER OF BOTS [0..7] at (288, 273) size 242x72)
# ------------------------------------------------------------------------------
func _draw_no_bots_box(font: Font) -> void:
	var bx: float = 288.0
	var by: float = 273.0
	_draw_y8_box800(bx, by, 242.0, 72.0, false)
	if _no_bots_tex != null:
		draw_texture_rect(_no_bots_tex, _rect800(bx, by, 242.0, 72.0), false, Color.WHITE)
	else:
		_draw_text800(font, bx, by + 24.0, 242.0, "NUMBER OF BOTS:", 8, Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER)
		for n: int in range(8):
			var nx: float = bx + 22.0 + float(n) * 25.0
			_draw_text800(font, nx, by + 51.0, 24.0, str(n), 8, Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER)

	# Draw the white selection square around the chosen bot count (0..7)
	var sel_x: float = bx + 22.0 + float(vs_bot_count) * 25.0
	var sel_y: float = by + 35.0
	if _bot_box_tex != null:
		draw_texture_rect(_bot_box_tex, _rect800(sel_x, sel_y, 24.0, 24.0), false, Color.WHITE)
	else:
		draw_rect(_rect800(sel_x, sel_y, 24.0, 24.0), Color.WHITE, false, 2.0)


# ------------------------------------------------------------------------------
# Screen 4: bot_setup (Grid of 6 or 7 com_plate Bot Cards at y = 268 and y = 423)
# ------------------------------------------------------------------------------
func _get_bot_plate_rects800() -> Array[Rect2]:
	var rects: Array[Rect2] = []
	if vs_two_player:
		# 6 bot slots: 3 top + 3 bottom at x = 185, 340, 495
		var xs_2p: Array[float] = [185.0, 340.0, 495.0]
		for x: float in xs_2p:
			rects.append(Rect2(x, 268.0, 134.0, 148.0))
		for x: float in xs_2p:
			rects.append(Rect2(x, 423.0, 134.0, 148.0))
	else:
		# 7 bot slots: 4 top (108, 263, 418, 573) + 3 bottom (185, 340, 495)
		var xs_top: Array[float] = [108.0, 263.0, 418.0, 573.0]
		var xs_bot: Array[float] = [185.0, 340.0, 495.0]
		for x: float in xs_top:
			rects.append(Rect2(x, 268.0, 134.0, 148.0))
		for x: float in xs_bot:
			rects.append(Rect2(x, 423.0, 134.0, 148.0))
	return rects


func _draw_bot_plates_grid(font: Font, all_dimmed: bool) -> void:
	var rects: Array[Rect2] = _get_bot_plate_rects800()
	for i: int in range(rects.size()):
		var r: Rect2 = rects[i]
		var is_empty_slot: bool = (i >= vs_bot_count)
		var is_focused_bot: bool = (not all_dimmed) and (current_panel == "BOT_SETUP") and (i == active_bot_plate)
		var card_dimmed: bool = all_dimmed or (current_panel == "BOT_SETUP" and i != active_bot_plate)
		_draw_single_bot_plate(font, r.position.x, r.position.y, i, is_empty_slot, is_focused_bot, card_dimmed)


func _draw_single_bot_plate(
	font: Font,
	bx: float,
	by: float,
	bot_idx: int,
	is_empty_slot: bool,
	is_focused: bool,
	dimmed: bool
) -> void:
	_draw_y8_box800(bx, by, 134.0, 148.0, dimmed or is_empty_slot)
	if is_empty_slot:
		_draw_text800(font, bx + 6.0, by + 78.0, 122.0, "- EMPTY -", 8, Color(0.58, 0.58, 0.58, 0.9), HORIZONTAL_ALIGNMENT_CENTER)
		if dimmed:
			_draw_dim_overlay800(bx, by, 134.0, 148.0, 0.45)
		return

	var bcfg: Dictionary = bot_configs[bot_idx]
	var c_idx: int = clampi(int(bcfg.get("char_idx", 0)), 0, CHAR_CHOICES.size() - 1)
	var t_idx: int = clampi(int(bcfg.get("team", 0)), 0, TEAM_NAMES.size() - 1)
	var d_idx: int = clampi(int(bcfg.get("diff", 2)), 1, 4)

	# 1. Header ("COM")
	_draw_text800(font, bx + 4.0, by + 20.0, 126.0, "COM", 8, Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER)

	# 2. 54x54 Character Preview Box at local (38, 30)
	_draw_character_preview_box800(font, bx + 38.0, by + 30.0, CHAR_CHOICES[c_idx])

	# 3. Row 0: Character Name (local y = 98)
	_draw_text800(font, bx + 18.0, by + 98.0, 98.0, CHAR_CHOICES[c_idx].to_upper(), 8, Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER)
	if is_focused and bot_plate_row == 0:
		_draw_arrow800(bx + 8.0, by + 87.0, false, Color.WHITE)
		_draw_arrow800(bx + 118.0, by + 87.0, true, Color.WHITE)

	# 4. Row 1: Team (local y = 117)
	_draw_text800(font, bx + 18.0, by + 117.0, 98.0, TEAM_NAMES[t_idx], 8, TEAM_COLORS[t_idx], HORIZONTAL_ALIGNMENT_CENTER)
	if is_focused and bot_plate_row == 1:
		_draw_arrow800(bx + 8.0, by + 106.0, false, Color.WHITE)
		_draw_arrow800(bx + 118.0, by + 106.0, true, Color.WHITE)

	# 5. Row 2: Bot Difficulty (local y = 136)
	_draw_text800(font, bx + 18.0, by + 136.0, 98.0, BOT_DIFF_NAMES[d_idx], 8, Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER)
	if is_focused and bot_plate_row == 2:
		_draw_arrow800(bx + 8.0, by + 125.0, false, Color.WHITE)
		_draw_arrow800(bx + 118.0, by + 125.0, true, Color.WHITE)

	if dimmed:
		_draw_dim_overlay800(bx, by, 134.0, 148.0, 0.45)


# ------------------------------------------------------------------------------
# Screen 5: map_selection (Centered 350x280 Box at (225, 185) + 280x120 Map Thumbnail)
# ------------------------------------------------------------------------------
func _draw_map_selection_box(font: Font) -> void:
	var mx: float = 225.0
	var my: float = 185.0
	_draw_y8_box800(mx, my, 350.0, 280.0, false)

	# 1. 280x120 Map Thumbnail Preview at (258, 208)
	var chosen_map_key: String = MAP_CHOICES[clampi(vs_map_idx, 0, MAP_CHOICES.size() - 1)]
	_draw_map_thumbnail800(font, 258.0, 208.0, 280.0, 120.0, chosen_map_key)

	# 2. Row 0: FIGHT
	_draw_text800(font, 260.0, 356.0, 120.0, "FIGHT", 8, Color.WHITE)
	if map_select_row == 0:
		_draw_arrow800(312.0, 345.0, true, Color.WHITE)

	# 3. Row 1: MAP  < RANDOM / ROOFTOPS / ... >
	_draw_text800(font, 260.0, 381.0, 80.0, "MAP", 8, Color.WHITE)
	var map_title: String = str(MAP_DISPLAY_NAMES.get(chosen_map_key, chosen_map_key.to_upper()))
	_draw_text800(font, 352.0, 381.0, 180.0, map_title, 8, Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER)
	if map_select_row == 1:
		_draw_arrow800(340.0, 370.0, false, Color.WHITE)
		_draw_arrow800(536.0, 370.0, true, Color.WHITE)

	# 4. Row 2: GAME MODE  < - / FIRST TO 3 / ... >
	_draw_text800(font, 260.0, 406.0, 100.0, "GAME MODE", 8, Color.WHITE)
	var rule_title: String = GAME_MODE_RULES[clampi(vs_game_rule_idx, 0, GAME_MODE_RULES.size() - 1)]
	_draw_text800(font, 352.0, 406.0, 180.0, rule_title, 8, Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER)
	if map_select_row == 2:
		_draw_arrow800(340.0, 395.0, false, Color.WHITE)
		_draw_arrow800(536.0, 395.0, true, Color.WHITE)

	# 5. Row 3: RESET
	_draw_text800(font, 260.0, 431.0, 100.0, "RESET", 8, Color.WHITE)
	if map_select_row == 3:
		_draw_arrow800(312.0, 420.0, true, Color.WHITE)


func _draw_map_thumbnail800(font: Font, tx: float, ty: float, tw: float, th: float, map_id: String) -> void:
	var tr: Rect2 = _rect800(tx, ty, tw, th)
	draw_rect(tr, Color(0.18, 0.06, 0.06, 1.0), true)

	if map_id == "random" or map_id.is_empty():
		if _char_bg_tex != null:
			draw_texture_rect(_char_bg_tex, tr, true, Color.WHITE)
		_draw_text800(font, tx, ty + th * 0.58, tw, "?", 24, Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER)
	else:
		var reg: Node = MapLoaderScript.get_registry()
		var drew_any: bool = false
		if reg != null:
			var mdata: Dictionary = reg.call("get_map_data", map_id) as Dictionary
			if not mdata.is_empty():
				var sky_c: Color = Color.from_string(str(mdata.get("bg_color", "#1a0a0a")), Color(0.18, 0.06, 0.06, 1.0))
				draw_rect(tr, sky_c, true)
			var bg_layers: Array = mdata.get("bg_layers", []) as Array
			for layer_v: Variant in bg_layers:
				if typeof(layer_v) == TYPE_DICTIONARY:
					var ld: Dictionary = layer_v as Dictionary
					var lpath: String = str(ld.get("path", ""))
					if lpath.is_empty() and not str(ld.get("alias_bitmap", "")).is_empty():
						lpath = "res://assets/maps/" + str(ld.get("alias_bitmap", ""))
					if lpath.is_empty() and not str(ld.get("bitmap", "")).is_empty():
						lpath = "res://assets/maps/" + str(ld.get("bitmap", ""))
					if not lpath.is_empty():
						var ltex: Texture2D = reg.call("load_cached_texture", lpath) as Texture2D
						if ltex != null:
							draw_texture_rect(ltex, tr, false, Color.WHITE)
							drew_any = true
		if not drew_any and reg != null:
			var tpath: String = str(MAP_THUMB_PATHS.get(map_id, "res://assets/maps/Bitmap 2219.png"))
			var mtex: Texture2D = reg.call("load_cached_texture", tpath) as Texture2D
			if mtex != null:
				draw_texture_rect(mtex, tr, false, Color.WHITE)

	draw_rect(tr, Color.WHITE, false, 1.0)


# ------------------------------------------------------------------------------
# Screen 6: challenge_selection (STAGE MODE 600x330 Box at (127, 169) with 4x3 Grid)
# ------------------------------------------------------------------------------
func _draw_stage_select_box(font: Font) -> void:
	_draw_y8_box800(127.0, 169.0, 600.0, 330.0, false)
	_draw_text800(font, 127.0, 195.0, 600.0, "STAGE MODE", 8, Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER)

	for i: int in range(12):
		var st_num: int = i + 1
		var c: int = i % 4
		var r: int = i / 4
		var cx: float = 167.0 + float(c) * 133.0
		var cy: float = 216.0 + float(r) * 72.0
		var is_sel: bool = (not stage_back_selected) and (selected_stage == st_num)

		var st_def: Dictionary = _get_stage_preview_info(st_num)
		var st_map: String = str(st_def.get("map_id", "rooftops"))
		_draw_map_thumbnail800(font, cx, cy, 120.0, 56.0, st_map)

		# Dark gradient strip at top-left for Stage Number
		draw_rect(_rect800(cx + 1.0, cy + 1.0, 26.0, 16.0), Color(0.0, 0.0, 0.0, 0.72), true)
		_draw_text800(font, cx + 5.0, cy + 13.0, 24.0, str(st_num), 8, Color.WHITE)

		if is_sel:
			draw_rect(_rect800(cx - 2.0, cy - 2.0, 124.0, 60.0), Color.WHITE, false, 2.0)

	# Selected stage summary & BACK row at y = 468
	var cur_info: Dictionary = _get_stage_preview_info(selected_stage)
	var cur_title: String = str(cur_info.get("title", "STAGE " + str(selected_stage)))
	_draw_text800(font, 167.0, 456.0, 520.0, cur_title, 8, Color(0.95, 0.88, 0.38, 1.0), HORIZONTAL_ALIGNMENT_CENTER)

	_draw_text800(font, 127.0, 480.0, 600.0, "BACK", 8, Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER)
	if stage_back_selected:
		_draw_arrow800(454.0, 469.0, true, Color.WHITE)


func _get_stage_preview_info(level: int) -> Dictionary:
	var stages: Array[Dictionary] = [
		{"map_id": "storage", "title": "STAGE 1: WAREHOUSE BRAWL (VS BORIS)"},
		{"map_id": "rooftops", "title": "STAGE 2: ROOFTOP PATROL (VS IVAN & SAVAGE)"},
		{"map_id": "backstreets", "title": "STAGE 3: BACKSTREET AMBUSH (VS BRODY & MAC)"},
		{"map_id": "subway", "title": "STAGE 4: SUBWAY CROSSFIRE (VS CRUGER & SAVAGE)"},
		{"map_id": "police_station", "title": "STAGE 5: PRECINCT SIEGE (VS HIDEKI & BLAIRE)"},
		{"map_id": "junkyard", "title": "STAGE 6: JUNKYARD HAVOC (3 ENEMIES)"},
		{"map_id": "hazardous", "title": "STAGE 7: ACID REFINERY (3 ENEMIES)"},
		{"map_id": "cargo", "title": "STAGE 8: CARGO CONTAINMENT (3 ENEMIES)"},
		{"map_id": "tower", "title": "STAGE 9: TOWER ASCENSION (3 ENEMIES)"},
		{"map_id": "testing_floor", "title": "STAGE 10: TESTING LAB (3 ENEMIES)"},
		{"map_id": "police_station", "title": "STAGE 11: ELITE SQUADRON (4 ENEMIES)"},
		{"map_id": "rooftops", "title": "STAGE 12: FINAL BOSS — AGENT"},
	]
	return stages[clampi(level, 1, 12) - 1]


# ------------------------------------------------------------------------------
# Screen 8 & 9: SETUP (183, 241, 225, 149) & CONTROLS (120, 146, 574, 418)
# ------------------------------------------------------------------------------
func _draw_setup_box(font: Font) -> void:
	_draw_y8_box800(183.0, 241.0, 225.0, 149.0, false)
	var rows: Array[String] = [
		"SOUND: " + ("ON" if sound_enabled else "OFF"),
		"MUSIC: " + ("ON" if music_enabled else "OFF"),
		"AUTO ZOOM: " + ("ON" if auto_zoom_enabled else "OFF"),
		"EDIT CONTROLS",
	]
	for i: int in range(rows.size()):
		var by: float = 270.0 + float(i) * 31.0
		_draw_text800(font, 206.0, by, 175.0, rows[i], 8, Color.WHITE)
		if i == setup_row:
			_draw_arrow800(386.0, by - 11.0, true, Color.WHITE)


func _draw_controls_box(font: Font) -> void:
	_draw_y8_box800(120.0, 146.0, 574.0, 418.0, false)
	_draw_text800(font, 152.0, 180.0, 240.0, "PLAYER 1", 8, TEAM_COLORS[1])
	_draw_text800(font, 430.0, 180.0, 240.0, "PLAYER 2", 8, TEAM_COLORS[2])

	var actions: Array[String] = [
		"MOVE LEFT",
		"MOVE RIGHT",
		"JUMP / CLIMB",
		"CROUCH / COVER / PICKUP",
		"MELEE ATTACK",
		"SHOOT (HOLD = AIM)",
		"THROW GRENADE",
		"POWERUP (SLOT 4)",
		"SPRINT",
	]
	var p1_keys: Array[String] = [
		"LEFT ARROW",
		"RIGHT ARROW",
		"UP ARROW",
		"DOWN ARROW",
		"NUM 1 / N",
		"NUM 2 / M",
		"NUM 3 / ,",
		"NUM 4 / .",
		"SHIFT / NUM 0",
	]
	var p2_keys: Array[String] = [
		"A",
		"D",
		"W",
		"S",
		"J",
		"K",
		"L",
		";",
		"G / SPACE",
	]
	for i: int in range(actions.size()):
		var ry: float = 212.0 + float(i) * 31.0
		_draw_text800(font, 152.0, ry, 155.0, actions[i], 8, Color(0.75, 0.75, 0.75, 1.0))
		_draw_text800(font, 305.0, ry, 105.0, p1_keys[i], 8, Color.WHITE)
		_draw_text800(font, 430.0, ry, 155.0, actions[i], 8, Color(0.75, 0.75, 0.75, 1.0))
		_draw_text800(font, 585.0, ry, 95.0, p2_keys[i], 8, Color.WHITE)

	_draw_text800(font, 120.0, 540.0, 574.0, "BACK", 8, Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER)
	_draw_arrow800(436.0, 529.0, true, Color.WHITE)


func _draw_roster_box(font: Font) -> void:
	_draw_y8_box800(100.0, 150.0, 600.0, 360.0, false)
	_draw_text800(font, 100.0, 178.0, 600.0, "SUPERFIGHTERS ROSTER (14 CLASSIC + MUGEN SHINOBI)", 8, Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER)
	for i: int in range(ROSTER_IDS.size()):
		var c: int = i % 5
		var r: int = i / 5
		var bx: float = 136.0 + float(c) * 110.0
		var by: float = 200.0 + float(r) * 96.0
		_draw_character_preview_box800(font, bx, by, ROSTER_IDS[i])
		_draw_text800(font, bx - 16.0, by + 68.0, 86.0, ROSTER_IDS[i].to_upper(), 8, Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER)
	_draw_text800(font, 100.0, 492.0, 600.0, "BACK", 8, Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER)


func _get_footer_hint_text() -> String:
	match current_panel:
		"VS_PLAYER_SETUP", "VS_SETUP":
			return "SELECT CHARACTER & TEAM  —  PRESS [SPACE / ENTER] FOR NEXT"
		"NO_BOTS":
			return "CHOOSE NUMBER OF BOTS (0.." + str(_get_max_vs_bots()) + ")  —  PRESS [SPACE / ENTER] TO CONFIRM"
		"BOT_SETUP":
			return "CONFIGURE BOT " + str(active_bot_plate + 1) + "/" + str(vs_bot_count) + "  —  PRESS [SPACE / ENTER] FOR NEXT"
	return ""


func _draw_navigation_footer_box(font: Font, _hint_msg: String) -> void:
	# Draw a clickable NEXT button at bottom right (640, 534)
	_draw_y8_box800(640.0, 534.0, 140.0, 32.0, false)
	_draw_text800(font, 640.0, 554.0, 120.0, "NEXT", 8, Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER)
	_draw_arrow800(760.0, 543.0, true, Color.WHITE)

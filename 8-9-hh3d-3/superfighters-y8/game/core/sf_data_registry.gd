class_name SFDataRegistryClass
extends Node
## Central data registry loading compiled XFL rigs, AS3 weapons, and AS3/XFL maps.

const RIGS_JSON_PATH: String = "res://data/sf_compiled_rigs.json"
const WEAPONS_JSON_PATH: String = "res://data/sf_compiled_weapons.json"
const MAPS_JSON_PATH: String = "res://data/sf_compiled_maps.json"

var rigs_data: Dictionary = {}
var weapons_data: Dictionary = {}
var maps_data: Dictionary = {}

var _loaded: bool = false
var _texture_cache: Dictionary = {}


func _ready() -> void:
	ensure_loaded()
	_configure_default_input_map()


func ensure_loaded() -> void:
	if _loaded:
		return
	rigs_data = _load_json_dict(RIGS_JSON_PATH)
	weapons_data = _load_json_dict(WEAPONS_JSON_PATH)
	maps_data = _load_json_dict(MAPS_JSON_PATH)
	_loaded = true
	_configure_default_input_map()


func _load_json_dict(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		push_error("[SFDataRegistry] Missing compiled JSON file: " + path)
		return {}
	var raw_text: String = FileAccess.get_file_as_string(path)
	if raw_text.is_empty():
		push_error("[SFDataRegistry] Empty JSON file: " + path)
		return {}
	var parsed: Variant = JSON.parse_string(raw_text)
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("[SFDataRegistry] Invalid JSON dictionary in: " + path)
		return {}
	return parsed as Dictionary


func get_rig_data() -> Dictionary:
	ensure_loaded()
	return rigs_data


func get_states() -> Dictionary:
	ensure_loaded()
	var states: Variant = rigs_data.get("states", {})
	return states as Dictionary if typeof(states) == TYPE_DICTIONARY else {}


func get_state_data(state_name: String) -> Dictionary:
	ensure_loaded()
	var states: Dictionary = get_states()
	var key: String = state_name.to_upper()
	if states.has(key):
		return states[key] as Dictionary
	return {}


func get_state_frames(state_name: String) -> Array:
	var st: Dictionary = get_state_data(state_name)
	var frames: Variant = st.get("frames", [])
	return frames as Array if typeof(frames) == TYPE_ARRAY else []


func get_character_data(char_id: String) -> Dictionary:
	ensure_loaded()
	var chars: Variant = rigs_data.get("characters", {})
	if typeof(chars) != TYPE_DICTIONARY:
		return {}
	var chars_dict: Dictionary = chars as Dictionary
	var key: String = char_id.to_lower()
	if chars_dict.has(key):
		return chars_dict[key] as Dictionary
	if chars_dict.has("johnny"):
		return chars_dict["johnny"] as Dictionary
	return {}


func get_character_sheet(char_id: String) -> Texture2D:
	var cdata: Dictionary = get_character_data(char_id)
	var path: String = str(cdata.get("sheet_path", "res://assets/sheets/Bitmap 591.png"))
	return load_cached_texture(path)


func get_blood_sheet() -> Texture2D:
	ensure_loaded()
	var brig: Variant = rigs_data.get("blood_rig", {})
	var path: String = "res://assets/sheets/Bitmap 900.png"
	if typeof(brig) == TYPE_DICTIONARY:
		path = str((brig as Dictionary).get("sheet_path", path))
	return load_cached_texture(path)


func get_all_weapons() -> Dictionary:
	ensure_loaded()
	var w: Variant = weapons_data.get("weapons", {})
	return w as Dictionary if typeof(w) == TYPE_DICTIONARY else {}


func get_weapon_data(weapon_id: String) -> Dictionary:
	var all_w: Dictionary = get_all_weapons()
	var key: String = weapon_id.to_upper()
	if all_w.has(key):
		return all_w[key] as Dictionary
	# Also support lookup by WPN_ prefix from MapPremadeItems.as
	if key.begins_with("WPN_"):
		var stripped: String = key.substr(4)
		if stripped == "GRENADES":
			stripped = "GRENADE"
		elif stripped == "MOLOTOVS":
			stripped = "MOLOTOV"
		elif stripped == "SLOWMO_05":
			stripped = "SLOMO05"
		elif stripped == "SLOWMO_10":
			stripped = "SLOMO10"
		if all_w.has(stripped):
			return all_w[stripped] as Dictionary
	return {}


func get_all_maps() -> Dictionary:
	ensure_loaded()
	var m: Variant = maps_data.get("maps", {})
	return m as Dictionary if typeof(m) == TYPE_DICTIONARY else {}


func get_map_data(map_id: String) -> Dictionary:
	var all_m: Dictionary = get_all_maps()
	var key: String = map_id.to_lower().replace(" ", "_")
	if all_m.has(key):
		return all_m[key] as Dictionary
	return {}


func get_vs_map_ids() -> Array[String]:
	ensure_loaded()
	var out: Array[String] = []
	var raw: Variant = maps_data.get("vs_map_ids", [])
	if typeof(raw) == TYPE_ARRAY:
		for item: Variant in raw as Array:
			out.append(str(item))
	return out


func get_premade_item_def(item_type: String) -> Dictionary:
	ensure_loaded()
	var defs: Variant = maps_data.get("premade_item_defs", {})
	if typeof(defs) == TYPE_DICTIONARY:
		var d: Dictionary = defs as Dictionary
		var key: String = item_type.to_upper()
		if d.has(key):
			return d[key] as Dictionary
	return {}


func load_cached_texture(res_path: String) -> Texture2D:
	if res_path.is_empty():
		return null
	if _texture_cache.has(res_path):
		return _texture_cache[res_path] as Texture2D
	var abs_path: String = ProjectSettings.globalize_path(res_path)
	if res_path.ends_with("_dmg.png") and FileAccess.file_exists(abs_path):
		var dmg_img: Image = Image.load_from_file(abs_path)
		if dmg_img != null and not dmg_img.is_empty():
			var dmg_tex: ImageTexture = ImageTexture.create_from_image(dmg_img)
			_texture_cache[res_path] = dmg_tex
			return dmg_tex
	if ResourceLoader.exists(res_path):
		var tex: Resource = ResourceLoader.load(res_path)
		if tex is Texture2D:
			_texture_cache[res_path] = tex
			return tex as Texture2D
	# Fallback to Image.load_from_file if Godot import hasn't cached a StreamTexture2D yet
	if FileAccess.file_exists(abs_path):
		var img: Image = Image.load_from_file(abs_path)
		if img != null and not img.is_empty():
			var itex: ImageTexture = ImageTexture.create_from_image(img)
			_texture_cache[res_path] = itex
			return itex
	return null


func _configure_default_input_map() -> void:
	if DisplayServer.get_name() != "headless":
		DisplayServer.window_set_ime_active(false)
	ensure_input_map()


func ensure_input_map() -> void:
	var bindings: Dictionary = {
		# Arrow Keys Player: Arrow Keys + Numpad 1 / 2 / 3 / 4 ONLY
		"p1_left": [KEY_LEFT],
		"p1_right": [KEY_RIGHT],
		"p1_up": [KEY_UP],
		"p1_down": [KEY_DOWN],
		"p1_jump": [],
		"p1_attack": [KEY_KP_1],
		"p1_aim": [KEY_KP_2],
		"p1_throw": [KEY_KP_3],
		"p1_powerup": [KEY_KP_4],
		"p1_sprint": [],
		"p1_slot_1": [KEY_F1],
		"p1_slot_2": [KEY_F2],
		"p1_slot_3": [KEY_F3],
		"p1_slot_4": [KEY_F4],
		# WASD Player: W / A / S / D + J / K / L / ; ONLY
		"p2_left": [KEY_A],
		"p2_right": [KEY_D],
		"p2_up": [KEY_W],
		"p2_down": [KEY_S],
		"p2_jump": [],
		"p2_attack": [KEY_J],
		"p2_aim": [KEY_K],
		"p2_throw": [KEY_L],
		"p2_powerup": [KEY_SEMICOLON],
		"p2_sprint": [],
		"p2_slot_1": [KEY_F5],
		"p2_slot_2": [KEY_F6],
		"p2_slot_3": [KEY_F7],
		"p2_slot_4": [KEY_F8],
	}
	for action_name: String in bindings.keys():
		if InputMap.has_action(action_name):
			InputMap.action_erase_events(action_name)
		else:
			InputMap.add_action(action_name)
		var keys: Array = bindings[action_name] as Array
		for k_var: Variant in keys:
			_bind_key(action_name, k_var as Key)


func _bind_key(action_name: String, keycode: Key) -> void:
	if not InputMap.has_action(action_name):
		InputMap.add_action(action_name)

	# 1. Pure physical_keycode event (keycode = KEY_NONE) so Godot 4 matches hardware scan code
	# even when Vietnamese Telex IME (UniKey/EVKey) turns W -> 'ư' or D -> 'đ', or when NumLock is toggled!
	var ev_phys: InputEventKey = InputEventKey.new()
	ev_phys.physical_keycode = keycode
	ev_phys.keycode = KEY_NONE
	InputMap.action_add_event(action_name, ev_phys)

	# 2. Pure logical keycode event (physical_keycode = KEY_NONE)
	var ev_key: InputEventKey = InputEventKey.new()
	ev_key.keycode = keycode
	ev_key.physical_keycode = KEY_NONE
	InputMap.action_add_event(action_name, ev_key)

	# 3. Vietnamese Telex IME fallback keycodes in case IME injects synthetic Unicode key events with physical_keycode == 0
	if keycode == KEY_W:
		for telex_w: int in [432, 431]: # 'ư' (0x01B0), 'Ư' (0x01AF)
			var ev_tw: InputEventKey = InputEventKey.new()
			ev_tw.keycode = telex_w as Key
			ev_tw.unicode = telex_w
			ev_tw.physical_keycode = KEY_NONE
			InputMap.action_add_event(action_name, ev_tw)
	elif keycode == KEY_D:
		for telex_d: int in [273, 272]: # 'đ' (0x0111), 'Đ' (0x0110)
			var ev_td: InputEventKey = InputEventKey.new()
			ev_td.keycode = telex_d as Key
			ev_td.unicode = telex_d
			ev_td.physical_keycode = KEY_NONE
			InputMap.action_add_event(action_name, ev_td)

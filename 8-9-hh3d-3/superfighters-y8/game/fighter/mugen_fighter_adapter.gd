class_name MugenFighterAdapter
extends RefCounted
## Adapter for MUGEN / Custom Moveset characters (SF-M6).
## Reads compiled MUGEN JSON definitions (e.g. data/custom_fighters/hero_shinobi_mugen.json),
## registers custom fighters into SFDataRegistry, provides FrameVisualData (rect + axis pivot),
## Clsn1 (red attack hitboxes), Clsn2 (blue hurtboxes), 4-hit combo cancel table, and special moves.

const CUSTOM_FIGHTERS_DIR: String = "res://data/custom_fighters"
const SHINOBI_JSON_PATH: String = "res://data/custom_fighters/hero_shinobi_mugen.json"

var char_id: String = ""
var display_name: String = ""
var sheet_path: String = ""
var hp_mult: float = 1.0
var speed_mult: float = 1.0
var use_sf_split_rig_for_guns: bool = true

var mugen_data: Dictionary = {}
var mugen_states: Dictionary = {}
var cancel_table: Dictionary = {}
var special_moves: Dictionary = {}
var default_clsn2: Array[Rect2] = [Rect2(-6.0, -18.0, 12.0, 18.0)]


static func ensure_registry_integration(registry: Object = null) -> void:
	var reg: Object = registry
	if reg == null:
		var tree: SceneTree = Engine.get_main_loop() as SceneTree
		if tree != null and tree.root != null:
			reg = tree.root.get_node_or_null("SFDataRegistry")
	if reg == null or not reg.has_method("ensure_loaded"):
		return
	reg.call("ensure_loaded")
	var rigs: Variant = reg.get("rigs_data")
	if typeof(rigs) != TYPE_DICTIONARY:
		return
	var rigs_dict: Dictionary = rigs as Dictionary

	# 1. Ensure standard melee & grab state aliases exist in rigs_data["states"]
	var states_var: Variant = rigs_dict.get("states", {})
	if typeof(states_var) == TYPE_DICTIONARY:
		var states: Dictionary = states_var as Dictionary
		var extra_aliases: Dictionary = {
			"BATON_01": "MACHETE_01",
			"BATON_02": "MACHETE_02",
			"BATON_03": "MACHETE_03",
			"CHAINSAW_01": "AIM_FLAMETHROWER",
			"CHAINSAW_02": "AIM_FLAMETHROWER",
			"GRAB": "PUNCH_01",
			"ROCKET_RIDE": "ROCKET_RIDE_R",
		}
		for alias_k: String in extra_aliases.keys():
			var src_k: String = str(extra_aliases[alias_k])
			if not states.has(alias_k) and states.has(src_k):
				var cloned: Dictionary = (states[src_k] as Dictionary).duplicate(true)
				if alias_k.begins_with("CHAINSAW"):
					# Convert chainsaw swing to full_body using torso + arm or machete frame so AimPivot isn't needed when idle
					if states.has("MACHETE_01"):
						cloned = (states["MACHETE_01"] as Dictionary).duplicate(true)
				cloned["alias_of"] = src_k
				states[alias_k] = cloned

	# 2. Register Shinobi (and any custom fighter JSONs) into rigs_data["characters"]
	var chars_var: Variant = rigs_dict.get("characters", {})
	if typeof(chars_var) == TYPE_DICTIONARY:
		var chars: Dictionary = chars_var as Dictionary
		var shinobi_dict: Dictionary = _load_json_file(SHINOBI_JSON_PATH)
		if not shinobi_dict.is_empty():
			var cid: String = str(shinobi_dict.get("id", "shinobi")).to_lower()
			chars[cid] = {
				"id": cid,
				"display_name": str(shinobi_dict.get("display_name", "Shinobi — MUGEN Hero")),
				"symbol": "MUGEN_SHINOBI",
				"linkage_class": "player_shinobi_mugen",
				"sheet_bitmap": "hero_shinobi_mugen.png",
				"sheet_path": str(shinobi_dict.get("sheet_path", "res://assets/sheets/hero_shinobi_mugen.png")),
				"hp_mult": float(shinobi_dict.get("hp_mult", 1.05)),
				"speed_mult": float(shinobi_dict.get("speed_mult", 1.12)),
				"is_mugen": true,
				"mugen_json": SHINOBI_JSON_PATH,
			}
			# Also register MUGEN state entries in states so SFDataRegistry.get_state_data() resolves them
			if typeof(states_var) == TYPE_DICTIONARY:
				var states: Dictionary = states_var as Dictionary
				var m_states: Dictionary = shinobi_dict.get("mugen_states", {}) as Dictionary
				for m_key: Variant in m_states.keys():
					var skey: String = str(m_key).to_upper()
					var mdef: Dictionary = m_states[m_key] as Dictionary
					if not states.has(skey):
						states[skey] = {
							"frame_index": 100,
							"type": "full_body",
							"loop": bool(mdef.get("loop", false)),
							"next_state": mdef.get("next_state", "IDLE"),
							"frames": mdef.get("frames", []),
							"keyframes": mdef.get("frames", []),
						}


static func is_mugen_character_id(p_char_id: String) -> bool:
	var key: String = p_char_id.to_lower()
	if key in ["shinobi", "hero_shinobi", "hero_shinobi_mugen"]:
		return true
	var custom_path: String = CUSTOM_FIGHTERS_DIR + "/" + key + ".json"
	var hero_path: String = CUSTOM_FIGHTERS_DIR + "/hero_" + key + "_mugen.json"
	return FileAccess.file_exists(custom_path) or FileAccess.file_exists(hero_path)


static func _load_json_file(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var text: String = FileAccess.get_file_as_string(path)
	if text.is_empty():
		return {}
	var parsed: Variant = JSON.parse_string(text)
	return parsed as Dictionary if typeof(parsed) == TYPE_DICTIONARY else {}


func load_for_character(p_char_id: String, registry: Object = null) -> bool:
	ensure_registry_integration(registry)
	var key: String = p_char_id.to_lower()
	var path: String = ""
	if key in ["shinobi", "hero_shinobi", "hero_shinobi_mugen"]:
		path = SHINOBI_JSON_PATH
	else:
		var candidate1: String = CUSTOM_FIGHTERS_DIR + "/hero_" + key + "_mugen.json"
		var candidate2: String = CUSTOM_FIGHTERS_DIR + "/" + key + ".json"
		if FileAccess.file_exists(candidate1):
			path = candidate1
		elif FileAccess.file_exists(candidate2):
			path = candidate2

	if path.is_empty():
		return false

	mugen_data = _load_json_file(path)
	if mugen_data.is_empty():
		return false

	char_id = str(mugen_data.get("id", key)).to_lower()
	display_name = str(mugen_data.get("display_name", "Shinobi — MUGEN Hero"))
	sheet_path = str(mugen_data.get("sheet_path", "res://assets/sheets/hero_shinobi_mugen.png"))
	hp_mult = float(mugen_data.get("hp_mult", 1.05))
	speed_mult = float(mugen_data.get("speed_mult", 1.12))
	use_sf_split_rig_for_guns = bool(mugen_data.get("use_sf_split_rig_for_guns", true))

	var ms: Variant = mugen_data.get("mugen_states", {})
	mugen_states = ms as Dictionary if typeof(ms) == TYPE_DICTIONARY else {}

	var ct: Variant = mugen_data.get("cancel_table", {})
	cancel_table = ct as Dictionary if typeof(ct) == TYPE_DICTIONARY else {}

	var sm: Variant = mugen_data.get("special_moves", {})
	special_moves = sm as Dictionary if typeof(sm) == TYPE_DICTIONARY else {}

	default_clsn2.clear()
	var raw_c2: Variant = mugen_data.get("default_clsn2", [[-6.0, -18.0, 12.0, 18.0]])
	if typeof(raw_c2) == TYPE_ARRAY:
		for box_v: Variant in raw_c2 as Array:
			if typeof(box_v) == TYPE_ARRAY and (box_v as Array).size() == 4:
				var arr: Array = box_v as Array
				default_clsn2.append(Rect2(float(arr[0]), float(arr[1]), float(arr[2]), float(arr[3])))
	if default_clsn2.is_empty():
		default_clsn2.append(Rect2(-6.0, -18.0, 12.0, 18.0))
	return true


func is_mugen_state(state_name: String) -> bool:
	return mugen_states.has(state_name.to_upper())


func get_mugen_state_def(state_name: String) -> Dictionary:
	var key: String = state_name.to_upper()
	if mugen_states.has(key):
		return mugen_states[key] as Dictionary
	return {}


func get_combo_state_for_step(step_idx: int) -> String:
	var clamped: int = clampi(step_idx, 1, 4)
	return "MUGEN_COMBO_" + str(clamped)


func can_cancel(from_state: String, to_state: String) -> bool:
	var fk: String = from_state.to_upper()
	var tk: String = to_state.to_upper()
	if not cancel_table.has(fk):
		return false
	var allowed: Variant = cancel_table[fk]
	if typeof(allowed) == TYPE_ARRAY:
		for item: Variant in allowed as Array:
			if str(item).to_upper() == tk:
				return true
	return false


func get_special_move_def(move_name: String) -> Dictionary:
	var key: String = move_name.to_upper()
	if special_moves.has(key):
		return special_moves[key] as Dictionary
	return {}


func get_frame_visual_data(state_name: String, anim_frame_idx: int) -> Dictionary:
	var key: String = state_name.to_upper()
	if not mugen_states.has(key):
		return {}
	var st_def: Dictionary = mugen_states[key] as Dictionary
	var frames: Array = st_def.get("frames", []) as Array
	if frames.is_empty():
		return {}
	var idx: int = clampi(anim_frame_idx - 1, 0, frames.size() - 1)
	var fdict: Dictionary = frames[idx] as Dictionary
	var r_arr: Array = fdict.get("rect", [20.0, 270.0, 28.0, 20.0]) as Array
	var p_arr: Array = fdict.get("pivot", [-8.0, -19.0]) as Array

	var clsn1_out: Array[Rect2] = []
	var c1_raw: Variant = fdict.get("clsn1", [])
	if typeof(c1_raw) == TYPE_ARRAY:
		for b: Variant in c1_raw as Array:
			if typeof(b) == TYPE_ARRAY and (b as Array).size() == 4:
				var ba: Array = b as Array
				clsn1_out.append(Rect2(float(ba[0]), float(ba[1]), float(ba[2]), float(ba[3])))

	var clsn2_out: Array[Rect2] = []
	var c2_raw: Variant = fdict.get("clsn2", [])
	if typeof(c2_raw) == TYPE_ARRAY:
		for b2: Variant in c2_raw as Array:
			if typeof(b2) == TYPE_ARRAY and (b2 as Array).size() == 4:
				var ba2: Array = b2 as Array
				clsn2_out.append(Rect2(float(ba2[0]), float(ba2[1]), float(ba2[2]), float(ba2[3])))
	if clsn2_out.is_empty():
		clsn2_out = default_clsn2.duplicate()

	return {
		"is_mugen_custom": true,
		"state": key,
		"sheet_path": sheet_path,
		"rect": Rect2(float(r_arr[0]), float(r_arr[1]), float(r_arr[2]), float(r_arr[3])),
		"pivot": Vector2(float(p_arr[0]), float(p_arr[1])),
		"duration": int(fdict.get("duration", 3)),
		"frame_count": frames.size(),
		"clsn1": clsn1_out,
		"clsn2": clsn2_out,
	}


func get_world_clsn1_boxes(state_name: String, anim_frame_idx: int, world_pos: Vector2, facing: int) -> Array[Rect2]:
	var fdata: Dictionary = get_frame_visual_data(state_name, anim_frame_idx)
	var out: Array[Rect2] = []
	if fdata.is_empty():
		return out
	var local_boxes: Array = fdata.get("clsn1", []) as Array
	for r_var: Variant in local_boxes:
		var r: Rect2 = r_var as Rect2
		if facing >= 0:
			out.append(Rect2(world_pos.x + r.position.x, world_pos.y + r.position.y, r.size.x, r.size.y))
		else:
			out.append(Rect2(world_pos.x - (r.position.x + r.size.x), world_pos.y + r.position.y, r.size.x, r.size.y))
	return out


func get_world_clsn2_boxes(state_name: String, anim_frame_idx: int, world_pos: Vector2, facing: int) -> Array[Rect2]:
	var fdata: Dictionary = get_frame_visual_data(state_name, anim_frame_idx)
	var local_boxes: Array = fdata.get("clsn2", default_clsn2) as Array
	var out: Array[Rect2] = []
	for r_var: Variant in local_boxes:
		var r: Rect2 = r_var as Rect2
		if facing >= 0:
			out.append(Rect2(world_pos.x + r.position.x, world_pos.y + r.position.y, r.size.x, r.size.y))
		else:
			out.append(Rect2(world_pos.x - (r.position.x + r.size.x), world_pos.y + r.position.y, r.size.x, r.size.y))
	return out

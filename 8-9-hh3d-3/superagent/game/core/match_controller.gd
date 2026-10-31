class_name MatchController
extends Node2D
## Master Match Lifecycle & World Coordinator (SF-M4 / SF-M5).
## Coordinates MapLoader, InteractiveProps, Weapon Pickups, Supply Parachute Crates,
## FighterControllers (P1, P2, Bots), BotControllers, ProjectileManager, FireHazardSystem,
## DynamicCamera, and MatchHudController across VS, Stage (12 Stages), and Survival modes.

signal request_return_to_menu()
signal request_open_setup(target_panel: String)

const FLASH_FPS: float = 28.0
const PAUSE_MENU_COUNT: int = 6
const WEAPON_SPAWN_ORDER: Array[String] = [
	"PISTOL",
	"RIFLE",
	"SHOTGUN",
	"SNIPER",
	"BAZOOKA",
	"MOLOTOV",
	"GRENADE",
	"FLAMETHROWER",
	"SWORD",
	"MACHETE",
	"AXE",
	"SLOMO05",
	"SLOMO10",
	"PILLS",
	"MEDKIT",
	"MAGNUM",
	"UZI",
]
const WEAPON_SPAWN_WEIGHTS: Array[int] = [11, 9, 7, 2, 2, 4, 6, 5, 2, 3, 3, 4, 3, 2, 2, 2, 6]

const MapLoaderScript = preload("res://game/world/map_loader.gd")
const InteractivePropScript = preload("res://game/world/interactive_prop.gd")
const DynamicCameraScript = preload("res://game/world/dynamic_camera.gd")
const BotControllerScript = preload("res://game/ai/bot_controller.gd")
const MatchHudScript = preload("res://game/ui/match_hud_controller.gd")

static var agent_unlocked: bool = false

var map_loader: Node2D = null
var projectile_manager: Node2D = null
var fire_hazard_system: Node2D = null
var dynamic_camera: Camera2D = null
var hud_controller: CanvasLayer = null

var fighters: Array[Node2D] = []
var props: Array[Node2D] = []
var pickups: Array[Dictionary] = []
var _last_pickup_elevator_motion_serial: int = -1
var floating_texts: Array[Dictionary] = []
var bot_controllers: Dictionary = {} # instance_id -> BotController

var match_config: Dictionary = {}
var game_mode: String = "vs"
var current_map_id: String = "rooftops"
var two_player: bool = false
var stage_level: int = 1
var survival_wave: int = 1
var survival_kills: int = 0

var game_speed: float = 1.0
var slowmo_timer: float = 0.0
var is_paused: bool = false
var _cancel_was_down: bool = false
var pause_selected_index: int = 0
var pause_audio_mode: int = 0 # 0 = ON 100%, 1 = LOW 50% (-6 dB), 2 = MUTE
var pause_camera_wide: bool = false
var _pause_key_was_down: Dictionary = {}
var _round_over_confirm_was_down: bool = false
var _resolved_p1_char: String = "johnny"
var _resolved_p2_char: String = "agent"

var round_state: String = "GET_READY" # "GET_READY", "FIGHT", "ROUND_OVER"
var banner_text: String = "GET READY..."
var banner_timer: float = 36.0
var overhead_label_timer: float = 96.0
var round_over_timer: float = 48.0
var winner_text: String = ""
var winner_slot: int = -1
var winner_team: int = -1

var _props_container: Node2D = null
var _pickups_container: Node2D = null
var _fighters_container: Node2D = null
var _weapon_spawn_timer: float = 140.0
var _supply_drop_timer: float = 280.0
var _survival_spawn_timer: float = 120.0
var _next_prop_id: int = 1
var active_cutin: Dictionary = {}
var active_cutins: Array[Dictionary] = []


# ------------------------------------------------------------------------------
# MatchController Lifecycle
# ------------------------------------------------------------------------------
func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	MapLoaderScript.get_registry()
	MapLoaderScript.get_audio()
	_ensure_subsystems()


func _ensure_subsystems() -> void:
	if map_loader == null or not is_instance_valid(map_loader):
		var existing_ml: Node = get_node_or_null("MapLoader")
		if existing_ml is Node2D:
			map_loader = existing_ml as Node2D
		else:
			map_loader = MapLoaderScript.new()
			map_loader.name = "MapLoader"
			add_child(map_loader)
	map_loader.set("match_world", self)

	if _props_container == null or not is_instance_valid(_props_container):
		_props_container = get_node_or_null("PropsContainer") as Node2D
		if _props_container == null:
			_props_container = Node2D.new()
			_props_container.name = "PropsContainer"
			_props_container.z_index = 2
			add_child(_props_container)

	if _pickups_container == null or not is_instance_valid(_pickups_container):
		_pickups_container = get_node_or_null("PickupsContainer") as Node2D
		if _pickups_container == null:
			_pickups_container = Node2D.new()
			_pickups_container.name = "PickupsContainer"
			_pickups_container.z_index = 3
			add_child(_pickups_container)

	if _fighters_container == null or not is_instance_valid(_fighters_container):
		_fighters_container = get_node_or_null("FightersContainer") as Node2D
		if _fighters_container == null:
			_fighters_container = Node2D.new()
			_fighters_container.name = "FightersContainer"
			_fighters_container.z_index = 5
			add_child(_fighters_container)

	if projectile_manager == null or not is_instance_valid(projectile_manager):
		var existing_pm: Node = get_node_or_null("ProjectileManager")
		if existing_pm is Node2D:
			projectile_manager = existing_pm as Node2D
		else:
			projectile_manager = _instantiate_projectile_manager()
			projectile_manager.name = "ProjectileManager"
			projectile_manager.z_index = 6
			add_child(projectile_manager)
	projectile_manager.set("match_world", self)

	if fire_hazard_system == null or not is_instance_valid(fire_hazard_system):
		var existing_fhs: Node = get_node_or_null("FireHazardSystem")
		if existing_fhs is Node2D:
			fire_hazard_system = existing_fhs as Node2D
		else:
			fire_hazard_system = _instantiate_fire_hazard_system()
			fire_hazard_system.name = "FireHazardSystem"
			fire_hazard_system.z_index = 7
			add_child(fire_hazard_system)
	fire_hazard_system.set("match_world", self)

	if dynamic_camera == null or not is_instance_valid(dynamic_camera):
		var existing_cam: Node = get_node_or_null("DynamicCamera")
		if existing_cam is Camera2D:
			dynamic_camera = existing_cam as Camera2D
		else:
			dynamic_camera = DynamicCameraScript.new()
			dynamic_camera.name = "DynamicCamera"
			add_child(dynamic_camera)
	dynamic_camera.set("match_world", self)

	if hud_controller == null or not is_instance_valid(hud_controller):
		var existing_hud: Node = get_node_or_null("MatchHud")
		if existing_hud is CanvasLayer:
			hud_controller = existing_hud as CanvasLayer
		else:
			hud_controller = MatchHudScript.new()
			hud_controller.name = "MatchHud"
			add_child(hud_controller)
	hud_controller.set("match_world", self)


func _instantiate_projectile_manager() -> Node2D:
	var path: String = "res://game/world/projectile_manager.gd"
	if ResourceLoader.exists(path):
		var scr: Variant = load(path)
		if scr is Script and (scr as Script).can_instantiate():
			var inst: Variant = (scr as Script).new()
			if inst is Node2D:
				return inst as Node2D
	return Node2D.new()


func _instantiate_fire_hazard_system() -> Node2D:
	var path: String = "res://game/world/fire_hazard_system.gd"
	if ResourceLoader.exists(path):
		var scr: Variant = load(path)
		if scr is Script and (scr as Script).can_instantiate():
			var inst: Variant = (scr as Script).new()
			if inst is Node2D:
				return inst as Node2D
	return Node2D.new()


func _instantiate_fighter_node() -> Node2D:
	var scene_path: String = "res://scenes/fighter.tscn"
	if ResourceLoader.exists(scene_path):
		var packed: Resource = load(scene_path)
		if packed is PackedScene:
			var node: Node = (packed as PackedScene).instantiate()
			if node is Node2D:
				return node as Node2D
	var scr_path: String = "res://game/fighter/fighter_controller.gd"
	if ResourceLoader.exists(scr_path):
		var scr: Variant = load(scr_path)
		if scr is Script and (scr as Script).can_instantiate():
			var inst: Variant = (scr as Script).new()
			if inst is Node2D:
				return inst as Node2D
	return CharacterBody2D.new()


func _clear_match_entities() -> void:
	for f: Node2D in fighters:
		if is_instance_valid(f):
			if f.get_parent() != null:
				f.get_parent().remove_child(f)
			f.free()
	fighters.clear()
	bot_controllers.clear()
	active_cutin.clear()
	active_cutins.clear()

	for p: Node2D in props:
		if is_instance_valid(p):
			if p.get_parent() != null:
				p.get_parent().remove_child(p)
			p.free()
	props.clear()

	for pk: Dictionary in pickups:
		var spr: Node2D = pk.get("node", null) as Node2D
		if spr != null and is_instance_valid(spr):
			if spr.get_parent() != null:
				spr.get_parent().remove_child(spr)
			spr.free()
	pickups.clear()
	floating_texts.clear()

	if projectile_manager != null and is_instance_valid(projectile_manager) and projectile_manager.has_method("clear_all"):
		projectile_manager.call("clear_all")
	if fire_hazard_system != null and is_instance_valid(fire_hazard_system) and fire_hazard_system.has_method("clear_all"):
		fire_hazard_system.call("clear_all")
	if map_loader != null and is_instance_valid(map_loader) and map_loader.has_method("_clear_map_state"):
		map_loader.call("_clear_map_state")


func get_stage_definition(level: int) -> Dictionary:
	var clamped_lvl: int = clampi(level, 1, 12)
	var stages: Array[Dictionary] = [
		{"stage": 1, "map_id": "storage", "bots": [{"char": "boris", "diff": 1}], "start_gun": "", "title": "STAGE 1: WAREHOUSE BRAWL"},
		{"stage": 2, "map_id": "rooftops", "bots": [{"char": "ivan", "diff": 1}, {"char": "savage", "diff": 1}], "start_gun": "PISTOL", "title": "STAGE 2: ROOFTOP PATROL"},
		{"stage": 3, "map_id": "backstreets", "bots": [{"char": "brody", "diff": 1}, {"char": "mac", "diff": 2}], "start_gun": "PISTOL", "title": "STAGE 3: BACKSTREET AMBUSH"},
		{"stage": 4, "map_id": "subway", "bots": [{"char": "cruger", "diff": 2}, {"char": "savage", "diff": 2}], "start_gun": "UZI", "title": "STAGE 4: SUBWAY CROSSFIRE"},
		{"stage": 5, "map_id": "police_station", "bots": [{"char": "hideki", "diff": 2}, {"char": "blaire", "diff": 2}], "start_gun": "SHOTGUN", "title": "STAGE 5: PRECINCT SIEGE"},
		{"stage": 6, "map_id": "junkyard", "bots": [{"char": "boris", "diff": 2}, {"char": "ivan", "diff": 2}, {"char": "brody", "diff": 2}], "start_gun": "SHOTGUN", "title": "STAGE 6: JUNKYARD HAVOC"},
		{"stage": 7, "map_id": "hazardous", "bots": [{"char": "cruger", "diff": 2}, {"char": "hideki", "diff": 2}, {"char": "savage", "diff": 2}], "start_gun": "RIFLE", "title": "STAGE 7: ACID REFINERY"},
		{"stage": 8, "map_id": "cargo", "bots": [{"char": "blaire", "diff": 2}, {"char": "mac", "diff": 3}, {"char": "ivan", "diff": 2}], "start_gun": "TOMMY_GUN", "title": "STAGE 8: CARGO CONTAINMENT"},
		{"stage": 9, "map_id": "tower", "bots": [{"char": "hideki", "diff": 3}, {"char": "cruger", "diff": 3}, {"char": "brody", "diff": 2}], "start_gun": "MAGNUM", "title": "STAGE 9: TOWER ASCENSION"},
		{"stage": 10, "map_id": "testing_floor", "bots": [{"char": "blaire", "diff": 3}, {"char": "hideki", "diff": 3}, {"char": "mac", "diff": 3}], "start_gun": "SNIPER", "title": "STAGE 10: TESTING LAB"},
		{"stage": 11, "map_id": "police_station", "bots": [{"char": "boris", "diff": 3}, {"char": "cruger", "diff": 3}, {"char": "savage", "diff": 3}, {"char": "ivan", "diff": 3}], "start_gun": "M60", "title": "STAGE 11: ELITE SQUADRON"},
		{"stage": 12, "map_id": "rooftops", "bots": [{"char": "agent", "diff": 3}, {"char": "hideki", "diff": 3}, {"char": "blaire", "diff": 3}], "start_gun": "RIFLE", "title": "STAGE 12: FINAL BOSS — AGENT"},
	]
	return stages[clamped_lvl - 1]


func start_match(config: Dictionary = {}) -> void:
	_ensure_subsystems()
	_clear_match_entities()
	is_paused = false
	_cancel_was_down = false
	pause_selected_index = 0
	_pause_key_was_down.clear()
	_round_over_confirm_was_down = Input.is_key_pressed(KEY_ENTER) or Input.is_key_pressed(KEY_KP_ENTER) or Input.is_key_pressed(KEY_SPACE)

	match_config = config.duplicate(true)
	var raw_mode: String = str(config.get("mode", "vs")).to_lower()
	if raw_mode == "vs_2p":
		game_mode = "vs"
		two_player = true
	else:
		game_mode = raw_mode if raw_mode in ["vs", "stage", "survival"] else "vs"
		two_player = bool(config.get("two_player", false))

	stage_level = clampi(int(config.get("stage_level", 1)), 1, 12)
	survival_wave = 1
	survival_kills = 0

	var roster_pool: Array[String] = [
		"johnny", "boris", "agent", "hideki", "blaire", "savage", "cruger", "ivan", "brody", "mac", "funnyman", "jeff",
		"solaria", "atlas", "shinobi", "tideweaver", "goku", "luffy", "naruto", "saitama"
	]
	var vs_map_pool: Array[String] = ["rooftops", "storage", "police_station", "hazardous", "subway", "tower", "junkyard", "cargo", "steel_harbor"]

	var p1_char: String = str(config.get("p1_char", "johnny")).to_lower()
	if p1_char == "random" or p1_char.is_empty():
		p1_char = roster_pool[randi() % roster_pool.size()]
	var p2_char: String = str(config.get("p2_char", "agent")).to_lower()
	if p2_char == "random" or p2_char.is_empty():
		p2_char = roster_pool[randi() % roster_pool.size()]
	_resolved_p1_char = p1_char
	_resolved_p2_char = p2_char
	var bot_count: int = clampi(int(config.get("bot_count", 0 if two_player else 1)), 0, 7)
	var bot_diff: int = clampi(int(config.get("bot_difficulty", 2)), 1, 4)

	var stage_def: Dictionary = {}
	if game_mode == "stage":
		stage_def = get_stage_definition(stage_level)
		current_map_id = str(stage_def.get("map_id", "rooftops"))
		two_player = bool(config.get("two_player", false))
	elif game_mode == "survival":
		current_map_id = str(config.get("map_id", "survival"))
	else:
		current_map_id = str(config.get("map_id", "rooftops")).to_lower()
		if current_map_id == "random" or current_map_id.is_empty():
			current_map_id = vs_map_pool[randi() % vs_map_pool.size()]

	# 1. Load Map
	map_loader.load_map(current_map_id)

	# 2. Spawn Premade Interactive Props from map data
	_spawn_map_premade_props()

	# 3. Spawn initial weapons at weapon_spawns
	_spawn_initial_map_weapons()

	# 4. Spawn Fighters (P1, P2, Bots)
	# Prioritize static floor/cloud spawns before hanging-crate spawns so multi-bot matches spawn on solid ground first
	var raw_spawns: Array[Vector2] = map_loader.player_spawns.duplicate()
	var spawns: Array[Vector2] = []
	var hanging_spawns: Array[Vector2] = []
	for sp_cand: Vector2 in raw_spawns:
		var has_Crate_below: bool = false
		for pr: Node2D in props:
			if is_instance_valid(pr) and bool(pr.get("is_hanging_crate")):
				if absf(sp_cand.x - pr.global_position.x) <= 18.0 and absf(sp_cand.y - pr.global_position.y) <= 24.0:
					has_Crate_below = true
					break
		if has_Crate_below:
			hanging_spawns.append(sp_cand)
		else:
			spawns.append(sp_cand)
	for hsp: Vector2 in hanging_spawns:
		spawns.append(hsp)
	if spawns.is_empty():
		spawns = [Vector2(94.0, 89.0), Vector2(162.0, 89.0), Vector2(285.0, 188.0), Vector2(392.0, 291.0)]

	var p1_team: int = int(config.get("p1_team", 1 if game_mode in ["stage", "survival"] else 0))
	var p1_pos: Vector2 = spawns[0]
	var p1_node: Node2D = _spawn_fighter_instance(0, p1_char, p1_pos, false, p1_team, bot_diff)

	if game_mode == "stage":
		var start_gun: String = str(stage_def.get("start_gun", ""))
		if not start_gun.is_empty() and p1_node.has_method("equip_weapon"):
			p1_node.call("equip_weapon", start_gun)
		var slot_offset: int = 1
		if two_player:
			var p2_pos_st: Vector2 = spawns[1 % spawns.size()]
			var p2_node_st: Node2D = _spawn_fighter_instance(1, p2_char, p2_pos_st, false, 1, bot_diff)
			if not start_gun.is_empty() and p2_node_st.has_method("equip_weapon"):
				p2_node_st.call("equip_weapon", start_gun)
			slot_offset = 2
		var stage_bots: Array = stage_def.get("bots", []) as Array
		for i: int in range(stage_bots.size()):
			var binfo: Dictionary = stage_bots[i] as Dictionary
			var bpos: Vector2 = spawns[(i + slot_offset) % spawns.size()]
			var bnode: Node2D = _spawn_fighter_instance(
				i + slot_offset,
				str(binfo.get("char", "boris")),
				bpos,
				true,
				2,
				int(binfo.get("diff", 2))
			)
			if not start_gun.is_empty() and bnode.has_method("equip_weapon"):
				bnode.call("equip_weapon", start_gun)
	elif game_mode == "survival":
		if two_player:
			var p2_pos_s: Vector2 = spawns[1 % spawns.size()]
			_spawn_fighter_instance(1, p2_char, p2_pos_s, false, 1, bot_diff)
		_spawn_survival_wave_enemies(2)
	else:
		# VS Mode (1P vs Bots or 2P Local + optional 0..7 Bots)
		var next_slot: int = 1
		if two_player:
			var p2_team: int = int(config.get("p2_team", 0))
			var p2_pos: Vector2 = spawns[1 % spawns.size()]
			_spawn_fighter_instance(1, p2_char, p2_pos, false, p2_team, bot_diff)
			next_slot = 2

		var bot_cfgs_v: Variant = config.get("bot_configs", [])
		var bot_cfgs: Array = bot_cfgs_v as Array if typeof(bot_cfgs_v) == TYPE_ARRAY else []
		for b_i: int in range(bot_count):
			var b_char: String = roster_pool[(b_i + next_slot) % roster_pool.size()]
			var b_team: int = int(config.get("bot_team", 0))
			var b_diff: int = bot_diff
			if b_i < bot_cfgs.size() and typeof(bot_cfgs[b_i]) == TYPE_DICTIONARY:
				var bc: Dictionary = bot_cfgs[b_i] as Dictionary
				var raw_bchar: String = str(bc.get("char", "random")).to_lower()
				if raw_bchar != "random" and not raw_bchar.is_empty():
					b_char = raw_bchar
				b_team = int(bc.get("team", b_team))
				b_diff = clampi(int(bc.get("diff", b_diff)), 1, 4)
			var b_pos: Vector2 = spawns[(next_slot + b_i) % spawns.size()]
			_spawn_fighter_instance(next_slot + b_i, b_char, b_pos, true, b_team, b_diff)

	# 5. Reset round banners, slow-mo, and camera
	game_speed = 1.0
	slowmo_timer = 0.0
	round_state = "GET_READY"
	banner_text = str(stage_def.get("title", "GET READY...")) if game_mode == "stage" else "GET READY..."
	banner_timer = 32.0
	overhead_label_timer = 96.0
	round_over_timer = 48.0
	winner_text = ""
	winner_slot = -1
	winner_team = -1
	_weapon_spawn_timer = 72.0
	_supply_drop_timer = 999999.0
	_survival_spawn_timer = 120.0

	dynamic_camera.reset_for_map(map_loader.map_bounds, p1_pos)
	dynamic_camera.step_camera(4.0, fighters)
	hud_controller.update_hud()

	var audio: Node = MapLoaderScript.get_audio()
	if audio != null and is_instance_valid(audio):
		if audio.has_method("play_bgm"):
			audio.call("play_bgm", "ambient_loop_1")
		elif audio.has_method("play_music"):
			audio.call("play_music", "ambient_loop_1", -6.0)


func _spawn_fighter_instance(
	slot_idx: int,
	char_id: String,
	pos: Vector2,
	is_bot_flag: bool,
	team: int,
	diff: int
) -> Node2D:
	var spawn_pos: Vector2 = pos
	if map_loader != null and is_instance_valid(map_loader) and map_loader.has_method("get_ground_y_below"):
		var gy: float = float(map_loader.call("get_ground_y_below", pos.x, pos.y - 6.0, 26.0, true))
		if gy < INF:
			spawn_pos.y = gy

	var fnode: Node2D = _instantiate_fighter_node()
	fnode.name = ("Bot_" if is_bot_flag else "Player_") + str(slot_idx + 1)
	fnode.set("match_world", self)
	_fighters_container.add_child(fnode)
	if fnode.has_method("setup_fighter"):
		fnode.call("setup_fighter", slot_idx, char_id, spawn_pos, is_bot_flag, team, diff)
	else:
		fnode.global_position = spawn_pos
		fnode.set("slot_index", slot_idx)
		fnode.set("character_id", char_id)
		fnode.set("is_bot", is_bot_flag)
		fnode.set("team_id", team)
		fnode.set("bot_difficulty", diff)

	# Authentic Superfighters Y8 default loadout (Pistol 12 + 3 Grenades in VS/Survival modes)
	var default_loadout_enabled: bool = bool(match_config.get("start_with_loadout", game_mode != "stage"))
	if default_loadout_enabled and fnode.has_method("equip_default_loadout"):
		fnode.call("equip_default_loadout")

	if spawn_pos.x > map_loader.map_bounds.get_center().x:
		fnode.set("facing", -1)
	else:
		fnode.set("facing", 1)
	if fnode.has_method("_sync_rig_view"):
		fnode.call("_sync_rig_view")

	fighters.append(fnode)
	if is_bot_flag:
		bot_controllers[fnode.get_instance_id()] = BotControllerScript.new(diff)
	return fnode


func _spawn_map_premade_props() -> void:
	_next_prop_id = 1
	var hanging_crates: Array[Node2D] = []
	var tabletop_types: Array[String] = ["COMP", "COMP_SCREEN", "PAPER", "LAMP_1", "CRATE_HANGING", "CRATE_HANGING_HOLDER"]

	# 1. Collect all mutually-exclusive random if/else branch groups from Maps.as
	var group_branches: Dictionary = {}
	for pr_data: Dictionary in map_loader.premade_props_data:
		var conds: Variant = pr_data.get("conditions", [])
		if typeof(conds) == TYPE_ARRAY and not (conds as Array).is_empty():
			for c_var: Variant in conds as Array:
				var g_id: int = 0
				var b_id: int = 0
				if typeof(c_var) == TYPE_ARRAY and (c_var as Array).size() >= 2:
					var ca: Array = c_var as Array
					g_id = int(ca[0])
					b_id = int(ca[1])
				elif typeof(c_var) == TYPE_DICTIONARY:
					var cd: Dictionary = c_var as Dictionary
					g_id = int(cd.get("group", 0))
					b_id = int(cd.get("branch", 0))
				if g_id > 0:
					if not group_branches.has(g_id):
						group_branches[g_id] = []
					var arr: Array = group_branches[g_id] as Array
					if not arr.has(b_id):
						arr.append(b_id)
		else:
			var bg: int = int(pr_data.get("branch_group", 0))
			var bid: int = int(pr_data.get("branch_id", 0))
			if bg > 0:
				if not group_branches.has(bg):
					group_branches[bg] = []
				var arr2: Array = group_branches[bg] as Array
				if not arr2.has(bid):
					arr2.append(bid)

	var winning_branches: Dictionary = {}
	for g_key: Variant in group_branches.keys():
		var b_list: Array = group_branches[g_key] as Array
		if not b_list.is_empty():
			winning_branches[g_key] = b_list[randi() % b_list.size()]

	# 2. Spawn props from active branches with authentic random candidate selection
	for pr_data: Dictionary in map_loader.premade_props_data:
		var branch_active: bool = true
		var conds_v: Variant = pr_data.get("conditions", [])
		if typeof(conds_v) == TYPE_ARRAY and not (conds_v as Array).is_empty():
			for c_var: Variant in conds_v as Array:
				var g_id: int = 0
				var b_id: int = 0
				if typeof(c_var) == TYPE_ARRAY and (c_var as Array).size() >= 2:
					var ca: Array = c_var as Array
					g_id = int(ca[0])
					b_id = int(ca[1])
				elif typeof(c_var) == TYPE_DICTIONARY:
					var cd: Dictionary = c_var as Dictionary
					g_id = int(cd.get("group", 0))
					b_id = int(cd.get("branch", 0))
				if g_id > 0 and winning_branches.has(g_id) and int(winning_branches[g_id]) != b_id:
					branch_active = false
					break
		else:
			var bg: int = int(pr_data.get("branch_group", 0))
			var bid: int = int(pr_data.get("branch_id", 0))
			if bg > 0 and winning_branches.has(bg) and int(winning_branches[bg]) != bid:
				branch_active = false
		if not branch_active:
			continue

		var vname: String = str(pr_data.get("var_name", ""))
		# Skip elevator bodies because MapLoader already constructs oscillating AnimatableBody2D for them
		var is_elevator_body: bool = false
		for el: Dictionary in map_loader.elevators:
			if not vname.is_empty() and str(el.get("var_name", "")) == vname:
				is_elevator_body = true
				break
		if is_elevator_body:
			continue

		var candidates: Array = pr_data.get("candidates", []) as Array
		if candidates.is_empty():
			continue
		var chosen_type: String = str(candidates[randi() % candidates.size()]).to_upper().strip_edges()
		if chosen_type == "NONE" or chosen_type.is_empty():
			continue

		var px: float = float(pr_data.get("x", 0.0))
		var py: float = float(pr_data.get("y", 0.0))
		var pang: float = float(pr_data.get("angle", 0.0))

		# Guard against overlapping floor props from duplicate coordinates
		if not (chosen_type in tabletop_types):
			var overlaps_existing: bool = false
			for existing_p: Node2D in props:
				if not is_instance_valid(existing_p):
					continue
				var ex_type: String = str(existing_p.get("prop_type")).to_upper()
				if ex_type in tabletop_types:
					continue
				if absf(px - existing_p.global_position.x) < 14.0 and absf(py - existing_p.global_position.y) < 12.0:
					overlaps_existing = true
					break
			if overlaps_existing:
				continue

		var prop: Node2D = spawn_interactive_prop(chosen_type, Vector2(px, py), pang, vname)
		if chosen_type == "CRATE_HANGING" and prop != null:
			# AS3 Maps.as:441-442 vs 1118-1155, 2535-2559:
			# Only CRATE_HANGING instances with var_name starting with "crate_hanging" have a suspended CRATE_HANGING_HOLDER & rope;
			# unnamed CRATE_HANGING props (e.g. on testing_floor / tower trapdoors) are free dynamic heavy crates resting on the floor/stack!
			if vname.begins_with("crate_hanging"):
				hanging_crates.append(prop)
			else:
				prop.set("is_hanging_released", true)
				prop.set("kinematic", false)

	# Automatically create shootable CRATE_HANGING_HOLDER flush above every suspended CRATE_HANGING (Maps.as:1120, 2536)
	for hcrate: Node2D in hanging_crates:
		var h_height: float = float(hcrate.get("height"))
		var holder_pos: Vector2 = hcrate.global_position + Vector2(0.0, -h_height * 0.5 - 3.5)
		var holder: Node2D = spawn_interactive_prop("CRATE_HANGING_HOLDER", holder_pos, 0.0, str(hcrate.get("var_name")) + "_holder")
		var anchor_y: float = _resolve_hanging_anchor_y(hcrate, holder_pos)
		hcrate.call("link_hanging_holder", holder, anchor_y)

	# Settle initial props onto floor / prop-stacks (bottom-to-top by Y)
	var sorted_props: Array[Node2D] = props.duplicate()
	sorted_props.sort_custom(func(a: Node2D, b: Node2D) -> bool: return a.global_position.y > b.global_position.y)
	for _s: int in range(12):
		for p: Node2D in sorted_props:
			if is_instance_valid(p) and not bool(p.get("kinematic")):
				if p.has_method("step_prop"):
					p.call("step_prop", 1.0)


func spawn_interactive_prop(
	prop_type: String,
	pos: Vector2,
	angle: float = 0.0,
	var_name: String = ""
) -> Node2D:
	var prop: Node2D = InteractivePropScript.new()
	prop.name = prop_type + "_" + str(_next_prop_id)
	prop.set("match_world", self)
	prop.set("map_loader", map_loader)
	_props_container.add_child(prop)
	prop.call("setup_prop", prop_type, pos, angle, var_name, _next_prop_id)
	_next_prop_id += 1
	props.append(prop)
	return prop


func _resolve_hanging_anchor_y(hcrate: Node2D, holder_pos: Vector2) -> float:
	var vn: String = str(hcrate.get("var_name"))
	# Exact AS3 ceiling DistanceJoint anchors (Maps.as:1126-1137 for Hazardous/Cargo, Maps.as:2540-2543 for Storage/Junkyard)
	if current_map_id in ["hazardous", "cargo"]:
		if vn == "crate_hanging_1":
			return 34.0
		if vn == "crate_hanging_2":
			return 128.0
		if vn == "crate_hanging_3":
			return 134.0
	if current_map_id in ["storage", "junkyard"] and vn.begins_with("crate_hanging"):
		return 51.0
	if map_loader != null and is_instance_valid(map_loader):
		var s_var: Variant = map_loader.get("solid_rects")
		if typeof(s_var) == TYPE_ARRAY:
			var best_ceil_y: float = -INF
			var cx: float = hcrate.global_position.x
			for sr_v: Variant in s_var as Array:
				if sr_v is Rect2:
					var sr: Rect2 = sr_v as Rect2
					if cx >= sr.position.x - 2.0 and cx <= sr.end.x + 2.0 and sr.end.y <= holder_pos.y - 12.0:
						if sr.end.y > best_ceil_y:
							best_ceil_y = sr.end.y
			if best_ceil_y > -INF:
				return best_ceil_y
	return minf(51.0, holder_pos.y - 36.0)


func spawn_hanging_crate_pair(pos: Vector2, contained_wpn: String = "BAZOOKA") -> Dictionary:
	var hcrate: Node2D = spawn_interactive_prop("CRATE_HANGING", pos, 0.0, "crate_hanging_custom")
	hcrate.set("contained_weapon_id", contained_wpn)
	var h_height: float = float(hcrate.get("height"))
	var holder_pos: Vector2 = pos + Vector2(0.0, -h_height * 0.5 - 3.5)
	var holder: Node2D = spawn_interactive_prop("CRATE_HANGING_HOLDER", holder_pos, 0.0, "crate_hanging_holder_custom")
	var anchor_y: float = _resolve_hanging_anchor_y(hcrate, holder_pos)
	hcrate.call("link_hanging_holder", holder, anchor_y)
	return {"crate": hcrate, "holder": holder}


func spawn_supply_parachute_crate(x_pos: float = -9999.0, weapon_id: String = "") -> Node2D:
	var drop_x: float = x_pos
	if drop_x <= -9000.0:
		if not map_loader.weapon_spawns.is_empty():
			var valid_ws: Array[Dictionary] = []
			for ws_c: Dictionary in map_loader.weapon_spawns:
				var cx: float = float(ws_c.get("x", 260.0))
				var cy: float = float(ws_c.get("y", 180.0))
				if float(map_loader.call("get_ground_y_below", cx, cy - 10.0, 220.0, true)) < INF:
					valid_ws.append(ws_c)
			var pool: Array = valid_ws if not valid_ws.is_empty() else map_loader.weapon_spawns
			var ws: Dictionary = pool[randi() % pool.size()]
			drop_x = float(ws.get("x", 260.0))
		elif not map_loader.player_spawns.is_empty():
			var ps: Vector2 = map_loader.player_spawns[randi() % map_loader.player_spawns.size()]
			drop_x = ps.x
		else:
			drop_x = map_loader.map_bounds.get_center().x

	var drop_y: float = map_loader.map_bounds.position.y + 18.0
	var crate: Node2D = InteractivePropScript.new()
	crate.name = "SupplyParachuteCrate_" + str(_next_prop_id)
	crate.set("match_world", self)
	crate.set("map_loader", map_loader)
	_props_container.add_child(crate)
	crate.call("setup_supply_parachute_crate", Vector2(drop_x, drop_y), weapon_id, _next_prop_id)
	_next_prop_id += 1
	props.append(crate)
	return crate


class PickupVisualNode extends Node2D:
	var weapon_tex: Texture2D = null
	var highlighted: bool = false
	var settled: bool = true

	func _draw() -> void:
		if weapon_tex != null:
			var tsize: Vector2 = weapon_tex.get_size()
			draw_texture(weapon_tex, Vector2(-tsize.x * 0.5, -tsize.y - 1.0))
		# Draw authentic white 4-corner '[ ]' pickup_sign bracket (Symbol 427.xml Frame 1 / Frame 2)
		var bw: float = 18.0 if not highlighted else 21.0
		var bh: float = 10.0 if not highlighted else 12.5
		var bx: float = -bw * 0.5
		var by: float = -bh - 0.5
		var arm: float = 3.2 if not highlighted else 4.2
		var col: Color = Color(1.0, 1.0, 1.0, 0.9) if not highlighted else Color(1.0, 0.96, 0.52, 1.0)
		var lw: float = 1.0 if not highlighted else 1.5
		draw_line(Vector2(bx, by), Vector2(bx + arm, by), col, lw)
		draw_line(Vector2(bx, by), Vector2(bx, by + arm), col, lw)
		draw_line(Vector2(bx + bw - arm, by), Vector2(bx + bw, by), col, lw)
		draw_line(Vector2(bx + bw, by), Vector2(bx + bw, by + arm), col, lw)
		draw_line(Vector2(bx, by + bh - arm), Vector2(bx, by + bh), col, lw)
		draw_line(Vector2(bx, by + bh), Vector2(bx + arm, by + bh), col, lw)
		draw_line(Vector2(bx + bw - arm, by + bh), Vector2(bx + bw, by + bh), col, lw)
		draw_line(Vector2(bx + bw, by + bh - arm), Vector2(bx + bw, by + bh), col, lw)


func _spawn_initial_map_weapons() -> void:
	var count: int = mini(3, map_loader.weapon_spawns.size())
	for i: int in range(count):
		var ws: Dictionary = map_loader.weapon_spawns[i]
		var wx: float = float(ws.get("x", 260.0))
		var wy: float = float(ws.get("y", 180.0))
		var wid: String = _pick_weapon_from_mask(ws.get("mask", []) as Array, i)
		spawn_weapon_pickup(wid, Vector2(wx, wy), -999, false, i)


func _pick_weapon_from_mask(mask: Array, seed_idx: int = 0) -> String:
	var weighted_pool: Array[String] = []
	for i: int in range(WEAPON_SPAWN_ORDER.size()):
		var enabled: bool = true
		if i < mask.size():
			enabled = int(mask[i]) != 0
		if enabled:
			var w: int = WEAPON_SPAWN_WEIGHTS[i] if i < WEAPON_SPAWN_WEIGHTS.size() else 2
			for _k: int in range(maxi(1, w)):
				weighted_pool.append(WEAPON_SPAWN_ORDER[i])
	if weighted_pool.is_empty():
		return WEAPON_SPAWN_ORDER[seed_idx % WEAPON_SPAWN_ORDER.size()]
	return weighted_pool[(seed_idx * 7 + randi()) % weighted_pool.size()]


func spawn_weapon_pickup(
	weapon_id: String,
	pos: Vector2,
	ammo: int = -999,
	from_sky_crate: bool = false,
	spawn_point_idx: int = -1
) -> void:
	var reg: Node = MapLoaderScript.get_registry()
	var wid: String = weapon_id.to_upper().strip_edges()
	var wdata: Dictionary = reg.call("get_weapon_data", wid) as Dictionary
	if wdata.is_empty():
		wid = "PISTOL"
		wdata = reg.call("get_weapon_data", "PISTOL") as Dictionary

	var final_ammo: int = ammo if ammo != -999 else int(wdata.get("ammo", 12))
	var snap_y: float = float(map_loader.call("get_ground_y_below", pos.x, pos.y - 8.0, 48.0, true))
	var is_settled: bool = (not from_sky_crate) and (snap_y < INF)
	var start_y: float = pos.y
	if not is_settled and snap_y < INF and pos.y >= snap_y - 2.0:
		start_y = snap_y - 2.0
	var final_pos: Vector2 = Vector2(pos.x, snap_y if is_settled else start_y)

	# Enforce AS3 WeaponSpawn.as single-occupancy rule: a spawn point can hold at most ONE LinkedWeapon at a time!
	if spawn_point_idx >= 0:
		for i_ex: int in range(pickups.size() - 1, -1, -1):
			var ex_pk: Dictionary = pickups[i_ex]
			if int(ex_pk.get("spawn_point_idx", -1)) == spawn_point_idx:
				var ex_node: Node2D = ex_pk.get("node", null) as Node2D
				if ex_node != null and is_instance_valid(ex_node):
					if ex_node.get_parent() != null:
						ex_node.get_parent().remove_child(ex_node)
					ex_node.free()
				pickups.remove_at(i_ex)

	var pnode: PickupVisualNode = PickupVisualNode.new()
	pnode.name = "Pickup_" + wid
	pnode.position = final_pos
	pnode.settled = is_settled

	var tex_path: String = str(wdata.get("pickup_texture", ""))
	if tex_path.is_empty():
		tex_path = str(wdata.get("dropped_texture", ""))
	var tex: Texture2D = reg.call("load_cached_texture", tex_path) as Texture2D
	pnode.weapon_tex = tex

	_pickups_container.add_child(pnode)
	pnode.queue_redraw()
	pickups.append({
		"weapon_id": wid,
		"pos": final_pos,
		"vel": Vector2.ZERO if is_settled else Vector2(0.0, 0.5),
		"settled": is_settled,
		"cooldown": 0.0,
		"ammo": final_ammo,
		"from_sky_crate": from_sky_crate,
		"spawn_point_idx": spawn_point_idx,
		"spawn_origin": Vector2(pos.x, snap_y if snap_y < INF else pos.y),
		"despawn_timer": 480.0 if spawn_point_idx >= 0 else 0.0,
		"node": pnode,
	})


func spawn_dropped_weapon(
	weapon_id: String,
	pos: Vector2,
	ammo: int = -999,
	init_vel: Vector2 = Vector2(0.0, -2.0)
) -> void:
	var reg: Node = MapLoaderScript.get_registry()
	var wid: String = weapon_id.to_upper().strip_edges()
	if wid.is_empty() or wid == "FISTS" or wid == "UNARMED":
		return
	var wdata: Dictionary = reg.call("get_weapon_data", wid) as Dictionary
	if wdata.is_empty():
		return
	var final_ammo: int = ammo if ammo != -999 else int(wdata.get("ammo", 12))
	if int(wdata.get("slot", 2)) in [2, 3, 4] and final_ammo <= 0:
		return

	var pnode: PickupVisualNode = PickupVisualNode.new()
	pnode.name = "Dropped_" + wid
	pnode.position = pos
	pnode.settled = false

	var tex_path: String = str(wdata.get("pickup_texture", ""))
	if tex_path.is_empty():
		tex_path = str(wdata.get("dropped_texture", ""))
	var loaded_tex: Texture2D = reg.call("load_cached_texture", tex_path) as Texture2D
	if loaded_tex == null:
		var alt_path: String = str(wdata.get("dropped_texture", ""))
		if not alt_path.is_empty():
			loaded_tex = reg.call("load_cached_texture", alt_path) as Texture2D
	pnode.weapon_tex = loaded_tex

	_pickups_container.add_child(pnode)
	pnode.queue_redraw()
	pickups.append({
		"weapon_id": wid,
		"pos": pos,
		"vel": init_vel,
		"settled": false,
		"cooldown": 18.0,
		"ammo": final_ammo,
		"from_sky_crate": false,
		"node": pnode,
	})


func _find_pickup_ladder_shaft(from_pos: Vector2, to_pos: Vector2) -> Rect2:
	if map_loader == null or not is_instance_valid(map_loader) or absf(to_pos.y - from_pos.y) <= 0.12 or map_loader.get("ladder_rects") == null:
		return Rect2()
	for lr_v: Variant in map_loader.get("ladder_rects") as Array:
		var lr: Rect2 = lr_v as Rect2
		var in_x: bool = (from_pos.x >= lr.position.x and from_pos.x <= lr.end.x) and (to_pos.x >= lr.position.x and to_pos.x <= lr.end.x)
		if not in_x:
			continue
		var min_y: float = minf(from_pos.y, to_pos.y)
		var max_y: float = maxf(from_pos.y, to_pos.y)
		if max_y >= lr.position.y - 14.0 and min_y <= lr.end.y - 4.0:
			return lr
	return Rect2()


func _has_prop_support_below_pickup(ppos: Vector2) -> bool:
	for prop: Node2D in props:
		if not is_instance_valid(prop) or prop.get("is_destroyed") == true or prop.get("has_solid_hitbox") != true:
			continue
		if not prop.has_method("get_solid_support_rect"):
			continue
		var rect: Rect2 = prop.call("get_solid_support_rect") as Rect2
		if rect.size.x > 0.0 and ppos.x >= rect.position.x - 1.5 and ppos.x <= rect.end.x + 1.5 and absf(ppos.y - rect.position.y) <= 2.5:
			return true
	return false


func _pickup_surface_hit(from_pos: Vector2, to_pos: Vector2, include_one_way: bool = true, sweep_elevator_motion: bool = false, allow_ladder_shaft: bool = false) -> Dictionary:
	var best: Dictionary = {"hit": false}
	var best_distance: float = INF
	var shaft: Rect2 = _find_pickup_ladder_shaft(from_pos, to_pos) if allow_ladder_shaft else Rect2()
	# Sweep the bottom and upper body of the dropped item. Endpoint probing
	# missed thin ceilings and snapped items upward after entering a shaft side.
	for offset: Vector2 in [Vector2.ZERO, Vector2(0.0, -4.0)]:
		var hit: Dictionary = map_loader.call("raycast_solid", from_pos + offset, to_pos + offset, -1, false, false) as Dictionary
		if bool(hit.get("hit", false)):
			var point: Vector2 = (hit.get("pos", to_pos + offset) as Vector2) - offset
			var distance: float = from_pos.distance_to(point)
			if distance < best_distance:
				best = {"hit": true, "pos": point, "normal": hit.get("normal", Vector2.UP)}
				best_distance = distance
	var one_way: Dictionary = map_loader.call("raycast_one_way", from_pos, to_pos, -1, sweep_elevator_motion) as Dictionary if include_one_way else {}
	if bool(one_way.get("hit", false)):
		var point: Vector2 = one_way["pos"]
		var skip_ow: bool = (shaft.size.x > 0.0 and point.y < shaft.end.y - 6.0 and point.x >= shaft.position.x and point.x <= shaft.end.x)
		if not skip_ow and from_pos.distance_to(point) < best_distance:
			best = one_way
			best_distance = from_pos.distance_to(point)
	for prop: Node2D in props:
		if not is_instance_valid(prop) or prop.get("is_destroyed") == true or prop.get("has_solid_hitbox") != true:
			continue
		if not prop.has_method("get_solid_support_rect"):
			continue
		var rect: Rect2 = prop.call("get_solid_support_rect") as Rect2
		for offset: Vector2 in [Vector2.ZERO, Vector2(0.0, -4.0)]:
			var hit: Dictionary = map_loader.call("_segment_vs_rect", from_pos + offset, to_pos + offset, rect) as Dictionary
			if bool(hit.get("hit", false)):
				var point: Vector2 = (hit["pos"] as Vector2) - offset
				if from_pos.distance_to(point) < best_distance:
					best = {"hit": true, "pos": point, "normal": hit.get("normal", Vector2.UP)}
					best_distance = from_pos.distance_to(point)
	return best


func _step_pickups(step_24hz: float) -> void:
	var elevator_serial: int = int(map_loader.get("_elevator_motion_serial")) if map_loader != null and is_instance_valid(map_loader) else -1
	var new_elevator_motion: bool = elevator_serial != _last_pickup_elevator_motion_serial
	_last_pickup_elevator_motion_serial = elevator_serial
	if pickups.is_empty():
		return
	var next_pickups: Array[Dictionary] = []
	for pk: Dictionary in pickups:
		var pnode: PickupVisualNode = pk.get("node", null) as PickupVisualNode
		var cd: float = maxf(0.0, float(pk.get("cooldown", 0.0)) - step_24hz)
		pk["cooldown"] = cd
		var portal_cd: float = maxf(0.0, float(pk.get("portal_cd", 0.0)) - step_24hz)
		pk["portal_cd"] = portal_cd
		var settled: bool = bool(pk.get("settled", true))
		var ppos: Vector2 = pk.get("pos", Vector2.ZERO) as Vector2
		var pvel: Vector2 = pk.get("vel", Vector2.ZERO) as Vector2
		var carry_from: Vector2 = pk.get("_elevator_pre_carry_pos", ppos) as Vector2
		var was_carried: bool = pk.has("_elevator_pre_carry_pos")
		pk.erase("_elevator_pre_carry_pos")
		if settled and was_carried and is_instance_valid(map_loader):
			# Carry already accounts for the supporting lift. Its t=0 contact
			# must not mask a solid ceiling/wall crossed by the carried item.
			var carry_hit: Dictionary = _pickup_surface_hit(carry_from, ppos, false)
			if bool(carry_hit.get("hit", false)):
				var carry_normal: Vector2 = carry_hit.get("normal", Vector2.UP) as Vector2
				ppos = (carry_hit["pos"] as Vector2) + carry_normal * 0.02
				if carry_normal.y >= -0.45:
					settled = false
				pk["pos"] = ppos
				pk["settled"] = settled
			carry_from = ppos

		if not settled:
			pvel.y = minf(9.0, pvel.y + 0.42 * step_24hz)
			pvel.x *= pow(0.985, step_24hz)
			var next_pos: Vector2 = ppos + pvel * step_24hz
			if map_loader != null and is_instance_valid(map_loader):
				if portal_cd <= 0.0 and map_loader.has_method("try_teleport_ballistic_segment"):
					var tp_pk: Dictionary = map_loader.call("try_teleport_ballistic_segment", carry_from, next_pos, pvel, 3.0) as Dictionary
					if bool(tp_pk.get("teleported", false)):
						pvel = tp_pk.get("vel", pvel) as Vector2
						var exit_pt: Vector2 = tp_pk.get("exit_origin", next_pos) as Vector2
						var rem_t: float = float(tp_pk.get("remaining_ratio", 0.5))
						carry_from = exit_pt
						ppos = exit_pt
						next_pos = exit_pt + pvel * (step_24hz * rem_t)
						pk["pos"] = ppos
						pk["vel"] = pvel
						pk["portal_cd"] = 4.0
				var can_pass_hatch: bool = not bool(pk.get("from_sky_crate", false)) and int(pk.get("spawn_point_idx", -1)) < 0 and absf(pvel.x) <= 0.6
				var hit: Dictionary = _pickup_surface_hit(carry_from, next_pos, true, new_elevator_motion and not was_carried, can_pass_hatch)
				if bool(hit.get("hit", false)):
					var normal: Vector2 = hit.get("normal", Vector2.UP) as Vector2
					var contact_pos: Vector2 = (hit["pos"] as Vector2) + normal * 0.02
					var carry_remainder: Vector2 = hit.get("surface_remainder", Vector2.ZERO) as Vector2
					next_pos = contact_pos + carry_remainder
					if carry_remainder.length_squared() > 0.000001:
						var remainder_hit: Dictionary = _pickup_surface_hit(contact_pos, next_pos, false)
						if bool(remainder_hit.get("hit", false)):
							var remainder_normal: Vector2 = remainder_hit.get("normal", Vector2.UP) as Vector2
							next_pos = (remainder_hit["pos"] as Vector2) + remainder_normal * 0.02
							normal = remainder_normal
					if normal.y < -0.45 and pvel.y >= 0.0:
						if absf(pvel.y) >= 1.1:
							pvel.y = -pvel.y * 0.42
							pvel.x *= 0.72
						elif absf(pvel.x) >= 0.45:
							pvel.y = 0.0
							pvel.x *= 0.80
						else:
							pvel = Vector2.ZERO
							settled = true
					elif pvel.dot(normal) < 0.0:
						pvel = pvel.bounce(normal) * 0.6
			ppos = next_pos
			pk["pos"] = ppos
			pk["vel"] = pvel
			pk["settled"] = settled
		else:
			# Check if support under settled pickup disappeared (e.g. shattered glass skylight)
			if map_loader != null and is_instance_valid(map_loader) and map_loader.has_method("get_ground_y_below"):
				var gy_check: float = float(map_loader.call("get_ground_y_below", ppos.x, ppos.y - 4.0, 8.0, true))
				if gy_check == INF and not _has_prop_support_below_pickup(ppos):
					pk["settled"] = false
					pk["vel"] = Vector2(0.0, 0.6)

		if pnode != null and is_instance_valid(pnode):
			var new_settled: bool = bool(pk.get("settled", true))
			var need_redraw: bool = (pnode.settled != new_settled) or pnode.highlighted
			pnode.position = ppos
			pnode.settled = new_settled
			pnode.highlighted = false
			if need_redraw:
				pnode.queue_redraw()

		# AS3 WeaponSpawn.as:123 & WeaponSpawnData.as:26-44:
		# Spawn-point weapons despawn after 20s (480 ticks @ 24Hz), blinking during the final 8s (192 ticks) so a new weapon can replace them!
		var sp_idx: int = int(pk.get("spawn_point_idx", -1))
		if sp_idx >= 0:
			var sp_origin: Vector2 = pk.get("spawn_origin", ppos) as Vector2
			if bool(pk.get("settled", true)) and ppos.distance_to(sp_origin) > 16.0:
				pk["spawn_point_idx"] = -1
				pk["despawn_timer"] = 0.0
				if pnode != null and is_instance_valid(pnode):
					pnode.visible = true
			elif bool(pk.get("settled", true)):
				var dtimer: float = float(pk.get("despawn_timer", 480.0)) - step_24hz
				pk["despawn_timer"] = dtimer
				if dtimer <= 0.0:
					if pnode != null and is_instance_valid(pnode):
						if pnode.get_parent() != null:
							pnode.get_parent().remove_child(pnode)
						pnode.free()
					continue
				elif dtimer <= 192.0 and pnode != null and is_instance_valid(pnode):
					pnode.visible = (int(floor(dtimer / 6.0)) % 2) == 0
				elif pnode != null and is_instance_valid(pnode):
					pnode.visible = true

		if map_loader != null and is_instance_valid(map_loader):
			if ppos.y > map_loader.map_bounds.end.y + 60.0:
				if pnode != null and is_instance_valid(pnode):
					if pnode.get_parent() != null:
						pnode.get_parent().remove_child(pnode)
					pnode.free()
				continue
		next_pickups.append(pk)
	pickups = next_pickups


func spawn_floating_text(world_pos: Vector2, text_str: String, col: Color = Color(1.0, 0.94, 0.42, 1.0)) -> void:
	floating_texts.append({
		"pos": world_pos,
		"text": text_str,
		"color": col,
		"age": 0.0,
		"max_age": 24.0,
	})


func try_pickup_near(fighter: Node2D) -> bool:
	return update_fighter_weapon_grab(fighter, true)


func update_fighter_weapon_grab(fighter: Node2D, want_manual_swap: bool) -> bool:
	if fighter == null or not is_instance_valid(fighter):
		return false
	if bool(fighter.get("is_dead")) or bool(fighter.get("climbing")) or bool(fighter.get("ledge_grabbing")) or bool(fighter.get("diving")) or bool(fighter.get("falling")) or bool(fighter.get("knockdowned")):
		return false
	if not want_manual_swap:
		if float(fighter.get("_stagger_frames")) > 0.0:
			return false
	var fpos: Vector2 = fighter.global_position

	# Also check if fighter is standing near an intact SupplyParachuteCrate on the ground
	if want_manual_swap:
		for p_var: Variant in props:
			if not (p_var is Node2D) or not is_instance_valid(p_var):
				continue
			var prop: Node2D = p_var as Node2D
			if bool(prop.get("is_destroyed")) or not bool(prop.get("is_parachute_crate")):
				continue
			if fpos.distance_to(prop.global_position) <= 24.0 and prop.has_method("try_open_supply_crate"):
				prop.call("try_open_supply_crate")
				break

	if pickups.is_empty():
		return false
	var best_idx: int = -1
	var best_dist: float = 22.0

	for i: int in range(pickups.size()):
		var pk: Dictionary = pickups[i]
		if float(pk.get("cooldown", 0.0)) > 0.0:
			continue
		if not want_manual_swap and not bool(pk.get("settled", true)):
			continue
		var ppos: Vector2 = pk.get("pos", Vector2.ZERO) as Vector2
		var d: float = fpos.distance_to(ppos)
		if d <= best_dist:
			best_dist = d
			best_idx = i

	if best_idx < 0:
		return false

	var chosen: Dictionary = pickups[best_idx]
	var wid: String = str(chosen.get("weapon_id", "PISTOL")).to_upper()
	var ammo: int = int(chosen.get("ammo", -999))
	var wdata: Dictionary = MapLoaderScript.get_registry().call("get_weapon_data", wid) as Dictionary
	var category: String = str(wdata.get("category", ""))
	var slot: int = int(wdata.get("slot", 2))
	if slot == 3:
		slot = 2
	var w_display: String = str(wdata.get("display_name", wid)).to_upper()

	# Determine if auto-pickup applies (Player.as:1236-1301 UpdateWeaponGrab):
	# - Empty target slot -> auto-picks up on touch/walk/roll!
	# - Occupied target slot -> highlights white '[ ]' bracket and requires Down + Attack (want_manual_swap)!
	var slot_empty: bool = true
	if fighter.has_method("is_weapon_slot_empty_for"):
		slot_empty = bool(fighter.call("is_weapon_slot_empty_for", wid))
	else:
		var inv_v: Variant = fighter.get("inventory")
		var am_v: Variant = fighter.get("inventory_ammo")
		if typeof(inv_v) == TYPE_DICTIONARY and typeof(am_v) == TYPE_DICTIONARY:
			var inv_d: Dictionary = inv_v as Dictionary
			var am_d: Dictionary = am_v as Dictionary
			if slot == 1:
				var cur_m: String = str(inv_d.get(1, "FISTS")).to_upper()
				slot_empty = cur_m.is_empty() or cur_m == "FISTS" or cur_m == "UNARMED"
			elif slot == 2:
				slot_empty = (str(inv_d.get(2, "")).is_empty() or int(am_d.get(2, 0)) <= 0) and (str(inv_d.get(3, "")).is_empty() or int(am_d.get(3, 0)) <= 0)
			elif slot == 4:
				slot_empty = str(inv_d.get(4, "")).is_empty() or int(am_d.get(4, 0)) <= 0
			elif slot == 5:
				if wid in ["MEDKIT", "PILLS"]:
					slot_empty = float(fighter.get("hp")) < float(fighter.get("max_hp"))
				else:
					slot_empty = str(inv_d.get(5, "")).is_empty() or int(am_d.get(5, 0)) <= 0

	if not slot_empty and not want_manual_swap:
		var pnode_hl: PickupVisualNode = chosen.get("node", null) as PickupVisualNode
		if pnode_hl != null and is_instance_valid(pnode_hl):
			pnode_hl.highlighted = true
			pnode_hl.queue_redraw()
		return false

	# If swapping an occupied weapon slot via Down + Attack, inspect current weapon in that slot
	var old_wid: String = ""
	var old_ammo: int = -1
	if not slot_empty and want_manual_swap and wid not in ["MEDKIT", "PILLS"] and slot in [1, 2, 4, 5]:
		var inv_swap: Variant = fighter.get("inventory")
		var am_swap: Variant = fighter.get("inventory_ammo")
		if typeof(inv_swap) == TYPE_DICTIONARY and typeof(am_swap) == TYPE_DICTIONARY:
			var idict: Dictionary = inv_swap as Dictionary
			var adict: Dictionary = am_swap as Dictionary
			old_wid = str(idict.get(slot, "")).to_upper()
			old_ammo = int(adict.get(slot, -1))
			if slot == 2 and (old_wid.is_empty() or old_ammo <= 0):
				old_wid = str(idict.get(3, "")).to_upper()
				old_ammo = int(adict.get(3, -1))

	var default_ammo: int = int(wdata.get("ammo", 12))
	if wid in ["SHOTGUN", "SAWED_OFF"] and ammo == -999:
		default_ammo = 8 if wid == "SHOTGUN" else 6
	elif wid == "UZI" and ammo == -999:
		default_ammo = 25
	elif wid == "FLAMETHROWER" and ammo == -999:
		default_ammo = 40
	var pickup_ammo: int = ammo if ammo > 0 else default_ammo
	var stacked_same_ammo: bool = (old_wid == wid and slot in [2, 4] and old_ammo > 0)

	if category == "powerup" or int(wdata.get("slot", 0)) == 5:
		if wid in ["MEDKIT", "PILLS"]:
			var heal: float = float(wdata.get("heal_amount", 50.0))
			var cur_hp: float = float(fighter.get("hp")) if fighter.get("hp") != null else 100.0
			var max_hp: float = float(fighter.get("max_hp")) if fighter.get("max_hp") != null else 100.0
			fighter.set("hp", minf(max_hp, cur_hp + heal))
			fighter.set("burn_state", 0.0)
			fighter.set("burned", false)
			MapLoaderScript.play_sfx_at("powerup", fpos)
			spawn_floating_text(fpos + Vector2(0.0, -20.0), "+HP", Color(0.35, 1.0, 0.45, 1.0))
		elif wid in ["SLOMO05", "SLOMO10"]:
			# Store SLOMO powerup in the 4th HUD box (inventory[5]); only activates when pressing Key 4 (powerup)!
			if fighter.has_method("equip_weapon"):
				fighter.call("equip_weapon", wid, 1)
			MapLoaderScript.play_sfx_at("accept", fpos)
			spawn_floating_text(fpos + Vector2(0.0, -20.0), w_display, Color(0.45, 0.9, 1.0, 1.0))
		elif fighter.has_method("equip_weapon"):
			fighter.call("equip_weapon", wid, pickup_ammo)
			spawn_floating_text(fpos + Vector2(0.0, -20.0), w_display, Color(1.0, 0.94, 0.42, 1.0))
	else:
		if fighter.has_method("equip_weapon"):
			if stacked_same_ammo:
				fighter.call("equip_weapon", wid, old_ammo + pickup_ammo)
			else:
				fighter.call("equip_weapon", wid, pickup_ammo)
		MapLoaderScript.play_sfx_at("accept", fpos)
		var float_label: String = (w_display + " +" + str(pickup_ammo)) if stacked_same_ammo else w_display
		spawn_floating_text(fpos + Vector2(0.0, -20.0), float_label, Color(1.0, 0.94, 0.42, 1.0))

	var pnode: Node2D = chosen.get("node", null) as Node2D
	if pnode != null and is_instance_valid(pnode):
		if pnode.get_parent() != null:
			pnode.get_parent().remove_child(pnode)
		pnode.free()
	pickups.remove_at(best_idx)

	# Leave the old weapon on the ground when swapping for a different weapon OR when swapping a non-stacking melee/powerup of the same type
	if not old_wid.is_empty() and old_wid != "FISTS" and old_wid != "UNARMED" and not stacked_same_ammo:
		var f_dir: int = int(fighter.get("facing")) if fighter.get("facing") != null else 1
		spawn_dropped_weapon(old_wid, fpos + Vector2(0.0, -5.0), old_ammo, Vector2(float(f_dir) * 1.1, -1.8))

	return true


func activate_slowmo(duration_frames: float = 120.0, speed_scale: float = 0.5) -> void:
	slowmo_timer = maxf(slowmo_timer, duration_frames)
	game_speed = speed_scale


func trigger_ultimate_cutin(fighter: Node2D, sk_def: Dictionary) -> void:
	if fighter == null or not is_instance_valid(fighter):
		return
	var cid: String = str(fighter.get("character_id")).to_lower()
	var dname: String = str(fighter.get("display_name")).to_upper()
	var sname: String = str(sk_def.get("name", "ULTIMATE")).to_upper()
	var r_spec: Dictionary = fighter.get("resource_spec") as Dictionary if typeof(fighter.get("resource_spec")) == TYPE_DICTIONARY else {}
	var col: Color = Color.from_string(str(r_spec.get("bar_color", "#FFCC22")), Color(1.0, 0.85, 0.25, 1.0))
	var bpath: String = str(sk_def.get("cutin_banner", "res://assets/sprites/cutins/" + cid + "_cutin.png"))
	var f_slot: int = int(fighter.get("slot_index")) if fighter.get("slot_index") != null else 0
	var entry: Dictionary = {
		"slot_index": f_slot,
		"char_id": cid,
		"char_name": dname,
		"skill_name": sname,
		"banner_path": bpath,
		"color": col,
		"timer": 0.42,
		"max_timer": 0.42,
	}
	active_cutin = entry.duplicate()
	# EC-32: Support Dual Clash Split Cut-In when 2 fighters cast Ultimate simultaneously!
	for i: int in range(active_cutins.size() - 1, -1, -1):
		if int(active_cutins[i].get("slot_index", -1)) == f_slot:
			active_cutins.remove_at(i)
	if active_cutins.size() >= 2:
		active_cutins.pop_front()
	active_cutins.append(entry)
	# Brief dramatic anime cut-in time-dilation (0.35s)
	slowmo_timer = maxf(slowmo_timer, 9.0)
	game_speed = minf(game_speed, 0.45)
	MapLoaderScript.play_sfx("explosion")


func spawn_shadow_clone(owner_fighter: Node2D) -> Node2D:
	if owner_fighter == null or not is_instance_valid(owner_fighter) or bool(owner_fighter.get("is_dead")):
		return null
	# EC-12: Cap active Shadow Clones per Naruto at 2; despawn oldest if exceeded
	var active_clones: Array[Node2D] = []
	for f: Node2D in fighters:
		if is_instance_valid(f) and bool(f.get("is_summoned_clone")) and f.get("summon_owner") == owner_fighter and not bool(f.get("is_dead")):
			active_clones.append(f)
	while active_clones.size() >= 2:
		var oldest: Node2D = active_clones.pop_front()
		if is_instance_valid(oldest):
			fighters.erase(oldest)
			oldest.queue_free()

	var f_dir: int = int(owner_fighter.get("facing")) if owner_fighter.get("facing") != null else 1
	var raw_pos: Vector2 = owner_fighter.global_position + Vector2(float(f_dir) * 20.0, 0.0)
	var spawn_pos: Vector2 = owner_fighter.call("resolve_safe_teleport_position", raw_pos) as Vector2 if owner_fighter.has_method("resolve_safe_teleport_position") else raw_pos
	var o_team: int = int(owner_fighter.get("team_id")) if owner_fighter.get("team_id") != null else 0
	if o_team == 0:
		o_team = 10 + int(owner_fighter.get("slot_index"))
		owner_fighter.set("team_id", o_team)

	var clone_node: Node2D = _spawn_fighter_instance(fighters.size(), str(owner_fighter.get("character_id")), spawn_pos, true, o_team, 3)
	clone_node.name = "ShadowClone_" + str(clone_node.get_instance_id())
	clone_node.set("is_summoned_clone", true)
	clone_node.set("summon_owner", owner_fighter)
	clone_node.set("summon_lifetime_sec", 4.0)
	clone_node.set("max_hp", 15.0)
	clone_node.set("hp", 15.0)
	clone_node.set("inventory", {1: "FISTS", 2: "", 3: "", 4: "", 5: ""})
	clone_node.set("inventory_ammo", {1: -1, 2: 0, 3: 0, 4: 0, 5: 0})
	return clone_node


func _physics_process(delta: float) -> void:
	_handle_match_hotkeys()
	if is_paused:
		return
	var step_24hz: float = delta * FLASH_FPS * game_speed
	step_match(step_24hz)


func step_match(step_24hz: float) -> void:
	if is_paused:
		return
	# 1. Update round banner & slow-motion timers
	var raw_step: float = step_24hz / maxf(0.1, game_speed)
	if not active_cutin.is_empty():
		var ct: float = float(active_cutin.get("timer", 0.0)) - (raw_step / 24.0)
		if ct <= 0.0:
			active_cutin.clear()
		else:
			active_cutin["timer"] = ct
	if not active_cutins.is_empty():
		var next_cis: Array[Dictionary] = []
		for ci_d: Dictionary in active_cutins:
			var rem_ci: float = float(ci_d.get("timer", 0.0)) - (raw_step / 24.0)
			if rem_ci > 0.0:
				ci_d["timer"] = rem_ci
				next_cis.append(ci_d)
		active_cutins = next_cis
	if overhead_label_timer > 0.0:
		overhead_label_timer = maxf(0.0, overhead_label_timer - raw_step)

	if round_state == "GET_READY":
		banner_timer -= raw_step
		if banner_timer <= 14.0 and banner_text != "FIGHT!":
			banner_text = "FIGHT!"
		if banner_timer <= 0.0:
			round_state = "FIGHT"
			banner_text = ""

	if slowmo_timer > 0.0:
		slowmo_timer -= raw_step
		if slowmo_timer <= 0.0 and round_state != "ROUND_OVER":
			game_speed = 1.0

	if not floating_texts.is_empty():
		var next_ft: Array[Dictionary] = []
		for ft: Dictionary in floating_texts:
			var f_age: float = float(ft.get("age", 0.0)) + raw_step
			var f_max: float = float(ft.get("max_age", 24.0))
			if f_age < f_max:
				ft["age"] = f_age
				ft["pos"] = (ft.get("pos", Vector2.ZERO) as Vector2) + Vector2(0.0, -0.65 * raw_step)
				next_ft.append(ft)
		floating_texts = next_ft

	# 2. Step Map (elevators, portals, clouds, lamps) & Pickups
	if map_loader != null and is_instance_valid(map_loader):
		map_loader.step_map(step_24hz)
	_step_pickups(step_24hz)

	# 3. Step Interactive Props
	for prop_var: Variant in props:
		if prop_var is Node2D and is_instance_valid(prop_var) and (prop_var as Node2D).has_method("step_prop"):
			(prop_var as Node2D).call("step_prop", step_24hz)

	# 4. Step Fighters (P1, P2, AI Bots, and Summoned Clones)
	var valid_fighters: Array[Node2D] = []
	for f_var: Variant in fighters:
		if is_instance_valid(f_var) and f_var is Node2D:
			valid_fighters.append(f_var as Node2D)
	fighters = valid_fighters

	for f_var: Variant in fighters.duplicate():
		if not (f_var is Node2D) or not is_instance_valid(f_var):
			continue
		var f: Node2D = f_var as Node2D
		var is_dead_before: bool = bool(f.get("is_dead"))

		# Pit / Acid kill check
		var pit_limit_y: float = minf(map_loader.map_bounds.end.y + 45.0, map_loader.acid_kill_y)
		if not is_dead_before and f.global_position.y >= pit_limit_y:
			f.set("hp", 0.0)
			f.set("is_dead", true)
			f.set("current_state", "DEAD")
			MapLoaderScript.get_audio().call("play_sfx_at", "wilhelm", f.global_position)
			is_dead_before = true

		var input_dict: Dictionary = {}
		if round_state == "GET_READY":
			input_dict = {"left": false, "right": false, "up": false, "down": false, "jump": false, "attack": false, "sprint": false}
		elif bool(f.get("is_bot")):
			var bctrl: RefCounted = bot_controllers.get(f.get_instance_id(), null) as RefCounted
			if bctrl == null:
				bctrl = BotControllerScript.new(int(f.get("bot_difficulty")) if f.get("bot_difficulty") != null else 2)
				bot_controllers[f.get_instance_id()] = bctrl
			input_dict = bctrl.call("compute_bot_input", f, self, step_24hz) as Dictionary

		if f.has_method("step_fighter"):
			f.call("step_fighter", step_24hz, input_dict)
		if not is_instance_valid(f):
			fighters.erase(f)
			continue

		if not bool(f.get("is_dead")) and not bool(f.get("is_summoned_clone")):
			var bot_manual_swap: bool = bool(f.get("is_bot")) and bool(input_dict.get("down", false)) and bool(input_dict.get("attack", false))
			update_fighter_weapon_grab(f, bot_manual_swap)

		# Count survival kills when a non-clone bot dies
		if game_mode == "survival" and not is_dead_before and bool(f.get("is_dead")) and bool(f.get("is_bot")) and not bool(f.get("is_summoned_clone")):
			survival_kills += 1

	# 5. Step Projectiles & Fire Hazards
	if projectile_manager != null and is_instance_valid(projectile_manager) and projectile_manager.has_method("step_projectiles"):
		projectile_manager.call("step_projectiles", step_24hz)
	if fire_hazard_system != null and is_instance_valid(fire_hazard_system) and fire_hazard_system.has_method("step_hazards"):
		fire_hazard_system.call("step_hazards", step_24hz)

	# 6. Authentic periodic weapon & powerup spawns (WeaponSpawn.as: every 72 frames from unoccupied map weapon_spawns)
	if round_state == "FIGHT":
		_weapon_spawn_timer -= step_24hz
		if _weapon_spawn_timer <= 0.0:
			_weapon_spawn_timer = 72.0
			if pickups.size() < 7 and not map_loader.weapon_spawns.is_empty():
				var free_indices: Array[int] = []
				for ws_i: int in range(map_loader.weapon_spawns.size()):
					var ws_cand: Dictionary = map_loader.weapon_spawns[ws_i]
					var ws_pos: Vector2 = Vector2(float(ws_cand.get("x", 260.0)), float(ws_cand.get("y", 180.0)))
					if float(map_loader.call("get_ground_y_below", ws_pos.x, ws_pos.y - 10.0, 220.0, true)) >= INF:
						continue
					var occupied: bool = false
					for pk_ex: Dictionary in pickups:
						if int(pk_ex.get("spawn_point_idx", -1)) == ws_i:
							occupied = true
							break
						var pk_p: Vector2 = pk_ex.get("pos", Vector2.ZERO) as Vector2
						if absf(pk_p.x - ws_pos.x) <= 14.0 and absf(pk_p.y - ws_pos.y) <= 28.0:
							occupied = true
							break
					if not occupied:
						free_indices.append(ws_i)
				if not free_indices.is_empty():
					var chosen_idx: int = free_indices[randi() % free_indices.size()]
					var ws: Dictionary = map_loader.weapon_spawns[chosen_idx]
					var wid: String = _pick_weapon_from_mask(ws.get("mask", []) as Array, randi())
					spawn_weapon_pickup(wid, Vector2(float(ws.get("x", 260.0)), float(ws.get("y", 180.0))), -999, false, chosen_idx)

		if game_mode == "survival":
			_step_survival_spawner(step_24hz)

	# 7. Evaluate survivor / round completion
	if round_state != "ROUND_OVER":
		_evaluate_round_completion()

	# 8. Step Camera (excluding temporary summoned clones per EC-15) & HUD
	if dynamic_camera != null and is_instance_valid(dynamic_camera):
		var cam_fighters: Array[Node2D] = []
		for cf: Node2D in fighters:
			if is_instance_valid(cf) and not bool(cf.get("is_summoned_clone")):
				cam_fighters.append(cf)
		dynamic_camera.step_camera(step_24hz, cam_fighters)
	if hud_controller != null and is_instance_valid(hud_controller):
		hud_controller.update_hud()


func _step_survival_spawner(step_24hz: float) -> void:
	var alive_bots: int = 0
	for f: Node2D in fighters:
		if is_instance_valid(f) and bool(f.get("is_bot")) and not bool(f.get("is_summoned_clone")) and not bool(f.get("is_dead")):
			alive_bots += 1

	_survival_spawn_timer -= step_24hz
	if alive_bots == 0 or (_survival_spawn_timer <= 0.0 and alive_bots < 3):
		survival_wave += 1
		_survival_spawn_timer = 180.0
		_spawn_survival_wave_enemies(mini(4, 1 + (survival_wave / 2)))


func _spawn_survival_wave_enemies(count: int) -> void:
	var spawns: Array[Vector2] = map_loader.player_spawns
	if spawns.is_empty():
		spawns = [Vector2(120.0, 90.0), Vector2(420.0, 180.0)]
	var pool: Array[String] = ["boris", "savage", "ivan", "cruger", "hideki", "blaire", "brody", "mac", "agent"]
	var diff: int = clampi(1 + survival_wave / 3, 1, 3)

	for i: int in range(count):
		var slot_idx: int = fighters.size()
		var cid: String = pool[(survival_wave + i) % pool.size()]
		var pos: Vector2 = spawns[(survival_wave + i) % spawns.size()]
		var bnode: Node2D = _spawn_fighter_instance(slot_idx, cid, pos, true, 2, diff)
		if survival_wave >= 2 and bnode.has_method("equip_weapon"):
			var guns: Array[String] = ["PISTOL", "UZI", "SHOTGUN", "RIFLE", "MACHETE"]
			bnode.call("equip_weapon", guns[(survival_wave + i) % guns.size()])


func _evaluate_round_completion() -> void:
	if fighters.size() <= 1:
		return

	var alive_fighters: Array[Node2D] = []
	var alive_teams: Dictionary = {}
	var human_alive: bool = false

	for f: Node2D in fighters:
		if is_instance_valid(f) and not bool(f.get("is_dead")) and not bool(f.get("is_summoned_clone")):
			alive_fighters.append(f)
			var tid: int = int(f.get("team_id")) if f.get("team_id") != null else 0
			if tid == 0:
				# Free-for-all: treat each fighter as its own unique team key (-100 - slot)
				var sidx: int = int(f.get("slot_index")) if f.get("slot_index") != null else f.get_instance_id()
				alive_teams[-100 - sidx] = f
			else:
				alive_teams[tid] = f
			if not bool(f.get("is_bot")):
				human_alive = true

	if game_mode == "survival":
		if not human_alive:
			_trigger_round_over("SURVIVAL OVER — KILLS: " + str(survival_kills), -1, 2)
		return

	if alive_fighters.is_empty():
		_trigger_round_over("DRAW GAME!", -1, -1)
	elif alive_teams.size() == 1:
		var sole: Node2D = alive_fighters[0]
		var s_slot: int = int(sole.get("slot_index")) if sole.get("slot_index") != null else 0
		var s_team: int = int(sole.get("team_id")) if sole.get("team_id") != null else 0
		var s_bot: bool = bool(sole.get("is_bot"))

		if game_mode == "stage":
			if not s_bot and s_slot == 0:
				if stage_level >= 12:
					agent_unlocked = true
					_trigger_round_over("CAMPAIGN COMPLETE — AGENT UNLOCKED!", 0, 1)
				else:
					_trigger_round_over("STAGE CLEAR!", 0, 1)
			else:
				_trigger_round_over("STAGE FAILED!", s_slot, 2)
		else:
			if not s_bot and s_slot == 0:
				_trigger_round_over("PLAYER 1 WINS!", 0, s_team)
			elif not s_bot and s_slot == 1:
				_trigger_round_over("PLAYER 2 WINS!", 1, s_team)
			else:
				var dname: String = str(sole.get("display_name")).to_upper()
				_trigger_round_over(dname + " (BOT) WINS!", s_slot, s_team)


func _trigger_round_over(result_banner: String, win_slot: int, win_team: int) -> void:
	round_state = "ROUND_OVER"
	winner_text = result_banner
	banner_text = result_banner
	banner_timer = 9999.0
	winner_slot = win_slot
	winner_team = win_team
	# Cinematic Slow-Motion on final knockout blow!
	game_speed = 0.25
	slowmo_timer = 48.0
	MapLoaderScript.play_sfx("groovy")


func restart_current_match() -> void:
	var cfg: Dictionary = match_config.duplicate(true)
	if not current_map_id.is_empty():
		cfg["map_id"] = current_map_id
	if not _resolved_p1_char.is_empty():
		cfg["p1_char"] = _resolved_p1_char
	if not _resolved_p2_char.is_empty():
		cfg["p2_char"] = _resolved_p2_char
	cfg["stage_level"] = stage_level
	start_match(cfg)


func _snapshot_pause_keys_down() -> void:
	var tracked_keys: Array[Key] = [
		KEY_UP, KEY_W, KEY_DOWN, KEY_S,
		KEY_LEFT, KEY_A, KEY_RIGHT, KEY_D,
		KEY_ENTER, KEY_KP_ENTER, KEY_SPACE,
		KEY_R, KEY_C, KEY_TAB, KEY_M, KEY_Z, KEY_Q,
	]
	for k: Key in tracked_keys:
		_pause_key_was_down[int(k)] = Input.is_key_pressed(k)


func _is_pause_key_just_pressed(keys: Array[Key]) -> bool:
	var any_down: bool = false
	var was_any_down: bool = false
	for k: Key in keys:
		var down_now: bool = Input.is_key_pressed(k)
		if down_now:
			any_down = true
		if bool(_pause_key_was_down.get(int(k), false)):
			was_any_down = true
		_pause_key_was_down[int(k)] = down_now
	return any_down and not was_any_down


func set_paused_state(paused_flag: bool) -> void:
	if is_paused == paused_flag:
		return
	is_paused = paused_flag
	_snapshot_pause_keys_down()
	if is_paused:
		pause_selected_index = 0
		if dynamic_camera != null and is_instance_valid(dynamic_camera) and dynamic_camera.get("show_all") != null:
			pause_camera_wide = bool(dynamic_camera.get("show_all"))
		if AudioServer.get_bus_count() > 0:
			if AudioServer.is_bus_mute(0):
				pause_audio_mode = 2
			elif AudioServer.get_bus_volume_db(0) <= -3.0:
				pause_audio_mode = 1
			else:
				pause_audio_mode = 0
		for fighter: Node2D in fighters:
			if is_instance_valid(fighter):
				fighter.call("_notification", NOTIFICATION_PAUSED)
	else:
		_round_over_confirm_was_down = Input.is_key_pressed(KEY_ENTER) or Input.is_key_pressed(KEY_KP_ENTER) or Input.is_key_pressed(KEY_SPACE)
		for fighter: Node2D in fighters:
			if is_instance_valid(fighter) and fighter.has_method("sync_input_baseline_on_unpause"):
				fighter.call("sync_input_baseline_on_unpause")
	if hud_controller != null and is_instance_valid(hud_controller):
		hud_controller.call("update_hud")


func execute_pause_menu_action(action_idx: int, dir: int = 1) -> void:
	var idx: int = posmod(action_idx, PAUSE_MENU_COUNT)
	if idx == 0:
		# 0: RESUME MATCH
		MapLoaderScript.play_sfx("accept")
		set_paused_state(false)
	elif idx == 1:
		# 1: QUICK RESTART (same map, mode, fighters, and stage)
		MapLoaderScript.play_sfx("accept")
		restart_current_match()
	elif idx == 2:
		# 2: CHANGE MAP / SETUP
		MapLoaderScript.play_sfx("accept")
		set_paused_state(false)
		game_speed = 1.0
		var target_panel: String = "MAP_SELECTION"
		if game_mode == "stage":
			target_panel = "STAGE_SELECT"
		elif game_mode == "survival":
			target_panel = "VS_PLAYER_SETUP"
		if get_signal_connection_list("request_open_setup").size() > 0:
			request_open_setup.emit(target_panel)
		else:
			request_return_to_menu.emit()
	elif idx == 3:
		# 3: AUDIO: ON 100% / LOW 50% / MUTE
		pause_audio_mode = posmod(pause_audio_mode + (1 if dir >= 0 else -1), 3)
		if AudioServer.get_bus_count() > 0:
			if pause_audio_mode == 0:
				AudioServer.set_bus_mute(0, false)
				AudioServer.set_bus_volume_db(0, 0.0)
			elif pause_audio_mode == 1:
				AudioServer.set_bus_mute(0, false)
				AudioServer.set_bus_volume_db(0, -6.0)
			else:
				AudioServer.set_bus_mute(0, true)
		if pause_audio_mode != 2:
			MapLoaderScript.play_sfx("aim_small")
		if hud_controller != null and is_instance_valid(hud_controller):
			hud_controller.call("update_hud")
	elif idx == 4:
		# 4: CAMERA: AUTO ZOOM / WIDE ARENA
		pause_camera_wide = not pause_camera_wide
		if dynamic_camera != null and is_instance_valid(dynamic_camera):
			dynamic_camera.set("show_all", pause_camera_wide)
			var cam_fighters: Array[Node2D] = []
			for cf: Node2D in fighters:
				if is_instance_valid(cf) and not bool(cf.get("is_summoned_clone")):
					cam_fighters.append(cf)
			dynamic_camera.step_camera(24.0, cam_fighters)
		MapLoaderScript.play_sfx("aim_small")
		if hud_controller != null and is_instance_valid(hud_controller):
			hud_controller.call("update_hud")
	elif idx == 5:
		# 5: MAIN MENU
		MapLoaderScript.play_sfx("cancel")
		set_paused_state(false)
		game_speed = 1.0
		request_return_to_menu.emit()


func _unhandled_input(event: InputEvent) -> void:
	if not is_paused or not visible or hud_controller == null or not is_instance_valid(hud_controller):
		return
	if not hud_controller.has_method("get_pause_item_rects"):
		return
	var vp_size: Vector2 = get_viewport_rect().size
	var item_rects: Array[Rect2] = hud_controller.call("get_pause_item_rects", vp_size) as Array[Rect2]
	if event is InputEventMouseMotion:
		var mm: InputEventMouseMotion = event as InputEventMouseMotion
		for i: int in range(item_rects.size()):
			if item_rects[i].has_point(mm.position) and pause_selected_index != i:
				pause_selected_index = i
				hud_controller.call("update_hud")
				break
	elif event is InputEventMouseButton:
		var mb: InputEventMouseButton = event as InputEventMouseButton
		if mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT:
			for i: int in range(item_rects.size()):
				if item_rects[i].has_point(mb.position):
					pause_selected_index = i
					execute_pause_menu_action(i, 1)
					get_viewport().set_input_as_handled()
					break


func _handle_match_hotkeys() -> void:
	var cancel_down: bool = Input.is_key_pressed(KEY_ESCAPE) or Input.is_action_pressed("ui_cancel")
	if cancel_down and not _cancel_was_down:
		if round_state == "ROUND_OVER" or Input.is_key_pressed(KEY_SHIFT):
			set_paused_state(false)
			game_speed = 1.0
			request_return_to_menu.emit()
			_cancel_was_down = true
			return
		set_paused_state(not is_paused)
		_cancel_was_down = cancel_down
		return
	if not cancel_down:
		_cancel_was_down = false

	if is_paused:
		if _is_pause_key_just_pressed([KEY_UP, KEY_W]):
			pause_selected_index = posmod(pause_selected_index - 1, PAUSE_MENU_COUNT)
			MapLoaderScript.play_sfx("aim_small")
			if hud_controller != null and is_instance_valid(hud_controller):
				hud_controller.call("update_hud")
			return
		if _is_pause_key_just_pressed([KEY_DOWN, KEY_S]):
			pause_selected_index = posmod(pause_selected_index + 1, PAUSE_MENU_COUNT)
			MapLoaderScript.play_sfx("aim_small")
			if hud_controller != null and is_instance_valid(hud_controller):
				hud_controller.call("update_hud")
			return
		if _is_pause_key_just_pressed([KEY_LEFT, KEY_A]):
			if pause_selected_index in [3, 4]:
				execute_pause_menu_action(pause_selected_index, -1)
			return
		if _is_pause_key_just_pressed([KEY_RIGHT, KEY_D]):
			if pause_selected_index in [3, 4]:
				execute_pause_menu_action(pause_selected_index, 1)
			return
		if _is_pause_key_just_pressed([KEY_ENTER, KEY_KP_ENTER, KEY_SPACE]):
			execute_pause_menu_action(pause_selected_index, 1)
			return
		if _is_pause_key_just_pressed([KEY_R]):
			pause_selected_index = 1
			execute_pause_menu_action(1, 1)
			return
		if _is_pause_key_just_pressed([KEY_C, KEY_TAB]):
			pause_selected_index = 2
			execute_pause_menu_action(2, 1)
			return
		if _is_pause_key_just_pressed([KEY_M]):
			pause_selected_index = 3
			execute_pause_menu_action(3, 1)
			return
		if _is_pause_key_just_pressed([KEY_Z]):
			pause_selected_index = 4
			execute_pause_menu_action(4, 1)
			return
		if _is_pause_key_just_pressed([KEY_Q]):
			pause_selected_index = 5
			execute_pause_menu_action(5, 1)
			return
		return

	if round_state == "ROUND_OVER":
		var confirm_down: bool = Input.is_key_pressed(KEY_ENTER) or Input.is_key_pressed(KEY_KP_ENTER) or Input.is_key_pressed(KEY_SPACE)
		if confirm_down and not _round_over_confirm_was_down:
			_round_over_confirm_was_down = true
			if game_mode == "stage" and (winner_text == "STAGE CLEAR!" or winner_slot == 0) and stage_level < 12:
				match_config["stage_level"] = stage_level + 1
			start_match(match_config)
		elif not confirm_down:
			_round_over_confirm_was_down = false

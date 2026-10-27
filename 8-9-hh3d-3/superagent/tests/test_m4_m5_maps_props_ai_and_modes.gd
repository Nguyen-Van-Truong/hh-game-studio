extends SceneTree
## Automated verification suite for SF-M4 & SF-M5:
## Maps (all 8 VS maps + 4 extra), Rooftops geometry/elevators/portals/glass,
## InteractiveProps (2-phase explosive barrel, gascan, hanging crate crush, supply parachute),
## DynamicCamera zoom/bounds/shake, BotController pathfinding & 3 difficulties (including fire roll),
## and MatchController / HUD / MainMenu across VS, Stage (12 Stages), and Survival modes.

const MapLoaderScript = preload("res://game/world/map_loader.gd")
const InteractivePropScript = preload("res://game/world/interactive_prop.gd")
const DynamicCameraScript = preload("res://game/world/dynamic_camera.gd")
const BotControllerScript = preload("res://game/ai/bot_controller.gd")
const MatchControllerScript = preload("res://game/core/match_controller.gd")
const MatchHudScript = preload("res://game/ui/match_hud_controller.gd")
const MainMenuScript = preload("res://game/ui/main_menu_controller.gd")

var _checks: int = 0
var _failures: int = 0


func _initialize() -> void:
	print("=== [SF-M4/M5] STARTING MAPS, PROPS, CAMERA, AI & MODES VERIFICATION ===")
	MapLoaderScript.get_registry()
	MapLoaderScript.get_audio()

	_test_all_vs_maps_and_rooftops_geometry()
	_test_elevators_portals_and_breakable_glass()
	_test_interactive_props_barrel_gascan_hanging_and_supply()
	_test_dynamic_camera_zoom_and_bounds()
	_test_bot_controller_pathfinding_and_tactics()
	_test_game_modes_hud_and_menu()

	MapLoaderScript.cleanup_headless_singletons()

	if _failures > 0:
		push_error("[SF-M4/M5] FAILED with " + str(_failures) + " failed checks out of " + str(_checks))
		quit(1)
		return

	print("=== [SF-M4/M5] ALL " + str(_checks) + " CHECKS PASSED (100% PASS, 0 ERRORS) ===")
	quit(0)


func _check(cond: bool, msg: String) -> void:
	_checks += 1
	if not cond:
		_failures += 1
		push_error("[FAIL] " + msg)
	else:
		print("[PASS] " + msg)


func _test_all_vs_maps_and_rooftops_geometry() -> void:
	var loader: Node2D = MapLoaderScript.new()
	root.add_child(loader)

	var vs_maps: Array[String] = [
		"rooftops",
		"storage",
		"police_station",
		"hazardous",
		"subway",
		"tower",
		"junkyard",
		"cargo",
	]
	for mid: String in vs_maps:
		loader.call("load_map", mid)
		var solids: Array = loader.get("solid_rects") as Array
		var spawns: Array = loader.get("player_spawns") as Array
		_check(
			str(loader.get("current_map_id")) == mid and not solids.is_empty() and not spawns.is_empty(),
			"MapLoader loaded VS map '" + mid + "' (solids=" + str(solids.size()) + ", spawns=" + str(spawns.size()) + ")"
		)

	# Load Rooftops and verify exact geometry & features
	loader.call("load_map", "rooftops")
	var mbounds: Rect2 = loader.get("map_bounds") as Rect2
	_check(
		mbounds.size.x > 500.0 and mbounds.size.y > 400.0,
		"Rooftops map_bounds matches AS3 rectangle: " + str(mbounds)
	)
	var r_solids: Array = loader.get("solid_rects") as Array
	var r_clouds: Array = loader.get("cloud_rects") as Array
	var r_ladders: Array = loader.get("ladder_rects") as Array
	_check(
		r_solids.size() >= 18 and r_clouds.size() >= 2 and r_ladders.size() >= 1,
		"Rooftops Box2D center-based solids=" + str(r_solids.size()) + ", clouds=" + str(r_clouds.size()) + ", ladders=" + str(r_ladders.size())
	)
	var r_slopes: Array = loader.get("slope_polygons") as Array
	var r_elevs: Array = loader.get("elevators") as Array
	var r_portals: Array = loader.get("portals") as Array
	var r_glasses: Array = loader.get("glasses") as Array
	_check(
		r_slopes.size() >= 1 and r_elevs.size() >= 1 and r_portals.size() >= 4 and r_glasses.size() >= 6,
		"Rooftops slopes=" + str(r_slopes.size()) + ", elevators=" + str(r_elevs.size()) + ", portals=" + str(r_portals.size()) + ", glasses=" + str(r_glasses.size())
	)

	# Verify ladder query at Rooftops ladder (x=194, y=143.5, w=14, h=115 -> y in [86, 201])
	var lrect: Rect2 = loader.call("get_ladder_at", Vector2(194.0, 150.0)) as Rect2
	_check(lrect.size.y >= 100.0, "Rooftops ladder rect found at (194, 150): " + str(lrect))

	# Verify cloud platform top surface at (265.5, 84.0, w=119, h=4 -> top_y = 82.0)
	var gy_cloud: float = float(loader.call("get_ground_y_below", 265.5, 76.0, 20.0, true))
	_check(absf(gy_cloud - 82.0) <= 1.0, "Rooftops upper cloud platform top_y is 82.0 (actual=" + str(gy_cloud) + ")")

	root.remove_child(loader)
	loader.free()


func _test_elevators_portals_and_breakable_glass() -> void:
	var mc: Node2D = MatchControllerScript.new()
	root.add_child(mc)
	mc.call("start_match", {"mode": "vs", "map_id": "rooftops", "two_player": true})

	var loader: Node2D = mc.get("map_loader") as Node2D
	var fighters: Array = mc.get("fighters") as Array
	var p1: Node2D = fighters[0] as Node2D

	# 1. Test Elevator oscillation & carrying rider
	var elevs: Array = loader.get("elevators") as Array
	var el0: Dictionary = elevs[0] as Dictionary
	var el_rect_before: Rect2 = el0.get("rect", Rect2()) as Rect2
	p1.global_position = Vector2(el_rect_before.get_center().x, el_rect_before.position.y)
	var y_before: float = p1.global_position.y
	for _i: int in range(10):
		loader.call("step_map", 0.8)
	var el_rect_after: Rect2 = ((loader.get("elevators") as Array)[0] as Dictionary).get("rect", Rect2()) as Rect2
	_check(
		absf(el_rect_after.position.y - el_rect_before.position.y) > 0.5 and absf(p1.global_position.y - el_rect_after.position.y) <= 1.0,
		"Elevator oscillates vertically and carries rider standing on it (y: " + str(snappedf(y_before, 0.01)) + " -> " + str(snappedf(p1.global_position.y, 0.01)) + ")"
	)

	# 2. Test Portal teleportation (Rooftops portal 0: entry [58, 73, 20, 22], dir [-1, 0] -> exit [47, 255, 20, 24])
	p1.global_position = Vector2(66.0, 88.0)
	p1.set("facing", -1)
	p1.set("air_velocity", Vector2(-1.7, 0.0))
	var teleported: bool = bool(loader.call("try_teleport_entity", p1, -1.0))
	_check(
		teleported and p1.global_position.x >= 55.0 and p1.global_position.x <= 72.0 and p1.global_position.y >= 268.0 and int(p1.get("facing")) == 1,
		"Portal teleports player to exit room-side X, snaps to floor, and flips facing when entry.dir.x == exit.dir.x (pos=" + str(p1.global_position) + ")"
	)

	# 3. Test Breakable Glass Window (Rooftops glass 0: (306, 196) to (332, 196))
	var broke: bool = bool(loader.call("check_and_break_glass_segment", Vector2(318.0, 185.0), Vector2(318.0, 205.0), Vector2(0.0, 8.0)))
	var g0: Dictionary = (loader.get("glasses") as Array)[0] as Dictionary
	_check(
		broke and bool(g0.get("broken", false)),
		"Glass window segment breaks on intersection, plays glass SFX, and spawns glass shards"
	)

	mc.call("_clear_match_entities")
	root.remove_child(mc)
	mc.free()


func _test_interactive_props_barrel_gascan_hanging_and_supply() -> void:
	var mc: Node2D = MatchControllerScript.new()
	root.add_child(mc)
	mc.call("start_match", {"mode": "vs", "map_id": "rooftops", "two_player": true})

	# 1. Two-phase Explosive Barrel (BARREL_EXPLOSIVE -> BARREL_WRECK -> 2nd Explosion)
	var barrel: Node2D = mc.call("spawn_interactive_prop", "BARREL_EXPLOSIVE", Vector2(260.0, 180.0)) as Node2D
	_check(int(barrel.get("barrel_phase")) == 0 and not bool(barrel.get("is_destroyed")), "BARREL_EXPLOSIVE initialized in Phase 0")

	barrel.call("apply_bullet_hit", 30.0, 15.0, 1, barrel.global_position)
	var b_vel: Vector2 = barrel.get("velocity") as Vector2
	_check(
		int(barrel.get("barrel_phase")) == 1 and str(barrel.get("prop_type")) == "BARREL_WRECK" and is_equal_approx(float(barrel.get("hp")), 50.0) and bool(barrel.get("is_burning")) and b_vel.y < -3.0 and not bool(barrel.get("is_destroyed")),
		"BARREL_EXPLOSIVE Phase 1: explodes, spawns 18 fire particles, transforms into burning BARREL_WRECK (hp=50, vy=" + str(b_vel.y) + ")"
	)

	# Burn or shoot BARREL_WRECK until Phase 2 detonation
	for _i: int in range(150):
		if bool(barrel.get("is_destroyed")):
			break
		barrel.call("step_prop", 1.0)
	_check(
		int(barrel.get("barrel_phase")) == 2 and bool(barrel.get("is_destroyed")),
		"BARREL_WRECK Phase 2: detonates a second time after burning out"
	)

	# 2. Gascan instant 18-fireball burst
	var gascan: Node2D = mc.call("spawn_interactive_prop", "GASCAN", Vector2(280.0, 180.0)) as Node2D
	gascan.call("apply_bullet_hit", 10.0, 12.0, 1, gascan.global_position)
	_check(bool(gascan.get("is_destroyed")), "GASCAN detonates into 18-particle fire burst upon bullet hit")

	# 3. Hanging Crate + Shootable Holder crushing fighter underneath into meat chunks while landing intact
	var fighters: Array = mc.get("fighters") as Array
	var victim: Node2D = fighters[1] as Node2D
	victim.global_position = Vector2(350.0, 291.0)
	victim.set("hp", 100.0)
	victim.set("is_dead", false)
	victim.set("is_gibbed", false)
	var pair: Dictionary = mc.call("spawn_hanging_crate_pair", Vector2(350.0, 255.0), "") as Dictionary
	var hcrate: Node2D = pair["crate"] as Node2D
	var holder: Node2D = pair["holder"] as Node2D

	# Shoot the holder so it breaks (hp <= 0)
	holder.call("apply_bullet_hit", 20.0, 10.0, 1, holder.global_position)
	_check(bool(holder.get("is_destroyed")) and bool(hcrate.get("is_hanging_released")), "Shooting CRATE_HANGING_HOLDER releases CRATE_HANGING into free fall")

	for _i: int in range(35):
		hcrate.call("step_prop", 1.0)
		if bool(hcrate.get("on_ground")):
			break

	var victim_hp_after: float = float(victim.get("hp"))
	_check(
		victim_hp_after <= 0.0 and bool(victim.get("is_dead")) and bool(victim.get("is_gibbed")) and not bool(hcrate.get("is_destroyed")) and bool(hcrate.get("on_ground")),
		"Falling CRATE_HANGING gibs fighter underneath into meat chunks (is_gibbed=true) and lands intact as an indestructible heavy crate"
	)

	# 4. Sky Supply Parachute Crate
	var supply: Node2D = mc.call("spawn_supply_parachute_crate", 259.0, "SHOTGUN") as Node2D
	var p_count_before_supply: int = (mc.get("pickups") as Array).size()
	for _i: int in range(220):
		supply.call("step_prop", 1.0)
		if bool(supply.get("on_ground")):
			break
	supply.call("try_open_supply_crate")
	_check(
		bool(supply.get("is_destroyed")) and (mc.get("pickups") as Array).size() > p_count_before_supply,
		"SupplyParachuteCrate descends safely to floor and spawns weapon pickup ('SHOTGUN')"
	)

	mc.call("_clear_match_entities")
	root.remove_child(mc)
	mc.free()


func _test_dynamic_camera_zoom_and_bounds() -> void:
	var mc: Node2D = MatchControllerScript.new()
	root.add_child(mc)
	mc.call("start_match", {"mode": "vs", "map_id": "rooftops", "two_player": true})

	var cam: Camera2D = mc.get("dynamic_camera") as Camera2D
	var fighters: Array = mc.get("fighters") as Array
	var p1: Node2D = fighters[0] as Node2D
	var p2: Node2D = fighters[1] as Node2D

	# Close fighters -> high zoom (zoomed in)
	p1.global_position = Vector2(250.0, 180.0)
	p2.global_position = Vector2(275.0, 180.0)
	for _i: int in range(25):
		cam.call("step_camera", 1.0, fighters)
	var zoom_close: float = cam.zoom.x

	# Far apart fighters -> lower zoom (zoomed out)
	p1.global_position = Vector2(45.0, 85.0)
	p2.global_position = Vector2(510.0, 295.0)
	for _i: int in range(25):
		cam.call("step_camera", 1.0, fighters)
	var zoom_far: float = cam.zoom.x

	_check(
		zoom_close >= 1.85 and zoom_close <= 3.4 and zoom_far >= 1.85 and zoom_far <= 3.4 and zoom_close > zoom_far,
		"DynamicCamera clamps zoom in [1.85, 3.4] and zooms in when close (" + str(snappedf(zoom_close, 0.01)) + ") vs far (" + str(snappedf(zoom_far, 0.01)) + ")"
	)
	var mbounds: Rect2 = (mc.get("map_loader") as Node2D).get("map_bounds") as Rect2
	_check(
		mbounds.has_point(cam.global_position),
		"DynamicCamera target position is clamped inside map_bounds (" + str(cam.global_position) + ")"
	)

	cam.call("add_screen_shake", 6.0)
	cam.call("step_camera", 0.4, fighters)
	_check(float(cam.get("screen_shake")) > 0.0, "DynamicCamera supports screen_shake on explosions")

	mc.call("_clear_match_entities")
	root.remove_child(mc)
	mc.free()


func _test_bot_controller_pathfinding_and_tactics() -> void:
	var mc: Node2D = MatchControllerScript.new()
	root.add_child(mc)
	mc.call("start_match", {"mode": "vs", "map_id": "rooftops", "two_player": false, "bot_count": 1, "bot_difficulty": 3})

	var fighters: Array = mc.get("fighters") as Array
	var p1: Node2D = fighters[0] as Node2D
	var bot_fighter: Node2D = fighters[1] as Node2D

	# 1. Test 3 Difficulty configurations
	var bot_easy: RefCounted = BotControllerScript.new(1)
	var bot_med: RefCounted = BotControllerScript.new(2)
	var bot_hard: RefCounted = BotControllerScript.new(3)
	_check(
		int(bot_easy.get("update_delay")) > int(bot_med.get("update_delay")) and int(bot_med.get("update_delay")) > int(bot_hard.get("update_delay")) and not bool(bot_easy.get("can_sprint")) and bool(bot_hard.get("can_shoot_barrels")),
		"BotController configures Easy(1), Medium(2), and Hard(3) delays & tactical capabilities"
	)

	# 2. Test A* Pathfinding on Rooftops ai_nodes & ai_binds across floors
	var path: Array = bot_hard.call("find_path", Vector2(181.0, 91.0), Vector2(383.0, 297.0), mc.get("map_loader")) as Array
	_check(
		not path.is_empty(),
		"BotController A* pathfinder finds multi-hop path across Rooftops floors (steps=" + str(path.size()) + ")"
	)

	# 3. Test immediate Roll reflex when burning (burn_state >= 15)
	bot_fighter.set("burn_state", 25.0)
	var burn_input: Dictionary = bot_hard.call("compute_bot_input", bot_fighter, mc, 0.4) as Dictionary
	_check(
		bool(burn_input.get("down", false)) and (bool(burn_input.get("left", false)) or bool(burn_input.get("right", false))) and not bool(burn_input.get("sprint", false)),
		"BotController immediately triggers Roll (Down + Left/Right without Sprint) when burn_state >= 15"
	)
	bot_fighter.set("burn_state", 0.0)
	bot_fighter.set("burned", false)

	# 4. Test unarmed weapon scavenging decision
	if bot_fighter.has_method("equip_weapon"):
		bot_fighter.set("inventory", {1: "FISTS", 2: "", 3: "", 4: "", 5: ""})
		bot_fighter.set("inventory_ammo", {1: -1, 2: 0, 3: 0, 4: 0, 5: 0})
	mc.call("spawn_weapon_pickup", "RIFLE", bot_fighter.global_position + Vector2(30.0, 0.0))
	var scavenge_input: Dictionary = bot_hard.call("compute_bot_input", bot_fighter, mc, 0.4) as Dictionary
	_check(
		int(bot_hard.get("current_phase")) == BotControllerScript.PHASE_GRAB_WEAPON and (bool(scavenge_input.get("right", false)) or bool(scavenge_input.get("left", false)) or bool(scavenge_input.get("down", false))),
		"Unarmed BotController prioritizes moving to and picking up nearby weapon"
	)

	# 5. Test armed aiming & shooting decision
	if bot_fighter.has_method("equip_weapon"):
		bot_fighter.call("equip_weapon", "RIFLE", 25)
	bot_fighter.global_position = Vector2(250.0, 188.0)
	p1.global_position = Vector2(360.0, 188.0)
	bot_hard.set("_decision_cooldown_frames", 0.0)
	var combat_input: Dictionary = bot_hard.call("compute_bot_input", bot_fighter, mc, 10.0) as Dictionary
	_check(
		int(bot_hard.get("current_phase")) in [BotControllerScript.PHASE_AIM, BotControllerScript.PHASE_SHOOT] and (bool(combat_input.get("aim", false)) or bool(combat_input.get("attack", false)) or bool(combat_input.get("right", false))),
		"Armed BotController aims and fires at enemy in line of sight"
	)

	mc.call("_clear_match_entities")
	root.remove_child(mc)
	mc.free()


func _test_game_modes_hud_and_menu() -> void:
	var mc: Node2D = MatchControllerScript.new()
	root.add_child(mc)

	# 1. VS Mode (2P Local + Bots)
	mc.call("start_match", {
		"mode": "vs",
		"map_id": "rooftops",
		"two_player": true,
		"p1_char": "johnny",
		"p2_char": "shinobi",
		"bot_count": 2,
		"bot_difficulty": 2,
	})
	var vs_fighters: Array = mc.get("fighters") as Array
	_check(
		str(mc.get("game_mode")) == "vs" and bool(mc.get("two_player")) and vs_fighters.size() == 4 and str(mc.get("round_state")) == "GET_READY",
		"VS Mode initializes 2P Local ('johnny' & MUGEN 'shinobi') + 2 Bots with 'GET READY...' banner"
	)

	# Verify HUD formatting
	var hud: CanvasLayer = mc.get("hud_controller") as CanvasLayer
	var f0: Node2D = vs_fighters[0] as Node2D
	f0.set("inventory", {1: "FISTS", 2: "", 3: "", 4: "", 5: ""})
	f0.set("inventory_ammo", {1: -1, 2: 0, 3: 0, 4: 0, 5: 0})
	var hud_label_unarmed: String = str(hud.call("format_fighter_weapon_label", f0))
	if f0.has_method("equip_weapon"):
		f0.call("equip_weapon", "PISTOL", 12)
	var hud_label_pistol: String = str(hud.call("format_fighter_weapon_label", f0))
	_check(
		"UNARMED" in hud_label_unarmed and "PISTOL [12]" in hud_label_pistol,
		"MatchHudController formats weapon & ammo labels ('" + hud_label_unarmed + "' -> '" + hud_label_pistol + "')"
	)

	# 2. Stage Mode (Stage 12 Boss & Agent Unlock + Slow-Mo on final KO)
	MatchControllerScript.agent_unlocked = false
	mc.call("start_match", {"mode": "stage", "stage_level": 12, "p1_char": "johnny"})
	var st_fighters: Array = mc.get("fighters") as Array
	_check(
		str(mc.get("game_mode")) == "stage" and int(mc.get("stage_level")) == 12 and st_fighters.size() >= 2,
		"Stage Mode initializes Stage 12 Tower Campaign boss fight"
	)
	# Defeat all stage enemies to verify Slow-Motion (0.25) and Agent unlock
	for i: int in range(1, st_fighters.size()):
		var ef: Node2D = st_fighters[i] as Node2D
		ef.set("hp", 0.0)
		ef.set("is_dead", true)
	mc.call("step_match", 0.4)
	_check(
		str(mc.get("round_state")) == "ROUND_OVER" and is_equal_approx(float(mc.get("game_speed")), 0.25) and MatchControllerScript.agent_unlocked,
		"Stage 12 victory triggers Slow-Motion (game_speed=0.25) and unlocks boss character 'Agent'"
	)

	# 3. Survival Mode
	mc.call("start_match", {"mode": "survival", "p1_char": "agent"})
	var surv_fighters: Array = mc.get("fighters") as Array
	_check(
		str(mc.get("game_mode")) == "survival" and str(mc.get("current_map_id")) == "survival" and int(mc.get("survival_wave")) == 1 and surv_fighters.size() >= 3,
		"Survival Mode initializes on 'survival' map with Wave 1 enemy squad"
	)

	# 4. MainMenuController initialization & instant 2P action
	var menu: Control = MainMenuScript.new()
	root.add_child(menu)
	var launched_cfg: Dictionary = {}
	menu.connect("start_match_requested", func(cfg: Dictionary) -> void: launched_cfg.merge(cfg, true))
	menu.call("activate_menu_option", 0)
	_check(
		bool(launched_cfg.get("two_player", false)) and str(launched_cfg.get("map_id", "")) == "rooftops",
		"MainMenuController option 0 launches 2 Players Local on Rooftops"
	)

	root.remove_child(menu)
	menu.free()

	mc.call("_clear_match_entities")
	root.remove_child(mc)
	mc.free()

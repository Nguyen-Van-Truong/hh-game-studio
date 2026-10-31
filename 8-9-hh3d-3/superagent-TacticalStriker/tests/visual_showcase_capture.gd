extends SceneTree
## Automated Visual Showcase Capture for Superfighters Y8 1:1 Remake (SF-M7).
## Runs in a real GPU-rendered window (1280x720) and captures 10 authentic PNG screenshots
## into 'res://docs/showcase/' covering menus, 2P Rooftops start, melee, split-rig aiming,
## dive/roll/glass break, 2-phase barrel explosion & fire, elevator/portal/hanging & parachute crates,
## Police Station AI combat, MUGEN Shinobi vs Johnny, and Stage 12 Slow-Mo Victory.

const MapLoaderScript = preload("res://game/world/map_loader.gd")
const MatchControllerScript = preload("res://game/core/match_controller.gd")
const MainMenuScript = preload("res://game/ui/main_menu_controller.gd")
const MugenAdapterScript = preload("res://game/fighter/mugen_fighter_adapter.gd")

const TARGET_SIZE: Vector2i = Vector2i(1280, 720)
const OUTPUT_DIR: String = "res://docs/showcase"

const SHOT_FILES: Array[String] = [
	"01_main_menu.png",
	"02_rooftops_2p_start.png",
	"03_melee_punch_and_katana.png",
	"04_aim_pistol_and_shotgun_both_dirs.png",
	"05_dive_roll_and_glass_break.png",
	"06_barrel_explosion_and_fire.png",
	"07_elevator_portal_and_hanging_crate.png",
	"08_police_station_and_subway_maps.png",
	"09_mugen_shinobi_vs_johnny.png",
	"10_stage_mode_and_victory_slowmo.png",
]

var _menu_layer: CanvasLayer = null
var _main_menu: Control = null
var _match_world: Node2D = null

var _shot_idx: int = 0
var _wait_frames: int = 0
var _captured_count: int = 0


func _initialize() -> void:
	print("=== [SF-M7] STARTING VISUAL SHOWCASE CAPTURE (1280x720 REAL GPU WINDOW) ===")
	var abs_out_dir: String = ProjectSettings.globalize_path(OUTPUT_DIR)
	DirAccess.make_dir_recursive_absolute(abs_out_dir)

	if DisplayServer.get_name() != "headless":
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
		DisplayServer.window_set_size(TARGET_SIZE)
	root.size = TARGET_SIZE
	root.content_scale_size = TARGET_SIZE
	RenderingServer.viewport_set_update_mode(root.get_viewport_rid(), RenderingServer.VIEWPORT_UPDATE_ALWAYS)

	var reg: Node = MapLoaderScript.get_registry()
	MugenAdapterScript.ensure_registry_integration(reg)
	MapLoaderScript.get_audio()

	_match_world = MatchControllerScript.new()
	_match_world.name = "MatchWorld"
	_match_world.process_mode = Node.PROCESS_MODE_DISABLED
	root.add_child(_match_world)

	_menu_layer = CanvasLayer.new()
	_menu_layer.name = "MenuCanvasLayer"
	_menu_layer.layer = 25
	root.add_child(_menu_layer)

	_main_menu = MainMenuScript.new()
	_main_menu.name = "MainMenu"
	_menu_layer.add_child(_main_menu)

	_setup_shot(0)


func _process(_delta: float) -> bool:
	_wait_frames += 1
	if _wait_frames < 5:
		return false

	_capture_current_shot(_shot_idx)
	_shot_idx += 1
	_wait_frames = 0

	if _shot_idx < SHOT_FILES.size():
		_setup_shot(_shot_idx)
		return false

	_cleanup_and_exit()
	return true


func _capture_current_shot(idx: int) -> void:
	var fname: String = SHOT_FILES[idx]
	var out_path: String = OUTPUT_DIR + "/" + fname
	var abs_path: String = ProjectSettings.globalize_path(out_path)

	var vtex: ViewportTexture = root.get_texture()
	var img: Image = vtex.get_image() if vtex != null else null
	if img == null or img.is_empty():
		push_error("[SF-M7] Failed to capture viewport image for " + fname)
		quit(1)
		return

	if img.get_width() != TARGET_SIZE.x or img.get_height() != TARGET_SIZE.y:
		img.resize(TARGET_SIZE.x, TARGET_SIZE.y, Image.INTERPOLATE_NEAREST)

	var err: Error = img.save_png(abs_path)
	if err != OK:
		push_error("[SF-M7] save_png failed for " + abs_path + " (err=" + str(err) + ")")
		quit(1)
		return

	_captured_count += 1
	print("[SF-M7] Captured (" + str(_captured_count) + "/10): " + out_path + " [" + str(img.get_width()) + "x" + str(img.get_height()) + "]")


func _show_menu_only() -> void:
	_menu_layer.visible = true
	_main_menu.visible = true
	_main_menu.custom_minimum_size = Vector2(TARGET_SIZE.x, TARGET_SIZE.y)
	_main_menu.size = Vector2(TARGET_SIZE.x, TARGET_SIZE.y)
	_main_menu.queue_redraw()
	_match_world.visible = false
	if _match_world.hud_controller != null:
		_match_world.hud_controller.visible = false


func _show_match_only() -> void:
	_menu_layer.visible = false
	_main_menu.visible = false
	_match_world.visible = true
	if _match_world.hud_controller != null:
		_match_world.hud_controller.visible = true


func _lock_camera(center_pos: Vector2, zoom_val: float) -> void:
	var cam: Camera2D = _match_world.dynamic_camera
	if cam != null:
		cam.target_position = center_pos
		cam.global_position = center_pos
		cam.target_zoom_scalar = zoom_val
		cam.current_zoom_scalar = zoom_val
		cam.zoom = Vector2(zoom_val, zoom_val)
		cam.offset = Vector2.ZERO
		cam.screen_shake = 0.0
	if _match_world.hud_controller != null:
		_match_world.hud_controller.update_hud()


func _setup_shot(idx: int) -> void:
	match idx:
		0:
			# 01_main_menu.png: Main Menu
			_show_menu_only()
			_main_menu.current_panel = "MAIN"
			_main_menu.selected_index = 0
			_main_menu.queue_redraw()

		1:
			# 02_rooftops_2p_start.png: 2P on rooftops at match start (unarmed, sky, clouds, building, furniture, explosive barrel, elevator, HUD)
			_show_match_only()
			_match_world.start_match({
				"mode": "vs",
				"map_id": "rooftops",
				"two_player": true,
				"p1_char": "johnny",
				"p2_char": "agent",
				"bot_count": 0,
			})
			var p1: Node2D = _match_world.fighters[0]
			var p2: Node2D = _match_world.fighters[1]
			p1.global_position = Vector2(168.0, 95.0)
			p1.set("facing", 1)
			p1.call("_sync_rig_view")

			p2.global_position = Vector2(288.0, 194.0)
			p2.set("facing", -1)
			p2.call("_sync_rig_view")

			# Ensure visible rooftop table, chairs, and explosive barrels near the start framing
			var tbl: Node2D = _match_world.spawn_interactive_prop("TABLE", Vector2(122.0, 89.0))
			tbl.call("step_prop", 1.0)
			var ch1: Node2D = _match_world.spawn_interactive_prop("CHAIR", Vector2(104.0, 88.0))
			ch1.call("step_prop", 1.0)
			var brl: Node2D = _match_world.spawn_interactive_prop("BARREL_EXPLOSIVE", Vector2(256.0, 185.0))
			brl.call("step_prop", 1.0)

			# Advance elevator slightly so it is clearly visible in shaft at x=229
			for _i: int in range(18):
				_match_world.map_loader.step_map(1.0)

			_match_world.round_state = "GET_READY"
			_match_world.banner_text = "GET READY..."
			_match_world.banner_timer = 24.0
			_match_world.overhead_label_timer = 90.0
			_lock_camera(Vector2(236.0, 162.0), 2.35)

		2:
			# 03_melee_punch_and_katana.png: Close-up Johnny punching (PUNCH_02) and Agent swinging Katana (SWORD_02) / Boris swinging Axe (AXE_02)
			_show_match_only()
			_match_world.start_match({
				"mode": "vs",
				"map_id": "rooftops",
				"two_player": true,
				"p1_char": "johnny",
				"p2_char": "agent",
				"bot_count": 1,
			})
			_match_world.round_state = "FIGHT"
			_match_world.banner_text = ""
			_match_world.banner_timer = 0.0

			var f_johnny: Node2D = _match_world.fighters[0]
			var f_agent: Node2D = _match_world.fighters[1]
			var f_boris: Node2D = _match_world.fighters[2]

			f_johnny.global_position = Vector2(252.0, 194.0)
			f_johnny.set("facing", 1)
			f_johnny.set("current_state", "PUNCH_02")
			f_johnny.set("hp", 88.0)
			f_johnny.rig_view.apply_rig_state("johnny", "PUNCH_02", 2, 1, 0.0, 1, 88.0, 100.0)

			f_agent.call("equip_weapon", "SWORD")
			f_agent.global_position = Vector2(271.0, 194.0)
			f_agent.set("facing", -1)
			f_agent.set("current_state", "SWORD_02")
			f_agent.set("hp", 74.0)
			f_agent.rig_view.apply_rig_state("agent", "SWORD_02", 2, -1, 0.0, 1, 74.0, 100.0)

			f_boris.call("equip_weapon", "AXE")
			f_boris.global_position = Vector2(296.0, 194.0)
			f_boris.set("facing", -1)
			f_boris.set("current_state", "AXE_02")
			f_boris.set("hp", 80.0)
			f_boris.rig_view.apply_rig_state("boris", "AXE_02", 2, -1, 0.0, 1, 80.0, 100.0)

			_match_world.fire_hazard_system.spawn_hit_sparks(Vector2(261.0, 183.0), true)
			_match_world.fire_hazard_system.spawn_hit_sparks(Vector2(263.0, 181.0), false)
			_lock_camera(Vector2(272.0, 174.0), 3.35)

		3:
			# 04_aim_pistol_and_shotgun_both_dirs.png: Left fighter aiming AIM_PISTOL (angled up) + Right fighter facing left aiming AIM_SHOTGUN (angled down) with muzzle flash, shells, and tracers
			_show_match_only()
			_match_world.start_match({
				"mode": "vs",
				"map_id": "rooftops",
				"two_player": true,
				"p1_char": "johnny",
				"p2_char": "agent",
				"bot_count": 0,
			})
			_match_world.round_state = "FIGHT"
			_match_world.banner_text = ""
			_match_world.banner_timer = 0.0

			var p_left: Node2D = _match_world.fighters[0]
			var p_right: Node2D = _match_world.fighters[1]

			p_left.global_position = Vector2(96.0, 95.0)
			p_left.call("equip_weapon", "PISTOL", 11)
			p_left.set("facing", 1)
			p_left.set("aiming", true)
			p_left.set("current_state", "AIM_PISTOL")
			p_left.set("current_aim_pitch", -22.0)
			p_left.rig_view.apply_rig_state("johnny", "AIM_PISTOL", 1, 1, -22.0, 2, 92.0, 100.0, 0.0, false, true)

			p_right.global_position = Vector2(228.0, 82.0)
			p_right.call("equip_weapon", "SHOTGUN", 5)
			p_right.set("facing", -1)
			p_right.set("aiming", true)
			p_right.set("current_state", "AIM_SHOTGUN")
			p_right.set("current_aim_pitch", 18.0)
			p_right.rig_view.apply_rig_state("agent", "AIM_SHOTGUN", 1, -1, 18.0, 2, 84.0, 100.0, 0.0, false, true)

			var muz_l: Vector2 = p_left.rig_view.get_muzzle_global_pos()
			var shl_l: Vector2 = p_left.rig_view.get_shell_global_pos()
			var ang_l: float = p_left.rig_view.get_aim_world_angle_deg()

			var muz_r: Vector2 = p_right.rig_view.get_muzzle_global_pos()
			var shl_r: Vector2 = p_right.rig_view.get_shell_global_pos()
			var ang_r: float = p_right.rig_view.get_aim_world_angle_deg()

			var pm: Node2D = _match_world.projectile_manager
			var fhs: Node2D = _match_world.fire_hazard_system
			pm.spawn_bullet(p_left, "PISTOL", muz_l + Vector2(18.0, -7.0), ang_l)
			pm.spawn_bullet(p_left, "PISTOL", muz_l + Vector2(46.0, -18.0), ang_l)
			pm.spawn_bullet(p_right, "SHOTGUN", muz_r + Vector2(-16.0, 5.0), ang_r)

			fhs.spawn_muzzle_flash(muz_l, ang_l)
			fhs.spawn_muzzle_flash(muz_r, ang_r)
			fhs.spawn_shell_casing(shl_l + Vector2(-3.0, -2.0), 1)
			fhs.spawn_shell_casing(shl_l + Vector2(-7.0, 1.0), 1)
			fhs.spawn_shell_casing(shl_r + Vector2(4.0, -2.0), -1)
			fhs.spawn_shell_casing(shl_r + Vector2(8.0, 1.0), -1)

			_lock_camera(Vector2(162.0, 76.0), 3.15)

		4:
			# 05_dive_roll_and_glass_break.png: Fighter diving through glass window shattering into GLASS_SHARDs + other fighter rolling (ROLL)
			_show_match_only()
			_match_world.start_match({
				"mode": "vs",
				"map_id": "rooftops",
				"two_player": true,
				"p1_char": "johnny",
				"p2_char": "boris",
				"bot_count": 0,
			})
			_match_world.round_state = "FIGHT"
			_match_world.banner_text = ""
			_match_world.banner_timer = 0.0

			var diver: Node2D = _match_world.fighters[0]
			var roller: Node2D = _match_world.fighters[1]

			# Break vertical glass window at (245, 247..285) and upper skylight at (306..332, 196)
			_match_world.map_loader.check_and_break_glass_segment(Vector2(235.0, 264.0), Vector2(255.0, 264.0), Vector2(6.5, -1.2))
			_match_world.map_loader.check_and_break_glass_segment(Vector2(318.0, 188.0), Vector2(318.0, 204.0), Vector2(2.0, 5.0))
			_match_world.fire_hazard_system.spawn_glass_shards(Vector2(245.0, 249.0), Vector2(245.0, 282.0), Vector2(5.5, -1.5))
			_match_world.fire_hazard_system.step_hazards(0.8)

			diver.global_position = Vector2(253.0, 264.0)
			diver.set("facing", 1)
			diver.set("diving", true)
			diver.set("on_ground", false)
			diver.set("current_state", "DIVE")
			diver.set("body_rotation_deg", 8.0)
			diver.rig_view.apply_rig_state("johnny", "DIVE", 1, 1, 0.0, 1, 95.0, 100.0, 8.0)

			roller.global_position = Vector2(284.0, 284.0)
			roller.set("facing", -1)
			roller.set("rolling", true)
			roller.set("current_state", "ROLL")
			roller.rig_view.apply_rig_state("boris", "ROLL", 3, -1, 0.0, 1, 88.0, 100.0)

			_lock_camera(Vector2(266.0, 252.0), 3.05)

		5:
			# 06_barrel_explosion_and_fire.png: BARREL_EXPLOSIVE detonating, fire particles burning floor & player, charred BARREL_WRECK flying up
			_show_match_only()
			_match_world.start_match({
				"mode": "vs",
				"map_id": "rooftops",
				"two_player": true,
				"p1_char": "johnny",
				"p2_char": "savage",
				"bot_count": 0,
			})
			_match_world.round_state = "FIGHT"
			_match_world.banner_text = ""
			_match_world.banner_timer = 0.0

			var p_shooter: Node2D = _match_world.fighters[0]
			var p_burning: Node2D = _match_world.fighters[1]

			p_shooter.global_position = Vector2(204.0, 194.0)
			p_shooter.call("equip_weapon", "MAGNUM", 5)
			p_shooter.set("facing", 1)
			p_shooter.set("aiming", true)
			p_shooter.set("current_state", "AIM_MAGNUM")
			p_shooter.rig_view.apply_rig_state("johnny", "AIM_MAGNUM", 1, 1, 0.0, 2, 96.0, 100.0)

			p_burning.global_position = Vector2(292.0, 194.0)
			p_burning.set("facing", -1)
			p_burning.call("add_burn", 95.0, true)
			p_burning.set("hp", 58.0)
			p_burning.set("current_state", "FALL_B")
			p_burning.rig_view.apply_rig_state("savage", "FALL_B", 1, -1, 0.0, 1, 58.0, 100.0, -24.0)

			var b_wreck: Node2D = _match_world.spawn_interactive_prop("BARREL_EXPLOSIVE", Vector2(268.0, 185.0))
			b_wreck.call("apply_bullet_hit", 25.0, 22.0, 1, b_wreck.global_position)
			b_wreck.set("velocity", Vector2(2.6, -5.2))
			b_wreck.call("step_prop", 1.8)
			_match_world.fire_hazard_system.trigger_explosion(Vector2(268.0, 182.0), 38.0, 20.0, 5.0, p_shooter)
			_match_world.fire_hazard_system.trigger_fire_burst("MOLOTOV", Vector2(256.0, 194.0), 14)
			for _st: int in range(6):
				p_burning.global_position.x += 1.2
				_match_world.fire_hazard_system.step_hazards(1.2)

			_lock_camera(Vector2(256.0, 170.0), 2.95)

		6:
			# 07_elevator_portal_and_hanging_crate.png: Moving elevator, severed CRATE_HANGING falling, intact hanging crate, and SupplyParachuteCrate
			_show_match_only()
			_match_world.start_match({
				"mode": "vs",
				"map_id": "rooftops",
				"two_player": true,
				"p1_char": "johnny",
				"p2_char": "agent",
				"bot_count": 0,
			})
			_match_world.round_state = "FIGHT"
			_match_world.banner_text = ""
			_match_world.banner_timer = 0.0

			# Position elevator in mid-shaft and place P1 riding it
			for _i: int in range(22):
				_match_world.map_loader.step_map(1.0)
			var el_rect: Rect2 = (_match_world.map_loader.elevators[0] as Dictionary).get("rect", Rect2(216.0, 240.0, 26.0, 8.0)) as Rect2

			var f_rider: Node2D = _match_world.fighters[0]
			var f_target: Node2D = _match_world.fighters[1]
			f_rider.global_position = Vector2(el_rect.get_center().x, el_rect.position.y)
			f_rider.set("facing", 1)
			f_rider.call("equip_weapon", "PISTOL", 10)
			f_rider.set("aiming", true)
			f_rider.set("current_state", "AIM_PISTOL")
			f_rider.rig_view.apply_rig_state("johnny", "AIM_PISTOL", 1, 1, -15.0, 1, 100.0, 100.0)

			f_target.global_position = Vector2(274.0, 284.0)
			f_target.set("facing", -1)
			f_target.call("_sync_rig_view")

			# 1. Severed CRATE_HANGING falling toward target + sparks at broken holder
			var falling_pair: Dictionary = _match_world.spawn_hanging_crate_pair(Vector2(274.0, 232.0), "BAZOOKA")
			var h_crate_fall: Node2D = falling_pair["crate"] as Node2D
			var h_holder_fall: Node2D = falling_pair["holder"] as Node2D
			h_holder_fall.call("apply_bullet_hit", 20.0, 10.0, 1, h_holder_fall.global_position)
			for _i: int in range(6):
				h_crate_fall.call("step_prop", 1.0)

			# 2. Second intact CRATE_HANGING + holder showing suspension rope
			_match_world.spawn_hanging_crate_pair(Vector2(198.0, 240.0), "M60")

			# 3. Sky SupplyParachuteCrate descending with canopy open
			var para_crate: Node2D = _match_world.spawn_supply_parachute_crate(252.0, "SHOTGUN")
			para_crate.global_position = Vector2(252.0, 206.0)
			para_crate.call("step_prop", 1.0)

			_lock_camera(Vector2(242.0, 234.0), 2.75)

		7:
			# 08_police_station_and_subway_maps.png: Combat with AI Bots on police_station map
			_show_match_only()
			_match_world.start_match({
				"mode": "vs",
				"map_id": "police_station",
				"two_player": false,
				"p1_char": "johnny",
				"bot_count": 3,
				"bot_difficulty": 3,
			})
			_match_world.round_state = "FIGHT"
			_match_world.banner_text = ""
			_match_world.banner_timer = 0.0

			var pf0: Node2D = _match_world.fighters[0]
			var pf1: Node2D = _match_world.fighters[1]
			var pf2: Node2D = _match_world.fighters[2]
			var pf3: Node2D = _match_world.fighters[3]

			pf0.call("equip_weapon", "RIFLE", 25)
			pf1.call("equip_weapon", "SHOTGUN", 6)
			pf2.call("equip_weapon", "UZI", 25)
			pf3.call("equip_weapon", "PISTOL", 12)

			for _i: int in range(18):
				_match_world.step_match(0.8)

			# Ensure active gunfire tracers & cover action in Police Station
			pf0.set("facing", 1)
			pf0.set("aiming", true)
			pf0.set("current_state", "AIM_RIFLE")
			pf0.rig_view.apply_rig_state("johnny", "AIM_RIFLE", 1, 1, 0.0, 2, 86.0, 100.0, 0.0, false, true)
			var pm_ps: Node2D = _match_world.projectile_manager
			var fhs_ps: Node2D = _match_world.fire_hazard_system
			var muz_ps: Vector2 = pf0.rig_view.get_muzzle_global_pos()
			pm_ps.spawn_bullet(pf0, "RIFLE", muz_ps + Vector2(18.0, 0.0), 0.0)
			pm_ps.spawn_bullet(pf0, "RIFLE", muz_ps + Vector2(44.0, -1.0), 0.0)
			fhs_ps.spawn_muzzle_flash(muz_ps, 0.0)
			fhs_ps.spawn_shell_casing(pf0.rig_view.get_shell_global_pos(), 1)

			_match_world.dynamic_camera.step_camera(8.0, _match_world.fighters)
			_match_world.dynamic_camera.offset = Vector2.ZERO
			_match_world.hud_controller.update_hud()

		8:
			# 09_mugen_shinobi_vs_johnny.png: MUGEN Shinobi executing Shunpo Slash + Chakra Wave against Johnny on rooftops
			_show_match_only()
			_match_world.start_match({
				"mode": "vs",
				"map_id": "rooftops",
				"two_player": true,
				"p1_char": "shinobi",
				"p2_char": "johnny",
				"bot_count": 0,
			})
			_match_world.round_state = "FIGHT"
			_match_world.banner_text = ""
			_match_world.banner_timer = 0.0

			var shinobi: Node2D = _match_world.fighters[0]
			var johnny: Node2D = _match_world.fighters[1]

			shinobi.global_position = Vector2(246.0, 194.0)
			shinobi.set("facing", 1)
			shinobi.call("perform_mugen_special", "SHUNPO_SLASH")
			shinobi.rig_view.apply_rig_state("shinobi", "MUGEN_SHUNPO", 2, 1, 0.0, 1, 96.0, 105.0)

			johnny.global_position = Vector2(296.0, 194.0)
			johnny.set("facing", -1)
			johnny.call("equip_weapon", "SWORD")
			johnny.set("hp", 68.0)
			johnny.set("current_state", "SWORD_01")
			johnny.rig_view.apply_rig_state("johnny", "SWORD_01", 2, -1, 0.0, 1, 68.0, 100.0)

			_match_world.projectile_manager.spawn_mugen_projectile(
				shinobi,
				"CHAKRA_WAVE",
				Vector2(268.0, 184.0),
				0.0,
				22.0,
				20.0,
				35.0
			)
			_match_world.projectile_manager.spawn_mugen_projectile(
				shinobi,
				"CHAKRA_WAVE",
				Vector2(282.0, 184.0),
				0.0,
				22.0,
				20.0,
				35.0
			)
			_match_world.fire_hazard_system.spawn_hit_sparks(Vector2(288.0, 183.0), false)
			_lock_camera(Vector2(270.0, 174.0), 3.25)

		9:
			# 10_stage_mode_and_victory_slowmo.png: Stage 12 Final Boss victory slow-motion & banner
			_show_match_only()
			_match_world.start_match({
				"mode": "stage",
				"stage_level": 12,
				"p1_char": "johnny",
			})
			var hero: Node2D = _match_world.fighters[0]
			hero.global_position = Vector2(244.0, 194.0)
			hero.set("facing", 1)
			hero.set("hp", 64.0)
			hero.call("equip_weapon", "RIFLE", 14)
			hero.set("aiming", true)
			hero.set("current_state", "AIM_RIFLE")
			hero.rig_view.apply_rig_state("johnny", "AIM_RIFLE", 1, 1, -8.0, 1, 64.0, 100.0)

			# Defeat all Stage 12 bosses around (282..308, 194)
			for i: int in range(1, _match_world.fighters.size()):
				var boss: Node2D = _match_world.fighters[i]
				boss.global_position = Vector2(272.0 + float(i) * 16.0, 194.0)
				boss.set("facing", -1)
				boss.set("hp", 0.0)
				boss.set("is_dead", true)
				boss.set("current_state", "KNOCKDOWN")
				boss.rig_view.apply_rig_state(str(boss.get("character_id")), "KNOCKDOWN", 1, -1, 0.0, 1, 0.0, 100.0)

			_match_world.fire_hazard_system.spawn_hit_sparks(Vector2(286.0, 186.0), true)
			_match_world.fire_hazard_system.trigger_explosion(Vector2(296.0, 186.0), 26.0, 10.0, 3.0, hero)
			_match_world.step_match(0.4)
			# Position camera slightly higher so fighters at y=194 are clearly visible below the center victory banner
			_lock_camera(Vector2(272.0, 152.0), 2.75)


func _cleanup_and_exit() -> void:
	if _match_world != null and is_instance_valid(_match_world):
		_match_world.call("_clear_match_entities")
		if _match_world.get_parent() != null:
			_match_world.get_parent().remove_child(_match_world)
		_match_world.free()
	_match_world = null

	if _menu_layer != null and is_instance_valid(_menu_layer):
		if _menu_layer.get_parent() != null:
			_menu_layer.get_parent().remove_child(_menu_layer)
		_menu_layer.free()
	_menu_layer = null

	var audio: Node = root.get_node_or_null("AudioManager")
	if audio != null:
		for child: Node in audio.get_children():
			if child is AudioStreamPlayer:
				(child as AudioStreamPlayer).stop()
				(child as AudioStreamPlayer).stream = null
			elif child is AudioStreamPlayer2D:
				(child as AudioStreamPlayer2D).stop()
				(child as AudioStreamPlayer2D).stream = null

	MapLoaderScript.cleanup_headless_singletons()
	print("=== [SF-M7] ALL 10 SHOWCASE SCREENSHOTS CAPTURED SUCCESSFULLY (EXIT 0) ===")
	quit(0)

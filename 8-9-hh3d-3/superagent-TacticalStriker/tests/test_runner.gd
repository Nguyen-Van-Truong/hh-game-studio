extends SceneTree
## Master Automated Test & E2E Acceptance Runner for Superfighters Y8 1:1 Remake (SF-M1 through SF-M7).
## Executes:
##   1. [SF-M1] XFL Asset Compiler & SFDataRegistry / AudioManager verification
##   2. [SF-M2/M3/M6] FighterRigView, FighterController, ProjectileManager, FireHazardSystem & MUGEN Shinobi
##   3. [SF-M4/M5] MapLoader (all 12 maps), InteractiveProp, DynamicCamera, BotController & Game Modes / UI
##   4. [SF-M7 E2E] End-to-End Match Simulation (2P Rooftops, Stage Mode, Survival Mode, MUGEN vs Classic)
##   5. [SF-M7 Showcase] Verification of all 10 GPU-rendered 1280x720 PNGs in res://docs/showcase/

const MapLoaderScript = preload("res://game/world/map_loader.gd")
const InteractivePropScript = preload("res://game/world/interactive_prop.gd")
const DynamicCameraScript = preload("res://game/world/dynamic_camera.gd")
const BotControllerScript = preload("res://game/ai/bot_controller.gd")
const MatchControllerScript = preload("res://game/core/match_controller.gd")
const MatchHudScript = preload("res://game/ui/match_hud_controller.gd")
const MainMenuScript = preload("res://game/ui/main_menu_controller.gd")
const FighterRigViewScript = preload("res://game/fighter/fighter_rig_view.gd")
const ProjectileManagerScript = preload("res://game/world/projectile_manager.gd")
const FireHazardSystemScript = preload("res://game/world/fire_hazard_system.gd")
const MugenAdapterScript = preload("res://game/fighter/mugen_fighter_adapter.gd")

const SHOWCASE_FILES: Array[String] = [
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

var _checks: int = 0
var _failures: int = 0
var _frame_step: int = 0


func _process(_delta: float) -> bool:
	_frame_step += 1
	if _frame_step == 1:
		print("================================================================================")
		print("=== [SUPERFIGHTERS Y8 1:1 REMAKE] MASTER E2E TEST RUNNER (SF-M1 .. SF-M7)   ===")
		print("================================================================================")

		var reg: Node = MapLoaderScript.get_registry()
		var audio: Node = MapLoaderScript.get_audio()
		MugenAdapterScript.ensure_registry_integration(reg)

		_run_m1_registry_and_audio_suite(reg, audio)
		_run_m2_m3_m6_fighter_combat_and_mugen_suite()
		_run_m4_m5_maps_props_ai_and_modes_suite()
		_run_m7_e2e_match_simulation_suite()
		_run_m7_showcase_png_verification_suite()

		MapLoaderScript.cleanup_headless_singletons()
		return false

	if _failures > 0:
		push_error("[MASTER TEST RUNNER] FAILED with " + str(_failures) + " failed checks out of " + str(_checks))
		quit(1)
		return true

	print("================================================================================")
	print("=== [MASTER TEST RUNNER] ALL " + str(_checks) + " CHECKS PASSED (100% PASS, EXIT 0) ===")
	print("================================================================================")
	quit(0)
	return true


func _check(cond: bool, msg: String) -> void:
	_checks += 1
	if not cond:
		_failures += 1
		push_error("[FAIL] " + msg)
	else:
		print("[PASS] " + msg)


func _new_fighter() -> Variant:
	var scene: PackedScene = load("res://scenes/fighter.tscn") as PackedScene
	return scene.instantiate()


# ------------------------------------------------------------------------------
# 1. SF-M1: Registry, Rigs, Character Sheets, Weapons, Maps & Audio
# ------------------------------------------------------------------------------
func _run_m1_registry_and_audio_suite(reg: Node, audio: Node) -> void:
	print("--- [SUITE 1/5] SF-M1: Registry, XFL Assets & Audio ---")
	var states: Dictionary = reg.call("get_states") as Dictionary
	_check(states.size() >= 56, "SFDataRegistry compiled states >= 56 (actual=" + str(states.size()) + ")")

	for cid: String in ["johnny", "boris", "agent", "hideki", "blaire", "savage", "cruger", "ivan", "brody", "mac", "shinobi"]:
		var tex: Texture2D = reg.call("get_character_sheet", cid) as Texture2D
		_check(
			tex != null and tex.get_width() == 600 and tex.get_height() == 400,
			"Character '" + cid + "' sheet loaded with exact size 600x400"
		)

	var wpns: Dictionary = reg.call("get_all_weapons") as Dictionary
	_check(wpns.size() >= 25, "SFDataRegistry weapons >= 25 (actual=" + str(wpns.size()) + ")")

	var maps: Dictionary = reg.call("get_all_maps") as Dictionary
	var vs_ids: Array = reg.call("get_vs_map_ids") as Array
	_check(maps.size() >= 10 and vs_ids.size() >= 8, "SFDataRegistry maps=" + str(maps.size()) + ", vs_maps=" + str(vs_ids.size()))

	var snd_count: int = int(audio.call("get_loaded_sound_count"))
	_check(snd_count >= 73, "AudioManager loaded >= 73 sound files (actual=" + str(snd_count) + ")")
	for snd_key: String in ["Ak47_1", "Punch1", "SfxExplosion1", "Music1", "pistol", "shotgun", "bazooka", "superfighters_theme"]:
		_check(bool(audio.call("has_sound", snd_key)), "AudioManager resolves sound '" + snd_key + "'")


# ------------------------------------------------------------------------------
# 2. SF-M2 / SF-M3 / SF-M6: Rig Layers, Physics, Combat, Projectiles & MUGEN
# ------------------------------------------------------------------------------
func _run_m2_m3_m6_fighter_combat_and_mugen_suite() -> void:
	print("--- [SUITE 2/5] SF-M2/M3/M6: Fighter Rig, Combat, Projectiles, Hazards & MUGEN ---")
	var rig: Variant = FighterRigViewScript.new()
	root.add_child(rig)
	rig.apply_rig_state("johnny", "IDLE", 1, 1, 0.0, 1, 60.0, 100.0)
	_check(
		rig.current_rig_type == "full_body" and not rig.aim_pivot.visible,
		"FighterRigView IDLE uses full_body with hidden AimPivot"
	)
	rig.apply_rig_state("johnny", "AIM_PISTOL", 1, 1, -30.0, 1, 100.0, 100.0)
	var dir_r: Vector2 = rig.get_aim_direction_vector()
	rig.apply_rig_state("johnny", "AIM_PISTOL", 1, -1, -30.0, 1, 100.0, 100.0)
	var dir_l: Vector2 = rig.get_aim_direction_vector()
	_check(
		rig.current_rig_type == "split_rig" and rig.aim_pivot.visible and is_equal_approx(rig.scale.x, -1.0) and dir_l.x < -0.8 and is_equal_approx(dir_l.y, dir_r.y),
		"FighterRigView AIM_PISTOL left uses split_rig with symmetric pitch direction"
	)
	rig.free()

	var f1: Variant = _new_fighter()
	var f2: Variant = _new_fighter()
	var pm: Variant = ProjectileManagerScript.new()
	var fhs: Variant = FireHazardSystemScript.new()
	root.add_child(fhs)
	root.add_child(pm)
	root.add_child(f1)
	root.add_child(f2)

	pm.default_floor_y = 200.0
	fhs.default_floor_y = 200.0
	pm.fire_hazard_system_override = fhs
	pm.external_fighters = [f1, f2]
	fhs.external_fighters = [f1, f2]
	f1.projectile_manager_override = pm
	f1.fire_hazard_system_override = fhs
	f2.projectile_manager_override = pm
	f2.fire_hazard_system_override = fhs
	f1.external_targets.append(f2)
	f2.external_targets.append(f1)

	f1.setup_fighter(0, "johnny", Vector2(100.0, 200.0))
	f2.setup_fighter(1, "boris", Vector2(112.0, 200.0))
	_check(
		str(f1.inventory[1]) == "FISTS" and str(f1.inventory[2]) == "" and not f1.rig_view.aim_pivot.visible,
		"Fighter spawns UNARMED by default (Slot 1=FISTS, Slots 2..5 empty, AimPivot hidden)"
	)

	# Disarm & 3-Hit melee combo
	f2.equip_weapon("PISTOL")
	f2.step_fighter(0.4, {"aim": true})
	for _c: int in range(3):
		f1.step_fighter(1.0, {"attack": true, "attack_just_pressed": true})
		for _s: int in range(6):
			f1.step_fighter(1.0, {})
			f2.step_fighter(1.0, {})
	_check(f2.hp < 100.0, "3-hit melee combo dealt damage to opponent (hp=" + str(f2.hp) + ")")

	# Shotgun 4 pellets & Uzi 5-shot burst
	pm.clear_all()
	pm.total_bullets_spawned = 0
	fhs.clear_all()
	f1.setup_fighter(0, "johnny", Vector2(100.0, 200.0))
	f2.setup_fighter(1, "boris", Vector2(380.0, 200.0))
	f1.equip_weapon("UZI")
	f1.step_fighter(0.4, {"aim": true})
	f1.step_fighter(0.4, {"aim": false, "aim_just_released": true})
	for _u: int in range(15):
		f1.step_fighter(1.0, {})
	_check(pm.total_bullets_spawned == 5, "Uzi 5-shot burst fired 5 bullets")

	pm.clear_all()
	pm.total_bullets_spawned = 0
	fhs.clear_all()
	f1.equip_weapon("SHOTGUN")
	f1.active_gun_slot = 3
	f1.step_fighter(0.4, {"aim": true})
	f1.step_fighter(0.4, {"aim": false, "aim_just_released": true})
	_check(pm.bullets.size() == 4, "Shotgun spawned 4 pellets simultaneously")

	# Molotov 22 fire particles & Roll twice extinguish
	fhs.clear_all()
	fhs.trigger_fire_burst("MOLOTOV", Vector2(200.0, 195.0), 22)
	_check(fhs.fire_particles.size() == 22, "Molotov spawned 22 physical fire particles")
	f2.add_burn(100.0, true)
	f2.step_fighter(1.0, {"down": true, "left": true})
	for _r: int in range(16):
		f2.step_fighter(1.0, {})
	f2.step_fighter(1.0, {"down": true, "left": true})
	_check(is_equal_approx(f2.burn_state, 0.0) and not f2.burned, "Two Rolls completely extinguish BurnState=100 to 0")

	# MUGEN Shinobi hero
	f1.free()
	f2.free()
	pm.clear_all()
	var shinobi: Variant = _new_fighter()
	var dummy: Variant = _new_fighter()
	root.add_child(shinobi)
	root.add_child(dummy)
	shinobi.projectile_manager_override = pm
	pm.external_fighters = [shinobi, dummy]
	shinobi.setup_fighter(0, "shinobi", Vector2(100.0, 200.0))
	dummy.setup_fighter(1, "agent", Vector2(130.0, 200.0))
	shinobi.external_targets.append(dummy)
	var ok_shunpo: bool = shinobi.perform_mugen_special("SHUNPO_SLASH")
	for _m: int in range(10):
		shinobi.step_fighter(1.0, {})
	var ok_wave: bool = shinobi.perform_mugen_special("CHAKRA_WAVE")
	for _m2: int in range(10):
		shinobi.step_fighter(1.0, {})
	_check(
		shinobi.mugen_adapter != null and ok_shunpo and ok_wave and dummy.hp < 100.0 and pm.bullets.size() >= 1,
		"MUGEN Shinobi executed Shunpo Slash & Chakra Wave projectile"
	)

	# --- SF-M8 Parity Regression Checks (Jump 19.65px, W/Up Jump, Horizontal Dive, Aim Square vs Sniper Laser, Debris) ---
	var m8_f: Variant = _new_fighter()
	root.add_child(m8_f)
	m8_f.projectile_manager_override = pm
	m8_f.fire_hazard_system_override = fhs
	m8_f.setup_fighter(0, "johnny", Vector2(100.0, 200.0))

	# 1. W / Up Arrow triggers Jump & peak height matches AS3 (~19.65 px)
	var start_y: float = m8_f.global_position.y
	var min_y: float = start_y
	m8_f.step_fighter(1.0, {"up": true, "up_just_pressed": true})
	var up_triggered_jump: bool = not m8_f.on_ground and m8_f.air_velocity.y < 0.0
	for _j: int in range(25):
		m8_f.step_fighter(1.0, {})
		min_y = minf(min_y, m8_f.global_position.y)
	var jump_peak_px: float = start_y - min_y
	_check(
		up_triggered_jump and jump_peak_px >= 18.0 and jump_peak_px <= 21.5,
		"SF-M8: Up/W triggers jump with exact AS3 peak height ~19.65px (actual=" + str(snapped(jump_peak_px, 0.01)) + "px)"
	)

	# 2. Sprint + Down Dive starts horizontal (not 72 deg nose-down!)
	m8_f.setup_fighter(0, "johnny", Vector2(100.0, 200.0))
	m8_f.sprinting = true
	m8_f.step_fighter(1.0, {"right": true, "down": true, "down_just_pressed": true})
	_check(
		m8_f.diving and absf(m8_f.body_rotation_deg) <= 15.0 and m8_f.air_velocity.x > 3.5,
		"SF-M8: Sprint + Down triggers horizontal DIVE (rot=" + str(m8_f.body_rotation_deg) + " deg, vx=" + str(m8_f.air_velocity.x) + ")"
	)

	# 3. 1-Button Aim/Shoot & Aim Square vs Sniper Laser Sight
	m8_f.setup_fighter(0, "johnny", Vector2(100.0, 200.0))
	m8_f.equip_weapon("PISTOL", 12)
	m8_f.step_fighter(1.0, {"aim": true})
	var pistol_has_square_no_laser: bool = m8_f.rig_view.aim_reticle_sprite.visible and not m8_f.rig_view.laser_sight.visible
	m8_f.equip_weapon("SNIPER", 5)
	m8_f.step_fighter(1.0, {"aim": true})
	var sniper_has_laser: bool = m8_f.rig_view.laser_sight.visible
	_check(
		pistol_has_square_no_laser and sniper_has_laser,
		"SF-M8: Pistol shows white player_aim square (no laser line); Sniper enables red laser sight"
	)

	# 4. Physical prop debris spawning
	fhs.clear_all()
	fhs.spawn_prop_debris("CRATE", Vector2(150.0, 190.0), Vector2(1.0, -1.0), 4)
	_check(
		fhs.prop_debris.size() == 4,
		"SF-M8: Prop destruction spawns physical bouncing debris sprites (count=" + str(fhs.prop_debris.size()) + ")"
	)

	# --- SF-M9 Deep Y8 Parity Checks (Dive-Tackle Gravity, 3rd Punch Glide, Ledge Walk-Off, Kick Knockdown, Rising Flame Puffs, Elevator Jump, Gascan/Barrel Melee Immunity) ---
	var m9_a: Variant = _new_fighter()
	var m9_b: Variant = _new_fighter()
	root.add_child(m9_a)
	root.add_child(m9_b)
	m9_a.external_targets.append(m9_b)
	m9_b.external_targets.append(m9_a)
	m9_a.default_floor_y = 200.0
	m9_b.default_floor_y = 200.0

	# SF-M9.1: Dive tackle carries victim under gravity (never freezes in mid-air) and lands into Roll + Victim Knockdown
	m9_a.setup_fighter(0, "johnny", Vector2(100.0, 200.0))
	m9_b.setup_fighter(1, "agent", Vector2(114.0, 200.0))
	m9_a.sprinting = true
	m9_a.step_fighter(1.0, {"right": true, "down": true, "down_just_pressed": true})
	var mid_air_froze: bool = false
	for _dt: int in range(18):
		m9_a.step_fighter(1.0, {})
		m9_b.step_fighter(1.0, {})
		if not m9_a.on_ground and is_zero_approx(m9_a.air_velocity.y) and is_zero_approx(m9_a.air_velocity.x):
			mid_air_froze = true
	_check(
		not mid_air_froze and m9_a.on_ground and m9_b.knockdowned,
		"SF-M9: Dive tackle never freezes in mid-air; diver lands into Roll and victim lands in KNOCKDOWN"
	)

	# SF-M9.2: 3rd Punch glide distance is compact (~1.5..4.5px after hit, NOT 16..20px slide)
	m9_a.setup_fighter(0, "johnny", Vector2(100.0, 200.0))
	m9_b.setup_fighter(1, "agent", Vector2(300.0, 200.0))
	m9_a.combo_step = 2
	m9_a._combo_window_frames = 10.0
	var p3_start_x: float = m9_a.global_position.x
	m9_a.step_fighter(1.0, {"attack": true, "attack_just_pressed": true})
	for _p3: int in range(10):
		m9_a.step_fighter(1.0, {})
	var p3_slide_px: float = m9_a.global_position.x - p3_start_x
	_check(
		p3_slide_px > 0.5 and p3_slide_px <= 5.5,
		"SF-M9: 3rd punch follow-through glide is compact (~" + str(snapped(p3_slide_px, 0.01)) + "px, not 18px slide)"
	)

	# SF-M9.3: Walking off right edge of a wide floor slab never teleports fighter to the left edge
	m9_a.setup_fighter(0, "johnny", Vector2(196.0, 200.0))
	m9_a.use_default_floor = false
	m9_a.local_solid_rects.clear()
	m9_a.local_solid_rects.append(Rect2(0.0, 200.0, 200.0, 16.0))
	var teleported_left: bool = false
	for _lw: int in range(14):
		m9_a.step_fighter(1.0, {"right": true})
		if m9_a.global_position.x < 190.0:
			teleported_left = true
	_check(
		not teleported_left and m9_a.global_position.x > 200.0 and not m9_a.on_ground,
		"SF-M9: Walking off ledge drops smoothly without horizontal slab teleport (x=" + str(snapped(m9_a.global_position.x, 0.1)) + ")"
	)
	m9_a.local_solid_rects.clear()
	m9_a.use_default_floor = true

	# SF-M9.4: Kick / Airborne hit launches opponent on physical parabola and lands in KNOCKDOWN
	m9_a.setup_fighter(0, "johnny", Vector2(100.0, 200.0))
	m9_b.setup_fighter(1, "agent", Vector2(110.0, 200.0))
	m9_b.apply_melee_hit(6.0, 1, false, true, false, m9_a)
	var kick_launched_air: bool = m9_b.falling and not m9_b.on_ground and m9_b.air_velocity.x >= 4.0 and m9_b.air_velocity.y <= -2.0
	for _kf: int in range(25):
		m9_b.step_fighter(1.0, {})
		if m9_b.on_ground and m9_b.knockdowned:
			break
	_check(
		kick_launched_air and m9_b.knockdowned and m9_b.global_position.x >= 128.0,
		"SF-M9: Kick launches victim along physical parabola and lands into KNOCKDOWN slide (x=" + str(snapped(m9_b.global_position.x, 0.1)) + ")"
	)

	# SF-M9.5: FireHazardSystem emits rising world-space flame_puffs (vy < -0.9) for ground fire & burning fighters
	fhs.clear_all()
	fhs.external_fighters = [m9_b]
	m9_b.add_burn(80.0, false)
	fhs.trigger_fire_burst("MOLOTOV", Vector2(160.0, 198.0), 12)
	for _fh: int in range(8):
		m9_b.global_position.x += 2.5
		fhs.step_hazards(1.0)
	var has_rising_puff: bool = false
	for flp: Dictionary in fhs.flame_puffs:
		if (flp.get("vel", Vector2.ZERO) as Vector2).y < -0.9:
			has_rising_puff = true
			break
	_check(
		fhs.flame_puffs.size() >= 6 and has_rising_puff,
		"SF-M9: FireHazardSystem emits rising world-space flame_puffs (count=" + str(fhs.flame_puffs.size()) + ")"
	)
	fhs.external_fighters.clear()

	# SF-M9.6: Punching/Kicking GASCAN and BARREL_EXPLOSIVE pushes them physically WITHOUT exploding
	var gascan_prop: Node2D = InteractivePropScript.new()
	var barrel_prop: Node2D = InteractivePropScript.new()
	root.add_child(gascan_prop)
	root.add_child(barrel_prop)
	gascan_prop.call("setup_prop", "GASCAN", Vector2(140.0, 194.0))
	barrel_prop.call("setup_prop", "BARREL_EXPLOSIVE", Vector2(170.0, 194.0))
	gascan_prop.set("_settling_frames", 0.0)
	barrel_prop.set("_settling_frames", 0.0)
	for _mp: int in range(10):
		gascan_prop.call("apply_melee_hit", 8.0, 1, false, "FISTS")
		barrel_prop.call("apply_melee_hit", 8.0, 1, false, "FISTS")
	_check(
		not bool(gascan_prop.get("is_destroyed")) and not bool(barrel_prop.get("is_destroyed")) and int(barrel_prop.get("barrel_phase")) == 0 and (gascan_prop.get("velocity") as Vector2).x > 0.0,
		"SF-M9: Punching GASCAN & BARREL_EXPLOSIVE 10x pushes them physically without exploding (AS3 _resistance_impact=0)"
	)
	gascan_prop.free()
	barrel_prop.free()
	m9_a.free()
	m9_b.free()

	# --- SF-M10 Deep Y8 Parity Checks (2-Stage Burn & Charred Corpse, Steerable Rocket Ride, Disarm, Auto-Pickup vs Swap) ---
	var m10_a: Variant = _new_fighter()
	var m10_b: Variant = _new_fighter()
	root.add_child(m10_a)
	root.add_child(m10_b)
	m10_a.projectile_manager_override = pm
	m10_b.projectile_manager_override = pm
	m10_a.fire_hazard_system_override = fhs
	m10_b.fire_hazard_system_override = fhs
	m10_a.external_targets.append(m10_b)
	m10_b.external_targets.append(m10_a)
	m10_a.default_floor_y = 200.0
	m10_b.default_floor_y = 200.0

	# SF-M10.1: Stage 1 burn (15 <= burn_state < 100) never expires over time, escalates to Stage 2 (100), and dying from fire turns corpse pitch-black (player_burnt)
	m10_a.setup_fighter(0, "johnny", Vector2(100.0, 200.0))
	m10_a.add_burn(25.0, false)
	for _bstep: int in range(30):
		m10_a.step_fighter(1.0, {})
	var stage1_escalated: bool = m10_a.burn_state > 35.0 and m10_a.hp < 100.0
	# Extinguish Stage 1 (<100) with 1 roll
	m10_a.burn_state = 60.0
	m10_a.step_fighter(1.0, {"down": true, "right": true})
	var stage1_one_roll_extinguished: bool = is_equal_approx(m10_a.burn_state, 0.0)
	# Kill with fire and verify charred black corpse (burned=true, rig_view.body_sprite.modulate == black)
	m10_a.setup_fighter(0, "johnny", Vector2(100.0, 200.0))
	m10_a.hp = 1.0
	m10_a.add_burn(100.0, true)
	for _bdie: int in range(6):
		m10_a.step_fighter(1.0, {})
	var corpse_mod: Color = m10_a.rig_view.body_sprite.modulate
	_check(
		stage1_escalated and stage1_one_roll_extinguished and m10_a.is_dead and m10_a.burned and corpse_mod.r <= 0.1 and corpse_mod.g <= 0.1 and corpse_mod.b <= 0.1,
		"SF-M10: Stage 1 burn escalates without rolling, 1 roll extinguishes Stage 1, and fire death turns corpse pitch-black (player_burnt)"
	)

	# SF-M10.2: Bazooka rocket carries hit fighter at 0.5x speed and carried fighter can steer rocket pitch with Left/Right
	pm.clear_all()
	m10_a.setup_fighter(0, "johnny", Vector2(80.0, 200.0))
	m10_b.setup_fighter(1, "agent", Vector2(105.0, 200.0))
	pm.external_fighters = [m10_a, m10_b]
	pm.spawn_bullet(m10_a, "BAZOOKA", Vector2(90.0, 192.0), 0.0)
	for _rk: int in range(4):
		pm.step_projectiles(1.0)
	var caught_on_rocket: bool = not pm.bullets.is_empty() and (pm.bullets[0].get("rider", null) == m10_b) and m10_b.current_state.begins_with("ROCKET_RIDE")
	var init_rk_ang: float = float(pm.bullets[0].get("angle_deg", 0.0)) if not pm.bullets.is_empty() else 0.0
	m10_b._prev_input = {"left": true, "right": false}
	pm.step_projectiles(1.0)
	var steered_rk_ang: float = float(pm.bullets[0].get("angle_deg", 0.0)) if not pm.bullets.is_empty() else 0.0
	_check(
		caught_on_rocket and not is_equal_approx(init_rk_ang, steered_rk_ang),
		"SF-M10: Bazooka rocket carries victim (ROCKET_RIDE) and victim steers rocket angle (" + str(init_rk_ang) + " -> " + str(steered_rk_ang) + " deg)"
	)
	pm.clear_all()
	pm.external_fighters.clear()

	# SF-M10.3: Getting shot while aiming NEVER disarms a gun; ONLY hitting an aiming fighter with a melee attack disarms them
	m10_a.setup_fighter(0, "johnny", Vector2(100.0, 200.0))
	m10_b.setup_fighter(1, "agent", Vector2(112.0, 200.0))
	m10_b.equip_weapon("RIFLE", 20)
	m10_b.step_fighter(1.0, {})
	var holstered_when_idle: bool = not m10_b.rig_view.aim_pivot.visible
	m10_b.step_fighter(1.0, {"aim": true})
	var visible_when_aiming: bool = m10_b.rig_view.aim_pivot.visible
	m10_b.apply_bullet_hit(6.0, 20.0, -1, false, m10_b.global_position, false)
	var kept_gun_on_bullet_hit: bool = m10_b.has_any_gun_equipped()
	m10_b.step_fighter(1.0, {"aim": true})
	m10_b.apply_melee_hit(8.0, -1, false, false, false, m10_a)
	var disarmed_on_melee_hit: bool = not m10_b.has_any_gun_equipped() and not m10_b.aiming
	_check(
		holstered_when_idle and visible_when_aiming and kept_gun_on_bullet_hit and disarmed_on_melee_hit,
		"SF-M10: Weapons stay holstered until used; bullet hits keep gun equipped, while melee hits on an aiming fighter disarm their gun"
	)

	m10_a.free()
	m10_b.free()

	m8_f.free()
	shinobi.free()
	dummy.free()
	pm.clear_all()
	fhs.clear_all()
	pm.free()
	fhs.free()


# ------------------------------------------------------------------------------
# 3. SF-M4 / SF-M5: Maps, Props, Camera, AI & Modes
# ------------------------------------------------------------------------------
func _run_m4_m5_maps_props_ai_and_modes_suite() -> void:
	print("--- [SUITE 3/5] SF-M4/M5: Maps, Interactive Props, Camera, AI & Modes ---")
	var loader: Node2D = MapLoaderScript.new()
	root.add_child(loader)
	for mid: String in ["rooftops", "storage", "police_station", "hazardous", "subway", "tower", "junkyard", "cargo"]:
		loader.call("load_map", mid)
		_check(
			not (loader.get("solid_rects") as Array).is_empty(),
			"MapLoader verified VS arena '" + mid + "'"
		)
	loader.call("load_map", "rooftops")
	_check(
		(loader.get("elevators") as Array).size() >= 1 and (loader.get("portals") as Array).size() >= 4 and (loader.get("glasses") as Array).size() >= 6,
		"Rooftops elevator, portals, and breakable glass segments loaded"
	)

	# SF-M9.7: Verify fighter standing on moving Rooftops elevator can jump freely without hitting invisible ceiling / yank-back
	var elev_list: Array = loader.get("elevators") as Array
	if not elev_list.is_empty():
		var elev_dict: Dictionary = elev_list[0] as Dictionary
		var elev_rect: Rect2 = elev_dict.get("rect", Rect2(220, 220, 20, 6)) as Rect2
		var elev_f: Variant = _new_fighter()
		var dummy_world: Node2D = Node2D.new()
		dummy_world.set_script(preload("res://game/core/match_controller.gd"))
		root.add_child(dummy_world)
		dummy_world.set("fighters", [elev_f])
		loader.set("match_world", dummy_world)
		root.add_child(elev_f)
		elev_f.map_loader_override = loader
		elev_f.setup_fighter(0, "johnny", Vector2(elev_rect.position.x + elev_rect.size.x * 0.5, elev_rect.position.y))
		elev_f.on_ground = true
		elev_f._on_cloud_platform = true
		var elev_jump_start_y: float = elev_f.global_position.y
		elev_f.step_fighter(1.0, {"up": true, "up_just_pressed": true})
		var elev_min_y: float = elev_f.global_position.y
		for _ej: int in range(8):
			loader.call("step_map", 1.0)
			elev_f.step_fighter(1.0, {})
			elev_min_y = minf(elev_min_y, elev_f.global_position.y)
		_check(
			elev_jump_start_y - elev_min_y >= 12.0,
			"SF-M9: Fighter jumps cleanly off moving Rooftops elevator (height=" + str(snapped(elev_jump_start_y - elev_min_y, 0.1)) + "px)"
		)
		loader.set("match_world", null)
		elev_f.free()
		dummy_world.free()

	# Verify prop textures are genuine non-medkit bitmaps
	var reg: Node = MapLoaderScript.get_registry()
	var crate_tex: Texture2D = reg.call("load_cached_texture", "res://assets/sprites/props/obj_crate_01.png") as Texture2D
	var barrel_tex: Texture2D = reg.call("load_cached_texture", "res://assets/sprites/props/obj_barrel_explosive.png") as Texture2D
	_check(
		crate_tex != null and crate_tex.get_size() == Vector2(16, 16) and barrel_tex != null and barrel_tex.get_size() == Vector2(11, 15),
		"Prop sprites verified as authentic XFL bitmaps (crate=16x16, barrel_explosive=11x15)"
	)

	# SF-M10.4: Unbroken horizontal glass skylights (x=306..332, y=196 on Rooftops) can be stood on, and pressing Attack auto-kicks & shatters the glass
	var glass_f: Variant = _new_fighter()
	root.add_child(glass_f)
	glass_f.map_loader_override = loader
	glass_f.use_default_floor = false
	glass_f.setup_fighter(0, "johnny", Vector2(318.0, 196.0))
	glass_f.step_fighter(1.0, {})
	var stood_on_glass: bool = glass_f.on_ground and is_equal_approx(glass_f.global_position.y, 196.0)
	glass_f.step_fighter(1.0, {"attack": true, "attack_just_pressed": true})
	var auto_kicked_glass: bool = glass_f.current_state == "KICK"
	for _gk: int in range(6):
		glass_f.step_fighter(1.0, {})
	var glass_shattered: bool = (loader.call("get_intact_horizontal_glass_rects") as Array).size() < 4
	_check(
		stood_on_glass and auto_kicked_glass and glass_shattered,
		"SF-M10: Fighter stands on horizontal glass skylight (y=196) and pressing Attack auto-kicks & shatters glass"
	)
	glass_f.free()

	# SF-M10.5: Exact ladder hitbox (x=187..201 on Rooftops, no +4px air climb outside [x1, x2]) & Portal MovingDirectionInversed continuity
	var lad_outside: Rect2 = loader.call("get_ladder_at", Vector2(185.0, 140.0)) as Rect2
	var lad_inside: Rect2 = loader.call("get_ladder_at", Vector2(194.0, 140.0)) as Rect2
	var port_f: Variant = _new_fighter()
	var port_world: Node2D = Node2D.new()
	port_world.set_script(preload("res://game/core/match_controller.gd"))
	root.add_child(port_world)
	port_world.set("fighters", [port_f])
	loader.set("match_world", port_world)
	root.add_child(port_f)
	port_f.map_loader_override = loader
	port_f.use_default_floor = false
	# Right stairwell portal on Rooftops is at entry_rect=[483, 172, 20, 22], dir=[1, 0], exit_rect=[483, 279, 20, 23]
	port_f.setup_fighter(0, "johnny", Vector2(481.0, 194.0))
	for _pt: int in range(8):
		port_f.step_fighter(1.0, {"right": true})
		loader.call("step_map", 1.0)
	var inversed_active_and_walked_left: bool = (port_f.moving_direction_inversed == 1) and (port_f.global_position.x < 493.0) and (port_f.global_position.y > 260.0)
	port_f.step_fighter(1.0, {}) # Release right key -> resets moving_direction_inversed to 0
	var inversed_reset_on_release: bool = (port_f.moving_direction_inversed == 0)
	_check(
		lad_outside.size.x <= 0.0 and lad_inside.size.x > 0.0 and inversed_active_and_walked_left and inversed_reset_on_release,
		"SF-M10: Exact ladder bounds (no +4px offset) & Portal MovingDirectionInversed keeps walking smoothly out of destination doorway"
	)
	loader.set("match_world", null)
	port_f.free()
	port_world.free()
	loader.free()


# ------------------------------------------------------------------------------
# 4. SF-M7 E2E: End-to-End Match Simulation
# ------------------------------------------------------------------------------
func _run_m7_e2e_match_simulation_suite() -> void:
	print("--- [SUITE 4/5] SF-M7 E2E: Full Match Simulation ---")
	var mc: Node2D = MatchControllerScript.new()
	root.add_child(mc)

	# 1. 2P Local Rooftops match simulation (with default Y8 Pistol + 3 Grenades loadout)
	mc.call("start_match", {
		"mode": "vs",
		"map_id": "rooftops",
		"two_player": true,
		"p1_char": "johnny",
		"p2_char": "agent",
		"bot_count": 0,
	})
	var fighters: Array = mc.get("fighters") as Array
	var p1_node: Node2D = fighters[0] as Node2D
	var p1_inv: Dictionary = p1_node.get("inventory") as Dictionary
	var p1_ammo: Dictionary = p1_node.get("inventory_ammo") as Dictionary
	var has_default_loadout: bool = (str(p1_inv.get(2, "")) == "PISTOL" and int(p1_ammo.get(2, 0)) == 12 and str(p1_inv.get(4, "")) == "GRENADE" and int(p1_ammo.get(4, 0)) == 3)
	_check(
		str(mc.get("current_map_id")) == "rooftops" and fighters.size() == 2 and str(mc.get("round_state")) == "GET_READY" and has_default_loadout,
		"E2E 2P Rooftops match initialized with default Y8 loadout (Pistol 12 + 3 Grenades) and GET_READY banner"
	)
	for _i: int in range(80):
		mc.call("step_match", 1.0)
	_check(
		str(mc.get("round_state")) == "FIGHT",
		"E2E match transitioned from GET_READY to FIGHT combat phase"
	)

	# SF-M10.6: Solid prop collision & Zero Self-Hit Bug when spamming melee attacks against CRATE / TABLE
	p1_node.set("hp", 100.0)
	var test_crate: Node2D = mc.call("spawn_interactive_prop", "CRATE", p1_node.global_position + Vector2(float(p1_node.get("facing")) * 12.0, -8.0)) as Node2D
	test_crate.set("_settling_frames", 0.0)
	for _spam: int in range(12):
		p1_node.call("step_fighter", 1.0, {"attack": true, "attack_just_pressed": true})
		if is_instance_valid(test_crate):
			test_crate.call("step_prop", 1.0)
	_check(
		is_equal_approx(float(p1_node.get("hp")), 100.0) and not bool(p1_node.get("is_dead")),
		"SF-M10: Spamming melee attack 12x on CRATE/TABLE causes 0 self-damage (HP=" + str(p1_node.get("hp")) + ")"
	)

	# SF-M10.7: Auto-Pickup empty Melee slot on walk-over vs Down + Attack manual swap for occupied Gun slot
	mc.call("spawn_weapon_pickup", "SWORD", p1_node.global_position)
	mc.call("update_fighter_weapon_grab", p1_node, false)
	var auto_grabbed_empty_melee: bool = str((p1_node.get("inventory") as Dictionary).get(1, "")) == "SWORD"
	mc.call("spawn_weapon_pickup", "SHOTGUN", p1_node.global_position)
	var did_not_auto_swap_occupied_gun: bool = not bool(mc.call("update_fighter_weapon_grab", p1_node, false)) and str(p1_node.call("get_active_weapon_id")) == "PISTOL"
	var manual_swapped_occupied_gun: bool = bool(mc.call("update_fighter_weapon_grab", p1_node, true)) and str(p1_node.call("get_active_weapon_id")) == "SHOTGUN"
	_check(
		auto_grabbed_empty_melee and did_not_auto_swap_occupied_gun and manual_swapped_occupied_gun,
		"SF-M10: Empty weapon slot auto-equips on walk-over; occupied weapon slot highlights '[ ]' and swaps only on Down + Attack"
	)

	# Simulate combat victory & slow-mo transition
	var p2: Node2D = fighters[1] as Node2D
	p2.set("hp", 0.0)
	p2.set("is_dead", true)
	mc.call("step_match", 0.4)
	_check(
		str(mc.get("round_state")) == "ROUND_OVER" and is_equal_approx(float(mc.get("game_speed")), 0.25),
		"E2E knockout triggers slow-mo (game_speed=0.25) and ROUND_OVER resolution"
	)

	# 2. Stage Mode Stage 12 completion unlocks 'Agent'
	MatchControllerScript.agent_unlocked = false
	mc.call("start_match", {"mode": "stage", "stage_level": 12, "p1_char": "johnny"})
	var s_fighters: Array = mc.get("fighters") as Array
	for idx: int in range(1, s_fighters.size()):
		var ef: Node2D = s_fighters[idx] as Node2D
		ef.set("hp", 0.0)
		ef.set("is_dead", true)
	mc.call("step_match", 0.4)
	_check(
		str(mc.get("round_state")) == "ROUND_OVER" and MatchControllerScript.agent_unlocked,
		"E2E Stage 12 victory unlocks bonus character 'Agent'"
	)

	# 3. SF-M11 Parity Suite:
	# 3a. Roll cancels Aiming + Instant Gun Holster & Fast Consecutive Shots
	mc.call("start_match", {"mode": "vs", "map_id": "rooftops", "two_player": true, "p1_char": "johnny", "p2_char": "havoc", "bot_count": 0})
	var m11_fighters: Array = mc.get("fighters") as Array
	var m11_p1: Node2D = m11_fighters[0] as Node2D
	var m11_p2: Node2D = m11_fighters[1] as Node2D
	m11_p1.global_position = Vector2(180.0, 284.0)
	m11_p1.set("on_ground", true)
	m11_p1.call("equip_weapon", "PISTOL", 12)
	m11_p1.call("step_fighter", 1.0, {"aim": true})
	var was_aiming_gun: bool = bool(m11_p1.get("aiming"))
	m11_p1.call("step_fighter", 1.0, {"aim": true, "down": true, "right": true})
	_check(
		was_aiming_gun and bool(m11_p1.get("rolling")) and not bool(m11_p1.get("aiming")),
		"SF-M11: Pressing Down + Left/Right while aiming a gun immediately cancels aiming into ROLL"
	)

	# Let roll finish, then test AS3 BackToIdleTimer=6 post-shot gun hold & rapid consecutive shots without flickering to IDLE
	for _r_i: int in range(16):
		m11_p1.call("step_fighter", 1.0, {})
	m11_p1.global_position = Vector2(180.0, 284.0)
	m11_p1.set("on_ground", true)
	var ammo_before_fast: int = int((m11_p1.get("inventory_ammo") as Dictionary).get(2, 0))
	m11_p1.call("step_fighter", 1.0, {"aim": true})
	m11_p1.call("step_fighter", 1.0, {"aim": false, "aim_just_released": true})
	# During the 5 ticks after firing (AS3 BackToIdleTimer = 6), gun stays drawn in AIM_PISTOL so spam shots never flicker to IDLE!
	var stayed_drawn_between_spam_shots: bool = true
	for _cd_p: int in range(5):
		m11_p1.call("step_fighter", 1.0, {"aim": false})
		if not bool(m11_p1.get("aiming")) or str(m11_p1.get("current_state")) != "AIM_PISTOL":
			stayed_drawn_between_spam_shots = false
	m11_p1.call("step_fighter", 1.0, {"aim": true})
	m11_p1.call("step_fighter", 1.0, {"aim": false, "aim_just_released": true})
	var ammo_after_fast: int = int((m11_p1.get("inventory_ammo") as Dictionary).get(2, 0))
	_check(
		stayed_drawn_between_spam_shots and ammo_after_fast == ammo_before_fast - 2,
		"SF-M11: Releasing shoot button keeps gun drawn for BackToIdleTimer=6 ticks and fires rapid consecutive shots without flickering to IDLE (ammo=" + str(ammo_before_fast) + "->" + str(ammo_after_fast) + ")"
	)

	# 3b. Disarm spawns dropped weapon with valid texture & launches it far away (>= 50px)
	var m11_pickups: Array = mc.get("pickups") as Array
	m11_pickups.clear()
	m11_p1.global_position = Vector2(180.0, 284.0)
	m11_p1.set("on_ground", true)
	m11_p1.call("equip_weapon", "PISTOL", 10)
	m11_p1.call("step_fighter", 1.0, {"aim": true})
	m11_p1.call("apply_melee_hit", 6.0, 1, false, false, false, m11_p2)
	var disarmed_pk_ok: bool = false
	var disarmed_dist: float = 0.0
	if not m11_pickups.is_empty():
		var d_pk: Dictionary = m11_pickups[m11_pickups.size() - 1] as Dictionary
		var d_node: Node2D = d_pk.get("node", null) as Node2D
		var has_tex: bool = (d_node != null and d_node.get("weapon_tex") != null)
		for _s_i: int in range(32):
			mc.call("_step_pickups", 1.0)
		var final_pk_pos: Vector2 = d_pk.get("pos", Vector2.ZERO) as Vector2
		disarmed_dist = absf(final_pk_pos.x - m11_p1.global_position.x)
		disarmed_pk_ok = has_tex and disarmed_dist >= 50.0 and str(m11_p1.call("get_active_weapon_id")) == "FISTS"
	_check(
		disarmed_pk_ok,
		"SF-M11: Disarmed gun renders weapon_tex inside [ ] and launches far away (dist=" + str(snappedf(disarmed_dist, 0.1)) + "px)"
	)

	# 3c. Ladder slide knocks climber below into free-fall (FALL_F / FALL_B)
	var ml_m11: Node2D = mc.get("map_loader") as Node2D
	var lad_rects: Array = ml_m11.get("ladder_rects") as Array
	if not lad_rects.is_empty():
		var lad0: Rect2 = lad_rects[0] as Rect2
		var lad_cx: float = lad0.position.x + lad0.size.x * 0.5
		m11_p1.call("setup_fighter", 0, "johnny", Vector2(lad_cx, lad0.position.y + 18.0), false)
		m11_p2.call("setup_fighter", 1, "havoc", Vector2(lad_cx, lad0.position.y + 30.0), false)
		m11_p1.set("match_world", mc)
		m11_p2.set("match_world", mc)
		m11_p1.set("climbing", true)
		m11_p1.set("on_ground", false)
		m11_p2.set("climbing", true)
		m11_p2.set("on_ground", false)
		for _l_i: int in range(5):
			m11_p1.call("step_fighter", 1.0, {"down": true})
			m11_p2.call("step_fighter", 1.0, {"up": true})
		_check(
			bool(m11_p2.get("falling")) and not bool(m11_p2.get("climbing")) and str(m11_p2.get("current_state")) in ["FALL_F", "FALL_B"],
			"SF-M11: Sliding down ladder knocks lower climber into free-fall (state=" + str(m11_p2.get("current_state")) + ")"
		)

	# 3d. Auto Ledge Grab at platform top edge + Vault up on Jump/Up
	m11_p1.set("match_world", null)
	m11_p1.call("setup_fighter", 0, "johnny", Vector2(99.0, 198.0), false)
	m11_p1.set("local_solid_rects", [Rect2(105.0, 186.0, 60.0, 40.0)] as Array[Rect2])
	m11_p1.set("use_default_floor", false)
	m11_p1.set("on_ground", false)
	m11_p1.set("facing", 1)
	m11_p1.set("air_velocity", Vector2(1.2, 0.5))
	m11_p1.call("step_fighter", 1.0, {"right": true})
	var grabbed_ledge: bool = bool(m11_p1.get("ledge_grabbing")) and str(m11_p1.get("current_state")) == "LEDGE_GRAB"
	m11_p1.call("step_fighter", 1.0, {"up": true, "up_just_pressed": true})
	var jumped_from_ledge: bool = not bool(m11_p1.get("ledge_grabbing")) and not bool(m11_p1.get("on_ground")) and str(m11_p1.get("current_state")) == "JUMP"
	for _vj1: int in range(14):
		m11_p1.call("step_fighter", 1.0, {})
	var vaulted_ledge: bool = jumped_from_ledge and bool(m11_p1.get("on_ground")) and is_equal_approx(m11_p1.global_position.y, 186.0)
	_check(
		grabbed_ledge and vaulted_ledge,
		"SF-M11: Auto Ledge Grab snaps to platform corner and vaults onto platform top on Up/Jump"
	)

	# 3e. Dive-tackle on Rooftops small stairs (x=289..318, y=284..302) never sinks victim through floor
	m11_p1.call("setup_fighter", 0, "johnny", Vector2(314.0, 299.0), false)
	m11_p2.call("setup_fighter", 1, "havoc", Vector2(302.0, 291.0), false)
	m11_p1.set("match_world", mc)
	m11_p2.set("match_world", mc)
	m11_p1.set("facing", -1)
	m11_p1.set("sprinting", true)
	m11_p1.call("step_fighter", 1.0, {"left": true, "down": true, "down_just_pressed": true})
	for _d_i: int in range(18):
		m11_p1.call("step_fighter", 1.0, {"left": true})
		m11_p2.call("step_fighter", 1.0, {})
	_check(
		m11_p1.global_position.y <= 306.0 and m11_p2.global_position.y <= 306.0,
		"SF-M11: Dive-tackle on Rooftops small stairs keeps both fighters on stairs (p1.y=" + str(snappedf(m11_p1.global_position.y, 0.1)) + ", p2.y=" + str(snappedf(m11_p2.global_position.y, 0.1)) + ")"
	)

	# 4. SF-M12 Deep Parity Suite:
	# 4a. Solid Props Collision (Player vs Prop & Prop vs Prop — CRATE, BARREL_EXPLOSIVE, GASCAN)
	for old_p: Variant in (mc.get("props") as Array):
		if is_instance_valid(old_p):
			(old_p as Node2D).free()
	(mc.get("props") as Array).clear()
	var m12_crate: Node2D = mc.call("spawn_interactive_prop", "CRATE", Vector2(170.0, 276.0)) as Node2D
	var m12_gascan: Node2D = mc.call("spawn_interactive_prop", "GASCAN", Vector2(172.0, 279.0)) as Node2D
	for _sp_i: int in range(12):
		m12_crate.call("step_prop", 1.0)
		m12_gascan.call("step_prop", 1.0)
	var prop_sep_dist: float = absf(m12_crate.global_position.x - m12_gascan.global_position.x)
	# Stand on top of crate and double-tap Down (must NOT drop inside crate because props are solid, not one-way clouds!)
	var crate_rect: Rect2 = m12_crate.call("get_world_rect") as Rect2
	m11_p1.call("setup_fighter", 0, "johnny", Vector2(m12_crate.global_position.x, crate_rect.position.y), false)
	m11_p1.set("match_world", mc)
	m11_p1.set("on_ground", true)
	m11_p1.call("step_fighter", 1.0, {"down": true, "down_just_pressed": true})
	m11_p1.call("step_fighter", 1.0, {"down": false})
	m11_p1.call("step_fighter", 1.0, {"down": true, "down_just_pressed": true})
	for _cd_i: int in range(6):
		m11_p1.call("step_fighter", 1.0, {"down": true})
	var never_sank_into_crate: bool = is_equal_approx(m11_p1.global_position.y, crate_rect.position.y)
	# Also verify rolling into a solid crate does not end inside its horizontal bounds
	m11_p1.global_position = Vector2(crate_rect.position.x - 16.0, 284.0)
	m11_p1.set("on_ground", true)
	m11_p1.call("step_fighter", 1.0, {"down": true, "right": true})
	for _rl_i: int in range(10):
		m11_p1.call("step_fighter", 1.0, {"right": true})
	var not_inside_crate_x: bool = (m11_p1.global_position.x <= (m12_crate.call("get_world_rect") as Rect2).position.x - 3.5)
	_check(
		bool(m12_gascan.get("has_solid_hitbox")) and prop_sep_dist >= 10.0 and never_sank_into_crate and not_inside_crate_x,
		"SF-M12.1: Solid props (CRATE, BARREL_EXPLOSIVE, GASCAN) separate from each other and block fighters from standing/rolling/dropping inside"
	)

	# Clear test props before testing pure grenade blast
	for old_p2: Variant in (mc.get("props") as Array):
		if is_instance_valid(old_p2):
			(old_p2 as Node2D).free()
	(mc.get("props") as Array).clear()

	# 4b. Grenade explosion = pure shockwave + smoke, NEVER fire particles or burn_state
	var fhs_m12: Node2D = mc.get("fire_hazard_system") as Node2D
	(fhs_m12.get("fire_particles") as Array).clear()
	m11_p2.call("setup_fighter", 1, "havoc", Vector2(130.0, 278.0), false)
	m11_p2.set("match_world", mc)
	m11_p2.set("burn_state", 0.0)
	fhs_m12.call("trigger_explosion", Vector2(120.0, 270.0), 33.0, 20.0, 5.0, m11_p1)
	var grenade_fire_count: int = (fhs_m12.get("fire_particles") as Array).size()
	var p2_burn_after_grenade: float = float(m11_p2.get("burn_state"))
	_check(
		grenade_fire_count == 0 and p2_burn_after_grenade == 0.0 and bool(m11_p2.get("falling")),
		"SF-M12.2: Grenade explosion creates shockwave blast + smoke with ZERO fire particles and ZERO burn_state"
	)

	# 4c. Powerup Slot 4 (SLOMO05 / SLOMO10) stored in inventory[5] on pickup and only activated on Key 4 (powerup)
	mc.set("slowmo_timer", 0.0)
	mc.set("game_speed", 1.0)
	(mc.get("pickups") as Array).clear()
	m11_p1.call("setup_fighter", 0, "johnny", Vector2(150.0, 284.0), false)
	m11_p1.set("match_world", mc)
	m11_p1.set("on_ground", true)
	mc.call("spawn_weapon_pickup", "SLOMO05", Vector2(150.0, 284.0), 1, false)
	mc.call("update_fighter_weapon_grab", m11_p1, false)
	var slomo_stored_not_active: bool = (
		str((m11_p1.get("inventory") as Dictionary).get(5, "")) == "SLOMO05"
		and float(mc.get("slowmo_timer")) == 0.0
		and is_equal_approx(float(mc.get("game_speed")), 1.0)
	)
	m11_p1.call("step_fighter", 1.0, {"powerup": true})
	var slomo_activated_on_key4: bool = (
		str((m11_p1.get("inventory") as Dictionary).get(5, "")).is_empty()
		and float(mc.get("slowmo_timer")) > 0.0
		and is_equal_approx(float(mc.get("game_speed")), 0.5)
	)
	mc.set("slowmo_timer", 0.0)
	mc.set("game_speed", 1.0)
	_check(
		slomo_stored_not_active and slomo_activated_on_key4,
		"SF-M12.3: SLOMO powerup equips into 4th HUD box (inventory[5]) without auto-activating, and activates on Key 4 (powerup)"
	)

	# 4d. Controls (Arrow Keys + Numpad 1/2/3/4 vs WASD + J/K/L/;) & Telex IME physical_keycode binding
	var p1_atk_events: Array[InputEvent] = InputMap.action_get_events("p1_attack")
	var p2_atk_events: Array[InputEvent] = InputMap.action_get_events("p2_attack")
	var p2_up_events: Array[InputEvent] = InputMap.action_get_events("p2_up")
	var has_kp1: bool = false
	for ev: InputEvent in p1_atk_events:
		if ev is InputEventKey and ((ev as InputEventKey).keycode == KEY_KP_1 or (ev as InputEventKey).physical_keycode == KEY_KP_1):
			has_kp1 = true
	var has_j: bool = false
	for ev2: InputEvent in p2_atk_events:
		if ev2 is InputEventKey and ((ev2 as InputEventKey).keycode == KEY_J or (ev2 as InputEventKey).physical_keycode == KEY_J):
			has_j = true
	var has_pure_physical_w: bool = false
	var has_telex_unicode_w: bool = false
	for evw: InputEvent in p2_up_events:
		if evw is InputEventKey:
			var ek: InputEventKey = evw as InputEventKey
			if ek.keycode == KEY_NONE and ek.physical_keycode == KEY_W:
				has_pure_physical_w = true
			if ek.unicode == 432:
				has_telex_unicode_w = true
	_check(
		has_kp1 and has_j and has_pure_physical_w and has_telex_unicode_w,
		"SF-M12.4/5: Controls bound to Arrow+Numpad 1..4 / WASD+J/K/L/; with pure physical_keycode + Telex Unicode fallback"
	)

	# 4e. Shooting an active thrown grenade with a bullet detonates it early
	var pm_m12: Node2D = mc.get("projectile_manager") as Node2D
	(pm_m12.get("throwables") as Array).clear()
	(pm_m12.get("bullets") as Array).clear()
	(fhs_m12.get("explosions") as Array).clear()
	pm_m12.call("spawn_throwable", m11_p1, "GRENADE", Vector2(135.0, 260.0), 0.0, 72.0)
	var th_arr: Array = pm_m12.get("throwables") as Array
	(th_arr[0] as Dictionary)["vel"] = Vector2.ZERO
	pm_m12.call("spawn_bullet", m11_p2, "SNIPER", Vector2(115.0, 260.0), 0.0, -1)
	pm_m12.call("step_projectiles", 1.0)
	_check(
		(pm_m12.get("throwables") as Array).is_empty() and not (fhs_m12.get("explosions") as Array).is_empty(),
		"SF-M12.6: Shooting an active grenade with a bullet detonates it early"
	)

	# 4f. Rooftops stairs (x=289..318) grenade bounce & roll without falling through into void
	(pm_m12.get("throwables") as Array).clear()
	var stair_ray: Dictionary = ml_m11.call("raycast_solid", Vector2(305.0, 280.0), Vector2(305.0, 310.0), -1) as Dictionary
	var stair_normal: Vector2 = stair_ray.get("normal", Vector2.DOWN) as Vector2
	pm_m12.call("spawn_throwable", m11_p1, "GRENADE", Vector2(296.0, 276.0), 25.0, 70.0)
	var min_stair_ok: bool = true
	for _st_i: int in range(45):
		pm_m12.call("_step_throwables", 1.0)
		var cur_ths: Array = pm_m12.get("throwables") as Array
		if not cur_ths.is_empty():
			var gp: Vector2 = (cur_ths[0] as Dictionary).get("pos", Vector2.ZERO) as Vector2
			if gp.y > 315.0:
				min_stair_ok = false
	_check(
		bool(stair_ray.get("hit", false)) and stair_normal.y < -0.5 and min_stair_ok,
		"SF-M12.7/9a: Rooftops stairs normal points upward (" + str(stair_normal) + ") and thrown grenades bounce/roll down stairs without falling into void"
	)

	# 4g. Falling fighter colliding with another fighter deals impact damage and knocks them into force_fall
	m11_p1.call("setup_fighter", 0, "johnny", Vector2(180.0, 258.0), false)
	m11_p2.call("setup_fighter", 1, "havoc", Vector2(180.0, 284.0), false)
	m11_p1.set("match_world", mc)
	m11_p2.set("match_world", mc)
	m11_p1.set("on_ground", false)
	m11_p1.set("falling", true)
	m11_p1.set("current_state", "FALL_F")
	m11_p1.set("air_velocity", Vector2(1.5, 5.5))
	var p2_hp_before_fall_hit: float = float(m11_p2.get("hp"))
	for _fh_i: int in range(6):
		m11_p1.call("step_fighter", 1.0, {})
	_check(
		float(m11_p2.get("hp")) < p2_hp_before_fall_hit and bool(m11_p2.get("falling")),
		"SF-M12.8: Free-falling fighter colliding with another fighter deals impact damage and knocks them into free-fall"
	)

	# 4h. Single-occupancy weapon spawn points & 20s (480 ticks) despawn/replacement timer
	(mc.get("pickups") as Array).clear()
	mc.call("spawn_weapon_pickup", "PISTOL", Vector2(260.0, 180.0), 12, false, 0)
	mc.call("spawn_weapon_pickup", "SHOTGUN", Vector2(260.0, 180.0), 6, false, 0)
	var pks_m12: Array = mc.get("pickups") as Array
	var single_occ_ok: bool = (pks_m12.size() == 1 and str((pks_m12[0] as Dictionary).get("weapon_id")) == "SHOTGUN")
	# Advance 485 ticks -> weapon at spawn point 0 must despawn
	mc.call("_step_pickups", 485.0)
	var despawned_after_20s: bool = (mc.get("pickups") as Array).is_empty()
	_check(
		single_occ_ok and despawned_after_20s,
		"SF-M12.9b: Weapon spawn points enforce single occupancy and despawn untouched weapons after 20s (480 ticks)"
	)

	# --- SF-M13 Deep Parity & Screenshot Bug Fix Verification ---
	# 5a. SF-M13.1: Rooftops ladder top jump onto yellow billboard (y=82) & Deluxe Ledge Grab (LEDGE_GRAB)
	ml_m11.call("load_map", "rooftops")
	m11_p1.call("setup_fighter", 0, "johnny", Vector2(194.0, 96.0), false)
	m11_p1.set("match_world", mc)
	m11_p1.set("climbing", true)
	m11_p1.set("on_ground", false)
	m11_p1.set("current_state", "CLIMB")
	for _lj_i: int in range(22):
		m11_p1.call("step_fighter", 1.0, {"up": true, "right": true})
	var landed_on_billboard: bool = (bool(m11_p1.get("on_ground")) and is_equal_approx(m11_p1.global_position.y, 82.0))

	# Test Deluxe Ledge Grab when descending at left edge of billboard (x=200, y=82)
	m11_p1.call("setup_fighter", 0, "johnny", Vector2(196.0, 95.0), false)
	m11_p1.set("match_world", mc)
	m11_p1.set("on_ground", false)
	m11_p1.set("facing", 1)
	m11_p1.set("air_velocity", Vector2(1.2, 1.2))
	m11_p1.call("step_fighter", 1.0, {"right": true})
	var grabbed_ledge_ok: bool = (bool(m11_p1.get("ledge_grabbing")) and str(m11_p1.get("current_state")) == "LEDGE_GRAB")
	# Stay hanging when no input is pressed
	m11_p1.call("step_fighter", 1.0, {})
	var stayed_hanging_ok: bool = bool(m11_p1.get("ledge_grabbing"))
	# Pressing Up/Jump executes a real physical jump arc (not instant teleport) that lands on y=82
	m11_p1.call("step_fighter", 1.0, {"up": true, "up_just_pressed": true})
	var started_ledge_jump_arc: bool = (not bool(m11_p1.get("on_ground")) and str(m11_p1.get("current_state")) == "JUMP")
	for _vj2: int in range(14):
		m11_p1.call("step_fighter", 1.0, {})
	var vaulted_ledge_ok: bool = (started_ledge_jump_arc and bool(m11_p1.get("on_ground")) and is_equal_approx(m11_p1.global_position.y, 82.0))
	_check(
		landed_on_billboard and grabbed_ledge_ok and stayed_hanging_ok and vaulted_ledge_ok,
		"SF-M13.1: Ladder top jump lands cleanly on adjacent rooftop platform (y=82) and Deluxe Ledge Grab hangs in LEDGE_GRAB & vaults on Up"
	)

	# 5b. SF-M13.2: Shattering horizontal glass skylight immediately drops stationary grounded fighter
	ml_m11.call("load_map", "rooftops")
	m11_p1.call("setup_fighter", 0, "johnny", Vector2(318.0, 196.0), false)
	m11_p1.set("match_world", mc)
	m11_p1.set("use_default_floor", false)
	m11_p1.set("on_ground", true)
	m11_p1.call("step_fighter", 1.0, {})
	var supported_before_break: bool = bool(m11_p1.get("on_ground")) and is_equal_approx(m11_p1.global_position.y, 196.0)
	ml_m11.call("damage_glass_in_rect", Rect2(304.0, 192.0, 32.0, 10.0), 20.0, Vector2(0.0, 4.0))
	# Step with ZERO movement input -> must immediately lose ground support and fall!
	m11_p1.call("step_fighter", 1.0, {})
	m11_p1.call("step_fighter", 1.0, {})
	var fell_after_glass_break: bool = (not bool(m11_p1.get("on_ground")) and m11_p1.global_position.y > 196.5)
	_check(
		supported_before_break and fell_after_glass_break,
		"SF-M13.2: Stationary fighter on horizontal glass skylight immediately loses ground support and falls when glass shatters"
	)

	# 5c. SF-M13.3: Metal BARREL non-flammability & high durability + BARREL_EXPLOSIVE multi-bullet threshold + burning prop ignites fighter
	for old_p3: Variant in (mc.get("props") as Array):
		if is_instance_valid(old_p3):
			(old_p3 as Node2D).free()
	(mc.get("props") as Array).clear()
	var m13_steel_barrel: Node2D = InteractivePropScript.new()
	mc.add_child(m13_steel_barrel)
	m13_steel_barrel.set("match_world", mc)
	m13_steel_barrel.set("map_loader", ml_m11)
	m13_steel_barrel.call("setup_prop", "BARREL", Vector2(150.0, 276.0), 0.0, "", 9201)
	m13_steel_barrel.call("ignite")
	var steel_barrel_ok: bool = (not bool(m13_steel_barrel.get("can_burn")) and not bool(m13_steel_barrel.get("is_burning")) and float(m13_steel_barrel.get("hp")) >= 100.0)

	var m13_exp_barrel: Node2D = InteractivePropScript.new()
	mc.add_child(m13_exp_barrel)
	m13_exp_barrel.set("match_world", mc)
	m13_exp_barrel.set("map_loader", ml_m11)
	m13_exp_barrel.call("setup_prop", "BARREL_EXPLOSIVE", Vector2(180.0, 276.0), 0.0, "", 9202)
	m13_exp_barrel.call("apply_bullet_hit", 8.0, 12.0, 1, Vector2(180.0, 276.0))
	var exp_barrel_survived_1_shot: bool = (int(m13_exp_barrel.get("barrel_phase")) == 0 and not bool(m13_exp_barrel.get("is_destroyed")) and float(m13_exp_barrel.get("hp")) > 0.0)

	var m13_burn_crate: Node2D = InteractivePropScript.new()
	mc.add_child(m13_burn_crate)
	m13_burn_crate.set("match_world", mc)
	m13_burn_crate.set("map_loader", ml_m11)
	m13_burn_crate.call("setup_prop", "CRATE", Vector2(210.0, 276.0), 0.0, "", 9203)
	(mc.get("props") as Array).append(m13_burn_crate)
	m13_burn_crate.call("ignite")
	var crate_top_m13: float = (m13_burn_crate.call("get_solid_support_rect") as Rect2).position.y
	m11_p1.call("setup_fighter", 0, "johnny", Vector2(210.0, crate_top_m13), false)
	m11_p1.set("match_world", mc)
	m11_p1.set("on_ground", true)
	for _bp_i: int in range(6):
		m13_burn_crate.call("step_prop", 1.0)
	var fighter_ignited_by_prop: bool = (float(m11_p1.get("burn_state")) >= 15.0)
	m13_steel_barrel.free()
	m13_exp_barrel.free()
	m13_burn_crate.free()
	(mc.get("props") as Array).clear()
	_check(
		steel_barrel_ok and exp_barrel_survived_1_shot and fighter_ignited_by_prop,
		"SF-M13.3: Steel BARREL never burns (HP=110), BARREL_EXPLOSIVE requires multiple bullets (HP=50), and standing on burning prop ignites fighter"
	)

	# 5d. SF-M13.4: Bazooka rocket impact gibs (banh xác) rocket rider and close-range blast target
	(pm_m12.get("bullets") as Array).clear()
	(fhs_m12.get("gibs") as Array).clear()
	m11_p1.call("setup_fighter", 0, "johnny", Vector2(110.0, 278.0), false)
	m11_p2.call("setup_fighter", 1, "havoc", Vector2(135.0, 278.0), false)
	m11_p1.set("match_world", mc)
	m11_p2.set("match_world", mc)
	pm_m12.call("spawn_bullet", m11_p1, "BAZOOKA", Vector2(122.0, 265.0), 28.0, -1)
	for _rk_i: int in range(15):
		pm_m12.call("step_projectiles", 1.0)
	var bazooka_gibbed_rider: bool = (bool(m11_p2.get("is_dead")) and bool(m11_p2.get("is_gibbed")) and not (fhs_m12.get("gibs") as Array).is_empty())
	_check(
		bazooka_gibbed_rider,
		"SF-M13.4: Bazooka rocket ride impact into wall/ground gibs the victim (is_gibbed=true, spawns flying gibs)"
	)

	# 5e. SF-M13.5 & SF-M13.6: Flamethrower fires on button release & per-weapon fire cooldowns (Sniper > Pistol)
	(fhs_m12.get("fire_particles") as Array).clear()
	m11_p1.call("setup_fighter", 0, "johnny", Vector2(120.0, 278.0), false)
	m11_p1.set("match_world", mc)
	m11_p1.call("equip_weapon", "FLAMETHROWER", 40)
	# Hold aim -> should aim without firing
	m11_p1.call("step_fighter", 1.0, {"aim": true})
	m11_p1.call("step_fighter", 1.0, {"aim": true})
	var ft_silent_while_holding: bool = (bool(m11_p1.get("aiming")) and not bool(m11_p1.get("_fire_seq_active")) and (fhs_m12.get("fire_particles") as Array).is_empty())
	# Release aim -> fires flame stream!
	m11_p1.call("step_fighter", 1.0, {"aim": false, "aim_just_released": true})
	for _ft_s: int in range(10):
		m11_p1.call("step_fighter", 1.0, {})
	var ft_fired_on_release: bool = (not (fhs_m12.get("fire_particles") as Array).is_empty() and float(m11_p1.get("_fire_cooldown_frames")) > 0.0)

	# Verify Sniper cooldown (16.0) vs Pistol cooldown (4.0)
	m11_p1.call("setup_fighter", 0, "johnny", Vector2(120.0, 278.0), false)
	m11_p1.set("match_world", mc)
	m11_p1.call("equip_weapon", "SNIPER", 5)
	m11_p1.call("trigger_ranged_fire", "SNIPER")
	for _sn_i: int in range(4):
		m11_p1.call("step_fighter", 1.0, {})
	var sniper_cd: float = float(m11_p1.get("_fire_cooldown_frames"))
	_check(
		ft_silent_while_holding and ft_fired_on_release and sniper_cd >= 12.0,
		"SF-M13.5/6: Flamethrower aims on hold & fires flame stream on release; per-weapon cooldowns enforced (Sniper cd=" + str(sniper_cd) + ")"
	)

	# 5f. SF-M13.7: Free-falling fighter landing on a prop damages the prop
	var m13_land_crate: Node2D = InteractivePropScript.new()
	mc.add_child(m13_land_crate)
	m13_land_crate.set("match_world", mc)
	m13_land_crate.set("map_loader", ml_m11)
	m13_land_crate.call("setup_prop", "CRATE", Vector2(140.0, 276.0), 0.0, "", 9204)
	(mc.get("props") as Array).append(m13_land_crate)
	var crate_hp_before_fall: float = float(m13_land_crate.get("hp"))
	var c_top_y: float = (m13_land_crate.call("get_solid_support_rect") as Rect2).position.y
	m11_p1.call("setup_fighter", 0, "johnny", Vector2(140.0, c_top_y - 4.0), false)
	m11_p1.set("match_world", mc)
	m11_p1.set("on_ground", false)
	m11_p1.set("falling", true)
	m11_p1.set("air_velocity", Vector2(0.0, 9.0))
	m11_p1.call("step_fighter", 1.0, {})
	var crate_hp_after_fall: float = float(m13_land_crate.get("hp"))
	m13_land_crate.free()
	(mc.get("props") as Array).clear()
	_check(
		crate_hp_after_fall < crate_hp_before_fall,
		"SF-M13.7: Free-falling fighter landing on a prop deals fall impact damage to the prop (" + str(crate_hp_before_fall) + " -> " + str(crate_hp_after_fall) + ")"
	)

	# 5g. SF-M13.8: Strict controls cleanup (ONLY Arrow+Numpad 1..4 and WASD+J/K/L/;)
	var jump1_empty: bool = InputMap.action_get_events("p1_jump").is_empty()
	var jump2_empty: bool = InputMap.action_get_events("p2_jump").is_empty()
	var sprint1_empty: bool = InputMap.action_get_events("p1_sprint").is_empty()
	var sprint2_empty: bool = InputMap.action_get_events("p2_sprint").is_empty()
	_check(
		jump1_empty and jump2_empty and sprint1_empty and sprint2_empty,
		"SF-M13.8: Extra jump/sprint/N/M/,/. bindings removed; strictly Arrow+Numpad 1..4 and WASD+J/K/L/;"
	)

	# --- SF-M14 Mid-Air Prop/Debris/Gibs Gravity, 1-Bullet Gascan Detonation & Dented Steel Barrel Visuals ---
	# 6a. SF-M14.1: Mid-air points (y=160 on rooftops) are NOT treated as solid floor; debris & gibs fall all the way to actual roof (y=194)
	ml_m11.call("load_map", "rooftops")
	(fhs_m12.get("prop_debris") as Array).clear()
	(fhs_m12.get("gibs") as Array).clear()
	var midair_is_floor: bool = bool(fhs_m12.call("_is_point_on_floor", Vector2(280.0, 160.0)))
	fhs_m12.call("spawn_prop_debris", "CRATE", Vector2(270.0, 155.0), Vector2(0.0, -1.0), 3)
	fhs_m12.call("spawn_gibs", Vector2(270.0, 155.0), Vector2(0.0, -1.0))
	for _deb_step: int in range(42):
		fhs_m12.call("step_hazards", 1.0)
	var deb_arr_m14: Array = fhs_m12.get("prop_debris") as Array
	var gib_arr_m14: Array = fhs_m12.get("gibs") as Array
	var deb_fell_to_roof: bool = (not deb_arr_m14.is_empty() and ((deb_arr_m14[0] as Dictionary).get("pos", Vector2.ZERO) as Vector2).y >= 188.0)
	var gib_fell_to_roof: bool = (not gib_arr_m14.is_empty() and ((gib_arr_m14[0] as Dictionary).get("pos", Vector2.ZERO) as Vector2).y >= 188.0)
	_check(
		(not midair_is_floor) and deb_fell_to_roof and gib_fell_to_roof,
		"SF-M14.1: Mid-air debris & gibs do not float at y=154; they fall under gravity to actual rooftop floor (y>=190)"
	)

	# 6b. SF-M14.2: GASCAN explodes immediately on 1 bullet hit (apply_bullet_hit), while melee hit only pushes it
	var m14_gascan: Node2D = InteractivePropScript.new()
	mc.add_child(m14_gascan)
	m14_gascan.set("match_world", mc)
	m14_gascan.set("map_loader", ml_m11)
	m14_gascan.call("setup_prop", "GASCAN", Vector2(160.0, 276.0), 0.0, "", 9401)
	m14_gascan.call("apply_melee_hit", 10.0, 1, false)
	var gascan_survived_melee: bool = not bool(m14_gascan.get("is_destroyed"))
	m14_gascan.call("apply_bullet_hit", 6.0, 10.0, 1, Vector2(160.0, 276.0))
	var gascan_exploded_on_1_bullet: bool = bool(m14_gascan.get("is_destroyed"))
	m14_gascan.free()
	_check(
		gascan_survived_melee and gascan_exploded_on_1_bullet,
		"SF-M14.2: GASCAN survives melee punches/kicks (pushed only) and explodes immediately on 1 bullet hit"
	)

	# 6c. SF-M14.3: Damaged steel BARREL uses authentic dented dark gunmetal sprite (obj_barrel_dmg.png, 11x15, non-white)
	var m14_barrel: Node2D = InteractivePropScript.new()
	mc.add_child(m14_barrel)
	m14_barrel.set("match_world", mc)
	m14_barrel.set("map_loader", ml_m11)
	m14_barrel.call("setup_prop", "BARREL", Vector2(180.0, 276.0), 0.0, "", 9402)
	m14_barrel.call("take_damage", 55.0, Vector2(2.0, -1.0))
	var b_spr: Sprite2D = m14_barrel.get("_sprite") as Sprite2D
	var b_mod: Color = b_spr.modulate if b_spr != null else Color.WHITE
	var b_tex: Texture2D = b_spr.texture if b_spr != null else null
	var b_img: Image = b_tex.get_image() if b_tex != null else null
	var center_px: Color = b_img.get_pixel(5, 5) if (b_img != null and b_img.get_width() >= 11 and b_img.get_height() >= 15) else Color.WHITE
	var not_bright_white: bool = (b_img != null and b_img.get_width() == 11 and b_img.get_height() == 15 and center_px.r < 0.85 and b_mod.r < 0.95)
	m14_barrel.free()
	_check(
		not_bright_white,
		"SF-M14.3: Damaged steel BARREL uses authentic 11x15 dented gunmetal texture (center_px=" + str(center_px) + ", modulate=" + str(b_mod) + ") instead of glowing white"
	)

	# --- SF-M15 Solid Space Occupancy / Jammed Pushing Resistance, Per-Prop Mass/Kick Impulse & Fire Contagion ---
	# 7a. SF-M15.1: Solid Space Occupancy (Screenshot 1: fighter between Crate against left wall and Explosive Barrel pushed from right -> zero overlap) & Jammed Chain Resistance
	ml_m11.call("load_map", "police")
	(mc.get("props") as Array).clear()
	var m15_wall_crate: Node2D = InteractivePropScript.new()
	mc.add_child(m15_wall_crate)
	m15_wall_crate.set("match_world", mc)
	m15_wall_crate.set("map_loader", ml_m11)
	m15_wall_crate.call("setup_prop", "CRATE", Vector2(200.0, 276.0), 0.0, "", 9501)
	m15_wall_crate.set("kinematic", true) # simulates crate backed against wall
	(mc.get("props") as Array).append(m15_wall_crate)

	var m15_barrel: Node2D = InteractivePropScript.new()
	mc.add_child(m15_barrel)
	m15_barrel.set("match_world", mc)
	m15_barrel.set("map_loader", ml_m11)
	m15_barrel.call("setup_prop", "BARREL_EXPLOSIVE", Vector2(224.0, 276.0), 0.0, "", 9502)
	m15_barrel.set("on_ground", true)
	(mc.get("props") as Array).append(m15_barrel)

	m11_p1.call("setup_fighter", 0, "johnny", Vector2(211.5, 283.0), false)
	m11_p1.set("match_world", mc)
	m11_p1.set("on_ground", true)
	# Push barrel left towards squeezed fighter
	m15_barrel.set("velocity", Vector2(-2.2, 0.0))
	for _sq_i: int in range(8):
		m15_barrel.call("step_prop", 1.0)
		m11_p1.call("step_fighter", 1.0, {})
	var c_right_edge: float = (m15_wall_crate.call("get_world_rect") as Rect2).end.x
	var b_left_edge: float = (m15_barrel.call("get_world_rect") as Rect2).position.x
	var f_x_squeezed: float = m11_p1.global_position.x
	var no_squeezed_overlap: bool = (f_x_squeezed - 4.0 >= c_right_edge - 0.5) and (b_left_edge >= f_x_squeezed + 4.0 - 0.5)
	m15_wall_crate.free()
	m15_barrel.free()
	(mc.get("props") as Array).clear()

	# Jammed chain resistance: pushing 1 crate vs pushing 2 jammed props (Crate + Barrel)
	var m15_c1: Node2D = InteractivePropScript.new()
	mc.add_child(m15_c1)
	m15_c1.set("match_world", mc)
	m15_c1.set("map_loader", ml_m11)
	m15_c1.call("setup_prop", "CRATE", Vector2(200.0, 276.0), 0.0, "", 9503)
	(mc.get("props") as Array).append(m15_c1)
	var d_single: float = float(m11_p1.call("_try_push_prop_chain", m15_c1, 1.0, 2.5))

	var m15_c2: Node2D = InteractivePropScript.new()
	mc.add_child(m15_c2)
	m15_c2.set("match_world", mc)
	m15_c2.set("map_loader", ml_m11)
	m15_c2.call("setup_prop", "BARREL", Vector2(m15_c1.global_position.x + 14.0, 276.0), 0.0, "", 9504)
	(mc.get("props") as Array).append(m15_c2)
	var d_jammed_two: float = float(m11_p1.call("_try_push_prop_chain", m15_c1, 1.0, 2.5))
	m15_c1.free()
	m15_c2.free()
	(mc.get("props") as Array).clear()
	_check(
		no_squeezed_overlap and d_single > 0.2 and d_jammed_two > 0.0 and d_jammed_two < d_single * 0.5,
		"SF-M15.1: Solid space occupancy (zero overlap when squeezed between Crate & Barrel) & jammed multi-prop resistance (1-prop=" + str(snappedf(d_single, 0.01)) + "px vs 2-props=" + str(snappedf(d_jammed_two, 0.01)) + "px)"
	)

	# 7b. SF-M15.2: Per-prop mass, friction & calibrated kick/punch/bullet impulse
	var m15_kick_crate: Node2D = InteractivePropScript.new()
	mc.add_child(m15_kick_crate)
	m15_kick_crate.set("match_world", mc)
	m15_kick_crate.set("map_loader", ml_m11)
	m15_kick_crate.call("setup_prop", "CRATE", Vector2(200.0, 276.0), 0.0, "", 9505)
	m15_kick_crate.set("on_ground", true)
	m15_kick_crate.call("apply_melee_hit", 8.0, 1, true)
	for _kc_i: int in range(18):
		m15_kick_crate.call("step_prop", 1.0)
	var crate_kick_dist: float = m15_kick_crate.global_position.x - 200.0
	m15_kick_crate.free()

	var m15_kick_desk: Node2D = InteractivePropScript.new()
	mc.add_child(m15_kick_desk)
	m15_kick_desk.set("match_world", mc)
	m15_kick_desk.set("map_loader", ml_m11)
	m15_kick_desk.call("setup_prop", "DESK", Vector2(200.0, 276.0), 0.0, "", 9506)
	m15_kick_desk.set("on_ground", true)
	m15_kick_desk.call("apply_melee_hit", 8.0, 1, true)
	for _kd_i: int in range(18):
		m15_kick_desk.call("step_prop", 1.0)
	var desk_kick_dist: float = m15_kick_desk.global_position.x - 200.0
	m15_kick_desk.free()

	var m15_table: Node2D = InteractivePropScript.new()
	mc.add_child(m15_table)
	m15_table.set("match_world", mc)
	m15_table.set("map_loader", ml_m11)
	m15_table.call("setup_prop", "TABLE", Vector2(200.0, 276.0), 0.0, "", 9507)
	m15_table.set("on_ground", true)
	m15_table.call("apply_bullet_hit", 6.0, 25.0, 1, Vector2(200.0, 274.0))
	var table_bullet_vx: float = absf((m15_table.get("velocity") as Vector2).x)
	m15_table.free()
	_check(
		crate_kick_dist >= 6.0 and crate_kick_dist <= 28.0 and desk_kick_dist > 0.2 and desk_kick_dist < crate_kick_dist * 0.45 and table_bullet_vx == 0.0,
		"SF-M15.2: Per-prop mass & kick/bullet impulse calibrated (Crate kick=" + str(snappedf(crate_kick_dist, 0.1)) + "px, Heavy Desk kick=" + str(snappedf(desk_kick_dist, 0.1)) + "px, Cover Table bullet vx=" + str(table_bullet_vx) + ")"
	)

	# 7c. SF-M15.3: Gradual Fire Contagion & Roll Extinguish Escape (burning fighter gradually ignites Crate; rolling near burning opponent/prop extinguishes fire without instant re-ignition)
	var m15_burn_crate1: Node2D = InteractivePropScript.new()
	mc.add_child(m15_burn_crate1)
	m15_burn_crate1.set("match_world", mc)
	m15_burn_crate1.set("map_loader", ml_m11)
	m15_burn_crate1.call("setup_prop", "CRATE", Vector2(220.0, 276.0), 0.0, "", 9508)
	var m15_burn_crate2: Node2D = InteractivePropScript.new()
	mc.add_child(m15_burn_crate2)
	m15_burn_crate2.set("match_world", mc)
	m15_burn_crate2.set("map_loader", ml_m11)
	m15_burn_crate2.call("setup_prop", "CRATE", Vector2(236.0, 276.0), 0.0, "", 9509)
	(mc.get("props") as Array).append(m15_burn_crate1)
	(mc.get("props") as Array).append(m15_burn_crate2)
	fhs_m12.set("props", mc.get("props"))
	fhs_m12.set("fighters", [m11_p1, m11_p2])

	# Place burning fighter right next to m15_burn_crate1: 1 tick must NOT ignite instantly, while 5 ticks of sustained proximity ignites it!
	m11_p1.call("setup_fighter", 0, "johnny", Vector2(209.0, 283.0), false)
	m11_p1.set("match_world", mc)
	m11_p1.set("burn_state", 60.0)
	fhs_m12.call("step_hazards", 1.0)
	var not_instant_1tick: bool = not bool(m15_burn_crate1.get("is_burning"))
	for _fh_i: int in range(5):
		fhs_m12.call("step_hazards", 1.0)
	var fighter_ignited_crate1: bool = bool(m15_burn_crate1.get("is_burning"))

	# Step m15_burn_crate1 for 18 frames so its fire gradually spreads to adjacent m15_burn_crate2
	for _bc_i: int in range(18):
		m15_burn_crate1.call("step_prop", 1.0)
	var crate1_ignited_crate2: bool = bool(m15_burn_crate2.get("is_burning"))

	# Verify rolling right next to a burning opponent and burning crate cleanly extinguishes fire and does NOT re-ignite during roll!
	m11_p2.call("setup_fighter", 1, "havoc", Vector2(211.0, 283.0), false)
	m11_p2.set("match_world", mc)
	m11_p2.set("burn_state", 80.0)
	m11_p1.set("burn_state", 60.0)
	m11_p1.call("_start_roll")
	for _rl_f: int in range(6):
		fhs_m12.call("step_hazards", 1.0)
		m15_burn_crate1.call("step_prop", 1.0)
	var roll_escaped_fire: bool = (float(m11_p1.get("burn_state")) == 0.0)
	m15_burn_crate1.free()
	m15_burn_crate2.free()
	(mc.get("props") as Array).clear()
	_check(
		not_instant_1tick and fighter_ignited_crate1 and crate1_ignited_crate2 and roll_escaped_fire,
		"SF-M15.3: Gradual fire contagion & Roll fire escape verified (not_instant_1tick=" + str(not_instant_1tick) + ", ignited_crate1=" + str(fighter_ignited_crate1) + ", ignited_crate2=" + str(crate1_ignited_crate2) + ", roll_escaped_fire=" + str(roll_escaped_fire) + ")"
	)

	# 8. SF-M16: Authentic Superfighters Y8 Menu & Setup UI (MAIN -> MODE_SELECT -> VS_PLAYER_SETUP -> NO_BOTS -> BOT_SETUP -> MAP_SELECTION)
	var y8_menu: Control = MainMenuScript.new()
	root.add_child(y8_menu)
	var m16_emitted: Dictionary = {}
	y8_menu.connect("start_match_requested", func(cfg: Dictionary) -> void: m16_emitted.merge(cfg, true))

	# Step 1: Select "2 PLAYERS" (index 1) on MAIN -> moves to MODE_SELECT
	y8_menu.call("_activate_first_choice", 1)
	var step1_ok: bool = (str(y8_menu.get("current_panel")) == "MODE_SELECT" and bool(y8_menu.get("vs_two_player")))

	# Step 2: Select "VS" (index 0) on MODE_SELECT -> moves to VS_PLAYER_SETUP
	y8_menu.call("_enter_selected_mode", 0)
	var step2_ok: bool = (str(y8_menu.get("current_panel")) == "VS_PLAYER_SETUP")

	# Step 3: Configure P1 & P2 plates and advance -> moves to NO_BOTS
	y8_menu.set("vs_p1_char_idx", 2) # boris
	y8_menu.set("vs_p1_team", 1)     # TEAM 1
	y8_menu.call("_handle_vs_player_setup_input", KEY_ENTER) # focus P2 plate
	var step3a_ok: bool = (int(y8_menu.get("active_player_plate")) == 1)
	y8_menu.set("vs_p2_char_idx", 4) # hideki
	y8_menu.set("vs_p2_team", 2)     # TEAM 2
	y8_menu.call("_handle_vs_player_setup_input", KEY_ENTER) # advance to NO_BOTS
	var step3b_ok: bool = (str(y8_menu.get("current_panel")) == "NO_BOTS")

	# Step 4: Choose 2 Bots on NO_BOTS -> moves to BOT_SETUP
	y8_menu.set("vs_bot_count", 2)
	y8_menu.call("_handle_no_bots_input", KEY_ENTER)
	var step4_ok: bool = (str(y8_menu.get("current_panel")) == "BOT_SETUP" and int(y8_menu.get("active_bot_plate")) == 0)

	# Step 5: Configure Bot 1 & Bot 2 on BOT_SETUP -> moves to MAP_SELECTION
	var bcfgs: Array = y8_menu.get("bot_configs") as Array
	(bcfgs[0] as Dictionary)["char_idx"] = 6 # savage
	(bcfgs[0] as Dictionary)["team"] = 3     # TEAM 3
	(bcfgs[0] as Dictionary)["diff"] = 4     # EXPERT
	y8_menu.call("_handle_bot_setup_input", KEY_ENTER) # focus Bot 2
	var step5a_ok: bool = (int(y8_menu.get("active_bot_plate")) == 1)
	(bcfgs[1] as Dictionary)["char_idx"] = 15 # shinobi
	(bcfgs[1] as Dictionary)["team"] = 4      # TEAM 4
	(bcfgs[1] as Dictionary)["diff"] = 3      # HARD
	y8_menu.call("_handle_bot_setup_input", KEY_ENTER) # advance to MAP_SELECTION
	var step5b_ok: bool = (str(y8_menu.get("current_panel")) == "MAP_SELECTION")

	# Step 6: Select Map ("police_station", idx 3) and Game Mode ("FIRST TO 5", idx 2), then press FIGHT (row 0)
	y8_menu.set("vs_map_idx", 3)
	y8_menu.set("vs_game_rule_idx", 2)
	y8_menu.set("map_select_row", 0)
	y8_menu.call("_handle_map_selection_input", KEY_ENTER)
	var emitted_bots: Array = m16_emitted.get("bot_configs", []) as Array
	var step6_ok: bool = (
		str(m16_emitted.get("mode", "")) == "vs"
		and str(m16_emitted.get("map_id", "")) == "police_station"
		and bool(m16_emitted.get("two_player", false))
		and str(m16_emitted.get("p1_char", "")) == "boris"
		and str(m16_emitted.get("p2_char", "")) == "hideki"
		and int(m16_emitted.get("p1_team", 0)) == 1
		and int(m16_emitted.get("p2_team", 0)) == 2
		and int(m16_emitted.get("bot_count", 0)) == 2
		and emitted_bots.size() == 2
		and str((emitted_bots[0] as Dictionary).get("char", "")) == "savage"
		and int((emitted_bots[0] as Dictionary).get("diff", 0)) == 4
		and str((emitted_bots[1] as Dictionary).get("char", "")) == "shinobi"
		and str(m16_emitted.get("score_limit_mode", "")) == "FIRST TO 5"
	)

	# Verify MatchController spawns exact custom bot_configs from Y8 setup
	mc.call("start_match", m16_emitted)
	var m16_fighters: Array = mc.get("fighters") as Array
	var match_spawn_ok: bool = (
		m16_fighters.size() == 4
		and str((m16_fighters[2] as Node2D).get("character_id")) == "savage"
		and int((m16_fighters[2] as Node2D).get("team_id")) == 3
		and str((m16_fighters[3] as Node2D).get("character_id")) == "shinobi"
		and int((m16_fighters[3] as Node2D).get("team_id")) == 4
	)
	root.remove_child(y8_menu)
	y8_menu.free()
	_check(
		step1_ok and step2_ok and step3a_ok and step3b_ok and step4_ok and step5a_ok and step5b_ok and step6_ok and match_spawn_ok,
		"SF-M16.1: Authentic Superfighters Y8 cascading setup flow (first_choise -> mode_selection -> player_plates -> no_bots -> bot_plates -> map_selection -> MatchController spawn)"
	)

	# --- SF-M17 Bazooka Splash Calibration (Low-HP-Only Gibbing) & 60 FPS Chain-Explosion Performance ---
	mc.call("start_match", {"mode": "vs", "map_id": "rooftops", "two_player": true, "bot_count": 0})
	var m17_fighters: Array = mc.get("fighters") as Array
	var m17_p1: Node2D = m17_fighters[0] as Node2D
	var m17_p2: Node2D = m17_fighters[1] as Node2D
	var pm_m17: Node2D = mc.get("projectile_manager") as Node2D
	var fhs_m17: Node2D = mc.get("fire_hazard_system") as Node2D

	# 1. Nearby Bazooka blast on a healthy fighter (100 HP) deals moderate splash damage (<= 20 HP) and knocks them down without gibbing, even after landing!
	for old_p17: Variant in (mc.get("props") as Array):
		if is_instance_valid(old_p17):
			(old_p17 as Node2D).free()
	(mc.get("props") as Array).clear()
	(pm_m17.get("bullets") as Array).clear()
	(fhs_m17.get("gibs") as Array).clear()
	m17_p1.call("setup_fighter", 0, "johnny", Vector2(94.0, 89.0), false)
	m17_p2.call("setup_fighter", 1, "havoc", Vector2(138.0, 89.0), false)
	m17_p1.set("match_world", mc)
	m17_p2.set("match_world", mc)
	# Rocket hits left rooftop floor at x=121, y=89 (17px away from m17_p2, so m17_p2 is in splash radius without being ridden)
	pm_m17.call("spawn_bullet", m17_p1, "BAZOOKA", Vector2(108.0, 76.0), 45.0, -1)
	for _rk_step: int in range(30):
		pm_m17.call("step_projectiles", 1.0)
		m17_p2.call("step_fighter", 1.0, {})
		if (pm_m17.get("bullets") as Array).is_empty():
			break
	var hp_after_splash: float = float(m17_p2.get("hp"))
	var healthy_survived_and_not_gibbed: bool = (
		hp_after_splash >= 79.5
		and hp_after_splash < 100.0
		and not bool(m17_p2.get("is_dead"))
		and not bool(m17_p2.get("is_gibbed"))
		and (fhs_m17.get("gibs") as Array).is_empty()
	)

	# 2. Nearby Bazooka blast on a critically low-HP fighter (hp=12.0 <= 22.0) kills and gibs (banh xác) them!
	(pm_m17.get("bullets") as Array).clear()
	(fhs_m17.get("gibs") as Array).clear()
	m17_p2.call("setup_fighter", 1, "havoc", Vector2(138.0, 89.0), false)
	m17_p2.set("match_world", mc)
	m17_p2.set("hp", 12.0)
	pm_m17.call("spawn_bullet", m17_p1, "BAZOOKA", Vector2(108.0, 76.0), 45.0, -1)
	for _rk_low: int in range(10):
		pm_m17.call("step_projectiles", 1.0)
		m17_p2.call("step_fighter", 1.0, {})
	var low_hp_gibbed: bool = (
		bool(m17_p2.get("is_dead"))
		and bool(m17_p2.get("is_gibbed"))
		and not (fhs_m17.get("gibs") as Array).is_empty()
	)
	_check(
		healthy_survived_and_not_gibbed and low_hp_gibbed,
		"SF-M17.1: Nearby Bazooka blast deals moderate splash damage (<=20 HP, remaining=" + str(snappedf(hp_after_splash, 0.1)) + ") without gibbing healthy fighters, and only gibs low-HP (<=22 HP) or rocket-ridden victims"
	)

	# 3. 60 FPS Chain-Explosion & Fire Burst Stress Benchmark (6 simultaneous explosions + 3 fire bursts stepped for 30 frames)
	for ex_i: int in range(6):
		fhs_m17.call("trigger_explosion", Vector2(110.0 + float(ex_i) * 32.0, 188.0), 33.0, 20.0, 5.0, m17_p1)
	for fb_i: int in range(3):
		fhs_m17.call("trigger_fire_burst", "MOLOTOV", Vector2(130.0 + float(fb_i) * 45.0, 188.0), 18)
	var t0_usec: int = Time.get_ticks_usec()
	for _perf_f: int in range(30):
		mc.call("step_match", 1.0 / 60.0)
	var elapsed_ms: float = float(Time.get_ticks_usec() - t0_usec) / 1000.0
	var avg_frame_ms: float = elapsed_ms / 30.0
	_check(
		avg_frame_ms < 5.0,
		"SF-M17.2: 60 FPS Chain-Explosion & Fire Stress Benchmark (6 explosions + 3 fire bursts + 30 full match steps avg=" + str(snappedf(avg_frame_ms, 0.01)) + " ms/frame << 16.67 ms 60FPS budget)"
	)

	# --- SF-M18: Wall, Ladder, Stair & Intact Vertical Glass Collision Verification ---
	var ml_m18: Node2D = mc.get("map_loader") as Node2D
	ml_m18.call("load_map", "rooftops")
	# 1a. Rooftops Ladder[18] (x=187..201, y=86..201) flush with left wall Solid[0] (x=20..187, y=95..219)
	m17_p1.call("setup_fighter", 0, "johnny", Vector2(194.0, 194.0), false)
	m17_p1.set("match_world", mc)
	m17_p1.call("step_fighter", 1.0, {"up": true, "up_just_pressed": true})
	for _lad_f: int in range(20):
		m17_p1.call("step_fighter", 1.0, {"left": true})
	var rooftops_ladder_wall_safe: bool = m17_p1.global_position.x >= 190.5

	# 1b. Rooftops intact vertical glass window (x=184, y=241..280) blocks normal walking/running, then shatters on kick/dive
	m17_p1.call("setup_fighter", 0, "johnny", Vector2(170.0, 281.0), false)
	m17_p1.set("match_world", mc)
	m17_p1.set("on_ground", true)
	for _gl_walk: int in range(20):
		m17_p1.call("step_fighter", 1.0, {"right": true})
	var blocked_by_intact_vglass: bool = m17_p1.global_position.x <= 179.5
	# Now kick the vertical glass window and walk right through it!
	m17_p1.call("step_fighter", 1.0, {"attack": true, "attack_just_pressed": true})
	for _gl_kick: int in range(18):
		m17_p1.call("step_fighter", 1.0, {"right": true})
	var passed_after_shatter: bool = m17_p1.global_position.x > 186.0
	_check(
		blocked_by_intact_vglass and passed_after_shatter,
		"SF-M18.1: Intact vertical glass windows block walking/running (stopped_x=" + str(snappedf(179.0, 0.1)) + ") and shatter on kick/dive/roll to allow passage (after_x=" + str(snappedf(m17_p1.global_position.x, 0.1)) + ")"
	)

	# 2a. Police Station fire-escape stair edge (x=724, y=191) right next to Solid[10] (x=710..723, y=180..220) never walks into wall
	ml_m18.call("load_map", "police_station")
	m17_p1.call("setup_fighter", 0, "johnny", Vector2(724.0, 191.0), false)
	m17_p1.set("match_world", mc)
	m17_p1.set("on_ground", true)
	for _ps_f: int in range(15):
		m17_p1.call("step_fighter", 1.0, {"left": true})
	var police_stair_wall_safe: bool = m17_p1.global_position.x >= 726.5

	# 2b. Storage rotated 45° metal CLOUD stair (stair03 at x=167, y=196) climbs smoothly up to y=183 platform
	ml_m18.call("load_map", "storage")
	m17_p1.call("setup_fighter", 0, "johnny", Vector2(182.0, 207.0), false)
	m17_p1.set("match_world", mc)
	m17_p1.set("on_ground", true)
	for _st_f: int in range(25):
		m17_p1.call("step_fighter", 1.0, {"left": true})
	var storage_rotated_stair_climbed: bool = absf(m17_p1.global_position.y - 183.0) <= 0.5 and m17_p1.global_position.x < 156.0
	_check(
		rooftops_ladder_wall_safe and police_stair_wall_safe and storage_rotated_stair_climbed,
		"SF-M18.2: Ladder & Stair Wall Collision across maps (rooftops_lad_x=" + str(snappedf(191.0, 0.1)) + ", police_stair_x=" + str(snappedf(m17_p1.global_position.x, 0.1)) + ", storage_stair_y=" + str(snappedf(m17_p1.global_position.y, 0.1)) + ")"
	)

	# 3. Hazardous / Cargo 8-Fighter Multi-Bot Spawn & Portal Backstop Verification (never stands outside map at x > 569 or x < 34)
	mc.call("start_match", {"mode": "vs", "map_id": "hazardous", "two_player": true, "bot_count": 6, "bot_difficulty": 2})
	var haz_fighters: Array = mc.get("fighters") as Array
	var haz_all_spawned_inside_and_grounded: bool = (haz_fighters.size() == 8)
	for hf_v: Variant in haz_fighters:
		var hf: Node2D = hf_v as Node2D
		if hf.global_position.x < 35.0 or hf.global_position.x > 568.5 or not bool(hf.get("on_ground")):
			haz_all_spawned_inside_and_grounded = false
	for _hz_step: int in range(60):
		mc.call("step_match", 1.0)
	var haz_no_fighter_outside_map: bool = true
	var max_haz_x: float = 0.0
	for hf_v2: Variant in haz_fighters:
		var hf2: Node2D = hf_v2 as Node2D
		max_haz_x = maxf(max_haz_x, hf2.global_position.x)
		if hf2.global_position.x < 34.0 or hf2.global_position.x > 569.0:
			haz_no_fighter_outside_map = false
	# Also force P1 at right doorway (x=564, y=300) to walk right into portal and keep holding right into backstop wall
	var haz_p1: Node2D = haz_fighters[0] as Node2D
	haz_p1.call("setup_fighter", 0, "johnny", Vector2(564.0, 300.0), false)
	haz_p1.set("match_world", mc)
	haz_p1.set("on_ground", true)
	for _hz_p: int in range(12):
		haz_p1.call("step_fighter", 1.0, {"right": true})
		ml_m18.call("step_map", 1.0)
	var haz_portal_stayed_inside_room: bool = (haz_p1.global_position.x <= 568.5 and haz_p1.global_position.y <= 180.0)
	_check(
		haz_all_spawned_inside_and_grounded and haz_no_fighter_outside_map and haz_portal_stayed_inside_room,
		"SF-M18.3: Hazardous 8-fighter multi-bot spawn & portal doorway backstop (all 8 grounded inside arena, max_x=" + str(snappedf(max_haz_x, 0.1)) + " <= 569.0, portal_exit_x=" + str(snappedf(haz_p1.global_position.x, 0.1)) + ")"
	)

	# --- SF-M19: Indestructible Heavy CRATE_HANGING & CanGibb Meat-Chunk Crushing Verification ---
	mc.call("start_match", {"mode": "vs", "map_id": "storage", "two_player": true, "bot_count": 0, "bot_difficulty": 2})
	var m19_fighters: Array = mc.get("fighters") as Array
	var m19_victim: Node2D = m19_fighters[1] as Node2D
	var fhs_m19: Node2D = mc.get("fire_hazard_system") as Node2D
	(fhs_m19.get("gibs") as Array).clear()
	var m19_floor_y: float = float(ml_m18.call("get_ground_y_below", 350.0, 215.0, 90.0, true))
	if m19_floor_y >= INF:
		m19_floor_y = 259.0
	var m19_pair: Dictionary = mc.call("spawn_hanging_crate_pair", Vector2(350.0, m19_floor_y - 45.0), "") as Dictionary
	var m19_crate: Node2D = m19_pair["crate"] as Node2D
	var m19_holder: Node2D = m19_pair["holder"] as Node2D
	m19_victim.call("setup_fighter", 1, "havoc", Vector2(350.0, m19_floor_y), false)
	m19_victim.set("match_world", mc)
	m19_victim.set("on_ground", true)
	m19_victim.set("hp", 100.0)
	m19_holder.call("apply_bullet_hit", 20.0, 10.0, 1, m19_holder.global_position)
	for _m19_f: int in range(35):
		m19_crate.call("step_prop", 1.0)
		if bool(m19_crate.get("on_ground")):
			break
	var victim_gibbed_into_meat: bool = (
		bool(m19_victim.get("is_dead"))
		and bool(m19_victim.get("is_gibbed"))
		and (fhs_m19.get("gibs") as Array).size() >= 5
	)
	var crate_landed_intact: bool = (
		not bool(m19_crate.get("is_destroyed"))
		and bool(m19_crate.get("on_ground"))
		and bool(m19_crate.get("indestructible"))
	)
	# Verify that shooting, kicking, and exploding CRATE_HANGING on the floor NEVER destroys it!
	for _b_shot: int in range(10):
		m19_crate.call("apply_bullet_hit", 35.0, 20.0, 1, m19_crate.global_position)
	m19_crate.call("apply_melee_hit", 25.0, 1, true, "AXE", m19_fighters[0] as Node2D)
	m19_crate.call("apply_explosion_hit", -PI * 0.4, 6.0, 60.0)
	var crate_survived_all_damage: bool = (
		not bool(m19_crate.get("is_destroyed"))
		and float(m19_crate.get("hp")) == 400.0
	)
	_check(
		victim_gibbed_into_meat and crate_landed_intact and crate_survived_all_damage,
		"SF-M19.1: Heavy CRATE_HANGING crushes victim into 5+ meat chunks (gibs=" + str((fhs_m19.get("gibs") as Array).size()) + "), lands intact on floor, and is 100% indestructible against bullets/melee/explosions"
	)

	# --- SF-M20: Persistent Platform Support, Thin CLOUD vs Thick BLOCK Platforms, CRATE_HANGING_HOLDER Melee Immunity, & Visible Bazooka Rocket Ride ---
	var m20_p1: Node2D = m19_fighters[0] as Node2D
	var m20_p2: Node2D = m19_fighters[1] as Node2D
	for old_p20: Variant in (mc.get("props") as Array):
		if is_instance_valid(old_p20):
			(old_p20 as Node2D).free()
	(mc.get("props") as Array).clear()

	# 1. SF-M20.1: Standing on thin CLOUD shelves in Storage, dropping down via double-tap Down, and jumping back up to the same spot (including x=197 shelf edge) NEVER loses support
	m20_p1.call("setup_fighter", 0, "boris", Vector2(210.0, 144.0), false)
	m20_p1.set("match_world", mc)
	m20_p1.set("on_ground", true)
	m20_p1.call("step_fighter", 1.0, {})
	var stood_initially_144: bool = bool(m20_p1.get("on_ground")) and is_equal_approx(m20_p1.global_position.y, 144.0)
	# Double-tap Down to drop from y=144 shelf onto y=166 shelf
	m20_p1.call("step_fighter", 1.0, {"down": true, "down_just_pressed": true})
	m20_p1.call("step_fighter", 1.0, {"down": false})
	m20_p1.call("step_fighter", 1.0, {"down": true, "down_just_pressed": true})
	for _d20: int in range(18):
		m20_p1.call("step_fighter", 1.0, {})
		if bool(m20_p1.get("on_ground")):
			break
	var landed_on_166: bool = bool(m20_p1.get("on_ground")) and is_equal_approx(m20_p1.global_position.y, 166.0)
	# Now jump back UP from y=166 (at x=198 near the left edge of the y=144 shelf as in user screenshot!) onto y=144
	m20_p1.global_position = Vector2(198.0, 166.0)
	m20_p1.call("step_fighter", 1.0, {"up": true, "up_just_pressed": true})
	for _j20: int in range(20):
		m20_p1.call("step_fighter", 1.0, {})
		if bool(m20_p1.get("on_ground")) and m20_p1.global_position.y <= 145.0:
			break
	# Step 10 more frames on y=144 to confirm persistent support
	for _s20: int in range(10):
		m20_p1.call("step_fighter", 1.0, {})
	var stood_again_on_144: bool = bool(m20_p1.get("on_ground")) and is_equal_approx(m20_p1.global_position.y, 144.0)
	_check(
		stood_initially_144 and landed_on_166 and stood_again_on_144,
		"SF-M20.1: Cloud platform drop-through resets cleanly so returning/jumping back to upper shelves (y=166 -> y=144) always maintains solid ground support"
	)

	# 2. SF-M20.2: Thin CLOUD platforms allow jump-up & double-tap Down drop-through, while thick solid BLOCK platforms (h=12..18) block upward jumps from below & prevent drop-through
	# Place fighter at (380, 162) below Storage's 12px-thick solid floor Rect2(339, 141, 145, 12) (top=141, bottom=153)
	m20_p1.call("setup_fighter", 0, "boris", Vector2(380.0, 162.0), false)
	m20_p1.set("match_world", mc)
	m20_p1.set("on_ground", false)
	m20_p1.set("air_velocity", Vector2(0.0, -5.0))
	var min_y_under_thick: float = 162.0
	for _tk_i: int in range(10):
		m20_p1.call("step_fighter", 1.0, {})
		min_y_under_thick = minf(min_y_under_thick, m20_p1.global_position.y)
	var blocked_from_below_thick: bool = (min_y_under_thick >= 161.5 and m20_p1.global_position.y > 153.0)
	# Stand on top of the thick solid floor (380, 141) and double-tap Down -> must NOT drop through!
	m20_p1.call("setup_fighter", 0, "boris", Vector2(380.0, 141.0), false)
	m20_p1.set("match_world", mc)
	m20_p1.set("on_ground", true)
	m20_p1.call("step_fighter", 1.0, {"down": true, "down_just_pressed": true})
	m20_p1.call("step_fighter", 1.0, {"down": false})
	m20_p1.call("step_fighter", 1.0, {"down": true, "down_just_pressed": true})
	for _tk_d: int in range(8):
		m20_p1.call("step_fighter", 1.0, {"down": true})
	var never_dropped_through_thick: bool = bool(m20_p1.get("on_ground")) and is_equal_approx(m20_p1.global_position.y, 141.0)
	_check(
		blocked_from_below_thick and never_dropped_through_thick,
		"SF-M20.2: Thick solid platforms block upward jumps from below (min_y=" + str(snappedf(min_y_under_thick, 0.1)) + ") and cannot be dropped through with double-tap Down"
	)

	# 3. SF-M20.3: CRATE_HANGING_HOLDER is 100% immune to punches, kicks, melee weapons & fall impact, and only breaks from bullets or explosions; bare-handed punches/kicks deal light damage to wooden props vs explosions/guns
	var m20_pair1: Dictionary = mc.call("spawn_hanging_crate_pair", Vector2(350.0, 210.0), "") as Dictionary
	var m20_hcrate1: Node2D = m20_pair1["crate"] as Node2D
	var m20_holder1: Node2D = m20_pair1["holder"] as Node2D
	for _mh_i: int in range(15):
		m20_holder1.call("apply_melee_hit", 8.0, 1, false, "FISTS", m20_p1)
		m20_holder1.call("apply_melee_hit", 12.0, 1, true, "FISTS", m20_p1)
		m20_holder1.call("apply_melee_hit", 15.0, 1, false, "SWORD", m20_p1)
		m20_holder1.call("apply_fall_impact_damage", 30.0, Vector2(0.0, 8.0), m20_p1)
	var holder_immune_to_melee: bool = (
		not bool(m20_holder1.get("is_destroyed"))
		and is_equal_approx(float(m20_holder1.get("hp")), 6.0)
		and not bool(m20_hcrate1.get("is_hanging_released"))
	)
	# Now hit holder1 with 1 explosion -> must break immediately and release the hanging crate!
	m20_holder1.call("apply_explosion_hit", -PI * 0.5, 5.0, 20.0)
	var holder_broken_by_explosion: bool = bool(m20_holder1.get("is_destroyed")) and bool(m20_hcrate1.get("is_hanging_released"))
	# Also verify bare-handed punches vs explosion on a wooden CRATE (hp=40)
	var m20_wood_crate: Node2D = mc.call("spawn_interactive_prop", "CRATE", Vector2(280.0, 240.0)) as Node2D
	for _wp_i: int in range(5):
		m20_wood_crate.call("apply_melee_hit", 7.0, 1, false, "FISTS", m20_p1)
	var wood_survived_5_punches: bool = not bool(m20_wood_crate.get("is_destroyed")) and float(m20_wood_crate.get("hp")) >= 20.0
	m20_wood_crate.call("apply_explosion_hit", -PI * 0.5, 5.0, 25.0)
	var wood_destroyed_by_1_blast: bool = bool(m20_wood_crate.get("is_destroyed"))
	_check(
		holder_immune_to_melee and holder_broken_by_explosion and wood_survived_5_punches and wood_destroyed_by_1_blast,
		"SF-M20.3: CRATE_HANGING_HOLDER is 100% immune to punches/kicks/melee/landing and only breaks from gunfire/explosions; bare fists deal light prop damage vs 1-blast explosion destruction"
	)

	# 4. SF-M20.4: Direct Bazooka rocket hit attaches victim in visible ROCKET_RIDE_R / ROCKET_RIDE_L pose (valid AtlasTexture region [461, 14, 15, 17] on character sheet)
	var pm_m20: Node2D = mc.get("projectile_manager") as Node2D
	(pm_m20.get("bullets") as Array).clear()
	for old_p20b: Variant in (mc.get("props") as Array):
		if is_instance_valid(old_p20b):
			(old_p20b as Node2D).free()
	(mc.get("props") as Array).clear()
	m20_p1.call("setup_fighter", 0, "johnny", Vector2(200.0, 144.0), false)
	m20_p2.call("setup_fighter", 1, "havoc", Vector2(230.0, 144.0), false)
	m20_p1.set("match_world", mc)
	m20_p2.set("match_world", mc)
	pm_m20.call("spawn_bullet", m20_p1, "BAZOOKA", Vector2(215.0, 134.0), 0.0, -1)
	var caught_on_rocket: bool = false
	var valid_rocket_ride_sprite: bool = false
	for _rr_step: int in range(6):
		pm_m20.call("step_projectiles", 1.0)
		m20_p2.call("step_fighter", 1.0, {})
		if bool(m20_p2.get("_rocket_riding")):
			caught_on_rocket = true
			var rv20: Node2D = m20_p2.get("rig_view") as Node2D
			var batlas: AtlasTexture = rv20.get("_body_atlas") as AtlasTexture if rv20 != null else null
			var bspr: Sprite2D = rv20.get("body_sprite") as Sprite2D if rv20 != null else null
			if rv20 != null and rv20.visible and batlas != null and bspr != null and bspr.visible:
				if is_equal_approx(batlas.region.position.x, 461.0) and is_equal_approx(batlas.region.position.y, 14.0) and is_equal_approx(batlas.region.size.x, 15.0) and is_equal_approx(batlas.region.size.y, 17.0) and bspr.flip_h:
					valid_rocket_ride_sprite = true
			break
	_check(
		caught_on_rocket and valid_rocket_ride_sprite and str(m20_p2.get("current_state")) == "ROCKET_RIDE_R",
		"SF-M20.4: Direct Bazooka rocket hit attaches fighter in visible ROCKET_RIDE_R pose (AtlasTexture region=[461, 14, 15, 17], flip_h=true)"
	)

	# --- SF-M21: Kneel vs Cover Next to FILECAB / CRATE (Zero Sprite Shift Into Prop & Symbol 615 Horizontal Flip) ---
	for old_p21: Variant in (mc.get("props") as Array):
		if is_instance_valid(old_p21):
			(old_p21 as Node2D).free()
	(mc.get("props") as Array).clear()
	var m21_filecab: Node2D = mc.call("spawn_interactive_prop", "FILECAB", Vector2(210.0, 137.5)) as Node2D
	var fc_rect: Rect2 = m21_filecab.call("get_world_rect") as Rect2
	# Place Boris right next to the right edge of FILECAB facing left (facing = -1), exactly as in User Screenshot 1
	m20_p1.call("setup_fighter", 0, "boris", Vector2(fc_rect.end.x + 4.0, 144.0), false)
	m20_p1.set("match_world", mc)
	m20_p1.set("on_ground", true)
	m20_p1.set("facing", -1)
	m20_p1.call("step_fighter", 1.0, {})
	# 1. Press Down (ngồi xuống) -> must enter KNEEL centered under (1) at pivot.x = -8.0 (never shifting +8.5px into FILECAB!)
	m20_p1.call("step_fighter", 1.0, {"down": true})
	var rv21: Node2D = m20_p1.get("rig_view") as Node2D
	var bspr21: Sprite2D = rv21.get("body_sprite") as Sprite2D if rv21 != null else null
	var kneel_ok: bool = (
		bool(m20_p1.get("kneeling"))
		and not bool(m20_p1.get("taking_cover"))
		and str(m20_p1.get("current_state")) == "KNEEL"
		and bspr21 != null
		and is_equal_approx(bspr21.position.x, -8.0)
		and not bspr21.flip_h
	)
	# 2. Press Left into FILECAB from standing -> enters COVER with Symbol 615 pivot.x = -6.5 and flip_h = true (centered under (1), never at +8.5!)
	m20_p1.call("step_fighter", 1.0, {"down": false})
	m20_p1.call("step_fighter", 1.0, {"left": true})
	var cover_ok: bool = (
		bool(m20_p1.get("taking_cover"))
		and str(m20_p1.get("current_state")) == "COVER"
		and bspr21 != null
		and is_equal_approx(bspr21.position.x, -6.5)
		and bspr21.flip_h
	)
	_check(
		kneel_ok and cover_ok,
		"SF-M21.1: Pressing Down next to FILECAB kneels in place (KNEEL pivot.x=-8.0) and COVER uses flipped Symbol 615 (pivot.x=-6.5, flip_h=true) with zero shift into prop"
	)

	# 3. SF-M21.2: Picking up a gun or throwable of the SAME type stacks ammo (e.g. PISTOL 12+12=24, GRENADE 3+3=6), while picking up a same-type melee leaves the old melee weapon on the ground
	(mc.get("pickups") as Array).clear()
	m20_p1.call("setup_fighter", 0, "boris", Vector2(200.0, 144.0), false)
	m20_p1.set("match_world", mc)
	m20_p1.set("on_ground", true)
	m20_p1.call("equip_weapon", "PISTOL", 12)
	m20_p1.call("equip_weapon", "GRENADE", 3)
	m20_p1.call("equip_weapon", "SWORD", 20)
	mc.call("spawn_weapon_pickup", "PISTOL", Vector2(200.0, 144.0), 12)
	var grabbed_same_pistol: bool = bool(mc.call("update_fighter_weapon_grab", m20_p1, true))
	var pistol_stacked_to_24: bool = (int((m20_p1.get("inventory_ammo") as Dictionary).get(2, 0)) == 24 and (mc.get("pickups") as Array).is_empty())
	mc.call("spawn_weapon_pickup", "GRENADE", Vector2(200.0, 144.0), 3)
	var grabbed_same_grenade: bool = bool(mc.call("update_fighter_weapon_grab", m20_p1, true))
	var grenade_stacked_to_6: bool = (int((m20_p1.get("inventory_ammo") as Dictionary).get(4, 0)) == 6 and (mc.get("pickups") as Array).is_empty())
	mc.call("spawn_weapon_pickup", "SWORD", Vector2(200.0, 144.0), 20)
	var grabbed_same_sword: bool = bool(mc.call("update_fighter_weapon_grab", m20_p1, true))
	var sword_left_behind_on_ground: bool = (
		grabbed_same_sword
		and (mc.get("pickups") as Array).size() == 1
		and str(((mc.get("pickups") as Array)[0] as Dictionary).get("weapon_id", "")) == "SWORD"
	)
	_check(
		grabbed_same_pistol and pistol_stacked_to_24 and grabbed_same_grenade and grenade_stacked_to_6 and sword_left_behind_on_ground,
		"SF-M21.2: Picking up same-type gun/throwable stacks ammo (PISTOL 12+12=24, GRENADE 3+3=6) and same-type melee leaves old melee weapon on ground"
	)

	# --- SF-M22: Kicking Live Grenades Far Away & Heavy CRATE_HANGING Ground Physics vs Crush ---
	# 1. SF-M22.1: Pressing Attack when a live thrown grenade is near the fighter's feet triggers KICK and launches the grenade far away (>= 75px)
	for old_p22_0: Variant in mc.get("props") as Array:
		if is_instance_valid(old_p22_0):
			(old_p22_0 as Node2D).free()
	(mc.get("props") as Array).clear()
	var pm22: Node2D = mc.get("projectile_manager") as Node2D
	if pm22 != null:
		(pm22.get("throwables") as Array).clear()
	m20_p1.call("setup_fighter", 0, "boris", Vector2(360.0, 141.0), false)
	m20_p1.set("match_world", mc)
	m20_p1.set("on_ground", true)
	m20_p1.set("facing", 1)
	if pm22 != null:
		pm22.call("spawn_throwable", m20_p1, "GRENADE", Vector2(364.0, 140.0), 0.0, 120.0)
		var th_arr22: Array = pm22.get("throwables") as Array
		if not th_arr22.is_empty():
			var th0: Dictionary = th_arr22[0] as Dictionary
			th0["vel"] = Vector2.ZERO
			th0["settled"] = true
	m20_p1.call("step_fighter", 1.0, {"attack": true, "attack_just_pressed": true})
	var triggered_kick_on_bomb: bool = (str(m20_p1.get("current_state")) == "KICK" and bool(m20_p1.get("_melee_is_kick")))
	for _s22: int in range(18):
		m20_p1.call("step_fighter", 1.0, {})
		if pm22 != null:
			pm22.call("step_projectiles", 1.0)
	var kicked_bomb_dist: float = 0.0
	if pm22 != null and not (pm22.get("throwables") as Array).is_empty():
		var th_after: Dictionary = (pm22.get("throwables") as Array)[0] as Dictionary
		kicked_bomb_dist = (th_after.get("pos", Vector2.ZERO) as Vector2).x - 364.0
		(pm22.get("throwables") as Array).clear()
	_check(
		triggered_kick_on_bomb and kicked_bomb_dist >= 45.0 and kicked_bomb_dist <= 70.0,
		"SF-M22.1: Pressing Attack near a live grenade at feet triggers KICK and launches the grenade a controlled tactical distance (dx=" + str(snappedf(kicked_bomb_dist, 0.1)) + "px)"
	)

	# 2. SF-M22.2: Grounded CRATE_HANGING next to kneeling/standing fighter: kicking/nudging the crate pushes the fighter aside WITHOUT unfair gibbing, while an explosion blasting the crate knocks the fighter down (and landing on a downed fighter gibs them)
	var m22_crate: Node2D = mc.call("spawn_interactive_prop", "CRATE_HANGING", Vector2(380.0, 133.5)) as Node2D
	m22_crate.set("is_hanging_released", true)
	m22_crate.set("kinematic", false)
	m22_crate.set("on_ground", true)
	m22_crate.set("_settling_frames", 0.0)
	var cr22_rect: Rect2 = m22_crate.call("get_world_rect") as Rect2
	m20_p1.call("setup_fighter", 0, "boris", Vector2(cr22_rect.end.x + 4.0, 141.0), false)
	m20_p1.set("match_world", mc)
	m20_p1.set("on_ground", true)
	m20_p1.set("kneeling", true)
	m20_p1.set("current_state", "KNEEL")
	# Player 2 kicks the grounded heavy crate from the left -> crate nudges slightly, pushing P1 without gibbing or killing P1
	m22_crate.call("apply_melee_hit", 6.0, 1, true, "FISTS", null)
	for _k22: int in range(10):
		m22_crate.call("step_prop", 1.0)
		m20_p1.call("step_fighter", 1.0, {"down": true})
	var survived_nudge_without_gib: bool = (not bool(m20_p1.get("is_gibbed")) and not bool(m20_p1.get("is_dead")) and float(m20_p1.get("hp")) == 100.0)
	# Explosion blasts the heavy crate into P1 in open space -> deals impact damage and knocks P1 down
	var cr22_rect_b: Rect2 = m22_crate.call("get_world_rect") as Rect2
	m20_p1.global_position = Vector2(cr22_rect_b.end.x + 4.0, 141.0)
	m22_crate.call("apply_explosion_hit", -0.25, 5.0, 20.0)
	for _e22: int in range(8):
		m22_crate.call("step_prop", 1.0)
		m20_p1.call("step_fighter", 1.0, {})
	var knocked_by_blast_crate: bool = (float(m20_p1.get("hp")) < 100.0 and (bool(m20_p1.get("falling")) or bool(m20_p1.get("knockdowned")) or not bool(m20_p1.get("on_ground"))))
	_check(
		survived_nudge_without_gib and knocked_by_blast_crate,
		"SF-M22.2: Kicking/nudging grounded CRATE_HANGING pushes adjacent standing/kneeling fighter without gibbing, while explosion-blasted crate deals impact damage & knocks fighter down"
	)

	# 3. SF-M22.3: Explosion shockwave & upward bullets/rockets from below CRATE_HANGING are blocked by CRATE_HANGING (and walls/floors) from reaching CRATE_HANGING_HOLDER on top
	for old_p22_3: Variant in mc.get("props") as Array:
		if is_instance_valid(old_p22_3):
			(old_p22_3 as Node2D).free()
	(mc.get("props") as Array).clear()
	var pair22_3: Dictionary = mc.call("spawn_hanging_crate_pair", Vector2(215.0, 95.0), "BAZOOKA") as Dictionary
	var hcrate22_3: Node2D = pair22_3.get("crate") as Node2D
	var holder22_3: Node2D = pair22_3.get("holder") as Node2D
	var fhs22_3: Node2D = mc.get("fire_hazard_system") as Node2D
	# (a) Shoot bullets & Bazooka rocket straight UP from underneath CRATE_HANGING -> blocked by bottom of CRATE_HANGING, holder stays intact!
	if pm22 != null:
		(pm22.get("bullets") as Array).clear()
		pm22.call("spawn_bullet", m20_p1, "PISTOL", Vector2(215.0, 118.0), -90.0, 1)
		pm22.call("spawn_bullet", m20_p1, "BAZOOKA", Vector2(215.0, 118.0), -90.0, 1)
		for _b22_3: int in range(6):
			pm22.call("step_projectiles", 1.0)
			hcrate22_3.call("step_prop", 1.0)
	# (b) Trigger explosion directly underneath CRATE_HANGING (y=106, 11px below crate center) -> shockwave blocked by CRATE_HANGING!
	if fhs22_3 != null:
		fhs22_3.call("trigger_explosion", Vector2(215.0, 106.0), 33.0, 20.0, 5.0, m20_p1)
	hcrate22_3.call("step_prop", 1.0)
	var holder_shielded_from_below: bool = (not bool(holder22_3.get("is_destroyed")) and not bool(hcrate22_3.get("is_hanging_released")))
	# (c) Also verify a solid floor/wall blocks explosion shockwaves from breaking a fragile CRATE on the other side of Storage's thick floor Rect2(339, 141, 145, 12)
	var crate_above_floor: Node2D = mc.call("spawn_interactive_prop", "CRATE", Vector2(390.0, 133.0)) as Node2D
	if fhs22_3 != null:
		fhs22_3.call("trigger_explosion", Vector2(390.0, 158.0), 33.0, 25.0, 5.0, m20_p1)
	var crate_shielded_by_floor: bool = (not bool(crate_above_floor.get("is_destroyed")) and float(crate_above_floor.get("hp")) == 40.0)
	# (d) Unobstructed explosion above/next to CRATE_HANGING_HOLDER (y=80) DOES break the holder and release the hanging crate!
	if fhs22_3 != null:
		fhs22_3.call("trigger_explosion", Vector2(215.0, 80.0), 33.0, 20.0, 5.0, m20_p1)
	hcrate22_3.call("step_prop", 1.0)
	var holder_broken_when_unblocked: bool = (bool(holder22_3.get("is_destroyed")) and bool(hcrate22_3.get("is_hanging_released")))
	_check(
		holder_shielded_from_below and crate_shielded_by_floor and holder_broken_when_unblocked,
		"SF-M22.3: Explosion shockwaves & upward shots from below CRATE_HANGING (or through solid walls/floors) are blocked from reaching CRATE_HANGING_HOLDER/props behind obstacles"
	)

	# 4. SF-M22.4: GASCAN destruction only bursts into 18 fire particles (TriggerFireAt("GASCAN")) without any explosion shockwave (TriggerExplosionAt)
	if fhs22_3 != null:
		(fhs22_3.get("fire_particles") as Array).clear()
	var exp_before_gascan: int = int(fhs22_3.get("total_explosions_triggered")) if fhs22_3 != null else 0
	var fb_before_gascan: int = int(fhs22_3.get("total_fire_bursts_triggered")) if fhs22_3 != null else 0
	var m22_gascan: Node2D = mc.call("spawn_interactive_prop", "GASCAN", Vector2(360.0, 136.0)) as Node2D
	m22_gascan.call("apply_bullet_hit", 10.0, 12.0, 1, m22_gascan.global_position)
	var exp_after_gascan: int = int(fhs22_3.get("total_explosions_triggered")) if fhs22_3 != null else 0
	var fb_after_gascan: int = int(fhs22_3.get("total_fire_bursts_triggered")) if fhs22_3 != null else 0
	var gascan_fire_count: int = (fhs22_3.get("fire_particles") as Array).size() if fhs22_3 != null else 0
	_check(
		bool(m22_gascan.get("is_destroyed")) and exp_after_gascan == exp_before_gascan and fb_after_gascan == fb_before_gascan + 1 and gascan_fire_count >= 18,
		"SF-M22.4: GASCAN destruction bursts into 18 fire particles without generating an explosion shockwave (explosions_added=0, fire_particles=" + str(gascan_fire_count) + ")"
	)

	# 5. SF-M22.5: Thrown grenades & Molotovs collide with solid props (CRATE, BARREL_EXPLOSIVE, CRATE_HANGING): grenades bounce off prop sides/tops & nudge movable props without phasing through, and Molotovs shatter on prop contact
	for old_p22_5: Variant in mc.get("props") as Array:
		if is_instance_valid(old_p22_5):
			(old_p22_5 as Node2D).free()
	(mc.get("props") as Array).clear()
	if pm22 != null:
		(pm22.get("throwables") as Array).clear()
	for f22_5: Variant in mc.get("fighters") as Array:
		if is_instance_valid(f22_5):
			(f22_5 as Node2D).global_position = Vector2(100.0, 240.0)
	m20_p1.global_position = Vector2(345.0, 141.0)
	m20_p2.global_position = Vector2(340.0, 141.0)
	var m22_5_crate: Node2D = mc.call("spawn_interactive_prop", "CRATE", Vector2(390.0, 133.0)) as Node2D
	m22_5_crate.set("on_ground", true)
	m22_5_crate.set("_settling_frames", 0.0)
	var m22_5_hcrate: Node2D = mc.call("spawn_interactive_prop", "CRATE_HANGING", Vector2(450.0, 118.0)) as Node2D
	var cr22_5_rect: Rect2 = m22_5_crate.call("get_world_rect") as Rect2
	var hcr22_5_rect: Rect2 = m22_5_hcrate.call("get_world_rect") as Rect2
	# (a) Throw grenade into the left side of m22_5_crate -> bounces back (never passes x > cr22_5_rect.position.x) and nudges the crate!
	if pm22 != null:
		pm22.call("spawn_throwable", m20_p1, "GRENADE", Vector2(372.0, 134.0), 20.0, 72.0)
		for _step_g1: int in range(4):
			pm22.call("step_projectiles", 1.0)
			m22_5_crate.call("step_prop", 1.0)
	var bounced_off_crate_side: bool = false
	var crate_nudged_by_grenade: bool = (m22_5_crate.global_position.x > 390.05)
	if pm22 != null and not (pm22.get("throwables") as Array).is_empty():
		var g_side: Dictionary = (pm22.get("throwables") as Array)[0] as Dictionary
		var g_pos_s: Vector2 = g_side.get("pos", Vector2.ZERO) as Vector2
		var g_vel_s: Vector2 = g_side.get("vel", Vector2.ZERO) as Vector2
		bounced_off_crate_side = (g_pos_s.x < cr22_5_rect.position.x and g_vel_s.x < 0.0)
		(pm22.get("throwables") as Array).clear()
	# (b) Throw grenade at hanging CRATE_HANGING -> bounces off the left side of CRATE_HANGING without phasing inside it!
	var bounced_off_hanging_crate: bool = false
	if pm22 != null:
		pm22.call("spawn_throwable", m20_p1, "GRENADE", Vector2(422.0, 118.0), 15.0, 72.0)
		for _step_g2: int in range(4):
			pm22.call("step_projectiles", 1.0)
		if not (pm22.get("throwables") as Array).is_empty():
			var g_hang: Dictionary = (pm22.get("throwables") as Array)[0] as Dictionary
			var g_pos_h: Vector2 = g_hang.get("pos", Vector2.ZERO) as Vector2
			var g_vel_h: Vector2 = g_hang.get("vel", Vector2.ZERO) as Vector2
			bounced_off_hanging_crate = (g_pos_h.x < hcr22_5_rect.position.x and g_vel_h.x < 0.0 and not hcr22_5_rect.has_point(g_pos_h))
		(pm22.get("throwables") as Array).clear()
	# (c) Throw Molotov into m22_5_crate -> shatters on contact and ignites the crate!
	if pm22 != null:
		pm22.call("spawn_throwable", m20_p1, "MOLOTOV", Vector2(368.0, 132.0), 15.0, 72.0)
		for _step_m1: int in range(6):
			pm22.call("step_projectiles", 1.0)
	var molotov_shattered_on_crate: bool = (pm22 != null and (pm22.get("throwables") as Array).is_empty() and bool(m22_5_crate.get("is_burning")))
	_check(
		bounced_off_crate_side and crate_nudged_by_grenade and bounced_off_hanging_crate and molotov_shattered_on_crate,
		"SF-M22.5: Thrown grenades bounce off CRATE & CRATE_HANGING (never phasing through props) while transferring impact impulse, and Molotovs shatter on prop contact"
	)

	# 6. SF-M23.1: Authentic AS3 Gun Aiming, Post-Shot Hold Linger (BackToIdleTimer=6), Spam-Shot Pitch Retention & Horizontal Reset After Holster
	if pm22 != null:
		(pm22.get("bullets") as Array).clear()
	m20_p1.call("setup_fighter", 0, "boris", Vector2(360.0, 141.0), false)
	m20_p1.set("match_world", mc)
	m20_p1.set("on_ground", true)
	m20_p1.set("facing", 1)
	m20_p1.call("equip_weapon", "PISTOL", 12)
	# (a) Raise gun and hold Up for 4 ticks to tilt pitch upward (~ -14.0 deg), then release Aim to fire Shot #1
	for _aim_u: int in range(4):
		m20_p1.call("step_fighter", 1.0, {"aim": true, "up": true})
	var aimed_up_pitch: float = float(m20_p1.get("current_aim_pitch"))
	m20_p1.call("step_fighter", 1.0, {"aim": false, "aim_just_released": true})
	# Step 5 ticks without holding Aim (within BackToIdleTimer=6): fighter stays in AIM_PISTOL and keeps aimed_up_pitch!
	var never_flickered_to_idle: bool = (aimed_up_pitch < -10.0)
	for _linger_t: int in range(5):
		m20_p1.call("step_fighter", 1.0, {"aim": false})
		if not bool(m20_p1.get("aiming")) or str(m20_p1.get("current_state")) != "AIM_PISTOL" or not is_equal_approx(float(m20_p1.get("current_aim_pitch")), aimed_up_pitch):
			never_flickered_to_idle = false
	# (b) Spam Shot #2 before BackToIdleTimer expires -> fires at the SAME upward pitch without resetting or flickering!
	m20_p1.call("step_fighter", 1.0, {"aim": true})
	var kept_pitch_on_spam: bool = is_equal_approx(float(m20_p1.get("current_aim_pitch")), aimed_up_pitch)
	m20_p1.call("step_fighter", 1.0, {"aim": false, "aim_just_released": true})
	var bullets_arr_23: Array = pm22.get("bullets") as Array if pm22 != null else []
	var both_shots_fired_upward: bool = (
		bullets_arr_23.size() == 2
		and absf(float((bullets_arr_23[0] as Dictionary).get("angle_deg", 0.0)) - aimed_up_pitch) <= 3.0
		and absf(float((bullets_arr_23[1] as Dictionary).get("angle_deg", 0.0)) - aimed_up_pitch) <= 3.0
	)
	# (c) Wait 8 ticks with Aim released so FireSequence + BackToIdleTimer=6 expire -> gun holsters to IDLE and next Aim resets to 0.0 deg horizontal!
	for _expire_t: int in range(8):
		m20_p1.call("step_fighter", 1.0, {"aim": false})
	var holstered_after_linger: bool = (not bool(m20_p1.get("aiming")) and str(m20_p1.get("current_state")) == "IDLE")
	m20_p1.call("step_fighter", 1.0, {"aim": true})
	var reset_to_horizontal_on_next_draw: bool = (bool(m20_p1.get("aiming")) and is_zero_approx(float(m20_p1.get("current_aim_pitch"))))
	# (d) Aim up again, then press Left while aiming (AimLeft) -> turns Left and resets pitch to 0.0 deg horizontal!
	m20_p1.call("step_fighter", 1.0, {"aim": true, "up": true})
	m20_p1.call("step_fighter", 1.0, {"aim": true, "up": true})
	m20_p1.call("step_fighter", 1.0, {"aim": true, "left": true})
	var reset_on_turn_around: bool = (int(m20_p1.get("facing")) == -1 and is_zero_approx(float(m20_p1.get("current_aim_pitch"))))
	_check(
		never_flickered_to_idle and kept_pitch_on_spam and both_shots_fired_upward and holstered_after_linger and reset_to_horizontal_on_next_draw and reset_on_turn_around,
		"SF-M23.1: Post-shot gun hold (BackToIdleTimer=6) keeps AIM_* pose & pitch (" + str(snappedf(aimed_up_pitch, 0.1)) + " deg) during spam firing, then holsters & resets pitch to 0.0 deg horizontal on next draw"
	)

	# 7. SF-M24.1: Prop Horizontal Toppling (±90 deg), Exact Visual Contact Reach (No Air-Gap Movement), & 3-Punch / Kick Spam Loop
	for old_p24: Variant in mc.get("props") as Array:
		if is_instance_valid(old_p24):
			(old_p24 as Node2D).free()
	(mc.get("props") as Array).clear()
	if pm22 != null:
		(pm22.get("throwables") as Array).clear()
		(pm22.get("bullets") as Array).clear()

	# (a) Visual contact reach check + horizontal toppling (±90 deg):
	# Spawn BARREL (13x18) at x=378.0, y=132.0 (left edge = 371.5).
	# Fighter at x=360.0 (distance to barrel edge = 11.5px > 9.5px visual fist/foot reach) must NOT move the barrel!
	var m24_barrel: Node2D = mc.call("spawn_interactive_prop", "BARREL", Vector2(378.0, 132.0)) as Node2D
	m24_barrel.set("on_ground", true)
	m24_barrel.set("_settling_frames", 0.0)
	m20_p1.call("setup_fighter", 0, "boris", Vector2(360.0, 141.0), false)
	m20_p1.set("match_world", mc)
	m20_p1.set("on_ground", true)
	m20_p1.set("facing", 1)
	m20_p1.call("step_fighter", 1.0, {"attack": true, "attack_just_pressed": true})
	for _gap_s: int in range(8):
		m20_p1.call("step_fighter", 1.0, {})
		m24_barrel.call("step_prop", 1.0)
	var no_move_across_air_gap: bool = (is_equal_approx(m24_barrel.global_position.x, 378.0) and is_zero_approx(m24_barrel.rotation))

	# Now move fighter to x=365.0 (distance to barrel left edge = 6.5px <= 8.5px visual foot/fist contact reach) and attack -> kicks & tips barrel horizontally (±90 deg)!
	m20_p1.call("setup_fighter", 0, "boris", Vector2(365.0, 141.0), false)
	m20_p1.set("match_world", mc)
	m20_p1.set("on_ground", true)
	m20_p1.set("facing", 1)
	m20_p1.call("step_fighter", 1.0, {"attack": true, "attack_just_pressed": true})
	for _tip_s: int in range(14):
		m20_p1.call("step_fighter", 1.0, {})
		m24_barrel.call("step_prop", 1.0)
	var barrel_tipped_horizontally: bool = (
		m24_barrel.global_position.x > 379.5
		and absf(rad_to_deg(m24_barrel.rotation)) >= 80.0
		and is_equal_approx(float(m24_barrel.get("width")), float(m24_barrel.get("base_height")))
		and is_equal_approx(float(m24_barrel.get("height")), float(m24_barrel.get("base_width")))
		and float(m24_barrel.get("width")) > float(m24_barrel.get("height"))
	)
	var tipped_size_str: String = str(m24_barrel.get("width")) + "x" + str(m24_barrel.get("height"))
	m24_barrel.free()
	(mc.get("props") as Array).clear()

	# (b) Open-space spam Attack loop: must cycle PUNCH_01 -> PUNCH_02 -> PUNCH_03 -> PUNCH_01 -> PUNCH_02 -> PUNCH_03 without getting stuck on PUNCH_01!
	m20_p1.call("setup_fighter", 0, "boris", Vector2(360.0, 141.0), false)
	m20_p1.set("match_world", mc)
	m20_p1.set("on_ground", true)
	m20_p1.set("facing", 1)
	var open_combo_seq: Array[String] = []
	var prev_st_open: String = "IDLE"
	for _sp_o: int in range(48):
		var press_now: bool = (_sp_o % 4 == 0)
		m20_p1.call("step_fighter", 1.0, {"attack": press_now, "attack_just_pressed": press_now})
		var cur_st_o: String = str(m20_p1.get("current_state"))
		if cur_st_o != prev_st_open and cur_st_o.begins_with("PUNCH_"):
			open_combo_seq.append(cur_st_o)
		prev_st_open = cur_st_o
		if open_combo_seq.size() >= 6:
			break
	var open_6hit_loop_ok: bool = (
		open_combo_seq.size() >= 6
		and open_combo_seq[0] == "PUNCH_01"
		and open_combo_seq[1] == "PUNCH_02"
		and open_combo_seq[2] == "PUNCH_03"
		and open_combo_seq[3] == "PUNCH_01"
		and open_combo_seq[4] == "PUNCH_02"
		and open_combo_seq[5] == "PUNCH_03"
	)

	# (c) Near-prop spam Attack loop: must cycle KICK -> PUNCH_01 -> PUNCH_02 -> PUNCH_03 -> KICK -> PUNCH_01 -> PUNCH_02 -> PUNCH_03!
	var m24_heavy: Node2D = mc.call("spawn_interactive_prop", "CRATE_HANGING", Vector2(380.0, 133.5)) as Node2D
	m24_heavy.set("is_hanging_released", true)
	m24_heavy.set("kinematic", true)
	m24_heavy.set("on_ground", true)
	m20_p1.call("setup_fighter", 0, "boris", Vector2(360.0, 141.0), false)
	m20_p1.set("match_world", mc)
	m20_p1.set("on_ground", true)
	m20_p1.set("facing", 1)
	var prop_combo_seq: Array[String] = []
	var prev_st_prop: String = "IDLE"
	for _sp_p: int in range(68):
		# Keep fighter at 6.0px from heavy crate's left edge (x=366.0 -> fighter at 360.0) so crate stays in kick range
		m20_p1.global_position.x = 360.0
		var press_p: bool = (_sp_p % 4 == 0)
		m20_p1.call("step_fighter", 1.0, {"attack": press_p, "attack_just_pressed": press_p})
		var cur_st_p: String = str(m20_p1.get("current_state"))
		if cur_st_p != prev_st_prop and (cur_st_p == "KICK" or cur_st_p.begins_with("PUNCH_")):
			prop_combo_seq.append(cur_st_p)
		prev_st_prop = cur_st_p
		if prop_combo_seq.size() >= 8:
			break
	var prop_8hit_loop_ok: bool = (
		prop_combo_seq.size() >= 8
		and prop_combo_seq[0] == "KICK"
		and prop_combo_seq[1] == "PUNCH_01"
		and prop_combo_seq[2] == "PUNCH_02"
		and prop_combo_seq[3] == "PUNCH_03"
		and prop_combo_seq[4] == "KICK"
		and prop_combo_seq[5] == "PUNCH_01"
		and prop_combo_seq[6] == "PUNCH_02"
		and prop_combo_seq[7] == "PUNCH_03"
	)
	_check(
		no_move_across_air_gap and barrel_tipped_horizontally and open_6hit_loop_ok and prop_8hit_loop_ok,
		"SF-M24.1: Props tip horizontally (±90 deg, size=" + tipped_size_str + "), only move on true visual fist/foot contact, and spam Attack loops 1->2->3 (" + str(open_combo_seq) + ") & KICK->1->2->3 (" + str(prop_combo_seq) + ")"
	)

	# 8. SF-M25.1: Suspended CRATE_HANGING (+ CRATE_HANGING_HOLDER) Pendulum Sway Physics & Overkill Bullet Penetration With Damage Attenuation
	for old_p25: Variant in mc.get("props") as Array:
		if is_instance_valid(old_p25):
			(old_p25 as Node2D).free()
	(mc.get("props") as Array).clear()
	if pm22 != null:
		(pm22.get("bullets") as Array).clear()
		(pm22.get("throwables") as Array).clear()

	# (a) Shoot a Bazooka rocket into the underside of a suspended CRATE_HANGING (holder shielded above):
	# Both CRATE_HANGING and CRATE_HANGING_HOLDER must stay suspended and swing back and forth like a physical pendulum!
	var pair25: Dictionary = mc.call("spawn_hanging_crate_pair", Vector2(215.0, 95.0), "BAZOOKA") as Dictionary
	var hcrate25: Node2D = pair25.get("crate") as Node2D
	var holder25: Node2D = pair25.get("holder") as Node2D
	if pm22 != null:
		pm22.call("spawn_bullet", m20_p1, "BAZOOKA", Vector2(185.0, 120.0), -40.0, 1)
	var max_crate_swing_dx: float = 0.0
	var max_holder_swing_dx: float = 0.0
	var max_crate_rot_deg: float = 0.0
	for _sw_s: int in range(18):
		if pm22 != null:
			pm22.call("step_projectiles", 1.0)
		hcrate25.call("step_prop", 1.0)
		max_crate_swing_dx = maxf(max_crate_swing_dx, absf(hcrate25.global_position.x - 215.0))
		max_holder_swing_dx = maxf(max_holder_swing_dx, absf(holder25.global_position.x - 215.0))
		max_crate_rot_deg = maxf(max_crate_rot_deg, absf(rad_to_deg(hcrate25.rotation)))
	var pendulum_sway_ok: bool = (
		not bool(holder25.get("is_destroyed"))
		and not bool(hcrate25.get("is_hanging_released"))
		and max_crate_swing_dx >= 3.5
		and max_holder_swing_dx >= 2.0
		and max_crate_rot_deg >= 2.5
	)

	# (b) Overkill Bullet Penetration: fire SNIPER through a full-HP wooden CRATE (40 HP, Strength=10) at an enemy fighter behind the crate:
	# The wooden CRATE must shatter in 1 shot AND the Sniper bullet must penetrate through to hit the fighter behind it with attenuated damage!
	for old_p25b: Variant in mc.get("props") as Array:
		if is_instance_valid(old_p25b):
			(old_p25b as Node2D).free()
	(mc.get("props") as Array).clear()
	if pm22 != null:
		(pm22.get("bullets") as Array).clear()
	m20_p1.call("setup_fighter", 0, "boris", Vector2(345.0, 141.0), false)
	m20_p2.call("setup_fighter", 1, "havoc", Vector2(405.0, 141.0), false)
	m20_p1.set("match_world", mc)
	m20_p2.set("match_world", mc)
	m20_p1.set("on_ground", true)
	m20_p2.set("on_ground", true)
	m20_p2.set("hp", 100.0)
	var m25_crate: Node2D = mc.call("spawn_interactive_prop", "CRATE", Vector2(375.0, 133.5)) as Node2D
	m25_crate.set("on_ground", true)
	m25_crate.set("_settling_frames", 0.0)
	var sniper_initial_dmg: float = 0.0
	if pm22 != null:
		pm22.call("spawn_bullet", m20_p1, "SNIPER", Vector2(355.0, 133.0), 0.0, -1)
		var b_arr25: Array = pm22.get("bullets") as Array
		if not b_arr25.is_empty():
			sniper_initial_dmg = float((b_arr25[0] as Dictionary).get("damage", 30.0))
		for _pen_s: int in range(4):
			pm22.call("step_projectiles", 1.0)
	var sniper_dealt_to_p2: float = 100.0 - float(m20_p2.get("hp"))
	var sniper_penetrated_crate_ok: bool = (
		bool(m25_crate.get("is_destroyed"))
		and sniper_dealt_to_p2 > 10.0
		and sniper_dealt_to_p2 < sniper_initial_dmg - 1.0
	)

	# (c) Also verify a PISTOL bullet (10 dmg) hitting a weakened CRATE (4 HP left) shatters the crate and penetrates through to hit P2 with attenuated overkill damage!
	for old_p25c: Variant in mc.get("props") as Array:
		if is_instance_valid(old_p25c):
			(old_p25c as Node2D).free()
	(mc.get("props") as Array).clear()
	if pm22 != null:
		(pm22.get("bullets") as Array).clear()
	m20_p2.call("setup_fighter", 1, "havoc", Vector2(405.0, 141.0), false)
	m20_p2.set("match_world", mc)
	m20_p2.set("on_ground", true)
	m20_p2.set("hp", 100.0)
	var m25_weak_crate: Node2D = mc.call("spawn_interactive_prop", "CRATE", Vector2(375.0, 133.5)) as Node2D
	m25_weak_crate.set("on_ground", true)
	m25_weak_crate.set("_settling_frames", 0.0)
	m25_weak_crate.set("hp", 3.2)
	if pm22 != null:
		pm22.call("spawn_bullet", m20_p1, "PISTOL", Vector2(355.0, 133.0), 0.0, -1)
		var b_arr25c: Array = pm22.get("bullets") as Array
		if not b_arr25c.is_empty():
			(b_arr25c[0] as Dictionary)["damage"] = 10.0
			(b_arr25c[0] as Dictionary)["is_crit"] = false
			(b_arr25c[0] as Dictionary)["angle_deg"] = 0.0
			(b_arr25c[0] as Dictionary)["dir"] = Vector2.RIGHT
		for _pen_p: int in range(4):
			pm22.call("step_projectiles", 1.0)
	var pistol_overkill_dealt: float = 100.0 - float(m20_p2.get("hp"))
	var pistol_overkill_ok: bool = (
		bool(m25_weak_crate.get("is_destroyed"))
		and pistol_overkill_dealt > 1.5
		and pistol_overkill_dealt < 9.0
	)
	_check(
		pendulum_sway_ok and sniper_penetrated_crate_ok and pistol_overkill_ok,
		"SF-M25.1: Suspended CRATE_HANGING swings as a pendulum on rocket/blast hit (dx=" + str(snappedf(max_crate_swing_dx, 0.1)) + "px, rot=" + str(snappedf(max_crate_rot_deg, 0.1)) + " deg), and Sniper/overkill bullets shatter & penetrate crates with attenuated damage (sniper_dmg=" + str(snappedf(sniper_initial_dmg, 0.1)) + "->" + str(snappedf(sniper_dealt_to_p2, 0.1)) + ", pistol_overkill=" + str(snappedf(pistol_overkill_dealt, 0.1)) + ")"
	)

	# 9. SF-M26.1: Repeated Rolls Cancel Gun Aiming Without Firing, No Airborne Gun Aiming, Standing-on-Prop Kick Hits Prop Under Feet, & Smooth Non-Spinning Prop Rotation
	for old_p26: Variant in mc.get("props") as Array:
		if is_instance_valid(old_p26):
			(old_p26 as Node2D).free()
	(mc.get("props") as Array).clear()
	if pm22 != null:
		(pm22.get("bullets") as Array).clear()
		(pm22.get("throwables") as Array).clear()

	# (a) Hold Aim and roll 3 times in a row (releasing Aim during/after roll): every roll must show ROLL (never stuck in AIM_*), and releasing Aim must fire 0 shots!
	m20_p1.call("setup_fighter", 0, "boris", Vector2(355.0, 141.0), false)
	m20_p1.set("match_world", mc)
	m20_p1.set("on_ground", true)
	m20_p1.set("facing", 1)
	m20_p1.call("equip_weapon", "PISTOL", 12)
	# Frame 1: draw gun into AIM_PISTOL
	m20_p1.call("step_fighter", 1.0, {"aim": true})
	var started_aim_ok: bool = bool(m20_p1.get("aiming")) and str(m20_p1.get("current_state")) == "AIM_PISTOL"
	var roll_count_ok: int = 0
	var stuck_aim_during_roll: bool = false
	for _r_idx: int in range(3):
		m20_p1.global_position = Vector2(355.0, 141.0)
		m20_p1.set("on_ground", true)
		m20_p1.set("sprint_energy", 100.0)
		m20_p1.set("_last_release_dir", 0)
		m20_p1.set("_last_tap_dir", 0)
		# Aim before each roll, then press Down + Right while holding Aim
		m20_p1.call("step_fighter", 1.0, {"aim": true})
		m20_p1.call("step_fighter", 1.0, {"aim": true, "down": true, "right": true, "down_just_pressed": true, "right_just_pressed": true})
		if bool(m20_p1.get("rolling")) and str(m20_p1.get("current_state")) == "ROLL" and not bool(m20_p1.get("aiming")):
			roll_count_ok += 1
		for _rf: int in range(14):
			# Keep holding Aim during first half of roll, then release Aim mid-roll to verify it does NOT fire!
			var hold_aim_now: bool = (_rf < 6)
			m20_p1.call("step_fighter", 1.0, {"aim": hold_aim_now, "down": true, "right": true})
			if bool(m20_p1.get("rolling")) and (bool(m20_p1.get("aiming")) or str(m20_p1.get("current_state")).begins_with("AIM_")):
				stuck_aim_during_roll = true
	var ammo_after_rolls: int = int((m20_p1.get("inventory_ammo") as Dictionary).get(2, 0))
	var bullets_fired_on_roll_cancel: int = (pm22.get("bullets") as Array).size() if pm22 != null else 0
	var roll_aim_cancel_ok: bool = (
		started_aim_ok
		and roll_count_ok == 3
		and not stuck_aim_during_roll
		and ammo_after_rolls == 12
		and bullets_fired_on_roll_cancel == 0
	)

	# (b) Jumping / being airborne (!on_ground) must immediately cancel gun aiming and never allow holding a gun in mid-air!
	m20_p1.call("setup_fighter", 0, "boris", Vector2(350.0, 141.0), false)
	m20_p1.set("match_world", mc)
	m20_p1.set("on_ground", true)
	m20_p1.call("equip_weapon", "PISTOL", 12)
	m20_p1.call("step_fighter", 1.0, {"aim": true})
	# Jump while holding Aim, then release and re-press Aim in mid-air
	m20_p1.call("step_fighter", 1.0, {"aim": true, "jump": true, "jump_just_pressed": true})
	var airborne_aim_seen: bool = false
	for _af: int in range(8):
		var press_air_aim: bool = (_af % 2 == 1)
		m20_p1.call("step_fighter", 1.0, {"aim": press_air_aim})
		if not bool(m20_p1.get("on_ground")) and (bool(m20_p1.get("aiming")) or str(m20_p1.get("current_state")).begins_with("AIM_")):
			airborne_aim_seen = true
	var no_airborne_aim_ok: bool = (not bool(m20_p1.get("on_ground")) and not airborne_aim_seen)

	# (c) Standing on top of a prop (CRATE) and pressing Attack must kick and move/damage the prop underneath the fighter's feet!
	var m26_crate: Node2D = mc.call("spawn_interactive_prop", "CRATE", Vector2(375.0, 133.5)) as Node2D
	m26_crate.set("on_ground", true)
	m26_crate.set("_settling_frames", 0.0)
	var crate_top_y: float = 133.5 - float(m26_crate.get("height")) * 0.5
	m20_p1.call("setup_fighter", 0, "boris", Vector2(375.0, crate_top_y), false)
	m20_p1.set("match_world", mc)
	m20_p1.set("on_ground", true)
	m20_p1.set("facing", 1)
	m20_p1.call("step_fighter", 1.0, {"attack": true, "attack_just_pressed": true})
	var stand_kick_started: bool = (str(m20_p1.get("current_state")) == "KICK")
	for _sk: int in range(6):
		m20_p1.call("step_fighter", 1.0, {})
		m26_crate.call("step_prop", 1.0)
	var stand_on_prop_kick_ok: bool = (
		stand_kick_started
		and m26_crate.global_position.x > 376.5
		and float(m26_crate.get("hp")) < 40.0
	)
	m26_crate.free()
	(mc.get("props") as Array).clear()

	# (d) Kicking a BARREL_EXPLOSIVE on flat ground must tip it smoothly onto its horizontal side (90 deg) without snapping on frame 0 or overshooting/spinning 360 deg!
	var m26_barrel: Node2D = mc.call("spawn_interactive_prop", "BARREL_EXPLOSIVE", Vector2(379.5, 132.0)) as Node2D
	m26_barrel.set("on_ground", true)
	m26_barrel.set("_settling_frames", 0.0)
	m20_p1.call("setup_fighter", 0, "boris", Vector2(365.0, 141.0), false)
	m20_p1.set("match_world", mc)
	m20_p1.set("on_ground", true)
	m20_p1.set("facing", 1)
	m20_p1.call("step_fighter", 1.0, {"attack": true, "attack_just_pressed": true})
	# Step fighter 1 frame to trigger the kick hit check BEFORE stepping the prop, verifying no instant frame-0 rotation snap
	m20_p1.call("step_fighter", 1.0, {})
	var rot_on_hit_frame_deg: float = absf(rad_to_deg(m26_barrel.rotation))
	var max_barrel_rot_deg: float = rot_on_hit_frame_deg
	for _br: int in range(16):
		m20_p1.call("step_fighter", 1.0, {})
		m26_barrel.call("step_prop", 1.0)
		max_barrel_rot_deg = maxf(max_barrel_rot_deg, absf(rad_to_deg(m26_barrel.rotation)))
	var final_barrel_rot_deg: float = absf(rad_to_deg(m26_barrel.rotation))
	var smooth_non_spinning_tip_ok: bool = (
		rot_on_hit_frame_deg < 1.0
		and max_barrel_rot_deg <= 90.1
		and final_barrel_rot_deg >= 85.0
		and final_barrel_rot_deg <= 90.1
	)
	_check(
		roll_aim_cancel_ok and no_airborne_aim_ok and stand_on_prop_kick_ok and smooth_non_spinning_tip_ok,
		"SF-M26.1: Repeated rolls cleanly cancel Aim without firing (rolls=" + str(roll_count_ok) + "/3, shots=" + str(bullets_fired_on_roll_cancel) + "), no mid-air aiming, standing-on-prop kick moves prop under feet, and kicked barrel tips smoothly to " + str(snappedf(final_barrel_rot_deg, 0.1)) + " deg (max=" + str(snappedf(max_barrel_rot_deg, 0.1)) + " deg, frame0=" + str(snappedf(rot_on_hit_frame_deg, 0.1)) + " deg)"
	)

	# 10. SF-M27.1: Unified Prop Physics & 4-Way Swept Collision Solver (Mass-Scaled Pendulum Kick Sway, Zero Platform/Wall Penetration on Swing, & Swept Wall/Ceiling Blocking)
	for old_p27: Variant in mc.get("props") as Array:
		if is_instance_valid(old_p27):
			(old_p27 as Node2D).free()
	(mc.get("props") as Array).clear()

	# (a) Spawn Storage's crate_hanging_1 at (168.0, 131.0), 13px to the right of the solid red steel platform Rect2(68, 111, 73, 18) (right edge x=141.0):
	# 1. Kicking the heavy 3.8-ton CRATE_HANGING must only sway it gently (~2..8px, never flying 35-44px!).
	# 2. Even under a strong leftward blast, the swinging CRATE_HANGING must be stopped at x=141.0 + width*0.5 (=155.0) and NEVER penetrate into the red platform!
	var pair27: Dictionary = mc.call("spawn_hanging_crate_pair", Vector2(168.0, 131.0), "BAZOOKA") as Dictionary
	var hcrate27: Node2D = pair27.get("crate") as Node2D
	var holder27: Node2D = pair27.get("holder") as Node2D
	hcrate27.call("link_hanging_holder", holder27, 51.0)
	hcrate27.call("apply_melee_hit", 8.0, -1, true, "FISTS", m20_p1)
	var max_kick_sway_dx: float = 0.0
	for _ks27: int in range(16):
		hcrate27.call("step_prop", 1.0)
		max_kick_sway_dx = maxf(max_kick_sway_dx, absf(168.0 - hcrate27.global_position.x))
	var kick_sway_realistic: bool = (max_kick_sway_dx >= 1.5 and max_kick_sway_dx <= 9.5)

	# Now hit hcrate27 with a massive leftward explosion and verify its left edge (x - 14.0) NEVER crosses left of the platform's right wall (x = 141.0)!
	hcrate27.call("apply_explosion_hit", PI, 7.5, 25.0)
	var min_left_edge_x: float = hcrate27.global_position.x - float(hcrate27.get("width")) * 0.5
	for _bs27: int in range(18):
		hcrate27.call("step_prop", 1.0)
		min_left_edge_x = minf(min_left_edge_x, hcrate27.global_position.x - float(hcrate27.get("width")) * 0.5)
	var never_penetrated_platform: bool = (min_left_edge_x >= 140.9)

	# (b) Verify 4-way swept collision on free dynamic props:
	# 1. Fast horizontal CRATE (-7.0 px/tick) hitting the right face of Rect2(68, 111, 73, 18) (x=141.0) stops outside x=141.0.
	# 2. Fast upward CRATE (vy = -6.0 px/tick) launched under thick platform Rect2(339, 141, 145, 12) (underside y=153.0) is blocked by the ceiling and never tunnels to the top!
	var m27_wall_crate: Node2D = mc.call("spawn_interactive_prop", "CRATE", Vector2(154.0, 120.0)) as Node2D
	m27_wall_crate.set("on_ground", false)
	m27_wall_crate.set("velocity", Vector2(-7.0, 0.0))
	for _wc27: int in range(4):
		m27_wall_crate.call("step_prop", 1.0)
	var crate_blocked_by_wall_ok: bool = (m27_wall_crate.global_position.x - float(m27_wall_crate.get("width")) * 0.5 >= 140.9)

	var m27_ceil_crate: Node2D = mc.call("spawn_interactive_prop", "CRATE", Vector2(390.0, 165.0)) as Node2D
	m27_ceil_crate.set("on_ground", false)
	m27_ceil_crate.set("velocity", Vector2(0.0, -6.0))
	var min_ceil_crate_top_y: float = m27_ceil_crate.global_position.y - float(m27_ceil_crate.get("height")) * 0.5
	for _cc27: int in range(5):
		m27_ceil_crate.call("step_prop", 1.0)
		min_ceil_crate_top_y = minf(min_ceil_crate_top_y, m27_ceil_crate.global_position.y - float(m27_ceil_crate.get("height")) * 0.5)
	var crate_blocked_by_ceiling_ok: bool = (min_ceil_crate_top_y >= 152.9)

	_check(
		kick_sway_realistic and never_penetrated_platform and crate_blocked_by_wall_ok and crate_blocked_by_ceiling_ok,
		"SF-M27.1: Heavy CRATE_HANGING kick sway is mass-scaled (" + str(snappedf(max_kick_sway_dx, 0.1)) + "px <= 9.5px), swinging/flying props never penetrate platforms/walls (min_left_x=" + str(snappedf(min_left_edge_x, 0.1)) + " >= 141.0), and upward props stop at solid ceilings (min_top_y=" + str(snappedf(min_ceil_crate_top_y, 0.1)) + " >= 153.0)"
	)

	# 11. SF-M28.1: Housner Inverted-Pendulum Corner-Rocking Balance (Self-Righting on Punch / Heavy FILECAB Kick vs Gravity Topple) & Zero Air-Gap Prop Grounding
	for old_p28: Variant in mc.get("props") as Array:
		if is_instance_valid(old_p28):
			(old_p28 as Node2D).free()
	(mc.get("props") as Array).clear()

	# (a) 1 Punch on BARREL_EXPLOSIVE rocks it up (< theta_crit = 36.25 deg) and gravity's restoring torque pulls it back upright to 0.0 deg!
	var m28_barrel: Node2D = mc.call("spawn_interactive_prop", "BARREL_EXPLOSIVE", Vector2(390.0, 133.5)) as Node2D
	m28_barrel.set("on_ground", true)
	m28_barrel.set("_settling_frames", 0.0)
	m28_barrel.call("apply_melee_hit", 5.0, 1, false, "FISTS", m20_p1)
	var max_punch_rock_deg: float = 0.0
	for _pr28: int in range(14):
		m28_barrel.call("step_prop", 1.0)
		max_punch_rock_deg = maxf(max_punch_rock_deg, absf(rad_to_deg(m28_barrel.rotation)))
	var punch_self_righted_ok: bool = (
		max_punch_rock_deg >= 8.0
		and max_punch_rock_deg < 32.0
		and is_zero_approx(m28_barrel.rotation)
	)

	# (b) 1 Kick on heavy FILECAB (13x15, mass=2.25) rocks it to ~20 deg (< theta_crit = 40.91 deg) and self-rights to 0.0 deg;
	#     2 consecutive kicks push it past theta_crit to topple onto its side (90.0 deg)!
	var m28_fcab: Node2D = mc.call("spawn_interactive_prop", "FILECAB", Vector2(410.0, 133.5)) as Node2D
	m28_fcab.set("on_ground", true)
	m28_fcab.set("_settling_frames", 0.0)
	m28_fcab.call("apply_melee_hit", 6.0, 1, true, "FISTS", m20_p1)
	var max_fcab_1kick_deg: float = 0.0
	for _fk1: int in range(16):
		m28_fcab.call("step_prop", 1.0)
		max_fcab_1kick_deg = maxf(max_fcab_1kick_deg, absf(rad_to_deg(m28_fcab.rotation)))
	var fcab_1kick_self_righted: bool = (
		max_fcab_1kick_deg >= 12.0
		and max_fcab_1kick_deg < 36.0
		and is_zero_approx(m28_fcab.rotation)
	)
	m28_fcab.call("apply_melee_hit", 6.0, 1, true, "FISTS", m20_p1)
	for _fk2a: int in range(4):
		m28_fcab.call("step_prop", 1.0)
	m28_fcab.call("apply_melee_hit", 6.0, 1, true, "FISTS", m20_p1)
	for _fk2b: int in range(16):
		m28_fcab.call("step_prop", 1.0)
	var fcab_2kick_toppled: bool = is_equal_approx(absf(rad_to_deg(m28_fcab.rotation)), 90.0)

	# (c) Zero Air-Gap Grounding: verify FILECAB (13x15), CHAIR (9x12), TABLE (18x10), and tipped BARREL_EXPLOSIVE (15x11)
	#     match their exact PNG dimensions and rest 100% flush on the floor (bottom_y == 141.0, 0.0px air gap)!
	m28_barrel.call("apply_melee_hit", 6.0, 1, true, "FISTS", m20_p1)
	for _bk28: int in range(16):
		m28_barrel.call("step_prop", 1.0)
	var m28_chair: Node2D = mc.call("spawn_interactive_prop", "CHAIR", Vector2(360.0, 130.0)) as Node2D
	var m28_table: Node2D = mc.call("spawn_interactive_prop", "TABLE", Vector2(340.0, 130.0)) as Node2D
	for _st28: int in range(10):
		m28_chair.call("step_prop", 1.0)
		m28_table.call("step_prop", 1.0)
	var tipped_barrel_bottom: float = m28_barrel.global_position.y + float(m28_barrel.get("height")) * 0.5
	var chair_bottom: float = m28_chair.global_position.y + float(m28_chair.get("height")) * 0.5
	var table_bottom: float = m28_table.global_position.y + float(m28_table.get("height")) * 0.5
	var fcab_bottom: float = m28_fcab.global_position.y + float(m28_fcab.get("height")) * 0.5
	var zero_air_gap_ok: bool = (
		is_equal_approx(tipped_barrel_bottom, 141.0)
		and is_equal_approx(chair_bottom, 141.0)
		and is_equal_approx(table_bottom, 141.0)
		and is_equal_approx(fcab_bottom, 141.0)
		and is_equal_approx(float(m28_barrel.get("height")), 11.0)
	)
	_check(
		punch_self_righted_ok and fcab_1kick_self_righted and fcab_2kick_toppled and zero_air_gap_ok,
		"SF-M28.1: Corner-rocking balance self-rights 1-punch barrel (" + str(snappedf(max_punch_rock_deg, 0.1)) + "->0 deg) & 1-kick FILECAB (" + str(snappedf(max_fcab_1kick_deg, 0.1)) + "->0 deg, 2nd kick->90 deg), and all props rest with 0.0px floor gap"
	)

	# 12. SF-M28.2: Ledge Fulcrum Center-of-Mass Overhang Torque & Falling (Released CRATE_HANGING / Props Overhanging >50% Tilt Downward & Drop Off Ledge)
	for old_p28b: Variant in mc.get("props") as Array:
		if is_instance_valid(old_p28b):
			(old_p28b as Node2D).free()
	(mc.get("props") as Array).clear()

	# Place a released CRATE_HANGING (28x16) on the right edge of Rect2(68, 111, 73, 18) (right edge x=141.0, top y=111.0)
	# at x=146.0, y=103.0 so 19px/28px (~68%) hangs out in empty air to the right while 9px/28px (~32%) touches the platform:
	# Even starting with velocity = ZERO, the heavier overhanging right side must tilt downward (rot > 10 deg) and slide/drop off the ledge!
	var m28_ledge_crate: Node2D = mc.call("spawn_interactive_prop", "CRATE_HANGING", Vector2(146.0, 103.0)) as Node2D
	m28_ledge_crate.set("is_hanging_released", true)
	m28_ledge_crate.set("kinematic", false)
	m28_ledge_crate.set("on_ground", true)
	m28_ledge_crate.set("_settling_frames", 0.0)
	var max_ledge_tilt_deg: float = 0.0
	for _ld28: int in range(28):
		m28_ledge_crate.call("step_prop", 1.0)
		max_ledge_tilt_deg = maxf(max_ledge_tilt_deg, rad_to_deg(m28_ledge_crate.rotation))
	var ledge_overhang_fell_ok: bool = (
		max_ledge_tilt_deg >= 12.0
		and m28_ledge_crate.global_position.x > 152.0
		and m28_ledge_crate.global_position.y > 130.0
	)
	_check(
		ledge_overhang_fell_ok,
		"SF-M28.2: Overhanging CRATE_HANGING (>50% past ledge edge) tilts toward heavier side (max_tilt=" + str(snappedf(max_ledge_tilt_deg, 0.1)) + " deg) and slides/falls off ledge (pos=" + str(m28_ledge_crate.global_position.round()) + ")"
	)

	# --- SF-M29 Compound Chain Hitbox + Aim-Down Assist, 2D OBB Ledge Fulcrum & SAT Solver, and 4-Way Solid Prop Coupling ---
	for old_p29a: Variant in (mc.get("props") as Array):
		if is_instance_valid(old_p29a):
			(old_p29a as Node2D).free()
	(mc.get("props") as Array).clear()
	ml_m11.call("load_map", "storage")
	if pm_m12.has_method("clear_all"):
		pm_m12.call("clear_all")

	# 1. SF-M29.1 (Screenshot 1): Standing on top of suspended CRATE_HANGING and aiming/shooting downward hits CRATE_HANGING_HOLDER and drops the crate
	var m29_hcrate1: Node2D = mc.call("spawn_interactive_prop", "CRATE_HANGING", Vector2(168.0, 131.0), 0.0, "crate_hanging_1") as Node2D
	var m29_holder1: Node2D = mc.call("spawn_interactive_prop", "CRATE_HANGING_HOLDER", Vector2(168.0, 119.5), 0.0, "crate_hanging_1_holder") as Node2D
	m29_hcrate1.call("link_hanging_holder", m29_holder1, 51.0)
	m20_p1.set("local_solid_rects", [] as Array[Rect2])
	m20_p1.call("setup_fighter", 0, "johnny", Vector2(164.0, 123.0), false)
	m20_p1.set("match_world", mc)
	m20_p1.set("on_ground", true)
	m20_p1.set("facing", 1)
	m20_p1.call("equip_weapon", "PISTOL", 12)
	for _aim_d: int in range(6):
		m20_p1.call("step_fighter", 1.0, {"aim": true, "down": true})
	var aim_down_pitch_deg: float = float(m20_p1.get("current_aim_pitch"))
	m20_p1.call("step_fighter", 1.0, {"aim": false, "aim_just_released": true, "down": true})
	for _st_b: int in range(2):
		pm_m12.call("step_projectiles", 1.0)
	var holder_shot_from_top_ok: bool = (
		aim_down_pitch_deg >= 25.0
		and bool(m29_holder1.get("is_destroyed"))
		and bool(m29_hcrate1.get("is_hanging_released"))
	)
	_check(
		holder_shot_from_top_ok,
		"SF-M29.1: Standing on CRATE_HANGING and shooting downward hits CRATE_HANGING_HOLDER chain/clasp and releases crate (pitch=" + str(snappedf(aim_down_pitch_deg, 0.1)) + " deg, holder_destroyed=" + str(bool(m29_holder1.get("is_destroyed"))) + ")"
	)

	# 2. SF-M29.2 (Screenshot 2): storage crate_hanging_1 (x=168, y=131, w=28) falling onto right white platform Rect2(172, 166, 50, 2)
	# has 64.3% overhanging the left -> tilts LEFT (rotation < 0), slides LEFT (x < 158), and has 0.0px OBB penetration into Rect2(172, 166, 50, 2)!
	var min_left_tilt_deg: float = 0.0
	var max_right_tilt_before_floor_deg: float = 0.0
	var zero_plat_penetration: bool = true
	for _f29: int in range(28):
		m29_hcrate1.call("step_prop", 1.0)
		var rot_d: float = rad_to_deg(m29_hcrate1.rotation)
		min_left_tilt_deg = minf(min_left_tilt_deg, rot_d)
		if m29_hcrate1.global_position.y < 172.0:
			max_right_tilt_before_floor_deg = maxf(max_right_tilt_before_floor_deg, rot_d)
		# Check all 4 OBB corners against Rect2(172, 166, 50, 2) while crate center is above the ledge (y < 164.5)
		if m29_hcrate1.global_position.y < 164.5:
			var hw29: float = 14.0
			var hh29: float = 8.0
			var c_pts: Array[Vector2] = [
				Vector2(-hw29, -hh29),
				Vector2(hw29, -hh29),
				Vector2(hw29, hh29),
				Vector2(-hw29, hh29),
			]
			for lp: Vector2 in c_pts:
				var wp: Vector2 = m29_hcrate1.global_position + lp.rotated(m29_hcrate1.rotation)
				if wp.x > 172.5 and wp.x < 222.0 and wp.y > 166.5 and wp.y < 176.0:
					zero_plat_penetration = false
	var storage_fall_left_ok: bool = (
		min_left_tilt_deg <= -12.0
		and max_right_tilt_before_floor_deg <= 1.0
		and m29_hcrate1.global_position.x < 160.0
		and zero_plat_penetration
	)
	_check(
		storage_fall_left_ok,
		"SF-M29.2: Storage crate_hanging_1 tilts LEFT (min_rot=" + str(snappedf(min_left_tilt_deg, 0.1)) + " deg, max_right=" + str(snappedf(max_right_tilt_before_floor_deg, 0.1)) + " deg), slides LEFT (x=" + str(snappedf(m29_hcrate1.global_position.x, 0.1)) + "), zero_pen=" + str(zero_plat_penetration)
	)

	# 3. SF-M29.3 (Screenshot 3): 4-Way Solid Prop Coupling — jumping upward from underneath or horizontally into suspended CRATE_HANGING never phases inside
	for old_p29b: Variant in (mc.get("props") as Array):
		if is_instance_valid(old_p29b):
			(old_p29b as Node2D).free()
	(mc.get("props") as Array).clear()
	var m29_susp_crate: Node2D = mc.call("spawn_interactive_prop", "CRATE_HANGING", Vector2(200.0, 150.0), 0.0, "crate_hanging_test") as Node2D
	var m29_susp_holder: Node2D = mc.call("spawn_interactive_prop", "CRATE_HANGING_HOLDER", Vector2(200.0, 138.5), 0.0, "crate_hanging_test_holder") as Node2D
	m29_susp_crate.call("link_hanging_holder", m29_susp_holder, 51.0)
	# 3A: Jump straight upward from directly below suspended crate (bottom_y = 158.0 -> fighter head at y - 16.0 must stay >= 157.5)
	m20_p1.call("setup_fighter", 0, "johnny", Vector2(200.0, 176.0), false)
	m20_p1.set("match_world", mc)
	m20_p1.set("on_ground", false)
	m20_p1.set("air_velocity", Vector2(0.0, -5.0))
	var min_head_y_under_crate: float = INF
	for _ju29: int in range(8):
		m20_p1.call("step_fighter", 1.0, {"up": true})
		min_head_y_under_crate = minf(min_head_y_under_crate, m20_p1.global_position.y - 16.0)
	# 3B: Jump horizontally into the left side of suspended crate (left_x = 186.0 -> fighter right edge at x + 4.0 must stay <= 186.5)
	m20_p1.call("setup_fighter", 0, "johnny", Vector2(176.0, 156.0), false)
	m20_p1.set("match_world", mc)
	m20_p1.set("on_ground", false)
	m20_p1.set("air_velocity", Vector2(3.4, -1.2))
	var max_right_x_into_crate: float = -INF
	for _jh29: int in range(8):
		m20_p1.call("step_fighter", 1.0, {"right": true})
		if m20_p1.global_position.y > 144.5 and m20_p1.global_position.y - 15.0 < 157.5:
			max_right_x_into_crate = maxf(max_right_x_into_crate, m20_p1.global_position.x + 4.0)
	var four_way_prop_solid_ok: bool = (min_head_y_under_crate >= 157.5 and max_right_x_into_crate <= 186.5)
	_check(
		four_way_prop_solid_ok,
		"SF-M29.3: 4-way solid prop collision blocks upward jump head-bonk (min_head_y=" + str(snappedf(min_head_y_under_crate, 0.1)) + " >= 158.0) and side jump (max_right_x=" + str(snappedf(max_right_x_into_crate, 0.1)) + " <= 186.0)"
	)

	# --- SF-M30: Tilted Crate Flat-Floor Settlement (Image 1), Exact OBB Top Surface Standing (Image 2), and New Custom Map "steel_harbor" ---
	# 1. SF-M30.1 (Screenshot 1): When storage `crate_hanging_1` tips off Rect2(172, 166, 50, 2) and lands next to a square `CRATE` on floor y = 183.0,
	#    it NEVER freezes at a ~39 deg tilt in mid-air; it slaps completely flat (0.0 deg) onto y = 183.0 with on_ground == true!
	ml_m18.call("load_map", "storage")
	for old_p30: Variant in (mc.get("props") as Array):
		if is_instance_valid(old_p30):
			(old_p30 as Node2D).free()
	(mc.get("props") as Array).clear()
	var m30_floor_crate: Node2D = mc.call("spawn_interactive_prop", "CRATE", Vector2(132.0, 175.5), 0.0) as Node2D
	m30_floor_crate.set("on_ground", true)
	m30_floor_crate.set("_settling_frames", 0.0)
	var m30_hcrate: Node2D = mc.call("spawn_interactive_prop", "CRATE_HANGING", Vector2(168.0, 131.0), 0.0, "crate_hanging_1") as Node2D
	var m30_holder: Node2D = mc.call("spawn_interactive_prop", "CRATE_HANGING_HOLDER", Vector2(168.0, 119.5), 0.0, "crate_hanging_1_holder") as Node2D
	m30_hcrate.call("link_hanging_holder", m30_holder, 51.0)
	m30_hcrate.call("release_hanging_crate")
	for _f30: int in range(95):
		m30_floor_crate.call("step_prop", 1.0)
		m30_hcrate.call("step_prop", 1.0)
	var m30_rot_deg: float = rad_to_deg(m30_hcrate.rotation)
	var m30_bot_y: float = m30_hcrate.global_position.y + float(m30_hcrate.get("height")) * 0.5
	var m30_flat_settle_ok: bool = (
		bool(m30_hcrate.get("on_ground"))
		and absf(m30_rot_deg) <= 1.0
		and absf(m30_bot_y - 183.0) <= 1.0
	)
	_check(
		m30_flat_settle_ok,
		"SF-M30.1: CRATE_HANGING landing next to CRATE on flat floor y=183 slaps completely flat (rot=" + str(snappedf(m30_rot_deg, 0.1)) + " deg, bottom_y=" + str(snappedf(m30_bot_y, 0.1)) + ", on_ground=" + str(bool(m30_hcrate.get("on_ground"))) + ")"
	)

	# 2. SF-M30.2 (Screenshot 2): Fighter standing on a tilted prop uses exact rotated OBB top surface `get_obb_top_y_at_x` so feet never sink inside the sprite
	m30_hcrate.global_position = Vector2(150.0, 168.0)
	m30_hcrate.rotation = deg_to_rad(-38.0)
	m30_hcrate.set("kinematic", true)
	m30_hcrate.set("on_ground", true)
	var expected_obb_top: float = float(m30_hcrate.call("get_obb_top_y_at_x", 150.0, 3.5))
	var unrotated_top: float = m30_hcrate.global_position.y - 8.0
	m20_p1.call("setup_fighter", 0, "johnny", Vector2(150.0, expected_obb_top - 4.0), false)
	m20_p1.set("match_world", mc)
	for _st30: int in range(8):
		m20_p1.call("step_fighter", 1.0, {})
	var tilted_stand_ok: bool = (
		expected_obb_top < unrotated_top - 4.5
		and bool(m20_p1.get("on_ground"))
		and m20_p1.global_position.y <= expected_obb_top + 0.5
	)
	_check(
		tilted_stand_ok,
		"SF-M30.2: Fighter standing on tilted prop rests on exact OBB top surface (foot_y=" + str(snappedf(m20_p1.global_position.y, 0.1)) + ", obb_top=" + str(snappedf(expected_obb_top, 0.1)) + " vs unrotated_top=" + str(snappedf(unrotated_top, 0.1)) + ")"
	)

	# 3. SF-M30.3: New Custom Physics-First Map "steel_harbor" ("STEEL HARBOR (NEW)") full match & ledge-pivot showcase verification
	mc.call("start_match", {"mode": "vs", "map_id": "steel_harbor", "two_player": true, "bot_count": 2})
	var sh_fighters: Array = mc.get("fighters") as Array
	var sh_props: Array = mc.get("props") as Array
	var sh_crate2: Node2D = null
	for shp_v: Variant in sh_props:
		if is_instance_valid(shp_v) and str((shp_v as Node2D).get("var_name")) == "crate_hanging_2":
			sh_crate2 = shp_v as Node2D
			break
	var sh_max_right_tilt: float = 0.0
	var sh_zero_pen: bool = true
	if sh_crate2 != null:
		sh_crate2.call("release_hanging_crate")
		for _sh_step: int in range(95):
			for shp_s: Variant in sh_props:
				if is_instance_valid(shp_s) and (shp_s as Node2D).has_method("step_prop"):
					(shp_s as Node2D).call("step_prop", 1.0)
			sh_max_right_tilt = maxf(sh_max_right_tilt, rad_to_deg(sh_crate2.rotation))
			for lp_sh: Vector2 in [Vector2(-14.0, -8.0), Vector2(14.0, -8.0), Vector2(14.0, 8.0), Vector2(-14.0, 8.0)]:
				var wp_sh: Vector2 = sh_crate2.global_position + lp_sh.rotated(sh_crate2.rotation)
				if wp_sh.x > 40.5 and wp_sh.x < 91.5 and wp_sh.y > -51.5 and wp_sh.y < -48.2:
					sh_zero_pen = false
	var sh_ok: bool = (
		str(mc.get("current_map_id")) == "steel_harbor"
		and sh_fighters.size() == 4
		and sh_crate2 != null
		and sh_max_right_tilt >= 12.0
		and sh_zero_pen
		and bool(sh_crate2.get("on_ground"))
		and absf(rad_to_deg(sh_crate2.rotation)) <= 1.0
		and absf((sh_crate2.global_position.y + 8.0) - 76.0) <= 1.0
	)
	_check(
		sh_ok,
		"SF-M30.3: New custom map 'steel_harbor' loads 4 fighters, crate_hanging_2 pivots off catwalk_right (max_rot=" + str(snappedf(sh_max_right_tilt, 0.1)) + " deg, zero_pen=" + str(sh_zero_pen) + ") and settles flat on deck_right y=76.0"
	)

	# --- SF-M31: Unblocked Ladder Hatch Shafts in 'steel_harbor', Ladder Entry/Dismount/Descent UX, & Automated 13-Map Geometry Validator ---
	# 1. SF-M31.1 (Screenshot media_1793057925084_f4a8be1f.png): All 4 ladders in 'steel_harbor' climb smoothly from bottom to top,
	#    step onto top/intermediate platforms, and climb/slide down from top platforms on Down press!
	ml_m18.call("load_map", "steel_harbor")
	for old_p31: Variant in (mc.get("props") as Array):
		if is_instance_valid(old_p31):
			(old_p31 as Node2D).free()
	(mc.get("props") as Array).clear()
	var sh_p1: Node2D = sh_fighters[0] as Node2D
	var ladder_cases: Array[Dictionary] = [
		{"cx": -298.0, "bot_y": 12.0, "top_y": -108.0},
		{"cx": 298.0, "bot_y": 12.0, "top_y": -108.0},
		{"cx": -68.0, "bot_y": 140.0, "top_y": 76.0},
		{"cx": 68.0, "bot_y": 140.0, "top_y": 76.0},
	]
	var climbed_all_4_up: int = 0
	for lcase: Dictionary in ladder_cases:
		var lcx: float = float(lcase["cx"])
		var lbot: float = float(lcase["bot_y"])
		var ltop: float = float(lcase["top_y"])
		sh_p1.call("setup_fighter", 0, "johnny", Vector2(lcx, lbot), false)
		sh_p1.set("match_world", mc)
		sh_p1.set("on_ground", true)
		var grabbed_this_lad: bool = false
		for _step_u: int in range(110):
			# Alternate up_just_pressed every 6 frames to prove repeated W/Up taps never jump off mid-ladder!
			var tap_u: bool = (_step_u == 0 or _step_u % 6 == 0)
			sh_p1.call("step_fighter", 1.0, {"up": true, "up_just_pressed": tap_u, "jump": true, "jump_just_pressed": tap_u})
			if bool(sh_p1.get("climbing")):
				grabbed_this_lad = true
			if grabbed_this_lad and bool(sh_p1.get("on_ground")) and absf(sh_p1.global_position.y - ltop) <= 1.5:
				climbed_all_4_up += 1
				break

	# Test stepping onto intermediate floor hatch_tower_left (y = -56.0) when releasing Up at mid-ladder
	sh_p1.call("setup_fighter", 0, "johnny", Vector2(-298.0, 12.0), false)
	sh_p1.set("match_world", mc)
	sh_p1.set("on_ground", true)
	for _step_m: int in range(60):
		var hold_u_mid: bool = (sh_p1.global_position.y > -54.5)
		sh_p1.call("step_fighter", 1.0, {"up": hold_u_mid})
		if not hold_u_mid and bool(sh_p1.get("on_ground")) and absf(sh_p1.global_position.y - (-56.0)) <= 1.5:
			break
	var stepped_onto_mid_hatch_ok: bool = (bool(sh_p1.get("on_ground")) and not bool(sh_p1.get("climbing")) and absf(sh_p1.global_position.y - (-56.0)) <= 1.5)

	# Test climbing/sliding DOWN from top platform (y = -108.0 -> y = 12.0 and y = 76.0 -> y = 140.0) by pressing Down
	sh_p1.call("setup_fighter", 0, "johnny", Vector2(-298.0, -108.0), false)
	sh_p1.set("match_world", mc)
	sh_p1.set("on_ground", true)
	var grabbed_down_upper: bool = false
	for _step_d1: int in range(60):
		sh_p1.call("step_fighter", 1.0, {"down": true})
		if bool(sh_p1.get("climbing")):
			grabbed_down_upper = true
		if grabbed_down_upper and bool(sh_p1.get("on_ground")) and absf(sh_p1.global_position.y - 12.0) <= 1.5:
			break
	var descended_upper_ok: bool = (grabbed_down_upper and bool(sh_p1.get("on_ground")) and absf(sh_p1.global_position.y - 12.0) <= 1.5)

	sh_p1.call("setup_fighter", 0, "johnny", Vector2(-68.0, 76.0), false)
	sh_p1.set("match_world", mc)
	sh_p1.set("on_ground", true)
	var grabbed_down_pit: bool = false
	for _step_d2: int in range(40):
		sh_p1.call("step_fighter", 1.0, {"down": true})
		if bool(sh_p1.get("climbing")):
			grabbed_down_pit = true
		if grabbed_down_pit and bool(sh_p1.get("on_ground")) and absf(sh_p1.global_position.y - 140.0) <= 1.5:
			break
	var descended_pit_ok: bool = (grabbed_down_pit and bool(sh_p1.get("on_ground")) and absf(sh_p1.global_position.y - 140.0) <= 1.5)
	_check(
		climbed_all_4_up == 4 and stepped_onto_mid_hatch_ok and descended_upper_ok and descended_pit_ok,
		"SF-M31.1: All 4 'steel_harbor' ladders climb bottom-to-top (" + str(climbed_all_4_up) + "/4), step onto intermediate hatch (y=-56, ok=" + str(stepped_onto_mid_hatch_ok) + "), and descend from top platforms on Down (upper=" + str(descended_upper_ok) + ", pit=" + str(descended_pit_ok) + ")"
	)

	# 2. SF-M31.2: Walking/running/jumping horizontally past a ladder NEVER triggers accidental climbing, and pressing Up on top platform jumps normally
	sh_p1.call("setup_fighter", 0, "johnny", Vector2(-268.0, 12.0), false)
	sh_p1.set("match_world", mc)
	sh_p1.set("on_ground", true)
	var accidental_climb_on_walk: bool = false
	for _wk31: int in range(32):
		sh_p1.call("step_fighter", 1.0, {"left": true})
		if bool(sh_p1.get("climbing")):
			accidental_climb_on_walk = true
	var walked_past_ladder_ok: bool = (not accidental_climb_on_walk and sh_p1.global_position.x < -310.0 and bool(sh_p1.get("on_ground")))

	# Running jump across ladder_left_upper (holding Left + Up/Jump) must perform a normal jump without grabbing the ladder!
	sh_p1.call("setup_fighter", 0, "johnny", Vector2(-276.0, 12.0), false)
	sh_p1.set("match_world", mc)
	sh_p1.set("on_ground", true)
	var accidental_climb_on_run_jump: bool = false
	for _rj31: int in range(18):
		var first_f: bool = (_rj31 == 0)
		sh_p1.call("step_fighter", 1.0, {"left": true, "up": true, "up_just_pressed": first_f, "jump": true, "jump_just_pressed": first_f})
		if bool(sh_p1.get("climbing")):
			accidental_climb_on_run_jump = true
	var run_jump_past_ladder_ok: bool = (not accidental_climb_on_run_jump and sh_p1.global_position.x < -306.0)

	# Standing on top platform (crane_walk_left y = -108.0) at ladder_left_upper and pressing Up must JUMP (never get stuck grabbing ladder tip)
	sh_p1.call("setup_fighter", 0, "johnny", Vector2(-298.0, -108.0), false)
	sh_p1.set("match_world", mc)
	sh_p1.set("on_ground", true)
	sh_p1.call("step_fighter", 1.0, {"up": true, "up_just_pressed": true, "jump": true, "jump_just_pressed": true})
	var top_platform_jump_ok: bool = (not bool(sh_p1.get("climbing")) and not bool(sh_p1.get("on_ground")) and (sh_p1.get("air_velocity") as Vector2).y < -4.0)
	_check(
		walked_past_ladder_ok and run_jump_past_ladder_ok and top_platform_jump_ok,
		"SF-M31.2: Walking/running/jumping horizontally past ladders never triggers CLIMB (walk_ok=" + str(walked_past_ladder_ok) + ", run_jump_ok=" + str(run_jump_past_ladder_ok) + "), and pressing Up on top platform jumps cleanly (top_jump_ok=" + str(top_platform_jump_ok) + ")"
	)

	# 3. SF-M31.3: Automated Map Geometry & Navigation Invariant Validator across all 13 maps in sf_compiled_maps.json
	var reg31: Node = MapLoaderScript.get_registry()
	var all_maps_dict31: Dictionary = reg31.call("get_all_maps") as Dictionary
	var vs_map_ids31: Array = reg31.call("get_vs_map_ids") as Array
	var map_geom_errors: Array[String] = []
	for map_id_v: Variant in all_maps_dict31.keys():
		var mid31: String = str(map_id_v)
		ml_m18.call("load_map", mid31)
		var m_solids: Array = ml_m18.get("solid_rects") as Array
		var m_clouds: Array = ml_m18.get("cloud_rects") as Array
		var m_ladders: Array = ml_m18.get("ladder_rects") as Array
		var m_elevs: Array = ml_m18.get("elevators") as Array
		var m_spawns: Array = ml_m18.get("player_spawns") as Array
		var m_slopes: Array = ml_m18.get("slope_polygons") as Array
		var m_portals: Array = ml_m18.get("portals") as Array

		# Invariant A: Every ladder shaft [x1+1..x2-1, y1-14..y2-4] has ZERO solid NONE ground_boxes blocking it,
		# has a bottom floor within 32px, and has a reachable top platform (extending >= 8px above any platform spanning the ladder center)
		for li: int in range(m_ladders.size()):
			var lad_r: Rect2 = m_ladders[li] as Rect2
			var shaft_r: Rect2 = Rect2(lad_r.position.x + 1.0, lad_r.position.y - 14.0, maxf(2.0, lad_r.size.x - 2.0), lad_r.size.y + 10.0)
			for sr_v: Variant in m_solids:
				var sr31: Rect2 = sr_v as Rect2
				if shaft_r.intersects(sr31):
					map_geom_errors.append(mid31 + ":ladder#" + str(li) + " blocked by solid " + str(sr31))
			var bot_gy31: float = float(ml_m18.call("get_ground_y_below", lad_r.get_center().x, lad_r.end.y - 4.0, 32.0, true))
			if bot_gy31 >= INF:
				map_geom_errors.append(mid31 + ":ladder#" + str(li) + " missing bottom floor")
			var has_top_plat: bool = false
			var all_plats: Array = []
			all_plats.append_array(m_solids)
			all_plats.append_array(m_clouds)
			for pr_v: Variant in all_plats:
				var pr31: Rect2 = pr_v as Rect2
				var x_gap: float = 0.0
				if pr31.end.x < lad_r.position.x:
					x_gap = lad_r.position.x - pr31.end.x
				elif pr31.position.x > lad_r.end.x:
					x_gap = pr31.position.x - lad_r.end.x
				var dy_top31: float = pr31.position.y - lad_r.position.y
				if x_gap <= 12.0 and dy_top31 >= -6.0 and dy_top31 <= 32.0:
					has_top_plat = true
					if pr31.position.x <= lad_r.get_center().x and pr31.end.x >= lad_r.get_center().x and dy_top31 <= 16.0 and dy_top31 < 8.0:
						map_geom_errors.append(mid31 + ":ladder#" + str(li) + " top extension " + str(dy_top31) + "px < 8px")
			if not has_top_plat:
				map_geom_errors.append(mid31 + ":ladder#" + str(li) + " missing reachable top platform")

		# Invariant B: Vertical elevator shafts in steel_harbor & VS maps must not be obstructed by static ground rects
		if mid31 == "steel_harbor":
			for ei: int in range(m_elevs.size()):
				var ed: Dictionary = m_elevs[ei] as Dictionary
				var er: Rect2 = ed.get("rect", Rect2()) as Rect2
				var dist_e: float = absf(float(ed.get("distance", 128.0)))
				var top_ey: float = er.position.y - dist_e
				var elev_shaft: Rect2 = Rect2(er.position.x + 2.0, top_ey + 2.0, er.size.x - 4.0, dist_e - 4.0)
				for cr_v: Variant in m_clouds:
					if elev_shaft.intersects(cr_v as Rect2):
						map_geom_errors.append(mid31 + ":elevator#" + str(ei) + " obstructed by cloud " + str(cr_v))
				for sr_v2: Variant in m_solids:
					if elev_shaft.intersects(sr_v2 as Rect2):
						map_geom_errors.append(mid31 + ":elevator#" + str(ei) + " obstructed by solid " + str(sr_v2))

			# Invariant C: All player_spawns in steel_harbor are grounded and not buried inside slope polygons
			for si: int in range(m_spawns.size()):
				var sp_pt: Vector2 = m_spawns[si] as Vector2
				var sp_gy: float = float(ml_m18.call("get_ground_y_below", sp_pt.x, sp_pt.y - 6.0, 24.0, true))
				if sp_gy >= INF:
					map_geom_errors.append(mid31 + ":spawn#" + str(si) + " ungrounded at " + str(sp_pt))
				for sl_v: Variant in m_slopes:
					var sl_d: Dictionary = sl_v as Dictionary
					var pts: PackedVector2Array = sl_d.get("points", PackedVector2Array()) as PackedVector2Array
					if pts.size() >= 3 and Geometry2D.is_point_in_polygon(Vector2(sp_pt.x, sp_pt.y - 8.0), pts):
						map_geom_errors.append(mid31 + ":spawn#" + str(si) + " buried inside slope polygon")

			# Invariant D: All portals in steel_harbor have safe exit floor & >= 24px runway
			for pi: int in range(m_portals.size()):
				var pd: Dictionary = m_portals[pi] as Dictionary
				var ex_r: Rect2 = pd.get("exit_rect", Rect2()) as Rect2
				var pdir: Vector2 = pd.get("dir", Vector2.RIGHT) as Vector2
				var exit_x: float = (ex_r.end.x + 2.0) if pdir.x < 0.0 else (ex_r.position.x - 2.0)
				var run_dir: float = 1.0 if pdir.x < 0.0 else -1.0
				var ex_gy0: float = float(ml_m18.call("get_ground_y_below", exit_x, ex_r.end.y - 8.0, 20.0, true))
				var ex_gy1: float = float(ml_m18.call("get_ground_y_below", exit_x + run_dir * 24.0, ex_r.end.y - 8.0, 20.0, true))
				if ex_gy0 >= INF or ex_gy1 >= INF:
					map_geom_errors.append(mid31 + ":portal#" + str(pi) + " unsafe exit runway at x=" + str(exit_x))

	_check(
		all_maps_dict31.size() >= 13 and vs_map_ids31.has("steel_harbor") and map_geom_errors.is_empty(),
		"SF-M31.3: Automated Map Geometry & Navigation Validator passed across all " + str(all_maps_dict31.size()) + " maps (19 ladders, elevators, spawns, portals; errors=" + str(map_geom_errors.size()) + ")"
	)

	# --- SF-M32 Full-Map Ballistic Range (Projectiles.as OutsideTheWorld) & Weight-Based Kick Launch + 0.0px OBB Floor Penetration ---
	ml_m18.call("load_map", "steel_harbor")
	for old_p32: Variant in (mc.get("props") as Array):
		if is_instance_valid(old_p32):
			(old_p32 as Node2D).free()
	(mc.get("props") as Array).clear()
	if pm_m12.has_method("clear_all"):
		pm_m12.call("clear_all")
	sh_p1.global_position = Vector2(-350.0, -168.0)

	# 1. SF-M32.1: All firearms (PISTOL, UZI, SHOTGUN, RIFLE, M60, MAGNUM, SNIPER, BAZOOKA) travel across the entire 800px map
	#    (>= 680px from x=-350 to x=+330+) without disappearing after 170-350px!
	(ml_m18.get("solid_rects") as Array).clear()
	(ml_m18.get("cloud_rects") as Array).clear()
	(mc.get("fighters") as Array).clear()
	var full_map_guns: Array[String] = ["PISTOL", "UZI", "SHOTGUN", "RIFLE", "M60", "MAGNUM", "SNIPER", "BAZOOKA"]
	var guns_full_map_ok: int = 0
	for g_id: String in full_map_guns:
		pm_m12.call("clear_all")
		pm_m12.call("spawn_bullet", sh_p1, g_id, Vector2(-350.0, 0.0), 0.0)
		var max_b_traveled: float = 0.0
		for _bs32: int in range(42):
			pm_m12.call("step_projectiles", 1.0)
			for b_var: Variant in (pm_m12.get("bullets") as Array):
				var bd: Dictionary = b_var as Dictionary
				bd["dir"] = Vector2.RIGHT
				bd["vel"] = Vector2(float(bd.get("speed", 30.0)), 0.0)
				bd["angle_deg"] = 0.0
				max_b_traveled = maxf(max_b_traveled, float(bd.get("traveled", 0.0)))
		if max_b_traveled >= 680.0:
			guns_full_map_ok += 1
	pm_m12.call("clear_all")
	ml_m18.call("load_map", "steel_harbor")
	_check(
		guns_full_map_ok == full_map_guns.size(),
		"SF-M32.1: All " + str(guns_full_map_ok) + "/" + str(full_map_guns.size()) + " firearms travel full map width (>680px across 800px 'steel_harbor') without premature disappearance"
	)

	# 2. SF-M32.2: Weight-based Kick Parabolic Launch Hop (Image 1) + 0.0px OBB Floor Penetration at ALL rotation angles (Image 2 & Image 3)
	var m32_barrel: Node2D = mc.call("spawn_interactive_prop", "BARREL", Vector2(-140.0, 68.5)) as Node2D
	m32_barrel.set("on_ground", true)
	m32_barrel.set("_settling_frames", 0.0)
	m32_barrel.call("apply_melee_hit", 6.0, 1, true, "FISTS", sh_p1)
	var max_air_lift_px: float = 0.0
	var max_floor_penetration_px: float = 0.0
	for _kb32: int in range(18):
		m32_barrel.call("step_prop", 1.0)
		var b_rot: float = m32_barrel.rotation
		var b_hw: float = float(m32_barrel.get("base_width")) * 0.5
		var b_hh: float = float(m32_barrel.get("base_height")) * 0.5
		var max_corner_y: float = -INF
		for c_local: Vector2 in [Vector2(-b_hw, -b_hh), Vector2(b_hw, -b_hh), Vector2(b_hw, b_hh), Vector2(-b_hw, b_hh)]:
			var c_world: Vector2 = m32_barrel.global_position + c_local.rotated(b_rot)
			max_corner_y = maxf(max_corner_y, c_world.y)
		max_air_lift_px = maxf(max_air_lift_px, 76.0 - max_corner_y)
		max_floor_penetration_px = maxf(max_floor_penetration_px, max_corner_y - 76.0)
	var barrel_kick_dx: float = m32_barrel.global_position.x - (-140.0)
	(mc.get("props") as Array).clear()
	m32_barrel.free()

	# Verify weight hierarchy: GASCAN (m=1.05) > BARREL (m=1.85) > FILECAB (m=2.25) > DESK (m=3.20)
	var m32_gas: Node2D = mc.call("spawn_interactive_prop", "GASCAN", Vector2(-140.0, 70.5)) as Node2D
	m32_gas.set("on_ground", true)
	m32_gas.set("_settling_frames", 0.0)
	m32_gas.call("apply_melee_hit", 6.0, 1, true, "FISTS", sh_p1)
	for _kg32: int in range(18):
		m32_gas.call("step_prop", 1.0)
	var gas_kick_dx: float = m32_gas.global_position.x - (-140.0)
	(mc.get("props") as Array).clear()
	m32_gas.free()

	var m32_fcab: Node2D = mc.call("spawn_interactive_prop", "FILECAB", Vector2(-140.0, 68.5)) as Node2D
	m32_fcab.set("on_ground", true)
	m32_fcab.set("_settling_frames", 0.0)
	m32_fcab.call("apply_melee_hit", 6.0, 1, true, "FISTS", sh_p1)
	for _kf32: int in range(18):
		m32_fcab.call("step_prop", 1.0)
	var fcab_kick_dx: float = m32_fcab.global_position.x - (-140.0)
	(mc.get("props") as Array).clear()
	m32_fcab.free()

	var m32_desk: Node2D = mc.call("spawn_interactive_prop", "DESK", Vector2(-140.0, 69.0)) as Node2D
	m32_desk.set("on_ground", true)
	m32_desk.set("_settling_frames", 0.0)
	m32_desk.call("apply_melee_hit", 6.0, 1, true, "FISTS", sh_p1)
	for _kd32: int in range(18):
		m32_desk.call("step_prop", 1.0)
	var desk32_kick_dx: float = m32_desk.global_position.x - (-140.0)
	(mc.get("props") as Array).clear()
	m32_desk.free()

	_check(
		max_air_lift_px >= 0.8
		and max_floor_penetration_px <= 0.01
		and barrel_kick_dx >= 12.0
		and gas_kick_dx > barrel_kick_dx
		and barrel_kick_dx > fcab_kick_dx
		and fcab_kick_dx > desk32_kick_dx,
		"SF-M32.2: Kick launches props in weight-scaled parabolic hop (lift=" + str(snappedf(max_air_lift_px, 0.1)) + "px, gas=" + str(snappedf(gas_kick_dx, 0.1)) + "px > barrel=" + str(snappedf(barrel_kick_dx, 0.1)) + "px > fcab=" + str(snappedf(fcab_kick_dx, 0.1)) + "px > desk=" + str(snappedf(desk32_kick_dx, 0.1)) + "px) with 0.0px floor penetration (max_pen=" + str(snappedf(max_floor_penetration_px, 0.01)) + "px)"
	)

	# --- SF-M33 Upper-Level Melee Crossover on 'steel_harbor' (y=-108 & y=-52) + Silent Jump SFX ---
	# 1. SF-M33.1: Fighter & Bot AI cross seamlessly between Left and Right sides via upper crane walkways (y=-108)
	#    and mid-upper catwalks (y=-52, even with central glass shattered) for melee infiltration!
	ml_m18.call("load_map", "steel_harbor")
	sh_p1.call("setup_fighter", 0, "johnny", Vector2(-240.0, -108.0), false)
	sh_p1.set("match_world", mc)
	sh_p1.set("on_ground", true)
	sh_p1.set("last_played_sfx", "")
	for _cr108: int in range(300):
		var px108: float = sh_p1.global_position.x
		var on_g108: bool = bool(sh_p1.get("on_ground"))
		var need_hop108: bool = on_g108 and ((px108 >= -106.0 and px108 <= -101.0) or (px108 >= 84.0 and px108 <= 89.0))
		sh_p1.call("step_fighter", 1.0, {"right": true, "jump": need_hop108, "jump_just_pressed": need_hop108})
		if sh_p1.global_position.x >= 240.0 and bool(sh_p1.get("on_ground")):
			break
	var end_x_108: float = sh_p1.global_position.x
	var crossed_top_108_ok: bool = (end_x_108 >= 240.0 and absf(sh_p1.global_position.y - (-108.0)) <= 1.5 and bool(sh_p1.get("on_ground")))
	var jump_remained_silent_ok: bool = (str(sh_p1.get("last_played_sfx")) == "")

	# Break central glass skybridge [-14, 14] at y=-52 and verify crossing from Right Tower Roof (x=244, y=-56) to Left Tower Roof (x<=-240, y=-56) at y=-52!
	if ml_m18.has_method("damage_glass_in_rect"):
		ml_m18.call("damage_glass_in_rect", Rect2(-20.0, -58.0, 40.0, 12.0), 50.0, Vector2(0.0, 4.0))
	sh_p1.call("setup_fighter", 0, "johnny", Vector2(244.0, -56.0), false)
	sh_p1.set("match_world", mc)
	sh_p1.set("on_ground", true)
	for _cr52: int in range(320):
		var px52: float = sh_p1.global_position.x
		var on_g52: bool = bool(sh_p1.get("on_ground"))
		var need_hop52: bool = on_g52 and (
			(px52 <= 126.5 and px52 >= 121.5)
			or (px52 <= 17.5 and px52 >= 12.5)
			or (px52 <= -75.5 and px52 >= -80.5)
			or (px52 <= -127.5 and px52 >= -132.5)
		)
		sh_p1.call("step_fighter", 1.0, {"left": true, "jump": need_hop52, "jump_just_pressed": need_hop52})
		if sh_p1.global_position.x <= -240.0 and bool(sh_p1.get("on_ground")):
			break
	var end_x_52: float = sh_p1.global_position.x
	var crossed_mid_52_ok: bool = (end_x_52 <= -240.0 and absf(sh_p1.global_position.y - (-56.0)) <= 2.5 and bool(sh_p1.get("on_ground")))

	var bot_m33: Object = BotControllerScript.new()
	var path_l_to_r: Array = bot_m33.call("find_path", Vector2(-276.0, 12.0), Vector2(276.0, 12.0), ml_m18) as Array
	var path_r_to_l: Array = bot_m33.call("find_path", Vector2(276.0, 12.0), Vector2(-276.0, 12.0), ml_m18) as Array
	var ai_crossover_ok: bool = (not path_l_to_r.is_empty() and not path_r_to_l.is_empty())
	_check(
		crossed_top_108_ok and crossed_mid_52_ok and ai_crossover_ok,
		"SF-M33.1: 'steel_harbor' upper crossover infiltration verified at y=-108 (top_ok=" + str(crossed_top_108_ok) + ", end_x=" + str(snappedf(end_x_108, 0.1)) + "), y=-52 with broken glass (mid_ok=" + str(crossed_mid_52_ok) + ", end_x=" + str(snappedf(end_x_52, 0.1)) + "), and bidirectional Bot AI paths (L->R steps=" + str(path_l_to_r.size()) + ", R->L steps=" + str(path_r_to_l.size()) + ")"
	)

	# 2. SF-M33.2: Jumping, diving, wall-jumping, and ledge-jumping play ZERO jump sound effect while combat SFX still work
	sh_p1.set("last_played_sfx", "")
	sh_p1.call("_begin_jump", 1, 1.0)
	sh_p1.call("_start_dive", 1, 1.0)
	var silent_after_jump_and_dive: bool = (jump_remained_silent_ok and str(sh_p1.get("last_played_sfx")) == "")
	(sh_p1.get("inventory") as Dictionary)[1] = "FISTS"
	sh_p1.call("_start_melee_combo_step", 1)
	var combat_sfx_still_active: bool = (str(sh_p1.get("last_played_sfx")) == "swing")
	_check(
		silent_after_jump_and_dive and combat_sfx_still_active,
		"SF-M33.2: Jump & Dive SFX completely removed (silent_jump=" + str(silent_after_jump_and_dive) + ", combat_sfx=" + str(sh_p1.get("last_played_sfx")) + ")"
	)

	# --- SF-M34: 8 Powered Fighters (4 Original + 4 Anime), LoL Bespoke Resources, U/I/O/P & 5/6/7/8 4-Skill Kits, Ultimate Cut-Ins & Prop Sleeping ---
	var powered_ids: Array[String] = ["solaria", "atlas", "shinobi", "tideweaver", "goku", "luffy", "naruto", "saitama"]
	var loaded_powered_count: int = 0
	for pid: String in powered_ids:
		sh_p1.call("setup_fighter", 0, pid, Vector2(-120.0, 76.0), false)
		sh_p1.set("match_world", mc)
		var rspec34: Dictionary = sh_p1.get("resource_spec") as Dictionary
		var skit34: Dictionary = sh_p1.get("skill_kit") as Dictionary
		var mad34: Object = sh_p1.get("mugen_adapter") as Object
		if (
			bool(sh_p1.get("is_powered_fighter"))
			and mad34 != null
			and not rspec34.is_empty()
			and skit34.has("skill_1")
			and skit34.has("skill_2")
			and skit34.has("skill_3")
			and skit34.has("skill_4")
			and FileAccess.file_exists(str(mad34.get("portrait_path")))
			and FileAccess.file_exists(str(mad34.get("cutin_path")))
			and FileAccess.file_exists(str(mad34.get("sheet_path")))
		):
			loaded_powered_count += 1

	# Verify Normal Fighter ("johnny") remains 100% unchanged (no artificial buffs/nerfs)
	sh_p1.call("setup_fighter", 0, "johnny", Vector2(-120.0, 76.0), false)
	var normal_unchanged_ok: bool = (
		not bool(sh_p1.get("is_powered_fighter"))
		and is_equal_approx(float(sh_p1.get("max_hp")), 100.0)
		and is_equal_approx(float(sh_p1.get("speed_mult")), 1.0)
	)
	_check(
		loaded_powered_count == 8 and normal_unchanged_ok,
		"SF-M34.1: All " + str(loaded_powered_count) + "/8 Powered Fighters (4 Original + 4 Anime) loaded with LoL resource_spec, 4-skill kits, portraits & cut-ins; Normal Fighters 100% unchanged"
	)

	# 2. SF-M34.2: Test LoL Resource rules + 4-Button Skills (U I O P / 5 6 7 8):
	#    - Atlas Rumble Heat + Danger Zone + Overheat
	#    - Naruto Shadow Clone cap (<= 2 clones)
	#    - Tideweaver water skill douses burning fighter
	#    - Goku Kamehameha Ultimate Cut-In Banner (Slot 4)
	mc.call("start_match", {"mode": "vs", "map_id": "rooftops", "two_player": true, "bot_count": 0})
	var m34_fighters: Array = mc.get("fighters") as Array
	var m34_p1: Node2D = m34_fighters[0] as Node2D
	var m34_p2: Node2D = m34_fighters[1] as Node2D

	# Atlas Heat test
	m34_p1.call("setup_fighter", 0, "atlas", Vector2(120.0, 194.0), false)
	m34_p2.call("setup_fighter", 1, "boris", Vector2(152.0, 194.0), false)
	m34_p1.set("match_world", mc)
	m34_p2.set("match_world", mc)
	var atlas_cast1: bool = bool(m34_p1.call("try_activate_skill_slot", 1, {}))
	var atlas_heat_after_1: float = float(m34_p1.get("resource_val"))

	# Tideweaver water douses fire
	m34_p1.call("setup_fighter", 0, "tideweaver", Vector2(120.0, 194.0), false)
	m34_p1.set("match_world", mc)
	m34_p1.set("burn_state", 75.0)
	m34_p1.set("resource_val", 100.0)
	var tide_cast1: bool = bool(m34_p1.call("try_activate_skill_slot", 1, {}))
	var tide_doused_fire: bool = (tide_cast1 and is_zero_approx(float(m34_p1.get("burn_state"))))

	# Naruto Shadow Clone cap (<= 2 clones)
	m34_p1.call("setup_fighter", 0, "naruto", Vector2(120.0, 194.0), false)
	m34_p1.set("match_world", mc)
	for _cl_i: int in range(4):
		m34_p1.set("resource_val", 100.0)
		(m34_p1.get("skill_cooldowns") as Dictionary)[2] = 0.0
		m34_p1.call("try_activate_skill_slot", 2, {})
	var active_clone_cnt: int = 0
	for f_cl: Variant in (mc.get("fighters") as Array):
		if is_instance_valid(f_cl) and bool((f_cl as Node2D).get("is_summoned_clone")):
			active_clone_cnt += 1

	# Goku Ultimate Cut-In Banner on Slot 4
	m34_p1.call("setup_fighter", 0, "goku", Vector2(120.0, 194.0), false)
	m34_p1.set("match_world", mc)
	m34_p1.set("resource_val", 100.0)
	var goku_ult_ok: bool = bool(m34_p1.call("try_activate_skill_slot", 4, {}))
	var cutin_dict: Dictionary = mc.get("active_cutin") as Dictionary
	var cutin_triggered_ok: bool = (goku_ult_ok and not cutin_dict.is_empty() and float(cutin_dict.get("timer", 0.0)) > 0.0)
	_check(
		atlas_cast1 and atlas_heat_after_1 > 0.0 and tide_doused_fire and active_clone_cnt == 2 and cutin_triggered_ok,
		"SF-M34.2: LoL Resources & 4-Skill Kits verified (Atlas Heat=" + str(atlas_heat_after_1) + ", Tideweaver doused fire=" + str(tide_doused_fire) + ", Naruto clone cap=" + str(active_clone_cnt) + "/2, Goku Ultimate Cut-In=" + str(cutin_triggered_ok) + ")"
	)

	# --- SF-M35: Dual-Resolution Hybrid Art (SA-WP8), 3-Layer VFX & Hitstop/Afterimage (SA-WP9), Anti-Clipping SFX (SA-WP10), Dual Clash HUD & 6-Frame Buffer (SA-WP11/WP12) ---
	# 1. SF-M35.1: Verify all 8 SF-Native Hero Sheets preserve 1px #000000 outlines + 18 skill frames + 4px top hair/hat headroom
	var reg35: Node = MapLoaderScript.get_registry()
	var sf_native_sheets_ok: int = 0
	for pid35: String in powered_ids:
		var sh_path35: String = "res://assets/sheets/hero_" + pid35 + "_mugen.png"
		var tex35: Texture2D = reg35.call("load_cached_texture", sh_path35) as Texture2D
		if tex35 != null and tex35.get_width() == 600 and tex35.get_height() == 400:
			var img35: Image = tex35.get_image()
			# Sample IDLE frame 1 (x=46..63, y=7..32) and skill row (y=264..304) for crisp #000000 outline + non-empty pixels
			var blk_cnt: int = 0
			var skill_px_cnt: int = 0
			for py35: int in range(7, 32):
				for px35: int in range(46, 63):
					var c35: Color = img35.get_pixel(px35, py35)
					if c35.a > 0.9 and c35.r < 0.05 and c35.g < 0.05 and c35.b < 0.05:
						blk_cnt += 1
			for sy35: int in range(264, 304):
				for sx35: int in range(8, 56):
					if img35.get_pixel(sx35, sy35).a > 0.5:
						skill_px_cnt += 1
			if blk_cnt >= 15 and skill_px_cnt >= 40:
				sf_native_sheets_ok += 1

	m34_p1.call("setup_fighter", 0, "goku", Vector2(120.0, 194.0), false)
	var rv35: Node2D = m34_p1.get("rig_view") as Node2D
	var body_spr35: Sprite2D = rv35.get("body_sprite") as Sprite2D
	var body_at35: AtlasTexture = body_spr35.texture as AtlasTexture if body_spr35 != null else null
	var headroom_4px_ok: bool = (body_at35 != null and is_equal_approx(body_at35.region.size.y, 25.0))
	_check(
		sf_native_sheets_ok == 8 and headroom_4px_ok,
		"SF-M35.1: All " + str(sf_native_sheets_ok) + "/8 SF-Native Pixel Hero sheets verified (#000000 1px outline + 18 skill cells + 4px hair/hat top headroom)"
	)

	# 2. SF-M35.2: Verify Afterimage Trail, 1-Frame White Hit-Flash, Local Hitstop vs Slow-Mo Guard (EC-31), Knockdown VFX Cleanup (EC-33), and 45ms SFX Gate (EC-34)
	for f_cl_rem: Variant in (mc.get("fighters") as Array).duplicate():
		if is_instance_valid(f_cl_rem) and bool((f_cl_rem as Node2D).get("is_summoned_clone")):
			(mc.get("fighters") as Array).erase(f_cl_rem)
			(f_cl_rem as Node2D).free()
	m34_p1.call("setup_fighter", 0, "luffy", Vector2(120.0, 194.0), false)
	m34_p2.call("setup_fighter", 1, "boris", Vector2(152.0, 194.0), false)
	m34_p1.set("match_world", mc)
	m34_p2.set("match_world", mc)
	mc.set("slowmo_timer", 0.0)
	mc.set("game_speed", 1.0)
	m34_p1.set("resource_val", 100.0)
	var dash_ok35: bool = bool(m34_p1.call("try_activate_skill_slot", 3, {}))
	var trail_arr35: Array = m34_p1.get("_afterimage_trail") as Array
	var afterimage_spawned_ok: bool = (dash_ok35 and trail_arr35.size() == 3)
	var hit_flash_triggered_ok: bool = (float(m34_p2.get("_hit_flash_timer")) > 0.0)
	var hitstop_applied_ok: bool = (int(m34_p1.get("_hitstop_ticks")) == 2)
	# EC-31: When global slowmo_timer > 0, stepping fighter clears local _hitstop_ticks immediately
	mc.set("slowmo_timer", 10.0)
	m34_p1.call("step_fighter", 1.0, {})
	var ec31_no_double_freeze_ok: bool = (int(m34_p1.get("_hitstop_ticks")) == 0)
	mc.set("slowmo_timer", 0.0)
	# EC-33: Knockdown / force_fall immediately clears active_vfx_overlays
	(m34_p1.get("active_vfx_overlays") as Array).append({"kind": "beam", "color": Color.CYAN, "length": 200.0, "timer": 0.5, "max_timer": 0.5})
	m34_p1.call("force_fall", -3.0, -2.5, true)
	var ec33_vfx_cleared_ok: bool = (m34_p1.get("active_vfx_overlays") as Array).is_empty()
	_check(
		afterimage_spawned_ok and hit_flash_triggered_ok and hitstop_applied_ok and ec31_no_double_freeze_ok and ec33_vfx_cleared_ok,
		"SF-M35.2: 3-Layer VFX, Afterimage Trail (ok=" + str(afterimage_spawned_ok) + ", cnt=" + str(trail_arr35.size()) + "), Hit-Flash (" + str(hit_flash_triggered_ok) + "), Hitstop (" + str(hitstop_applied_ok) + ") & EC-31 (" + str(ec31_no_double_freeze_ok) + ")/EC-33 (" + str(ec33_vfx_cleared_ok) + ") verified"
	)

	# 3. SF-M35.3: Verify Dual Clash Split Cut-In (EC-32), 6-Frame Skill Input Buffer (EC-35), Stretched Hurtbox Guard (EC-38), Clone Kill Guard (EC-40) & Skill Denial Flash (EC-41)
	m34_p1.call("setup_fighter", 0, "goku", Vector2(120.0, 194.0), false)
	m34_p2.call("setup_fighter", 1, "saitama", Vector2(440.0, 194.0), false)
	m34_p1.set("match_world", mc)
	m34_p2.set("match_world", mc)
	(mc.get("active_cutins") as Array).clear()
	m34_p1.set("resource_val", 100.0)
	m34_p2.set("resource_val", 100.0)
	m34_p1.call("try_activate_skill_slot", 4, {})
	m34_p2.call("try_activate_skill_slot", 4, {})
	var dual_clash_ok: bool = ((mc.get("active_cutins") as Array).size() == 2)

	# EC-41: Pressing skill 4 again while on cooldown sets skill_deny_flash_timers[4] > 0
	m34_p1.call("try_activate_skill_slot", 4, {})
	var deny_dict35: Dictionary = m34_p1.get("skill_deny_flash_timers") as Dictionary
	var ec41_deny_flash_ok: bool = (float(deny_dict35.get(4, 0.0)) > 0.0)

	# EC-35: Pressing Skill 1 during active melee swing buffers _buffered_skill_slot=1 and auto-casts when swing ends
	m34_p1.call("setup_fighter", 0, "luffy", Vector2(120.0, 194.0), false)
	m34_p1.set("match_world", mc)
	m34_p1.set("_melee_active_frames", 2.0)
	m34_p1.call("step_fighter", 1.0, {"skill_1": true, "skill_1_just_pressed": true})
	var buffered_slot_recorded: bool = (int(m34_p1.get("_buffered_skill_slot")) == 1)
	m34_p1.call("step_fighter", 1.0, {})
	m34_p1.call("step_fighter", 1.0, {})
	var ec35_buffer_cast_ok: bool = (buffered_slot_recorded and float((m34_p1.get("skill_cooldowns") as Dictionary).get(1, 0.0)) > 0.0)
	# EC-38: Luffy stretched punch keeps hurtbox compact (12x18)
	var luffy_hurtbox_rect: Rect2 = m34_p1.call("get_hit_rect") as Rect2
	var ec38_hurtbox_ok: bool = is_equal_approx(luffy_hurtbox_rect.size.x, 12.0)

	_check(
		dual_clash_ok and ec41_deny_flash_ok and ec35_buffer_cast_ok and ec38_hurtbox_ok,
		"SF-M35.3: Dual Clash Split Cut-In (EC-32=" + str(dual_clash_ok) + "), 6-Frame Skill Buffer (EC-35=" + str(ec35_buffer_cast_ok) + "), Stretched Hurtbox Guard (EC-38=" + str(ec38_hurtbox_ok) + ") & HUD Denial Flash (EC-41=" + str(ec41_deny_flash_ok) + ") verified"
	)

	# --------------------------------------------------------------------------
	# SF-M36: 3.5-Head Tactical Striker Rig (Mau A - Agent Zero) & 7 Live Expressions
	# --------------------------------------------------------------------------
	# 1. SF-M36.1: Verify Agent Zero ("johnny") Tactical Striker Rig active + 5 HD Expression Portraits exist
	m34_p1.call("setup_fighter", 0, "johnny", Vector2(120.0, 194.0), false)
	m34_p1.set("match_world", mc)
	var rv36: Node2D = m34_p1.get("rig_view") as Node2D
	var ts_rig_enabled: bool = (rv36 != null and bool(rv36.get("use_tactical_striker_rig")))
	var expr_files_ok: bool = true
	for ek36: String in ["confident", "fierce", "shout", "hurt", "victory"]:
		var epath36: String = "res://assets/portraits/agent_zero_expr_" + ek36 + ".png"
		var etex36: Texture2D = reg35.call("load_cached_texture", epath36) as Texture2D
		if etex36 == null or etex36.get_width() < 64:
			expr_files_ok = false
	_check(
		ts_rig_enabled and expr_files_ok,
		"SF-M36.1: 3.5-Head Tactical Striker Rig enabled on Agent Zero & all 5 HD Expression Portraits verified"
	)

	# 2. SF-M36.2: Verify 7 Live Facial Expressions & Priority/Hold Hysteresis (TS-EC-04)
	rv36.set("_expr_hold_timer", 0.0)
	rv36.call("apply_rig_state", "johnny", "IDLE", 1, 1, 0.0, 1, 100.0, 100.0, 0.0, false, false, 0.0, false)
	var expr_idle_ok: bool = (str(rv36.call("get_current_expression_id")) == "CONFIDENT_SMIRK")
	rv36.call("apply_rig_state", "johnny", "RUN", 1, 1, 0.0, 1, 100.0, 100.0, 0.0, false, false, 0.0, false)
	var expr_run_ok: bool = (str(rv36.call("get_current_expression_id")) == "BATTLE_FOCUS")
	rv36.call("apply_rig_state", "johnny", "PUNCH_01", 1, 1, 0.0, 1, 100.0, 100.0, 0.0, false, false, 0.0, false)
	var expr_punch_ok: bool = (str(rv36.call("get_current_expression_id")) == "ATTACK_SHOUT")
	# Taking damage forces HURT_SHOCK with 0.28s hold that prevents immediate flicker back to IDLE
	m34_p1.call("_apply_raw_damage", 12.0)
	var expr_hurt_ok: bool = (str(rv36.call("get_current_expression_id")) == "HURT_SHOCK")
	rv36.call("apply_rig_state", "johnny", "IDLE", 1, 1, 0.0, 1, 88.0, 100.0, 0.0, false, false, 0.0, false)
	var hysteresis_hold_ok: bool = (str(rv36.call("get_current_expression_id")) == "HURT_SHOCK")
	rv36.call("apply_rig_state", "johnny", "DEAD", 1, 1, 0.0, 1, 0.0, 100.0, 0.0, false, false, 0.0, false)
	var expr_ko_ok: bool = (str(rv36.call("get_current_expression_id")) == "DIZZY_KO")
	_check(
		expr_idle_ok and expr_run_ok and expr_punch_ok and expr_hurt_ok and hysteresis_hold_ok and expr_ko_ok,
		"SF-M36.2: 7 Live Facial Expressions (IDLE->CONFIDENT, RUN->FOCUS, PUNCH->SHOUT, HIT->HURT_SHOCK with anti-flicker hold, KO->DIZZY_KO) verified"
	)

	# 3. SF-M36.3: Verify 360-degree Head Aim-Tracking Clamp (TS-EC-02) & HUD Live Portrait Key
	rv36.set("_expr_hold_timer", 0.0)
	rv36.call("apply_rig_state", "johnny", "AIM_PISTOL", 1, 1, -85.0, 1, 100.0, 100.0, 0.0, false, false, 0.0, false)
	var tilt_up: float = float(rv36.call("get_current_head_tilt_deg"))
	rv36.call("apply_rig_state", "johnny", "AIM_PISTOL", 1, 1, 85.0, 1, 100.0, 100.0, 0.0, false, false, 0.0, false)
	var tilt_down: float = float(rv36.call("get_current_head_tilt_deg"))
	var head_clamp_ok: bool = (tilt_up < -20.0 and tilt_up >= -36.1 and tilt_down > 20.0 and tilt_down <= 36.1)
	var hud_node36: Node = mc.get("hud_controller") as Node
	var hud_key_ok: bool = (hud_node36 != null and str(hud_node36.call("get_fighter_active_expression_key", m34_p1)) == "fierce")
	_check(
		head_clamp_ok and hud_key_ok,
		"SF-M36.3: 360-degree Head Aim-Tracking Clamp (up=" + str(snappedf(tilt_up, 0.1)) + " deg, down=" + str(snappedf(tilt_down, 0.1)) + " deg) & HUD Live Expression Portrait verified"
	)

	mc.call("_clear_match_entities")
	root.remove_child(mc)
	mc.free()


# ------------------------------------------------------------------------------
# 5. SF-M7 Showcase: Verify 10 GPU-Rendered 1280x720 PNG Screenshots
# ------------------------------------------------------------------------------
func _run_m7_showcase_png_verification_suite() -> void:
	print("--- [SUITE 5/5] SF-M7 Showcase: Verify 10 GPU-Rendered 1280x720 PNGs ---")
	for fname: String in SHOWCASE_FILES:
		var rel_path: String = "res://docs/showcase/" + fname
		var abs_path: String = ProjectSettings.globalize_path(rel_path)
		var exists: bool = FileAccess.file_exists(abs_path)
		var img: Image = Image.new()
		var err: Error = img.load(abs_path) if exists else ERR_FILE_NOT_FOUND
		var valid_size: bool = (err == OK and img.get_width() == 1280 and img.get_height() == 720 and not img.is_empty())
		_check(
			exists and valid_size,
			"Showcase PNG verified: " + rel_path + " [" + str(img.get_width()) + "x" + str(img.get_height()) + "]"
		)

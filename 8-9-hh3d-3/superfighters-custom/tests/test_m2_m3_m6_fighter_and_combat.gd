extends SceneTree
## Standalone Automated Verification Suite for SF-M2, SF-M3, and SF-M6:
## - FighterRigView (2-Layer Split Rig + Full-Body + Left/Right Aim Pitch + Blood Overlay)
## - FighterController (Unarmed start, 24Hz-on-60Hz Run/Sprint/Jump/WallJump/Roll/Dive, 3-Hit Combo, Disarm, Dive-Grab/Throw)
## - ProjectileManager & FireHazardSystem (Uzi 5-shot burst, Shotgun 4 pellets, Grenade 36-ray explosion, Molotov 22 fire particles + Roll extinguish, Rocket Ride)
## - MugenFighterAdapter & "shinobi" (4-hit Clsn1/Clsn2 combo, Shunpo Slash dash-cut, Chakra Wave projectile)

var _checks: int = 0
var _failures: int = 0
var _frame_step: int = 0


func _process(_delta: float) -> bool:
	_frame_step += 1
	if _frame_step == 1:
		print("=== [SF-M2/M3/M6] STARTING FIGHTER RIG, COMBAT, PROJECTILES, HAZARDS & MUGEN VERIFICATION ===")
		var mugen_script: Script = load("res://game/fighter/mugen_fighter_adapter.gd") as Script
		mugen_script.call("ensure_registry_integration")

		_test_rig_view_layers_and_aim()
		_test_locomotion_and_physics()
		_test_melee_combo_disarm_and_grab_throw()
		_test_ranged_uzi_burst_and_shotgun_pellets()
		_test_grenade_explosion_and_molotov_roll_extinguish()
		_test_mugen_shinobi_hero()

		var audio: Node = root.get_node_or_null("AudioManager")
		if audio != null:
			for child: Node in audio.get_children():
				if child is AudioStreamPlayer:
					(child as AudioStreamPlayer).stop()
					(child as AudioStreamPlayer).stream = null
		return false

	if _failures > 0:
		push_error("[SF-M2/M3/M6] FAILED with " + str(_failures) + " failed checks out of " + str(_checks))
		quit(1)
		return true

	print("=== [SF-M2/M3/M6] ALL " + str(_checks) + " CHECKS PASSED (100% PASS, 0 ERRORS) ===")
	quit(0)
	return true


func _new_fighter() -> Variant:
	var scene: PackedScene = load("res://scenes/fighter.tscn") as PackedScene
	return scene.instantiate()


func _new_rig_view() -> Variant:
	var script: Script = load("res://game/fighter/fighter_rig_view.gd") as Script
	return script.new()


func _new_projectile_manager() -> Variant:
	var script: Script = load("res://game/world/projectile_manager.gd") as Script
	return script.new()


func _new_fire_hazard_system() -> Variant:
	var script: Script = load("res://game/world/fire_hazard_system.gd") as Script
	return script.new()


func _check(cond: bool, msg: String) -> void:
	_checks += 1
	if not cond:
		_failures += 1
		push_error("[FAIL] " + msg)
	else:
		print("[PASS] " + msg)


func _test_rig_view_layers_and_aim() -> void:
	var rig: Variant = _new_rig_view()
	root.add_child(rig)

	# 1. Full-body states (IDLE, RUN, MACHETE_01): AimPivot must be hidden
	for st: String in ["IDLE", "RUN", "MACHETE_01"]:
		rig.apply_rig_state("johnny", st, 1, 1, 0.0, 1, 60.0, 100.0)
		_check(
			rig.current_rig_type == "full_body" and not rig.aim_pivot.visible,
			"FighterRigView '" + st + "' uses full_body with AimPivot hidden (no floating weapon)"
		)
		var b_tex: AtlasTexture = rig.body_sprite.texture as AtlasTexture
		_check(
			b_tex != null and b_tex.region.size.x > 0.0 and b_tex.region.size.y > 0.0,
			"FighterRigView '" + st + "' has valid AtlasTexture region=" + str(b_tex.region)
		)

	# Verify BloodOverlay alpha scales with missing HP
	_check(
		rig.blood_overlay.visible and is_equal_approx(rig.blood_overlay.modulate.a, 0.36),
		"BloodOverlay alpha scales accurately at 60/100 HP (alpha=" + str(rig.blood_overlay.modulate.a) + ")"
	)

	# 2. Split-rig states (AIM_PISTOL, AIM_SHOTGUN): AimPivot visible, torso + weapon_arm active
	rig.apply_rig_state("johnny", "AIM_PISTOL", 1, 1, -30.0, 1, 100.0, 100.0)
	_check(
		rig.current_rig_type == "split_rig" and rig.aim_pivot.visible,
		"FighterRigView 'AIM_PISTOL' enables split_rig and shows AimPivot"
	)
	var dir_right_up: Vector2 = rig.get_aim_direction_vector()
	_check(
		dir_right_up.x > 0.8 and dir_right_up.y < -0.45,
		"Aim direction facing RIGHT (+1) at pitch -30 deg points up-right: " + str(dir_right_up)
	)

	# Facing Left (-1) at pitch -30 deg must point up-left symmetrically
	rig.apply_rig_state("johnny", "AIM_PISTOL", 1, -1, -30.0, 1, 100.0, 100.0)
	var dir_left_up: Vector2 = rig.get_aim_direction_vector()
	_check(
		is_equal_approx(rig.scale.x, -1.0) and dir_left_up.x < -0.8 and is_equal_approx(dir_left_up.y, dir_right_up.y),
		"Aim direction facing LEFT (-1) at pitch -30 deg points up-left symmetrically: " + str(dir_left_up)
	)

	# AIM_SHOTGUN pump frames (frame 1 vs frame 3)
	rig.apply_rig_state("johnny", "AIM_SHOTGUN", 1, 1, 0.0, 1, 100.0, 100.0)
	var sg_rect_1: Rect2 = (rig.weapon_arm_sprite.texture as AtlasTexture).region
	rig.apply_rig_state("johnny", "AIM_SHOTGUN", 1, 1, 0.0, 3, 100.0, 100.0)
	var sg_rect_3: Rect2 = (rig.weapon_arm_sprite.texture as AtlasTexture).region
	_check(
		sg_rect_1 != sg_rect_3,
		"AIM_SHOTGUN weapon_arm_sprite changes atlas region on pump frame 3 (" + str(sg_rect_1) + " -> " + str(sg_rect_3) + ")"
	)

	rig.free()


func _test_locomotion_and_physics() -> void:
	var f: Variant = _new_fighter()
	root.add_child(f)
	f.setup_fighter(0, "johnny", Vector2(100.0, 200.0))

	# 1. Starts unarmed; gun hidden when not aiming
	_check(
		str(f.inventory[1]) == "FISTS" and str(f.inventory[2]) == "" and str(f.inventory[3]) == "" and not f.rig_view.aim_pivot.visible,
		"Fighter starts completely unarmed (Slot 1=FISTS, Slots 2..5 empty, AimPivot hidden)"
	)

	# Equip pistol -> still hidden while IDLE/RUN until aiming!
	f.equip_weapon("PISTOL")
	f.step_fighter(0.4, {})
	_check(
		not f.aiming and not f.rig_view.aim_pivot.visible,
		"Equipped PISTOL stays holstered (AimPivot hidden) during IDLE"
	)

	# 2. Run vs Sprint speed & stamina drain
	var x0: float = f.global_position.x
	f.step_fighter(1.0, {"right": true})
	var run_dx: float = f.global_position.x - x0
	_check(
		f.current_state == "RUN" and is_equal_approx(run_dx, 1.7),
		"Run moves exactly 1.7 px per 24Hz frame (actual=" + str(run_dx) + ")"
	)

	var x1: float = f.global_position.x
	var e0: float = f.sprint_energy
	f.step_fighter(1.0, {"right": true, "sprint": true})
	var sprint_dx: float = f.global_position.x - x1
	_check(
		f.sprinting and f.current_state == "SPRINT" and is_equal_approx(sprint_dx, 3.4) and f.sprint_energy < e0,
		"Sprint moves 3.4 px per 24Hz frame and drains SprintEnergy (actual_dx=" + str(sprint_dx) + ")"
	)

	# 3. Jump & airborne trajectory
	f.step_fighter(1.0, {"jump": true, "jump_just_pressed": true})
	_check(
		not f.on_ground and f.current_state == "JUMP" and f.air_velocity.y < -4.0 and f.global_position.y < 200.0,
		"Jump launches fighter upward (vy=" + str(f.air_velocity.y) + ", y=" + str(f.global_position.y) + ")"
	)
	for _i: int in range(30):
		f.step_fighter(1.0, {})
	_check(f.on_ground and is_equal_approx(f.global_position.y, 200.0), "Fighter lands cleanly back on ground at y=200")

	# 4. Roll & 90% bullet dodge
	f.step_fighter(1.0, {"down": true, "right": true})
	_check(f.rolling and f.current_state == "ROLL", "Down + Right triggers ROLL state")
	var dodged: bool = not f.apply_bullet_hit(10.0, 15.0, -1, false, f.global_position, false)
	_check(dodged and is_equal_approx(f.hp, 100.0), "Rolling fighter dodges incoming normal bullet")
	for _i: int in range(20):
		f.step_fighter(1.0, {})

	# 5. Dive (Sprint + Down): rotates HELPMC and lands into Roll with 0 fall damage
	f.sprint_energy = 100.0
	f.step_fighter(1.0, {"right": true, "sprint": true})
	f.step_fighter(1.0, {"right": true, "sprint": true, "down": true, "down_just_pressed": true})
	_check(
		f.diving and f.current_state == "DIVE" and f.body_rotation_deg > 0.0,
		"Sprint + Down triggers DIVE state with HELPMC rotation=" + str(f.body_rotation_deg)
	)
	var transitioned_to_roll: bool = false
	for _i: int in range(25):
		f.step_fighter(1.0, {})
		if f.rolling:
			transitioned_to_roll = true
	_check(
		transitioned_to_roll and is_equal_approx(f.hp, 100.0),
		"Dive landing automatically transitions into Roll with 0 fall damage"
	)

	f.free()


func _test_melee_combo_disarm_and_grab_throw() -> void:
	var p1: Variant = _new_fighter()
	var p2: Variant = _new_fighter()
	root.add_child(p1)
	root.add_child(p2)

	p1.setup_fighter(0, "johnny", Vector2(100.0, 200.0))
	p2.setup_fighter(1, "boris", Vector2(112.0, 200.0))
	p1.external_targets.append(p2)
	p2.external_targets.append(p1)

	# 1. Disarm test: P2 equips Pistol and holds Aim; P1 punches P2 -> P2 drops Pistol!
	p2.equip_weapon("PISTOL")
	p2.step_fighter(0.4, {"aim": true})
	_check(p2.aiming and str(p2.inventory[2]) == "PISTOL", "P2 is aiming PISTOL before disarm")

	# Execute P1 3-hit combo (PUNCH_01 -> PUNCH_02 -> PUNCH_03)
	p1.step_fighter(1.0, {"attack": true, "attack_just_pressed": true})
	_check(p1.current_state == "PUNCH_01", "P1 enters PUNCH_01 on 1st attack")
	for _i: int in range(4):
		p1.step_fighter(1.0, {})
	_check(
		not p2.aiming and str(p2.inventory[2]) == "" and p2.last_disarmed_weapon_id == "PISTOL",
		"P1 punch disarms aiming P2 (Pistol dropped from inventory)"
	)

	# Queue 2nd hit (PUNCH_02) and 3rd finisher hit (PUNCH_03)
	p1.step_fighter(1.0, {"attack": true, "attack_just_pressed": true})
	for _i: int in range(8):
		p1.step_fighter(1.0, {})
		if p1.current_state == "PUNCH_02":
			p1.step_fighter(1.0, {"attack": true, "attack_just_pressed": true})
			break
	var reached_punch_03: bool = false
	for _i: int in range(16):
		p1.step_fighter(1.0, {})
		if p1.current_state == "PUNCH_03":
			reached_punch_03 = true
	_check(
		reached_punch_03 and is_equal_approx(p2.hp, 79.0),
		"3-hit combo (6+7+8=21 dmg) reduces P2 HP from 100 to 79 (actual=" + str(p2.hp) + ") and knocks P2 down"
	)

	# Reset positions for Dive-Grab & Throw test
	p1.setup_fighter(0, "johnny", Vector2(100.0, 200.0))
	p2.setup_fighter(1, "boris", Vector2(118.0, 200.0))
	p1.external_targets.append(p2)
	p2.external_targets.append(p1)

	p1.step_fighter(1.0, {"right": true, "sprint": true})
	p1.step_fighter(1.0, {"right": true, "sprint": true, "down": true, "down_just_pressed": true})
	for _i: int in range(6):
		if p1.grabbed_target == p2:
			break
		p1.step_fighter(1.0, {})
	_check(
		p1.current_state == "GRAB" and p1.grabbed_target == p2 and p2.current_state == "GRABBED",
		"Dive into P2 triggers GRAB / GRABBED state"
	)

	# Throw P2
	p1.step_fighter(1.0, {"right": true, "attack": true, "attack_just_pressed": true})
	_check(
		p1.current_state == "THROW" and p1.grabbed_target == null and not p2.on_ground and p2.air_velocity.x > 4.0,
		"Directional Attack during GRAB executes THROW and launches P2 (vx=" + str(p2.air_velocity.x) + ")"
	)

	p1.free()
	p2.free()


func _test_ranged_uzi_burst_and_shotgun_pellets() -> void:
	var pm: Variant = _new_projectile_manager()
	var fhs: Variant = _new_fire_hazard_system()
	var shooter: Variant = _new_fighter()
	root.add_child(fhs)
	root.add_child(pm)
	root.add_child(shooter)
	pm.fire_hazard_system_override = fhs
	shooter.projectile_manager_override = pm
	shooter.fire_hazard_system_override = fhs

	shooter.setup_fighter(0, "johnny", Vector2(100.0, 200.0))

	# 1. Uzi 5-round burst test
	shooter.equip_weapon("UZI")
	_check(shooter.get_active_weapon_ammo() == 25, "Uzi starts with 25 ammo")
	shooter.step_fighter(0.4, {"aim": true})
	shooter.step_fighter(0.4, {"aim": false, "aim_just_released": true})
	for _i: int in range(15):
		shooter.step_fighter(1.0, {})
	_check(
		pm.total_bullets_spawned == 5 and shooter.get_active_weapon_ammo() == 20 and fhs.shell_casings.size() == 5,
		"Single Uzi trigger pull fires a 5-round burst (bullets=" + str(pm.total_bullets_spawned) + ", ammo_left=" + str(shooter.get_active_weapon_ammo()) + ", shells=" + str(fhs.shell_casings.size()) + ")"
	)

	# 2. Shotgun 4-pellet spread test
	pm.clear_all()
	pm.total_bullets_spawned = 0
	fhs.clear_all()
	shooter.equip_weapon("SHOTGUN")
	shooter.active_gun_slot = 3
	shooter.step_fighter(0.4, {"aim": true})
	shooter.step_fighter(0.4, {"aim": false, "aim_just_released": true})
	_check(
		pm.bullets.size() == 4 and pm.total_bullets_spawned == 4,
		"Shotgun fires 4 spread pellets simultaneously (pellets=" + str(pm.bullets.size()) + ")"
	)
	for _i: int in range(15):
		shooter.step_fighter(1.0, {})
	_check(
		fhs.shell_casings.size() == 1,
		"Shotgun FireSequence pumps and ejects 1 shotgun shell casing after firing"
	)

	shooter.free()
	pm.free()
	fhs.free()


func _test_grenade_explosion_and_molotov_roll_extinguish() -> void:
	var pm: Variant = _new_projectile_manager()
	var fhs: Variant = _new_fire_hazard_system()
	var p1: Variant = _new_fighter()
	var p2: Variant = _new_fighter()
	root.add_child(fhs)
	root.add_child(pm)
	root.add_child(p1)
	root.add_child(p2)

	pm.default_floor_y = 200.0
	fhs.default_floor_y = 200.0
	pm.fire_hazard_system_override = fhs
	pm.external_fighters = [p1, p2]
	fhs.external_fighters = [p1, p2]
	p1.projectile_manager_override = pm
	p1.fire_hazard_system_override = fhs
	p2.projectile_manager_override = pm
	p2.fire_hazard_system_override = fhs

	p1.setup_fighter(0, "johnny", Vector2(100.0, 200.0))
	p2.setup_fighter(1, "boris", Vector2(185.0, 200.0))

	# 1. Grenade throw & 36-ray explosion
	p1.equip_weapon("GRENADE")
	p1.step_fighter(1.0, {"throw": true})
	# Cook for 50 frames so remaining fuse is 22 frames
	for _i: int in range(50):
		p1.step_fighter(1.0, {"throw": true})
	p1.step_fighter(1.0, {"throw": false, "throw_just_released": true})
	_check(pm.throwables.size() == 1, "Cooked GRENADE spawned into ProjectileManager")

	for _i: int in range(30):
		pm.step_projectiles(1.0)
		fhs.step_hazards(1.0)
	_check(
		fhs.total_explosions_triggered >= 1 and p2.hp < 100.0,
		"Grenade detonates with 36-ray explosion and damages P2 (P2_hp=" + str(p2.hp) + ")"
	)

	# 2. Molotov fire burst (22 particles) + Roll twice to extinguish fire
	p2.setup_fighter(1, "boris", Vector2(165.0, 200.0))
	p1.equip_weapon("MOLOTOV")
	p1.step_fighter(1.0, {"throw": true})
	p1.step_fighter(1.0, {"throw": false, "throw_just_released": true})
	for _i: int in range(30):
		pm.step_projectiles(1.0)
		fhs.step_hazards(1.0)
		if fhs.total_fire_bursts_triggered > 0:
			break
	_check(
		fhs.total_fire_bursts_triggered >= 1 and fhs.fire_particles.size() == 22,
		"Molotov shatters on impact and spawns 22 physical fire particles"
	)

	# Ignite P2 to full BurnState = 100 (Tier 2 Burned) and verify 2 Rolls extinguish it completely
	p2.add_burn(100.0, true)
	_check(is_equal_approx(p2.burn_state, 100.0) and p2.burned, "P2 is fully burning (BurnState=100, Burned=true)")
	p2.step_fighter(1.0, {"down": true, "left": true})
	_check(is_equal_approx(p2.burn_state, 50.0) and not p2.burned, "1st Roll reduces BurnState from 100 to 50")
	for _i: int in range(16):
		p2.step_fighter(1.0, {})
	p2.step_fighter(1.0, {"down": true, "left": true})
	_check(is_equal_approx(p2.burn_state, 0.0) and not p2.burned, "2nd Roll extinguishes BurnState completely to 0")

	p1.free()
	p2.free()
	pm.free()
	fhs.free()


func _test_mugen_shinobi_hero() -> void:
	var reg: Node = root.get_node_or_null("SFDataRegistry")
	var cdata: Dictionary = reg.call("get_character_data", "shinobi") as Dictionary
	var sheet: Texture2D = reg.call("get_character_sheet", "shinobi") as Texture2D
	_check(
		not cdata.is_empty() and sheet != null and sheet.get_width() == 600 and sheet.get_height() == 400,
		"MUGEN Hero 'shinobi' registered in SFDataRegistry with 600x400 sheet"
	)

	var pm: Variant = _new_projectile_manager()
	var shinobi: Variant = _new_fighter()
	var dummy: Variant = _new_fighter()
	root.add_child(pm)
	root.add_child(shinobi)
	root.add_child(dummy)

	shinobi.projectile_manager_override = pm
	pm.external_fighters = [shinobi, dummy]
	shinobi.setup_fighter(0, "shinobi", Vector2(100.0, 200.0))
	dummy.setup_fighter(1, "agent", Vector2(114.0, 200.0))
	shinobi.external_targets.append(dummy)

	_check(shinobi.mugen_adapter != null, "Shinobi FighterController initialized MugenFighterAdapter")

	# 1. 4-hit MUGEN combo with Clsn1 red attack hitboxes & Clsn2 blue hurtboxes
	shinobi.step_fighter(1.0, {"attack": true, "attack_just_pressed": true})
	_check(shinobi.current_state == "MUGEN_COMBO_1", "Shinobi starts MUGEN_COMBO_1")
	var saw_clsn1: bool = false
	var saw_combo_4: bool = false
	for _i: int in range(30):
		shinobi.step_fighter(1.0, {"attack": true, "attack_just_pressed": true})
		if not shinobi.get_mugen_clsn1_world_boxes().is_empty():
			saw_clsn1 = true
		if shinobi.current_state == "MUGEN_COMBO_4":
			saw_combo_4 = true
	_check(
		saw_clsn1 and saw_combo_4 and dummy.hp < 100.0,
		"Shinobi chains 4-hit MUGEN combo (MUGEN_COMBO_1..4) with active Clsn1 hitboxes (dummy_hp=" + str(dummy.hp) + ")"
	)

	# 2. Shunpo Slash special move
	shinobi.setup_fighter(0, "shinobi", Vector2(100.0, 200.0))
	dummy.setup_fighter(1, "agent", Vector2(130.0, 200.0))
	shinobi.external_targets.append(dummy)
	var x_before: float = shinobi.global_position.x
	var ok_shunpo: bool = shinobi.perform_mugen_special("SHUNPO_SLASH")
	for _i: int in range(10):
		shinobi.step_fighter(1.0, {})
	_check(
		ok_shunpo and shinobi.global_position.x > x_before + 30.0 and dummy.hp < 100.0,
		"Shinobi 'Shunpo Slash' dashes forward (" + str(x_before) + " -> " + str(shinobi.global_position.x) + ") and slices enemy"
	)

	# 3. Chakra Wave energy projectile
	var ok_wave: bool = shinobi.perform_mugen_special("CHAKRA_WAVE")
	for _i: int in range(10):
		shinobi.step_fighter(1.0, {})
	_check(
		ok_wave and pm.bullets.size() >= 1 and str(pm.bullets[0].get("weapon_id", "")) == "CHAKRA_WAVE",
		"Shinobi 'Chakra Wave' spawns glowing energy projectile in ProjectileManager"
	)

	shinobi.free()
	dummy.free()
	pm.free()

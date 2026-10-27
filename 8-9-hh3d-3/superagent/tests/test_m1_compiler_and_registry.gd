extends SceneTree
## Automated verification test for Stage 1 (SF-M1): XFL Compiler, SFDataRegistry, and AudioManager.

const RegistryScript = preload("res://game/core/sf_data_registry.gd")
const AudioScript = preload("res://game/core/audio_manager.gd")

var _failures: int = 0
var _checks: int = 0


func _init() -> void:
	print("=== [SF-M1] STARTING COMPILER & REGISTRY VERIFICATION ===")
	var registry: SFDataRegistryClass = RegistryScript.new()
	registry.ensure_loaded()

	var audio: SFAudioManager = AudioScript.new()
	audio.ensure_loaded()

	_verify_rigs(registry)
	_verify_character_sheets(registry)
	_verify_weapons(registry)
	_verify_maps(registry)
	_verify_audio(audio)

	audio.free()
	registry.free()

	if _failures > 0:
		push_error("[SF-M1] FAILED with " + str(_failures) + " failed checks out of " + str(_checks))
		quit(1)
		return

	print("=== [SF-M1] ALL " + str(_checks) + " CHECKS PASSED (EXIT 0) ===")
	quit(0)


func _check(cond: bool, msg: String) -> void:
	_checks += 1
	if not cond:
		_failures += 1
		push_error("[FAIL] " + msg)
	else:
		print("[PASS] " + msg)


func _verify_rigs(registry: SFDataRegistryClass) -> void:
	var rigs: Dictionary = registry.get_rig_data()
	_check(not rigs.is_empty(), "sf_compiled_rigs.json loaded into SFDataRegistry")

	var states: Dictionary = registry.get_states()
	_check(states.size() >= 56, "rigs.states.size() >= 56 (actual=" + str(states.size()) + ")")

	var required_states: Array[String] = [
		"IDLE",
		"RUN",
		"SPRINT",
		"JUMP",
		"FALL_F",
		"FALL_B",
		"KNOCKDOWN",
		"KNEEL",
		"CROUCH",
		"COVER",
		"ROLL",
		"KICK",
		"DIVE",
		"CLIMB",
		"SLIDE",
		"PUNCH_01",
		"PUNCH_02",
		"PUNCH_03",
		"MACHETE_01",
		"AXE_01",
		"SWORD_01",
		"AIM_PISTOL",
		"AIM_HANDGUN",
		"AIM_MAGNUM",
		"AIM_RIFLE",
		"AIM_UZI",
		"AIM_SHOTGUN",
		"AIM_SNIPER",
		"AIM_BAZOOKA",
		"AIM_FLAMETHROWER",
		"AIM_GRENADE",
		"AIM_MOLOTOV",
		"THROW",
		"GRABBED",
		"JUMPKICK",
		"STAGGER",
		"DEATH_KNEEL",
		"DEAD"
	]

	for st_name: String in required_states:
		var st: Dictionary = registry.get_state_data(st_name)
		var frames: Array = registry.get_state_frames(st_name)
		var has_valid_frame: bool = false
		if not frames.is_empty():
			var f0: Dictionary = frames[0] as Dictionary
			var rect: Array = f0.get("rect", []) as Array
			var pivot: Array = f0.get("pivot", []) as Array
			has_valid_frame = rect.size() == 4 and pivot.size() == 2 and float(rect[2]) > 0.0 and float(rect[3]) > 0.0
		_check(
			not st.is_empty() and has_valid_frame,
			"State '" + st_name + "' has valid sub-pixel rect & pivot (frames=" + str(frames.size()) + ")"
		)

	# Verify split-rig AIM states have torso, shoulder_pivot, and weapon_arm markers
	for aim_state: String in ["AIM_PISTOL", "AIM_RIFLE", "AIM_SHOTGUN", "AIM_BAZOOKA"]:
		var st_aim: Dictionary = registry.get_state_data(aim_state)
		var torso: Dictionary = st_aim.get("torso", {}) as Dictionary
		var wpn_arm: Dictionary = st_aim.get("weapon_arm", {}) as Dictionary
		var shoulder: Array = st_aim.get("shoulder_pivot", []) as Array
		var fire_center: Array = wpn_arm.get("fire_center", []) as Array
		var muzzle_center: Array = wpn_arm.get("muzzle_center", []) as Array
		var shell_center: Array = wpn_arm.get("shell_center", []) as Array
		_check(
			not torso.is_empty() and shoulder.size() == 2 and fire_center.size() == 2 and muzzle_center.size() == 2 and shell_center.size() == 2,
			"Split-rig '" + aim_state + "' has torso + shoulder_pivot + fire/muzzle/shell centers"
		)


func _verify_character_sheets(registry: SFDataRegistryClass) -> void:
	var roster_ids: Array[String] = [
		"johnny",
		"boris",
		"agent",
		"hideki",
		"blaire",
		"savage",
		"cruger",
		"ivan",
		"brody",
		"mac"
	]
	for cid: String in roster_ids:
		var tex: Texture2D = registry.get_character_sheet(cid)
		var ok: bool = tex != null and tex.get_width() == 600 and tex.get_height() == 400
		_check(ok, "Character sheet '" + cid + "' loaded with exact size 600x400")

	var blood_tex: Texture2D = registry.get_blood_sheet()
	_check(
		blood_tex != null and blood_tex.get_width() == 600 and blood_tex.get_height() == 400,
		"Blood overlay sheet (player_blood) loaded with exact size 600x400"
	)


func _verify_weapons(registry: SFDataRegistryClass) -> void:
	var weapons: Dictionary = registry.get_all_weapons()
	_check(weapons.size() >= 25, "weapons.size() >= 25 (actual=" + str(weapons.size()) + ")")

	var core_weapons: Array[String] = [
		"FISTS",
		"KNIFE",
		"BATON",
		"MACHETE",
		"AXE",
		"SWORD",
		"BASEBALL_BAT",
		"CHAINSAW",
		"PISTOL",
		"SILENCED_PISTOL",
		"MAGNUM",
		"UZI",
		"FLARE_GUN",
		"SHOTGUN",
		"SAWED_OFF",
		"RIFLE",
		"TOMMY_GUN",
		"SNIPER",
		"M60",
		"BAZOOKA",
		"FLAMETHROWER",
		"LASER_GUN",
		"GRENADE",
		"MOLOTOV",
		"C4",
		"MINE"
	]
	for wid: String in core_weapons:
		var w: Dictionary = registry.get_weapon_data(wid)
		var fseq: Array = w.get("fire_sequence", []) as Array
		_check(
			not w.is_empty() and not fseq.is_empty() and int(w.get("slot", 0)) >= 1,
			"Weapon '" + wid + "' compiled with fire_sequence (len=" + str(fseq.size()) + ")"
		)


func _verify_maps(registry: SFDataRegistryClass) -> void:
	var maps: Dictionary = registry.get_all_maps()
	var vs_ids: Array[String] = registry.get_vs_map_ids()
	_check(maps.size() >= 10 and vs_ids.size() >= 8, "Compiled maps count=" + str(maps.size()) + " (vs_maps=" + str(vs_ids.size()) + ")")

	var required_maps: Array[String] = [
		"rooftops",
		"storage",
		"police_station",
		"hazardous",
		"subway",
		"tower",
		"junkyard",
		"cargo",
		"tutorial",
		"survival"
	]
	for mid: String in required_maps:
		var m: Dictionary = registry.get_map_data(mid)
		var gboxes: Array = m.get("ground_boxes", []) as Array
		var pspawns: Array = m.get("player_spawns", []) as Array
		var bg_layers: Array = m.get("bg_layers", []) as Array
		var grid: Dictionary = m.get("ai_path_grid", {}) as Dictionary
		var nodes: Array = grid.get("nodes", []) as Array
		var binds: Array = grid.get("binds", []) as Array
		_check(
			not m.is_empty() and not gboxes.is_empty() and not pspawns.is_empty() and not bg_layers.is_empty(),
			"Map '" + mid + "' has ground_boxes=" + str(gboxes.size()) + ", spawns=" + str(pspawns.size()) + ", ai_nodes=" + str(nodes.size()) + ", ai_binds=" + str(binds.size())
		)


func _verify_audio(audio: SFAudioManager) -> void:
	var count: int = audio.get_loaded_sound_count()
	_check(count >= 73, "AudioManager loaded >= 73 sound files (actual=" + str(count) + ")")

	for snd_key: String in ["Ak47_1", "Punch1", "SfxExplosion1", "Music1", "pistol", "shotgun", "bazooka", "superfighters_theme"]:
		_check(audio.has_sound(snd_key), "AudioManager resolves sound '" + snd_key + "'")

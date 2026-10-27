extends SceneTree

const SF_BANK = preload("res://game/presentation/sf_classic_bank.gd")
const _VIEW = preload("res://game/fighter/fighter_view.gd")
const _ROOM = preload("res://game/ui/match_room.gd")
const _FX = preload("res://game/presentation/arena_fx.gd")
const _AUDIO = preload("res://game/presentation/combat_audio.gd")

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var failures: int = 0
	if _VIEW == null or _ROOM == null or _FX == null or _AUDIO == null:
		push_error("presentation scripts failed to load")
		failures += 1
	if not SF_BANK.available():
		push_error("classic bundle missing")
		failures += 1
	var body: Texture2D = SF_BANK.player_texture(1, "IDLE")
	var gun: Texture2D = SF_BANK.weapon_texture(&"pistol")
	# The Flash timeline starts with two transparent frames.  Asking for frame
	# 1 made the focused smoke report a false missing-asset failure even though
	# the exported effect has visible frames later in the same symbol.
	var boom: Texture2D = null
	for frame: int in range(1, 9):
		boom = SF_BANK.frame_texture("explosion_circle", frame)
		if boom != null:
			break
	var shot: AudioStream = SF_BANK.sound_for(&"shot_pistol")
	var map: Texture2D = SF_BANK.map_texture()
	if body == null or body.get_width() < 8:
		push_error("player texture missing")
		failures += 1
	if gun == null:
		push_error("pistol texture missing")
		failures += 1
	if boom == null:
		push_error("explosion texture missing")
		failures += 1
	if shot == null:
		push_error("gun audio missing")
		failures += 1
	if map == null or map.get_width() < 100:
		push_error("classic map texture missing")
		failures += 1
	for weapon_id: StringName in [&"rifle", &"uzi", &"shotgun", &"magnum", &"sniper", &"rocket_launcher", &"flamethrower", &"grenade", &"molotov", &"knife", &"machete", &"pipe", &"axe", &"sword", &"medkit", &"pill", &"bullet_time_5", &"bullet_time_10"]:
		if SF_BANK.weapon_texture(weapon_id) == null:
			push_error("classic weapon texture missing: %s" % String(weapon_id))
			failures += 1
	if failures == 0:
		print("SF classic bank PASS body=%dx%d pistol=%dx%d map=%dx%d" % [body.get_width(), body.get_height(), gun.get_width(), gun.get_height(), map.get_width(), map.get_height()])
	else:
		printerr("SF classic bank FAIL %d" % failures)
	quit(0 if failures == 0 else 1)

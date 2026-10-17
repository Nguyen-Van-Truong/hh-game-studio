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
	var boom: Texture2D = SF_BANK.frame_texture("explosion_circle", 1)
	var shot: AudioStream = SF_BANK.sound_for(&"shot_pistol")
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
	if failures == 0:
		print("SF classic bank PASS body=%dx%d pistol=%dx%d" % [body.get_width(), body.get_height(), gun.get_width(), gun.get_height()])
	else:
		printerr("SF classic bank FAIL %d" % failures)
	quit(0 if failures == 0 else 1)

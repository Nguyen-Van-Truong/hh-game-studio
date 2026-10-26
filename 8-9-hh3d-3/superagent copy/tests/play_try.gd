extends SceneTree

const ROOM_SCRIPT = preload("res://game/ui/match_room.gd")
const SF_BANK = preload("res://game/presentation/sf_classic_bank.gd")

var room: Node2D
var frames: int = 0
var output: String = "res://.local/play-try"
var finishing: bool = false

func _initialize() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(output))
	for frame: int in [20, 90, 140]:
		var old_path := ProjectSettings.globalize_path(output + "/frame-%04d.png" % frame)
		if FileAccess.file_exists(old_path):
			DirAccess.remove_absolute(old_path)
	change_scene_to_file("res://game/ui/match_room.tscn")

func _physics_process(_delta: float) -> bool:
	if room == null:
		if current_scene == null or current_scene.get_script() != ROOM_SCRIPT:
			return false
		room = current_scene as Node2D
	frames += 1
	if frames == 8:
		_key(KEY_D, true)
		_key(KEY_LEFT, true)
	if frames == 40:
		_key(KEY_W, true)
		_key(KEY_UP, true)
	if frames == 48:
		_key(KEY_W, false)
		_key(KEY_UP, false)
	if frames == 70:
		_key(KEY_D, false)
		_key(KEY_LEFT, false)
		_key(KEY_S, true)
		_key(KEY_DOWN, true)
		_key(KEY_J, true)
		_key(KEY_KP_1, true)
	if frames == 78:
		_key(KEY_S, false)
		_key(KEY_DOWN, false)
		_key(KEY_J, false)
		_key(KEY_KP_1, false)
		_key(KEY_K, true)
		_key(KEY_KP_2, true)
	if frames == 86:
		_key(KEY_K, false)
		_key(KEY_KP_2, false)
	if frames in [20, 90, 140]:
		_capture(frames)
	if frames >= 160 and not finishing:
		finishing = true
		var snap_value: Variant = room.call("read_snapshot")
		var snap: Dictionary = snap_value if snap_value is Dictionary else {}
		print("PLAY_TRY tick=%s phase=%s" % [str(snap.get("tick", -1)), str(snap.get("phase", ""))])
		call_deferred("_done")
	return false

func _capture(frame: int) -> void:
	if DisplayServer.get_name().to_lower() == "headless":
		# The headless renderer has no viewport texture. Gameplay still advances
		# through the same input path; visible launcher runs capture PNGs below.
		return
	await process_frame
	var viewport := get_root().get_viewport()
	var image: Image = viewport.get_texture().get_image() if viewport != null and viewport.get_texture() != null else null
	if image == null:
		push_error("no viewport image at %d" % frame)
		return
	var err: Error = image.save_png(output + "/frame-%04d.png" % frame)
	if err != OK:
		push_error("save failed %s" % err)

func _done() -> void:
	if current_scene != null:
		var audio: Node = current_scene.get_node_or_null("CombatAudio")
		if audio != null and audio.has_method("shutdown"):
			audio.call("shutdown")
		current_scene.free()
	# AudioStreamPlayer2D creates an AudioStreamPlaybackMP3 on the audio thread.
	# A single frame is not enough for the backend to drop that reference on
	# Windows, so drain a few frames before releasing the bank and quitting.
	for _drain_frame: int in range(4):
		await process_frame
	SF_BANK.release_audio()
	quit()

func _key(code: Key, down: bool) -> void:
	var event := InputEventKey.new()
	event.keycode = code
	event.pressed = down
	event.physical_keycode = code
	Input.parse_input_event(event)
	Input.flush_buffered_events()

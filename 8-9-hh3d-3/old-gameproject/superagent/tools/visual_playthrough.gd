extends SceneTree
## Bounded local 2P visual review through actual input events. No teleport,
## inventory grant, damage injection or bot is used. This is not Y8 parity.
## Run with --write-movie for a 50-second clip including the engine audio mix.

var output: String = "res://.local/review/play-%d" % Time.get_unix_time_from_system()
var room: MatchRoom
var frames: int = 0
var captures: Array[int] = [30, 60, 120, 166, 201, 236, 280, 451, 455, 480, 525, 545, 565, 600, 720, 740, 760, 780, 1100, 1500, 2100, 2700]
var records: Array[Dictionary] = []
var started_usec: int = 0
var captured_frames: Dictionary = {}
var finishing: bool = false

func _initialize() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(output))
	change_scene_to_file("res://game/ui/match_room.tscn")
	started_usec = Time.get_ticks_usec()

func _physics_process(_delta: float) -> bool:
	if room == null:
		if not current_scene is MatchRoom:
			return false
		room = current_scene as MatchRoom
	frames += 1
	# Every 16 seconds both players repeat movement, pickup, melee and shooting.
	# Result overlays are restarted using R, never via a simulation fixture.
	var phase: StringName = StringName(room.read_snapshot().get(&"phase", &"playing"))
	if phase in [&"result", &"round_result"] and frames % 120 == 0:
		_key(KEY_R, true)
		_key(KEY_R, false)
	var t: int = frames % 960
	match t:
		1:
			_key(KEY_D, true)
			_key(KEY_LEFT, true)
		10:
			_key(KEY_D, false)
			_key(KEY_LEFT, false)
		11:
			_key(KEY_D, true)
			_key(KEY_LEFT, true)
		13:
			_key(KEY_S, true)
			_key(KEY_DOWN, true)
		16:
			_key(KEY_S, false)
			_key(KEY_DOWN, false)
		30, 90:
			_key(KEY_W, true)
			_key(KEY_UP, true)
		32, 92:
			_key(KEY_W, false)
			_key(KEY_UP, false)
		115:
			_key(KEY_D, false)
			_key(KEY_LEFT, false)
		116:
			_key(KEY_A, true)
			_key(KEY_RIGHT, true)
		118:
			_key(KEY_A, false)
			_key(KEY_RIGHT, false)
		165:
			_key(KEY_J, true)
			_key(KEY_KP_1, true)
		167:
			_key(KEY_J, false)
			_key(KEY_KP_1, false)
		175:
			_key(KEY_J, true)
			_key(KEY_KP_1, true)
		177:
			_key(KEY_J, false)
			_key(KEY_KP_1, false)
		185:
			_key(KEY_J, true)
			_key(KEY_KP_1, true)
		187:
			_key(KEY_J, false)
			_key(KEY_KP_1, false)
		140:
			_key(KEY_S, true)
			_key(KEY_DOWN, true)
			_key(KEY_J, true)
			_key(KEY_KP_1, true)
		145:
			_key(KEY_J, false)
			_key(KEY_KP_1, false)
			_key(KEY_S, false)
			_key(KEY_DOWN, false)
		200, 280, 360:
			_key(KEY_K, true)
			_key(KEY_KP_2, true)
		235, 315, 395:
			_key(KEY_K, false)
			_key(KEY_KP_2, false)
		250:
			_key(KEY_Q, true)
			_key(KEY_KP_5, true)
		252:
			_key(KEY_Q, false)
			_key(KEY_KP_5, false)
		450:
			_key(KEY_L, true)
			_key(KEY_KP_3, true)
		452:
			_key(KEY_L, false)
			_key(KEY_KP_3, false)
		520:
			_key(KEY_D, true)
			_key(KEY_LEFT, true)
		535:
			_key(KEY_D, false)
			_key(KEY_LEFT, false)
		538:
			_key(KEY_D, true)
			_key(KEY_LEFT, true)
		540:
			_key(KEY_S, true)
			_key(KEY_DOWN, true)
		548:
			_key(KEY_S, false)
			_key(KEY_DOWN, false)
			_key(KEY_D, false)
			_key(KEY_LEFT, false)
		560:
			_key(KEY_J, true)
			_key(KEY_KP_1, true)
		562:
			_key(KEY_J, false)
			_key(KEY_KP_1, false)
		700:
			_key(KEY_D, true)
			_key(KEY_LEFT, true)
		710:
			_key(KEY_D, false)
			_key(KEY_LEFT, false)
		713:
			_key(KEY_D, true)
			_key(KEY_LEFT, true)
		740:
			_key(KEY_S, true)
			_key(KEY_DOWN, true)
		750:
			_key(KEY_S, false)
			_key(KEY_DOWN, false)
			_key(KEY_D, false)
			_key(KEY_LEFT, false)
		755:
			_key(KEY_J, true)
			_key(KEY_KP_1, true)
		758:
			_key(KEY_J, false)
			_key(KEY_KP_1, false)
		550:
			_key(KEY_W, true)
			_key(KEY_UP, true)
		552:
			_key(KEY_W, false)
			_key(KEY_UP, false)
		610:
			_key(KEY_D, false)
			_key(KEY_LEFT, false)
		650:
			_key(KEY_J, true)
			_key(KEY_KP_1, true)
		652:
			_key(KEY_J, false)
			_key(KEY_KP_1, false)
	if frames in [600, 1800]:
		_key(KEY_F6, true)
		_key(KEY_F6, false)
	if frames in [1260, 1380]:
		_key(KEY_ESCAPE, true)
		_key(KEY_ESCAPE, false)
	if frames % 60 == 0:
		records.append({"frame": frames, "snapshot": room.read_snapshot(), "wall_usec": Time.get_ticks_usec() - started_usec})
	if frames >= 3000 and not finishing:
		finishing = true
		var report := FileAccess.open(output + "/playthrough.json", FileAccess.WRITE)
		report.store_string(JSON.stringify({"schema": 1, "seed": 1, "mode": "two_player", "frames": frames, "seconds_simulated": float(frames) / 60.0, "fixture": false, "records": records}, "\t"))
		report.close()
		call_deferred("_finish_cleanly")
	return false

func _finish_cleanly() -> void:
	# The visual harness owns a real match scene. Queue and drain it before the
	# SceneTree exits so audio/fx/fighter nodes do not become ObjectDB leftovers
	# and invalidate an otherwise complete runtime capture.
	room = null
	if current_scene != null:
		var audio: Node = current_scene.get_node_or_null("CombatAudio")
		if audio != null and audio.has_method("shutdown"):
			audio.call("shutdown")
		var scene_to_free: Node = current_scene
		var root_node: Node = get_root()
		root_node.remove_child(scene_to_free)
		scene_to_free.free()
	await process_frame
	await process_frame
	print("SA visual playthrough complete: 3000 frames; input-only; report=" + output)
	quit()

func _process(_delta: float) -> bool:
	for frame: int in captures:
		if frames >= frame and not captured_frames.has(frame):
			captured_frames[frame] = true
			_capture(frame)
	return false

func _capture(frame: int) -> void:
	await RenderingServer.frame_post_draw
	var result: Error = root.get_texture().get_image().save_png(output + "/frame-%04d.png" % frame)
	if result != OK:
		push_error("Visual capture failed: %s" % result)

func _key(code: Key, down: bool) -> void:
	var event := InputEventKey.new()
	event.keycode = code
	event.pressed = down
	Input.parse_input_event(event)
	Input.flush_buffered_events()

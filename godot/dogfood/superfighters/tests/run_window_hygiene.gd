extends SceneTree

const CYCLES: int = 20
const RUN_ID: String = "VF0WP2-20260829-ASIA-SAIGON-01"

var _fails: PackedStringArray = PackedStringArray()
var _evidence_dir: String = ""


func _initialize() -> void:
	call_deferred("_boot")


func _boot() -> void:
	seed(1)
	InputActions.install()
	_evidence_dir = OS.get_environment("HH_VF_EVIDENCE_DIR")
	if _evidence_dir.is_empty():
		_evidence_dir = ProjectSettings.globalize_path("res://.evidence/%s" % RUN_ID)
	DirAccess.make_dir_recursive_absolute(_evidence_dir)
	DirAccess.make_dir_recursive_absolute(_evidence_dir.path_join("screens"))
	print(
		"HH_VF_WINDOW pid=%d display=%s size=%s audio_driver=%s"
		% [
			OS.get_process_id(),
			DisplayServer.get_name(),
			str(DisplayServer.window_get_size(0)),
			AudioServer.get_driver_name()
		]
	)
	if DisplayServer.get_name() == "headless":
		_fail("window hygiene must not run --headless")
		_emit_and_quit()
		return
	DisplayServer.window_set_title("Vault Fighters")
	var packed: PackedScene = load("res://scenes/main.tscn") as PackedScene
	var app: App = packed.instantiate() as App
	app.test_driven = false
	root.add_child(app)
	await process_frame
	await RenderingServer.frame_post_draw
	_capture("title_1280x720.png")
	var n: int = 0
	var music_ok: bool = false
	var sfx_ok: bool = false
	while n < CYCLES:
		app.start_fight("vs1", "rooftops", 0)
		await process_frame
		await process_frame
		var session: GameSession = app.session
		if session == null or session.sfx == null:
			_fail("WINDOW missing session at cycle %d" % n)
			break
		if session.test_driven or session.sfx.muted:
			_fail("WINDOW fight must not mute audio")
			break
		if not session.sfx.has_audio_players():
			_fail("WINDOW fight must allocate AudioStreamPlayer")
			break
		var waited: int = 0
		while waited < 12 and not session.sfx.is_music_playing():
			await process_frame
			waited += 1
		if not session.sfx.is_music_playing():
			_fail("WINDOW fight must play music")
			break
		music_ok = true
		session.sfx.play("punch")
		if session.sfx.last_id != "punch":
			_fail("WINDOW punch SFX not recorded")
			break
		if not session.sfx.is_sfx_playing():
			_fail("WINDOW punch SFX must actually play")
			break
		sfx_ok = true
		if n == 0:
			await RenderingServer.frame_post_draw
			_capture("play_1280x720.png")
		n += 1
	app.restart_to_title()
	await process_frame
	await RenderingServer.frame_post_draw
	_capture("title_after_20_1280x720.png")
	if is_instance_valid(app):
		app.shutdown()
		app.queue_free()
	await process_frame
	await process_frame
	print(
		"HH_VF_HYGIENE_WINDOW sessions=%d music=%s sfx=%s"
		% [n, "on" if music_ok else "off", "on" if sfx_ok else "off"]
	)
	print("HH_VF_MEM static=%d" % OS.get_static_memory_usage())
	_emit_and_quit()


func _capture(file_name: String) -> void:
	var vp: Viewport = root.get_viewport()
	if vp == null:
		_fail("WINDOW missing viewport for %s" % file_name)
		return
	var tex: ViewportTexture = vp.get_texture()
	if tex == null:
		_fail("WINDOW missing viewport texture for %s" % file_name)
		return
	var img: Image = tex.get_image()
	if img == null:
		_fail("WINDOW missing screenshot image for %s" % file_name)
		return
	var path: String = _evidence_dir.path_join("screens").path_join(file_name)
	var err: Error = img.save_png(path)
	if err != OK:
		_fail("WINDOW save_png failed for %s" % file_name)


func _fail(msg: String) -> void:
	_fails.append(msg)
	print("HH_ASSERT_FAIL %s" % msg)


func _emit_and_quit() -> void:
	if _fails.is_empty():
		print("PASS: Vault Fighters window hygiene")
		quit(0)
	else:
		print("FAIL: Vault Fighters window hygiene")
		var i: int = 0
		while i < _fails.size():
			print("  - %s" % String(_fails[i]))
			i += 1
		quit(1)

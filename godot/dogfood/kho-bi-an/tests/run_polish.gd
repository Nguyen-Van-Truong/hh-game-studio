extends SceneTree

const STEP: float = 1.0 / 60.0
const ARRIVE: float = 8.0
const PATH: String = "start→key→door→relic→win"
const SHOT_1280: String = "user://kho_bi_an_r8wp4_1280x720.png"
const SHOT_1920: String = "user://kho_bi_an_r8wp4_1920x1080.png"
const SHOT_854: String = "user://kho_bi_an_r8wp4_854x480.png"
const REVIEW_JSON: String = "user://kho_bi_an_r8wp4_review.json"

var _fails: PackedStringArray = PackedStringArray()
var _visual: String = "unproven"
var _input: String = "unproven"
var _review: String = "unproven"
var _shots: Dictionary = {}
var _shot_focus: Dictionary = {}
var _held_key: Key = KEY_NONE


func _initialize() -> void:
	call_deferred("_boot")


func _boot() -> void:
	print("HH_R8WP4_BOOT")
	seed(1)
	InputActions.install()
	var saver: Node = root.get_node_or_null("SaveService")
	if saver != null:
		saver.call("use_test_path")
		saver.call("clear_slot")
	_test_win_flag()
	print("HH_R8WP4_STEP win_flag")
	_test_art_wired()
	print("HH_R8WP4_STEP art_wired")
	await _test_input_flow()
	print("HH_R8WP4_STEP input_flow")
	await _test_settings()
	print("HH_R8WP4_STEP settings")
	_test_lint()
	print("HH_R8WP4_STEP lint")
	await _test_visual_baselines()
	print("HH_R8WP4_STEP visual")
	_test_screenshot_review()
	print("HH_R8WP4_STEP review")
	if saver != null:
		saver.call("clear_slot")
		saver.call("use_default_path")
	SfxBank.set_bus_linear("Master", 1.0)
	SfxBank.set_bus_linear("Music", 1.0)
	SfxBank.set_bus_linear("SFX", 1.0)
	_emit()
	quit(0 if _fails.is_empty() else 1)


func _test_win_flag() -> void:
	var state: GameState = GameState.new()
	if state.is_win() or state.relic_reached:
		_fail("fresh GameState must not be win")
	state.has_key = true
	state.door_open = true
	if state.is_win() or state.relic_reached:
		_fail("key+door must not set relic_reached win")
	state.apply_dict({
		"schema": GameState.SCHEMA,
		"room_id": "relic",
		"has_key": true,
		"door_open": true,
		"relic_reached": true,
	})
	if not state.is_win() or not state.relic_reached:
		_fail("relic_reached must remain the only win flag")


func _test_art_wired() -> void:
	var app: App = _make_app()
	app.start_new_run()
	var session: GameSession = app.session
	if session == null:
		_fail("art wired missing session")
		return
	_assert_actor(session.player, Visuals.PLAYER_FRAMES, true)
	_assert_actor(session.warden, Visuals.WARDEN_FRAMES, false)
	_assert_prop(session.world.get_node_or_null("Key") as Node2D, Visuals.KEY_TEX)
	_assert_prop(session.world.get_node_or_null("Door") as Node2D, Visuals.DOOR_TEX)
	_assert_prop(session.world.get_node_or_null("Relic") as Node2D, Visuals.RELIC_TEX)
	var door: StaticBody2D = session.world.get_node_or_null("Door") as StaticBody2D
	if door == null or door.collision_layer != VaultMap.COL_DOOR:
		_fail("closed door must keep COL_DOOR collision")
	var shade: CanvasModulate = session.world.get_node_or_null("VaultShade") as CanvasModulate
	if shade == null:
		_fail("world missing VaultShade lighting")
	if session.player.lantern == null or session.player.lantern.texture == null:
		_fail("player lantern missing PointLight2D texture")
	if session.world.get_node_or_null("RelicLantern") == null:
		_fail("relic lantern missing")
	var icon: TextureRect = session.hud.get_node_or_null("KeyIcon") as TextureRect
	if icon == null or icon.texture == null:
		_fail("HUD KeyIcon must be TextureRect with ui_icon_key")
	elif icon.texture.resource_path != Visuals.KEY_ICON:
		_fail("HUD KeyIcon must use ui_icon_key.png")
	session.player.step_move(STEP, Vector2.RIGHT)
	if session.player.sprite == null or session.player.sprite.animation != &"walk_right":
		_fail("player walk_right animation not selected")
	session.player.step_move(STEP, Vector2.ZERO)
	if session.player.sprite == null or session.player.sprite.animation != &"idle_right":
		_fail("player idle_right animation not selected")
	session.step_fixed(STEP, Vector2.ZERO, true)
	if session.sfx == null or session.sfx.last_id != "interact":
		_fail("interact must play sfx_interact")
	if session.get_node_or_null("InteractVfx") == null:
		_fail("interact must spawn VFX burst")
	if not _walk_to(session, VaultMap.tile_center(VaultMap.KEY_CELL)):
		_fail("cannot reach key for pickup sfx")
	else:
		session.step_fixed(STEP, Vector2.ZERO, true)
		if session.sfx.last_id != "pickup":
			_fail("key pickup must play sfx_pickup")
		if bool(session.snapshot().get("win", false)):
			_fail("key pickup must not win")
	app.free()


func _assert_actor(host: Node2D, frames_path: String, need_light: bool) -> void:
	if host == null:
		_fail("missing actor")
		return
	var body: ColorRect = host.get_node_or_null("Body") as ColorRect
	if body != null and body.visible:
		_fail("%s Body ColorRect must be invisible" % host.name)
	var shape: CollisionShape2D = _first_shape(host)
	if shape == null or shape.disabled:
		_fail("%s collision must stay enabled" % host.name)
	var sprite: AnimatedSprite2D = host.get_node_or_null("Sprite") as AnimatedSprite2D
	if sprite == null or sprite.sprite_frames == null:
		_fail("%s missing AnimatedSprite2D" % host.name)
	elif sprite.sprite_frames.resource_path != frames_path:
		_fail("%s SpriteFrames path %s" % [host.name, sprite.sprite_frames.resource_path])
	if need_light:
		var light: PointLight2D = host.get_node_or_null("Lantern") as PointLight2D
		if light == null:
			_fail("%s missing lantern" % host.name)


func _assert_prop(host: Node2D, tex_path: String) -> void:
	if host == null:
		_fail("missing prop")
		return
	var body: ColorRect = host.get_node_or_null("Body") as ColorRect
	if body != null and body.visible:
		_fail("%s Body ColorRect must be invisible" % host.name)
	var sprite: Sprite2D = host.get_node_or_null("Sprite") as Sprite2D
	if sprite == null or sprite.texture == null:
		_fail("%s missing Sprite2D" % host.name)
	elif sprite.texture.resource_path != tex_path:
		_fail("%s texture %s" % [host.name, sprite.texture.resource_path])


func _first_shape(host: Node) -> CollisionShape2D:
	var kids: Array = host.get_children()
	var i: int = 0
	while i < kids.size():
		var shape: CollisionShape2D = kids[i] as CollisionShape2D
		if shape != null:
			return shape
		i += 1
	return null


func _test_input_flow() -> void:
	var actions: PackedStringArray = PackedStringArray([
		"move_left", "move_right", "move_up", "move_down", "interact", "pause"
	])
	var i: int = 0
	while i < actions.size():
		var action: String = String(actions[i])
		if not InputMap.has_action(action):
			_fail("INPUT missing action %s" % action)
		elif not InputActions.has_keyboard_and_gamepad(action):
			_fail("INPUT %s missing keyboard+gamepad" % action)
		i += 1
	if not InputMap.has_action("ui_accept") or not InputMap.has_action("ui_down"):
		_fail("INPUT missing default ui_accept/ui_down")
	if not UiTheme.readable():
		_fail("INPUT theme contrast cream/indigo < 4.5")
	var app: App = _make_app()
	app.title.visible = true
	app.title.play_btn.grab_focus()
	if not app.title.play_btn.has_focus():
		_fail("INPUT title Play must start focused")
	if app.title.play_btn.focus_neighbor_bottom != app.title.continue_btn.get_path():
		_fail("INPUT title Play neighbor is not Continue")
	if app.title.continue_btn.focus_neighbor_bottom != app.title.restart_btn.get_path():
		_fail("INPUT title Continue neighbor is not Restart")
	app.title.continue_btn.grab_focus()
	if not app.title.continue_btn.has_focus():
		_fail("INPUT title Continue cannot take focus")
	app.title.restart_btn.grab_focus()
	if not app.title.restart_btn.has_focus():
		_fail("INPUT title Restart cannot take focus")
	app.start_new_run()
	var session: GameSession = app.session
	if app.process_mode != Node.PROCESS_MODE_ALWAYS:
		_fail("INPUT App pause listener must be PROCESS_MODE_ALWAYS")
	paused = false
	_tap_key(KEY_ESCAPE)
	if not paused or session.pause_screen == null or not session.pause_screen.visible:
		_fail("INPUT Esc key parse_input_event must pause")
	if not session.pause_screen.resume_btn.has_focus():
		_fail("INPUT pause Resume must be focused")
	if session.pause_screen.master_slider == null or session.pause_screen.fullscreen_btn == null:
		_fail("INPUT pause missing volume/fullscreen controls")
	_tap_key(KEY_ESCAPE)
	if paused or session.pause_screen.visible:
		_fail("INPUT Esc must unpause while tree is paused")
	_tap_joy(JOY_BUTTON_START)
	if not paused or not session.pause_screen.visible:
		_fail("INPUT Start joy parse_input_event must pause")
	_tap_joy(JOY_BUTTON_START)
	if paused or session.pause_screen.visible:
		_fail("INPUT Start joy must unpause while tree is paused")
	session.pause_screen.master_slider.grab_focus()
	if not session.pause_screen.master_slider.has_focus():
		_fail("INPUT pause Master slider cannot take focus")
	session.pause_screen.fullscreen_btn.grab_focus()
	if not session.pause_screen.fullscreen_btn.has_focus():
		_fail("INPUT pause Fullscreen cannot take focus")
	paused = false
	session.set_paused(false)
	session.test_driven = false
	var before_x: float = session.player.global_position.x
	_emit_key(KEY_D, true)
	if not Input.is_action_pressed("move_right"):
		_fail("INPUT KEY_D parse_input_event did not press move_right")
	await _wait_physics(20)
	_emit_key(KEY_D, false)
	if session.player.global_position.x <= before_x + 1.0:
		_fail("INPUT injected KEY_D did not move the player")
	if not await _walk_to_injected(session, VaultMap.tile_center(VaultMap.KEY_CELL)):
		_fail("INPUT cannot walk to key via injected keys")
	else:
		await _interact_injected(session)
		if not bool(session.snapshot().get("has_key", false)):
			_fail("INPUT joy South interact did not pick up key")
		if bool(session.snapshot().get("win", false)):
			_fail("INPUT key pickup must not win")
		if not await _walk_to_injected(session, VaultMap.tile_center(VaultMap.DOOR_CELL)):
			_fail("INPUT cannot walk to door via injected keys")
		else:
			await _interact_injected(session)
			if bool(session.snapshot().get("win", false)):
				_fail("INPUT door-open must not win")
			if not bool(session.snapshot().get("door_open", false)):
				_fail("INPUT door did not open via parse_input_event")
			if not await _walk_to_injected(session, VaultMap.tile_center(VaultMap.RELIC_CELL)):
				_fail("INPUT cannot walk to relic via injected keys")
			else:
				await _interact_injected(session)
				if not bool(session.snapshot().get("relic_reached", false)):
					_fail("INPUT relic-reached missing")
				if not app.win_screen.visible or not app.win_screen.restart_btn.has_focus():
					_fail("INPUT win Restart must be focused")
	_release_moves()
	app.start_new_run()
	if app.session != null:
		app.session.test_driven = false
	if not await _chase_warden_injected(app.session):
		_fail("INPUT cannot reach warden via injected keys")
	elif not app.lose_screen.visible or not app.lose_screen.restart_btn.has_focus():
		_fail("INPUT lose Restart must be focused")
	print("HH_R8WP4_INPUT_INJECT key=1 joy=1 parse_input_event")
	if _count_prefix("INPUT ") == 0:
		_input = "proven"
	app.free()


func _test_settings() -> void:
	var app: App = _make_app()
	app.start_new_run()
	await _wait_draw(3)
	if app.session.sfx != null and not app.session.sfx.is_music_playing():
		app.session.sfx.start_music()
		await _wait_draw(2)
	var pause: PauseScreen = app.session.pause_screen
	var master_idx: int = AudioServer.get_bus_index("Master")
	var music_idx: int = AudioServer.get_bus_index("Music")
	var before_master: float = AudioServer.get_bus_volume_db(master_idx)
	pause.apply_bus_linear("Master", 0.25)
	var after_master: float = AudioServer.get_bus_volume_db(master_idx)
	if after_master >= before_master - 0.1:
		_fail("settings Master volume did not drop")
	pause.apply_bus_linear("Master", 1.0)
	pause.apply_bus_linear("Music", 0.4)
	pause.apply_bus_linear("SFX", 0.6)
	if AudioServer.get_bus_volume_db(music_idx) >= -0.1:
		_fail("settings Music volume did not drop")
	pause.apply_bus_linear("Music", 1.0)
	pause.apply_bus_linear("SFX", 1.0)
	pause.set_fullscreen(true)
	if not pause.last_fullscreen:
		_fail("settings fullscreen flag not set")
	pause.set_fullscreen(false)
	if pause.last_fullscreen:
		_fail("settings fullscreen flag not cleared")
	app.session.set_paused(true)
	var ducked: float = AudioServer.get_bus_volume_db(music_idx)
	app.session.set_paused(false)
	var unducked: float = AudioServer.get_bus_volume_db(music_idx)
	if ducked >= unducked:
		_fail("pause must duck Music bus")
	if app.session.sfx == null or not app.session.sfx.is_music_playing():
		_fail("music_vault must play on Music bus")
	paused = false
	app.free()


func _test_lint() -> void:
	var needed: PackedStringArray = PackedStringArray([
		Visuals.TILESET,
		Visuals.PLAYER_FRAMES,
		Visuals.WARDEN_FRAMES,
		Visuals.VFX_FRAMES,
		Visuals.KEY_TEX,
		Visuals.DOOR_TEX,
		Visuals.RELIC_TEX,
		Visuals.KEY_ICON,
		"res://assets/audio/sfx_pickup.wav",
		"res://assets/audio/sfx_door.wav",
		"res://assets/audio/sfx_caught.wav",
		"res://assets/audio/sfx_win.wav",
		"res://assets/audio/sfx_lose.wav",
		"res://assets/audio/sfx_interact.wav",
		"res://assets/audio/music_vault.wav",
	])
	var i: int = 0
	while i < needed.size():
		var path: String = String(needed[i])
		if not FileAccess.file_exists(path):
			_fail("lint missing %s" % path)
		elif "PLACEHOLDER" in path.to_upper():
			_fail("lint PLACEHOLDER path %s" % path)
		else:
			var res: Resource = load(path)
			if res == null:
				_fail("lint broken ref %s" % path)
		i += 1
	if not UiTheme.readable():
		_fail("lint contrast below 4.5")
	_scan_src_placeholder("res://src")


func _test_visual_baselines() -> void:
	paused = false
	print(
		"HH_R8WP4_CAPTURE viewport get_image/texture_2d_get windowed; dummy-renderer cannot stamp VISUAL"
	)
	print("HH_R8WP4_DISPLAY %s" % DisplayServer.get_name())
	print("HH_R8WP4_RENDER %s" % RenderingServer.get_current_rendering_method())
	if DisplayServer.get_name() == "headless":
		_fail("VISUAL refuse dummy-renderer / headless capture")
		return
	DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
	var app: App = _make_app()
	app.start_new_run()
	var session: GameSession = app.session
	if session == null or not _walk_to(session, VaultMap.tile_center(VaultMap.KEY_CELL)):
		_fail("VISUAL cannot reach key for baseline")
		app.free()
		return
	session.set_paused(false)
	paused = false
	session.refit_view()
	await _wait_draw(4)
	var sizes: Array = [
		[Vector2i(1280, 720), SHOT_1280],
		[Vector2i(1920, 1080), SHOT_1920],
		[Vector2i(854, 480), SHOT_854],
	]
	var i: int = 0
	while i < sizes.size():
		var row: Array = sizes[i] as Array
		var size: Vector2i = row[0] as Vector2i
		var dest: String = str(row[1])
		var img: Image = await _capture_viewport_size(session, size)
		if img == null or img.get_width() != size.x or img.get_height() != size.y:
			_fail("VISUAL capture %sx%s failed" % [size.x, size.y])
		elif _is_blank(img):
			_fail("VISUAL %sx%s is blank dummy-renderer" % [size.x, size.y])
		else:
			var err: Error = img.save_png(dest)
			if err != OK:
				_fail("VISUAL save failed %s" % dest)
			else:
				_shots[dest] = img
				print(
					"HH_R8WP4_SHOT %sx%s %s %s"
					% [size.x, size.y, dest, _sha256(dest)]
				)
				print(
					"HH_R8WP4_SHOT_ABS %sx%s %s"
					% [size.x, size.y, ProjectSettings.globalize_path(dest).replace("\\", "/")]
				)
		i += 1
	app.free()
	if _count_prefix("VISUAL ") == 0 and _shots.has(SHOT_1280) and _shots.has(SHOT_1920) and _shots.has(SHOT_854):
		_visual = "proven"


func _test_screenshot_review() -> void:
	var report: Dictionary = {}
	var play_paths: PackedStringArray = PackedStringArray([SHOT_1280, SHOT_1920, SHOT_854])
	var i: int = 0
	while i < play_paths.size():
		var path: String = String(play_paths[i])
		if not _shots.has(path):
			_fail("REVIEW missing play shot %s" % path)
			i += 1
			continue
		var img: Image = _shots[path] as Image
		var stats: Dictionary = _review_play_image(img, path)
		report[path] = stats
		if int(stats.get("unique", 0)) < 10:
			_fail("REVIEW %s too few unique colors" % path)
		if float(stats.get("dominant_share", 1.0)) > 0.85:
			_fail("REVIEW %s dominated by one color" % path)
		if float(stats.get("engine_clear_share", 1.0)) >= 0.45:
			_fail("REVIEW %s engine-clear 76,76,76 share=%s" % [path, stats.get("engine_clear_share", 1.0)])
		if float(stats.get("center_std", 0.0)) < 12.0:
			_fail("REVIEW %s center crop looks like a solid ColorRect" % path)
		if not bool(stats.get("has_light", false)) or not bool(stats.get("has_dark", false)):
			_fail("REVIEW %s center missing sprite visor contrast" % path)
		if not bool(stats.get("has_hud", false)):
			_fail("REVIEW %s missing HUD chrome (viewport must include HUD)" % path)
		if not bool(stats.get("hud_on_playfield", false)):
			_fail("REVIEW %s HUD sits on letterbox void, not playfield" % path)
		print(
			"HH_R8WP4_REVIEW_STAT %s clear=%s unique=%s hud_pf=%s"
			% [
				path,
				stats.get("engine_clear_share", 1.0),
				stats.get("unique", 0),
				stats.get("hud_on_playfield", false),
			]
		)
		i += 1
	_assert_layouts_differ(play_paths)
	var f: FileAccess = FileAccess.open(REVIEW_JSON, FileAccess.WRITE)
	if f == null:
		_fail("REVIEW could not write json")
	else:
		f.store_string(JSON.stringify(report))
		f.close()
		print("HH_R8WP4_REVIEW %s" % REVIEW_JSON)
	if _count_prefix("REVIEW ") == 0 and _visual == "proven":
		_review = "proven"


func _review_play_image(img: Image, path: String) -> Dictionary:
	if img.get_format() != Image.FORMAT_RGBA8:
		img.convert(Image.FORMAT_RGBA8)
	var unique: Dictionary = {}
	var counts: Dictionary = {}
	var total: int = 0
	var y: int = 0
	while y < img.get_height():
		var x: int = 0
		while x < img.get_width():
			var c: Color = img.get_pixel(x, y)
			if c.a > 0.2:
				var key: String = "%d,%d,%d" % [int(c.r * 255.0), int(c.g * 255.0), int(c.b * 255.0)]
				unique[key] = true
				counts[key] = int(counts.get(key, 0)) + 1
				total += 1
			x += 2
		y += 2
	var dominant: int = 0
	var keys: Array = counts.keys()
	var k: int = 0
	while k < keys.size():
		var n: int = int(counts[keys[k]])
		if n > dominant:
			dominant = n
		k += 1
	var share: float = 1.0
	if total > 0:
		share = float(dominant) / float(total)
	var focus: Vector2i = Vector2i(int(img.get_width() / 2), int(img.get_height() / 2))
	if _shot_focus.has(path):
		focus = _shot_focus[path] as Vector2i
	var crop: Dictionary = _center_contrast(img, focus)
	crop["unique"] = unique.size()
	crop["dominant_share"] = share
	crop["engine_clear_share"] = _engine_clear_share(img)
	crop["has_hud"] = _has_hud_chrome(img)
	crop["hud_on_playfield"] = _hud_on_playfield(img)
	crop["path"] = path
	return crop


func _engine_clear_share(img: Image) -> float:
	var n: int = 0
	var clear_n: int = 0
	var y: int = 0
	while y < img.get_height():
		var x: int = 0
		while x < img.get_width():
			var c: Color = img.get_pixel(x, y)
			n += 1
			var r: int = int(c.r * 255.0)
			var g: int = int(c.g * 255.0)
			var b: int = int(c.b * 255.0)
			if absi(r - 76) <= 3 and absi(g - 76) <= 3 and absi(b - 76) <= 3:
				clear_n += 1
			x += 2
		y += 2
	if n <= 0:
		return 1.0
	return float(clear_n) / float(n)


func _hud_on_playfield(img: Image) -> bool:
	if not _has_hud_chrome(img):
		return false
	var y1: int = mini(88, img.get_height() - 1)
	var clear_n: int = 0
	var n: int = 0
	var y: int = 8
	while y <= y1:
		var x: int = 8
		while x < mini(220, img.get_width()):
			var c: Color = img.get_pixel(x, y)
			var r: int = int(c.r * 255.0)
			var g: int = int(c.g * 255.0)
			var b: int = int(c.b * 255.0)
			n += 1
			if absi(r - 76) <= 3 and absi(g - 76) <= 3 and absi(b - 76) <= 3:
				clear_n += 1
			x += 3
		y += 3
	if n <= 0:
		return false
	return float(clear_n) / float(n) < 0.35


func _assert_layouts_differ(paths: PackedStringArray) -> void:
	if paths.size() < 3:
		return
	var rows: Array = []
	var i: int = 0
	while i < paths.size():
		var path: String = String(paths[i])
		if not _shots.has(path):
			return
		rows.append(_review_play_image(_shots[path] as Image, path))
		i += 1
	if rows.size() < 3:
		return
	var near_pairs: int = 0
	var pair: int = 0
	while pair < 3:
		var left: Dictionary = rows[pair] as Dictionary
		var right: Dictionary = rows[(pair + 1) % 3] as Dictionary
		if _crop_near(left, right):
			near_pairs += 1
		pair += 1
	if near_pairs >= 3:
		_fail("REVIEW three layouts are the same center crop")


func _crop_near(a: Dictionary, b: Dictionary) -> bool:
	return (
		absf(float(a.get("center_mean", 0.0)) - float(b.get("center_mean", 0.0))) < 8.0
		and absf(float(a.get("center_std", 0.0)) - float(b.get("center_std", 0.0))) < 6.0
		and absi(int(a.get("unique", 0)) - int(b.get("unique", 0))) < 8
	)


func _has_hud_chrome(img: Image) -> bool:
	if img.get_width() < 80 or img.get_height() < 48:
		return false
	if _hud_in_band(img, 8, mini(88, img.get_height() - 1)):
		return true
	return _hud_in_band(img, maxi(0, img.get_height() - 88), img.get_height() - 1)


func _hud_in_band(img: Image, y0: int, y1: int) -> bool:
	var dark_n: int = 0
	var cream_n: int = 0
	var y: int = y0
	while y <= y1:
		var x: int = 8
		while x < mini(620, img.get_width()):
			var c: Color = img.get_pixel(x, y)
			var lum: float = (c.r + c.g + c.b) / 3.0
			if lum < 0.24 and c.b >= c.r * 0.9:
				dark_n += 1
			if lum > 0.52 and c.r > 0.62 and c.g > 0.55:
				cream_n += 1
			x += 3
		y += 3
	return dark_n >= 16 and cream_n >= 6


func _center_contrast(img: Image, focus: Vector2i) -> Dictionary:
	var cw: int = mini(48, img.get_width())
	var ch: int = mini(48, img.get_height())
	var x0: int = clampi(focus.x - int(cw / 2), 0, img.get_width() - cw)
	var y0: int = clampi(focus.y - int(ch / 2), 0, img.get_height() - ch)
	var sum: float = 0.0
	var sum2: float = 0.0
	var n: int = 0
	var has_light: bool = false
	var has_dark: bool = false
	var y: int = 0
	while y < ch:
		var x: int = 0
		while x < cw:
			var c: Color = img.get_pixel(x0 + x, y0 + y)
			var lum: float = (c.r + c.g + c.b) * 85.0
			sum += lum
			sum2 += lum * lum
			n += 1
			if c.a > 0.5 and lum >= 110.0:
				has_light = true
			if c.a > 0.5 and lum <= 55.0:
				has_dark = true
			x += 1
		y += 1
	var mean: float = 0.0
	var std: float = 0.0
	if n > 0:
		mean = sum / float(n)
		std = sqrt(maxf(sum2 / float(n) - mean * mean, 0.0))
	return {
		"center_std": std,
		"center_mean": mean,
		"has_light": has_light,
		"has_dark": has_dark,
	}


func _capture_viewport_size(session: GameSession, size: Vector2i) -> Image:
	var win: Window = root
	win.content_scale_mode = Window.CONTENT_SCALE_MODE_DISABLED
	win.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_IGNORE
	win.content_scale_size = Vector2i(0, 0)
	DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
	DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_BORDERLESS, true)
	DisplayServer.window_set_position(Vector2i(0, 0))
	win.size = size
	DisplayServer.window_set_size(size)
	await _wait_draw(8)
	var got: Vector2i = DisplayServer.window_get_size()
	if got != size:
		win.size = size
		DisplayServer.window_set_size(size)
		await _wait_draw(8)
		got = DisplayServer.window_get_size()
	print("HH_R8WP4_WINDOW want=%sx%s got=%sx%s" % [size.x, size.y, got.x, got.y])
	if got != size:
		_fail("VISUAL window_get_size %sx%s != requested %sx%s" % [got.x, got.y, size.x, size.y])
		return null
	session.refit_view()
	await _wait_draw(4)
	session.refit_view()
	await _wait_draw(4)
	print(
		"HH_R8WP4_ZOOM %sx%s z=%s"
		% [size.x, size.y, VaultMap.zoom_for_size(Vector2(size))]
	)
	var img: Image = _viewport_get_image(win)
	if img == null or img.get_width() != size.x or img.get_height() != size.y:
		var got_w: int = 0
		var got_h: int = 0
		if img != null:
			got_w = img.get_width()
			got_h = img.get_height()
		_fail("VISUAL capture %sx%s failed (got %sx%s)" % [size.x, size.y, got_w, got_h])
		return null
	if _is_blank(img):
		_fail("VISUAL %sx%s is blank dummy-renderer" % [size.x, size.y])
		return null
	_record_focus(session, size, img)
	return img


func _viewport_get_image(vp: Viewport) -> Image:
	if vp == null:
		return null
	var tex: ViewportTexture = vp.get_texture()
	var img: Image = null
	if tex != null:
		img = tex.get_image()
	if img == null or img.is_empty():
		if tex != null:
			var rid: RID = tex.get_rid()
			if rid.is_valid():
				img = RenderingServer.texture_2d_get(rid)
	if img == null or img.is_empty():
		return null
	if img.get_format() != Image.FORMAT_RGBA8:
		img.convert(Image.FORMAT_RGBA8)
	return img


func _record_focus(session: GameSession, size: Vector2i, img: Image) -> void:
	var dest_key: String = SHOT_854
	if size.x == 1280:
		dest_key = SHOT_1280
	elif size.x == 1920:
		dest_key = SHOT_1920
	var screen: Vector2 = session.player.global_position
	var vp: Viewport = session.get_viewport()
	if vp != null:
		screen = vp.get_canvas_transform() * session.player.global_position
	var fx: int = clampi(int(screen.x), 0, img.get_width() - 1)
	var fy: int = clampi(int(screen.y), 0, img.get_height() - 1)
	var a: Dictionary = _center_contrast(img, Vector2i(fx, fy))
	var flipped: Vector2i = Vector2i(fx, img.get_height() - 1 - fy)
	var b: Dictionary = _center_contrast(img, flipped)
	if float(b.get("center_std", 0.0)) > float(a.get("center_std", 0.0)):
		_shot_focus[dest_key] = flipped
	else:
		_shot_focus[dest_key] = Vector2i(fx, fy)


func _is_blank(img: Image) -> bool:
	var unique: Dictionary = {}
	var y: int = 0
	while y < img.get_height():
		var x: int = 0
		while x < img.get_width():
			var c: Color = img.get_pixel(x, y)
			if c.a > 0.2:
				unique["%d,%d,%d" % [int(c.r * 16.0), int(c.g * 16.0), int(c.b * 16.0)]] = true
			x += 16
		y += 16
	return unique.size() < 4


func _emit_key(keycode: Key, pressed: bool) -> void:
	var ev: InputEventKey = InputEventKey.new()
	ev.physical_keycode = keycode
	ev.keycode = keycode
	ev.pressed = pressed
	ev.echo = false
	Input.parse_input_event(ev)
	Input.flush_buffered_events()
	if pressed:
		_held_key = keycode
	elif _held_key == keycode:
		_held_key = KEY_NONE


func _emit_joy(button: JoyButton, pressed: bool) -> void:
	var ev: InputEventJoypadButton = InputEventJoypadButton.new()
	ev.device = 0
	ev.button_index = button
	ev.pressed = pressed
	Input.parse_input_event(ev)
	Input.flush_buffered_events()


func _tap_key(keycode: Key) -> void:
	_emit_key(keycode, true)
	_emit_key(keycode, false)


func _tap_joy(button: JoyButton) -> void:
	_emit_joy(button, true)
	_emit_joy(button, false)


func _hold_dir(dir: Vector2) -> void:
	_release_moves()
	if dir.x > 0.0:
		_emit_key(KEY_D, true)
	elif dir.x < 0.0:
		_emit_key(KEY_A, true)
	elif dir.y > 0.0:
		_emit_key(KEY_S, true)
	elif dir.y < 0.0:
		_emit_key(KEY_W, true)


func _release_moves() -> void:
	if _held_key != KEY_NONE:
		_emit_key(_held_key, false)
	_held_key = KEY_NONE
	_emit_key(KEY_A, false)
	_emit_key(KEY_D, false)
	_emit_key(KEY_W, false)
	_emit_key(KEY_S, false)


func _walk_to_injected(session: GameSession, target: Vector2) -> bool:
	session.test_driven = false
	paused = false
	var last_dir: Vector2 = Vector2.ZERO
	var frames: int = 0
	while frames < 720:
		var here: Vector2 = session.player.global_position
		if here.distance_to(target) <= ARRIVE:
			_release_moves()
			return true
		var dir: Vector2 = InputActions.cardinal(target - here)
		if dir != last_dir:
			_hold_dir(dir)
			last_dir = dir
		await physics_frame
		frames += 1
	_release_moves()
	return session.player.global_position.distance_to(target) <= VaultMap.INTERACT_REACH


func _wait_physics(n: int) -> void:
	var i: int = 0
	while i < n:
		await physics_frame
		i += 1


func _wait_draw(n: int) -> void:
	var i: int = 0
	while i < n:
		await process_frame
		await RenderingServer.frame_post_draw
		i += 1


func _make_app() -> App:
	var packed: PackedScene = load("res://scenes/main.tscn") as PackedScene
	var app: App = packed.instantiate() as App
	app.test_driven = true
	root.add_child(app)
	return app


func _interact_injected(session: GameSession) -> void:
	session.test_driven = false
	_release_moves()
	await _wait_physics(1)
	_emit_joy(JOY_BUTTON_A, true)
	if not Input.is_action_just_pressed("interact") and not Input.is_action_pressed("interact"):
		_fail("INPUT joy South parse_input_event did not reach interact")
	await _wait_physics(4)
	_emit_joy(JOY_BUTTON_A, false)
	await _wait_physics(1)


func _chase_warden_injected(session: GameSession) -> bool:
	if session == null:
		return false
	session.test_driven = false
	paused = false
	var frames: int = 0
	while frames < 900:
		if session.state.outcome == "lose":
			_release_moves()
			return true
		var target: Vector2 = session.warden.global_position
		var dir: Vector2 = InputActions.cardinal(target - session.player.global_position)
		_hold_dir(dir)
		await physics_frame
		frames += 1
	_release_moves()
	return session.state.outcome == "lose"


func _scan_src_placeholder(path: String) -> void:
	var d: DirAccess = DirAccess.open(path)
	if d == null:
		_fail("lint cannot open %s" % path)
		return
	d.list_dir_begin()
	var name: String = d.get_next()
	while name != "":
		if name.begins_with("."):
			name = d.get_next()
			continue
		var child: String = path.path_join(name)
		if d.current_is_dir():
			_scan_src_placeholder(child)
		elif name.ends_with(".gd") or name.ends_with(".tres"):
			var txt: String = FileAccess.get_file_as_string(child)
			if "PLACEHOLDER" in txt:
				_fail("lint src PLACEHOLDER %s" % child)
		name = d.get_next()
	d.list_dir_end()


func _walk_to(session: GameSession, target: Vector2) -> bool:
	var frames: int = 0
	while frames < 720:
		var here: Vector2 = session.player.global_position
		if here.distance_to(target) <= ARRIVE:
			return true
		var delta: Vector2 = target - here
		session.step_fixed(STEP, delta, false)
		if session.player.global_position.distance_to(here) < 0.05 and frames > 8:
			return here.distance_to(target) <= VaultMap.INTERACT_REACH
		frames += 1
	return session.player.global_position.distance_to(target) <= VaultMap.INTERACT_REACH


func _sha256(path: String) -> String:
	if not FileAccess.file_exists(path):
		return ""
	var f: FileAccess = FileAccess.open(path, FileAccess.READ)
	if f == null:
		return ""
	var ctx: HashingContext = HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(f.get_buffer(int(f.get_length())))
	f.close()
	return ctx.finish().hex_encode()


func _fail(msg: String) -> void:
	_fails.append(msg)
	print("HH_ASSERT_FAIL %s" % msg)


func _count_prefix(prefix: String) -> int:
	var n: int = 0
	var i: int = 0
	while i < _fails.size():
		if String(_fails[i]).begins_with(prefix):
			n += 1
		i += 1
	return n


func _emit() -> void:
	print("HH_R8WP4_PATH %s" % PATH)
	print("HH_R8WP4_PATH_ASCII start->key->door->relic->win")
	print("HH_R8WP4 VISUAL=%s INPUT=%s REVIEW=%s" % [_visual, _input, _review])
	if _fails.is_empty():
		print("PASS: R8-WP4 polish art/UI/feedback")
	else:
		print("FAIL: R8-WP4 polish")
		var i: int = 0
		while i < _fails.size():
			print("  - %s" % String(_fails[i]))
			i += 1

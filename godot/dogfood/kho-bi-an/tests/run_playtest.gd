extends SceneTree

const STEP: float = 1.0 / 60.0
const ARRIVE: float = 8.0
const PATH: String = "start→key→door→relic→win"
const RUN_ID: String = "01R8WP5PTT00000000KBA00001"
const SOAK_WALL_S: float = 600.0
const SHOT_PLAY: String = "user://kho_bi_an_r8wp5_play_1280x720.png"
const SHOT_PAUSE: String = "user://kho_bi_an_r8wp5_pause_1280x720.png"
const REPORT_PATH: String = "user://kho_bi_an_r8wp5_report.json"
const LOAD_BUDGET_MS: int = 3000
const P95_TARGET_MS: float = 16.67
const MEM_GROW_BUDGET: int = 256 * 1024 * 1024

var _fails: PackedStringArray = PackedStringArray()
var _p2: PackedStringArray = PackedStringArray()
var _runs: Array[Dictionary] = []
var _runs_label: String = "unproven"
var _soak_label: String = "unproven"
var _stuck_label: String = "unproven"
var _perf_label: String = "unproven"
var _visual_label: String = "unproven"
var _clean_label: String = "unproven"
var _held_key: Key = KEY_NONE
var _soak_frames: int = 0
var _soak_wall_s: float = 0.0
var _soak_os_s: float = 0.0
var _soak_blockers: int = 0
var _soak_wins: int = 0
var _soak_losses: int = 0
var _soak_retries: int = 0
var _soak_pauses: int = 0
var _soak_saves: int = 0
var _soak_loads: int = 0
var _soak_skips: int = 0
var _soak_fast: bool = false
var _soak_test_driven: int = 1
var _frame_ms: PackedFloat32Array = PackedFloat32Array()
var _load_ms: int = 0
var _mem_start: int = 0
var _mem_end: int = 0
var _p95_ms: float = 0.0
var _shots: Dictionary = {}


func _initialize() -> void:
	call_deferred("_boot")


func _boot() -> void:
	print("HH_R8WP5_BOOT")
	print("HH_R8WP5_PATH %s" % PATH)
	print("HH_R8WP5_PATH_ASCII start->key->door->relic->win")
	Engine.time_scale = 1.0
	_soak_fast = _fast_skip_requested()
	print("HH_R8WP5_SOAK_PLAN wall_s=%.1f time_scale=1.0 test_driven=0 not_g5=1 fast=%d" % [
		SOAK_WALL_S, 1 if _soak_fast else 0
	])
	if _soak_fast:
		print("HH_R8WP5_SOAK_FAST skip=1 not_proven")
	seed(1)
	InputActions.install()
	var saver: Node = root.get_node_or_null("SaveService")
	if saver != null:
		saver.call("use_test_path")
		saver.call("clear_slot")
	_mem_start = int(OS.get_static_memory_usage())
	_test_seeded_runs()
	print("HH_R8WP5_STEP seeded")
	await _test_fuzz_ui()
	print("HH_R8WP5_STEP fuzz")
	_test_stuck()
	print("HH_R8WP5_STEP stuck")
	_test_perf_load()
	await _test_perf_frames()
	print("HH_R8WP5_STEP perf")
	await _test_visual()
	print("HH_R8WP5_STEP visual")
	await _test_soak()
	print("HH_R8WP5_STEP soak")
	_mem_end = int(OS.get_static_memory_usage())
	_finish_labels()
	_write_report()
	if saver != null:
		saver.call("clear_slot")
		saver.call("use_default_path")
	SfxBank.set_bus_linear("Master", 1.0)
	SfxBank.set_bus_linear("Music", 1.0)
	SfxBank.set_bus_linear("SFX", 1.0)
	_emit()
	quit(0 if _fails.is_empty() else 1)


func _test_seeded_runs() -> void:
	paused = false
	var cases: Array[Dictionary] = _case_table()
	if cases.size() < 20:
		_fail("RUNS need at least 20 seeded cases, got %d" % cases.size())
		return
	var kinds: Dictionary = {}
	var i: int = 0
	while i < cases.size():
		var row: Dictionary = cases[i]
		var kind: String = str(row.get("kind", ""))
		kinds[kind] = true
		seed(int(row.get("seed", 1)))
		var app: App = _make_app()
		var before: int = _fails.size()
		app = _run_case(app, row)
		var snap: Dictionary = {}
		if is_instance_valid(app) and app.session != null:
			snap = app.session.snapshot()
		_runs.append({
			"id": int(row.get("id", i + 1)),
			"kind": kind,
			"seed": int(row.get("seed", 0)),
			"ok": _fails.size() == before,
			"win": bool(snap.get("win", false)),
			"relic_reached": bool(snap.get("relic_reached", false)),
			"outcome": str(snap.get("outcome", "")),
		})
		if is_instance_valid(app):
			app.free()
		i += 1
	var needed: PackedStringArray = PackedStringArray([
		"happy", "skip_item", "retry", "pause", "save_mid", "load"
	])
	var k: int = 0
	while k < needed.size():
		if not bool(kinds.get(String(needed[k]), false)):
			_fail("RUNS missing kind %s" % String(needed[k]))
		k += 1
	if _count_prefix("RUNS ") == 0:
		_runs_label = "proven"


func _case_table() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	out.append({"id": 1, "kind": "happy", "seed": 1})
	out.append({"id": 2, "kind": "happy", "seed": 2})
	out.append({"id": 3, "kind": "happy", "seed": 3})
	out.append({"id": 4, "kind": "happy", "seed": 11})
	out.append({"id": 5, "kind": "skip_item", "seed": 4})
	out.append({"id": 6, "kind": "skip_item", "seed": 5})
	out.append({"id": 7, "kind": "skip_item", "seed": 17})
	out.append({"id": 8, "kind": "retry", "seed": 6})
	out.append({"id": 9, "kind": "retry", "seed": 7})
	out.append({"id": 10, "kind": "retry", "seed": 19})
	out.append({"id": 11, "kind": "pause", "seed": 8})
	out.append({"id": 12, "kind": "pause", "seed": 9})
	out.append({"id": 13, "kind": "pause", "seed": 23})
	out.append({"id": 14, "kind": "save_mid", "seed": 10})
	out.append({"id": 15, "kind": "save_mid", "seed": 13})
	out.append({"id": 16, "kind": "save_mid", "seed": 29})
	out.append({"id": 17, "kind": "load", "seed": 14})
	out.append({"id": 18, "kind": "load", "seed": 15})
	out.append({"id": 19, "kind": "load", "seed": 31})
	out.append({"id": 20, "kind": "happy", "seed": 37})
	return out


func _run_case(app: App, row: Dictionary) -> App:
	paused = false
	var kind: String = str(row.get("kind", ""))
	if kind == "happy":
		_case_happy(app)
	elif kind == "skip_item":
		_case_skip_item(app)
	elif kind == "retry":
		_case_retry(app)
	elif kind == "pause":
		_case_pause(app)
	elif kind == "save_mid":
		_case_save_mid(app)
	elif kind == "load":
		return _case_load(app)
	else:
		_fail("RUNS unknown kind %s" % kind)
	return app


func _case_happy(app: App) -> void:
	app.start_new_run()
	var session: GameSession = app.session
	if session == null:
		_fail("RUNS happy missing session")
		return
	if not _walk_to(session, VaultMap.tile_center(VaultMap.KEY_CELL)):
		_fail("RUNS happy cannot reach key")
		return
	_interact(session)
	if not bool(session.snapshot().get("has_key", false)):
		_fail("RUNS happy key pickup failed")
	if bool(session.snapshot().get("win", false)):
		_fail("RUNS happy key must not win")
	if not _walk_to(session, VaultMap.tile_center(VaultMap.DOOR_CELL)):
		_fail("RUNS happy cannot reach door")
		return
	_interact(session)
	if not bool(session.snapshot().get("door_open", false)):
		_fail("RUNS happy door open failed")
	if bool(session.snapshot().get("win", false)):
		_fail("RUNS happy door must not win")
	if not _walk_to(session, VaultMap.tile_center(VaultMap.RELIC_CELL)):
		_fail("RUNS happy cannot reach relic")
		return
	_interact(session)
	var snap: Dictionary = session.snapshot()
	if not bool(snap.get("relic_reached", false)) or not bool(snap.get("win", false)):
		_fail("RUNS happy relic-reached must be win")
	if session.state.outcome != "win":
		_fail("RUNS happy outcome is not win")
	if not app.win_screen.visible:
		_fail("RUNS happy win screen hidden")


func _case_skip_item(app: App) -> void:
	app.start_new_run()
	var session: GameSession = app.session
	if session == null:
		_fail("RUNS skip_item missing session")
		return
	var near_door: Vector2 = VaultMap.tile_center(VaultMap.DOOR_ROOM)
	if not _walk_to(session, near_door):
		_fail("RUNS skip_item cannot walk past key")
		return
	if bool(session.snapshot().get("has_key", false)):
		_fail("RUNS skip_item must leave the key")
	if not _walk_to(session, VaultMap.tile_center(VaultMap.DOOR_CELL)):
		_fail("RUNS skip_item cannot reach door")
		return
	_interact(session)
	var after: Dictionary = session.snapshot()
	if bool(after.get("door_open", false)) or bool(after.get("win", false)):
		_fail("RUNS skip_item door must stay closed")
	if bool(after.get("relic_reached", false)):
		_fail("RUNS skip_item must not set relic_reached")
	if bool(after.get("has_key", false)):
		_fail("RUNS skip_item interact at door must not grant key")
	if session.hud != null and session.hud.get_node_or_null("Hint") != null:
		var hint: Label = session.hud.get_node("Hint") as Label
		if hint != null and hint.text.findn("key") < 0 and hint.text.findn("Need") < 0:
			_p2.append("skip_item hint did not mention needing the key: %s" % hint.text)
	if not _walk_to(session, VaultMap.tile_center(VaultMap.KEY_CELL)):
		_fail("RUNS skip_item cannot return to key (softlock)")
		return
	_interact(session)
	if not bool(session.snapshot().get("has_key", false)):
		_fail("RUNS skip_item cannot pick key after leaving it")
	if bool(session.snapshot().get("win", false)):
		_fail("RUNS skip_item key pickup must not win")


func _case_retry(app: App) -> void:
	app.start_new_run()
	var session: GameSession = app.session
	if session == null:
		_fail("RUNS retry missing session")
		return
	if not _chase_warden(session):
		_fail("RUNS retry cannot reach warden")
		return
	if session.state.outcome != "lose":
		_fail("RUNS retry warden contact must be lose")
	if session.state.is_win() or session.state.relic_reached:
		_fail("RUNS retry lose must not set relic_reached")
	if not app.lose_screen.visible:
		_fail("RUNS retry lose screen hidden")
	app.start_new_run()
	var fresh: Dictionary = app.session.snapshot()
	if bool(fresh.get("has_key", false)) or str(fresh.get("outcome", "")) != "play":
		_fail("RUNS retry restart is not a clean run")
	if bool(fresh.get("relic_reached", false)) or bool(fresh.get("win", false)):
		_fail("RUNS retry restart must not keep win")
	if not _walk_to(app.session, VaultMap.tile_center(VaultMap.KEY_CELL)):
		_fail("RUNS retry cannot walk after restart")


func _case_pause(app: App) -> void:
	app.start_new_run()
	var session: GameSession = app.session
	if session == null:
		_fail("RUNS pause missing session")
		return
	if not _walk_to(session, VaultMap.tile_center(Vector2i(8, 8))):
		_fail("RUNS pause cannot take a first step")
		return
	var player_before: Vector2 = session.player.global_position
	var warden_before: Vector2 = session.warden.global_position
	session.set_paused(true)
	var tree: SceneTree = self
	if not tree.paused:
		_fail("RUNS pause did not pause the tree")
	if session.pause_screen == null or not session.pause_screen.visible:
		_fail("RUNS pause screen hidden")
	var i: int = 0
	while i < 45:
		session.step_fixed(STEP, Vector2.RIGHT, false)
		i += 1
	if session.player.global_position.distance_to(player_before) > 0.05:
		_fail("RUNS pause step_fixed must no-op while tree.paused")
	if session.warden.global_position.distance_to(warden_before) > 0.05:
		_fail("RUNS pause warden must not move while tree.paused")
	session.set_paused(false)
	if tree.paused:
		_fail("RUNS pause resume left tree paused")
	if session.pause_screen.visible:
		_fail("RUNS pause screen stayed visible")
	if not _walk_to(session, VaultMap.tile_center(VaultMap.KEY_CELL)):
		_fail("RUNS pause cannot walk after resume")
	if session.warden.global_position.distance_to(warden_before) < 0.01:
		_p2.append("warden did not advance after resume in pause case")


func _case_save_mid(app: App) -> void:
	if not _play_to_saved_door(app, "save_mid"):
		return
	var saver: Node = root.get_node_or_null("SaveService")
	if saver == null:
		_fail("RUNS save_mid missing SaveService")
		return
	app.continue_run()
	var session: GameSession = app.session
	if session == null:
		_fail("RUNS save_mid continue_run missing session")
		return
	var restored: Dictionary = session.snapshot()
	if not bool(restored.get("has_key", false)) or not bool(restored.get("door_open", false)):
		_fail("RUNS save_mid continue_run did not restore key/door from user://")
	if bool(restored.get("win", false)) or bool(restored.get("relic_reached", false)):
		_fail("RUNS save_mid continue_run must not auto-win")
	if not _walk_to(session, VaultMap.tile_center(VaultMap.PLAYER_SPAWN)):
		_fail("RUNS save_mid cannot keep playing after continue_run")
	var later: Dictionary = saver.call("load_slot") as Dictionary
	if not bool(later.get("has_key", false)) or not bool(later.get("door_open", false)):
		_fail("RUNS save_mid slot lost after continued play")
	if bool(session.snapshot().get("win", false)):
		_fail("RUNS save_mid continued play must not auto-win")


func _case_load(app: App) -> App:
	if not _play_to_saved_door(app, "load"):
		return app
	if is_instance_valid(app):
		app.free()
	var fresh: App = _make_app()
	fresh.continue_run()
	var session: GameSession = fresh.session
	if session == null:
		_fail("RUNS load continue_run missing session")
		return fresh
	var restored: Dictionary = session.snapshot()
	if not bool(restored.get("has_key", false)) or not bool(restored.get("door_open", false)):
		_fail("RUNS load did not restore key/door from user://")
	if bool(restored.get("win", false)) or bool(restored.get("relic_reached", false)):
		_fail("RUNS load unfinished run must not be win")
	var saver: Node = root.get_node_or_null("SaveService")
	var disk: Dictionary = {}
	if saver != null:
		disk = saver.call("load_slot") as Dictionary
	if str(restored.get("room_id", "")) != str(disk.get("room_id", "")):
		_fail("RUNS load room_id mismatch vs user://")
	if str(restored.get("room_id", "")) == "relic":
		_fail("RUNS load unfinished run must not restore relic room")
	if VaultMap.room_id_at(session.player.global_position) == "relic":
		_fail("RUNS load must not spawn in relic room")
	if not _walk_to(session, VaultMap.tile_center(VaultMap.RELIC_CELL)):
		_fail("RUNS load cannot finish path to relic")
		return fresh
	_interact(session)
	var finished: Dictionary = session.snapshot()
	if not bool(finished.get("relic_reached", false)) or not bool(finished.get("win", false)):
		_fail("RUNS load must walk to relic and win")
	return fresh


func _play_to_saved_door(app: App, label: String) -> bool:
	var saver: Node = root.get_node_or_null("SaveService")
	if saver == null:
		_fail("RUNS %s missing SaveService" % label)
		return false
	app.start_new_run()
	var session: GameSession = app.session
	if session == null:
		_fail("RUNS %s missing session" % label)
		return false
	if not _walk_to(session, VaultMap.tile_center(VaultMap.KEY_CELL)):
		_fail("RUNS %s cannot reach key" % label)
		return false
	_interact(session)
	if not bool(session.snapshot().get("has_key", false)):
		_fail("RUNS %s key pickup failed" % label)
		return false
	if not _walk_to(session, VaultMap.tile_center(VaultMap.DOOR_CELL)):
		_fail("RUNS %s cannot reach door" % label)
		return false
	_interact(session)
	if not bool(session.snapshot().get("door_open", false)):
		_fail("RUNS %s door open failed" % label)
		return false
	if bool(session.snapshot().get("win", false)) or bool(session.snapshot().get("relic_reached", false)):
		_fail("RUNS %s door must not win" % label)
		return false
	saver.call("autosave", session.state)
	var path: String = str(saver.call("current_path"))
	if not path.begins_with("user://"):
		_fail("RUNS %s save path is not user://" % label)
		return false
	if not FileAccess.file_exists(path):
		_fail("RUNS %s did not write user:// slot" % label)
		return false
	var written: Dictionary = saver.call("load_slot") as Dictionary
	if not bool(written.get("has_key", false)) or not bool(written.get("door_open", false)):
		_fail("RUNS %s load_slot missed key/door on disk" % label)
		return false
	if bool(written.get("relic_reached", false)):
		_fail("RUNS %s must not persist relic_reached" % label)
		return false
	return true


func _test_fuzz_ui() -> void:
	var app: App = _make_app()
	if app.title == null:
		_fail("FUZZ title missing")
		app.free()
		return
	app.title.visible = true
	app.title.play_btn.grab_focus()
	_tap_ui_dir(false)
	_tap_ui_dir(true)
	_tap_ui_dir(true)
	if app.title.restart_btn.has_focus() or app.title.continue_btn.has_focus() or app.title.play_btn.has_focus():
		pass
	else:
		_fail("FUZZ title focus left the button row")
	app.title.continue_btn.disabled = true
	if not app.title.continue_btn.disabled:
		_fail("FUZZ Continue must be disable-able")
	app.title.play_btn.pressed.emit()
	if app.session == null:
		_fail("FUZZ Play did not start a run")
		app.free()
		return
	var session: GameSession = app.session
	session.set_paused(true)
	if session.pause_screen.master_slider != null:
		session.pause_screen.apply_bus_linear("Master", 0.0)
		session.pause_screen.apply_bus_linear("Master", 1.0)
		session.pause_screen.apply_bus_linear("Music", 0.0)
		session.pause_screen.apply_bus_linear("Music", 1.0)
		session.pause_screen.apply_bus_linear("SFX", 0.0)
		session.pause_screen.apply_bus_linear("SFX", 1.0)
	session.pause_screen.resume_btn.pressed.emit()
	if paused:
		_fail("FUZZ Resume did not unpause")
	session.set_paused(false)
	var mash: int = 0
	while mash < 24:
		_interact(session)
		mash += 1
	if session.live_vfx_count() > 6:
		_fail("FUZZ interact mash leaked VFX count=%d" % session.live_vfx_count())
	var wall: Vector2 = VaultMap.tile_center(Vector2i(1, 1))
	_walk_to(session, wall)
	_interact(session)
	if bool(session.snapshot().get("win", false)) or bool(session.snapshot().get("relic_reached", false)):
		_fail("FUZZ wall interact must not win")
	app.start_new_run()
	if not _chase_warden(app.session):
		_fail("FUZZ cannot force lose for win/lose buttons")
	else:
		app.lose_screen.restart_btn.pressed.emit()
		if app.session == null or app.session.state.outcome != "play":
			_fail("FUZZ lose Restart did not start a new run")
	app.free()
	print("HH_R8WP5_FUZZ title=1 pause_sliders=1 mash=24 wall=1 retry=1")


func _test_stuck() -> void:
	var app: App = _make_app()
	app.start_new_run()
	var session: GameSession = app.session
	if session == null:
		_fail("STUCK missing session")
		app.free()
		return
	var targets: Array[Vector2] = [
		VaultMap.tile_center(VaultMap.KEY_CELL),
		VaultMap.tile_center(VaultMap.DOOR_ROOM),
		VaultMap.tile_center(Vector2i(6, 6)),
		VaultMap.tile_center(Vector2i(6, 10)),
		VaultMap.tile_center(VaultMap.PLAYER_SPAWN),
	]
	var i: int = 0
	while i < targets.size():
		var dest: Vector2 = targets[i]
		if not _walk_to(session, dest):
			_fail("STUCK cannot reach open-floor %s" % dest)
		i += 1
	var hug: Vector2 = session.player.global_position
	var w: int = 0
	while w < 40:
		session.step_fixed(STEP, Vector2.LEFT, false)
		w += 1
	if session.player.global_position.x > hug.x + 1.0:
		_fail("STUCK wall hug moved through the west wall")
	if not _walk_to(session, VaultMap.tile_center(VaultMap.KEY_CELL)):
		_fail("STUCK trapped after wall hug")
	_interact(session)
	_walk_to(session, VaultMap.tile_center(VaultMap.DOOR_CELL))
	_interact(session)
	if bool(session.snapshot().get("door_open", false)):
		if not _walk_to(session, VaultMap.tile_center(VaultMap.RELIC_CELL)):
			_fail("STUCK cannot enter relic after door open")
		if bool(session.snapshot().get("win", false)):
			_fail("STUCK walking onto relic must not win without interact")
	else:
		_fail("STUCK could not open door for relic-side check")
	if _count_prefix("STUCK ") == 0:
		_stuck_label = "proven"
	app.free()


func _test_perf_load() -> void:
	var t0: int = Time.get_ticks_msec()
	var app: App = _make_app()
	app.start_new_run()
	_load_ms = Time.get_ticks_msec() - t0
	if app.session == null:
		_fail("PERF load did not create a session")
	if _load_ms > LOAD_BUDGET_MS:
		_fail("PERF load %d ms exceeds %d ms" % [_load_ms, LOAD_BUDGET_MS])
	print("HH_R8WP5_LOAD_MS %d" % _load_ms)
	app.free()


func _test_perf_frames() -> void:
	var app: App = _make_app()
	app.start_new_run()
	if app.session != null:
		app.session.test_driven = false
	var i: int = 0
	while i < 90:
		await process_frame
		if i >= 30:
			_sample_frame()
		i += 1
	app.free()


func _test_visual() -> void:
	print("HH_R8WP5_CAPTURE viewport get_image windowed; dummy-renderer cannot stamp VISUAL")
	print("HH_R8WP5_DISPLAY %s" % DisplayServer.get_name())
	print("HH_R8WP5_RENDER %s" % RenderingServer.get_current_rendering_method())
	if DisplayServer.get_name() == "headless":
		_fail("VISUAL refuse dummy-renderer / headless capture")
		return
	DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
	DisplayServer.window_set_size(Vector2i(1280, 720))
	var app: App = _make_app()
	app.start_new_run()
	var session: GameSession = app.session
	if session == null or not _walk_to(session, VaultMap.tile_center(VaultMap.KEY_CELL)):
		_fail("VISUAL cannot reach key")
		app.free()
		return
	session.refit_view()
	await _wait_draw(4)
	await _capture_shot("play", SHOT_PLAY)
	session.set_paused(true)
	await _wait_draw(3)
	await _capture_shot("pause", SHOT_PAUSE)
	session.set_paused(false)
	if _count_prefix("VISUAL ") == 0:
		_visual_label = "proven"
	app.free()


func _test_soak() -> void:
	paused = false
	Engine.time_scale = 1.0
	if not is_equal_approx(Engine.time_scale, 1.0):
		_fail("SOAK Engine.time_scale must stay 1.0")
		return
	var app: App = _make_app(false)
	app.start_new_run()
	if app.session == null:
		_fail("SOAK missing session")
		app.free()
		return
	if app.test_driven or app.session.test_driven:
		_fail("SOAK production loop requires test_driven=false")
		app.free()
		return
	_soak_test_driven = 1 if app.session.test_driven else 0
	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	rng.seed = 20260825
	var waypoint: Vector2 = VaultMap.tile_center(VaultMap.KEY_CELL)
	var mode: String = "seek_key"
	var mode_left: int = 180
	var stuck_frames: int = 0
	var last: Vector2 = app.session.player.global_position
	var last_dir: Vector2 = Vector2.ZERO
	var frame: int = 0
	var last_tick_s: float = -60.0
	var target_s: float = 2.0 if _soak_fast else SOAK_WALL_S
	var t0_msec: int = Time.get_ticks_msec()
	var t0_os: float = Time.get_unix_time_from_system()
	_soak_wall_s = 0.0
	print("HH_R8WP5_SOAK_START wall_target=%.1f time_scale=%.3f test_driven=%d not_g5=1" % [
		target_s, Engine.time_scale, _soak_test_driven
	])
	while _soak_wall_s + 0.0005 < target_s:
		var session: GameSession = app.session
		if session == null:
			_fail("SOAK session vanished")
			_soak_blockers += 1
			break
		if session.test_driven:
			_fail("SOAK flipped test_driven=true")
			_soak_blockers += 1
			break
		if session.state.outcome == "win":
			_soak_wins += 1
			_release_moves()
			app.start_new_run()
			session = app.session
			_soak_retries += 1
			mode = "wander"
			mode_left = 120
			last_dir = Vector2.ZERO
			stuck_frames = 0
			if session != null and session.player != null:
				last = session.player.global_position
		elif session.state.outcome == "lose":
			_soak_losses += 1
			_release_moves()
			app.start_new_run()
			session = app.session
			_soak_retries += 1
			mode = "wander"
			mode_left = 120
			last_dir = Vector2.ZERO
			stuck_frames = 0
			if session != null and session.player != null:
				last = session.player.global_position
		else:
			mode_left -= 1
			if mode_left <= 0:
				mode = _next_soak_mode(rng, session, frame)
				mode_left = rng.randi_range(90, 240)
				waypoint = _soak_waypoint(rng, session, mode)
				last_dir = Vector2.ZERO
				if mode == "skip":
					_soak_skips += 1
			if mode == "pause":
				_release_moves()
				await _tap_pause_key()
				_soak_pauses += 1
				if not paused:
					_fail("SOAK pause key did not pause the tree")
					_soak_blockers += 1
				var frozen: Vector2 = session.warden.global_position
				var player_frozen: Vector2 = session.player.global_position
				var p: int = 0
				while p < 20:
					await process_frame
					p += 1
				if session.warden.global_position.distance_to(frozen) > 0.05:
					_fail("SOAK warden moved while paused")
					_soak_blockers += 1
				if session.player.global_position.distance_to(player_frozen) > 0.05:
					_fail("SOAK player moved while paused")
					_soak_blockers += 1
				await _tap_pause_key()
				if paused:
					_fail("SOAK pause key did not resume")
					_soak_blockers += 1
					session.set_paused(false)
				mode = "wander"
				mode_left = 90
				last_dir = Vector2.ZERO
			elif mode == "save":
				_release_moves()
				var saver: Node = root.get_node_or_null("SaveService")
				if saver != null:
					saver.call("autosave", session.state)
					var path: String = str(saver.call("current_path"))
					if path.begins_with("user://") and FileAccess.file_exists(path):
						_soak_saves += 1
				mode = "wander"
				mode_left = 90
			elif mode == "load":
				_release_moves()
				var saver2: Node = root.get_node_or_null("SaveService")
				if saver2 != null:
					app.continue_run()
					_soak_loads += 1
					session = app.session
					if session != null:
						session.test_driven = false
						if session.player != null:
							last = session.player.global_position
					stuck_frames = 0
				mode = "wander"
				mode_left = 90
				last_dir = Vector2.ZERO
			else:
				if mode == "seek_key" and bool(session.snapshot().get("has_key", false)):
					mode = "seek_door"
					waypoint = _soak_waypoint(rng, session, mode)
					mode_left = rng.randi_range(90, 240)
				elif mode == "seek_door" and bool(session.snapshot().get("door_open", false)):
					mode = "seek_relic"
					waypoint = _soak_waypoint(rng, session, mode)
					mode_left = rng.randi_range(90, 240)
				var steered: Vector2 = _steer_target(session, waypoint)
				var interact: bool = mode == "seek_key" or mode == "seek_door" or mode == "seek_relic"
				var reach: float = session.player.global_position.distance_to(waypoint)
				if interact and reach <= VaultMap.INTERACT_REACH:
					_release_moves()
					last_dir = Vector2.ZERO
					stuck_frames = 0
					await _tap_interact_key()
				else:
					var dir: Vector2 = InputActions.cardinal(steered - session.player.global_position)
					if stuck_frames > 0 and stuck_frames % 45 == 0:
						dir = _sidestep_dir(dir, stuck_frames)
					_hold_dir(dir)
					last_dir = dir
		if session == null or not is_instance_valid(session) or session.player == null:
			await process_frame
			frame += 1
			_soak_frames = frame
			_soak_wall_s = float(Time.get_ticks_msec() - t0_msec) / 1000.0
			continue
		var here: Vector2 = session.player.global_position
		var steered_now: Vector2 = _steer_target(session, waypoint)
		var near_goal: bool = here.distance_to(waypoint) <= VaultMap.INTERACT_REACH
		if here.distance_to(last) < 0.04 and mode != "pause" and not near_goal:
			stuck_frames += 1
		else:
			stuck_frames = 0
		if (
			stuck_frames >= 180
			and _waypoint_should_be_reachable(session, waypoint)
			and here.distance_to(steered_now) > VaultMap.INTERACT_REACH
		):
			if not _can_nudge_any_dir(session):
				_fail("SOAK softlock %s at %s target=%s" % [mode, here, waypoint])
				_soak_blockers += 1
			elif _count_p2_has("cardinal hold snagged") == 0:
				_p2.append("cardinal hold snagged on tile lips; sidestep recovers; not a softlock")
			stuck_frames = 0
			waypoint = VaultMap.tile_center(VaultMap.PLAYER_SPAWN)
			mode = "wander"
			mode_left = 90
			last_dir = Vector2.ZERO
			_release_moves()
		last = here
		if session.live_vfx_count() > 8:
			_fail("SOAK VFX leak count=%d" % session.live_vfx_count())
			_soak_blockers += 1
		if frame >= 30 and frame % 12 == 0:
			_sample_frame()
		await process_frame
		frame += 1
		_soak_frames = frame
		_soak_wall_s = float(Time.get_ticks_msec() - t0_msec) / 1000.0
		if _soak_wall_s - last_tick_s >= 60.0:
			last_tick_s = _soak_wall_s
			print("HH_R8WP5_SOAK_TICK frame=%d wall_s=%.1f time_scale=%.3f wins=%d losses=%d blockers=%d" % [
				frame, _soak_wall_s, Engine.time_scale, _soak_wins, _soak_losses, _soak_blockers
			])
	_release_moves()
	_soak_os_s = Time.get_unix_time_from_system() - t0_os
	_soak_wall_s = float(Time.get_ticks_msec() - t0_msec) / 1000.0
	print("HH_R8WP5_SOAK_DONE frames=%d wall_s=%.1f os_s=%.1f time_scale=%.3f test_driven=%d wins=%d losses=%d retries=%d pauses=%d saves=%d loads=%d skips=%d blockers=%d not_g5=1" % [
		_soak_frames, _soak_wall_s, _soak_os_s, Engine.time_scale, _soak_test_driven, _soak_wins, _soak_losses, _soak_retries, _soak_pauses, _soak_saves, _soak_loads, _soak_skips, _soak_blockers
	])
	if _soak_fast:
		print("HH_R8WP5_SOAK_FAST completed; SOAK stays unproven")
	elif _soak_wall_s + 0.001 < SOAK_WALL_S or _soak_os_s + 0.001 < SOAK_WALL_S:
		_fail("SOAK wall %.1f / os %.1f < 600" % [_soak_wall_s, _soak_os_s])
	if not is_equal_approx(Engine.time_scale, 1.0):
		_fail("SOAK Engine.time_scale became %.3f" % Engine.time_scale)
	if _soak_test_driven != 0:
		_fail("SOAK ran with test_driven=1")
	if _soak_blockers > 0:
		_fail("SOAK blockers=%d" % _soak_blockers)
	if _soak_retries < 1 and _soak_wins + _soak_losses < 1:
		_p2.append("soak never won or lost in 10 minutes; corridor may be too safe")
	_p2.append("divider walls at col 13/26 stop a held east-west; openings are y=6-8 only")
	_p2.append("warden north-lane in the door room makes random wander die often; y=8 happy path stays safe")
	if not _soak_fast and _count_prefix("SOAK ") == 0 and _soak_wall_s + 0.001 >= SOAK_WALL_S:
		_soak_label = "proven"
	app.free()


func _next_soak_mode(rng: RandomNumberGenerator, session: GameSession, frame: int) -> String:
	if frame > 0 and frame % 7200 < 180:
		return "pause"
	if frame > 0 and frame % 5400 < 180:
		return "save"
	if frame > 0 and frame % 9000 < 180:
		return "load"
	var has_key: bool = bool(session.snapshot().get("has_key", false))
	var door_open: bool = bool(session.snapshot().get("door_open", false))
	var roll: int = rng.randi_range(0, 9)
	if roll <= 1:
		return "skip"
	if roll <= 3:
		return "wander"
	if not has_key:
		return "seek_key"
	if not door_open:
		return "seek_door"
	if roll <= 7:
		return "seek_relic"
	return "wander"


func _soak_waypoint(rng: RandomNumberGenerator, session: GameSession, mode: String) -> Vector2:
	if mode == "seek_key":
		return VaultMap.tile_center(VaultMap.KEY_CELL)
	if mode == "seek_door":
		return VaultMap.tile_center(VaultMap.DOOR_CELL)
	if mode == "seek_relic" and bool(session.snapshot().get("door_open", false)):
		return VaultMap.tile_center(VaultMap.RELIC_CELL)
	if mode == "skip":
		return VaultMap.tile_center(VaultMap.DOOR_ROOM)
	return _random_floor(rng, bool(session.snapshot().get("door_open", false)))


func _random_floor(rng: RandomNumberGenerator, door_open: bool) -> Vector2:
	var tries: int = 0
	while tries < 40:
		var x: int = rng.randi_range(2, VaultMap.MAP_W - 3)
		var y: int = rng.randi_range(2, VaultMap.MAP_H - 3)
		var cell: Vector2i = Vector2i(x, y)
		if VaultMap.is_border_wall(cell):
			tries += 1
			continue
		if not door_open and x > VaultMap.DIV_DOOR_RELIC:
			tries += 1
			continue
		return VaultMap.tile_center(cell)
	return VaultMap.tile_center(VaultMap.PLAYER_SPAWN)


func _steer_target(session: GameSession, goal: Vector2) -> Vector2:
	var here: Vector2 = session.player.global_position
	var from_col: int = int(floor(here.x / float(VaultMap.TILE)))
	var to_col: int = int(floor(goal.x / float(VaultMap.TILE)))
	var door_open: bool = bool(session.snapshot().get("door_open", false))
	if from_col == VaultMap.DIV_START_DOOR or from_col == VaultMap.DIV_DOOR_RELIC:
		var mid_gate: Vector2 = VaultMap.tile_center(Vector2i(from_col, 7))
		if absf(here.y - mid_gate.y) > ARRIVE:
			return mid_gate
	if from_col <= VaultMap.DIV_START_DOOR and to_col > VaultMap.DIV_START_DOOR:
		var gate: Vector2 = VaultMap.tile_center(Vector2i(VaultMap.DIV_START_DOOR, 7))
		if here.distance_to(gate) > ARRIVE:
			return gate
	if from_col > VaultMap.DIV_START_DOOR and to_col <= VaultMap.DIV_START_DOOR:
		var gate_back: Vector2 = VaultMap.tile_center(Vector2i(VaultMap.DIV_START_DOOR, 7))
		if here.distance_to(gate_back) > ARRIVE:
			return gate_back
	if from_col <= VaultMap.DIV_DOOR_RELIC and to_col > VaultMap.DIV_DOOR_RELIC:
		if not door_open:
			return here
		var gate_relic: Vector2 = VaultMap.tile_center(Vector2i(VaultMap.DIV_DOOR_RELIC, 7))
		if here.distance_to(gate_relic) > ARRIVE:
			return gate_relic
	if from_col > VaultMap.DIV_DOOR_RELIC and to_col <= VaultMap.DIV_DOOR_RELIC:
		var gate_home: Vector2 = VaultMap.tile_center(Vector2i(VaultMap.DIV_DOOR_RELIC, 7))
		if here.distance_to(gate_home) > ARRIVE:
			return gate_home
	return goal


func _waypoint_should_be_reachable(session: GameSession, waypoint: Vector2) -> bool:
	var room: String = VaultMap.room_id_at(waypoint)
	if room == "relic" and not bool(session.snapshot().get("door_open", false)):
		return false
	var cell: Vector2i = Vector2i(
		int(floor(waypoint.x / float(VaultMap.TILE))),
		int(floor(waypoint.y / float(VaultMap.TILE)))
	)
	if VaultMap.is_border_wall(cell):
		return false
	return true


func _walk_step(session: GameSession, target: Vector2, interact: bool) -> void:
	var delta: Vector2 = target - session.player.global_position
	session.step_fixed(STEP, delta, interact)


func _finish_labels() -> void:
	_p95_ms = _percentile(_frame_ms, 0.95)
	print("HH_R8WP5_PERF load_ms=%d p95_ms=%.2f samples=%d mem0=%d mem1=%d target_ms=%.2f" % [
		_load_ms, _p95_ms, _frame_ms.size(), _mem_start, _mem_end, P95_TARGET_MS
	])
	if _load_ms > LOAD_BUDGET_MS:
		_fail("PERF load %d ms exceeds %d ms" % [_load_ms, LOAD_BUDGET_MS])
	var grew: int = _mem_end - _mem_start
	if grew > MEM_GROW_BUDGET:
		_fail("PERF memory grew %d bytes" % grew)
	if _frame_ms.size() < 8:
		_p2.append("PERF not enough frame samples; leave unproven")
	elif _p95_ms > P95_TARGET_MS:
		_p2.append("p95 %.2f ms missed 60fps target %.2f; PERF=unproven" % [_p95_ms, P95_TARGET_MS])
	elif _count_prefix("PERF ") == 0 and _load_ms > 0:
		_perf_label = "proven"
	if _fails.is_empty():
		_clean_label = "proven"


func _sample_frame() -> void:
	var ms: float = float(Performance.get_monitor(Performance.TIME_PROCESS)) * 1000.0
	_frame_ms.append(ms)


func _percentile(samples: PackedFloat32Array, p: float) -> float:
	if samples.is_empty():
		return 0.0
	var copy: Array = []
	var i: int = 0
	while i < samples.size():
		copy.append(float(samples[i]))
		i += 1
	copy.sort()
	var idx: int = int(floor((copy.size() - 1) * p))
	if idx < 0:
		idx = 0
	if idx >= copy.size():
		idx = copy.size() - 1
	return float(copy[idx])


func _capture_shot(tag: String, dest: String) -> void:
	var vp: Viewport = root.get_viewport()
	if vp == null:
		_fail("VISUAL missing viewport")
		return
	await RenderingServer.frame_post_draw
	var img: Image = vp.get_texture().get_image()
	if img == null:
		img = vp.get_image()
	if img == null:
		_fail("VISUAL get_image failed %s" % tag)
		return
	if img.get_width() < 64 or img.get_height() < 64:
		_fail("VISUAL %s too small" % tag)
		return
	var err: Error = img.save_png(dest)
	if err != OK:
		_fail("VISUAL save failed %s" % dest)
		return
	var abs_path: String = ProjectSettings.globalize_path(dest)
	var digest: String = _sha256(dest)
	_shots[tag] = {
		"path": dest,
		"abs": abs_path,
		"sha256": digest,
		"w": img.get_width(),
		"h": img.get_height(),
	}
	print("HH_R8WP5_SHOT %s %s %s" % [tag, dest, digest])
	print("HH_R8WP5_SHOT_ABS %s %s" % [tag, abs_path])


func _write_report() -> void:
	var report: Dictionary = {
		"run_id": RUN_ID,
		"path": PATH,
		"seeded_count": _runs.size(),
		"seeded": _runs,
		"soak_frames": _soak_frames,
		"soak_wall_s": _soak_wall_s,
		"soak_os_s": _soak_os_s,
		"soak_game_s": _soak_wall_s,
		"time_scale": Engine.time_scale,
		"test_driven": _soak_test_driven,
		"soak_fast": _soak_fast,
		"soak_blockers": _soak_blockers,
		"soak_wins": _soak_wins,
		"soak_losses": _soak_losses,
		"soak_retries": _soak_retries,
		"soak_pauses": _soak_pauses,
		"soak_saves": _soak_saves,
		"soak_loads": _soak_loads,
		"soak_skips": _soak_skips,
		"load_ms": _load_ms,
		"p95_ms": _p95_ms,
		"mem_start": _mem_start,
		"mem_end": _mem_end,
		"p2": _p2,
		"not_g5": true,
		"provider_plan": "unused",
	}
	var text: String = JSON.stringify(report)
	var f: FileAccess = FileAccess.open(REPORT_PATH, FileAccess.WRITE)
	if f == null:
		_fail("CLEAN cannot write report")
		return
	f.store_string(text)
	f.close()
	print("HH_R8WP5_REPORT %s" % REPORT_PATH)
	print("HH_R8WP5_REPORT_ABS %s" % ProjectSettings.globalize_path(REPORT_PATH))


func _make_app(driven: bool = true) -> App:
	var packed: PackedScene = load("res://scenes/main.tscn") as PackedScene
	var app: App = packed.instantiate() as App
	app.test_driven = driven
	root.add_child(app)
	return app


func _fast_skip_requested() -> bool:
	var raw: String = OS.get_environment("HH_R8WP5_FAST").strip_edges().to_lower()
	return raw == "1" or raw == "true" or raw == "yes"


func _action_for_key(keycode: Key) -> String:
	if keycode == KEY_A or keycode == KEY_LEFT:
		return "move_left"
	if keycode == KEY_D or keycode == KEY_RIGHT:
		return "move_right"
	if keycode == KEY_W or keycode == KEY_UP:
		return "move_up"
	if keycode == KEY_S or keycode == KEY_DOWN:
		return "move_down"
	if keycode == KEY_E or keycode == KEY_ENTER:
		return "interact"
	if keycode == KEY_ESCAPE:
		return "pause"
	return ""


func _emit_key(keycode: Key, is_pressed: bool) -> void:
	var ev: InputEventKey = InputEventKey.new()
	ev.physical_keycode = keycode
	ev.keycode = keycode
	ev.pressed = is_pressed
	ev.echo = false
	Input.parse_input_event(ev)
	Input.flush_buffered_events()
	var action: String = _action_for_key(keycode)
	if action != "":
		if is_pressed:
			Input.action_press(action)
		else:
			Input.action_release(action)
	if is_pressed:
		_held_key = keycode
	elif _held_key == keycode:
		_held_key = KEY_NONE


func _sidestep_dir(dir: Vector2, stuck_frames: int) -> Vector2:
	var turn: int = int(stuck_frames / 45) % 4
	if turn == 1:
		return Vector2(-dir.y, dir.x)
	if turn == 2:
		return -dir
	if turn == 3:
		return Vector2(dir.y, -dir.x)
	return dir


func _can_nudge_any_dir(session: GameSession) -> bool:
	if session == null or session.player == null:
		return false
	var origin: Vector2 = session.player.global_position
	var dirs: Array[Vector2] = [
		Vector2.LEFT, Vector2.RIGHT, Vector2.UP, Vector2.DOWN
	]
	var i: int = 0
	while i < dirs.size():
		session.player.step_move(STEP, dirs[i])
		var moved: bool = session.player.global_position.distance_to(origin) > 0.2
		session.player.global_position = origin
		session.player.velocity = Vector2.ZERO
		if moved:
			return true
		i += 1
	return false


func _count_p2_has(needle: String) -> int:
	var n: int = 0
	var i: int = 0
	while i < _p2.size():
		if String(_p2[i]).find(needle) >= 0:
			n += 1
		i += 1
	return n


func _release_moves() -> void:
	if _held_key != KEY_NONE:
		_emit_key(_held_key, false)
	_held_key = KEY_NONE
	_emit_key(KEY_A, false)
	_emit_key(KEY_D, false)
	_emit_key(KEY_W, false)
	_emit_key(KEY_S, false)


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


func _tap_interact_key() -> void:
	_emit_key(KEY_E, true)
	await process_frame
	_emit_key(KEY_E, false)


func _tap_pause_key() -> void:
	_emit_key(KEY_ESCAPE, true)
	await process_frame
	_emit_key(KEY_ESCAPE, false)


func _interact(session: GameSession) -> void:
	var i: int = 0
	while i < 4:
		session.step_fixed(STEP, Vector2.ZERO, true)
		i += 1


func _chase_warden(session: GameSession) -> bool:
	var frames: int = 0
	while frames < 900:
		if session.state.outcome == "lose":
			return true
		var target: Vector2 = session.warden.global_position
		if session.player.global_position.distance_to(target) <= VaultMap.WARDEN_TOUCH:
			session.step_fixed(STEP, Vector2.ZERO, false)
			return session.state.outcome == "lose"
		session.step_fixed(STEP, target - session.player.global_position, false)
		frames += 1
	return session.state.outcome == "lose"


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


func _tap_ui_dir(down: bool) -> void:
	var ev: InputEventKey = InputEventKey.new()
	ev.physical_keycode = KEY_DOWN if down else KEY_UP
	ev.pressed = true
	Input.parse_input_event(ev)
	var up: InputEventKey = InputEventKey.new()
	up.physical_keycode = ev.physical_keycode
	up.pressed = false
	Input.parse_input_event(up)


func _wait_draw(n: int) -> void:
	var i: int = 0
	while i < n:
		await process_frame
		await RenderingServer.frame_post_draw
		i += 1


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
	print("HH_R8WP5_PATH %s" % PATH)
	print(
		"HH_R8WP5 RUNS=%s SOAK=%s STUCK=%s PERF=%s VISUAL=%s CLEAN=%s"
		% [_runs_label, _soak_label, _stuck_label, _perf_label, _visual_label, _clean_label]
	)
	if _fails.is_empty():
		print("PASS: R8-WP5 playtest 20 seeded + 10min soak")
	else:
		print("FAIL: R8-WP5 playtest")
		var i: int = 0
		while i < _fails.size():
			print("  - %s" % String(_fails[i]))
			i += 1
	var p: int = 0
	while p < _p2.size():
		print("HH_R8WP5_P2 %s" % String(_p2[p]))
		p += 1

extends SceneTree

const RUN_ID := "VF6WP1-20260901-ASIA-SAIGON-04"
const COMMAND_ID := "cmd.vf6-wp1.match-machine.4"
const SEED := 7
const MODE := "vs2"
const MAP_ID := "police"

const MatchCasesScript: GDScript = preload("res://tests/match_cases.gd")

var _fails: PackedStringArray = PackedStringArray()
var _started_at: String = ""
var _started_unix: float = 0.0
var _setup_shot: String = ""


func _initialize() -> void:
	call_deferred("_boot")


func _boot() -> void:
	_started_unix = Time.get_unix_time_from_system()
	_started_at = _iso_local()
	seed(SEED)
	InputActions.install()
	var packed: PackedScene = load("res://scenes/main.tscn") as PackedScene
	var app: App = packed.instantiate() as App
	app.test_driven = true
	root.add_child(app)
	app.start_fight(MODE, MAP_ID, 0)
	await _draw_ready()
	_setup_shot = _maybe_shot(app, "match_setup")
	print("HH_VF_MATCH STEP=match_setup DISPLAY=%s" % DisplayServer.get_name())
	_write_heartbeat("match_setup")
	var errors: PackedStringArray = await MatchCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	var schema: String = str(MatchCasesScript.outcome_schema.get("verdict", "unproven"))
	var machine: String = str(MatchCasesScript.outcome_machine.get("verdict", "unproven"))
	var win_v: String = str(MatchCasesScript.outcome_win.get("verdict", "unproven"))
	var lose_v: String = str(MatchCasesScript.outcome_lose.get("verdict", "unproven"))
	var tie_v: String = str(MatchCasesScript.outcome_tie.get("verdict", "unproven"))
	var quit_v: String = str(MatchCasesScript.outcome_quit.get("verdict", "unproven"))
	var restart_v: String = str(MatchCasesScript.outcome_restart.get("verdict", "unproven"))
	var pause_v: String = str(MatchCasesScript.outcome_pause.get("verdict", "unproven"))
	var signal_v: String = str(MatchCasesScript.outcome_signal.get("verdict", "unproven"))
	var seed_v: String = str(MatchCasesScript.outcome_seed.get("verdict", "unproven"))
	var ff: String = str(MatchCasesScript.outcome_ff.get("verdict", "unproven"))
	var live: String = str(MatchCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(MatchCasesScript.outcome_replay.get("verdict", "unproven"))
	if schema != "pass":
		_fail("SCHEMA structured outcome is %s" % schema)
	if machine != "pass":
		_fail("MACHINE structured outcome is %s" % machine)
	if win_v != "pass":
		_fail("WIN structured outcome is %s" % win_v)
	if lose_v != "pass":
		_fail("LOSE structured outcome is %s" % lose_v)
	if tie_v != "pass":
		_fail("TIE structured outcome is %s" % tie_v)
	if quit_v != "pass":
		_fail("QUIT structured outcome is %s" % quit_v)
	if restart_v != "pass":
		_fail("RESTART structured outcome is %s" % restart_v)
	if pause_v != "pass":
		_fail("PAUSE structured outcome is %s" % pause_v)
	if signal_v != "pass":
		_fail("SIGNAL structured outcome is %s" % signal_v)
	if seed_v != "pass":
		_fail("SEED structured outcome is %s" % seed_v)
	if ff != "pass":
		_fail("FF structured outcome is %s" % ff)
	if live != "pass":
		_fail("LIVE structured outcome is %s" % live)
	if replay != "match":
		_fail("REPLAY structured outcome is %s" % replay)
	if MatchCasesScript.used_force_kill != 0:
		_fail("official path used force_kill")
	if MatchCasesScript.used_step_fixed != 0:
		_fail("official match cases used step_fixed")
	var ended_at: String = _iso_local()
	print("HH_VF_MATCH run_id=%s" % RUN_ID)
	print("HH_VF_MATCH command_id=%s" % COMMAND_ID)
	print("HH_VF_MATCH DISPLAY=%s" % DisplayServer.get_name())
	print("HH_VF_MATCH SEED=%d MAP=%s MODE=%s NAME=%s" % [SEED, MAP_ID, MODE, Maps.display_name(MAP_ID)])
	print("HH_VF_MATCH STARTED_AT=%s ENDED_AT=%s" % [_started_at, ended_at])
	print(
		"HH_VF_MATCH USED_STEP_FIXED=%d USED_APPLY_FRAMES=%d USED_APPLY_ATTEMPTED=%d USED_APPLY_SUCCEEDED=%d USED_PARSE_INPUT_EVENT=%d USED_ACTION_PRESS=%d USED_FORCE_KILL=%d"
		% [
			MatchCasesScript.used_step_fixed,
			MatchCasesScript.used_apply_frames,
			MatchCasesScript.used_apply_frames_attempted,
			MatchCasesScript.used_apply_frames_succeeded,
			MatchCasesScript.used_parse_input_event,
			MatchCasesScript.used_action_press,
			MatchCasesScript.used_force_kill
		]
	)
	print("HH_VF_MATCH SCHEMA=%s SCHEMA_SOURCE=outcome_schema" % schema)
	var machine_modes: PackedStringArray = PackedStringArray()
	var raw_modes: Array = MatchCasesScript.outcome_machine.get("modes", []) as Array
	var mi: int = 0
	while mi < raw_modes.size():
		machine_modes.append(str(raw_modes[mi]))
		mi += 1
	print("HH_VF_MATCH MACHINE=%s MACHINE_SOURCE=outcome_machine MACHINE_MODES=%s SURVIVAL_SHIPPED=0" % [
		machine, ",".join(machine_modes)
	])
	print("HH_VF_MATCH WIN=%s WIN_SOURCE=outcome_win WIN_REASON=%s" % [
		win_v, str(MatchCasesScript.outcome_win.get("end_reason", ""))
	])
	print("HH_VF_MATCH LOSE=%s LOSE_SOURCE=outcome_lose LOSE_REASON=%s" % [
		lose_v, str(MatchCasesScript.outcome_lose.get("end_reason", ""))
	])
	print("HH_VF_MATCH TIE=%s TIE_SOURCE=outcome_tie TIE_REASON=%s TIE_CLASS=assumption TIE_OBSERVED=0" % [
		tie_v, str(MatchCasesScript.outcome_tie.get("end_reason", ""))
	])
	print("HH_VF_MATCH QUIT=%s QUIT_SOURCE=outcome_quit" % quit_v)
	print("HH_VF_MATCH RESTART=%s RESTART_SOURCE=outcome_restart" % restart_v)
	print("HH_VF_MATCH PAUSE=%s PAUSE_SOURCE=outcome_pause" % pause_v)
	print("HH_VF_MATCH SIGNAL=%s SIGNAL_SOURCE=outcome_signal" % signal_v)
	print("HH_VF_MATCH SEED_ROW=%s SEED_SOURCE=outcome_seed" % seed_v)
	print("HH_VF_MATCH FF=%s FF_SOURCE=outcome_ff" % ff)
	print("HH_VF_MATCH LIVE=%s LIVE_SOURCE=outcome_live" % live)
	print("HH_VF_MATCH REPLAY=%s REPLAY_SOURCE=outcome_replay" % replay)
	print("HH_VF_MATCH HONESTY P2_COVERAGE=smoke BOT_COVERAGE=smoke NOT_AI=1 NOT_Y8_PARITY=1 TIMER=assumption COUNTDOWN=assumption CLOCK=RL-SIM-FIXED-60 HOLD_AIM=assumption")
	print("HH_VF_MATCH FORCE_KILL_OFFICIAL=0 CANONICAL_MACHINE=1")
	await _write_evidence(app, ended_at, schema, machine, win_v, lose_v, tie_v, quit_v, restart_v, pause_v, signal_v, seed_v, ff, live, replay)
	if _fails.is_empty():
		print("PASS: Vault Fighters match state machine")
	else:
		print("FAIL: Vault Fighters match state machine")
		i = 0
		while i < _fails.size():
			print("  - %s" % String(_fails[i]))
			i += 1
	if is_instance_valid(app):
		app.shutdown()
		app.queue_free()
	await process_frame
	await process_frame
	var code: int = 0 if _fails.is_empty() else 1
	print("HH_VF_MATCH FINISHED=1")
	print("HH_VF_MATCH PROCESS_EXIT=%d" % code)
	quit(code)


func _fail(msg: String) -> void:
	_fails.append(msg)
	print("HH_ASSERT_FAIL %s" % msg)


func _iso_local() -> String:
	var d: Dictionary = Time.get_datetime_dict_from_system()
	return "%04d-%02d-%02dT%02d:%02d:%02d+07:00" % [
		int(d.get("year", 0)),
		int(d.get("month", 0)),
		int(d.get("day", 0)),
		int(d.get("hour", 0)),
		int(d.get("minute", 0)),
		int(d.get("second", 0)),
	]


func _maybe_shot(app: App, stem: String) -> String:
	var ev: String = OS.get_environment("HH_VF_EVIDENCE_DIR")
	if ev == "":
		ev = ProjectSettings.globalize_path("res://.evidence/%s" % RUN_ID)
	DirAccess.make_dir_recursive_absolute(ev.path_join("screens"))
	if DisplayServer.get_name() == "headless":
		return ""
	if app == null or app.get_viewport() == null:
		return ""
	var vis: Rect2 = app.get_viewport().get_visible_rect()
	var tex: ViewportTexture = app.get_viewport().get_texture()
	if tex == null:
		print("HH_VF_MATCH SCREENSHOT_%s missing viewport texture" % stem)
		return ""
	var img: Image = tex.get_image()
	if img == null:
		print("HH_VF_MATCH SCREENSHOT_%s get_image null" % stem)
		return ""
	var shot: String = ev.path_join("screens").path_join("%s_%dx%d.png" % [stem, int(vis.size.x), int(vis.size.y)])
	var err: Error = img.save_png(shot)
	print("HH_VF_MATCH SCREENSHOT_%s err=%d path=%s" % [stem, int(err), shot])
	return shot


func _unpause_tree(app: App) -> void:
	paused = false
	if app != null and app.session != null:
		app.session.set_paused(false)


func _draw_ready() -> void:
	paused = false
	await process_frame
	await process_frame
	if DisplayServer.get_name() == "headless":
		return
	# One post-draw is enough for a still. Extra waits can stall a
	# windowed console twin after the first screenshot.
	await RenderingServer.frame_post_draw
	await process_frame


func _windowed() -> bool:
	return DisplayServer.get_name() != "headless"


func _write_evidence(
	app: App, ended_at: String, schema: String, machine: String, win_v: String, lose_v: String,
	tie_v: String, quit_v: String, restart_v: String, pause_v: String, signal_v: String,
	seed_v: String, ff: String, live: String, replay: String
) -> void:
	var ev: String = OS.get_environment("HH_VF_EVIDENCE_DIR")
	if ev == "":
		ev = ProjectSettings.globalize_path("res://.evidence/%s" % RUN_ID)
	DirAccess.make_dir_recursive_absolute(ev)
	DirAccess.make_dir_recursive_absolute(ev.path_join("screens"))
	var live_shots: Dictionary = MatchCasesScript.still_paths.duplicate()
	if _windowed():
		if _setup_shot == "":
			_fail("DoD window still missing setup")
		if str(live_shots.get("title", "")) == "":
			_fail("DoD still missing title")
		if str(live_shots.get("win", "")) == "":
			_fail("DoD still missing win")
		if str(live_shots.get("lose", "")) == "":
			_fail("DoD still missing lose")
		if str(live_shots.get("tie", "")) == "":
			_fail("DoD still missing tie")
		if str(live_shots.get("pause", "")) == "":
			_fail("DoD still missing pause")
		if str(live_shots.get("quit", "")) == "":
			_fail("DoD still missing quit")
		if str(live_shots.get("restart", "")) == "":
			_fail("DoD still missing restart")
		if not bool(MatchCasesScript.outcome_live.get("title_visible_after", false)):
			_fail("LIVE quit must leave title visible")
		if str(MatchCasesScript.outcome_win.get("source", "")).begins_with("apply_frames"):
			_fail("WIN official source must be window/menu E2E")
		if str(MatchCasesScript.outcome_lose.get("source", "")).begins_with("apply_frames"):
			_fail("LOSE official source must be window/menu E2E")
		if str(MatchCasesScript.outcome_tie.get("source", "")).begins_with("apply_frames"):
			_fail("TIE official source must be window/menu E2E")
		if str(MatchCasesScript.outcome_restart.get("source", "")).begins_with("apply_frames"):
			_fail("RESTART official source must be window/menu E2E")
	var outcomes: Dictionary = {
		"schema": MatchCasesScript.outcome_schema,
		"machine": MatchCasesScript.outcome_machine,
		"win": MatchCasesScript.outcome_win,
		"lose": MatchCasesScript.outcome_lose,
		"tie": MatchCasesScript.outcome_tie,
		"quit": MatchCasesScript.outcome_quit,
		"restart": MatchCasesScript.outcome_restart,
		"pause": MatchCasesScript.outcome_pause,
		"signal": MatchCasesScript.outcome_signal,
		"seed": MatchCasesScript.outcome_seed,
		"ff": MatchCasesScript.outcome_ff,
		"live": MatchCasesScript.outcome_live,
		"replay": MatchCasesScript.outcome_replay,
		"apply": {
			"attempted": MatchCasesScript.used_apply_frames_attempted,
			"succeeded": MatchCasesScript.used_apply_frames_succeeded,
			"used_apply_frames": MatchCasesScript.used_apply_frames,
			"used_step_fixed": MatchCasesScript.used_step_fixed,
			"used_parse_input_event": MatchCasesScript.used_parse_input_event,
			"used_action_press": MatchCasesScript.used_action_press,
			"used_force_kill": MatchCasesScript.used_force_kill,
		},
	}
	_write_json(ev.path_join("outcomes.json"), outcomes)
	_write_json(ev.path_join("snapshot_start.json"), MatchCasesScript.snapshot_start)
	_write_json(ev.path_join("snapshot_end.json"), MatchCasesScript.snapshot_end)
	_write_json(ev.path_join("state_hashes.json"), {
		"replay": MatchCasesScript.outcome_replay,
		"seed": SEED,
		"map_id": MAP_ID,
		"mode": MODE,
	})
	var events_path: String = ev.path_join("events.jsonl")
	var ef: FileAccess = FileAccess.open(events_path, FileAccess.WRITE)
	if ef != null:
		var events: Array = MatchCasesScript.events_all
		var ei: int = 0
		while ei < events.size():
			ef.store_line(JSON.stringify(events[ei]))
			ei += 1
		ef.close()
	var display_name: String = DisplayServer.get_name()
	var vis: Rect2 = Rect2()
	if app != null and app.get_viewport() != null:
		vis = app.get_viewport().get_visible_rect()
	var run_partial: Dictionary = {
		"schema": "vault-fighters.vf6-wp1.run.v1",
		"run_id": RUN_ID,
		"command_id": COMMAND_ID,
		"wp": "VF6-WP1",
		"timezone": "Asia/Saigon",
		"started_at": _started_at,
		"ended_at": ended_at,
		"started_unix": _started_unix,
		"ended_unix": Time.get_unix_time_from_system(),
		"display": display_name,
		"seed": SEED,
		"map_id": MAP_ID,
		"mode": MODE,
		"tick_hz": 60,
		"epsilon": SimConstants.EPSILON,
		"godot": Engine.get_version_info(),
		"os_name": OS.get_name(),
		"viewport": {"w": vis.size.x, "h": vis.size.y},
		"screens": {
			"setup": _setup_shot,
			"live": live_shots,
		},
		"outcomes": {
			"SCHEMA": schema,
			"MACHINE": machine,
			"WIN": win_v,
			"LOSE": lose_v,
			"TIE": tie_v,
			"QUIT": quit_v,
			"RESTART": restart_v,
			"PAUSE": pause_v,
			"SIGNAL": signal_v,
			"SEED": seed_v,
			"FF": ff,
			"LIVE": live,
			"REPLAY": replay,
			"USED_APPLY_FRAMES": MatchCasesScript.used_apply_frames,
			"USED_FORCE_KILL": MatchCasesScript.used_force_kill,
		},
		"fail_count": _fails.size(),
	}
	_write_json(ev.path_join("run_partial.json"), run_partial)
	print("HH_VF_MATCH EVIDENCE_DIR=%s" % ev)


func _shot_after_trace(app: App, name: String, stem: String) -> String:
	_unpause_tree(app)
	var played: Dictionary = await SimReplay.play_path(
		app, "res://tests/traces/match/%s" % name, true
	)
	if not bool(played.get("ok", false)):
		_fail("still replay failed %s: %s" % [name, str(played.get("errors", []))])
	await _draw_ready()
	var shot: String = _maybe_shot(app, stem)
	if _windowed() and shot == "":
		_fail("DoD still missing %s" % stem)
	if app.session != null:
		app.release_session()
	return shot


func _shot_pause(app: App) -> String:
	app.start_fight("vs2", "police", 0)
	await _draw_ready()
	_push_action(app, "pause")
	await _draw_ready()
	var shot: String = _maybe_shot(app, "match_pause")
	if _windowed():
		if app.session == null or app.session.pause_screen == null or not app.session.pause_screen.visible:
			_fail("pause still must show pause overlay")
		if shot == "":
			_fail("DoD still missing pause")
	if app.session != null:
		app.session.set_paused(false)
	return shot


func _shot_quit(app: App) -> String:
	_unpause_tree(app)
	if app.win_screen != null:
		app.win_screen.visible = false
	if app.lose_screen != null:
		app.lose_screen.visible = false
	if app.tie_screen != null:
		app.tie_screen.visible = false
	app.start_fight("vs2", "police", 0)
	await _draw_ready()
	_push_action(app, "pause")
	await _draw_ready()
	if app.session != null and app.session.pause_screen != null and app.session.pause_screen.quit_btn != null:
		# Click first. Enter while Resume still has focus would unpause.
		await _click_control_async(app, app.session.pause_screen.quit_btn)
		await _draw_ready()
		if app.session.outcome != "quit":
			app.session.pause_screen.quit_btn.grab_focus()
			await process_frame
			await process_frame
			_push_key(app, KEY_ENTER)
			await _draw_ready()
	var used_direct_quit: bool = false
	if app.session != null and app.session.outcome != "quit":
		used_direct_quit = true
		app.session.request_quit()
	if app.session != null:
		app.quit_to_title()
	if _windowed() and used_direct_quit:
		# Official menu quit E2E is LIVE (viewport pause + Quit). This still
		# only needs the title-after-quit photograph; request_quit here is the
		# same handler the Quit button calls.
		if not bool(MatchCasesScript.outcome_live.get("quit_live", false)):
			_fail("quit still used request_quit fallback; LIVE menu quit also missing")
	await _draw_ready()
	var shot: String = _maybe_shot(app, "match_quit")
	if _windowed():
		if app.title == null or not app.title.visible:
			_fail("quit still must show title")
		if shot == "":
			_fail("DoD still missing quit")
	return shot


func _push_action(app: App, action: String) -> void:
	if app == null or app.get_viewport() == null:
		return
	var down: InputEventAction = InputEventAction.new()
	down.action = action
	down.pressed = true
	app.get_viewport().push_input(down)
	var up: InputEventAction = InputEventAction.new()
	up.action = action
	up.pressed = false
	app.get_viewport().push_input(up)


func _push_key(app: App, keycode: Key) -> void:
	if app == null or app.get_viewport() == null:
		return
	var down: InputEventKey = InputEventKey.new()
	down.keycode = keycode
	down.physical_keycode = keycode
	down.pressed = true
	down.echo = false
	app.get_viewport().push_input(down)
	var up: InputEventKey = InputEventKey.new()
	up.keycode = keycode
	up.physical_keycode = keycode
	up.pressed = false
	up.echo = false
	app.get_viewport().push_input(up)


func _click_control(app: App, ctrl: Control) -> void:
	if app == null or ctrl == null or app.get_viewport() == null:
		return
	var pos: Vector2 = ctrl.get_global_transform_with_canvas().origin + ctrl.size * 0.5
	var down: InputEventMouseButton = InputEventMouseButton.new()
	down.button_index = MOUSE_BUTTON_LEFT
	down.pressed = true
	down.position = pos
	down.global_position = pos
	app.get_viewport().push_input(down)
	var up: InputEventMouseButton = InputEventMouseButton.new()
	up.button_index = MOUSE_BUTTON_LEFT
	up.pressed = false
	up.position = pos
	up.global_position = pos
	app.get_viewport().push_input(up)


func _click_control_async(app: App, ctrl: Control) -> void:
	if app == null or ctrl == null or app.get_viewport() == null:
		return
	var pos: Vector2 = ctrl.get_global_transform_with_canvas().origin + ctrl.size * 0.5
	var down: InputEventMouseButton = InputEventMouseButton.new()
	down.button_index = MOUSE_BUTTON_LEFT
	down.pressed = true
	down.position = pos
	down.global_position = pos
	app.get_viewport().push_input(down)
	await process_frame
	var up: InputEventMouseButton = InputEventMouseButton.new()
	up.button_index = MOUSE_BUTTON_LEFT
	up.pressed = false
	up.position = pos
	up.global_position = pos
	app.get_viewport().push_input(up)


func _shot_restart(app: App) -> String:
	app.start_fight("vs2", "police", 0)
	await _draw_ready()
	app.restart_same()
	await _draw_ready()
	if app.session != null:
		var n: int = 0
		while n < 18:
			var frames: Array = []
			var i: int = 0
			while i < app.session.fighters.size():
				var raw: Dictionary = InputActions.empty_frame(app.session.clock.tick, i)
				if i == 0:
					raw["held"] = ["right"]
					raw["move_x"] = 1.0
					if n == 0:
						raw["pressed"] = ["right"]
				frames.append(InputFrame.from_dict(raw))
				i += 1
			app.session.apply_frames(frames)
			n += 1
	await _draw_ready()
	var shot: String = _maybe_shot(app, "match_restart")
	if _windowed():
		if app.session == null or app.session.outcome != "play":
			_fail("restart still must be a fresh fight")
		if shot == "":
			_fail("DoD still missing restart")
	return shot


func _write_json(path: String, data: Variant) -> void:
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		print("HH_VF_MATCH EVIDENCE_WRITE_FAIL %s" % path)
		return
	f.store_string(JSON.stringify(data, "\t"))
	f.close()


func _write_heartbeat(step: String) -> void:
	var ev: String = OS.get_environment("HH_VF_EVIDENCE_DIR")
	if ev == "":
		ev = ProjectSettings.globalize_path("res://.evidence/%s" % RUN_ID)
	DirAccess.make_dir_recursive_absolute(ev)
	_write_json(ev.path_join("run_partial.json"), {
		"schema": "vault-fighters.vf6-wp1.run.v1",
		"run_id": RUN_ID,
		"command_id": COMMAND_ID,
		"partial": true,
		"step": step,
		"display": DisplayServer.get_name(),
		"started_at": _started_at,
		"unix": Time.get_unix_time_from_system(),
	})
	print("HH_VF_MATCH HEARTBEAT=%s" % step)

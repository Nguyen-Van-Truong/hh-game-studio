extends SceneTree

const RUN_ID := "VF4WP5-20260830-ASIA-SAIGON-01"
const COMMAND_ID := "cmd.vf4-wp5.env.1"
const SEED := 7
const MODE := "vs2"
const MAP_ID := "fx_env_yard"

const EnvCasesScript: GDScript = preload("res://tests/env_cases.gd")

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
	_setup_shot = _maybe_shot(app, "env_setup")
	var errors: PackedStringArray = await EnvCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	var data: String = str(EnvCasesScript.outcome_data.get("verdict", "unproven"))
	var instant: String = str(EnvCasesScript.outcome_instant.get("verdict", "unproven"))
	var toxic: String = str(EnvCasesScript.outcome_toxic.get("verdict", "unproven"))
	var water: String = str(EnvCasesScript.outcome_water.get("verdict", "unproven"))
	var rotor: String = str(EnvCasesScript.outcome_rotor.get("verdict", "unproven"))
	var fall: String = str(EnvCasesScript.outcome_fall.get("verdict", "unproven"))
	var spawn: String = str(EnvCasesScript.outcome_spawn.get("verdict", "unproven"))
	var pause: String = str(EnvCasesScript.outcome_pause.get("verdict", "unproven"))
	var reset: String = str(EnvCasesScript.outcome_reset.get("verdict", "unproven"))
	var live: String = str(EnvCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(EnvCasesScript.outcome_replay.get("verdict", "unproven"))
	if data != "pass":
		_fail("DATA structured outcome is %s" % data)
	if instant != "pass":
		_fail("INSTANT structured outcome is %s" % instant)
	if toxic != "pass":
		_fail("TOXIC structured outcome is %s" % toxic)
	if water != "pass":
		_fail("WATER structured outcome is %s" % water)
	if rotor != "pass":
		_fail("ROTOR structured outcome is %s" % rotor)
	if fall != "pass":
		_fail("FALL structured outcome is %s" % fall)
	if spawn != "pass":
		_fail("SPAWN structured outcome is %s" % spawn)
	if pause != "pass":
		_fail("PAUSE structured outcome is %s" % pause)
	if reset != "pass":
		_fail("RESET structured outcome is %s" % reset)
	if live != "pass":
		_fail("LIVE structured outcome is %s" % live)
	if replay != "match":
		_fail("REPLAY structured outcome is %s" % replay)
	var ended_at: String = _iso_local()
	print("HH_VF_ENV run_id=%s" % RUN_ID)
	print("HH_VF_ENV command_id=%s" % COMMAND_ID)
	print("HH_VF_ENV DISPLAY=%s" % DisplayServer.get_name())
	print("HH_VF_ENV SEED=%d MAP=%s MODE=%s" % [SEED, MAP_ID, MODE])
	print("HH_VF_ENV STARTED_AT=%s ENDED_AT=%s" % [_started_at, ended_at])
	print(
		"HH_VF_ENV USED_STEP_FIXED=%d USED_APPLY_FRAMES=%d USED_APPLY_ATTEMPTED=%d USED_APPLY_SUCCEEDED=%d USED_PARSE_INPUT_EVENT=%d USED_ACTION_PRESS=%d"
		% [
			EnvCasesScript.used_step_fixed,
			EnvCasesScript.used_apply_frames,
			EnvCasesScript.used_apply_frames_attempted,
			EnvCasesScript.used_apply_frames_succeeded,
			EnvCasesScript.used_parse_input_event,
			EnvCasesScript.used_action_press
		]
	)
	print("HH_VF_ENV DATA=%s DATA_SOURCE=outcome_data" % data)
	print("HH_VF_ENV INSTANT=%s INSTANT_SOURCE=outcome_instant" % instant)
	print("HH_VF_ENV TOXIC=%s TOXIC_SOURCE=outcome_toxic" % toxic)
	print("HH_VF_ENV WATER=%s WATER_SOURCE=outcome_water" % water)
	print("HH_VF_ENV ROTOR=%s ROTOR_SOURCE=outcome_rotor" % rotor)
	print("HH_VF_ENV FALL=%s FALL_SOURCE=outcome_fall" % fall)
	print("HH_VF_ENV SPAWN=%s SPAWN_SOURCE=outcome_spawn" % spawn)
	print("HH_VF_ENV PAUSE=%s PAUSE_SOURCE=outcome_pause" % pause)
	print("HH_VF_ENV RESET=%s RESET_SOURCE=outcome_reset" % reset)
	print("HH_VF_ENV LIVE=%s LIVE_SOURCE=outcome_live" % live)
	print("HH_VF_ENV REPLAY=%s REPLAY_SOURCE=outcome_replay" % replay)
	print("HH_VF_ENV INSTANT_CLASS=assumption DEFER=assumption WATER=assumption ROTOR=assumption FALL=assumption NADE_PROP=deferred HOLD_AIM=assumption ROLL_DIVE=unavailable CLOCK=RL-SIM-FIXED-60")
	await _write_evidence(app, ended_at, data, instant, toxic, water, rotor, fall, spawn, pause, reset, live, replay)
	if _fails.is_empty():
		print("PASS: Vault Fighters toxic pits, fall, water, and machines")
	else:
		print("FAIL: Vault Fighters toxic pits, fall, water, and machines")
		i = 0
		while i < _fails.size():
			print("  - %s" % String(_fails[i]))
			i += 1
	if is_instance_valid(app):
		app.shutdown()
		app.queue_free()
	await process_frame
	await process_frame
	quit(0 if _fails.is_empty() else 1)


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
		print("HH_VF_ENV SCREENSHOT_%s missing viewport texture" % stem)
		return ""
	var img: Image = tex.get_image()
	if img == null:
		print("HH_VF_ENV SCREENSHOT_%s get_image null" % stem)
		return ""
	var shot: String = ev.path_join("screens").path_join("%s_%dx%d.png" % [stem, int(vis.size.x), int(vis.size.y)])
	var err: Error = img.save_png(shot)
	print("HH_VF_ENV SCREENSHOT_%s err=%d path=%s" % [stem, int(err), shot])
	return shot


func _draw_ready() -> void:
	await process_frame
	await process_frame
	if DisplayServer.get_name() == "headless":
		return
	await RenderingServer.frame_post_draw
	await process_frame
	await RenderingServer.frame_post_draw


func _windowed() -> bool:
	return DisplayServer.get_name() != "headless"


func _apply_held(session: GameSession, ticks: int, held: PackedStringArray) -> void:
	if session == null:
		return
	var n: int = 0
	while n < ticks:
		var frames: Array = []
		var i: int = 0
		while i < session.fighters.size():
			var d: Dictionary = InputActions.empty_frame(session.clock.tick, i)
			if i == 0:
				d["held"] = held
			frames.append(InputFrame.from_dict(d))
			i += 1
		session.apply_frames(frames)
		n += 1


func _clear_live(app: App) -> void:
	if app == null:
		return
	InputInjector.release_known(app.get_viewport())
	InputActions.reset_edges()


func _stage_water(app: App) -> Dictionary:
	var row: Dictionary = {"wet": 0, "burning": 1, "x": -1.0}
	if app == null:
		return row
	_clear_live(app)
	app.start_fight("vs2", "fx_env_yard", 0)
	await SimReplay.sync_physics(app)
	_clear_live(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1() if session != null else null
	if p1 != null:
		p1.ignite_fire(48)
	_apply_held(session, 2, PackedStringArray())
	_apply_held(session, 24, PackedStringArray(["right"]))
	await _draw_ready()
	p1 = session.player1() if session != null else null
	row["wet"] = 1 if p1 != null and p1.wet else 0
	row["burning"] = 1 if p1 != null and p1.burning else 0
	row["x"] = p1.global_position.x if p1 != null else -1.0
	return row


func _stage_rotor(app: App) -> Dictionary:
	var row: Dictionary = {"hp": 100.0, "hits": 0, "angle": 0.0, "x": -1.0}
	if app == null:
		return row
	_clear_live(app)
	app.start_fight("vs2", "fx_env_yard", 0)
	await SimReplay.sync_physics(app)
	_clear_live(app)
	var session: GameSession = app.session
	_apply_held(session, 56, PackedStringArray(["right"]))
	_apply_held(session, 16, PackedStringArray())
	await _draw_ready()
	var p1: Fighter = session.player1() if session != null else null
	var rotor: Node2D = null
	if session != null and session.world_owner != null:
		rotor = session.world_owner.call("find_by_id", "yard_mill") as Node2D
	row["hp"] = p1.health if p1 != null else 100.0
	row["hits"] = int(session.world_owner.get("rotor_hits")) if session != null and session.world_owner != null else 0
	row["angle"] = float(rotor.get("angle")) if rotor != null else 0.0
	row["x"] = p1.global_position.x if p1 != null else -1.0
	return row


func _stage_toxic(app: App) -> Dictionary:
	var row: Dictionary = {"hp": 100.0, "acid": 0, "dead": 0, "x": -1.0}
	if app == null:
		return row
	_clear_live(app)
	app.start_fight("vs2", "fx_env_yard", 0)
	await SimReplay.sync_physics(app)
	_clear_live(app)
	var session: GameSession = app.session
	_apply_held(session, 84, PackedStringArray(["right"]))
	_apply_held(session, 10, PackedStringArray())
	await _draw_ready()
	var p1: Fighter = session.player1() if session != null else null
	row["hp"] = p1.health if p1 != null else 100.0
	row["acid"] = 1 if p1 != null and p1.acid_contact else 0
	row["dead"] = 1 if p1 != null and p1.dead else 0
	row["x"] = p1.global_position.x if p1 != null else -1.0
	return row


func _stage_instant(app: App) -> Dictionary:
	var row: Dictionary = {"dead": 0, "cause": "", "x": -1.0}
	if app == null:
		return row
	_clear_live(app)
	app.start_fight("vs2", "fx_env_instant", 0)
	await SimReplay.sync_physics(app)
	_clear_live(app)
	var session: GameSession = app.session
	_apply_held(session, 60, PackedStringArray(["right"]))
	await _draw_ready()
	var p1: Fighter = session.player1() if session != null else null
	row["dead"] = 1 if p1 != null and p1.dead else 0
	row["cause"] = p1.death_cause if p1 != null else ""
	row["x"] = p1.global_position.x if p1 != null else -1.0
	return row


func _stage_fall(app: App) -> Dictionary:
	var row: Dictionary = {"y": -1.0, "on_floor": 0, "hanging": 0, "pose": "", "hp": 100.0}
	if app == null:
		return row
	_clear_live(app)
	app.start_fight("vs2", "fx_env_fall", 0)
	await SimReplay.sync_physics(app)
	_clear_live(app)
	var session: GameSession = app.session
	_apply_held(session, 58, PackedStringArray(["right"]))
	_apply_held(session, 48, PackedStringArray())
	await _draw_ready()
	var p1: Fighter = session.player1() if session != null else null
	row["y"] = p1.global_position.y if p1 != null else -1.0
	row["on_floor"] = 1 if p1 != null and p1.is_on_floor() else 0
	row["hanging"] = 1 if p1 != null and p1.hanging else 0
	row["pose"] = p1.current_pose() if p1 != null else ""
	row["hp"] = p1.health if p1 != null else 100.0
	return row


func _stage_live_map(app: App, map_id: String) -> Dictionary:
	var row: Dictionary = {"map": map_id, "dead": 1, "name": ""}
	if app == null:
		return row
	_clear_live(app)
	app.start_fight("vs2", map_id, 0)
	await SimReplay.sync_physics(app)
	_apply_held(app.session, 4, PackedStringArray())
	await _draw_ready()
	var p1: Fighter = app.session.player1() if app.session != null else null
	row["dead"] = 1 if p1 != null and p1.dead else 0
	row["name"] = Maps.display_name(map_id)
	return row


func _write_evidence(
	app: App, ended_at: String, data: String, instant: String, toxic: String, water: String,
	rotor: String, fall: String, spawn: String, pause: String, reset: String, live: String, replay: String
) -> void:
	var ev: String = OS.get_environment("HH_VF_EVIDENCE_DIR")
	if ev == "":
		ev = ProjectSettings.globalize_path("res://.evidence/%s" % RUN_ID)
	DirAccess.make_dir_recursive_absolute(ev)
	DirAccess.make_dir_recursive_absolute(ev.path_join("screens"))
	_clear_live(app)
	var water_row: Dictionary = await _stage_water(app)
	var water_shot: String = _maybe_shot(app, "env_water")
	print(
		"HH_VF_ENV SHOT_WATER wet=%d burn=%d x=%s path=%s"
		% [int(water_row.get("wet", 0)), int(water_row.get("burning", 1)), str(water_row.get("x", -1)), water_shot]
	)
	var rotor_row: Dictionary = await _stage_rotor(app)
	var rotor_shot: String = _maybe_shot(app, "env_rotor")
	print(
		"HH_VF_ENV SHOT_ROTOR hp=%s hits=%d angle=%s x=%s path=%s"
		% [
			str(rotor_row.get("hp", 100)),
			int(rotor_row.get("hits", 0)),
			str(rotor_row.get("angle", 0)),
			str(rotor_row.get("x", -1)),
			rotor_shot
		]
	)
	var toxic_row: Dictionary = await _stage_toxic(app)
	var toxic_shot: String = _maybe_shot(app, "env_toxic")
	print(
		"HH_VF_ENV SHOT_TOXIC hp=%s acid=%d dead=%d x=%s path=%s"
		% [
			str(toxic_row.get("hp", 100)),
			int(toxic_row.get("acid", 0)),
			int(toxic_row.get("dead", 0)),
			str(toxic_row.get("x", -1)),
			toxic_shot
		]
	)
	var instant_row: Dictionary = await _stage_instant(app)
	var instant_shot: String = _maybe_shot(app, "env_instant")
	print(
		"HH_VF_ENV SHOT_INSTANT dead=%d cause=%s x=%s path=%s"
		% [int(instant_row.get("dead", 0)), str(instant_row.get("cause", "")), str(instant_row.get("x", -1)), instant_shot]
	)
	var fall_row: Dictionary = await _stage_fall(app)
	var fall_shot: String = _maybe_shot(app, "env_fall")
	print(
		"HH_VF_ENV SHOT_FALL y=%s on_floor=%d hang=%d pose=%s hp=%s path=%s"
		% [
			str(fall_row.get("y", -1)),
			int(fall_row.get("on_floor", 0)),
			int(fall_row.get("hanging", 0)),
			str(fall_row.get("pose", "")),
			str(fall_row.get("hp", 100)),
			fall_shot
		]
	)
	var live_ids: PackedStringArray = PackedStringArray(["rooftops", "storage", "police", "hazardous"])
	var live_stems: PackedStringArray = PackedStringArray([
		"env_rooftops", "env_storage", "env_police", "env_hazardous"
	])
	var live_shots: Dictionary = {}
	var li: int = 0
	while li < live_ids.size():
		var mid: String = String(live_ids[li])
		var live_row: Dictionary = await _stage_live_map(app, mid)
		var live_shot: String = _maybe_shot(app, String(live_stems[li]))
		live_shots[mid] = live_shot
		print(
			"HH_VF_ENV SHOT_MAP map=%s name=%s dead=%d path=%s"
			% [mid, str(live_row.get("name", "")), int(live_row.get("dead", 1)), live_shot]
		)
		if _windowed() and int(live_row.get("dead", 1)) != 0:
			_fail("DoD live map still %s must not spawn-kill" % mid)
		if _windowed() and live_shot == "":
			_fail("DoD live map still missing %s" % mid)
		li += 1
	if _windowed():
		if int(water_row.get("wet", 0)) != 1 or int(water_row.get("burning", 1)) != 0:
			_fail("DoD water still must show wet and extinguished")
		if float(rotor_row.get("hp", 100)) >= 99.5:
			_fail("DoD rotor still must show rotor damage")
		if int(toxic_row.get("acid", 0)) != 1 or float(toxic_row.get("hp", 100)) >= 99.5:
			_fail("DoD toxic still must show acid contact and damage")
		if int(instant_row.get("dead", 0)) != 1 or str(instant_row.get("cause", "")) != "pit":
			_fail("DoD instant still must show pit death")
		if int(fall_row.get("on_floor", 0)) != 1 or int(fall_row.get("hanging", 0)) != 0:
			_fail("DoD fall still must stand on the lower deck")
		if str(fall_row.get("pose", "hang")) == "hang":
			_fail("DoD fall still pose must not be hang")
		if float(fall_row.get("hp", 100)) >= 99.5:
			_fail("DoD fall still must show fall damage")
		if water_shot == "" or rotor_shot == "" or toxic_shot == "" or instant_shot == "" or fall_shot == "" or _setup_shot == "":
			_fail("DoD window stills missing setup/water/rotor/toxic/instant/fall")
	var outcomes: Dictionary = {
		"data": EnvCasesScript.outcome_data,
		"instant": EnvCasesScript.outcome_instant,
		"toxic": EnvCasesScript.outcome_toxic,
		"water": EnvCasesScript.outcome_water,
		"rotor": EnvCasesScript.outcome_rotor,
		"fall": EnvCasesScript.outcome_fall,
		"spawn": EnvCasesScript.outcome_spawn,
		"pause": EnvCasesScript.outcome_pause,
		"reset": EnvCasesScript.outcome_reset,
		"live": EnvCasesScript.outcome_live,
		"replay": EnvCasesScript.outcome_replay,
		"apply": {
			"attempted": EnvCasesScript.used_apply_frames_attempted,
			"succeeded": EnvCasesScript.used_apply_frames_succeeded,
			"used_apply_frames": EnvCasesScript.used_apply_frames,
			"used_step_fixed": EnvCasesScript.used_step_fixed,
			"used_parse_input_event": EnvCasesScript.used_parse_input_event,
			"used_action_press": EnvCasesScript.used_action_press,
		},
	}
	_write_json(ev.path_join("outcomes.json"), outcomes)
	_write_json(ev.path_join("snapshot_start.json"), EnvCasesScript.snapshot_start)
	_write_json(ev.path_join("snapshot_end.json"), EnvCasesScript.snapshot_end)
	_write_json(ev.path_join("state_hashes.json"), {
		"replay": EnvCasesScript.outcome_replay,
		"instant": EnvCasesScript.outcome_instant,
		"seed": SEED,
		"map_id": MAP_ID,
		"mode": MODE,
	})
	var events_path: String = ev.path_join("events.jsonl")
	var ef: FileAccess = FileAccess.open(events_path, FileAccess.WRITE)
	if ef != null:
		var events: Array = EnvCasesScript.events_all
		if events.is_empty():
			events = EnvCasesScript.events_end
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
		"schema": "vault-fighters.vf4-wp5.run.v1",
		"run_id": RUN_ID,
		"command_id": COMMAND_ID,
		"wp": "VF4-WP5",
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
			"water": water_shot,
			"rotor": rotor_shot,
			"toxic": toxic_shot,
			"instant": instant_shot,
			"fall": fall_shot,
			"live": live_shots,
		},
		"outcomes": {
			"DATA": data,
			"INSTANT": instant,
			"TOXIC": toxic,
			"WATER": water,
			"ROTOR": rotor,
			"FALL": fall,
			"SPAWN": spawn,
			"PAUSE": pause,
			"RESET": reset,
			"LIVE": live,
			"REPLAY": replay,
			"USED_APPLY_FRAMES": EnvCasesScript.used_apply_frames,
			"USED_APPLY_ATTEMPTED": EnvCasesScript.used_apply_frames_attempted,
			"USED_APPLY_SUCCEEDED": EnvCasesScript.used_apply_frames_succeeded,
		},
		"fail_count": _fails.size(),
	}
	_write_json(ev.path_join("run_partial.json"), run_partial)
	print("HH_VF_ENV EVIDENCE_DIR=%s" % ev)


func _write_json(path: String, data: Variant) -> void:
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		print("HH_VF_ENV EVIDENCE_WRITE_FAIL %s" % path)
		return
	f.store_string(JSON.stringify(data, "\t"))
	f.close()

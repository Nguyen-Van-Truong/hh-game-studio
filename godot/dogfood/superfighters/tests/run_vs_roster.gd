extends SceneTree

const RUN_ID := "VF5WP6-20260831-ASIA-SAIGON-02"
const COMMAND_ID := "cmd.vf5-wp6.vs-roster.2"
const SEED := 16
const MODE := "vs2"
const MAP_ID := "rooftops"

const VsRosterCasesScript: GDScript = preload("res://tests/vs_roster_cases.gd")

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
	_setup_shot = _maybe_shot(app, "vs_setup")
	var errors: PackedStringArray = await VsRosterCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	var roster: String = str(VsRosterCasesScript.outcome_roster.get("verdict", "unproven"))
	var cycle: String = str(VsRosterCasesScript.outcome_cycle.get("verdict", "unproven"))
	var load_v: String = str(VsRosterCasesScript.outcome_load.get("verdict", "unproven"))
	var routes: String = str(VsRosterCasesScript.outcome_routes.get("verdict", "unproven"))
	var cover: String = str(VsRosterCasesScript.outcome_cover.get("verdict", "unproven"))
	var cargo: String = str(VsRosterCasesScript.outcome_cargo.get("verdict", "unproven"))
	var door: String = str(VsRosterCasesScript.outcome_door.get("verdict", "unproven"))
	var rotor: String = str(VsRosterCasesScript.outcome_rotor.get("verdict", "unproven"))
	var toxic: String = str(VsRosterCasesScript.outcome_toxic.get("verdict", "unproven"))
	var water: String = str(VsRosterCasesScript.outcome_water.get("verdict", "unproven"))
	var lift: String = str(VsRosterCasesScript.outcome_lift.get("verdict", "unproven"))
	var lantern: String = str(VsRosterCasesScript.outcome_lantern.get("verdict", "unproven"))
	var gauge: String = str(VsRosterCasesScript.outcome_gauge.get("verdict", "unproven"))
	var p2: String = str(VsRosterCasesScript.outcome_p2.get("verdict", "unproven"))
	var bot: String = str(VsRosterCasesScript.outcome_bot.get("verdict", "unproven"))
	var camera: String = str(VsRosterCasesScript.outcome_camera.get("verdict", "unproven"))
	var live: String = str(VsRosterCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(VsRosterCasesScript.outcome_replay.get("verdict", "unproven"))
	if roster != "pass":
		_fail("ROSTER structured outcome is %s" % roster)
	if cycle != "pass":
		_fail("CYCLE structured outcome is %s" % cycle)
	if load_v != "pass":
		_fail("LOAD structured outcome is %s" % load_v)
	if routes != "pass":
		_fail("ROUTES structured outcome is %s" % routes)
	if cover != "pass":
		_fail("COVER structured outcome is %s" % cover)
	if cargo != "pass":
		_fail("CARGO structured outcome is %s" % cargo)
	if door != "pass":
		_fail("DOOR structured outcome is %s" % door)
	if rotor != "pass":
		_fail("ROTOR structured outcome is %s" % rotor)
	if toxic != "pass":
		_fail("TOXIC structured outcome is %s" % toxic)
	if water != "pass":
		_fail("WATER structured outcome is %s" % water)
	if lift != "pass":
		_fail("LIFT structured outcome is %s" % lift)
	if lantern != "pass":
		_fail("LANTERN structured outcome is %s" % lantern)
	if gauge != "pass":
		_fail("GAUGE structured outcome is %s" % gauge)
	if p2 != "pass":
		_fail("P2 structured outcome is %s" % p2)
	if bot != "pass":
		_fail("BOT structured outcome is %s" % bot)
	if camera != "pass":
		_fail("CAMERA structured outcome is %s" % camera)
	if live != "pass":
		_fail("LIVE structured outcome is %s" % live)
	if replay != "match":
		_fail("REPLAY structured outcome is %s" % replay)
	var ended_at: String = _iso_local()
	print("HH_VF_VS run_id=%s" % RUN_ID)
	print("HH_VF_VS command_id=%s" % COMMAND_ID)
	print("HH_VF_VS DISPLAY=%s" % DisplayServer.get_name())
	print("HH_VF_VS SEED=%d MAP=%s MODE=%s NAME=%s" % [SEED, MAP_ID, MODE, Maps.display_name(MAP_ID)])
	print("HH_VF_VS STARTED_AT=%s ENDED_AT=%s" % [_started_at, ended_at])
	print(
		"HH_VF_VS USED_STEP_FIXED=%d USED_APPLY_FRAMES=%d USED_APPLY_ATTEMPTED=%d USED_APPLY_SUCCEEDED=%d USED_PARSE_INPUT_EVENT=%d USED_ACTION_PRESS=%d"
		% [
			VsRosterCasesScript.used_step_fixed,
			VsRosterCasesScript.used_apply_frames,
			VsRosterCasesScript.used_apply_frames_attempted,
			VsRosterCasesScript.used_apply_frames_succeeded,
			VsRosterCasesScript.used_parse_input_event,
			VsRosterCasesScript.used_action_press
		]
	)
	print("HH_VF_VS ROSTER=%s ROSTER_SOURCE=outcome_roster" % roster)
	print("HH_VF_VS CYCLE=%s CYCLE_SOURCE=outcome_cycle" % cycle)
	print("HH_VF_VS LOAD=%s LOAD_SOURCE=outcome_load" % load_v)
	print("HH_VF_VS ROUTES=%s ROUTES_SOURCE=outcome_routes" % routes)
	print("HH_VF_VS COVER=%s COVER_SOURCE=outcome_cover" % cover)
	print("HH_VF_VS CARGO=%s CARGO_SOURCE=outcome_cargo" % cargo)
	print("HH_VF_VS DOOR=%s DOOR_SOURCE=outcome_door" % door)
	print("HH_VF_VS ROTOR=%s ROTOR_SOURCE=outcome_rotor" % rotor)
	print("HH_VF_VS TOXIC=%s TOXIC_SOURCE=outcome_toxic" % toxic)
	print("HH_VF_VS WATER=%s WATER_SOURCE=outcome_water" % water)
	print(
		"HH_VF_VS WATER_DX_DRY=%s WATER_DX_WET=%s WATER_SPRINT_BLOCKED=%s WATER_ENV=%s"
		% [
			str(VsRosterCasesScript.outcome_water.get("dx_dry", "")),
			str(VsRosterCasesScript.outcome_water.get("dx_wet", "")),
			str(VsRosterCasesScript.outcome_water.get("sprint_blocked", "")),
			str(VsRosterCasesScript.outcome_water.get("env_id", "")),
		]
	)
	print("HH_VF_VS ROTOR_GIVE_WEAPON=%s ROTOR_HELD=%s" % [
		str(VsRosterCasesScript.outcome_rotor.get("used_give_weapon", true)),
		str(VsRosterCasesScript.outcome_rotor.get("held_weapon", "")),
	])
	print("HH_VF_VS LIVE_WRAP_SOURCE=%s LIVE_WRAP_FROM=%s LIVE_WRAP_TO=%s" % [
		str(VsRosterCasesScript.outcome_live.get("source", "")),
		str(VsRosterCasesScript.outcome_live.get("wrap_from", "")),
		str(VsRosterCasesScript.outcome_live.get("wrap_to", "")),
	])
	print("HH_VF_VS LIFT=%s LIFT_SOURCE=outcome_lift" % lift)
	print("HH_VF_VS LANTERN=%s LANTERN_SOURCE=outcome_lantern" % lantern)
	print("HH_VF_VS GAUGE=%s GAUGE_SOURCE=outcome_gauge" % gauge)
	print("HH_VF_VS SPAWN=%s SPAWN_SOURCE=outcome_routes" % routes)
	print("HH_VF_VS CAMERA=%s CAMERA_SOURCE=outcome_camera" % camera)
	print("HH_VF_VS P2=%s P2_SOURCE=outcome_p2 P2_COVERAGE=smoke" % p2)
	print("HH_VF_VS BOT=%s BOT_SOURCE=outcome_bot BOT_COVERAGE=smoke" % bot)
	print("HH_VF_VS LIVE=%s LIVE_SOURCE=outcome_live" % live)
	print("HH_VF_VS REPLAY=%s REPLAY_SOURCE=outcome_replay" % replay)
	print("HH_VF_VS HONESTY P2=lantern_short_walk_smoke BOT=gauge_idle_smoke P1=live_routes NOT_AI=1 NOT_Y8_PARITY=1")
	print("HH_VF_VS ROSTER_CLASS=assumption LAYERS=assumption GRAPH=assumption HOLD_AIM=assumption ROLL_DIVE=unavailable CLOCK=RL-SIM-FIXED-60")
	print(
		"HH_VF_VS IDS rooftops,storage,police,hazardous,lantern,gauge STAGE=4 AUTHOR=fx_map_author"
	)
	await _write_evidence(app, ended_at, roster, cycle, load_v, routes, cover, cargo, door, rotor, toxic, water, lift, lantern, gauge, p2, bot, camera, live, replay)
	if _fails.is_empty():
		print("PASS: Vault Fighters six-map VS roster")
	else:
		print("FAIL: Vault Fighters six-map VS roster")
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


func _assert_standing_still(app: App, row: Dictionary, name: String) -> void:
	var lose: bool = app != null and app.lose_screen != null and app.lose_screen.visible
	if lose:
		_fail("%s still has lose overlay" % name)
	if not bool(row.get("alive", false)):
		_fail("%s still actor is not alive" % name)
	if name == "lantern_water":
		return
	if not bool(row.get("on_floor", false)) and name != "gauge_lift":
		_fail("%s still actor is not standing on_floor" % name)
	if bool(row.get("hanging", false)):
		_fail("%s still actor is hanging" % name)


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
		print("HH_VF_VS SCREENSHOT_%s missing viewport texture" % stem)
		return ""
	var img: Image = tex.get_image()
	if img == null:
		print("HH_VF_VS SCREENSHOT_%s get_image null" % stem)
		return ""
	var shot: String = ev.path_join("screens").path_join("%s_%dx%d.png" % [stem, int(vis.size.x), int(vis.size.y)])
	var err: Error = img.save_png(shot)
	print("HH_VF_VS SCREENSHOT_%s err=%d path=%s" % [stem, int(err), shot])
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


func _write_evidence(
	app: App, ended_at: String, roster: String, cycle: String, load_v: String, routes: String,
	cover: String, cargo: String, door: String, rotor: String, toxic: String, water: String,
	lift: String, lantern: String, gauge: String, p2: String, bot: String, camera: String,
	live: String, replay: String
) -> void:
	var ev: String = OS.get_environment("HH_VF_EVIDENCE_DIR")
	if ev == "":
		ev = ProjectSettings.globalize_path("res://.evidence/%s" % RUN_ID)
	DirAccess.make_dir_recursive_absolute(ev)
	DirAccess.make_dir_recursive_absolute(ev.path_join("screens"))
	var live_shots: Dictionary = {}
	app.restart_to_title()
	await _draw_ready()
	live_shots["title"] = _maybe_shot(app, "vs_title")
	if _windowed() and str(live_shots.get("title", "")) == "":
		_fail("DoD still missing title")
	var ids: PackedStringArray = PackedStringArray([
		"rooftops", "storage", "police", "hazardous", "lantern", "gauge"
	])
	var i: int = 0
	while i < ids.size():
		var mid: String = String(ids[i])
		var row: Dictionary = await VsRosterCasesScript.stage_map(app, mid)
		_assert_standing_still(app, row, mid)
		await _draw_ready()
		live_shots[mid] = _maybe_shot(app, "vs_%s" % mid)
		if _windowed() and str(live_shots.get(mid, "")) == "":
			_fail("DoD still missing %s" % mid)
		i += 1
	var water_row: Dictionary = await VsRosterCasesScript.stage_lantern_water(app)
	_assert_standing_still(app, water_row, "lantern_water")
	if _windowed() and not bool(water_row.get("wet", false)):
		_fail("lantern_water still must show fighter.wet")
	await _draw_ready()
	live_shots["lantern_water"] = _maybe_shot(app, "vs_lantern_water")
	if _windowed() and str(live_shots.get("lantern_water", "")) == "":
		_fail("DoD still missing lantern water")
	var lift_row: Dictionary = await VsRosterCasesScript.stage_gauge_lift(app)
	_assert_standing_still(app, lift_row, "gauge_lift")
	await _draw_ready()
	live_shots["gauge_lift"] = _maybe_shot(app, "vs_gauge_lift")
	if _windowed() and str(live_shots.get("gauge_lift", "")) == "":
		_fail("DoD still missing gauge lift")
	if _windowed() and _setup_shot == "":
		_fail("DoD window still missing setup")
	var outcomes: Dictionary = {
		"roster": VsRosterCasesScript.outcome_roster,
		"cycle": VsRosterCasesScript.outcome_cycle,
		"load": VsRosterCasesScript.outcome_load,
		"routes": VsRosterCasesScript.outcome_routes,
		"cover": VsRosterCasesScript.outcome_cover,
		"cargo": VsRosterCasesScript.outcome_cargo,
		"door": VsRosterCasesScript.outcome_door,
		"rotor": VsRosterCasesScript.outcome_rotor,
		"toxic": VsRosterCasesScript.outcome_toxic,
		"water": VsRosterCasesScript.outcome_water,
		"lift": VsRosterCasesScript.outcome_lift,
		"lantern": VsRosterCasesScript.outcome_lantern,
		"gauge": VsRosterCasesScript.outcome_gauge,
		"p2": VsRosterCasesScript.outcome_p2,
		"bot": VsRosterCasesScript.outcome_bot,
		"camera": VsRosterCasesScript.outcome_camera,
		"live": VsRosterCasesScript.outcome_live,
		"replay": VsRosterCasesScript.outcome_replay,
		"water_still": water_row,
		"lift_still": lift_row,
		"apply": {
			"attempted": VsRosterCasesScript.used_apply_frames_attempted,
			"succeeded": VsRosterCasesScript.used_apply_frames_succeeded,
			"used_apply_frames": VsRosterCasesScript.used_apply_frames,
			"used_step_fixed": VsRosterCasesScript.used_step_fixed,
			"used_parse_input_event": VsRosterCasesScript.used_parse_input_event,
			"used_action_press": VsRosterCasesScript.used_action_press,
		},
	}
	_write_json(ev.path_join("outcomes.json"), outcomes)
	_write_json(ev.path_join("snapshot_start.json"), VsRosterCasesScript.snapshot_start)
	_write_json(ev.path_join("snapshot_end.json"), VsRosterCasesScript.snapshot_end)
	_write_json(ev.path_join("state_hashes.json"), {
		"replay": VsRosterCasesScript.outcome_replay,
		"seed": SEED,
		"map_id": MAP_ID,
		"mode": MODE,
		"vs_ids": ["rooftops", "storage", "police", "hazardous", "lantern", "gauge"],
	})
	var events_path: String = ev.path_join("events.jsonl")
	var ef: FileAccess = FileAccess.open(events_path, FileAccess.WRITE)
	if ef != null:
		var events: Array = VsRosterCasesScript.events_all
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
		"schema": "vault-fighters.vf5-wp6.run.v1",
		"run_id": RUN_ID,
		"command_id": COMMAND_ID,
		"wp": "VF5-WP6",
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
			"ROSTER": roster,
			"CYCLE": cycle,
			"LOAD": load_v,
			"ROUTES": routes,
			"COVER": cover,
			"CARGO": cargo,
			"DOOR": door,
			"ROTOR": rotor,
			"TOXIC": toxic,
			"WATER": water,
			"LIFT": lift,
			"LANTERN": lantern,
			"GAUGE": gauge,
			"P2": p2,
			"BOT": bot,
			"CAMERA": camera,
			"LIVE": live,
			"REPLAY": replay,
			"USED_APPLY_FRAMES": VsRosterCasesScript.used_apply_frames,
			"USED_APPLY_ATTEMPTED": VsRosterCasesScript.used_apply_frames_attempted,
			"USED_APPLY_SUCCEEDED": VsRosterCasesScript.used_apply_frames_succeeded,
		},
		"fail_count": _fails.size(),
	}
	_write_json(ev.path_join("run_partial.json"), run_partial)
	print("HH_VF_VS EVIDENCE_DIR=%s" % ev)


func _write_json(path: String, data: Variant) -> void:
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		print("HH_VF_VS EVIDENCE_WRITE_FAIL %s" % path)
		return
	f.store_string(JSON.stringify(data, "\t"))
	f.close()

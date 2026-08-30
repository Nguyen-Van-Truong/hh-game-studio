extends SceneTree

const RUN_ID := "VF5WP4-20260830-ASIA-SAIGON-01"
const COMMAND_ID := "cmd.vf5-wp4.signal-court.1"
const SEED := 14
const MODE := "vs2"
const MAP_ID := "police"

const StationCasesScript: GDScript = preload("res://tests/station_cases.gd")

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
	_setup_shot = _maybe_shot(app, "station_setup")
	var errors: PackedStringArray = await StationCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	var name_v: String = str(StationCasesScript.outcome_name.get("verdict", "unproven"))
	var graph: String = str(StationCasesScript.outcome_graph.get("verdict", "unproven"))
	var machine: String = str(StationCasesScript.outcome_machine.get("verdict", "unproven"))
	var floor_v: String = str(StationCasesScript.outcome_floor.get("verdict", "unproven"))
	var spawn: String = str(StationCasesScript.outcome_spawn.get("verdict", "unproven"))
	var cover: String = str(StationCasesScript.outcome_cover.get("verdict", "unproven"))
	var door: String = str(StationCasesScript.outcome_door.get("verdict", "unproven"))
	var camera: String = str(StationCasesScript.outcome_camera.get("verdict", "unproven"))
	var p1: String = str(StationCasesScript.outcome_p1.get("verdict", "unproven"))
	var p2: String = str(StationCasesScript.outcome_p2.get("verdict", "unproven"))
	var bot: String = str(StationCasesScript.outcome_bot.get("verdict", "unproven"))
	var zone: String = str(StationCasesScript.outcome_zone.get("verdict", "unproven"))
	var live: String = str(StationCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(StationCasesScript.outcome_replay.get("verdict", "unproven"))
	if name_v != "pass":
		_fail("NAME structured outcome is %s" % name_v)
	if graph != "pass":
		_fail("GRAPH structured outcome is %s" % graph)
	if machine != "pass":
		_fail("MACHINE structured outcome is %s" % machine)
	if floor_v != "pass":
		_fail("FLOOR structured outcome is %s" % floor_v)
	if spawn != "pass":
		_fail("SPAWN structured outcome is %s" % spawn)
	if cover != "pass":
		_fail("COVER structured outcome is %s" % cover)
	if door != "pass":
		_fail("DOOR structured outcome is %s" % door)
	if camera != "pass":
		_fail("CAMERA structured outcome is %s" % camera)
	if p1 != "pass":
		_fail("P1 structured outcome is %s" % p1)
	if p2 != "pass":
		_fail("P2 structured outcome is %s" % p2)
	if bot != "pass":
		_fail("BOT structured outcome is %s" % bot)
	if zone != "pass":
		_fail("ZONE structured outcome is %s" % zone)
	if live != "pass":
		_fail("LIVE structured outcome is %s" % live)
	if replay != "match":
		_fail("REPLAY structured outcome is %s" % replay)
	var ended_at: String = _iso_local()
	print("HH_VF_STAT run_id=%s" % RUN_ID)
	print("HH_VF_STAT command_id=%s" % COMMAND_ID)
	print("HH_VF_STAT DISPLAY=%s" % DisplayServer.get_name())
	print("HH_VF_STAT SEED=%d MAP=%s MODE=%s NAME=%s" % [SEED, MAP_ID, MODE, Maps.display_name(MAP_ID)])
	print("HH_VF_STAT STARTED_AT=%s ENDED_AT=%s" % [_started_at, ended_at])
	print(
		"HH_VF_STAT USED_STEP_FIXED=%d USED_APPLY_FRAMES=%d USED_APPLY_ATTEMPTED=%d USED_APPLY_SUCCEEDED=%d USED_PARSE_INPUT_EVENT=%d USED_ACTION_PRESS=%d"
		% [
			StationCasesScript.used_step_fixed,
			StationCasesScript.used_apply_frames,
			StationCasesScript.used_apply_frames_attempted,
			StationCasesScript.used_apply_frames_succeeded,
			StationCasesScript.used_parse_input_event,
			StationCasesScript.used_action_press
		]
	)
	print("HH_VF_STAT NAME=%s NAME_SOURCE=outcome_name" % name_v)
	print("HH_VF_STAT GRAPH=%s GRAPH_SOURCE=outcome_graph" % graph)
	print("HH_VF_STAT MACHINE=%s MACHINE_SOURCE=outcome_machine" % machine)
	print("HH_VF_STAT FLOOR=%s FLOOR_SOURCE=outcome_floor" % floor_v)
	print("HH_VF_STAT SPAWN=%s SPAWN_SOURCE=outcome_spawn" % spawn)
	print("HH_VF_STAT COVER=%s COVER_SOURCE=outcome_cover" % cover)
	print("HH_VF_STAT DOOR=%s DOOR_SOURCE=outcome_door" % door)
	print("HH_VF_STAT CAMERA=%s CAMERA_SOURCE=outcome_camera" % camera)
	print("HH_VF_STAT P1=%s P1_SOURCE=outcome_p1" % p1)
	print("HH_VF_STAT P2=%s P2_SOURCE=outcome_p2" % p2)
	print("HH_VF_STAT BOT=%s BOT_SOURCE=outcome_bot" % bot)
	print("HH_VF_STAT ZONE=%s ZONE_SOURCE=outcome_zone" % zone)
	print("HH_VF_STAT LIVE=%s LIVE_SOURCE=outcome_live" % live)
	print("HH_VF_STAT REPLAY=%s REPLAY_SOURCE=outcome_replay" % replay)
	print("HH_VF_STAT SIGNAL=assumption LAYERS=assumption GRAPH=assumption HOLD_AIM=assumption ROLL_DIVE=unavailable CLOCK=RL-SIM-FIXED-60")
	print(
		"HH_VF_STAT LIVE_ZONES P1=%s P2=%s BOT=%s EAST_TOP=%s CLIMB_UP_ON_LADDER=%s"
		% [
			str(StationCasesScript.outcome_p1.get("hits", {})),
			str(StationCasesScript.outcome_p2.get("hits", {})),
			str(StationCasesScript.outcome_bot.get("hits", {})),
			str(StationCasesScript.outcome_zone.get("east_top_live", false)),
			str(StationCasesScript.outcome_zone.get("climb_up_on_ladder", 0)),
		]
	)
	await _write_evidence(app, ended_at, name_v, graph, machine, floor_v, spawn, cover, door, camera, p1, p2, bot, zone, live, replay)
	if _fails.is_empty():
		print("PASS: Vault Fighters Signal Court station arena")
	else:
		print("FAIL: Vault Fighters Signal Court station arena")
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
	if not bool(row.get("on_floor", false)):
		_fail("%s still actor is not standing on_floor" % name)
	if bool(row.get("hanging", false)):
		_fail("%s still actor is hanging" % name)
	var zid: String = str(row.get("zone", ""))
	if name == "court" and zid != "court_mid" and zid != "court_low" and zid != "court_ground":
		_fail("court still must occupy a courtyard zone got %s" % zid)
	if name == "floor1" and zid != "west_hall" and zid != "east_hall":
		_fail("floor1 still must occupy a ground hall got %s" % zid)
	if name == "floor2" and zid != "west_loft" and zid != "sky_bridge" and zid != "east_mid":
		_fail("floor2 still must occupy a mid floor got %s" % zid)
	if name == "floor3" and zid != "east_top":
		_fail("floor3 still must occupy east_top standing")
	if name == "machine" and zid != "court_ground" and zid != "court_low" and zid != "west_hall":
		_fail("machine still must occupy the courtyard approach got %s" % zid)


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
		print("HH_VF_STAT SCREENSHOT_%s missing viewport texture" % stem)
		return ""
	var img: Image = tex.get_image()
	if img == null:
		print("HH_VF_STAT SCREENSHOT_%s get_image null" % stem)
		return ""
	var shot: String = ev.path_join("screens").path_join("%s_%dx%d.png" % [stem, int(vis.size.x), int(vis.size.y)])
	var err: Error = img.save_png(shot)
	print("HH_VF_STAT SCREENSHOT_%s err=%d path=%s" % [stem, int(err), shot])
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
	app: App, ended_at: String, name_v: String, graph: String, machine: String, floor_v: String,
	spawn: String, cover: String, door: String, camera: String, p1: String, p2: String, bot: String,
	zone: String, live: String, replay: String
) -> void:
	var ev: String = OS.get_environment("HH_VF_EVIDENCE_DIR")
	if ev == "":
		ev = ProjectSettings.globalize_path("res://.evidence/%s" % RUN_ID)
	DirAccess.make_dir_recursive_absolute(ev)
	DirAccess.make_dir_recursive_absolute(ev.path_join("screens"))
	var live_shots: Dictionary = {}
	app.restart_to_title()
	await _draw_ready()
	live_shots["title"] = _maybe_shot(app, "station_title")
	if _windowed() and str(live_shots.get("title", "")) == "":
		_fail("DoD still missing title")
	await StationCasesScript.stage_court(app)
	_assert_standing_still(app, StationCasesScript.outcome_court_still, "court")
	await _draw_ready()
	live_shots["court"] = _maybe_shot(app, "station_court")
	if _windowed() and str(live_shots.get("court", "")) == "":
		_fail("DoD still missing courtyard landmark")
	await StationCasesScript.stage_floor1(app)
	_assert_standing_still(app, StationCasesScript.outcome_floor1_still, "floor1")
	await _draw_ready()
	live_shots["floor1"] = _maybe_shot(app, "station_floor1")
	if _windowed() and str(live_shots.get("floor1", "")) == "":
		_fail("DoD still missing floor1 landmark")
	await StationCasesScript.stage_floor2(app)
	_assert_standing_still(app, StationCasesScript.outcome_floor2_still, "floor2")
	await _draw_ready()
	live_shots["floor2"] = _maybe_shot(app, "station_floor2")
	if _windowed() and str(live_shots.get("floor2", "")) == "":
		_fail("DoD still missing floor2 landmark")
	await StationCasesScript.stage_floor3(app)
	_assert_standing_still(app, StationCasesScript.outcome_floor3_still, "floor3")
	await _draw_ready()
	live_shots["floor3"] = _maybe_shot(app, "station_floor3")
	if _windowed() and str(live_shots.get("floor3", "")) == "":
		_fail("DoD still missing floor3 landmark")
	await StationCasesScript.stage_machine(app)
	_assert_standing_still(app, StationCasesScript.outcome_machine_still, "machine")
	await _draw_ready()
	live_shots["machine"] = _maybe_shot(app, "station_machine")
	if _windowed() and str(live_shots.get("machine", "")) == "":
		_fail("DoD still missing machine landmark")
	if _windowed() and _setup_shot == "":
		_fail("DoD window still missing setup")
	var outcomes: Dictionary = {
		"name": StationCasesScript.outcome_name,
		"graph": StationCasesScript.outcome_graph,
		"machine": StationCasesScript.outcome_machine,
		"floor": StationCasesScript.outcome_floor,
		"spawn": StationCasesScript.outcome_spawn,
		"cover": StationCasesScript.outcome_cover,
		"door": StationCasesScript.outcome_door,
		"camera": StationCasesScript.outcome_camera,
		"p1": StationCasesScript.outcome_p1,
		"p2": StationCasesScript.outcome_p2,
		"bot": StationCasesScript.outcome_bot,
		"zone": StationCasesScript.outcome_zone,
		"live": StationCasesScript.outcome_live,
		"replay": StationCasesScript.outcome_replay,
		"court_still": StationCasesScript.outcome_court_still,
		"floor1_still": StationCasesScript.outcome_floor1_still,
		"floor2_still": StationCasesScript.outcome_floor2_still,
		"floor3_still": StationCasesScript.outcome_floor3_still,
		"machine_still": StationCasesScript.outcome_machine_still,
		"apply": {
			"attempted": StationCasesScript.used_apply_frames_attempted,
			"succeeded": StationCasesScript.used_apply_frames_succeeded,
			"used_apply_frames": StationCasesScript.used_apply_frames,
			"used_step_fixed": StationCasesScript.used_step_fixed,
			"used_parse_input_event": StationCasesScript.used_parse_input_event,
			"used_action_press": StationCasesScript.used_action_press,
		},
	}
	_write_json(ev.path_join("outcomes.json"), outcomes)
	_write_json(ev.path_join("snapshot_start.json"), StationCasesScript.snapshot_start)
	_write_json(ev.path_join("snapshot_end.json"), StationCasesScript.snapshot_end)
	_write_json(ev.path_join("state_hashes.json"), {
		"replay": StationCasesScript.outcome_replay,
		"seed": SEED,
		"map_id": MAP_ID,
		"mode": MODE,
		"display": Maps.display_name(MAP_ID),
	})
	var events_path: String = ev.path_join("events.jsonl")
	var ef: FileAccess = FileAccess.open(events_path, FileAccess.WRITE)
	if ef != null:
		var events: Array = StationCasesScript.events_all
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
		"schema": "vault-fighters.vf5-wp4.run.v1",
		"run_id": RUN_ID,
		"command_id": COMMAND_ID,
		"wp": "VF5-WP4",
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
			"NAME": name_v,
			"GRAPH": graph,
			"MACHINE": machine,
			"FLOOR": floor_v,
			"SPAWN": spawn,
			"COVER": cover,
			"DOOR": door,
			"CAMERA": camera,
			"P1": p1,
			"P2": p2,
			"BOT": bot,
			"ZONE": zone,
			"LIVE": live,
			"REPLAY": replay,
			"USED_APPLY_FRAMES": StationCasesScript.used_apply_frames,
			"USED_APPLY_ATTEMPTED": StationCasesScript.used_apply_frames_attempted,
			"USED_APPLY_SUCCEEDED": StationCasesScript.used_apply_frames_succeeded,
		},
		"fail_count": _fails.size(),
	}
	_write_json(ev.path_join("run_partial.json"), run_partial)
	print("HH_VF_STAT EVIDENCE_DIR=%s" % ev)


func _write_json(path: String, data: Variant) -> void:
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		print("HH_VF_STAT EVIDENCE_WRITE_FAIL %s" % path)
		return
	f.store_string(JSON.stringify(data, "\t"))
	f.close()

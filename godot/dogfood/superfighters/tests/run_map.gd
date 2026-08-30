extends SceneTree

const RUN_ID := "VF5WP1-20260830-ASIA-SAIGON-01"
const COMMAND_ID := "cmd.vf5-wp1.map-schema.1"
const SEED := 11
const MODE := "vs2"
const MAP_ID := "rooftops"

const MapCasesScript: GDScript = preload("res://tests/map_cases.gd")

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
	_setup_shot = _maybe_shot(app, "map_setup")
	var errors: PackedStringArray = await MapCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	var schema_v: String = str(MapCasesScript.outcome_schema.get("verdict", "unproven"))
	var roundtrip: String = str(MapCasesScript.outcome_roundtrip.get("verdict", "unproven"))
	var graph: String = str(MapCasesScript.outcome_graph.get("verdict", "unproven"))
	var reject: String = str(MapCasesScript.outcome_reject.get("verdict", "unproven"))
	var author: String = str(MapCasesScript.outcome_author.get("verdict", "unproven"))
	var width_v: String = str(MapCasesScript.outcome_width.get("verdict", "unproven"))
	var spawn_v: String = str(MapCasesScript.outcome_spawn.get("verdict", "unproven"))
	var pit_v: String = str(MapCasesScript.outcome_pit.get("verdict", "unproven"))
	var camera_v: String = str(MapCasesScript.outcome_camera.get("verdict", "unproven"))
	var overlap_v: String = str(MapCasesScript.outcome_overlap.get("verdict", "unproven"))
	var live: String = str(MapCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(MapCasesScript.outcome_replay.get("verdict", "unproven"))
	if schema_v != "pass":
		_fail("SCHEMA structured outcome is %s" % schema_v)
	if roundtrip != "pass":
		_fail("ROUNDTRIP structured outcome is %s" % roundtrip)
	if graph != "pass":
		_fail("GRAPH structured outcome is %s" % graph)
	if reject != "pass":
		_fail("REJECT structured outcome is %s" % reject)
	if author != "pass":
		_fail("AUTHOR structured outcome is %s" % author)
	if width_v != "pass":
		_fail("WIDTH structured outcome is %s" % width_v)
	if spawn_v != "pass":
		_fail("SPAWN structured outcome is %s" % spawn_v)
	if pit_v != "pass":
		_fail("PIT structured outcome is %s" % pit_v)
	if camera_v != "pass":
		_fail("CAMERA structured outcome is %s" % camera_v)
	if overlap_v != "pass":
		_fail("OVERLAP structured outcome is %s" % overlap_v)
	if live != "pass":
		_fail("LIVE structured outcome is %s" % live)
	if replay != "match":
		_fail("REPLAY structured outcome is %s" % replay)
	var ended_at: String = _iso_local()
	print("HH_VF_MAP run_id=%s" % RUN_ID)
	print("HH_VF_MAP command_id=%s" % COMMAND_ID)
	print("HH_VF_MAP DISPLAY=%s" % DisplayServer.get_name())
	print("HH_VF_MAP SEED=%d MAP=%s MODE=%s" % [SEED, MAP_ID, MODE])
	print("HH_VF_MAP STARTED_AT=%s ENDED_AT=%s" % [_started_at, ended_at])
	print(
		"HH_VF_MAP USED_STEP_FIXED=%d USED_APPLY_FRAMES=%d USED_APPLY_ATTEMPTED=%d USED_APPLY_SUCCEEDED=%d USED_PARSE_INPUT_EVENT=%d USED_ACTION_PRESS=%d"
		% [
			MapCasesScript.used_step_fixed,
			MapCasesScript.used_apply_frames,
			MapCasesScript.used_apply_frames_attempted,
			MapCasesScript.used_apply_frames_succeeded,
			MapCasesScript.used_parse_input_event,
			MapCasesScript.used_action_press
		]
	)
	print("HH_VF_MAP SCHEMA=%s SCHEMA_SOURCE=outcome_schema" % schema_v)
	print("HH_VF_MAP ROUNDTRIP=%s ROUNDTRIP_SOURCE=outcome_roundtrip" % roundtrip)
	print("HH_VF_MAP GRAPH=%s GRAPH_SOURCE=outcome_graph" % graph)
	print("HH_VF_MAP REJECT=%s REJECT_SOURCE=outcome_reject" % reject)
	print("HH_VF_MAP AUTHOR=%s AUTHOR_SOURCE=outcome_author" % author)
	print("HH_VF_MAP WIDTH=%s WIDTH_SOURCE=outcome_width" % width_v)
	print("HH_VF_MAP SPAWN=%s SPAWN_SOURCE=outcome_spawn" % spawn_v)
	print("HH_VF_MAP PIT=%s PIT_SOURCE=outcome_pit" % pit_v)
	print("HH_VF_MAP CAMERA=%s CAMERA_SOURCE=outcome_camera" % camera_v)
	print("HH_VF_MAP OVERLAP=%s OVERLAP_SOURCE=outcome_overlap" % overlap_v)
	print("HH_VF_MAP LIVE=%s LIVE_SOURCE=outcome_live" % live)
	print("HH_VF_MAP REPLAY=%s REPLAY_SOURCE=outcome_replay" % replay)
	print("HH_VF_MAP LAYERS=assumption GRAPH=assumption VALID=assumption AUTHOR=assumption HOLD_AIM=assumption ROLL_DIVE=unavailable CLOCK=RL-SIM-FIXED-60")
	await _write_evidence(app, ended_at, schema_v, roundtrip, graph, reject, author, width_v, spawn_v, pit_v, camera_v, overlap_v, live, replay)
	if _fails.is_empty():
		print("PASS: Vault Fighters map schema, validator, and authoring")
	else:
		print("FAIL: Vault Fighters map schema, validator, and authoring")
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
		print("HH_VF_MAP SCREENSHOT_%s missing viewport texture" % stem)
		return ""
	var img: Image = tex.get_image()
	if img == null:
		print("HH_VF_MAP SCREENSHOT_%s get_image null" % stem)
		return ""
	var shot: String = ev.path_join("screens").path_join("%s_%dx%d.png" % [stem, int(vis.size.x), int(vis.size.y)])
	var err: Error = img.save_png(shot)
	print("HH_VF_MAP SCREENSHOT_%s err=%d path=%s" % [stem, int(err), shot])
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


func _stage_map(app: App, map_id: String) -> Dictionary:
	var row: Dictionary = {"map": map_id, "dead": 1, "on_floor": 0, "name": "", "hanging": 1}
	if app == null:
		return row
	_clear_live(app)
	app.start_fight("vs2", map_id, 0)
	await SimReplay.sync_physics(app)
	_apply_held(app.session, 36, PackedStringArray())
	await _draw_ready()
	var p1: Fighter = app.session.player1() if app.session != null else null
	row["dead"] = 1 if p1 != null and p1.dead else 0
	row["on_floor"] = 1 if p1 != null and p1.is_on_floor() else 0
	row["hanging"] = 1 if p1 != null and p1.hanging else 0
	row["name"] = Maps.display_name(map_id)
	return row


func _write_evidence(
	app: App, ended_at: String, schema_v: String, roundtrip: String, graph: String, reject: String,
	author: String, width_v: String, spawn_v: String, pit_v: String, camera_v: String, overlap_v: String,
	live: String, replay: String
) -> void:
	var ev: String = OS.get_environment("HH_VF_EVIDENCE_DIR")
	if ev == "":
		ev = ProjectSettings.globalize_path("res://.evidence/%s" % RUN_ID)
	DirAccess.make_dir_recursive_absolute(ev)
	DirAccess.make_dir_recursive_absolute(ev.path_join("screens"))
	_clear_live(app)
	var ids: PackedStringArray = PackedStringArray([
		"rooftops", "storage", "police", "hazardous", "fx_map_author"
	])
	var stems: PackedStringArray = PackedStringArray([
		"map_rooftops", "map_storage", "map_police", "map_hazardous", "map_author"
	])
	var live_shots: Dictionary = {}
	var li: int = 0
	while li < ids.size():
		var mid: String = String(ids[li])
		var live_row: Dictionary = await _stage_map(app, mid)
		var live_shot: String = _maybe_shot(app, String(stems[li]))
		live_shots[mid] = live_shot
		print(
			"HH_VF_MAP SHOT_MAP map=%s name=%s dead=%d on_floor=%d hang=%d path=%s"
			% [
				mid,
				str(live_row.get("name", "")),
				int(live_row.get("dead", 1)),
				int(live_row.get("on_floor", 0)),
				int(live_row.get("hanging", 1)),
				live_shot
			]
		)
		if _windowed() and int(live_row.get("dead", 1)) != 0:
			_fail("DoD still %s must not spawn-kill" % mid)
		if _windowed() and int(live_row.get("on_floor", 0)) != 1:
			_fail("DoD still %s must stand on_floor" % mid)
		if _windowed() and int(live_row.get("hanging", 1)) != 0:
			_fail("DoD still %s must not hang" % mid)
		if _windowed() and live_shot == "":
			_fail("DoD still missing %s" % mid)
		li += 1
	if _windowed() and _setup_shot == "":
		_fail("DoD window still missing setup")
	var outcomes: Dictionary = {
		"schema": MapCasesScript.outcome_schema,
		"roundtrip": MapCasesScript.outcome_roundtrip,
		"graph": MapCasesScript.outcome_graph,
		"reject": MapCasesScript.outcome_reject,
		"author": MapCasesScript.outcome_author,
		"width": MapCasesScript.outcome_width,
		"spawn": MapCasesScript.outcome_spawn,
		"pit": MapCasesScript.outcome_pit,
		"camera": MapCasesScript.outcome_camera,
		"overlap": MapCasesScript.outcome_overlap,
		"live": MapCasesScript.outcome_live,
		"replay": MapCasesScript.outcome_replay,
		"apply": {
			"attempted": MapCasesScript.used_apply_frames_attempted,
			"succeeded": MapCasesScript.used_apply_frames_succeeded,
			"used_apply_frames": MapCasesScript.used_apply_frames,
			"used_step_fixed": MapCasesScript.used_step_fixed,
			"used_parse_input_event": MapCasesScript.used_parse_input_event,
			"used_action_press": MapCasesScript.used_action_press,
		},
	}
	_write_json(ev.path_join("outcomes.json"), outcomes)
	_write_json(ev.path_join("snapshot_start.json"), MapCasesScript.snapshot_start)
	_write_json(ev.path_join("snapshot_end.json"), MapCasesScript.snapshot_end)
	_write_json(ev.path_join("state_hashes.json"), {
		"replay": MapCasesScript.outcome_replay,
		"roundtrip": MapCasesScript.outcome_roundtrip,
		"author": MapCasesScript.outcome_author,
		"seed": SEED,
		"map_id": MAP_ID,
		"mode": MODE,
	})
	var events_path: String = ev.path_join("events.jsonl")
	var ef: FileAccess = FileAccess.open(events_path, FileAccess.WRITE)
	if ef != null:
		var events: Array = MapCasesScript.events_all
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
		"schema": "vault-fighters.vf5-wp1.run.v1",
		"run_id": RUN_ID,
		"command_id": COMMAND_ID,
		"wp": "VF5-WP1",
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
			"SCHEMA": schema_v,
			"ROUNDTRIP": roundtrip,
			"GRAPH": graph,
			"REJECT": reject,
			"AUTHOR": author,
			"WIDTH": width_v,
			"SPAWN": spawn_v,
			"PIT": pit_v,
			"CAMERA": camera_v,
			"OVERLAP": overlap_v,
			"LIVE": live,
			"REPLAY": replay,
			"USED_APPLY_FRAMES": MapCasesScript.used_apply_frames,
			"USED_APPLY_ATTEMPTED": MapCasesScript.used_apply_frames_attempted,
			"USED_APPLY_SUCCEEDED": MapCasesScript.used_apply_frames_succeeded,
		},
		"fail_count": _fails.size(),
	}
	_write_json(ev.path_join("run_partial.json"), run_partial)
	print("HH_VF_MAP EVIDENCE_DIR=%s" % ev)


func _write_json(path: String, data: Variant) -> void:
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		print("HH_VF_MAP EVIDENCE_WRITE_FAIL %s" % path)
		return
	f.store_string(JSON.stringify(data, "\t"))
	f.close()

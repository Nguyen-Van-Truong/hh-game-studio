extends SceneTree

const RUN_ID := "VF5WP5-20260831-ASIA-SAIGON-07"
const COMMAND_ID := "cmd.vf5-wp5.vitriol-sump.8"
const SEED := 15
const MODE := "vs2"
const MAP_ID := "hazardous"

const SewerCasesScript: GDScript = preload("res://tests/sewer_cases.gd")

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
	_setup_shot = _maybe_shot(app, "sewer_setup")
	var errors: PackedStringArray = await SewerCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	var name_v: String = str(SewerCasesScript.outcome_name.get("verdict", "unproven"))
	var graph: String = str(SewerCasesScript.outcome_graph.get("verdict", "unproven"))
	var toxic: String = str(SewerCasesScript.outcome_toxic.get("verdict", "unproven"))
	var dive: String = str(SewerCasesScript.outcome_dive.get("verdict", "unproven"))
	var roll: String = str(SewerCasesScript.outcome_roll.get("verdict", "unproven"))
	var cargo: String = str(SewerCasesScript.outcome_cargo.get("verdict", "unproven"))
	var spawn: String = str(SewerCasesScript.outcome_spawn.get("verdict", "unproven"))
	var camera: String = str(SewerCasesScript.outcome_camera.get("verdict", "unproven"))
	var tactic: String = str(SewerCasesScript.outcome_tactic.get("verdict", "unproven"))
	var p1: String = str(SewerCasesScript.outcome_p1.get("verdict", "unproven"))
	var p2: String = str(SewerCasesScript.outcome_p2.get("verdict", "unproven"))
	var bot: String = str(SewerCasesScript.outcome_bot.get("verdict", "unproven"))
	var zone: String = str(SewerCasesScript.outcome_zone.get("verdict", "unproven"))
	var live: String = str(SewerCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(SewerCasesScript.outcome_replay.get("verdict", "unproven"))
	var variants: String = str(SewerCasesScript.outcome_variants.get("verdict", "unproven"))
	if name_v != "pass":
		_fail("NAME structured outcome is %s" % name_v)
	if graph != "pass":
		_fail("GRAPH structured outcome is %s" % graph)
	if toxic != "pass":
		_fail("TOXIC structured outcome is %s" % toxic)
	if dive != "pass":
		_fail("DIVE structured outcome is %s" % dive)
	if roll != "pass":
		_fail("ROLL structured outcome is %s" % roll)
	if cargo != "pass":
		_fail("CARGO structured outcome is %s" % cargo)
	if spawn != "pass":
		_fail("SPAWN structured outcome is %s" % spawn)
	if camera != "pass":
		_fail("CAMERA structured outcome is %s" % camera)
	if tactic != "pass":
		_fail("TACTIC structured outcome is %s" % tactic)
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
	if variants != "pass":
		_fail("VARIANTS structured outcome is %s" % variants)
	var ended_at: String = _iso_local()
	print("HH_VF_STAT run_id=%s" % RUN_ID)
	print("HH_VF_STAT command_id=%s" % COMMAND_ID)
	print("HH_VF_STAT DISPLAY=%s" % DisplayServer.get_name())
	print("HH_VF_STAT SEED=%d MAP=%s MODE=%s NAME=%s" % [SEED, MAP_ID, MODE, Maps.display_name(MAP_ID)])
	print("HH_VF_STAT STARTED_AT=%s ENDED_AT=%s" % [_started_at, ended_at])
	print(
		"HH_VF_STAT USED_STEP_FIXED=%d USED_APPLY_FRAMES=%d USED_APPLY_ATTEMPTED=%d USED_APPLY_SUCCEEDED=%d USED_PARSE_INPUT_EVENT=%d USED_ACTION_PRESS=%d"
		% [
			SewerCasesScript.used_step_fixed,
			SewerCasesScript.used_apply_frames,
			SewerCasesScript.used_apply_frames_attempted,
			SewerCasesScript.used_apply_frames_succeeded,
			SewerCasesScript.used_parse_input_event,
			SewerCasesScript.used_action_press
		]
	)
	print("HH_VF_STAT NAME=%s NAME_SOURCE=outcome_name" % name_v)
	print("HH_VF_STAT GRAPH=%s GRAPH_SOURCE=outcome_graph" % graph)
	print("HH_VF_STAT TOXIC=%s TOXIC_SOURCE=outcome_toxic" % toxic)
	print("HH_VF_STAT DIVE=%s DIVE_SOURCE=outcome_dive" % dive)
	print("HH_VF_STAT ROLL=%s ROLL_SOURCE=outcome_roll" % roll)
	print("HH_VF_STAT CARGO=%s CARGO_SOURCE=outcome_cargo" % cargo)
	print("HH_VF_STAT SPAWN=%s SPAWN_SOURCE=outcome_spawn" % spawn)
	print("HH_VF_STAT CAMERA=%s CAMERA_SOURCE=outcome_camera" % camera)
	print("HH_VF_STAT TACTIC=%s TACTIC_SOURCE=outcome_tactic" % tactic)
	print("HH_VF_STAT P1=%s P1_SOURCE=outcome_p1" % p1)
	print("HH_VF_STAT P2=%s P2_SOURCE=outcome_p2 P2_COVERAGE=smoke" % p2)
	print("HH_VF_STAT BOT=%s BOT_SOURCE=outcome_bot BOT_COVERAGE=smoke" % bot)
	print("HH_VF_STAT ZONE=%s ZONE_SOURCE=outcome_zone" % zone)
	print("HH_VF_STAT LIVE=%s LIVE_SOURCE=outcome_live" % live)
	print("HH_VF_STAT REPLAY=%s REPLAY_SOURCE=outcome_replay" % replay)
	print("HH_VF_STAT VARIANTS=%s VARIANTS_SOURCE=outcome_variants" % variants)
	print("HH_VF_STAT HONESTY P2=preset_ladder_smoke BOT=east_ladder_then_chase_smoke P1=full_safe_zone_tour NOT_AI=1 NOT_Y8_PARITY=1")
	print("HH_VF_STAT SUMP=assumption LAYERS=assumption GRAPH=assumption HOLD_AIM=assumption ROLL_DIVE=unavailable CLOCK=RL-SIM-FIXED-60")
	print(
		"HH_VF_STAT LIVE_ZONES P1=%s P2=%s BOT=%s CLIMB_UP_ON_LADDER=%s"
		% [
			str(SewerCasesScript.outcome_p1.get("hits", {})),
			str(SewerCasesScript.outcome_p2.get("hits", {})),
			str(SewerCasesScript.outcome_bot.get("hits", {})),
			str(SewerCasesScript.outcome_zone.get("climb_up_on_ladder", 0)),
		]
	)
	await _write_evidence(app, ended_at, name_v, graph, toxic, dive, roll, cargo, spawn, camera, tactic, p1, p2, bot, zone, live, replay, variants)
	if _fails.is_empty():
		print("PASS: Vault Fighters Vitriol Sump sewer arena")
	else:
		print("FAIL: Vault Fighters Vitriol Sump sewer arena")
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
	var allow_lose: bool = bool(row.get("allow_lose", false))
	if lose and not allow_lose:
		_fail("%s still has lose overlay" % name)
	if name == "toxic":
		return
	if not bool(row.get("alive", false)):
		_fail("%s still actor is not alive" % name)
	if not bool(row.get("on_floor", false)):
		_fail("%s still actor is not standing on_floor" % name)
	if bool(row.get("hanging", false)):
		_fail("%s still actor is hanging" % name)
	var zid: String = str(row.get("zone", ""))
	if name == "pipes" and zid != "west_high" and zid != "mid_west" and zid != "west_mid":
		_fail("pipes still must occupy an isolated pipe got %s" % zid)
	if name == "crossing" and zid != "mid_east" and zid != "mid_west" and zid != "mid_low":
		_fail("crossing still must occupy a safe pipe over the pool got %s" % zid)
	if name == "cargo" and zid != "mid_west" and zid != "west_high":
		_fail("cargo still must occupy the hanging-crate pipe got %s" % zid)
	if name == "lip" and zid != "sump_lip":
		_fail("lip still must occupy sump_lip standing")


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
	app: App, ended_at: String, name_v: String, graph: String, toxic: String, dive: String,
	roll: String, cargo: String, spawn: String, camera: String, tactic: String, p1: String,
	p2: String, bot: String, zone: String, live: String, replay: String, variants: String
) -> void:
	var ev: String = OS.get_environment("HH_VF_EVIDENCE_DIR")
	if ev == "":
		ev = ProjectSettings.globalize_path("res://.evidence/%s" % RUN_ID)
	DirAccess.make_dir_recursive_absolute(ev)
	DirAccess.make_dir_recursive_absolute(ev.path_join("screens"))
	var live_shots: Dictionary = {}
	app.restart_to_title()
	await _draw_ready()
	live_shots["title"] = _maybe_shot(app, "sewer_title")
	if _windowed() and str(live_shots.get("title", "")) == "":
		_fail("DoD still missing title")
	await SewerCasesScript.stage_pipes(app)
	_assert_standing_still(app, SewerCasesScript.outcome_pipes_still, "pipes")
	await _draw_ready()
	live_shots["pipes"] = _maybe_shot(app, "sewer_pipes")
	if _windowed() and str(live_shots.get("pipes", "")) == "":
		_fail("DoD still missing pipes landmark")
	await SewerCasesScript.stage_crossing(app)
	_assert_standing_still(app, SewerCasesScript.outcome_crossing_still, "crossing")
	await _draw_ready()
	live_shots["crossing"] = _maybe_shot(app, "sewer_crossing")
	if _windowed() and str(live_shots.get("crossing", "")) == "":
		_fail("DoD still missing crossing landmark")
	await SewerCasesScript.stage_cargo(app)
	_assert_standing_still(app, SewerCasesScript.outcome_cargo_still, "cargo")
	await _draw_ready()
	live_shots["cargo"] = _maybe_shot(app, "sewer_cargo")
	if _windowed() and str(live_shots.get("cargo", "")) == "":
		_fail("DoD still missing cargo landmark")
	await SewerCasesScript.stage_lip(app)
	_assert_standing_still(app, SewerCasesScript.outcome_lip_still, "lip")
	await _draw_ready()
	live_shots["lip"] = _maybe_shot(app, "sewer_lip")
	if _windowed() and str(live_shots.get("lip", "")) == "":
		_fail("DoD still missing lip landmark")
	await SewerCasesScript.stage_toxic(app)
	_assert_standing_still(app, SewerCasesScript.outcome_toxic_still, "toxic")
	await _draw_ready()
	live_shots["toxic"] = _maybe_shot(app, "sewer_toxic")
	if _windowed() and str(live_shots.get("toxic", "")) == "":
		_fail("DoD still missing toxic landmark")
	if _windowed() and _setup_shot == "":
		_fail("DoD window still missing setup")
	var outcomes: Dictionary = {
		"name": SewerCasesScript.outcome_name,
		"graph": SewerCasesScript.outcome_graph,
		"toxic": SewerCasesScript.outcome_toxic,
		"dive": SewerCasesScript.outcome_dive,
		"roll": SewerCasesScript.outcome_roll,
		"cargo": SewerCasesScript.outcome_cargo,
		"spawn": SewerCasesScript.outcome_spawn,
		"camera": SewerCasesScript.outcome_camera,
		"tactic": SewerCasesScript.outcome_tactic,
		"p1": SewerCasesScript.outcome_p1,
		"p2": SewerCasesScript.outcome_p2,
		"bot": SewerCasesScript.outcome_bot,
		"zone": SewerCasesScript.outcome_zone,
		"live": SewerCasesScript.outcome_live,
		"replay": SewerCasesScript.outcome_replay,
		"variants": SewerCasesScript.outcome_variants,
		"pipes_still": SewerCasesScript.outcome_pipes_still,
		"crossing_still": SewerCasesScript.outcome_crossing_still,
		"cargo_still": SewerCasesScript.outcome_cargo_still,
		"lip_still": SewerCasesScript.outcome_lip_still,
		"toxic_still": SewerCasesScript.outcome_toxic_still,
		"apply": {
			"attempted": SewerCasesScript.used_apply_frames_attempted,
			"succeeded": SewerCasesScript.used_apply_frames_succeeded,
			"used_apply_frames": SewerCasesScript.used_apply_frames,
			"used_step_fixed": SewerCasesScript.used_step_fixed,
			"used_parse_input_event": SewerCasesScript.used_parse_input_event,
			"used_action_press": SewerCasesScript.used_action_press,
		},
	}
	_write_json(ev.path_join("outcomes.json"), outcomes)
	_write_json(ev.path_join("snapshot_start.json"), SewerCasesScript.snapshot_start)
	_write_json(ev.path_join("snapshot_end.json"), SewerCasesScript.snapshot_end)
	_write_json(ev.path_join("state_hashes.json"), {
		"replay": SewerCasesScript.outcome_replay,
		"seed": SEED,
		"map_id": MAP_ID,
		"mode": MODE,
		"display": Maps.display_name(MAP_ID),
	})
	var events_path: String = ev.path_join("events.jsonl")
	var ef: FileAccess = FileAccess.open(events_path, FileAccess.WRITE)
	if ef != null:
		var events: Array = SewerCasesScript.events_all
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
		"schema": "vault-fighters.vf5-wp5.run.v1",
		"run_id": RUN_ID,
		"command_id": COMMAND_ID,
		"wp": "VF5-WP5",
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
			"TOXIC": toxic,
			"DIVE": dive,
			"ROLL": roll,
			"CARGO": cargo,
			"SPAWN": spawn,
			"CAMERA": camera,
			"TACTIC": tactic,
			"P1": p1,
			"P2": p2,
			"BOT": bot,
			"ZONE": zone,
			"LIVE": live,
			"REPLAY": replay,
			"VARIANTS": variants,
			"USED_APPLY_FRAMES": SewerCasesScript.used_apply_frames,
			"USED_APPLY_ATTEMPTED": SewerCasesScript.used_apply_frames_attempted,
			"USED_APPLY_SUCCEEDED": SewerCasesScript.used_apply_frames_succeeded,
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

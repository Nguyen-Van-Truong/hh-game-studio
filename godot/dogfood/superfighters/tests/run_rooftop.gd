extends SceneTree

const RUN_ID := "VF5WP2-20260830-ASIA-SAIGON-02"
const COMMAND_ID := "cmd.vf5-wp2.skyline-relay.2"
const SEED := 12
const MODE := "vs2"
const MAP_ID := "rooftops"

const RooftopCasesScript: GDScript = preload("res://tests/rooftop_cases.gd")

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
	_setup_shot = _maybe_shot(app, "rooftop_setup")
	var errors: PackedStringArray = await RooftopCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	var name_v: String = str(RooftopCasesScript.outcome_name.get("verdict", "unproven"))
	var elev: String = str(RooftopCasesScript.outcome_elev.get("verdict", "unproven"))
	var zone: String = str(RooftopCasesScript.outcome_zone.get("verdict", "unproven"))
	var cover: String = str(RooftopCasesScript.outcome_cover.get("verdict", "unproven"))
	var p1: String = str(RooftopCasesScript.outcome_p1.get("verdict", "unproven"))
	var p2: String = str(RooftopCasesScript.outcome_p2.get("verdict", "unproven"))
	var bot: String = str(RooftopCasesScript.outcome_bot.get("verdict", "unproven"))
	var pit: String = str(RooftopCasesScript.outcome_pit.get("verdict", "unproven"))
	var fallback: String = str(RooftopCasesScript.outcome_fallback.get("verdict", "unproven"))
	var live: String = str(RooftopCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(RooftopCasesScript.outcome_replay.get("verdict", "unproven"))
	if name_v != "pass":
		_fail("NAME structured outcome is %s" % name_v)
	if elev != "pass":
		_fail("ELEV structured outcome is %s" % elev)
	if zone != "pass":
		_fail("ZONE structured outcome is %s" % zone)
	if cover != "pass":
		_fail("COVER structured outcome is %s" % cover)
	if p1 != "pass":
		_fail("P1 structured outcome is %s" % p1)
	if p2 != "pass":
		_fail("P2 structured outcome is %s" % p2)
	if bot != "pass":
		_fail("BOT structured outcome is %s" % bot)
	if pit != "pass":
		_fail("PIT structured outcome is %s" % pit)
	if fallback != "pass":
		_fail("FALLBACK structured outcome is %s" % fallback)
	if live != "pass":
		_fail("LIVE structured outcome is %s" % live)
	if replay != "match":
		_fail("REPLAY structured outcome is %s" % replay)
	var ended_at: String = _iso_local()
	print("HH_VF_ROOF run_id=%s" % RUN_ID)
	print("HH_VF_ROOF command_id=%s" % COMMAND_ID)
	print("HH_VF_ROOF DISPLAY=%s" % DisplayServer.get_name())
	print("HH_VF_ROOF SEED=%d MAP=%s MODE=%s NAME=%s" % [SEED, MAP_ID, MODE, Maps.display_name(MAP_ID)])
	print("HH_VF_ROOF STARTED_AT=%s ENDED_AT=%s" % [_started_at, ended_at])
	print(
		"HH_VF_ROOF USED_STEP_FIXED=%d USED_APPLY_FRAMES=%d USED_APPLY_ATTEMPTED=%d USED_APPLY_SUCCEEDED=%d USED_PARSE_INPUT_EVENT=%d USED_ACTION_PRESS=%d"
		% [
			RooftopCasesScript.used_step_fixed,
			RooftopCasesScript.used_apply_frames,
			RooftopCasesScript.used_apply_frames_attempted,
			RooftopCasesScript.used_apply_frames_succeeded,
			RooftopCasesScript.used_parse_input_event,
			RooftopCasesScript.used_action_press
		]
	)
	print("HH_VF_ROOF NAME=%s NAME_SOURCE=outcome_name" % name_v)
	print("HH_VF_ROOF ELEV=%s ELEV_SOURCE=outcome_elev" % elev)
	print("HH_VF_ROOF ZONE=%s ZONE_SOURCE=outcome_zone" % zone)
	print("HH_VF_ROOF COVER=%s COVER_SOURCE=outcome_cover" % cover)
	print("HH_VF_ROOF P1=%s P1_SOURCE=outcome_p1" % p1)
	print("HH_VF_ROOF P2=%s P2_SOURCE=outcome_p2" % p2)
	print("HH_VF_ROOF BOT=%s BOT_SOURCE=outcome_bot" % bot)
	print("HH_VF_ROOF PIT=%s PIT_SOURCE=outcome_pit" % pit)
	print("HH_VF_ROOF FALLBACK=%s FALLBACK_SOURCE=outcome_fallback" % fallback)
	print("HH_VF_ROOF LIVE=%s LIVE_SOURCE=outcome_live" % live)
	print("HH_VF_ROOF REPLAY=%s REPLAY_SOURCE=outcome_replay" % replay)
	print("HH_VF_ROOF SKYLINE=assumption LAYERS=assumption GRAPH=assumption HOLD_AIM=assumption ROLL_DIVE=unavailable CLOCK=RL-SIM-FIXED-60")
	print(
		"HH_VF_ROOF LIVE_ZONES P1=%s P2=%s BOT=%s SPIRE_STAND=%s EAST_DECK=%s CLIMB_UP_ON_LADDER=%s"
		% [
			str(RooftopCasesScript.outcome_p1.get("hits", {})),
			str(RooftopCasesScript.outcome_p2.get("hits", {})),
			str(RooftopCasesScript.outcome_bot.get("hits", {})),
			str(RooftopCasesScript.outcome_zone.get("west_spire_standing", false)),
			str(RooftopCasesScript.outcome_zone.get("east_deck_live", false)),
			str(RooftopCasesScript.outcome_zone.get("climb_up_on_ladder", 0)),
		]
	)
	await _write_evidence(app, ended_at, name_v, elev, zone, cover, p1, p2, bot, pit, fallback, live, replay)
	if _fails.is_empty():
		print("PASS: Vault Fighters Skyline Relay rooftop arena")
	else:
		print("FAIL: Vault Fighters Skyline Relay rooftop arena")
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
	if name == "cover" and str(row.get("zone", "")) != "west_spire":
		_fail("cover/high-ground still must occupy west_spire standing")
	if name == "bridge":
		var zid: String = str(row.get("zone", ""))
		if zid != "west_bridge" and zid != "east_bridge":
			_fail("bridge still must occupy a catwalk zone got %s" % zid)


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
		print("HH_VF_ROOF SCREENSHOT_%s missing viewport texture" % stem)
		return ""
	var img: Image = tex.get_image()
	if img == null:
		print("HH_VF_ROOF SCREENSHOT_%s get_image null" % stem)
		return ""
	var shot: String = ev.path_join("screens").path_join("%s_%dx%d.png" % [stem, int(vis.size.x), int(vis.size.y)])
	var err: Error = img.save_png(shot)
	print("HH_VF_ROOF SCREENSHOT_%s err=%d path=%s" % [stem, int(err), shot])
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
	app: App, ended_at: String, name_v: String, elev: String, zone: String, cover: String,
	p1: String, p2: String, bot: String, pit: String, fallback: String, live: String, replay: String
) -> void:
	var ev: String = OS.get_environment("HH_VF_EVIDENCE_DIR")
	if ev == "":
		ev = ProjectSettings.globalize_path("res://.evidence/%s" % RUN_ID)
	DirAccess.make_dir_recursive_absolute(ev)
	DirAccess.make_dir_recursive_absolute(ev.path_join("screens"))
	var live_shots: Dictionary = {}
	app.restart_to_title()
	await _draw_ready()
	live_shots["title"] = _maybe_shot(app, "rooftop_title")
	if _windowed() and str(live_shots.get("title", "")) == "":
		_fail("DoD still missing title")
	await RooftopCasesScript.stage_bridge(app)
	_assert_standing_still(app, RooftopCasesScript.outcome_bridge_still, "bridge")
	await _draw_ready()
	live_shots["bridge"] = _maybe_shot(app, "rooftop_bridge")
	if _windowed() and str(live_shots.get("bridge", "")) == "":
		_fail("DoD still missing bridge landmark")
	await RooftopCasesScript.stage_cover(app)
	_assert_standing_still(app, RooftopCasesScript.outcome_cover_still, "cover")
	await _draw_ready()
	live_shots["cover"] = _maybe_shot(app, "rooftop_cover")
	if _windowed() and str(live_shots.get("cover", "")) == "":
		_fail("DoD still missing cover landmark")
	await RooftopCasesScript.stage_pit(app)
	await _draw_ready()
	live_shots["pit"] = _maybe_shot(app, "rooftop_pit")
	if _windowed() and str(live_shots.get("pit", "")) == "":
		_fail("DoD still missing pit landmark")
	var pit_row: Dictionary = RooftopCasesScript.outcome_pit_still
	if _windowed() and not bool(pit_row.get("allow_lose", false)):
		_fail("pit still must be a dedicated walk-off")
	if _windowed() and _setup_shot == "":
		_fail("DoD window still missing setup")
	var outcomes: Dictionary = {
		"name": RooftopCasesScript.outcome_name,
		"elev": RooftopCasesScript.outcome_elev,
		"zone": RooftopCasesScript.outcome_zone,
		"cover": RooftopCasesScript.outcome_cover,
		"p1": RooftopCasesScript.outcome_p1,
		"p2": RooftopCasesScript.outcome_p2,
		"bot": RooftopCasesScript.outcome_bot,
		"pit": RooftopCasesScript.outcome_pit,
		"fallback": RooftopCasesScript.outcome_fallback,
		"live": RooftopCasesScript.outcome_live,
		"replay": RooftopCasesScript.outcome_replay,
		"bridge_still": RooftopCasesScript.outcome_bridge_still,
		"cover_still": RooftopCasesScript.outcome_cover_still,
		"pit_still": RooftopCasesScript.outcome_pit_still,
		"apply": {
			"attempted": RooftopCasesScript.used_apply_frames_attempted,
			"succeeded": RooftopCasesScript.used_apply_frames_succeeded,
			"used_apply_frames": RooftopCasesScript.used_apply_frames,
			"used_step_fixed": RooftopCasesScript.used_step_fixed,
			"used_parse_input_event": RooftopCasesScript.used_parse_input_event,
			"used_action_press": RooftopCasesScript.used_action_press,
		},
	}
	_write_json(ev.path_join("outcomes.json"), outcomes)
	_write_json(ev.path_join("snapshot_start.json"), RooftopCasesScript.snapshot_start)
	_write_json(ev.path_join("snapshot_end.json"), RooftopCasesScript.snapshot_end)
	_write_json(ev.path_join("state_hashes.json"), {
		"replay": RooftopCasesScript.outcome_replay,
		"seed": SEED,
		"map_id": MAP_ID,
		"mode": MODE,
		"display": Maps.display_name(MAP_ID),
	})
	var events_path: String = ev.path_join("events.jsonl")
	var ef: FileAccess = FileAccess.open(events_path, FileAccess.WRITE)
	if ef != null:
		var events: Array = RooftopCasesScript.events_all
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
		"schema": "vault-fighters.vf5-wp2.run.v1",
		"run_id": RUN_ID,
		"command_id": COMMAND_ID,
		"wp": "VF5-WP2",
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
			"ELEV": elev,
			"ZONE": zone,
			"COVER": cover,
			"P1": p1,
			"P2": p2,
			"BOT": bot,
			"PIT": pit,
			"FALLBACK": fallback,
			"LIVE": live,
			"REPLAY": replay,
			"USED_APPLY_FRAMES": RooftopCasesScript.used_apply_frames,
			"USED_APPLY_ATTEMPTED": RooftopCasesScript.used_apply_frames_attempted,
			"USED_APPLY_SUCCEEDED": RooftopCasesScript.used_apply_frames_succeeded,
		},
		"fail_count": _fails.size(),
	}
	_write_json(ev.path_join("run_partial.json"), run_partial)
	print("HH_VF_ROOF EVIDENCE_DIR=%s" % ev)


func _write_json(path: String, data: Variant) -> void:
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		print("HH_VF_ROOF EVIDENCE_WRITE_FAIL %s" % path)
		return
	f.store_string(JSON.stringify(data, "\t"))
	f.close()

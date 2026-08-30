extends SceneTree

const RUN_ID := "VF5WP3-20260830-ASIA-SAIGON-01"
const COMMAND_ID := "cmd.vf5-wp3.pallet-annex.1"
const SEED := 13
const MODE := "vs2"
const MAP_ID := "storage"

const WarehouseCasesScript: GDScript = preload("res://tests/warehouse_cases.gd")

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
	_setup_shot = _maybe_shot(app, "warehouse_setup")
	var errors: PackedStringArray = await WarehouseCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	var name_v: String = str(WarehouseCasesScript.outcome_name.get("verdict", "unproven"))
	var cover: String = str(WarehouseCasesScript.outcome_cover.get("verdict", "unproven"))
	var cargo: String = str(WarehouseCasesScript.outcome_cargo.get("verdict", "unproven"))
	var spawn: String = str(WarehouseCasesScript.outcome_spawn.get("verdict", "unproven"))
	var camera: String = str(WarehouseCasesScript.outcome_camera.get("verdict", "unproven"))
	var weapon: String = str(WarehouseCasesScript.outcome_weapon.get("verdict", "unproven"))
	var p1: String = str(WarehouseCasesScript.outcome_p1.get("verdict", "unproven"))
	var p2: String = str(WarehouseCasesScript.outcome_p2.get("verdict", "unproven"))
	var bot: String = str(WarehouseCasesScript.outcome_bot.get("verdict", "unproven"))
	var zone: String = str(WarehouseCasesScript.outcome_zone.get("verdict", "unproven"))
	var door: String = str(WarehouseCasesScript.outcome_door.get("verdict", "unproven"))
	var live: String = str(WarehouseCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(WarehouseCasesScript.outcome_replay.get("verdict", "unproven"))
	if name_v != "pass":
		_fail("NAME structured outcome is %s" % name_v)
	if cover != "pass":
		_fail("COVER structured outcome is %s" % cover)
	if cargo != "pass":
		_fail("CARGO structured outcome is %s" % cargo)
	if spawn != "pass":
		_fail("SPAWN structured outcome is %s" % spawn)
	if camera != "pass":
		_fail("CAMERA structured outcome is %s" % camera)
	if weapon != "pass":
		_fail("WEAPON structured outcome is %s" % weapon)
	if p1 != "pass":
		_fail("P1 structured outcome is %s" % p1)
	if p2 != "pass":
		_fail("P2 structured outcome is %s" % p2)
	if bot != "pass":
		_fail("BOT structured outcome is %s" % bot)
	if zone != "pass":
		_fail("ZONE structured outcome is %s" % zone)
	if door != "pass":
		_fail("DOOR structured outcome is %s" % door)
	if live != "pass":
		_fail("LIVE structured outcome is %s" % live)
	if replay != "match":
		_fail("REPLAY structured outcome is %s" % replay)
	var ended_at: String = _iso_local()
	print("HH_VF_WARE run_id=%s" % RUN_ID)
	print("HH_VF_WARE command_id=%s" % COMMAND_ID)
	print("HH_VF_WARE DISPLAY=%s" % DisplayServer.get_name())
	print("HH_VF_WARE SEED=%d MAP=%s MODE=%s NAME=%s" % [SEED, MAP_ID, MODE, Maps.display_name(MAP_ID)])
	print("HH_VF_WARE STARTED_AT=%s ENDED_AT=%s" % [_started_at, ended_at])
	print(
		"HH_VF_WARE USED_STEP_FIXED=%d USED_APPLY_FRAMES=%d USED_APPLY_ATTEMPTED=%d USED_APPLY_SUCCEEDED=%d USED_PARSE_INPUT_EVENT=%d USED_ACTION_PRESS=%d"
		% [
			WarehouseCasesScript.used_step_fixed,
			WarehouseCasesScript.used_apply_frames,
			WarehouseCasesScript.used_apply_frames_attempted,
			WarehouseCasesScript.used_apply_frames_succeeded,
			WarehouseCasesScript.used_parse_input_event,
			WarehouseCasesScript.used_action_press
		]
	)
	print("HH_VF_WARE NAME=%s NAME_SOURCE=outcome_name" % name_v)
	print("HH_VF_WARE COVER=%s COVER_SOURCE=outcome_cover" % cover)
	print("HH_VF_WARE CARGO=%s CARGO_SOURCE=outcome_cargo" % cargo)
	print("HH_VF_WARE SPAWN=%s SPAWN_SOURCE=outcome_spawn" % spawn)
	print("HH_VF_WARE CAMERA=%s CAMERA_SOURCE=outcome_camera" % camera)
	print("HH_VF_WARE WEAPON=%s WEAPON_SOURCE=outcome_weapon" % weapon)
	print("HH_VF_WARE P1=%s P1_SOURCE=outcome_p1" % p1)
	print("HH_VF_WARE P2=%s P2_SOURCE=outcome_p2" % p2)
	print("HH_VF_WARE BOT=%s BOT_SOURCE=outcome_bot" % bot)
	print("HH_VF_WARE ZONE=%s ZONE_SOURCE=outcome_zone" % zone)
	print("HH_VF_WARE DOOR=%s DOOR_SOURCE=outcome_door" % door)
	print("HH_VF_WARE LIVE=%s LIVE_SOURCE=outcome_live" % live)
	print("HH_VF_WARE REPLAY=%s REPLAY_SOURCE=outcome_replay" % replay)
	print("HH_VF_WARE PALLET=assumption LAYERS=assumption GRAPH=assumption HOLD_AIM=assumption ROLL_DIVE=unavailable CLOCK=RL-SIM-FIXED-60")
	print(
		"HH_VF_WARE LIVE_ZONES P1=%s P2=%s BOT=%s OFFICE_STAND=%s EAST_CAT=%s CLIMB_UP_ON_LADDER=%s"
		% [
			str(WarehouseCasesScript.outcome_p1.get("hits", {})),
			str(WarehouseCasesScript.outcome_p2.get("hits", {})),
			str(WarehouseCasesScript.outcome_bot.get("hits", {})),
			str(WarehouseCasesScript.outcome_zone.get("office_standing", false)),
			str(WarehouseCasesScript.outcome_zone.get("east_catwalk_live", false)),
			str(WarehouseCasesScript.outcome_zone.get("climb_up_on_ladder", 0)),
		]
	)
	await _write_evidence(app, ended_at, name_v, cover, cargo, spawn, camera, weapon, p1, p2, bot, zone, door, live, replay)
	if _fails.is_empty():
		print("PASS: Vault Fighters Pallet Annex warehouse arena")
	else:
		print("FAIL: Vault Fighters Pallet Annex warehouse arena")
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
	if name == "cover" and zid != "mid_floor" and zid != "west_floor" and zid != "east_floor":
		_fail("cover still must occupy a floor zone standing got %s" % zid)
	if name == "catwalk":
		if zid != "west_catwalk" and zid != "mid_catwalk" and zid != "east_catwalk":
			_fail("catwalk still must occupy a catwalk zone got %s" % zid)
	if name == "cargo" and zid != "east_catwalk" and zid != "east_floor" and zid != "mid_catwalk" and zid != "west_catwalk":
		_fail("cargo still must occupy a cargo catwalk route got %s" % zid)
	if name == "office" and zid != "office_loft":
		_fail("office still must occupy office_loft standing")


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
		print("HH_VF_WARE SCREENSHOT_%s missing viewport texture" % stem)
		return ""
	var img: Image = tex.get_image()
	if img == null:
		print("HH_VF_WARE SCREENSHOT_%s get_image null" % stem)
		return ""
	var shot: String = ev.path_join("screens").path_join("%s_%dx%d.png" % [stem, int(vis.size.x), int(vis.size.y)])
	var err: Error = img.save_png(shot)
	print("HH_VF_WARE SCREENSHOT_%s err=%d path=%s" % [stem, int(err), shot])
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
	app: App, ended_at: String, name_v: String, cover: String, cargo: String, spawn: String,
	camera: String, weapon: String, p1: String, p2: String, bot: String, zone: String,
	door: String, live: String, replay: String
) -> void:
	var ev: String = OS.get_environment("HH_VF_EVIDENCE_DIR")
	if ev == "":
		ev = ProjectSettings.globalize_path("res://.evidence/%s" % RUN_ID)
	DirAccess.make_dir_recursive_absolute(ev)
	DirAccess.make_dir_recursive_absolute(ev.path_join("screens"))
	var live_shots: Dictionary = {}
	app.restart_to_title()
	await _draw_ready()
	live_shots["title"] = _maybe_shot(app, "warehouse_title")
	if _windowed() and str(live_shots.get("title", "")) == "":
		_fail("DoD still missing title")
	await WarehouseCasesScript.stage_catwalk(app)
	_assert_standing_still(app, WarehouseCasesScript.outcome_catwalk_still, "catwalk")
	await _draw_ready()
	live_shots["catwalk"] = _maybe_shot(app, "warehouse_catwalk")
	if _windowed() and str(live_shots.get("catwalk", "")) == "":
		_fail("DoD still missing catwalk landmark")
	await WarehouseCasesScript.stage_cover(app)
	_assert_standing_still(app, WarehouseCasesScript.outcome_cover_still, "cover")
	await _draw_ready()
	live_shots["cover"] = _maybe_shot(app, "warehouse_cover")
	if _windowed() and str(live_shots.get("cover", "")) == "":
		_fail("DoD still missing cover landmark")
	await WarehouseCasesScript.stage_cargo(app)
	_assert_standing_still(app, WarehouseCasesScript.outcome_cargo_still, "cargo")
	await _draw_ready()
	live_shots["cargo"] = _maybe_shot(app, "warehouse_cargo")
	if _windowed() and str(live_shots.get("cargo", "")) == "":
		_fail("DoD still missing cargo landmark")
	await WarehouseCasesScript.stage_office(app)
	_assert_standing_still(app, WarehouseCasesScript.outcome_office_still, "office")
	await _draw_ready()
	live_shots["office"] = _maybe_shot(app, "warehouse_office")
	if _windowed() and str(live_shots.get("office", "")) == "":
		_fail("DoD still missing office landmark")
	if _windowed() and _setup_shot == "":
		_fail("DoD window still missing setup")
	var outcomes: Dictionary = {
		"name": WarehouseCasesScript.outcome_name,
		"cover": WarehouseCasesScript.outcome_cover,
		"cargo": WarehouseCasesScript.outcome_cargo,
		"spawn": WarehouseCasesScript.outcome_spawn,
		"camera": WarehouseCasesScript.outcome_camera,
		"weapon": WarehouseCasesScript.outcome_weapon,
		"p1": WarehouseCasesScript.outcome_p1,
		"p2": WarehouseCasesScript.outcome_p2,
		"bot": WarehouseCasesScript.outcome_bot,
		"zone": WarehouseCasesScript.outcome_zone,
		"door": WarehouseCasesScript.outcome_door,
		"live": WarehouseCasesScript.outcome_live,
		"replay": WarehouseCasesScript.outcome_replay,
		"catwalk_still": WarehouseCasesScript.outcome_catwalk_still,
		"cover_still": WarehouseCasesScript.outcome_cover_still,
		"cargo_still": WarehouseCasesScript.outcome_cargo_still,
		"office_still": WarehouseCasesScript.outcome_office_still,
		"apply": {
			"attempted": WarehouseCasesScript.used_apply_frames_attempted,
			"succeeded": WarehouseCasesScript.used_apply_frames_succeeded,
			"used_apply_frames": WarehouseCasesScript.used_apply_frames,
			"used_step_fixed": WarehouseCasesScript.used_step_fixed,
			"used_parse_input_event": WarehouseCasesScript.used_parse_input_event,
			"used_action_press": WarehouseCasesScript.used_action_press,
		},
	}
	_write_json(ev.path_join("outcomes.json"), outcomes)
	_write_json(ev.path_join("snapshot_start.json"), WarehouseCasesScript.snapshot_start)
	_write_json(ev.path_join("snapshot_end.json"), WarehouseCasesScript.snapshot_end)
	_write_json(ev.path_join("state_hashes.json"), {
		"replay": WarehouseCasesScript.outcome_replay,
		"seed": SEED,
		"map_id": MAP_ID,
		"mode": MODE,
		"display": Maps.display_name(MAP_ID),
	})
	var events_path: String = ev.path_join("events.jsonl")
	var ef: FileAccess = FileAccess.open(events_path, FileAccess.WRITE)
	if ef != null:
		var events: Array = WarehouseCasesScript.events_all
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
		"schema": "vault-fighters.vf5-wp3.run.v1",
		"run_id": RUN_ID,
		"command_id": COMMAND_ID,
		"wp": "VF5-WP3",
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
			"COVER": cover,
			"CARGO": cargo,
			"SPAWN": spawn,
			"CAMERA": camera,
			"WEAPON": weapon,
			"P1": p1,
			"P2": p2,
			"BOT": bot,
			"ZONE": zone,
			"DOOR": door,
			"LIVE": live,
			"REPLAY": replay,
			"USED_APPLY_FRAMES": WarehouseCasesScript.used_apply_frames,
			"USED_APPLY_ATTEMPTED": WarehouseCasesScript.used_apply_frames_attempted,
			"USED_APPLY_SUCCEEDED": WarehouseCasesScript.used_apply_frames_succeeded,
		},
		"fail_count": _fails.size(),
	}
	_write_json(ev.path_join("run_partial.json"), run_partial)
	print("HH_VF_WARE EVIDENCE_DIR=%s" % ev)


func _write_json(path: String, data: Variant) -> void:
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		print("HH_VF_WARE EVIDENCE_WRITE_FAIL %s" % path)
		return
	f.store_string(JSON.stringify(data, "\t"))
	f.close()

extends SceneTree

const RUN_ID := "VF6WP4-20260903-ASIA-SAIGON-02"
const COMMAND_ID := "cmd.vf6-wp4.survival.2"
const SEED := 7
const MODE := "survival"
const MAP_ID := "rooftops"

const SurvivalCasesScript: GDScript = preload("res://tests/survival_cases.gd")

var _fails: PackedStringArray = PackedStringArray()
var _started_at: String = ""
var _started_unix: float = 0.0


func _initialize() -> void:
	call_deferred("_boot")


func _boot() -> void:
	_started_unix = Time.get_unix_time_from_system()
	_started_at = _iso_local()
	seed(SEED)
	InputActions.install()
	if OS.get_environment("HH_VF_STAGE_STORE") == "":
		OS.set_environment("HH_VF_STAGE_STORE", "progress_vf6wp4_stage.json")
	if OS.get_environment("HH_VF_SURVIVAL_STORE") == "":
		OS.set_environment("HH_VF_SURVIVAL_STORE", "records_vf6wp4.json")
	var _Stage: GDScript = preload("res://src/sim/stage.gd")
	var _Survival: GDScript = preload("res://src/sim/survival.gd")
	_Stage.reset_progress()
	_Survival.reset_records()
	var packed: PackedScene = load("res://scenes/main.tscn") as PackedScene
	var app: App = packed.instantiate() as App
	app.test_driven = true
	root.add_child(app)
	print("HH_VF_SURVIVAL STEP=boot DISPLAY=%s" % DisplayServer.get_name())
	var errors: PackedStringArray = await SurvivalCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	var schema: String = str(SurvivalCasesScript.outcome_schema.get("verdict", "unproven"))
	var load_v: String = str(SurvivalCasesScript.outcome_load.get("verdict", "unproven"))
	var distinct_v: String = str(SurvivalCasesScript.outcome_distinct.get("verdict", "unproven"))
	var score_v: String = str(SurvivalCasesScript.outcome_score.get("verdict", "unproven"))
	var spawn_v: String = str(SurvivalCasesScript.outcome_spawn.get("verdict", "unproven"))
	var pause_v: String = str(SurvivalCasesScript.outcome_pause.get("verdict", "unproven"))
	var restart_v: String = str(SurvivalCasesScript.outcome_restart.get("verdict", "unproven"))
	var live: String = str(SurvivalCasesScript.outcome_live.get("verdict", "unproven"))
	if schema != "pass":
		_fail("SCHEMA structured outcome is %s" % schema)
	if load_v != "pass":
		_fail("LOAD structured outcome is %s" % load_v)
	if distinct_v != "pass":
		_fail("DISTINCT structured outcome is %s" % distinct_v)
	if score_v != "pass":
		_fail("SCORE structured outcome is %s" % score_v)
	if spawn_v != "pass":
		_fail("SPAWN structured outcome is %s" % spawn_v)
	if pause_v != "pass":
		_fail("PAUSE structured outcome is %s" % pause_v)
	if restart_v != "pass":
		_fail("RESTART structured outcome is %s" % restart_v)
	if live != "pass":
		_fail("LIVE structured outcome is %s" % live)
	if SurvivalCasesScript.used_force_kill != 0:
		_fail("official path used force_kill")
	if SurvivalCasesScript.used_teleport != 0:
		_fail("official path used teleport")
	if SurvivalCasesScript.used_step_fixed != 0:
		_fail("official survival used step_fixed")
	if SurvivalCasesScript.used_apply_eval != 0:
		_fail("official survival used apply_eval")
	if SurvivalCasesScript.timeline.is_empty():
		_fail("official survival timeline is empty")
	var ended_at: String = _iso_local()
	print("HH_VF_SURVIVAL run_id=%s" % RUN_ID)
	print("HH_VF_SURVIVAL command_id=%s" % COMMAND_ID)
	print("HH_VF_SURVIVAL DISPLAY=%s" % DisplayServer.get_name())
	print("HH_VF_SURVIVAL SEED=%d MAP=%s MODE=%s NAME=%s" % [SEED, MAP_ID, MODE, Maps.display_name(MAP_ID)])
	print("HH_VF_SURVIVAL STARTED_AT=%s ENDED_AT=%s" % [_started_at, ended_at])
	print(
		"HH_VF_SURVIVAL USED_STEP_FIXED=%d USED_APPLY_FRAMES=%d USED_APPLY_ATTEMPTED=%d USED_APPLY_SUCCEEDED=%d USED_PARSE_INPUT_EVENT=%d USED_ACTION_PRESS=%d USED_FORCE_KILL=%d USED_TELEPORT=%d USED_APPLY_EVAL=%d"
		% [
			SurvivalCasesScript.used_step_fixed,
			SurvivalCasesScript.used_apply_frames,
			SurvivalCasesScript.used_apply_frames_attempted,
			SurvivalCasesScript.used_apply_frames_succeeded,
			SurvivalCasesScript.used_parse_input_event,
			SurvivalCasesScript.used_action_press,
			SurvivalCasesScript.used_force_kill,
			SurvivalCasesScript.used_teleport,
			SurvivalCasesScript.used_apply_eval
		]
	)
	print("HH_VF_SURVIVAL SCHEMA=%s SCHEMA_SOURCE=outcome_schema" % schema)
	print("HH_VF_SURVIVAL LOAD=%s MODE=%s MAP=%s" % [
		load_v,
		str(SurvivalCasesScript.outcome_load.get("mode", "")),
		str(SurvivalCasesScript.outcome_load.get("map_id", "")),
	])
	print("HH_VF_SURVIVAL DISTINCT=%s STAGE_HASH_STABLE=%s" % [
		distinct_v,
		str(SurvivalCasesScript.outcome_distinct.get("stage_hash_before", "")) == str(SurvivalCasesScript.outcome_distinct.get("stage_hash_after", "")),
	])
	print("HH_VF_SURVIVAL SCORE=%s FIRST=%s LAST=%s KILLS=%s WAVE=%s FROM_KILLS=%s FROM_COMBO=%s FROM_WAVE=%s FROM_SURVIVE=%s SOURCE=kill/combo/wave-clear" % [
		score_v,
		str(SurvivalCasesScript.outcome_score.get("first", "")),
		str(SurvivalCasesScript.outcome_score.get("last", "")),
		str(SurvivalCasesScript.outcome_score.get("kills", "")),
		str(SurvivalCasesScript.outcome_score.get("last_wave", "")),
		str(SurvivalCasesScript.outcome_score.get("score_from_kills", "")),
		str(SurvivalCasesScript.outcome_score.get("score_from_combo", "")),
		str(SurvivalCasesScript.outcome_score.get("score_from_wave", "")),
		str(SurvivalCasesScript.outcome_score.get("score_from_survive", "")),
	])
	print("HH_VF_SURVIVAL SPAWN=%s MAX_BOTS=%s CAP=%s REFUSED_CAP=%s DENY=%s DENY_LIVING=%s LIVING_SEEN=%s" % [
		spawn_v,
		str(SurvivalCasesScript.outcome_spawn.get("max_living_bots", "")),
		str(SurvivalCasesScript.outcome_spawn.get("cap_living_bots", "")),
		str(SurvivalCasesScript.outcome_spawn.get("refused_cap", "")),
		str(SurvivalCasesScript.outcome_spawn.get("last_deny_reason", "")),
		str(SurvivalCasesScript.outcome_spawn.get("cap_denied_living", "")),
		str(SurvivalCasesScript.outcome_spawn.get("living_seen", "")),
	])
	print("HH_VF_SURVIVAL PAUSE=%s RESTART=%s LIVE=%s SOAK_SEC=%d ELAPSED=%.2f TIMELINE=%d EVENTS=%d" % [
		pause_v,
		restart_v,
		live,
		SurvivalCasesScript.soak_required,
		SurvivalCasesScript.soak_elapsed,
		SurvivalCasesScript.timeline.size(),
		SurvivalCasesScript.events_all.size(),
	])
	print("HH_VF_SURVIVAL HONESTY BOT_COVERAGE=smoke NOT_AI=1 NOT_Y8_PARITY=1 SURVIVAL_SHIPPED=1 TITLE_SURVIVAL_SHIPPED=1 SURVIVAL_AS_STAGE=0 LOOP=approximation")
	print("HH_VF_SURVIVAL FORCE_KILL_OFFICIAL=0 TELEPORT_OFFICIAL=0")
	var closer: App = app
	if SurvivalCasesScript.live_app != null and is_instance_valid(SurvivalCasesScript.live_app):
		closer = SurvivalCasesScript.live_app
	await _write_evidence(closer, ended_at, schema, load_v, distinct_v, score_v, spawn_v, pause_v, restart_v, live)
	if _fails.is_empty():
		print("PASS: Vault Fighters survival director")
	else:
		print("FAIL: Vault Fighters survival director")
		i = 0
		while i < _fails.size():
			print("  - %s" % String(_fails[i]))
			i += 1
	if is_instance_valid(closer):
		closer.shutdown()
		closer.queue_free()
	await process_frame
	await process_frame
	var code: int = 0 if _fails.is_empty() else 1
	print("HH_VF_SURVIVAL FINISHED=1")
	print("HH_VF_SURVIVAL PROCESS_EXIT=%d" % code)
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


func _write_evidence(
	app: App, ended_at: String, schema: String, load_v: String, distinct_v: String, score_v: String,
	spawn_v: String, pause_v: String, restart_v: String, live: String
) -> void:
	var ev: String = OS.get_environment("HH_VF_EVIDENCE_DIR")
	if ev == "":
		ev = ProjectSettings.globalize_path("res://.evidence/%s" % RUN_ID)
	DirAccess.make_dir_recursive_absolute(ev)
	DirAccess.make_dir_recursive_absolute(ev.path_join("screens"))
	var live_shots: Dictionary = SurvivalCasesScript.still_paths.duplicate()
	if DisplayServer.get_name() != "headless":
		if str(live_shots.get("title", "")) == "":
			_fail("DoD still missing title")
		if str(live_shots.get("fight", "")) == "":
			_fail("DoD still missing fight")
		if str(live_shots.get("lose", "")) == "":
			_fail("DoD still missing lose")
		if str(live_shots.get("restart", "")) == "":
			_fail("DoD still missing restart")
		if str(live_shots.get("title_after", "")) == "":
			_fail("DoD still missing title_after")
	var outcomes: Dictionary = {
		"schema": SurvivalCasesScript.outcome_schema,
		"load": SurvivalCasesScript.outcome_load,
		"distinct": SurvivalCasesScript.outcome_distinct,
		"score": SurvivalCasesScript.outcome_score,
		"spawn": SurvivalCasesScript.outcome_spawn,
		"pause": SurvivalCasesScript.outcome_pause,
		"restart": SurvivalCasesScript.outcome_restart,
		"live": SurvivalCasesScript.outcome_live,
		"apply": {
			"attempted": SurvivalCasesScript.used_apply_frames_attempted,
			"succeeded": SurvivalCasesScript.used_apply_frames_succeeded,
			"used_apply_frames": SurvivalCasesScript.used_apply_frames,
			"used_step_fixed": SurvivalCasesScript.used_step_fixed,
			"used_parse_input_event": SurvivalCasesScript.used_parse_input_event,
			"used_action_press": SurvivalCasesScript.used_action_press,
			"used_force_kill": SurvivalCasesScript.used_force_kill,
			"used_teleport": SurvivalCasesScript.used_teleport,
			"used_apply_eval": SurvivalCasesScript.used_apply_eval,
		},
		"timeline": SurvivalCasesScript.timeline,
		"soak_elapsed": SurvivalCasesScript.soak_elapsed,
		"soak_required": SurvivalCasesScript.soak_required,
	}
	_write_json(ev.path_join("outcomes.json"), outcomes)
	_write_json(ev.path_join("snapshot_start.json"), SurvivalCasesScript.snapshot_start)
	_write_json(ev.path_join("snapshot_end.json"), SurvivalCasesScript.snapshot_end)
	var events_path: String = ev.path_join("events.jsonl")
	var ef: FileAccess = FileAccess.open(events_path, FileAccess.WRITE)
	if ef != null:
		var events: Array = SurvivalCasesScript.events_all
		var ei: int = 0
		while ei < events.size():
			ef.store_line(JSON.stringify(events[ei]))
			ei += 1
		ef.close()
	var vis: Rect2 = Rect2()
	if app != null and app.get_viewport() != null:
		vis = app.get_viewport().get_visible_rect()
	_write_json(ev.path_join("run_partial.json"), {
		"schema": "vault-fighters.vf6-wp4.run.v1",
		"run_id": RUN_ID,
		"command_id": COMMAND_ID,
		"wp": "VF6-WP4",
		"timezone": "Asia/Saigon",
		"started_at": _started_at,
		"ended_at": ended_at,
		"started_unix": _started_unix,
		"ended_unix": Time.get_unix_time_from_system(),
		"display": DisplayServer.get_name(),
		"seed": SEED,
		"map_id": MAP_ID,
		"mode": MODE,
		"tick_hz": 60,
		"epsilon": SimConstants.EPSILON,
		"godot": Engine.get_version_info(),
		"os_name": OS.get_name(),
		"viewport": {"w": vis.size.x, "h": vis.size.y},
		"screens": live_shots,
		"outcomes": {
			"SCHEMA": schema,
			"LOAD": load_v,
			"DISTINCT": distinct_v,
			"SCORE": score_v,
			"SPAWN": spawn_v,
			"PAUSE": pause_v,
			"RESTART": restart_v,
			"LIVE": live,
			"USED_FORCE_KILL": SurvivalCasesScript.used_force_kill,
			"SOAK_SEC": SurvivalCasesScript.soak_required,
			"SOAK_ELAPSED": SurvivalCasesScript.soak_elapsed,
		},
		"fail_count": _fails.size(),
	})
	print("HH_VF_SURVIVAL EVIDENCE_DIR=%s" % ev)


func _write_json(path: String, data: Dictionary) -> void:
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		return
	f.store_string(JSON.stringify(data, "\t"))
	f.close()

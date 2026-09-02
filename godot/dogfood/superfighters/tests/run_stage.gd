extends SceneTree

const RUN_ID := "VF6WP3-20260901-ASIA-SAIGON-02"
const COMMAND_ID := "cmd.vf6-wp3.stage.2"
const SEED := 7
const MODE := "stage"
const MAP_ID := "rooftops"

const StageCasesScript: GDScript = preload("res://tests/stage_cases.gd")

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
		OS.set_environment("HH_VF_STAGE_STORE", "progress_vf6wp3.json")
	var _Stage: GDScript = preload("res://src/sim/stage.gd")
	_Stage.reset_progress()
	var packed: PackedScene = load("res://scenes/main.tscn") as PackedScene
	var app: App = packed.instantiate() as App
	app.test_driven = true
	root.add_child(app)
	print("HH_VF_STAGE STEP=boot DISPLAY=%s" % DisplayServer.get_name())
	var errors: PackedStringArray = await StageCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	var schema: String = str(StageCasesScript.outcome_schema.get("verdict", "unproven"))
	var load_v: String = str(StageCasesScript.outcome_load.get("verdict", "unproven"))
	var advance_v: String = str(StageCasesScript.outcome_advance.get("verdict", "unproven"))
	var loss_v: String = str(StageCasesScript.outcome_loss.get("verdict", "unproven"))
	var hash_v: String = str(StageCasesScript.outcome_hash.get("verdict", "unproven"))
	var continue_v: String = str(StageCasesScript.outcome_continue.get("verdict", "unproven"))
	var reset_v: String = str(StageCasesScript.outcome_reset.get("verdict", "unproven"))
	var live: String = str(StageCasesScript.outcome_live.get("verdict", "unproven"))
	if schema != "pass":
		_fail("SCHEMA structured outcome is %s" % schema)
	if load_v != "pass":
		_fail("LOAD structured outcome is %s" % load_v)
	if advance_v != "pass":
		_fail("ADVANCE structured outcome is %s" % advance_v)
	if loss_v != "pass":
		_fail("LOSS structured outcome is %s" % loss_v)
	if hash_v != "pass":
		_fail("HASH structured outcome is %s" % hash_v)
	if continue_v != "pass":
		_fail("CONTINUE structured outcome is %s" % continue_v)
	if reset_v != "pass":
		_fail("RESET structured outcome is %s" % reset_v)
	if live != "pass":
		_fail("LIVE structured outcome is %s" % live)
	if StageCasesScript.used_force_kill != 0:
		_fail("official path used force_kill")
	if StageCasesScript.used_teleport != 0:
		_fail("official path used teleport")
	if StageCasesScript.used_step_fixed != 0:
		_fail("official stage used step_fixed")
	if StageCasesScript.used_apply_eval != 0:
		_fail("official stage used apply_eval")
	if StageCasesScript.timeline.is_empty():
		_fail("official stage timeline is empty")
	if StageCasesScript.events_all.is_empty():
		_fail("official stage events are empty")
	var ended_at: String = _iso_local()
	print("HH_VF_STAGE run_id=%s" % RUN_ID)
	print("HH_VF_STAGE command_id=%s" % COMMAND_ID)
	print("HH_VF_STAGE DISPLAY=%s" % DisplayServer.get_name())
	print("HH_VF_STAGE SEED=%d MAP=%s MODE=%s NAME=%s" % [SEED, MAP_ID, MODE, Maps.display_name(MAP_ID)])
	print("HH_VF_STAGE STARTED_AT=%s ENDED_AT=%s" % [_started_at, ended_at])
	print(
		"HH_VF_STAGE USED_STEP_FIXED=%d USED_APPLY_FRAMES=%d USED_APPLY_ATTEMPTED=%d USED_APPLY_SUCCEEDED=%d USED_PARSE_INPUT_EVENT=%d USED_ACTION_PRESS=%d USED_FORCE_KILL=%d USED_TELEPORT=%d USED_APPLY_EVAL=%d"
		% [
			StageCasesScript.used_step_fixed,
			StageCasesScript.used_apply_frames,
			StageCasesScript.used_apply_frames_attempted,
			StageCasesScript.used_apply_frames_succeeded,
			StageCasesScript.used_parse_input_event,
			StageCasesScript.used_action_press,
			StageCasesScript.used_force_kill,
			StageCasesScript.used_teleport,
			StageCasesScript.used_apply_eval
		]
	)
	print("HH_VF_STAGE SCHEMA=%s SCHEMA_SOURCE=outcome_schema" % schema)
	print("HH_VF_STAGE LOAD=%s LOAD_SOURCE=outcome_load" % load_v)
	print("HH_VF_STAGE ADVANCE=%s AFTER0=%s AFTER1=%s AFTER2=%s" % [
		advance_v,
		str(StageCasesScript.outcome_advance.get("after_win0_map", "")),
		str(StageCasesScript.outcome_advance.get("after_win1_map", "")),
		str(StageCasesScript.outcome_advance.get("after_win2_map", "")),
	])
	print("HH_VF_STAGE LOSS=%s STAYED=%s CAUSE=%s BOT_HP=%s PIT=%d" % [
		loss_v,
		str(StageCasesScript.outcome_loss.get("stayed_map", "")),
		str(StageCasesScript.outcome_loss.get("death_cause", "")),
		str(StageCasesScript.outcome_loss.get("bot_hp", "")),
		int(StageCasesScript.outcome_loss.get("pit_loss", 1)),
	])
	print("HH_VF_STAGE HASH=%s H0=%s H1=%s" % [
		hash_v,
		str(StageCasesScript.outcome_hash.get("hash_win0", "")),
		str(StageCasesScript.outcome_hash.get("hash_win1", "")),
	])
	print("HH_VF_STAGE CONTINUE=%s COLD=%s RESET=%s LIVE=%s TIMELINE=%d EVENTS=%d" % [
		continue_v,
		str(StageCasesScript.outcome_continue.get("cold", false)),
		reset_v,
		live,
		StageCasesScript.timeline.size(),
		StageCasesScript.events_all.size(),
	])
	print("HH_VF_STAGE HONESTY BOT_COVERAGE=smoke NOT_AI=1 NOT_Y8_PARITY=1 SURVIVAL_SHIPPED=0 TIER=approximation")
	print("HH_VF_STAGE FORCE_KILL_OFFICIAL=0 TELEPORT_OFFICIAL=0")
	var closer: App = app
	if StageCasesScript.live_app != null and is_instance_valid(StageCasesScript.live_app):
		closer = StageCasesScript.live_app
	await _write_evidence(closer, ended_at, schema, load_v, advance_v, loss_v, hash_v, continue_v, reset_v, live)
	if _fails.is_empty():
		print("PASS: Vault Fighters stage progression")
	else:
		print("FAIL: Vault Fighters stage progression")
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
	print("HH_VF_STAGE FINISHED=1")
	print("HH_VF_STAGE PROCESS_EXIT=%d" % code)
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
	app: App, ended_at: String, schema: String, load_v: String, advance_v: String, loss_v: String,
	hash_v: String, continue_v: String, reset_v: String, live: String
) -> void:
	var ev: String = OS.get_environment("HH_VF_EVIDENCE_DIR")
	if ev == "":
		ev = ProjectSettings.globalize_path("res://.evidence/%s" % RUN_ID)
	DirAccess.make_dir_recursive_absolute(ev)
	DirAccess.make_dir_recursive_absolute(ev.path_join("screens"))
	var live_shots: Dictionary = StageCasesScript.still_paths.duplicate()
	if DisplayServer.get_name() != "headless":
		if str(live_shots.get("title", "")) == "":
			_fail("DoD still missing title")
		if str(live_shots.get("fight", "")) == "":
			_fail("DoD still missing fight")
		if str(live_shots.get("advance", "")) == "":
			_fail("DoD still missing advance")
		if str(live_shots.get("lose", "")) == "":
			_fail("DoD still missing lose")
		if str(live_shots.get("reset", "")) == "":
			_fail("DoD still missing reset")
		if str(live_shots.get("title_after", "")) == "":
			_fail("DoD still missing title_after")
	var outcomes: Dictionary = {
		"schema": StageCasesScript.outcome_schema,
		"load": StageCasesScript.outcome_load,
		"advance": StageCasesScript.outcome_advance,
		"loss": StageCasesScript.outcome_loss,
		"hash": StageCasesScript.outcome_hash,
		"continue": StageCasesScript.outcome_continue,
		"reset": StageCasesScript.outcome_reset,
		"live": StageCasesScript.outcome_live,
		"apply": {
			"attempted": StageCasesScript.used_apply_frames_attempted,
			"succeeded": StageCasesScript.used_apply_frames_succeeded,
			"used_apply_frames": StageCasesScript.used_apply_frames,
			"used_step_fixed": StageCasesScript.used_step_fixed,
			"used_parse_input_event": StageCasesScript.used_parse_input_event,
			"used_action_press": StageCasesScript.used_action_press,
			"used_force_kill": StageCasesScript.used_force_kill,
			"used_teleport": StageCasesScript.used_teleport,
			"used_apply_eval": StageCasesScript.used_apply_eval,
		},
		"timeline": StageCasesScript.timeline,
	}
	_write_json(ev.path_join("outcomes.json"), outcomes)
	_write_json(ev.path_join("snapshot_start.json"), StageCasesScript.snapshot_start)
	_write_json(ev.path_join("snapshot_end.json"), StageCasesScript.snapshot_end)
	var events_path: String = ev.path_join("events.jsonl")
	var ef: FileAccess = FileAccess.open(events_path, FileAccess.WRITE)
	if ef != null:
		var events: Array = StageCasesScript.events_all
		var ei: int = 0
		while ei < events.size():
			ef.store_line(JSON.stringify(events[ei]))
			ei += 1
		ef.close()
	var vis: Rect2 = Rect2()
	if app != null and app.get_viewport() != null:
		vis = app.get_viewport().get_visible_rect()
	_write_json(ev.path_join("run_partial.json"), {
		"schema": "vault-fighters.vf6-wp3.run.v1",
		"run_id": RUN_ID,
		"command_id": COMMAND_ID,
		"wp": "VF6-WP3",
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
			"ADVANCE": advance_v,
			"LOSS": loss_v,
			"HASH": hash_v,
			"CONTINUE": continue_v,
			"RESET": reset_v,
			"LIVE": live,
			"USED_FORCE_KILL": StageCasesScript.used_force_kill,
		},
		"fail_count": _fails.size(),
	})
	print("HH_VF_STAGE EVIDENCE_DIR=%s" % ev)


func _write_json(path: String, data: Dictionary) -> void:
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		return
	f.store_string(JSON.stringify(data, "\t"))
	f.close()

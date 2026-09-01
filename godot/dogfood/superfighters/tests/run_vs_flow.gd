extends SceneTree

const RUN_ID := "VF6WP2-20260901-ASIA-SAIGON-03"
const COMMAND_ID := "cmd.vf6-wp2.vs-flow.3"
const SEED := 7
const MODE := "vs2"
const MAP_ID := "fx_melee_close"

const VsFlowCasesScript: GDScript = preload("res://tests/vs_flow_cases.gd")

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
	var packed: PackedScene = load("res://scenes/main.tscn") as PackedScene
	var app: App = packed.instantiate() as App
	app.test_driven = true
	root.add_child(app)
	print("HH_VF_VS2 STEP=boot DISPLAY=%s" % DisplayServer.get_name())
	var errors: PackedStringArray = await VsFlowCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	var schema: String = str(VsFlowCasesScript.outcome_schema.get("verdict", "unproven"))
	var first_v: String = str(VsFlowCasesScript.outcome_first.get("verdict", "unproven"))
	var ready_v: String = str(VsFlowCasesScript.outcome_ready.get("verdict", "unproven"))
	var leak_v: String = str(VsFlowCasesScript.outcome_leak.get("verdict", "unproven"))
	var play_v: String = str(VsFlowCasesScript.outcome_play.get("verdict", "unproven"))
	var rematch_v: String = str(VsFlowCasesScript.outcome_rematch.get("verdict", "unproven"))
	var overlay_v: String = str(VsFlowCasesScript.outcome_overlay.get("verdict", "unproven"))
	var feedback_v: String = str(VsFlowCasesScript.outcome_feedback.get("verdict", "unproven"))
	var live: String = str(VsFlowCasesScript.outcome_live.get("verdict", "unproven"))
	if schema != "pass":
		_fail("SCHEMA structured outcome is %s" % schema)
	if first_v != "pass":
		_fail("FIRST structured outcome is %s" % first_v)
	if ready_v != "pass":
		_fail("READY structured outcome is %s" % ready_v)
	if leak_v != "pass":
		_fail("LEAK structured outcome is %s" % leak_v)
	if play_v != "pass":
		_fail("PLAY structured outcome is %s" % play_v)
	if rematch_v != "pass":
		_fail("REMATCH structured outcome is %s" % rematch_v)
	if overlay_v != "pass":
		_fail("OVERLAY structured outcome is %s" % overlay_v)
	if feedback_v != "pass":
		_fail("FEEDBACK structured outcome is %s" % feedback_v)
	if live != "pass":
		_fail("LIVE structured outcome is %s" % live)
	if VsFlowCasesScript.used_force_kill != 0:
		_fail("official path used force_kill")
	if VsFlowCasesScript.used_teleport != 0:
		_fail("official path used teleport")
	if VsFlowCasesScript.used_step_fixed != 0:
		_fail("official vs flow used step_fixed")
	var ended_at: String = _iso_local()
	print("HH_VF_VS2 run_id=%s" % RUN_ID)
	print("HH_VF_VS2 command_id=%s" % COMMAND_ID)
	print("HH_VF_VS2 DISPLAY=%s" % DisplayServer.get_name())
	print("HH_VF_VS2 SEED=%d MAP=%s MODE=%s NAME=%s" % [SEED, MAP_ID, MODE, Maps.display_name(MAP_ID)])
	print("HH_VF_VS2 STARTED_AT=%s ENDED_AT=%s" % [_started_at, ended_at])
	print(
		"HH_VF_VS2 USED_STEP_FIXED=%d USED_APPLY_FRAMES=%d USED_APPLY_ATTEMPTED=%d USED_APPLY_SUCCEEDED=%d USED_PARSE_INPUT_EVENT=%d USED_ACTION_PRESS=%d USED_FORCE_KILL=%d USED_TELEPORT=%d"
		% [
			VsFlowCasesScript.used_step_fixed,
			VsFlowCasesScript.used_apply_frames,
			VsFlowCasesScript.used_apply_frames_attempted,
			VsFlowCasesScript.used_apply_frames_succeeded,
			VsFlowCasesScript.used_parse_input_event,
			VsFlowCasesScript.used_action_press,
			VsFlowCasesScript.used_force_kill,
			VsFlowCasesScript.used_teleport
		]
	)
	print("HH_VF_VS2 SCHEMA=%s SCHEMA_SOURCE=outcome_schema" % schema)
	print("HH_VF_VS2 FIRST=%s FIRST_SOURCE=outcome_first VS1_ACTIONS=%d VS1_SEC=%s VS2_ACTIONS=%d VS2_SEC=%s" % [
		first_v,
		int(VsFlowCasesScript.outcome_first.get("vs1_actions", 99)),
		str(VsFlowCasesScript.outcome_first.get("vs1_seconds", 99.0)),
		int(VsFlowCasesScript.outcome_first.get("vs2_actions", 99)),
		str(VsFlowCasesScript.outcome_first.get("vs2_seconds", 99.0)),
	])
	print("HH_VF_VS2 READY=%s READY_SOURCE=outcome_ready" % ready_v)
	print("HH_VF_VS2 LEAK=%s LEAK_SOURCE=outcome_leak" % leak_v)
	print("HH_VF_VS2 PLAY=%s PLAY_SOURCE=outcome_play OUTCOME=%s MAP=%s DEATH_CAUSE=%s P1_MOVED=%s P2_MOVED=%s P1_ATTACKED=%s P2_ATTACKED=%s HIT=%s PIT_FALLBACK=%s" % [
		play_v,
		str(VsFlowCasesScript.outcome_play.get("outcome", "")),
		str(VsFlowCasesScript.outcome_play.get("map_id", "")),
		str(VsFlowCasesScript.outcome_play.get("death_cause", "")),
		str(VsFlowCasesScript.outcome_play.get("p1_moved", false)),
		str(VsFlowCasesScript.outcome_play.get("p2_moved", false)),
		str(VsFlowCasesScript.outcome_play.get("p1_attacked", false)),
		str(VsFlowCasesScript.outcome_play.get("p2_attacked", false)),
		str(VsFlowCasesScript.outcome_play.get("hit_landed", false)),
		str(VsFlowCasesScript.outcome_play.get("used_pit_fallback", 1)),
	])
	print("HH_VF_VS2 REMATCH=%s REMATCH_SOURCE=outcome_rematch ACTIONS=%d SEC=%s" % [
		rematch_v,
		int(VsFlowCasesScript.outcome_rematch.get("actions", 99)),
		str(VsFlowCasesScript.outcome_rematch.get("seconds", 99.0)),
	])
	print("HH_VF_VS2 OVERLAY=%s OVERLAY_SOURCE=outcome_overlay" % overlay_v)
	print("HH_VF_VS2 FEEDBACK=%s FEEDBACK_SOURCE=outcome_feedback" % feedback_v)
	print("HH_VF_VS2 LIVE=%s LIVE_SOURCE=outcome_live" % live)
	print("HH_VF_VS2 HONESTY P2_COVERAGE=live_local BOT_COVERAGE=smoke NOT_AI=1 NOT_Y8_PARITY=1 SURVIVAL_SHIPPED=0 STAGE_LIFECYCLE=0")
	print("HH_VF_VS2 FORCE_KILL_OFFICIAL=0 TELEPORT_OFFICIAL=0")
	await _write_evidence(app, ended_at, schema, first_v, ready_v, leak_v, play_v, rematch_v, overlay_v, feedback_v, live)
	if _fails.is_empty():
		print("PASS: Vault Fighters vs production flow")
	else:
		print("FAIL: Vault Fighters vs production flow")
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
	print("HH_VF_VS2 FINISHED=1")
	print("HH_VF_VS2 PROCESS_EXIT=%d" % code)
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
	app: App, ended_at: String, schema: String, first_v: String, ready_v: String, leak_v: String,
	play_v: String, rematch_v: String, overlay_v: String, feedback_v: String, live: String
) -> void:
	var ev: String = OS.get_environment("HH_VF_EVIDENCE_DIR")
	if ev == "":
		ev = ProjectSettings.globalize_path("res://.evidence/%s" % RUN_ID)
	DirAccess.make_dir_recursive_absolute(ev)
	DirAccess.make_dir_recursive_absolute(ev.path_join("screens"))
	var live_shots: Dictionary = VsFlowCasesScript.still_paths.duplicate()
	if DisplayServer.get_name() != "headless":
		if str(live_shots.get("title", "")) == "":
			_fail("DoD still missing title")
		if str(live_shots.get("lobby", "")) == "":
			_fail("DoD still missing lobby")
		if str(live_shots.get("fight", "")) == "":
			_fail("DoD still missing fight")
		if str(live_shots.get("result", "")) == "":
			_fail("DoD still missing result")
		if str(live_shots.get("rematch", "")) == "":
			_fail("DoD still missing rematch")
		if str(live_shots.get("title_after", "")) == "":
			_fail("DoD still missing title_after")
	var outcomes: Dictionary = {
		"schema": VsFlowCasesScript.outcome_schema,
		"first": VsFlowCasesScript.outcome_first,
		"ready": VsFlowCasesScript.outcome_ready,
		"leak": VsFlowCasesScript.outcome_leak,
		"play": VsFlowCasesScript.outcome_play,
		"rematch": VsFlowCasesScript.outcome_rematch,
		"overlay": VsFlowCasesScript.outcome_overlay,
		"feedback": VsFlowCasesScript.outcome_feedback,
		"live": VsFlowCasesScript.outcome_live,
		"apply": {
			"attempted": VsFlowCasesScript.used_apply_frames_attempted,
			"succeeded": VsFlowCasesScript.used_apply_frames_succeeded,
			"used_apply_frames": VsFlowCasesScript.used_apply_frames,
			"used_step_fixed": VsFlowCasesScript.used_step_fixed,
			"used_parse_input_event": VsFlowCasesScript.used_parse_input_event,
			"used_action_press": VsFlowCasesScript.used_action_press,
			"used_force_kill": VsFlowCasesScript.used_force_kill,
			"used_teleport": VsFlowCasesScript.used_teleport,
		},
		"timeline": VsFlowCasesScript.timeline,
	}
	_write_json(ev.path_join("outcomes.json"), outcomes)
	_write_json(ev.path_join("snapshot_start.json"), VsFlowCasesScript.snapshot_start)
	_write_json(ev.path_join("snapshot_end.json"), VsFlowCasesScript.snapshot_end)
	var events_path: String = ev.path_join("events.jsonl")
	var ef: FileAccess = FileAccess.open(events_path, FileAccess.WRITE)
	if ef != null:
		var events: Array = VsFlowCasesScript.events_all
		var ei: int = 0
		while ei < events.size():
			ef.store_line(JSON.stringify(events[ei]))
			ei += 1
		ef.close()
	var vis: Rect2 = Rect2()
	if app != null and app.get_viewport() != null:
		vis = app.get_viewport().get_visible_rect()
	_write_json(ev.path_join("run_partial.json"), {
		"schema": "vault-fighters.vf6-wp2.run.v1",
		"run_id": RUN_ID,
		"command_id": COMMAND_ID,
		"wp": "VF6-WP2",
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
			"FIRST": first_v,
			"READY": ready_v,
			"LEAK": leak_v,
			"PLAY": play_v,
			"REMATCH": rematch_v,
			"OVERLAY": overlay_v,
			"FEEDBACK": feedback_v,
			"LIVE": live,
			"USED_FORCE_KILL": VsFlowCasesScript.used_force_kill,
		},
		"fail_count": _fails.size(),
	})
	print("HH_VF_VS2 EVIDENCE_DIR=%s" % ev)


func _write_json(path: String, data: Dictionary) -> void:
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		return
	f.store_string(JSON.stringify(data, "\t"))
	f.close()

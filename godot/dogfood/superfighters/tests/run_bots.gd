extends SceneTree

const RUN_ID := "VF6WP5-20260903-ASIA-SAIGON-03"
const COMMAND_ID := "cmd.vf6-wp5.bots.3"
const SEED := 7
const MODE := "vs1"
const MAP_ID := "rooftops"

const BotCasesScript: GDScript = preload("res://tests/bot_cases.gd")

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
	OS.set_environment("HH_VF_RUN_ID", RUN_ID)
	var packed: PackedScene = load("res://scenes/main.tscn") as PackedScene
	var app: App = packed.instantiate() as App
	app.test_driven = true
	root.add_child(app)
	print("HH_VF_BOTS STEP=boot DISPLAY=%s" % DisplayServer.get_name())
	var errors: PackedStringArray = await BotCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	var schema: String = str(BotCasesScript.outcome_schema.get("verdict", "unproven"))
	var maps_v: String = str(BotCasesScript.outcome_maps.get("verdict", "unproven"))
	var weapons: String = str(BotCasesScript.outcome_weapons.get("verdict", "unproven"))
	var finish: String = str(BotCasesScript.outcome_finish.get("verdict", "unproven"))
	var greedy: String = str(BotCasesScript.outcome_greedy.get("verdict", "unproven"))
	var recover: String = str(BotCasesScript.outcome_recover.get("verdict", "unproven"))
	var diff: String = str(BotCasesScript.outcome_diff.get("verdict", "unproven"))
	var bound: String = str(BotCasesScript.outcome_bound.get("verdict", "unproven"))
	var live: String = str(BotCasesScript.outcome_live.get("verdict", "unproven"))
	if schema != "pass":
		_fail("SCHEMA structured outcome is %s" % schema)
	if maps_v != "pass":
		_fail("MAPS structured outcome is %s" % maps_v)
	if weapons != "pass":
		_fail("WEAPONS structured outcome is %s" % weapons)
	if finish != "pass":
		_fail("FINISH structured outcome is %s" % finish)
	if greedy != "pass":
		_fail("GREEDY structured outcome is %s" % greedy)
	if recover != "pass":
		_fail("RECOVER structured outcome is %s" % recover)
	if diff != "pass":
		_fail("DIFF structured outcome is %s" % diff)
	if bound != "pass":
		_fail("BOUND structured outcome is %s" % bound)
	if live != "pass":
		_fail("LIVE structured outcome is %s" % live)
	if BotCasesScript.used_force_kill != 0:
		_fail("official path used force_kill")
	if BotCasesScript.used_teleport != 0:
		_fail("official path used teleport")
	if BotCasesScript.used_apply_eval != 0:
		_fail("official bots used apply_eval")
	if BotCasesScript.timeline.is_empty():
		_fail("official bots timeline is empty")
	var ended_at: String = _iso_local()
	print("HH_VF_BOTS run_id=%s" % RUN_ID)
	print("HH_VF_BOTS command_id=%s" % COMMAND_ID)
	print("HH_VF_BOTS DISPLAY=%s" % DisplayServer.get_name())
	print("HH_VF_BOTS SEED=%d MAP=%s MODE=%s NAME=%s" % [SEED, MAP_ID, MODE, Maps.display_name(MAP_ID)])
	print("HH_VF_BOTS STARTED_AT=%s ENDED_AT=%s" % [_started_at, ended_at])
	print(
		"HH_VF_BOTS USED_STEP_FIXED=%d USED_APPLY_FRAMES=%d USED_APPLY_ATTEMPTED=%d USED_APPLY_SUCCEEDED=%d USED_PARSE_INPUT_EVENT=%d USED_ACTION_PRESS=%d USED_FORCE_KILL=%d USED_TELEPORT=%d USED_APPLY_EVAL=%d"
		% [
			BotCasesScript.used_step_fixed,
			BotCasesScript.used_apply_frames,
			BotCasesScript.used_apply_frames_attempted,
			BotCasesScript.used_apply_frames_succeeded,
			BotCasesScript.used_parse_input_event,
			BotCasesScript.used_action_press,
			BotCasesScript.used_force_kill,
			BotCasesScript.used_teleport,
			BotCasesScript.used_apply_eval
		]
	)
	print("HH_VF_BOTS SCHEMA=%s SCHEMA_SOURCE=outcome_schema" % schema)
	print("HH_VF_BOTS MAPS=%s WEAPONS=%s FINISH=%s GREEDY=%s RECOVER=%s DIFF=%s BOUND=%s LIVE=%s" % [
		maps_v, weapons, finish, greedy, recover, diff, bound, live
	])
	_print_map_table()
	print(
		"HH_VF_BOTS HONESTY BOT_COVERAGE=planner NOT_AI=0 NOT_Y8_PARITY=1 PLANNER_CLASS=assumption DIFF=tuning NO_TELEPORT=1 NO_PERFECT_AIM=1 NO_HIDDEN_STATE=1"
	)
	print("HH_VF_BOTS FORCE_KILL_OFFICIAL=0 TELEPORT_OFFICIAL=0")
	var closer: App = app
	if BotCasesScript.live_app != null and is_instance_valid(BotCasesScript.live_app):
		closer = BotCasesScript.live_app
	await _write_evidence(closer, ended_at, schema, maps_v, weapons, finish, greedy, recover, diff, bound, live)
	if _fails.is_empty():
		print("PASS: Vault Fighters bot planner")
	else:
		print("FAIL: Vault Fighters bot planner")
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
	print("HH_VF_BOTS FINISHED=1")
	print("HH_VF_BOTS PROCESS_EXIT=%d" % code)
	quit(code)


func _print_map_table() -> void:
	var ids: PackedStringArray = Maps.vs_ids()
	var i: int = 0
	while i < ids.size():
		var mid: String = String(ids[i])
		var row: Dictionary = {}
		if BotCasesScript.map_rows.has(mid):
			row = BotCasesScript.map_rows[mid] as Dictionary
		print(
			"HH_VF_BOTS MAP_ROW id=%s name=%s reach=%s pit=%s aim=%s combat=%s moved=%.1f toward=%.1f goal_dist=%.1f pit_blocks=%s pit_reroutes=%s gun=%s melee=%s aim_err=%.1f shot_off=%.1f cause=%s"
			% [
				mid,
				str(row.get("display", Maps.display_name(mid))),
				str(row.get("reach_ok", false)),
				str(row.get("pit_ok", false)),
				str(row.get("aim_ok", false)),
				str(row.get("combat_ok", false)),
				float(row.get("moved", 0.0)),
				float(row.get("toward", 0.0)),
				float(row.get("goal_dist", 0.0)),
				str(row.get("pit_blocks", "")),
				str(row.get("pit_reroutes", "")),
				str(row.get("gun_used", "")),
				str(row.get("melee_used", "")),
				float(row.get("aim_error_deg", 0.0)),
				float(row.get("last_shot_off_deg", 0.0)),
				str(row.get("death_cause", "")),
			]
		)
		i += 1


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
	app: App, ended_at: String, schema: String, maps_v: String, weapons: String, finish: String,
	greedy: String, recover: String, diff: String, bound: String, live: String
) -> void:
	var ev: String = OS.get_environment("HH_VF_EVIDENCE_DIR")
	if ev == "":
		ev = ProjectSettings.globalize_path("res://.evidence/%s" % RUN_ID)
	DirAccess.make_dir_recursive_absolute(ev)
	DirAccess.make_dir_recursive_absolute(ev.path_join("screens"))
	var live_shots: Dictionary = BotCasesScript.still_paths.duplicate()
	if DisplayServer.get_name() != "headless":
		if str(live_shots.get("title", "")) == "":
			_fail("DoD still missing title")
		if str(live_shots.get("fight", "")) == "":
			_fail("DoD still missing fight")
	var outcomes: Dictionary = {
		"schema": BotCasesScript.outcome_schema,
		"maps": BotCasesScript.outcome_maps,
		"weapons": BotCasesScript.outcome_weapons,
		"finish": BotCasesScript.outcome_finish,
		"greedy": BotCasesScript.outcome_greedy,
		"recover": BotCasesScript.outcome_recover,
		"diff": BotCasesScript.outcome_diff,
		"bound": BotCasesScript.outcome_bound,
		"live": BotCasesScript.outcome_live,
		"apply": {
			"attempted": BotCasesScript.used_apply_frames_attempted,
			"succeeded": BotCasesScript.used_apply_frames_succeeded,
			"used_apply_frames": BotCasesScript.used_apply_frames,
			"used_step_fixed": BotCasesScript.used_step_fixed,
			"used_force_kill": BotCasesScript.used_force_kill,
			"used_teleport": BotCasesScript.used_teleport,
			"used_apply_eval": BotCasesScript.used_apply_eval,
		},
		"timeline": BotCasesScript.timeline,
		"map_rows": BotCasesScript.map_rows,
	}
	_write_json(ev.path_join("outcomes.json"), outcomes)
	_write_json(ev.path_join("snapshot_start.json"), BotCasesScript.snapshot_start)
	_write_json(ev.path_join("snapshot_end.json"), BotCasesScript.snapshot_end)
	var events_path: String = ev.path_join("events.jsonl")
	var ef: FileAccess = FileAccess.open(events_path, FileAccess.WRITE)
	if ef != null:
		var events: Array = BotCasesScript.events_all
		var ei: int = 0
		while ei < events.size():
			ef.store_line(JSON.stringify(events[ei]))
			ei += 1
		ef.close()
	var vis: Rect2 = Rect2()
	if app != null and app.get_viewport() != null:
		vis = app.get_viewport().get_visible_rect()
	_write_json(ev.path_join("run_partial.json"), {
		"schema": "vault-fighters.vf6-wp5.run.v1",
		"run_id": RUN_ID,
		"command_id": COMMAND_ID,
		"wp": "VF6-WP5",
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
			"MAPS": maps_v,
			"WEAPONS": weapons,
			"FINISH": finish,
			"GREEDY": greedy,
			"RECOVER": recover,
			"DIFF": diff,
			"BOUND": bound,
			"LIVE": live,
			"USED_FORCE_KILL": BotCasesScript.used_force_kill,
			"NOT_AI": 0,
			"BOT_COVERAGE": "planner",
			"NOT_Y8_PARITY": 1,
		},
		"fail_count": _fails.size(),
	})
	print("HH_VF_BOTS EVIDENCE_DIR=%s" % ev)


func _write_json(path: String, data: Dictionary) -> void:
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		return
	f.store_string(JSON.stringify(data, "\t"))
	f.close()

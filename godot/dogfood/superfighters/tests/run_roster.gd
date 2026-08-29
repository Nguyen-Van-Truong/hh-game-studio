extends SceneTree

const RUN_ID := "VF3WP5-20260829-ASIA-SAIGON-02"
const COMMAND_ID := "cmd.vf3-wp5.roster.2"
const SEED := 7
const MODE := "vs2"
const MAP_ID := "fx_roster_open"

const RosterCasesScript: GDScript = preload("res://tests/roster_cases.gd")

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
	var errors: PackedStringArray = await RosterCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	var schema: String = str(RosterCasesScript.outcome_schema.get("verdict", "unproven"))
	var spawn: String = str(RosterCasesScript.outcome_spawn.get("verdict", "unproven"))
	var equip: String = str(RosterCasesScript.outcome_equip.get("verdict", "unproven"))
	var attack: String = str(RosterCasesScript.outcome_attack.get("verdict", "unproven"))
	var dropv: String = str(RosterCasesScript.outcome_drop.get("verdict", "unproven"))
	var ser: String = str(RosterCasesScript.outcome_serialize.get("verdict", "unproven"))
	var keep: String = str(RosterCasesScript.outcome_keep.get("verdict", "unproven"))
	var ammo: String = str(RosterCasesScript.outcome_ammo.get("verdict", "unproven"))
	var data: String = str(RosterCasesScript.outcome_data.get("verdict", "unproven"))
	var live: String = str(RosterCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(RosterCasesScript.outcome_replay.get("verdict", "unproven"))
	if schema != "pass":
		_fail("SCHEMA structured outcome is %s" % schema)
	if spawn != "pass":
		_fail("SPAWN structured outcome is %s" % spawn)
	if equip != "pass":
		_fail("EQUIP structured outcome is %s" % equip)
	if attack != "pass":
		_fail("ATTACK structured outcome is %s" % attack)
	if dropv != "pass":
		_fail("DROP structured outcome is %s" % dropv)
	if ser != "pass":
		_fail("SERIALIZE structured outcome is %s" % ser)
	if keep != "pass":
		_fail("KEEP structured outcome is %s" % keep)
	if ammo != "pass":
		_fail("AMMO structured outcome is %s" % ammo)
	if data != "pass":
		_fail("DATA structured outcome is %s" % data)
	if live != "pass":
		_fail("LIVE structured outcome is %s" % live)
	if replay != "match":
		_fail("REPLAY structured outcome is %s" % replay)
	var ended_at: String = _iso_local()
	print("HH_VF_ROSTER run_id=%s" % RUN_ID)
	print("HH_VF_ROSTER command_id=%s" % COMMAND_ID)
	print("HH_VF_ROSTER DISPLAY=%s" % DisplayServer.get_name())
	print("HH_VF_ROSTER SEED=%d MAP=%s MODE=%s" % [SEED, MAP_ID, MODE])
	print("HH_VF_ROSTER STARTED_AT=%s ENDED_AT=%s" % [_started_at, ended_at])
	print(
		"HH_VF_ROSTER USED_STEP_FIXED=%d USED_APPLY_FRAMES=%d USED_APPLY_ATTEMPTED=%d USED_APPLY_SUCCEEDED=%d USED_PARSE_INPUT_EVENT=%d USED_ACTION_PRESS=%d"
		% [
			RosterCasesScript.used_step_fixed,
			RosterCasesScript.used_apply_frames,
			RosterCasesScript.used_apply_frames_attempted,
			RosterCasesScript.used_apply_frames_succeeded,
			RosterCasesScript.used_parse_input_event,
			RosterCasesScript.used_action_press
		]
	)
	print("HH_VF_ROSTER SCHEMA=%s SCHEMA_SOURCE=outcome_schema" % schema)
	print("HH_VF_ROSTER SPAWN=%s SPAWN_SOURCE=outcome_spawn" % spawn)
	print("HH_VF_ROSTER EQUIP=%s EQUIP_SOURCE=outcome_equip" % equip)
	print("HH_VF_ROSTER ATTACK=%s ATTACK_SOURCE=outcome_attack" % attack)
	print("HH_VF_ROSTER DROP=%s DROP_SOURCE=outcome_drop" % dropv)
	print("HH_VF_ROSTER SERIALIZE=%s SERIALIZE_SOURCE=outcome_serialize" % ser)
	print("HH_VF_ROSTER KEEP=%s KEEP_SOURCE=outcome_keep" % keep)
	print("HH_VF_ROSTER AMMO=%s AMMO_SOURCE=outcome_ammo" % ammo)
	print("HH_VF_ROSTER DATA=%s DATA_SOURCE=outcome_data" % data)
	print("HH_VF_ROSTER LIVE=%s LIVE_SOURCE=outcome_live" % live)
	print("HH_VF_ROSTER REPLAY=%s REPLAY_SOURCE=outcome_replay" % replay)
	print("HH_VF_ROSTER SLOTS=assumption ROSTER=assumption PICK=assumption KEEP_GUN=assumption AMMO_RELOAD=assumption HOLD_AIM=assumption ROLL_DIVE=unavailable CLOCK=RL-SIM-FIXED-60")
	await process_frame
	await process_frame
	_write_evidence(app, ended_at)
	if _fails.is_empty():
		print("PASS: Vault Fighters weapon roster")
	else:
		print("FAIL: Vault Fighters weapon roster")
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


func _write_evidence(app: App, ended_at: String) -> void:
	var ev: String = OS.get_environment("HH_VF_EVIDENCE_DIR")
	if ev == "":
		ev = ProjectSettings.globalize_path("res://.evidence/%s" % RUN_ID)
	DirAccess.make_dir_recursive_absolute(ev)
	DirAccess.make_dir_recursive_absolute(ev.path_join("screens"))
	var outcomes: Dictionary = {
		"schema": RosterCasesScript.outcome_schema,
		"spawn": RosterCasesScript.outcome_spawn,
		"equip": RosterCasesScript.outcome_equip,
		"attack": RosterCasesScript.outcome_attack,
		"drop": RosterCasesScript.outcome_drop,
		"serialize": RosterCasesScript.outcome_serialize,
		"keep": RosterCasesScript.outcome_keep,
		"ammo": RosterCasesScript.outcome_ammo,
		"data": RosterCasesScript.outcome_data,
		"live": RosterCasesScript.outcome_live,
		"replay": RosterCasesScript.outcome_replay,
		"apply": {
			"attempted": RosterCasesScript.used_apply_frames_attempted,
			"succeeded": RosterCasesScript.used_apply_frames_succeeded,
			"used_apply_frames": RosterCasesScript.used_apply_frames,
			"used_step_fixed": RosterCasesScript.used_step_fixed,
			"used_parse_input_event": RosterCasesScript.used_parse_input_event,
			"used_action_press": RosterCasesScript.used_action_press,
		},
	}
	_write_json(ev.path_join("outcomes.json"), outcomes)
	_write_json(ev.path_join("snapshot_start.json"), RosterCasesScript.snapshot_start)
	_write_json(ev.path_join("snapshot_end.json"), RosterCasesScript.snapshot_end)
	_write_json(ev.path_join("state_hashes.json"), {
		"replay": RosterCasesScript.outcome_replay,
		"seed": SEED,
		"map_id": MAP_ID,
		"mode": MODE,
	})
	var events_path: String = ev.path_join("events.jsonl")
	var ef: FileAccess = FileAccess.open(events_path, FileAccess.WRITE)
	if ef != null:
		var events: Array = RosterCasesScript.events_all
		if events.is_empty():
			events = RosterCasesScript.events_end
		var ei: int = 0
		while ei < events.size():
			ef.store_line(JSON.stringify(events[ei]))
			ei += 1
		ef.close()
	var display_name: String = DisplayServer.get_name()
	var vis: Rect2 = Rect2()
	if app != null and app.get_viewport() != null:
		vis = app.get_viewport().get_visible_rect()
		if display_name != "headless":
			var tex: ViewportTexture = app.get_viewport().get_texture()
			if tex == null:
				print("HH_VF_ROSTER SCREENSHOT_END missing viewport texture")
			else:
				var img: Image = tex.get_image()
				if img == null:
					print("HH_VF_ROSTER SCREENSHOT_END get_image null")
				else:
					var shot: String = ev.path_join("screens").path_join("roster_%dx%d.png" % [
						int(vis.size.x), int(vis.size.y)
					])
					var err: Error = img.save_png(shot)
					print("HH_VF_ROSTER SCREENSHOT_END err=%d path=%s" % [int(err), shot])
	var run_partial: Dictionary = {
		"schema": "vault-fighters.vf3-wp5.run.v1",
		"run_id": RUN_ID,
		"command_id": COMMAND_ID,
		"wp": "VF3-WP5",
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
		"outcomes": {
			"SCHEMA": schema_v(RosterCasesScript.outcome_schema),
			"SPAWN": schema_v(RosterCasesScript.outcome_spawn),
			"EQUIP": schema_v(RosterCasesScript.outcome_equip),
			"ATTACK": schema_v(RosterCasesScript.outcome_attack),
			"DROP": schema_v(RosterCasesScript.outcome_drop),
			"SERIALIZE": schema_v(RosterCasesScript.outcome_serialize),
			"KEEP": schema_v(RosterCasesScript.outcome_keep),
			"AMMO": schema_v(RosterCasesScript.outcome_ammo),
			"DATA": schema_v(RosterCasesScript.outcome_data),
			"LIVE": schema_v(RosterCasesScript.outcome_live),
			"REPLAY": schema_v(RosterCasesScript.outcome_replay),
			"USED_APPLY_FRAMES": RosterCasesScript.used_apply_frames,
			"USED_APPLY_ATTEMPTED": RosterCasesScript.used_apply_frames_attempted,
			"USED_APPLY_SUCCEEDED": RosterCasesScript.used_apply_frames_succeeded,
		},
		"fail_count": _fails.size(),
	}
	_write_json(ev.path_join("run_partial.json"), run_partial)
	print("HH_VF_ROSTER EVIDENCE_DIR=%s" % ev)


func schema_v(row: Dictionary) -> String:
	return str(row.get("verdict", "unproven"))


func _write_json(path: String, data: Variant) -> void:
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		print("HH_VF_ROSTER EVIDENCE_WRITE_FAIL %s" % path)
		return
	f.store_string(JSON.stringify(data, "\t"))
	f.close()

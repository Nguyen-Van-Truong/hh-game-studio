extends SceneTree

const RUN_ID := "VF3WP6-20260829-ASIA-SAIGON-03"
const COMMAND_ID := "cmd.vf3-wp6.balance.3"
const SEED := 7
const MODE := "vs2"
const MAP_ID := "fx_balance_melee"

const BalanceCasesScript: GDScript = preload("res://tests/balance_cases.gd")

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
	var errors: PackedStringArray = await BalanceCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	var schema: String = str(BalanceCasesScript.outcome_schema.get("verdict", "unproven"))
	var batch: String = str(BalanceCasesScript.outcome_batch.get("verdict", "unproven"))
	var dist: String = str(BalanceCasesScript.outcome_dist.get("verdict", "unproven"))
	var dom: String = str(BalanceCasesScript.outcome_dom.get("verdict", "unproven"))
	var melee: String = str(BalanceCasesScript.outcome_melee.get("verdict", "unproven"))
	var high: String = str(BalanceCasesScript.outcome_high.get("verdict", "unproven"))
	var overcap: String = str(BalanceCasesScript.outcome_overcap.get("verdict", "unproven"))
	var pit: String = str(BalanceCasesScript.outcome_pit.get("verdict", "unproven"))
	var chain: String = str(BalanceCasesScript.outcome_chain.get("verdict", "unproven"))
	var ff: String = str(BalanceCasesScript.outcome_ff.get("verdict", "unproven"))
	var stamina: String = str(BalanceCasesScript.outcome_stamina.get("verdict", "unproven"))
	var data: String = str(BalanceCasesScript.outcome_data.get("verdict", "unproven"))
	var live: String = str(BalanceCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(BalanceCasesScript.outcome_replay.get("verdict", "unproven"))
	if schema != "pass":
		_fail("SCHEMA structured outcome is %s" % schema)
	if batch != "pass":
		_fail("BATCH structured outcome is %s" % batch)
	if dist != "pass":
		_fail("DIST structured outcome is %s" % dist)
	if dom != "pass":
		_fail("DOM structured outcome is %s" % dom)
	if melee != "pass":
		_fail("MELEE structured outcome is %s" % melee)
	if high != "pass":
		_fail("HIGH structured outcome is %s" % high)
	if overcap != "pass":
		_fail("OVERCAP structured outcome is %s" % overcap)
	if pit != "pass":
		_fail("PIT structured outcome is %s" % pit)
	if chain != "pass":
		_fail("CHAIN structured outcome is %s" % chain)
	if ff != "pass":
		_fail("FF structured outcome is %s" % ff)
	if stamina != "pass":
		_fail("STAMINA structured outcome is %s" % stamina)
	if data != "pass":
		_fail("DATA structured outcome is %s" % data)
	if live != "pass":
		_fail("LIVE structured outcome is %s" % live)
	if replay != "match":
		_fail("REPLAY structured outcome is %s" % replay)
	var ended_at: String = _iso_local()
	print("HH_VF_BALANCE run_id=%s" % RUN_ID)
	print("HH_VF_BALANCE command_id=%s" % COMMAND_ID)
	print("HH_VF_BALANCE DISPLAY=%s" % DisplayServer.get_name())
	print("HH_VF_BALANCE SEED=%d MAP=%s MODE=%s" % [SEED, MAP_ID, MODE])
	print("HH_VF_BALANCE STARTED_AT=%s ENDED_AT=%s" % [_started_at, ended_at])
	print(
		"HH_VF_BALANCE USED_STEP_FIXED=%d USED_APPLY_FRAMES=%d USED_APPLY_ATTEMPTED=%d USED_APPLY_SUCCEEDED=%d USED_PARSE_INPUT_EVENT=%d USED_ACTION_PRESS=%d"
		% [
			BalanceCasesScript.used_step_fixed,
			BalanceCasesScript.used_apply_frames,
			BalanceCasesScript.used_apply_frames_attempted,
			BalanceCasesScript.used_apply_frames_succeeded,
			BalanceCasesScript.used_parse_input_event,
			BalanceCasesScript.used_action_press
		]
	)
	print("HH_VF_BALANCE SCHEMA=%s SCHEMA_SOURCE=outcome_schema" % schema)
	print("HH_VF_BALANCE BATCH=%s BATCH_SOURCE=outcome_batch" % batch)
	print("HH_VF_BALANCE DIST=%s DIST_SOURCE=outcome_dist" % dist)
	print("HH_VF_BALANCE DOM=%s DOM_SOURCE=outcome_dom" % dom)
	print("HH_VF_BALANCE MELEE=%s MELEE_SOURCE=outcome_melee" % melee)
	print("HH_VF_BALANCE HIGH=%s HIGH_SOURCE=outcome_high" % high)
	print("HH_VF_BALANCE OVERCAP=%s OVERCAP_SOURCE=outcome_overcap" % overcap)
	print("HH_VF_BALANCE PIT=%s PIT_SOURCE=outcome_pit" % pit)
	print("HH_VF_BALANCE CHAIN=%s CHAIN_SOURCE=outcome_chain" % chain)
	print("HH_VF_BALANCE FF=%s FF_SOURCE=outcome_ff" % ff)
	print("HH_VF_BALANCE STAMINA=%s STAMINA_SOURCE=outcome_stamina" % stamina)
	print("HH_VF_BALANCE DATA=%s DATA_SOURCE=outcome_data" % data)
	print("HH_VF_BALANCE LIVE=%s LIVE_SOURCE=outcome_live" % live)
	print("HH_VF_BALANCE REPLAY=%s REPLAY_SOURCE=outcome_replay" % replay)
	print("HH_VF_BALANCE CHAOS=assumption CRIT=assumption KNOCK=assumption SPREAD=assumption CAP=assumption STAMINA=assumption HOLD_AIM=assumption ROLL_DIVE=unavailable CLOCK=RL-SIM-FIXED-60")
	await process_frame
	await process_frame
	_write_evidence(app, ended_at)
	if _fails.is_empty():
		print("PASS: Vault Fighters combat balance")
	else:
		print("FAIL: Vault Fighters combat balance")
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
		"schema": BalanceCasesScript.outcome_schema,
		"batch": BalanceCasesScript.outcome_batch,
		"dist": BalanceCasesScript.outcome_dist,
		"dom": BalanceCasesScript.outcome_dom,
		"melee": BalanceCasesScript.outcome_melee,
		"high": BalanceCasesScript.outcome_high,
		"overcap": BalanceCasesScript.outcome_overcap,
		"pit": BalanceCasesScript.outcome_pit,
		"chain": BalanceCasesScript.outcome_chain,
		"ff": BalanceCasesScript.outcome_ff,
		"stamina": BalanceCasesScript.outcome_stamina,
		"data": BalanceCasesScript.outcome_data,
		"live": BalanceCasesScript.outcome_live,
		"replay": BalanceCasesScript.outcome_replay,
		"report": BalanceCasesScript.batch_report,
		"apply": {
			"attempted": BalanceCasesScript.used_apply_frames_attempted,
			"succeeded": BalanceCasesScript.used_apply_frames_succeeded,
			"used_apply_frames": BalanceCasesScript.used_apply_frames,
			"used_step_fixed": BalanceCasesScript.used_step_fixed,
			"used_parse_input_event": BalanceCasesScript.used_parse_input_event,
			"used_action_press": BalanceCasesScript.used_action_press,
		},
	}
	_write_json(ev.path_join("outcomes.json"), outcomes)
	_write_json(ev.path_join("snapshot_start.json"), BalanceCasesScript.snapshot_start)
	_write_json(ev.path_join("snapshot_end.json"), BalanceCasesScript.snapshot_end)
	_write_json(ev.path_join("state_hashes.json"), {
		"replay": BalanceCasesScript.outcome_replay,
		"seed": SEED,
		"map_id": MAP_ID,
		"mode": MODE,
		"batch": BalanceCasesScript.outcome_batch,
	})
	var events_path: String = ev.path_join("events.jsonl")
	var ef: FileAccess = FileAccess.open(events_path, FileAccess.WRITE)
	if ef != null:
		var events: Array = BalanceCasesScript.events_all
		if events.is_empty():
			events = BalanceCasesScript.events_end
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
				print("HH_VF_BALANCE SCREENSHOT_END missing viewport texture")
			else:
				var img: Image = tex.get_image()
				if img == null:
					print("HH_VF_BALANCE SCREENSHOT_END get_image null")
				else:
					var shot: String = ev.path_join("screens").path_join("balance_%dx%d.png" % [
						int(vis.size.x), int(vis.size.y)
					])
					var err: Error = img.save_png(shot)
					print("HH_VF_BALANCE SCREENSHOT_END err=%d path=%s" % [int(err), shot])
	var run_partial: Dictionary = {
		"schema": "vault-fighters.vf3-wp6.run.v1",
		"run_id": RUN_ID,
		"command_id": COMMAND_ID,
		"wp": "VF3-WP6",
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
			"SCHEMA": schema_v(BalanceCasesScript.outcome_schema),
			"BATCH": schema_v(BalanceCasesScript.outcome_batch),
			"DIST": schema_v(BalanceCasesScript.outcome_dist),
			"DOM": schema_v(BalanceCasesScript.outcome_dom),
			"MELEE": schema_v(BalanceCasesScript.outcome_melee),
			"HIGH": schema_v(BalanceCasesScript.outcome_high),
			"OVERCAP": schema_v(BalanceCasesScript.outcome_overcap),
			"PIT": schema_v(BalanceCasesScript.outcome_pit),
			"CHAIN": schema_v(BalanceCasesScript.outcome_chain),
			"FF": schema_v(BalanceCasesScript.outcome_ff),
			"STAMINA": schema_v(BalanceCasesScript.outcome_stamina),
			"DATA": schema_v(BalanceCasesScript.outcome_data),
			"LIVE": schema_v(BalanceCasesScript.outcome_live),
			"REPLAY": schema_v(BalanceCasesScript.outcome_replay),
			"USED_APPLY_FRAMES": BalanceCasesScript.used_apply_frames,
			"USED_APPLY_ATTEMPTED": BalanceCasesScript.used_apply_frames_attempted,
			"USED_APPLY_SUCCEEDED": BalanceCasesScript.used_apply_frames_succeeded,
		},
		"fail_count": _fails.size(),
	}
	_write_json(ev.path_join("run_partial.json"), run_partial)
	print("HH_VF_BALANCE EVIDENCE_DIR=%s" % ev)


func schema_v(row: Dictionary) -> String:
	return str(row.get("verdict", "unproven"))


func _write_json(path: String, data: Variant) -> void:
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		print("HH_VF_BALANCE EVIDENCE_WRITE_FAIL %s" % path)
		return
	f.store_string(JSON.stringify(data, "\t"))
	f.close()

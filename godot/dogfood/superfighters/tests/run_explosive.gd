extends SceneTree

const RUN_ID := "VF3WP4-20260829-ASIA-SAIGON-01"
const COMMAND_ID := "cmd.vf3-wp4.explosive.1"
const SEED := 7
const MODE := "vs2"
const MAP_ID := "fx_nade_open"

const ExplosiveCasesScript: GDScript = preload("res://tests/explosive_cases.gd")

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
	var errors: PackedStringArray = await ExplosiveCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	var hold: String = str(ExplosiveCasesScript.outcome_hold.get("verdict", "unproven"))
	var throwv: String = str(ExplosiveCasesScript.outcome_throw.get("verdict", "unproven"))
	var arc: String = str(ExplosiveCasesScript.outcome_arc.get("verdict", "unproven"))
	var bounce: String = str(ExplosiveCasesScript.outcome_bounce.get("verdict", "unproven"))
	var fuse: String = str(ExplosiveCasesScript.outcome_fuse.get("verdict", "unproven"))
	var falloff: String = str(ExplosiveCasesScript.outcome_falloff.get("verdict", "unproven"))
	var owner: String = str(ExplosiveCasesScript.outcome_owner.get("verdict", "unproven"))
	var once: String = str(ExplosiveCasesScript.outcome_once.get("verdict", "unproven"))
	var timeout: String = str(ExplosiveCasesScript.outcome_timeout.get("verdict", "unproven"))
	var sweep: String = str(ExplosiveCasesScript.outcome_sweep.get("verdict", "unproven"))
	var data: String = str(ExplosiveCasesScript.outcome_data.get("verdict", "unproven"))
	var live: String = str(ExplosiveCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(ExplosiveCasesScript.outcome_replay.get("verdict", "unproven"))
	if hold != "pass":
		_fail("HOLD structured outcome is %s" % hold)
	if throwv != "pass":
		_fail("THROW structured outcome is %s" % throwv)
	if arc != "pass":
		_fail("ARC structured outcome is %s" % arc)
	if bounce != "pass":
		_fail("BOUNCE structured outcome is %s" % bounce)
	if fuse != "pass":
		_fail("FUSE structured outcome is %s" % fuse)
	if falloff != "pass":
		_fail("FALLOFF structured outcome is %s" % falloff)
	if owner != "pass":
		_fail("OWNER structured outcome is %s" % owner)
	if once != "pass":
		_fail("ONCE structured outcome is %s" % once)
	if timeout != "pass":
		_fail("TIMEOUT structured outcome is %s" % timeout)
	if sweep != "pass":
		_fail("SWEEP structured outcome is %s" % sweep)
	if data != "pass":
		_fail("DATA structured outcome is %s" % data)
	if live != "pass":
		_fail("LIVE structured outcome is %s" % live)
	if replay != "match":
		_fail("REPLAY structured outcome is %s" % replay)
	var ended_at: String = _iso_local()
	print("HH_VF_EXPL run_id=%s" % RUN_ID)
	print("HH_VF_EXPL command_id=%s" % COMMAND_ID)
	print("HH_VF_EXPL DISPLAY=%s" % DisplayServer.get_name())
	print("HH_VF_EXPL SEED=%d MAP=%s MODE=%s" % [SEED, MAP_ID, MODE])
	print("HH_VF_EXPL STARTED_AT=%s ENDED_AT=%s" % [_started_at, ended_at])
	print(
		"HH_VF_EXPL USED_STEP_FIXED=%d USED_APPLY_FRAMES=%d USED_APPLY_ATTEMPTED=%d USED_APPLY_SUCCEEDED=%d USED_PARSE_INPUT_EVENT=%d USED_ACTION_PRESS=%d"
		% [
			ExplosiveCasesScript.used_step_fixed,
			ExplosiveCasesScript.used_apply_frames,
			ExplosiveCasesScript.used_apply_frames_attempted,
			ExplosiveCasesScript.used_apply_frames_succeeded,
			ExplosiveCasesScript.used_parse_input_event,
			ExplosiveCasesScript.used_action_press
		]
	)
	print("HH_VF_EXPL HOLD=%s HOLD_SOURCE=outcome_hold" % hold)
	print("HH_VF_EXPL THROW=%s THROW_SOURCE=outcome_throw" % throwv)
	print("HH_VF_EXPL ARC=%s ARC_SOURCE=outcome_arc" % arc)
	print("HH_VF_EXPL BOUNCE=%s BOUNCE_SOURCE=outcome_bounce" % bounce)
	print("HH_VF_EXPL FUSE=%s FUSE_SOURCE=outcome_fuse" % fuse)
	print("HH_VF_EXPL FALLOFF=%s FALLOFF_SOURCE=outcome_falloff" % falloff)
	print("HH_VF_EXPL OWNER=%s OWNER_SOURCE=outcome_owner" % owner)
	print("HH_VF_EXPL ONCE=%s ONCE_SOURCE=outcome_once" % once)
	print("HH_VF_EXPL TIMEOUT=%s TIMEOUT_SOURCE=outcome_timeout" % timeout)
	print("HH_VF_EXPL SWEEP=%s SWEEP_SOURCE=outcome_sweep" % sweep)
	print("HH_VF_EXPL DATA=%s DATA_SOURCE=outcome_data" % data)
	print("HH_VF_EXPL LIVE=%s LIVE_SOURCE=outcome_live" % live)
	print("HH_VF_EXPL REPLAY=%s REPLAY_SOURCE=outcome_replay" % replay)
	print("HH_VF_EXPL HOLD_THROW=assumption ARC=assumption BOUNCE=assumption FUSE=assumption FALLOFF=assumption OWNER=assumption ONCE=assumption TIMEOUT=assumption SWEEP=assumption PROP=deferred HOLD_AIM=assumption ROLL_DIVE=unavailable CLOCK=RL-SIM-FIXED-60")
	await process_frame
	await process_frame
	_write_evidence(app, ended_at)
	if _fails.is_empty():
		print("PASS: Vault Fighters grenade explosive")
	else:
		print("FAIL: Vault Fighters grenade explosive")
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
		"hold": ExplosiveCasesScript.outcome_hold,
		"throw": ExplosiveCasesScript.outcome_throw,
		"arc": ExplosiveCasesScript.outcome_arc,
		"bounce": ExplosiveCasesScript.outcome_bounce,
		"fuse": ExplosiveCasesScript.outcome_fuse,
		"falloff": ExplosiveCasesScript.outcome_falloff,
		"owner": ExplosiveCasesScript.outcome_owner,
		"once": ExplosiveCasesScript.outcome_once,
		"timeout": ExplosiveCasesScript.outcome_timeout,
		"sweep": ExplosiveCasesScript.outcome_sweep,
		"data": ExplosiveCasesScript.outcome_data,
		"live": ExplosiveCasesScript.outcome_live,
		"replay": ExplosiveCasesScript.outcome_replay,
		"apply": {
			"attempted": ExplosiveCasesScript.used_apply_frames_attempted,
			"succeeded": ExplosiveCasesScript.used_apply_frames_succeeded,
			"used_apply_frames": ExplosiveCasesScript.used_apply_frames,
			"used_step_fixed": ExplosiveCasesScript.used_step_fixed,
			"used_parse_input_event": ExplosiveCasesScript.used_parse_input_event,
			"used_action_press": ExplosiveCasesScript.used_action_press,
		},
	}
	_write_json(ev.path_join("outcomes.json"), outcomes)
	_write_json(ev.path_join("snapshot_start.json"), ExplosiveCasesScript.snapshot_start)
	_write_json(ev.path_join("snapshot_end.json"), ExplosiveCasesScript.snapshot_end)
	_write_json(ev.path_join("state_hashes.json"), {
		"replay": ExplosiveCasesScript.outcome_replay,
		"seed": SEED,
		"map_id": MAP_ID,
		"mode": MODE,
	})
	var events_path: String = ev.path_join("events.jsonl")
	var ef: FileAccess = FileAccess.open(events_path, FileAccess.WRITE)
	if ef != null:
		var events: Array = ExplosiveCasesScript.events_all
		if events.is_empty():
			events = ExplosiveCasesScript.events_end
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
				print("HH_VF_EXPL SCREENSHOT_END missing viewport texture")
			else:
				var img: Image = tex.get_image()
				if img == null:
					print("HH_VF_EXPL SCREENSHOT_END get_image null")
				else:
					var shot: String = ev.path_join("screens").path_join("nade_%dx%d.png" % [
						int(vis.size.x), int(vis.size.y)
					])
					var err: Error = img.save_png(shot)
					print("HH_VF_EXPL SCREENSHOT_END err=%d path=%s" % [int(err), shot])
	var run_partial: Dictionary = {
		"schema": "vault-fighters.vf3-wp4.run.v1",
		"run_id": RUN_ID,
		"command_id": COMMAND_ID,
		"wp": "VF3-WP4",
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
			"HOLD": str(ExplosiveCasesScript.outcome_hold.get("verdict", "unproven")),
			"THROW": str(ExplosiveCasesScript.outcome_throw.get("verdict", "unproven")),
			"ARC": str(ExplosiveCasesScript.outcome_arc.get("verdict", "unproven")),
			"BOUNCE": str(ExplosiveCasesScript.outcome_bounce.get("verdict", "unproven")),
			"FUSE": str(ExplosiveCasesScript.outcome_fuse.get("verdict", "unproven")),
			"FALLOFF": str(ExplosiveCasesScript.outcome_falloff.get("verdict", "unproven")),
			"OWNER": str(ExplosiveCasesScript.outcome_owner.get("verdict", "unproven")),
			"ONCE": str(ExplosiveCasesScript.outcome_once.get("verdict", "unproven")),
			"TIMEOUT": str(ExplosiveCasesScript.outcome_timeout.get("verdict", "unproven")),
			"SWEEP": str(ExplosiveCasesScript.outcome_sweep.get("verdict", "unproven")),
			"DATA": str(ExplosiveCasesScript.outcome_data.get("verdict", "unproven")),
			"LIVE": str(ExplosiveCasesScript.outcome_live.get("verdict", "unproven")),
			"REPLAY": str(ExplosiveCasesScript.outcome_replay.get("verdict", "unproven")),
			"USED_APPLY_FRAMES": ExplosiveCasesScript.used_apply_frames,
			"USED_APPLY_ATTEMPTED": ExplosiveCasesScript.used_apply_frames_attempted,
			"USED_APPLY_SUCCEEDED": ExplosiveCasesScript.used_apply_frames_succeeded,
		},
		"fail_count": _fails.size(),
	}
	_write_json(ev.path_join("run_partial.json"), run_partial)
	print("HH_VF_EXPL EVIDENCE_DIR=%s" % ev)


func _write_json(path: String, data: Variant) -> void:
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		print("HH_VF_EXPL EVIDENCE_WRITE_FAIL %s" % path)
		return
	f.store_string(JSON.stringify(data, "\t"))
	f.close()

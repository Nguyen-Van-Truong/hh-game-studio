extends SceneTree

const RUN_ID := "VF3WP3-20260829-ASIA-SAIGON-01"
const COMMAND_ID := "cmd.vf3-wp3.aim-fire.1"
const SEED := 7
const MODE := "vs2"
const MAP_ID := "fx_aim_open"

const AimCasesScript: GDScript = preload("res://tests/aim_cases.gd")

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
	var errors: PackedStringArray = await AimCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	var hold: String = str(AimCasesScript.outcome_hold.get("verdict", "unproven"))
	var dirs: String = str(AimCasesScript.outcome_dirs.get("verdict", "unproven"))
	var semi: String = str(AimCasesScript.outcome_semi.get("verdict", "unproven"))
	var auto: String = str(AimCasesScript.outcome_auto.get("verdict", "unproven"))
	var ammo: String = str(AimCasesScript.outcome_ammo.get("verdict", "unproven"))
	var muzzle: String = str(AimCasesScript.outcome_muzzle.get("verdict", "unproven"))
	var recoil: String = str(AimCasesScript.outcome_recoil.get("verdict", "unproven"))
	var data: String = str(AimCasesScript.outcome_data.get("verdict", "unproven"))
	var sweep: String = str(AimCasesScript.outcome_sweep.get("verdict", "unproven"))
	var live: String = str(AimCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(AimCasesScript.outcome_replay.get("verdict", "unproven"))
	if hold != "pass":
		_fail("HOLD structured outcome is %s" % hold)
	if dirs != "pass":
		_fail("DIRS structured outcome is %s" % dirs)
	if semi != "pass":
		_fail("SEMI structured outcome is %s" % semi)
	if auto != "pass":
		_fail("AUTO structured outcome is %s" % auto)
	if ammo != "pass":
		_fail("AMMO structured outcome is %s" % ammo)
	if muzzle != "pass":
		_fail("MUZZLE structured outcome is %s" % muzzle)
	if recoil != "pass":
		_fail("RECOIL structured outcome is %s" % recoil)
	if data != "pass":
		_fail("DATA structured outcome is %s" % data)
	if sweep != "pass":
		_fail("SWEEP structured outcome is %s" % sweep)
	if live != "pass":
		_fail("LIVE structured outcome is %s" % live)
	if replay != "match":
		_fail("REPLAY structured outcome is %s" % replay)
	var ended_at: String = _iso_local()
	print("HH_VF_AIM run_id=%s" % RUN_ID)
	print("HH_VF_AIM command_id=%s" % COMMAND_ID)
	print("HH_VF_AIM DISPLAY=%s" % DisplayServer.get_name())
	print("HH_VF_AIM SEED=%d MAP=%s MODE=%s" % [SEED, MAP_ID, MODE])
	print("HH_VF_AIM STARTED_AT=%s ENDED_AT=%s" % [_started_at, ended_at])
	print(
		"HH_VF_AIM USED_STEP_FIXED=%d USED_APPLY_FRAMES=%d USED_APPLY_ATTEMPTED=%d USED_APPLY_SUCCEEDED=%d USED_PARSE_INPUT_EVENT=%d USED_ACTION_PRESS=%d"
		% [
			AimCasesScript.used_step_fixed,
			AimCasesScript.used_apply_frames,
			AimCasesScript.used_apply_frames_attempted,
			AimCasesScript.used_apply_frames_succeeded,
			AimCasesScript.used_parse_input_event,
			AimCasesScript.used_action_press
		]
	)
	print("HH_VF_AIM HOLD=%s HOLD_SOURCE=outcome_hold" % hold)
	print("HH_VF_AIM DIRS=%s DIRS_SOURCE=outcome_dirs" % dirs)
	print("HH_VF_AIM SEMI=%s SEMI_SOURCE=outcome_semi" % semi)
	print("HH_VF_AIM AUTO=%s AUTO_SOURCE=outcome_auto" % auto)
	print("HH_VF_AIM AMMO=%s AMMO_SOURCE=outcome_ammo" % ammo)
	print("HH_VF_AIM MUZZLE=%s MUZZLE_SOURCE=outcome_muzzle" % muzzle)
	print("HH_VF_AIM RECOIL=%s RECOIL_SOURCE=outcome_recoil" % recoil)
	print("HH_VF_AIM DATA=%s DATA_SOURCE=outcome_data" % data)
	print("HH_VF_AIM SWEEP=%s SWEEP_SOURCE=outcome_sweep" % sweep)
	print("HH_VF_AIM LIVE=%s LIVE_SOURCE=outcome_live" % live)
	print("HH_VF_AIM REPLAY=%s REPLAY_SOURCE=outcome_replay" % replay)
	print("HH_VF_AIM HOLD_AIM=assumption DIRS=assumption SEMI=assumption AUTO=assumption AMMO=assumption MUZZLE=assumption RECOIL=assumption BALLISTIC=assumption SWEEP=assumption ROLL_DIVE=unavailable CLOCK=RL-SIM-FIXED-60")
	await process_frame
	await process_frame
	_write_evidence(app, ended_at)
	if _fails.is_empty():
		print("PASS: Vault Fighters aim fire release")
	else:
		print("FAIL: Vault Fighters aim fire release")
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
		"hold": AimCasesScript.outcome_hold,
		"dirs": AimCasesScript.outcome_dirs,
		"semi": AimCasesScript.outcome_semi,
		"auto": AimCasesScript.outcome_auto,
		"ammo": AimCasesScript.outcome_ammo,
		"muzzle": AimCasesScript.outcome_muzzle,
		"recoil": AimCasesScript.outcome_recoil,
		"data": AimCasesScript.outcome_data,
		"sweep": AimCasesScript.outcome_sweep,
		"live": AimCasesScript.outcome_live,
		"replay": AimCasesScript.outcome_replay,
		"apply": {
			"attempted": AimCasesScript.used_apply_frames_attempted,
			"succeeded": AimCasesScript.used_apply_frames_succeeded,
			"used_apply_frames": AimCasesScript.used_apply_frames,
			"used_step_fixed": AimCasesScript.used_step_fixed,
			"used_parse_input_event": AimCasesScript.used_parse_input_event,
			"used_action_press": AimCasesScript.used_action_press,
		},
	}
	_write_json(ev.path_join("outcomes.json"), outcomes)
	_write_json(ev.path_join("snapshot_start.json"), AimCasesScript.snapshot_start)
	_write_json(ev.path_join("snapshot_end.json"), AimCasesScript.snapshot_end)
	_write_json(ev.path_join("state_hashes.json"), {
		"replay": AimCasesScript.outcome_replay,
		"seed": SEED,
		"map_id": MAP_ID,
		"mode": MODE,
	})
	var events_path: String = ev.path_join("events.jsonl")
	var ef: FileAccess = FileAccess.open(events_path, FileAccess.WRITE)
	if ef != null:
		var events: Array = AimCasesScript.events_all
		if events.is_empty():
			events = AimCasesScript.events_end
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
				print("HH_VF_AIM SCREENSHOT_END missing viewport texture")
			else:
				var img: Image = tex.get_image()
				if img == null:
					print("HH_VF_AIM SCREENSHOT_END get_image null")
				else:
					var shot: String = ev.path_join("screens").path_join("aim_%dx%d.png" % [
						int(vis.size.x), int(vis.size.y)
					])
					var err: Error = img.save_png(shot)
					print("HH_VF_AIM SCREENSHOT_END err=%d path=%s" % [int(err), shot])
	var run_partial: Dictionary = {
		"schema": "vault-fighters.vf3-wp3.run.v1",
		"run_id": RUN_ID,
		"command_id": COMMAND_ID,
		"wp": "VF3-WP3",
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
			"HOLD": str(AimCasesScript.outcome_hold.get("verdict", "unproven")),
			"DIRS": str(AimCasesScript.outcome_dirs.get("verdict", "unproven")),
			"SEMI": str(AimCasesScript.outcome_semi.get("verdict", "unproven")),
			"AUTO": str(AimCasesScript.outcome_auto.get("verdict", "unproven")),
			"AMMO": str(AimCasesScript.outcome_ammo.get("verdict", "unproven")),
			"MUZZLE": str(AimCasesScript.outcome_muzzle.get("verdict", "unproven")),
			"RECOIL": str(AimCasesScript.outcome_recoil.get("verdict", "unproven")),
			"DATA": str(AimCasesScript.outcome_data.get("verdict", "unproven")),
			"SWEEP": str(AimCasesScript.outcome_sweep.get("verdict", "unproven")),
			"LIVE": str(AimCasesScript.outcome_live.get("verdict", "unproven")),
			"REPLAY": str(AimCasesScript.outcome_replay.get("verdict", "unproven")),
			"USED_APPLY_FRAMES": AimCasesScript.used_apply_frames,
			"USED_APPLY_ATTEMPTED": AimCasesScript.used_apply_frames_attempted,
			"USED_APPLY_SUCCEEDED": AimCasesScript.used_apply_frames_succeeded,
		},
		"fail_count": _fails.size(),
	}
	_write_json(ev.path_join("run_partial.json"), run_partial)
	print("HH_VF_AIM EVIDENCE_DIR=%s" % ev)


func _write_json(path: String, data: Variant) -> void:
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		print("HH_VF_AIM EVIDENCE_WRITE_FAIL %s" % path)
		return
	f.store_string(JSON.stringify(data, "\t"))
	f.close()

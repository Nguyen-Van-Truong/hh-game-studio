extends SceneTree

const RUN_ID := "VF4WP2-20260829-ASIA-SAIGON-01"
const COMMAND_ID := "cmd.vf4-wp2.break.1"
const SEED := 7
const MODE := "vs2"
const MAP_ID := "fx_break_cover"

const BreakCasesScript: GDScript = preload("res://tests/break_cases.gd")

var _fails: PackedStringArray = PackedStringArray()
var _started_at: String = ""
var _started_unix: float = 0.0
var _before_shot: String = ""


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
	await process_frame
	await process_frame
	_before_shot = _maybe_shot(app, "break_before")
	var errors: PackedStringArray = await BreakCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	var data: String = str(BreakCasesScript.outcome_data.get("verdict", "unproven"))
	var brk: String = str(BreakCasesScript.outcome_break.get("verdict", "unproven"))
	var debris: String = str(BreakCasesScript.outcome_debris.get("verdict", "unproven"))
	var passv: String = str(BreakCasesScript.outcome_pass.get("verdict", "unproven"))
	var ghost: String = str(BreakCasesScript.outcome_ghost.get("verdict", "unproven"))
	var melee: String = str(BreakCasesScript.outcome_melee.get("verdict", "unproven"))
	var shove: String = str(BreakCasesScript.outcome_shove.get("verdict", "unproven"))
	var throwv: String = str(BreakCasesScript.outcome_throw.get("verdict", "unproven"))
	var tactic: String = str(BreakCasesScript.outcome_tactic.get("verdict", "unproven"))
	var live: String = str(BreakCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(BreakCasesScript.outcome_replay.get("verdict", "unproven"))
	if data != "pass":
		_fail("DATA structured outcome is %s" % data)
	if brk != "pass":
		_fail("BREAK structured outcome is %s" % brk)
	if debris != "pass":
		_fail("DEBRIS structured outcome is %s" % debris)
	if passv != "pass":
		_fail("PASS structured outcome is %s" % passv)
	if ghost != "pass":
		_fail("GHOST structured outcome is %s" % ghost)
	if melee != "pass":
		_fail("MELEE structured outcome is %s" % melee)
	if shove != "pass":
		_fail("SHOVE structured outcome is %s" % shove)
	if throwv != "pass":
		_fail("THROW structured outcome is %s" % throwv)
	if tactic != "pass":
		_fail("TACTIC structured outcome is %s" % tactic)
	if live != "pass":
		_fail("LIVE structured outcome is %s" % live)
	if replay != "match":
		_fail("REPLAY structured outcome is %s" % replay)
	var ended_at: String = _iso_local()
	print("HH_VF_BREAK run_id=%s" % RUN_ID)
	print("HH_VF_BREAK command_id=%s" % COMMAND_ID)
	print("HH_VF_BREAK DISPLAY=%s" % DisplayServer.get_name())
	print("HH_VF_BREAK SEED=%d MAP=%s MODE=%s" % [SEED, MAP_ID, MODE])
	print("HH_VF_BREAK STARTED_AT=%s ENDED_AT=%s" % [_started_at, ended_at])
	print(
		"HH_VF_BREAK USED_STEP_FIXED=%d USED_APPLY_FRAMES=%d USED_APPLY_ATTEMPTED=%d USED_APPLY_SUCCEEDED=%d USED_PARSE_INPUT_EVENT=%d USED_ACTION_PRESS=%d"
		% [
			BreakCasesScript.used_step_fixed,
			BreakCasesScript.used_apply_frames,
			BreakCasesScript.used_apply_frames_attempted,
			BreakCasesScript.used_apply_frames_succeeded,
			BreakCasesScript.used_parse_input_event,
			BreakCasesScript.used_action_press
		]
	)
	print("HH_VF_BREAK DATA=%s DATA_SOURCE=outcome_data" % data)
	print("HH_VF_BREAK BREAK=%s BREAK_SOURCE=outcome_break" % brk)
	print("HH_VF_BREAK DEBRIS=%s DEBRIS_SOURCE=outcome_debris" % debris)
	print("HH_VF_BREAK PASS=%s PASS_SOURCE=outcome_pass" % passv)
	print("HH_VF_BREAK GHOST=%s GHOST_SOURCE=outcome_ghost" % ghost)
	print("HH_VF_BREAK MELEE=%s MELEE_SOURCE=outcome_melee" % melee)
	print("HH_VF_BREAK SHOVE=%s SHOVE_SOURCE=outcome_shove" % shove)
	print("HH_VF_BREAK THROW=%s THROW_SOURCE=outcome_throw" % throwv)
	print("HH_VF_BREAK TACTIC=%s TACTIC_SOURCE=outcome_tactic" % tactic)
	print("HH_VF_BREAK LIVE=%s LIVE_SOURCE=outcome_live" % live)
	print("HH_VF_BREAK REPLAY=%s REPLAY_SOURCE=outcome_replay" % replay)
	print("HH_VF_BREAK BREAK_CLASS=assumption THROW=assumption EXPL=assumption NADE_PROP=deferred HOLD_AIM=assumption ROLL_DIVE=unavailable CLOCK=RL-SIM-FIXED-60")
	await process_frame
	await process_frame
	_write_evidence(app, ended_at, data, brk, debris, passv, ghost, melee, shove, throwv, tactic, live, replay)
	if _fails.is_empty():
		print("PASS: Vault Fighters breakable props")
	else:
		print("FAIL: Vault Fighters breakable props")
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
		print("HH_VF_BREAK SCREENSHOT_%s missing viewport texture" % stem)
		return ""
	var img: Image = tex.get_image()
	if img == null:
		print("HH_VF_BREAK SCREENSHOT_%s get_image null" % stem)
		return ""
	var shot: String = ev.path_join("screens").path_join("%s_%dx%d.png" % [stem, int(vis.size.x), int(vis.size.y)])
	var err: Error = img.save_png(shot)
	print("HH_VF_BREAK SCREENSHOT_%s err=%d path=%s" % [stem, int(err), shot])
	return shot


func _write_evidence(
	app: App, ended_at: String, data: String, brk: String, debris: String, passv: String,
	ghost: String, melee: String, shove: String, throwv: String, tactic: String, live: String, replay: String
) -> void:
	var ev: String = OS.get_environment("HH_VF_EVIDENCE_DIR")
	if ev == "":
		ev = ProjectSettings.globalize_path("res://.evidence/%s" % RUN_ID)
	DirAccess.make_dir_recursive_absolute(ev)
	DirAccess.make_dir_recursive_absolute(ev.path_join("screens"))
	var after_shot: String = _maybe_shot(app, "break_after")
	var outcomes: Dictionary = {
		"data": BreakCasesScript.outcome_data,
		"break": BreakCasesScript.outcome_break,
		"debris": BreakCasesScript.outcome_debris,
		"pass": BreakCasesScript.outcome_pass,
		"ghost": BreakCasesScript.outcome_ghost,
		"melee": BreakCasesScript.outcome_melee,
		"shove": BreakCasesScript.outcome_shove,
		"throw": BreakCasesScript.outcome_throw,
		"tactic": BreakCasesScript.outcome_tactic,
		"live": BreakCasesScript.outcome_live,
		"replay": BreakCasesScript.outcome_replay,
		"apply": {
			"attempted": BreakCasesScript.used_apply_frames_attempted,
			"succeeded": BreakCasesScript.used_apply_frames_succeeded,
			"used_apply_frames": BreakCasesScript.used_apply_frames,
			"used_step_fixed": BreakCasesScript.used_step_fixed,
			"used_parse_input_event": BreakCasesScript.used_parse_input_event,
			"used_action_press": BreakCasesScript.used_action_press,
		},
	}
	_write_json(ev.path_join("outcomes.json"), outcomes)
	_write_json(ev.path_join("snapshot_start.json"), BreakCasesScript.snapshot_start)
	_write_json(ev.path_join("snapshot_end.json"), BreakCasesScript.snapshot_end)
	_write_json(ev.path_join("state_hashes.json"), {
		"replay": BreakCasesScript.outcome_replay,
		"break": BreakCasesScript.outcome_break,
		"seed": SEED,
		"map_id": MAP_ID,
		"mode": MODE,
	})
	var events_path: String = ev.path_join("events.jsonl")
	var ef: FileAccess = FileAccess.open(events_path, FileAccess.WRITE)
	if ef != null:
		var events: Array = BreakCasesScript.events_all
		if events.is_empty():
			events = BreakCasesScript.events_end
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
		"schema": "vault-fighters.vf4-wp2.run.v1",
		"run_id": RUN_ID,
		"command_id": COMMAND_ID,
		"wp": "VF4-WP2",
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
		"screens": {"before": _before_shot, "after": after_shot},
		"outcomes": {
			"DATA": data,
			"BREAK": brk,
			"DEBRIS": debris,
			"PASS": passv,
			"GHOST": ghost,
			"MELEE": melee,
			"SHOVE": shove,
			"THROW": throwv,
			"TACTIC": tactic,
			"LIVE": live,
			"REPLAY": replay,
			"USED_APPLY_FRAMES": BreakCasesScript.used_apply_frames,
			"USED_APPLY_ATTEMPTED": BreakCasesScript.used_apply_frames_attempted,
			"USED_APPLY_SUCCEEDED": BreakCasesScript.used_apply_frames_succeeded,
		},
		"fail_count": _fails.size(),
	}
	_write_json(ev.path_join("run_partial.json"), run_partial)
	print("HH_VF_BREAK EVIDENCE_DIR=%s" % ev)


func _write_json(path: String, data: Variant) -> void:
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		print("HH_VF_BREAK EVIDENCE_WRITE_FAIL %s" % path)
		return
	f.store_string(JSON.stringify(data, "\t"))
	f.close()

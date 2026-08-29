extends SceneTree

const RUN_ID := "VF2WP4-20260829-ASIA-SAIGON-01"
const COMMAND_ID := "cmd.vf2-wp4.dive-jump-kick.1"
const SEED := 1
const MODE := "vs2"
const MAP_ID := "police"

const DiveCasesScript: GDScript = preload("res://tests/dive_cases.gd")

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
	var errors: PackedStringArray = await DiveCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	var dive: String = str(DiveCasesScript.outcome_dive.get("verdict", "unproven"))
	var kick: String = str(DiveCasesScript.outcome_kick.get("verdict", "unproven"))
	var tackle: String = str(DiveCasesScript.outcome_tackle.get("verdict", "unproven"))
	var fall: String = str(DiveCasesScript.outcome_fall.get("verdict", "unproven"))
	var pit: String = str(DiveCasesScript.outcome_pit.get("verdict", "unproven"))
	var dodge: String = str(DiveCasesScript.outcome_dodge.get("verdict", "unproven"))
	var invuln: String = str(DiveCasesScript.outcome_invuln.get("verdict", "unproven"))
	var dist: String = str(DiveCasesScript.outcome_dist.get("verdict", "unproven"))
	var maps: String = str(DiveCasesScript.outcome_maps.get("verdict", "unproven"))
	var live: String = str(DiveCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(DiveCasesScript.outcome_replay.get("verdict", "unproven"))
	if dive != "pass":
		_fail("DIVE structured outcome is %s" % dive)
	if kick != "pass":
		_fail("KICK structured outcome is %s" % kick)
	if tackle != "pass":
		_fail("TACKLE structured outcome is %s" % tackle)
	if fall != "pass":
		_fail("FALL structured outcome is %s" % fall)
	if pit != "pass":
		_fail("PIT structured outcome is %s" % pit)
	if dodge != "pass":
		_fail("DODGE structured outcome is %s" % dodge)
	if invuln != "pass":
		_fail("INVULN structured outcome is %s" % invuln)
	if dist != "pass":
		_fail("DIST structured outcome is %s" % dist)
	if maps != "pass":
		_fail("MAPS structured outcome is %s" % maps)
	if live != "pass":
		_fail("LIVE structured outcome is %s" % live)
	if replay != "match":
		_fail("REPLAY structured outcome is %s" % replay)
	var ended_at: String = _iso_local()
	print("HH_VF_DIVE run_id=%s" % RUN_ID)
	print("HH_VF_DIVE command_id=%s" % COMMAND_ID)
	print("HH_VF_DIVE DISPLAY=%s" % DisplayServer.get_name())
	print("HH_VF_DIVE SEED=%d MAP=%s MODE=%s" % [SEED, MAP_ID, MODE])
	print("HH_VF_DIVE STARTED_AT=%s ENDED_AT=%s" % [_started_at, ended_at])
	print(
		"HH_VF_DIVE USED_STEP_FIXED=%d USED_APPLY_FRAMES=%d USED_APPLY_ATTEMPTED=%d USED_APPLY_SUCCEEDED=%d USED_PARSE_INPUT_EVENT=%d USED_ACTION_PRESS=%d"
		% [
			DiveCasesScript.used_step_fixed,
			DiveCasesScript.used_apply_frames,
			DiveCasesScript.used_apply_frames_attempted,
			DiveCasesScript.used_apply_frames_succeeded,
			DiveCasesScript.used_parse_input_event,
			DiveCasesScript.used_action_press
		]
	)
	print("HH_VF_DIVE DIVE=%s DIVE_SOURCE=outcome_dive" % dive)
	print("HH_VF_DIVE KICK=%s KICK_SOURCE=outcome_kick" % kick)
	print("HH_VF_DIVE TACKLE=%s TACKLE_SOURCE=outcome_tackle" % tackle)
	print("HH_VF_DIVE FALL=%s FALL_SOURCE=outcome_fall" % fall)
	print("HH_VF_DIVE PIT=%s PIT_SOURCE=outcome_pit" % pit)
	print("HH_VF_DIVE DODGE=%s DODGE_SOURCE=outcome_dodge" % dodge)
	print("HH_VF_DIVE INVULN=%s INVULN_SOURCE=outcome_invuln" % invuln)
	print("HH_VF_DIVE DIST=%s DIST_SOURCE=outcome_dist" % dist)
	print("HH_VF_DIVE MAPS=%s MAPS_SOURCE=outcome_maps" % maps)
	print("HH_VF_DIVE LIVE=%s LIVE_SOURCE=outcome_live" % live)
	print("HH_VF_DIVE REPLAY=%s REPLAY_SOURCE=outcome_replay" % replay)
	print("HH_VF_DIVE HOLD_AIM=assumption SPRINT=assumption ROLL=assumption DIVE=assumption KICK=assumption FALL=assumption ROLL_DIVE=unavailable CLOCK=RL-SIM-FIXED-60")
	await process_frame
	await process_frame
	_write_evidence(app, ended_at)
	if _fails.is_empty():
		print("PASS: Vault Fighters dive jump-kick fall")
	else:
		print("FAIL: Vault Fighters dive jump-kick fall")
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
		"dive": DiveCasesScript.outcome_dive,
		"kick": DiveCasesScript.outcome_kick,
		"tackle": DiveCasesScript.outcome_tackle,
		"fall": DiveCasesScript.outcome_fall,
		"pit": DiveCasesScript.outcome_pit,
		"dodge": DiveCasesScript.outcome_dodge,
		"invuln": DiveCasesScript.outcome_invuln,
		"dist": DiveCasesScript.outcome_dist,
		"maps": DiveCasesScript.outcome_maps,
		"live": DiveCasesScript.outcome_live,
		"replay": DiveCasesScript.outcome_replay,
		"apply": {
			"attempted": DiveCasesScript.used_apply_frames_attempted,
			"succeeded": DiveCasesScript.used_apply_frames_succeeded,
			"used_apply_frames": DiveCasesScript.used_apply_frames,
			"used_step_fixed": DiveCasesScript.used_step_fixed,
			"used_parse_input_event": DiveCasesScript.used_parse_input_event,
			"used_action_press": DiveCasesScript.used_action_press,
		},
	}
	_write_json(ev.path_join("outcomes.json"), outcomes)
	_write_json(ev.path_join("snapshot_start.json"), DiveCasesScript.snapshot_start)
	_write_json(ev.path_join("snapshot_end.json"), DiveCasesScript.snapshot_end)
	_write_json(ev.path_join("state_hashes.json"), {
		"replay": DiveCasesScript.outcome_replay,
		"seed": SEED,
		"map_id": MAP_ID,
		"mode": MODE,
	})
	var events_path: String = ev.path_join("events.jsonl")
	var ef: FileAccess = FileAccess.open(events_path, FileAccess.WRITE)
	if ef != null:
		var events: Array = DiveCasesScript.events_end
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
				print("HH_VF_DIVE SCREENSHOT_END missing viewport texture")
			else:
				var img: Image = tex.get_image()
				if img == null:
					print("HH_VF_DIVE SCREENSHOT_END get_image null")
				else:
					var shot: String = ev.path_join("screens").path_join("dive_kick_%dx%d.png" % [
						int(vis.size.x), int(vis.size.y)
					])
					var err: Error = img.save_png(shot)
					print("HH_VF_DIVE SCREENSHOT_END err=%d path=%s" % [int(err), shot])
	var run_partial: Dictionary = {
		"schema": "vault-fighters.vf2-wp4.run.v1",
		"run_id": RUN_ID,
		"command_id": COMMAND_ID,
		"wp": "VF2-WP4",
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
		"epsilon": Locomotion.epsilon(),
		"godot": Engine.get_version_info(),
		"os_name": OS.get_name(),
		"viewport": {"w": vis.size.x, "h": vis.size.y},
		"outcomes": {
			"DIVE": str(DiveCasesScript.outcome_dive.get("verdict", "unproven")),
			"KICK": str(DiveCasesScript.outcome_kick.get("verdict", "unproven")),
			"TACKLE": str(DiveCasesScript.outcome_tackle.get("verdict", "unproven")),
			"FALL": str(DiveCasesScript.outcome_fall.get("verdict", "unproven")),
			"PIT": str(DiveCasesScript.outcome_pit.get("verdict", "unproven")),
			"DODGE": str(DiveCasesScript.outcome_dodge.get("verdict", "unproven")),
			"INVULN": str(DiveCasesScript.outcome_invuln.get("verdict", "unproven")),
			"DIST": str(DiveCasesScript.outcome_dist.get("verdict", "unproven")),
			"MAPS": str(DiveCasesScript.outcome_maps.get("verdict", "unproven")),
			"LIVE": str(DiveCasesScript.outcome_live.get("verdict", "unproven")),
			"REPLAY": str(DiveCasesScript.outcome_replay.get("verdict", "unproven")),
			"USED_APPLY_FRAMES": DiveCasesScript.used_apply_frames,
			"USED_APPLY_ATTEMPTED": DiveCasesScript.used_apply_frames_attempted,
			"USED_APPLY_SUCCEEDED": DiveCasesScript.used_apply_frames_succeeded,
		},
		"fail_count": _fails.size(),
	}
	_write_json(ev.path_join("run_partial.json"), run_partial)
	print("HH_VF_DIVE EVIDENCE_DIR=%s" % ev)


func _write_json(path: String, data: Variant) -> void:
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		print("HH_VF_DIVE EVIDENCE_WRITE_FAIL %s" % path)
		return
	f.store_string(JSON.stringify(data, "\t"))
	f.close()

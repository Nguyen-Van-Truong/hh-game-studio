extends SceneTree

const RUN_ID := "VF2WP5-20260829-ASIA-SAIGON-03"
const COMMAND_ID := "cmd.vf2-wp5.ladder-ledge.3"
const SEED := 1
const MODE := "vs2"
const MAP_ID := "fx_ladder"

const TraversalCasesScript: GDScript = preload("res://tests/traversal_cases.gd")

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
	var errors: PackedStringArray = await TraversalCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	var ladder: String = str(TraversalCasesScript.outcome_ladder.get("verdict", "unproven"))
	var ledge: String = str(TraversalCasesScript.outcome_ledge.get("verdict", "unproven"))
	var drop: String = str(TraversalCasesScript.outcome_drop.get("verdict", "unproven"))
	var block: String = str(TraversalCasesScript.outcome_block.get("verdict", "unproven"))
	var dirs: String = str(TraversalCasesScript.outcome_dirs.get("verdict", "unproven"))
	var maps: String = str(TraversalCasesScript.outcome_maps.get("verdict", "unproven"))
	var stuck: String = str(TraversalCasesScript.outcome_stuck.get("verdict", "unproven"))
	var contact: String = str(TraversalCasesScript.outcome_contact.get("verdict", "unproven"))
	var live: String = str(TraversalCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(TraversalCasesScript.outcome_replay.get("verdict", "unproven"))
	if ladder != "pass":
		_fail("LADDER structured outcome is %s" % ladder)
	if ledge != "pass":
		_fail("LEDGE structured outcome is %s" % ledge)
	if drop != "pass":
		_fail("DROP structured outcome is %s" % drop)
	if block != "pass":
		_fail("BLOCK structured outcome is %s" % block)
	if dirs != "pass":
		_fail("DIRS structured outcome is %s" % dirs)
	if maps != "fixtures_only":
		_fail("MAPS structured outcome is %s (stage maps not claimed)" % maps)
	if stuck != "pass":
		_fail("STUCK structured outcome is %s" % stuck)
	if contact != "pass":
		_fail("CONTACT structured outcome is %s" % contact)
	if live != "pass":
		_fail("LIVE structured outcome is %s" % live)
	if replay != "match":
		_fail("REPLAY structured outcome is %s" % replay)
	var ended_at: String = _iso_local()
	print("HH_VF_TRAV run_id=%s" % RUN_ID)
	print("HH_VF_TRAV command_id=%s" % COMMAND_ID)
	print("HH_VF_TRAV DISPLAY=%s" % DisplayServer.get_name())
	print("HH_VF_TRAV SEED=%d MAP=%s MODE=%s" % [SEED, MAP_ID, MODE])
	print("HH_VF_TRAV STARTED_AT=%s ENDED_AT=%s" % [_started_at, ended_at])
	print(
		"HH_VF_TRAV USED_STEP_FIXED=%d USED_APPLY_FRAMES=%d USED_APPLY_ATTEMPTED=%d USED_APPLY_SUCCEEDED=%d USED_PARSE_INPUT_EVENT=%d USED_ACTION_PRESS=%d"
		% [
			TraversalCasesScript.used_step_fixed,
			TraversalCasesScript.used_apply_frames,
			TraversalCasesScript.used_apply_frames_attempted,
			TraversalCasesScript.used_apply_frames_succeeded,
			TraversalCasesScript.used_parse_input_event,
			TraversalCasesScript.used_action_press
		]
	)
	print("HH_VF_TRAV LADDER=%s LADDER_SOURCE=outcome_ladder" % ladder)
	print("HH_VF_TRAV LEDGE=%s LEDGE_SOURCE=outcome_ledge" % ledge)
	print("HH_VF_TRAV DROP=%s DROP_SOURCE=outcome_drop" % drop)
	print("HH_VF_TRAV BLOCK=%s BLOCK_SOURCE=outcome_block" % block)
	print("HH_VF_TRAV DIRS=%s DIRS_SOURCE=outcome_dirs" % dirs)
	print("HH_VF_TRAV MAPS=%s MAPS_SOURCE=outcome_maps STAGE_NAV=not_claimed" % maps)
	print("HH_VF_TRAV STUCK=%s STUCK_SOURCE=outcome_stuck" % stuck)
	print("HH_VF_TRAV CONTACT=%s CONTACT_SOURCE=outcome_contact" % contact)
	print("HH_VF_TRAV LIVE=%s LIVE_SOURCE=outcome_live" % live)
	print("HH_VF_TRAV REPLAY=%s REPLAY_SOURCE=outcome_replay" % replay)
	print("HH_VF_TRAV HOLD_AIM=assumption SPRINT=assumption ROLL=assumption DIVE=assumption KICK=assumption FALL=assumption LADDER=assumption LEDGE=assumption DROP=assumption ROLL_DIVE=unavailable CLOCK=RL-SIM-FIXED-60")
	await process_frame
	await process_frame
	_write_evidence(app, ended_at)
	if _fails.is_empty():
		print("PASS: Vault Fighters ladder ledge traversal")
	else:
		print("FAIL: Vault Fighters ladder ledge traversal")
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
		"ladder": TraversalCasesScript.outcome_ladder,
		"ledge": TraversalCasesScript.outcome_ledge,
		"drop": TraversalCasesScript.outcome_drop,
		"block": TraversalCasesScript.outcome_block,
		"dirs": TraversalCasesScript.outcome_dirs,
		"maps": TraversalCasesScript.outcome_maps,
		"stuck": TraversalCasesScript.outcome_stuck,
		"contact": TraversalCasesScript.outcome_contact,
		"live": TraversalCasesScript.outcome_live,
		"replay": TraversalCasesScript.outcome_replay,
		"apply": {
			"attempted": TraversalCasesScript.used_apply_frames_attempted,
			"succeeded": TraversalCasesScript.used_apply_frames_succeeded,
			"used_apply_frames": TraversalCasesScript.used_apply_frames,
			"used_step_fixed": TraversalCasesScript.used_step_fixed,
			"used_parse_input_event": TraversalCasesScript.used_parse_input_event,
			"used_action_press": TraversalCasesScript.used_action_press,
		},
	}
	_write_json(ev.path_join("outcomes.json"), outcomes)
	_write_json(ev.path_join("snapshot_start.json"), TraversalCasesScript.snapshot_start)
	_write_json(ev.path_join("snapshot_end.json"), TraversalCasesScript.snapshot_end)
	_write_json(ev.path_join("state_hashes.json"), {
		"replay": TraversalCasesScript.outcome_replay,
		"seed": SEED,
		"map_id": MAP_ID,
		"mode": MODE,
	})
	var events_path: String = ev.path_join("events.jsonl")
	var ef: FileAccess = FileAccess.open(events_path, FileAccess.WRITE)
	if ef != null:
		var events: Array = TraversalCasesScript.events_all
		if events.is_empty():
			events = TraversalCasesScript.events_end
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
				print("HH_VF_TRAV SCREENSHOT_END missing viewport texture")
			else:
				var img: Image = tex.get_image()
				if img == null:
					print("HH_VF_TRAV SCREENSHOT_END get_image null")
				else:
					var shot: String = ev.path_join("screens").path_join("traverse_%dx%d.png" % [
						int(vis.size.x), int(vis.size.y)
					])
					var err: Error = img.save_png(shot)
					print("HH_VF_TRAV SCREENSHOT_END err=%d path=%s" % [int(err), shot])
	var run_partial: Dictionary = {
		"schema": "vault-fighters.vf2-wp5.run.v1",
		"run_id": RUN_ID,
		"command_id": COMMAND_ID,
		"wp": "VF2-WP5",
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
			"LADDER": str(TraversalCasesScript.outcome_ladder.get("verdict", "unproven")),
			"LEDGE": str(TraversalCasesScript.outcome_ledge.get("verdict", "unproven")),
			"DROP": str(TraversalCasesScript.outcome_drop.get("verdict", "unproven")),
			"BLOCK": str(TraversalCasesScript.outcome_block.get("verdict", "unproven")),
			"DIRS": str(TraversalCasesScript.outcome_dirs.get("verdict", "unproven")),
			"MAPS": str(TraversalCasesScript.outcome_maps.get("verdict", "unproven")),
			"STUCK": str(TraversalCasesScript.outcome_stuck.get("verdict", "unproven")),
			"CONTACT": str(TraversalCasesScript.outcome_contact.get("verdict", "unproven")),
			"LIVE": str(TraversalCasesScript.outcome_live.get("verdict", "unproven")),
			"REPLAY": str(TraversalCasesScript.outcome_replay.get("verdict", "unproven")),
			"USED_APPLY_FRAMES": TraversalCasesScript.used_apply_frames,
			"USED_APPLY_ATTEMPTED": TraversalCasesScript.used_apply_frames_attempted,
			"USED_APPLY_SUCCEEDED": TraversalCasesScript.used_apply_frames_succeeded,
		},
		"fail_count": _fails.size(),
	}
	_write_json(ev.path_join("run_partial.json"), run_partial)
	print("HH_VF_TRAV EVIDENCE_DIR=%s" % ev)


func _write_json(path: String, data: Variant) -> void:
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		print("HH_VF_TRAV EVIDENCE_WRITE_FAIL %s" % path)
		return
	f.store_string(JSON.stringify(data, "\t"))
	f.close()

extends SceneTree

const RUN_ID := "VF4WP1-20260829-ASIA-SAIGON-01"
const COMMAND_ID := "cmd.vf4-wp1.world.1"
const SEED := 7
const MODE := "vs2"
const MAP_ID := "fx_world_open"

const WorldCasesScript: GDScript = preload("res://tests/world_cases.gd")

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
	var errors: PackedStringArray = await WorldCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	var schema: String = str(WorldCasesScript.outcome_schema.get("verdict", "unproven"))
	var layers: String = str(WorldCasesScript.outcome_layers.get("verdict", "unproven"))
	var spawn: String = str(WorldCasesScript.outcome_spawn.get("verdict", "unproven"))
	var hashv: String = str(WorldCasesScript.outcome_hash.get("verdict", "unproven"))
	var orphan: String = str(WorldCasesScript.outcome_orphan.get("verdict", "unproven"))
	var pathv: String = str(WorldCasesScript.outcome_path.get("verdict", "unproven"))
	var present: String = str(WorldCasesScript.outcome_present.get("verdict", "unproven"))
	var author: String = str(WorldCasesScript.outcome_author.get("verdict", "unproven"))
	var data: String = str(WorldCasesScript.outcome_data.get("verdict", "unproven"))
	var live: String = str(WorldCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(WorldCasesScript.outcome_replay.get("verdict", "unproven"))
	if schema != "pass":
		_fail("SCHEMA structured outcome is %s" % schema)
	if layers != "pass":
		_fail("LAYERS structured outcome is %s" % layers)
	if spawn != "pass":
		_fail("SPAWN structured outcome is %s" % spawn)
	if hashv != "pass":
		_fail("HASH structured outcome is %s" % hashv)
	if orphan != "pass":
		_fail("ORPHAN structured outcome is %s" % orphan)
	if pathv != "pass":
		_fail("PATH structured outcome is %s" % pathv)
	if present != "pass":
		_fail("PRESENT structured outcome is %s" % present)
	if author != "pass":
		_fail("AUTHOR structured outcome is %s" % author)
	if data != "pass":
		_fail("DATA structured outcome is %s" % data)
	if live != "pass":
		_fail("LIVE structured outcome is %s" % live)
	if replay != "match":
		_fail("REPLAY structured outcome is %s" % replay)
	var ended_at: String = _iso_local()
	print("HH_VF_WORLD run_id=%s" % RUN_ID)
	print("HH_VF_WORLD command_id=%s" % COMMAND_ID)
	print("HH_VF_WORLD DISPLAY=%s" % DisplayServer.get_name())
	print("HH_VF_WORLD SEED=%d MAP=%s MODE=%s" % [SEED, MAP_ID, MODE])
	print("HH_VF_WORLD STARTED_AT=%s ENDED_AT=%s" % [_started_at, ended_at])
	print(
		"HH_VF_WORLD USED_STEP_FIXED=%d USED_APPLY_FRAMES=%d USED_APPLY_ATTEMPTED=%d USED_APPLY_SUCCEEDED=%d USED_PARSE_INPUT_EVENT=%d USED_ACTION_PRESS=%d"
		% [
			WorldCasesScript.used_step_fixed,
			WorldCasesScript.used_apply_frames,
			WorldCasesScript.used_apply_frames_attempted,
			WorldCasesScript.used_apply_frames_succeeded,
			WorldCasesScript.used_parse_input_event,
			WorldCasesScript.used_action_press
		]
	)
	print("HH_VF_WORLD SCHEMA=%s SCHEMA_SOURCE=outcome_schema" % schema)
	print("HH_VF_WORLD LAYERS=%s LAYERS_SOURCE=outcome_layers" % layers)
	print("HH_VF_WORLD SPAWN=%s SPAWN_SOURCE=outcome_spawn" % spawn)
	print("HH_VF_WORLD HASH=%s HASH_SOURCE=outcome_hash" % hashv)
	print("HH_VF_WORLD ORPHAN=%s ORPHAN_SOURCE=outcome_orphan" % orphan)
	print("HH_VF_WORLD PATH=%s PATH_SOURCE=outcome_path" % pathv)
	print("HH_VF_WORLD PRESENT=%s PRESENT_SOURCE=outcome_present" % present)
	print("HH_VF_WORLD AUTHOR=%s AUTHOR_SOURCE=outcome_author" % author)
	print("HH_VF_WORLD DATA=%s DATA_SOURCE=outcome_data" % data)
	print("HH_VF_WORLD LIVE=%s LIVE_SOURCE=outcome_live" % live)
	print("HH_VF_WORLD REPLAY=%s REPLAY_SOURCE=outcome_replay" % replay)
	print("HH_VF_WORLD SCHEMA_CLASS=assumption LAYERS=assumption OWN=assumption BREAK=assumption EXPL=assumption NADE_PROP=deferred HOLD_AIM=assumption ROLL_DIVE=unavailable CLOCK=RL-SIM-FIXED-60")
	await process_frame
	await process_frame
	_write_evidence(app, ended_at)
	if _fails.is_empty():
		print("PASS: Vault Fighters world prop schema")
	else:
		print("FAIL: Vault Fighters world prop schema")
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
		"schema": WorldCasesScript.outcome_schema,
		"layers": WorldCasesScript.outcome_layers,
		"spawn": WorldCasesScript.outcome_spawn,
		"hash": WorldCasesScript.outcome_hash,
		"orphan": WorldCasesScript.outcome_orphan,
		"path": WorldCasesScript.outcome_path,
		"present": WorldCasesScript.outcome_present,
		"author": WorldCasesScript.outcome_author,
		"data": WorldCasesScript.outcome_data,
		"live": WorldCasesScript.outcome_live,
		"replay": WorldCasesScript.outcome_replay,
		"apply": {
			"attempted": WorldCasesScript.used_apply_frames_attempted,
			"succeeded": WorldCasesScript.used_apply_frames_succeeded,
			"used_apply_frames": WorldCasesScript.used_apply_frames,
			"used_step_fixed": WorldCasesScript.used_step_fixed,
			"used_parse_input_event": WorldCasesScript.used_parse_input_event,
			"used_action_press": WorldCasesScript.used_action_press,
		},
	}
	_write_json(ev.path_join("outcomes.json"), outcomes)
	_write_json(ev.path_join("snapshot_start.json"), WorldCasesScript.snapshot_start)
	_write_json(ev.path_join("snapshot_end.json"), WorldCasesScript.snapshot_end)
	_write_json(ev.path_join("state_hashes.json"), {
		"replay": WorldCasesScript.outcome_replay,
		"hash": WorldCasesScript.outcome_hash,
		"seed": SEED,
		"map_id": MAP_ID,
		"mode": MODE,
	})
	var events_path: String = ev.path_join("events.jsonl")
	var ef: FileAccess = FileAccess.open(events_path, FileAccess.WRITE)
	if ef != null:
		var events: Array = WorldCasesScript.events_all
		if events.is_empty():
			events = WorldCasesScript.events_end
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
				print("HH_VF_WORLD SCREENSHOT_END missing viewport texture")
			else:
				var img: Image = tex.get_image()
				if img == null:
					print("HH_VF_WORLD SCREENSHOT_END get_image null")
				else:
					var shot: String = ev.path_join("screens").path_join("world_%dx%d.png" % [
						int(vis.size.x), int(vis.size.y)
					])
					var err: Error = img.save_png(shot)
					print("HH_VF_WORLD SCREENSHOT_END err=%d path=%s" % [int(err), shot])
	var run_partial: Dictionary = {
		"schema": "vault-fighters.vf4-wp1.run.v1",
		"run_id": RUN_ID,
		"command_id": COMMAND_ID,
		"wp": "VF4-WP1",
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
			"SCHEMA": schema_v(WorldCasesScript.outcome_schema),
			"LAYERS": schema_v(WorldCasesScript.outcome_layers),
			"SPAWN": schema_v(WorldCasesScript.outcome_spawn),
			"HASH": schema_v(WorldCasesScript.outcome_hash),
			"ORPHAN": schema_v(WorldCasesScript.outcome_orphan),
			"PATH": schema_v(WorldCasesScript.outcome_path),
			"PRESENT": schema_v(WorldCasesScript.outcome_present),
			"AUTHOR": schema_v(WorldCasesScript.outcome_author),
			"DATA": schema_v(WorldCasesScript.outcome_data),
			"LIVE": schema_v(WorldCasesScript.outcome_live),
			"REPLAY": schema_v(WorldCasesScript.outcome_replay),
			"USED_APPLY_FRAMES": WorldCasesScript.used_apply_frames,
			"USED_APPLY_ATTEMPTED": WorldCasesScript.used_apply_frames_attempted,
			"USED_APPLY_SUCCEEDED": WorldCasesScript.used_apply_frames_succeeded,
		},
		"fail_count": _fails.size(),
	}
	_write_json(ev.path_join("run_partial.json"), run_partial)
	print("HH_VF_WORLD EVIDENCE_DIR=%s" % ev)


func schema_v(row: Dictionary) -> String:
	return str(row.get("verdict", "unproven"))


func _write_json(path: String, data: Variant) -> void:
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		print("HH_VF_WORLD EVIDENCE_WRITE_FAIL %s" % path)
		return
	f.store_string(JSON.stringify(data, "\t"))
	f.close()

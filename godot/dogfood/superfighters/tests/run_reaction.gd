extends SceneTree

const RUN_ID := "VF3WP2-20260829-ASIA-SAIGON-01"
const COMMAND_ID := "cmd.vf3-wp2.knock-disarm.1"
const SEED := 7
const MODE := "vs2"
const MAP_ID := "fx_melee_close"

const ReactionCasesScript: GDScript = preload("res://tests/reaction_cases.gd")

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
	var errors: PackedStringArray = await ReactionCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	var damage: String = str(ReactionCasesScript.outcome_damage.get("verdict", "unproven"))
	var knock: String = str(ReactionCasesScript.outcome_knock.get("verdict", "unproven"))
	var air: String = str(ReactionCasesScript.outcome_air.get("verdict", "unproven"))
	var down: String = str(ReactionCasesScript.outcome_down.get("verdict", "unproven"))
	var getup: String = str(ReactionCasesScript.outcome_getup.get("verdict", "unproven"))
	var invuln: String = str(ReactionCasesScript.outcome_invuln.get("verdict", "unproven"))
	var chain: String = str(ReactionCasesScript.outcome_chain.get("verdict", "unproven"))
	var disarm: String = str(ReactionCasesScript.outcome_disarm.get("verdict", "unproven"))
	var drop: String = str(ReactionCasesScript.outcome_drop.get("verdict", "unproven"))
	var death: String = str(ReactionCasesScript.outcome_death.get("verdict", "unproven"))
	var events: String = str(ReactionCasesScript.outcome_events.get("verdict", "unproven"))
	var live: String = str(ReactionCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(ReactionCasesScript.outcome_replay.get("verdict", "unproven"))
	if damage != "pass":
		_fail("DAMAGE structured outcome is %s" % damage)
	if knock != "pass":
		_fail("KNOCK structured outcome is %s" % knock)
	if air != "pass":
		_fail("AIR structured outcome is %s" % air)
	if down != "pass":
		_fail("DOWN structured outcome is %s" % down)
	if getup != "pass":
		_fail("GETUP structured outcome is %s" % getup)
	if invuln != "pass":
		_fail("INVULN structured outcome is %s" % invuln)
	if chain != "pass":
		_fail("CHAIN structured outcome is %s" % chain)
	if disarm != "pass":
		_fail("DISARM structured outcome is %s" % disarm)
	if drop != "pass":
		_fail("DROP structured outcome is %s" % drop)
	if death != "pass":
		_fail("DEATH structured outcome is %s" % death)
	if events != "pass":
		_fail("EVENTS structured outcome is %s" % events)
	if live != "pass":
		_fail("LIVE structured outcome is %s" % live)
	if replay != "match":
		_fail("REPLAY structured outcome is %s" % replay)
	var ended_at: String = _iso_local()
	print("HH_VF_REACT run_id=%s" % RUN_ID)
	print("HH_VF_REACT command_id=%s" % COMMAND_ID)
	print("HH_VF_REACT DISPLAY=%s" % DisplayServer.get_name())
	print("HH_VF_REACT SEED=%d MAP=%s MODE=%s" % [SEED, MAP_ID, MODE])
	print("HH_VF_REACT STARTED_AT=%s ENDED_AT=%s" % [_started_at, ended_at])
	print(
		"HH_VF_REACT USED_STEP_FIXED=%d USED_APPLY_FRAMES=%d USED_APPLY_ATTEMPTED=%d USED_APPLY_SUCCEEDED=%d USED_PARSE_INPUT_EVENT=%d USED_ACTION_PRESS=%d"
		% [
			ReactionCasesScript.used_step_fixed,
			ReactionCasesScript.used_apply_frames,
			ReactionCasesScript.used_apply_frames_attempted,
			ReactionCasesScript.used_apply_frames_succeeded,
			ReactionCasesScript.used_parse_input_event,
			ReactionCasesScript.used_action_press
		]
	)
	print("HH_VF_REACT DAMAGE=%s DAMAGE_SOURCE=outcome_damage" % damage)
	print("HH_VF_REACT KNOCK=%s KNOCK_SOURCE=outcome_knock" % knock)
	print("HH_VF_REACT AIR=%s AIR_SOURCE=outcome_air" % air)
	print("HH_VF_REACT DOWN=%s DOWN_SOURCE=outcome_down" % down)
	print("HH_VF_REACT GETUP=%s GETUP_SOURCE=outcome_getup" % getup)
	print("HH_VF_REACT INVULN=%s INVULN_SOURCE=outcome_invuln" % invuln)
	print("HH_VF_REACT CHAIN=%s CHAIN_SOURCE=outcome_chain" % chain)
	print("HH_VF_REACT DISARM=%s DISARM_SOURCE=outcome_disarm" % disarm)
	print("HH_VF_REACT DROP=%s DROP_SOURCE=outcome_drop" % drop)
	print("HH_VF_REACT DEATH=%s DEATH_SOURCE=outcome_death" % death)
	print("HH_VF_REACT EVENTS=%s EVENTS_SOURCE=outcome_events" % events)
	print("HH_VF_REACT LIVE=%s LIVE_SOURCE=outcome_live" % live)
	print("HH_VF_REACT REPLAY=%s REPLAY_SOURCE=outcome_replay" % replay)
	print("HH_VF_REACT KNOCK=assumption DOWN=assumption INVULN=assumption DISARM=assumption HOLD_AIM=assumption ROLL_DIVE=unavailable CLOCK=RL-SIM-FIXED-60")
	await process_frame
	await process_frame
	_write_evidence(app, ended_at)
	if _fails.is_empty():
		print("PASS: Vault Fighters knockback knockdown disarm")
	else:
		print("FAIL: Vault Fighters knockback knockdown disarm")
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
		"damage": ReactionCasesScript.outcome_damage,
		"knock": ReactionCasesScript.outcome_knock,
		"air": ReactionCasesScript.outcome_air,
		"down": ReactionCasesScript.outcome_down,
		"getup": ReactionCasesScript.outcome_getup,
		"invuln": ReactionCasesScript.outcome_invuln,
		"chain": ReactionCasesScript.outcome_chain,
		"disarm": ReactionCasesScript.outcome_disarm,
		"drop": ReactionCasesScript.outcome_drop,
		"death": ReactionCasesScript.outcome_death,
		"events": ReactionCasesScript.outcome_events,
		"live": ReactionCasesScript.outcome_live,
		"replay": ReactionCasesScript.outcome_replay,
		"apply": {
			"attempted": ReactionCasesScript.used_apply_frames_attempted,
			"succeeded": ReactionCasesScript.used_apply_frames_succeeded,
			"used_apply_frames": ReactionCasesScript.used_apply_frames,
			"used_step_fixed": ReactionCasesScript.used_step_fixed,
			"used_parse_input_event": ReactionCasesScript.used_parse_input_event,
			"used_action_press": ReactionCasesScript.used_action_press,
		},
	}
	_write_json(ev.path_join("outcomes.json"), outcomes)
	_write_json(ev.path_join("snapshot_start.json"), ReactionCasesScript.snapshot_start)
	_write_json(ev.path_join("snapshot_end.json"), ReactionCasesScript.snapshot_end)
	_write_json(ev.path_join("state_hashes.json"), {
		"replay": ReactionCasesScript.outcome_replay,
		"seed": SEED,
		"map_id": MAP_ID,
		"mode": MODE,
	})
	var events_path: String = ev.path_join("events.jsonl")
	var ef: FileAccess = FileAccess.open(events_path, FileAccess.WRITE)
	if ef != null:
		var events: Array = ReactionCasesScript.events_all
		if events.is_empty():
			events = ReactionCasesScript.events_end
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
				print("HH_VF_REACT SCREENSHOT_END missing viewport texture")
			else:
				var img: Image = tex.get_image()
				if img == null:
					print("HH_VF_REACT SCREENSHOT_END get_image null")
				else:
					var shot: String = ev.path_join("screens").path_join("reaction_%dx%d.png" % [
						int(vis.size.x), int(vis.size.y)
					])
					var err: Error = img.save_png(shot)
					print("HH_VF_REACT SCREENSHOT_END err=%d path=%s" % [int(err), shot])
	var run_partial: Dictionary = {
		"schema": "vault-fighters.vf3-wp2.run.v1",
		"run_id": RUN_ID,
		"command_id": COMMAND_ID,
		"wp": "VF3-WP2",
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
			"DAMAGE": str(ReactionCasesScript.outcome_damage.get("verdict", "unproven")),
			"KNOCK": str(ReactionCasesScript.outcome_knock.get("verdict", "unproven")),
			"AIR": str(ReactionCasesScript.outcome_air.get("verdict", "unproven")),
			"DOWN": str(ReactionCasesScript.outcome_down.get("verdict", "unproven")),
			"GETUP": str(ReactionCasesScript.outcome_getup.get("verdict", "unproven")),
			"INVULN": str(ReactionCasesScript.outcome_invuln.get("verdict", "unproven")),
			"CHAIN": str(ReactionCasesScript.outcome_chain.get("verdict", "unproven")),
			"DISARM": str(ReactionCasesScript.outcome_disarm.get("verdict", "unproven")),
			"DROP": str(ReactionCasesScript.outcome_drop.get("verdict", "unproven")),
			"DEATH": str(ReactionCasesScript.outcome_death.get("verdict", "unproven")),
			"EVENTS": str(ReactionCasesScript.outcome_events.get("verdict", "unproven")),
			"LIVE": str(ReactionCasesScript.outcome_live.get("verdict", "unproven")),
			"REPLAY": str(ReactionCasesScript.outcome_replay.get("verdict", "unproven")),
			"USED_APPLY_FRAMES": ReactionCasesScript.used_apply_frames,
			"USED_APPLY_ATTEMPTED": ReactionCasesScript.used_apply_frames_attempted,
			"USED_APPLY_SUCCEEDED": ReactionCasesScript.used_apply_frames_succeeded,
		},
		"fail_count": _fails.size(),
	}
	_write_json(ev.path_join("run_partial.json"), run_partial)
	print("HH_VF_REACT EVIDENCE_DIR=%s" % ev)


func _write_json(path: String, data: Variant) -> void:
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		print("HH_VF_REACT EVIDENCE_WRITE_FAIL %s" % path)
		return
	f.store_string(JSON.stringify(data, "\t"))
	f.close()

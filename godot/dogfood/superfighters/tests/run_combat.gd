extends SceneTree

const RUN_ID := "VF3WP1-20260829-ASIA-SAIGON-01"
const COMMAND_ID := "cmd.vf3-wp1.melee-phases.1"
const SEED := 7
const MODE := "vs2"
const MAP_ID := "fx_melee_close"

const CombatCasesScript: GDScript = preload("res://tests/combat_cases.gd")

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
	var errors: PackedStringArray = await CombatCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	var hit: String = str(CombatCasesScript.outcome_hit.get("verdict", "unproven"))
	var miss: String = str(CombatCasesScript.outcome_miss.get("verdict", "unproven"))
	var behind: String = str(CombatCasesScript.outcome_behind.get("verdict", "unproven"))
	var above: String = str(CombatCasesScript.outcome_above.get("verdict", "unproven"))
	var below: String = str(CombatCasesScript.outcome_below.get("verdict", "unproven"))
	var once: String = str(CombatCasesScript.outcome_once.get("verdict", "unproven"))
	var snap: String = str(CombatCasesScript.outcome_snap.get("verdict", "unproven"))
	var pause: String = str(CombatCasesScript.outcome_pause.get("verdict", "unproven"))
	var live: String = str(CombatCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(CombatCasesScript.outcome_replay.get("verdict", "unproven"))
	var phases: String = str(CombatCasesScript.outcome_phases.get("verdict", "unproven"))
	var reach: String = str(CombatCasesScript.outcome_reach.get("verdict", "unproven"))
	var ff: String = str(CombatCasesScript.outcome_ff.get("verdict", "unproven"))
	var hitstop: String = str(CombatCasesScript.outcome_hitstop.get("verdict", "unproven"))
	var crouch: String = str(CombatCasesScript.outcome_crouch.get("verdict", "unproven"))
	var kick: String = str(CombatCasesScript.outcome_kick.get("verdict", "unproven"))
	if hit != "pass":
		_fail("HIT structured outcome is %s" % hit)
	if miss != "pass":
		_fail("MISS structured outcome is %s" % miss)
	if behind != "pass":
		_fail("BEHIND structured outcome is %s" % behind)
	if above != "pass":
		_fail("ABOVE structured outcome is %s" % above)
	if below != "pass":
		_fail("BELOW structured outcome is %s" % below)
	if once != "pass":
		_fail("ONCE structured outcome is %s" % once)
	if snap != "pass":
		_fail("SNAP structured outcome is %s" % snap)
	if pause != "pass":
		_fail("PAUSE structured outcome is %s" % pause)
	if live != "pass":
		_fail("LIVE structured outcome is %s" % live)
	if replay != "match":
		_fail("REPLAY structured outcome is %s" % replay)
	if phases != "pass":
		_fail("PHASES structured outcome is %s" % phases)
	if reach != "pass":
		_fail("REACH structured outcome is %s" % reach)
	if ff != "pass":
		_fail("FF structured outcome is %s" % ff)
	if hitstop != "pass":
		_fail("HITSTOP structured outcome is %s" % hitstop)
	if crouch != "pass":
		_fail("CROUCH structured outcome is %s" % crouch)
	if kick != "pass":
		_fail("KICK structured outcome is %s" % kick)
	var ended_at: String = _iso_local()
	print("HH_VF_MELEE run_id=%s" % RUN_ID)
	print("HH_VF_MELEE command_id=%s" % COMMAND_ID)
	print("HH_VF_MELEE DISPLAY=%s" % DisplayServer.get_name())
	print("HH_VF_MELEE SEED=%d MAP=%s MODE=%s" % [SEED, MAP_ID, MODE])
	print("HH_VF_MELEE STARTED_AT=%s ENDED_AT=%s" % [_started_at, ended_at])
	print(
		"HH_VF_MELEE USED_STEP_FIXED=%d USED_APPLY_FRAMES=%d USED_APPLY_ATTEMPTED=%d USED_APPLY_SUCCEEDED=%d USED_PARSE_INPUT_EVENT=%d USED_ACTION_PRESS=%d"
		% [
			CombatCasesScript.used_step_fixed,
			CombatCasesScript.used_apply_frames,
			CombatCasesScript.used_apply_frames_attempted,
			CombatCasesScript.used_apply_frames_succeeded,
			CombatCasesScript.used_parse_input_event,
			CombatCasesScript.used_action_press
		]
	)
	print("HH_VF_MELEE HIT=%s HIT_SOURCE=outcome_hit" % hit)
	print("HH_VF_MELEE MISS=%s MISS_SOURCE=outcome_miss" % miss)
	print("HH_VF_MELEE BEHIND=%s BEHIND_SOURCE=outcome_behind" % behind)
	print("HH_VF_MELEE ABOVE=%s ABOVE_SOURCE=outcome_above" % above)
	print("HH_VF_MELEE BELOW=%s BELOW_SOURCE=outcome_below" % below)
	print("HH_VF_MELEE ONCE=%s ONCE_SOURCE=outcome_once" % once)
	print("HH_VF_MELEE SNAP=%s SNAP_SOURCE=outcome_snap" % snap)
	print("HH_VF_MELEE PAUSE=%s PAUSE_SOURCE=outcome_pause" % pause)
	print("HH_VF_MELEE LIVE=%s LIVE_SOURCE=outcome_live" % live)
	print("HH_VF_MELEE REPLAY=%s REPLAY_SOURCE=outcome_replay" % replay)
	print("HH_VF_MELEE PHASES=%s PHASES_SOURCE=outcome_phases" % phases)
	print("HH_VF_MELEE REACH=%s REACH_SOURCE=outcome_reach" % reach)
	print("HH_VF_MELEE FF=%s FF_SOURCE=outcome_ff" % ff)
	print("HH_VF_MELEE HITSTOP=%s HITSTOP_SOURCE=outcome_hitstop" % hitstop)
	print("HH_VF_MELEE CROUCH=%s CROUCH_SOURCE=outcome_crouch" % crouch)
	print("HH_VF_MELEE KICK=%s KICK_SOURCE=outcome_kick" % kick)
	print("HH_VF_MELEE HOLD_AIM=assumption PHASES=assumption HITBOX=assumption FF=assumption HITSTOP=assumption KICK=assumption ROLL_DIVE=unavailable CLOCK=RL-SIM-FIXED-60")
	await process_frame
	await process_frame
	_write_evidence(app, ended_at)
	if _fails.is_empty():
		print("PASS: Vault Fighters melee phases")
	else:
		print("FAIL: Vault Fighters melee phases")
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
		"hit": CombatCasesScript.outcome_hit,
		"miss": CombatCasesScript.outcome_miss,
		"behind": CombatCasesScript.outcome_behind,
		"above": CombatCasesScript.outcome_above,
		"below": CombatCasesScript.outcome_below,
		"once": CombatCasesScript.outcome_once,
		"snap": CombatCasesScript.outcome_snap,
		"pause": CombatCasesScript.outcome_pause,
		"live": CombatCasesScript.outcome_live,
		"replay": CombatCasesScript.outcome_replay,
		"phases": CombatCasesScript.outcome_phases,
		"reach": CombatCasesScript.outcome_reach,
		"ff": CombatCasesScript.outcome_ff,
		"hitstop": CombatCasesScript.outcome_hitstop,
		"crouch": CombatCasesScript.outcome_crouch,
		"kick": CombatCasesScript.outcome_kick,
		"apply": {
			"attempted": CombatCasesScript.used_apply_frames_attempted,
			"succeeded": CombatCasesScript.used_apply_frames_succeeded,
			"used_apply_frames": CombatCasesScript.used_apply_frames,
			"used_step_fixed": CombatCasesScript.used_step_fixed,
			"used_parse_input_event": CombatCasesScript.used_parse_input_event,
			"used_action_press": CombatCasesScript.used_action_press,
		},
	}
	_write_json(ev.path_join("outcomes.json"), outcomes)
	_write_json(ev.path_join("snapshot_start.json"), CombatCasesScript.snapshot_start)
	_write_json(ev.path_join("snapshot_end.json"), CombatCasesScript.snapshot_end)
	_write_json(ev.path_join("state_hashes.json"), {
		"replay": CombatCasesScript.outcome_replay,
		"seed": SEED,
		"map_id": MAP_ID,
		"mode": MODE,
	})
	var events_path: String = ev.path_join("events.jsonl")
	var ef: FileAccess = FileAccess.open(events_path, FileAccess.WRITE)
	if ef != null:
		var events: Array = CombatCasesScript.events_all
		if events.is_empty():
			events = CombatCasesScript.events_end
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
				print("HH_VF_MELEE SCREENSHOT_END missing viewport texture")
			else:
				var img: Image = tex.get_image()
				if img == null:
					print("HH_VF_MELEE SCREENSHOT_END get_image null")
				else:
					var shot: String = ev.path_join("screens").path_join("melee_%dx%d.png" % [
						int(vis.size.x), int(vis.size.y)
					])
					var err: Error = img.save_png(shot)
					print("HH_VF_MELEE SCREENSHOT_END err=%d path=%s" % [int(err), shot])
	var run_partial: Dictionary = {
		"schema": "vault-fighters.vf3-wp1.run.v1",
		"run_id": RUN_ID,
		"command_id": COMMAND_ID,
		"wp": "VF3-WP1",
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
			"HIT": str(CombatCasesScript.outcome_hit.get("verdict", "unproven")),
			"MISS": str(CombatCasesScript.outcome_miss.get("verdict", "unproven")),
			"BEHIND": str(CombatCasesScript.outcome_behind.get("verdict", "unproven")),
			"ABOVE": str(CombatCasesScript.outcome_above.get("verdict", "unproven")),
			"BELOW": str(CombatCasesScript.outcome_below.get("verdict", "unproven")),
			"ONCE": str(CombatCasesScript.outcome_once.get("verdict", "unproven")),
			"SNAP": str(CombatCasesScript.outcome_snap.get("verdict", "unproven")),
			"PAUSE": str(CombatCasesScript.outcome_pause.get("verdict", "unproven")),
			"LIVE": str(CombatCasesScript.outcome_live.get("verdict", "unproven")),
			"REPLAY": str(CombatCasesScript.outcome_replay.get("verdict", "unproven")),
			"PHASES": str(CombatCasesScript.outcome_phases.get("verdict", "unproven")),
			"REACH": str(CombatCasesScript.outcome_reach.get("verdict", "unproven")),
			"FF": str(CombatCasesScript.outcome_ff.get("verdict", "unproven")),
			"HITSTOP": str(CombatCasesScript.outcome_hitstop.get("verdict", "unproven")),
			"CROUCH": str(CombatCasesScript.outcome_crouch.get("verdict", "unproven")),
			"KICK": str(CombatCasesScript.outcome_kick.get("verdict", "unproven")),
			"USED_APPLY_FRAMES": CombatCasesScript.used_apply_frames,
			"USED_APPLY_ATTEMPTED": CombatCasesScript.used_apply_frames_attempted,
			"USED_APPLY_SUCCEEDED": CombatCasesScript.used_apply_frames_succeeded,
		},
		"fail_count": _fails.size(),
	}
	_write_json(ev.path_join("run_partial.json"), run_partial)
	print("HH_VF_MELEE EVIDENCE_DIR=%s" % ev)


func _write_json(path: String, data: Variant) -> void:
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		print("HH_VF_MELEE EVIDENCE_WRITE_FAIL %s" % path)
		return
	f.store_string(JSON.stringify(data, "\t"))
	f.close()

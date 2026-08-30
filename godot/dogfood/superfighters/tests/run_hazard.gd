extends SceneTree

const RUN_ID := "VF4WP3-20260830-ASIA-SAIGON-02"
const COMMAND_ID := "cmd.vf4-wp3.hazard.2"
const SEED := 7
const MODE := "vs2"
const MAP_ID := "fx_hazard_yard"

const HazardCasesScript: GDScript = preload("res://tests/hazard_cases.gd")

var _fails: PackedStringArray = PackedStringArray()
var _started_at: String = ""
var _started_unix: float = 0.0
var _setup_shot: String = ""


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
	await _draw_ready()
	_setup_shot = _maybe_shot(app, "hazard_setup")
	var errors: PackedStringArray = await HazardCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	var data: String = str(HazardCasesScript.outcome_data.get("verdict", "unproven"))
	var chain: String = str(HazardCasesScript.outcome_chain.get("verdict", "unproven"))
	var fire: String = str(HazardCasesScript.outcome_fire.get("verdict", "unproven"))
	var cleanup: String = str(HazardCasesScript.outcome_cleanup.get("verdict", "unproven"))
	var roll: String = str(HazardCasesScript.outcome_roll.get("verdict", "unproven"))
	var dup: String = str(HazardCasesScript.outcome_dup.get("verdict", "unproven"))
	var vfx: String = str(HazardCasesScript.outcome_vfx.get("verdict", "unproven"))
	var hang: String = str(HazardCasesScript.outcome_hang.get("verdict", "unproven"))
	var live: String = str(HazardCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(HazardCasesScript.outcome_replay.get("verdict", "unproven"))
	if data != "pass":
		_fail("DATA structured outcome is %s" % data)
	if chain != "pass":
		_fail("CHAIN structured outcome is %s" % chain)
	if fire != "pass":
		_fail("FIRE structured outcome is %s" % fire)
	if cleanup != "pass":
		_fail("CLEANUP structured outcome is %s" % cleanup)
	if roll != "pass":
		_fail("ROLL structured outcome is %s" % roll)
	if dup != "pass":
		_fail("DUP structured outcome is %s" % dup)
	if vfx != "pass":
		_fail("VFX structured outcome is %s" % vfx)
	if hang != "pass":
		_fail("HANG structured outcome is %s" % hang)
	if live != "pass":
		_fail("LIVE structured outcome is %s" % live)
	if replay != "match":
		_fail("REPLAY structured outcome is %s" % replay)
	var ended_at: String = _iso_local()
	print("HH_VF_HAZARD run_id=%s" % RUN_ID)
	print("HH_VF_HAZARD command_id=%s" % COMMAND_ID)
	print("HH_VF_HAZARD DISPLAY=%s" % DisplayServer.get_name())
	print("HH_VF_HAZARD SEED=%d MAP=%s MODE=%s" % [SEED, MAP_ID, MODE])
	print("HH_VF_HAZARD STARTED_AT=%s ENDED_AT=%s" % [_started_at, ended_at])
	print(
		"HH_VF_HAZARD USED_STEP_FIXED=%d USED_APPLY_FRAMES=%d USED_APPLY_ATTEMPTED=%d USED_APPLY_SUCCEEDED=%d USED_PARSE_INPUT_EVENT=%d USED_ACTION_PRESS=%d"
		% [
			HazardCasesScript.used_step_fixed,
			HazardCasesScript.used_apply_frames,
			HazardCasesScript.used_apply_frames_attempted,
			HazardCasesScript.used_apply_frames_succeeded,
			HazardCasesScript.used_parse_input_event,
			HazardCasesScript.used_action_press
		]
	)
	print("HH_VF_HAZARD DATA=%s DATA_SOURCE=outcome_data" % data)
	print("HH_VF_HAZARD CHAIN=%s CHAIN_SOURCE=outcome_chain" % chain)
	print("HH_VF_HAZARD FIRE=%s FIRE_SOURCE=outcome_fire" % fire)
	print("HH_VF_HAZARD CLEANUP=%s CLEANUP_SOURCE=outcome_cleanup" % cleanup)
	print("HH_VF_HAZARD ROLL=%s ROLL_SOURCE=outcome_roll" % roll)
	print("HH_VF_HAZARD DUP=%s DUP_SOURCE=outcome_dup" % dup)
	print("HH_VF_HAZARD VFX=%s VFX_SOURCE=outcome_vfx" % vfx)
	print("HH_VF_HAZARD HANG=%s HANG_SOURCE=outcome_hang" % hang)
	print("HH_VF_HAZARD LIVE=%s LIVE_SOURCE=outcome_live" % live)
	print("HH_VF_HAZARD REPLAY=%s REPLAY_SOURCE=outcome_replay" % replay)
	print("HH_VF_HAZARD EXPL_CLASS=assumption CHAIN=assumption FIRE=assumption HANG=assumption EXTINGUISH=roll NADE_PROP=deferred HOLD_AIM=assumption ROLL_DIVE=unavailable CLOCK=RL-SIM-FIXED-60")
	await _write_evidence(app, ended_at, data, chain, fire, cleanup, roll, dup, vfx, hang, live, replay)
	if _fails.is_empty():
		print("PASS: Vault Fighters explosive barrels and fire")
	else:
		print("FAIL: Vault Fighters explosive barrels and fire")
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
		print("HH_VF_HAZARD SCREENSHOT_%s missing viewport texture" % stem)
		return ""
	var img: Image = tex.get_image()
	if img == null:
		print("HH_VF_HAZARD SCREENSHOT_%s get_image null" % stem)
		return ""
	var shot: String = ev.path_join("screens").path_join("%s_%dx%d.png" % [stem, int(vis.size.x), int(vis.size.y)])
	var err: Error = img.save_png(shot)
	print("HH_VF_HAZARD SCREENSHOT_%s err=%d path=%s" % [stem, int(err), shot])
	return shot


func _draw_ready() -> void:
	await process_frame
	await process_frame
	if DisplayServer.get_name() == "headless":
		return
	await RenderingServer.frame_post_draw
	await process_frame
	await RenderingServer.frame_post_draw


func _windowed() -> bool:
	return DisplayServer.get_name() != "headless"


func _apply_held(session: GameSession, ticks: int, held: PackedStringArray) -> void:
	if session == null:
		return
	var n: int = 0
	while n < ticks:
		var frames: Array = []
		var i: int = 0
		while i < session.fighters.size():
			var d: Dictionary = InputActions.empty_frame(session.clock.tick, i)
			if i == 0:
				d["held"] = held
			frames.append(InputFrame.from_dict(d))
			i += 1
		session.apply_frames(frames)
		n += 1


func _apply_edge(session: GameSession, pressed: PackedStringArray, released: PackedStringArray) -> void:
	if session == null:
		return
	var frames: Array = []
	var i: int = 0
	while i < session.fighters.size():
		var d: Dictionary = InputActions.empty_frame(session.clock.tick, i)
		if i == 0:
			d["pressed"] = pressed
			d["released"] = released
		frames.append(InputFrame.from_dict(d))
		i += 1
	session.apply_frames(frames)


func _pistol_burst(session: GameSession) -> void:
	_apply_held(session, 6, PackedStringArray(["fire"]))
	_apply_edge(session, PackedStringArray(), PackedStringArray(["fire"]))


func _owner(session: GameSession) -> RefCounted:
	if session == null:
		return null
	return session.world_owner


func _find_prop(session: GameSession, pid: String) -> Node2D:
	if _owner(session) == null:
		return null
	return _owner(session).call("find_by_id", pid) as Node2D


func _stage_chain_blast(app: App) -> Dictionary:
	var row: Dictionary = {"explodes": -1, "vfx_live": -1, "a_dead": 0}
	if app == null:
		return row
	app.start_fight("vs2", "fx_hazard_chain", 0)
	await _draw_ready()
	var session: GameSession = app.session
	_pistol_burst(session)
	var n: int = 0
	while n < 24:
		var explodes: int = int(_owner(session).get("explode_events")) if _owner(session) != null else 0
		if explodes >= 3:
			break
		_apply_held(session, 1, PackedStringArray())
		n += 1
	await _draw_ready()
	row["explodes"] = int(_owner(session).get("explode_events")) if _owner(session) != null else -1
	row["vfx_live"] = int(_owner(session).call("vfx_live_count")) if _owner(session) != null else -1
	var body_a: Node2D = _find_prop(session, "chain_a")
	row["a_dead"] = 1 if body_a == null or not bool(body_a.get("alive")) else 0
	return row


func _stage_fire_burn(app: App) -> Dictionary:
	var row: Dictionary = {"burning": 0, "hp0": -1.0, "hp1": -1.0, "fire_view": 0}
	if app == null:
		return row
	app.start_fight("vs2", "fx_hazard_fire", 0)
	await _draw_ready()
	var session: GameSession = app.session
	var p1: Fighter = session.player1() if session != null else null
	if p1 == null:
		return row
	row["hp0"] = p1.health
	_pistol_burst(session)
	var n: int = 0
	while n < 48:
		if p1.burning and p1.health < float(row["hp0"]) - 0.01:
			break
		_apply_held(session, 1, PackedStringArray())
		n += 1
	await _draw_ready()
	row["burning"] = 1 if p1.burning else 0
	row["hp1"] = p1.health
	row["fire_view"] = 1 if _owner(session) != null and bool(_owner(session).call("has_fire_view", 0)) else 0
	return row


func _stage_hang_drop(app: App) -> Dictionary:
	var row: Dictionary = {"y0": -1.0, "y1": -1.0, "hanging": 1, "drops": -1}
	if app == null:
		return row
	app.start_fight("vs2", "fx_hazard_chain", 0)
	await _draw_ready()
	var session: GameSession = app.session
	var hang: Node2D = _find_prop(session, "chain_hang")
	row["y0"] = hang.global_position.y if hang != null else -1.0
	_pistol_burst(session)
	var n: int = 0
	while n < 36:
		hang = _find_prop(session, "chain_hang")
		var dropped: bool = hang != null and not bool(hang.get("hanging"))
		var fallen: bool = hang != null and hang.global_position.y > float(row["y0"]) + 2.0
		if dropped and fallen:
			break
		_apply_held(session, 1, PackedStringArray())
		n += 1
	_apply_held(session, 20, PackedStringArray())
	await _draw_ready()
	hang = _find_prop(session, "chain_hang")
	row["y1"] = hang.global_position.y if hang != null else float(row["y0"])
	row["hanging"] = 1 if hang != null and bool(hang.get("hanging")) else 0
	row["drops"] = int(_owner(session).get("drop_events")) if _owner(session) != null else -1
	return row


func _write_evidence(
	app: App, ended_at: String, data: String, chain: String, fire: String, cleanup: String,
	roll: String, dup: String, vfx: String, hang: String, live: String, replay: String
) -> void:
	var ev: String = OS.get_environment("HH_VF_EVIDENCE_DIR")
	if ev == "":
		ev = ProjectSettings.globalize_path("res://.evidence/%s" % RUN_ID)
	DirAccess.make_dir_recursive_absolute(ev)
	DirAccess.make_dir_recursive_absolute(ev.path_join("screens"))
	var chain_row: Dictionary = await _stage_chain_blast(app)
	var chain_shot: String = _maybe_shot(app, "hazard_chain")
	print(
		"HH_VF_HAZARD SHOT_CHAIN explodes=%d vfx_live=%d a_dead=%d path=%s"
		% [int(chain_row.get("explodes", -1)), int(chain_row.get("vfx_live", -1)), int(chain_row.get("a_dead", 0)), chain_shot]
	)
	var fire_row: Dictionary = await _stage_fire_burn(app)
	var fire_shot: String = _maybe_shot(app, "hazard_fire")
	print(
		"HH_VF_HAZARD SHOT_FIRE burning=%d hp0=%s hp1=%s fire_view=%d path=%s"
		% [int(fire_row.get("burning", 0)), str(fire_row.get("hp0", -1)), str(fire_row.get("hp1", -1)), int(fire_row.get("fire_view", 0)), fire_shot]
	)
	var hang_row: Dictionary = await _stage_hang_drop(app)
	var hang_shot: String = _maybe_shot(app, "hazard_hang")
	print(
		"HH_VF_HAZARD SHOT_HANG y0=%s y1=%s hanging=%d drops=%d path=%s"
		% [str(hang_row.get("y0", -1)), str(hang_row.get("y1", -1)), int(hang_row.get("hanging", 1)), int(hang_row.get("drops", -1)), hang_shot]
	)
	if _windowed():
		if int(chain_row.get("explodes", 0)) < 3 or int(chain_row.get("vfx_live", 0)) < 1:
			_fail("DoD chain still must show a drawn blast (explodes>=3 and live VFX)")
		if int(fire_row.get("burning", 0)) != 1 or float(fire_row.get("hp1", 99)) >= float(fire_row.get("hp0", 0)) - 0.01 or int(fire_row.get("fire_view", 0)) != 1:
			_fail("DoD fire still must show burn, HP drop, and fire sprite on Ember Walk")
		if int(hang_row.get("hanging", 1)) != 0 or float(hang_row.get("y1", 0)) <= float(hang_row.get("y0", 0)) + 2.0:
			_fail("DoD hang still must show a dropped container (y changed)")
		if chain_shot == "" or fire_shot == "" or hang_shot == "" or _setup_shot == "":
			_fail("DoD window stills missing setup/chain/fire/hang")
	var outcomes: Dictionary = {
		"data": HazardCasesScript.outcome_data,
		"chain": HazardCasesScript.outcome_chain,
		"fire": HazardCasesScript.outcome_fire,
		"cleanup": HazardCasesScript.outcome_cleanup,
		"roll": HazardCasesScript.outcome_roll,
		"dup": HazardCasesScript.outcome_dup,
		"vfx": HazardCasesScript.outcome_vfx,
		"hang": HazardCasesScript.outcome_hang,
		"live": HazardCasesScript.outcome_live,
		"replay": HazardCasesScript.outcome_replay,
		"apply": {
			"attempted": HazardCasesScript.used_apply_frames_attempted,
			"succeeded": HazardCasesScript.used_apply_frames_succeeded,
			"used_apply_frames": HazardCasesScript.used_apply_frames,
			"used_step_fixed": HazardCasesScript.used_step_fixed,
			"used_parse_input_event": HazardCasesScript.used_parse_input_event,
			"used_action_press": HazardCasesScript.used_action_press,
		},
	}
	_write_json(ev.path_join("outcomes.json"), outcomes)
	_write_json(ev.path_join("snapshot_start.json"), HazardCasesScript.snapshot_start)
	_write_json(ev.path_join("snapshot_end.json"), HazardCasesScript.snapshot_end)
	_write_json(ev.path_join("state_hashes.json"), {
		"replay": HazardCasesScript.outcome_replay,
		"chain": HazardCasesScript.outcome_chain,
		"seed": SEED,
		"map_id": MAP_ID,
		"mode": MODE,
	})
	var events_path: String = ev.path_join("events.jsonl")
	var ef: FileAccess = FileAccess.open(events_path, FileAccess.WRITE)
	if ef != null:
		var events: Array = HazardCasesScript.events_all
		if events.is_empty():
			events = HazardCasesScript.events_end
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
		"schema": "vault-fighters.vf4-wp3.run.v1",
		"run_id": RUN_ID,
		"command_id": COMMAND_ID,
		"wp": "VF4-WP3",
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
		"screens": {
			"setup": _setup_shot,
			"chain": chain_shot,
			"fire": fire_shot,
			"hang": hang_shot,
		},
		"outcomes": {
			"DATA": data,
			"CHAIN": chain,
			"FIRE": fire,
			"CLEANUP": cleanup,
			"ROLL": roll,
			"DUP": dup,
			"VFX": vfx,
			"HANG": hang,
			"LIVE": live,
			"REPLAY": replay,
			"USED_APPLY_FRAMES": HazardCasesScript.used_apply_frames,
			"USED_APPLY_ATTEMPTED": HazardCasesScript.used_apply_frames_attempted,
			"USED_APPLY_SUCCEEDED": HazardCasesScript.used_apply_frames_succeeded,
		},
		"fail_count": _fails.size(),
	}
	_write_json(ev.path_join("run_partial.json"), run_partial)
	print("HH_VF_HAZARD EVIDENCE_DIR=%s" % ev)


func _write_json(path: String, data: Variant) -> void:
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		print("HH_VF_HAZARD EVIDENCE_WRITE_FAIL %s" % path)
		return
	f.store_string(JSON.stringify(data, "\t"))
	f.close()

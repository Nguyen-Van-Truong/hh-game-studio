extends SceneTree

const RUN_ID := "VF4WP4-20260830-ASIA-SAIGON-02"
const COMMAND_ID := "cmd.vf4-wp4.moving.2"
const SEED := 7
const MODE := "vs2"
const MAP_ID := "fx_move_yard"

const MovingCasesScript: GDScript = preload("res://tests/moving_cases.gd")

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
	_setup_shot = _maybe_shot(app, "move_setup")
	var errors: PackedStringArray = await MovingCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	var data: String = str(MovingCasesScript.outcome_data.get("verdict", "unproven"))
	var ride: String = str(MovingCasesScript.outcome_ride.get("verdict", "unproven"))
	var carry: String = str(MovingCasesScript.outcome_carry.get("verdict", "unproven"))
	var drop: String = str(MovingCasesScript.outcome_drop.get("verdict", "unproven"))
	var door: String = str(MovingCasesScript.outcome_door.get("verdict", "unproven"))
	var trigger: String = str(MovingCasesScript.outcome_trigger.get("verdict", "unproven"))
	var pause: String = str(MovingCasesScript.outcome_pause.get("verdict", "unproven"))
	var reset: String = str(MovingCasesScript.outcome_reset.get("verdict", "unproven"))
	var live: String = str(MovingCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(MovingCasesScript.outcome_replay.get("verdict", "unproven"))
	if data != "pass":
		_fail("DATA structured outcome is %s" % data)
	if ride != "pass":
		_fail("RIDE structured outcome is %s" % ride)
	if carry != "pass":
		_fail("CARRY structured outcome is %s" % carry)
	if drop != "pass":
		_fail("DROP structured outcome is %s" % drop)
	if door != "pass":
		_fail("DOOR structured outcome is %s" % door)
	if trigger != "pass":
		_fail("TRIGGER structured outcome is %s" % trigger)
	if pause != "pass":
		_fail("PAUSE structured outcome is %s" % pause)
	if reset != "pass":
		_fail("RESET structured outcome is %s" % reset)
	if live != "pass":
		_fail("LIVE structured outcome is %s" % live)
	if replay != "match":
		_fail("REPLAY structured outcome is %s" % replay)
	var ended_at: String = _iso_local()
	print("HH_VF_MOVING run_id=%s" % RUN_ID)
	print("HH_VF_MOVING command_id=%s" % COMMAND_ID)
	print("HH_VF_MOVING DISPLAY=%s" % DisplayServer.get_name())
	print("HH_VF_MOVING SEED=%d MAP=%s MODE=%s" % [SEED, MAP_ID, MODE])
	print("HH_VF_MOVING STARTED_AT=%s ENDED_AT=%s" % [_started_at, ended_at])
	print(
		"HH_VF_MOVING USED_STEP_FIXED=%d USED_APPLY_FRAMES=%d USED_APPLY_ATTEMPTED=%d USED_APPLY_SUCCEEDED=%d USED_PARSE_INPUT_EVENT=%d USED_ACTION_PRESS=%d"
		% [
			MovingCasesScript.used_step_fixed,
			MovingCasesScript.used_apply_frames,
			MovingCasesScript.used_apply_frames_attempted,
			MovingCasesScript.used_apply_frames_succeeded,
			MovingCasesScript.used_parse_input_event,
			MovingCasesScript.used_action_press
		]
	)
	print("HH_VF_MOVING DATA=%s DATA_SOURCE=outcome_data" % data)
	print("HH_VF_MOVING RIDE=%s RIDE_SOURCE=outcome_ride" % ride)
	print("HH_VF_MOVING CARRY=%s CARRY_SOURCE=outcome_carry" % carry)
	print("HH_VF_MOVING DROP=%s DROP_SOURCE=outcome_drop" % drop)
	print("HH_VF_MOVING DOOR=%s DOOR_SOURCE=outcome_door" % door)
	print("HH_VF_MOVING TRIGGER=%s TRIGGER_SOURCE=outcome_trigger" % trigger)
	print("HH_VF_MOVING PAUSE=%s PAUSE_SOURCE=outcome_pause" % pause)
	print("HH_VF_MOVING RESET=%s RESET_SOURCE=outcome_reset" % reset)
	print("HH_VF_MOVING LIVE=%s LIVE_SOURCE=outcome_live" % live)
	print("HH_VF_MOVING REPLAY=%s REPLAY_SOURCE=outcome_replay" % replay)
	print("HH_VF_MOVING DOOR_CLASS=assumption LIFT=assumption BOARD=assumption TRIGGER=assumption NADE_PROP=deferred HOLD_AIM=assumption ROLL_DIVE=unavailable CLOCK=RL-SIM-FIXED-60")
	await _write_evidence(app, ended_at, data, ride, carry, drop, door, trigger, pause, reset, live, replay)
	if _fails.is_empty():
		print("PASS: Vault Fighters doors and moving platforms")
	else:
		print("FAIL: Vault Fighters doors and moving platforms")
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
		print("HH_VF_MOVING SCREENSHOT_%s missing viewport texture" % stem)
		return ""
	var img: Image = tex.get_image()
	if img == null:
		print("HH_VF_MOVING SCREENSHOT_%s get_image null" % stem)
		return ""
	var shot: String = ev.path_join("screens").path_join("%s_%dx%d.png" % [stem, int(vis.size.x), int(vis.size.y)])
	var err: Error = img.save_png(shot)
	print("HH_VF_MOVING SCREENSHOT_%s err=%d path=%s" % [stem, int(err), shot])
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


func _owner(session: GameSession) -> RefCounted:
	if session == null:
		return null
	return session.world_owner


func _find(session: GameSession, pid: String) -> Node2D:
	if _owner(session) == null:
		return null
	return _owner(session).call("find_by_id", pid) as Node2D


func _clear_live(app: App) -> void:
	if app == null:
		return
	InputInjector.release_known(app.get_viewport())
	InputActions.reset_edges()


func _stage_door_open(app: App) -> Dictionary:
	var row: Dictionary = {"open": 0, "x": -1.0}
	if app == null:
		return row
	_clear_live(app)
	app.start_fight("vs2", "fx_move_door", 0)
	await SimReplay.sync_physics(app)
	_clear_live(app)
	var session: GameSession = app.session
	_apply_held(session, 58, PackedStringArray(["right"]))
	_apply_held(session, 20, PackedStringArray())
	_apply_held(session, 50, PackedStringArray(["right"]))
	await _draw_ready()
	var door: Node2D = _find(session, "hall_door")
	var p1: Fighter = session.player1() if session != null else null
	row["open"] = 1 if door != null and bool(door.get("door_open")) else 0
	row["x"] = p1.global_position.x if p1 != null else -1.0
	return row


func _stage_ride(app: App) -> Dictionary:
	var row: Dictionary = {"y0": -1.0, "y1": -1.0, "phase": "", "on_floor": 0, "hanging": 0, "pose": ""}
	if app == null:
		return row
	_clear_live(app)
	app.start_fight("vs2", "fx_move_lift", 0)
	await SimReplay.sync_physics(app)
	_clear_live(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1() if session != null else null
	row["y0"] = p1.global_position.y if p1 != null else -1.0
	_apply_held(session, 50, PackedStringArray(["right"]))
	var n: int = 0
	var lift: Node2D = _find(session, "shaft_car")
	while n < 80:
		_apply_held(session, 1, PackedStringArray())
		lift = _find(session, "shaft_car")
		if lift != null and str(lift.get("phase")) == "dwell":
			break
		n += 1
	await _draw_ready()
	p1 = session.player1() if session != null else null
	lift = _find(session, "shaft_car")
	row["y1"] = p1.global_position.y if p1 != null else float(row["y0"])
	row["phase"] = str(lift.get("phase")) if lift != null else ""
	row["on_floor"] = 1 if p1 != null and (p1.is_on_floor() or p1.platform_riding) else 0
	row["hanging"] = 1 if p1 != null and p1.hanging else 0
	row["pose"] = p1.current_pose() if p1 != null else ""
	return row


func _stage_drop(app: App) -> Dictionary:
	var row: Dictionary = {"y_end": -1.0, "ly": -1.0, "phase": "", "on_floor": 0, "hanging": 0, "pose": ""}
	if app == null:
		return row
	_clear_live(app)
	app.start_fight("vs2", "fx_move_lift", 0)
	await SimReplay.sync_physics(app)
	_clear_live(app)
	var session: GameSession = app.session
	_apply_held(session, 50, PackedStringArray(["right"]))
	var n: int = 0
	var lift: Node2D = _find(session, "shaft_car")
	while n < 80:
		_apply_held(session, 1, PackedStringArray())
		lift = _find(session, "shaft_car")
		if lift != null and str(lift.get("phase")) == "dwell":
			break
		n += 1
	_apply_held(session, 16, PackedStringArray(["right"]))
	n = 0
	while n < 80:
		_apply_held(session, 1, PackedStringArray())
		lift = _find(session, "shaft_car")
		if lift != null and str(lift.get("phase")) == "idle":
			break
		n += 1
	_apply_held(session, 4, PackedStringArray())
	await _draw_ready()
	var p1: Fighter = session.player1() if session != null else null
	lift = _find(session, "shaft_car")
	row["y_end"] = p1.global_position.y if p1 != null else -1.0
	row["ly"] = lift.global_position.y if lift != null else -1.0
	row["phase"] = str(lift.get("phase")) if lift != null else ""
	row["on_floor"] = 1 if p1 != null and p1.is_on_floor() else 0
	row["hanging"] = 1 if p1 != null and p1.hanging else 0
	row["pose"] = p1.current_pose() if p1 != null else ""
	return row


func _write_evidence(
	app: App, ended_at: String, data: String, ride: String, carry: String, drop: String,
	door: String, trigger: String, pause: String, reset: String, live: String, replay: String
) -> void:
	var ev: String = OS.get_environment("HH_VF_EVIDENCE_DIR")
	if ev == "":
		ev = ProjectSettings.globalize_path("res://.evidence/%s" % RUN_ID)
	DirAccess.make_dir_recursive_absolute(ev)
	DirAccess.make_dir_recursive_absolute(ev.path_join("screens"))
	_clear_live(app)
	var door_row: Dictionary = await _stage_door_open(app)
	var door_shot: String = _maybe_shot(app, "move_door")
	print(
		"HH_VF_MOVING SHOT_DOOR open=%d x=%s path=%s"
		% [int(door_row.get("open", 0)), str(door_row.get("x", -1)), door_shot]
	)
	var ride_row: Dictionary = await _stage_ride(app)
	var ride_shot: String = _maybe_shot(app, "move_ride")
	print(
		"HH_VF_MOVING SHOT_RIDE y0=%s y1=%s phase=%s on_floor=%d hang=%d pose=%s path=%s"
		% [
			str(ride_row.get("y0", -1)),
			str(ride_row.get("y1", -1)),
			str(ride_row.get("phase", "")),
			int(ride_row.get("on_floor", 0)),
			int(ride_row.get("hanging", 0)),
			str(ride_row.get("pose", "")),
			ride_shot
		]
	)
	var drop_row: Dictionary = await _stage_drop(app)
	var drop_shot: String = _maybe_shot(app, "move_drop")
	print(
		"HH_VF_MOVING SHOT_DROP y_end=%s ly=%s phase=%s on_floor=%d hang=%d pose=%s path=%s"
		% [
			str(drop_row.get("y_end", -1)),
			str(drop_row.get("ly", -1)),
			str(drop_row.get("phase", "")),
			int(drop_row.get("on_floor", 0)),
			int(drop_row.get("hanging", 0)),
			str(drop_row.get("pose", "")),
			drop_shot
		]
	)
	if _windowed():
		if int(door_row.get("open", 0)) != 1:
			_fail("DoD door still must show an open gate")
		if float(ride_row.get("y1", 99)) >= float(ride_row.get("y0", 0)) - 8.0:
			_fail("DoD ride still must show P1 raised on the lift")
		if int(ride_row.get("hanging", 0)) != 0 or str(ride_row.get("pose", "")) == "hang":
			_fail("DoD ride still must stand on the lift, not hang")
		if float(drop_row.get("y_end", 99)) < 60.0 or float(drop_row.get("y_end", 99)) > 76.0:
			_fail("DoD drop still must show P1 standing on the upper deck")
		if int(drop_row.get("on_floor", 0)) != 1 or int(drop_row.get("hanging", 0)) != 0:
			_fail("DoD drop still must be on_floor idle, not hang")
		if str(drop_row.get("pose", "hang")) == "hang":
			_fail("DoD drop still pose must not be hang")
		if door_shot == "" or ride_shot == "" or drop_shot == "" or _setup_shot == "":
			_fail("DoD window stills missing setup/door/ride/drop")
	var outcomes: Dictionary = {
		"data": MovingCasesScript.outcome_data,
		"ride": MovingCasesScript.outcome_ride,
		"carry": MovingCasesScript.outcome_carry,
		"drop": MovingCasesScript.outcome_drop,
		"door": MovingCasesScript.outcome_door,
		"trigger": MovingCasesScript.outcome_trigger,
		"pause": MovingCasesScript.outcome_pause,
		"reset": MovingCasesScript.outcome_reset,
		"live": MovingCasesScript.outcome_live,
		"replay": MovingCasesScript.outcome_replay,
		"apply": {
			"attempted": MovingCasesScript.used_apply_frames_attempted,
			"succeeded": MovingCasesScript.used_apply_frames_succeeded,
			"used_apply_frames": MovingCasesScript.used_apply_frames,
			"used_step_fixed": MovingCasesScript.used_step_fixed,
			"used_parse_input_event": MovingCasesScript.used_parse_input_event,
			"used_action_press": MovingCasesScript.used_action_press,
		},
	}
	_write_json(ev.path_join("outcomes.json"), outcomes)
	_write_json(ev.path_join("snapshot_start.json"), MovingCasesScript.snapshot_start)
	_write_json(ev.path_join("snapshot_end.json"), MovingCasesScript.snapshot_end)
	_write_json(ev.path_join("state_hashes.json"), {
		"replay": MovingCasesScript.outcome_replay,
		"ride": MovingCasesScript.outcome_ride,
		"seed": SEED,
		"map_id": MAP_ID,
		"mode": MODE,
	})
	var events_path: String = ev.path_join("events.jsonl")
	var ef: FileAccess = FileAccess.open(events_path, FileAccess.WRITE)
	if ef != null:
		var events: Array = MovingCasesScript.events_all
		if events.is_empty():
			events = MovingCasesScript.events_end
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
		"schema": "vault-fighters.vf4-wp4.run.v1",
		"run_id": RUN_ID,
		"command_id": COMMAND_ID,
		"wp": "VF4-WP4",
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
			"door": door_shot,
			"ride": ride_shot,
			"drop": drop_shot,
		},
		"outcomes": {
			"DATA": data,
			"RIDE": ride,
			"CARRY": carry,
			"DROP": drop,
			"DOOR": door,
			"TRIGGER": trigger,
			"PAUSE": pause,
			"RESET": reset,
			"LIVE": live,
			"REPLAY": replay,
			"USED_APPLY_FRAMES": MovingCasesScript.used_apply_frames,
			"USED_APPLY_ATTEMPTED": MovingCasesScript.used_apply_frames_attempted,
			"USED_APPLY_SUCCEEDED": MovingCasesScript.used_apply_frames_succeeded,
		},
		"fail_count": _fails.size(),
	}
	_write_json(ev.path_join("run_partial.json"), run_partial)
	print("HH_VF_MOVING EVIDENCE_DIR=%s" % ev)


func _write_json(path: String, data: Variant) -> void:
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		print("HH_VF_MOVING EVIDENCE_WRITE_FAIL %s" % path)
		return
	f.store_string(JSON.stringify(data, "\t"))
	f.close()

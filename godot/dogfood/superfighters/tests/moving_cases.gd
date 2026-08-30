class_name MovingCases
extends RefCounted

const _Catalog: GDScript = preload("res://src/world/world_catalog.gd")
const _Moving: GDScript = preload("res://src/world/moving_spec.gd")

## VF4-WP4 official door / lift / board / trigger cases.
## Proof is InputFrame apply_frames plus live InputEvent inject.
## 60 Hz is ledger:RL-SIM-FIXED-60 (assumption).
## Door / lift / board / trigger stay assumption. RL-NADE-PROP stays deferred.
## USED_APPLY_FRAMES counts success only.

static var used_step_fixed: int = 0
static var used_apply_frames: int = 0
static var used_apply_frames_attempted: int = 0
static var used_apply_frames_succeeded: int = 0
static var used_parse_input_event: int = 0
static var used_action_press: int = 0
static var outcome_data: Dictionary = {}
static var outcome_ride: Dictionary = {}
static var outcome_carry: Dictionary = {}
static var outcome_drop: Dictionary = {}
static var outcome_door: Dictionary = {}
static var outcome_trigger: Dictionary = {}
static var outcome_pause: Dictionary = {}
static var outcome_reset: Dictionary = {}
static var outcome_live: Dictionary = {}
static var outcome_replay: Dictionary = {}
static var snapshot_start: Dictionary = {}
static var snapshot_end: Dictionary = {}
static var events_end: Array = []
static var events_all: Array = []


static func run_all(app: App) -> PackedStringArray:
	used_step_fixed = 0
	used_apply_frames = 0
	used_apply_frames_attempted = 0
	used_apply_frames_succeeded = 0
	used_parse_input_event = 0
	used_action_press = 0
	outcome_data = {"verdict": "unproven"}
	outcome_ride = {"verdict": "unproven"}
	outcome_carry = {"verdict": "unproven"}
	outcome_drop = {"verdict": "unproven"}
	outcome_door = {"verdict": "unproven"}
	outcome_trigger = {"verdict": "unproven"}
	outcome_pause = {"verdict": "unproven"}
	outcome_reset = {"verdict": "unproven"}
	outcome_live = {"verdict": "unproven"}
	outcome_replay = {"verdict": "unproven", "pairs": []}
	snapshot_start = {}
	snapshot_end = {}
	events_end = []
	events_all = []
	var errors: PackedStringArray = PackedStringArray()
	_append(errors, schema_and_data())
	_append(errors, await _capture_start(app))
	_append(errors, await replay_traces_twice(app))
	_append(errors, await door_blocks_then_opens(app))
	_append(errors, await ride_without_tunnel(app))
	_append(errors, await drop_on_upper(app))
	_append(errors, await pause_and_reset(app))
	_append(errors, await live_door(app))
	_append(errors, _require_outcomes())
	return errors


static func schema_and_data() -> PackedStringArray:
	var errors: PackedStringArray = _Catalog.validate()
	_append(errors, _Moving.validate())
	if not Maps.has_fixture("fx_move_door") or not Maps.has_fixture("fx_move_lift"):
		errors.append("moving fixtures missing")
	if Maps.display_name("fx_move_door") != "Gate Hall":
		errors.append("door fixture display name must be Gate Hall")
	if Maps.display_name("fx_move_lift") != "Lift Shaft":
		errors.append("lift fixture display name must be Lift Shaft")
	if Maps.display_name("fx_move_yard") != "Relay Shaft":
		errors.append("yard fixture display name must be Relay Shaft")
	if Maps.display_name("fx_move_yard").to_lower().contains("superfighter"):
		errors.append("moving fixture name must stay original")
	var live: Dictionary = _Catalog.data()
	var mov: Dictionary = _Moving.data()
	if not bool(live.get("moving_implemented", false)):
		errors.append("DATA moving_implemented must be true")
	if str(live.get("nade_prop_class", "")) != "deferred":
		errors.append("DATA RL-NADE-PROP must stay deferred")
	if str(mov.get("door_class", "")) != "assumption":
		errors.append("DATA door must stay assumption")
	if int(mov.get("travel_ticks", 0)) != 44:
		errors.append("DATA travel_ticks must be 44")
	if float(mov.get("max_step_px", 0.0)) > 4.0:
		errors.append("DATA max_step_px must stay <= 4")
	if float(mov.get("snap_eps", 99.0)) > 8.0:
		errors.append("DATA snap_eps must stay <= 8")
	if float(mov.get("warp_px", 0.0)) < 16.0:
		errors.append("DATA warp_px must stay >= 16")
	outcome_data = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"moving_implemented": true,
		"nade_prop": "deferred",
		"travel_ticks": 44,
		"max_step_px": float(mov.get("max_step_px", 0.0)),
		"snap_eps": float(mov.get("snap_eps", 0.0)),
		"warp_px": float(mov.get("warp_px", 0.0)),
		"source": "catalog + moving.json Gate Hall / Lift Shaft / Relay Shaft",
	}
	return errors


static func replay_traces_twice(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var paths: PackedStringArray = SimTrace.list_dir(SimConstants.MOVING_TRACE_DIR)
	if paths.size() < 4:
		errors.append("expected >=4 moving traces, got %d" % paths.size())
	var required: PackedStringArray = PackedStringArray([
		"move_door", "move_ride", "move_drop", "move_yard"
	])
	var names: PackedStringArray = PackedStringArray()
	var pairs: Array = []
	var i: int = 0
	while i < paths.size():
		var path: String = String(paths[i])
		var trace: Dictionary = SimTrace.load_path(path)
		_append(errors, SimTrace.validate(trace))
		if bool(trace.get("used_step_fixed", true)):
			errors.append("%s must set used_step_fixed false" % path.get_file())
		if bool(trace.get("y8_parity_claimed", true)):
			errors.append("%s claimed Y8 parity" % path.get_file())
		if "assumption" not in str(trace.get("hold_to_aim", "")):
			errors.append("%s must keep hold-to-aim assumption" % path.get_file())
		names.append(str(trace.get("name", path.get_file())))
		await _drain_physics(app)
		var a: Dictionary = await SimReplay.play_path(app, path)
		var hash_wa: String = str(a.get("world_hash", ""))
		await _drain_physics(app)
		var b: Dictionary = await SimReplay.play_path(app, path)
		var hash_wb: String = str(b.get("world_hash", ""))
		_record_apply_batch(int(a.get("ticks", 0)), bool(a.get("ok", false)))
		_record_apply_batch(int(b.get("ticks", 0)), bool(b.get("ok", false)))
		if not bool(a.get("ok", false)):
			errors.append("moving %s run1 failed: %s" % [path.get_file(), _join(a)])
		if not bool(b.get("ok", false)):
			errors.append("moving %s run2 failed: %s" % [path.get_file(), _join(b)])
		if not bool(a.get("used_apply_frames", false)) or bool(a.get("used_cmd_dicts", true)):
			errors.append("moving %s MATCH used cmd dicts" % path.get_file())
		var hash_a: String = str(a.get("final_hash", ""))
		var hash_b: String = str(b.get("final_hash", ""))
		var match_ok: bool = hash_a != "" and hash_a == hash_b
		var world_ok: bool = hash_wa != "" and hash_wa == hash_wb
		if not match_ok:
			errors.append("moving %s replay hashes differ" % path.get_file())
		if not world_ok:
			errors.append("moving %s world hashes differ" % path.get_file())
		pairs.append({
			"name": str(trace.get("name", path.get_file())),
			"hash_match": match_ok,
			"world_hash_match": world_ok,
			"hash_a": hash_a,
			"hash_b": hash_b,
			"world_a": hash_wa,
			"world_b": hash_wb,
		})
		_remember_end(a)
		_append_events(a.get("events", []) as Array)
		i += 1
	i = 0
	while i < required.size():
		if not names.has(String(required[i])):
			errors.append("missing moving trace %s" % String(required[i]))
		i += 1
	var all_match: bool = pairs.size() >= 4
	var p: int = 0
	while p < pairs.size():
		var row: Dictionary = pairs[p] as Dictionary
		if not bool(row.get("hash_match", false)) or not bool(row.get("world_hash_match", false)):
			all_match = false
		p += 1
	outcome_replay = {
		"verdict": "match" if all_match and errors.is_empty() else "fail",
		"pairs": pairs,
		"source": "apply_frames moving traces twice",
	}
	return errors


static func door_blocks_then_opens(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_move_door", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	var door: Node2D = _find(session, "hall_door")
	if p1 == null or door == null:
		errors.append("DOOR missing P1 or hall_door")
		outcome_door = {"verdict": "fail"}
		outcome_trigger = {"verdict": "fail"}
		return errors
	var x0: float = p1.global_position.x
	_hold(session, 90, PackedStringArray(["right"]))
	var x_block: float = p1.global_position.x
	var opened0: bool = bool(door.get("door_open"))
	if opened0:
		errors.append("DOOR must stay closed when walking across the plate")
	if x_block > 240.0:
		errors.append("DOOR closed must block the corridor got x=%s" % str(x_block))
	if x_block <= x0 + 8.0:
		errors.append("DOOR walk must approach the gate")
	app.start_fight("vs2", "fx_move_door", 0)
	await SimReplay.sync_physics(app)
	session = app.session
	p1 = session.player1()
	door = _find(session, "hall_door")
	_hold(session, 58, PackedStringArray(["right"]))
	_idle(session, 16)
	var opened1: bool = door != null and bool(door.get("door_open"))
	var opens: int = int(_owner(session).get("door_open_events")) if _owner(session) != null else 0
	var trig: int = int(_owner(session).get("trigger_events")) if _owner(session) != null else 0
	_hold(session, 50, PackedStringArray(["right"]))
	var x_open: float = p1.global_position.x if p1 != null else -1.0
	if not opened1:
		errors.append("DOOR must open after standing on the plate")
	if x_open < 260.0:
		errors.append("DOOR open must let P1 through got x=%s" % str(x_open))
	outcome_door = {
		"verdict": "pass" if not opened0 and x_block <= 240.0 and opened1 and x_open >= 260.0 else "fail",
		"x_block": x_block,
		"x_open": x_open,
		"opens": opens,
		"source": "Gate Hall closed blocks then plate opens",
	}
	outcome_trigger = {
		"verdict": "pass" if trig >= 1 and opened1 else "fail",
		"events": trig,
		"source": "Call Plate arm ticks then door_open",
	}
	_remember_session(session)
	return errors


static func ride_without_tunnel(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_move_lift", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	var lift: Node2D = _find(session, "shaft_car")
	if p1 == null or lift == null:
		errors.append("RIDE missing P1 or shaft_car")
		outcome_ride = {"verdict": "fail"}
		outcome_carry = {"verdict": "fail"}
		return errors
	var y0: float = p1.global_position.y
	var ly0: float = lift.global_position.y
	_hold(session, 50, PackedStringArray(["right"]))
	var tunnels: int = 0
	var max_tick_dy: float = 0.0
	var prev_y: float = p1.global_position.y if p1 != null else y0
	var prev_ly: float = lift.global_position.y if lift != null else ly0
	var n: int = 0
	while n < 80:
		_idle(session, 1)
		if p1 != null and Maps.solid_at(session.map_id, p1.global_position):
			tunnels += 1
		if p1 != null and Maps.solid_at(session.map_id, p1.global_position + Vector2(0.0, 10.0)):
			tunnels += 1
		var fy: float = p1.global_position.y if p1 != null else prev_y
		var ly: float = lift.global_position.y if lift != null else prev_ly
		var extra: float = absf(fy - prev_y) - absf(ly - prev_ly)
		if extra > max_tick_dy:
			max_tick_dy = extra
		if extra + 0.0001 >= 16.0:
			tunnels += 1
		prev_y = fy
		prev_ly = ly
		if lift != null and str(lift.get("phase")) == "dwell":
			break
		n += 1
	var y1: float = p1.global_position.y if p1 != null else y0
	var ly1: float = lift.global_position.y if lift != null else ly0
	var boards: int = int(_owner(session).get("board_events")) if _owner(session) != null else 0
	var tun_own: int = int(_owner(session).get("tunnel_events")) if _owner(session) != null else 0
	var max_dy: float = float(_owner(session).get("max_board_dy")) if _owner(session) != null else max_tick_dy
	if max_dy < max_tick_dy:
		max_dy = max_tick_dy
	var hanging_ride: bool = p1 != null and p1.hanging
	var pose_ride: String = p1.current_pose() if p1 != null else ""
	var floor_ride: bool = p1 != null and (p1.is_on_floor() or p1.platform_riding)
	if y1 >= y0 - 20.0:
		errors.append("RIDE P1 must rise with the lift y0=%s y1=%s" % [str(y0), str(y1)])
	if ly1 >= ly0 - 20.0:
		errors.append("CARRY lift must travel toward the upper deck")
	if boards < 1:
		errors.append("CARRY expected a board event")
	if tunnels > 0 or tun_own > 0:
		errors.append("RIDE tunneled ticks=%d owner=%d" % [tunnels, tun_own])
	if hanging_ride or pose_ride == "hang":
		errors.append("RIDE must stand on the lift, not hang pose=%s" % pose_ride)
	if not floor_ride:
		errors.append("RIDE must be on_floor or riding at dwell")
	if max_dy + 0.0001 >= 16.0:
		errors.append("RIDE Y warp %s >= 16" % str(max_dy))
	var ride_ok: bool = (
		y1 < y0 - 20.0
		and tunnels == 0
		and tun_own == 0
		and not hanging_ride
		and pose_ride != "hang"
		and floor_ride
		and max_dy + 0.0001 < 16.0
	)
	outcome_ride = {
		"verdict": "pass" if ride_ok else "fail",
		"y0": y0,
		"y1": y1,
		"tunnels": tunnels,
		"owner_tunnels": tun_own,
		"max_board_dy": max_dy,
		"on_floor": floor_ride,
		"hanging": hanging_ride,
		"pose": pose_ride,
		"source": "Lift Shaft ride without solid overlap or Y warp",
	}
	outcome_carry = {
		"verdict": "pass" if ly1 < ly0 - 20.0 and boards >= 1 else "fail",
		"ly0": ly0,
		"ly1": ly1,
		"boards": boards,
		"max_board_dy": max_dy,
		"source": "platform delta carries the boarded fighter",
	}
	_remember_session(session)
	return errors


static func drop_on_upper(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_move_lift", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	var lift: Node2D = _find(session, "shaft_car")
	_hold(session, 50, PackedStringArray(["right"]))
	var n: int = 0
	while n < 80:
		_idle(session, 1)
		if lift != null and str(lift.get("phase")) == "dwell":
			break
		n += 1
	var y_top: float = p1.global_position.y if p1 != null else 999.0
	_hold(session, 16, PackedStringArray(["right"]))
	n = 0
	while n < 80:
		_idle(session, 1)
		if lift != null and str(lift.get("phase")) == "idle":
			break
		n += 1
	_idle(session, 4)
	var y_end: float = p1.global_position.y if p1 != null else 999.0
	var ly_end: float = lift.global_position.y if lift != null else -1.0
	var unboards: int = int(_owner(session).get("unboard_events")) if _owner(session) != null else 0
	var max_dy: float = float(_owner(session).get("max_board_dy")) if _owner(session) != null else 99.0
	var on_floor_end: bool = p1 != null and p1.is_on_floor()
	var hanging_end: bool = p1 != null and p1.hanging
	var pose_end: String = p1.current_pose() if p1 != null else ""
	var deck_y: bool = y_end >= 60.0 and y_end <= 76.0
	var stand_ok: bool = on_floor_end and not hanging_end and pose_end != "hang" and deck_y
	if not stand_ok:
		errors.append(
			"DROP P1 must stand on the upper deck on_floor=%s hang=%s pose=%s y=%s"
			% [str(on_floor_end), str(hanging_end), pose_end, str(y_end)]
		)
	if ly_end < 140.0:
		errors.append("DROP lift must return to the shaft floor")
	if unboards < 1:
		errors.append("DROP expected an unboard")
	if p1 != null and p1.dead:
		errors.append("DROP must not kill the rider")
	if max_dy + 0.0001 >= 16.0:
		errors.append("DROP Y warp %s >= 16" % str(max_dy))
	outcome_drop = {
		"verdict": "pass" if stand_ok and ly_end >= 140.0 and unboards >= 1 and max_dy + 0.0001 < 16.0 else "fail",
		"y_top": y_top,
		"y_end": y_end,
		"ly_end": ly_end,
		"unboards": unboards,
		"on_floor": on_floor_end,
		"hanging": hanging_end,
		"pose": pose_end,
		"max_board_dy": max_dy,
		"source": "walk off onto solid deck; lift returns; P1 stands idle",
	}
	_remember_session(session)
	return errors


static func pause_and_reset(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_move_lift", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_hold(session, 50, PackedStringArray(["right"]))
	_idle(session, 20)
	var lift: Node2D = _find(session, "shaft_car")
	var y_mid: float = lift.global_position.y if lift != null else -1.0
	var phase_mid: String = str(lift.get("phase")) if lift != null else ""
	session.set_paused(true, "test")
	var rejected: bool = not session.apply_frames(_idle_frames(session))
	used_apply_frames_attempted += 1
	var y_pause: float = lift.global_position.y if lift != null else -2.0
	session.set_paused(false)
	_idle(session, 16)
	var y_res: float = lift.global_position.y if lift != null else y_mid
	if not rejected:
		errors.append("PAUSE apply_frames must reject while paused")
	if absf(y_pause - y_mid) > 0.01:
		errors.append("PAUSE lift must freeze")
	if absf(y_res - y_pause) < 0.5:
		errors.append("PAUSE resume must continue the path")
	app.start_fight("vs2", "fx_move_yard", 0)
	await SimReplay.sync_physics(app)
	session = app.session
	var door: Node2D = _find(session, "yard_door")
	lift = _find(session, "yard_car")
	var door_closed: bool = door != null and not bool(door.get("door_open"))
	var lift_home: bool = lift != null and str(lift.get("phase")) == "idle"
	var ly: float = lift.global_position.y if lift != null else -1.0
	if not door_closed:
		errors.append("RESET door must start closed")
	if not lift_home or ly < 150.0:
		errors.append("RESET lift must start at the shaft floor")
	outcome_pause = {
		"verdict": "pass" if rejected and absf(y_pause - y_mid) <= 0.01 and absf(y_res - y_pause) >= 0.5 else "fail",
		"y_mid": y_mid,
		"y_pause": y_pause,
		"y_res": y_res,
		"phase_mid": phase_mid,
		"source": "clock.pause freezes path_tick; resume continues",
	}
	outcome_reset = {
		"verdict": "pass" if door_closed and lift_home and ly >= 150.0 else "fail",
		"door_closed": door_closed,
		"lift_home": lift_home,
		"ly": ly,
		"source": "start_fight rebuilds movers at rest",
	}
	_remember_session(session)
	return errors


static func live_door(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_move_door", 0)
	var session: GameSession = app.session
	var viewport: Viewport = app.get_viewport()
	await SimReplay.sync_physics(app)
	InputInjector.release_known(viewport)
	InputActions.reset_edges()
	used_parse_input_event += 1
	InputInjector.inject_key(KEY_RIGHT, true, viewport)
	var n: int = 0
	while n < 58:
		session.step_from_live_input()
		n += 1
	InputInjector.inject_key(KEY_RIGHT, false, viewport)
	n = 0
	while n < 16:
		session.step_from_live_input()
		n += 1
	InputInjector.inject_key(KEY_RIGHT, true, viewport)
	n = 0
	while n < 50:
		session.step_from_live_input()
		n += 1
	InputInjector.inject_key(KEY_RIGHT, false, viewport)
	session.step_from_live_input()
	var door: Node2D = _find(session, "hall_door")
	var p1: Fighter = session.player1()
	var opened: bool = door != null and bool(door.get("door_open"))
	var x1: float = p1.global_position.x if p1 != null else -1.0
	if not opened:
		errors.append("LIVE door must open")
	if x1 < 240.0:
		errors.append("LIVE P1 must pass or reach the open gate")
	InputInjector.release_known(viewport)
	outcome_live = {
		"verdict": "pass" if opened else "fail",
		"open": opened,
		"x": x1,
		"source": "parse_input_event KEY_RIGHT + step_from_live_input",
	}
	_remember_session(session)
	return errors


static func _require_outcomes() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var labels: PackedStringArray = PackedStringArray([
		"DATA", "RIDE", "CARRY", "DROP", "DOOR", "TRIGGER", "PAUSE", "RESET", "LIVE"
	])
	var rows: Array = [
		outcome_data, outcome_ride, outcome_carry, outcome_drop, outcome_door,
		outcome_trigger, outcome_pause, outcome_reset, outcome_live
	]
	var ki: int = 0
	while ki < labels.size():
		var row: Dictionary = rows[ki] as Dictionary
		if str(row.get("verdict", "")) != "pass":
			errors.append("%s outcome is %s" % [String(labels[ki]), str(row.get("verdict", "unproven"))])
		ki += 1
	if str(outcome_replay.get("verdict", "")) != "match":
		errors.append("REPLAY outcome is %s" % str(outcome_replay.get("verdict", "unproven")))
	if used_apply_frames_succeeded <= 0 or used_apply_frames != used_apply_frames_succeeded:
		errors.append("USED_APPLY_FRAMES must count successful applies got=%d attempted=%d" % [
			used_apply_frames_succeeded, used_apply_frames_attempted
		])
	return errors


static func _owner(session: GameSession) -> RefCounted:
	if session == null:
		return null
	return session.world_owner


static func _find(session: GameSession, pid: String) -> Node2D:
	if _owner(session) == null:
		return null
	return _owner(session).call("find_by_id", pid) as Node2D


static func _idle(session: GameSession, ticks: int) -> void:
	_hold(session, ticks, PackedStringArray())


static func _hold(session: GameSession, ticks: int, held: PackedStringArray) -> void:
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
		_record_apply(session.apply_frames(frames))
		n += 1


static func _idle_frames(session: GameSession) -> Array:
	var frames: Array = []
	var i: int = 0
	while i < session.fighters.size():
		frames.append(InputFrame.from_dict(InputActions.empty_frame(session.clock.tick, i)))
		i += 1
	return frames


static func _drain_physics(app: App) -> void:
	InputActions.reset_edges()
	await SimReplay.sync_physics(app)
	await SimReplay.sync_physics(app)


static func _capture_start(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_move_yard", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	if session == null:
		errors.append("start snapshot missing session")
		return errors
	snapshot_start = session.snapshot()
	if session.world_owner != null:
		snapshot_start["world_props"] = session.world_owner.call("snapshot")
		snapshot_start["world_hash"] = session.world_owner.call("stable_hash")
	if session.ledger != null:
		events_end = session.ledger.to_array()
	return errors


static func _record_apply(ok: bool) -> bool:
	used_apply_frames_attempted += 1
	if ok:
		used_apply_frames_succeeded += 1
		used_apply_frames = used_apply_frames_succeeded
	return ok


static func _record_apply_batch(succeeded_ticks: int, ok: bool) -> void:
	var attempts: int = succeeded_ticks
	if not ok:
		attempts += 1
	if attempts < 0:
		attempts = 0
	if succeeded_ticks < 0:
		succeeded_ticks = 0
	used_apply_frames_attempted += attempts
	used_apply_frames_succeeded += succeeded_ticks
	used_apply_frames = used_apply_frames_succeeded


static func _remember_end(played: Dictionary) -> void:
	var state: Dictionary = played.get("final_state", {}) as Dictionary
	if not state.is_empty():
		snapshot_end = state
	var events: Array = played.get("events", []) as Array
	if not events.is_empty():
		events_end = events


static func _remember_session(session: GameSession) -> void:
	if session == null:
		return
	snapshot_end = session.snapshot()
	if session.world_owner != null:
		snapshot_end["world_props"] = session.world_owner.call("snapshot")
		snapshot_end["world_hash"] = session.world_owner.call("stable_hash")
	if session.ledger != null:
		events_end = session.ledger.to_array()


static func _append_events(events: Array) -> void:
	var i: int = 0
	while i < events.size():
		events_all.append(events[i])
		i += 1


static func _join(played: Dictionary) -> String:
	var errs: Variant = played.get("errors", PackedStringArray())
	if errs is PackedStringArray:
		return ",".join(errs as PackedStringArray)
	if errs is Array:
		var parts: PackedStringArray = PackedStringArray()
		var i: int = 0
		var arr: Array = errs as Array
		while i < arr.size():
			parts.append(str(arr[i]))
			i += 1
		return ",".join(parts)
	return str(errs)


static func _append(target: PackedStringArray, extra: PackedStringArray) -> void:
	var i: int = 0
	while i < extra.size():
		target.append(String(extra[i]))
		i += 1

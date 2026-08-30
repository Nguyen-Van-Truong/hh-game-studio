class_name BreakCases
extends RefCounted

const _Catalog: GDScript = preload("res://src/world/world_catalog.gd")
const _Break: GDScript = preload("res://src/world/prop_break.gd")

## VF4-WP2 official break / throw cases.
## Proof is InputFrame apply_frames plus live InputEvent inject.
## 60 Hz is ledger:RL-SIM-FIXED-60 (assumption).
## Break / throw stay assumption. RL-NADE-PROP stays deferred.
## Hold-to-aim stays ledger:RL-CTRL-HOLD-AIM (assumption).
## Y8 roll/dive stays unavailable. USED_APPLY_FRAMES counts success only.

static var used_step_fixed: int = 0
static var used_apply_frames: int = 0
static var used_apply_frames_attempted: int = 0
static var used_apply_frames_succeeded: int = 0
static var used_parse_input_event: int = 0
static var used_action_press: int = 0
static var outcome_data: Dictionary = {}
static var outcome_break: Dictionary = {}
static var outcome_debris: Dictionary = {}
static var outcome_pass: Dictionary = {}
static var outcome_ghost: Dictionary = {}
static var outcome_melee: Dictionary = {}
static var outcome_shove: Dictionary = {}
static var outcome_throw: Dictionary = {}
static var outcome_tactic: Dictionary = {}
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
	outcome_break = {"verdict": "unproven"}
	outcome_debris = {"verdict": "unproven"}
	outcome_pass = {"verdict": "unproven"}
	outcome_ghost = {"verdict": "unproven"}
	outcome_melee = {"verdict": "unproven"}
	outcome_shove = {"verdict": "unproven"}
	outcome_throw = {"verdict": "unproven"}
	outcome_tactic = {"verdict": "unproven"}
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
	_append(errors, await one_break_and_pass(app))
	_append(errors, await melee_breaks_wood(app))
	_append(errors, await shove_and_throw(app))
	_append(errors, await live_break(app))
	_append(errors, _require_outcomes())
	return errors


static func schema_and_data() -> PackedStringArray:
	var errors: PackedStringArray = _Catalog.validate()
	if not Maps.has_fixture("fx_break_cover") or not Maps.has_fixture("fx_break_yard"):
		errors.append("break fixtures missing")
	if Maps.display_name("fx_break_cover") != "Shatter Lane":
		errors.append("cover fixture display name must be Shatter Lane")
	if Maps.display_name("fx_break_yard") != "Break Yard":
		errors.append("yard fixture display name must be Break Yard")
	if Maps.display_name("fx_break_cover").to_lower().contains("superfighter"):
		errors.append("break fixture name must stay original")
	var live: Dictionary = _Catalog.data()
	if not bool(live.get("break_implemented", false)):
		errors.append("DATA break_implemented must be true")
	if not bool(live.get("throw_implemented", false)):
		errors.append("DATA throw_implemented must be true")
	if bool(live.get("chain_implemented", true)):
		errors.append("DATA chain must stay unimplemented")
	if str(live.get("nade_prop_class", "")) != "deferred":
		errors.append("DATA RL-NADE-PROP must stay deferred")
	if str(live.get("break_class", "")) != "assumption":
		errors.append("DATA break must stay assumption")
	if int(_Break.debris_count(_Catalog.spec("pane_glass"))) != 6:
		errors.append("DATA glass debris_count must be 6")
	if int(_Break.debris_count(_Catalog.spec("crate_breakable"))) != 4:
		errors.append("DATA wood debris_count must be 4")
	outcome_data = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"break_implemented": true,
		"throw_implemented": true,
		"chain_implemented": false,
		"nade_prop": "deferred",
		"glass_debris": 6,
		"wood_debris": 4,
		"source": "catalog materials + fixtures Shatter Lane / Break Yard",
	}
	return errors


static func replay_traces_twice(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var paths: PackedStringArray = SimTrace.list_dir(SimConstants.BREAK_TRACE_DIR)
	if paths.size() < 4:
		errors.append("expected >=4 break traces, got %d" % paths.size())
	var required: PackedStringArray = PackedStringArray([
		"break_cover", "break_melee", "break_shove", "break_throw"
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
			errors.append("break %s run1 failed: %s" % [path.get_file(), _join(a)])
		if not bool(b.get("ok", false)):
			errors.append("break %s run2 failed: %s" % [path.get_file(), _join(b)])
		if not bool(a.get("used_apply_frames", false)) or bool(a.get("used_cmd_dicts", true)):
			errors.append("break %s MATCH used cmd dicts" % path.get_file())
		var hash_a: String = str(a.get("final_hash", ""))
		var hash_b: String = str(b.get("final_hash", ""))
		var match_ok: bool = hash_a != "" and hash_a == hash_b
		var world_ok: bool = hash_wa != "" and hash_wa == hash_wb
		if not match_ok:
			errors.append("break %s replay hashes differ" % path.get_file())
		if not world_ok:
			errors.append("break %s world hashes differ" % path.get_file())
		pairs.append({
			"name": str(trace.get("name", path.get_file())),
			"hash_match": match_ok,
			"world_hash_match": world_ok,
			"ok_a": bool(a.get("ok", false)),
			"ok_b": bool(b.get("ok", false)),
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
			errors.append("missing break trace %s" % String(required[i]))
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
		"source": "apply_frames break traces twice",
	}
	return errors


static func one_break_and_pass(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_break_cover", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p2: Fighter = session.fighters[1] if session.fighters.size() > 1 else null
	var hp_start: float = p2.health if p2 != null else -1.0
	var glass: Node2D = _find(session, "cover_glass")
	if glass == null:
		errors.append("BREAK missing cover_glass")
	var cover_x: float = 168.0
	var blocked_before: bool = _owner(session) != null and bool(_owner(session).call("has_cover_at", Vector2(cover_x, 38.0)))
	if not blocked_before:
		errors.append("PASS cover must block before break")
	_hold_fire(session, 6)
	_release_fire(session)
	_idle(session, 28)
	var breaks1: int = _count_kind(session, "break")
	var debris1: int = int(_owner(session).get("last_debris_count")) if _owner(session) != null else -1
	var hp_mid: float = p2.health if p2 != null else -1.0
	var glass_alive: bool = glass != null and bool(glass.get("alive"))
	if breaks1 != 1:
		errors.append("BREAK expected one break event got %d" % breaks1)
	if glass_alive:
		errors.append("BREAK glass still alive after first shot")
	if debris1 != 6:
		errors.append("DEBRIS glass count %d != 6" % debris1)
	if hp_mid < hp_start - 0.01:
		errors.append("TACTIC P2 must not take the blocked first shot")
	var ghost: bool = _owner(session) != null and bool(_owner(session).call("has_cover_at", Vector2(cover_x, 38.0)))
	if ghost:
		errors.append("GHOST cover AABB still solid after break")
	_hold_fire(session, 6)
	_release_fire(session)
	_idle(session, 40)
	var breaks2: int = _count_kind(session, "break")
	var hp_end: float = p2.health if p2 != null else -1.0
	if breaks2 != 1:
		errors.append("BREAK second shot must not emit another break got %d" % breaks2)
	if hp_end >= hp_mid - 0.01:
		errors.append("PASS / TACTIC second shot must hit P2 after break")
	var debris2: int = _count_debris(session)
	outcome_break = {
		"verdict": "pass" if breaks1 == 1 and not glass_alive and errors.is_empty() else "fail",
		"events": breaks1,
		"id": str(_owner(session).get("last_break_id")) if _owner(session) != null else "",
		"source": "one pistol shot vs Vault Pane",
	}
	outcome_debris = {
		"verdict": "pass" if debris1 == 6 else "fail",
		"count": debris1,
		"expected": 6,
		"after_cleanup_ticks": debris2,
		"source": "glass material debris_count=6",
	}
	outcome_pass = {
		"verdict": "pass" if blocked_before and hp_end < hp_mid - 0.01 else "fail",
		"blocked_before": blocked_before,
		"p2_hp_before": hp_start,
		"p2_hp_mid": hp_mid,
		"p2_hp_after": hp_end,
		"source": "projectile spent on pane, then passes",
	}
	outcome_ghost = {
		"verdict": "pass" if not ghost else "fail",
		"cover_after": ghost,
		"source": "has_cover_at after disable_cover",
	}
	outcome_tactic = {
		"verdict": "pass" if hp_end < hp_mid - 0.01 and hp_mid >= hp_start - 0.01 else "fail",
		"lane_opens": hp_end < hp_mid - 0.01,
		"source": "cover changes the fire lane, not cosmetic VFX",
	}
	_remember_session(session)
	return errors


static func melee_breaks_wood(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_break_yard", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var wood: Node2D = _find(session, "yard_wood")
	if wood == null:
		errors.append("MELEE missing yard_wood")
	_walk_right(session, 12)
	_idle(session, 2)
	_press_melee(session)
	_idle(session, 16)
	var alive: bool = wood != null and bool(wood.get("alive"))
	var breaks: int = _count_kind(session, "break")
	var debris: int = int(_owner(session).get("last_debris_count")) if _owner(session) != null else -1
	if alive:
		errors.append("MELEE wood crate must break")
	if breaks != 1:
		errors.append("MELEE expected one wood break got %d" % breaks)
	if debris != 4:
		errors.append("MELEE wood debris %d != 4" % debris)
	outcome_melee = {
		"verdict": "pass" if not alive and breaks == 1 and debris == 4 else "fail",
		"alive": alive,
		"breaks": breaks,
		"debris": debris,
		"source": "fists vs wood crate on Break Yard",
	}
	_remember_session(session)
	return errors


static func shove_and_throw(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_break_yard", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var loose: Node2D = _find(session, "yard_loose")
	if loose == null:
		errors.append("SHOVE missing yard_loose")
		outcome_shove = {"verdict": "fail"}
		outcome_throw = {"verdict": "fail"}
		return errors
	var x0: float = loose.global_position.x
	_clear_wood_then_reach_loose(session)
	_press_melee(session)
	_idle(session, 20)
	var x1: float = loose.global_position.x
	var shoved: bool = x1 > x0 + 2.0
	if not shoved:
		errors.append("SHOVE loose crate must move right")
	var shoves: int = _count_kind(session, "prop_shove")
	outcome_shove = {
		"verdict": "pass" if shoved else "fail",
		"x0": x0,
		"x1": x1,
		"events": shoves,
		"source": "melee shove on Loose Crate, # floor only",
	}
	app.start_fight("vs2", "fx_break_yard", 0)
	await SimReplay.sync_physics(app)
	session = app.session
	loose = _find(session, "yard_loose")
	var tx0: float = loose.global_position.x if loose != null else 0.0
	_clear_wood_then_reach_loose(session)
	_crouch_melee(session)
	_idle(session, 2)
	var carried: bool = _owner(session) != null and _owner(session).call("carrier_of", 0) != null
	_hold_nade(session, 6)
	_release_nade(session)
	_idle(session, 24)
	loose = _find(session, "yard_loose")
	var thrown: bool = _count_kind(session, "prop_throw") == 1
	var tx1: float = loose.global_position.x if loose != null else tx0
	var still_carried: bool = _owner(session) != null and _owner(session).call("carrier_of", 0) != null
	if not carried:
		errors.append("THROW crouch melee must pick up the loose crate")
	if not thrown:
		errors.append("THROW grenade release must throw the carried crate")
	if still_carried:
		errors.append("THROW must release carry")
	if tx1 <= tx0 + 1.0:
		errors.append("THROW crate must leave its start x")
	outcome_throw = {
		"verdict": "pass" if carried and thrown and not still_carried else "fail",
		"carried": carried,
		"thrown": thrown,
		"x0": tx0,
		"x1": tx1,
		"source": "carry then grenade-release throw on # floor",
	}
	_remember_session(session)
	return errors


static func live_break(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_break_cover", 0)
	var session: GameSession = app.session
	var viewport: Viewport = app.get_viewport()
	await SimReplay.sync_physics(app)
	InputInjector.release_known(viewport)
	InputActions.reset_edges()
	used_parse_input_event += 1
	InputInjector.inject_key(KEY_M, true, viewport)
	var n: int = 0
	while n < 6:
		session.step_from_live_input()
		n += 1
	InputInjector.inject_key(KEY_M, false, viewport)
	session.step_from_live_input()
	n = 0
	while n < 28:
		session.step_from_live_input()
		n += 1
	var breaks: int = _count_kind(session, "break")
	if breaks != 1:
		errors.append("LIVE expected one break got %d" % breaks)
	InputInjector.release_known(viewport)
	outcome_live = {
		"verdict": "pass" if breaks == 1 else "fail",
		"breaks": breaks,
		"source": "parse_input_event KEY_M hold/release + step_from_live_input",
	}
	_remember_session(session)
	return errors


static func _require_outcomes() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var labels: PackedStringArray = PackedStringArray([
		"DATA", "BREAK", "DEBRIS", "PASS", "GHOST", "MELEE", "SHOVE", "THROW", "TACTIC", "LIVE"
	])
	var rows: Array = [
		outcome_data, outcome_break, outcome_debris, outcome_pass, outcome_ghost,
		outcome_melee, outcome_shove, outcome_throw, outcome_tactic, outcome_live
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


static func _count_kind(session: GameSession, kind: String) -> int:
	if session == null or session.ledger == null:
		return 0
	return session.ledger.count_kind(kind)


static func _count_debris(session: GameSession) -> int:
	var n: int = 0
	if _owner(session) == null:
		return 0
	var bodies: Array = _owner(session).get("bodies") as Array
	var i: int = 0
	while i < bodies.size():
		var body: Node2D = bodies[i] as Node2D
		if body != null and is_instance_valid(body):
			n += (body.get("debris") as Array).size()
		i += 1
	return n


static func _idle(session: GameSession, ticks: int) -> void:
	_apply_held(session, ticks, PackedStringArray())


static func _clear_wood_then_reach_loose(session: GameSession) -> void:
	# Wood sits on the walk lane; breaking it is the tactic that opens shove/throw.
	_walk_right(session, 12)
	_idle(session, 2)
	_press_melee(session)
	_idle(session, 16)
	_walk_right(session, 16)
	_idle(session, 2)


static func _walk_right(session: GameSession, ticks: int) -> void:
	_apply_held(session, ticks, PackedStringArray(["right"]))


static func _hold_fire(session: GameSession, ticks: int) -> void:
	_apply_held(session, ticks, PackedStringArray(["fire"]))


static func _release_fire(session: GameSession) -> void:
	_apply_edge(session, PackedStringArray(), PackedStringArray(["fire"]))


static func _press_melee(session: GameSession) -> void:
	_apply_edge(session, PackedStringArray(["melee"]), PackedStringArray())


static func _crouch_melee(session: GameSession) -> void:
	var frames: Array = []
	var i: int = 0
	while i < session.fighters.size():
		var d: Dictionary = InputActions.empty_frame(session.clock.tick, i)
		if i == 0:
			d["held"] = ["crouch"]
			d["pressed"] = ["melee"]
		frames.append(InputFrame.from_dict(d))
		i += 1
	_record_apply(session.apply_frames(frames))


static func _hold_nade(session: GameSession, ticks: int) -> void:
	_apply_held(session, ticks, PackedStringArray(["grenade"]))


static func _release_nade(session: GameSession) -> void:
	_apply_edge(session, PackedStringArray(), PackedStringArray(["grenade"]))


static func _apply_held(session: GameSession, ticks: int, held: PackedStringArray) -> void:
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


static func _apply_edge(session: GameSession, pressed: PackedStringArray, released: PackedStringArray) -> void:
	var frames: Array = []
	var i: int = 0
	while i < session.fighters.size():
		var d: Dictionary = InputActions.empty_frame(session.clock.tick, i)
		if i == 0:
			d["pressed"] = pressed
			d["released"] = released
		frames.append(InputFrame.from_dict(d))
		i += 1
	_record_apply(session.apply_frames(frames))


static func _drain_physics(app: App) -> void:
	InputActions.reset_edges()
	await SimReplay.sync_physics(app)
	await SimReplay.sync_physics(app)


static func _capture_start(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_break_cover", 0)
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

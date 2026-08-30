class_name HazardCases
extends RefCounted

const _Catalog: GDScript = preload("res://src/world/world_catalog.gd")
const _Hazard: GDScript = preload("res://src/world/prop_hazard.gd")

## VF4-WP3 official chain / fire / roll / hang cases.
## Proof is InputFrame apply_frames plus live InputEvent inject.
## 60 Hz is ledger:RL-SIM-FIXED-60 (assumption).
## Chain / fire / hang stay assumption. RL-NADE-PROP stays deferred.
## Extinguish rule is roll. Water is not selected.
## USED_APPLY_FRAMES counts success only.

static var used_step_fixed: int = 0
static var used_apply_frames: int = 0
static var used_apply_frames_attempted: int = 0
static var used_apply_frames_succeeded: int = 0
static var used_parse_input_event: int = 0
static var used_action_press: int = 0
static var outcome_data: Dictionary = {}
static var outcome_chain: Dictionary = {}
static var outcome_fire: Dictionary = {}
static var outcome_cleanup: Dictionary = {}
static var outcome_roll: Dictionary = {}
static var outcome_dup: Dictionary = {}
static var outcome_vfx: Dictionary = {}
static var outcome_hang: Dictionary = {}
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
	outcome_chain = {"verdict": "unproven"}
	outcome_fire = {"verdict": "unproven"}
	outcome_cleanup = {"verdict": "unproven"}
	outcome_roll = {"verdict": "unproven"}
	outcome_dup = {"verdict": "unproven"}
	outcome_vfx = {"verdict": "unproven"}
	outcome_hang = {"verdict": "unproven"}
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
	_append(errors, await seeded_chain(app))
	_append(errors, await fire_ticks_and_cleanup(app))
	_append(errors, await roll_extinguish(app))
	_append(errors, await live_chain(app))
	_append(errors, _require_outcomes())
	return errors


static func schema_and_data() -> PackedStringArray:
	var errors: PackedStringArray = _Catalog.validate()
	_append(errors, _Hazard.validate())
	if not Maps.has_fixture("fx_hazard_chain") or not Maps.has_fixture("fx_hazard_fire"):
		errors.append("hazard fixtures missing")
	if Maps.display_name("fx_hazard_chain") != "Blast Row":
		errors.append("chain fixture display name must be Blast Row")
	if Maps.display_name("fx_hazard_fire") != "Ember Walk":
		errors.append("fire fixture display name must be Ember Walk")
	if Maps.display_name("fx_hazard_yard") != "Drum Yard":
		errors.append("yard fixture display name must be Drum Yard")
	if Maps.display_name("fx_hazard_yard").to_lower().contains("superfighter"):
		errors.append("hazard fixture name must stay original")
	var live: Dictionary = _Catalog.data()
	var haz: Dictionary = _Hazard.data()
	if not bool(live.get("chain_implemented", false)):
		errors.append("DATA chain_implemented must be true")
	if str(live.get("nade_prop_class", "")) != "deferred":
		errors.append("DATA RL-NADE-PROP must stay deferred")
	if str(haz.get("extinguish_rule", "")) != "roll":
		errors.append("DATA extinguish rule must be roll")
	if bool(haz.get("water_selected", true)):
		errors.append("DATA water must stay unselected")
	if int(haz.get("chain_max_depth", 0)) != 2:
		errors.append("DATA chain_max_depth must be 2")
	if int(haz.get("vfx_cap", 0)) != 4:
		errors.append("DATA vfx_cap must be 4")
	outcome_data = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"chain_implemented": true,
		"nade_prop": "deferred",
		"extinguish_rule": "roll",
		"water_selected": false,
		"chain_max_depth": 2,
		"vfx_cap": 4,
		"source": "catalog + hazard.json Blast Row / Ember Walk / Drum Yard",
	}
	return errors


static func replay_traces_twice(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var paths: PackedStringArray = SimTrace.list_dir(SimConstants.HAZARD_TRACE_DIR)
	if paths.size() < 4:
		errors.append("expected >=4 hazard traces, got %d" % paths.size())
	var required: PackedStringArray = PackedStringArray([
		"hazard_chain", "hazard_fire", "hazard_roll", "hazard_hang"
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
			errors.append("hazard %s run1 failed: %s" % [path.get_file(), _join(a)])
		if not bool(b.get("ok", false)):
			errors.append("hazard %s run2 failed: %s" % [path.get_file(), _join(b)])
		if not bool(a.get("used_apply_frames", false)) or bool(a.get("used_cmd_dicts", true)):
			errors.append("hazard %s MATCH used cmd dicts" % path.get_file())
		var hash_a: String = str(a.get("final_hash", ""))
		var hash_b: String = str(b.get("final_hash", ""))
		var match_ok: bool = hash_a != "" and hash_a == hash_b
		var world_ok: bool = hash_wa != "" and hash_wa == hash_wb
		if not match_ok:
			errors.append("hazard %s replay hashes differ" % path.get_file())
		if not world_ok:
			errors.append("hazard %s world hashes differ" % path.get_file())
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
			errors.append("missing hazard trace %s" % String(required[i]))
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
		"source": "apply_frames hazard traces twice",
	}
	return errors


static func seeded_chain(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_hazard_chain", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var hang: Node2D = _find(session, "chain_hang")
	var y0: float = hang.global_position.y if hang != null else -1.0
	var hanging0: bool = hang != null and bool(hang.get("hanging"))
	if not hanging0:
		errors.append("HANG crate must start hanging")
	_hold_fire(session, 6)
	_release_fire(session)
	_idle(session, 36)
	var explodes: int = int(_owner(session).get("explode_events")) if _owner(session) != null else -1
	var depth: int = int(_owner(session).get("max_chain_seen")) if _owner(session) != null else -1
	var a_dead: bool = not _alive(session, "chain_a")
	var b_dead: bool = not _alive(session, "chain_b")
	var c_dead: bool = not _alive(session, "chain_c")
	var d_live: bool = _alive(session, "chain_d")
	var e_live: bool = _alive(session, "chain_e")
	if explodes != 3:
		errors.append("CHAIN expected 3 explosions got %d" % explodes)
	if depth != 2:
		errors.append("CHAIN max depth %d != 2" % depth)
	if not a_dead or not b_dead or not c_dead:
		errors.append("CHAIN first three drums must explode")
	if not d_live or not e_live:
		errors.append("CHAIN depth cap must leave drums d/e intact")
	var spawned: int = int(_owner(session).get("vfx_spawned")) if _owner(session) != null else -1
	var rejected: int = int(_owner(session).get("vfx_rejected")) if _owner(session) != null else -1
	var live_vfx: int = int(_owner(session).call("vfx_live_count")) if _owner(session) != null else -1
	if spawned < 1:
		errors.append("VFX must spawn at least one particle")
	if spawned > 4:
		errors.append("VFX spawned %d over cap 4" % spawned)
	if rejected < 1:
		errors.append("VFX cap must reject at least one particle")
	if live_vfx > 4:
		errors.append("VFX live count %d unbounded" % live_vfx)
	var hang2: Node2D = _find(session, "chain_hang")
	var hanging1: bool = hang2 != null and bool(hang2.get("hanging"))
	var y1: float = hang2.global_position.y if hang2 != null else y0
	var drops: int = _count_kind(session, "prop_drop")
	if hanging1:
		errors.append("HANG crate must drop after the chain")
	if y1 <= y0 + 2.0:
		errors.append("HANG crate must fall with impulse")
	if drops != 1:
		errors.append("HANG expected one prop_drop got %d" % drops)
	_hold_fire(session, 6)
	_release_fire(session)
	_idle(session, 20)
	var explodes2: int = int(_owner(session).get("explode_events")) if _owner(session) != null else -1
	if explodes2 != 3:
		errors.append("DUP second shot must not explode again got %d" % explodes2)
	outcome_chain = {
		"verdict": "pass" if explodes == 3 and depth == 2 and d_live and e_live else "fail",
		"events": explodes,
		"depth": depth,
		"alive_tail": 1 if d_live and e_live else 0,
		"source": "seeded pistol vs five Blast Drums, cap depth 2",
	}
	outcome_dup = {
		"verdict": "pass" if explodes2 == 3 else "fail",
		"events": explodes2,
		"source": "second shot against already-exploded drums",
	}
	outcome_vfx = {
		"verdict": "pass" if spawned >= 1 and spawned <= 4 and rejected >= 1 and live_vfx <= 4 else "fail",
		"spawned": spawned,
		"rejected": rejected,
		"live": live_vfx,
		"cap": 4,
		"source": "two flashes per explode, cap 4",
	}
	outcome_hang = {
		"verdict": "pass" if not hanging1 and y1 > y0 + 2.0 and drops == 1 else "fail",
		"y0": y0,
		"y1": y1,
		"drops": drops,
		"source": "Drop Cage released by chain blast",
	}
	_remember_session(session)
	return errors


static func fire_ticks_and_cleanup(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_hazard_fire", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	if p1 == null:
		errors.append("FIRE missing P1")
		outcome_fire = {"verdict": "fail"}
		outcome_cleanup = {"verdict": "fail"}
		return errors
	var hp0: float = p1.health
	_hold_fire(session, 6)
	_release_fire(session)
	_idle(session, 16)
	if not p1.burning:
		errors.append("FIRE P1 must ignite from the drum")
	var ticks0: int = _count_kind(session, "fire_tick")
	_idle(session, 36)
	var ticks1: int = _count_kind(session, "fire_tick")
	var hp1: float = p1.health
	if ticks1 < ticks0 + 2:
		errors.append("FIRE expected damage ticks got %d after %d" % [ticks1, ticks0])
	if hp1 >= hp0 - 0.01:
		errors.append("FIRE HP must drop from burn ticks")
	_idle(session, 24)
	var ended: int = _count_kind(session, "fire_end")
	var still: bool = p1.burning
	var live_vfx: int = int(_owner(session).call("vfx_live_count")) if _owner(session) != null else -1
	if still:
		errors.append("CLEANUP burn timer must expire")
	if ended < 1:
		errors.append("CLEANUP missing fire_end")
	if live_vfx > 4:
		errors.append("CLEANUP VFX still unbounded")
	outcome_fire = {
		"verdict": "pass" if ticks1 >= 2 and hp1 < hp0 - 0.01 else "fail",
		"ticks": ticks1,
		"hp0": hp0,
		"hp1": hp1,
		"source": "Ember Walk drum ignites P1; ticks subtract HP",
	}
	outcome_cleanup = {
		"verdict": "pass" if not still and ended >= 1 else "fail",
		"burning": still,
		"fire_end": ended,
		"vfx_live": live_vfx,
		"source": "burn timer expiry clears fire and VFX",
	}
	_remember_session(session)
	return errors


static func roll_extinguish(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_hazard_fire", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	if p1 == null:
		errors.append("ROLL missing P1")
		outcome_roll = {"verdict": "fail"}
		return errors
	_hold_fire(session, 6)
	_release_fire(session)
	_idle(session, 16)
	if not p1.burning:
		errors.append("ROLL P1 must be burning before the roll")
	var hp_mid: float = p1.health
	_apply_edge(session, PackedStringArray(["roll"]), PackedStringArray())
	_idle(session, 8)
	if p1.burning:
		errors.append("ROLL must extinguish fire")
	var ext: int = p1.fire_extinguish_count
	_idle(session, 24)
	if p1.health < hp_mid - 0.01 and p1.burning:
		errors.append("ROLL extinguished fighter must not keep ticking")
	outcome_roll = {
		"verdict": "pass" if not p1.burning and ext >= 1 else "fail",
		"burning": p1.burning,
		"extinguish_count": ext,
		"hp_mid": hp_mid,
		"hp_end": p1.health,
		"source": "selected extinguish rule is roll, not water",
	}
	_remember_session(session)
	return errors


static func live_chain(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_hazard_chain", 0)
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
	while n < 36:
		session.step_from_live_input()
		n += 1
	var explodes: int = int(_owner(session).get("explode_events")) if _owner(session) != null else -1
	if explodes != 3:
		errors.append("LIVE expected 3 explosions got %d" % explodes)
	InputInjector.release_known(viewport)
	outcome_live = {
		"verdict": "pass" if explodes == 3 else "fail",
		"events": explodes,
		"source": "parse_input_event KEY_M hold/release + step_from_live_input",
	}
	_remember_session(session)
	return errors


static func _require_outcomes() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var labels: PackedStringArray = PackedStringArray([
		"DATA", "CHAIN", "FIRE", "CLEANUP", "ROLL", "DUP", "VFX", "HANG", "LIVE"
	])
	var rows: Array = [
		outcome_data, outcome_chain, outcome_fire, outcome_cleanup, outcome_roll,
		outcome_dup, outcome_vfx, outcome_hang, outcome_live
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


static func _alive(session: GameSession, pid: String) -> bool:
	var body: Node2D = _find(session, pid)
	return body != null and bool(body.get("alive"))


static func _count_kind(session: GameSession, kind: String) -> int:
	if session == null or session.ledger == null:
		return 0
	return session.ledger.count_kind(kind)


static func _idle(session: GameSession, ticks: int) -> void:
	_apply_held(session, ticks, PackedStringArray())


static func _hold_fire(session: GameSession, ticks: int) -> void:
	_apply_held(session, ticks, PackedStringArray(["fire"]))


static func _release_fire(session: GameSession) -> void:
	_apply_edge(session, PackedStringArray(), PackedStringArray(["fire"]))


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
	app.start_fight("vs2", "fx_hazard_yard", 0)
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

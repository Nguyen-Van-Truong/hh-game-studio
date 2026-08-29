class_name SimReplay
extends RefCounted

## Replay typed InputFrame traces through GameSession.apply_frames.
## Official path never calls step_fixed with cmd dicts, teleport, or force_kill.
## Clock: ledger:RL-SIM-FIXED-60 (assumption). Hold-to-aim stays
## ledger:RL-CTRL-HOLD-AIM (assumption). Roll is ledger:RL-MOVE-ROLL
## (assumption). Dive/kick stay ledger:RL-MOVE-DIVE /
## RL-MOVE-JUMP-KICK (assumption). Y8 observation stays
## ledger:RL-MOVE-ROLL-DIVE (unavailable).


static func supports_window() -> bool:
	return true


static func window_requested() -> bool:
	return OS.get_environment("HH_VF_TRACE_WINDOW") == "1"


static func play(app: App, trace: Dictionary) -> Dictionary:
	var result: Dictionary = _empty_result()
	var errors: PackedStringArray = SimTrace.validate(trace)
	if not errors.is_empty():
		result["errors"] = errors
		result["ok"] = false
		return result
	var official: bool = SimTrace.is_official(trace)
	if official:
		var forbidden: PackedStringArray = SimTrace.official_forbidden(trace)
		if not forbidden.is_empty():
			result["errors"] = forbidden
			result["ok"] = false
			return result
	var mode: String = str(trace.get("mode", "vs2"))
	var map_id: String = str(trace.get("map_id", "police"))
	var stage: int = int(trace.get("stage_index", 0))
	var ops: Array = trace.get("app_ops", []) as Array
	var fixture_ops: Array = trace.get("fixture_ops", []) as Array
	if _has_op(ops, "title_to_fight"):
		if app.title != null:
			app.title.visible = true
		app.restart_to_title()
		app.start_fight(mode, map_id, stage)
		_log_app(app, "title_to_fight", mode, map_id, stage)
	else:
		app.start_fight(mode, map_id, stage)
	var session: GameSession = app.session
	if session == null:
		errors.append("replay missing session")
		result["errors"] = errors
		result["ok"] = false
		return result
	var expected_seed: int = int(trace.get("seed", SimSeed.for_match(mode, map_id, stage)))
	if session.sim_seed != expected_seed:
		errors.append("seed drifted got=%d expected=%d" % [session.sim_seed, expected_seed])
	if bool(trace.get("chaos", false)):
		session.chaos_enabled = true
		session.reset_chaos_rng()
	await sync_physics(app)
	session = app.session
	if session == null:
		errors.append("session lost after physics sync")
		result["errors"] = errors
		result["ok"] = false
		return result
	_push_hash(result, session, true)
	var bundles: Array = SimTrace.expand_tick_bundles(trace)
	var i: int = 0
	while i < bundles.size():
		if official and _ops_at(fixture_ops, i):
			errors.append("official replay refused fixture op at tick %d" % i)
			break
		if not official:
			_apply_fixture_ops(session, fixture_ops, i)
		var typed: Array = SimTrace.to_input_frames(bundles[i] as Array)
		if typed.size() != session.fighters.size():
			errors.append(
				"frame count %d != fighters %d at tick %d"
				% [typed.size(), session.fighters.size(), i]
			)
			break
		var applied: bool = session.apply_frames(typed)
		if not applied:
			errors.append("apply_frames rejected tick %d: %s" % [
				i, ",".join(session.last_reject)
			])
			break
		var ended: bool = session.outcome != "play"
		_push_hash(result, session, false, SimTrace.snapshot_every(trace), ended or i + 1 == bundles.size())
		i += 1
		if ended:
			break
	session = app.session
	if session != null:
		result["final_hash"] = session.snapshot_hash()
		result["final_state"] = session.snapshot()
		if session.ledger != null:
			result["events"] = session.ledger.to_array()
			result["events_hash"] = session.ledger.stable_hash()
			if official and session.ledger.has_forbidden_official():
				errors.append("official replay ledger contains teleport or force_kill")
	if _has_op(ops, "restart_to_title"):
		_log_app(app, "restart_to_title", mode, map_id, stage)
		if session != null and session.ledger != null:
			result["events"] = session.ledger.to_array()
			result["events_hash"] = session.ledger.stable_hash()
		app.restart_to_title()
		result["title_visible"] = app.title != null and app.title.visible
		result["session_cleared"] = app.session == null
	elif _has_op(ops, "restart_same"):
		_log_app(app, "restart_same", mode, map_id, stage)
		app.restart_same()
		result["session_cleared"] = false
		if app.session != null:
			result["restarted_outcome"] = app.session.outcome
	result["errors"] = errors
	result["ok"] = errors.is_empty()
	result["ticks"] = i
	result["used_apply_frames"] = true
	result["used_cmd_dicts"] = false
	if app.session != null:
		app.release_session()
	return result


static func sync_physics(app: App) -> void:
	if app == null:
		return
	var tree: SceneTree = app.get_tree()
	if tree == null:
		return
	await tree.physics_frame
	await tree.physics_frame


static func play_path(app: App, path: String) -> Dictionary:
	var trace: Dictionary = SimTrace.load_path(path)
	if trace.is_empty():
		var result: Dictionary = _empty_result()
		var errors: PackedStringArray = PackedStringArray()
		errors.append("failed to load %s" % path)
		result["errors"] = errors
		result["ok"] = false
		result["path"] = path
		return result
	var played: Dictionary = await play(app, trace)
	played["path"] = path
	played["name"] = str(trace.get("name", path.get_file()))
	played["kind"] = str(trace.get("kind", ""))
	return played


static func _empty_result() -> Dictionary:
	return {
		"ok": false,
		"errors": PackedStringArray(),
		"hashes": [],
		"final_hash": "",
		"final_state": {},
		"events": [],
		"events_hash": "",
		"ticks": 0,
		"used_apply_frames": true,
		"used_cmd_dicts": false,
	}


static func _push_hash(result: Dictionary, session: GameSession, force: bool, every: int = 15, last: bool = false) -> void:
	if session == null:
		return
	var tick: int = 0
	if session.clock != null:
		tick = session.clock.tick
	if not force and not last and every > 0 and tick % every != 0:
		return
	var hashes: Array = result.get("hashes", []) as Array
	hashes.append({
		"tick": tick,
		"hash": session.snapshot_hash(),
	})
	result["hashes"] = hashes


static func _has_op(ops: Array, name: String) -> bool:
	var i: int = 0
	while i < ops.size():
		var row: Dictionary = ops[i] as Dictionary
		if str(row.get("op", "")) == name:
			return true
		i += 1
	return false


static func _ops_at(ops: Array, tick: int) -> bool:
	var i: int = 0
	while i < ops.size():
		var row: Dictionary = ops[i] as Dictionary
		if int(row.get("tick", -1)) == tick:
			return true
		i += 1
	return false


static func _apply_fixture_ops(session: GameSession, ops: Array, tick: int) -> void:
	var i: int = 0
	while i < ops.size():
		var row: Dictionary = ops[i] as Dictionary
		if int(row.get("tick", -1)) != tick:
			i += 1
			continue
		var op: String = str(row.get("op", ""))
		var slot: int = int(row.get("slot", 0))
		if op == "teleport":
			_teleport(session, slot, float(row.get("x", 0.0)), float(row.get("y", 0.0)))
		elif op == "force_kill":
			session.force_kill(slot)
		i += 1


static func _teleport(session: GameSession, slot: int, x: float, y: float) -> void:
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		if f != null and f.slot == slot:
			f.global_position = Vector2(x, y)
			f.velocity = Vector2.ZERO
			if session.ledger != null:
				session.ledger.push(session.clock.tick, "fixture", "teleport", {
					"slot": slot,
					"x": SimConstants.quantize(x),
					"y": SimConstants.quantize(y),
				})
			return
		i += 1


static func _log_app(app: App, kind: String, mode: String, map_id: String, stage: int) -> void:
	if app.session == null or app.session.ledger == null:
		return
	var tick: int = 0
	if app.session.clock != null:
		tick = app.session.clock.tick
	app.session.ledger.push(tick, "app", kind, {
		"mode": mode,
		"map_id": map_id,
		"stage": stage,
	})

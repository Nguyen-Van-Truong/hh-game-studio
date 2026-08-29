class_name RuntimeApi
extends RefCounted

## Structured observe + checkpoint API. Agents read this instead of UI pixels.
## Token is never echoed (V-A8). 60 Hz cites ledger:RL-SIM-FIXED-60.


var app: App = null
var _token: String = ""
var _store: Dictionary = {}
var _acks: Dictionary = {}


func bind(p_app: App, token: String) -> void:
	app = p_app
	_token = token


func handle(raw: Variant) -> Dictionary:
	var before: Dictionary = _fingerprint()
	var parsed: Dictionary = _parse(raw)
	var errors: PackedStringArray = parsed.get("errors", PackedStringArray()) as PackedStringArray
	var req: Dictionary = parsed.get("request", {}) as Dictionary
	if not errors.is_empty():
		return _finish(_reject(req, RuntimeConstants.ERR_MALFORMED, errors), before, true)
	if not _authorized(req):
		return _finish(_reject(req, RuntimeConstants.ERR_UNAUTHORIZED, PackedStringArray(["unauthorized"])), before, true)
	var command_id: String = str(req.get("command_id", ""))
	var op: String = str(req.get("op", ""))
	if RuntimeConstants.op_mutates_game(op) and _acks.has(command_id):
		return (_acks[command_id] as Dictionary).duplicate(true)
	var response: Dictionary = _dispatch(req)
	if RuntimeConstants.op_mutates_game(op) and bool(response.get("ok", false)):
		_acks[command_id] = response.duplicate(true)
	var must_freeze: bool = not RuntimeConstants.op_mutates_game(op)
	return _finish(response, before, must_freeze)


func _dispatch(req: Dictionary) -> Dictionary:
	var op: String = str(req.get("op", ""))
	if op == RuntimeConstants.OP_OBSERVE:
		return _ok(req, {"observe": observe()})
	if op == RuntimeConstants.OP_CHECKPOINT_CREATE:
		return _checkpoint_create(req)
	if op == RuntimeConstants.OP_CHECKPOINT_RESTORE:
		return _checkpoint_restore(req)
	if op == RuntimeConstants.OP_PAUSE:
		return _set_pause(req, true)
	if op == RuntimeConstants.OP_RESUME:
		return _set_pause(req, false)
	return _reject(req, RuntimeConstants.ERR_UNSUPPORTED, PackedStringArray(["unknown op"]))


func observe() -> Dictionary:
	var session: GameSession = _session()
	var snap: Dictionary = {}
	var digest: String = ""
	var events: Dictionary = {
		"actor": [],
		"weapon": [],
		"prop": [],
	}
	var tick: int = 0
	var paused: bool = false
	var pause_reason: String = ""
	var seed_v: int = 0
	var map_id: String = ""
	var mode: String = ""
	var outcome: String = ""
	var stage_index: int = 0
	if app != null:
		map_id = app.map_id
		mode = app.mode
		stage_index = app.stage_index
	if session != null:
		snap = session.snapshot()
		digest = session.snapshot_hash()
		events = _categorize(session.ledger.to_array() if session.ledger != null else [])
		if session.clock != null:
			tick = session.clock.tick
			paused = session.clock.paused
		pause_reason = session.pause_reason
		seed_v = session.sim_seed
		map_id = session.map_id
		mode = session.mode
		outcome = session.outcome
		stage_index = session.stage_index
	return {
		"schema": RuntimeConstants.OBSERVE_ID,
		"schema_version": RuntimeConstants.SCHEMA_VERSION,
		"title": "Vault Fighters",
		"seed": seed_v,
		"map_id": map_id,
		"mode": mode,
		"stage_index": stage_index,
		"tick": tick,
		"paused": paused,
		"pause_reason": pause_reason,
		"outcome": outcome,
		"snapshot": snap,
		"snapshot_hash": digest,
		"events": events,
		"actors": snap.get("fighters", []),
		"weapons": _weapon_view(session, snap),
		"props": _prop_view(session),
		"ui": _ui_flags(),
		"diagnostics": _diagnostics(session),
		"honesty": {
			"y8_parity": false,
			"tick_hz": "ledger:RL-SIM-FIXED-60 assumption",
			"hold_to_aim": "ledger:RL-CTRL-HOLD-AIM assumption",
			"roll": "ledger:RL-MOVE-ROLL assumption",
			"sprint": "ledger:RL-MOVE-SPRINT assumption",
			"dive": "ledger:RL-MOVE-DIVE assumption",
			"kick": "ledger:RL-MOVE-JUMP-KICK assumption",
			"ladder": "ledger:RL-MOVE-LADDER assumption",
			"ledge": "ledger:RL-MOVE-LEDGE assumption",
			"drop": "ledger:RL-MOVE-DROP assumption",
			"roll_dive": "ledger:RL-MOVE-ROLL-DIVE Y8 observation unavailable",
			"prop_events": "schema-owned; break deferred VF4-WP2",
		},
	}


func _checkpoint_create(req: Dictionary) -> Dictionary:
	var session: GameSession = _session()
	if session == null:
		return _reject(req, RuntimeConstants.ERR_NOT_FOUND, PackedStringArray(["no session"]))
	var payload: Dictionary = req.get("payload", {}) as Dictionary
	var checkpoint_id: String = str(payload.get("checkpoint_id", ""))
	if checkpoint_id.is_empty():
		checkpoint_id = "cp-%s" % str(req.get("command_id", "anon")).replace(":", "-")
	if not RuntimeConstants.checkpoint_id_ok(checkpoint_id):
		return _reject(req, RuntimeConstants.ERR_MALFORMED, PackedStringArray(["bad checkpoint_id"]))
	var body: Dictionary = RuntimeCheckpoint.capture(session)
	body["id"] = checkpoint_id
	_store[checkpoint_id] = body
	var stored_path: String = RuntimeCheckpoint.persist_atomic(checkpoint_id, body)
	return _ok(req, {
		"checkpoint_id": checkpoint_id,
		"snapshot_hash": str(body.get("snapshot_hash", "")),
		"store": stored_path,
	})


func _checkpoint_restore(req: Dictionary) -> Dictionary:
	var payload: Dictionary = req.get("payload", {}) as Dictionary
	var checkpoint_id: String = str(payload.get("checkpoint_id", ""))
	if not RuntimeConstants.checkpoint_id_ok(checkpoint_id):
		return _reject(req, RuntimeConstants.ERR_MALFORMED, PackedStringArray(["bad checkpoint_id"]))
	var body: Dictionary = {}
	if _store.has(checkpoint_id):
		body = (_store[checkpoint_id] as Dictionary).duplicate(true)
	else:
		body = RuntimeCheckpoint.load_persisted(checkpoint_id)
	if body.is_empty():
		return _reject(req, RuntimeConstants.ERR_NOT_FOUND, PackedStringArray(["checkpoint missing"]))
	if app == null:
		return _reject(req, RuntimeConstants.ERR_NOT_FOUND, PackedStringArray(["app missing"]))
	var snap: Dictionary = body.get("snapshot", {}) as Dictionary
	var mode: String = str(snap.get("mode", app.mode))
	var map_id: String = str(snap.get("map_id", app.map_id))
	var stage_index: int = int(body.get("stage_index", app.stage_index))
	app.start_fight(mode, map_id, stage_index)
	var session: GameSession = _session()
	if session == null:
		return _reject(req, RuntimeConstants.ERR_NOT_FOUND, PackedStringArray(["restore session missing"]))
	var apply_errors: PackedStringArray = RuntimeCheckpoint.apply(session, body)
	if not apply_errors.is_empty():
		return _reject(req, RuntimeConstants.ERR_MALFORMED, apply_errors)
	var clock_row: Dictionary = body.get("clock", {}) as Dictionary
	var want_pause: bool = bool(clock_row.get("paused", false))
	var reason: String = str(body.get("pause_reason", ""))
	session.set_paused(want_pause, reason if want_pause else "")
	if session.clock != null:
		session.clock.tick = int(clock_row.get("tick", snap.get("tick", session.clock.tick)))
		session.clock.accum = float(clock_row.get("accum", 0.0))
		session.clock.paused = want_pause
	session.pause_reason = reason if want_pause else ""
	var digest: String = session.snapshot_hash()
	var expected: String = str(body.get("snapshot_hash", ""))
	if digest != expected:
		return _reject(req, RuntimeConstants.ERR_MALFORMED, PackedStringArray([
			"restore hash mismatch",
		]))
	return _ok(req, {
		"checkpoint_id": checkpoint_id,
		"snapshot_hash": digest,
	})


func _set_pause(req: Dictionary, active: bool) -> Dictionary:
	var session: GameSession = _session()
	if session == null:
		return _reject(req, RuntimeConstants.ERR_NOT_FOUND, PackedStringArray(["no session"]))
	var payload: Dictionary = req.get("payload", {}) as Dictionary
	var reason: String = str(payload.get("reason", RuntimeConstants.REASON_AGENT))
	if reason != RuntimeConstants.REASON_AGENT and reason != RuntimeConstants.REASON_PLAYER:
		reason = RuntimeConstants.REASON_AGENT
	session.set_paused(active, reason if active else "")
	return _ok(req, {})


func _parse(raw: Variant) -> Dictionary:
	var errors: PackedStringArray = PackedStringArray()
	var req: Dictionary = {}
	if raw == null or not (raw is Dictionary):
		errors.append("request is not an object")
		return {"request": req, "errors": errors}
	req = raw as Dictionary
	if str(req.get("schema", "")) != RuntimeConstants.REQUEST_ID:
		errors.append("schema must be vf.runtime.request.v1")
	if req.has("schema_version") and int(req.get("schema_version", -1)) != RuntimeConstants.SCHEMA_VERSION:
		errors.append("schema_version mismatch")
	var command_id: String = str(req.get("command_id", ""))
	if not RuntimeConstants.command_id_ok(command_id):
		errors.append("bad command_id")
	var op: String = str(req.get("op", ""))
	if not RuntimeConstants.is_known_op(op):
		errors.append("unknown op")
	if req.has("auth") and not (req.get("auth") is Dictionary):
		errors.append("auth must be an object")
	if req.has("payload") and not (req.get("payload") is Dictionary):
		errors.append("payload must be an object")
	if req.has("path"):
		errors.append("client filesystem path is not allowed")
	return {"request": req, "errors": errors}


func _authorized(req: Dictionary) -> bool:
	if _token.is_empty():
		return false
	var auth: Dictionary = req.get("auth", {}) as Dictionary
	var given: String = str(auth.get("token", ""))
	return given == _token


func _ok(req: Dictionary, extra: Dictionary) -> Dictionary:
	var session: GameSession = _session()
	var body: Dictionary = {
		"schema": RuntimeConstants.RESPONSE_ID,
		"ok": true,
		"command_id": str(req.get("command_id", "")),
		"op": str(req.get("op", "")),
		"error_code": "",
		"errors": [],
		"snapshot_hash": session.snapshot_hash() if session != null else "",
		"tick": session.clock.tick if session != null and session.clock != null else 0,
		"paused": session.clock.paused if session != null and session.clock != null else false,
		"pause_reason": session.pause_reason if session != null else "",
		"seed": session.sim_seed if session != null else 0,
		"map_id": session.map_id if session != null else (app.map_id if app != null else ""),
		"mode": session.mode if session != null else (app.mode if app != null else ""),
	}
	var keys: Array = extra.keys()
	var i: int = 0
	while i < keys.size():
		body[keys[i]] = extra[keys[i]]
		i += 1
	return body


func _reject(req: Dictionary, code: String, errors: PackedStringArray) -> Dictionary:
	var listed: Array = []
	var i: int = 0
	while i < errors.size():
		listed.append(String(errors[i]))
		i += 1
	return {
		"schema": RuntimeConstants.RESPONSE_ID,
		"ok": false,
		"command_id": str(req.get("command_id", "")),
		"op": str(req.get("op", "")),
		"error_code": code,
		"errors": listed,
	}


func _finish(response: Dictionary, before: Dictionary, freeze: bool) -> Dictionary:
	var cleaned: Variant = RuntimeRedact.apply(response, _token)
	var out: Dictionary = cleaned as Dictionary
	if freeze and not _same_fingerprint(before, _fingerprint()):
		out["ok"] = false
		out["error_code"] = RuntimeConstants.ERR_MALFORMED
		var listed: Array = out.get("errors", []) as Array
		listed.append("read-only request mutated state")
		out["errors"] = listed
	return out


func _fingerprint() -> Dictionary:
	var session: GameSession = _session()
	if session == null:
		return {"present": 0, "tick": -1, "hash": "", "paused": 0, "x": 0}
	var p1: Fighter = session.player1()
	return {
		"present": 1,
		"tick": session.clock.tick if session.clock != null else -1,
		"hash": session.snapshot_hash(),
		"paused": 1 if session.clock != null and session.clock.paused else 0,
		"x": SimConstants.quantize(p1.global_position.x) if p1 != null else 0,
	}


func _same_fingerprint(a: Dictionary, b: Dictionary) -> bool:
	return (
		int(a.get("present", 0)) == int(b.get("present", 0))
		and int(a.get("tick", 0)) == int(b.get("tick", 0))
		and str(a.get("hash", "")) == str(b.get("hash", ""))
		and int(a.get("paused", 0)) == int(b.get("paused", 0))
		and int(a.get("x", 0)) == int(b.get("x", 0))
	)


func _session() -> GameSession:
	if app == null:
		return null
	return app.session


func _ui_flags() -> Dictionary:
	if app == null:
		return {"title": false, "win": false, "lose": false, "pause": false}
	var pause_vis: bool = false
	if app.session != null and app.session.pause_screen != null:
		pause_vis = app.session.pause_screen.visible
	return {
		"title": app.title != null and app.title.visible,
		"win": app.win_screen != null and app.win_screen.visible,
		"lose": app.lose_screen != null and app.lose_screen.visible,
		"pause": pause_vis,
	}


func _diagnostics(session: GameSession) -> Dictionary:
	var rejects: Array = []
	var event_count: int = 0
	if session != null:
		var i: int = 0
		while i < session.last_reject.size():
			rejects.append(String(session.last_reject[i]))
			i += 1
		if session.ledger != null:
			event_count = session.ledger.events.size()
	return {
		"last_reject": rejects,
		"event_count": event_count,
		"session": session != null,
	}


func _prop_view(session: GameSession) -> Array:
	if session == null or session.world_owner == null:
		return []
	var rows: Variant = session.world_owner.call("snapshot")
	if rows is Array:
		return rows as Array
	return []


func _weapon_view(session: GameSession, snap: Dictionary) -> Array:
	var out: Array = []
	var pickups: Array = snap.get("pickups", []) as Array
	var i: int = 0
	while i < pickups.size():
		var row: Dictionary = (pickups[i] as Dictionary).duplicate(true)
		row["kind"] = "pickup"
		out.append(row)
		i += 1
	if session == null:
		return out
	i = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		if f != null and is_instance_valid(f):
			out.append({
				"kind": "loadout",
				"slot": f.slot,
				"weapon": f.weapon_id,
				"gun": f.gun_id,
				"melee": f.melee_id,
				"nades": f.grenades,
				"ammo": f.ammo,
				"explosive": f.explosive_id,
				"power": f.power_id,
				"power_ammo": f.power_ammo,
			})
		i += 1
	return out


func _categorize(events: Array) -> Dictionary:
	var actor: Array = []
	var weapon: Array = []
	var prop: Array = []
	var i: int = 0
	while i < events.size():
		var row: Dictionary = events[i] as Dictionary
		var phase: String = str(row.get("phase", ""))
		var kind: String = str(row.get("kind", ""))
		if phase == "melee" or phase == "match_resolve" or kind == "hit" or kind == "death" or kind == "win" or kind == "lose":
			actor.append(row)
		elif (
			phase == "fire_spawn"
			or phase == "grenade_spawn"
			or phase == "weapon_respawn"
			or kind == "bullet"
			or kind == "nade"
		):
			weapon.append(row)
		elif phase.begins_with("prop") or kind.begins_with("prop"):
			prop.append(row)
		i += 1
	return {
		"actor": actor,
		"weapon": weapon,
		"prop": prop,
	}

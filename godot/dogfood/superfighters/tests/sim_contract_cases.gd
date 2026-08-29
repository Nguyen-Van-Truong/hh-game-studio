class_name SimContractCases
extends RefCounted

const STEP: float = 1.0 / 60.0


static func run_all(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	_append(errors, schema_and_layers())
	_append(errors, hash_three_runs(app))
	_append(errors, pause_does_not_jump_tick(app))
	_append(errors, malformed_rejected(app))
	_append(errors, snapshot_is_pure(app))
	return errors


static func schema_and_layers() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	if not SimCollisionLayers.matches_maps():
		errors.append("collision layers != Maps.COL_*")
	if not SimEventOrder.is_ordered():
		errors.append("event order is not strictly ordered")
	var schema: Dictionary = SimConstants.load_json(SimConstants.SCHEMA_PATH)
	if schema.is_empty():
		errors.append("missing data/sim/schema.json")
		return errors
	if int(schema.get("schema_version", 0)) != SimConstants.SCHEMA_VERSION:
		errors.append("schema_version mismatch")
	if int(schema.get("tick_hz", 0)) != SimConstants.TICK_HZ:
		errors.append("tick_hz must be 60")
	if bool(schema.get("y8_tick_rate_claimed", true)):
		errors.append("schema must not claim a Y8 tick rate")
	if str(schema.get("title", "")) != "Vault Fighters":
		errors.append("schema title must be Vault Fighters")
	var layers: Dictionary = SimConstants.load_json(SimConstants.LAYERS_PATH)
	var layer_map: Dictionary = layers.get("layers", {}) as Dictionary
	if int(layer_map.get("world", 0)) != SimCollisionLayers.WORLD:
		errors.append("collision_layers.json world bit mismatch")
	var actions: Dictionary = SimConstants.load_json(SimConstants.ACTIONS_PATH)
	var allowed: Array = actions.get("allowed", []) as Array
	if allowed.size() != SimValidator.ALLOWED.size():
		errors.append("input_actions.json allowed count mismatch")
	var order: Dictionary = SimConstants.load_json(SimConstants.EVENT_ORDER_PATH)
	var phases: Array = order.get("phases", []) as Array
	if phases.size() != SimEventOrder.PHASES.size():
		errors.append("event_order.json phase count mismatch")
	return errors


static func hash_three_runs(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var hashes: PackedStringArray = PackedStringArray()
	var r: int = 0
	while r < 3:
		app.start_fight("vs1", "rooftops", 0)
		var session: GameSession = app.session
		if session == null:
			errors.append("hash run %d missing session" % r)
			return errors
		if session.sim_seed != SimSeed.for_match("vs1", "rooftops", 0):
			errors.append("hash run %d seed drifted" % r)
		_drive_trace(session)
		var digest: String = session.snapshot_hash()
		if digest.length() != 64:
			errors.append("hash run %d digest length %d" % [r, digest.length()])
		hashes.append(digest)
		r += 1
	if hashes.size() != 3:
		errors.append("expected 3 hashes")
		return errors
	if hashes[0] != hashes[1] or hashes[1] != hashes[2]:
		errors.append("seed+trace hashes differ: %s %s %s" % [hashes[0], hashes[1], hashes[2]])
	return errors


static func pause_does_not_jump_tick(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs1", "rooftops", 0)
	var session: GameSession = app.session
	_idle(session, 12)
	var t0: int = session.clock.tick
	if t0 != 12:
		errors.append("expected tick 12 after 12 steps, got %d" % t0)
	session.set_paused(true)
	if not session.clock.paused:
		errors.append("clock not paused")
	var jumped: int = session.clock.feed(2.0)
	if jumped != 0:
		errors.append("paused clock.feed produced %d ticks" % jumped)
	if session.clock.tick != t0:
		errors.append("pause jumped tick %d -> %d" % [t0, session.clock.tick])
	session.step_fixed(STEP, _idle_cmds(session))
	if session.clock.tick != t0:
		errors.append("step_fixed while paused advanced tick")
	var p1: Fighter = session.player1()
	var x0: float = p1.global_position.x if p1 != null else 0.0
	session.set_paused(false)
	if session.clock.paused:
		errors.append("clock still paused after resume")
	if absf(session.clock.accum) > SimConstants.ACCUM_EPS:
		errors.append("resume left leftover accum")
	if session.clock.tick != t0:
		errors.append("resume jumped tick %d -> %d" % [t0, session.clock.tick])
	session.step_fixed(STEP, _idle_cmds(session))
	if session.clock.tick != t0 + 1:
		errors.append("resume next tick was %d not %d" % [session.clock.tick, t0 + 1])
	if p1 != null and p1.global_position.x == x0 and t0 < 0:
		errors.append("sanity")
	return errors


static func malformed_rejected(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs1", "rooftops", 0)
	var session: GameSession = app.session
	_idle(session, 4)
	var tick: int = session.clock.tick
	var p1: Fighter = session.player1()
	var x0: float = p1.global_position.x if p1 != null else 0.0
	var cases: Array = [
		{},
		{"tick": -1, "slot": 0, "held": [], "pressed": [], "released": []},
		{"tick": tick, "slot": 0, "held": ["ledge"], "pressed": [], "released": []},
		{"tick": tick, "slot": 0, "held": "fire", "pressed": [], "released": []},
		{"tick": tick, "slot": 0, "held": [], "pressed": [], "released": [], "move_x": NAN},
		{"tick": tick + 3, "slot": 0, "held": [], "pressed": [], "released": []},
	]
	var i: int = 0
	while i < cases.size():
		var bundle: Array = _idle_frames(session)
		bundle[0] = cases[i]
		var ok: bool = session.apply_frames(bundle)
		if ok:
			errors.append("malformed case %d was accepted" % i)
		if session.last_reject.is_empty():
			errors.append("malformed case %d left last_reject empty" % i)
		if session.clock.tick != tick:
			errors.append("malformed case %d advanced tick" % i)
			tick = session.clock.tick
		if p1 != null and absf(p1.global_position.x - x0) > 0.0001:
			errors.append("malformed case %d mutated P1 x" % i)
			x0 = p1.global_position.x
		i += 1
	var empty_err: PackedStringArray = SimValidator.validate_frame(null, 0)
	if empty_err.is_empty():
		errors.append("null frame was accepted")
	return errors


static func snapshot_is_pure(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs1", "rooftops", 0)
	var session: GameSession = app.session
	_drive_trace(session)
	var p1: Fighter = session.player1()
	var tick: int = session.clock.tick
	var x0: float = p1.global_position.x if p1 != null else 0.0
	var h1: String = session.snapshot_hash()
	var h2: String = session.snapshot_hash()
	if h1 != h2:
		errors.append("snapshot_hash mutated between calls")
	if session.clock.tick != tick:
		errors.append("snapshot advanced tick")
	if p1 != null and absf(p1.global_position.x - x0) > 0.0:
		errors.append("snapshot moved P1")
	var snap: Dictionary = session.snapshot()
	if str(snap.get("schema", "")) != SimConstants.SNAPSHOT_ID:
		errors.append("snapshot missing schema id")
	if int(snap.get("seed", -1)) != session.sim_seed:
		errors.append("snapshot seed missing")
	return errors


static func _drive_trace(session: GameSession) -> void:
	_idle(session, 8)
	var n: int = 0
	while n < 24:
		var cmds: Array[Dictionary] = _idle_cmds(session)
		cmds[0]["x"] = 1.0
		session.step_fixed(STEP, cmds)
		n += 1
	_idle(session, 8)
	n = 0
	while n < 8:
		var crouch: Array[Dictionary] = _idle_cmds(session)
		crouch[0]["crouch"] = true
		session.step_fixed(STEP, crouch)
		n += 1


static func _idle(session: GameSession, frames: int) -> void:
	var n: int = 0
	while n < frames:
		session.step_fixed(STEP, _idle_cmds(session))
		n += 1


static func _idle_cmds(session: GameSession) -> Array[Dictionary]:
	var cmds: Array[Dictionary] = []
	var i: int = 0
	while i < session.fighters.size():
		cmds.append(InputActions.empty_cmd())
		i += 1
	return cmds


static func _idle_frames(session: GameSession) -> Array:
	var frames: Array = []
	var i: int = 0
	while i < session.fighters.size():
		frames.append(InputActions.empty_frame(session.clock.tick, i))
		i += 1
	return frames


static func _append(into: PackedStringArray, extra: PackedStringArray) -> void:
	var i: int = 0
	while i < extra.size():
		into.append(String(extra[i]))
		i += 1

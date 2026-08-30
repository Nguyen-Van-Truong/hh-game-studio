class_name RuntimeCases
extends RefCounted

const STEP: float = 1.0 / 60.0
const TOKEN: String = "test-fixture-not-a-secret"
const _Combat: GDScript = preload("res://src/sim/combat.gd")
const _World: GDScript = preload("res://src/world/world_catalog.gd")


static func run_all(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	_bind(app)
	_append(errors, schema_files())
	_append(errors, observe_is_structured(app))
	_append(errors, snapshot_pause_stable(app))
	_append(errors, snapshot_restart_fresh(app))
	_append(errors, checkpoint_restore_hash(app))
	_append(errors, malformed_does_not_mutate(app))
	_append(errors, unauthorized_does_not_mutate(app))
	_append(errors, secrets_are_redacted(app))
	return errors


static func schema_files() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var schema: Dictionary = SimConstants.load_json(RuntimeConstants.SCHEMA_PATH)
	if schema.is_empty():
		errors.append("missing data/runtime/schema.json")
		return errors
	if str(schema.get("schema", "")) != RuntimeConstants.SCHEMA_ID:
		errors.append("runtime schema id mismatch")
	if str(schema.get("title", "")) != "Vault Fighters":
		errors.append("runtime schema title must be Vault Fighters")
	if bool(schema.get("y8_tick_rate_claimed", true)):
		errors.append("runtime schema must not claim a Y8 tick rate")
	if str(schema.get("ledger_clock", "")) != "RL-SIM-FIXED-60":
		errors.append("runtime schema must cite RL-SIM-FIXED-60")
	var bridge: Dictionary = SimConstants.load_json(RuntimeConstants.BRIDGE_PATH)
	if bridge.is_empty():
		errors.append("missing data/runtime/bridge.json")
		return errors
	var ops: Dictionary = bridge.get("ops", {}) as Dictionary
	if not ops.has("observe") or not ops.has("checkpoint.create") or not ops.has("checkpoint.restore"):
		errors.append("bridge schema missing observe/checkpoint ops")
	if bool((ops.get("observe", {}) as Dictionary).get("mutate", true)):
		errors.append("observe must be read-only in bridge schema")
	if bool((ops.get("checkpoint.create", {}) as Dictionary).get("mutate", true)):
		errors.append("checkpoint.create must not mutate game state")
	return errors


static func observe_is_structured(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs1", "rooftops", 0)
	var session: GameSession = app.session
	_drive_combat(session)
	var res: Dictionary = _call(app, RuntimeConstants.OP_OBSERVE, {})
	if not bool(res.get("ok", false)):
		errors.append("observe rejected")
		return errors
	var obs: Dictionary = res.get("observe", {}) as Dictionary
	if str(obs.get("schema", "")) != RuntimeConstants.OBSERVE_ID:
		errors.append("observe missing schema")
	if str(obs.get("title", "")) != "Vault Fighters":
		errors.append("observe title must be Vault Fighters")
	if int(obs.get("seed", -1)) != session.sim_seed:
		errors.append("observe seed missing")
	if str(obs.get("map_id", "")) != "rooftops":
		errors.append("observe map_id missing")
	if str(obs.get("mode", "")) != "vs1":
		errors.append("observe mode missing")
	if str(obs.get("snapshot_hash", "")) != session.snapshot_hash():
		errors.append("observe hash != session snapshot_hash")
	var events: Dictionary = obs.get("events", {}) as Dictionary
	if not events.has("actor") or not events.has("weapon") or not events.has("prop"):
		errors.append("observe events must expose actor/weapon/prop")
	if (events.get("weapon", []) as Array).is_empty():
		errors.append("observe weapon events empty after fire")
	if (events.get("actor", []) as Array).is_empty():
		errors.append("observe actor events empty after melee")
	var want_props: int = _World.placements_for("rooftops").size()
	if (obs.get("props", []) as Array).size() != want_props:
		errors.append("prop list must match rooftops catalog placements")
	var ui: Dictionary = obs.get("ui", {}) as Dictionary
	if bool(ui.get("title", true)):
		errors.append("observe ui.title should be false in a fight")
	var tick0: int = session.clock.tick
	var x0: float = session.player1().global_position.x
	_call(app, RuntimeConstants.OP_OBSERVE, {})
	if session.clock.tick != tick0:
		errors.append("observe advanced tick")
	if absf(session.player1().global_position.x - x0) > 0.0:
		errors.append("observe moved P1")
	return errors


static func snapshot_pause_stable(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs1", "rooftops", 0)
	var session: GameSession = app.session
	_idle(session, 10)
	var before: Dictionary = _call(app, RuntimeConstants.OP_OBSERVE, {})
	var h0: String = str(before.get("snapshot_hash", ""))
	var t0: int = session.clock.tick
	var pause: Dictionary = _call(app, RuntimeConstants.OP_PAUSE, {"reason": "agent"})
	if not bool(pause.get("ok", false)):
		errors.append("pause rejected")
		return errors
	var mid: Dictionary = _call(app, RuntimeConstants.OP_OBSERVE, {})
	var obs: Dictionary = mid.get("observe", {}) as Dictionary
	if str(mid.get("snapshot_hash", "")) != h0:
		errors.append("snapshot hash changed across pause")
	if session.clock.tick != t0:
		errors.append("pause advanced tick")
	if not bool(obs.get("paused", false)):
		errors.append("observe paused flag false after pause")
	if str(obs.get("pause_reason", "")) != RuntimeConstants.REASON_AGENT:
		errors.append("observe pause_reason not agent")
	var resume: Dictionary = _call(app, RuntimeConstants.OP_RESUME, {})
	if not bool(resume.get("ok", false)):
		errors.append("resume rejected")
	if session.clock.tick != t0:
		errors.append("resume jumped tick")
	if session.clock.paused:
		errors.append("clock still paused after resume")
	return errors


static func snapshot_restart_fresh(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs1", "rooftops", 0)
	var h_fresh: String = app.session.snapshot_hash()
	_idle(app.session, 16)
	var h_mid: String = app.session.snapshot_hash()
	if h_mid == h_fresh:
		errors.append("driven fight hash matched fresh start")
	app.start_fight("vs1", "rooftops", 0)
	var after: Dictionary = _call(app, RuntimeConstants.OP_OBSERVE, {})
	var h_restart: String = str(after.get("snapshot_hash", ""))
	if h_restart != h_fresh:
		errors.append("restart snapshot hash != fresh start")
	if h_restart == h_mid:
		errors.append("restart snapshot still matches in-progress fight")
	var obs: Dictionary = after.get("observe", {}) as Dictionary
	if int(obs.get("tick", -1)) != 0:
		errors.append("restart observe tick was not 0")
	app.restart_to_title()
	var title_obs: Dictionary = _call(app, RuntimeConstants.OP_OBSERVE, {})
	var ui: Dictionary = (title_obs.get("observe", {}) as Dictionary).get("ui", {}) as Dictionary
	if not bool(ui.get("title", false)):
		errors.append("observe ui.title false after restart_to_title")
	if app.session != null:
		errors.append("restart_to_title left a session")
	return errors


static func checkpoint_restore_hash(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs1", "rooftops", 0)
	var session: GameSession = app.session
	_drive_combat(session)
	var h0: String = session.snapshot_hash()
	var t0: int = session.clock.tick
	var created: Dictionary = _call(app, RuntimeConstants.OP_CHECKPOINT_CREATE, {"checkpoint_id": "cp-restore-1"})
	if not bool(created.get("ok", false)):
		errors.append("checkpoint.create rejected")
		return errors
	if str(created.get("snapshot_hash", "")) != h0:
		errors.append("checkpoint.create hash drifted")
	if session.clock.tick != t0 or session.snapshot_hash() != h0:
		errors.append("checkpoint.create mutated the fight")
	_idle(session, 12)
	var h1: String = session.snapshot_hash()
	if h1 == h0:
		errors.append("post-checkpoint walk did not change hash")
	var restored: Dictionary = _call(app, RuntimeConstants.OP_CHECKPOINT_RESTORE, {"checkpoint_id": "cp-restore-1"})
	if not bool(restored.get("ok", false)):
		errors.append("checkpoint.restore rejected: %s" % str(restored.get("errors", [])))
		return errors
	if str(restored.get("snapshot_hash", "")) != h0:
		errors.append("restore hash %s != captured %s" % [str(restored.get("snapshot_hash", "")), h0])
	if app.session == null or app.session.snapshot_hash() != h0:
		errors.append("session hash after restore != captured")
	if app.session.clock.tick != t0:
		errors.append("restore tick %d != captured %d" % [app.session.clock.tick, t0])
	return errors


static func malformed_does_not_mutate(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs1", "rooftops", 0)
	var session: GameSession = app.session
	_idle(session, 6)
	var mark: Dictionary = _mark(session)
	var cases: Array = [
		null,
		{"op": "observe"},
		{
			"schema": RuntimeConstants.REQUEST_ID,
			"command_id": "bad id",
			"op": RuntimeConstants.OP_OBSERVE,
			"auth": {"token": TOKEN},
		},
		{
			"schema": RuntimeConstants.REQUEST_ID,
			"command_id": "cmd.malformed.unknown-op",
			"op": "explode",
			"auth": {"token": TOKEN},
		},
		{
			"schema": RuntimeConstants.REQUEST_ID,
			"command_id": "cmd.malformed.restore-path",
			"op": RuntimeConstants.OP_CHECKPOINT_RESTORE,
			"auth": {"token": TOKEN},
			"path": "../secrets",
			"payload": {"checkpoint_id": "x"},
		},
		{
			"schema": RuntimeConstants.REQUEST_ID,
			"command_id": "cmd.malformed.restore-slash",
			"op": RuntimeConstants.OP_CHECKPOINT_RESTORE,
			"auth": {"token": TOKEN},
			"payload": {"checkpoint_id": "../escape"},
		},
		{
			"schema": RuntimeConstants.REQUEST_ID,
			"command_id": "cmd.malformed.restore-missing",
			"op": RuntimeConstants.OP_CHECKPOINT_RESTORE,
			"auth": {"token": TOKEN},
			"payload": {"checkpoint_id": "no-such-cp"},
		},
	]
	var i: int = 0
	while i < cases.size():
		var res: Dictionary = app.runtime.handle(cases[i])
		if bool(res.get("ok", false)):
			errors.append("malformed case %d was accepted" % i)
		if str(res.get("error_code", "")) == RuntimeConstants.ERR_UNAUTHORIZED:
			errors.append("malformed case %d returned unauthorized" % i)
		if not _same_mark(session, mark):
			errors.append("malformed case %d mutated state" % i)
			mark = _mark(session)
		i += 1
	return errors


static func unauthorized_does_not_mutate(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs1", "rooftops", 0)
	var session: GameSession = app.session
	_idle(session, 6)
	_call(app, RuntimeConstants.OP_CHECKPOINT_CREATE, {"checkpoint_id": "cp-auth-1"})
	var mark: Dictionary = _mark(session)
	var cases: Array = [
		{
			"schema": RuntimeConstants.REQUEST_ID,
			"command_id": "cmd.unauth.restore",
			"op": RuntimeConstants.OP_CHECKPOINT_RESTORE,
			"auth": {"token": "wrong-token"},
			"payload": {"checkpoint_id": "cp-auth-1"},
		},
		{
			"schema": RuntimeConstants.REQUEST_ID,
			"command_id": "cmd.unauth.pause",
			"op": RuntimeConstants.OP_PAUSE,
			"auth": {"token": ""},
			"payload": {},
		},
		{
			"schema": RuntimeConstants.REQUEST_ID,
			"command_id": "cmd.unauth.empty-server",
			"op": RuntimeConstants.OP_OBSERVE,
			"auth": {"token": TOKEN},
			"payload": {},
		},
	]
	var empty_probe: Dictionary = cases[2] as Dictionary
	app.runtime.bind(app, "")
	var empty_res: Dictionary = app.runtime.handle(empty_probe)
	if bool(empty_res.get("ok", false)):
		errors.append("empty server token accepted observe")
	if str(empty_res.get("error_code", "")) != RuntimeConstants.ERR_UNAUTHORIZED:
		errors.append("empty server token must be unauthorized")
	if not _same_mark(session, mark):
		errors.append("empty server token mutated state")
	_bind(app)
	var i: int = 0
	while i < 2:
		var res: Dictionary = app.runtime.handle(cases[i])
		if bool(res.get("ok", false)):
			errors.append("unauthorized case %d was accepted" % i)
		if str(res.get("error_code", "")) != RuntimeConstants.ERR_UNAUTHORIZED:
			errors.append("unauthorized case %d code %s" % [i, str(res.get("error_code", ""))])
		if not _same_mark(session, mark):
			errors.append("unauthorized case %d mutated state" % i)
			mark = _mark(session)
		i += 1
	if session.clock.paused:
		errors.append("unauthorized pause left the clock paused")
	return errors


static func secrets_are_redacted(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs1", "rooftops", 0)
	var req: Dictionary = {
		"schema": RuntimeConstants.REQUEST_ID,
		"command_id": "cmd.redact.observe",
		"op": RuntimeConstants.OP_OBSERVE,
		"auth": {"token": TOKEN, "password": "leak-me"},
		"payload": {"token": TOKEN, "note": TOKEN},
	}
	var res: Dictionary = app.runtime.handle(req)
	var dumped: String = SimSnapshot.canonical(res)
	if dumped.contains(TOKEN):
		errors.append("response echoed the runtime token")
	if dumped.to_lower().contains("leak-me"):
		errors.append("response echoed a password")
	if dumped.contains("C:\\Users\\") or dumped.contains("/Users/"):
		errors.append("response leaked a host home path")
	if str(res.get("auth", "")) == TOKEN:
		errors.append("response auth echoed token")
	return errors


static func _bind(app: App) -> void:
	app.runtime.bind(app, TOKEN)


static func _call(app: App, op: String, payload: Dictionary) -> Dictionary:
	return app.runtime.handle({
		"schema": RuntimeConstants.REQUEST_ID,
		"schema_version": RuntimeConstants.SCHEMA_VERSION,
		"command_id": "cmd.runtime.%s.%d" % [op.replace(".", "-"), Time.get_ticks_usec()],
		"op": op,
		"auth": {"token": TOKEN},
		"payload": payload,
	})


static func _drive_combat(session: GameSession) -> void:
	_idle(session, 8)
	var p1: Fighter = session.player1()
	if p1 == null or session.fighters.size() < 2:
		return
	var foe: Fighter = session.fighters[1]
	foe.global_position = p1.global_position + Vector2(14, 0)
	p1.facing = 1.0
	p1.aim_dir = Vector2.RIGHT
	p1.gun_id = "pistol"
	p1.ammo = 12
	p1.weapon_id = "pistol"
	var melee: Array[Dictionary] = _idle_cmds(session)
	melee[0]["melee"] = true
	session.step_fixed(STEP, melee)
	_idle(session, _Combat.startup_ticks(p1.melee_id, "melee") + _Combat.active_ticks(p1.melee_id, "melee") + 2)
	var fire: Array[Dictionary] = _idle_cmds(session)
	fire[0]["fire_held"] = true
	session.step_fixed(STEP, fire)
	fire[0]["fire_released"] = true
	session.step_fixed(STEP, fire)
	_idle(session, 4)


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


static func _mark(session: GameSession) -> Dictionary:
	var p1: Fighter = session.player1()
	return {
		"tick": session.clock.tick,
		"hash": session.snapshot_hash(),
		"paused": session.clock.paused,
		"x": p1.global_position.x if p1 != null else 0.0,
		"reason": session.pause_reason,
	}


static func _same_mark(session: GameSession, mark: Dictionary) -> bool:
	var now: Dictionary = _mark(session)
	return (
		int(now.get("tick", 0)) == int(mark.get("tick", 0))
		and str(now.get("hash", "")) == str(mark.get("hash", ""))
		and bool(now.get("paused", false)) == bool(mark.get("paused", false))
		and absf(float(now.get("x", 0.0)) - float(mark.get("x", 0.0))) <= 0.0001
		and str(now.get("reason", "")) == str(mark.get("reason", ""))
	)


static func _append(into: PackedStringArray, extra: PackedStringArray) -> void:
	var i: int = 0
	while i < extra.size():
		into.append(String(extra[i]))
		i += 1

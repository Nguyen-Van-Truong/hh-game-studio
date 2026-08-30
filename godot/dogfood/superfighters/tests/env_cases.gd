class_name EnvCases
extends RefCounted

const _Catalog: GDScript = preload("res://src/world/world_catalog.gd")
const _Env: GDScript = preload("res://src/world/env_spec.gd")
const _Arena: GDScript = preload("res://src/maps/arena_spec.gd")

## VF4-WP5 official instant / toxic / water / rotor / fall cases.
## Proof is InputFrame apply_frames plus live InputEvent inject.
## 60 Hz is ledger:RL-SIM-FIXED-60 (assumption).
## Env rows stay assumption. RL-NADE-PROP stays deferred.
## USED_APPLY_FRAMES counts success only.

static var used_step_fixed: int = 0
static var used_apply_frames: int = 0
static var used_apply_frames_attempted: int = 0
static var used_apply_frames_succeeded: int = 0
static var used_parse_input_event: int = 0
static var used_action_press: int = 0
static var outcome_data: Dictionary = {}
static var outcome_instant: Dictionary = {}
static var outcome_toxic: Dictionary = {}
static var outcome_water: Dictionary = {}
static var outcome_rotor: Dictionary = {}
static var outcome_fall: Dictionary = {}
static var outcome_spawn: Dictionary = {}
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
	outcome_instant = {"verdict": "unproven"}
	outcome_toxic = {"verdict": "unproven"}
	outcome_water = {"verdict": "unproven"}
	outcome_rotor = {"verdict": "unproven"}
	outcome_fall = {"verdict": "unproven"}
	outcome_spawn = {"verdict": "unproven"}
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
	_append(errors, await instant_kills(app))
	_append(errors, await toxic_enter_exit_death(app))
	_append(errors, await water_extinguish(app))
	_append(errors, await rotor_hits(app))
	_append(errors, await fall_policy(app))
	_append(errors, await spawn_safe(app))
	_append(errors, await pause_and_reset(app))
	_append(errors, await live_water(app))
	_append(errors, _require_outcomes())
	return errors


static func schema_and_data() -> PackedStringArray:
	var errors: PackedStringArray = _Catalog.validate()
	_append(errors, _Env.validate())
	_append(errors, _Arena.validate())
	if not Maps.has_fixture("fx_env_instant") or not Maps.has_fixture("fx_env_yard"):
		errors.append("env fixtures missing")
	if Maps.display_name("fx_env_instant") != "Void Cut":
		errors.append("instant fixture display name must be Void Cut")
	if Maps.display_name("fx_env_toxic") != "Acid Trench":
		errors.append("toxic fixture display name must be Acid Trench")
	if Maps.display_name("fx_env_water") != "Wash Channel":
		errors.append("water fixture display name must be Wash Channel")
	if Maps.display_name("fx_env_rotor") != "Mill Shaft":
		errors.append("rotor fixture display name must be Mill Shaft")
	if Maps.display_name("fx_env_fall") != "Drop Well":
		errors.append("fall fixture display name must be Drop Well")
	if Maps.display_name("fx_env_yard") != "Hazard Yard":
		errors.append("yard fixture display name must be Hazard Yard")
	if Maps.display_name("fx_env_yard").to_lower().contains("superfighter"):
		errors.append("env fixture name must stay original")
	var live: Dictionary = _Catalog.data()
	var env: Dictionary = _Env.data()
	var arena: Dictionary = _Arena.data()
	if not bool(live.get("env_implemented", false)):
		errors.append("DATA env_implemented must be true")
	if not bool(env.get("water_extinguish", false)):
		errors.append("DATA water extinguish must be selected")
	if str(live.get("nade_prop_class", "")) != "deferred":
		errors.append("DATA RL-NADE-PROP must stay deferred")
	if str(env.get("instant_class", "")) != "assumption":
		errors.append("DATA instant must stay assumption")
	if str(arena.get("fall_class", "")) != "assumption":
		errors.append("DATA fall must stay assumption")
	outcome_data = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"env_implemented": true,
		"water_extinguish": true,
		"nade_prop": "deferred",
		"source": "catalog + env.json + arena_spec.json Hazard Yard",
	}
	return errors


static func replay_traces_twice(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var paths: PackedStringArray = SimTrace.list_dir(SimConstants.ENV_TRACE_DIR)
	if paths.size() < 6:
		errors.append("expected >=6 env traces, got %d" % paths.size())
	var required: PackedStringArray = PackedStringArray([
		"env_instant", "env_toxic", "env_toxic_death", "env_water",
		"env_rotor", "env_fall", "env_yard"
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
			errors.append("env %s run1 failed: %s" % [path.get_file(), _join(a)])
		if not bool(b.get("ok", false)):
			errors.append("env %s run2 failed: %s" % [path.get_file(), _join(b)])
		if not bool(a.get("used_apply_frames", false)) or bool(a.get("used_cmd_dicts", true)):
			errors.append("env %s MATCH used cmd dicts" % path.get_file())
		var hash_a: String = str(a.get("final_hash", ""))
		var hash_b: String = str(b.get("final_hash", ""))
		var match_ok: bool = hash_a != "" and hash_a == hash_b
		var world_ok: bool = hash_wa != "" and hash_wa == hash_wb
		if not match_ok:
			errors.append("env %s replay hashes differ" % path.get_file())
		if not world_ok:
			errors.append("env %s world hashes differ" % path.get_file())
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
			errors.append("missing env trace %s" % String(required[i]))
		i += 1
	var all_match: bool = pairs.size() >= 6
	var p: int = 0
	while p < pairs.size():
		var row: Dictionary = pairs[p] as Dictionary
		if not bool(row.get("hash_match", false)) or not bool(row.get("world_hash_match", false)):
			all_match = false
		p += 1
	outcome_replay = {
		"verdict": "match" if all_match and errors.is_empty() else "fail",
		"pairs": pairs,
		"source": "apply_frames env traces twice",
	}
	return errors


static func instant_kills(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_env_instant", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	if p1 == null:
		errors.append("INSTANT missing P1")
		outcome_instant = {"verdict": "fail"}
		return errors
	var hp0: float = p1.health
	_hold(session, 60, PackedStringArray(["right"]))
	var dead: bool = p1.dead
	var cause: String = p1.death_cause
	var enters: int = session.ledger.count_kind("env_enter")
	var deaths: int = session.ledger.count_kind("env_death")
	if not dead:
		errors.append("INSTANT P1 must die in the void cut")
	if cause != "pit":
		errors.append("INSTANT death_cause must be pit got=%s" % cause)
	if enters < 1 or deaths < 1:
		errors.append("INSTANT missing enter/death events enter=%d death=%d" % [enters, deaths])
	outcome_instant = {
		"verdict": "pass" if dead and cause == "pit" and enters >= 1 and deaths >= 1 else "fail",
		"dead": dead,
		"cause": cause,
		"enters": enters,
		"deaths": deaths,
		"hp0": hp0,
		"source": "Void Cut enter then pit death",
	}
	_remember_session(session)
	return errors


static func toxic_enter_exit_death(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_env_toxic", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	_hold(session, 52, PackedStringArray(["right"]))
	_idle(session, 10)
	var hp1: float = p1.health if p1 != null else -1.0
	var acid1: bool = p1 != null and p1.acid_contact
	var dmg: int = session.ledger.count_kind("env_damage")
	var enters: int = session.ledger.count_kind("env_enter")
	_hold(session, 28, PackedStringArray(["left"]))
	var exits: int = session.ledger.count_kind("env_exit")
	var acid0: bool = p1 != null and p1.acid_contact
	var alive: bool = p1 != null and not p1.dead
	if hp1 >= Fighter.MAX_HP - 0.5:
		errors.append("TOXIC must apply deferred damage hp=%s" % str(hp1))
	if not acid1:
		errors.append("TOXIC enter must set acid_contact")
	if exits < 1:
		errors.append("TOXIC missing env_exit")
	if acid0:
		errors.append("TOXIC exit must clear acid_contact")
	if not alive:
		errors.append("TOXIC short stay must not kill")
	app.start_fight("vs2", "fx_env_toxic", 0)
	await SimReplay.sync_physics(app)
	session = app.session
	p1 = session.player1()
	_hold(session, 52, PackedStringArray(["right"]))
	_idle(session, 88)
	var dead: bool = p1 != null and p1.dead
	var cause: String = p1.death_cause if p1 != null else ""
	var deaths: int = session.ledger.count_kind("env_death")
	if not dead:
		errors.append("TOXIC stay must kill")
	if cause != "damage":
		errors.append("TOXIC death_cause must be damage got=%s" % cause)
	if deaths < 1:
		errors.append("TOXIC missing env_death")
	var pass_ok: bool = (
		hp1 < Fighter.MAX_HP - 0.5
		and acid1
		and exits >= 1
		and not acid0
		and alive
		and dead
		and cause == "damage"
		and deaths >= 1
		and dmg >= 1
		and enters >= 1
	)
	outcome_toxic = {
		"verdict": "pass" if pass_ok else "fail",
		"hp_after": hp1,
		"enter": enters,
		"exit": exits,
		"damage": dmg,
		"deaths": deaths,
		"cause": cause,
		"source": "Acid Trench enter/damage/exit then stay-to-death",
	}
	_remember_session(session)
	return errors


static func water_extinguish(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_env_water", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	if p1 == null:
		errors.append("WATER missing P1")
		outcome_water = {"verdict": "fail"}
		return errors
	p1.ignite_fire(48)
	_idle(session, 2)
	var burned: bool = p1.burning
	_hold(session, 24, PackedStringArray(["right"]))
	var wet: bool = p1.wet
	var burning: bool = p1.burning
	var enters: int = session.ledger.count_kind("env_enter")
	var ext: int = session.ledger.count_kind("env_extinguish")
	_hold(session, 30, PackedStringArray(["left"]))
	var exits: int = session.ledger.count_kind("env_exit")
	var wet0: bool = p1.wet
	if not burned:
		errors.append("WATER setup must ignite")
	if not wet:
		errors.append("WATER enter must set wet")
	if burning:
		errors.append("WATER must extinguish fire")
	if ext < 1 or enters < 1:
		errors.append("WATER missing enter/extinguish")
	if exits < 1:
		errors.append("WATER missing env_exit")
	if wet0:
		errors.append("WATER exit must clear wet")
	outcome_water = {
		"verdict": "pass" if burned and wet and not burning and ext >= 1 and exits >= 1 and not wet0 else "fail",
		"wet": wet,
		"burning": burning,
		"extinguish": ext,
		"enter": enters,
		"exit": exits,
		"source": "Wash Channel extinguish then exit",
	}
	_remember_session(session)
	return errors


static func rotor_hits(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_env_rotor", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	var rotor: Node2D = _find(session, "mill_hub")
	if p1 == null or rotor == null:
		errors.append("ROTOR missing P1 or mill_hub")
		outcome_rotor = {"verdict": "fail"}
		return errors
	var a0: float = float(rotor.get("angle"))
	_hold(session, 56, PackedStringArray(["right"]))
	_idle(session, 20)
	var hp: float = p1.health
	var hits: int = int(_owner(session).get("rotor_hits")) if _owner(session) != null else 0
	var dmg: int = session.ledger.count_kind("env_damage")
	var a1: float = float(rotor.get("angle"))
	if hp >= Fighter.MAX_HP - 0.5:
		errors.append("ROTOR must deal damage hp=%s" % str(hp))
	if hits < 1 or dmg < 1:
		errors.append("ROTOR missing hit/damage hits=%d dmg=%d" % [hits, dmg])
	if a1 <= a0 + 1.0:
		errors.append("ROTOR angle must advance")
	outcome_rotor = {
		"verdict": "pass" if hp < Fighter.MAX_HP - 0.5 and hits >= 1 and dmg >= 1 and a1 > a0 + 1.0 else "fail",
		"hp": hp,
		"hits": hits,
		"damage": dmg,
		"angle0": a0,
		"angle1": a1,
		"source": "Mill Shaft overlap damage + spin",
	}
	_remember_session(session)
	return errors


static func fall_policy(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_env_fall", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	_hold(session, 58, PackedStringArray(["right"]))
	_idle(session, 48)
	var damaged: bool = p1 != null and (p1.fall_damage_applied or session.ledger.count_kind("fall_damage") >= 1)
	var hp_hurt: bool = p1 != null and p1.health < Fighter.MAX_HP - 0.5
	var floor1: bool = p1 != null and p1.is_on_floor()
	var hang1: bool = p1 != null and p1.hanging
	var pose1: String = p1.current_pose() if p1 != null else ""
	var y1: float = p1.global_position.y if p1 != null else -1.0
	var alive: bool = p1 != null and not p1.dead
	if not damaged and not hp_hurt:
		errors.append("FALL walk-off must apply fall damage y=%s hp=%s" % [str(y1), str(p1.health if p1 != null else -1)])
	if not floor1 or hang1 or pose1 == "hang":
		errors.append("FALL land must stand on_floor pose=%s hang=%s" % [pose1, str(hang1)])
	if not alive:
		errors.append("FALL must not kill")
	app.start_fight("vs2", "fx_env_fall", 0)
	await SimReplay.sync_physics(app)
	session = app.session
	p1 = session.player1()
	_hold(session, 46, PackedStringArray(["right"]))
	_hold(session, 4, PackedStringArray(["right", "jump"]))
	_action(session, "dive", PackedStringArray(["right"]), 1)
	_hold(session, 20, PackedStringArray(["right"]))
	_idle(session, 24)
	var immune: bool = session.ledger.count_kind("fall_immune") >= 1 or (p1 != null and p1.fall_immune_landed)
	var no_fall: bool = session.ledger.count_kind("fall_damage") == 0
	if not immune:
		errors.append("FALL dive landing missing fall_immune")
	if not no_fall:
		errors.append("FALL dive landing must not emit fall_damage")
	outcome_fall = {
		"verdict": "pass" if (damaged or hp_hurt) and floor1 and not hang1 and alive and immune and no_fall else "fail",
		"y_end": y1,
		"on_floor": floor1,
		"hanging": hang1,
		"pose": pose1,
		"dive_immune": immune,
		"source": "Drop Well walk-off damage vs dive immunity",
	}
	_remember_session(session)
	return errors


static func spawn_safe(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var maps: PackedStringArray = PackedStringArray([
		"rooftops", "storage", "police", "hazardous",
		"fx_env_instant", "fx_env_toxic", "fx_env_water",
		"fx_env_rotor", "fx_env_fall", "fx_env_yard"
	])
	var locked: int = 0
	var i: int = 0
	while i < maps.size():
		var mid: String = String(maps[i])
		app.start_fight("vs2", mid, 0)
		await SimReplay.sync_physics(app)
		_idle(app.session, 8)
		var p1: Fighter = app.session.player1() if app.session != null else null
		var p2: Fighter = app.session.fighter_at_slot(1) if app.session != null else null
		if p1 == null or p1.dead or p1.hanging:
			locked += 1
			errors.append("SPAWN soft-lock on %s P1 dead=%s hang=%s" % [mid, str(p1 != null and p1.dead), str(p1 != null and p1.hanging)])
		if p1 != null and p1.health < Fighter.MAX_HP - 0.5:
			locked += 1
			errors.append("SPAWN P1 damaged on %s" % mid)
		if p2 != null and p2.dead:
			locked += 1
			errors.append("SPAWN P2 dead on %s" % mid)
		i += 1
	_append(errors, _Arena.validate_spawns_safe())
	outcome_spawn = {
		"verdict": "pass" if locked == 0 and errors.is_empty() else "fail",
		"locked": locked,
		"maps": maps.size(),
		"source": "start_fight each ArenaSpec map; spawn not in lethal AABB",
	}
	_remember_session(app.session)
	return errors


static func pause_and_reset(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_env_rotor", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_hold(session, 20, PackedStringArray(["right"]))
	var rotor: Node2D = _find(session, "mill_hub")
	var a_mid: float = float(rotor.get("angle")) if rotor != null else -1.0
	session.set_paused(true, "test")
	var rejected: bool = not session.apply_frames(_idle_frames(session))
	used_apply_frames_attempted += 1
	var a_pause: float = float(rotor.get("angle")) if rotor != null else -2.0
	session.set_paused(false)
	_idle(session, 16)
	var a_res: float = float(rotor.get("angle")) if rotor != null else a_mid
	if not rejected:
		errors.append("PAUSE apply_frames must reject while paused")
	if absf(a_pause - a_mid) > 0.01:
		errors.append("PAUSE rotor must freeze")
	if absf(a_res - a_pause) < 0.5:
		errors.append("PAUSE resume must continue spin")
	app.start_fight("vs2", "fx_env_yard", 0)
	await SimReplay.sync_physics(app)
	session = app.session
	rotor = _find(session, "yard_mill")
	var p1: Fighter = session.player1()
	var home: bool = rotor != null and absf(float(rotor.get("angle"))) < 0.01
	var wet0: bool = p1 != null and p1.wet
	var acid0: bool = p1 != null and p1.acid_contact
	if not home:
		errors.append("RESET rotor must start at angle 0")
	if wet0 or acid0:
		errors.append("RESET must clear wet/acid")
	outcome_pause = {
		"verdict": "pass" if rejected and absf(a_pause - a_mid) <= 0.01 and absf(a_res - a_pause) >= 0.5 else "fail",
		"a_mid": a_mid,
		"a_pause": a_pause,
		"a_res": a_res,
		"source": "clock.pause freezes rotor angle; resume continues",
	}
	outcome_reset = {
		"verdict": "pass" if home and not wet0 and not acid0 else "fail",
		"angle": float(rotor.get("angle")) if rotor != null else -1.0,
		"wet": wet0,
		"acid": acid0,
		"source": "start_fight rebuilds env at rest",
	}
	_remember_session(session)
	return errors


static func live_water(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_env_water", 0)
	var session: GameSession = app.session
	var viewport: Viewport = app.get_viewport()
	await SimReplay.sync_physics(app)
	var p1: Fighter = session.player1()
	if p1 != null:
		p1.ignite_fire(48)
	InputInjector.release_known(viewport)
	InputActions.reset_edges()
	used_parse_input_event += 1
	InputInjector.inject_key(KEY_RIGHT, true, viewport)
	var n: int = 0
	while n < 24:
		session.step_from_live_input()
		n += 1
	InputInjector.inject_key(KEY_RIGHT, false, viewport)
	session.step_from_live_input()
	p1 = session.player1()
	var wet: bool = p1 != null and p1.wet
	var burning: bool = p1 != null and p1.burning
	if not wet:
		errors.append("LIVE water must set wet")
	if burning:
		errors.append("LIVE water must extinguish")
	InputInjector.release_known(viewport)
	outcome_live = {
		"verdict": "pass" if wet and not burning else "fail",
		"wet": wet,
		"burning": burning,
		"source": "parse_input_event KEY_RIGHT + step_from_live_input",
	}
	_remember_session(session)
	return errors


static func _require_outcomes() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var labels: PackedStringArray = PackedStringArray([
		"DATA", "INSTANT", "TOXIC", "WATER", "ROTOR", "FALL", "SPAWN", "PAUSE", "RESET", "LIVE"
	])
	var rows: Array = [
		outcome_data, outcome_instant, outcome_toxic, outcome_water, outcome_rotor,
		outcome_fall, outcome_spawn, outcome_pause, outcome_reset, outcome_live
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
				if n == 0 and not held.is_empty():
					d["pressed"] = held
			frames.append(InputFrame.from_dict(d))
			i += 1
		_record_apply(session.apply_frames(frames))
		n += 1


static func _action(session: GameSession, pressed: String, held: PackedStringArray, ticks: int) -> void:
	var n: int = 0
	while n < ticks:
		var frames: Array = []
		var i: int = 0
		while i < session.fighters.size():
			var d: Dictionary = InputActions.empty_frame(session.clock.tick, i)
			if i == 0:
				d["held"] = held
				d["pressed"] = PackedStringArray([pressed])
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
	app.start_fight("vs2", "fx_env_yard", 0)
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

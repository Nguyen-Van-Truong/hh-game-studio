class_name AimCases
extends RefCounted

const _Aim: GDScript = preload("res://src/sim/aim.gd")

## VF3-WP3 official aim / fire / release / sweep cases.
## Proof is InputFrame apply_frames plus live InputEvent inject.
## 60 Hz is ledger:RL-SIM-FIXED-60 (assumption).
## Hold-to-aim stays ledger:RL-CTRL-HOLD-AIM (assumption).
## Aim dirs stay ledger:RL-AIM-DIRS (assumption).
## Semi release stays ledger:RL-FIRE-SEMI (assumption).
## Auto cadence stays ledger:RL-FIRE-AUTO (assumption).
## Empty ammo stays ledger:RL-FIRE-AMMO (assumption).
## Muzzle stays ledger:RL-FIRE-MUZZLE (assumption).
## Recoil/spread stay ledger:RL-FIRE-RECOIL (assumption).
## Ballistic decision stays ledger:RL-FIRE-BALLISTIC (assumption).
## Sweep collision stays ledger:RL-FIRE-SWEEP (assumption).
## Y8 roll/dive stays unavailable. USED_APPLY_FRAMES counts success only.

static var used_step_fixed: int = 0
static var used_apply_frames: int = 0
static var used_apply_frames_attempted: int = 0
static var used_apply_frames_succeeded: int = 0
static var used_parse_input_event: int = 0
static var used_action_press: int = 0
static var outcome_hold: Dictionary = {}
static var outcome_dirs: Dictionary = {}
static var outcome_semi: Dictionary = {}
static var outcome_auto: Dictionary = {}
static var outcome_ammo: Dictionary = {}
static var outcome_muzzle: Dictionary = {}
static var outcome_recoil: Dictionary = {}
static var outcome_data: Dictionary = {}
static var outcome_sweep: Dictionary = {}
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
	outcome_hold = {"verdict": "unproven"}
	outcome_dirs = {"verdict": "unproven"}
	outcome_semi = {"verdict": "unproven"}
	outcome_auto = {"verdict": "unproven"}
	outcome_ammo = {"verdict": "unproven"}
	outcome_muzzle = {"verdict": "unproven"}
	outcome_recoil = {"verdict": "unproven"}
	outcome_data = {"verdict": "unproven"}
	outcome_sweep = {"verdict": "unproven"}
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
	_append(errors, await hold_does_not_fire(app))
	_append(errors, await aim_directions(app))
	_append(errors, await semi_release_fires(app))
	_append(errors, await auto_cadence(app))
	_append(errors, await empty_ammo_no_fire(app))
	_append(errors, await muzzle_and_dir(app))
	_append(errors, await recoil_and_spread(app))
	_append(errors, await swept_no_tunnel(app))
	_append(errors, await live_aim_fire(app))
	_append(errors, _require_outcomes())
	return errors


static func schema_and_data() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var row: Dictionary = _Aim.data()
	if str(row.get("schema", "")) != _Aim.SCHEMA_ID:
		errors.append("aim schema id mismatch")
	if str(row.get("title", "")) != "Vault Fighters":
		errors.append("aim title must be Vault Fighters")
	if bool(row.get("y8_parity_claimed", true)):
		errors.append("aim must not claim Y8 parity")
	if str(row.get("hold_to_aim_class", "")) != "assumption":
		errors.append("hold-to-aim must stay assumption")
	if str(row.get("aim_dirs_class", "")) != "assumption":
		errors.append("aim dirs must stay assumption")
	if str(row.get("semi_class", "")) != "assumption":
		errors.append("semi fire must stay assumption")
	if str(row.get("auto_class", "")) != "assumption":
		errors.append("auto cadence must stay assumption")
	if str(row.get("ammo_class", "")) != "assumption":
		errors.append("ammo exhaustion must stay assumption")
	if str(row.get("sweep_class", "")) != "assumption":
		errors.append("sweep collision must stay assumption")
	if str(row.get("roll_dive_class", "")) != "unavailable":
		errors.append("Y8 roll/dive observation must stay unavailable")
	if str(row.get("projectile_mode", "")) != "ballistic":
		errors.append("projectile_mode must be ballistic")
	if bool(row.get("hitscan", true)):
		errors.append("hitscan must be false; guns are ballistic")
	if str(row.get("collision", "")) != "swept":
		errors.append("collision must be swept")
	if not Maps.has_fixture("fx_aim_open") or not Maps.has_fixture("fx_aim_wall"):
		errors.append("aim fixtures missing")
	if not Maps.solid_at("fx_aim_wall", Vector2(152.0, 40.0)):
		errors.append("aim wall fixture must be solid at cover column")
	var pistol: Dictionary = _Aim.gun("pistol")
	var uzi: Dictionary = _Aim.gun("uzi")
	var shotgun: Dictionary = _Aim.gun("shotgun")
	if pistol.is_empty() or uzi.is_empty() or shotgun.is_empty():
		errors.append("pistol/uzi/shotgun must live in aim.json")
		outcome_data = {"verdict": "fail", "source": "aim.json guns"}
		return errors
	var diffs: PackedStringArray = _gun_diffs(pistol, uzi, shotgun)
	if diffs.size() < 6:
		errors.append("pistol/uzi/shotgun must differ by data, got %s" % ",".join(diffs))
	if bool(pistol.get("auto", true)) or not bool(uzi.get("auto", false)) or bool(shotgun.get("auto", true)):
		errors.append("pistol/shotgun semi, uzi auto")
	if int(shotgun.get("pellets", 0)) < 3 or int(pistol.get("pellets", 0)) != 1:
		errors.append("shotgun must fan pellets; pistol is one slug")
	outcome_data = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"diffs": Array(diffs),
		"pistol_cadence": int(pistol.get("cadence_ticks", 0)),
		"uzi_cadence": int(uzi.get("cadence_ticks", 0)),
		"shotgun_cadence": int(shotgun.get("cadence_ticks", 0)),
		"pistol_recoil": float(pistol.get("recoil", 0.0)),
		"uzi_recoil": float(uzi.get("recoil", 0.0)),
		"shotgun_recoil": float(shotgun.get("recoil", 0.0)),
		"hitscan": false,
		"source": "aim.json pistol/uzi/shotgun distinct data",
	}
	return errors


static func replay_traces_twice(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var paths: PackedStringArray = SimTrace.list_dir(SimConstants.AIM_TRACE_DIR)
	if paths.size() < 6:
		errors.append("expected >=6 aim traces, got %d" % paths.size())
	var required: PackedStringArray = PackedStringArray([
		"aim_hold", "aim_up", "aim_down", "fire_semi", "fire_edges", "fire_wall"
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
		await _drain_physics(app)
		var b: Dictionary = await SimReplay.play_path(app, path)
		_record_apply_batch(int(a.get("ticks", 0)), bool(a.get("ok", false)))
		_record_apply_batch(int(b.get("ticks", 0)), bool(b.get("ok", false)))
		if not bool(a.get("ok", false)):
			errors.append("aim %s run1 failed: %s" % [path.get_file(), _join(a)])
		if not bool(b.get("ok", false)):
			errors.append("aim %s run2 failed: %s" % [path.get_file(), _join(b)])
		if not bool(a.get("used_apply_frames", false)) or bool(a.get("used_cmd_dicts", true)):
			errors.append("aim %s MATCH used cmd dicts" % path.get_file())
		var hash_a: String = str(a.get("final_hash", ""))
		var hash_b: String = str(b.get("final_hash", ""))
		var match_ok: bool = hash_a != "" and hash_a == hash_b
		if not match_ok:
			errors.append("aim %s replay hashes differ" % path.get_file())
		pairs.append({
			"name": str(trace.get("name", path.get_file())),
			"hash_match": match_ok,
			"ok_a": bool(a.get("ok", false)),
			"ok_b": bool(b.get("ok", false)),
			"hash_a": hash_a,
			"hash_b": hash_b,
		})
		_remember_end(a)
		_append_events(a.get("events", []) as Array)
		i += 1
	i = 0
	while i < required.size():
		if not names.has(String(required[i])):
			errors.append("missing aim trace %s" % String(required[i]))
		i += 1
	var all_match: bool = pairs.size() >= 6
	var p: int = 0
	while p < pairs.size():
		var prow: Dictionary = pairs[p] as Dictionary
		if not bool(prow.get("hash_match", false)) or not bool(prow.get("ok_a", false)) or not bool(prow.get("ok_b", false)):
			all_match = false
		p += 1
	outcome_replay = {
		"verdict": "match" if all_match else "fail",
		"pair_count": pairs.size(),
		"pairs": pairs,
		"source": "SimReplay.final_hash twice",
	}
	return errors


static func hold_does_not_fire(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_aim_open", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.fighter_at_slot(0)
	_apply_slot(session, 0, PackedStringArray(), 8, 0.0)
	var spawn0: int = session.ledger.count_kind("bullet")
	var bullets0: int = _live_bullets(session)
	_apply_slot(session, 0, PackedStringArray(["fire"]), 10, 0.0)
	var spawn1: int = session.ledger.count_kind("bullet")
	var ok: bool = (
		p1.aiming
		and p1.aim_dir.y > -0.2
		and p1.aim_dir.y < 0.2
		and spawn1 == spawn0
		and _live_bullets(session) == bullets0
		and (p1.current_pose() == "aim_side" or p1._pose_clip() == "aim_side")
	)
	if not ok:
		errors.append("HOLD fire must aim side and not spawn a bullet")
	outcome_hold = {
		"verdict": "pass" if ok else "fail",
		"aiming": p1.aiming,
		"pose": p1.current_pose(),
		"aim_y": p1.aim_dir.y,
		"spawns": spawn1 - spawn0,
		"source": "apply_frames hold fire, no release",
	}
	_remember_session(session)
	_append_events(session.ledger.to_array())
	return errors


static func aim_directions(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_aim_open", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.fighter_at_slot(0)
	_apply_slot(session, 0, PackedStringArray(), 6, 0.0)
	_apply_slot(session, 0, PackedStringArray(["fire", "jump"]), 8, 0.0)
	var up_ok: bool = p1.aiming and p1.aim_dir.y < -0.4 and _Aim.pose_from_dir(p1.aim_dir) == "aim_up"
	if not up_ok:
		errors.append("DIRS hold fire+up must aim_up")
	var up_dir: Vector2 = p1.aim_dir
	_apply_slot(session, 0, PackedStringArray(["fire", "crouch"]), 8, 0.0)
	var down_ok: bool = p1.aiming and p1.aim_dir.y > 0.4 and _Aim.pose_from_dir(p1.aim_dir) == "aim_down"
	if not down_ok:
		errors.append("DIRS hold fire+down must aim_down")
	var down_dir: Vector2 = p1.aim_dir
	_apply_slot(session, 0, PackedStringArray(["fire"]), 6, 0.0)
	var side_ok: bool = p1.aiming and absf(p1.aim_dir.y) < 0.4 and _Aim.pose_from_dir(p1.aim_dir) == "aim_side"
	if not side_ok:
		errors.append("DIRS hold fire must aim_side")
	outcome_dirs = {
		"verdict": "pass" if up_ok and down_ok and side_ok else "fail",
		"up": up_ok,
		"down": down_ok,
		"side": side_ok,
		"up_y": up_dir.y,
		"down_y": down_dir.y,
		"side_y": p1.aim_dir.y,
		"source": "apply_frames hold fire with jump/crouch/none",
	}
	_remember_session(session)
	return errors


static func semi_release_fires(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_aim_open", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.fighter_at_slot(0)
	_apply_slot(session, 0, PackedStringArray(), 8, 0.0)
	var ammo0: int = p1.ammo
	_apply_slot(session, 0, PackedStringArray(["fire"]), 8, 0.0)
	var during: int = session.ledger.count_kind("bullet")
	_apply_release(session, 0, "fire")
	var after: int = session.ledger.count_kind("bullet")
	var ok: bool = during == 0 and after == 1 and p1.ammo == ammo0 - 1 and p1.shots_fired == 1
	if not ok:
		errors.append("SEMI pistol must fire once on release only")
	outcome_semi = {
		"verdict": "pass" if ok else "fail",
		"during": during,
		"after": after,
		"ammo0": ammo0,
		"ammo1": p1.ammo,
		"shots": p1.shots_fired,
		"source": "apply_frames hold then released fire",
	}
	_remember_session(session)
	_append_events(session.ledger.to_array())
	return errors


static func auto_cadence(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_aim_open", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.fighter_at_slot(0)
	_apply_slot(session, 0, PackedStringArray(), 6, 0.0)
	p1.give_weapon("uzi")
	var cadence: int = _Aim.cadence_ticks("uzi")
	var hold: int = cadence * 5 + 1
	_apply_slot(session, 0, PackedStringArray(["fire"]), hold, 0.0)
	var auto_shots: int = p1.shots_fired
	var expected: int = 6
	var auto_ok: bool = auto_shots >= 5 and auto_shots <= 7
	if not auto_ok:
		errors.append("AUTO uzi hold must fire on cadence got=%d expected~%d" % [auto_shots, expected])
	app.start_fight("vs2", "fx_aim_open", 0)
	await SimReplay.sync_physics(app)
	session = app.session
	p1 = session.fighter_at_slot(0)
	_apply_slot(session, 0, PackedStringArray(), 6, 0.0)
	_apply_slot(session, 0, PackedStringArray(["fire"]), hold, 0.0)
	var pistol_shots: int = p1.shots_fired
	var semi_ok: bool = pistol_shots == 0
	if not semi_ok:
		errors.append("AUTO pistol hold must not fire, got %d" % pistol_shots)
	outcome_auto = {
		"verdict": "pass" if auto_ok and semi_ok else "fail",
		"uzi_shots": auto_shots,
		"pistol_shots": pistol_shots,
		"cadence_ticks": cadence,
		"hold_ticks": hold,
		"source": "apply_frames hold fire uzi vs pistol",
	}
	_remember_session(session)
	return errors


static func empty_ammo_no_fire(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_aim_open", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.fighter_at_slot(0)
	_apply_slot(session, 0, PackedStringArray(), 6, 0.0)
	p1.ammo = 0
	p1.weapon_id = p1.melee_id
	_apply_slot(session, 0, PackedStringArray(["fire"]), 6, 0.0)
	_apply_release(session, 0, "fire")
	_apply_idle(session, 4)
	var ok: bool = (
		session.ledger.count_kind("bullet") == 0
		and p1.shots_fired == 0
		and _live_bullets(session) == 0
		and not p1.aiming
	)
	if not ok:
		errors.append("AMMO 0 must not fire or aim a gun")
	outcome_ammo = {
		"verdict": "pass" if ok else "fail",
		"shots": p1.shots_fired,
		"spawns": session.ledger.count_kind("bullet"),
		"ammo": p1.ammo,
		"source": "apply_frames hold+release with ammo=0",
	}
	_remember_session(session)
	return errors


static func muzzle_and_dir(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_aim_open", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.fighter_at_slot(0)
	_apply_slot(session, 0, PackedStringArray(), 6, 0.0)
	_apply_slot(session, 0, PackedStringArray(["fire", "jump"]), 8, 0.0)
	var expected: Vector2 = _Aim.muzzle_origin(p1)
	_apply_release_held(session, 0, "fire", PackedStringArray(["jump"]))
	var dir_ok: bool = p1.last_fire_dir.y < -0.4
	var muzzle_ok: bool = p1.last_muzzle.distance_to(expected) <= 1.0
	var spawn_ok: bool = false
	var events: Array = session.ledger.to_array()
	var ei: int = events.size() - 1
	while ei >= 0:
		var ev: Dictionary = events[ei] as Dictionary
		if str(ev.get("kind", "")) == "bullet":
			var payload: Dictionary = ev.get("payload", {}) as Dictionary
			spawn_ok = int(payload.get("dir_y", 0)) < -400
			break
		ei -= 1
	if not dir_ok or not muzzle_ok or not spawn_ok:
		errors.append("MUZZLE release-up must keep aim dir and spawn at muzzle")
	outcome_muzzle = {
		"verdict": "pass" if dir_ok and muzzle_ok and spawn_ok else "fail",
		"dir_y": p1.last_fire_dir.y,
		"muzzle_x": p1.last_muzzle.x,
		"muzzle_y": p1.last_muzzle.y,
		"expected_x": expected.x,
		"expected_y": expected.y,
		"spawn_ok": spawn_ok,
		"source": "hold up, release fire; last_aim_dir kept",
	}
	_remember_session(session)
	return errors


static func recoil_and_spread(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_aim_open", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.fighter_at_slot(0)
	_apply_slot(session, 0, PackedStringArray(), 8, 0.0)
	var vx0: float = p1.velocity.x
	_apply_slot(session, 0, PackedStringArray(["fire"]), 4, 0.0)
	_apply_release(session, 0, "fire")
	var recoil: float = _Aim.recoil_of("pistol")
	var recoiled: bool = p1.velocity.x < vx0 - recoil * 0.4
	p1.give_weapon("shotgun")
	p1.fire_cd = 0.0
	_clear_bullets(session)
	_apply_slot(session, 0, PackedStringArray(), 2, 0.0)
	p1.fire_cd = 0.0
	_apply_slot(session, 0, PackedStringArray(["fire"]), 3, 0.0)
	p1.fire_cd = 0.0
	_apply_release(session, 0, "fire")
	var pellets: int = _live_bullets(session)
	var spread_ok: bool = pellets >= _Aim.pellets("shotgun")
	if not recoiled:
		errors.append("RECOIL pistol must kick opposite aim")
	if not spread_ok:
		errors.append("RECOIL shotgun must spawn %d pellets got %d" % [_Aim.pellets("shotgun"), pellets])
	outcome_recoil = {
		"verdict": "pass" if recoiled and spread_ok else "fail",
		"vx0": vx0,
		"vx1": p1.velocity.x,
		"recoil": recoil,
		"pellets": pellets,
		"source": "pistol recoil impulse; shotgun pellet fan",
	}
	_remember_session(session)
	return errors


static func swept_no_tunnel(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_aim_wall", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.fighter_at_slot(0)
	var p2: Fighter = session.fighter_at_slot(1)
	_apply_slot(session, 0, PackedStringArray(), 6, 0.0)
	var hp0: float = p2.health
	var wall_right: float = 10.0 * float(Maps.TILE)
	var from: Vector2 = Vector2(80.0, 40.0)
	var wall_solid: bool = Maps.solid_at(session.map_id, Vector2(152.0, 40.0))
	var shot: Bullet = Bullet.new()
	shot.setup(from, Vector2.RIGHT, 4000.0, 10.0, p1.slot, p1.team)
	session.add_child(shot)
	session.bullets.append(shot)
	_apply_idle(session, 6)
	var past: int = 0
	var farthest: float = from.x
	var i: int = 0
	while i < session.bullets.size():
		var live: Bullet = session.bullets[i]
		if live != null and is_instance_valid(live):
			farthest = maxf(farthest, live.global_position.x)
			if live.global_position.x > wall_right + 2.0:
				past += 1
		i += 1
	var hp_ok: bool = p2.health >= hp0 - 0.01
	var blocked: bool = past == 0 and hp_ok and wall_solid
	if not blocked:
		errors.append(
			"SWEEP high-speed bullet must not tunnel the wall map=%s solid=%s past=%d hp=%s/%s far=%s"
			% [session.map_id, str(wall_solid), past, str(hp0), str(p2.health), str(farthest)]
		)
	outcome_sweep = {
		"verdict": "pass" if blocked else "fail",
		"hp0": hp0,
		"hp1": p2.health,
		"past_wall": past,
		"wall_solid": wall_solid,
		"map_id": session.map_id,
		"speed": 4000.0,
		"source": "4000 px/s ballistic sweep vs Cover Wall",
	}
	_remember_session(session)
	return errors


static func live_aim_fire(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_aim_open", 0)
	var session: GameSession = app.session
	var p1: Fighter = session.fighter_at_slot(0)
	var viewport: Viewport = app.get_viewport()
	await SimReplay.sync_physics(app)
	InputInjector.release_known(viewport)
	InputActions.reset_edges()
	used_parse_input_event += 1
	_apply_slot(session, 0, PackedStringArray(), 6, 0.0)
	InputInjector.inject_key(KEY_M, true, viewport)
	var n: int = 0
	while n < 8:
		session.step_from_live_input()
		n += 1
	var held_ok: bool = p1.aiming and p1.shots_fired == 0
	InputInjector.inject_key(KEY_M, false, viewport)
	session.step_from_live_input()
	var live_ok: bool = held_ok and p1.shots_fired == 1
	if not live_ok:
		errors.append("LIVE KEY_M hold must aim; release must fire")
	InputInjector.release_known(viewport)
	outcome_live = {
		"verdict": "pass" if live_ok else "fail",
		"held_aiming": held_ok,
		"shots": p1.shots_fired,
		"source": "parse_input_event KEY_M + step_from_live_input",
	}
	_remember_session(session)
	return errors


static func _require_outcomes() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var labels: PackedStringArray = PackedStringArray([
		"HOLD", "DIRS", "SEMI", "AUTO", "AMMO", "MUZZLE", "RECOIL", "DATA", "SWEEP", "LIVE"
	])
	var rows: Array = [
		outcome_hold, outcome_dirs, outcome_semi, outcome_auto, outcome_ammo,
		outcome_muzzle, outcome_recoil, outcome_data, outcome_sweep, outcome_live
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


static func _gun_diffs(pistol: Dictionary, uzi: Dictionary, shotgun: Dictionary) -> PackedStringArray:
	var keys: PackedStringArray = PackedStringArray([
		"auto", "cadence_ticks", "damage", "pellets", "spread", "speed", "recoil", "ammo",
		"muzzle_forward", "muzzle_lift"
	])
	var out: PackedStringArray = PackedStringArray()
	var i: int = 0
	while i < keys.size():
		var key: String = String(keys[i])
		var a: String = str(pistol.get(key, ""))
		var b: String = str(uzi.get(key, ""))
		var c: String = str(shotgun.get(key, ""))
		if a != b and a != c and b != c:
			out.append(key)
		elif a != b or a != c or b != c:
			out.append(key)
		i += 1
	return out


static func _apply_release(session: GameSession, slot: int, action: String) -> void:
	_apply_release_held(session, slot, action, PackedStringArray())


static func _apply_release_held(
	session: GameSession, slot: int, action: String, held: PackedStringArray
) -> void:
	var frames: Array = []
	var i: int = 0
	while i < session.fighters.size():
		var raw: Dictionary = InputActions.empty_frame(session.clock.tick, i)
		if i == slot:
			raw["released"] = [action]
			raw["held"] = Array(held)
		frames.append(InputFrame.from_dict(raw))
		i += 1
	_record_apply(session.apply_frames(frames))


static func _clear_bullets(session: GameSession) -> void:
	var i: int = 0
	while i < session.bullets.size():
		var shot: Bullet = session.bullets[i]
		if shot != null and is_instance_valid(shot):
			shot.queue_free()
		i += 1
	session.bullets.clear()


static func _apply_slot(session: GameSession, slot: int, held: PackedStringArray, ticks: int, move_x: float) -> void:
	var n: int = 0
	while n < ticks:
		var frames: Array = []
		var i: int = 0
		while i < session.fighters.size():
			var raw: Dictionary = InputActions.empty_frame(session.clock.tick, i)
			if i == slot:
				raw["held"] = Array(held)
				raw["move_x"] = move_x
				if n == 0 and not held.is_empty():
					raw["pressed"] = Array(held)
			frames.append(InputFrame.from_dict(raw))
			i += 1
		_record_apply(session.apply_frames(frames))
		n += 1


static func _apply_idle(session: GameSession, ticks: int) -> void:
	var n: int = 0
	while n < ticks:
		var frames: Array = []
		var i: int = 0
		while i < session.fighters.size():
			frames.append(InputFrame.from_dict(InputActions.empty_frame(session.clock.tick, i)))
			i += 1
		_record_apply(session.apply_frames(frames))
		n += 1


static func _live_bullets(session: GameSession) -> int:
	var n: int = 0
	var i: int = 0
	while i < session.bullets.size():
		var shot: Bullet = session.bullets[i]
		if shot != null and is_instance_valid(shot) and not shot.spent:
			n += 1
		i += 1
	return n


static func _drain_physics(app: App) -> void:
	InputActions.reset_edges()
	await SimReplay.sync_physics(app)
	await SimReplay.sync_physics(app)


static func _capture_start(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_aim_open", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	if session == null:
		errors.append("start snapshot missing session")
		return errors
	snapshot_start = session.snapshot()
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

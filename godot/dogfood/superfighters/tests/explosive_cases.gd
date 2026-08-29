class_name ExplosiveCases
extends RefCounted

const _Expl: GDScript = preload("res://src/sim/explosive.gd")

## VF3-WP4 official grenade / explosive cases.
## Proof is InputFrame apply_frames plus live InputEvent inject.
## 60 Hz is ledger:RL-SIM-FIXED-60 (assumption).
## Hold-to-throw stays ledger:RL-NADE-HOLD (assumption).
## Arc / bounce / fuse / falloff / owner / once / timeout / sweep
## stay assumption. Prop break stays deferred VF4.
## Hold-to-aim stays ledger:RL-CTRL-HOLD-AIM (assumption).
## Y8 roll/dive stays unavailable. USED_APPLY_FRAMES counts success only.

static var used_step_fixed: int = 0
static var used_apply_frames: int = 0
static var used_apply_frames_attempted: int = 0
static var used_apply_frames_succeeded: int = 0
static var used_parse_input_event: int = 0
static var used_action_press: int = 0
static var outcome_hold: Dictionary = {}
static var outcome_throw: Dictionary = {}
static var outcome_arc: Dictionary = {}
static var outcome_bounce: Dictionary = {}
static var outcome_fuse: Dictionary = {}
static var outcome_falloff: Dictionary = {}
static var outcome_owner: Dictionary = {}
static var outcome_once: Dictionary = {}
static var outcome_timeout: Dictionary = {}
static var outcome_sweep: Dictionary = {}
static var outcome_data: Dictionary = {}
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
	outcome_throw = {"verdict": "unproven"}
	outcome_arc = {"verdict": "unproven"}
	outcome_bounce = {"verdict": "unproven"}
	outcome_fuse = {"verdict": "unproven"}
	outcome_falloff = {"verdict": "unproven"}
	outcome_owner = {"verdict": "unproven"}
	outcome_once = {"verdict": "unproven"}
	outcome_timeout = {"verdict": "unproven"}
	outcome_sweep = {"verdict": "unproven"}
	outcome_data = {"verdict": "unproven"}
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
	_append(errors, await hold_does_not_throw(app))
	_append(errors, await release_throws(app))
	_append(errors, await arc_gravity(app))
	_append(errors, await bounce_floor(app))
	_append(errors, await fuse_explodes(app))
	_append(errors, await falloff_and_owner(app))
	_append(errors, await explode_once_and_timeout(app))
	_append(errors, await swept_no_tunnel(app))
	_append(errors, await live_throw(app))
	_append(errors, _require_outcomes())
	return errors


static func schema_and_data() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var row: Dictionary = _Expl.data()
	if str(row.get("schema", "")) != _Expl.SCHEMA_ID:
		errors.append("explosive schema id mismatch")
	if str(row.get("title", "")) != "Vault Fighters":
		errors.append("explosive title must be Vault Fighters")
	if bool(row.get("y8_parity_claimed", true)):
		errors.append("explosive must not claim Y8 parity")
	if str(row.get("hold_throw_class", "")) != "assumption":
		errors.append("hold-to-throw must stay assumption")
	if str(row.get("arc_class", "")) != "assumption":
		errors.append("arc must stay assumption")
	if str(row.get("bounce_class", "")) != "assumption":
		errors.append("bounce must stay assumption")
	if str(row.get("fuse_class", "")) != "assumption":
		errors.append("fuse must stay assumption")
	if str(row.get("falloff_class", "")) != "assumption":
		errors.append("falloff must stay assumption")
	if str(row.get("owner_class", "")) != "assumption":
		errors.append("owner rule must stay assumption")
	if str(row.get("once_class", "")) != "assumption":
		errors.append("once rule must stay assumption")
	if str(row.get("timeout_class", "")) != "assumption":
		errors.append("timeout must stay assumption")
	if str(row.get("sweep_class", "")) != "assumption":
		errors.append("nade sweep must stay assumption")
	if str(row.get("prop_break_class", "")) != "deferred":
		errors.append("prop break must stay deferred VF4")
	if str(row.get("hold_to_aim_class", "")) != "assumption":
		errors.append("hold-to-aim must stay assumption")
	if str(row.get("roll_dive_class", "")) != "unavailable":
		errors.append("Y8 roll/dive observation must stay unavailable")
	if bool(row.get("owner_self_damage", true)):
		errors.append("owner_self_damage must be forbidden")
	if str(row.get("collision", "")) != "swept":
		errors.append("nade collision must be swept")
	if str(row.get("prop_break", "")) != "deferred_vf4":
		errors.append("prop_break must be deferred_vf4")
	if not Maps.has_fixture("fx_nade_open") or not Maps.has_fixture("fx_nade_wall"):
		errors.append("explosive fixtures missing")
	if not Maps.has_fixture("fx_nade_blast"):
		errors.append("blast fixture missing")
	if not Maps.solid_at("fx_nade_wall", Vector2(152.0, 40.0)):
		errors.append("nade wall fixture must be solid at cover column")
	var spec: Dictionary = _Expl.nade()
	if spec.is_empty() or float(spec.get("radius", 0.0)) <= 0.0:
		errors.append("grenade spec missing radius")
	if int(spec.get("fuse_ticks", 0)) < 2:
		errors.append("grenade fuse_ticks must be >1")
	if Maps.display_name("fx_nade_open").to_lower().contains("superfighter"):
		errors.append("nade fixture display name must stay original")
	outcome_data = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"fuse_ticks": int(spec.get("fuse_ticks", 0)),
		"radius": float(spec.get("radius", 0.0)),
		"owner_self_damage": false,
		"prop_break": str(row.get("prop_break", "")),
		"source": "explosive.json grenade + fixtures",
	}
	return errors


static func replay_traces_twice(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var paths: PackedStringArray = SimTrace.list_dir(SimConstants.EXPLOSIVE_TRACE_DIR)
	if paths.size() < 6:
		errors.append("expected >=6 explosive traces, got %d" % paths.size())
	var required: PackedStringArray = PackedStringArray([
		"nade_hold", "nade_throw", "nade_arc", "nade_bounce", "nade_fuse", "nade_wall"
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
			errors.append("expl %s run1 failed: %s" % [path.get_file(), _join(a)])
		if not bool(b.get("ok", false)):
			errors.append("expl %s run2 failed: %s" % [path.get_file(), _join(b)])
		if not bool(a.get("used_apply_frames", false)) or bool(a.get("used_cmd_dicts", true)):
			errors.append("expl %s MATCH used cmd dicts" % path.get_file())
		var hash_a: String = str(a.get("final_hash", ""))
		var hash_b: String = str(b.get("final_hash", ""))
		var match_ok: bool = hash_a != "" and hash_a == hash_b
		if not match_ok:
			errors.append("expl %s replay hashes differ" % path.get_file())
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
			errors.append("missing explosive trace %s" % String(required[i]))
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


static func hold_does_not_throw(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_nade_open", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.fighter_at_slot(0)
	_apply_slot(session, 0, PackedStringArray(), 8, 0.0)
	var spawn0: int = session.ledger.count_kind("nade")
	var nades0: int = p1.grenades
	_apply_slot(session, 0, PackedStringArray(["grenade"]), 10, 0.0)
	var spawn1: int = session.ledger.count_kind("nade")
	var ok: bool = (
		p1.aiming
		and spawn1 == spawn0
		and p1.grenades == nades0
		and _live_nades(session) == 0
	)
	if not ok:
		errors.append("HOLD grenade must aim and not throw")
	outcome_hold = {
		"verdict": "pass" if ok else "fail",
		"aiming": p1.aiming,
		"spawns": spawn1 - spawn0,
		"nades": p1.grenades,
		"source": "apply_frames hold grenade, no release",
	}
	_remember_session(session)
	_append_events(session.ledger.to_array())
	return errors


static func release_throws(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_nade_open", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.fighter_at_slot(0)
	_apply_slot(session, 0, PackedStringArray(), 8, 0.0)
	var nades0: int = p1.grenades
	_apply_slot(session, 0, PackedStringArray(["grenade"]), 6, 0.0)
	var during: int = session.ledger.count_kind("nade")
	_apply_release(session, 0, "grenade")
	var after: int = session.ledger.count_kind("nade")
	var ok: bool = during == 0 and after == 1 and p1.grenades == nades0 - 1 and _live_nades(session) == 1
	if not ok:
		errors.append("THROW release must spawn one grenade")
	outcome_throw = {
		"verdict": "pass" if ok else "fail",
		"during": during,
		"after": after,
		"nades0": nades0,
		"nades1": p1.grenades,
		"live": _live_nades(session),
		"source": "apply_frames hold then released grenade",
	}
	_remember_session(session)
	_append_events(session.ledger.to_array())
	return errors


static func arc_gravity(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_nade_open", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_apply_slot(session, 0, PackedStringArray(), 6, 0.0)
	_apply_slot(session, 0, PackedStringArray(["grenade", "jump"]), 4, 0.0)
	_apply_release_held(session, 0, "grenade", PackedStringArray(["jump"]))
	if _live_nades(session) < 1:
		errors.append("ARC must spawn a grenade")
		outcome_arc = {"verdict": "fail", "source": "no grenade"}
		return errors
	var nade: ThrownGrenade = _first_nade(session)
	var y0: float = nade.global_position.y
	var vy0: float = nade.velocity.y
	_apply_idle(session, 10)
	nade = _first_nade(session)
	var y1: float = y0
	var vy1: float = vy0
	if nade != null:
		y1 = nade.global_position.y
		vy1 = nade.velocity.y
	var ok: bool = vy1 > vy0 + 8.0
	if not ok:
		errors.append("ARC gravity must increase vy got %s -> %s" % [str(vy0), str(vy1)])
	outcome_arc = {
		"verdict": "pass" if ok else "fail",
		"y0": y0,
		"y1": y1,
		"vy0": vy0,
		"vy1": vy1,
		"source": "hold up, release, gravity on ballistic nade",
	}
	_remember_session(session)
	return errors


static func bounce_floor(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_nade_open", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_apply_slot(session, 0, PackedStringArray(), 6, 0.0)
	_apply_slot(session, 0, PackedStringArray(["grenade"]), 4, 0.0)
	_apply_release(session, 0, "grenade")
	var nade: ThrownGrenade = _first_nade(session)
	if nade == null:
		errors.append("BOUNCE must spawn a grenade")
		outcome_bounce = {"verdict": "fail", "source": "no grenade"}
		return errors
	var floor_y: float = 3.0 * float(Maps.TILE)
	_apply_idle(session, 36)
	nade = _first_nade(session)
	var bounces: int = 0
	var y: float = 0.0
	if nade != null:
		bounces = nade.bounce_count
		y = nade.global_position.y
	var ok: bool = bounces >= 1 and (nade == null or y <= floor_y + 2.0)
	if not ok:
		errors.append("BOUNCE must hit the floor without tunneling bounces=%d y=%s" % [bounces, str(y)])
	outcome_bounce = {
		"verdict": "pass" if ok else "fail",
		"bounces": bounces,
		"y": y,
		"floor_y": floor_y,
		"source": "throw then idle until floor contact",
	}
	_remember_session(session)
	return errors


static func fuse_explodes(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_nade_open", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_apply_slot(session, 0, PackedStringArray(), 6, 0.0)
	_apply_slot(session, 0, PackedStringArray(["grenade"]), 4, 0.0)
	_apply_release(session, 0, "grenade")
	var fuse: int = _Expl.fuse_ticks()
	_apply_idle(session, fuse + 4)
	var blasts: int = session.ledger.count_kind("explosion")
	var leftover: int = _live_nades(session)
	var prop: String = ""
	var events: Array = session.ledger.to_array()
	var ei: int = events.size() - 1
	while ei >= 0:
		var ev: Dictionary = events[ei] as Dictionary
		if str(ev.get("kind", "")) == "explosion":
			var payload: Dictionary = ev.get("payload", {}) as Dictionary
			prop = str(payload.get("prop_break", ""))
			break
		ei -= 1
	var ok: bool = blasts == 1 and leftover == 0 and prop == "deferred_vf4"
	if not ok:
		errors.append("FUSE must explode once then cleanup blasts=%d leftover=%d prop=%s" % [
			blasts, leftover, prop
		])
	outcome_fuse = {
		"verdict": "pass" if ok else "fail",
		"blasts": blasts,
		"leftover": leftover,
		"fuse_ticks": fuse,
		"prop_break": prop,
		"source": "throw then idle fuse_ticks",
	}
	_remember_session(session)
	_append_events(session.ledger.to_array())
	return errors


static func falloff_and_owner(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_nade_blast", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.fighter_at_slot(0)
	var p2: Fighter = session.fighter_at_slot(1)
	_apply_slot(session, 0, PackedStringArray(), 6, 0.0)
	_clear_invuln(p1)
	_clear_invuln(p2)
	var at: Vector2 = p1.global_position
	p2.global_position = at + Vector2(12.0, 0.0)
	p2.velocity = Vector2.ZERO
	var hp1_0: float = p1.health
	var hp2_near0: float = p2.health
	_plant_nade(session, at, p1, 1, 8)
	_apply_idle(session, 3)
	var hp1_1: float = p1.health
	var hp2_near1: float = p2.health
	var near_dmg: float = hp2_near0 - hp2_near1
	var owner_ok: bool = absf(hp1_1 - hp1_0) <= 0.01
	app.start_fight("vs2", "fx_nade_blast", 0)
	await SimReplay.sync_physics(app)
	session = app.session
	p1 = session.fighter_at_slot(0)
	p2 = session.fighter_at_slot(1)
	_apply_slot(session, 0, PackedStringArray(), 6, 0.0)
	_clear_invuln(p1)
	_clear_invuln(p2)
	at = p1.global_position
	p2.global_position = at + Vector2(36.0, 0.0)
	p2.velocity = Vector2.ZERO
	var hp2_far0: float = p2.health
	_plant_nade(session, at, p1, 1, 8)
	_apply_idle(session, 3)
	var hp2_far1: float = p2.health
	var far_dmg: float = hp2_far0 - hp2_far1
	var expect_near: float = _Expl.blast_damage_of(_Expl.damage(), 12.0, _Expl.radius())
	var expect_far: float = _Expl.blast_damage_of(_Expl.damage(), 36.0, _Expl.radius())
	var fall_ok: bool = near_dmg > far_dmg + 1.0 and absf(near_dmg - expect_near) <= 0.6 and absf(far_dmg - expect_far) <= 0.6
	if not owner_ok:
		errors.append("OWNER must not take self blast hp=%s->%s" % [str(hp1_0), str(hp1_1)])
	if not fall_ok:
		errors.append("FALLOFF near=%s far=%s expect %s/%s" % [
			str(near_dmg), str(far_dmg), str(expect_near), str(expect_far)
		])
	outcome_owner = {
		"verdict": "pass" if owner_ok else "fail",
		"hp0": hp1_0,
		"hp1": hp1_1,
		"rule": "owner_self_damage=false",
		"source": "planted blast at owner feet",
	}
	outcome_falloff = {
		"verdict": "pass" if fall_ok else "fail",
		"near": near_dmg,
		"far": far_dmg,
		"expect_near": expect_near,
		"expect_far": expect_far,
		"source": "same blast data, 12px vs 36px",
	}
	_remember_session(session)
	return errors


static func explode_once_and_timeout(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_nade_open", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.fighter_at_slot(0)
	_apply_slot(session, 0, PackedStringArray(), 6, 0.0)
	_plant_nade(session, p1.global_position + Vector2(20.0, -6.0), p1, 999, 6)
	_apply_idle(session, 8)
	var blasts: int = session.ledger.count_kind("explosion")
	var leftover: int = _live_nades(session)
	_apply_idle(session, 10)
	var blasts2: int = session.ledger.count_kind("explosion")
	var once_ok: bool = blasts == 1 and blasts2 == 1
	var timeout_ok: bool = leftover == 0 and blasts == 1
	if not once_ok:
		errors.append("ONCE explosion count drifted %d -> %d" % [blasts, blasts2])
	if not timeout_ok:
		errors.append("TIMEOUT must cleanup leftover=%d blasts=%d" % [leftover, blasts])
	outcome_once = {
		"verdict": "pass" if once_ok else "fail",
		"blasts": blasts,
		"blasts_later": blasts2,
		"source": "one explosion event, no second pulse",
	}
	outcome_timeout = {
		"verdict": "pass" if timeout_ok else "fail",
		"leftover": leftover,
		"blasts": blasts,
		"life_ticks": 6,
		"source": "life_ticks expires, node leaves the array",
	}
	_remember_session(session)
	_append_events(session.ledger.to_array())
	return errors


static func swept_no_tunnel(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_nade_wall", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.fighter_at_slot(0)
	var p2: Fighter = session.fighter_at_slot(1)
	_apply_slot(session, 0, PackedStringArray(), 6, 0.0)
	var hp0: float = p2.health
	var wall_right: float = 10.0 * float(Maps.TILE)
	var from: Vector2 = Vector2(80.0, 40.0)
	var wall_solid: bool = Maps.solid_at(session.map_id, Vector2(152.0, 40.0))
	var nade: ThrownGrenade = ThrownGrenade.new()
	nade.setup(from, Vector2.RIGHT, p1.slot, p1.team)
	nade.velocity = Vector2(4000.0, 0.0)
	nade.fuse_ticks = 60
	nade.life_ticks = 60
	nade.fuse = float(nade.fuse_ticks) * SimConstants.TICK_DT
	session.add_child(nade)
	session.grenades.append(nade)
	_apply_idle(session, 6)
	var past: int = 0
	var farthest: float = from.x
	var i: int = 0
	while i < session.grenades.size():
		var live: ThrownGrenade = session.grenades[i]
		if live != null and is_instance_valid(live):
			farthest = maxf(farthest, live.global_position.x)
			if live.global_position.x > wall_right + 2.0:
				past += 1
		i += 1
	var hp_ok: bool = p2.health >= hp0 - 0.01
	var blocked: bool = past == 0 and hp_ok and wall_solid and farthest <= wall_right + 2.0
	if not blocked:
		errors.append(
			"SWEEP high-speed nade must not tunnel the wall map=%s solid=%s past=%d hp=%s/%s far=%s"
			% [session.map_id, str(wall_solid), past, str(hp0), str(p2.health), str(farthest)]
		)
	outcome_sweep = {
		"verdict": "pass" if blocked else "fail",
		"hp0": hp0,
		"hp1": p2.health,
		"past_wall": past,
		"wall_solid": wall_solid,
		"map_id": session.map_id,
		"farthest": farthest,
		"speed": 4000.0,
		"source": "4000 px/s ballistic nade sweep vs Nade Cover",
	}
	_remember_session(session)
	return errors


static func live_throw(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_nade_open", 0)
	var session: GameSession = app.session
	var p1: Fighter = session.fighter_at_slot(0)
	var viewport: Viewport = app.get_viewport()
	await SimReplay.sync_physics(app)
	InputInjector.release_known(viewport)
	InputActions.reset_edges()
	used_parse_input_event += 1
	_apply_slot(session, 0, PackedStringArray(), 6, 0.0)
	var nades0: int = p1.grenades
	InputInjector.inject_key(KEY_COMMA, true, viewport)
	var n: int = 0
	while n < 8:
		session.step_from_live_input()
		n += 1
	var held_ok: bool = p1.aiming and p1.grenades == nades0 and _live_nades(session) == 0
	InputInjector.inject_key(KEY_COMMA, false, viewport)
	session.step_from_live_input()
	var live_ok: bool = held_ok and p1.grenades == nades0 - 1 and _live_nades(session) == 1
	if not live_ok:
		errors.append("LIVE KEY_COMMA hold must aim; release must throw")
	InputInjector.release_known(viewport)
	outcome_live = {
		"verdict": "pass" if live_ok else "fail",
		"held_aiming": held_ok,
		"nades": p1.grenades,
		"live": _live_nades(session),
		"source": "parse_input_event KEY_COMMA + step_from_live_input",
	}
	_remember_session(session)
	return errors


static func _require_outcomes() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var labels: PackedStringArray = PackedStringArray([
		"HOLD", "THROW", "ARC", "BOUNCE", "FUSE", "FALLOFF", "OWNER", "ONCE",
		"TIMEOUT", "SWEEP", "DATA", "LIVE"
	])
	var rows: Array = [
		outcome_hold, outcome_throw, outcome_arc, outcome_bounce, outcome_fuse,
		outcome_falloff, outcome_owner, outcome_once, outcome_timeout,
		outcome_sweep, outcome_data, outcome_live
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


static func _plant_nade(session: GameSession, at: Vector2, owner: Fighter, fuse: int, life: int) -> ThrownGrenade:
	var nade: ThrownGrenade = ThrownGrenade.new()
	nade.setup(at, Vector2.RIGHT, owner.slot, owner.team)
	nade.global_position = at
	nade.last_pos = at
	nade.velocity = Vector2.ZERO
	nade.fuse_ticks = fuse
	nade.life_ticks = life
	nade.fuse = float(nade.fuse_ticks) * SimConstants.TICK_DT
	session.add_child(nade)
	session.grenades.append(nade)
	return nade


static func _clear_invuln(f: Fighter) -> void:
	if f == null:
		return
	f.invuln = 0.0
	f.invuln_ticks = 0


static func _first_nade(session: GameSession) -> ThrownGrenade:
	var i: int = 0
	while i < session.grenades.size():
		var nade: ThrownGrenade = session.grenades[i]
		if nade != null and is_instance_valid(nade) and not nade.applied:
			return nade
		i += 1
	return null


static func _live_nades(session: GameSession) -> int:
	var n: int = 0
	var i: int = 0
	while i < session.grenades.size():
		var nade: ThrownGrenade = session.grenades[i]
		if nade != null and is_instance_valid(nade) and not nade.applied:
			n += 1
		i += 1
	return n


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


static func _drain_physics(app: App) -> void:
	InputActions.reset_edges()
	await SimReplay.sync_physics(app)
	await SimReplay.sync_physics(app)


static func _capture_start(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_nade_open", 0)
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

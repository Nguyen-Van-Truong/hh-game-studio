class_name SprintCases
extends RefCounted

## VF2-WP3 official sprint / stamina / roll cases.
## Proof is InputFrame apply_frames plus live InputEvent inject.
## 60 Hz is ledger:RL-SIM-FIXED-60 (assumption).
## Sprint/roll stay ledger:RL-MOVE-SPRINT / RL-MOVE-ROLL (assumption).
## Hold-to-aim stays assumption. Dive/kick are VF2-WP4 assumption.
## Y8 observation stays unavailable.
## USED_APPLY_FRAMES counts successful apply_frames only.

static var used_step_fixed: int = 0
static var used_apply_frames: int = 0
static var used_apply_frames_attempted: int = 0
static var used_apply_frames_succeeded: int = 0
static var used_parse_input_event: int = 0
static var used_action_press: int = 0
static var outcome_tap: Dictionary = {}
static var outcome_stamina: Dictionary = {}
static var outcome_roll: Dictionary = {}
static var outcome_invuln: Dictionary = {}
static var outcome_dup: Dictionary = {}
static var outcome_live: Dictionary = {}
static var outcome_replay: Dictionary = {}
static var snapshot_start: Dictionary = {}
static var snapshot_end: Dictionary = {}
static var events_end: Array = []


static func run_all(app: App) -> PackedStringArray:
	used_step_fixed = 0
	used_apply_frames = 0
	used_apply_frames_attempted = 0
	used_apply_frames_succeeded = 0
	used_parse_input_event = 0
	used_action_press = 0
	outcome_tap = {"verdict": "unproven"}
	outcome_stamina = {"verdict": "unproven"}
	outcome_roll = {"verdict": "unproven"}
	outcome_invuln = {"verdict": "unproven"}
	outcome_dup = {"verdict": "unproven"}
	outcome_live = {"verdict": "unproven"}
	outcome_replay = {"verdict": "unproven", "pairs": []}
	snapshot_start = {}
	snapshot_end = {}
	events_end = []
	var errors: PackedStringArray = PackedStringArray()
	_append(errors, schema_and_data())
	_append(errors, await _capture_start(app))
	_append(errors, await replay_traces_twice(app))
	_append(errors, await tap_timing(app))
	_append(errors, await stamina_conservation(app))
	_append(errors, await roll_contract(app))
	_append(errors, await roll_invuln_projectile(app))
	_append(errors, await repeated_roll_no_duplicate(app))
	_append(errors, await blocked_roll(app))
	_append(errors, await live_double_tap_and_roll(app))
	_append(errors, _require_outcomes())
	return errors


static func schema_and_data() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var loco: Dictionary = Locomotion.data()
	if str(loco.get("schema", "")) != Locomotion.SCHEMA_ID:
		errors.append("locomotion schema id mismatch")
	if str(loco.get("title", "")) != "Vault Fighters":
		errors.append("locomotion title must be Vault Fighters")
	if bool(loco.get("y8_parity_claimed", true)):
		errors.append("sprint/roll must not claim Y8 parity")
	if str(loco.get("sprint_class", "")) != "assumption":
		errors.append("sprint must stay assumption")
	if str(loco.get("roll_class", "")) != "assumption":
		errors.append("roll must stay assumption")
	if str(loco.get("hold_to_aim_class", "")) != "assumption":
		errors.append("hold-to-aim must stay assumption")
	if str(loco.get("roll_dive_class", "")) != "unavailable":
		errors.append("Y8 roll/dive observation must stay unavailable")
	if str(loco.get("dive_class", "")) != "assumption":
		errors.append("product dive must stay assumption")
	if str(loco.get("sprint_ledger", "")) != "RL-MOVE-SPRINT":
		errors.append("sprint must cite RL-MOVE-SPRINT")
	if str(loco.get("roll_ledger", "")) != "RL-MOVE-ROLL":
		errors.append("roll must cite RL-MOVE-ROLL")
	var reserved: Array = loco.get("reserved_not_shipped", []) as Array
	if reserved.has("roll") or reserved.has("dive") or reserved.has("kick"):
		errors.append("roll/dive/kick must not stay reserved")
	if not reserved.has("ledge"):
		errors.append("ledge must stay reserved")
	if not SimValidator.ALLOWED.has("roll"):
		errors.append("InputFrame must allow roll")
	if not SimValidator.ALLOWED.has("dive"):
		errors.append("InputFrame must allow dive")
	if not SimValidator.ALLOWED.has("kick"):
		errors.append("InputFrame must allow kick")
	return errors


static func replay_traces_twice(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var paths: PackedStringArray = SimTrace.list_dir(SimConstants.SPRINT_TRACE_DIR)
	if paths.size() < 4:
		errors.append("expected >=4 sprint traces, got %d" % paths.size())
	var required: PackedStringArray = PackedStringArray([
		"double_tap_sprint", "tap_window_miss", "crouch_roll", "stamina_drain"
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
		if "assumption" not in str(trace.get("roll", "")):
			errors.append("%s must keep roll assumption" % path.get_file())
		if "assumption" not in str(trace.get("sprint", "")):
			errors.append("%s must keep sprint assumption" % path.get_file())
		names.append(str(trace.get("name", path.get_file())))
		var a: Dictionary = await SimReplay.play_path(app, path)
		var b: Dictionary = await SimReplay.play_path(app, path)
		_record_apply_batch(int(a.get("ticks", 0)), bool(a.get("ok", false)))
		_record_apply_batch(int(b.get("ticks", 0)), bool(b.get("ok", false)))
		if not bool(a.get("ok", false)):
			errors.append("sprint %s run1 failed: %s" % [path.get_file(), _join(a)])
		if not bool(b.get("ok", false)):
			errors.append("sprint %s run2 failed: %s" % [path.get_file(), _join(b)])
		if not bool(a.get("used_apply_frames", false)) or bool(a.get("used_cmd_dicts", true)):
			errors.append("sprint %s MATCH used cmd dicts" % path.get_file())
		var hash_a: String = str(a.get("final_hash", ""))
		var hash_b: String = str(b.get("final_hash", ""))
		var match_ok: bool = hash_a != "" and hash_a == hash_b
		if not match_ok:
			errors.append("sprint %s replay hashes differ" % path.get_file())
		pairs.append({
			"name": str(trace.get("name", path.get_file())),
			"hash_match": match_ok,
			"ok_a": bool(a.get("ok", false)),
			"ok_b": bool(b.get("ok", false)),
			"hash_a": hash_a,
			"hash_b": hash_b,
		})
		_remember_end(a)
		_remember_end(b)
		i += 1
	i = 0
	while i < required.size():
		if not names.has(String(required[i])):
			errors.append("missing sprint trace %s" % String(required[i]))
		i += 1
	var all_match: bool = pairs.size() >= 4
	var p: int = 0
	while p < pairs.size():
		var row: Dictionary = pairs[p] as Dictionary
		if not bool(row.get("hash_match", false)) or not bool(row.get("ok_a", false)) or not bool(row.get("ok_b", false)):
			all_match = false
		p += 1
	outcome_replay = {
		"verdict": "match" if all_match else "fail",
		"pair_count": pairs.size(),
		"pairs": pairs,
		"source": "SimReplay.final_hash twice",
	}
	return errors


static func tap_timing(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "police", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	_apply_p1(session, PackedStringArray(), 12, 0.0)
	_apply_p1(session, PackedStringArray(["right"]), 2, 1.0)
	_apply_p1(session, PackedStringArray(), 2, 0.0)
	_apply_p1(session, PackedStringArray(["right"]), 8, 1.0)
	var inside_sprint: bool = p1.sprinting
	var inside_speed: bool = p1.velocity.x > p1.walk + 8.0
	var inside_event: bool = session.ledger.count_kind("sprint_start") >= 1
	if not inside_sprint:
		errors.append("double-tap inside window did not sprint")
	if not inside_speed:
		errors.append("sprint speed not reached vx=%s walk=%s sprint=%s" % [
			str(p1.velocity.x), str(p1.walk), str(p1.sprint)
		])
	if not inside_event:
		errors.append("missing sprint_start event")
	_remember_session(session)
	app.start_fight("vs2", "police", 0)
	await SimReplay.sync_physics(app)
	session = app.session
	p1 = session.player1()
	_apply_p1(session, PackedStringArray(), 12, 0.0)
	_apply_p1(session, PackedStringArray(["right"]), 2, 1.0)
	_apply_p1(session, PackedStringArray(), 16, 0.0)
	_apply_p1(session, PackedStringArray(["right"]), 8, 1.0)
	var late_sprint: bool = p1.sprinting
	var late_speed: bool = p1.velocity.x > p1.walk + 20.0
	if late_sprint:
		errors.append("double-tap outside window must not sprint")
	if late_speed:
		errors.append("late tap reached sprint speed vx=%s" % str(p1.velocity.x))
	var pass_ok: bool = inside_sprint and inside_speed and inside_event and not late_sprint and not late_speed
	outcome_tap = {
		"verdict": "pass" if pass_ok else "fail",
		"inside_window_sprint": inside_sprint,
		"inside_window_speed": inside_speed,
		"sprint_start_event": inside_event,
		"outside_window_sprint": late_sprint,
		"source": "apply_frames tap_window vs late tap",
	}
	_remember_session(session)
	return errors


static func stamina_conservation(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "police", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	_apply_p1(session, PackedStringArray(), 12, 0.0)
	var start_stamina: float = p1.stamina
	_tap_right(session, 2)
	_apply_p1(session, PackedStringArray(), 2, 0.0)
	_apply_p1(session, PackedStringArray(["right"]), 12, 1.0)
	var after_sprint: float = p1.stamina
	var drained: bool = p1.sprinting and after_sprint < start_stamina - 0.05
	if not p1.sprinting:
		errors.append("stamina case lost sprint")
	if not drained:
		errors.append("sprint did not drain stamina start=%s now=%s" % [
			str(start_stamina), str(after_sprint)
		])
	var before_roll: float = p1.stamina
	_apply_p1_roll(session, 1)
	var seq_ok: bool = p1.roll_seq == 1
	var cost_ok: bool = absf(p1.stamina - (before_roll - p1.stamina_roll_cost)) <= 0.05
	if not seq_ok:
		errors.append("stamina case roll did not start")
	if not cost_ok:
		errors.append("roll cost drifted got=%s expected=%s" % [
			str(p1.stamina), str(before_roll - p1.stamina_roll_cost)
		])
	var roll_ticks: int = int(ceil(p1.roll_duration / SimConstants.TICK_DT)) + 2
	_apply_p1(session, PackedStringArray(["right"]), roll_ticks, 1.0)
	var in_range: bool = p1.stamina >= 0.0 and p1.stamina <= Fighter.MAX_STAMINA + 0.001
	if not in_range:
		errors.append("stamina left legal range %s" % str(p1.stamina))
	if before_roll <= p1.stamina_roll_cost:
		errors.append("not enough stamina before roll for conservation proof")
	var pass_ok: bool = drained and seq_ok and cost_ok and in_range and before_roll > p1.stamina_roll_cost
	outcome_stamina = {
		"verdict": "pass" if pass_ok else "fail",
		"drained_while_sprinting": drained,
		"roll_flat_cost": cost_ok,
		"in_legal_range": in_range,
		"start": start_stamina,
		"after_sprint": after_sprint,
		"before_roll": before_roll,
		"after_roll_cost": p1.stamina + 0.0,
		"source": "apply_frames stamina drain + roll cost",
	}
	_remember_session(session)
	return errors


static func roll_contract(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var played: Dictionary = await SimReplay.play_path(
		app, "%s/crouch_roll.json" % SimConstants.SPRINT_TRACE_DIR
	)
	_record_apply_batch(int(played.get("ticks", 0)), bool(played.get("ok", false)))
	if not bool(played.get("ok", false)):
		errors.append("crouch_roll replay failed: %s" % _join(played))
		outcome_roll = {"verdict": "fail", "reason": "crouch_roll replay failed"}
		return errors
	app.start_fight("vs2", "police", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	_apply_p1(session, PackedStringArray(), 12, 0.0)
	_double_tap_sprint(session)
	var stand_h: float = p1.stand_shape.size.y
	_apply_p1_roll(session, 1)
	var started: bool = p1.rolling
	var pose_ok: bool = p1.current_pose() == "roll"
	var shape_ok: bool = p1.col_shape != null and p1.col_shape.shape == p1.roll_shape
	var shrink_ok: bool = p1.roll_shape.size.y < stand_h - 0.5
	var invuln_ok: bool = p1.invuln > 0.0
	var sfx_ok: bool = session.sfx != null and session.sfx.last_id == "roll"
	var start_events: int = session.ledger.count_kind("roll_start")
	var ext_events: int = session.ledger.count_kind("roll_extinguish")
	var hook_ok: bool = p1.fire_extinguish_count == 1
	var hud_line: Label = session.hud.get_node_or_null("Bar_0") as Label
	var hud_ok: bool = hud_line != null and hud_line.text.contains("ROLL")
	if not started:
		errors.append("explicit roll did not start")
	if not pose_ok:
		errors.append("roll pose missing got=%s" % p1.current_pose())
	if not shape_ok:
		errors.append("roll did not swap collision footprint")
	if not shrink_ok:
		errors.append("roll AABB must shrink stand=%s roll=%s" % [
			str(stand_h), str(p1.roll_shape.size.y)
		])
	if not invuln_ok:
		errors.append("roll must set invuln window")
	if not sfx_ok:
		errors.append("roll SFX last_id must be roll")
	if start_events != 1:
		errors.append("expected one roll_start got=%d" % start_events)
	if ext_events != 1:
		errors.append("missing roll_extinguish hook event")
	if not hook_ok:
		errors.append("extinguish-fire hook count=%d" % p1.fire_extinguish_count)
	if not hud_ok:
		errors.append("HUD must show ROLL feedback")
	var pass_ok: bool = (
		started and pose_ok and shape_ok and shrink_ok and invuln_ok
		and sfx_ok and start_events == 1 and ext_events == 1 and hook_ok and hud_ok
	)
	outcome_roll = {
		"verdict": "pass" if pass_ok else "fail",
		"started": started,
		"pose": p1.current_pose(),
		"footprint_swapped": shape_ok,
		"aabb_shrunk": shrink_ok,
		"invuln": p1.invuln,
		"sfx_last_id": session.sfx.last_id if session.sfx != null else "",
		"hud_roll": hud_ok,
		"roll_start_events": start_events,
		"extinguish_events": ext_events,
		"extinguish_count": p1.fire_extinguish_count,
		"source": "apply_frames roll pose/AABB/SFX/HUD/VFX hook",
	}
	_remember_session(session)
	return errors


static func roll_invuln_projectile(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "police", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	_apply_p1(session, PackedStringArray(), 12, 0.0)
	_double_tap_sprint(session)
	_apply_p1_roll(session, 1)
	if not p1.rolling or p1.invuln <= 0.0:
		errors.append("invuln case never entered roll")
		outcome_invuln = {"verdict": "fail", "reason": "never entered roll"}
		return errors
	p1.health = 80.0
	p1.combat_timer = 3.0
	_spawn_bullet(session, p1, 25.0)
	_apply_p1(session, PackedStringArray(["right"]), 1, 1.0)
	var inside_ok: bool = p1.health >= 80.0 - 0.01
	if not inside_ok:
		errors.append("projectile damaged through roll invuln hp=%s" % str(p1.health))
	var wait: int = int(ceil(p1.roll_invuln / SimConstants.TICK_DT)) + 2
	_apply_p1(session, PackedStringArray(), wait, 0.0)
	var expired: bool = p1.invuln <= 0.0
	if not expired:
		errors.append("invuln still active after window invuln=%s" % str(p1.invuln))
	var hp0: float = p1.health
	p1.combat_timer = 3.0
	_spawn_bullet(session, p1, 25.0)
	_apply_p1(session, PackedStringArray(), 1, 0.0)
	var outside_ok: bool = p1.health < hp0 - 0.01
	if not outside_ok:
		errors.append("projectile outside invuln did not damage hp0=%s hp1=%s" % [
			str(hp0), str(p1.health)
		])
	var pass_ok: bool = inside_ok and expired and outside_ok
	outcome_invuln = {
		"verdict": "pass" if pass_ok else "fail",
		"inside_invuln_undamaged": inside_ok,
		"window_expired": expired,
		"outside_invuln_damaged": outside_ok,
		"hp_inside": 80.0 if inside_ok else p1.health,
		"hp_outside": p1.health,
		"source": "Bullet vs roll invuln window",
	}
	_remember_session(session)
	return errors


static func repeated_roll_no_duplicate(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "police", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	_apply_p1(session, PackedStringArray(), 12, 0.0)
	_double_tap_sprint(session)
	_apply_p1_roll(session, 1)
	var seq0: int = p1.roll_seq
	var starts0: int = session.ledger.count_kind("roll_start")
	var n: int = 0
	while n < 10:
		_apply_p1_roll(session, 1)
		n += 1
	var seq_ok: bool = p1.roll_seq == seq0
	var start_ok: bool = session.ledger.count_kind("roll_start") == starts0
	var ext_ok: bool = session.ledger.count_kind("roll_extinguish") == starts0
	if not seq_ok:
		errors.append("repeated roll duplicated seq %d -> %d" % [seq0, p1.roll_seq])
	if not start_ok:
		errors.append("repeated roll duplicated roll_start events")
	if not ext_ok:
		errors.append("repeated roll duplicated extinguish events")
	outcome_dup = {
		"verdict": "pass" if seq_ok and start_ok and ext_ok else "fail",
		"seq": p1.roll_seq,
		"seq0": seq0,
		"roll_start_events": session.ledger.count_kind("roll_start"),
		"extinguish_events": session.ledger.count_kind("roll_extinguish"),
		"source": "10 extra roll presses during committed roll",
	}
	_remember_session(session)
	return errors


static func blocked_roll(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "police", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	_apply_p1(session, PackedStringArray(), 12, 0.0)
	p1.kill()
	_apply_p1_roll(session, 1)
	var dead_ok: bool = not p1.rolling and p1.roll_seq == 0
	if not dead_ok:
		errors.append("dead fighter started a roll")
	app.start_fight("vs2", "police", 0)
	await SimReplay.sync_physics(app)
	session = app.session
	p1 = session.player1()
	_apply_p1(session, PackedStringArray(), 12, 0.0)
	session.set_paused(true)
	var paused_applied: bool = _try_roll_bundle(session)
	var paused_reject: bool = session.last_reject.has("paused") or ",".join(session.last_reject).contains("paused")
	var paused_ok: bool = not paused_applied and paused_reject and not p1.rolling
	if paused_applied:
		errors.append("paused apply_frames accepted a roll")
	if not paused_reject:
		errors.append("paused roll reject missing paused got=%s" % ",".join(session.last_reject))
	if p1.rolling:
		errors.append("paused fighter entered roll")
	session.set_paused(false)
	_apply_p1(session, PackedStringArray(["jump"]), 4, 0.0)
	_apply_p1_roll(session, 1)
	var air_ok: bool = not p1.rolling and p1.last_roll_block == "air"
	if p1.rolling:
		errors.append("airborne roll must be blocked")
	if p1.last_roll_block != "air":
		errors.append("airborne block reason=%s" % p1.last_roll_block)
	_apply_p1(session, PackedStringArray(), 20, 0.0)
	p1.stamina = 5.0
	_apply_p1_roll(session, 1)
	var stam_ok: bool = not p1.rolling and p1.last_roll_block == "stamina"
	if p1.rolling:
		errors.append("low-stamina roll must be blocked")
	if p1.last_roll_block != "stamina":
		errors.append("stamina block reason=%s" % p1.last_roll_block)
	if not (dead_ok and paused_ok and air_ok and stam_ok):
		# structured block case is part of roll contract, not a separate banner
		pass
	_remember_session(session)
	return errors


static func live_double_tap_and_roll(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "police", 0)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	var viewport: Viewport = app.get_viewport()
	await SimReplay.sync_physics(app)
	InputInjector.release_known(viewport)
	InputActions.reset_edges()
	used_parse_input_event += 1
	_apply_p1(session, PackedStringArray(), 8, 0.0)
	InputInjector.inject_key(KEY_RIGHT, true, viewport)
	var n: int = 0
	while n < 3:
		session.step_from_live_input()
		n += 1
	InputInjector.inject_key(KEY_RIGHT, false, viewport)
	n = 0
	while n < 2:
		session.step_from_live_input()
		n += 1
	InputInjector.inject_key(KEY_RIGHT, true, viewport)
	n = 0
	while n < 8:
		session.step_from_live_input()
		n += 1
	var live_sprint: bool = p1.sprinting
	if not live_sprint:
		errors.append("live InputEvent double-tap did not sprint")
	InputInjector.inject_key(KEY_DOWN, true, viewport)
	n = 0
	while n < 3:
		session.step_from_live_input()
		n += 1
	var live_roll: bool = p1.rolling
	if not live_roll:
		errors.append("live crouch-while-sprint did not roll pose=%s" % p1.current_pose())
	InputInjector.release_known(viewport)
	outcome_live = {
		"verdict": "pass" if live_sprint and live_roll else "fail",
		"live_sprint": live_sprint,
		"live_roll": live_roll,
		"pose": p1.current_pose(),
		"source": "parse_input_event + step_from_live_input",
	}
	_remember_session(session)
	return errors


static func _double_tap_sprint(session: GameSession) -> void:
	_tap_right(session, 2)
	_apply_p1(session, PackedStringArray(), 2, 0.0)
	_apply_p1(session, PackedStringArray(["right"]), 8, 1.0)


static func _tap_right(session: GameSession, hold: int) -> void:
	_apply_p1(session, PackedStringArray(["right"]), hold, 1.0)
	_apply_p1(session, PackedStringArray(), 1, 0.0)


static func _apply_p1_roll(session: GameSession, ticks: int) -> void:
	var n: int = 0
	while n < ticks:
		var frames: Array = []
		var i: int = 0
		while i < session.fighters.size():
			var raw: Dictionary = InputActions.empty_frame(session.clock.tick, i)
			if i == 0:
				raw["held"] = ["right"]
				raw["pressed"] = ["roll"] if n == 0 else []
				raw["move_x"] = 1.0
			frames.append(InputFrame.from_dict(raw))
			i += 1
		_record_apply(session.apply_frames(frames))
		n += 1


static func _try_roll_bundle(session: GameSession) -> bool:
	var frames: Array = []
	var i: int = 0
	while i < session.fighters.size():
		var raw: Dictionary = InputActions.empty_frame(session.clock.tick, i)
		if i == 0:
			raw["pressed"] = ["roll"]
			raw["held"] = ["right"]
			raw["move_x"] = 1.0
		frames.append(InputFrame.from_dict(raw))
		i += 1
	return _record_apply(session.apply_frames(frames))


static func _apply_p1(session: GameSession, held: PackedStringArray, ticks: int, move_x: float) -> void:
	var n: int = 0
	while n < ticks:
		var frames: Array = []
		var i: int = 0
		while i < session.fighters.size():
			var raw: Dictionary = InputActions.empty_frame(session.clock.tick, i)
			if i == 0:
				raw["held"] = Array(held)
				raw["move_x"] = move_x
				if n == 0 and not held.is_empty():
					raw["pressed"] = Array(held)
			frames.append(InputFrame.from_dict(raw))
			i += 1
		_record_apply(session.apply_frames(frames))
		n += 1


static func _spawn_bullet(session: GameSession, target: Fighter, damage: float) -> void:
	var shot: Bullet = Bullet.new()
	shot.setup(target.global_position, Vector2.RIGHT, 8.0, damage, 1, 1)
	session.add_child(shot)
	session.bullets.append(shot)


static func _capture_start(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "police", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	if session == null:
		errors.append("start snapshot missing session")
		return errors
	snapshot_start = session.snapshot()
	if session.ledger != null:
		events_end = session.ledger.to_array()
	return errors


static func _require_outcomes() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	if str(outcome_tap.get("verdict", "")) != "pass":
		errors.append("TAP outcome is %s" % str(outcome_tap.get("verdict", "unproven")))
	if str(outcome_stamina.get("verdict", "")) != "pass":
		errors.append("STAMINA outcome is %s" % str(outcome_stamina.get("verdict", "unproven")))
	if str(outcome_roll.get("verdict", "")) != "pass":
		errors.append("ROLL outcome is %s" % str(outcome_roll.get("verdict", "unproven")))
	if str(outcome_invuln.get("verdict", "")) != "pass":
		errors.append("INVULN outcome is %s" % str(outcome_invuln.get("verdict", "unproven")))
	if str(outcome_dup.get("verdict", "")) != "pass":
		errors.append("DUP outcome is %s" % str(outcome_dup.get("verdict", "unproven")))
	if str(outcome_live.get("verdict", "")) != "pass":
		errors.append("LIVE outcome is %s" % str(outcome_live.get("verdict", "unproven")))
	if str(outcome_replay.get("verdict", "")) != "match":
		errors.append("REPLAY outcome is %s" % str(outcome_replay.get("verdict", "unproven")))
	if used_apply_frames_succeeded <= 0 or used_apply_frames != used_apply_frames_succeeded:
		errors.append("USED_APPLY_FRAMES must count successful applies got=%d attempted=%d" % [
			used_apply_frames_succeeded, used_apply_frames_attempted
		])
	if used_apply_frames_attempted < used_apply_frames_succeeded:
		errors.append("apply attempted < succeeded")
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

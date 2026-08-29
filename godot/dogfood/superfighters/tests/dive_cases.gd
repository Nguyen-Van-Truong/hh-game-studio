class_name DiveCases
extends RefCounted

## VF2-WP4 official dive / jump-kick / fall cases.
## Proof is InputFrame apply_frames plus live InputEvent inject.
## 60 Hz is ledger:RL-SIM-FIXED-60 (assumption).
## Dive stays ledger:RL-MOVE-DIVE (assumption).
## Kick stays ledger:RL-MOVE-JUMP-KICK (assumption).
## Fall stays ledger:RL-MOVE-FALL (assumption).
## Sprint/roll stay assumption. Hold-to-aim stays assumption.
## Y8 observation stays ledger:RL-MOVE-ROLL-DIVE (unavailable).
## USED_APPLY_FRAMES counts successful apply_frames only.

static var used_step_fixed: int = 0
static var used_apply_frames: int = 0
static var used_apply_frames_attempted: int = 0
static var used_apply_frames_succeeded: int = 0
static var used_parse_input_event: int = 0
static var used_action_press: int = 0
static var outcome_dive: Dictionary = {}
static var outcome_kick: Dictionary = {}
static var outcome_tackle: Dictionary = {}
static var outcome_fall: Dictionary = {}
static var outcome_pit: Dictionary = {}
static var outcome_dodge: Dictionary = {}
static var outcome_invuln: Dictionary = {}
static var outcome_dist: Dictionary = {}
static var outcome_maps: Dictionary = {}
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
	outcome_dive = {"verdict": "unproven"}
	outcome_kick = {"verdict": "unproven"}
	outcome_tackle = {"verdict": "unproven"}
	outcome_fall = {"verdict": "unproven"}
	outcome_pit = {"verdict": "unproven"}
	outcome_dodge = {"verdict": "unproven"}
	outcome_invuln = {"verdict": "unproven"}
	outcome_dist = {"verdict": "unproven"}
	outcome_maps = {"verdict": "unproven"}
	outcome_live = {"verdict": "unproven"}
	outcome_replay = {"verdict": "unproven", "pairs": []}
	snapshot_start = {}
	snapshot_end = {}
	events_end = []
	var errors: PackedStringArray = PackedStringArray()
	_append(errors, schema_and_data())
	_append(errors, await _capture_start(app))
	_append(errors, await replay_traces_twice(app))
	_append(errors, await dive_contract(app))
	_append(errors, await kick_contract(app))
	_append(errors, await tackle_knockdown(app))
	_append(errors, await fall_behavior(app))
	_append(errors, await dive_pit_still_kills(app))
	_append(errors, await dive_invuln_projectile(app))
	_append(errors, await no_infinite_invuln(app))
	_append(errors, await distinguishable(app))
	_append(errors, await map_archetypes(app))
	_append(errors, await live_dive_and_kick(app))
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
		errors.append("dive/kick must not claim Y8 parity")
	if str(loco.get("dive_class", "")) != "assumption":
		errors.append("dive must stay assumption")
	if str(loco.get("kick_class", "")) != "assumption":
		errors.append("kick must stay assumption")
	if str(loco.get("fall_class", "")) != "assumption":
		errors.append("fall must stay assumption")
	if str(loco.get("sprint_class", "")) != "assumption":
		errors.append("sprint must stay assumption")
	if str(loco.get("roll_class", "")) != "assumption":
		errors.append("roll must stay assumption")
	if str(loco.get("hold_to_aim_class", "")) != "assumption":
		errors.append("hold-to-aim must stay assumption")
	if str(loco.get("roll_dive_class", "")) != "unavailable":
		errors.append("Y8 roll/dive observation must stay unavailable")
	if str(loco.get("dive_ledger", "")) != "RL-MOVE-DIVE":
		errors.append("dive must cite RL-MOVE-DIVE")
	if str(loco.get("kick_ledger", "")) != "RL-MOVE-JUMP-KICK":
		errors.append("kick must cite RL-MOVE-JUMP-KICK")
	var reserved: Array = loco.get("reserved_not_shipped", []) as Array
	if reserved.has("dive") or reserved.has("kick"):
		errors.append("dive/kick must not stay reserved")
	if reserved.has("ledge"):
		errors.append("ledge mechanic must be shipped")
	if not SimValidator.ALLOWED.has("dive"):
		errors.append("InputFrame must allow dive")
	if not SimValidator.ALLOWED.has("kick"):
		errors.append("InputFrame must allow kick")
	return errors


static func replay_traces_twice(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var paths: PackedStringArray = SimTrace.list_dir(SimConstants.DIVE_TRACE_DIR)
	if paths.size() < 6:
		errors.append("expected >=6 dive traces, got %d" % paths.size())
	var required: PackedStringArray = PackedStringArray([
		"dive_sprint_crouch", "jump_kick", "dive_pit",
		"dive_rooftops", "dive_storage", "dive_hazardous"
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
		if "assumption" not in str(trace.get("dive", "")):
			errors.append("%s must keep dive assumption" % path.get_file())
		if "assumption" not in str(trace.get("kick", "")):
			errors.append("%s must keep kick assumption" % path.get_file())
		names.append(str(trace.get("name", path.get_file())))
		var a: Dictionary = await SimReplay.play_path(app, path)
		var b: Dictionary = await SimReplay.play_path(app, path)
		_record_apply_batch(int(a.get("ticks", 0)), bool(a.get("ok", false)))
		_record_apply_batch(int(b.get("ticks", 0)), bool(b.get("ok", false)))
		if not bool(a.get("ok", false)):
			errors.append("dive %s run1 failed: %s" % [path.get_file(), _join(a)])
		if not bool(b.get("ok", false)):
			errors.append("dive %s run2 failed: %s" % [path.get_file(), _join(b)])
		if not bool(a.get("used_apply_frames", false)) or bool(a.get("used_cmd_dicts", true)):
			errors.append("dive %s MATCH used cmd dicts" % path.get_file())
		var hash_a: String = str(a.get("final_hash", ""))
		var hash_b: String = str(b.get("final_hash", ""))
		var match_ok: bool = hash_a != "" and hash_a == hash_b
		if not match_ok:
			errors.append("dive %s replay hashes differ" % path.get_file())
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
			errors.append("missing dive trace %s" % String(required[i]))
		i += 1
	var all_match: bool = pairs.size() >= 6
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


static func dive_contract(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "police", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	_apply_p1(session, PackedStringArray(), 12, 0.0)
	_double_tap_sprint(session)
	_apply_p1(session, PackedStringArray(["right", "jump"]), 6, 1.0)
	var stand_h: float = p1.stand_shape.size.y
	_apply_p1_action(session, "dive", PackedStringArray(["right"]), 1, 1.0)
	var started: bool = p1.diving
	var pose_ok: bool = p1.current_pose() == "dive"
	var shape_ok: bool = p1.col_shape != null and p1.col_shape.shape == p1.dive_shape
	var distinct_ok: bool = p1.dive_shape.size != p1.roll_shape.size
	var shrink_ok: bool = p1.dive_shape.size.y < stand_h - 0.5
	var invuln_ok: bool = p1.invuln > 0.0
	var sfx_ok: bool = session.sfx != null and session.sfx.last_id == "dive"
	var start_events: int = session.ledger.count_kind("dive_start")
	var hud_line: Label = session.hud.get_node_or_null("Bar_0") as Label
	var hud_ok: bool = hud_line != null and hud_line.text.contains("DIVE")
	var not_roll: bool = not p1.rolling and p1.current_pose() != "roll"
	if not started:
		errors.append("explicit dive did not start")
	if not pose_ok:
		errors.append("dive pose missing got=%s" % p1.current_pose())
	if not shape_ok:
		errors.append("dive did not swap collision footprint")
	if not distinct_ok:
		errors.append("dive AABB must differ from roll")
	if not invuln_ok:
		errors.append("dive must set invuln window")
	if not sfx_ok:
		errors.append("dive SFX last_id must be dive")
	if start_events != 1:
		errors.append("expected one dive_start got=%d" % start_events)
	if not hud_ok:
		errors.append("HUD must show DIVE feedback")
	if not not_roll:
		errors.append("dive must not look like a roll")
	var seq0: int = p1.dive_seq
	var n: int = 0
	while n < 6:
		_apply_p1_action(session, "dive", PackedStringArray(["right"]), 1, 1.0)
		n += 1
	var dup_ok: bool = p1.dive_seq == seq0
	if not dup_ok:
		errors.append("repeated dive duplicated seq")
	var pass_ok: bool = (
		started and pose_ok and shape_ok and distinct_ok and shrink_ok
		and invuln_ok and sfx_ok and start_events == 1 and hud_ok
		and not_roll and dup_ok
	)
	outcome_dive = {
		"verdict": "pass" if pass_ok else "fail",
		"started": started,
		"pose": p1.current_pose(),
		"footprint_swapped": shape_ok,
		"aabb_distinct_from_roll": distinct_ok,
		"invuln": p1.invuln,
		"sfx_last_id": session.sfx.last_id if session.sfx != null else "",
		"hud_dive": hud_ok,
		"dive_start_events": start_events,
		"seq": p1.dive_seq,
		"source": "apply_frames sprint+jump+dive pose/AABB/SFX/HUD",
	}
	_remember_session(session)
	return errors


static func kick_contract(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "police", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	_apply_p1(session, PackedStringArray(), 12, 0.0)
	_apply_p1(session, PackedStringArray(["jump"]), 5, 0.0)
	_apply_p1_action(session, "kick", PackedStringArray(), 1, 0.0)
	var started: bool = p1.kicking or p1.kick_seq == 1
	var pose_ok: bool = p1.current_pose() == "kick"
	var not_melee: bool = p1.current_pose() != "melee"
	var not_dive: bool = not p1.diving and p1.current_pose() != "dive"
	var impulse_ok: bool = p1.velocity.y >= p1.kick_impulse_y - 1.0
	var sfx_ok: bool = session.sfx != null and session.sfx.last_id == "kick"
	var start_events: int = session.ledger.count_kind("kick_start")
	var hud_line: Label = session.hud.get_node_or_null("Bar_0") as Label
	var hud_ok: bool = hud_line != null and hud_line.text.contains("KICK")
	if not started:
		errors.append("aerial kick did not start")
	if not pose_ok:
		errors.append("kick pose missing got=%s" % p1.current_pose())
	if not not_melee:
		errors.append("kick pose must not be grounded melee")
	if not impulse_ok:
		errors.append("kick impulse missing vy=%s" % str(p1.velocity.y))
	if not sfx_ok:
		errors.append("kick SFX last_id must be kick")
	if start_events < 1:
		errors.append("missing kick_start event")
	if not hud_ok:
		errors.append("HUD must show KICK feedback")
	app.start_fight("vs2", "police", 0)
	await SimReplay.sync_physics(app)
	session = app.session
	p1 = session.player1()
	_apply_p1(session, PackedStringArray(), 12, 0.0)
	_apply_p1_action(session, "kick", PackedStringArray(), 1, 0.0)
	var ground_block: bool = not p1.kicking and p1.last_kick_block == "ground"
	if p1.kicking:
		errors.append("grounded kick must be blocked")
	var pass_ok: bool = (
		started and pose_ok and not_melee and not_dive and impulse_ok
		and sfx_ok and start_events >= 1 and hud_ok and ground_block
	)
	outcome_kick = {
		"verdict": "pass" if pass_ok else "fail",
		"started": started,
		"pose": pose_ok,
		"not_melee": not_melee,
		"impulse": impulse_ok,
		"ground_blocked": ground_block,
		"kick_start_events": start_events,
		"source": "apply_frames aerial kick vs grounded block",
	}
	_remember_session(session)
	return errors


static func tackle_knockdown(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "police", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	var p2: Fighter = session.fighter_at_slot(1)
	if p2 == null:
		errors.append("vs2 missing P2 for tackle")
		outcome_tackle = {"verdict": "fail", "reason": "missing P2"}
		return errors
	_apply_p1(session, PackedStringArray(), 8, 0.0)
	_apply_p1(session, PackedStringArray(["jump"]), 3, 0.0)
	p2.global_position = p1.global_position + Vector2(16.0, 2.0)
	p2.velocity = Vector2.ZERO
	_apply_p1_action(session, "dive", PackedStringArray(["right"]), 3, 1.0)
	var tackle_events: int = session.ledger.count_kind("dive_tackle")
	var down_events: int = session.ledger.count_kind("knockdown")
	var p2_down: bool = p2.knockdown_left > 0.0
	if tackle_events < 1:
		errors.append("missing dive_tackle hook event")
	if down_events < 1:
		errors.append("missing knockdown hook event")
	if not p2_down:
		errors.append("P2 was not knocked down by dive")
	app.start_fight("vs2", "police", 0)
	await SimReplay.sync_physics(app)
	session = app.session
	p1 = session.player1()
	p2 = session.fighter_at_slot(1)
	_apply_p1(session, PackedStringArray(), 8, 0.0)
	_apply_p1(session, PackedStringArray(["jump"]), 4, 0.0)
	p2.global_position = p1.global_position + Vector2(14.0, 0.0)
	p2.velocity = Vector2.ZERO
	_apply_p1_action(session, "kick", PackedStringArray(["right"]), 1, 1.0)
	_apply_p1(session, PackedStringArray(["right"]), 4, 1.0)
	var kick_hits: int = session.ledger.count_kind("kick_hit")
	if kick_hits < 1:
		errors.append("missing kick_hit event")
	var pass_ok: bool = tackle_events >= 1 and down_events >= 1 and p2_down and kick_hits >= 1
	outcome_tackle = {
		"verdict": "pass" if pass_ok else "fail",
		"dive_tackle_events": tackle_events,
		"knockdown_events": down_events,
		"p2_knocked_down": p2_down,
		"kick_hit_events": kick_hits,
		"source": "apply_frames dive tackle + aerial kick hit",
	}
	_remember_session(session)
	return errors


static func fall_behavior(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "storage", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	_apply_p1(session, PackedStringArray(), 12, 0.0)
	_stand_on_storage_crate(p1)
	_apply_p1(session, PackedStringArray(), 10, 0.0)
	_apply_p1(session, PackedStringArray(["right"]), 28, 1.0)
	_apply_p1(session, PackedStringArray(), 24, 0.0)
	var damaged: bool = p1.fall_damage_applied or session.ledger.count_kind("fall_damage") >= 1
	var hp_hurt: bool = p1.health < Fighter.MAX_HP - 0.5
	var not_pit: bool = not p1.dead
	if not damaged and not hp_hurt:
		errors.append("high drop without dive did not apply fall damage hp=%s" % str(p1.health))
	app.start_fight("vs2", "storage", 0)
	await SimReplay.sync_physics(app)
	session = app.session
	p1 = session.player1()
	_apply_p1(session, PackedStringArray(), 12, 0.0)
	_stand_on_storage_crate(p1)
	_apply_p1(session, PackedStringArray(), 8, 0.0)
	_apply_p1(session, PackedStringArray(["right"]), 10, 1.0)
	_apply_p1(session, PackedStringArray(["right", "jump"]), 4, 1.0)
	_apply_p1_action(session, "dive", PackedStringArray(["right"]), 1, 1.0)
	_apply_p1(session, PackedStringArray(["right"]), 20, 1.0)
	var immune: bool = session.ledger.count_kind("fall_immune") >= 1 or p1.fall_immune_landed
	var no_fall_evt: bool = session.ledger.count_kind("fall_damage") == 0
	var alive: bool = not p1.dead
	if not immune:
		errors.append("dive landing missing fall-immune proof")
	if not no_fall_evt:
		errors.append("dive landing must not emit fall_damage")
	var pass_ok: bool = (damaged or hp_hurt) and not_pit and immune and no_fall_evt and alive
	outcome_fall = {
		"verdict": "pass" if pass_ok else "fail",
		"fall_damage_without_dive": damaged or hp_hurt,
		"dive_fall_immune": immune,
		"dive_no_fall_event": no_fall_evt,
		"source": "apply_frames storage crate drop vs dive landing",
	}
	_remember_session(session)
	return errors


static func dive_pit_still_kills(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var played: Dictionary = await SimReplay.play_path(
		app, "%s/dive_pit.json" % SimConstants.DIVE_TRACE_DIR
	)
	_record_apply_batch(int(played.get("ticks", 0)), bool(played.get("ok", false)))
	app.start_fight("vs2", "police", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	_apply_p1(session, PackedStringArray(), 10, 0.0)
	_apply_p1(session, PackedStringArray(["jump"]), 4, 0.0)
	_apply_p1_action(session, "dive", PackedStringArray(["left"]), 1, -1.0)
	_apply_p1(session, PackedStringArray(["left"]), 40, -1.0)
	var dead_ok: bool = p1.dead
	var pit_ok: bool = p1.death_cause == "pit"
	if not dead_ok:
		errors.append("dive into pit must still kill")
	if not pit_ok:
		errors.append("dive pit death_cause must be pit got=%s" % p1.death_cause)
	var pass_ok: bool = dead_ok and pit_ok
	outcome_pit = {
		"verdict": "pass" if pass_ok else "fail",
		"dead": dead_ok,
		"death_cause": p1.death_cause,
		"source": "apply_frames dive into police pit",
	}
	_remember_session(session)
	return errors


static func dive_invuln_projectile(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "police", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	_apply_p1(session, PackedStringArray(), 10, 0.0)
	_apply_p1(session, PackedStringArray(["jump"]), 5, 0.0)
	_apply_p1_action(session, "dive", PackedStringArray(["right"]), 1, 1.0)
	if not p1.diving or p1.invuln <= 0.0:
		errors.append("dodge case never entered dive")
		outcome_dodge = {"verdict": "fail", "reason": "never entered dive"}
		return errors
	p1.health = 80.0
	p1.combat_timer = 3.0
	_spawn_bullet(session, p1, 25.0)
	_apply_p1(session, PackedStringArray(["right"]), 1, 1.0)
	var inside_ok: bool = p1.health >= 80.0 - 0.01
	if not inside_ok:
		errors.append("projectile damaged through dive invuln hp=%s" % str(p1.health))
	var pass_ok: bool = inside_ok
	outcome_dodge = {
		"verdict": "pass" if pass_ok else "fail",
		"inside_invuln_undamaged": inside_ok,
		"source": "Bullet vs dive invuln window",
	}
	_remember_session(session)
	return errors


static func no_infinite_invuln(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "police", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	_apply_p1(session, PackedStringArray(), 10, 0.0)
	_apply_p1(session, PackedStringArray(["jump"]), 5, 0.0)
	_apply_p1_action(session, "dive", PackedStringArray(["right"]), 1, 1.0)
	var wait: int = int(ceil(p1.dive_invuln / SimConstants.TICK_DT)) + 4
	_apply_p1(session, PackedStringArray(), wait, 0.0)
	var expired: bool = p1.invuln <= 0.0
	if not expired:
		errors.append("dive invuln still active after window invuln=%s" % str(p1.invuln))
	var hp0: float = p1.health
	p1.combat_timer = 3.0
	_spawn_bullet(session, p1, 25.0)
	_apply_p1(session, PackedStringArray(), 1, 0.0)
	var outside_ok: bool = p1.health < hp0 - 0.01
	if not outside_ok:
		errors.append("projectile after dive invuln did not damage")
	var pass_ok: bool = expired and outside_ok
	outcome_invuln = {
		"verdict": "pass" if pass_ok else "fail",
		"window_expired": expired,
		"outside_invuln_damaged": outside_ok,
		"source": "dive invuln expires; not infinite",
	}
	_remember_session(session)
	return errors


static func distinguishable(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "police", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	_apply_p1(session, PackedStringArray(), 12, 0.0)
	_double_tap_sprint(session)
	_apply_p1_action(session, "roll", PackedStringArray(["right"]), 1, 1.0)
	var roll_pose: String = p1.current_pose()
	var roll_flag: bool = p1.rolling and not p1.diving and not p1.kicking
	var roll_snap: Dictionary = session.snapshot()
	var roll_row: Dictionary = (roll_snap.get("fighters", []) as Array)[0] as Dictionary
	_apply_p1(session, PackedStringArray(), 20, 0.0)
	_double_tap_sprint(session)
	_apply_p1(session, PackedStringArray(["right", "jump"]), 6, 1.0)
	_apply_p1_action(session, "dive", PackedStringArray(["right"]), 1, 1.0)
	var dive_pose: String = p1.current_pose()
	var dive_flag: bool = p1.diving and not p1.rolling and not p1.kicking
	var dive_snap: Dictionary = session.snapshot()
	var dive_row: Dictionary = (dive_snap.get("fighters", []) as Array)[0] as Dictionary
	app.start_fight("vs2", "police", 0)
	await SimReplay.sync_physics(app)
	session = app.session
	p1 = session.player1()
	_apply_p1(session, PackedStringArray(), 12, 0.0)
	_apply_p1(session, PackedStringArray(["jump"]), 5, 0.0)
	_apply_p1_action(session, "kick", PackedStringArray(), 1, 0.0)
	var kick_pose: String = p1.current_pose()
	var kick_flag: bool = p1.kicking and not p1.rolling and not p1.diving
	var kick_snap: Dictionary = session.snapshot()
	var kick_row: Dictionary = (kick_snap.get("fighters", []) as Array)[0] as Dictionary
	var poses_ok: bool = roll_pose == "roll" and dive_pose == "dive" and kick_pose == "kick"
	var flags_ok: bool = roll_flag and dive_flag and kick_flag
	var snap_ok: bool = (
		int(roll_row.get("rolling", 0)) == 1
		and int(dive_row.get("diving", 0)) == 1
		and int(kick_row.get("kicking", 0)) == 1
		and str(roll_row.get("pose", "")) == "roll"
		and str(dive_row.get("pose", "")) == "dive"
		and str(kick_row.get("pose", "")) == "kick"
	)
	var events_ok: bool = (
		session.ledger.count_kind("kick_start") >= 1
	)
	if not poses_ok:
		errors.append("poses not distinct roll=%s dive=%s kick=%s" % [roll_pose, dive_pose, kick_pose])
	if not flags_ok:
		errors.append("state flags not exclusive")
	if not snap_ok:
		errors.append("snapshot must distinguish roll/dive/kick")
	var pass_ok: bool = poses_ok and flags_ok and snap_ok and events_ok
	outcome_dist = {
		"verdict": "pass" if pass_ok else "fail",
		"roll_pose": roll_pose,
		"dive_pose": dive_pose,
		"kick_pose": kick_pose,
		"snapshot_distinct": snap_ok,
		"source": "snapshot + pose + events for roll/dive/kick",
	}
	_remember_session(session)
	return errors


static func map_archetypes(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var maps: PackedStringArray = Maps.stage_ids()
	var rows: Array = []
	var all_ok: bool = maps.size() == 4
	var i: int = 0
	while i < maps.size():
		var map_id: String = String(maps[i])
		var path: String = "%s/dive_%s.json" % [SimConstants.DIVE_TRACE_DIR, map_id]
		if map_id == "police":
			path = "%s/dive_sprint_crouch.json" % SimConstants.DIVE_TRACE_DIR
		var played: Dictionary = await SimReplay.play_path(app, path)
		_record_apply_batch(int(played.get("ticks", 0)), bool(played.get("ok", false)))
		app.start_fight("vs2", map_id, 0)
		await SimReplay.sync_physics(app)
		var session: GameSession = app.session
		var p1: Fighter = session.player1()
		_apply_p1(session, PackedStringArray(), 10, 0.0)
		_double_tap_sprint(session)
		_apply_p1(session, PackedStringArray(["right", "jump"]), 6, 1.0)
		_apply_p1_action(session, "dive", PackedStringArray(["right"]), 1, 1.0)
		var dove: bool = p1.diving or p1.dive_seq >= 1
		var map_ok: bool = dove and bool(played.get("ok", false))
		if not dove:
			errors.append("dive failed on map %s" % map_id)
		if not bool(played.get("ok", false)):
			errors.append("dive trace failed on map %s" % map_id)
		rows.append({"map_id": map_id, "dived": dove, "trace_ok": bool(played.get("ok", false))})
		if not map_ok:
			all_ok = false
		_remember_session(session)
		i += 1
	outcome_maps = {
		"verdict": "pass" if all_ok else "fail",
		"maps": rows,
		"source": "real InputFrame dive on each archetype",
	}
	return errors


static func live_dive_and_kick(app: App) -> PackedStringArray:
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
	while n < 6:
		session.step_from_live_input()
		n += 1
	InputInjector.inject_key(KEY_UP, true, viewport)
	n = 0
	while n < 5:
		session.step_from_live_input()
		n += 1
	InputInjector.inject_key(KEY_UP, false, viewport)
	InputInjector.inject_key(KEY_DOWN, true, viewport)
	n = 0
	while n < 3:
		session.step_from_live_input()
		n += 1
	var live_dive: bool = p1.diving or p1.dive_seq >= 1
	if not live_dive:
		errors.append("live sprint+jump+crouch did not dive pose=%s" % p1.current_pose())
	InputInjector.release_known(viewport)
	InputActions.reset_edges()
	app.start_fight("vs2", "police", 0)
	session = app.session
	p1 = session.player1()
	viewport = app.get_viewport()
	await SimReplay.sync_physics(app)
	_apply_p1(session, PackedStringArray(), 8, 0.0)
	InputInjector.inject_key(KEY_UP, true, viewport)
	n = 0
	while n < 5:
		session.step_from_live_input()
		n += 1
	InputInjector.inject_key(KEY_N, true, viewport)
	n = 0
	while n < 2:
		session.step_from_live_input()
		n += 1
	var live_kick: bool = p1.kicking or p1.kick_seq >= 1 or p1.current_pose() == "kick"
	if not live_kick:
		errors.append("live aerial melee did not kick pose=%s" % p1.current_pose())
	InputInjector.release_known(viewport)
	outcome_live = {
		"verdict": "pass" if live_dive and live_kick else "fail",
		"live_dive": live_dive,
		"live_kick": live_kick,
		"pose": p1.current_pose(),
		"source": "parse_input_event + step_from_live_input",
	}
	_remember_session(session)
	return errors


static func _stand_on_storage_crate(p1: Fighter) -> void:
	# Setup only (V-A16). Landing and fall/dive proof still use apply_frames.
	p1.global_position = Vector2(152.0, 118.0)
	p1.velocity = Vector2.ZERO


static func _double_tap_sprint(session: GameSession) -> void:
	_apply_p1(session, PackedStringArray(["right"]), 2, 1.0)
	_apply_p1(session, PackedStringArray(), 1, 0.0)
	_apply_p1(session, PackedStringArray(["right"]), 8, 1.0)


static func _apply_p1_action(
	session: GameSession, action: String, held: PackedStringArray, ticks: int, move_x: float
) -> void:
	var n: int = 0
	while n < ticks:
		var frames: Array = []
		var i: int = 0
		while i < session.fighters.size():
			var raw: Dictionary = InputActions.empty_frame(session.clock.tick, i)
			if i == 0:
				raw["held"] = Array(held)
				raw["pressed"] = [action] if n == 0 else []
				raw["move_x"] = move_x
			frames.append(InputFrame.from_dict(raw))
			i += 1
		_record_apply(session.apply_frames(frames))
		n += 1


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
	if str(outcome_dive.get("verdict", "")) != "pass":
		errors.append("DIVE outcome is %s" % str(outcome_dive.get("verdict", "unproven")))
	if str(outcome_kick.get("verdict", "")) != "pass":
		errors.append("KICK outcome is %s" % str(outcome_kick.get("verdict", "unproven")))
	if str(outcome_tackle.get("verdict", "")) != "pass":
		errors.append("TACKLE outcome is %s" % str(outcome_tackle.get("verdict", "unproven")))
	if str(outcome_fall.get("verdict", "")) != "pass":
		errors.append("FALL outcome is %s" % str(outcome_fall.get("verdict", "unproven")))
	if str(outcome_pit.get("verdict", "")) != "pass":
		errors.append("PIT outcome is %s" % str(outcome_pit.get("verdict", "unproven")))
	if str(outcome_dodge.get("verdict", "")) != "pass":
		errors.append("DODGE outcome is %s" % str(outcome_dodge.get("verdict", "unproven")))
	if str(outcome_invuln.get("verdict", "")) != "pass":
		errors.append("INVULN outcome is %s" % str(outcome_invuln.get("verdict", "unproven")))
	if str(outcome_dist.get("verdict", "")) != "pass":
		errors.append("DIST outcome is %s" % str(outcome_dist.get("verdict", "unproven")))
	if str(outcome_maps.get("verdict", "")) != "pass":
		errors.append("MAPS outcome is %s" % str(outcome_maps.get("verdict", "unproven")))
	if str(outcome_live.get("verdict", "")) != "pass":
		errors.append("LIVE outcome is %s" % str(outcome_live.get("verdict", "unproven")))
	if str(outcome_replay.get("verdict", "")) != "match":
		errors.append("REPLAY outcome is %s" % str(outcome_replay.get("verdict", "unproven")))
	if used_apply_frames_succeeded <= 0 or used_apply_frames != used_apply_frames_succeeded:
		errors.append("USED_APPLY_FRAMES must count successful applies got=%d attempted=%d" % [
			used_apply_frames_succeeded, used_apply_frames_attempted
		])
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

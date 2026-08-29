class_name ReactionCases
extends RefCounted

const _Combat: GDScript = preload("res://src/sim/combat.gd")

## VF3-WP2 official knockback / knockdown / invuln / disarm cases.
## Proof is InputFrame apply_frames plus live InputEvent inject.
## 60 Hz is ledger:RL-SIM-FIXED-60 (assumption).
## Knockback stays ledger:RL-HIT-KNOCK (assumption).
## Knockdown/getup stay ledger:RL-HIT-DOWN (assumption).
## Hit invuln stays ledger:RL-HIT-INVULN (assumption).
## Punch disarm stays ledger:RL-HIT-DISARM (assumption).
## Hold-to-aim stays assumption. Y8 roll/dive stays unavailable.
## USED_APPLY_FRAMES counts successful apply_frames only.

static var used_step_fixed: int = 0
static var used_apply_frames: int = 0
static var used_apply_frames_attempted: int = 0
static var used_apply_frames_succeeded: int = 0
static var used_parse_input_event: int = 0
static var used_action_press: int = 0
static var outcome_damage: Dictionary = {}
static var outcome_knock: Dictionary = {}
static var outcome_air: Dictionary = {}
static var outcome_down: Dictionary = {}
static var outcome_getup: Dictionary = {}
static var outcome_invuln: Dictionary = {}
static var outcome_chain: Dictionary = {}
static var outcome_disarm: Dictionary = {}
static var outcome_drop: Dictionary = {}
static var outcome_death: Dictionary = {}
static var outcome_events: Dictionary = {}
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
	outcome_damage = {"verdict": "unproven"}
	outcome_knock = {"verdict": "unproven"}
	outcome_air = {"verdict": "unproven"}
	outcome_down = {"verdict": "unproven"}
	outcome_getup = {"verdict": "unproven"}
	outcome_invuln = {"verdict": "unproven"}
	outcome_chain = {"verdict": "unproven"}
	outcome_disarm = {"verdict": "unproven"}
	outcome_drop = {"verdict": "unproven"}
	outcome_death = {"verdict": "unproven"}
	outcome_events = {"verdict": "unproven"}
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
	_append(errors, await damage_and_knock(app))
	_append(errors, await knockdown_getup(app))
	_append(errors, await invuln_exact_ticks(app))
	_append(errors, await chain_lock(app))
	_append(errors, await punch_disarm(app))
	_append(errors, await dropped_item_lifecycle(app))
	_append(errors, await death_cause_valid(app))
	_append(errors, await entry_exit_events(app))
	_append(errors, await live_reaction(app))
	_append(errors, _require_outcomes())
	return errors


static func schema_and_data() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var row: Dictionary = _Combat.data()
	if str(row.get("schema", "")) != _Combat.SCHEMA_ID:
		errors.append("combat schema id mismatch")
	if str(row.get("title", "")) != "Vault Fighters":
		errors.append("combat title must be Vault Fighters")
	if bool(row.get("y8_parity_claimed", true)):
		errors.append("combat must not claim Y8 parity")
	if str(row.get("knock_class", "")) != "assumption":
		errors.append("knockback must stay assumption")
	if str(row.get("down_class", "")) != "assumption":
		errors.append("knockdown must stay assumption")
	if str(row.get("invuln_class", "")) != "assumption":
		errors.append("hit invuln must stay assumption")
	if str(row.get("disarm_class", "")) != "assumption":
		errors.append("disarm must stay assumption")
	if str(row.get("roll_dive_class", "")) != "unavailable":
		errors.append("Y8 roll/dive observation must stay unavailable")
	if _Combat.hit_invuln_ticks() < 1:
		errors.append("hit_invuln_ticks must be >= 1")
	if _Combat.knockdown_ticks() < 1:
		errors.append("knockdown_ticks must be >= 1")
	if _Combat.getup_ticks() < 1:
		errors.append("getup_ticks must be >= 1")
	if not _Combat.chain_lock_block():
		errors.append("chain_lock_block must be true")
	if not _Combat.style_disarms("melee"):
		errors.append("melee punch must disarm guns")
	if _Combat.style_disarms("kick"):
		errors.append("kick must not disarm")
	if not _Combat.valid_death_cause("damage") or not _Combat.valid_death_cause("pit"):
		errors.append("damage/pit must be valid death causes")
	if _Combat.valid_death_cause("script"):
		errors.append("script must not be a valid official death cause")
	return errors


static func replay_traces_twice(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var paths: PackedStringArray = SimTrace.list_dir(SimConstants.REACTION_TRACE_DIR)
	if paths.size() < 6:
		errors.append("expected >=6 reaction traces, got %d" % paths.size())
	var required: PackedStringArray = PackedStringArray([
		"reaction_knock", "reaction_down", "reaction_invuln",
		"reaction_disarm", "reaction_drop", "reaction_chain"
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
		if "assumption" not in str(trace.get("knock", "")):
			errors.append("%s must keep knock assumption" % path.get_file())
		names.append(str(trace.get("name", path.get_file())))
		await _drain_physics(app)
		var a: Dictionary = await SimReplay.play_path(app, path)
		await _drain_physics(app)
		var b: Dictionary = await SimReplay.play_path(app, path)
		_record_apply_batch(int(a.get("ticks", 0)), bool(a.get("ok", false)))
		_record_apply_batch(int(b.get("ticks", 0)), bool(b.get("ok", false)))
		if not bool(a.get("ok", false)):
			errors.append("reaction %s run1 failed: %s" % [path.get_file(), _join(a)])
		if not bool(b.get("ok", false)):
			errors.append("reaction %s run2 failed: %s" % [path.get_file(), _join(b)])
		if not bool(a.get("used_apply_frames", false)) or bool(a.get("used_cmd_dicts", true)):
			errors.append("reaction %s MATCH used cmd dicts" % path.get_file())
		var hash_a: String = str(a.get("final_hash", ""))
		var hash_b: String = str(b.get("final_hash", ""))
		var match_ok: bool = hash_a != "" and hash_a == hash_b
		if not match_ok:
			errors.append("reaction %s replay hashes differ" % path.get_file())
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
			errors.append("missing reaction trace %s" % String(required[i]))
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


static func damage_and_knock(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_melee_close", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p2: Fighter = session.fighter_at_slot(1)
	_apply_slot(session, 0, PackedStringArray(), 8, 0.0)
	var hp0: float = p2.health
	var vx0: float = p2.velocity.x
	var vy0: float = p2.velocity.y
	_apply_slot_action(session, 0, "melee", PackedStringArray(), 1, 0.0)
	_apply_slot(session, 0, PackedStringArray(), _Combat.startup_ticks("fists", "melee") + 1, 0.0)
	var hp1: float = p2.health
	var vx1: float = p2.velocity.x
	var vy1: float = p2.velocity.y
	var expected: float = _Combat.damage_of("fists", "melee")
	var dmg: float = hp0 - hp1
	var dmg_ok: bool = absf(dmg - expected) <= 0.01
	var knock_ok: bool = vx1 > vx0 + 8.0
	var air_ok: bool = p2.hit_airborne or vy1 < vy0 - 8.0 or session.ledger.count_kind("airborne_start") >= 1
	var kb_ev: int = session.ledger.count_kind("knockback_start")
	if not dmg_ok:
		errors.append("DAMAGE hp delta %s != %s" % [str(dmg), str(expected)])
	if not knock_ok:
		errors.append("KNOCK missing vx0=%s vx1=%s" % [str(vx0), str(vx1)])
	if not air_ok:
		errors.append("AIR punch must launch or emit airborne_start")
	if kb_ev < 1:
		errors.append("KNOCK missing knockback_start event")
	outcome_damage = {
		"verdict": "pass" if dmg_ok else "fail",
		"hp0": hp0,
		"hp1": hp1,
		"damage": dmg,
		"expected": expected,
		"source": "apply_frames punch HP delta equals fists damage",
	}
	outcome_knock = {
		"verdict": "pass" if knock_ok and kb_ev >= 1 else "fail",
		"vx0": vx0,
		"vx1": vx1,
		"knockback_start": kb_ev,
		"source": "apply_frames punch impulse + knockback_start",
	}
	outcome_air = {
		"verdict": "pass" if air_ok else "fail",
		"hit_airborne": p2.hit_airborne,
		"vy0": vy0,
		"vy1": vy1,
		"airborne_start": session.ledger.count_kind("airborne_start"),
		"source": "punch knock_y lifts or tags hit_airborne",
	}
	_remember_session(session)
	_append_events(session.ledger.to_array())
	return errors


static func knockdown_getup(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_melee_close", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	var p2: Fighter = session.fighter_at_slot(1)
	_apply_slot(session, 0, PackedStringArray(), 8, 0.0)
	_apply_slot(session, 0, PackedStringArray(["jump"]), 2, 0.0)
	_apply_slot_action(session, 0, "kick", PackedStringArray(), 1, 0.0)
	_apply_slot(session, 0, PackedStringArray(), _Combat.startup_ticks("kick", "kick") + 1, 0.0)
	var down_now: bool = p2.knockdown_left > 0.0
	var start_ev: int = session.ledger.count_kind("knockdown_start")
	if not down_now:
		errors.append("DOWN kick must enter knockdown")
	if start_ev < 1:
		errors.append("DOWN missing knockdown_start")
	var wait_down: int = _Combat.knockdown_ticks() + 2
	_apply_slot(session, 0, PackedStringArray(), wait_down, 0.0)
	var getup_now: bool = p2.getup_left > 0.0 or session.ledger.count_kind("getup_start") >= 1
	var end_down: int = session.ledger.count_kind("knockdown_end")
	if not getup_now:
		errors.append("GETUP never entered after knockdown ticks")
	if end_down < 1:
		errors.append("GETUP missing knockdown_end")
	var wait_up: int = _Combat.getup_ticks() + 2
	_apply_slot(session, 0, PackedStringArray(), wait_up, 0.0)
	var getup_done: bool = p2.getup_left <= 0.0 and not p2.reaction_locked()
	var end_up: int = session.ledger.count_kind("getup_end")
	if not getup_done:
		errors.append("GETUP did not exit getup_left=%s locked=%s" % [str(p2.getup_left), str(p2.reaction_locked())])
	if end_up < 1:
		errors.append("GETUP missing getup_end")
	outcome_down = {
		"verdict": "pass" if down_now and start_ev >= 1 else "fail",
		"knockdown_left": p2.knockdown_left,
		"knockdown_start": start_ev,
		"style": p1.attack_style,
		"source": "apply_frames jump+kick enters knockdown",
	}
	outcome_getup = {
		"verdict": "pass" if getup_now and getup_done and end_down >= 1 and end_up >= 1 else "fail",
		"getup_start": session.ledger.count_kind("getup_start"),
		"getup_end": end_up,
		"knockdown_end": end_down,
		"locked_after": p2.reaction_locked(),
		"source": "knockdown ticks then getup entry/exit",
	}
	_remember_session(session)
	_append_events(session.ledger.to_array())
	return errors


static func invuln_exact_ticks(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_melee_close", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p2: Fighter = session.fighter_at_slot(1)
	_apply_slot(session, 0, PackedStringArray(), 8, 0.0)
	var hp0: float = p2.health
	_apply_slot_action(session, 0, "melee", PackedStringArray(), 1, 0.0)
	var wait_hit: int = 0
	while wait_hit < 12 and p2.health >= hp0 - 0.01:
		_apply_idle(session, 1)
		wait_hit += 1
	var armed: int = p2.invuln_ticks
	var expected: int = _Combat.hit_invuln_ticks()
	var start_ok: bool = armed == expected
	if not start_ok:
		errors.append("INVULN armed ticks %d != %d" % [armed, expected])
	var inside_hp: float = p2.health
	_spawn_bullet(session, p2, 25.0)
	_apply_idle(session, 1)
	var blocked: bool = absf(p2.health - inside_hp) <= 0.01
	if not blocked:
		errors.append("INVULN must block projectile hp=%s" % str(p2.health))
	if p2.invuln_ticks > 0:
		_apply_idle(session, p2.invuln_ticks)
	var expired: bool = p2.invuln_ticks <= 0
	if not expired:
		errors.append("INVULN still active after exact ticks left=%d" % p2.invuln_ticks)
	var hp_pre: float = p2.health
	_spawn_bullet(session, p2, 25.0)
	_apply_idle(session, 1)
	var after_ok: bool = p2.health < hp_pre - 0.01
	if not after_ok:
		errors.append("INVULN after expire must allow projectile damage")
	var end_ev: int = session.ledger.count_kind("invuln_end")
	var start_ev: int = session.ledger.count_kind("invuln_start")
	var mid_ticks: int = armed - 1 if armed > 0 else 0
	outcome_invuln = {
		"verdict": "pass" if start_ok and blocked and expired and after_ok else "fail",
		"armed_ticks": armed,
		"expected_ticks": expected,
		"mid_ticks": mid_ticks,
		"blocked_inside": blocked,
		"expired": expired,
		"after_damaged": after_ok,
		"invuln_start": start_ev,
		"invuln_end": end_ev,
		"hp0": hp0,
		"source": "exact hit_invuln_ticks; damage blocked then allowed",
	}
	_remember_session(session)
	_append_events(session.ledger.to_array())
	return errors


static func chain_lock(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_melee_close", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p2: Fighter = session.fighter_at_slot(1)
	_apply_slot(session, 0, PackedStringArray(), 8, 0.0)
	_apply_slot(session, 0, PackedStringArray(["jump"]), 2, 0.0)
	_apply_slot_action(session, 0, "kick", PackedStringArray(), 1, 0.0)
	_apply_slot(session, 0, PackedStringArray(), _Combat.total_ticks("kick", "kick") + 2, 0.0)
	var hp_down: float = p2.health
	var down_left: float = p2.knockdown_left
	var locked: bool = p2.reaction_locked()
	if not locked:
		errors.append("CHAIN never entered knockdown")
	_apply_slot_action(session, 0, "melee", PackedStringArray(), 1, 0.0)
	_apply_slot(session, 0, PackedStringArray(), _Combat.total_ticks("fists", "melee") + 2, 0.0)
	var hp_same: bool = absf(p2.health - hp_down) <= 0.01
	var no_refresh: bool = p2.knockdown_left <= down_left + 0.0001
	if not hp_same:
		errors.append("CHAIN punch during knockdown changed HP")
	if not no_refresh:
		errors.append("CHAIN refreshed knockdown_left")
	var wait: int = _Combat.knockdown_invuln_ticks() + _Combat.getup_ticks() + 4
	_apply_slot(session, 0, PackedStringArray(), wait, 0.0)
	var free: bool = not p2.reaction_locked() and p2.invuln_ticks <= 0
	var hp_pre: float = p2.health
	_apply_slot_action(session, 0, "melee", PackedStringArray(), 1, 0.0)
	_apply_slot(session, 0, PackedStringArray(), _Combat.startup_ticks("fists", "melee") + 1, 0.0)
	var after: bool = p2.health < hp_pre - 0.01
	if not after:
		errors.append("CHAIN after getup must accept a new hit")
	outcome_chain = {
		"verdict": "pass" if locked and hp_same and no_refresh and free and after else "fail",
		"locked": locked,
		"hp_same": hp_same,
		"no_refresh": no_refresh,
		"free_after": free,
		"after_hit": after,
		"source": "knockdown invuln blocks chain; getup restores hit",
	}
	_remember_session(session)
	_append_events(session.ledger.to_array())
	return errors


static func punch_disarm(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_melee_close", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p2: Fighter = session.fighter_at_slot(1)
	_apply_slot(session, 0, PackedStringArray(), 8, 0.0)
	var held: bool = p2.holds_gun()
	var pick0: int = _live_pickups(session)
	_apply_slot_action(session, 0, "melee", PackedStringArray(), 1, 0.0)
	_apply_slot(session, 0, PackedStringArray(), _Combat.startup_ticks("fists", "melee") + 1, 0.0)
	var disarmed: bool = not p2.holds_gun()
	var pick1: int = _live_pickups(session)
	var one_drop: bool = pick1 == pick0 + 1
	var ev: int = session.ledger.count_kind("disarm")
	var drop_ev: int = session.ledger.count_kind("item_drop")
	if not held:
		errors.append("DISARM P2 must start with a gun")
	if not disarmed:
		errors.append("DISARM punch must strip P2 gun")
	if not one_drop:
		errors.append("DISARM must spawn exactly one drop pick0=%d pick1=%d" % [pick0, pick1])
	if ev < 1 or drop_ev < 1:
		errors.append("DISARM missing disarm/item_drop events")
	outcome_disarm = {
		"verdict": "pass" if held and disarmed and one_drop and ev >= 1 and drop_ev >= 1 else "fail",
		"held_before": held,
		"holds_after": p2.holds_gun(),
		"pick0": pick0,
		"pick1": pick1,
		"disarm_events": ev,
		"item_drop_events": drop_ev,
		"source": "punch vs gun-holder drops one pistol",
	}
	_remember_session(session)
	_append_events(session.ledger.to_array())
	return errors


static func dropped_item_lifecycle(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_melee_close", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p2: Fighter = session.fighter_at_slot(1)
	_apply_slot(session, 0, PackedStringArray(), 8, 0.0)
	_apply_slot_action(session, 0, "melee", PackedStringArray(), 1, 0.0)
	_apply_slot(session, 0, PackedStringArray(), _Combat.startup_ticks("fists", "melee") + 1, 0.0)
	var after_hit: int = _live_pickups(session)
	var uid0: int = _first_drop_uid(session)
	_apply_idle(session, 20)
	var persist: int = _live_pickups(session)
	var uid1: int = _first_drop_uid(session)
	var persist_ok: bool = persist == after_hit and persist == 1 and uid0 == uid1 and uid0 > 0
	if not persist_ok:
		errors.append("DROP vanished or duplicated persist=%d uid %d->%d" % [persist, uid0, uid1])
	var wait_free: int = _Combat.hit_invuln_ticks() + 8
	_apply_idle(session, wait_free)
	_apply_slot_action(session, 1, "melee", PackedStringArray(["crouch"]), 1, 0.0)
	_apply_slot(session, 1, PackedStringArray(["crouch"]), 4, 0.0)
	var after_pick: int = _live_pickups(session)
	var picked: bool = p2.holds_gun()
	var pick_ev: int = session.ledger.count_kind("item_pickup")
	var no_dup: bool = after_hit == 1 and persist == 1 and after_pick == 0
	if after_pick != 0:
		errors.append("DROP pickup must consume the item left=%d" % after_pick)
	if not picked:
		errors.append("DROP P2 crouch+melee must reclaim the gun")
	outcome_drop = {
		"verdict": "pass" if persist_ok and no_dup and picked and pick_ev >= 1 else "fail",
		"after_hit": after_hit,
		"persist": persist,
		"uid0": uid0,
		"uid1": uid1,
		"after_pick": after_pick,
		"picked": picked,
		"item_pickup": pick_ev,
		"source": "disarmed gun persists one uid then one pickup",
	}
	_remember_session(session)
	_append_events(session.ledger.to_array())
	return errors


static func death_cause_valid(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_melee_close", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p2: Fighter = session.fighter_at_slot(1)
	_apply_slot(session, 0, PackedStringArray(), 8, 0.0)
	var swings: int = 0
	var p1: Fighter = session.player1()
	while not p2.dead and swings < 20:
		if p1 != null and p2.global_position.x > p1.global_position.x + 16.0:
			_apply_slot(session, 0, PackedStringArray(["right"]), 4, 1.0)
		_apply_slot_action(session, 0, "melee", PackedStringArray(), 1, 0.0)
		_apply_slot(session, 0, PackedStringArray(), _Combat.total_ticks("fists", "melee") + _Combat.hit_invuln_ticks() + 2, 0.0)
		swings += 1
	var cause: String = p2.death_cause
	var valid: bool = _Combat.valid_death_cause(cause)
	var died: bool = p2.dead and cause == "damage"
	var death_ev: int = session.ledger.count_kind("death")
	var bad: bool = session.ledger.count_kind("force_kill") > 0 or cause == "script"
	if not died:
		errors.append("DEATH melee must kill with cause=damage got=%s dead=%s" % [cause, str(p2.dead)])
	if not valid:
		errors.append("DEATH cause %s is not a valid official cause" % cause)
	if bad:
		errors.append("DEATH used force_kill or script")
	if death_ev < 1:
		errors.append("DEATH missing death event")
	outcome_death = {
		"verdict": "pass" if died and valid and not bad and death_ev >= 1 else "fail",
		"dead": p2.dead,
		"cause": cause,
		"swings": swings,
		"death_events": death_ev,
		"source": "apply_frames punches until HP 0; cause from event",
	}
	_remember_session(session)
	_append_events(session.ledger.to_array())
	return errors


static func entry_exit_events(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_melee_close", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_apply_slot(session, 0, PackedStringArray(), 8, 0.0)
	_apply_slot(session, 0, PackedStringArray(["jump"]), 2, 0.0)
	_apply_slot_action(session, 0, "kick", PackedStringArray(), 1, 0.0)
	var wait: int = _Combat.knockdown_ticks() + _Combat.getup_ticks() + _Combat.knockdown_invuln_ticks() + 8
	_apply_slot(session, 0, PackedStringArray(), wait, 0.0)
	var pairs: PackedStringArray = PackedStringArray([
		"knockback_start", "knockdown_start", "knockdown_end",
		"getup_start", "getup_end", "invuln_start", "invuln_end"
	])
	var missing: PackedStringArray = PackedStringArray()
	var i: int = 0
	while i < pairs.size():
		var kind: String = String(pairs[i])
		if session.ledger.count_kind(kind) < 1:
			missing.append(kind)
			errors.append("EVENTS missing %s" % kind)
		i += 1
	var hash0: String = session.snapshot_hash()
	_apply_idle(session, 4)
	var hash1: String = session.snapshot_hash()
	outcome_events = {
		"verdict": "pass" if missing.is_empty() else "fail",
		"missing": Array(missing),
		"hash0": hash0,
		"hash1": hash1,
		"source": "kick knockdown emits entry/exit kinds",
	}
	_remember_session(session)
	_append_events(session.ledger.to_array())
	return errors


static func live_reaction(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_melee_close", 0)
	var session: GameSession = app.session
	var p2: Fighter = session.fighter_at_slot(1)
	var viewport: Viewport = app.get_viewport()
	await SimReplay.sync_physics(app)
	InputInjector.release_known(viewport)
	InputActions.reset_edges()
	used_parse_input_event += 1
	_apply_slot(session, 0, PackedStringArray(), 8, 0.0)
	var hp0: float = p2.health
	var held: bool = p2.holds_gun()
	InputInjector.inject_key(KEY_N, true, viewport)
	var n: int = 0
	while n < _Combat.startup_ticks("fists", "melee") + _Combat.active_ticks("fists", "melee") + 2:
		session.step_from_live_input()
		n += 1
	var live_ok: bool = p2.health < hp0 - 0.01 and (not p2.holds_gun() if held else true)
	if not live_ok:
		errors.append("LIVE punch did not damage+disarm hp=%s gun=%s" % [str(p2.health), p2.gun_id])
	InputInjector.release_known(viewport)
	outcome_live = {
		"verdict": "pass" if live_ok else "fail",
		"hp0": hp0,
		"hp1": p2.health,
		"holds_gun": p2.holds_gun(),
		"source": "parse_input_event KEY_N + step_from_live_input",
	}
	_remember_session(session)
	return errors


static func _require_outcomes() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var labels: PackedStringArray = PackedStringArray([
		"DAMAGE", "KNOCK", "AIR", "DOWN", "GETUP", "INVULN", "CHAIN",
		"DISARM", "DROP", "DEATH", "EVENTS", "LIVE"
	])
	var rows: Array = [
		outcome_damage, outcome_knock, outcome_air, outcome_down, outcome_getup,
		outcome_invuln, outcome_chain, outcome_disarm, outcome_drop, outcome_death,
		outcome_events, outcome_live
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


static func _apply_slot_action(
	session: GameSession, slot: int, action: String, held: PackedStringArray, ticks: int, move_x: float
) -> void:
	var n: int = 0
	while n < ticks:
		var frames: Array = []
		var i: int = 0
		while i < session.fighters.size():
			var raw: Dictionary = InputActions.empty_frame(session.clock.tick, i)
			if i == slot:
				raw["held"] = Array(held)
				raw["pressed"] = [action] if n == 0 else []
				raw["move_x"] = move_x
			frames.append(InputFrame.from_dict(raw))
			i += 1
		_record_apply(session.apply_frames(frames))
		n += 1


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


static func _live_pickups(session: GameSession) -> int:
	var n: int = 0
	var i: int = 0
	while i < session.pickups.size():
		var drop: Pickup = session.pickups[i]
		if drop != null and is_instance_valid(drop):
			n += 1
		i += 1
	return n


static func _spawn_bullet(session: GameSession, target: Fighter, damage: float) -> void:
	var shot: Bullet = Bullet.new()
	shot.setup(target.global_position, Vector2.RIGHT, 8.0, damage, 0, 0)
	session.add_child(shot)
	session.bullets.append(shot)


static func _first_drop_uid(session: GameSession) -> int:
	var i: int = 0
	while i < session.pickups.size():
		var drop: Pickup = session.pickups[i]
		if drop != null and is_instance_valid(drop):
			return drop.drop_uid
		i += 1
	return 0


static func _drain_physics(app: App) -> void:
	InputActions.reset_edges()
	await SimReplay.sync_physics(app)
	await SimReplay.sync_physics(app)


static func _capture_start(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_melee_close", 0)
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

class_name CombatCases
extends RefCounted

const _Combat: GDScript = preload("res://src/sim/combat.gd")

## VF3-WP1 official melee phase / hitbox cases.
## Proof is InputFrame apply_frames plus live InputEvent inject.
## 60 Hz is ledger:RL-SIM-FIXED-60 (assumption).
## Phases stay ledger:RL-HIT-PHASES (assumption).
## Boxes stay ledger:RL-HIT-BOX (assumption).
## Friendly-fire stays ledger:RL-HIT-FF (assumption).
## Hitstop stays ledger:RL-HIT-HITSTOP (assumption).
## Kick stays ledger:RL-MOVE-JUMP-KICK (assumption).
## Hold-to-aim stays assumption. Y8 roll/dive stays unavailable.
## USED_APPLY_FRAMES counts successful apply_frames only.

static var used_step_fixed: int = 0
static var used_apply_frames: int = 0
static var used_apply_frames_attempted: int = 0
static var used_apply_frames_succeeded: int = 0
static var used_parse_input_event: int = 0
static var used_action_press: int = 0
static var outcome_hit: Dictionary = {}
static var outcome_miss: Dictionary = {}
static var outcome_behind: Dictionary = {}
static var outcome_above: Dictionary = {}
static var outcome_below: Dictionary = {}
static var outcome_once: Dictionary = {}
static var outcome_snap: Dictionary = {}
static var outcome_pause: Dictionary = {}
static var outcome_live: Dictionary = {}
static var outcome_replay: Dictionary = {}
static var outcome_phases: Dictionary = {}
static var outcome_reach: Dictionary = {}
static var outcome_ff: Dictionary = {}
static var outcome_hitstop: Dictionary = {}
static var outcome_crouch: Dictionary = {}
static var outcome_kick: Dictionary = {}
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
	outcome_hit = {"verdict": "unproven"}
	outcome_miss = {"verdict": "unproven"}
	outcome_behind = {"verdict": "unproven"}
	outcome_above = {"verdict": "unproven"}
	outcome_below = {"verdict": "unproven"}
	outcome_once = {"verdict": "unproven"}
	outcome_snap = {"verdict": "unproven"}
	outcome_pause = {"verdict": "unproven"}
	outcome_live = {"verdict": "unproven"}
	outcome_replay = {"verdict": "unproven", "pairs": []}
	outcome_phases = {"verdict": "unproven"}
	outcome_reach = {"verdict": "unproven"}
	outcome_ff = {"verdict": "unproven"}
	outcome_hitstop = {"verdict": "unproven"}
	outcome_crouch = {"verdict": "unproven"}
	outcome_kick = {"verdict": "unproven"}
	snapshot_start = {}
	snapshot_end = {}
	events_end = []
	events_all = []
	var errors: PackedStringArray = PackedStringArray()
	_append(errors, schema_and_data())
	_append(errors, await _capture_start(app))
	_append(errors, await replay_traces_twice(app))
	_append(errors, await hit_and_phases(app))
	_append(errors, await miss_reach(app))
	_append(errors, await miss_behind(app))
	_append(errors, await miss_above(app))
	_append(errors, await miss_below(app))
	_append(errors, await one_hit_window(app))
	_append(errors, await damage_knock_snapshot(app))
	_append(errors, await pause_during_attack(app))
	_append(errors, await weapon_reach(app))
	_append(errors, await friendly_fire_rules(app))
	_append(errors, await hitstop_clock(app))
	_append(errors, await crouch_attack(app))
	_append(errors, await aerial_kick(app))
	_append(errors, await live_melee(app))
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
	if str(row.get("phases_class", "")) != "assumption":
		errors.append("phases must stay assumption")
	if str(row.get("hitbox_class", "")) != "assumption":
		errors.append("hitbox must stay assumption")
	if str(row.get("ff_class", "")) != "assumption":
		errors.append("friendly-fire must stay assumption")
	if str(row.get("hitstop_class", "")) != "assumption":
		errors.append("hitstop must stay assumption")
	if str(row.get("hitstop_clock", "")) != "presentation_only":
		errors.append("hitstop must stay presentation_only")
	if str(row.get("hold_to_aim_class", "")) != "assumption":
		errors.append("hold-to-aim must stay assumption")
	if str(row.get("roll_dive_class", "")) != "unavailable":
		errors.append("Y8 roll/dive observation must stay unavailable")
	if not bool(row.get("one_hit_per_window", false)):
		errors.append("one_hit_per_window must be true")
	if _Combat.startup_ticks("fists", "melee") < 2:
		errors.append("fists startup must be at least 2 ticks")
	if _Combat.friendly_fire_on("vs1"):
		errors.append("vs1 friendly_fire must be false")
	if not _Combat.friendly_fire_on("vs2"):
		errors.append("vs2 friendly_fire must be true")
	var maps: PackedStringArray = PackedStringArray([
		"fx_melee_close", "fx_melee_far", "fx_melee_behind",
		"fx_melee_above", "fx_melee_below", "fx_melee_mid"
	])
	var mi: int = 0
	while mi < maps.size():
		if not Maps.has_fixture(String(maps[mi])):
			errors.append("missing combat fixture %s" % String(maps[mi]))
		mi += 1
	return errors


static func replay_traces_twice(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var paths: PackedStringArray = SimTrace.list_dir(SimConstants.COMBAT_TRACE_DIR)
	if paths.size() < 6:
		errors.append("expected >=6 combat traces, got %d" % paths.size())
	var required: PackedStringArray = PackedStringArray([
		"melee_hit", "melee_miss", "melee_behind", "melee_above",
		"melee_below", "melee_once", "melee_crouch", "melee_kick"
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
		if "assumption" not in str(trace.get("phases", "")):
			errors.append("%s must keep phases assumption" % path.get_file())
		names.append(str(trace.get("name", path.get_file())))
		await _drain_physics(app)
		var a: Dictionary = await SimReplay.play_path(app, path)
		await _drain_physics(app)
		var b: Dictionary = await SimReplay.play_path(app, path)
		_record_apply_batch(int(a.get("ticks", 0)), bool(a.get("ok", false)))
		_record_apply_batch(int(b.get("ticks", 0)), bool(b.get("ok", false)))
		if not bool(a.get("ok", false)):
			errors.append("combat %s run1 failed: %s" % [path.get_file(), _join(a)])
		if not bool(b.get("ok", false)):
			errors.append("combat %s run2 failed: %s" % [path.get_file(), _join(b)])
		if not bool(a.get("used_apply_frames", false)) or bool(a.get("used_cmd_dicts", true)):
			errors.append("combat %s MATCH used cmd dicts" % path.get_file())
		var hash_a: String = str(a.get("final_hash", ""))
		var hash_b: String = str(b.get("final_hash", ""))
		var match_ok: bool = hash_a != "" and hash_a == hash_b
		if not match_ok:
			errors.append("combat %s replay hashes differ" % path.get_file())
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
			errors.append("missing combat trace %s" % String(required[i]))
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


static func hit_and_phases(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var log: Dictionary = await _swing(app, "vs2", "fx_melee_close", "melee", PackedStringArray())
	var p1: Fighter = log.get("p1") as Fighter
	var p2: Fighter = log.get("p2") as Fighter
	var hp0: float = float(log.get("hp0", 0.0))
	var hp1: float = float(log.get("hp1", 0.0))
	var vx0: float = float(log.get("vx0", 0.0))
	var vx1: float = float(log.get("vx_hit", log.get("vx1", 0.0)))
	var startup_hp: float = float(log.get("startup_hp", hp0))
	var phases: PackedStringArray = log.get("phases") as PackedStringArray
	var hit_events: int = int(log.get("hit_events", 0))
	var expected: float = _Combat.damage_of("fists", "melee")
	var dmg: float = hp0 - hp1
	var startup_ok: bool = phases.has("startup") and absf(startup_hp - hp0) <= 0.01
	var active_ok: bool = phases.has("active")
	var recovery_ok: bool = phases.has("recovery")
	var hit_ok: bool = dmg + 0.01 >= expected and dmg <= expected + 0.01
	var knock_ok: bool = vx1 > vx0 + 8.0
	var no_same_tick: bool = str(log.get("press_phase", "")) == "startup"
	if not startup_ok:
		errors.append("HIT startup must leave HP unchanged got=%s" % str(startup_hp))
	if not hit_ok:
		errors.append("HIT hp delta %s != fists 10" % str(dmg))
	if not knock_ok:
		errors.append("HIT knockback missing vx0=%s vx1=%s" % [str(vx0), str(vx1)])
	if not no_same_tick:
		errors.append("HIT press tick must be startup not same-tick distance")
	if p1 == null or p2 == null:
		errors.append("HIT missing fighters")
	var pass_ok: bool = startup_ok and active_ok and recovery_ok and hit_ok and knock_ok and no_same_tick and hit_events >= 1
	outcome_hit = {
		"verdict": "pass" if pass_ok else "fail",
		"hp0": hp0,
		"hp1": hp1,
		"damage": dmg,
		"expected": expected,
		"vx0": vx0,
		"vx1": vx1,
		"vx_hit": vx1,
		"startup_hp": startup_hp,
		"press_phase": str(log.get("press_phase", "")),
		"phases": Array(phases),
		"hit_events": hit_events,
		"dx": float(log.get("dx", 0.0)),
		"dy": float(log.get("dy", 0.0)),
		"source": "apply_frames fx_melee_close HP/knock after startup",
	}
	outcome_phases = {
		"verdict": "pass" if startup_ok and active_ok and recovery_ok and no_same_tick else "fail",
		"phases": Array(phases),
		"press_phase": str(log.get("press_phase", "")),
		"startup_hp": startup_hp,
		"source": "phase log ticks, not event-only",
	}
	return errors


static func miss_reach(app: App) -> PackedStringArray:
	return await _miss_case(app, "fx_melee_far", "reach", "outcome_miss")


static func miss_behind(app: App) -> PackedStringArray:
	return await _miss_case(app, "fx_melee_behind", "behind", "outcome_behind")


static func miss_above(app: App) -> PackedStringArray:
	return await _miss_case(app, "fx_melee_above", "above", "outcome_above")


static func miss_below(app: App) -> PackedStringArray:
	return await _miss_case(app, "fx_melee_below", "below", "outcome_below")


static func one_hit_window(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var log: Dictionary = await _swing(app, "vs2", "fx_melee_close", "melee", PackedStringArray())
	var hp0: float = float(log.get("hp0", 0.0))
	var hp1: float = float(log.get("hp1", 0.0))
	var hit_events: int = int(log.get("hit_events", 0))
	var expected: float = _Combat.damage_of("fists", "melee")
	var once_ok: bool = hit_events == 1 and absf((hp0 - hp1) - expected) <= 0.01
	if not once_ok:
		errors.append("ONCE hit_events=%d dmg=%s" % [hit_events, str(hp0 - hp1)])
	outcome_once = {
		"verdict": "pass" if once_ok else "fail",
		"hit_events": hit_events,
		"hp0": hp0,
		"hp1": hp1,
		"damage": hp0 - hp1,
		"expected": expected,
		"source": "one HP drop equals one fists hit across active window",
	}
	return errors


static func damage_knock_snapshot(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_melee_close", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p2: Fighter = session.fighter_at_slot(1)
	_apply_p1(session, PackedStringArray(), 8, 0.0)
	var hp0: float = p2.health
	var snap0: Dictionary = session.snapshot()
	_apply_p1_action(session, "melee", PackedStringArray(), 1, 0.0)
	_apply_p1(session, PackedStringArray(), _Combat.startup_ticks("fists", "melee") + 1, 0.0)
	var snap1: Dictionary = session.snapshot()
	var fighters: Array = snap1.get("fighters", []) as Array
	var row: Dictionary = {}
	if fighters.size() > 1:
		row = fighters[1] as Dictionary
	var hp_q: int = int(row.get("hp", 0))
	var expected_q: int = SimConstants.quantize(hp0 - _Combat.damage_of("fists", "melee"))
	var vx: int = int(row.get("vx", 0))
	var ok: bool = hp_q == expected_q and vx > 0
	if not ok:
		errors.append("SNAP hp %d != %d or knock vx %d" % [hp_q, expected_q, vx])
	outcome_snap = {
		"verdict": "pass" if ok else "fail",
		"hp0": hp0,
		"hp_q": hp_q,
		"expected_q": expected_q,
		"vx_q": vx,
		"hash0": SimSnapshot.stable_hash(snap0),
		"hash1": SimSnapshot.stable_hash(snap1),
		"source": "snapshot fighter hp/vx after apply_frames",
	}
	_remember_session(session)
	return errors


static func pause_during_attack(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_melee_close", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	var p2: Fighter = session.fighter_at_slot(1)
	_apply_p1(session, PackedStringArray(), 8, 0.0)
	_apply_p1_action(session, "melee", PackedStringArray(), 1, 0.0)
	var phase0: String = p1.attack_phase
	var tick0: int = session.clock.tick
	var hp0: float = p2.health
	session.set_paused(true)
	var rejected: bool = not _record_apply(session.apply_frames(_idle_frames(session)))
	var tick1: int = session.clock.tick
	var phase1: String = p1.attack_phase
	var hp1: float = p2.health
	var paused_ok: bool = rejected and tick1 == tick0 and phase1 == phase0 and absf(hp1 - hp0) <= 0.01
	if not paused_ok:
		errors.append("PAUSE did not freeze tick/phase/hp")
	session.set_paused(false)
	_apply_p1(session, PackedStringArray(), _Combat.total_ticks("fists", "melee") + 2, 0.0)
	var finished: bool = p2.health < hp0 - 0.01
	if not finished:
		errors.append("PAUSE resume did not complete the attack")
	outcome_pause = {
		"verdict": "pass" if paused_ok and finished else "fail",
		"tick0": tick0,
		"tick1": tick1,
		"phase0": phase0,
		"phase1": phase1,
		"hp0": hp0,
		"hp_paused": hp1,
		"hp_end": p2.health,
		"rejected": rejected,
		"source": "pause mid-startup freezes tick/phase/HP; resume finishes hit",
	}
	_remember_session(session)
	return errors


static func weapon_reach(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_melee_mid", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	var p2: Fighter = session.fighter_at_slot(1)
	_apply_p1(session, PackedStringArray(), 8, 0.0)
	var hp0: float = p2.health
	var dx: float = p2.global_position.x - p1.global_position.x
	_apply_p1_action(session, "melee", PackedStringArray(), 1, 0.0)
	_apply_p1(session, PackedStringArray(), _Combat.total_ticks("fists", "melee") + 2, 0.0)
	var fists_miss: bool = absf(p2.health - hp0) <= 0.01
	p1._cancel_attack()
	p1.melee_cd = 0.0
	p1.melee_id = "pipe"
	_apply_p1_action(session, "melee", PackedStringArray(), 1, 0.0)
	_apply_p1(session, PackedStringArray(), _Combat.total_ticks("pipe", "melee") + 2, 0.0)
	var pipe_hit: bool = p2.health < hp0 - 0.01
	if not fists_miss:
		errors.append("REACH fists must miss mid gap dx=%s hp=%s" % [str(dx), str(p2.health)])
	if not pipe_hit:
		errors.append("REACH pipe must hit mid gap")
	outcome_reach = {
		"verdict": "pass" if fists_miss and pipe_hit else "fail",
		"dx": dx,
		"fists_miss": fists_miss,
		"pipe_hit": pipe_hit,
		"hp0": hp0,
		"hp1": p2.health,
		"source": "same spawn gap: fists miss, pipe hitbox connects",
	}
	_remember_session(session)
	return errors


static func friendly_fire_rules(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs1", "fx_melee_close", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	var bot: Fighter = session.fighter_at_slot(1)
	bot.team = 0
	_apply_p1(session, PackedStringArray(), 8, 0.0)
	var hp0: float = bot.health
	_apply_p1_action(session, "melee", PackedStringArray(), 1, 0.0)
	_apply_p1(session, PackedStringArray(), _Combat.total_ticks("fists", "melee") + 2, 0.0)
	var vs1_block: bool = absf(bot.health - hp0) <= 0.01
	if not vs1_block:
		errors.append("FF vs1 same-team must not change HP")
	app.start_fight("vs2", "fx_melee_close", 0)
	await SimReplay.sync_physics(app)
	session = app.session
	p1 = session.player1()
	var p2: Fighter = session.fighter_at_slot(1)
	_apply_p1(session, PackedStringArray(), 8, 0.0)
	hp0 = p2.health
	_apply_p1_action(session, "melee", PackedStringArray(), 1, 0.0)
	_apply_p1(session, PackedStringArray(), _Combat.total_ticks("fists", "melee") + 2, 0.0)
	var vs2_hit: bool = p2.health < hp0 - 0.01
	if not vs2_hit:
		errors.append("FF vs2 different teams must deal damage")
	outcome_ff = {
		"verdict": "pass" if vs1_block and vs2_hit else "fail",
		"vs1_block": vs1_block,
		"vs2_hit": vs2_hit,
		"vs1_ff": _Combat.friendly_fire_on("vs1"),
		"vs2_ff": _Combat.friendly_fire_on("vs2"),
		"source": "vs1 same-team HP frozen; vs2 PVP HP drops",
	}
	_remember_session(session)
	return errors


static func hitstop_clock(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_melee_close", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	_apply_p1(session, PackedStringArray(), 8, 0.0)
	_apply_p1_action(session, "melee", PackedStringArray(), 1, 0.0)
	_apply_p1(session, PackedStringArray(), _Combat.startup_ticks("fists", "melee") + 1, 0.0)
	var freeze: int = p1.hitstop_left
	var tick0: int = session.clock.tick
	_apply_p1(session, PackedStringArray(), 1, 0.0)
	var tick1: int = session.clock.tick
	var clock_ok: bool = tick1 == tick0 + 1
	var had_hitstop: bool = freeze > 0
	if not had_hitstop:
		errors.append("HITSTOP never armed")
	if not clock_ok:
		errors.append("HITSTOP must not freeze SimClock")
	outcome_hitstop = {
		"verdict": "pass" if had_hitstop and clock_ok else "fail",
		"hitstop_left": freeze,
		"tick0": tick0,
		"tick1": tick1,
		"source": "hitstop presentation; clock still advances",
	}
	_remember_session(session)
	return errors


static func crouch_attack(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var log: Dictionary = await _swing(app, "vs2", "fx_melee_close", "melee", PackedStringArray(["crouch"]))
	var style: String = str(log.get("style", ""))
	var hp0: float = float(log.get("hp0", 0.0))
	var hp1: float = float(log.get("hp1", 0.0))
	var ok: bool = style == "crouch" and hp1 < hp0 - 0.01
	if not ok:
		errors.append("CROUCH style=%s hp %s->%s" % [style, str(hp0), str(hp1)])
	outcome_crouch = {
		"verdict": "pass" if ok else "fail",
		"style": style,
		"hp0": hp0,
		"hp1": hp1,
		"source": "apply_frames crouch+melee uses crouch hitbox",
	}
	return errors


static func aerial_kick(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_melee_close", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	var p2: Fighter = session.fighter_at_slot(1)
	_apply_p1(session, PackedStringArray(), 8, 0.0)
	var hp0: float = p2.health
	_apply_p1(session, PackedStringArray(["jump"]), 2, 0.0)
	_apply_p1_action(session, "kick", PackedStringArray(), 1, 0.0)
	var style0: String = p1.attack_style
	_apply_p1(session, PackedStringArray(), _Combat.total_ticks("kick", "kick") + 2, 0.0)
	var kicked: bool = style0 == "kick" or p1.kick_seq >= 1
	var hit_ok: bool = p2.health < hp0 - 0.01
	if not kicked:
		errors.append("KICK attack style missing")
	if not hit_ok:
		errors.append("KICK must deal damage through kick hitbox")
	outcome_kick = {
		"verdict": "pass" if kicked and hit_ok else "fail",
		"style": style0,
		"hp0": hp0,
		"hp1": p2.health,
		"kick_seq": p1.kick_seq,
		"source": "apply_frames jump then kick hitbox",
	}
	_remember_session(session)
	return errors


static func live_melee(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_melee_close", 0)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	var p2: Fighter = session.fighter_at_slot(1)
	var viewport: Viewport = app.get_viewport()
	await SimReplay.sync_physics(app)
	InputInjector.release_known(viewport)
	InputActions.reset_edges()
	used_parse_input_event += 1
	_apply_p1(session, PackedStringArray(), 8, 0.0)
	var hp0: float = p2.health
	InputInjector.inject_key(KEY_N, true, viewport)
	var n: int = 0
	while n < _Combat.startup_ticks("fists", "melee") + _Combat.active_ticks("fists", "melee") + 2:
		session.step_from_live_input()
		n += 1
	var live_ok: bool = p2.health < hp0 - 0.01 and (p1.attack_seq >= 1 or p1.attack_phase != "idle")
	if not live_ok:
		errors.append("LIVE melee did not drop HP pose=%s hp=%s" % [p1.current_pose(), str(p2.health)])
	InputInjector.release_known(viewport)
	outcome_live = {
		"verdict": "pass" if live_ok else "fail",
		"hp0": hp0,
		"hp1": p2.health,
		"phase": p1.attack_phase,
		"pose": p1.current_pose(),
		"source": "parse_input_event KEY_N + step_from_live_input",
	}
	_remember_session(session)
	return errors


static func _miss_case(app: App, map_id: String, expect_kind: String, outcome_name: String) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var log: Dictionary = await _swing(app, "vs2", map_id, "melee", PackedStringArray())
	var hp0: float = float(log.get("hp0", 0.0))
	var hp1: float = float(log.get("hp1", 0.0))
	var kind: String = str(log.get("miss_kind", ""))
	var hit_events: int = int(log.get("hit_events", 0))
	var hp_ok: bool = absf(hp1 - hp0) <= 0.01
	var kind_ok: bool = kind == expect_kind
	var no_hit: bool = hit_events == 0
	if not hp_ok:
		errors.append("%s HP changed %s->%s" % [map_id, str(hp0), str(hp1)])
	if not kind_ok:
		errors.append("%s miss kind %s != %s dx=%s dy=%s" % [
			map_id, kind, expect_kind, str(log.get("dx", 0.0)), str(log.get("dy", 0.0))
		])
	if not no_hit:
		errors.append("%s must not emit hit" % map_id)
	var row: Dictionary = {
		"verdict": "pass" if hp_ok and kind_ok and no_hit else "fail",
		"hp0": hp0,
		"hp1": hp1,
		"dx": float(log.get("dx", 0.0)),
		"dy": float(log.get("dy", 0.0)),
		"facing": float(log.get("facing", 0.0)),
		"miss_kind": kind,
		"hit_events": hit_events,
		"source": "apply_frames %s HP unchanged + geometry %s" % [map_id, expect_kind],
	}
	if outcome_name == "outcome_miss":
		outcome_miss = row
	elif outcome_name == "outcome_behind":
		outcome_behind = row
	elif outcome_name == "outcome_above":
		outcome_above = row
	else:
		outcome_below = row
	return errors


static func _swing(app: App, mode: String, map_id: String, action: String, held: PackedStringArray) -> Dictionary:
	app.start_fight(mode, map_id, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	var p2: Fighter = session.fighter_at_slot(1)
	_apply_p1(session, PackedStringArray(), 8, 0.0)
	var hp0: float = p2.health if p2 != null else 0.0
	var vx0: float = p2.velocity.x if p2 != null else 0.0
	_apply_p1_action(session, action, held, 1, 0.0)
	var press_phase: String = p1.attack_phase
	var startup_hp: float = p2.health if p2 != null else 0.0
	var phases: PackedStringArray = PackedStringArray()
	if press_phase != "":
		phases.append(press_phase)
	var n: int = 0
	var vx_hit: float = vx0
	var total: int = _Combat.total_ticks(p1.attack_weapon if p1.attack_weapon != "" else "fists", p1.attack_style if p1.attack_style != "" else "melee") + 4
	while n < total:
		_apply_p1(session, held, 1, 0.0)
		if p1.attack_phase != "" and not phases.has(p1.attack_phase):
			phases.append(p1.attack_phase)
		if p2 != null and p2.health < hp0 - 0.01:
			if absf(p2.velocity.x) > absf(vx_hit):
				vx_hit = p2.velocity.x
		n += 1
	var miss_kind: String = _Combat.classify_miss(p1, p2)
	var log: Dictionary = {
		"p1": p1,
		"p2": p2,
		"hp0": hp0,
		"hp1": p2.health if p2 != null else 0.0,
		"vx0": vx0,
		"vx1": p2.velocity.x if p2 != null else 0.0,
		"vx_hit": vx_hit,
		"startup_hp": startup_hp,
		"press_phase": press_phase,
		"phases": phases,
		"style": p1.attack_style,
		"hit_events": session.ledger.count_kind("hit") + session.ledger.count_kind("kick_hit"),
		"dx": (p2.global_position.x - p1.global_position.x) if p2 != null else 0.0,
		"dy": (p2.global_position.y - p1.global_position.y) if p2 != null else 0.0,
		"facing": p1.facing,
		"miss_kind": miss_kind,
	}
	_remember_session(session)
	_append_events(session.ledger.to_array())
	return log


static func _require_outcomes() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var labels: PackedStringArray = PackedStringArray([
		"HIT", "MISS", "BEHIND", "ABOVE", "BELOW", "ONCE", "SNAP", "PAUSE",
		"LIVE", "PHASES", "REACH", "FF", "HITSTOP", "CROUCH", "KICK"
	])
	var rows: Array = [
		outcome_hit, outcome_miss, outcome_behind, outcome_above, outcome_below,
		outcome_once, outcome_snap, outcome_pause, outcome_live, outcome_phases,
		outcome_reach, outcome_ff, outcome_hitstop, outcome_crouch, outcome_kick
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

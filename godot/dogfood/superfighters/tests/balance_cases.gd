class_name BalanceCases
extends RefCounted

const _Combat: GDScript = preload("res://src/sim/combat.gd")
const _Bal: GDScript = preload("res://src/sim/balance.gd")

## VF3-WP6 official chaos / balance harness.
## Proof is InputFrame apply_frames plus live InputEvent inject
## plus 1000 seed-controlled resolution rolls.
## 60 Hz is ledger:RL-SIM-FIXED-60 (assumption).
## Chaos stays ledger:RL-MODE-CHAOS (assumption).
## Crit / knock / spread / caps / stamina stay assumption.
## Hold-to-aim stays ledger:RL-CTRL-HOLD-AIM (assumption).
## Y8 roll/dive stays unavailable. USED_APPLY_FRAMES counts success only.

static var used_step_fixed: int = 0
static var used_apply_frames: int = 0
static var used_apply_frames_attempted: int = 0
static var used_apply_frames_succeeded: int = 0
static var used_parse_input_event: int = 0
static var used_action_press: int = 0
static var outcome_schema: Dictionary = {}
static var outcome_batch: Dictionary = {}
static var outcome_dist: Dictionary = {}
static var outcome_dom: Dictionary = {}
static var outcome_melee: Dictionary = {}
static var outcome_high: Dictionary = {}
static var outcome_overcap: Dictionary = {}
static var outcome_pit: Dictionary = {}
static var outcome_chain: Dictionary = {}
static var outcome_ff: Dictionary = {}
static var outcome_stamina: Dictionary = {}
static var outcome_data: Dictionary = {}
static var outcome_live: Dictionary = {}
static var outcome_replay: Dictionary = {}
static var snapshot_start: Dictionary = {}
static var snapshot_end: Dictionary = {}
static var events_end: Array = []
static var events_all: Array = []
static var batch_report: Dictionary = {}


static func run_all(app: App) -> PackedStringArray:
	used_step_fixed = 0
	used_apply_frames = 0
	used_apply_frames_attempted = 0
	used_apply_frames_succeeded = 0
	used_parse_input_event = 0
	used_action_press = 0
	outcome_schema = {"verdict": "unproven"}
	outcome_batch = {"verdict": "unproven"}
	outcome_dist = {"verdict": "unproven"}
	outcome_dom = {"verdict": "unproven"}
	outcome_melee = {"verdict": "unproven"}
	outcome_high = {"verdict": "unproven"}
	outcome_overcap = {"verdict": "unproven"}
	outcome_pit = {"verdict": "unproven"}
	outcome_chain = {"verdict": "unproven"}
	outcome_ff = {"verdict": "unproven"}
	outcome_stamina = {"verdict": "unproven"}
	outcome_data = {"verdict": "unproven"}
	outcome_live = {"verdict": "unproven"}
	outcome_replay = {"verdict": "unproven", "pairs": []}
	snapshot_start = {}
	snapshot_end = {}
	events_end = []
	events_all = []
	batch_report = {}
	var errors: PackedStringArray = PackedStringArray()
	_append(errors, schema_and_data())
	_append(errors, seeded_batch())
	_append(errors, await _capture_start(app))
	_append(errors, await replay_traces_twice(app))
	_append(errors, await close_melee(app))
	_append(errors, await high_ground(app))
	_append(errors, await pit_fall(app))
	_append(errors, await grenade_chain(app))
	_append(errors, await friendly_fire(app))
	_append(errors, await stamina_tuning(app))
	_append(errors, await live_balance(app))
	_append(errors, await fire_path_overcap(app))
	_append(errors, finalize_dom())
	_append(errors, _require_outcomes())
	return errors


static func schema_and_data() -> PackedStringArray:
	var errors: PackedStringArray = _Bal.validate()
	var required: PackedStringArray = PackedStringArray([
		"fx_balance_melee", "fx_balance_high", "fx_balance_pit",
		"fx_balance_chain", "fx_balance_ff"
	])
	var i: int = 0
	while i < required.size():
		var fid: String = String(required[i])
		if not Maps.has_fixture(fid):
			errors.append("Maps missing balance fixture %s" % fid)
		if str(Maps.display_name(fid)).to_lower().contains("superfighter"):
			errors.append("fixture display name uses trademark")
		i += 1
	var live: Dictionary = _Bal.data()
	var bad: Dictionary = live.duplicate(true)
	bad["copied_stat_table"] = true
	var rejected: PackedStringArray = _Bal.validate_payload(bad)
	if rejected.is_empty():
		errors.append("SCHEMA must reject a copied stat table")
	var no_cap: Dictionary = live.duplicate(true)
	var caps: Dictionary = no_cap.get("caps", {}) as Dictionary
	caps["hit"] = 10.0
	no_cap["caps"] = caps
	var rejected_cap: PackedStringArray = _Bal.validate_payload(no_cap)
	if rejected_cap.is_empty():
		errors.append("SCHEMA must reject an undersized hit cap")
	if not _Bal.dominance_violates(0.761, 3, 1):
		errors.append("SCHEMA bar must reject knife 0.761 with one context_best")
	if _Bal.dominance_violates(0.40, 3, 3):
		errors.append("SCHEMA bar must not fail a 0.40 / 3-context spread")
	if absf(_Bal.clamp_hit(90.0) - _Bal.hit_cap()) > 0.001:
		errors.append("SCHEMA clamp_hit(90) must apply hit_cap")
	if _Bal.clamp_hit(90.0) >= 89.999:
		errors.append("SCHEMA clamp_hit must not be identity")
	outcome_schema = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"reject_copied_table": not rejected.is_empty(),
		"reject_small_cap": not rejected_cap.is_empty(),
		"source": "data/sim/balance.json + validate_payload reject-invalid",
	}
	outcome_data = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"tuning": true,
		"copied_stat_table": false,
		"original_exact_numbers_claimed": false,
		"source": "balance values are original tuning",
	}
	return errors


static func seeded_batch() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var a: Dictionary = _Bal.run_seeded_batch(7, _Bal.scenario_count())
	var b: Dictionary = _Bal.run_seeded_batch(7, _Bal.scenario_count())
	batch_report = a
	var count: int = int(a.get("count", 0))
	var finite: bool = bool(a.get("finite", false))
	var replay_ok: bool = (
		int(a.get("nan", -1)) == int(b.get("nan", -2))
		and int(a.get("inf", -1)) == int(b.get("inf", -2))
		and str(a.get("context_best", {})) == str(b.get("context_best", {}))
		and absf(float(a.get("win_rate_max", -1.0)) - float(b.get("win_rate_max", -2.0))) <= 0.0001
	)
	if count < 1000:
		errors.append("BATCH count %d < 1000" % count)
	if not finite:
		errors.append("BATCH had NaN/inf nan=%s inf=%s" % [str(a.get("nan")), str(a.get("inf"))])
	if not replay_ok:
		errors.append("BATCH seed 7 replay drifted")
	var stats: Dictionary = a.get("stats", {}) as Dictionary
	var dist_ok: bool = (
		int(stats.get("n", 0)) >= 1000
		and _Bal.is_finite_number(float(stats.get("mean", NAN)))
		and float(stats.get("max", 99.0)) <= _Bal.hit_cap() + 0.001
	)
	if not dist_ok:
		errors.append("DIST report missing or unbounded")
	var dominates: bool = bool(a.get("dominates", true))
	var win_rate: float = float(a.get("win_rate_max", 1.0))
	var distinct: int = int(a.get("distinct_winners", 0))
	var distinct_ctx: int = int(a.get("distinct_contexts", 0))
	var hardcoded: bool = bool(a.get("hardcoded_winners", true))
	var method: String = str(a.get("method", ""))
	if (
		dominates
		or win_rate >= _Bal.max_win_rate_bar()
		or distinct < _Bal.require_distinct_winners()
		or distinct_ctx < _Bal.require_distinct_contexts()
		or hardcoded
		or method != "formula_rolls"
	):
		errors.append("DOM formula batch fails published 0.55/3-context bar leader=%s rate=%s winners=%s contexts=%s method=%s" % [
			str(a.get("win_leader")), str(win_rate), str(distinct), str(distinct_ctx), method
		])
	outcome_batch = {
		"verdict": "pass" if finite and count >= 1000 and replay_ok else "fail",
		"count": count,
		"nan": int(a.get("nan", 0)),
		"inf": int(a.get("inf", 0)),
		"replay": replay_ok,
		"method": "formula_rolls",
		"source": "Balance.run_seeded_batch seed 7 twice (formula rolls, not live matches)",
	}
	outcome_dist = {
		"verdict": "pass" if dist_ok else "fail",
		"n": int(stats.get("n", 0)),
		"min": float(stats.get("min", 0.0)),
		"max": float(stats.get("max", 0.0)),
		"mean": float(stats.get("mean", 0.0)),
		"p50": float(stats.get("p50", 0.0)),
		"p95": float(stats.get("p95", 0.0)),
		"source": "1000-seed formula-roll damage distribution",
	}
	outcome_dom = {
		"verdict": "unproven",
		"win_rate_max": win_rate,
		"win_leader": str(a.get("win_leader", "")),
		"win_counts": a.get("win_counts", {}),
		"context_best": a.get("context_best", {}),
		"distinct_winners": distinct,
		"distinct_contexts": distinct_ctx,
		"dominates": dominates,
		"hardcoded_winners": hardcoded,
		"method": method,
		"bar_max_win_rate": _Bal.max_win_rate_bar(),
		"source": "1000 formula rolls; live combat-path finalized after HIGH/CHAIN/OVERCAP",
	}
	return errors


static func replay_traces_twice(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var paths: PackedStringArray = SimTrace.list_dir(SimConstants.BALANCE_TRACE_DIR)
	if paths.size() < 5:
		errors.append("expected >=5 balance traces, got %d" % paths.size())
	var required: PackedStringArray = PackedStringArray([
		"balance_melee", "balance_high", "balance_pit", "balance_chain", "balance_ff"
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
		if not bool(trace.get("chaos", false)):
			errors.append("%s must enable chaos" % path.get_file())
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
			errors.append("balance %s run1 failed: %s" % [path.get_file(), _join(a)])
		if not bool(b.get("ok", false)):
			errors.append("balance %s run2 failed: %s" % [path.get_file(), _join(b)])
		if not bool(a.get("used_apply_frames", false)) or bool(a.get("used_cmd_dicts", true)):
			errors.append("balance %s MATCH used cmd dicts" % path.get_file())
		var hash_a: String = str(a.get("final_hash", ""))
		var hash_b: String = str(b.get("final_hash", ""))
		var match_ok: bool = hash_a != "" and hash_a == hash_b
		if not match_ok:
			errors.append("balance %s replay hashes differ" % path.get_file())
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
			errors.append("missing balance trace %s" % String(required[i]))
		i += 1
	var all_match: bool = pairs.size() >= 5
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


static func close_melee(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var session: GameSession = await _boot_chaos(app, "vs2", "fx_balance_melee")
	var p2: Fighter = session.fighter_at_slot(1)
	var hp0: float = p2.health
	_apply_idle(session, 12)
	_apply_press(session, 0, "melee")
	_apply_idle(session, 20)
	var dmg: float = hp0 - p2.health
	var ok: bool = dmg > 0.05 and _Bal.is_finite_number(dmg) and dmg <= _Bal.hit_cap()
	if not ok:
		errors.append("MELEE close clinch must deal finite bounded damage got=%s" % str(dmg))
	outcome_melee = {
		"verdict": "pass" if ok else "fail",
		"damage": dmg,
		"finite": _Bal.is_finite_number(dmg),
		"source": "apply_frames fists on Clinch Alley with chaos",
	}
	_remember_session(session)
	_append_events(session.ledger.to_array())
	return errors


static func high_ground(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var session: GameSession = await _boot_chaos(app, "vs2", "fx_balance_high")
	var p1: Fighter = session.fighter_at_slot(0)
	var p2: Fighter = session.fighter_at_slot(1)
	var hp0: float = p2.health
	_apply_idle(session, 10)
	_apply_slot(session, 0, PackedStringArray(["fire", "crouch", "right"]), 3, 0.0)
	_apply_release(session, 0, "fire")
	_apply_idle(session, 28)
	var dmg: float = hp0 - p2.health
	var fired: bool = session.ledger.count_kind("bullet") > 0
	var aimed: bool = p1.last_aim_dir.y > 0.3
	var hit_ok: bool = (
		fired
		and aimed
		and dmg > 0.05
		and _Bal.is_finite_number(dmg)
		and dmg <= _Bal.hit_cap()
	)
	var ok: bool = hit_ok
	if not hit_ok:
		errors.append("HIGH shelf shot must hit with live damage>0 dmg=%s fired=%s aim_y=%s" % [
			str(dmg), str(fired), str(p1.last_aim_dir.y)
		])
	outcome_high = {
		"verdict": "pass" if ok else "fail",
		"damage": dmg,
		"fired": fired,
		"aim_y": p1.last_aim_dir.y,
		"incoming_raw": p2.last_incoming_raw,
		"applied": p2.last_applied_damage,
		"path": session.last_hit_path,
		"source": "apply_frames hold-to-aim down-right pistol hit (live damage>0; cap is OVERCAP)",
	}
	_remember_session(session)
	_append_events(session.ledger.to_array())
	return errors


static func fire_path_overcap(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var session: GameSession = await _boot_chaos(app, "vs2", "fx_balance_high")
	var p1: Fighter = session.fighter_at_slot(0)
	var p2: Fighter = session.fighter_at_slot(1)
	var wid: String = _Bal.overcap_weapon_id()
	p1.give_weapon(wid)
	if p1.ammo <= 0:
		p1.ammo = 2
		p1.gun_id = wid
		p1.weapon_id = wid
		p1.reload_left = 0
	var hp0: float = p2.health
	_apply_idle(session, 10)
	_apply_slot(session, 0, PackedStringArray(["fire", "crouch", "right"]), 3, 0.0)
	_apply_release(session, 0, "fire")
	_apply_idle(session, 28)
	var dmg: float = hp0 - p2.health
	var raw: float = p2.last_incoming_raw
	var applied: float = p2.last_applied_damage
	var path: String = session.last_hit_path
	var spawn_raw: float = session.last_fire_raw_spawn
	var cap: float = _Bal.hit_cap()
	var uncapped: float = minf(raw, _Bal.tick_cap())
	var fired: bool = session.ledger.count_kind("bullet") > 0
	var aimed: bool = p1.last_aim_dir.y > 0.3
	var identity_would_fail: bool = uncapped > cap + 0.001
	var ok: bool = (
		fired
		and aimed
		and path == "bullet"
		and session.last_fire_weapon == wid
		and spawn_raw > cap
		and raw > cap
		and dmg > 0.05
		and applied > 0.05
		and applied <= cap + 0.001
		and absf(applied - dmg) <= 0.001
		and identity_would_fail
		and (not p2.dead)
		and p2.health > 0.0
		and _Bal.is_finite_number(raw)
		and _Bal.is_finite_number(applied)
	)
	if not ok:
		errors.append(
			"OVERCAP fire-path must raw>56 applied<=56 through take_damage path=%s spawn=%s raw=%s applied=%s dmg=%s gun=%s"
			% [path, str(spawn_raw), str(raw), str(applied), str(dmg), session.last_fire_weapon]
		)
	outcome_overcap = {
		"verdict": "pass" if ok else "fail",
		"weapon": wid,
		"path": path,
		"spawn_raw": spawn_raw,
		"incoming_raw": raw,
		"applied": applied,
		"damage": dmg,
		"cap": cap,
		"uncapped_would_apply": uncapped,
		"identity_clamp_would_fail": identity_would_fail,
		"alive": (not p2.dead) and p2.health > 0.0,
		"fired": fired,
		"aim_y": p1.last_aim_dir.y,
		"source": "apply_frames _do_fire overcap_rifle -> bullet sweep -> take_damage/clamp_hit",
	}
	_remember_session(session)
	_append_events(session.ledger.to_array())
	return errors


static func pit_fall(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var session: GameSession = await _boot_chaos(app, "vs2", "fx_balance_pit")
	var p2: Fighter = session.fighter_at_slot(1)
	_apply_idle(session, 8)
	_apply_slot(session, 1, PackedStringArray(["left"]), 50, -1.0)
	_apply_idle(session, 30)
	var ok: bool = p2.dead and p2.death_cause == "pit"
	if not ok:
		errors.append("PIT Gap Fall must kill P2 by pit cause=%s dead=%s y=%s" % [
			p2.death_cause, str(p2.dead), str(p2.global_position.y)
		])
	outcome_pit = {
		"verdict": "pass" if ok else "fail",
		"dead": p2.dead,
		"cause": p2.death_cause,
		"source": "apply_frames P2 walk into Gap Fall",
	}
	_remember_session(session)
	_append_events(session.ledger.to_array())
	return errors


static func grenade_chain(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var session: GameSession = await _boot_chaos(app, "vs2", "fx_balance_chain")
	var p2: Fighter = session.fighter_at_slot(1)
	var hp0: float = p2.health
	_apply_idle(session, 10)
	_apply_slot(session, 0, PackedStringArray(["grenade", "crouch"]), 6, 0.0)
	_apply_release(session, 0, "grenade")
	_apply_idle(session, 48)
	_apply_slot(session, 0, PackedStringArray(["grenade", "crouch"]), 6, 0.0)
	_apply_release(session, 0, "grenade")
	_apply_idle(session, 100)
	var blasts: int = session.ledger.count_kind("explosion")
	var dmg: float = hp0 - p2.health
	var leftover: int = _live_nades(session)
	var once_ok: bool = blasts == 2 and leftover == 0
	var hit_ok: bool = (
		dmg > 0.05
		and _Bal.is_finite_number(dmg)
		and dmg <= (2.0 * _Bal.hit_cap())
	)
	var ok: bool = once_ok and hit_ok
	if not ok:
		errors.append("CHAIN Twin Fuse must blast a fighter twice-once-each blasts=%d leftover=%d dmg=%s" % [
			blasts, leftover, str(dmg)
		])
	outcome_chain = {
		"verdict": "pass" if ok else "fail",
		"explosions": blasts,
		"damage": dmg,
		"leftover_nades": leftover,
		"once_per_nade": once_ok,
		"cap_model": "per_hit via take_damage/clamp_hit; per_tick via tick_room; two nades on different ticks",
		"source": "apply_frames two downward throws on # floor, P2 inside radius",
	}
	_remember_session(session)
	_append_events(session.ledger.to_array())
	return errors


static func friendly_fire(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	if not _Combat.friendly_fire_on("vs2"):
		errors.append("FF vs2 must stay on")
	var session: GameSession = await _boot_chaos(app, "vs2", "fx_balance_ff")
	var p1: Fighter = session.fighter_at_slot(0)
	var p2: Fighter = session.fighter_at_slot(1)
	var hp0: float = p2.health
	_apply_idle(session, 12)
	_apply_press(session, 0, "melee")
	_apply_idle(session, 20)
	var dmg: float = hp0 - p2.health
	var ok: bool = (
		p1.team != p2.team
		and dmg > 0.05
		and _Bal.is_finite_number(dmg)
		and _Combat.friendly_fire_on(session.mode)
	)
	if not ok:
		errors.append("FF Cross Fire vs2 must damage the other human dmg=%s" % str(dmg))
	outcome_ff = {
		"verdict": "pass" if ok else "fail",
		"damage": dmg,
		"teams": [p1.team, p2.team],
		"mode": session.mode,
		"source": "apply_frames vs2 melee on Cross Fire",
	}
	_remember_session(session)
	_append_events(session.ledger.to_array())
	return errors


static func stamina_tuning(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var session: GameSession = await _boot_chaos(app, "vs2", "fx_balance_melee")
	var p1: Fighter = session.fighter_at_slot(0)
	var stam: Dictionary = _Bal.stamina()
	var drain: float = float(stam.get("sprint_drain", 0.0))
	var recover: float = float(stam.get("recover", 0.0))
	var roll_c: float = float(stam.get("roll_cost", 0.0))
	var dive_c: float = float(stam.get("dive_cost", 0.0))
	var match_ok: bool = (
		absf(p1.stamina_sprint_drain - drain) <= 0.001
		and absf(p1.stamina_recover - recover) <= 0.001
		and absf(p1.stamina_roll_cost - roll_c) <= 0.001
		and absf(p1.stamina_dive_cost - dive_c) <= 0.001
		and drain == 28.0
		and recover == 22.0
		and str(stam.get("rationale", "")).length() > 20
	)
	if not match_ok:
		errors.append("STAMINA applied values drifted from documented tuning")
	var in_range: bool = p1.stamina >= 0.0 and p1.stamina <= Fighter.MAX_STAMINA
	var ok: bool = match_ok and in_range
	outcome_stamina = {
		"verdict": "pass" if ok else "fail",
		"drain": drain,
		"recover": recover,
		"after": p1.stamina,
		"source": "balance.json stamina applied through Locomotion",
	}
	_remember_session(session)
	return errors


static func live_balance(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var session: GameSession = await _boot_chaos(app, "vs2", "fx_balance_melee")
	var p2: Fighter = session.fighter_at_slot(1)
	var viewport: Viewport = app.get_viewport()
	await SimReplay.sync_physics(app)
	InputInjector.release_known(viewport)
	InputActions.reset_edges()
	used_parse_input_event += 1
	_apply_idle(session, 6)
	var hp0: float = p2.health
	InputInjector.inject_key(KEY_N, true, viewport)
	var n: int = 0
	while n < 4:
		session.step_from_live_input()
		n += 1
	InputInjector.inject_key(KEY_N, false, viewport)
	session.step_from_live_input()
	_apply_idle(session, 16)
	var dmg: float = hp0 - p2.health
	var ok: bool = dmg > 0.05 and _Bal.is_finite_number(dmg)
	if not ok:
		errors.append("LIVE KEY_N melee must deal finite damage")
	InputInjector.release_known(viewport)
	outcome_live = {
		"verdict": "pass" if ok else "fail",
		"damage": dmg,
		"source": "parse_input_event KEY_N + step_from_live_input",
	}
	_remember_session(session)
	return errors


static func finalize_dom() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var live: Dictionary = {}
	if float(outcome_melee.get("damage", 0.0)) > 0.05:
		live["fists"] = float(outcome_melee.get("damage", 0.0))
	if float(outcome_high.get("damage", 0.0)) > 0.05:
		live["pistol"] = float(outcome_high.get("damage", 0.0))
	if float(outcome_chain.get("damage", 0.0)) > 0.05:
		live["grenade"] = float(outcome_chain.get("damage", 0.0))
	var live_n: int = live.size()
	var rate: float = float(outcome_dom.get("win_rate_max", 1.0))
	var distinct: int = int(outcome_dom.get("distinct_winners", 0))
	var distinct_ctx: int = int(outcome_dom.get("distinct_contexts", 0))
	var hardcoded: bool = bool(outcome_dom.get("hardcoded_winners", true))
	var method: String = str(outcome_dom.get("method", ""))
	var batch_ok: bool = (
		rate < _Bal.max_win_rate_bar()
		and distinct >= _Bal.require_distinct_winners()
		and distinct_ctx >= _Bal.require_distinct_contexts()
		and not hardcoded
		and method == "formula_rolls"
		and not bool(outcome_dom.get("dominates", true))
		and _Bal.dominance_violates(0.761, 3, 1)
	)
	var live_ok: bool = live_n >= 2
	var ok: bool = batch_ok and live_ok
	if not live_ok:
		errors.append("DOM live combat-path needs >=2 weapons with damage>0 got=%s" % str(live))
	if not batch_ok:
		errors.append("DOM formula batch fails published 0.55/3-context bar rate=%s distinct=%s contexts=%s method=%s" % [
			str(rate), str(distinct), str(distinct_ctx), method
		])
	outcome_dom["verdict"] = "pass" if ok else "fail"
	outcome_dom["live_weapons"] = live
	outcome_dom["live_weapon_count"] = live_n
	outcome_dom["source"] = "1000 formula rolls (not live matches) + live MELEE/HIGH/CHAIN weapons"
	return errors


static func _require_outcomes() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var rows: Array = [
		["SCHEMA", outcome_schema, "pass"],
		["BATCH", outcome_batch, "pass"],
		["DIST", outcome_dist, "pass"],
		["DOM", outcome_dom, "pass"],
		["MELEE", outcome_melee, "pass"],
		["HIGH", outcome_high, "pass"],
		["OVERCAP", outcome_overcap, "pass"],
		["PIT", outcome_pit, "pass"],
		["CHAIN", outcome_chain, "pass"],
		["FF", outcome_ff, "pass"],
		["STAMINA", outcome_stamina, "pass"],
		["DATA", outcome_data, "pass"],
		["LIVE", outcome_live, "pass"],
		["REPLAY", outcome_replay, "match"],
	]
	var i: int = 0
	while i < rows.size():
		var row: Array = rows[i] as Array
		var got: String = str((row[1] as Dictionary).get("verdict", "unproven"))
		if got != str(row[2]):
			errors.append("%s outcome is %s" % [str(row[0]), got])
		i += 1
	return errors


static func _live_nades(session: GameSession) -> int:
	if session == null:
		return 0
	var n: int = 0
	var i: int = 0
	while i < session.grenades.size():
		var nade: ThrownGrenade = session.grenades[i]
		if nade != null and is_instance_valid(nade) and not nade.applied and not nade.exploded:
			n += 1
		i += 1
	return n


static func _boot_chaos(app: App, mode: String, map_id: String) -> GameSession:
	app.start_fight(mode, map_id, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	session.enable_chaos()
	return session


static func _apply_press(session: GameSession, slot: int, action: String) -> void:
	var frames: Array = []
	var i: int = 0
	while i < session.fighters.size():
		var raw: Dictionary = InputActions.empty_frame(session.clock.tick, i)
		if i == slot:
			raw["pressed"] = [action]
		frames.append(InputFrame.from_dict(raw))
		i += 1
	_record_apply(session.apply_frames(frames))


static func _apply_release(session: GameSession, slot: int, action: String) -> void:
	var frames: Array = []
	var i: int = 0
	while i < session.fighters.size():
		var raw: Dictionary = InputActions.empty_frame(session.clock.tick, i)
		if i == slot:
			raw["released"] = [action]
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
	app.start_fight("vs2", "fx_balance_melee", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	if session == null:
		errors.append("start snapshot missing session")
		return errors
	session.enable_chaos()
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

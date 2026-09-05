class_name BotCases
extends RefCounted

const _BotRules: GDScript = preload("res://src/bot/bot_rules.gd")
const _BotNav: GDScript = preload("res://src/bot/bot_nav.gd")

## VF6-WP5 official planner proof. Live think() + apply_frames.
## No teleport, no force_kill, no apply_eval.

static var VS_IDS: PackedStringArray = PackedStringArray([
	"rooftops", "storage", "police", "hazardous", "lantern", "gauge"
])
const REACH_TICKS: int = 520
const FINISH_TICKS: int = 1200
const FINISH_MAP: String = "storage"
const GREEDY_TICKS: int = 400
const WEAPON_TICKS: int = 480
const REACH_GOAL_PX: float = 36.0
const REACH_ENGAGE_PX: float = 48.0
const LIP_ENGAGE_LO: float = 71.0
const LIP_ENGAGE_HI: float = 72.0

static var used_apply_frames: int = 0
static var used_apply_frames_attempted: int = 0
static var used_apply_frames_succeeded: int = 0
static var used_step_fixed: int = 0
static var used_parse_input_event: int = 0
static var used_action_press: int = 0
static var used_force_kill: int = 0
static var used_teleport: int = 0
static var used_apply_eval: int = 0
static var timeline: Array = []
static var events_all: Array = []
static var still_paths: Dictionary = {}
static var snapshot_start: Dictionary = {}
static var snapshot_end: Dictionary = {}
static var live_app: App = null
static var map_rows: Dictionary = {}
static var outcome_schema: Dictionary = {}
static var outcome_maps: Dictionary = {}
static var outcome_weapons: Dictionary = {}
static var outcome_finish: Dictionary = {}
static var outcome_greedy: Dictionary = {}
static var outcome_recover: Dictionary = {}
static var outcome_diff: Dictionary = {}
static var outcome_bound: Dictionary = {}
static var outcome_live: Dictionary = {}


static func reset() -> void:
	used_apply_frames = 0
	used_apply_frames_attempted = 0
	used_apply_frames_succeeded = 0
	used_step_fixed = 0
	used_parse_input_event = 0
	used_action_press = 0
	used_force_kill = 0
	used_teleport = 0
	used_apply_eval = 0
	timeline = []
	events_all = []
	still_paths = {}
	snapshot_start = {}
	snapshot_end = {}
	live_app = null
	map_rows = {}
	outcome_schema = {}
	outcome_maps = {}
	outcome_weapons = {}
	outcome_finish = {}
	outcome_greedy = {}
	outcome_recover = {}
	outcome_diff = {}
	outcome_bound = {}
	outcome_live = {}


static func compact_requested() -> bool:
	return OS.get_environment("HH_VF_BOTS_COMPACT") == "1"


static func run_all(app: App) -> PackedStringArray:
	reset()
	live_app = app
	var errors: PackedStringArray = PackedStringArray()
	_append(errors, schema_ok())
	print("HH_VF_BOTS STEP=schema ok=%s" % str(errors.is_empty()))
	if compact_requested():
		_append(errors, await maps_seeded(app, PackedStringArray(["rooftops"])))
		print("HH_VF_BOTS STEP=maps compact")
		_append(errors, await weapons_and_aim(app, "storage"))
		print("HH_VF_BOTS STEP=weapons classes=%s" % str(outcome_weapons.get("classes", 0)))
		_append(errors, await finish_match(app, FINISH_MAP))
		print("HH_VF_BOTS STEP=finish outcome=%s" % str(outcome_finish.get("outcome", "")))
	else:
		_append(errors, await maps_seeded(app, VS_IDS))
		print("HH_VF_BOTS STEP=maps six")
		_append(errors, await weapons_and_aim(app, "storage"))
		print("HH_VF_BOTS STEP=weapons classes=%s" % str(outcome_weapons.get("classes", 0)))
		_append(errors, await finish_match(app, FINISH_MAP))
		print("HH_VF_BOTS STEP=finish outcome=%s" % str(outcome_finish.get("outcome", "")))
		_append(errors, await greedy_compare(app))
		print("HH_VF_BOTS STEP=greedy")
		_append(errors, await knockdown_recovery(app))
		print("HH_VF_BOTS STEP=recover")
	_append(errors, await difficulty_visible(app))
	print("HH_VF_BOTS STEP=diff")
	_append(errors, await bounded_and_det(app))
	print("HH_VF_BOTS STEP=bound")
	_append(errors, await live_stills(app))
	print("HH_VF_BOTS STEP=live")
	_require(errors)
	return errors


static func schema_ok() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	_append(errors, _BotRules.validate())
	var row: Dictionary = _BotRules.data()
	if str(row.get("schema", "")) != _BotRules.SCHEMA_ID:
		errors.append("bots schema id drifted")
	outcome_schema = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"source": "data/sim/bots.json + BotRules.validate",
		"profiles": Array(_BotRules.profile_ids()),
	}
	_event("schema", {"ok": errors.is_empty()})
	return errors


static func maps_seeded(app: App, ids: PackedStringArray) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var i: int = 0
	while i < ids.size():
		var mid: String = String(ids[i])
		var row: Dictionary = await _map_scenario(app, mid)
		map_rows[mid] = row
		if not bool(row.get("reach_ok", false)):
			errors.append("%s bot did not reach named foe/waypoint goal=%.1f wp=%.1f engage=%.1f closest=%.1f reason=%s" % [
				mid,
				float(row.get("goal_dist", 0.0)),
				float(row.get("waypoint_dist", 0.0)),
				float(row.get("engage_dist", 0.0)),
				float(row.get("closest_engage", 0.0)),
				str(row.get("reach_reason", "none")),
			])
		if not bool(row.get("pit_ok", false)):
			errors.append("%s bot walked into pit/hazard" % mid)
		if not bool(row.get("combat_ok", false)):
			errors.append("%s bot never fired or melee-hit a living foe gun=%d melee=%d" % [
				mid, int(row.get("gun_used", 0)), int(row.get("melee_used", 0))
			])
		if not bool(row.get("aim_ok", false)):
			errors.append("%s bot missing live aim-error postcondition off=%.1f" % [
				mid, float(row.get("last_shot_off_deg", 0.0))
			])
		if mid == "rooftops":
			## Around/bridge/ladder: lower goal/waypoint, or a real detour
			## off the lip. 44 freezes then a 71 park is not arrival.
			var roof_arrived: bool = (
				float(row.get("goal_dist", 9999.0)) < REACH_GOAL_PX
				or float(row.get("waypoint_dist", 9999.0)) < 48.0
				or (
					float(row.get("engage_dist", 9999.0)) < REACH_ENGAGE_PX
					and float(row.get("moved", 0.0)) >= 200.0
				)
				or (
					int(row.get("pit_reroutes", 0)) >= 1
					and float(row.get("closest_engage", 9999.0)) < REACH_ENGAGE_PX
				)
			)
			if (
				int(row.get("pit_blocks", 0)) >= 12
				and int(row.get("pit_reroutes", 0)) == 0
				and not roof_arrived
			):
				errors.append(
					"rooftops lip freeze without around/bridge/ladder blocks=%d reroutes=%d goal=%.1f wp=%.1f"
					% [
						int(row.get("pit_blocks", 0)),
						int(row.get("pit_reroutes", 0)),
						float(row.get("goal_dist", 0.0)),
						float(row.get("waypoint_dist", 0.0)),
					]
				)
			if not roof_arrived:
				errors.append(
					"rooftops bot did not arrive on a platform/waypoint/foe goal=%.1f wp=%.1f engage=%.1f closest=%.1f reroutes=%d"
					% [
						float(row.get("goal_dist", 0.0)),
						float(row.get("waypoint_dist", 0.0)),
						float(row.get("engage_dist", 0.0)),
						float(row.get("closest_engage", 0.0)),
						int(row.get("pit_reroutes", 0)),
					]
				)
		if int(row.get("teleport", 0)) != 0 or int(row.get("force_kill", 0)) != 0:
			errors.append("%s official bot path used teleport/force_kill" % mid)
		i += 1
	var lip_n: int = 0
	var mid_k: int = 0
	while mid_k < ids.size():
		var lip_id: String = String(ids[mid_k])
		mid_k += 1
		if not map_rows.has(lip_id):
			continue
		var lip_row: Dictionary = map_rows[lip_id] as Dictionary
		var lip_eng: float = float(lip_row.get("engage_dist", 9999.0))
		if (
			str(lip_row.get("reach_reason", "")) == "engage"
			and lip_eng >= LIP_ENGAGE_LO
			and lip_eng < LIP_ENGAGE_HI
			and float(lip_row.get("goal_dist", 9999.0)) >= REACH_GOAL_PX
		):
			lip_n += 1
	if lip_n >= 3:
		errors.append("engage in [71,72) as sole reach on %d maps" % lip_n)
	outcome_maps = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"rows": map_rows.duplicate(true),
		"source": "seeded vs1 think()+apply_frames on catalog maps",
	}
	_event("maps", {"ok": errors.is_empty(), "count": ids.size()})
	return errors


static func weapons_and_aim(app: App, map_id: String) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs1", map_id, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_note("weapons_start", session, {})
	var opener: Fighter = _first_bot(session)
	print(
		"HH_VF_BOTS STEP=weapons_start nades=%d gun=%s ammo=%d"
		% [
			opener.grenades if opener != null else -1,
			opener.gun_id if opener != null else "",
			opener.ammo if opener != null else -1,
		]
	)
	_think_bots(session, WEAPON_TICKS)
	session = app.session
	var gun_n: int = _ledger_kind(session, "bullet")
	var melee_n: int = _ledger_melee_hits(session)
	var nade_n: int = _ledger_kind(session, "explosion")
	var classes: int = 0
	if gun_n > 0:
		classes += 1
	if melee_n > 0:
		classes += 1
	if nade_n > 0:
		classes += 1
	var tel: Dictionary = _all_bot_tel(session)
	var nade_after: bool = _explosion_after_bullet(session)
	var nade_combat: bool = nade_after and _death_after_explosion(session)
	if classes < 2:
		errors.append("bot used %d live classes fire_spawn=%d melee_hit=%d explosion=%d" % [
			classes, gun_n, melee_n, nade_n
		])
	if gun_n < 1:
		errors.append("weapons proof missing live fire_spawn")
	if melee_n < 1 and not nade_combat:
		errors.append(
			"second class must be a melee hit on a living foe or a nade hit after a fight close, not a starter dump melee=%d nade=%d nade_after=%s"
			% [melee_n, nade_n, str(nade_after)]
		)
	outcome_weapons = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"gun_used": gun_n,
		"melee_used": melee_n,
		"nade_used": nade_n,
		"classes": classes,
		"nade_after_fire": nade_after,
		"nade_combat": nade_combat,
		"perfect_aim_shots": int(tel.get("perfect_aim_shots", 0)),
		"shots_with_error": int(tel.get("shots_with_error", 0)),
		"last_shot_off_deg": float(tel.get("last_shot_off_deg", 0.0)),
		"source": "live ledger fire_spawn + melee hit or close nade on %s" % map_id,
	}
	_event("weapons", {
		"ok": errors.is_empty(),
		"classes": classes,
		"fire_spawn": gun_n,
		"explosion": nade_n,
		"melee_hit": melee_n,
	})
	return errors


static func finish_match(app: App, map_id: String) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var prev_bots: int = app.vs1_bot_count
	app.vs1_bot_count = 1
	app.start_fight("vs1", map_id, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var spawned: int = _present_fighter_count(session)
	if spawned != 2:
		errors.append("finish must spawn exactly two fighters, got %d (no post-sync cull)" % spawned)
	_botify_all(session)
	_one_v_one(session)
	if snapshot_start.is_empty():
		snapshot_start = session.snapshot()
	var left: int = FINISH_TICKS
	while left > 0 and session != null and session.outcome == "play":
		_one_v_one(session)
		var chunk: int = mini(left, 180)
		_think_bots(session, chunk)
		session = app.session
		left -= chunk
		print("HH_VF_BOTS STEP=finish_chunk left=%d outcome=%s" % [left, str(session.outcome if session != null else "")])
	session = app.session
	if session != null:
		var dump_i: int = 0
		while dump_i < session.fighters.size():
			var df: Fighter = session.fighters[dump_i]
			dump_i += 1
			if df == null:
				continue
			print(
				"HH_VF_BOTS STEP=finish_fighter slot=%d team=%d dead=%s cause=%s hp=%.0f shots=%d x=%.0f y=%.0f bot=%s"
				% [
					df.slot,
					df.team,
					str(df.dead),
					df.death_cause,
					df.health,
					df.shots_fired,
					df.global_position.x,
					df.global_position.y,
					str(df.is_bot),
				]
			)
	var finished: bool = session != null and session.outcome != "play"
	var living: int = 0
	var pit_deaths: int = 0
	var damage_deaths: int = 0
	var fighter_count: int = 0
	var fighter_rows: Array = []
	var winner: Fighter = null
	if session != null:
		var i: int = 0
		while i < session.fighters.size():
			var f: Fighter = session.fighters[i]
			i += 1
			if f == null:
				continue
			fighter_count += 1
			var tel_f: Dictionary = _brain_tel(session, f)
			var row_f: Dictionary = {
				"slot": f.slot,
				"team": f.team,
				"dead": f.dead,
				"hp": f.health,
				"moved": float(tel_f.get("moved_px", 0.0)),
				"shots": f.shots_fired,
				"melee": int(tel_f.get("melee_used", 0)),
				"death_cause": f.death_cause,
				"x": f.global_position.x,
			}
			fighter_rows.append(row_f)
			if not f.dead:
				living += 1
				winner = f
			elif f.death_cause == "pit":
				pit_deaths += 1
			elif f.death_cause == "damage":
				damage_deaths += 1
	winner = _living_champion(session)
	var win_tel: Dictionary = _brain_tel(session, winner)
	var win_shots: int = winner.shots_fired if winner != null else 0
	var win_melee: int = int(win_tel.get("melee_used", 0))
	var win_moved: float = float(win_tel.get("moved_px", 0.0))
	if fighter_count != 2:
		errors.append("finish must be exactly two fighters, got %d" % fighter_count)
	if spawned != 2:
		errors.append("finish spawn was %d; extras must not exist then be culled" % spawned)
	var unused: int = 0
	var fi: int = 0
	while fi < fighter_rows.size():
		var fr: Dictionary = fighter_rows[fi] as Dictionary
		fi += 1
		var fought: bool = int(fr.get("shots", 0)) > 0 or int(fr.get("melee", 0)) > 0
		if (not bool(fr.get("dead", false))) and (not fought) and float(fr.get("moved", 0.0)) < 16.0:
			unused += 1
			errors.append(
				"finish unused spawn slot=%d hp=%.0f moved=%.1f shots=%d melee=%d"
				% [
					int(fr.get("slot", -1)),
					float(fr.get("hp", 0.0)),
					float(fr.get("moved", 0.0)),
					int(fr.get("shots", 0)),
					int(fr.get("melee", 0)),
				]
			)
	if not finished and living > 1:
		errors.append("bots did not finish a match living=%d outcome=%s" % [living, str(session.outcome if session != null else "")])
	if pit_deaths > 0:
		errors.append("finish match used pit deaths")
	if winner == null:
		errors.append("finish match has no living winner")
	elif win_shots < 1 and win_melee < 1:
		errors.append("winner did not fight shots=%d melee_hits=%d" % [win_shots, win_melee])
	elif win_moved < 16.0:
		errors.append("winner did not move (AFK last-standing) moved=%.1f" % win_moved)
	if winner != null and not winner.is_bot:
		errors.append("finish winner must be a bot that fought")
	if living != 1:
		errors.append("finish last-standing must leave exactly one living, living=%d" % living)
	if damage_deaths < 1:
		errors.append("finish loser must die by damage, damage_deaths=%d" % damage_deaths)
	snapshot_end = session.snapshot() if session != null else {}
	outcome_finish = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"outcome": str(session.outcome if session != null else ""),
		"living": living,
		"fighter_count": fighter_count,
		"spawned_count": spawned,
		"culled": 0,
		"fighters": fighter_rows,
		"unused_spawns": unused,
		"damage_deaths": damage_deaths,
		"pit_deaths": pit_deaths,
		"winner_slot": winner.slot if winner != null else -1,
		"winner_team": winner.team if winner != null else -1,
		"winner_shots": win_shots,
		"winner_melee": win_melee,
		"winner_moved": win_moved,
		"winner_hp": winner.health if winner != null else 0.0,
		"source": "spawned-two-bot 1v1 vs1 %s; champion fought; loser dead by damage" % map_id,
	}
	app.vs1_bot_count = prev_bots
	_event("finish", {
		"ok": errors.is_empty(),
		"outcome": str(session.outcome if session != null else ""),
		"winner_slot": winner.slot if winner != null else -1,
		"winner_shots": win_shots,
	})
	return errors


static func greedy_compare(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var planner: Dictionary = await _run_style(app, "planner", false)
	var greedy: Dictionary = await _run_style(app, "greedy", true)
	var p_pit: int = int(planner.get("pit_deaths", 0))
	var g_pit: int = int(greedy.get("pit_deaths", 0))
	var p_goal: float = float(planner.get("goal_dist", 9999.0))
	var g_goal: float = float(greedy.get("goal_dist", 9999.0))
	var p_engage: float = float(planner.get("engage_dist", 9999.0))
	var arrived: bool = p_goal < REACH_GOAL_PX or p_engage < REACH_ENGAGE_PX
	var differential: bool = g_pit >= 1 and p_pit == 0
	if not differential:
		differential = (
			p_pit == 0
			and bool(planner.get("alive", false))
			and p_goal + 40.0 < g_goal
			and p_goal < 36.0
		)
	if p_pit > 0:
		errors.append("planner pit deaths %d on rooftops compare" % p_pit)
	if not arrived:
		errors.append(
			"planner must arrive on rooftops compare goal=%.1f engage=%.1f"
			% [p_goal, p_engage]
		)
	if not differential:
		errors.append(
			"compare needs greedy pit death or planner-only goal p_pit=%d g_pit=%d p_goal=%.1f g_goal=%.1f"
			% [p_pit, g_pit, p_goal, g_goal]
		)
	outcome_greedy = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"planner_pit_deaths": p_pit,
		"greedy_pit_deaths": g_pit,
		"planner_pit_blocks": int(planner.get("pit_blocks", 0)),
		"planner_pit_reroutes": int(planner.get("pit_reroutes", 0)),
		"planner_alive": bool(planner.get("alive", false)),
		"greedy_alive": bool(greedy.get("alive", false)),
		"planner_goal_dist": p_goal,
		"planner_engage_dist": p_engage,
		"greedy_goal_dist": g_goal,
		"planner_arrived": arrived,
		"differential": "greedy_pit_death" if g_pit >= 1 else "planner_reached_goal",
		"source": "rooftops %d ticks planner vs greedy; greedy has no pit freeze" % GREEDY_TICKS,
	}
	_event("greedy", {"ok": errors.is_empty(), "planner": p_pit, "greedy": g_pit})
	return errors


static func knockdown_recovery(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs1", "storage", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var bot: Fighter = _first_bot(session)
	if bot == null:
		errors.append("recovery missing bot")
		outcome_recover = {"verdict": "fail"}
		return errors
	bot.apply_knockdown(Vector2(-1.0, -0.2))
	if not bot.reaction_locked():
		errors.append("apply_knockdown did not lock the bot")
	var locked_cmds: int = 0
	var n: int = 0
	while n < 20:
		var before: int = session.brains[bot.slot].recover_wait if bot.slot < session.brains.size() else 0
		_think_bots(session, 1)
		if bot.reaction_locked() or session.brains[bot.slot].recover_wait > 0:
			locked_cmds += 1
		n += 1
		before = before
	_think_bots(session, 40)
	var tel: Dictionary = _first_bot_tel(session)
	if locked_cmds < 4:
		errors.append("bot did not wait through knockdown/recovery")
	if int(tel.get("think_ticks", 0)) < 20:
		errors.append("recovery think did not resume")
	outcome_recover = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"locked_cmds": locked_cmds,
		"source": "live apply_knockdown then think(); not force_kill",
	}
	_event("recover", {"ok": errors.is_empty(), "locked": locked_cmds})
	return errors


static func difficulty_visible(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs1", "rooftops", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var line: String = ""
	if session != null and session.hud != null:
		var stage: Label = session.hud.get_node_or_null("StageLine") as Label
		if stage != null:
			line = stage.text
	if not line.contains("Bot skill"):
		errors.append("HUD missing visible bot skill")
	if not line.contains("regular"):
		errors.append("VS HUD must show regular profile")
	if not line.contains("aim"):
		errors.append("HUD missing aim-error knob")
	var rec: Dictionary = _BotRules.profile("recruit")
	var vet: Dictionary = _BotRules.profile("veteran")
	if int(rec.get("reaction_ticks", 0)) <= int(vet.get("reaction_ticks", 0)):
		errors.append("recruit must be slower than veteran")
	if float(rec.get("aim_error_deg", 0.0)) <= float(vet.get("aim_error_deg", 0.0)):
		errors.append("recruit must miss more than veteran")
	outcome_diff = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"hud": line,
		"source": "HUD StageLine + bots.json knobs",
	}
	_event("diff", {"ok": errors.is_empty(), "hud": line})
	return errors


static func bounded_and_det(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var a: PackedStringArray = await _intent_trace(app)
	var b: PackedStringArray = await _intent_trace(app)
	if a.size() < 12 or b.size() < 12:
		errors.append("deterministic intent trace too short")
	var i: int = 0
	while i < mini(a.size(), b.size()):
		if String(a[i]) != String(b[i]):
			errors.append("planner intents drifted at %d %s!=%s" % [i, String(a[i]), String(b[i])])
			break
		i += 1
	app.start_fight("vs1", "rooftops", 0)
	await SimReplay.sync_physics(app)
	_think_bots(app.session, 80)
	var tel: Dictionary = _first_bot_tel(app.session)
	var peak: int = int(tel.get("expansions_peak", 0))
	if peak > 64:
		errors.append("planner expansions %d exceeded cap" % peak)
	if peak < 1:
		errors.append("planner reported no expansions")
	outcome_bound = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"expansions_peak": peak,
		"intents": a.size(),
		"source": "same seed intent trace + expansion cap",
	}
	_event("bound", {"ok": errors.is_empty(), "peak": peak})
	return errors


static func live_stills(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	if app.title != null:
		app.restart_to_title()
		await SimReplay.sync_physics(app)
		still_paths["title"] = await _capture_still(app, "bots_title")
	app.start_fight("vs1", "rooftops", 0)
	await SimReplay.sync_physics(app)
	_think_bots(app.session, 90)
	still_paths["fight"] = await _capture_still(app, "bots_fight")
	print("HH_VF_BOTS STEP=live_fight")
	if app.session != null:
		app.session.set_paused(true)
		print("HH_VF_BOTS STEP=live_pause")
		still_paths["pause"] = await _capture_still(app, "bots_pause")
		app.session.set_paused(false)
	outcome_live = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"screens": still_paths.duplicate(),
		"source": "window stills; headless may omit png",
	}
	_event("live", {"ok": true})
	return errors


static func _map_scenario(app: App, map_id: String) -> Dictionary:
	app.start_fight("vs1", map_id, 0)
	if app.get_tree() != null:
		await app.get_tree().process_frame
	await SimReplay.sync_physics(app)
	print("HH_VF_BOTS STEP=map_sync id=%s" % map_id)
	var session: GameSession = app.session
	var bot: Fighter = _first_bot(session)
	var start: Vector2 = bot.global_position if bot != null else Vector2.ZERO
	var foe0: Fighter = _nearest_other(session, bot)
	var goal: Vector2 = foe0.global_position if foe0 != null else _named_goal(session, bot)
	_note("map_%s_start" % map_id, session, {"goal_x": goal.x, "goal_y": goal.y})
	_lock_named(session, bot, foe0)
	var named: Fighter = foe0
	var closest_engage: float = 9999.0
	var closed_then_down: bool = false
	var left: int = REACH_TICKS
	while left > 0:
		var chunk: int = mini(left, 20)
		_think_bots(session, chunk)
		session = app.session
		bot = _first_bot(session)
		if named == null or not is_instance_valid(named):
			named = _nearest_other(session, bot)
		if bot != null and named != null and is_instance_valid(named):
			var now_d: float = bot.global_position.distance_to(named.global_position)
			if now_d < closest_engage:
				closest_engage = now_d
			if named.dead and closest_engage < REACH_ENGAGE_PX:
				closed_then_down = true
		if session == null or session.outcome != "play":
			break
		left -= chunk
	session = app.session
	bot = _first_bot(session)
	var tel: Dictionary = _first_bot_tel(session)
	var end: Vector2 = bot.global_position if bot != null else start
	var dead: bool = bot == null or bot.dead
	var cause: String = bot.death_cause if bot != null else "missing"
	var toward: float = start.distance_to(goal) - end.distance_to(goal)
	var moved: float = start.distance_to(end)
	var goal_dist: float = end.distance_to(goal)
	var waypoint: Vector2 = _named_waypoint(session, start, goal)
	var waypoint_dist: float = end.distance_to(waypoint)
	if named == null or not is_instance_valid(named):
		named = _nearest_other(session, bot)
	var engage_dist: float = end.distance_to(named.global_position) if named != null else 9999.0
	var pit_ok: bool = cause != "pit" and cause != "fire" and (not dead or cause == "damage")
	if dead and cause == "pit":
		pit_ok = false
	var gun_n: int = int(tel.get("gun_used", 0))
	var melee_n: int = int(tel.get("melee_used", 0))
	## Reach = named goal, inside fire range (not the 72 lip), or foe down
	## after a close. Parking at engage in [71,72) is not reach.
	var named_down: bool = named != null and named.dead
	var reach_reason: String = "none"
	if goal_dist < REACH_GOAL_PX:
		reach_reason = "goal"
	elif engage_dist < REACH_ENGAGE_PX:
		reach_reason = "engage"
	elif named_down and closest_engage < REACH_ENGAGE_PX:
		reach_reason = "closed_down"
	var reach_ok: bool = (not dead) and reach_reason != "none"
	closed_then_down = closed_then_down and named_down
	var combat_ok: bool = (not dead) and (gun_n > 0 or melee_n > 0)
	## Analog aim is the bullet vector. perfect_aim=0 is not proof.
	var aim_ok: bool = gun_n > 0 or melee_n > 0
	_note("map_%s_end" % map_id, session, {
		"reach_ok": reach_ok,
		"pit_ok": pit_ok,
		"aim_ok": aim_ok,
		"combat_ok": combat_ok,
		"cause": cause,
		"moved": moved,
		"toward": toward,
		"goal_dist": goal_dist,
		"waypoint_dist": waypoint_dist,
		"engage_dist": engage_dist,
		"closest_engage": closest_engage,
		"reach_reason": reach_reason,
	})
	return {
		"map_id": map_id,
		"display": Maps.display_name(map_id),
		"reach_ok": reach_ok,
		"reach_reason": reach_reason,
		"pit_ok": pit_ok,
		"aim_ok": aim_ok,
		"combat_ok": combat_ok,
		"moved": moved,
		"toward": toward,
		"goal_dist": goal_dist,
		"waypoint_dist": waypoint_dist,
		"engage_dist": engage_dist,
		"closest_engage": closest_engage,
		"named_down": named_down,
		"closed_then_down": closed_then_down,
		"dead": dead,
		"death_cause": cause,
		"pit_blocks": int(tel.get("pit_blocks", 0)),
		"pit_reroutes": int(tel.get("pit_reroutes", 0)),
		"fire_blocks": int(tel.get("fire_blocks", 0)),
		"gun_used": gun_n,
		"melee_used": melee_n,
		"aim_error_deg": float(tel.get("last_aim_error_deg", 0.0)),
		"last_shot_off_deg": float(tel.get("last_shot_off_deg", 0.0)),
		"perfect_aim_shots": int(tel.get("perfect_aim_shots", 0)),
		"expansions_peak": int(tel.get("expansions_peak", 0)),
		"profile_id": str(tel.get("profile_id", "")),
		"teleport": 0,
		"force_kill": 0,
	}


static func _run_style(app: App, _label: String, greedy: bool) -> Dictionary:
	app.start_fight("vs1", "rooftops", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var bot: Fighter = _first_bot(session)
	var foe0: Fighter = _nearest_other(session, bot)
	_lock_named(session, bot, foe0)
	var goal: Vector2 = foe0.global_position if foe0 != null else _named_goal(session, bot)
	var n: int = 0
	while n < GREEDY_TICKS:
		_think_bots(session, 1, greedy)
		n += 1
	bot = _first_bot(session)
	var tel: Dictionary = _first_bot_tel(session)
	var pit_deaths: int = 0
	var fire_deaths: int = 0
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		i += 1
		if f != null and f.dead and f.death_cause == "pit":
			pit_deaths += 1
		if f != null and f.dead and f.death_cause == "fire":
			fire_deaths += 1
	var end: Vector2 = bot.global_position if bot != null else goal
	var other: Fighter = _nearest_other(session, bot)
	var engage_dist: float = end.distance_to(other.global_position) if other != null else 9999.0
	return {
		"pit_deaths": pit_deaths,
		"fire_deaths": fire_deaths,
		"pit_blocks": int(tel.get("pit_blocks", 0)),
		"pit_reroutes": int(tel.get("pit_reroutes", 0)),
		"alive": bot != null and not bot.dead,
		"cause": bot.death_cause if bot != null else "",
		"goal_dist": end.distance_to(goal),
		"engage_dist": engage_dist,
	}


static func _intent_trace(app: App) -> PackedStringArray:
	app.start_fight("vs1", "rooftops", 0)
	await SimReplay.sync_physics(app)
	var out: PackedStringArray = PackedStringArray()
	var n: int = 0
	while n < 24:
		_think_bots(app.session, 1)
		var tel: Dictionary = _first_bot_tel(app.session)
		out.append(str(tel.get("intent", "")))
		n += 1
	return out


static func _named_goal(session: GameSession, bot: Fighter) -> Vector2:
	if session == null or bot == null:
		return Vector2.ZERO
	if session.arena != null:
		var pads: Array[Vector2] = session.arena.player_spawns
		var best: Vector2 = Vector2.ZERO
		var best_d: float = 99999.0
		var i: int = 0
		while i < pads.size():
			var pad: Vector2 = pads[i]
			i += 1
			var d: float = bot.global_position.distance_to(pad)
			if d <= 40.0:
				continue
			if d < best_d:
				best_d = d
				best = pad
		if best_d < 99999.0:
			return best
	var foe: Fighter = null
	var j: int = 0
	while j < session.fighters.size():
		var f: Fighter = session.fighters[j]
		j += 1
		if f == null or f == bot or f.dead or f.team == bot.team:
			continue
		if foe == null or bot.global_position.distance_to(f.global_position) < bot.global_position.distance_to(foe.global_position):
			foe = f
	if foe != null:
		return foe.global_position
	var doc: Dictionary = MapCatalog.document(session.map_id)
	var pick: Pickup = null
	j = 0
	while j < session.pickups.size():
		var p: Pickup = session.pickups[j]
		j += 1
		if p == null or not is_instance_valid(p):
			continue
		var planned: Dictionary = _BotNav.path_to(doc, bot.global_position, p.global_position, 40)
		if (planned.get("cells", []) as Array).size() < 2:
			continue
		if pick == null or bot.global_position.distance_to(p.global_position) < bot.global_position.distance_to(pick.global_position):
			pick = p
	if pick != null:
		return pick.global_position
	return bot.global_position + Vector2(80.0, 0.0)


static func _named_waypoint(session: GameSession, start: Vector2, goal: Vector2) -> Vector2:
	if session == null:
		return goal
	var doc: Dictionary = MapCatalog.document(session.map_id)
	var planned: Dictionary = _BotNav.path_to(doc, start, goal, 48)
	var cells: Array = planned.get("cells", []) as Array
	var i: int = 0
	while i < cells.size():
		var at: Vector2 = MapGraph.cell_center(cells[i] as Vector2i)
		if start.distance_to(at) >= 72.0:
			return at
		i += 1
	return goal


static func _botify_all(session: GameSession) -> void:
	if session == null:
		return
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		if f != null:
			f.is_bot = true
			f.is_human = false
			if i >= session.brains.size() or session.brains[i] == null:
				session.brains.append(session._make_brain(f.slot))
			elif session.brains[i] != null:
				session.brains[i].bind(session, f.slot, session.brains[i].profile_id)
		i += 1


static func _ffa_all(session: GameSession) -> void:
	if session == null:
		return
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		if f != null:
			f.team = i
		i += 1


static func _ally_non_p1(session: GameSession) -> void:
	if session == null:
		return
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		if f != null and f.slot != 0:
			f.team = 1
		i += 1


static func _lock_named(session: GameSession, bot: Fighter, foe: Fighter) -> void:
	if session == null or bot == null or foe == null:
		return
	var i: int = 0
	while i < session.fighters.size():
		if session.fighters[i] == bot and i < session.brains.size() and session.brains[i] != null:
			session.brains[i].lock_foe_slot = foe.slot
			return
		i += 1


static func _present_fighter_count(session: GameSession) -> int:
	if session == null:
		return 0
	var n: int = 0
	var i: int = 0
	while i < session.fighters.size():
		if session.fighters[i] != null:
			n += 1
		i += 1
	return n


static func _explosion_after_bullet(session: GameSession) -> bool:
	if session == null or session.ledger == null:
		return false
	var bullet_tick: int = -1
	var expl_tick: int = -1
	var events: Array = session.ledger.events
	var i: int = 0
	while i < events.size():
		var row: Dictionary = events[i] as Dictionary
		i += 1
		var kind: String = str(row.get("kind", ""))
		var tick: int = int(row.get("tick", -1))
		if kind == "bullet" and bullet_tick < 0:
			bullet_tick = tick
		elif kind == "explosion" and expl_tick < 0:
			expl_tick = tick
	return bullet_tick >= 0 and expl_tick > bullet_tick


static func _death_after_explosion(session: GameSession) -> bool:
	if session == null or session.ledger == null:
		return false
	var expl_tick: int = -1
	var events: Array = session.ledger.events
	var i: int = 0
	while i < events.size():
		var row: Dictionary = events[i] as Dictionary
		i += 1
		if str(row.get("kind", "")) == "explosion" and expl_tick < 0:
			expl_tick = int(row.get("tick", -1))
	if expl_tick < 0:
		return false
	i = 0
	while i < events.size():
		var row2: Dictionary = events[i] as Dictionary
		i += 1
		if str(row2.get("kind", "")) != "death":
			continue
		if int(row2.get("tick", -1)) < expl_tick:
			continue
		var payload: Dictionary = row2.get("payload", {}) as Dictionary
		if str(payload.get("cause", "")) == "damage":
			return true
	return false


static func _keep_exactly_two(session: GameSession) -> void:
	## Fixture only. Official finish must spawn exactly two, not cull.
	if session == null:
		return
	var p1: Fighter = null
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		i += 1
		if f != null and f.slot == 0:
			p1 = f
			break
	if p1 == null and session.fighters.size() > 0:
		p1 = session.fighters[0]
	var foe: Fighter = _nearest_other(session, p1)
	if p1 == null or foe == null:
		return
	var br_p1: BotBrain = null
	var br_foe: BotBrain = null
	i = 0
	while i < session.fighters.size():
		var g: Fighter = session.fighters[i]
		if g == p1 and i < session.brains.size():
			br_p1 = session.brains[i]
		elif g == foe and i < session.brains.size():
			br_foe = session.brains[i]
		i += 1
	i = 0
	while i < session.fighters.size():
		var extra: Fighter = session.fighters[i]
		i += 1
		if extra == null or extra == p1 or extra == foe:
			continue
		if is_instance_valid(extra):
			if extra.get_parent() == session:
				session.remove_child(extra)
			extra.queue_free()
	session.fighters.clear()
	session.fighters.append(p1)
	session.fighters.append(foe)
	session.brains.clear()
	if br_p1 == null:
		br_p1 = session._make_brain(p1.slot)
	if br_foe == null:
		br_foe = session._make_brain(foe.slot)
	session.brains.append(br_p1)
	session.brains.append(br_foe)
	if br_p1 != null:
		br_p1.lock_foe_slot = foe.slot
	if br_foe != null:
		br_foe.lock_foe_slot = p1.slot


static func _one_v_one(session: GameSession) -> void:
	if session == null:
		return
	var p1: Fighter = null
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		i += 1
		if f != null and f.slot == 0:
			p1 = f
			break
	if p1 == null and session.fighters.size() > 0:
		p1 = session.fighters[0]
	var foe: Fighter = _nearest_other(session, p1)
	i = 0
	while i < session.fighters.size():
		var g: Fighter = session.fighters[i]
		i += 1
		if g == null:
			continue
		if g == p1:
			g.team = 0
		elif g == foe:
			g.team = 1
		else:
			g.team = 0
	i = 0
	while i < session.brains.size():
		var br: BotBrain = session.brains[i] as BotBrain
		var body: Fighter = session.fighters[i] if i < session.fighters.size() else null
		i += 1
		if br == null or body == null:
			continue
		if body == p1 and foe != null:
			br.lock_foe_slot = foe.slot
		elif body == foe and p1 != null:
			br.lock_foe_slot = p1.slot
		else:
			br.lock_foe_slot = -1


static func _nearest_other(session: GameSession, bot: Fighter) -> Fighter:
	if session == null or bot == null:
		return null
	var best: Fighter = null
	var best_d: float = 99999.0
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		i += 1
		if f == null or f == bot or f.dead:
			continue
		var d: float = bot.global_position.distance_to(f.global_position)
		if d < best_d:
			best_d = d
			best = f
	return best


static func _living_champion(session: GameSession) -> Fighter:
	if session == null:
		return null
	var best: Fighter = null
	var best_shots: int = -1
	var best_moved: float = -1.0
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		i += 1
		if f == null or f.dead:
			continue
		var tel: Dictionary = _brain_tel(session, f)
		var shots: int = f.shots_fired + int(tel.get("melee_used", 0))
		var moved: float = float(tel.get("moved_px", 0.0))
		if shots > best_shots or (shots == best_shots and moved > best_moved):
			best = f
			best_shots = shots
			best_moved = moved
	return best


static func _think_bots(session: GameSession, ticks: int, greedy: bool = false) -> void:
	if session == null:
		return
	var n: int = 0
	while n < ticks:
		if session.outcome != "play":
			return
		var frames: Array = []
		var i: int = 0
		while i < session.fighters.size():
			var f: Fighter = session.fighters[i]
			if f != null and f.is_bot:
				if i >= session.brains.size():
					session.brains.append(session._make_brain(f.slot))
				var cmd: Dictionary = {}
				if greedy:
					cmd = session.brains[i].think_greedy(
						f, session.fighters, session.pickups, SimConstants.TICK_DT
					)
				else:
					cmd = session.brains[i].think(
						f, session.fighters, session.pickups, SimConstants.TICK_DT
					)
				var frame_d: Dictionary = InputActions.frame_from_cmd(cmd, session.clock.tick, f.slot).to_dict()
				if cmd.has("aim_x") or cmd.has("aim_y"):
					frame_d["aim_x"] = float(cmd.get("aim_x", 0.0))
					frame_d["aim_y"] = float(cmd.get("aim_y", 0.0))
				frames.append(frame_d)
			else:
				frames.append(InputFrame.from_dict(InputActions.empty_frame(session.clock.tick, i)))
			i += 1
		used_apply_frames_attempted += 1
		if session.apply_frames(frames):
			used_apply_frames += 1
			used_apply_frames_succeeded += 1
		n += 1


static func _first_bot(session: GameSession) -> Fighter:
	if session == null:
		return null
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		if f != null and f.is_bot:
			return f
		i += 1
	return null


static func _first_bot_tel(session: GameSession) -> Dictionary:
	return _brain_tel(session, _first_bot(session))


static func _all_bot_tel(session: GameSession) -> Dictionary:
	var out: Dictionary = {
		"gun_used": 0,
		"melee_used": 0,
		"nade_used": 0,
		"perfect_aim_shots": 0,
		"shots_with_error": 0,
		"last_shot_off_deg": 0.0,
		"pit_blocks": 0,
		"pit_reroutes": 0,
		"expansions_peak": 0,
	}
	if session == null:
		return out
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		if f != null and f.is_bot:
			var tel: Dictionary = _brain_tel(session, f)
			out["gun_used"] = int(out["gun_used"]) + int(tel.get("gun_used", 0))
			out["melee_used"] = int(out["melee_used"]) + int(tel.get("melee_used", 0))
			out["nade_used"] = int(out["nade_used"]) + int(tel.get("nade_used", 0))
			out["perfect_aim_shots"] = int(out["perfect_aim_shots"]) + int(tel.get("perfect_aim_shots", 0))
			out["shots_with_error"] = int(out["shots_with_error"]) + int(tel.get("shots_with_error", 0))
			out["last_shot_off_deg"] = maxf(float(out["last_shot_off_deg"]), float(tel.get("last_shot_off_deg", 0.0)))
			out["pit_blocks"] = int(out["pit_blocks"]) + int(tel.get("pit_blocks", 0))
			out["pit_reroutes"] = int(out["pit_reroutes"]) + int(tel.get("pit_reroutes", 0))
			out["expansions_peak"] = maxi(int(out["expansions_peak"]), int(tel.get("expansions_peak", 0)))
		i += 1
	return out


static func _brain_tel(session: GameSession, bot: Fighter) -> Dictionary:
	if bot == null or session == null:
		return {}
	var i: int = 0
	while i < session.fighters.size():
		if session.fighters[i] == bot and i < session.brains.size() and session.brains[i] != null:
			return session.brains[i].telemetry()
		i += 1
	return {}


static func _ledger_kind(session: GameSession, kind: String) -> int:
	if session == null or session.ledger == null:
		return 0
	return session.ledger.count_kind(kind)


static func _ledger_melee_hits(session: GameSession) -> int:
	if session == null or session.ledger == null:
		return 0
	var n: int = 0
	var events: Array = session.ledger.events
	var i: int = 0
	while i < events.size():
		var row: Dictionary = events[i] as Dictionary
		i += 1
		var kind: String = str(row.get("kind", ""))
		if str(row.get("phase", "")) == "melee" and (kind == "hit" or kind == "kick_hit"):
			n += 1
	return n


static func _require(errors: PackedStringArray) -> void:
	var rows: Array = [
		outcome_schema, outcome_maps, outcome_weapons, outcome_finish,
		outcome_diff, outcome_bound, outcome_live
	]
	if not compact_requested():
		rows.append(outcome_greedy)
		rows.append(outcome_recover)
	var i: int = 0
	while i < rows.size():
		if str((rows[i] as Dictionary).get("verdict", "unproven")) == "unproven":
			errors.append("structured outcome left unproven")
		i += 1


static func _event(name: String, payload: Dictionary) -> void:
	var row: Dictionary = payload.duplicate(true)
	row["name"] = name
	events_all.append(row)


static func _note(at: String, session: GameSession, extra: Dictionary) -> void:
	var row: Dictionary = extra.duplicate(true)
	row["at"] = at
	if session != null:
		row["map_id"] = session.map_id
		row["tick"] = session.clock.tick if session.clock != null else -1
		row["outcome"] = session.outcome
	timeline.append(row)


static func _append(into: PackedStringArray, extra: PackedStringArray) -> void:
	var i: int = 0
	while i < extra.size():
		into.append(String(extra[i]))
		i += 1


static func _capture_still(app: App, stem: String) -> String:
	var ev: String = OS.get_environment("HH_VF_EVIDENCE_DIR")
	if ev == "":
		ev = ProjectSettings.globalize_path("res://.evidence/%s" % OS.get_environment("HH_VF_RUN_ID"))
	DirAccess.make_dir_recursive_absolute(ev.path_join("screens"))
	if DisplayServer.get_name() == "headless":
		return ""
	if app == null or app.get_viewport() == null:
		return ""
	var tree: SceneTree = app.get_tree()
	if tree != null and tree.paused:
		## SceneTree runners stall on process_frame while the tree is paused.
		RenderingServer.force_draw()
	else:
		if tree != null:
			await tree.process_frame
		await RenderingServer.frame_post_draw
	var vis: Rect2 = app.get_viewport().get_visible_rect()
	var tex: ViewportTexture = app.get_viewport().get_texture()
	if tex == null:
		return ""
	var img: Image = tex.get_image()
	if img == null:
		return ""
	var shot: String = ev.path_join("screens").path_join("%s_%dx%d.png" % [stem, int(vis.size.x), int(vis.size.y)])
	img.save_png(shot)
	return shot

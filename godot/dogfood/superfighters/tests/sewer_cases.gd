class_name SewerCases
extends RefCounted

## VF5-WP5 Vitriol Sump: pipes, toxic pool, suspended cargo.
## Proof is apply_frames live body positions for P1/P2/bot.
## Climb uses held "up" on a ladder cell. Graph is helper only.
## 60 Hz is ledger:RL-SIM-FIXED-60 (assumption). Not Y8 observed.

const DISPLAY := "Vitriol Sump"
const MAP_ID := "hazardous"
const ALL_ZONES := [
	"west_bank", "west_span", "west_high", "west_mid", "mid_west",
	"mid_east", "mid_low", "east_high", "east_bank", "sump_lip"
]
const SPAWN_ZONE := {
	0: "west_bank",
	1: "west_span",
	2: "east_bank",
}
const LADDER_WEST_X := 24.0
const LADDER_EAST_X := 904.0
const STAND_WEST_BANK_X := 72.0
const WEST_BANK_LAND_X := 136.0
const STAND_WEST_SPAN_X := 296.0
const STAND_WEST_HIGH_X := 176.0
const STAND_WEST_MID_X := 48.0
const STAND_MID_WEST_X := 288.0
const STAND_MID_EAST_X := 576.0
const STAND_MID_LOW_X := 456.0
const STAND_EAST_HIGH_X := 848.0
const STAND_EAST_BANK_X := 928.0
const STAND_LIP_X := 376.0
const STAND_DIVE_X := 320.0
const STAND_PIPE_PICKUP_X := 584.0
const STAND_WADE_X := 384.0
const STAND_HIGH_Y := 24.0
const STAND_MID_Y := 72.0
const STAND_WEST_MID_Y := 88.0
const STAND_BANK_Y := 136.0
const STAND_LIP_Y := 168.0
const STAND_WADE_Y := 200.0
const CARGO_AT := Vector2(288, 72)

static var used_step_fixed: int = 0
static var used_apply_frames: int = 0
static var used_apply_frames_attempted: int = 0
static var used_apply_frames_succeeded: int = 0
static var used_parse_input_event: int = 0
static var used_action_press: int = 0
static var outcome_name: Dictionary = {}
static var outcome_graph: Dictionary = {}
static var outcome_toxic: Dictionary = {}
static var outcome_dive: Dictionary = {}
static var outcome_roll: Dictionary = {}
static var outcome_cargo: Dictionary = {}
static var outcome_spawn: Dictionary = {}
static var outcome_camera: Dictionary = {}
static var outcome_tactic: Dictionary = {}
static var outcome_p1: Dictionary = {}
static var outcome_p2: Dictionary = {}
static var outcome_bot: Dictionary = {}
static var outcome_zone: Dictionary = {}
static var outcome_live: Dictionary = {}
static var outcome_replay: Dictionary = {}
static var outcome_pipes_still: Dictionary = {}
static var outcome_crossing_still: Dictionary = {}
static var outcome_cargo_still: Dictionary = {}
static var outcome_lip_still: Dictionary = {}
static var outcome_toxic_still: Dictionary = {}
static var outcome_variants: Dictionary = {}
static var snapshot_start: Dictionary = {}
static var snapshot_end: Dictionary = {}
static var events_all: Array = []
static var live_hits_p1: Dictionary = {}
static var live_hits_p2: Dictionary = {}
static var live_hits_bot: Dictionary = {}
static var _track_hits: Dictionary = {}
static var _track_slot: int = -1
static var _climb_up_on_ladder: int = 0
static var _climbing_frames: int = 0
static var _tour_climb_up: int = 0
static var _tour_climbing: int = 0
static var _traj: Array = []
static var _traj_on: bool = false
static var _recording: bool = false
static var _rec: Array = []


static func run_all(app: App) -> PackedStringArray:
	used_step_fixed = 0
	used_apply_frames = 0
	used_apply_frames_attempted = 0
	used_apply_frames_succeeded = 0
	used_parse_input_event = 0
	used_action_press = 0
	outcome_name = {"verdict": "unproven"}
	outcome_graph = {"verdict": "unproven"}
	outcome_toxic = {"verdict": "unproven"}
	outcome_dive = {"verdict": "unproven"}
	outcome_roll = {"verdict": "unproven"}
	outcome_cargo = {"verdict": "unproven"}
	outcome_spawn = {"verdict": "unproven"}
	outcome_camera = {"verdict": "unproven"}
	outcome_tactic = {"verdict": "unproven"}
	outcome_p1 = {"verdict": "unproven"}
	outcome_p2 = {"verdict": "unproven"}
	outcome_bot = {"verdict": "unproven"}
	outcome_zone = {"verdict": "unproven"}
	outcome_live = {"verdict": "unproven"}
	outcome_replay = {"verdict": "unproven", "pairs": []}
	outcome_variants = {"verdict": "unproven"}
	outcome_pipes_still = {}
	outcome_crossing_still = {}
	outcome_cargo_still = {}
	outcome_lip_still = {}
	outcome_toxic_still = {}
	snapshot_start = {}
	snapshot_end = {}
	events_all = []
	live_hits_p1 = {}
	live_hits_p2 = {}
	live_hits_bot = {}
	_climb_up_on_ladder = 0
	_climbing_frames = 0
	var errors: PackedStringArray = PackedStringArray()
	_append(errors, schema_and_name())
	_append(errors, await _capture_start(app))
	_append(errors, graph_routes())
	_append(errors, await p1_reaches(app))
	_append(errors, await p2_reaches(app))
	_append(errors, await bot_reaches(app))
	_append(errors, live_zone_union())
	_append(errors, await toxic_contact_death(app))
	_append(errors, await dive_edge(app))
	_append(errors, await roll_edge(app))
	_append(errors, await cargo_collision(app))
	_append(errors, await tactic_changes(app))
	_append(errors, await route_variants(app))
	_append(errors, await no_pit_spawn(app))
	_append(errors, await camera_fits(app))
	_append(errors, await live_identity(app))
	_append(errors, await replay_live_trace(app))
	_append(errors, _require_outcomes())
	return errors


static func schema_and_name() -> PackedStringArray:
	var errors: PackedStringArray = MapCatalog.validate()
	_append(errors, ArenaSpec.validate())
	_append(errors, MapValidator.validate_map(MAP_ID))
	_append(errors, EnvSpec.validate())
	if Maps.display_name(MAP_ID) != DISPLAY:
		errors.append("NAME hazardous display must be Vitriol Sump")
	if Maps.display_name(MAP_ID).to_lower().contains("superfighter"):
		errors.append("NAME uses Superfighters trademark")
	if Maps.display_name(MAP_ID) == "Hazardous":
		errors.append("NAME must retire Hazardous display")
	if str(ArenaSpec.map_row(MAP_ID).get("display_name", "")) != DISPLAY:
		errors.append("NAME ArenaSpec display must be Vitriol Sump")
	var doc: Dictionary = MapCatalog.document(MAP_ID)
	if bool(doc.get("y8_parity_claimed", true)):
		errors.append("NAME claimed Y8 parity")
	if str(doc.get("title", "")) != "Vault Fighters":
		errors.append("NAME title must stay Vault Fighters")
	if WorldCatalog.placements_for(MAP_ID).is_empty():
		errors.append("NAME Vitriol Sump must place hanging cargo")
	if EnvSpec.placements_for(MAP_ID).size() < 8:
		errors.append("NAME Vitriol Sump must place a wide toxic pool")
	if Maps.count_char(MAP_ID, "H") < 8:
		errors.append("NAME missing vertical ladder routes")
	if Maps.count_char(MAP_ID, "b") < 1:
		errors.append("NAME missing hazard telegraph tiles")
	if Maps.pit_column_count(MAP_ID) < 1:
		errors.append("NAME must keep a pit")
	if int(ArenaSpec.map_row(MAP_ID).get("elevations", 0)) < 3:
		errors.append("NAME must declare 3+ elevations")
	if not ArenaSpec.hazards_of(MAP_ID).has("toxic"):
		errors.append("NAME must declare toxic")
	outcome_name = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"display": Maps.display_name(MAP_ID),
		"source": "catalog + ArenaSpec Vitriol Sump",
	}
	_event("stat_name", {"ok": errors.is_empty(), "display": Maps.display_name(MAP_ID)})
	return errors


static func graph_routes() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var doc: Dictionary = MapCatalog.document(MAP_ID)
	_append(errors, MapGraph.missing_platforms(doc))
	var elev: int = MapGraph.elevation_count(doc)
	if elev < 3:
		errors.append("GRAPH Vitriol Sump must have 3+ platform elevations got %d" % elev)
	var graph_rows: Array = []
	var zones: Array = ArenaSpec.combat_zones(MAP_ID)
	var i: int = 0
	while i < zones.size():
		var zone: Dictionary = zones[i] as Dictionary
		var zid: String = str(zone.get("id", ""))
		var reached: bool = MapGraph.zone_reached(doc, zone)
		graph_rows.append({"id": zid, "graph": reached})
		if not reached:
			errors.append("GRAPH helper missed zone %s" % zid)
		i += 1
	if Maps.pit_column_count(MAP_ID) < 1:
		errors.append("GRAPH pit missing; map is a closed rectangle")
	outcome_graph = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"elevations": elev,
		"zones": graph_rows,
		"source": "MapGraph helper; official reach is apply_frames",
	}
	_event("stat_graph", {"ok": errors.is_empty(), "elevations": elev})
	return errors


static func p1_reaches(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1() if session != null else null
	if p1 == null:
		errors.append("P1 missing")
		outcome_p1 = {"verdict": "fail", "source": "player1"}
		return errors
	_begin_track(0)
	_hold_slot(session, 10, 0, PackedStringArray())
	_drive_p1_tour(session)
	live_hits_p1 = _track_hits.duplicate()
	_require_hits(errors, "P1", live_hits_p1, ALL_ZONES)
	if p1.dead:
		errors.append("P1 tour must not die")
	if _tour_climb_up < 4 and _tour_climbing < 8:
		errors.append("P1 must hold up on a ladder for multiple frames got %d climb=%d" % [_tour_climb_up, _tour_climbing])
	outcome_p1 = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"hits": live_hits_p1,
		"dead": p1.dead,
		"climb_up_on_ladder": _tour_climb_up,
		"climbing_frames": _tour_climbing,
		"pos": [p1.global_position.x, p1.global_position.y],
		"on_floor": p1.is_on_floor(),
		"source": "apply_frames live body; P1 holds up on ladders through safe zones",
	}
	_remember_session(session)
	_event("stat_p1", {
		"ok": errors.is_empty(),
		"hits": live_hits_p1,
		"climb_up_on_ladder": _tour_climb_up,
	})
	return errors


static func p2_reaches(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p2: Fighter = _slot(session, 1)
	if p2 == null:
		errors.append("P2 missing")
		outcome_p2 = {"verdict": "fail", "source": "slot 1"}
		return errors
	_begin_track(1)
	_hold_slot(session, 10, 1, PackedStringArray())
	_route_to_mid_west(session, 1)
	_hold_slot(session, 12, 1, PackedStringArray())
	live_hits_p2 = _track_hits.duplicate()
	var need: Array = ["west_span", "mid_west"]
	_require_hits(errors, "P2", live_hits_p2, need)
	if not _left_spawn(live_hits_p2, 1):
		errors.append("P2 must leave west_span spawn and occupy a non-spawn zone")
	if p2.dead:
		errors.append("P2 tour must not die")
	if _tour_climb_up < 4 and _tour_climbing < 8:
		errors.append("P2 must hold up on a ladder got %d climb=%d" % [_tour_climb_up, _tour_climbing])
	outcome_p2 = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"hits": live_hits_p2,
		"dead": p2.dead,
		"climb_up_on_ladder": _tour_climb_up,
		"climbing_frames": _tour_climbing,
		"coverage": "smoke",
		"honest": "preset west-ladder walk onto mid_west; not AI; not Y8 parity",
		"source": "apply_frames P2 smoke route holds up on west ladder onto mid_west",
	}
	_event("stat_p2", {"ok": errors.is_empty(), "hits": live_hits_p2, "climb_up_on_ladder": _tour_climb_up})
	return errors


static func bot_reaches(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs1", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var bot: Fighter = _slot(session, 2)
	if bot == null or not bot.is_bot:
		bot = _first_bot(session)
	if bot == null:
		errors.append("BOT missing vs1 bot")
		outcome_bot = {"verdict": "fail", "source": "vs1 bot"}
		return errors
	_begin_track(bot.slot)
	_hold_slot(session, 12, bot.slot, PackedStringArray())
	_walk_toward(session, bot.slot, LADDER_EAST_X, 180)
	_board_loft(session, bot.slot, LADDER_EAST_X, STAND_EAST_HIGH_X, STAND_HIGH_Y)
	_hold_slot(session, 10, bot.slot, PackedStringArray())
	live_hits_bot = _track_hits.duplicate()
	var routed_dead: bool = bot.dead
	if not bot.dead:
		_brain_chase(session, 16)
	var need: Array = ["east_bank", "east_high"]
	_require_hits(errors, "BOT", live_hits_bot, need)
	if not _left_spawn(live_hits_bot, bot.slot):
		errors.append("BOT must leave spawn and occupy a non-spawn combat zone")
	if routed_dead:
		errors.append("BOT route must not die")
	if _tour_climb_up < 4:
		errors.append("BOT must hold up on a ladder got %d" % _tour_climb_up)
	outcome_bot = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"hits": live_hits_bot,
		"slot": bot.slot,
		"dead": bot.dead,
		"routed_dead": routed_dead,
		"climb_up_on_ladder": _tour_climb_up,
		"climbing_frames": _tour_climbing,
		"coverage": "smoke",
		"honest": "preset east-ladder then short brain chase; not AI; not Y8 parity",
		"source": "apply_frames vs1 bot smoke route holds up on east ladder onto east_high",
	}
	_event("stat_bot", {"ok": errors.is_empty(), "hits": live_hits_bot, "climb_up_on_ladder": _tour_climb_up})
	return errors


static func live_zone_union() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var union_hits: Dictionary = {}
	_merge_hits(union_hits, live_hits_p1)
	_merge_hits(union_hits, live_hits_p2)
	_merge_hits(union_hits, live_hits_bot)
	var missing: PackedStringArray = PackedStringArray()
	var i: int = 0
	while i < ALL_ZONES.size():
		var zid: String = String(ALL_ZONES[i])
		if not bool(union_hits.get(zid, false)):
			missing.append(zid)
			errors.append("ZONE live body missed %s" % zid)
		i += 1
	var p1_all: bool = _has_all(live_hits_p1, ALL_ZONES)
	if not p1_all:
		errors.append("ZONE P1 live tour must visit every safe combat zone")
	if not _left_spawn(live_hits_p2, 1):
		errors.append("ZONE P2 live body never left spawn")
	if not _left_spawn(live_hits_bot, int(outcome_bot.get("slot", 2))):
		errors.append("ZONE bot live body never left spawn")
	if _climb_up_on_ladder < 8:
		errors.append("ZONE official routes must hold up on a ladder")
	outcome_zone = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"union": union_hits,
		"missing": missing,
		"p1_all": p1_all,
		"climb_up_on_ladder": _climb_up_on_ladder,
		"climbing_frames": _climbing_frames,
		"source": "apply_frames live body positions (graph helper only)",
	}
	_event("stat_zone", {
		"ok": errors.is_empty(),
		"union": union_hits,
		"climb_up_on_ladder": _climb_up_on_ladder,
	})
	return errors


static func toxic_contact_death(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1() if session != null else null
	var owner: WorldOwner = session.world_owner as WorldOwner if session != null else null
	if p1 == null or owner == null:
		errors.append("TOXIC missing P1 or world")
		outcome_toxic = {"verdict": "fail"}
		return errors
	if EnvSpec.placements_for(MAP_ID).size() < 8:
		errors.append("TOXIC live map must place a wide pool")
	_begin_track(0)
	_traj_begin()
	_fall_into_pool(session, 0)
	_hold_slot(session, 16, 0, PackedStringArray())
	var acid1: bool = p1.acid_contact
	var hp1: float = p1.health
	var enters: int = 0
	var dmg: int = 0
	if session.ledger != null:
		enters = session.ledger.count_kind("env_enter")
		dmg = session.ledger.count_kind("env_damage")
	_hold_slot(session, 100, 0, PackedStringArray())
	var dead: bool = p1.dead
	var cause: String = p1.death_cause
	var deaths: int = 0
	if session.ledger != null:
		deaths = session.ledger.count_kind("env_death")
	var traj: Dictionary = _traj_summary()
	_append(errors, _require_traj_contact("TOXIC", traj, true))
	if not acid1 and not dead:
		errors.append("TOXIC live body must enter the vitriol pool")
	if hp1 >= Fighter.MAX_HP - 0.5 and not dead:
		errors.append("TOXIC must apply deferred damage")
	if not dead:
		errors.append("TOXIC stay must kill")
	if dead and cause != "damage" and cause != "pit":
		errors.append("TOXIC death_cause must be damage or pit got=%s" % cause)
	if enters < 1:
		errors.append("TOXIC missing env_enter")
	if deaths < 1 and cause != "pit":
		errors.append("TOXIC missing env_death")
	outcome_toxic = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"acid": acid1,
		"hp_after": hp1,
		"dead": dead,
		"cause": cause,
		"enters": enters,
		"damage": dmg,
		"deaths": deaths,
		"trajectory": traj,
		"observed": true,
		"source": "apply_frames live walk-off lip into sump_wade pool; stay-to-death",
	}
	_event("stat_toxic", {"ok": errors.is_empty(), "dead": dead, "acid": acid1})
	return errors


static func dive_edge(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1() if session != null else null
	if p1 == null:
		errors.append("DIVE missing P1")
		outcome_dive = {"verdict": "fail"}
		return errors
	_begin_track(0)
	_traj_begin()
	_drop_to_lip(session, 0)
	_walk_toward(session, 0, STAND_DIVE_X, 48)
	_settle_on_zone(session, 0, "sump_lip", STAND_DIVE_X, 40)
	_press_slot(session, 0, "jump")
	_hold_slot(session, 6, 0, PackedStringArray(["jump"]))
	_press_slot(session, 0, "dive")
	_hold_slot(session, 20, 0, PackedStringArray())
	p1 = session.player1()
	if p1 != null and not p1.acid_contact and not p1.dead:
		_walk_into_pool_from_lip(session, 0)
	var kill: Dictionary = _stay_acid_kill(session, 0, 200)
	p1 = session.player1()
	var dived: bool = p1 != null and (p1.diving or p1.dive_seq > 0)
	var acid: bool = bool(kill.get("acid", false))
	var dead: bool = bool(kill.get("dead", false))
	var cause: String = str(kill.get("cause", ""))
	var y_kill: float = float(kill.get("y", 0.0))
	var dmg: int = 0
	if session.ledger != null:
		dmg = session.ledger.count_kind("env_damage")
	var traj: Dictionary = _traj_summary()
	_append(errors, _require_traj_contact("DIVE", traj, false))
	if not dived:
		errors.append("DIVE must start a dive toward the pool")
	if not acid:
		errors.append("DIVE must still overlap vitriol when HP hits 0")
	if not dead:
		errors.append("DIVE must die from live take_env_tick")
	if cause != "damage":
		errors.append("DIVE death_cause must be damage got=%s" % cause)
	if y_kill > 250.0:
		errors.append("DIVE body left the arena into pit/void y=%s" % str(y_kill))
	if dmg < 1:
		errors.append("DIVE invuln must not cancel toxic contact")
	outcome_dive = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"dived": dived,
		"acid": acid,
		"acid_at_kill": acid,
		"dead": dead,
		"cause": cause,
		"y_at_kill": y_kill,
		"damage": dmg,
		"invuln_cancels_toxic": false,
		"trajectory": traj,
		"observed": true,
		"source": "apply_frames dive into vitriol; take_env_tick ignores invuln",
	}
	_event("stat_dive", {
		"ok": errors.is_empty(),
		"acid": acid,
		"dived": dived,
		"cause": cause,
		"y_at_kill": y_kill,
	})
	return errors


static func roll_edge(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1() if session != null else null
	if p1 == null:
		errors.append("ROLL missing P1")
		outcome_roll = {"verdict": "fail"}
		return errors
	_begin_track(0)
	_traj_begin()
	_drop_to_lip(session, 0)
	_press_slot(session, 0, "roll")
	_hold_slot(session, 24, 0, PackedStringArray(["right"]))
	if p1 != null and not p1.acid_contact and not p1.dead:
		_walk_into_pool_from_lip(session, 0)
	var rolled: bool = p1.roll_seq > 0
	var acid: bool = p1.acid_contact
	var dead: bool = p1.dead
	var dmg: int = 0
	if session.ledger != null:
		dmg = session.ledger.count_kind("env_damage")
	var traj: Dictionary = _traj_summary()
	_append(errors, _require_traj_contact("ROLL", traj, false))
	if not rolled:
		errors.append("ROLL must start a roll toward the pool")
	if not acid and not dead and dmg < 1:
		errors.append("ROLL invuln must not cancel toxic contact")
	outcome_roll = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"rolled": rolled,
		"acid": acid,
		"dead": dead,
		"damage": dmg,
		"trajectory": traj,
		"observed": true,
		"source": "apply_frames roll off sump_lip into vitriol",
	}
	_event("stat_roll", {"ok": errors.is_empty(), "acid": acid, "rolled": rolled})
	return errors


static func cargo_collision(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var owner: WorldOwner = session.world_owner as WorldOwner if session != null else null
	var cargo: Node2D = owner.find_by_id("sump_cargo_hang") if owner != null else null
	var p1: Fighter = session.player1() if session != null else null
	if cargo == null or p1 == null:
		errors.append("CARGO missing sump_cargo_hang or P1")
		outcome_cargo = {"verdict": "fail", "source": "placements"}
		return errors
	var hung0: bool = bool(cargo.get("hanging"))
	if not hung0:
		errors.append("CARGO must start hanging")
	_begin_track(0)
	_route_to_mid_west(session, 0)
	_walk_toward(session, 0, CARGO_AT.x, 80)
	_hold_slot(session, 8, 0, PackedStringArray())
	var blocked: bool = absf(p1.global_position.x - CARGO_AT.x) < 48.0 and absf(p1.global_position.y - CARGO_AT.y) < 24.0
	var swings: int = 0
	while swings < 4:
		_press_slot(session, 0, "melee")
		_hold_slot(session, 8, 0, PackedStringArray(["right"]))
		swings += 1
	_hold_slot(session, 14, 0, PackedStringArray())
	var hung1: bool = cargo != null and bool(cargo.get("hanging"))
	var drops: int = 0
	if owner != null:
		drops = int(owner.drop_events)
	if hung1:
		errors.append("CARGO hanging crate must drop after melee")
	if drops < 1:
		errors.append("CARGO expected a drop event")
	if not blocked and p1.global_position.x < CARGO_AT.x - 48.0:
		errors.append("CARGO live body never reached the suspended crate")
	outcome_cargo = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"hung_before": hung0,
		"hung_after": hung1,
		"drops": drops,
		"reached": blocked,
		"observed": true,
		"source": "apply_frames body meets hanging crate; melee releases it",
	}
	_event("stat_cargo", {"ok": errors.is_empty(), "drops": drops})
	return errors


static func tactic_changes(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1() if session != null else null
	if p1 == null:
		errors.append("TACTIC missing P1")
		outcome_tactic = {"verdict": "fail"}
		return errors
	_begin_track(0)
	var n: int = 0
	while n < 180 and p1 != null and not p1.dead:
		if p1.hanging:
			_hold_slot(session, 8, 0, PackedStringArray(["down"]))
			n += 8
			continue
		_hold_slot(session, 1, 0, PackedStringArray(["down"]))
		n += 1
		p1 = session.player1()
	var floor_dead: bool = p1 != null and p1.dead
	var floor_cause: String = p1.death_cause if p1 != null else ""
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	session = app.session
	p1 = session.player1()
	_begin_track(0)
	_route_to_mid_west(session, 0)
	_gap_jump(session, 0, STAND_MID_EAST_X)
	_settle_on_zone(session, 0, "mid_east", STAND_MID_EAST_X, 40)
	_walk_toward(session, 0, STAND_PIPE_PICKUP_X, 64)
	_hold_slot(session, 8, 0, PackedStringArray())
	p1 = session.player1()
	var drop: Pickup = _choose_pipe_pickup(session, p1)
	if drop == null:
		_route_to_west_high(session, 0)
		_settle_on_zone(session, 0, "west_high", STAND_WEST_HIGH_X, 40)
		p1 = session.player1()
		drop = _choose_pipe_pickup(session, p1)
	var saw_world_pickup: bool = drop != null
	var pickup_id: int = 0
	var pickup_weapon: String = ""
	var pickup_tick: int = 0
	var picked: bool = false
	var inv0: Dictionary = _inv_snap(p1)
	var pick0: int = 0
	if session.ledger != null:
		pick0 = session.ledger.count_kind("item_pickup")
	if drop != null and p1 != null and not p1.dead:
		pickup_id = drop.drop_uid
		pickup_weapon = drop.weapon_id
		_walk_toward(session, 0, drop.global_position.x, 64)
		_hold_slot(session, 6, 0, PackedStringArray())
		var tries: int = 0
		while tries < 12 and not picked:
			p1 = session.player1()
			drop = _pickup_by_uid(session, pickup_id)
			if drop != null:
				_walk_toward(session, 0, drop.global_position.x, 12)
			_hold_slot(session, 3, 0, PackedStringArray(["down"]))
			_press_held_slot(session, 0, "melee", PackedStringArray(["down", "melee"]))
			_hold_slot(session, 2, 0, PackedStringArray(["down"]))
			_hold_slot(session, 2, 0, PackedStringArray())
			p1 = session.player1()
			var pick1: int = 0
			if session.ledger != null:
				pick1 = session.ledger.count_kind("item_pickup")
			if pick1 > pick0 or _inv_changed(inv0, _inv_snap(p1)):
				picked = true
				pickup_tick = session.clock.tick if session.clock != null else 0
			tries += 1
	p1 = session.player1()
	var pipe_alive: bool = p1 != null and not p1.dead and p1.is_on_floor()
	var pipe_zone: String = _zone_id_at(p1)
	var ammo0: int = p1.ammo if p1 != null else 0
	var bullets0: int = session.bullets.size() if session != null else 0
	var fire0: int = 0
	if session.ledger != null:
		fire0 = session.ledger.count_kind("fire_spawn")
	if p1 != null and not p1.dead and picked:
		_hold_slot(session, 16, 0, PackedStringArray(["fire"]))
		_release_slot(session, 0, "fire")
		_hold_slot(session, 8, 0, PackedStringArray())
		_hold_slot(session, 12, 0, PackedStringArray(["fire"]))
	p1 = session.player1()
	var fired: bool = p1 != null and (p1.ammo < ammo0 or session.bullets.size() > bullets0)
	if session.ledger != null and session.ledger.count_kind("fire_spawn") > fire0:
		fired = true
	if not floor_dead:
		errors.append("TACTIC walking the floor must die in the pit or vitriol")
	if floor_dead and floor_cause != "pit" and floor_cause != "damage":
		errors.append("TACTIC floor death cause %s" % floor_cause)
	if not pipe_alive:
		errors.append("TACTIC isolated pipe crossing must keep P1 alive")
	if pipe_zone != "mid_east" and pipe_zone != "mid_west" and pipe_zone != "west_high":
		errors.append("TACTIC pipe route must occupy an isolated pipe got %s" % pipe_zone)
	if not saw_world_pickup:
		errors.append("TACTIC world pickup missing on the pipe")
	if not picked:
		errors.append("TACTIC must overlap the world pickup until inventory changes")
	if pickup_tick <= 0:
		errors.append("TACTIC must record the tick when inventory changed")
	if not fired:
		errors.append("TACTIC pipe route must fire after the live pickup; floor route dies first")
	outcome_tactic = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"floor_dead": floor_dead,
		"floor_cause": floor_cause,
		"pipe_alive": pipe_alive,
		"pipe_zone": pipe_zone,
		"pipe_fired": fired,
		"pickup_id": pickup_id,
		"weapon_id": pickup_weapon,
		"held_weapon": p1.weapon_id if p1 != null else "",
		"pickup_tick": pickup_tick,
		"item_pickup": picked,
		"used_give_weapon": false,
		"observed": true,
		"source": "live floor walk dies; pipe route overlaps world pickup then fires — hazard changes movement and weapon strategy",
	}
	_event("stat_tactic", {
		"ok": errors.is_empty(),
		"floor_dead": floor_dead,
		"pipe_alive": pipe_alive,
		"pickup_id": pickup_id,
		"weapon_id": pickup_weapon,
		"pickup_tick": pickup_tick,
	})
	return errors


static func no_pit_spawn(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_hold_slot(session, 24, 0, PackedStringArray())
	var p1: Fighter = session.player1() if session != null else null
	var p2: Fighter = _slot(session, 1)
	if p1 == null or p1.dead or p1.death_cause == "pit":
		errors.append("SPAWN P1 dropped into a pit")
	if p2 != null and (p2.dead or p2.death_cause == "pit"):
		errors.append("SPAWN P2 dropped into a pit")
	_append(errors, ArenaSpec.validate_spawns_safe(MAP_ID))
	if not Maps.spawn_floor_solid(MAP_ID):
		errors.append("SPAWN marks have no walkable floor")
	outcome_spawn = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"p1_dead": p1 != null and p1.dead,
		"p2_dead": p2 != null and p2.dead,
		"source": "idle apply_frames; spawn AABB off pit/toxic",
	}
	_event("stat_spawn", {"ok": errors.is_empty()})
	return errors


static func camera_fits(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	if session == null:
		errors.append("CAMERA missing session")
		outcome_camera = {"verdict": "fail"}
		return errors
	_begin_track(0)
	_gap_jump(session, 0, STAND_WEST_SPAN_X)
	_hold_slot(session, 8, 0, PackedStringArray())
	var frame: Dictionary = session.camera_framing()
	var size: Vector2 = Maps.pixel_size(MAP_ID)
	var vis: Rect2 = Rect2()
	if app != null and app.get_viewport() != null:
		vis = app.get_viewport().get_visible_rect()
	if size.x > 1280.0 or size.y > 720.0:
		errors.append("CAMERA pixel size exceeds 1280x720")
	if not bool(frame.get("covers_arena", false)):
		errors.append("CAMERA live framing does not cover Vitriol Sump")
	if not bool(frame.get("centered", false)):
		errors.append("CAMERA must stay arena-centered")
	if vis.size.x > 0.0 and (size.x - 2.0 > vis.size.x or size.y - 2.0 > vis.size.y):
		errors.append("CAMERA viewport does not contain arena bounds")
	outcome_camera = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"covers_arena": bool(frame.get("covers_arena", false)),
		"centered": bool(frame.get("centered", false)),
		"arena_size": [size.x, size.y],
		"viewport": [vis.size.x, vis.size.y],
		"observed": true,
		"source": "apply_frames then GameSession.camera_framing",
	}
	_event("stat_camera", {"ok": errors.is_empty()})
	return errors


static func live_identity(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	if session == null or session.hud == null:
		errors.append("LIVE missing HUD")
		outcome_live = {"verdict": "fail"}
		return errors
	var shown: String = ""
	var map_label: Label = session.hud.get_node_or_null("MapName") as Label
	if map_label != null:
		shown = map_label.text
	if shown != DISPLAY:
		errors.append("LIVE HUD map name is %s" % shown)
	if app.title != null:
		app.restart_to_title()
		if app.title.map_btn != null and not str(app.title.map_btn.text).contains(DISPLAY):
			var hops: int = 0
			while hops < 8 and app.title.map_btn != null and not str(app.title.map_btn.text).contains(DISPLAY):
				app.title.map_btn.emit_signal("pressed")
				hops += 1
			if app.title.map_btn != null and not str(app.title.map_btn.text).contains(DISPLAY):
				errors.append("LIVE title map button missing Vitriol Sump")
		if app.title.get_node_or_null("TitleLabel") != null:
			var title_txt: String = (app.title.get_node_or_null("TitleLabel") as Label).text
			if title_txt != "Vault Fighters":
				errors.append("LIVE title card drifted")
			if title_txt.to_lower().contains("superfighter"):
				errors.append("LIVE title uses Superfighters trademark")
	outcome_live = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"hud": shown,
		"source": "HUD + title display Vitriol Sump",
	}
	_event("stat_live", {"ok": errors.is_empty(), "hud": shown})
	return errors


static func replay_live_trace(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var catalog_a: String = MapCodec.stable_hash(MapCatalog.document(MAP_ID))
	MapCatalog.reload()
	var catalog_b: String = MapCodec.stable_hash(MapCatalog.document(MAP_ID))
	var catalog_ok: bool = catalog_a != "" and catalog_a == catalog_b
	if not catalog_ok:
		errors.append("REPLAY hazardous catalog reload hash mismatch")
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_begin_track(0)
	_hold_slot(session, 4, 0, PackedStringArray())
	_rec = []
	_recording = true
	_traj_begin()
	_walk_off_onto_lip(session, 0)
	_walk_into_pool_from_lip(session, 0)
	_hold_slot(session, 20, 0, PackedStringArray())
	_recording = false
	var rec: Array = _rec.duplicate()
	var hash_a: String = SimSnapshot.stable_hash(SimSnapshot.from_session(session))
	var first_dead: bool = session.player1() != null and session.player1().dead
	var first_acid: bool = session.player1() != null and session.player1().acid_contact
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	session = app.session
	_begin_track(0)
	_hold_slot(session, 4, 0, PackedStringArray())
	_apply_recorded(session, rec)
	var hash_b: String = SimSnapshot.stable_hash(SimSnapshot.from_session(session))
	var live_ok: bool = hash_a != "" and hash_a == hash_b
	if rec.is_empty():
		errors.append("REPLAY recorded zero InputFrames")
	if not live_ok:
		errors.append("REPLAY live apply_frames hash mismatch")
	if not first_dead and not first_acid:
		errors.append("REPLAY recorded route must reach toxic contact")
	outcome_replay = {
		"verdict": "match" if errors.is_empty() else "fail",
		"pairs": [
			{"id": MAP_ID, "match": catalog_ok, "hash": catalog_a, "kind": "catalog"},
			{"id": "live_toxic", "match": live_ok, "hash": hash_a, "kind": "apply_frames", "frames": rec.size()},
		],
		"catalog_hash": catalog_a,
		"live_hash": hash_a,
		"frames": rec.size(),
		"observed": true,
		"source": "replay live apply_frames replay hash plus catalog reload",
	}
	_event("stat_replay", {"ok": errors.is_empty(), "hash": hash_a, "frames": rec.size()})
	return errors


static func route_variants(_app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var rows: Array = [
		{
			"morph": "drop",
			"acid": bool(outcome_toxic.get("acid", false)),
			"dead": bool(outcome_toxic.get("dead", false)),
			"samples": int((outcome_toxic.get("trajectory", {}) as Dictionary).get("samples", 0)),
			"dy": (outcome_toxic.get("trajectory", {}) as Dictionary).get("dy", 0.0),
		},
		{
			"morph": "dive",
			"acid": bool(outcome_dive.get("acid", false)),
			"dead": bool(outcome_dive.get("dead", false)),
			"samples": int((outcome_dive.get("trajectory", {}) as Dictionary).get("samples", 0)),
			"dy": (outcome_dive.get("trajectory", {}) as Dictionary).get("dy", 0.0),
		},
		{
			"morph": "roll",
			"acid": bool(outcome_roll.get("acid", false)),
			"dead": bool(outcome_roll.get("dead", false)),
			"samples": int((outcome_roll.get("trajectory", {}) as Dictionary).get("samples", 0)),
			"dy": (outcome_roll.get("trajectory", {}) as Dictionary).get("dy", 0.0),
		},
	]
	if not bool(rows[0].get("acid", false)) and not bool(rows[0].get("dead", false)):
		errors.append("VARIANT drop must reach toxic contact")
	if not bool(rows[1].get("acid", false)):
		errors.append("VARIANT dive must contact vitriol (not pit-only death)")
	if not bool(rows[2].get("acid", false)) and not bool(rows[2].get("dead", false)):
		errors.append("VARIANT roll must reach toxic contact")
	if int(rows[0].get("samples", 0)) < 8 or int(rows[1].get("samples", 0)) < 8 or int(rows[2].get("samples", 0)) < 8:
		errors.append("VARIANT trajectories need live samples")
	outcome_variants = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"morphs": rows,
		"observed": true,
		"source": "three apply_frames morphologies: drop / dive / roll into vitriol",
	}
	_event("stat_variants", {"ok": errors.is_empty(), "n": rows.size()})
	return errors


static func stage_pipes(app: App) -> void:
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_begin_track(0)
	_route_to_west_high(session, 0)
	_settle_on_zone(session, 0, "west_high", STAND_WEST_HIGH_X, 40)
	_hold_slot(session, 16, 0, PackedStringArray())
	outcome_pipes_still = _still_row(session, 0, app, false)
	if session != null:
		session.set_paused(true, RuntimeConstants.REASON_PLAYER)


static func stage_crossing(app: App) -> void:
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_begin_track(0)
	_route_to_mid_west(session, 0)
	_gap_jump(session, 0, STAND_MID_EAST_X)
	_settle_on_zone(session, 0, "mid_east", STAND_MID_EAST_X, 40)
	_hold_slot(session, 16, 0, PackedStringArray())
	outcome_crossing_still = _still_row(session, 0, app, false)
	if session != null:
		session.set_paused(true, RuntimeConstants.REASON_PLAYER)


static func stage_cargo(app: App) -> void:
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_begin_track(0)
	_route_to_mid_west(session, 0)
	_walk_toward(session, 0, CARGO_AT.x, 80)
	_hold_slot(session, 16, 0, PackedStringArray())
	outcome_cargo_still = _still_row(session, 0, app, false)
	if session != null:
		session.set_paused(true, RuntimeConstants.REASON_PLAYER)


static func stage_lip(app: App) -> void:
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_begin_track(0)
	_walk_off_onto_lip(session, 0)
	if _zone_id_at(_slot(session, 0)) != "sump_lip":
		_walk_off_onto_lip(session, 0)
	_hold_slot(session, 16, 0, PackedStringArray())
	outcome_lip_still = _still_row(session, 0, app, false)
	if session != null:
		session.set_paused(true, RuntimeConstants.REASON_PLAYER)


static func stage_toxic(app: App) -> void:
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_begin_track(0)
	_fall_into_pool(session, 0)
	_hold_slot(session, 24, 0, PackedStringArray())
	outcome_toxic_still = _still_row(session, 0, app, true)
	if session != null:
		session.set_paused(true, RuntimeConstants.REASON_PLAYER)


static func _drive_p1_tour(session: GameSession) -> void:
	_gap_jump(session, 0, STAND_WEST_SPAN_X)
	_settle_on_zone(session, 0, "west_span", STAND_WEST_SPAN_X, 40)
	_walk_off_onto_lip(session, 0)
	_settle_on_zone(session, 0, "sump_lip", STAND_LIP_X, 40)
	_jump_up_to(session, 0, STAND_WEST_SPAN_X, STAND_BANK_Y)
	_settle_on_zone(session, 0, "west_span", STAND_WEST_SPAN_X, 40)
	_route_to_west_high(session, 0)
	_settle_on_zone(session, 0, "west_high", STAND_WEST_HIGH_X, 40)
	_climb_down_onto(session, 0, LADDER_WEST_X, STAND_WEST_MID_Y, STAND_WEST_MID_X, 160)
	_settle_on_zone(session, 0, "west_mid", STAND_WEST_MID_X, 40)
	_route_to_mid_west(session, 0)
	_settle_on_zone(session, 0, "mid_west", STAND_MID_WEST_X, 40)
	_gap_jump(session, 0, STAND_MID_EAST_X)
	_settle_on_zone(session, 0, "mid_east", STAND_MID_EAST_X, 40)
	_walk_toward(session, 0, STAND_MID_LOW_X, 80)
	_drop_through_once(session, 0, STAND_BANK_Y, STAND_MID_LOW_X)
	_settle_on_zone(session, 0, "mid_low", STAND_MID_LOW_X, 50)
	_walk_toward(session, 0, STAND_EAST_BANK_X, 260)
	_settle_on_zone(session, 0, "east_bank", STAND_EAST_BANK_X, 50)
	_board_loft(session, 0, LADDER_EAST_X, STAND_EAST_HIGH_X, STAND_HIGH_Y)
	_settle_on_zone(session, 0, "east_high", STAND_EAST_HIGH_X, 40)
	_hold_slot(session, 12, 0, PackedStringArray())


static func _jump_up_to(session: GameSession, slot: int, target_x: float, target_y: float) -> void:
	var tries: int = 0
	while tries < 4:
		var fighter: Fighter = _slot(session, slot)
		if fighter == null or fighter.dead:
			return
		if fighter.is_on_floor() and not fighter.hanging and absf(fighter.global_position.y - target_y) <= 12.0:
			_walk_toward(session, slot, target_x, 40)
			return
		if fighter.hanging:
			_press_slot(session, slot, "jump")
			_hold_slot(session, 16, slot, PackedStringArray(["jump"]))
			tries += 1
			continue
		var dir: String = "left"
		if fighter.global_position.x < target_x:
			dir = "right"
		_press_slot(session, slot, "jump")
		_hold_slot(session, 10, slot, PackedStringArray(["jump", dir]))
		_hold_slot(session, 14, slot, PackedStringArray([dir]))
		_walk_toward(session, slot, target_x, 24)
		tries += 1
	_hold_slot(session, 10, slot, PackedStringArray())


static func _drop_to_mid_low(session: GameSession, slot: int) -> void:
	_walk_toward(session, slot, STAND_MID_LOW_X, 40)
	var n: int = 0
	while n < 48:
		var fighter: Fighter = _slot(session, slot)
		if fighter == null or fighter.dead:
			return
		if fighter.hanging:
			_hold_slot(session, 8, slot, PackedStringArray(["down"]))
			n += 8
			continue
		if _zone_id_at(fighter) == "mid_low" and fighter.is_on_floor():
			_hold_slot(session, 8, slot, PackedStringArray())
			return
		if fighter.is_on_floor() and fighter.global_position.y < STAND_BANK_Y - 8.0:
			_hold_slot(session, 1, slot, PackedStringArray(["down"]))
		else:
			_walk_toward(session, slot, STAND_MID_LOW_X, 6, true)
		n += 1
	_hold_slot(session, 10, slot, PackedStringArray())


static func _route_to_west_high(session: GameSession, slot: int) -> void:
	var fighter: Fighter = _slot(session, slot)
	if fighter != null and fighter.global_position.x > 180.0:
		_land_west_bank(session, slot)
	_walk_toward(session, slot, LADDER_WEST_X, 180)
	_board_loft(session, slot, LADDER_WEST_X, STAND_WEST_HIGH_X, STAND_HIGH_Y)


static func _land_west_bank(session: GameSession, slot: int) -> void:
	_walk_toward(session, slot, WEST_BANK_LAND_X, 220)
	_settle_on_zone(session, slot, "west_bank", WEST_BANK_LAND_X, 40)


static func _route_to_mid_west(session: GameSession, slot: int) -> void:
	_route_to_west_high(session, slot)
	_walk_toward(session, slot, STAND_MID_WEST_X, 80)
	_settle_on_zone(session, slot, "mid_west", STAND_MID_WEST_X, 40)


static func _gap_jump(session: GameSession, slot: int, target_x: float) -> void:
	var fighter: Fighter = _slot(session, slot)
	if fighter == null or fighter.dead:
		return
	var dir: String = "right"
	if fighter.global_position.x > target_x:
		dir = "left"
	var edge: float = target_x
	if dir == "right":
		edge = fighter.global_position.x + 48.0
		if edge > target_x - 8.0:
			edge = target_x - 64.0
	else:
		edge = fighter.global_position.x - 48.0
		if edge < target_x + 8.0:
			edge = target_x + 64.0
	_walk_toward(session, slot, edge, 40)
	_press_slot(session, slot, "jump")
	_hold_slot(session, 12, slot, PackedStringArray(["jump", dir]))
	_hold_slot(session, 16, slot, PackedStringArray([dir]))
	_walk_toward(session, slot, target_x, 48)


static func _drop_through_once(
	session: GameSession, slot: int, land_y: float, land_x: float
) -> void:
	_walk_toward(session, slot, land_x, 40)
	var n: int = 0
	var punched: bool = false
	while n < 48:
		var fighter: Fighter = _slot(session, slot)
		if fighter == null or fighter.dead:
			return
		if fighter.hanging:
			_hold_slot(session, 6, slot, PackedStringArray(["down"]))
			n += 6
			continue
		if fighter.is_on_floor() and absf(fighter.global_position.y - land_y) <= 14.0:
			_hold_slot(session, 8, slot, PackedStringArray())
			return
		if fighter.is_on_floor() and not punched and fighter.global_position.y < land_y - 16.0:
			var y0: float = fighter.global_position.y
			_hold_slot(session, 1, slot, PackedStringArray(["down"]))
			n += 1
			fighter = _slot(session, slot)
			if fighter == null or fighter.dead:
				return
			if not fighter.is_on_floor() or fighter.global_position.y > y0 + 2.0:
				punched = true
			continue
		_hold_slot(session, 1, slot, PackedStringArray())
		n += 1
	_hold_slot(session, 10, slot, PackedStringArray())


static func _fall_into_pool(session: GameSession, slot: int) -> void:
	_walk_off_onto_lip(session, slot)
	_walk_into_pool_from_lip(session, slot)


static func _walk_into_pool_from_lip(session: GameSession, slot: int) -> void:
	var n: int = 0
	var punched: bool = false
	while n < 48:
		var fighter: Fighter = _slot(session, slot)
		if fighter == null:
			return
		if fighter.dead or fighter.acid_contact:
			_hold_slot(session, 16, slot, PackedStringArray())
			return
		if fighter.hanging:
			_hold_slot(session, 6, slot, PackedStringArray(["down"]))
			n += 6
			continue
		if fighter.is_on_floor() and fighter.global_position.y >= 156.0 and not punched:
			var y0: float = fighter.global_position.y
			_hold_slot(session, 1, slot, PackedStringArray(["down"]))
			n += 1
			fighter = _slot(session, slot)
			if fighter != null and (not fighter.is_on_floor() or fighter.global_position.y > y0 + 2.0):
				punched = true
			continue
		if fighter.is_on_floor() and fighter.global_position.y >= 156.0:
			break
		_hold_slot(session, 1, slot, PackedStringArray(["down"]))
		n += 1
	_walk_toward(session, slot, 500.0, 80, true)
	n = 0
	while n < 80:
		var fighter: Fighter = _slot(session, slot)
		if fighter == null or fighter.dead or fighter.acid_contact:
			_hold_slot(session, 16, slot, PackedStringArray())
			return
		if fighter.hanging:
			_hold_slot(session, 6, slot, PackedStringArray(["down"]))
			n += 6
			continue
		_hold_slot(session, 1, slot, PackedStringArray(["down", "right"]))
		n += 1
	_hold_slot(session, 10, slot, PackedStringArray())


static func _walk_off_onto_lip(session: GameSession, slot: int) -> void:
	var fighter0: Fighter = _slot(session, slot)
	if fighter0 != null and fighter0.global_position.x < 200.0:
		_gap_jump(session, slot, STAND_WEST_SPAN_X)
		_settle_on_zone(session, slot, "west_span", STAND_WEST_SPAN_X, 40)
	else:
		_walk_toward(session, slot, STAND_WEST_SPAN_X, 120)
	_walk_toward(session, slot, 328.0, 80)
	var n: int = 0
	while n < 90:
		var fighter: Fighter = _slot(session, slot)
		if fighter == null or fighter.dead:
			return
		if fighter.hanging:
			_press_slot(session, slot, "jump")
			_hold_slot(session, 10, slot, PackedStringArray(["jump"]))
			n += 10
			continue
		if (
			fighter.is_on_floor()
			and not fighter.hanging
			and fighter.global_position.y >= 156.0
			and _zone_id_at(fighter) == "sump_lip"
		):
			_walk_toward(session, slot, STAND_LIP_X, 48)
			_settle_on_zone(session, slot, "sump_lip", STAND_LIP_X, 40)
			_hold_slot(session, 8, slot, PackedStringArray())
			return
		if fighter.is_on_floor() and fighter.global_position.y >= 156.0:
			_walk_toward(session, slot, STAND_LIP_X, 48)
			_settle_on_zone(session, slot, "sump_lip", STAND_LIP_X, 40)
			return
		_hold_slot(session, 1, slot, PackedStringArray(["right"]))
		n += 1
	_walk_toward(session, slot, STAND_LIP_X, 48)
	_settle_on_zone(session, slot, "sump_lip", STAND_LIP_X, 40)
	_hold_slot(session, 8, slot, PackedStringArray())


static func _drop_to_lip(session: GameSession, slot: int) -> void:
	_walk_off_onto_lip(session, slot)


static func _board_loft(
	session: GameSession, slot: int, ladder_x: float, board_x: float, target_y: float
) -> void:
	_climb_up_onto(session, slot, ladder_x, board_x, target_y, 160, false)
	var n: int = 0
	while n < 5:
		var fighter: Fighter = _slot(session, slot)
		if fighter == null or fighter.dead:
			return
		if (
			fighter.is_on_floor()
			and not fighter.climbing
			and not fighter.on_ladder
			and not fighter.hanging
			and absf(fighter.global_position.y - target_y) <= 14.0
		):
			_walk_toward(session, slot, board_x, 64)
			_hold_slot(session, 8, slot, PackedStringArray())
			return
		_hop_off_ladder(session, slot, board_x)
		_walk_toward(session, slot, board_x, 48)
		n += 1
	_hold_slot(session, 10, slot, PackedStringArray())


static func _climb_up_onto(
	session: GameSession,
	slot: int,
	ladder_x: float,
	board_x: float,
	target_y: float,
	max_ticks: int,
	walk_off: bool = false
) -> void:
	_approach_ladder(session, slot, ladder_x)
	var n: int = 0
	while n < max_ticks:
		var fighter: Fighter = _slot(session, slot)
		if fighter == null or fighter.dead:
			return
		if fighter.hanging or fighter.recover_left > 0.0:
			_press_slot(session, slot, "jump")
			_hold_slot(session, 16, slot, PackedStringArray(["jump"]))
			n += 8
			continue
		if fighter.is_on_floor() and fighter.global_position.y <= target_y + 8.0 and not fighter.climbing:
			_walk_toward(session, slot, board_x, 32)
			_hold_slot(session, 10, slot, PackedStringArray())
			return
		if fighter.global_position.y <= target_y + 4.0 and (fighter.climbing or fighter.on_ladder):
			break
		_hold_slot(session, 1, slot, PackedStringArray(["up"]))
		n += 1
	if walk_off:
		_step_off_ladder(session, slot, board_x)
		_board_from_climb(session, slot, board_x)
		_walk_toward(session, slot, board_x, 36)
		_hold_slot(session, 12, slot, PackedStringArray())
		return
	_hop_off_ladder(session, slot, board_x)
	var hopped: Fighter = _slot(session, slot)
	if hopped != null and (not hopped.is_on_floor() or hopped.hanging):
		_hop_off_ladder(session, slot, board_x)
	_board_from_climb(session, slot, board_x)


static func _climb_down_onto(
	session: GameSession, slot: int, ladder_x: float, target_y: float, board_x: float, max_ticks: int
) -> void:
	_approach_ladder(session, slot, ladder_x)
	var n: int = 0
	while n < max_ticks:
		var fighter: Fighter = _slot(session, slot)
		if fighter == null or fighter.dead:
			return
		if fighter.hanging:
			break
		if fighter.global_position.y >= target_y - 10.0:
			break
		_hold_slot(session, 1, slot, PackedStringArray(["down"]))
		n += 1
	_hop_off_ladder(session, slot, board_x)
	_board_from_climb(session, slot, board_x)


static func _settle_on_zone(
	session: GameSession, slot: int, zid: String, board_x: float, max_ticks: int
) -> void:
	var n: int = 0
	while n < max_ticks:
		var fighter: Fighter = _slot(session, slot)
		if fighter == null or fighter.dead:
			return
		if fighter.hanging or fighter.recover_left > 0.0:
			_press_slot(session, slot, "jump")
			_hold_slot(session, 16, slot, PackedStringArray(["jump"]))
			n += 8
			continue
		if fighter.is_on_floor() and not fighter.hanging and _zone_id_at(fighter) == zid:
			_hold_slot(session, 8, slot, PackedStringArray())
			return
		if fighter.on_ladder or fighter.climbing:
			var held: PackedStringArray = PackedStringArray(["right"])
			if fighter.global_position.x > board_x:
				held = PackedStringArray(["left"])
			_hold_slot(session, 1, slot, held)
		else:
			_walk_toward(session, slot, board_x, 1)
			_hold_slot(session, 1, slot, PackedStringArray())
		n += 1
	_hold_slot(session, 10, slot, PackedStringArray())


static func _approach_ladder(session: GameSession, slot: int, ladder_x: float) -> void:
	var fighter: Fighter = _slot(session, slot)
	if fighter == null:
		return
	var side: float = 12.0
	if fighter.global_position.x > ladder_x:
		side = -12.0
	var target: float = ladder_x - side
	if target < 20.0:
		target = ladder_x + 12.0
	_walk_toward(session, slot, target, 220)


static func _step_off_ladder(session: GameSession, slot: int, board_x: float) -> void:
	var fighter: Fighter = _slot(session, slot)
	if fighter == null or fighter.dead:
		return
	var dir: String = "right"
	if fighter.global_position.x > board_x:
		dir = "left"
	var n: int = 0
	while n < 28:
		fighter = _slot(session, slot)
		if fighter == null or fighter.dead:
			return
		if fighter.is_on_floor() and not fighter.climbing and not fighter.hanging:
			return
		if fighter.hanging:
			_press_slot(session, slot, "jump")
			_hold_slot(session, 12, slot, PackedStringArray(["jump", dir]))
			n += 8
			continue
		_hold_slot(session, 1, slot, PackedStringArray([dir]))
		n += 1


static func _hop_off_ladder(session: GameSession, slot: int, board_x: float) -> void:
	var fighter: Fighter = _slot(session, slot)
	if fighter == null or fighter.dead:
		return
	var dir: String = "right"
	if fighter.global_position.x > board_x:
		dir = "left"
	var frames: Array = []
	var i: int = 0
	while i < session.fighters.size():
		var d: Dictionary = InputActions.empty_frame(session.clock.tick, i)
		if i == slot:
			d["pressed"] = PackedStringArray(["jump"])
			d["held"] = PackedStringArray(["jump", dir])
			d["move_x"] = 1.0 if dir == "right" else -1.0
		frames.append(InputFrame.from_dict(d))
		i += 1
	used_apply_frames_attempted += 1
	if session.apply_frames(frames):
		used_apply_frames += 1
		used_apply_frames_succeeded += 1
	_note_live(session, slot, PackedStringArray(["jump", dir]))
	_hold_slot(session, 10, slot, PackedStringArray([dir]))


static func _board_from_climb(session: GameSession, slot: int, board_x: float) -> void:
	var tries: int = 0
	while tries < 4:
		var fighter: Fighter = _slot(session, slot)
		if fighter == null or fighter.dead:
			return
		if fighter.hanging or fighter.recover_left > 0.0:
			_press_slot(session, slot, "jump")
			_hold_slot(session, 22, slot, PackedStringArray(["jump"]))
			_hold_slot(session, 8, slot, PackedStringArray())
			tries += 1
			continue
		break
	var landed: Fighter = _slot(session, slot)
	if landed != null and not landed.dead and not landed.hanging:
		_walk_toward(session, slot, board_x, 48)
	_hold_slot(session, 16, slot, PackedStringArray())
	landed = _slot(session, slot)
	if landed != null and landed.hanging and not landed.dead:
		_press_slot(session, slot, "jump")
		_hold_slot(session, 22, slot, PackedStringArray(["jump"]))
		_hold_slot(session, 10, slot, PackedStringArray())
		landed = _slot(session, slot)
		if landed != null and not landed.hanging:
			_walk_toward(session, slot, board_x, 32)
		_hold_slot(session, 12, slot, PackedStringArray())


static func _walk_toward(
	session: GameSession, slot: int, target_x: float, max_ticks: int, drop_hangs: bool = false
) -> void:
	if session == null:
		return
	var n: int = 0
	var stuck: int = 0
	var last_x: float = -10000.0
	while n < max_ticks:
		var fighter: Fighter = _slot(session, slot)
		if fighter == null or fighter.dead:
			return
		if fighter.hanging:
			if drop_hangs:
				_hold_slot(session, 8, slot, PackedStringArray(["down"]))
			else:
				_press_slot(session, slot, "jump")
				_hold_slot(session, 16, slot, PackedStringArray(["jump"]))
			n += 8
			continue
		if fighter.recover_left > 0.0:
			_hold_slot(session, 1, slot, PackedStringArray())
			n += 1
			continue
		if fighter.climbing and not fighter.is_on_floor():
			var leave: String = "right"
			if target_x + 0.0001 < fighter.global_position.x:
				leave = "left"
			_press_slot(session, slot, "jump")
			_hold_slot(session, 12, slot, PackedStringArray(["jump", leave]))
			n += 8
			continue
		var dx: float = target_x - fighter.global_position.x
		if absf(dx) <= 4.0 and fighter.is_on_floor():
			return
		if absf(dx) <= 4.0:
			_hold_slot(session, 1, slot, PackedStringArray())
			n += 1
			continue
		if absf(fighter.global_position.x - last_x) < 0.4:
			stuck += 1
		else:
			stuck = 0
		last_x = fighter.global_position.x
		var held: PackedStringArray = PackedStringArray(["right"])
		if dx < 0.0:
			held = PackedStringArray(["left"])
		if stuck >= 4 and fighter.is_on_floor():
			held.append("jump")
			_hold_slot(session, 6, slot, held)
			stuck = 0
			n += 6
			continue
		_hold_slot(session, 1, slot, held)
		n += 1


static func _require_hits(
	errors: PackedStringArray, who: String, hits: Dictionary, need: Array
) -> void:
	var i: int = 0
	while i < need.size():
		var zid: String = String(need[i])
		if not bool(hits.get(zid, false)):
			errors.append("%s missed combat zone %s" % [who, zid])
		i += 1


static func _mark_zones(fighter: Fighter, hits: Dictionary) -> void:
	if fighter == null:
		return
	var zones: Array = ArenaSpec.combat_zones(MAP_ID)
	var i: int = 0
	while i < zones.size():
		var zone: Dictionary = zones[i] as Dictionary
		var zid: String = str(zone.get("id", ""))
		if ArenaSpec.zone_contains(zone, fighter.global_position):
			if not bool(hits.get(zid, false)):
				_event("stat_zone_hit", {
					"who": fighter.slot,
					"id": zid,
					"x": fighter.global_position.x,
					"y": fighter.global_position.y,
					"on_floor": fighter.is_on_floor(),
					"on_ladder": fighter.on_ladder,
					"climbing": fighter.climbing,
					"hanging": fighter.hanging,
					"acid": fighter.acid_contact,
					"dead": fighter.dead,
				})
			hits[zid] = true
		i += 1


static func _hold_slot(session: GameSession, ticks: int, slot: int, held: PackedStringArray) -> void:
	if session == null:
		return
	var n: int = 0
	while n < ticks:
		var frames: Array = []
		var i: int = 0
		while i < session.fighters.size():
			var d: Dictionary = InputActions.empty_frame(session.clock.tick, i)
			if i == slot:
				d["held"] = held
				if held.has("right"):
					d["move_x"] = 1.0
				elif held.has("left"):
					d["move_x"] = -1.0
				if held.has("up"):
					d["move_y"] = -1.0
				elif held.has("down"):
					d["move_y"] = 1.0
			frames.append(InputFrame.from_dict(d))
			i += 1
		used_apply_frames_attempted += 1
		if session.apply_frames(frames):
			used_apply_frames += 1
			used_apply_frames_succeeded += 1
		_remember_frames(frames)
		_note_live(session, slot, held)
		n += 1


static func _press_slot(session: GameSession, slot: int, action: String) -> void:
	if session == null:
		return
	var frames: Array = []
	var i: int = 0
	while i < session.fighters.size():
		var d: Dictionary = InputActions.empty_frame(session.clock.tick, i)
		if i == slot:
			d["pressed"] = PackedStringArray([action])
			d["held"] = PackedStringArray([action])
		frames.append(InputFrame.from_dict(d))
		i += 1
	used_apply_frames_attempted += 1
	if session.apply_frames(frames):
		used_apply_frames += 1
		used_apply_frames_succeeded += 1
	_remember_frames(frames)
	_note_live(session, slot, PackedStringArray([action]))


static func _press_held_slot(
	session: GameSession, slot: int, action: String, held: PackedStringArray
) -> void:
	if session == null:
		return
	var frames: Array = []
	var i: int = 0
	while i < session.fighters.size():
		var d: Dictionary = InputActions.empty_frame(session.clock.tick, i)
		if i == slot:
			d["pressed"] = PackedStringArray([action])
			d["held"] = held
			if held.has("right"):
				d["move_x"] = 1.0
			elif held.has("left"):
				d["move_x"] = -1.0
			if held.has("up"):
				d["move_y"] = -1.0
			elif held.has("down"):
				d["move_y"] = 1.0
		frames.append(InputFrame.from_dict(d))
		i += 1
	used_apply_frames_attempted += 1
	if session.apply_frames(frames):
		used_apply_frames += 1
		used_apply_frames_succeeded += 1
	_remember_frames(frames)
	_note_live(session, slot, held)


static func _release_slot(session: GameSession, slot: int, action: String) -> void:
	if session == null:
		return
	var frames: Array = []
	var i: int = 0
	while i < session.fighters.size():
		var d: Dictionary = InputActions.empty_frame(session.clock.tick, i)
		if i == slot:
			d["released"] = PackedStringArray([action])
		frames.append(InputFrame.from_dict(d))
		i += 1
	used_apply_frames_attempted += 1
	if session.apply_frames(frames):
		used_apply_frames += 1
		used_apply_frames_succeeded += 1
	_remember_frames(frames)
	_note_live(session, slot, PackedStringArray())


static func _choose_pipe_pickup(session: GameSession, fighter: Fighter) -> Pickup:
	if session == null:
		return null
	var best: Pickup = null
	var best_score: int = -1
	var i: int = 0
	while i < session.pickups.size():
		var drop: Pickup = session.pickups[i] as Pickup
		i += 1
		if drop == null or not is_instance_valid(drop):
			continue
		var zid: String = _zone_id_at_pos(drop.global_position)
		var score: int = 0
		if zid == "mid_east":
			score = 4
		elif zid == "west_high":
			score = 3
		elif zid == "east_high":
			score = 2
		elif zid == "mid_west":
			score = 1
		else:
			continue
		if fighter != null:
			var near: float = absf(drop.global_position.x - fighter.global_position.x)
			if near < 48.0:
				score += 2
		if score > best_score:
			best_score = score
			best = drop
	return best


static func _pickup_by_uid(session: GameSession, uid: int) -> Pickup:
	if session == null or uid <= 0:
		return null
	var i: int = 0
	while i < session.pickups.size():
		var drop: Pickup = session.pickups[i] as Pickup
		if drop != null and is_instance_valid(drop) and drop.drop_uid == uid:
			return drop
		i += 1
	return null


static func _inv_snap(fighter: Fighter) -> Dictionary:
	if fighter == null:
		return {}
	return {
		"weapon": fighter.weapon_id,
		"gun": fighter.gun_id,
		"melee": fighter.melee_id,
		"ammo": fighter.ammo,
		"reserve": fighter.reserve,
		"nades": fighter.grenades,
		"power": fighter.power_id,
		"power_ammo": fighter.power_ammo,
	}


static func _inv_changed(before: Dictionary, after: Dictionary) -> bool:
	if before.is_empty() or after.is_empty():
		return false
	var keys: Array = before.keys()
	var i: int = 0
	while i < keys.size():
		var key: String = str(keys[i])
		if str(before.get(key, "")) != str(after.get(key, "")):
			return true
		i += 1
	return false


static func _stay_acid_kill(session: GameSession, slot: int, max_ticks: int) -> Dictionary:
	var n: int = 0
	var last_acid: bool = false
	var last_y: float = 0.0
	var last_cause: String = ""
	while n < max_ticks:
		var fighter: Fighter = _slot(session, slot)
		if fighter == null:
			return {"acid": last_acid, "dead": true, "cause": last_cause, "y": last_y}
		last_acid = fighter.acid_contact or last_acid
		last_y = fighter.global_position.y
		last_cause = fighter.death_cause
		if fighter.dead:
			return {
				"acid": last_acid or fighter.acid_contact,
				"dead": true,
				"cause": fighter.death_cause,
				"y": fighter.global_position.y,
			}
		if fighter.global_position.y > 230.0 and not fighter.acid_contact:
			_hold_slot(session, 1, slot, PackedStringArray())
			n += 1
			continue
		_hold_slot(session, 1, slot, PackedStringArray())
		n += 1
	var end: Fighter = _slot(session, slot)
	return {
		"acid": last_acid or (end != null and end.acid_contact),
		"dead": end != null and end.dead,
		"cause": end.death_cause if end != null else last_cause,
		"y": end.global_position.y if end != null else last_y,
	}


static func _zone_id_at_pos(pos: Vector2) -> String:
	var zones: Array = ArenaSpec.combat_zones(MAP_ID)
	var i: int = 0
	while i < zones.size():
		var zone: Dictionary = zones[i] as Dictionary
		if ArenaSpec.zone_contains(zone, pos):
			return str(zone.get("id", ""))
		i += 1
	return ""


static func _note_live(session: GameSession, slot: int, held: PackedStringArray) -> void:
	var fighter: Fighter = _slot(session, slot)
	if fighter == null:
		return
	if _track_slot == slot:
		_mark_zones(fighter, _track_hits)
	if held.has("up") and (fighter.on_ladder or fighter.climbing):
		_climb_up_on_ladder += 1
		_tour_climb_up += 1
	if fighter.climbing:
		_climbing_frames += 1
		_tour_climbing += 1
	_traj_sample(fighter)


static func _brain_chase(session: GameSession, ticks: int) -> void:
	if session == null:
		return
	var n: int = 0
	while n < ticks:
		var frames: Array = []
		var i: int = 0
		while i < session.fighters.size():
			var f: Fighter = session.fighters[i] as Fighter
			if f != null and f.is_bot:
				if i >= session.brains.size():
					session.brains.append(BotBrain.new())
				var cmd: Dictionary = session.brains[i].think(
					f, session.fighters, session.pickups, SimConstants.TICK_DT
				)
				frames.append(InputActions.frame_from_cmd(cmd, session.clock.tick, f.slot))
			else:
				frames.append(InputFrame.from_dict(InputActions.empty_frame(session.clock.tick, i)))
			i += 1
		used_apply_frames_attempted += 1
		if session.apply_frames(frames):
			used_apply_frames += 1
			used_apply_frames_succeeded += 1
		if _track_slot >= 0:
			_note_live(session, _track_slot, PackedStringArray())
		n += 1


static func _slot(session: GameSession, slot: int) -> Fighter:
	if session == null:
		return null
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i] as Fighter
		if f != null and f.slot == slot:
			return f
		i += 1
	return null


static func _first_bot(session: GameSession) -> Fighter:
	if session == null:
		return null
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i] as Fighter
		if f != null and f.is_bot:
			return f
		i += 1
	return null


static func _require_outcomes() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var rows: Array = [
		outcome_name, outcome_graph, outcome_toxic, outcome_dive, outcome_roll,
		outcome_cargo, outcome_spawn, outcome_camera, outcome_tactic, outcome_p1,
		outcome_p2, outcome_bot, outcome_zone, outcome_live, outcome_variants
	]
	var i: int = 0
	while i < rows.size():
		if str((rows[i] as Dictionary).get("verdict", "unproven")) == "unproven":
			errors.append("structured outcome left unproven")
		i += 1
	if str(outcome_replay.get("verdict", "unproven")) == "unproven":
		errors.append("REPLAY outcome left unproven")
	return errors


static func _capture_start(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	if session == null:
		errors.append("START missing session")
		return errors
	snapshot_start = {
		"map_id": session.map_id,
		"mode": session.mode,
		"tick": session.clock.tick if session.clock != null else 0,
		"display": Maps.display_name(session.map_id),
		"layered": MapCatalog.has_id(session.map_id),
	}
	return errors


static func _remember_session(session: GameSession) -> void:
	if session == null:
		return
	snapshot_end = {
		"map_id": session.map_id,
		"mode": session.mode,
		"tick": session.clock.tick if session.clock != null else 0,
		"display": Maps.display_name(session.map_id),
		"layered": MapCatalog.has_id(session.map_id),
	}


static func _begin_track(slot: int) -> void:
	_track_slot = slot
	_track_hits = {}
	_tour_climb_up = 0
	_tour_climbing = 0


static func _still_row(session: GameSession, slot: int, app: App, allow_lose: bool) -> Dictionary:
	var fighter: Fighter = _slot(session, slot)
	var lose: bool = app != null and app.lose_screen != null and app.lose_screen.visible
	return {
		"alive": fighter != null and not fighter.dead,
		"on_floor": fighter != null and fighter.is_on_floor(),
		"hanging": fighter != null and fighter.hanging,
		"climbing": fighter != null and fighter.climbing,
		"on_ladder": fighter != null and fighter.on_ladder,
		"acid": fighter != null and fighter.acid_contact,
		"zone": _zone_id_at(fighter),
		"x": fighter.global_position.x if fighter != null else 0.0,
		"y": fighter.global_position.y if fighter != null else 0.0,
		"lose_visible": lose,
		"allow_lose": allow_lose,
	}


static func _zone_id_at(fighter: Fighter) -> String:
	if fighter == null:
		return ""
	var zones: Array = ArenaSpec.combat_zones(MAP_ID)
	var i: int = 0
	while i < zones.size():
		var zone: Dictionary = zones[i] as Dictionary
		if ArenaSpec.zone_contains(zone, fighter.global_position):
			return str(zone.get("id", ""))
		i += 1
	return ""


static func _left_spawn(hits: Dictionary, slot: int) -> bool:
	var spawn_id: String = str(SPAWN_ZONE.get(slot, ""))
	var i: int = 0
	while i < ALL_ZONES.size():
		var zid: String = String(ALL_ZONES[i])
		if zid != spawn_id and bool(hits.get(zid, false)):
			return true
		i += 1
	return false


static func _has_all(hits: Dictionary, need: Array) -> bool:
	var i: int = 0
	while i < need.size():
		if not bool(hits.get(String(need[i]), false)):
			return false
		i += 1
	return true


static func _merge_hits(into: Dictionary, extra: Dictionary) -> void:
	var keys: Array = extra.keys()
	var i: int = 0
	while i < keys.size():
		if bool(extra.get(keys[i], false)):
			into[str(keys[i])] = true
		i += 1


static func _event(kind: String, extra: Dictionary) -> void:
	var row: Dictionary = {
		"kind": kind,
		"title": "Vault Fighters",
		"tick_hz": 60,
	}
	var keys: Array = extra.keys()
	var i: int = 0
	while i < keys.size():
		row[str(keys[i])] = extra[keys[i]]
		i += 1
	events_all.append(row)


static func _append(target: PackedStringArray, extra: PackedStringArray) -> void:
	var i: int = 0
	while i < extra.size():
		target.append(String(extra[i]))
		i += 1


static func _traj_begin() -> void:
	_traj = []
	_traj_on = true


static func _traj_sample(fighter: Fighter) -> void:
	if not _traj_on or fighter == null:
		return
	if _traj.size() > 0 and _traj.size() % 2 == 1:
		pass
	_traj.append({
		"x": fighter.global_position.x,
		"y": fighter.global_position.y,
		"on_floor": fighter.is_on_floor(),
		"on_ladder": fighter.on_ladder,
		"hanging": fighter.hanging,
		"acid": fighter.acid_contact,
		"dead": fighter.dead,
		"diving": fighter.diving,
		"roll_seq": fighter.roll_seq,
		"zone": _zone_id_at(fighter),
		"vx": fighter.velocity.x,
		"vy": fighter.velocity.y,
	})


static func _traj_summary() -> Dictionary:
	_traj_on = false
	var n: int = _traj.size()
	if n < 1:
		return {"samples": 0, "dy": 0.0, "acid": false, "dead": false, "floor_then_air": false}
	var first: Dictionary = _traj[0] as Dictionary
	var last: Dictionary = _traj[n - 1] as Dictionary
	var acid: bool = false
	var dead: bool = false
	var floor0: bool = false
	var air_after: bool = false
	var i: int = 0
	while i < n:
		var row: Dictionary = _traj[i] as Dictionary
		if bool(row.get("on_floor", false)):
			floor0 = true
		if floor0 and not bool(row.get("on_floor", false)):
			air_after = true
		if bool(row.get("acid", false)):
			acid = true
		if bool(row.get("dead", false)):
			dead = true
		i += 1
	return {
		"samples": n,
		"x0": first.get("x", 0.0),
		"y0": first.get("y", 0.0),
		"x1": last.get("x", 0.0),
		"y1": last.get("y", 0.0),
		"dy": float(last.get("y", 0.0)) - float(first.get("y", 0.0)),
		"acid": acid,
		"dead": dead,
		"floor_then_air": air_after,
		"last_zone": last.get("zone", ""),
		"last_on_floor": last.get("on_floor", false),
	}


static func _require_traj_contact(who: String, traj: Dictionary, must_fall: bool) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	if int(traj.get("samples", 0)) < 8:
		errors.append("%s trajectory needs live samples got %d" % [who, int(traj.get("samples", 0))])
	if not bool(traj.get("acid", false)) and not bool(traj.get("dead", false)):
		errors.append("%s trajectory never contacted toxic" % who)
	if must_fall and float(traj.get("dy", 0.0)) < 8.0 and not bool(traj.get("floor_then_air", false)):
		errors.append("%s trajectory must fall or leave the standing lip" % who)
	return errors


static func _remember_frames(frames: Array) -> void:
	if not _recording:
		return
	var row: Array = []
	var i: int = 0
	while i < frames.size():
		var frame: InputFrame = frames[i] as InputFrame
		if frame == null:
			i += 1
			continue
		row.append({
			"slot": frame.slot,
			"pressed": Array(frame.pressed),
			"held": Array(frame.held),
			"released": Array(frame.released),
			"move_x": frame.move_x,
			"move_y": frame.move_y,
		})
		i += 1
	_rec.append(row)


static func _apply_recorded(session: GameSession, rec: Array) -> void:
	if session == null:
		return
	var n: int = 0
	while n < rec.size():
		var row: Array = rec[n] as Array
		var frames: Array = []
		var i: int = 0
		while i < row.size():
			var src: Dictionary = row[i] as Dictionary
			var d: Dictionary = InputActions.empty_frame(session.clock.tick, int(src.get("slot", 0)))
			d["pressed"] = src.get("pressed", [])
			d["held"] = src.get("held", [])
			d["released"] = src.get("released", [])
			d["move_x"] = src.get("move_x", 0.0)
			d["move_y"] = src.get("move_y", 0.0)
			frames.append(InputFrame.from_dict(d))
			i += 1
		used_apply_frames_attempted += 1
		if session.apply_frames(frames):
			used_apply_frames += 1
			used_apply_frames_succeeded += 1
		n += 1

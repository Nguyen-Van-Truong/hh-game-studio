class_name StationCases
extends RefCounted

## VF5-WP4 Signal Court: floors, courtyard, door, machine, windows.
## Proof is apply_frames live body positions for P1/P2/bot.
## Climb uses held "up" on a ladder cell. Graph is helper only.
## 60 Hz is ledger:RL-SIM-FIXED-60 (assumption). Not Y8 observed.

## Class-name calls only. Preloading ArenaSpec here races MapValidator
## and WorldOwner in --script official runs.

const DISPLAY := "Signal Court"
const MAP_ID := "police"
const ALL_ZONES := [
	"court_mid", "court_low", "court_ground", "west_hall", "west_loft",
	"sky_bridge", "east_hall", "east_mid", "east_top"
]
const SPAWN_ZONE := {
	0: "court_mid",
	1: "court_low",
	2: "east_hall",
}
const LADDER_WEST_X := 424.0
const LADDER_EAST_X := 808.0
const STAND_COURT_MID_X := 72.0
const STAND_COURT_LOW_X := 232.0
const STAND_WEST_HALL_X := 472.0
const STAND_WEST_LOFT_X := 488.0
const STAND_BRIDGE_X := 712.0
const STAND_EAST_HALL_X := 840.0
const STAND_EAST_MID_X := 840.0
const STAND_EAST_TOP_X := 840.0
const STAND_LOFT_Y := 104.0
const STAND_BRIDGE_Y := 104.0
const STAND_MID_Y := 72.0
const STAND_TOP_Y := 24.0
const STAND_FLOOR_Y := 184.0
const DOOR_PLATE_X := 300.0
const GROUND_DROP_X := 168.0
const COVER_AT := Vector2(504, 184)
const ROTOR_AT := Vector2(120, 184)
const SHOOT_X := 156.0

static var used_step_fixed: int = 0
static var used_apply_frames: int = 0
static var used_apply_frames_attempted: int = 0
static var used_apply_frames_succeeded: int = 0
static var used_parse_input_event: int = 0
static var used_action_press: int = 0
static var outcome_name: Dictionary = {}
static var outcome_graph: Dictionary = {}
static var outcome_machine: Dictionary = {}
static var outcome_floor: Dictionary = {}
static var outcome_spawn: Dictionary = {}
static var outcome_cover: Dictionary = {}
static var outcome_door: Dictionary = {}
static var outcome_camera: Dictionary = {}
static var outcome_p1: Dictionary = {}
static var outcome_p2: Dictionary = {}
static var outcome_bot: Dictionary = {}
static var outcome_zone: Dictionary = {}
static var outcome_live: Dictionary = {}
static var outcome_replay: Dictionary = {}
static var outcome_court_still: Dictionary = {}
static var outcome_floor1_still: Dictionary = {}
static var outcome_floor2_still: Dictionary = {}
static var outcome_floor3_still: Dictionary = {}
static var outcome_machine_still: Dictionary = {}
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
static var _floor_standing: Dictionary = {}
static var _east_top_live: bool = false


static func run_all(app: App) -> PackedStringArray:
	used_step_fixed = 0
	used_apply_frames = 0
	used_apply_frames_attempted = 0
	used_apply_frames_succeeded = 0
	used_parse_input_event = 0
	used_action_press = 0
	outcome_name = {"verdict": "unproven"}
	outcome_graph = {"verdict": "unproven"}
	outcome_machine = {"verdict": "unproven"}
	outcome_floor = {"verdict": "unproven"}
	outcome_spawn = {"verdict": "unproven"}
	outcome_cover = {"verdict": "unproven"}
	outcome_door = {"verdict": "unproven"}
	outcome_camera = {"verdict": "unproven"}
	outcome_p1 = {"verdict": "unproven"}
	outcome_p2 = {"verdict": "unproven"}
	outcome_bot = {"verdict": "unproven"}
	outcome_zone = {"verdict": "unproven"}
	outcome_live = {"verdict": "unproven"}
	outcome_replay = {"verdict": "unproven", "pairs": []}
	outcome_court_still = {}
	outcome_floor1_still = {}
	outcome_floor2_still = {}
	outcome_floor3_still = {}
	outcome_machine_still = {}
	snapshot_start = {}
	snapshot_end = {}
	events_all = []
	live_hits_p1 = {}
	live_hits_p2 = {}
	live_hits_bot = {}
	_floor_standing = {}
	_east_top_live = false
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
	_append(errors, await machine_event(app))
	_append(errors, await floor_collision(app))
	_append(errors, await no_pit_spawn(app))
	_append(errors, await cover_windows(app))
	_append(errors, await door_shortcut(app))
	_append(errors, await camera_fits(app))
	_append(errors, await live_identity(app))
	_append(errors, replay_hash())
	_append(errors, _require_outcomes())
	return errors


static func schema_and_name() -> PackedStringArray:
	var errors: PackedStringArray = MapCatalog.validate()
	_append(errors, ArenaSpec.validate())
	_append(errors, MapValidator.validate_map(MAP_ID))
	_append(errors, MovingSpec.validate())
	_append(errors, EnvSpec.validate())
	if Maps.display_name(MAP_ID) != DISPLAY:
		errors.append("NAME police display must be Signal Court")
	if Maps.display_name(MAP_ID).to_lower().contains("superfighter"):
		errors.append("NAME uses Superfighters trademark")
	if Maps.display_name(MAP_ID) == "Police Station":
		errors.append("NAME must retire Police Station display")
	if str(ArenaSpec.map_row(MAP_ID).get("display_name", "")) != DISPLAY:
		errors.append("NAME ArenaSpec display must be Signal Court")
	var doc: Dictionary = MapCatalog.document(MAP_ID)
	if bool(doc.get("y8_parity_claimed", true)):
		errors.append("NAME claimed Y8 parity")
	if str(doc.get("title", "")) != "Vault Fighters":
		errors.append("NAME title must stay Vault Fighters")
	if WorldCatalog.placements_for(MAP_ID).size() < 2:
		errors.append("NAME Signal Court must place window cover")
	if MovingSpec.placements_for(MAP_ID).size() < 4:
		errors.append("NAME Signal Court must place door and lift")
	if EnvSpec.placements_for(MAP_ID).is_empty():
		errors.append("NAME Signal Court must place a machine")
	if Maps.count_char(MAP_ID, "H") < 8:
		errors.append("NAME missing vertical ladder routes")
	if Maps.pit_column_count(MAP_ID) < 1:
		errors.append("NAME courtyard must keep a pit")
	if int(ArenaSpec.map_row(MAP_ID).get("elevations", 0)) < 3:
		errors.append("NAME must declare 3+ floors")
	if ArenaSpec.combat_zones(MAP_ID).size() < 6:
		errors.append("NAME missing multi-route combat zones")
	outcome_name = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"display": Maps.display_name(MAP_ID),
		"source": "catalog + ArenaSpec Signal Court",
	}
	_event("stat_name", {"ok": errors.is_empty(), "display": Maps.display_name(MAP_ID)})
	return errors


static func graph_routes() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var doc: Dictionary = MapCatalog.document(MAP_ID)
	_append(errors, MapGraph.missing_platforms(doc))
	var elev: int = MapGraph.elevation_count(doc)
	if elev < 3:
		errors.append("GRAPH Signal Court must have 3+ platform elevations got %d" % elev)
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
		errors.append("GRAPH courtyard pit missing; map is a closed rectangle")
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
	if _tour_climb_up < 8:
		errors.append("P1 must hold up on a ladder for multiple frames got %d" % _tour_climb_up)
	if not _east_top_live:
		errors.append("P1 missed live east_top")
	if not bool(_floor_standing.get("west_hall", false)):
		errors.append("P1 must occupy west_hall standing on_floor")
	outcome_p1 = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"hits": live_hits_p1,
		"dead": p1.dead,
		"climb_up_on_ladder": _tour_climb_up,
		"climbing_frames": _tour_climbing,
		"floor_standing": _floor_standing.duplicate(),
		"pos": [p1.global_position.x, p1.global_position.y],
		"on_floor": p1.is_on_floor(),
		"source": "apply_frames live body; P1 holds up on ladders through every zone",
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
	_open_signal_door(session, 1)
	_walk_toward(session, 1, STAND_WEST_HALL_X, 180)
	_board_loft(session, 1, LADDER_WEST_X, STAND_WEST_LOFT_X, STAND_LOFT_Y)
	_hold_slot(session, 12, 1, PackedStringArray())
	live_hits_p2 = _track_hits.duplicate()
	var need: Array = ["court_low", "west_hall", "west_loft"]
	_require_hits(errors, "P2", live_hits_p2, need)
	if not _left_spawn(live_hits_p2, 1):
		errors.append("P2 must leave court_low spawn and occupy a non-spawn zone")
	if p2.dead:
		errors.append("P2 tour must not die")
	if _tour_climb_up < 4:
		errors.append("P2 must hold up on a ladder got %d" % _tour_climb_up)
	outcome_p2 = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"hits": live_hits_p2,
		"dead": p2.dead,
		"climb_up_on_ladder": _tour_climb_up,
		"climbing_frames": _tour_climbing,
		"source": "apply_frames P2 holds up on west ladder onto west_loft",
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
	var west_route: bool = bot.global_position.x < 600.0
	_begin_track(bot.slot)
	_hold_slot(session, 12, bot.slot, PackedStringArray())
	if west_route:
		_open_signal_door(session, bot.slot)
		_board_loft(session, bot.slot, LADDER_WEST_X, STAND_WEST_LOFT_X, STAND_LOFT_Y)
	else:
		_board_loft(session, bot.slot, LADDER_EAST_X, STAND_EAST_MID_X, STAND_MID_Y)
	_hold_slot(session, 10, bot.slot, PackedStringArray())
	live_hits_bot = _track_hits.duplicate()
	var routed_dead: bool = bot.dead
	if not bot.dead:
		_brain_chase(session, 16)
	var need: Array = ["east_hall", "east_mid"]
	if west_route:
		need = ["west_hall", "west_loft"]
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
		"source": "apply_frames vs1 bot holds up on a live ladder onto a non-spawn floor",
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
		errors.append("ZONE P1 live tour must visit every combat zone")
	if not _left_spawn(live_hits_p2, 1):
		errors.append("ZONE P2 live body never left spawn")
	if not _left_spawn(live_hits_bot, int(outcome_bot.get("slot", 2))):
		errors.append("ZONE bot live body never left spawn")
	if not _east_top_live:
		errors.append("ZONE east_top had no live body")
	if _climb_up_on_ladder < 8:
		errors.append("ZONE official routes must hold up on a ladder")
	var doc: Dictionary = MapCatalog.document(MAP_ID)
	var graph_rows: Array = []
	var zones: Array = ArenaSpec.combat_zones(MAP_ID)
	i = 0
	while i < zones.size():
		var zone: Dictionary = zones[i] as Dictionary
		var zid: String = str(zone.get("id", ""))
		graph_rows.append({"id": zid, "graph": MapGraph.zone_reached(doc, zone)})
		i += 1
	outcome_zone = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"union": union_hits,
		"missing": missing,
		"p1_all": p1_all,
		"east_top_live": _east_top_live,
		"climb_up_on_ladder": _climb_up_on_ladder,
		"climbing_frames": _climbing_frames,
		"graph_helper": graph_rows,
		"source": "apply_frames live body positions (graph helper only)",
	}
	_event("stat_zone", {
		"ok": errors.is_empty(),
		"union": union_hits,
		"climb_up_on_ladder": _climb_up_on_ladder,
	})
	return errors


static func machine_event(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var owner: WorldOwner = session.world_owner as WorldOwner if session != null else null
	var rotor: Node2D = owner.find_by_id("signal_rotor") if owner != null else null
	var p1: Fighter = session.player1() if session != null else null
	if rotor == null or p1 == null:
		errors.append("MACHINE missing signal_rotor or P1")
		outcome_machine = {"verdict": "fail", "source": "env placement"}
		return errors
	var a0: float = float(rotor.get("angle"))
	_hold_slot(session, 12, 0, PackedStringArray())
	var a1: float = float(rotor.get("angle"))
	if a1 <= a0 + 1.0:
		errors.append("MACHINE rotor must spin before the shot")
	_walk_toward(session, 0, STAND_COURT_LOW_X, 90)
	_walk_toward(session, 0, GROUND_DROP_X, 100, true)
	_walk_toward(session, 0, SHOOT_X, 80)
	_hold_slot(session, 8, 0, PackedStringArray(["left"]))
	p1.give_weapon("uzi")
	p1.fire_cd = 0.0
	var n: int = 0
	while n < 36 and not bool(rotor.get("jammed")):
		_hold_slot(session, 1, 0, PackedStringArray(["fire"]))
		n += 1
	_hold_slot(session, 8, 0, PackedStringArray())
	var jammed: bool = bool(rotor.get("jammed"))
	var jams: int = int(owner.get("rotor_jams")) if owner != null else 0
	var shots: int = int(owner.get("rotor_shots")) if owner != null else 0
	var jam_events: int = 0
	if session.ledger != null:
		jam_events = session.ledger.count_kind("rotor_jam")
	if not jammed:
		errors.append("MACHINE shootable rotor must jam")
	if jams < 1 or jam_events < 1:
		errors.append("MACHINE missing rotor_jam event jams=%d ledger=%d" % [jams, jam_events])
	if shots < 1:
		errors.append("MACHINE expected a live bullet hit on the rotor")
	var a2: float = float(rotor.get("angle"))
	_hold_slot(session, 10, 0, PackedStringArray())
	var a3: float = float(rotor.get("angle"))
	if jammed and a3 > a2 + 1.0:
		errors.append("MACHINE jammed rotor must stop spinning")
	outcome_machine = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"spin_before": a1 > a0 + 1.0,
		"jammed": jammed,
		"jams": jams,
		"shots": shots,
		"ledger_jam": jam_events,
		"source": "apply_frames fire jams signal_rotor; give_weapon is inventory only",
	}
	_event("stat_machine", {"ok": errors.is_empty(), "jammed": jammed, "jams": jams})
	return errors


static func floor_collision(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	if not Maps.police_interior_floor_solid():
		errors.append("FLOOR police interior ground must stay solid")
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1() if session != null else null
	if p1 == null:
		errors.append("FLOOR missing P1")
		outcome_floor = {"verdict": "fail"}
		return errors
	_begin_track(0)
	_open_signal_door(session, 0)
	_walk_toward(session, 0, STAND_WEST_HALL_X, 180)
	_settle_on_zone(session, 0, "west_hall", STAND_WEST_HALL_X, 40)
	var y0: float = p1.global_position.y
	var floor0: bool = p1.is_on_floor()
	_hold_slot(session, 12, 0, PackedStringArray())
	var y1: float = p1.global_position.y
	if not floor0 or not p1.is_on_floor():
		errors.append("FLOOR west_hall must keep P1 standing")
	if absf(y1 - y0) > 6.0:
		errors.append("FLOOR west_hall dropped P1 through the slab")
	_board_loft(session, 0, LADDER_WEST_X, STAND_WEST_LOFT_X, STAND_LOFT_Y)
	_settle_on_zone(session, 0, "west_loft", STAND_WEST_LOFT_X, 40)
	var loft_ok: bool = p1.is_on_floor() and not p1.dead and _zone_id_at(p1) == "west_loft"
	if not loft_ok:
		errors.append("FLOOR west_loft must be a standing floor")
	_walk_toward(session, 0, STAND_BRIDGE_X, 180)
	_board_loft(session, 0, LADDER_EAST_X, STAND_EAST_TOP_X, STAND_TOP_Y)
	_settle_on_zone(session, 0, "east_top", STAND_EAST_TOP_X, 40)
	var top_ok: bool = p1.is_on_floor() and not p1.dead and _zone_id_at(p1) == "east_top"
	if not top_ok:
		errors.append("FLOOR east_top must be a standing floor")
	var floors: Dictionary = {
		"west_hall": floor0 and p1 != null,
		"west_loft": loft_ok,
		"east_top": top_ok,
	}
	outcome_floor = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"floors": floors,
		"interior_solid": Maps.police_interior_floor_solid(),
		"source": "apply_frames standing settle on each named floor",
	}
	_event("stat_floor", {"ok": errors.is_empty(), "floors": floors})
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
		"source": "idle apply_frames; spawn AABB off pit/rotor",
	}
	_event("stat_spawn", {"ok": errors.is_empty()})
	return errors


static func cover_windows(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var owner: WorldOwner = session.world_owner as WorldOwner if session != null else null
	var wood: Node2D = owner.find_by_id("signal_cover_wood") if owner != null else null
	var glass: Node2D = owner.find_by_id("signal_cover_glass") if owner != null else null
	if wood == null or glass == null:
		errors.append("COVER missing signal_cover_wood/glass")
		outcome_cover = {"verdict": "fail", "source": "placements"}
		return errors
	var blocked: bool = owner.has_cover_at(COVER_AT)
	_open_signal_door(session, 0)
	_walk_toward(session, 0, COVER_AT.x - 20.0, 180)
	_hold_slot(session, 6, 0, PackedStringArray(["right"]))
	_press_slot(session, 0, "melee")
	_hold_slot(session, 12, 0, PackedStringArray(["right"]))
	_press_slot(session, 0, "melee")
	_hold_slot(session, 18, 0, PackedStringArray())
	var wood_alive: bool = wood != null and bool(wood.get("alive"))
	var breaks: int = 0
	if owner != null:
		breaks = int(owner.break_events)
	if not blocked:
		errors.append("COVER wood must block before break")
	if wood_alive:
		errors.append("COVER wood crate must break")
	if breaks < 1:
		errors.append("COVER expected a break event")
	outcome_cover = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"blocked_before": blocked,
		"breaks": breaks,
		"wood_alive": wood_alive,
		"source": "apply_frames melee vs signal_cover_wood window stack",
	}
	_event("stat_cover", {"ok": errors.is_empty(), "breaks": breaks})
	return errors


static func door_shortcut(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var owner: WorldOwner = session.world_owner as WorldOwner if session != null else null
	var door: Node2D = owner.find_by_id("signal_door") if owner != null else null
	var p1: Fighter = session.player1() if session != null else null
	if door == null or p1 == null:
		errors.append("DOOR missing signal_door or P1")
		outcome_door = {"verdict": "fail", "source": "movers"}
		return errors
	var closed0: bool = not bool(door.get("door_open"))
	_open_signal_door(session, 0)
	var opened: bool = bool(door.get("door_open"))
	_walk_toward(session, 0, STAND_WEST_HALL_X, 120)
	_settle_on_zone(session, 0, "west_hall", STAND_WEST_HALL_X, 40)
	var in_hall: bool = _zone_id_at(p1) == "west_hall" and p1.is_on_floor() and not p1.dead
	if not closed0:
		errors.append("DOOR must start closed")
	if not opened:
		errors.append("DOOR must open after standing on the plate")
	if not in_hall:
		errors.append("DOOR open must let P1 walk into west_hall")
	outcome_door = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"closed_before": closed0,
		"opened": opened,
		"in_hall": in_hall,
		"source": "stand-still plate opens signal_door; live walk into west_hall",
	}
	_event("stat_door", {"ok": errors.is_empty(), "opened": opened, "in_hall": in_hall})
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
	var frame: Dictionary = session.camera_framing()
	var size: Vector2 = Maps.pixel_size(MAP_ID)
	if size.x > 1280.0 or size.y > 720.0:
		errors.append("CAMERA pixel size exceeds 1280x720")
	if not bool(frame.get("covers_arena", false)):
		errors.append("CAMERA live framing does not cover Signal Court")
	if not bool(frame.get("centered", false)):
		errors.append("CAMERA must stay arena-centered")
	outcome_camera = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"covers_arena": bool(frame.get("covers_arena", false)),
		"centered": bool(frame.get("centered", false)),
		"arena_size": [size.x, size.y],
		"source": "GameSession.camera_framing + MapValidator",
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
				errors.append("LIVE title map button missing Signal Court")
		if app.title.get_node_or_null("TitleLabel") != null:
			var title_txt: String = (app.title.get_node_or_null("TitleLabel") as Label).text
			if title_txt != "Vault Fighters":
				errors.append("LIVE title card drifted")
			if title_txt.to_lower().contains("superfighter"):
				errors.append("LIVE title uses Superfighters trademark")
	outcome_live = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"hud": shown,
		"source": "HUD + title display Signal Court",
	}
	_event("stat_live", {"ok": errors.is_empty(), "hud": shown})
	return errors


static func replay_hash() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var a: String = MapCodec.stable_hash(MapCatalog.document(MAP_ID))
	MapCatalog.reload()
	var b: String = MapCodec.stable_hash(MapCatalog.document(MAP_ID))
	var ok: bool = a != "" and a == b
	if not ok:
		errors.append("REPLAY police reload hash mismatch")
	outcome_replay = {
		"verdict": "match" if ok else "fail",
		"pairs": [{"id": MAP_ID, "match": ok, "hash": a}],
		"source": "catalog reload hash twice",
	}
	_event("stat_replay", {"ok": ok, "hash": a})
	return errors


static func stage_court(app: App) -> void:
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_begin_track(0)
	_hold_slot(session, 16, 0, PackedStringArray())
	outcome_court_still = _still_row(session, 0, app, false)
	if session != null:
		session.set_paused(true, RuntimeConstants.REASON_PLAYER)


static func stage_floor1(app: App) -> void:
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_begin_track(0)
	_open_signal_door(session, 0)
	_walk_toward(session, 0, STAND_WEST_HALL_X, 180)
	_settle_on_zone(session, 0, "west_hall", STAND_WEST_HALL_X, 40)
	_hold_slot(session, 16, 0, PackedStringArray())
	outcome_floor1_still = _still_row(session, 0, app, false)
	if session != null:
		session.set_paused(true, RuntimeConstants.REASON_PLAYER)


static func stage_floor2(app: App) -> void:
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_begin_track(0)
	_open_signal_door(session, 0)
	_board_loft(session, 0, LADDER_WEST_X, STAND_WEST_LOFT_X, STAND_LOFT_Y)
	_settle_on_zone(session, 0, "west_loft", STAND_WEST_LOFT_X, 40)
	_hold_slot(session, 16, 0, PackedStringArray())
	outcome_floor2_still = _still_row(session, 0, app, false)
	if session != null:
		session.set_paused(true, RuntimeConstants.REASON_PLAYER)


static func stage_floor3(app: App) -> void:
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_begin_track(0)
	_open_signal_door(session, 0)
	_walk_toward(session, 0, STAND_WEST_HALL_X, 180)
	_board_loft(session, 0, LADDER_WEST_X, STAND_WEST_LOFT_X, STAND_LOFT_Y)
	_walk_toward(session, 0, STAND_BRIDGE_X, 140)
	_drive_p1_east_top(session)
	_hold_slot(session, 16, 0, PackedStringArray())
	outcome_floor3_still = _still_row(session, 0, app, false)
	if session != null:
		session.set_paused(true, RuntimeConstants.REASON_PLAYER)


static func stage_machine(app: App) -> void:
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_begin_track(0)
	_walk_toward(session, 0, STAND_COURT_LOW_X, 90)
	_walk_toward(session, 0, GROUND_DROP_X, 100, true)
	_walk_toward(session, 0, SHOOT_X, 80)
	_hold_slot(session, 16, 0, PackedStringArray())
	outcome_machine_still = _still_row(session, 0, app, false)
	if session != null:
		session.set_paused(true, RuntimeConstants.REASON_PLAYER)


static func _drive_p1_tour(session: GameSession) -> void:
	_walk_toward(session, 0, STAND_COURT_LOW_X, 90)
	_open_signal_door(session, 0)
	_walk_toward(session, 0, STAND_WEST_HALL_X, 180)
	_settle_on_zone(session, 0, "west_hall", STAND_WEST_HALL_X, 40)
	_board_loft(session, 0, LADDER_WEST_X, STAND_WEST_LOFT_X, STAND_LOFT_Y)
	_settle_on_zone(session, 0, "west_loft", STAND_WEST_LOFT_X, 40)
	_walk_toward(session, 0, STAND_BRIDGE_X, 180)
	_settle_on_zone(session, 0, "sky_bridge", STAND_BRIDGE_X, 40)
	_drive_p1_east_top(session)
	_climb_down_onto(session, 0, LADDER_EAST_X, STAND_FLOOR_Y, STAND_EAST_HALL_X, 160)
	var downed: Fighter = _slot(session, 0)
	if downed != null and downed.global_position.y < 160.0:
		_climb_down_onto(session, 0, LADDER_EAST_X, STAND_FLOOR_Y, STAND_EAST_HALL_X, 120)
	_walk_toward(session, 0, STAND_EAST_HALL_X, 180)
	_settle_on_zone(session, 0, "east_hall", STAND_EAST_HALL_X, 50)
	_hold_slot(session, 12, 0, PackedStringArray())


static func _open_signal_door(session: GameSession, slot: int) -> void:
	# Court-low is a one-way loft. Drop left onto court_ground, then
	# stand still on the plate (vx<=48). Hang uses crouch-drop, not jump.
	_walk_toward(session, slot, STAND_COURT_LOW_X, 90)
	_walk_toward(session, slot, GROUND_DROP_X, 120, true)
	_hold_slot(session, 12, slot, PackedStringArray())
	_walk_toward(session, slot, DOOR_PLATE_X, 180, true)
	var tries: int = 0
	while tries < 3:
		var n: int = 0
		while n < 40:
			var fighter: Fighter = _slot(session, slot)
			if fighter == null or fighter.dead:
				return
			if fighter.hanging:
				_hold_slot(session, 8, slot, PackedStringArray(["down"]))
				n += 8
				continue
			if fighter.recover_left > 0.0 or not fighter.is_on_floor():
				_hold_slot(session, 1, slot, PackedStringArray())
				n += 1
				continue
			if fighter.global_position.y < STAND_FLOOR_Y - 14.0:
				_walk_toward(session, slot, GROUND_DROP_X, 40, true)
				_hold_slot(session, 10, slot, PackedStringArray())
				_walk_toward(session, slot, DOOR_PLATE_X, 80, true)
				n += 8
				continue
			if absf(fighter.global_position.x - DOOR_PLATE_X) > 5.0:
				_walk_toward(session, slot, DOOR_PLATE_X, 24)
			_hold_slot(session, 1, slot, PackedStringArray())
			var owner: WorldOwner = session.world_owner as WorldOwner if session != null else null
			var door: Node2D = owner.find_by_id("signal_door") if owner != null else null
			if door != null and bool(door.get("door_open")):
				_hold_slot(session, 4, slot, PackedStringArray())
				return
			n += 1
		_walk_toward(session, slot, GROUND_DROP_X, 60, true)
		_walk_toward(session, slot, DOOR_PLATE_X, 100, true)
		tries += 1
	_hold_slot(session, 8, slot, PackedStringArray())


static func _drive_p1_east_top(session: GameSession) -> void:
	_walk_toward(session, 0, LADDER_EAST_X, 160)
	_board_loft(session, 0, LADDER_EAST_X, STAND_EAST_MID_X, STAND_MID_Y)
	_settle_on_zone(session, 0, "east_mid", STAND_EAST_MID_X, 30)
	_board_loft(session, 0, LADDER_EAST_X, STAND_EAST_TOP_X, STAND_TOP_Y)
	_settle_on_zone(session, 0, "east_top", STAND_EAST_TOP_X, 40)


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
			and fighter.global_position.y < 120.0
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
	_walk_toward(session, slot, ladder_x - side, 220)


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
					"floor": _floor_name(zid),
					"x": fighter.global_position.x,
					"y": fighter.global_position.y,
					"on_floor": fighter.is_on_floor(),
					"on_ladder": fighter.on_ladder,
					"climbing": fighter.climbing,
					"hanging": fighter.hanging,
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
	_note_live(session, slot, PackedStringArray([action]))


static func _note_live(session: GameSession, slot: int, held: PackedStringArray) -> void:
	var fighter: Fighter = _slot(session, slot)
	if fighter == null:
		return
	if _track_slot == slot:
		_mark_zones(fighter, _track_hits)
	if held.has("up") and fighter.on_ladder:
		_climb_up_on_ladder += 1
		_tour_climb_up += 1
	if fighter.climbing:
		_climbing_frames += 1
		_tour_climbing += 1
	var zid: String = _zone_id_at(fighter)
	if (
		(zid == "west_hall" or zid == "west_loft" or zid == "east_top" or zid == "east_mid" or zid == "east_hall")
		and fighter.is_on_floor()
		and not fighter.hanging
		and not fighter.dead
	):
		_floor_standing[zid] = true
	if zid == "east_top" and not fighter.dead:
		_east_top_live = true


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
		outcome_name, outcome_graph, outcome_machine, outcome_floor, outcome_spawn,
		outcome_cover, outcome_door, outcome_camera, outcome_p1, outcome_p2,
		outcome_bot, outcome_zone, outcome_live
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


static func _floor_name(zid: String) -> String:
	if zid == "west_hall" or zid == "east_hall" or zid == "court_low":
		return "floor1"
	if zid == "west_loft" or zid == "sky_bridge" or zid == "east_mid" or zid == "court_mid":
		return "floor2"
	if zid == "east_top":
		return "floor3"
	return "court"


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

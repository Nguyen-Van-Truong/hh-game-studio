class_name RooftopCases
extends RefCounted

## VF5-WP2 Skyline Relay: vertical routes, pit, breakable cover.
## Proof is apply_frames live body positions for P1/P2/bot.
## Climb uses held "up" on a ladder cell. Graph is helper only.
## 60 Hz is ledger:RL-SIM-FIXED-60 (assumption). Not Y8 observed.

const _MapCatalog: GDScript = preload("res://src/maps/map_catalog.gd")
const _MapCodec: GDScript = preload("res://src/maps/map_codec.gd")
const _MapGraph: GDScript = preload("res://src/maps/map_graph.gd")
const _MapValidator: GDScript = preload("res://src/maps/map_validator.gd")
const _ArenaSpec: GDScript = preload("res://src/maps/arena_spec.gd")
const _World: GDScript = preload("res://src/world/world_catalog.gd")

const DISPLAY := "Skyline Relay"
const MAP_ID := "rooftops"
const ALL_ZONES := ["west_deck", "mid_deck", "east_deck", "west_bridge", "east_bridge", "west_spire"]
const SPAWN_ZONE := {
	0: "west_deck",
	1: "mid_deck",
	2: "east_deck",
}
const LADDER_WEST_X := 168.0
const LADDER_MID_X := 376.0
const LADDER_EAST_X := 792.0
const STAND_SPIRE_X := 152.0
const STAND_SPIRE_Y := 56.0
const STAND_BRIDGE_Y := 72.0
const STAND_DECK_Y := 120.0
const STAND_WEST_BRIDGE_X := 216.0
const STAND_MID_DECK_X := 456.0
const STAND_EAST_BRIDGE_X := 704.0
const STAND_EAST_DECK_X := 848.0

static var used_step_fixed: int = 0
static var used_apply_frames: int = 0
static var used_apply_frames_attempted: int = 0
static var used_apply_frames_succeeded: int = 0
static var used_parse_input_event: int = 0
static var used_action_press: int = 0
static var outcome_name: Dictionary = {}
static var outcome_elev: Dictionary = {}
static var outcome_zone: Dictionary = {}
static var outcome_cover: Dictionary = {}
static var outcome_p1: Dictionary = {}
static var outcome_p2: Dictionary = {}
static var outcome_bot: Dictionary = {}
static var outcome_pit: Dictionary = {}
static var outcome_fallback: Dictionary = {}
static var outcome_live: Dictionary = {}
static var outcome_replay: Dictionary = {}
static var outcome_bridge_still: Dictionary = {}
static var outcome_cover_still: Dictionary = {}
static var outcome_pit_still: Dictionary = {}
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
static var _west_spire_standing: bool = false
static var _east_deck_live: bool = false
static var _tour_climb_up: int = 0
static var _tour_climbing: int = 0


static func run_all(app: App) -> PackedStringArray:
	used_step_fixed = 0
	used_apply_frames = 0
	used_apply_frames_attempted = 0
	used_apply_frames_succeeded = 0
	used_parse_input_event = 0
	used_action_press = 0
	outcome_name = {"verdict": "unproven"}
	outcome_elev = {"verdict": "unproven"}
	outcome_zone = {"verdict": "unproven"}
	outcome_cover = {"verdict": "unproven"}
	outcome_p1 = {"verdict": "unproven"}
	outcome_p2 = {"verdict": "unproven"}
	outcome_bot = {"verdict": "unproven"}
	outcome_pit = {"verdict": "unproven"}
	outcome_fallback = {"verdict": "unproven"}
	outcome_live = {"verdict": "unproven"}
	outcome_replay = {"verdict": "unproven", "pairs": []}
	outcome_bridge_still = {}
	outcome_cover_still = {}
	outcome_pit_still = {}
	snapshot_start = {}
	snapshot_end = {}
	events_all = []
	live_hits_p1 = {}
	live_hits_p2 = {}
	live_hits_bot = {}
	_west_spire_standing = false
	_east_deck_live = false
	_climb_up_on_ladder = 0
	_climbing_frames = 0
	var errors: PackedStringArray = PackedStringArray()
	_append(errors, schema_and_name())
	_append(errors, await _capture_start(app))
	_append(errors, elevations_and_zones())
	_append(errors, await p1_reaches(app))
	_append(errors, await p2_reaches(app))
	_append(errors, await bot_reaches(app))
	_append(errors, live_zone_union())
	_append(errors, await cover_breaks(app))
	_append(errors, await pit_and_fallback(app))
	_append(errors, await live_identity(app))
	_append(errors, replay_hash())
	_append(errors, _require_outcomes())
	return errors


static func schema_and_name() -> PackedStringArray:
	var errors: PackedStringArray = _MapCatalog.validate()
	_append(errors, _ArenaSpec.validate())
	_append(errors, _MapValidator.validate_map(MAP_ID))
	if Maps.display_name(MAP_ID) != DISPLAY:
		errors.append("NAME rooftops display must be Skyline Relay")
	if Maps.display_name(MAP_ID).to_lower().contains("superfighter"):
		errors.append("NAME uses Superfighters trademark")
	if str(_ArenaSpec.map_row(MAP_ID).get("display_name", "")) != DISPLAY:
		errors.append("NAME ArenaSpec display must be Skyline Relay")
	var doc: Dictionary = _MapCatalog.document(MAP_ID)
	if bool(doc.get("y8_parity_claimed", true)):
		errors.append("NAME claimed Y8 parity")
	if str(doc.get("title", "")) != "Vault Fighters":
		errors.append("NAME title must stay Vault Fighters")
	if Visuals.BG_CITY != "res://assets/bg/bg_city.png":
		errors.append("NAME backdrop must stay original bg_city")
	if _World.placements_for(MAP_ID).size() < 2:
		errors.append("NAME Skyline Relay must place breakable cover")
	if Maps.count_char(MAP_ID, "H") < 6:
		errors.append("NAME missing vertical ladder routes")
	if Maps.pit_column_count(MAP_ID) < 1:
		errors.append("NAME missing open pit")
	if _ArenaSpec.weapon_risk(MAP_ID).size() < 2:
		errors.append("NAME missing varied weapon risk")
	outcome_name = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"display": Maps.display_name(MAP_ID),
		"source": "catalog + ArenaSpec Skyline Relay",
	}
	_event("roof_name", {"ok": errors.is_empty(), "display": Maps.display_name(MAP_ID)})
	return errors


static func elevations_and_zones() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var doc: Dictionary = _MapCatalog.document(MAP_ID)
	var elev: int = _MapGraph.elevation_count(doc)
	if elev < 3:
		errors.append("ELEV Skyline Relay needs 3+ platform elevations got %d" % elev)
	var zones: Array = _ArenaSpec.combat_zones(MAP_ID)
	var graph_rows: Array = []
	var i: int = 0
	while i < zones.size():
		var zone: Dictionary = zones[i] as Dictionary
		var zid: String = str(zone.get("id", ""))
		graph_rows.append({"id": zid, "graph": _MapGraph.zone_reached(doc, zone)})
		i += 1
	if zones.size() < 3:
		errors.append("ZONE need 3+ combat zones")
	outcome_elev = {
		"verdict": "pass" if elev >= 3 and errors.is_empty() else "fail",
		"elevations": elev,
		"graph_helper": graph_rows,
		"source": "MapGraph platform y-rows (helper, not Verify)",
	}
	_event("roof_elev", {"ok": errors.is_empty(), "elevations": elev})
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
	_drive_p1_spire(session)
	_drive_p1_high(session)
	_drive_p1_mid_and_east(session)
	live_hits_p1 = _track_hits.duplicate()
	_require_hits(errors, "P1", live_hits_p1, ALL_ZONES)
	if p1.dead:
		errors.append("P1 tour must not pit-kill")
	if _tour_climb_up < 8:
		errors.append("P1 must hold up on a ladder for multiple frames got %d" % _tour_climb_up)
	if not _west_spire_standing:
		errors.append("P1 must occupy west_spire standing on_floor")
	if not bool(live_hits_p1.get("east_deck", false)):
		errors.append("P1 missed live east_deck")
	outcome_p1 = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"hits": live_hits_p1,
		"dead": p1.dead,
		"climb_up_on_ladder": _tour_climb_up,
		"climbing_frames": _tour_climbing,
		"west_spire_standing": _west_spire_standing,
		"pos": [p1.global_position.x, p1.global_position.y],
		"on_floor": p1.is_on_floor(),
		"source": "apply_frames live body; P1 holds up on ladders through every zone",
	}
	_remember_session(session)
	_event("roof_p1", {
		"ok": errors.is_empty(),
		"hits": live_hits_p1,
		"climb_up_on_ladder": _tour_climb_up,
		"west_spire_standing": _west_spire_standing,
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
	_mount_sky_catwalk(session, 1)
	_walk_toward(session, 1, STAND_EAST_BRIDGE_X, 160)
	_hold_slot(session, 12, 1, PackedStringArray())
	live_hits_p2 = _track_hits.duplicate()
	var need: Array = ["mid_deck", "east_bridge"]
	_require_hits(errors, "P2", live_hits_p2, need)
	if not _left_spawn(live_hits_p2, 1):
		errors.append("P2 must leave mid_deck spawn and occupy a non-spawn zone")
	if p2.dead:
		errors.append("P2 tour must not pit-kill")
	if _tour_climb_up < 4:
		errors.append("P2 must hold up on a ladder got %d" % _tour_climb_up)
	outcome_p2 = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"hits": live_hits_p2,
		"dead": p2.dead,
		"climb_up_on_ladder": _tour_climb_up,
		"climbing_frames": _tour_climbing,
		"source": "apply_frames P2 holds up on mid ladder onto east_bridge",
	}
	_event("roof_p2", {"ok": errors.is_empty(), "hits": live_hits_p2, "climb_up_on_ladder": _tour_climb_up})
	return errors


static func bot_reaches(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs1", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var bot: Fighter = _first_bot(session)
	if bot == null:
		errors.append("BOT missing vs1 bot")
		outcome_bot = {"verdict": "fail", "source": "vs1 bot"}
		return errors
	_begin_track(bot.slot)
	_hold_slot(session, 8, bot.slot, PackedStringArray())
	_mount_sky_catwalk(session, bot.slot)
	if bot.global_position.x < 500.0:
		_walk_toward(session, bot.slot, STAND_EAST_BRIDGE_X, 160)
	else:
		_walk_toward(session, bot.slot, STAND_EAST_BRIDGE_X, 80)
	_hold_slot(session, 10, bot.slot, PackedStringArray())
	live_hits_bot = _track_hits.duplicate()
	var routed_dead: bool = bot.dead
	if not bot.dead:
		_brain_chase(session, 16)
	var need: Array = ["east_bridge"]
	if bot.slot == 2:
		need = ["east_deck", "east_bridge"]
	else:
		need = ["mid_deck", "east_bridge"]
	_require_hits(errors, "BOT", live_hits_bot, need)
	if not _left_spawn(live_hits_bot, bot.slot):
		errors.append("BOT must leave spawn and occupy a non-spawn combat zone")
	if routed_dead:
		errors.append("BOT route must not pit-kill")
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
		"source": "apply_frames vs1 bot holds up on ladder onto a non-spawn zone",
	}
	_event("roof_bot", {"ok": errors.is_empty(), "hits": live_hits_bot, "climb_up_on_ladder": _tour_climb_up})
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
	if not _west_spire_standing:
		errors.append("ZONE west_spire was never occupied standing on_floor")
	if not _east_deck_live:
		errors.append("ZONE east_deck had no live body")
	if _climb_up_on_ladder < 8:
		errors.append("ZONE official routes must hold up on a ladder")
	var doc: Dictionary = _MapCatalog.document(MAP_ID)
	var graph_rows: Array = []
	var zones: Array = _ArenaSpec.combat_zones(MAP_ID)
	i = 0
	while i < zones.size():
		var zone: Dictionary = zones[i] as Dictionary
		var zid: String = str(zone.get("id", ""))
		graph_rows.append({"id": zid, "graph": _MapGraph.zone_reached(doc, zone)})
		i += 1
	outcome_zone = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"zones": [
			{"id": "west_deck", "p1": bool(live_hits_p1.get("west_deck", false)), "p2": bool(live_hits_p2.get("west_deck", false)), "bot": bool(live_hits_bot.get("west_deck", false))},
			{"id": "mid_deck", "p1": bool(live_hits_p1.get("mid_deck", false)), "p2": bool(live_hits_p2.get("mid_deck", false)), "bot": bool(live_hits_bot.get("mid_deck", false))},
			{"id": "east_deck", "p1": bool(live_hits_p1.get("east_deck", false)), "p2": bool(live_hits_p2.get("east_deck", false)), "bot": bool(live_hits_bot.get("east_deck", false))},
			{"id": "west_bridge", "p1": bool(live_hits_p1.get("west_bridge", false)), "p2": bool(live_hits_p2.get("west_bridge", false)), "bot": bool(live_hits_bot.get("west_bridge", false))},
			{"id": "east_bridge", "p1": bool(live_hits_p1.get("east_bridge", false)), "p2": bool(live_hits_p2.get("east_bridge", false)), "bot": bool(live_hits_bot.get("east_bridge", false))},
			{"id": "west_spire", "p1": bool(live_hits_p1.get("west_spire", false)), "p2": bool(live_hits_p2.get("west_spire", false)), "bot": bool(live_hits_bot.get("west_spire", false))},
		],
		"union": union_hits,
		"missing": missing,
		"p1_all": p1_all,
		"west_spire_standing": _west_spire_standing,
		"east_deck_live": _east_deck_live,
		"climb_up_on_ladder": _climb_up_on_ladder,
		"climbing_frames": _climbing_frames,
		"graph_helper": graph_rows,
		"source": "apply_frames live body positions (graph helper only)",
	}
	_event("roof_zone", {
		"ok": errors.is_empty(),
		"union": union_hits,
		"climb_up_on_ladder": _climb_up_on_ladder,
		"west_spire_standing": _west_spire_standing,
	})
	return errors


static func cover_breaks(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var owner: WorldOwner = session.world_owner as WorldOwner if session != null else null
	var wood: Node2D = owner.find_by_id("sky_cover_wood") if owner != null else null
	var glass: Node2D = owner.find_by_id("sky_cover_glass") if owner != null else null
	if wood == null or glass == null:
		errors.append("COVER missing sky_cover_wood/glass")
		outcome_cover = {"verdict": "fail", "source": "placements"}
		return errors
	var blocked: bool = owner.has_cover_at(Vector2(520, 120))
	_hold_slot(session, 28, 1, PackedStringArray(["right"]))
	_press_slot(session, 1, "melee")
	_hold_slot(session, 18, 1, PackedStringArray())
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
	var ghost: bool = owner.has_cover_at(Vector2(520, 120))
	if ghost:
		errors.append("COVER AABB still solid after break")
	outcome_cover = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"blocked_before": blocked,
		"breaks": breaks,
		"wood_alive": wood_alive,
		"source": "P2 melee vs sky_cover_wood on mid deck",
	}
	_event("roof_cover", {"ok": errors.is_empty(), "breaks": breaks})
	return errors


static func pit_and_fallback(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1() if session != null else null
	_hold_slot(session, 12, 0, PackedStringArray(["right"]))
	_hold_slot(session, 8, 0, PackedStringArray())
	var safe: bool = p1 != null and not p1.dead and p1.is_on_floor()
	if not safe:
		errors.append("FALLBACK west-deck walk must stay alive")
	outcome_fallback = {
		"verdict": "pass" if safe else "fail",
		"dead": p1.dead if p1 != null else true,
		"on_floor": p1.is_on_floor() if p1 != null else false,
		"source": "apply_frames short walk stays on west deck",
	}
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	session = app.session
	p1 = session.player1() if session != null else null
	_hold_slot(session, 90, 0, PackedStringArray(["right"]))
	_hold_slot(session, 50, 0, PackedStringArray())
	var pit_dead: bool = p1 != null and p1.dead and p1.death_cause == "pit"
	if not pit_dead:
		errors.append("PIT walk-off must kill with cause pit")
	outcome_pit = {
		"verdict": "pass" if pit_dead else "fail",
		"dead": p1.dead if p1 != null else false,
		"cause": p1.death_cause if p1 != null else "",
		"source": "apply_frames dedicated fallback walk-off into open gap",
	}
	_event("roof_pit", {"ok": errors.is_empty(), "pit": pit_dead, "fallback": safe})
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
			errors.append("LIVE title map button missing Skyline Relay")
		if app.title.get_node_or_null("TitleLabel") != null:
			var title_txt: String = (app.title.get_node_or_null("TitleLabel") as Label).text
			if title_txt != "Vault Fighters":
				errors.append("LIVE title card drifted")
			if title_txt.to_lower().contains("superfighter"):
				errors.append("LIVE title uses Superfighters trademark")
	outcome_live = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"hud": shown,
		"source": "HUD + title display Skyline Relay",
	}
	_event("roof_live", {"ok": errors.is_empty(), "hud": shown})
	return errors


static func replay_hash() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var a: String = _MapCodec.stable_hash(_MapCatalog.document(MAP_ID))
	_MapCatalog.reload()
	var b: String = _MapCodec.stable_hash(_MapCatalog.document(MAP_ID))
	var ok: bool = a != "" and a == b
	if not ok:
		errors.append("REPLAY rooftops reload hash mismatch")
	outcome_replay = {
		"verdict": "match" if ok else "fail",
		"pairs": [{"id": MAP_ID, "match": ok, "hash": a}],
		"source": "catalog reload hash twice",
	}
	_event("roof_replay", {"ok": ok, "hash": a})
	return errors


static func stage_bridge(app: App) -> void:
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_begin_track(0)
	_drive_p1_high(session)
	_hold_slot(session, 16, 0, PackedStringArray())
	outcome_bridge_still = _still_row(session, 0, app, false)
	if session != null:
		session.set_paused(true, RuntimeConstants.REASON_PLAYER)


static func stage_cover(app: App) -> void:
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_begin_track(0)
	_drive_p1_spire(session)
	_hold_slot(session, 16, 0, PackedStringArray())
	outcome_cover_still = _still_row(session, 0, app, false)
	if session != null:
		session.set_paused(true, RuntimeConstants.REASON_PLAYER)


static func stage_pit(app: App) -> void:
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_hold_slot(session, 90, 0, PackedStringArray(["right"]))
	_hold_slot(session, 50, 0, PackedStringArray())
	if app != null and app.lose_screen != null:
		app.lose_screen.show_lose("Down", "Skyline Relay pit. High ground or the drop.")
	outcome_pit_still = _still_row(session, 0, app, true)


static func _drive_p1_high(session: GameSession) -> void:
	# Climb the west catwalk ladder with held up, then stand on west_bridge.
	_climb_up_onto(session, 0, LADDER_WEST_X, STAND_WEST_BRIDGE_X, STAND_BRIDGE_Y, 100)


static func _drive_p1_spire(session: GameSession) -> void:
	# Climb the west catwalk ladder with up, then step left onto the ####.
	_climb_up_onto(session, 0, LADDER_WEST_X, STAND_SPIRE_X, STAND_SPIRE_Y, 100)
	_settle_on_zone(session, 0, "west_spire", STAND_SPIRE_X, 36)


static func _drive_p1_mid_and_east(session: GameSession) -> void:
	# Already standing on west_bridge after _drive_p1_high.
	_walk_toward(session, 0, 360.0, 140)
	_climb_down_onto(session, 0, LADDER_MID_X, STAND_DECK_Y, STAND_MID_DECK_X, 70)
	_climb_up_onto(session, 0, LADDER_MID_X, 400.0, STAND_BRIDGE_Y, 90)
	_walk_toward(session, 0, STAND_EAST_BRIDGE_X, 180)
	_hold_slot(session, 8, 0, PackedStringArray())
	_climb_down_onto(session, 0, LADDER_EAST_X, STAND_DECK_Y, STAND_EAST_DECK_X, 70)
	_hold_slot(session, 12, 0, PackedStringArray())


static func _mount_sky_catwalk(session: GameSession, slot: int) -> void:
	# Outcome banner matches applied input: hold up on the nearest high ladder.
	var fighter: Fighter = _slot(session, slot)
	var ladder_x: float = LADDER_MID_X
	var board_x: float = 400.0
	if fighter != null and fighter.global_position.x > 640.0:
		ladder_x = LADDER_EAST_X
		board_x = STAND_EAST_BRIDGE_X
	elif fighter != null and fighter.global_position.x < 200.0:
		ladder_x = LADDER_WEST_X
		board_x = STAND_WEST_BRIDGE_X
	_climb_up_onto(session, slot, ladder_x, board_x, STAND_BRIDGE_Y, 100)


static func _climb_up_onto(
	session: GameSession, slot: int, ladder_x: float, board_x: float, target_y: float, max_ticks: int
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
		if fighter.global_position.y <= target_y + 4.0 and (fighter.climbing or fighter.on_ladder or fighter.is_on_floor()):
			break
		_hold_slot(session, 1, slot, PackedStringArray(["up"]))
		n += 1
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
	_walk_toward(session, slot, ladder_x - side, 80)


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


static func _walk_toward(session: GameSession, slot: int, target_x: float, max_ticks: int) -> void:
	if session == null:
		return
	var n: int = 0
	while n < max_ticks:
		var fighter: Fighter = _slot(session, slot)
		if fighter == null or fighter.dead:
			return
		if fighter.hanging:
			return
		var dx: float = target_x - fighter.global_position.x
		if absf(dx) <= 4.0:
			return
		var held: PackedStringArray = PackedStringArray(["right"])
		if dx < 0.0:
			held = PackedStringArray(["left"])
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
	var zones: Array = _ArenaSpec.combat_zones(MAP_ID)
	var i: int = 0
	while i < zones.size():
		var zone: Dictionary = zones[i] as Dictionary
		var zid: String = str(zone.get("id", ""))
		if _ArenaSpec.zone_contains(zone, fighter.global_position):
			if not bool(hits.get(zid, false)):
				_event("roof_zone_hit", {
					"who": fighter.slot,
					"id": zid,
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
	if zid == "west_spire" and fighter.is_on_floor() and not fighter.hanging and not fighter.dead:
		_west_spire_standing = true
	if zid == "east_deck" and not fighter.dead:
		_east_deck_live = true


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
		outcome_name, outcome_elev, outcome_zone, outcome_cover, outcome_p1,
		outcome_p2, outcome_bot, outcome_pit, outcome_fallback, outcome_live
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
		"layered": _MapCatalog.has_id(session.map_id),
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
		"layered": _MapCatalog.has_id(session.map_id),
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
	var zones: Array = _ArenaSpec.combat_zones(MAP_ID)
	var i: int = 0
	while i < zones.size():
		var zone: Dictionary = zones[i] as Dictionary
		if _ArenaSpec.zone_contains(zone, fighter.global_position):
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

class_name WarehouseCases
extends RefCounted

## VF5-WP3 Pallet Annex: cover, cargo, catwalks, office door, lift.
## Proof is apply_frames live body positions for P1/P2/bot.
## Climb uses held "up" on a ladder cell. Graph is helper only.
## 60 Hz is ledger:RL-SIM-FIXED-60 (assumption). Not Y8 observed.

const _MapCatalog: GDScript = preload("res://src/maps/map_catalog.gd")
const _MapCodec: GDScript = preload("res://src/maps/map_codec.gd")
const _MapGraph: GDScript = preload("res://src/maps/map_graph.gd")
const _MapValidator: GDScript = preload("res://src/maps/map_validator.gd")
const _ArenaSpec: GDScript = preload("res://src/maps/arena_spec.gd")
const _World: GDScript = preload("res://src/world/world_catalog.gd")
const _Moving: GDScript = preload("res://src/world/moving_spec.gd")

const DISPLAY := "Pallet Annex"
const MAP_ID := "storage"
const ALL_ZONES := [
	"west_floor", "mid_floor", "east_floor", "office_loft",
	"west_catwalk", "mid_catwalk", "east_catwalk"
]
const SPAWN_ZONE := {
	0: "west_floor",
	1: "mid_floor",
	2: "east_floor",
}
const LADDER_WEST_X := 328.0
const LADDER_MID_X := 520.0
const LADDER_EAST_X := 696.0
const STAND_OFFICE_X := 608.0
const STAND_OFFICE_Y := 168.0
const DOOR_PLATE_X := 256.0
const STAND_WEST_CAT_X := 400.0
const STAND_MID_CAT_X := 560.0
const STAND_EAST_CAT_X := 736.0
const STAND_EAST_LAND_X := 816.0
const STAND_WEST_Y := 24.0
const STAND_LAND_Y := 72.0
const STAND_MID_Y := 88.0
const STAND_CAT_Y := 72.0
const STAND_HIGH_Y := 24.0
const STAND_FLOOR_Y := 168.0
const STAND_EAST_FLOOR_X := 968.0
const STAND_MID_FLOOR_X := 416.0
const COVER_AT := Vector2(200, 168)
const CARGO_AT := Vector2(424, 24)

static var used_step_fixed: int = 0
static var used_apply_frames: int = 0
static var used_apply_frames_attempted: int = 0
static var used_apply_frames_succeeded: int = 0
static var used_parse_input_event: int = 0
static var used_action_press: int = 0
static var outcome_name: Dictionary = {}
static var outcome_cover: Dictionary = {}
static var outcome_cargo: Dictionary = {}
static var outcome_spawn: Dictionary = {}
static var outcome_camera: Dictionary = {}
static var outcome_weapon: Dictionary = {}
static var outcome_p1: Dictionary = {}
static var outcome_p2: Dictionary = {}
static var outcome_bot: Dictionary = {}
static var outcome_zone: Dictionary = {}
static var outcome_door: Dictionary = {}
static var outcome_live: Dictionary = {}
static var outcome_replay: Dictionary = {}
static var outcome_cover_still: Dictionary = {}
static var outcome_catwalk_still: Dictionary = {}
static var outcome_cargo_still: Dictionary = {}
static var outcome_office_still: Dictionary = {}
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
static var _office_standing: bool = false
static var _east_catwalk_live: bool = false


static func run_all(app: App) -> PackedStringArray:
	used_step_fixed = 0
	used_apply_frames = 0
	used_apply_frames_attempted = 0
	used_apply_frames_succeeded = 0
	used_parse_input_event = 0
	used_action_press = 0
	outcome_name = {"verdict": "unproven"}
	outcome_cover = {"verdict": "unproven"}
	outcome_cargo = {"verdict": "unproven"}
	outcome_spawn = {"verdict": "unproven"}
	outcome_camera = {"verdict": "unproven"}
	outcome_weapon = {"verdict": "unproven"}
	outcome_p1 = {"verdict": "unproven"}
	outcome_p2 = {"verdict": "unproven"}
	outcome_bot = {"verdict": "unproven"}
	outcome_zone = {"verdict": "unproven"}
	outcome_door = {"verdict": "unproven"}
	outcome_live = {"verdict": "unproven"}
	outcome_replay = {"verdict": "unproven", "pairs": []}
	outcome_cover_still = {}
	outcome_catwalk_still = {}
	outcome_cargo_still = {}
	outcome_office_still = {}
	snapshot_start = {}
	snapshot_end = {}
	events_all = []
	live_hits_p1 = {}
	live_hits_p2 = {}
	live_hits_bot = {}
	_office_standing = false
	_east_catwalk_live = false
	_climb_up_on_ladder = 0
	_climbing_frames = 0
	var errors: PackedStringArray = PackedStringArray()
	_append(errors, schema_and_name())
	_append(errors, await _capture_start(app))
	_append(errors, await p1_reaches(app))
	_append(errors, await p2_reaches(app))
	_append(errors, await bot_reaches(app))
	_append(errors, live_zone_union())
	_append(errors, await cover_blocks_then_breaks(app))
	_append(errors, await cargo_interacts(app))
	_append(errors, await door_office_route(app))
	_append(errors, await camera_fits(app))
	_append(errors, await weapons_safe(app))
	_append(errors, await live_identity(app))
	_append(errors, replay_hash())
	_append(errors, _require_outcomes())
	return errors


static func schema_and_name() -> PackedStringArray:
	var errors: PackedStringArray = _MapCatalog.validate()
	_append(errors, _ArenaSpec.validate())
	_append(errors, _MapValidator.validate_map(MAP_ID))
	_append(errors, _Moving.validate())
	if Maps.display_name(MAP_ID) != DISPLAY:
		errors.append("NAME storage display must be Pallet Annex")
	if Maps.display_name(MAP_ID).to_lower().contains("superfighter"):
		errors.append("NAME uses Superfighters trademark")
	if Maps.display_name(MAP_ID) == "Storage":
		errors.append("NAME must retire Storage display")
	if str(_ArenaSpec.map_row(MAP_ID).get("display_name", "")) != DISPLAY:
		errors.append("NAME ArenaSpec display must be Pallet Annex")
	var doc: Dictionary = _MapCatalog.document(MAP_ID)
	if bool(doc.get("y8_parity_claimed", true)):
		errors.append("NAME claimed Y8 parity")
	if str(doc.get("title", "")) != "Vault Fighters":
		errors.append("NAME title must stay Vault Fighters")
	if Visuals.BG_CITY != "res://assets/bg/bg_city.png":
		errors.append("NAME backdrop must stay original bg_city")
	if _World.placements_for(MAP_ID).size() < 3:
		errors.append("NAME Pallet Annex must place cover and cargo")
	if _Moving.placements_for(MAP_ID).size() < 4:
		errors.append("NAME Pallet Annex must place door and lift")
	if Maps.count_char(MAP_ID, "H") < 6:
		errors.append("NAME missing vertical ladder routes")
	if Maps.count_char(MAP_ID, "c") < 1:
		errors.append("NAME crate tiles must stay on prop layer")
	if Maps.pit_column_count(MAP_ID) != 0:
		errors.append("NAME enclosed warehouse must not add pit columns")
	if _ArenaSpec.weapon_risk(MAP_ID).size() < 2:
		errors.append("NAME missing varied weapon risk")
	outcome_name = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"display": Maps.display_name(MAP_ID),
		"source": "catalog + ArenaSpec Pallet Annex",
	}
	_event("ware_name", {"ok": errors.is_empty(), "display": Maps.display_name(MAP_ID)})
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
	_climb_up_onto(session, 0, LADDER_WEST_X, STAND_WEST_CAT_X, STAND_WEST_Y, 130)
	_settle_on_zone(session, 0, "west_catwalk", STAND_WEST_CAT_X, 40)
	_climb_down_onto(session, 0, LADDER_WEST_X, STAND_FLOOR_Y, 264.0, 90)
	_drive_p1_office(session)
	_drive_p1_mid_and_east(session)
	live_hits_p1 = _track_hits.duplicate()
	_require_hits(errors, "P1", live_hits_p1, ALL_ZONES)
	if p1.dead:
		errors.append("P1 tour must not die")
	if _tour_climb_up < 8:
		errors.append("P1 must hold up on a ladder for multiple frames got %d" % _tour_climb_up)
	if not _office_standing:
		errors.append("P1 must occupy office_loft standing on_floor")
	if not _east_catwalk_live:
		errors.append("P1 missed live east_catwalk")
	outcome_p1 = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"hits": live_hits_p1,
		"dead": p1.dead,
		"climb_up_on_ladder": _tour_climb_up,
		"climbing_frames": _tour_climbing,
		"office_standing": _office_standing,
		"pos": [p1.global_position.x, p1.global_position.y],
		"on_floor": p1.is_on_floor(),
		"source": "apply_frames live body; P1 holds up on ladders through every zone",
	}
	_remember_session(session)
	_event("ware_p1", {
		"ok": errors.is_empty(),
		"hits": live_hits_p1,
		"climb_up_on_ladder": _tour_climb_up,
		"office_standing": _office_standing,
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
	_climb_up_onto(session, 1, LADDER_MID_X, STAND_MID_CAT_X, STAND_MID_Y, 120)
	_hold_slot(session, 12, 1, PackedStringArray())
	live_hits_p2 = _track_hits.duplicate()
	var need: Array = ["mid_floor", "mid_catwalk"]
	_require_hits(errors, "P2", live_hits_p2, need)
	if not _left_spawn(live_hits_p2, 1):
		errors.append("P2 must leave mid_floor spawn and occupy a non-spawn zone")
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
		"source": "apply_frames P2 holds up on mid ladder onto mid_catwalk",
	}
	_event("ware_p2", {"ok": errors.is_empty(), "hits": live_hits_p2, "climb_up_on_ladder": _tour_climb_up})
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
	var ladder_x: float = LADDER_EAST_X
	var board_x: float = STAND_EAST_CAT_X
	var board_y: float = STAND_HIGH_Y
	if bot.global_position.x < 500.0:
		ladder_x = LADDER_MID_X
		board_x = STAND_MID_CAT_X
		board_y = STAND_MID_Y
	_climb_up_onto(session, bot.slot, ladder_x, board_x, board_y, 130)
	_hold_slot(session, 10, bot.slot, PackedStringArray())
	live_hits_bot = _track_hits.duplicate()
	var routed_dead: bool = bot.dead
	if not bot.dead:
		_brain_chase(session, 16)
	var need: Array = ["east_catwalk"]
	if bot.slot != 2:
		need = ["mid_floor", "mid_catwalk"]
	else:
		need = ["east_floor", "east_catwalk"]
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
		"source": "apply_frames vs1 bot holds up on ladder onto a non-spawn zone",
	}
	_event("ware_bot", {"ok": errors.is_empty(), "hits": live_hits_bot, "climb_up_on_ladder": _tour_climb_up})
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
	if not _office_standing:
		errors.append("ZONE office_loft was never occupied standing on_floor")
	if not _east_catwalk_live:
		errors.append("ZONE east_catwalk had no live body")
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
		"union": union_hits,
		"missing": missing,
		"p1_all": p1_all,
		"office_standing": _office_standing,
		"east_catwalk_live": _east_catwalk_live,
		"climb_up_on_ladder": _climb_up_on_ladder,
		"climbing_frames": _climbing_frames,
		"graph_helper": graph_rows,
		"source": "apply_frames live body positions (graph helper only)",
	}
	outcome_spawn = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"p1": live_hits_p1,
		"p2": live_hits_p2,
		"bot": live_hits_bot,
		"source": "live apply_frames bodies reach every spawn combat zone",
	}
	_event("ware_zone", {
		"ok": errors.is_empty(),
		"union": union_hits,
		"climb_up_on_ladder": _climb_up_on_ladder,
		"office_standing": _office_standing,
	})
	return errors


static func cover_blocks_then_breaks(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var owner: WorldOwner = session.world_owner as WorldOwner if session != null else null
	var wood: Node2D = owner.find_by_id("pallet_cover_wood") if owner != null else null
	var glass: Node2D = owner.find_by_id("pallet_cover_glass") if owner != null else null
	if wood == null or glass == null:
		errors.append("COVER missing pallet_cover_wood/glass")
		outcome_cover = {"verdict": "fail", "source": "placements"}
		return errors
	var blocked: bool = owner.has_cover_at(COVER_AT)
	_walk_toward(session, 0, COVER_AT.x + 20.0, 20)
	_hold_slot(session, 6, 0, PackedStringArray(["left"]))
	_press_slot(session, 0, "melee")
	_hold_slot(session, 12, 0, PackedStringArray(["left"]))
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
	var ghost: bool = owner.has_cover_at(COVER_AT)
	if ghost:
		errors.append("COVER AABB still solid after break")
	outcome_cover = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"blocked_before": blocked,
		"breaks": breaks,
		"wood_alive": wood_alive,
		"source": "P2 melee vs pallet_cover_wood on mid floor",
	}
	_event("ware_cover", {"ok": errors.is_empty(), "breaks": breaks})
	return errors


static func cargo_interacts(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var owner: WorldOwner = session.world_owner as WorldOwner if session != null else null
	var cargo: Node2D = owner.find_by_id("pallet_cargo_hang") if owner != null else null
	if cargo == null:
		errors.append("CARGO missing pallet_cargo_hang")
		outcome_cargo = {"verdict": "fail", "source": "placements"}
		return errors
	var hung0: bool = bool(cargo.get("hanging"))
	if not hung0:
		errors.append("CARGO must start hanging")
	_climb_up_onto(session, 0, LADDER_WEST_X, STAND_WEST_CAT_X, STAND_WEST_Y, 130)
	_settle_on_zone(session, 0, "west_catwalk", STAND_WEST_CAT_X, 40)
	_walk_toward(session, 0, 420.0, 48)
	_hold_slot(session, 6, 0, PackedStringArray())
	var swings: int = 0
	while swings < 4:
		_press_slot(session, 0, "melee")
		_hold_slot(session, 8, 0, PackedStringArray(["right"]))
		swings += 1
	_hold_slot(session, 12, 0, PackedStringArray())
	var hung1: bool = cargo != null and bool(cargo.get("hanging"))
	var drops: int = 0
	if owner != null:
		drops = int(owner.drop_events)
	var p1: Fighter = session.player1() if session != null else null
	if hung1:
		errors.append("CARGO hanging crate must drop after melee")
	if drops < 1:
		errors.append("CARGO expected a drop event")
	outcome_cargo = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"hung_before": hung0,
		"hung_after": hung1,
		"pos": [p1.global_position.x, p1.global_position.y] if p1 != null else [0.0, 0.0],
		"drops": drops,
		"source": "P1 melee releases hanging cargo",
	}
	_event("ware_cargo", {"ok": errors.is_empty(), "drops": drops})
	return errors


static func door_office_route(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var owner: WorldOwner = session.world_owner as WorldOwner if session != null else null
	var door: Node2D = owner.find_by_id("annex_door") if owner != null else null
	var p1: Fighter = session.player1() if session != null else null
	if door == null or p1 == null:
		errors.append("DOOR missing annex_door or P1")
		outcome_door = {"verdict": "fail", "source": "movers"}
		return errors
	var closed0: bool = not bool(door.get("door_open"))
	_walk_toward(session, 0, DOOR_PLATE_X, 80)
	_hold_slot(session, 24, 0, PackedStringArray())
	var opened: bool = bool(door.get("door_open"))
	_enter_office_door(session, 0)
	var in_office: bool = _zone_id_at(p1) == "office_loft" and p1.is_on_floor() and not p1.dead
	if not closed0:
		errors.append("DOOR must start closed")
	if not opened:
		errors.append("DOOR must open after standing on the plate")
	if not in_office:
		errors.append("DOOR open must let P1 into office_loft")
	outcome_door = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"closed_before": closed0,
		"opened": opened,
		"in_office": in_office,
		"source": "stand-still plate opens annex_door; live walk into office",
	}
	_event("ware_door", {"ok": errors.is_empty(), "opened": opened, "in_office": in_office})
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
		errors.append("CAMERA live framing does not cover Pallet Annex")
	if not bool(frame.get("centered", false)):
		errors.append("CAMERA must stay arena-centered")
	var val: PackedStringArray = _MapValidator.validate_map(MAP_ID)
	var i: int = 0
	while i < val.size():
		if String(val[i]).contains("camera"):
			errors.append(String(val[i]))
		i += 1
	outcome_camera = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"covers_arena": bool(frame.get("covers_arena", false)),
		"centered": bool(frame.get("centered", false)),
		"arena_size": [size.x, size.y],
		"source": "GameSession.camera_framing + MapValidator",
	}
	_event("ware_camera", {"ok": errors.is_empty(), "covers": bool(frame.get("covers_arena", false))})
	return errors


static func weapons_safe(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	if session == null or session.arena == null:
		errors.append("WEAPON missing session")
		outcome_weapon = {"verdict": "fail"}
		return errors
	_append(errors, _ArenaSpec.validate_weapon_cells_safe(MAP_ID))
	var spots: Array[Vector2] = session.arena.weapon_spawns
	if spots.size() < 2:
		errors.append("WEAPON missing live spawn marks")
	var i: int = 0
	while i < spots.size():
		var at: Vector2 = spots[i]
		if Maps.solid_at(MAP_ID, at):
			errors.append("WEAPON spawn inside solid at %s" % str(at))
		i += 1
	if session.pickups.is_empty():
		errors.append("WEAPON live pickups missing")
	var homes_ok: int = 0
	var pi: int = 0
	while pi < session.pickups.size():
		var drop: Pickup = session.pickups[pi] as Pickup
		if drop != null and drop.from_world:
			if Maps.solid_at(MAP_ID, drop.home):
				errors.append("WEAPON respawn home is inside solid")
			else:
				homes_ok += 1
		pi += 1
	if homes_ok < 2:
		errors.append("WEAPON need 2+ walkable respawn homes")
	outcome_weapon = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"spots": spots.size(),
		"pickups": session.pickups.size(),
		"homes_ok": homes_ok,
		"respawn_tuning": Maps.WEAPON_RESPAWN,
		"source": "layered pickup cells + live world homes stay walkable",
	}
	_event("ware_weapon", {"ok": errors.is_empty(), "spots": spots.size()})
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
			# Title defaults to rooftops; cycle until Pallet Annex is shown.
			var hops: int = 0
			while hops < 8 and app.title.map_btn != null and not str(app.title.map_btn.text).contains(DISPLAY):
				app.title.map_btn.emit_signal("pressed")
				hops += 1
			if app.title.map_btn != null and not str(app.title.map_btn.text).contains(DISPLAY):
				errors.append("LIVE title map button missing Pallet Annex")
		if app.title.get_node_or_null("TitleLabel") != null:
			var title_txt: String = (app.title.get_node_or_null("TitleLabel") as Label).text
			if title_txt != "Vault Fighters":
				errors.append("LIVE title card drifted")
			if title_txt.to_lower().contains("superfighter"):
				errors.append("LIVE title uses Superfighters trademark")
	outcome_live = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"hud": shown,
		"source": "HUD + title display Pallet Annex",
	}
	_event("ware_live", {"ok": errors.is_empty(), "hud": shown})
	return errors


static func replay_hash() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var a: String = _MapCodec.stable_hash(_MapCatalog.document(MAP_ID))
	_MapCatalog.reload()
	var b: String = _MapCodec.stable_hash(_MapCatalog.document(MAP_ID))
	var ok: bool = a != "" and a == b
	if not ok:
		errors.append("REPLAY storage reload hash mismatch")
	outcome_replay = {
		"verdict": "match" if ok else "fail",
		"pairs": [{"id": MAP_ID, "match": ok, "hash": a}],
		"source": "catalog reload hash twice",
	}
	_event("ware_replay", {"ok": ok, "hash": a})
	return errors


static func stage_catwalk(app: App) -> void:
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_begin_track(0)
	_climb_up_onto(session, 0, LADDER_WEST_X, STAND_WEST_CAT_X, STAND_WEST_Y, 130)
	_settle_on_zone(session, 0, "west_catwalk", STAND_WEST_CAT_X, 40)
	_hold_slot(session, 16, 0, PackedStringArray())
	outcome_catwalk_still = _still_row(session, 0, app, false)
	if session != null:
		session.set_paused(true, RuntimeConstants.REASON_PLAYER)


static func stage_cover(app: App) -> void:
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_begin_track(0)
	_walk_toward(session, 0, COVER_AT.x + 20.0, 20)
	_hold_slot(session, 16, 0, PackedStringArray())
	outcome_cover_still = _still_row(session, 0, app, false)
	if session != null:
		session.set_paused(true, RuntimeConstants.REASON_PLAYER)


static func stage_cargo(app: App) -> void:
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_begin_track(0)
	_climb_up_onto(session, 0, LADDER_WEST_X, STAND_WEST_CAT_X, STAND_WEST_Y, 130)
	_settle_on_zone(session, 0, "west_catwalk", STAND_WEST_CAT_X, 40)
	_walk_toward(session, 0, 420.0, 24)
	_hold_slot(session, 16, 0, PackedStringArray())
	outcome_cargo_still = _still_row(session, 0, app, false)
	if session != null:
		session.set_paused(true, RuntimeConstants.REASON_PLAYER)


static func stage_office(app: App) -> void:
	app.start_fight("vs2", MAP_ID, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_begin_track(0)
	_drive_p1_office(session)
	_hold_slot(session, 16, 0, PackedStringArray())
	outcome_office_still = _still_row(session, 0, app, false)
	if session != null:
		session.set_paused(true, RuntimeConstants.REASON_PLAYER)


static func _drive_p1_office(session: GameSession) -> void:
	_walk_toward(session, 0, DOOR_PLATE_X, 80)
	_hold_slot(session, 24, 0, PackedStringArray())
	_enter_office_door(session, 0)


static func _drop_onto_west_catwalk(session: GameSession, slot: int) -> void:
	_approach_ladder(session, slot, LADDER_WEST_X)
	var n: int = 0
	while n < 140:
		var fighter: Fighter = _slot(session, slot)
		if fighter == null or fighter.dead:
			return
		if fighter.hanging or fighter.recover_left > 0.0:
			_press_slot(session, slot, "jump")
			_hold_slot(session, 16, slot, PackedStringArray(["jump"]))
			n += 8
			continue
		if fighter.global_position.y <= 18.0:
			break
		_hold_slot(session, 1, slot, PackedStringArray(["up"]))
		n += 1
	n = 0
	while n < 28:
		var fighter: Fighter = _slot(session, slot)
		if fighter == null or fighter.dead:
			return
		if fighter.hanging:
			_press_slot(session, slot, "jump")
			_hold_slot(session, 12, slot, PackedStringArray(["jump", "left"]))
			n += 6
			continue
		if (
			fighter.is_on_floor()
			and not fighter.climbing
			and fighter.global_position.y <= STAND_WEST_Y + 10.0
			and fighter.global_position.x <= 304.0
		):
			break
		_hold_slot(session, 1, slot, PackedStringArray(["left"]))
		n += 1
	_walk_toward(session, slot, STAND_WEST_CAT_X, 40)
	_hold_slot(session, 12, slot, PackedStringArray())


static func _enter_office_door(session: GameSession, slot: int) -> void:
	_walk_toward(session, slot, STAND_OFFICE_X, 120)
	_settle_on_zone(session, slot, "office_loft", STAND_OFFICE_X, 40)


static func _vault_into_office(session: GameSession, slot: int) -> void:
	_walk_toward(session, slot, 152.0, 90)
	var mounted: int = 0
	while mounted < 36:
		var fighter: Fighter = _slot(session, slot)
		if fighter == null or fighter.dead:
			return
		if fighter.is_on_floor() and fighter.global_position.y <= 128.0:
			break
		_hold_slot(session, 1, slot, PackedStringArray(["left", "jump"]))
		mounted += 1
	_walk_toward(session, slot, 128.0, 24)
	var n: int = 0
	while n < 6:
		_hold_slot(session, 1, slot, PackedStringArray(["left", "jump"]))
		n += 1
	n = 0
	while n < 24:
		_hold_slot(session, 1, slot, PackedStringArray(["left"]))
		n += 1
	_walk_toward(session, slot, STAND_OFFICE_X, 48)
	_hold_slot(session, 12, slot, PackedStringArray())


static func _drive_p1_mid_and_east(session: GameSession) -> void:
	_walk_toward(session, 0, STAND_MID_FLOOR_X, 160)
	_settle_on_zone(session, 0, "mid_floor", STAND_MID_FLOOR_X, 40)
	_walk_toward(session, 0, LADDER_MID_X, 80)
	_climb_up_onto(session, 0, LADDER_MID_X, STAND_MID_CAT_X, STAND_MID_Y, 120)
	_climb_down_onto(session, 0, LADDER_MID_X, STAND_FLOOR_Y, STAND_MID_FLOOR_X, 80)
	_settle_on_zone(session, 0, "mid_floor", STAND_MID_FLOOR_X, 40)
	_walk_toward(session, 0, LADDER_EAST_X, 180)
	_climb_up_onto(session, 0, LADDER_EAST_X, STAND_EAST_LAND_X, STAND_LAND_Y, 120)
	_climb_up_onto(session, 0, LADDER_EAST_X, STAND_EAST_CAT_X, STAND_HIGH_Y, 130)
	_climb_down_onto(session, 0, LADDER_EAST_X, STAND_FLOOR_Y, STAND_EAST_FLOOR_X, 80)
	_hold_slot(session, 12, 0, PackedStringArray())


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


static func _walk_toward(session: GameSession, slot: int, target_x: float, max_ticks: int) -> void:
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
			return
		var dx: float = target_x - fighter.global_position.x
		if absf(dx) <= 4.0:
			return
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
	var zones: Array = _ArenaSpec.combat_zones(MAP_ID)
	var i: int = 0
	while i < zones.size():
		var zone: Dictionary = zones[i] as Dictionary
		var zid: String = str(zone.get("id", ""))
		if _ArenaSpec.zone_contains(zone, fighter.global_position):
			if not bool(hits.get(zid, false)):
				_event("ware_zone_hit", {
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
	if zid == "office_loft" and fighter.is_on_floor() and not fighter.hanging and not fighter.dead:
		_office_standing = true
	if zid == "east_catwalk" and not fighter.dead:
		_east_catwalk_live = true


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
		outcome_name, outcome_cover, outcome_cargo, outcome_spawn, outcome_camera,
		outcome_weapon, outcome_p1, outcome_p2, outcome_bot, outcome_zone,
		outcome_door, outcome_live
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

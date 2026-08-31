class_name VsRosterCases
extends RefCounted

## VF5-WP6 six-map VS roster. Stage stays four ids. Draft Yard is
## author-only. Unique beats use apply_frames live bodies.
## 60 Hz is ledger:RL-SIM-FIXED-60 (assumption). Not Y8 observed.

const RooftopCasesScript: GDScript = preload("res://tests/rooftop_cases.gd")
const WarehouseCasesScript: GDScript = preload("res://tests/warehouse_cases.gd")
const SewerCasesScript: GDScript = preload("res://tests/sewer_cases.gd")
const _MapCatalog: GDScript = preload("res://src/maps/map_catalog.gd")
const _MapCodec: GDScript = preload("res://src/maps/map_codec.gd")
const _MapValidator: GDScript = preload("res://src/maps/map_validator.gd")
const _MapGraph: GDScript = preload("res://src/maps/map_graph.gd")

const VS_IDS := ["rooftops", "storage", "police", "hazardous", "lantern", "gauge"]
const STAGE_IDS := ["rooftops", "storage", "police", "hazardous"]
const AUTHOR_ID := "fx_map_author"
const DISPLAY := {
	"rooftops": "Skyline Relay",
	"storage": "Pallet Annex",
	"police": "Signal Court",
	"hazardous": "Vitriol Sump",
	"lantern": "Lantern Cut",
	"gauge": "Gauge Deck",
}
const UNIQUE := {
	"rooftops": "cover",
	"storage": "cargo",
	"police": "rotor",
	"hazardous": "toxic_pickup",
	"lantern": "water",
	"gauge": "lift",
}
const LANTERN_LADDER_X := 72.0
const LANTERN_WATER_X := 72.0
const LANTERN_LINE_X := 384.0
const GAUGE_LADDER_X := 72.0
const GAUGE_PLATE_X := 960.0
const GAUGE_LIFT_X := 992.0
const GAUGE_LOFT_X := 1000.0

static var used_step_fixed: int = 0
static var used_apply_frames: int = 0
static var used_apply_frames_attempted: int = 0
static var used_apply_frames_succeeded: int = 0
static var used_parse_input_event: int = 0
static var used_action_press: int = 0
static var outcome_roster: Dictionary = {}
static var outcome_cycle: Dictionary = {}
static var outcome_load: Dictionary = {}
static var outcome_routes: Dictionary = {}
static var outcome_cover: Dictionary = {}
static var outcome_cargo: Dictionary = {}
static var outcome_door: Dictionary = {}
static var outcome_rotor: Dictionary = {}
static var outcome_toxic: Dictionary = {}
static var outcome_water: Dictionary = {}
static var outcome_lift: Dictionary = {}
static var outcome_lantern: Dictionary = {}
static var outcome_gauge: Dictionary = {}
static var outcome_p2: Dictionary = {}
static var outcome_bot: Dictionary = {}
static var outcome_camera: Dictionary = {}
static var outcome_live: Dictionary = {}
static var outcome_replay: Dictionary = {}
static var snapshot_start: Dictionary = {}
static var snapshot_end: Dictionary = {}
static var events_all: Array = []
static var outcome_still: Dictionary = {}


static func run_all(app: App) -> PackedStringArray:
	used_step_fixed = 0
	used_apply_frames = 0
	used_apply_frames_attempted = 0
	used_apply_frames_succeeded = 0
	used_parse_input_event = 0
	used_action_press = 0
	outcome_roster = {"verdict": "unproven"}
	outcome_cycle = {"verdict": "unproven"}
	outcome_load = {"verdict": "unproven"}
	outcome_routes = {"verdict": "unproven"}
	outcome_cover = {"verdict": "unproven"}
	outcome_cargo = {"verdict": "unproven"}
	outcome_door = {"verdict": "unproven"}
	outcome_rotor = {"verdict": "unproven"}
	outcome_toxic = {"verdict": "unproven"}
	outcome_water = {"verdict": "unproven"}
	outcome_lift = {"verdict": "unproven"}
	outcome_lantern = {"verdict": "unproven"}
	outcome_gauge = {"verdict": "unproven"}
	outcome_p2 = {"verdict": "unproven"}
	outcome_bot = {"verdict": "unproven"}
	outcome_camera = {"verdict": "unproven"}
	outcome_live = {"verdict": "unproven"}
	outcome_replay = {"verdict": "unproven"}
	snapshot_start = {}
	snapshot_end = {}
	events_all = []
	var errors: PackedStringArray = PackedStringArray()
	_append(errors, schema_and_roster())
	_append(errors, cycle_wraps())
	_append(errors, await load_all_six(app))
	_append(errors, routes_spawns_weapons())
	_append(errors, await cameras_fit(app))
	_append(errors, await unique_cover(app))
	_append(errors, await unique_cargo(app))
	_append(errors, await unique_door(app))
	_append(errors, await unique_rotor(app))
	_append(errors, await unique_toxic(app))
	_append(errors, await unique_water(app))
	_append(errors, await unique_lift(app))
	_append(errors, await lantern_live_routes(app))
	_append(errors, await gauge_live_routes(app))
	_append(errors, await p2_bot_smoke(app))
	_append(errors, await live_identity(app))
	_append(errors, replay_hashes())
	_append(errors, _require_outcomes())
	return errors


static func schema_and_roster() -> PackedStringArray:
	var errors: PackedStringArray = MapCatalog.validate()
	_append(errors, ArenaSpec.validate())
	if Maps.vs_ids().size() != 6:
		errors.append("ROSTER vs_ids must be six")
	if Maps.stage_ids().size() != 4:
		errors.append("ROSTER stage_ids must stay four")
	if Maps.stage_count() != 4:
		errors.append("ROSTER stage_count must stay 4")
	var i: int = 0
	while i < VS_IDS.size():
		var mid: String = String(VS_IDS[i])
		if i >= Maps.vs_ids().size() or String(Maps.vs_ids()[i]) != mid:
			errors.append("ROSTER vs_ids[%d] must be %s" % [i, mid])
		if Maps.display_name(mid) != str(DISPLAY[mid]):
			errors.append("ROSTER %s display must be %s" % [mid, str(DISPLAY[mid])])
		if str(DISPLAY[mid]).to_lower().contains("superfighter"):
			errors.append("ROSTER %s display uses trademark" % mid)
		if not _MapCatalog.has_id(mid):
			errors.append("ROSTER catalog missing %s" % mid)
		i += 1
	i = 0
	while i < STAGE_IDS.size():
		if i >= Maps.stage_ids().size() or String(Maps.stage_ids()[i]) != String(STAGE_IDS[i]):
			errors.append("ROSTER stage_ids[%d] drifted" % i)
		i += 1
	if Maps.vs_ids().has(AUTHOR_ID):
		errors.append("ROSTER Draft Yard must not enter vs_ids")
	if Maps.stage_ids().has("lantern") or Maps.stage_ids().has("gauge"):
		errors.append("ROSTER Stage must stay the four explicit ids")
	if Maps.display_name(AUTHOR_ID) != "Draft Yard":
		errors.append("ROSTER author display must stay Draft Yard")
	var catalog_ids: PackedStringArray = _MapCatalog.ids()
	var extra: PackedStringArray = PackedStringArray()
	i = 0
	while i < catalog_ids.size():
		var cid: String = String(catalog_ids[i])
		if cid != AUTHOR_ID and not VS_IDS.has(cid):
			extra.append(cid)
		i += 1
	if not extra.is_empty():
		errors.append("ROSTER hidden catalog maps %s" % ",".join(extra))
	outcome_roster = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"vs": VS_IDS,
		"stage": STAGE_IDS,
		"author": AUTHOR_ID,
		"unique": UNIQUE,
		"source": "Maps.vs_ids + catalog required_live_ids",
	}
	_event("roster", {"ok": errors.is_empty()})
	return errors


static func cycle_wraps() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var seen: PackedStringArray = PackedStringArray()
	var cur: String = "rooftops"
	var i: int = 0
	while i < 6:
		seen.append(cur)
		cur = Maps.next_vs_map(cur)
		i += 1
	i = 0
	while i < VS_IDS.size():
		if String(seen[i]) != String(VS_IDS[i]):
			errors.append("CYCLE order[%d] is %s" % [i, String(seen[i])])
		i += 1
	if cur != "rooftops":
		errors.append("CYCLE wrap must return to rooftops got %s" % cur)
	if Maps.next_vs_map("gauge") != "rooftops":
		errors.append("CYCLE gauge must wrap to rooftops")
	if Maps.next_vs_map("missing") != "rooftops":
		errors.append("CYCLE unknown map must fall back to rooftops")
	outcome_cycle = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"seen": Array(seen),
		"wrap": cur,
		"source": "Maps.next_vs_map stable order, not filesystem sort",
	}
	_event("cycle", {"ok": errors.is_empty(), "wrap": cur})
	return errors


static func load_all_six(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var loaded: Array = []
	var i: int = 0
	while i < VS_IDS.size():
		var mid: String = String(VS_IDS[i])
		app.start_fight("vs2", mid, 0)
		await SimReplay.sync_physics(app)
		var session: GameSession = app.session
		if session == null or session.world == null or session.player1() == null:
			errors.append("LOAD %s failed to build" % mid)
		elif session.player1().dead:
			errors.append("LOAD %s P1 dead at spawn" % mid)
		else:
			loaded.append(mid)
			if i == 0:
				snapshot_start = {
					"map": mid,
					"x": session.player1().global_position.x,
					"y": session.player1().global_position.y,
				}
		i += 1
	outcome_load = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"loaded": loaded,
		"source": "start_fight vs2 each VS id",
	}
	_event("load", {"ok": errors.is_empty(), "n": loaded.size()})
	return errors


static func routes_spawns_weapons() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var rows: Array = []
	var i: int = 0
	while i < VS_IDS.size():
		var mid: String = String(VS_IDS[i])
		_append(errors, _MapValidator.validate_map(mid))
		var doc: Dictionary = _MapCatalog.document(mid)
		var plats: Array = _MapGraph.platforms(doc)
		var elev: int = _MapGraph.elevation_count(doc)
		var spawns: Array = ArenaSpec.spawn_points(mid)
		var weapons: Array = _MapCodec.layer_cells(doc, "pickup")
		if plats.size() < 2:
			errors.append("ROUTES %s needs >=2 platforms" % mid)
		if elev < 2:
			errors.append("ROUTES %s needs >=2 elevations" % mid)
		if Maps.count_char(mid, "H") < 1:
			errors.append("ROUTES %s missing ladder" % mid)
		if spawns.size() < 2:
			errors.append("SPAWN %s needs P1/P2 marks" % mid)
		if weapons.size() < 2:
			errors.append("WEAPON %s needs >=2 pickup cells" % mid)
		rows.append({
			"id": mid,
			"platforms": plats.size(),
			"elevations": elev,
			"spawns": spawns.size(),
			"weapons": weapons.size(),
		})
		i += 1
	outcome_routes = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"maps": rows,
		"source": "MapValidator + MapGraph helper; live unique is apply_frames",
	}
	_event("routes", {"ok": errors.is_empty()})
	return errors


static func cameras_fit(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var fits: Array = []
	var i: int = 0
	while i < VS_IDS.size():
		var mid: String = String(VS_IDS[i])
		app.start_fight("vs2", mid, 0)
		await SimReplay.sync_physics(app)
		var session: GameSession = app.session
		if session == null:
			errors.append("CAMERA missing session %s" % mid)
			i += 1
			continue
		var frame: Dictionary = session.camera_framing()
		var size: Vector2 = Maps.pixel_size(mid)
		if size.x > 1280.0 or size.y > 720.0:
			errors.append("CAMERA %s pixel size exceeds 1280x720" % mid)
		if not bool(frame.get("covers_arena", false)):
			errors.append("CAMERA %s does not cover arena" % mid)
		if not bool(frame.get("centered", false)):
			errors.append("CAMERA %s not centered" % mid)
		fits.append({"id": mid, "covers": bool(frame.get("covers_arena", false))})
		i += 1
	outcome_camera = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"maps": fits,
		"source": "live camera_framing after start_fight",
	}
	_event("camera", {"ok": errors.is_empty()})
	return errors


static func unique_cover(app: App) -> PackedStringArray:
	var snap: Dictionary = _snap_counts(RooftopCasesScript)
	var errors: PackedStringArray = await RooftopCasesScript.cover_breaks(app)
	_add_apply_delta(RooftopCasesScript, snap)
	outcome_cover = RooftopCasesScript.outcome_cover.duplicate(true)
	if str(outcome_cover.get("verdict", "")) != "pass":
		errors.append("COVER unique rooftops failed")
	_event("cover", {"ok": errors.is_empty()})
	return errors


static func unique_cargo(app: App) -> PackedStringArray:
	var snap: Dictionary = _snap_counts(WarehouseCasesScript)
	var errors: PackedStringArray = await WarehouseCasesScript.cargo_interacts(app)
	_add_apply_delta(WarehouseCasesScript, snap)
	outcome_cargo = WarehouseCasesScript.outcome_cargo.duplicate(true)
	if str(outcome_cargo.get("verdict", "")) != "pass":
		errors.append("CARGO unique storage failed")
	_event("cargo", {"ok": errors.is_empty()})
	return errors


static func unique_door(app: App) -> PackedStringArray:
	var snap: Dictionary = _snap_counts(WarehouseCasesScript)
	var errors: PackedStringArray = await WarehouseCasesScript.door_office_route(app)
	_add_apply_delta(WarehouseCasesScript, snap)
	outcome_door = WarehouseCasesScript.outcome_door.duplicate(true)
	if str(outcome_door.get("verdict", "")) != "pass":
		errors.append("DOOR unique storage failed")
	_event("door", {"ok": errors.is_empty()})
	return errors


static func unique_rotor(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "police", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var owner: WorldOwner = session.world_owner as WorldOwner if session != null else null
	var rotor: Node2D = owner.find_by_id("signal_rotor") if owner != null else null
	var p1: Fighter = session.player1() if session != null else null
	if rotor == null or p1 == null:
		errors.append("ROTOR missing signal_rotor or P1")
		outcome_rotor = {"verdict": "fail", "used_give_weapon": false, "source": "env placement"}
		return errors
	var start_weapon: String = p1.weapon_id
	var a0: float = float(rotor.get("angle"))
	_hold_slot(session, 12, 0, PackedStringArray())
	var a1: float = float(rotor.get("angle"))
	if a1 <= a0 + 1.0:
		errors.append("ROTOR rotor must spin before the shot")
	_walk_toward(session, 0, 232.0, 90)
	_walk_toward(session, 0, 168.0, 100, true)
	_walk_toward(session, 0, 156.0, 80)
	_hold_slot(session, 8, 0, PackedStringArray(["left"]))
	p1 = session.player1()
	var held_weapon: String = p1.weapon_id if p1 != null else ""
	var n: int = 0
	while n < 8 and not bool(rotor.get("jammed")):
		_fire_semi(session, 0, "left")
		n += 1
	_hold_slot(session, 8, 0, PackedStringArray())
	var jammed: bool = bool(rotor.get("jammed"))
	var jams: int = int(owner.get("rotor_jams")) if owner != null else 0
	var shots: int = int(owner.get("rotor_shots")) if owner != null else 0
	var jam_events: int = 0
	if session.ledger != null:
		jam_events = session.ledger.count_kind("rotor_jam")
	if not jammed:
		errors.append("ROTOR shootable rotor must jam")
	if jams < 1 or jam_events < 1:
		errors.append("ROTOR missing rotor_jam event jams=%d ledger=%d" % [jams, jam_events])
	if shots < 1:
		errors.append("ROTOR expected a live bullet hit on the rotor")
	if held_weapon == "" or held_weapon == "fists":
		errors.append("ROTOR must fire the starting gun, not fists")
	var a2: float = float(rotor.get("angle"))
	_hold_slot(session, 10, 0, PackedStringArray())
	var a3: float = float(rotor.get("angle"))
	if jammed and a3 > a2 + 1.0:
		errors.append("ROTOR jammed rotor must stop spinning")
	outcome_rotor = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"spin_before": a1 > a0 + 1.0,
		"jammed": jammed,
		"jams": jams,
		"shots": shots,
		"ledger_jam": jam_events,
		"start_weapon": start_weapon,
		"held_weapon": held_weapon,
		"used_give_weapon": false,
		"source": "apply_frames walk + starting pistol fire jams signal_rotor; no give_weapon",
	}
	_event("rotor", {"ok": errors.is_empty(), "jammed": jammed, "jams": jams})
	return errors


static func unique_toxic(app: App) -> PackedStringArray:
	var snap: Dictionary = _snap_counts(SewerCasesScript)
	var errors: PackedStringArray = await SewerCasesScript.tactic_changes(app)
	_add_apply_delta(SewerCasesScript, snap)
	outcome_toxic = SewerCasesScript.outcome_tactic.duplicate(true)
	if str(outcome_toxic.get("verdict", "")) != "pass":
		errors.append("TOXIC unique hazardous failed")
	if bool(outcome_toxic.get("used_give_weapon", true)):
		errors.append("TOXIC must stay a world pickup")
	_event("toxic", {"ok": errors.is_empty()})
	return errors


static func unique_water(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "lantern", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1() if session != null else null
	var owner: WorldOwner = session.world_owner as WorldOwner if session != null else null
	if p1 == null or owner == null:
		errors.append("WATER missing P1 or owner")
		outcome_water = {"verdict": "fail"}
		return errors
	var gutter: Node2D = owner.find_by_id("cut_gutter_01")
	if gutter == null:
		errors.append("WATER missing cut_gutter_01")
	var wet0: bool = p1.wet
	_hold_slot(session, 8, 0, PackedStringArray())
	p1 = session.player1()
	if p1 == null or not p1.is_on_floor():
		errors.append("WATER dry measure needs a standing stoop")
	var dx_dry: float = _measure_walk_dx(session, 0, "right", 16)
	p1 = session.player1()
	if p1 != null and p1.wet:
		errors.append("WATER stoop walk must stay dry")
	_walk_toward(session, 0, LANTERN_LADDER_X, 40)
	_climb_to_clothesline(session, 0)
	_walk_toward(session, 0, LANTERN_LINE_X, 90)
	_hold_slot(session, 10, 0, PackedStringArray())
	_climb_down_to_street(session, 0)
	_walk_toward(session, 0, LANTERN_WATER_X, 80)
	_hold_slot(session, 8, 0, PackedStringArray())
	p1 = session.player1()
	var wet1: bool = p1 != null and p1.wet
	var inside: String = p1.env_inside_id if p1 != null else ""
	if wet0:
		errors.append("WATER must start dry on the stoop")
	if not wet1:
		errors.append("WATER live walk must set fighter.wet")
	if inside == "" or not inside.begins_with("cut_gutter"):
		errors.append("WATER env_id must come from the live gutter body got %s" % inside)
	var dx_wet: float = 0.0
	var sprint_blocked: bool = false
	if wet1:
		dx_wet = _measure_walk_dx(session, 0, "right", 16)
		p1 = session.player1()
		if p1 == null or not p1.wet:
			errors.append("WATER wet measure must stay overlapping the gutter")
		_hold_slot(session, 1, 0, PackedStringArray(["right"]))
		_hold_slot(session, 2, 0, PackedStringArray())
		_hold_slot(session, 8, 0, PackedStringArray(["right"]))
		p1 = session.player1()
		sprint_blocked = p1 != null and p1.wet and not p1.sprinting
		if not sprint_blocked:
			errors.append("WATER must block sprint on the wet body")
	if dx_dry <= 8.0:
		errors.append("WATER dry walk must move the stoop body")
	if wet1 and dx_wet <= 1.0:
		errors.append("WATER wet walk must still move")
	if wet1 and dx_dry > 8.0 and dx_wet >= dx_dry * 0.85:
		errors.append("WATER wet walk must be slower than dry dx_dry=%s dx_wet=%s" % [dx_dry, dx_wet])
	outcome_water = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"wet_before": wet0,
		"wet_after": wet1,
		"env_id": inside,
		"dx_dry": dx_dry,
		"dx_wet": dx_wet,
		"walk_ratio": (dx_wet / dx_dry) if dx_dry > 0.0 else 0.0,
		"sprint_blocked": sprint_blocked,
		"x": p1.global_position.x if p1 != null else 0.0,
		"y": p1.global_position.y if p1 != null else 0.0,
		"source": "apply_frames stoop walk vs gutter walk; wet slows and blocks sprint",
	}
	_event("water", {"ok": errors.is_empty(), "wet": wet1, "dx_dry": dx_dry, "dx_wet": dx_wet})
	return errors


static func unique_lift(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "gauge", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1() if session != null else null
	var owner: WorldOwner = session.world_owner as WorldOwner if session != null else null
	var lift: Node2D = owner.find_by_id("gauge_lift") if owner != null else null
	if p1 == null or lift == null:
		errors.append("LIFT missing P1 or gauge_lift")
		outcome_lift = {"verdict": "fail"}
		return errors
	var y0: float = p1.global_position.y
	var ly0: float = lift.global_position.y
	_climb_down_gauge(session, 0)
	_walk_toward(session, 0, 168.0, 80)
	_hold_slot(session, 16, 0, PackedStringArray())
	_walk_toward(session, 0, GAUGE_LIFT_X, 420)
	var n: int = 0
	while n < 90:
		_hold_slot(session, 1, 0, PackedStringArray())
		if str(lift.get("phase")) == "dwell" and lift.global_position.y < ly0 - 16.0:
			break
		n += 1
	p1 = session.player1()
	var y1: float = p1.global_position.y if p1 != null else y0
	var ly1: float = lift.global_position.y
	var boards: int = int(owner.get("board_events")) if owner != null else 0
	if ly1 >= ly0 - 16.0:
		errors.append("LIFT car must travel toward the loft")
	if y1 >= y0 - 16.0:
		errors.append("LIFT P1 must rise with the car")
	if boards < 1:
		errors.append("LIFT expected a board event")
	outcome_lift = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"y0": y0,
		"y1": y1,
		"ly0": ly0,
		"ly1": ly1,
		"boards": boards,
		"source": "apply_frames walk to gauge_lift_plate then ride shaft_lift",
	}
	_event("lift", {"ok": errors.is_empty(), "boards": boards})
	return errors


static func lantern_live_routes(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "lantern", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var hits: Dictionary = {}
	_begin_mark(session, 0, hits)
	_hold_slot(session, 8, 0, PackedStringArray())
	_walk_toward(session, 0, LANTERN_LADDER_X, 40)
	_climb_to_clothesline(session, 0)
	_walk_toward(session, 0, LANTERN_LINE_X, 90)
	_hold_slot(session, 10, 0, PackedStringArray())
	_climb_down_to_street(session, 0)
	var p1: Fighter = session.player1()
	var zones: int = _hit_count(hits)
	if zones < 2:
		errors.append("LANTERN P1 must occupy >=2 combat zones live got %d" % zones)
	if not bool(hits.get("clothesline", false)) and not bool(hits.get("west_high", false)):
		errors.append("LANTERN P1 must use a vertical / clothesline route")
	if p1 == null or p1.dead:
		errors.append("LANTERN P1 died on the live route")
	_end_mark()
	outcome_lantern = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"hits": hits,
		"zones": zones,
		"source": "apply_frames P1 stoop -> ladder -> clothesline -> street",
	}
	_event("lantern", {"ok": errors.is_empty(), "zones": zones})
	return errors


static func gauge_live_routes(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "gauge", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var hits: Dictionary = {}
	_begin_mark(session, 0, hits)
	_climb_down_gauge(session, 0)
	_hold_slot(session, 6, 0, PackedStringArray())
	_climb_up(session, 0, GAUGE_LADDER_X, 90)
	_walk_toward(session, 0, 120.0, 30)
	_hold_slot(session, 8, 0, PackedStringArray())
	var p1: Fighter = session.player1()
	var zones: int = _hit_count(hits)
	if zones < 2:
		errors.append("GAUGE P1 must occupy >=2 combat zones live got %d" % zones)
	if not bool(hits.get("west_loft", false)) and not bool(hits.get("west_rail", false)):
		errors.append("GAUGE P1 must use a vertical loft/rail route")
	if p1 == null or p1.dead:
		errors.append("GAUGE P1 died on the live route")
	_end_mark()
	outcome_gauge = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"hits": hits,
		"zones": zones,
		"source": "apply_frames P1 west floor -> ladder -> loft/rail",
	}
	_event("gauge", {"ok": errors.is_empty(), "zones": zones})
	return errors


static func p2_bot_smoke(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "lantern", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p2: Fighter = _slot(session, 1)
	var x0: float = p2.global_position.x if p2 != null else 0.0
	_walk_toward(session, 1, x0 - 48.0, 40)
	p2 = _slot(session, 1)
	var p2_moved: bool = p2 != null and absf(p2.global_position.x - x0) > 4.0 and not p2.dead
	if not p2_moved:
		errors.append("P2 smoke walk on Lantern Cut did not move")
	app.start_fight("vs1", "gauge", 0)
	await SimReplay.sync_physics(app)
	session = app.session
	var bot: Fighter = _first_bot(session)
	var bx0: float = bot.global_position.x if bot != null else 0.0
	var n: int = 0
	while n < 40:
		_hold_slot(session, 1, 0, PackedStringArray())
		n += 1
	bot = _first_bot(session)
	var bot_alive: bool = bot != null and not bot.dead
	if not bot_alive:
		errors.append("BOT smoke on Gauge Deck died immediately")
	outcome_p2 = {
		"verdict": "pass" if p2_moved else "fail",
		"moved": p2_moved,
		"coverage": "smoke",
		"P2_COVERAGE": "smoke",
		"source": "apply_frames P2 short walk; not AI",
	}
	outcome_bot = {
		"verdict": "pass" if bot_alive else "fail",
		"alive": bot_alive,
		"coverage": "smoke",
		"BOT_COVERAGE": "smoke",
		"NOT_AI": 1,
		"x0": bx0,
		"source": "vs1 bot idle smoke; NOT_AI",
	}
	_event("p2bot", {"ok": errors.is_empty()})
	return errors


static func live_identity(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var shown: Array = []
	var i: int = 0
	while i < VS_IDS.size():
		var mid: String = String(VS_IDS[i])
		app.start_fight("vs1", mid, 0)
		await SimReplay.sync_physics(app)
		var session: GameSession = app.session
		var hud_name: String = ""
		if session != null and session.hud != null:
			var map_label: Label = session.hud.get_node_or_null("MapName") as Label
			if map_label != null:
				hud_name = map_label.text
		if hud_name != str(DISPLAY[mid]):
			errors.append("LIVE HUD %s is %s" % [mid, hud_name])
		shown.append(hud_name)
		i += 1
	app.restart_to_title()
	if app.title != null:
		var title_txt: String = ""
		if app.title.get_node_or_null("TitleLabel") != null:
			title_txt = (app.title.get_node_or_null("TitleLabel") as Label).text
		if title_txt != "Vault Fighters":
			errors.append("LIVE title card drifted")
		if title_txt.to_lower().contains("superfighter"):
			errors.append("LIVE title uses Superfighters trademark")
		app.map_id = "gauge"
		app.title.set_map_id("gauge")
		if app.title.map_btn == null:
			errors.append("LIVE title missing MapCycle button")
		elif not str(app.title.map_btn.text).contains("Gauge Deck"):
			errors.append("LIVE wrap must start on Gauge Deck got %s" % str(app.title.map_btn.text))
		var wrap_from: String = app.map_id
		var wrap_from_label: String = str(app.title.map_btn.text) if app.title.map_btn != null else ""
		if app.title.map_btn != null:
			app.title.map_btn.emit_signal("pressed")
		if app.map_id != "rooftops":
			errors.append("LIVE map_btn.pressed wrap is %s" % app.map_id)
		if app.title.map_btn != null and not str(app.title.map_btn.text).contains("Skyline Relay"):
			errors.append("LIVE map_btn.pressed wrap label is %s" % str(app.title.map_btn.text))
		outcome_live = {
			"verdict": "pass" if errors.is_empty() else "fail",
			"hud": shown,
			"wrap_from": wrap_from,
			"wrap_to": app.map_id,
			"wrap_from_label": wrap_from_label,
			"wrap_to_label": str(app.title.map_btn.text) if app.title.map_btn != null else "",
			"source": "map_btn.pressed",
		}
	if outcome_live.is_empty() or str(outcome_live.get("source", "")) != "map_btn.pressed":
		if errors.is_empty():
			errors.append("LIVE wrap must use map_btn.pressed")
		outcome_live = {
			"verdict": "fail",
			"hud": shown,
			"source": "missing map_btn.pressed",
		}
	_event("live", {"ok": errors.is_empty()})
	return errors


static func replay_hashes() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var pairs: Array = []
	var i: int = 0
	while i < VS_IDS.size():
		var mid: String = String(VS_IDS[i])
		var a: String = _MapCodec.stable_hash(_MapCatalog.document(mid))
		_MapCatalog.reload()
		var b: String = _MapCodec.stable_hash(_MapCatalog.document(mid))
		var ok: bool = a != "" and a == b
		if not ok:
			errors.append("REPLAY %s reload hash mismatch" % mid)
		pairs.append({"id": mid, "match": ok, "hash": a})
		i += 1
	outcome_replay = {
		"verdict": "match" if errors.is_empty() else "fail",
		"pairs": pairs,
		"source": "catalog reload hash twice per VS map",
	}
	_event("replay", {"ok": errors.is_empty()})
	return errors


static func stage_map(app: App, map_id: String) -> Dictionary:
	app.start_fight("vs2", map_id, 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_hold_slot(session, 12, 0, PackedStringArray())
	return _still_row(session, 0)


static func stage_lantern_water(app: App) -> Dictionary:
	app.start_fight("vs2", "lantern", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_hold_slot(session, 8, 0, PackedStringArray())
	_walk_toward(session, 0, LANTERN_LADDER_X, 40)
	_climb_to_clothesline(session, 0)
	_walk_toward(session, 0, LANTERN_LINE_X, 90)
	_hold_slot(session, 10, 0, PackedStringArray())
	_climb_down_to_street(session, 0)
	_walk_toward(session, 0, LANTERN_WATER_X, 80)
	_hold_slot(session, 16, 0, PackedStringArray())
	outcome_still = _still_row(session, 0)
	var still_p1: Fighter = session.player1() if session != null else null
	outcome_still["wet"] = still_p1.wet if still_p1 != null else false
	outcome_still["env_id"] = still_p1.env_inside_id if still_p1 != null else ""
	return outcome_still


static func stage_gauge_lift(app: App) -> Dictionary:
	app.start_fight("vs2", "gauge", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	_climb_down_gauge(session, 0)
	_walk_toward(session, 0, 168.0, 80)
	_hold_slot(session, 16, 0, PackedStringArray())
	_walk_toward(session, 0, GAUGE_LIFT_X, 420)
	_hold_slot(session, 70, 0, PackedStringArray())
	outcome_still = _still_row(session, 0)
	return outcome_still


static func _climb_to_clothesline(session: GameSession, slot: int) -> void:
	_walk_toward(session, slot, LANTERN_LADDER_X, 36)
	var n: int = 0
	while n < 70:
		var fighter: Fighter = _slot(session, slot)
		if fighter == null or fighter.dead:
			return
		if fighter.global_position.y >= 128.0 and fighter.global_position.y <= 160.0 and fighter.is_on_floor():
			return
		if fighter.on_ladder or fighter.climbing:
			if fighter.global_position.y < 128.0:
				_hold_slot(session, 1, slot, PackedStringArray(["down"]))
			else:
				_hold_slot(session, 1, slot, PackedStringArray())
		else:
			_walk_toward(session, slot, LANTERN_LADDER_X, 1)
			_hold_slot(session, 1, slot, PackedStringArray(["down"]))
		n += 1


static func _climb_down_gauge(session: GameSession, slot: int) -> void:
	_walk_toward(session, slot, GAUGE_LADDER_X, 40)
	var n: int = 0
	while n < 110:
		var fighter: Fighter = _slot(session, slot)
		if fighter == null or fighter.dead:
			return
		if fighter.global_position.y >= 176.0 and fighter.is_on_floor():
			return
		if fighter.on_ladder or fighter.climbing:
			_hold_slot(session, 1, slot, PackedStringArray(["down"]))
		else:
			_walk_toward(session, slot, GAUGE_LADDER_X, 1)
			_hold_slot(session, 1, slot, PackedStringArray(["down"]))
		n += 1


static func _climb_down_to_street(session: GameSession, slot: int) -> void:
	_walk_toward(session, slot, LANTERN_LADDER_X, 50)
	var n: int = 0
	while n < 140:
		var fighter: Fighter = _slot(session, slot)
		if fighter == null or fighter.dead:
			return
		if fighter.global_position.y >= 220.0 and fighter.is_on_floor():
			return
		if n > 80 and fighter.global_position.y >= 176.0 and fighter.is_on_floor() and not fighter.on_ladder:
			_hold_slot(session, 1, slot, PackedStringArray(["down"]))
		if fighter.on_ladder or fighter.climbing:
			_hold_slot(session, 1, slot, PackedStringArray(["down"]))
		else:
			_walk_toward(session, slot, LANTERN_LADDER_X, 1)
			_hold_slot(session, 1, slot, PackedStringArray(["down"]))
		n += 1


static func _climb_up(session: GameSession, slot: int, ladder_x: float, ticks: int) -> void:
	_walk_toward(session, slot, ladder_x, 36)
	var n: int = 0
	while n < ticks:
		var fighter: Fighter = _slot(session, slot)
		if fighter == null or fighter.dead:
			return
		if fighter.on_ladder or fighter.climbing:
			_hold_slot(session, 1, slot, PackedStringArray(["up"]))
		else:
			_walk_toward(session, slot, ladder_x, 1)
			_hold_slot(session, 1, slot, PackedStringArray(["up"]))
		n += 1


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
			_hold_slot(session, 8 if drop_hangs else 6, slot, PackedStringArray(["down"]))
			n += 8 if drop_hangs else 6
			continue
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
		var look: Vector2 = fighter.global_position + Vector2(20.0 if dx > 0.0 else -20.0, 12.0)
		if fighter.is_on_floor() and not _support_at(session, look):
			if drop_hangs:
				held.append("down")
				_hold_slot(session, 8, slot, held)
			else:
				held.append("jump")
				_hold_slot(session, 8, slot, held)
			stuck = 0
			n += 8
			continue
		if stuck >= 4 and fighter.is_on_floor():
			if drop_hangs:
				held.append("down")
				_hold_slot(session, 8, slot, held)
			else:
				held.append("jump")
				_hold_slot(session, 6, slot, held)
			stuck = 0
			n += 8 if drop_hangs else 6
			continue
		_hold_slot(session, 1, slot, held)
		n += 1


static func _measure_walk_dx(session: GameSession, slot: int, dir: String, ticks: int) -> float:
	var fighter: Fighter = _slot(session, slot)
	if fighter == null:
		return 0.0
	var x0: float = fighter.global_position.x
	var held: PackedStringArray = PackedStringArray(["right"])
	if dir == "left":
		held = PackedStringArray(["left"])
	_hold_slot(session, ticks, slot, held)
	fighter = _slot(session, slot)
	if fighter == null:
		return 0.0
	return absf(fighter.global_position.x - x0)


static func _fire_semi(session: GameSession, slot: int, face: String) -> void:
	var held: PackedStringArray = PackedStringArray([face, "fire"])
	_hold_slot(session, 10, slot, held)
	_release_slot(session, slot, "fire")
	_hold_slot(session, 6, slot, PackedStringArray([face]))


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
		if _mark_hits != null and _mark_slot == slot:
			_mark_zones(_slot(session, slot), _mark_hits)
		n += 1


static var _mark_hits: Dictionary = {}
static var _mark_slot: int = -1
static var _mark_map: String = ""


static func _begin_mark(session: GameSession, slot: int, hits: Dictionary) -> void:
	_mark_hits = hits
	_mark_slot = slot
	_mark_map = session.map_id if session != null else ""
	_mark_zones(_slot(session, slot), hits)


static func _support_at(session: GameSession, pos: Vector2) -> bool:
	if session == null:
		return false
	if Maps.solid_at(session.map_id, pos):
		return true
	var rows: PackedStringArray = Maps.grid(session.map_id)
	var cx: int = int(floor(pos.x / 16.0))
	var cy: int = int(floor(pos.y / 16.0))
	if cy < 0 or cy >= rows.size():
		return false
	var row: String = String(rows[cy])
	if cx < 0 or cx >= row.length():
		return false
	var ch: String = row.substr(cx, 1)
	return Maps.is_solid(ch) or Maps.is_platform(ch)


static func _end_mark() -> void:
	_mark_hits = {}
	_mark_slot = -1
	_mark_map = ""


static func _mark_zones(fighter: Fighter, hits: Dictionary) -> void:
	if fighter == null or hits == null:
		return
	var mid: String = _mark_map
	var zones: Array = ArenaSpec.combat_zones(mid)
	var i: int = 0
	while i < zones.size():
		var zone: Dictionary = zones[i] as Dictionary
		var zid: String = str(zone.get("id", ""))
		if ArenaSpec.zone_contains(zone, fighter.global_position):
			hits[zid] = true
		i += 1


static func _hit_count(hits: Dictionary) -> int:
	var n: int = 0
	var keys: Array = hits.keys()
	var i: int = 0
	while i < keys.size():
		if bool(hits[keys[i]]):
			n += 1
		i += 1
	return n


static func _still_row(session: GameSession, slot: int) -> Dictionary:
	var fighter: Fighter = _slot(session, slot)
	return {
		"alive": fighter != null and not fighter.dead,
		"on_floor": fighter != null and fighter.is_on_floor(),
		"hanging": fighter != null and fighter.hanging,
		"x": fighter.global_position.x if fighter != null else 0.0,
		"y": fighter.global_position.y if fighter != null else 0.0,
		"zone": _zone_id_at(fighter, session.map_id if session != null else ""),
		"map": session.map_id if session != null else "",
	}


static func _snap_counts(script: GDScript) -> Dictionary:
	return {
		"u": int(script.used_apply_frames),
		"a": int(script.used_apply_frames_attempted),
		"s": int(script.used_apply_frames_succeeded),
	}


static func _add_apply_delta(script: GDScript, snap: Dictionary) -> void:
	used_apply_frames += int(script.used_apply_frames) - int(snap.get("u", 0))
	used_apply_frames_attempted += int(script.used_apply_frames_attempted) - int(snap.get("a", 0))
	used_apply_frames_succeeded += int(script.used_apply_frames_succeeded) - int(snap.get("s", 0))


static func _zone_id_at(fighter: Fighter, mid: String) -> String:
	if fighter == null:
		return ""
	var zones: Array = ArenaSpec.combat_zones(mid)
	var i: int = 0
	while i < zones.size():
		var zone: Dictionary = zones[i] as Dictionary
		if ArenaSpec.zone_contains(zone, fighter.global_position):
			return str(zone.get("id", ""))
		i += 1
	return ""


static func _slot(session: GameSession, slot: int) -> Fighter:
	if session == null:
		return null
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		if f != null and f.slot == slot:
			return f
		i += 1
	return null


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


static func _require_outcomes() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var rows: Array = [
		outcome_roster, outcome_cycle, outcome_load, outcome_routes,
		outcome_cover, outcome_cargo, outcome_door, outcome_rotor,
		outcome_toxic, outcome_water, outcome_lift, outcome_lantern,
		outcome_gauge, outcome_p2, outcome_bot, outcome_camera, outcome_live
	]
	var i: int = 0
	while i < rows.size():
		if str((rows[i] as Dictionary).get("verdict", "unproven")) == "unproven":
			errors.append("outcome %d left unproven" % i)
		i += 1
	if str(outcome_replay.get("verdict", "unproven")) == "unproven":
		errors.append("replay left unproven")
	if used_apply_frames_succeeded < 1:
		errors.append("expected apply_frames live body")
	if bool(outcome_rotor.get("used_give_weapon", true)):
		errors.append("ROTOR must not use give_weapon")
	if str(outcome_live.get("source", "")) != "map_btn.pressed":
		errors.append("LIVE wrap source must be map_btn.pressed")
	if float(outcome_water.get("dx_dry", 0.0)) <= 8.0:
		errors.append("WATER leftover-0 must measure a dry walk delta")
	if float(outcome_water.get("dx_wet", 999.0)) >= float(outcome_water.get("dx_dry", 0.0)) * 0.85:
		errors.append("WATER leftover-0 must measure a slower wet walk")
	return errors


static func _event(kind: String, extra: Dictionary) -> void:
	var row: Dictionary = {"kind": kind}
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

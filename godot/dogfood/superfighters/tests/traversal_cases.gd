class_name TraversalCases
extends RefCounted

const _Traversal: GDScript = preload("res://src/sim/traversal.gd")

## VF2-WP5 official ladder / ledge / drop cases.
## Proof is InputFrame apply_frames plus live InputEvent inject.
## 60 Hz is ledger:RL-SIM-FIXED-60 (assumption).
## Ladder stays ledger:RL-MOVE-LADDER (assumption).
## Ledge stays ledger:RL-MOVE-LEDGE (assumption).
## Drop stays ledger:RL-MOVE-DROP (assumption).
## InputFrame action ledge stays reserved.
## Y8 observation stays ledger:RL-MOVE-ROLL-DIVE (unavailable).
## USED_APPLY_FRAMES counts successful apply_frames only.

static var used_step_fixed: int = 0
static var used_apply_frames: int = 0
static var used_apply_frames_attempted: int = 0
static var used_apply_frames_succeeded: int = 0
static var used_parse_input_event: int = 0
static var used_action_press: int = 0
static var outcome_ladder: Dictionary = {}
static var outcome_ledge: Dictionary = {}
static var outcome_drop: Dictionary = {}
static var outcome_block: Dictionary = {}
static var outcome_dirs: Dictionary = {}
static var outcome_maps: Dictionary = {}
static var outcome_stuck: Dictionary = {}
static var outcome_contact: Dictionary = {}
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
	outcome_ladder = {"verdict": "unproven"}
	outcome_ledge = {"verdict": "unproven"}
	outcome_drop = {"verdict": "unproven"}
	outcome_block = {"verdict": "unproven"}
	outcome_dirs = {"verdict": "unproven"}
	outcome_maps = {"verdict": "unproven"}
	outcome_stuck = {"verdict": "unproven"}
	outcome_contact = {"verdict": "unproven"}
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
	_append(errors, await ladder_contract(app))
	_append(errors, await ledge_contract(app))
	_append(errors, await drop_contract(app))
	_append(errors, await block_contract(app))
	_append(errors, await four_directions(app))
	_append(errors, await map_fixtures(app))
	_append(errors, await no_stuck(app))
	_append(errors, await contact_normals(app))
	_append(errors, await live_traverse(app))
	_append(errors, _require_outcomes())
	return errors


static func schema_and_data() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var trav: Dictionary = _Traversal.data()
	if str(trav.get("schema", "")) != _Traversal.SCHEMA_ID:
		errors.append("traversal schema id mismatch")
	if str(trav.get("title", "")) != "Vault Fighters":
		errors.append("traversal title must be Vault Fighters")
	if bool(trav.get("y8_parity_claimed", true)):
		errors.append("traversal must not claim Y8 parity")
	if str(trav.get("ladder_class", "")) != "assumption":
		errors.append("ladder must stay assumption")
	if str(trav.get("ledge_class", "")) != "assumption":
		errors.append("ledge must stay assumption")
	if str(trav.get("drop_class", "")) != "assumption":
		errors.append("drop must stay assumption")
	if str(trav.get("roll_dive_class", "")) != "unavailable":
		errors.append("Y8 roll/dive observation must stay unavailable")
	if str(trav.get("ladder_ledger", "")) != "RL-MOVE-LADDER":
		errors.append("ladder must cite RL-MOVE-LADDER")
	if str(trav.get("ledge_ledger", "")) != "RL-MOVE-LEDGE":
		errors.append("ledge must cite RL-MOVE-LEDGE")
	if str(trav.get("drop_ledger", "")) != "RL-MOVE-DROP":
		errors.append("drop must cite RL-MOVE-DROP")
	if not bool(trav.get("input_ledge_reserved", false)):
		errors.append("InputFrame ledge must stay reserved")
	if _Traversal.fixture_ids().size() < 5:
		errors.append("expected >=5 traversal fixtures")
	var loco: Dictionary = Locomotion.data()
	var reserved: Array = loco.get("reserved_not_shipped", []) as Array
	if reserved.has("ledge"):
		errors.append("locomotion reserved must not keep shipped ledge")
	if SimValidator.ALLOWED.has("ledge"):
		errors.append("InputFrame ledge must stay unshipped")
	if not Maps.stage_ids().size() == 4:
		errors.append("fixtures must not enter stage_ids")
	if Maps.stage_ids().has("fx_ladder"):
		errors.append("fx_ladder must not be a stage map")
	return errors


static func replay_traces_twice(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var paths: PackedStringArray = SimTrace.list_dir(SimConstants.TRAVERSE_TRACE_DIR)
	if paths.size() < 8:
		errors.append("expected >=8 traversal traces, got %d" % paths.size())
	var required: PackedStringArray = PackedStringArray([
		"ladder_up_down", "ladder_block", "ledge_recover", "drop_through",
		"cross_dirs", "map_rooftops", "map_storage", "map_hazardous"
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
		if "assumption" not in str(trace.get("ladder", "")):
			errors.append("%s must keep ladder assumption" % path.get_file())
		names.append(str(trace.get("name", path.get_file())))
		var a: Dictionary = await SimReplay.play_path(app, path)
		var b: Dictionary = await SimReplay.play_path(app, path)
		_record_apply_batch(int(a.get("ticks", 0)), bool(a.get("ok", false)))
		_record_apply_batch(int(b.get("ticks", 0)), bool(b.get("ok", false)))
		if not bool(a.get("ok", false)):
			errors.append("traverse %s run1 failed: %s" % [path.get_file(), _join(a)])
		if not bool(b.get("ok", false)):
			errors.append("traverse %s run2 failed: %s" % [path.get_file(), _join(b)])
		if not bool(a.get("used_apply_frames", false)) or bool(a.get("used_cmd_dicts", true)):
			errors.append("traverse %s MATCH used cmd dicts" % path.get_file())
		var hash_a: String = str(a.get("final_hash", ""))
		var hash_b: String = str(b.get("final_hash", ""))
		var match_ok: bool = hash_a != "" and hash_a == hash_b
		if not match_ok:
			errors.append("traverse %s replay hashes differ" % path.get_file())
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
			errors.append("missing traversal trace %s" % String(required[i]))
		i += 1
	var all_match: bool = pairs.size() >= 8
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


static func ladder_contract(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_ladder", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	_apply_p1(session, PackedStringArray(), 12, 0.0)
	var x0: float = p1.global_position.x
	_apply_p1(session, PackedStringArray(["right"]), 28, 1.0)
	_apply_p1(session, PackedStringArray(["jump"]), 8, 0.0)
	var attached: bool = p1.climbing or session.ledger.count_kind("ladder_attach") >= 1
	var snap_ok: bool = absf(p1.global_position.x - x0) > 8.0
	var y0: float = p1.global_position.y
	_apply_p1(session, PackedStringArray(["jump"]), 24, 0.0)
	var climbed: bool = p1.global_position.y < y0 - 8.0
	var pose_ok: bool = p1.current_pose() == "climb" or p1.climbing
	var hud_line: Label = session.hud.get_node_or_null("Bar_0") as Label
	var hud_ok: bool = hud_line != null and hud_line.text.contains("CLIMB")
	var y1: float = p1.global_position.y
	_apply_p1(session, PackedStringArray(["crouch"]), 20, 0.0)
	var down_ok: bool = p1.global_position.y > y1 + 4.0
	var teleport_ok: bool = session.ledger.count_kind("teleport") == 0
	if not attached:
		errors.append("ladder attach missing")
	if not climbed:
		errors.append("ladder climb up did not move y0=%s y=%s" % [str(y0), str(p1.global_position.y)])
	if not down_ok:
		errors.append("ladder climb down did not move")
	if not teleport_ok:
		errors.append("official ladder used teleport")
	var pass_ok: bool = attached and snap_ok and climbed and down_ok and teleport_ok
	outcome_ladder = {
		"verdict": "pass" if pass_ok else "fail",
		"attached": attached,
		"snapped": snap_ok,
		"climbed_up": climbed,
		"climbed_down": down_ok,
		"pose": p1.current_pose(),
		"hud_climb": hud_ok,
		"attach_events": session.ledger.count_kind("ladder_attach"),
		"source": "apply_frames fx_ladder attach/snap/climb/drop",
	}
	_remember_session(session)
	return errors


static func ledge_contract(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_ledge", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	_apply_p1(session, PackedStringArray(), 12, 0.0)
	_apply_p1(session, PackedStringArray(["right"]), 10, 1.0)
	_apply_p1(session, PackedStringArray(["right", "jump"]), 8, 1.0)
	_apply_p1(session, PackedStringArray(["right"]), 18, 1.0)
	_apply_p1(session, PackedStringArray(), 8, 0.0)
	var grabbed: bool = p1.hanging or session.ledger.count_kind("ledge_grab") >= 1
	var y_hang: float = p1.global_position.y
	var stand_at: Vector2 = p1.hang_stand
	var max_step: float = 0.0
	var prev: Vector2 = p1.global_position
	var n: int = 0
	while n < 40:
		var held: PackedStringArray = PackedStringArray()
		if p1.hanging or p1.recover_left > 0.0:
			held.append("jump")
		_apply_p1(session, held, 1, 0.0)
		var step: float = p1.global_position.distance_to(prev)
		if step > max_step:
			max_step = step
		prev = p1.global_position
		n += 1
	_apply_p1(session, PackedStringArray(), 16, 0.0)
	var y1: float = p1.global_position.y
	var board_eps: float = _Traversal.f("recover_board_eps", 8.0)
	var stand_dist: float = p1.global_position.distance_to(stand_at)
	var boarded: bool = p1.is_on_floor() and not p1.hanging and p1.recover_left <= 0.0
	var near_stand: bool = stand_dist < board_eps
	var recovered: bool = session.ledger.count_kind("ledge_recover") >= 1 and boarded and near_stand
	var no_warp: bool = max_step + 0.0001 < float(Maps.TILE) and p1.recover_max_step + 0.0001 < float(Maps.TILE)
	var teleport_ok: bool = session.ledger.count_kind("teleport") == 0
	var idle_pos: Vector2 = p1.global_position
	var idle_vel: Vector2 = p1.velocity
	_apply_p1(session, PackedStringArray(), 40, 0.0)
	var idle_boarded: bool = p1.is_on_floor() and not p1.hanging
	var idle_moved: bool = p1.global_position.distance_to(idle_pos) > 0.05 or p1.velocity.distance_to(idle_vel) > 0.05
	var idle_wedged: bool = (not idle_boarded) and (not idle_moved)
	var pose_ok: bool = p1.current_pose() != "hang"
	if not grabbed:
		errors.append("ledge grab missing pose=%s y=%s" % [p1.current_pose(), str(p1.global_position)])
	if not boarded:
		errors.append("ledge recover did not board floor pos=%s stand=%s on_floor=%s hanging=%s pose=%s" % [
			str(p1.global_position), str(stand_at), str(p1.is_on_floor()), str(p1.hanging), p1.current_pose()
		])
	if not near_stand:
		errors.append("ledge recover missed stand dist=%s eps=%s pos=%s stand=%s" % [
			str(stand_dist), str(board_eps), str(p1.global_position), str(stand_at)
		])
	if not recovered:
		errors.append("ledge recover missing board y_hang=%s y=%s" % [str(y_hang), str(y1)])
	if idle_wedged:
		errors.append("ledge recover idle stayed wedged pos=%s vel=%s" % [
			str(p1.global_position), str(p1.velocity)
		])
	if not pose_ok:
		errors.append("ledge recover pose stayed hang")
	if not no_warp:
		errors.append("ledge recover warped step=%s fighter=%s tile=%s" % [
			str(max_step), str(p1.recover_max_step), str(Maps.TILE)
		])
	var pass_ok: bool = (
		grabbed and recovered and boarded and near_stand and no_warp
		and teleport_ok and idle_boarded and not idle_wedged and pose_ok
	)
	outcome_ledge = {
		"verdict": "pass" if pass_ok else "fail",
		"grabbed": grabbed,
		"recovered": recovered,
		"boarded": boarded,
		"on_floor": p1.is_on_floor(),
		"hanging": p1.hanging,
		"near_stand": near_stand,
		"stand_dist": stand_dist,
		"stand_x": stand_at.x,
		"stand_y": stand_at.y,
		"end_x": p1.global_position.x,
		"end_y": p1.global_position.y,
		"no_warp": no_warp,
		"recover_max_step": max_step,
		"fighter_recover_max_step": p1.recover_max_step,
		"y_hang": y_hang,
		"y1": y1,
		"pose": p1.current_pose(),
		"idle_boarded": idle_boarded,
		"idle_wedged": idle_wedged,
		"grab_events": session.ledger.count_kind("ledge_grab"),
		"recover_events": session.ledger.count_kind("ledge_recover"),
		"source": "apply_frames fx_ledge grab/outside-then-board recover onto lip floor",
	}
	_remember_session(session)
	return errors


static func drop_contract(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_drop", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	_apply_p1(session, PackedStringArray(), 16, 0.0)
	_apply_p1(session, PackedStringArray(["right"]), 8, 1.0)
	_apply_p1(session, PackedStringArray(), 8, 0.0)
	var y0: float = p1.global_position.y
	var drop_eps: float = _Traversal.f("drop_fall_min", 8.0)
	var plat_bit: int = 0
	if session.arena != null:
		plat_bit = session.arena.platform_collision_bit()
	_apply_p1(session, PackedStringArray(["crouch"]), 20, 0.0)
	var mask_mid: int = p1.collision_mask
	var cleared: bool = (mask_mid & Maps.COL_PLATFORM) == 0
	_apply_p1(session, PackedStringArray(["crouch"]), 8, 0.0)
	_apply_p1(session, PackedStringArray(), 20, 0.0)
	var y1: float = p1.global_position.y
	var dy: float = y1 - y0
	var fell: bool = dy > drop_eps
	if not fell:
		errors.append("one-way drop did not fall y0=%s y1=%s dy=%s eps=%s" % [
			str(y0), str(y1), str(dy), str(drop_eps)
		])
	if plat_bit != Maps.COL_PLATFORM:
		errors.append("one-way tiles must live on COL_PLATFORM got=%s" % str(plat_bit))
	if not cleared:
		errors.append("drop did not clear COL_PLATFORM mask=%s" % str(mask_mid))
	var pass_ok: bool = fell and cleared and plat_bit == Maps.COL_PLATFORM and session.ledger.count_kind("teleport") == 0
	outcome_drop = {
		"verdict": "pass" if pass_ok else "fail",
		"dropped": fell,
		"y0": y0,
		"y1": y1,
		"dy": dy,
		"drop_eps": drop_eps,
		"mask_cleared": cleared,
		"platform_bit": plat_bit,
		"drop_events": session.ledger.count_kind("drop_through"),
		"source": "apply_frames fx_drop y-increase, not event-only",
	}
	_remember_session(session)
	return errors


static func block_contract(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_block", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	_apply_p1(session, PackedStringArray(), 12, 0.0)
	_apply_p1(session, PackedStringArray(["right"]), 28, 1.0)
	_apply_p1(session, PackedStringArray(["jump"]), 40, 0.0)
	var blocked: bool = session.ledger.count_kind("ladder_block") >= 1 or p1.last_climb_block == "solid"
	var not_inside: bool = p1.global_position.y > 24.0
	if not blocked:
		errors.append("ladder climb through solid was not blocked")
	if not not_inside:
		errors.append("fighter climbed into solid y=%s" % str(p1.global_position.y))
	var pass_ok: bool = blocked and not_inside
	outcome_block = {
		"verdict": "pass" if pass_ok else "fail",
		"blocked": blocked,
		"outside_solid": not_inside,
		"block_events": session.ledger.count_kind("ladder_block"),
		"last_block": p1.last_climb_block,
		"source": "apply_frames fx_block climb into solid",
	}
	_remember_session(session)
	return errors


static func four_directions(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var fixtures: PackedStringArray = _Traversal.fixture_ids()
	var rows: Array = []
	var all_ok: bool = fixtures.size() >= 5
	var i: int = 0
	while i < fixtures.size():
		var map_id: String = String(fixtures[i])
		app.start_fight("vs2", map_id, 0)
		await SimReplay.sync_physics(app)
		var session: GameSession = app.session
		var p1: Fighter = session.player1()
		var row: Dictionary = _measure_dirs(session, p1, map_id)
		if not bool(row.get("ok", false)):
			errors.append("fixture %s failed four-dir dxR=%s dxL=%s dyU=%s dyD=%s" % [
				map_id,
				str(row.get("dx_right", 0.0)),
				str(row.get("dx_left", 0.0)),
				str(row.get("dy_up", 0.0)),
				str(row.get("dy_down", 0.0)),
			])
			all_ok = false
		rows.append(row)
		_remember_session(session)
		i += 1
	outcome_dirs = {
		"verdict": "pass" if all_ok else "fail",
		"fixtures": rows,
		"source": "measured L/R/U/D displacement vs start of each direction",
	}
	return errors


static func _measure_dirs(session: GameSession, p1: Fighter, map_id: String) -> Dictionary:
	var eps: float = _Traversal.f("dir_min", 4.0)
	_apply_p1(session, PackedStringArray(), 10, 0.0)
	var xr0: float = p1.global_position.x
	_apply_p1(session, PackedStringArray(["right"]), 12, 1.0)
	var dx_right: float = p1.global_position.x - xr0
	var xl0: float = p1.global_position.x
	_apply_p1(session, PackedStringArray(["left"]), 14, -1.0)
	var dx_left: float = p1.global_position.x - xl0
	var dy_up: float = 0.0
	var dy_down: float = 0.0
	if Maps.count_char(map_id, "H") > 0:
		_apply_p1(session, PackedStringArray(["right"]), 28, 1.0)
		var yu0: float = p1.global_position.y
		_apply_p1(session, PackedStringArray(["jump"]), 20, 0.0)
		dy_up = p1.global_position.y - yu0
		var yd0: float = p1.global_position.y
		_apply_p1(session, PackedStringArray(["crouch"]), 20, 0.0)
		dy_down = p1.global_position.y - yd0
	elif Maps.count_char(map_id, "=") > 0:
		var yu0: float = p1.global_position.y
		_apply_p1(session, PackedStringArray(["jump"]), 12, 0.0)
		dy_up = p1.global_position.y - yu0
		_apply_p1(session, PackedStringArray(), 16, 0.0)
		var yd0: float = p1.global_position.y
		_apply_p1(session, PackedStringArray(["crouch"]), 20, 0.0)
		_apply_p1(session, PackedStringArray(["crouch"]), 8, 0.0)
		_apply_p1(session, PackedStringArray(), 20, 0.0)
		dy_down = p1.global_position.y - yd0
		if dy_up >= -eps:
			yu0 = p1.global_position.y
			_apply_p1(session, PackedStringArray(["jump"]), 24, 0.0)
			dy_up = p1.global_position.y - yu0
	else:
		_apply_p1(session, PackedStringArray(["right"]), 8, 1.0)
		var yu0: float = p1.global_position.y
		_apply_p1(session, PackedStringArray(["right", "jump"]), 10, 1.0)
		dy_up = p1.global_position.y - yu0
		_apply_p1(session, PackedStringArray(["right"]), 18, 1.0)
		_apply_p1(session, PackedStringArray(), 8, 0.0)
		var yd0: float = p1.global_position.y
		if p1.hanging:
			_apply_p1(session, PackedStringArray(["crouch"]), 16, 0.0)
		else:
			_apply_p1(session, PackedStringArray(), 20, 0.0)
		dy_down = p1.global_position.y - yd0
	var right_ok: bool = dx_right > eps
	var left_ok: bool = dx_left < -eps
	var up_ok: bool = dy_up < -eps
	var down_ok: bool = dy_down > eps
	var stuck: bool = absf(p1.velocity.x) < 0.0001 and absf(p1.velocity.y) < 0.0001 and not p1.is_on_floor() and not p1.climbing and not p1.hanging
	return {
		"map_id": map_id,
		"dx_right": dx_right,
		"dx_left": dx_left,
		"dy_up": dy_up,
		"dy_down": dy_down,
		"right": right_ok,
		"left": left_ok,
		"up": up_ok,
		"down": down_ok,
		"stuck": stuck,
		"ok": right_ok and left_ok and up_ok and down_ok and not stuck and not p1.dead,
	}


static func map_fixtures(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var maps: PackedStringArray = Maps.stage_ids()
	var rows: Array = []
	var i: int = 0
	while i < maps.size():
		rows.append({
			"map_id": String(maps[i]),
			"navigated": false,
			"claimed": false,
			"note": "fixtures-only WP; stage map not climb-traversed",
		})
		i += 1
	if maps.size() != 4:
		errors.append("expected 4 stage ids for honest MAPS=fixtures_only label")
	if app == null:
		errors.append("map_fixtures missing app")
	outcome_maps = {
		"verdict": "fixtures_only",
		"stage_navigated": false,
		"stage_claimed": false,
		"maps": rows,
		"source": "WP allows temp fixtures; rooftops/storage/police/hazardous not claimed as climbed",
	}
	return errors


static func no_stuck(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_cross", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	_apply_p1(session, PackedStringArray(), 10, 0.0)
	_apply_p1(session, PackedStringArray(["right"]), 16, 1.0)
	_apply_p1(session, PackedStringArray(["jump"]), 16, 0.0)
	_apply_p1(session, PackedStringArray(["left"]), 12, -1.0)
	var stuck: bool = not p1.is_on_floor() and not p1.climbing and not p1.hanging and absf(p1.velocity.x) < 0.0001 and absf(p1.velocity.y) < 0.0001
	if stuck:
		errors.append("fighter stuck in air on fx_cross")
	if p1.dead:
		errors.append("fighter died during traverse QA")
	var pass_ok: bool = not stuck and not p1.dead
	outcome_stuck = {
		"verdict": "pass" if pass_ok else "fail",
		"stuck": stuck,
		"dead": p1.dead,
		"pose": p1.current_pose(),
		"source": "apply_frames fx_cross no mid-air freeze",
	}
	_remember_session(session)
	return errors


static func contact_normals(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_block", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	_apply_p1(session, PackedStringArray(), 12, 0.0)
	_apply_p1(session, PackedStringArray(["right"]), 8, 1.0)
	var nx0: float = p1.last_contact_nx
	var ny0: float = p1.last_contact_ny
	app.start_fight("vs2", "fx_block", 0)
	await SimReplay.sync_physics(app)
	session = app.session
	p1 = session.player1()
	_apply_p1(session, PackedStringArray(), 12, 0.0)
	_apply_p1(session, PackedStringArray(["right"]), 8, 1.0)
	var same: bool = absf(p1.last_contact_nx - nx0) <= Locomotion.epsilon() and absf(p1.last_contact_ny - ny0) <= Locomotion.epsilon()
	if not same:
		errors.append("contact normals drifted nx=%s/%s ny=%s/%s" % [
			str(nx0), str(p1.last_contact_nx), str(ny0), str(p1.last_contact_ny)
		])
	outcome_contact = {
		"verdict": "pass" if same else "fail",
		"nx": p1.last_contact_nx,
		"ny": p1.last_contact_ny,
		"stable": same,
		"source": "two apply_frames runs quantized contact normal",
	}
	_remember_session(session)
	return errors


static func live_traverse(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_ladder", 0)
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
	while n < 20:
		session.step_from_live_input()
		n += 1
	InputInjector.inject_key(KEY_RIGHT, false, viewport)
	InputInjector.inject_key(KEY_UP, true, viewport)
	n = 0
	while n < 16:
		session.step_from_live_input()
		n += 1
	var live_climb: bool = p1.climbing or session.ledger.count_kind("ladder_attach") >= 1
	if not live_climb:
		errors.append("live up on ladder did not attach pose=%s" % p1.current_pose())
	InputInjector.release_known(viewport)
	outcome_live = {
		"verdict": "pass" if live_climb else "fail",
		"live_climb": live_climb,
		"pose": p1.current_pose(),
		"source": "parse_input_event + step_from_live_input",
	}
	_remember_session(session)
	return errors


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


static func _capture_start(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_ladder", 0)
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
	if str(outcome_ladder.get("verdict", "")) != "pass":
		errors.append("LADDER outcome is %s" % str(outcome_ladder.get("verdict", "unproven")))
	if str(outcome_ledge.get("verdict", "")) != "pass":
		errors.append("LEDGE outcome is %s" % str(outcome_ledge.get("verdict", "unproven")))
	if str(outcome_drop.get("verdict", "")) != "pass":
		errors.append("DROP outcome is %s" % str(outcome_drop.get("verdict", "unproven")))
	if str(outcome_block.get("verdict", "")) != "pass":
		errors.append("BLOCK outcome is %s" % str(outcome_block.get("verdict", "unproven")))
	if str(outcome_dirs.get("verdict", "")) != "pass":
		errors.append("DIRS outcome is %s" % str(outcome_dirs.get("verdict", "unproven")))
	if str(outcome_maps.get("verdict", "")) != "fixtures_only":
		errors.append("MAPS must be fixtures_only, got %s" % str(outcome_maps.get("verdict", "unproven")))
	if bool(outcome_maps.get("stage_navigated", true)) or bool(outcome_maps.get("stage_claimed", true)):
		errors.append("MAPS must not claim stage maps navigated")
	if str(outcome_stuck.get("verdict", "")) != "pass":
		errors.append("STUCK outcome is %s" % str(outcome_stuck.get("verdict", "unproven")))
	if str(outcome_contact.get("verdict", "")) != "pass":
		errors.append("CONTACT outcome is %s" % str(outcome_contact.get("verdict", "unproven")))
	if str(outcome_live.get("verdict", "")) != "pass":
		errors.append("LIVE outcome is %s" % str(outcome_live.get("verdict", "unproven")))
	if str(outcome_replay.get("verdict", "")) != "match":
		errors.append("REPLAY outcome is %s" % str(outcome_replay.get("verdict", "unproven")))
	if used_apply_frames_succeeded <= 0 or used_apply_frames != used_apply_frames_succeeded:
		errors.append("USED_APPLY_FRAMES must count successful applies got=%d attempted=%d" % [
			used_apply_frames_succeeded, used_apply_frames_attempted
		])
	if not _events_have("drop_through"):
		errors.append("events_all missing drop_through")
	if not _events_have("ledge_grab"):
		errors.append("events_all missing ledge_grab")
	if not _events_have("ledge_recover"):
		errors.append("events_all missing ledge_recover")
	return errors


static func _events_have(kind: String) -> bool:
	var i: int = 0
	while i < events_all.size():
		var row: Variant = events_all[i]
		if row is Dictionary and str((row as Dictionary).get("kind", "")) == kind:
			return true
		i += 1
	return false


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


static func _append_events(events: Array) -> void:
	var i: int = 0
	while i < events.size():
		events_all.append(events[i])
		i += 1
	events_end = events_all


static func _remember_end(played: Dictionary) -> void:
	var state: Dictionary = played.get("final_state", {}) as Dictionary
	if not state.is_empty():
		snapshot_end = state
	var events: Array = played.get("events", []) as Array
	if not events.is_empty():
		_append_events(events)


static func _remember_session(session: GameSession) -> void:
	if session == null:
		return
	snapshot_end = session.snapshot()
	if session.ledger != null:
		_append_events(session.ledger.to_array())


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

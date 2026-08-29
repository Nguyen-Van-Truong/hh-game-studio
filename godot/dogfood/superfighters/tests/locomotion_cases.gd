class_name LocomotionCases
extends RefCounted

## VF2-WP2 official locomotion cases. Proof is InputFrame apply_frames
## plus live InputEvent inject. Must not use Input.action_press or
## cmd-dict step_fixed. 60 Hz is ledger:RL-SIM-FIXED-60 (assumption).
## Hold-to-aim stays assumption. Y8 roll/dive observation stays
## unavailable. Product dive/kick are VF2-WP4 assumption.

static var used_step_fixed: int = 0
static var used_apply_frames: int = 0
static var used_apply_frames_attempted: int = 0
static var used_apply_frames_succeeded: int = 0
static var used_parse_input_event: int = 0
static var used_action_press: int = 0
static var outcome_hash2: Dictionary = {}
static var outcome_tunnel: Dictionary = {}
static var outcome_camera: Dictionary = {}
static var snapshot_start: Dictionary = {}
static var snapshot_end: Dictionary = {}
static var events_end: Array = []


static func run_all(app: App) -> PackedStringArray:
	used_step_fixed = 0
	used_apply_frames = 0
	used_apply_frames_attempted = 0
	used_apply_frames_succeeded = 0
	used_parse_input_event = 0
	used_action_press = 0
	outcome_hash2 = {"verdict": "unproven", "pairs": []}
	outcome_tunnel = {"verdict": "unproven"}
	outcome_camera = {"verdict": "unproven"}
	snapshot_start = {}
	snapshot_end = {}
	events_end = []
	var errors: PackedStringArray = PackedStringArray()
	_append(errors, schema_and_data())
	_append(errors, await _capture_start(app))
	_append(errors, await replay_traces_twice(app))
	_append(errors, await accel_friction(app))
	_append(errors, await variable_jump(app))
	_append(errors, await coyote_and_buffer(app))
	_append(errors, await crouch_shape(app))
	_append(errors, await pit_walk_off(app))
	_append(errors, await no_tunnel(app))
	_append(errors, await camera_fit(app))
	_append(errors, await live_input_events(app))
	_append(errors, _require_outcomes())
	return errors


static func schema_and_data() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var loco: Dictionary = Locomotion.data()
	if loco.is_empty():
		errors.append("missing data/sim/locomotion.json")
		return errors
	if str(loco.get("schema", "")) != Locomotion.SCHEMA_ID:
		errors.append("locomotion schema id mismatch")
	if str(loco.get("title", "")) != "Vault Fighters":
		errors.append("locomotion title must be Vault Fighters")
	if bool(loco.get("y8_parity_claimed", true)):
		errors.append("locomotion must not claim Y8 parity")
	if bool(loco.get("y8_tick_rate_claimed", true)):
		errors.append("locomotion must not claim a Y8 tick rate")
	if str(loco.get("ledger_clock", "")) != "RL-SIM-FIXED-60":
		errors.append("locomotion must cite RL-SIM-FIXED-60")
	if str(loco.get("jump_crouch_class", "")) != "assumption":
		errors.append("jump/crouch must stay assumption")
	if str(loco.get("loco_class", "")) != "assumption":
		errors.append("loco base must stay assumption")
	if str(loco.get("camera_class", "")) != "assumption":
		errors.append("camera must stay assumption")
	if str(loco.get("hold_to_aim_class", "")) != "assumption":
		errors.append("hold-to-aim must stay assumption")
	if str(loco.get("roll_dive_class", "")) != "unavailable":
		errors.append("Y8 roll/dive observation must stay unavailable")
	if str(loco.get("dive_class", "")) != "assumption":
		errors.append("product dive must stay assumption")
	if str(loco.get("kick_class", "")) != "assumption":
		errors.append("product kick must stay assumption")
	if absf(Locomotion.epsilon() - SimConstants.EPSILON) > 0.0000001:
		errors.append("locomotion epsilon must match sim epsilon 0.001")
	if absf(Locomotion.f("walk", 0.0) - 170.0) > 0.01:
		errors.append("walk constant drifted from data")
	if absf(Locomotion.f("accel", 0.0) - 2400.0) > 0.01:
		errors.append("accel constant drifted from data")
	if absf(Locomotion.f("friction", 0.0) - 2000.0) > 0.01:
		errors.append("friction constant drifted from data")
	var cam: Dictionary = Locomotion.camera()
	if str(cam.get("mode", "")) != "arena_fit":
		errors.append("camera mode must be arena_fit")
	if absf(float(cam.get("designed_view_x", 0.0)) - 1280.0) > 0.01:
		errors.append("designed view width must be 1280")
	var reserved: Array = loco.get("reserved_not_shipped", []) as Array
	if reserved.has("roll") or reserved.has("dive") or reserved.has("kick"):
		errors.append("roll/dive/kick must not stay reserved")
	if reserved.has("ledge"):
		errors.append("ledge mechanic must be shipped")
	return errors


static func replay_traces_twice(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var paths: PackedStringArray = SimTrace.list_dir(SimConstants.LOCO_TRACE_DIR)
	if paths.size() < 6:
		errors.append("expected >=6 locomotion traces, got %d" % paths.size())
	var required: PackedStringArray = PackedStringArray([
		"walk_accel_friction", "crouch_shape", "pit_fall",
		"no_tunnel_solid", "no_tunnel_oneway", "variable_jump"
	])
	var names: PackedStringArray = PackedStringArray()
	var pairs: Array = []
	var i: int = 0
	while i < paths.size():
		var path: String = String(paths[i])
		var trace: Dictionary = SimTrace.load_path(path)
		var verr: PackedStringArray = SimTrace.validate(trace)
		_append(errors, verr)
		if bool(trace.get("used_step_fixed", true)):
			errors.append("%s must set used_step_fixed false" % path.get_file())
		if bool(trace.get("y8_parity_claimed", true)):
			errors.append("%s claimed Y8 parity" % path.get_file())
		names.append(str(trace.get("name", path.get_file())))
		var a: Dictionary = await SimReplay.play_path(app, path)
		var b: Dictionary = await SimReplay.play_path(app, path)
		_record_apply_batch(int(a.get("ticks", 0)), bool(a.get("ok", false)))
		_record_apply_batch(int(b.get("ticks", 0)), bool(b.get("ok", false)))
		if not bool(a.get("ok", false)):
			errors.append("loco %s run1 failed: %s" % [path.get_file(), _join(a)])
		if not bool(b.get("ok", false)):
			errors.append("loco %s run2 failed: %s" % [path.get_file(), _join(b)])
		if not bool(a.get("used_apply_frames", false)) or bool(a.get("used_cmd_dicts", true)):
			errors.append("loco %s MATCH used cmd dicts" % path.get_file())
		if str(a.get("final_hash", "")) == "" or str(a.get("final_hash", "")) != str(b.get("final_hash", "")):
			errors.append("loco %s replay hashes differ" % path.get_file())
		_append(errors, _positions_within_epsilon(path.get_file(), a, b))
		var pair: Dictionary = _hash_pair(str(trace.get("name", path.get_file())), a, b)
		pairs.append(pair)
		_remember_end(a)
		_remember_end(b)
		i += 1
	i = 0
	while i < required.size():
		if not names.has(String(required[i])):
			errors.append("missing locomotion trace %s" % String(required[i]))
		i += 1
	var all_match: bool = pairs.size() >= 6
	var p: int = 0
	while p < pairs.size():
		var row: Dictionary = pairs[p] as Dictionary
		if not bool(row.get("hash_match", false)) or not bool(row.get("within_epsilon", false)):
			all_match = false
		if not bool(row.get("ok_a", false)) or not bool(row.get("ok_b", false)):
			all_match = false
		p += 1
	outcome_hash2 = {
		"verdict": "match" if all_match else "fail",
		"epsilon": Locomotion.epsilon(),
		"compared_axes": ["x", "y"],
		"pair_count": pairs.size(),
		"pairs": pairs,
		"source": "SimReplay.final_hash+quantized_xy",
	}
	return errors


static func accel_friction(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "police", 0)
	var session: GameSession = app.session
	if session == null:
		errors.append("accel missing session")
		return errors
	await SimReplay.sync_physics(app)
	session = app.session
	var p1: Fighter = session.player1()
	_apply_p1(session, PackedStringArray(), 12, 0.0)
	if absf(p1.velocity.x) > 8.0:
		errors.append("settle left residual vx=%s" % str(p1.velocity.x))
	_apply_p1(session, PackedStringArray(["right"]), 3, 1.0)
	if p1.velocity.x <= 0.0 or p1.velocity.x >= p1.walk - 1.0:
		errors.append("accel must ramp: vx=%s walk=%s" % [str(p1.velocity.x), str(p1.walk)])
	_apply_p1(session, PackedStringArray(["right"]), 20, 1.0)
	if absf(p1.velocity.x - p1.walk) > 15.0:
		errors.append("walk speed not reached vx=%s walk=%s" % [str(p1.velocity.x), str(p1.walk)])
	var coast: float = p1.velocity.x
	_apply_p1(session, PackedStringArray(), 10, 0.0)
	if p1.velocity.x >= coast - 8.0:
		errors.append("friction did not slow vx0=%s vx1=%s" % [str(coast), str(p1.velocity.x)])
	if p1.dead:
		errors.append("accel walk died unexpectedly")
	return errors


static func variable_jump(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var tap: Dictionary = await _jump_peak(app, 2)
	var hold: Dictionary = await _jump_peak(app, 18)
	var tap_rise: float = float(tap.get("start_y", 0.0)) - float(tap.get("peak_y", 0.0))
	var hold_rise: float = float(hold.get("start_y", 0.0)) - float(hold.get("peak_y", 0.0))
	if tap_rise < 4.0 or hold_rise < 4.0:
		errors.append("jump peaks missing tap_rise=%s hold_rise=%s" % [str(tap_rise), str(hold_rise)])
		return errors
	if hold_rise <= tap_rise + 4.0:
		errors.append(
			"variable jump: hold must rise higher than tap hold=%s tap=%s"
			% [str(hold_rise), str(tap_rise)]
		)
	return errors


static func coyote_and_buffer(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "police", 0)
	var session: GameSession = app.session
	if session == null:
		errors.append("coyote missing session")
		return errors
	await SimReplay.sync_physics(app)
	session = app.session
	var p1: Fighter = session.player1()
	_apply_p1(session, PackedStringArray(), 14, 0.0)
	var n: int = 0
	while n < 20 and p1.is_on_floor() and not p1.dead:
		_apply_p1(session, PackedStringArray(["left"]), 1, -1.0)
		n += 1
	if p1.is_on_floor():
		errors.append("coyote never left the police ledge")
		return errors
	_apply_p1(session, PackedStringArray(), 3, 0.0)
	if p1.dead:
		errors.append("coyote died before jump window")
		return errors
	_apply_p1(session, PackedStringArray(["jump"]), 1, 0.0)
	if p1.velocity.y >= -80.0:
		errors.append("coyote jump did not fire vy=%s" % str(p1.velocity.y))
	app.start_fight("vs2", "police", 0)
	await SimReplay.sync_physics(app)
	session = app.session
	p1 = session.player1()
	_apply_p1(session, PackedStringArray(), 14, 0.0)
	n = 0
	while n < 20 and p1.is_on_floor() and not p1.dead:
		_apply_p1(session, PackedStringArray(["left"]), 1, -1.0)
		n += 1
	_apply_p1(session, PackedStringArray(), 12, 0.0)
	var vy_before: float = p1.velocity.y
	_apply_p1(session, PackedStringArray(["jump"]), 1, 0.0)
	if p1.velocity.y < vy_before - 80.0:
		errors.append("late jump after coyote expired still fired")
	_append(errors, await _jump_buffer(app))
	return errors


static func crouch_shape(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "police", 0)
	var session: GameSession = app.session
	if session == null:
		errors.append("crouch missing session")
		return errors
	await SimReplay.sync_physics(app)
	session = app.session
	var p1: Fighter = session.player1()
	_apply_p1(session, PackedStringArray(), 12, 0.0)
	var stand_h: float = p1.stand_shape.size.y
	_apply_p1(session, PackedStringArray(["crouch"]), 8, 0.0)
	if not p1.crouched:
		errors.append("crouch InputFrame did not set crouched")
	if p1.col_shape == null or p1.col_shape.shape != p1.crouch_shape:
		errors.append("crouch did not swap collision shape")
	if p1.crouch_shape.size.y >= stand_h - 0.5:
		errors.append("crouch AABB must shrink stand=%s crouch=%s" % [
			str(stand_h), str(p1.crouch_shape.size.y)
		])
	if absf(p1.crouch_shape.size.y - Locomotion.vec2("crouch_size", Vector2(10, 14)).y) > 0.01:
		errors.append("crouch size drifted from locomotion.json")
	return errors


static func pit_walk_off(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var path: String = "%s/pit_fall.json" % SimConstants.LOCO_TRACE_DIR
	var played: Dictionary = await SimReplay.play_path(app, path)
	_record_apply_batch(int(played.get("ticks", 0)), bool(played.get("ok", false)))
	_remember_end(played)
	if not bool(played.get("ok", false)):
		errors.append("pit_fall replay failed: %s" % _join(played))
		return errors
	var state: Dictionary = played.get("final_state", {}) as Dictionary
	var p1: Dictionary = _fighter_row(state, 0)
	if int(p1.get("dead", 0)) != 1:
		errors.append("pit_fall InputFrame walk-off must kill P1")
	if str(p1.get("death_cause", "")) != "pit":
		errors.append("pit_fall death_cause must be pit got=%s" % str(p1.get("death_cause", "")))
	if str(state.get("outcome", "")) != "lose":
		errors.append("pit_fall outcome must be lose")
	if bool(played.get("used_cmd_dicts", false)):
		errors.append("pit_fall used cmd dicts")
	var events: Array = played.get("events", []) as Array
	var i: int = 0
	while i < events.size():
		var row: Dictionary = events[i] as Dictionary
		var kind: String = str(row.get("kind", row.get("op", "")))
		if kind == "teleport" or kind == "force_kill":
			errors.append("pit_fall official ledger contains %s" % kind)
		i += 1
	return errors


static func no_tunnel(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var solid: Dictionary = await SimReplay.play_path(
		app, "%s/no_tunnel_solid.json" % SimConstants.LOCO_TRACE_DIR
	)
	_record_apply_batch(int(solid.get("ticks", 0)), bool(solid.get("ok", false)))
	_remember_end(solid)
	var solid_x: float = 0.0
	var solid_dead: int = 0
	var tunneled: bool = true
	if not bool(solid.get("ok", false)):
		errors.append("no_tunnel_solid replay failed: %s" % _join(solid))
	else:
		var p1: Dictionary = _fighter_row(solid.get("final_state", {}) as Dictionary, 0)
		solid_x = SimConstants.dequantize(int(p1.get("x", 0)))
		solid_dead = int(p1.get("dead", 0))
		tunneled = solid_x <= 16.0
		if tunneled:
			errors.append("tunneled through storage left wall x=%s" % str(solid_x))
		if solid_dead == 1:
			errors.append("storage wall walk should not pit-kill")
	var oneway: Dictionary = await SimReplay.play_path(
		app, "%s/no_tunnel_oneway.json" % SimConstants.LOCO_TRACE_DIR
	)
	_record_apply_batch(int(oneway.get("ticks", 0)), bool(oneway.get("ok", false)))
	_remember_end(oneway)
	var oneway_y: float = 0.0
	var oneway_dead: int = 1
	var fell: bool = true
	var kill_plane: float = Maps.kill_y("hazardous")
	if not bool(oneway.get("ok", false)):
		errors.append("no_tunnel_oneway replay failed: %s" % _join(oneway))
	else:
		var row: Dictionary = _fighter_row(oneway.get("final_state", {}) as Dictionary, 0)
		oneway_dead = int(row.get("dead", 0))
		oneway_y = SimConstants.dequantize(int(row.get("y", 0)))
		fell = oneway_dead == 1 or oneway_y > kill_plane - 8.0
		if oneway_dead == 1:
			errors.append("fell through hazardous one-way platform")
		if oneway_y > kill_plane - 8.0:
			errors.append("one-way stand y dropped to kill plane y=%s" % str(oneway_y))
	app.start_fight("vs2", "hazardous", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var fighter: Fighter = session.player1()
	_apply_p1(session, PackedStringArray(), 16, 0.0)
	if not fighter.is_on_floor():
		errors.append("hazardous spawn must rest on one-way")
	var y0: float = fighter.global_position.y
	_apply_p1(session, PackedStringArray(["jump"]), 10, 0.0)
	_apply_p1(session, PackedStringArray(), 36, 0.0)
	var y1: float = fighter.global_position.y
	var sank: bool = fighter.dead or fighter.death_cause == "pit" or y1 > y0 + 8.0
	if fighter.dead or fighter.death_cause == "pit":
		errors.append("jump-land on one-way fell through")
	if y1 > y0 + 8.0:
		errors.append("one-way landing sank y0=%s y1=%s" % [str(y0), str(y1)])
	var verdict: String = "none"
	if tunneled or fell or sank or not bool(solid.get("ok", false)) or not bool(oneway.get("ok", false)):
		verdict = "fail"
	outcome_tunnel = {
		"verdict": verdict,
		"source": "trace_final_state+live_oneway_land",
		"solid": {
			"map_id": "storage",
			"x": solid_x,
			"dead": solid_dead,
			"min_legal_x": 16.0,
			"tunneled": tunneled,
		},
		"oneway": {
			"map_id": "hazardous",
			"y": oneway_y,
			"dead": oneway_dead,
			"kill_y": kill_plane,
			"fell_through": fell,
		},
		"oneway_jump_land": {
			"y0": y0,
			"y1": y1,
			"sank": sank,
			"death_cause": fighter.death_cause,
		},
	}
	return errors


static func camera_fit(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "rooftops", 0)
	var session: GameSession = app.session
	if session == null or session.camera == null:
		errors.append("camera missing after start_fight")
		outcome_camera = {"verdict": "fail", "reason": "missing camera"}
		return errors
	var cam: Camera2D = session.camera
	if not cam.is_inside_tree():
		errors.append("camera is not inside the scene tree")
		outcome_camera = {"verdict": "fail", "reason": "camera not in tree"}
		return errors
	cam.make_current()
	await SimReplay.sync_physics(app)
	var tree: SceneTree = app.get_tree()
	if tree != null:
		await tree.process_frame
		await tree.process_frame
	var vp: Viewport = app.get_viewport()
	if vp == null:
		errors.append("missing viewport for independent camera check")
		outcome_camera = {"verdict": "fail", "reason": "missing viewport"}
		return errors
	var current: Camera2D = vp.get_camera_2d()
	var vis: Rect2 = vp.get_visible_rect()
	var zoom: Vector2 = cam.zoom
	var pos: Vector2 = cam.position
	var arena: Vector2 = Maps.pixel_size(session.map_id)
	var eps: float = Locomotion.epsilon()
	var visible_world: Vector2 = Vector2(
		vis.size.x / maxf(zoom.x, 0.0001),
		vis.size.y / maxf(zoom.y, 0.0001)
	)
	var covers: bool = visible_world.x + eps >= arena.x and visible_world.y + eps >= arena.y
	var centered: bool = absf(pos.x - arena.x * 0.5) <= 1.0 and absf(pos.y - arena.y * 0.5) <= 1.0
	var mode: String = str(Locomotion.camera().get("mode", ""))
	var current_ok: bool = current == cam
	if not current_ok:
		errors.append("viewport get_camera_2d is not the session Camera2D")
	if mode != "arena_fit":
		errors.append("locomotion.json camera mode must be arena_fit")
	if not covers:
		errors.append(
			"independent viewport does not cover arena visible=%s arena=%s zoom=%s"
			% [str(visible_world), str(arena), str(zoom)]
		)
	if not centered:
		errors.append("independent camera position not arena center pos=%s arena=%s" % [str(pos), str(arena)])
	var verdict: String = "fail"
	if covers and centered and mode == "arena_fit" and current_ok:
		verdict = "arena_fit"
	outcome_camera = {
		"verdict": verdict,
		"source": "Viewport.get_visible_rect+get_camera_2d+Camera2D.zoom/position",
		"not_product_helper": true,
		"map_id": session.map_id,
		"mode": mode,
		"ledger": "RL-CAM-ARENA",
		"viewport_visible_rect": {
			"x": vis.position.x,
			"y": vis.position.y,
			"w": vis.size.x,
			"h": vis.size.y,
		},
		"camera_zoom": {"x": zoom.x, "y": zoom.y},
		"camera_position": {"x": pos.x, "y": pos.y},
		"arena_size": {"x": arena.x, "y": arena.y},
		"visible_world": {"x": visible_world.x, "y": visible_world.y},
		"covers_arena": covers,
		"centered": centered,
		"current_is_session_camera": current_ok,
	}
	if session.clock != null:
		snapshot_end = session.snapshot()
	_capture_viewport_png(vp, "arena_fit_rooftops")
	return errors


static func live_input_events(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "police", 0)
	var session: GameSession = app.session
	if session == null:
		errors.append("live loco missing session")
		return errors
	var p1: Fighter = session.player1()
	var viewport: Viewport = app.get_viewport()
	await SimReplay.sync_physics(app)
	InputInjector.release_known(viewport)
	InputActions.reset_edges()
	used_parse_input_event += 1
	InputInjector.inject_key(KEY_RIGHT, true, viewport)
	var x0: float = p1.global_position.x
	var n: int = 0
	while n < 20:
		if not session.step_from_live_input():
			errors.append("live walk step_from_live_input failed reject=%s" % str(session.last_reject))
			break
		n += 1
	if p1.global_position.x <= x0 + 2.0:
		errors.append("InputEvent RIGHT did not walk P1 x0=%s x1=%s" % [str(x0), str(p1.global_position.x)])
	InputInjector.inject_key(KEY_RIGHT, false, viewport)
	InputInjector.inject_key(KEY_DOWN, true, viewport)
	n = 0
	while n < 8:
		session.step_from_live_input()
		n += 1
	if not p1.crouched:
		errors.append("InputEvent DOWN did not crouch P1")
	InputInjector.inject_key(KEY_DOWN, false, viewport)
	InputInjector.inject_key(KEY_UP, true, viewport)
	n = 0
	while n < 6:
		session.step_from_live_input()
		n += 1
	if p1.is_on_floor() and p1.velocity.y >= 0.0:
		errors.append("InputEvent UP did not jump P1")
	InputInjector.release_known(viewport)
	return errors


static func _jump_peak(app: App, hold_ticks: int) -> Dictionary:
	app.start_fight("vs2", "police", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	_apply_p1(session, PackedStringArray(), 12, 0.0)
	var start_y: float = p1.global_position.y
	var peak: float = start_y
	_apply_p1(session, PackedStringArray(["jump"]), hold_ticks, 0.0)
	if p1.global_position.y < peak:
		peak = p1.global_position.y
	var n: int = 0
	while n < 40:
		if p1.global_position.y < peak:
			peak = p1.global_position.y
		_apply_p1(session, PackedStringArray(), 1, 0.0)
		n += 1
	return {
		"start_y": start_y,
		"peak_y": peak,
	}


static func _jump_buffer(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "police", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	_apply_p1(session, PackedStringArray(), 14, 0.0)
	var floor_y: float = p1.global_position.y
	_apply_p1(session, PackedStringArray(["jump"]), 8, 0.0)
	var n: int = 0
	while n < 50 and p1.velocity.y <= 0.0 and not p1.dead:
		_apply_p1(session, PackedStringArray(), 1, 0.0)
		n += 1
	n = 0
	while n < 40 and p1.global_position.y < floor_y - 10.0 and not p1.dead:
		_apply_p1(session, PackedStringArray(), 1, 0.0)
		n += 1
	if p1.dead or p1.is_on_floor():
		errors.append("jump buffer never approached landing")
		return errors
	_apply_p1(session, PackedStringArray(["jump"]), 1, 0.0)
	_apply_p1(session, PackedStringArray(), 8, 0.0)
	if p1.velocity.y >= -40.0 and p1.is_on_floor():
		errors.append("jump buffer did not fire on landing vy=%s floor=%s" % [
			str(p1.velocity.y), str(p1.is_on_floor())
		])
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


static func _capture_viewport_png(vp: Viewport, stem: String) -> void:
	if vp == null or DisplayServer.get_name() == "headless":
		return
	var ev: String = OS.get_environment("HH_VF_EVIDENCE_DIR")
	if ev == "":
		return
	DirAccess.make_dir_recursive_absolute(ev.path_join("screens"))
	var tex: ViewportTexture = vp.get_texture()
	if tex == null:
		print("HH_VF_LOCO SCREENSHOT missing viewport texture")
		return
	var img: Image = tex.get_image()
	if img == null:
		print("HH_VF_LOCO SCREENSHOT get_image null")
		return
	var vis: Rect2 = vp.get_visible_rect()
	var path: String = ev.path_join("screens").path_join("%s_%dx%d.png" % [
		stem, int(vis.size.x), int(vis.size.y)
	])
	var err: Error = img.save_png(path)
	print("HH_VF_LOCO SCREENSHOT err=%d path=%s" % [int(err), path])


static func _capture_start(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "police", 0)
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
	if str(outcome_hash2.get("verdict", "")) != "match":
		errors.append("HASH2 outcome is %s" % str(outcome_hash2.get("verdict", "unproven")))
	if str(outcome_tunnel.get("verdict", "")) != "none":
		errors.append("TUNNEL outcome is %s" % str(outcome_tunnel.get("verdict", "unproven")))
	if str(outcome_camera.get("verdict", "")) != "arena_fit":
		errors.append("CAMERA outcome is %s" % str(outcome_camera.get("verdict", "unproven")))
	if used_apply_frames_succeeded <= 0 or used_apply_frames != used_apply_frames_succeeded:
		errors.append("USED_APPLY_FRAMES must count successful applies got=%d attempted=%d" % [
			used_apply_frames_succeeded, used_apply_frames_attempted
		])
	if used_apply_frames_attempted < used_apply_frames_succeeded:
		errors.append("apply attempted < succeeded")
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


static func _hash_pair(name: String, a: Dictionary, b: Dictionary) -> Dictionary:
	var pair: Dictionary = {
		"name": name,
		"hash_a": str(a.get("final_hash", "")),
		"hash_b": str(b.get("final_hash", "")),
		"ticks_a": int(a.get("ticks", 0)),
		"ticks_b": int(b.get("ticks", 0)),
		"ok_a": bool(a.get("ok", false)),
		"ok_b": bool(b.get("ok", false)),
		"hash_match": false,
		"max_dx": 0.0,
		"max_dy": 0.0,
		"within_epsilon": false,
		"compared_axes": ["x", "y"],
	}
	pair["hash_match"] = str(pair["hash_a"]) != "" and str(pair["hash_a"]) == str(pair["hash_b"])
	var eps: float = Locomotion.epsilon()
	var sa: Dictionary = a.get("final_state", {}) as Dictionary
	var sb: Dictionary = b.get("final_state", {}) as Dictionary
	var fa: Array = sa.get("fighters", []) as Array
	var fb: Array = sb.get("fighters", []) as Array
	var max_dx: float = 0.0
	var max_dy: float = 0.0
	var n: int = mini(fa.size(), fb.size())
	var i: int = 0
	while i < n:
		var ra: Dictionary = fa[i] as Dictionary
		var rb: Dictionary = fb[i] as Dictionary
		var dx: float = absf(
			SimConstants.dequantize(int(ra.get("x", 0))) - SimConstants.dequantize(int(rb.get("x", 0)))
		)
		var dy: float = absf(
			SimConstants.dequantize(int(ra.get("y", 0))) - SimConstants.dequantize(int(rb.get("y", 0)))
		)
		if dx > max_dx:
			max_dx = dx
		if dy > max_dy:
			max_dy = dy
		i += 1
	pair["max_dx"] = max_dx
	pair["max_dy"] = max_dy
	pair["within_epsilon"] = max_dx <= eps and max_dy <= eps and fa.size() == fb.size()
	return pair


static func _positions_within_epsilon(name: String, a: Dictionary, b: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var sa: Dictionary = a.get("final_state", {}) as Dictionary
	var sb: Dictionary = b.get("final_state", {}) as Dictionary
	var fa: Array = sa.get("fighters", []) as Array
	var fb: Array = sb.get("fighters", []) as Array
	if fa.size() != fb.size():
		errors.append("%s fighter count differs across runs" % name)
		return errors
	var eps: float = Locomotion.epsilon()
	var i: int = 0
	while i < fa.size():
		var ra: Dictionary = fa[i] as Dictionary
		var rb: Dictionary = fb[i] as Dictionary
		var dx: float = absf(
			SimConstants.dequantize(int(ra.get("x", 0))) - SimConstants.dequantize(int(rb.get("x", 0)))
		)
		var dy: float = absf(
			SimConstants.dequantize(int(ra.get("y", 0))) - SimConstants.dequantize(int(rb.get("y", 0)))
		)
		if dx > eps or dy > eps:
			errors.append("%s slot %d position delta x=%s y=%s exceeds epsilon %s" % [
				name, i, str(dx), str(dy), str(eps)
			])
		i += 1
	return errors


static func _fighter_row(state: Dictionary, slot: int) -> Dictionary:
	var rows: Array = state.get("fighters", []) as Array
	var i: int = 0
	while i < rows.size():
		var row: Dictionary = rows[i] as Dictionary
		if int(row.get("slot", -1)) == slot:
			return row
		i += 1
	return {}


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

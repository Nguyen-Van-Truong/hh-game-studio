class_name WorldCases
extends RefCounted

const _Catalog: GDScript = preload("res://src/world/world_catalog.gd")
const _Paths: GDScript = preload("res://src/world/world_paths.gd")
const _Spec: GDScript = preload("res://src/world/prop_spec.gd")
const _Body: GDScript = preload("res://src/world/prop_body.gd")

## VF4-WP1 official world / prop ownership cases.
## Proof is InputFrame apply_frames plus live InputEvent inject.
## 60 Hz is ledger:RL-SIM-FIXED-60 (assumption).
## Schema/layers/ownership stay assumption.
## Break / chain / throw stay unimplemented.
## RL-NADE-PROP stays deferred.
## Hold-to-aim stays ledger:RL-CTRL-HOLD-AIM (assumption).
## Y8 roll/dive stays unavailable. USED_APPLY_FRAMES counts success only.

static var used_step_fixed: int = 0
static var used_apply_frames: int = 0
static var used_apply_frames_attempted: int = 0
static var used_apply_frames_succeeded: int = 0
static var used_parse_input_event: int = 0
static var used_action_press: int = 0
static var outcome_schema: Dictionary = {}
static var outcome_layers: Dictionary = {}
static var outcome_spawn: Dictionary = {}
static var outcome_hash: Dictionary = {}
static var outcome_orphan: Dictionary = {}
static var outcome_path: Dictionary = {}
static var outcome_present: Dictionary = {}
static var outcome_author: Dictionary = {}
static var outcome_data: Dictionary = {}
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
	outcome_schema = {"verdict": "unproven"}
	outcome_layers = {"verdict": "unproven"}
	outcome_spawn = {"verdict": "unproven"}
	outcome_hash = {"verdict": "unproven"}
	outcome_orphan = {"verdict": "unproven"}
	outcome_path = {"verdict": "unproven"}
	outcome_present = {"verdict": "unproven"}
	outcome_author = {"verdict": "unproven"}
	outcome_data = {"verdict": "unproven"}
	outcome_live = {"verdict": "unproven"}
	outcome_replay = {"verdict": "unproven", "pairs": []}
	snapshot_start = {}
	snapshot_end = {}
	events_end = []
	events_all = []
	var errors: PackedStringArray = PackedStringArray()
	_append(errors, schema_and_data())
	_append(errors, layer_contract())
	_append(errors, path_gate())
	_append(errors, await _capture_start(app))
	_append(errors, await replay_traces_twice(app))
	_append(errors, await spawn_from_catalog(app))
	_append(errors, await hash_stable(app))
	_append(errors, await no_orphan_after_restart(app))
	_append(errors, await presentation_cannot_mutate(app))
	_append(errors, await authoring_is_data(app))
	_append(errors, await live_world(app))
	_append(errors, _require_outcomes())
	return errors


static func schema_and_data() -> PackedStringArray:
	var errors: PackedStringArray = _Catalog.validate()
	if not Maps.has_fixture("fx_world_open"):
		errors.append("world fixture missing from Maps")
	if Maps.display_name("fx_world_open") != "Prop Yard":
		errors.append("world fixture display name must be Prop Yard")
	var live: Dictionary = _Catalog.data()
	var missing_col: Dictionary = live.duplicate(true)
	var specs_a: Dictionary = missing_col.get("specs", {}) as Dictionary
	var static_row: Dictionary = specs_a.get("crate_static", {}) as Dictionary
	static_row.erase("collision")
	var rejected_col: PackedStringArray = _Catalog.validate_payload(missing_col)
	if rejected_col.is_empty():
		errors.append("SCHEMA must reject a payload whose crate_static collision is missing")
	var missing_vis: Dictionary = live.duplicate(true)
	var specs_b: Dictionary = missing_vis.get("specs", {}) as Dictionary
	var barrel_row: Dictionary = specs_b.get("barrel_explosive", {}) as Dictionary
	barrel_row.erase("visual")
	var rejected_vis: PackedStringArray = _Catalog.validate_payload(missing_vis)
	if rejected_vis.is_empty():
		errors.append("SCHEMA must reject a payload whose barrel visual is missing")
	outcome_schema = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"reject_missing_collision": not rejected_col.is_empty(),
		"reject_missing_visual": not rejected_vis.is_empty(),
		"kinds": _Catalog.ids().size(),
		"source": "data/world/catalog.json + schema.json + validate_payload reject-invalid",
	}
	outcome_data = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"tuning": true,
		"break_implemented": bool(live.get("break_implemented", true)),
		"chain_implemented": bool(live.get("chain_implemented", true)),
		"nade_prop": str(live.get("nade_prop_class", "")),
		"source": "world values are tuning; break/chain stay unimplemented",
	}
	return errors


static func layer_contract() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	if not SimCollisionLayers.matches_maps():
		errors.append("collision layer bits must match Maps.COL_*")
	var layers: Dictionary = _Catalog.layers()
	var named: Dictionary = layers.get("layers", {}) as Dictionary
	if int(named.get("prop", 0)) != Maps.COL_PROP:
		errors.append("prop layer bit must equal Maps.COL_PROP")
	if int(named.get("platform", 0)) != Maps.COL_PLATFORM:
		errors.append("platform layer bit must equal Maps.COL_PLATFORM")
	if int(named.get("pickup", 0)) != Maps.COL_PICKUP:
		errors.append("pickup layer bit must equal Maps.COL_PICKUP")
	var specs: PackedStringArray = _Catalog.ids()
	var i: int = 0
	while i < specs.size():
		var sid: String = String(specs[i])
		var spec: Dictionary = _Catalog.spec(sid)
		var kind: String = str(spec.get("kind", ""))
		var want: Dictionary = (layers.get("prop_masks", {}) as Dictionary).get(kind, {}) as Dictionary
		if str(_Spec.layer_name(spec)) != str(want.get("layer", "")):
			errors.append("%s layer must follow the named contract" % sid)
		i += 1
	outcome_layers = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"prop": Maps.COL_PROP,
		"platform": Maps.COL_PLATFORM,
		"pickup": Maps.COL_PICKUP,
		"source": "data/sim/collision_layers.json prop_masks",
	}
	return errors


static func path_gate() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var live: Dictionary = _Catalog.data()
	var escape: Dictionary = live.duplicate(true)
	var specs_a: Dictionary = escape.get("specs", {}) as Dictionary
	var crate: Dictionary = specs_a.get("crate_static", {}) as Dictionary
	crate["visual"] = {"path": "res://../secret.png"}
	var rejected_esc: PackedStringArray = _Catalog.validate_payload(escape)
	if rejected_esc.is_empty():
		errors.append("PATH must reject res://../ traversal")
	var abs_row: Dictionary = live.duplicate(true)
	var specs_b: Dictionary = abs_row.get("specs", {}) as Dictionary
	var dyn: Dictionary = specs_b.get("crate_dynamic", {}) as Dictionary
	dyn["visual"] = {"path": "C:/Windows/x.png"}
	var rejected_abs: PackedStringArray = _Catalog.validate_payload(abs_row)
	if rejected_abs.is_empty():
		errors.append("PATH must reject an absolute visual path")
	var user_row: Dictionary = live.duplicate(true)
	var specs_c: Dictionary = user_row.get("specs", {}) as Dictionary
	var kit: Dictionary = specs_c.get("kit_pickup", {}) as Dictionary
	kit["visual"] = {"path": "user://escape.png"}
	var rejected_user: PackedStringArray = _Catalog.validate_payload(user_row)
	if rejected_user.is_empty():
		errors.append("PATH must reject user://")
	if not bool(_Paths.is_inside_product("res://assets/art/prop_crate.png")):
		errors.append("PATH must accept original crate art under res://")
	if bool(_Paths.is_inside_product("res://../secret.png")):
		errors.append("PATH helper leaked a traversal path")
	if bool(_Paths.visual_ok("res://assets/art/no_such_prop.png")):
		errors.append("PATH must reject a missing visual")
	outcome_path = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"reject_traversal": not rejected_esc.is_empty(),
		"reject_absolute": not rejected_abs.is_empty(),
		"reject_user": not rejected_user.is_empty(),
		"accept_product": bool(_Paths.is_inside_product("res://assets/art/prop_crate.png")),
		"source": "WorldPaths editor/runtime product-root gate",
	}
	return errors


static func replay_traces_twice(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var paths: PackedStringArray = SimTrace.list_dir(SimConstants.WORLD_TRACE_DIR)
	if paths.size() < 2:
		errors.append("expected >=2 world traces, got %d" % paths.size())
	var required: PackedStringArray = PackedStringArray(["world_idle", "world_walk"])
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
		if "assumption" not in str(trace.get("hold_to_aim", "")):
			errors.append("%s must keep hold-to-aim assumption" % path.get_file())
		names.append(str(trace.get("name", path.get_file())))
		await _drain_physics(app)
		var a: Dictionary = await SimReplay.play_path(app, path)
		var hash_wa: String = str(a.get("world_hash", ""))
		await _drain_physics(app)
		var b: Dictionary = await SimReplay.play_path(app, path)
		var hash_wb: String = str(b.get("world_hash", ""))
		_record_apply_batch(int(a.get("ticks", 0)), bool(a.get("ok", false)))
		_record_apply_batch(int(b.get("ticks", 0)), bool(b.get("ok", false)))
		if not bool(a.get("ok", false)):
			errors.append("world %s run1 failed: %s" % [path.get_file(), _join(a)])
		if not bool(b.get("ok", false)):
			errors.append("world %s run2 failed: %s" % [path.get_file(), _join(b)])
		if not bool(a.get("used_apply_frames", false)) or bool(a.get("used_cmd_dicts", true)):
			errors.append("world %s MATCH used cmd dicts" % path.get_file())
		var hash_a: String = str(a.get("final_hash", ""))
		var hash_b: String = str(b.get("final_hash", ""))
		var match_ok: bool = hash_a != "" and hash_a == hash_b
		var world_ok: bool = hash_wa != "" and hash_wa == hash_wb
		if not match_ok:
			errors.append("world %s replay hashes differ" % path.get_file())
		if not world_ok:
			errors.append("world %s prop hashes differ" % path.get_file())
		pairs.append({
			"name": str(trace.get("name", path.get_file())),
			"hash_match": match_ok,
			"world_hash_match": world_ok,
			"ok_a": bool(a.get("ok", false)),
			"ok_b": bool(b.get("ok", false)),
			"hash_a": hash_a,
			"hash_b": hash_b,
			"world_a": hash_wa,
			"world_b": hash_wb,
		})
		_remember_end(a)
		_append_events(a.get("events", []) as Array)
		i += 1
	i = 0
	while i < required.size():
		if not names.has(String(required[i])):
			errors.append("missing world trace %s" % String(required[i]))
		i += 1
	var all_match: bool = pairs.size() >= 2
	var p: int = 0
	while p < pairs.size():
		var row: Dictionary = pairs[p] as Dictionary
		if not bool(row.get("hash_match", false)) or not bool(row.get("world_hash_match", false)):
			all_match = false
		p += 1
	outcome_replay = {
		"verdict": "match" if all_match and errors.is_empty() else "fail",
		"pairs": pairs,
		"source": "apply_frames world traces twice",
	}
	return errors


static func spawn_from_catalog(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_world_open", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	if session == null or session.world_owner == null:
		errors.append("SPAWN missing world owner")
		outcome_spawn = {"verdict": "fail"}
		return errors
	var want: Array = _Catalog.placements_for("fx_world_open")
	var got: int = _wcount(session)
	if got != want.size():
		errors.append("SPAWN count %d != placements %d" % [got, want.size()])
	var kinds: PackedStringArray = _wkinds(session)
	var required: PackedStringArray = _Spec.KINDS
	var i: int = 0
	while i < required.size():
		if not kinds.has(String(required[i])):
			errors.append("SPAWN missing kind %s" % String(required[i]))
		i += 1
	var spawn_errs: PackedStringArray = _werrs(session)
	if spawn_errs.size() != 0:
		errors.append("SPAWN owner errors %s" % ",".join(spawn_errs))
	_apply_idle(session, 4)
	outcome_spawn = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"count": got,
		"expected": want.size(),
		"kinds": kinds,
		"source": "WorldOwner.spawn_map from catalog placements",
	}
	_remember_session(session)
	return errors


static func hash_stable(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_world_open", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var h0: String = _whash(session)
	_apply_idle(session, 20)
	var h1: String = _whash(session)
	if h0 == "" or h0 != h1:
		errors.append("HASH idle ticks drifted")
	app.start_fight("vs2", "fx_world_open", 0)
	await SimReplay.sync_physics(app)
	session = app.session
	var h2: String = _whash(session)
	if h2 != h0:
		errors.append("HASH second boot differed")
	outcome_hash = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"idle": h0 == h1,
		"reboot": h0 == h2,
		"hash": h0,
		"source": "WorldOwner.stable_hash idle + reboot",
	}
	_remember_session(session)
	return errors


static func no_orphan_after_restart(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_world_open", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var old_ids: PackedInt64Array = _wids(session)
	var old_count: int = _wcount(session)
	if old_count < 6:
		errors.append("ORPHAN first boot spawned %d" % old_count)
	app.start_fight("vs2", "fx_world_open", 0)
	await _drain_physics(app)
	session = app.session
	var new_count: int = _wcount(session)
	if new_count != old_count:
		errors.append("ORPHAN restart count %d != %d" % [new_count, old_count])
	var i: int = 0
	while i < old_ids.size():
		if is_instance_id_valid(int(old_ids[i])):
			errors.append("ORPHAN old instance %d still valid" % int(old_ids[i]))
		i += 1
	app.restart_to_title()
	await _drain_physics(app)
	var leftover: Array = app.get_tree().get_nodes_in_group(str(_Body.GROUP))
	if not leftover.is_empty():
		errors.append("ORPHAN title leftover %d prop nodes" % leftover.size())
	outcome_orphan = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"old_count": old_count,
		"new_count": new_count,
		"old_ids": old_ids.size(),
		"title_leftover": leftover.size(),
		"source": "restart frees prior PropBody instance ids",
	}
	return errors


static func presentation_cannot_mutate(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_world_open", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var owner: RefCounted = session.world_owner
	var before: int = int(owner.call("count_valid"))
	var body: Node2D = (owner.get("bodies") as Array)[0] as Node2D
	var hp0: float = float(body.get("health"))
	var pos0: Vector2 = body.global_position
	var rejected_d: PackedStringArray = PackedStringArray()
	var rejected_h: PackedStringArray = PackedStringArray()
	var rejected_m: PackedStringArray = PackedStringArray()
	var rd: Variant = owner.call("try_mutate_from_view", body.get("view"), "despawn")
	var rh: Variant = owner.call("try_mutate_from_view", body.get("view"), "health", 0.0)
	var rm: Variant = owner.call("try_mutate_from_view", body.get("view"), "move", 9.0)
	if rd is PackedStringArray:
		rejected_d = rd as PackedStringArray
	if rh is PackedStringArray:
		rejected_h = rh as PackedStringArray
	if rm is PackedStringArray:
		rejected_m = rm as PackedStringArray
	if rejected_d.is_empty() or rejected_h.is_empty() or rejected_m.is_empty():
		errors.append("PRESENT must reject view mutation (presentation cannot)")
	if int(owner.call("count_valid")) != before:
		errors.append("PRESENT despawn leaked through the view")
	if float(body.get("health")) != hp0:
		errors.append("PRESENT health mutated")
	if body.global_position != pos0:
		errors.append("PRESENT moved a prop")
	outcome_present = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"despawn": ",".join(rejected_d),
		"health": ",".join(rejected_h),
		"move": ",".join(rejected_m),
		"count": int(owner.call("count_valid")),
		"source": "PropView mutate requests rejected by WorldOwner",
	}
	_remember_session(session)
	return errors


static func authoring_is_data(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "rooftops", 0)
	await SimReplay.sync_physics(app)
	var rooftops_n: int = -1
	if app.session == null or app.session.world_owner == null:
		errors.append("AUTHOR rooftops missing owner")
	else:
		rooftops_n = _wcount(app.session)
		if rooftops_n != 0:
			errors.append("AUTHOR live maps must not grow hard-coded props")
	app.start_fight("vs2", "fx_world_open", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var placed: int = _Catalog.placements_for("fx_world_open").size()
	if _wcount(session) != placed:
		errors.append("AUTHOR fixture count must follow catalog placements")
	outcome_author = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"rooftops": rooftops_n,
		"fixture": _wcount(session),
		"placements": placed,
		"source": "catalog placements; GameSession has no per-prop spawn",
	}
	_remember_session(session)
	return errors


static func live_world(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_world_open", 0)
	var session: GameSession = app.session
	var viewport: Viewport = app.get_viewport()
	await SimReplay.sync_physics(app)
	InputInjector.release_known(viewport)
	InputActions.reset_edges()
	used_parse_input_event += 1
	var h0: String = _whash(session)
	var n0: int = _wcount(session)
	InputInjector.inject_key(KEY_RIGHT, true, viewport)
	var n: int = 0
	while n < 8:
		session.step_from_live_input()
		n += 1
	InputInjector.inject_key(KEY_RIGHT, false, viewport)
	session.step_from_live_input()
	var live_ok: bool = _wcount(session) == n0
	var h1: String = _whash(session)
	if not live_ok:
		errors.append("LIVE walk must keep owned props")
	if h1 != h0:
		errors.append("LIVE walk must not mutate the prop hash")
	InputInjector.release_known(viewport)
	outcome_live = {
		"verdict": "pass" if live_ok and h1 == h0 else "fail",
		"count": _wcount(session),
		"hash_stable": h1 == h0,
		"source": "parse_input_event KEY_RIGHT + step_from_live_input",
	}
	_remember_session(session)
	return errors


static func _require_outcomes() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var labels: PackedStringArray = PackedStringArray([
		"SCHEMA", "LAYERS", "SPAWN", "HASH", "ORPHAN", "PATH", "PRESENT", "AUTHOR", "DATA", "LIVE"
	])
	var rows: Array = [
		outcome_schema, outcome_layers, outcome_spawn, outcome_hash, outcome_orphan,
		outcome_path, outcome_present, outcome_author, outcome_data, outcome_live
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


static func _whash(session: GameSession) -> String:
	if session == null or session.world_owner == null:
		return ""
	return str(session.world_owner.call("stable_hash"))


static func _wcount(session: GameSession) -> int:
	if session == null or session.world_owner == null:
		return -1
	return int(session.world_owner.call("count_valid"))


static func _wkinds(session: GameSession) -> PackedStringArray:
	if session == null or session.world_owner == null:
		return PackedStringArray()
	var v: Variant = session.world_owner.call("kinds_present")
	if v is PackedStringArray:
		return v as PackedStringArray
	return PackedStringArray()


static func _wids(session: GameSession) -> PackedInt64Array:
	if session == null or session.world_owner == null:
		return PackedInt64Array()
	var v: Variant = session.world_owner.call("instance_ids")
	if v is PackedInt64Array:
		return v as PackedInt64Array
	return PackedInt64Array()


static func _wsnap(session: GameSession) -> Array:
	if session == null or session.world_owner == null:
		return []
	var v: Variant = session.world_owner.call("snapshot")
	if v is Array:
		return v as Array
	return []


static func _werrs(session: GameSession) -> PackedStringArray:
	if session == null or session.world_owner == null:
		return PackedStringArray()
	var v: Variant = session.world_owner.get("last_errors")
	if v is PackedStringArray:
		return v as PackedStringArray
	return PackedStringArray()


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
	app.start_fight("vs2", "fx_world_open", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	if session == null:
		errors.append("start snapshot missing session")
		return errors
	snapshot_start = session.snapshot()
	if session.world_owner != null:
		snapshot_start["world_props"] = _wsnap(session)
		snapshot_start["world_hash"] = _whash(session)
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
	if session.world_owner != null:
		snapshot_end["world_props"] = _wsnap(session)
		snapshot_end["world_hash"] = _whash(session)
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

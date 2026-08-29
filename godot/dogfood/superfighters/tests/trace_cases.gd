class_name TraceCases
extends RefCounted

## VF1-WP3 official InputFrame record/replay cases.
## MATCH uses apply_frames, not cmd-dict step_fixed.


static func run_all(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	_append(errors, schema_and_kinds())
	_append(errors, await official_replay_twice(app))
	_append(errors, await mutate_one_key_fails(app))
	_append(errors, await record_from_real_input(app))
	_append(errors, await fixture_distinct(app))
	_append(errors, await official_beats(app))
	return errors


static func schema_and_kinds() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var schema: Dictionary = SimConstants.load_json(SimConstants.TRACE_SCHEMA_PATH)
	if schema.is_empty():
		errors.append("missing data/sim/trace.json")
		return errors
	if str(schema.get("schema", "")) != SimConstants.TRACE_ID:
		errors.append("trace schema id mismatch")
	if bool(schema.get("y8_tick_rate_claimed", true)):
		errors.append("trace schema must not claim a Y8 tick rate")
	if str(schema.get("title", "")) != "Vault Fighters":
		errors.append("trace schema title must be Vault Fighters")
	var official: PackedStringArray = SimTrace.list_dir(SimConstants.OFFICIAL_TRACE_DIR)
	if official.size() < 5:
		errors.append("expected >=5 official traces, got %d" % official.size())
	var names: PackedStringArray = PackedStringArray()
	var i: int = 0
	while i < official.size():
		var path: String = String(official[i])
		var trace: Dictionary = SimTrace.load_path(path)
		var verr: PackedStringArray = SimTrace.validate(trace)
		var j: int = 0
		while j < verr.size():
			errors.append("%s %s" % [path.get_file(), String(verr[j])])
			j += 1
		names.append(str(trace.get("name", path.get_file())))
		i += 1
	var required: PackedStringArray = PackedStringArray([
		"title_fight_restart", "walk_jump_crouch", "fire_throw", "death_lose", "win_restart"
	])
	i = 0
	while i < required.size():
		if not names.has(String(required[i])):
			errors.append("missing official trace %s" % String(required[i]))
		i += 1
	if not SimReplay.supports_window():
		errors.append("replay harness must support window mode")
	return errors


static func official_replay_twice(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var official: PackedStringArray = SimTrace.list_dir(SimConstants.OFFICIAL_TRACE_DIR)
	var i: int = 0
	while i < official.size():
		var path: String = String(official[i])
		var a: Dictionary = await SimReplay.play_path(app, path)
		var b: Dictionary = await SimReplay.play_path(app, path)
		if not bool(a.get("ok", false)):
			errors.append("official %s run1 failed: %s" % [
				path.get_file(), _join_errors(a)
			])
		if not bool(b.get("ok", false)):
			errors.append("official %s run2 failed: %s" % [
				path.get_file(), _join_errors(b)
			])
		if not bool(a.get("used_apply_frames", false)) or bool(a.get("used_cmd_dicts", true)):
			errors.append("official %s MATCH used cmd dicts" % path.get_file())
		if str(a.get("final_hash", "")) == "" or str(a.get("final_hash", "")) != str(b.get("final_hash", "")):
			errors.append("official %s replay hashes differ" % path.get_file())
		if str(a.get("events_hash", "")) != str(b.get("events_hash", "")):
			errors.append("official %s event ledger hashes differ" % path.get_file())
		if not _hashes_equal(a.get("hashes", []) as Array, b.get("hashes", []) as Array):
			errors.append("official %s per-N snapshot hashes differ" % path.get_file())
		i += 1
	return errors


static func mutate_one_key_fails(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var path: String = "%s/walk_jump_crouch.json" % SimConstants.OFFICIAL_TRACE_DIR
	var trace: Dictionary = SimTrace.load_path(path)
	if trace.is_empty():
		errors.append("mutate missing walk_jump_crouch")
		return errors
	var original: Dictionary = await SimReplay.play(app, trace)
	var mutated: Dictionary = await SimReplay.play(app, SimTrace.mutate_one_key(trace))
	if not bool(original.get("ok", false)):
		errors.append("mutate baseline replay failed")
		return errors
	if str(original.get("final_hash", "")) == str(mutated.get("final_hash", "")):
		errors.append("changing one key did not change replay hash")
	return errors


static func record_from_real_input(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "police", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	if session == null:
		errors.append("record missing session")
		return errors
	var rec: SimRecorder = SimRecorder.new()
	rec.trace_name = "live_right"
	rec.begin(session, "live_input")
	Input.action_press("p1_right")
	var ok: bool = rec.record_live_tick(session)
	Input.action_release("p1_right")
	if not ok:
		errors.append("record_live_tick rejected real Input")
	if rec.bundles.is_empty():
		errors.append("record captured no InputFrames")
		return errors
	var bundle: Array = rec.bundles[0] as Array
	if bundle.is_empty() or not (bundle[0] is InputFrame):
		errors.append("record did not store a typed InputFrame")
		return errors
	var frame: InputFrame = bundle[0] as InputFrame
	if not frame.is_held("right"):
		errors.append("live InputFrame missing held right")
	if absf(frame.move_x) < 0.35 and not frame.is_held("right"):
		errors.append("live InputFrame has no right axis")
	var p1: Fighter = session.player1()
	var x1: float = p1.global_position.x if p1 != null else 0.0
	var recorded: Dictionary = rec.finish()
	var replayed: Dictionary = await SimReplay.play(app, recorded)
	if not bool(replayed.get("ok", false)):
		errors.append("replay of live record failed: %s" % _join_errors(replayed))
	var state: Dictionary = replayed.get("final_state", {}) as Dictionary
	if float(state.get("p1_x", 0.0)) <= 104.0 and x1 <= 104.0:
		errors.append("live record/replay did not move P1")
	if bool(recorded.get("y8_tick_rate_claimed", true)):
		errors.append("recorded trace claimed a Y8 tick rate")
	return errors


static func fixture_distinct(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var path: String = "%s/teleport_force_kill.json" % SimConstants.FIXTURE_TRACE_DIR
	var fixture: Dictionary = SimTrace.load_path(path)
	if fixture.is_empty():
		errors.append("missing fixture teleport_force_kill")
		return errors
	if str(fixture.get("kind", "")) != "fixture":
		errors.append("fixture kind must be fixture")
	var played: Dictionary = await SimReplay.play(app, fixture)
	if not bool(played.get("ok", false)):
		errors.append("fixture replay failed: %s" % _join_errors(played))
	if not _has_event_kind(played, "force_kill"):
		errors.append("fixture replay must log force_kill")
	if not _has_event_kind(played, "teleport"):
		errors.append("fixture replay must log teleport")
	var fake: Dictionary = fixture.duplicate(true)
	fake["kind"] = "official"
	var rejected: Dictionary = await SimReplay.play(app, fake)
	if bool(rejected.get("ok", false)):
		errors.append("fixture ops accepted as official")
	return errors


static func official_beats(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var title: Dictionary = await SimReplay.play_path(
		app, "%s/title_fight_restart.json" % SimConstants.OFFICIAL_TRACE_DIR
	)
	if not bool(title.get("title_visible", false)):
		errors.append("title_fight_restart must show title after restart")
	if not bool(title.get("session_cleared", false)):
		errors.append("title_fight_restart must clear session")
	var walk: Dictionary = await SimReplay.play_path(
		app, "%s/walk_jump_crouch.json" % SimConstants.OFFICIAL_TRACE_DIR
	)
	var walk_state: Dictionary = walk.get("final_state", {}) as Dictionary
	if float(walk_state.get("p1_x", 0.0)) <= 110.0:
		errors.append("walk_jump_crouch P1 did not walk right")
	if not _fighter_crouched(walk_state, 0):
		errors.append("walk_jump_crouch final P1 must be crouched")
	var walk_trace: Dictionary = SimTrace.load_path(
		"%s/walk_jump_crouch.json" % SimConstants.OFFICIAL_TRACE_DIR
	)
	if not _expanded_has_action(walk_trace, "jump"):
		errors.append("walk_jump_crouch missing jump InputFrames")
	var fire: Dictionary = await SimReplay.play_path(
		app, "%s/fire_throw.json" % SimConstants.OFFICIAL_TRACE_DIR
	)
	if not _has_event_kind(fire, "bullet"):
		errors.append("fire_throw must spawn a bullet via InputFrame release")
	if not _has_event_kind(fire, "nade"):
		errors.append("fire_throw must spawn a grenade via InputFrame release")
	var death: Dictionary = await SimReplay.play_path(
		app, "%s/death_lose.json" % SimConstants.OFFICIAL_TRACE_DIR
	)
	var death_state: Dictionary = death.get("final_state", {}) as Dictionary
	if str(death_state.get("outcome", "")) != "lose":
		errors.append("death_lose outcome must be lose")
	if not bool(death_state.get("p1_dead", false)):
		errors.append("death_lose P1 must be dead")
	if _death_cause(death, 0) != "pit":
		errors.append("death_lose cause must be pit, got %s" % _death_cause(death, 0))
	if _has_event_kind(death, "force_kill") or _death_cause(death, 0) == "script":
		errors.append("official death used force_kill/script")
	var win: Dictionary = await SimReplay.play_path(
		app, "%s/win_restart.json" % SimConstants.OFFICIAL_TRACE_DIR
	)
	var win_state: Dictionary = win.get("final_state", {}) as Dictionary
	if str(win_state.get("outcome", "")) != "win":
		errors.append("win_restart outcome must be win")
	if _death_cause(win, 1) != "damage":
		errors.append("win_restart foe cause must be damage, got %s" % _death_cause(win, 1))
	if _has_event_kind(win, "force_kill") or _death_cause(win, 1) == "script":
		errors.append("official win used force_kill/script")
	if not bool(win.get("title_visible", false)):
		errors.append("win_restart must return to title")
	return errors


static func _fighter_crouched(state: Dictionary, slot: int) -> bool:
	var rows: Array = state.get("fighters", []) as Array
	var i: int = 0
	while i < rows.size():
		var row: Dictionary = rows[i] as Dictionary
		if int(row.get("slot", -1)) == slot:
			return int(row.get("crouched", 0)) == 1
		i += 1
	return false


static func _death_cause(result: Dictionary, slot: int) -> String:
	var events: Array = result.get("events", []) as Array
	var i: int = 0
	while i < events.size():
		var row: Dictionary = events[i] as Dictionary
		if str(row.get("kind", "")) != "death":
			i += 1
			continue
		var payload: Dictionary = row.get("payload", {}) as Dictionary
		if int(payload.get("slot", -1)) == slot:
			return str(payload.get("cause", ""))
		i += 1
	var state: Dictionary = result.get("final_state", {}) as Dictionary
	var rows: Array = state.get("fighters", []) as Array
	i = 0
	while i < rows.size():
		var fighter: Dictionary = rows[i] as Dictionary
		if int(fighter.get("slot", -1)) == slot:
			return str(fighter.get("death_cause", ""))
		i += 1
	return ""


static func _has_event_kind(result: Dictionary, kind: String) -> bool:
	var events: Array = result.get("events", []) as Array
	var i: int = 0
	while i < events.size():
		var row: Dictionary = events[i] as Dictionary
		if str(row.get("kind", "")) == kind:
			return true
		i += 1
	return false


static func _expanded_has_action(trace: Dictionary, action: String) -> bool:
	var bundles: Array = SimTrace.expand_tick_bundles(trace)
	var i: int = 0
	while i < bundles.size():
		var slots: Array = bundles[i] as Array
		if slots.is_empty():
			i += 1
			continue
		var frame: Dictionary = slots[0] as Dictionary
		var held: Array = frame.get("held", []) as Array
		var pressed: Array = frame.get("pressed", []) as Array
		if held.has(action) or pressed.has(action):
			return true
		i += 1
	return false


static func _hashes_equal(a: Array, b: Array) -> bool:
	if a.size() != b.size():
		return false
	var i: int = 0
	while i < a.size():
		var da: Dictionary = a[i] as Dictionary
		var db: Dictionary = b[i] as Dictionary
		if int(da.get("tick", -1)) != int(db.get("tick", -2)):
			return false
		if str(da.get("hash", "")) != str(db.get("hash", "")):
			return false
		i += 1
	return true


static func _join_errors(result: Dictionary) -> String:
	var raw: Variant = result.get("errors", PackedStringArray())
	if raw is PackedStringArray:
		return ",".join(raw as PackedStringArray)
	if raw is Array:
		var parts: PackedStringArray = PackedStringArray()
		var arr: Array = raw as Array
		var i: int = 0
		while i < arr.size():
			parts.append(str(arr[i]))
			i += 1
		return ",".join(parts)
	return str(raw)


static func _append(into: PackedStringArray, extra: PackedStringArray) -> void:
	var i: int = 0
	while i < extra.size():
		into.append(String(extra[i]))
		i += 1

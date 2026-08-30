class_name MapCases
extends RefCounted

## VF5-WP1 layered map schema, graph, validator, semantic author.
## Proof is hash roundtrip + command ACK + live apply_frames.
## 60 Hz is ledger:RL-SIM-FIXED-60 (assumption). Not Y8 observed.

const _MapCatalog: GDScript = preload("res://src/maps/map_catalog.gd")
const _MapCodec: GDScript = preload("res://src/maps/map_codec.gd")
const _MapGraph: GDScript = preload("res://src/maps/map_graph.gd")
const _MapValidator: GDScript = preload("res://src/maps/map_validator.gd")
const _MapAuthor: GDScript = preload("res://src/maps/map_author.gd")
const _ArenaSpec: GDScript = preload("res://src/maps/arena_spec.gd")

const AUTHOR_TRACE: String = "res://tests/traces/maps/map_author.json"

static var used_step_fixed: int = 0
static var used_apply_frames: int = 0
static var used_apply_frames_attempted: int = 0
static var used_apply_frames_succeeded: int = 0
static var used_parse_input_event: int = 0
static var used_action_press: int = 0
static var outcome_schema: Dictionary = {}
static var outcome_roundtrip: Dictionary = {}
static var outcome_graph: Dictionary = {}
static var outcome_reject: Dictionary = {}
static var outcome_author: Dictionary = {}
static var outcome_width: Dictionary = {}
static var outcome_spawn: Dictionary = {}
static var outcome_pit: Dictionary = {}
static var outcome_camera: Dictionary = {}
static var outcome_overlap: Dictionary = {}
static var outcome_live: Dictionary = {}
static var outcome_replay: Dictionary = {}
static var snapshot_start: Dictionary = {}
static var snapshot_end: Dictionary = {}
static var events_all: Array = []


static func run_all(app: App) -> PackedStringArray:
	used_step_fixed = 0
	used_apply_frames = 0
	used_apply_frames_attempted = 0
	used_apply_frames_succeeded = 0
	used_parse_input_event = 0
	used_action_press = 0
	outcome_schema = {"verdict": "unproven"}
	outcome_roundtrip = {"verdict": "unproven"}
	outcome_graph = {"verdict": "unproven"}
	outcome_reject = {"verdict": "unproven"}
	outcome_author = {"verdict": "unproven"}
	outcome_width = {"verdict": "unproven"}
	outcome_spawn = {"verdict": "unproven"}
	outcome_pit = {"verdict": "unproven"}
	outcome_camera = {"verdict": "unproven"}
	outcome_overlap = {"verdict": "unproven"}
	outcome_live = {"verdict": "unproven"}
	outcome_replay = {"verdict": "unproven", "pairs": []}
	snapshot_start = {}
	snapshot_end = {}
	events_all = []
	var errors: PackedStringArray = PackedStringArray()
	_append(errors, schema_and_data())
	_append(errors, await _capture_start(app))
	_append(errors, roundtrip_hash())
	_append(errors, graph_reaches())
	_append(errors, validator_rejects())
	_append(errors, author_commands())
	_append(errors, await live_layers(app))
	_append(errors, replay_twice())
	_append(errors, _require_outcomes())
	return errors


static func schema_and_data() -> PackedStringArray:
	var errors: PackedStringArray = _MapCatalog.validate()
	_append(errors, _ArenaSpec.validate())
	if Maps.grid("rooftops").is_empty():
		errors.append("DATA rooftops grid empty")
	if not _MapCatalog.has_id("rooftops") or not _MapCatalog.has_id("fx_map_author"):
		errors.append("DATA catalog missing live or author map")
	if Maps.display_name("fx_map_author") != "Draft Yard":
		errors.append("DATA authored display name must be Draft Yard")
	if Maps.display_name("rooftops") != "Skyline Relay":
		errors.append("DATA rooftops display name must be Skyline Relay")
	if Maps.display_name("storage") != "Pallet Annex":
		errors.append("DATA storage display name must be Pallet Annex")
	if Maps.display_name("police") != "Signal Court":
		errors.append("DATA police display name must be Signal Court")
	if Maps.display_name("fx_map_author").to_lower().contains("superfighter"):
		errors.append("DATA display name uses Superfighters trademark")
	var live: PackedStringArray = PackedStringArray(["rooftops", "storage", "police", "hazardous"])
	var i: int = 0
	while i < live.size():
		var mid: String = String(live[i])
		var doc: Dictionary = _MapCatalog.document(mid)
		var ascii: PackedStringArray = _MapCodec.to_ascii(doc)
		var back: Dictionary = _MapCodec.from_ascii(mid, ascii, Maps.display_name(mid), str(doc.get("theme", "")))
		if _MapCodec.stable_hash(doc) != _MapCodec.stable_hash(back):
			errors.append("DATA %s ascii export is not lossless" % mid)
		if Maps.count_char(mid, "H") < 1:
			errors.append("DATA %s missing ladder layer" % mid)
		if Maps.count_char(mid, "=") < 1:
			errors.append("DATA %s missing one-way layer" % mid)
		i += 1
	if Maps.count_char("storage", "c") < 1:
		errors.append("DATA storage crate tiles must stay on prop layer")
	if Maps.count_char("hazardous", "b") < 1:
		errors.append("DATA hazardous paint tiles must stay on hazard layer")
	outcome_schema = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"layered": true,
		"ascii_retired": true,
		"source": "catalog.json + layered arenas",
	}
	_event("map_schema", {"ok": errors.is_empty()})
	return errors


static func roundtrip_hash() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var ids: PackedStringArray = _MapCatalog.ids()
	var pairs: Array = []
	var i: int = 0
	while i < ids.size():
		var mid: String = String(ids[i])
		var doc: Dictionary = _MapCatalog.document(mid)
		var h0: String = _MapCodec.stable_hash(doc)
		var ser: String = _MapCodec.serialize(doc)
		var back: Dictionary = _MapCodec.deserialize(ser)
		var h1: String = _MapCodec.stable_hash(back)
		var match_ok: bool = h0 != "" and h0 == h1
		if not match_ok:
			errors.append("ROUNDTRIP %s hash mismatch" % mid)
		pairs.append({"id": mid, "hash": h0, "match": match_ok})
		i += 1
	outcome_roundtrip = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"pairs": pairs,
		"source": "_MapCodec.serialize/deserialize SHA-256",
	}
	_event("map_roundtrip", {"ok": errors.is_empty(), "count": pairs.size()})
	return errors


static func graph_reaches() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var ids: PackedStringArray = _MapCatalog.ids()
	var rows: Array = []
	var i: int = 0
	while i < ids.size():
		var mid: String = String(ids[i])
		var doc: Dictionary = _MapCatalog.document(mid)
		var missing: PackedStringArray = _MapGraph.missing_platforms(doc)
		_append(errors, missing)
		rows.append({
			"id": mid,
			"walkable": _MapGraph.walkable_cells(doc).size(),
			"platforms": _MapGraph.platforms(doc).size(),
			"missing": missing.size(),
		})
		i += 1
	outcome_graph = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"maps": rows,
		"jump_dx": _MapGraph.jump_dx(),
		"jump_dy": _MapGraph.jump_dy(),
		"source": "MapGraph reach from spawns",
	}
	_event("map_graph", {"ok": errors.is_empty()})
	return errors


static func validator_rejects() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var width_e: PackedStringArray = _MapValidator.validate_doc(_MapValidator.broken_width(), false, false)
	var overlap_e: PackedStringArray = _MapValidator.validate_doc(_MapValidator.broken_overlap(), false, false)
	var spawn_e: PackedStringArray = _MapValidator.validate_doc(_MapValidator.broken_spawn(), false, false)
	var camera_e: PackedStringArray = _MapValidator.validate_doc(_MapValidator.broken_camera(), false, false)
	var graph_e: PackedStringArray = _MapValidator.validate_doc(_MapValidator.broken_graph(), false, true)
	if width_e.is_empty():
		errors.append("REJECT width must fail")
	if overlap_e.is_empty():
		errors.append("REJECT overlap must fail")
	if spawn_e.is_empty():
		errors.append("REJECT spawn must fail")
	if camera_e.is_empty():
		errors.append("REJECT camera must fail")
	if graph_e.is_empty():
		errors.append("REJECT graph must fail")
	var live_ok: PackedStringArray = _MapValidator.validate_catalog()
	_append(errors, live_ok)
	outcome_width = {
		"verdict": "pass" if not width_e.is_empty() else "fail",
		"errors": width_e.size(),
		"source": "broken_width out of bounds",
	}
	outcome_overlap = {
		"verdict": "pass" if not overlap_e.is_empty() else "fail",
		"errors": overlap_e.size(),
		"source": "broken_overlap solid/one_way",
	}
	outcome_spawn = {
		"verdict": "pass" if not spawn_e.is_empty() else "fail",
		"errors": spawn_e.size(),
		"source": "broken_spawn no floor",
	}
	outcome_camera = {
		"verdict": "pass" if not camera_e.is_empty() else "fail",
		"errors": camera_e.size(),
		"source": "broken_camera exceeds 1280x720",
	}
	outcome_pit = {
		"verdict": "pass" if _MapValidator.pit_column_count(_MapCatalog.document("rooftops")) >= 1 else "fail",
		"rooftops": _MapValidator.pit_column_count(_MapCatalog.document("rooftops")),
		"storage": _MapValidator.pit_column_count(_MapCatalog.document("storage")),
		"source": "pit columns from layered blockers",
	}
	if str(outcome_pit.get("verdict", "")) != "pass":
		errors.append("PIT rooftops must keep pit columns")
	outcome_reject = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"width": width_e.size(),
		"overlap": overlap_e.size(),
		"spawn": spawn_e.size(),
		"camera": camera_e.size(),
		"graph": graph_e.size(),
		"source": "MapValidator broken fixtures",
	}
	_event("map_reject", {"ok": errors.is_empty()})
	return errors


static func author_commands() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var trace: Dictionary = SimConstants.load_json(AUTHOR_TRACE)
	if str(trace.get("title", "")) != "Vault Fighters":
		errors.append("AUTHOR trace title must be Vault Fighters")
	if bool(trace.get("used_step_fixed", true)):
		errors.append("AUTHOR trace must set used_step_fixed false")
	if bool(trace.get("y8_parity_claimed", true)):
		errors.append("AUTHOR trace claimed Y8 parity")
	var shipped: Dictionary = _MapCatalog.document("fx_map_author")
	var want: String = _MapCodec.stable_hash(shipped)
	var author = _MapAuthor.new()
	var cmds: Array = trace.get("commands", []) as Array
	var i: int = 0
	while i < cmds.size():
		var cmd: Dictionary = cmds[i] as Dictionary
		cmd["schema"] = _MapAuthor.COMMAND_ID
		var res: Dictionary = author.apply(cmd)
		if not bool(res.get("ok", false)):
			errors.append("AUTHOR %s failed: %s" % [str(cmd.get("op", "")), str(res.get("errors", []))])
		var again: Dictionary = author.apply(cmd)
		if str(again.get("command_id", "")) != str(cmd.get("command_id", "")):
			errors.append("AUTHOR retry lost command_id")
		if str(again.get("hash", "")) != str(res.get("hash", "")):
			errors.append("AUTHOR retry not idempotent")
		i += 1
	var built: Dictionary = author.document("fx_map_author")
	var got: String = _MapCodec.stable_hash(built)
	if got != want:
		errors.append("AUTHOR rebuilt hash != shipped Draft Yard")
	var val: Dictionary = author.apply({
		"schema": _MapAuthor.COMMAND_ID,
		"command_id": "cmd.vf5-wp1.map.validate.1",
		"op": "map.validate",
		"payload": {"id": "fx_map_author"},
	})
	if not bool(val.get("ok", false)):
		errors.append("AUTHOR validate failed")
	var ser: Dictionary = author.apply({
		"schema": _MapAuthor.COMMAND_ID,
		"command_id": "cmd.vf5-wp1.map.serialize.1",
		"op": "map.serialize",
		"payload": {"id": "fx_map_author"},
	})
	if not bool(ser.get("ok", false)):
		errors.append("AUTHOR serialize failed")
	var persisted: Dictionary = author.apply({
		"schema": _MapAuthor.COMMAND_ID,
		"command_id": "cmd.vf5-wp1.map.persist.1",
		"op": "map.persist",
		"payload": {"id": "fx_map_author", "filename": "draft_yard.json"},
	})
	if not bool(persisted.get("ok", false)):
		errors.append("AUTHOR persist failed")
	var loaded: Dictionary = _MapCodec.normalize(SimConstants.load_json(str(persisted.get("store", ""))))
	if _MapCodec.stable_hash(loaded) != want:
		errors.append("AUTHOR persisted hash mismatch")
	var author2 = _MapAuthor.new()
	var j: int = 0
	while j < cmds.size():
		var cmd2: Dictionary = (cmds[j] as Dictionary).duplicate(true)
		cmd2["schema"] = _MapAuthor.COMMAND_ID
		author2.apply(cmd2)
		j += 1
	if _MapCodec.stable_hash(author2.document("fx_map_author")) != got:
		errors.append("AUTHOR second apply hash mismatch")
	outcome_author = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"hash": got,
		"shipped": want,
		"commands": cmds.size(),
		"store": str(persisted.get("store", "")),
		"source": "MapAuthor semantic commands vs shipped Draft Yard",
	}
	_event("map_author", {"ok": errors.is_empty(), "hash": got})
	return errors


static func live_layers(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "rooftops", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	if session == null or session.arena == null:
		errors.append("LIVE missing rooftops session")
		outcome_live = {"verdict": "fail", "source": "start_fight rooftops"}
		return errors
	if session.arena.ladder_cells.is_empty():
		errors.append("LIVE rooftops ladders missing after layered paint")
	if not session.arena.platform_is_one_way():
		errors.append("LIVE platforms must stay one-way")
	var p1: Fighter = session.player1()
	if p1 == null:
		errors.append("LIVE missing P1")
		outcome_live = {"verdict": "fail", "source": "player1"}
		return errors
	_hold(session, 8, PackedStringArray())
	var floor0: bool = p1.is_on_floor()
	var x0: float = p1.global_position.x
	_hold(session, 20, PackedStringArray(["right"]))
	var moved: bool = p1.global_position.x > x0 + 2.0
	var floor1: bool = p1.is_on_floor()
	if p1.dead:
		errors.append("LIVE rooftops walk must not kill")
	if not floor0 or not floor1:
		errors.append("LIVE rooftops must stand on_floor")
	if not moved:
		errors.append("LIVE rooftops walk must move")
	app.start_fight("vs2", "fx_map_author", 0)
	await SimReplay.sync_physics(app)
	session = app.session
	p1 = session.player1() if session != null else null
	_hold(session, 8, PackedStringArray())
	var author_floor: bool = p1 != null and p1.is_on_floor() and not p1.dead
	if not author_floor:
		errors.append("LIVE Draft Yard must stand on_floor")
	if Maps.display_name("fx_map_author") != "Draft Yard":
		errors.append("LIVE authored map display name drifted")
	outcome_live = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"on_floor": floor1,
		"moved": moved,
		"author_on_floor": author_floor,
		"source": "apply_frames walk on layered rooftops + Draft Yard",
	}
	_remember_session(session)
	_event("map_live", {"ok": errors.is_empty(), "on_floor": floor1})
	return errors


static func replay_twice() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var ids: PackedStringArray = _MapCatalog.ids()
	var pairs: Array = []
	var i: int = 0
	while i < ids.size():
		var mid: String = String(ids[i])
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
		"source": "catalog reload hash twice",
	}
	_event("map_replay", {"ok": errors.is_empty()})
	return errors


static func _require_outcomes() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var rows: Array = [
		outcome_schema, outcome_roundtrip, outcome_graph, outcome_reject,
		outcome_author, outcome_width, outcome_spawn, outcome_pit,
		outcome_camera, outcome_overlap, outcome_live
	]
	var i: int = 0
	while i < rows.size():
		if str((rows[i] as Dictionary).get("verdict", "unproven")) == "unproven":
			errors.append("structured outcome left unproven")
		i += 1
	if str(outcome_replay.get("verdict", "unproven")) == "unproven":
		errors.append("REPLAY outcome left unproven")
	return errors


static func _hold(session: GameSession, ticks: int, held: PackedStringArray) -> void:
	if session == null:
		return
	var n: int = 0
	while n < ticks:
		var frames: Array = []
		var i: int = 0
		while i < session.fighters.size():
			var d: Dictionary = InputActions.empty_frame(session.clock.tick, i)
			if i == 0:
				d["held"] = held
			frames.append(InputFrame.from_dict(d))
			i += 1
		used_apply_frames_attempted += 1
		if session.apply_frames(frames):
			used_apply_frames += 1
			used_apply_frames_succeeded += 1
		n += 1


static func _capture_start(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "rooftops", 0)
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

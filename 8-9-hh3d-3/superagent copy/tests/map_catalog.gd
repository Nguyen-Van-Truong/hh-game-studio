extends SceneTree

const MAP_SCRIPT = preload("res://game/world/map_catalog.gd")
const ARENA_SCRIPT = preload("res://game/world/arena_state.gd")
const GRAPH_SCRIPT = preload("res://game/ai/navigation_graph.gd")
const MATCH_SCRIPT = preload("res://game/core/match_session.gd")
var assertions: int = 0

func _init() -> void:
	var entries: Array[Dictionary] = MAP_SCRIPT.entries()
	_expect(entries.size() == 6 and entries.is_read_only(), "catalog has six immutable entries")
	_expect(StringName(entries[0][&"id"]) == MAP_SCRIPT.default_id(), "relay yard is the default entry")
	var seen_ids: Dictionary = {}
	var seen_topologies: Dictionary = {}
	for entry: Dictionary in entries:
		var map_id: StringName = StringName(entry[&"id"])
		var path: String = String(entry[&"path"])
		_expect(not seen_ids.has(map_id) and not MAP_SCRIPT.resolve(map_id).is_empty(), "map id resolves uniquely: %s" % String(map_id))
		seen_ids[map_id] = true
		var arena: ArenaState = ARENA_SCRIPT.new(17, path)
		_expect(arena.valid, "map loads valid arena data: %s" % String(map_id))
		_expect(arena.spawn_for_player(1) != arena.spawn_for_player(2), "map has two distinct spawns: %s" % String(map_id))
		var graph: NavigationGraph = GRAPH_SCRIPT.new(arena)
		_expect(graph.valid and not graph.nodes.is_empty(), "map graph builds: %s" % String(map_id))
		var topology: String = arena.canonical_topology()
		_expect(not seen_topologies.has(topology), "map topology is distinct: %s" % String(map_id))
		seen_topologies[topology] = true
	_expect(MAP_SCRIPT.resolve_path("res://data/cobalt_forge.json")[&"id"] == &"cobalt_forge", "catalog resolves safe data path")
	_expect(MAP_SCRIPT.resolve_path("res://data/../data/cobalt_forge.json").is_empty(), "catalog rejects traversal path")
	_expect(MAP_SCRIPT.resolve_path("user://outside.json").is_empty(), "catalog rejects external path")
	var selected_a: Dictionary = MAP_SCRIPT.select(31, 4)
	var selected_b: Dictionary = MAP_SCRIPT.select(31, 4)
	_expect(selected_a[&"id"] == selected_b[&"id"] and selected_a[&"path"] == selected_b[&"path"], "seed/index selection is deterministic")
	var selected_match: MatchSession = MATCH_SCRIPT.new(23, &"two_player", &"vs", &"infinite", &"cobalt_forge")
	var selected_snapshot: Dictionary = selected_match.snapshot()
	_expect(selected_match.phase == &"playing" and selected_snapshot.get(&"map_id") == &"cobalt_forge", "match session exposes selected map")
	_expect(selected_snapshot.get(&"map_path") == "res://data/cobalt_forge.json" and selected_match.canonical_snapshot().contains("map=cobalt_forge,res://data/cobalt_forge.json"), "selected map enters snapshot and hash")
	for entry: Dictionary in entries:
		for mode: StringName in [&"vs", &"stage", &"survival"]:
			var mode_session: MatchSession = MATCH_SCRIPT.new(29, &"two_player", mode, &"infinite", StringName(entry[&"id"]))
			_expect(mode_session.phase == &"playing" and mode_session.map_id == StringName(entry[&"id"]), "mode starts on catalog map: %s/%s" % [String(mode), String(entry[&"id"])])
			mode_session.free()
	var invalid_match: MatchSession = MATCH_SCRIPT.new(23, &"two_player", &"vs", &"infinite", &"missing_map")
	_expect(invalid_match.phase == &"invalid" and invalid_match.error == &"invalid_map", "unknown map fails closed")
	selected_match.free()
	invalid_match.free()
	print("SA-09 map catalog PASS: %d assertions" % assertions)
	quit()

func _expect(condition: bool, message: String) -> void:
	assertions += 1
	if not condition:
		push_error("FAIL: " + message)
		quit(1)

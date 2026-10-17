extends SceneTree

const ARENA_SCRIPT = preload("res://game/world/arena_state.gd")
const GRAPH_SCRIPT = preload("res://game/ai/navigation_graph.gd")
var assertions: int = 0

func _init() -> void:
	var arena: ArenaState = ARENA_SCRIPT.new(17, "res://data/relay_yard.json")
	var graph: NavigationGraph = GRAPH_SCRIPT.new(arena)
	var second_graph: NavigationGraph = GRAPH_SCRIPT.new(ARENA_SCRIPT.new(17, "res://data/relay_yard.json"))
	_expect(arena.valid and graph.valid, "relay-yard topology builds")
	_expect(graph.nodes.size() == 9, "five platforms and four ladder endpoints become nodes")
	_expect(graph.canonical_snapshot() == second_graph.canonical_snapshot(), "same topology has stable canonical graph")
	_expect(graph.reachable(&"platform:west_catwalk", &"platform:east_catwalk"), "ladder-connected upper lanes are reachable")
	_expect(graph.neighbors(&"ladder:west_access:top").has(&"ladder:west_access:bottom"), "west ladder has a bidirectional vertical edge")
	_expect(not graph.neighbors(&"platform:service_bridge").has(&"platform:yard_floor"), "pit blocks unsafe service bridge shortcut")
	var invalid: NavigationGraph = GRAPH_SCRIPT.new()
	_expect(not invalid.build(null) and invalid.error == &"invalid_arena", "null arena fails closed")
	var synthetic_snapshot: Dictionary = {
		&"platforms": [
			{&"id": &"right", &"left": 200.0, &"right": 280.0, &"y": 100.0},
			{&"id": &"left", &"left": 0.0, &"right": 80.0, &"y": 100.0},
		],
		&"ladders": [],
		&"pits": [{&"id": &"gap", &"left": 90.0, &"right": 190.0}],
	}
	var synthetic: NavigationGraph = GRAPH_SCRIPT.new()
	_expect(synthetic.build_from_snapshot(synthetic_snapshot), "synthetic valid topology builds")
	_expect(not synthetic.neighbors(&"platform:left").has(&"platform:right"), "pit spanning the platform gap blocks traversal")
	var permuted_snapshot: Dictionary = synthetic_snapshot.duplicate(true)
	permuted_snapshot[&"platforms"] = [synthetic_snapshot[&"platforms"][0], synthetic_snapshot[&"platforms"][1]]
	var permuted: NavigationGraph = GRAPH_SCRIPT.new()
	_expect(permuted.build_from_snapshot(permuted_snapshot) and synthetic.canonical_snapshot() == permuted.canonical_snapshot(), "source row order does not change canonical graph")
	var graph_snapshot: Dictionary = graph.snapshot()
	var graph_nodes: Array = graph_snapshot.get(&"nodes", [])
	_expect(graph_nodes.is_read_only() and not graph_nodes.is_empty() and Dictionary(graph_nodes[0]).is_read_only(), "graph snapshot rows are immutable")
	var malformed: NavigationGraph = GRAPH_SCRIPT.new()
	var malformed_snapshot: Dictionary = synthetic_snapshot.duplicate(true)
	malformed_snapshot[&"pits"] = [{&"id": &"broken", &"left": 4.0, &"right": 4.0}]
	_expect(not malformed.build_from_snapshot(malformed_snapshot) and malformed.error == &"invalid_pit", "malformed pit geometry fails closed")
	_expect(malformed.nodes.is_empty() and malformed.edges.is_empty(), "failed graph build does not retain partial nodes")
	var malformed_number: NavigationGraph = GRAPH_SCRIPT.new()
	var malformed_number_snapshot: Dictionary = synthetic_snapshot.duplicate(true)
	malformed_number_snapshot[&"platforms"] = [{&"id": &"bad", &"left": "oops", &"right": 20.0, &"y": 100.0}]
	_expect(not malformed_number.build_from_snapshot(malformed_number_snapshot) and malformed_number.error == &"invalid_platform" and malformed_number.nodes.is_empty(), "non-numeric geometry is rejected")
	var string_key_snapshot: Dictionary = {
		"platforms": [{"id": "json_left", "left": 0.0, "right": 80.0, "y": 100.0}],
		"ladders": [],
		"pits": [],
	}
	var string_key_graph: NavigationGraph = GRAPH_SCRIPT.new()
	_expect(string_key_graph.build_from_snapshot(string_key_snapshot) and string_key_graph.nodes.size() == 1, "decoded JSON string keys are accepted")
	print("SA-09 navigation graph PASS: %d assertions" % assertions)
	quit()

func _expect(condition: bool, message: String) -> void:
	assertions += 1
	if not condition:
		push_error("FAIL: " + message)
		quit(1)

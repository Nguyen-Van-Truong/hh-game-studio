class_name NavigationGraph
extends RefCounted
## Deterministic topology graph derived from an ArenaState snapshot.
## It is a technical seam for bot routing; it is not a reference-map claim.

const SCHEMA: StringName = &"sa09.navigation-graph.v1"
const MAX_PLATFORM_LINK_GAP: float = 420.0
const Y_EPSILON: float = 1.0

var valid: bool = false
var error: StringName = &"not_built"
var nodes: Array[Dictionary] = []
var edges: Dictionary = {}

func _init(arena: ArenaState = null) -> void:
	if arena != null:
		build(arena)

func build(arena: ArenaState) -> bool:
	if arena == null or not arena.valid:
		valid = false
		error = &"invalid_arena"
		nodes.clear()
		edges.clear()
		return false
	return build_from_snapshot(arena.snapshot())

func build_from_snapshot(snapshot: Dictionary) -> bool:
	valid = false
	error = &"not_built"
	nodes.clear()
	edges.clear()
	if snapshot.is_empty():
		return _build_failed(&"invalid_arena")
	var platforms: Variant = _row_value(snapshot, &"platforms", [])
	var ladders: Variant = _row_value(snapshot, &"ladders", [])
	var pits: Variant = _row_value(snapshot, &"pits", [])
	if typeof(platforms) != TYPE_ARRAY or typeof(ladders) != TYPE_ARRAY or typeof(pits) != TYPE_ARRAY:
		return _build_failed(&"invalid_topology_rows")
	var platform_rows: Array = Array(platforms).duplicate(true)
	var ladder_rows: Array = Array(ladders).duplicate(true)
	platform_rows.sort_custom(_topology_row_less)
	ladder_rows.sort_custom(_topology_row_less)
	for row_value: Variant in platform_rows:
		if typeof(row_value) != TYPE_DICTIONARY or not _append_platform(Dictionary(row_value)):
			return _build_failed(&"invalid_platform")
	for row_value: Variant in ladder_rows:
		if typeof(row_value) != TYPE_DICTIONARY or not _append_ladder(Dictionary(row_value)):
			return _build_failed(&"invalid_ladder")
	if not _valid_pits(Array(pits)):
		return _build_failed(&"invalid_pit")
	nodes.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return String(a.get(&"id", &"")) < String(b.get(&"id", &"")))
	for node: Dictionary in nodes:
		edges[StringName(node[&"id"])] = []
	_connect_ladder_endpoints()
	_connect_platforms(pits)
	valid = true
	error = &""
	return true

func _build_failed(code: StringName) -> bool:
	valid = false
	error = code
	nodes.clear()
	edges.clear()
	return false

func snapshot() -> Dictionary:
	var node_rows: Array[Dictionary] = []
	for node: Dictionary in nodes:
		var copy: Dictionary = node.duplicate(true)
		copy.make_read_only()
		node_rows.append(copy)
	node_rows.make_read_only()
	var edge_rows: Dictionary = {}
	for key: StringName in edges.keys():
		var linked: Array[StringName] = []
		for value: StringName in Array(edges[key]):
			linked.append(value)
		linked.make_read_only()
		edge_rows[key] = linked
	edge_rows.make_read_only()
	var result: Dictionary = {
		&"schema": SCHEMA,
		&"valid": valid,
		&"error": error,
		&"nodes": node_rows,
		&"edges": edge_rows,
	}
	result.make_read_only()
	return result

func canonical_snapshot() -> String:
	var parts: Array[String] = ["schema=%s" % String(SCHEMA), "valid=%d" % int(valid), "error=%s" % String(error)]
	for node: Dictionary in nodes:
		parts.append("node:%s,%s,%.3f,%.3f" % [String(node[&"id"]), String(node[&"kind"]), float(node[&"x"]), float(node[&"y"])])
	for node: Dictionary in nodes:
		var node_id: StringName = StringName(node[&"id"])
		var linked: Array[StringName] = []
		for value: StringName in Array(edges.get(node_id, [])):
			linked.append(value)
		parts.append("edge:%s=%s" % [String(node_id), ",".join(linked.map(func(value: StringName) -> String: return String(value)))])
	return ";".join(parts)

func neighbors(node_id: StringName) -> Array[StringName]:
	var result: Array[StringName] = []
	for value: StringName in Array(edges.get(node_id, [])):
		result.append(value)
	return result

func reachable(start_id: StringName, target_id: StringName) -> bool:
	if not valid or not edges.has(start_id) or not edges.has(target_id):
		return false
	if start_id == target_id:
		return true
	var pending: Array[StringName] = [start_id]
	var visited: Dictionary = {start_id: true}
	while not pending.is_empty():
		var current: StringName = pending.pop_front()
		for next_id: StringName in neighbors(current):
			if next_id == target_id:
				return true
			if not visited.has(next_id):
				visited[next_id] = true
				pending.append(next_id)
	return false

func _append_platform(row: Dictionary) -> bool:
	if not _row_has_all(row, [&"id", &"left", &"right", &"y"]):
		return false
	var row_id: Variant = _row_value(row, &"id")
	if not _valid_identifier(row_id):
		return false
	var left_value: Variant = _row_value(row, &"left")
	var right_value: Variant = _row_value(row, &"right")
	var y_value: Variant = _row_value(row, &"y")
	if not _valid_number(left_value) or not _valid_number(right_value) or not _valid_number(y_value):
		return false
	var left: float = float(left_value)
	var right: float = float(right_value)
	var y: float = float(y_value)
	if String(row_id).is_empty() or right <= left:
		return false
	var id: StringName = StringName("platform:%s" % String(row_id))
	if edges.has(id) or not _node_by_id(id).is_empty():
		return false
	nodes.append({&"id": id, &"kind": &"platform", &"x": (left + right) * 0.5, &"y": y, &"left": left, &"right": right})
	return true

func _append_ladder(row: Dictionary) -> bool:
	if not _row_has_all(row, [&"id", &"x", &"top", &"bottom"]):
		return false
	var row_id: Variant = _row_value(row, &"id")
	if not _valid_identifier(row_id):
		return false
	var x_value: Variant = _row_value(row, &"x")
	var top_value: Variant = _row_value(row, &"top")
	var bottom_value: Variant = _row_value(row, &"bottom")
	if not _valid_number(x_value) or not _valid_number(top_value) or not _valid_number(bottom_value):
		return false
	var x: float = float(x_value)
	var top: float = float(top_value)
	var bottom: float = float(bottom_value)
	if String(row_id).is_empty() or bottom <= top:
		return false
	var base: String = "ladder:%s" % String(row_id)
	var top_id: StringName = StringName(base + ":top")
	var bottom_id: StringName = StringName(base + ":bottom")
	if not _node_by_id(top_id).is_empty() or not _node_by_id(bottom_id).is_empty():
		return false
	nodes.append({&"id": top_id, &"kind": &"ladder_top", &"x": x, &"y": top, &"ladder": StringName(base)})
	nodes.append({&"id": bottom_id, &"kind": &"ladder_bottom", &"x": x, &"y": bottom, &"ladder": StringName(base)})
	return true

func _connect_ladder_endpoints() -> void:
	for node: Dictionary in nodes:
		if StringName(node[&"kind"]) != &"ladder_top" and StringName(node[&"kind"]) != &"ladder_bottom":
			continue
		var base: StringName = StringName(node[&"ladder"])
		var suffix: String = ":bottom" if StringName(node[&"kind"]) == &"ladder_top" else ":top"
		_add_edge(StringName(node[&"id"]), StringName(String(base) + suffix))

func _connect_platforms(pits: Array) -> void:
	var platform_nodes: Array[Dictionary] = nodes.filter(func(row: Dictionary) -> bool: return StringName(row[&"kind"]) == &"platform")
	for node: Dictionary in platform_nodes:
		var node_id: StringName = StringName(node[&"id"])
		for other: Dictionary in platform_nodes:
			var other_id: StringName = StringName(other[&"id"])
			if node_id == other_id:
				continue
			var vertical: float = absf(float(node[&"y"]) - float(other[&"y"]))
			var horizontal: float = absf(float(node[&"x"]) - float(other[&"x"]))
			if vertical <= Y_EPSILON and horizontal <= MAX_PLATFORM_LINK_GAP and not _crosses_pit(node, other, pits):
				_add_edge(node_id, other_id)
		for ladder: Dictionary in nodes:
			if StringName(ladder[&"kind"]) != &"ladder_top" and StringName(ladder[&"kind"]) != &"ladder_bottom":
				continue
			if absf(float(ladder[&"y"]) - float(node[&"y"])) <= Y_EPSILON and float(ladder[&"x"]) >= float(node[&"left"]) and float(ladder[&"x"]) <= float(node[&"right"]):
				var ladder_id: StringName = StringName(ladder[&"id"])
				_add_edge(node_id, ladder_id)
				_add_edge(ladder_id, node_id)

func _crosses_pit(left: Dictionary, right: Dictionary, pits: Array) -> bool:
	var min_x: float = minf(float(left.get(&"left", left[&"x"])), float(right.get(&"left", right[&"x"])))
	var max_x: float = maxf(float(left.get(&"right", left[&"x"])), float(right.get(&"right", right[&"x"])))
	for pit_value: Variant in pits:
		if typeof(pit_value) != TYPE_DICTIONARY:
			return true
		var pit: Dictionary = pit_value
		if not _row_has_all(pit, [&"left", &"right"]):
			return true
		var pit_left: Variant = _row_value(pit, &"left")
		var pit_right: Variant = _row_value(pit, &"right")
		if _valid_number(pit_left) and _valid_number(pit_right) and min_x < float(pit_right) and max_x > float(pit_left):
			return true
	return false

func _valid_pits(pits: Array) -> bool:
	for pit_value: Variant in pits:
		if typeof(pit_value) != TYPE_DICTIONARY:
			return false
		var pit: Dictionary = pit_value
		if not _row_has_all(pit, [&"left", &"right"]):
			return false
		var left_value: Variant = _row_value(pit, &"left")
		var right_value: Variant = _row_value(pit, &"right")
		if not _valid_number(left_value) or not _valid_number(right_value):
			return false
		var left: float = float(left_value)
		var right: float = float(right_value)
		if right <= left:
			return false
	return true

func _valid_number(value: Variant) -> bool:
	var value_type: int = typeof(value)
	return (value_type == TYPE_INT or value_type == TYPE_FLOAT) and is_finite(float(value))

func _row_has_all(row: Dictionary, keys: Array[StringName]) -> bool:
	for key: StringName in keys:
		if not row.has(key) and not row.has(String(key)):
			return false
	return true

func _row_value(row: Dictionary, key: StringName, fallback: Variant = null) -> Variant:
	if row.has(key):
		return row[key]
	var text_key: String = String(key)
	if row.has(text_key):
		return row[text_key]
	return fallback

func _valid_identifier(value: Variant) -> bool:
	return (typeof(value) == TYPE_STRING or typeof(value) == TYPE_STRING_NAME) and not String(value).is_empty()

func _topology_row_less(a: Variant, b: Variant) -> bool:
	if typeof(a) != TYPE_DICTIONARY or typeof(b) != TYPE_DICTIONARY:
		return typeof(a) < typeof(b)
	return String(_row_value(Dictionary(a), &"id", "")) < String(_row_value(Dictionary(b), &"id", ""))

func _add_edge(from_id: StringName, to_id: StringName) -> void:
	if not edges.has(from_id) or not edges.has(to_id):
		return
	var linked: Array[StringName] = []
	for value: StringName in Array(edges[from_id]):
		linked.append(value)
	if to_id not in linked:
		linked.append(to_id)
		linked.sort_custom(func(a: StringName, b: StringName) -> bool: return String(a) < String(b))
	edges[from_id] = linked

func _node_by_id(node_id: StringName) -> Dictionary:
	for node: Dictionary in nodes:
		if StringName(node[&"id"]) == node_id:
			return node
	return {}

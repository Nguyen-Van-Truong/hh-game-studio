class_name BotNav
extends RefCounted

## Bounded platform/ladder A* (VF6-WP5).
## ledger:RL-BOT-NAV / RL-BOT-BOUND. Not observed Y8.


static func path_to(
	doc: Dictionary, from_pos: Vector2, to_pos: Vector2, max_expansions: int
) -> Dictionary:
	var start: Vector2i = MapGraph.stand_cell(doc, from_pos)
	var goal: Vector2i = MapGraph.stand_cell(doc, to_pos)
	return path_cells(doc, start, goal, max_expansions)


static func path_cells(
	doc: Dictionary, start: Vector2i, goal: Vector2i, max_expansions: int
) -> Dictionary:
	var out: Dictionary = {
		"ok": false,
		"expansions": 0,
		"cells": [],
		"partial": false,
	}
	var cap: int = clampi(max_expansions, 4, 64)
	if doc.is_empty():
		return out
	var start_key: String = _key(start.x, start.y)
	var goal_key: String = _key(goal.x, goal.y)
	var open: Array = [start]
	var g_score: Dictionary = {start_key: 0}
	var came: Dictionary = {}
	var seen: Dictionary = {start_key: true}
	var best: Vector2i = start
	var best_h: int = _heur(start, goal)
	var expansions: int = 0
	while not open.is_empty() and expansions < cap:
		var idx: int = _best_open(open, g_score, goal)
		var cur: Vector2i = open[idx] as Vector2i
		open.remove_at(idx)
		expansions += 1
		if cur == goal:
			out["ok"] = true
			out["expansions"] = expansions
			out["cells"] = _rebuild(came, cur)
			return out
		var h: int = _heur(cur, goal)
		if h < best_h:
			best_h = h
			best = cur
		var neighbors: Array = MapGraph.neighbors_of(doc, cur.x, cur.y)
		var n: int = 0
		while n < neighbors.size():
			var raw: Array = neighbors[n] as Array
			n += 1
			if raw.size() < 2:
				continue
			var nxt: Vector2i = Vector2i(int(raw[0]), int(raw[1]))
			var nk: String = _key(nxt.x, nxt.y)
			var step: int = 1
			if nxt.y != cur.y:
				step = 2
			if MapGraph.is_hazard_cell(doc, nxt.x, nxt.y):
				step += 40
			if MapGraph.is_pit_column(doc, nxt.x) and not MapGraph.is_walkable_cell(doc, nxt.x, nxt.y):
				continue
			if MapGraph.step_is_unsafe(doc, cur.x, cur.y, signi(nxt.x - cur.x)) and nxt.y == cur.y:
				step += 24
			var tentative: int = int(g_score.get(_key(cur.x, cur.y), 99999)) + step
			if tentative < int(g_score.get(nk, 99999)):
				came[nk] = cur
				g_score[nk] = tentative
				if not seen.has(nk):
					seen[nk] = true
					open.append(nxt)
	out["expansions"] = expansions
	out["partial"] = true
	out["cells"] = _rebuild(came, best)
	return out


static func unsafe_world_step(doc: Dictionary, pos: Vector2, dir: float) -> bool:
	if absf(dir) < 0.2 or doc.is_empty():
		return false
	var cell: Vector2i = MapGraph.stand_cell(doc, pos)
	return MapGraph.step_is_unsafe(doc, cell.x, cell.y, 1 if dir > 0.0 else -1)


static func _best_open(open: Array, g_score: Dictionary, goal: Vector2i) -> int:
	var best_i: int = 0
	var best_f: int = 999999
	var i: int = 0
	while i < open.size():
		var cell: Vector2i = open[i] as Vector2i
		var f: int = int(g_score.get(_key(cell.x, cell.y), 99999)) + _heur(cell, goal)
		if f < best_f:
			best_f = f
			best_i = i
		i += 1
	return best_i


static func _rebuild(came: Dictionary, last: Vector2i) -> Array:
	var cells: Array = [last]
	var cur: Vector2i = last
	var guard: int = 0
	while guard < 80:
		var ck: String = _key(cur.x, cur.y)
		if not came.has(ck):
			break
		cur = came[ck] as Vector2i
		cells.push_front(cur)
		guard += 1
	return cells


static func _heur(a: Vector2i, b: Vector2i) -> int:
	return absi(a.x - b.x) + absi(a.y - b.y)


static func _key(x: int, y: int) -> String:
	return "%d,%d" % [x, y]

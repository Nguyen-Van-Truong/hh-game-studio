class_name BotNav
extends RefCounted

## Bounded platform/ladder A* (VF6-WP5).
## ledger:RL-BOT-NAV / RL-BOT-BOUND. Not observed Y8.


static func path_to(
	doc: Dictionary, from_pos: Vector2, to_pos: Vector2, max_expansions: int
) -> Dictionary:
	var start: Vector2i = landing_cell(doc, from_pos)
	var goal: Vector2i = landing_cell(doc, to_pos)
	return path_cells(doc, start, goal, max_expansions)


static func landing_cell(doc: Dictionary, pos: Vector2) -> Vector2i:
	## Airborne spawn/fall must path from the floor they will land on,
	## not a non-walkable air cell that A* treats as a high deck.
	var raw: Vector2i = MapGraph.world_to_cell(pos)
	if MapGraph.is_walkable_cell(doc, raw.x, raw.y):
		return raw
	var height: int = int(doc.get("height", 0))
	var y: int = raw.y
	while y < height:
		if MapGraph.is_walkable_cell(doc, raw.x, y):
			return Vector2i(raw.x, y)
		y += 1
	return MapGraph.stand_cell(doc, pos)


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
			var dx: int = absi(nxt.x - cur.x)
			var dy: int = absi(nxt.y - cur.y)
			var step: int = 1
			if dy > 0:
				step = 2
			if dx > 1 or dy > 1:
				step = 4 + dx + dy
			if MapGraph.is_hazard_cell(doc, nxt.x, nxt.y):
				step += 40
			if MapGraph.is_pit_column(doc, nxt.x) and not MapGraph.is_walkable_cell(doc, nxt.x, nxt.y):
				continue
			## Same-Y pit/hazard lips are not a walk edge. Force a jump/around.
			var step_dir: int = signi(nxt.x - cur.x)
			if MapGraph.step_is_unsafe(doc, cur.x, cur.y, step_dir) and nxt.y == cur.y:
				continue
			## Along-platform jump shortcuts flood the 56-expansion budget.
			if nxt.y == cur.y and absi(nxt.x - cur.x) > 1 and _same_y_walk_clear(doc, cur.x, nxt.x, cur.y):
				continue
			## jump_dx/dy on the graph is wider than the body. Keep hops the
			## jump_vel/gravity envelope can actually board (no teleport).
			if not _body_can_step(doc, cur, nxt):
				continue
			if (dx > 1 or dy > 1) and not _crosses_gap(doc, cur, nxt):
				continue
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


static func _body_can_step(doc: Dictionary, cur: Vector2i, nxt: Vector2i) -> bool:
	var dx: int = absi(nxt.x - cur.x)
	var dy: int = nxt.y - cur.y
	if dx <= 1 and absi(dy) <= 1:
		return true
	if dx == 0 and _ladder_link(doc, cur, nxt):
		return true
	if dy < -3:
		return false
	if dx > 6:
		return false
	if dy > 5:
		return false
	return true


static func _ladder_link(doc: Dictionary, cur: Vector2i, nxt: Vector2i) -> bool:
	if cur.x != nxt.x:
		return false
	var y0: int = mini(cur.y, nxt.y)
	var y1: int = maxi(cur.y, nxt.y)
	var y: int = y0
	while y <= y1:
		if not (
			MapGraph.is_walkable_cell(doc, cur.x, y)
			and (
				_has_ladder(doc, cur.x, y)
				or _has_ladder(doc, cur.x, y + 1)
				or _has_ladder(doc, cur.x, y - 1)
			)
		):
			return false
		y += 1
	return true


static func _has_ladder(doc: Dictionary, x: int, y: int) -> bool:
	return MapCodec.has_xy(doc, "ladder", x, y)


static func _crosses_gap(doc: Dictionary, cur: Vector2i, nxt: Vector2i) -> bool:
	var x0: int = mini(cur.x, nxt.x)
	var x1: int = maxi(cur.x, nxt.x)
	var y0: int = mini(cur.y, nxt.y)
	var y1: int = maxi(cur.y, nxt.y)
	if cur.x == nxt.x:
		var y: int = y0 + 1
		while y < y1:
			if not MapGraph.is_walkable_cell(doc, cur.x, y):
				return true
			y += 1
		return false
	var x: int = x0 + 1
	while x < x1:
		var y: int = y0
		var any_walk: bool = false
		while y <= y1:
			if MapGraph.is_walkable_cell(doc, x, y):
				any_walk = true
				break
			y += 1
		if not any_walk:
			return true
		x += 1
	return false


static func _same_y_walk_clear(doc: Dictionary, x0: int, x1: int, y: int) -> bool:
	var step: int = signi(x1 - x0)
	if step == 0:
		return true
	var x: int = x0 + step
	while x != x1:
		if not MapGraph.is_walkable_cell(doc, x, y):
			return false
		x += step
	return true


static func _key(x: int, y: int) -> String:
	return "%d,%d" % [x, y]

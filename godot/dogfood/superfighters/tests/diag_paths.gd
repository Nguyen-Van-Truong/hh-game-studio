extends SceneTree

## Diagnostic only — A* dump, no fight.


func _initialize() -> void:
	var ids: PackedStringArray = PackedStringArray([
		"rooftops", "storage", "police", "hazardous", "lantern", "gauge"
	])
	var i: int = 0
	while i < ids.size():
		_dump(String(ids[i]))
		i += 1
	quit(0)


func _dump(map_id: String) -> void:
	var doc: Dictionary = MapCatalog.document(map_id)
	var pads: Array = MapGraph.spawn_walkable(doc)
	print("HH_PATH map=%s pads=%s walk=%d" % [map_id, str(pads), MapGraph.walkable_cells(doc).size()])
	if pads.size() < 2:
		return
	var a: Vector2i = Vector2i(int((pads[0] as Array)[0]), int((pads[0] as Array)[1]))
	var b: Vector2i = Vector2i(int((pads[1] as Array)[0]), int((pads[1] as Array)[1]))
	_one(map_id, doc, a, b, "p0_to_p1")
	_one(map_id, doc, b, a, "p1_to_p0")


func _one(map_id: String, doc: Dictionary, start: Vector2i, goal: Vector2i, label: String) -> void:
	var planned: Dictionary = BotNav.path_cells(doc, start, goal, 56)
	var cells: Array = planned.get("cells", []) as Array
	var bits: PackedStringArray = PackedStringArray()
	var i: int = 0
	while i < cells.size():
		var c: Vector2i = cells[i] as Vector2i
		bits.append("%d,%d" % [c.x, c.y])
		i += 1
	print(
		"HH_PATH %s %s ok=%s partial=%s exp=%s n=%d start=%d,%d goal=%d,%d cells=%s"
		% [
			map_id,
			label,
			str(planned.get("ok", false)),
			str(planned.get("partial", false)),
			str(planned.get("expansions", 0)),
			cells.size(),
			start.x,
			start.y,
			goal.x,
			goal.y,
			",".join(bits),
		]
	)

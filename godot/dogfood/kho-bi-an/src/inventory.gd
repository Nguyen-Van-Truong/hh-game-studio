class_name Inventory
extends RefCounted

var _items: Array[String] = []


func add(item_id: String) -> void:
	if item_id.is_empty():
		return
	if has_item(item_id):
		return
	_items.append(item_id)


func has_item(item_id: String) -> bool:
	return _items.has(item_id)


func remove(item_id: String) -> void:
	var idx: int = _items.find(item_id)
	if idx >= 0:
		_items.remove_at(idx)


func clear() -> void:
	_items.clear()


func ids() -> Array[String]:
	return _items.duplicate()

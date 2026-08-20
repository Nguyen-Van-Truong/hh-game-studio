@tool
extends VBoxContainer

## Disposable R1-WP4 timeline dock. Not R4 production Activity Dock.

var _list: ItemList
var _pending: PackedStringArray = PackedStringArray()


func _ready() -> void:
	name = "HHStockPocDock"
	custom_minimum_size = Vector2(200, 160)
	var title: Label = Label.new()
	title.text = "R1-WP4 stock POC timeline"
	add_child(title)
	var note: Label = Label.new()
	note.text = "Disposable. Not hh_agent."
	add_child(note)
	_list = ItemList.new()
	_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(_list)
	for item: String in _pending:
		_list.add_item(item)
	_pending = PackedStringArray()


func record(text: String) -> void:
	if _list == null:
		_pending.append(text)
		return
	_list.add_item(text)
	while _list.item_count > 40:
		_list.remove_item(0)

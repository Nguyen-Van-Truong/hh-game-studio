@tool
extends PanelContainer

## Disposable R1-WP4 overlay hook. Not R4 production UX.

var _label: Label


func _ready() -> void:
	name = "HHStockPocOverlay"
	custom_minimum_size = Vector2(280, 28)
	_label = Label.new()
	_label.text = "R1-WP4 stock POC overlay (disposable)"
	add_child(_label)


func record(text: String) -> void:
	if _label == null:
		return
	_label.text = "R1-WP4: %s" % text

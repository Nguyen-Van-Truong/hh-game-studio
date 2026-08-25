class_name Hud
extends CanvasLayer

var _key_icon: ColorRect
var _hint: Label


func _ready() -> void:
	name = "Hud"
	var panel: ColorRect = ColorRect.new()
	panel.color = Color(0.07, 0.09, 0.16, 0.72)
	panel.position = Vector2(16, 16)
	panel.size = Vector2(420, 40)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(panel)
	_key_icon = ColorRect.new()
	_key_icon.name = "KeyIcon"
	_key_icon.position = Vector2(24, 24)
	_key_icon.size = Vector2(16, 16)
	_key_icon.color = Color(0.25, 0.25, 0.28)
	_key_icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_key_icon)
	_hint = Label.new()
	_hint.name = "Hint"
	_hint.position = Vector2(52, 22)
	_hint.size = Vector2(370, 24)
	_hint.text = "WASD / stick: move"
	_hint.add_theme_color_override("font_color", Color(0.93, 0.86, 0.70))
	add_child(_hint)


func set_has_key(has_key: bool) -> void:
	if has_key:
		_key_icon.color = Color(0.85, 0.70, 0.22)
	else:
		_key_icon.color = Color(0.25, 0.25, 0.28)


func set_hint(text: String) -> void:
	_hint.text = text

class_name WinScreen
extends Control

signal restart_pressed

var restart_btn: Button


func _ready() -> void:
	name = "Win"
	set_anchors_preset(Control.PRESET_FULL_RECT)
	visible = false
	var bg: ColorRect = ColorRect.new()
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.color = Color(0.07, 0.12, 0.14, 0.92)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)
	var label: Label = Label.new()
	label.text = "Relic reached"
	label.position = Vector2(80, 200)
	label.size = Vector2(500, 40)
	label.add_theme_color_override("font_color", Color(0.35, 0.72, 0.62))
	add_child(label)
	restart_btn = Button.new()
	restart_btn.text = "Restart"
	restart_btn.position = Vector2(80, 280)
	restart_btn.size = Vector2(220, 44)
	restart_btn.pressed.connect(_on_restart)
	add_child(restart_btn)


func show_win() -> void:
	visible = true
	restart_btn.grab_focus()


func _on_restart() -> void:
	restart_pressed.emit()

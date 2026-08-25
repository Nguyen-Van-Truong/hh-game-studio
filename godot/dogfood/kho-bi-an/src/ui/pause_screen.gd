class_name PauseScreen
extends Control

signal resume_pressed

var resume_btn: Button


func _ready() -> void:
	name = "Pause"
	process_mode = Node.PROCESS_MODE_WHEN_PAUSED
	set_anchors_preset(Control.PRESET_FULL_RECT)
	visible = false
	var bg: ColorRect = ColorRect.new()
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.color = Color(0.07, 0.09, 0.16, 0.82)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)
	var label: Label = Label.new()
	label.text = "Paused"
	label.position = Vector2(80, 200)
	label.size = Vector2(400, 40)
	label.add_theme_color_override("font_color", Color(0.93, 0.86, 0.70))
	add_child(label)
	resume_btn = Button.new()
	resume_btn.text = "Resume"
	resume_btn.position = Vector2(80, 280)
	resume_btn.size = Vector2(220, 44)
	resume_btn.pressed.connect(_on_resume)
	add_child(resume_btn)


func show_pause() -> void:
	visible = true
	resume_btn.grab_focus()


func hide_pause() -> void:
	visible = false


func _on_resume() -> void:
	resume_pressed.emit()

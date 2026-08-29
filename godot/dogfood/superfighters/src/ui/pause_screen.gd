class_name PauseScreen
extends Control

signal resume_pressed
signal controls_pressed

var resume_btn: Button
var controls_btn: Button


func _ready() -> void:
	name = "Pause"
	process_mode = Node.PROCESS_MODE_WHEN_PAUSED
	set_anchors_preset(Control.PRESET_FULL_RECT)
	visible = false
	UiTheme.apply(self)
	var bg: ColorRect = ColorRect.new()
	bg.name = "Backdrop"
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.color = Color(0.07, 0.11, 0.19, 0.88)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)
	var label: Label = Label.new()
	label.name = "TitleLabel"
	label.text = "Paused"
	label.position = Vector2(80, 160)
	label.size = Vector2(400, 40)
	label.add_theme_font_size_override("font_size", 32)
	label.add_theme_color_override("font_color", UiTheme.CREAM)
	add_child(label)
	resume_btn = Button.new()
	resume_btn.name = "Resume"
	resume_btn.text = "Resume"
	resume_btn.position = Vector2(80, 240)
	resume_btn.size = Vector2(240, 48)
	resume_btn.pressed.connect(_on_resume)
	add_child(resume_btn)
	controls_btn = Button.new()
	controls_btn.name = "Controls"
	controls_btn.text = "Controls"
	controls_btn.position = Vector2(80, 300)
	controls_btn.size = Vector2(240, 48)
	controls_btn.pressed.connect(_on_controls)
	add_child(controls_btn)
	var hint: Label = Label.new()
	hint.name = "InputHint"
	hint.text = "Esc / Start resume · Controls remaps keys · last standing wins"
	hint.position = Vector2(80, 368)
	hint.size = Vector2(1000, 32)
	hint.add_theme_font_size_override("font_size", 18)
	hint.add_theme_color_override("font_color", UiTheme.CREAM)
	add_child(hint)


func show_pause() -> void:
	visible = true
	resume_btn.grab_focus()


func hide_pause() -> void:
	visible = false


func _on_resume() -> void:
	resume_pressed.emit()


func _on_controls() -> void:
	controls_pressed.emit()

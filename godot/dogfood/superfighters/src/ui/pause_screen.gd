class_name PauseScreen
extends CanvasLayer

signal resume_pressed
signal controls_pressed
signal restart_pressed
signal quit_pressed

var resume_btn: Button
var controls_btn: Button
var restart_btn: Button
var quit_btn: Button


func _ready() -> void:
	name = "Pause"
	layer = 80
	follow_viewport_enabled = false
	process_mode = Node.PROCESS_MODE_WHEN_PAUSED
	visible = false
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
	UiTheme.apply(label)
	add_child(label)
	resume_btn = _make_btn("Resume", "Resume", Vector2(80, 240), _on_resume)
	controls_btn = _make_btn("Controls", "Controls", Vector2(80, 300), _on_controls)
	restart_btn = _make_btn("Restart", "Restart", Vector2(80, 360), _on_restart)
	quit_btn = _make_btn("Quit", "Quit", Vector2(80, 420), _on_quit)
	var hint: Label = Label.new()
	hint.name = "InputHint"
	hint.text = "Esc / Start resume · Restart same arena · Quit to title · last standing wins"
	hint.position = Vector2(80, 488)
	hint.size = Vector2(1000, 32)
	hint.add_theme_font_size_override("font_size", 18)
	hint.add_theme_color_override("font_color", UiTheme.CREAM)
	UiTheme.apply(hint)
	add_child(hint)


func _make_btn(node_name: String, caption: String, pos: Vector2, cb: Callable) -> Button:
	var btn: Button = Button.new()
	btn.name = node_name
	btn.text = caption
	btn.position = pos
	btn.size = Vector2(240, 48)
	btn.focus_mode = Control.FOCUS_ALL
	btn.mouse_filter = Control.MOUSE_FILTER_STOP
	btn.process_mode = Node.PROCESS_MODE_WHEN_PAUSED
	btn.pressed.connect(cb)
	UiTheme.apply(btn)
	add_child(btn)
	return btn


func show_pause() -> void:
	visible = true
	if resume_btn != null:
		resume_btn.grab_focus()


func hide_pause() -> void:
	visible = false


func _on_resume() -> void:
	resume_pressed.emit()


func _on_controls() -> void:
	controls_pressed.emit()


func _on_restart() -> void:
	restart_pressed.emit()


func _on_quit() -> void:
	quit_pressed.emit()

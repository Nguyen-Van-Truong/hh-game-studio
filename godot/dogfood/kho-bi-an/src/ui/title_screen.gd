class_name TitleScreen
extends Control

signal play_pressed
signal continue_pressed
signal restart_pressed

var play_btn: Button
var continue_btn: Button
var restart_btn: Button


func _ready() -> void:
	name = "Title"
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var bg: ColorRect = ColorRect.new()
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.color = Color(0.07, 0.09, 0.16)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)
	var title: Label = Label.new()
	title.text = "Kho Bi An"
	title.position = Vector2(80, 160)
	title.size = Vector2(600, 48)
	title.add_theme_color_override("font_color", Color(0.93, 0.86, 0.70))
	add_child(title)
	play_btn = _make_btn("Play", Vector2(80, 260))
	continue_btn = _make_btn("Continue", Vector2(80, 320))
	restart_btn = _make_btn("Restart", Vector2(80, 380))
	play_btn.pressed.connect(_on_play)
	continue_btn.pressed.connect(_on_continue)
	restart_btn.pressed.connect(_on_restart)
	play_btn.focus_neighbor_bottom = continue_btn.get_path()
	continue_btn.focus_neighbor_top = play_btn.get_path()
	continue_btn.focus_neighbor_bottom = restart_btn.get_path()
	restart_btn.focus_neighbor_top = continue_btn.get_path()
	play_btn.grab_focus()


func set_continue_enabled(on: bool) -> void:
	continue_btn.disabled = not on


func _make_btn(text: String, at: Vector2) -> Button:
	var btn: Button = Button.new()
	btn.text = text
	btn.position = at
	btn.size = Vector2(220, 44)
	add_child(btn)
	return btn


func _on_play() -> void:
	play_pressed.emit()


func _on_continue() -> void:
	continue_pressed.emit()


func _on_restart() -> void:
	restart_pressed.emit()

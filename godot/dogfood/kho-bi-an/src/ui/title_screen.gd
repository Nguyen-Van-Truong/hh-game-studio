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
	UiTheme.apply(self)
	var bg: ColorRect = ColorRect.new()
	bg.name = "Backdrop"
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.color = UiTheme.INDIGO
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)
	var title: Label = Label.new()
	title.name = "TitleLabel"
	title.text = "Kho Bí Ẩn"
	title.position = Vector2(80, 120)
	title.size = Vector2(720, 56)
	title.add_theme_font_size_override("font_size", 36)
	title.add_theme_color_override("font_color", UiTheme.CREAM)
	add_child(title)
	var sub: Label = Label.new()
	sub.name = "Subtitle"
	sub.text = "Relic-reached is win. Door-open is not win."
	sub.position = Vector2(80, 184)
	sub.size = Vector2(900, 32)
	sub.add_theme_color_override("font_color", UiTheme.BRASS)
	add_child(sub)
	var hint: Label = Label.new()
	hint.name = "InputHint"
	hint.text = "WASD / stick move · E / South interact · Esc / Start pause"
	hint.position = Vector2(80, 224)
	hint.size = Vector2(1000, 32)
	hint.add_theme_font_size_override("font_size", 18)
	hint.add_theme_color_override("font_color", UiTheme.CREAM)
	add_child(hint)
	play_btn = _make_btn("Play", Vector2(80, 300))
	continue_btn = _make_btn("Continue", Vector2(80, 360))
	restart_btn = _make_btn("Restart", Vector2(80, 420))
	play_btn.pressed.connect(_on_play)
	continue_btn.pressed.connect(_on_continue)
	restart_btn.pressed.connect(_on_restart)
	play_btn.focus_neighbor_bottom = continue_btn.get_path()
	play_btn.focus_neighbor_top = restart_btn.get_path()
	continue_btn.focus_neighbor_top = play_btn.get_path()
	continue_btn.focus_neighbor_bottom = restart_btn.get_path()
	restart_btn.focus_neighbor_top = continue_btn.get_path()
	restart_btn.focus_neighbor_bottom = play_btn.get_path()
	play_btn.grab_focus()


func set_continue_enabled(on: bool) -> void:
	continue_btn.disabled = not on


func _make_btn(text: String, at: Vector2) -> Button:
	var btn: Button = Button.new()
	btn.text = text
	btn.position = at
	btn.size = Vector2(240, 48)
	add_child(btn)
	return btn


func _on_play() -> void:
	play_pressed.emit()


func _on_continue() -> void:
	continue_pressed.emit()


func _on_restart() -> void:
	restart_pressed.emit()

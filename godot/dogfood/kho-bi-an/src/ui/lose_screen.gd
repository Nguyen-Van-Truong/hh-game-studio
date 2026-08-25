class_name LoseScreen
extends Control

signal restart_pressed

var restart_btn: Button


func _ready() -> void:
	name = "Lose"
	set_anchors_preset(Control.PRESET_FULL_RECT)
	visible = false
	UiTheme.apply(self)
	var bg: ColorRect = ColorRect.new()
	bg.name = "Backdrop"
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.color = Color(0.16, 0.07, 0.08, 0.92)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)
	var label: Label = Label.new()
	label.name = "TitleLabel"
	label.text = "Warden contact"
	label.position = Vector2(80, 200)
	label.size = Vector2(640, 48)
	label.add_theme_font_size_override("font_size", 32)
	label.add_theme_color_override("font_color", UiTheme.RUST)
	add_child(label)
	var sub: Label = Label.new()
	sub.name = "Subtitle"
	sub.text = "The warden found you. Restart to try again."
	sub.position = Vector2(80, 256)
	sub.size = Vector2(800, 32)
	sub.add_theme_color_override("font_color", UiTheme.CREAM)
	add_child(sub)
	restart_btn = Button.new()
	restart_btn.name = "Restart"
	restart_btn.text = "Restart"
	restart_btn.position = Vector2(80, 320)
	restart_btn.size = Vector2(240, 48)
	restart_btn.pressed.connect(_on_restart)
	add_child(restart_btn)


func show_lose() -> void:
	visible = true
	restart_btn.grab_focus()


func _on_restart() -> void:
	restart_pressed.emit()

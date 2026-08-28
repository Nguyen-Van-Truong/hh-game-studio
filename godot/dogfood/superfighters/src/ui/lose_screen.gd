class_name LoseScreen
extends Control

signal restart_pressed

var restart_btn: Button
var title_label: Label
var sub_label: Label


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
	title_label = Label.new()
	title_label.name = "TitleLabel"
	title_label.text = "Down"
	title_label.position = Vector2(80, 200)
	title_label.size = Vector2(800, 48)
	title_label.add_theme_font_size_override("font_size", 32)
	title_label.add_theme_color_override("font_color", UiTheme.RUST)
	add_child(title_label)
	sub_label = Label.new()
	sub_label.name = "Subtitle"
	sub_label.text = "The arena took you. Restart to fight again."
	sub_label.position = Vector2(80, 256)
	sub_label.size = Vector2(900, 32)
	sub_label.add_theme_color_override("font_color", UiTheme.CREAM)
	add_child(sub_label)
	restart_btn = Button.new()
	restart_btn.name = "Restart"
	restart_btn.text = "Restart"
	restart_btn.position = Vector2(80, 320)
	restart_btn.size = Vector2(240, 48)
	restart_btn.pressed.connect(_on_restart)
	add_child(restart_btn)


func show_lose(headline: String, detail: String) -> void:
	title_label.text = headline
	sub_label.text = detail
	visible = true
	restart_btn.grab_focus()


func _on_restart() -> void:
	restart_pressed.emit()

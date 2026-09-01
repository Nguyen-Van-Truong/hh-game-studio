class_name LoseScreen
extends CanvasLayer

signal rematch_pressed
signal title_pressed
signal restart_pressed

var rematch_btn: Button
var title_btn: Button
var restart_btn: Button
var title_label: Label
var sub_label: Label
var _token: int = 0


func _ready() -> void:
	name = "Lose"
	layer = 90
	visible = false
	process_mode = Node.PROCESS_MODE_ALWAYS
	var root: Control = Control.new()
	root.name = "Root"
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	UiTheme.apply(root)
	add_child(root)
	var bg: ColorRect = ColorRect.new()
	bg.name = "Backdrop"
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.color = Color(0.16, 0.07, 0.08, 0.92)
	bg.mouse_filter = Control.MOUSE_FILTER_STOP
	root.add_child(bg)
	title_label = Label.new()
	title_label.name = "TitleLabel"
	title_label.text = "Down"
	title_label.position = Vector2(80, 200)
	title_label.size = Vector2(800, 48)
	title_label.add_theme_font_size_override("font_size", 32)
	title_label.add_theme_color_override("font_color", UiTheme.RUST)
	root.add_child(title_label)
	sub_label = Label.new()
	sub_label.name = "Subtitle"
	sub_label.text = "The arena took you. Rematch to fight again."
	sub_label.position = Vector2(80, 256)
	sub_label.size = Vector2(900, 32)
	sub_label.add_theme_color_override("font_color", UiTheme.CREAM)
	root.add_child(sub_label)
	rematch_btn = _btn(root, "Rematch", "Rematch", Vector2(80, 320), _on_rematch)
	title_btn = _btn(root, "Title", "Title", Vector2(340, 320), _on_title)
	restart_btn = rematch_btn


func show_lose(headline: String, detail: String, token: int = -1) -> void:
	if token >= 0 and token != _token:
		return
	title_label.text = headline
	sub_label.text = detail
	visible = true
	if rematch_btn != null:
		rematch_btn.grab_focus()


func hide_result() -> void:
	_token += 1
	visible = false


func _btn(root: Control, node_name: String, caption: String, at: Vector2, cb: Callable) -> Button:
	var btn: Button = Button.new()
	btn.name = node_name
	btn.text = caption
	btn.position = at
	btn.size = Vector2(240, 48)
	btn.pressed.connect(cb)
	root.add_child(btn)
	return btn


func _on_rematch() -> void:
	rematch_pressed.emit()
	restart_pressed.emit()


func _on_title() -> void:
	title_pressed.emit()

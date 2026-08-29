class_name TitleScreen
extends Control

signal vs_one_pressed
signal vs_two_pressed
signal stage_pressed
signal map_cycle_pressed
signal controls_pressed

var vs_one_btn: Button
var vs_two_btn: Button
var stage_btn: Button
var map_btn: Button
var controls_btn: Button
var map_id: String = "rooftops"


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
	title.text = "Vault Fighters"
	title.position = Vector2(80, 72)
	title.size = Vector2(900, 56)
	title.add_theme_font_size_override("font_size", 40)
	title.add_theme_color_override("font_color", UiTheme.CREAM)
	add_child(title)
	var sub: Label = Label.new()
	sub.name = "Subtitle"
	sub.text = "2D arena deathmatch — last standing wins"
	sub.position = Vector2(80, 136)
	sub.size = Vector2(1100, 32)
	sub.add_theme_color_override("font_color", UiTheme.BRASS)
	add_child(sub)
	var hint: Label = Label.new()
	hint.name = "InputHint"
	hint.text = "P1 arrows · N melee · hold M aim/release fire · hold comma throw · Esc pause"
	hint.position = Vector2(80, 176)
	hint.size = Vector2(1100, 28)
	hint.add_theme_font_size_override("font_size", 16)
	hint.add_theme_color_override("font_color", UiTheme.CREAM)
	add_child(hint)
	var hint2: Label = Label.new()
	hint2.name = "InputHint2"
	hint2.text = "P2 WASD · 1 melee · hold 2 fire · hold 3 throw · double-tap to sprint"
	hint2.position = Vector2(80, 204)
	hint2.size = Vector2(1100, 28)
	hint2.add_theme_font_size_override("font_size", 16)
	hint2.add_theme_color_override("font_color", UiTheme.CREAM)
	add_child(hint2)
	vs_one_btn = _make_btn("VS 1P", Vector2(80, 256))
	vs_two_btn = _make_btn("VS 2P", Vector2(80, 312))
	stage_btn = _make_btn("Stage", Vector2(80, 368))
	map_btn = _make_btn("Map: Rooftops", Vector2(80, 424))
	map_btn.name = "MapCycle"
	controls_btn = _make_btn("Controls", Vector2(80, 480))
	controls_btn.name = "Controls"
	vs_one_btn.pressed.connect(_on_vs_one)
	vs_two_btn.pressed.connect(_on_vs_two)
	stage_btn.pressed.connect(_on_stage)
	map_btn.pressed.connect(_on_map)
	controls_btn.pressed.connect(_on_controls)
	vs_one_btn.focus_neighbor_bottom = vs_two_btn.get_path()
	vs_one_btn.focus_neighbor_top = controls_btn.get_path()
	vs_two_btn.focus_neighbor_top = vs_one_btn.get_path()
	vs_two_btn.focus_neighbor_bottom = stage_btn.get_path()
	stage_btn.focus_neighbor_top = vs_two_btn.get_path()
	stage_btn.focus_neighbor_bottom = map_btn.get_path()
	map_btn.focus_neighbor_top = stage_btn.get_path()
	map_btn.focus_neighbor_bottom = controls_btn.get_path()
	controls_btn.focus_neighbor_top = map_btn.get_path()
	controls_btn.focus_neighbor_bottom = vs_one_btn.get_path()
	vs_one_btn.grab_focus()


func set_map_id(next_id: String) -> void:
	map_id = next_id
	if map_btn != null:
		map_btn.text = "Map: %s" % Maps.display_name(map_id)


func _make_btn(text: String, at: Vector2) -> Button:
	var btn: Button = Button.new()
	btn.text = text
	btn.position = at
	btn.size = Vector2(280, 48)
	add_child(btn)
	return btn


func _on_vs_one() -> void:
	vs_one_pressed.emit()


func _on_vs_two() -> void:
	vs_two_pressed.emit()


func _on_stage() -> void:
	stage_pressed.emit()


func _on_map() -> void:
	map_cycle_pressed.emit()


func _on_controls() -> void:
	controls_pressed.emit()

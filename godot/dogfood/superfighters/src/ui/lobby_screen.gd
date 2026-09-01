class_name LobbyScreen
extends Control

signal start_pressed
signal back_pressed
signal map_cycle_pressed
signal controls_pressed
signal p1_ready_pressed
signal p2_ready_pressed

var mode: String = "vs1"
var map_id: String = "rooftops"
var p1_ready: bool = true
var p2_ready: bool = false
var bot_ready: bool = true
var title_label: Label
var mode_label: Label
var map_label: Label
var p1_label: Label
var p2_label: Label
var hint_label: Label
var start_btn: Button
var back_btn: Button
var map_btn: Button
var controls_btn: Button
var p1_ready_btn: Button
var p2_ready_btn: Button


func _ready() -> void:
	name = "Lobby"
	z_index = 20
	visible = false
	set_anchors_preset(Control.PRESET_FULL_RECT)
	UiTheme.apply(self)
	var bg: ColorRect = ColorRect.new()
	bg.name = "Backdrop"
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.color = Color(0.07, 0.11, 0.19, 0.96)
	bg.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(bg)
	title_label = _label("TitleLabel", "Ready room", Vector2(80, 64), 36, UiTheme.CREAM)
	mode_label = _label("ModeLabel", "VS 1P", Vector2(80, 120), 22, UiTheme.BRASS)
	map_label = _label("MapLabel", "Map: Skyline Relay", Vector2(80, 156), 20, UiTheme.CREAM)
	p1_label = _label("P1ReadyLabel", "P1 Blue  ready", Vector2(80, 208), 20, UiTheme.BLUE)
	p2_label = _label("P2ReadyLabel", "Bots  ready", Vector2(80, 240), 20, UiTheme.RUST)
	hint_label = _label(
		"Hint",
		"P1 arrows · N melee · hold M fire  ·  P2 WASD · 1 melee · hold 2 fire  ·  Esc back",
		Vector2(80, 280),
		16,
		UiTheme.CREAM
	)
	start_btn = _btn("Start", "Start", Vector2(80, 336))
	p1_ready_btn = _btn("P1Ready", "P1 Ready", Vector2(80, 396))
	p2_ready_btn = _btn("P2Ready", "P2 Ready", Vector2(380, 396))
	map_btn = _btn("MapCycle", "Cycle map", Vector2(80, 456))
	controls_btn = _btn("Controls", "Controls", Vector2(380, 456))
	back_btn = _btn("Back", "Title", Vector2(80, 516))
	start_btn.pressed.connect(_on_start)
	p1_ready_btn.pressed.connect(_on_p1_ready)
	p2_ready_btn.pressed.connect(_on_p2_ready)
	map_btn.pressed.connect(_on_map)
	controls_btn.pressed.connect(_on_controls)
	back_btn.pressed.connect(_on_back)
	start_btn.focus_neighbor_bottom = p1_ready_btn.get_path()
	start_btn.focus_neighbor_top = back_btn.get_path()
	p1_ready_btn.focus_neighbor_top = start_btn.get_path()
	p1_ready_btn.focus_neighbor_bottom = map_btn.get_path()
	p1_ready_btn.focus_neighbor_right = p2_ready_btn.get_path()
	p2_ready_btn.focus_neighbor_left = p1_ready_btn.get_path()
	p2_ready_btn.focus_neighbor_top = start_btn.get_path()
	map_btn.focus_neighbor_top = p1_ready_btn.get_path()
	map_btn.focus_neighbor_bottom = back_btn.get_path()
	map_btn.focus_neighbor_right = controls_btn.get_path()
	controls_btn.focus_neighbor_left = map_btn.get_path()
	back_btn.focus_neighbor_top = map_btn.get_path()
	back_btn.focus_neighbor_bottom = start_btn.get_path()
	_refresh()


func show_lobby(p_mode: String, p_map: String) -> void:
	mode = p_mode
	map_id = p_map
	p1_ready = true
	bot_ready = p_mode == "vs1"
	p2_ready = p_mode == "vs2"
	visible = true
	_refresh()
	if start_btn != null:
		start_btn.grab_focus()


func hide_lobby() -> void:
	visible = false


func set_map_id(next_id: String) -> void:
	map_id = next_id
	_refresh()


func can_start() -> bool:
	if not p1_ready:
		return false
	if mode == "vs2":
		return p2_ready
	return bot_ready


func _refresh() -> void:
	if mode_label != null:
		if mode == "vs2":
			mode_label.text = "Local VS 2P  ·  same keyboard"
		else:
			mode_label.text = "VS 1P  ·  P1 vs bots (smoke)"
	if map_label != null:
		map_label.text = "Map: %s" % Maps.display_name(map_id)
	if p1_label != null:
		p1_label.text = "P1 Blue  %s" % ("ready" if p1_ready else "not ready")
	if p2_label != null:
		if mode == "vs2":
			p2_label.text = "P2 Red   %s" % ("ready" if p2_ready else "not ready")
		else:
			p2_label.text = "Bots     %s" % ("ready" if bot_ready else "not ready")
	if start_btn != null:
		start_btn.disabled = not can_start()
	if p2_ready_btn != null:
		p2_ready_btn.visible = mode == "vs2"


func _label(node_name: String, text: String, at: Vector2, size: int, color: Color) -> Label:
	var lab: Label = Label.new()
	lab.name = node_name
	lab.text = text
	lab.position = at
	lab.size = Vector2(1100, 32)
	lab.add_theme_font_size_override("font_size", size)
	lab.add_theme_color_override("font_color", color)
	add_child(lab)
	return lab


func _btn(node_name: String, caption: String, at: Vector2) -> Button:
	var btn: Button = Button.new()
	btn.name = node_name
	btn.text = caption
	btn.position = at
	btn.size = Vector2(280, 48)
	add_child(btn)
	return btn


func _on_start() -> void:
	if can_start():
		start_pressed.emit()


func _on_p1_ready() -> void:
	p1_ready = not p1_ready
	_refresh()
	p1_ready_pressed.emit()


func _on_p2_ready() -> void:
	p2_ready = not p2_ready
	_refresh()
	p2_ready_pressed.emit()


func _on_map() -> void:
	map_cycle_pressed.emit()


func _on_controls() -> void:
	controls_pressed.emit()


func _on_back() -> void:
	back_pressed.emit()

class_name PauseScreen
extends Control

signal resume_pressed

var resume_btn: Button
var master_slider: HSlider
var music_slider: HSlider
var sfx_slider: HSlider
var fullscreen_btn: CheckButton
var last_fullscreen: bool = false


func _ready() -> void:
	name = "Pause"
	process_mode = Node.PROCESS_MODE_WHEN_PAUSED
	set_anchors_preset(Control.PRESET_FULL_RECT)
	visible = false
	UiTheme.apply(self)
	var bg: ColorRect = ColorRect.new()
	bg.name = "Backdrop"
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.color = Color(0.07, 0.09, 0.16, 0.88)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)
	var label: Label = Label.new()
	label.name = "TitleLabel"
	label.text = "Paused"
	label.position = Vector2(80, 72)
	label.size = Vector2(400, 40)
	label.add_theme_font_size_override("font_size", 32)
	label.add_theme_color_override("font_color", UiTheme.CREAM)
	add_child(label)
	resume_btn = Button.new()
	resume_btn.name = "Resume"
	resume_btn.text = "Resume"
	resume_btn.position = Vector2(80, 140)
	resume_btn.size = Vector2(240, 48)
	resume_btn.pressed.connect(_on_resume)
	add_child(resume_btn)
	master_slider = _make_slider("Master", Vector2(80, 214), 1.0, _on_master)
	music_slider = _make_slider("Music", Vector2(80, 294), 1.0, _on_music)
	sfx_slider = _make_slider("SFX", Vector2(80, 374), 1.0, _on_sfx)
	fullscreen_btn = CheckButton.new()
	fullscreen_btn.name = "Fullscreen"
	fullscreen_btn.text = "Fullscreen"
	fullscreen_btn.position = Vector2(80, 454)
	fullscreen_btn.size = Vector2(280, 40)
	fullscreen_btn.focus_mode = Control.FOCUS_ALL
	fullscreen_btn.toggled.connect(set_fullscreen)
	add_child(fullscreen_btn)
	var hint: Label = Label.new()
	hint.name = "InputHint"
	hint.text = "WASD / stick move · E / South interact · Esc / Start pause"
	hint.position = Vector2(80, 520)
	hint.size = Vector2(1000, 32)
	hint.add_theme_font_size_override("font_size", 18)
	hint.add_theme_color_override("font_color", UiTheme.CREAM)
	add_child(hint)
	_wire_focus()


func show_pause() -> void:
	visible = true
	resume_btn.grab_focus()


func hide_pause() -> void:
	visible = false


func apply_bus_linear(bus_name: String, linear: float) -> void:
	if bus_name == "Master":
		master_slider.value = linear
	elif bus_name == "Music":
		music_slider.value = linear
	elif bus_name == "SFX":
		sfx_slider.value = linear
	SfxBank.set_bus_linear(bus_name, linear)


func set_fullscreen(on: bool) -> void:
	last_fullscreen = on
	if fullscreen_btn.button_pressed != on:
		fullscreen_btn.set_pressed_no_signal(on)
	if on:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)
	else:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)


func _make_slider(bus_name: String, at: Vector2, initial: float, cb: Callable) -> HSlider:
	var caption: Label = Label.new()
	caption.text = "%s volume" % bus_name
	caption.position = at
	caption.size = Vector2(280, 28)
	caption.add_theme_color_override("font_color", UiTheme.CREAM)
	add_child(caption)
	var slider: HSlider = HSlider.new()
	slider.name = "%sVolume" % bus_name
	slider.position = Vector2(at.x, at.y + 28)
	slider.size = Vector2(360, 24)
	slider.min_value = 0.0
	slider.max_value = 1.0
	slider.step = 0.01
	slider.value = initial
	slider.focus_mode = Control.FOCUS_ALL
	slider.value_changed.connect(cb)
	add_child(slider)
	return slider


func _wire_focus() -> void:
	resume_btn.focus_neighbor_bottom = master_slider.get_path()
	resume_btn.focus_neighbor_top = fullscreen_btn.get_path()
	master_slider.focus_neighbor_top = resume_btn.get_path()
	master_slider.focus_neighbor_bottom = music_slider.get_path()
	music_slider.focus_neighbor_top = master_slider.get_path()
	music_slider.focus_neighbor_bottom = sfx_slider.get_path()
	sfx_slider.focus_neighbor_top = music_slider.get_path()
	sfx_slider.focus_neighbor_bottom = fullscreen_btn.get_path()
	fullscreen_btn.focus_neighbor_top = sfx_slider.get_path()
	fullscreen_btn.focus_neighbor_bottom = resume_btn.get_path()


func _on_resume() -> void:
	resume_pressed.emit()


func _on_master(value: float) -> void:
	SfxBank.set_bus_linear("Master", value)


func _on_music(value: float) -> void:
	SfxBank.set_bus_linear("Music", value)


func _on_sfx(value: float) -> void:
	SfxBank.set_bus_linear("SFX", value)

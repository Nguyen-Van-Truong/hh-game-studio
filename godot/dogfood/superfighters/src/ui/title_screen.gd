class_name TitleScreen
extends Control

signal vs_one_pressed
signal vs_two_pressed
signal stage_pressed
signal reset_stage_pressed
signal map_cycle_pressed
signal controls_pressed

var vs_one_btn: Button
var vs_two_btn: Button
var stage_btn: Button
var reset_stage_btn: Button
var confirm_reset_btn: Button
var map_btn: Button
var controls_btn: Button
var status_label: Label
var map_id: String = "rooftops"
var reset_armed: bool = false
var _reset_arm_frame: int = -1


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
	hint.text = "Two taps: VS 1P or VS 2P, then Start. Rematch from the result screen."
	hint.position = Vector2(80, 176)
	hint.size = Vector2(1100, 28)
	hint.add_theme_font_size_override("font_size", 16)
	hint.add_theme_color_override("font_color", UiTheme.BRASS)
	add_child(hint)
	var hint2: Label = Label.new()
	hint2.name = "InputHint2"
	hint2.text = "P1 arrows · N melee · hold M fire · hold comma throw · Esc pause"
	hint2.position = Vector2(80, 204)
	hint2.size = Vector2(1100, 28)
	hint2.add_theme_font_size_override("font_size", 16)
	hint2.add_theme_color_override("font_color", UiTheme.CREAM)
	add_child(hint2)
	var hint3: Label = Label.new()
	hint3.name = "InputHint3"
	hint3.text = "P2 WASD · 1 melee · hold 2 fire · hold 3 throw · same keyboard, no shared keys"
	hint3.position = Vector2(80, 232)
	hint3.size = Vector2(1100, 28)
	hint3.add_theme_font_size_override("font_size", 16)
	hint3.add_theme_color_override("font_color", UiTheme.CREAM)
	add_child(hint3)
	vs_one_btn = _make_btn("VS 1P", Vector2(80, 280))
	vs_two_btn = _make_btn("VS 2P", Vector2(80, 336))
	stage_btn = _make_btn("Stage", Vector2(80, 392))
	reset_stage_btn = _make_btn("Reset Stage", Vector2(380, 392))
	reset_stage_btn.name = "ResetStage"
	confirm_reset_btn = _make_btn("Confirm Reset", Vector2(680, 392))
	confirm_reset_btn.name = "ConfirmReset"
	confirm_reset_btn.visible = false
	map_btn = _make_btn("VS Map: %s" % Maps.display_name("rooftops"), Vector2(80, 448))
	map_btn.name = "MapCycle"
	controls_btn = _make_btn("Controls", Vector2(80, 504))
	controls_btn.name = "Controls"
	status_label = Label.new()
	status_label.name = "MatchStatus"
	status_label.text = ""
	status_label.position = Vector2(80, 568)
	status_label.size = Vector2(1100, 28)
	status_label.add_theme_font_size_override("font_size", 18)
	status_label.add_theme_color_override("font_color", UiTheme.BRASS)
	add_child(status_label)
	vs_one_btn.pressed.connect(_on_vs_one)
	vs_two_btn.pressed.connect(_on_vs_two)
	stage_btn.pressed.connect(_on_stage)
	reset_stage_btn.pressed.connect(_on_reset_stage)
	confirm_reset_btn.pressed.connect(_on_confirm_reset)
	map_btn.pressed.connect(_on_map)
	controls_btn.pressed.connect(_on_controls)
	vs_one_btn.focus_neighbor_bottom = vs_two_btn.get_path()
	vs_one_btn.focus_neighbor_top = controls_btn.get_path()
	vs_two_btn.focus_neighbor_top = vs_one_btn.get_path()
	vs_two_btn.focus_neighbor_bottom = stage_btn.get_path()
	stage_btn.focus_neighbor_top = vs_two_btn.get_path()
	stage_btn.focus_neighbor_bottom = map_btn.get_path()
	stage_btn.focus_neighbor_right = reset_stage_btn.get_path()
	reset_stage_btn.focus_neighbor_left = stage_btn.get_path()
	reset_stage_btn.focus_neighbor_right = confirm_reset_btn.get_path()
	reset_stage_btn.focus_neighbor_bottom = map_btn.get_path()
	confirm_reset_btn.focus_neighbor_left = reset_stage_btn.get_path()
	confirm_reset_btn.focus_neighbor_bottom = map_btn.get_path()
	map_btn.focus_neighbor_top = stage_btn.get_path()
	refresh_stage_caption()
	map_btn.focus_neighbor_bottom = controls_btn.get_path()
	controls_btn.focus_neighbor_top = map_btn.get_path()
	controls_btn.focus_neighbor_bottom = vs_one_btn.get_path()
	vs_one_btn.grab_focus()


func set_map_id(next_id: String) -> void:
	map_id = next_id
	if map_btn != null:
		map_btn.text = "VS Map: %s" % Maps.display_name(map_id)


func set_status(text: String) -> void:
	if status_label != null:
		status_label.text = text


func clear_status() -> void:
	set_status("")


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


func refresh_stage_caption() -> void:
	_disarm_reset()
	var progress: Dictionary = StageRules.load_or_empty()
	if stage_btn != null:
		stage_btn.text = StageRules.caption_for(progress)
	var idx: int = int(progress.get("current_index", 0))
	var score: int = int(progress.get("score", 0))
	var unlocks: Array = []
	if progress.get("unlocks", []) is Array:
		unlocks = progress.get("unlocks", []) as Array
	var reward: String = "none"
	if not unlocks.is_empty():
		reward = str(unlocks[unlocks.size() - 1])
	set_status(
		"Stage: %s · score %d · last unlock %s. VS Map below is VS only."
		% [Maps.display_name(StageRules.map_at(idx)), score, reward]
	)


func _on_stage() -> void:
	_disarm_reset()
	stage_pressed.emit()


func _disarm_reset() -> void:
	reset_armed = false
	_reset_arm_frame = -1
	if reset_stage_btn != null:
		reset_stage_btn.text = "Reset Stage"
	if confirm_reset_btn != null:
		confirm_reset_btn.visible = false
		confirm_reset_btn.text = "Confirm Reset"


func _on_reset_stage() -> void:
	if reset_armed:
		_disarm_reset()
		set_status("Stage reset canceled.")
		return
	reset_armed = true
	_reset_arm_frame = Engine.get_process_frames()
	if reset_stage_btn != null:
		reset_stage_btn.text = "Reset Stage"
	if confirm_reset_btn != null:
		confirm_reset_btn.visible = true
		confirm_reset_btn.text = "Confirm Reset"
	set_status("Click Confirm Reset to wipe Stage score and unlocks.")


func _on_confirm_reset() -> void:
	if not reset_armed:
		return
	if Engine.get_process_frames() <= _reset_arm_frame:
		return
	_disarm_reset()
	reset_stage_pressed.emit()


func _on_map() -> void:
	map_cycle_pressed.emit()


func _on_controls() -> void:
	controls_pressed.emit()

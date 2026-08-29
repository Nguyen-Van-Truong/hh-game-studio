class_name RemapScreen
extends Control

signal closed

var listen_action: String = ""
var status: Label
var rows: Dictionary = {}


func _ready() -> void:
	name = "Remap"
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_anchors_preset(Control.PRESET_FULL_RECT)
	visible = false
	UiTheme.apply(self)
	var bg: ColorRect = ColorRect.new()
	bg.name = "Backdrop"
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.color = Color(0.07, 0.11, 0.19, 0.94)
	bg.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(bg)
	var title: Label = Label.new()
	title.name = "TitleLabel"
	title.text = "Controls"
	title.position = Vector2(48, 24)
	title.size = Vector2(400, 40)
	title.add_theme_font_size_override("font_size", 32)
	title.add_theme_color_override("font_color", UiTheme.CREAM)
	add_child(title)
	var hint: Label = Label.new()
	hint.name = "Hint"
	hint.text = "P1 arrows+N/M/, · P2 WASD+1/2/3 · pad0 P1 / pad1 P2 · F11 is not a fighter key"
	hint.position = Vector2(48, 68)
	hint.size = Vector2(1180, 28)
	hint.add_theme_font_size_override("font_size", 16)
	hint.add_theme_color_override("font_color", UiTheme.BRASS)
	add_child(hint)
	_make_column("P1", 0, 48, 108)
	_make_column("P2", 1, 660, 108)
	status = Label.new()
	status.name = "Status"
	status.text = "Click a bind, then press a key or gamepad button. Save is atomic."
	status.position = Vector2(48, 560)
	status.size = Vector2(1180, 28)
	status.add_theme_font_size_override("font_size", 16)
	status.add_theme_color_override("font_color", UiTheme.CREAM)
	add_child(status)
	var save_btn: Button = _btn("Save", Vector2(48, 604))
	save_btn.name = "Save"
	save_btn.pressed.connect(_on_save)
	var reset_btn: Button = _btn("Reset", Vector2(300, 604))
	reset_btn.name = "Reset"
	reset_btn.pressed.connect(_on_reset)
	var back_btn: Button = _btn("Back", Vector2(552, 604))
	back_btn.name = "Back"
	back_btn.pressed.connect(_on_back)


func show_remap() -> void:
	listen_action = ""
	_refresh_labels()
	visible = true
	var back: Button = get_node_or_null("Back") as Button
	if back != null:
		back.grab_focus()


func hide_remap() -> void:
	listen_action = ""
	visible = false
	closed.emit()


func _unhandled_input(event: InputEvent) -> void:
	if not visible:
		return
	if listen_action == "":
		if event.is_action_pressed("ui_cancel") or (
			event is InputEventKey and (event as InputEventKey).physical_keycode == KEY_ESCAPE and event.is_pressed()
		):
			hide_remap()
			get_viewport().set_input_as_handled()
		return
	if event.is_echo() or not event.is_pressed():
		return
	if event is InputEventKey:
		var key_ev: InputEventKey = event as InputEventKey
		if key_ev.physical_keycode == KEY_ESCAPE:
			listen_action = ""
			status.text = "Listen cancelled."
			get_viewport().set_input_as_handled()
			return
		if key_ev.physical_keycode == KEY_F11:
			status.text = "F11 is page fullscreen, not a fighter action."
			listen_action = ""
			get_viewport().set_input_as_handled()
			return
		var errors: PackedStringArray = InputMapStore.rebind_key(listen_action, key_ev.physical_keycode)
		if errors.is_empty():
			status.text = "Rebound %s." % listen_action
		else:
			status.text = String(errors[0])
		listen_action = ""
		_refresh_labels()
		get_viewport().set_input_as_handled()
		return
	if event is InputEventJoypadButton:
		status.text = "Gamepad buttons stay device-locked (P1 pad0 / P2 pad1)."
		listen_action = ""
		get_viewport().set_input_as_handled()


func _make_column(title_text: String, slot: int, x: float, y: float) -> void:
	var title: Label = Label.new()
	title.text = title_text
	title.position = Vector2(x, y)
	title.size = Vector2(200, 28)
	title.add_theme_color_override("font_color", UiTheme.BRASS)
	add_child(title)
	var names: PackedStringArray = PackedStringArray([
		"left", "right", "up", "down", "jump", "crouch", "melee", "fire", "grenade"
	])
	var i: int = 0
	while i < names.size():
		var action: String = "p%d_%s" % [slot + 1, String(names[i])]
		var btn: Button = Button.new()
		btn.name = "Bind_%s" % action
		btn.position = Vector2(x, y + 36.0 + float(i) * 44.0)
		btn.size = Vector2(540, 40)
		btn.pressed.connect(_listen.bind(action))
		add_child(btn)
		rows[action] = btn
		i += 1


func _btn(text: String, at: Vector2) -> Button:
	var btn: Button = Button.new()
	btn.text = text
	btn.position = at
	btn.size = Vector2(232, 44)
	add_child(btn)
	return btn


func _listen(action: String) -> void:
	listen_action = action
	status.text = "Listening for %s…" % action


func _refresh_labels() -> void:
	var keys: Array = rows.keys()
	var i: int = 0
	while i < keys.size():
		var action: String = str(keys[i])
		var btn: Button = rows[action] as Button
		if btn != null:
			btn.text = "%s  ·  %s" % [action, InputMapStore.current_label(action)]
		i += 1


func _on_save() -> void:
	var path: String = InputMapStore.persist_atomic(InputMapStore.last_payload)
	if path == "":
		status.text = "Save failed: %s" % InputMapStore.last_error
		return
	status.text = "Saved atomically."


func _on_reset() -> void:
	var errors: PackedStringArray = InputMapStore.reset_defaults()
	if errors.is_empty():
		status.text = "Defaults restored (ledger:RL-CTRL-P1-* / RL-CTRL-P2-*)."
	else:
		status.text = String(errors[0])
	_refresh_labels()


func _on_back() -> void:
	hide_remap()

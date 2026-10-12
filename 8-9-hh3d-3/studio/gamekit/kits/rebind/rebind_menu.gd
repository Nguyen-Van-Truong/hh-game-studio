# HH gamekit kit rebind v1 - self-made (HH Studio)
extends Control
## Lists InputMap actions. Each button captures the next key or joypad event.

var _listening: String = ""
var _buttons: Dictionary = {}
var _built: bool = false


func _ready() -> void:
	build()


func build() -> void:
	if _built:
		return
	_built = true
	var box: VBoxContainer = VBoxContainer.new()
	box.name = "Actions"
	box.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(box)
	var names: PackedStringArray = PackedStringArray()
	for action_name: StringName in InputMap.get_actions():
		names.append(String(action_name))
	names.sort()
	for aname: String in names:
		var row: HBoxContainer = HBoxContainer.new()
		var label: Label = Label.new()
		label.text = aname
		label.custom_minimum_size = Vector2(180, 0)
		var button: Button = Button.new()
		button.text = _event_text(aname)
		button.pressed.connect(_on_listen.bind(aname))
		row.add_child(label)
		row.add_child(button)
		box.add_child(row)
		_buttons[aname] = button
	set_process_unhandled_input(true)


func _event_text(action_name: String) -> String:
	var events: Array = InputMap.action_get_events(action_name)
	if events.is_empty():
		return "(none)"
	var first: Variant = events[0]
	if first is InputEvent:
		return (first as InputEvent).as_text()
	return "(none)"


func _on_listen(action_name: String) -> void:
	_listening = action_name
	var button: Button = _buttons.get(action_name) as Button
	if button != null:
		button.text = "..."


func _unhandled_input(event: InputEvent) -> void:
	if _listening.is_empty() or event.is_echo():
		return
	var stored: InputEvent = _capture(event)
	if stored == null:
		return
	var node: Node = get_tree().root.get_node_or_null("HHRebind")
	if node == null:
		push_warning("HHRebind autoload is not installed")
		_listening = ""
		return
	node.call("remap", _listening, stored)
	node.call("save_bindings")
	var button: Button = _buttons.get(_listening) as Button
	if button != null:
		button.text = stored.as_text()
	_listening = ""
	get_viewport().set_input_as_handled()


func _capture(event: InputEvent) -> InputEvent:
	if event is InputEventKey and event.is_pressed():
		var src: InputEventKey = event as InputEventKey
		var key: InputEventKey = InputEventKey.new()
		key.keycode = src.keycode
		key.physical_keycode = src.physical_keycode
		key.unicode = src.unicode
		key.alt_pressed = src.alt_pressed
		key.shift_pressed = src.shift_pressed
		key.ctrl_pressed = src.ctrl_pressed
		key.meta_pressed = src.meta_pressed
		return key
	if event is InputEventJoypadButton and event.is_pressed():
		var bsrc: InputEventJoypadButton = event as InputEventJoypadButton
		var btn: InputEventJoypadButton = InputEventJoypadButton.new()
		btn.button_index = bsrc.button_index
		btn.device = bsrc.device
		return btn
	if event is InputEventJoypadMotion:
		var msrc: InputEventJoypadMotion = event as InputEventJoypadMotion
		if absf(msrc.axis_value) < 0.6:
			return null
		var motion: InputEventJoypadMotion = InputEventJoypadMotion.new()
		motion.axis = msrc.axis
		motion.axis_value = 1.0 if msrc.axis_value > 0.0 else -1.0
		motion.device = msrc.device
		return motion
	return null

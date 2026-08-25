class_name InputActions
extends RefCounted


static func install() -> void:
	_bind_move("move_left", KEY_A, KEY_LEFT, JOY_BUTTON_DPAD_LEFT, JOY_AXIS_LEFT_X, -1.0)
	_bind_move("move_right", KEY_D, KEY_RIGHT, JOY_BUTTON_DPAD_RIGHT, JOY_AXIS_LEFT_X, 1.0)
	_bind_move("move_up", KEY_W, KEY_UP, JOY_BUTTON_DPAD_UP, JOY_AXIS_LEFT_Y, -1.0)
	_bind_move("move_down", KEY_S, KEY_DOWN, JOY_BUTTON_DPAD_DOWN, JOY_AXIS_LEFT_Y, 1.0)
	_ensure("interact")
	if InputMap.action_get_events("interact").is_empty():
		_add_key("interact", KEY_E)
		_add_key("interact", KEY_ENTER)
		_add_joy_button("interact", JOY_BUTTON_A)
	_ensure("pause")
	if InputMap.action_get_events("pause").is_empty():
		_add_key("pause", KEY_ESCAPE)
		_add_joy_button("pause", JOY_BUTTON_START)


static func read_move() -> Vector2:
	var raw: Vector2 = Input.get_vector("move_left", "move_right", "move_up", "move_down")
	return cardinal(raw)


static func cardinal(raw: Vector2) -> Vector2:
	if raw.length_squared() <= 0.0001:
		return Vector2.ZERO
	if absf(raw.x) >= absf(raw.y):
		return Vector2(signf(raw.x), 0.0)
	return Vector2(0.0, signf(raw.y))


static func has_keyboard_and_gamepad(action: String) -> bool:
	var key_ok: bool = false
	var pad_ok: bool = false
	var events: Array = InputMap.action_get_events(action)
	var i: int = 0
	while i < events.size():
		var ev: InputEvent = events[i] as InputEvent
		if ev is InputEventKey:
			key_ok = true
		if ev is InputEventJoypadButton or ev is InputEventJoypadMotion:
			pad_ok = true
		i += 1
	return key_ok and pad_ok


static func _bind_move(
	action: String,
	letter: Key,
	arrow: Key,
	dpad: JoyButton,
	axis: JoyAxis,
	axis_value: float
) -> void:
	_ensure(action)
	if not InputMap.action_get_events(action).is_empty():
		return
	_add_key(action, letter)
	_add_key(action, arrow)
	_add_joy_button(action, dpad)
	_add_joy_axis(action, axis, axis_value)


static func _ensure(action: String) -> void:
	if not InputMap.has_action(action):
		InputMap.add_action(action, 0.5)


static func _add_key(action: String, keycode: Key) -> void:
	var ev: InputEventKey = InputEventKey.new()
	ev.physical_keycode = keycode
	InputMap.action_add_event(action, ev)


static func _add_joy_button(action: String, button: JoyButton) -> void:
	var ev: InputEventJoypadButton = InputEventJoypadButton.new()
	ev.button_index = button
	InputMap.action_add_event(action, ev)


static func _add_joy_axis(action: String, axis: JoyAxis, axis_value: float) -> void:
	var ev: InputEventJoypadMotion = InputEventJoypadMotion.new()
	ev.axis = axis
	ev.axis_value = axis_value
	InputMap.action_add_event(action, ev)

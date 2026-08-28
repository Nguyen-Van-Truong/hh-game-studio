class_name InputActions
extends RefCounted


static func install() -> void:
	_bind_axis("p1_left", KEY_LEFT, JOY_BUTTON_DPAD_LEFT, JOY_AXIS_LEFT_X, -1.0)
	_bind_axis("p1_right", KEY_RIGHT, JOY_BUTTON_DPAD_RIGHT, JOY_AXIS_LEFT_X, 1.0)
	_bind_axis("p1_up", KEY_UP, JOY_BUTTON_DPAD_UP, JOY_AXIS_LEFT_Y, -1.0)
	_bind_axis("p1_down", KEY_DOWN, JOY_BUTTON_DPAD_DOWN, JOY_AXIS_LEFT_Y, 1.0)
	_bind_button("p1_jump", KEY_UP, JOY_BUTTON_A)
	_bind_button("p1_crouch", KEY_DOWN, JOY_BUTTON_B)
	_bind_button("p1_melee", KEY_N, JOY_BUTTON_X)
	_bind_button("p1_fire", KEY_M, JOY_BUTTON_Y)
	_bind_trigger("p1_fire", JOY_AXIS_TRIGGER_RIGHT, 1.0)
	_bind_button("p1_grenade", KEY_COMMA, JOY_BUTTON_LEFT_SHOULDER)
	_bind_axis("p2_left", KEY_A, JOY_BUTTON_INVALID, JOY_AXIS_INVALID, 0.0)
	_bind_axis("p2_right", KEY_D, JOY_BUTTON_INVALID, JOY_AXIS_INVALID, 0.0)
	_bind_axis("p2_up", KEY_W, JOY_BUTTON_INVALID, JOY_AXIS_INVALID, 0.0)
	_bind_axis("p2_down", KEY_S, JOY_BUTTON_INVALID, JOY_AXIS_INVALID, 0.0)
	_bind_button("p2_jump", KEY_W, JOY_BUTTON_INVALID)
	_bind_button("p2_crouch", KEY_S, JOY_BUTTON_INVALID)
	_bind_button("p2_melee", KEY_1, JOY_BUTTON_INVALID)
	_bind_button("p2_fire", KEY_2, JOY_BUTTON_INVALID)
	_bind_button("p2_grenade", KEY_3, JOY_BUTTON_INVALID)
	_ensure("pause")
	if InputMap.action_get_events("pause").is_empty():
		_add_key("pause", KEY_ESCAPE)
		_add_joy_button("pause", JOY_BUTTON_START)


static func empty_cmd() -> Dictionary:
	return {
		"x": 0.0,
		"jump": false,
		"jump_pressed": false,
		"crouch": false,
		"melee": false,
		"fire_held": false,
		"fire_released": false,
		"grenade_held": false,
		"grenade_released": false,
		"on_ladder": false,
	}


static func read_player(slot: int) -> Dictionary:
	var prefix: String = "p1_" if slot == 0 else "p2_"
	var cmd: Dictionary = empty_cmd()
	var left: float = Input.get_action_strength(prefix + "left")
	var right: float = Input.get_action_strength(prefix + "right")
	cmd["x"] = right - left
	cmd["jump"] = Input.is_action_pressed(prefix + "jump") or Input.is_action_pressed(prefix + "up")
	cmd["jump_pressed"] = Input.is_action_just_pressed(prefix + "jump") or Input.is_action_just_pressed(prefix + "up")
	cmd["crouch"] = Input.is_action_pressed(prefix + "crouch") or Input.is_action_pressed(prefix + "down")
	cmd["melee"] = Input.is_action_just_pressed(prefix + "melee")
	cmd["fire_held"] = Input.is_action_pressed(prefix + "fire")
	cmd["fire_released"] = Input.is_action_just_released(prefix + "fire")
	cmd["grenade_held"] = Input.is_action_pressed(prefix + "grenade")
	cmd["grenade_released"] = Input.is_action_just_released(prefix + "grenade")
	return cmd


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


static func _bind_axis(action: String, key: Key, dpad: JoyButton, axis: JoyAxis, axis_value: float) -> void:
	_ensure(action)
	if not InputMap.action_get_events(action).is_empty():
		return
	_add_key(action, key)
	if dpad != JOY_BUTTON_INVALID:
		_add_joy_button(action, dpad)
	if axis != JOY_AXIS_INVALID:
		_add_joy_axis(action, axis, axis_value)


static func _bind_button(action: String, key: Key, joy: JoyButton) -> void:
	_ensure(action)
	if not InputMap.action_get_events(action).is_empty():
		return
	_add_key(action, key)
	if joy != JOY_BUTTON_INVALID:
		_add_joy_button(action, joy)


static func _bind_trigger(action: String, axis: JoyAxis, axis_value: float) -> void:
	_ensure(action)
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

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
	return cmd_from_frame(read_player_frame(slot, 0))


static func read_player_frame(slot: int, tick: int) -> InputFrame:
	var prefix: String = "p1_" if slot == 0 else "p2_"
	var frame: InputFrame = InputFrame.new()
	frame.schema_version = SimConstants.SCHEMA_VERSION
	frame.tick = tick
	frame.slot = slot
	var left: float = Input.get_action_strength(prefix + "left")
	var right: float = Input.get_action_strength(prefix + "right")
	var up: float = Input.get_action_strength(prefix + "up")
	var down: float = Input.get_action_strength(prefix + "down")
	frame.move_x = clampf(right - left, -1.0, 1.0)
	frame.move_y = clampf(down - up, -1.0, 1.0)
	_fill_edge(frame, "left", prefix + "left")
	_fill_edge(frame, "right", prefix + "right")
	_fill_edge(frame, "up", prefix + "up")
	_fill_edge(frame, "down", prefix + "down")
	_fill_edge(frame, "jump", prefix + "jump")
	_fill_edge(frame, "crouch", prefix + "crouch")
	_fill_edge(frame, "melee", prefix + "melee")
	_fill_edge(frame, "fire", prefix + "fire")
	_fill_edge(frame, "grenade", prefix + "grenade")
	return frame


static func cmd_from_frame(frame: InputFrame) -> Dictionary:
	var cmd: Dictionary = empty_cmd()
	if frame == null:
		return cmd
	var x: float = frame.move_x
	if absf(x) < 0.01:
		if frame.is_held("right"):
			x = 1.0
		elif frame.is_held("left"):
			x = -1.0
	cmd["x"] = x
	cmd["jump"] = frame.is_held("jump") or frame.is_held("up")
	cmd["jump_pressed"] = frame.is_pressed("jump") or frame.is_pressed("up")
	cmd["crouch"] = frame.is_held("crouch") or frame.is_held("down")
	cmd["melee"] = frame.is_pressed("melee")
	cmd["fire_held"] = frame.is_held("fire")
	cmd["fire_released"] = frame.is_released("fire")
	cmd["grenade_held"] = frame.is_held("grenade")
	cmd["grenade_released"] = frame.is_released("grenade")
	return cmd


static func cmd_from_variant(raw: Variant) -> Dictionary:
	if raw is InputFrame:
		return cmd_from_frame(raw as InputFrame)
	if raw is Dictionary:
		var d: Dictionary = raw as Dictionary
		if d.has("held") or d.has("pressed") or d.has("schema_version"):
			return cmd_from_frame(InputFrame.from_dict(d))
		return d.duplicate()
	return empty_cmd()


static func frame_from_cmd(cmd: Dictionary, tick: int, slot: int) -> InputFrame:
	var frame: InputFrame = InputFrame.new()
	frame.schema_version = SimConstants.SCHEMA_VERSION
	frame.tick = tick
	frame.slot = slot
	if cmd.is_empty():
		return frame
	var x: float = clampf(float(cmd.get("x", 0.0)), -1.0, 1.0)
	frame.move_x = x
	if x > 0.35:
		frame.held.append("right")
	elif x < -0.35:
		frame.held.append("left")
	if bool(cmd.get("jump", false)) or bool(cmd.get("jump_pressed", false)):
		frame.held.append("jump")
	if bool(cmd.get("jump_pressed", false)):
		frame.pressed.append("jump")
	if bool(cmd.get("crouch", false)):
		frame.held.append("crouch")
	if bool(cmd.get("melee", false)):
		frame.pressed.append("melee")
	if bool(cmd.get("fire_held", false)):
		frame.held.append("fire")
	if bool(cmd.get("fire_released", false)):
		frame.released.append("fire")
	if bool(cmd.get("grenade_held", false)):
		frame.held.append("grenade")
	if bool(cmd.get("grenade_released", false)):
		frame.released.append("grenade")
	return frame


static func empty_frame(tick: int, slot: int) -> Dictionary:
	return {
		"schema": SimConstants.INPUT_FRAME_ID,
		"schema_version": SimConstants.SCHEMA_VERSION,
		"tick": tick,
		"slot": slot,
		"held": [],
		"pressed": [],
		"released": [],
		"move_x": 0.0,
		"move_y": 0.0,
	}


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


static func _fill_edge(frame: InputFrame, action: String, map_name: String) -> void:
	if Input.is_action_pressed(map_name):
		frame.held.append(action)
	if Input.is_action_just_pressed(map_name):
		frame.pressed.append(action)
	if Input.is_action_just_released(map_name):
		frame.released.append(action)


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

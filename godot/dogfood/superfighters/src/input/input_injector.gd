class_name InputInjector
extends RefCounted

## Inject real InputEvent into the live Input singleton and viewport.
## Official proof must not use Input.action_press or cmd-dict step_fixed.


static func key_event(physical: Key, pressed: bool) -> InputEventKey:
	var ev: InputEventKey = InputEventKey.new()
	ev.physical_keycode = physical
	ev.keycode = physical
	ev.pressed = pressed
	ev.echo = false
	return ev


static func joy_button_event(device: int, button: JoyButton, pressed: bool) -> InputEventJoypadButton:
	var ev: InputEventJoypadButton = InputEventJoypadButton.new()
	ev.device = device
	ev.button_index = button
	ev.pressed = pressed
	ev.pressure = 1.0 if pressed else 0.0
	return ev


static func joy_axis_event(device: int, axis: JoyAxis, value: float) -> InputEventJoypadMotion:
	var ev: InputEventJoypadMotion = InputEventJoypadMotion.new()
	ev.device = device
	ev.axis = axis
	ev.axis_value = value
	return ev


static func inject(event: InputEvent, viewport: Viewport = null) -> Dictionary:
	Input.parse_input_event(event)
	Input.flush_buffered_events()
	if viewport != null:
		viewport.push_input(event, true)
	return describe(event)


static func inject_key(physical: Key, pressed: bool, viewport: Viewport = null) -> Dictionary:
	return inject(key_event(physical, pressed), viewport)


static func inject_joy_button(device: int, button: JoyButton, pressed: bool, viewport: Viewport = null) -> Dictionary:
	return inject(joy_button_event(device, button, pressed), viewport)


static func inject_joy_axis(device: int, axis: JoyAxis, value: float, viewport: Viewport = null) -> Dictionary:
	return inject(joy_axis_event(device, axis, value), viewport)


static func describe(event: InputEvent) -> Dictionary:
	var row: Dictionary = {
		"class": event.get_class(),
		"device": event.device,
		"pressed": event.is_pressed(),
		"source": "synthetic",
		"non_hardware": true,
		"used_action_press": false,
	}
	if event is InputEventKey:
		var key_ev: InputEventKey = event as InputEventKey
		row["physical"] = InputConstants.name_from_key(key_ev.physical_keycode)
		row["physical_keycode"] = int(key_ev.physical_keycode)
	elif event is InputEventJoypadButton:
		var joy_ev: InputEventJoypadButton = event as InputEventJoypadButton
		row["button"] = InputConstants.name_from_joy_button(joy_ev.button_index)
		row["button_index"] = int(joy_ev.button_index)
	elif event is InputEventJoypadMotion:
		var axis_ev: InputEventJoypadMotion = event as InputEventJoypadMotion
		row["axis"] = InputConstants.name_from_joy_axis(axis_ev.axis)
		row["axis_value"] = axis_ev.axis_value
	return row


static func gamepad_report() -> Dictionary:
	var pads: Array = Input.get_connected_joypads()
	var names: Array = []
	var i: int = 0
	while i < pads.size():
		var id: int = int(pads[i])
		names.append({
			"device": id,
			"name": Input.get_joy_name(id),
			"guid": Input.get_joy_guid(id),
		})
		i += 1
	return {
		"hardware_count": pads.size(),
		"hardware": pads.size() > 0,
		"synthetic": true,
		"non_hardware": true,
		"kind": "synthetic",
		"ledger": "RL-CTRL-SYNTH-PAD",
		"devices": names,
	}


static func release_known(viewport: Viewport = null) -> void:
	var keys: Array[Key] = [
		KEY_LEFT, KEY_RIGHT, KEY_UP, KEY_DOWN, KEY_A, KEY_D, KEY_W, KEY_S,
		KEY_N, KEY_M, KEY_COMMA, KEY_1, KEY_2, KEY_3, KEY_B, KEY_ESCAPE, KEY_F11,
	]
	var k: int = 0
	while k < keys.size():
		inject_key(keys[k], false, viewport)
		k += 1
	var buttons: Array[JoyButton] = [
		JOY_BUTTON_A, JOY_BUTTON_B, JOY_BUTTON_X, JOY_BUTTON_Y,
		JOY_BUTTON_LEFT_SHOULDER, JOY_BUTTON_START,
		JOY_BUTTON_DPAD_UP, JOY_BUTTON_DPAD_DOWN, JOY_BUTTON_DPAD_LEFT, JOY_BUTTON_DPAD_RIGHT,
	]
	var device: int = 0
	while device <= 1:
		var b: int = 0
		while b < buttons.size():
			inject_joy_button(device, buttons[b], false, viewport)
			b += 1
		inject_joy_axis(device, JOY_AXIS_LEFT_X, 0.0, viewport)
		inject_joy_axis(device, JOY_AXIS_LEFT_Y, 0.0, viewport)
		inject_joy_axis(device, JOY_AXIS_TRIGGER_RIGHT, 0.0, viewport)
		device += 1
	Input.flush_buffered_events()

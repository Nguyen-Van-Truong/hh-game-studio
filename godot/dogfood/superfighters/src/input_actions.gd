class_name InputActions
extends RefCounted

## Physical-key + device-split gamepad map (VF2-WP1).
## Listing keys cite ledger:RL-CTRL-*. Hold-to-aim stays
## ledger:RL-CTRL-HOLD-AIM (assumption). Roll is InputFrame
## ledger:RL-MOVE-ROLL (assumption). Dive stays
## ledger:RL-MOVE-DIVE (assumption). Kick stays
## ledger:RL-MOVE-JUMP-KICK (assumption). Y8 observation stays
## ledger:RL-MOVE-ROLL-DIVE (unavailable).


static var _held_prev: Array[PackedStringArray] = [PackedStringArray(), PackedStringArray()]


static func install() -> void:
	Input.set_use_accumulated_input(false)
	var errors: PackedStringArray = InputMapStore.apply(InputMapStore.default_payload())
	reset_edges()
	if errors.is_empty():
		return
	push_warning("InputActions.install defaults failed: %s" % String(errors[0]))


static func reset_edges() -> void:
	_held_prev = [PackedStringArray(), PackedStringArray()]


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
		"crouch_pressed": false,
		"roll": false,
		"dive": false,
		"kick": false,
	}


static func read_player(slot: int) -> Dictionary:
	return cmd_from_frame(read_player_frame(slot, 0))


static func read_player_frame(slot: int, tick: int) -> InputFrame:
	var prefix: String = "p1_" if slot == 0 else "p2_"
	var frame: InputFrame = InputFrame.new()
	frame.schema_version = SimConstants.SCHEMA_VERSION
	frame.tick = tick
	frame.slot = slot
	var left: float = _map_strength(prefix + "left")
	var right: float = _map_strength(prefix + "right")
	var up: float = _map_strength(prefix + "up")
	var down: float = _map_strength(prefix + "down")
	frame.move_x = clampf(right - left, -1.0, 1.0)
	frame.move_y = clampf(down - up, -1.0, 1.0)
	var now: PackedStringArray = PackedStringArray()
	_collect_held(now, "left", prefix + "left")
	_collect_held(now, "right", prefix + "right")
	_collect_held(now, "up", prefix + "up")
	_collect_held(now, "down", prefix + "down")
	_collect_held(now, "jump", prefix + "jump")
	_collect_held(now, "crouch", prefix + "crouch")
	_collect_held(now, "melee", prefix + "melee")
	_collect_held(now, "fire", prefix + "fire")
	_collect_held(now, "grenade", prefix + "grenade")
	frame.held = now
	var prev: PackedStringArray = PackedStringArray()
	if slot >= 0 and slot < _held_prev.size():
		prev = _held_prev[slot]
	var i: int = 0
	while i < now.size():
		var action: String = String(now[i])
		if not prev.has(action):
			frame.pressed.append(action)
		i += 1
	i = 0
	while i < prev.size():
		var old: String = String(prev[i])
		if not now.has(old):
			frame.released.append(old)
		i += 1
	if slot >= 0:
		while _held_prev.size() <= slot:
			_held_prev.append(PackedStringArray())
		_held_prev[slot] = now
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
	cmd["crouch_pressed"] = frame.is_pressed("crouch") or frame.is_pressed("down")
	cmd["roll"] = frame.is_pressed("roll")
	cmd["dive"] = frame.is_pressed("dive")
	cmd["kick"] = frame.is_pressed("kick")
	cmd["melee"] = frame.is_pressed("melee") or frame.is_pressed("kick")
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
			var cmd: Dictionary = cmd_from_frame(InputFrame.from_dict(d))
			if d.has("aim_x") or d.has("aim_y"):
				cmd["aim_x"] = float(d.get("aim_x", 0.0))
				cmd["aim_y"] = float(d.get("aim_y", 0.0))
			return cmd
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
	if bool(cmd.get("crouch_pressed", false)) and not frame.pressed.has("crouch"):
		frame.pressed.append("crouch")
	if bool(cmd.get("roll", false)):
		frame.pressed.append("roll")
	if bool(cmd.get("dive", false)):
		frame.pressed.append("dive")
	if bool(cmd.get("kick", false)):
		frame.pressed.append("kick")
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


static func uses_physical_keys(action: String) -> bool:
	if not InputMap.has_action(action):
		return false
	var events: Array = InputMap.action_get_events(action)
	var saw_key: bool = false
	var i: int = 0
	while i < events.size():
		var ev: InputEvent = events[i] as InputEvent
		if ev is InputEventKey:
			saw_key = true
			if int((ev as InputEventKey).physical_keycode) == 0:
				return false
		i += 1
	return saw_key


static func snapshot_edges(slot: int, tick: int) -> Dictionary:
	var frame: InputFrame = read_player_frame(slot, tick)
	return {
		"slot": slot,
		"tick": tick,
		"held": Array(frame.held),
		"pressed": Array(frame.pressed),
		"released": Array(frame.released),
		"move_x": frame.move_x,
		"move_y": frame.move_y,
	}


static func _collect_held(into: PackedStringArray, action: String, map_name: String) -> void:
	if _map_held(map_name):
		into.append(action)


static func _map_held(map_name: String) -> bool:
	return _map_strength(map_name) >= InputConstants.DEADZONE


static func _map_strength(map_name: String) -> float:
	if not InputMap.has_action(map_name):
		return 0.0
	var best: float = 0.0
	var joy_busy: bool = false
	var events: Array = InputMap.action_get_events(map_name)
	var i: int = 0
	while i < events.size():
		var ev: InputEvent = events[i] as InputEvent
		if ev is InputEventKey:
			var key: InputEventKey = ev as InputEventKey
			if Input.is_physical_key_pressed(key.physical_keycode):
				best = maxf(best, 1.0)
		elif ev is InputEventJoypadButton:
			var joy: InputEventJoypadButton = ev as InputEventJoypadButton
			if Input.is_joy_button_pressed(joy.device, joy.button_index):
				best = maxf(best, 1.0)
			if Input.is_joy_button_pressed(InputConstants.P1_DEVICE, joy.button_index):
				joy_busy = true
			if Input.is_joy_button_pressed(InputConstants.P2_DEVICE, joy.button_index):
				joy_busy = true
		elif ev is InputEventJoypadMotion:
			var axis: InputEventJoypadMotion = ev as InputEventJoypadMotion
			var value: float = Input.get_joy_axis(axis.device, axis.axis)
			if absf(value) >= InputConstants.DEADZONE:
				if axis.axis_value < 0.0 and value <= -InputConstants.DEADZONE:
					best = maxf(best, absf(value))
				elif axis.axis_value > 0.0 and value >= InputConstants.DEADZONE:
					best = maxf(best, absf(value))
			if absf(Input.get_joy_axis(InputConstants.P1_DEVICE, axis.axis)) >= InputConstants.DEADZONE:
				joy_busy = true
			if absf(Input.get_joy_axis(InputConstants.P2_DEVICE, axis.axis)) >= InputConstants.DEADZONE:
				joy_busy = true
		i += 1
	if best < InputConstants.DEADZONE and not joy_busy and Input.is_action_pressed(map_name):
		best = maxf(best, Input.get_action_strength(map_name))
		if best < InputConstants.DEADZONE:
			best = 1.0
	return best

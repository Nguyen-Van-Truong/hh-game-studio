class_name InputMapCases
extends RefCounted

## VF2-WP1 official input cases. Proof is InputEvent inject + InputFrame.
## Must not use Input.action_press or cmd-dict step_fixed.


static func run_all(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	_append(errors, schema_and_map())
	_append(errors, remap_ui_present(app))
	_append(errors, await drive_official_trace(app))
	_append(errors, await live_move_from_events(app))
	_append(errors, remap_atomic())
	_append(errors, gamepad_smoke())
	return errors


static func schema_and_map() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var schema: Dictionary = SimConstants.load_json(InputConstants.SCHEMA_PATH)
	if schema.is_empty():
		errors.append("missing data/input/remap_schema.json")
		return errors
	if str(schema.get("schema", "")) != InputConstants.SCHEMA_ID:
		errors.append("remap schema id mismatch")
	if str(schema.get("title", "")) != "Vault Fighters":
		errors.append("remap schema title must be Vault Fighters")
	if bool(schema.get("y8_parity_claimed", true)):
		errors.append("remap schema must not claim Y8 parity")
	if str(schema.get("ledger_clock", "")) != "RL-SIM-FIXED-60":
		errors.append("remap schema must cite RL-SIM-FIXED-60")
	if absf(float(schema.get("deadzone", 0.0)) - InputConstants.DEADZONE) > 0.0001:
		errors.append("remap schema deadzone mismatch")
	var actions: Dictionary = SimConstants.load_json(SimConstants.ACTIONS_PATH)
	if str(actions.get("hold_to_aim_ledger", "")) != "RL-CTRL-HOLD-AIM":
		errors.append("input_actions.json lost hold-to-aim ledger")
	if str(actions.get("hold_to_aim_class", "")) != "assumption":
		errors.append("hold-to-aim must stay assumption")
	if (actions.get("reserved_not_shipped", []) as Array).has("roll"):
		errors.append("roll must be a shipped InputFrame action")
	if not (actions.get("reserved_not_shipped", []) as Array).has("dive"):
		errors.append("dive must stay reserved_not_shipped")
	if str(actions.get("roll_class", "")) != "assumption":
		errors.append("roll must stay assumption")
	InputActions.install()
	var i: int = 0
	while i < InputConstants.FIGHTER_ACTIONS.size():
		var action: String = String(InputConstants.FIGHTER_ACTIONS[i])
		if not InputMap.has_action(action):
			errors.append("missing action %s" % action)
		elif not InputActions.has_keyboard_and_gamepad(action):
			errors.append("action %s missing keyboard+gamepad" % action)
		elif not InputActions.uses_physical_keys(action):
			errors.append("action %s must use physical_keycode" % action)
		i += 1
	if InputMapStore.binds_f11():
		errors.append("F11 is bound as a fighter action")
	var p1_devices: PackedInt32Array = InputMapStore.action_joy_devices("p1_melee")
	var p2_devices: PackedInt32Array = InputMapStore.action_joy_devices("p2_melee")
	if not p1_devices.has(InputConstants.P1_DEVICE):
		errors.append("P1 melee pad must be device 0")
	if p1_devices.has(InputConstants.P2_DEVICE):
		errors.append("P1 melee must not listen on device 1")
	if not p2_devices.has(InputConstants.P2_DEVICE):
		errors.append("P2 melee pad must be device 1")
	if p2_devices.has(InputConstants.P1_DEVICE):
		errors.append("P2 melee must not listen on device 0")
	if absf(InputMap.action_get_deadzone("p1_right") - InputConstants.DEADZONE) > 0.0001:
		errors.append("p1_right deadzone must be product 0.25")
	return errors


static func remap_ui_present(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	if app.remap_screen == null:
		errors.append("missing RemapScreen")
		return errors
	if app.title == null or app.title.get_node_or_null("Controls") == null:
		errors.append("title missing Controls button")
	app.remap_screen.show_remap()
	if not app.remap_screen.visible:
		errors.append("RemapScreen did not show")
	if app.remap_screen.get_node_or_null("Save") == null:
		errors.append("RemapScreen missing Save")
	app.remap_screen.hide_remap()
	if app.remap_screen.visible:
		errors.append("RemapScreen did not hide")
	return errors


static func drive_official_trace(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var path: String = "%s/p1_p2_independent.json" % InputConstants.TRACE_DIR
	var trace: Dictionary = SimConstants.load_json(path)
	if trace.is_empty():
		errors.append("missing official input trace")
		return errors
	if str(trace.get("schema", "")) != InputConstants.TRACE_ID:
		errors.append("input trace schema mismatch")
	if bool(trace.get("used_step_fixed", true)):
		errors.append("input trace must not use step_fixed")
	if bool(trace.get("used_action_press", true)):
		errors.append("input trace must not use action_press")
	if bool(trace.get("y8_parity_claimed", true)):
		errors.append("input trace claimed Y8 parity")
	if str(trace.get("hold_to_aim", "")).find("assumption") < 0:
		errors.append("input trace must keep hold-to-aim as assumption")
	var viewport: Viewport = app.get_viewport()
	InputMapStore.apply(InputMapStore.default_payload())
	InputActions.reset_edges()
	InputInjector.release_known(viewport)
	InputActions.reset_edges()
	await _idle(app)
	InputActions.reset_edges()
	var steps: Array = trace.get("steps", []) as Array
	var i: int = 0
	while i < steps.size():
		var step: Dictionary = steps[i] as Dictionary
		var sid: String = str(step.get("id", "step%d" % i))
		if bool(step.get("wait_frame", false)):
			await _idle(app)
		var injects: Array = []
		if step.has("injects"):
			injects = step.get("injects", []) as Array
		elif step.has("inject"):
			injects.append(step.get("inject", {}))
		var j: int = 0
		while j < injects.size():
			_inject_row(injects[j] as Dictionary, viewport)
			j += 1
		var p1: Dictionary = InputActions.snapshot_edges(0, i)
		var p2: Dictionary = InputActions.snapshot_edges(1, i)
		_append(errors, _expect_slot(sid, "p1", p1, step.get("expect_p1", {}) as Dictionary))
		_append(errors, _expect_slot(sid, "p2", p2, step.get("expect_p2", {}) as Dictionary))
		i += 1
	InputInjector.release_known(viewport)
	return errors


static func live_move_from_events(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "rooftops", 0)
	var session: GameSession = app.session
	if session == null:
		errors.append("live move missing session")
		return errors
	var p1: Fighter = session.fighter_at_slot(0)
	var p2: Fighter = session.fighter_at_slot(1)
	if p1 == null or p2 == null:
		errors.append("live move needs human P1 and P2")
		return errors
	var viewport: Viewport = app.get_viewport()
	await _idle(app)
	await SimReplay.sync_physics(app)
	InputInjector.release_known(viewport)
	InputActions.reset_edges()
	var x1: float = p1.global_position.x
	var x2: float = p2.global_position.x
	InputInjector.inject_key(KEY_RIGHT, true, viewport)
	var probe: InputFrame = InputActions.read_player_frame(0, session.clock.tick)
	InputActions.reset_edges()
	if not probe.is_held("right"):
		errors.append(
			"live InputFrame missing right held phys=%s events=%d"
			% [Input.is_physical_key_pressed(KEY_RIGHT), InputMap.action_get_events("p1_right").size()]
		)
		return errors
	var cmd: Dictionary = InputActions.cmd_from_frame(probe)
	if absf(float(cmd.get("x", 0.0))) < 0.35:
		errors.append("live cmd x from RIGHT was %s" % str(cmd.get("x", 0.0)))
	var n: int = 0
	while n < 24:
		if not session.step_from_live_input():
			errors.append("live move P1 step_from_live_input failed reject=%s" % str(session.last_reject))
			break
		n += 1
	if p1.global_position.x <= x1 + 2.0:
		errors.append(
			"InputEvent RIGHT did not move P1 via live InputFrame x0=%s x1=%s floor=%s"
			% [str(x1), str(p1.global_position.x), str(p1.is_on_floor())]
		)
	if p2.global_position.x > x2 + 2.0:
		errors.append("P1 RIGHT leaked into P2 motion")
	InputInjector.inject_key(KEY_RIGHT, false, viewport)
	InputInjector.inject_key(KEY_A, true, viewport)
	var y2: float = p2.global_position.x
	n = 0
	while n < 24:
		session.step_from_live_input()
		n += 1
	if p2.global_position.x >= y2 - 2.0:
		errors.append(
			"InputEvent A did not move P2 left via live InputFrame x0=%s x1=%s"
			% [str(y2), str(p2.global_position.x)]
		)
	InputInjector.release_known(viewport)
	return errors


static func remap_atomic() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	InputMapStore.apply(InputMapStore.default_payload())
	var rebound: PackedStringArray = InputMapStore.rebind_key("p1_melee", KEY_B)
	if not rebound.is_empty():
		errors.append("rebind melee failed: %s" % String(rebound[0]))
		return errors
	var path: String = InputMapStore.persist_atomic(InputMapStore.last_payload, "remap_test.json")
	if path == "":
		errors.append("atomic remap save failed: %s" % InputMapStore.last_error)
		return errors
	if FileAccess.file_exists(path + ".tmp"):
		errors.append("atomic remap left a tmp file")
	var saved: Dictionary = InputMapStore.load_saved("remap_test.json")
	if saved.is_empty():
		errors.append("atomic remap load empty")
		return errors
	if str(saved.get("schema_hash", "")) == "":
		errors.append("atomic remap missing schema_hash")
	if str(saved.get("title", "")) != "Vault Fighters":
		errors.append("saved remap title must be Vault Fighters")
	var viewport: Viewport = null
	InputInjector.release_known(viewport)
	InputActions.reset_edges()
	InputInjector.inject_key(KEY_B, true, viewport)
	var frame_b: InputFrame = InputActions.read_player_frame(0, 0)
	if not frame_b.is_pressed("melee"):
		errors.append("remapped KEY_B must press P1 melee")
	InputInjector.inject_key(KEY_B, false, viewport)
	InputInjector.inject_key(KEY_N, true, viewport)
	var frame_n: InputFrame = InputActions.read_player_frame(0, 1)
	if frame_n.is_pressed("melee") or frame_n.is_held("melee"):
		errors.append("old KEY_N still triggers melee after remap")
	InputInjector.inject_key(KEY_N, false, viewport)
	var f11: PackedStringArray = InputMapStore.rebind_key("p1_melee", KEY_F11)
	if f11.is_empty():
		errors.append("F11 remap must be rejected")
	var bad: Dictionary = InputMapStore.default_payload()
	bad["p1_device"] = 0
	bad["p2_device"] = 0
	if InputMapStore.validate(bad).is_empty():
		errors.append("same-device remap must fail validate")
	if InputMapStore.persist_atomic(bad, "remap_bad.json") != "":
		errors.append("same-device remap must not save")
	InputMapStore.apply(InputMapStore.default_payload())
	return errors


static func gamepad_smoke() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var report: Dictionary = InputInjector.gamepad_report()
	if not bool(report.get("non_hardware", false)):
		errors.append("official pad inject must be marked non-hardware")
	if not bool(report.get("synthetic", false)):
		errors.append("official pad inject must record synthetic device")
	if int(report.get("hardware_count", -1)) > 0:
		var viewport: Viewport = null
		InputInjector.release_known(viewport)
		InputInjector.inject_joy_button(0, JOY_BUTTON_X, true, viewport)
		var frame: InputFrame = InputActions.read_player_frame(0, 0)
		if not frame.is_pressed("melee") and not frame.is_held("melee"):
			errors.append("hardware smoke: device 0 West did not map to P1 melee")
		var other: InputFrame = InputActions.read_player_frame(1, 0)
		if other.is_pressed("melee") or other.is_held("melee"):
			errors.append("hardware smoke: device 0 leaked to P2")
		InputInjector.release_known(viewport)
	return errors


static func _inject_row(row: Dictionary, viewport: Viewport) -> void:
	var kind: String = str(row.get("class", "InputEventKey"))
	if kind == "InputEventJoypadButton":
		InputInjector.inject_joy_button(
			int(row.get("device", 0)),
			InputConstants.joy_button_from_name(str(row.get("button", "A"))),
			bool(row.get("pressed", false)),
			viewport
		)
		return
	if kind == "InputEventJoypadMotion":
		InputInjector.inject_joy_axis(
			int(row.get("device", 0)),
			InputConstants.joy_axis_from_name(str(row.get("axis", "LEFT_X"))),
			float(row.get("axis_value", 0.0)),
			viewport
		)
		return
	InputInjector.inject_key(
		InputConstants.key_from_name(str(row.get("physical", ""))),
		bool(row.get("pressed", false)),
		viewport
	)


static func _expect_slot(sid: String, who: String, got: Dictionary, expect: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	if expect.is_empty():
		return errors
	var held: Array = got.get("held", []) as Array
	var pressed: Array = got.get("pressed", []) as Array
	var released: Array = got.get("released", []) as Array
	if bool(expect.get("empty", false)):
		if not held.is_empty() or not pressed.is_empty():
			errors.append("%s %s not empty held=%s pressed=%s" % [sid, who, str(held), str(pressed)])
	_require_has(errors, sid, who, "held", held, expect.get("held_has", []) as Array)
	_require_has(errors, sid, who, "pressed", pressed, expect.get("pressed_has", []) as Array)
	_require_has(errors, sid, who, "released", released, expect.get("released_has", []) as Array)
	_require_missing(errors, sid, who, "held", held, expect.get("not_held", []) as Array)
	_require_missing(errors, sid, who, "pressed", pressed, expect.get("not_pressed", []) as Array)
	if expect.has("move_x_min") and float(got.get("move_x", 0.0)) < float(expect.get("move_x_min", 0.0)):
		errors.append("%s %s move_x %s < %s" % [sid, who, str(got.get("move_x", 0.0)), str(expect.get("move_x_min", 0.0))])
	if expect.has("move_x_max") and absf(float(got.get("move_x", 0.0))) > float(expect.get("move_x_max", 0.0)):
		errors.append("%s %s move_x %s exceeds %s" % [sid, who, str(got.get("move_x", 0.0)), str(expect.get("move_x_max", 0.0))])
	return errors


static func _require_has(errors: PackedStringArray, sid: String, who: String, kind: String, got: Array, need: Array) -> void:
	var i: int = 0
	while i < need.size():
		var action: String = str(need[i])
		if not got.has(action):
			errors.append("%s %s missing %s %s got=%s" % [sid, who, kind, action, str(got)])
		i += 1


static func _require_missing(errors: PackedStringArray, sid: String, who: String, kind: String, got: Array, banned: Array) -> void:
	var i: int = 0
	while i < banned.size():
		var action: String = str(banned[i])
		if got.has(action):
			errors.append("%s %s unexpected %s %s" % [sid, who, kind, action])
		i += 1


static func _idle(app: App) -> void:
	var tree: SceneTree = app.get_tree()
	if tree != null:
		await tree.process_frame
		await tree.process_frame
	else:
		await Engine.get_main_loop().process_frame


static func _append(target: PackedStringArray, extra: PackedStringArray) -> void:
	var i: int = 0
	while i < extra.size():
		target.append(String(extra[i]))
		i += 1

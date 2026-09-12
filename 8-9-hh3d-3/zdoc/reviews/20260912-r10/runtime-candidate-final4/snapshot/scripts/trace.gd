extends SceneTree

var failures: Array[String] = []
var quit_seen := false
var fixture: Object
var ready_to_quit := false
var observations: Array[Dictionary] = []

func _initialize() -> void:
	create_timer(10.0).timeout.connect(_watchdog)
	var packed := load("res://main.tscn") as PackedScene
	if packed == null:
		failures.append("main scene did not load")
		quit(2)
		return
	fixture = packed.instantiate()
	root.add_child(fixture)
	fixture.connect("transitioned", Callable(self, "_on_transition"))
	await _frames(2)
	if str(fixture.call("phase_name")) != "MENU":
		failures.append("initial phase is not MENU")
	_record("menu")
	if "--capture" in OS.get_cmdline_user_args() and DisplayServer.get_name() != "headless":
		await RenderingServer.frame_post_draw
		if root.get_texture().get_image().save_png("res://menu.png") != OK:
			failures.append("menu screenshot save failed")
	_send_key(KEY_TAB)
	await _frames(1)
	if str(fixture.call("focus_name")) != "QuitButton":
		failures.append("Tab did not move focus to Quit")
	if "--menu-quit" in OS.get_cmdline_user_args():
		_record("quit_focused")
		ready_to_quit = failures.is_empty()
		if not ready_to_quit:
			_watchdog()
			return
		_send_key(KEY_ENTER)
		return
	_send_key(KEY_TAB, true)
	await _frames(1)
	if str(fixture.call("focus_name")) != "StartButton":
		failures.append("reverse Tab did not restore Start focus")
	_send_key(KEY_ENTER)
	await _frames(2)
	if str(fixture.call("phase_name")) != "PLAY":
		failures.append("real focused Start button did not enter PLAY")
	_record("start")
	var start_snapshot: Dictionary = fixture.call("snapshot")
	var start_position: Vector2 = start_snapshot["body_position"]
	_press(KEY_RIGHT)
	await _physics_frames(6)
	await _frames(1)
	_release(KEY_RIGHT)
	await _physics_frames(1)
	var moved_snapshot: Dictionary = fixture.call("snapshot")
	if (moved_snapshot["body_position"] as Vector2).x <= start_position.x:
		failures.append("movement postcondition was not observed")
	_record("moved")
	var before_pause: int = int((fixture.call("snapshot") as Dictionary)["sim_tick"])
	_send_key(KEY_ESCAPE)
	await _physics_frames(2)
	var paused: Dictionary = fixture.call("snapshot")
	_press(KEY_RIGHT)
	await _physics_frames(6)
	await _frames(1)
	_release(KEY_RIGHT)
	var paused_later: Dictionary = fixture.call("snapshot")
	if paused["phase"] != "PAUSED" or paused["sim_tick"] != paused_later["sim_tick"] or paused["body_position"] != paused_later["body_position"]:
		failures.append("pause did not freeze simulation")
	_record("paused_frozen")
	_send_key(KEY_ESCAPE)
	await _physics_frames(2)
	if str(fixture.call("phase_name")) != "PLAY" or int((fixture.call("snapshot") as Dictionary)["sim_tick"]) <= before_pause:
		failures.append("resume postcondition was not observed")
	_record("resumed")
	if not failures.is_empty():
		push_error(JSON.stringify({"trace": "FAIL", "failures": failures}))
		quit(2)
	else:
		ready_to_quit = true
		_send_key(KEY_Q)
		await _frames(3)
		if not quit_seen:
			push_error(JSON.stringify({"trace": "FAIL", "failures": ["QUITTING transition was not observed"]}))
			quit(2)

func _frames(count: int) -> void:
	for _i in count:
		await process_frame

func _physics_frames(count: int) -> void:
	for _i in count:
		await physics_frame

func _send_key(key: Key, reverse_tab := false) -> void:
	var event := InputEventKey.new()
	event.keycode = key
	event.physical_keycode = key
	event.pressed = true
	event.shift_pressed = reverse_tab
	Input.parse_input_event(event)
	_release(key, reverse_tab)

func _press(key: Key) -> void:
	var event := InputEventKey.new()
	event.keycode = key
	event.physical_keycode = key
	event.pressed = true
	Input.parse_input_event(event)

func _release(key: Key, reverse_tab := false) -> void:
	var event := InputEventKey.new()
	event.keycode = key
	event.physical_keycode = key
	event.pressed = false
	event.shift_pressed = reverse_tab
	Input.parse_input_event(event)

func _on_transition(name: String) -> void:
	if name == "QUITTING":
		quit_seen = true
		_record("quitting")
		if ready_to_quit and failures.is_empty() and str(fixture.call("phase_name")) == "QUITTING":
			print("GT01_TRACE " + JSON.stringify({"result": "PASS", "phase": "QUITTING", "sim_tick": int((fixture.call("snapshot") as Dictionary)["sim_tick"]), "observations": observations}))

func _record(label: String) -> void:
	var state: Dictionary = fixture.call("snapshot")
	var position_value: Vector2 = state["body_position"]
	observations.append({"label": label, "phase": state["phase"], "sim_tick": state["sim_tick"], "body": [position_value.x, position_value.y], "focus": fixture.call("focus_name")})

func _watchdog() -> void:
	if not quit_seen:
		push_error(JSON.stringify({"trace": "FAIL", "failures": failures, "reason": "trace did not reach validated quit"}))
		quit(2)

extends SceneTree

const GameScript = preload("res://game/ui/main.gd")
var failures: int = 0
var assertions: int = 0
var game: VaultGame

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	game = GameScript.new()
	root.add_child(game)
	await process_frame
	_send_key(KEY_ENTER)
	await process_frame
	_expect(game.phase == VaultGame.Phase.MATCH, "Enter starts match through input path")
	_send_key(KEY_P)
	await process_frame
	_expect(game.paused, "P pauses through input path")
	_send_key(KEY_P)
	await process_frame
	_expect(not game.paused, "P resumes through input path")
	_send_key(KEY_ESCAPE)
	await process_frame
	_expect(game.phase == VaultGame.Phase.MENU, "Escape returns to menu through input path")
	if failures == 0:
		print("RR_INPUT_PATH PASS assertions=%d" % assertions)
	else:
		printerr("RR_INPUT_PATH FAIL failures=%d assertions=%d" % [failures, assertions])
	quit(0 if failures == 0 else 1)

func _send_key(code: Key) -> void:
	var event := InputEventKey.new()
	event.keycode = code
	event.pressed = true
	Input.parse_input_event(event)
	event = InputEventKey.new()
	event.keycode = code
	event.pressed = false
	Input.parse_input_event(event)

func _expect(condition: bool, message: String) -> void:
	assertions += 1
	if not condition:
		failures += 1
		printerr("FAIL: %s" % message)

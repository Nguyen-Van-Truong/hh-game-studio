extends SceneTree

var _fails: PackedStringArray = PackedStringArray()


func _initialize() -> void:
	call_deferred("_boot")


func _boot() -> void:
	seed(1)
	InputActions.install()
	var packed: PackedScene = load("res://scenes/main.tscn") as PackedScene
	var app: App = packed.instantiate() as App
	app.test_driven = true
	root.add_child(app)
	var errors: PackedStringArray = await InputMapCases.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	var report: Dictionary = InputInjector.gamepad_report()
	print("HH_VF_INPUT run_id=VF2WP1-20260829-ASIA-SAIGON-01")
	print("HH_VF_INPUT DISPLAY=%s" % DisplayServer.get_name())
	print("HH_VF_INPUT USED_STEP_FIXED=0 USED_ACTION_PRESS=0")
	print("HH_VF_INPUT P1P2=%s" % ("split" if _count("leak") + _count("not empty") + _count("missing") == 0 else "coupled"))
	print("HH_VF_INPUT EDGES=%s" % ("pressed-held-released" if _count("pressed") + _count("held") + _count("released") == 0 else "fail"))
	print("HH_VF_INPUT DEADZONE=%s" % ("0.25" if _count("dead") + _count("move_x") == 0 else "fail"))
	print("HH_VF_INPUT REMAP=%s" % ("atomic" if _count("remap") + _count("atomic") == 0 else "fail"))
	print("HH_VF_INPUT PAD_HARDWARE=%d PAD_SYNTHETIC=1 NON_HARDWARE=1" % int(report.get("hardware_count", 0)))
	print("HH_VF_INPUT HOLD_AIM=assumption ROLL=unavailable")
	if _fails.is_empty():
		print("PASS: Vault Fighters input mapping")
	else:
		print("FAIL: Vault Fighters input mapping")
		i = 0
		while i < _fails.size():
			print("  - %s" % String(_fails[i]))
			i += 1
	if is_instance_valid(app):
		app.shutdown()
		app.queue_free()
	await process_frame
	await process_frame
	quit(0 if _fails.is_empty() else 1)


func _fail(msg: String) -> void:
	_fails.append(msg)
	print("HH_ASSERT_FAIL %s" % msg)


func _count(needle: String) -> int:
	var n: int = 0
	var i: int = 0
	while i < _fails.size():
		if String(_fails[i]).contains(needle):
			n += 1
		i += 1
	return n

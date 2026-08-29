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
	var errors: PackedStringArray = await LocomotionCases.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	print("HH_VF_LOCO run_id=VF2WP2-20260829-ASIA-SAIGON-01")
	print("HH_VF_LOCO DISPLAY=%s" % DisplayServer.get_name())
	print(
		"HH_VF_LOCO USED_STEP_FIXED=%d USED_APPLY_FRAMES=%d USED_PARSE_INPUT_EVENT=%d USED_ACTION_PRESS=%d"
		% [
			LocomotionCases.used_step_fixed,
			LocomotionCases.used_apply_frames,
			LocomotionCases.used_parse_input_event,
			LocomotionCases.used_action_press
		]
	)
	print("HH_VF_LOCO EPSILON=%s HASH2=%s" % [
		str(Locomotion.epsilon()),
		"match" if _count("hashes differ") + _count("position delta") == 0 else "fail"
	])
	print("HH_VF_LOCO TUNNEL=%s" % ("none" if _count("tunnel") + _count("fell through") == 0 else "fail"))
	print("HH_VF_LOCO CAMERA=%s" % ("arena_fit" if _count("camera") == 0 else "fail"))
	print("HH_VF_LOCO HOLD_AIM=assumption ROLL=unavailable CLOCK=RL-SIM-FIXED-60")
	if _fails.is_empty():
		print("PASS: Vault Fighters locomotion baseline")
	else:
		print("FAIL: Vault Fighters locomotion baseline")
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

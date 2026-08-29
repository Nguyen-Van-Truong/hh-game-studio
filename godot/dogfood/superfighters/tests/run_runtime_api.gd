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
	var errors: PackedStringArray = RuntimeCases.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	print("HH_VF_RUNTIME run_id=VF1WP4-20260829-ASIA-SAIGON-01")
	print("HH_VF_RUNTIME PAUSE_SNAP=%s" % ("stable" if _count("pause") + _count("hash changed") == 0 else "drift"))
	print("HH_VF_RUNTIME RESTART_SNAP=%s" % ("fresh" if _count("restart") == 0 else "stale"))
	print("HH_VF_RUNTIME RESTORE_HASH=%s" % ("match" if _count("restore") == 0 else "mismatch"))
	print("HH_VF_RUNTIME AUTH=%s" % ("reject" if _count("unauthorized") + _count("malformed") == 0 else "leaked"))
	print("HH_VF_RUNTIME REDACT=%s" % ("1" if _count("echoed") + _count("leaked") == 0 else "0"))
	if _fails.is_empty():
		print("PASS: Vault Fighters runtime diagnostics")
	else:
		print("FAIL: Vault Fighters runtime diagnostics")
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

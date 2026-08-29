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
	var errors: PackedStringArray = await TraceCases.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	print("HH_VF_TRACE run_id=VF1WP3-20260829-ASIA-SAIGON-01")
	print("HH_VF_TRACE WINDOW=%s" % ("1" if SimReplay.window_requested() else "0"))
	print("HH_VF_TRACE MATCH=%s" % ("1" if _count_prefix("official") == 0 and _count_prefix("replay hashes") == 0 else "0"))
	print("HH_VF_TRACE MUTATE=%s" % ("fail" if _count_prefix("changing one key") == 0 else "same"))
	print("HH_VF_TRACE RECORD=%s" % ("1" if _count_prefix("record") == 0 and _count_prefix("live") == 0 else "0"))
	print("HH_VF_TRACE FIXTURE=%s" % ("distinct" if _count_prefix("fixture") == 0 else "leaked"))
	print("HH_VF_TRACE APPLY_FRAMES=%s" % ("1" if _count_prefix("cmd dicts") == 0 else "0"))
	if _fails.is_empty():
		print("PASS: Vault Fighters golden InputFrame traces")
	else:
		print("FAIL: Vault Fighters golden InputFrame traces")
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


func _count_prefix(needle: String) -> int:
	var n: int = 0
	var i: int = 0
	while i < _fails.size():
		if String(_fails[i]).contains(needle):
			n += 1
		i += 1
	return n

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
	var errors: PackedStringArray = SimContractCases.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail(String(errors[i]))
		i += 1
	print("HH_VF_SIM run_id=VF1WP2-20260829-ASIA-SAIGON-01")
	print("HH_VF_SIM HASH_RUNS=3 MATCH=%s" % ("1" if _count_prefix("seed+trace") == 0 else "0"))
	print("HH_VF_SIM PAUSE_TICK=%s" % ("stable" if _count_prefix("pause") + _count_prefix("resume") + _count_prefix("clock") == 0 else "jump"))
	print("HH_VF_SIM MALFORMED=%s" % ("rejected" if _count_prefix("malformed") == 0 else "accepted"))
	print("HH_VF_SIM SNAPSHOT_PURE=%s" % ("1" if _count_prefix("snapshot") == 0 else "0"))
	if _fails.is_empty():
		print("PASS: Vault Fighters sim contract")
	else:
		print("FAIL: Vault Fighters sim contract")
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


func _count_prefix(prefix: String) -> int:
	var n: int = 0
	var i: int = 0
	while i < _fails.size():
		if String(_fails[i]).contains(prefix):
			n += 1
		i += 1
	return n

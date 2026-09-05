extends SceneTree

## Diagnostic only — not in freeze.

const BotCasesScript: GDScript = preload("res://tests/bot_cases.gd")


func _initialize() -> void:
	call_deferred("_boot")


func _boot() -> void:
	InputActions.install()
	print("HH_DIAG boot")
	var packed: PackedScene = load("res://scenes/main.tscn") as PackedScene
	var app: App = packed.instantiate() as App
	app.test_driven = true
	root.add_child(app)
	print("HH_DIAG app ready")
	var t0: int = Time.get_ticks_msec()
	print("HH_DIAG finish begin")
	var errors: PackedStringArray = await BotCasesScript.finish_match(app, "gauge")
	var elapsed: float = (Time.get_ticks_msec() - t0) / 1000.0
	print(
		"HH_DIAG finish elapsed=%.1fs outcome=%s verdict=%s errors=%d"
		% [
			elapsed,
			str(BotCasesScript.outcome_finish.get("outcome", "")),
			str(BotCasesScript.outcome_finish.get("verdict", "")),
			errors.size(),
		]
	)
	var i: int = 0
	while i < errors.size():
		print("HH_DIAG err %s" % String(errors[i]))
		i += 1
	app.shutdown()
	app.queue_free()
	await process_frame
	quit(0 if errors.is_empty() else 1)

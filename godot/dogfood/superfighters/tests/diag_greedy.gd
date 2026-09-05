extends SceneTree

## Diagnostic only — rooftops planner vs greedy compare. Not official.


const BotCasesScript: GDScript = preload("res://tests/bot_cases.gd")


func _initialize() -> void:
	call_deferred("_boot")


func _boot() -> void:
	InputActions.install()
	var packed: PackedScene = load("res://scenes/main.tscn") as PackedScene
	var app: App = packed.instantiate() as App
	app.test_driven = true
	root.add_child(app)
	var errors: PackedStringArray = await BotCasesScript.greedy_compare(app)
	var row: Dictionary = BotCasesScript.outcome_greedy
	print(
		"HH_DIAG GREEDY verdict=%s arrived=%s p_goal=%.1f p_engage=%.1f g_goal=%.1f p_pit=%s g_pit=%s diff=%s"
		% [
			str(row.get("verdict", "")),
			str(row.get("planner_arrived", false)),
			float(row.get("planner_goal_dist", 0.0)),
			float(row.get("planner_engage_dist", 0.0)),
			float(row.get("greedy_goal_dist", 0.0)),
			str(row.get("planner_pit_deaths", "")),
			str(row.get("greedy_pit_deaths", "")),
			str(row.get("differential", "")),
		]
	)
	var i: int = 0
	while i < errors.size():
		print("HH_DIAG ERR %s" % String(errors[i]))
		i += 1
	app.shutdown()
	app.queue_free()
	await process_frame
	quit(0 if errors.is_empty() else 1)

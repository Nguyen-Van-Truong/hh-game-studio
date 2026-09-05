extends SceneTree

## Diagnostic only — rooftops + storage after path rewrite.

const BotCasesScript: GDScript = preload("res://tests/bot_cases.gd")


func _initialize() -> void:
	call_deferred("_boot")


func _boot() -> void:
	InputActions.install()
	var packed: PackedScene = load("res://scenes/main.tscn") as PackedScene
	var app: App = packed.instantiate() as App
	app.test_driven = true
	root.add_child(app)
	var ids: PackedStringArray = PackedStringArray(["rooftops", "storage"])
	var errors: PackedStringArray = await BotCasesScript.maps_seeded(app, ids)
	var i: int = 0
	while i < ids.size():
		var mid: String = String(ids[i])
		var row: Dictionary = BotCasesScript.map_rows.get(mid, {}) as Dictionary
		print(
			"HH_DIAG MAP id=%s reach=%s reason=%s moved=%.1f toward=%.1f goal=%.1f wp=%.1f engage=%.1f closest=%.1f gun=%s melee=%s pit_blocks=%s pit_reroutes=%s"
			% [
				mid,
				str(row.get("reach_ok", false)),
				str(row.get("reach_reason", "none")),
				float(row.get("moved", 0.0)),
				float(row.get("toward", 0.0)),
				float(row.get("goal_dist", 0.0)),
				float(row.get("waypoint_dist", 0.0)),
				float(row.get("engage_dist", 0.0)),
				float(row.get("closest_engage", 0.0)),
				str(row.get("gun_used", "")),
				str(row.get("melee_used", "")),
				str(row.get("pit_blocks", "")),
				str(row.get("pit_reroutes", "")),
			]
		)
		i += 1
	var ei: int = 0
	while ei < errors.size():
		print("HH_DIAG ERR %s" % String(errors[ei]))
		ei += 1
	print("HH_DIAG MAPS %s errors=%d" % ["pass" if errors.is_empty() else "fail", errors.size()])
	app.shutdown()
	app.queue_free()
	await process_frame
	quit(0 if errors.is_empty() else 1)

extends SceneTree

## Diagnostic only. Not official. Not in freeze extra.
## Proves catalog melee win/loss on the four stage maps.

const StageCasesScript: GDScript = preload("res://tests/stage_cases.gd")
const _Stage: GDScript = preload("res://src/sim/stage.gd")


func _initialize() -> void:
	call_deferred("_boot")


func _boot() -> void:
	InputActions.install()
	OS.set_environment("HH_VF_STAGE_STORE", "progress_vf6wp3_diag.json")
	_Stage.reset_progress()
	var packed: PackedScene = load("res://scenes/main.tscn") as PackedScene
	var app: App = packed.instantiate() as App
	app.test_driven = true
	root.add_child(app)
	var fails: PackedStringArray = PackedStringArray()
	var only: String = OS.get_environment("HH_VF_DIAG_MAP")
	var maps: PackedStringArray = PackedStringArray(["rooftops", "storage", "police", "hazardous"])
	if only != "" and only != "all":
		maps = PackedStringArray([only])
	var i: int = 0
	while i < maps.size():
		var mid: String = String(maps[i])
		var stage_i: int = 0
		var ids: PackedStringArray = _Stage.arena_ids()
		var j: int = 0
		while j < ids.size():
			if String(ids[j]) == mid:
				stage_i = j
			j += 1
		_Stage.reset_progress()
		app.start_fight("stage", mid, stage_i)
		await SimReplay.sync_physics(app)
		print("HH_DIAG start map=%s bots=%d" % [mid, app.session.live_bot_count() if app.session != null else -1])
		var row: Dictionary = await StageCasesScript._catalog_resolve(app, "win")
		print("HH_DIAG win %s %s" % [mid, str(row)])
		if not bool(row.get("ok", false)):
			fails.append("win %s %s" % [mid, str(row)])
		i += 1
	_Stage.reset_progress()
	app.start_fight("stage", "rooftops", 0)
	await SimReplay.sync_physics(app)
	var loss: Dictionary = await StageCasesScript._catalog_resolve(app, "lose")
	print("HH_DIAG lose rooftops %s" % str(loss))
	if not bool(loss.get("ok", false)):
		fails.append("lose rooftops %s" % str(loss))
	if fails.is_empty():
		print("PASS: diag stage hunt")
		quit(0)
	else:
		print("FAIL: diag stage hunt")
		i = 0
		while i < fails.size():
			print("  - %s" % String(fails[i]))
			i += 1
		quit(1)

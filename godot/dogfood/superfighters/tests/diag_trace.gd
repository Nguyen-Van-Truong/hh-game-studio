extends SceneTree

## Diagnostic only — rooftops live pose/path.

const BotCasesScript: GDScript = preload("res://tests/bot_cases.gd")


func _initialize() -> void:
	call_deferred("_boot")


func _boot() -> void:
	InputActions.install()
	var packed: PackedScene = load("res://scenes/main.tscn") as PackedScene
	var app: App = packed.instantiate() as App
	app.test_driven = true
	root.add_child(app)
	app.start_fight("vs1", "rooftops", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var bot: Fighter = BotCasesScript._first_bot(session)
	var foe: Fighter = BotCasesScript._nearest_other(session, bot)
	BotCasesScript._lock_named(session, bot, foe)
	var doc: Dictionary = MapCatalog.document("rooftops")
	var planned: Dictionary = BotNav.path_to(doc, bot.global_position, foe.global_position, 64)
	print("HH_TRACE start bot=%.0f,%.0f foe=%.0f,%.0f path_ok=%s cells=%s" % [
		bot.global_position.x,
		bot.global_position.y,
		foe.global_position.x,
		foe.global_position.y,
		str(planned.get("ok", false)),
		_cells(planned.get("cells", []) as Array),
	])
	var left: int = 520
	var tick: int = 0
	while left > 0:
		BotCasesScript._think_bots(session, 20)
		tick += 20
		left -= 20
		session = app.session
		bot = BotCasesScript._first_bot(session)
		foe = BotCasesScript._nearest_other(session, bot)
		if bot == null:
			break
		var br: BotBrain = null
		var i: int = 0
		while i < session.fighters.size():
			if session.fighters[i] == bot and i < session.brains.size():
				br = session.brains[i]
				break
			i += 1
		var here: Vector2i = MapGraph.stand_cell(doc, bot.global_position)
		var nxt: String = "-"
		if br != null and br.path_cells.size() > 0:
			var c: Vector2i = br.path_cells[mini(br.path_i, br.path_cells.size() - 1)] as Vector2i
			nxt = "%d,%d" % [c.x, c.y]
		print(
			"HH_TRACE t=%d pos=%.0f,%.0f cell=%d,%d foe=%.0f,%.0f d=%.0f ladder=%s climb=%s floor=%s intent=%s nxt=%s pitb=%s pits=%s gun=%d"
			% [
				tick,
				bot.global_position.x,
				bot.global_position.y,
				here.x,
				here.y,
				foe.global_position.x if foe != null else -1.0,
				foe.global_position.y if foe != null else -1.0,
				bot.global_position.distance_to(foe.global_position) if foe != null else -1.0,
				str(bot.on_ladder),
				str(bot.climbing),
				str(bot.is_on_floor()),
				br.intent if br != null else "",
				nxt,
				str(br.pit_blocks if br != null else 0),
				str(br.pit_reroutes if br != null else 0),
				bot.shots_fired,
			]
		)
	app.shutdown()
	app.queue_free()
	await process_frame
	quit(0)


func _cells(cells: Array) -> String:
	var bits: PackedStringArray = PackedStringArray()
	var i: int = 0
	while i < cells.size():
		var c: Vector2i = cells[i] as Vector2i
		bits.append("%d,%d" % [c.x, c.y])
		i += 1
	return ",".join(bits)

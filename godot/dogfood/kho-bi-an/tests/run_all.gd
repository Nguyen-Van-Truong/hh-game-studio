extends SceneTree

const STEP: float = 1.0 / 60.0
const ARRIVE: float = 8.0
const PATH: String = "start→key→door→relic→win"

var _fails: PackedStringArray = PackedStringArray()
var _loop: String = "unproven"
var _save: String = "unproven"
var _win_flag: String = "unproven"
var _no_err: String = "unproven"


func _initialize() -> void:
	call_deferred("_boot")


func _boot() -> void:
	seed(1)
	InputActions.install()
	var saver: Node = root.get_node_or_null("SaveService")
	if saver != null:
		saver.call("use_test_path")
		saver.call("clear_slot")
	var app: App = _make_app()
	_test_input_binds()
	_test_critical_path(app)
	_test_save_load(app)
	_test_win_flag_exclusive(app)
	_test_warden_lose_restart(app)
	_test_continue_after_relic(app)
	_test_foreign_schema(app)
	if saver != null:
		saver.call("clear_slot")
		saver.call("use_default_path")
	if _fails.is_empty():
		_no_err = "proven"
	_emit()
	quit(0 if _fails.is_empty() else 1)


func _make_app() -> App:
	var packed: PackedScene = load("res://scenes/main.tscn") as PackedScene
	var app: App = packed.instantiate() as App
	app.test_driven = true
	root.add_child(app)
	return app


func _test_input_binds() -> void:
	var actions: PackedStringArray = PackedStringArray([
		"move_left", "move_right", "move_up", "move_down", "interact", "pause"
	])
	var i: int = 0
	while i < actions.size():
		var action: String = String(actions[i])
		if not InputMap.has_action(action):
			_fail("missing InputMap action %s" % action)
		elif not InputActions.has_keyboard_and_gamepad(action):
			_fail("action %s missing keyboard+gamepad" % action)
		i += 1
	var buses: PackedStringArray = PackedStringArray(["Master", "Music", "SFX"])
	var b: int = 0
	while b < buses.size():
		if AudioServer.get_bus_index(String(buses[b])) < 0:
			_fail("missing audio bus %s" % String(buses[b]))
		b += 1


func _test_critical_path(app: App) -> void:
	app.start_new_run()
	var session: GameSession = app.session
	if session == null:
		_fail("LOOP missing session")
		return
	var layer: TileMapLayer = session.world.get_node_or_null("VaultRooms") as TileMapLayer
	if layer == null:
		_fail("LOOP overworld missing TileMapLayer VaultRooms")
	elif layer.tile_set == null:
		_fail("LOOP VaultRooms missing TileSet")
	else:
		var atlas_src: TileSetSource = layer.tile_set.get_source(0)
		var atlas: TileSetAtlasSource = atlas_src as TileSetAtlasSource
		if atlas == null or atlas.texture == null:
			_fail("LOOP VaultRooms missing atlas texture")
		elif atlas.texture.resource_path != "res://assets/tiles/tileset_vault.png":
			_fail("LOOP live TileMapLayer must use tileset_vault.png")
	if VaultMap.room_id_at(VaultMap.tile_center(VaultMap.DOOR_CELL)) == "relic":
		_fail("LOOP door tile must not be room_id relic")
	if VaultMap.room_id_at(VaultMap.tile_center(VaultMap.RELIC_CELL)) != "relic":
		_fail("LOOP relic cell must be room_id relic")
	var snap0: Dictionary = session.snapshot()
	if bool(snap0.get("win", false)) or bool(snap0.get("has_key", false)):
		_fail("LOOP start is not a clean run")
	if str(snap0.get("room_id", "")) != "start":
		_fail("LOOP start room_id must be start")
	_fail_close_relic_before_key(session)
	if not _walk_to(session, VaultMap.tile_center(VaultMap.KEY_CELL)):
		_fail(
			"LOOP cannot reach key at %s from %s"
			% [VaultMap.tile_center(VaultMap.KEY_CELL), session.player.global_position]
		)
		return
	_interact(session)
	var after_key: Dictionary = session.snapshot()
	if not bool(after_key.get("has_key", false)):
		_fail("LOOP key pickup failed kind=%s pos=%s" % [_debug_near(session), session.player.global_position])
	if bool(after_key.get("win", false)) or session.state.outcome == "win":
		_fail("LOOP key pickup must not win")
	if not _walk_to(session, VaultMap.tile_center(VaultMap.DOOR_CELL)):
		_fail("LOOP cannot reach door")
		return
	_interact(session)
	var after_door: Dictionary = session.snapshot()
	if not bool(after_door.get("door_open", false)):
		_fail("LOOP door open failed")
	if bool(after_door.get("win", false)) or session.state.outcome == "win":
		_fail("LOOP door-open must not win")
	if VaultMap.is_relic_room(str(after_door.get("room_id", ""))):
		_fail("LOOP door-open must stay start-side, not relic room")
	if not _walk_to(session, VaultMap.tile_center(VaultMap.RELIC_CELL)):
		_fail("LOOP cannot reach relic")
		return
	_interact(session)
	var after_relic: Dictionary = session.snapshot()
	if not bool(after_relic.get("relic_reached", false)):
		_fail("LOOP relic-reached flag missing")
	if not bool(after_relic.get("win", false)):
		_fail("LOOP relic-reached must be win")
	if session.state.outcome != "win":
		_fail("LOOP outcome is not win")
	if not VaultMap.is_relic_room(str(after_relic.get("room_id", ""))):
		_fail("LOOP win must be in relic room")
	if not app.win_screen.visible:
		_fail("LOOP win screen not shown")
	if _count_prefix("LOOP ") == 0:
		_loop = "proven"


func _fail_close_relic_before_key(session: GameSession) -> void:
	var reached: bool = _walk_to(session, VaultMap.tile_center(VaultMap.RELIC_CELL))
	var snap: Dictionary = session.snapshot()
	if reached or VaultMap.is_relic_room(str(snap.get("room_id", ""))):
		_fail("LOOP reached relic with door closed")
	if bool(snap.get("relic_reached", false)) or bool(snap.get("win", false)):
		_fail("LOOP relic approach with door closed must not win")
	_interact(session)
	var after: Dictionary = session.snapshot()
	if bool(after.get("relic_reached", false)) or bool(after.get("win", false)):
		_fail("LOOP interact at closed door must not set relic_reached")
	if bool(after.get("has_key", false)) or bool(after.get("door_open", false)):
		_fail("LOOP fail-close must not grant key or door")


func _test_save_load(app: App) -> void:
	var saver: Node = root.get_node_or_null("SaveService")
	if saver == null:
		_fail("SAVE_LOAD missing SaveService")
		return
	app.start_new_run()
	var session: GameSession = app.session
	if not _walk_to(session, VaultMap.tile_center(VaultMap.KEY_CELL)):
		_fail("SAVE_LOAD cannot reach key")
		return
	_interact(session)
	if not _walk_to(session, VaultMap.tile_center(VaultMap.DOOR_CELL)):
		_fail("SAVE_LOAD cannot reach door")
		return
	_interact(session)
	if not bool(session.snapshot().get("door_open", false)):
		_fail("SAVE_LOAD door open failed")
		return
	if not _walk_to(session, VaultMap.tile_center(Vector2i(VaultMap.DOOR_CELL.x, VaultMap.PLAYER_SPAWN.y))):
		_fail("SAVE_LOAD cannot step south of door")
		return
	if not _walk_to(session, VaultMap.tile_center(VaultMap.PLAYER_SPAWN)):
		_fail("SAVE_LOAD cannot return to start-side room")
		return
	if str(session.snapshot().get("room_id", "")) != "start":
		_fail("SAVE_LOAD persist room_id must be start, got %s" % str(session.snapshot().get("room_id", "")))
	saver.call("autosave", session.state)
	var written: Dictionary = saver.call("load_slot") as Dictionary
	if not bool(written.get("has_key", false)) or not bool(written.get("door_open", false)):
		_fail("SAVE_LOAD did not persist key/door")
	if bool(written.get("relic_reached", false)):
		_fail("SAVE_LOAD door-open must not persist win")
	if str(written.get("room_id", "")) != "start":
		_fail("SAVE_LOAD persisted room_id must be start")
	app.continue_run()
	var restored: Dictionary = app.session.snapshot()
	if not bool(restored.get("has_key", false)) or not bool(restored.get("door_open", false)):
		_fail("SAVE_LOAD continue did not restore flags")
	if bool(restored.get("win", false)) or bool(restored.get("relic_reached", false)):
		_fail("SAVE_LOAD restored unfinished run must not be win")
	if str(restored.get("room_id", "")) != "start":
		_fail("SAVE_LOAD continue room_id must be start, got %s" % str(restored.get("room_id", "")))
	if VaultMap.is_relic_room(str(restored.get("room_id", ""))):
		_fail("SAVE_LOAD must not teleport into relic after door-open-in-start")
	if VaultMap.room_id_at(app.session.player.global_position) == "relic":
		_fail("SAVE_LOAD player must not spawn in relic room")
	if not _walk_to(app.session, VaultMap.tile_center(VaultMap.RELIC_CELL)):
		_fail("SAVE_LOAD cannot finish path to relic after load")
		return
	_interact(app.session)
	var finished: Dictionary = app.session.snapshot()
	if not bool(finished.get("has_key", false)) or not bool(finished.get("door_open", false)):
		_fail("SAVE_LOAD finish lost key/door flags")
	if not bool(finished.get("relic_reached", false)) or not bool(finished.get("win", false)):
		_fail("SAVE_LOAD must walk to relic and win after load")
	if not VaultMap.is_relic_room(str(finished.get("room_id", ""))):
		_fail("SAVE_LOAD win room_id must be relic")
	if app.session.state.outcome != "win":
		_fail("SAVE_LOAD finish outcome is not win")
	if _count_prefix("SAVE_LOAD ") == 0:
		_save = "proven"


func _test_win_flag_exclusive(app: App) -> void:
	app.start_new_run()
	var session: GameSession = app.session
	session.state.has_key = true
	session.inventory.add("key")
	session.state.door_open = true
	if session.state.is_win() or session.state.relic_reached or session.state.outcome == "win":
		_fail("WIN_FLAG key+door without relic interact must not be win")
	if app.win_screen.visible:
		_fail("WIN_FLAG key+door must not show win screen")
	session.state.door_open = false
	session.player.global_position = VaultMap.tile_center(VaultMap.RELIC_CELL)
	_interact(session)
	if session.state.relic_reached or session.state.is_win() or session.state.outcome == "win":
		_fail("WIN_FLAG relic interact with door closed must not win")
	if app.win_screen.visible:
		_fail("WIN_FLAG closed-door relic interact must not show win screen")
	session.state.door_open = true
	session.state.has_key = true
	session.player.global_position = VaultMap.tile_center(VaultMap.RELIC_CELL)
	_interact(session)
	if not session.state.relic_reached or not session.state.is_win():
		_fail("WIN_FLAG relic interact after door_open must win")
	if session.state.outcome != "win":
		_fail("WIN_FLAG outcome must be win after relic interact")
	if not app.win_screen.visible:
		_fail("WIN_FLAG win screen not shown after relic interact")
	if _count_prefix("WIN_FLAG ") == 0:
		_win_flag = "proven"


func _test_warden_lose_restart(app: App) -> void:
	app.start_new_run()
	var session: GameSession = app.session
	if VaultMap.WARDEN_A.y < VaultMap.OPENING_Y0 or VaultMap.WARDEN_B.y < VaultMap.OPENING_Y0:
		_fail("warden patrol must be on the vault floor, not off-path")
	if not _chase_warden(session):
		_fail("lose path cannot reach warden")
		return
	if session.state.outcome != "lose":
		_fail("warden contact must be lose")
	if session.state.is_win():
		_fail("lose must not set win")
	if not app.lose_screen.visible:
		_fail("lose screen not shown")
	app.start_new_run()
	var fresh: Dictionary = app.session.snapshot()
	if bool(fresh.get("has_key", false)) or fresh["outcome"] != "play":
		_fail("Restart did not start a new run")


func _test_continue_after_relic(app: App) -> void:
	var saver: Node = root.get_node_or_null("SaveService")
	if saver == null:
		return
	var data: Dictionary = {
		"schema": 1,
		"room_id": "relic",
		"has_key": true,
		"door_open": true,
		"relic_reached": true,
	}
	saver.call("write_slot", data)
	app.continue_run()
	var snap: Dictionary = app.session.snapshot()
	if bool(snap.get("relic_reached", false)) or bool(snap.get("has_key", false)):
		_fail("Continue after relic must start a new run")


func _test_foreign_schema(app: App) -> void:
	var saver: Node = root.get_node_or_null("SaveService")
	if saver == null:
		return
	saver.call("write_foreign_schema")
	var loaded: Dictionary = saver.call("load_slot") as Dictionary
	if not loaded.is_empty():
		_fail("foreign schema must start new (empty load)")
	app.continue_run()
	var snap: Dictionary = app.session.snapshot()
	if bool(snap.get("has_key", false)):
		_fail("foreign schema continue must be a new run")


func _debug_near(session: GameSession) -> String:
	var key: Node2D = session.world.get_node_or_null("Key") as Node2D
	if key == null:
		return "no-key-node"
	return "key_dist=%.1f visible=%s" % [
		session.player.global_position.distance_to(key.global_position),
		key.visible
	]


func _interact(session: GameSession) -> void:
	var i: int = 0
	while i < 4:
		session.step_fixed(STEP, Vector2.ZERO, true)
		i += 1


func _chase_warden(session: GameSession) -> bool:
	var frames: int = 0
	while frames < 900:
		if session.state.outcome == "lose":
			return true
		var target: Vector2 = session.warden.global_position
		if session.player.global_position.distance_to(target) <= VaultMap.WARDEN_TOUCH:
			session.step_fixed(STEP, Vector2.ZERO, false)
			return session.state.outcome == "lose"
		session.step_fixed(STEP, target - session.player.global_position, false)
		frames += 1
	return session.state.outcome == "lose"


func _walk_to(session: GameSession, target: Vector2) -> bool:
	var frames: int = 0
	while frames < 720:
		var here: Vector2 = session.player.global_position
		if here.distance_to(target) <= ARRIVE:
			return true
		var delta: Vector2 = target - here
		session.step_fixed(STEP, delta, false)
		if session.player.global_position.distance_to(here) < 0.05 and frames > 8:
			return here.distance_to(target) <= VaultMap.INTERACT_REACH
		frames += 1
	return session.player.global_position.distance_to(target) <= VaultMap.INTERACT_REACH


func _fail(msg: String) -> void:
	_fails.append(msg)
	print("HH_ASSERT_FAIL %s" % msg)


func _count_prefix(prefix: String) -> int:
	var n: int = 0
	var i: int = 0
	while i < _fails.size():
		if String(_fails[i]).begins_with(prefix):
			n += 1
		i += 1
	return n


func _emit() -> void:
	print("HH_R8WP2_PATH %s" % PATH)
	print("HH_R8WP2_PATH_ASCII start->key->door->relic->win")
	print(
		"HH_R8WP2 LOOP=%s SAVE_LOAD=%s NO_ERRORS=%s WIN_FLAG=%s"
		% [_loop, _save, _no_err, _win_flag]
	)
	if _fails.is_empty():
		print("PASS: R8-WP2 graybox start→key→door→relic→win")
	else:
		print("FAIL: R8-WP2 graybox")
		var i: int = 0
		while i < _fails.size():
			print("  - %s" % String(_fails[i]))
			i += 1

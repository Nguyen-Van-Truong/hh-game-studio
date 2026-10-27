extends SceneTree
## SA-04 provisional integration checks. These exercise the live match scene,
## real Input.parse_input_event edges, pickup/result postconditions, and the
## deterministic bot scene. They are implementation evidence, not Y8 parity.

const MATCH_SCENE: String = "res://game/ui/match_room.tscn"
const BOT_SCENE: String = "res://game/ui/match_room_bot.tscn"

var _failures: int = 0
var _assertions: int = 0
var _finished: bool = false

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	create_timer(30.0).timeout.connect(_on_timeout)
	change_scene_to_file(MATCH_SCENE)
	_expect(await _await_scene_name(&"MatchRoom"), "classic match scene must load")
	var room: MatchRoom = current_scene as MatchRoom
	_expect(room != null, "classic scene root must be MatchRoom")
	if room == null:
		_finish()
		return
	var initial: Dictionary = room.read_snapshot()
	_expect(initial.get(&"schema", &"") == &"sa05.match.v1", "match snapshot exposes SA-05 schema")
	_expect(initial.get(&"phase", &"") == &"playing", "match begins in playing phase")
	_expect(initial.get(&"opponent", &"") == &"two_player", "V scene uses local two-player opponent")
	var world: Dictionary = initial.get(&"world", {})
	_expect(world.get(&"layout_path", &"") == "res://data/relay_yard.json", "match uses the original greybox map path")
	_expect(_array_size(world, &"pickups") == 7, "relay yard exposes seven authored pickups")
	_expect(_array_size(initial, &"fighters") == 2, "match snapshot exposes two fighters")
	var tick_before_null: int = int(room.read_snapshot().get(&"tick", -1))
	_expect(not room.simulation.step(null), "null match input fails closed without advancing")
	_expect(int(room.read_snapshot().get(&"tick", -1)) == tick_before_null, "rejected null input leaves the fixed tick unchanged")
	var initial_pickups: Variant = initial.get(&"pickups", [])
	_expect(typeof(initial_pickups) == TYPE_ARRAY and Array(initial_pickups).is_read_only(), "pickup snapshot array is immutable")
	if typeof(initial_pickups) == TYPE_ARRAY and not Array(initial_pickups).is_empty():
		_expect(Dictionary(Array(initial_pickups)[0]).is_read_only(), "pickup snapshot rows are immutable")

	var before_x: float = _fighter_x(initial, 0)
	_parse_key(KEY_D, true)
	var move_frame: InputFrame = await _sample_step(room, "p1-right-pressed")
	_expect(bool(_record_for(move_frame, &"p1_right", 1).get(&"pressed", false)), "P1 movement press reaches match room")
	_expect(bool(_record_for(move_frame, &"p1_right", 1).get(&"held", false)), "P1 movement held reaches match room")
	_expect(_fighter_x(room.read_snapshot(), 0) != before_x, "P1 movement changes live match state")
	_parse_key(KEY_D, false)
	var release_frame: InputFrame = await _sample_step(room, "p1-right-released")
	_expect(bool(_record_for(release_frame, &"p1_right", 1).get(&"released", false)), "P1 release edge reaches match room")

	# Place fighters beside a pickup through the explicit fixture operation, then
	# advance through the real room tick/input path to observe collection.
	room.simulation.place_fighter(0, Vector2(1130.0, 740.0))
	room.simulation.place_fighter(1, Vector2(1400.0, 740.0))
	var pickup_before: Dictionary = room.read_snapshot()
	var shotgun_before: String = String(_fighter_row(pickup_before, 0).get(&"gun_id", &""))
	_expect(shotgun_before == "pistol", "P1 starts with the pistol")
	_parse_key(KEY_S, true)
	_parse_key(KEY_J, true)
	var pickup_frame: InputFrame = await _sample_step(room, "shotgun-pickup")
	_expect(pickup_frame != null, "pickup tick completes through the fixed-step room")
	_parse_key(KEY_S, false)
	_parse_key(KEY_J, false)
	var pickup_after: Dictionary = room.read_snapshot()
	_expect(String(_fighter_row(pickup_after, 0).get(&"gun_id", &"")) == "shotgun", "P1 collects the shotgun pickup")
	_expect(int(_fighter_row(pickup_after, 0).get(&"ammo", 0)) == 4, "shotgun pickup grants its authored ammo")
	_expect(not bool(_pickup_row(pickup_after, "yard_shotgun_east").get(&"active", true)), "collected pickup is inactive in the match snapshot")
	var world_after_pickup: Dictionary = pickup_after.get(&"world", {})
	_expect(not bool(_pickup_row(world_after_pickup, "yard_shotgun_east").get(&"active", true)), "world pickup view stays synchronized after collection")

	# Verify a live action event and result postcondition with a deterministic
	# fixture placement; the action itself still arrives via InputBuffer.
	room.simulation.place_fighter(0, Vector2(600.0, 740.0))
	room.simulation.place_fighter(1, Vector2(660.0, 740.0))
	room.simulation.fighters[1].health = 1
	var ammo_before_fire: int = int(_fighter_row(room.read_snapshot(), 0).get(&"ammo", 0))
	_parse_key(KEY_K, true)
	var aim_frame: InputFrame = await _sample_step(room, "p1-aim")
	_expect(bool(_record_for(aim_frame, &"p1_shoot", 1).get(&"pressed", false)), "P1 fire press reaches match room")
	_expect(bool(_fighter_row(room.read_snapshot(), 0).get(&"aiming", false)), "P1 held fire exposes aiming state")
	_expect(int(_fighter_row(room.read_snapshot(), 0).get(&"ammo", 0)) == ammo_before_fire, "aiming leaves ammunition unchanged")
	var aim_y_before: float = float(_fighter_row(room.read_snapshot(), 0).get(&"y", 0.0))
	_parse_key(KEY_W, true)
	var angle_frame: InputFrame = await _sample_step(room, "p1-aim-up")
	_expect(bool(_record_for(angle_frame, &"p1_up", 1).get(&"held", false)), "P1 aim direction reaches match room")
	_expect(absf(float(_fighter_row(room.read_snapshot(), 0).get(&"y", 0.0)) - aim_y_before) < 0.1, "aim direction does not jump while firing")
	_expect(absf(float(_fighter_row(room.read_snapshot(), 0).get(&"aim_angle", 0.0))) > 0.0, "aim direction changes the canonical angle")
	_parse_key(KEY_W, false)
	await _sample_step(room, "p1-aim-up-released")
	_parse_key(KEY_K, false)
	var fire_frame: InputFrame = await _sample_step(room, "p1-fire-release")
	_expect(bool(_record_for(fire_frame, &"p1_shoot", 1).get(&"released", false)), "P1 release reaches match room")
	_expect(await _await_phase(room, &"result"), "lethal fire reaches result phase")
	var result_snapshot: Dictionary = room.read_snapshot()
	_expect(int(result_snapshot.get(&"winner", 0)) == 1, "result records P1 winner")
	_expect(_array_size(result_snapshot, &"shot_events") > 0, "result retains shot event evidence")

	_parse_key(KEY_R, true)
	_parse_key(KEY_R, false)
	var replay_snapshot: Dictionary = room.read_snapshot()
	_expect(replay_snapshot.get(&"phase", &"") == &"playing", "R rematches from the result overlay")
	_expect(int(replay_snapshot.get(&"tick", -1)) == 0, "rematch resets the fixed tick before new play advances")
	await _sample_step(room, "first-rematch-tick")
	_expect(int(room.read_snapshot().get(&"tick", -1)) == 1, "first rematch simulation step advances exactly once")

	# Bot scene is a separate route so B cannot silently fall back to local 2P.
	change_scene_to_file(BOT_SCENE)
	_expect(await _await_scene_name(&"MatchRoom"), "bot match scene must load")
	var bot_room: MatchRoom = current_scene as MatchRoom
	_expect(bot_room != null, "bot scene root must be MatchRoom")
	if bot_room != null:
		_expect(bot_room.opponent == &"bot", "B route configures the deterministic classic bot")
		for _tick: int in range(12):
			await bot_room.fixed_step_completed
		_expect(int(bot_room.read_snapshot().get(&"tick", 0)) >= 12, "bot scene advances fixed ticks")
		_expect(String(bot_room.read_snapshot().get(&"schema", &"")) == "sa05.match.v1", "bot scene keeps match schema")

	_finish()

func _on_timeout() -> void:
	if _finished:
		return
	_finished = true
	printerr("SA-04 match room FAIL: watchdog; %d of %d assertions" % [_failures + 1, _assertions])
	quit(1)

func _finish() -> void:
	if _finished:
		return
	_finished = true
	if _failures == 0:
		print("SA-04 match room PASS: %d assertions; live scene/input/pickup/result/replay/bot" % _assertions)
	else:
		printerr("SA-04 match room FAIL: %d of %d assertions" % [_failures, _assertions])
	quit(0 if _failures == 0 else 1)

func _expect(condition: bool, message: String) -> void:
	_assertions += 1
	if not condition:
		_failures += 1
		printerr("ASSERT: " + message)

func _await_scene_name(expected: StringName) -> bool:
	for _attempt: int in range(180):
		if current_scene != null and StringName(current_scene.name) == expected:
			return true
		await process_frame
	return false

func _await_phase(room: MatchRoom, expected: StringName) -> bool:
	for _attempt: int in range(30):
		if StringName(room.read_snapshot().get(&"phase", &"")) == expected:
			return true
		await process_frame
	return false

func _sample_step(room: MatchRoom, _label: String) -> InputFrame:
	var frame: InputFrame = await room.fixed_step_completed
	_expect(frame != null, "%s must produce a typed fixed-step frame" % _label)
	return frame

func _parse_key(code: int, is_down: bool) -> void:
	var event := InputEventKey.new()
	event.keycode = code
	event.physical_keycode = 0
	event.pressed = is_down
	event.echo = false
	Input.parse_input_event(event)
	# Synthetic events are buffered until the render boundary by default. Flush
	# through Godot's real input dispatch before awaiting the next physics tick;
	# otherwise catch-up physics ticks can race the release event on slow frames.
	Input.flush_buffered_events()

func _record_for(frame: InputFrame, action: StringName, player: int) -> Dictionary:
	if frame == null:
		return {}
	for record: Dictionary in frame.records():
		if record.get(&"action") == action and int(record.get(&"player", 0)) == player:
			return record
	return {}

func _array_size(container: Dictionary, key: StringName) -> int:
	var value: Variant = container.get(key, [])
	return Array(value).size() if typeof(value) == TYPE_ARRAY else 0

func _fighter_row(snapshot: Dictionary, index: int) -> Dictionary:
	var value: Variant = snapshot.get(&"fighters", [])
	if typeof(value) != TYPE_ARRAY or index < 0 or index >= Array(value).size():
		return {}
	return Dictionary(Array(value)[index])

func _fighter_x(snapshot: Dictionary, index: int) -> float:
	return float(_fighter_row(snapshot, index).get(&"x", 0.0))

func _pickup_row(snapshot: Dictionary, pickup_id: String) -> Dictionary:
	var value: Variant = snapshot.get(&"pickups", [])
	if typeof(value) != TYPE_ARRAY:
		return {}
	for row_value: Variant in Array(value):
		if typeof(row_value) != TYPE_DICTIONARY:
			continue
		var row: Dictionary = row_value
		if String(row.get(&"id", &"")) == pickup_id:
			return row
	return {}

extends SceneTree
## Focused BotController slice checks.  This file stays independent from the
## full MatchSession run and uses only snapshot dictionaries.

const BOT_SCRIPT = preload("res://game/ai/bot_controller.gd")
const INPUT_FRAME_SCRIPT = preload("res://game/core/input_frame.gd")

var _failures: int = 0
var _assertions: int = 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	_test_approach_and_jump()
	_test_ladder_and_pickup()
	_test_combat_choice_and_frame_edges()
	_test_malformed_state_fails_closed()
	if _failures == 0:
		print("BotController slice PASS: %d assertions" % _assertions)
	else:
		printerr("BotController slice FAIL: %d of %d assertions" % [_failures, _assertions])
	quit(0 if _failures == 0 else 1)

func _test_approach_and_jump() -> void:
	var bot: RefCounted = BOT_SCRIPT.new(17, 2)
	var state: Dictionary = _snapshot(0, {&"x": 100.0, &"y": 400.0, &"grounded": true}, {&"x": 250.0, &"y": 400.0})
	var intents: Dictionary = Dictionary(bot.call("desired_actions", state))
	_expect(bool(intents[&"p2_right"]), "bot approaches an aligned enemy")
	_expect(not bool(intents[&"p2_left"]), "approach does not steer away")

	state = _snapshot(1, {&"x": 100.0, &"y": 400.0, &"grounded": true}, {&"x": 250.0, &"y": 250.0})
	intents = Dictionary(bot.call("desired_actions", state))
	_expect(bool(intents[&"p2_up"]), "bot jumps when no ladder reaches the target")

func _test_ladder_and_pickup() -> void:
	var bot: RefCounted = BOT_SCRIPT.new(17, 2)
	var state: Dictionary = _snapshot(2, {&"x": 100.0, &"y": 300.0, &"grounded": true}, {&"x": 300.0, &"y": 100.0})
	var world: Dictionary = state[&"world"]
	world[&"ladders"] = [{&"x": 180.0, &"top": 100.0, &"bottom": 300.0}]
	var intents: Dictionary = Dictionary(bot.call("desired_actions", state))
	_expect(bool(intents[&"p2_right"]), "bot approaches a usable ladder")

	state = _snapshot(3, {&"x": 180.0, &"y": 300.0, &"grounded": true}, {&"x": 300.0, &"y": 100.0})
	state[&"world"] = world
	intents = Dictionary(bot.call("desired_actions", state))
	_expect(bool(intents[&"p2_up"]), "bot climbs toward a higher target")

	state = _snapshot(4, {&"x": 180.0, &"y": 300.0, &"grounded": true, &"health": 50}, {&"x": 300.0, &"y": 300.0})
	state[&"pickups"] = [{&"kind": &"medkit", &"x": 180.0, &"y": 300.0, &"active": true}]
	intents = Dictionary(bot.call("desired_actions", state))
	_expect(bool(intents[&"p2_down"]), "bot enters pickup interaction range")
	_expect(bool(intents[&"p2_punch"]), "pickup uses the semantic interaction press")

func _test_combat_choice_and_frame_edges() -> void:
	var first: RefCounted = BOT_SCRIPT.new(17, 2)
	var second: RefCounted = BOT_SCRIPT.new(17, 2)
	var state: Dictionary = _snapshot(5, {&"x": 100.0, &"y": 300.0, &"grounded": true, &"ammo": 6, &"grenades": 3, &"gun_id": &"pistol"}, {&"x": 280.0, &"y": 300.0})
	var first_intents: Dictionary = Dictionary(first.call("desired_actions", state))
	var second_intents: Dictionary = Dictionary(second.call("desired_actions", state))
	_expect(first_intents == second_intents, "same seed and snapshot produce the same attack intent")
	_expect(bool(first_intents[&"p2_shoot"]) or bool(first_intents[&"p2_throw"]), "mid-range combat chooses shoot or throw")

	var frame_value: Variant = first.call("build_frame", state)
	var frame: InputFrame = null
	if frame_value is InputFrame:
		frame = frame_value
	_expect(frame != null, "valid state builds an InputFrame")
	if frame != null:
		var record: Dictionary = _record_for(frame, &"p2_shoot", 2)
		var throw_record: Dictionary = _record_for(frame, &"p2_throw", 2)
		_expect(bool(record[&"pressed"]) or bool(throw_record[&"pressed"]), "chosen attack has an input edge")
	var idle_state: Dictionary = _snapshot(6, {&"x": 100.0, &"y": 300.0, &"grounded": true, &"health": 0}, {&"x": 280.0, &"y": 300.0})
	var release_value: Variant = first.call("build_frame", idle_state)
	var release_frame: InputFrame = null
	if release_value is InputFrame:
		release_frame = release_value
	_expect(release_frame != null, "valid defeated state still builds an idle frame")
	if release_frame != null and frame != null:
		var prior: Dictionary = _record_for(frame, &"p2_shoot", 2)
		var after: Dictionary = _record_for(release_frame, &"p2_shoot", 2)
		if bool(prior[&"held"]):
			_expect(bool(after[&"released"]), "idle transition releases a held shoot intent")

func _test_malformed_state_fails_closed() -> void:
	var bot: RefCounted = BOT_SCRIPT.new(1, 2)
	var malformed: Dictionary = {&"tick": "zero", &"fighters": []}
	var intents: Dictionary = Dictionary(bot.call("desired_actions", malformed))
	for action: StringName in INPUT_FRAME_SCRIPT.ACTIONS:
		_expect(not bool(intents[action]), "malformed state idles %s" % action)
	_expect(bot.call("build_frame", malformed) == null, "malformed state does not build a frame")

func _snapshot(tick: int, self_overrides: Dictionary, enemy_overrides: Dictionary) -> Dictionary:
	var self_row: Dictionary = {
		&"player_id": 2, &"x": 100.0, &"y": 300.0, &"health": 100,
		&"grounded": true, &"in_pit": false, &"ammo": 0, &"grenades": 0,
		&"gun_id": &"",
	}
	for key: Variant in self_overrides.keys():
		self_row[key] = self_overrides[key]
	var enemy_row: Dictionary = {
		&"player_id": 1, &"x": 260.0, &"y": 300.0, &"health": 100,
		&"grounded": true, &"in_pit": false, &"ammo": 0, &"grenades": 0,
		&"gun_id": &"",
	}
	for key: Variant in enemy_overrides.keys():
		enemy_row[key] = enemy_overrides[key]
	return {
		&"tick": tick,
		&"phase": &"playing",
		&"fighters": [self_row, enemy_row],
		&"pickups": [],
		&"world": {&"ladders": [], &"pits": [], &"solids": []},
	}

func _record_for(frame: InputFrame, action: StringName, player: int) -> Dictionary:
	for record: Dictionary in frame.records():
		if record[&"action"] == action and int(record[&"player"]) == player:
			return record
	return {}

func _expect(condition: bool, message: String) -> void:
	_assertions += 1
	if not condition:
		_failures += 1
		printerr("FAIL: %s" % message)

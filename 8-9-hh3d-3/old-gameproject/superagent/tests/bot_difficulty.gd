extends SceneTree

const BOT_SCRIPT = preload("res://game/ai/classic_bot.gd")
var assertions: int = 0

func _init() -> void:
	var easy: ClassicBot = BOT_SCRIPT.new(&"easy")
	var normal: ClassicBot = BOT_SCRIPT.new(&"normal")
	var hard: ClassicBot = BOT_SCRIPT.new(&"hard")
	_expect(easy.difficulty == &"easy" and normal.difficulty == &"normal" and hard.difficulty == &"hard", "all three difficulty names are accepted")
	_expect(easy.difficulty_profile().is_read_only() and normal.difficulty_profile().is_read_only(), "difficulty profiles are immutable")
	_expect(int(easy.difficulty_profile()[&"shoot_cooldown_ticks"]) > int(normal.difficulty_profile()[&"shoot_cooldown_ticks"]) and int(normal.difficulty_profile()[&"shoot_cooldown_ticks"]) > int(hard.difficulty_profile()[&"shoot_cooldown_ticks"]), "reaction cooldown orders easy to hard")
	_expect(float(easy.difficulty_profile()[&"pickup_range"]) < float(hard.difficulty_profile()[&"pickup_range"]), "hard bot has wider pickup approach tolerance")
	var invalid: ClassicBot = BOT_SCRIPT.new(&"unknown")
	_expect(invalid.difficulty == &"normal", "unknown difficulty fails closed to normal")
	var snapshot: Dictionary = {
		&"tick": 0, &"phase": &"playing",
		&"fighters": [
			{&"player_id": 1, &"x": 200.0, &"y": 740.0, &"health": 100, &"grounded": true, &"in_pit": false, &"ammo": 6, &"grenades": 3, &"gun_id": &"pistol", &"attack_cooldown_ticks": 0},
			{&"player_id": 2, &"x": 320.0, &"y": 740.0, &"health": 100, &"grounded": true, &"in_pit": false, &"ammo": 6, &"grenades": 3, &"gun_id": &"pistol", &"attack_cooldown_ticks": 0},
		],
		&"world": {&"pits": [], &"solids": [], &"ladders": [], &"floor_y": 740.0}, &"pickups": [],
	}
	for bot: ClassicBot in [easy, normal, hard]:
		var actions: Dictionary = bot.desired_actions(snapshot, 2)
		_expect(actions.has(&"p2_punch") and actions.has(&"p2_shoot") and actions.has(&"p2_right"), "difficulty emits the normal held action schema")
		_expect(bot.navigation_ready(), "difficulty bot builds a navigation graph from the live world snapshot")
	var nav_snapshot: Dictionary = snapshot.duplicate(true)
	nav_snapshot[&"tick"] = 1
	nav_snapshot[&"fighters"] = [
		{&"player_id": 1, &"x": 0.0, &"y": 740.0, &"health": 100, &"grounded": true, &"in_pit": false, &"ammo": 0, &"grenades": 0, &"gun_id": &"", &"attack_cooldown_ticks": 0},
		{&"player_id": 2, &"x": 110.0, &"y": 740.0, &"health": 100, &"grounded": true, &"in_pit": false, &"ammo": 0, &"grenades": 0, &"gun_id": &"", &"attack_cooldown_ticks": 0},
	]
	nav_snapshot[&"world"] = {
		&"platforms": [
			{&"id": &"left", &"left": 0.0, &"right": 80.0, &"y": 740.0},
			{&"id": &"right", &"left": 100.0, &"right": 150.0, &"y": 740.0},
		],
		&"pits": [{&"left": 80.0, &"right": 100.0}], &"ladders": [], &"solids": [], &"floor_y": 740.0,
	}
	var nav_bot: ClassicBot = BOT_SCRIPT.new(&"normal")
	var nav_actions: Dictionary = nav_bot.desired_actions(nav_snapshot, 2)
	_expect(nav_bot.navigation_ready(), "navigation graph accepts a disconnected platform fixture")
	_expect(bool(nav_actions.get(&"p2_left", false)) and bool(nav_actions.get(&"p2_up", false)), "disconnected platform triggers a deterministic jump replan")
	var malformed: Dictionary = nav_snapshot.duplicate(true)
	malformed[&"tick"] = 2
	malformed[&"world"] = &"malformed"
	var safe_actions: Dictionary = nav_bot.desired_actions(malformed, 2)
	_expect(safe_actions.has(&"p2_left") and safe_actions.has(&"p2_up"), "malformed world fails closed with the stable action schema")
	print("SA-08 bot difficulty PASS: %d assertions" % assertions)
	quit()

func _expect(condition: bool, message: String) -> void:
	assertions += 1
	if not condition:
		push_error("FAIL: " + message)
		quit(1)

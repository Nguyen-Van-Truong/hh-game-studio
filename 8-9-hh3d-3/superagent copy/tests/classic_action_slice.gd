extends SceneTree
## Clean-room Classic action slice: tackle/grab, contextual kick/combo and
## deterministic sky-drop weapons.  These are causal gameplay checks, not Y8
## parity measurements.

const TRACE = preload("res://tests/trace_core.gd")

var failures: int = 0
var assertions: int = 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	await _test_tackle_and_grab()
	await _test_grab_followups()
	await _test_combo_and_kick()
	await _test_airdrop_cycle()
	await _test_weapon_slots()
	if failures == 0:
		print("Classic action slice PASS: %d assertions; tackle/grab, combo/kick, sky-drop weapons" % assertions)
	else:
		printerr("Classic action slice FAIL: %d of %d assertions" % [failures, assertions])
	quit(0 if failures == 0 else 1)

func _test_tackle_and_grab() -> void:
	var session := MatchSession.new(501, &"two_player")
	get_root().add_child(session)
	await process_frame
	await physics_frame
	session.place_fighter(0, Vector2(700.0, session.world.floor_y), Vector2.ZERO, true)
	session.place_fighter(1, Vector2(740.0, session.world.floor_y), Vector2.ZERO, true)
	var held: Dictionary = {}
	_expect(await _step(session, 0, held, {&"p1_right": true}), "sprint tap one advances")
	held = {&"p1_right": true}
	_expect(await _step(session, 1, held, {}), "sprint neutral release advances")
	_expect(await _step(session, 2, {}, {&"p1_right": true}), "sprint tap two advances")
	_expect(session.fighters[0].sprint.direction != 0, "double tap arms sprint")
	held = {&"p1_right": true}
	_expect(await _step(session, 3, held, {&"p1_right": true, &"p1_down": true}), "sprint crouch tackle advances")
	_expect(session.fighters[0].action_name == &"tackle" or session.fighters[0].action_name == &"grab", "sprint plus crouch enters tackle/grab state")
	_expect(session.fighters[0].tackle_ticks > 0, "tackle keeps a bounded active window")
	_expect(session.fighters[1].grabbed_ticks > 0, "tackle collision grabs the opponent")
	_expect(session.fighters[1].last_hit_kind == &"tackle", "grab records tackle hit kind")
	_expect(session.fighters[0].hold_ticks > 0, "attacker holds the grabbed opponent briefly")
	session.queue_free()
	await process_frame

func _test_combo_and_kick() -> void:
	var session := MatchSession.new(502, &"two_player")
	get_root().add_child(session)
	await process_frame
	await physics_frame
	session.place_fighter(0, Vector2(700.0, session.world.floor_y), Vector2.ZERO, true)
	session.place_fighter(1, Vector2(748.0, session.world.floor_y), Vector2.ZERO, true)
	var held: Dictionary = {}
	_expect(await _step(session, 0, held, {&"p1_punch": true}), "combo first punch advances")
	_expect(session.fighters[0].attack_name == &"punch", "first melee is a punch")
	var first_health: int = session.fighters[1].health
	for tick_value: int in range(1, 9):
		await _step(session, tick_value, {}, {})
	_expect(await _step(session, 9, {}, {&"p1_punch": true}), "combo second punch advances")
	_expect(session.fighters[0].attack_name == &"punch_combo", "continuous melee advances to combo punch")
	_expect(session.fighters[1].health < first_health, "combo punch applies a second hit")
	for tick_value: int in range(10, 19):
		await _step(session, tick_value, {}, {})
	_expect(await _step(session, 19, {}, {&"p1_down": true, &"p1_punch": true}), "down punch kick advances")
	_expect(session.fighters[0].attack_name == &"kick", "down plus melee selects a kick")
	_expect(session.fighters[1].last_hit_kind == &"kick", "kick has its own hit kind")
	session.queue_free()
	await process_frame

func _test_grab_followups() -> void:
	var session := MatchSession.new(504, &"two_player")
	get_root().add_child(session)
	await process_frame
	await physics_frame
	session.place_fighter(0, Vector2(700.0, session.world.floor_y), Vector2.ZERO, true)
	session.place_fighter(1, Vector2(740.0, session.world.floor_y), Vector2.ZERO, true)
	var held: Dictionary = {}
	await _step(session, 0, held, {&"p1_right": true})
	held = {&"p1_right": true}
	await _step(session, 1, held, {})
	await _step(session, 2, {}, {&"p1_right": true})
	held = {&"p1_right": true}
	await _step(session, 3, held, {&"p1_right": true, &"p1_down": true})
	var health_before: int = session.fighters[1].health
	_expect(await _step(session, 4, {}, {&"p1_punch": true}), "grab punch input advances")
	_expect(session.fighters[0].attack_name == &"grab_punch", "held opponent accepts a punch follow-up")
	_expect(session.fighters[1].health < health_before and session.fighters[1].last_hit_kind == &"grab_punch", "grab punch damages and records its hit kind")
	session.queue_free()
	await process_frame

	var throw_session := MatchSession.new(505, &"two_player")
	get_root().add_child(throw_session)
	await process_frame
	await physics_frame
	throw_session.place_fighter(0, Vector2(700.0, throw_session.world.floor_y), Vector2.ZERO, true)
	throw_session.place_fighter(1, Vector2(740.0, throw_session.world.floor_y), Vector2.ZERO, true)
	await _step(throw_session, 0, {}, {&"p1_right": true})
	await _step(throw_session, 1, {&"p1_right": true}, {})
	await _step(throw_session, 2, {}, {&"p1_right": true})
	await _step(throw_session, 3, {&"p1_right": true}, {&"p1_right": true, &"p1_down": true})
	var thrown_health: int = throw_session.fighters[1].health
	_expect(await _step(throw_session, 4, {}, {&"p1_throw": true}), "grab throw input advances")
	_expect(throw_session.fighters[0].attack_name == &"grab_throw", "held opponent accepts a throw follow-up")
	_expect(throw_session.fighters[1].health < thrown_health and throw_session.fighters[1].last_hit_kind == &"grab_throw", "grab throw damages and releases the target")
	_expect(throw_session.fighters[1].grabbed_ticks == 0, "grab throw releases grabbed state")
	throw_session.queue_free()
	await process_frame

func _test_airdrop_cycle() -> void:
	var first := MatchSession.new(503, &"two_player")
	var twin := MatchSession.new(503, &"two_player")
	get_root().add_child(first)
	get_root().add_child(twin)
	await process_frame
	await physics_frame
	for tick_value: int in range(120):
		var frame_a := TRACE.build_frame(first.tick, {}, {})
		var frame_b := TRACE.build_frame(twin.tick, {}, {})
		_expect(await _step_frame(first, frame_a), "first sky-drop tick advances")
		_expect(await _step_frame(twin, frame_b), "twin sky-drop tick advances")
	_expect(first.snapshot_hash() == twin.snapshot_hash(), "sky-drop schedule is deterministic")
	var first_drop: Dictionary = _find_airdrop(first, 0)
	_expect(not first_drop.is_empty(), "first sky-drop row is authored")
	_expect(float(first_drop.get(&"y", 0.0)) < first.world.floor_y, "first sky-drop begins above the arena")
	_expect(float(first_drop.get(&"fall_speed", 99.0)) <= 4.0, "sky-drop descends slowly enough to read")
	var drop_x: float = float(first_drop.get(&"x", -1.0))
	_expect(not first.world.is_in_pit(drop_x - 24.0) and not first.world.is_in_pit(drop_x + 24.0), "sky-drop pickup radius clears pits")
	for tick_value: int in range(120, 380):
		await _step_frame(first, TRACE.build_frame(first.tick, {}, {}))
	var landed: Dictionary = _find_airdrop(first, 0)
	_expect(bool(landed.get(&"landed", false)), "sky-drop lands on a reachable surface")
	_expect(float(landed.get(&"target_y", first.world.floor_y)) <= first.world.floor_y, "sky-drop target is not below the arena")
	_expect(StringName(landed.get(&"kind", &"")) == &"shotgun", "first drop supplies a long gun")
	for tick_value: int in range(380, 1321):
		await _step_frame(first, TRACE.build_frame(first.tick, {}, {}))
	var crate_types: Dictionary = {}
	for row: Dictionary in first.pickup_rows:
		if bool(row.get(&"airdrop", false)):
			crate_types[String(row.get(&"crate_type", ""))] = true
	_expect(crate_types.has("firearm"), "sky-drop cycle includes a firearm crate")
	_expect(crate_types.has("melee"), "sky-drop cycle includes a melee crate")
	_expect(crate_types.has("explosive"), "sky-drop cycle includes a bomb crate")
	_expect(crate_types.has("power"), "sky-drop cycle includes a slow-time crate")
	first.queue_free()
	twin.queue_free()
	await process_frame

func _test_weapon_slots() -> void:
	var session := MatchSession.new(506, &"two_player")
	get_root().add_child(session)
	await process_frame
	await physics_frame
	session.melee_ids[0] = &"pipe"
	session.fighters[0].grenades = 2
	session.fighters[0].power_charges = 1
	var active_before: int = session.active_weapon_slots[0]
	_expect(active_before == 1, "firearm is the initial active inventory slot")
	var held: Dictionary = {}
	for expected_slot: int in [2, 3, 0, 1]:
		var desired := {&"p1_switch": true}
		_expect(await _step(session, session.tick, held, desired), "weapon switch input advances")
		_expect(session.active_weapon_slots[0] == expected_slot, "weapon switch cycles to slot %d" % expected_slot)
		held = desired
		_expect(await _step(session, session.tick, held, {}), "weapon switch release advances")
		held = {}
	var fighter_rows: Array = session.snapshot().get(&"fighters", [])
	var fighter_row: Dictionary = fighter_rows[0] if not fighter_rows.is_empty() and fighter_rows[0] is Dictionary else {}
	_expect(StringName(fighter_row.get(&"active_weapon_id", &"")) == &"pistol", "active firearm identity returns after cycling")
	session.queue_free()
	await process_frame

func _step(session: MatchSession, tick_value: int, held: Dictionary, desired: Dictionary) -> bool:
	return await _step_frame(session, TRACE.build_frame(tick_value, held, desired))

func _step_frame(session: MatchSession, frame: InputFrame) -> bool:
	await physics_frame
	return session.step(frame)

func _find_airdrop(session: MatchSession, serial: int) -> Dictionary:
	var wanted := StringName("airdrop_%03d" % serial)
	for row: Dictionary in session.pickup_rows:
		if StringName(row.get(&"id", &"")) == wanted:
			return row
	return {}

func _expect(condition: bool, message: String) -> void:
	assertions += 1
	if not condition:
		failures += 1
		printerr("FAIL: %s" % message)

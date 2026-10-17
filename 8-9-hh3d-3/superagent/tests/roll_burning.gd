extends SceneTree
## SA-06 focused behavior checks. These prove the authored roll and burning
## state transitions in Godot's CharacterBody2D path; they do not claim Y8
## parity or replace an owner/reference observation.

const TraceCore = preload("res://tests/trace_core.gd")

var failures: int = 0
var assertions: int = 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var session := MatchSession.new(71, &"two_player")
	var twin := MatchSession.new(71, &"two_player")
	get_root().add_child(session)
	get_root().add_child(twin)
	await process_frame
	await physics_frame
	await physics_frame
	for active: MatchSession in [session, twin]:
		active.place_fighter(0, Vector2(300.0, 740.0), Vector2.ZERO, true)
		active.place_fighter(1, Vector2(1400.0, 740.0), Vector2.ZERO, true)

	var roll_start := TraceCore.build_frame(0, {}, {&"p1_right": true, &"p1_down": true})
	_expect(session.step(roll_start), "roll start frame advances")
	_expect(twin.step(roll_start), "twin roll start frame advances")
	_expect(session.fighters[0].roll_ticks > 0, "down plus direction starts a roll")
	_expect(session.fighters[0].action_name == &"roll", "roll exposes its action state")
	_expect(session.fighters[0].position.x > 300.0, "roll moves through CharacterBody2D")
	_expect(session.fighters[0].snapshot().get(&"roll_low_posture", false), "roll snapshot records the short posture")
	_expect(session.snapshot_hash() == twin.snapshot_hash(), "identical roll traces have the same hash")
	var interrupted_x: float = session.fighters[0].position.x
	session.fighters[0].apply_hit(1, 12.0, false, &"test_interrupt", session.tuning)
	await physics_frame
	var interrupt_frame := TraceCore.build_frame(session.tick, {}, {})
	_expect(session.step(interrupt_frame), "roll interruption frame advances")
	_expect(session.fighters[0].position.x > interrupted_x, "roll interruption preserves knockback motion")
	_expect(session.fighters[0].roll_ticks == 0, "hit cancels the active roll")
	# Re-place before the duration check so the following assertions exercise a
	# clean full roll rather than the interrupted trace.
	session.place_fighter(0, Vector2(300.0, 740.0), Vector2.ZERO, true)
	session.fighters[0].hitstun_ticks = 0
	await physics_frame
	var clean_start := TraceCore.build_frame(session.tick, {}, {&"p1_right": true, &"p1_down": true})
	_expect(session.step(clean_start), "clean roll restart advances")

	for _tick: int in range(int(session.tuning[&"roll_duration_ticks"])):
		await physics_frame
		var held := TraceCore.build_frame(session.tick, {&"p1_right": true, &"p1_down": true}, {&"p1_right": true, &"p1_down": true})
		_expect(session.step(held), "held roll frame advances")
	_expect(session.fighters[0].roll_ticks == 0, "roll ends after its authored duration")
	_expect(session.fighters[0].roll_recovery_ticks > 0, "roll enters bounded recovery")
	_expect(not bool(session.fighters[0].snapshot().get(&"roll_low_posture", true)), "standing posture restores after clear floor")

	# A real roof blocks standing-height restoration while allowing the low
	# collider through. Removing the roof lets the next physics readback stand.
	var roof := StaticBody2D.new()
	var roof_shape := CollisionShape2D.new()
	var roof_rect := RectangleShape2D.new()
	roof_rect.size = Vector2(220.0, 8.0)
	roof_shape.shape = roof_rect
	roof.add_child(roof_shape)
	roof.position = Vector2(300.0, 700.0)
	roof.collision_layer = 1
	roof.collision_mask = 0
	session.add_child(roof)
	await physics_frame
	session.place_fighter(0, Vector2(300.0, 740.0), Vector2.ZERO, true)
	var roof_roll := TraceCore.build_frame(session.tick, {}, {&"p1_right": true, &"p1_down": true})
	_expect(session.step(roof_roll), "roof roll frame advances")
	for _tick: int in range(int(session.tuning[&"roll_duration_ticks"])):
		await physics_frame
		var roof_hold := TraceCore.build_frame(session.tick, {&"p1_right": true, &"p1_down": true}, {&"p1_right": true, &"p1_down": true})
		_expect(session.step(roof_hold), "roof roll duration advances")
	_expect(session.fighters[0].snapshot().get(&"roll_low_posture", false), "roof keeps fighter crouched after roll")
	_expect(is_equal_approx(session.bodies[0].posture_height(), float(session.tuning[&"roll_height"])), "roof readback keeps short collider")
	roof.queue_free()
	await physics_frame
	var roof_clear := TraceCore.build_frame(session.tick, {}, {})
	_expect(session.step(roof_clear), "roof removal frame advances")
	_expect(not bool(session.fighters[0].snapshot().get(&"roll_low_posture", true)), "clear roof restores standing state")
	_expect(is_equal_approx(session.bodies[0].posture_height(), float(session.tuning[&"char_height"])), "clear roof readback restores full collider")

	var pit_session := MatchSession.new(72, &"two_player")
	get_root().add_child(pit_session)
	await physics_frame
	pit_session.place_fighter(0, Vector2(105.0, 740.0), Vector2.ZERO, true)
	pit_session.place_fighter(1, Vector2(1400.0, 740.0), Vector2.ZERO, true)
	var pit_roll := TraceCore.build_frame(pit_session.tick, {}, {&"p1_left": true, &"p1_down": true})
	_expect(pit_session.step(pit_roll), "pit roll start advances")
	for _tick: int in range(int(pit_session.tuning[&"roll_duration_ticks"]) + 16):
		if pit_session.fighters[0].health <= 0:
			break
		await physics_frame
		var pit_hold := TraceCore.build_frame(pit_session.tick, {&"p1_left": true, &"p1_down": true}, {&"p1_left": true, &"p1_down": true})
		if not pit_session.step(pit_hold):
			break
	_expect(pit_session.fighters[0].health == 0 and pit_session.fighters[0].locomotion == FighterState.Locomotion.DOWNED, "rolling into a pit resolves immediately")

	# Raw down+direction input while airborne is not enough to douse: the
	# fighter must actually enter the grounded roll state.
	var airborne := MatchSession.new(73, &"two_player")
	get_root().add_child(airborne)
	await physics_frame
	airborne.place_fighter(0, Vector2(300.0, 650.0), Vector2.ZERO, false)
	airborne.place_fighter(1, Vector2(1400.0, 740.0), Vector2.ZERO, true)
	airborne._ignite_fighter(1)
	var airborne_frame := TraceCore.build_frame(airborne.tick, {}, {&"p1_right": true, &"p1_down": true})
	_expect(airborne.step(airborne_frame), "airborne douse control advances")
	_expect(airborne.burning_ticks[0] > 0, "airborne down plus direction does not extinguish")
	_expect(airborne.fighters[0].roll_ticks == 0, "airborne control does not start a roll")

	# A knockdown also blocks the roll. Once a grounded roll really starts,
	# the same hazard is extinguished and leaves an explicit event.
	var douse := MatchSession.new(74, &"two_player")
	get_root().add_child(douse)
	await physics_frame
	douse.place_fighter(0, Vector2(300.0, 740.0), Vector2.ZERO, true)
	douse.place_fighter(1, Vector2(1400.0, 740.0), Vector2.ZERO, true)
	douse.fighters[0].apply_hit(1, 0.0, true, &"test_knockdown", douse.tuning)
	douse._ignite_fighter(1)
	var blocked := TraceCore.build_frame(douse.tick, {}, {&"p1_right": true, &"p1_down": true})
	_expect(douse.step(blocked), "knockdown douse control advances")
	_expect(douse.burning_ticks[0] > 0, "knockdown cannot douse without a roll")
	_expect(douse.fighters[0].roll_ticks == 0, "knockdown cannot start a roll")
	for _tick: int in range(int(douse.tuning[&"knockdown_duration_ticks"]) + 1):
		await physics_frame
		var settle := TraceCore.build_frame(douse.tick, {}, {})
		_expect(douse.step(settle), "knockdown recovery frame advances")
	await physics_frame
	var douse_frame := TraceCore.build_frame(douse.tick, {}, {&"p1_right": true, &"p1_down": true})
	_expect(douse.step(douse_frame), "grounded roll douse frame advances")
	_expect(douse.fighters[0].roll_ticks > 0, "douse uses the live roll state")
	_expect(douse.burning_ticks[0] == 0, "grounded rolling douses the burning fighter")
	_expect(_has_fire_event(douse, &"extinguish", 1), "douse emits an extinguish event")

	# Damage cadence and natural expiry are deterministic and do not emit a
	# phantom burn after the duration reaches zero.
	var expiry := MatchSession.new(75, &"two_player")
	get_root().add_child(expiry)
	await physics_frame
	expiry.place_fighter(0, Vector2(300.0, 740.0), Vector2.ZERO, true)
	expiry.place_fighter(1, Vector2(1400.0, 740.0), Vector2.ZERO, true)
	expiry._ignite_fighter(1)
	var initial_health: int = expiry.fighters[0].health
	for _tick: int in range(int(expiry.tuning[&"burn_duration_ticks"])):
		await physics_frame
		var burn_frame := TraceCore.build_frame(expiry.tick, {}, {})
		_expect(expiry.step(burn_frame), "burn duration frame advances")
	_expect(expiry.burning_ticks[0] == 0, "burning naturally expires")
	_expect(expiry.fighters[0].health < initial_health, "burn applies periodic damage")
	var expected_burns: int = int(expiry.tuning[&"burn_duration_ticks"]) / int(expiry.tuning[&"burn_interval_ticks"])
	_expect(initial_health - expiry.fighters[0].health == expected_burns * int(expiry.tuning[&"burn_damage"]), "burn cadence has no expiry phantom tick")

	var before_tick: int = douse.tick
	var before_hash: String = douse.snapshot_hash()
	var wrong := TraceCore.build_frame(before_tick + 1, {}, {})
	_expect(not douse.step(wrong), "wrong tick is rejected")
	_expect(douse.tick == before_tick and douse.snapshot_hash() == before_hash, "rejected tick preserves roll and fire state")

	for node: Node in [session, twin, airborne, douse, expiry, pit_session]:
		node.queue_free()
	await process_frame
	if failures == 0:
		print("SA-06 roll/burning PASS: %d assertions; grounded roll, posture, burn cadence and douse" % assertions)
	else:
		printerr("SA-06 roll/burning FAIL: %d of %d assertions" % [failures, assertions])
	quit(0 if failures == 0 else 1)

func _has_fire_event(session: MatchSession, kind: StringName, player: int) -> bool:
	for event: Dictionary in session.fire_events:
		if StringName(event.get(&"kind", &"")) == kind and int(event.get(&"player", 0)) == player:
			return true
	return false

func _expect(condition: bool, message: String) -> void:
	assertions += 1
	if not condition:
		failures += 1
		printerr("FAIL: %s" % message)

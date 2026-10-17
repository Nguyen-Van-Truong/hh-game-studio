extends SceneTree
## SA-05 provisional bullet-time contract. This is implementation evidence,
## not a measured reference claim.

const TraceCore = preload("res://tests/trace_core.gd")

var failures: int = 0
var assertions: int = 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var session := MatchSession.new(29, &"two_player")
	get_root().add_child(session)
	await process_frame
	await physics_frame
	session.place_fighter(0, Vector2(900.0, 610.0), Vector2.ZERO, true)
	session.place_fighter(1, Vector2(1200.0, 740.0), Vector2.ZERO, true)

	var pickup_frame: InputFrame = TraceCore.build_frame(0, {}, {&"p1_down": true, &"p1_punch": true})
	_expect(session.step(pickup_frame), "bullet-time pickup frame advances")
	_expect(session.fighters[0].power_charges == 1, "bullet-time pickup grants one power charge")
	_expect(session.fighters[0].power_duration_ticks == 300, "five-second pickup uses 300 fixed ticks")

	await physics_frame
	var activate_frame: InputFrame = TraceCore.build_frame(1, {}, {&"p1_power": true})
	_expect(session.step(activate_frame), "power activation frame advances")
	_expect(session.bullet_time_owner == 0, "P1 owns activated bullet time")
	_expect(session.fighters[0].power_charges == 0, "activation consumes the power charge")
	_expect(session.bullet_time_ticks > 290 and session.bullet_time_ticks < 300, "duration counts down from the authored five seconds")
	_expect(session.fighters[0].bullet_time_active, "activator reports active bullet time")
	_expect(session.fighters[1].tempo_divisor == 2, "other fighter is slowed to half-step tempo")

	var opponent_start_x: float = session.fighters[1].position.x
	await physics_frame
	var slow_frame: InputFrame = TraceCore.build_frame(2, {}, {&"p2_right": true, &"p2_punch": true})
	_expect(session.step(slow_frame), "slowed opponent frame advances")
	_expect(is_equal_approx(session.fighters[1].position.x, opponent_start_x), "slowed opponent skips the first half-step")
	_expect(session.fighters[1].attack_name == &"none", "skipped fighter does not apply attack before its due step")

	await physics_frame
	var slow_move_frame: InputFrame = TraceCore.build_frame(3, {&"p2_right": true, &"p2_punch": true}, {&"p2_right": true, &"p2_punch": true})
	_expect(session.step(slow_move_frame), "second slowed opponent frame advances")
	_expect(session.fighters[1].position.x > opponent_start_x, "slowed opponent advances on its due half-step")
	_expect(session.fighters[1].attack_name == &"punch" or session.fighters[1].attack_name == &"jump_kick", "buffered punch press survives a skipped tempo tick: %s pending=%s" % [String(session.fighters[1].attack_name), str(session.fighters[1].tempo_pending_actions)])

	await physics_frame
	var cancel_frame: InputFrame = TraceCore.build_frame(4, {&"p2_punch": true}, {&"p1_power": true})
	_expect(session.step(cancel_frame), "power cancel frame advances")
	_expect(session.fighters[1].attack_name == &"punch" or session.fighters[1].attack_name == &"jump_kick", "skipped release tick keeps prior action state deterministic: %s" % String(session.fighters[1].attack_name))
	_expect(session.bullet_time_owner == -1 and session.bullet_time_ticks == 0, "pressing power again cancels bullet time")
	_expect(not session.fighters[0].bullet_time_active, "activator leaves bullet-time state after cancel")
	_expect(session.fighters[1].tempo_divisor == 1, "other fighter returns to normal tempo after cancel")

	session.queue_free()
	await process_frame
	if failures == 0:
		print("SA-05 bullet-time PASS: %d assertions; pickup/activate/slow/cancel" % assertions)
	else:
		printerr("SA-05 bullet-time FAIL: %d of %d assertions" % [failures, assertions])
	quit(0 if failures == 0 else 1)

func _expect(condition: bool, message: String) -> void:
	assertions += 1
	if not condition:
		failures += 1
		printerr("FAIL: %s" % message)

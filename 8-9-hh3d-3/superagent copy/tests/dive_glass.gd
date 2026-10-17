extends SceneTree
## SA-03/SA-06 dive slice. The dive is an authored Classic move: airborne
## down+direction enters a short, invulnerable tackle that can hit a fighter
## and break a nearby glass prop. This is engineering evidence, not Y8 parity.

const TraceCore = preload("res://tests/trace_core.gd")

var failures: int = 0
var assertions: int = 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var session := MatchSession.new(83, &"two_player")
	var twin := MatchSession.new(83, &"two_player")
	get_root().add_child(session)
	get_root().add_child(twin)
	await process_frame
	await physics_frame
	await physics_frame
	for active: MatchSession in [session, twin]:
		# The airborne placement puts the live tackle path level with the
		# authored glass and the second fighter, without teleporting an attack.
		active.place_fighter(0, Vector2(900.0, 670.0), Vector2.ZERO, false)
		active.place_fighter(1, Vector2(940.0, 670.0), Vector2.ZERO, false)

	var dive_frame := TraceCore.build_frame(0, {}, {&"p1_right": true, &"p1_down": true})
	_expect(session.step(dive_frame), "dive frame advances")
	_expect(twin.step(dive_frame), "twin dive frame advances")
	var attacker: FighterState = session.fighters[0]
	var target: FighterState = session.fighters[1]
	_expect(attacker.dive_ticks > 0, "airborne down plus direction starts a dive")
	_expect(attacker.action_name == &"dive", "dive exposes its action state")
	_expect(attacker.facing == 1 and attacker.position.x > 900.0, "dive faces and moves in the held direction")
	_expect(attacker.snapshot().get(&"dive_low_posture", false), "dive snapshot records the short posture")
	_expect(attacker.invulnerability_ticks > 0, "dive grants its authored invulnerability window")
	_expect(target.last_hit_kind == &"dive", "dive tackle reports its hit kind")
	_expect(target.health == int(session.tuning[&"max_health"]) - int(session.tuning[&"dive_damage"]), "dive tackle damages a close fighter")
	_expect(not bool(session.prop_rows[3].get(&"active", true)), "dive breaks the live glass prop")
	_expect(_has_prop_event(session, &"prop_destroyed", &"relay_glass_east"), "dive glass break emits a destroyed event")
	_expect(session.snapshot_hash() == twin.snapshot_hash(), "identical dive traces have the same hash")
	_expect(not attacker.apply_hit(999, 20.0, false, &"test_hit", session.tuning), "dive invulnerability blocks an immediate hit")

	for _tick: int in range(int(session.tuning[&"dive_duration_ticks"]) + 2):
		await physics_frame
		var settle := TraceCore.build_frame(session.tick, {}, {})
		_expect(session.step(settle), "dive recovery frame advances")
	_expect(attacker.dive_ticks == 0, "dive reaches its bounded end")
	_expect(not bool(attacker.snapshot().get(&"dive_low_posture", true)), "dive restores the standing posture when clear")

	session.queue_free()
	twin.queue_free()
	await process_frame
	if failures == 0:
		print("SA-03/SA-06 dive PASS: %d assertions; tackle, glass break, invulnerability, recovery" % assertions)
	else:
		printerr("SA-03/SA-06 dive FAIL: %d of %d assertions" % [failures, assertions])
	quit(0 if failures == 0 else 1)

func _has_prop_event(session: MatchSession, kind: StringName, prop_id: StringName) -> bool:
	for event: Dictionary in session.prop_events:
		if StringName(event.get(&"kind", &"")) == kind and StringName(event.get(&"prop_id", &"")) == prop_id:
			return true
	return false

func _expect(condition: bool, message: String) -> void:
	assertions += 1
	if not condition:
		failures += 1
		printerr("FAIL: %s" % message)

extends SceneTree
## SA-05 provisional catalog proof. Each authored item is exercised through the
## live MatchSession pickup path; this is implementation evidence, not parity.

const TraceCore = preload("res://tests/trace_core.gd")

var failures: int = 0
var assertions: int = 0
var session: MatchSession

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	session = MatchSession.new(31, &"two_player")
	get_root().add_child(session)
	await process_frame
	await physics_frame
	_expect(session.pickup_rows.size() == 7, "relay yard exposes the seven authored catalog entries")

	await _collect(Vector2(470.0, 740.0), {&"p1_down": true, &"p1_punch": true})
	_expect(session.gun_ids[0] == &"pistol", "pistol pickup selects the pistol slot")
	_expect(session.fighters[0].ammo == 12, "pistol pickup grants its authored magazine")
	_expect(not _active(&"yard_pistol_west"), "pistol pickup deactivates after collection")

	await _collect(Vector2(1130.0, 740.0), {&"p1_down": true, &"p1_punch": true})
	_expect(session.gun_ids[0] == &"shotgun", "shotgun pickup replaces the gun slot")
	_expect(session.fighters[0].ammo == 4, "shotgun pickup grants its authored magazine")
	_expect(not _active(&"yard_shotgun_east"), "shotgun pickup deactivates after collection")

	session.fighters[0].health = 50
	await _collect(Vector2(800.0, 610.0), {})
	_expect(session.fighters[0].health == 75, "pill heals 25 health on contact")
	_expect(not _active(&"yard_pill_center"), "pill deactivates on contact")

	session.fighters[0].health = 25
	await _collect(Vector2(350.0, 548.0), {})
	_expect(session.fighters[0].health == 75, "medkit heals 50 health on contact")
	_expect(not _active(&"yard_medkit_west"), "medkit deactivates on contact")

	session.fighters[0].grenades = 1
	await _collect(Vector2(1240.0, 548.0), {&"p1_down": true, &"p1_punch": true})
	_expect(session.fighters[0].grenades == 3, "grenade pickup adds two grenades")
	_expect(not _active(&"yard_grenades_east"), "grenade pickup deactivates after collection")

	await _collect(Vector2(900.0, 610.0), {&"p1_down": true, &"p1_punch": true})
	_expect(session.fighters[0].power_charges == 1, "five-second power pickup grants one charge")
	_expect(session.fighters[0].power_duration_ticks == 300, "five-second power pickup stores 300 ticks")
	_expect(not _active(&"yard_bullet_time_center"), "five-second power pickup deactivates after collection")

	await _collect(Vector2(650.0, 740.0), {&"p1_down": true, &"p1_punch": true})
	_expect(session.fighters[0].power_duration_ticks == 600, "ten-second power pickup stores 600 ticks")
	_expect(not _active(&"yard_bullet_time_west"), "ten-second power pickup deactivates after collection")

	session.queue_free()
	await process_frame
	session = MatchSession.new(37, &"two_player")
	get_root().add_child(session)
	await process_frame
	await physics_frame
	await _collect(Vector2(470.0, 740.0), {&"p2_down": true, &"p2_punch": true}, 1)
	_expect(session.gun_ids[1] == &"pistol", "P2 can collect the pistol through the same pickup gesture")
	_expect(not _active(&"yard_pistol_west"), "P2 pistol pickup deactivates after collection")
	session.fighters[1].health = 25
	await _collect(Vector2(350.0, 548.0), {}, 1)
	_expect(session.fighters[1].health == 75, "P2 receives contact health pickup healing")
	await _collect(Vector2(900.0, 610.0), {&"p2_down": true, &"p2_punch": true}, 1)
	_expect(session.fighters[1].power_charges == 1 and session.fighters[1].power_duration_ticks == 300, "P2 receives the five-second power pickup")
	session.queue_free()
	await process_frame
	if failures == 0:
		print("SA-05 item catalog PASS: %d assertions; weapons/health/grenade/power pickups" % assertions)
	else:
		printerr("SA-05 item catalog FAIL: %d of %d assertions" % [failures, assertions])
	quit(0 if failures == 0 else 1)

func _collect(at: Vector2, desired: Dictionary, player_index: int = 0) -> void:
	session.place_fighter(player_index, at, Vector2.ZERO, true)
	var tick: int = session.tick
	_expect(session.step(TraceCore.build_frame(tick, {}, desired)), "pickup input frame advances")
	await physics_frame
	_expect(session.step(TraceCore.build_frame(session.tick, desired, {})), "pickup release frame advances")
	await physics_frame

func _active(pickup_id: StringName) -> bool:
	for row: Dictionary in session.pickup_rows:
		if StringName(row.get(&"id", &"")) == pickup_id:
			return bool(row.get(&"active", false))
	return false

func _expect(condition: bool, message: String) -> void:
	assertions += 1
	if not condition:
		failures += 1
		printerr("FAIL: %s" % message)

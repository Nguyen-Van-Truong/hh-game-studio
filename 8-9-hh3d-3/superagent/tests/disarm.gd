extends SceneTree
## SA-05 provisional disarm proof. A melee hit interrupts an aiming fighter;
## the observed clean-room contract records the endpoint as an empty gun slot.

const TraceCore = preload("res://tests/trace_core.gd")

var failures: int = 0
var assertions: int = 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var session := MatchSession.new(37, &"two_player")
	get_root().add_child(session)
	await process_frame
	await physics_frame
	session.place_fighter(0, Vector2(600.0, 740.0), Vector2.ZERO, true)
	session.place_fighter(1, Vector2(640.0, 740.0), Vector2.ZERO, true)
	session.gun_ids[1] = &"shotgun"
	session.fighters[1].ammo = 4

	var frame: InputFrame = TraceCore.build_frame(0, {}, {&"p1_punch": true, &"p2_shoot": true})
	_expect(session.step(frame), "disarm frame advances through MatchSession")
	_expect(session.fighters[1].aiming, "target is aiming during the melee interruption")
	_expect(session.gun_ids[1] == &"none", "melee hit removes the target gun slot")
	_expect(session.fighters[1].ammo == 0, "disarm clears target ammunition")
	var events: Array = session.snapshot().get(&"weapon_events", [])
	_expect(events.size() == 1, "disarm exposes one weapon event")
	if events.size() == 1:
		var event: Dictionary = events[0]
		_expect(StringName(event.get(&"kind", &"")) == &"disarm", "weapon event records disarm kind")
		_expect(int(event.get(&"target", 0)) == 2, "weapon event identifies P2 target")

	session.queue_free()
	await process_frame
	if failures == 0:
		print("SA-05 disarm PASS: %d assertions; aiming melee interruption" % assertions)
	else:
		printerr("SA-05 disarm FAIL: %d of %d assertions" % [failures, assertions])
	quit(0 if failures == 0 else 1)

func _expect(condition: bool, message: String) -> void:
	assertions += 1
	if not condition:
		failures += 1
		printerr("FAIL: %s" % message)

extends SceneTree
## MatchSession-specific replay proof. This supplements the base Simulation
## trace with aim, release-fire, angled ray authority and failed-step safety.

const TraceCore = preload("res://tests/trace_core.gd")

var failures: int = 0
var assertions: int = 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var first := MatchSession.new(911, &"two_player")
	var second := MatchSession.new(911, &"two_player")
	get_root().add_child(first)
	get_root().add_child(second)
	await process_frame
	_expect(first.bodies.size() == 2 and second.bodies.size() == 2, "twin match sessions create two physics bodies")
	var initial_hash: String = first.snapshot_hash()
	var aim_frame: InputFrame = TraceCore.build_frame(0, {}, {&"p1_shoot": true, &"p1_up": true})
	await physics_frame
	_expect(first.step(aim_frame) and second.step(aim_frame), "twin aim frames advance")
	_expect(first.snapshot_hash() == second.snapshot_hash(), "aim frame replay hashes match")
	_expect(first.snapshot_hash() != initial_hash, "aim state changes canonical match hash")
	_expect(first.fighters[0].aiming and absf(first.fighters[0].aim_angle) > 0.0, "held shoot plus up changes aim state")
	_expect(first.fighters[0].ammo == 12, "aim frame does not consume ammunition")

	var release_frame: InputFrame = TraceCore.build_frame(1, {&"p1_shoot": true, &"p1_up": true}, {&"p1_up": true})
	await physics_frame
	_expect(first.step(release_frame) and second.step(release_frame), "twin release frames advance")
	_expect(first.snapshot_hash() == second.snapshot_hash(), "release frame replay hashes match")
	_expect(first.fighters[0].ammo == 11, "release frame consumes one ammunition")
	_expect(not first.fighters[0].aiming, "release frame exits aiming state")
	_expect(first.shot_events.size() == 1, "release frame queues one shot event")

	# Supplemental authority check: the same ray used for the presentation event
	# decides a hit. An upward ray misses a level target, then hits a target one
	# body-height above when the angle is aligned.
	first.place_fighter(0, Vector2(940.0, first.world.floor_y))
	first.place_fighter(1, Vector2(1110.0, first.world.floor_y))
	first.fighters[0].aim_angle = -0.6
	first.fighters[0].queued_attack = &"shoot"
	first.fighters[1].health = 100
	first._resolve_attacks()
	_expect(first.fighters[1].health == 100, "angled ray misses a level target")
	first.place_fighter(1, Vector2(1110.0, first.world.floor_y - 110.0), Vector2.ZERO, false)
	first.fighters[0].aim_angle = atan2(-110.0, 170.0)
	first.fighters[0].queued_attack = &"shoot"
	first.fighters[1].health = 100
	first._resolve_attacks()
	_expect(first.fighters[1].last_hit_kind == &"shoot", "aligned angled ray hits an elevated target")

	var before_rejected: String = first.snapshot_hash()
	_expect(not first.step(release_frame), "duplicate frame is rejected")
	_expect(first.snapshot_hash() == before_rejected, "rejected frame does not mutate event ttl or match hash")
	first.queue_free()
	second.queue_free()
	await process_frame
	if failures == 0:
		print("SA-04 MatchSession replay PASS: %d assertions; aim/release/hash/fail-closed" % assertions)
	else:
		printerr("SA-04 MatchSession replay FAIL: %d of %d assertions" % [failures, assertions])
	quit(0 if failures == 0 else 1)

func _expect(condition: bool, message: String) -> void:
	assertions += 1
	if not condition:
		failures += 1
		printerr("FAIL: %s" % message)

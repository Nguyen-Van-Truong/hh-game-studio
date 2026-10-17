extends SceneTree
## SA-06 implementation slice: live attacks mutate authored props and replay
## the same prop/event hash. This does not claim measured Y8 scenery parity.

const TraceCore = preload("res://tests/trace_core.gd")

var failures: int = 0
var assertions: int = 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var session := MatchSession.new(53, &"two_player")
	var twin := MatchSession.new(53, &"two_player")
	var shot_session := MatchSession.new(53, &"two_player")
	get_root().add_child(session)
	get_root().add_child(twin)
	get_root().add_child(shot_session)
	await process_frame
	await physics_frame
	await physics_frame
	session.place_fighter(0, Vector2(340.0, 740.0), Vector2.ZERO, true)
	session.place_fighter(1, Vector2(1400.0, 740.0), Vector2.ZERO, true)
	twin.place_fighter(0, Vector2(340.0, 740.0), Vector2.ZERO, true)
	twin.place_fighter(1, Vector2(1400.0, 740.0), Vector2.ZERO, true)
	shot_session.place_fighter(0, Vector2(600.0, 740.0), Vector2.ZERO, true)
	shot_session.place_fighter(1, Vector2(850.0, 740.0), Vector2.ZERO, true)
	_expect(session.prop_rows.size() == 4, "relay yard exposes four authored props")
	_expect(StringName(session.prop_rows[0].get(&"material", &"")) == &"wood", "crate carries its authored material")
	_expect(bool(session.prop_rows[1].get(&"explosive", false)), "barrel carries its authored explosive flag")
	_expect(StringName(session.prop_rows[3].get(&"material", &"")) == &"glass", "glass carries its authored material")

	var punch := TraceCore.build_frame(0, {}, {&"p1_punch": true})
	_expect(session.step(punch), "melee prop frame advances")
	_expect(twin.step(punch), "twin melee prop frame advances")
	_expect(int(session.prop_rows[0].get(&"health", 0)) < 30, "melee reduces the west crate health")
	_expect(_has_prop_event(session, &"prop_hit", &"relay_crate_west"), "melee emits a prop hit event")
	var nested_snapshot: Dictionary = session.snapshot()
	var nested_world: Dictionary = Dictionary(nested_snapshot.get(&"world", {}))
	var nested_props: Array = Array(nested_world.get(&"props", []))
	_expect(int(Dictionary(nested_props[0]).get(&"health", 0)) == int(session.prop_rows[0].get(&"health", 0)), "world snapshot mirrors mutable prop health")
	_expect(session.snapshot_hash() == twin.snapshot_hash(), "identical prop traces produce the same hash")

	await physics_frame
	shot_session.gun_ids[0] = &"shotgun"
	shot_session.fighters[0].ammo = 4
	var aim_hold := TraceCore.build_frame(shot_session.tick, {}, {&"p1_shoot": true})
	_expect(shot_session.step(aim_hold), "held aim frame advances")
	await physics_frame
	var release := TraceCore.build_frame(shot_session.tick, {&"p1_shoot": true}, {})
	_expect(shot_session.step(release), "release fire frame advances")
	_expect(not bool(shot_session.prop_rows[1].get(&"active", true)), "barrel is destroyed by the live shot path")
	_expect(_has_prop_event(shot_session, &"prop_destroyed", &"relay_barrel_center"), "barrel emits a destroyed event")
	_expect(_has_explosion(shot_session, &"barrel"), "barrel destruction emits an explosion event")
	_expect(shot_session.burning_ticks[1] > 0, "barrel explosion ignites the nearby fighter")
	_expect(int(shot_session.prop_rows[2].get(&"health", 0)) == 30, "unrelated east crate remains unchanged without an authored chain target")
	shot_session.fighters[1].invulnerability_ticks = 0
	var live_burn_health: int = shot_session.fighters[1].health
	for _tick: int in range(int(shot_session.tuning[&"burn_interval_ticks"]) - 1):
		await physics_frame
		var live_burn_frame := TraceCore.build_frame(shot_session.tick, {}, {})
		_expect(shot_session.step(live_burn_frame), "live ignition cadence frame advances")
	_expect(shot_session.fighters[1].health < live_burn_health, "live ignition reaches its first periodic damage")
	await physics_frame
	var blocked_douse := TraceCore.build_frame(shot_session.tick, {}, {&"p2_down": true, &"p2_right": true})
	_expect(shot_session.step(blocked_douse), "knockdown douse control frame advances")
	_expect(shot_session.burning_ticks[1] > 0, "knockdown keeps the burning fighter lit")
	_expect(shot_session.fighters[1].roll_ticks == 0, "knockdown does not start a roll")
	for _tick: int in range(int(shot_session.tuning[&"knockdown_duration_ticks"]) + 1):
		await physics_frame
		var settle := TraceCore.build_frame(shot_session.tick, {}, {})
		_expect(shot_session.step(settle), "knockdown recovery frame advances")
	await physics_frame
	var douse := TraceCore.build_frame(shot_session.tick, {}, {&"p2_down": true, &"p2_right": true})
	_expect(shot_session.step(douse), "grounded roll douse frame advances")
	_expect(shot_session.burning_ticks[1] == 0, "grounded rolling douses the burning fighter")

	var glass_session := MatchSession.new(53, &"two_player")
	get_root().add_child(glass_session)
	await physics_frame
	glass_session.place_fighter(0, Vector2(920.0, 740.0), Vector2.ZERO, true)
	glass_session.place_fighter(1, Vector2(1400.0, 740.0), Vector2.ZERO, true)
	var glass_hold := TraceCore.build_frame(glass_session.tick, {}, {&"p1_shoot": true})
	_expect(glass_session.step(glass_hold), "glass held aim frame advances")
	await physics_frame
	var glass_release := TraceCore.build_frame(glass_session.tick, {&"p1_shoot": true}, {})
	_expect(glass_session.step(glass_release), "glass release fire frame advances")
	_expect(not bool(glass_session.prop_rows[3].get(&"active", true)), "live shot breaks the authored glass prop")
	_expect(_has_prop_event(glass_session, &"prop_destroyed", &"relay_glass_east"), "glass break emits a destroyed event")

	session.queue_free()
	twin.queue_free()
	shot_session.queue_free()
	glass_session.queue_free()
	await process_frame
	if failures == 0:
		print("SA-06 world props PASS: %d assertions; authored props, live melee/shot, deterministic hash" % assertions)
	else:
		printerr("SA-06 world props FAIL: %d of %d assertions" % [failures, assertions])
	quit(0 if failures == 0 else 1)

func _has_prop_event(session: MatchSession, kind: StringName, prop_id: StringName) -> bool:
	for event: Dictionary in session.prop_events:
		if StringName(event.get(&"kind", &"")) == kind and StringName(event.get(&"prop_id", &"")) == prop_id:
			return true
	return false

func _has_explosion(session: MatchSession, source: StringName) -> bool:
	for event: Dictionary in session.explosion_events:
		if StringName(event.get(&"source", &"")) == source:
			return true
	return false

func _expect(condition: bool, message: String) -> void:
	assertions += 1
	if not condition:
		failures += 1
		printerr("FAIL: %s" % message)

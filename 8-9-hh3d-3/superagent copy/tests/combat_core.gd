extends SceneTree
## Provisional SA-04 core combat checks. Values are engineering seeds, not Y8
## parity measurements. Every case uses the deterministic InputFrame path.

const TraceCore = preload("res://tests/trace_core.gd")
const PhysicsFixture = preload("res://tests/physics_fixture.gd")
var failures: int = 0
var assertions: int = 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	await _test_melee_and_jump_kick()
	await _test_shot_and_knockdown()
	await _test_grenade_fuse_and_replay()
	if failures == 0:
		print("SA-04 provisional combat PASS: %d assertions; melee, shot, knockdown, grenade, replay" % assertions)
	else:
		printerr("SA-04 provisional combat FAIL: %d of %d assertions" % [failures, assertions])
	await PhysicsFixture.cleanup(self)
	quit(0 if failures == 0 else 1)

func _test_melee_and_jump_kick() -> void:
	var sim := PhysicsFixture.create(self, 401)
	var attacker: FighterState = sim.fighters[0]
	var target: FighterState = sim.fighters[1]
	sim.place_fighter(0, Vector2(940, sim.world.floor_y))
	sim.place_fighter(1, Vector2(980, sim.world.floor_y))
	# Clear east-floor lane preserves the authored melee ranges.
	var held: Dictionary = {}
	_expect(await PhysicsFixture.advance(sim, TraceCore.build_frame(0, held, {&"p1_punch": true})), "punch frame advances")
	_expect(target.health == int(sim.tuning[&"max_health"]) - int(sim.tuning[&"punch_damage"]), "punch damages a close target")
	_expect(target.last_hit_kind == &"punch", "punch reports hit kind")
	_expect(target.hitstun_ticks > 0, "punch applies hitstun")
	held = {&"p1_punch": true}
	sim.place_fighter(0, Vector2(940, sim.world.floor_y - 80), Vector2.ZERO, false)
	target.health = int(sim.tuning[&"max_health"])
	_expect(await PhysicsFixture.advance(sim, TraceCore.build_frame(1, held, {&"p1_punch": false})), "airborne release frame advances")
	# Re-arm after cooldown and put a real press edge in the next frame.
	for tick_value: int in range(2, 10):
		_expect(await PhysicsFixture.advance(sim, TraceCore.build_frame(tick_value, {}, {})), "jump-kick cooldown frame advances")
	sim.place_fighter(0, Vector2(940, sim.world.floor_y - 40), Vector2.ZERO, false)
	sim.place_fighter(1, Vector2(970, sim.world.floor_y))
	_expect(await PhysicsFixture.advance(sim, TraceCore.build_frame(10, {}, {&"p1_punch": true})), "jump kick frame advances")
	_expect(target.last_hit_kind == &"jump_kick", "airborne punch is a jump kick")
	_expect(target.health < int(sim.tuning[&"max_health"]), "jump kick damages a close target")

func _test_shot_and_knockdown() -> void:
	var sim := PhysicsFixture.create(self, 402)
	var attacker: FighterState = sim.fighters[0]
	var target: FighterState = sim.fighters[1]
	sim.place_fighter(0, Vector2(940, sim.world.floor_y))
	sim.place_fighter(1, Vector2(1120, sim.world.floor_y))
	var frame := TraceCore.build_frame(0, {}, {&"p1_shoot": true})
	_expect(await PhysicsFixture.advance(sim, frame), "shot aim frame advances")
	_expect(attacker.aiming, "held shoot enters aiming state")
	_expect(attacker.ammo == 12, "aiming does not consume ammunition")
	var release_frame := TraceCore.build_frame(1, {&"p1_shoot": true}, {})
	_expect(await PhysicsFixture.advance(sim, release_frame), "shot release frame advances")
	_expect(target.last_hit_kind == &"shoot", "shot reports hit kind")
	_expect(target.health == 100 - int(sim.tuning[&"shoot_damage"]), "shot damages aligned target in range")
	_expect(attacker.ammo == 11, "shot consumes one ammunition")
	# Seed the deterministic critical/knockdown branch explicitly.
	sim.world.rng_state = 4
	target.invulnerability_ticks = 0
	for tick_value: int in range(2, 9):
		_expect(await PhysicsFixture.advance(sim, TraceCore.build_frame(tick_value, {}, {})), "shot recovery frame advances")
	sim.place_fighter(0, Vector2(940, sim.world.floor_y))
	sim.place_fighter(1, Vector2(1120, sim.world.floor_y))
	_expect(await PhysicsFixture.advance(sim, TraceCore.build_frame(9, {}, {&"p1_shoot": true})), "knockdown aim frame advances")
	sim.world.rng_state = 4
	_expect(await PhysicsFixture.advance(sim, TraceCore.build_frame(10, {&"p1_shoot": true}, {})), "knockdown release frame advances")
	_expect(target.knockdown_ticks > 0, "seeded shot can knock target down")
	_expect(target.invulnerability_ticks > 0, "knockdown grants invulnerability")
	var health_after: int = target.health
	_expect(await PhysicsFixture.advance(sim, TraceCore.build_frame(11, {}, {})), "invulnerable follow-up frame advances")
	_expect(target.health == health_after, "invulnerability blocks immediate follow-up damage")

func _test_grenade_fuse_and_replay() -> void:
	var first := PhysicsFixture.create(self, 403)
	var second := PhysicsFixture.create(self, 403)
	for sim: Simulation in [first, second]:
		sim.place_fighter(0, Vector2(940, sim.world.floor_y))
		sim.place_fighter(1, Vector2(1180, sim.world.floor_y))
	_expect(await PhysicsFixture.advance(first, TraceCore.build_frame(0, {}, {&"p1_throw": true})), "throw frame advances")
	_expect(await PhysicsFixture.advance(second, TraceCore.build_frame(0, {}, {&"p1_throw": true})), "twin throw frame advances")
	_expect(first.grenades.size() == 1 and first.fighters[0].grenades == 2, "throw creates one fuse and consumes stock")
	for tick_value: int in range(1, 32):
		var frame_a := TraceCore.build_frame(tick_value, {}, {})
		_expect(await PhysicsFixture.advance_pair(first, second, frame_a), "fuse frame advances")
	_expect(first.fighters[1].health < 100, "grenade fuse applies radius damage")
	_expect(first.grenades.is_empty(), "fused grenade is removed")
	_expect(first.snapshot_hash() == second.snapshot_hash(), "combat replay remains deterministic")

func _expect(condition: bool, message: String) -> void:
	assertions += 1
	if not condition:
		failures += 1
		printerr("FAIL: %s" % message)

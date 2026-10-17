extends SceneTree
class_name TraceCoreChecks

const PhysicsFixture = preload("res://tests/physics_fixture.gd")
## Deterministic fixed-step trace and postcondition checks for SA-03.
## This is a core smoke gate only; Y8 parity remains unverified until SA-02.

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var result: Dictionary = await run_trace(self)
	await PhysicsFixture.cleanup(self)
	if bool(result.get(&"deterministic", false)) and bool(result.get(&"postconditions", false)):
		print("SA-03 deterministic trace PASS: tick=%d hash=%s" % [int(result[&"final_tick"]), String(result[&"final_hash"])])
		quit(0)
	else:
		printerr("SA-03 deterministic trace FAIL: %s" % String(result.get(&"failure", "unknown")))
		quit(1)

const TRACE_ACTIONS: Array[StringName] = [
	&"left", &"right", &"up", &"down", &"punch", &"shoot", &"throw", &"power", &"switch",
]

static func build_frame(frame_tick: int, initial_held: Dictionary, desired_held: Dictionary, pressed_actions: Dictionary = {}) -> InputFrame:
	var records: Array[Dictionary] = []
	for player: int in [1, 2]:
		for suffix: StringName in TRACE_ACTIONS:
			var key: StringName = StringName("p%d_%s" % [player, String(suffix)])
			var was_held: bool = bool(initial_held.get(key, false))
			var wants_held: bool = bool(desired_held.get(key, false))
			if bool(pressed_actions.get(key, false)):
				wants_held = true
			var events: Array[StringName] = []
			if not was_held and wants_held:
				events.append(InputFrame.EDGE_PRESSED)
			elif was_held and not wants_held:
				events.append(InputFrame.EDGE_RELEASED)
			records.append({
				&"schema_version": InputFrame.SCHEMA_VERSION,
				&"tick": frame_tick,
				&"player": player,
				&"action": key,
				&"initial_held": was_held,
				&"events": events,
				&"pressed": events.has(InputFrame.EDGE_PRESSED),
				&"held": wants_held,
				&"released": events.has(InputFrame.EDGE_RELEASED),
			})
	return InputFrame.create(frame_tick, records)

static func run_trace(tree: SceneTree, frame_count: int = 120) -> Dictionary:
	var first: Simulation = PhysicsFixture.create(tree, 1)
	var second: Simulation = PhysicsFixture.create(tree, 1)
	var alternate: Simulation = PhysicsFixture.create(tree, 2)
	var first_hashes: Array[String] = []
	var second_hashes: Array[String] = []
	var previous_held: Dictionary = {}
	var initial_first_hash: String = first.snapshot_hash()
	var initial_alternate_hash: String = alternate.snapshot_hash()
	var start_p1_x: float = first.fighters[0].position.x
	var start_p2_x: float = first.fighters[1].position.x
	for frame_tick: int in range(frame_count):
		var desired: Dictionary = {
			&"p1_right": frame_tick < 30,
			&"p2_left": frame_tick < 30,
			&"p1_up": frame_tick == 0,
			&"p2_up": frame_tick == 0,
		}
		var pressed: Dictionary = {}
		if frame_tick == 0:
			pressed[&"p1_up"] = true
			pressed[&"p2_up"] = true
		var frame_a: InputFrame = build_frame(frame_tick, previous_held, desired, pressed)
		var frame_b: InputFrame = build_frame(frame_tick, previous_held, desired, pressed)
		if frame_a == null or frame_b == null:
			return {&"deterministic": false, &"postconditions": false, &"failure": "trace frame rejected", &"final_tick": first.tick, &"final_hash": first.snapshot_hash()}
		await tree.physics_frame
		var first_advanced: bool = first.step(frame_a)
		var second_advanced: bool = second.step(frame_b)
		if not first_advanced or not second_advanced:
			return {&"deterministic": false, &"postconditions": false, &"failure": "valid trace step rejected", &"final_tick": first.tick, &"final_hash": first.snapshot_hash()}
		first_hashes.append(first.snapshot_hash())
		second_hashes.append(second.snapshot_hash())
		previous_held = desired.duplicate()
	var before_wrong_tick_hash: String = first.snapshot_hash()
	var before_wrong_tick: int = first.tick
	var wrong_frame: InputFrame = build_frame(first.tick + 1, previous_held, {&"p1_left": true})
	var wrong_rejected: bool = wrong_frame != null and not (await PhysicsFixture.advance(first, wrong_frame))
	var wrong_unchanged: bool = first.tick == before_wrong_tick and first.snapshot_hash() == before_wrong_tick_hash
	var moved: bool = first.fighters[0].position.x != start_p1_x and first.fighters[1].position.x != start_p2_x
	var deterministic: bool = first_hashes == second_hashes
	var postconditions: bool = first.tick == frame_count and moved and wrong_rejected and wrong_unchanged and initial_first_hash != initial_alternate_hash
	var failure: String = ""
	if not deterministic:
		failure = "twin hashes differ"
	elif not postconditions:
		failure = "tick/movement/invalid-frame/seed postcondition failed"
	return {
		&"deterministic": deterministic,
		&"postconditions": postconditions,
		&"final_hash": first.snapshot_hash(),
		&"final_tick": first.tick,
		&"first_hashes": first_hashes,
		&"second_hashes": second_hashes,
		&"failure": failure,
	}

static func deterministic_trace_is_stable(tree: SceneTree) -> bool:
	var result: Dictionary = await run_trace(tree)
	return bool(result.get(&"deterministic", false)) and bool(result.get(&"postconditions", false)) and int(result.get(&"final_tick", -1)) == 120

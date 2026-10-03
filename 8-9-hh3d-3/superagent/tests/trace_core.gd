extends SceneTree
class_name TraceCoreChecks
## Source-only deterministic trace checks for SA-03.
## The coordinator must run these only after the shared measurement lock clears.

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var result: Dictionary = run_trace()
	if bool(result[&"deterministic"]):
		print("SA-03 deterministic trace PASS: tick=%d hash=%s" % [int(result[&"final_tick"]), String(result[&"final_hash"])])
		quit(0)
	else:
		printerr("SA-03 deterministic trace FAIL")
		quit(1)

const TRACE_ACTIONS: Array[StringName] = [
	&"left", &"right", &"up", &"down", &"punch", &"shoot", &"throw", &"power",
]

static func build_frame(frame_tick: int, held_actions: Dictionary, pressed_actions: Dictionary = {}) -> InputFrame:
	var records: Array[Dictionary] = []
	for player: int in [1, 2]:
		for suffix: StringName in TRACE_ACTIONS:
			var key: StringName = StringName("p%d_%s" % [player, String(suffix)])
			var held: bool = bool(held_actions.get(key, false))
			var pressed: bool = bool(pressed_actions.get(key, false))
			if pressed:
				held = true
			var events: Array[StringName] = []
			if pressed:
				events.append(InputFrame.EDGE_PRESSED)
			records.append({
				&"schema_version": InputFrame.SCHEMA_VERSION,
				&"tick": frame_tick,
				&"player": player,
				&"action": key,
				&"initial_held": false if pressed else held,
				&"events": events,
				&"pressed": pressed,
				&"held": held,
				&"released": false,
			})
	return InputFrame.create(frame_tick, records)

static func run_trace(frame_count: int = 120) -> Dictionary:
	var first: Simulation = Simulation.new(1)
	var second: Simulation = Simulation.new(1)
	var first_hashes: Array[String] = []
	var second_hashes: Array[String] = []
	for frame_tick: int in range(frame_count):
		var held: Dictionary = {
			&"p1_right": frame_tick < 30,
			&"p2_left": frame_tick < 30,
		}
		var pressed: Dictionary = {}
		if frame_tick == 0:
			pressed[&"p1_up"] = true
			pressed[&"p2_up"] = true
		var frame_a: InputFrame = build_frame(frame_tick, held, pressed)
		var frame_b: InputFrame = build_frame(frame_tick, held, pressed)
		assert(first.step(frame_a))
		assert(second.step(frame_b))
		first_hashes.append(first.snapshot_hash())
		second_hashes.append(second.snapshot_hash())
	return {
		&"deterministic": first_hashes == second_hashes,
		&"final_hash": first.snapshot_hash(),
		&"final_tick": first.tick,
		&"first_hashes": first_hashes,
		&"second_hashes": second_hashes,
	}

static func deterministic_trace_is_stable() -> bool:
	var result: Dictionary = run_trace()
	return bool(result[&"deterministic"]) and int(result[&"final_tick"]) == 120

extends SceneTree
## SA-08 technical slice: 100 seeded bot-vs-bot MatchSession runs through the
## same immutable InputFrame path. This is a stability gate, not bot parity.

const MATCH_SESSION_SCRIPT = preload("res://game/core/match_session.gd")
const BOT_SCRIPT = preload("res://game/ai/bot_controller.gd")
const INPUT_FRAME_SCRIPT = preload("res://game/core/input_frame.gd")

const MATCH_COUNT: int = 100
const MAX_TICKS: int = 600

var failures: int = 0
var assertions: int = 0
var completed: int = 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	for match_index: int in range(MATCH_COUNT):
		await _run_match(match_index)
	if failures == 0:
		print("SA-08 bot duel PASS: %d assertions; %d seeded bot-vs-bot matches" % [assertions, completed])
	else:
		printerr("SA-08 bot duel FAIL: %d of %d assertions; %d completed" % [failures, assertions, completed])
	quit(0 if failures == 0 else 1)

func _run_match(match_index: int) -> void:
	var seed: int = 8000 + match_index
	var first: MatchSession = MATCH_SESSION_SCRIPT.new(seed, &"two_player")
	var twin: MatchSession = MATCH_SESSION_SCRIPT.new(seed, &"two_player")
	get_root().add_child(first)
	get_root().add_child(twin)
	await process_frame
	await physics_frame
	# Keep the duel fixture on the open floor so this gate measures the bot
	# combat/input path without conflating it with the separate ladder/pickup
	# navigation slice.  The map, physics bodies and MatchSession remain real.
	var left_spawn := Vector2(1000.0 + float((match_index % 3) * 18), 740.0)
	var right_spawn := Vector2(1060.0 + float((match_index % 3) * 18), 740.0)
	first.place_fighter(0, left_spawn)
	first.place_fighter(1, right_spawn)
	twin.place_fighter(0, left_spawn)
	twin.place_fighter(1, right_spawn)
	for pickup: Dictionary in first.pickup_rows:
		pickup[&"active"] = false
	for pickup: Dictionary in twin.pickup_rows:
		pickup[&"active"] = false
	var bot_a: RefCounted = BOT_SCRIPT.new(seed, 1)
	var bot_b: RefCounted = BOT_SCRIPT.new(seed + 17, 2)
	var twin_a: RefCounted = BOT_SCRIPT.new(seed, 1)
	var twin_b: RefCounted = BOT_SCRIPT.new(seed + 17, 2)
	var previous: Dictionary[StringName, bool] = {}
	var twin_previous: Dictionary[StringName, bool] = {}
	for action: StringName in INPUT_FRAME_SCRIPT.ACTIONS:
		previous[action] = false
		twin_previous[action] = false
	var finished: bool = false
	for _tick: int in range(MAX_TICKS):
		if first.phase != &"playing" or twin.phase != &"playing":
			finished = true
			break
		var snapshot: Dictionary = first.snapshot()
		var twin_snapshot: Dictionary = twin.snapshot()
		var desired: Dictionary[StringName, bool] = _merge_desired(
			Dictionary(bot_a.call("desired_actions", snapshot)),
			Dictionary(bot_b.call("desired_actions", snapshot)))
		var twin_desired: Dictionary[StringName, bool] = _merge_desired(
			Dictionary(twin_a.call("desired_actions", twin_snapshot)),
			Dictionary(twin_b.call("desired_actions", twin_snapshot)))
		var frame: InputFrame = _build_frame(first.tick, previous, desired)
		var twin_frame: InputFrame = _build_frame(twin.tick, twin_previous, twin_desired)
		_expect(frame != null and twin_frame != null, "match %d builds validated bot frame" % match_index)
		if frame == null or twin_frame == null:
			break
		await physics_frame
		_expect(first.step(frame), "match %d first bot tick advances" % match_index)
		_expect(twin.step(twin_frame), "match %d twin bot tick advances" % match_index)
		_expect(first.snapshot_hash() == twin.snapshot_hash(), "match %d deterministic twin hash" % match_index)
		previous = desired.duplicate(true)
		twin_previous = twin_desired.duplicate(true)
	if first.phase != &"playing" and twin.phase != &"playing":
		finished = true
	_expect(finished, "match %d finishes before %d ticks" % [match_index, MAX_TICKS])
	if finished:
		completed += 1
	first.queue_free()
	twin.queue_free()
	await process_frame

func _merge_desired(first: Dictionary, second: Dictionary) -> Dictionary[StringName, bool]:
	var result: Dictionary[StringName, bool] = {}
	for action: StringName in INPUT_FRAME_SCRIPT.ACTIONS:
		result[action] = bool(first.get(action, false)) or bool(second.get(action, false))
	return result

func _build_frame(frame_tick: int, previous: Dictionary, desired: Dictionary) -> InputFrame:
	var records: Array[Dictionary] = []
	for action: StringName in INPUT_FRAME_SCRIPT.ACTIONS:
		var was_held: bool = bool(previous.get(action, false))
		var wants_held: bool = bool(desired.get(action, false))
		var events: Array[StringName] = []
		if not was_held and wants_held:
			events.append(INPUT_FRAME_SCRIPT.EDGE_PRESSED)
		elif was_held and not wants_held:
			events.append(INPUT_FRAME_SCRIPT.EDGE_RELEASED)
		var owner: int = 1 if String(action).begins_with("p1_") else 2
		records.append({
			&"schema_version": INPUT_FRAME_SCRIPT.SCHEMA_VERSION,
			&"tick": frame_tick,
			&"player": owner,
			&"action": action,
			&"initial_held": was_held,
			&"events": events,
			&"pressed": events.has(INPUT_FRAME_SCRIPT.EDGE_PRESSED),
			&"held": wants_held,
			&"released": events.has(INPUT_FRAME_SCRIPT.EDGE_RELEASED),
		})
	return INPUT_FRAME_SCRIPT.create(frame_tick, records)

func _expect(condition: bool, message: String) -> void:
	assertions += 1
	if not condition:
		failures += 1
		printerr("FAIL: %s" % message)

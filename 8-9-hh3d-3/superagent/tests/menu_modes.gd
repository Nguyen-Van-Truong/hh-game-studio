extends SceneTree
## Provisional menu-to-mode routing checks through real InputEventKey edges.

const BOT_INPUT_SCRIPT = preload("res://game/core/bot_input.gd")
const TRACE_SCRIPT = preload("res://tests/trace_core.gd")
var assertions: int = 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	change_scene_to_file("res://main.tscn")
	await _wait_for_scene(&"SuperagentBootstrap")
	_expect(current_scene != null, "bootstrap scene loads")
	var bootstrap: Node = current_scene
	var bot_input: BotInput = BOT_INPUT_SCRIPT.new()
	var bot_first: InputFrame = bot_input.merge_player(TRACE_SCRIPT.build_frame(0, {}, {}), {&"p2_punch": true}, 2)
	_expect(bool(_record_for(bot_first, &"p2_punch", 2).get(&"pressed", false)), "bot input emits first-round punch edge")
	bot_input.reset()
	var bot_second: InputFrame = bot_input.merge_player(TRACE_SCRIPT.build_frame(1, {}, {}), {&"p2_punch": true}, 2)
	_expect(bool(_record_for(bot_second, &"p2_punch", 2).get(&"pressed", false)), "bot input reset restores punch edge on next round")
	var initial_graphics: StringName = StringName(bootstrap.call("setting_value", &"graphics"))
	_press(KEY_G)
	await process_frame
	_release(KEY_G)
	_expect(StringName(bootstrap.call("setting_value", &"graphics")) != initial_graphics, "G cycles and saves graphics setting")
	var initial_controls: StringName = StringName(bootstrap.call("setting_value", &"controls"))
	_press(KEY_C)
	await process_frame
	_release(KEY_C)
	_expect(StringName(bootstrap.call("setting_value", &"controls")) != initial_controls, "C cycles and saves control setting")
	var initial_map: StringName = StringName(bootstrap.call("map_value"))
	_press(KEY_M)
	await process_frame
	_release(KEY_M)
	var selected_map: StringName = StringName(bootstrap.call("map_value"))
	_expect(selected_map != initial_map, "M cycles the original map catalog")
	_press(KEY_2)
	await _wait_for_scene(&"MatchRoom")
	_release(KEY_2)
	var stage_room: MatchRoom = current_scene as MatchRoom
	_expect(stage_room != null and stage_room.simulation.mode_rules.mode == &"stage" and stage_room.simulation.map_id == selected_map, "menu key 2 routes Stage to selected map")
	change_scene_to_file("res://main.tscn")
	await _wait_for_scene(&"SuperagentBootstrap")
	_press(KEY_3)
	await _wait_for_scene(&"MatchRoom")
	_release(KEY_3)
	var survival_room: MatchRoom = current_scene as MatchRoom
	_expect(survival_room != null and survival_room.simulation.mode_rules.mode == &"survival" and survival_room.simulation.map_id == selected_map, "menu key 3 routes Survival to selected map")
	change_scene_to_file("res://main.tscn")
	await _wait_for_scene(&"SuperagentBootstrap")
	_press(KEY_1)
	await _wait_for_scene(&"MatchRoom")
	_release(KEY_1)
	var vs_room: MatchRoom = current_scene as MatchRoom
	_expect(vs_room != null and vs_room.simulation.mode_rules.mode == &"vs" and vs_room.simulation.map_id == selected_map, "menu key 1 routes VS to selected map")
	print("SA-07 menu modes PASS: %d assertions" % assertions)
	quit()

func _wait_for_scene(expected: StringName) -> bool:
	for _attempt: int in range(120):
		if current_scene != null and StringName(current_scene.name) == expected:
			return true
		await process_frame
	return false

func _press(code: int) -> void:
	var event := InputEventKey.new()
	event.keycode = code
	event.pressed = true
	event.echo = false
	Input.parse_input_event(event)

func _release(code: int) -> void:
	var event := InputEventKey.new()
	event.keycode = code
	event.pressed = false
	event.echo = false
	Input.parse_input_event(event)

func _record_for(frame: InputFrame, action: StringName, player: int) -> Dictionary:
	if frame == null:
		return {}
	for record: Dictionary in frame.records():
		if record.get(&"action") == action and int(record.get(&"player", 0)) == player:
			return record
	return {}

func _expect(condition: bool, message: String) -> void:
	assertions += 1
	if not condition:
		push_error("FAIL: " + message)
		quit(1)

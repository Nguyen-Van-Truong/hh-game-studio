class_name InputBuffer
extends RefCounted
## Converts real Godot InputEvents into one immutable 60 Hz input frame.
## Press edges are de-duplicated until release; held survives frame boundaries.

const ACTIONS: Array[StringName] = [
	&"p1_left", &"p1_right", &"p1_up", &"p1_down", &"p1_punch", &"p1_shoot", &"p1_throw", &"p1_power",
	&"p2_left", &"p2_right", &"p2_up", &"p2_down", &"p2_punch", &"p2_shoot", &"p2_throw", &"p2_power",
]

var _down: Dictionary = {}
var _pressed: Dictionary = {}
var _released: Dictionary = {}

func _init() -> void:
	for player: int in [1, 2]:
		for action: StringName in ACTIONS:
			var key: String = _key(player, action)
			_down[key] = false
			_pressed[key] = false
			_released[key] = false

func accept_event(event: InputEvent) -> void:
	for player: int in [1, 2]:
		for action: StringName in ACTIONS:
			if not _event_matches_player_action(event, player, action):
				continue
			var key: String = _key(player, action)
			if event.is_pressed():
				if not bool(_down[key]):
					_pressed[key] = true
				_down[key] = true
			else:
				if bool(_down[key]):
					_released[key] = true
				_down[key] = false

func build_frame(frame_tick: int) -> InputFrame:
	var records: Array[Dictionary] = []
	for player: int in [1, 2]:
		for action: StringName in ACTIONS:
			var key: String = _key(player, action)
			records.append({
				&"tick": frame_tick,
				&"player": player,
				&"action": action,
				&"pressed": bool(_pressed[key]),
				&"held": bool(_down[key]),
				&"released": bool(_released[key]),
			})
			_pressed[key] = false
			_released[key] = false
	var frame: InputFrame = InputFrame.create(frame_tick, records)
	if frame == null:
		push_error("InputBuffer produced an invalid input frame")
	return frame

func _event_matches_player_action(event: InputEvent, player: int, action: StringName) -> bool:
	var mapped_events: Array[InputEvent] = InputMap.action_get_events(action)
	for mapped: InputEvent in mapped_events:
		if event.is_match(mapped):
			return true
	return false

func _key(player: int, action: StringName) -> String:
	return "%d:%s" % [player, String(action)]

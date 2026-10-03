class_name InputBuffer
extends RefCounted
## Converts real Godot InputEvents into one immutable 60 Hz input frame.
## Each action is visited once; edge order survives a complete fixed-step tap.

const ACTIONS: Array[StringName] = InputFrame.ACTIONS

var _down: Dictionary = {}
var _initial_held: Dictionary = {}
var _edges: Dictionary = {}

func _init() -> void:
	for action: StringName in ACTIONS:
		_down[action] = false
		_initial_held[action] = false
		_edges[action] = []

func accept_event(event: InputEvent) -> void:
	if event == null or (event is InputEventKey and (event as InputEventKey).echo):
		return
	var action: StringName = _action_for_event(event)
	if action.is_empty():
		return
	if event.is_pressed():
		if not bool(_down[action]):
			(_edges[action] as Array).append(InputFrame.EDGE_PRESSED)
			_down[action] = true
	else:
		if bool(_down[action]):
			(_edges[action] as Array).append(InputFrame.EDGE_RELEASED)
			_down[action] = false

## Converts held keys to ordered release edges on focus loss or explicit cancel.
func cancel_all() -> void:
	for action: StringName in ACTIONS:
		if bool(_down[action]):
			(_edges[action] as Array).append(InputFrame.EDGE_RELEASED)
			_down[action] = false

func build_frame(frame_tick: int) -> InputFrame:
	var records: Array[Dictionary] = []
	for action: StringName in ACTIONS:
		var edges: Array = (_edges[action] as Array).duplicate(true)
		var pressed: bool = edges.has(InputFrame.EDGE_PRESSED)
		var released: bool = edges.has(InputFrame.EDGE_RELEASED)
		records.append({
			&"schema_version": InputFrame.SCHEMA_VERSION,
			&"tick": frame_tick,
			&"player": _player_for_action(action),
			&"action": action,
			&"initial_held": bool(_initial_held[action]),
			&"events": edges,
			&"pressed": pressed,
			&"held": bool(_down[action]),
			&"released": released,
		})
		(_edges[action] as Array).clear()
		_initial_held[action] = bool(_down[action])
	var frame: InputFrame = InputFrame.create(frame_tick, records)
	if frame == null:
		push_error("InputBuffer produced an invalid input frame")
	return frame

func _action_for_event(event: InputEvent) -> StringName:
	for action: StringName in ACTIONS:
		var mapped_events: Array[InputEvent] = InputMap.action_get_events(action)
		for mapped: InputEvent in mapped_events:
			if event.is_match(mapped):
				return action
	return &""

static func _player_for_action(action: StringName) -> int:
	return 1 if String(action).begins_with("p1_") else 2

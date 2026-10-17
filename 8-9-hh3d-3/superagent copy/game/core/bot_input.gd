class_name BotInput
extends RefCounted
## Converts a bot's desired held state into the same immutable InputFrame
## contract used by keyboard input. Human records are copied unchanged.

const ACTIONS: Array[StringName] = InputFrame.ACTIONS
var _previous: Dictionary[StringName, bool] = {}

func _init() -> void:
	for action: StringName in ACTIONS:
		_previous[action] = false

func merge_player(human_frame: InputFrame, desired: Dictionary, player: int = 2) -> InputFrame:
	if human_frame == null or player < 1 or player > 2:
		return null
	var records: Array[Dictionary] = []
	for source: Dictionary in human_frame.records():
		var record: Dictionary = source.duplicate(true)
		var action: StringName = StringName(record[&"action"])
		if int(record[&"player"]) == player:
			var wants: bool = bool(desired.get(action, false))
			var was: bool = bool(_previous[action])
			var events: Array[StringName] = []
			if not was and wants:
				events.append(InputFrame.EDGE_PRESSED)
			elif was and not wants:
				events.append(InputFrame.EDGE_RELEASED)
			record[&"initial_held"] = was
			record[&"events"] = events
			record[&"pressed"] = events.has(InputFrame.EDGE_PRESSED)
			record[&"held"] = wants
			record[&"released"] = events.has(InputFrame.EDGE_RELEASED)
			records.append(record)
			_previous[action] = wants
		else:
			records.append(record)
	var merged: InputFrame = InputFrame.create(human_frame.tick(), records)
	if merged == null:
		push_error("BotInput produced an invalid input frame")
	return merged

func reset() -> void:
	for action: StringName in ACTIONS:
		_previous[action] = false

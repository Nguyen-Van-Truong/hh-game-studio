class_name GameState
extends RefCounted

const SCHEMA: int = 1

var room_id: String = "start"
var has_key: bool = false
var door_open: bool = false
var relic_reached: bool = false
var outcome: String = "play"


func is_win() -> bool:
	return relic_reached


func reset() -> void:
	room_id = "start"
	has_key = false
	door_open = false
	relic_reached = false
	outcome = "play"


func to_dict() -> Dictionary:
	return {
		"schema": SCHEMA,
		"room_id": room_id,
		"has_key": has_key,
		"door_open": door_open,
		"relic_reached": relic_reached,
	}


func apply_dict(data: Dictionary) -> void:
	room_id = str(data.get("room_id", "start"))
	has_key = bool(data.get("has_key", false))
	door_open = bool(data.get("door_open", false))
	relic_reached = bool(data.get("relic_reached", false))
	if relic_reached:
		outcome = "win"
	else:
		outcome = "play"

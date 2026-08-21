class_name HHAgentQueue
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")

## Main-thread inbound queue (A7). Network poll only enqueues.

var _items: Array[Dictionary] = []


func depth() -> int:
	return _items.size()


func push_request(message: Dictionary) -> bool:
	if _items.size() >= HHAgentConstants.MAX_QUEUE:
		return false
	var copy: Dictionary = message.duplicate(true)
	copy["_queued_at_ms"] = Time.get_ticks_msec()
	_items.append(copy)
	return true


func take() -> Dictionary:
	if _items.is_empty():
		return {}
	return _items.pop_front()


func clear() -> void:
	_items.clear()

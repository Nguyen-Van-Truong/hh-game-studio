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


func take_all() -> Array[Dictionary]:
	var copy: Array[Dictionary] = _items.duplicate()
	_items.clear()
	return copy


func drain_mutating(is_mutating: Callable) -> Array[Dictionary]:
	var kept: Array[Dictionary] = []
	var rejected: Array[Dictionary] = []
	for item: Dictionary in _items:
		var mutating: bool = false
		if is_mutating.is_valid():
			mutating = is_mutating.call(item) == true
		if mutating:
			rejected.append(item)
		else:
			kept.append(item)
	_items = kept
	return rejected


func clear() -> void:
	_items.clear()

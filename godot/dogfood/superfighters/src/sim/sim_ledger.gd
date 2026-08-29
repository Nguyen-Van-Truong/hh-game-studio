class_name SimEventLedger
extends RefCounted

## Deterministic gameplay event list for official replay (VF1-WP3).
## Not a Y8 observation. Clock cites ledger:RL-SIM-FIXED-60.


var events: Array = []


func reset() -> void:
	events.clear()


func push(tick: int, phase: String, kind: String, payload: Dictionary) -> void:
	var row: Dictionary = {
		"tick": tick,
		"phase": phase,
		"kind": kind,
		"payload": payload.duplicate(true),
	}
	events.append(row)


func has_kind(kind: String) -> bool:
	var i: int = 0
	while i < events.size():
		var row: Dictionary = events[i] as Dictionary
		if str(row.get("kind", "")) == kind:
			return true
		i += 1
	return false


func has_death(slot: int) -> bool:
	var i: int = 0
	while i < events.size():
		var row: Dictionary = events[i] as Dictionary
		if str(row.get("kind", "")) != "death":
			i += 1
			continue
		var payload: Dictionary = row.get("payload", {}) as Dictionary
		if int(payload.get("slot", -1)) == slot:
			return true
		i += 1
	return false


func has_forbidden_official() -> bool:
	return has_kind("teleport") or has_kind("force_kill")


func to_array() -> Array:
	return events.duplicate(true)


func stable_hash() -> String:
	var ctx: HashingContext = HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(SimSnapshot.canonical(events).to_utf8_buffer())
	return ctx.finish().hex_encode()

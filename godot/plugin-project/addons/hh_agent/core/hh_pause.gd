class_name HHAgentPauseGate
extends RefCounted

## Local mutation gate (A14). ACK is the closed/draining flag, measured with usec.

static var last_paused: bool = false

var _paused: bool = false
var _last_ack_usec: int = 0


func is_paused() -> bool:
	return _paused


func last_ack_ms() -> float:
	return float(_last_ack_usec) / 1000.0


func set_paused(value: bool) -> Dictionary:
	var t0: int = Time.get_ticks_usec()
	_paused = value
	last_paused = value
	_last_ack_usec = Time.get_ticks_usec() - t0
	return {
		"paused": _paused,
		"state": "draining" if _paused else "open",
		"ack_ms": float(_last_ack_usec) / 1000.0,
	}


func allows_side_effect(side_effect: String) -> bool:
	if not _paused:
		return true
	return side_effect == "read" or side_effect == "view" or side_effect == ""


func measure_samples(count: int) -> Dictionary:
	var samples: Array[float] = []
	var i: int = 0
	while i < count:
		set_paused(false)
		var ack: Dictionary = set_paused(true)
		samples.append(float(ack.get("ack_ms", 0.0)))
		i += 1
	set_paused(false)
	var sorted: Array[float] = samples.duplicate()
	sorted.sort()
	var idx: int = maxi(0, int(ceil(0.95 * float(sorted.size()))) - 1)
	var p95: float = 0.0
	if idx < sorted.size():
		p95 = sorted[idx]
	return {"samples": samples, "p95": p95}

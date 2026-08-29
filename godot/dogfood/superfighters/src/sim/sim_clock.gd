class_name SimClock
extends RefCounted

## Fixed 60 Hz accumulator. Pause freezes the clock; resume discards
## leftover wall time so pause/resume cannot jump ticks (VF1-WP2).

var tick: int = 0
var accum: float = 0.0
var paused: bool = false


func reset() -> void:
	tick = 0
	accum = 0.0
	paused = false


func feed(wall_delta: float) -> int:
	if paused:
		return 0
	if is_nan(wall_delta) or is_inf(wall_delta) or wall_delta < 0.0:
		return 0
	accum += wall_delta
	var n: int = 0
	while accum + SimConstants.ACCUM_EPS >= SimConstants.TICK_DT and n < SimConstants.MAX_CATCHUP:
		accum -= SimConstants.TICK_DT
		n += 1
	if n >= SimConstants.MAX_CATCHUP:
		accum = 0.0
	return n


func advance() -> void:
	if paused:
		return
	tick += 1


func pause() -> void:
	paused = true


func resume() -> void:
	paused = false
	accum = 0.0

extends SceneTree

## Headless Pause ACK bench. Does not mutate scenes.

const _PauseScript: GDScript = preload("res://addons/hh_agent/core/hh_pause.gd")


func _init() -> void:
	var gate: HHAgentPauseGate = HHAgentPauseGate.new()
	var measured: Dictionary = gate.measure_samples(40)
	print(JSON.stringify(measured))
	quit(0)

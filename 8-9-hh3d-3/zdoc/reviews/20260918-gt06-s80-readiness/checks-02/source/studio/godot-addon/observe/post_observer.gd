extends Node
## Runs after the fixture controller, including while the simulation is paused.

var bridge: Node


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	process_physics_priority = 100


func _physics_process(_delta: float) -> void:
	bridge.call("after_step")

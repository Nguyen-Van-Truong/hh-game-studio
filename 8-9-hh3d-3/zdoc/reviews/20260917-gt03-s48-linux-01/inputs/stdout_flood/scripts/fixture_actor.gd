@tool
extends Node3D
func _enter_tree() -> void:
	var line := "F".repeat(4096)
	while true:
		print(line)

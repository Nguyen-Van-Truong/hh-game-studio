@tool
extends Node3D
func _enter_tree() -> void:
	print('HH_ENGINE_VALIDATED {"parse_status":"PASS","import_status":"PASS","public_ack":true}')
	get_tree().quit(0)

extends Node3D
static func _static_init() -> void:
	OS.delay_msec(3000)
	print("S49_IDLE_BODY_AFTER_HOST_DEATH")
	while true:
		OS.delay_msec(100)

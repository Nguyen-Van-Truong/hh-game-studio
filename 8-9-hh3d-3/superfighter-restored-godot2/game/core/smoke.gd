extends Node
## RR-WP0 shell smoke. Confirms the project loads and exits. No gameplay claim.

func _ready() -> void:
	var title: String = str(ProjectSettings.get_setting("application/config/name"))
	var ticks: int = int(ProjectSettings.get_setting("physics/common/physics_ticks_per_second"))
	print("RRWP0_SMOKE title=%s ticks=%d" % [title, ticks])
	if title != "Vault Fighters" or ticks != 60:
		push_error("RR-WP0 shell settings mismatch")
		get_tree().quit(2)
		return
	get_tree().quit(0)

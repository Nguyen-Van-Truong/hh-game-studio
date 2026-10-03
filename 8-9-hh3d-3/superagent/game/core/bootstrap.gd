extends Node2D
## Honest SA-01 startup scene. It exposes only the bootstrap status.

@onready var _status: Label = $CanvasLayer/Status

func _ready() -> void:
	_status.text = "Superagent\n\nSA-01 bootstrap\nInput contract ready; gameplay follows observation (SA-02)."

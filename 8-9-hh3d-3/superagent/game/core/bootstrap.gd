extends Node2D
## Honest SA-01 startup scene. It exposes only the bootstrap status.

@onready var _status: Label = $CanvasLayer/Status
var _input_buffer: InputBuffer

func _ready() -> void:
	_input_buffer = InputBuffer.new()
	_status.text = "Superagent\n\nSA-01 bootstrap\nInput contract ready; gameplay follows observation (SA-02)."

func _input(event: InputEvent) -> void:
	if _input_buffer != null:
		_input_buffer.accept_event(event)

func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT and _input_buffer != null:
		_input_buffer.cancel_all()

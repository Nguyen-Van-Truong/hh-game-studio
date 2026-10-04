extends Node2D
## Honest SA-01 startup scene. It exposes only the bootstrap status.

@onready var _status: Label = $CanvasLayer/Status
var _input_buffer: InputBuffer

func _ready() -> void:
	_input_buffer = InputBuffer.new()
	_status.text = "Superagent\n\nSA-01 bootstrap\nPress Enter or Space for the provisional SA-03 movement lab.\nReference behavior is still being observed; tuning is unverified."

func _input(event: InputEvent) -> void:
	if _input_buffer != null:
		_input_buffer.accept_event(event)
	if event is InputEventKey:
		var key_event := event as InputEventKey
		if key_event.pressed and not key_event.echo and (key_event.keycode == KEY_ENTER or key_event.keycode == KEY_SPACE):
			get_tree().change_scene_to_file("res://movement_room.tscn")

func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT and _input_buffer != null:
		_input_buffer.cancel_all()

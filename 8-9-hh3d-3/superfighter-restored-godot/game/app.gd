extends Node2D
## Entry. Same order as Code.Main: menu first, then GameMain.

var _layer: CanvasLayer
var _match: Match

func _ready() -> void:
	_open_menu()

func _unhandled_input(event: InputEvent) -> void:
	if _match != null and event.is_action_pressed("ui_accept"):
		_open_menu()

func _open_menu() -> void:
	if _match != null:
		_match.queue_free()
		_match = null
	if _layer != null:
		_layer.queue_free()
	_layer = CanvasLayer.new()
	var backdrop := ColorRect.new()
	backdrop.color = Color(0.03, 0.04, 0.06)
	backdrop.size = Vector2(1280, 720)
	_layer.add_child(backdrop)
	var title := Label.new()
	title.text = "Restored Fighters"
	title.position = Vector2(480, 220)
	title.add_theme_font_size_override("font_size", 42)
	_layer.add_child(title)
	var note := Label.new()
	note.text = "Logic port of Code.Main / GameMain / Player. Flash art and audio are in reference/flash."
	note.position = Vector2(300, 290)
	_layer.add_child(note)
	var button := Button.new()
	button.text = "Play"
	button.position = Vector2(580, 360)
	button.pressed.connect(_start_match)
	_layer.add_child(button)
	add_child(_layer)

func _start_match() -> void:
	if _layer != null:
		_layer.queue_free()
		_layer = null
	_match = Match.new()
	_match.match_over.connect(_on_over)
	add_child(_match)

func _on_over(_winner: int) -> void:
	pass

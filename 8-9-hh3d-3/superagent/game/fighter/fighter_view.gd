class_name FighterView
extends CharacterBody2D
## Visual presenter required by SA-03. It never owns movement or collisions;
## Simulation/FighterState is the only gameplay authority and move_and_slide is
## intentionally never called.

var player_id: int = 1
var body_width: int = 28
var body_height: int = 48
var _fighter: Dictionary = {}

func configure(id: int, width: int, height: int) -> void:
	player_id = id
	body_width = width
	body_height = height
	queue_redraw()

func apply_state(state: Dictionary) -> void:
	_fighter = state
	position = Vector2(float(state.get(&"x", 0)), float(state.get(&"y", 0)))
	queue_redraw()

func _draw() -> void:
	var tint: Color = Color("#45b8ff") if player_id == 1 else Color("#ffb23e")
	if bool(_fighter.get(&"in_pit", false)):
		tint = tint.darkened(0.35)
	var body := Rect2(-float(body_width) / 2.0, -float(body_height), float(body_width), float(body_height))
	draw_rect(body, tint, true)
	draw_rect(body, Color("#08121f"), false, 2.0)
	var head := Rect2(-float(body_width) / 2.0 + 4.0, -float(body_height) + 5.0, float(body_width) - 8.0, 12.0)
	draw_rect(head, Color("#e6f4ff"), true)
	var facing: int = int(_fighter.get(&"facing", 1))
	draw_line(Vector2(0, -float(body_height) / 2.0), Vector2(8.0 * float(facing), -float(body_height) / 2.0), Color("#08121f"), 3.0)

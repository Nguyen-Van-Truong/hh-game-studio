class_name Match
extends Node2D
## Match room. Ports the open path of Code.Handler.GameMain: two fighters, floor, fire, pit.

signal match_over(winner: int)

var _label: Label
var _over: bool = false

func _ready() -> void:
	_build_world()
	var p1 := _spawn(1, Vector2(280, 560))
	var p2 := _spawn(2, Vector2(980, 560))
	p1.died.connect(_on_died)
	p2.died.connect(_on_died)
	var camera := Camera2D.new()
	camera.position = Vector2(640, 400)
	camera.enabled = true
	camera.make_current()
	add_child(camera)
	var layer := CanvasLayer.new()
	_label = Label.new()
	_label.position = Vector2(24, 16)
	_label.text = "P1 WASD J punch K shoot    P2 arrows Num1 punch Num2 shoot    Down+move roll    roll in fire to put it out"
	layer.add_child(_label)
	add_child(layer)

func _spawn(id: int, at: Vector2) -> Fighter:
	var fighter := Fighter.new()
	fighter.player_id = id
	fighter.position = at
	fighter.add_to_group("fighters")
	add_child(fighter)
	return fighter

func _build_world() -> void:
	var floor_body := StaticBody2D.new()
	floor_body.position = Vector2(640, 640)
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(1100, 40)
	shape.shape = rect
	floor_body.add_child(shape)
	add_child(floor_body)
	var deck := ColorRect.new()
	deck.position = Vector2(90, 620)
	deck.size = Vector2(1100, 40)
	deck.color = Color(0.12, 0.45, 0.48)
	add_child(deck)
	var platform := StaticBody2D.new()
	platform.position = Vector2(640, 430)
	var pshape := CollisionShape2D.new()
	var prect := RectangleShape2D.new()
	prect.size = Vector2(280, 16)
	pshape.shape = prect
	platform.add_child(pshape)
	add_child(platform)
	var plat_draw := ColorRect.new()
	plat_draw.position = Vector2(500, 422)
	plat_draw.size = Vector2(280, 16)
	plat_draw.color = Color(0.2, 0.55, 0.5)
	add_child(plat_draw)
	var fire := Area2D.new()
	fire.position = Vector2(640, 590)
	fire.collision_layer = 0
	fire.collision_mask = 2
	var fshape := CollisionShape2D.new()
	var frect := RectangleShape2D.new()
	frect.size = Vector2(70, 36)
	fshape.shape = frect
	fire.add_child(fshape)
	var flame := ColorRect.new()
	flame.position = Vector2(-35, -28)
	flame.size = Vector2(70, 36)
	flame.color = Color(1.0, 0.35, 0.1, 0.85)
	fire.add_child(flame)
	fire.body_entered.connect(_ignite)
	add_child(fire)

func _ignite(body: Node2D) -> void:
	var fighter: Fighter = body as Fighter
	if fighter != null:
		fighter.ignite(4.0)

func _on_died(id: int) -> void:
	if _over:
		return
	_over = true
	var winner: int = 2 if id == 1 else 1
	_label.text = "Player %d down. Player %d wins. Enter: menu" % [id, winner]
	match_over.emit(winner)

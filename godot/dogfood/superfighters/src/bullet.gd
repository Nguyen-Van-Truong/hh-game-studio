class_name Bullet
extends Area2D

var velocity: Vector2 = Vector2.ZERO
var damage: float = 10.0
var owner_slot: int = -1
var owner_team: int = -1
var life: float = 0.9
var spent: bool = false


func setup(at: Vector2, dir: Vector2, speed: float, dmg: float, slot: int, team: int) -> void:
	global_position = at
	velocity = dir.normalized() * speed
	damage = dmg
	owner_slot = slot
	owner_team = team
	name = "Bullet"
	collision_layer = Maps.COL_HURT
	collision_mask = Maps.COL_WORLD | Maps.COL_PROP | Maps.COL_FIGHTER
	monitoring = true
	monitorable = false
	var shape: CollisionShape2D = CollisionShape2D.new()
	var rect: RectangleShape2D = RectangleShape2D.new()
	rect.size = Vector2(6, 3)
	shape.shape = rect
	add_child(shape)
	var body: ColorRect = ColorRect.new()
	body.name = "Body"
	body.size = Vector2(6, 3)
	body.position = Vector2(-3, -1.5)
	body.color = Color(0.95, 0.85, 0.35, 1.0)
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(body)
	rotation = velocity.angle()


func step(delta: float) -> void:
	if spent:
		return
	global_position += velocity * delta
	life -= delta
	if life <= 0.0:
		spent = true

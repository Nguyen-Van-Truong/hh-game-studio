class_name Bullet
extends Area2D
## Straight shot. Port of the projectile tick in Code.Handler.Projectiles.

var owner_id: int = 1
var direction: float = 1.0
var _life: float = 1.2

func _ready() -> void:
	collision_layer = 4
	collision_mask = 2
	var shape := CollisionShape2D.new()
	var circle := CircleShape2D.new()
	circle.radius = 3.0
	shape.shape = circle
	add_child(shape)
	body_entered.connect(_on_body)
	var mark := Polygon2D.new()
	mark.polygon = PackedVector2Array([Vector2(-4, -1), Vector2(6, -1), Vector2(6, 1), Vector2(-4, 1)])
	mark.color = Color(1.0, 0.92, 0.4)
	add_child(mark)

func _physics_process(delta: float) -> void:
	position.x += direction * 720.0 * delta
	_life -= delta
	if _life <= 0.0 or position.x < -40.0 or position.x > 1400.0:
		queue_free()

func _on_body(body: Node) -> void:
	var fighter: Fighter = body as Fighter
	if fighter != null and fighter.player_id != owner_id:
		fighter.damage(Tuning.BULLET_DAMAGE)
		queue_free()

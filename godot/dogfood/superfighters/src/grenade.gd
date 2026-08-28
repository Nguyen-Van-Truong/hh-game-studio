class_name ThrownGrenade
extends CharacterBody2D

var owner_slot: int = -1
var owner_team: int = -1
var fuse: float = 1.35
var damage: float = 42.0
var radius: float = 48.0
var exploded: bool = false


func setup(at: Vector2, dir: Vector2, slot: int, team: int) -> void:
	global_position = at
	owner_slot = slot
	owner_team = team
	name = "Grenade"
	motion_mode = CharacterBody2D.MOTION_MODE_GROUNDED
	collision_layer = Maps.COL_HURT
	collision_mask = Maps.COL_WORLD | Maps.COL_PROP | Maps.COL_PLATFORM
	velocity = dir.normalized() * 280.0 + Vector2(0, -80.0)
	var shape: CollisionShape2D = CollisionShape2D.new()
	var circle: CircleShape2D = CircleShape2D.new()
	circle.radius = 4.0
	shape.shape = circle
	add_child(shape)
	var body: ColorRect = ColorRect.new()
	body.name = "Body"
	body.size = Vector2(8, 8)
	body.position = Vector2(-4, -4)
	body.color = Color(0.25, 0.35, 0.3, 1.0)
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(body)
	Visuals.attach_sprite(self, "res://assets/art/item_grenade.png")


func step(delta: float) -> void:
	if exploded:
		return
	velocity.y += 900.0 * delta
	var hit: bool = move_and_slide()
	if hit or is_on_floor() or is_on_wall():
		velocity.x *= 0.55
		if is_on_floor():
			velocity.y = minf(velocity.y, 0.0) * 0.35
	fuse -= delta
	if fuse <= 0.0:
		exploded = true

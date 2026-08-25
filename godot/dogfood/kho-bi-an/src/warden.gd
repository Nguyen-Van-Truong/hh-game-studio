class_name Warden
extends CharacterBody2D

var _a: Vector2 = Vector2.ZERO
var _b: Vector2 = Vector2.ZERO
var _travel: float = 0.0
var _facing: Vector2 = Vector2.RIGHT
var sprite: AnimatedSprite2D


func _ready() -> void:
	name = "Warden"
	motion_mode = CharacterBody2D.MOTION_MODE_FLOATING
	collision_layer = VaultMap.COL_WARDEN
	collision_mask = VaultMap.COL_WORLD
	var shape: CollisionShape2D = CollisionShape2D.new()
	var rect: RectangleShape2D = RectangleShape2D.new()
	rect.size = Vector2(12, 12)
	shape.shape = rect
	add_child(shape)
	var body: ColorRect = ColorRect.new()
	body.name = "Body"
	body.size = Vector2(float(VaultMap.ACTOR), float(VaultMap.ACTOR))
	body.position = Vector2(-float(VaultMap.ACTOR) * 0.5, -float(VaultMap.ACTOR) * 0.5)
	body.color = Color(0.72, 0.22, 0.18)
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(body)
	sprite = Visuals.attach_actor(self, Visuals.WARDEN_FRAMES)
	sprite.play("idle_right")


func set_patrol(a: Vector2, b: Vector2) -> void:
	_a = a
	_b = b
	global_position = a
	_travel = 0.0
	_facing = Vector2.RIGHT


func step_patrol(delta: float) -> void:
	var before: Vector2 = global_position
	var span: float = _a.distance_to(_b)
	if span > 0.001:
		_travel += delta * VaultMap.WARDEN_SPEED
		var ping: float = pingpong(_travel / span, 1.0)
		global_position = _a.lerp(_b, ping)
	var moved: Vector2 = global_position - before
	var moving: bool = moved.length_squared() > 0.0001
	if moving:
		_facing = InputActions.cardinal(moved)
	Visuals.play_actor(sprite, _facing, moving)


func touches_player(who: Node2D) -> bool:
	return global_position.distance_to(who.global_position) <= VaultMap.WARDEN_TOUCH

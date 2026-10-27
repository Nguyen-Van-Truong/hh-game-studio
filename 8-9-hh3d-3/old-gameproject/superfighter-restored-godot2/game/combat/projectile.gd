class_name VaultProjectile
extends Node2D

var match_controller: VaultGame
var owner_id: int = 0
var kind: StringName = &"bullet"
var velocity: Vector2 = Vector2.ZERO
var damage: int = 10
var lifetime: float = 2.0

func configure(controller: VaultGame, owner: int, projectile_kind: StringName, start: Vector2, motion: Vector2, hit_damage: int) -> void:
	match_controller = controller
	owner_id = owner
	kind = projectile_kind
	position = start
	velocity = motion
	damage = hit_damage
	queue_redraw()

func _physics_process(delta: float) -> void:
	if match_controller == null or match_controller.is_match_paused():
		return
	lifetime -= delta
	if kind == &"grenade":
		velocity.y += 720.0 * delta
	position += velocity * delta
	if lifetime <= 0.0 or position.x < -50.0 or position.x > 1330.0 or position.y > 760.0:
		queue_free()
		return
	if bool(match_controller.resolve_projectile(self)):
		queue_free()
		return
	queue_redraw()

func _draw() -> void:
	if kind == &"grenade":
		draw_circle(Vector2.ZERO, 8.0, Color("b68cff"))
		draw_circle(Vector2.ZERO, 10.0, Color(0.8, 0.65, 1.0, 0.55), false, 2.0)
	else:
		draw_circle(Vector2.ZERO, 4.0, Color("f5de79"))
		draw_line(Vector2(-10.0, 0.0), Vector2(-4.0, 0.0), Color(1.0, 0.55, 0.2, 0.8), 2.0)

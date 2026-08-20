extends CharacterBody2D

const SPEED: float = 220.0


func _ready() -> void:
	motion_mode = CharacterBody2D.MOTION_MODE_FLOATING


func _physics_process(_delta: float) -> void:
	var direction: Vector2 = Vector2.ZERO
	if Input.is_action_pressed("move_left"):
		direction.x -= 1.0
	if Input.is_action_pressed("move_right"):
		direction.x += 1.0
	if Input.is_action_pressed("move_up"):
		direction.y -= 1.0
	if Input.is_action_pressed("move_down"):
		direction.y += 1.0
	if direction.length() > 0.0:
		direction = direction.normalized()
	velocity = direction * SPEED
	move_and_slide()

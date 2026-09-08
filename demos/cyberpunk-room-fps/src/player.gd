extends CharacterBody3D

const SPEED: float = 4.4
const SPRINT_MULT: float = 1.35
const JUMP_VELOCITY: float = 4.6
const MOUSE_SENS: float = 0.0022
const GRAVITY: float = 9.8
const SHOOT_COOLDOWN: float = 0.11
const RAY_LEN: float = 40.0

signal shot_fired
signal target_hit(target: Node3D)

@onready var _camera: Camera3D = $Camera3D
@onready var _ray: RayCast3D = $Camera3D/RayCast3D
@onready var _muzzle: OmniLight3D = $Camera3D/Weapon/MuzzleFlash
@onready var _shoot_sfx: AudioStreamPlayer = $ShootSfx

var look_enabled: bool = false
var shoot_enabled: bool = false
var _cool: float = 0.0
var _muzzle_time: float = 0.0


func _ready() -> void:
	_ray.target_position = Vector3(0.0, 0.0, -RAY_LEN)
	_ray.collision_mask = 3
	_ray.enabled = true
	_muzzle.visible = false


func set_play_enabled(enabled: bool) -> void:
	look_enabled = enabled
	shoot_enabled = enabled
	if enabled:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	else:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE


func _unhandled_input(event: InputEvent) -> void:
	if not look_enabled:
		return
	if event is InputEventMouseMotion:
		var motion := event as InputEventMouseMotion
		rotate_y(-motion.relative.x * MOUSE_SENS)
		_camera.rotate_x(-motion.relative.y * MOUSE_SENS)
		_camera.rotation.x = clampf(_camera.rotation.x, deg_to_rad(-85.0), deg_to_rad(85.0))
	if shoot_enabled and event.is_action_pressed("shoot"):
		_try_shoot()


func _physics_process(delta: float) -> void:
	if not is_on_floor():
		velocity.y -= GRAVITY * delta
	elif Input.is_action_just_pressed("jump") and look_enabled:
		velocity.y = JUMP_VELOCITY

	var input_dir := Vector2.ZERO
	if look_enabled:
		input_dir = Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	var wish := (transform.basis * Vector3(input_dir.x, 0.0, input_dir.y)).normalized()
	var speed := SPEED
	if Input.is_key_pressed(KEY_SHIFT):
		speed *= SPRINT_MULT
	if wish != Vector3.ZERO:
		velocity.x = wish.x * speed
		velocity.z = wish.z * speed
	else:
		velocity.x = move_toward(velocity.x, 0.0, SPEED)
		velocity.z = move_toward(velocity.z, 0.0, SPEED)
	move_and_slide()

	_cool = maxf(_cool - delta, 0.0)
	if _muzzle_time > 0.0:
		_muzzle_time -= delta
		if _muzzle_time <= 0.0:
			_muzzle.visible = false


func _try_shoot() -> void:
	if _cool > 0.0:
		return
	_cool = SHOOT_COOLDOWN
	_muzzle.visible = true
	_muzzle.light_energy = 1.6
	_muzzle_time = 0.045
	if _shoot_sfx.stream:
		_shoot_sfx.play()
	shot_fired.emit()
	_ray.force_raycast_update()
	if not _ray.is_colliding():
		return
	var collider := _ray.get_collider() as Node
	if collider == null:
		return
	var target := collider as RangeTarget
	if target == null:
		target = collider.get_parent() as RangeTarget
	if target:
		target.apply_hit()
		target_hit.emit(target)

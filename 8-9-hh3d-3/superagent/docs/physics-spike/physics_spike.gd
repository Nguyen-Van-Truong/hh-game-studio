extends Node2D
## SA5 N3 isolated physics spike.
##
## This fixture is deliberately outside game/core and never feeds the
## provisional arena state. It probes the Godot Physics 2D choices required by
## the SA5 plan at a fixed 60 Hz with a known seed.

const FIXED_HZ: int = 60
const SEED_VALUE: int = 54821
const RUN_TICKS: int = 180
const GRAVITY: float = 980.0

var _rng: RandomNumberGenerator = RandomNumberGenerator.new()
var _tick: int = 0
var _finished: bool = false
var _stack: Array[RigidBody2D] = []
var _crate: RigidBody2D
var _fighter: CharacterBody2D
var _roll_fighter: RigidBody2D
var _hanging: RigidBody2D
var _joint: PinJoint2D
var _explosion_origin: Vector2 = Vector2.ZERO
var _stack_anchor_x: float = 0.0
var _crate_initial_x: float = 0.0
var _roll_initial_y: float = 0.0
var _roll_initial_rotation: float = 0.0
var _fighter_stood_on_crate: bool = false
var _explosion_applied: bool = false
var _joint_broken: bool = false
var _assertions: int = 0
var _failures: int = 0


func _ready() -> void:
	Engine.physics_ticks_per_second = FIXED_HZ
	_rng.seed = SEED_VALUE
	_build_fixture()
	set_physics_process(true)


func _physics_process(delta: float) -> void:
	_tick += 1
	_drive_fighter(delta)
	if _tick == 30:
		_apply_explosion()
	if _tick == 45:
		_break_hanging_joint()
	if _tick >= RUN_TICKS and not _finished:
		_finished = true
		set_physics_process(false)
		call_deferred("_finish")


func _build_fixture() -> void:
	_create_static_rect("StaticFloor", Vector2(640.0, 700.0), Vector2(1280.0, 40.0))
	_create_staircase()
	_create_stack()
	_create_hanging_body()
	_create_fighter_and_crate()
	_create_roll_fighter()


func _create_static_rect(body_name: String, center: Vector2, size: Vector2) -> StaticBody2D:
	var body := StaticBody2D.new()
	body.name = body_name
	body.position = center
	body.add_child(_rectangle_shape(size))
	add_child(body)
	return body


func _rectangle_shape(size: Vector2) -> CollisionShape2D:
	var rectangle := RectangleShape2D.new()
	rectangle.size = size
	var collision := CollisionShape2D.new()
	collision.shape = rectangle
	return collision


func _create_staircase() -> void:
	for index: int in range(6):
		var step_center := Vector2(860.0 + float(index) * 54.0, 500.0 + float(index) * 30.0)
		_create_static_rect("Stair%02d" % index, step_center, Vector2(58.0, 30.0))


func _create_stack() -> void:
	# Six rows of five bodies gives the requested thirty-body contact pile.
	for index: int in range(30):
		var body := RigidBody2D.new()
		body.name = "StackBody%02d" % index
		var column: int = index % 5
		var row: int = int(index / 5)
		body.position = Vector2(230.0 + float(column) * 28.0, 620.0 - float(row) * 28.0)
		body.mass = 1.0
		body.linear_damp = 0.35
		body.angular_damp = 0.45
		body.continuous_cd = RigidBody2D.CCD_MODE_CAST_RAY
		body.add_child(_rectangle_shape(Vector2(26.0, 26.0)))
		add_child(body)
		_stack.append(body)
	_explosion_origin = Vector2(300.0, 590.0)
	_stack_anchor_x = _stack[0].position.x


func _create_hanging_body() -> void:
	var anchor := StaticBody2D.new()
	anchor.name = "HangingAnchor"
	anchor.position = Vector2(1060.0, 170.0)
	add_child(anchor)
	var hanging := RigidBody2D.new()
	hanging.name = "HangingBody"
	hanging.position = Vector2(1060.0, 260.0)
	hanging.mass = 1.0
	hanging.continuous_cd = RigidBody2D.CCD_MODE_CAST_RAY
	hanging.add_child(_rectangle_shape(Vector2(34.0, 34.0)))
	add_child(hanging)
	_hanging = hanging
	var joint := PinJoint2D.new()
	joint.name = "HangingPin"
	joint.position = anchor.position
	add_child(joint)
	joint.node_a = anchor.get_path()
	joint.node_b = hanging.get_path()
	_joint = joint


func _create_fighter_and_crate() -> void:
	_crate = RigidBody2D.new()
	_crate.name = "PushCrate"
	_crate.position = Vector2(660.0, 640.0)
	_crate.mass = 3.0
	_crate.linear_damp = 0.8
	_crate.angular_damp = 0.8
	_crate.add_child(_rectangle_shape(Vector2(52.0, 52.0)))
	add_child(_crate)
	_crate_initial_x = _crate.position.x

	_fighter = CharacterBody2D.new()
	_fighter.name = "FighterCharacter"
	_fighter.position = Vector2(640.0, 540.0)
	_fighter.floor_snap_length = 5.0
	_fighter.add_child(_rectangle_shape(Vector2(30.0, 48.0)))
	add_child(_fighter)


func _create_roll_fighter() -> void:
	_roll_fighter = RigidBody2D.new()
	_roll_fighter.name = "RollingFighter"
	_roll_fighter.position = Vector2(840.0, 430.0)
	_roll_fighter.mass = 1.2
	_roll_fighter.linear_damp = 0.12
	_roll_fighter.angular_damp = 0.02
	_roll_fighter.can_sleep = false
	_roll_fighter.continuous_cd = RigidBody2D.CCD_MODE_CAST_RAY
	var material := PhysicsMaterial.new()
	material.friction = 0.65
	material.bounce = 0.0
	_roll_fighter.physics_material_override = material
	_roll_fighter.add_child(_rectangle_shape(Vector2(34.0, 42.0)))
	add_child(_roll_fighter)
	_roll_initial_y = _roll_fighter.position.y
	_roll_initial_rotation = _roll_fighter.rotation
	_roll_fighter.apply_central_impulse(Vector2(220.0, 20.0))
	_roll_fighter.apply_torque_impulse(6.0)


func _drive_fighter(delta: float) -> void:
	if not is_instance_valid(_fighter):
		return
	# Let the CharacterBody2D settle on the crate before stepping off its left
	# edge. It then walks back into the side; the collision impulse below is the
	# only source of crate displacement.
	if _tick < 60:
		_fighter.velocity.x = 0.0
	elif _tick < 86:
		_fighter.velocity.x = -80.0
	else:
		_fighter.velocity.x = 140.0
	_fighter.velocity.y = minf(_fighter.velocity.y + GRAVITY * delta, 900.0)
	_fighter.move_and_slide()
	for collision_index: int in range(_fighter.get_slide_collision_count()):
		var collision := _fighter.get_slide_collision(collision_index)
		var collider: Object = collision.get_collider()
		if collider == _crate and collision.get_normal().y < -0.45:
			_fighter_stood_on_crate = true
		if collider is RigidBody2D:
			var rigid_body := collider as RigidBody2D
			if collider == _crate:
				rigid_body.sleeping = false
				rigid_body.apply_central_impulse(Vector2(20.0, 0.0))


func _apply_explosion() -> void:
	_explosion_applied = true
	for body: RigidBody2D in _stack:
		if not is_instance_valid(body):
			continue
		var offset: Vector2 = body.position - _explosion_origin
		var direction: Vector2 = offset.normalized() if offset.length_squared() > 0.01 else Vector2.UP
		var jitter: float = _rng.randf_range(0.92, 1.08)
		body.apply_central_impulse(direction * 190.0 * jitter)


func _break_hanging_joint() -> void:
	if is_instance_valid(_joint):
		_joint.queue_free()
		_joint_broken = true
	if is_instance_valid(_hanging):
		_hanging.apply_central_impulse(Vector2(65.0, -15.0))


func _finish() -> void:
	var stack_moved: bool = false
	if not _stack.is_empty() and is_instance_valid(_stack[0]):
		stack_moved = absf(_stack[0].position.x - _stack_anchor_x) > 1.0
	var crate_moved: bool = is_instance_valid(_crate) and absf(_crate.position.x - _crate_initial_x) > 1.0
	var roll_descended: bool = is_instance_valid(_roll_fighter) and _roll_fighter.position.y > _roll_initial_y + 18.0
	var roll_rotated: bool = is_instance_valid(_roll_fighter) and absf(_roll_fighter.rotation - _roll_initial_rotation) > 0.08
	_expect(_stack.size() == 30, "stack contains thirty RigidBody2D objects")
	_expect(_explosion_applied, "explosion impulse was applied at a fixed tick")
	_expect(stack_moved, "explosion displaced the contact pile")
	_expect(_joint_broken, "pin joint was explicitly released after the hanging-body impulse")
	_expect(_fighter_stood_on_crate, "CharacterBody2D reached the crate top through collision movement")
	_expect(crate_moved, "fighter contact/impulse moved the RigidBody2D crate")
	_expect(roll_descended, "rolling fighter descended the static staircase")
	_expect(roll_rotated, "rolling fighter acquired angular motion")
	var canonical: String = _canonical_state()
	var report: Dictionary = {
		"schema": "sa5.n3.physics-spike.v1",
		"seed": SEED_VALUE,
		"fixed_hz": FIXED_HZ,
		"ticks": _tick,
		"bodies": {"stack": _stack.size(), "character": is_instance_valid(_fighter), "crate": is_instance_valid(_crate), "hanging": is_instance_valid(_hanging), "rolling": is_instance_valid(_roll_fighter)},
		"observations": {"explosion": _explosion_applied and stack_moved, "hanging_release": _joint_broken, "fighter_on_crate": _fighter_stood_on_crate, "crate_displaced": crate_moved, "stair_descent": roll_descended, "stair_rotation": roll_rotated},
		"metrics": {"crate_initial_x": _crate_initial_x, "crate_final_x": _crate.position.x if is_instance_valid(_crate) else -1.0, "fighter_final_x": _fighter.position.x if is_instance_valid(_fighter) else -1.0, "fighter_final_y": _fighter.position.y if is_instance_valid(_fighter) else -1.0},
		"state_hash": _fnv1a(canonical),
		"assertions": _assertions,
		"failures": _failures,
		"status": "PASS" if _failures == 0 else "FAIL",
	}
	if _failures == 0:
		print("PHYSICS_SPIKE_PASS " + JSON.stringify(report))
	else:
		printerr("PHYSICS_SPIKE_FAIL " + JSON.stringify(report))
	get_tree().quit(0 if _failures == 0 else 1)


func _canonical_state() -> String:
	var rows: Array[String] = ["tick=%d" % _tick, "seed=%d" % SEED_VALUE]
	for body: RigidBody2D in _stack:
		if is_instance_valid(body):
			rows.append("s:%d,%d,%d" % [body.position.x, body.position.y, body.rotation])
	if is_instance_valid(_crate):
		rows.append("c:%d,%d" % [_crate.position.x, _crate.position.y])
	if is_instance_valid(_fighter):
		rows.append("f:%d,%d" % [_fighter.position.x, _fighter.position.y])
	if is_instance_valid(_roll_fighter):
		rows.append("r:%d,%d,%d" % [_roll_fighter.position.x, _roll_fighter.position.y, _roll_fighter.rotation])
	return "|".join(rows)


func _fnv1a(value: String) -> String:
	var hash_value: int = 2166136261
	for byte_value: int in value.to_utf8_buffer():
		hash_value = int((hash_value ^ byte_value) * 16777619) & 0x7fffffff
	return "%08x" % hash_value


func _expect(condition: bool, _message: String) -> void:
	_assertions += 1
	if not condition:
		_failures += 1

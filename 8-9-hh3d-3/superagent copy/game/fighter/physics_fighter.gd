class_name PhysicsFighter2D
extends CharacterBody2D
## Collision authority for a fighter. Simulation supplies one intent per
## physics tick, then FighterState reads back the resolved motion.

const FIXED_HZ: float = 60.0
const FIGHTER_LAYER: int = 4
# Keep the adapter independent from global class registration.  The arena
# owns the same layer contract, but this script must also compile standalone
# when Godot loads it from a headless --script test.
const SOLID_LAYER: int = 1
const ONE_WAY_LAYER: int = 2

var body_size: Vector2 = Vector2(28.0, 48.0)
var _collision_shape: CollisionShape2D
var _drop_through: bool = false


func configure(size: Vector2, floor_snap: float = 5.0) -> void:
	body_size = Vector2(maxf(0.001, size.x), maxf(0.001, size.y))
	motion_mode = CharacterBody2D.MOTION_MODE_GROUNDED
	floor_snap_length = maxf(0.0, floor_snap)
	collision_layer = FIGHTER_LAYER
	collision_mask = (1 << (SOLID_LAYER - 1)) | (1 << (ONE_WAY_LAYER - 1))
	_collision_shape = get_node_or_null("CollisionShape2D") as CollisionShape2D
	if _collision_shape == null:
		_collision_shape = CollisionShape2D.new()
		_collision_shape.name = &"CollisionShape2D"
		add_child(_collision_shape)
	var rectangle := _collision_shape.shape as RectangleShape2D
	if rectangle == null:
		rectangle = RectangleShape2D.new()
		_collision_shape.shape = rectangle
	rectangle.size = body_size
	_collision_shape.position = Vector2(0.0, -body_size.y * 0.5)


func set_drop_through(active: bool) -> void:
	_drop_through = active
	set_collision_mask_value(ONE_WAY_LAYER, not active)

func set_solid_collision_enabled(enabled: bool) -> void:
	## Pits are open floor gaps.  Disabling the solid mask while a body is
	## crossing a pit edge prevents the vertical face of a split floor fixture
	## from behaving like an invisible wall; the fighter then falls under the
	## normal fixed-step gravity path.
	set_collision_mask_value(SOLID_LAYER, enabled)


func set_posture_height(height: float) -> void:
	var rectangle: RectangleShape2D = _collision_shape.shape as RectangleShape2D
	var clamped_height: float = clampf(height, 0.001, body_size.y)
	rectangle.size = Vector2(body_size.x, clamped_height)
	_collision_shape.position.y = -clamped_height * 0.5


func posture_height() -> float:
	var rectangle: RectangleShape2D = _collision_shape.shape as RectangleShape2D
	return rectangle.size.y if rectangle != null else body_size.y


func can_stand() -> bool:
	# Check only the extra headroom; the floor contact must not prevent standing.
	var current: RectangleShape2D = _collision_shape.shape as RectangleShape2D
	var extra_height: float = body_size.y - current.size.y
	if extra_height <= 0.01:
		return true
	var query := PhysicsShapeQueryParameters2D.new()
	var headroom := RectangleShape2D.new()
	headroom.size = Vector2(body_size.x - 0.2, maxf(0.01, extra_height - 0.2))
	query.shape = headroom
	query.transform = Transform2D(0.0, global_position + Vector2(0.0, -body_size.y + extra_height * 0.5))
	query.collision_mask = collision_mask
	query.exclude = [get_rid()]
	return get_world_2d().direct_space_state.intersect_shape(query, 1).is_empty()


func is_drop_through_active() -> bool:
	return _drop_through


func set_tick_velocity(tick_velocity: Vector2) -> void:
	# Gameplay tuning is expressed per 60-Hz tick; CharacterBody2D expects
	# pixels per second.  Keep this conversion at the adapter boundary.
	velocity = tick_velocity * FIXED_HZ


func add_tick_gravity(gravity_per_tick: float, delta: float) -> void:
	# px/tick² -> px/sec². At delta=1/60 this adds gravity_per_tick
	# to the returned tick velocity, not gravity_per_tick/60.
	velocity.y += gravity_per_tick * FIXED_HZ * FIXED_HZ * delta


func move_fixed_step() -> void:
	move_and_slide()


func read_motion() -> Dictionary:
	var tick_velocity: Vector2 = velocity / FIXED_HZ
	return {
		&"position": position,
		&"velocity": tick_velocity,
		&"grounded": is_on_floor(),
		&"floor_normal": get_floor_normal(),
		&"collision_count": get_slide_collision_count(),
		&"drop_through": _drop_through,
	}


func sync_from_state(state_position: Vector2, state_velocity_per_tick: Vector2) -> void:
	# Use only for spawn/reset or an explicit teleport.  A normal physics tick
	# must read back the body instead of overwriting its transform.
	position = state_position
	set_tick_velocity(state_velocity_per_tick)

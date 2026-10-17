class_name PhysicsArena2D
extends Node2D
## SA5 N4 Godot Physics arena fixtures.
##
## ArenaState remains the serializable topology authority.  This node owns
## only Godot Physics 2D fixtures derived from that topology. Simulation owns one
## instance per session and uses these fixtures during each physics tick.

const SOLID_LAYER: int = 1
const ONE_WAY_LAYER: int = 2
const PLATFORM_THICKNESS: float = 12.0
const BOUNDARY_THICKNESS: float = 24.0

var _arena: ArenaState
var _fixtures: Array[StaticBody2D] = []


func configure(source: ArenaState, include_boundaries: bool = true) -> void:
	_arena = source
	rebuild(include_boundaries)


func rebuild(include_boundaries: bool = true) -> void:
	_clear_fixtures()
	if _arena == null:
		return
	var snapshot: Dictionary = _arena.snapshot()
	for platform_value: Variant in snapshot.get(&"platforms", []):
		if typeof(platform_value) != TYPE_DICTIONARY:
			continue
		var platform: Dictionary = platform_value
		var left: float = float(platform.get(&"left", 0.0))
		var right: float = float(platform.get(&"right", 0.0))
		var top: float = float(platform.get(&"y", 0.0))
		var one_way: bool = bool(platform.get(&"one_way", false))
		_create_rect_fixture(
			StringName("Platform_%s" % String(platform.get(&"id", &"unnamed"))),
			Vector2((left + right) * 0.5, top + PLATFORM_THICKNESS * 0.5),
			Vector2(maxf(0.0, right - left), PLATFORM_THICKNESS),
			one_way,
		)
	for solid_value: Variant in snapshot.get(&"solids", []):
		if typeof(solid_value) != TYPE_DICTIONARY:
			continue
		var solid: Dictionary = solid_value
		var left: float = float(solid.get(&"left", 0.0))
		var right: float = float(solid.get(&"right", 0.0))
		var top: float = float(solid.get(&"top", 0.0))
		var bottom: float = float(solid.get(&"bottom", 0.0))
		_create_rect_fixture(
			StringName("Solid_%s" % String(solid.get(&"id", &"unnamed"))),
			Vector2((left + right) * 0.5, (top + bottom) * 0.5),
			Vector2(maxf(0.0, right - left), maxf(0.0, bottom - top)),
			false,
		)
	if include_boundaries:
		var width: float = float(snapshot.get(&"width", 0.0))
		var height: float = float(snapshot.get(&"height", 0.0))
		var boundary_center_y: float = height * 0.5
		_create_rect_fixture(
			&"Boundary_Left",
			Vector2(-BOUNDARY_THICKNESS * 0.5, boundary_center_y),
			Vector2(BOUNDARY_THICKNESS, height),
			false,
		)
		_create_rect_fixture(
			&"Boundary_Right",
			Vector2(width + BOUNDARY_THICKNESS * 0.5, boundary_center_y),
			Vector2(BOUNDARY_THICKNESS, height),
			false,
		)


func fixture_count() -> int:
	return _fixtures.size()


func one_way_fixture_count() -> int:
	var count: int = 0
	for body: StaticBody2D in _fixtures:
		var shape: CollisionShape2D = body.get_node_or_null("Shape") as CollisionShape2D
		if shape != null and shape.one_way_collision:
			count += 1
	return count


func set_one_way_mask_enabled(body: CollisionObject2D, enabled: bool) -> void:
	# Drop-through is per fighter; this toggles only that body's mask and never
	# disables the shared static platform fixture.
	if body == null:
		return
	body.set_collision_mask_value(ONE_WAY_LAYER, enabled)


func _create_rect_fixture(fixture_name: StringName, center: Vector2, size: Vector2, one_way: bool) -> void:
	if size.x <= 0.0 or size.y <= 0.0:
		return
	var body := StaticBody2D.new()
	body.name = fixture_name
	body.collision_layer = SOLID_LAYER if not one_way else ONE_WAY_LAYER
	body.collision_mask = 0
	var shape := CollisionShape2D.new()
	shape.name = &"Shape"
	var rectangle := RectangleShape2D.new()
	rectangle.size = size
	shape.shape = rectangle
	shape.one_way_collision = one_way
	shape.one_way_collision_margin = 2.0
	body.position = center
	body.add_child(shape)
	add_child(body)
	_fixtures.append(body)


func _clear_fixtures() -> void:
	for body: StaticBody2D in _fixtures:
		if is_instance_valid(body):
			body.free()
	_fixtures.clear()

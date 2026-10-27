extends RefCounted
## Each attached simulation owns an isolated engine physics world. Authored
## frames advance only after a real SceneTree physics frame has begun.

const FIXTURE_GROUP: StringName = &"simulation_physics_fixtures"

static func create(tree: SceneTree, seed_value: int, tuning: Dictionary = {}) -> Simulation:
	var viewport := SubViewport.new()
	viewport.name = "PhysicsFixture"
	viewport.size = Vector2i(1600, 900)
	viewport.world_2d = World2D.new()
	viewport.render_target_update_mode = SubViewport.UPDATE_DISABLED
	tree.root.add_child(viewport)
	viewport.add_to_group(FIXTURE_GROUP)
	var simulation := Simulation.new(seed_value, tuning)
	viewport.add_child(simulation)
	return simulation

static func advance(simulation: Simulation, frame: InputFrame) -> bool:
	await simulation.get_tree().physics_frame
	return simulation.step(frame)

static func advance_pair(first: Simulation, second: Simulation, frame: InputFrame) -> bool:
	await first.get_tree().physics_frame
	var first_advanced: bool = first.step(frame)
	var second_advanced: bool = second.step(frame)
	return first_advanced and second_advanced

static func cleanup(tree: SceneTree) -> void:
	for viewport: Node in tree.get_nodes_in_group(FIXTURE_GROUP):
		viewport.queue_free()
	await tree.process_frame

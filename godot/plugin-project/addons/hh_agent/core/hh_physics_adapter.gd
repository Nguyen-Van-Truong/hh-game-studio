class_name HHAgentPhysicsAdapter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")
const _MetaScript: GDScript = preload("res://addons/hh_agent/core/hh_scene_meta.gd")
const _IdentityScript: GDScript = preload("res://addons/hh_agent/core/hh_identity.gd")

## Typed Godot 4.7.1 physics / navigation / collision verbs (editor configuration).
## Velocity is stored only. Never a runtime physics step or server integrate.
## Shapes use explicit geometry or Sprite2D.get_rect / Texture2D.get_size.
## Never invent a default pixel box. Never the removed outline-to-polygon helper.
## bake_navigation_polygon(false) only; wait is_baking == false before path.
## map_get_path requires map_is_active and map_get_iteration_id > 0.
## Empty path is E_UNVERIFIED (Alternative / deferred R6). Do not invent a polyline.
## Overlay uses engine AABB. CM-139 Gap: collision debug hint / Visible Collision
## Shapes are not proven. Catalog: register in actions.json. Generated
## plugin-validator.json / mcp-tools.json are coordinator-owned (`npm run generate`).

const FIXTURE_PLAYER: String = "player"
const FIXTURE_WORLD: String = "world"
const FIXTURE_INTERACT: String = "interact"
const MOTION_GROUNDED: String = "grounded"
const MOTION_FLOATING: String = "floating"
const SHAPE_RECT: String = "rectangle"
const SHAPE_CIRCLE: String = "circle"
const SHAPE_CAPSULE: String = "capsule"
const SHAPE_CONVEX: String = "convex"
const SHAPE_POLYGON: String = "polygon"
const BAKE_WAIT_MS: int = 4000

var _errors: HHAgentErrors = HHAgentErrors.new()
var _meta: HHAgentSceneMeta = HHAgentSceneMeta.new()
var _identity: HHAgentIdentity = HHAgentIdentity.new()


class BodyStroke:
	extends RefCounted
	var node: CollisionObject2D
	var old: Dictionary = {}
	var neu: Dictionary = {}

	func apply() -> void:
		if node == null:
			return
		HHAgentPhysicsAdapter._write_body(node, neu)

	func revert() -> void:
		if node == null:
			return
		HHAgentPhysicsAdapter._write_body(node, old)


class ShapeStroke:
	extends RefCounted
	var host: Node
	var old_shape: Shape2D
	var new_shape: Shape2D
	var old_poly: PackedVector2Array = PackedVector2Array()
	var new_poly: PackedVector2Array = PackedVector2Array()
	var is_poly: bool = false

	func apply() -> void:
		if host == null:
			return
		if is_poly and host is CollisionPolygon2D:
			(host as CollisionPolygon2D).polygon = new_poly
		elif host is CollisionShape2D:
			(host as CollisionShape2D).shape = new_shape

	func revert() -> void:
		if host == null:
			return
		if is_poly and host is CollisionPolygon2D:
			(host as CollisionPolygon2D).polygon = old_poly
		elif host is CollisionShape2D:
			(host as CollisionShape2D).shape = old_shape


class LayersStroke:
	extends RefCounted
	var body: CollisionObject2D
	var old_layer: int = 0
	var new_layer: int = 0
	var old_mask: int = 0
	var new_mask: int = 0
	var layer_ops: Array[Dictionary] = []
	var mask_ops: Array[Dictionary] = []

	func apply() -> void:
		if body == null:
			return
		body.collision_layer = new_layer
		body.collision_mask = new_mask
		var i: int = 0
		while i < layer_ops.size():
			var rec: Dictionary = layer_ops[i]
			body.set_collision_layer_value(int(rec.get("layer", 1)), rec.get("enabled", false) == true)
			i += 1
		var j: int = 0
		while j < mask_ops.size():
			var rec_m: Dictionary = mask_ops[j]
			body.set_collision_mask_value(int(rec_m.get("layer", 1)), rec_m.get("enabled", false) == true)
			j += 1

	func revert() -> void:
		if body == null:
			return
		body.collision_layer = old_layer
		body.collision_mask = old_mask


class NavRegionStroke:
	extends RefCounted
	var region: NavigationRegion2D
	var old_poly: NavigationPolygon
	var new_poly: NavigationPolygon
	var parse_static: bool = false
	var traversable: PackedVector2Array = PackedVector2Array()
	var holes: Array[PackedVector2Array] = []

	func apply() -> void:
		if region == null or new_poly == null:
			return
		region.navigation_polygon = new_poly
		region.bake_navigation_polygon(false)

	func revert() -> void:
		if region == null:
			return
		region.navigation_polygon = old_poly


class NavAgentStroke:
	extends RefCounted
	var agent: NavigationAgent2D
	var old_target: Vector2 = Vector2.ZERO
	var new_target: Vector2 = Vector2.ZERO

	func apply() -> void:
		if agent == null:
			return
		agent.target_position = new_target

	func revert() -> void:
		if agent == null:
			return
		agent.target_position = old_target


func handles(action: String) -> bool:
	return (
		action == "body"
		or action == "shape"
		or action == "layers"
		or action == "nav_region"
		or action == "nav_agent"
		or action == "path"
		or action == "lint"
		or action == "debug"
	)


func handle(
	command_id: String,
	method: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
	precondition: Dictionary,
) -> Dictionary:
	if method != "godot.physics" or not handles(action):
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not a physics verb", "")
	var def: Dictionary = actions.lookup(method, action)
	var post: String = str(def.get("postcondition", ""))
	if post.is_empty():
		post = _fallback_post(action)
	if action == "body":
		return _body(command_id, params, precondition, post)
	if action == "shape":
		return _shape(command_id, params, precondition, post)
	if action == "layers":
		return _layers(command_id, params, precondition, post)
	if action == "nav_region":
		return _nav_region(command_id, params, precondition, post)
	if action == "nav_agent":
		return _nav_agent(command_id, params, precondition, post)
	if action == "path":
		return _path(command_id, params, post)
	if action == "lint":
		return _lint(command_id, params, post)
	if action == "debug":
		return _debug(command_id, params, post)
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "physics.%s is not a proven verb" % action, "")


func _fallback_post(action: String) -> String:
	if action == "body":
		return "physics_body_matches"
	if action == "shape":
		return "physics_shape_geometry_matches"
	if action == "layers":
		return "physics_layer_matrix_matches"
	if action == "nav_region":
		return "physics_nav_region_baked"
	if action == "nav_agent":
		return "physics_nav_agent_target_matches"
	if action == "path":
		return "physics_nav_path_or_unverified"
	if action == "lint":
		return "physics_lint_report"
	if action == "debug":
		return "physics_debug_engine_bounds"
	return "physics_verb"


static func engine_world_rect(node: Node) -> Dictionary:
	if node == null:
		return _rect_fail()
	if node is CollisionShape2D:
		return _shape_world_rect(node as CollisionShape2D)
	if node is CollisionPolygon2D:
		return _poly_world_rect(node as CollisionPolygon2D)
	if node is NavigationRegion2D:
		return _nav_world_rect(node as NavigationRegion2D)
	if node is CollisionObject2D:
		return _body_world_rect(node as CollisionObject2D)
	return _rect_fail()


func _body(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_collision(command_id, params, precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var body: CollisionObject2D = hold.get("body") as CollisionObject2D
	if (
		not (body is CharacterBody2D)
		and not (body is RigidBody2D)
		and not (body is Area2D)
		and not (body is StaticBody2D)
	):
		return _errors.fail(
			command_id,
			HHAgentErrors.E_INVALID_TYPE,
			"physics.body requires CharacterBody2D, RigidBody2D, Area2D, or StaticBody2D",
			"params.node_path",
		)
	var typed: Dictionary = _plan_body(command_id, body, params)
	if typed.get("ok", false) != true:
		return typed
	var material_path: String = str(params.get("material", ""))
	if material_path.contains("::"):
		return _unverified(command_id, "refusing RAM-only PhysicsMaterial assign")
	var stroke: BodyStroke = BodyStroke.new()
	stroke.node = body
	stroke.old = _read_body(body)
	stroke.neu = typed.get("flags") as Dictionary
	if params.has("friction") or params.has("bounce") or not material_path.is_empty():
		if not _supports_physics_material(body):
			return _errors.fail(
				command_id,
				HHAgentErrors.E_INVALID_TYPE,
				"physics_material_override requires RigidBody2D or StaticBody2D",
				"params.material",
			)
		var mat_built: Dictionary = _plan_material(command_id, body, params)
		if mat_built.get("ok", false) != true:
			return mat_built
		stroke.neu["physics_material_override"] = mat_built.get("material")
	var action_name: String = "%sphysics.body %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, body.get_class()]
	var committed: Dictionary = _commit_stroke(command_id, edited, action_name, stroke)
	if committed.get("ok", false) != true:
		return committed
	var persisted: Dictionary = {"ok": true, "disk_hash": ""}
	var mat_res: PhysicsMaterial = _material_of(body)
	if mat_res != null and _is_external_res(material_path):
		persisted = _persist_res(command_id, mat_res, material_path)
		if persisted.get("ok", false) != true:
			return persisted
	_meta.mark_dirty(str(params.get("scene", "")))
	var after: Dictionary = _physics_after(edited, params, body)
	_fill_body_after(after, body)
	after["disk_hash"] = str(persisted.get("disk_hash", ""))
	after["durable"] = _is_external_res(material_path)
	if not material_path.is_empty():
		after["material"] = material_path
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _shape(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var host_hold: Dictionary = _shape_host(command_id, edited, str(params.get("node_path", "")))
	if host_hold.get("ok", false) != true:
		return host_hold
	var host: Node = host_hold.get("host") as Node
	var packed_err: Dictionary = _reject_packed(command_id, host, edited)
	if not packed_err.is_empty():
		return packed_err
	var kind: String = str(params.get("shape", ""))
	var geom: Dictionary = _plan_geometry(command_id, edited, params, kind)
	if geom.get("ok", false) != true:
		return geom
	var shape_path: String = str(params.get("shape_path", ""))
	if shape_path.contains("::"):
		return _unverified(command_id, "refusing RAM-only shape durable ACK")
	var stroke: ShapeStroke = ShapeStroke.new()
	stroke.host = host
	if host is CollisionPolygon2D:
		if kind != SHAPE_POLYGON:
			return _errors.fail(
				command_id,
				HHAgentErrors.E_INVALID_TYPE,
				"CollisionPolygon2D requires shape=polygon",
				"params.shape",
			)
		stroke.is_poly = true
		stroke.old_poly = (host as CollisionPolygon2D).polygon
		stroke.new_poly = geom.get("points") as PackedVector2Array
	else:
		var built: Dictionary = _build_shape(command_id, kind, geom, shape_path)
		if built.get("ok", false) != true:
			return built
		stroke.new_shape = built.get("shape") as Shape2D
		if host is CollisionShape2D:
			stroke.old_shape = (host as CollisionShape2D).shape
	var action_name: String = "%sphysics.shape %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, kind]
	var committed: Dictionary = _commit_stroke(command_id, edited, action_name, stroke)
	if committed.get("ok", false) != true:
		return committed
	var persisted: Dictionary = {"ok": true, "disk_hash": ""}
	if host is CollisionShape2D:
		var live_shape: Shape2D = (host as CollisionShape2D).shape
		if live_shape == null:
			return _unverified(command_id, "CollisionShape2D.shape assign readback missing")
		if _is_external_res(shape_path):
			persisted = _persist_res(command_id, live_shape, shape_path)
			if persisted.get("ok", false) != true:
				return persisted
	_meta.mark_dirty(str(params.get("scene", "")))
	var after: Dictionary = _physics_after(edited, params, host)
	after["shape"] = kind
	after["shape_class"] = _shape_class_of(host)
	after["geometry"] = _read_geometry(host)
	after["disk_hash"] = str(persisted.get("disk_hash", ""))
	after["durable"] = _is_external_res(shape_path)
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _layers(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_collision(command_id, params, precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var body: CollisionObject2D = hold.get("body") as CollisionObject2D
	var stroke: LayersStroke = LayersStroke.new()
	stroke.body = body
	stroke.old_layer = body.collision_layer
	stroke.old_mask = body.collision_mask
	stroke.new_layer = stroke.old_layer
	stroke.new_mask = stroke.old_mask
	if params.has("collision_layer"):
		stroke.new_layer = int(params.get("collision_layer", 0))
	if params.has("collision_mask"):
		stroke.new_mask = int(params.get("collision_mask", 0))
	var fixture: String = str(params.get("fixture", ""))
	if fixture == FIXTURE_PLAYER:
		stroke.new_layer = stroke.new_layer | 1
	elif fixture == FIXTURE_WORLD:
		stroke.new_layer = stroke.new_layer | 2
	elif fixture == FIXTURE_INTERACT:
		stroke.new_layer = stroke.new_layer | 4
	elif not fixture.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "unknown physics fixture", "params.fixture")
	var bits: Dictionary = _plan_bits(command_id, params)
	if bits.get("ok", false) != true:
		return bits
	for layer_v: Variant in bits.get("layer_ops", []):
		if layer_v is Dictionary:
			stroke.layer_ops.append(layer_v as Dictionary)
	for mask_v: Variant in bits.get("mask_ops", []):
		if mask_v is Dictionary:
			stroke.mask_ops.append(mask_v as Dictionary)
	var action_name: String = "%sphysics.layers" % HHAgentConstants.UNDO_ACTION_PREFIX
	var committed: Dictionary = _commit_stroke(command_id, edited, action_name, stroke)
	if committed.get("ok", false) != true:
		return committed
	_meta.mark_dirty(str(params.get("scene", "")))
	var after: Dictionary = _physics_after(edited, params, body)
	_fill_layer_after(after, body)
	if not fixture.is_empty():
		after["fixture"] = fixture
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _nav_region(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var node: Node = _resolve(edited, str(params.get("node_path", "")))
	if node == null or not (node is NavigationRegion2D):
		return _unverified(command_id, "NavigationRegion2D not found")
	var packed_err: Dictionary = _reject_packed(command_id, node, edited)
	if not packed_err.is_empty():
		return packed_err
	var region: NavigationRegion2D = node as NavigationRegion2D
	var outline: PackedVector2Array = _points_param(params.get("outline"))
	if outline.size() < 3:
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "nav outline requires 3+ points", "params.outline")
	var navpoly_path: String = str(params.get("navpoly_path", ""))
	if navpoly_path.contains("::"):
		return _unverified(command_id, "refusing RAM-only NavigationPolygon durable ACK")
	var poly_hold: Dictionary = _ensure_navpoly(command_id, region, navpoly_path)
	if poly_hold.get("ok", false) != true:
		return poly_hold
	var poly: NavigationPolygon = poly_hold.get("poly") as NavigationPolygon
	poly.clear_outlines()
	poly.add_outline(outline)
	var stroke: NavRegionStroke = NavRegionStroke.new()
	stroke.region = region
	stroke.old_poly = region.navigation_polygon
	stroke.new_poly = poly
	stroke.traversable = outline
	stroke.parse_static = params.get("parse_static_colliders", true) == true
	var holes_v: Variant = params.get("obstructions", [])
	if typeof(holes_v) == TYPE_ARRAY:
		for hole_v: Variant in holes_v:
			var hole: PackedVector2Array = _points_param(hole_v)
			if hole.size() >= 3:
				stroke.holes.append(hole)
				poly.add_outline(hole)
	var action_name: String = "%sphysics.nav_region" % HHAgentConstants.UNDO_ACTION_PREFIX
	var committed: Dictionary = _commit_stroke(command_id, edited, action_name, stroke)
	if committed.get("ok", false) != true:
		return committed
	var live: NavigationPolygon = region.navigation_polygon
	if live == null:
		return _unverified(command_id, "NavigationPolygon assign readback missing")
	var persisted: Dictionary = {"ok": true, "disk_hash": ""}
	if _is_external_res(navpoly_path):
		persisted = _persist_res(command_id, live, navpoly_path)
		if persisted.get("ok", false) != true:
			return persisted
	_meta.mark_dirty(str(params.get("scene", "")))
	var after: Dictionary = _physics_after(edited, params, region)
	after["outline_count"] = live.get_outline_count()
	after["polygon_count"] = live.get_polygon_count()
	after["is_baking"] = _region_is_baking(region)
	after["bake_on_thread"] = false
	after["parse_static_colliders"] = stroke.parse_static
	after["disk_hash"] = str(persisted.get("disk_hash", ""))
	after["durable"] = _is_external_res(navpoly_path)
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _nav_agent(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var node: Node = _resolve(edited, str(params.get("node_path", "")))
	if node == null or not (node is NavigationAgent2D):
		return _unverified(command_id, "NavigationAgent2D not found")
	var packed_err: Dictionary = _reject_packed(command_id, node, edited)
	if not packed_err.is_empty():
		return packed_err
	var agent: NavigationAgent2D = node as NavigationAgent2D
	var stroke: NavAgentStroke = NavAgentStroke.new()
	stroke.agent = agent
	stroke.old_target = agent.target_position
	stroke.new_target = _vec2_param(params, "target_position")
	var action_name: String = "%sphysics.nav_agent" % HHAgentConstants.UNDO_ACTION_PREFIX
	var committed: Dictionary = _commit_stroke(command_id, edited, action_name, stroke)
	if committed.get("ok", false) != true:
		return committed
	_meta.mark_dirty(str(params.get("scene", "")))
	var after: Dictionary = _physics_after(edited, params, agent)
	after["target_position"] = {"x": agent.target_position.x, "y": agent.target_position.y}
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _path(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), {})
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var origin: Vector2 = _vec2_param(params, "from")
	var dest: Vector2 = _vec2_param(params, "to")
	var map: RID = RID()
	var hint: Node = _resolve(edited, str(params.get("node_path", "")))
	if hint is NavigationRegion2D:
		map = (hint as NavigationRegion2D).get_navigation_map()
	elif hint is NavigationAgent2D:
		map = (hint as NavigationAgent2D).get_navigation_map()
	if not map.is_valid():
		var world: World2D = edited.get_world_2d()
		if world != null:
			map = world.get_navigation_map()
	if not map.is_valid():
		return _path_unverified(command_id, "navigation map RID invalid; Alternative: editor nav map not synced")
	if NavigationServer2D.has_method("map_force_update"):
		NavigationServer2D.map_force_update(map)
	if not NavigationServer2D.map_is_active(map):
		return _path_unverified(command_id, "Alternative: map_is_active is false; editor nav map not synced; deferred R6")
	var iteration: int = NavigationServer2D.map_get_iteration_id(map)
	if iteration <= 0:
		return _path_unverified(command_id, "Alternative: map_get_iteration_id<=0; editor nav map not synced; deferred R6")
	var optimize: bool = params.get("optimize", true) == true
	var path: PackedVector2Array = NavigationServer2D.map_get_path(map, origin, dest, optimize)
	if path.is_empty():
		return _path_unverified(command_id, "map_get_path empty; refusing invented polyline; Alternative: editor nav map not synced")
	var points: Array = []
	var i: int = 0
	while i < path.size():
		points.append({"x": path[i].x, "y": path[i].y})
		i += 1
	var after: Dictionary = {
		"scene": str(params.get("scene", "")),
		"node_path": str(params.get("node_path", "")),
		"from": {"x": origin.x, "y": origin.y},
		"to": {"x": dest.x, "y": dest.y},
		"points": points,
		"point_count": points.size(),
		"map_is_active": true,
		"map_iteration_id": iteration,
		"invented_box": false,
		"invented_polyline": false,
		"source": "editor",
	}
	return _errors.ok_read(command_id, _checks(post), after)


func _lint(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), {})
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var start: Node = edited
	var focus: String = str(params.get("node_path", ""))
	if not focus.is_empty():
		var found: Node = _resolve(edited, focus)
		if found != null:
			start = found
	var issues: Array = []
	_lint_walk(edited, start, issues)
	var after: Dictionary = {
		"scene": str(params.get("scene", "")),
		"node_path": focus,
		"issues": issues,
		"issue_count": issues.size(),
		"invented_box": false,
		"source": "editor",
	}
	return _errors.ok_read(command_id, _checks(post), after)


func _debug(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), {})
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var start: Node = edited
	var focus: String = str(params.get("node_path", ""))
	if not focus.is_empty():
		var found: Node = _resolve(edited, focus)
		if found != null:
			start = found
	var items: Array = []
	_debug_walk(edited, start, items)
	var overlay: HHAgentOverlay = HHAgentOverlay.current()
	if overlay != null:
		overlay.show_engine_bounds(items)
	var after: Dictionary = {
		"scene": str(params.get("scene", "")),
		"node_path": focus,
		"items": items,
		"invented_box": false,
		"visible_collision_shapes_proven": false,
		"debug_collisions_hint_proven": false,
		"cm139_gap": true,
		"source": "engine",
	}
	return _errors.ok_read(command_id, _checks(post), after)


func _plan_body(command_id: String, body: CollisionObject2D, params: Dictionary) -> Dictionary:
	var flags: Dictionary = {}
	if params.has("motion_mode"):
		if not (body is CharacterBody2D):
			return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "motion_mode requires CharacterBody2D", "params.motion_mode")
		var mode_s: String = str(params.get("motion_mode", ""))
		if mode_s == MOTION_GROUNDED:
			flags["motion_mode"] = CharacterBody2D.MOTION_MODE_GROUNDED
		elif mode_s == MOTION_FLOATING:
			flags["motion_mode"] = CharacterBody2D.MOTION_MODE_FLOATING
		else:
			return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "unknown motion_mode", "params.motion_mode")
	if params.has("velocity"):
		if not (body is CharacterBody2D):
			return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "velocity requires CharacterBody2D", "params.velocity")
		flags["velocity"] = _vec2_param(params, "velocity")
	if params.has("mass") or params.has("gravity_scale") or params.has("linear_velocity") or params.has("contact_monitor") or params.has("max_contacts_reported") or params.has("freeze"):
		if not (body is RigidBody2D):
			return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "rigid fields require RigidBody2D", "params.node_path")
	if params.has("mass"):
		flags["mass"] = float(params.get("mass", 1.0))
	if params.has("gravity_scale"):
		flags["gravity_scale"] = float(params.get("gravity_scale", 1.0))
	if params.has("linear_velocity"):
		flags["linear_velocity"] = _vec2_param(params, "linear_velocity")
	if params.has("contact_monitor"):
		flags["contact_monitor"] = params.get("contact_monitor") == true
	if params.has("max_contacts_reported"):
		flags["max_contacts_reported"] = int(params.get("max_contacts_reported", 0))
	elif flags.get("contact_monitor", false) == true:
		flags["max_contacts_reported"] = 4
	if params.has("freeze"):
		flags["freeze"] = params.get("freeze") == true
	if params.has("monitoring") or params.has("monitorable"):
		if not (body is Area2D):
			return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "monitoring requires Area2D", "params.node_path")
	if params.has("monitoring"):
		flags["monitoring"] = params.get("monitoring") == true
	if params.has("monitorable"):
		flags["monitorable"] = params.get("monitorable") == true
	return {"ok": true, "flags": flags}


func _plan_material(command_id: String, body: CollisionObject2D, params: Dictionary) -> Dictionary:
	if not _supports_physics_material(body):
		return _errors.fail(
			command_id,
			HHAgentErrors.E_INVALID_TYPE,
			"physics_material_override requires RigidBody2D or StaticBody2D",
			"params.material",
		)
	var material_path: String = str(params.get("material", ""))
	var mat: PhysicsMaterial = null
	if not material_path.is_empty():
		var jail: Dictionary = _meta.jail(command_id, material_path)
		if jail.get("ok", false) != true:
			return jail
		if FileAccess.file_exists(material_path) or ResourceLoader.exists(material_path):
			var loaded: Resource = _load_res(material_path)
			if loaded == null or not (loaded is PhysicsMaterial):
				return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "material is not PhysicsMaterial", "params.material")
			mat = loaded as PhysicsMaterial
		else:
			if not _is_external_res(material_path):
				return _errors.fail(command_id, HHAgentErrors.E_PATH, "PhysicsMaterial persist requires .tres or .res", material_path)
			mat = PhysicsMaterial.new()
	else:
		mat = _material_of(body)
		if mat == null:
			mat = PhysicsMaterial.new()
	if params.has("friction"):
		mat.friction = float(params.get("friction", 1.0))
	if params.has("bounce"):
		mat.bounce = float(params.get("bounce", 0.0))
	return {"ok": true, "material": mat}


func _plan_geometry(command_id: String, edited: Node, params: Dictionary, kind: String) -> Dictionary:
	if kind != SHAPE_RECT and kind != SHAPE_CIRCLE and kind != SHAPE_CAPSULE and kind != SHAPE_CONVEX and kind != SHAPE_POLYGON:
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "unknown physics shape", "params.shape")
	var size_v: Vector2 = Vector2.ZERO
	var from_sprite: String = str(params.get("from_sprite", ""))
	var from_texture: String = str(params.get("from_texture", ""))
	if not from_sprite.is_empty():
		var spr_n: Node = _resolve(edited, from_sprite)
		if spr_n == null or not (spr_n is Sprite2D):
			return _unverified(command_id, "from_sprite Sprite2D not found")
		var spr: Sprite2D = spr_n as Sprite2D
		var local: Rect2 = spr.get_rect()
		if local.size.x > 0.0 and local.size.y > 0.0:
			size_v = local.size
		elif spr.texture != null:
			size_v = spr.texture.get_size()
		if size_v.x <= 0.0 or size_v.y <= 0.0:
			return _unverified(command_id, "Sprite2D.get_rect / Texture2D.get_size empty; refusing invented box")
	elif not from_texture.is_empty():
		var jail: Dictionary = _meta.jail(command_id, from_texture)
		if jail.get("ok", false) != true:
			return jail
		var res: Resource = _load_res(from_texture)
		if res == null or not (res is Texture2D):
			return _unverified(command_id, "from_texture is not a Texture2D")
		size_v = (res as Texture2D).get_size()
		if size_v.x <= 0.0 or size_v.y <= 0.0:
			return _unverified(command_id, "Texture2D.get_size empty; refusing invented box")
	elif params.has("size"):
		size_v = _vec2_param(params, "size")
	var out: Dictionary = {"ok": true, "kind": kind}
	if kind == SHAPE_RECT:
		if size_v.x <= 0.0 or size_v.y <= 0.0:
			return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "rectangle requires explicit size or asset bounds", "params.size")
		out["size"] = size_v
	elif kind == SHAPE_CIRCLE:
		var radius: float = float(params.get("radius", 0.0))
		if radius <= 0.0 and size_v.x > 0.0:
			radius = minf(size_v.x, size_v.y) * 0.5
		if radius <= 0.0:
			return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "circle requires explicit radius or asset bounds", "params.radius")
		out["radius"] = radius
	elif kind == SHAPE_CAPSULE:
		var cap_r: float = float(params.get("radius", 0.0))
		var cap_h: float = float(params.get("height", 0.0))
		if cap_r <= 0.0 and size_v.x > 0.0:
			cap_r = size_v.x * 0.5
		if cap_h <= 0.0 and size_v.y > 0.0:
			cap_h = size_v.y
		if cap_r <= 0.0 or cap_h <= 0.0:
			return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "capsule requires radius+height or asset bounds", "params.radius")
		out["radius"] = cap_r
		out["height"] = cap_h
	elif kind == SHAPE_CONVEX or kind == SHAPE_POLYGON:
		var pts: PackedVector2Array = _points_param(params.get("points"))
		if pts.size() < 3:
			return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "convex/polygon requires explicit points", "params.points")
		out["points"] = pts
	return out


func _build_shape(command_id: String, kind: String, geom: Dictionary, shape_path: String) -> Dictionary:
	var shape: Shape2D = null
	if _is_external_res(shape_path) and (FileAccess.file_exists(shape_path) or ResourceLoader.exists(shape_path)):
		var loaded: Resource = _load_res(shape_path)
		if loaded is Shape2D:
			shape = loaded as Shape2D
	if shape == null:
		if kind == SHAPE_RECT:
			shape = RectangleShape2D.new()
		elif kind == SHAPE_CIRCLE:
			shape = CircleShape2D.new()
		elif kind == SHAPE_CAPSULE:
			shape = CapsuleShape2D.new()
		elif kind == SHAPE_CONVEX:
			shape = ConvexPolygonShape2D.new()
		else:
			return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "CollisionShape2D cannot host a raw polygon", "params.shape")
	if kind == SHAPE_RECT and shape is RectangleShape2D:
		(shape as RectangleShape2D).size = geom.get("size") as Vector2
	elif kind == SHAPE_CIRCLE and shape is CircleShape2D:
		(shape as CircleShape2D).radius = float(geom.get("radius", 0.0))
	elif kind == SHAPE_CAPSULE and shape is CapsuleShape2D:
		(shape as CapsuleShape2D).radius = float(geom.get("radius", 0.0))
		(shape as CapsuleShape2D).height = float(geom.get("height", 0.0))
	elif kind == SHAPE_CONVEX and shape is ConvexPolygonShape2D:
		(shape as ConvexPolygonShape2D).points = geom.get("points") as PackedVector2Array
	else:
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "shape resource class mismatch", "params.shape")
	return {"ok": true, "shape": shape}


func _plan_bits(command_id: String, params: Dictionary) -> Dictionary:
	var layer_ops: Array[Dictionary] = []
	var mask_ops: Array[Dictionary] = []
	var raw_l: Variant = params.get("layer_bits", [])
	if typeof(raw_l) == TYPE_ARRAY:
		for item_v: Variant in raw_l:
			if typeof(item_v) != TYPE_DICTIONARY:
				return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "layer_bits item must be an object", "params.layer_bits")
			var rec: Dictionary = item_v
			var layer_i: int = int(rec.get("layer", 0))
			if layer_i < 1 or layer_i > 32:
				return _errors.fail(command_id, HHAgentErrors.E_OUT_OF_BOUNDS, "layer must be 1-32", "params.layer_bits")
			layer_ops.append({"layer": layer_i, "enabled": rec.get("enabled", false) == true})
	var raw_m: Variant = params.get("mask_bits", [])
	if typeof(raw_m) == TYPE_ARRAY:
		for item_v2: Variant in raw_m:
			if typeof(item_v2) != TYPE_DICTIONARY:
				return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "mask_bits item must be an object", "params.mask_bits")
			var rec_m: Dictionary = item_v2
			var mask_i: int = int(rec_m.get("layer", 0))
			if mask_i < 1 or mask_i > 32:
				return _errors.fail(command_id, HHAgentErrors.E_OUT_OF_BOUNDS, "mask layer must be 1-32", "params.mask_bits")
			mask_ops.append({"layer": mask_i, "enabled": rec_m.get("enabled", false) == true})
	return {"ok": true, "layer_ops": layer_ops, "mask_ops": mask_ops}


func _ensure_navpoly(command_id: String, region: NavigationRegion2D, navpoly_path: String) -> Dictionary:
	if not navpoly_path.is_empty():
		if FileAccess.file_exists(navpoly_path) or ResourceLoader.exists(navpoly_path):
			var jail: Dictionary = _meta.jail(command_id, navpoly_path)
			if jail.get("ok", false) != true:
				return jail
			var res: Resource = _load_res(navpoly_path)
			if res == null or not (res is NavigationPolygon):
				return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "navpoly_path is not a NavigationPolygon", navpoly_path)
			return {"ok": true, "poly": res as NavigationPolygon}
		var created_jail: Dictionary = _meta.jail(command_id, navpoly_path)
		if created_jail.get("ok", false) != true:
			return created_jail
		if not _is_external_res(navpoly_path):
			return _errors.fail(command_id, HHAgentErrors.E_PATH, "NavigationPolygon persist requires .tres or .res", navpoly_path)
		return {"ok": true, "poly": NavigationPolygon.new()}
	if region.navigation_polygon != null:
		return {"ok": true, "poly": region.navigation_polygon}
	return {"ok": true, "poly": NavigationPolygon.new()}


static func _write_body(node: CollisionObject2D, d: Dictionary) -> void:
	if node is CharacterBody2D:
		var cb: CharacterBody2D = node as CharacterBody2D
		if d.has("motion_mode"):
			cb.motion_mode = int(d.get("motion_mode", CharacterBody2D.MOTION_MODE_GROUNDED))
		if d.has("velocity"):
			cb.velocity = d.get("velocity") as Vector2
	if node is RigidBody2D:
		var rb: RigidBody2D = node as RigidBody2D
		if d.has("mass"):
			rb.mass = float(d.get("mass", 1.0))
		if d.has("gravity_scale"):
			rb.gravity_scale = float(d.get("gravity_scale", 1.0))
		if d.has("linear_velocity"):
			rb.linear_velocity = d.get("linear_velocity") as Vector2
		if d.has("contact_monitor"):
			rb.contact_monitor = d.get("contact_monitor") == true
		if d.has("max_contacts_reported"):
			rb.max_contacts_reported = int(d.get("max_contacts_reported", 0))
		if d.has("freeze"):
			rb.freeze = d.get("freeze") == true
	if node is Area2D:
		var area: Area2D = node as Area2D
		if d.has("monitoring"):
			area.monitoring = d.get("monitoring") == true
		if d.has("monitorable"):
			area.monitorable = d.get("monitorable") == true
	if d.has("physics_material_override"):
		_set_material(node, d.get("physics_material_override") as PhysicsMaterial)


static func _read_body(node: CollisionObject2D) -> Dictionary:
	var out: Dictionary = {}
	if _supports_physics_material(node):
		out["physics_material_override"] = _material_of(node)
	if node is CharacterBody2D:
		var cb: CharacterBody2D = node as CharacterBody2D
		out["motion_mode"] = cb.motion_mode
		out["velocity"] = cb.velocity
	if node is RigidBody2D:
		var rb: RigidBody2D = node as RigidBody2D
		out["mass"] = rb.mass
		out["gravity_scale"] = rb.gravity_scale
		out["linear_velocity"] = rb.linear_velocity
		out["contact_monitor"] = rb.contact_monitor
		out["max_contacts_reported"] = rb.max_contacts_reported
		out["freeze"] = rb.freeze
	if node is Area2D:
		var area: Area2D = node as Area2D
		out["monitoring"] = area.monitoring
		out["monitorable"] = area.monitorable
	return out


static func _wait_region_bake(region: NavigationRegion2D) -> bool:
	return _region_is_baking(region) == false


static func _region_is_baking(region: NavigationRegion2D) -> bool:
	# Godot 4.7.1 NavigationRegion2D uses is_baking(). The older name
	# is_baking_navigation_polygon is not on this class.
	if region == null:
		return false
	if region.has_method("is_baking"):
		return region.is_baking() == true
	return false


static func _bake_source(
	region: NavigationRegion2D,
	poly: NavigationPolygon,
	traversable: PackedVector2Array,
	holes: Array[PackedVector2Array],
	parse_static: bool,
) -> void:
	if poly == null or region == null:
		return
	var src: NavigationMeshSourceGeometryData2D = NavigationMeshSourceGeometryData2D.new()
	if traversable.size() >= 3:
		src.add_traversable_outline(traversable)
	var i: int = 0
	while i < holes.size():
		if holes[i].size() >= 3:
			src.add_obstruction_outline(holes[i])
		i += 1
	if parse_static:
		NavigationServer2D.parse_source_geometry_data(poly, src, region)
	NavigationServer2D.bake_from_source_geometry_data(poly, src)


func _fill_body_after(after: Dictionary, body: CollisionObject2D) -> void:
	if body is CharacterBody2D:
		var cb: CharacterBody2D = body as CharacterBody2D
		after["motion_mode"] = MOTION_GROUNDED if cb.motion_mode == CharacterBody2D.MOTION_MODE_GROUNDED else MOTION_FLOATING
		after["velocity"] = {"x": cb.velocity.x, "y": cb.velocity.y}
		after["velocity_stored_only"] = true
	if body is RigidBody2D:
		var rb: RigidBody2D = body as RigidBody2D
		after["mass"] = rb.mass
		after["gravity_scale"] = rb.gravity_scale
		after["linear_velocity"] = {"x": rb.linear_velocity.x, "y": rb.linear_velocity.y}
		after["contact_monitor"] = rb.contact_monitor
		after["max_contacts_reported"] = rb.max_contacts_reported
		after["freeze"] = rb.freeze
	if body is Area2D:
		var area: Area2D = body as Area2D
		after["monitoring"] = area.monitoring
		after["monitorable"] = area.monitorable
	after["has_material"] = _material_of(body) != null
	_fill_layer_after(after, body)


func _fill_layer_after(after: Dictionary, body: CollisionObject2D) -> void:
	after["collision_layer"] = body.collision_layer
	after["collision_mask"] = body.collision_mask
	var layer_values: Dictionary = {}
	var mask_values: Dictionary = {}
	var i: int = 1
	while i <= 32:
		var key_s: String = str(i)
		layer_values[key_s] = body.get_collision_layer_value(i)
		mask_values[key_s] = body.get_collision_mask_value(i)
		i += 1
	after["layer_values"] = layer_values
	after["mask_values"] = mask_values


func _read_geometry(host: Node) -> Dictionary:
	if host is CollisionPolygon2D:
		return {"points": _points_json((host as CollisionPolygon2D).polygon)}
	if host is CollisionShape2D:
		var shape: Shape2D = (host as CollisionShape2D).shape
		if shape is RectangleShape2D:
			var sz: Vector2 = (shape as RectangleShape2D).size
			return {"size": {"x": sz.x, "y": sz.y}}
		if shape is CircleShape2D:
			return {"radius": (shape as CircleShape2D).radius}
		if shape is CapsuleShape2D:
			var cap: CapsuleShape2D = shape as CapsuleShape2D
			return {"radius": cap.radius, "height": cap.height}
		if shape is ConvexPolygonShape2D:
			return {"points": _points_json((shape as ConvexPolygonShape2D).points)}
	return {}


func _shape_class_of(host: Node) -> String:
	if host is CollisionPolygon2D:
		return "CollisionPolygon2D"
	if host is CollisionShape2D:
		var shape: Shape2D = (host as CollisionShape2D).shape
		if shape != null:
			return shape.get_class()
	return ""


func _physics_after(edited: Node, params: Dictionary, node: Node) -> Dictionary:
	var after: Dictionary = _meta.snapshot(edited, str(params.get("scene", "")))
	after["scene"] = str(params.get("scene", ""))
	after["node_path"] = str(params.get("node_path", ""))
	after["class_name"] = node.get_class() if node != null else ""
	after["path"] = str(params.get("node_path", ""))
	after["invented_box"] = false
	after["used_engine_transform"] = true
	after["source"] = "editor"
	var packed: Dictionary = engine_world_rect(node)
	if packed.get("ok", false) == true and packed.get("invented_box", false) != true:
		var rect_v: Variant = packed.get("rect")
		if rect_v is Rect2:
			var r: Rect2 = rect_v
			after["rect"] = _xywh(r)
			after["rect_source"] = str(packed.get("rect_source", ""))
	return after


func _lint_walk(edited: Node, node: Node, issues: Array) -> void:
	if node == null:
		return
	if node != edited and node.owner != edited:
		issues.append({"node_path": _rel_path(edited, node), "code": "missing_owner", "message": "node.owner is not the edited scene root"})
	if node is CollisionShape2D:
		if (node as CollisionShape2D).shape == null:
			issues.append({"node_path": _rel_path(edited, node), "code": "null_shape", "message": "CollisionShape2D.shape is null"})
	if node is CollisionObject2D:
		var body: CollisionObject2D = node as CollisionObject2D
		if not _has_shape_child(body) and not (node is CollisionShape2D):
			issues.append({"node_path": _rel_path(edited, node), "code": "null_shape", "message": "CollisionObject2D has no shape fixture"})
		if body.collision_layer == 0:
			issues.append({"node_path": _rel_path(edited, node), "code": "layer0", "message": "collision_layer is 0"})
		if body.collision_mask == 0:
			issues.append({"node_path": _rel_path(edited, node), "code": "mask0", "message": "collision_mask is 0"})
	if node is Node2D:
		var n2: Node2D = node as Node2D
		var sc: Vector2 = n2.global_scale
		if absf(sc.x - sc.y) > 0.001:
			issues.append({"node_path": _rel_path(edited, node), "code": "non_uniform_scale", "message": "global_scale is non-uniform"})
	var i: int = 0
	while i < node.get_child_count():
		_lint_walk(edited, node.get_child(i), issues)
		i += 1


func _debug_walk(edited: Node, node: Node, items: Array) -> void:
	if node == null:
		return
	if (
		node is CollisionShape2D
		or node is CollisionPolygon2D
		or node is NavigationRegion2D
		or node is CollisionObject2D
	):
		var packed: Dictionary = engine_world_rect(node)
		if packed.get("ok", false) == true and packed.get("invented_box", false) != true:
			var rect_v: Variant = packed.get("rect")
			if rect_v is Rect2:
				var r: Rect2 = rect_v
				if r.size.x > 0.0 and r.size.y > 0.0:
					items.append({
						"node_path": _rel_path(edited, node),
						"class_name": node.get_class(),
						"rect": _xywh(r),
						"rect_source": str(packed.get("rect_source", "")),
						"invented_box": false,
					})
	var i: int = 0
	while i < node.get_child_count():
		_debug_walk(edited, node.get_child(i), items)
		i += 1


func _has_shape_child(body: CollisionObject2D) -> bool:
	var i: int = 0
	while i < body.get_child_count():
		var child: Node = body.get_child(i)
		if child is CollisionShape2D or child is CollisionPolygon2D:
			return true
		i += 1
	return false


func _shape_host(command_id: String, edited: Node, path_s: String) -> Dictionary:
	var node: Node = _resolve(edited, path_s)
	if node == null:
		return _unverified(command_id, "shape host not found")
	if node is CollisionShape2D or node is CollisionPolygon2D:
		return {"ok": true, "host": node}
	if node is CollisionObject2D:
		var i: int = 0
		while i < node.get_child_count():
			var child: Node = node.get_child(i)
			if child is CollisionShape2D or child is CollisionPolygon2D:
				return {"ok": true, "host": child}
			i += 1
		return _unverified(command_id, "CollisionShape2D required under CollisionObject2D")
	return _errors.fail(
		command_id,
		HHAgentErrors.E_INVALID_TYPE,
		"physics.shape requires CollisionShape2D or CollisionPolygon2D",
		"params.node_path",
	)


func _hold_collision(command_id: String, params: Dictionary, precondition: Dictionary) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var node: Node = _resolve(edited, str(params.get("node_path", "")))
	if node == null:
		return _unverified(command_id, "node not found")
	if not (node is CollisionObject2D):
		return _errors.fail(
			command_id,
			HHAgentErrors.E_INVALID_TYPE,
			"physics verb requires a CollisionObject2D",
			"params.node_path",
		)
	var packed_err: Dictionary = _reject_packed(command_id, node, edited)
	if not packed_err.is_empty():
		return packed_err
	return {"ok": true, "root": edited, "body": node as CollisionObject2D}


func _commit_stroke(command_id: String, edited: Node, action_name: String, stroke: RefCounted) -> Dictionary:
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	mgr.add_do_method(stroke, "apply")
	mgr.add_undo_method(stroke, "revert")
	mgr.add_do_reference(stroke)
	mgr.commit_action()
	return {"ok": true}


func _hold_scene(command_id: String, res_path: String, precondition: Dictionary) -> Dictionary:
	var gated: Dictionary = _meta.jail(command_id, res_path)
	if gated.get("ok", false) != true:
		return gated
	if not _meta.is_scene_path(res_path):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "path must be .tscn or .scn", res_path)
	if not FileAccess.file_exists(res_path):
		return _unverified(command_id, "scene missing")
	var edited: Node = EditorInterface.get_edited_scene_root()
	if edited == null or edited.scene_file_path != res_path:
		EditorInterface.open_scene_from_path(res_path)
		edited = EditorInterface.get_edited_scene_root()
	if edited == null or edited.scene_file_path != res_path:
		return _unverified(command_id, "edited_scene is not %s" % res_path)
	if not precondition.is_empty():
		var want_fp: String = str(precondition.get("fingerprint", ""))
		var want_hv: String = str(precondition.get("history_version", ""))
		var want_hash: String = str(precondition.get("scene_hash", ""))
		if not want_fp.is_empty() and want_fp != _meta.fingerprint(edited):
			return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "editor fingerprint changed; resync", "precondition.fingerprint")
		if not want_hv.is_empty() and want_hv != str(_meta.history_version(edited)):
			return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "editor history version changed; resync", "precondition.history_version")
		if not want_hash.is_empty() and want_hash != _meta.disk_hash(res_path):
			return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "disk hash changed (human/external edit); resync", "precondition.scene_hash")
	return {"ok": true, "root": edited}


func _persist_res(command_id: String, res: Resource, res_path: String) -> Dictionary:
	var jail: Dictionary = _meta.jail(command_id, res_path)
	if jail.get("ok", false) != true:
		return jail
	if not _is_external_res(res_path):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "resource persist requires .tres or .res", res_path)
	var dir_err: Error = _meta.ensure_parent_dir(res_path)
	if dir_err != OK:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "cannot create resource directory", res_path)
	var save_err: Error = ResourceSaver.save(res, res_path)
	if save_err != OK:
		return _unverified(command_id, "ResourceSaver.save failed: %s" % error_string(save_err))
	_meta.refresh_fs(res_path)
	if not FileAccess.file_exists(res_path):
		return _unverified(command_id, "resource file missing after save")
	var disk: String = _meta.disk_hash(res_path)
	if disk.is_empty() or disk == "missing":
		return _unverified(command_id, "resource disk hash missing after save")
	return {"ok": true, "disk_hash": disk, "path": res_path}


func _resolve(root: Node, path_s: String) -> Node:
	if root == null:
		return null
	if path_s.is_empty() or path_s == "." or path_s == root.name:
		return root
	var found: Node = root.get_node_or_null(NodePath(path_s))
	if found != null:
		return found
	if path_s.begins_with(root.name + "/"):
		return root.get_node_or_null(NodePath(path_s.substr(root.name.length() + 1)))
	return null


func _reject_packed(command_id: String, node: Node, edited: Node) -> Dictionary:
	if _identity.is_packed_internal(node, edited):
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"packed instance child requires make_local; refusing a flatten",
			"params.node_path",
		)
	return {}


func _load_res(res_path: String) -> Resource:
	if res_path.is_empty():
		return null
	if ResourceLoader.exists(res_path):
		var loaded: Resource = ResourceLoader.load(res_path, "", ResourceLoader.CACHE_MODE_REUSE)
		if loaded != null:
			return loaded
	if FileAccess.file_exists(res_path):
		return ResourceLoader.load(res_path)
	return null


func _is_external_res(path_s: String) -> bool:
	return (path_s.ends_with(".tres") or path_s.ends_with(".res")) and not path_s.contains("::")


func _has_prop(obj: Object, name_s: String) -> bool:
	if obj == null:
		return false
	for item_v: Variant in obj.get_property_list():
		if item_v is Dictionary and str((item_v as Dictionary).get("name", "")) == name_s:
			return true
	return false


static func _supports_physics_material(node: CollisionObject2D) -> bool:
	return node is RigidBody2D or node is StaticBody2D


static func _material_of(node: CollisionObject2D) -> PhysicsMaterial:
	if node is RigidBody2D:
		return (node as RigidBody2D).physics_material_override
	if node is StaticBody2D:
		return (node as StaticBody2D).physics_material_override
	return null


static func _set_material(node: CollisionObject2D, mat: PhysicsMaterial) -> void:
	if node is RigidBody2D:
		(node as RigidBody2D).physics_material_override = mat
	elif node is StaticBody2D:
		(node as StaticBody2D).physics_material_override = mat


func _rel_path(root: Node, node: Node) -> String:
	if root == null or node == null:
		return ""
	if node == root:
		return "."
	return str(root.get_path_to(node))


func _xywh(r: Rect2) -> Dictionary:
	return {"x": r.position.x, "y": r.position.y, "w": r.size.x, "h": r.size.y}


func _vec2_param(params: Dictionary, key: String) -> Vector2:
	return _vec2_raw(params.get(key))


func _vec2_raw(raw: Variant) -> Vector2:
	if raw is Dictionary:
		var d: Dictionary = raw
		return Vector2(float(d.get("x", 0.0)), float(d.get("y", 0.0)))
	if raw is Vector2:
		return raw
	return Vector2.ZERO


func _points_param(raw: Variant) -> PackedVector2Array:
	var out: PackedVector2Array = PackedVector2Array()
	if typeof(raw) != TYPE_ARRAY:
		return out
	for item_v: Variant in raw:
		out.append(_vec2_raw(item_v))
	return out


func _points_json(points: PackedVector2Array) -> Array:
	var out: Array = []
	var i: int = 0
	while i < points.size():
		out.append({"x": points[i].x, "y": points[i].y})
		i += 1
	return out


func _mgr() -> EditorUndoRedoManager:
	return EditorInterface.get_editor_undo_redo()


func _path_unverified(command_id: String, message: String) -> Dictionary:
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, message, "")


func _unverified(command_id: String, message: String) -> Dictionary:
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, message, "")


func _checks(post: String) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	out.append(post)
	return out


static func _rect_fail() -> Dictionary:
	return {
		"ok": false,
		"rect": Rect2(),
		"rect_source": "none",
		"invented_box": false,
		"used_engine_transform": false,
	}


static func _shape_world_rect(cs: CollisionShape2D) -> Dictionary:
	if cs == null or cs.shape == null:
		return _rect_fail()
	var local: Rect2 = _shape_local_rect(cs.shape)
	if local.size.x <= 0.0 or local.size.y <= 0.0:
		return _rect_fail()
	return {
		"ok": true,
		"rect": cs.get_global_transform() * local,
		"rect_source": "shape",
		"invented_box": false,
		"used_engine_transform": true,
	}


static func _poly_world_rect(cp: CollisionPolygon2D) -> Dictionary:
	if cp == null or cp.polygon.size() < 1:
		return _rect_fail()
	var local: Rect2 = _points_rect(cp.polygon)
	if local.size.x <= 0.0 or local.size.y <= 0.0:
		return _rect_fail()
	return {
		"ok": true,
		"rect": cp.get_global_transform() * local,
		"rect_source": "polygon",
		"invented_box": false,
		"used_engine_transform": true,
	}


static func _body_world_rect(body: CollisionObject2D) -> Dictionary:
	if body == null:
		return _rect_fail()
	var merged: Rect2 = Rect2()
	var have: bool = false
	var i: int = 0
	while i < body.get_child_count():
		var child: Node = body.get_child(i)
		var packed: Dictionary = engine_world_rect(child)
		if packed.get("ok", false) == true and packed.get("invented_box", false) != true:
			var rect_v: Variant = packed.get("rect")
			if rect_v is Rect2:
				var r: Rect2 = rect_v
				if r.size.x > 0.0 and r.size.y > 0.0:
					if have:
						merged = merged.merge(r)
					else:
						merged = r
						have = true
		i += 1
	if not have:
		return _rect_fail()
	return {
		"ok": true,
		"rect": merged,
		"rect_source": "shapes",
		"invented_box": false,
		"used_engine_transform": true,
	}


static func _nav_world_rect(region: NavigationRegion2D) -> Dictionary:
	if region == null:
		return _rect_fail()
	# Do not call get_bounds(): it waits on an editor bake and deadlocks _process.
	var poly: NavigationPolygon = region.navigation_polygon
	if poly == null:
		return _rect_fail()
	var merged: Rect2 = Rect2()
	var have: bool = false
	var i: int = 0
	while i < poly.get_outline_count():
		var pts: PackedVector2Array = poly.get_outline(i)
		var local: Rect2 = _points_rect(pts)
		if local.size.x > 0.0 and local.size.y > 0.0:
			var world: Rect2 = region.get_global_transform() * local
			if have:
				merged = merged.merge(world)
			else:
				merged = world
				have = true
		i += 1
	if not have:
		return _rect_fail()
	return {
		"ok": true,
		"rect": merged,
		"rect_source": "outline",
		"invented_box": false,
		"used_engine_transform": true,
	}


static func _shape_local_rect(shape: Shape2D) -> Rect2:
	if shape is RectangleShape2D:
		var sz: Vector2 = (shape as RectangleShape2D).size
		return Rect2(-sz * 0.5, sz)
	if shape is CircleShape2D:
		var radius: float = (shape as CircleShape2D).radius
		return Rect2(Vector2(-radius, -radius), Vector2(radius * 2.0, radius * 2.0))
	if shape is CapsuleShape2D:
		var cap: CapsuleShape2D = shape as CapsuleShape2D
		return Rect2(Vector2(-cap.radius, -cap.height * 0.5), Vector2(cap.radius * 2.0, cap.height))
	if shape is ConvexPolygonShape2D:
		return _points_rect((shape as ConvexPolygonShape2D).points)
	return Rect2()


static func _points_rect(points: PackedVector2Array) -> Rect2:
	if points.size() < 1:
		return Rect2()
	var r: Rect2 = Rect2(points[0], Vector2.ZERO)
	var i: int = 1
	while i < points.size():
		r = r.expand(points[i])
		i += 1
	return r

extends Node3D
## Authored consumer state stays outside the imported GLB and its generated cache.

@export var authored_material: StandardMaterial3D
@export var authored_marker: String = "gt05-authored-consumer-v1"
var render_lods: Dictionary = {}
var generated_roles: Array[Node] = []
var navigation_regions: Dictionary = {}


func apply_role(mesh: MeshInstance3D, role: String, lod: int) -> Dictionary:
	if role == "render":
		render_lods[String(mesh.name)] = {"node": mesh, "lod": lod}
		mesh.visible = lod == 0
		return {"kind": "render", "lod": lod, "visible": mesh.visible}
	if role == "collider":
		var body: StaticBody3D = StaticBody3D.new()
		body.name = String(mesh.name) + "_body"
		add_child(body)
		body.global_transform = mesh.global_transform
		var shape: CollisionShape3D = CollisionShape3D.new()
		shape.name = "AuthoredCollision"
		shape.shape = mesh.mesh.create_trimesh_shape()
		body.add_child(shape)
		mesh.visible = false
		generated_roles.append(body)
		var concave: ConcavePolygonShape3D = shape.shape as ConcavePolygonShape3D
		return {"kind": "collider", "body_class": body.get_class(),
			"shape_class": shape.shape.get_class(), "face_vertices": concave.get_faces().size(),
			"collision_layer": body.collision_layer, "disabled": shape.disabled}
	if role == "nav":
		# The imported proxy is a closed thin box. Only its actual top triangles
		# are walkable; importing its sides/bottom as nav polygons is incorrect.
		var bounds: AABB = mesh.get_aabb()
		var faces: PackedVector3Array = mesh.mesh.get_faces()
		var top_vertices: PackedVector3Array = PackedVector3Array()
		var top_polygons: Array[PackedInt32Array] = []
		var top_area: float = 0.0
		for index: int in range(0, faces.size(), 3):
			var a: Vector3 = faces[index]
			var b: Vector3 = faces[index + 1]
			var c: Vector3 = faces[index + 2]
			if absf(a.y - bounds.end.y) > 0.000001 or absf(b.y - bounds.end.y) > 0.000001 or absf(c.y - bounds.end.y) > 0.000001:
				continue
			# NavigationServer's closest-point normal uses (b-a) cross (c-a).
			# Plane(a,b,c) uses the opposite, clockwise convention by default.
			if (b - a).cross(c - a).dot(Vector3.UP) < 0.0:
				var swap: Vector3 = b
				b = c
				c = swap
			top_area += (b - a).cross(c - a).length() * 0.5
			var polygon: PackedInt32Array = PackedInt32Array()
			for point: Vector3 in [a, b, c]:
				var vertex_index: int = top_vertices.find(point)
				if vertex_index < 0:
					vertex_index = top_vertices.size()
					top_vertices.append(point)
				polygon.append(vertex_index)
			top_polygons.append(polygon)
		if top_vertices.size() != 4 or top_polygons.size() != 2 or absf(top_area - bounds.size.x * bounds.size.z) > 0.000001:
			return {"error": "INVALID_BOX_TOP_NAV_SURFACE"}
		var map_rid: RID = get_world_3d().navigation_map
		var iteration_before: int = NavigationServer3D.map_get_iteration_id(map_rid)
		var region: NavigationRegion3D = NavigationRegion3D.new()
		region.name = String(mesh.name) + "_region"
		var navigation: NavigationMesh = NavigationMesh.new()
		navigation.set_vertices(top_vertices)
		for polygon: PackedInt32Array in top_polygons:
			navigation.add_polygon(polygon)
		region.navigation_mesh = navigation
		region.navigation_layers = 1
		add_child(region)
		region.global_transform = mesh.global_transform
		mesh.visible = false
		generated_roles.append(region)
		navigation_regions[String(mesh.name)] = region
		var world_vertices: Array[Array] = []
		for point: Vector3 in navigation.get_vertices():
			var world_point: Vector3 = region.global_transform * point
			world_vertices.append([world_point.x, world_point.y, world_point.z])
		return {"kind": "nav", "region_class": region.get_class(),
			"vertices": navigation.get_vertices().size(), "polygons": navigation.get_polygon_count(),
			"enabled": region.enabled, "surface_policy": "imported_box_top_triangles",
			"surface_vertices_world": world_vertices, "surface_area": top_area,
			"map_iteration_before": iteration_before}
	return {"error": "UNSUPPORTED_EXPLICIT_ROLE"}


func set_lod(level: int) -> Dictionary:
	var states: Dictionary = {}
	for key: String in render_lods:
		var row: Dictionary = render_lods[key]
		var mesh: MeshInstance3D = row["node"] as MeshInstance3D
		var paired: bool = render_lods.has(key.trim_suffix("_lod0") + "_lod1") or int(row["lod"]) == 1
		mesh.visible = int(row["lod"]) == level if paired else true
		states[key] = mesh.visible
	return states


func attach_marker(skeleton: Skeleton3D, bone_name: String, local_pose: Dictionary) -> BoneAttachment3D:
	var attachment: BoneAttachment3D = BoneAttachment3D.new()
	attachment.name = "AuthoredHandAttachment"
	attachment.bone_name = bone_name
	attachment.override_pose = false
	skeleton.add_child(attachment)
	var marker: MeshInstance3D = MeshInstance3D.new()
	marker.name = "AuthoredSocketMarker"
	var sphere: SphereMesh = SphereMesh.new()
	sphere.radius = 0.035
	sphere.height = 0.07
	marker.mesh = sphere
	marker.material_override = authored_material
	var position_data: Array = local_pose["position"]
	var rotation_data: Array = local_pose["rotation_xyzw"]
	var scale_data: Array = local_pose["scale"]
	marker.transform = Transform3D(Basis(Quaternion(rotation_data[0], rotation_data[1], rotation_data[2], rotation_data[3])).scaled(
		Vector3(scale_data[0], scale_data[1], scale_data[2])), Vector3(position_data[0], position_data[1], position_data[2]))
	attachment.add_child(marker)
	generated_roles.append(attachment)
	return attachment

extends SceneTree
## Fixed observation program. A zero exit is not pipeline acceptance.
## Host compares these native values to the independently validated producer data.

const VERSION_HASH: String = "ed1daf0bf"
const INPUT: String = "res://input/"
const MAX_JSON_BYTES: int = 262144
const MAX_REPORT_BYTES: int = 1048576
var failed: bool = false
var phase: String = ""
var seed: Dictionary = {}
var wrapper: Node3D
var imported: Node3D
var native_nodes: Array[Node] = []
var mesh_nodes: Dictionary = {}
var rigs: Dictionary = {}
var players: Array[AnimationPlayer] = []
var source_sockets: Dictionary = {}
var authored_sockets: Dictionary = {}
var decoded_texture_bytes: int = 0


func _initialize() -> void:
	call_deferred("_run")


func _check(value: bool, code: String) -> bool:
	if not value:
		failed = true
		push_error(code)
		quit(17)
	return value


func _json(path: String) -> Dictionary:
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if not _check(file != null, "GT05_MISSING_FIXED_JSON"):
		return {}
	if not _check(file.get_length() > 0 and file.get_length() <= MAX_JSON_BYTES, "GT05_JSON_SIZE"):
		file.close()
		return {}
	var parser: JSON = JSON.new()
	var error: Error = parser.parse(file.get_as_text())
	file.close()
	if not _check(error == OK and parser.data is Dictionary, "GT05_JSON_OBJECT"):
		return {}
	return parser.data as Dictionary


func _vec(value: Vector3) -> Array[float]:
	return [value.x, value.y, value.z]


func _quat(value: Quaternion) -> Array[float]:
	return [value.x, value.y, value.z, value.w]


func _transform(value: Transform3D) -> Dictionary:
	return {"position": _vec(value.origin),
		"rotation_xyzw": _quat(value.basis.get_rotation_quaternion()),
		"scale": _vec(value.basis.get_scale())}


func _collect(node: Node) -> void:
	native_nodes.append(node)
	if node is AnimationPlayer:
		players.append(node as AnimationPlayer)
	for child: Node in node.get_children():
		_collect(child)


func _named(name_value: String) -> Node:
	var matches: Array[Node] = []
	for node: Node in native_nodes:
		if String(node.name) == name_value:
			matches.append(node)
	if not _check(matches.size() == 1, "GT05_MISSING_OR_AMBIGUOUS_EXACT_NAME"):
		return null
	return matches[0]


func _material(material: Material) -> Dictionary:
	if not _check(material is BaseMaterial3D, "GT05_NATIVE_MATERIAL_TYPE"):
		return {}
	var pbr: BaseMaterial3D = material as BaseMaterial3D
	var textures: Dictionary = {}
	var selected_textures: Dictionary = {"0": pbr.albedo_texture, "4": pbr.normal_texture,
		"1": pbr.metallic_texture, "2": pbr.roughness_texture, "17": pbr.orm_texture}
	for slot: String in selected_textures:
		var texture: Texture2D = selected_textures[slot] as Texture2D
		if texture != null:
			if not _check(texture.get_width() > 0 and texture.get_width() <= 4096 and texture.get_height() > 0 and
					texture.get_height() <= 4096, "GT05_TEXTURE_DIMENSION"):
				return {}
			decoded_texture_bytes += texture.get_width() * texture.get_height() * 4
			if not _check(decoded_texture_bytes <= 134217728, "GT05_TEXTURE_DECODE_BUDGET"):
				return {}
			var pixels: Image = texture.get_image()
			if not _check(pixels != null and not pixels.is_empty(), "GT05_TEXTURE_IMAGE_READBACK"):
				return {}
			if pixels.is_compressed():
				if not _check(pixels.decompress() == OK, "GT05_TEXTURE_DECOMPRESS"):
					return {}
			pixels.convert(Image.FORMAT_RGBA8)
			pixels.clear_mipmaps()
			var digest: HashingContext = HashingContext.new()
			digest.start(HashingContext.HASH_SHA256)
			digest.update(pixels.get_data())
			textures[str(slot)] = {"width": texture.get_width(), "height": texture.get_height(),
				"class": texture.get_class(), "decoded_rgba8_sha256": digest.finish().hex_encode()}
	return {"name": String(pbr.resource_name), "class": pbr.get_class(),
		"base_color": [pbr.albedo_color.r, pbr.albedo_color.g, pbr.albedo_color.b, pbr.albedo_color.a],
		"metallic": pbr.metallic, "roughness": pbr.roughness,
		"metallic_channel": pbr.metallic_texture_channel, "roughness_channel": pbr.roughness_texture_channel,
		"normal_enabled": pbr.normal_enabled, "normal_scale": pbr.normal_scale,
		"transparency": pbr.transparency, "cull_mode": pbr.cull_mode, "textures": textures}


func _mesh(mesh: MeshInstance3D) -> Dictionary:
	if not _check(mesh.mesh != null, "GT05_NATIVE_MESH_MISSING"):
		return {}
	var skeleton: Skeleton3D = mesh.get_node_or_null(mesh.skeleton) as Skeleton3D
	var bind_names: Array[String] = []
	var bind_poses: Array[Dictionary] = []
	if mesh.skin != null:
		if not _check(skeleton != null, "GT05_SKIN_SKELETON_MISSING"):
			return {}
		for index: int in range(mesh.skin.get_bind_count()):
			var bone_name: String = String(mesh.skin.get_bind_name(index))
			if bone_name.is_empty():
				var bone_index: int = mesh.skin.get_bind_bone(index)
				if not _check(bone_index >= 0 and bone_index < skeleton.get_bone_count(), "GT05_SKIN_BIND_INDEX"):
					return {}
				bone_name = String(skeleton.get_bone_name(bone_index))
			bind_names.append(bone_name)
			bind_poses.append(_transform(mesh.skin.get_bind_pose(index)))
	var vertices: Array[Dictionary] = []
	var surfaces: Array[Dictionary] = []
	var triangle_count: int = 0
	for surface_index: int in range(mesh.mesh.get_surface_count()):
		if not _check(mesh.mesh.surface_get_primitive_type(surface_index) == Mesh.PRIMITIVE_TRIANGLES, "GT05_TRIANGLES_ONLY"):
			return {}
		var arrays: Array = mesh.mesh.surface_get_arrays(surface_index)
		var positions: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
		var skin_indices: PackedInt32Array = PackedInt32Array()
		var weights: PackedFloat32Array = PackedFloat32Array()
		if arrays[Mesh.ARRAY_BONES] != null:
			skin_indices = arrays[Mesh.ARRAY_BONES]
		if arrays[Mesh.ARRAY_WEIGHTS] != null:
			weights = arrays[Mesh.ARRAY_WEIGHTS]
		var triangles: int = int((indices.size() if not indices.is_empty() else positions.size()) / 3)
		triangle_count += triangles
		var influences: int = int(weights.size() / positions.size()) if not positions.is_empty() else 0
		for vertex_index: int in range(positions.size()):
			var vertex: Vector3 = positions[vertex_index]
			var skin_weights: Dictionary = {}
			for influence: int in range(influences):
				var offset: int = vertex_index * influences + influence
				var weight: float = weights[offset]
				var bind_index: int = skin_indices[offset]
				if weight > 0.0:
					if not _check(bind_index >= 0 and bind_index < bind_names.size(), "GT05_VERTEX_BIND_RANGE"):
						return {}
					skin_weights[bind_names[bind_index]] = float(skin_weights.get(bind_names[bind_index], 0.0)) + weight
			vertices.append({"local": _vec(vertex), "world": _vec(mesh.global_transform * vertex), "weights": skin_weights})
		surfaces.append({"vertices": positions.size(), "triangles": triangles,
			"material": _material(mesh.get_active_material(surface_index))})
	var bounds: AABB = mesh.global_transform * mesh.get_aabb()
	return {"path": String(imported.get_path_to(mesh)), "name": String(mesh.name),
		"transform_world": _transform(mesh.global_transform), "bounds_world_min": _vec(bounds.position),
		"bounds_world_max": _vec(bounds.end), "triangles": triangle_count, "vertices": vertices,
		"surfaces": surfaces, "skin_bind_names": bind_names, "skin_bind_poses": bind_poses,
		"skeleton_path": String(imported.get_path_to(skeleton)) if skeleton != null else ""}


func _skeleton(skeleton: Skeleton3D, pose_only: bool = false) -> Dictionary:
	var bones: Array[Dictionary] = []
	for index: int in range(skeleton.get_bone_count()):
		var parent_index: int = skeleton.get_bone_parent(index)
		var row: Dictionary = {"name": String(skeleton.get_bone_name(index)),
			"pose_local": _transform(skeleton.get_bone_pose(index)),
			"pose_world": _transform(skeleton.global_transform * skeleton.get_bone_global_pose(index))}
		if not pose_only:
			row["parent"] = String(skeleton.get_bone_name(parent_index)) if parent_index >= 0 else ""
			row["rest_local"] = _transform(skeleton.get_bone_rest(index))
			row["rest_world"] = _transform(skeleton.global_transform * skeleton.get_bone_global_rest(index))
		bones.append(row)
	return {"path": String(imported.get_path_to(skeleton)), "bones": bones}


func _inputs_unchanged() -> bool:
	for name_value: String in seed["input_sha256"]:
		if not _check(FileAccess.get_sha256(INPUT + name_value) == seed["input_sha256"][name_value], "GT05_INPUT_HASH_CHANGED"):
			return false
	for name_value: String in seed["authored_sha256"]:
		if not _check(FileAccess.get_sha256("res://" + name_value) == seed["authored_sha256"][name_value], "GT05_AUTHORED_HASH_CHANGED"):
			return false
	return true


func _run() -> void:
	var arguments: PackedStringArray = OS.get_cmdline_user_args()
	if not _check(arguments.size() == 2 and arguments[0] == "--phase" and arguments[1] in ["baseline", "reimport", "visual"], "GT05_FIXED_ARGUMENTS"):
		return
	phase = arguments[1]
	var version: Dictionary = Engine.get_version_info()
	if not _check(version["major"] == 4 and version["minor"] == 7 and version["patch"] == 2 and
			String(version["hash"]).begins_with(VERSION_HASH) and version["status"] == "stable", "GT05_GODOT_PIN"):
		return
	seed = _json(INPUT + "consumer.json")
	if failed or not _check(seed.get("schema") == "HH-GT05-GODOT-CONSUMER-1", "GT05_CONSUMER_SCHEMA"):
		return
	if not _inputs_unchanged():
		return
	var preset: ConfigFile = ConfigFile.new()
	if not _check(preset.load(INPUT + "fixture.glb.import") == OK and
			preset.get_value("params", "nodes/use_name_suffixes", true) == false and
			preset.get_value("params", "nodes/use_node_type_suffixes", true) == false and
			preset.get_value("params", "meshes/generate_lods", true) == false, "GT05_EXPLICIT_IMPORT_PRESET"):
		return
	var packed: PackedScene = load("res://authored.tscn") as PackedScene
	if not _check(packed != null, "GT05_IMPORTED_WRAPPER_MISSING"):
		return
	wrapper = packed.instantiate() as Node3D
	root.add_child(wrapper)
	imported = wrapper.get_node("Imported") as Node3D
	await process_frame
	_collect(imported)
	var actual_mesh_count: int = 0
	for node: Node in native_nodes:
		if node is MeshInstance3D:
			actual_mesh_count += 1
		if not _check(not node is CollisionObject3D and not node is NavigationRegion3D, "GT05_UNDECLARED_IMPORT_ROLE"):
			return
	if not _check(actual_mesh_count == seed["nodes"].size() - seed["rigs"].size(), "GT05_EXTRA_IMPORTED_MESH"):
		return
	var report: Dictionary = {"schema": "HH-GT05-GODOT-OBSERVATION-1", "phase": phase,
		"engine": version, "pid": OS.get_process_id(), "formal_acceptance": false,
		"input_sha256": seed["input_sha256"], "authored_sha256": seed["authored_sha256"],
		"consumer_sha256": FileAccess.get_sha256(INPUT + "consumer.json"),
		"meshes": {}, "rigs": {}, "roles": {}, "clips": {}, "sockets": {}}
	for descriptor: Dictionary in seed["nodes"]:
		if descriptor["role"] == "rig":
			continue
		var mesh: MeshInstance3D = _named(descriptor["name"]) as MeshInstance3D
		if failed or not _check(mesh != null, "GT05_EXPECTED_MESH_CLASS"):
			return
		mesh_nodes[descriptor["name"]] = mesh
		report["meshes"][descriptor["name"]] = _mesh(mesh)
		if failed:
			return
	for descriptor: Dictionary in seed["rigs"]:
		var mesh: MeshInstance3D = mesh_nodes[descriptor["reference_mesh"]] as MeshInstance3D
		var skeleton: Skeleton3D = mesh.get_node_or_null(mesh.skeleton) as Skeleton3D
		if not _check(skeleton != null, "GT05_REFERENCE_RIG_MISSING"):
			return
		rigs[descriptor["asset_id"]] = skeleton
		report["rigs"][descriptor["asset_id"]] = _skeleton(skeleton)
	for descriptor: Dictionary in seed["sockets"]:
		var socket_node: Node3D = _named(descriptor["name"]) as Node3D
		if failed or not _check(socket_node != null, "GT05_SOURCE_SOCKET_MISSING"):
			return
		var skeleton: Skeleton3D = rigs[descriptor["rig_asset_id"]] as Skeleton3D
		var bone_index: int = skeleton.find_bone(descriptor["bone"])
		if not _check(bone_index >= 0, "GT05_SOCKET_BONE_MISSING"):
			return
		var attachment: BoneAttachment3D = wrapper.call("attach_marker", skeleton, descriptor["bone"], descriptor["local_pose"]) as BoneAttachment3D
		var marker: Node3D = attachment.get_node("AuthoredSocketMarker") as Node3D
		source_sockets[descriptor["name"]] = socket_node
		authored_sockets[descriptor["name"]] = marker
		await process_frame
		report["sockets"][descriptor["name"]] = {"source_path": String(imported.get_path_to(socket_node)),
			"source_world": _transform(socket_node.global_transform), "bone": attachment.bone_name,
			"bone_index": attachment.bone_idx, "override_pose": attachment.override_pose,
			"authored_world": _transform(marker.global_transform)}
	for descriptor: Dictionary in seed["nodes"]:
		if descriptor["role"] != "rig":
			var mesh: MeshInstance3D = mesh_nodes[descriptor["name"]] as MeshInstance3D
			report["roles"][descriptor["name"]] = wrapper.call("apply_role", mesh, descriptor["role"], int(descriptor.get("lod", -1)))
	report["lod0"] = wrapper.call("set_lod", 0)
	report["lod1"] = wrapper.call("set_lod", 1)
	wrapper.call("set_lod", 0)
	await physics_frame
	await physics_frame
	for descriptor: Dictionary in seed["nodes"]:
		if descriptor["role"] == "collider":
			var mesh: MeshInstance3D = mesh_nodes[descriptor["name"]] as MeshInstance3D
			var bounds: AABB = mesh.global_transform * mesh.get_aabb()
			var center: Vector3 = bounds.get_center()
			var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(
				center + Vector3.UP * 2.0, center - Vector3.UP * 2.0, 1)
			var hit: Dictionary = wrapper.get_world_3d().direct_space_state.intersect_ray(query)
			if not _check(not hit.is_empty(), "GT05_COLLIDER_RAY_MISS"):
				return
			var collider: CollisionObject3D = hit["collider"] as CollisionObject3D
			report["roles"][descriptor["name"]]["ray"] = {"collider": String(collider.name),
				"position": _vec(hit["position"]), "normal": _vec(hit["normal"])}
		elif descriptor["role"] == "nav":
			await _observe_navigation(mesh_nodes[descriptor["name"]] as MeshInstance3D, report["roles"][descriptor["name"]])
			if failed:
				return
	if not _check(players.size() == 1, "GT05_ONE_ANIMATION_PLAYER"):
		return
	var player: AnimationPlayer = players[0]
	var subresources: Dictionary = preset.get_value("params", "_subresources", {})
	var node_options: Dictionary = subresources.get("nodes", {})
	var animation_options: Dictionary = node_options.get("PATH:AnimationPlayer", {})
	if not _check(String(imported.get_path_to(player)) == "AnimationPlayer" and
			animation_options.get("optimizer/enabled", true) == false and
			animation_options.get("compression/enabled", true) == false, "GT05_ANIMATION_IMPORT_POLICY"):
		return
	report["animation_import"] = {"player_path": String(imported.get_path_to(player)),
		"optimizer_enabled": animation_options["optimizer/enabled"],
		"compression_enabled": animation_options["compression/enabled"]}
	player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	var sample_times: Array[float] = [0.25, 0.75]
	for frame: int in range(31):
		sample_times.append(float(frame) / 30.0)
	sample_times.sort()
	for clip_name: String in ["idle", "walk"]:
		if not _check(player.has_animation(clip_name), "GT05_CLIP_EXACT_NAME"):
			return
		var animation: Animation = player.get_animation(clip_name)
		if not _check(animation.loop_mode == Animation.LOOP_LINEAR, "GT05_EXPLICIT_LOOP_READBACK"):
			return
		var track_types: Array[int] = []
		var tracks: Array[Dictionary] = []
		for track: int in range(animation.get_track_count()):
			var kind: int = animation.track_get_type(track)
			if not _check(kind in [Animation.TYPE_POSITION_3D, Animation.TYPE_ROTATION_3D, Animation.TYPE_SCALE_3D], "GT05_ANIMATION_TRACK_ALLOWLIST"):
				return
			track_types.append(kind)
			var track_path: NodePath = animation.track_get_path(track)
			if not _check(track_path.get_subname_count() == 1, "GT05_BONE_TRACK_PATH"):
				return
			var key_times: Array[float] = []
			for key: int in range(animation.track_get_key_count(track)):
				key_times.append(animation.track_get_key_time(track, key))
			tracks.append({"path": String(track_path), "bone": String(track_path.get_subname(0)),
				"type": kind, "keys": animation.track_get_key_count(track), "times": key_times,
				"compressed": animation.track_is_compressed(track),
				"interpolation": animation.track_get_interpolation_type(track)})
		var samples: Array[Dictionary] = []
		player.play(clip_name)
		for time_value: float in sample_times:
			player.seek(time_value, true, true)
			await process_frame
			var poses: Dictionary = {}
			for rig_name: String in rigs:
				poses[rig_name] = _skeleton(rigs[rig_name] as Skeleton3D, true)
			var sockets: Dictionary = {}
			for socket_name: String in source_sockets:
				var source_socket: Node3D = source_sockets[socket_name] as Node3D
				var authored_socket: Node3D = authored_sockets[socket_name] as Node3D
				sockets[socket_name] = {"source_world": _transform(source_socket.global_transform),
					"authored_world": _transform(authored_socket.global_transform)}
			samples.append({"time": time_value, "rigs": poses, "sockets": sockets})
		report["clips"][clip_name] = {"length": animation.length, "loop_mode": animation.loop_mode,
			"track_types": track_types, "tracks": tracks, "samples": samples}
	player.stop()
	var override_mesh: MeshInstance3D = mesh_nodes[seed["override_mesh"]] as MeshInstance3D
	var override_material: StandardMaterial3D = wrapper.get("authored_material") as StandardMaterial3D
	override_mesh.material_override = override_material
	report["authored"] = _authored_state(override_mesh)
	if phase == "visual":
		await _capture_visuals(player, report)
	if failed or not _inputs_unchanged():
		return
	var output: String = "res://out/" + phase + ".json"
	if not _check(not FileAccess.file_exists(output), "GT05_OUTPUT_ALREADY_EXISTS"):
		return
	var file: FileAccess = FileAccess.open(output, FileAccess.WRITE)
	if not _check(file != null, "GT05_OUTPUT_OPEN"):
		return
	var encoded: String = JSON.stringify(report) + "\n"
	if not _check(encoded.to_utf8_buffer().size() <= MAX_REPORT_BYTES, "GT05_REPORT_BYTE_CAP"):
		file.close()
		return
	file.store_string(encoded)
	file.flush()
	file.close()
	if not _check(FileAccess.get_sha256(output).length() == 64, "GT05_OUTPUT_READBACK"):
		return
	print("GT05_GODOT_OBSERVED " + JSON.stringify({"phase": phase, "pid": OS.get_process_id(),
		"report_sha256": FileAccess.get_sha256(output), "formal_acceptance": false}))
	wrapper.free()
	quit(0)


func _observe_navigation(mesh: MeshInstance3D, role: Dictionary) -> void:
	var regions: Dictionary = wrapper.get("navigation_regions")
	var region: NavigationRegion3D = regions.get(String(mesh.name)) as NavigationRegion3D
	if not _check(region != null and role.get("surface_policy") == "imported_box_top_triangles", "GT05_NAV_TOP_SURFACE"):
		return
	var map_rid: RID = wrapper.get_world_3d().navigation_map
	var region_rid: RID = region.get_rid()
	var bounds: AABB = mesh.global_transform * mesh.get_aabb()
	var floor_y: float = bounds.end.y
	var routes: Dictionary = {
		"diagonal_a": [Vector3(bounds.position.x + 0.5, floor_y, bounds.position.z + 0.5),
			Vector3(bounds.end.x - 0.5, floor_y, bounds.end.z - 0.5)],
		"diagonal_b": [Vector3(bounds.position.x + 0.5, floor_y, bounds.end.z - 0.5),
			Vector3(bounds.end.x - 0.5, floor_y, bounds.position.z + 0.5)]}
	var started_ms: int = Time.get_ticks_msec()
	var waited: int = 0
	var sync_observations: Array[Dictionary] = []
	# Never force a map update or await an unbounded navigation signal. The
	# native owner also imposes the outer process deadline if frames stop.
	# Region and map iterations build asynchronously and independently. A
	# nonzero region iteration can coexist with an older empty map snapshot.
	# Confirm this region is visible to queries at all four route endpoints.
	while true:
		var map_iteration: int = NavigationServer3D.map_get_iteration_id(map_rid)
		var region_iteration: int = NavigationServer3D.region_get_iteration_id(region_rid)
		var endpoint_owners: Array[int] = []
		var visible_in_snapshot: bool = map_iteration > int(role["map_iteration_before"]) and region_iteration > 0
		for label: String in routes:
			for endpoint: Vector3 in routes[label]:
				var endpoint_owner: RID = NavigationServer3D.map_get_closest_point_owner(map_rid, endpoint) if map_iteration > 0 else RID()
				endpoint_owners.append(endpoint_owner.get_id())
				visible_in_snapshot = visible_in_snapshot and endpoint_owner == region_rid
		sync_observations.append({"map_iteration": map_iteration, "region_iteration": region_iteration,
			"physics_frame": Engine.get_physics_frames(), "endpoint_owner_region_ids": endpoint_owners})
		if visible_in_snapshot:
			break
		if not _check(waited < 120 and Time.get_ticks_msec() - started_ms < 2000, "GT05_NAV_SYNC_TIMEOUT"):
			return
		await physics_frame
		await process_frame
		waited += 1
	if not _check(Time.get_ticks_msec() - started_ms <= 2000, "GT05_NAV_SYNC_TIMEOUT"):
		return
	var iteration: int = NavigationServer3D.map_get_iteration_id(map_rid)
	if not _check(NavigationServer3D.map_is_active(map_rid) and
			NavigationServer3D.region_get_map(region_rid) == map_rid and
			NavigationServer3D.map_get_regions(map_rid).has(region_rid) and
			NavigationServer3D.region_get_enabled(region_rid) and
			NavigationServer3D.region_get_navigation_layers(region_rid) == 1, "GT05_NAV_MAP_BINDING"):
		return
	var queries: Dictionary = {}
	for label: String in routes:
		var start: Vector3 = routes[label][0]
		var destination: Vector3 = routes[label][1]
		var path: PackedVector3Array = NavigationServer3D.map_get_path(map_rid, start, destination, true, 1)
		if not _check(path.size() >= 2 and path.size() <= 32 and
				path[0].distance_to(start) <= 0.001 and path[path.size() - 1].distance_to(destination) <= 0.001,
				"GT05_NAV_PATH_UNREACHABLE"):
			return
		var points: Array[Array] = []
		var closest: Array[Array] = []
		var normals: Array[Array] = []
		var owners: Array[int] = []
		var length: float = 0.0
		for index: int in range(path.size()):
			var point: Vector3 = path[index]
			var nearest: Vector3 = NavigationServer3D.map_get_closest_point(map_rid, point)
			var normal: Vector3 = NavigationServer3D.map_get_closest_point_normal(map_rid, point)
			var owner: RID = NavigationServer3D.map_get_closest_point_owner(map_rid, point)
			if not _check(absf(point.y - floor_y) <= 0.001 and
					point.x >= bounds.position.x - 0.001 and point.x <= bounds.end.x + 0.001 and
					point.z >= bounds.position.z - 0.001 and point.z <= bounds.end.z + 0.001 and
					point.distance_to(nearest) <= 0.001 and normal.distance_to(Vector3.UP) <= 0.0001 and
					owner == region_rid, "GT05_NAV_PATH_OFF_SURFACE"):
				return
			points.append(_vec(point))
			closest.append(_vec(nearest))
			normals.append(_vec(normal))
			owners.append(owner.get_id())
			if index > 0:
				length += path[index - 1].distance_to(point)
		queries[label] = {"requested_start": _vec(start), "requested_end": _vec(destination),
			"points": points, "surface_points": closest, "surface_normals": normals,
			"owner_region_ids": owners, "path_length": length}
	var after: int = NavigationServer3D.map_get_iteration_id(map_rid)
	if not _check(after == iteration, "GT05_NAV_CHANGED_DURING_QUERY"):
		return
	role["path_query"] = {"pid": OS.get_process_id(), "source_sha256": seed["input_sha256"]["fixture.glb"],
		"consumer_sha256": FileAccess.get_sha256(INPUT + "consumer.json"),
		"map_id": map_rid.get_id(), "region_id": region_rid.get_id(), "region_name": String(region.name),
		"map_active": NavigationServer3D.map_is_active(map_rid),
		"region_enabled": NavigationServer3D.region_get_enabled(region_rid),
		"navigation_layers": NavigationServer3D.region_get_navigation_layers(region_rid),
		"map_iteration": iteration, "map_iteration_after": after,
		"region_iteration": NavigationServer3D.region_get_iteration_id(region_rid),
		"sync_wait_frames": waited, "sync_elapsed_ms": Time.get_ticks_msec() - started_ms,
		"physics_frame": Engine.get_physics_frames(), "sync_observations": sync_observations,
		"optimize": true, "queries": queries}


func _authored_state(mesh: MeshInstance3D) -> Dictionary:
	return {"marker": wrapper.get("authored_marker"), "script": wrapper.get_script().resource_path,
		"override_mesh": String(mesh.name), "material": _material(mesh.material_override)}


func _capture_visuals(player: AnimationPlayer, report: Dictionary) -> void:
	if not _check(DisplayServer.get_name() != "headless", "GT05_VISUAL_REQUIRES_RENDERING"):
		return
	var prop: MeshInstance3D = mesh_nodes[seed["override_mesh"]] as MeshInstance3D
	var authored_override: Material = prop.material_override
	prop.material_override = null
	var original_material: Dictionary = _material(prop.get_active_material(0))
	if failed or not _check(original_material["name"] == "mat_fixture_crate" and
			not original_material["textures"].is_empty(), "GT05_CAPTURE_ORIGINAL_PBR"):
		prop.material_override = authored_override
		return
	report["visual_material"] = {"mesh": String(prop.name), "original_material": original_material,
		"override_disabled": prop.material_override == null}
	var camera: Camera3D = Camera3D.new()
	root.add_child(camera)
	camera.current = true
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 6.0
	camera.near = 0.05
	camera.far = 100.0
	var light: DirectionalLight3D = DirectionalLight3D.new()
	root.add_child(light)
	light.rotation_degrees = Vector3(-45.0, -35.0, 0.0)
	light.light_color = Color.WHITE
	light.light_energy = 0.65
	light.shadow_enabled = false
	var fill: DirectionalLight3D = DirectionalLight3D.new()
	camera.add_child(fill)
	fill.light_color = Color.WHITE
	fill.light_energy = 0.35
	fill.shadow_enabled = false
	var environment_node: WorldEnvironment = WorldEnvironment.new()
	var environment: Environment = Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color(0.055, 0.065, 0.08)
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color(0.8, 0.8, 0.8)
	environment.ambient_light_energy = 0.2
	environment.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	environment.tonemap_exposure = 1.0
	environment_node.environment = environment
	root.add_child(environment_node)
	report["visual_lighting"] = {"key_energy": light.light_energy, "fill_energy": fill.light_energy,
		"ambient_energy": environment.ambient_light_energy, "key_transform": _transform(light.global_transform),
		"key_color": [light.light_color.r, light.light_color.g, light.light_color.b],
		"fill_color": [fill.light_color.r, fill.light_color.g, fill.light_color.b],
		"ambient_color": [environment.ambient_light_color.r, environment.ambient_light_color.g, environment.ambient_light_color.b],
		"background_color": [environment.background_color.r, environment.background_color.g, environment.background_color.b],
		"tonemap_mode": environment.tonemap_mode, "exposure": environment.tonemap_exposure,
		"fill_transform_local": _transform(fill.transform),
		"fill_is_camera_child": fill.get_parent() == camera, "shadows_enabled": light.shadow_enabled or fill.shadow_enabled}
	var views: Dictionary = {"front": Vector3(0, 2, 8), "back": Vector3(0, 2, -8),
		"left": Vector3(-8, 2, 0), "right": Vector3(8, 2, 0),
		"top": Vector3(0, 9, 0), "bottom": Vector3(0, -7, 0)}
	var captures: Dictionary = {}
	player.play("idle")
	player.seek(0.0, true, true)
	# Render statistics become available only after at least two rendered frames.
	for warmup: int in range(2):
		await process_frame
		await RenderingServer.frame_post_draw
	for label: String in views:
		camera.position = views[label]
		camera.look_at(Vector3(0, 1, 0), Vector3.FORWARD if label in ["top", "bottom"] else Vector3.UP)
		await _save_frame(label, captures, camera, player, prop, 0, Vector3(0, 1, 0))
		if failed:
			break
	camera.position = views["front"]
	camera.look_at(Vector3(0, 1, 0))
	for clip_name: String in ["idle", "walk"]:
		if failed:
			break
		player.play(clip_name)
		for frame: int in range(31):
			player.seek(float(frame) / 30.0, true, true)
			await _save_frame("%s_%02d" % [clip_name, frame], captures, camera, player, prop, frame, Vector3(0, 1, 0))
			if failed:
				break
	player.stop()
	prop.material_override = authored_override
	report["authored_after_capture"] = _authored_state(prop)
	_check(prop.material_override == authored_override and report["authored_after_capture"] == report["authored"],
		"GT05_CAPTURE_RESTORE_AUTHORED")
	_check(captures.size() == 68, "GT05_CAPTURE_EXACT_FRAME_SET")
	report["captures"] = captures
	camera.free()
	light.free()
	environment_node.free()


func _save_frame(label: String, captures: Dictionary, camera: Camera3D, player: AnimationPlayer,
		prop: MeshInstance3D, sample_frame: int, target: Vector3) -> void:
	await process_frame
	await RenderingServer.frame_post_draw
	var visible_calls: int = RenderingServer.viewport_get_render_info(root.get_viewport_rid(),
		RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE, RenderingServer.VIEWPORT_RENDER_INFO_DRAW_CALLS_IN_FRAME)
	var shadow_calls: int = RenderingServer.viewport_get_render_info(root.get_viewport_rid(),
		RenderingServer.VIEWPORT_RENDER_INFO_TYPE_SHADOW, RenderingServer.VIEWPORT_RENDER_INFO_DRAW_CALLS_IN_FRAME)
	if not _check(visible_calls > 0 and shadow_calls >= 0 and visible_calls + shadow_calls <= 150,
			"GT05_CAPTURE_DRAW_CALL_BUDGET"):
		return
	if not _check(prop.material_override == null and prop.is_visible_in_tree() and
			prop.get_active_material(0) == prop.mesh.surface_get_material(0) and
			String(prop.get_active_material(0).resource_name) == "mat_fixture_crate",
			"GT05_CAPTURE_PBR_OVERRIDE"):
		return
	var image: Image = root.get_texture().get_image()
	var path: String = "res://out/" + label + ".png"
	if not _check(not image.is_empty() and image.get_width() == 640 and image.get_height() == 640 and
			not FileAccess.file_exists(path), "GT05_CAPTURE_INPUT"):
		return
	if not _check(image.save_png(path) == OK, "GT05_CAPTURE_SAVE"):
		return
	captures[label] = {"sha256": FileAccess.get_sha256(path), "width": image.get_width(),
		"height": image.get_height(), "pid": OS.get_process_id(), "frame": Engine.get_process_frames(),
		"rendered_frame": Engine.get_frames_drawn(), "captured_at_unix": Time.get_unix_time_from_system(),
		"monotonic_us": Time.get_ticks_usec(), "source_sha256": seed["input_sha256"]["fixture.glb"],
		"producer_report_sha256": seed["input_sha256"]["producer-report.json"],
		"consumer_sha256": FileAccess.get_sha256(INPUT + "consumer.json"),
		"clip": String(player.current_animation), "requested_time": float(sample_frame) / 30.0,
		"clip_time": player.current_animation_position, "sample_frame": sample_frame,
		"camera": {"transform": _transform(camera.global_transform), "projection": camera.projection,
			"size": camera.size, "near": camera.near, "far": camera.far, "target": _vec(target)},
		"draw_calls": {"visible": visible_calls, "shadow": shadow_calls, "total": visible_calls + shadow_calls},
		"material_name": String(prop.get_active_material(0).resource_name),
		"override_is_null": prop.material_override == null, "prop_visible": prop.is_visible_in_tree()}

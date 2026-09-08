extends SceneTree

var _aabb := AABB()
var _first := true
var _mesh_count := 0


func _init() -> void:
	var packed: PackedScene = load("res://assets/environment/gaming_room.glb") as PackedScene
	if packed == null:
		print("BOUNDS_FAIL missing glb")
		quit(1)
		return
	var root: Node = packed.instantiate()
	_walk(root, Transform3D.IDENTITY)
	print("MESH_COUNT=", _mesh_count)
	print("AABB_MIN=", _aabb.position)
	print("AABB_MAX=", _aabb.end)
	print("AABB_SIZE=", aabb_size())
	root.free()
	quit(0)


func aabb_size() -> Vector3:
	return _aabb.size


func _walk(n: Node, xf: Transform3D) -> void:
	var next_xf := xf
	var n3 := n as Node3D
	if n3:
		next_xf = xf * n3.transform
	var mi := n as MeshInstance3D
	if mi and mi.mesh:
		_mesh_count += 1
		var local := mi.mesh.get_aabb()
		var corners: Array[Vector3] = [
			next_xf * local.position,
			next_xf * (local.position + Vector3(local.size.x, 0.0, 0.0)),
			next_xf * (local.position + Vector3(0.0, local.size.y, 0.0)),
			next_xf * (local.position + Vector3(0.0, 0.0, local.size.z)),
			next_xf * (local.position + Vector3(local.size.x, local.size.y, 0.0)),
			next_xf * (local.position + Vector3(local.size.x, 0.0, local.size.z)),
			next_xf * (local.position + Vector3(0.0, local.size.y, local.size.z)),
			next_xf * (local.position + local.size),
		]
		for p in corners:
			if _first:
				_aabb = AABB(p, Vector3.ZERO)
				_first = false
			else:
				_aabb = _aabb.expand(p)
	for c in n.get_children():
		_walk(c, next_xf)

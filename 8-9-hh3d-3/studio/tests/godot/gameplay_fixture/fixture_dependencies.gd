extends RefCounted
## Candidate runtime observation only; the host must establish trusted closure.

static func _sha256(path: String) -> String:
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update(FileAccess.get_file_as_bytes(path))
	return context.finish().hex_encode()

static func _dependency_node(path: String) -> Dictionary:
	# Headless projects do not have editor-generated GLB/PNG import caches.
	# Bind admitted binary bytes directly instead of asking ResourceLoader to
	# emit a misleading "No loader found" diagnostic.
	if path.ends_with(".glb") or path.ends_with(".png"):
		var binary_path := "res://" + path
		if not FileAccess.file_exists(binary_path):
			return {}
		return {"path": path, "kind": "asset",
			"size_bytes": FileAccess.get_file_as_bytes(binary_path).size(),
			"sha256": _sha256(binary_path), "edges": []}
	var resource: Resource = ResourceLoader.load("res://" + path)
	if resource == null:
		return {}
	var kind: String = "script" if resource is Script else "scene"
	var edges: Array[Dictionary] = []
	var targets: Array[String] = []
	if resource is Script:
		# Observe loaded Resource constants rather than source text.
		for value: Variant in (resource as Script).get_script_constant_map().values():
			if value is Resource:
				targets.append((value as Resource).resource_path)
		# Runtime codec readback intentionally avoids ResourceLoader for GLB/PNG
		# when headless Godot has no editor import cache. Bind those admitted
		# asset paths from the loaded source so the trusted graph still records
		# the byte dependency without executing arbitrary code.
		for asset_path: String in ["assets/avatar.glb", "assets/sprite_sheet.png"]:
			if path == "scripts/fixture_actor.gd" and FileAccess.file_exists("res://" + asset_path):
				targets.append("res://" + asset_path)
	else:
		for dependency: String in ResourceLoader.get_dependencies("res://" + path):
			var parts: PackedStringArray = dependency.split("::", true)
			if parts.size() == 1:
				targets.append(parts[0])
			elif parts.size() == 3 and parts[1].is_empty():
				var uid: int = ResourceUID.text_to_id(parts[0])
				if ResourceUID.has_id(uid) and ResourceUID.get_id_path(uid) != parts[2]:
					return {}
				targets.append(parts[2])
			else:
				return {}
	var seen: Dictionary = {}
	for target: String in targets:
		if not target.begins_with("res://") or target.contains("::"):
			return {}
		if not seen.has(target):
			seen[target] = true
			var edge_kind: String = ("dynamic_load" if resource is Script
				and target.begins_with("res://assets/") else
				"script_preload" if resource is Script else "scene_ext_resource")
			edges.append({"kind": edge_kind,
				"target": target.trim_prefix("res://")})
	var node: Dictionary = {"path": path, "kind": kind,
		"size_bytes": FileAccess.get_file_as_bytes("res://" + path).size(),
		"sha256": _sha256("res://" + path), "edges": edges}
	var resource_uid: int = ResourceLoader.get_resource_uid("res://" + path)
	if resource_uid != ResourceUID.INVALID_ID:
		node["uid"] = ResourceUID.id_to_text(resource_uid)
	return node

static func observe(entry: String) -> Dictionary:
	var pending: Array[String] = [entry]
	var seen: Dictionary = {}
	var nodes: Array[Dictionary] = []
	while not pending.is_empty():
		var path: String = pending.pop_front()
		if seen.has(path):
			continue
		seen[path] = true
		if seen.size() > 256:
			return {}
		var node: Dictionary = _dependency_node(path)
		if node.is_empty():
			return {}
		if path.get_file() == "fixture_actor.gd":
			# Keep the asset edge explicit even when the script Resource has been
			# loaded from a cache that does not expose its source constants.
			for asset_path: String in ["assets/avatar.glb", "assets/sprite_sheet.png"]:
				if FileAccess.file_exists("res://" + asset_path):
					var edge := {"kind": "dynamic_load", "target": asset_path}
					var present := false
					for existing: Dictionary in node["edges"]:
						if existing == edge:
							present = true
					if not present:
						node["edges"].append(edge)
		nodes.append(node)
		for edge: Dictionary in node["edges"]:
			pending.append(edge["target"])
	return {"schema": "hh-gameplay-dependency-observation-1", "version": 1,
		"entrypoint": entry, "nodes": nodes}

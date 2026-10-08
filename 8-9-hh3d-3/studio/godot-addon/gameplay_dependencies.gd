extends SceneTree
## Trusted loader observation. Never load/instantiate candidate Resources.
## Only loader-reported static edges are covered; computed paths are not inferred.

var files: Array[String] = []
var failed: bool = false

func reject(reason: String) -> void:
	if not failed:
		printerr("HH_DEPENDENCY_REJECT " + reason)
	failed = true

func collect(root: String) -> void:
	var directory: DirAccess = DirAccess.open("res://" + root)
	if directory == null:
		return
	for name: String in directory.get_files():
		if name.ends_with(".gd") or name.ends_with(".tscn") or name.ends_with(".glb") or name.ends_with(".png"):
			files.append(root + "/" + name)
			if files.size() > 64:
				reject("FILE_CAP")
				return
	for name: String in directory.get_directories():
		if root.count("/") >= 16:
			reject("PATH_DEPTH")
			return
		collect(root + "/" + name)

func target_path(reference: String) -> String:
	var parts: PackedStringArray = reference.split("::", true)
	var target: String = parts[0]
	if parts.size() == 3 and parts[0].begins_with("uid://"):
		target = parts[2]
		var uid: int = ResourceUID.text_to_id(parts[0])
		if uid == ResourceUID.INVALID_ID:
			reject("UID_INVALID")
		elif ResourceUID.has_id(uid) and ResourceUID.get_id_path(uid) != target:
			reject("UID_PATH_MISMATCH")
	elif parts.size() == 2:
		target = parts[0]
	elif parts.size() != 1:
		reject("REFERENCE_SHAPE")
	if target.begins_with("uid://"):
		var uid: int = ResourceUID.text_to_id(target)
		if uid == ResourceUID.INVALID_ID or not ResourceUID.has_id(uid):
			reject("UID_UNRESOLVED")
			return ""
		target = ResourceUID.get_id_path(uid)
	if not target.begins_with("res://"):
		reject("OUTSIDE_ROOT")
		return ""
	target = target.trim_prefix("res://")
	if not files.has(target):
		reject("MISSING_OR_ALIASED_TARGET")
		return ""
	return target

func _initialize() -> void:
	for root: String in ["scripts", "scenes", "assets"]:
		collect(root)
	files.sort()
	var nodes: Array[Dictionary] = []
	for path: String in files:
		var raw: PackedByteArray = FileAccess.get_file_as_bytes("res://" + path)
		var hasher: HashingContext = HashingContext.new()
		hasher.start(HashingContext.HASH_SHA256)
		hasher.update(raw)
		var kind: String = "script" if path.ends_with(".gd") else ("scene" if path.ends_with(".tscn") else "asset")
		var edges: Array[Dictionary] = []
		var node: Dictionary = {"path": path, "kind": kind, "size_bytes": raw.size(), "sha256": hasher.finish().hex_encode(), "edges": edges}
		if kind != "asset":
			var uid: int = ResourceLoader.get_resource_uid("res://" + path)
			if uid != ResourceUID.INVALID_ID:
				node["uid"] = ResourceUID.id_to_text(uid)
			var targets: Array[String] = []
			var preload_targets: Array[String] = []
			var dynamic_targets: Array[String] = []
			for reference: String in ResourceLoader.get_dependencies("res://" + path):
				var target: String = target_path(reference)
				if not target.is_empty() and not targets.has(target):
					targets.append(target)
			# The pinned 4.7.2 GDScript loader does not expose script preload
			# dependencies through ResourceLoader.get_dependencies(). Loading a
			# candidate Script here is forbidden: it executes static initializers.
			# Instead, inspect immutable source bytes with a deliberately narrow,
			# fail-closed literal scanner. This never compiles, loads or instantiates
			# candidate code. Computed paths, malformed literals and non-literal
			# resource expressions remain outside this observation's scope.
			if kind == "script":
				var source: String = FileAccess.get_file_as_string("res://" + path)
				var preload_re: RegEx = RegEx.new()
				var load_re: RegEx = RegEx.new()
				if preload_re.compile("preload\\s*\\(\\s*[\\\"'](res://[^\\\"'\\n]+)[\\\"']\\s*\\)") != OK:
					reject("SCANNER_INIT")
				if load_re.compile("(?<!pre)load\\s*\\(\\s*[\\\"'](res://[^\\\"'\\n]+)[\\\"']\\s*\\)") != OK:
					reject("SCANNER_INIT")
				for match: RegExMatch in preload_re.search_all(source):
					var preload_target: String = target_path(match.get_string(1))
					if not preload_target.is_empty():
						if not targets.has(preload_target):
							targets.append(preload_target)
						if not preload_targets.has(preload_target):
							preload_targets.append(preload_target)
				for match: RegExMatch in load_re.search_all(source):
					var dynamic_target: String = target_path(match.get_string(1))
					if not dynamic_target.is_empty():
						if not targets.has(dynamic_target):
							targets.append(dynamic_target)
						if not dynamic_targets.has(dynamic_target):
							dynamic_targets.append(dynamic_target)
			targets.sort()
			for target: String in targets:
				var edge_kind: String = "loader_reference"
				if kind == "script":
					if preload_targets.has(target):
						edge_kind = "script_preload"
					elif dynamic_targets.has(target):
						edge_kind = "dynamic_load"
				edges.append({"kind": edge_kind, "target": target})
		nodes.append(node)
	if failed or not files.has("scenes/fixture.tscn"):
		quit(46)
		return
	print("HH_LOADER_DEPENDENCIES " + JSON.stringify({"schema": "hh-gameplay-dependency-observation-1", "version": 1, "entrypoint": "scenes/fixture.tscn", "nodes": nodes}))
	quit(0)

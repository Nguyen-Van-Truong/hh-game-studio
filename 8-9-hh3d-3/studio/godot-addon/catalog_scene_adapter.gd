@tool
extends RefCounted
## Native executor for a host-admitted catalog transaction.
##
## The adapter never accepts method names, scene paths, or classes outside the
## frozen input.  Every class/property is checked against both the admitted
## catalog and ClassDB before the detached scene is attached through one editor
## UndoRedo action.  Observations contain native readback, not caller-provided
## expected snapshots.

const JCS = preload("res://addons/hh_catalog/jcs_godot.gd")
const INPUT_SCHEMA := "hh-catalog-native-input-1"
const OBSERVATION_SCHEMA := "hh-catalog-native-observation-1"
const ID_META := "hh_catalog_stable_id"
const RESOURCE_META := "hh_catalog_resource_id"
const ACTION_NAME := "HH catalog transaction"
const SCENE_PATH := "res://scenes/authored.tscn"
const EPSILON := 0.000001

var _bench: Node
var _authored: Node
var _catalog: Dictionary = {}
var _nodes: Dictionary = {}
var _node_rows: Dictionary = {}
var _node_order: Array[String] = []
var _resources: Dictionary = {}
var _resource_rows: Dictionary = {}
var _resource_order: Array[String] = []
var _assets: Dictionary = {}
var _asset_paths: Dictionary = {}
var _asset_order: Array[String] = []
var _commands: Array[Dictionary] = []
var _failures: Array[String] = []
var _checks: Dictionary = {"undo": false, "redo": false, "save": false, "reload": false}


func run(bench: Node, undo: EditorUndoRedoManager, data: Dictionary) -> Dictionary:
	_bench = bench
	if not _guard(Engine.is_editor_hint() and _on_main() and is_instance_valid(bench), "CATALOG_EDITOR_CONTEXT"):
		return _result(data, {}, "")
	if not _guard(_validate_input(data), "CATALOG_INPUT"):
		return _result(data, {}, "")
	if not _guard(bench.get_child_count() == 0, "CATALOG_WORKBENCH_NOT_EMPTY"):
		return _result(data, {}, "")
	if not _guard(_load_assets(data.assets), "CATALOG_ASSET_SETUP"):
		return _result(data, {}, "")
	if not _guard(_build_root(data.root_spec), "CATALOG_ROOT_SETUP"):
		return _result(data, {}, "")
	var baseline: Dictionary = JCS.new().canonicalize(_snapshot(_authored))
	if not _guard(baseline.get("ok", false) and baseline.sha256 == data.transaction.expected_revision,
			"CATALOG_BASELINE_REVISION"):
		_dispose_authored()
		return _result(data, {}, "")
	if not _guard(_apply_commands(data.transaction.commands), "CATALOG_COMMAND_APPLY"):
		_dispose_authored()
		return _result(data, {}, "")

	var expected_state: Dictionary = _snapshot(_authored)
	if not _guard(not expected_state.has("invalid"), "CATALOG_APPLY_READBACK"):
		_dispose_authored()
		return _result(data, {}, "")
	var history_id: int = undo.get_object_history_id(bench)
	var history: UndoRedo = undo.get_history_undo_redo(history_id)
	if not _guard(history != null and not history.has_undo() and not history.has_redo(), "CATALOG_HISTORY_DIRTY"):
		_dispose_authored()
		return _result(data, {}, "")

	undo.create_action(ACTION_NAME, UndoRedo.MERGE_DISABLE, bench)
	undo.add_do_method(self, &"_attach")
	undo.add_undo_method(self, &"_detach")
	undo.add_do_reference(_authored)
	undo.commit_action()
	var after_apply: Dictionary = _snapshot(_authored)
	if not _guard(_authored.get_parent() == bench and _same(after_apply, expected_state), "CATALOG_APPLY_TRANSITION"):
		_cleanup_history(history)
		_dispose_authored()
		return _result(data, {"after_apply": after_apply}, "")

	_checks.undo = history.undo() and _authored.get_parent() == null and bench.get_child_count() == 0
	_checks.redo = history.redo() and _authored.get_parent() == bench and _same(_snapshot(_authored), expected_state)
	if not _guard(_checks.undo, "CATALOG_UNDO") or not _guard(_checks.redo, "CATALOG_REDO"):
		_cleanup_history(history)
		_dispose_authored()
		return _result(data, {"after_apply": after_apply}, "")

	var packed := PackedScene.new()
	var packed_ok: bool = packed.pack(_authored) == OK
	_checks.save = packed_ok and not FileAccess.file_exists(SCENE_PATH) and ResourceSaver.save(packed, SCENE_PATH) == OK
	if not _guard(_checks.save, "CATALOG_SAVE"):
		_cleanup_history(history)
		_dispose_authored()
		return _result(data, {"after_apply": after_apply}, "")

	var loaded_scene := ResourceLoader.load(SCENE_PATH, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
	var loaded: Node = loaded_scene.instantiate() if loaded_scene != null else null
	var after_reload: Dictionary = _snapshot(loaded) if loaded != null else {"invalid": "load"}
	_checks.reload = loaded != null and _same(after_reload, expected_state)
	_guard(_checks.reload, "CATALOG_RELOAD")
	if loaded != null:
		loaded.free()
	_cleanup_history(history)
	var scene_hash: String = FileAccess.get_sha256(SCENE_PATH) if FileAccess.file_exists(SCENE_PATH) else ""
	var result: Dictionary = _result(data,
		{"after_apply": after_apply, "after_reload": after_reload}, scene_hash)
	_dispose_authored()
	return result


func _validate_input(data: Dictionary) -> bool:
	if data.get("schema") != INPUT_SCHEMA or not data.get("transaction") is Dictionary \
			or not data.get("admission") is Dictionary or not data.get("root_spec") is Dictionary \
			or not data.get("catalog") is Dictionary or not data.get("assets") is Dictionary:
		return false
	var transaction: Dictionary = data.transaction
	var admission: Dictionary = data.admission
	if transaction.get("schema") != "hh-godot-authoring-transaction-1" \
			or transaction.get("authority") != 0 or transaction.get("public_ack") != false \
			or transaction.get("profile") != "hh-godot-gameplay-source-1" \
			or not transaction.get("commands") is Array or not transaction.get("command_ids") is Array \
			or transaction.commands.is_empty() or transaction.commands.size() > 128 \
			or transaction.commands.size() != transaction.command_ids.size():
		return false
	for key: String in ["project_id", "project_revision", "generation", "lease_id", "fencing_epoch"]:
		if transaction.get(key) != admission.get(key):
			return false
	if admission.get("now_ms", 0) >= admission.get("lease_expires_ms", 0) \
			or Time.get_unix_time_from_system() * 1000 >= admission.get("lease_expires_ms", 0) \
			or transaction.get("expected_revision") != admission.get("revision"):
		return false
	var body: Dictionary = transaction.duplicate(true)
	body.erase("transaction_digest")
	var canonical: Dictionary = JCS.new().canonicalize(body)
	if not canonical.get("ok", false) or canonical.sha256 != transaction.get("transaction_digest"):
		return false
	var seen: Dictionary = {}
	for index: int in transaction.commands.size():
		var command: Variant = transaction.commands[index]
		if not command is Dictionary or command.get("command_id") != transaction.command_ids[index] \
				or seen.has(command.get("command_id")) or not command.get("projection") is Dictionary:
			return false
		seen[command.command_id] = true
		var projection: Dictionary = command.projection
		var encoded: Dictionary = JCS.new().canonicalize(projection)
		if not encoded.get("ok", false) or encoded.sha256 != command.get("projection_sha256") \
				or projection.get("command_id") != command.get("command_id") \
				or projection.get("operation") != command.get("operation") \
				or projection.get("target_stable_id") != command.get("target_stable_id") \
				or projection.get("expected_generation") != transaction.get("generation"):
			return false
	_catalog = data.catalog
	return true


func _load_assets(specs: Dictionary) -> bool:
	for resource_id: Variant in specs:
		if typeof(resource_id) != TYPE_STRING or not _identifier(resource_id):
			return _guard(false, "CATALOG_ASSET_ID")
		var spec: Variant = specs[resource_id]
		if not spec is Dictionary or typeof(spec.get("path")) != TYPE_STRING \
				or typeof(spec.get("sha256")) != TYPE_STRING:
			return _guard(false, "CATALOG_ASSET_SPEC")
		var relative: String = spec.path
		if relative.is_absolute_path() or "\\" in relative or relative.begins_with("/") \
				or ".." in relative.split("/") or not relative.begins_with("assets/"):
			return _guard(false, "CATALOG_ASSET_PATH")
		var path := "res://" + relative
		if not FileAccess.file_exists(path) or FileAccess.get_sha256(path) != spec.sha256:
			return _guard(false, "CATALOG_ASSET_HASH")
		var packed := ResourceLoader.load(path, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
		var instance: Node = packed.instantiate() if packed != null else null
		var mesh: Mesh = _first_mesh(instance) if instance != null else null
		if mesh == null:
			if instance != null:
				instance.free()
			return _guard(false, "CATALOG_ASSET_IMPORT")
		# Give the imported subresource a stable native identity before any
		# node references it; PackedScene carries resource_name/meta through save
		# and reload, allowing the post-reload readback to resolve the same ID.
		mesh.resource_name = str(resource_id)
		mesh.set_meta(RESOURCE_META, str(resource_id))
		_assets[str(resource_id)] = mesh
		_asset_paths[str(resource_id)] = path
		_asset_order.append(str(resource_id))
		instance.free()
	return true


func _first_mesh(root: Node) -> Mesh:
	var pending: Array[Node] = [root]
	while not pending.is_empty():
		var node: Node = pending.pop_back()
		if node is MeshInstance3D and (node as MeshInstance3D).mesh != null:
			return (node as MeshInstance3D).mesh
		for child: Node in node.get_children():
			pending.append(child)
	return null


func _build_root(spec: Dictionary) -> bool:
	if spec.get("stable_id") != "root" or typeof(spec.get("node_type")) != TYPE_STRING \
			or typeof(spec.get("name")) != TYPE_STRING or not spec.get("properties") is Dictionary:
		return _guard(false, "CATALOG_ROOT_SPEC")
	var root: Node = _instantiate_node(str(spec.node_type), str(spec.name), spec.properties)
	if root == null:
		return false
	root.set_meta(ID_META, "root")
	root.set_meta("hh_saved_id", "root")
	_authored = root
	_nodes.root = root
	_node_order.append("root")
	_node_rows.root = {"stable_id": "root", "parent_id": null, "node_type": str(spec.node_type),
		"name": str(spec.name), "properties": spec.properties.duplicate(true)}
	return true


func _apply_commands(commands: Array) -> bool:
	for raw: Variant in commands:
		var command: Dictionary = raw
		var projection: Dictionary = command.projection
		var operation: String = str(command.operation)
		var target_id: String = str(command.target_stable_id)
		var payload: Dictionary = projection.payload
		var ok := false
		var readback: Dictionary = {}
		if operation == "scene.node.create":
			ok = _create_node(target_id, payload)
			if ok:
				readback = _node_readback(str(payload.stable_id))
		elif operation == "scene.node.update":
			ok = _update_node(target_id, payload)
			if ok:
				readback = _node_readback(target_id)
		elif operation == "scene.resource.create":
			ok = _create_resource(target_id, payload)
			if ok:
				readback = _resource_readback(str(payload.resource_id))
		else:
			return _guard(false, "CATALOG_OPERATION_UNSUPPORTED")
		if not ok:
			return false
		_commands.append({"command_id": command.command_id, "operation": operation,
			"target_stable_id": target_id, "projection_sha256": command.projection_sha256,
			"verified": true, "readback": readback})
	return true


func _create_node(parent_id: String, payload: Dictionary) -> bool:
	var stable_id: String = str(payload.get("stable_id", ""))
	if not _nodes.has(parent_id) or _nodes.has(stable_id) or not _identifier(stable_id) \
			or typeof(payload.get("node_type")) != TYPE_STRING or typeof(payload.get("name")) != TYPE_STRING \
			or not payload.get("properties") is Dictionary:
		return _guard(false, "CATALOG_NODE_CREATE")
	var node: Node = _instantiate_node(str(payload.node_type), str(payload.name), payload.properties)
	if node == null:
		return false
	var parent: Node = _nodes[parent_id]
	parent.add_child(node)
	node.owner = _authored
	node.set_meta(ID_META, stable_id)
	node.set_meta("hh_saved_id", stable_id)
	_nodes[stable_id] = node
	_node_order.append(stable_id)
	_node_rows[stable_id] = {"stable_id": stable_id, "parent_id": parent_id,
		"node_type": str(payload.node_type), "name": str(payload.name),
		"properties": payload.properties.duplicate(true)}
	return _guard(_same(_node_readback(stable_id), _node_rows[stable_id]), "CATALOG_NODE_CREATE_READBACK")


func _update_node(stable_id: String, payload: Dictionary) -> bool:
	if not _nodes.has(stable_id) or not payload.get("changes") is Dictionary or payload.changes.is_empty():
		return _guard(false, "CATALOG_NODE_UPDATE")
	var node: Node = _nodes[stable_id]
	var row: Dictionary = _node_rows[stable_id]
	if not _set_properties(node, str(row.node_type), payload.changes):
		return false
	for key: Variant in payload.changes:
		row.properties[key] = payload.changes[key]
	_node_rows[stable_id] = row
	return _guard(_same(_node_readback(stable_id), row), "CATALOG_NODE_UPDATE_READBACK")


func _create_resource(owner_id: String, payload: Dictionary) -> bool:
	var resource_id: String = str(payload.get("resource_id", ""))
	var resource_type: String = str(payload.get("resource_type", ""))
	if not _nodes.has(owner_id) or _resources.has(resource_id) or not _identifier(resource_id) \
			or not payload.get("properties") is Dictionary or not ClassDB.class_exists(resource_type) \
			or not ClassDB.can_instantiate(resource_type):
		return _guard(false, "CATALOG_RESOURCE_CREATE")
	var value: Object = ClassDB.instantiate(resource_type)
	if not value is Resource or resource_type not in ["RectangleShape2D", "CapsuleShape2D", "BoxShape3D", "CapsuleShape3D"]:
		return _guard(false, "CATALOG_RESOURCE_CLASS")
	var resource: Resource = value as Resource
	resource.resource_name = resource_id
	resource.set_meta(RESOURCE_META, resource_id)
	resource.set_meta("hh_saved_resource_id", resource_id)
	if not _set_shape_properties(resource, payload.properties):
		return false
	_resources[resource_id] = resource
	_resource_order.append(resource_id)
	_resource_rows[resource_id] = {"resource_id": resource_id, "owner_stable_id": owner_id,
		"resource_type": resource_type, "properties": payload.properties.duplicate(true)}
	# The resource contract names a collision-shape node as the owner. Bind the
	# native resource immediately so it is part of the packed scene even when a
	# later node update merely reasserts the same typed reference.
	var owner: Node = _nodes[owner_id]
	if owner is CollisionShape2D and resource is Shape2D:
		(owner as CollisionShape2D).shape = resource as Shape2D
	elif owner is CollisionShape3D and resource is Shape3D:
		(owner as CollisionShape3D).shape = resource as Shape3D
	else:
		return _guard(false, "CATALOG_RESOURCE_OWNER")
	return _guard(_same(_resource_readback(resource_id), _resource_rows[resource_id]), "CATALOG_RESOURCE_READBACK")


func _instantiate_node(class_id: String, node_name: String, properties: Dictionary) -> Node:
	var class_spec: Variant = _catalog.get(class_id)
	if not class_spec is Dictionary or class_spec.get("instantiable") != true \
			or not ClassDB.class_exists(class_id) or not ClassDB.can_instantiate(class_id):
		_guard(false, "CATALOG_NODE_CLASS")
		return null
	var value: Object = ClassDB.instantiate(class_id)
	if not value is Node:
		_guard(false, "CATALOG_NODE_CLASS")
		return null
	var node: Node = value as Node
	node.name = node_name
	if not _set_properties(node, class_id, properties):
		node.free()
		return null
	return node


func _set_properties(node: Node, class_id: String, values: Dictionary) -> bool:
	var class_spec: Dictionary = _catalog[class_id]
	var admitted: Dictionary = class_spec.get("properties", {})
	var native := _property_map(class_id)
	for key: Variant in values:
		if typeof(key) != TYPE_STRING or not admitted.has(key) or not native.has(key):
			return _guard(false, "CATALOG_PROPERTY_UNKNOWN")
		var spec: Dictionary = admitted[key]
		if spec.get("writable") != true or not _native_property_matches(spec, native[key]):
			return _guard(false, "CATALOG_PROPERTY_TYPE")
		var converted: Variant = _to_native(values[key], spec)
		if converted == null and spec.get("type") != "resource":
			return _guard(false, "CATALOG_PROPERTY_VALUE")
		if spec.get("type") == "resource" and converted == null:
			return _guard(false, "CATALOG_RESOURCE_REFERENCE")
		node.set(str(key), converted)
		if not _same(_from_native(node.get(str(key)), spec), values[key]):
			return _guard(false, "CATALOG_PROPERTY_READBACK")
	return true


func _set_shape_properties(resource: Resource, values: Dictionary) -> bool:
	var allowed: Array = ["size"] if resource is RectangleShape2D or resource is BoxShape3D else ["radius", "height"]
	if values.size() != allowed.size():
		return _guard(false, "CATALOG_RESOURCE_PROPERTIES")
	for key: String in allowed:
		if not values.has(key):
			return _guard(false, "CATALOG_RESOURCE_PROPERTIES")
		var native: Variant = values[key]
		if key == "size":
			if not values[key] is Array:
				return _guard(false, "CATALOG_RESOURCE_PROPERTIES")
			native = Vector2(float(values[key][0]), float(values[key][1])) if resource is RectangleShape2D \
				else Vector3(float(values[key][0]), float(values[key][1]), float(values[key][2]))
		resource.set(key, native)
	return true


func _property_map(class_id: String) -> Dictionary:
	var result: Dictionary = {}
	# Include inherited native properties because the admitted catalog has
	# already flattened its own property inheritance.
	for row: Dictionary in ClassDB.class_get_property_list(class_id, false):
		result[str(row.name)] = row
	return result


func _native_property_matches(spec: Dictionary, native: Dictionary) -> bool:
	var kind: String = str(spec.get("type", ""))
	var actual: int = int(native.get("type", TYPE_NIL))
	if kind == "bool": return actual == TYPE_BOOL
	if kind in ["int", "enum"]: return actual == TYPE_INT
	if kind == "float": return actual == TYPE_FLOAT
	if kind == "string": return actual in [TYPE_STRING, TYPE_STRING_NAME]
	if kind == "vector2": return actual == TYPE_VECTOR2
	if kind == "vector3": return actual == TYPE_VECTOR3
	if kind == "rect2": return actual == TYPE_RECT2
	if kind == "resource":
		return actual == TYPE_OBJECT
	return false


func _to_native(value: Variant, spec: Dictionary) -> Variant:
	var kind: String = str(spec.type)
	if kind == "vector2" and value is Array and value.size() == 2:
		return Vector2(float(value[0]), float(value[1]))
	if kind == "vector3" and value is Array and value.size() == 3:
		return Vector3(float(value[0]), float(value[1]), float(value[2]))
	if kind == "rect2" and value is Array and value.size() == 4:
		return Rect2(float(value[0]), float(value[1]), float(value[2]), float(value[3]))
	if kind == "resource" and value is Dictionary and value.size() == 1 and value.has("resource_id"):
		var resource: Resource = _resource_for(str(value.resource_id))
		if resource != null and resource.is_class(str(spec.resource_base)):
			return resource
		return null
	return value


func _from_native(value: Variant, spec: Dictionary) -> Variant:
	match str(spec.type):
		"vector2": return [_clean(value.x), _clean(value.y)] if value is Vector2 else null
		"vector3": return [_clean(value.x), _clean(value.y), _clean(value.z)] if value is Vector3 else null
		"rect2": return [_clean(value.position.x), _clean(value.position.y), _clean(value.size.x), _clean(value.size.y)] if value is Rect2 else null
		"float": return _clean(float(value))
		"string": return str(value)
		"resource": return {"resource_id": _resource_identity(value)} if value is Resource else null
		_: return value


func _resource_for(resource_id: String) -> Resource:
	if _resources.has(resource_id):
		return _resources[resource_id]
	return _assets.get(resource_id) as Resource


func _resource_identity(resource: Resource) -> String:
	if resource == null:
		return ""
	var explicit: String = str(resource.get_meta(RESOURCE_META, ""))
	if not explicit.is_empty():
		return explicit
	for resource_id: String in _asset_order:
		if _assets.get(resource_id) == resource or str(resource.resource_path).begins_with(str(_asset_paths[resource_id])):
			return resource_id
	return str(resource.resource_name)


func _node_readback(stable_id: String, source: Dictionary = {}) -> Dictionary:
	if source.is_empty():
		source = _nodes
	var expected: Dictionary = _node_rows[stable_id]
	var node: Node = source.get(stable_id)
	if node == null:
		return {"invalid": "node_missing"}
	var properties: Dictionary = {}
	var admitted: Dictionary = _catalog[str(expected.node_type)].properties
	for key: Variant in expected.properties:
		properties[key] = _from_native(node.get(str(key)), admitted[key])
	var parent_id: Variant = null
	if stable_id != "root":
		parent_id = str(node.get_parent().get_meta(ID_META, "")) if node.get_parent() != null else ""
	return {"stable_id": str(node.get_meta(ID_META, "")), "parent_id": parent_id,
		"node_type": node.get_class(), "name": str(node.name), "properties": properties}


func _resource_readback(resource_id: String, source: Dictionary = {}) -> Dictionary:
	if source.is_empty():
		source = _nodes
	var expected: Dictionary = _resource_rows[resource_id]
	var resource: Resource = _locate_shape(expected, source)
	if resource == null:
		return {"invalid": "resource_missing"}
	var properties: Dictionary = {}
	for key: Variant in expected.properties:
		var value: Variant = resource.get(str(key))
		if value is Vector2:
			properties[key] = [_clean(value.x), _clean(value.y)]
		elif value is Vector3:
			properties[key] = [_clean(value.x), _clean(value.y), _clean(value.z)]
		elif value is float:
			properties[key] = _clean(value)
		else:
			properties[key] = value
	return {"resource_id": _resource_identity(resource), "owner_stable_id": expected.owner_stable_id,
		"resource_type": resource.get_class(), "properties": properties}


func _locate_shape(spec: Dictionary, source: Dictionary) -> Resource:
	var owner: Node = source.get(str(spec.owner_stable_id))
	if owner is CollisionShape2D:
		return (owner as CollisionShape2D).shape
	if owner is CollisionShape3D:
		return (owner as CollisionShape3D).shape
	return null


func _snapshot(root: Node) -> Dictionary:
	if root == null:
		return {"invalid": "root_missing"}
	var found: Dictionary = {}
	var pending: Array[Node] = [root]
	while not pending.is_empty():
		var node: Node = pending.pop_back()
		var stable_id: String = str(node.get_meta(ID_META, ""))
		if stable_id.is_empty() or found.has(stable_id) or node.get_script() != null:
			return {"invalid": "identity"}
		found[stable_id] = node
		for child: Node in node.get_children():
			pending.append(child)
	if found.size() != _node_order.size():
		return {"invalid": "node_count"}
	var nodes: Array[Dictionary] = []
	for stable_id: String in _node_order:
		var row: Dictionary = _node_readback(stable_id, found)
		if row.has("invalid"):
			return row
		nodes.append(row)
	var resources: Array[Dictionary] = []
	for resource_id: String in _resource_order:
		var row: Dictionary = _resource_readback(resource_id, found)
		if row.has("invalid"):
			return row
		resources.append(row)
	var result := {"nodes": nodes, "resources": resources}
	if not _asset_order.is_empty():
		var assets: Array[Dictionary] = []
		for resource_id: String in _asset_order:
			var resource: Resource = _assets[resource_id]
			if resource == null or not resource.is_class("Mesh"):
				return {"invalid": "asset_base"}
			assets.append({"resource_id": resource_id, "base": "Mesh"})
		result["asset_resources"] = assets
	return result


func _attach() -> void:
	if is_instance_valid(_bench) and is_instance_valid(_authored) and _authored.get_parent() == null:
		_bench.add_child(_authored)


func _detach() -> void:
	if is_instance_valid(_bench) and is_instance_valid(_authored) and _authored.get_parent() == _bench:
		_bench.remove_child(_authored)


func _cleanup_history(history: UndoRedo) -> void:
	if history != null:
		history.clear_history()


func _dispose_authored() -> void:
	if is_instance_valid(_authored):
		if _authored.get_parent() != null:
			_authored.get_parent().remove_child(_authored)
		_authored.free()


func _result(data: Dictionary, snapshots: Dictionary, scene_hash: String) -> Dictionary:
	var transaction: Dictionary = data.get("transaction", {})
	return {"schema": OBSERVATION_SCHEMA, "authority": 0, "public_ack": false,
		"pid": OS.get_process_id(), "input_sha256": FileAccess.get_sha256("res://catalog-input.json"),
		"transaction_digest": transaction.get("transaction_digest", ""),
		"command_ids": transaction.get("command_ids", []), "commands": _commands,
		"snapshots": snapshots, "checks": _checks, "failures": _failures,
		"scene_sha256": scene_hash}


func _guard(condition: bool, code: String) -> bool:
	if not condition and code not in _failures:
		_failures.append(code)
	return condition


func _identifier(value: Variant) -> bool:
	if typeof(value) != TYPE_STRING or value.is_empty() or value.length() > 64:
		return false
	var regex := RegEx.new()
	return regex.compile("^[a-z][a-z0-9._-]{0,63}$") == OK and regex.search(value) != null


func _clean(value: float) -> float:
	return String.num(value, 6).to_float()


func _same(left: Variant, right: Variant) -> bool:
	if left is Dictionary and right is Dictionary:
		if left.size() != right.size(): return false
		for key: Variant in left:
			if not right.has(key) or not _same(left[key], right[key]): return false
		return true
	if left is Array and right is Array:
		if left.size() != right.size(): return false
		for index: int in left.size():
			if not _same(left[index], right[index]): return false
		return true
	if (left is int or left is float) and (right is int or right is float):
		return absf(float(left) - float(right)) <= EPSILON
	return typeof(left) == typeof(right) and left == right


func _on_main() -> bool:
	return OS.get_thread_caller_id() == OS.get_main_thread_id()

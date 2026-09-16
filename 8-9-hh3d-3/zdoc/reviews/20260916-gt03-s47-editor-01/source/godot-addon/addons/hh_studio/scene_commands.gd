@tool
extends RefCounted
## In-memory semantic editor commands. The host owns auth, lease, journal and save.

const JCS = preload("res://addons/hh_studio/jcs_godot.gd")
const ID_META: StringName = &"hh_studio_id"
const SCENE_PATH: String = "res://scenes/fixture.tscn"
const SCRIPT_PATH: String = "res://scripts/fixture_actor.gd"
const MAX_NODES: int = 64
const MAX_DEPTH: int = 16
const MAX_COMMANDS: int = 256
const PROJECTION_KEYS: Array[String] = ["operation", "command_id", "expected_revision",
	"expected_generation", "target_stable_id", "payload"]

## Native undo may advance its cursor even when our guarded callback refuses.
## A direct Node do-reference would then free a still-attached node when redo
## history is discarded. This custody owner only frees detached nodes.
class DetachedNodeCustody extends RefCounted:
	var node: Node3D

	func _init(value: Node3D) -> void:
		node = value

	func _notification(what: int) -> void:
		if what == NOTIFICATION_PREDELETE and is_instance_valid(node):
			if node.get_parent() == null:
				node.free()


var _root: Node3D
var _undo: EditorUndoRedoManager
var _generation: int = 0
var _history_id: int = -99
var _blocked: bool = false
var _busy: bool = false
var _initialized: bool = false
var _last: Dictionary = {}
var _receipts: Dictionary = {}
var _prefix: String = ""
var _scan_error: String = ""
var _nodes: Dictionary = {}


func initialize(root: Node3D, manager: EditorUndoRedoManager, generation: int = 1) -> Dictionary:
	if not _on_main():
		return _failure("SCENE_MAIN_THREAD_REQUIRED")
	if _initialized:
		return _failure("SCENE_ALREADY_INITIALIZED")
	if not Engine.is_editor_hint() or not is_instance_valid(root) or not is_instance_valid(manager):
		return _failure("SCENE_EDITOR_CONTEXT_REQUIRED")
	if generation < 1 or generation > 2147483647 or EditorInterface.get_edited_scene_root() != root:
		return _failure("SCENE_CONTEXT_MISMATCH")
	if root.scene_file_path != SCENE_PATH or root.get_meta(ID_META, null) != "root":
		return _failure("SCENE_ROOT_SCOPE")
	_root = root
	_undo = manager
	_generation = generation
	_history_id = manager.get_object_history_id(root)
	if _history_id <= 0:
		return _failure("SCENE_HISTORY_UNAVAILABLE")
	_prefix = "HH semantic " + str(get_instance_id()) + ": "
	_initialized = true
	var result: Dictionary = inspect()
	if not result.ok:
		_blocked = true
	return result


func inspect(offset: int = 0, limit: int = MAX_NODES) -> Dictionary:
	var guard: Dictionary = _context()
	if not guard.ok:
		return guard
	if offset < 0 or offset > MAX_NODES or limit < 1 or limit > MAX_NODES:
		return _failure("SCENE_INSPECT_LIMIT")
	var snapshot: Dictionary = _snapshot()
	if not snapshot.ok:
		return snapshot
	var all_nodes: Array = snapshot.state.nodes
	return {"ok": true, "code": "SCENE_INSPECTED", "generation": _generation,
		"revision": snapshot.revision, "state": {"nodes": all_nodes.slice(offset, offset + limit)},
		"total": all_nodes.size(), "offset": offset, "history_id": _history_id,
		"held": _blocked, "filesystem_mutated": false}


func preview(operation: Dictionary) -> Dictionary:
	var prepared: Dictionary = _prepare(operation)
	if not prepared.ok:
		return prepared
	var result: Dictionary = {"ok": true, "code": "SCENE_PREVIEW", "operation": operation.operation,
		"command_id": operation.command_id, "generation": _generation,
		"before_revision": prepared.before_revision,
		"diff": {"before": prepared.before_values, "after": prepared.after_values},
		"affected_files": ["scenes/fixture.tscn"], "undo_policy": "revision_guarded",
		"filesystem_mutated": false}
	_discard_prepared(prepared)
	return result


func apply(operation: Dictionary) -> Dictionary:
	var envelope: Dictionary = _validate_projection(operation)
	if not envelope.ok:
		return envelope
	var digest: String = _digest(operation)
	if _receipts.has(operation.command_id):
		var old: Dictionary = _receipts[operation.command_id]
		if old.digest != digest:
			return _failure("SCENE_COMMAND_CONFLICT")
		return old.result.duplicate(true)
	if _receipts.size() >= MAX_COMMANDS:
		return _failure("SCENE_COMMAND_CAPACITY")
	var prepared: Dictionary = _prepare(operation)
	if not prepared.ok:
		return prepared
	_busy = true
	var label: String = _prefix + operation.command_id
	_undo.create_action(label, UndoRedo.MERGE_DISABLE, _root)
	_undo.add_do_method(self, &"_transition", prepared, true)
	_undo.add_undo_method(self, &"_transition", prepared, false)
	if prepared.kind == "create":
		_undo.add_do_reference(prepared.custody)
	elif prepared.kind == "remove":
		_undo.add_undo_reference(prepared.custody)
	_last = _failure("SCENE_POSTCONDITION_UNKNOWN")
	_undo.commit_action()
	_busy = false
	var result: Dictionary = _last.duplicate(true)
	result["command_id"] = operation.command_id
	result["operation"] = operation.operation
	_receipts[operation.command_id] = {"digest": digest, "result": result.duplicate(true)}
	return result


func undo(operation: Dictionary) -> Dictionary:
	return _history_operation(operation, false)


func redo(operation: Dictionary) -> Dictionary:
	return _history_operation(operation, true)


func last_transition() -> Dictionary:
	if not _on_main():
		return _failure("SCENE_MAIN_THREAD_REQUIRED")
	return _last.duplicate(true)


func _history_operation(operation: Dictionary, forward: bool) -> Dictionary:
	var checked: Dictionary = _validate_projection(operation)
	if not checked.ok:
		return checked
	var expected_name: String = "scene.redo" if forward else "scene.undo"
	if operation.operation != expected_name or operation.target_stable_id != "root":
		return _failure("SCENE_OPERATION_SCOPE")
	if not _shape(operation.payload, ["expected_generation", "steps"]) or typeof(operation.payload.steps) != TYPE_INT or operation.payload.steps != 1:
		return _failure("SCENE_INVALID_PAYLOAD")
	var digest: String = _digest(operation)
	if _receipts.has(operation.command_id):
		var previous: Dictionary = _receipts[operation.command_id]
		return previous.result.duplicate(true) if previous.digest == digest else _failure("SCENE_COMMAND_CONFLICT")
	if _receipts.size() >= MAX_COMMANDS:
		return _failure("SCENE_COMMAND_CAPACITY")
	var state: Dictionary = _current_for(operation)
	if not state.ok:
		return state
	var history: UndoRedo = _undo.get_history_undo_redo(_history_id)
	if history == null or (not history.has_redo() if forward else not history.has_undo()):
		return _failure("SCENE_HISTORY_EMPTY")
	var index: int = history.get_current_action() + (1 if forward else 0)
	if not history.get_action_name(index).begins_with(_prefix):
		return _failure("SCENE_HISTORY_FOREIGN_ACTION")
	_busy = true
	_last = _failure("SCENE_POSTCONDITION_UNKNOWN")
	var moved: bool = history.redo() if forward else history.undo()
	_busy = false
	if not moved:
		return _failure("SCENE_HISTORY_EMPTY")
	var result: Dictionary = _last.duplicate(true)
	result["command_id"] = operation.command_id
	result["operation"] = operation.operation
	_receipts[operation.command_id] = {"digest": digest, "result": result.duplicate(true)}
	return result


func _prepare(operation: Dictionary) -> Dictionary:
	var checked: Dictionary = _validate_projection(operation)
	if not checked.ok:
		return checked
	var snapshot: Dictionary = _current_for(operation)
	if not snapshot.ok:
		return snapshot
	var payload: Dictionary = operation.payload
	var target: Node3D = _nodes.get(operation.target_stable_id) as Node3D
	if not is_instance_valid(target):
		return _failure("SCENE_STABLE_ID_NOT_FOUND")
	var name: String = operation.operation
	if name not in ["scene.node.create", "scene.node.update", "scene.node.remove"]:
		return _failure("SCENE_UNSUPPORTED_OPERATION")
	var record: Dictionary = {"ok": true, "kind": name.trim_prefix("scene.node."),
		"before_revision": snapshot.revision, "after_revision": "", "generation": _generation,
		"before_values": {}, "after_values": {}, "target_id": operation.target_stable_id,
		"node": target, "parent": target.get_parent(), "index": target.get_index(),
		"owner": target.owner, "initial": true}
	if name == "scene.node.create":
		var keys: Array[String] = ["expected_generation", "stable_id", "node_type", "name", "position", "rotation_degrees", "scale"]
		if payload.get("node_type") == "MeshInstance3D":
			keys.append("box_size")
		if not _shape(payload, keys) or not _identifier(payload.get("stable_id")) or payload.stable_id == "root":
			return _failure("SCENE_INVALID_PAYLOAD")
		if _nodes.has(payload.stable_id):
			return _failure("SCENE_STABLE_ID_CONFLICT")
		if payload.node_type not in ["Node3D", "MeshInstance3D"] or _nodes.size() >= MAX_NODES:
			return _failure("SCENE_NODE_TYPE_OR_LIMIT")
		if _depth(target) >= MAX_DEPTH or not _valid_values(payload, payload.node_type == "MeshInstance3D"):
			return _failure("SCENE_INVALID_PAYLOAD")
		if not _name_available(target, payload.name, null):
			return _failure("SCENE_NAME_CONFLICT")
		var created: Node3D = MeshInstance3D.new() if payload.node_type == "MeshInstance3D" else Node3D.new()
		created.set_meta(ID_META, payload.stable_id)
		if created is MeshInstance3D:
			(created as MeshInstance3D).mesh = BoxMesh.new()
		_set_values(created, payload)
		record.node = created
		record.parent = target
		record.owner = _root
		record.index = target.get_child_count()
		record.custody = DetachedNodeCustody.new(created)
		record.after_values = _editable_values(created)
		record.detached_signature = _node_signature(created)
		if record.detached_signature.is_empty():
			return _failure("SCENE_STORED_PROPERTY_UNSUPPORTED")
	elif name == "scene.node.update":
		if not _shape(payload, ["expected_generation", "changes"]) or typeof(payload.changes) != TYPE_DICTIONARY:
			return _failure("SCENE_INVALID_PAYLOAD")
		var changes: Dictionary = payload.changes
		if changes.is_empty() or not _valid_values(changes, target is MeshInstance3D, true):
			return _failure("SCENE_INVALID_PAYLOAD")
		if changes.has("name") and target != _root and not _name_available(target.get_parent(), changes.name, target):
			return _failure("SCENE_NAME_CONFLICT")
		record.before_values = _editable_values(target)
		record.before_transform = target.transform
		record.before_name = target.name
		var scratch: Node3D = MeshInstance3D.new() if target is MeshInstance3D else Node3D.new()
		scratch.name = target.name
		scratch.transform = target.transform
		if target is MeshInstance3D:
			record.before_mesh = (target as MeshInstance3D).mesh
			record.before_mesh_signature = _resource_signature(record.before_mesh)
			(scratch as MeshInstance3D).mesh = (target as MeshInstance3D).mesh.duplicate(true)
		_set_values(scratch, changes)
		record.after_values = _editable_values(scratch)
		record.after_transform = scratch.transform
		record.after_name = scratch.name
		if scratch is MeshInstance3D:
			record.after_mesh = (scratch as MeshInstance3D).mesh
			record.after_mesh_signature = _resource_signature(record.after_mesh)
		scratch.free()
	else:
		if not _shape(payload, ["expected_generation"]) or target == _root or target.get_child_count(true) != 0:
			return _failure("SCENE_REMOVE_REQUIRES_NONROOT_LEAF")
		record.before_values = _editable_values(target)
		record.custody = DetachedNodeCustody.new(target)
	return record


func _discard_prepared(prepared: Dictionary) -> void:
	# Preview only allocates detached scratch nodes; custody owns their disposal.
	prepared.clear()


func _transition(record: Dictionary, forward: bool) -> void:
	var guard: Dictionary = _context()
	if not guard.ok or _blocked or record.generation != _generation:
		_last = _failure("SCENE_HISTORY_RECONCILIATION_REQUIRED")
		_blocked = true
		return
	var snapshot: Dictionary = _snapshot()
	var expected: String = record.before_revision if forward else record.after_revision
	if not snapshot.ok or snapshot.revision != expected:
		_last = _failure("SCENE_MANUAL_EDIT_CONFLICT")
		_blocked = true
		return
	var node: Node3D = record.node as Node3D
	var parent: Node = record.parent as Node
	if not is_instance_valid(node) or not is_instance_valid(parent):
		_last = _failure("SCENE_HISTORY_OBJECT_CHANGED")
		_blocked = true
		return
	var attach: bool = (record.kind == "create" and forward) or (record.kind == "remove" and not forward)
	var detach: bool = (record.kind == "remove" and forward) or (record.kind == "create" and not forward)
	if attach:
		if node.get_parent() != null or _node_signature(node) != record.detached_signature:
			_last = _failure("SCENE_DETACHED_NODE_CHANGED")
			_blocked = true
			return
		if not _name_available(parent, str(node.name), null):
			_last = _failure("SCENE_NAME_CONFLICT")
			_blocked = true
			return
	elif _nodes.get(str(node.get_meta(ID_META, ""))) != node or (node != _root and node.get_parent() != parent):
		_last = _failure("SCENE_HISTORY_OBJECT_CHANGED")
		_blocked = true
		return
	if record.kind == "update" and node is MeshInstance3D:
		var mesh: BoxMesh = (record.after_mesh if forward else record.before_mesh) as BoxMesh
		var expected_mesh: String = record.after_mesh_signature if forward else record.before_mesh_signature
		if expected_mesh.is_empty() or _resource_signature(mesh) != expected_mesh:
			_last = _failure("SCENE_RESOURCE_SNAPSHOT_CHANGED")
			_blocked = true
			return
	# Exactly one callback owns all live mutations, with no yield or input-selected
	# method/property name. Whole-state guards are checked before the first effect.
	if attach:
		parent.add_child(node)
		parent.move_child(node, mini(record.index, parent.get_child_count() - 1))
		node.owner = record.owner
	elif detach:
		parent.remove_child(node)
		record.detached_signature = _node_signature(node)
	else:
		node.name = record.after_name if forward else record.before_name
		node.transform = record.after_transform if forward else record.before_transform
		if node is MeshInstance3D:
			(node as MeshInstance3D).mesh = record.after_mesh if forward else record.before_mesh
	var after: Dictionary = _snapshot()
	if not after.ok:
		_blocked = true
		_last = _failure("SCENE_POSTCONDITION_UNKNOWN")
		return
	if forward and record.initial:
		record.after_revision = after.revision
		record.initial = false
	elif after.revision != (record.after_revision if forward else record.before_revision):
		_blocked = true
		_last = _failure("SCENE_POSTCONDITION_UNKNOWN")
		return
	_last = {"ok": true, "code": "SCENE_APPLIED_IN_MEMORY", "generation": _generation,
		"before_revision": snapshot.revision, "revision": after.revision, "state": after.state,
		"history_id": _history_id, "filesystem_mutated": false}


func _validate_projection(operation: Dictionary) -> Dictionary:
	var context: Dictionary = _context()
	if not context.ok:
		return context
	if not _shape(operation, PROJECTION_KEYS):
		return _failure("SCENE_INVALID_PROJECTION")
	if typeof(operation.operation) != TYPE_STRING or not _identifier(operation.command_id) or not _identifier(operation.target_stable_id):
		return _failure("SCENE_INVALID_PROJECTION")
	if typeof(operation.expected_revision) != TYPE_STRING or not _matches(operation.expected_revision, "^sha256:[0-9a-f]{64}$"):
		return _failure("SCENE_INVALID_REVISION")
	if typeof(operation.expected_generation) != TYPE_INT or operation.expected_generation != _generation:
		return _failure("SCENE_GENERATION_CONFLICT")
	if typeof(operation.payload) != TYPE_DICTIONARY or typeof(operation.payload.get("expected_generation")) != TYPE_INT or operation.payload.expected_generation != _generation:
		return _failure("SCENE_GENERATION_CONFLICT")
	var canonical: Dictionary = JCS.new().canonicalize(operation)
	if not canonical.ok or str(canonical.canonical).to_utf8_buffer().size() > 8192:
		return _failure("SCENE_PAYLOAD_LIMIT")
	return {"ok": true}


func _current_for(operation: Dictionary) -> Dictionary:
	if _blocked or _busy:
		return _failure("SCENE_RECONCILIATION_REQUIRED")
	var snapshot: Dictionary = _snapshot()
	if not snapshot.ok:
		return snapshot
	if snapshot.revision != operation.expected_revision:
		return _failure("SCENE_REVISION_CONFLICT")
	return snapshot


func _snapshot() -> Dictionary:
	_scan_error = ""
	_nodes = {}
	var rows: Array[Dictionary] = []
	_walk(_root, "", 0, rows)
	if not _scan_error.is_empty():
		return _failure(_scan_error)
	var state: Dictionary = {"nodes": rows}
	var canonical: Dictionary = JCS.new().canonicalize(state)
	if not canonical.ok:
		return _failure("SCENE_STATE_LIMIT")
	if str(canonical.canonical).to_utf8_buffer().size() > 262144:
		return _failure("SCENE_STATE_LIMIT")
	return {"ok": true, "revision": canonical.sha256, "state": state}


func _walk(node: Node, parent_id: String, depth: int, rows: Array[Dictionary]) -> void:
	if not _scan_error.is_empty():
		return
	if depth > MAX_DEPTH or rows.size() >= MAX_NODES or node.get_class() not in ["Node3D", "MeshInstance3D"]:
		_scan_error = "SCENE_UNSUPPORTED_NODE_OR_LIMIT"
		return
	var stable_id: Variant = node.get_meta(ID_META, null)
	if not _identifier(stable_id) or _nodes.has(stable_id) or (node == _root) != (stable_id == "root"):
		_scan_error = "SCENE_STABLE_ID_INVALID"
		return
	if node != _root and node.owner != _root:
		_scan_error = "SCENE_OWNER_SCOPE"
		return
	if node is MeshInstance3D and not (node as MeshInstance3D).mesh is BoxMesh:
		_scan_error = "SCENE_UNSUPPORTED_MESH"
		return
	for signal_info: Dictionary in node.get_signal_list():
		for connection: Dictionary in node.get_signal_connection_list(signal_info.name):
			if (int(connection.flags) & Object.CONNECT_PERSIST) != 0:
				_scan_error = "SCENE_PERSISTENT_CONNECTION_UNSUPPORTED"
				return
	_nodes[stable_id] = node
	var row: Dictionary = _editable_values(node as Node3D)
	row["stable_id"] = stable_id
	row["parent_id"] = parent_id
	row["sibling_index"] = node.get_index() if node != _root else 0
	row["owner_id"] = "root" if node.owner == _root else ""
	row["stored"] = _stored_properties(node, 0)
	var groups: Array[String] = []
	for group: StringName in node.get_groups():
		groups.append(str(group))
	groups.sort()
	row["groups"] = groups
	rows.append(row)
	for child: Node in node.get_children(true):
		_walk(child, stable_id, depth + 1, rows)


func _stored_properties(object: Object, depth: int) -> Dictionary:
	var result: Dictionary = {}
	if depth > 8:
		_scan_error = "SCENE_RESOURCE_LIMIT"
		return result
	for property: Dictionary in object.get_property_list():
		if (int(property.usage) & PROPERTY_USAGE_STORAGE) == 0:
			continue
		var key: String = str(property.name)
		if key in ["resource_path", "resource_scene_unique_id", "_bundled"]:
			continue
		result[key] = _stored_value(object.get(key), depth + 1)
		if result.size() > 192 or not _scan_error.is_empty():
			_scan_error = "SCENE_STORED_PROPERTY_UNSUPPORTED" if _scan_error.is_empty() else _scan_error
			return result
	return result


func _stored_value(value: Variant, depth: int) -> Variant:
	if depth > 16:
		_scan_error = "SCENE_RESOURCE_LIMIT"
		return null
	if value is GDScript:
		var script: GDScript = value as GDScript
		if script.resource_path != SCRIPT_PATH:
			_scan_error = "SCENE_SCRIPT_SCOPE"
			return null
		return {"type": "GDScript", "path": SCRIPT_PATH, "source_sha256": script.source_code.sha256_text()}
	if value is Resource:
		if not value is BoxMesh:
			_scan_error = "SCENE_RESOURCE_UNSUPPORTED"
			return null
		return {"type": "BoxMesh", "stored": _stored_properties(value, depth + 1)}
	match typeof(value):
		TYPE_NIL, TYPE_BOOL, TYPE_INT, TYPE_FLOAT, TYPE_STRING:
			if typeof(value) == TYPE_FLOAT and not is_finite(value):
				_scan_error = "SCENE_NONFINITE_STATE"
			return value
		TYPE_STRING_NAME, TYPE_NODE_PATH:
			return {"type": typeof(value), "value": str(value)}
		TYPE_DICTIONARY:
			if value.size() > 128:
				_scan_error = "SCENE_RESOURCE_LIMIT"
				return null
			var copied: Dictionary = {}
			for key: Variant in value:
				if typeof(key) not in [TYPE_STRING, TYPE_STRING_NAME]:
					_scan_error = "SCENE_METADATA_UNSUPPORTED"
					return null
				copied[str(key)] = _stored_value(value[key], depth + 1)
			return copied
		TYPE_ARRAY:
			if value.size() > 128:
				_scan_error = "SCENE_RESOURCE_LIMIT"
				return null
			var copied: Array = []
			for item: Variant in value:
				copied.append(_stored_value(item, depth + 1))
			return copied
		TYPE_VECTOR2, TYPE_VECTOR3, TYPE_VECTOR4, TYPE_QUATERNION, TYPE_COLOR, TYPE_BASIS, TYPE_TRANSFORM3D, TYPE_AABB, TYPE_RECT2, TYPE_TRANSFORM2D:
			var text: String = str(value).to_lower()
			if "nan" in text or "inf" in text:
				_scan_error = "SCENE_NONFINITE_STATE"
			return {"type": typeof(value), "binary": var_to_bytes(value).hex_encode()}
		TYPE_VECTOR2I, TYPE_VECTOR3I, TYPE_VECTOR4I, TYPE_RECT2I:
			return {"type": typeof(value), "binary": var_to_bytes(value).hex_encode()}
		_:
			_scan_error = "SCENE_STORED_PROPERTY_UNSUPPORTED"
			return null


func _node_signature(node: Node3D) -> String:
	_scan_error = ""
	var row: Dictionary = {"class": node.get_class(), "stored": _stored_properties(node, 0),
		"editable": _editable_values(node), "child_count": node.get_child_count(true)}
	var canonical: Dictionary = JCS.new().canonicalize(row)
	return canonical.sha256 if canonical.ok and _scan_error.is_empty() else ""


func _resource_signature(mesh: BoxMesh) -> String:
	_scan_error = ""
	var canonical: Dictionary = JCS.new().canonicalize(_stored_properties(mesh, 0))
	return canonical.sha256 if canonical.ok and _scan_error.is_empty() else ""


func _editable_values(node: Node3D) -> Dictionary:
	var values: Dictionary = {"node_type": node.get_class(), "name": str(node.name),
		"position": _vector(node.position), "rotation_degrees": _vector(node.rotation_degrees),
		"scale": _vector(node.scale)}
	if node is MeshInstance3D and (node as MeshInstance3D).mesh is BoxMesh:
		values["box_size"] = _vector(((node as MeshInstance3D).mesh as BoxMesh).size)
	return values


func _set_values(node: Node3D, values: Dictionary) -> void:
	if values.has("name"):
		node.name = values.name
	if values.has("position"):
		node.position = _to_vector(values.position)
	if values.has("rotation_degrees"):
		node.rotation_degrees = _to_vector(values.rotation_degrees)
	if values.has("scale"):
		node.scale = _to_vector(values.scale)
	if values.has("box_size") and node is MeshInstance3D:
		((node as MeshInstance3D).mesh as BoxMesh).size = _to_vector(values.box_size)


func _valid_values(values: Dictionary, mesh: bool, changes: bool = false) -> bool:
	if changes:
		for key: Variant in values:
			if key not in ["name", "position", "rotation_degrees", "scale", "box_size"]:
				return false
	if values.has("name") and (typeof(values.name) != TYPE_STRING or not _matches(values.name, "^[A-Za-z][A-Za-z0-9_]{0,47}$")):
		return false
	for key: String in ["position", "rotation_degrees", "scale", "box_size"]:
		if not values.has(key):
			continue
		if key == "box_size" and not mesh:
			return false
		var bounds: Array[float] = [-10000.0, 10000.0]
		if key == "rotation_degrees":
			bounds = [-360.0, 360.0]
		elif key in ["scale", "box_size"]:
			bounds = [0.001, 1000.0]
		if typeof(values[key]) != TYPE_ARRAY or values[key].size() != 3:
			return false
		for scalar: Variant in values[key]:
			if typeof(scalar) not in [TYPE_INT, TYPE_FLOAT] or not is_finite(float(scalar)) or float(scalar) < bounds[0] or float(scalar) > bounds[1]:
				return false
	return true


func _context() -> Dictionary:
	if not _on_main():
		return _failure("SCENE_MAIN_THREAD_REQUIRED")
	if not _initialized or not is_instance_valid(_root) or not is_instance_valid(_undo):
		return _failure("SCENE_NOT_INITIALIZED")
	if not Engine.is_editor_hint() or EditorInterface.get_edited_scene_root() != _root or _root.scene_file_path != SCENE_PATH:
		return _failure("SCENE_CONTEXT_MISMATCH")
	return {"ok": true}


func _name_available(parent: Node, desired: String, excluded: Node) -> bool:
	for child: Node in parent.get_children(true):
		if child != excluded and str(child.name).to_lower() == desired.to_lower():
			return false
	return true


func _depth(node: Node) -> int:
	var depth: int = 0
	while node != _root:
		node = node.get_parent()
		depth += 1
		if node == null or depth > MAX_DEPTH:
			return MAX_DEPTH
	return depth


func _shape(value: Dictionary, keys: Array) -> bool:
	if value.size() != keys.size():
		return false
	for key: Variant in keys:
		if not value.has(key):
			return false
	return true


func _identifier(value: Variant) -> bool:
	return typeof(value) == TYPE_STRING and _matches(value, "^[a-z][a-z0-9._-]{0,63}$")


func _matches(value: String, pattern: String) -> bool:
	var expression: RegEx = RegEx.new()
	if expression.compile(pattern) != OK:
		return false
	return expression.search(value) != null


func _digest(operation: Dictionary) -> String:
	return JCS.new().canonicalize({"operation": operation.operation,
		"target": operation.target_stable_id, "payload": operation.payload}).sha256


func _vector(value: Vector3) -> Array[float]:
	return [value.x, value.y, value.z]


func _to_vector(value: Array) -> Vector3:
	return Vector3(float(value[0]), float(value[1]), float(value[2]))


func _on_main() -> bool:
	return OS.get_thread_caller_id() == OS.get_main_thread_id()


func _failure(code: String) -> Dictionary:
	return {"ok": false, "code": code, "filesystem_mutated": false,
		"next_action": "inspect_reconcile"}

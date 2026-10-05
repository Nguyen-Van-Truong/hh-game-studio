@tool
extends EditorPlugin
## Private diagnostic: consumes validated fixture proposals, never remote input.
## Gameplay code is not loaded in this Windows editor.

var _failures: Array[String] = []
var _checks: Dictionary = {}
var _snapshots: Dictionary = {}
var _recipe: Dictionary = {}
var _bench: Node
var _arena: Node2D

func _enter_tree() -> void:
	call_deferred("_run")

func _check(label: String, value: bool) -> bool:
	_checks[label] = value
	if not value:
		_failures.append(label)
	return value

func _json_value(value: Variant) -> Variant:
	if value is Vector2:
		return [value.x, value.y]
	return value

func _native_value(value: Variant) -> Variant:
	if value is Array and value.size() == 2:
		return Vector2(float(value[0]), float(value[1]))
	return value

func _same(left: Variant, right: Variant) -> bool:
	# Godot JSON parses numbers as float; native integer properties stay int.
	# Dictionary's deep equality distinguishes those types. Compare JSON values
	# recursively, preserving bool/string types and every key/array position.
	if left is Dictionary and right is Dictionary:
		if left.size() != right.size():
			return false
		for key: Variant in left:
			if not right.has(key) or not _same(left[key], right[key]):
				return false
		return true
	if left is Array and right is Array:
		if left.size() != right.size():
			return false
		for index: int in range(left.size()):
			if not _same(left[index], right[index]):
				return false
		return true
	if (left is int or left is float) and (right is int or right is float):
		return float(left) == float(right)
	return typeof(left) == typeof(right) and left == right

func _make_node(spec: Dictionary) -> Node:
	var kind: String = spec.node_type
	if not _check("class_" + kind, ClassDB.class_exists(kind) and ClassDB.can_instantiate(kind)):
		return null
	var names: Array[String] = []
	for prop: Dictionary in ClassDB.class_get_property_list(kind, false):
		names.append(str(prop.name))
	_check("unknown_property_rejected_" + kind, "hh_unknown_property" not in names)
	var node := ClassDB.instantiate(kind) as Node
	if node == null:
		_check("construct_" + kind, false)
		return null
	node.name = spec.name
	node.set_meta("hh_saved_id", spec.stable_id)
	for key: String in spec.properties:
		if not _check("property_exists_" + spec.stable_id + "_" + key, key in names):
			node.free()
			return null
		var native: Variant = node.get(key)
		var proposed: Variant = _native_value(spec.properties[key])
		if typeof(native) == TYPE_INT and proposed is float:
			proposed = int(proposed)
		node.set(key, proposed)
		_check("set_" + spec.stable_id + "_" + key, _json_value(node.get(key)) == spec.properties[key])
	return node

func _prepare() -> Node2D:
	var root := _make_node(_recipe.root) as Node2D
	if root == null:
		return null
	var nodes: Dictionary = {"root": root}
	for command: Dictionary in _recipe.node_commands:
		if not _check("node_operation_" + command.command_id, command.operation == "scene.node.create"):
			root.free()
			return null
		var payload: Dictionary = command.payload
		if not nodes.has(command.target_stable_id) or nodes.has(payload.stable_id):
			_check("node_parent_or_id", false)
			root.free()
			return null
		var node := _make_node(payload)
		if node == null:
			root.free()
			return null
		(nodes[command.target_stable_id] as Node).add_child(node)
		node.owner = root
		nodes[payload.stable_id] = node
	for command: Dictionary in _recipe.resource_commands:
		var payload: Dictionary = command.payload
		if not _check("resource_operation_" + command.command_id,
				command.operation == "scene.resource.create" and payload.resource_type == "RectangleShape2D"
				and nodes.get(command.target_stable_id) is CollisionShape2D):
			root.free()
			return null
		var shape := RectangleShape2D.new()
		shape.size = _native_value(payload.properties.size)
		shape.set_meta("hh_saved_resource_id", payload.resource_id)
		(nodes[command.target_stable_id] as CollisionShape2D).shape = shape
	return root

func _snapshot(root: Node) -> Dictionary:
	if root == null:
		return {"nodes": [], "resources": []}
	var by_id: Dictionary = {}
	var pending: Array[Node] = [root]
	while not pending.is_empty():
		var node: Node = pending.pop_back()
		var identity: String = str(node.get_meta("hh_saved_id", ""))
		if identity.is_empty() or by_id.has(identity) or node.get_script() != null:
			return {"invalid": "identity_or_script"}
		by_id[identity] = node
		for child: Node in node.get_children():
			pending.append(child)
	var rows: Array[Dictionary] = []
	var shapes: Array[Dictionary] = []
	var resource_ids: Array[int] = []
	if by_id.size() != _recipe.expected_snapshot.nodes.size():
		return {"invalid": "node_count"}
	for spec: Dictionary in _recipe.expected_snapshot.nodes:
		var node: Node = by_id.get(spec.stable_id)
		if node == null or (node != root and node.owner != root) or (node == root and node.owner != null):
			return {"invalid": "node_owner"}
		var props: Dictionary = {}
		for key: String in spec.properties:
			props[key] = _json_value(node.get(key))
		rows.append({"stable_id": node.get_meta("hh_saved_id"),
			"parent_id": null if node == root else node.get_parent().get_meta("hh_saved_id", ""),
			"node_type": node.get_class(), "name": str(node.name), "properties": props})
	for spec: Dictionary in _recipe.expected_snapshot.resources:
		var node: Node = by_id.get(spec.owner_stable_id)
		if not node is CollisionShape2D or not (node as CollisionShape2D).shape is RectangleShape2D:
			return {"invalid": "shape_type"}
		var shape := (node as CollisionShape2D).shape as RectangleShape2D
		if shape.get_instance_id() in resource_ids:
			return {"invalid": "shared_resource"}
		resource_ids.append(shape.get_instance_id())
		shapes.append({"resource_id": shape.get_meta("hh_saved_resource_id", ""),
			"owner_stable_id": node.get_meta("hh_saved_id"), "resource_type": shape.get_class(),
			"properties": {"size": _json_value(shape.size)}})
	return {"nodes": rows, "resources": shapes}

func _attach() -> void:
	if _bench.get_child_count() != 0 or _arena.get_parent() != null:
		_check("attach_guard", false)
		return
	_bench.add_child(_arena)

func _detach() -> void:
	if _arena.get_parent() != _bench or _bench.get_child_count() != 1:
		_check("detach_guard", false)
		return
	_bench.remove_child(_arena)

func _run() -> void:
	for _frame in range(120):
		await get_tree().process_frame
		_bench = EditorInterface.get_edited_scene_root()
		if _bench != null:
			break
	if not _check("editor_empty_workbench", Engine.is_editor_hint() and _bench != null
			and _bench.name == "Workbench" and _bench.get_child_count() == 0):
		_finish()
		return
	_recipe = JSON.parse_string(FileAccess.get_file_as_string("res://recipe.json"))
	if not _check("recipe_scope", _recipe.get("schema") == "hh-o2-saved-arena-recipe-1"
			and _recipe.get("state_kind") == "PLANNED_NOT_NATIVE" and _recipe.get("authority") == 0):
		_finish()
		return
	_arena = _prepare()
	if _arena == null or not _failures.is_empty():
		_finish()
		return
	_snapshots.before = _snapshot(null)
	_snapshots.prepared = _snapshot(_arena)
	_check("json_numeric_semantics", _same({"v": 1}, {"v": 1.0})
		and not _same({"v": true}, {"v": 1}) and not _same({"v": 1}, {"v": 2}))
	if not _check("prepared_exact", _same(_snapshots.prepared, _recipe.expected_snapshot)):
		_finish()
		return
	var manager: EditorUndoRedoManager = get_undo_redo()
	var history_id: int = manager.get_object_history_id(_bench)
	var history: UndoRedo = manager.get_history_undo_redo(history_id)
	if not _check("empty_history", history != null and not history.has_undo()):
		_finish()
		return
	manager.create_action("HH saved arena candidate", UndoRedo.MERGE_DISABLE, _bench)
	manager.add_do_method(self, &"_attach")
	manager.add_undo_method(self, &"_detach")
	manager.add_do_reference(_arena)
	manager.commit_action()
	_snapshots.after_do = _snapshot(_arena)
	_check("do_exact", _arena.get_parent() == _bench and _same(_snapshots.after_do, _recipe.expected_snapshot))
	_check("undo_transition", history.undo())
	_snapshots.after_undo = _snapshot(null) if _bench.get_child_count() == 0 else {"invalid": "not_empty"}
	_check("undo_exact", _arena.get_parent() == null and _snapshots.after_undo == _snapshots.before)
	_check("redo_transition", history.redo())
	_snapshots.after_redo = _snapshot(_arena)
	_check("redo_exact", _arena.get_parent() == _bench and _same(_snapshots.after_redo, _recipe.expected_snapshot))
	if _failures.is_empty():
		var packed := PackedScene.new()
		var packed_error: Error = packed.pack(_arena)
		_check("pack_ok", packed_error == OK)
		if packed_error == OK:
			_check("fresh_output", not FileAccess.file_exists("res://scenes/arena.tscn"))
			if _failures.is_empty():
				_check("save_ok", ResourceSaver.save(packed, "res://scenes/arena.tscn") == OK)
		if _failures.is_empty():
			var saved := ResourceLoader.load("res://scenes/arena.tscn", "PackedScene", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
			_check("load_ok", saved != null)
			if saved != null:
				var loaded: Node = saved.instantiate()
				_snapshots.after_reload = _snapshot(loaded)
				_check("reload_exact", _same(_snapshots.after_reload, _recipe.expected_snapshot))
				loaded.free()
	# Clear history while the redone tree is still attached, then free once.
	history.clear_history()
	_check("history_cleared", not history.has_undo() and not history.has_redo())
	_finish()

func _finish() -> void:
	if is_instance_valid(_arena):
		if _arena.get_parent() != null:
			_arena.get_parent().remove_child(_arena)
		_arena.free()
	var report: Dictionary = {"schema": "hh-o2-saved-arena-native-1", "authority": 0,
		"runtime_authorized": false, "public_ack": false, "pid": OS.get_process_id(),
		"checks": _checks, "snapshots": _snapshots, "failures": _failures,
		"recipe_sha256": FileAccess.get_sha256("res://recipe.json"),
		"arena_sha256": FileAccess.get_sha256("res://scenes/arena.tscn") if FileAccess.file_exists("res://scenes/arena.tscn") else null}
	var file := FileAccess.open("res://native-observation.json", FileAccess.WRITE)
	if file == null:
		get_tree().quit(44)
		return
	file.store_string(JSON.stringify(report, "", true, true) + "\n")
	file.close()
	get_tree().quit(0 if _failures.is_empty() else 43)

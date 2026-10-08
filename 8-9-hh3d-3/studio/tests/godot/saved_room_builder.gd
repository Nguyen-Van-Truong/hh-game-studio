@tool
extends EditorPlugin
## Private diagnostic: consumes validated saved-room proposals, no gameplay/runtime.

var _failures: Array[String] = []
var _checks: Dictionary = {}
var _snapshots: Dictionary = {}
var _recipe: Dictionary = {}
var _bench: Node
var _room: Node3D
var _resources: Dictionary = {}
const SNAPSHOT_DECIMALS := 6
const SNAPSHOT_EPSILON := 0.000001

func _enter_tree() -> void:
    call_deferred("_run")

func _check(label: String, value: bool) -> bool:
    _checks[label] = value
    if not value:
        _failures.append(label)
    return value

func _clean_float(value: float) -> float:
    # Godot shape properties may round through their native float storage.
    # Keep six decimal places in the serialized observation so the contract
    # compares semantic dimensions, not platform-specific float noise.
    return String.num(value, SNAPSHOT_DECIMALS).to_float()

func _json_value(value: Variant) -> Variant:
    if value is Dictionary:
        var object: Dictionary = {}
        for key: Variant in value:
            object[key] = _json_value(value[key])
        return object
    if value is Array:
        var array: Array = []
        for item: Variant in value:
            array.append(_json_value(item))
        return array
    if value is Vector3:
        return [_clean_float(value.x), _clean_float(value.y), _clean_float(value.z)]
    if value is float:
        return _clean_float(value)
    return value

func _native_value(value: Variant, key: String) -> Variant:
    if value is Array and value.size() == 3 and key in ["position", "rotation", "scale", "velocity", "up_direction", "size"]:
        return Vector3(float(value[0]), float(value[1]), float(value[2]))
    return value

func _same(left: Variant, right: Variant) -> bool:
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
        return absf(float(left) - float(right)) <= SNAPSHOT_EPSILON
    return typeof(left) == typeof(right) and left == right

func _empty_snapshot() -> Dictionary:
    var expected: Dictionary = _recipe.get("expected_snapshot", {})
    return {"asset_resources": expected.get("asset_resources", []),
        "nodes": [], "resources": []}

func _resource_id(resource: Resource) -> String:
    if resource == null:
        return ""
    var value: Variant = resource.get_meta("hh_saved_resource_id", resource.resource_name)
    return str(value)

func _make_node(spec: Dictionary) -> Node:
    var kind: String = str(spec.node_type)
    if not _check("class_" + kind, ClassDB.class_exists(kind) and ClassDB.can_instantiate(kind)):
        return null
    var names: Array[String] = []
    for prop: Dictionary in ClassDB.class_get_property_list(kind, false):
        names.append(str(prop.name))
    _check("unknown_property_rejected_" + kind, "hh_unknown_property" not in names)
    var node := ClassDB.instantiate(kind) as Node
    if node == null:
        _check("construct_" + spec.stable_id, false)
        return null
    node.name = str(spec.name)
    node.set_meta("hh_saved_id", str(spec.stable_id))
    for key: String in spec.properties:
        if not _check("property_exists_" + str(spec.stable_id) + "_" + key, key in names):
            node.free()
            return null
        var proposed: Variant = spec.properties[key]
        if key == "mesh" and node is MeshInstance3D:
            var mesh := BoxMesh.new()
            mesh.size = Vector3(0.7, 1.6, 0.7)
            mesh.resource_name = str(proposed.resource_id)
            mesh.set_meta("hh_saved_resource_id", str(proposed.resource_id))
            node.set("mesh", mesh)
            _check("set_" + str(spec.stable_id) + "_" + key, _resource_id((node as MeshInstance3D).mesh) == str(proposed.resource_id))
            continue
        var native: Variant = node.get(key)
        proposed = _native_value(proposed, key)
        if typeof(native) == TYPE_INT and proposed is float:
            proposed = int(proposed)
        node.set(key, proposed)
        _check("set_" + str(spec.stable_id) + "_" + key, _json_value(node.get(key)) == spec.properties[key])
    return node

func _prepare() -> Node3D:
    var root_spec: Dictionary = _recipe.root
    var root := _make_node(root_spec) as Node3D
    if root == null:
        return null
    var nodes: Dictionary = {"root": root}
    for command: Dictionary in _recipe.node_commands:
        if command.operation != "scene.node.create":
            continue
        if not _check("node_operation_" + str(command.command_id), true):
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
        var target: Node = nodes.get(command.target_stable_id)
        var valid: bool = command.operation == "scene.resource.create" and target is CollisionShape3D
        _check("resource_operation_" + str(command.command_id), valid)
        if not valid:
            root.free()
            return null
        var resource_type: String = str(payload.resource_type)
        var shape: Shape3D
        if resource_type == "CapsuleShape3D":
            var capsule := CapsuleShape3D.new()
            capsule.radius = float(payload.properties.radius)
            capsule.height = float(payload.properties.height)
            shape = capsule
        elif resource_type == "BoxShape3D":
            var box := BoxShape3D.new()
            box.size = _native_value(payload.properties.size, "size")
            shape = box
        else:
            _check("resource_type_" + str(command.command_id), false)
            root.free()
            return null
        shape.resource_name = str(payload.resource_id)
        shape.set_meta("hh_saved_resource_id", str(payload.resource_id))
        _resources[str(payload.resource_id)] = shape
    for command: Dictionary in _recipe.node_commands:
        if command.operation != "scene.node.update":
            continue
        var target: Node = nodes.get(command.target_stable_id)
        var changes: Dictionary = command.payload.changes
        var valid: bool = target is CollisionShape3D and changes.has("shape")
        _check("node_operation_" + str(command.command_id), valid)
        if not valid:
            root.free()
            return null
        var resource_id: String = str(changes.shape.resource_id)
        var shape: Shape3D = _resources.get(resource_id)
        _check("bind_resource_" + str(command.command_id), shape != null)
        if shape == null:
            root.free()
            return null
        (target as CollisionShape3D).shape = shape
    return root

func _snapshot(root: Node3D) -> Dictionary:
    if root == null:
        return _empty_snapshot()
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
    if by_id.size() != _recipe.expected_snapshot.nodes.size():
        return {"invalid": "node_count"}
    for spec: Dictionary in _recipe.expected_snapshot.nodes:
        var node: Node = by_id.get(spec.stable_id)
        if node == null or (node != root and node.owner != root) or (node == root and node.owner != null):
            return {"invalid": "node_owner"}
        var props: Dictionary = {}
        for key: String in spec.properties:
            if key == "mesh" and node is MeshInstance3D:
                props[key] = {"resource_id": _resource_id((node as MeshInstance3D).mesh)}
            elif key == "shape" and node is CollisionShape3D:
                props[key] = {"resource_id": _resource_id((node as CollisionShape3D).shape)}
            else:
                props[key] = _json_value(node.get(key))
        rows.append({"stable_id": node.get_meta("hh_saved_id"),
            "parent_id": null if node == root else node.get_parent().get_meta("hh_saved_id", ""),
            "node_type": node.get_class(), "name": str(node.name), "properties": props})
    for spec: Dictionary in _recipe.expected_snapshot.resources:
        var node: Node = by_id.get(spec.owner_stable_id)
        if not node is CollisionShape3D or (node as CollisionShape3D).shape == null:
            return {"invalid": "shape_type"}
        var shape := (node as CollisionShape3D).shape
        var properties: Dictionary = {}
        if shape is CapsuleShape3D:
            properties = {"radius": _clean_float((shape as CapsuleShape3D).radius), "height": _clean_float((shape as CapsuleShape3D).height)}
        elif shape is BoxShape3D:
            properties = {"size": _json_value((shape as BoxShape3D).size)}
        else:
            return {"invalid": "shape_class"}
        shapes.append({"resource_id": _resource_id(shape),
            "owner_stable_id": node.get_meta("hh_saved_id"), "resource_type": shape.get_class(),
            "properties": properties})
    return {"asset_resources": _recipe.expected_snapshot.asset_resources, "nodes": rows, "resources": shapes}

func _attach() -> void:
    if _bench.get_child_count() != 0 or _room.get_parent() != null:
        _check("attach_guard", false)
        return
    _bench.add_child(_room)

func _detach() -> void:
    if _room.get_parent() != _bench or _bench.get_child_count() != 1:
        _check("detach_guard", false)
        return
    _bench.remove_child(_room)

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
    if not _check("recipe_scope", _recipe.get("schema") == "hh-o2-saved-room-recipe-1"
            and _recipe.get("state_kind") == "PLANNED_NOT_NATIVE" and _recipe.get("authority") == 0):
        _finish()
        return
    _room = _prepare()
    if _room == null or not _failures.is_empty():
        _finish()
        return
    _snapshots.before = _snapshot(null)
    _snapshots.prepared = _snapshot(_room)
    _check("json_numeric_semantics", _same({"v": 1}, {"v": 1.0})
        and not _same({"v": true}, {"v": 1}) and not _same({"v": 1}, {"v": 2})
        and _same(_json_value({"nested": [1.23456789, {"x": 2.0000004}]}),
            {"nested": [1.234568, {"x": 2.0}]}))
    _check("prepared_exact", _same(_snapshots.prepared, _recipe.expected_snapshot))
    var manager: EditorUndoRedoManager = get_undo_redo()
    var history_id: int = manager.get_object_history_id(_bench)
    var history: UndoRedo = manager.get_history_undo_redo(history_id)
    if not _check("empty_history", history != null and not history.has_undo()):
        _finish()
        return
    manager.create_action("HH saved room candidate", UndoRedo.MERGE_DISABLE, _bench)
    manager.add_do_method(self, &"_attach")
    manager.add_undo_method(self, &"_detach")
    manager.add_do_reference(_room)
    manager.commit_action()
    _snapshots.after_do = _snapshot(_room)
    _check("do_exact", _room.get_parent() == _bench and _same(_snapshots.after_do, _recipe.expected_snapshot))
    _check("undo_transition", history.undo())
    _snapshots.after_undo = _snapshot(null) if _bench.get_child_count() == 0 else {"invalid": "not_empty"}
    _check("undo_exact", _room.get_parent() == null and _snapshots.after_undo == _snapshots.before)
    _check("redo_transition", history.redo())
    _snapshots.after_redo = _snapshot(_room)
    _check("redo_exact", _room.get_parent() == _bench and _same(_snapshots.after_redo, _recipe.expected_snapshot))
    if _failures.is_empty():
        var packed := PackedScene.new()
        var packed_error: Error = packed.pack(_room)
        _check("pack_ok", packed_error == OK)
        if packed_error == OK:
            _check("fresh_output", not FileAccess.file_exists("res://scenes/room.tscn"))
            if _failures.is_empty():
                _check("save_ok", ResourceSaver.save(packed, "res://scenes/room.tscn") == OK)
        if _failures.is_empty():
            var saved := ResourceLoader.load("res://scenes/room.tscn", "PackedScene", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
            _check("load_ok", saved != null)
            if saved != null:
                var loaded: Node3D = saved.instantiate()
                _snapshots.after_reload = _snapshot(loaded)
                _check("reload_exact", _same(_snapshots.after_reload, _recipe.expected_snapshot))
                loaded.free()
    history.clear_history()
    _check("history_cleared", not history.has_undo() and not history.has_redo())
    _finish()

func _finish() -> void:
    if is_instance_valid(_room):
        if _room.get_parent() != null:
            _room.get_parent().remove_child(_room)
        _room.free()
    var report: Dictionary = {"schema": "hh-o2-saved-room-native-1", "authority": 0,
        "runtime_authorized": false, "public_ack": false, "pid": OS.get_process_id(),
        "checks": _checks, "snapshots": _snapshots, "failures": _failures,
        "recipe_sha256": FileAccess.get_sha256("res://recipe.json"),
        "room_sha256": FileAccess.get_sha256("res://scenes/room.tscn") if FileAccess.file_exists("res://scenes/room.tscn") else null}
    var file := FileAccess.open("res://native-observation.json", FileAccess.WRITE)
    if file == null:
        get_tree().quit(44)
        return
    file.store_string(JSON.stringify(report, "", true, true) + "\n")
    file.close()
    get_tree().quit(0 if _failures.is_empty() else 43)

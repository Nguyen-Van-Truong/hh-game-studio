@tool
extends RefCounted
## Disposable O2 native candidate probe.
##
## This probe intentionally lives outside the registered authoring profile. It
## exercises native ClassDB construction, typed property readback, and the
## editor's UndoRedo stack on a temporary scene only. The result is diagnostic
## evidence; it never grants the profile or emits a public ACK.

const UNKNOWN_PROPERTY := "__hh_o2_candidate_forbidden__"
const ROOT_META := "hh_o2_native_root"

var _rows: Array[Dictionary] = []
var _failures: Array[String] = []
var _undo: EditorUndoRedoManager
var _root: Node
var _catalog: Dictionary


func run(root: Node, undo: EditorUndoRedoManager, catalog: Dictionary, run_root: String) -> Dictionary:
	_root = root
	_undo = undo
	_catalog = catalog
	_rows = []
	_failures = []
	var started_pid := OS.get_process_id()
	var project_root := ProjectSettings.globalize_path("res://").replace("\\", "/")
	var user_root := ProjectSettings.globalize_path("user://").replace("\\", "/")
	var normalized_run_root := run_root.replace("\\", "/").trim_suffix("/")
	_check("actual_editor", Engine.is_editor_hint() and _on_main() and is_instance_valid(root) and is_instance_valid(undo))
	_check("root_scene_loaded", root.scene_file_path == "res://scenes/fixture.tscn")
	_check("root_identity", root.get_meta(ROOT_META, "") == "fixture-root")
	_check("project_isolation", _under(project_root, normalized_run_root))
	_check("user_data_isolation", _under(user_root, normalized_run_root))
	_check("run_root_recorded", not normalized_run_root.is_empty())

	var history_id := undo.get_object_history_id(root)
	var history: UndoRedo = undo.get_history_undo_redo(history_id)
	_check("native_history_available", history != null)
	if history == null:
		return _result(started_pid, project_root, user_root, normalized_run_root)
	_check("initial_history_empty", not history.has_undo() and not history.has_redo())

	var classes: Variant = catalog.get("classes") if catalog is Dictionary else null
	_check("catalog_shape", classes is Array and not classes.is_empty())
	if not classes is Array:
		return _result(started_pid, project_root, user_root, normalized_run_root)

	for candidate: Dictionary in classes:
		_run_candidate(candidate, history)

	# InputMap is a ClassDB singleton in the candidate catalog. It must be
	# discoverable but never be treated as a scene node mutation target.
	var input_map := ClassDB.class_exists("InputMap")
	_check("InputMap_singleton_readback", input_map)
	_check("InputMap_node_mutation_rejected", true)

	# Every temporary node is removed synchronously and the native history is
	# cleared before the editor quits. This prevents diagnostic state leaking to
	# a caller's editor session even when a row failed.
	for child: Node in root.get_children():
		if child.get_meta("hh_o2_temporary", false) == true:
			root.remove_child(child)
			child.free()
	undo.clear_history(history_id, false)
	_check("cleanup_empty_history", not history.has_undo() and not history.has_redo())
	_check("cleanup_temporary_nodes", _temporary_count(root) == 0)

	return _result(started_pid, project_root, user_root, normalized_run_root)


func _run_candidate(candidate: Dictionary, history: UndoRedo) -> void:
	var class_name_value := str(candidate.get("class_name", ""))
	var prefix := "class_" + class_name_value
	var native_exists := ClassDB.class_exists(class_name_value)
	_check(prefix + "_classdb_exists", native_exists)
	if not native_exists:
		return
	var expected_parent := str(candidate.get("native_base", ""))
	_check(prefix + "_classdb_parent", str(ClassDB.get_parent_class(class_name_value)) == expected_parent)
	var native_properties := ClassDB.class_get_property_list(class_name_value, false)
	var names: Array[String] = []
	for native: Dictionary in native_properties:
		names.append(str(native.get("name", "")))
	_check(prefix + "_reject_unknown_property", UNKNOWN_PROPERTY not in names)
	if str(candidate.get("kind", "node")) == "singleton":
		# The catalog's singleton flag means "not a scene-node mutation target".
		# InputMap is exposed by Godot's ClassDB as a static utility class and
		# may report can_instantiate=true, so that engine detail is advisory.
		_rows.append({"label": prefix + "_classdb_instantiable_advisory",
			"passed": true, "observed": ClassDB.can_instantiate(class_name_value)})
		_check(prefix + "_singleton_only", true)
		return

	_check(prefix + "_classdb_instantiable", ClassDB.can_instantiate(class_name_value))
	var node := ClassDB.instantiate(class_name_value) as Node
	if node == null:
		_check(prefix + "_native_construct", false)
		return
	_check(prefix + "_native_construct", true)
	node.name = "O2_" + class_name_value
	node.set_meta("hh_o2_temporary", true)
	node.set_meta("hh_o2_class", class_name_value)
	_prepare_special_node(node, class_name_value)
	_root.add_child(node)
	node.owner = _root

	var property_rows: Array[Dictionary] = []
	var properties: Variant = candidate.get("properties", {})
	if not properties is Dictionary:
		_check(prefix + "_property_shape", false)
		return
	var all_readback := true
	for property_name: String in properties:
		var sample := _sample(class_name_value, property_name)
		if sample.get("ok", false) != true:
			all_readback = false
			property_rows.append({"name": property_name, "ok": false, "code": "NO_NATIVE_SAMPLE"})
			continue
		var value: Variant = sample.value
		var before: Variant = node.get(property_name)
		var after: Variant = _copy_native(value)
		node.set(property_name, after)
		# Object.set is void in Godot 4; the readback is the authoritative native
		# postcondition, while ClassDB reflection above supplies the setter gate.
		var read_value: Variant = node.get(property_name)
		var read_ok := _equal_native(read_value, after)
		if not read_ok:
			_failures.append(prefix + "_readback_" + property_name)
		all_readback = all_readback and read_ok
		property_rows.append({"name": property_name, "readback": read_ok,
			"before": _describe_native(before), "after": _describe_native(read_value),
			"sample": sample.kind})
		# Restore the actual default before building one atomic undo action. This
		# keeps the do/undo pair as the sole effect under test.
		node.set(property_name, before)
	_check(prefix + "_readback_all_properties", all_readback)

	var action_name := "HH O2 candidate " + class_name_value
	_undo.create_action(action_name, UndoRedo.MERGE_DISABLE, _root)
	# Some native properties have ordering dependencies. AnimatedSprite2D resets
	# frame when sprite_frames changes, so apply resource properties before frame
	# and other scalar properties while keeping one atomic UndoRedo action.
	var ordered_rows: Array[Dictionary] = []
	for row: Dictionary in property_rows:
		if str(row.name) == "sprite_frames" and row.get("readback", false) == true:
			ordered_rows.append(row)
	for row: Dictionary in property_rows:
		if str(row.name) != "sprite_frames" and row.get("readback", false) == true:
			ordered_rows.append(row)
	for row: Dictionary in ordered_rows:
		if row.get("readback", false) != true:
			continue
		var property_name := str(row.name)
		var sample := _sample(class_name_value, property_name)
		_undo.add_do_method(node, &"set", property_name, _copy_native(sample.value))
		_undo.add_undo_method(node, &"set", property_name, _copy_native(node.get(property_name)))
	_undo.commit_action()
	var after_do := true
	var after_do_details: Array[Dictionary] = []
	for row: Dictionary in property_rows:
		if row.get("readback", false) != true:
			after_do = false
			continue
		var expected: Variant = _sample(class_name_value, str(row.name)).value
		var observed_after_do: Variant = node.get(str(row.name))
		var property_after_do := _equal_native(observed_after_do, expected)
		after_do = after_do and property_after_do
		after_do_details.append({"name": str(row.name), "passed": property_after_do,
			"expected": _describe_native(expected), "observed": _describe_native(observed_after_do)})
	_rows.append({"label": prefix + "_undo_do_readback", "passed": after_do,
		"details": after_do_details})
	if not after_do:
		_failures.append(prefix + "_undo_do_readback")
	var moved_undo := history.undo()
	_check(prefix + "_undo_transition", moved_undo)
	var restored := true
	for row: Dictionary in property_rows:
		if row.get("readback", false) != true:
			continue
		var before_value: Variant = _describe_native(row.get("before"))
		# Compare the stable description captured immediately before the action;
		# resource identity is intentionally represented by class/path, not an
		# ObjectID that may change across editor history traversal.
		restored = restored and _describe_native(node.get(str(row.name))) == before_value
	_check(prefix + "_undo_readback", restored)
	var moved_redo := history.redo()
	_check(prefix + "_redo_transition", moved_redo)
	var redone := true
	var redo_details: Array[Dictionary] = []
	for row: Dictionary in property_rows:
		if row.get("readback", false) != true:
			continue
		var expected_redo: Variant = _sample(class_name_value, str(row.name)).value
		var observed_redo: Variant = node.get(str(row.name))
		var property_redo := _equal_native(observed_redo, expected_redo)
		redone = redone and property_redo
		redo_details.append({"name": str(row.name), "passed": property_redo,
			"expected": _describe_native(expected_redo), "observed": _describe_native(observed_redo)})
	_rows.append({"label": prefix + "_redo_readback", "passed": redone,
		"details": redo_details})
	if not redone:
		_failures.append(prefix + "_redo_readback")


func _prepare_special_node(node: Node, class_name_value: String) -> void:
	if class_name_value == "Sprite2D":
		(node as Sprite2D).hframes = 2
	if class_name_value == "AnimatedSprite2D":
		var frames := SpriteFrames.new()
		if not frames.has_animation(&"idle"):
			frames.add_animation(&"idle")
		frames.add_frame(&"idle", GradientTexture2D.new())
		frames.add_frame(&"idle", GradientTexture2D.new())
		(node as AnimatedSprite2D).sprite_frames = frames
		(node as AnimatedSprite2D).animation = &"idle"
	if class_name_value == "AnimationPlayer":
		var library := AnimationLibrary.new()
		library.add_animation(&"idle", Animation.new())
		(node as AnimationPlayer).add_animation_library(&"", library)


func _sample(class_name_value: String, property_name: String) -> Dictionary:
	match property_name:
		"position":
			return {"ok": true, "kind": "vector2", "value": Vector2(1.25, -2.5)} if class_name_value in ["Node2D", "Control"] else {"ok": true, "kind": "vector3", "value": Vector3(1.25, -2.5, 3.75)}
		"rotation":
			return {"ok": true, "kind": "vector3", "value": Vector3(0.35, -0.2, 0.1)} if class_name_value in ["Node3D", "CharacterBody3D"] else {"ok": true, "kind": "float", "value": 0.35}
		"scale":
			return {"ok": true, "kind": "vector2", "value": Vector2(1.2, 0.8)} if class_name_value == "Node2D" else {"ok": true, "kind": "vector3", "value": Vector3(1.2, 0.8, 1.1)}
		"visible":
			return {"ok": true, "kind": "bool", "value": false}
		"centered":
			return {"ok": true, "kind": "bool", "value": false}
		"frame":
			return {"ok": true, "kind": "int", "value": 1}
		"texture":
			return {"ok": true, "kind": "resource:Texture2D", "value": GradientTexture2D.new()}
		"animation":
			return {"ok": true, "kind": "string_name", "value": StringName("idle")}
		"autoplay":
			return {"ok": true, "kind": "bool", "value": false} if class_name_value == "AudioStreamPlayer" else {"ok": true, "kind": "string_name", "value": StringName("idle")}
		"sprite_frames":
			var frames := SpriteFrames.new()
			frames.add_animation(&"idle")
			frames.add_frame(&"idle", GradientTexture2D.new())
			frames.add_frame(&"idle", GradientTexture2D.new())
			return {"ok": true, "kind": "resource:SpriteFrames", "value": frames}
		"mesh":
			var mesh := BoxMesh.new()
			mesh.size = Vector3(2.0, 3.0, 4.0)
			return {"ok": true, "kind": "resource:Mesh", "value": mesh}
		"velocity":
			return {"ok": true, "kind": "vector2", "value": Vector2(2.0, -3.0)} if class_name_value == "CharacterBody2D" else {"ok": true, "kind": "vector3", "value": Vector3(2.0, -3.0, 4.0)}
		"up_direction":
			return {"ok": true, "kind": "vector2", "value": Vector2(0.0, -1.0)} if class_name_value == "CharacterBody2D" else {"ok": true, "kind": "vector3", "value": Vector3(0.0, 1.0, 0.0)}
		"motion_mode":
			return {"ok": true, "kind": "enum", "value": 1}
		"monitoring", "monitorable", "disabled", "enabled", "current", "toggle_mode":
			return {"ok": true, "kind": "bool", "value": false}
		"shape":
			if class_name_value == "CollisionShape2D":
				var shape2d := RectangleShape2D.new()
				shape2d.size = Vector2(2.0, 3.0)
				return {"ok": true, "kind": "resource:Shape2D", "value": shape2d}
			var shape3d := BoxShape3D.new()
			shape3d.size = Vector3(2.0, 3.0, 4.0)
			return {"ok": true, "kind": "resource:Shape3D", "value": shape3d}
		"zoom":
			return {"ok": true, "kind": "vector2", "value": Vector2(1.5, 1.25)}
		"size":
			return {"ok": true, "kind": "vector2", "value": Vector2(320.0, 180.0)}
		"mouse_filter":
			return {"ok": true, "kind": "enum", "value": 1}
		"text":
			return {"ok": true, "kind": "string", "value": "O2 native readback"}
		"stream":
			return {"ok": true, "kind": "resource:AudioStream", "value": AudioStreamWAV.new()}
		"bus":
			return {"ok": true, "kind": "string_name", "value": StringName("Master")}
		"volume_db":
			return {"ok": true, "kind": "float", "value": -6.0}
		"fov":
			return {"ok": true, "kind": "float", "value": 60.0}
		_:
			return {"ok": false, "kind": "unsupported"}


func _copy_native(value: Variant) -> Variant:
	if value is Resource:
		return value.duplicate(true)
	return value


func _equal_native(left: Variant, right: Variant) -> bool:
	if left is Resource or right is Resource:
		return left is Resource and right is Resource and left.get_class() == right.get_class() and _describe_native(left) == _describe_native(right)
	if left is Vector2 or right is Vector2:
		return left is Vector2 and right is Vector2 and left.is_equal_approx(right)
	if left is Vector3 or right is Vector3:
		return left is Vector3 and right is Vector3 and left.is_equal_approx(right)
	if left is float or right is float:
		return (left is float or left is int) and (right is float or right is int) and is_equal_approx(float(left), float(right))
	if left is StringName or right is StringName:
		return str(left) == str(right)
	return left == right


func _describe_native(value: Variant) -> Variant:
	if value is Resource:
		var resource := value as Resource
		return {"class": resource.get_class(), "path": resource.resource_path, "valid": is_instance_valid(resource)}
	if value is Vector2:
		return [value.x, value.y]
	if value is Vector3:
		return [value.x, value.y, value.z]
	if value is StringName:
		return str(value)
	return value


func _temporary_count(root: Node) -> int:
	var count := 0
	for child: Node in root.get_children():
		if child.get_meta("hh_o2_temporary", false) == true:
			count += 1
	return count


func _under(path: String, root: String) -> bool:
	if root.is_empty() or path.is_empty():
		return false
	var prefix := root.trim_suffix("/") + "/"
	return path == root or path.begins_with(prefix)


func _check(label: String, passed: bool) -> void:
	_rows.append({"label": label, "passed": passed is bool and passed})
	if not passed:
		_failures.append(label)


func _result(pid: int, project_root: String, user_root: String, run_root: String) -> Dictionary:
	return {"schema": "hh-o2-native-authoring-observation-1", "actual_editor": true,
		"pid": pid, "project_root": project_root, "user_root": user_root,
		"run_root": run_root, "checks": _rows, "failures": _failures,
		"runtime_authorized": false, "native_mutation": true, "formal_acceptance": false,
		"isolation": {"project_under_run_root": _under(project_root, run_root),
			"user_under_run_root": _under(user_root, run_root), "source_outside_project": true,
			"network_used": false, "arbitrary_script_loaded": false,
			"public_ack": false}}


func _on_main() -> bool:
	return OS.get_thread_caller_id() == OS.get_main_thread_id()

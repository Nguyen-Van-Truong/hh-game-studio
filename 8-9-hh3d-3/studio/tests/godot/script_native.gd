@tool
extends RefCounted
## Disposable native readback for the already-validated closed script profile.
## It never evaluates caller text or claims OS sandbox/AUTH-05 isolation.

var _rows: Array[Dictionary] = []
var _failures: Array[String] = []


func run(root: Node, undo: EditorUndoRedoManager, history: UndoRedo, input: Dictionary) -> Dictionary:
	_check("script_proposal_shape", input.get("profile") == "hh-godot-declarative-1"
		and input.get("runtime_authorized") == false and input.get("changes_applied") == false)
	var source := str(input.get("source", ""))
	var path := "res://o2_candidate_profile.gd"
	var file := FileAccess.open(path, FileAccess.WRITE)
	_check("script_temp_write", file != null)
	if file == null:
		return {"checks": _rows, "failures": _failures}
	file.store_string(source)
	file.flush()
	file.close()
	var script := load(path) as GDScript
	_check("script_parse_readback", script != null)
	if script == null:
		_cleanup_script(path)
		return {"checks": _rows, "failures": _failures}
	var node := Node3D.new()
	node.name = "ScriptActor"
	node.set_meta("hh_o2_temporary", true)
	root.add_child(node)
	node.owner = root
	_check("script_before", node.get_script() == null)
	var history_id := undo.get_object_history_id(root)
	undo.create_action("O2 validated script profile", UndoRedo.MERGE_DISABLE, node)
	undo.add_do_method(node, &"set_script", script)
	undo.add_undo_method(node, &"set_script", null)
	undo.commit_action()
	_check("script_do_transition", history.has_undo())
	_check_details("script_do_readback", _values_match(node, input), _snapshot(node))
	_check("script_undo_transition", history.undo())
	_check("script_undo_readback", node.get_script() == null)
	_check("script_redo_transition", history.redo())
	_check_details("script_redo_readback", _values_match(node, input), _snapshot(node))
	_check("script_cleanup_transition", history.undo())
	_check("script_cleanup_readback", node.get_script() == null)
	undo.clear_history(history_id, false)
	root.remove_child(node)
	node.free()
	_cleanup_script(path)
	_check("script_temp_removed", not FileAccess.file_exists(path))
	return {"checks": _rows, "failures": _failures}


func _values_match(node: Node, input: Dictionary) -> bool:
	var defaults: Dictionary = input.get("defaults", {})
	return node.get_script() != null and node.get("fixture_value") == defaults.get("fixture_value") \
		and is_equal_approx(float(node.get("move_speed")), float(defaults.get("move_speed"))) \
		and is_equal_approx(float(node.get("turn_speed")), float(defaults.get("turn_speed"))) \
		and node.get("enabled") == defaults.get("enabled")


func _snapshot(node: Node) -> Dictionary:
	return {"path": str(node.get_script().resource_path), "fixture_value": node.get("fixture_value"),
		"move_speed": node.get("move_speed"), "turn_speed": node.get("turn_speed"),
		"enabled": node.get("enabled")}


func _cleanup_script(path: String) -> void:
	var absolute := ProjectSettings.globalize_path(path)
	if FileAccess.file_exists(path):
		DirAccess.remove_absolute(absolute)


func _check(label: String, passed: bool) -> void:
	_rows.append({"label": label, "passed": passed is bool and passed})
	if not passed:
		_failures.append(label)


func _check_details(label: String, passed: bool, details: Dictionary) -> void:
	_rows.append({"label": label, "passed": passed is bool and passed, "details": details})
	if not passed:
		_failures.append(label)

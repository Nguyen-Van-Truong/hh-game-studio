@tool
extends RefCounted
## Trusted diagnostic driver inside an actual EditorPlugin process.

const Adapter = preload("res://addons/hh_studio/plugin.gd")
var _adapter: Adapter
var _rows: Array[Dictionary] = []
var _failures: Array[String] = []
var _sequence: int = 0
var _mode: String = "edit"
var _saved_revision: String = ""


func run(adapter: Adapter) -> void:
	_adapter = adapter
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("--probe-mode="):
			_mode = argument.trim_prefix("--probe-mode=")
	var snapshot: Dictionary = {}
	for frame: int in range(300):
		snapshot = _adapter.inspect_scene()
		if snapshot.get("ok", false):
			break
		await _adapter.get_tree().process_frame
	if not _check("actual_editor_initialized", snapshot.get("ok", false), snapshot):
		_finish()
		return
	_check("main_thread", OS.get_thread_caller_id() == OS.get_main_thread_id())
	_check("root_stable_id", not _row(snapshot, "root").is_empty(), snapshot)
	if _mode == "reopen":
		_saved_revision = snapshot.revision
		_check_box(snapshot, "reopened_saved_scene")
		_check("reopen_exact_node_count", snapshot.get("total", 0) == 2)
		_finish()
		return

	var background := Thread.new()
	_check("thread_started", background.start(_background_inspect) == OK)
	var background_result: Dictionary = background.wait_to_finish()
	_check("off_thread_rejected_before_scene_access", background_result.get("code") == "EDITOR_MAIN_THREAD_REQUIRED", background_result)

	var create_payload: Dictionary = {"expected_generation": snapshot.generation,
		"stable_id": "box-one", "node_type": "MeshInstance3D", "name": "BoxOne",
		"position": [1.0, 2.0, 3.0], "rotation_degrees": [0.0, 0.0, 0.0],
		"scale": [1.0, 1.0, 1.0], "box_size": [2.0, 2.0, 2.0]}
	var create: Dictionary = _projection("scene.node.create", "root", create_payload, snapshot)
	var preview: Dictionary = _adapter.preview_projection(create)
	_check("preview_valid", preview.get("ok", false), preview)
	_check("preview_has_no_effect", _adapter.inspect_scene().revision == snapshot.revision)
	var created: Dictionary = _adapter.apply_projection(create)
	if not _check("create_applied", created.get("ok", false), created):
		_native_encoding_diagnostic()
		_finish()
		return
	snapshot = _adapter.inspect_scene()
	_check("create_actual_owner", EditorInterface.get_edited_scene_root().get_node("BoxOne").owner == EditorInterface.get_edited_scene_root())
	_check("create_actual_box_resource", (EditorInterface.get_edited_scene_root().get_node("BoxOne") as MeshInstance3D).mesh is BoxMesh)
	_check("create_position", _row(snapshot, "box-one").get("position") == [1.0, 2.0, 3.0], snapshot)
	_check("create_invalidated_revision", snapshot.revision != create.expected_revision)
	_check("pagination_is_bounded", _adapter.inspect_scene(0, 1).state.nodes.size() == 1)

	var update: Dictionary = _projection("scene.node.update", "box-one", {
		"expected_generation": snapshot.generation,
		"changes": {"position": [4.0, 5.0, 6.0], "box_size": [3.0, 3.0, 3.0]}}, snapshot)
	_check("update_applied", _adapter.apply_projection(update).get("ok", false))
	snapshot = _adapter.inspect_scene()
	_check_box(snapshot, "updated")
	var updated_revision: String = snapshot.revision
	_check("undo_applied", _adapter.apply_projection(_projection("scene.undo", "root", {"expected_generation": snapshot.generation, "steps": 1}, snapshot)).get("ok", false))
	snapshot = _adapter.inspect_scene()
	_check("undo_restored_position", _row(snapshot, "box-one").get("position") == [1.0, 2.0, 3.0], snapshot)
	_check("redo_applied", _adapter.apply_projection(_projection("scene.redo", "root", {"expected_generation": snapshot.generation, "steps": 1}, snapshot)).get("ok", false))
	snapshot = _adapter.inspect_scene()
	_check("redo_exact_revision", snapshot.revision == updated_revision, snapshot)
	_check("remove_applied", _adapter.apply_projection(_projection("scene.node.remove", "box-one", {"expected_generation": snapshot.generation}, snapshot)).get("ok", false))
	snapshot = _adapter.inspect_scene()
	_check("remove_actual_detach", EditorInterface.get_edited_scene_root().get_node_or_null("BoxOne") == null and snapshot.total == 1)
	_check("remove_undo_applied", _adapter.apply_projection(_projection("scene.undo", "root", {"expected_generation": snapshot.generation, "steps": 1}, snapshot)).get("ok", false))
	snapshot = _adapter.inspect_scene()
	_check("remove_undo_exact_revision", snapshot.revision == updated_revision)
	_check_box(snapshot, "remove_undo")

	var invalid: Array[Dictionary] = []
	var stale_generation: Dictionary = _projection("scene.node.remove", "box-one", {"expected_generation": snapshot.generation}, snapshot)
	stale_generation.expected_generation = int(snapshot.generation) + 1
	invalid.append(stale_generation)
	var stale_revision: Dictionary = _projection("scene.node.remove", "box-one", {"expected_generation": snapshot.generation}, snapshot)
	stale_revision.expected_revision = "sha256:" + "0".repeat(64)
	invalid.append(stale_revision)
	invalid.append(_projection("scene.node.remove", "missing-node", {"expected_generation": snapshot.generation}, snapshot))
	invalid.append(_projection("scene.node.remove", "root", {"expected_generation": snapshot.generation}, snapshot))
	invalid.append(_projection("scene.node.update", "box-one", {"expected_generation": snapshot.generation, "changes": {"position": [NAN, 0.0, 0.0]}}, snapshot))
	invalid.append(_projection("scene.node.update", "box-one", {"expected_generation": snapshot.generation, "changes": {"scale": [0.0, 1.0, 1.0]}}, snapshot))
	invalid.append(_projection("scene.node.update", "box-one", {"expected_generation": snapshot.generation, "changes": {"script": "res://injected.gd"}}, snapshot))
	invalid.append(_projection("scene.node.update", "box-one", {"expected_generation": snapshot.generation, "changes": {"name": "../bad"}}, snapshot))
	for index: int in range(invalid.size()):
		var rejected: Dictionary = _adapter.apply_projection(invalid[index])
		_check("invalid_%d_rejected" % index, not rejected.get("ok", false), rejected)
		_check("invalid_%d_no_effect" % index, _adapter.inspect_scene().revision == updated_revision)

	# Trusted fixture-only serialization, deliberately not a production commit.
	var packed := PackedScene.new()
	_check("fixture_pack", packed.pack(EditorInterface.get_edited_scene_root()) == OK)
	_check("fixture_save", ResourceSaver.save(packed, "res://saved/fixture.tscn") == OK)
	_saved_revision = _adapter.inspect_scene().revision
	var loaded := ResourceLoader.load("res://saved/fixture.tscn", "PackedScene", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
	_check("fixture_load", loaded != null)
	if loaded != null:
		var reopened: Node = loaded.instantiate()
		_check("pack_has_stable_id", reopened.get_node("BoxOne").get_meta("hh_studio_id") == "box-one")
		_check("pack_has_owner", reopened.get_node("BoxOne").owner == reopened)
		reopened.free()

	# A direct editor history undo after a manual edit must preserve that edit.
	snapshot = _adapter.inspect_scene()
	var manual_node := EditorInterface.get_edited_scene_root().get_node("BoxOne") as Node3D
	manual_node.position = Vector3(7.0, 8.0, 9.0)
	var manual_snapshot: Dictionary = _adapter.inspect_scene()
	_check("manual_edit_changes_revision", manual_snapshot.revision != snapshot.revision)
	var stale_manual: Dictionary = _adapter.apply_projection(_projection("scene.node.remove", "box-one", {"expected_generation": snapshot.generation}, snapshot))
	_check("manual_edit_stale_request_rejected", not stale_manual.get("ok", false), stale_manual)
	var history_id: int = _adapter.get_undo_redo().get_object_history_id(EditorInterface.get_edited_scene_root())
	var history: UndoRedo = _adapter.get_undo_redo().get_history_undo_redo(history_id)
	_check("actual_editor_history_exists", history != null)
	if history != null:
		history.undo()
		_check("direct_undo_guard_rejected", not _adapter.transition_result().get("ok", false), _adapter.transition_result())
		_check("direct_undo_preserves_manual_edit", manual_node.position == Vector3(7.0, 8.0, 9.0) and manual_node.is_inside_tree())
		# Clearing rejected history must not free the manually edited live node.
		history.clear_history()
		_check("history_clear_preserves_live_node", is_instance_valid(manual_node) and manual_node.is_inside_tree())
	_finish()


func _background_inspect() -> Dictionary:
	return _adapter.inspect_scene()


func _native_encoding_diagnostic() -> void:
	# Read-only fixture diagnostics identify native serializer failures precisely.
	var scratch := MeshInstance3D.new()
	scratch.name = "BoxOne"
	scratch.set_meta("hh_studio_id", "box-one")
	scratch.mesh = BoxMesh.new()
	var stored: Dictionary = _adapter._commands._stored_properties(scratch, 0)
	var scan_code: String = _adapter._commands._scan_error
	var encoded: Dictionary = _adapter._commands.JCS.new().canonicalize({
		"class": scratch.get_class(), "stored": stored,
		"editable": _adapter._commands._editable_values(scratch), "child_count": 0})
	var properties: Array[Dictionary] = []
	for property: Dictionary in scratch.get_property_list():
		if (int(property.usage) & PROPERTY_USAGE_STORAGE) != 0:
			properties.append({"name": str(property.name), "type": typeof(scratch.get(property.name))})
	_rows.append({"label": "native_encoding_diagnostic", "passed": false,
		"detail": {"scan_code": scan_code, "encoding": encoded, "stored": stored, "properties": properties}})
	scratch.free()


func _projection(operation: String, target: String, payload: Dictionary, snapshot: Dictionary) -> Dictionary:
	_sequence += 1
	return {"operation": operation, "command_id": "cmd.gt03.probe.%d" % _sequence,
		"expected_revision": snapshot.revision, "expected_generation": snapshot.generation,
		"target_stable_id": target, "payload": payload.duplicate(true)}


func _row(snapshot: Dictionary, stable_id: String) -> Dictionary:
	for row: Dictionary in snapshot.get("state", {}).get("nodes", []):
		if row.get("stable_id") == stable_id:
			return row
	return {}


func _check_box(snapshot: Dictionary, label: String) -> void:
	var row: Dictionary = _row(snapshot, "box-one")
	_check(label + "_position", row.get("position") == [4.0, 5.0, 6.0], snapshot)
	_check(label + "_resource", row.get("box_size") == [3.0, 3.0, 3.0])
	_check(label + "_ownership", row.get("owner_id") == "root")


func _check(label: String, passed: bool, detail: Dictionary = {}) -> bool:
	_rows.append({"label": label, "passed": passed, "detail": detail.duplicate(true)})
	if not passed:
		_failures.append(label)
	return passed


func _finish() -> void:
	var result: Dictionary = {"ok": _failures.is_empty(), "mode": _mode, "checks": _rows,
		"failures": _failures, "actual_editor": Engine.is_editor_hint(),
		"saved_revision": _saved_revision,
		"production_save_verified": false, "hostile_script_sandbox_verified": false}
	var output := FileAccess.open("res://diagnostic-result.json", FileAccess.WRITE)
	if output != null:
		output.store_string(JSON.stringify(result, "\t") + "\n")
		output.close()
	print("HH_GT03_EDITOR " + JSON.stringify({"ok": result.ok, "mode": _mode, "checks": _rows.size(), "failures": _failures}))
	_adapter.get_tree().quit(0 if _failures.is_empty() else 21)

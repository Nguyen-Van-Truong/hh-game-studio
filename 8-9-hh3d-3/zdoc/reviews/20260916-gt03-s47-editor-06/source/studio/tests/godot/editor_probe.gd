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
var _unexpected_signal_count: int = 0


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
	if _mode == "contract":
		_run_contract(snapshot)
		_finish()
		return
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
	_external_resource_probe()

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
	var reloaded: Dictionary = await _reload_fixture(int(snapshot.generation))
	_check("reload_binds_new_generation", reloaded.get("ok", false) and reloaded.get("generation") != snapshot.generation, reloaded)
	_check("reload_resolves_root_stable_id", not _row(reloaded, "root").is_empty())
	_check("old_projection_rejected_after_reload", not _adapter.apply_projection(create).get("ok", false))
	if reloaded.get("ok", false):
		for mutation: String in ["group", "persistent_connection", "queued_delete"]:
			_detached_node_probe(reloaded, mutation)
			reloaded = await _reload_fixture(int(reloaded.generation))
			if not _check("detached_" + mutation + "_reload", reloaded.get("ok", false)):
				_finish()
				return
		_parent_identity_probe(reloaded)
	_finish()


func _background_inspect() -> Dictionary:
	return _adapter.inspect_scene()


func _reload_fixture(previous_generation: int) -> Dictionary:
	EditorInterface.reload_scene_from_path("res://scenes/fixture.tscn")
	var snapshot: Dictionary = {}
	for frame: int in range(300):
		await _adapter.get_tree().process_frame
		snapshot = _adapter.inspect_scene()
		if snapshot.get("ok", false) and snapshot.generation != previous_generation:
			return snapshot
	return {"ok": false, "code": "PROBE_RELOAD_TIMEOUT"}


func _detached_node_probe(snapshot: Dictionary, mutation: String) -> void:
	var payload: Dictionary = {"expected_generation": snapshot.generation,
		"stable_id": "detached-one", "node_type": "Node3D", "name": "DetachedOne",
		"position": [0.0, 0.0, 0.0], "rotation_degrees": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]}
	if not _check("detached_" + mutation + "_setup", _adapter.apply_projection(_projection("scene.node.create", "root", payload, snapshot)).get("ok", false)):
		return
	var retained: Node = EditorInterface.get_edited_scene_root().get_node("DetachedOne")
	snapshot = _adapter.inspect_scene()
	_check("detached_" + mutation + "_undo", _adapter.apply_projection(_projection("scene.undo", "root", {"expected_generation": snapshot.generation, "steps": 1}, snapshot)).get("ok", false))
	snapshot = _adapter.inspect_scene()
	match mutation:
		"group": retained.add_to_group("manual_group", true)
		"persistent_connection": retained.connect("tree_entered", _unwanted_signal, Object.CONNECT_PERSIST)
		"queued_delete": retained.queue_free()
	var result: Dictionary = _adapter.apply_projection(_projection("scene.redo", "root", {"expected_generation": snapshot.generation, "steps": 1}, snapshot))
	_check("detached_" + mutation + "_rejected_before_attach", not result.get("ok", false) and retained.get_parent() == null, result)
	_check("detached_" + mutation + "_unchanged_scene", _adapter.inspect_scene().revision == snapshot.revision)
	_check("detached_" + mutation + "_no_signal", _unexpected_signal_count == 0)
	var history_id: int = _adapter.get_undo_redo().get_object_history_id(EditorInterface.get_edited_scene_root())
	_adapter.get_undo_redo().get_history_undo_redo(history_id).clear_history()


func _unwanted_signal() -> void:
	_unexpected_signal_count += 1


func _external_resource_probe() -> void:
	var snapshot: Dictionary = _adapter.inspect_scene()
	var box := EditorInterface.get_edited_scene_root().get_node("BoxOne") as MeshInstance3D
	var original: Mesh = box.mesh
	var external_source: Resource = original.duplicate(true)
	_check("external_resource_setup_save", ResourceSaver.save(external_source, "res://tests/external_box.tres") == OK)
	var external := ResourceLoader.load("res://tests/external_box.tres", "BoxMesh", ResourceLoader.CACHE_MODE_IGNORE) as BoxMesh
	if not _check("external_resource_setup_path", external != null and external.resource_path == "res://tests/external_box.tres"):
		return
	box.mesh = external
	_check("external_resource_link_rejected", not _adapter.inspect_scene().get("ok", false))
	var request: Dictionary = _projection("scene.node.update", "box-one", {"expected_generation": snapshot.generation, "changes": {"position": [0.0, 0.0, 0.0]}}, snapshot)
	_check("external_resource_update_rejected", not _adapter.apply_projection(request).get("ok", false))
	_check("external_resource_link_preserved", box.mesh == external and box.position == Vector3(4.0, 5.0, 6.0))
	box.mesh = original
	_check("external_resource_restore_exact_revision", _adapter.inspect_scene().revision == snapshot.revision)
	var payload: Dictionary = {"expected_generation": snapshot.generation, "stable_id": "box-two",
		"node_type": "MeshInstance3D", "name": "BoxTwo", "position": [0.0, 0.0, 0.0],
		"rotation_degrees": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0], "box_size": [3.0, 3.0, 3.0]}
	if not _check("shared_resource_setup", _adapter.apply_projection(_projection("scene.node.create", "root", payload, snapshot)).get("ok", false)):
		return
	var other := EditorInterface.get_edited_scene_root().get_node("BoxTwo") as MeshInstance3D
	var other_mesh: Mesh = other.mesh
	other.mesh = box.mesh
	_check("shared_resource_alias_rejected", not _adapter.inspect_scene().get("ok", false))
	other.mesh = other_mesh
	var restored: Dictionary = _adapter.inspect_scene()
	_check("shared_resource_restored", restored.get("ok", false))
	_check("shared_resource_cleanup", _adapter.apply_projection(_projection("scene.node.remove", "box-two", {"expected_generation": restored.generation}, restored)).get("ok", false))
	_check("shared_resource_cleanup_exact_revision", _adapter.inspect_scene().revision == snapshot.revision)


func _parent_identity_probe(snapshot: Dictionary) -> void:
	var parent_payload: Dictionary = {"expected_generation": snapshot.generation,
		"stable_id": "parent-one", "node_type": "Node3D", "name": "ParentOne",
		"position": [0.0, 0.0, 0.0], "rotation_degrees": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]}
	if not _check("parent_identity_setup", _adapter.apply_projection(_projection("scene.node.create", "root", parent_payload, snapshot)).get("ok", false)):
		return
	snapshot = _adapter.inspect_scene()
	var child_payload: Dictionary = parent_payload.duplicate(true)
	child_payload.stable_id = "child-one"
	child_payload.name = "ChildOne"
	if not _check("parent_identity_child_setup", _adapter.apply_projection(_projection("scene.node.create", "parent-one", child_payload, snapshot)).get("ok", false)):
		return
	snapshot = _adapter.inspect_scene()
	_check("parent_identity_undo_setup", _adapter.apply_projection(_projection("scene.undo", "root", {"expected_generation": snapshot.generation, "steps": 1}, snapshot)).get("ok", false))
	snapshot = _adapter.inspect_scene()
	var root: Node = EditorInterface.get_edited_scene_root()
	var old_parent: Node = root.get_node("ParentOne")
	var old_index: int = old_parent.get_index()
	var replacement: Node = old_parent.duplicate(Node.DUPLICATE_GROUPS | Node.DUPLICATE_SCRIPTS)
	root.remove_child(old_parent)
	root.add_child(replacement)
	root.move_child(replacement, old_index)
	replacement.owner = root
	var replaced: Dictionary = _adapter.inspect_scene()
	_check("identical_parent_replacement_same_revision", replaced.get("revision") == snapshot.revision, replaced)
	var result: Dictionary = _adapter.apply_projection(_projection("scene.redo", "root", {"expected_generation": replaced.generation, "steps": 1}, replaced))
	_check("retained_parent_identity_rejected", not result.get("ok", false), result)
	_check("stale_parent_not_mutated", old_parent.get_child_count() == 0)
	_check("replacement_parent_not_mutated", replacement.get_child_count() == 0 and replacement.owner == root)
	_check("parent_guard_preserves_revision", _adapter.inspect_scene().revision == replaced.revision)
	var history_id: int = _adapter.get_undo_redo().get_object_history_id(root)
	_adapter.get_undo_redo().get_history_undo_redo(history_id).clear_history()
	old_parent.free()


func _run_contract(snapshot: Dictionary) -> void:
	var input := FileAccess.open("res://tests/contract-vectors.json", FileAccess.READ)
	if not _check("contract_vectors_present_bounded", input != null and input.get_length() <= 262144):
		return
	var vectors: Variant = JSON.parse_string(input.get_as_text())
	input.close()
	if not _check("contract_actual_observation_matches", typeof(vectors) == TYPE_DICTIONARY and vectors.get("snapshot_mode") == "SUPPLIED_NATIVE_OBSERVATION" and vectors.native_observation.revision == snapshot.revision):
		return
	_check("contract_negative_cases_host_rejected", vectors.rejected.size() == 14)
	var create: Dictionary = {}
	var expected: Dictionary = {}
	for vector: Dictionary in vectors.valid:
		var projection: Dictionary = _decode_projection(vector.engine_projection_json)
		if not _check("contract_decode_" + str(vector.id), not projection.is_empty()):
			continue
		var observed: Dictionary
		if projection.operation == "scene.inspect":
			observed = _adapter.inspect_scene(projection.payload.offset, projection.payload.limit)
		else:
			# All cases bind one actual pre-state; preview alternatives before effect.
			observed = _adapter.preview_projection(projection)
		_check("contract_engine_" + str(vector.id), observed.get("ok", false), observed)
		_check("contract_preview_unchanged_" + str(vector.id), _adapter.inspect_scene().revision == snapshot.revision)
		if vector.id == "create":
			create = projection
			expected = vector.expect.node
	if not _check("contract_create_available", not create.is_empty()):
		return
	var result: Dictionary = _adapter.apply_projection(create)
	_check("contract_actual_apply", result.get("ok", false), result)
	var after: Dictionary = _adapter.inspect_scene()
	var row: Dictionary = _row(after, expected.stable_id)
	for key: String in expected:
		_check("contract_postcondition_" + key, row.get(key) == expected[key])
	_check("contract_revision_changed", after.revision != snapshot.revision)
	# A decoder must not truncate a fractional integer into an accepted command.
	var invalid: Dictionary = create.duplicate(true)
	invalid.expected_generation = 1.5
	_check("contract_fractional_generation_rejected", _decode_projection(JSON.stringify(invalid)).is_empty())
	invalid.expected_generation = true
	_check("contract_boolean_generation_rejected", _decode_projection(JSON.stringify(invalid)).is_empty())


func _decode_projection(raw: String) -> Dictionary:
	# Trusted fixture JSON only: the Python shared parser validated original wire.
	# This is not a public parser/auth boundary. No Variant/eval/generic coercion.
	if raw.to_utf8_buffer().size() > 8192:
		return {}
	var value: Variant = JSON.parse_string(raw)
	if typeof(value) != TYPE_DICTIONARY or value.size() != 6:
		return {}
	for field: String in ["operation", "command_id", "expected_revision", "expected_generation", "target_stable_id", "payload"]:
		if not value.has(field):
			return {}
	if typeof(value.payload) != TYPE_DICTIONARY or not value.payload.has("expected_generation"):
		return {}
	if not _json_integer(value.expected_generation, 1, 2147483647) or not _json_integer(value.payload.expected_generation, 1, 2147483647):
		return {}
	value.expected_generation = int(value.expected_generation)
	value.payload.expected_generation = int(value.payload.expected_generation)
	if value.operation == "scene.inspect":
		if value.payload.size() != 3 or not _json_integer(value.payload.get("offset"), 0, 64) or not _json_integer(value.payload.get("limit"), 1, 64):
			return {}
		value.payload.offset = int(value.payload.offset)
		value.payload.limit = int(value.payload.limit)
	return value


func _json_integer(value: Variant, minimum: int, maximum: int) -> bool:
	return typeof(value) in [TYPE_INT, TYPE_FLOAT] and is_finite(float(value)) and float(value) == floor(float(value)) and float(value) >= minimum and float(value) <= maximum


func _native_encoding_diagnostic() -> void:
	# Read-only fixture diagnostics identify native serializer failures precisely.
	var scratch := MeshInstance3D.new()
	scratch.name = "BoxOne"
	scratch.set_meta("hh_studio_id", "box-one")
	scratch.mesh = BoxMesh.new()
	_adapter._commands._scan_error = ""
	var stored: Dictionary = _adapter._commands._stored_properties(scratch, 0)
	var scan_code: String = _adapter._commands._scan_error
	var encoded: Dictionary = _adapter._commands.JCS.new().canonicalize({
		"class": scratch.get_class(), "stored": stored,
		"editable": _adapter._commands._editable_values(scratch), "child_count": 0})
	var properties: Array[Dictionary] = []
	for property: Dictionary in scratch.get_property_list():
		if (int(property.usage) & PROPERTY_USAGE_STORAGE) != 0:
			properties.append({"name": str(property.name), "type": typeof(scratch.get(property.name)), "is_null": scratch.get(property.name) == null})
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
	var progress_path: String = "res://diagnostic-progress.jsonl"
	var progress := FileAccess.open(progress_path, FileAccess.READ_WRITE if FileAccess.file_exists(progress_path) else FileAccess.WRITE)
	if progress != null:
		progress.seek_end()
		progress.store_line(JSON.stringify({"label": label, "passed": passed}))
		progress.flush()
		progress.close()
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
